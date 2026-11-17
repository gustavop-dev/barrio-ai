"""BIB-09-secuencia-mensajes: los mensajes 2 a 4 del comprador después del primero (clase 09, con las reglas de detención
de la clase 10; fase 4 de docs/plan-outbound.md), medidos con las funciones de producción.

Cada persona recorre el camino real hasta el «Hecho, le escribí» del primer mensaje (fase 3) y después el reloj simulado
avanza: la lectura del inbox (el conector simulado es LinkedIn: lo que Gustavo envía a mano y lo que ella responde), el
paso de borradores del autopiloto con sus jobs, Tu turno y los cierres de Gustavo. Claude y Jev simulados
(test_comprador_e2e.judge_sequence); unidades del curso sintéticas, sin red ni proveedores pagados. El equipo nunca
envía un mensaje: los seguimientos son borradores que Gustavo copia y envía (INB-08)."""
import json
import os
from datetime import timedelta
from unittest import expectedFailure
from unittest.mock import patch

from django.test import SimpleTestCase
from team_backend import evaluaciones, operador
from team_backend.models import AuditEvent
from team_backend.tests.test_comprador_e2e import SequencePathBase, case_text, sequence_text

CASE = evaluaciones.COURSE_CASES['secuencia_mensajes']
MINUTE = timedelta(minutes=1)
DAYS = dict(zip((2, 3, 4), CASE['input']['flujo']['dias']))
PEOPLE = {'flujo': ('seq-ana', 'Ana Flujo'), 'S2': ('seq-bea', 'Bea Responde'), 'S3': ('seq-cris', 'Cris Espera'),
          'S5': ('seq-dani', 'Dani Repite'), 'S6': ('seq-eva', 'Eva Disculpa'), 'S7': ('seq-fer', 'Fer Sinpersona'),
          'S8': ('seq-gil', 'Gil Pide'), 'S9': ('seq-hugo', 'Hugo Juez'), 'S10': ('seq-ines', 'Ines Noescribir')}
STOPPED_AT = {'S5': 2, 'S6': 2, 'S7': 3, 'S8': 4, 'S9': 3}  # the follow-up each rule variant stops


