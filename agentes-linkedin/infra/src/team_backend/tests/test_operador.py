"""Behaviour of the account operator: one approved version, one execution, no blind retries."""
import hashlib
import json
import os
import uuid
from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth.models import Permission, User
from django.db import connection
from django.test import SimpleTestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient
from knowledge import db
from team_backend import jobs, operador, orquestacion
from team_backend.connectors import ConnectorError, FakeConnector, public_identifier
from team_backend.models import (ActionExecution, ActionOutcome, ActionProposal, ApiCredential, AuditEvent, ConnectorAccount, CycleLedger, Job,
                                 ObservedPost, Worker)

ALL=['access_knowledge','run_agents','use_paid_providers','operate_linkedin','approve_actions','execute_actions','manage_jobs']

class OperatorBase(TransactionTestCase):
    def setUp(self):
        self.assertTrue(connection.settings_dict['NAME'].startswith('test_'))
        env=patch.dict(os.environ,{'LIVE_PROVIDERS':'false','OPERATOR_ALLOW_FAKE':'true',
                                   'OPERATOR_DAILY_LIMITS':'','OPERATOR_WEEKLY_LIMITS':'','OPERATOR_PAUSED':'false',
                                   'OPERATOR_WINDOW':'00:00-24:00','OPERATOR_MIN_SPACING_SECONDS':'0','OPERATOR_AUTONOMY':'',
                                   'OPERATOR_ALERT_WEBHOOK':'','OPERATOR_DAILY_LLM_USD':'1','OPERATOR_DAILY_PROPOSALS':'6',
                                   # The weekly summary depends on the real weekday; test_resumen_semanal turns it on.
                                   'WEEKLY_SUMMARY_ENABLED':'false',
                                   # So does the monthly review (first Monday); test_revision_mensual turns it on.
                                   'MONTHLY_REVIEW_ENABLED':'false',
                                   # INT-04 reads the comments of every confirmed own post; test_respuestas turns it on.
                                   'REPLIES_ENABLED':'false',
                                   # The GASP type of a day depends on the real weekday; test_estrategia turns it on.
                                   'STRATEGY_ENABLED':'false'})
        env.start();self.addCleanup(env.stop)
        self.weekend_patch=patch('team_backend.operador.is_weekend',return_value=False)
        self.weekend_patch.start();self.addCleanup(self.weekend_patch.stop)
        # Legacy scenarios exercise their own gates; BAR-15 tests restore the real durable scheduler.
        self.spacing_patch=patch('team_backend.operador.reserve_spacing')
        self.spacing_patch.start();self.addCleanup(self.spacing_patch.stop)
        self.day_schedule_patch=patch('team_backend.operador.prepare_day_schedule')
        self.day_schedule_patch.start();self.addCleanup(self.day_schedule_patch.stop)
        network=patch('httpx.post',side_effect=AssertionError('Network forbidden in operator tests'))
        network.start();self.addCleanup(network.stop)
        FakeConnector.reset();self.addCleanup(FakeConnector.reset)
        with db.connect() as c:
            c.execute('TRUNCATE memory,runs,usage_ledger,embedding_cache,unit_evidence,edges,chunks,units,source_files,evidence,unit_revisions CASCADE')
            c.execute("INSERT INTO source_files(path,sha256) VALUES('fixture','abc')")
            c.execute('''INSERT INTO units(id,session,title,original,sha256,source_path,pointer,metadata)
                VALUES('LI-03-M006-K02',3,'Comentarios que aportan','{"title":"Opinión, fundamento y apertura"}','abc','fixture','/units/0','{}')''')
        # Synthetic corpus only; never import private course text into fixtures.
        role_units=set(operador.COMMENT_UNITS+operador.REFERENTS_UNITS+operador.ANALYSIS_UNITS+operador.NETWORK_UNITS+operador.INBOX_UNITS+operador.LEAD_UNITS
                       +operador.FIRST_MESSAGE_UNITS+operador.WARMUP_COMMENT_UNITS)
        with db.connect() as c:
            for uid in role_units:
                c.execute('''INSERT INTO units(id,session,title,original,sha256,source_path,pointer,metadata)
                    VALUES(%s,%s,%s,'{"title":"Synthetic course fixture","limits_errors":"Do not infer facts or authority"}',
                    'fixture-hash','fixture','/units/0','{}') ON CONFLICT(id) DO NOTHING''',(uid,int(uid[3:5]),uid))
        self.addCleanup(self.drop_outbound_units)
        self.gustavo=User.objects.create_user('gustavo-test',password='local-only-password')
        self.grant(self.gustavo,*ALL)
        self.service=User.objects.create_user('service-test')
        self.grant(self.service,'access_knowledge','run_agents','operate_linkedin')
        token='service-token-test'
        ApiCredential.objects.create(name='svc',user=self.service,digest=hashlib.sha256(token.encode()).hexdigest())
        self.api=APIClient();self.api.credentials(HTTP_AUTHORIZATION='Bearer '+token)
        self.human=APIClient();self.human.force_login(self.gustavo)
        self.fake=FakeConnector('acc_fake1')
        self.fake.seed_user('referente-ai','Ana Referente',posts=['Shipping AI agents to production is mostly evals.','Second post'])
        self.account=operador.register_account(self.gustavo,'fake','acc_fake1','Cuenta simulada')
        self.worker=Worker.objects.create()

    def drop_outbound_units(self):
        # The class 07–12 rows seeded for activated methodologies (FIRST_MESSAGE_UNITS) never outlive the test: a
        # migration test that goes back past 0045 restores CHECK(session BETWEEN 1 AND 6) and fails on them.
        with db.connect() as c:c.execute('DELETE FROM units WHERE session>6')

    def grant(self,user,*codes):
        user.user_permissions.add(*Permission.objects.filter(content_type__app_label='team_backend',codename__in=codes))
        for attr in ['_perm_cache','_user_perm_cache','_group_perm_cache']:
            if hasattr(user,attr):delattr(user,attr)

    def observed(self):
        operador.add_referent(self.gustavo,self.account,'https://www.linkedin.com/in/referente-ai/','Habla de agentes en producción')
        job,_=jobs.enqueue_operation(self.gustavo,'observe',{'account':str(self.account.id),'limit':5})
        jobs.process_one(self.worker)
        return list(ObservedPost.objects.order_by('provider_post_id'))

    def proposal(self,post,text='Evals are where most of the work hides. Which failure modes do you test first?'):
        response=self.api.post('/api/v1/operador/actions',{'post':str(post.id),'capability':'INT-03','payload':{'text':text}},format='json')
        self.assertEqual(response.status_code,201,response.content)
        return response.json()

    def approve(self,action):
        response=self.human.post(f'/api/v1/operador/actions/{action["id"]}/approve',{'expected_hash':action['payload_hash']},format='json')
        self.assertEqual(response.status_code,202,response.content)
        jobs.process_one(self.worker)
        return ActionProposal.objects.get(id=action['id'])


