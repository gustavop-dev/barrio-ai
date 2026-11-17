"""BIB-09-primer-mensaje-comprador: el primer mensaje a un comprador calentado que acepta la invitación (clase 09, fase 3
de docs/plan-outbound.md), medido con las funciones de producción. Caso hermano de BIB-09-primer-mensaje, con la misma
metodología activada (primer_mensaje).

Cada variante recorre el camino real: elegido y seguido, su post leído y comentado por el autopiloto (Claude y Jev
simulados), su respuesta o un segundo comentario, la invitación que Gustavo aprueba, la aceptación que lee sync_network,
el paso de borradores del autopiloto y Tu turno. Unidades del curso sintéticas, sin red ni proveedores pagados.

El Jev simulado es un juez por rasgos del texto (test_comprador_e2e.judge_message), no una tabla de respuestas."""
from datetime import timedelta
from unittest import expectedFailure
from unittest.mock import patch

from django.utils import timezone
from team_backend import evaluaciones
from team_backend.models import ActionProposal, Contact, PostComment
from team_backend.tests.test_comprador_e2e import AFTER_POST, WARM_3, FirstMessagePathBase
from team_backend.tests.test_respuestas import CLOSING, FOLLOW_UP, QUESTION, draft

CASE = evaluaciones.COURSE_CASES['primer_mensaje_comprador']
PEOPLE = {'M1': ('pm-mara', 'Mara Uno'), 'M2': ('pm-nico', 'Nico Dos'), 'M3': ('pm-olga', 'Olga Tres'),
          'M4': ('pm-paco', 'Paco Cuatro'), 'M5': ('pm-rita', 'Rita Cinco')}
LATER = timedelta(hours=2)  # Tu turno read two hours after the acceptance: the card never shows the same minute


def message(variant):
    return CASE['input'][variant]['mensaje']


class FirstMessageCaseBase(FirstMessagePathBase):
    def write(self, variant):
        self.texts[('buyer-message', PEOPLE[variant][1])] = message(variant)

    def answered_and_accepted(self, variant):
        """M1, M4, M5: she answered a warm-up comment (an interaction), was invited and accepted."""
        contact = self.answered(*PEOPLE[variant])
        self.write(variant)
        self.assertEqual(self.invite(contact).state, 'confirmed')
        return self.accepted(contact)

    def outcome(self, contact, later=LATER):
        drafts = self.drafts_of(contact, 'mensaje')
        cards = self.cards_of(contact, later)
        return {'borrador': drafts[-1] if drafts else None, 'tarjetas': cards, 'stopped_by': self.stopped(contact, 'mensaje'),
                'pagado': self.paid(contact, 'buyer-message')}

    # -- the variants
    def m1(self):
        contact = self.answered_and_accepted('M1')
        self.prepare()  # the same cycle that saw the acceptance
        same_cycle = bool(self.drafts_of(contact, 'mensaje'))
        run = self.outcome(contact)
        anchor = (run['borrador'].anchor or {}) if run['borrador'] else {}
        return dict(run, contact=contact, mismo_ciclo=same_cycle, cita=anchor.get('tipo'))

    def m2(self):
        contact, second = self.two_comments(*PEOPLE['M2'])
        self.write('M2')
        self.assertEqual(self.invite(contact).state, 'confirmed')
        contact = self.accepted(contact)
        accepted = self.journey(contact).accepted_at
        self.prepare()
        early = bool(self.drafts_of(contact, 'mensaje')) or bool(self.cards_of(contact, LATER))
        # One more touch after she accepted: a comment on a new post of hers (calentamiento 2).
        self.their_new_post(contact, AFTER_POST, suffix='p3', hours_ago=1)
        self.observe(later=True)
        self.a_day_later(second)
        third = self.autopilot_comment(WARM_3)
        touched = self.journey(contact).touches.filter(kind='comentario', at__gt=accepted).exists()
        at = accepted + timedelta(days=7, minutes=1)
        self.prepare(at)
        run = self.outcome(contact, at - timezone.now() + LATER)
        return dict(run, contact=contact, antes_de_tiempo=early, toque=touched, tercero=third)

    def m3(self):
        contact, at = self.without_posts(*PEOPLE['M3'])
        # The drafter would write if asked: what is measured is that nobody asks.
        self.texts[('buyer-message', PEOPLE['M3'][1])] = CASE['input']['M2']['mensaje']
        self.assertEqual(self.invite(contact, at).state, 'confirmed')
        contact = self.accepted(contact)
        later = self.journey(contact).accepted_at + timedelta(days=21, minutes=1)
        self.prepare(later)
        return dict(self.outcome(contact, later - timezone.now() + LATER), contact=contact)

    def m4(self):
        contact = self.answered_and_accepted('M4')
        self.prepare()
        return dict(self.outcome(contact), contact=contact)

    def m5(self):
        contact = self.answered_and_accepted('M5')
        self.prepare()
        return dict(self.outcome(contact), contact=contact)

    def m6(self):
        """She talked with him on his post (two public replies and the drafted message, RSP-07), is a buyer the team
        follows, was invited and accepted: one card, the conversation's."""
        _, pid = self.publish()
        sara = self.fake.seed_person('pm-sara', 'Sara Seis', headline='Founder & CEO at Seis', location='Austin, Texas')
        root = self.fake.comment_on_own_post(pid, sara['id'], QUESTION, at=timezone.now() - timedelta(minutes=20))
        self.read()
        first = PostComment.objects.get()
        self.propose(first, draft())
        self.execute_proposal(ActionProposal.objects.get(capability='INT-04'))
        contact = Contact.objects.get(pk=first.contact_id)
        checked = {'state': 'ok', 'checked_at': timezone.now().isoformat()}  # the web saw her seed round
        Contact.objects.filter(pk=contact.pk).update(classification={'fit': True, 'role': 'comprador', 'confidence': 0.9,
                                                                     'region': 'us', 'stage_check': checked},
                                                     stage='followed', followed_at=timezone.now() - timedelta(hours=1),
                                                     location='Austin, Texas')
        self.fake.comment_on_own_post(pid, sara['id'], FOLLOW_UP, thread=root, at=timezone.now() + timedelta(seconds=5))
        self.rescan()  # her second comment: the hook brings her journey up to date (followed, two comments)
        second = PostComment.objects.get(text=FOLLOW_UP)
        opener = 'Hi Sara, I kept thinking about your golden datasets going stale. How are you versioning them now?'
        self.propose(second, draft(reply=CLOSING, dm_opener=opener))
        with self.lead():
            self.execute_proposal(ActionProposal.objects.get(capability='INT-04', comment=second))
        contact = Contact.objects.get(pk=contact.pk)
        self.assertEqual(self.invite(contact).state, 'confirmed')  # commented his post: invited without the warm-up
        contact = self.accepted(contact)
        self.texts[('buyer-message', contact.display_name)] = message('M1')
        self.prepare()
        cards = self.cards_of(contact, LATER)
        origin = [('recorrido' if (c['message'] or {}).get('origin') == 'recorrido' else 'conversacion') for c in cards]
        return {'contact': contact, 'tarjetas': cards, 'origen': origin[0] if len(origin) == 1 else origin}


