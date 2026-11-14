"""The soak run of phase 4 (navegador/rodaje.py) on a fake clock: the day's plan (working hours, the long gap, the jitter,
the weekend, a restart), the caps of each write, nothing done twice across days, comments only with the operator's
texts, the stops (3) and what only someone on the server fixes (4), the budgets, the summary without names or ids, the
status table and the command. The runner first talks to a fake client that keeps an invented LinkedIn in memory; the
last tests go through the real service on the fake browser (tests/falsos.py). Nothing here reaches a network."""
import asyncio
import io
import json
import os
import random
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from aiohttp.test_utils import TestClient, TestServer

from linkedin_directo import LinkedInError
from linkedin_directo.servicio import ServiceTransport
from linkedin_directo.transporte import Answer, Request, Transport, check_answer

from navegador import __main__ as cli
from navegador import ajustes, rodaje
from navegador.almacen import Store
from navegador.rodaje import CANNOT, DONE, STOPPED, Ritmo, Rodaje, counts, plan
from navegador.servidor import build
from tests.falsos import TOKEN, Browser, World, account_dir, raw

ZONE = ZoneInfo('America/Bogota')
WEDNESDAY, SATURDAY = date(2026, 11, 11), date(2026, 11, 14)
OWN = 'ACoCuentaFicticia01'
PEOPLE = [f'ACoPersonaFicticia{i:04d}' for i in range(40)]
INVITERS = [f'ACoInvitaFicticia{i:04d}' for i in range(6)]
WRITE_OPS = ('add_reaction', 'follow_user', 'send_invitation', 'accept_invitation', 'create_comment',
             'comment_in_thread')


def moment(day, hour, minute=0):
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=ZONE).timestamp()


class Clock:
    def __init__(self, now):
        self.now = now

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += max(seconds, 0)


class Mundo:
    """An invented LinkedIn: 40 people (half of them creators), three posts each (the first one large), six people who
    invited the account, one unread chat. Writes change it, as LinkedIn would."""

    def __init__(self):
        self.people = {p: {'network_distance': 'OUT_OF_NETWORK', 'is_following': False, 'relation_request_status': '',
                           'followers': 12000 if i % 2 == 0 else 800} for i, p in enumerate(PEOPLE)}
        self.posts = {str(7100000000000000000 + i * 10 + j): {'author': p, 'reactions': 120 if j == 0 else 10,
                                                              'reacted': False}
                      for i, p in enumerate(PEOPLE) for j in range(3)}
        self.received = {str(900000 + k): p for k, p in enumerate(INVITERS)}
        for p in INVITERS:
            self.people[p] = {'network_distance': 'SECOND_DEGREE', 'is_following': False, 'relation_request_status': '',
                              'followers': 300}
        self.comments, self.writes, self.searches = {}, [], 0


