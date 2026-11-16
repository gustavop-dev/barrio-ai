"""BIB-09-primer-mensaje: la primera metodología de outbound (clase 09) medida con las funciones de producción.

El único primer mensaje que existe es el dm_opener de INT-04 (respuestas.propose, segundo turno con cierre permitido), que
Tu turno muestra como «Mensaje sugerido» cuando la persona ya es conexión y que Gustavo envía a mano. Cada variante del caso
recorre el camino real: lectura del hilo, borrador (Claude simulado), compuerta del autopiloto con el líder (Jev simulado),
escritura en el conector simulado, conexión y Tu turno. Unidades del curso sintéticas, sin red ni proveedores pagados.

El Jev simulado es un juez por rasgos del texto, no una tabla de respuestas: lo que se prueba es que el código haga las
preguntas, aplique los umbrales y respete lo que el líder decide."""
import re
from contextlib import contextmanager
from datetime import timedelta
from unittest import expectedFailure
from unittest.mock import patch

from django.utils import timezone
from knowledge import db
from team_backend import autopiloto, evaluaciones, lider, operador, respuestas
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
        # Unidades sintéticas de la clase 09 (la lista del caso): nunca texto del curso privado.
        with db.connect() as c:
            for uid in CASE['units']:
                c.execute('''INSERT INTO units(id,session,title,original,sha256,source_path,pointer,metadata)
                    VALUES(%s,%s,%s,'{"title":"Synthetic course fixture","limits_errors":"Do not infer facts or authority"}',
                    'fixture-hash','fixture','/units/0','{}') ON CONFLICT(id) DO NOTHING''', (uid, int(uid[3:5]), uid))
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

    def gate_and_write(self, proposal):
        with self.lead():
            proposal = autopiloto.policy_review(ActionProposal.objects.get(pk=proposal.pk))
        if proposal.state == 'approved':
            operador.execute(self.gustavo, proposal.id)
        return ActionProposal.objects.get(pk=proposal.pk)

    def messages_sent(self):
        """Mensajes privados escritos por la cuenta: el equipo nunca envía uno (INB-08)."""
        return sum(m['is_sender'] for chat in self.fake.state['chats'].values() for m in chat['messages'])

    def cards(self):
        return self.human.get('/api/v1/tu-turno').json()['tasks']['mensajes']

    def conversation(self, opener, name='Ana Payments', public_id='ana-payments', post=POST):
        """Ana comenta, el equipo responde (turno 1), Ana sigue con sustancia y el equipo cierra (turno 2) redactando
        `opener`. Después Ana es conexión. Devuelve lo observable de esa variante."""
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
        claude = self.propose(second, draft(reply=CLOSING, dm_opener=opener))
        proposal = self.gate_and_write(ActionProposal.objects.get(capability='INT-04', comment=second))
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
                'stored': stored, 'row': second, 'proposal': proposal, 'review': review, 'drafts': claude.call_count}

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

    @expectedFailure  # línea base: hoy el mensaje llega a Tu turno sin reglas (ver docs/linea-base-primer-mensaje.md)
    def test_p2_asking_for_time_and_a_link_is_stopped_by_the_rules(self):
        outcome = self.conversation(CASE['input']['P2']['dm_opener'])
        self.assertFalse(outcome['card'])
        self.assertEqual(outcome['stopped_by'], 'reglas')
        self.assertEqual(outcome['proposal'].state, 'confirmed')  # la respuesta pública sale igual
        self.assertEqual(self.messages_sent(), 0)

    @expectedFailure  # línea base: hoy el mensaje llega a Tu turno sin reglas ni juez
    def test_p3_formulas_and_selling_are_stopped_by_the_rules(self):
        outcome = self.conversation(CASE['input']['P3']['dm_opener'])
        self.assertFalse(outcome['card'])
        self.assertEqual(outcome['stopped_by'], 'reglas')
        self.assertEqual(outcome['proposal'].state, 'confirmed')
        self.assertEqual(self.messages_sent(), 0)

    @expectedFailure  # línea base: el líder hoy no revisa el primer mensaje
    def test_p3_the_judge_alone_would_also_reject_it(self):
        outcome = self.conversation(CASE['input']['P1']['dm_opener'])
        row = outcome['row']
        row.decision = dict(row.decision, dm_opener=CASE['input']['P3']['dm_opener'])
        row.save(update_fields=['decision'])
        with self.lead():
            review = lider.review(ActionProposal.objects.get(pk=outcome['proposal'].pk))
        self.assertEqual(review['decision'], 'approve')  # la respuesta pública no depende del primer mensaje
        self.assertIs(review.get('dm_approved'), False)

    @expectedFailure  # línea base: el líder hoy no revisa el primer mensaje
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

    @expectedFailure  # línea base: falla la conducta (P2–P4) y el fundamento (la clase 09 no está activada)
    def test_the_case_passes_with_production_functions(self):
        grade, result = self.run_case()
        self.assertTrue(grade['passed'], (grade['errors'], result))

    @expectedFailure  # línea base: las unidades de la clase 09 aún no se pueden cargar para un agente
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
