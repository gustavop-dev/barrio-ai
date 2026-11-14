"""The login from the app (navegador/conexion.py) on the fake browser and fake processes: one at a time, the account
refusing calls meanwhile, the remote view only with its key and only while the login lasts, the four endings with
their teardown, the stop it clears and the one it keeps, and logs without the view's key."""
import asyncio
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from aiohttp import ClientSession, WSMsgType
from aiohttp.test_utils import TestClient, TestServer, unused_port

from navegador import pagina
from navegador.almacen import Store
from navegador.conexion import HEADER, view_key
from navegador.servidor import build
from tests.falsos import TOKEN, Browser, World, call

AUTH = {'Authorization': f'Bearer {TOKEN}'}
LOGIN = 'https://www.linkedin.com/login'


class Process:
    def __init__(self, argv):
        self.argv, self.returncode = argv, None

    def terminate(self):
        self.returncode = -15

    def kill(self):
        self.returncode = -9

    async def wait(self):
        return self.returncode


class LoginCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.vnc_port, self.view_port = unused_port(), unused_port()
        self.novnc = Path(tempfile.mkdtemp())
        (self.novnc / 'vnc.html').write_text('<html>novnc</html>')
        self.world = World(Browser(landing=LOGIN), connect=True, view_port=self.view_port, novnc=self.novnc)
        self.addCleanup(self.world.tmp.cleanup)
        self.world.advance = False  # the login's clock moves only when a test moves it
        self.procs, self.stored = [], None

        async def vnc(reader, writer):  # stands in for x11vnc: greets, then echoes
            writer.write(b'RFB 003.008\n')
            await writer.drain()
            while data := await reader.read(100):
                writer.write(b'eco:' + data)
                await writer.drain()
        self.vnc = await asyncio.start_server(vnc, '127.0.0.1', self.vnc_port)
        self.addAsyncCleanup(self.close_vnc)
        deps = self.world.deps()
        deps['connect'] = {'spawn': self.spawn, 'launcher': self.browser.launch, 'stored': lambda profile: self.stored,
                           'screen_ready': self.screen_ready, 'port_open': self.port_open, 'vnc_port': self.vnc_port}
        self.client = TestClient(TestServer(build(self.world.settings, **deps)))
        await self.client.start_server()
        self.addAsyncCleanup(self.client.close)

    async def close_vnc(self):
        self.vnc.close()
        await self.vnc.wait_closed()

    async def spawn(self, *argv):
        self.procs.append(Process(argv))
        return self.procs[-1]

    def screen_ready(self, name):
        return any(p.argv[0] == 'Xvfb' and p.returncode is None for p in self.procs)

    async def port_open(self, port):
        return port == self.vnc_port and any(p.argv[0] == 'x11vnc' and p.returncode is None for p in self.procs)

    @property
    def browser(self):
        return self.world.browser

    def store(self):
        return Store(self.world.settings.account_dir('prueba'))

    async def start(self, account='prueba'):
        response = await self.client.post(f'/v1/cuentas/{account}/conexion', headers=AUTH)
        return response.status, await response.json()

    async def state(self, session):
        response = await self.client.get(f'/v1/conexiones/{session}', headers=AUTH)
        return await response.json()

    async def ended(self, session):
        for _ in range(300):
            body = await self.state(session)
            if body['estado'] not in ('abriendo', 'esperando'):
                return body
            await asyncio.sleep(0.01)
        raise AssertionError('la conexión no terminó')

    def log_in(self):
        """The person types the password: the tab reaches the feed with the session cookie."""
        self.browser.contexts[-1].pages[0].url = pagina.FEED

    def assert_torn_down(self):
        self.assertTrue(self.procs and all(p.returncode is not None for p in self.procs))
        self.assertTrue(self.browser.contexts[-1].closed)
        self.assertFalse(pagina.held(self.store().profile))


