"""Mobile app backend (docs/app-movil-backend.md): device-token login as a human session and native push through Expo.
No network: Expo runs on httpx.MockTransport, and every test that does not mock it fails if it tries to reach Expo."""
import hashlib
import json
import os
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch
import httpx
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIClient
from knowledge import providers
from team_backend import expo, notificaciones
from team_backend.authentication import DEVICE_PREFIX
from team_backend.models import ApiCredential, AuditEvent, Capture, DeviceToken, ExpoPushToken, GalleryPhoto
from team_backend.operador_views import human_session
from team_backend.tests.test_capturas import MediaMixin, photo
from team_backend.tests.test_operador import OperatorBase

PASSWORD='local-only-password'
PHONE='ExponentPushToken[movil-gustavo-1]'

def forbidden(request):
    raise AssertionError(f'Network forbidden: {request.method} {request.url}')

class ExpoFake:
    """Stands in for exp.host: one ticket per message (errors by token), receipts by ticket id."""
    def __init__(self,errors=None,receipts=None,status=200):
        self.errors=errors or {};self.receipts=receipts or {};self.status=status;self.sent=[];self.receipt_requests=[];self.headers=[]
    def __call__(self,request):
        body=json.loads(request.content);self.headers.append(request.headers)
        if self.status!=200:return httpx.Response(self.status,json={'errors':[{'code':'INTERNAL_SERVER_ERROR','message':'x'}]})
        if request.url.path=='/--/api/v2/push/getReceipts':
            self.receipt_requests.append(body['ids'])
            return httpx.Response(200,json={'data':{i:self.receipts[i] for i in body['ids'] if i in self.receipts}})
        self.assertion(request)
        self.sent.append(body)
        return httpx.Response(200,json={'data':[
            {'status':'error','message':'not registered','details':{'error':self.errors[m['to']]}} if m['to'] in self.errors
            else {'status':'ok','id':'ticket-'+m['to']} for m in body]})
    def assertion(self,request):
        assert str(request.url)==expo.SEND_URL,request.url
    @property
    def messages(self):return [m for batch in self.sent for m in batch]


class AppMovilBase(OperatorBase):
    def setUp(self):
        super().setUp();cache.clear()
        self.use_expo(forbidden)

    def use_expo(self,handler):
        transport=patch.object(expo,'TRANSPORT',httpx.MockTransport(handler));transport.start();self.addCleanup(transport.stop)
        return handler

    def issue(self,name='Pixel de Gustavo',username='gustavo-test',password=PASSWORD,client=None):
        return (client or Client()).post('/api/v1/auth/token',{'username':username,'password':password,'device_name':name},
                                         content_type='application/json')

    def token(self,name='Pixel de Gustavo',username='gustavo-test'):
        response=self.issue(name,username);self.assertEqual(response.status_code,201,response.content)
        return response.json()['token']

    def bearer(self,token):
        client=APIClient();client.credentials(HTTP_AUTHORIZATION='Bearer '+token)
        return client


