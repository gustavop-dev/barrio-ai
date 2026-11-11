"""Daily own publication: official LinkedIn OAuth and Posts API, editorial circuit, scheduling and API.
No network and no spend: the Posts API and OAuth run against httpx.MockTransport, Claude is patched."""
import json
import os
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse
import httpx
from cryptography.fernet import Fernet
from django.utils import timezone
from team_backend import autopiloto, connectors_linkedin as li, editorial
from team_backend.connectors import ConnectorError, ConnectorUncertain
from team_backend.models import ConnectorAccount, LinkedInCredential
from team_backend.tests.test_operador import OperatorBase

KEY=Fernet.generate_key().decode()
OAUTH_ENV={'LINKEDIN_CLIENT_ID':'client-test','LINKEDIN_CLIENT_SECRET':'secret-test','FIELD_ENCRYPTION_KEY':KEY,
           'LINKEDIN_REDIRECT_URI':'https://barrio.example.test/api/v1/linkedin/oauth/callback','LIVE_LINKEDIN_OFFICIAL':'false',
           'LINKEDIN_API_VERSION':'202610','EDITORIAL_POST_TIME':'08:30','EDITORIAL_LEAD_HOURS':'12','EDITORIAL_DAILY_LLM_USD':'1'}

def forbidden(request):
    raise AssertionError(f'Network forbidden: {request.method} {request.url}')

class PublicationBase(OperatorBase):
    def setUp(self):
        super().setUp()
        env=patch.dict(os.environ,OAUTH_ENV);env.start();self.addCleanup(env.stop)
        transport=patch.object(li,'TRANSPORT',httpx.MockTransport(forbidden));transport.start();self.addCleanup(transport.stop)
        li.FakeLinkedInOfficial.reset();self.addCleanup(li.FakeLinkedInOfficial.reset)

    def remember(self,key,value):
        import uuid
        from psycopg.types.json import Jsonb
        from knowledge import db
        with db.connect() as c:
            c.execute("INSERT INTO memory(id,namespace,key,version,value,status,author,evidence) VALUES(%s,'user',%s,1,%s,'confirmed','user','prueba')",
                      (str(uuid.uuid4()),key,Jsonb(value)))

    def gustavo_memory(self):
        self.remember('trayectoria.projectapp',{'texto':'Founder of ProjectApp, a custom software studio.','uso_publico':True})
        self.remember('objetivo.prioridad',{'texto':'Prioridad 60/40 entre oportunidades personales y ProjectApp.','uso_publico':False})
        self.remember('audiencia.segmento','Founders hispanohablantes de startups presemilla en EE. UU.')  # legacy value: private

    def bot(self):
        from django.contrib.auth.models import User
        bot,_=User.objects.get_or_create(username='barrio-autopiloto')
        self.grant(bot,'access_knowledge','run_agents','use_paid_providers','operate_linkedin','execute_actions')
        return bot

    def credential(self,expires_in=timedelta(days=60),token='AQ-live-token-never-logged'):
        account=ConnectorAccount.objects.create(provider='linkedin',external_account_id='urn:li:person:abc123',label='LinkedIn oficial')
        return LinkedInCredential.objects.create(account=account,member_urn='urn:li:person:abc123',member_name='Gustavo',
            scopes='openid profile w_member_social',token_encrypted=li.encrypt(token),expires_at=timezone.now()+expires_in)


