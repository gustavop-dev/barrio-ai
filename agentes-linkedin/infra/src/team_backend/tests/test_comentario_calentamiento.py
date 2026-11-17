"""BIB-09-comentario-calentamiento: el comentario en el post de un comprador que se calienta antes de invitarlo
(clases 07 y 10; fase 2 de docs/plan-outbound.md), medido con las funciones de producción.

Cada variante recorre el camino real: compradores elegidos y seguidos (descubrir, clasificar con la etapa en la web,
seguir), su post en el conector simulado, la lectura (job observe), la propuesta del autopiloto (autopiloto._propose),
el borrador (job propose_comment, Claude simulado), la compuerta del autopiloto con el líder (policy_review, Jev
simulado) y la escritura (operador.execute). Unidades del curso sintéticas, sin red ni proveedores pagados.

El Jev simulado es un juez por rasgos del texto, no una tabla de respuestas: lo que se prueba es que el código haga las
preguntas, aplique los umbrales y respete lo que el líder decide."""
import json
import os
import re
import uuid
from contextlib import contextmanager
from datetime import timedelta
from unittest import expectedFailure
from unittest.mock import patch

from django.utils import timezone
from team_backend import autopiloto, evaluaciones, jobs, operador
from team_backend.models import ActionProposal, Contact, Job, ObservedPost
from team_backend.tests.test_comprador_e2e import BuyerPathBase

CASE = evaluaciones.COURSE_CASES['comentario_calentamiento']
VARIANTS = ('C1', 'C2', 'C3', 'C4', 'C5', 'C6')
PEOPLE = {'C1': ('cal-carla', 'Carla Uno'), 'C2': ('cal-dario', 'Dario Dos'), 'C3': ('cal-elena', 'Elena Tres'),
          'C4': ('cal-fabio', 'Fabio Cuatro'), 'C5': ('cal-gina', 'Gina Cinco'), 'C6': ('cal-hugo', 'Hugo Seis')}
REFERENT = 'Ana Referente'  # sembrada por OperatorBase (referente-ai)
# Lo que el líder contesta al prefiltro (autopiloto._propose): el post merece un comentario. Lo que se mide es el comentario.
PREFILTER_OK = {'sustancia': 0.9, 'tema': 0.9, 'vacante': 0.05, 'promocion': 0.1, 'hito': 0.05}


def comment(variant):
    text = CASE['input'][variant]['comentario']
    return CASE['input'][text]['comentario'] if text in CASE['input'] else text


def sentences(text):
    return [s for s in re.split(r'(?<=[.!?])\s+', text.strip()) if s]


def judge(text):
    """Jev simulado: probabilidad de «sí» de cada pregunta del líder según rasgos del texto.

    Aporte propio: un mecanismo o una práctica concreta que la publicación no dice (no repetirla ni felicitar).
    Pregunta abierta y concreta: la última frase pregunta por una decisión o una práctica del autor."""
    parts = sentences(text) or ['']
    last, low = parts[-1].lower(), text.lower()
    applause = any(k in low for k in ('great post', 'love how', 'congrats', '👏', 'keep it up'))
    sells = any(k in low for k in ('dm me', "i'll show you", 'our team builds'))
    own = any(k in low for k in ('logging those answers', 'hides which answer', 'usual sign'))
    specific = last.endswith('?') and last.startswith(('which ', 'how are you deciding', 'what made', 'did '))
    return {'aporta': 0.85 if (own or specific) and not applause else 0.2,
            'pitch': 0.9 if sells else 0.05, 'inventa': 0.05, 'respeto': 0.95,
            'cal_aporte': 0.9 if own and not applause else 0.15,
            'cal_pregunta': 0.9 if specific else 0.2,
            'cal_aplauso': 0.9 if applause else 0.05}