class FakeClient:
    """Cliente's methods over an invented LinkedIn: each sends its requests (one per real call) through the transport
    it is given and judges the answer as the real client does, so the soak's recorder, budgets and stops see them."""

    def __init__(self, transport, world):
        self.t, self.w, self.me = transport, world, {}

    def _send(self, operation, write=False, kind='voyager'):
        request = Request('POST' if write else 'GET', f'/voyager/api/{operation}', kind, None, write, operation)
        return check_answer(request, self.t.send(request))

    def _write(self, operation, target):
        self._send(operation, write=True)
        self.w.writes.append((operation, target))

    def account_status(self):
        self._send('account_status')
        self.me = {'fsd': OWN, 'public_id': 'cuenta-ficticia'}
        return {'status': 'running'}

    def search_parameters(self, kind, words, limit=5):
        for _ in range(3):
            self._send('search_parameters')
        return [{'id': '103644278', 'name': words}]

    def search_people(self, words, location=None):
        self._send('search_people', kind='page')
        start, self.w.searches = self.w.searches * 10 % len(PEOPLE), self.w.searches + 1
        return [{'id': p, 'type': 'individual'} for p in (PEOPLE * 2)[start:start + 10]]

    def list_user_posts(self, user, limit=10):
        if user == 'me':
            self.account_status()
            self._send('list_user_posts')
            return []
        self._send('list_user_posts')
        return [{'id': pid, 'author': {'id': p['author'], 'type': 'individual'}, 'reactions_counter': p['reactions'],
                 'user_reacted': p['reacted'], 'is_repost': False}
                for pid, p in self.w.posts.items() if p['author'] == user][:limit]

    def get_profile(self, person):
        self._send('get_profile')
        self._send('get_profile')
        found = self.w.people[person]
        return {'id': person, 'network_distance': found['network_distance'], 'is_following': found['is_following'],
                'relation_request_status': found['relation_request_status'],
                'signals': {'followers': found['followers']}}

    def get_post(self, post):
        self._send('get_post')
        return {'id': post, 'user_reacted': self.w.posts[post]['reacted']}

    def list_comments(self, post, limit=50):
        self._send('list_comments')
        return list(self.w.comments.get(post, []))

    def list_comment_thread(self, post, comment, limit=50):
        self._send('list_comment_thread')
        return []

    def list_chats(self, limit=20):
        self._send('list_chats')
        return [{'id': '2-Y2hhdC1maWN0aWNpbw==', 'unread_count': 1}]

    def list_chat_messages(self, chat, limit=10):
        self._send('list_chat_messages')
        return []

    def own_audience(self):
        self._send('own_audience')
        return {'followers': 3, 'connections': 1}

    def profile_views(self, days=14):
        self._send('profile_views')
        return 2

    def analytics(self, start, end):
        self._send('analytics', kind='sdui')
        return {}

    def list_invitations(self, kind, limit=100):
        self._send('list_invitations')
        if kind == 'sent':
            return []
        return [{'id': iid, 'user': {'id': p}} for iid, p in self.w.received.items()]

    def accept_invitation(self, iid):
        self._write('accept_invitation', iid)
        self.w.people[self.w.received.pop(iid)]['network_distance'] = 'FIRST_DEGREE'

    def add_reaction(self, post, reaction):
        self._write('add_reaction', post)
        self.w.posts[post]['reacted'] = True

    def follow_user(self, person):
        self._write('follow_user', person)
        self.w.people[person]['is_following'] = True

    def send_invitation(self, person):
        self._write('send_invitation', person)
        self.w.people[person]['relation_request_status'] = 'PENDING'

    def create_comment(self, post, text):
        self._write('create_comment', post)
        self.w.comments.setdefault(post, []).append({'id': '1', 'is_sender': True, 'text': text})


class Linea(Transport):
    """The service as the soak sees it: every call takes 5 s; `script(request, n)` may answer something else (an
    Answer) or refuse (an exception), by the call's number."""

    def __init__(self, clock, script=None):
        self.clock, self.script, self.calls = clock, script, []

    def send(self, request):
        self.clock.now += 5
        self.calls.append((self.clock.now, request.operation, request.write))
        found = self.script(request, len(self.calls)) if self.script else None
        if isinstance(found, BaseException):
            raise found
        return found or Answer(200, '{"data":{}}', 'application/json', 'https://www.linkedin.com/voyager/api/x')


class SoakCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.data = Path(tmp.name)
        account_dir(self.data)
        self.world = Mundo()

    def soak(self, now, script=None, ritmo=None, seed='semilla'):
        self.clock = Clock(now)
        self.line = Linea(self.clock, script)
        return Rodaje('prueba', self.data, self.line, ritmo or Ritmo(), client=lambda t: FakeClient(t, self.world),
                      clock=self.clock, sleep=self.clock.sleep, rand=random.Random(7), seed=seed)

    def summary(self, day):
        return json.loads((self.data / 'cuentas' / 'prueba' / 'rodaje' / f'rodaje-{day}.json').read_text())

    def writes(self):
        return [(at, op) for at, op, write in self.line.calls if write]


