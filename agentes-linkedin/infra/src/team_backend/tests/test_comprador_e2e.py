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
    def providers(self,fit=True,note=''):
        """`note`: the classifier also proposes an invitation note (today's only source of notes, red.plan)."""
        from team_backend import research
        def claude(system,message,**kwargs):
            if kwargs['purpose']=='network-stage':
                return {'text':json.dumps({'verdict':'semilla_o_mas','evidence':'La fuente dice que levantó una ronda semilla.',
                                           'source_urls':['https://news.example/acme-seed']}),'model':'claude-sonnet-5-5'}
            cited=['LI-03-M005-K06']+(['LI-03-M006-K01'] if note else [])
            out=[{'id':p['id'],'fit':fit,'role':'comprador','modality':'projectapp','affinity':'desconocida','reason':'Founder con producto.',
                  'confidence':0.9,'course_citations':cited,'invitation_note':note,'note_reason':'Conversamos en su post.' if note else ''}
                 for p in json.loads(message)['people']]
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
    def step_choose(self,slug='ana-acme',name='Ana Acme',location='Austin, Texas',note=''):
        """discover_network finds the person in a search; classify_contacts classifies and checks the stage on the web."""
        person=self.fake.seed_person(slug,name,headline='Founder & CEO at Acme',search='founder pre-seed',location=location)
        self.job('discover_network')
        stop=self.providers(note=note)
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
    def chosen_and_followed(self,slug='ana-acme',name='Ana Acme',note=''):
        contact=self.step_choose(slug,name,note=note)
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


# --------------------------------------------------------------------------- phase 3: the first message and the note (BAR-20)

WARM_3=('Moving the weekly report off the spreadsheet usually shows who owned the numbers; teams that name one owner per '
        'report keep the habit. Which report did your clients notice first?')
AFTER_POST='We moved the weekly report off the spreadsheet. Next is onboarding without a call for every new client.'


def judge_message(text):
    """Jev simulado para el primer mensaje: retoma algo concreto, pregunta acotada, sin vender."""
    low=(text or '').lower()
    concrete=any(k in low for k in ('spreadsheet','report','pilot','manual step','onboarding'))
    generic=any(k in low for k in ('great to be connected','how are you thinking','what do you think'))
    sells=any(k in low for k in ('my team','we help','minutes','a call'))
    return {'dm_toque':0.9 if concrete and not generic else 0.15,'dm_puente':0.85 if concrete else 0.3,
            'dm_pregunta':0.2 if generic else 0.85,'dm_un_tema':0.9,'dm_en_persona':0.3 if generic else 0.85,
            'dm_pitch':0.9 if sells else 0.05,'inventa':0.05}


def judge_note(text):
    """Jev simulado para la nota: un hecho concreto suyo, que sirva para que acepte, sin vender."""
    low=(text or '').lower()
    sells=any(k in low for k in ('my team solves','we help','i help','our services'))
    concrete=any(k in low for k in ('spreadsheet','pilot','report','onboarding','piloto'))
    return {'nota_hecho':0.9 if concrete else 0.1,'nota_aceptar':0.2 if sells else 0.85,'nota_generica':0.05 if concrete else 0.9,
            'nota_pitch':0.9 if sells else 0.05,'nota_inventa':0.05}


