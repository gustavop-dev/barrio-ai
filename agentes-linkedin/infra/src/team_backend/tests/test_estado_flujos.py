"""The state of every flow (flujos.py, 19/11/2026): the registry, the status rules, the Slack report and its command.

Each incident of 17–19/11/2026 is rebuilt with fixture rows on top of a healthy day and must turn its own flow 🟡/🔴 with
its plain reason while the others stay green. The clock is frozen (DAY of test_ventana_lectura, a Wednesday in Bogotá).
Slack is an httpx.MockTransport (SlackBase); nothing calls a provider or LinkedIn, and the report writes nothing."""
import io
import re
import uuid
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext

from team_backend import alertas_slack, flujos, miembros, operador
from team_backend.models import (ActionExecution, ActionProposal, AuditEvent, Contact, EditorialPiece, Job, Member,
                                 ObservedPost, WebResearchRun)
from team_backend.tests.test_alertas_slack import SUMMARY, SlackBase
from team_backend.tests.test_ventana_lectura import DAY, at

DOC = Path(__file__).resolve().parents[5] / 'docs' / 'funcionalidades' / 'estado-de-flujos.md'
EVERY_FLOW_ON = {
    'SLACK_ESTADO_FLUJOS': 'true', 'SLACK_WEBHOOK_RESUMEN': SUMMARY, 'SLACK_ESTADO_FLUJOS_HORA': '18:00',
    'SLACK_ESTADO_FLUJOS_MANANA': '08:45', 'OPERATOR_AUTOPILOT': 'true', 'STRATEGY_ENABLED': 'true',
    'WEEKLY_SUMMARY_ENABLED': 'true', 'MONTHLY_REVIEW_ENABLED': 'true', 'INBOX_ENABLED': 'true', 'LEAD_ENABLED': 'true',
    'BUYER_WARMUP_ENABLED': 'true', 'BUYER_FIRST_MESSAGE_ENABLED': 'true', 'BUYER_SEQUENCE_ENABLED': 'true',
    'BUYER_REPLY_ENABLED': 'true', 'CALCOM_BOOKING_URL': 'https://cal.example.test/gustavo', 'PROFILE_ENABLED': 'true',
    'REFERENTES_ANALISIS': 'true', 'EDITORIAL_POST_TIME': '08:30', 'EDITORIAL_LEAD_HOURS': '12'}


class FlowsBase(SlackBase):
    """A healthy Wednesday with every flow on. The web research switch is patched on (web_sources.live_web) instead of
    LIVE_PROVIDERS, so no provider could be reached even by mistake."""

    def setUp(self):
        super().setUp()
        env = patch.dict('os.environ', EVERY_FLOW_ON)
        env.start()
        self.addCleanup(env.stop)
        web = patch('team_backend.web_sources.live_web', return_value=None)
        web.start()
        self.addCleanup(web.stop)
        self.clock = at(18, 30)
        clock = patch('django.utils.timezone.now', side_effect=lambda: self.clock)
        clock.start()
        self.addCleanup(clock.stop)
        self.publisher = operador.register_account(self.gustavo, 'linkedin_fake', 'pub-1', 'Publicación')
        self.healthy()

    def job(self, kind, state='complete', created=None, finished=None, error='', **params):
        created = created or at(10)
        return Job.objects.create(owner=self.bot, request_hash=uuid.uuid4().hex, agent='operador', task=kind, kind=kind,
                                  state=state, error=error, params=params, created_at=created,
                                  finished_at=finished or (created + timedelta(minutes=2) if state != 'queued' else None))

    def piece(self, day, created, state='ready', **fields):
        return EditorialPiece.objects.create(account=self.publisher, slot_date=day, scheduled_for=at(8, 30), state=state,
                                             final_text='Hoy', created_at=created, **fields)

    def write(self, account, capability, when, state='confirmed', **target):
        proposal = ActionProposal.objects.create(account=account, capability=capability, payload={'text': 'x'},
                                                 payload_hash=uuid.uuid4().hex * 2, state=state, created_at=when - timedelta(minutes=10),
                                                 **target)
        ActionExecution.objects.create(proposal=proposal, idempotency_key=uuid.uuid4().hex, provider='linkedin_fake', state=state,
                                       executed_by=self.gustavo, started_at=when, wrote=True)
        return proposal

    def healthy(self):
        """Today's post out at 08:30 with its own image, a comment on a referent's post at 10:00, the inbox read at
        18:00 and the comments of his posts at 18:15: what a good day leaves."""
        today = self.piece(DAY.date(), at(21, 0, -1), image_kind='infografia', image_review={'ok': True})
        self.write(self.publisher, 'CONT-09', at(8, 30), piece=today)
        operador.add_referent(self.gustavo, self.account, 'https://www.linkedin.com/in/referente-ai/', 'Habla de agentes')
        post = ObservedPost.objects.create(account=self.account, provider_post_id='op-1', text='x', observed_at=at(9))
        self.write(self.account, 'INT-03', at(10), post=post)
        self.job('read_inbox', created=at(18), account=str(self.account.id))
        self.reads(1, at(18, 15))  # the comments of his posts read a quarter of an hour ago

    def results(self, now=None, member=None):
        return {r.flujo.id: r for r in flujos.informe(now or self.clock, member)}

    def states(self, results):
        return {key: r.estado for key, r in results.items()}

    def summary(self):
        return self.texts(SUMMARY)