class DeviceTokenTests(AppMovilBase):
    def test_issue_use_and_revoke(self):
        self.assertEqual(self.issue(password='wrong').status_code,400)
        self.assertEqual(Client().post('/api/v1/auth/token','[]',content_type='application/json').status_code,400)
        response=self.issue('  ');body=response.json()
        self.assertEqual(response.status_code,201);self.assertEqual(response['Cache-Control'],'no-store')
        token=body['token'];self.assertTrue(token.startswith(DEVICE_PREFIX))
        self.assertEqual(set(body),{'token','user','device'});self.assertEqual(set(body['device']),{'id','name','created_at'})
        self.assertEqual(body['device']['name'],'App móvil')  # a blank name gets a default
        device=DeviceToken.objects.get(id=body['device']['id'])
        self.assertEqual(device.digest,hashlib.sha256(token.encode()).hexdigest())  # only the digest is stored
        self.assertTrue(AuditEvent.objects.filter(action='auth.device_token',target=str(device.id)).exists())
        # The same user payload as the session, and GET /auth/session works with the bearer token alone (no cookie).
        session=Client().get('/api/v1/auth/session',HTTP_AUTHORIZATION='Bearer '+token).json()
        self.assertEqual(session,{'authenticated':True,'user':body['user']});self.assertIn('approve_actions',session['user']['permissions'])
        phone=self.bearer(token)
        self.assertEqual(phone.get('/api/v1/operador/overview').status_code,200)
        self.assertIsNotNone(DeviceToken.objects.get(pk=device.pk).last_used_at)
        devices=phone.get('/api/v1/auth/dispositivos').json()
        self.assertEqual([(d['id'],d['current'],d['push']) for d in devices],[(str(device.id),True,False)])
        # Revoking is for device tokens only; the PWA logs out with /auth/logout.
        refused=self.human.post('/api/v1/auth/token/revocar')
        self.assertEqual(refused.status_code,400);self.assertIn('detail',refused.json())
        self.assertEqual(self.api.post('/api/v1/auth/token/revocar').status_code,400)
        self.assertEqual(phone.post('/api/v1/auth/token/revocar').status_code,204)
        self.assertIsNotNone(DeviceToken.objects.get(pk=device.pk).revoked_at)
        self.assertEqual(phone.get('/api/v1/operador/overview').status_code,401)
        self.assertEqual(Client().get('/api/v1/auth/session',HTTP_AUTHORIZATION='Bearer '+token).json(),{'authenticated':False,'user':None})
        self.assertEqual(self.bearer(DEVICE_PREFIX+'unknown').get('/api/v1/operador/overview').status_code,401)

    def test_token_login_shares_the_session_login_lockout(self):
        browser=Client(enforce_csrf_checks=True);browser.get('/api/v1/auth/session');csrf=browser.cookies['csrftoken'].value
        def session_login(password):
            return browser.post('/api/v1/auth/login',{'username':'gustavo-test','password':password},
                                content_type='application/json',HTTP_X_CSRFTOKEN=csrf).status_code
        for _ in range(5):self.assertEqual(self.issue(password='wrong').status_code,400)
        for _ in range(5):self.assertEqual(session_login('wrong'),400)
        self.assertEqual(self.issue().status_code,429)  # ten failures in either door lock both
        self.assertEqual(session_login(PASSWORD),429)
        self.assertEqual(DeviceToken.objects.count(),0)
        cache.clear()
        self.assertEqual(self.issue().status_code,201)
        self.assertEqual(self.issue(password='wrong').status_code,400)
        self.assertEqual(self.issue().status_code,201)  # a success resets the counter, as in /auth/login

    def test_device_token_is_a_human_session_and_a_service_token_is_not(self):
        phone=self.bearer(self.token())
        self.assertEqual(self.api.post('/api/v1/operador/control',{'paused':True,'reason':'x'},format='json').status_code,403)
        stopped=phone.post('/api/v1/operador/control',{'paused':True,'reason':'Revisar desde el móvil'},format='json')
        self.assertEqual(stopped.status_code,200);self.assertTrue(stopped.json()['paused'])
        self.assertEqual(self.api.get('/api/v1/operador/accounts').status_code,200)  # the service token still authenticates
        self.assertEqual(self.api.post(f'/api/v1/operador/accounts/{self.account.id}/pause',{'paused':True,'reason':'x'},format='json').status_code,403)
        # human_session() itself: a session (auth None) and a device token pass; a service credential never does.
        human_session(SimpleNamespace(auth=None));human_session(SimpleNamespace(auth=DeviceToken.objects.get()))
        with self.assertRaises(PermissionDenied):human_session(SimpleNamespace(auth=ApiCredential.objects.get()))
        with self.assertRaises(PermissionDenied):human_session(SimpleNamespace(auth='other'))

    def test_the_prefix_never_shadows_a_service_credential(self):
        """A service token that happened to start with the device prefix still authenticates as the service, and is
        still refused for decisions."""
        odd=DEVICE_PREFIX+'service-token'
        ApiCredential.objects.create(name='odd',user=self.service,digest=hashlib.sha256(odd.encode()).hexdigest())
        service=self.bearer(odd)
        self.assertEqual(service.get('/api/v1/operador/accounts').status_code,200)
        self.assertEqual(service.post('/api/v1/operador/control',{'paused':True,'reason':'x'},format='json').status_code,403)

    def test_same_permission_model_as_the_session(self):
        guest=User.objects.create_user('invitado',password=PASSWORD);self.grant(guest,'access_knowledge')
        phone=self.bearer(self.token(username='invitado'))
        self.assertEqual(phone.get('/api/v1/operador/overview').status_code,403)  # require(user,'operate_linkedin')
        self.assertEqual(phone.post('/api/v1/capturas',{'nota':'Hola'},format='multipart').status_code,403)  # approve_actions
        guest.is_active=False;guest.save()
        self.assertEqual(phone.get('/api/v1/auth/dispositivos').status_code,401)

    def test_bearer_needs_no_csrf(self):
        browser=Client(enforce_csrf_checks=True)
        response=self.issue(client=browser);self.assertEqual(response.status_code,201)
        token=response.json()['token']
        self.assertEqual(browser.post('/api/v1/operador/control',{'paused':True,'reason':'x'},content_type='application/json').status_code,401)
        stopped=browser.post('/api/v1/operador/control',{'paused':True,'reason':'Sin CSRF'},content_type='application/json',
                             HTTP_AUTHORIZATION='Bearer '+token)
        self.assertEqual(stopped.status_code,200,stopped.content)
        # A session without the CSRF header is still refused: nothing loosened for cookies.
        session=Client(enforce_csrf_checks=True);session.force_login(self.gustavo)
        self.assertEqual(session.post('/api/v1/operador/control',{'paused':False,'reason':''},content_type='application/json').status_code,403)

    def test_devices_list_and_remote_revoke(self):
        phone=self.bearer(self.token('Pixel'));old=self.token('Teléfono viejo');old_phone=self.bearer(old)
        self.assertEqual(old_phone.post('/api/v1/push/expo',{'token':PHONE,'device_name':'Teléfono viejo'},format='json').status_code,201)
        devices=phone.get('/api/v1/auth/dispositivos').json()
        self.assertEqual([(d['name'],d['current'],d['push']) for d in devices],[('Teléfono viejo',False,True),('Pixel',True,False)])
        settings=phone.get('/api/v1/ajustes').json()
        self.assertEqual([d['name'] for d in settings['devices']],['Teléfono viejo','Pixel'])
        self.assertEqual(settings['expo_push'],{'active':1,'last_success_at':None,'last_error':''})
        self.assertIn('push_types',settings)  # additive: the rest of Ajustes is unchanged
        old_id=devices[0]['id']
        self.assertEqual(self.api.delete(f'/api/v1/auth/dispositivos/{old_id}').status_code,403)
        other=User.objects.create_user('otra',password=PASSWORD);self.grant(other,'access_knowledge')
        self.assertEqual(self.bearer(self.token(username='otra')).delete(f'/api/v1/auth/dispositivos/{old_id}').status_code,404)
        self.assertEqual(phone.delete(f'/api/v1/auth/dispositivos/{old_id}').status_code,204)
        self.assertEqual(phone.delete(f'/api/v1/auth/dispositivos/{old_id}').status_code,404)
        self.assertEqual(old_phone.get('/api/v1/auth/dispositivos').status_code,401)
        lost=ExpoPushToken.objects.get(token=PHONE)
        self.assertEqual((lost.active,lost.last_error),(False,'device_revoked'))  # a lost phone stops getting push
        self.assertEqual(expo.broadcast('t','b'),0)
        self.assertEqual([d['name'] for d in phone.get('/api/v1/auth/dispositivos').json()],['Pixel'])
        self.assertEqual(self.human.get('/api/v1/ajustes').json()['devices'][0]['current'],False)  # the PWA sees them too


