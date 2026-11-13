"""The Transport the client talks to, and how its answers are judged.

A Transport makes ONE call to www.linkedin.com from inside the account's logged-in page and returns what came back,
without interpreting it: `send(Request) -> Answer`. Copying the session cookies to a script got the session revoked on
the second call (spike, 2026-11-13); a `fetch` made by the page itself did not. `live_query` hands the GraphQL query
ids the page used by itself while loading: they rotate with LinkedIn deploys, so a fresh one beats the fixed one.

The client (cliente.py) builds every Request, checks it against the allowlist (permitidas.py) before sending and
judges the Answer here: pushback stops the account, a write whose fate is unknown is Uncertain, the rest is a plain
error. The navegador service applies its own guards on top (pauses, budgets, hard stop); see
docs/navegador-contrato.md."""
import json
import re
from dataclasses import dataclass
from urllib.parse import urlsplit

from .errores import LinkedInError, Uncertain

KINDS = ('voyager', 'sdui', 'page')
# The headers each kind of call carries. The service adds the csrf-token (the page's JSESSIONID, read inside the page,
# never sent to us) and, for the server-driven UI, the x-li-* headers of the page's own latest call; nothing else.
HEADERS = {
    'voyager': {'accept': 'application/vnd.linkedin.normalized+json+2.1', 'x-restli-protocol-version': '2.0.0'},
    'voyager_post': {'content-type': 'application/json; charset=UTF-8'},
    'sdui': {'content-type': 'application/json'},
    'page': {'accept': 'text/html'},
}
STOP = (401, 403, 429, 999)
BAD_PATHS = ('/login', '/checkpoint', '/uas', '/authwall')
CHALLENGE = ('captcha', 'challenge', 'checkpoint', 'security verification', 'unusual activity')
CHALLENGE_TITLE = re.compile(r'<title>[^<]*(security verification|verificaci|captcha|checkpoint)', re.I)
CODE = re.compile(r'[A-Za-z][A-Za-z0-9_]{1,59}')


@dataclass(frozen=True)
class Request:
    method: str  # GET or POST
    path: str  # on www.linkedin.com, query included and already encoded
    kind: str  # voyager (JSON API), sdui (server-driven UI, a component stream) or page (an HTML document)
    body: dict | None = None
    write: bool = False
    operation: str = ''  # the connector method that sends it: the service's budgets and audit


@dataclass(frozen=True)
class Answer:
    status: int  # LinkedIn's HTTP status; 0 = no answer (timeout or network error inside the page)
    text: str = ''
    content_type: str = ''
    url: str = ''  # where the answer came from; a redirect is never followed
    redirected: bool = False


class Transport:
    """One account's way to LinkedIn. Implementations: the service client (servicio.ServiceTransport) and, in the
    phase-2 service, the page itself."""

    def send(self, request):
        raise NotImplementedError

    def live_query(self, prefixes, variables):
        """The newest GraphQL call the page made itself whose operation name starts with one of `prefixes` and used
        the same variable names (paging aside): {'path', 'query_id', 'variables', 'source'}, or None."""
        return None


def bad_path(url):
    path = urlsplit(url or '').path.lower()
    return next((p for p in BAD_PATHS if path == p or path.startswith(p + '/')), '')


def error_code(data):
    """LinkedIn's own error code in an error answer (`code` or `data.code`), when it has one."""
    for block in (data, data.get('data') if isinstance(data, dict) else None):
        code = block.get('code') if isinstance(block, dict) else None
        if isinstance(code, str) and CODE.fullmatch(code):
            return code.lower()
    return ''


def check_answer(request, answer):
    """The parsed JSON of a Voyager answer, or the text of a page or component stream. Raises LinkedInError (pause on
    pushback) or, for a write whose outcome is unknown, Uncertain."""
    status, text = answer.status or 0, answer.text or ''
    head, data = text.lstrip()[:1], None
    if head in ('{', '['):
        try:
            data = json.loads(text)
        except ValueError:
            pass
    inner = data.get('status') if isinstance(data, dict) else None
    lower = text[:8192].lower()
    html = 'html' in (answer.content_type or '').lower() or head == '<'
    name = request.operation or request.kind

    def stop(why, kind):
        raise LinkedInError(f'LinkedIn: {why} en {name}; la cuenta se detiene.', kind=kind, status=status or None,
                            pause=True)

    if answer.redirected or 300 <= status < 400:
        stop('redirección', 'redirect')
    if status in STOP or inner in STOP:
        stop(f'HTTP {status if status in STOP else inner}', 'pushback')
    if bad_path(answer.url):
        stop(f'la respuesta vino de {bad_path(answer.url)}', 'login')
    if request.kind != 'page' and html and (status < 400 or any(m in lower for m in CHALLENGE)):
        stop('HTML en vez de datos (checkpoint, CAPTCHA o muro de acceso)', 'challenge')
    if request.kind == 'page' and CHALLENGE_TITLE.search(text[:20000]):
        stop('reto o CAPTCHA en la página', 'challenge')
    if request.kind != 'page' and status >= 400 and data is None and any(m in lower for m in CHALLENGE):
        stop('reto o CAPTCHA en la respuesta', 'challenge')
    if not status:
        if request.write:
            raise Uncertain(f'LinkedIn no respondió a {name} tras enviarla; resultado incierto.')
        raise LinkedInError(f'LinkedIn no respondió a {name}.', kind='network')
    if status >= 500:
        if request.write:
            raise Uncertain(f'LinkedIn: HTTP {status} en {name}; resultado incierto.')
        raise LinkedInError(f'LinkedIn: HTTP {status} en {name}.', kind='http_error', status=status)
    if status >= 400:
        code = error_code(data)
        raise LinkedInError(f'LinkedIn: HTTP {status} en {name}' + (f' ({code}).' if code else '.'),
                            kind=f'linkedin/{code}' if code else 'not_found' if status == 404 else 'http_error',
                            status=status)
    if request.kind != 'voyager':
        return text
    if not isinstance(data, dict):
        if request.write:
            raise Uncertain(f'LinkedIn: respuesta ilegible tras {name}; resultado incierto.')
        raise LinkedInError(f'LinkedIn: respuesta sin JSON en {name}.', kind='unreadable', status=status)
    errors = data.get('errors')
    if errors and not request.write:  # GraphQL answers 200 with `errors` for a stale query id or a wrong variable
        raise LinkedInError(f'LinkedIn: GraphQL con {len(errors)} errores en {name}.', kind='graphql', status=status)
    return data
