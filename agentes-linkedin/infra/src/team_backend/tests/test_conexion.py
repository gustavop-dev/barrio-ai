"""Conectar LinkedIn desde la app (team_backend/conexion.py): starting a login only for a `directo` account and only
when it is on, the limit on starts, the single-use ticket (expiry, reuse, another user, an ended login), the cookie
Caddy's forward_auth checks and the view key it gets back, cancelling, and what a finished login does: the pause the
service caused cleared, any other pause kept, audit events. The navegador service is an httpx MockTransport."""
import hashlib
import hmac
import os
from datetime import timedelta
from unittest.mock import patch

import httpx
from django.contrib.auth.models import Permission, User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from linkedin_directo.servicio import TO_DO
from team_backend import conexion
from team_backend.models import ApiCredential, AuditEvent, BrowserLogin, ConnectorAccount

ENV = {'LINKEDIN_CONEXION_APP': 'true', 'NAVEGADOR_URL': 'http://navegador.interno:8790',
       'NAVEGADOR_TOKEN': 'token-ficticio-0123456789abcdef'}
SESSION = 'sesion-ficticia-0001'
LATER = (timezone.now() + timedelta(minutes=10)).isoformat()


def grant(user, *codes):
    user.user_permissions.add(*Permission.objects.filter(content_type__app_label='team_backend', codename__in=codes))
    for attr in ('_perm_cache', '_user_perm_cache', '_group_perm_cache'):
        if hasattr(user, attr):
            delattr(user, attr)


class FakeService:
    """The navegador service's login API: answers by method and path, and records what it was asked."""

    def __init__(self):
        self.state, self.calls, self.start = 'esperando', [], (201, None)
        self.stopped = False

    def body(self):
        return {'sesion': SESSION, 'cuenta': 'cuenta-prueba', 'estado': self.state, 'motivo': '', 'vence': LATER,
                'detenida': self.stopped}

    def __call__(self, request):
        self.calls.append((request.method, request.url.path, request.headers.get('authorization')))
        if request.method == 'POST':
            status, body = self.start
            return httpx.Response(status, json=body or self.body())
        if request.method == 'DELETE':
            self.state = 'cancelada'
        return httpx.Response(200, json=self.body())


class ConnectBase(TestCase):
    def setUp(self):
        env = patch.dict(os.environ, ENV)
        env.start()
        self.addCleanup(env.stop)
        self.service = FakeService()
        def request(method, url, **options):
            with httpx.Client(transport=httpx.MockTransport(self.service)) as client:
                return client.request(method, url, headers=options.get('headers'))
        mocked = patch.object(httpx, 'request', request)
        mocked.start()
        self.addCleanup(mocked.stop)
        self.gustavo = User.objects.create_user('gustavo', password='x')
        grant(self.gustavo, 'access_knowledge', 'operate_linkedin', 'approve_actions')
        self.other = User.objects.create_user('otra', password='x')
        grant(self.other, 'access_knowledge', 'operate_linkedin')
        self.human = APIClient()
        self.human.force_login(self.gustavo)
        self.account = ConnectorAccount.objects.create(provider='directo', external_account_id='cuenta-prueba',
                                                       label='Cuenta directa de prueba')

    def start(self, client=None, account=None):
        response = (client or self.human).post(f'/api/v1/operador/accounts/{(account or self.account).id}/conexion')
        return response.status_code, response.json()

    def ticket(self, url):
        return url.split('ticket=', 1)[1]

    def enter(self, raw):
        return self.client.get('/api/v1/linkedin/pantalla/entrar', {'ticket': raw})

    def allow(self, cookie):
        self.client.cookies.clear()
        if cookie:
            self.client.cookies[conexion.COOKIE] = cookie
        return self.client.get('/api/v1/linkedin/pantalla/permitir')