class ExpoPushTests(AppMovilBase):
    def register(self,client,token=PHONE,name='Pixel'):
        response=client.post('/api/v1/push/expo',{'token':token,'device_name':name},format='json')
        self.assertEqual(response.status_code,201,response.content)
        return response.json()['id']

    def tokens(self,count):
        return [ExpoPushToken.objects.create(user=self.gustavo,token=f'ExponentPushToken[t{i:03d}]',device_name=f'T{i}') for i in range(count)]

    def test_registration_and_unregistration(self):
        phone=self.bearer(self.token('Pixel'))
        self.assertEqual(phone.post('/api/v1/push/expo',{'token':'not-a-token'},format='json').status_code,400)
        self.assertEqual(self.api.post('/api/v1/push/expo',{'token':PHONE},format='json').status_code,403)
        first=self.register(phone,name='')
        saved=ExpoPushToken.objects.get();self.assertEqual((saved.device_name,saved.device.name),('Pixel','Pixel'))
        ExpoPushToken.objects.update(active=False,last_error='DeviceNotRegistered')
        self.assertEqual(self.register(phone,name='Pixel 9'),first)  # registering again updates the same row
        saved.refresh_from_db();self.assertEqual((saved.device_name,saved.active,saved.last_error),('Pixel 9',True,''))
        self.assertEqual(self.register(phone,token='ExpoPushToken[legacy-format]'),str(ExpoPushToken.objects.get(token='ExpoPushToken[legacy-format]').id))
        self.assertEqual(phone.delete('/api/v1/push/expo',{'token':PHONE},format='json').status_code,204)
        self.assertEqual(list(ExpoPushToken.objects.values_list('token',flat=True)),['ExpoPushToken[legacy-format]'])

    def test_send_is_batched_with_the_web_push_content(self):
        fake=self.use_expo(ExpoFake());self.tokens(150)
        notificaciones.avisar('uncertain','Acción incierta en LinkedIn','Revisa si el comentario salió.')
        self.assertEqual([len(batch) for batch in fake.sent],[100,50])
        first=fake.messages[0]
        self.assertEqual(first,{'to':'ExponentPushToken[t000]','title':'Acción incierta en LinkedIn','body':'Revisa si el comentario salió.',
                                'data':{'url':'/tu-turno','tag':'0ff1ce-uncertain'},'channelId':'default','priority':'high','sound':'default',
                                'ttl':86400})
        self.assertNotIn('authorization',fake.headers[0])  # no account needed
        self.assertTrue(all(t.last_success_at and len(t.tickets)==1 for t in ExpoPushToken.objects.all()))
        fake.sent.clear()
        with patch.dict(os.environ,{'EXPO_ACCESS_TOKEN':'expo-test-token'}):
            notificaciones.avisar('piece_published','Publicaste «X»','Las impresiones llegan mañana.',link='/calendario/pieza/7',ref='piece_published:7')
        self.assertEqual(fake.headers[-1]['authorization'],'Bearer expo-test-token')
        self.assertEqual({(m['priority'],m['data']['url']) for m in fake.messages},{('default','/calendario/pieza/7')})

    def test_device_not_registered_deactivates_the_token(self):
        gone,kept=self.tokens(2)
        fake=self.use_expo(ExpoFake(errors={gone.token:'DeviceNotRegistered',kept.token:'MessageRateExceeded'}))
        self.assertEqual(expo.broadcast('Hola','Prueba'),0)
        gone.refresh_from_db();kept.refresh_from_db()
        self.assertEqual((gone.active,gone.last_error),(False,'DeviceNotRegistered'))
        self.assertEqual((kept.active,kept.last_error),(True,'MessageRateExceeded'))  # only DeviceNotRegistered deactivates
        expo.broadcast('Hola','Otra');self.assertEqual([m['to'] for m in fake.sent[-1]],[kept.token])

    def test_receipts_deactivate_devices_that_disappeared_later(self):
        now=timezone.now();iso=lambda delta:(now-delta).isoformat()
        uninstalled,fine=self.tokens(2)
        uninstalled.tickets=[['old',iso(timedelta(minutes=20))],['young',iso(timedelta(minutes=1))],['stale',iso(timedelta(hours=25))]]
        uninstalled.save();fine.tickets=[['ok-old',iso(timedelta(minutes=30))],['fine-young',iso(timedelta(minutes=2))]];fine.save()
        fake=self.use_expo(ExpoFake(receipts={'old':{'status':'error','message':'gone','details':{'error':'DeviceNotRegistered'}},
                                              'ok-old':{'status':'ok'}}))
        with expo._client() as http:self.assertEqual(expo.check_receipts(http,now),1)
        self.assertEqual(sorted(fake.receipt_requests[0]),['ok-old','old'])  # only tickets older than 15 minutes
        uninstalled.refresh_from_db();fine.refresh_from_db()
        self.assertEqual((uninstalled.active,uninstalled.last_error,uninstalled.tickets),(False,'DeviceNotRegistered',[]))
        self.assertTrue(fine.active);self.assertEqual([t[0] for t in fine.tickets],['fine-young'])  # young tickets wait

    def test_per_kind_switch_applies_before_expo(self):
        fake=self.use_expo(ExpoFake());self.tokens(1)
        self.human.patch('/api/v1/ajustes/preferencias',{'push_disabled':['question']},format='json')
        notificaciones.avisar('question','El director te pregunta: ¿qué stack usas?')
        notificaciones.avisar('connection_fit','Ana aceptó tu invitación',ref='connection:1')  # no push by default
        self.assertEqual(fake.sent,[])
        notificaciones.avisar('profile_task','Tarea de perfil nueva')
        self.assertEqual([m['title'] for m in fake.messages],['Tarea de perfil nueva'])

    def test_failures_never_break_the_work_that_pushes(self):
        self.tokens(1)
        def down(request):raise httpx.ConnectError('expo down')
        self.use_expo(down)
        created=notificaciones.avisar('piece_published','Publicaste «Y»',link='/calendario/pieza/8',ref='piece_published:8')
        self.assertIsNotNone(created)  # the Notification is still recorded
        self.use_expo(ExpoFake(status=503))
        self.assertEqual(expo.broadcast('a','b'),0)
        with patch.object(expo,'targets',side_effect=RuntimeError('db down')):self.assertEqual(expo.broadcast('a','b'),0)
        self.assertTrue(ExpoPushToken.objects.get().active)  # an outage is not the device's fault

    def test_push_test_reaches_expo_devices(self):
        phone=self.bearer(self.token())
        with patch.dict(os.environ,{'VAPID_PUBLIC_KEY':'','VAPID_PRIVATE_KEY':''}):
            self.assertEqual(phone.post('/api/v1/push/test').status_code,403)  # nothing configured, no device
            self.register(phone)
            fake=self.use_expo(ExpoFake())
            response=phone.post('/api/v1/push/test')
        self.assertEqual((response.status_code,response.json()),(202,{'sent':1}))
        self.assertEqual((fake.messages[0]['to'],fake.messages[0]['data']['url'],fake.messages[0]['priority']),(PHONE,'/ajustes','high'))
        status=phone.get('/api/v1/ajustes').json()['expo_push']
        self.assertEqual(status['active'],1);self.assertIsNotNone(status['last_success_at'])


