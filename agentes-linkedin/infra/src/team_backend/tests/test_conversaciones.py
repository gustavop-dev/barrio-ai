"""conversaciones_inbox (docs/conversaciones-inbox.md): read-only inbox, Jev's read, Tu turno card, push and person card."""
import os
from datetime import timedelta
from unittest.mock import patch
import httpx
from django.contrib.auth.models import User
from django.utils import timezone
from knowledge import db, providers
from team_backend import autopiloto, conversaciones, jobs
from team_backend.connectors import FakeConnector, UnipileConnector
from team_backend.models import Contact, Conversation, Job, Opportunity
from team_backend.tests.test_operador import OperatorBase
from team_backend.tests.test_rediseno import JevMock

BUSINESS={'oportunidad':0.86,'espera':0.81,'venta':0.04,'startups':0.2,'projectapp':0.9}
ASK='Hola Gustavo, vi tu post sobre alcance de features. ¿Tienes disponibilidad para un proyecto corto de IA en enero?'


class InboxBase(OperatorBase):
    def setUp(self):
        super().setUp()
        env=patch.dict(os.environ,{'INBOX_ENABLED':'true','INBOX_READ_CAPS':'','LIVE_PROVIDERS':'true','TYPESAFE_API_KEY':'ts-test-key',
                                   'TYPESAFE_LIMIT_USD':'1','NETWORK_ENABLED':'false','METRICS_EVERY_MINUTES':'0'})
        env.start();self.addCleanup(env.stop)
        self.jev=JevMock(BUSINESS)
        transport=patch.object(providers,'TYPESAFE_TRANSPORT',httpx.MockTransport(self.jev))
        transport.start();self.addCleanup(transport.stop)
        pushes=patch('team_backend.alerts.notify',return_value=True)
        self.push=pushes.start();self.addCleanup(pushes.stop)
        self.bot,_=User.objects.get_or_create(username='barrio-autopiloto')
        self.grant(self.bot,'access_knowledge','run_agents','use_paid_providers','operate_linkedin','execute_actions')
        self.lucia=self.fake.seed_person('lucia-ficticia','Lucía Ficticia',headline='Cofundadora @ Huerta Labs (pre-seed)',distance='FIRST_DEGREE')
        self.contact=Contact.objects.create(account=self.account,provider_user_id=self.lucia['id'],public_identifier='lucia-ficticia',
            display_name='Lucía Ficticia',headline='Cofundadora @ Huerta Labs (pre-seed)',source='manual',stage='connected',
            profile_url='https://www.linkedin.com/in/lucia-ficticia',
            classification={'fit':True,'role':'comprador','modality':'projectapp','affinity':'desconocida','reason':'r','confidence':0.8})

    def ago(self,**kwargs):
        return timezone.now()-timedelta(**kwargs)

    def chat(self,messages=None,chat_id='2-SHVlcnRhTGFicw=='):
        return self.fake.seed_chat(self.lucia['id'],messages or [('Gracias por aceptar la invitación.',True,self.ago(days=3)),(ASK,False,self.ago(hours=2))],chat_id=chat_id)

    def read_inbox(self):
        jobs.enqueue_operation(self.bot,'read_inbox',{'account':str(self.account.id)})
        while jobs.process_one(self.worker):pass
        return Job.objects.filter(kind='read_inbox').order_by('-created_at').first()

    def turno(self):
        return self.human.get('/api/v1/tu-turno').json()

    def conversation_cards(self):
        return [c for c in self.turno()['items'] if c['type']=='conversacion']