class PlanTests(unittest.TestCase):
    def test_a_weekday_spreads_over_the_working_hours_around_one_long_gap(self):
        events, info = plan(WEDNESDAY, Ritmo(), random.Random(3))
        start, end = moment(WEDNESDAY, 8), moment(WEDNESDAY, 20)
        moments = [at for at, _ in events]
        self.assertEqual(moments, sorted(moments))
        self.assertTrue(all(start <= at < end for at in moments))
        names = [name for _, name in events]
        self.assertEqual({n: names.count(n) for n in rodaje.ROUTINES}, rodaje.ROUTINES)
        self.assertEqual({k: names.count(k) for k in rodaje.WRITES}, {k: rodaje.WRITE_DEFAULTS[k] for k in rodaje.WRITES})
        self.assertNotIn('aceptaciones', names)  # they go with the network rounds
        first = {name: next(at for at, n in events if n == name) for name in rodaje.FIRST}
        self.assertTrue(start + 120 <= first['descubrir'] <= start + 600)
        self.assertTrue(start + 720 <= first['referentes'] <= start + 1500)
        gaps = [(b - a, a) for a, b in zip(moments, moments[1:])]
        longest, at = max(gaps)
        self.assertGreaterEqual(longest, 3600)
        self.assertTrue(moment(WEDNESDAY, 11) <= at <= moment(WEDNESDAY, 16))
        self.assertEqual(sum(1 for gap, _ in gaps if gap >= 3600), 1)
        self.assertRegex(info['pausa_larga'], r'^1[1-6]:\d\d-1[2-8]:\d\d$')
        writes = sorted(at for at, name in events if name in rodaje.WRITES)
        self.assertGreaterEqual(writes[0], start + rodaje.WARMUP * 60)
        self.assertTrue(all(b - a >= 20 * 60 for a, b in zip(writes, writes[1:])))

    def test_runs_are_not_on_a_grid(self):
        one = [at for at, name in plan(WEDNESDAY, Ritmo(), random.Random(1))[0] if name == 'bandeja']
        steps = {round(b - a) for a, b in zip(one, one[1:])}
        self.assertGreater(len(steps), 5)

    def test_the_weekend_goes_at_half_pace(self):
        runs, writes = counts(Ritmo(), weekend=True)
        self.assertEqual(runs, {'descubrir': 1, 'referentes': 2, 'perfiles': 4, 'borradores': 3, 'bandeja': 6,
                                'propios': 3, 'metricas': 2, 'red': 1, 'analitica': 1, 'canario': 1})
        self.assertEqual(writes, {'reacciones': 3, 'seguimientos': 2, 'invitaciones': 1, 'comentarios': 0,
                                  'respuestas': 0, 'aceptaciones': 2})
        events, info = plan(SATURDAY, Ritmo(), random.Random(3))
        self.assertTrue(info['fin_de_semana'])
        self.assertEqual(len(events), sum(runs.values()) + 6)

    def test_the_scale_multiplies_the_reads_but_not_the_daily_ones(self):
        runs, writes = counts(Ritmo(scale=2), weekend=False)
        self.assertEqual((runs['bandeja'], runs['referentes'], runs['analitica'], runs['canario']), (24, 8, 1, 1))
        self.assertEqual(writes['reacciones'], 6)

    def test_a_day_is_planned_the_same_after_a_restart_and_only_what_is_ahead_runs(self):
        seeded = lambda: random.Random(f'semilla:prueba:{WEDNESDAY}')  # noqa: E731
        whole, _ = plan(WEDNESDAY, Ritmo(), seeded())
        self.assertEqual(plan(WEDNESDAY, Ritmo(), seeded())[0], whole)
        self.assertNotEqual(plan(WEDNESDAY + timedelta(days=7), Ritmo(), random.Random('semilla:prueba:otro'))[0],
                            whole)
        noon = moment(WEDNESDAY, 12)
        later, _ = plan(WEDNESDAY, Ritmo(), seeded(), begin=noon)
        self.assertEqual(later, [e for e in whole if e[0] >= noon])
        fewer, _ = plan(WEDNESDAY, Ritmo(), seeded(), done={'reacciones': 4})
        self.assertEqual(sum(1 for _, n in fewer if n == 'reacciones'), 2)


