"""BIB-11-respuesta-comprador: la respuesta del comprador, la reunión agendada y la entrega del lead (clase 11, con la
clase 08 y la tabla de diagnóstico de la clase 12; fase 6 de docs/plan-outbound.md), medidas con las funciones de
producción.

Cada persona recorre el camino real hasta el «Hecho, le escribí» del primer mensaje (fase 3); después responde y un reloj
simulado avanza: la lectura del inbox (el conector simulado es LinkedIn: lo que Gustavo envía a mano y lo que ella
responde), el paso de borradores del autopiloto con sus jobs, Tu turno y los cierres de Gustavo, el webhook firmado de
Cal.com (lo publica el cliente de pruebas) y la entrega. Claude y Jev simulados (test_comprador_e2e.judge_reply_type y
judge_reply_draft); unidades del curso sintéticas, sin red, sin Cal.com ni proveedores pagados. El equipo nunca envía un
mensaje: las respuestas son borradores que Gustavo copia y envía (INB-08)."""
import hashlib
import hmac
import json
import os
from datetime import date, datetime, timedelta
from datetime import timezone as utc_tz
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from team_backend import agenda_calcom, alertas_slack, comprador, evaluaciones, lectura_embudo, operador, respuesta_comprador
from team_backend.models import AuditEvent, BuyerDraft, BuyerJourney, Contact, MeetingBooking
from team_backend.tests.test_comprador import BuyerBase
from team_backend.tests.test_comprador_e2e import BOOKING_URL, DAY, HOUR, ReplyPathBase, reply_input

CASE = evaluaciones.COURSE_CASES['respuesta_comprador']
PEOPLE = {'flujo': ('resp-ana', 'Ana Interesa', 'Founder & CEO at Acme'), 'P': ('resp-bea', 'Bea Pregunta', 'Founder & CEO at Acme'),
          'N1': ('resp-cris', 'Cris Enero', 'Founder & CEO at Acme'), 'N2': ('resp-dani', 'Dani Ahora', 'Founder & CEO at Acme'),
          'X': ('resp-eva', 'Eva Fuera', 'Founder & CEO at Acme'), 'O': ('resp-fer', 'Fer Redirige', 'Founder & CEO at Globex'),
          'B': ('resp-gil', 'Gil Duda', 'Founder & CEO at Acme'), 'E': ('resp-hugo', 'Hugo Sinenlace', 'Founder & CEO at Acme')}
FIRST_WAVE = ('flujo', 'P', 'N1', 'N2', 'X', 'O', 'B')


def first_of_month_after(at, month):
    """The first day of the month after `month`, the next one after `at` (local): «after January» → 1 February."""
    local = at.astimezone(operador.local_tz()).date()
    target = month % 12 + 1
    day = date(local.year, target, 1)
    return day if day > local else date(local.year + 1, target, 1)


