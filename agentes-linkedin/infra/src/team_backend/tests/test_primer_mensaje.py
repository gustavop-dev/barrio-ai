"""BIB-09-primer-mensaje: la primera metodología de outbound (clase 09) medida con las funciones de producción.

El único primer mensaje que existe es el dm_opener de INT-04 (respuestas.propose, segundo turno con cierre permitido), que
Tu turno muestra como «Mensaje sugerido» cuando la persona ya es conexión y que Gustavo envía a mano. Cada variante del caso
recorre el camino real: lectura del hilo, borrador (Claude simulado), compuerta del autopiloto con el líder (Jev simulado),
escritura en el conector simulado, conexión y Tu turno. Unidades del curso sintéticas, sin red ni proveedores pagados.

El Jev simulado es un juez por rasgos del texto, no una tabla de respuestas: lo que se prueba es que el código haga las
preguntas, aplique los umbrales y respete lo que el líder decide."""
import json
import re
from contextlib import contextmanager
from datetime import timedelta
from unittest.mock import patch

from django.test import SimpleTestCase
from django.utils import timezone
from knowledge import db
from team_backend import autopiloto, evaluaciones, guardas, lider, operador, respuestas
from team_backend.models import ActionProposal, AuditEvent, Contact, PostComment
from team_backend.tests.test_respuestas import RepliesBase, draft

CASE = evaluaciones.COURSE_CASES['primer_mensaje']
POST = ('Rollbacks are a product decision, not an ops chore: the hard part is the state that half-migrated users leave '
        'behind, not the deploy.')
REPLY_1 = ('That reconciliation gap is the part nobody plans for. Keeping the old path readable until the data settles '
           'usually costs less than the rollback itself.')
CLOSING = ('Running both flows for a while is usually what removes the guessing. This thread is getting interesting; happy '
           'to connect and keep comparing notes.')
# Lo que el líder contesta a las preguntas de la respuesta pública: todas pasan. El caso mide solo el primer mensaje.
PUBLIC_OK = {'responde': 0.9, 'hilo': 0.9, 'pitch': 0.05, 'inventa': 0.05, 'respeto': 0.95}


P1, P2, P3, P4 = (CASE['input'][v]['dm_opener'] for v in ('P1', 'P2', 'P3', 'P4'))
DM_RULE = 'Primer mensaje que vende o pide minutos, una llamada o una reunión'


def drafted(reply=CLOSING, dm_opener=''):
    """Una respuesta de Claude simulada para encadenar borradores distintos (side_effect)."""
    data = {'decision': 'reply', 'language': 'en', 'reply': reply, 'rationale': 'Answers what she said.',
            'citations': ['LI-03-M006-K02'], 'claims_needing_evidence': [], 'risks': [], 'dm_opener': dm_opener,
            'question_for_gustavo': {'question': '', 'purpose': '', 'memory_key': ''}}
    return {'text': json.dumps(data), 'model': 'claude-opus-5-5'}


def sentences(text):
    return [s for s in re.split(r'(?<=[.!?;])\s+', text.strip()) if s]


def judge(dm):
    """Jev simulado para el primer mensaje: probabilidad de «sí» de cada pregunta según rasgos del texto."""
    parts = sentences(dm) or ['']
    first, last, low = parts[0].lower(), parts[-1].lower(), dm.lower()
    names_what_she_said = any(k in first for k in ('payments flow', 'rolling back', 'rollback'))
    services = any(k in low for k in ('partner', 'our services', 'we help', 'we are a'))
    easy = last.endswith('?') and (last.startswith(('did ', 'do ', 'is ', 'are ', 'was ', 'would ', 'should ', 'have '))
                                   or ' or ' in last)
    many_problems = bool(re.search(r'\w+, \w+,? and \w+', low))
    formulas = any(k in low for k in ('hope you', 'looking forward', 'leading partner'))
    asks = any(k in low for k in ('minutes', 'http', 'call', 'email', 'partner'))
    return {'dm_toque': 0.9 if names_what_she_said else 0.1,
            'dm_puente': 0.85 if any(k in low for k in ('point', 'thread', 'chat', 'conversation')) and not services else 0.15,
            'dm_pregunta': 0.9 if easy else 0.15,
            'dm_un_tema': 0.1 if many_problems else 0.9,
            'dm_en_persona': 0.2 if formulas else 0.85,
            'dm_pitch': 0.9 if asks else 0.05}