class OperatorTests(OperatorBase):
    def test_observe_reads_posts_once_and_dedupes(self):
        """DESC-04 is read-only and idempotent: repeated observation does not duplicate posts."""
        posts=self.observed()
        self.assertEqual(len(posts),2)
        job,_=jobs.enqueue_operation(self.gustavo,'observe',{'account':str(self.account.id),'limit':5})
        jobs.process_one(self.worker);job.refresh_from_db()
        self.assertEqual((job.state,job.result_status),('complete','observed:0+2'))
        self.assertEqual(ObservedPost.objects.count(),2)
        self.assertEqual(self.fake.state['writes'],0)

    def test_service_token_prepares_but_never_decides(self):
        """A Bearer credential can propose; approving, pausing or resolving needs a human session."""
        action=self.proposal(self.observed()[0])
        self.assertEqual(self.api.post(f'/api/v1/operador/actions/{action["id"]}/approve',{'expected_hash':action['payload_hash']},format='json').status_code,403)
        self.assertEqual(self.api.post(f'/api/v1/operador/accounts/{self.account.id}/pause',{'paused':False},format='json').status_code,403)
        self.assertEqual(ActionProposal.objects.get(id=action['id']).state,'proposed')
        self.assertEqual(Job.objects.filter(kind='execute_action').count(),0)

    def test_approved_comment_executes_once_and_is_confirmed(self):
        """INT-03: the exact approved text is written once and confirmed by reading LinkedIn back."""
        post=self.observed()[0];action=self.proposal(post)
        wrong=self.human.post(f'/api/v1/operador/actions/{action["id"]}/approve',{'expected_hash':'0'*64},format='json')
        self.assertEqual(wrong.status_code,409)
        proposal=self.approve(action)
        self.assertEqual(proposal.state,'confirmed')
        execution=proposal.execution
        self.assertTrue(execution.external_id.startswith('comment:'))
        self.assertEqual(self.fake.state['writes'],1)
        self.assertEqual(self.fake.list_comments(post.provider_post_id)[0]['text'],action['payload']['text'])
        # Executing again, re-requesting or re-approving never writes a second comment.
        self.assertEqual(operador.execute(self.gustavo,proposal.id).id,execution.id)
        self.assertEqual(self.human.post(f'/api/v1/operador/actions/{action["id"]}/execute').status_code,403)
        self.assertEqual(self.human.post(f'/api/v1/operador/actions/{action["id"]}/approve',{'expected_hash':action['payload_hash']},format='json').status_code,409)
        self.assertEqual(self.fake.state['writes'],1)
        self.assertTrue(AuditEvent.objects.filter(action='operator.execution_confirmed',target=str(proposal.id)).exists())

    def test_revision_invalidates_the_previous_version(self):
        post=self.observed()[0];action=self.proposal(post)
        revised=self.api.post(f'/api/v1/operador/actions/{action["id"]}/revise',{'payload':{'text':'A sharper take.'}},format='json').json()
        self.assertEqual(ActionProposal.objects.get(id=action['id']).state,'superseded')
        self.assertEqual(revised['version'],2)
        stale=self.human.post(f'/api/v1/operador/actions/{revised["id"]}/approve',{'expected_hash':action['payload_hash']},format='json')
        self.assertEqual(stale.status_code,409)
        self.assertEqual(self.approve(revised).payload['text'],'A sharper take.')

    def test_single_open_action_per_post(self):
        post=self.observed()[0];self.proposal(post)
        again=self.api.post('/api/v1/operador/actions',{'post':str(post.id),'capability':'INT-03','payload':{'text':'Otro'}},format='json')
        self.assertEqual(again.status_code,409)

    def test_uncertain_write_is_never_retried_and_reconciles(self):
        """A timeout after sending leaves the action uncertain; reconciliation reads, never writes."""
        first,second=self.observed()
        self.fake.state['fail_next']='uncertain_applied'
        applied=self.approve(self.proposal(first))
        self.assertEqual(applied.state,'uncertain');self.assertEqual(self.fake.state['writes'],1)
        jobs.enqueue_operation(self.gustavo,'reconcile_action',{'proposal':str(applied.id)});jobs.process_one(self.worker)
        applied.refresh_from_db();self.assertEqual(applied.state,'confirmed');self.assertEqual(self.fake.state['writes'],1)
        self.fake.state['fail_next']='uncertain_not_applied'
        lost=self.approve(self.proposal(second))
        jobs.enqueue_operation(self.gustavo,'reconcile_action',{'proposal':str(lost.id)});jobs.process_one(self.worker)
        lost.refresh_from_db();self.assertEqual(lost.state,'uncertain');self.assertEqual(self.fake.state['writes'],1)
        resolved=self.human.post(f'/api/v1/operador/actions/{lost.id}/resolve',{'outcome':'failed','note':'No aparece en el hilo tras 1 h'},format='json')
        self.assertEqual(resolved.json()['state'],'failed')

    def test_rate_limit_pauses_the_account_and_blocks_next_writes(self):
        """ADM-04: a 429 or restriction stops all writes on the account until a human resumes it."""
        first,second=self.observed()
        self.fake.state['fail_next']='rate_limit'
        failed=self.approve(self.proposal(first))
        self.assertEqual(failed.state,'failed');self.assertEqual(failed.execution.http_status,429)
        self.account.refresh_from_db();self.assertTrue(self.account.paused)
        blocked=self.approve(self.proposal(second))
        job=Job.objects.filter(kind='execute_action',params__proposal=str(blocked.id)).get()
        self.assertEqual((job.state,job.result_status),('failed','blocked'))
        self.assertEqual(blocked.state,'approved')
        self.assertEqual(self.fake.state['writes'],0)

    def test_daily_limit_and_global_pause_send_nothing(self):
        first,second=self.observed()
        with patch.dict(os.environ,{'OPERATOR_DAILY_LIMITS':'INT-03=1'}):
            self.assertEqual(self.approve(self.proposal(first)).state,'confirmed')
            capped=self.approve(self.proposal(second))
        self.assertEqual(capped.state,'approved')
        with patch.dict(os.environ,{'OPERATOR_PAUSED':'true'}):
            with self.assertRaises(operador.OperatorBlocked):operador.execute(self.gustavo,capped.id)
        self.assertEqual(self.fake.state['writes'],1)
        # Once the gate is lifted the same approval can be executed; only once.
        self.assertEqual(self.human.post(f'/api/v1/operador/actions/{capped.id}/execute').status_code,202)
        jobs.process_one(self.worker);capped.refresh_from_db()
        self.assertEqual(capped.state,'confirmed');self.assertEqual(self.fake.state['writes'],2)
        self.assertEqual(self.human.post(f'/api/v1/operador/actions/{capped.id}/execute').status_code,403)

    def test_existing_identical_comment_is_not_duplicated(self):
        post=self.observed()[0];action=self.proposal(post,'Already said this.')
        self.fake.state['comments'][post.provider_post_id].append({'id':'comment:manual','text':'already  said this.','is_sender':True,
                                                                   'created_at':None,'author':{}})
        proposal=self.approve(action)
        self.assertEqual((proposal.state,proposal.execution.external_id),('confirmed','comment:manual'))
        self.assertEqual(self.fake.state['writes'],0)

    def test_reaction_is_confirmed_by_reading_back(self):
        post=self.observed()[0]
        action=self.api.post('/api/v1/operador/actions',{'post':str(post.id),'capability':'INT-02','payload':{'reaction':'linkedin_insightful'}},format='json').json()
        self.assertEqual(self.approve(action).state,'confirmed')
        self.assertTrue(self.fake.get_post(post.provider_post_id)['user_reacted'])
        invalid=self.api.post('/api/v1/operador/actions',{'post':str(post.id),'capability':'INT-02','payload':{'reaction':'like'}},format='json')
        self.assertEqual(invalid.status_code,400)

    def test_agent_proposal_is_grounded_and_waits_for_approval(self):
        """The agent drafts; citations outside the context are dropped; nothing is executed."""
        post=self.observed()[0]
        answer={'decision':'comment','language':'en','comment':'Evals first, then tooling.','rationale':'Adds a concrete angle.',
                'citations':['LI-03-M006-K02','LI-99-X'],'claims_needing_evidence':[],'risks':[]}
        with patch('knowledge.providers.claude',return_value={'text':json.dumps(answer),'model':'claude-opus-5-5'}) as claude:
            job,_=jobs.enqueue_operation(self.gustavo,'propose_comment',{'post':str(post.id)});jobs.process_one(self.worker)
        job.refresh_from_db();self.assertEqual((job.state,job.result_status),('complete','proposed'))
        proposal=ActionProposal.objects.get(post=post)
        self.assertEqual((proposal.source,proposal.citations),('agent',['LI-03-M006-K02']))
        self.assertIn('El agente citó unidades fuera del contexto; se descartaron.',proposal.risks)
        self.assertEqual(claude.call_args.kwargs['output_schema'],operador.COMMENT_SCHEMA)
        self.assertEqual(self.fake.state['writes'],0)
        # A post that already has an open comment does not trigger a second paid draft.
        again,_=jobs.enqueue_operation(self.gustavo,'propose_comment',{'post':str(post.id)});jobs.process_one(self.worker)
        again.refresh_from_db();self.assertEqual(again.state,'failed')

    def test_agent_may_skip_and_paid_calls_stay_disabled(self):
        post,other=self.observed()
        skip={'decision':'skip','language':'en','comment':'','rationale':'Nada genuino que aportar.','citations':[],'claims_needing_evidence':[],'risks':[]}
        with patch('knowledge.providers.claude',return_value={'text':json.dumps(skip),'model':'claude-opus-5-5'}):
            jobs.enqueue_operation(self.gustavo,'propose_comment',{'post':str(post.id)});jobs.process_one(self.worker)
        self.assertEqual(ActionProposal.objects.get(post=post).state,'discarded')
        job,_=jobs.enqueue_operation(self.gustavo,'propose_comment',{'post':str(other.id)});jobs.process_one(self.worker)
        job.refresh_from_db()
        self.assertEqual(job.state,'failed');self.assertIn('Proveedores desactivados',job.error)

    def earlier_comment(self,author):
        """An own comment (INT-03) written four days ago on another post by `author`, measured at 72 h."""
        now=timezone.now()
        post=ObservedPost.objects.create(account=self.account,provider_post_id='urn:li:activity:earlier',author_provider_id=author,
                                         author_name='Ana Referente',text='An earlier post about evals.')
        proposal=ActionProposal.objects.create(account=self.account,post=post,capability='INT-03',payload={'text':'Which eval runs first?'},
                                               payload_hash='0'*64,state='confirmed')
        execution=ActionExecution.objects.create(proposal=proposal,provider='fake',executed_by=self.gustavo,state='confirmed',wrote=True,
                                                 idempotency_key=uuid.uuid4().hex,started_at=now-timedelta(days=4))
        ActionOutcome.objects.create(execution=execution,kind='72h',source='read',captured_at=now-timedelta(days=1),
                                     replies=2,reactions=3,author_replied=True)
        return execution

    def test_the_drafter_reads_how_earlier_comments_landed(self):
        """comment_outcomes reaches the model and the cycle ledger; with nothing measured the message stays as it was."""
        first,second=self.observed()
        answer={'decision':'comment','language':'en','comment':'Evals are where most of the work hides. Which failure mode do you test first?',
                'rationale':'Adds a concrete angle.','citations':['LI-03-M006-K02'],'claims_needing_evidence':[],'risks':[]}
        def draft(post):
            with patch('knowledge.providers.claude',return_value={'text':json.dumps(answer),'model':'claude-opus-5-5'}) as claude:
                job,_=jobs.enqueue_operation(self.gustavo,'propose_comment',{'post':str(post.id)});jobs.process_one(self.worker)
            job.refresh_from_db();self.assertEqual((job.state,job.result_status),('complete','proposed'))
            snapshots=CycleLedger.objects.get(cycle='red',key=str(job.id)).progress_ledger['snapshots']
            return json.loads(claude.call_args_list[0].args[1]),orquestacion.unpack(snapshots['comment_outcomes'])
        sent,frozen=draft(first)
        self.assertEqual(list(sent),['post','existing_comments','public_facts','private_guidance','orientation','referent_evidence',
                                     'comment_language','recent_own_comments'])
        self.assertIsNone(frozen)  # the ledger still proves the drafter received nothing
        execution=self.earlier_comment(first.author_provider_id)
        sent,frozen=draft(second)
        expected={'con_este_autor':[{'commented_at':execution.started_at.isoformat(),'replies':2,'reactions':3,'author_replied':True,'kind':'72h'}],
                  'ultimos_30_dias':{'measured':1,'with_reply':1,'author_replied':1}}
        self.assertEqual((sent['comment_outcomes'],frozen),(expected,expected))
        self.assertEqual(self.fake.state['writes'],0)

    def test_fake_connector_requires_explicit_flag(self):
        with patch.dict(os.environ,{'OPERATOR_ALLOW_FAKE':'false'}):
            with self.assertRaises(ConnectorError):FakeConnector('acc_fake1')


