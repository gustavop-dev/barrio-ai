"""LinkedIn without Unipile (docs/plan-linkedin-directo.md): the provider `directo`, with exactly UnipileConnector's
methods, arguments and answers, so operador, autopiloto, respuestas, red, metricas and conversaciones do not change.
One read more, only here: `analytics`, the account's creator analytics (team_backend/analitica.py).

LinkedIn itself (routes, parsing, the write allowlist) lives in the linkedin_directo package; every call is made from
inside the account's logged-in page by the navegador service (contract: docs/navegador-contrato.md). This module only
reads the configuration and maps the package's errors to the connector's: pushback pauses the account, a write whose
fate is unknown is ConnectorUncertain, a note refusal is InvitationNoteQuota only with proof.

Off by default and fail-closed: LIVE_LINKEDIN_DIRECTO=true, NAVEGADOR_URL and NAVEGADOR_TOKEN are all needed. Tests
inject a fake Transport (TRANSPORT) and never reach a service. external_account_id is the account's name in the
navegador service (a slug), never a LinkedIn credential."""
import os
import re
from linkedin_directo import Cliente, LinkedInError, NoteQuota, Uncertain
from .connectors import ConnectorError, ConnectorUncertain, InvitationNoteQuota

TRANSPORT=None  # tests inject a linkedin_directo Transport; production builds a ServiceTransport from the environment
ACCOUNT=re.compile(r'[a-z0-9][a-z0-9_\-]{0,62}')

def live():
    return os.environ.get('LIVE_LINKEDIN_DIRECTO','false').lower()=='true'

def service_transport(account_id):
    if not live():raise ConnectorError('Conector directo desactivado: configurar LIVE_LINKEDIN_DIRECTO=true.',kind='disabled')
    url=os.environ.get('NAVEGADOR_URL','').strip();token=os.environ.get('NAVEGADOR_TOKEN','').strip()
    if not url or not token:raise ConnectorError('Falta NAVEGADOR_URL o NAVEGADOR_TOKEN en el entorno privado.',kind='config')
    if not re.match(r'https?://[^/\s]+',url):raise ConnectorError('NAVEGADOR_URL debe empezar por http:// o https://.',kind='config')
    from linkedin_directo.servicio import ServiceTransport
    return ServiceTransport(url,token,account_id)

class DirectoConnector:
    provider='directo'

    def __init__(self,account_id,transport=None):
        if not ACCOUNT.fullmatch(account_id or ''):raise ConnectorError('Identificador de cuenta del navegador inválido.',kind='config')
        self.account_id=account_id
        self.client=Cliente(transport or TRANSPORT or service_transport(account_id))

    def _do(self,name,*args,**kwargs):
        try:return getattr(self.client,name)(*args,**kwargs)
        except NoteQuota as exc:raise InvitationNoteQuota(str(exc),exc.status) from None
        except LinkedInError as exc:raise ConnectorError(str(exc),status=exc.status,kind=exc.kind,pause=exc.pause) from None
        except Uncertain as exc:raise ConnectorUncertain(str(exc)) from None

    def account_status(self):return self._do('account_status')
    def get_user(self,identifier):return self._do('get_user',identifier)
    def list_user_posts(self,user_id,limit=10):return self._do('list_user_posts',user_id,limit)
    def get_post(self,post_id):return self._do('get_post',post_id)
    def list_comments(self,post_id,limit=50):return self._do('list_comments',post_id,limit)
    def create_comment(self,post_id,text):return self._do('create_comment',post_id,text)
    # INT-04: the thread of a top-level comment. No method name says «reply»: the inbox guarantee (INB-08) forbids it.
    def list_comment_thread(self,post_id,comment_id,limit=50):return self._do('list_comment_thread',post_id,comment_id,limit)
    def comment_in_thread(self,post_id,comment_id,text):return self._do('comment_in_thread',post_id,comment_id,text)
    def react_to_comment(self,post_id,comment_id,reaction):return self._do('react_to_comment',post_id,comment_id,reaction)
    def add_reaction(self,post_id,reaction):return self._do('add_reaction',post_id,reaction)
    def get_profile(self,user_id):return self._do('get_profile',user_id)
    def search_people(self,keywords,location=None,profile_language=None):return self._do('search_people',keywords,location,profile_language)
    def search_parameters(self,kind,keywords,limit=5):return self._do('search_parameters',kind,keywords,limit)
    def follow_user(self,user_id):return self._do('follow_user',user_id)
    def send_invitation(self,user_id,note=None):return self._do('send_invitation',user_id,note)
    def list_invitations(self,kind,limit=100):return self._do('list_invitations',kind,limit)
    def accept_invitation(self,request_id):return self._do('accept_invitation',request_id)
    def own_audience(self):return self._do('own_audience')
    def profile_views(self,days=14):return self._do('profile_views',days)
    # Inbox: reads only, like UnipileConnector. Nothing here sends, marks as read or edits a message.
    def list_chats(self,limit=20,inbox='CLASSIC_PRIMARY'):return self._do('list_chats',limit,inbox)
    def list_chat_messages(self,chat_id,limit=10):return self._do('list_chat_messages',chat_id,limit)
    # Only here: the account's creator analytics (linkedin_directo.analitica.Workbook). Unipile has no such read, so
    # callers check `hasattr(connector,'analytics')` (analitica.py) instead of a stub on the other providers.
    def analytics(self,start,end,order=None):return self._do('analytics',start,end,order)