class LinkedInOAuthTests(PublicationBase):
    def start(self):
        response=self.human.get('/api/v1/linkedin/oauth/start')
        self.assertEqual(response.status_code,302,response.content)
        query=parse_qs(urlparse(response['Location']).query)
        self.assertTrue(response['Location'].startswith(li.AUTH_URL))
        self.assertEqual(query['scope'],['openid profile w_member_social'])
        self.assertEqual(query['redirect_uri'],[OAUTH_ENV['LINKEDIN_REDIRECT_URI']])
        return query['state'][0]

    def test_state_is_validated_and_the_token_is_encrypted(self):
        self.assertEqual(self.api.get('/api/v1/linkedin/oauth/start').status_code,403)  # never with a Bearer token
        self.start()
        wrong=self.human.get('/api/v1/linkedin/oauth/callback',{'code':'c0de','state':'forged'})
        self.assertEqual(wrong['Location'],'/ajustes?linkedin=error&motivo=state')
        self.assertFalse(LinkedInCredential.objects.exists())
        # The state is single use: replaying the right one after a failure is rejected too.
        state=self.start();seen=[]
        def linkedin(request):
            seen.append(request.url.path)
            if request.url.path=='/oauth/v2/accessToken':
                form=parse_qs(request.content.decode())
                self.assertEqual((form['grant_type'],form['code'],form['client_secret']),(['authorization_code'],['c0de'],['secret-test']))
                return httpx.Response(200,json={'access_token':'AQ-secret-token','expires_in':5184000,'scope':'openid,profile,w_member_social'})
            self.assertEqual(request.headers['Authorization'],'Bearer AQ-secret-token')
            return httpx.Response(200,json={'sub':'782bbtaQ','name':'Gustavo P','email':'private@example.test'})
        with patch.object(li,'TRANSPORT',httpx.MockTransport(linkedin)):
            ok=self.human.get('/api/v1/linkedin/oauth/callback',{'code':'c0de','state':state})
            self.assertEqual(ok['Location'],'/ajustes?linkedin=ok')
            replay=self.human.get('/api/v1/linkedin/oauth/callback',{'code':'c0de','state':state,'rebote':'1'})
        self.assertEqual(replay['Location'],'/ajustes?linkedin=error&motivo=sesion')
        self.assertEqual(seen,['/oauth/v2/accessToken','/v2/userinfo'])
        credential=LinkedInCredential.objects.select_related('account').get()
        self.assertEqual((credential.member_urn,credential.account.provider),('urn:li:person:782bbtaQ','linkedin'))
        self.assertNotIn('AQ-secret-token',credential.token_encrypted)
        self.assertEqual(li.decrypt(credential.token_encrypted),'AQ-secret-token')
        self.assertAlmostEqual((credential.expires_at-timezone.now()).total_seconds(),5184000,delta=60)
        status=self.human.get('/api/v1/linkedin/status').json()
        self.assertEqual((status['connected'],status['member_urn'],status['days_left'],status['api_version']),(True,'urn:li:person:782bbtaQ',59,'202610'))
        self.assertNotIn('AQ-secret-token',json.dumps(status))

    def test_strict_session_cookie_gets_one_same_site_bounce(self):
        from django.test import Client
        anonymous=Client()
        bounce=anonymous.get('/api/v1/linkedin/oauth/callback',{'code':'c0de','state':'s'})
        self.assertEqual(bounce.status_code,200);self.assertIn(b'rebote=1',bounce.content)
        self.assertEqual(bounce['Referrer-Policy'],'no-referrer')
        self.assertEqual(anonymous.get('/api/v1/linkedin/oauth/callback',{'code':'c0de','state':'s','rebote':'1'})['Location'],
                         '/ajustes?linkedin=error&motivo=sesion')

    def test_missing_publish_scope_is_not_stored(self):
        state=self.start()
        def linkedin(request):
            if request.url.path=='/oauth/v2/accessToken':return httpx.Response(200,json={'access_token':'t','expires_in':60,'scope':'openid profile'})
            return httpx.Response(200,json={'sub':'x1'})
        with patch.object(li,'TRANSPORT',httpx.MockTransport(linkedin)):
            response=self.human.get('/api/v1/linkedin/oauth/callback',{'code':'c','state':state})
        self.assertEqual(response['Location'],'/ajustes?linkedin=error&motivo=scope')
        self.assertFalse(LinkedInCredential.objects.exists())