class StartTests(LoginCase):
    async def test_it_opens_its_own_screen_the_view_and_the_login_page(self):
        status, body = await self.start()
        self.assertEqual((status, body['estado'], body['cuenta']), (201, 'esperando', 'prueba'))
        self.assertEqual([p.argv[0] for p in self.procs], ['Xvfb', 'x11vnc'])
        self.assertEqual(self.procs[0].argv[1], ':98')  # never the service's screen, where other accounts are
        x11vnc = self.procs[1].argv
        self.assertIn('-localhost', x11vnc)
        self.assertIn('-nevershared', x11vnc)
        self.assertEqual(self.browser.screens, [':98'])
        self.assertEqual(self.browser.contexts[-1].pages[0].url, LOGIN)
        self.assertTrue(pagina.held(self.store().profile))

    async def test_one_login_at_a_time_per_service(self):
        await self.start()
        Store(self.world.settings.account_dir('otra')).profile.mkdir(parents=True)
        for account in ('prueba', 'otra'):
            status, body = await self.start(account)
            self.assertEqual((status, body['code']), (409, 'conexion'))
        self.assertEqual(self.browser.launches, 1)

    async def test_the_account_refuses_calls_meanwhile_without_a_stop(self):
        await self.start()
        response = await self.client.post('/v1/cuentas/prueba/llamadas', json=call(), headers=AUTH)
        body = await response.json()
        self.assertEqual((response.status, body['code']), (503, 'conexion'))
        self.assertGreater(body['retry_after'], 0)
        self.assertEqual(self.browser.fetches, [])
        self.assertIsNone(self.store().stopped())

    async def test_off_unless_enabled_and_never_for_an_unknown_name(self):
        status, _ = await self.start('Mal Nombre')
        self.assertEqual(status, 404)
        self.world.settings = replace(self.world.settings, connect=False)
        client = TestClient(TestServer(build(self.world.settings, **self.world.deps())))
        await client.start_server()
        self.addAsyncCleanup(client.close)
        response = await client.post('/v1/cuentas/prueba/conexion', headers=AUTH)
        self.assertEqual(response.status, 404)
        self.assertEqual(self.procs, [])

    async def test_another_internet_exit_does_not_open(self):
        self.store().set_egress('proxy-000000000000')
        status, body = await self.start()
        self.assertEqual((status, body['code']), (503, 'egress'))
        self.assertEqual(self.procs, [])

    async def test_a_first_login_records_the_exit_and_a_new_account_gets_its_profile(self):
        status, _ = await self.start('nueva')
        self.assertEqual(status, 201)
        store = Store(self.world.settings.account_dir('nueva'))
        self.assertTrue(store.profile.is_dir())
        self.assertEqual(store.egress(), 'directo')

    async def test_the_token_is_required(self):
        response = await self.client.post('/v1/cuentas/prueba/conexion')
        self.assertEqual(response.status, 401)


class ViewTests(LoginCase):
    async def test_the_view_needs_the_session_key_and_bridges_to_vnc(self):
        _, body = await self.start()
        key = view_key(TOKEN, body['sesion'])
        url = f'http://127.0.0.1:{self.view_port}'
        async with ClientSession() as http:
            for headers in ({}, {HEADER: 'x' * 64}, {HEADER: view_key('otro-token-0123456789abcdef', body['sesion'])}):
                async with http.get(f'{url}/vnc.html', headers=headers) as answer:
                    self.assertEqual(answer.status, 403)
            async with http.get(f'{url}/vnc.html', headers={HEADER: key}) as answer:
                self.assertEqual((answer.status, await answer.text()), (200, '<html>novnc</html>'))
            ws = await http.ws_connect(f'{url}/websockify', headers={HEADER: key}, protocols=('binary',))
            self.assertEqual((await ws.receive()).data, b'RFB 003.008\n')
            await ws.send_bytes(b'tecla')
            self.assertEqual((await ws.receive()).data, b'eco:tecla')
            self.log_in()
            await self.ended(body['sesion'])
            self.assertIn((await ws.receive()).type, (WSMsgType.CLOSE, WSMsgType.CLOSING, WSMsgType.CLOSED))
            with self.assertRaises(OSError):  # the view is gone with the login
                await http.get(f'{url}/vnc.html', headers={HEADER: key})


