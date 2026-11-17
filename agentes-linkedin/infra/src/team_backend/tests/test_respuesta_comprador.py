"""BIB-11-respuesta-comprador: la respuesta del comprador, la reunión agendada y la entrega del lead (clase 11, con la
clase 08 y la tabla de diagnóstico de la clase 12; fase 6 de docs/plan-outbound.md), medidas con las funciones de
producción.

Cada persona recorre el camino real hasta el «Hecho, le escribí» del primer mensaje (fase 3); después responde y un reloj
simulado avanza: la lectura del inbox (el conector simulado es LinkedIn: lo que Gustavo envía a mano y lo que ella
responde), el paso de borradores del autopiloto con sus jobs, Tu turno y los cierres de Gustavo, el webhook firmado de
Cal.com (lo publica el cliente de pruebas) y la entrega. Claude y Jev simulados (test_comprador_e2e.judge_reply_type y
judge_reply_draft); unidades del curso sintéticas, sin red, sin Cal.com ni proveedores pagados. El equipo nunca envía un
mensaje: las respuestas son borradores que Gustavo copia y envía (INB-08)."""
import json
import os
from datetime import date, timedelta
from unittest import expectedFailure
from unittest.mock import patch

from django.test import SimpleTestCase
from team_backend import evaluaciones, operador
from team_backend.models import AuditEvent, BuyerDraft, Contact
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

    @expectedFailure  # Línea base: nadie clasifica su respuesta, ni redacta, ni agenda, ni entrega el lead (fase 6)
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

    @expectedFailure  # Línea base: no hay reglas fijas de la respuesta (respuesta_comprador.text_issues)
    def test_the_case_replies(self):
        from team_backend import respuesta_comprador
        with patch('team_backend.guardas.blocks', return_value=([], [])):
            for variant, kind in (('flujo', 'interesado'), ('P', 'pide_informacion'), ('N1', 'no_es_el_momento'),
                                  ('X', 'no_le_interesa'), ('O', 'otra_persona')):
                self.assertEqual(respuesta_comprador.text_issues(kind, reply_input(variant, 'borrador'), reply_input(variant)), [], variant)


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
