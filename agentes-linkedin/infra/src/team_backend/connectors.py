"""What every LinkedIn connector shares: the errors, the answers' shapes and the simulated account.

The real account goes through connectors_directo (LinkedIn directo, the navegador service) and own publications
through connectors_linkedin (official API). Each method performs at most one call and never retries a write: LinkedIn
gives no idempotency key, so the operator reconciles an uncertain write by reading back instead of repeating it.
FakeConnector is the in-memory account of tests and QA; the parsers below read its rows.
"""
import os
import re
import uuid
from datetime import datetime, timedelta, timezone

REACTIONS=('linkedin_like','linkedin_celebrate','linkedin_support','linkedin_love','linkedin_insightful','linkedin_funny')

class ConnectorError(Exception):
    """Definite failure: the provider did not apply the operation.
    pause=True means further writes on this account must stop until a human reviews it. `retry_after` (seconds), when
    known, is when the same call may be tried again (the navegador service's budget). `deferrable` is set only by
    connectors_directo, for the navegador service's own refusals before anything left (see `deferred`)."""
    def __init__(self,message,*,status=None,kind='error',pause=False,retry_after=None,deferrable=False):
        super().__init__(message);self.status=status;self.kind=kind;self.pause=pause;self.retry_after=retry_after
        self.deferrable=deferrable

def deferred(exc):
    """The one rule for «nothing left, wait and try again»: only the navegador service refusing before the call left,
    for a reason that is ours and not the account's (its budget, or the call not sent: browser busy or not ready, another
    internet exit, the service unreachable). Such work waits and is retried; it is never a pause, an executed or failed
    action, or a verdict on a person or a post. Every other error, of every provider (a 5xx, not found, the simulated
    not_sent…), keeps its meaning."""
    return bool(getattr(exc,'deferrable',False)) and not exc.pause

class ConnectorUncertain(Exception):
    """The write may have reached LinkedIn; its effect is unknown until reconciled."""

class InvitationNoteQuota(ConnectorError):
    """Only an explicit note-only rejection proving that no invitation was created."""
    def __init__(self,message,status=None):
        super().__init__(message,status=status,kind='note_quota')

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

SIGNAL_FLAGS=('is_creator','is_hiring','is_open_to_work','is_influencer','is_premium')

def _signals(data):
    """What a profile or a search result says about the person's reach and moment (Gustavo, 12/11/2026: no community
    or no established business makes a founder irrelevant). A simulated profile carries followers_count,
    relations_count, bio and language at the top level and the flags in specifics; a search result, the counts. None
    means not given, never zero."""
    data=data or {};specifics=data.get('specifics') or {}
    def count(key):return _count(data[key] if key in data else specifics.get(key))
    flags={k:bool(specifics.get(k,data.get(k))) for k in SIGNAL_FLAGS if k in specifics or k in data}
    out={'followers':count('followers_count'),'connections':count('relations_count'),**flags}
    if isinstance(data.get('bio'),str) and data['bio'].strip():out['bio']=data['bio'].strip()[:800]
    if isinstance(data.get('language'),str) and data['language']:out['language']=data['language'][:10]
    return {k:v for k,v in out.items() if v is not None}

def _profile(data):
    """Network view of a profile (DESC-03): distance, follow and invitation status, restrictions, signals."""
    specifics=data.get('specifics') or {}
    request=specifics.get('relation_request') or {}
    return dict(_user(data),location=data.get('location') or '',
                network_distance=specifics.get('network_distance') or data.get('network_distance') or '',
                is_following=bool(data.get('is_following')),
                relation_request_status=specifics.get('relation_request_status') or '',
                invitation_id=str(request.get('id') or ''),
                is_restricted=bool(specifics.get('is_restricted')),
                signals=_signals(data))

def _invitation(data):
    return {'id':str(data['id']),'type':data.get('type') or '','created_at':_when(data.get('created_at')),
            'message':data.get('message') or '','user':_user(data.get('user'))}