class EndTests(LoginCase):
    async def test_logged_in_closes_everything_and_the_account_works_again(self):
        _, body = await self.start()
        self.log_in()
        end = await self.ended(body['sesion'])
        self.assertEqual((end['estado'], end['detenida']), ('conectada', False))
        self.assert_torn_down()
        self.browser.landing = pagina.FEED
        response = await self.client.post('/v1/cuentas/prueba/llamadas', json=call(), headers=AUTH)
        self.assertEqual(response.status, 200)
        self.assertEqual(self.browser.screens[-1], None)  # the service's own screen again

    async def test_a_session_that_did_not_reach_the_disk_is_a_failure(self):
        self.stored = False
        _, body = await self.start()
        self.log_in()
        end = await self.ended(body['sesion'])
        self.assertEqual(end['estado'], 'fallida')
        self.assertIn('sesión', end['motivo'])

    async def test_the_deadline_tears_it_down(self):
        _, body = await self.start()
        self.world.clock.now += self.world.settings.connect_minutes * 60
        end = await self.ended(body['sesion'])
        self.assertEqual(end['estado'], 'vencida')
        self.assert_torn_down()
        self.assertEqual(self.browser.fetches, [])

    async def test_cancel_and_a_closed_window(self):
        _, body = await self.start()
        response = await self.client.delete(f'/v1/conexiones/{body["sesion"]}', headers=AUTH)
        self.assertEqual((response.status, (await response.json())['estado']), (200, 'cancelada'))
        self.assert_torn_down()
        _, body = await self.start()
        self.browser.contexts[-1].pages = []
        self.assertEqual((await self.ended(body['sesion']))['estado'], 'cancelada')
        self.assertEqual((await self.client.get('/v1/conexiones/otra-cosa', headers=AUTH)).status, 404)

    async def test_a_browser_that_does_not_open_fails_and_cleans_up(self):
        self.browser.fail_launch = RuntimeError('sin navegador')
        status, body = await self.start()
        self.assertEqual((status, body['estado']), (201, 'fallida'))
        self.assertIn('RuntimeError', body['motivo'])
        self.assertTrue(all(p.returncode is not None for p in self.procs))
        self.assertFalse(pagina.held(self.store().profile))

    async def test_a_session_stop_is_cleared_and_any_other_kept(self):
        for reason, session, kept in (('la página está en /login', True, False), ('LinkedIn: HTTP 429 en x', False, True)):
            with self.subTest(reason=reason):
                self.store().stop(reason, session=session)
                _, body = await self.start()
                self.log_in()
                end = await self.ended(body['sesion'])
                self.assertEqual((end['estado'], end['detenida']), ('conectada', kept))
                self.store().resume()


class LogTests(LoginCase):
    async def test_the_view_key_is_never_logged(self):
        with self.assertLogs('navegador', 'INFO') as logs:
            _, body = await self.start()
            self.log_in()
            await self.ended(body['sesion'])
        text = '\n'.join(logs.output)
        self.assertNotIn(view_key(TOKEN, body['sesion']), text)
        self.assertNotIn(body['sesion'], text)
        self.assertIn('conectada', text)


class SessionStopTests(unittest.TestCase):
    def test_which_reasons_are_the_session(self):
        self.assertTrue(pagina.lost_session('la página está en /checkpoint'))
        self.assertTrue(pagina.lost_session('se fue la cookie de sesión (li_at)'))
        self.assertFalse(pagina.lost_session('HTTP 429 en una llamada de la propia página'))
