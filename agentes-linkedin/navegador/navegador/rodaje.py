"""The soak run of phase 4 (docs/plan-linkedin-directo.md, «Fase 4»): ONE test account doing a production day, day
after day, through the running service and nothing else: no backend, no database, no proposals, no AI.

    python -m navegador rodaje <cuenta>          runs until stopped (`--dias N` for N days)
    python -m navegador rodaje estado [<cuenta>] the last days in one table

A day (README «Rodaje»):
- reads at production's pace per hour inside the working hours (08:00-20:00 America/Bogota by default), with the mix of
  the production jobs (README «Topes frente al ritmo real»): own profile, audience and views, own posts and their
  comments, other people's post lists, comments of posts, profiles with their top card, people search with a place
  filter and the location typeahead, invitations, chats, one analytics export and the daily canary;
- a few harmless writes, each read before and after as production does: LIKE on large public posts, following their
  authors, invitations WITHOUT a note to creators out of the network, and accepting invitations from people (the
  received list already leaves newsletters and pages out). Comments and replies only with an explicit number and the
  operator's own texts, each used once (default 0: a test account commenting on strangers' posts is spam to them).
  Never an unfollow, a withdrawal, a deletion or a message: Cliente has no such call and the allowlist refuses them;
- spread with jitter around one long idle gap; weekends at half pace;
- never the same post or person twice (hecho.json: salted hashes and a date, no id or name);
- every guard of the service, as for the backend: its pauses, budgets, allowlist and request_id. A stop (the service
  has the account stopped or without a session, or LinkedIn pushed back) ends the day and the command with 3; another
  internet exit or a refused configuration, with 4. Started again that same day, it waits for the next one.

Every day leaves cuentas/<cuenta>/rodaje/rodaje-AAAA-MM-DD.json: counts per routine and operation, LinkedIn's statuses,
the service's refusals, budget refusals, stops, the canary and durations. Never a name, an id or a text.

A day is planned from a seed of the account and the date, so a restart (a new container) plans the same day again and
runs only what is still ahead; the writes already made that day count against its caps."""
import hashlib
import logging
import os
import random
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, time as day_time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from linkedin_directo import Cliente, LinkedInError, Uncertain, canario
from linkedin_directo.transporte import Transport

from .ajustes import ConfigError
from .almacen import Store, read_json, write_json

log = logging.getLogger('navegador.rodaje')
DONE, STOPPED, CANNOT = 0, 3, 4
WEEKEND = 0.5
# Runs on a weekday at scale 1: production's pace per hour (README «Topes frente al ritmo real»), in working hours only.
ROUTINES = {
    'descubrir': 2,   # /me, the location typeahead (3 calls, once a day) and 2 people searches with it (red.discover)
    'referentes': 4,  # the post lists of the day's 15 people (operador.observe, every 3 h)
    'perfiles': 8,    # 5 profiles of the pool with their top card (red._enrich)
    'borradores': 6,  # /me and the comments of a post (operador.propose_comment)
    'bandeja': 12,    # /me, the chats and the messages of unread ones (conversaciones.read_inbox, hourly)
    'propios': 6,     # /me, own posts and the comments and threads of this week's (respuestas.read)
    'metricas': 4,    # own posts, the newest one and its comments, audience and views (metricas.collect)
    'red': 3,         # received and sent invitations; accepting the received ones (red.sync, RED-04)
    'analitica': 1,   # one export, the last 28 days (analitica.run makes five)
    'canario': 1,     # the daily canary: 14 reads, 16 calls
}
DAILY = ('analitica', 'canario')  # weekends too
FIRST = {'descubrir': (2, 10), 'referentes': (12, 25)}  # minutes into the day: the pool exists before any write
WRITES = ('reacciones', 'seguimientos', 'invitaciones', 'comentarios', 'respuestas')  # placed in the day
KINDS = WRITES + ('aceptaciones',)  # accepting goes with `red`, when someone invited the account
WRITE_DEFAULTS = {'reacciones': 6, 'seguimientos': 4, 'invitaciones': 2, 'aceptaciones': 5, 'comentarios': 0,
                  'respuestas': 0}
WRITE_MAX = 30  # the service's own daily budget of each kind of write
SCALE_MAX = 3  # about production's busiest day of reads (~880), under the service's 1000 a day
WARMUP = 45  # minutes into the day before the first write
ROUND = (3, 8)  # minutes between two accepts of one network round (production's spacing in a round)
REFERENTS, PROFILES, PICK_TRIES = 15, 5, 3
JITTER = 0.35  # of the space between two runs of a routine
CANNOT_KINDS = ('config', 'disabled', 'egress')  # only someone on the server fixes these
HALT_KINDS = ('stopped', 'login')
CUT_KINDS = ('budget', 'not_sent', 'network')  # nothing left or nothing came back: the routine ends, the day goes on
OUT_OF_NETWORK = ('OUT_OF_NETWORK', 'THIRD_DEGREE')
WEEK = timedelta(days=7)