class ReplyCaseBase(ReplyPathBase):
    def run_case(self):
        """Every variant with the production functions, graded with grade_course_case."""
        people = {}
        for variant, (slug, name, headline) in PEOPLE.items():
            people[variant] = self.messaged(slug, name, headline=headline)
            if reply_input(variant, 'borrador'):
                self.write_reply(people[variant], reply_input(variant, 'borrador'), faltan=reply_input(variant, 'faltan') or (),
                                 referido=reply_input(variant, 'referido') or '')
        self.fake.seed_person('bruno-globex', 'Bruno Ruiz', 'Head of Operations at Globex', location='Austin, Texas')
        writes, at, result = self.fake.state['writes'], self.start + DAY, {}

        # They answer a day after the first message. I: with the switch off nothing is classified.
        for variant in FIRST_WAVE:
            self.she_replies(people[variant], reply_input(variant), at)
        with patch.dict(os.environ, {'BUYER_REPLY_ENABLED': 'false'}):
            self.cycle(at + HOUR)
        result['I_clasificadas'] = sum(len(self.replies_of(c)) for c in people.values())
        self.cycle(at + 2 * HOUR)
        self.cycle(at + 3 * HOUR)  # the referral's profile, read in the next cycle
        # E: interested while CALCOM_BOOKING_URL is empty.
        self.she_replies(people['E'], reply_input('E'), at + 4 * HOUR)
        with patch.dict(os.environ, {'CALCOM_BOOKING_URL': ''}):
            self.cycle(at + 5 * HOUR)
        later = at + 6 * HOUR

        def kind(variant):
            row = self.reply(people[variant])
            return ((row.inputs or {}).get('clasificacion') or {}).get('tipo') if row else None

        def link(variant):
            row = self.reply(people[variant])
            return bool(row and BOOKING_URL in (row.text or ''))

        for variant in FIRST_WAVE:
            result[f'{variant}_tipo'] = kind(variant)
        ana = people['flujo']
        result['flujo_paso'] = self.journey(ana).step
        ref = self.booking_ref(ana)
        result['flujo_enlace'] = bool(ref) and link('flujo') and ref in self.reply(ana).text
        result['P_enlace'] = link('P')
        cards = self.reply_cards(people['P'], later)
        result['P_faltan'] = bool(cards) and 'Falta' in cards[0]['body']
        cris = self.journey(people['N1'])
        result['N1_descanso'] = cris.rest_reason or None
        result['N1_hasta_lo_que_dijo'] = bool(cris.rest_until) and (
            cris.rest_until.astimezone(operador.local_tz()).date() == first_of_month_after(at, 1))
        result['N1_enlace'] = link('N1')
        dani = self.journey(people['N2'])
        rest = dani.touches.filter(kind='descanso').order_by('-at').first()
        result['N2_descanso_dias'] = round((dani.rest_until - rest.at) / DAY) if dani.rest_until and rest else None
        eva = self.journey(people['X'])
        result['X_salida'] = eva.exit_reason or None
        result['X_enlace'] = link('X')
        result['O_enlace'] = link('O')
        bruno = Contact.objects.filter(public_identifier='bruno-globex').first()
        bruno_journey = getattr(bruno, 'buyer_journey', None) if bruno else None
        result['O_referido'] = bool(bruno_journey and bruno_journey.referred_by_id == self.journey(people['O']).pk)
        gil = self.reply(people['B'])
        result['B_borrador'] = bool(gil and gil.text)
        result['B_tarjeta'] = bool(self.reply_cards(people['B'], later))
        hugo = self.reply(people['E'])
        result['E_borrador'] = bool(hugo and hugo.text)
        result['E_aviso'] = AuditEvent.objects.filter(action='buyer.reply_no_link').exists()

        # X: she writes again; nothing more is ever prepared for her.
        first = self.reply(people['X'])
        self.she_replies(people['X'], reply_input('X', 'despues'), later)
        self.cycle(later + HOUR)
        self.cycle(later + 3 * DAY)
        result['X_despues'] = (BuyerDraft.objects.filter(contact=people['X'], created_at__gt=first.created_at).count()
                               if first else None)

        # The flow: «Hecho, le escribí», she books through the link, the lead is handed over and Gustavo confirms it.
        cards = self.reply_cards(ana, later)
        if cards:
            self.close_at(cards[0], 'enviado', later)
        booked = later + DAY
        self.webhook('BOOKING_CREATED', 'case-booking-1', start=booked + 3 * DAY, ref=ref or '', name='Ana Interesa',
                     email='ana@acme.example', at=booked)
        result['flujo_reunion'] = self.journey(ana).step == 'reunion'
        handoff = self.handoff_of(ana, booked + HOUR)
        fields = ('persona', 'empresa', 'fuente', 'recorrido', 'conversacion', 'reunion', 'negocio')
        result['flujo_entrega'] = bool(handoff) and all(handoff.get(k) for k in fields) and handoff['fuente'] == 'linkedin' and (
            len(handoff['conversacion']) == 3 and not {'calificacion', 'preguntas'} & set(handoff))
        opportunity = self.confirm_opportunity(ana, booked + 2 * HOUR) if handoff else None
        result['flujo_oportunidad'] = opportunity.get('etapa') if opportunity else None

        result['mensajes_enviados'] = self.fake.state['writes'] - writes
        result['clasificacion_con_metodologia'] = any(
            j['purpose'] == 'buyer-reply-classify' and 'LI-11-M006-K01' in (j['state'].get('course_context') or '') for j in self.jev)
        result['borrador_con_metodologia'] = any('LI-11-M006-K01' in c['context'] for c in self.calls if c['purpose'] == 'buyer-reply')
        grounding = (self.reply(ana).review or {}) if self.reply(ana) else {}
        result['course_citations'] = grounding.get('course_citations', [])
        return evaluaciones.grade_course_case('respuesta_comprador', result, grounding), result


class ReplyCaseTests(ReplyCaseBase):
    """El caso completo. Línea base: docs/linea-base-respuesta-comprador.md."""

    def test_the_case_passes_with_production_functions(self):
        grade, result = self.run_case()
        self.assertTrue(grade['passed'], (grade['errors'], result))

    def test_the_case_loads_whole_versioned_sources_and_rejects_wrong_behaviour(self):
        context, grounding = evaluaciones.course_case_context('respuesta_comprador')
        self.assertEqual(grounding['course_missing'], [])
        result = dict(CASE['expected'], course_citations=CASE['required'])
        self.assertTrue(evaluaciones.grade_course_case('respuesta_comprador', result, grounding)['passed'])
        for wrong in ({'flujo_enlace': False}, {'X_despues': 1}, {'B_borrador': True}, {'N2_descanso_dias': 30},
                      {'mensajes_enviados': 1}, {'course_citations': CASE['required'] + ['LI-11-M006-K04']}):
            self.assertFalse(evaluaciones.grade_course_case('respuesta_comprador', dict(result, **wrong), grounding)['passed'], wrong)