class DayTests(SoakCase):
    def test_a_whole_day_reads_at_pace_writes_up_to_its_caps_and_keeps_no_names(self):
        soak = self.soak(moment(WEDNESDAY, 8))
        self.assertEqual(soak.run_day(WEDNESDAY), DONE)
        s = self.summary(WEDNESDAY)
        made = {k: s['escrituras'][k].get('hechas', 0) for k in rodaje.KINDS}
        self.assertEqual(made, {'reacciones': 6, 'seguimientos': 4, 'invitaciones': 2, 'aceptaciones': 5,
                                'comentarios': 0, 'respuestas': 0})
        self.assertEqual({k: s['escrituras'][k].get('confirmadas', 0) for k in made}, made)
        ops = [op for _, op in self.writes()]
        self.assertEqual({op: ops.count(op) for op in set(ops)},
                         {'add_reaction': 6, 'follow_user': 4, 'send_invitation': 2, 'accept_invitation': 5})
        self.assertTrue(250 <= s['lecturas'] <= 450, s['lecturas'])
        self.assertEqual(s['llamadas'], len(self.line.calls))
        self.assertEqual((s['codigo'], s['arranques'], s['paradas'], s['presupuesto']), (0, 1, [], 0))
        self.assertEqual(s['http'], {'200': len(self.line.calls)})
        self.assertEqual(s['canario']['resultado'], 'roto')  # the invented answers carry none of LinkedIn's fields
        self.assertEqual(s['plan']['escrituras']['reacciones'], 6)
        self.assertTrue(all(s['rutinas'][name]['corridas'] >= n for name, n in rodaje.ROUTINES.items()))
        start, end = moment(WEDNESDAY, 8), moment(WEDNESDAY, 20)
        self.assertTrue(all(start <= at <= end + 600 for at, _, _ in self.line.calls))
        writes = [at for at, _ in self.writes()]
        self.assertGreaterEqual(writes[0], start + rodaje.WARMUP * 60)
        self.assertTrue(all(b - a >= 3 * 60 for a, b in zip(writes, writes[1:])))
        kept = (self.data / 'cuentas' / 'prueba' / 'rodaje').glob('*.json')
        text = ''.join(p.read_text() for p in kept)
        for value in PEOPLE + INVITERS + list(self.world.posts) + list(self.world.received) + [OWN, '103644278']:
            self.assertNotIn(value, text)

    def test_nothing_is_done_twice_across_days(self):
        soak = self.soak(moment(WEDNESDAY, 7))
        self.assertEqual(soak.run(days=2), DONE)
        targets = [target for _, target in self.world.writes]
        self.assertEqual(len(targets), len(set(targets)))
        self.assertEqual(len([w for w in self.world.writes if w[0] == 'add_reaction']), 12)
        self.assertEqual(len([w for w in self.world.writes if w[0] == 'accept_invitation']), 6)  # all there were
        followed = {t for op, t in self.world.writes if op == 'follow_user'}
        invited = {t for op, t in self.world.writes if op == 'send_invitation'}
        self.assertFalse(followed & invited)
        self.assertTrue(all(self.world.people[p]['followers'] >= 5000 for p in invited))
        self.assertEqual(self.summary(WEDNESDAY + timedelta(days=1))['codigo'], DONE)
        again = self.soak(moment(WEDNESDAY + timedelta(days=2), 7))  # a new process: what was done is on disk
        again.run(days=1)
        targets = [target for _, target in self.world.writes]
        self.assertEqual(len(targets), len(set(targets)))

    def test_comments_need_the_operators_texts_and_each_goes_out_once(self):
        args = type('A', (), {'horario': '08:00-20:00', 'zona': 'America/Bogota', 'escala': '1', 'textos': '',
                              'lugar': 'United States', 'busquedas': 'founder', **{k: str(v) for k, v in
                                                                                   rodaje.WRITE_DEFAULTS.items()}})()
        args.comentarios = '2'
        with self.assertRaises(ajustes.ConfigError):
            rodaje.ritmo_from(args)
        texts = self.data / 'textos.txt'
        texts.write_text('Un texto propio, escrito a mano.\n\n')
        args.textos = str(texts)
        ritmo = rodaje.ritmo_from(args)
        self.assertEqual(ritmo.texts, ('Un texto propio, escrito a mano.',))
        self.soak(moment(WEDNESDAY, 8), ritmo=ritmo).run_day(WEDNESDAY)
        s = self.summary(WEDNESDAY)
        self.assertEqual(s['escrituras']['comentarios'], {'salieron': 1, 'hechas': 1, 'confirmadas': 1, 'sin_texto': 1})
        self.assertEqual([op for _, op in self.writes()].count('create_comment'), 1)
        self.assertNotIn('Un texto propio', ''.join(p.read_text() for p in (self.data / 'cuentas').rglob('*.json')))

    def test_a_restart_runs_the_rest_of_the_day_within_its_caps(self):
        self.soak(moment(WEDNESDAY, 8)).run_day(WEDNESDAY)
        before = len(self.world.writes)
        soak = self.soak(moment(WEDNESDAY, 15))  # the container came back: same day, same plan, caps already met
        self.assertEqual(soak.run_day(WEDNESDAY), DONE)
        s = self.summary(WEDNESDAY)
        self.assertEqual(s['arranques'], 2)
        self.assertEqual(len(self.world.writes), before)
        self.assertEqual(s['escrituras']['reacciones']['salieron'], 6)
        self.assertTrue(all(at >= moment(WEDNESDAY, 15) for at, _, _ in self.line.calls))