class StartTests(ConnectBase):
    def test_a_directo_account_gets_a_login_and_a_single_use_link(self):
        status, body = self.start()
        self.assertEqual((status, body['login']['state']), (201, 'esperando'))
        self.assertIn('/api/v1/linkedin/pantalla/entrar?ticket=', body['url'])
        login = BrowserLogin.objects.get()
        self.assertEqual((login.session, login.user, login.account), (SESSION, self.gustavo, self.account))
        self.assertNotIn(self.ticket(body['url']), login.ticket_hash)  # only its hash is kept
        self.assertEqual(self.service.calls[0][:2], ('POST', '/v1/cuentas/cuenta-prueba/conexion'))
        self.assertTrue(AuditEvent.objects.filter(action='linkedin.login_started', target=str(self.account.id)).exists())

    def test_other_providers_off_and_no_permission_are_refused(self):
        unipile = ConnectorAccount.objects.create(provider='unipile', external_account_id='acc_x', label='Unipile')
        self.assertEqual(self.start(account=unipile)[0], 400)
        with patch.dict(os.environ, {'LINKEDIN_CONEXION_APP': 'false'}):
            self.assertEqual(self.start()[0], 404)
        viewer = User.objects.create_user('lectora', password='x')
        grant(viewer, 'access_knowledge')
        client = APIClient()
        client.force_login(viewer)
        self.assertEqual(self.start(client)[0], 403)
        self.assertEqual(self.service.calls, [])

    def test_a_service_credential_cannot_start_it(self):
        robot = User.objects.create_user('servicio', password='x')
        grant(robot, 'access_knowledge', 'operate_linkedin')
        token = 'token-de-servicio-de-prueba'
        ApiCredential.objects.create(name='svc', user=robot, digest=hashlib.sha256(token.encode()).hexdigest())
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION='Bearer ' + token)
        self.assertEqual(self.start(client)[0], 403)

    def test_starts_are_limited_per_account_and_hour(self):
        for _ in range(conexion.STARTS_PER_HOUR):
            BrowserLogin.objects.create(account=self.account, user=self.gustavo, session='s', state='vencida',
                                        expires_at=timezone.now(), finished_at=timezone.now())
        self.assertEqual(self.start()[0], 429)
        self.assertEqual(self.service.calls, [])

    def test_a_service_that_cannot_says_why(self):
        self.service.start = (503, {'reason': 'la salida a internet cambió; no salió nada', 'code': 'egress'})
        status, body = self.start()
        self.assertEqual(status, 503)
        self.assertIn('otra conexión a internet', body['detail'])
        self.assertFalse(BrowserLogin.objects.exists())

    def test_pressing_again_reopens_the_same_login(self):
        _, first = self.start()
        _, again = self.start()
        self.assertEqual(first['login']['id'], again['login']['id'])
        self.assertNotEqual(first['url'], again['url'])
        self.assertEqual([c[0] for c in self.service.calls], ['POST', 'GET'])


class TicketTests(ConnectBase):
    def test_the_ticket_becomes_a_cookie_once_and_the_cookie_gets_the_view_key(self):
        _, body = self.start()
        raw = self.ticket(body['url'])
        response = self.enter(raw)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response['Location'].startswith('/conectar/vnc.html?'))
        cookie = response.cookies[conexion.COOKIE]
        self.assertEqual((cookie['path'], cookie['httponly'], cookie['samesite']), ('/conectar/', True, 'Strict'))
        self.assertEqual(response['Cache-Control'], 'no-store')
        allowed = self.allow(cookie.value)
        key = hmac.new(ENV['NAVEGADOR_TOKEN'].encode(), f'pantalla:{SESSION}'.encode(), hashlib.sha256).hexdigest()
        self.assertEqual((allowed.status_code, allowed['X-Pantalla-Clave']), (200, key))
        self.assertEqual(self.enter(raw).status_code, 410)  # single use
        self.assertEqual(self.allow('otra-cookie').status_code, 401)
        self.assertEqual(self.allow('').status_code, 401)

    def test_an_expired_ticket_opens_nothing(self):
        _, body = self.start()
        BrowserLogin.objects.update(ticket_expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.enter(self.ticket(body['url'])).status_code, 410)

    def test_a_ticket_of_an_ended_login_opens_nothing(self):
        _, body = self.start()
        BrowserLogin.objects.update(state='vencida')
        self.assertEqual(self.enter(self.ticket(body['url'])).status_code, 410)

    def test_a_cookie_stops_working_when_its_login_ends_or_its_user_loses_the_permission(self):
        _, body = self.start()
        cookie = self.enter(self.ticket(body['url'])).cookies[conexion.COOKIE].value
        self.gustavo.user_permissions.remove(Permission.objects.get(codename='operate_linkedin'))
        self.assertEqual(self.allow(cookie).status_code, 401)
        grant(self.gustavo, 'operate_linkedin')
        self.assertEqual(self.allow(cookie).status_code, 200)
        self.service.state = 'conectada'
        self.human.get(f'/api/v1/operador/conexiones/{body["login"]["id"]}')
        self.assertEqual(self.allow(cookie).status_code, 401)

    def test_a_new_link_replaces_the_old_cookie_and_only_its_user_gets_one(self):
        _, body = self.start()
        lid = body['login']['id']
        first = self.enter(self.ticket(body['url'])).cookies[conexion.COOKIE].value
        other = APIClient()
        other.force_login(self.other)
        self.assertEqual(other.post(f'/api/v1/operador/conexiones/{lid}/enlace').status_code, 403)
        again = self.human.post(f'/api/v1/operador/conexiones/{lid}/enlace').json()
        second = self.enter(self.ticket(again['url'])).cookies[conexion.COOKIE].value
        self.assertEqual((self.allow(first).status_code, self.allow(second).status_code), (401, 200))

    def test_off_means_no_door(self):
        _, body = self.start()
        with patch.dict(os.environ, {'LINKEDIN_CONEXION_APP': 'false'}):
            self.assertEqual(self.enter(self.ticket(body['url'])).status_code, 410)


