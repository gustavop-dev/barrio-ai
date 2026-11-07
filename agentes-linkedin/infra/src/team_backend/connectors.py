"""LinkedIn connectors used by the account operator.

Each method performs at most one provider call and never retries a write. Unipile v2
documents no idempotency key, so the operator reconciles uncertain writes by reading
back the post instead of repeating them.
Contract: https://developer.unipile.com/v2.0/reference/api-usage.md (consulted 2026-11-06).
"""
import os
import re
import uuid
from datetime import datetime, timezone
from urllib.parse import quote
import httpx

REACTIONS=('linkedin_like','linkedin_celebrate','linkedin_support','linkedin_love','linkedin_insightful','linkedin_funny')

class ConnectorError(Exception):
    """Definite failure: the provider did not apply the operation.
    pause=True means further writes on this account must stop until a human reviews it."""
    def __init__(self,message,*,status=None,kind='error',pause=False):
        super().__init__(message);self.status=status;self.kind=kind;self.pause=pause

class ConnectorUncertain(Exception):
    """The write may have reached LinkedIn; its effect is unknown until reconciled."""

def public_identifier(value):
    """Accept a public slug or a linkedin.com/in/ URL; never guess from a name."""
    value=(value or '').strip()
    match=re.search(r'linkedin\.com/in/([^/?#]+)',value)
    slug=(match.group(1) if match else value).strip('/')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9\-_%.]{1,99}',slug):raise ValueError('Identificador público de LinkedIn inválido')
    return slug

def _when(value):
    if not value:return None
    try:return datetime.fromisoformat(str(value).replace('Z','+00:00'))
    except ValueError:return None

def _user(data):
    data=data or {}
    return {'id':str(data.get('id') or ''),'public_identifier':data.get('public_identifier') or '',
            'display_name':data.get('display_name') or '','profile_url':data.get('profile_url') or '',
            'headline':data.get('headline') or data.get('description') or '','type':data.get('type') or ''}

def _profile(data):
    """Network view of a profile (DESC-03): distance, follow and invitation status, restrictions."""
    specifics=data.get('specifics') or {}
    request=specifics.get('relation_request') or {}
    return dict(_user(data),location=data.get('location') or '',
                network_distance=specifics.get('network_distance') or data.get('network_distance') or '',
                is_following=bool(data.get('is_following')),
                relation_request_status=specifics.get('relation_request_status') or '',
                invitation_id=str(request.get('id') or ''),
                is_restricted=bool(specifics.get('is_restricted')))

def _invitation(data):
    return {'id':str(data['id']),'type':data.get('type') or '','created_at':_when(data.get('created_at')),
            'message':data.get('message') or '','user':_user(data.get('user'))}

def _count(value):
    """Unipile v2 reports reactions as [{reaction, count}]; older shapes use an int."""
    if isinstance(value,list):return sum(int(item.get('count') or 0) for item in value if isinstance(item,dict))
    return value if isinstance(value,int) and not isinstance(value,bool) else None

def _post(data):
    analytics=data.get('analytics') or {}
    return {'id':str(data['id']),'share_url':data.get('share_url') or '','text':data.get('text') or '',
            'created_at':_when(data.get('created_at')),'author':_user(data.get('author')),
            'comments_counter':_count(data.get('comments_counter')),'reactions_counter':_count(data.get('reactions_counter')),
            # A boolean: LinkedIn exposes whether we reacted, not which reaction.
            'user_reacted':bool(data.get('user_reacted')),'is_repost':bool(data.get('is_repost')),
            'impressions':_count(analytics.get('impressions_counter'))}

def _comment(data):
    return {'id':str(data['id']),'text':data.get('text') or '','created_at':_when(data.get('created_at')),
            'is_sender':bool(data.get('is_sender')),'thread_id':data.get('thread_id'),'author':_user(data.get('author'))}

def same_text(a,b):
    return ' '.join((a or '').split()).casefold()==' '.join((b or '').split()).casefold()


