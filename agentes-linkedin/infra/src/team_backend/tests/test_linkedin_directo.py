"""The provider `directo` (docs/plan-linkedin-directo.md, docs/navegador-contrato.md): each of the 21 connector
operations builds the expected LinkedIn request and answers in Unipile's shapes; ids round-trip between operations;
pushback pauses and a write of unknown fate is uncertain; the allowlist refuses before anything leaves; the provider is
wired and stays off without its configuration. Every LinkedIn answer is a hand-written fixture with invented values
(directo_fixtures.py); nothing here reaches a network."""
import inspect
import json
import os
import re
from datetime import datetime, timezone
from unittest.mock import patch
import httpx
from django.test import SimpleTestCase, TestCase
from linkedin_directo import Answer, Cliente, LinkedInError, NoteQuota, Request, Uncertain, cliente, permitidas, rutas
from linkedin_directo.servicio import ServiceTransport
from team_backend import connectors, connectors_directo, conversaciones, metricas, operador, respuestas
from team_backend.connectors import ConnectorError, ConnectorUncertain, InvitationNoteQuota, UnipileConnector, get_connector
from team_backend.connectors_directo import DirectoConnector
from team_backend.models import ConnectorAccount
from team_backend.serializers import AccountInput
from team_backend.tests import directo_fixtures as F
from team_backend.tests.directo_fixtures import ANA, LUIS, OWN, POST, html, ok, stream

UTC=timezone.utc
# Unipile's shapes, from its own normalizers: the direct provider must give the same keys.
USER=set(connectors._user({}))
POST_KEYS=set(connectors._post({'id':'1'}))
COMMENT_KEYS=set(connectors._comment({'id':'1'}))
PROFILE_KEYS=set(connectors._profile({}))
INVITATION_KEYS=set(connectors._invitation({'id':'1'}))
CHAT_KEYS=set(connectors._chat({'id':'1'}))
MESSAGE_KEYS=set(connectors._message({'id':'1'}))
SEARCH_KEYS=USER|{'location','network_distance','signals'}
SENT_AT=datetime(2026,11,9,12,tzinfo=UTC)

def ana_url():return 'https://www.linkedin.com/in/ana-ficticia'

def connector(*routes,live=None):
    t=F.FakeTransport(*routes,live=live)
    return DirectoConnector('cuenta-prueba',transport=t),t

def profiles(request):
    """The profile read of whichever invented person the path names."""
    for person in (OWN,ANA,LUIS):
        if f'memberIdentity={person[1]}&' in request.path or f'memberIdentity={person[0]}&' in request.path:
            return ok(F.full_profile(person))
    return Answer(404,'{}','application/json')

def card(person,**kw):return ('GET',r'^/voyager/api/graphql\?includeWebMetadata=true&variables=\(vanityName:',ok(F.top_card(person,**kw)))
def sdui(sduiid,answer=None):return ('POST','^'+re.escape(rutas.sdui(sduiid))+'$',answer or DONE)
def page(*drawn):return ('GET',r'^/feed/update/urn:li:activity:\d+/$',F.post_page(POST,drawn))
def search(people=(ANA,LUIS)):return ('GET',r'^/search/results/people/\?',F.search_page(people))

DONE=stream('0:{"items":[],"errors":[]}')
ME=('GET',r'^/voyager/api/me$',ok(F.me()))
PROFILES=('GET',r'^/voyager/api/identity/dash/profiles\?',profiles)
INVITE=('POST','^'+re.escape(rutas.voyager(rutas.INVITE))+'$',ok(F.invite_answer(ANA,'7100001')))
RECEIVED=('GET',r'^/voyager/api/relationships/invitationViews\?',ok(F.invitations(
    'received',[('7000001',ANA,SENT_AT,'Hola, conectemos'),('7000002',LUIS,SENT_AT,None)],newsletter=True)))
ACCEPT=('POST',r'^/voyager/api/relationships/invitations/\d+\?action=accept$',ok({'data':{'*value':'urn:li:fs_relInvitation:7000001'}}))
CONVERSATIONS=('GET',r'^/voyager/api/voyagerMessagingGraphQL/graphql\?queryId=messengerConversations\.',ok(F.conversations()))
MESSAGES=('GET',r'^/voyager/api/voyagerMessagingGraphQL/graphql\?queryId=messengerMessages\.',ok(F.chat_messages()))

def top_comments():
    a=F.comment(POST,F.COMMENT_A,'Muy buen punto',ANA,datetime(2026,11,10,16,tzinfo=UTC))
    b=F.comment(POST,F.COMMENT_B,'Gracias por leer',OWN,datetime(2026,11,10,17,tzinfo=UTC))
    company=F.comment(POST,'9000009','Desde la empresa',LUIS,datetime(2026,11,10,17,30,tzinfo=UTC),company=True)
    # LinkedIn tucks a comment's first answer into `included`: it is not a top-level comment.
    tucked=F.comment(POST,F.REPLY,'Respuesta incrustada',LUIS,datetime(2026,11,10,18,tzinfo=UTC),parent=F.COMMENT_A)
    return F.comments(POST,[(a,1),(b,0),(company,0)],embedded=[tucked])

def thread_comments():
    reply=F.comment(POST,F.REPLY,'Respuesta del autor',OWN,datetime(2026,11,10,18,tzinfo=UTC),parent=F.COMMENT_A)
    return F.comments(POST,[(reply,0)])

def comments_route(request):
    return ok(thread_comments() if 'updateId=comment' in request.path else top_comments())

COMMENTS=('GET',r'^/voyager/api/feed/comments\?',comments_route)


