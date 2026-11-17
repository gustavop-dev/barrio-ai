"""BIB-09-nota-invitacion: la nota de invitación, reservada a compradores calentados con un hecho concreto y redactada al
invitar (clase 09, fase 3 de docs/plan-outbound.md), medida con las funciones de producción.

Cada variante recorre el camino real: elegido y seguido, un comentario del autopiloto en su post y su respuesta (Claude y
Jev simulados), el paso de borradores del autopiloto, el plan de red, la compuerta autónoma de RED-02 con el líder y el
envío. Unidades del curso sintéticas, sin red ni proveedores pagados. El Jev simulado es un juez por rasgos del texto
(test_comprador_e2e.judge_note).

También reproduce el error que la fase 3 corrige: una invitación con nota a una persona que Gustavo confirmó (o con el
líder apagado) quedaba bloqueada hasta caducar, porque nadie marcaba la nota como aprobada."""
import os
from unittest import expectedFailure
from unittest.mock import patch

from django.test import SimpleTestCase
from team_backend import evaluaciones, operador, red
from team_backend.models import ActionProposal, AuditEvent
from team_backend.tests.test_comprador_e2e import FirstMessagePathBase

CASE = evaluaciones.COURSE_CASES['nota_invitacion']
WRITTEN = ('N1', 'N2', 'N3', 'N4', 'N5', 'N6', 'N7')
PEOPLE = {'N1': ('nota-ines', 'Ines Uno'), 'N2': ('nota-juan', 'Juan Dos'), 'N3': ('nota-kira', 'Kira Tres'),
          'N4': ('nota-leo', 'Leo Cuatro'), 'N5': ('nota-mia', 'Mia Cinco'), 'N6': ('nota-noa', 'Noa Seis'),
          'N7': ('nota-omar', 'Omar Siete'), 'N8': ('nota-pia', 'Pia Ocho'), 'N9': ('nota-quim', 'Quim Nueve'),
          'G': ('nota-rosa', 'Rosa Gustavo')}
# Today's only notes come from the classifier (red.plan): G carries one, to reproduce the blocked invitation.
CLASSIFIER_NOTE = 'Ana, your answer on the spreadsheet pilot stayed with me. Would love to connect.'


def note(variant):
    return CASE['input'][variant]['nota']


class NoteCaseBase(FirstMessagePathBase):
    def setUp(self):
        super().setUp()
        # Ten buyers read in one day (the production cap is 8: a test of the case, not of the read cap).
        env = patch.dict(os.environ, {'BUYER_POSTS_READ_DAILY_LIMIT': '20'})
        env.start()
        self.addCleanup(env.stop)

    def run_variant(self, variant, send=True):
        """The variant's buyer up to the invitation. `send`: the gate approves it and the operator sends it; otherwise
        it is measured as proposed and Gustavo vetoes it, so the day's ramp keeps room for the next one."""
        slug, name = PEOPLE[variant]
        env = {'LINKEDIN_INVITE_NOTE_MONTHLY_LIMIT': '0'} if variant == 'N9' else {}
        with patch.dict(os.environ, env):
            if variant == 'N8':
                contact, at = self.without_posts(slug, name)
                self.texts[('invite-note', name)] = note('N1')
                self.prepare(at)
                self.plan(at)
            else:
                contact = self.answered(slug, name, note=CLASSIFIER_NOTE if variant == 'G' else '')
                if variant == 'G':
                    red.confirm_fit(self.gustavo, contact.pk)
                self.texts[('invite-note', name)] = note(variant if variant in WRITTEN else 'N1')
                self.prepare()
                self.plan()
            proposal = ActionProposal.objects.filter(contact=contact, capability='RED-02').order_by('-created_at').first()
            payload_note = bool(proposal and proposal.payload.get('note'))
            if proposal is not None and send:
                proposal = self.gate_and_send(proposal)
            elif proposal is not None:
                operador.reject(self.gustavo, proposal.id, 'Medida; se veta para dejar cupo en la rampa del día.')
        sent = self.sent_invitation(contact)
        return {'contact': contact, 'proposal': proposal, 'invitada': bool(sent),
                'con_nota': bool(sent and sent['message']) if send else payload_note,
                'stopped_by': self.stopped(contact, 'nota')}

    def gate_and_send(self, proposal):
        """The autonomous gate of RED-02 (policy_review with the lead) and the operator."""
        from team_backend import autopiloto
        with self.lead(), patch.dict(os.environ, {'OPERATOR_AUTONOMY': 'RED-02=auto'}):
            proposal = autopiloto.policy_review(ActionProposal.objects.get(pk=proposal.pk))
            if proposal.state == 'approved':
                try:
                    operador.execute(self.gustavo, proposal.id)
                except operador.OperatorBlocked:
                    pass  # stopped by the last gate: stays approved until it expires
        return ActionProposal.objects.get(pk=proposal.pk)