class ReplyRulesTests(SimpleTestCase):
    """Las reglas fijas de la respuesta: el único enlace es el de la agenda y solo en interesado y pide información; sin
    fórmulas de venta, precios, promesas ni presión; en su idioma; corta. Y el enlace de agenda nunca en el M1–M4."""

    def test_the_case_replies(self):
        with patch('team_backend.guardas.blocks', return_value=([], [])):
            for variant, kind in (('flujo', 'interesado'), ('P', 'pide_informacion'), ('N1', 'no_es_el_momento'),
                                  ('X', 'no_le_interesa'), ('O', 'otra_persona')):
                self.assertEqual(respuesta_comprador.text_issues(kind, reply_input(variant, 'borrador'), reply_input(variant)), [], variant)

    def test_each_fixed_rule_names_what_breaks_it(self):
        her = reply_input('flujo')
        cases = (('interesado', 'Ana, our services cover exactly that. Pick a slot that suits you.', 'vende u ofrece servicios'),
                 ('pide_informacion', 'Bea, it is $4,000 per project. Pick a slot that suits you.', 'precios o tarifas'),
                 ('interesado', 'Ana, we will deliver it in two weeks. Pick a slot that suits you.', 'promete resultados'),
                 ('interesado', 'Ana, this is the last chance this month. Pick a slot that suits you.', 'presiona o insiste'),
                 ('no_le_interesa', 'Eva, thanks for telling me. Please reconsider when the reports hurt again.', 'presiona o insiste'),
                 ('no_es_el_momento', 'Cris, thanks for telling me. A quick call in February about the report?', 'llamada o una reunión'),
                 ('otra_persona', 'Fer, thanks. Could you book a meeting with Bruno for me?', 'llamada o una reunión'),
                 ('interesado', 'Ana, see https://acme.example/case first. Pick a slot that suits you.', 'enlace propio'),
                 ('interesado', 'Ana, write me at gustavo@barrio.example about the report. Pick a slot.', 'correo'),
                 ('interesado', 'Ana, the Friday report is the place to start. ' * 12, 'más de 500 caracteres'),
                 ('interesado', 'Ana, the Friday report.\nThe spreadsheet behind it.\nWho owns it.\nPick a slot that suits you.',
                  'más de 3 líneas'),
                 ('interesado', 'Ana, gracias por contarme lo del reporte de los viernes. Elige el horario que te quede mejor y '
                                'lo revisamos juntos con tus números.', 'fuera del idioma'))
        with patch('team_backend.guardas.blocks', return_value=([], [])):
            for kind, text, issue in cases:
                found = ' | '.join(respuesta_comprador.text_issues(kind, text, her))
                self.assertIn(issue, found, (kind, text))
            # The same call offer is right where she asked for it.
            self.assertEqual(respuesta_comprador.text_issues('interesado', 'Ana, happy to. A quick call about the Friday report?', her), [])

    def test_the_booking_link_is_one_at_the_end_and_only_where_it_belongs(self):
        link = f'{BOOKING_URL}?metadata%5Bbarrio%5D=abcdEFGH1234'
        body = reply_input('flujo', 'borrador')
        self.assertEqual(respuesta_comprador.link_issues('interesado', f'{body}\n{link}', link), [])
        self.assertEqual(respuesta_comprador.link_issues('pide_informacion', f'{body}\n{link}\n', link), [])
        self.assertEqual(respuesta_comprador.link_issues('interesado', body, link), ['La respuesta debe terminar con el enlace de tu agenda'])
        self.assertEqual(respuesta_comprador.link_issues('interesado', f'{body}\n{link}', ''), ['La respuesta debe terminar con el enlace de tu agenda'])
        self.assertEqual(respuesta_comprador.link_issues('interesado', f'{body} acme.io\n{link}', link),
                         ['La respuesta lleva otro enlace además del de tu agenda'])
        for kind in ('no_es_el_momento', 'no_le_interesa', 'otra_persona'):
            self.assertEqual(respuesta_comprador.link_issues(kind, f'{body}\n{link}', ''), ['Enlace en una respuesta que no lo lleva'])
            self.assertEqual(respuesta_comprador.link_issues(kind, body, ''), [])

    def test_her_link_carries_the_identifier_and_only_an_https_url(self):
        journey = SimpleNamespace(booking_ref='abcdEFGH1234')
        with patch.dict(os.environ, {'CALCOM_BOOKING_URL': BOOKING_URL}):
            self.assertEqual(respuesta_comprador.link_for(journey), f'{BOOKING_URL}?metadata%5Bbarrio%5D=abcdEFGH1234')
        with patch.dict(os.environ, {'CALCOM_BOOKING_URL': BOOKING_URL + '?duration=30'}):
            self.assertEqual(respuesta_comprador.link_for(journey), f'{BOOKING_URL}?duration=30&metadata%5Bbarrio%5D=abcdEFGH1234')
        for bad in ('', 'http://cal.com/gustavo', 'cal.com/gustavo', 'https://cal.com/a b'):
            with patch.dict(os.environ, {'CALCOM_BOOKING_URL': bad}):
                self.assertEqual(respuesta_comprador.link_for(journey), '', bad)


