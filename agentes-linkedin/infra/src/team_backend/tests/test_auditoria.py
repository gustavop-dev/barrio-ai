"""Phase 1 of the AI architecture audit (docs/auditoria-arquitectura-ia.md): E1–E6 and the worker lanes (B1)."""
import json
import os
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.management import CommandError, call_command
from django.utils import timezone

from knowledge import db, providers
from team_backend import autopiloto, capturas, editorial, jobs, operador
from team_backend.models import ActionExecution, ActionProposal, Capture, Contact, EditorialPiece, Worker
from team_backend.tests.fakes import FakeAnthropic, message
from team_backend.tests.test_capturas import MediaMixin
from team_backend.tests.test_operador import OperatorBase
from team_backend.tests.test_publicacion import EditorialBase, answers
from team_backend.tests.test_red import NetworkBase


class ClaudeOutputCapTests(OperatorBase):
    """E1, E4, E5: thinking counts against max_tokens, so a cut answer must say so; cache reads are priced per model."""

    def ledger(self):
        with db.connect() as c:
            return c.execute('SELECT status,actual_usd FROM usage_ledger ORDER BY created_at').fetchall()

    def call(self,outcome,**kwargs):
        env={'LIVE_PROVIDERS':'true','ANTHROPIC_API_KEY':'test-only','ANTHROPIC_LIMIT_USD':'5','ANTHROPIC_MODEL':'claude-opus-5-5'}
        with patch.dict(os.environ,env),patch('knowledge.providers.anthropic_client',return_value=FakeAnthropic(outcome)) as client:
            return providers.claude('Sistema','Tarea',purpose='prueba',**kwargs),client.return_value

    def test_a_structured_answer_cut_by_max_tokens_is_an_explicit_error_and_is_still_settled(self):
        cut=message(text='{"destino": "po',output_tokens=2000,stop_reason='max_tokens')
        with self.assertRaisesRegex(ValueError,r'agotó max_tokens \(2000\).*prueba'):
            self.call(cut,max_tokens=2000,output_schema={'type':'object'})
        self.assertEqual([row['status'] for row in self.ledger()],['complete'])  # billed: the spend is recorded

    def test_free_text_cut_by_max_tokens_is_returned(self):
        answer,_=self.call(message(text='Texto largo',stop_reason='max_tokens'),max_tokens=500)
        self.assertEqual(answer['stop_reason'],'max_tokens')

    def test_cache_reads_use_the_price_of_the_model(self):
        self.assertEqual(providers.cache_read_multiplier('claude-opus-5-5'),Decimal('0.05'))
        self.assertEqual(providers.cache_read_multiplier('claude-sonnet-5-5'),Decimal('0.1'))
        answer,_=self.call(message(input_tokens=0,output_tokens=0,cache_read=1_000_000))
        self.assertAlmostEqual(answer['estimated_usd'],0.20)  # Opus 5.5 reads cache at $0.20/M, not $0.40

    def test_editorial_stages_leave_room_for_thinking(self):
        for name,stage in editorial.STAGES.items():
            self.assertGreaterEqual(stage[4],12000,name)

    def test_capture_routing_uses_low_effort_and_room_for_thinking(self):
        def fake(system,message,max_tokens=None,output_schema=None,effort=None,purpose='agent-run',model=None):
            self.assertEqual((max_tokens,effort,purpose),(2000,'low','capture-route'))
            return {'text':json.dumps({'destino':'dato','motivo':'Es un dato sobre él.'})}
        with patch('knowledge.providers.claude',side_effect=fake):
            self.assertEqual(capturas.classify('Trabajé cinco años en banca.',[])[0],'dato')


class NetworkClassifierCapTests(NetworkBase):
    def test_the_classifier_sets_its_effort_and_leaves_room_for_thinking(self):
        ana=self.contact('founder-ana','Ana Founder',stage='candidate')
        Contact.objects.filter(pk=ana.pk).update(classification={})
        seen={}
        def fake(system,message,max_tokens=None,output_schema=None,effort=None,purpose='agent-run',model=None):
            seen.update(max_tokens=max_tokens,effort=effort)
            people=json.loads(message)['people']
            return {'text':json.dumps({'contacts':[{'id':p['id'],'fit':True,'role':'comprador','modality':'projectapp','affinity':'desconocida',
                                                    'reason':'r','confidence':0.9} for p in people]}),'model':model}
        with patch('knowledge.providers.claude',side_effect=fake):self.job('classify_contacts')
        self.assertEqual(seen,{'max_tokens':16000,'effort':'medium'})


class CommentDraftRoomTests(OperatorBase):
    """E2: a paid draft only when a write slot is left after the comments already waiting for one."""

    def test_no_new_draft_while_approved_comments_fill_the_daily_cap(self):
        first_post,second_post=self.observed()
        with patch.dict(os.environ,{'OPERATOR_DAILY_LIMITS':'INT-03=1','OPERATOR_AUTHOR_COOLDOWN_HOURS':'0'}):
            waiting=operador.create_proposal(self.gustavo,first_post,'INT-03',{'text':'Evals are where the work hides. Which failure do you test first?'},
                                             citations=['LI-03-M006-K02'],source='agent')
            ActionProposal.objects.filter(pk=waiting.pk).update(state='approved')
            self.assertEqual(autopiloto._propose(self.gustavo,self.account,timezone.now()),0)
            ActionProposal.objects.filter(pk=waiting.pk).update(state='discarded')
            self.assertEqual(autopiloto._propose(self.gustavo,self.account,timezone.now()),1)