class HealthyDayTests(FlowsBase):
    def test_a_healthy_day_is_all_green_in_one_message(self):
        results = self.results()
        self.assertEqual(set(self.states(results).values()), {flujos.VERDE}, {k: r.hallazgos for k, r in results.items()})
        self.assertEqual(len(results), len(flujos.FLUJOS))
        text = flujos.texto(self.clock, list(results.values()))
        self.assertIn('🟢 Todo funciona: 13 flujos al día.', text)
        self.assertLessEqual(len(text), alertas_slack.PART_CHARS)
        self.assertEqual(alertas_slack.parts(text), [text])

    def test_the_evening_message_reads_on_a_phone(self):
        """Snapshot of the healthy evening report: the date and the verdict, one line per flow, then each green flow
        with its key number. No table, no internal id, no long line."""
        text = flujos.text_for(self.clock)
        self.maxDiff = None
        self.assertEqual(text, HEALTHY_EVENING)
        self.assertNotIn('|', text)
        self.assertFalse(re.search(r'[0-9a-f]{8}-[0-9a-f]{4}-', text))
        self.assertLessEqual(max(len(line) for line in text.split('\n')), 160)

    def test_the_morning_message_is_short(self):
        """Snapshot of the morning report (08:45) of the post incident: what moved since midnight, what waits today and
        one line per problem with what to do; never the stages."""
        ActionExecution.objects.filter(proposal__capability='CONT-09').delete()
        ActionProposal.objects.filter(capability='CONT-09').delete()
        EditorialPiece.objects.all().delete()
        self.clock = at(8, 45)
        text = flujos.text_for(self.clock, morning=True)
        self.maxDiff = None
        self.assertEqual(text, MORNING_POST_MISSING)
        self.assertNotIn('  · ', text)

    def test_a_switched_off_flow_is_white_with_its_switch(self):
        with patch.dict('os.environ', {'NETWORK_ENABLED': 'false', 'STRATEGY_ENABLED': 'false', 'WEEKLY_SUMMARY_ENABLED': 'false',
                                       'MONTHLY_REVIEW_ENABLED': 'false', 'INBOX_ENABLED': 'false'}):
            results = self.results()
            text = flujos.texto(self.clock, list(results.values()))
        self.assertEqual({k for k, s in self.states(results).items() if s == flujos.APAGADO}, {'red', 'plan_resumenes', 'inbox'})
        self.assertIn('⚪ Crecimiento de red (NETWORK_ENABLED=false)', text)
        self.assertIn('⚪ Mensajes privados (INBOX_ENABLED=false)', text)
        self.assertIn('⚪ Plan semanal y resúmenes (STRATEGY_ENABLED, WEEKLY_SUMMARY_ENABLED y MONTHLY_REVIEW_ENABLED en false)', text)
        self.assertIn('🟢 Todo funciona: 10 flujos al día. · ⚪ 3 apagados', text)

    def test_the_machine_flow_opened_shows_its_spend_and_writes(self):
        """Salud de la máquina never turns white: the autopilot off is red, and the opened flow carries its spend and
        the day's writes under its stages."""
        with patch.dict('os.environ', {'OPERATOR_AUTOPILOT': 'false'}):
            results = self.results()
            text = flujos.texto(self.clock, list(results.values()))
        self.assertEqual({k for k, s in self.states(results).items() if s != flujos.VERDE}, {'salud'})
        self.assertEqual(results['salud'].estado, flujos.ROJO)
        self.assertIn('🔴 *Salud de la máquina* — detenido\n⚠️ El autopiloto está apagado: nada se encola solo.', text)
        self.assertIn('\n  · IA: 0,00 USD hoy, 0,00 de 100,00 en el mes', text)
        self.assertRegex(text, r'\n  · Escrituras de hoy: [^\n]*posts 1/1')
        self.assertIn('👉 Qué hacer: Enciende OPERATOR_AUTOPILOT.', text)

    def test_a_switched_off_stage_says_its_switch(self):
        with patch.dict('os.environ', {'BUYER_SEQUENCE_ENABLED': 'false', 'BUYER_REPLY_ENABLED': 'false'}):
            buyer = self.results()['comprador']
        self.assertEqual(buyer.estado, flujos.VERDE)
        off = {e.nombre: e.apagada for e in buyer.etapas if e.apagada}
        self.assertEqual(off, {'Secuencia (mensajes 2 a 4)': 'BUYER_SEQUENCE_ENABLED', 'Respuesta a quien respondió': 'BUYER_REPLY_ENABLED',
                               'Reunión': 'BUYER_REPLY_ENABLED=false'})