class ReplyDecisionTests(SimpleTestCase):
    """«otro» unless one type is confident (BUYER_REPLY_MIN) and ahead of the next one (BUYER_REPLY_MARGIN)."""

    def probabilities(self, **values):
        return {t: values.get(t, 0.05) for t in respuesta_comprador.TYPES}

    def test_the_type_needs_confidence_and_a_margin(self):
        decide = respuesta_comprador.decide
        self.assertEqual(decide(self.probabilities(interesado=0.9)), 'interesado')
        self.assertEqual(decide(self.probabilities(otra_persona=0.7)), 'otra_persona')  # the minimum itself passes
        self.assertEqual(decide(self.probabilities(interesado=0.69)), 'otro')
        self.assertEqual(decide(self.probabilities(interesado=0.9, pide_informacion=0.75)), 'otro')
        self.assertEqual(decide(self.probabilities(interesado=0.95, pide_informacion=0.7)), 'interesado')
        self.assertEqual(decide({}), 'otro')
        self.assertEqual(decide({'otro': 0.99, 'interesado': 0.1}), 'otro')  # only the five types count

    def test_the_thresholds_come_from_the_environment_within_bounds(self):
        with patch.dict(os.environ, {'BUYER_REPLY_MIN': '0.95'}):
            self.assertEqual(respuesta_comprador.decide(self.probabilities(interesado=0.9)), 'otro')
        with patch.dict(os.environ, {'BUYER_REPLY_MARGIN': '0.05'}):
            self.assertEqual(respuesta_comprador.decide(self.probabilities(interesado=0.9, pide_informacion=0.8)), 'interesado')
        with patch.dict(os.environ, {'BUYER_REPLY_MIN': 'x', 'BUYER_REPLY_MARGIN': '-3'}):
            self.assertEqual((respuesta_comprador.minimum(), respuesta_comprador.margin() >= 0), (0.7, True))


class ReplyDateTests(SimpleTestCase):
    """«No es el momento»: the date she said, read in code (English and Spanish), or 90 days."""
    TODAY = date(2026, 11, 17)

    def test_what_she_said_becomes_a_date(self):
        for text, expected in (('Write me after January.', date(2027, 2, 1)), ('Busy until March, sorry.', date(2027, 3, 1)),
                               ('Escríbeme después de enero.', date(2027, 2, 1)), ('Mejor en marzo de 2027.', date(2027, 3, 1)),
                               ('Try me next quarter.', date(2027, 1, 1)), ('el próximo año', date(2027, 1, 1)),
                               ('Ask again in 6 weeks.', date(2026, 12, 29)), ('in two months', date(2027, 1, 17)),
                               ('dentro de 10 días', date(2026, 11, 27)), ('Q2 2027 works', date(2027, 4, 1)),
                               ('After 2027-02-15 please.', date(2027, 2, 15)), ('desde el 15/02/2027', date(2027, 2, 15)),
                               ('In March, or maybe after April.', date(2027, 3, 1))):
            self.assertEqual(respuesta_comprador.said_date(text, self.TODAY), expected, text)
        for text in ('Not now, too busy.', 'Ahora no es el momento.', '', None):
            self.assertIsNone(respuesta_comprador.said_date(text, self.TODAY), text)

    def test_the_rest_ends_at_her_date_at_nine_or_after_ninety_days(self):
        at = datetime(2026, 11, 17, 18, 0, tzinfo=utc_tz.utc)
        until, said = respuesta_comprador.rest_until('Write me after January.', at)
        local = until.astimezone(operador.local_tz())
        self.assertEqual((local.date(), local.hour, said), (date(2027, 2, 1), 9, True))
        for text in ('Not now.', 'after 2026-01-10', '2028-06-01 maybe'):  # nothing, in the past, beyond a year
            self.assertEqual(respuesta_comprador.rest_until(text, at), (at + timedelta(days=90), False), text)

    def test_the_profile_she_named(self):
        self.assertEqual(respuesta_comprador.profile_in(reply_input('O')), 'bruno-globex')
        self.assertEqual(respuesta_comprador.profile_in('https://www.linkedin.com/in/lia-initech/'), 'lia-initech')
        self.assertEqual(respuesta_comprador.profile_in('Talk to Lia from operations.'), '')