class AccountAndProfileTests(SimpleTestCase):
    def test_account_status_is_one_read_of_me(self):
        c,t=connector(ME)
        self.assertEqual(c.account_status(),{'status':'running','is_locked':False})
        [r]=t.sent
        self.assertEqual((r.method,r.path,r.kind,r.body,r.write,r.operation),('GET','/voyager/api/me','voyager',None,False,'account_status'))

    def test_me_without_the_account_profile_is_unreadable(self):
        c,_=connector(('GET',r'^/voyager/api/me$',ok({'data':{},'included':[]})))
        with self.assertRaises(ConnectorError) as e:c.account_status()
        self.assertEqual(e.exception.kind,'unreadable');self.assertFalse(e.exception.pause)

    def test_get_user_by_public_id_profile_id_or_me(self):
        c,t=connector(ME,PROFILES)
        ana=c.get_user('ana-ficticia')
        self.assertEqual(ana,{'id':ANA[0],'public_identifier':'ana-ficticia','display_name':'Ana Ficticia','profile_url':ana_url(),
                              'headline':'Producto e IA aplicada (ficticio)','type':'individual'})
        self.assertEqual(set(ana),USER)
        self.assertEqual(t.paths(),['/voyager/api/identity/dash/profiles?q=memberIdentity&memberIdentity=ana-ficticia'
                                    '&decorationId='+rutas.PROFILE_DECO])
        self.assertEqual(c.get_user(ANA[0])['id'],ANA[0])
        self.assertEqual(c.get_user('me')['id'],OWN[0])
        self.assertEqual(t.paths()[2:],['/voyager/api/me','/voyager/api/identity/dash/profiles?q=memberIdentity'
                                        '&memberIdentity=cuenta-de-prueba&decorationId='+rutas.PROFILE_DECO])

    def test_an_invalid_or_unknown_person_sends_nothing_or_is_not_found(self):
        c,t=connector(PROFILES)
        with self.assertRaises(ConnectorError) as e:c.get_user('un nombre con espacios')
        self.assertEqual(e.exception.kind,'invalid');self.assertEqual(t.sent,[])
        with self.assertRaises(ConnectorError) as e:c.get_profile('persona-inexistente')
        self.assertEqual((e.exception.kind,e.exception.pause),('not_found',False))

    def test_get_profile_adds_distance_follow_state_and_reach_from_the_top_card(self):
        c,t=connector(PROFILES,card(ANA,following=True))
        p=c.get_profile(ANA[0])
        self.assertEqual(set(p),PROFILE_KEYS)
        self.assertEqual(p,{'id':ANA[0],'public_identifier':'ana-ficticia','display_name':'Ana Ficticia','profile_url':ana_url(),
                            'headline':'Producto e IA aplicada (ficticio)','type':'individual','location':'Ciudad Ficticia, País de Prueba',
                            'network_distance':'SECOND_DEGREE','is_following':True,'relation_request_status':'','invitation_id':'',
                            'is_restricted':False,'signals':{'followers':120,'connections':80,'bio':'Texto de prueba sobre producto.'}})
        self.assertEqual(t.paths()[1],'/voyager/api/graphql?includeWebMetadata=true&variables=(vanityName:ana-ficticia)'
                                      f'&queryId={rutas.TOP_CARD}')
        self.assertTrue(all(not r.write for r in t.sent))

    def test_get_profile_reads_a_pending_invitation_and_the_first_degree(self):
        pending={'noConnection':{'memberDistance':'DISTANCE_3','invitation':{'*invitation':'urn:li:fsd_invitation:7000009'}}}
        c,_=connector(PROFILES,card(ANA,relationship=pending))
        p=c.get_profile('ana-ficticia')
        self.assertEqual((p['network_distance'],p['relation_request_status'],p['invitation_id']),('THIRD_DEGREE','PENDING','7000009'))
        self.assertFalse(p['is_following'])  # the hashtag the card lists first is followed; Ana is not
        c,_=connector(PROFILES,card(ANA,relationship={'*connection':'urn:li:fsd_connection:1'}))
        self.assertEqual(c.get_profile(ANA[0])['network_distance'],'FIRST_DEGREE')

    def test_the_own_profile_skips_the_top_card(self):
        c,t=connector(ME,PROFILES)
        p=c.get_profile('me')
        self.assertEqual((p['id'],p['network_distance']),(OWN[0],'SELF'))
        self.assertEqual(len(t.sent),2)

    def test_own_audience_and_profile_views(self):
        c,t=connector(ME,card(OWN,own=True,followers=321,connections=210),
                      ('GET',r'^/voyager/api/identity/wvmpCards$',ok(F.profile_views(37))))
        audience=c.own_audience()
        self.assertEqual(audience,{'followers':321,'connections':210});self.assertEqual(set(audience),set(connectors._audience({})))
        self.assertIn('variables=(vanityName:cuenta-de-prueba)',t.paths()[1])
        self.assertIsNone(c.profile_views(14))  # another window than LinkedIn's own: absent, without calling
        self.assertEqual(len(t.sent),2)
        self.assertEqual(c.profile_views(rutas.VIEWS_DAYS),37)
        self.assertEqual(t.paths()[-1],'/voyager/api/identity/wvmpCards')