class Stop(Exception):
    """The day ends here: `code` STOPPED (the account is stopped or LinkedIn pushed back) or CANNOT (someone has to fix
    the service's configuration or accept the internet exit)."""

    def __init__(self, code, kind, status, reason):
        super().__init__(reason)
        self.code, self.kind, self.status, self.reason = code, kind, status, reason


class Cut(Exception):
    """This routine ends here (a budget refusal, the call not sent, no answer); the day goes on."""


@dataclass(frozen=True)
class Ritmo:
    hours: tuple = (day_time(8), day_time(20))
    zone: str = 'America/Bogota'
    scale: float = 1.0
    writes: dict = field(default_factory=lambda: dict(WRITE_DEFAULTS))
    gap: tuple = (60, 120)  # minutes of the long idle gap, somewhere around midday
    spacing: float = 20.0  # minutes between two writes, at least
    place: str = 'United States'
    searches: tuple = ('founder', 'product manager', 'cto', 'software engineer')
    texts: tuple = ()  # the operator's own comment texts: each goes out once, never generated
    min_reactions: int = 50  # a «large public post», to react to or to follow its author
    min_followers: int = 5000  # a creator, to invite

    def window(self, day):
        """The day's working hours as two epoch seconds."""
        zone = ZoneInfo(self.zone)
        return tuple(datetime.combine(day, hour, tzinfo=zone).timestamp() for hour in self.hours)


# --- the day's plan ---------------------------------------------------------------------------------------------------
def counts(ritmo, weekend):
    """Runs of each routine and writes of each kind in a whole day."""
    factor = WEEKEND if weekend else 1.0
    runs = {name: n if name in DAILY else max(1, int(n * ritmo.scale * factor)) for name, n in ROUTINES.items()}
    return runs, {kind: int(ritmo.writes.get(kind, 0) * factor) for kind in KINDS}


def plan(day, ritmo, rand, begin=None, done=None):
    """The day's events in order, [(epoch, routine or kind of write)], and what was planned. The routines' runs are
    spread evenly over the active time (the working hours without the long gap), each with some jitter; the writes go at
    random, WARMUP minutes in and `spacing` apart. `begin` (a restart) drops what is already behind; `done` (writes
    already made today, per kind) comes off the day's writes."""
    start, end = ritmo.window(day)
    weekend = day.weekday() >= 5
    runs, writes = counts(ritmo, weekend)
    length = end - start
    gap = rand.uniform(*ritmo.gap) * 60
    gap_at = rand.uniform(start + 0.3 * length, max(start + 0.3 * length, end - 0.3 * length - gap))
    first = gap_at - start
    total = length - gap

    def at(x):  # a moment of active time -> the clock, skipping the gap
        x = min(max(x, 0.0), total - 1)
        return start + x if x < first else gap_at + gap + (x - first)

    events = []
    for name, n in runs.items():
        space = total / n
        for i in range(n):
            if i == 0 and name in FIRST:
                x = rand.uniform(*FIRST[name]) * 60
            else:
                x = (i + 0.5 + rand.uniform(-JITTER, JITTER)) * space
            events.append((at(x), name))
    taken = []
    for kind in WRITES:
        for _ in range(writes[kind]):
            for _ in range(200):
                moment = at(rand.uniform(WARMUP * 60, total))
                if all(abs(moment - other) >= ritmo.spacing * 60 for other in taken):
                    taken.append(moment)
                    events.append((moment, kind))
                    break
    begin = start if begin is None else begin
    left = {kind: max(0, writes[kind] - (done or {}).get(kind, 0)) for kind in KINDS}
    out = []
    for moment, name in sorted(events):
        if moment < begin:
            continue
        if name in WRITES:
            if not left[name]:
                continue
            left[name] -= 1
        out.append((moment, name))
    zone = ZoneInfo(ritmo.zone)
    hhmm = lambda t: datetime.fromtimestamp(t, zone).strftime('%H:%M')  # noqa: E731
    return out, {'rutinas': runs, 'escrituras': writes, 'pausa_larga': f'{hhmm(gap_at)}-{hhmm(gap_at + gap)}',
                 'fin_de_semana': weekend}