class UnipileConnector:
    provider='unipile'
    host='https://api.unipile.com'

    def __init__(self,account_id,api_key=None,transport=None):
        if os.environ.get('LIVE_LINKEDIN','false').lower()!='true':
            raise ConnectorError('Conector LinkedIn desactivado: configurar LIVE_LINKEDIN=true.',kind='disabled')
        key=api_key or os.environ.get('UNIPILE_API_KEY')
        if not key:raise ConnectorError('Falta UNIPILE_API_KEY en el entorno privado.',kind='disabled')
        if not re.fullmatch(r'acc_[A-Za-z0-9_\-]+',account_id or ''):raise ConnectorError('Identificador de cuenta Unipile inválido.',kind='config')
        self.account_id=account_id
        self.http=httpx.Client(base_url=self.host,transport=transport,timeout=httpx.Timeout(30.0,connect=10.0),
                               headers={'X-API-KEY':key,'accept':'application/json'})

    def _path(self,*parts):
        return '/v2/'+self.account_id+'/'+'/'.join(quote(str(p),safe='') for p in parts)

    def _error(self,response):
        try:body=response.json()
        except ValueError:body={}
        kind=body.get('type') or 'http_error';status=response.status_code
        # Re-authentication, permission/restriction signals and rate limits stop the account.
        pause=status in (401,403,429) or kind in ('api/account_restricted','provider/invalid_authorization')
        return ConnectorError(f'Unipile: HTTP {status} ({kind}).',status=status,kind=kind,pause=pause)

    def _read(self,path,params=None):
        try:response=self.http.get(path,params=params)
        except httpx.HTTPError as exc:raise ConnectorError(f'Unipile no respondió: {type(exc).__name__}.',kind='network') from None
        if response.status_code>=400:raise self._error(response)
        return response.json()

    def _query(self,path,body,params=None):
        """A read sent as POST (search): failures are definite, never uncertain."""
        try:response=self.http.post(path,json=body,params=params)
        except httpx.HTTPError as exc:raise ConnectorError(f'Unipile no respondió: {type(exc).__name__}.',kind='network') from None
        if response.status_code>=400:raise self._error(response)
        return response.json()

    def _write(self,path,body):
        try:response=self.http.post(path,json=body)
        except (httpx.ConnectError,httpx.ConnectTimeout):
            raise ConnectorError('Unipile: no fue posible conectar; la acción no se envió.',kind='not_sent') from None
        except httpx.HTTPError as exc:
            raise ConnectorUncertain(f'Unipile: respuesta incierta ({type(exc).__name__}).') from None
        # Gateway/provider timeouts and server errors may hide an applied write.
        if response.status_code>=500:raise ConnectorUncertain(f'Unipile: HTTP {response.status_code}; resultado incierto.')
        if response.status_code>=400:raise self._error(response)
        try:return response.json()
        except ValueError:raise ConnectorUncertain('Unipile: respuesta ilegible tras escribir.') from None

    def account_status(self):
        # running = operational; errored/disconnected/degraded/partial require attention.
        for item in self._read('/v2/accounts',{'provider':'linkedin','limit':'100'}).get('data',[]):
            if item.get('id')==self.account_id:
                return {'status':item.get('status') or 'unknown','is_locked':bool(item.get('is_locked'))}
        return {'status':'missing','is_locked':True}

    def get_user(self,identifier):return _user(self._read(self._path('users',identifier)))

    def list_user_posts(self,user_id,limit=10):
        return [_post(p) for p in self._read(self._path('users',user_id,'posts'),{'limit':limit}).get('data',[])]

    def get_post(self,post_id):return _post(self._read(self._path('posts',post_id)))

    def list_comments(self,post_id,limit=50):
        data=self._read(self._path('posts',post_id,'comments'),{'limit':limit,'sort_by':'MOST_RECENT'})
        return [_comment(c) for c in data.get('data',[])]

    def create_comment(self,post_id,text):return _comment(self._write(self._path('posts',post_id,'comments'),{'text':text}))

    def add_reaction(self,post_id,reaction):
        if reaction not in REACTIONS:raise ConnectorError('Reacción no admitida.',kind='invalid')
        self._write(self._path('posts',post_id,'reactions'),{'reaction':reaction})
        return {'reaction':reaction}

    # -- network (DESC-02/03, RED-01/02/03/04); profile reads do not notify a visit
    def get_profile(self,user_id):return _profile(self._read(self._path('users',user_id)))

    def search_people(self,keywords):
        data=self._query(self._path('linkedin','search','people'),{'keywords':keywords})
        return [dict(_user(p),location=p.get('location') or '',network_distance=p.get('network_distance') or '')
                for p in data.get('data',[]) if p.get('id')]

    def follow_user(self,user_id):
        self._write(self._path('users','me','follow',user_id),{});return {'user_id':user_id}

    def send_invitation(self,user_id):
        # No note: the free account only has a handful of notes a month (reparto v1.1).
        return _invitation(self._write(self._path('users','me','relation-requests'),{'user_id':user_id}))

    def list_invitations(self,kind,limit=100):
        if kind not in ('sent','received'):raise ConnectorError('Tipo de invitación inválido.',kind='invalid')
        data=self._read(self._path('users','me','relation-requests'),{'type':kind,'limit':limit})
        return [_invitation(i) for i in data.get('data',[])]

    def accept_invitation(self,request_id):
        self._write(self._path('users','me','relation-requests',request_id,'accept'),{});return {'request_id':request_id}