class PostAndCommentTests(SimpleTestCase):
    def test_list_user_posts(self):
        rows=[(POST,'Primer post',ANA,{'likes':5,'comments':2,'shares':1,'liked':True,'impressions':300}),
              (F.OTHER_POST,'Post de otra persona',LUIS,{'likes':1}),
              (F.snowflake(F.POSTED,7),'Tercero',ANA,{})]
        c,t=connector(('GET',r'^/voyager/api/identity/profileUpdatesV2\?',ok(F.posts(*rows))))
        found=c.list_user_posts(ANA[0],limit=2)
        self.assertEqual(t.paths(),['/voyager/api/identity/profileUpdatesV2?q=memberShareFeed&profileUrn=urn%3Ali%3Afsd_profile%3A'
                                    f'{ANA[0]}&moduleKey=member-shares%3Aphone&count=2&start=0&includeLongTermHistory=true'])
        self.assertEqual(len(found),2)
        first=found[0]
        self.assertEqual(set(first),POST_KEYS)
        self.assertEqual((first['id'],first['created_at'],first['share_url']),
                         (POST,F.POSTED,f'https://www.linkedin.com/feed/update/urn:li:activity:{POST}/'))
        self.assertEqual((first['text'],first['reactions_counter'],first['comments_counter'],first['reposts_counter'],
                          first['user_reacted'],first['impressions'],first['is_repost']),('Primer post',5,2,1,True,300,False))
        self.assertEqual(first['author'],{'id':ANA[0],'public_identifier':'ana-ficticia','display_name':'Ana Ficticia',
                                          'profile_url':ana_url(),'headline':'Titular ficticio','type':'individual'})
        self.assertTrue(found[1]['is_repost'])  # someone else's update in Ana's activity
        self.assertIsNone(found[1]['impressions'])

    def test_list_user_posts_of_a_public_id_reads_the_profile_first(self):
        c,t=connector(PROFILES,('GET',r'profileUpdatesV2',ok(F.posts((POST,'Uno',ANA,{})))))
        self.assertEqual([p['id'] for p in c.list_user_posts('ana-ficticia')],[POST])
        self.assertIn('memberIdentity=ana-ficticia',t.paths()[0]);self.assertIn(f'fsd_profile%3A{ANA[0]}',t.paths()[1])

    def test_get_post_reads_only_the_asked_update(self):
        c,t=connector(('GET',r'^/voyager/api/feed/updates\?q=highlightedFeed',ok(F.highlighted(POST,liked=True))))
        p=c.get_post(POST)
        self.assertEqual(t.paths(),[f'/voyager/api/feed/updates?q=highlightedFeed&highlightedUpdateUrns=List(urn%3Ali%3Aactivity%3A{POST})'])
        self.assertEqual(set(p),POST_KEYS)
        self.assertEqual((p['id'],p['reactions_counter'],p['comments_counter'],p['reposts_counter'],p['user_reacted'],p['impressions'],
                          p['author']['id']),(POST,4,2,1,True,None,OWN[0]))
        self.assertEqual(c.get_post(f'urn:li:activity:{POST}')['id'],POST)

    def test_get_post_refuses_another_post_and_a_bad_id(self):
        c,t=connector(('GET',r'highlightedFeed',ok(F.highlighted(F.OTHER_POST))))
        with self.assertRaises(ConnectorError) as e:c.get_post(POST)
        self.assertEqual(e.exception.kind,'not_found')
        with self.assertRaises(ConnectorError) as e:c.get_post('no-es-un-id')
        self.assertEqual(e.exception.kind,'invalid');self.assertEqual(len(t.sent),1)

    def test_list_comments_top_level_only(self):
        c,t=connector(ME,COMMENTS)
        found=c.list_comments(POST)
        self.assertEqual(t.paths()[1],f'/voyager/api/feed/comments?q=comments&updateId=activity%3A{POST}&count=50&start=0&sortOrder=RELEVANCE')
        self.assertEqual([x['id'] for x in found],[F.COMMENT_A,F.COMMENT_B,'9000009'])
        self.assertEqual(set(found[0]),COMMENT_KEYS)
        self.assertEqual(found[0],{'id':F.COMMENT_A,'text':'Muy buen punto','created_at':datetime(2026,11,10,16,tzinfo=UTC),
                                   'is_sender':False,'thread_id':None,'reply_counter':1,
                                   # Like Unipile's comment author: no headline (the callers read the profile).
                                   'author':{'id':ANA[0],'public_identifier':'ana-ficticia','display_name':'Ana Ficticia',
                                             'profile_url':ana_url(),'headline':'','type':'individual'}})
        self.assertTrue(found[1]['is_sender'])
        self.assertEqual((found[2]['author']['type'],found[2]['author']['id'],found[2]['author']['display_name']),('company','','Empresa Ficticia'))
        self.assertEqual(len(c.list_comments(POST,limit=1)),1)

    def test_list_comment_thread(self):
        c,t=connector(ME,COMMENTS)
        found=c.list_comment_thread(POST,F.COMMENT_A,limit=5)
        self.assertEqual(t.paths()[1],f'/voyager/api/feed/comments?q=comments&updateId=comment%3A%28activity%3A{POST}%2C{F.COMMENT_A}%29'
                                      '&count=5&start=0&sortOrder=CHRONOLOGICAL')
        self.assertEqual([(x['id'],x['thread_id'],x['is_sender'],x['text']) for x in found],[(F.REPLY,F.COMMENT_A,True,'Respuesta del autor')])
        with self.assertRaises(ConnectorError) as e:c.list_comment_thread(POST,'abc')
        self.assertEqual(e.exception.kind,'invalid');self.assertEqual(len(t.sent),2)

    def test_create_comment_fills_the_page_box_and_makes_one_write(self):
        new=F.snowflake(datetime(2026,11,10,19,tzinfo=UTC),6)
        c,t=connector(page(),sdui(rutas.COMMENT,F.comment_written(POST,new,'Un aporte de prueba')))
        out=c.create_comment(POST,'Un aporte de prueba')
        read,write=t.sent
        self.assertEqual((read.method,read.path,read.kind,read.write),('GET',f'/feed/update/urn:li:activity:{POST}/','page',False))
        self.assertEqual((write.method,write.path,write.kind,write.write,write.operation),
                         ('POST',rutas.sdui(rutas.COMMENT),'sdui',True,'create_comment'))
        body=write.body;args=body['requestedArguments']
        self.assertEqual((body['requestId'],body['serverRequest']['requestId'],args['screenId']),(rutas.COMMENT,rutas.COMMENT,rutas.POST_SCREEN))
        self.assertNotIn('parentCommentUrn',args['payload']['collection']);self.assertTrue(args['payload']['_ExecutionId'])
        values={s['key']:s['value'] for s in body['states']}
        self.assertEqual(len(values),len(rutas.COMMENT_BOX));self.assertEqual(body['states'],args['states'])
        self.assertEqual(values['commentFieldBinding-ficticio0'],'Un aporte de prueba')
        self.assertEqual(values['richCommentFieldBinding-ficticio0']['text'],'Un aporte de prueba')
        self.assertEqual(set(out),COMMENT_KEYS)
        # The answer draws the comment list again with the new comment in it: its id, and its time is in the id.
        self.assertEqual((out['id'],out['text'],out['is_sender'],out['thread_id'],out['created_at']),
                         (new,'Un aporte de prueba',True,None,datetime(2026,11,10,19,tzinfo=UTC)))
        self.assertFalse(rutas.has_mention(body))

    def test_without_the_new_id_in_the_answer_the_callers_find_it_by_reading(self):
        two=stream(F.comment_written(POST,F.COMMENT_A,'x').text+'\n'+F.comment_written(POST,F.COMMENT_B,'y').text)
        for answer in (DONE,two):
            with self.subTest(answer=answer.text[:30]):
                c,t=connector(page(),sdui(rutas.COMMENT,answer))
                self.assertEqual((c.create_comment(POST,'Hola')['id'],len(t.sent)),('',2))

    def test_comment_in_thread_uses_that_comment_template(self):
        c,t=connector(page(F.COMMENT_B,F.COMMENT_A),sdui(rutas.COMMENT,F.comment_written(POST,F.REPLY,'Gracias por el aporte',F.COMMENT_A)))
        out=c.comment_in_thread(POST,F.COMMENT_A,'Gracias por el aporte')
        body=t.sent[1].body
        self.assertEqual(body['requestedArguments']['payload']['collection']['parentCommentUrn']['commentId'],F.COMMENT_A)
        self.assertEqual({s['key']:s['value'] for s in body['states']}['commentFieldBinding-ficticio2'],'Gracias por el aporte')
        # The parent is in the answer too: the new id is the other one. No mention of the parent's author is sent.
        self.assertEqual((out['id'],out['thread_id']),(F.REPLY,F.COMMENT_A))
        rich=[s['value'] for s in body['states'] if s['originalProtoCase']=='textModelForWrite']
        self.assertEqual(rich,[{'$type':rutas.TEXT_MODEL,'text':'Gracias por el aporte','attribute':[],'webDataAttributes':[]}])
        self.assertFalse(rutas.has_mention(body))

    def test_a_reply_to_a_comment_the_page_does_not_draw_reuses_another_reply_box(self):
        c,t=connector(page(F.COMMENT_B),sdui(rutas.COMMENT,F.comment_written(POST,F.REPLY,'Hola',F.COMMENT_A)))
        out=c.comment_in_thread(POST,F.COMMENT_A,'Hola')
        args=t.sent[1].body['requestedArguments'];collection=args['payload']['collection']
        thread=f'urn:li:activity:{POST}'
        self.assertEqual((collection['parentCommentUrn'],collection['threadUrn'],collection['parentThreadUrn']),
                         ({'commentId':F.COMMENT_A,'thread':thread},{'threadUrnCommentThreadUrn':{'commentUrn':{'commentId':F.COMMENT_A,'thread':thread}}},
                          {'threadUrnActivityThreadUrn':{'activityUrn':{'activityId':POST}}}))
        # B's binding keys, consistent between the payload, the asked state keys and the states sent.
        keys={args['payload'][field]['key'] for field,_,_ in rutas.COMMENT_BOX}
        self.assertEqual(keys,{s['key'] for s in args['states']})
        self.assertEqual(keys,{k['key']['value']['id'] for k in args['requestedStateKeys']})
        self.assertIn('commentFieldBinding-ficticio1',keys)
        self.assertIn('currentActor',args['requestMetadata'])
        self.assertEqual((out['id'],out['thread_id']),(F.REPLY,F.COMMENT_A))
        # Only the box on the page: the box becomes the reply.
        c,t=connector(page(),sdui(rutas.COMMENT))
        c.comment_in_thread(POST,F.COMMENT_A,'Hola')
        collection=t.sent[1].body['requestedArguments']['payload']['collection']
        self.assertEqual((collection['parentCommentUrn']['commentId'],set(collection)),
                         (F.COMMENT_A,{'updateKey','threadUrn','parentThreadUrn','parentCommentUrn'}))
        self.assertEqual(collection['threadUrn']['threadUrnCommentThreadUrn']['commentUrn']['commentId'],F.COMMENT_A)

    def test_without_the_right_template_nothing_is_written(self):
        c,t=connector(('GET',r'^/feed/update/',html('<html><head><title>Post</title></head><body></body></html>')))
        with self.assertRaises(ConnectorError) as e:c.create_comment(POST,'Hola')
        self.assertEqual(e.exception.kind,'template_missing');self.assertEqual(len(t.sent),1)
        with self.assertRaises(ConnectorError) as e:c.comment_in_thread(POST,F.COMMENT_A,'Hola')
        self.assertEqual(e.exception.kind,'template_missing');self.assertEqual(len(t.sent),2)
        with self.assertRaises(ConnectorError) as e:c.create_comment(POST,'   ')
        self.assertEqual(e.exception.kind,'invalid');self.assertEqual(len(t.sent),2)

    def test_a_write_linkedin_answers_with_errors_is_rejected(self):
        c,_=connector(page(),sdui(rutas.COMMENT,stream('0:{"errors":[{"message":"no"}]}')))
        with self.assertRaises(ConnectorError) as e:c.create_comment(POST,'Hola')
        self.assertEqual((e.exception.kind,e.exception.pause),('rejected',False))

    def test_reactions(self):
        self.assertEqual(set(rutas.REACTIONS),set(connectors.REACTIONS))
        c,t=connector(sdui(rutas.REACT))
        self.assertEqual(c.add_reaction(POST,'linkedin_celebrate'),{'reaction':'linkedin_celebrate'})
        self.assertEqual(c.react_to_comment(POST,F.COMMENT_A,'linkedin_like'),{'reaction':'linkedin_like'})
        on_post,on_comment=[r.body['requestedArguments']['payload'] for r in t.sent]
        self.assertEqual(on_post,{'threadUrn':{'threadUrnActivityThreadUrn':{'activityUrn':{'activityId':POST}}},
                                  'reactionType':'ReactionType_PRAISE','reactionSource':'Update'})
        self.assertEqual(on_comment,{'threadUrn':{'threadUrnCommentThreadUrn':{'commentUrn':{'commentId':F.COMMENT_A,'thread':f'urn:li:activity:{POST}'}}},
                                     'reactionType':'ReactionType_LIKE','reactionSource':'Comment'})
        self.assertTrue(all(r.write and r.path==rutas.sdui(rutas.REACT) and 'serverRequest' not in r.body for r in t.sent))
        with self.assertRaises(ConnectorError) as e:c.add_reaction(POST,'like')
        self.assertEqual(e.exception.kind,'invalid');self.assertEqual(len(t.sent),2)