class PostsApiContractTests(PublicationBase):
    def connector(self,handler,**credential):
        self.cred=self.credential(**credential)
        with patch.dict(os.environ,{'LIVE_LINKEDIN_OFFICIAL':'true'}):connector=li.LinkedInOfficialConnector(self.cred.account)
        patcher=patch.object(li,'TRANSPORT',httpx.MockTransport(handler));patcher.start();self.addCleanup(patcher.stop)
        return connector

    def test_disabled_by_default(self):
        with self.assertRaises(ConnectorError) as ctx:li.LinkedInOfficialConnector(self.credential().account)
        self.assertEqual(ctx.exception.kind,'disabled')

    def test_text_post_body_headers_and_urn(self):
        def handler(request):
            self.assertEqual(str(request.url),li.POSTS_URL)
            self.assertEqual((request.headers['LinkedIn-Version'],request.headers['X-Restli-Protocol-Version']),('202610','2.0.0'))
            self.assertEqual(request.headers['Authorization'],'Bearer AQ-live-token-never-logged')
            body=json.loads(request.content)
            self.assertEqual(body,{'author':'urn:li:person:abc123','commentary':'Ship small \\(then measure\\) in C\\# #evals',
                'visibility':'PUBLIC','distribution':{'feedDistribution':'MAIN_FEED','targetEntities':[],'thirdPartyDistributionChannels':[]},
                'lifecycleState':'PUBLISHED','isReshareDisabledByAuthor':False})
            return httpx.Response(201,headers={'x-restli-id':'urn:li:share:6844785523593134080'})
        created=self.connector(handler).create_post('Ship small (then measure) in C# #evals')
        self.assertEqual(created,{'id':'urn:li:share:6844785523593134080','url':'https://www.linkedin.com/feed/update/urn:li:share:6844785523593134080/'})

    def test_outcomes_are_classified_and_never_retried(self):
        calls=[]
        def make(response):
            def handler(request):
                calls.append(1)
                if isinstance(response,Exception):raise type(response)('x',request=request)
                return response
            return handler
        cases=[(httpx.Response(429),ConnectorError,True),(httpx.Response(401),ConnectorError,True),(httpx.Response(422),ConnectorError,False),
               (httpx.Response(504),ConnectorUncertain,None),(httpx.Response(201),ConnectorUncertain,None),
               (httpx.ReadTimeout('x'),ConnectorUncertain,None),(httpx.ConnectError('x'),ConnectorError,False)]
        for response,error,pause in cases:
            LinkedInCredential.objects.all().delete();ConnectorAccount.objects.filter(provider='linkedin').delete()
            with self.assertRaises(error) as ctx:self.connector(make(response)).create_post('A text post.')
            if pause is not None:self.assertEqual(ctx.exception.pause,pause)
        self.assertEqual(len(calls),len(cases))  # one request per attempt, no automatic retry
        self.assertEqual(ctx.exception.kind,'not_sent')

    def test_expired_token_is_not_sent(self):
        connector=self.connector(forbidden,expires_in=timedelta(seconds=-1))
        self.assertEqual(connector.account_status()['status'],'token_expired')
        with self.assertRaises(ConnectorError) as ctx:connector.create_post('A text post.')
        self.assertTrue(ctx.exception.pause)

    def test_token_close_to_expiry_alerts_once_and_expiry_pauses(self):
        """Seven days before expiry Gustavo gets a push; once expired, publishing pauses."""
        credential=self.credential(expires_in=timedelta(days=5))
        bot=self.bot()
        with patch('team_backend.alerts.notify') as notify:
            autopiloto.tick(bot);autopiloto.tick(bot)
        notify.assert_called_once();self.assertIn('caduca',notify.call_args.args[0])
        status=self.human.get('/api/v1/linkedin/status').json()
        self.assertEqual((status['expiring_soon'],status['days_left']),(True,4))
        LinkedInCredential.objects.filter(pk=credential.pk).update(expires_at=timezone.now()-timedelta(minutes=1))
        with patch('team_backend.alerts.notify') as notify:autopiloto.tick(bot)
        credential.account.refresh_from_db()
        self.assertTrue(credential.account.paused);self.assertIn(li.TOKEN_PAUSE,credential.account.paused_reason)
        # «LinkedIn caducado» (urgent), not the generic «cuenta en pausa»: the body says publishing is paused.
        self.assertEqual(notify.call_args.args[0],'LinkedIn caducado');self.assertIn('pausa',notify.call_args.args[1])
        self.assertTrue(notify.call_args.kwargs['urgent'])


class MemoryGuardTests(PublicationBase):
    """uso_publico: only public facts are attributable; private guidance orients and never leaks."""
    def test_comment_receives_split_memory_and_the_gate_blocks_a_leak(self):
        from team_backend import jobs
        from team_backend.models import ActionProposal
        self.gustavo_memory();post=self.observed()[0];bot=self.bot()
        leak='Evals first, always. That is exactly what Spanish-speaking founders ask me about. Which failure mode do you test first?'
        answer={'decision':'comment','language':'en','comment':leak,'rationale':'r','citations':['LI-03-M006-K02'],
                'claims_needing_evidence':[],'risks':[]}
        with patch('knowledge.providers.claude',return_value={'text':json.dumps(answer),'model':'claude-opus-5-5'}) as claude:
            jobs.enqueue_operation(bot,'propose_comment',{'post':str(post.id)});jobs.process_one(self.worker)
        system,message=claude.call_args.args[0],json.loads(claude.call_args.args[1])
        self.assertNotIn('confirmed_user_memory',message);self.assertIn('private_guidance',system)
        self.assertEqual(message['public_facts'],[{'key':'trayectoria.projectapp','version':1,'fact':'Founder of ProjectApp, a custom software studio.'}])
        self.assertEqual({g['key'] for g in message['private_guidance']},{'objetivo.prioridad','audiencia.segmento'})
        self.assertNotIn('60/40',json.dumps(message['public_facts']))
        autopiloto.tick(bot)
        proposal=ActionProposal.objects.get(post=post)
        self.assertEqual(proposal.state,'discarded')
        self.assertTrue(any('orientación privada' in r for r in proposal.risks),proposal.risks)
        self.assertEqual(self.fake.state['writes'],0)