SECRET = 'calcom-unit-secret'


def sign(raw, secret=SECRET):
    return hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()


def delivery(trigger='BOOKING_CREATED', **payload):
    body = {'uid': 'u-1', 'startTime': '2026-11-20T15:00:00Z', 'endTime': '2026-11-20T15:30:00Z',
            'attendees': [{'name': 'Ana Acme', 'email': 'ana@acme.example'}], 'metadata': {}}
    return json.dumps({'triggerEvent': trigger, 'createdAt': '2026-11-17T12:00:00Z', 'payload': {**body, **payload}}).encode()


class WebhookSignatureTests(SimpleTestCase):
    """X-Cal-Signature-256 = HMAC-SHA256(secret, raw body), hex (Cal.com's sendPayload.ts); the body only to match."""

    def test_only_the_exact_body_signed_with_the_secret_passes(self):
        raw = delivery()
        with patch.dict(os.environ, {'CALCOM_WEBHOOK_SECRET': SECRET}):
            self.assertTrue(agenda_calcom.signed(raw, sign(raw)))
            self.assertTrue(agenda_calcom.signed(raw, sign(raw).upper()))
            self.assertFalse(agenda_calcom.signed(raw + b' ', sign(raw)))
            self.assertFalse(agenda_calcom.signed(raw, sign(raw, 'other')))
            self.assertFalse(agenda_calcom.signed(raw, ''))
        with patch.dict(os.environ, {'CALCOM_WEBHOOK_SECRET': ''}):
            self.assertFalse(agenda_calcom.signed(raw, sign(raw, '')))

    def test_the_body_gives_only_checked_fields(self):
        fields = agenda_calcom._fields({'uid': ' u-9 ', 'rescheduleUid': 'u-8', 'startTime': '2026-11-20T15:00:00Z', 'endTime': '2026-11-20',
                                        'attendees': [{'name': 'Ana', 'email': 'ANA@Acme.Example'}],
                                        'metadata': {'barrio': 'abcdEFGH1234'}})
        self.assertEqual((fields['uid'], fields['previous'], fields['email'], fields['ref'], fields['end']),
                         ('u-9', 'u-8', 'ana@acme.example', 'abcdEFGH1234', None))
        self.assertEqual(fields['start'], datetime(2026, 11, 20, 15, 0, tzinfo=utc_tz.utc))
        bad = agenda_calcom._fields({'uid': 7, 'fromReschedule': 'u-7', 'attendees': 'Ana', 'metadata': {'barrio': "x' OR 1=1"},
                                     'startTime': '2026-11-20T15:00:00'})
        self.assertEqual((bad['uid'], bad['previous'], bad['name'], bad['email'], bad['ref'], bad['start']), ('', 'u-7', '', '', '', None))
        self.assertEqual(agenda_calcom._fields({'attendees': [{'email': 'not-an-email'}], 'metadata': {'barrio': 'short'}})['email'], '')