class StopTests(SoakCase):
    def test_linkedin_pushing_back_ends_the_day_with_3_and_nothing_more_goes_out(self):
        pushback = lambda request, n: Answer(429, '', 'text/html') if n == 40 else None  # noqa: E731
        soak = self.soak(moment(WEDNESDAY, 8), pushback)
        self.assertEqual(soak.run(), STOPPED)
        self.assertEqual(len(self.line.calls), 40)
        s = self.summary(WEDNESDAY)
        self.assertEqual(s['codigo'], STOPPED)
        self.assertEqual(s['http']['429'], 1)
        [stop] = s['paradas']
        self.assertEqual((stop['tipo'], stop['estado']), ('pushback', 429))
        # Started again the same day, it waits for the next one: not one call before 08:00 tomorrow.
        again = self.soak(moment(WEDNESDAY, 13))
        self.assertEqual(again.run(days=1), DONE)
        self.assertGreaterEqual(min(at for at, _, _ in self.line.calls), moment(WEDNESDAY + timedelta(days=1), 8))
        self.assertEqual(self.summary(WEDNESDAY)['codigo'], STOPPED)

    def test_a_stop_the_service_recorded_counts_before_any_call(self):
        Store(self.data / 'cuentas' / 'prueba').stop('LinkedIn: HTTP 999 en get_profile')
        self.assertEqual(self.soak(moment(WEDNESDAY, 8)).run_day(WEDNESDAY), STOPPED)
        self.assertEqual(self.line.calls, [])
        self.assertEqual(self.summary(WEDNESDAY)['paradas'][0]['tipo'], 'stopped')

    def test_the_service_without_a_session_or_with_the_account_stopped_is_a_stop_too(self):
        for day, kind, status in ((SATURDAY, 'login', 423), (SATURDAY + timedelta(days=1), 'stopped', 409)):
            with self.subTest(kind=kind):
                refuse = lambda request, n: LinkedInError('Servicio navegador: no.', kind=kind, status=status,  # noqa: E731
                                                          pause=True)
                self.assertEqual(self.soak(moment(day, 8), refuse).run_day(day), STOPPED)
                self.assertEqual(len(self.line.calls), 1)
                self.assertEqual(self.summary(day)['servicio'], {f'{status} {kind}': 1})

    def test_another_internet_exit_needs_someone_on_the_server(self):
        egress = lambda request, n: LinkedInError('Servicio navegador: otra salida.', kind='egress', status=503,  # noqa: E731
                                                  since='2026-11-11T13:00:00+00:00')
        self.assertEqual(self.soak(moment(WEDNESDAY, 8), egress).run(), CANNOT)
        s = self.summary(WEDNESDAY)
        self.assertEqual((s['codigo'], s['servicio'], s['paradas'][0]['tipo']), (CANNOT, {'503 egress': 1}, 'egress'))

    def test_a_spent_budget_ends_the_routine_not_the_day(self):
        budget = lambda request, n: LinkedInError('Servicio navegador: presupuesto.', kind='budget', status=422,  # noqa: E731
                                                  retry_after=600) if request.operation == 'get_profile' else None
        self.assertEqual(self.soak(moment(WEDNESDAY, 8), budget).run_day(WEDNESDAY), DONE)
        s = self.summary(WEDNESDAY)
        self.assertGreater(s['presupuesto'], 0)
        self.assertGreater(s['rutinas']['perfiles']['cortadas'], 0)
        self.assertEqual(s['escrituras']['seguimientos'].get('hechas', 0), 0)
        self.assertEqual(s['escrituras']['reacciones']['hechas'], 6)

    def test_a_write_refused_before_leaving_does_not_count_against_the_cap(self):
        refuse = lambda request, n: LinkedInError('Servicio navegador: presupuesto.', kind='budget', status=422,  # noqa: E731
                                                  retry_after=600) if request.write else None
        self.soak(moment(WEDNESDAY, 8), refuse).run_day(WEDNESDAY)
        reactions = self.summary(WEDNESDAY)['escrituras']['reacciones']
        self.assertEqual((reactions.get('salieron', 0), reactions['no_salieron']), (0, 6))

    def test_a_write_linkedin_did_not_answer_is_uncertain_and_counts(self):
        lost = lambda request, n: Answer(0) if request.operation == 'add_reaction' else None  # noqa: E731
        self.soak(moment(WEDNESDAY, 8), lost).run_day(WEDNESDAY)
        reactions = self.summary(WEDNESDAY)['escrituras']['reacciones']
        self.assertEqual((reactions['salieron'], reactions['inciertas'], reactions.get('hechas', 0)), (6, 6, 0))