class IncidentTests(FlowsBase):
    """The five incidents of 17–19/11/2026: each turns its own flow, and only its flow, with its plain reason."""

    def only(self, results, flow, state):
        expected = {key: flujos.VERDE for key in results}
        expected[flow] = state
        self.assertEqual(self.states(results), expected, {k: [h.texto for h in r.hallazgos] for k, r in results.items()})
        return results[flow]

    def test_the_daily_post_not_prepared_after_a_job_id_collision(self):
        """19/11/2026: the day's automatic job had already run for a piece later moved to another day; every tick asked
        again for that id and no piece was prepared, two days in a row."""
        ActionExecution.objects.filter(proposal__capability='CONT-09').delete()
        ActionProposal.objects.filter(capability='CONT-09').delete()
        EditorialPiece.objects.all().delete()
        job = self.job('prepare_piece', created=at(20, 30, -1), slot=DAY.date().isoformat())
        # Its piece was later moved away as another day's extra post: the day is free but its job id is taken.
        self.piece(DAY.date() + timedelta(days=3), at(20, 40, -1), second_of_day=True, origin_job=str(job.id))
        self.clock = at(8, 45)
        post = self.only(self.results(), 'post_diario', flujos.ROJO)
        self.assertEqual(post.hallazgos[0].texto, 'El post de hoy no está preparado: su preparación debía empezar el 03/11 a las '
                                                  '20:30 y el trabajo de ese día ya había corrido y el autopiloto no lo volvió a '
                                                  'encargar.')
        self.assertIn('Planificar', post.hallazgos[0].accion)
        morning = flujos.text_for(self.clock, morning=True)
        self.assertIn('🔴 *Post diario*: El post de hoy no está preparado', morning)
        self.clock = at(18, 30)  # the evening: it did not go out at its hour
        post = self.only(self.results(), 'post_diario', flujos.ROJO)
        self.assertIn('El post de hoy no salió a su hora (08:30): no hay pieza preparada.', [h.texto for h in post.hallazgos])

    def test_follows_and_invitations_without_profile_reads(self):
        """18/11/2026: research spent the shared profile reads at 13:04 and seguir/invitar failed 151 times."""
        with patch.dict('os.environ', {'OPERATOR_PROFILE_READ_DAILY_LIMIT': '4'}):
            for minute in range(4):
                AuditEvent.objects.create(action='operator.profile_read', target=miembros.policy_key(None), created_at=at(13, minute),
                                          metadata={'account': str(self.account.id), 'purpose': 'research', 'pool': 'investigacion'})
            for n in range(6):
                contact = Contact.objects.create(account=self.account, provider_user_id=f'p-{n}', display_name='P', source='manual',
                                                 stage='fit', classification={'role': 'comprador', 'fit': True},
                                                 discovered_at=at(8), updated_at=at(8))
                capability = 'RED-01' if n % 2 else 'RED-02'
                proposal = ActionProposal.objects.create(account=self.account, contact=contact, capability=capability, payload={},
                                                         payload_hash=uuid.uuid4().hex * 2, state='approved', created_at=at(9))
                self.job('execute_action', state='failed', created=at(14, n), proposal=str(proposal.id),
                         error='Tope compartido de lecturas de perfil alcanzado; la operación espera.')
            red = self.only(self.results(), 'red', flujos.ROJO)
            text = flujos.texto(self.clock, list(self.results().values()))
        texts = [h.texto for h in red.hallazgos]
        self.assertIn('Seguidos: los 3 intentos de las últimas 24 h fallaron (sin lecturas de perfil: el cupo del día se gastó).', texts)
        self.assertIn('Invitados: los 3 intentos de las últimas 24 h fallaron (sin lecturas de perfil: el cupo del día se gastó).', texts)
        # The four of 13:00 plus the referent's profile read of the healthy day (18:30): research took them all.
        self.assertIn('Seguir e invitar se quedaron sin lecturas de perfil a las 13:03 (acciones 0/2, investigación 5/2).', texts)
        self.assertIn('👉 Qué hacer: Sube OPERATOR_PROFILE_READ_DAILY_LIMIT (hasta 100) o baja OPERATOR_PROFILE_READ_RESEARCH_SHARE.',
                      text)
        self.assertIn('  · Seguidos: hoy 0 de 3 propuestos, 3 fallaron · ayer 0 · 3 aprobados en cola desde las 09:00', text)

    def test_web_research_left_running_and_the_buyer_checks_out_of_budget(self):
        """18/11/2026: runs stayed «running» forever (their result never saved) and the buyers' web checks stopped on the
        cycle's cost_cap."""
        WebResearchRun.objects.create(key=f'etapa:{uuid.uuid4()}:1:20261104', request_hash='0' * 64, created_at=at(9), state='running')
        research = self.only(self.results(), 'investigacion', flujos.AMARILLO)
        self.assertEqual(research.hallazgos[0].texto, '1 investigación quedó a medias (en curso desde las 09:00): su gasto no se '
                                                      'repite y su resultado no llegó.')
        with patch.dict('os.environ', {'NETWORK_STAGE_CHECK': 'true'}):
            for n in range(3):
                self.job('check_buyer_stages', state='failed', created=at(11, n * 20), error='cost_cap', account=str(self.account.id))
            results = self.results()
        self.assertEqual(results['red'].estado, flujos.ROJO)
        self.assertIn('Verificados en la web: los 3 intentos de las últimas 24 h fallaron (se acabó el presupuesto de su ciclo).',
                      [h.texto for h in results['red'].hallazgos])

    def test_buyers_discarded_with_a_level_that_keeps_them(self):
        """18/11/2026: the classifier's fit took buyers out of the neighborhood although their level kept them."""
        Contact.objects.create(account=self.account, provider_user_id='b-1', display_name='Compradora', source='manual', stage='discarded',
                               classification={'role': 'comprador', 'fit': False, 'buyer': {'level': 'probable'}},
                               discovered_at=at(9), updated_at=at(15))
        red = self.only(self.results(), 'red', flujos.AMARILLO)
        self.assertEqual(red.hallazgos[0].texto, '1 comprador salió del barrio en 24 h con un nivel que lo mantiene (una regla de '
                                                 'clasificación, no su nivel).')
        self.assertIn('reevaluar-compradores', red.hallazgos[0].accion)
        self.assertNotIn('Compradora', flujos.texto(self.clock, list(self.results().values())))  # nobody is named

    def test_posts_with_the_generic_fallback_image(self):
        """17–18/11/2026: 4 of 14 posts went out with the brand card the code draws when their own image failed."""
        self.piece(DAY.date() + timedelta(days=1), at(18, 0), image_kind='tarjeta', image_review={'ok': True, 'mode': 'fixed_brand_card'},
                   image_reason='Infografía rechazada tras una corrección: el texto no cabe')
        post = self.only(self.results(), 'post_diario', flujos.AMARILLO)
        self.assertEqual(post.hallazgos[0].texto, '1 pieza lista lleva un respaldo en vez de su imagen propia (la tarjeta '
                                                  'genérica: la revisión visual rechazó la infografía); 1 de 2 esta semana.')

    def test_the_other_fallbacks_count_too(self):
        """Since #144 the post's key line and the editor's photo come before the brand card: still not its own image, so
        the same yellow, naming which fallback and the reason behind its «Respaldo con…» prefix."""
        reason = 'Infografía rechazada tras una corrección: el texto no cabe'
        self.piece(DAY.date() + timedelta(days=1), at(18, 0), image_kind='infografia',
                   image_review={'ok': True, 'mode': 'tarjeta_contenido', 'fallback': {'level': 'contenido', 'reason': reason}},
                   image_reason='Respaldo con la frase clave del post: ' + reason)
        self.piece(DAY.date() - timedelta(days=2), at(9, 0, -3), image_kind='foto',
                   image_review={'ok': True, 'mode': 'foto_respaldo', 'fallback': {'level': 'foto', 'reason': 'Sin proveedor visual'}},
                   image_reason='Respaldo con una foto de la galería: Sin proveedor visual')
        post = self.only(self.results(), 'post_diario', flujos.AMARILLO)
        self.assertEqual(post.hallazgos[0].texto, '1 pieza lista lleva un respaldo en vez de su imagen propia (la tarjeta con '
                                                  'la frase del post: la revisión visual rechazó la infografía); 2 de 3 esta semana.')
        stage = {e.nombre: e for e in post.etapas}['Imagen propia']
        self.assertEqual((stage.hoy.entraron, stage.hoy.avanzaron), (1, 0))