GOOD_POST='''Before writing a line of code for a new feature, ask one question: what decision will this help someone make?

Founders often arrive with a solution in mind: a dashboard, an AI assistant, a new integration. The useful work starts one step earlier, with the decision behind the request. Who makes it, how often, and what does a wrong call cost?

That question changes the scope. A weekly decision rarely needs real-time data. A decision with expensive mistakes needs an audit trail before it needs automation. And an AI feature earns its place only when someone can check its output against the outcome it was meant to improve.

Which decision is your product helping someone make this week?'''
INVENTED='''Last year I built an AI pipeline for a fintech client that cut their review costs by 40% in three months.

The lesson was simple: start from the decision the software supports, not from the feature list the founder brings. Who makes the call, how often, and what does a wrong call cost? Those answers decide the scope, the data you need and whether AI belongs in the product at all.

Which decision is your product helping someone make this week?'''
# Successful circuits need the complete curated lists; missing-unit cases remove
# an actual row explicitly instead of relying on a partial corpus in every test.
EDITORIAL_UNITS=list(dict.fromkeys(uid for stage in editorial.STAGES.values() for uid in stage[2]))

def answers(final=GOOD_POST,decision='write',verdict='ready_for_execution',findings=(),claims=None,signals_used=()):
    claims=claims if claims is not None else [{'text':'A weekly decision rarely needs real-time data.','kind':'general_knowledge','ref':''}]
    variant=lambda angle:{'angle':angle,'text':final,'claims':claims,'uncertainties':[]}
    assessment={'strengths':['Clear question'],'objections':[{'text':'Could use an example','severity':'preference'}]}
    return {
        'director':{'decision':decision,'skip_reason':'' if decision=='write' else 'No genuine material today.','primary_reader':'lector_comprador',
                    'modality':'personal_startups','pillar':'business_to_product','thesis':'Scope features from the decision they support.',
                    'approach':'LI-05-M001-K02','format':'infografia','image':{'kind':'infografia','reason':'Tarjeta disponible sin proveedor','photos':[]},'questions_for_gustavo':[],'ideas_used':[],'research_request':{'needed':False,'public_question':'','public_only':True},'reader_value':'A scoping question to reuse.',
                    'evidence':[{'kind':'general_knowledge','ref':'','note':'Product scoping practice'}],'success_criterion':'Founders reply with their decision.',
                    'avoid':['Inventing cases'],'signals_used':list(signals_used),'citations':['LI-04-M005-K01','LI-99-X'],'rationale':'Pillar fits; no repetition.'},
        'redactor':{'variant_a':variant('decision'),'variant_b':variant('objection'),'citations':['LI-06-M002-K09']},
        'lectores':{'readers':[{'reader':r,'variant_a':assessment,'variant_b':assessment} for r in
                    ['lector_comprador','lector_recomendador','lector_divulgador','lector_lider','lector_par']],'summary':'A slightly stronger.','citations':[]},
        'seleccion':{'decision':'A','final_text':final,'rationale':'Clearer hook.','claims':claims,'resolved_objections':[],
                     'kept_objections':['Could use an example'],'citations':['LI-06-M002-K09']},
        'verificador':{'verdict':verdict,'findings':list(findings),'checked_claims':[{'text':c['text'],'ref':c['ref'],'status':'general_knowledge'} for c in claims],
                       'summary':'Checked.','citations':['LI-06-M002-K09']},
        # R4: by default the repair round returns the same text, so a blocked piece stays blocked without re-verifying.
        'reparacion':{'decision':'repaired','final_text':final,'changes':[],'rationale':'Nothing safe to change.','claims':claims,
                      'citations':['LI-06-M002-K09']}}