class NoWriteExecutionTests(NetworkBase):
    """E3: an execution that found nothing to write uses neither the daily cap nor the spacing."""

    def test_an_already_followed_person_does_not_use_the_follow_cap(self):
        ana=self.contact('founder-ana','Ana Founder')
        with patch.dict(os.environ,{'OPERATOR_DAILY_LIMITS':'RED-01=1'}):
            self.job('plan_network')
            self.fake.state['network'][ana.provider_user_id]['is_following']=True  # followed by hand meanwhile
            proposal=self.approve_open(ana,'RED-01')
            self.assertEqual(proposal.state,'confirmed')
            self.assertFalse(proposal.execution.wrote)
            self.assertEqual(operador.capacity_left(self.account,'RED-01'),1)
            self.assertEqual(self.fake.state['writes'],0)

    def test_spacing_counts_only_executions_that_wrote(self):
        ana=self.contact('founder-ana','Ana Founder')
        self.job('plan_network')
        proposal=ActionProposal.objects.get(contact=ana,capability='RED-01')
        execution=ActionExecution.objects.create(proposal=proposal,idempotency_key='k1',provider='fake',executed_by=self.gustavo,
                                                 state='failed',error_kind='already_connected',wrote=False)
        with patch.dict(os.environ,{'OPERATOR_MIN_SPACING_SECONDS':'1200'}):
            self.assertTrue(operador.spacing_ok(self.account))
            ActionExecution.objects.filter(pk=execution.pk).update(wrote=True)
            self.assertFalse(operador.spacing_ok(self.account))


class IdeaReleaseTests(MediaMixin,EditorialBase):
    """E6: Gustavo's idea is spent only by a piece that goes out."""

    def setUp(self):
        super().setUp();self.use_media()

    def idea(self):
        return Capture.objects.create(created_by=self.gustavo,note='Decidir qué medir antes de construir.',purpose='post',state='idea')

    def test_an_idea_returns_to_the_table_when_the_verifier_blocks_its_piece(self):
        idea=self.idea()
        plan=answers(verdict='blocked');plan['director']=dict(plan['director'],ideas_used=[str(idea.id)])
        piece=self.plan(plan)
        self.assertEqual(piece.state,'blocked')
        idea.refresh_from_db()
        self.assertEqual(idea.state,'idea')
        self.assertNotIn('used_in',idea.routed_to or {})
        self.assertEqual(idea.outcome['kind'],'idea')
        self.assertIn('el verificador la bloqueó',idea.outcome['text'])
        self.assertEqual(capturas.ideas_for_director()[0]['id'],str(idea.id))  # offered again

    def test_an_idea_stays_used_when_its_piece_is_ready_and_returns_when_it_is_vetoed(self):
        idea=self.idea()
        plan=answers();plan['director']=dict(plan['director'],ideas_used=[str(idea.id)])
        piece=self.plan(plan)
        self.assertEqual(piece.state,'ready')
        idea.refresh_from_db();self.assertEqual(idea.state,'usado')
        proposal=ActionProposal.objects.get(piece=piece)
        if proposal.state not in ('proposed','approved'):ActionProposal.objects.filter(pk=proposal.pk).update(state='approved')
        operador.reject(self.gustavo,proposal.id,'No me convence')
        idea.refresh_from_db()
        self.assertEqual(idea.state,'idea');self.assertIn('la vetaste',idea.outcome['text'])

    def test_a_skipped_piece_releases_the_idea(self):
        idea=self.idea()
        plan=answers(decision='skip');plan['director']=dict(plan['director'],ideas_used=[str(idea.id)])
        piece=self.plan(plan)
        self.assertEqual(piece.state,EditorialPiece.State.SKIPPED)
        idea.refresh_from_db();self.assertEqual(idea.state,'idea')


class WorkerLaneTests(OperatorBase):
    """B1: LinkedIn executions run on their own lane and never wait behind LLM or transcription work."""

    def test_each_lane_claims_only_its_jobs(self):
        slow,_=jobs.enqueue_operation(self.gustavo,'observe',{'account':str(self.account.id),'limit':5})
        write,_=jobs.enqueue_operation(self.gustavo,'reconcile_action',{'proposal':'00000000-0000-0000-0000-000000000000'})
        actions=Worker.objects.create(lane='acciones');general=Worker.objects.create(lane='general')
        self.assertEqual(jobs.claim(actions).id,write.id)  # the write skips ahead of the older slow job
        self.assertIsNone(jobs.claim(actions))
        self.assertEqual(jobs.claim(general).id,slow.id)
        self.assertIsNone(jobs.claim(general))

    def test_the_default_lane_takes_everything(self):
        job,_=jobs.enqueue_operation(self.gustavo,'reconcile_action',{'proposal':'00000000-0000-0000-0000-000000000000'})
        self.assertEqual(self.worker.lane,'todas')
        self.assertEqual(jobs.claim(self.worker).id,job.id)

    def test_health_is_checked_per_lane(self):
        Worker.objects.all().update(stopped_at=timezone.now())
        Worker.objects.create(lane='general')
        call_command('worker_health','--lane','general')
        call_command('worker_health')
        with self.assertRaisesRegex(CommandError,'carril acciones'):
            call_command('worker_health','--lane','acciones')
        Worker.objects.filter(lane='general').update(last_seen=timezone.now()-timedelta(hours=1))
        with self.assertRaises(CommandError):call_command('worker_health','--lane','general')
