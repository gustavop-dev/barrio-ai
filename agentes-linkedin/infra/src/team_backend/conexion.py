"""Conectar LinkedIn desde la app (Ajustes › Máquina; navegador README «Conectar desde la app»). Off unless
LINKEDIN_CONEXION_APP=true, here and in the service (NAVEGADOR_CONEXION) and in Caddy's /conectar/ route.

The person logs in on LinkedIn's own page, in the navegador service's browser for a `directo` account, through a
remote view (noVNC) that exists only while that login lasts. Who reaches what:
- the app (a human session) starts, polls and cancels the login here; the service is never reachable from outside;
- the app opens a link with a single-use ticket (TICKET_TTL) in the system browser; `enter` swaps it for a cookie
  (HttpOnly, Secure, SameSite=Strict, Path=/conectar/) that lasts until the login's deadline, bound to that login;
- Caddy sends every /conectar/ request to `allow` first (forward_auth). For a live login's cookie it answers the view
  key, which Caddy adds to the request it passes to the service (X-Pantalla-Clave). The key is an HMAC of the service
  token and the login's session id: never stored, never in a URL, never given to the person's browser.
Ticket and cookie are kept only as SHA-256 hashes. Starts are limited per account and hour.

When the service says it ended: conectada clears the account's pause if it came from the service stopping it or
having no session (servicio.TO_DO) and the service no longer has it stopped; nothing else runs by itself."""
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta
from urllib.parse import quote

import httpx
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, Throttled, ValidationError

from linkedin_directo.servicio import TO_DO

from .models import BrowserLogin, ConnectorAccount
from .operador import _audit
from .permissions import require

TICKET_TTL = timedelta(minutes=2)
STARTS_PER_HOUR = 4  # per account: each start opens a browser on LinkedIn's login page
COOKIE = 'barrio_pantalla'
VIEW = '/conectar/'
# noVNC scaled to the phone's screen; the screen keeps the service's size, which LinkedIn sees.
VIEW_PAGE = VIEW + 'vnc.html?autoconnect=1&reconnect=1&resize=scale&path=conectar/websockify'
START_TIMEOUT = 60.0  # the service waits up to 45 s for the screen, the view and the login page
ACTIVE = (BrowserLogin.State.STARTING, BrowserLogin.State.WAITING)


class Unavailable(Exception):
    """The service cannot run a login now: the reason, for the app (503)."""


def enabled():
    return os.environ.get('LINKEDIN_CONEXION_APP', 'false').strip().lower() == 'true'


def _hash(raw):
    return hashlib.sha256(raw.encode()).hexdigest()


def _token():
    return os.environ.get('NAVEGADOR_TOKEN', '').strip()


def view_key(session):
    """The same key the service checks (navegador/conexion.view_key)."""
    return hmac.new(_token().encode(), f'pantalla:{session}'.encode(), hashlib.sha256).hexdigest()


def _service(method, path, timeout=10.0):
    url = os.environ.get('NAVEGADOR_URL', '').strip().rstrip('/')
    if not url or not _token():
        raise Unavailable('Falta NAVEGADOR_URL o NAVEGADOR_TOKEN en el servidor.')
    try:
        response = httpx.request(method, url + path, headers={'authorization': f'Bearer {_token()}'},
                                 timeout=httpx.Timeout(timeout, connect=5.0))
    except httpx.HTTPError:
        raise Unavailable('El navegador del servidor no responde; inténtalo más tarde.') from None
    try:
        body = response.json()
    except ValueError:
        body = {}
    return response.status_code, body if isinstance(body, dict) else {}


def _when(text):
    try:
        return datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return None


def _apply(login, body):
    """The service's view of the login: {estado, motivo, vence, detenida}."""
    state = body.get('estado')
    if state in BrowserLogin.State.values:
        login.state = state
    login.reason = str(body.get('motivo') or '')[:500]
    login.still_stopped = bool(body.get('detenida'))
    login.expires_at = _when(body.get('vence')) or login.expires_at


def ticket(login):
    """A fresh single-use ticket for the login's remote view (the previous one stops working)."""
    raw = secrets.token_urlsafe(32)
    login.ticket_hash, login.ticket_expires_at = _hash(raw), timezone.now() + TICKET_TTL
    login.save(update_fields=['ticket_hash', 'ticket_expires_at'])
    return raw


def start(user, account):
    """(login, ticket or None). Refuses another provider, too many starts, or a service that cannot."""
    require(user, 'operate_linkedin')
    if not enabled():
        raise NotFound('Conectar LinkedIn desde la app está apagado en el servidor (LINKEDIN_CONEXION_APP).')
    if account.provider != ConnectorAccount.Provider.DIRECTO:
        raise ValidationError('Solo una cuenta de LinkedIn directo se conecta desde la app.')
    now = timezone.now()
    for open_login in account.browser_logins.filter(state__in=ACTIVE):
        refresh(open_login)
        if open_login.state == BrowserLogin.State.WAITING and open_login.user_id == user.id:
            return open_login, ticket(open_login)  # the same login, opened again
    if account.browser_logins.filter(started_at__gte=now - timedelta(hours=1)).count() >= STARTS_PER_HOUR:
        raise Throttled(detail='Demasiados intentos de conectar esta cuenta en una hora; espera un rato.')
    status, body = _service('POST', f'/v1/cuentas/{quote(account.external_account_id, safe="")}/conexion',
                            START_TIMEOUT)
    if status != 201 or not body.get('sesion'):
        reason = str(body.get('reason') or f'HTTP {status}')
        if body.get('code') == 'egress':
            reason += ' La sesión de esta cuenta salía por otra conexión a internet: hay que aceptarlo en el servidor.'
        raise Unavailable(f'El navegador del servidor no abrió la conexión: {reason}')
    login = BrowserLogin(account=account, user=user, session=str(body['sesion'])[:64],
                         expires_at=now + timedelta(minutes=10))
    _apply(login, body)
    login.save()
    _audit(user, 'linkedin.login_started', account.id, login=str(login.id), state=login.state)
    if login.state not in ACTIVE:
        finish(login)
        return login, None
    return login, ticket(login)


