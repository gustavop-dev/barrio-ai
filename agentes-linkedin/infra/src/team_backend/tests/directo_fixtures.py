"""Hand-written LinkedIn answers for the direct provider's tests, and a fake Transport that serves them.

Only the STRUCTURE mirrors what LinkedIn answered in the spike of 2026-11-13 (field names and nesting, the same ones
its canary checks). Every value is invented: no real person, id, urn, text or token."""
import json
import re
from datetime import datetime, timezone
from linkedin_directo import Answer, Transport
from linkedin_directo import rutas

UTC=timezone.utc
OWN=('ACoCuentaPrueba000001','cuenta-de-prueba','1000001','Cuenta','Prueba')
ANA=('ACoAnaFicticia0000002','ana-ficticia','2000002','Ana','Ficticia')
LUIS=('ACoLuisFicticio000003','luis-ficticio','3000003','Luis','Ficticio')
POSTED=datetime(2026,11,10,15,0,tzinfo=UTC)

def snowflake(when,n=1):
    """A LinkedIn-like id: epoch milliseconds shifted left 22 bits (how a post's date is read back)."""
    return str((int(when.timestamp()*1000)<<22)+n)

POST=snowflake(POSTED,1)
OTHER_POST=snowflake(POSTED,2)
COMMENT_A=snowflake(datetime(2026,11,10,16,0,tzinfo=UTC),3)
COMMENT_B=snowflake(datetime(2026,11,10,17,0,tzinfo=UTC),4)
REPLY=snowflake(datetime(2026,11,10,18,0,tzinfo=UTC),5)
THREAD='2-ZmFrZVRocmVhZDE='
GROUP='2-ZmFrZUdyb3VwMQ=='

def ms(when):return int(when.timestamp()*1000)

# --------------------------------------------------------------------------- transport

def ok(data):return Answer(200,json.dumps(data),'application/json','https://www.linkedin.com/voyager/api/x')
def html(text):return Answer(200,text,'text/html; charset=utf-8','https://www.linkedin.com/page')
def stream(text):return Answer(200,text,'text/x-component','https://www.linkedin.com/flagship-web/x')

class FakeTransport(Transport):
    """Answers by (method, path regex), in order; a request nobody answers fails the test. `live` maps a GraphQL
    operation prefix to a live query record."""
    def __init__(self,*routes,live=None):
        self.routes=list(routes);self.sent=[];self.live=live or {};self.live_asked=[]

    def send(self,request):
        self.sent.append(request)
        for method,pattern,answer in self.routes:
            if request.method==method and re.search(pattern,request.path):
                return answer(request) if callable(answer) else answer
        raise AssertionError(f'Sin respuesta para {request.method} {request.path}')

    def live_query(self,prefixes,variables):
        self.live_asked.append((tuple(prefixes),tuple(variables)))
        return next((v for k,v in self.live.items() if k.startswith(tuple(prefixes))),None)

    def paths(self):return [r.path for r in self.sent]

# --------------------------------------------------------------------------- people

def mini(person,occupation='Trabaja en una empresa ficticia'):
    fsd,public,member,first,last=person
    return {'$type':'com.linkedin.voyager.identity.shared.MiniProfile','entityUrn':f'urn:li:fs_miniProfile:{fsd}',
            'dashEntityUrn':f'urn:li:fsd_profile:{fsd}','objectUrn':f'urn:li:member:{member}','publicIdentifier':public,
            'firstName':first,'lastName':last,'occupation':occupation}

def me():
    return {'data':{'*miniProfile':f'urn:li:fs_miniProfile:{OWN[0]}','plainId':int(OWN[2])},'included':[mini(OWN)]}

def full_profile(person,headline='Producto e IA aplicada (ficticio)',place='Ciudad Ficticia, País de Prueba'):
    fsd,public,member,first,last=person
    return {'data':{'*elements':[f'urn:li:fsd_profile:{fsd}']},'included':[
        {'$type':'com.linkedin.voyager.dash.identity.profile.Profile','entityUrn':f'urn:li:fsd_profile:{fsd}',
         'publicIdentifier':public,'firstName':first,'lastName':last,'headline':headline,'objectUrn':f'urn:li:member:{member}',
         'summary':'Texto de prueba sobre producto.','geoLocation':{'*geo':'urn:li:fsd_geo:900001'}},
        {'$type':'com.linkedin.voyager.dash.common.Geo','entityUrn':'urn:li:fsd_geo:900001','defaultLocalizedName':place}]}