class EditorialBase(PublicationBase):
    def setUp(self):
        super().setUp()
        import tempfile, shutil
        from django.test import override_settings
        root=tempfile.mkdtemp(prefix='editorial-images-');self.addCleanup(shutil.rmtree,root,ignore_errors=True)
        media=override_settings(MEDIA_ROOT=root);media.enable();self.addCleanup(media.disable)
        from knowledge import db
        from team_backend import operador
        with db.connect() as c:
            for uid in EDITORIAL_UNITS:
                c.execute('''INSERT INTO units(id,session,title,original,sha256,source_path,pointer,metadata)
                    VALUES(%s,5,%s,'{"title":"Unidad de prueba"}','abc','fixture','/units/0','{}') ON CONFLICT(id) DO NOTHING''',(uid,uid))
        self.official=operador.register_account(self.gustavo,'linkedin_fake','urn:li:person:fake','LinkedIn simulado')
        self.linkedin=li.FakeLinkedInOfficial(self.official)
        self.autobot=self.bot();self.calls=[]
        notify=patch('team_backend.alerts.notify');self.notify=notify.start();self.addCleanup(notify.stop)

    def claude(self,plan):
        def fake(system,message,max_tokens=None,output_schema=None,effort=None,purpose='agent-run'):
            self.assertIsNotNone(output_schema)
            data=json.loads(message);self.calls.append((purpose,data,system));answer=plan[purpose.split('-',1)[1]]
            if answer.get('signals_used')==['first']:answer=dict(answer,signals_used=[data['signals']['observed_posts'][0]['id']])
            return {'text':json.dumps(answer),'model':'claude-opus-5-5','estimated_usd':0.01,'request_id':'req_'+purpose}
        return patch('knowledge.providers.claude',side_effect=fake)

    def drain(self):
        from team_backend import jobs
        while jobs.process_one(self.worker):pass

    def plan(self,plan):
        with self.claude(plan):
            response=self.human.post('/api/v1/editorial/plan',{},format='json')
            self.assertEqual(response.status_code,202,response.content)
            self.drain()
        from team_backend.models import EditorialPiece
        return EditorialPiece.objects.get(slot_date=response.json()['slot_date'],origin_job=response.json()['job']['id'])

    def arrive(self,piece):
        """The scheduled hour arrives."""
        from team_backend.models import EditorialPiece
        EditorialPiece.objects.filter(pk=piece.pk).update(scheduled_for=timezone.now()-timedelta(minutes=1))

    def ready_piece(self,days_ago,text=GOOD_POST):
        import hashlib
        from team_backend import operador
        from team_backend.models import EditorialPiece
        now=timezone.now()
        piece=EditorialPiece.objects.create(account=self.official,slot_date=(now-timedelta(days=days_ago)).astimezone(operador.local_tz()).date(),
            scheduled_for=now-timedelta(hours=1+days_ago),state='ready',final_text=text,
            verification={'verdict':'ready_for_execution','text_sha256':hashlib.sha256(text.encode()).hexdigest()})
        from team_backend.imagenes import fallback
        fallback(piece,'Fixture sin proveedores')
        proposal=operador.create_proposal(self.gustavo,None,'CONT-09',{'text':text},citations=['LI-04-M005-K01'],source='agent',piece=piece)
        return autopiloto.policy_review(proposal)