def refresh(login):
    """The login as the service sees it now; once it ended, what follows from it (finish)."""
    if login.state not in ACTIVE:
        return login
    try:
        status, body = _service('GET', f'/v1/conexiones/{quote(login.session, safe="")}')
    except Unavailable:
        if login.expires_at > timezone.now():
            return login  # the service may be back before the deadline
        status, body = 404, {}
    if status == 404:
        login.state = BrowserLogin.State.FAILED
        login.reason = 'el navegador del servidor se reinició o ya no tiene esta conexión; vuelve a intentarlo'
    elif status == 200:
        _apply(login, body)
    else:
        return login
    login.save(update_fields=['state', 'reason', 'still_stopped', 'expires_at'])
    if login.state not in ACTIVE:
        finish(login)
    return login


def _paused_by_the_service(account):
    """Whether the account's pause is the service having stopped it or having no session (servicio.TO_DO)."""
    reason = account.paused_reason or ''
    return account.paused and any(TO_DO[code].format(account.external_account_id) in reason for code in (409, 423))


def finish(login):
    with transaction.atomic():
        done = BrowserLogin.objects.filter(pk=login.pk, finished_at__isnull=True).update(
            finished_at=timezone.now(), ticket_hash='', cookie_hash='')
        if not done:
            return  # another poll finished it
        account = ConnectorAccount.objects.select_for_update().get(pk=login.account_id)
        _audit(login.user, 'linkedin.login_finished', account.id, login=str(login.id), state=login.state,
               still_stopped=login.still_stopped)
        if login.state == BrowserLogin.State.CONNECTED and not login.still_stopped and _paused_by_the_service(account):
            account.paused, account.paused_reason = False, ''
            account.save(update_fields=['paused', 'paused_reason'])
            _audit(login.user, 'operator.account_resumed', account.id,
                   reason='Sesión de LinkedIn iniciada desde la app (Conectar LinkedIn).')


def cancel(user, login):
    require(user, 'operate_linkedin')
    if login.state in ACTIVE:
        try:
            status, body = _service('DELETE', f'/v1/conexiones/{quote(login.session, safe="")}', 20.0)
        except Unavailable:
            status, body = 0, {}
        if status == 200:
            _apply(login, body)
        if login.state in ACTIVE:
            login.state, login.reason = BrowserLogin.State.CANCELLED, 'cancelada desde la app'
        login.save(update_fields=['state', 'reason', 'still_stopped', 'expires_at'])
        _audit(user, 'linkedin.login_cancelled', login.account_id, login=str(login.id))
        finish(login)
    return login


def new_link(user, login):
    """Another ticket for the same login (the browser was closed), only for whoever started it."""
    require(user, 'operate_linkedin')
    if login.user_id != user.id:
        raise PermissionDenied('Solo quien inició esta conexión puede abrirla.')
    refresh(login)
    if login.state != BrowserLogin.State.WAITING:
        raise ValidationError('Esta conexión ya terminó.')
    return ticket(login)


def _usable(login):
    user = login.user
    return (user is not None and user.is_active and user.has_perm('team_backend.operate_linkedin')
            and login.state == BrowserLogin.State.WAITING and login.finished_at is None
            and login.expires_at > timezone.now())


def redeem(raw):
    """(login, cookie) for a valid, unused, unexpired ticket of a waiting login; None otherwise. Single use."""
    if not raw or len(raw) > 200:
        return None
    with transaction.atomic():
        # Only the login row is locked: its user is a nullable join, and PostgreSQL cannot lock that side of it.
        login = (BrowserLogin.objects.select_for_update(of=('self',)).select_related('user')
                 .filter(ticket_hash=_hash(raw), ticket_expires_at__gt=timezone.now()).first())
        if login is None:
            return None
        cookie = secrets.token_urlsafe(32)
        # Spent whatever happens next; the cookie replaces any earlier one, so only the last browser sees the view.
        login.ticket_hash, login.cookie_hash = '', _hash(cookie) if _usable(login) else ''
        login.save(update_fields=['ticket_hash', 'cookie_hash'])
        if not login.cookie_hash:
            return None
    _audit(login.user, 'linkedin.login_view_opened', login.account_id, login=str(login.id))
    return login, cookie


def allow(cookie):
    """The view key for a live login's cookie (Caddy forward_auth), or None."""
    if not cookie or len(cookie) > 200:
        return None
    login = BrowserLogin.objects.select_related('user').filter(cookie_hash=_hash(cookie)).first()
    return view_key(login.session) if login is not None and _usable(login) else None


def latest(account):
    """The account's last login, as the app shows it next to the button."""
    if account.provider != ConnectorAccount.Provider.DIRECTO:
        return None
    login = account.browser_logins.first()
    return {'enabled': enabled(), 'last': output(login) if login else None}


def output(login):
    return {'id': str(login.id), 'state': login.state, 'reason': login.reason, 'still_stopped': login.still_stopped,
            'started_at': login.started_at, 'expires_at': login.expires_at, 'finished_at': login.finished_at}