class ReadOnlyTests(FlowsBase):
    def test_the_report_never_writes_reads_linkedin_or_calls_a_provider(self):
        forbidden = AssertionError('the report must not call this')
        with patch('team_backend.connectors.get_connector', side_effect=forbidden), \
                patch('knowledge.providers.claude', side_effect=forbidden), \
                patch('knowledge.providers.reserve', side_effect=forbidden), \
                patch('knowledge.providers.embeddings', side_effect=forbidden), \
                patch('team_backend.research.research', side_effect=forbidden), \
                patch('httpx.Client.send', side_effect=forbidden), \
                CaptureQueriesContext(connection) as queries:
            flujos.text_for(self.clock)
            flujos.text_for(at(8, 45), morning=True)
        writes = [q['sql'] for q in queries.captured_queries if re.match(r'\s*(INSERT|UPDATE|DELETE)', q['sql'], re.I)]
        self.assertEqual(writes, [])

    def test_a_broken_flow_never_hides_the_others(self):
        def broken(ctx):
            raise RuntimeError('rota')
        with self.assertLogs('team_backend.flujos', 'WARNING'):
            results = flujos.informe(self.clock, flujos=[replace(flujos.FLUJOS_POR_ID['red'], medir=broken),
                                                         flujos.FLUJOS_POR_ID['ideas']])
        self.assertEqual([r.estado for r in results], [flujos.AMARILLO, flujos.VERDE])
        self.assertEqual(results[0].hallazgos[0].texto, 'No se pudo medir este flujo (error al leer su estado).')