class WebhookReceiveTests(TestCase):
    """agenda_calcom.receive: what is rejected, ignored, stored and processed once."""

    def setUp(self):
        env = patch.dict(os.environ, {'CALCOM_WEBHOOK_SECRET': SECRET, 'BUYER_REPLY_ENABLED': 'true'})
        env.start()
        self.addCleanup(env.stop)

    def test_rejections_store_nothing_and_audit_once_an_hour(self):
        raw = delivery()
        now = timezone.now()
        self.assertEqual(agenda_calcom.receive(b'x' * (64 * 1024 + 1), sign(b'x'), now)[0], 413)
        self.assertEqual(agenda_calcom.receive(raw, 'f' * 64, now)[0], 403)
        self.assertEqual(agenda_calcom.receive(raw, 'f' * 64, now)[0], 403)
        with patch.dict(os.environ, {'CALCOM_WEBHOOK_SECRET': ''}):
            self.assertEqual(agenda_calcom.receive(raw, sign(raw), now), (403, {'detail': 'Webhook sin configurar.'}))
        with patch.dict(os.environ, {'BUYER_REPLY_ENABLED': 'false'}):
            self.assertEqual(agenda_calcom.receive(raw, sign(raw), now)[0], 202)
        self.assertFalse(MeetingBooking.objects.exists())
        self.assertEqual(sorted(AuditEvent.objects.filter(action='calcom.rejected').values_list('target', flat=True)), ['firma', 'sin_secreto'])

    def test_malformed_or_foreign_deliveries(self):
        now = timezone.now()
        for raw, status in ((b'not json', 400), (b'[1, 2]', 400), (delivery(uid=''), 400), (delivery('MEETING_ENDED'), 200)):
            self.assertEqual(agenda_calcom.receive(raw, sign(raw), now)[0], status, raw)
        self.assertFalse(MeetingBooking.objects.exists())

    def test_a_booking_nobody_matches_is_stored_once(self):
        raw = delivery(metadata={'barrio': 'unknownREF123'})
        now = timezone.now()
        status, body = agenda_calcom.receive(raw, sign(raw), now)
        self.assertEqual((status, body['emparejada_por'], body['estado']), (200, 'sin_emparejar', 'agendada'))
        self.assertEqual(agenda_calcom.receive(raw, sign(raw), now), (200, {'repetido': True}))
        booking = MeetingBooking.objects.get()
        self.assertEqual((booking.uid, booking.ref, booking.journey_id, len(booking.events)), ('u-1', 'unknownREF123', None, 1))
        self.assertEqual(list(agenda_calcom.unmatched()), [booking])
        # Cancelled: it leaves the unmatched list; a late «created» does not revive it.
        cancel = delivery('BOOKING_CANCELLED')
        self.assertEqual(agenda_calcom.receive(cancel, sign(cancel), now)[1]['estado'], 'cancelada')
        late = delivery(endTime='2026-11-20T15:45:00Z')
        self.assertEqual(agenda_calcom.receive(late, sign(late), now)[1]['estado'], 'cancelada')
        self.assertEqual(list(agenda_calcom.unmatched()), [])

    def test_gustavos_note_gives_the_date(self):
        local = operador.local_tz()
        self.assertEqual(agenda_calcom.note_date('20/11/2026 10:30 por correo'), datetime(2026, 11, 20, 10, 30, tzinfo=local))
        self.assertEqual(agenda_calcom.note_date('el 20/11/2026'), datetime(2026, 11, 20, 9, 0, tzinfo=local))
        self.assertEqual(agenda_calcom.note_date('2026-11-20T10:30:00+00:00'), datetime(2026, 11, 20, 10, 30, tzinfo=utc_tz.utc))
        for text in ('', 'por LinkedIn', '31/02/2026'):
            self.assertIsNone(agenda_calcom.note_date(text), text)


class MeetingFoldTests(SimpleTestCase):
    """The fold with phase 6's touches: a meeting, its reschedule and its cancellation."""
    START = datetime(2026, 11, 17, 12, 0, tzinfo=utc_tz.utc)

    def touch(self, kind, at, key='', **detail):
        return SimpleNamespace(kind=kind, at=at, key=key, direction=comprador.DIRECTION[kind], detail=detail)

    def replied(self):
        s = self.START
        return [self.touch('elegido', s), self.touch('acepto_invitacion', s + HOUR), self.touch('mensaje', s + 2 * HOUR),
                self.touch('respondio_mensaje', s + DAY), self.touch('respuesta_clasificada', s + DAY, tipo='interesado'),
                self.touch('interesado', s + DAY)]

    def test_a_reschedule_moves_the_date_and_keeps_when_she_booked(self):
        s = self.START
        state = comprador._fold(self.replied() + [
            self.touch('reunion', s + 2 * DAY, reserva='b1', inicio=(s + 5 * DAY).isoformat()),
            self.touch('reunion', s + 3 * DAY, reserva='b2', inicio=(s + 8 * DAY).isoformat(), reemplaza='b1')])
        self.assertEqual((state.step(), state.meeting_date(), state.first['meeting'], state.reply_type),
                         ('reunion', s + 8 * DAY, s + 2 * DAY, 'interesado'))

    def test_a_cancellation_goes_back_to_interested_and_stops_counting(self):
        s = self.START
        booked = self.replied() + [self.touch('reunion', s + 2 * DAY, reserva='b1', inicio=(s + 5 * DAY).isoformat())]
        state = comprador._fold(booked + [self.touch('reunion_cancelada', s + 3 * DAY, reserva='b1')])
        self.assertEqual((state.step(), state.meeting_date(), 'meeting' in state.first), ('interesado', None, False))
        # Another booking after it counts from its own date.
        state = comprador._fold(booked + [self.touch('reunion_cancelada', s + 3 * DAY, reserva='b1'),
                                          self.touch('reunion', s + 4 * DAY, reserva='b3', inicio=(s + 9 * DAY).isoformat())])
        self.assertEqual((state.step(), state.meeting_date(), state.first['meeting']), ('reunion', s + 9 * DAY, s + 4 * DAY))
        # Cancelling a booking she does not have changes nothing.
        state = comprador._fold(booked + [self.touch('reunion_cancelada', s + 3 * DAY, reserva='other')])
        self.assertEqual((state.step(), state.first['meeting']), ('reunion', s + 2 * DAY))

    def test_her_reply_type_belongs_to_the_attempt(self):
        s = self.START
        state = comprador._fold(self.replied()[:5] + [
            self.touch('respuesta_clasificada', s + DAY, tipo='no_es_el_momento'),
            self.touch('descanso', s + DAY, motivo='no_es_el_momento', hasta=(s + 60 * DAY).isoformat()),
            self.touch('reintento', s + 60 * DAY, angulo='Lo que dijo', tipo='lo_que_dijo')])
        self.assertEqual((state.step(), state.reply_type, state.attempt), ('acepto', '', 2))