# --- what was done, never twice ---------------------------------------------------------------------------------------
class Done:
    """Posts, people, comments and texts the soak already acted on: a salted hash and the day, never the id or a name.
    The salt stays in the same file (it only keeps the hashes from matching ids elsewhere) and seeds the days' plans."""

    def __init__(self, folder):
        self.path = Path(folder) / 'hecho.json'
        data = read_json(self.path)
        data = data if isinstance(data, dict) else {}
        self.salt = data.get('sal') if isinstance(data.get('sal'), str) and data['sal'] else secrets.token_hex(16)
        self.seen = data.get('hecho') if isinstance(data.get('hecho'), dict) else {}
        if data.get('sal') != self.salt:
            self.save()

    def key(self, kind, value):
        return hashlib.sha256(f'{self.salt}:{kind}:{value}'.encode()).hexdigest()[:24]

    def has(self, kind, value):
        return self.key(kind, value) in self.seen

    def add(self, kind, value, day):
        self.seen[self.key(kind, value)] = day.isoformat()
        self.save()

    def save(self):
        write_json(self.path, {'sal': self.salt, 'hecho': self.seen})


# --- the day's summary ------------------------------------------------------------------------------------------------
def blank(account, day, ritmo):
    return {'fecha': day.isoformat(), 'cuenta': account, 'zona': ritmo.zone,
            'horario': '-'.join(h.strftime('%H:%M') for h in ritmo.hours), 'fin_de_semana': day.weekday() >= 5,
            'pausa_larga': '', 'plan': {}, 'rutinas': {}, 'operaciones': {},
            'escrituras': {kind: {} for kind in KINDS}, 'http': {}, 'servicio': {}, 'presupuesto': 0, 'errores': {},
            'paradas': [], 'canario': None, 'lecturas': 0, 'llamadas': 0, 'segundos': 0.0, 'inicio': '', 'fin': '',
            'arranques': 0, 'perdidas': 0, 'codigo': None}


def bump(table, key, n=1):
    table[key] = table.get(key, 0) + n
    return table


class Recorder(Transport):
    """Counts every call into the day's summary, by operation, with LinkedIn's status or the service's refusal and how
    long it took. Nothing of what LinkedIn answered is kept. `answered` counts the writes LinkedIn answered: a write
    that failed before it grew did not leave."""

    def __init__(self, transport, summary, clock):
        self.transport, self.summary, self.clock, self.answered = transport, summary, clock, 0

    def send(self, request):
        started, name = self.clock(), request.operation or request.kind
        row = self.summary['operaciones'].setdefault(name, {'llamadas': 0, 'rechazadas': 0, 'segundos': 0.0})
        try:
            answer = self.transport.send(request)
        except LinkedInError as exc:  # the service's own refusal: nothing reached LinkedIn
            bump(row, 'rechazadas')
            bump(self.summary['servicio'], f'{exc.status or "-"} {exc.kind}')
            if exc.kind == 'budget':
                self.summary['presupuesto'] += 1
            raise
        except Uncertain:
            bump(self.summary['servicio'], 'incierta')
            raise
        finally:
            took = self.clock() - started
            row['segundos'] = round(row['segundos'] + took, 1)
            self.summary['segundos'] = round(self.summary['segundos'] + took, 1)
        bump(row, 'llamadas')
        self.summary['llamadas'] += 1
        if request.write:
            self.answered += 1
        else:
            self.summary['lecturas'] += 1
        bump(self.summary['http'], 'redireccion' if answer.redirected else str(answer.status))
        return answer

    def live_query(self, prefixes, variables):
        return self.transport.live_query(prefixes, variables)