class FirstMessageBase(RepliesBase):
    def setUp(self):
        super().setUp()
        # Las unidades de la clase 09 (FIRST_MESSAGE_UNITS) las siembra OperatorBase, sintéticas: nunca texto del curso.
        self.jev_calls = []

    @contextmanager
    def lead(self):
        """El líder activo con Jev simulado: la misma compuerta que en producción (autopiloto.policy_review)."""
        def answer(state, questions, **kwargs):
            self.jev_calls.append({'state': state, 'questions': dict(questions), 'purpose': kwargs.get('purpose')})
            scores = {qid: PUBLIC_OK.get(qid, 0.9) for qid in questions}
            dm = (state.get('primer_mensaje') or {}).get('texto', '')
            scores.update({qid: value for qid, value in judge(dm).items() if qid in questions})
            return {'answers': {qid: {'noul': value} for qid, value in scores.items()}, 'model': 'fake-jev', 'estimated_usd': 0}
        with patch.dict('os.environ', {'LEAD_ENABLED': 'true'}), patch('knowledge.providers.typesafe', side_effect=answer):
            yield

    def gate_and_write(self, proposal, lead=True):
        with self.lead() if lead else patch.dict('os.environ', {'LEAD_ENABLED': 'false'}):
            proposal = autopiloto.policy_review(ActionProposal.objects.get(pk=proposal.pk))
        if proposal.state == 'approved':
            operador.execute(self.gustavo, proposal.id)
        return ActionProposal.objects.get(pk=proposal.pk)

    def messages_sent(self):
        """Mensajes privados escritos por la cuenta: el equipo nunca envía uno (INB-08)."""
        return sum(m['is_sender'] for chat in self.fake.state['chats'].values() for m in chat['messages'])

    def cards(self):
        return self.human.get('/api/v1/tu-turno').json()['tasks']['mensajes']

    def conversation(self, opener, name='Ana Payments', public_id='ana-payments', post=POST, claude=None, lead=True):
        """Ana comenta, el equipo responde (turno 1), Ana sigue con sustancia y el equipo cierra (turno 2) redactando
        `opener` (o lo que devuelva `claude`, un patch de knowledge.providers.claude). Después Ana es conexión. Devuelve lo
        observable de esa variante."""
        thread = CASE['input']['thread']
        _, pid = self.publish(post)
        ana = self.person(public_id, name, 'VP Engineering at a fintech startup')
        root = self.fake.comment_on_own_post(pid, ana['id'], thread['comment'], at=timezone.now() - timedelta(minutes=20))
        self.read()
        first = PostComment.objects.get(provider_comment_id=root)
        self.propose(first, draft(reply=REPLY_1))
        self.gate_and_write(ActionProposal.objects.get(capability='INT-04', comment=first))
        Contact.objects.filter(pk=first.contact_id).update(classification={'fit': True, 'role': 'comprador', 'confidence': 0.9})
        self.fake.comment_on_own_post(pid, ana['id'], thread['follow_up'], thread=root, at=timezone.now() + timedelta(seconds=5))
        self.rescan()
        second = PostComment.objects.get(text=thread['follow_up'], thread_id=root)
        claude = self.propose(second, claude or draft(reply=CLOSING, dm_opener=opener))
        proposal = self.gate_and_write(ActionProposal.objects.get(capability='INT-04', comment=second), lead=lead)
        Contact.objects.filter(pk=first.contact_id).update(stage='connected', connected_at=timezone.now(), network_distance='FIRST_DEGREE')
        respuestas.on_connected(Contact.objects.get(pk=first.contact_id))
        second.refresh_from_db()
        stored = (second.decision or {}).get('dm_opener', '')
        review = proposal.review or {}
        cards = [c for c in self.cards() if c['id'] == f'dm:{second.id}']
        if cards:
            stopped_by = None
        elif opener and not stored:
            stopped_by = 'reglas'
        elif stored and review.get('dm_approved') is False:
            stopped_by = 'juez'
        else:
            stopped_by = 'otro'
        return {'card': bool(cards), 'card_text': cards[0]['message']['text'] if cards else None, 'stopped_by': stopped_by,
                'stored': stored, 'row': second, 'proposal': proposal, 'review': review, 'claude': claude}

    def cold_acceptance(self):
        """P5: alguien sin conversación previa acepta una invitación. Nada se redacta ni llega a Tu turno."""
        eva = self.contact('cold-eva', 'Eva Cold', stage='followed', followed_hours=60)
        self.job('plan_network')
        self.approve_open(eva, 'RED-02')
        self.fake.accept_sent(eva.provider_user_id)
        self.job('sync_network')
        eva.refresh_from_db()
        self.assertEqual(eva.stage, 'connected')
        drafted = PostComment.objects.filter(contact=eva).exclude(decision__dm_opener='').filter(decision__has_key='dm_opener').exists()
        pushed = AuditEvent.objects.filter(action='replies.dm_ready', metadata__contact=str(eva.pk)).exists()
        cards = [c for c in self.cards() if c['message']['person']['id'] == str(eva.pk)]
        return {'card': bool(cards), 'stopped_by': 'momento' if not (cards or drafted or pushed) else None}