class EditorialCircuitTests(EditorialBase):
    def test_a_missing_curated_unit_blocks_before_any_paid_stage(self):
        from knowledge import db
        with db.connect() as connection:
            connection.execute('UPDATE units SET active=false WHERE id=%s',(editorial.APPROACH_UNITS[-1],))
        piece=self.plan(answers())
        self.assertEqual(piece.state,'failed')
        self.assertIn('Biblioteca no disponible',piece.note)
        self.assertEqual(self.calls,[])

    def test_full_circuit_publishes_once_without_a_human(self):
        """Director → copywriters A/B → readers → selection → verifier → policy → Posts API → reconciliation."""
        from team_backend import operador
        from team_backend.models import ActionProposal
        self.observed()
        piece=self.plan(answers(signals_used=['first']))
        self.assertEqual((piece.state,piece.stage),('ready','visual'))
        self.assertEqual([c[0] for c in self.calls],['editorial-director','editorial-redactor','editorial-lectores','editorial-seleccion','editorial-verificador'])
        director=self.calls[0][1]
        self.assertEqual(director['public_facts'],[])  # empty memory: no experiences can be attributed
        self.assertIn('brief.prioridad',{g['key'] for g in director['private_guidance']})
        self.assertEqual(len(director['signals']['observed_posts']),2)
        self.assertEqual(len(piece.signals),1)  # the observed post the director used reaches writers and verifier as a source
        self.assertEqual(self.calls[1][1]['sources'],piece.signals);self.assertEqual(self.calls[4][1]['sources'],piece.signals)
        self.assertEqual(self.calls[1][1]['course_units'][0]['unit_id'],'LI-05-M001-K02')  # the chosen approach grounds the writers
        self.assertNotIn('LI-99-X',piece.citations)
        self.assertEqual(piece.verification['text_sha256'],__import__('hashlib').sha256(GOOD_POST.encode()).hexdigest())
        proposal=ActionProposal.objects.get(piece=piece)
        self.assertEqual((proposal.capability,proposal.post_id,proposal.state,proposal.source),('CONT-09',None,'proposed','agent'))
        report=autopiloto.tick(self.autobot)
        proposal.refresh_from_db()
        self.assertEqual((report['reviewed'],report['execute'],proposal.state),(1,0,'approved'))  # waits for its hour
        self.assertIn('está lista',self.notify.call_args.args[0])
        self.arrive(piece)
        self.assertEqual(autopiloto.tick(self.autobot)['execute'],1);self.drain()
        proposal.refresh_from_db();execution=proposal.execution
        self.assertEqual(self.linkedin.state['writes'],1)
        self.assertEqual(self.linkedin.state['posts'][0]['body']['commentary'],li.little_text(GOOD_POST))
        self.assertTrue(execution.external_id.startswith('urn:li:share:'));self.assertIn('/feed/update/urn:li:share:',execution.external_url)
        self.assertEqual(proposal.state,'sent')  # Unipile reads own posts but LinkedIn does not show it yet
        self.fake.seed_own_post(GOOD_POST,impressions=321)  # settled by text: Unipile ids are opaque, never URNs
        self.assertEqual(operador.reconcile(self.gustavo,proposal.id).state,'confirmed')
        piece.refresh_from_db();self.assertEqual((piece.metrics['impressions'],piece.metrics['source']),(321,'unipile'))
        # The API exposes the action with a null post and the piece behind it.
        listed=self.human.get('/api/v1/operador/actions',{'state':'confirmed'}).json()['results']
        self.assertEqual((listed[0]['post'],listed[0]['piece_id'],listed[0]['capability']),(None,str(piece.id),'CONT-09'))
        self.assertTrue(listed[0]['scheduled_for'])
        detail=self.human.get(f'/api/v1/editorial/pieces/{piece.id}').json()
        self.assertEqual((detail['status'],detail['final_text'],detail['verification']['verdict']),('published',GOOD_POST,'ready_for_execution'))
        self.assertEqual(detail['metrics']['impressions'],321)
        only_posts=self.human.get('/api/v1/operador/actions',{'capability':'CONT-09'}).json()['results']
        self.assertEqual({a['capability'] for a in only_posts},{'CONT-09'})
        self.assertEqual(self.human.get('/api/v1/operador/actions',{'capability':'INT-03'}).json()['count'],0)
        self.assertEqual(set(detail['variants']),{'variant_a','variant_b','citations'});self.assertEqual(len(detail['panel']['readers']),5)
        self.assertEqual(detail['action_detail']['post'],None)
        calendar=self.human.get('/api/v1/editorial/calendar').json()
        day=next(d for d in calendar['days'] if d['pieces'])
        self.assertEqual((day['pieces'][0]['status'],day['pieces'][0]['pillar']),('published','business_to_product'))
        self.assertEqual(calendar['post_time'],'08:30')
        # Ticking again never publishes twice.
        autopiloto.tick(self.autobot);self.drain()
        self.assertEqual(self.linkedin.state['writes'],1)

    def test_verifier_blocks_an_invented_experience(self):
        """R3/R4: the verifier catches what the rules cannot see; one repair round that changes nothing leaves it blocked."""
        from team_backend.models import ActionProposal
        anecdote=GOOD_POST.replace('Founders often arrive','I thought scoping was the easy part. Founders often arrive')
        finding={'issue':'invented_experience','severity':'material','quote':'I thought scoping was the easy part','detail':'Not in public_facts.'}
        piece=self.plan(answers(final=anecdote,verdict='blocked',findings=[finding]))
        self.assertEqual(piece.state,'blocked');self.assertIn('invented_experience',piece.note)
        self.assertEqual(piece.verification['repair']['outcome'],'sin_cambios')
        self.assertFalse(ActionProposal.objects.filter(piece=piece).exists())
        self.assertIn('bloqueó',self.notify.call_args.args[0])
        # Even if the model reviewer would miss it, the deterministic guard stops first-person experience without public
        # facts before the verifier is paid (R3).
        before=len(self.calls)
        again=self.plan(answers(final=INVENTED))
        self.assertEqual(again.state,'blocked');self.assertIn('sin hechos públicos confirmados',again.note)
        self.assertNotIn('editorial-verificador',[c[0] for c in self.calls[before:]])
        self.assertEqual(self.linkedin.state['writes'],0)

    def test_private_guidance_never_becomes_an_attributable_fact(self):
        from team_backend.models import ActionProposal
        self.gustavo_memory()
        leak=GOOD_POST.replace('Founders often arrive','Spanish-speaking founders in the US often arrive')
        piece=self.plan(answers(final=leak))
        for purpose,message,_ in self.calls:
            if 'public_facts' in message:
                self.assertEqual([f['key'] for f in message['public_facts']],['trayectoria.projectapp'],purpose)
                self.assertNotIn('60/40',json.dumps(message['public_facts']))
                self.assertTrue({'objetivo.prioridad','audiencia.segmento'}<={g['key'] for g in message['private_guidance']})
        self.assertNotIn('public_facts',self.calls[2][1])  # the readers panel gets no memory at all
        self.assertEqual(piece.state,'blocked');self.assertIn('orientación privada',piece.note)
        self.assertFalse(ActionProposal.objects.filter(piece=piece).exists())

    def test_director_may_skip_and_the_day_is_not_retried(self):
        with patch.dict(os.environ,{'EDITORIAL_LEAD_HOURS':'24'}),self.claude(answers(decision='skip')):
            self.assertEqual(autopiloto.tick(self.autobot)['plan'],1);self.drain()
            from team_backend.models import EditorialPiece
            piece=EditorialPiece.objects.get()
            self.assertEqual((piece.state,piece.note),('skipped','No genuine material today.'))
            self.assertEqual([c[0] for c in self.calls],['editorial-director'])
            self.assertEqual(autopiloto.tick(self.autobot)['plan'],0);self.drain()
        self.assertEqual(EditorialPiece.objects.count(),1)
        calendar=self.human.get('/api/v1/editorial/calendar').json()
        self.assertIn('skipped',[p['status'] for d in calendar['days'] for p in d['pieces']])

    def test_plan_retry_with_same_request_returns_the_same_job(self):
        import uuid
        rid=str(uuid.uuid4())
        with self.claude(answers()):
            first=self.human.post('/api/v1/editorial/plan',{'request_id':rid},format='json')
            again=self.human.post('/api/v1/editorial/plan',{'request_id':rid},format='json')
        self.assertEqual((first.status_code,again.status_code),(202,200))
        self.assertEqual((first.json()['job']['id'],first.json()['slot_date']),(again.json()['job']['id'],again.json()['slot_date']))

    def test_one_piece_per_day_at_most(self):
        from team_backend import operador
        late,today=self.ready_piece(1),self.ready_piece(0)
        self.assertEqual((late.state,today.state),('approved','approved'))
        self.assertEqual(autopiloto.tick(self.autobot)['execute'],1);self.drain()
        self.assertEqual(operador.capacity_left(self.official,'CONT-09'),0)
        self.assertEqual(autopiloto.tick(self.autobot)['execute'],0)
        with self.assertRaises(operador.OperatorBlocked):operador.execute(self.autobot,today.id)
        self.assertEqual(self.linkedin.state['writes'],1)
        # A planned slot cannot hold two open pieces either.
        from django.db import IntegrityError
        from team_backend.models import EditorialPiece
        with self.assertRaises(IntegrityError):
            EditorialPiece.objects.create(account=self.official,slot_date=today.piece.slot_date,scheduled_for=timezone.now())

    def test_uncertain_publication_is_never_repeated(self):
        from team_backend import operador
        proposal=self.ready_piece(0)
        self.linkedin.state['fail_next']='uncertain_applied'
        autopiloto.tick(self.autobot);self.drain()
        proposal.refresh_from_db();self.assertEqual(proposal.state,'uncertain')
        self.assertIn('¿Salió o no?',self.notify.call_args.args[0])
        with patch('team_backend.operador._own_posts_reader',return_value=None):
            execution=operador.reconcile(self.gustavo,proposal.id)
        self.assertEqual(execution.state,'uncertain');self.assertIn('w_member_social',execution.note)
        self.assertEqual(operador.execute(self.autobot,proposal.id).id,execution.id)
        autopiloto.tick(self.autobot);self.drain()
        self.assertEqual(self.linkedin.state['writes'],1)
        self.fake.seed_own_post(GOOD_POST)  # Unipile shows Gustavo's own post: settled by text, without writing
        self.assertEqual(operador.reconcile(self.gustavo,proposal.id).state,'confirmed')
        self.assertEqual(self.linkedin.state['writes'],1)

    def test_a_spent_ai_budget_stops_editorial_spending(self):
        from knowledge import providers as paid
        from team_backend.models import EditorialPiece, Job
        fuse=patch.dict(os.environ,{'AI_DAILY_FUSE_USD':'1'});fuse.start();self.addCleanup(fuse.stop)
        paid.reserve('anthropic','editorial-director','1')  # the team's daily safety fuse is spent
        with patch.dict(os.environ,{'EDITORIAL_LEAD_HOURS':'24'}),self.claude(answers()) as claude:
            self.assertEqual(autopiloto.tick(self.autobot)['plan'],0)
            self.assertEqual(self.human.post('/api/v1/editorial/plan',{},format='json').status_code,202);self.drain()
        claude.assert_not_called()
        job=Job.objects.get(kind='prepare_piece')
        self.assertEqual(job.state,'failed');self.assertIn('Presupuesto de IA',job.error)
        self.assertFalse(EditorialPiece.objects.exists())
        self.assertEqual(autopiloto.llm_spent_today(),0)  # the comments budget is untouched
        overview=self.human.get('/api/v1/operador/overview').json()['today']
        self.assertEqual(Decimal(overview['editorial_llm_spent_usd']),1)

    def test_vetoed_piece_is_not_published(self):
        proposal=self.ready_piece(0)
        response=self.human.post(f'/api/v1/operador/actions/{proposal.id}/reject',{'note':'No me representa'},format='json')
        self.assertEqual(response.json()['state'],'rejected')
        autopiloto.tick(self.autobot);self.drain()
        self.assertEqual(self.linkedin.state['writes'],0)
        detail=self.human.get(f'/api/v1/editorial/pieces/{proposal.piece_id}').json()
        self.assertEqual(detail['status'],'vetoed')

    def test_nothing_is_prepared_while_official_publishing_is_off(self):
        self.credential()  # real API account, LIVE_LINKEDIN_OFFICIAL=false
        with patch.dict(os.environ,{'EDITORIAL_LEAD_HOURS':'24'}),self.claude(answers()) as claude:
            self.assertEqual(autopiloto.tick(self.autobot)['plan'],0)
            self.assertEqual(self.human.post('/api/v1/editorial/plan',{},format='json').status_code,409)
        claude.assert_not_called()