# --- the runner -------------------------------------------------------------------------------------------------------
class Rodaje:
    def __init__(self, account, data, transport, ritmo=None, client=Cliente, clock=time.time, sleep=time.sleep,
                 rand=None, seed=''):
        self.account, self.transport, self.ritmo = account, transport, ritmo or Ritmo()
        self.store = Store(Path(data) / 'cuentas' / account)
        self.folder = self.store.root / 'rodaje'
        self.client, self.clock, self.sleep = client, clock, sleep
        self.rand = rand or random.Random()
        self.zone = ZoneInfo(self.ritmo.zone)
        self.done = Done(self.folder)
        self.seed = seed or self.done.salt  # the plan of a day is the same after a restart
        self.people, self.posts, self.referents = {}, {}, []  # the pool, in memory: rebuilt by reading
        self.geo, self.own, self.last_write, self.summary, self.day = None, '', 0.0, None, None

    # --- days ---------------------------------------------------------------------------------------------------------
    def today(self):
        return datetime.fromtimestamp(self.clock(), self.zone).date()

    def path(self, day):
        return self.folder / f'rodaje-{day.isoformat()}.json'

    def run(self, days=0):
        """Day after day; returns at a stop (3 or 4), or 0 after `days` days when given."""
        ran = 0
        while True:
            day = self.today()
            start, end = self.ritmo.window(day)
            kept = read_json(self.path(day))
            if self.clock() >= end or (isinstance(kept, dict) and kept.get('codigo') in (STOPPED, CANNOT)):
                self.wait_until(self.ritmo.window(day + timedelta(days=1))[0])
                continue
            self.wait_until(start)
            code = self.run_day(day)
            ran += 1
            if code or (days and ran >= days):
                return code
            self.wait_until(self.ritmo.window(day + timedelta(days=1))[0])

    def wait_until(self, moment):
        while self.clock() < moment:
            self.sleep(moment - self.clock())

    def run_day(self, day):
        kept = read_json(self.path(day))
        self.summary = kept if isinstance(kept, dict) and kept.get('fecha') == day.isoformat() else \
            blank(self.account, day, self.ritmo)
        self.day, self.geo, self.referents = day, None, []  # the day's people are picked again with what is known
        self.summary['arranques'] += 1
        self.summary['codigo'] = None  # running again
        done = {kind: self.summary['escrituras'].get(kind, {}).get('salieron', 0) for kind in KINDS}
        events, info = plan(day, self.ritmo, random.Random(f'{self.seed}:{self.account}:{day}'), self.clock(), done)
        if not self.summary['plan']:
            self.summary['plan'] = {'rutinas': info['rutinas'], 'escrituras': info['escrituras']}
            self.summary['pausa_larga'] = info['pausa_larga']
            self.summary['inicio'] = self.hhmm()
        log.info('rodaje %s: %s, %d tareas por delante (pausa larga %s)', self.account, day, len(events),
                 info['pausa_larga'])
        end = self.ritmo.window(day)[1]
        try:
            for index, (moment, what) in enumerate(events):
                if what in WRITES:  # a network round may have just accepted someone
                    moment = max(moment, self.last_write + self.ritmo.spacing * 60)
                self.wait_until(moment)
                if self.clock() >= end:
                    self.summary['perdidas'] += len(events) - index
                    break
                self.step(what)
                self.save()
        except Stop as exc:
            self.summary['paradas'].append({'hora': self.hhmm(), 'tipo': exc.kind, 'estado': exc.status,
                                            'motivo': exc.reason[:300]})
            self.summary['codigo'] = exc.code
            self.summary['fin'] = self.hhmm()
            self.save()
            log.warning('rodaje %s: PARADA (%s): %s', self.account, exc.kind, exc.reason[:300])
            return exc.code
        self.summary['codigo'] = DONE
        self.summary['fin'] = self.hhmm()
        self.save()
        return DONE

    def save(self):
        write_json(self.path(self.day), self.summary)

    def hhmm(self):
        return datetime.fromtimestamp(self.clock(), self.zone).strftime('%H:%M')

    # --- one step: a routine or a write -------------------------------------------------------------------------------
    def step(self, what):
        if self.store.stopped():  # read from disk: a stop the service recorded counts before any call
            raise Stop(STOPPED, 'stopped', None, 'la cuenta está detenida en el servicio (python -m navegador estado)')
        started, row = self.clock(), self.summary['rutinas'].setdefault(what, {'corridas': 0, 'cortadas': 0,
                                                                                'segundos': 0.0})
        client = self.client(Recorder(self.transport, self.summary, self.clock))
        try:
            getattr(self, ('w_' if what in KINDS else 'r_') + what)(client)
        except Cut:
            bump(row, 'cortadas')
        finally:
            bump(row, 'corridas')
            row['segundos'] = round(row['segundos'] + self.clock() - started, 1)
        log.info('rodaje %s: %s (%.0f s)', self.account, what, self.clock() - started)

    def call(self, function, *args):
        """One operation: its answer, or None when it failed on its own (the error is counted). A stop or a refusal
        that ends the routine raises."""
        try:
            return function(*args)
        except LinkedInError as exc:
            self.judge(exc)
        except Uncertain:
            bump(self.summary['errores'], 'incierta')
        except Exception as exc:  # an answer this code cannot read: counted, and this routine ends
            bump(self.summary['errores'], f'interno:{type(exc).__name__}')
            raise Cut() from None
        return None

    def judge(self, exc):
        if exc.kind in CANNOT_KINDS:
            raise Stop(CANNOT, exc.kind, exc.status, str(exc)) from None
        if exc.pause or exc.kind in HALT_KINDS:
            raise Stop(STOPPED, exc.kind, exc.status, str(exc)) from None
        bump(self.summary['errores'], exc.kind)
        if exc.kind in CUT_KINDS:
            raise Cut() from None

    def write(self, kind, client, function, *args):
        """One write: True when LinkedIn took it. What left (LinkedIn answered it, or its fate is unknown) counts
        against the day's cap as `salieron`; a write refused before leaving is `no_salieron`."""
        row, before = self.summary['escrituras'][kind], client.t.answered
        self.last_write = self.clock()
        try:
            function(*args)
        except Uncertain:
            bump(row, 'salieron')
            bump(row, 'inciertas')
            return False
        except LinkedInError as exc:
            left = client.t.answered > before
            bump(row, 'salieron' if left else 'no_salieron')
            if left:
                bump(row, 'rechazadas')
            self.judge(exc)
            return False
        bump(row, 'salieron')
        bump(row, 'hechas')
        return True

    def note(self, kind, what):
        bump(self.summary['escrituras'][kind], what)

    def left(self, kind):
        cap = counts(self.ritmo, self.day.weekday() >= 5)[1][kind]
        return cap - self.summary['escrituras'][kind].get('salieron', 0)

    def spaced(self):
        return self.clock() - self.last_write >= self.ritmo.spacing * 60

    # --- the pool -----------------------------------------------------------------------------------------------------
    def me(self, client):
        self.call(client.account_status)
        self.own = (client.me or {}).get('fsd') or self.own

    def keep_person(self, user):
        if user.get('id') and user['id'] != self.own and user.get('type', 'individual') in ('individual', ''):
            self.people.setdefault(user['id'], {})

    def keep_post(self, post):
        author = post.get('author') or {}
        if post.get('is_repost') or not author.get('id') or author['id'] == self.own:
            return
        self.posts[post['id']] = {'author': author['id'], 'kind': author.get('type') or '',
                                  'reactions': post.get('reactions_counter') or 0,
                                  'reacted': bool(post.get('user_reacted'))}
        self.keep_person(author)

    def keep_profile(self, person, profile):
        self.people.setdefault(person, {}).update(
            distance=profile.get('network_distance') or '', following=bool(profile.get('is_following')),
            pending=profile.get('relation_request_status') == 'PENDING',
            followers=(profile.get('signals') or {}).get('followers'))

    def creators_first(self, people):
        """People in random order, the known creators (followers read on their profile) ahead of the rest."""
        people = sorted(people)
        self.rand.shuffle(people)
        return sorted(people, key=lambda p: (self.people.get(p) or {}).get('followers') is None
                      or self.people[p]['followers'] < self.ritmo.min_followers)

    def need_pool(self):
        if not self.people:
            self.step('descubrir')
        if not self.posts:
            self.step('referentes')

    # --- the routines (reads) -----------------------------------------------------------------------------------------
    def r_descubrir(self, client):
        self.me(client)
        if self.geo is None:  # the location typeahead, once a day
            places = self.call(client.search_parameters, 'LOCATION', self.ritmo.place, 3) or []
            self.geo = places[0]['id'] if places else ''
        for words in self.rand.sample(list(self.ritmo.searches), min(2, len(self.ritmo.searches))):
            for user in self.call(client.search_people, words, [self.geo] if self.geo else None) or []:
                self.keep_person(user)

    def r_referentes(self, client):
        if not self.people:
            self.step('descubrir')
        if len(self.referents) < REFERENTS:  # the same people all day, like production's referents
            others = [p for p in self.people if p not in self.referents]
            self.referents += self.creators_first(others)[:REFERENTS - len(self.referents)]
        for person in self.referents:
            for post in self.call(client.list_user_posts, person, 5) or []:
                self.keep_post(post)

    def r_perfiles(self, client):
        unread = sorted(p for p, info in self.people.items() if 'distance' not in info)
        for person in self.rand.sample(unread, min(PROFILES, len(unread))):
            profile = self.call(client.get_profile, person)
            if profile:
                self.keep_profile(person, profile)

    def r_borradores(self, client):
        self.need_pool()
        self.me(client)
        if self.posts:
            self.call(client.list_comments, self.rand.choice(sorted(self.posts)), 50)

    def r_bandeja(self, client):
        self.me(client)
        chats = self.call(client.list_chats, 20) or []
        for chat in [c for c in chats if c.get('unread_count')][:2]:
            self.call(client.list_chat_messages, chat['id'], 10)

    def r_propios(self, client):
        self.me(client)
        recent = datetime.fromtimestamp(self.clock(), timezone.utc) - WEEK
        for post in [p for p in self.call(client.list_user_posts, 'me', 5) or []
                     if p.get('created_at') and p['created_at'] >= recent][:2]:
            comments = self.call(client.list_comments, post['id'], 50) or []
            for comment in [c for c in comments if c.get('reply_counter')][:2]:
                self.call(client.list_comment_thread, post['id'], comment['id'], 50)

    def r_metricas(self, client):
        posts = self.call(client.list_user_posts, 'me', 10) or []
        self.own = (client.me or {}).get('fsd') or self.own
        if posts:
            self.call(client.get_post, posts[0]['id'])
            self.call(client.list_comments, posts[0]['id'], 50)
        self.call(client.own_audience)
        self.call(client.profile_views, 90)

    def r_red(self, client):
        """The network round: both invitation lists, then the received ones accepted up to the day's cap, ROUND minutes
        apart like production's rounds (the first one only `spacing` after the last write)."""
        self.me(client)
        received = self.call(client.list_invitations, 'received', 100) or []
        self.call(client.list_invitations, 'sent', 100)
        accepted = 0
        for invitation in received:  # people only: lectura.invitations leaves newsletters and pages out
            person = (invitation.get('user') or {}).get('id')
            if self.left('aceptaciones') <= 0 or not (accepted or self.spaced()):
                break
            if not person or self.done.has('persona', person) or self.done.has('invitacion', invitation['id']):
                continue
            if accepted:
                self.sleep(self.rand.uniform(*ROUND) * 60)
            accepted += 1
            self.done.add('invitacion', invitation['id'], self.day)
            self.done.add('persona', person, self.day)
            if self.write('aceptaciones', client, client.accept_invitation, invitation['id']):
                after = self.call(client.get_profile, person)
                if after and after.get('network_distance') == 'FIRST_DEGREE':
                    self.note('aceptaciones', 'confirmadas')

    def r_analitica(self, client):
        last = datetime.fromtimestamp(self.clock(), timezone.utc).date() - timedelta(days=1)
        self.call(client.analytics, last - timedelta(days=27), last)

    def r_canario(self, client):
        report = canario.run(client.t)
        error = report.get('error') or {}
        self.summary['canario'] = {'resultado': report['resultado'], 'llamadas': report['llamadas'],
                                   'fallan': [r['operacion'] for r in report['operaciones'] if r['estado'] != canario.OK],
                                   'error': error.get('kind') or ''}
        if error.get('kind') in CANNOT_KINDS:
            raise Stop(CANNOT, error['kind'], None, error.get('motivo') or '')
        if report['resultado'] == canario.HALTED:
            raise Stop(STOPPED, error.get('kind') or 'stopped', None, error.get('motivo') or '')

    # --- the writes ---------------------------------------------------------------------------------------------------
    def large_posts(self):
        return [p for p, info in sorted(self.posts.items()) if info['reactions'] >= self.ritmo.min_reactions
                and info['kind'] in ('individual', '') and not self.done.has('publicacion', p)]

    def w_reacciones(self, client):
        self.need_pool()
        candidates = [p for p in self.large_posts() if not self.posts[p]['reacted']]
        if not candidates:
            return self.note('reacciones', 'sin_candidato')
        post = self.rand.choice(candidates)
        self.me(client)
        before = self.call(client.get_post, post)
        if before is None:
            return None
        self.done.add('publicacion', post, self.day)
        if before.get('user_reacted'):
            self.posts[post]['reacted'] = True
            return self.note('reacciones', 'ya_hecha')
        if self.write('reacciones', client, client.add_reaction, post, 'linkedin_like'):
            self.posts[post]['reacted'] = True
            after = self.call(client.get_post, post)
            if after and after.get('user_reacted'):
                self.note('reacciones', 'confirmadas')
        return None

    def person(self, kind, client, candidates, fits, send, confirmed):
        """Follow or invite: up to PICK_TRIES people, in the given order, read before and judged by `fits`; the first
        that fits gets the write and is read again. A person read but not fit is left alone, and nobody is picked
        twice either way."""
        candidates = [p for p in candidates if not self.done.has('persona', p)][:PICK_TRIES]
        if not candidates:
            return self.note(kind, 'sin_candidato')
        self.me(client)
        for person in candidates:
            before = self.call(client.get_profile, person)
            if before is None:
                continue
            self.keep_profile(person, before)
            self.done.add('persona', person, self.day)
            if not fits(before):
                self.note(kind, 'no_encaja')
                continue
            if self.write(kind, client, send, person):
                after = self.call(client.get_profile, person)
                if after and confirmed(after):
                    self.note(kind, 'confirmadas')
            return None
        return None

    def w_seguimientos(self, client):
        """The author of a large public post, never someone already followed or connected."""
        self.need_pool()
        authors = self.creators_first({self.posts[p]['author'] for p in self.large_posts()})
        return self.person('seguimientos', client, authors,
                           lambda p: p.get('network_distance') not in ('SELF', 'FIRST_DEGREE') and not p.get('is_following'),
                           client.follow_user, lambda p: p.get('is_following'))

    def w_invitaciones(self, client):
        """A creator out of the account's network, without a note and without an invitation already pending."""
        self.need_pool()
        known = [p for p, info in self.people.items() if info.get('distance', OUT_OF_NETWORK[0]) in OUT_OF_NETWORK
                 and (info.get('followers') is None or info['followers'] >= self.ritmo.min_followers)
                 and not info.get('pending')]
        return self.person('invitaciones', client, self.creators_first(known),
                           lambda p: p.get('network_distance') in OUT_OF_NETWORK and not p.get('relation_request_status')
                           and ((p.get('signals') or {}).get('followers') or 0) >= self.ritmo.min_followers,
                           client.send_invitation, lambda p: p.get('relation_request_status') == 'PENDING')

    def text(self, kind):
        found = next((t for t in self.ritmo.texts if not self.done.has('texto', t)), None)
        if found is None:
            self.note(kind, 'sin_texto')
        return found

    def w_comentarios(self, client):
        text = self.text('comentarios')
        if text is None:
            return None
        self.need_pool()
        candidates = self.large_posts()
        if not candidates:
            return self.note('comentarios', 'sin_candidato')
        post = self.rand.choice(candidates)
        self.me(client)
        before = self.call(client.list_comments, post, 50)
        if before is None:
            return None
        self.done.add('publicacion', post, self.day)
        if any(c.get('is_sender') for c in before):
            return self.note('comentarios', 'ya_hecha')
        self.done.add('texto', text, self.day)
        if self.write('comentarios', client, client.create_comment, post, text):
            after = self.call(client.list_comments, post, 50) or []
            if any(c.get('is_sender') and c.get('text') == text for c in after):
                self.note('comentarios', 'confirmadas')
        return None

    def w_respuestas(self, client):
        """A reply in a thread of the account's OWN posts (INT-04), never on someone else's post."""
        text = self.text('respuestas')
        if text is None:
            return None
        self.me(client)
        for post in self.call(client.list_user_posts, 'me', 5) or []:
            for comment in self.call(client.list_comments, post['id'], 50) or []:
                key = f'{post["id"]}:{comment["id"]}'
                if comment.get('is_sender') or self.done.has('comentario', key):
                    continue
                thread = self.call(client.list_comment_thread, post['id'], comment['id'], 50)
                if thread is None:
                    return None
                self.done.add('comentario', key, self.day)
                if any(c.get('is_sender') for c in thread):
                    self.note('respuestas', 'ya_hecha')
                    continue
                self.done.add('texto', text, self.day)
                if self.write('respuestas', client, client.comment_in_thread, post['id'], comment['id'], text):
                    after = self.call(client.list_comment_thread, post['id'], comment['id'], 50) or []
                    if any(c.get('is_sender') and c.get('text') == text for c in after):
                        self.note('respuestas', 'confirmadas')
                return None
        return self.note('respuestas', 'sin_candidato')