class FirstMessageCaseTests(FirstMessageBase):
    """Las cinco variantes de BIB-09-primer-mensaje. Línea base: docs/linea-base-primer-mensaje.md."""

    def test_p1_a_concrete_message_from_the_thread_reaches_tu_turno(self):
        outcome = self.conversation(CASE['input']['P1']['dm_opener'])
        self.assertTrue(outcome['card'])
        self.assertEqual(outcome['card_text'], CASE['input']['P1']['dm_opener'])
        self.assertEqual(outcome['proposal'].state, 'confirmed')
        self.assertEqual(self.messages_sent(), 0)

    def test_p2_asking_for_time_and_a_link_is_stopped_by_the_rules(self):
        outcome = self.conversation(CASE['input']['P2']['dm_opener'])
        self.assertFalse(outcome['card'])
        self.assertEqual(outcome['stopped_by'], 'reglas')
        self.assertEqual(outcome['proposal'].state, 'confirmed')  # la respuesta pública sale igual
        self.assertEqual(self.messages_sent(), 0)

    def test_p3_formulas_and_selling_are_stopped_by_the_rules(self):
        outcome = self.conversation(CASE['input']['P3']['dm_opener'])
        self.assertFalse(outcome['card'])
        self.assertEqual(outcome['stopped_by'], 'reglas')
        self.assertEqual(outcome['proposal'].state, 'confirmed')
        self.assertEqual(self.messages_sent(), 0)

    def test_p3_the_judge_alone_would_also_reject_it(self):
        outcome = self.conversation(CASE['input']['P1']['dm_opener'])
        row = outcome['row']
        row.decision = dict(row.decision, dm_opener=CASE['input']['P3']['dm_opener'])
        row.save(update_fields=['decision'])
        with self.lead():
            review = lider.review(ActionProposal.objects.get(pk=outcome['proposal'].pk))
        self.assertEqual(review['decision'], 'approve')  # la respuesta pública no depende del primer mensaje
        self.assertIs(review.get('dm_approved'), False)

    def test_p4_a_vague_philosophical_message_is_stopped_by_the_judge(self):
        outcome = self.conversation(CASE['input']['P4']['dm_opener'])
        self.assertFalse(outcome['card'])
        self.assertEqual(outcome['stopped_by'], 'juez')
        self.assertEqual(outcome['proposal'].state, 'confirmed')
        self.assertEqual(self.messages_sent(), 0)

    def test_p5_a_cold_acceptance_never_drafts_a_message(self):
        outcome = self.cold_acceptance()
        self.assertFalse(outcome['card'])
        self.assertEqual(outcome['stopped_by'], 'momento')
        self.assertEqual(self.messages_sent(), 0)

    def run_case(self):
        """Las cinco variantes con las funciones de producción, calificadas con grade_course_case."""
        result, reviews = {}, {}
        # Cuatro conversaciones en un mismo día de lecturas: los topes diarios de lectura no son lo que se mide aquí.
        with patch.dict('os.environ', {'REPLIES_READ_CAPS': 'posts=60,comments=60,threads=60,people_posts=20'}):
            for variant in ('P1', 'P2', 'P3', 'P4'):
                # Un post distinto por variante: la lectura reconoce cada post propio por su texto exacto.
                outcome = self.conversation(CASE['input'][variant]['dm_opener'], name=f'Ana {variant}',
                                            public_id=f'ana-{variant.lower()}', post=f'{POST} ({variant})')
                result[f'{variant}_card'] = outcome['card']
                result[f'{variant}_stopped_by'] = outcome['stopped_by']
                reviews[variant] = outcome
        p1 = reviews['P1']
        row = p1['row']
        row.decision = dict(row.decision, dm_opener=CASE['input']['P3']['dm_opener'])
        row.save(update_fields=['decision'])
        with self.lead():
            judged = lider.review(ActionProposal.objects.get(pk=p1['proposal'].pk))
        result['P3_judge_rejects'] = judged.get('dm_approved') is False
        cold = self.cold_acceptance()
        result.update(P5_card=cold['card'], P5_stopped_by=cold['stopped_by'], messages_sent=self.messages_sent())
        grounding = p1['review']
        result['course_citations'] = grounding.get('course_citations', [])
        result = {k: v for k, v in result.items() if k in CASE['expected'] or k == 'course_citations'}
        return evaluaciones.grade_course_case('primer_mensaje', result, grounding), result

    def test_the_case_passes_with_production_functions(self):
        grade, result = self.run_case()
        self.assertTrue(grade['passed'], (grade['errors'], result))

    def test_the_case_loads_whole_versioned_sources_and_rejects_wrong_behaviour(self):
        context, grounding = evaluaciones.course_case_context('primer_mensaje')
        self.assertIn('limits_errors', context)
        self.assertEqual(grounding['course_missing'], [])
        result = dict(CASE['expected'], course_citations=CASE['required'])
        self.assertTrue(evaluaciones.grade_course_case('primer_mensaje', result, grounding)['passed'])
        self.assertFalse(evaluaciones.grade_course_case('primer_mensaje', dict(result, P2_card=True), grounding)['passed'])
        self.assertFalse(evaluaciones.grade_course_case('primer_mensaje', dict(result, messages_sent=1), grounding)['passed'])
        self.assertFalse(evaluaciones.grade_course_case('primer_mensaje', dict(CASE['expected'], course_citations=['LI-07-V001-K01']),
                                                        grounding)['passed'])