class NoteCaseTests(NoteCaseBase):
    """Las variantes de BIB-09-nota-invitacion. Línea base: docs/linea-base-nota-invitacion.md."""

    # Línea base: nadie redacta la nota al invitar; solo la del clasificador.
    @expectedFailure
    def test_n1_a_concrete_note_is_drafted_at_invite_time_and_goes_with_the_invitation(self):
        run = self.run_variant('N1')
        self.assertTrue(run['con_nota'])
        self.assertEqual(self.sent_invitation(run['contact'])['message'], note('N1'))
        call = next(c for c in self.calls if c['purpose'] == 'invite-note')
        self.assertTrue(any(f.get('comentario_del_equipo') for f in call['inputs']['hechos']))  # the warm-up comment as context

    # Línea base: no hay redacción de la nota que cargue sus unidades.
    @expectedFailure
    def test_n1_the_draft_loads_the_note_units(self):
        self.run_variant('N1')
        context = next(c['context'] for c in self.calls if c['purpose'] == 'invite-note')
        for uid in CASE['units']:
            self.assertIn(uid, context)

    # Línea base: no hay reglas fijas de la nota del comprador.
    @expectedFailure
    def test_n2_to_n6_the_fixed_rules_stop_the_note_and_the_invitation_goes_without_it(self):
        for variant in ('N2', 'N3', 'N4', 'N5', 'N6'):
            run = self.run_variant(variant, send=variant == 'N2')
            self.assertEqual((run['con_nota'], run['stopped_by']), (False, 'reglas'), variant)
            if variant == 'N2':
                self.assertTrue(run['invitada'])

    # Línea base: no hay preguntas del líder para esta nota.
    @expectedFailure
    def test_n7_the_lead_rejects_the_note(self):
        run = self.run_variant('N7')
        self.assertEqual((run['con_nota'], run['stopped_by'], run['invitada']), (False, 'juez', True))

    # Línea base: nadie registra que falte el hecho.
    @expectedFailure
    def test_n8_without_a_warm_up_or_a_fact_no_note_is_drafted(self):
        run = self.run_variant('N8')
        self.assertEqual((run['con_nota'], run['stopped_by']), (False, 'hecho'))
        self.assertFalse(self.paid(run['contact'], 'invite-note'))

    # Línea base: nadie registra que falte el cupo.
    @expectedFailure
    def test_n9_without_notes_left_this_month_it_goes_without_one(self):
        run = self.run_variant('N9')
        self.assertEqual((run['con_nota'], run['stopped_by'], run['invitada']), (False, 'cupo', True))

    # Línea base: el error: la nota sin revisión bloquea la invitación hasta caducar.
    @expectedFailure
    def test_g_a_person_gustavo_confirmed_is_invited(self):
        run = self.run_variant('G')
        self.assertEqual(run['proposal'].state, 'confirmed', run['proposal'].risks)
        self.assertTrue(run['invitada'])

    def run_case(self):
        """Todas las variantes con las funciones de producción, calificadas con grade_course_case."""
        runs = {v: self.run_variant(v, send=v in ('N1', 'N2', 'N7', 'N9', 'G')) for v in PEOPLE}
        result = {'redactada_al_invitar': self.paid(runs['N1']['contact'], 'invite-note'),
                  'nota_con_metodologia': any('LI-09-M002-K06' in c['context'] for c in self.calls if c['purpose'] == 'invite-note'),
                  'G_invitada': runs['G']['invitada'],
                  'invitaciones_sin_salir': ActionProposal.objects.filter(capability='RED-02', state='approved').count()}
        for v in PEOPLE:
            if f'{v}_con_nota' in CASE['expected']:
                result[f'{v}_con_nota'] = runs[v]['con_nota']
            if f'{v}_stopped_by' in CASE['expected']:
                result[f'{v}_stopped_by'] = runs[v]['stopped_by']
        drafts = self.drafts_of(runs['N1']['contact'], 'nota')
        grounding = (drafts[-1].review or {}) if drafts else {}
        result['course_citations'] = grounding.get('course_citations', [])
        return evaluaciones.grade_course_case('nota_invitacion', result, grounding), result

    # Línea base: el caso completo no pasa (docs/linea-base-nota-invitacion.md).
    @expectedFailure
    def test_the_case_passes_with_production_functions(self):
        grade, result = self.run_case()
        self.assertTrue(grade['passed'], (grade['errors'], result))

    # Línea base: las tres unidades de la clase 09 no se cargan hasta activar la metodología.
    @expectedFailure
    def test_the_case_loads_whole_versioned_sources_and_rejects_wrong_behaviour(self):
        context, grounding = evaluaciones.course_case_context('nota_invitacion')
        self.assertEqual(grounding['course_missing'], [])
        result = dict(CASE['expected'], course_citations=CASE['required'])
        self.assertTrue(evaluaciones.grade_course_case('nota_invitacion', result, grounding)['passed'])
        self.assertFalse(evaluaciones.grade_course_case('nota_invitacion', dict(result, N2_con_nota=True), grounding)['passed'])
        self.assertFalse(evaluaciones.grade_course_case('nota_invitacion', dict(result, invitaciones_sin_salir=1), grounding)['passed'])
        self.assertFalse(evaluaciones.grade_course_case('nota_invitacion', dict(result, course_citations=CASE['required'] + ['LI-09-M003-K02']),
                                                        grounding)['passed'])


