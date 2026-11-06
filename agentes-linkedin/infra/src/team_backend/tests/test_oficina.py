"""Office PWA backend: session login with CSRF, machine overview and stop, activity, Web Push."""
import os
from types import SimpleNamespace
from unittest.mock import patch
from django.core.cache import cache
from django.test import Client
from pywebpush import WebPushException
from team_backend import autopiloto, jobs, operador, push
from team_backend.models import Job, OperatorControl, PushSubscription
from team_backend.tests.test_operador import OperatorBase

SUBSCRIPTION={'endpoint':'https://push.example.test/sub/1','keys':{'p256dh':'BKey','auth':'secret'}}

class OfficeTests(OperatorBase):
    def setUp(self):
        super().setUp();cache.clear()
        public,private=push.generate_keys()
        env=patch.dict(os.environ,{'VAPID_PUBLIC_KEY':public,'VAPID_PRIVATE_KEY':private,'VAPID_SUBJECT':'mailto:test@example.test'})
        env.start();self.addCleanup(env.stop)
        self.browser=Client(enforce_csrf_checks=True)

    def csrf(self):
        self.browser.get('/api/v1/auth/session')
        return self.browser.cookies['csrftoken'].value

    def sign_in(self):
        token=self.csrf()
        response=self.browser.post('/api/v1/auth/login',{'username':'gustavo-test','password':'local-only-password'},
                                   content_type='application/json',HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code,200,response.content)
        return self.browser.cookies['csrftoken'].value

    def post(self,url,data=None):
        return self.browser.post(url,data or {},content_type='application/json',HTTP_X_CSRFTOKEN=self.browser.cookies['csrftoken'].value)

    def test_login_requires_csrf_and_limits_attempts(self):
        anonymous=self.browser.get('/api/v1/auth/session').json()
        self.assertEqual(anonymous,{'authenticated':False,'user':None})
        self.assertEqual(self.browser.post('/api/v1/auth/login',{'username':'gustavo-test','password':'local-only-password'},
                                           content_type='application/json').status_code,403)
        token=self.csrf()
        for _ in range(10):
            self.assertEqual(self.browser.post('/api/v1/auth/login',{'username':'gustavo-test','password':'wrong'},
                content_type='application/json',HTTP_X_CSRFTOKEN=token).status_code,400)
        self.assertEqual(self.browser.post('/api/v1/auth/login',{'username':'gustavo-test','password':'local-only-password'},
            content_type='application/json',HTTP_X_CSRFTOKEN=token).status_code,429)
        cache.clear();self.sign_in()
        session=self.browser.get('/api/v1/auth/session').json()
        self.assertTrue(session['authenticated']);self.assertIn('approve_actions',session['user']['permissions'])
        self.assertEqual(self.post('/api/v1/auth/logout').status_code,204)
        self.assertEqual(self.browser.get('/api/v1/operador/overview').status_code,401)

    def test_overview_reports_real_state(self):
        self.sign_in();post=self.observed()[0]
        self.approve(self.proposal(post))
        data=self.browser.get('/api/v1/operador/overview').json()
        self.assertEqual(data['control']['source'],'none')
        capacity=data['accounts'][0]['capacity']['INT-03']
        self.assertEqual((capacity['daily'],capacity['daily_used'],capacity['left']),(3,1,2))
        self.assertEqual(data['today']['proposals']['confirmed'],1)
        self.assertEqual(data['counts']['posts'],2)
        self.assertEqual(data['autopilot']['policy_version'],autopiloto.POLICY_VERSION)
        feed=self.browser.get('/api/v1/operador/feed?limit=100').json()
        self.assertIn('operator.execution_confirmed',[e['action'] for e in feed])

    def test_total_stop_from_the_office(self):
        self.assertEqual(self.api.post('/api/v1/operador/control',{'paused':True,'reason':'x'},format='json').status_code,403)
        self.sign_in()
        self.assertEqual(self.post('/api/v1/operador/control',{'paused':True}).status_code,400)
        stopped=self.post('/api/v1/operador/control',{'paused':True,'reason':'Revisar el tono'}).json()
        self.assertEqual((stopped['paused'],stopped['source']),(True,'db'))
        self.assertTrue(operador.globally_paused())
        self.assertEqual(autopiloto.tick(self.bot_user()).get('stopped'),'OPERATOR_PAUSED')
        with self.assertRaises(operador.OperatorBlocked):operador.execute(self.gustavo,'00000000-0000-0000-0000-000000000000')
        self.assertFalse(self.post('/api/v1/operador/control',{'paused':False}).json()['paused'])
        with patch.dict(os.environ,{'OPERATOR_PAUSED':'true'}):
            self.assertEqual(self.post('/api/v1/operador/control',{'paused':False}).status_code,409)
        self.assertFalse(OperatorControl.current().paused)

    def bot_user(self):
        from django.contrib.auth.models import User
        bot=User.objects.create_user('barrio-autopiloto')
        self.grant(bot,'access_knowledge','run_agents','use_paid_providers','operate_linkedin','execute_actions')
        return bot

    def test_activity_reflects_real_jobs_only(self):
        self.sign_in()
        roles=self.browser.get('/api/v1/oficina/actividad').json()['roles']
        self.assertEqual(len(roles),16)
        self.assertEqual(roles['lector_par']['status'],'diseno')
        self.assertEqual(roles['investigador_referentes']['status'],'en_espera')
        job,_=jobs.enqueue_operation(self.gustavo,'observe',{'account':str(self.account.id),'limit':5})
        Job.objects.filter(pk=job.pk).update(state=Job.State.RUNNING,worker=self.worker)
        roles=self.browser.get('/api/v1/oficina/actividad').json()['roles']
        self.assertEqual(roles['investigador_referentes']['status'],'trabajando')
        self.assertEqual(roles['relaciones_comunidad']['status'],'en_espera')

    def test_push_subscription_test_and_revocation(self):
        with patch.dict(os.environ,{'VAPID_PUBLIC_KEY':''}):
            self.assertEqual(self.api.get('/api/v1/push/key').status_code,503)
        self.assertTrue(self.api.get('/api/v1/push/key').json()['public_key'])
        self.assertEqual(self.api.post('/api/v1/push/subscriptions',SUBSCRIPTION,format='json').status_code,403)
        self.sign_in()
        self.assertEqual(self.post('/api/v1/push/subscriptions',SUBSCRIPTION).status_code,201)
        self.assertEqual(self.post('/api/v1/push/subscriptions',{'endpoint':'http://insecure.test','keys':{'p256dh':'a','auth':'b'}}).status_code,400)
        with patch('team_backend.push.webpush') as webpush:
            self.assertEqual(self.post('/api/v1/push/test').json(),{'sent':1})
        payload=webpush.call_args.args[1]
        self.assertIn('Notificación de prueba',payload)
        gone=WebPushException('gone',response=SimpleNamespace(status_code=410))
        with patch('team_backend.push.webpush',side_effect=gone):
            self.assertEqual(self.post('/api/v1/push/test').json(),{'sent':0})
        self.assertEqual(PushSubscription.objects.count(),0)

    def test_account_pause_alerts_every_subscribed_device(self):
        self.sign_in();self.post('/api/v1/push/subscriptions',SUBSCRIPTION)
        post=self.observed()[0]
        self.fake.state['fail_next']='rate_limit'
        with patch('team_backend.push.webpush') as webpush:
            self.approve(self.proposal(post))
        self.assertEqual(webpush.call_count,1)
        self.assertIn('cuenta en pausa',webpush.call_args.args[1])
