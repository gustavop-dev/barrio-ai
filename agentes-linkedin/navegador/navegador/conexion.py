"""Entrar a mano en LinkedIn desde la app (Ajustes › Máquina, «Conectar LinkedIn»), inside the running service: the app
cannot stop or start containers. One login at a time per service, and only with NAVEGADOR_CONEXION=true. The HTTP side
is in docs/navegador-contrato.md; the whole path (backend ticket, Caddy, app) in README «Conectar desde la app».

- Start: the account's open page closes (behind any call in flight) and the account refuses calls with 503 `conexion`
  until the login ends: nothing leaves, the backend retries later and pauses nothing. The login browser opens the
  account's profile, by the internet exit of its session (another one is refused as for a call; the first login records
  it), on a virtual screen of its own (NAVEGADOR_PANTALLA_CONEXION, the service's size): never the service's screen,
  where other accounts' logged-in windows are. It shows LinkedIn's login page; the person types the password there.
- The remote view, only while the login lasts: x11vnc on that screen, on the container's loopback and without a VNC
  password, and a small web server on settings.view_port (internal network, never published) serving noVNC and
  bridging its WebSocket to x11vnc. Every request to it must carry X-Pantalla-Clave = HMAC-SHA256(NAVEGADOR_TOKEN,
  'pantalla:' + session id): the backend hands it to Caddy (forward_auth) for a browser that redeemed a single-use
  ticket, so the person's browser never holds it. Neither that key nor the session id is ever logged.
- Ends: conectada (the tab reached the feed with the session cookie; the browser then closes so Chromium writes its
  cookies, and the profile on disk must hold the session), vencida (settings.connect_minutes without that), cancelada
  (the backend, or the window closed without a session), fallida (the screen, the view or the browser did not start).
  Then the browser, the view and the screen go, in that order, and the account opens again on its next call, on the
  service's screen: one more feed load, as after a restart. The login shows its end only once all that is done and
  the session on disk is checked: a poll never sees «conectada» that could still turn into «fallida».
- Every wait has a deadline in real time (STEP_WAIT, STOP_WAIT, END_WAIT, besides START_WAIT and the login's own),
  whatever the clock the login measures its minutes with: a stuck browser or view never holds the service, the
  account or a request forever. Cancelling, the start running out of time and the service stopping all go through
  Login.stop.
- Conectada clears a stop that was the session going away (Store.stop session=True): the person just logged in, in that
  very browser. Any other stop (429, 999, a challenge in an answer) stays for an operator: a session that is still
  valid reaches the feed with nobody having looked at anything."""
import asyncio
import hashlib
import hmac
import logging
import secrets
from collections import OrderedDict
from pathlib import Path
from urllib.parse import urlsplit

from aiohttp import WSMsgType, web

from linkedin_directo.transporte import bad_path

from . import pagina
from .ajustes import ACCOUNT
from .almacen import stamp
from .cuenta import Refused

log = logging.getLogger('navegador')
STARTING, WAITING, CONNECTED, EXPIRED, CANCELLED, FAILED = (
    'abriendo', 'esperando', 'conectada', 'vencida', 'cancelada', 'fallida')
ACTIVE = (STARTING, WAITING)
HEADER = 'X-Pantalla-Clave'
VNC_PORT = 5901  # x11vnc, on the container's loopback only
SIZE = '1366x900x24'  # the service's screen (entrada.sh): LinkedIn sees one screen size before and after the login
START_WAIT = 45.0  # seconds for the screen, the view and the login page
TICK = 1.0  # seconds between two looks at the login tab
STEP_WAIT = 15.0  # real seconds for one step that talks to the browser or the view: a look at the tab, a close
STOP_WAIT = 10.0  # real seconds a login gets to notice it must end (it looks every TICK) before it is cut short
END_WAIT = 90.0  # real seconds for its teardown after that, whose steps have their own deadlines: the last resort
VIEW_SHUTDOWN = 5.0  # seconds aiohttp gives the view's open requests when it goes (its default is 60)
KEEP = 20  # ended logins kept to answer a late poll


class Failed(Exception):
    """The login could not start or go on: its reason, for the backend and the app."""


def view_key(token, session):
    """What Caddy adds to every request of the remote view (forward_auth, from the backend's answer)."""
    return hmac.new(token.encode(), f'pantalla:{session}'.encode(), hashlib.sha256).hexdigest()


