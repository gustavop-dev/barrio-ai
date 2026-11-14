"""Conectar LinkedIn desde la app (team_backend/conexion.py): start, poll, open again and cancel a login into a
`directo` account's browser (human session), plus the two plain views the remote view goes through: `enter` swaps the
single-use ticket for the view's cookie, and `allow` answers Caddy's forward_auth with the view key."""
from django.conf import settings
from django.http import HttpResponse, HttpResponseRedirect
from django.utils import timezone
from django.views.decorators.http import require_GET
from rest_framework.response import Response
from rest_framework.views import APIView

from . import conexion
from .models import BrowserLogin, ConnectorAccount
from .operador_views import get_or_404, human_session
from .permissions import require

GONE = ('<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
        '<title>Conectar LinkedIn</title><body style="font-family:sans-serif;padding:24px">'
        '<p>Este enlace ya se usó o venció.</p><p>Vuelve a la app y pulsa «Abrir de nuevo» o «Conectar LinkedIn».</p>'
        '</body></html>')


def _link(request, raw):
    return request.build_absolute_uri('/api/v1/linkedin/pantalla/entrar') + f'?ticket={raw}' if raw else None


def _answer(request, login, raw=None, status=200):
    return Response({'login': conexion.output(login), 'url': _link(request, raw)}, status=status)


class AccountLogin(APIView):
    def post(self, request, aid):
        human_session(request)
        account = get_or_404(ConnectorAccount, id=aid)
        try:
            login, raw = conexion.start(request.user, account)
        except conexion.Unavailable as exc:
            return Response({'detail': str(exc)}, status=503)
        return _answer(request, login, raw, 201)


class LoginDetail(APIView):
    def get(self, request, lid):
        require(request.user, 'operate_linkedin')
        return _answer(request, conexion.refresh(get_or_404(BrowserLogin, id=lid)))


class LoginLink(APIView):
    def post(self, request, lid):
        human_session(request)
        login = get_or_404(BrowserLogin, id=lid)
        return _answer(request, login, conexion.new_link(request.user, login))


class LoginCancel(APIView):
    def post(self, request, lid):
        human_session(request)
        return _answer(request, conexion.cancel(request.user, get_or_404(BrowserLogin, id=lid)))


def _private(response):
    response['Cache-Control'] = 'no-store'
    response['Referrer-Policy'] = 'no-referrer'  # the ticket is in this URL
    return response


@require_GET
def enter(request):
    found = conexion.redeem(request.GET.get('ticket', '')) if conexion.enabled() else None
    if found is None:
        return _private(HttpResponse(GONE, status=410))
    login, cookie = found
    response = HttpResponseRedirect(conexion.VIEW_PAGE)
    response.set_cookie(conexion.COOKIE, cookie, max_age=max(1, int((login.expires_at - timezone.now()).total_seconds())),
                        path=conexion.VIEW, secure=settings.SESSION_COOKIE_SECURE, httponly=True, samesite='Strict')
    return _private(response)


@require_GET
def allow(request):
    key = conexion.allow(request.COOKIES.get(conexion.COOKIE, '')) if conexion.enabled() else None
    if key is None:
        return _private(HttpResponse(status=401))
    response = HttpResponse(status=200)
    response['X-Pantalla-Clave'] = key  # Caddy copies it to the request it passes on; it never reaches the browser
    return _private(response)
