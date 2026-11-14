"""One account: its page and the guards every call passes, in this order (docs/navegador-contrato.md):

1. the allowlist, the backend's own (linkedin_directo.permitidas.check): outside it, 422 and nothing leaves;
2. a write's request_id: already answered, the same answer again; in flight, or lost mid-send by a crash, 409;
3. the stop flag: LinkedIn pushed back before, 409 until an operator clears it;
4. one call at a time per account; a call that cannot reach the page within the deadline does not leave (503);
5. the budgets, per hour and per day, reads and writes apart, and per day each kind of write: 422 with code `budget`
   and the seconds until the window has room again (retry_after);
6. the page, opened on the first call and kept open, only by the internet exit the session last used (a different
   one, 503 until an operator accepts it); no session, 423; profile in use, no browser or no screen for it, 503. Only
   when `idle_minutes` is set (off by default: the backend calls at least hourly, so it would mostly churn) it is
   closed after that long without calls, and the next call opens it again: one more feed load, as LinkedIn sees it;
7. a random pause, then the page checked (on LinkedIn, the session cookie there, no 429/999 on its own calls);
8. ONE fetch from inside the page, its answer returned as it came. Never a retry, never a redirect followed.

The answer is judged with the backend's own check_answer: pushback (401/403/429/999, a redirect, a login, checkpoint or
CAPTCHA page, HTML where data was expected) stops the account, and so do the page leaving for a login or checkpoint
path and the session cookie disappearing. The answer that showed it still goes back (the call left; the backend judges
it as well) and every later call gets 409.

Logs carry the account, the operation, the route without ids or query, statuses and timings: never a body, a cookie,
a token or anything LinkedIn answered."""
import asyncio
import json
import logging
import math
import random
import re
import time
from urllib.parse import parse_qs, urlsplit

from linkedin_directo import permitidas, rutas
from linkedin_directo.errores import LinkedInError, Uncertain
from linkedin_directo.transporte import HEADERS, Answer, check_answer

from . import pagina
from .almacen import IMPORTED, Store

log = logging.getLogger('navegador')
HOUR, DAY = 3600, 86400
WORDS = {'read': 'lecturas', 'write': 'escrituras', 'hour': 'hora', 'day': 'día', 'comment': 'comentarios y respuestas',
         'reaction': 'reacciones', 'follow': 'seguimientos', 'invitation': 'invitaciones', 'accept': 'aceptaciones'}
WRITES = {rutas.COMMENT: 'comment', rutas.REACT: 'reaction', rutas.FOLLOW: 'follow'}  # by sduiid
IDS = re.compile(r'urn(?::|%3A)li(?::|%3A)[^/]*|ACo[A-Za-z0-9_\-]{6,}|\d{5,}')
TAG = re.compile(r'[A-Za-z][A-Za-z0-9_.]{0,100}')


class Refused(Exception):
    """The service does not make the call: the HTTP status it answers and a short reason, never LinkedIn's data. A spent
    budget also says so (`code` budget) and when it has room again (`retry_after`, seconds); another internet exit says
    so too (`code` egress) and since when it is refused (`since`): only an operator clears that one."""

    def __init__(self, status, reason, code='', retry_after=None, since=None):
        super().__init__(reason)
        self.status, self.reason, self.code, self.retry_after, self.since = status, reason, code, retry_after, since


def write_kind(request):
    """Which of the five writes an allowed request is, read from the request itself (not from its operation name): a
    comment and a reply share one."""
    if request.kind == 'voyager':
        return 'invitation' if request.path == rutas.voyager(rutas.INVITE) else 'accept'
    return WRITES.get((parse_qs(urlsplit(request.path).query).get('sduiid') or [''])[0], '')


def route(path):
    """A path fit for a log line: no query, ids masked; the sduiid or GraphQL operation name kept as a label."""
    parts = urlsplit(path)
    query = parse_qs(parts.query)
    tag = ((query.get('sduiid') or [''])[0] or (query.get('queryId') or [''])[0].split('.')[0]
           or (query.get('q') or [''])[0])
    return (IDS.sub('{id}', parts.path) + (f' {tag}' if TAG.fullmatch(tag) else ''))[:140]


def pushback(request, answer):
    """(why this answer stops the account, by the backend's own judgment (pause=True), or ''; whether that was the
    session: an answer from a login or checkpoint page)."""
    try:
        check_answer(request, answer)
    except LinkedInError as exc:
        return (str(exc), exc.kind == 'login') if exc.pause else ('', False)
    except Uncertain:
        return '', False
    return '', False