class FirstMessageRulesTests(SimpleTestCase):
    """respuestas.dm_text_issues: lo que mata un mensaje (LI-09-M003-K04) y la pregunta 6 de la guía (LI-09-M004-K02) como
    reglas fijas. Frases completas: una palabra suelta nunca cuenta."""

    def setUp(self):
        blocks = patch('team_backend.guardas.blocks', return_value=([], list(guardas.BASELINE_GUIDANCE)))
        blocks.start()
        self.addCleanup(blocks.stop)

    def issues(self, text, reference=CASE['input']['thread']['follow_up']):
        return respuestas.dm_text_issues(text, reference)

    def test_the_case_messages(self):
        self.assertEqual(self.issues(P1), [])
        self.assertEqual(self.issues(P4), [])  # lo vago no es una regla: lo juzga el líder
        self.assertEqual(self.issues(''), [])
        p2 = self.issues(P2)
        self.assertIn('Primer mensaje con enlaces', p2)
        self.assertIn(DM_RULE, p2)
        p3 = ' '.join(self.issues(P3))
        for formula in ("«Hope you're doing well»", '«We are a leading»', '«Looking forward to hearing»'):
            self.assertIn(formula, p3)

    def test_asking_for_time_or_a_meeting_in_either_language(self):
        english = CASE['input']['thread']['follow_up']
        spanish = 'Justo eso: nunca supimos si fue el flag o el orden del despliegue. ¿Mantuviste los dos flujos mientras volvías atrás?'
        for text, reference in (('Do you have 15 minutes this week to compare notes?', english),
                                ('Would you have a few minutes for a quick call about it?', english),
                                ('Could we hop on a call next week and compare?', english),
                                ("Let's schedule a quick meeting about the rollback.", english),
                                ('What is your email? I can send the checklist we used.', english),
                                ('Here is my calendly in case it helps.', english),
                                ('¿Tienes 15 minutos esta semana para comparar notas?', spanish),
                                ('¿Agendamos una llamada para verlo con calma?', spanish),
                                ('¿Tendrías tiempo el jueves para contarme cómo lo resolviste?', spanish)):
            with self.subTest(text=text):
                self.assertIn(DM_RULE, self.issues(text, reference))

    def test_the_killer_formulas_in_either_language(self):
        spanish = 'Justo eso: nunca supimos si fue el flag o el orden del despliegue. ¿Mantuviste los dos flujos mientras volvías atrás?'
        for text, reference in (('Gracias por conectar. ¿Cómo resolviste lo del flag?', spanish),
                                ('Espero que estés muy bien. ¿Volviste a separar los despliegues?', spanish),
                                ('Quedo atento a tus comentarios sobre el rollback del flujo de pagos.', spanish),
                                ('Me encantaría que fueras parte de mi red; ¿usaste un flag para volver atrás?', spanish),
                                ('Thanks for connecting! Did the flag or the deploy order cause it?', CASE['input']['thread']['follow_up'])):
            with self.subTest(text=text):
                self.assertTrue(any(i.startswith('Primer mensaje con fórmulas que lo matan') for i in self.issues(text, reference)))

    def test_no_false_positives_on_a_concrete_message(self):
        spanish = 'Justo eso: nunca supimos si fue el flag o el orden del despliegue. ¿Mantuviste los dos flujos mientras volvías atrás?'
        for text, reference in (
                ('Your point that the rollback took 40 minutes but reconciliation took two days stuck with me. Was it the flag?', None),
                ('Your note on the API call order stuck with me. Did you change the call sequence or the deploy order?', None),
                ('Thanks for connecting the dots between flags and deploy order. Which one bit you first?', None),
                ('Hope the migration settled after all. Did you keep both flows running?', None),
                ('Quedó pendiente lo del flag en el hilo. ¿Lo resolviste con otro despliegue?', spanish),
                ('Espero que el rollback haya salido bien al final. ¿Lo hiciste con un flag o con otro despliegue?', spanish)):
            with self.subTest(text=text):
                self.assertEqual(self.issues(text, reference or CASE['input']['thread']['follow_up']), [])

    def test_length_lines_and_language(self):
        four = 'Your point on rollbacks stuck. We left it open. I keep thinking about it. Did you use a flag?'
        self.assertIn('Primer mensaje de más de 3 líneas (4)', self.issues(four))
        self.assertEqual(respuestas.dm_lines('One line.\nTwo lines?'), 2)
        long = 'Your point about rolling back the payments flow stuck with me; ' + 'the reconciliation part ' * 20 + 'Did you use a flag?'
        self.assertGreater(len(long), respuestas.DM_MAX_CHARS)
        self.assertTrue(any(i.startswith('Primer mensaje de más de 500 caracteres') for i in self.issues(long)))
        spanish = 'Justo eso: nunca supimos si fue el flag o el orden del despliegue. ¿Mantuviste los dos flujos mientras volvías atrás?'
        self.assertIn('Primer mensaje fuera del idioma de la persona (es)', self.issues(P1, spanish))