class WarmupCommentBase(BuyerPathBase):
    def setUp(self):
        super().setUp()
        # Varios compradores en un día: las comprobaciones de etapa y el tope de comentarios de producción (10/día).
        env = patch.dict(os.environ, {'BUYER_WARMUP_ENABLED': 'true', 'NETWORK_STAGE_CHECKS_PER_DAY': '20',
                                      'OPERATOR_DAILY_LIMITS': 'INT-03=10', 'OPERATOR_WEEKLY_LIMITS': 'INT-03=50'})
        env.start()
        self.addCleanup(env.stop)
        self.jev_calls, self.drafts, self.texts = [], [], {}

    # -- providers
    @contextmanager
    def lead(self):
        """El líder activo con Jev simulado: la misma compuerta que en producción (autopiloto.policy_review)."""
        def answer(state, questions, **kwargs):
            self.jev_calls.append({'state': state, 'questions': dict(questions), 'purpose': kwargs.get('purpose')})
            scores = PREFILTER_OK if kwargs.get('purpose') == 'comment-prefilter' else judge(state.get('comentario') or '')
            return {'answers': {qid: {'noul': scores.get(qid, 0.9)} for qid in questions}, 'model': 'fake-jev', 'estimated_usd': 0}
        with patch.dict('os.environ', {'LEAD_ENABLED': 'true'}), patch('knowledge.providers.typesafe', side_effect=answer):
            yield

    @contextmanager
    def drafter(self):
        """Claude simulado para Relaciones: redacta para cada autor el comentario de su variante (self.texts)."""
        def claude(system, message, **kwargs):
            data = json.loads(message)
            text = self.texts[data['post']['author']]
            self.drafts.append({'author': data['post']['author'], 'context': kwargs.get('context') or '', 'system': system,
                                'inputs': data})
            out = {'decision': 'comment', 'language': 'en', 'comment': text, 'rationale': 'Aporta y pregunta.',
                   'citations': ['LI-07-M005-K05', 'LI-03-M006-K02'], 'claims_needing_evidence': [], 'risks': []}
            return {'text': json.dumps(out), 'model': 'claude-opus-5-5'}
        with patch('knowledge.providers.claude', side_effect=claude):
            yield

    # -- steps (production code only)
    def buyers(self, variants):
        """Elegidos y seguidos: un buscador los encuentra, el clasificador dice «comprador», la web confirma la etapa y
        Gustavo aprueba cada RED-01."""
        people = {v: self.fake.seed_person(PEOPLE[v][0], PEOPLE[v][1], headline=f'Founder & CEO at {PEOPLE[v][1].split()[0]} Labs',
                                           search='founder pre-seed', location='Austin, Texas') for v in variants}
        self.job('discover_network')
        stop = self.providers()
        try:
            for _ in range(len(people)):
                self.job('classify_contacts')
                if not Contact.objects.filter(classification__stage_check__state='pending').exists():
                    break
        finally:
            stop()
        contacts = {v: Contact.objects.get(account=self.account, provider_user_id=p['id']) for v, p in people.items()}
        for _ in range(len(people)):
            self.job('plan_network')
            for contact in contacts.values():
                if ActionProposal.objects.filter(contact=contact, capability='RED-01', state='proposed').exists():
                    self.approve_open(contact, 'RED-01')
            if all(c.stage == 'followed' for c in Contact.objects.filter(pk__in=[c.pk for c in contacts.values()])):
                break
        return {v: Contact.objects.get(pk=c.pk) for v, c in contacts.items()}

    def seed_post(self, user, text=None, hours_ago=3, suffix='cal'):
        """Un post reciente de esa persona en LinkedIn (el conector simulado); nadie lo guardó todavía."""
        pid = f'activity:{user["public_identifier"]}-{suffix}'
        at = timezone.now() - timedelta(hours=hours_ago)
        self.fake.state['posts'][pid] = {'id': pid, 'share_url': 'https://www.linkedin.com/feed/update/urn:li:' + pid,
                                         'text': text or CASE['input']['post'], 'created_at': at.isoformat(), 'author': user,
                                         'comments_counter': 0, 'reactions_counter': [], 'reposts_counter': 0,
                                         'user_reacted': False, 'is_repost': False}
        self.fake.state['comments'][pid] = []
        return pid

    def observe(self):
        jobs.enqueue_operation(self.bot, 'observe', {'account': str(self.account.id), 'limit': 5, 'referents': []},
                               request_id=uuid.uuid4())
        self.drain()

    def stored(self, pid):
        """El post como lo guardó la lectura; si la lectura no lo trajo, como lo dejaría hoy la observación a mano
        (BuyerPathBase.their_post), para medir el resto del camino."""
        post = ObservedPost.objects.filter(account=self.account, provider_post_id=pid).first()
        if post:
            return post, True
        raw = self.fake.state['posts'][pid]
        post = ObservedPost.objects.create(account=self.account, provider_post_id=pid, author_name=raw['author']['display_name'],
                                           author_provider_id=raw['author']['id'], text=raw['text'], share_url=raw['share_url'],
                                           posted_at=raw['created_at'])
        return post, False

    def draft(self, post):
        if not ActionProposal.objects.filter(post=post, capability='INT-03').exists():
            jobs.enqueue_operation(self.bot, 'propose_comment', {'post': str(post.id)}, request_id=uuid.uuid4())
            self.drain()

    def gate_and_write(self, proposal):
        proposal = autopiloto.policy_review(ActionProposal.objects.get(pk=proposal.pk))
        if proposal.state == 'approved':
            operador.execute(self.gustavo, proposal.id)
        return ActionProposal.objects.get(pk=proposal.pk)

    def outcome(self, post):
        """Qué pasó con el comentario de ese post: publicado, o quién lo paró («reglas» o «juez»)."""
        proposal = ActionProposal.objects.filter(post=post, capability='INT-03').order_by('-created_at').first()
        if proposal is None:
            return {'publicado': False, 'stopped_by': 'sin_borrador', 'proposal': None}
        if proposal.state == 'proposed':
            proposal = self.gate_and_write(proposal)
        if proposal.state == 'confirmed':
            stopped = None
        elif proposal.state == 'discarded':
            stopped = 'juez' if (proposal.review or {}).get('decision') == 'discard' else 'reglas'
        else:
            stopped = 'otro'
        return {'publicado': proposal.state == 'confirmed', 'stopped_by': stopped, 'proposal': proposal}

    def messages_sent(self):
        """Mensajes privados escritos por la cuenta: el equipo nunca envía uno (INB-08)."""
        return sum(m['is_sender'] for chat in self.fake.state['chats'].values() for m in chat['messages'])

    def warm(self, variants):
        """Los compradores de esas variantes, sus posts leídos (o guardados a mano si la lectura no los trae), la propuesta
        del autopiloto, los borradores y la compuerta. Devuelve lo observable."""
        contacts = self.buyers(variants)
        pids = {v: self.seed_post(self.fake.state['users'][c.provider_user_id]) for v, c in contacts.items()}
        self.texts.update({PEOPLE[v][1]: comment(v) for v in variants})
        self.observe()
        posts, read = {}, {}
        for v, pid in pids.items():
            posts[v], read[v] = self.stored(pid)
        with self.drafter(), self.lead():
            autopiloto._propose(self.bot, self.account, timezone.now())
            queued = Job.objects.filter(kind='propose_comment', state='queued').first()
            proposed = bool(queued and ObservedPost.objects.filter(pk=queued.params['post'], referent__isnull=True,
                                                                   author_provider_id__in=[c.provider_user_id for c in contacts.values()]).exists())
            self.drain()
            for post in posts.values():
                self.draft(post)
            outcomes = {v: self.outcome(post) for v, post in posts.items()}
        return {'contacts': contacts, 'posts': posts, 'read': read, 'proposed': proposed, 'outcomes': outcomes}

    def referent(self, text):
        """El mismo texto en el post de un referente: hoy se publica y la metodología no lo toca."""
        operador.add_referent(self.gustavo, self.account, 'https://www.linkedin.com/in/referente-ai/', 'Habla de producto')
        pid = self.seed_post(self.fake.state['users']['referente-ai'], hours_ago=1, suffix='ref')
        self.texts[REFERENT] = text
        self.observe()
        post = ObservedPost.objects.get(account=self.account, provider_post_id=pid)
        with self.drafter(), self.lead():
            self.draft(post)
            return self.outcome(post), post