class FirstMessagePathBase(WarmupPathBase):
    """The path with BUYER_FIRST_MESSAGE_ENABLED (phase 3): when a warmed buyer accepts, the team prepares a first message
    that Gustavo sends himself (Tu turno «Mensaje sugerido»); the month's notes go to warmed buyers, drafted at invite
    time. The steps call the production entry points; where today's code has none (before phase 3), the step does
    nothing, which is what the baselines measure."""
    def setUp(self):
        super().setUp()
        # 17/11/2026: 20 paid comment drafts a day (OperatorBase keeps the old 6 for the other suites).
        env=patch.dict(os.environ,{'BUYER_FIRST_MESSAGE_ENABLED':'true','NETWORK_STAGE_CHECKS_PER_DAY':'20','OPERATOR_DAILY_PROPOSALS':'20'})
        env.start();self.addCleanup(env.stop)
        # Several acceptances in one test day: each one is a sync_network read (4 a day in production).
        caps=patch.dict(red.READ_CAPS,{'sync':20});caps.start();self.addCleanup(caps.stop)
        self.texts={};self.calls=[]

    # -- providers
    def lead(self):
        """The lead with Jev simulated for every review of this path: comments, people, first messages and notes."""
        from team_backend import lider
        risks=set(lider.NETWORK_RISKS)
        def answer(state,questions,**kwargs):
            purpose=kwargs.get('purpose')
            self.jev.append({'purpose':purpose,'questions':dict(questions),'state':state})
            if purpose=='comment-prefilter':scores=PREFILTER
            elif purpose=='lead-review-message':scores=judge_message((state.get('primer_mensaje') or {}).get('texto'))
            elif purpose=='lead-review-note':scores=judge_note((state.get('nota') or {}).get('texto'))
            else:scores={}
            low=LOW|risks|{'dm_pitch'}  # RSP-07: the message drafted with a closing reply does not sell
            return {'answers':{q:{'noul':scores.get(q,0.05 if q in low else 0.9)} for q in questions},'model':'fake-jev','estimated_usd':0}
        stack=ExitStack()
        stack.enter_context(patch.dict(os.environ,{'LEAD_ENABLED':'true'}))
        stack.enter_context(patch('knowledge.providers.typesafe',side_effect=answer))
        return stack

    def writer(self):
        """Claude simulado para el primer mensaje y la nota: el texto de cada persona (self.texts[(purpose, nombre)]),
        citando el primer hecho que le dieron."""
        def claude(system,message,**kwargs):
            purpose=kwargs.get('purpose');data=json.loads(message)
            self.calls.append({'purpose':purpose,'context':kwargs.get('context') or '','system':system,'inputs':data})
            name=(data.get('persona') or {}).get('nombre','')
            facts=data.get('hechos') or []
            text=self.texts.get((purpose,name),'')
            out={'decision':'write' if text else 'none','language':'en','anchor':facts[0]['id'] if facts else '',
                 'rationale':'Retoma su hecho y le pregunta algo fácil.','claims_needing_evidence':[],'risks':[]}
            if purpose=='invite-note':
                out.update(note=text,citations=['LI-09-M002-K06','LI-09-V008-K04','LI-09-M002-K01','LI-03-M006-K01'])
            else:
                out.update(message=text,citations=['LI-09-M002-K05','LI-09-M003-K02','LI-09-M003-K03','LI-09-M003-K04','LI-09-M004-K02'])
            return {'text':json.dumps(out),'model':'claude-opus-5-5'}
        return patch('knowledge.providers.claude',side_effect=claude)

    # -- reads
    def drafts_of(self,contact,kind):
        """The person's drafts (BuyerDraft, phase 3); [] before it exists."""
        from team_backend import models
        model=getattr(models,'BuyerDraft',None)
        return list(model.objects.filter(contact=contact,kind=kind).order_by('created_at')) if model else []

    def stopped(self,contact,kind):
        """Who stopped the person's draft: «reglas», «juez», «hecho» (nothing real to cite) or «cupo» (no note left)."""
        event=(AuditEvent.objects.filter(action='buyer.draft_stopped',target=str(contact.pk),metadata__tipo=kind)
               .order_by('-created_at').first())
        return event.metadata.get('por') if event else None

    def paid(self,contact,purpose):
        return any(c['purpose']==purpose and (c['inputs'].get('persona') or {}).get('nombre')==contact.display_name for c in self.calls)

    def turn(self,later=timedelta(0)):
        """Tu turno → mensajes, read `later` from now (a card may wait for its hour)."""
        from rest_framework.test import APIClient
        client=APIClient();client.force_authenticate(self.gustavo)  # the session would not outlive a clock days ahead
        with patch('django.utils.timezone.now',return_value=timezone.now()+later):
            response=client.get('/api/v1/tu-turno')
        self.assertEqual(response.status_code,200,response.content)
        return response.json()['tasks']['mensajes']

    def cards_of(self,contact,later=timedelta(0)):
        return [c for c in self.turn(later) if ((c.get('message') or {}).get('person') or {}).get('id')==str(contact.pk)]

    def sent_invitation(self,contact):
        return next((i for i in self.fake.state['invitations']['sent'].values() if i['user']['id']==contact.provider_user_id),None)

    def messages_sent(self):
        """Private messages the account wrote: the team never sends one (INB-08)."""
        return sum(m['is_sender'] for chat in self.fake.state['chats'].values() for m in chat['messages'])

    # -- steps (production code only)
    def prepare(self,now=None,rounds=8):
        """The autopilot's buyer-draft step (phase 3: autopiloto._buyer_drafts) and its jobs, until it queues nothing.
        Before phase 3 there is no such step: nobody prepares a first message or a note."""
        step=getattr(autopiloto,'_buyer_drafts',None)
        if step is None:return 0
        queued=0
        with self.writer(),self.lead():
            for _ in range(rounds):
                n=step(self.bot,self.account,now or timezone.now())
                self.drain()
                if not n:break
                queued+=n
        return queued

    def close(self,card,how):
        action=next(a for a in card['actions'] if (a.get('body') or {}).get('how')==how)
        response=self.human.post(action['endpoint'],{'how':how},format='json')
        self.assertEqual(response.status_code,200,response.content)
        return response.json()

    def answered(self,slug,name,note=''):
        """Chosen, followed, one warm-up comment and her answer to it: warmed and ready to be invited (an accelerator)."""
        contact=self.chosen_and_followed(slug,name,note=note)
        self.their_new_post(contact)
        self.observe()
        first=self.autopilot_comment(WARM_1)
        self.assertEqual(first.state,'confirmed',first.risks)
        self.step_their_answer(contact,first)
        return Contact.objects.get(pk=contact.pk)

    def two_comments(self,slug,name):
        """Chosen, followed and the two warm-up comments, without an answer of hers."""
        contact=self.chosen_and_followed(slug,name)
        first,second=self.warm_up(contact)
        return Contact.objects.get(pk=contact.pk),second

    def without_posts(self,slug,name):
        """Chosen and followed, two reads without a post: the route without posts, ready at 14 days. Returns the moment."""
        contact=self.chosen_and_followed(slug,name)
        self.observe();self.observe(later=True)
        return contact,self.journey(contact).touches.get(kind='seguir').at+timedelta(days=14,minutes=1)

    def invite(self,contact,now=None,auto=False):
        """The plan proposes the invitation; Gustavo approves it (approval, as today) or, with `auto`, the autopilot's gate
        (RED-02 autonomous, the lead) approves it; the operator sends it. Returns the proposal. As in the autopilot's
        tick, the buyer-draft step runs first: a warmed buyer's note is decided before the plan (red.plan holds her
        while it is not)."""
        self.prepare(now)
        self.plan(now)
        proposal=ActionProposal.objects.filter(contact=contact,capability='RED-02').order_by('-created_at').first()
        if proposal is None:return None
        if not auto:
            with self.lead():return self.approve_open(contact,'RED-02')
        with self.lead(),patch.dict(os.environ,{'OPERATOR_AUTONOMY':'RED-02=auto'}):
            proposal=autopiloto.policy_review(ActionProposal.objects.get(pk=proposal.pk))
            if proposal.state=='approved':
                try:operador.execute(self.gustavo,proposal.id)
                except operador.OperatorBlocked:pass  # the gate stopped the send: it stays approved
        return ActionProposal.objects.get(pk=proposal.pk)

    def accepted(self,contact):
        contact=self.step_accept(contact)
        self.assertEqual(self.journey(contact).step,'acepto')
        return contact