class FirstMessageProcedureTests(FirstMessageBase):
    """La única reescritura, el descarte entero, la misma revisión del líder y la tarjeta solo con dm_approved."""

    def test_a_message_that_breaks_a_rule_goes_into_the_single_redraft_and_the_reply_stays_the_first(self):
        claude = patch('knowledge.providers.claude', side_effect=[drafted(dm_opener=P2),
                                                                  drafted(reply='A different public reply.', dm_opener=P1)])
        outcome = self.conversation(P2, claude=claude)
        calls = outcome['claude'].call_args_list
        self.assertEqual(len(calls), 2)  # el borrador y la única reescritura
        revision = json.loads(calls[1].args[1])['revision']
        self.assertEqual(revision['rule_violations'], [])
        self.assertEqual(revision['previous_dm_opener'], P2)
        self.assertIn(DM_RULE, revision['dm_rule_violations'])
        self.assertEqual(outcome['proposal'].payload['text'], CLOSING)  # la respuesta pública es la del primer borrador
        self.assertEqual(outcome['proposal'].state, 'confirmed')
        self.assertEqual(outcome['stored'], P1)
        self.assertTrue(outcome['card'])
        self.assertEqual(outcome['card_text'], P1)

    def test_a_message_that_still_breaks_the_rules_is_dropped_whole_and_only_audited(self):
        long = P1[:-1] + ', and ' + 'whether the reconciliation job ' * 18 + 'ran twice?'
        claude = patch('knowledge.providers.claude', side_effect=[drafted(dm_opener=P3), drafted(dm_opener=long)])
        outcome = self.conversation(P3, claude=claude)
        self.assertFalse(outcome['card'])
        self.assertEqual(outcome['stopped_by'], 'reglas')
        self.assertEqual(outcome['stored'], '')
        self.assertEqual(outcome['proposal'].payload['text'], CLOSING)
        self.assertEqual(outcome['proposal'].state, 'confirmed')  # la respuesta pública sale igual
        self.assertTrue(any(r.startswith('Primer mensaje descartado por las reglas fijas: Primer mensaje de más de 500')
                            for r in outcome['proposal'].risks))
        audit = AuditEvent.objects.get(action='replies.drafted', target=str(outcome['row'].id))
        self.assertEqual(audit.metadata['dm_rejected']['text'], long)  # entero: nunca se recorta
        self.assertNotIn('dm_rejected', outcome['row'].decision)

    def test_the_lead_judges_the_message_in_the_same_review_and_never_discards_the_reply(self):
        outcome = self.conversation(P4)
        reviews = [c for c in self.jev_calls if c['purpose'] == 'lead-review']
        self.assertEqual(len(reviews), 2)  # turno 1 y turno 2: ninguna llamada aparte para el mensaje
        first, second = reviews
        self.assertNotIn('primer_mensaje', first['state'])
        self.assertFalse(lider.DM_IDS & set(first['questions']))
        self.assertEqual(second['state']['primer_mensaje']['texto'], P4)
        self.assertLessEqual(lider.DM_IDS, set(second['questions']))
        review = outcome['review']
        self.assertEqual((review['decision'], review['reasons']), ('approve', []))
        self.assertIs(review['dm_approved'], False)
        self.assertEqual({re.search(r'\((dm_\w+)=', r).group(1) for r in review['dm_reasons']}, {'dm_toque', 'dm_pregunta'})
        self.assertLessEqual(lider.DM_IDS, set(review['answers']))
        self.assertEqual(outcome['proposal'].state, 'confirmed')
        first_review = ActionProposal.objects.get(capability='INT-04', comment__thread_id='').review
        self.assertNotIn('dm_approved', first_review)

    def test_without_the_lead_review_there_is_no_card(self):
        outcome = self.conversation(P1, lead=False)
        self.assertEqual(outcome['proposal'].state, 'confirmed')
        self.assertEqual(outcome['stored'], P1)
        self.assertFalse(outcome['card'])