class EndTests(ConnectBase):
    def poll(self, lid):
        return self.human.get(f'/api/v1/operador/conexiones/{lid}').json()['login']

    def test_connected_clears_the_pause_the_service_caused(self):
        for code in (409, 423):
            with self.subTest(code=code):
                self.account.paused, self.account.paused_reason = True, 'Servicio navegador: HTTP en x. ' + TO_DO[code].format(
                    'cuenta-prueba')
                self.account.save()
                BrowserLogin.objects.all().delete()
                self.service.state = 'esperando'
                _, body = self.start()
                self.service.state = 'conectada'
                self.assertEqual(self.poll(body['login']['id'])['state'], 'conectada')
                self.account.refresh_from_db()
                self.assertEqual((self.account.paused, self.account.paused_reason), (False, ''))
        self.assertEqual(AuditEvent.objects.filter(action='linkedin.login_finished').count(), 2)

    def test_a_pause_for_anything_else_or_a_stop_the_service_kept_stays(self):
        for reason, stopped in (('Pausa a mano: revisando', False), ('x ' + TO_DO[409].format('cuenta-prueba'), True)):
            with self.subTest(reason=reason):
                ConnectorAccount.objects.filter(pk=self.account.pk).update(paused=True, paused_reason=reason)
                BrowserLogin.objects.all().delete()
                self.service.state, self.service.stopped = 'esperando', False
                _, body = self.start()
                self.service.state, self.service.stopped = 'conectada', stopped
                login = self.poll(body['login']['id'])
                self.assertEqual((login['state'], login['still_stopped']), ('conectada', stopped))
                self.account.refresh_from_db()
                self.assertEqual((self.account.paused, self.account.paused_reason), (True, reason))

    def test_cancel_reaches_the_service_and_is_audited(self):
        _, body = self.start()
        response = self.human.post(f'/api/v1/operador/conexiones/{body["login"]["id"]}/cancelar')
        self.assertEqual(response.json()['login']['state'], 'cancelada')
        self.assertIn(('DELETE', f'/v1/conexiones/{SESSION}'), [c[:2] for c in self.service.calls])
        self.assertTrue(AuditEvent.objects.filter(action='linkedin.login_cancelled').exists())

    def test_a_service_that_forgot_the_login_ends_it(self):
        _, body = self.start()
        with patch.object(conexion, '_service', return_value=(404, {})):
            self.assertEqual(self.poll(body['login']['id'])['state'], 'fallida')

    def test_the_account_shows_whether_it_is_on_and_the_last_login(self):
        self.start()
        account = self.human.get('/api/v1/operador/accounts').json()
        rows = account['results'] if isinstance(account, dict) else account
        connect = rows[0]['connect']
        self.assertEqual((connect['enabled'], connect['last']['state']), (True, 'esperando'))
        ConnectorAccount.objects.create(provider='unipile', external_account_id='acc_y', label='Unipile')
        rows = self.human.get('/api/v1/operador/accounts').json()
        rows = rows['results'] if isinstance(rows, dict) else rows
        self.assertIsNone(next(r for r in rows if r['provider'] == 'unipile')['connect'])

    def test_the_token_goes_to_the_service_and_nowhere_else(self):
        _, body = self.start()
        self.assertEqual(self.service.calls[0][2], 'Bearer ' + ENV['NAVEGADOR_TOKEN'])
        self.assertNotIn(ENV['NAVEGADOR_TOKEN'], str(body))
        for event in AuditEvent.objects.all():
            self.assertNotIn(ENV['NAVEGADOR_TOKEN'], str(event.metadata))