class ConfirmedNoteBugTests(NoteCaseBase):
    """El error de hoy, con el interruptor apagado: la nota del clasificador sin revisión del líder (Gustavo confirmó a
    la persona, o LEAD_ENABLED=false) bloqueaba la invitación en red.execution_issues hasta que caducaba."""

    def setUp(self):
        super().setUp()
        env = patch.dict(os.environ, {'BUYER_FIRST_MESSAGE_ENABLED': 'false'})
        env.start()
        self.addCleanup(env.stop)

    def invited_with_a_classifier_note(self, slug, name, confirm=False):
        contact = self.answered(slug, name, note=CLASSIFIER_NOTE)
        if confirm:
            red.confirm_fit(self.gustavo, contact.pk)
        self.plan()
        proposal = ActionProposal.objects.get(contact=contact, capability='RED-02')
        self.assertEqual(proposal.payload.get('note'), CLASSIFIER_NOTE)
        return contact, proposal

    # Línea base: el error: bloqueada en red.execution_issues hasta caducar.
    @expectedFailure
    def test_confirmed_by_gustavo_the_invitation_goes_out_without_the_unreviewed_note(self):
        contact, proposal = self.invited_with_a_classifier_note('bug-rosa', 'Rosa Bug', confirm=True)
        proposal = self.gate_and_send(proposal)
        self.assertEqual(proposal.state, 'confirmed', proposal.risks)
        self.assertEqual(self.sent_invitation(contact)['message'], '')
        omitted = AuditEvent.objects.get(action='network.note_omitted', target=str(proposal.pk))
        self.assertIn('líder', omitted.metadata['reason'])
        self.assertFalse(AuditEvent.objects.filter(action='network.note_reserved', target=str(proposal.pk)).exists())

    # Línea base: el error: bloqueada en red.execution_issues hasta caducar.
    @expectedFailure
    def test_with_the_lead_off_the_invitation_goes_out_without_the_unreviewed_note(self):
        contact, proposal = self.invited_with_a_classifier_note('bug-sol', 'Sol Bug')
        from team_backend import autopiloto
        with patch.dict(os.environ, {'OPERATOR_AUTONOMY': 'RED-02=auto', 'LEAD_ENABLED': 'false'}):
            proposal = autopiloto.policy_review(ActionProposal.objects.get(pk=proposal.pk))
            self.assertEqual(proposal.state, 'approved')
            try:
                operador.execute(self.gustavo, proposal.id)
            except operador.OperatorBlocked:
                pass
        proposal.refresh_from_db()
        self.assertEqual(proposal.state, 'confirmed')
        self.assertEqual(self.sent_invitation(contact)['message'], '')

    def test_a_note_the_lead_approved_still_goes_with_the_invitation(self):
        contact, proposal = self.invited_with_a_classifier_note('bug-tea', 'Tea Bug')
        proposal = self.gate_and_send(proposal)
        self.assertEqual(proposal.state, 'confirmed', proposal.risks)
        self.assertTrue(proposal.review['note_approved'])
        self.assertEqual(self.sent_invitation(contact)['message'], CLASSIFIER_NOTE)


class NoteRulesTests(SimpleTestCase):
    """Las reglas fijas de la nota (mensajes_comprador.note_text_issues): ≤200 caracteres, sin venta, sin «ser parte de
    mi red», sin elogio genérico, el hecho presente y en el idioma de la persona."""
    FACT = [{'id': 'h1', 'tipo': 'comentario', 'texto': 'We shipped our first paid pilot with two engineers and a spreadsheet.'}]

    def issues(self, variant):
        from team_backend import mensajes_comprador
        return mensajes_comprador.note_text_issues(note(variant), self.FACT, 'h1', reference=self.FACT[0]['texto'])

    # Línea base: mensajes_comprador.note_text_issues no existe.
    @expectedFailure
    def test_the_case_notes(self):
        self.assertEqual(self.issues('N1'), [])
        self.assertEqual(self.issues('N7'), [])  # passes the rules: the lead stops it
        for variant in ('N2', 'N3', 'N4', 'N5', 'N6'):
            self.assertTrue(self.issues(variant), variant)