class SharedShapeTests(SimpleTestCase):
    """What every connector shares (connectors.py): a post's counters and the public identifier."""
    def test_real_post_payload_is_normalized(self):
        """Reactions may come as a per-type list to add up; user_reacted is a bool."""
        from team_backend.connectors import _post
        post=_post({'object':'Post','id':'7497','share_url':'https://www.linkedin.com/feed/update/x','text':'t',
                    'created_at':'2026-08-23T12:00:00.000Z','user_reacted':False,'comments_counter':2,'reposts_counter':0,
                    'reactions_counter':[{'reaction':'like','count':3},{'reaction':'celebrate','count':1}],'is_repost':False,
                    'author':{'id':'ACo1','display_name':'Ana','public_identifier':'ana'},'analytics':{'impressions_counter':321}})
        self.assertEqual((post['reactions_counter'],post['comments_counter'],post['user_reacted'],post['impressions']),(4,2,False,321))
        self.assertEqual(_post({'id':'x','reactions_counter':[],'user_reacted':True})['reactions_counter'],0)

    def test_identifier_rejects_names(self):
        with self.assertRaises(ValueError):public_identifier('Ana María López')


class AutopilotTests(OperatorBase):
    """Autonomous machine: observe → draft → policy approval → spaced execution → reconcile."""
    def setUp(self):
        super().setUp()
        from team_backend import autopiloto
        self.autopiloto=autopiloto
        self.bot=User.objects.create_user('barrio-autopiloto')
        self.grant(self.bot,'access_knowledge','run_agents','use_paid_providers','operate_linkedin','execute_actions')
        operador.add_referent(self.gustavo,self.account,'referente-ai','Habla de agentes en producción')

    def drain(self):
        while jobs.process_one(self.worker):pass

    def draft(self,text='Evals are where most of the work hides. Which failure mode do you test first in production?',citations=('LI-03-M006-K02',),claims=()):
        answer={'decision':'comment','language':'en','comment':text,'rationale':'Aporta un ángulo concreto.',
                'citations':list(citations),'claims_needing_evidence':list(claims),'risks':[]}
        return patch('knowledge.providers.claude',return_value={'text':json.dumps(answer),'model':'claude-opus-5-5'})

    def test_full_cycle_runs_without_a_human(self):
        report=self.autopiloto.tick(self.bot);self.drain()
        self.assertEqual(report['observe'],1);self.assertEqual(ObservedPost.objects.count(),2)
        with self.draft():
            self.assertEqual(self.autopiloto.tick(self.bot)['propose'],1);self.drain()
        proposal=ActionProposal.objects.get(source='agent')
        self.assertEqual(proposal.state,'proposed')
        report=self.autopiloto.tick(self.bot);self.drain()
        self.assertEqual((report['reviewed'],report['execute']),(1,1))
        proposal.refresh_from_db()
        self.assertEqual(proposal.state,'confirmed');self.assertIsNone(proposal.decided_by)
        self.assertIn(self.autopiloto.POLICY_VERSION,proposal.decision_note)
        self.assertEqual(self.fake.state['writes'],1)
        # Ticking again neither re-drafts the same post nor writes again.
        with self.draft():self.autopiloto.tick(self.bot);self.drain()
        self.assertEqual(ActionProposal.objects.filter(post=proposal.post).count(),1)
        self.assertEqual(self.fake.state['writes'],1)

    def test_policy_discards_pitch_links_and_unsupported_claims(self):
        posts=self.observed()
        bad=[('Great insight! We build agents at ProjectApp, DM me to talk about your roadmap.',()),
             ('Totally agree with this point, more here: https://example.com/agents and #AI tips for everyone.',()),
             ('In my last project we cut latency by 80% with exactly this approach for a big retailer.',('80% de latencia',))]
        for post,(text,claims) in zip(posts,bad[:2]):
            operador.create_proposal(self.gustavo,post,'INT-03',{'text':text})
        self.autopiloto.tick(self.bot)
        states=sorted(ActionProposal.objects.values_list('state',flat=True))
        self.assertEqual(states,['discarded','discarded'])
        reasons=sum((p.risks for p in ActionProposal.objects.all()),[])
        self.assertIn('Contiene pitch o petición de contacto',reasons);self.assertIn('Contiene enlaces',reasons)
        self.assertIn('Contiene hashtags',reasons)
        ActionProposal.objects.all().delete()
        with self.draft(text=bad[2][0],claims=bad[2][1]):
            jobs.enqueue_operation(self.bot,'propose_comment',{'post':str(posts[0].id)});self.drain()
        self.autopiloto.tick(self.bot);self.drain()
        self.assertEqual(ActionProposal.objects.get().state,'discarded')
        self.assertEqual(self.fake.state['writes'],0)

    @patch.dict(os.environ,{'OPERATOR_AUTHOR_COOLDOWN_HOURS':'0'})  # two posts by one referent; the cooldown has its own test
    def test_window_spacing_and_caps_hold_back_writes(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        first,second=self.observed()
        for post in (first,second):
            operador.create_proposal(self.gustavo,post,'INT-03',{'text':'A concrete, useful contribution to this conversation about evals.'})
        night=datetime(2026,11,6,3,0,tzinfo=ZoneInfo('America/Bogota'))
        with patch.dict(os.environ,{'OPERATOR_WINDOW':'07:00-21:00','OPERATOR_MIN_SPACING_SECONDS':'1200'}):
            self.assertEqual(self.autopiloto.tick(self.bot,now=night)['execute'],0)
            self.assertEqual(ActionProposal.objects.filter(state='approved').count(),2)
            with patch('team_backend.operador.within_window',return_value=True):
                self.autopiloto.tick(self.bot);self.drain()
                self.assertEqual(self.fake.state['writes'],1)
                self.assertEqual(self.autopiloto.tick(self.bot)['execute'],0)  # spacing not yet met
        with patch.dict(os.environ,{'OPERATOR_DAILY_LIMITS':'INT-03=1'}):
            self.assertEqual(self.autopiloto.tick(self.bot)['execute'],0)  # daily cap reached
        self.autopiloto.tick(self.bot);self.drain()
        self.assertEqual(self.fake.state['writes'],2)

    def test_expiry_budget_approval_mode_and_global_stop(self):
        from datetime import timedelta
        from django.utils import timezone
        first,second=self.observed()
        old=operador.create_proposal(self.gustavo,first,'INT-03',{'text':'A concrete, useful contribution to this conversation about evals.'})
        ActionProposal.objects.filter(pk=old.pk).update(created_at=timezone.now()-timedelta(hours=49))
        with patch.dict(os.environ,{'OPERATOR_AUTONOMY':'INT-03=approval'}):
            self.assertEqual(self.autopiloto.tick(self.bot)['expired'],1)
            human=operador.create_proposal(self.gustavo,second,'INT-03',{'text':'Another concrete and useful contribution about evals here.'})
            self.autopiloto.tick(self.bot)
            human.refresh_from_db();self.assertEqual(human.state,'proposed')
        reservation=__import__('knowledge.providers',fromlist=['reserve']).reserve('anthropic','propose-comment','1')
        self.assertTrue(reservation)
        ActionProposal.objects.filter(pk=human.pk).update(state='rejected')
        self.assertEqual(self.autopiloto.tick(self.bot)['propose'],0)  # daily LLM budget exhausted
        with patch.dict(os.environ,{'OPERATOR_PAUSED':'true'}):
            self.assertEqual(self.autopiloto.tick(self.bot).get('stopped'),'OPERATOR_PAUSED')

    def test_restriction_pauses_and_alerts(self):
        post=self.observed()[0]
        operador.create_proposal(self.gustavo,post,'INT-03',{'text':'A concrete, useful contribution to this conversation about evals.'})
        self.fake.state['fail_next']='rate_limit'
        with patch('team_backend.alerts.notify') as notify:
            self.autopiloto.tick(self.bot);self.drain()
        self.account.refresh_from_db();self.assertTrue(self.account.paused)
        notify.assert_called_once();self.assertIn('pausa',notify.call_args.args[0])
        report=self.autopiloto.tick(self.bot)
        self.assertEqual((report['observe'],report['execute']),(0,0))

    def test_command_respects_switch(self):
        from django.core.management import call_command
        with patch.dict(os.environ,{'OPERATOR_AUTOPILOT':'false'}):
            call_command('autopiloto','--once','--usuario','barrio-autopiloto')
        self.assertEqual(Job.objects.filter(kind='observe').count(),0)
        with patch.dict(os.environ,{'OPERATOR_AUTOPILOT':'true'}):
            call_command('autopiloto','--once','--usuario','barrio-autopiloto')
        self.assertEqual(Job.objects.filter(kind='observe').count(),1)