class ScheduleTests(FlowsBase):
    def reports(self):
        return [t for t in self.summary() if 'estado de los flujos' in t.split('\n', 1)[0].lower()]

    def test_once_per_slot_morning_and_evening(self):
        for moment in (at(8, 40), at(8, 45), at(8, 50), at(12), at(17, 59)):
            self.clock = moment
            self.watch(moment)
        self.assertEqual(len(self.reports()), 1)
        self.assertTrue(self.reports()[0].startswith('Barrio · *Buenos días: estado de los flujos* · mié 04/11 · 08:45'))
        for moment in (at(18), at(18, 5), at(21), at(23, 59)):
            self.clock = moment
            self.watch(moment)
        self.assertEqual(len(self.reports()), 2)
        self.assertTrue(self.reports()[1].startswith('Barrio · *Estado de los flujos* · mié 04/11 · 18:00'))
        self.assertEqual(sorted(AuditEvent.objects.filter(action='slack.alert', target__startswith='estado:')
                                .values_list('target', flat=True)), ['estado:manana', 'estado:tarde'])
        self.assertFalse(any('estado de los flujos' in t.lower() for t in self.texts()))  # never on the alerts channel

    def test_it_replaces_the_old_daily_summary_only_while_it_is_on(self):
        old = lambda: [t for t in self.summary() if 'Resumen del 04/11' in t]  # noqa: E731
        self.clock = at(21, 30)
        self.watch(self.clock)
        self.assertEqual((old(), len(self.reports())), ([], 1))
        with patch.dict('os.environ', {'SLACK_ESTADO_FLUJOS': 'false'}):
            self.watch(self.clock)
        self.assertEqual((len(old()), len(self.reports())), (1, 1))

    def test_an_empty_morning_hour_turns_the_short_report_off(self):
        with patch.dict('os.environ', {'SLACK_ESTADO_FLUJOS_MANANA': ''}):
            self.clock = at(9)
            self.watch(self.clock)
        self.assertEqual(self.reports(), [])

    def test_a_long_report_goes_in_parts_that_read_alone(self):
        text = 'Barrio · *Estado de los flujos* · mié 04/11 · 18:00\n' + '\n\n'.join(f'Bloque {n}\n' + 'x' * 900 for n in range(9))
        parts = alertas_slack.parts(text)
        self.assertGreater(len(parts), 2)
        self.assertTrue(all(len(p) <= alertas_slack.PART_CHARS for p in parts))
        self.assertTrue(parts[1].startswith(f'Barrio · *Estado de los flujos* · mié 04/11 · 18:00 (sigue 2/{len(parts)})\n\n'))
        self.assertEqual(''.join(p for p in parts).count('x'), 9 * 900)
        with patch('team_backend.flujos.text_for', return_value=text):
            self.clock = at(18)
            self.watch(self.clock)
            self.watch(self.clock)
        self.assertEqual(self.summary(), parts)  # every part once, in order


