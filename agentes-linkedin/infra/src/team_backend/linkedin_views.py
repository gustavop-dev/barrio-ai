"""OAuth of the official LinkedIn API for Gustavo's member account, and its status for the PWA.

The session cookie is SameSite=Strict, so LinkedIn's cross-site redirect to the callback arrives
without it. The callback then bounces once through a same-site page (meta refresh) and validates
the `state` saved in the session on the second, same-site request."""
import secrets
import time
from django.http import HttpResponse, HttpResponseRedirect
from django.utils.html import escape
from django.views.decorators.http import require_GET
from urllib.parse import urlencode
from rest_framework.response import Response
from rest_framework.views import APIView
from . import connectors_linkedin as li
from .connectors import ConnectorError
from .jobs import audit
from .operador_views import human_session
from .permissions import require

STATE_KEY='linkedin_oauth_state'
STATE_TTL=600

class OAuthStart(APIView):
    def get(self,request):
        human_session(request);require(request.user,'approve_actions')
        state=secrets.token_urlsafe(32)
        try:url=li.authorization_url(state)
        except ConnectorError as exc:return Response({'detail':str(exc)},status=503)
        request.session[STATE_KEY]={'value':state,'at':time.time()}
        audit(request.user,'linkedin.oauth_started','linkedin',request.request_id)
        return HttpResponseRedirect(url)

def _done(result,reason=''):
    return HttpResponseRedirect('/ajustes?'+urlencode({'linkedin':result,**({'motivo':reason} if reason else {})}))

def _bounce(request):
    params={k:request.GET[k] for k in ('code','state','error') if k in request.GET}
    target=request.path+'?'+urlencode(dict(params,rebote='1'))
    response=HttpResponse(f'<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0;url={escape(target)}">'
                          f'<title>Barrio AI</title><p>Conectando LinkedIn… <a href="{escape(target)}">continuar</a></p>')
    response['Cache-Control']='no-store';response['Referrer-Policy']='no-referrer'
    return response

@require_GET
def oauth_callback(request):
    user=request.user
    saved=request.session.get(STATE_KEY) if user.is_authenticated else None
    if saved is None and request.GET.get('rebote')!='1':return _bounce(request)
    request.session.pop(STATE_KEY,None)  # single use
    if not user.is_authenticated or not saved:return _done('error','sesion')
    if not user.has_perm('team_backend.approve_actions'):return _done('error','permiso')
    state=request.GET.get('state','')
    valid=(isinstance(saved,dict) and isinstance(saved.get('value'),str) and secrets.compare_digest(saved['value'],state)
           and time.time()-float(saved.get('at',0))<=STATE_TTL)
    if not valid:
        audit(user,'linkedin.oauth_rejected','linkedin',getattr(request,'request_id',''),reason='state')
        return _done('error','state')
    if request.GET.get('error'):
        audit(user,'linkedin.oauth_rejected','linkedin',getattr(request,'request_id',''),reason='denied')
        return _done('error','denegado')
    code=request.GET.get('code','')
    if not code or len(code)>2000:return _done('error','code')
    try:
        token=li.exchange_code(code)
        li.connect_member(user,token,li.userinfo(token['access_token']))
    except ConnectorError as exc:
        # Never log the code or token; only the failure kind.
        audit(user,'linkedin.oauth_failed','linkedin',getattr(request,'request_id',''),kind=exc.kind,http_status=exc.status)
        return _done('error','scope' if exc.kind=='scope' else 'canje')
    return _done('ok')

class Status(APIView):
    def get(self,request):
        require(request.user,'operate_linkedin')
        return Response(li.status_payload())