class NetworkTests(SimpleTestCase):
    def test_search_people_is_one_page_read_with_what_the_page_carries(self):
        c,t=connector(search())
        found=c.search_people('fundadores ia',location=['900001'],profile_language=['es'])
        self.assertEqual(t.paths(),['/search/results/people/?keywords=fundadores%20ia&origin=GLOBAL_SEARCH_HEADER'
                                    '&geoUrn=%5B%22900001%22%5D&profileLanguage=%5B%22es%22%5D'])
        self.assertEqual(t.sent[0].kind,'page')
        self.assertEqual([p['id'] for p in found],[ANA[0],LUIS[0]])
        self.assertEqual(set(found[0]),SEARCH_KEYS)
        # The member ids of all (kept for follow), the public id of the first ones (a profile prefetch).
        self.assertEqual((c.client.members[ANA[0]],c.client.members[LUIS[0]]),(ANA[2],LUIS[2]))
        self.assertEqual([(p['public_identifier'],p['profile_url']) for p in found],[('ana-ficticia',ana_url()),('','')])
        # Lazy: name, headline, distance and place are not on the page; the caller's capped profile read fills them.
        self.assertEqual((found[0]['display_name'],found[0]['headline'],found[0]['network_distance'],found[0]['location'],
                          found[0]['signals'],found[0]['type']),('','','','',{},'individual'))
        with self.assertRaises(ConnectorError) as e:c.search_people('  ')
        self.assertEqual(e.exception.kind,'invalid');self.assertEqual(len(t.sent),1)

    def test_search_results_take_both_forms_of_the_member_ids(self):
        from linkedin_directo import lectura
        page=F.search_page((ANA,LUIS),public=2).text
        self.assertEqual(lectura.search_results(page),[{'id':ANA[0],'member':ANA[2],'public_identifier':'ana-ficticia'},
                                                       {'id':LUIS[0],'member':LUIS[2],'public_identifier':'luis-ficticio'}])
        snippet={'requestId':rutas.SNIPPETS,'requestedArguments':{'payload':{
            'memberProfileIds':[f'urn:li:fsd_profile:{ANA[0]}'],'memberEntityUrns':[f'urn:li:member:{ANA[2]}']}}}
        older=json.dumps([snippet],separators=(',',':')).replace('"','\\"')
        self.assertEqual(lectura.search_results(older),[{'id':ANA[0],'member':ANA[2],'public_identifier':''}])

    def test_search_parameters_reads_the_location_typeahead(self):
        c,t=connector(search(),('POST','^'+re.escape(rutas.sdui(rutas.FILTER_BAR,'component'))+'$',F.filter_bar()),
                      sdui(rutas.GEO_TYPEAHEAD,F.typeahead([('900001','Ciudad Ficticia'),('900002','Otra Ciudad')])))
        self.assertEqual(c.search_parameters('LOCATION','Ciud',limit=1),[{'id':'900001','name':'Ciudad Ficticia'}])
        first,bar,query=t.sent
        self.assertEqual(first.path,'/search/results/people/?keywords=a&origin=GLOBAL_SEARCH_HEADER')
        self.assertEqual((bar.kind,bar.write,bar.body['componentId'],bar.body['clientArguments']['payload']),
                         ('sdui',False,rutas.FILTER_BAR,{'consulta':'ficticia'}))
        self.assertFalse(query.write)
        self.assertEqual([(s['key'],s['value']) for s in query.body['states']],[('ubicacion-ficticia','Ciud')])
        self.assertEqual(query.body['requestedArguments']['screenId'],rutas.SEARCH_SCREEN)
        self.assertEqual(len(c.search_parameters('LOCATION','Otra')),2)
        self.assertEqual(len(t.sent),4)  # the typeahead template is kept: one call more
        with self.assertRaises(ConnectorError) as e:c.search_parameters('COMPANY','x')
        self.assertEqual(e.exception.kind,'invalid')

    def test_follow_reads_the_profile_only_without_the_member_id(self):
        c,t=connector(PROFILES,sdui(rutas.FOLLOW))
        self.assertEqual(c.follow_user(ANA[0]),{'user_id':ANA[0]})
        read,write=t.sent
        self.assertIn(f'memberIdentity={ANA[0]}&',read.path)
        self.assertEqual(write.body['requestedArguments']['payload'],{'followStateType':'FollowStateType_FOLLOW_ACTIVE','memberUrn':{'memberId':ANA[2]}})
        self.assertEqual((write.write,write.operation),(True,'follow_user'))
        c.follow_user(ANA[0])
        self.assertEqual(len(t.sent),3)

    def test_send_invitation(self):
        c,t=connector(INVITE)
        out=c.send_invitation(ANA[0],note='Hola, me interesa tu trabajo')
        [r]=t.sent
        self.assertEqual((r.method,r.kind,r.write,r.operation),('POST','voyager',True,'send_invitation'))
        self.assertEqual(r.body,{'invitee':{'inviteeUnion':{'memberProfile':f'urn:li:fsd_profile:{ANA[0]}'}},'customMessage':'Hola, me interesa tu trabajo'})
        self.assertEqual(set(out),INVITATION_KEYS)
        self.assertEqual((out['id'],out['type'],out['created_at'],out['message'],out['user']['id']),('7100001','sent',None,'Hola, me interesa tu trabajo',ANA[0]))
        self.assertEqual(c.send_invitation(ANA[0])['message'],'')
        self.assertEqual(t.sent[1].body,{'invitee':{'inviteeUnion':{'memberProfile':f'urn:li:fsd_profile:{ANA[0]}'}}})
        with self.assertRaises(ConnectorError) as e:c.send_invitation(ANA[0],note='x'*(rutas.NOTE_LIMIT+1))
        self.assertEqual(e.exception.kind,'invalid');self.assertEqual(len(t.sent),2)

    def test_a_refused_invitation_is_a_note_quota_only_with_proof(self):
        refused=('POST',re.escape(rutas.INVITE),Answer(400,json.dumps({'code':'CUOTA_FICTICIA','status':400}),'application/json'))
        c,_=connector(refused)
        with self.assertRaises(ConnectorError) as e:c.send_invitation(ANA[0],note='Hola')
        self.assertNotIsInstance(e.exception,InvitationNoteQuota)
        self.assertEqual((e.exception.kind,e.exception.status,e.exception.pause),('linkedin/cuota_ficticia',400,False))
        with patch.object(cliente,'NOTE_QUOTA_CODES',frozenset({'cuota_ficticia'})):
            with self.assertRaises(InvitationNoteQuota) as e:c.send_invitation(ANA[0],note='Hola')
            self.assertEqual((e.exception.kind,e.exception.status),('note_quota',400))
            with self.assertRaises(ConnectorError) as e:c.send_invitation(ANA[0])  # without a note it cannot be the note
            self.assertNotIsInstance(e.exception,InvitationNoteQuota)

    def test_list_invitations(self):
        c,t=connector(RECEIVED,('GET',r'^/voyager/api/relationships/sentInvitationViewsV2\?',
                                ok(F.invitations('sent',[('7000003',LUIS,SENT_AT,'Nota enviada')]))))
        got=c.list_invitations('received',limit=10)
        self.assertEqual(t.paths(),['/voyager/api/relationships/invitationViews?q=receivedInvitation&start=0&count=10&includeInsights=true'])
        # The newsletter invitation in the same list is left out.
        self.assertEqual([(i['id'],i['type'],i['message'],i['user']['id']) for i in got],
                         [('7000001','received','Hola, conectemos',ANA[0]),('7000002','received','',LUIS[0])])
        self.assertEqual(set(got[0]),INVITATION_KEYS)
        self.assertEqual((got[0]['created_at'],got[0]['user']['public_identifier'],got[0]['user']['profile_url']),(SENT_AT,'ana-ficticia',ana_url()))
        sent=c.list_invitations('sent')
        self.assertEqual(t.paths()[1],'/voyager/api/relationships/sentInvitationViewsV2?q=invitationType&invitationType=CONNECTION&start=0&count=100')
        self.assertEqual([(i['id'],i['type'],i['message'],i['user']['id']) for i in sent],[('7000003','sent','Nota enviada',LUIS[0])])
        with self.assertRaises(ConnectorError) as e:c.list_invitations('otra')
        self.assertEqual(e.exception.kind,'invalid')

    def test_accept_uses_the_secret_of_the_received_list(self):
        c,t=connector(RECEIVED,ACCEPT)
        self.assertEqual(c.accept_invitation('7000001'),{'request_id':'7000001'})
        read,write=t.sent  # no secret yet: the received list is read first
        self.assertEqual(read.method,'GET')
        self.assertEqual((write.path,write.write,write.operation),('/voyager/api/relationships/invitations/7000001?action=accept',True,'accept_invitation'))
        self.assertEqual(write.body,{'invitationId':'7000001','invitationSharedSecret':'secreto-ficticio','isGenericInvitation':False})
        c.accept_invitation('7000002')
        self.assertEqual(len(t.sent),3)
        for gone in ('7999999','8888'):  # unknown, or the newsletter one
            with self.assertRaises(ConnectorError) as e:c.accept_invitation(gone)
            self.assertEqual(e.exception.kind,'invitation_gone')
        self.assertEqual([r.method for r in t.sent[3:]],['GET','GET'])
        with self.assertRaises(ConnectorError) as e:c.accept_invitation('abc')
        self.assertEqual(e.exception.kind,'invalid')