class StatusTests(SoakCase):
    def test_the_last_days_in_one_table(self):
        lines = []
        rodaje.status(self.data, out=lines.append)
        self.assertEqual(lines, ['No hay ningún rodaje todavía.'])
        self.soak(moment(WEDNESDAY, 8)).run_day(WEDNESDAY)
        Store(self.data / 'cuentas' / 'prueba').stop('prueba')
        self.soak(moment(WEDNESDAY + timedelta(days=1), 8)).run_day(WEDNESDAY + timedelta(days=1))
        lines = []
        rodaje.status(self.data, out=lines.append)
        self.assertEqual(lines[0], 'prueba:')
        self.assertIn('2026-11-11  lab', lines[2])
        self.assertIn('6/4/2/5/0/0', lines[2])
        self.assertTrue(lines[2].rstrip().endswith('0'))
        self.assertRegex(lines[3], r'  08:\d\d stopped ')
        self.assertTrue(lines[3].rstrip().endswith('3'))

    def test_the_command_needs_the_token_but_not_for_its_status(self):
        env = {'NAVEGADOR_DATOS': str(self.data), 'NAVEGADOR_TOKEN': '', 'RODAJE_CUENTA': ''}
        with patch.dict(os.environ, env), redirect_stdout(io.StringIO()) as out:
            self.assertEqual(cli.main(['rodaje', 'estado']), 0)
        self.assertIn('No hay ningún rodaje', out.getvalue())
        with patch.dict(os.environ, env):
            for argv, says in ((['rodaje', 'prueba'], 'NAVEGADOR_TOKEN'), (['rodaje', 'estado', 'NO VALE'], 'inválido')):
                with self.subTest(argv=argv), self.assertRaises(SystemExit) as e:
                    cli.main(argv)
                self.assertIn(says, str(e.exception))
        with patch.dict(os.environ, {**env, 'NAVEGADOR_TOKEN': TOKEN}):
            cases = ((['rodaje'], 'Falta la cuenta'), (['rodaje', 'otra'], 'no tiene perfil'),
                     (['rodaje', 'prueba', '--comentarios', '1'], '--textos'),
                     (['rodaje', 'prueba', '--escala', '5'], 'escala'),
                     (['rodaje', 'prueba', '--horario', '20:00-08:00'], 'Horario'))
            for argv, says in cases:
                with self.subTest(argv=argv), self.assertRaises(SystemExit) as e:
                    cli.main(argv)
                self.assertIn(says, str(e.exception))


class ThroughTheServiceTests(unittest.IsolatedAsyncioTestCase):
    """The soak with the real client and the backend's own transport, against the real service on the fake browser."""

    async def start(self, browser, **changes):
        self.world = World(browser, **changes)
        self.addCleanup(self.world.tmp.cleanup)
        client = TestClient(TestServer(build(self.world.settings, **self.world.deps())))
        await client.start_server()
        self.addAsyncCleanup(client.close)
        clock = Clock(moment(WEDNESDAY, 8))
        transport = ServiceTransport(str(client.make_url('')), TOKEN, 'prueba')
        self.addCleanup(transport.http.close)
        return Rodaje('prueba', self.world.data, transport, clock=clock, sleep=clock.sleep, rand=random.Random(7))

    def summary(self):
        return json.loads((self.world.data / 'cuentas' / 'prueba' / 'rodaje' / f'rodaje-{WEDNESDAY}.json').read_text())

    async def test_linkedin_pushing_back_stops_the_soak_and_the_account(self):
        soak = await self.start(Browser(answers=[raw(status=429, text='')]))
        self.assertEqual(await asyncio.to_thread(soak.run_day, WEDNESDAY), STOPPED)
        self.assertEqual(len(self.world.browser.fetches), 1)
        self.assertTrue(Store(self.world.settings.account_dir('prueba')).stopped())
        s = self.summary()
        self.assertEqual((s['http'], s['paradas'][0]['tipo'], s['paradas'][0]['estado']), ({'429': 1}, 'pushback', 429))

    async def test_the_services_budgets_hold_for_the_soak_too(self):
        budgets = {**ajustes.BUDGETS, ('read', 'day'): 0}
        soak = await self.start(Browser(), budgets=budgets)
        self.assertEqual(await asyncio.to_thread(soak.run_day, WEDNESDAY), DONE)
        self.assertEqual(self.world.browser.fetches, [])
        s = self.summary()
        self.assertEqual((s['lecturas'], s['http']), (0, {}))
        self.assertEqual(s['presupuesto'], sum(s['servicio'].values()))
        self.assertEqual(s['canario']['resultado'], 'no_corrio')


if __name__ == '__main__':
    unittest.main()