class WeeklyReadingTests(BuyerBase):
    """LI-12-M001-K04: the first stage under its threshold, its most probable cause and ONE change; under 30 invitations
    nothing is judged."""

    def journeys(self, n, **fields):
        made = []
        for i in range(n):
            _, journey = self.buyer(f'lect-{len(self.made)}', f'Lectura {len(self.made)}')
            self.made.append(journey)
            made.append(journey)
        BuyerJourney.objects.filter(pk__in=[j.pk for j in made]).update(**fields)
        return made

    def setUp(self):
        super().setUp()
        self.made = []
        self.now = timezone.now()

    def test_it_breaks_at_acceptance_first(self):
        week = self.now - 2 * DAY
        # Five accepted of 32 (15.6 %) and none of the five who replied booked: two stages break, the first one wins.
        self.journeys(5, invited_at=week, accepted_at=week, first_message_at=week, replied_at=week)
        self.journeys(27, invited_at=week)
        reading = lectura_embudo.read(self.now)
        self.assertEqual((reading['muestra_chica'], reading['invitaciones'], reading['se_rompe']), (False, 32, 'aceptacion'))
        self.assertEqual((reading['causa'], reading['cambio']), ('Lista equivocada o perfil que no convence', 'Afina la lista y tu perfil'))
        rows = {r['etapa']: r for r in reading['tabla']}
        self.assertEqual([r['etapa'] for r in reading['tabla'] if r['rota']], ['aceptacion', 'reunion'])
        row = rows['aceptacion']
        self.assertEqual((row['n'], row['de'], row['valor_pct'], row['umbral_pct'], row['fuente_umbral']), (5, 32, 15.6, 20, 'curso'))
        self.assertLessEqual(len(reading['lineas']), 5)
        self.assertIn('Se rompe primero en la aceptación', reading['lineas'][1])
        self.assertIn('Un solo cambio esta semana: afina la lista y tu perfil', reading['lineas'][2])

    def test_it_breaks_at_the_reply_when_acceptance_is_fine(self):
        week = self.now - 2 * DAY
        self.journeys(1, invited_at=week, accepted_at=week, first_message_at=week, replied_at=week)
        self.journeys(29, invited_at=week, accepted_at=week, first_message_at=week)
        self.journeys(2, invited_at=week)
        reading = lectura_embudo.read(self.now)
        self.assertEqual((reading['se_rompe'], reading['cambio']), ('respuesta', 'Reescribe solo el mensaje 1'))
        self.assertFalse(next(r for r in reading['tabla'] if r['etapa'] == 'aceptacion')['rota'])
        self.assertEqual(reading['semana_actual']['invitados'] + reading['semana_anterior']['invitados'], 32)

    def test_a_small_sample_is_not_judged(self):
        week = self.now - 2 * DAY
        self.journeys(5, invited_at=week)
        reading = lectura_embudo.read(self.now)
        self.assertEqual((reading['muestra_chica'], reading['se_rompe'], reading['causa'], reading['cambio']), (True, None, None, None))
        self.assertIn('Muestra chica: 5 invitaciones en total, menos de 30', reading['lineas'][1])
        self.assertTrue(next(r for r in reading['tabla'] if r['etapa'] == 'aceptacion')['rota'])  # the table still shows it

    def test_it_goes_to_slack_on_mondays_inside_the_window_once_a_week(self):
        self.journeys(3, invited_at=self.now - 2 * DAY)
        local = operador.local_tz()
        monday = datetime(2026, 11, 16, 10, 0, tzinfo=local)
        with patch.dict(os.environ, {'BUYER_REPLY_ENABLED': 'true', 'READ_WINDOW': '08:00-20:00'}):
            alerts = alertas_slack.lectura_semanal_embudo(monday)
            self.assertEqual([(a.key, a.once, a.channel) for a in alerts], [('comprador:lectura:2026-11-16', 'ever', 'resumen')])
            self.assertLessEqual(len(alerts[0].text().splitlines()), 5)
            self.assertEqual(alertas_slack.lectura_semanal_embudo(monday + DAY), [])
            self.assertEqual(alertas_slack.lectura_semanal_embudo(monday.replace(hour=6)), [])
        with patch.dict(os.environ, {'BUYER_REPLY_ENABLED': 'false'}):
            self.assertEqual(alertas_slack.lectura_semanal_embudo(monday), [])


