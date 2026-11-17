"""The buyer's path as it runs today, end to end (comprador.py, phase 1 of docs/plan-outbound.md): the production
functions (red.discover/classify/plan/sync, the operator, desenlaces_captura, respuestas) drive a synthetic buyer with
the fake connector and patched providers, and each step checks the journey, its touches and the funnel.

BuyerPathBase is the harness: one method per step of the path, each going through production code. Phases 2–6 add
their steps here (read the buyer's posts and comment, the first message on acceptance, messages 2–4, the non-posting
route, the classified reply and the meeting) and extend the walk; nothing in it writes the journey directly."""
import json
import os
import uuid
from contextlib import ExitStack
from datetime import timedelta
from unittest.mock import patch
from django.utils import timezone
from team_backend import autopiloto, calentamiento, comprador, jobs, operador, red, respuestas
from team_backend.models import (ActionExecution, ActionProposal, AuditEvent, BuyerJourney, BuyerTouch, Contact, Job, ObservedPost,
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


# --------------------------------------------------------------------------- phase 2: the warm-up (BAR-19)

WARM_1=('Two engineers and a spreadsheet is how most pilots start; the usual sign it holds is logging which report the client '
        'opens weekly. Which report made them pay first?')
WARM_2=('Moving from a pilot to a product usually breaks at onboarding: the spreadsheet hid manual steps nobody wrote down. '
        'Which manual step are you automating first next quarter?')
NEXT_POST='Our pilot client renewed. Now we are rebuilding onboarding so the next ten clients do not need a call each.'
PREFILTER={'sustancia':0.9,'tema':0.9,'vacante':0.05,'promocion':0.1,'hito':0.05}
LOW={'pitch','inventa','cal_aplauso'}


class WarmupPathBase(BuyerPathBase):
    """The path with BUYER_WARMUP_ENABLED: the team reads the buyer's posts, comments them through the autopilot (rules
    and the lead, Jev simulated) and invites once the warm-up is done. Caps of 17/11/2026: 15 comments a day, 75 a week."""
    def setUp(self):
        super().setUp()
        env=patch.dict(os.environ,{'BUYER_WARMUP_ENABLED':'true','OPERATOR_DAILY_LIMITS':'INT-03=15','OPERATOR_WEEKLY_LIMITS':'INT-03=75'})
        env.start();self.addCleanup(env.stop)
        self.drafts=[];self.jev=[]

    def lead(self):
        def answer(state,questions,**kwargs):
            self.jev.append({'purpose':kwargs.get('purpose'),'questions':dict(questions),'state':state})
            if kwargs.get('purpose')=='comment-prefilter':return {'answers':{q:{'noul':PREFILTER.get(q,0.9)} for q in questions},'model':'fake-jev','estimated_usd':0}
            return {'answers':{q:{'noul':0.05 if q in LOW else 0.9} for q in questions},'model':'fake-jev','estimated_usd':0}
        stack=ExitStack()
        stack.enter_context(patch.dict(os.environ,{'LEAD_ENABLED':'true'}))
        stack.enter_context(patch('knowledge.providers.typesafe',side_effect=answer))
        return stack

    def drafter(self,text):
        def claude(system,message,**kwargs):
            self.drafts.append({'context':kwargs.get('context') or '','system':system,'inputs':json.loads(message)})
            out={'decision':'comment','language':'en','comment':text,'rationale':'Aporta y pregunta.',
                 'citations':['LI-07-M005-K05','LI-03-M006-K02'],'claims_needing_evidence':[],'risks':[]}
            return {'text':json.dumps(out),'model':'claude-opus-5-5'}
        return patch('knowledge.providers.claude',side_effect=claude)

    # -- steps (production code only)
    def chosen_and_followed(self,slug='ana-acme',name='Ana Acme'):
        contact=self.step_choose(slug,name)
        follow=self.step_follow(contact)
        self.assertEqual(follow.state,'confirmed')
        contact.refresh_from_db()
        return contact

    def their_new_post(self,contact,text=BUYER_POST,suffix='p1',hours_ago=2):
        """A post of the buyer on LinkedIn (the fake connector). Nobody stored it: the read does."""
        user=self.fake.state['users'][contact.provider_user_id]
        pid=f'activity:{user["public_identifier"]}-{suffix}'
        self.fake.state['posts'][pid]={'id':pid,'share_url':'https://www.linkedin.com/feed/update/urn:li:'+pid,'text':text,
            'created_at':(timezone.now()-timedelta(hours=hours_ago)).isoformat(),'author':user,'comments_counter':0,
            'reactions_counter':[],'reposts_counter':0,'user_reacted':False,'is_repost':False}
        self.fake.state['comments'][pid]=[]
        return pid

    def observe(self,later=False):
        """The observe job (operador.observe → calentamiento.read_posts). `later`: the reread interval passed."""
        if later:
            AuditEvent.objects.filter(action=calentamiento.POSTS_READ).update(created_at=timezone.now()-timedelta(hours=73))
        jobs.enqueue_operation(self.bot,'observe',{'account':str(self.account.id),'limit':5,'referents':[]},request_id=uuid.uuid4())
        self.drain()
        return Job.objects.filter(kind='observe').order_by('-created_at').first()

    def autopilot_comment(self,text):
        """autopiloto._propose picks the post, propose_comment drafts it, the gate (rules + lead) and the operator write
        it. Returns the proposal, or None when the autopilot proposed nothing."""
        before=set(ActionProposal.objects.filter(capability='INT-03').values_list('pk',flat=True))
        with self.drafter(text),self.lead():
            queued=autopiloto._propose(self.bot,self.account,timezone.now())
            self.drain()
            new=ActionProposal.objects.filter(capability='INT-03').exclude(pk__in=before).first()
            if not queued or new is None:return None
            new=autopiloto.policy_review(new)
            if new.state=='approved':operador.execute(self.gustavo,new.id)
        return ActionProposal.objects.get(pk=new.pk)

    def a_day_later(self,proposal,hours=49):
        """The author wait (48 h) passed since that comment was drafted."""
        ActionProposal.objects.filter(pk=proposal.pk).update(created_at=timezone.now()-timedelta(hours=hours))

    def plan(self,now=None):
        if now is None:return self.job('plan_network')
        return red.plan(self.bot,self.account,now)

    def invite_proposed(self,contact):
        return ActionProposal.objects.filter(contact=contact,capability='RED-02').exists()

    def warm_up(self,contact):
        """Two warm-up comments on two of their posts, the second after the author wait."""
        self.their_new_post(contact)
        self.observe()
        first=self.autopilot_comment(WARM_1)
        self.assertEqual(first.state,'confirmed',first.risks)
        self.their_new_post(contact,NEXT_POST,suffix='p2',hours_ago=1)
        self.observe(later=True)
        self.a_day_later(first)
        second=self.autopilot_comment(WARM_2)
        self.assertEqual(second.state,'confirmed',second.risks)
        return first,second


class WarmupBuyerPathTests(WarmupPathBase):
    def test_chosen_followed_read_two_comments_invited_accepted(self):
        # 1–2. Chosen and followed: warming up, due at the latest 14 days after the follow (not 48 h).
        ana=self.chosen_and_followed()
        journey=self.journey(ana)
        follow=journey.touches.get(kind='seguir')
        self.assertEqual((journey.step,journey.next_at),('calentando',follow.at+timedelta(days=14)))

        # 3. Her recent posts are read (one read, her own daily cap) and stored without a referent.
        pid=self.their_new_post(ana)
        job=self.observe()
        self.assertEqual(job.state,'complete',job.error)
        post=ObservedPost.objects.get(provider_post_id=pid)
        self.assertEqual((post.referent_id,post.author_provider_id),(None,ana.provider_user_id))
        self.assertEqual(AuditEvent.objects.filter(action=calentamiento.READ_ACTION).count(),1)
        read=AuditEvent.objects.get(action=calentamiento.POSTS_READ)
        self.assertEqual((read.target,read.metadata['comentables']),(str(ana.pk),1))

        # 4. First comment: the autopilot proposes her post, the draft loads the warm-up methodology, the rules and the
        # lead (with its three warm-up questions) pass it, the operator writes it.
        first=self.autopilot_comment(WARM_1)
        self.assertEqual((first.state,first.post_id),('confirmed',post.pk))
        for uid in operador.WARMUP_COMMENT_UNITS:self.assertIn(uid,self.drafts[0]['context'])
        self.assertIn('calentamiento',self.drafts[0]['inputs'])
        self.assertIn('Comentario de calentamiento',self.drafts[0]['system'])
        review=next(c for c in self.jev if c['purpose']=='lead-review')
        self.assertLessEqual({'cal_aporte','cal_pregunta','cal_aplauso'},set(review['questions']))
        self.assertEqual(review['state']['course_grounding']['course_methodology'],'comentario_calentamiento')
        self.assertEqual(self.fake.list_comments(pid)[0]['text'],WARM_1)
        journey=self.journey(ana)
        self.assertEqual((journey.step,journey.warm_comments,journey.next_at),('calentando',1,follow.at+timedelta(days=14)))

        # 5. One comment is not the warm-up: 49 h after the follow she is still not invited (today's rule would).
        Contact.objects.filter(pk=ana.pk).update(followed_at=timezone.now()-timedelta(hours=49))
        self.plan()
        self.assertFalse(self.invite_proposed(ana))

        # 6. The author wait: a new post of hers is read, but no second comment within 48 h of the first.
        pid2=self.their_new_post(ana,NEXT_POST,suffix='p2',hours_ago=1)
        self.observe(later=True)
        self.assertTrue(ObservedPost.objects.filter(provider_post_id=pid2,referent__isnull=True).exists())
        self.assertIsNone(self.autopilot_comment(WARM_2))
        self.assertFalse(Job.objects.filter(kind='propose_comment',state='queued').exists())

        # 7. Second comment after the wait: the warm-up is done, she is due now.
        self.a_day_later(first)
        second=self.autopilot_comment(WARM_2)
        self.assertEqual(second.state,'confirmed',second.risks)
        journey=self.journey(ana)
        comments=list(journey.touches.filter(kind='comentario').order_by('at'))
        self.assertEqual((journey.warm_comments,journey.next_at),(2,comments[1].at))

        # 8. Invitation without a note (RED-02 through the plan and Gustavo's approval).
        self.plan()
        invite=self.approve_open(ana,'RED-02')
        self.assertEqual((invite.state,Contact.objects.get(pk=ana.pk).stage),('confirmed','invited'))
        journey=self.journey(ana)
        self.assertEqual((journey.step,journey.comments_before_invite,journey.next_at),('invitado',2,None))

        # 9. She accepts.
        ana=self.step_accept(ana)
        self.assertEqual(self.journey(ana).step,'acepto')
        self.assertEqual([k for k,_ in self.kinds(ana)],['elegido','seguir','comentario','comentario','invitacion','acepto_invitacion'])

        # The funnel shows the real warm-up: calentados and calentados_2, and the comparisons.
        funnel=self.funnel()
        total=self.stages(funnel['acumulado'])
        self.assertEqual({k:total[k] for k in ('elegidos','calentados','calentados_2','invitados','aceptaron')},
                         {'elegidos':1,'calentados':1,'calentados_2':1,'invitados':1,'aceptaron':1})
        compare=funnel['comparaciones']
        self.assertEqual((compare['calentamiento']['calentados']['personas'],compare['calentamiento']['no_calentados']['personas']),(1,0))
        self.assertEqual((compare['senal_de_compra']['con_senal_de_compra']['personas'],
                          compare['senal_de_compra']['sin_senal_de_compra']['personas']),(0,1))
        self.assertEqual(self.fake.state['writes'],4)  # follow, two comments, invitation
        self.assertEqual(sum(m['is_sender'] for chat in self.fake.state['chats'].values() for m in chat['messages']),0)
        self.assertFalse(AuditEvent.objects.filter(action__in=['buyer.record_failed','buyer.warmup_failed']).exists())

    def test_1_she_answers_the_first_comment_and_is_invited_without_the_second(self):
        ana=self.chosen_and_followed()
        self.their_new_post(ana)
        self.observe()
        first=self.autopilot_comment(WARM_1)
        self.plan()
        self.assertFalse(self.invite_proposed(ana))
        self.step_their_answer(ana,first)  # «respondió a un comentario del equipo» (Alta): the warm-up ends now
        journey=self.journey(ana)
        signal=journey.touches.get(kind='respondio_comentario')
        self.assertEqual((journey.warm_comments,journey.next_at),(1,signal.at))
        self.plan()
        self.assertEqual(self.approve_open(ana,'RED-02').state,'confirmed')
        self.assertEqual(self.journey(ana).comments_before_invite,1)
        self.assertEqual(self.stages(self.funnel()['acumulado'])['calentados_2'],0)

    def test_2_without_posts_she_takes_the_route_without_posts_and_is_invited_at_14_days(self):
        ana=self.chosen_and_followed()
        self.observe()
        self.assertEqual(self.journey(ana).route,'sin_definir')
        self.observe(later=True)  # a second read in 10 days without a commentable post
        journey=self.journey(ana)
        self.assertEqual((journey.route,journey.step),('sin_posts','calentando'))
        reads=AuditEvent.objects.filter(action=calentamiento.READ_ACTION).count()
        self.observe(later=True)  # nobody reads her any more
        self.assertEqual(AuditEvent.objects.filter(action=calentamiento.READ_ACTION).count(),reads)
        follow=journey.touches.get(kind='seguir').at
        self.plan(now=follow+timedelta(days=13))
        self.assertFalse(self.invite_proposed(ana))
        self.plan(now=follow+timedelta(days=14,minutes=1))
        self.assertEqual(self.approve_open(ana,'RED-02').state,'confirmed')
        self.assertEqual(self.journey(ana).comments_before_invite,0)

    def test_3_no_acceptance_in_21_days_rests_her_and_a_signal_wakes_her_without_a_new_invitation(self):
        ana=self.chosen_and_followed()
        self.warm_up(ana)
        self.plan()
        self.approve_open(ana,'RED-02')
        invited=self.journey(ana).touches.get(kind='invitacion').at
        self.plan(now=invited+timedelta(days=20))
        self.assertEqual(self.journey(ana).step,'invitado')
        later=invited+timedelta(days=22)
        summary=self.plan(now=later)
        self.assertEqual(summary['calentamiento']['descanso'],1)
        journey=self.journey(ana)
        self.assertEqual((journey.step,journey.rest_reason,journey.rest_until),('descanso','invitacion_no_aceptada',later+timedelta(days=60)))
        listed=calentamiento.old_invitations(21,now=later)
        self.assertEqual([(i['nombre'],i['recorrido']['paso']) for i in listed['invitaciones']],[('Ana Acme','descanso')])

        # While she rests nobody reads or comments her posts.
        self.their_new_post(ana,'Hiring our first account executive next month to take over pilots.',suffix='p3',hours_ago=1)
        reads=AuditEvent.objects.filter(action=calentamiento.READ_ACTION).count()
        self.observe(later=True)
        self.assertEqual(AuditEvent.objects.filter(action=calentamiento.READ_ACTION).count(),reads)
        self.assertIsNone(self.autopilot_comment(WARM_1))

        # A signal during the rest wakes her at once (the phase API records it as the hooks would: she commented on his post).
        comprador.record(journey,BuyerTouch.Kind.COMMENTED_POST,at=later+timedelta(days=1),key='prueba:comento')
        summary=self.plan(now=later+timedelta(days=2))
        self.assertEqual(summary['calentamiento']['despiertan'],1)
        journey=self.journey(ana)
        retry=journey.touches.get(kind='reintento')
        self.assertEqual((journey.step,journey.attempt,retry.detail['por_senal']),('calentando',2,True))
        self.assertEqual(retry.detail['angulo'],'Señal en el descanso: Comentó en un post de Gustavo')
        # The invitation is still pending: never sent again (stage invited), never withdrawn.
        self.assertEqual(ActionProposal.objects.filter(contact=ana,capability='RED-02').count(),1)
        self.assertEqual(Contact.objects.get(pk=ana.pk).stage,'invited')

    def test_5_the_day_is_shared_8_2_5_and_a_group_without_posts_passes_its_slots(self):
        # 17/11/2026: 15 a day, 8 buyers, 5 referents, 2 community (no source yet: they pass on); a weekend's 7 → 4/1/2.
        self.assertEqual(calentamiento.quotas(15),{'compradores':8,'comunidad':2,'referentes':5})
        self.assertEqual(calentamiento.quotas(7),{'compradores':4,'comunidad':1,'referentes':2})
        ana=self.chosen_and_followed()
        self.their_new_post(ana)
        self.observe()
        operador.add_referent(self.gustavo,self.account,'https://www.linkedin.com/in/referente-ai/','Habla de producto')
        jobs.enqueue_operation(self.bot,'observe',{'account':str(self.account.id),'limit':5,'referents':[]},request_id=uuid.uuid4())
        self.drain()
        now=timezone.now()
        self.assertEqual(calentamiento.rooms(self.account,now,{'compradores','referentes'}),{'compradores':8,'comunidad':0,'referentes':7})
        # Buyers first: her post before the referent's.
        first=self.autopilot_comment(WARM_1)
        self.assertIsNone(first.post.referent_id)
        # With the buyers' slots spent, the referent's post still gets its own; without buyers' posts, all slots go on.
        with patch.object(calentamiento,'used',return_value={'compradores':8,'comunidad':0,'referentes':0}):
            room=calentamiento.rooms(self.account,now,{'referentes'})
            self.assertEqual(room,{'compradores':0,'comunidad':0,'referentes':7})
            second=self.autopilot_comment('Evals become the product once customers ask how you know it works. Which eval did your customers ask for first?')
        self.assertIsNotNone(second.post.referent_id)
        self.assertEqual(calentamiento.rooms(self.account,now,set()),{'compradores':7,'comunidad':2,'referentes':4})
        self.assertEqual(calentamiento.rooms(self.account,now,{'referentes'})['referentes'],13)

    def test_6_peers_and_recommenders_keep_todays_rule(self):
        par=self.contact('par-luis','Luis Par',stage='followed',followed_hours=49)
        rec=self.contact('rec-rosa','Rosa Rec',stage='followed',followed_hours=47)
        for row,role in ((par,'par'),(rec,'recomendador')):
            Contact.objects.filter(pk=row.pk).update(classification=dict(row.classification,role=role))
        self.plan()
        self.assertTrue(self.invite_proposed(par))
        self.assertFalse(self.invite_proposed(rec))
        self.assertFalse(BuyerJourney.objects.exists())

    def test_7_caps_and_ramp_are_the_same(self):
        with patch.dict(os.environ,{'BUYER_WARMUP_ENABLED':'false'}):
            off=(operador.limits(timezone.now()),red.ramp_limits(self.account))
        self.assertEqual((operador.limits(timezone.now()),red.ramp_limits(self.account)),off)
        for cap in range(0,21):self.assertEqual(sum(calentamiento.quotas(cap).values()),cap)
        # The overall cap rules: with INT-03 spent for the day nothing is proposed, whatever the groups say.
        ana=self.chosen_and_followed()
        self.their_new_post(ana)
        self.observe()
        with patch.object(operador,'capacity_left',return_value=0):
            self.assertIsNone(self.autopilot_comment(WARM_1))


class WarmupSwitchOffTests(BuyerPathBase):
    def test_4_with_the_switch_off_the_path_is_todays(self):
        with patch.dict(os.environ,{'BUYER_WARMUP_ENABLED':'false'}):
            ana=self.step_choose()
            follow=self.step_follow(ana)
            journey=self.journey(ana)
            self.assertEqual(journey.next_at,journey.touches.get(kind='seguir').at+timedelta(hours=48))
            user=self.fake.state['users'][ana.provider_user_id]
            self.fake.state['posts']['activity:ana-p1']={'id':'activity:ana-p1','share_url':'https://www.linkedin.com/feed/update/urn:li:activity:ana-p1',
                'text':BUYER_POST,'created_at':timezone.now().isoformat(),'author':user,'comments_counter':0,'reactions_counter':[],
                'reposts_counter':0,'user_reacted':False,'is_repost':False}
            jobs.enqueue_operation(self.bot,'observe',{'account':str(self.account.id),'limit':5,'referents':[]},request_id=uuid.uuid4())
            self.drain()
            self.assertFalse(ObservedPost.objects.exists())  # nobody reads buyers' posts
            self.assertFalse(AuditEvent.objects.filter(action__in=[calentamiento.READ_ACTION,calentamiento.POSTS_READ]).exists())
            post=self.their_post(ana)
            self.assertEqual(autopiloto._propose(self.bot,self.account,timezone.now()),0)  # only referents' posts
            self.assertFalse(calentamiento.warmup_post(post))
            long_text=' '.join(['word']*58)+'.'
            proposal=ActionProposal(account=self.account,capability='INT-03',post=post,payload={'text':long_text},source='human')
            self.assertEqual(autopiloto.comment_text_issues(proposal),[])  # no warm-up rules on her post
            Contact.objects.filter(pk=ana.pk).update(followed_at=timezone.now()-timedelta(hours=49))
            self.job('plan_network')
            self.assertTrue(ActionProposal.objects.filter(contact=ana,capability='RED-02').exists())
            self.assertNotIn('peso',comprador.temperature(ana))
            self.assertEqual(follow.state,'confirmed')