def top_card(person,relationship=None,following=False,followers=120,connections=80):
    """The profile top card: Profile, its MemberRelationship union and its FollowingState."""
    fsd,public=person[0],person[1]
    state=f'urn:li:fsd_followingState:urn:li:fsd_profile:{fsd}'
    return {'data':{'data':{'identityDashProfilesByMemberIdentity':{'*elements':[f'urn:li:fsd_profile:{fsd}']}}},'included':[
        {'$type':'com.linkedin.voyager.dash.identity.profile.Profile','entityUrn':f'urn:li:fsd_profile:{fsd}','publicIdentifier':public,
         '*followingState':state,'connections':{'paging':{'total':connections}},'*memberRelationship':f'urn:li:fsd_memberRelationship:{fsd}'},
        {'$type':'com.linkedin.voyager.dash.relationships.MemberRelationship','entityUrn':f'urn:li:fsd_memberRelationship:{fsd}',
         'memberRelationship':relationship if relationship is not None else {'noConnection':{'memberDistance':'DISTANCE_2'}}},
        {'$type':'com.linkedin.voyager.dash.feed.FollowingState','entityUrn':state,'following':following,'followerCount':followers}]}

def profile_views(n):
    return {'data':{'*elements':['urn:li:fs_wvmpCard:1']},'included':[{'$type':'com.linkedin.voyager.identity.me.Card',
        'entityUrn':'urn:li:fs_wvmpCard:1','value':{'com.linkedin.voyager.identity.me.wvmpOverview.WvmpViewersCard':{
            'insightCards':[{'value':{'com.linkedin.voyager.identity.me.wvmpOverview.WvmpSummaryInsightCard':{'numViews':n}}}]}}}]}

# --------------------------------------------------------------------------- posts and comments

def counts(urn,likes=0,comments=0,shares=0,liked=False,impressions=None):
    return {'$type':'com.linkedin.voyager.feed.shared.SocialActivityCounts','entityUrn':f'urn:li:fs_socialActivityCounts:{urn}',
            'urn':urn,'numLikes':likes,'numComments':comments,'numShares':shares,'liked':liked,'numImpressions':impressions}

def update(activity,text,person,reshared=False):
    fsd,public,member,first,last=person
    out={'$type':'com.linkedin.voyager.feed.render.UpdateV2','entityUrn':f'urn:li:fs_updateV2:(urn:li:activity:{activity},MEMBER_SHARES)',
         'updateMetadata':{'urn':f'urn:li:activity:{activity}'},'commentary':{'text':{'text':text}},
         'actor':{'urn':f'urn:li:member:{member}','name':{'text':f'{first} {last}'},'description':{'text':'Titular ficticio'},
                  'navigationContext':{'actionTarget':f'https://www.linkedin.com/in/{public}?miniProfileUrn=urn%3Ali%3Afs_miniProfile%3A{fsd}'},
                  'image':{'attributes':[{'*miniProfile':f'urn:li:fs_miniProfile:{fsd}'}]}}}
    if reshared:out['*resharedUpdate']=f'urn:li:fs_updateV2:(urn:li:activity:{OTHER_POST},MEMBER_SHARES)'
    return out

def posts(*rows):
    """rows: (activity, text, author, counts kwargs)."""
    included,refs=[],[]
    for activity,text,person,kw in rows:
        u=update(activity,text,person);refs.append(u['entityUrn'])
        included+=[u,counts(f'urn:li:activity:{activity}',**kw),mini(person)]
    return {'data':{'*elements':refs,'paging':{'count':len(rows),'start':0}},'included':included}

def highlighted(activity,text='Un post de prueba',liked=False):
    """get_post's finder: a wrapper whose *value is the asked update, then a feed post nobody asked for."""
    first,feed=update(activity,text,OWN),update(OTHER_POST,'Otro post del feed',ANA)
    wrapper={'entityUrn':f'urn:li:fs_feedUpdate:{activity}','*value':first['entityUrn']}
    return {'data':{'*elements':[wrapper['entityUrn'],feed['entityUrn']]},'included':[
        wrapper,first,feed,counts(f'urn:li:activity:{activity}',likes=4,comments=2,shares=1,liked=liked),
        counts(f'urn:li:activity:{OTHER_POST}',likes=9),mini(OWN),mini(ANA)]}

def comment(post,cid,text,person,created,parent=None,distance='DISTANCE_2',company=False):
    fsd,public,member,first,last=person
    actor=({'com.linkedin.voyager.feed.CompanyActor':{'urn':'urn:li:company:4000004','*miniCompany':'urn:li:fs_miniCompany:4000004'}}
           if company else {'com.linkedin.voyager.feed.MemberActor':{'urn':f'urn:li:member:{member}',
                            '*miniProfile':f'urn:li:fs_miniProfile:{fsd}','distance':{'value':distance},'following':False}})
    return {'$type':'com.linkedin.voyager.feed.Comment','entityUrn':f'urn:li:fs_objectComment:({cid},activity:{post})',
            'urn':f'urn:li:comment:(activity:{post},{cid})','commentV2':{'text':text},'createdTime':ms(created),
            'commenter':actor,'commenterForDashConversion':{'title':{'text':'Empresa Ficticia' if company else f'{first} {last}'}},
            'parentCommentUrn':f'urn:li:comment:(activity:{post},{parent})' if parent else None}