def _count(value):
    """A counter is a number, or a list of [{reaction, count}] (reactions by kind) to add up; anything else is None."""
    if isinstance(value,list):return sum(int(item.get('count') or 0) for item in value if isinstance(item,dict))
    return value if isinstance(value,int) and not isinstance(value,bool) else None

def _post(data):
    analytics=data.get('analytics') or {}
    return {'id':str(data['id']),'share_url':data.get('share_url') or '','text':data.get('text') or '',
            'created_at':_when(data.get('created_at')),'author':_user(data.get('author')),
            'comments_counter':_count(data.get('comments_counter')),'reactions_counter':_count(data.get('reactions_counter')),
            # A boolean: LinkedIn exposes whether we reacted, not which reaction.
            'user_reacted':bool(data.get('user_reacted')),'is_repost':bool(data.get('is_repost')),
            # reposts_counter: number, or null when hidden.
            'reposts_counter':_count(data.get('reposts_counter')),'impressions':_count(analytics.get('impressions_counter')),
            # analisis_referentes: the media type when the provider says it ('' = not known).
            'media':str(data.get('media') or '')[:20]}

def _audience(data):
    """Own profile counters: followers_count and relations_count at the top level, or in specifics."""
    specifics=data.get('specifics') or {}
    def pick(key):return _count(data[key] if key in data else specifics.get(key))
    return {'followers':pick('followers_count'),'connections':pick('relations_count')}

def _profile_views(data):
    """Profile views: analytics.views_count covers the window asked for; analytics is optional."""
    return _count((data.get('analytics') or {}).get('views_count'))

def _comment(data):
    return {'id':str(data['id']),'text':data.get('text') or '','created_at':_when(data.get('created_at')),
            'is_sender':bool(data.get('is_sender')),'thread_id':data.get('thread_id'),'author':_user(data.get('author')),
            # How many answers a top-level comment has.
            'reply_counter':_count(data.get('reply_counter')),
            # How many reacted to the comment: directo reads LinkedIn's count; the simulated account has none (null,
            # never zero).
            'reaction_counter':None}

def _chat(data):
    """A chat: a 1to1 one names the other member in user_id; last_message is a preview or a whole message."""
    last=data.get('last_message') or {}
    kind=data.get('type') or ('group' if data.get('is_group') else 'channel' if data.get('is_channel') else '1to1' if data.get('is_1to1') else '')
    return {'id':str(data['id']),'name':data.get('name') or '','type':kind,'user_id':str(data.get('user_id') or ''),
            'unread_count':_count(data.get('unread_count')) or 0,'is_readonly':bool(data.get('is_readonly')),
            'last_message_at':_when(data.get('last_message_timestamp') or data.get('updated_at')),
            'last_message':{'id':str(last.get('id') or ''),'text':last.get('text') or '','is_sender':bool(last.get('is_sender'))} if last else None}

def _message(data):
    """A chat message. hidden: deleted, hidden or an event (reaction, announcement…), never shown as text."""
    return {'id':str(data['id']),'text':data.get('text') or '','at':_when(data.get('timestamp')),'is_sender':bool(data.get('is_sender')),
            'sender_id':str(data.get('sender_id') or ''),'sender':_user(data.get('sender')),
            'hidden':bool(data.get('is_hidden') or data.get('is_deleted') or data.get('is_event')),
            'attachments':len(data.get('attachments') or [])}