class InboxTests(SimpleTestCase):
    def test_list_chats(self):
        c,t=connector(ME,CONVERSATIONS)
        one,group=c.list_chats()
        self.assertEqual(t.paths()[1],f'/voyager/api/voyagerMessagingGraphQL/graphql?queryId={rutas.CONVERSATIONS}'
                                      f'&variables=(mailboxUrn:urn%3Ali%3Afsd_profile%3A{OWN[0]})')
        self.assertEqual(set(one),CHAT_KEYS)
        self.assertEqual(one,{'id':F.THREAD,'name':'Ana Ficticia','type':'1to1','user_id':ANA[0],'unread_count':1,'is_readonly':False,
                              'last_message_at':datetime(2026,11,11,9,30,tzinfo=UTC),
                              'last_message':{'id':'2-bWVuc2FqZTI=','text':'¿Tienes un rato esta semana?','is_sender':False}})
        self.assertEqual((group['id'],group['type'],group['name'],group['user_id'],group['last_message']),(F.GROUP,'group','Grupo ficticio','',None))
        self.assertEqual(c.list_chats(limit=1),[one])
        self.assertEqual(c.list_chats(inbox='COMPANY_1_PRIMARY'),[])  # company inboxes are not read here
        self.assertEqual(len(t.sent),3)

    def test_a_live_query_id_wins_over_the_fixed_one(self):
        fresh='messengerConversations.'+'0123456789abcdef'*2
        live={'messengerConversations':{'path':'/voyager/api/voyagerMessagingGraphQL/graphql','query_id':fresh,'variables':['mailboxUrn'],'source':'page'}}
        c,t=connector(ME,CONVERSATIONS,live=live)
        c.list_chats()
        self.assertTrue(t.paths()[1].startswith(f'/voyager/api/voyagerMessagingGraphQL/graphql?queryId={fresh}&variables=(mailboxUrn:'))
        self.assertEqual(t.live_asked,[(rutas.CONVERSATION_QUERIES,('mailboxUrn',))])
        odd={'messengerConversations':{'path':'/otro host/','query_id':'raro);x','variables':['mailboxUrn']}}
        c,t=connector(ME,CONVERSATIONS,live=odd)
        c.list_chats()
        self.assertIn(f'queryId={rutas.CONVERSATIONS}&',t.paths()[1])

    def test_list_chat_messages(self):
        c,t=connector(ME,MESSAGES)
        found=c.list_chat_messages(F.THREAD,limit=2)
        self.assertEqual(t.paths()[1],f'/voyager/api/voyagerMessagingGraphQL/graphql?queryId={rutas.MESSAGES}&variables=(conversationUrn:'
                                      f'urn%3Ali%3Amsg_conversation%3A%28urn%3Ali%3Afsd_profile%3A{OWN[0]}%2C2-ZmFrZVRocmVhZDE%3D%29)')
        self.assertEqual([(m['id'],m['is_sender'],m['sender_id']) for m in found],[('2-bWVuc2FqZTI=',False,ANA[0]),('2-bWVuc2FqZTE=',True,OWN[0])])
        self.assertEqual(set(found[0]),MESSAGE_KEYS)
        self.assertEqual((found[0]['at'],found[0]['text'],found[0]['sender']['display_name'],found[0]['hidden'],found[0]['attachments']),
                         (datetime(2026,11,11,9,30,tzinfo=UTC),'¿Tienes un rato esta semana?','Ana Ficticia',False,0))
        self.assertTrue(c.list_chat_messages(F.THREAD)[-1]['hidden'])  # a recalled message
        with self.assertRaises(ConnectorError) as e:c.list_chat_messages('../otra')
        self.assertEqual(e.exception.kind,'invalid');self.assertEqual(len(t.sent),3)


