"""The buyer's path as it runs today, end to end (comprador.py, phase 1 of docs/plan-outbound.md): the production
functions (red.discover/classify/plan/sync, the operator, desenlaces_captura, respuestas) drive a synthetic buyer with
the fake connector and patched providers, and each step checks the journey, its touches and the funnel.

BuyerPathBase is the harness: one method per step of the path, each going through production code. Phases 2–6 add
their steps here (read the buyer's posts and comment, the first message on acceptance, messages 2–4, the non-posting
route, the classified reply and the meeting) and extend the walk; nothing in it writes the journey directly."""
import json
import os
import uuid
from datetime import timedelta
from unittest.mock import patch
from django.utils import timezone
from team_backend import comprador, respuestas
from team_backend.models import (ActionExecution, ActionProposal, AuditEvent, BuyerJourney, BuyerTouch, Contact, ObservedPost,
                                 PostComment)
from team_backend.tests.test_respuestas import CLOSING, FOLLOW_UP, QUESTION, RepliesBase, draft

BUYER_POST='We shipped our first paid pilot with two engineers and a spreadsheet. Next quarter we need the real product.'
WARM_COMMENT='Two engineers and a spreadsheet is how most pilots start. What made the client pay before the product existed?'
THEIR_ANSWER='Honestly, the spreadsheet solved a real reporting pain. Now we need it to scale without hiring ten people.'


class BuyerPathBase(RepliesBase):
    """Harness of the buyer's path. Every step goes through production code and returns what it touched."""
    def setUp(self):
        super().setUp()
        # Today's buyer rules (12/11/2026): in the United States and with the stage checked on the web.
        env=patch.dict(os.environ,{'NETWORK_BUYER_REGION':'us','NETWORK_STAGE_CHECK':'true','BUYER_RECORD_ENABLED':'true'})
        env.start();self.addCleanup(env.stop)

    # -- providers: the classifier says «comprador», the web finds a seed round (no paid call, no network)
    def providers(self,fit=True):
        from team_backend import research
        def claude(system,message,**kwargs):
            if kwargs['purpose']=='network-stage':
                return {'text':json.dumps({'verdict':'semilla_o_mas','evidence':'La fuente dice que levantó una ronda semilla.',
                                           'source_urls':['https://news.example/acme-seed']}),'model':'claude-sonnet-5-5'}
            out=[{'id':p['id'],'fit':fit,'role':'comprador','modality':'projectapp','affinity':'desconocida','reason':'Founder con producto.',
                  'confidence':0.9,'course_citations':['LI-03-M005-K06'],'invitation_note':'','note_reason':''} for p in json.loads(message)['people']]
            return {'text':json.dumps({'contacts':out}),'model':kwargs.get('model'),'estimated_usd':0.001,'request_id':'req_net'}
        def web(request):
            source=research.Source('s1','https://news.example/acme-seed','Acme seed','Acme raised a seed round','2026-11-12T00:00:00+00:00')
            return research.ResearchResult(request.public_question,'complete','2026-11-12T00:00:00+00:00',
                                           (research.Finding('Acme raised a seed round.',('s1',)),),(source,),usage={'model':'claude-sonnet-5-5'})
        claude_patch=patch('knowledge.providers.claude',side_effect=claude);web_patch=patch('team_backend.research.research',side_effect=web)
        claude_patch.start();web_patch.start()
        return lambda:(claude_patch.stop(),web_patch.stop())

    # -- reads
    def journey(self,contact):
        return BuyerJourney.objects.get(contact=contact)

    def kinds(self,contact):
        return [(t.kind,t.direction) for t in self.journey(contact).touches.order_by('at','created_at')]

    def funnel(self):
        response=self.human.get('/api/v1/resultados/embudo-comprador?semanas=2')
        self.assertEqual(response.status_code,200,response.content)
        return response.json()

    def stages(self,block):
        return {s['etapa']:s['personas'] for s in block['etapas']}

    # -- steps (production code only)
    def step_choose(self,slug='ana-acme',name='Ana Acme',location='Austin, Texas'):
        """discover_network finds the person in a search; classify_contacts classifies and checks the stage on the web."""
        person=self.fake.seed_person(slug,name,headline='Founder & CEO at Acme',search='founder pre-seed',location=location)
        self.job('discover_network')
        stop=self.providers()
        try:job=self.job('classify_contacts')
        finally:stop()
        self.assertEqual(job.state,'complete',job.error)
        return Contact.objects.get(account=self.account,provider_user_id=person['id'])

    def step_follow(self,contact):
        self.job('plan_network')
        return self.approve_open(contact,'RED-01')

    def their_post(self,contact,text=BUYER_POST):
        """A post of the buyer as the account would observe it (phase 2 reads them itself)."""
        user=self.fake.state['users'][contact.provider_user_id]
        pid=f'activity:{user["public_identifier"]}-own';now=timezone.now()
        self.fake.state['posts'][pid]={'id':pid,'share_url':'https://www.linkedin.com/feed/update/urn:li:'+pid,'text':text,
            'created_at':now.isoformat(),'author':user,'comments_counter':0,'reactions_counter':[],'reposts_counter':0,
            'user_reacted':False,'is_repost':False}
        self.fake.state['comments'][pid]=[]
        return ObservedPost.objects.create(account=self.account,provider_post_id=pid,author_name=contact.display_name,
                                           author_provider_id=contact.provider_user_id,text=text,posted_at=now)

    def step_comment(self,post,text=WARM_COMMENT):
        """INT-03 on the buyer's post, through the API and the operator."""
        return self.approve(self.proposal(post,text))

    def step_their_answer(self,contact,comment):
        """The buyer answers the team's comment; 72 h later collect_outcomes reads who answered."""
        ActionExecution.objects.filter(pk=comment.execution.pk).update(started_at=timezone.now()-timedelta(hours=73))
        self.fake.comment_on_own_post(comment.post.provider_post_id,contact.provider_user_id,THEIR_ANSWER,thread=comment.execution.external_id)
        job=self.job('collect_outcomes')
        self.assertEqual(job.state,'complete',job.error)
        return job

    def step_invite(self,contact):
        Contact.objects.filter(pk=contact.pk).update(followed_at=timezone.now()-timedelta(hours=49))  # the warm-up passed
        self.job('plan_network')
        return self.approve_open(contact,'RED-02')

    def step_accept(self,contact):
        self.fake.accept_sent(contact.provider_user_id)
        job=self.job('sync_network')
        self.assertEqual(job.state,'complete',job.error)
        contact.refresh_from_db()
        return contact