class ReadTests(InboxBase):
    def test_reads_the_chat_list_and_the_new_thread_counting_reads_and_never_writing(self):
        self.chat()
        job=self.read_inbox()
        self.assertEqual((job.state,job.error),('complete',''));self.assertTrue(job.execute)  # a paid (Jev) operation
        conversation=Conversation.objects.get()
        self.assertEqual((conversation.provider_chat_id,conversation.attendee_name,conversation.attendee_provider_id,conversation.contact),
                         ('2-SHVlcnRhTGFicw==','Lucía Ficticia','AColucia-ficticia',self.contact))
        self.assertEqual([(m['from_me'],m['text']) for m in conversation.messages],[(True,'Gracias por aceptar la invitación.'),(False,ASK)])
        self.assertFalse(conversation.last_from_me);self.assertEqual(conversation.last_message_preview,ASK)
        self.assertEqual((conversaciones.reads_today(self.account,'chats'),conversaciones.reads_today(self.account,'messages')),(1,1))
        self.assertEqual(self.fake.state['writes'],0)
        self.read_inbox()  # nothing new: the list is read again, the thread is not
        self.assertEqual((conversaciones.reads_today(self.account,'chats'),conversaciones.reads_today(self.account,'messages')),(2,1))

    def test_each_configured_inbox_is_one_read(self):
        self.chat()
        asked=[]
        original=FakeConnector.list_chats
        def spy(connector,limit=20,inbox='CLASSIC_PRIMARY'):
            asked.append(inbox);return original(connector,limit,inbox=inbox)
        with patch.dict(os.environ,{'INBOX_IDS':'CLASSIC_PRIMARY, COMPANY_1_PRIMARY'}),patch.object(FakeConnector,'list_chats',spy):
            self.read_inbox()
        self.assertEqual(asked,['CLASSIC_PRIMARY','COMPANY_1_PRIMARY'])
        self.assertEqual(conversaciones.reads_today(self.account,'chats'),2)
        self.assertEqual(len(self.jev.requests),1)

    def test_old_chats_are_kept_from_the_list_only_and_groups_are_skipped(self):
        self.chat([(ASK,False,self.ago(days=40))])
        self.read_inbox()
        conversation=Conversation.objects.get()
        self.assertEqual((conversation.messages,conversation.assessment),([],{}))
        self.assertEqual(conversaciones.reads_today(self.account,'messages'),0)
        self.assertEqual(self.jev.requests,[])

    def test_read_caps_stop_the_reads(self):
        self.chat()
        other=self.fake.seed_person('pablo-ficticio','Pablo Ficticio')
        self.fake.seed_chat(other['id'],[('¿Hablamos de tu experiencia con agentes?',False,self.ago(hours=1))])
        with patch.dict(os.environ,{'INBOX_READ_CAPS':'chats=1,messages=1'}):
            job=self.read_inbox()
            self.assertIn('Tope diario de lecturas del inbox «messages»',job.error)
            self.assertEqual(sum(1 for c in Conversation.objects.all() if c.messages),1)
            job=self.read_inbox()
            self.assertIn('«chats» alcanzado (1)',job.error)

    def test_a_rate_limit_pauses_the_account_and_a_stopped_account_is_not_read(self):
        self.chat()
        self.fake.state['read_fail']='rate_limit'
        job=self.read_inbox()
        self.account.refresh_from_db()
        self.assertTrue(self.account.paused);self.assertIn('429',job.error)
        self.assertEqual(Conversation.objects.count(),0)
        self.account.paused=False;self.account.save()
        self.fake.state['status']='disconnected'
        job=self.read_inbox()
        self.account.refresh_from_db()
        self.assertTrue(self.account.paused);self.assertIn('no está operativa',job.error)
        self.assertEqual(conversaciones.reads_today(self.account,'chats'),1)  # only the first, failed, list

    def test_the_connector_reads_unipile_v2_and_has_no_way_to_send(self):
        for name in dir(UnipileConnector)+dir(FakeConnector):
            self.assertNotRegex(name,r'send_message|start_chat|reply|forward|mark|read_message')
        seen=[]
        def unipile(request):
            seen.append((request.method,request.url.path,dict(request.url.params)))
            if request.url.path.endswith('/chats'):
                return httpx.Response(200,json={'data':[{'object':'Chat','id':'2-abc==','name':'Lucía Ficticia','type':'1to1','is_1to1':True,
                    'user_id':'ACoLucia','unread_count':1,'last_message_timestamp':'2026-11-07T15:12:00.000Z',
                    'last_message':{'object':'MessagePreview','id':'m2','text':'¿Tienes disponibilidad?','is_sender':False}}]})
            return httpx.Response(200,json={'data':[{'object':'Message','id':'m2','chat_id':'2-abc==','sender_id':'ACoLucia','text':'¿Tienes disponibilidad?',
                'timestamp':'2026-11-07T15:12:00.000Z','is_sender':False,'is_hidden':False,'is_deleted':False,'is_event':False,'attachments':[],
                'sender':{'object':'User','id':'ACoLucia','type':'individual','display_name':'Lucía Ficticia','public_identifier':'lucia-ficticia'}},
                {'object':'Message','id':'m1','chat_id':'2-abc==','sender_id':'me','timestamp':'2026-11-06T10:00:00.000Z','is_sender':True,
                 'is_hidden':False,'is_deleted':False,'is_event':True,'event_type':8,'attachments':[]}]})
        with patch.dict(os.environ,{'LIVE_LINKEDIN':'true','UNIPILE_API_KEY':'test-only'}):
            connector=UnipileConnector('acc_test1',transport=httpx.MockTransport(unipile))
            chats=connector.list_chats(20);messages=connector.list_chat_messages('2-abc==',10)
        self.assertEqual(seen,[('GET','/v2/acc_test1/inboxes/CLASSIC_PRIMARY/chats',{'limit':'20'}),
                               ('GET','/v2/acc_test1/chats/2-abc==/messages',{'limit':'10'})])
        self.assertEqual((chats[0]['type'],chats[0]['user_id'],chats[0]['last_message']['id'],chats[0]['last_message_at'].hour),('1to1','ACoLucia','m2',15))
        self.assertEqual([(m['id'],m['is_sender'],m['hidden']) for m in messages],[('m2',False,False),('m1',True,True)])
        self.assertEqual(messages[0]['sender']['public_identifier'],'lucia-ficticia')
        self.assertEqual(conversaciones.chat_url('2-abc=='),'https://www.linkedin.com/messaging/thread/2-abc==/')
        self.assertEqual(conversaciones.chat_url('opaque_id'),'https://www.linkedin.com/messaging/')