class IdRoundTripTests(SimpleTestCase):
    """An id one operation returns is what the next one takes, as with Unipile."""

    def test_a_post_id_reads_and_reacts(self):
        c,t=connector(('GET',r'profileUpdatesV2',ok(F.posts((POST,'Uno',OWN,{'impressions':50})))),
                      ('GET',r'highlightedFeed',ok(F.highlighted(POST))),sdui(rutas.REACT))
        pid=c.list_user_posts(OWN[0])[0]['id']
        self.assertEqual(c.get_post(pid)['id'],pid)
        c.add_reaction(pid,'linkedin_like')
        self.assertEqual(t.sent[2].body['requestedArguments']['payload']['threadUrn']['threadUrnActivityThreadUrn']['activityUrn']['activityId'],pid)

    def test_a_comment_id_opens_its_thread_reacts_and_answers_in_it(self):
        c,t=connector(ME,COMMENTS,sdui(rutas.REACT),page(F.COMMENT_A),sdui(rutas.COMMENT))
        cid=c.list_comments(POST)[0]['id']
        self.assertEqual([x['thread_id'] for x in c.list_comment_thread(POST,cid)],[cid])
        c.react_to_comment(POST,cid,'linkedin_like')
        c.comment_in_thread(POST,cid,'Gracias')
        react,write=t.sent[3],t.sent[5]
        self.assertEqual(react.body['requestedArguments']['payload']['threadUrn']['threadUrnCommentThreadUrn']['commentUrn']['commentId'],cid)
        self.assertEqual(write.body['requestedArguments']['payload']['collection']['parentCommentUrn']['commentId'],cid)

    def test_a_person_found_by_search_or_a_comment_is_followed_and_invited_without_another_read(self):
        c,t=connector(ME,search(),COMMENTS,sdui(rutas.FOLLOW),INVITE)
        luis=c.search_people('fundadores')[1]['id']
        c.follow_user(luis);c.send_invitation(luis,'Hola')
        self.assertEqual(t.sent[1].body['requestedArguments']['payload']['memberUrn'],{'memberId':LUIS[2]})
        self.assertEqual(t.sent[2].body['invitee']['inviteeUnion']['memberProfile'],f'urn:li:fsd_profile:{LUIS[0]}')
        ana=c.list_comments(POST)[0]['author']['id']
        c.follow_user(ana)
        self.assertEqual(t.sent[-1].body['requestedArguments']['payload']['memberUrn'],{'memberId':ANA[2]})
        self.assertFalse(any('identity/dash/profiles' in p for p in t.paths()))

    def test_a_profile_keeps_the_id_it_was_asked_for(self):
        # comunidad.read_public only trusts a profile whose id is the person's provider id.
        c,t=connector(PROFILES,card(ANA),sdui(rutas.FOLLOW))
        self.assertEqual(c.get_profile(ANA[0])['id'],ANA[0])
        self.assertEqual(c.get_profile('ana-ficticia')['id'],ANA[0])
        c.follow_user(ANA[0])
        self.assertEqual(t.sent[-1].body['requestedArguments']['payload']['memberUrn'],{'memberId':ANA[2]})
        self.assertEqual(len(t.sent),5)

    def test_an_invitation_and_a_chat_id_go_back_in(self):
        c,t=connector(ME,RECEIVED,ACCEPT,CONVERSATIONS,MESSAGES)
        iid=c.list_invitations('received')[0]['id']
        c.accept_invitation(iid)
        self.assertEqual(t.sent[-1].body['invitationId'],iid)
        chat=c.list_chats()[0]['id']
        self.assertEqual(len(c.list_chat_messages(chat)),3)
        self.assertIn('%2C'+chat.replace('=','%3D')+'%29',t.paths()[-1])


class ErrorMappingTests(SimpleTestCase):
    def read_error(self,answer):
        c,_=connector(('GET',r'^/voyager/api/me$',answer))
        with self.assertRaises(ConnectorError) as e:c.account_status()
        return e.exception

    def test_pushback_and_lost_sessions_pause_the_account(self):
        cases=((Answer(429,'{}','application/json'),'pushback'),(Answer(999,''),'pushback'),(Answer(401,''),'pushback'),
               (Answer(403,'{}','application/json'),'pushback'),(Answer(200,json.dumps({'status':429}),'application/json'),'pushback'),
               (Answer(302,''),'redirect'),(Answer(200,'{}','application/json',redirected=True),'redirect'),
               (Answer(200,'{}','application/json','https://www.linkedin.com/checkpoint/challenge/x'),'login'),
               (Answer(200,'<html><title>Iniciar sesión</title></html>','text/html'),'challenge'))
        for answer,kind in cases:
            with self.subTest(status=answer.status,kind=kind):
                e=self.read_error(answer)
                self.assertTrue(e.pause);self.assertEqual(e.kind,kind)

    def test_a_challenge_page_pauses_before_any_write(self):
        c,t=connector(('GET',r'^/feed/update/',html('<html><head><title>Security Verification</title></head></html>')),sdui(rutas.COMMENT))
        with self.assertRaises(ConnectorError) as e:c.create_comment(POST,'Hola')
        self.assertEqual((e.exception.kind,e.exception.pause),('challenge',True));self.assertEqual(len(t.sent),1)
        c,_=connector(sdui(rutas.REACT,Answer(429,'')))
        with self.assertRaises(ConnectorError) as e:c.add_reaction(POST,'linkedin_like')
        self.assertTrue(e.exception.pause)

    def test_other_failures_are_plain_errors(self):
        cases=((Answer(404,'{}','application/json'),'not_found',404),
               (Answer(400,json.dumps({'code':'BAD_PARAM'}),'application/json'),'linkedin/bad_param',400),
               (Answer(422,json.dumps({'data':{'code':'OTRO_CODIGO'}}),'application/json'),'linkedin/otro_codigo',422),
               (Answer(500,''),'http_error',500),(Answer(0,''),'network',None),(Answer(200,'[]','application/json'),'unreadable',200),
               (Answer(200,json.dumps({'errors':[{'message':'x'}],'data':{}}),'application/json'),'graphql',200))
        for answer,kind,status in cases:
            with self.subTest(kind=kind):
                e=self.read_error(answer)
                self.assertEqual((e.kind,e.status,e.pause),(kind,status,False))

    def test_an_answer_of_another_shape_is_an_error_not_a_crash(self):
        odd={'data':{'*elements':['u1']},'included':[{'entityUrn':'u1','updateMetadata':'raro'}]}
        c,_=connector(('GET',r'profileUpdatesV2',ok(odd)))
        with self.assertRaises(ConnectorError) as e:c.list_user_posts(ANA[0])
        self.assertEqual(e.exception.kind,'unreadable')

    def test_a_write_without_a_clear_answer_is_uncertain(self):
        for answer in (Answer(0,''),Answer(502,''),Answer(500,'')):
            with self.subTest(status=answer.status):
                c,_=connector(sdui(rutas.REACT,answer))
                with self.assertRaises(ConnectorUncertain):c.add_reaction(POST,'linkedin_like')
        c,_=connector(('POST',re.escape(rutas.INVITE),Answer(200,'listo','text/plain')))
        with self.assertRaises(ConnectorUncertain):c.send_invitation(ANA[0])
        c,_=connector(RECEIVED,('POST',r'action=accept',Answer(504,'')))
        with self.assertRaises(ConnectorUncertain):c.accept_invitation('7000001')
        c,_=connector(sdui(rutas.REACT,Answer(400,'{}','application/json')))
        with self.assertRaises(ConnectorError) as e:c.add_reaction(POST,'linkedin_like')
        self.assertEqual((e.exception.kind,e.exception.pause),('http_error',False))

    def test_the_package_errors_become_the_connector_ones(self):
        c,_=connector()
        cases=((LinkedInError('x',kind='pushback',status=429,pause=True),ConnectorError,('pushback',429,True)),
               (NoteQuota('y',400),InvitationNoteQuota,('note_quota',400,False)),(Uncertain('z'),ConnectorUncertain,None))
        for raised,expected,fields in cases:
            with self.subTest(expected=expected.__name__),patch.object(c.client,'send_invitation',side_effect=raised):
                with self.assertRaises(expected) as e:c.send_invitation(ANA[0],'Hola')
                if fields:self.assertEqual((e.exception.kind,e.exception.status,e.exception.pause),fields)