class VoiceTests(EditorialBase):
    """Gustavo's own tone document reaches the agents that write public text, and only them."""
    def test_writers_and_selection_write_in_gustavos_voice(self):
        from team_backend import voz
        self.observed()
        self.plan(answers(signals_used=['first']))
        systems={purpose.split('-',1)[1]:system for purpose,_,system in self.calls}
        for stage in ('redactor','seleccion'):
            self.assertIn(voz.VOICE_GUIDE,systems[stage]);self.assertIn('# Tono de voz',systems[stage])
            self.assertIn('Una versión cuidada de esta voz',systems[stage])  # the whole document, not an excerpt
        for stage in ('director','lectores','verificador'):self.assertNotIn('<tono_de_voz',systems[stage])
        self.assertIn('voz informal de Gustavo',systems['verificador'])


class CommentVoiceTests(PublicationBase):
    def test_comment_writer_gets_the_voice_and_an_invented_spanish_anecdote_is_discarded(self):
        from team_backend import jobs, voz
        from team_backend.models import ActionProposal
        post=self.observed()[0];bot=self.bot()
        story='Uy qué pro. Yo pensé que eso salía en un rato, pero construí algo parecido y no jsjs. Cómo lo mantienen?'
        answer={'decision':'comment','language':'es','comment':story,'rationale':'r','citations':['LI-03-M006-K02'],
                'claims_needing_evidence':[],'risks':[]}
        with patch('knowledge.providers.claude',return_value={'text':json.dumps(answer),'model':'claude-opus-5-5'}) as claude:
            jobs.enqueue_operation(bot,'propose_comment',{'post':str(post.id)});jobs.process_one(self.worker)
        system=claude.call_args.args[0]
        self.assertTrue(system.startswith('Eres el agente de Relaciones'));self.assertTrue(system.endswith(voz.block()))
        autopiloto.tick(bot)
        proposal=ActionProposal.objects.get(post=post)
        self.assertEqual(proposal.state,'discarded')
        self.assertTrue(any('sin hechos públicos confirmados' in r for r in proposal.risks),proposal.risks)
        self.assertEqual(self.fake.state['writes'],0)