class TodayBuyerPathTests(BuyerPathBase):
    def test_classify_follow_comment_answer_invite_accept(self):
        # 1. Chosen: discovered in a search, classified as a fitting buyer, the web confirms the stage.
        ana=self.step_choose()
        self.assertEqual((ana.stage,ana.classification['stage_check']['state']),('fit','ok'))
        journey=self.journey(ana)
        self.assertEqual((journey.step,journey.entry,journey.route,journey.origin),('elegido','saliente','sin_definir','en_vivo'))
        self.assertEqual(self.kinds(ana),[('elegido','estado')])

        # 2. Follow (RED-01, approved by Gustavo): warming up; due to be invited 48 h after the follow.
        follow=self.step_follow(ana)
        self.assertEqual((follow.state,ana.stage),('confirmed','followed'))
        journey=self.journey(ana)
        touch=journey.touches.get(kind='seguir')
        self.assertEqual((touch.direction,touch.proposal_id,touch.execution_id,touch.source),('saliente',follow.pk,follow.execution.pk,'en_vivo'))
        self.assertEqual((journey.step,journey.warming_at),('calentando',touch.at))
        self.assertEqual(journey.next_at,touch.at+timedelta(hours=48))

        # 3. A comment of the team on a post of hers (INT-03; ObservedPost.author_provider_id is her).
        post=self.their_post(ana)
        comment=self.step_comment(post)
        self.assertEqual(comment.state,'confirmed')
        journey=self.journey(ana)
        touch=journey.touches.get(kind='comentario')
        self.assertEqual((touch.direction,touch.post_id,touch.execution_id,touch.proposal_id),('saliente',post.pk,comment.execution.pk,comment.pk))
        self.assertEqual((journey.step,journey.warm_comments,journey.comments_before_invite,journey.route),('calentando',1,1,'comentarios'))
        self.assertFalse(journey.signal_before_invite)

        # 4. She answers that comment: the 72 h outcome lists her; a signal received before the invitation.
        self.step_their_answer(ana,comment)
        journey=self.journey(ana)
        signal=journey.touches.get(kind='respondio_comentario')
        self.assertEqual((signal.direction,signal.outcome.execution_id,signal.post_id),('entrante',comment.execution.pk,post.pk))
        self.assertTrue(signal.detail['autor_del_post'])
        self.assertEqual((journey.inbound_signals,journey.signal_before_invite,journey.last_inbound_at),(1,True,signal.at))
        heat=comprador.temperature(ana)
        self.assertEqual((heat['total'],heat['por_tipo'],heat['antes_de_invitar']),(1,{'respondio_comentario':1},1))
        self.assertEqual(heat['senales'][0]['ref']['outcome'],str(signal.outcome_id))

        # 5. Invitation without a note once the warm-up passed (RED-02).
        invite=self.step_invite(ana)
        self.assertEqual((invite.state,ana.stage),('confirmed','invited'))
        journey=self.journey(ana)
        touch=journey.touches.get(kind='invitacion')
        self.assertEqual((touch.direction,touch.detail['con_nota'],touch.execution_id),('saliente',False,invite.execution.pk))
        self.assertEqual((journey.step,journey.invite_note,journey.comments_before_invite,journey.next_at),('invitado',False,1,None))
        self.assertTrue(journey.signal_before_invite)

        # 6. She accepts; red.sync reads the connection.
        ana=self.step_accept(ana)
        self.assertEqual(ana.stage,'connected')
        journey=self.journey(ana)
        touch=journey.touches.get(kind='acepto_invitacion')
        self.assertEqual((touch.direction,touch.at),('entrante',ana.connected_at))
        self.assertEqual((journey.step,journey.accepted_at,journey.inbound_signals),('acepto',ana.connected_at,2))
        self.assertEqual(self.kinds(ana),[('elegido','estado'),('seguir','saliente'),('comentario','saliente'),('respondio_comentario','entrante'),
                                         ('invitacion','saliente'),('acepto_invitacion','entrante')])

        # The funnel (read-only endpoint): the path so far, later stages at zero, and the small sample flagged.
        funnel=self.funnel()
        total=funnel['acumulado']
        self.assertEqual(self.stages(total),{'elegidos':1,'calentados':1,'calentados_2':0,'invitados':1,'aceptaron':1,'recibieron_mensaje':0,
                                             'respondieron':0,'interesados':0,'reunion':0})
        self.assertEqual({s['etapa']:s['paso_pct'] for s in total['etapas']}['aceptaron'],100.0)
        self.assertEqual((total['invitaciones'],total['muestra_chica'],total['aviso']),(1,True,comprador.SMALL_SAMPLE_TEXT))
        this_week=funnel['semanas'][0]
        self.assertEqual(self.stages(this_week['cohorte'])['aceptaron'],1)
        self.assertEqual({k:this_week['actividad'][k] for k in ('elegidos','seguidos','invitados','aceptaron','comentarios','senales_entrantes')},
                         {'elegidos':1,'seguidos':1,'invitados':1,'aceptaron':1,'comentarios':1,'senales_entrantes':2})
        compare=funnel['comparaciones']
        self.assertEqual((compare['senal']['con_senal']['personas'],compare['senal']['sin_senal']['personas']),(1,0))
        self.assertEqual((compare['nota']['sin_nota']['personas'],compare['nota']['con_nota']['personas']),(1,0))
        self.assertEqual((compare['calentamiento']['calentados']['personas'],compare['ruta']['comentarios']['personas']),(1,1))
        self.assertEqual(funnel['estado_actual']['acepto'],1)

        # Nobody rests or leaves on today's path, and nothing the team does reads the record: the writes were the same.
        self.assertEqual((funnel['descanso'],funnel['salidas']['fuera_de_criterio']),({r:0 for r in BuyerJourney.RestReason.values},0))
        self.assertEqual(self.fake.state['writes'],3)  # follow, comment, invitation
        self.assertFalse(AuditEvent.objects.filter(action='buyer.record_failed').exists())

        # The rebuild finds every fact the hooks recorded: a second pass adds nothing, and from scratch it is the same log.
        live=set(BuyerTouch.objects.filter(journey__contact=ana).values_list('kind','key','direction'))
        self.assertEqual(comprador.rebuild()['toques_nuevos'],0)
        BuyerJourney.objects.filter(contact=ana).delete()
        summary=comprador.rebuild()
        self.assertEqual((summary['recorridos'],summary['nuevos'],summary['fallos']),(1,1,0))
        self.assertEqual(set(BuyerTouch.objects.filter(journey__contact=ana).values_list('kind','key','direction')),live)
        rebuilt=self.journey(ana)
        self.assertEqual((rebuilt.step,rebuilt.origin,rebuilt.comments_before_invite,rebuilt.signal_before_invite),('acepto','reconstruido',1,True))

    def test_a_buyer_waiting_for_the_web_is_not_chosen_yet(self):
        from team_backend import research
        self.fake.seed_person('beto-acme','Beto Acme',headline='Founder at Acme',search='founder pre-seed',location='Austin, Texas')
        self.job('discover_network')
        nothing=research.ResearchResult('q','unavailable','2026-11-12T00:00:00+00:00',usage={'model':'claude-sonnet-5-5'})
        with self.classifier({'Beto Acme':(True,0.9)}),patch('team_backend.research.research',return_value=nothing):
            self.job('classify_contacts')
        beto=Contact.objects.get(display_name='Beto Acme')
        self.assertEqual(beto.classification['stage_check']['state'],'pending')
        self.assertFalse(BuyerJourney.objects.exists())  # the stage is not confirmed: not chosen
        self.assertEqual(self.funnel()['acumulado']['personas'],0)

    def test_a_buyer_outside_the_united_states_is_not_chosen(self):
        self.fake.seed_person('caro-mx','Caro MX',headline='Founder at Acme',search='founder pre-seed',location='Mexico City')
        self.job('discover_network')
        stop=self.providers()
        try:self.job('classify_contacts')
        finally:stop()
        self.assertFalse(Contact.objects.get(display_name='Caro MX').classification['fit'])
        self.assertFalse(BuyerJourney.objects.exists())