class AllowlistTests(SimpleTestCase):
    def comment_body(self,text,mention=False):
        template=rutas.templates(rutas.unescape(F.post_page(POST).text),rutas.COMMENT)[0]
        states=rutas.comment_states(template,text)
        if mention:  # what the web pre-fills in a reply box: the parent's author
            states[1]['value']['attribute']=[{'start':0,'length':4,'type':{'$case':'mention','mention':{'entityID':ANA[0]}}}]
        return rutas.envelope(template,states,rutas.POST_SCREEN)

    def test_what_the_client_builds_is_allowed(self):
        allowed=(Request('GET','/voyager/api/me','voyager'),Request('GET',rutas.post_page(POST),'page'),
                 Request('GET',rutas.search_page('fundadores',['900001'],['es']),'page'),
                 Request('POST',rutas.sdui(rutas.REACT),'sdui',rutas.envelope(rutas.reaction(POST,'LIKE')),True),
                 Request('POST',rutas.sdui(rutas.REACT),'sdui',rutas.envelope(rutas.comment_reaction(POST,F.COMMENT_A,'EMPATHY')),True),
                 Request('POST',rutas.sdui(rutas.FOLLOW),'sdui',rutas.envelope(rutas.follow(ANA[2])),True),
                 Request('POST',rutas.sdui(rutas.COMMENT),'sdui',self.comment_body('Hola'),True),
                 Request('POST',rutas.voyager(rutas.INVITE),'voyager',rutas.invitation(ANA[0],'Hola'),True),
                 Request('POST',rutas.voyager(rutas.ACCEPT.format('7000001')),'voyager',rutas.acceptance('7000001','s'),True),
                 Request('POST',rutas.sdui(rutas.FILTER_BAR,'component'),'sdui',{'componentId':rutas.FILTER_BAR}),
                 Request('POST',rutas.sdui(rutas.GEO_TYPEAHEAD),'sdui',{'requestId':rutas.GEO_TYPEAHEAD}))
        for request in allowed:
            with self.subTest(path=request.path[:60]):permitidas.check(request)

    def test_everything_else_is_refused_before_leaving(self):
        unfollow=rutas.follow(ANA[2]);unfollow['requestedArguments']['payload']['followStateType']='FollowStateType_FOLLOW_INACTIVE'
        unreact=rutas.reaction(POST,'LIKE');unreact['requestedArguments']['payload']['reactionType']='ReactionType_UNREACT'
        invitee={'inviteeUnion':{'memberProfile':f'urn:li:fsd_profile:{ANA[0]}'}}
        refused={
            'perfil como página':Request('GET','/in/ana-ficticia/','page'),
            'mensajes como página':Request('GET',f'/messaging/thread/{F.THREAD}/','page'),
            'lectura fuera de Voyager':Request('GET','/feed/','voyager'),
            'otro host':Request('GET','//otro.example/voyager/api/me','voyager'),
            'salto de línea':Request('GET','/voyager/api/me\r\nx: y','voyager'),
            'tipo desconocido':Request('GET','/voyager/api/me','graphql'),
            'escritura como lectura':Request('POST',rutas.voyager(rutas.INVITE),'voyager',rutas.invitation(ANA[0]),False),
            'retirar invitación':Request('POST','/voyager/api/relationships/invitations/7000001?action=withdraw','voyager',{'invitationId':'7000001'},True),
            'ignorar invitación':Request('POST','/voyager/api/relationships/invitations/7000001?action=ignore','voyager',rutas.acceptance('7000001','s'),True),
            'aceptar otra':Request('POST',rutas.voyager(rutas.ACCEPT.format('7000001')),'voyager',rutas.acceptance('7000002','s'),True),
            'aceptar genérica':Request('POST',rutas.voyager(rutas.ACCEPT.format('7000001')),'voyager',
                                       {**rutas.acceptance('7000001','s'),'isGenericInvitation':True},True),
            'nota larga':Request('POST',rutas.voyager(rutas.INVITE),'voyager',{'invitee':invitee,'customMessage':'x'*301},True),
            'invitación con extra':Request('POST',rutas.voyager(rutas.INVITE),'voyager',{'invitee':invitee,'trackingId':'x'},True),
            'dejar de seguir':Request('POST',rutas.sdui(rutas.FOLLOW),'sdui',rutas.envelope(unfollow),True),
            'quitar reacción':Request('POST',rutas.sdui(rutas.REACT),'sdui',rutas.envelope(unreact),True),
            'reacción como lectura':Request('POST',rutas.sdui(rutas.REACT),'sdui',rutas.envelope(rutas.reaction(POST,'LIKE'))),
            'acción no listada':Request('POST',rutas.sdui('com.linkedin.sdui.reactions.delete'),'sdui',
                                        {'requestId':'com.linkedin.sdui.reactions.delete','requestedArguments':{'payload':{}}},True),
            'requestId cambiado':Request('POST',rutas.sdui(rutas.REACT),'sdui',{**rutas.envelope(rutas.reaction(POST,'LIKE')),'requestId':rutas.FOLLOW},True),
            'lectura marcada como escritura':Request('POST',rutas.sdui(rutas.FILTER_BAR,'component'),'sdui',{},True),
            'GET a la UI del servidor':Request('GET',rutas.sdui(rutas.REACT),'sdui'),
            'comentario sin plantilla':Request('POST',rutas.sdui(rutas.COMMENT),'sdui',
                                               rutas.envelope({'requestId':rutas.COMMENT,'requestedArguments':{'payload':{'collection':{}}}}),True),
            'comentario vacío':Request('POST',rutas.sdui(rutas.COMMENT),'sdui',self.comment_body('   '),True),
            'respuesta con mención':Request('POST',rutas.sdui(rutas.COMMENT),'sdui',self.comment_body('Hola',mention=True),True),
        }
        for why,request in refused.items():
            with self.subTest(why):
                t=F.FakeTransport()
                with self.assertRaises(LinkedInError) as e:Cliente(t)._send(request)
                self.assertEqual(e.exception.kind,'refused');self.assertEqual(t.sent,[])
                self.assertIn('no se envió nada',str(e.exception))


