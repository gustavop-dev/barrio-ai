"""The HTTP side of the contract (docs/navegador-contrato.md):

- POST /v1/cuentas/{cuenta}/llamadas  one LinkedIn call; 200 with what LinkedIn answered, or the service's own status
- GET  /v1/cuentas/{cuenta}/consultas  a fresh GraphQL query id the page used itself
- GET  /health                         for the container's health check: no token, no data

/v1 needs `Authorization: Bearer <NAVEGADOR_TOKEN>`, compared in constant time (401 without it, 403 when wrong).
aiohttp's access log is off: each call gets one line from cuenta.py with nothing LinkedIn answered in it."""
import asyncio
import hmac
import logging
import random
import re
import time

from aiohttp import web

from linkedin_directo.transporte import KINDS, Request

from . import pagina
from .ajustes import ACCOUNT
from .cuenta import Account, Refused

log = logging.getLogger('navegador')
REQUEST_ID = re.compile(r'[A-Za-z0-9\-]{8,64}')
OPERATION = re.compile(r'[a-z_]{0,64}')
NAME = re.compile(r'[A-Za-z][A-Za-z0-9_]{0,100}')
MAX_PATH = 8192


class Service:
    def __init__(self, settings, opener=None, clock=time.time, sleep=asyncio.sleep, rand=random.uniform):
        self.settings, self.opener, self.clock = settings, opener, clock
        self.deps = {'clock': clock, 'sleep': sleep, 'rand': rand}
        self.accounts = {}

    def account(self, name):
        if not ACCOUNT.fullmatch(name or '') or not (self.settings.account_dir(name) / 'perfil').is_dir():
            raise Refused(404, 'cuenta desconocida en el servicio')
        if name not in self.accounts:
            self.accounts[name] = Account(name, self.settings, self.opener, **self.deps)
        return self.accounts[name]

    async def close(self):
        for account in self.accounts.values():
            await account.close()
        await pagina.stop_driver()


SERVICE = web.AppKey('service', Service)


def reason(status, text, code='', retry_after=None, since=None):
    """The service's own answer. A spent budget adds `code: budget` and `retry_after` (seconds, also as the header);
    another internet exit, `code: egress` and `since` (when that refusal began)."""
    body, headers = {'reason': text}, {}
    if code:
        body['code'] = code
    if retry_after is not None:
        body['retry_after'], headers['Retry-After'] = retry_after, str(retry_after)
    if since:
        body['since'] = since
    return web.json_response(body, status=status, headers=headers)


@web.middleware
async def token(request, handler):
    if request.path.startswith('/v1/'):
        scheme, _, given = request.headers.get('Authorization', '').partition(' ')
        if scheme.lower() != 'bearer' or not given.strip():
            return reason(401, 'falta el token')
        if not hmac.compare_digest(given.strip().encode(), request.app[SERVICE].settings.token.encode()):
            return reason(403, 'token incorrecto')
    return await handler(request)


def parse(data):
    """The Request and request_id of a call body; Refused(400) for anything else."""
    if not isinstance(data, dict):
        raise Refused(400, 'se esperaba un objeto JSON')
    method, path, kind, body = data.get('method'), data.get('path'), data.get('kind'), data.get('body')
    write, operation, request_id = data.get('write', False), data.get('operation') or '', data.get('request_id')
    if method not in ('GET', 'POST') or kind not in KINDS or not isinstance(path, str) or not 0 < len(path) <= MAX_PATH \
            or not (body is None or isinstance(body, dict)) or not isinstance(write, bool) \
            or not isinstance(operation, str) or not OPERATION.fullmatch(operation) \
            or not isinstance(request_id, str) or not REQUEST_ID.fullmatch(request_id):
        raise Refused(400, 'petición mal formada')
    return Request(method, path, kind, body, write, operation), request_id


async def calls(request):
    service = request.app[SERVICE]
    arrived, name, operation = service.clock(), request.match_info['cuenta'], '-'
    try:
        try:
            data = await request.json()
        except (ValueError, UnicodeDecodeError):
            raise Refused(400, 'el cuerpo no es JSON') from None
        call, request_id = parse(data)
        operation = call.operation or '-'
        answer = await service.account(name).call(call, request_id, arrived)
    except Refused as exc:
        log.info('cuenta=%s op=%s -> %s %s', name if ACCOUNT.fullmatch(name) else '?', operation, exc.status, exc.reason)
        return reason(exc.status, exc.reason, exc.code, exc.retry_after, exc.since)
    return web.json_response({'status': answer.status, 'text': answer.text, 'content_type': answer.content_type,
                              'url': answer.url, 'redirected': answer.redirected})


async def queries(request):
    service = request.app[SERVICE]
    arrived, name = service.clock(), request.match_info['cuenta']
    prefixes = [p for p in request.query.get('prefixes', '').split(',') if p]
    variables = [v for v in request.query.get('variables', '').split(',') if v]
    try:
        if not prefixes or not all(NAME.fullmatch(x) for x in prefixes + variables):
            raise Refused(400, 'prefixes y variables mal formados')
        found = await service.account(name).live_query(prefixes, variables, arrived)
    except Refused as exc:
        log.info('cuenta=%s consultas -> %s %s', name if ACCOUNT.fullmatch(name) else '?', exc.status, exc.reason)
        return reason(exc.status, exc.reason, exc.code, exc.retry_after, exc.since)
    return web.json_response(found)


async def health(request):
    return web.json_response({'status': 'ok'})


def build(settings, **deps):
    """The aiohttp app. `deps` (opener, clock, sleep, rand) replace the browser and time in the tests."""
    app = web.Application(middlewares=[token], client_max_size=1024 * 1024)
    service = Service(settings, **deps)
    app[SERVICE] = service
    app.router.add_get('/health', health)
    app.router.add_post('/v1/cuentas/{cuenta}/llamadas', calls)
    app.router.add_get('/v1/cuentas/{cuenta}/consultas', queries)

    async def cleanup(app):
        await service.close()
    app.on_cleanup.append(cleanup)
    return app


def serve(settings):
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    for noisy in ('aiohttp.access', 'asyncio'):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    log.info('servicio navegador en %s:%s (datos en %s)', settings.host, settings.port, settings.data)
    web.run_app(build(settings), host=settings.host, port=settings.port, access_log=None, print=None)