def case_text(case,variant):
    from team_backend import evaluaciones
    field='nota' if case=='nota_invitacion' else 'mensaje'
    return evaluaciones.COURSE_CASES[case]['input'][variant][field]


LATER=timedelta(hours=2)  # Tu turno read two hours after the acceptance: an interacted buyer's card shows one hour after


class FirstMessageBuyerPathTests(FirstMessagePathBase):
    """Phase 3 end to end (BAR-20): the note at invite time and the first message on acceptance, with the journey, Tu
    turno and the funnel after each step. The variants 1–10 of the brief; the case modules (test_primer_mensaje_comprador,
    test_nota_invitacion) grade the same functions against their baselines."""

    def write(self,contact,note=None,message=None):
        if note is not None:self.texts[('invite-note',contact.display_name)]=note
        if message is not None:self.texts[('buyer-message',contact.display_name)]=message

    def test_chosen_warmed_invited_with_a_note_accepts_draft_lead_card_done_message_1(self):
        # 1–3. Chosen, followed, one warm-up comment and her answer to it: warmed, ready to be invited.
        ana=self.answered('ana-acme','Ana Acme')
        self.write(ana,note=case_text('nota_invitacion','N1'),message=case_text('primer_mensaje_comprador','M1'))

        # 4. The plan holds her while her note is decided; the autopilot's step drafts it (one paid call, the note's
        # methodology, the warm-up comment as context), the lead reviews it with its five questions.
        with self.lead():
            held=self.plan(timezone.now())
        self.assertEqual((held['nota_en_espera'],self.invite_proposed(ana)),(1,False))
        invite=self.invite(ana)
        self.assertEqual(invite.state,'confirmed',invite.risks)
        note=self.drafts_of(ana,'nota')[-1]
        self.assertEqual((note.state,note.proposal_id,note.text,note.anchor['tipo']),('enviado',invite.pk,case_text('nota_invitacion','N1'),'respondio_comentario'))
        call=next(c for c in self.calls if c['purpose']=='invite-note')
        for uid in operador.INVITE_NOTE_UNITS:self.assertIn(uid,call['context'])
        self.assertEqual(call['inputs']['hechos'][0]['comentario_del_equipo'],WARM_1)
        review=next(c for c in self.jev if c['purpose']=='lead-review-note')
        self.assertEqual(set(review['questions'])-{'orientacion'},{'nota_hecho','nota_aceptar','nota_generica','nota_pitch','nota_inventa'})
        self.assertEqual(note.review['course_methodology'],'nota_invitacion')
        self.assertEqual(self.sent_invitation(ana)['message'],case_text('nota_invitacion','N1'))
        journey=self.journey(ana)
        self.assertEqual((journey.step,journey.invite_note),('invitado',True))
        self.assertEqual(journey.touches.get(kind='borrador').detail,{'tipo':'nota','numero':1,'intento':1,'resultado':'listo','por':''})

        # 5. She accepts. The same cycle prepares the first message (she interacted): the methodology's units, her facts,
        # the lead's six DM questions; the card waits an hour.
        ana=self.accepted(ana)
        self.prepare()
        message=self.drafts_of(ana,'mensaje')[-1]
        accepted=self.journey(ana).accepted_at
        self.assertEqual((message.state,message.show_at),('listo',accepted+timedelta(hours=1)))
        context=next(c['context'] for c in self.calls if c['purpose']=='buyer-message')
        for uid in operador.FIRST_MESSAGE_UNITS:self.assertIn(uid,context)
        review=next(c for c in self.jev if c['purpose']=='lead-review-message')
        self.assertLessEqual({'dm_toque','dm_puente','dm_pregunta','dm_un_tema','dm_en_persona','dm_pitch','inventa'},set(review['questions']))
        self.assertEqual(review['state']['primer_mensaje']['texto'],case_text('primer_mensaje_comprador','M1'))
        self.assertEqual(message.review['course_methodology'],'primer_mensaje')
        self.assertEqual(self.cards_of(ana),[])  # never the minute she accepted

        # 6. Tu turno an hour later: one «Mensaje sugerido» card, Gustavo's three buttons, what it cites.
        cards=self.cards_of(ana,LATER)
        self.assertEqual(len(cards),1)
        card=cards[0]
        self.assertEqual([a['label'] for a in card['actions']],['Abrir su perfil','Hecho, le escribí','No escribirle'])
        self.assertEqual((card['message']['text'],card['message']['origin'],card['message']['comment']),
                         (case_text('primer_mensaje_comprador','M1'),'recorrido',BUYER_POST))
        self.assertEqual((card['message']['comment_label'],card['message']['reply']),('Su post',WARM_1))
        drafts=self.funnel()['borradores']
        self.assertEqual((drafts['pendientes'],drafts['enviados'],drafts['recorrido']['pendientes']),(1,0,1))

        # 7. «Hecho, le escribí»: mensaje_1, from the journey's draft. The team never sent a private message.
        self.close(card,'enviado')
        journey=self.journey(ana)
        sent=journey.touches.get(kind='mensaje')
        self.assertEqual((sent.direction,sent.detail),('saliente',{'fuente':'recorrido','numero':1}))
        self.assertEqual((journey.step,journey.messages_sent,journey.first_message_at),('mensaje_1',1,sent.at))
        self.assertEqual([k for k,_ in self.kinds(ana)],['elegido','seguir','comentario','respondio_comentario','borrador','invitacion',
                                                         'acepto_invitacion','borrador','mensaje'])
        self.assertEqual(self.cards_of(ana,LATER),[])
        self.assertIn('Mensaje sugerido para Ana Acme',[r['title'] for r in self.turn_payload(LATER)['recent']])

        # The funnel: received a message, the drafts sent, the invitation with a note.
        funnel=self.funnel()
        total=self.stages(funnel['acumulado'])
        self.assertEqual({k:total[k] for k in ('invitados','aceptaron','recibieron_mensaje')},{'invitados':1,'aceptaron':1,'recibieron_mensaje':1})
        drafts=funnel['borradores']
        self.assertEqual((drafts['pendientes'],drafts['enviados'],drafts['enviados_pct']),(0,1,100.0))
        self.assertEqual({k:drafts['recorrido'][k] for k in ('preparados','pendientes','enviados')},{'preparados':1,'pendientes':0,'enviados':1})
        self.assertEqual({k:drafts['notas'][k] for k in ('preparadas','con_invitacion','enviadas')},{'preparadas':1,'con_invitacion':1,'enviadas':1})
        self.assertEqual((funnel['comparaciones']['nota']['con_nota']['personas'],funnel['comparaciones']['nota']['sin_nota']['personas']),(1,0))
        self.assertEqual((self.fake.state['writes'],self.messages_sent()),(3,0))  # follow, comment, invitation
        self.assertEqual(comprador.rebuild()['toques_nuevos'],0)
        self.assertFalse(AuditEvent.objects.filter(action__in=['buyer.record_failed','buyer.draft_stopped']).exists())

    def turn_payload(self,later=timedelta(0)):
        from rest_framework.test import APIClient
        client=APIClient();client.force_authenticate(self.gustavo)
        with patch('django.utils.timezone.now',return_value=timezone.now()+later):
            return client.get('/api/v1/tu-turno').json()

    def test_1_she_interacted_the_draft_is_prepared_in_the_cycle_that_sees_the_acceptance(self):
        ana=self.answered('ana-acme','Ana Acme')
        self.write(ana,message=case_text('primer_mensaje_comprador','M1'))
        self.invite(ana)
        ana=self.accepted(ana)
        self.assertEqual(self.journey(ana).next_at,self.journey(ana).accepted_at)  # due at the acceptance
        self.prepare()
        self.assertEqual(self.drafts_of(ana,'mensaje')[-1].state,'listo')
        self.assertEqual(len(self.cards_of(ana,LATER)),1)

    def test_2_no_interaction_a_touch_after_accepting_then_the_draft_n_days_later(self):
        ana,second=self.two_comments('ana-acme','Ana Acme')
        self.write(ana,note=case_text('nota_invitacion','N1'),message=case_text('primer_mensaje_comprador','M2'))
        self.invite(ana)
        ana=self.accepted(ana)
        accepted=self.journey(ana).accepted_at
        self.assertEqual(self.journey(ana).next_at,accepted+timedelta(days=21))  # no touch yet: at the latest in 21 days
        self.prepare()
        self.assertEqual(self.drafts_of(ana,'mensaje'),[])
        self.assertEqual([j.pk for j in calentamiento.second_touch(self.account)],[self.journey(ana).pk])
        # Calentamiento 2: a new post of hers is read and commented with the warm-up rules.
        self.their_new_post(ana,AFTER_POST,suffix='p3',hours_ago=1)
        self.observe(later=True)
        self.a_day_later(second)
        third=self.autopilot_comment(WARM_3)
        self.assertEqual(third.state,'confirmed',third.risks)
        journey=self.journey(ana)
        touch=journey.touches.filter(kind='comentario',at__gt=accepted).get()
        self.assertEqual(journey.next_at,accepted+timedelta(days=7))
        self.assertEqual(calentamiento.second_touch(self.account),[])
        self.prepare(accepted+timedelta(days=6,hours=23))
        self.assertEqual(self.drafts_of(ana,'mensaje'),[])  # never before the N days
        self.prepare(accepted+timedelta(days=7,minutes=1))
        message=self.drafts_of(ana,'mensaje')[-1]
        self.assertEqual((message.state,message.anchor['tipo']),('listo','comentario_en_su_post'))
        self.assertEqual(message.anchor['comentario_del_equipo'],WARM_3)  # the newest commented post first
        self.assertEqual(len(self.cards_of(ana,timedelta(days=7,hours=1))),1)
        self.assertGreater(message.decided_at,touch.at)
        self.assertEqual([k for k,_ in self.kinds(ana)][-3:],['acepto_invitacion','comentario','borrador'])

    def test_3_nothing_real_to_cite_no_message_no_paid_call_and_the_reason_kept(self):
        ana,at=self.without_posts('ana-acme','Ana Acme')
        self.write(ana,message=case_text('primer_mensaje_comprador','M2'))
        self.invite(ana,at)
        ana=self.accepted(ana)
        # The job itself, asked before the step decides (a stale queue): nothing real, so no paid call either.
        from team_backend import mensajes_comprador
        with self.writer(),self.lead():
            result=mensajes_comprador.prepare(self.bot,{'contact':str(ana.pk),'kind':'mensaje'})
        self.assertEqual((result['decision'],result['stopped_by']),('sin_borrador','hecho'))
        later=self.journey(ana).accepted_at+timedelta(days=7,minutes=1)  # the route without posts: no touch to wait for
        self.prepare(later)
        draft=self.drafts_of(ana,'mensaje')[-1]
        self.assertEqual((draft.state,draft.stopped_by,draft.text),('sin_borrador','hecho',''))
        self.assertFalse(self.paid(ana,'buyer-message'))
        self.assertEqual(self.cards_of(ana,timedelta(days=8)),[])
        journey=self.journey(ana)
        self.assertEqual(journey.touches.filter(kind='borrador').order_by('at').last().detail['por'],'hecho')
        self.assertIsNone(journey.next_at)
        stopped=self.funnel()['borradores']['recorrido']['parados']
        self.assertEqual(stopped['hecho'],1)

    def test_4_a_draft_the_rules_or_the_lead_reject_is_discarded_audited_and_never_shown(self):
        rules=self.answered('ana-acme','Ana Acme')
        lead=self.answered('bea-acme','Bea Acme')
        self.write(rules,message=case_text('primer_mensaje_comprador','M4'))
        self.write(lead,message=case_text('primer_mensaje_comprador','M5'))
        for contact in (rules,lead):self.invite(contact)
        rules=self.accepted(rules);lead=self.accepted(lead)
        self.prepare()
        self.assertEqual([c['purpose'] for c in self.calls if c['inputs']['persona']['nombre']=='Ana Acme' and c['purpose']=='buyer-message'],
                         ['buyer-message','buyer-message'])  # one redraft
        for contact,by in ((rules,'reglas'),(lead,'juez')):
            draft=self.drafts_of(contact,'mensaje')[-1]
            self.assertEqual((draft.state,draft.stopped_by),('descartado',by))
            self.assertEqual(self.stopped(contact,'mensaje'),by)
            self.assertEqual(self.cards_of(contact,LATER),[])
        self.assertEqual(self.drafts_of(lead,'mensaje')[-1].review['decision'],'discard')
        self.assertEqual(self.funnel()['borradores']['pendientes'],0)

    def test_5_no_escribirle_is_a_definitive_exit(self):
        ana=self.answered('ana-acme','Ana Acme')
        self.write(ana,message=case_text('primer_mensaje_comprador','M1'))
        self.invite(ana)
        ana=self.accepted(ana)
        self.prepare()
        card=self.cards_of(ana,LATER)[0]
        response=self.human.post(next(a for a in card['actions'] if a['label']=='No escribirle')['endpoint'],
                                 {'how':'no','note':'Ya la conozco por otro lado.'},format='json')
        self.assertEqual(response.status_code,200,response.content)
        self.assertEqual(response.json()['closed']['how'],'no')
        journey=self.journey(ana)
        self.assertEqual((journey.step,journey.exit_reason,journey.first_message_at),('salio','descartado_por_gustavo',None))
        self.assertEqual(journey.touches.get(kind='no_escribirle').detail,{'fuente':'recorrido','numero':1})
        self.assertEqual(self.drafts_of(ana,'mensaje')[-1].state,'no_enviado')
        self.assertEqual(self.cards_of(ana,LATER),[])
        self.assertEqual(self.prepare(),0)  # nothing more for her
        funnel=self.funnel()
        self.assertEqual((funnel['salidas']['descartado_por_gustavo'],self.stages(funnel['acumulado'])['recibieron_mensaje']),(1,0))
        self.assertEqual(funnel['borradores']['no_enviados'],1)
        again=self.human.post(card['actions'][1]['endpoint'],{'how':'enviado'},format='json')  # already closed: same answer
        self.assertEqual((again.status_code,again.json()['closed']['how']),(200,'no'))

    def test_6_without_notes_left_this_month_the_invitation_goes_without_one(self):
        ana=self.answered('ana-acme','Ana Acme')
        self.write(ana,note=case_text('nota_invitacion','N1'))
        with patch.dict(os.environ,{'LINKEDIN_INVITE_NOTE_MONTHLY_LIMIT':'0'}):
            invite=self.invite(ana)
        self.assertEqual(invite.state,'confirmed')
        self.assertEqual(self.sent_invitation(ana)['message'],'')
        self.assertFalse(self.paid(ana,'invite-note'))
        self.assertEqual(self.stopped(ana,'nota'),'cupo')
        self.assertIs(self.journey(ana).invite_note,False)
        notes=self.funnel()['borradores']['notas']
        self.assertEqual((notes['enviadas'],notes['parados']['cupo']),(0,1))

    def test_7_a_person_gustavo_confirmed_is_invited_with_the_note_the_lead_reviewed(self):
        ana=self.answered('ana-acme','Ana Acme',note='Ana, your answer on the spreadsheet pilot stayed with me. Would love to connect.')
        red.confirm_fit(self.gustavo,ana.pk)
        self.write(ana,note=case_text('nota_invitacion','N1'))
        invite=self.invite(ana,auto=True)
        self.assertEqual(invite.state,'confirmed',invite.risks)
        self.assertEqual(self.sent_invitation(ana)['message'],case_text('nota_invitacion','N1'))  # the buyer's note, not the classifier's
        self.assertFalse(AuditEvent.objects.filter(action='network.note_omitted').exists())
        self.assertEqual(ActionProposal.objects.filter(capability='RED-02',state='approved').count(),0)

    def test_9_a_conversation_on_his_post_and_a_journey_one_card_and_no_second_message(self):
        _,pid=self.publish()
        sara=self.fake.seed_person('sara-seis','Sara Seis',headline='Founder & CEO at Seis',location='Austin, Texas')
        root=self.fake.comment_on_own_post(pid,sara['id'],QUESTION,at=timezone.now()-timedelta(minutes=20))
        self.read();first=PostComment.objects.get()
        self.propose(first,draft());self.execute_proposal(ActionProposal.objects.get(capability='INT-04'))
        contact=Contact.objects.get(pk=first.contact_id)
        checked={'state':'ok','checked_at':timezone.now().isoformat()}
        Contact.objects.filter(pk=contact.pk).update(classification={'fit':True,'role':'comprador','confidence':0.9,'region':'us','stage_check':checked},
                                                     stage='followed',followed_at=timezone.now()-timedelta(hours=1),location='Austin, Texas')
        self.fake.comment_on_own_post(pid,sara['id'],FOLLOW_UP,thread=root,at=timezone.now()+timedelta(seconds=5))
        self.rescan()
        second=PostComment.objects.get(text=FOLLOW_UP)
        self.propose(second,draft(reply=CLOSING,dm_opener='Hi Sara, I kept thinking about your golden datasets going stale. How are you versioning them now?'))
        with self.lead():self.execute_proposal(ActionProposal.objects.get(capability='INT-04',comment=second))
        contact=Contact.objects.get(pk=contact.pk)
        self.write(contact,message=case_text('primer_mensaje_comprador','M1'))
        self.invite(contact)
        contact=self.accepted(contact)
        self.prepare()
        cards=self.cards_of(contact,LATER)
        self.assertEqual(len(cards),1)
        self.assertNotEqual(cards[0]['message'].get('origin'),'recorrido')  # RSP-07's card wins
        self.assertEqual(self.drafts_of(contact,'mensaje'),[])
        self.close(cards[0],'enviado')
        self.prepare(timezone.now()+timedelta(days=22))
        self.assertEqual(self.drafts_of(contact,'mensaje'),[])  # she got her first message: no second one
        self.assertEqual(self.cards_of(contact,timedelta(days=22)),[])
        self.assertEqual(self.journey(contact).step,'mensaje_1')

    def test_9_a_conversation_after_the_journey_card_hides_it_and_its_message_retires_the_draft(self):
        ana=self.answered('ana-acme','Ana Acme')
        self.write(ana,message=case_text('primer_mensaje_comprador','M1'))
        self.invite(ana)
        ana=self.accepted(ana)
        self.prepare()
        self.assertEqual([c['message']['origin'] for c in self.cards_of(ana,LATER)],['recorrido'])
        # Before Gustavo writes, she talks with the team on his post and the closing reply drafts RSP-07's message.
        _,pid=self.publish()
        root=self.fake.comment_on_own_post(pid,ana.provider_user_id,QUESTION,at=timezone.now()-timedelta(minutes=20))
        self.read();first=PostComment.objects.get()
        self.assertEqual(first.contact_id,ana.pk)
        self.propose(first,draft());self.execute_proposal(ActionProposal.objects.get(capability='INT-04'))
        self.fake.comment_on_own_post(pid,ana.provider_user_id,FOLLOW_UP,thread=root,at=timezone.now()+timedelta(seconds=5))
        self.rescan()
        second=PostComment.objects.get(text=FOLLOW_UP)
        self.propose(second,draft(reply=CLOSING,dm_opener='Hi Ana, I kept thinking about your golden datasets going stale. How are you versioning them now?'))
        with self.lead():self.execute_proposal(ActionProposal.objects.get(capability='INT-04',comment=second))
        cards=self.cards_of(ana,LATER)
        self.assertEqual(len(cards),1)  # one card per person: the conversation's wins
        self.assertNotEqual(cards[0]['message'].get('origin'),'recorrido')
        self.close(cards[0],'enviado')
        self.prepare()
        self.assertEqual(self.drafts_of(ana,'mensaje')[-1].state,'reemplazado')  # she got her first message: the draft retires
        self.assertEqual(self.cards_of(ana,LATER),[])
        self.assertEqual(self.journey(ana).messages_sent,1)

    def test_10_peers_and_recommenders_keep_todays_rule(self):
        par=self.contact('par-luis','Luis Par',stage='followed',followed_hours=49)
        rec=self.contact('rec-rosa','Rosa Rec',stage='followed',followed_hours=47)
        for row,role in ((par,'par'),(rec,'recomendador')):
            Contact.objects.filter(pk=row.pk).update(classification=dict(row.classification,role=role))
        self.assertEqual(self.prepare(),0)
        with self.lead():summary=self.plan(timezone.now())  # the switch and the lead on: nobody is held for a note
        self.assertEqual(summary.get('nota_en_espera',0),0)
        self.assertTrue(self.invite_proposed(par))
        self.assertFalse(self.invite_proposed(rec))
        self.assertFalse(ActionProposal.objects.get(contact=par,capability='RED-02').payload.get('note'))
        self.assertFalse(BuyerJourney.objects.exists())
        self.assertFalse(Job.objects.filter(kind='prepare_buyer_draft').exists())
        self.assertEqual(self.calls,[])