async def spawn(*argv):
    """A child process whose output is dropped: nothing of Xvfb or x11vnc is needed or logged."""
    return await asyncio.create_subprocess_exec(*argv, stdin=asyncio.subprocess.DEVNULL,
                                                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)


async def port_open(port, host='127.0.0.1'):
    try:
        _, writer = await asyncio.wait_for(asyncio.open_connection(host, port), 1)
    except (OSError, asyncio.TimeoutError):
        return False
    writer.close()
    return True


async def step(what, awaitable, seconds=STEP_WAIT):
    """One step of a teardown, with a deadline in real time: done, failed or out of time, the next one runs."""
    try:
        await asyncio.wait_for(awaitable, seconds)
    except Exception as exc:  # TimeoutError included; never more than the step and the error's type
        log.warning('conexión desde la app: %s no terminó bien (%s)', what, type(exc).__name__)


async def end_process(proc):
    if proc.returncode is None:
        try:
            proc.terminate()
            await asyncio.wait_for(proc.wait(), 5)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
        except ProcessLookupError:
            pass


def on_feed(url):
    parts = urlsplit(url or '')
    return parts.netloc == pagina.HOST and parts.path.startswith('/feed') and not bad_path(url)


class Login:
    """One login from the app, from the screen it opens to the teardown."""

    def __init__(self, owner, account):
        self.owner, self.account = owner, account
        self.id = secrets.token_urlsafe(18)
        self.state, self.reason, self.cancelled = STARTING, '', ''
        self.started = owner.clock()
        self.deadline = self.started + owner.settings.connect_minutes * 60
        self.ended = None
        self.ready = asyncio.Event()  # set once the person can log in, or once it ended
        self.ctx = self.holding = self.runner = None
        self.procs, self.sockets, self.task = [], set(), None
        self.closing = False  # the teardown began: the view lets nobody in, and the task is never cut short
        self.end_as = None  # how a stop ends it (FAILED when the start ran out of time), else CANCELLED

    def left(self):
        """Seconds until the login ends at the latest: when a refused call may come back."""
        return max(1, int(self.deadline - self.owner.clock()) + 1)

    def public(self):
        stopped = self.account.store.stopped()
        return {'sesion': self.id, 'cuenta': self.account.name, 'estado': self.state, 'motivo': self.reason,
                'inicio': stamp(self.started), 'vence': stamp(self.deadline),
                'fin': stamp(self.ended) if self.ended else None,
                'detenida': bool(stopped), 'parada': (stopped or {}).get('motivo') or ''}

    async def run(self):
        """The whole login. Its state stays STARTING or WAITING until the teardown is over and the session on disk
        checked; only then it shows how it ended."""
        state, reason, closed = None, '', False  # None: cancelled (or cut short) before any other end
        try:
            await self._open()
            if not self.cancelled:
                self.state = WAITING
                self.ready.set()
                log.info('cuenta=%s conexión desde la app: esperando a que entren en LinkedIn (hasta %s)',
                         self.account.name, stamp(self.deadline))
                state, reason, closed = await self._watch()
        except Failed as exc:
            state, reason = FAILED, str(exc)
        except asyncio.CancelledError:  # stop() cut it short: whatever was opened still goes
            asyncio.current_task().uncancel()
        except Exception as exc:  # the browser or a process failed: say what, never more
            state, reason = FAILED, f'el navegador de la conexión falló ({type(exc).__name__})'
        await self._teardown()
        if state == CONNECTED or closed:
            # Chromium writes its cookies when it closes: the profile on disk has the last word.
            try:
                stored = self.owner.stored(self.account.store.profile)
            except Exception:  # unreadable: as if it could not tell
                stored = None
            if stored is False:
                state, reason = FAILED, 'no quedó la sesión guardada en el navegador; vuelve a intentarlo'
            elif closed and stored is None:
                state, reason = CANCELLED, 'se cerró la ventana del navegador'
            else:
                state, reason = CONNECTED, ''
        if state is None:
            state, reason = self.end_as or CANCELLED, self.cancelled or 'la conexión se interrumpió'
        if state == CONNECTED:
            try:
                stopped = self.account.store.stopped()
                if stopped and stopped.get('sesion'):
                    self.account.store.resume()
                    log.info('cuenta=%s parada por la sesión quitada tras entrar desde la app', self.account.name)
            except OSError as exc:
                log.warning('cuenta=%s no se pudo quitar la parada tras entrar (%s)', self.account.name,
                            type(exc).__name__)
        self.state, self.reason, self.ended = state, reason, self.owner.clock()
        self.ready.set()
        log.info('cuenta=%s conexión desde la app: %s', self.account.name, self.state)

    async def stop(self, reason, end_as=None):
        """End the login and wait for it, in real time: STOP_WAIT seconds for it to notice (the watch looks every TICK,
        a browser still opening has its own deadlines), then what it is doing is cut short, never its teardown, which
        gets END_WAIT more. Returns once it ended, or once that last deadline passed."""
        self.cancelled = self.cancelled or reason
        self.end_as = self.end_as or end_as
        if self.task is None or self.task.done():
            return
        done, _ = await asyncio.wait({self.task}, timeout=STOP_WAIT)
        if not done and not self.closing:
            log.warning('cuenta=%s la conexión desde la app no terminó a tiempo: se corta', self.account.name)
            self.task.cancel()
        if not done:
            await asyncio.wait({self.task}, timeout=END_WAIT)

    async def _until(self, check, seconds=10.0):
        for _ in range(int(seconds / 0.25)):
            if await check():
                return True
            await asyncio.sleep(0.25)
        return False

    async def _open(self):
        owner, settings, screen = self.owner, self.owner.settings, self.owner.settings.connect_screen
        if owner.screen_ready(screen) is not False:  # a screen there already (or not a local one): never share it
            raise Failed(f'la pantalla de la conexión ({screen}) ya está en uso o no es local')
        number = screen.lstrip(':').split('.')[0]
        for stale in (Path(f'/tmp/.X{number}-lock'), pagina.X_SOCKETS / f'X{number}'):
            try:
                stale.unlink(missing_ok=True)  # left by a screen that died with an earlier process
            except OSError:  # not ours to remove (a read-only X socket folder, as under WSLg): Xvfb says so itself
                pass
        self.procs.append(await owner.spawn('Xvfb', screen, '-screen', '0', SIZE, '-nolisten', 'tcp'))

        async def screen_up():
            return owner.screen_ready(screen) is True
        if not await self._until(screen_up):
            raise Failed('la pantalla virtual de la conexión no arrancó')
        # No VNC password: x11vnc listens on the loopback only, and the one way in is the bridge below, which checks the
        # per-session key. -nevershared/-dontdisconnect: one viewer at a time, and a second one cannot push it out.
        self.procs.append(await owner.spawn('x11vnc', '-display', screen, '-localhost', '-rfbport',
                                            str(owner.vnc_port), '-nopw', '-forever', '-nevershared',
                                            '-dontdisconnect', '-quiet'))
        if not await self._until(lambda: owner.port_open(owner.vnc_port)):
            raise Failed('la vista remota (x11vnc) no arrancó')
        self.runner = await owner.serve_view(self)
        try:
            self.holding = pagina.hold(self.account.store.profile)
        except pagina.Busy:
            raise Failed('el perfil está abierto en otro navegador (¿una entrada por SSH en curso?)') from None
        self.ctx = await owner.launcher(self.account.store.profile, headless=False,
                                        proxy=settings.egress(self.account.name).option(), screen=screen)
        tab = self.ctx.pages[0] if self.ctx.pages else await self.ctx.new_page()
        await tab.goto(pagina.LOGIN, wait_until='domcontentloaded', timeout=pagina.GOTO_TIMEOUT_MS)

    async def _watch(self):
        """Until the feed with a session, the deadline, a cancel or the window closed: (state, reason, closed), the
        state None for a cancel or a closed window."""
        while True:
            if self.cancelled:
                return None, '', False
            if self.owner.clock() >= self.deadline:
                return EXPIRED, 'se acabó el tiempo sin entrar en LinkedIn', False
            if not self.ctx.pages:
                return None, '', True
            if on_feed(self.ctx.pages[0].url) and await asyncio.wait_for(pagina.has_session(self.ctx), STEP_WAIT):
                return CONNECTED, '', False
            await self.owner.sleep(TICK)

    async def _teardown(self):
        """The browser, the view and the screen, in that order, each step with its deadline (step); the profile and the
        account are let go whatever happens."""
        self.closing = True
        try:
            if self.ctx is not None:
                await step('cerrar el navegador', self.ctx.close())  # the window may already be gone
                self.ctx = None
            pagina.let_go(self.holding)
            self.holding = None
            for ws in list(self.sockets):
                await step('cerrar la vista remota', ws.close())
            if self.runner is not None:
                await step('apagar la vista remota', self.runner.cleanup())
                self.runner = None
            for proc in reversed(self.procs):
                await step('terminar un proceso de la pantalla', end_process(proc))
            self.procs = []
        finally:
            if self.holding is not None:
                pagina.let_go(self.holding)
                self.holding = None
            self.account.connecting = None


