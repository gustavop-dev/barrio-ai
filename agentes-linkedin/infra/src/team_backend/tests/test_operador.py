"""Behaviour of the account operator: one approved version, one execution, no blind retries."""
import hashlib
import json
import os
from unittest.mock import patch
import httpx
from django.contrib.auth.models import Permission, User
from django.db import connection
from django.test import TransactionTestCase
from rest_framework.test import APIClient
from knowledge import db
from team_backend import jobs, operador
from team_backend.connectors import ConnectorError, ConnectorUncertain, FakeConnector, UnipileConnector, public_identifier
from team_backend.models import ActionExecution, ActionProposal, ApiCredential, AuditEvent, ConnectorAccount, Job, ObservedPost, Worker

ALL=['access_knowledge','run_agents','use_paid_providers','operate_linkedin','approve_actions','execute_actions','manage_jobs']

class OperatorTests(TransactionTestCase):
    def setUp(self):
        self.assertTrue(connection.settings_dict['NAME'].startswith('test_'))
        env=patch.dict(os.environ,{'LIVE_PROVIDERS':'false','LIVE_LINKEDIN':'false','OPERATOR_ALLOW_FAKE':'true',
                                   'OPERATOR_DAILY_LIMITS':'','OPERATOR_PAUSED':'false'})
        env.start();self.addCleanup(env.stop)
        network=patch('httpx.post',side_effect=AssertionError('Network forbidden in operator tests'))
        network.start();self.addCleanup(network.stop)
        FakeConnector.reset();self.addCleanup(FakeConnector.reset)
        with db.connect() as c:
            c.execute('TRUNCATE memory,runs,usage_ledger,embedding_cache,unit_evidence,edges,chunks,units,source_files,evidence,unit_revisions CASCADE')
            c.execute("INSERT INTO source_files(path,sha256) VALUES('fixture','abc')")
            c.execute('''INSERT INTO units(id,session,title,original,sha256,source_path,pointer,metadata)
                VALUES('LI-03-M006-K02',3,'Comentarios que aportan','{"title":"Opinión, fundamento y apertura"}','abc','fixture','/units/0','{}')''')
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
        self.assertEqual(self.fake.get_post(post.provider_post_id)['user_reacted'],'linkedin_insightful')
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

    def test_fake_connector_requires_explicit_flag(self):
        with patch.dict(os.environ,{'OPERATOR_ALLOW_FAKE':'false'}):
            with self.assertRaises(ConnectorError):FakeConnector('acc_fake1')


class UnipileContractTests(TransactionTestCase):
    """HTTP contract of Unipile v2 against a mock transport; no real network."""
    def connector(self,handler):
        with patch.dict(os.environ,{'LIVE_LINKEDIN':'true'}):
            return UnipileConnector('acc_TEST1',api_key='k-test',transport=httpx.MockTransport(handler))

    def test_disabled_without_explicit_switch(self):
        with patch.dict(os.environ,{'LIVE_LINKEDIN':'false'}):
            with self.assertRaises(ConnectorError) as ctx:UnipileConnector('acc_TEST1',api_key='k')
        self.assertEqual(ctx.exception.kind,'disabled')

    def test_paths_headers_and_parsing(self):
        seen=[]
        def handler(request):
            seen.append((request.method,request.url.raw_path.split(b'?')[0].decode(),request.headers.get('X-API-KEY')))
            if request.method=='POST':
                self.assertEqual(json.loads(request.content),{'text':'Hola'})
                return httpx.Response(201,json={'object':'Comment','id':'c1','text':'Hola','is_sender':True,'created_at':'2026-11-06T12:00:00Z'})
            if request.url.path.endswith('/posts'):
                return httpx.Response(200,json={'data':[{'id':'activity:1','text':'t','share_url':'u','created_at':'2026-11-06T10:00:00.000Z',
                    'author':{'id':'ACo1','display_name':'Ana','public_identifier':'ana'}}],'next_cursor':None})
            return httpx.Response(200,json={'id':'ACo1','display_name':'Ana','public_identifier':'ana','profile_url':'https://www.linkedin.com/in/ana'})
        c=self.connector(handler)
        self.assertEqual(c.get_user(public_identifier('https://www.linkedin.com/in/ana/'))['id'],'ACo1')
        self.assertEqual(c.list_user_posts('ACo1')[0]['id'],'activity:1')
        self.assertEqual(c.create_comment('activity:1','Hola')['id'],'c1')
        self.assertEqual(seen[0],('GET','/v2/acc_TEST1/users/ana','k-test'))
        self.assertEqual(seen[1][1],'/v2/acc_TEST1/users/ACo1/posts')
        self.assertEqual(seen[2][:2],('POST','/v2/acc_TEST1/posts/activity%3A1/comments'))

    def test_write_outcomes_are_classified(self):
        def rate_limited(request):return httpx.Response(429,json={'type':'provider/too_many_requests','status':429})
        with self.assertRaises(ConnectorError) as ctx:self.connector(rate_limited).create_comment('p','x')
        self.assertTrue(ctx.exception.pause)
        def gateway_timeout(request):return httpx.Response(504,json={'type':'provider/timeout'})
        with self.assertRaises(ConnectorUncertain):self.connector(gateway_timeout).create_comment('p','x')
        def read_timeout(request):raise httpx.ReadTimeout('slow',request=request)
        with self.assertRaises(ConnectorUncertain):self.connector(read_timeout).create_comment('p','x')
        def refused(request):raise httpx.ConnectError('down',request=request)
        with self.assertRaises(ConnectorError) as ctx:self.connector(refused).create_comment('p','x')
        self.assertEqual(ctx.exception.kind,'not_sent')
        def rejected(request):return httpx.Response(422,json={'type':'provider/unprocessable_entity'})
        with self.assertRaises(ConnectorError) as ctx:self.connector(rejected).create_comment('p','x')
        self.assertFalse(ctx.exception.pause)

    def test_identifier_rejects_names(self):
        with self.assertRaises(ValueError):public_identifier('Ana María López')