class TwoMembersTests(FlowsBase):
    def test_each_member_gets_hers_and_the_machine_goes_once(self):
        with override_settings(REFERENTS_GUSTAVO_USERNAME=self.gustavo.get_username()):
            gustavo, _ = miembros.ensure_first_member()
        user = type(self.gustavo).objects.create_user('cto-test', password='local-only-password')
        cto = Member.objects.create(organization=gustavo.organization, user=user, display_name='CTO de prueba', role='CTO')
        alerts = alertas_slack.estado_de_flujos(self.clock)
        self.assertEqual([a.key for a in alerts], ['estado:tarde', f'estado:tarde:{cto.pk}'])
        texts = [a.text() for a in alerts]
        self.assertTrue(texts[0].startswith('Barrio · Gustavo · *Estado de los flujos*'), texts[0][:80])
        self.assertTrue(texts[1].startswith('Barrio · CTO de prueba · *Estado de los flujos*'), texts[1][:80])
        self.assertIn('Investigación en internet', texts[0])
        self.assertNotIn('Investigación en internet', texts[1])  # the machine's: only in the first member's


class CommandTests(FlowsBase):
    def run_command(self, *args):
        out = io.StringIO()
        call_command('operador', '--usuario', self.gustavo.get_username(), 'estado-flujos', *args, stdout=out)
        return out.getvalue()

    def test_it_prints_without_sending_by_default(self):
        out = self.run_command()
        self.assertIn('Barrio · *Estado de los flujos* · mié 04/11 · 18:30', out)
        self.assertIn('Solo impreso: con --enviar también va a Slack.', out)
        self.assertEqual(self.sent, [])
        self.assertFalse(AuditEvent.objects.filter(action='slack.alert').exists())
        self.assertIn('Buenos días', self.run_command('--manana'))

    def test_it_sends_once_per_minute_with_enviar(self):
        self.assertIn('Enviado al canal de resúmenes de Slack.', self.run_command('--enviar'))
        self.assertIn('No se envió: ya salió en este minuto.', self.run_command('--enviar'))
        self.assertEqual(len(self.summary()), 1)


