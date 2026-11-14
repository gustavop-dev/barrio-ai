"""The settings and the operator's commands: the pause floor and the budgets from the environment, importing a profile
without touching the original, reading whether a profile holds a session without opening a browser, the status line,
the log routes without ids, and the canary's own judgment. Nothing here opens a browser or reaches a network."""
import asyncio
import io
import json
import os
import socket
import sqlite3
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from linkedin_directo import LinkedInError, rutas
from linkedin_directo.canario import INVITATION, Recorder, verdict
from linkedin_directo.servicio import READ_TIMEOUT

from navegador import __main__ as cli
from navegador import ajustes, pagina
from navegador.almacen import IMPORTED, Store
from navegador import canario as canary
from navegador.cuenta import route
from navegador.pagina import stored_session
from tests.falsos import TOKEN, settings

DEAD_PID = 2 ** 22 + 7  # above Linux's pid_max: no process has it


def cookies(profile, expires):
    """A Chromium cookie store with only what stored_session reads; the value column stays empty."""
    (profile / 'Default').mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(profile / 'Default' / 'Cookies')
    try:
        db.execute('CREATE TABLE cookies (host_key TEXT, name TEXT, value TEXT, expires_utc INTEGER)')
        db.execute("INSERT INTO cookies VALUES ('.www.linkedin.com', 'li_at', '', ?)", (expires,))
        db.commit()
    finally:
        db.close()


def chromium_time(seconds):
    return int((seconds + 11644473600) * 1_000_000)


def snapshot(folder):
    out = {}
    for root, dirs, files in os.walk(folder):
        for name in dirs + files:
            path = os.path.join(root, name)
            info = os.lstat(path)
            out[os.path.relpath(path, folder)] = (info.st_size, info.st_mtime_ns)
    return out