class SequenceCaseBase(SequencePathBase):
    def run_case(self):
        """Every variant with the production functions, graded with grade_course_case."""
        people = {}
        for variant, (slug, name) in PEOPLE.items():
            people[variant] = self.messaged(slug, name)
            self.follow_ups(people[variant], variant)
        start, writes = self.start, self.fake.state['writes']
        result = {'flujo_antes_de_tiempo': False, 'flujo_dias': []}
        everyone = lambda: sorted({n for c in people.values() for n in self.numbers(c)})

        # Message 2, due 4 days after the first «Hecho». One minute before: nothing.
        self.cycle(start + timedelta(days=DAYS[2]) - MINUTE)
        result['flujo_antes_de_tiempo'] |= bool(everyone())
        # S11: the switch off; S4: the inbox off (the sequence never assumes «she did not answer»).
        with patch.dict(os.environ, {'BUYER_SEQUENCE_ENABLED': 'false'}):
            self.cycle(start + timedelta(days=DAYS[2]) + MINUTE)
        result['S11_numeros'] = everyone()
        with patch.dict(os.environ, {'INBOX_ENABLED': 'false'}):
            self.cycle(start + timedelta(days=DAYS[2]) + 2 * MINUTE)
        result['S4_numeros'] = everyone()
        result['S4_aviso'] = AuditEvent.objects.filter(action='buyer.sequence_waiting').exists()
        due2 = self.cycle(start + timedelta(days=DAYS[2]) + 3 * MINUTE)
        if self.numbers(people['flujo']) == [2]:
            result['flujo_dias'].append(round((due2 - start) / timedelta(days=1)))

        # Gustavo sends message 2 an hour later, everywhere except S3 (he never does) and the ones the rules stopped.
        sent2 = due2 + timedelta(hours=1)
        for variant in ('flujo', 'S2', 'S7', 'S8', 'S9', 'S10'):
            cards = self.sequence_cards(people[variant], sent2)
            if cards:
                self.close_at(cards[0], 'enviado', sent2)

        # Message 3, due 5 days after the «Hecho» of message 2.
        self.cycle(sent2 + timedelta(days=DAYS[3]) - MINUTE)
        result['flujo_antes_de_tiempo'] |= any(n > 2 for n in everyone())
        due3 = self.cycle(sent2 + timedelta(days=DAYS[3]) + MINUTE)
        if self.numbers(people['flujo']) == [2, 3]:
            result['flujo_dias'].append(round((due3 - sent2) / timedelta(days=1)))
        # S2: she answers while message 3 waits in Tu turno.
        bea = people['S2']
        self.she_replies(bea, CASE['input']['S2']['respuesta'], due3 + timedelta(hours=2))
        self.cycle(due3 + timedelta(hours=3))
        # S10: «No escribirle» on message 3.
        cards = self.sequence_cards(people['S10'], due3 + timedelta(hours=1))
        if cards:
            self.close_at(cards[0], 'no', due3 + timedelta(hours=1), note='Prefiero no insistir.')
        # Message 3 sent: S8 an hour after its card; the flow a day later (the deadline runs from «Hecho», not the draft).
        sent3 = {'S8': due3 + timedelta(hours=1), 'flujo': due3 + timedelta(days=1)}
        for variant, at in sent3.items():
            cards = self.sequence_cards(people[variant], at)
            if cards:
                self.close_at(cards[0], 'enviado', at)

        # Message 4, due 7 days after the «Hecho» of message 3.
        self.cycle(sent3['S8'] + timedelta(days=DAYS[4]) + MINUTE)
        self.cycle(sent3['flujo'] + timedelta(days=DAYS[4]) - MINUTE)
        result['flujo_antes_de_tiempo'] |= 4 in self.numbers(people['flujo'])
        due4 = self.cycle(sent3['flujo'] + timedelta(days=DAYS[4]) + MINUTE)
        if self.numbers(people['flujo']) == [2, 3, 4]:
            result['flujo_dias'].append(round((due4 - sent3['flujo']) / timedelta(days=1)))
        sent4 = due4 + timedelta(hours=1)
        cards = self.sequence_cards(people['flujo'], sent4)
        if cards:
            self.close_at(cards[0], 'enviado', sent4)

        # No reply after message 4: she rests (BUYER_SEQUENCE_REST_AFTER_DAYS, 7) for 90 days.
        rest = self.cycle(sent4 + timedelta(days=7) + MINUTE)
        ana = self.journey(people['flujo'])
        result['flujo_descanso'] = ana.rest_reason or None
        result['flujo_descanso_dias'] = round((ana.rest_until - rest) / timedelta(days=1)) if ana.rest_until else None
        result['flujo_numeros'] = self.numbers(people['flujo'])

        # The rest of the variants, read at the end.
        bea_journey = self.journey(bea)
        result['S2_paso'] = bea_journey.step
        result['S2_numeros'] = self.numbers(bea)
        result['S2_cancelados'] = sorted(d.number for d in self.drafts_of(bea, 'mensaje') if d.state == 'cancelado')
        replied = (self.funnel().get('secuencia') or {}).get('respondieron_tras') or {}
        result['S2_respondio_tras'] = next((int(n) for n, count in replied.items() if count), None)
        result['S3_numeros'] = self.numbers(people['S3'])
        for variant, number in STOPPED_AT.items():
            draft = self.draft(people[variant], number)
            result[f'{variant}_stopped_by'] = draft.stopped_by if draft else None
        later = rest + timedelta(hours=1)
        result['tarjetas_paradas'] = sum(len(self.sequence_cards(people[v], later)) for v in STOPPED_AT)
        result['S10_salida'] = self.journey(people['S10']).exit_reason or None
        result['S10_numeros'] = self.numbers(people['S10'])
        result['mensajes_enviados'] = self.fake.state['writes'] - writes
        result['borrador_con_metodologia'] = any('LI-09-M003-K05' in c['context'] for c in self.calls if c['purpose'] == 'buyer-sequence')
        drafts = [d for d in self.drafts_of(people['flujo'], 'mensaje') if d.number > 1]
        grounding = (drafts[-1].review or {}) if drafts else {}
        result['course_citations'] = grounding.get('course_citations', [])
        return evaluaciones.grade_course_case('secuencia_mensajes', result, grounding), result


class SequenceCaseTests(SequenceCaseBase):
    """El caso completo. Línea base: docs/linea-base-secuencia-mensajes.md."""

    @expectedFailure  # Línea base: nadie prepara los mensajes 2 a 4 ni detiene, descansa o avisa (fase 4)
    def test_the_case_passes_with_production_functions(self):
        grade, result = self.run_case()
        self.assertTrue(grade['passed'], (grade['errors'], result))

    def test_the_case_loads_whole_versioned_sources_and_rejects_wrong_behaviour(self):
        context, grounding = evaluaciones.course_case_context('secuencia_mensajes')
        self.assertEqual(grounding['course_missing'], [])
        result = dict(CASE['expected'], course_citations=CASE['required'])
        self.assertTrue(evaluaciones.grade_course_case('secuencia_mensajes', result, grounding)['passed'])
        for wrong in ({'flujo_dias': [4, 4, 4]}, {'S2_numeros': [2, 3, 4]}, {'S4_numeros': [2]}, {'mensajes_enviados': 1},
                      {'course_citations': CASE['required'] + ['LI-09-M003-K02']}):
            self.assertFalse(evaluaciones.grade_course_case('secuencia_mensajes', dict(result, **wrong), grounding)['passed'], wrong)