class ServiceTransportTests(SimpleTestCase):
    READ=Request('GET','/voyager/api/me','voyager',operation='account_status')
    WRITE=Request('POST',rutas.sdui(rutas.REACT),'sdui',{'requestId':rutas.REACT},True,'add_reaction')

    def service(self,handler):
        return ServiceTransport('http://navegador.interno:8080/','token-ficticio','cuenta-prueba',http_transport=httpx.MockTransport(handler))

    def test_one_post_per_call_with_the_token_and_the_request(self):
        seen=[]
        def handler(request):
            seen.append(request)
            return httpx.Response(200,json={'status':200,'text':'{"a":1}','content_type':'application/json',
                                            'url':'https://www.linkedin.com/voyager/api/me','redirected':False})
        answer=self.service(handler).send(self.WRITE)
        [r]=seen
        self.assertEqual((r.method,str(r.url)),('POST','http://navegador.interno:8080/v1/cuentas/cuenta-prueba/llamadas'))
        self.assertEqual(r.headers['authorization'],'Bearer token-ficticio')
        body=json.loads(r.content)
        self.assertEqual({k:body[k] for k in ('method','path','kind','body','write','operation')},
                         {'method':'POST','path':rutas.sdui(rutas.REACT),'kind':'sdui','body':{'requestId':rutas.REACT},'write':True,'operation':'add_reaction'})
        self.assertRegex(body['request_id'],r'^[0-9a-f-]{36}$')
        self.assertEqual(answer,Answer(200,'{"a":1}','application/json','https://www.linkedin.com/voyager/api/me',False))

    def test_the_service_own_answers(self):
        cases=((400,'contract',False),(401,'config',True),(403,'config',True),(404,'config',True),(409,'stopped',True),
               (422,'refused',False),(423,'login',True),(503,'not_sent',False),(504,'network',False),(502,'network',False))
        for status,kind,pause in cases:
            with self.subTest(status=status):
                t=self.service(lambda r,s=status:httpx.Response(s,json={'reason':'motivo corto'}))
                with self.assertRaises(LinkedInError) as e:t.send(self.READ)
                self.assertEqual((e.exception.kind,e.exception.pause,e.exception.status),(kind,pause,status))
                self.assertIn('motivo corto',str(e.exception));self.assertNotIn('token-ficticio',str(e.exception))
        for status in (500,502,504):  # it may have left: a write is uncertain
            with self.subTest(write=status),self.assertRaises(Uncertain):
                self.service(lambda r,s=status:httpx.Response(s)).send(self.WRITE)
        for status in (409,422,423,503):  # it did not leave: a write is a plain error
            with self.subTest(write=status),self.assertRaises(LinkedInError):
                self.service(lambda r,s=status:httpx.Response(s)).send(self.WRITE)

    def test_network_failures(self):
        def down(request):raise httpx.ConnectError('sin conexión',request=request)
        def late(request):raise httpx.ReadTimeout('tarde',request=request)
        def garbled(request):return httpx.Response(200,text='no es json')
        with self.assertRaises(LinkedInError) as e:self.service(down).send(self.WRITE)
        self.assertEqual(e.exception.kind,'not_sent')
        with self.assertRaises(Uncertain):self.service(late).send(self.WRITE)
        with self.assertRaises(LinkedInError) as e:self.service(late).send(self.READ)
        self.assertEqual(e.exception.kind,'network')
        with self.assertRaises(Uncertain):self.service(garbled).send(self.WRITE)
        with self.assertRaises(LinkedInError) as e:self.service(garbled).send(self.READ)
        self.assertEqual(e.exception.kind,'contract')

    def test_live_query(self):
        seen=[]
        fresh='messengerConversations.'+'a'*32
        def handler(request):
            seen.append(request)
            return httpx.Response(200,json={'path':'/voyagerMessagingGraphQL/graphql','query_id':fresh,'variables':['mailboxUrn'],'source':'page'})
        self.assertEqual(self.service(handler).live_query(rutas.CONVERSATION_QUERIES,['mailboxUrn'])['query_id'],fresh)
        self.assertEqual((seen[0].method,seen[0].url.path,dict(seen[0].url.params)),
                         ('GET','/v1/cuentas/cuenta-prueba/consultas',
                          {'prefixes':','.join(rutas.CONVERSATION_QUERIES),'variables':'mailboxUrn'}))
        def down(request):raise httpx.ConnectError('x',request=request)
        for handler in (lambda r:httpx.Response(404,json={'reason':'ninguna'}),lambda r:httpx.Response(200,json={'path':'/x'}),
                        lambda r:httpx.Response(200,text='x'),down):
            self.assertIsNone(self.service(handler).live_query(['a'],['b']))


class DirectoConnectorTests(SimpleTestCase):
    def setUp(self):
        p=patch.object(connectors_directo,'TRANSPORT',None);p.start();self.addCleanup(p.stop)

    def build(self,account='cuenta-prueba',**env):
        clean={k:v for k,v in os.environ.items() if k not in ('LIVE_LINKEDIN_DIRECTO','NAVEGADOR_URL','NAVEGADOR_TOKEN')}
        with patch.dict(os.environ,{**clean,**env},clear=True):return DirectoConnector(account)

    def test_the_same_methods_and_arguments_as_unipile(self):
        def methods(cls):return {n:str(inspect.signature(f)) for n,f in inspect.getmembers(cls,inspect.isfunction) if not n.startswith('_')}
        own=methods(DirectoConnector)
        # One read more, only here: the creator analytics; callers check hasattr (test_analitica.py).
        self.assertEqual(own.pop('analytics'),'(self, start, end, order=None)')
        self.assertFalse(hasattr(UnipileConnector,'analytics'))
        self.assertEqual(own,methods(UnipileConnector))
        self.assertEqual(len(own),21)
        self.assertEqual(DirectoConnector.provider,'directo')

    def test_no_way_to_send_a_message(self):
        for name in dir(DirectoConnector)+dir(Cliente):
            self.assertNotRegex(name,r'send_message|start_chat|reply|forward|mark|read_message')

    def test_off_and_fail_closed_without_configuration(self):
        on={'LIVE_LINKEDIN_DIRECTO':'true','NAVEGADOR_URL':'http://navegador.interno:8080','NAVEGADOR_TOKEN':'token-ficticio'}
        cases=(({},'disabled'),({'LIVE_LINKEDIN_DIRECTO':'false','NAVEGADOR_URL':on['NAVEGADOR_URL'],'NAVEGADOR_TOKEN':'token-ficticio'},'disabled'),
               ({'LIVE_LINKEDIN_DIRECTO':'true'},'config'),({**on,'NAVEGADOR_TOKEN':''},'config'),({**on,'NAVEGADOR_URL':' '},'config'),
               ({**on,'NAVEGADOR_URL':'ftp://navegador.interno'},'config'))
        for env,kind in cases:
            with self.subTest(env=sorted(env)),self.assertRaises(ConnectorError) as e:self.build(**env)
            self.assertEqual((e.exception.kind,e.exception.pause),(kind,False))
            self.assertNotIn('token-ficticio',str(e.exception))
        c=self.build(**on)
        self.assertIsInstance(c.client.t,ServiceTransport)
        self.assertEqual((c.client.t.account,str(c.client.t.http.base_url).rstrip('/')),('cuenta-prueba','http://navegador.interno:8080'))

    def test_the_account_is_a_slug_of_the_service(self):
        for account in ('','Con Mayúsculas','../cuenta','a'*70,'acc_ABC123',None):
            with self.subTest(account=account),self.assertRaises(ConnectorError) as e:
                DirectoConnector(account,transport=F.FakeTransport())
            self.assertEqual(e.exception.kind,'config')


class ProviderWiringTests(TestCase):
    def account(self):
        return ConnectorAccount.objects.create(provider='directo',external_account_id='cuenta-prueba',label='Cuenta directa de prueba')

    def test_a_directo_account_gets_the_direct_connector(self):
        account=self.account()
        t=F.FakeTransport(ME)
        with patch.object(connectors_directo,'TRANSPORT',t):
            self.assertIsInstance(get_connector(account),DirectoConnector)
            operador.check_account(account)
        account.refresh_from_db()
        self.assertEqual((account.status,account.is_locked,account.paused),('running',False,False))
        self.assertEqual(t.paths(),['/voyager/api/me'])

    def test_off_by_default(self):
        account=self.account()
        with patch.object(connectors_directo,'TRANSPORT',None),patch.dict(os.environ,{'LIVE_LINKEDIN_DIRECTO':'false'}):
            with self.assertRaises(ConnectorError) as e:get_connector(account)
        self.assertEqual(e.exception.kind,'disabled')

    def test_the_provider_is_accepted_where_unipile_is(self):
        self.assertIn('directo',ConnectorAccount.Provider.values)
        self.assertTrue(AccountInput(data={'provider':'directo','external_account_id':'cuenta-prueba','label':'Prueba'}).is_valid())
        for providers in (metricas.PROVIDERS,conversaciones.PROVIDERS,respuestas.PROVIDERS):
            self.assertIn('directo',providers)