class ConversationOnHisPostTests(BuyerPathBase):
    def test_a_buyer_who_talked_on_his_post_gets_a_drafted_message_and_gustavo_writes_it(self):
        """The other path of today: a comment on Gustavo's post (a signal), two public replies, the connection and the
        drafted first message (pending in Tu turno) until «Hecho, le escribí»."""
        _,pid=self.publish()
        maria=self.person()
        root=self.fake.comment_on_own_post(pid,maria['id'],QUESTION,at=timezone.now()-timedelta(minutes=20))
        self.read();first=PostComment.objects.get()
        self.assertFalse(BuyerJourney.objects.exists())  # not classified yet: not a buyer
        self.propose(first,draft());self.execute_proposal(ActionProposal.objects.get(capability='INT-04'))
        contact=Contact.objects.get(pk=first.contact_id)
        Contact.objects.filter(pk=contact.pk).update(classification={'fit':True,'role':'comprador','confidence':0.9})
        self.fake.comment_on_own_post(pid,maria['id'],FOLLOW_UP,thread=root,at=timezone.now()+timedelta(seconds=5))
        self.rescan()  # her second comment is stored: the journey starts with both comments and the team's reply
        second=PostComment.objects.get(text=FOLLOW_UP)
        journey=self.journey(contact)
        self.assertEqual([k for k,_ in self.kinds(contact)],['comento_post','elegido','respuesta_hilo','comento_post'])
        self.assertEqual((journey.step,journey.inbound_signals,journey.signal_before_invite),('elegido',2,True))
        reply=journey.touches.get(kind='respuesta_hilo')
        self.assertEqual((reply.direction,reply.comment_id),('saliente',first.pk))

        opener='Hi María, I kept thinking about your golden datasets going stale. How are you versioning them now?'
        self.propose(second,draft(reply=CLOSING,dm_opener=opener))
        proposal=ActionProposal.objects.get(capability='INT-04',comment=second)
        def jev(state,questions,**kwargs):
            low={'pitch':0.05,'inventa':0.05,'dm_pitch':0.05}
            return {'answers':{q:{'noul':low.get(q,0.9)} for q in questions},'model':'fake-jev','estimated_usd':0}
        with patch.dict('os.environ',{'LEAD_ENABLED':'true'}),patch('knowledge.providers.typesafe',side_effect=jev):
            self.assertEqual(self.execute_proposal(proposal).state,'confirmed')
        Contact.objects.filter(pk=contact.pk).update(stage='connected',connected_at=timezone.now(),network_distance='FIRST_DEGREE')
        respuestas.on_connected(Contact.objects.get(pk=contact.pk))

        # The drafted message waits in Tu turno: pending, not sent.
        self.assertEqual(comprador.drafts()['pendientes'],1)
        self.assertEqual((self.funnel()['borradores']['pendientes'],self.funnel()['borradores']['enviados']),(1,0))

        closed=self.human.post(f'/api/v1/respuestas/{second.id}/mensaje',{'how':'enviado'},format='json')
        self.assertEqual(closed.status_code,200,closed.content)
        journey=self.journey(contact)
        message=journey.touches.get(kind='mensaje')
        self.assertEqual((message.direction,message.comment_id,message.detail['fuente']),('saliente',second.pk,'mensaje_sugerido'))
        self.assertEqual((journey.step,journey.messages_sent,journey.first_message_at),('mensaje_1',1,message.at))
        self.assertEqual(journey.touches.get(kind='ya_conectados').direction,'estado')  # connected without an invitation of his
        drafts=self.funnel()['borradores']
        self.assertEqual((drafts['pendientes'],drafts['enviados'],drafts['enviados_pct']),(0,1,100.0))
        total=self.stages(self.funnel()['acumulado'])
        self.assertEqual((total['aceptaron'],total['recibieron_mensaje'],total['invitados']),(1,1,0))
        self.assertEqual(self.fake.state['writes'],2)  # two public replies; the message is Gustavo's, never the team's