# --- status -----------------------------------------------------------------------------------------------------------
WRITE_COLUMNS = ('reacciones', 'seguimientos', 'invitaciones', 'aceptaciones', 'comentarios', 'respuestas')


def status(data, account=None, days=14, out=print):
    """The last `days` summaries of each account (or of one) in one table."""
    folder = Path(data) / 'cuentas'
    names = [account] if account else sorted(p.name for p in folder.iterdir() if (p / 'rodaje').is_dir()) \
        if folder.is_dir() else []
    if not names:
        out('No hay ningún rodaje todavía.')
    for name in names:
        files = sorted((folder / name / 'rodaje').glob('rodaje-*.json'))[-days:]
        out(f'{name}:' if files else f'{name}: sin días de rodaje')
        if files:
            out(f'{"fecha":10}  {"día":3}  {"lecturas":>8}  {"hechas r/s/i/a/c/re":>19}  {"no 200":>6}  '
                f'{"topes":>5}  {"servicio":>8}  {"canario":9}  {"parada":28}  código')
        for path in files:
            s = read_json(path) or {}
            writes = '/'.join(str((s.get('escrituras') or {}).get(k, {}).get('hechas', 0)) for k in WRITE_COLUMNS)
            other = sum(n for code, n in (s.get('http') or {}).items() if code != '200')
            refused = sum((s.get('servicio') or {}).values())
            stop = (s.get('paradas') or [{}])[-1]
            stop = f'{stop.get("hora", "")} {stop.get("tipo", "")} {stop.get("estado") or ""}'.strip() \
                if s.get('paradas') else '—'
            canary = (s.get('canario') or {}).get('resultado') or '—'
            code = s.get('codigo')
            out(f'{s.get("fecha", path.stem[7:]):10}  {"fds" if s.get("fin_de_semana") else "lab":3}  '
                f'{s.get("lecturas", 0):>8}  {writes:>19}  {other:>6}  {s.get("presupuesto", 0):>5}  {refused:>8}  '
                f'{canary:9}  {stop[:28]:28}  {"en curso" if code is None else code}')
    return 0


