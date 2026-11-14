"""The backend's Transport: an HTTP client of the navegador service, which owns one logged-in Chromium per account and
makes each call from inside its page. Wire contract: docs/navegador-contrato.md (the service implements it in phase 2).

One POST per LinkedIn call. The service answers 200 with what LinkedIn answered (judged by the client, not here) or
an error status of its own, mapped here so that nothing is ever retried and a write whose fate is unknown is
Uncertain: the service may have sent it. The bearer token is never logged or put in a message."""
import uuid
from urllib.parse import quote

import httpx

from .errores import LinkedInError, Uncertain
from .transporte import Answer, Transport

CALLS = '/v1/cuentas/{}/llamadas'
QUERIES = '/v1/cuentas/{}/consultas'
# The service waits 3 to 7 s before each call and gives LinkedIn 30 s inside the page: 75 s covers both.
READ_TIMEOUT, CONNECT_TIMEOUT = 75.0, 5.0
# The service's own answers (anything but 200): (kind, pause, sent). `sent` = the call may have reached LinkedIn.
SERVICE = {
    400: ('contract', False, False),  # the service did not understand the request
    401: ('config', True, False),  # wrong token
    403: ('config', True, False),
    404: ('config', True, False),  # unknown account in the service
    409: ('stopped', True, False),  # the service stopped this account (LinkedIn pushed back earlier): no retry
    422: ('refused', False, False),  # outside the service's allowlist: nothing left (its budget: 'budget', below)
    423: ('login', True, False),  # no session: someone has to log in by hand in that browser
    503: ('not_sent', False, False),  # browser not ready or busy: nothing left (another internet exit: 'egress', below)
    504: ('network', False, True),  # the call left the page and its answer did not come back in time
}
# What the owner has to do when the service stopped the account: the callers put the message in the pause reason.
TO_DO = {
    409: 'Revisa LinkedIn a mano en el navegador del servicio (verificación, aviso o restricción) y, cuando esté bien, '
         'reanuda la cuenta allí (python -m navegador reanudar {}) y en Barrio.',
    423: 'Inicia sesión de nuevo en LinkedIn en el navegador del servicio (python -m navegador login {}) y reanuda la '
         'cuenta en Barrio.',
}
# A 503 with `code: egress`: the account's internet exit is not the one its session last used, and the service does not
# open it (a session that hops between IPs is what LinkedIn ends sessions for). Nothing left; it lasts until someone acts.
EGRESS_TO_DO = ('Si el cambio de salida es a propósito, acéptalo en el servidor (python -m navegador salida {} --aceptar) '
                'y, si puedes, vuelve a entrar a mano desde la nueva salida; si no, vuelve a poner la salida de antes.')


class ServiceTransport(Transport):
    def __init__(self, base_url, token, account, *, http_transport=None, timeout=READ_TIMEOUT):
        self.account = account
        self.http = httpx.Client(base_url=base_url.rstrip('/'), transport=http_transport,
                                 timeout=httpx.Timeout(timeout, connect=CONNECT_TIMEOUT),
                                 headers={'authorization': f'Bearer {token}', 'accept': 'application/json'})

    def send(self, request):
        payload = {'method': request.method, 'path': request.path, 'kind': request.kind, 'body': request.body,
                   'write': request.write, 'operation': request.operation, 'request_id': str(uuid.uuid4())}
        name = request.operation or request.kind
        try:
            response = self.http.post(CALLS.format(quote(self.account, safe='')), json=payload)
        except (httpx.ConnectError, httpx.ConnectTimeout):
            raise LinkedInError(f'El servicio navegador no respondió; {name} no salió.', kind='not_sent') from None
        except httpx.HTTPError as exc:
            if request.write:
                raise Uncertain(f'El servicio navegador no contestó tras recibir {name} ({type(exc).__name__}); '
                                'resultado incierto.') from None
            raise LinkedInError(f'El servicio navegador no contestó ({type(exc).__name__}).', kind='network') from None
        if response.status_code != 200:
            kind, pause, sent = SERVICE.get(response.status_code, ('network', False, response.status_code >= 500))
            if sent and request.write:
                raise Uncertain(f'Servicio navegador: HTTP {response.status_code} tras recibir {name}; resultado incierto.')
            wait = _budget(response)
            if wait:
                # The account's budget in the service, not LinkedIn's: the message names neither a limit nor a quota,
                # so the network's rules (red.LIMIT_ERROR) never take it for LinkedIn pushing back.
                raise LinkedInError(f'Servicio navegador: presupuesto de la cuenta agotado en {name} '
                                    f'({_reason(response)}); vuelve a haber cupo en {-(-wait // 60)} min.',
                                    kind='budget', status=response.status_code, retry_after=wait)
            since = _egress(response)
            if since is not None:
                raise LinkedInError(f'Servicio navegador: no abre la cuenta por otra salida a internet en {name}; no salió '
                                    f'nada. {EGRESS_TO_DO.format(self.account)}', kind='egress',
                                    status=response.status_code, since=since)
            hint = TO_DO.get(response.status_code, '').format(self.account)
            raise LinkedInError(f'Servicio navegador: HTTP {response.status_code} en {name} ({_reason(response)}).'
                                + (f' {hint}' if hint else ''), kind=kind, status=response.status_code, pause=pause)
        try:
            data = response.json()
            return Answer(status=int(data['status']), text=data.get('text') or '',
                          content_type=data.get('content_type') or '', url=data.get('url') or '',
                          redirected=bool(data.get('redirected')))
        except (ValueError, KeyError, TypeError):
            if request.write:
                raise Uncertain(f'Servicio navegador: respuesta ilegible tras {name}; resultado incierto.') from None
            raise LinkedInError('Servicio navegador: respuesta ilegible.', kind='contract') from None

    def live_query(self, prefixes, variables):
        """A fresh GraphQL query id, when the page used one; any failure here only means the fixed id is used."""
        try:
            response = self.http.get(QUERIES.format(quote(self.account, safe='')),
                                     params={'prefixes': ','.join(prefixes), 'variables': ','.join(variables)})
            data = response.json() if response.status_code == 200 else None
        except (httpx.HTTPError, ValueError):
            return None
        return data if isinstance(data, dict) and data.get('query_id') else None


def _budget(response):
    """Seconds until the account's budget in the service has room again, for a 422 that says it was the budget
    (`code: budget`); None for anything else."""
    try:
        data = response.json() if response.status_code == 422 else {}
        wait = data.get('retry_after') if isinstance(data, dict) and data.get('code') == 'budget' else None
    except (ValueError, AttributeError):
        return None
    return max(1, min(int(wait), 86400)) if isinstance(wait, (int, float)) and not isinstance(wait, bool) else None


def _egress(response):
    """For a 503 that says it was another internet exit (`code: egress`), since when ('' when the service did not
    say); None for anything else."""
    try:
        data = response.json() if response.status_code == 503 else {}
    except (ValueError, AttributeError):
        return None
    if not isinstance(data, dict) or data.get('code') != 'egress':
        return None
    since = data.get('since')
    return since[:40] if isinstance(since, str) else ''


def _reason(response):
    """The service's short reason (`reason`), never LinkedIn's text."""
    try:
        reason = response.json().get('reason')
    except (ValueError, AttributeError):
        reason = None
    return reason[:120] if isinstance(reason, str) and reason else 'sin motivo'