def same_text(a,b):
    return ' '.join((a or '').split()).casefold()==' '.join((b or '').split()).casefold()


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
                                                     'network':{},'invitations':{'sent':{},'received':{}},'search':{},'chats':{},
                                                     'threads':{},'comment_reactions':{}})

    @classmethod
    def reset(cls):cls.store.clear()

    def seed_user(self,public_id,display_name,posts=()):
        user={'id':'ACo'+public_id,'public_identifier':public_id,'display_name':display_name,'profile_url':'https://www.linkedin.com/in/'+public_id}
        self.state['users'][public_id]=user;self.state['users'][user['id']]=user
        # Seed recent posts once; a fixed calendar date eventually empties the
        # autopilot's 72-hour candidate window. Preserve chronological order.
        posts=tuple(posts);now=datetime.now(timezone.utc)
        for i,text in enumerate(posts):
            pid=f'activity:{public_id}-{i}'
            self.state['posts'][pid]={'id':pid,'share_url':'https://www.linkedin.com/feed/update/urn:li:'+pid,'text':text,
                'created_at':(now-timedelta(minutes=len(posts)-i)).isoformat(),'author':user,'comments_counter':0,
                'reactions_counter':[],'reposts_counter':0,'user_reacted':False,'is_repost':False}
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
        """A post of the connected member, as list_user_posts('me') returns it."""
        pid=f'activity:me-{len(self.state["posts"])}'
        self.state['posts'][pid]={'id':pid,'share_url':'https://www.linkedin.com/feed/update/urn:li:'+pid,'text':text,
            'created_at':datetime.now(timezone.utc).isoformat(),'author':{'id':'me','display_name':'Cuenta conectada'},
            'comments_counter':0,'reactions_counter':[],'reposts_counter':0,'user_reacted':False,'is_repost':False,
            'analytics':{'impressions_counter':impressions} if impressions is not None else {}}
        self.state['comments'][pid]=[]
        return pid

    def set_post_counters(self,post_id,impressions=None,reactions=None,comments=None,reposts=None):
        """Counters as the account reports them; None means hidden or absent (null), never zero."""
        post=self.state['posts'][post_id]
        post.update(reactions_counter=[{'reaction':'👍','count':reactions}] if reactions is not None else None,
                    comments_counter=comments,reposts_counter=reposts,
                    analytics={'impressions_counter':impressions} if impressions is not None else {})

    def seed_audience(self,followers=None,connections=None,views=None):
        """Own profile and profile views; a None leaves the field out, as when LinkedIn hides it."""
        me={'object':'UserProfile','id':'me','display_name':'Cuenta conectada','provider':'LINKEDIN','specifics':{'network_distance':'SELF'}}
        if followers is not None:me['followers_count']=followers
        if connections is not None:me['relations_count']=connections
        self.state['me']=me
        self.state['profile_views']={'object':'ProfileViews','entities':[],
            **({'analytics':{'object':'ProfileViewsAnalytics','views_count':views}} if views is not None else {})}

    def own_audience(self):return _audience(self.state.get('me') or {})

    def profile_views(self,days=14):return _profile_views(self.state.get('profile_views') or {})

    def get_post(self,post_id):
        if post_id not in self.state['posts']:raise ConnectorError('Simulado: post no encontrado.',status=404,kind='provider/resource_not_found')
        return _post(self.state['posts'][post_id])

    def list_comments(self,post_id,limit=50):
        rows=[dict(c,reply_counter=len(self.state['threads'].get(c['id'],[]))) for c in self.state['comments'].get(post_id,[])]
        return [_comment(c) for c in reversed(rows)][:limit]

    def comment_on_own_post(self,post_id,user_id,text,thread=None,at=None):
        """Someone comments on an own post (or answers in the thread of `thread`), as LinkedIn lists it: no headline."""
        user=self.state['users'][user_id]
        author={k:user[k] for k in ('id','display_name','profile_url','public_identifier','type') if k in user}
        comment={'id':'comment:'+uuid.uuid4().hex[:12],'text':text,'is_sender':False,'author':author,
                 'created_at':(at or datetime.now(timezone.utc)).isoformat()}
        if thread:self.state['threads'].setdefault(thread,[]).append(dict(comment,thread_id=thread))
        else:self.state['comments'][post_id].append(comment)
        return comment['id']

    def list_comment_thread(self,post_id,comment_id,limit=50):
        self._read_fail();self.get_post(post_id)
        return [_comment(c) for c in reversed(self.state['threads'].get(comment_id,[]))][:limit]

    def comment_in_thread(self,post_id,comment_id,text):
        mode=self._fail();self.get_post(post_id)
        if not any(c['id']==comment_id for c in self.state['comments'].get(post_id,[])):
            raise ConnectorError('Simulado: comentario no encontrado.',status=404,kind='provider/resource_not_found')
        comment={'id':'comment:'+uuid.uuid4().hex[:12],'text':text,'created_at':datetime.now(timezone.utc).isoformat(),
                 'is_sender':True,'thread_id':comment_id,'author':{'id':'me','display_name':'Cuenta conectada'}}
        if mode!='uncertain_not_applied':
            self.state['threads'].setdefault(comment_id,[]).append(comment);self.state['writes']+=1
        if mode in ('uncertain_applied','uncertain_not_applied'):raise ConnectorUncertain('Simulado: timeout tras enviar.')
        return _comment(comment)

    def react_to_comment(self,post_id,comment_id,reaction):
        if reaction not in REACTIONS:raise ConnectorError('Reacción no admitida.',kind='invalid')
        mode=self._fail();self.get_post(post_id)
        if mode!='uncertain_not_applied':
            self.state['comment_reactions'][comment_id]=reaction;self.state['writes']+=1
        if mode in ('uncertain_applied','uncertain_not_applied'):raise ConnectorUncertain('Simulado: timeout tras enviar.')
        return {'reaction':reaction}

    def create_comment(self,post_id,text):
        mode=self._fail();self.get_post(post_id)
        comment={'id':'comment:'+uuid.uuid4().hex[:12],'text':text,'created_at':datetime.now(timezone.utc).isoformat(),
                 'is_sender':True,'author':{'id':'me','display_name':'Cuenta conectada'}}
        if mode!='uncertain_not_applied':
            self.state['comments'][post_id].append(comment);self.state['writes']+=1
        if mode in ('uncertain_applied','uncertain_not_applied'):raise ConnectorUncertain('Simulado: timeout tras enviar.')
        return _comment(comment)

    # -- network
    def seed_person(self,public_id,display_name,headline='',distance='SECOND_DEGREE',comment_on=None,comment='',search=None,kind='individual',
                    location='',signals=None):
        """A LinkedIn member who may comment on a seeded post and/or appear in a keyword search."""
        user={'id':'ACo'+public_id,'public_identifier':public_id,'display_name':display_name,'headline':headline,
              'profile_url':'https://www.linkedin.com/in/'+public_id,'type':kind}
        if location:user['location']=location
        if signals:user['signals']=dict(signals)
        self.state['users'][public_id]=user;self.state['users'][user['id']]=user
        self.state['network'][user['id']]={'network_distance':distance,'is_following':False,'relation_request_status':''}
        if comment_on:
            # As on LinkedIn, a comment author carries name, id and URL but no headline.
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
        return dict(_user(user),location=user.get('location',''),network_distance=net['network_distance'],is_following=net['is_following'],
                    relation_request_status=net['relation_request_status'],invitation_id=sent['id'] if sent else '',is_restricted=False,
                    signals=dict(user.get('signals',{})))

    def search_people(self,keywords,location=None,profile_language=None):
        self.state.setdefault('search_calls',[]).append({'keywords':keywords,'location':location,'profile_language':profile_language})
        return [dict(_user(self.state['users'][uid]),location=self.state['users'][uid].get('location',''),
                     network_distance=self.state['network'][uid]['network_distance'],signals=dict(self.state['users'][uid].get('signals',{})))
                for uid in self.state['search'].get(keywords,[])]

    def search_parameters(self,kind,keywords,limit=5):
        self.state.setdefault('parameter_calls',[]).append((kind,keywords))
        return [{'id':'103644278','name':'United States'}] if kind=='LOCATION' and keywords.lower()=='united states' else []

    def follow_user(self,user_id):
        mode=self._fail();self.get_profile(user_id)
        if mode!='uncertain_not_applied':self.state['network'][user_id]['is_following']=True;self.state['writes']+=1
        if mode in ('uncertain_applied','uncertain_not_applied'):raise ConnectorUncertain('Simulado: timeout tras enviar.')
        return {'user_id':user_id}

    def send_invitation(self,user_id,note=None):
        mode=self._fail();self.get_profile(user_id)
        rid='inv:'+uuid.uuid4().hex[:10]
        invitation={'id':rid,'type':'sent','message':note or '','created_at':datetime.now(timezone.utc).isoformat(),'user':self.state['users'][user_id]}
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

    # -- inbox (reads only, like the real connector: nothing here sends a message)
    def seed_chat(self,user_id,messages,chat_id=None):
        """A 1to1 chat with a seeded member. messages: [(text, is_sender, datetime)], oldest first."""
        user=self.state['users'][user_id];cid=chat_id or 'chat-'+user['public_identifier']
        self.state['chats'][cid]={'user':user,'messages':[]}
        for text,is_sender,at in messages:self.add_message(cid,text,is_sender,at)
        return cid

    def add_message(self,chat_id,text,is_sender=False,at=None):
        chat=self.state['chats'][chat_id];user=chat['user']
        me={'object':'User','id':'me','type':'individual','display_name':'Cuenta conectada'}
        message={'object':'Message','id':'msg-'+uuid.uuid4().hex[:12],'chat_id':chat_id,'sender_id':'me' if is_sender else user['id'],
                 'sender':me if is_sender else dict(user,object='User'),'text':text,'is_sender':is_sender,'is_hidden':False,
                 'is_deleted':False,'is_event':False,'attachments':[],'timestamp':(at or datetime.now(timezone.utc)).isoformat()}
        chat['messages'].append(message)
        return message['id']

    def _read_fail(self):
        mode=self.state.pop('read_fail',None)
        if mode=='rate_limit':raise ConnectorError('Simulado: HTTP 429.',status=429,kind='provider/too_many_requests',pause=True)
        if mode=='reject':raise ConnectorError('Simulado: HTTP 404.',status=404,kind='provider/resource_not_found')

    def list_chats(self,limit=20,inbox='CLASSIC_PRIMARY'):
        self._read_fail();rows=[]
        for cid,chat in self.state['chats'].items():
            last=chat['messages'][-1] if chat['messages'] else None
            rows.append({'object':'Chat','id':cid,'name':chat['user']['display_name'],'type':'1to1','is_1to1':True,'user_id':chat['user']['id'],
                         'unread_count':0 if not last or last['is_sender'] else 1,'last_message_timestamp':last['timestamp'] if last else None,
                         'last_message':{'object':'MessagePreview','id':last['id'],'text':last['text'],'is_sender':last['is_sender']} if last else None})
        rows.sort(key=lambda c:c['last_message_timestamp'] or '',reverse=True)
        return [_chat(c) for c in rows[:limit]]

    def list_chat_messages(self,chat_id,limit=10):
        self._read_fail()
        if chat_id not in self.state['chats']:raise ConnectorError('Simulado: chat no encontrado.',status=404,kind='provider/resource_not_found')
        return [_message(m) for m in reversed(self.state['chats'][chat_id]['messages'])][:limit]

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
    if account.provider=='fake':return FakeConnector(account.external_account_id)
    if account.provider=='directo':
        from .connectors_directo import DirectoConnector
        return DirectoConnector(account.external_account_id)
    if account.provider in ('linkedin','linkedin_fake'):
        from .connectors_linkedin import connector_for
        return connector_for(account)
    raise ConnectorError('Proveedor de LinkedIn desconocido.',kind='config')