# --- the command ------------------------------------------------------------------------------------------------------
def options(parser):
    env = os.environ.get
    parser.add_argument('cuenta', nargs='?', default=env('RODAJE_CUENTA') or None,
                        help='la cuenta (por defecto RODAJE_CUENTA); «estado» muestra los últimos días')
    parser.add_argument('otra', nargs='?', help='con «estado»: solo esa cuenta')
    parser.add_argument('--dias', type=int, default=0, help='con «estado», cuántos días (14); si no, parar tras N días')
    parser.add_argument('--url', help='dirección del servicio (por defecto NAVEGADOR_URL o 127.0.0.1:NAVEGADOR_PUERTO)')
    parser.add_argument('--horario', default=env('RODAJE_HORARIO') or '08:00-20:00')
    parser.add_argument('--zona', default=env('RODAJE_ZONA') or 'America/Bogota')
    parser.add_argument('--escala', default=env('RODAJE_ESCALA') or '1', help='multiplica las lecturas del día')
    for kind, default in WRITE_DEFAULTS.items():
        parser.add_argument(f'--{kind}', default=env(f'RODAJE_{kind.upper()}') or str(default))
    parser.add_argument('--textos', default=env('RODAJE_TEXTOS') or '',
                        help='archivo con los textos propios de comentarios y respuestas, uno por línea')
    parser.add_argument('--lugar', default=env('RODAJE_LUGAR') or 'United States')
    parser.add_argument('--busquedas', default=env('RODAJE_BUSQUEDAS') or 'founder,product manager,cto,software engineer')