class AssessmentAndCardTests(InboxBase):
    def test_an_opportunity_becomes_a_tu_turno_card_with_one_push_and_no_opportunity_is_created(self):
        self.chat();self.read_inbox()
        conversation=Conversation.objects.get()
        judged=conversation.assessment
        self.assertEqual((judged['opportunity'],judged['awaiting_reply'],judged['pitch'],judged['modality']),(True,True,False,'projectapp'))
        self.assertEqual(judged['answers']['oportunidad'],0.86);self.assertEqual(judged['model'],'jev-1.14.0')
        body=self.jev.requests[0]
        self.assertEqual(set(body['questions']),{'oportunidad','espera','venta','startups','projectapp'})
        self.assertIn('datos de terceros',body['state']['aviso'])
        self.assertEqual(body['state']['conversacion'][-1],{'de':'la persona','fecha':conversation.messages[-1]['at'],'texto':ASK})
        with db.connect() as c:
            row=c.execute("SELECT status,purpose FROM usage_ledger WHERE provider='typesafe'").fetchone()
        self.assertEqual((row['status'],row['purpose']),('complete','inbox-assess'))
        self.assertEqual(self.push.call_count,1)
        title,detail=self.push.call_args.args[:2]
        self.assertEqual(title,'Lucía Ficticia te escribió')
        self.assertEqual(detail,'Posible oportunidad: ProjectApp (86 %) · Espera tu respuesta (81 %)')
        self.assertNotIn('enero',detail)  # no message text in the push
        self.assertEqual(self.push.call_args.kwargs['url'],'/tu-turno')

        data=self.turno()
        card=next(c for c in data['items'] if c['type']=='conversacion')
        self.assertEqual(data['tasks']['conversaciones'][0]['id'],card['id']);self.assertEqual(data['counts']['tareas'],1)
        self.assertEqual((card['priority'],card['state'],card['agent'],card['agent_label'],card['title']),
                         ('importante','nueva','conversaciones_inbox','Conversaciones e inbox','Lucía Ficticia te escribió'))
        self.assertTrue(card['id'].startswith(f'conversation:{conversation.id}:'))
        self.assertEqual(card['body'],'Posible oportunidad: ProjectApp (86 %) · Espera tu respuesta (81 %)')
        labels=[a['label'] for a in card['actions']]
        self.assertEqual(labels,['Abrir en LinkedIn','Hecho, respondí','Marcar como oportunidad','No responder'])
        self.assertEqual(card['actions'][0],{'label':'Abrir en LinkedIn','href':'https://www.linkedin.com/messaging/thread/2-SHVlcnRhTGFicw==/','primary':True})
        self.assertEqual(card['actions'][2]['opportunity']['contact'],str(self.contact.id))
        self.assertEqual(card['actions'][2]['opportunity']['modality'],'projectapp')
        self.assertTrue(card['actions'][3]['note_optional'])
        self.assertEqual(card['conversation']['person']['id'],str(self.contact.id))
        self.assertEqual(card['conversation']['messages'][-1]['text'],ASK)
        self.assertEqual(Opportunity.objects.count(),0)

        self.human.post('/api/v1/tu-turno/vistos',{'ids':[card['id']]},format='json')
        self.read_inbox()  # nothing new: no new judgment, no second push, and the card keeps its id (Vista)
        self.assertEqual((len(self.jev.requests),self.push.call_count),(1,1))
        self.assertEqual(self.conversation_cards()[0]['state'],'vista')

        self.fake.add_message('2-SHVlcnRhTGFicw==','Te comparto el alcance: dos semanas, un piloto con datos reales.',False)
        self.read_inbox()  # a new inbound message: judged and pushed once more, and shown as Nueva again
        self.assertEqual((len(self.jev.requests),self.push.call_count),(2,2))
        again=self.conversation_cards()[0]
        self.assertNotEqual(again['id'],card['id']);self.assertEqual(again['state'],'nueva')

    def test_a_pitch_or_spam_is_judged_but_never_proposed(self):
        self.jev.probabilities=dict(BUSINESS,venta=0.92)
        self.chat([('Hi Gustavo! We help agencies 10x their leads. Book a demo this week?',False,self.ago(hours=1))])
        self.read_inbox()
        judged=Conversation.objects.get().assessment
        self.assertEqual((judged['pitch'],judged['opportunity'],judged['awaiting_reply']),(True,False,False))
        self.assertEqual(self.conversation_cards(),[]);self.assertEqual(self.push.call_count,0)

    def test_without_business_or_a_pending_reply_there_is_no_card(self):
        self.jev.probabilities=dict(BUSINESS,oportunidad=0.1,espera=0.3)
        self.chat([('¡Felicitaciones por el nuevo proyecto!',False,self.ago(hours=1))])
        self.read_inbox()
        self.assertEqual(self.conversation_cards(),[]);self.assertEqual(self.push.call_count,0)

    def test_jev_unavailable_leaves_it_unjudged_and_the_next_run_retries(self):
        self.jev.status=529
        self.chat();self.read_inbox()
        conversation=Conversation.objects.get()
        self.assertIn('error',conversation.assessment);self.assertNotIn('message_id',conversation.assessment)
        self.assertEqual(self.conversation_cards(),[])
        self.jev.status=200
        self.read_inbox()
        conversation.refresh_from_db()
        self.assertTrue(conversation.assessment['opportunity']);self.assertEqual(len(self.conversation_cards()),1)

    def test_a_reply_on_linkedin_or_closing_the_card_takes_it_away_until_a_new_message(self):
        self.chat();self.read_inbox()
        self.fake.add_message('2-SHVlcnRhTGFicw==','¡Hola Lucía! Sí, hablemos el martes.',True)
        self.read_inbox()
        conversation=Conversation.objects.get()
        self.assertTrue(conversation.last_from_me);self.assertEqual(self.conversation_cards(),[])
        recent=self.turno()['recent']
        self.assertIn({'kind':'conversation','id':f'conversation:{conversation.id}','title':'Lucía Ficticia te escribió','how':'Respondiste en LinkedIn'},
                      [{k:r[k] for k in ('kind','id','title','how')} for r in recent])

        self.fake.add_message('2-SHVlcnRhTGFicw==','Perfecto. ¿Te sirve a las 10?',False)
        self.read_inbox()
        card=self.conversation_cards()[0]
        close=next(a for a in card['actions'] if a['label']=='No responder')
        self.assertEqual(self.api.post(close['endpoint'],close['body'],format='json').status_code,403)  # a service token never decides
        response=self.human.post(close['endpoint'],dict(close['body'],note='Lo hablamos por teléfono'),format='json')
        self.assertEqual(response.status_code,200,response.content);self.assertFalse(response.json()['needs_you'])
        self.assertEqual(self.conversation_cards(),[])
        self.assertIn('Sin responder',[r['how'] for r in self.turno()['recent']])
        self.assertEqual(self.human.post(close['endpoint'],{'how':'otra'},format='json').status_code,400)
        self.fake.add_message('2-SHVlcnRhTGFicw==','¿Seguimos?',False)
        self.read_inbox()
        self.assertEqual(len(self.conversation_cards()),1)
        mine=Conversation.objects.create(account=self.account,provider_chat_id='2-solo',messages=[{'id':'x','at':None,'from_me':True,'text':'Hola'}])
        self.assertEqual(self.human.post(f'/api/v1/conversaciones/{mine.id}/cerrar',{'how':'respondi'},format='json').status_code,409)

    def test_the_card_offers_no_opportunity_when_one_is_open_and_disappears_when_the_inbox_is_off(self):
        Opportunity.objects.create(contact=self.contact,modality='projectapp',created_by=self.gustavo)
        self.chat();self.read_inbox()
        self.assertNotIn('Marcar como oportunidad',[a['label'] for a in self.conversation_cards()[0]['actions']])
        with patch.dict(os.environ,{'INBOX_ENABLED':'false'}):
            self.assertEqual(self.conversation_cards(),[])