def comments(post,rows,embedded=()):
    """rows: (comment, replies); `embedded` are replies LinkedIn tucks into `included` without listing them."""
    included,refs=[],[]
    for c,replies in rows:
        refs.append(c['entityUrn']);included+=[c,counts(c['urn'],likes=1,comments=replies)]
    included+=list(embedded)+[mini(OWN),mini(ANA),mini(LUIS)]
    return {'data':{'*elements':refs,'paging':{'count':len(rows),'start':0}},'included':included}

def post_page(activity,drawn=()):
    """The post page: its comment box's createComment request and one per drawn comment, inside escaped script
    strings, as the page keeps them."""
    def box(n,parent=None):
        collection={'threadUrn':{'activityUrn':{'activityId':activity}}}
        if parent:collection['parentCommentUrn']={'commentId':parent,'thread':f'urn:li:activity:{activity}'}
        payload={'collection':collection,'trackingId':'seguimiento-ficticio',
                 **{field:{'key':f'{field}-ficticio{n}','namespace':'MemoryNamespace'} for field,_,_ in rutas.COMMENT_BOX}}
        return {'requestId':rutas.COMMENT,'requestedArguments':{'payload':payload},'onSuccess':{'$type':'proto.sdui.actions.core.Noop'}}
    tree=[box(0)]+[box(i+1,c) for i,c in enumerate(drawn)]
    escaped=json.dumps(tree,separators=(',',':')).replace('"','\\"')
    return html(f'<html><head><title>Post</title></head><body><script>self.__next_f.push([1,"{escaped}"])</script></body></html>')

# --------------------------------------------------------------------------- search

def search_page(people):
    """The people search page: its snippet request lists the results' profile and member ids; a lazy filter bar too."""
    snippet={'requestId':rutas.SNIPPETS,'requestedArguments':{'payload':{
        'memberProfileIds':[f'urn:li:fsd_profile:{p[0]}' for p in people],'memberEntityUrns':[f'urn:li:member:{p[2]}' for p in people]}}}
    bar={'$type':'proto.sdui.actions.core.LoadComponent','requestedArguments':{'payload':{'consulta':'ficticia'}},'newComponentId':rutas.FILTER_BAR}
    escaped=json.dumps([snippet,bar],separators=(',',':')).replace('"','\\"')
    return html(f'<html><head><title>Buscar</title></head><body><script>self.__next_f.push([1,"{escaped}"])</script></body></html>')

def filter_bar():
    focus={'requestId':rutas.GEO_TYPEAHEAD,'requestedArguments':{'payload':{'emptyStateKeyword':'a','keywordsField':{'key':'k0'}}}}
    typing={'requestId':rutas.GEO_TYPEAHEAD,'requestedArguments':{'payload':{'keywordsField':{'key':'ubicacion-ficticia','namespace':'MemoryNamespace'}}}}
    return stream('0:["$","div",null,{"children":['+json.dumps(focus,separators=(',',':'))+','+json.dumps(typing,separators=(',',':'))+']}]')

def typeahead(places):
    rows=[]
    for gid,label in places:
        rows+=['{"children":["%s"]}'%label,'{"action":{"newString":"%s","key":{"key":{"value":{"$case":"id","id":"SEARCH_FILTER_geoUrn"}}}}}'%gid]
    return stream('1:{"items":['+','.join(rows)+'],"errors":[]}')

# --------------------------------------------------------------------------- invitations

def invitation(iid,other,kind,sent,secret='secreto-ficticio',message=None):
    me_urn=f'urn:li:fs_miniProfile:{OWN[0]}';other_urn=f'urn:li:fs_miniProfile:{other[0]}'
    return {'$type':'com.linkedin.voyager.relationships.invitation.Invitation','entityUrn':f'urn:li:fs_relInvitation:{iid}',
            'sharedSecret':secret,'sentTime':ms(sent),'invitationType':'PENDING','message':message,'customMessage':bool(message),
            'invitee':{'$type':'com.linkedin.voyager.relationships.invitation.ProfileInvitee','*miniProfile':me_urn if kind=='received' else other_urn},
            '*fromMember':other_urn if kind=='received' else me_urn,'*toMember':me_urn if kind=='received' else other_urn}