class SettingsTests(unittest.TestCase):
    def test_the_pause_has_a_floor_and_a_ceiling(self):
        self.assertEqual(ajustes.pause(0, 0.5), (ajustes.PAUSE_FLOOR, ajustes.PAUSE_FLOOR))
        self.assertEqual(ajustes.pause(5, 2), (5.0, 5.0))
        self.assertEqual(ajustes.pause(4, 100), (4.0, ajustes.PAUSE_CEILING))
        self.assertEqual(ajustes.load({'NAVEGADOR_TOKEN': TOKEN}).pause, (3.0, 7.0))
        # A call that leaves by the deadline gets LinkedIn's answer back before the backend stops waiting.
        self.assertLess(ajustes.DEADLINE + ajustes.LINKEDIN_TIMEOUT_MS / 1000 + 5, READ_TIMEOUT)

    def test_budgets_come_from_the_environment(self):
        loaded = ajustes.load({'NAVEGADOR_TOKEN': TOKEN, 'NAVEGADOR_ESCRITURAS_DIA': '5', 'NAVEGADOR_INVITACIONES_DIA': '0'})
        self.assertEqual(loaded.budgets, {**ajustes.BUDGETS, ('write', 'day'): 5, ('invitation', 'day'): 0})
        self.assertEqual(set(ajustes.BUDGET_ENV), set(ajustes.BUDGETS))
        self.assertEqual({kind for kind, _ in ajustes.BUDGETS} - {'read', 'write'}, set(ajustes.WRITE_KINDS))
        for bad in ('muchas', '-1'):
            with self.subTest(bad=bad), self.assertRaises(ajustes.ConfigError):
                ajustes.load({'NAVEGADOR_TOKEN': TOKEN, 'NAVEGADOR_LECTURAS_HORA': bad})

    def test_the_proxy_comes_from_the_environment_and_is_never_repeated(self):
        loaded = ajustes.load({'NAVEGADOR_TOKEN': TOKEN, 'NAVEGADOR_PROXY': 'http://salida.interna:3128',
                               'NAVEGADOR_PROXY_CUENTAS': 'otra=https://otra.interna:8443, tercera=directo',
                               'NAVEGADOR_PROXY_USUARIO': 'usuario-ficticio', 'NAVEGADOR_PROXY_CLAVE': 'clave-ficticia'})
        self.assertEqual(loaded.egress('prueba').option(), {'server': 'http://salida.interna:3128',
                                                            'username': 'usuario-ficticio', 'password': 'clave-ficticia'})
        self.assertEqual(loaded.egress('otra').server, 'https://otra.interna:8443')
        self.assertEqual((loaded.egress('tercera').option(), loaded.egress('tercera').label), (None, 'directo'))
        self.assertEqual(ajustes.load({'NAVEGADOR_TOKEN': TOKEN}).egress('prueba').label, 'directo')
        label = loaded.egress('prueba').label
        self.assertRegex(label, r'^proxy-[0-9a-f]{12}$')
        self.assertEqual(label, ajustes.Egress('socks5://SALIDA.interna:3128').label)  # host and port, nothing else
        self.assertNotEqual(label, loaded.egress('otra').label)
        for secret in ('usuario-ficticio', 'clave-ficticia'):
            self.assertNotIn(secret, repr(loaded) + repr(loaded.egress('prueba')))
        bad = ({'NAVEGADOR_PROXY': 'http://usuario:clave-secreta@salida.interna:3128'},
               {'NAVEGADOR_PROXY': 'ftp://salida.interna:21'}, {'NAVEGADOR_PROXY': 'http://salida.interna:99999'},
               {'NAVEGADOR_PROXY': 'http://salida.interna'}, {'NAVEGADOR_PROXY_CUENTAS': 'Mayus=directo'},
               {'NAVEGADOR_PROXY_USUARIO': 'usuario-ficticio'},
               {'NAVEGADOR_PROXY': 'socks5://127.0.0.1:1080', 'NAVEGADOR_PROXY_USUARIO': 'u', 'NAVEGADOR_PROXY_CLAVE': 'c'})
        for env in bad:
            with self.subTest(env=sorted(env)), self.assertRaises(ajustes.ConfigError) as e:
                ajustes.load({'NAVEGADOR_TOKEN': TOKEN, **env})
            self.assertNotIn('clave-secreta', str(e.exception))

    def test_only_serving_and_the_canary_need_the_token(self):
        self.assertEqual(ajustes.load({}, need_token=False).token, '')

    def test_an_idle_browser_stays_open_unless_told_otherwise(self):
        self.assertEqual(ajustes.load({}, need_token=False).idle_minutes, 0)
        self.assertEqual(ajustes.load({'NAVEGADOR_CIERRE_INACTIVO_MIN': ''}, need_token=False).idle_minutes, 0)
        self.assertEqual(ajustes.load({'NAVEGADOR_CIERRE_INACTIVO_MIN': '45'}, need_token=False).idle_minutes, 45)


class ScreenTests(unittest.TestCase):
    def test_a_screen_is_ready_only_when_it_accepts_a_connection(self):
        with tempfile.TemporaryDirectory() as tmp, patch('navegador.pagina.X_SOCKETS', Path(tmp)):
            self.assertFalse(pagina.display_ready(':99'))
            live = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            live.bind(str(Path(tmp) / 'X99'))
            live.listen(1)
            try:
                self.assertTrue(pagina.display_ready(':99'))
                self.assertTrue(pagina.display_ready(':99.0'))
            finally:
                live.close()
            self.assertTrue((Path(tmp) / 'X99').exists())  # what a restarted container keeps in /tmp
            self.assertFalse(pagina.display_ready(':99'))
        self.assertIsNone(pagina.display_ready('otra-maquina:0'))
        with patch.dict(os.environ, {'DISPLAY': '', 'NAVEGADOR_PANTALLA': ':42'}):
            self.assertEqual(pagina.display(), ':42')  # what `docker exec` sees: the image's screen


class ProfileTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.settings = settings(self.tmp / 'datos')
        self.source = self.tmp / 'origen'
        cookies(self.source, chromium_time(time.time() + 86400))
        (self.source / 'Default' / 'Preferences').write_text('{}')
        (self.source / 'Default' / 'Cache').mkdir()
        (self.source / 'Default' / 'Cache' / 'data_0').write_bytes(b'cache')
        os.symlink(f'{socket.gethostname()}-{DEAD_PID}', self.source / 'SingletonLock')  # left by a dead browser

    def run_quietly(self, function, *args):
        with redirect_stdout(io.StringIO()) as out:
            function(*args)
        return out.getvalue()

    def test_a_profile_is_copied_without_locks_or_caches_and_the_original_is_untouched(self):
        before = snapshot(self.source)
        out = self.run_quietly(cli.import_profile, self.settings, str(self.source), 'prueba')
        self.assertIn('Sesión guardada: sí', out)
        target = self.settings.account_dir('prueba') / 'perfil'
        self.assertTrue((target / 'Default' / 'Preferences').is_file())
        self.assertFalse((target / 'Default' / 'Cache').exists())
        self.assertFalse(os.path.lexists(target / 'SingletonLock'))
        self.assertTrue(stored_session(target))
        self.assertEqual(snapshot(self.source), before)
        with self.assertRaises(SystemExit):  # an account's profile is never overwritten
            cli.import_profile(self.settings, str(self.source), 'prueba')
        self.assertEqual(Store(self.settings.account_dir('prueba')).egress(), IMPORTED)  # its session went out elsewhere
        self.assertIn('salida prueba --aceptar', out)

    def test_login_never_opens_a_session_by_another_exit(self):
        store = Store(self.settings.account_dir('prueba'))
        store.profile.mkdir(parents=True)
        store.set_egress('directo')
        moved = replace(self.settings, proxy='socks5://127.0.0.1:1080')
        with patch('navegador.pagina.launch') as launch, self.assertRaises(SystemExit) as stop:
            asyncio.run(cli.login(moved, 'prueba'))
        launch.assert_not_called()
        self.assertIn('salida prueba --aceptar', str(stop.exception.code))
        self.assertEqual(store.egress(), 'directo')

    def test_refused_while_a_browser_has_it_open_or_when_it_is_not_a_profile(self):
        (self.source / 'SingletonLock').unlink()
        os.symlink(f'{socket.gethostname()}-{os.getpid()}', self.source / 'SingletonLock')
        self.assertFalse(pagina.profile_busy(self.source))  # a live pid that is not a browser (a reused one) holds nothing
        with patch('navegador.pagina.is_browser', return_value=True), self.assertRaises(SystemExit):
            cli.import_profile(self.settings, str(self.source), 'prueba')
        (self.source / 'SingletonLock').unlink()
        os.symlink(f'otra-maquina-{os.getpid()}', self.source / 'SingletonLock')
        self.assertTrue(pagina.profile_busy(self.source))  # another machine's lock is never ours to take
        with self.assertRaises(SystemExit):
            cli.import_profile(self.settings, str(self.source), 'prueba')
        (self.tmp / 'vacia').mkdir()
        with self.assertRaises(SystemExit):
            cli.import_profile(self.settings, str(self.tmp / 'vacia'), 'prueba')
        self.assertFalse(self.settings.account_dir('prueba').exists())

    def test_whether_a_profile_holds_a_session_is_read_without_a_browser(self):
        self.assertTrue(stored_session(self.source))
        expired = self.tmp / 'caducado'
        cookies(expired, chromium_time(time.time() - 60))
        self.assertFalse(stored_session(expired))
        self.assertIsNone(stored_session(self.tmp / 'sin-perfil'))

    def test_status_says_stopped_and_what_was_spent(self):
        self.run_quietly(cli.import_profile, self.settings, str(self.source), 'prueba')
        store = Store(self.settings.account_dir('prueba'))
        store.count(('write', 'reaction'), time.time())
        store.stop('LinkedIn: HTTP 429 en add_reaction; la cuenta se detiene.')
        out = self.run_quietly(cli.status, self.settings)
        self.assertIn('prueba: sesión guardada sí', out)
        self.assertIn('DETENIDA', out)
        self.assertIn('escrituras 1/h 1/día (reacciones 1)', out)
        self.assertIn('Reanudada', self.run_quietly(cli.resume, self.settings, 'prueba'))
        self.assertIn('activa', self.run_quietly(cli.status, self.settings, 'prueba'))
        with patch('navegador.pagina.display_ready', return_value=False):
            self.assertIn(': NO RESPONDE', self.run_quietly(cli.status, self.settings))
        with patch('navegador.pagina.display_ready', return_value=True):
            self.assertIn(': lista', self.run_quietly(cli.status, self.settings))