class CalendarAttemptsTests(EditorialBase):
    """10/11: days that already had their post ready also showed older blocked attempts («Bloqueada por el verificador»)."""

    def piece(self, day, state, note=''):
        from team_backend.models import EditorialPiece
        return EditorialPiece.objects.create(account=self.official, slot_date=day, scheduled_for=editorial.scheduled_for(day),
                                             state=state, note=note)

    def test_a_day_shows_its_post_not_its_older_attempts_and_a_budget_stop_is_left_to_the_autopilot(self):
        from team_backend import operador
        today = timezone.now().astimezone(operador.local_tz()).date()
        ready_day, blocked_day, budget_day, past = (today + timedelta(days=n) for n in (1, 2, 3, -2))
        self.piece(ready_day, 'blocked', 'El verificador emitió blocked; Hallazgo material')
        self.piece(ready_day, 'blocked', 'Ciclo detenido: cost_cap')
        ready = self.piece(ready_day, 'ready')
        self.piece(blocked_day, 'blocked', 'El verificador emitió blocked; primer intento')
        last = self.piece(blocked_day, 'failed', 'Error del proveedor')
        self.piece(budget_day, 'blocked', 'Ciclo detenido: cost_cap')
        stopped = self.piece(past, 'blocked', 'Ciclo detenido: cost_cap')
        calendar = self.human.get('/api/v1/editorial/calendar', {'desde': str(past), 'dias': 7}).json()
        shown = {d['date']: [p['id'] for p in d['pieces']] for d in calendar['days']}
        self.assertEqual((shown[str(ready_day)], shown[str(blocked_day)], shown[str(budget_day)], shown[str(past)]),
                         ([str(ready.id)], [str(last.id)], [], [str(stopped.id)]))
        body = self.human.get(f'/api/v1/calendario?desde={past}&hasta={budget_day}').json()
        events = {d['date']: [e['ref'] for e in d['events'] if e['layer'] == 'publicaciones'] for d in body['days']}
        self.assertEqual((events[str(ready_day)], events[str(blocked_day)], events[str(budget_day)], events[str(past)]),
                         ([str(ready.id)], [str(last.id)], [], [str(stopped.id)]))
        # The older attempts still open from their own link.
        self.assertEqual(self.human.get(f'/api/v1/editorial/pieces/{stopped.id}').status_code, 200)