class WarmupCommentCaseTests(WarmupCommentBase):
    """Las variantes de BIB-09-comentario-calentamiento. Línea base: docs/linea-base-comentario-calentamiento.md."""

    @expectedFailure  # Línea base: observe solo lee referentes y _propose solo propone posts de referentes activos.
    def test_flow_the_posts_of_a_warming_buyer_are_read_and_proposed(self):
        run = self.warm(['C1'])
        self.assertTrue(run['read']['C1'])
        self.assertIsNone(run['posts']['C1'].referent_id)
        self.assertTrue(run['proposed'])

    def test_c1_a_concrete_contribution_and_one_question_is_published(self):
        run = self.warm(['C1'])
        self.assertTrue(run['outcomes']['C1']['publicado'], run['outcomes']['C1']['proposal'].risks)
        self.assertEqual(self.fake.list_comments(run['posts']['C1'].provider_post_id)[0]['text'], comment('C1'))
        self.assertEqual(self.messages_sent(), 0)

    @expectedFailure  # Línea base: los agentes no pueden cargar unidades de las clases 07 y 10.
    def test_c1_the_draft_loads_the_warm_up_units(self):
        self.warm(['C1'])
        context = self.drafts[0]['context']
        for uid in operador.WARMUP_COMMENT_UNITS:
            self.assertIn(uid, context)

    @expectedFailure  # Línea base: no hay regla de aplauso; lo para el líder (aporta) después de pagar su revisión.
    def test_c2_applause_is_stopped_by_the_rules(self):
        run = self.warm(['C2'])
        self.assertEqual((run['outcomes']['C2']['publicado'], run['outcomes']['C2']['stopped_by']), (False, 'reglas'))

    def test_c3_selling_is_stopped_by_the_rules(self):
        run = self.warm(['C3'])
        self.assertEqual((run['outcomes']['C3']['publicado'], run['outcomes']['C3']['stopped_by']), (False, 'reglas'))

    @expectedFailure  # Línea base: la regla de longitud es 40–900 caracteres, no 25–40 palabras.
    def test_c4_more_than_40_words_is_stopped_by_the_rules(self):
        run = self.warm(['C4'])
        self.assertEqual((run['outcomes']['C4']['publicado'], run['outcomes']['C4']['stopped_by']), (False, 'reglas'))

    @expectedFailure  # Línea base: ninguna regla exige la pregunta final.
    def test_c5_without_a_question_is_stopped_by_the_rules(self):
        run = self.warm(['C5'])
        self.assertEqual((run['outcomes']['C5']['publicado'], run['outcomes']['C5']['stopped_by']), (False, 'reglas'))

    @expectedFailure  # Línea base: «aporta» acepta una pregunta concreta sin aporte propio.
    def test_c6_a_question_without_an_own_contribution_is_stopped_by_the_judge(self):
        run = self.warm(['C6'])
        self.assertEqual((run['outcomes']['C6']['publicado'], run['outcomes']['C6']['stopped_by']), (False, 'juez'))

    def test_r_the_same_text_without_a_question_on_a_referent_post_still_goes_out(self):
        outcome, _ = self.referent(comment('C5'))
        self.assertTrue(outcome['publicado'], outcome['proposal'].risks)

    def run_case(self):
        """Todas las variantes con las funciones de producción, calificadas con grade_course_case."""
        run = self.warm(list(VARIANTS))
        result = {'leido': all(run['read'].values()), 'propuesto': run['proposed'],
                  'borrador_con_metodologia': any('LI-07-M005-K05' in d['context'] for d in self.drafts if d['author'] == PEOPLE['C1'][1])}
        for v in VARIANTS:
            result[f'{v}_publicado'] = run['outcomes'][v]['publicado']
            result[f'{v}_stopped_by'] = run['outcomes'][v]['stopped_by']
        outcome, _ = self.referent(comment('R'))
        result.update(R_publicado=outcome['publicado'], mensajes_enviados=self.messages_sent())
        grounding = run['outcomes']['C1']['proposal'].review or {}
        result['course_citations'] = grounding.get('course_citations', [])
        result = {k: v for k, v in result.items() if k in CASE['expected'] or k == 'course_citations'}
        return evaluaciones.grade_course_case('comentario_calentamiento', result, grounding), result

    @expectedFailure  # Línea base: sin lectura, propuesta, reglas ni preguntas del calentamiento.
    def test_the_case_passes_with_production_functions(self):
        grade, result = self.run_case()
        self.assertTrue(grade['passed'], (grade['errors'], result))

    @expectedFailure  # Línea base: la metodología no está activada.
    def test_the_case_loads_whole_versioned_sources_and_rejects_wrong_behaviour(self):
        context, grounding = evaluaciones.course_case_context('comentario_calentamiento')
        self.assertIn('limits_errors', context)
        self.assertEqual(grounding['course_missing'], [])
        result = dict(CASE['expected'], course_citations=CASE['required'])
        self.assertTrue(evaluaciones.grade_course_case('comentario_calentamiento', result, grounding)['passed'])
        self.assertFalse(evaluaciones.grade_course_case('comentario_calentamiento', dict(result, C2_publicado=True), grounding)['passed'])
        self.assertFalse(evaluaciones.grade_course_case('comentario_calentamiento', dict(result, mensajes_enviados=1), grounding)['passed'])
        self.assertFalse(evaluaciones.grade_course_case('comentario_calentamiento', dict(CASE['expected'], course_citations=['LI-07-V001-K01']),
                                                        grounding)['passed'])