class Connections:
    """The service's logins from the app: at most one at a time."""

    def __init__(self, service, spawn=spawn, launcher=pagina.launch, stored=pagina.stored_session,
                 screen_ready=pagina.display_ready, port_open=port_open, vnc_port=VNC_PORT):
        self.service, self.settings = service, service.settings
        self.clock, self.sleep = service.clock, service.sleep
        self.spawn, self.launcher, self.stored = spawn, launcher, stored
        self.screen_ready, self.port_open, self.vnc_port = screen_ready, port_open, vnc_port
        self.current = None
        self.logins = OrderedDict()

    async def start(self, name):
        if not self.settings.connect:
            raise Refused(404, 'conectar desde la app está apagado en el servicio (NAVEGADOR_CONEXION)')
        if self.current is not None and self.current.state in ACTIVE:
            raise Refused(409, 'ya hay una conexión en curso en el servicio; termínala o cancélala primero',
                          code='conexion')
        if not ACCOUNT.fullmatch(name or ''):
            raise Refused(404, 'cuenta desconocida en el servicio')
        self.settings.account_dir(name).joinpath('perfil').mkdir(parents=True, exist_ok=True, mode=0o700)
        account = self.service.account(name)
        account._egress()  # another exit: 503 egress, as for a call; the account's first login records this one
        try:
            await asyncio.wait_for(account.lock.acquire(), self.settings.deadline)
        except asyncio.TimeoutError:
            raise Refused(503, 'cuenta ocupada con otras llamadas; vuelve a intentarlo') from None
        try:
            login = Login(self, account)
            account.connecting = login
            await account.close()
        finally:
            account.lock.release()
        self.current = self.logins[login.id] = login
        while len(self.logins) > KEEP:
            self.logins.popitem(last=False)
        login.task = asyncio.create_task(login.run())
        try:
            await asyncio.wait_for(login.ready.wait(), START_WAIT)
        except asyncio.TimeoutError:
            await login.stop('el navegador de la conexión no abrió a tiempo', end_as=FAILED)
        return login

    def find(self, session):
        return self.logins.get(session or '')

    async def cancel(self, session):
        login = self.find(session)
        if login is not None and login.state in ACTIVE:
            await login.stop('cancelada desde Barrio')
        return login

    async def close(self):
        if self.current is not None and self.current.state in ACTIVE:
            await self.current.stop('el servicio se detuvo')

    async def serve_view(self, login):
        runner = web.AppRunner(self.view(login), access_log=None, shutdown_timeout=VIEW_SHUTDOWN)
        await runner.setup()
        await web.TCPSite(runner, self.settings.host, self.settings.view_port).start()
        return runner

    def view(self, login):
        """noVNC and its WebSocket for this login only: 403 without its key, and nothing once it ended."""
        key = view_key(self.settings.token, login.id).encode()

        @web.middleware
        async def guard(request, handler):
            if (login.closing or login.state not in ACTIVE
                    or not hmac.compare_digest(request.headers.get(HEADER, '').encode(), key)):
                return web.Response(status=403, text='sin permiso')
            return await handler(request)

        async def bridge(request):
            ws = web.WebSocketResponse(protocols=('binary',), heartbeat=30)
            await ws.prepare(request)
            try:
                reader, writer = await asyncio.wait_for(asyncio.open_connection('127.0.0.1', self.vnc_port), STEP_WAIT)
            except (OSError, asyncio.TimeoutError):
                await ws.close()
                return ws
            if login.closing:  # the teardown began while this one was opening: it would miss its close
                writer.close()
                await ws.close()
                return ws
            login.sockets.add(ws)

            async def to_vnc():
                async for message in ws:
                    if message.type == WSMsgType.BINARY:
                        writer.write(message.data)
                        await writer.drain()

            async def to_browser():
                while data := await reader.read(65536):
                    await ws.send_bytes(data)

            tasks = [asyncio.create_task(to_vnc()), asyncio.create_task(to_browser())]
            try:
                await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            finally:
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                writer.close()
                await ws.close()
                login.sockets.discard(ws)
            return ws

        app = web.Application(middlewares=[guard])
        app.router.add_get('/websockify', bridge)
        if self.settings.novnc.is_dir():
            app.router.add_static('/', self.settings.novnc)
        return app
