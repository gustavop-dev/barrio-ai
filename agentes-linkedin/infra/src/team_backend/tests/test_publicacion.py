"""Daily own publication: official LinkedIn OAuth and Posts API, editorial circuit, scheduling and API.
No network and no spend: the Posts API and OAuth run against httpx.MockTransport, Claude is patched."""
import json
import os
from datetime import timedelta
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse
import httpx
from cryptography.fernet import Fernet
from django.utils import timezone
from team_backend import autopiloto, connectors_linkedin as li
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
        self.assertIn('pausa',notify.call_args.args[0])

    def bot(self):
        from django.contrib.auth.models import User
        bot=User.objects.create_user('barrio-autopiloto')
        self.grant(bot,'access_knowledge','run_agents','use_paid_providers','operate_linkedin','execute_actions')
        return bot