class ReplyActivationTests(SimpleTestCase):
    """La activación es por metodología: solo sus seis unidades de las clases 08, 11 y 12, solo cuando se nombra, solo en
    sus roles."""

    def test_the_activated_list_is_the_case_and_the_graph_list(self):
        from knowledge.clases import CLASES_AGENTES, METODOLOGIAS_ACTIVAS, legible_por_agentes
        activa = METODOLOGIAS_ACTIVAS['respuesta_comprador']
        self.assertEqual(CLASES_AGENTES, tuple(range(1, 7)))
        self.assertEqual(list(activa['unidades']), operador.BUYER_REPLY_UNITS)
        self.assertEqual((activa['evaluacion'], activa['lista']), (CASE['id'], 'operador.BUYER_REPLY_UNITS'))
        self.assertEqual(CASE['units'], operador.BUYER_REPLY_UNITS)
        self.assertEqual(set(CASE['required']), set(CASE['units']))
        self.assertEqual(activa['roles'], ('relaciones_comunidad', 'lider_jev'))
        for uid in operador.BUYER_REPLY_UNITS:
            self.assertTrue(legible_por_agentes(uid, 'respuesta_comprador'))
            self.assertFalse(legible_por_agentes(uid))
            self.assertFalse(legible_por_agentes(uid, 'secuencia_mensajes'))
        # LI-09-V004-K02 is not adopted; the rest of classes 08, 11 and 12 and the sequence's units stay closed.
        for uid in ('LI-09-V004-K02', 'LI-11-M006-K04', 'LI-11-M006-K05', 'LI-12-M001-K03', 'LI-12-M004-K01', 'LI-09-M003-K05'):
            self.assertFalse(legible_por_agentes(uid, 'respuesta_comprador'), uid)
        from team_backend.orquestacion import load_graph
        graph = load_graph()
        self.assertEqual(graph['course_lists']['operador.BUYER_REPLY_UNITS'], operador.BUYER_REPLY_UNITS)
        self.assertEqual([n['id'] for n in graph['nodes'] if 'operador.BUYER_REPLY_UNITS' in n['course_lists']],
                         ['relaciones_comunidad', 'lider_jev'])


class ReplyReadingRegistryTests(SimpleTestCase):
    """El registro de lectura nombra exactamente las unidades activadas, con su hash, puntero y fuentes; las decisiones de
    Gustavo que ganan al curso (la reserva manda sobre el «sí») y lo que no se convirtió en regla."""

    def test_the_reading_registry_matches_the_activation(self):
        from pathlib import Path
        from knowledge.clases import METODOLOGIAS_ACTIVAS
        activa = METODOLOGIAS_ACTIVAS['respuesta_comprador']
        self.assertEqual(activa['registro'], 'relaciones/registro-lectura-respuesta-comprador.json')
        path = Path(operador.__file__).resolve().parents[3] / 'equipos' / activa['registro']
        if not path.exists():
            self.skipTest('La imagen solo empaqueta grafo.yaml; el registro vive en equipos/relaciones.')
        registry = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual((registry['metodologia'], registry['evaluacion'], registry['lista']),
                         ('respuesta_comprador', activa['evaluacion'], activa['lista']))
        self.assertEqual(tuple(registry['roles']), activa['roles'])
        self.assertEqual([u['unidad_id'] for u in registry['unidades']], operador.BUYER_REPLY_UNITS)
        self.assertEqual(registry['alcance']['por_clase'], {'08': 1, '11': 4, '12': 1})
        for unit in registry['unidades']:
            prefix = unit['unidad_id'][3:5]
            self.assertEqual(unit['clase'], int(prefix))
            self.assertTrue(unit['lectura_completa'])
            self.assertRegex(unit['hash'], r'^[0-9a-f]{64}$')
            self.assertRegex(unit['pointer'], r'^/learning_units/\d+$')
            self.assertTrue(unit['criterio_derivado'] and unit['limites_y_excepciones'] and unit['uso'])
            self.assertTrue(unit['fuentes_con_prefijo_de_clase'])
            self.assertTrue(all(key.startswith(prefix + ':') for key in unit['fuentes_con_prefijo_de_clase']))
        decisions = ' '.join(registry['decisiones_vigentes_que_ganan'])
        self.assertIn('REUNIÓN AGENDADA', decisions)
        self.assertIn('Cal.com', decisions)
        self.assertIn('«sí»', decisions)
        not_adopted = ' '.join(registry['no_convertido_en_regla'])
        for item in ('envío automático', 'CRM', 'calificación', 'LI-09-V004-K02'):
            self.assertIn(item, not_adopted)