class FirstMessageReadingTests(FirstMessageBase):
    """La lectura: Relaciones y el líder cargan FIRST_MESSAGE_UNITS enteras solo cuando hay un primer mensaje, y sin ellas la
    respuesta pública sigue como siempre."""

    def test_only_the_closing_draft_and_its_review_load_the_class_09_units(self):
        outcome = self.conversation(P1)
        context = outcome['claude'].call_args.kwargs['context']
        for uid in operador.FIRST_MESSAGE_UNITS:
            self.assertIn(uid, context)
        drafted = AuditEvent.objects.filter(action='replies.drafted').order_by('created_at')
        first, second = [e.metadata['course_citations'] for e in drafted]
        self.assertFalse(set(operador.FIRST_MESSAGE_UNITS) & set(first))
        self.assertLessEqual(set(operador.FIRST_MESSAGE_UNITS), set(second))
        reviews = [c['state']['course_grounding'] for c in self.jev_calls if c['purpose'] == 'lead-review']
        self.assertEqual(reviews[0]['course_citations'], operador.LEAD_UNITS)
        self.assertNotIn('course_methodology', reviews[0])
        self.assertEqual(reviews[1]['course_citations'], operador.LEAD_UNITS + operador.FIRST_MESSAGE_UNITS)
        self.assertEqual(reviews[1]['course_methodology'], 'primer_mensaje')
        self.assertEqual(reviews[1]['course_version'], 'bib-v2')
        self.assertEqual(reviews[1]['criterion_sources']['dm_pregunta'], ['LI-09-M003-K03'])
        self.assertEqual(reviews[1]['criterion_sources']['dm_pitch'], ['LI-09-M002-K04', 'LI-03-M006-K01'])
        question = [c for c in self.jev_calls if c['purpose'] == 'lead-review'][1]['questions']['dm_pregunta']
        self.assertIn('LI-09-M003-K03', question['instructions'])

    def test_without_the_class_09_units_the_reply_goes_out_and_no_message_is_kept(self):
        with db.connect() as c:
            c.execute('DELETE FROM units WHERE id = ANY(%s)', (operador.FIRST_MESSAGE_UNITS,))
        outcome = self.conversation(P1)
        self.assertEqual(outcome['proposal'].payload['text'], CLOSING)
        self.assertEqual(outcome['proposal'].state, 'confirmed')
        self.assertEqual(outcome['stored'], '')
        self.assertFalse(outcome['card'])
        self.assertTrue(any(r.startswith('Primer mensaje sin redactar: faltan unidades de la clase 09') for r in outcome['proposal'].risks))
        self.assertNotIn('LI-09-M003-K02', outcome['claude'].call_args.kwargs['context'])

    def test_if_the_units_vanish_before_the_review_the_message_is_not_judged_and_the_reply_is(self):
        outcome = self.conversation(P1)
        with db.connect() as c:
            c.execute('DELETE FROM units WHERE id = ANY(%s)', (operador.FIRST_MESSAGE_UNITS,))
        self.jev_calls.clear()
        with self.lead():
            review = lider.review(ActionProposal.objects.get(pk=outcome['proposal'].pk))
        self.assertEqual((review['decision'], review['course_missing']), ('approve', []))
        self.assertIs(review['dm_approved'], False)
        self.assertEqual(review['dm_reasons'], [lider.DM_UNAVAILABLE])
        self.assertNotIn('primer_mensaje', self.jev_calls[0]['state'])
        self.assertFalse(lider.DM_IDS & set(self.jev_calls[0]['questions']))