class FirstMessageCaseTests(FirstMessageCaseBase):
    """Las variantes de BIB-09-primer-mensaje-comprador. Línea base: docs/linea-base-primer-mensaje-comprador.md."""

    # Línea base: nadie prepara un mensaje al aceptar (solo RSP-07 tras una conversación en su post).
    @expectedFailure
    def test_m1_she_interacted_the_draft_is_prepared_in_the_same_cycle_and_cites_it(self):
        run = self.m1()
        self.assertTrue(run['mismo_ciclo'])
        self.assertEqual(len(run['tarjetas']), 1)
        self.assertEqual(run['tarjetas'][0]['message']['text'], message('M1'))
        self.assertEqual(run['cita'], 'respondio_comentario')
        self.assertEqual(self.messages_sent(), 0)

    # Línea base: sin borrador al aceptar no hay tarjeta.
    @expectedFailure
    def test_m1_the_card_never_shows_the_same_minute(self):
        run = self.m1()
        self.assertEqual(self.cards_of(run['contact']), [])
        self.assertEqual(len(self.cards_of(run['contact'], LATER)), 1)

    # Línea base: nadie redacta el mensaje del recorrido: no hay llamada que cargue las unidades.
    @expectedFailure
    def test_m1_the_draft_loads_the_first_message_units(self):
        self.m1()
        context = next(c['context'] for c in self.calls if c['purpose'] == 'buyer-message')
        for uid in CASE['units']:
            self.assertIn(uid, context)

    # Línea base: después de aceptar nadie lee ni comenta sus posts, y no hay borrador a los N días.
    @expectedFailure
    def test_m2_without_interaction_a_touch_first_and_the_draft_n_days_after(self):
        run = self.m2()
        self.assertFalse(run['antes_de_tiempo'])
        self.assertTrue(run['toque'])
        self.assertEqual(len(run['tarjetas']), 1)

    # Línea base: no hay motivo registrado («hecho») porque nadie lo evalúa.
    @expectedFailure
    def test_m3_nothing_real_to_cite_no_message_and_no_paid_call(self):
        run = self.m3()
        self.assertEqual(run['tarjetas'], [])
        self.assertEqual(run['stopped_by'], 'hecho')
        self.assertFalse(run['pagado'])

    # Línea base: sin borrador no hay reglas que lo paren.
    @expectedFailure
    def test_m4_a_draft_breaking_a_fixed_rule_after_the_redraft_shows_no_card(self):
        run = self.m4()
        self.assertEqual((run['tarjetas'], run['stopped_by']), ([], 'reglas'))

    # Línea base: sin borrador no hay líder que lo pare.
    @expectedFailure
    def test_m5_a_draft_the_lead_rejects_shows_no_card(self):
        run = self.m5()
        self.assertEqual((run['tarjetas'], run['stopped_by']), ([], 'juez'))

    def test_m6_a_conversation_on_his_post_and_a_journey_one_card(self):
        run = self.m6()
        self.assertEqual((len(run['tarjetas']), run['origen']), (1, 'conversacion'))

    def run_case(self):
        """Todas las variantes con las funciones de producción, calificadas con grade_course_case."""
        runs = {'M1': self.m1(), 'M2': self.m2(), 'M3': self.m3(), 'M4': self.m4(), 'M5': self.m5(), 'M6': self.m6()}
        result = {'borrador_con_metodologia': any('LI-09-M003-K02' in c['context'] for c in self.calls if c['purpose'] == 'buyer-message'),
                  'M1_mismo_ciclo': runs['M1']['mismo_ciclo'], 'M1_tarjeta': len(runs['M1']['tarjetas']) == 1,
                  'M1_cita': runs['M1']['cita'], 'M2_antes_de_tiempo': runs['M2']['antes_de_tiempo'], 'M2_toque': runs['M2']['toque'],
                  'M2_tarjeta': len(runs['M2']['tarjetas']) == 1, 'M3_tarjeta': bool(runs['M3']['tarjetas']),
                  'M3_stopped_by': runs['M3']['stopped_by'], 'M3_pagado': runs['M3']['pagado'],
                  'M4_tarjeta': bool(runs['M4']['tarjetas']), 'M4_stopped_by': runs['M4']['stopped_by'],
                  'M5_tarjeta': bool(runs['M5']['tarjetas']), 'M5_stopped_by': runs['M5']['stopped_by'],
                  'M6_tarjetas': len(runs['M6']['tarjetas']), 'M6_origen': runs['M6']['origen'], 'mensajes_enviados': self.messages_sent()}
        grounding = (runs['M1']['borrador'].review or {}) if runs['M1']['borrador'] else {}
        result['course_citations'] = grounding.get('course_citations', [])
        return evaluaciones.grade_course_case('primer_mensaje_comprador', result, grounding), result

    # Línea base: el caso completo no pasa (docs/linea-base-primer-mensaje-comprador.md).
    @expectedFailure
    def test_the_case_passes_with_production_functions(self):
        grade, result = self.run_case()
        self.assertTrue(grade['passed'], (grade['errors'], result))

    def test_the_case_loads_whole_versioned_sources_and_rejects_wrong_behaviour(self):
        context, grounding = evaluaciones.course_case_context('primer_mensaje_comprador')
        self.assertEqual(grounding['course_missing'], [])
        self.assertEqual(grounding['course_methodology'], 'primer_mensaje')
        result = dict(CASE['expected'], course_citations=CASE['required'])
        self.assertTrue(evaluaciones.grade_course_case('primer_mensaje_comprador', result, grounding)['passed'])
        self.assertFalse(evaluaciones.grade_course_case('primer_mensaje_comprador', dict(result, M3_pagado=True), grounding)['passed'])
        self.assertFalse(evaluaciones.grade_course_case('primer_mensaje_comprador', dict(result, mensajes_enviados=1), grounding)['passed'])
        # A unit of class 09 outside the activated list is still not readable.
        self.assertFalse(evaluaciones.grade_course_case('primer_mensaje_comprador', dict(result, course_citations=CASE['required'] + ['LI-09-M002-K06']),
                                                        grounding)['passed'])


class FirstMessageSwitchOffTests(FirstMessageCaseBase):
    def test_with_the_switch_off_nothing_is_prepared_and_rsp07_is_intact(self):
        with patch.dict('os.environ', {'BUYER_FIRST_MESSAGE_ENABLED': 'false'}):
            run = self.m1()
            self.assertEqual((run['mismo_ciclo'], run['tarjetas'], run['pagado']), (False, [], False))
            m6 = self.m6()
            self.assertEqual((len(m6['tarjetas']), m6['origen']), (1, 'conversacion'))