class SequenceRulesTests(SimpleTestCase):
    """Las reglas fijas de cada seguimiento, además de las del primer mensaje (sin enlaces, sin pedir una reunión, sin
    fórmulas): el M2 no repite el M1 ni se disculpa; el M3 pregunta por la persona indicada; el M4 no pide nada."""
    M1 = case_text('primer_mensaje_comprador', 'M1')
    REFERENCE = 'Honestly, the spreadsheet solved a real reporting pain. Now we need it to scale without hiring ten people.'

    def issues(self, number, text):
        from team_backend import secuencia_comprador
        return secuencia_comprador.text_issues(number, text, previous=self.M1, reference=self.REFERENCE)

    @expectedFailure  # Línea base: no hay reglas fijas por número de seguimiento (secuencia_comprador.text_issues)
    def test_the_case_follow_ups(self):
        for number in (2, 3, 4):
            self.assertEqual(self.issues(number, sequence_text('flujo', number)), [], number)
        self.assertEqual(self.issues(3, sequence_text('S9', 3)), [])  # passes the rules: the lead stops it
        for variant, number in (('S5', 2), ('S6', 2), ('S7', 3), ('S8', 4)):
            self.assertTrue(self.issues(number, sequence_text(variant, number)), variant)


class SequenceActivationTests(SimpleTestCase):
    """La activación es por metodología: solo sus seis unidades de las clases 09 y 10, solo cuando se nombra, solo en sus
    roles."""

    def test_the_activated_list_is_the_case_and_the_graph_list(self):
        from knowledge.clases import CLASES_AGENTES, METODOLOGIAS_ACTIVAS, legible_por_agentes
        activa = METODOLOGIAS_ACTIVAS['secuencia_mensajes']
        self.assertEqual(CLASES_AGENTES, tuple(range(1, 7)))
        self.assertEqual(list(activa['unidades']), operador.SEQUENCE_UNITS)
        self.assertEqual((activa['evaluacion'], activa['lista']), (CASE['id'], 'operador.SEQUENCE_UNITS'))
        self.assertEqual(CASE['units'], operador.SEQUENCE_UNITS)
        self.assertLessEqual(set(CASE['required']), set(CASE['units']))
        self.assertEqual(activa['roles'], ('relaciones_comunidad', 'lider_jev'))
        for uid in operador.SEQUENCE_UNITS:
            self.assertTrue(legible_por_agentes(uid, 'secuencia_mensajes'))
            self.assertFalse(legible_por_agentes(uid))
            self.assertFalse(legible_por_agentes(uid, 'primer_mensaje'))
        # The first message's and the note's units stay closed to the sequence, and the rest of classes 09–10 too.
        for uid in ('LI-09-M003-K02', 'LI-09-M002-K06', 'LI-09-M003-K06', 'LI-10-V013-K01'):
            self.assertFalse(legible_por_agentes(uid, 'secuencia_mensajes'), uid)
        from team_backend.orquestacion import load_graph
        graph = load_graph()
        self.assertEqual(graph['course_lists']['operador.SEQUENCE_UNITS'], operador.SEQUENCE_UNITS)
        self.assertEqual([n['id'] for n in graph['nodes'] if 'operador.SEQUENCE_UNITS' in n['course_lists']],
                         ['relaciones_comunidad', 'lider_jev'])


class SequenceReadingRegistryTests(SimpleTestCase):
    """El registro de lectura nombra exactamente las unidades activadas, con su hash, puntero y fuentes; las decisiones de
    Gustavo que ganan al curso y lo que no se convirtió en regla."""

    def test_the_reading_registry_matches_the_activation(self):
        from pathlib import Path
        from knowledge.clases import METODOLOGIAS_ACTIVAS
        activa = METODOLOGIAS_ACTIVAS['secuencia_mensajes']
        self.assertEqual(activa['registro'], 'relaciones/registro-lectura-secuencia-mensajes.json')
        path = Path(operador.__file__).resolve().parents[3] / 'equipos' / activa['registro']
        if not path.exists():
            self.skipTest('La imagen solo empaqueta grafo.yaml; el registro vive en equipos/relaciones.')
        registry = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual((registry['metodologia'], registry['evaluacion'], registry['lista']),
                         ('secuencia_mensajes', activa['evaluacion'], activa['lista']))
        self.assertEqual(tuple(registry['roles']), activa['roles'])
        self.assertEqual([u['unidad_id'] for u in registry['unidades']], operador.SEQUENCE_UNITS)
        self.assertEqual(registry['alcance']['por_clase'], {'09': 4, '10': 2})
        for unit in registry['unidades']:
            prefix = unit['unidad_id'][3:5]
            self.assertEqual(unit['clase'], int(prefix))
            self.assertTrue(unit['lectura_completa'])
            self.assertRegex(unit['hash'], r'^[0-9a-f]{64}$')
            self.assertRegex(unit['pointer'], r'^/learning_units/\d+$')
            self.assertTrue(unit['criterio_derivado'] and unit['limites_y_excepciones'] and unit['uso'])
            self.assertTrue(unit['fuentes_con_prefijo_de_clase'])
            self.assertTrue(all(key.startswith(prefix + ':') for key in unit['fuentes_con_prefijo_de_clase']))
        self.assertTrue(any('Gustavo' in d and 'borradores' in d for d in registry['decisiones_vigentes_que_ganan']))
        self.assertTrue(any('email' in item for item in registry['no_convertido_en_regla']))