class FirstMessageSwitchOffPathTests(FirstMessagePathBase):
    def test_8_with_the_switch_off_the_path_is_todays_and_rsp07_intact(self):
        with patch.dict(os.environ,{'BUYER_FIRST_MESSAGE_ENABLED':'false'}):
            ana=self.answered('ana-acme','Ana Acme',note='Ana, your answer on the spreadsheet pilot stayed with me. Would love to connect.')
            self.texts[('invite-note','Ana Acme')]=case_text('nota_invitacion','N1')
            self.texts[('buyer-message','Ana Acme')]=case_text('primer_mensaje_comprador','M1')
            with self.lead():summary=self.plan(timezone.now())
            self.assertNotIn('nota_en_espera',{k for k,v in summary.items() if v})
            invite=self.invite(ana,auto=True)
            self.assertEqual(invite.payload.get('note'),'Ana, your answer on the spreadsheet pilot stayed with me. Would love to connect.')
            ana=self.accepted(ana)
            self.assertIsNone(self.journey(ana).next_at)  # nothing due after the acceptance, as before phase 3
            self.assertEqual(self.prepare(timezone.now()+timedelta(days=22)),0)
            self.assertEqual(calentamiento.second_touch(self.account),[])
            self.assertEqual((self.calls,self.cards_of(ana,timedelta(days=22))),([],[]))
            self.assertFalse(Job.objects.filter(kind='prepare_buyer_draft').exists())
            from team_backend.models import BuyerDraft
            self.assertFalse(BuyerDraft.objects.exists())
            drafts=self.funnel()['borradores']
            self.assertEqual((drafts['recorrido']['preparados'],drafts['notas']['preparadas']),(0,0))