class RouteTests(unittest.TestCase):
    def test_log_routes_keep_no_ids_and_no_query(self):
        cases = {
            '/voyager/api/identity/dash/profiles?q=memberIdentity&memberIdentity=persona-publica&decorationId=x':
                '/voyager/api/identity/dash/profiles memberIdentity',
            rutas.sdui(rutas.REACT): '/flagship-web/rsc-action/actions/server-request ' + rutas.REACT,
            '/voyager/api/relationships/invitations/7000001?action=accept': '/voyager/api/relationships/invitations/{id}',
            '/voyager/api/voyagerMessagingGraphQL/graphql?queryId=messengerMessages.abc&variables=(conversationUrn:x)':
                '/voyager/api/voyagerMessagingGraphQL/graphql messengerMessages',
            '/search/results/people/?keywords=una%20persona': '/search/results/people/',
            rutas.post_page('7123456789012345678'): '/feed/update/{id}/',
        }
        for path, expected in cases.items():
            with self.subTest(path=path[:50]):
                self.assertEqual(route(path), expected)


class CanaryTests(unittest.TestCase):
    def test_the_busiest_post_and_comment_come_from_linkedin_counters(self):
        def counts(urn, comments):
            return {'$type': 'com.linkedin.voyager.feed.shared.SocialActivityCounts', 'urn': urn,
                    'numComments': comments}
        recorder = Recorder(None)  # only the counters of an answer already in hand are read
        recorder.last = json.dumps({'included': [
            counts('urn:li:activity:1001', 3), counts('urn:li:activity:1002', 9), counts('urn:li:activity:1003', 0),
            counts('urn:li:comment:(activity:1002,2001)', 4), counts('urn:li:comment:(activity:1002,2002)', 0)]})
        self.assertEqual(recorder.busiest('activity'), '1002')
        self.assertEqual(recorder.busiest('activity', skip='1002'), '1001')
        self.assertEqual(recorder.busiest('comment'), '2001')
        recorder.last = 'no es json'
        self.assertEqual(recorder.busiest('activity'), '')

    def test_a_field_no_row_carries_is_a_break(self):
        when = datetime(2026, 11, 10, tzinfo=timezone.utc)
        self.assertEqual(verdict([{'id': '1', 'user': {'id': 'ACo1'}, 'created_at': when}], 1, INVITATION), ('ok', '', 1))
        self.assertEqual(verdict([], 0, INVITATION), ('ok', '', 0))
        self.assertEqual(verdict([], 1, INVITATION), ('roto', '0 filas (se esperaba al menos 1)', 0))
        self.assertEqual(verdict([{'id': '1', 'user': {'id': ''}, 'created_at': None}], 1, INVITATION),
                         ('roto', 'faltan campos: user.id, created_at', 1))

    def test_the_command_keeps_the_report_and_says_how_it_ended(self):
        class Refusing:
            def __init__(self, error):
                self.error = error

            def send(self, request):
                raise self.error

            def live_query(self, prefixes, variables):
                return None
        cases = ((LinkedInError('El servicio navegador no respondió; account_status no salió.', kind='not_sent'),
                  canary.NOT_RUN, 'no_corrio'),
                 (LinkedInError('Servicio navegador: HTTP 423 en account_status (sin sesión).', kind='login', status=423,
                                pause=True), canary.HALTED, 'alto'))
        for error, code, result in cases:
            with self.subTest(result=result), tempfile.TemporaryDirectory() as tmp:
                lines = []
                self.assertEqual(canary.run('', TOKEN, 'prueba', Path(tmp), out=lines.append, transport=Refusing(error)), code)
                [saved] = (Path(tmp) / 'canario').iterdir()
                report = json.loads(saved.read_text())
                self.assertEqual((report['resultado'], report['codigo'], report['llamadas'], len(report['operaciones'])),
                                 (result, code, 1, 1))
                self.assertEqual(report['error']['kind'], error.kind)
                self.assertEqual('DETENIDO' in lines[-1], code == canary.HALTED)


if __name__ == '__main__':
    unittest.main()