class PersonCardTests(InboxBase):
    def test_the_person_card_shows_the_latest_messages_the_team_read_and_the_link(self):
        self.chat();self.read_inbox()
        data=self.human.get(f'/api/v1/red/contacts/{self.contact.id}').json()
        conversation=data['conversation']
        self.assertEqual(conversation['chat_url'],'https://www.linkedin.com/messaging/thread/2-SHVlcnRhTGFicw==/')
        self.assertEqual([(m['from_me'],m['text']) for m in conversation['messages']],[(True,'Gracias por aceptar la invitación.'),(False,ASK)])
        self.assertEqual((conversation['assessment']['opportunity'],conversation['assessment']['modality']),(True,'projectapp'))
        self.assertTrue(conversation['needs_you']);self.assertTrue(data['your_turn'])
        self.assertEqual(data['next_step'],{'owner':'gustavo','text':'Te toca: responder su mensaje','at':None})
        other=Contact.objects.create(account=self.account,provider_user_id='ACoOtra',display_name='Otra',source='manual')
        empty=self.human.get(f'/api/v1/red/contacts/{other.id}').json()
        self.assertEqual((empty['conversation'],empty['your_turn']),(None,False))


class AutopilotTests(InboxBase):
    def inbox_jobs(self):
        return Job.objects.filter(kind='read_inbox').count()

    def test_the_autopilot_queues_the_inbox_on_its_clock_only_when_switched_on(self):
        with patch.dict(os.environ,{'INBOX_ENABLED':'false'}):
            autopiloto.tick(self.bot)
        self.assertEqual(self.inbox_jobs(),0)
        report=autopiloto.tick(self.bot)
        self.assertEqual((report['inbox'],self.inbox_jobs()),(1,1))
        autopiloto.tick(self.bot)
        self.assertEqual(self.inbox_jobs(),1)  # pending, then the same bucket: one job per clock
        job=Job.objects.get(kind='read_inbox')
        self.assertEqual(jobs.lane_jobs('general').filter(id=job.id).count(),1)  # never on the actions lane
        Job.objects.all().delete()
        self.account.paused=True;self.account.save()
        autopiloto.tick(self.bot)
        self.assertEqual(self.inbox_jobs(),0)

    def test_the_defaults_keep_the_inbox_off(self):
        with patch.dict(os.environ,{},clear=False):
            os.environ.pop('INBOX_ENABLED',None)
            self.assertFalse(conversaciones.enabled())
        self.assertEqual(conversaciones.read_caps(),{'chats':24,'messages':60})
        self.assertEqual(conversaciones.thresholds(),{'opportunity':0.6,'reply':0.6,'pitch':0.4})