def ritmo_from(args):
    try:
        start, _, end = args.horario.partition('-')
        hours = (day_time.fromisoformat(start.strip()), day_time.fromisoformat(end.strip()))
        if hours[0] >= hours[1]:
            raise ValueError
    except ValueError:
        raise ConfigError('Horario: HH:MM-HH:MM, la primera hora antes que la segunda.') from None
    try:
        ZoneInfo(args.zona)
    except (ZoneInfoNotFoundError, ValueError):
        raise ConfigError(f'Zona horaria desconocida: {args.zona}.') from None
    try:
        scale = float(args.escala)
        writes = {kind: int(getattr(args, kind)) for kind in WRITE_DEFAULTS}
    except ValueError:
        raise ConfigError('La escala y los números de escrituras deben ser números.') from None
    if not 0 < scale <= SCALE_MAX or any(not 0 <= n <= WRITE_MAX for n in writes.values()):
        raise ConfigError(f'La escala va de 0 a {SCALE_MAX} y cada tipo de escritura de 0 a {WRITE_MAX} al día.')
    texts = ()
    if writes['comentarios'] or writes['respuestas']:
        try:
            texts = tuple(t.strip() for t in Path(args.textos).read_text('utf-8').splitlines() if t.strip())
        except OSError:
            raise ConfigError('Comentarios y respuestas solo con --textos: un archivo con tus textos, uno por línea '
                              '(cada uno sale una sola vez).') from None
        if not texts:
            raise ConfigError('El archivo de --textos no tiene ningún texto.')
    searches = tuple(s.strip() for s in args.busquedas.split(',') if s.strip())
    if not searches or not args.lugar.strip():
        raise ConfigError('Hacen falta un lugar y al menos una búsqueda.')
    return Ritmo(hours=hours, zone=args.zona, scale=scale, writes=writes, place=args.lugar.strip(), searches=searches,
                 texts=texts)


def main(args, settings):
    if args.cuenta == 'estado':
        return status(settings.data, args.otra, args.dias or 14)
    if not args.cuenta:
        raise ConfigError('Falta la cuenta: python -m navegador rodaje <cuenta> (o RODAJE_CUENTA).')
    ritmo = ritmo_from(args)
    if not Store(settings.account_dir(args.cuenta)).exists():
        raise ConfigError('Esa cuenta no tiene perfil en el servicio: primero python -m navegador login <cuenta>.')
    from linkedin_directo.servicio import ServiceTransport
    url = args.url or os.environ.get('NAVEGADOR_URL') or f'http://127.0.0.1:{settings.port}'
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    logging.getLogger('httpx').setLevel(logging.WARNING)  # its lines carry the service's url with the account
    return Rodaje(args.cuenta, settings.data, ServiceTransport(url, settings.token, args.cuenta), ritmo).run(args.dias)