class FakeConnector:
    """In-memory LinkedIn for tests and local rehearsals. Never touches the network.
    `fail_next` simulates provider outcomes: reject, rate_limit, uncertain_applied,
    uncertain_not_applied, not_sent."""
    provider='fake'
    store={}

    def __init__(self,account_id):
        if os.environ.get('OPERATOR_ALLOW_FAKE','false').lower()!='true':
            raise ConnectorError('Conector simulado desactivado (OPERATOR_ALLOW_FAKE).',kind='disabled')
        self.account_id=account_id
        self.state=self.store.setdefault(account_id,{'status':'running','is_locked':False,'users':{},'posts':{},'comments':{},'reactions':{},'fail_next':None,'writes':0,
                                                     'network':{},'invitations':{'sent':{},'received':{}},'search':{}})

    @classmethod
    def reset(cls):cls.store.clear()

    def seed_user(self,public_id,display_name,posts=()):
        user={'id':'ACo'+public_id,'public_identifier':public_id,'display_name':display_name,'profile_url':'https://www.linkedin.com/in/'+public_id}
        self.state['users'][public_id]=user;self.state['users'][user['id']]=user
        for i,text in enumerate(posts):
            pid=f'activity:{public_id}-{i}'
            self.state['posts'][pid]={'id':pid,'share_url':'https://www.linkedin.com/feed/update/urn:li:'+pid,'text':text,
                'created_at':datetime(2026,11,6,12,i,tzinfo=timezone.utc).isoformat(),'author':user,'comments_counter':0,
                'reactions_counter':[],'user_reacted':False,'is_repost':False}
            self.state['comments'][pid]=[]
        return user

    def _fail(self):
        mode=self.state['fail_next'];self.state['fail_next']=None
        if mode=='reject':raise ConnectorError('Simulado: HTTP 422.',status=422,kind='provider/unprocessable_entity')
        if mode=='rate_limit':raise ConnectorError('Simulado: HTTP 429.',status=429,kind='provider/too_many_requests',pause=True)
        if mode=='not_sent':raise ConnectorError('Simulado: sin conexión.',kind='not_sent')
        return mode

    def account_status(self):return {'status':self.state['status'],'is_locked':self.state['is_locked']}

    def get_user(self,identifier):
        user=self.state['users'].get(identifier)
        if not user:raise ConnectorError('Simulado: perfil no encontrado.',status=404,kind='provider/resource_not_found')
        return _user(user)

    def list_user_posts(self,user_id,limit=10):
        return [_post(p) for p in self.state['posts'].values() if p['author']['id']==user_id][:limit]

    def seed_own_post(self,text,impressions=None):
        """A post of the connected member, as Unipile returns it for list_user_posts('me') (opaque id)."""
        pid=f'activity:me-{len(self.state["posts"])}'
        self.state['posts'][pid]={'id':pid,'share_url':'https://www.linkedin.com/feed/update/urn:li:'+pid,'text':text,
            'created_at':datetime.now(timezone.utc).isoformat(),'author':{'id':'me','display_name':'Cuenta conectada'},
            'comments_counter':0,'reactions_counter':[],'user_reacted':False,'is_repost':False,
            'analytics':{'impressions_counter':impressions} if impressions is not None else {}}
        self.state['comments'][pid]=[]
        return pid

    def get_post(self,post_id):
        if post_id not in self.state['posts']:raise ConnectorError('Simulado: post no encontrado.',status=404,kind='provider/resource_not_found')
        return _post(self.state['posts'][post_id])

    def list_comments(self,post_id,limit=50):return [_comment(c) for c in reversed(self.state['comments'].get(post_id,[]))][:limit]

    def create_comment(self,post_id,text):
        mode=self._fail();self.get_post(post_id)
        comment={'id':'comment:'+uuid.uuid4().hex[:12],'text':text,'created_at':datetime.now(timezone.utc).isoformat(),
                 'is_sender':True,'author':{'id':'me','display_name':'Cuenta conectada'}}
        if mode!='uncertain_not_applied':
            self.state['comments'][post_id].append(comment);self.state['writes']+=1
        if mode in ('uncertain_applied','uncertain_not_applied'):raise ConnectorUncertain('Simulado: timeout tras enviar.')
        return _comment(comment)

    # -- network
    def seed_person(self,public_id,display_name,headline='',distance='SECOND_DEGREE',comment_on=None,comment='',search=None,kind='individual'):
        """A LinkedIn member who may comment on a seeded post and/or appear in a keyword search."""
        user={'id':'ACo'+public_id,'public_identifier':public_id,'display_name':display_name,'headline':headline,
              'profile_url':'https://www.linkedin.com/in/'+public_id,'type':kind}
        self.state['users'][public_id]=user;self.state['users'][user['id']]=user
        self.state['network'][user['id']]={'network_distance':distance,'is_following':False,'relation_request_status':''}
        if comment_on:
            # Like Unipile v2, a comment author carries name, id and URL but no headline.
            author={k:user[k] for k in ('id','display_name','profile_url','type')}
            self.state['comments'][comment_on].append({'id':'comment:'+uuid.uuid4().hex[:12],'text':comment,'is_sender':False,
                'created_at':datetime(2026,11,6,13,0,tzinfo=timezone.utc).isoformat(),'author':author})
        if search:self.state['search'].setdefault(search,[]).append(user['id'])
        return user

    def receive_invitation(self,user_id,message=''):
        rid='inv:'+uuid.uuid4().hex[:10]
        self.state['invitations']['received'][rid]={'id':rid,'type':'received','message':message,
            'created_at':datetime(2026,11,6,14,0,tzinfo=timezone.utc).isoformat(),'user':self.state['users'][user_id]}
        return rid

    def get_profile(self,user_id):
        user=self.state['users'].get(user_id)
        if not user:raise ConnectorError('Simulado: perfil no encontrado.',status=404,kind='provider/resource_not_found')
        net=self.state['network'].setdefault(user['id'],{'network_distance':'THIRD_DEGREE','is_following':False,'relation_request_status':''})
        sent=next((i for i in self.state['invitations']['sent'].values() if i['user']['id']==user['id']),None)
        return dict(_user(user),location='',network_distance=net['network_distance'],is_following=net['is_following'],
                    relation_request_status=net['relation_request_status'],invitation_id=sent['id'] if sent else '',is_restricted=False)

    def search_people(self,keywords):
        return [dict(_user(self.state['users'][uid]),location='',network_distance=self.state['network'][uid]['network_distance'])
                for uid in self.state['search'].get(keywords,[])]

    def follow_user(self,user_id):
        mode=self._fail();self.get_profile(user_id)
        if mode!='uncertain_not_applied':self.state['network'][user_id]['is_following']=True;self.state['writes']+=1
        if mode in ('uncertain_applied','uncertain_not_applied'):raise ConnectorUncertain('Simulado: timeout tras enviar.')
        return {'user_id':user_id}

    def send_invitation(self,user_id):
        mode=self._fail();self.get_profile(user_id)
        rid='inv:'+uuid.uuid4().hex[:10]
        invitation={'id':rid,'type':'sent','message':'','created_at':datetime.now(timezone.utc).isoformat(),'user':self.state['users'][user_id]}
        if mode!='uncertain_not_applied':
            self.state['invitations']['sent'][rid]=invitation;self.state['network'][user_id]['relation_request_status']='PENDING'
            self.state['writes']+=1
        if mode in ('uncertain_applied','uncertain_not_applied'):raise ConnectorUncertain('Simulado: timeout tras enviar.')
        return _invitation(invitation)

    def list_invitations(self,kind,limit=100):
        return [_invitation(i) for i in self.state['invitations'][kind].values()][:limit]

    def accept_invitation(self,request_id):
        mode=self._fail()
        invitation=self.state['invitations']['received'].get(request_id)
        if not invitation:raise ConnectorError('Simulado: invitación inexistente.',status=404,kind='provider/resource_not_found')
        if mode!='uncertain_not_applied':
            del self.state['invitations']['received'][request_id]
            self.state['network'][invitation['user']['id']]['network_distance']='FIRST_DEGREE';self.state['writes']+=1
        if mode in ('uncertain_applied','uncertain_not_applied'):raise ConnectorUncertain('Simulado: timeout tras enviar.')
        return {'request_id':request_id}

    def accept_sent(self,user_id):
        """Simulate the other person accepting our invitation."""
        for rid,inv in list(self.state['invitations']['sent'].items()):
            if inv['user']['id']==user_id:del self.state['invitations']['sent'][rid]
        self.state['network'][user_id].update(network_distance='FIRST_DEGREE',relation_request_status='')

    def add_reaction(self,post_id,reaction):
        if reaction not in REACTIONS:raise ConnectorError('Reacción no admitida.',kind='invalid')
        mode=self._fail();self.get_post(post_id)
        if mode!='uncertain_not_applied':
            self.state['posts'][post_id]['user_reacted']=True;self.state['writes']+=1
        if mode in ('uncertain_applied','uncertain_not_applied'):raise ConnectorUncertain('Simulado: timeout tras enviar.')
        return {'reaction':reaction}


def get_connector(account):
    if account.provider=='unipile':return UnipileConnector(account.external_account_id)
    if account.provider=='fake':return FakeConnector(account.external_account_id)
    if account.provider in ('linkedin','linkedin_fake'):
        from .connectors_linkedin import connector_for
        return connector_for(account)
    raise ConnectorError('Proveedor de LinkedIn desconocido.',kind='config')