class BearerUploadTests(MediaMixin,AppMovilBase):
    def setUp(self):
        super().setUp();self.use_media()
        transport=patch.object(providers,'ASSEMBLYAI_TRANSPORT',httpx.MockTransport(forbidden));transport.start();self.addCleanup(transport.stop)

    def test_multipart_capture_and_gallery_upload_with_bearer(self):
        token=self.token()
        browser=Client(enforce_csrf_checks=True)  # no cookie and no CSRF header: only the device token
        response=browser.post('/api/v1/capturas',{'nota':'Idea desde el móvil','fotos':[photo()]},HTTP_AUTHORIZATION='Bearer '+token)
        self.assertEqual(response.status_code,201,response.content)
        capture=Capture.objects.get(id=response.json()['id'])
        self.assertEqual((capture.note,capture.photos.count()),('Idea desde el móvil',1))
        uploaded=browser.post('/api/v1/galeria',{'fotos':[photo(name='otra.jpg')]},HTTP_AUTHORIZATION='Bearer '+token)
        self.assertEqual(uploaded.status_code,201,uploaded.content)
        self.assertEqual(GalleryPhoto.objects.count(),2)
        image=browser.get(f'/api/v1/galeria/{uploaded.json()[0]["id"]}/imagen',HTTP_AUTHORIZATION='Bearer '+token)
        self.assertEqual(image.status_code,200)
        self.assertEqual(self.api.post('/api/v1/capturas',{'nota':'Hola'},format='multipart').status_code,403)