def invitations(kind,rows,newsletter=False):
    """rows: (id, other person, sent datetime, message). A newsletter invitation can come in the same list."""
    included,refs=[],[]
    for iid,other,sent,message in rows:
        view=f'urn:li:fs_relInvitationView:{iid}';refs.append(view)
        included+=[{'$type':'com.linkedin.voyager.relationships.invitation.InvitationView','entityUrn':view,
                    '*invitation':f'urn:li:fs_relInvitation:{iid}','genericInvitationView':None},
                   invitation(iid,other,kind,sent,message=message),mini(other)]
    if newsletter:
        refs.append('urn:li:fs_relInvitationView:8888')
        included+=[{'entityUrn':'urn:li:fs_relInvitationView:8888','*invitation':'urn:li:fs_relInvitation:8888',
                    '*genericInvitationView':'urn:li:fs_relGenericInvitationView:8888'},
                   {'entityUrn':'urn:li:fs_relInvitation:8888','sharedSecret':'boletin','sentTime':None,'invitationType':'PENDING',
                    'invitee':{'$type':'com.linkedin.voyager.relationships.invitation.GenericInvitee'}}]
    return {'data':{'*elements':refs,'paging':{'count':len(refs),'start':0,'total':0}},'included':included+[mini(OWN)]}

# --------------------------------------------------------------------------- messaging

def participant(person):
    fsd,public,member,first,last=person
    return {'$type':'com.linkedin.messenger.MessagingParticipant','entityUrn':f'urn:li:msg_messagingParticipant:urn:li:fsd_profile:{fsd}',
            'hostIdentityUrn':f'urn:li:fsd_profile:{fsd}','participantType':{'member':{
                'firstName':{'text':first},'lastName':{'text':last},'headline':{'text':'Titular ficticio'},
                'profileUrl':f'https://www.linkedin.com/in/{public}','distance':'DISTANCE_1'}}}

def message_entity(thread,mid,text,sender,at,render='DEFAULT'):
    return {'$type':'com.linkedin.messenger.Message','entityUrn':f'urn:li:msg_message:(urn:li:fsd_profile:{OWN[0]},{mid})',
            'backendUrn':f'urn:li:messagingMessage:{mid}','body':{'text':text},'deliveredAt':ms(at),
            '*sender':f'urn:li:msg_messagingParticipant:urn:li:fsd_profile:{sender[0]}','messageBodyRenderFormat':render,
            'renderContent':[],'*conversation':f'urn:li:msg_conversation:(urn:li:fsd_profile:{OWN[0]},{thread})'}

def conversations():
    """A 1to1 chat with Ana whose last message is hers, and a group chat."""
    one=f'urn:li:msg_conversation:(urn:li:fsd_profile:{OWN[0]},{THREAD})'
    group=f'urn:li:msg_conversation:(urn:li:fsd_profile:{OWN[0]},{GROUP})'
    last=message_entity(THREAD,'2-bWVuc2FqZTI=','¿Tienes un rato esta semana?',ANA,datetime(2026,11,11,9,30,tzinfo=UTC))
    return {'data':{'data':{'messengerConversationsBySyncToken':{'*elements':[one,group]}}},'included':[
        {'$type':'com.linkedin.messenger.Conversation','entityUrn':one,'lastActivityAt':ms(datetime(2026,11,11,9,30,tzinfo=UTC)),
         'unreadCount':1,'groupChat':False,'*conversationParticipants':[participant(ANA)['entityUrn'],participant(OWN)['entityUrn']],
         'messages':{'*elements':[last['entityUrn']]}},
        {'$type':'com.linkedin.messenger.Conversation','entityUrn':group,'lastActivityAt':ms(datetime(2026,11,9,8,0,tzinfo=UTC)),
         'unreadCount':0,'groupChat':True,'title':'Grupo ficticio',
         '*conversationParticipants':[participant(ANA)['entityUrn'],participant(LUIS)['entityUrn'],participant(OWN)['entityUrn']]},
        participant(ANA),participant(LUIS),participant(OWN),last]}

def chat_messages():
    older=message_entity(THREAD,'2-bWVuc2FqZTE=','Hola, gracias por conectar',OWN,datetime(2026,11,10,10,0,tzinfo=UTC))
    gone=message_entity(THREAD,'2-bWVuc2FqZTA=','',ANA,datetime(2026,11,9,10,0,tzinfo=UTC),render='RECALLED')
    newer=message_entity(THREAD,'2-bWVuc2FqZTI=','¿Tienes un rato esta semana?',ANA,datetime(2026,11,11,9,30,tzinfo=UTC))
    return {'data':{'data':{'messengerMessagesBySyncToken':{'*elements':[older['entityUrn'],gone['entityUrn'],newer['entityUrn']]}}},
            'included':[older,gone,newer,participant(ANA),participant(OWN)]}