class RegistryTests(FlowsBase):
    def test_the_plain_reasons_never_leak_an_id_or_a_link(self):
        self.assertEqual(flujos.motivo('cost_cap'), 'se acabó el presupuesto de su ciclo')
        self.assertEqual(flujos.motivo('Ciclo detenido: call_timeout'), 'una llamada a la IA tardó más que su límite')
        self.assertEqual(flujos.motivo('Parte de las acciones del cupo de lecturas de perfil agotada (2/2); …'),
                         'sin lecturas de perfil: la investigación dejó sin cupo a las acciones')
        self.assertEqual(flujos.motivo(''), 'sin detalle')
        raw = flujos.motivo('Algo raro con 3fa85f64-5717-4562-b3fc-2c963f66afa6 en https://example.test/x. Detalle privado')
        self.assertEqual(raw, 'algo raro con … en …')

    def test_the_document_covers_every_flow_and_stage(self):
        doc = DOC.read_text(encoding='utf-8')
        for name, stages in flujos.documented_names():
            with self.subTest(flujo=name):
                self.assertIn(f'## {name}', doc)
                for stage in stages:
                    self.assertIn(stage, doc)


HEALTHY_EVENING = """Barrio · *Estado de los flujos* · mié 04/11 · 18:30
🟢 Todo funciona: 13 flujos al día.

🟢 Post diario
🟢 Plan semanal y resúmenes
🟢 Tus ideas
🟢 Correcciones tuyas a un post
🟢 Comentarios en referentes
🟢 Respuestas en tus posts
🟢 Crecimiento de red
🟢 Comprador
🟢 Mensajes privados
🟢 Referentes
🟢 Investigación en internet
🟢 Perfil y posicionamiento
🟢 Salud de la máquina

🟢 *Post diario*: publicado hoy a las 08:30
🟢 *Plan semanal y resúmenes*: esta semana sin plan (el director planea cada día)
🟢 *Tus ideas*: hoy 0 capturas recibidas; 0 ideas esperan en la mesa editorial
🟢 *Correcciones tuyas a un post*: hoy no mandaste correcciones
🟢 *Comentarios en referentes*: hoy 1 comentario publicado de 1 propuesto
🟢 *Respuestas en tus posts*: hoy 0 respuestas publicadas; 0 comentarios esperan respuesta
🟢 *Crecimiento de red*: hoy 0 seguidos, 0 invitados y 0 aceptaron tu invitación
🟢 *Comprador*: 0 compradores calentándose; 0 mensajes listos para que los envíes
🟢 *Mensajes privados*: bandeja leída 1 vez hoy; 0 conversaciones te esperan
🟢 *Referentes*: 1 referente activo; 0 cambios esperan tu respuesta
🟢 *Investigación en internet*: hoy no se pidió ninguna
🟢 *Perfil y posicionamiento*: al día
🟢 *Salud de la máquina*: IA: 0,00 USD hoy, 0,00 de 100,00 en el mes"""


MORNING_POST_MISSING = """Barrio · *Buenos días: estado de los flujos* · mié 04/11 · 08:45
🔴 1 detenido · 🟢 12 funcionando

🔴 Post diario
🟢 Plan semanal y resúmenes
🟢 Tus ideas
🟢 Correcciones tuyas a un post
🟢 Comentarios en referentes
🟢 Respuestas en tus posts
🟢 Crecimiento de red
🟢 Comprador
🟢 Mensajes privados
🟢 Referentes
🟢 Investigación en internet
🟢 Perfil y posicionamiento
🟢 Salud de la máquina

*Desde medianoche*
• Post de hoy: no está preparado

*Lo que pide atención*
🔴 *Post diario*: El post de hoy no está preparado: su preparación debía empezar el 03/11 a las 20:30 y el autopiloto no \
encargó su preparación.
   👉 Prepáralo a mano desde el calendario («Planificar») y revisa el autopiloto."""