class FirstMessageActivationTests(SimpleTestCase):
    """La activación es por metodología: solo sus siete unidades, solo cuando se nombra, solo en sus roles."""

    def test_the_activated_list_is_the_case_and_the_graph_list(self):
        from knowledge.clases import CLASES_AGENTES, METODOLOGIAS_ACTIVAS
        activa = METODOLOGIAS_ACTIVAS['primer_mensaje']
        self.assertEqual(CLASES_AGENTES, tuple(range(1, 7)))  # la activación no amplía las clases de los agentes
        self.assertEqual(list(activa['unidades']), operador.FIRST_MESSAGE_UNITS)
        self.assertEqual(activa['evaluacion'], CASE['id'])
        self.assertEqual(CASE['units'], operador.FIRST_MESSAGE_UNITS)
        self.assertLessEqual(set(CASE['required']), set(operador.FIRST_MESSAGE_UNITS))
        for key, methodology in METODOLOGIAS_ACTIVAS.items():
            self.assertIn(key, evaluaciones.COURSE_CASES)
            self.assertEqual(evaluaciones.COURSE_CASES[key]['id'], methodology['evaluacion'])

    def test_only_its_roles_name_the_methodology_in_code(self):
        from pathlib import Path
        source = Path(operador.__file__).parent
        naming = {p.name for p in source.glob('*.py') if "metodologia='primer_mensaje'" in p.read_text(encoding='utf-8')}
        self.assertEqual(naming, {'respuestas.py', 'lider.py'})  # relaciones_comunidad y lider_jev
        using = {p.name for p in source.glob('*.py') if 'FIRST_MESSAGE_UNITS' in p.read_text(encoding='utf-8')}
        self.assertEqual(using, {'operador.py', 'respuestas.py', 'lider.py', 'evaluaciones.py'})