class Account:
    def __init__(self, name, settings, opener=None, clock=time.time, sleep=asyncio.sleep, rand=random.uniform,
                 display=pagina.display_ready):
        self.name, self.settings = name, settings
        self.opener = opener or pagina.Page.open
        self.clock, self.sleep, self.rand, self.display = clock, sleep, rand, display
        self.store = Store(settings.account_dir(name))
        self.lock = asyncio.Lock()
        self.page = None
        self.connecting = None  # the login from the app in progress on this account (conexion.Login), if any
        self.in_flight = set()
        self.used = clock()  # the last call or query: the page closes after settings.idle_minutes without one
        self.store.prune_writes(time.time())

    # --- the two things the service is asked -------------------------------------------------------------------------
    async def call(self, request, request_id, arrived):
        """LinkedIn's Answer to one request, or Refused."""
        try:
            permitidas.check(request)
        except LinkedInError:
            raise Refused(422, 'fuera de la lista permitida; no salió nada') from None
        if request.write:
            done = self.store.write_record(request_id)
            if done and done.get('state') == 'answered' and isinstance(done.get('answer'), dict):
                log.info('cuenta=%s op=%s request_id repetido: la respuesta guardada, sin volver a enviar',
                         self.name, request.operation or '-')
                return Answer(**done['answer'])
            if done or request_id in self.in_flight:
                raise Refused(409, 'request_id repetido: esa escritura ya salió o está saliendo; no se repite')
            self.in_flight.add(request_id)
        try:
            self._not_stopped()
            await self._acquire(arrived)
            try:
                return await self._send(request, request_id, arrived)
            finally:
                self.used = self.clock()
                self.lock.release()
        finally:
            if request.write:
                self.in_flight.discard(request_id)

    async def live_query(self, prefixes, variables, arrived):
        """The newest GraphQL call the page made itself while loading, shaped like the asker's: {path, query_id,
        variables, source}. Opens the page if it is not open yet (the next call needs it anyway)."""
        self._not_stopped()
        await self._acquire(arrived)
        try:
            page = await self._open()
            found = pagina.pick_live(page.live, prefixes, variables)
        finally:
            self.used = self.clock()
            self.lock.release()
        if not found:
            raise Refused(404, 'la página no hizo ninguna consulta así')
        return {'path': found['path'], 'query_id': found['query_id'], 'variables': found['variables'],
                'source': 'page'}

    async def close(self):
        page, self.page = self.page, None
        if page is not None:
            await page.close()

    async def close_if_idle(self):
        """Close the page after settings.idle_minutes without a call (0 = never): an open account's browser holds about
        1 GiB. Never while a call holds or waits for the account. True when it closed."""
        idle = self.settings.idle_minutes * 60
        if not idle or self.page is None or self.lock.locked() or self.clock() - self.used < idle:
            return False
        async with self.lock:  # behind a call that was about to take it, if any: then that call counts as use
            if self.page is None or self.clock() - self.used < idle:
                return False
            await self.close()
        log.info('cuenta=%s navegador cerrado tras %.0f min sin llamadas; la próxima llamada lo vuelve a abrir',
                 self.name, idle / 60)
        return True

    # --- the guards --------------------------------------------------------------------------------------------------
    def _not_stopped(self):
        if self.connecting is not None:
            # Not a stop: nothing is wrong with the account, and the backend retries the call later (503, never paused).
            raise Refused(503, 'se está entrando a mano en LinkedIn en esta cuenta desde la app; no salió nada',
                          code='conexion', retry_after=self.connecting.left())
        if self.store.stopped():
            raise Refused(409, 'cuenta detenida: LinkedIn frenó antes; alguien tiene que revisarla y reanudarla')

    async def _acquire(self, arrived):
        left = self.settings.deadline - (self.clock() - arrived)
        try:
            await asyncio.wait_for(self.lock.acquire(), max(left, 0.001))
        except asyncio.TimeoutError:
            raise Refused(503, 'cuenta ocupada con otras llamadas; no salió nada') from None

    def _budget(self, kinds):
        """Refused(422, code 'budget') when a window of any of `kinds` is spent, with the seconds until the last of them
        has room again. A refused call counts nowhere."""
        now, spent, wait = self.clock(), [], 0.0
        for kind in kinds:
            sent = self.store.usage(kind, now)
            for window, span in (('hour', HOUR), ('day', DAY)):
                cap = self.settings.budgets.get((kind, window))
                inside = sorted(t for t in sent if now - t < span)
                if cap is None or len(inside) < cap:
                    continue
                spent.append(f'{WORDS[kind]} por {WORDS[window]}')
                wait = max(wait, inside[len(inside) - cap] + span - now if cap else span)
        if spent:
            raise Refused(422, f'tope de {" y ".join(spent)} agotado; no salió nada', code='budget',
                          retry_after=max(1, math.ceil(wait)))

    def _egress(self):
        """A session going out by another IP is what LinkedIn ends sessions for: the first open records this account's
        exit; a different one (or a profile imported from another machine) does not open until an operator accepts
        it. The label only: never the proxy's address or credentials."""
        label, last = self.settings.egress(self.name).label, self.store.egress()
        if last is None:
            self.store.set_egress(label, self.clock())
        elif last != label:
            log.warning('cuenta=%s salida distinta de la última (%s, ahora %s): no se abre', self.name, last, label)
            why = 'la sesión se importó de otro equipo' if last == IMPORTED else 'la salida a internet cambió'
            raise Refused(503, f'{why}; no salió nada. Para abrirla por esta salida: python -m navegador salida '
                               f'{self.name} --aceptar', code='egress', since=self.store.egress_refused(self.clock()))
        else:
            self.store.egress_matches()
        return label

    async def _stop(self, reason, session=False):
        self.store.stop(reason, self.clock(), session=session)
        log.warning('cuenta=%s DETENIDA: %s', self.name, reason)
        await self.close()

    async def _open(self):
        page = self.page
        if page is not None and not page.alive():
            await self.close()
            page = None
        if page is not None and self.clock() - page.loaded_at > self.settings.reload_hours * HOUR:
            try:
                await page.reload()  # fresh query ids; a tab left on one load for days looks abandoned
            except pagina.Stop as exc:
                await self._stop(str(exc), exc.session)
                raise Refused(409, 'LinkedIn frenó al recargar el inicio; la cuenta se detiene') from None
            except Exception as exc:
                log.warning('cuenta=%s la recarga falló (%s); se vuelve a abrir', self.name, type(exc).__name__)
                await self.close()
                page = None
        if page is None:
            label = self._egress()
            if not self.settings.headless and self.display() is False:
                log.warning('cuenta=%s sin pantalla para el navegador (%s no responde)', self.name, pagina.display())
                raise Refused(503, 'sin pantalla para el navegador (la pantalla virtual no responde); no salió nada. '
                                   'Reinicia el contenedor del servicio')
            try:
                self.page = await self.opener(self.store.profile, self.settings)
            except pagina.NoSession:
                raise Refused(423, 'sin sesión de LinkedIn en este navegador: alguien tiene que entrar a mano') from None
            except pagina.Busy:
                raise Refused(503, 'el perfil está abierto en otro navegador; no salió nada') from None
            except pagina.Stop as exc:
                await self._stop(str(exc), exc.session)
                raise Refused(409, 'LinkedIn frenó al abrir el inicio; la cuenta se detiene') from None
            except Exception as exc:
                log.warning('cuenta=%s el navegador no abrió (%s)', self.name, type(exc).__name__)
                raise Refused(503, f'el navegador no abrió ({type(exc).__name__}); no salió nada') from None
            log.info('cuenta=%s navegador abierto (salida %s)', self.name, label)
        return self.page

    def _headers(self, request, page):
        if request.kind == 'voyager':
            headers = {**HEADERS['voyager'], **page.voyager_headers}
            if request.method == 'POST':
                headers.update(HEADERS['voyager_post'])
            return headers
        if request.kind == 'sdui':
            return {**page.sdui_headers, **HEADERS['sdui']}
        return dict(HEADERS['page'])

    async def _send(self, request, request_id, arrived):
        self._not_stopped()  # again: a call queued behind the one that stopped the account
        kinds = ('write', write_kind(request)) if request.write else ('read',)
        kinds = tuple(k for k in kinds if k)
        self._budget(kinds)
        page = await self._open()
        waited, pause = self.clock() - arrived, self.rand(*self.settings.pause)
        await self.sleep(pause)
        if self.clock() - arrived > self.settings.deadline:
            raise Refused(503, 'se agotó el plazo antes de salir; no salió nada')
        try:
            reason = await page.trouble()
        except Exception as exc:
            await self.close()
            raise Refused(503, f'la página no está lista ({type(exc).__name__}); no salió nada') from None
        if reason:
            await self._stop(reason, pagina.lost_session(reason))
            raise Refused(409, 'LinkedIn frenó antes de esta llamada; la cuenta se detiene; no salió nada')
        if request.write:
            self.store.sending(request_id, self.clock())
        self.store.count(kinds, self.clock())
        started = self.clock()
        body = json.dumps(request.body, ensure_ascii=False) if request.body is not None else None
        try:
            raw = await page.fetch(request.path, request.method, self._headers(request, page), body)
        except Exception as exc:  # the page navigated, closed or crashed mid-call: it may have left
            try:
                reason = await page.trouble()
            except Exception:
                reason = ''
            await (self._stop(reason, pagina.lost_session(reason)) if reason else self.close())
            log.warning('cuenta=%s op=%s %s %s -> la página falló durante la llamada (%s)', self.name,
                        request.operation or '-', request.method, route(request.path), type(exc).__name__)
            raise Refused(504, 'la página falló durante la llamada; pudo haber salido') from None
        answer = Answer(status=int(raw.get('status') or 0), text=raw.get('text') or '',
                        content_type=raw.get('ctype') or '', url=raw.get('url') or '',
                        redirected=raw.get('type') == 'opaqueredirect')
        took = self.clock() - started
        reason, session = pushback(request, answer)
        if not reason:
            try:
                reason = await page.trouble()
                session = pagina.lost_session(reason)
            except Exception:  # the answer is in hand; the page will be opened again for the next call
                await self.close()
        if request.write:
            self.store.answered(request_id, {'status': answer.status, 'text': answer.text,
                                             'content_type': answer.content_type, 'url': answer.url,
                                             'redirected': answer.redirected}, self.clock())
        log.info('cuenta=%s op=%s %s %s %s -> %s (espera %.1f s, pausa %.1f s, linkedin %.1f s)', self.name,
                 request.operation or '-', request.method, request.kind, route(request.path),
                 'redirección' if answer.redirected else answer.status, waited, pause, took)
        if reason:
            await self._stop(reason, session)
        return answer
