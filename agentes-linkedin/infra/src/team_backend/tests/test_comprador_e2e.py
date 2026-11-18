"""The buyer's path as it runs today, end to end (comprador.py, phase 1 of docs/plan-outbound.md): the production
functions (red.discover/classify/plan/sync, the operator, desenlaces_captura, respuestas) drive a synthetic buyer with
the fake connector and patched providers, and each step checks the journey, its touches and the funnel.

BuyerPathBase is the harness: one method per step of the path, each going through production code. Phases 2–6 add
their steps here (read the buyer's posts and comment, the first message on acceptance, messages 2–4, the non-posting
route, the classified reply and the meeting) and extend the walk; nothing in it writes the journey directly."""
import json
import os
import uuid
from contextlib import ExitStack, contextmanager
from datetime import timedelta
from unittest.mock import patch
from django.utils import timezone
from team_backend import autopiloto, calentamiento, comprador, conversaciones, evaluaciones, jobs, nivel_comprador, operador, red, respuestas
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
                return {'text':json.dumps({'verdict':'confirmado','evidence':'La fuente dice que levantó una ronda semilla.',
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
    def step_choose(self,slug='ana-acme',name='Ana Acme',location='Austin, Texas',note='',headline='Founder & CEO at Acme'):
        """discover_network finds the person in a search; classify_contacts classifies her and check_buyer_stages checks
        her stage on the web."""
        person=self.fake.seed_person(slug,name,headline=headline,search='founder pre-seed',location=location)
        self.job('discover_network')
        stop=self.providers(note=note)
        try:
            job=self.job('classify_contacts')
            self.step_check()
        finally:stop()
        self.assertEqual(job.state,'complete',job.error)
        return Contact.objects.get(account=self.account,provider_user_id=person['id'])

    def step_check(self):
        """check_buyer_stages, as the autopilot queues it while a buyer waits for her web check: one check a run, with its
        own budget apart from the classification (18/11/2026)."""
        for _ in range(5):
            if not red.stage_pending(self.account,timezone.now()):return
            job=self.job('check_buyer_stages')
            self.assertEqual(job.state,'complete',job.error)

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

    def test_a_buyer_the_web_has_not_confirmed_walks_the_path_por_confirmar(self):
        # BAR-24 (Gustavo, 17/11/2026): nothing found on the web yet is not a «no». She is chosen por_confirmar, followed,
        # invited and accepted like the others, and her journey keeps the level and score she entered with.
        from team_backend import research
        self.fake.seed_person('beto-acme','Beto Acme',headline='Founder at Acme',search='founder pre-seed',location='Austin, Texas')
        self.job('discover_network')
        nothing=research.ResearchResult('q','unavailable','2026-11-12T00:00:00+00:00',usage={'model':'claude-sonnet-5-5'})
        with self.classifier({'Beto Acme':(True,0.9)}),patch('team_backend.research.research',return_value=nothing):
            self.job('classify_contacts')
            self.assertEqual(self.job('check_buyer_stages').result_status,'etapas:0/1')
        beto=Contact.objects.get(display_name='Beto Acme')
        entered=beto.classification['buyer']
        self.assertEqual((beto.stage,beto.classification['stage_check']['state'],entered['level']),('fit','pending','por_confirmar'))
        journey=self.journey(beto)
        self.assertEqual((journey.step,journey.entry_level,journey.entry_score,journey.entry_score_version),
                         ('elegido','por_confirmar',entered['score'],nivel_comprador.SCORE_VERSION))
        self.assertEqual(self.step_follow(beto).state,'confirmed')

        # The next day the web finds the seed round: her level and score go up; what she entered with stays.
        stop=self.providers()
        try:red.check_stages(self.gustavo,self.account,now=timezone.now()+timedelta(days=1))
        finally:stop()
        beto.refresh_from_db()
        self.assertEqual((beto.classification['stage_check']['state'],beto.classification['buyer']['level']),('ok','confirmado'))
        self.assertGreater(beto.classification['buyer']['score'],entered['score'])
        self.assertEqual(self.step_invite(beto).state,'confirmed')
        beto=self.step_accept(beto)
        journey=self.journey(beto)
        self.assertEqual((beto.stage,journey.step,journey.entry_level,journey.entry_score),('connected','acepto','por_confirmar',entered['score']))

        entry=self.funnel()['entrada_comprador']
        self.assertEqual(entry['por_nivel']['por_confirmar'],
                         {'elegidos':1,'seguidos':1,'calentados':0,'invitados':1,'aceptaron':1,'respondieron':0})
        self.assertEqual(entry['por_nivel']['confirmado']['elegidos'],0)
        self.assertEqual(entry['por_puntaje'][nivel_comprador.band(entered['score'])]['aceptaron'],1)

    def test_a_buyer_from_latin_america_is_chosen_after_the_us_ones(self):
        # Gustavo, 17/11/2026: «podríamos prospectarlos al inicio; queremos ir hacia USA pero no los descartamos de una».
        self.fake.seed_person('caro-mx','Caro MX',headline='Founder & CEO at Acme',search='founder pre-seed',location='Mexico City')
        ana=self.step_choose()
        caro=Contact.objects.get(display_name='Caro MX')
        self.assertTrue(caro.classification['fit'])
        self.assertEqual((self.journey(caro).entry_level,self.journey(ana).entry_level),('confirmado','confirmado'))
        self.assertLess(caro.classification['buyer']['score'],ana.classification['buyer']['score'])  # market: latam 8, objetivo 20
        self.assertEqual([c.display_name for c in red.prioritized([caro,ana])],['Ana Acme','Caro MX'])


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
    def chosen_and_followed(self,slug='ana-acme',name='Ana Acme',note='',headline='Founder & CEO at Acme',location='Austin, Texas'):
        contact=self.step_choose(slug,name,location=location,note=note,headline=headline)
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

    def test_a_buyer_from_latin_america_warms_up_like_one_from_the_united_states(self):
        # BAR-24: Latin America comes after the United States in the order, never off the path. With the switch on she
        # is read, commented twice after the author wait and invited without a note, like Ana.
        caro=self.chosen_and_followed('caro-mx','Caro MX',location='Mexico City')
        journey=self.journey(caro)
        follow=journey.touches.get(kind='seguir')
        self.assertEqual((journey.step,journey.next_at,journey.entry_level),('calentando',follow.at+timedelta(days=14),'confirmado'))
        self.warm_up(caro)
        self.plan()
        invite=self.approve_open(caro,'RED-02')
        self.assertEqual((invite.state,Contact.objects.get(pk=caro.pk).stage),('confirmed','invited'))
        journey=self.journey(caro)
        self.assertEqual((journey.step,journey.warm_comments,journey.comments_before_invite),('invitado',2,2))
        entry=self.funnel()['entrada_comprador']['por_nivel']['confirmado']
        self.assertEqual({k:entry[k] for k in ('elegidos','seguidos','calentados','invitados')},
                         {'elegidos':1,'seguidos':1,'calentados':1,'invitados':1})

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


def judge_sequence(number,text):
    """Jev simulado para los seguimientos (fase 4): el M2 nombra el mismo dolor; el M3 pregunta por la persona indicada sin
    volver a contar el dolor; el M4 cierra sin rogar ni pedir; ninguno vende."""
    low=(text or '').lower()
    sells=any(k in low for k in ('my team','we help','a call','our services'))
    pain=sum(k in low for k in ('spreadsheet','report','copies','copying'))
    out={'seg_pitch':0.9 if sells else 0.05,'inventa':0.05}
    if number==2:out.update(seg_mismo_dolor=0.9 if pain else 0.2,seg_repite=0.1,seg_disculpa=0.05)
    elif number==3:out.update(seg_persona_indicada=0.9 if 'right person' in low or 'persona indicada' in low else 0.1,
                              seg_repite_dolor=0.8 if pain>=2 else 0.1)
    else:out.update(seg_cierre=0.9,seg_ruega=0.05,seg_pide=0.05)
    return out


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
            elif purpose=='lead-review-sequence':
                follow=state.get('seguimiento') or {}
                scores=judge_sequence(follow.get('numero'),follow.get('texto'))
            elif purpose=='buyer-reply-classify':scores=judge_reply_type((state.get('ultimo_mensaje') or {}).get('texto'))
            elif purpose=='lead-review-reply':scores=judge_reply_draft(state.get('respuesta') or {})
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
            number=(data.get('seguimiento') or {}).get('numero')
            text=self.texts.get((purpose,name,number) if purpose=='buyer-sequence' else (purpose,name),'')
            out={'decision':'write' if text else 'none','language':'en','anchor':facts[0]['id'] if facts else '',
                 'rationale':'Retoma su hecho y le pregunta algo fácil.','claims_needing_evidence':[],'risks':[]}
            if purpose=='invite-note':
                out.update(note=text,citations=['LI-09-M002-K06','LI-09-V008-K04','LI-09-M002-K01','LI-03-M006-K01'])
            elif purpose=='buyer-sequence':
                out.update(message=text,citations=list(evaluaciones.COURSE_CASES['secuencia_mensajes']['units']))
            elif purpose=='buyer-reply':  # phase 6: the reply to what she wrote, with what is missing and whom she named
                extra=self.texts.get(('buyer-reply-extra',name),{})
                out.update(message=text,faltan=list(extra.get('faltan',[])),referido_nombre=extra.get('referido_nombre',''),
                           citations=list(evaluaciones.COURSE_CASES['respuesta_comprador']['units']))
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

    def answered(self,slug,name,note='',headline='Founder & CEO at Acme'):
        """Chosen, followed, one warm-up comment and her answer to it: warmed and ready to be invited (an accelerator)."""
        contact=self.chosen_and_followed(slug,name,note=note,headline=headline)
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

    def without_posts(self,slug,name,headline='Founder & CEO at Acme'):
        """Chosen and followed, two reads without a post: the route without posts, ready at 14 days. Returns the moment."""
        contact=self.chosen_and_followed(slug,name,headline=headline)
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


class BuyerReadWindowTests(FirstMessagePathBase):
    """READ_WINDOW (#133) also covers the buyer's periodic work (merge of 17/11/2026): reading her posts
    (calentamiento.read_posts, the observe only for buyers) and preparing her drafts (autopiloto._buyer_drafts) happen only
    inside the window, like every other background read; an observe Gustavo asks for at night reads only the referents."""
    WINDOW={'READ_WINDOW':'07:00-21:00','OPERATOR_TIMEZONE':'America/Bogota'}

    def local(self,hour,days=0):
        """Today (or `days` later) at `hour`, Bogotá time, never in the past."""
        from zoneinfo import ZoneInfo
        moment=timezone.now().astimezone(ZoneInfo('America/Bogota')).replace(hour=hour,minute=0,second=0,microsecond=0)+timedelta(days=days)
        return moment if moment>timezone.now() else moment+timedelta(days=1)

    def test_her_posts_are_read_only_inside_the_window(self):
        ana=self.chosen_and_followed()
        self.their_new_post(ana)
        night=self.local(23);morning=night+timedelta(hours=11)
        connector=operador.get_connector(self.account)
        with patch.dict(os.environ,self.WINDOW):
            self.assertEqual(autopiloto._observe(self.bot,self.account,night),0)  # nothing queued at night
            with patch('django.utils.timezone.now',return_value=night):
                out=calentamiento.read_posts(self.account,connector,night)  # an observe asked for at night
            self.assertEqual((out['personas'],out.get('fuera_de_ventana')),(0,True))
            self.assertFalse(AuditEvent.objects.filter(action=calentamiento.READ_ACTION).exists())
            self.assertEqual(autopiloto._observe(self.bot,self.account,morning),1)  # the observe only for buyers
            self.assertTrue(Job.objects.get(kind='observe').params['solo_compradores'])
            with patch('django.utils.timezone.now',return_value=morning):
                out=calentamiento.read_posts(self.account,connector,morning)
        self.assertEqual((out['personas'],out.get('fuera_de_ventana')),(1,None))

    def test_her_drafts_are_prepared_only_inside_the_window(self):
        ana=self.answered('ana-acme','Ana Acme')
        self.texts[('buyer-message','Ana Acme')]=case_text('primer_mensaje_comprador','M1')
        self.invite(ana)
        ana=self.accepted(ana)
        night=self.local(23)
        with patch.dict(os.environ,self.WINDOW):
            self.assertEqual(self.prepare(night),0)
            self.assertEqual((self.drafts_of(ana,'mensaje'),Job.objects.filter(kind='prepare_buyer_draft',params__kind='mensaje').count()),([],0))
            self.prepare(night+timedelta(hours=11))  # 10:00 the next morning
        self.assertEqual(self.drafts_of(ana,'mensaje')[-1].state,'listo')


# --------------------------------------------------------------------------- phase 4: messages 2–4 (BAR-21)

def sequence_text(variant,number):
    """The case's follow-up `number` for `variant`; the flow's when the variant does not change it."""
    case=evaluaciones.COURSE_CASES['secuencia_mensajes']['input']
    key=f'mensaje_{number}'
    return case.get(variant,{}).get(key) or case['flujo'][key]


class SequencePathBase(FirstMessagePathBase):
    """The path with BUYER_SEQUENCE_ENABLED (phase 4): after «Hecho, le escribí» on the first message the team prepares
    messages 2–4 (BUYER_SEQUENCE_DAYS after each «Hecho»), which Gustavo copies and sends himself, and everything stops
    when she replies (read in the inbox, INBOX_ENABLED). A simulated clock moves the days. The fake connector's chats are
    LinkedIn: what Gustavo sends by hand after each «Hecho» and what she answers; the team never writes one. Before phase
    4 the steps find nothing to do, which is what the baseline measures."""
    def setUp(self):
        super().setUp()
        env=patch.dict(os.environ,{'BUYER_SEQUENCE_ENABLED':'true','INBOX_ENABLED':'true','BUYER_POSTS_READ_DAILY_LIMIT':'20'})
        env.start();self.addCleanup(env.stop)
        self.start=timezone.now()+LATER  # the first «Hecho»: two hours after the acceptance
        self.chats={}

    @contextmanager
    def clock(self,moment):
        """The world at `moment`: timezone.now and the models' default dates (Django binds those when models load)."""
        from django.apps import apps
        with ExitStack() as stack:
            stack.enter_context(patch('django.utils.timezone.now',return_value=moment))
            for model in apps.get_app_config('team_backend').get_models():
                for field in model._meta.fields:
                    if getattr(field.default,'__module__','')=='django.utils.timezone':
                        stack.enter_context(patch.object(field,'_get_default',new=lambda:timezone.now()))
            yield moment

    def gustavo_api(self):
        from rest_framework.test import APIClient
        client=APIClient();client.force_authenticate(self.gustavo)  # a session would not outlive the clock
        return client

    # -- LinkedIn, by hand
    def chat(self,contact):
        if contact.pk not in self.chats:self.chats[contact.pk]=self.fake.seed_chat(contact.provider_user_id,[])
        return self.chats[contact.pk]

    def by_hand(self,contact,text,at):
        """Gustavo sends it himself from LinkedIn after «Hecho, le escribí»."""
        self.fake.add_message(self.chat(contact),text,True,at)

    def she_replies(self,contact,text,at):
        self.fake.add_message(self.chat(contact),text,False,at)

    # -- Tu turno at a moment
    def turn_at(self,at):
        with self.clock(at):
            response=self.gustavo_api().get('/api/v1/tu-turno')
        self.assertEqual(response.status_code,200,response.content)
        return response.json()

    def cards_at(self,contact,at):
        return [c for c in self.turn_at(at)['tasks']['mensajes'] if ((c.get('message') or {}).get('person') or {}).get('id')==str(contact.pk)]

    def close_at(self,card,how,at,note=''):
        """Gustavo closes the card at `at`: «Hecho, le escribí» (and he sends it on LinkedIn) or «No escribirle»."""
        action=next(a for a in card['actions'] if (a.get('body') or {}).get('how')==how)
        with self.clock(at):
            response=self.gustavo_api().post(action['endpoint'],dict({'how':how},**({'note':note} if note else {})),format='json')
        self.assertEqual(response.status_code,200,response.content)
        if how=='enviado':self.by_hand(Contact.objects.get(pk=card['message']['person']['id']),card['message']['text'],at)
        return response.json()

    # -- steps
    def messaged(self,slug,name,at=None,headline='Founder & CEO at Acme'):
        """Chosen, warmed, invited, accepted and «Hecho, le escribí» on the first message of the journey (phase 3) at `at`."""
        contact=self.answered(slug,name,headline=headline)
        self.texts[('buyer-message',name)]=case_text('primer_mensaje_comprador','M1')
        self.invite(contact)
        contact=self.accepted(contact)
        self.prepare()
        cards=self.cards_of(contact,LATER)
        self.assertEqual(len(cards),1)
        self.close_at(cards[0],'enviado',at or self.start)
        return Contact.objects.get(pk=contact.pk)

    def follow_ups(self,contact,variant='flujo'):
        """Claude simulado escribe, para esta persona, los seguimientos 2–4 de la variante."""
        for number in (2,3,4):self.texts[('buyer-sequence',contact.display_name,number)]=sequence_text(variant,number)

    def cycle(self,at):
        """One autopilot cycle at `at`: the inbox read (when on) and the buyer-draft step with its jobs, tick after tick
        (one paid draft each) until it queues nothing: a few minutes of the real autopilot."""
        with self.clock(at):
            if conversaciones.enabled():
                with self.lead():self.job('read_inbox')
            self.prepare(at,rounds=30)
        return at

    # -- reads
    def numbers(self,contact):
        """The follow-ups (2–4) the team decided for her in this attempt: prepared or stopped."""
        attempt=self.journey(contact).attempt
        return sorted(d.number for d in self.drafts_of(contact,'mensaje') if d.number>1 and d.decided_at and d.attempt==attempt)

    def draft(self,contact,number):
        return next((d for d in self.drafts_of(contact,'mensaje') if d.number==number),None)

    def sequence_cards(self,contact,at):
        """Her follow-up cards in Tu turno at `at` (the first message's card is not one)."""
        first=self.draft(contact,1)
        return [c for c in self.cards_at(contact,at) if not first or c['id']!=f'dm:{first.pk}']



MINUTE=timedelta(minutes=1);HOUR=timedelta(hours=1);DAY=timedelta(days=1)


class SequenceBuyerPathTests(SequencePathBase):
    """BAR-21 de punta a punta con las funciones de producción y el reloj simulado: M1 → M2 a los 4 días del «Hecho» →
    M3 a los 5 → M4 a los 7 → sin respuesta, descanso de 90 días; y sus variantes."""

    def send_follow_up(self,contact,number,at,sent):
        """The follow-up `number` is drafted when due (BUYER_SEQUENCE_DAYS after `sent`), reviewed and shown; Gustavo
        sends it an hour later. Returns that moment."""
        due=sent+timedelta(days={2:4,3:5,4:7}[number])
        self.cycle(due-MINUTE)
        self.assertNotIn(number,self.numbers(contact))  # never a minute early
        self.cycle(due+MINUTE)
        cards=self.sequence_cards(contact,due+HOUR)
        self.assertEqual(len(cards),1,number)
        self.close_at(cards[0],'enviado',due+HOUR)
        return due+HOUR

    def rested_after_a_stopped_follow_up(self,slug,name):
        """M2 stopped by the fixed rules (it apologises): BUYER_SEQUENCE_REST_AFTER_DAYS after M1 she rests."""
        contact=self.messaged(slug,name);self.follow_ups(contact,'S6')
        self.cycle(self.start+4*DAY+MINUTE)
        self.assertEqual(self.draft(contact,2).stopped_by,'reglas')
        rest=self.cycle(self.start+7*DAY+MINUTE)
        self.assertEqual((self.journey(contact).step,self.journey(contact).rest_reason),('descanso','secuencia_sin_respuesta'))
        return contact,rest

    def test_the_whole_sequence_until_the_rest(self):
        ana=self.messaged('seq-e2e-ana','Ana Ruta');self.follow_ups(ana)
        writes=self.fake.state['writes'];sent=self.start
        self.assertEqual(self.journey(ana).next_at,self.start+4*DAY)  # comprador.next_at: M2 is due 4 days after «Hecho»
        for number in (2,3,4):
            due=sent+timedelta(days={2:4,3:5,4:7}[number])
            self.cycle(due-MINUTE)
            self.assertNotIn(number,self.numbers(ana))
            self.cycle(due+MINUTE)
            draft=self.draft(ana,number)
            self.assertEqual((draft.state,draft.stopped_by,draft.attempt),('listo','',1))
            self.assertEqual(draft.text,sequence_text('flujo',number))
            self.assertEqual(draft.review['decision'],'approve')  # the lead with its questions per number
            review=next(j for j in reversed(self.jev) if j['purpose']=='lead-review-sequence')
            self.assertEqual(review['state']['seguimiento']['numero'],number)
            self.assertTrue({f'seg_{q}' for q in {2:('mismo_dolor','repite','disculpa'),3:('persona_indicada','repite_dolor'),
                                                  4:('cierre','ruega','pide')}[number]}<=set(review['questions']))
            # The drafter got what Gustavo already sent her and the sequence's units, whole.
            call=next(c for c in reversed(self.calls) if c['purpose']=='buyer-sequence')
            self.assertEqual([m['numero'] for m in call['inputs']['seguimiento']['anteriores']],list(range(1,number)))
            self.assertIn('LI-09-V014-K02',call['context'])
            cards=self.sequence_cards(ana,due+HOUR)
            self.assertEqual(len(cards),1)
            card=cards[0]
            self.assertEqual((card['title'],card['message']['text_label'],card['message']['text']),
                             (f'Seguimiento {number} de 4 para Ana Ruta',f'Seguimiento {number} de 4',draft.text))
            self.assertEqual([a['label'] for a in card['actions']],['Abrir su perfil','Hecho, le escribí','No escribirle'])
            self.assertEqual(card['actions'][1]['endpoint'],f'/api/v1/respuestas/{draft.pk}/mensaje')
            sent=due+HOUR;self.close_at(card,'enviado',sent)
            journey=self.journey(ana)
            self.assertEqual((journey.step,journey.messages_sent),(f'mensaje_{number}',number))
            self.assertEqual(self.sequence_cards(ana,sent+MINUTE),[])
        # Seven days after message 4 without a reply: she rests 90 days and stays a connection.
        self.assertEqual(self.journey(ana).next_at,sent+7*DAY)
        self.cycle(sent+7*DAY-MINUTE)
        self.assertEqual(self.journey(ana).step,'mensaje_4')
        rest=self.cycle(sent+7*DAY+MINUTE)
        journey=self.journey(ana)
        self.assertEqual((journey.step,journey.rest_reason,round((journey.rest_until-rest)/DAY)),('descanso','secuencia_sin_respuesta',90))
        self.assertEqual(Contact.objects.get(pk=ana.pk).stage,'connected')
        self.assertTrue(AuditEvent.objects.filter(action='buyer.sequence_rested',target=str(ana.pk)).exists())
        self.assertEqual(self.numbers(ana),[2,3,4])
        self.assertEqual(self.fake.state['writes'],writes)  # the team never writes a message (INB-08)
        sequence=self.funnel()['secuencia']
        self.assertEqual(sequence['recibieron'],{'1':1,'2':1,'3':1,'4':1})
        self.assertEqual(sequence['descansan'],1)
        drafts=self.funnel()['borradores']['por_numero']
        self.assertEqual([drafts[n]['enviados'] for n in '1234'],[1,1,1,1])

    def test_1_a_reply_after_message_2_stops_everything(self):
        handled=[]
        bea=self.messaged('seq-e2e-bea','Bea Para');self.follow_ups(bea)
        sent2=self.send_follow_up(bea,2,None,self.start)
        with patch('team_backend.secuencia_comprador.REPLY_HANDLERS',[lambda journey,at,after:handled.append((journey.contact_id,after))]):
            self.she_replies(bea,'Good timing, the weekly numbers are a mess.',sent2+2*DAY)
            self.cycle(sent2+2*DAY+HOUR)
            self.cycle(sent2+5*DAY+MINUTE)  # message 3 would be due
            self.cycle(sent2+12*DAY+MINUTE)
        journey=self.journey(bea)
        self.assertEqual(journey.step,'respondio')
        self.assertEqual(self.numbers(bea),[2])
        self.assertIn(('respondio_mensaje','entrante'),self.kinds(bea))
        event=AuditEvent.objects.get(action='buyer.sequence_replied',target=str(bea.pk))
        self.assertEqual((event.metadata['numero'],event.metadata['cancelados']),(2,[]))
        self.assertEqual(handled,[(bea.pk,2)])  # phase 6's hook, once
        self.assertEqual(self.funnel()['secuencia']['respondieron_tras'],{'1':0,'2':1,'3':0,'4':0})

    def test_1b_a_reply_with_message_3_waiting_cancels_it_and_hides_its_card(self):
        bea=self.messaged('seq-e2e-bea2','Bea Espera');self.follow_ups(bea)
        sent2=self.send_follow_up(bea,2,None,self.start)
        self.cycle(sent2+5*DAY+MINUTE)
        self.assertEqual(self.draft(bea,3).state,'listo')
        self.she_replies(bea,'Sorry for the delay: yes, the reports.',sent2+5*DAY+HOUR)
        # The next inbox read sees her reply: the card is gone and message 3 is cancelled.
        self.cycle(sent2+5*DAY+2*HOUR)
        self.assertEqual(self.sequence_cards(bea,sent2+5*DAY+2*HOUR),[])
        self.assertEqual((self.draft(bea,3).state,self.journey(bea).step),('cancelado','respondio'))
        with self.clock(sent2+5*DAY+3*HOUR):  # «Hecho» on the cancelled card: it is no longer in Tu turno
            response=self.gustavo_api().post(f'/api/v1/respuestas/{self.draft(bea,3).pk}/mensaje',{'how':'enviado'},format='json')
        self.assertEqual(response.status_code,409,response.content)
        self.assertEqual(self.journey(bea).messages_sent,2)

    def test_2_message_2_not_sent_means_no_message_3(self):
        cris=self.messaged('seq-e2e-cris','Cris Nunca');self.follow_ups(cris)
        self.cycle(self.start+4*DAY+MINUTE)
        self.assertEqual(self.draft(cris,2).state,'listo')
        for days in (9,10,16,30):self.cycle(self.start+days*DAY+MINUTE)
        self.assertEqual(self.numbers(cris),[2])
        self.assertEqual((self.journey(cris).step,self.draft(cris,2).state),('mensaje_1','listo'))

    def test_3_with_the_inbox_off_nothing_is_prepared_and_it_says_so(self):
        dani=self.messaged('seq-e2e-dani','Dani Sin');self.follow_ups(dani)
        with patch.dict(os.environ,{'INBOX_ENABLED':'false'}):
            # Two cycles of the same local day (the notice is once a local day): the clock starts from the real hour, so
            # an hour later may already be tomorrow (it failed when run at 21:xx in Bogotá).
            first=self.start+4*DAY+MINUTE;midnight=operador.period_starts(first)[0]+DAY
            self.cycle(first);self.cycle(min(first+HOUR,first+(midnight-first)/2))
            self.assertEqual(self.numbers(dani),[])
            self.assertEqual(Job.objects.filter(kind='prepare_buyer_draft',params__number=2).count(),0)  # nothing paid
            events=AuditEvent.objects.filter(action='buyer.sequence_waiting')
            self.assertEqual(events.count(),1)  # once a day
            self.assertIn('INBOX_ENABLED=false',events.get().metadata['motivo'])
            self.assertEqual(self.journey(dani).step,'mensaje_1')  # never «no respondió»
        # A stale read (no read of the chat list in the last 3 h) waits too; a fresh one unblocks it.
        with self.clock(self.start+4*DAY+5*HOUR):
            with self.writer(),self.lead():autopiloto._buyer_drafts(self.bot,self.account,timezone.now())
        self.assertEqual(self.numbers(dani),[])
        self.cycle(self.start+4*DAY+6*HOUR)
        self.assertEqual(self.numbers(dani),[2])

    def test_4_a_follow_up_the_rules_or_the_lead_reject_never_shows(self):
        eva=self.messaged('seq-e2e-eva','Eva Regla');self.follow_ups(eva,'S6')
        hugo=self.messaged('seq-e2e-hugo','Hugo Lider');self.follow_ups(hugo,'S9')
        self.cycle(self.start+4*DAY+MINUTE)
        self.assertEqual((self.draft(eva,2).state,self.draft(eva,2).stopped_by),('descartado','reglas'))
        self.assertIn('Mensaje 2 que se disculpa por escribir de nuevo',self.draft(eva,2).issues)
        self.assertEqual(self.sequence_cards(eva,self.start+4*DAY+HOUR),[])
        sent2=self.start+4*DAY+HOUR;self.close_at(self.sequence_cards(hugo,sent2)[0],'enviado',sent2)
        self.cycle(sent2+5*DAY+MINUTE)
        self.assertEqual((self.draft(hugo,3).state,self.draft(hugo,3).stopped_by),('descartado','juez'))
        self.assertEqual(self.sequence_cards(hugo,sent2+5*DAY+HOUR),[])
        stopped=AuditEvent.objects.filter(action='buyer.draft_stopped',target=str(hugo.pk),metadata__numero=3)
        self.assertEqual(stopped.get().metadata['por'],'juez')
        # No message 4 after a stopped one; 7 days after the last «Hecho» she rests.
        self.cycle(sent2+7*DAY+MINUTE)
        self.assertEqual((self.numbers(hugo),self.journey(hugo).step),([2,3],'descanso'))

    def test_5_no_escribirle_on_message_3_is_a_definitive_exit(self):
        ines=self.messaged('seq-e2e-ines','Ines Fuera');self.follow_ups(ines)
        sent2=self.send_follow_up(ines,2,None,self.start)
        self.cycle(sent2+5*DAY+MINUTE)
        self.close_at(self.sequence_cards(ines,sent2+5*DAY+HOUR)[0],'no',sent2+5*DAY+HOUR,note='No insistir.')
        self.cycle(sent2+12*DAY+MINUTE);self.cycle(sent2+30*DAY)
        journey=self.journey(ines)
        self.assertEqual((journey.step,journey.exit_reason,self.numbers(ines)),('salio','descartado_por_gustavo',[2,3]))
        self.assertEqual(self.draft(ines,3).state,'no_enviado')

    def test_6_with_the_switch_off_the_journey_ends_at_the_first_message(self):
        with patch.dict(os.environ,{'BUYER_SEQUENCE_ENABLED':'false'}):
            fer=self.messaged('seq-e2e-fer','Fer Apagado');self.follow_ups(fer)
            journey=self.journey(fer)
            self.assertEqual((journey.step,journey.next_at),('mensaje_1',None))
            for days in (4,9,16,30):self.cycle(self.start+days*DAY+MINUTE)
            self.assertEqual((self.numbers(fer),self.journey(fer).step),([],'mensaje_1'))
            self.assertFalse(AuditEvent.objects.filter(action__startswith='buyer.sequence').exists())
            self.assertFalse(any(c['purpose']=='buyer-sequence' for c in self.calls))
            self.assertFalse(self.funnel()['secuencia']['activa'])

    def test_7_a_signal_during_the_rest_wakes_her_with_a_new_first_message(self):
        gil,rest=self.rested_after_a_stopped_follow_up('seq-e2e-gil','Gil Despierta')
        self.cycle(rest+10*DAY)
        self.assertEqual(self.journey(gil).step,'descanso')
        comprador.record(self.journey(gil),BuyerTouch.Kind.REACTED_POST,at=rest+20*DAY,key='prueba:reaccion')
        self.cycle(rest+20*DAY+HOUR)
        journey=self.journey(gil)
        self.assertEqual((journey.attempt,journey.step),(2,'acepto'))
        self.assertTrue(journey.touches.filter(kind='reintento',detail__por_senal=True).exists())
        self.cycle(rest+20*DAY+2*HOUR)
        first=next(d for d in self.drafts_of(gil,'mensaje') if d.attempt==2)
        self.assertEqual((first.number,first.state),(1,'listo'))  # phase 3 again, for the new attempt

    def test_8_deadlines_run_from_hecho_not_from_the_draft(self):
        hal=self.messaged('seq-e2e-hal','Hal Tarde');self.follow_ups(hal)
        drafted=self.cycle(self.start+4*DAY+MINUTE)
        self.assertEqual(self.numbers(hal),[2])
        sent2=drafted+2*DAY  # Gustavo sends it two days later
        self.assertEqual(self.sequence_cards(hal,sent2),[])  # no inbox read in 24 h: her reply could be there, no card
        self.cycle(sent2-HOUR)
        self.close_at(self.sequence_cards(hal,sent2)[0],'enviado',sent2)
        self.assertEqual(self.journey(hal).next_at,sent2+5*DAY)
        self.cycle(drafted+5*DAY+MINUTE)
        self.assertEqual(self.numbers(hal),[2])
        self.cycle(sent2+5*DAY+MINUTE)
        self.assertEqual(self.numbers(hal),[2,3])

    def test_a_weekend_waits_for_monday(self):
        ivo=self.messaged('seq-e2e-ivo','Ivo Lunes');self.follow_ups(ivo)
        with patch('team_backend.operador.is_weekend',return_value=True):
            self.cycle(self.start+4*DAY+MINUTE)
        self.assertEqual(self.numbers(ivo),[])
        self.cycle(self.start+6*DAY)
        self.assertEqual(self.numbers(ivo),[2])

    def test_her_reply_in_the_chat_list_stops_it_before_her_thread_is_read(self):
        jo=self.messaged('seq-e2e-jo','Jo Lista');self.follow_ups(jo)
        sent2=self.send_follow_up(jo,2,None,self.start)
        self.she_replies(jo,'Interesting, tell me more.',sent2+DAY)
        with patch.dict(os.environ,{'INBOX_THREADS_PER_RUN':'0'}):  # the list sees it; no thread is read this run
            self.cycle(sent2+DAY+HOUR)
        journey=self.journey(jo)
        stand_in=journey.touches.get(kind='respondio_mensaje')
        self.assertTrue(stand_in.key.startswith('lista:'))
        self.assertEqual(journey.step,'respondio')
        self.cycle(sent2+DAY+2*HOUR)  # the thread is read: its message replaces the stand-in
        self.assertEqual([t.key.split(':')[0] for t in comprador.current(self.journey(jo).touches.filter(kind='respondio_mensaje'))],
                         ['conversacion'])
        self.assertEqual(AuditEvent.objects.filter(action='buyer.sequence_replied',target=str(jo.pk)).count(),1)

    def test_an_overdue_follow_up_is_not_written_late(self):
        with patch.dict(os.environ,{'BUYER_SEQUENCE_ENABLED':'false'}):
            kai=self.messaged('seq-e2e-kai','Kai Viejo');self.follow_ups(kai)
        self.cycle(self.start+20*DAY)  # the switch turned on 20 days after the first message
        self.assertEqual(self.numbers(kai),[])
        self.assertEqual((self.journey(kai).step,self.journey(kai).rest_reason),('descanso','secuencia_sin_respuesta'))

    def test_phase_6_links_a_referral_to_message_3(self):
        from team_backend import secuencia_comprador
        lu=self.messaged('seq-e2e-lu','Lu Refiere');self.follow_ups(lu)
        mia=self.messaged('seq-e2e-mia','Mia Referida')
        self.assertIsNone(secuencia_comprador.referral_asked(self.journey(lu)))
        with self.assertRaises(ValueError):secuencia_comprador.link_referral(self.journey(mia),self.journey(lu))
        sent2=self.send_follow_up(lu,2,None,self.start)
        sent3=self.send_follow_up(lu,3,None,sent2)
        asked=secuencia_comprador.referral_asked(self.journey(lu))
        self.assertEqual((asked['texto'],asked['borrador']),(sequence_text('flujo',3),str(self.draft(lu,3).pk)))
        touch=secuencia_comprador.link_referral(self.journey(mia),self.journey(lu),at=sent3+DAY,note='Me dijo que hablara con ella.')
        self.assertEqual((touch.kind,touch.direction,touch.detail['de']),('referido','estado',str(lu.pk)))
        self.assertEqual(self.journey(mia).referred_by_id,self.journey(lu).pk)
        secuencia_comprador.link_referral(self.journey(mia),self.journey(lu))  # once
        self.assertEqual(self.journey(mia).touches.filter(kind='referido').count(),1)
        with self.assertRaises(ValueError):secuencia_comprador.link_referral(self.journey(lu),self.journey(lu))


# --------------------------------------------------------------------------- phase 5: the buyer who does not post (BAR-22)

SEED_URL='https://news.example/acme-seed'
HIRING_URL='https://jobs.example/acme-account-executive'
SIGNAL_NOTE='Ana, saw Acme raised its seed round to turn the pilot into a real product. Connecting to follow how it goes.'
SIGNAL_MESSAGE=('Hi Ana, saw Acme raised its seed round to turn the pilot into a real product. Which manual step of the pilot '
                'are you automating first?')
TALK_MESSAGE=('Hi Ana, I talked with Bruno from your team about moving the pilot off spreadsheets. Which report does Acme want '
              'to automate first?')


class NoPostsPathBase(SequencePathBase):
    """The path with BUYER_NO_POSTS_ROUTE_ENABLED (phase 5, sin_posts.py) on top of phases 2–4: the buyer who does not
    post, his bridge (a colleague who does) and the retries. The fake connector's search by company name returns the
    people seeded with `search=<company>`; the web check may cite buying signals (self.stage_signals)."""
    def setUp(self):
        super().setUp()
        env=patch.dict(os.environ,{'BUYER_NO_POSTS_ROUTE_ENABLED':'true'})
        env.start();self.addCleanup(env.stop)
        self.stage_signals=[];self.web_keys=[];self.stage_verdict='confirmado'
        self.human=self.gustavo_api()  # the clock moves weeks ahead: a session would not outlive it

    def signal(self,kind='ronda',days=10,url=SEED_URL,evidence='Acme raised a seed round to turn its pilot into a product.'):
        return {'tipo':kind,'fecha':(timezone.now()-timedelta(days=days)).date().isoformat(),'source_url':url,'evidencia':evidence}

    def providers(self,fit=True,note=''):
        """BuyerPathBase's, with the web check citing self.stage_signals (each one with its source among the findings) and
        answering self.stage_verdict."""
        from team_backend import research
        def claude(system,message,**kwargs):
            if kwargs['purpose']=='network-stage':
                return {'text':json.dumps({'verdict':self.stage_verdict,'evidence':'La fuente dice que levantó una ronda semilla.',
                                           'source_urls':[SEED_URL],'senales':list(self.stage_signals)}),'model':'claude-sonnet-5-5'}
            out=[{'id':p['id'],'fit':fit,'role':'comprador','modality':'projectapp','affinity':'desconocida','reason':'Founder con producto.',
                  'confidence':0.9,'course_citations':['LI-03-M005-K06'],'invitation_note':'','note_reason':''}
                 for p in json.loads(message)['people']]
            return {'text':json.dumps({'contacts':out}),'model':kwargs.get('model'),'estimated_usd':0.001,'request_id':'req_net'}
        def web(request):
            self.web_keys.append(request.key)
            urls=[SEED_URL]+[s['source_url'] for s in self.stage_signals if s['source_url']!=SEED_URL]
            sources=tuple(research.Source(f's{i}',url,'Acme','Acme news','2026-11-12T00:00:00+00:00') for i,url in enumerate(urls,1))
            return research.ResearchResult(request.public_question,'complete','2026-11-12T00:00:00+00:00',
                                           (research.Finding('Acme raised a seed round.',tuple(s.id for s in sources)),),sources,
                                           usage={'model':'claude-sonnet-5-5'})
        claude_patch=patch('knowledge.providers.claude',side_effect=claude);web_patch=patch('team_backend.research.research',side_effect=web)
        claude_patch.start();web_patch.start()
        return lambda:(claude_patch.stop(),web_patch.stop())

    # -- LinkedIn
    def candidate(self,slug,name,headline,company='Acme',posts=True,distance='SECOND_DEGREE'):
        """Someone the search by `company` finds; with `posts`, a recent post of theirs."""
        user=self.fake.seed_person(slug,name,headline=headline,search=company,distance=distance)
        if posts:
            pid=f'activity:{slug}-p1'
            self.fake.state['posts'][pid]={'id':pid,'share_url':'https://www.linkedin.com/feed/update/urn:li:'+pid,'text':BUYER_POST,
                'created_at':(timezone.now()-timedelta(hours=2)).isoformat(),'author':user,'comments_counter':0,
                'reactions_counter':[],'reposts_counter':0,'user_reacted':False,'is_repost':False}
            self.fake.state['comments'][pid]=[]
        return user

    # -- reads
    def bridge(self,buyer):
        return Contact.objects.filter(bridge_for__contact=buyer).first()

    def bridge_states(self,buyer):
        return [(t.detail['estado'],t.detail.get('motivo')) for t in self.journey(buyer).touches.filter(kind='puente').order_by('at','created_at')]

    def searched(self):
        return [c['keywords'] for c in self.fake.state.get('search_calls',[])]

    def reads(self):
        """The reads phase 5 may spend: its searches (and the «search» cap), profile reads (and the shared cap) and the
        posts reads of the buyers' cap made to see whether a candidate posts."""
        network=lambda kind:AuditEvent.objects.filter(action='network.read',metadata__kind=kind).count()
        return {'busquedas':AuditEvent.objects.filter(action='buyer.bridge_search').count(),'search':network('search'),
                'perfil':network('profile'),'perfil_compartido':AuditEvent.objects.filter(action='operator.profile_read',
                                                                                            metadata__purpose='buyer_bridge').count(),
                'posts_candidatos':AuditEvent.objects.filter(action=calentamiento.READ_ACTION,metadata__contact__startswith='puente:').count()}

    def angles(self,contact):
        return [t.detail.get('tipo') for t in self.journey(contact).touches.filter(kind='reintento').order_by('at')]


class NoPostsBuyerPathTests(NoPostsPathBase):
    """BAR-22 end to end with the production functions: the route without posts, the bridge, the note by signal, the
    first message and the retries."""

    def test_1_no_posts_invited_at_14_days_with_a_note_and_a_first_message_on_her_signal(self):
        self.stage_signals=[self.signal()]
        ana,at=self.without_posts('ana-acme','Ana Acme')
        self.assertEqual((self.journey(ana).route,len(calentamiento.buying_signals(Contact.objects.get(pk=ana.pk)))),('sin_posts',1))
        # She has a sourced signal to cite: no bridge is asked for. «Comment where she comments»: the connector cannot
        # read her comments, so nothing is commented or invented; the funnel says so.
        self.plan()
        self.assertEqual(self.bridge_states(ana),[])
        self.assertFalse(self.journey(ana).touches.filter(kind__in=['comentario','visita']).exists())
        route=self.funnel()['ruta_sin_posts']
        self.assertEqual((route['donde_comenta']['disponible'],route['visitas']['disponible']),(False,False))
        # 13 days: not yet. 14 days: invited with one of the month's notes, citing her signal.
        self.texts[('invite-note','Ana Acme')]=SIGNAL_NOTE;self.texts[('buyer-message','Ana Acme')]=SIGNAL_MESSAGE
        follow=self.journey(ana).touches.get(kind='seguir').at
        self.prepare(follow+timedelta(days=13));self.plan(follow+timedelta(days=13))
        self.assertFalse(self.invite_proposed(ana))
        with self.clock(at):invite=self.invite(ana,at)  # the note is drafted and sent that day
        self.assertEqual(invite.state,'confirmed',invite.risks)
        note=self.drafts_of(ana,'nota')[-1]
        self.assertEqual((note.state,note.anchor['tipo'],note.anchor['fuente'],note.text),('enviado','senal_de_compra',SEED_URL,SIGNAL_NOTE))
        self.assertEqual(self.sent_invitation(ana)['message'],SIGNAL_NOTE)
        # She accepts; on this route there is no touch to wait for: the message a week later, on the same signal.
        ana=self.accepted(ana)
        accepted=self.journey(ana).accepted_at
        self.assertEqual(self.journey(ana).next_at,accepted+timedelta(days=7))
        self.prepare(accepted+timedelta(days=7,minutes=1))
        message=self.drafts_of(ana,'mensaje')[-1]
        self.assertEqual((message.state,message.anchor['tipo'],message.anchor['fuente'],message.text),
                         ('listo','senal_de_compra',SEED_URL,SIGNAL_MESSAGE))
        cards=self.cards_of(ana,timedelta(days=7,hours=2))
        self.assertEqual([c['message']['comment_label'] for c in cards],['Señal de compra de su empresa'])
        self.assertEqual((self.messages_sent(),self.searched().count('Acme')),(0,0))

    def test_1b_the_note_by_signal_waits_behind_the_buyers_warmed_with_comments(self):
        self.stage_signals=[self.signal()]
        ana,at=self.without_posts('ana-acme','Ana Acme')
        bea=self.chosen_and_followed('bea-globex','Bea Globex',headline='Founder & CEO at Globex')
        self.their_new_post(bea);self.observe()
        self.assertEqual(self.autopilot_comment(WARM_1).state,'confirmed')  # Bea: warmed with one comment, not ready yet
        self.texts[('invite-note','Ana Acme')]=SIGNAL_NOTE
        with patch('team_backend.red.note_room',return_value=1):  # one note left this month
            self.prepare(at)
        self.assertEqual(self.stopped(ana,'nota'),'cupo')
        self.assertFalse(self.paid(ana,'invite-note'))
        self.assertIn('calentó con comentarios',self.drafts_of(ana,'nota')[-1].reason)

    def test_2_no_signal_her_bridge_is_found_warmed_accepts_and_her_message_cites_the_real_interaction(self):
        from team_backend import mensajes_comprador
        ana,at=self.without_posts('ana-acme','Ana Acme')
        # Nothing real to cite: the sweep asks for her bridge right away.
        self.plan()
        self.assertEqual(self.bridge_states(ana),[('pedido','sin_ancla')])
        # The search by her company: same role (CEO, like her), another company, then her co-founder who posts.
        self.candidate('carla-acme','Carla Acme','CEO at Acme')
        self.candidate('dora-globex','Dora Globex','CTO at Globex Acme Partners Inc',posts=True)
        self.candidate('bruno-acme','Bruno Acme','Co-founder & CTO at Acme')
        before=self.reads()
        self.observe()
        bruno=self.bridge(ana)
        self.assertEqual((bruno.display_name,bruno.classification['role'],bruno.stage,bruno.bridge_for_id),
                         ('Bruno Acme','puente','fit',self.journey(ana).pk))
        self.assertEqual(bruno.classification['puente']['cargo'],'cto')
        self.assertEqual(self.bridge_states(ana),[('pedido','sin_ancla'),('encontrado','busqueda')])
        after=self.reads()
        self.assertEqual({k:after[k]-before[k] for k in after},{'busquedas':1,'search':1,'perfil':0,'perfil_compartido':0,'posts_candidatos':1})
        self.assertFalse(BuyerJourney.objects.filter(contact=bruno).exists())  # its own role, never a second buyer
        # Followed, warmed with two comments (warm-up rules, the bridge's own purpose) and invited without a note.
        self.plan()
        self.assertEqual(self.approve_open(bruno,'RED-01').state,'confirmed')
        first=self.autopilot_comment(WARM_1)
        self.assertEqual((first.state,first.post.author_provider_id),('confirmed',bruno.provider_user_id))
        self.assertIn('Colega de un posible cliente',self.drafts[-1]['inputs']['calentamiento']['para_que'])
        self.plan()
        self.assertFalse(self.invite_proposed(bruno))  # one comment is not the warm-up
        self.their_new_post(bruno,NEXT_POST,suffix='p2',hours_ago=1)
        self.observe(later=True)
        self.a_day_later(first)
        self.assertEqual(self.autopilot_comment(WARM_2).state,'confirmed')
        self.plan()
        self.assertEqual(self.approve_open(bruno,'RED-02').state,'confirmed')
        self.assertNotIn('note',ActionProposal.objects.get(contact=bruno,capability='RED-02').payload)
        # He accepts: a signal of hers (senal_puente); her heat goes up; not a signal she gave before the invitation.
        self.assertEqual(comprador.temperature(ana,weigh=True)['peso'],0)
        self.step_accept(bruno)
        journey=self.journey(ana)
        signal=journey.touches.get(kind='senal_puente')
        self.assertEqual((signal.direction,signal.detail['tipo'],signal.detail['interaccion']),('entrante','acepto',False))
        self.assertEqual((comprador.temperature(ana,weigh=True)['peso'],journey.signal_before_invite),(1.0,False))
        # Only an acceptance: a text that says Gustavo talked with him breaks a fixed rule.
        facts=mensajes_comprador.anchors(Contact.objects.get(pk=ana.pk))
        self.assertEqual([(f['tipo'],f['interaccion']) for f in facts],[('puente',False)])
        self.assertIn('Dice que habló con alguien sin una interacción real que lo respalde',
                      mensajes_comprador.message_text_issues(TALK_MESSAGE,facts,facts[0]['id']))
        # He answers the team's comment: a real interaction.
        self.step_their_answer(bruno,first)
        self.assertEqual(sorted(t.detail['tipo'] for t in self.journey(ana).touches.filter(kind='senal_puente')),['acepto','respondio_comentario'])
        # She is invited at 14 days (no note text: it goes without one), accepts, and her first message cites the interaction.
        self.texts[('buyer-message','Ana Acme')]=TALK_MESSAGE
        self.assertEqual(self.invite(ana,at).state,'confirmed')
        ana=self.accepted(ana)
        accepted=self.journey(ana).accepted_at
        self.prepare(accepted+timedelta(days=7,minutes=1))
        message=self.drafts_of(ana,'mensaje')[-1]
        self.assertEqual((message.state,message.text,message.anchor['tipo'],message.anchor['interaccion']),('listo',TALK_MESSAGE,'puente',True))
        call=next(c for c in self.calls if c['purpose']=='buyer-message')
        self.assertIn('Un hecho de tipo "puente"',call['system'])
        cards=self.cards_of(ana,timedelta(days=7,hours=2))
        self.assertEqual([c['message']['comment_label'] for c in cards],['Su colega (el puente)'])
        # Never the same to the second person of a company: a comment on his post that says her message again.
        post=ObservedPost.objects.filter(author_provider_id=bruno.provider_user_id).first()
        repeated=ActionProposal(account=self.account,capability='INT-03',post=post,payload={'text':TALK_MESSAGE},source='human')
        self.assertIn('Comentario que repite lo que el equipo le escribió a Ana Acme, de su misma empresa',autopiloto.comment_text_issues(repeated))
        fresh=ActionProposal(account=self.account,capability='INT-03',post=post,payload={'text':WARM_3},source='human')
        self.assertFalse([i for i in autopiloto.comment_text_issues(fresh) if 'repite' in i])
        # The funnel: the route with a bridge, the bridge followed, invited and accepted, one buyer with its interaction.
        route=self.funnel()['ruta_sin_posts']
        self.assertEqual((route['comparacion']['con_puente']['personas'],route['comparacion']['sin_puente']['personas']),(1,0))
        self.assertEqual({k:route['puentes'][k] for k in ('pedidos','busquedas','encontrados','seguidos','invitados','aceptaron',
                                                         'compradores_con_senal_del_puente','compradores_con_interaccion_del_puente')},
                         {'pedidos':1,'busquedas':1,'encontrados':1,'seguidos':1,'invitados':1,'aceptaron':1,
                          'compradores_con_senal_del_puente':1,'compradores_con_interaccion_del_puente':1})
        self.assertEqual(comprador.rebuild()['toques_nuevos'],0)
        self.assertEqual(self.messages_sent(),0)
        self.assertFalse(AuditEvent.objects.filter(action__in=['buyer.record_failed','buyer.warmup_failed']).exists())

    def test_3_never_more_than_two_people_per_company_nor_two_with_the_same_role(self):
        with patch.dict(os.environ,{'BUYER_NO_POSTS_ROUTE_ENABLED':'false'}):  # both chosen before any bridge is asked for
            ana,_=self.without_posts('ana-acme','Ana Acme')
            eva,_=self.without_posts('eva-acme','Eva Acme',headline='CTO at Acme')  # a second buyer of the same company
        self.candidate('bruno-acme','Bruno Acme','Co-founder & COO at Acme')
        self.plan();self.observe()
        # Ana and Eva are already two people of Acme: no third one, not even a search.
        for buyer in (ana,eva):self.assertEqual(self.bridge_states(buyer),[('pedido','sin_ancla'),('sin_puente','empresa_completa')])
        self.assertNotIn('Acme',self.searched())
        # Another company where the search only finds people with his own role (CEO) or of another company.
        gil,_=self.without_posts('gil-globex','Gil Globex',headline='Founder & CEO at Globex')
        self.candidate('carl-globex','Carl Globex','Chief Executive Officer, Globex',company='Globex')
        self.candidate('dan-initech','Dan Initech','CTO at Initech',company='Globex')
        self.plan();self.observe()
        self.assertEqual(self.bridge_states(gil),[('pedido','sin_ancla'),('sin_puente','mismo_cargo')])
        self.assertEqual(self.searched().count('Globex'),1)
        self.assertFalse(Contact.objects.filter(bridge_for__isnull=False).exists())
        self.assertEqual(self.funnel()['ruta_sin_posts']['puentes']['sin_puente'],{'empresa_completa':2,'mismo_cargo':1})

    def test_4_nothing_real_to_cite_and_no_bridge_no_message(self):
        ana,at=self.without_posts('ana-acme','Ana Acme')
        self.plan();self.observe()  # asked for, searched: nobody at Acme
        self.assertEqual(self.bridge_states(ana),[('pedido','sin_ancla'),('sin_puente','sin_resultados')])
        self.texts[('buyer-message','Ana Acme')]=SIGNAL_MESSAGE
        self.assertEqual(self.invite(ana,at).state,'confirmed')
        self.assertEqual(self.stopped(ana,'nota'),'hecho')
        ana=self.accepted(ana)
        self.prepare(self.journey(ana).accepted_at+timedelta(days=7,minutes=1))
        draft=self.drafts_of(ana,'mensaje')[-1]
        self.assertEqual((draft.state,draft.stopped_by,draft.text),('sin_borrador','hecho',''))
        self.assertFalse(self.paid(ana,'buyer-message'))
        self.assertEqual(self.cards_of(ana,timedelta(days=8)),[])

    def test_5_invited_with_one_comment_and_not_accepted_in_21_days_rests(self):
        ana=self.answered('ana-acme','Ana Acme')  # one comment and her answer: invited without the second
        self.assertEqual(self.invite(ana).state,'confirmed')
        journey=self.journey(ana)
        self.assertEqual((journey.comments_before_invite,journey.route),(1,'comentarios'))
        invited=journey.touches.get(kind='invitacion').at
        self.plan(now=invited+timedelta(days=20))
        self.assertEqual(self.journey(ana).step,'invitado')
        later=invited+timedelta(days=21,hours=1)
        summary=self.plan(now=later)
        self.assertEqual(summary['calentamiento']['descanso'],1)
        journey=self.journey(ana)
        self.assertEqual((journey.step,journey.rest_reason,journey.rest_until),('descanso','invitacion_no_aceptada',later+timedelta(days=60)))

    def test_6_each_retry_changes_its_angle_and_the_third_attempt_rests_a_year(self):
        self.stage_signals=[self.signal()]
        ana,at=self.without_posts('ana-acme','Ana Acme')
        with patch.dict(os.environ,{'NETWORK_STAGE_CHECK':'false'}):  # the re-check has its own test (7)
            self.plan()
            self.assertEqual(self.bridge_states(ana),[])  # a signal to cite: no bridge yet
            self.assertEqual(self.invite(ana,at).state,'confirmed')  # no note text: invited without one
            invited=self.journey(ana).touches.get(kind='invitacion').at
            # 21 days without accepting: on this route the bridge goes first; nobody at Acme posts, so she rests.
            due=invited+timedelta(days=21,hours=1)
            summary=self.plan(now=due)
            self.assertEqual((summary['calentamiento']['descanso'],summary['calentamiento']['puente_antes_del_descanso']),(0,1))
            self.assertEqual(self.bridge_states(ana),[('pedido','ruta_sin_resultado')])
            self.observe()
            self.plan(now=due+HOUR)
            journey=self.journey(ana)
            self.assertEqual((journey.step,journey.attempt,journey.rest_until),('descanso',1,due+HOUR+timedelta(days=60)))
            self.assertEqual(self.bridge_states(ana),[('sin_puente','sin_resultados'),('pedido','ruta_sin_resultado')])
            # The end of the rest: attempt 2 with her signal (no text cited it yet).
            end=journey.rest_until+MINUTE
            self.plan(now=end)
            journey=self.journey(ana)
            self.assertEqual((journey.step,journey.attempt,self.angles(ana)),('calentando',2,['senal_nueva']))
            self.assertEqual(journey.touches.get(kind='reintento').detail['senal'],SEED_URL)
            # Her invitation is still pending (never sent again): 21 days from this attempt's start she rests again,
            # without a second search for the bridge.
            self.plan(now=end+timedelta(days=21,hours=1))
            journey=self.journey(ana)
            self.assertEqual((journey.step,journey.attempt),('descanso',2))
            self.assertEqual(self.searched().count('Acme'),1)
            # Attempt 3: another angle (another topic; the signal and the bridge were used), and then a year.
            end=journey.rest_until+MINUTE
            self.plan(now=end)
            self.assertEqual((self.journey(ana).attempt,self.angles(ana)),(3,['senal_nueva','otro_tema']))
            last=end+timedelta(days=21,hours=1)
            self.plan(now=last)
            journey=self.journey(ana)
            self.assertEqual((journey.step,journey.attempt,journey.rest_until),('descanso',3,last+timedelta(days=365)))
            self.assertEqual(ActionProposal.objects.filter(contact=ana,capability='RED-02').count(),1)
        retries=self.funnel()['ruta_sin_posts']['reintentos']['por_angulo']
        self.assertEqual(retries,{'senal_nueva':1,'otro_tema':1})

    def test_7_one_re_check_of_her_signals_when_a_rest_ends(self):
        ana=self.answered('ana-acme','Ana Acme')
        self.invite(ana)
        invited=self.journey(ana).touches.get(kind='invitacion').at
        self.plan(now=invited+timedelta(days=21,hours=1))
        end=self.journey(ana).rest_until+MINUTE
        # The rest ends: the retry waits for one web re-check of her buying signals, inside the day's stage checks.
        self.plan(now=end)
        journey=self.journey(ana)
        self.assertEqual((journey.step,journey.touches.filter(kind='reverificacion').count()),('descanso',1))
        self.assertTrue(red.stage_pending(self.account,end))
        with patch.object(red,'stage_checks_left',return_value=0):  # no allowance left today: it waits
            self.job('check_buyer_stages')
        self.assertEqual([k for k in self.web_keys if 'reverificacion' in k],[])
        self.stage_signals=[self.signal('contratacion',days=3,url=HIRING_URL,evidence='Acme is hiring its first account executive.')]
        stop=self.providers()
        try:
            self.job('check_buyer_stages')
            self.job('check_buyer_stages')  # once: a second run does not check her again
        finally:stop()
        self.assertEqual(len([k for k in self.web_keys if 'reverificacion' in k]),1)
        ana=Contact.objects.get(pk=ana.pk)
        self.assertEqual([s['fuente'] for s in calentamiento.buying_signals(ana)],[HIRING_URL])
        self.assertEqual((ana.classification['stage_check']['state'],ana.classification['fit']),('ok',True))  # the verdict stays
        self.assertFalse(red.stage_pending(self.account,end))
        # The retry now has a new angle: the signal the re-check found.
        self.plan(now=end+HOUR)
        journey=self.journey(ana)
        retry=journey.touches.get(kind='reintento')
        self.assertEqual((journey.attempt,retry.detail['tipo'],retry.detail['senal']),(2,'senal_nueva',HIRING_URL))
        self.assertEqual(self.funnel()['ruta_sin_posts']['reverificaciones'],{'pedidas':1,'hechas':1,'con_senal_nueva':1,'vencidas':0})

    def test_7b_the_re_check_raises_the_level_of_a_buyer_por_confirmar_and_her_entry_stays(self):
        # BAR-24: the web read her company and could not say (por_confirmar, with a source); she went the whole way to a
        # rest. The one re-check finds the round: her level and score go up, the journey keeps what she entered with.
        self.stage_verdict='por_confirmar'
        ana=self.answered('ana-acme','Ana Acme')
        entered=ana.classification['buyer']
        self.assertEqual((ana.classification['stage_check']['state'],entered['level'],self.journey(ana).entry_level),
                         ('ok','por_confirmar','por_confirmar'))
        self.invite(ana)
        invited=self.journey(ana).touches.get(kind='invitacion').at
        self.plan(now=invited+timedelta(days=21,hours=1))
        self.plan(now=self.journey(ana).rest_until+MINUTE)
        self.stage_verdict='confirmado'
        stop=self.providers()
        try:self.job('check_buyer_stages')
        finally:stop()
        self.assertEqual(len([k for k in self.web_keys if 'reverificacion' in k]),1)
        ana=Contact.objects.get(pk=ana.pk)
        buyer=ana.classification['buyer']
        self.assertEqual((buyer['level'],buyer['basis'],ana.classification['fit']),('confirmado','web',True))
        self.assertGreater(buyer['score'],entered['score'])
        self.assertEqual([h['event'] for h in ana.history if h['event']=='stage_rechecked'],['stage_rechecked'])
        self.assertIn('por_confirmar → confirmado',[h['detail'] for h in ana.history if h['event']=='stage_rechecked'][0])
        journey=self.journey(ana)
        self.assertEqual((journey.step,journey.entry_level,journey.entry_score),('descanso','por_confirmar',entered['score']))

    def test_9_reads_stay_inside_their_caps_and_no_visit_is_simulated(self):
        from team_backend.connectors import FakeConnector
        search=FakeConnector.search_people
        companies={'Acme','Globex','Initech'}
        def page(connector,keywords,location=None,profile_language=None):
            """The real search page by company: ids only, no name, headline or distance (linkedin_directo.cliente)."""
            found=search(connector,keywords,location,profile_language)
            if keywords not in companies:return found
            return [dict(p,headline='',display_name='',network_distance='') for p in found]
        with patch.dict(os.environ,{'BUYER_BRIDGE_SEARCHES_PER_DAY':'2','BUYER_BRIDGE_PROFILES_PER_SEARCH':'2'}),\
             patch.object(FakeConnector,'search_people',autospec=True,side_effect=page):
            with patch.dict(os.environ,{'BUYER_NO_POSTS_ROUTE_ENABLED':'false'}):  # both chosen before any bridge is asked for
                ana,_=self.without_posts('ana-acme','Ana Acme')
                gil,_=self.without_posts('gil-globex','Gil Globex',headline='Founder & CEO at Globex')
            for slug,name in (('carla-acme','Carla Acme'),('cora-acme','Cora Acme')):self.candidate(slug,name,'CEO at Acme')
            self.candidate('bruno-acme','Bruno Acme','CTO at Acme')
            self.candidate('gus-globex','Gus Globex','COO at Globex',company='Globex')
            before=self.reads()
            self.plan();self.observe()
            after=self.reads()
            # Two searches (its own cap); a profile read only for a result without a headline, at most two per search
            # (Acme: two CEOs, like her; the CTO is never read); one posts read to see that Gus posts.
            self.assertEqual({k:after[k]-before[k] for k in after},
                             {'busquedas':2,'search':2,'perfil':3,'perfil_compartido':3,'posts_candidatos':1})
            self.assertEqual(self.bridge_states(ana)[-1],('sin_puente','sin_lectura'))
            self.assertEqual(self.bridge(gil).display_name,'Gus Globex')
            # A third buyer the same day: the day's searches are spent, the request waits for tomorrow.
            ivo,_=self.without_posts('ivo-initech','Ivo Initech',headline='Founder & CEO at Initech')
            self.candidate('ian-initech','Ian Initech','CTO at Initech',company='Initech')
            self.plan();self.observe()
            self.assertEqual(self.bridge_states(ivo),[('pedido','sin_ancla')])
            self.assertEqual(self.reads()['busquedas'],2)
            # The shared profile cap rules too: spent, nothing is read and the request still waits.
            with patch.dict(os.environ,{'OPERATOR_PROFILE_READ_DAILY_LIMIT':'0','BUYER_BRIDGE_SEARCHES_PER_DAY':'3'}):
                self.observe()
            self.assertEqual(self.bridge_states(ivo),[('pedido','sin_ancla')])
            self.assertEqual((self.reads()['perfil_compartido'],self.bridge(ivo)),(3,None))
            # Tomorrow: searched again, read and found.
            with self.clock(timezone.now()+timedelta(days=1)):self.observe()
            self.assertEqual(self.bridge(ivo).display_name,'Ian Initech')
        self.assertFalse(BuyerTouch.objects.filter(kind='visita').exists())  # no visit is simulated
        self.assertFalse(AuditEvent.objects.filter(action='network.read',metadata__kind='visit').exists())


class NoPostsSwitchOffTests(NoPostsPathBase):
    def test_8_with_the_switch_off_the_path_is_the_one_of_phases_2_to_4(self):
        from team_backend import mensajes_comprador
        with patch.dict(os.environ,{'BUYER_NO_POSTS_ROUTE_ENABLED':'false'}):
            self.stage_signals=[self.signal()]
            ana,at=self.without_posts('ana-acme','Ana Acme')
            self.candidate('bruno-acme','Bruno Acme','Co-founder & CTO at Acme')
            self.plan();self.observe()
            self.assertEqual((self.bridge_states(ana),self.searched().count('Acme')),([],0))
            self.assertFalse(Contact.objects.filter(bridge_for__isnull=False).exists())
            # Her signal does not give her a note (phase 3: notes only for warmed buyers).
            self.texts[('invite-note','Ana Acme')]=SIGNAL_NOTE
            self.assertEqual(self.invite(ana,at).state,'confirmed')
            self.assertEqual(self.stopped(ana,'nota'),'hecho')
            self.assertFalse(self.paid(ana,'invite-note'))
            # Invited with fewer than two comments (none) and not accepted: no rest (phase 2 asks for the two comments).
            invited=self.journey(ana).touches.get(kind='invitacion').at
            summary=red.plan(self.bot,self.account,invited+timedelta(days=22))
            self.assertEqual(summary['calentamiento'],{'descanso':0,'despiertan':0,'reintentos':0,'proximo':0,'fallos':0})
            self.assertEqual(self.journey(ana).step,'invitado')
            self.assertNotIn('ruta_sin_posts',self.funnel())
            facts=[{'id':'h1','tipo':'senal_de_compra','texto':'x'}]
            self.assertNotIn('Dice que habló con alguien sin una interacción real que lo respalde',
                             mensajes_comprador.message_text_issues(TALK_MESSAGE,facts,'h1'))
            self.assertFalse(BuyerTouch.objects.filter(kind__in=['puente','senal_puente','reverificacion']).exists())


# --------------------------------------------------------------------------- phase 6: her reply, the meeting and the handoff (BAR-23)

BOOKING_URL='https://cal.com/gustavo-barrio/intro'
WEBHOOK_SECRET='calcom-test-secret'


def reply_input(variant,field='respuesta'):
    return evaluaciones.COURSE_CASES['respuesta_comprador']['input'].get(variant,{}).get(field)


def judge_reply_type(text):
    """Jev simulado para clasificar su respuesta (LI-11-M006-K01): una probabilidad por tipo, por palabras clave. Nada
    claro (o dos tipos a la vez): todas bajas o empatadas, y el código decide «otro»."""
    low=(text or '').lower()
    keys={'interesado':('happy to talk','good timing','sounds good','let us talk',"let's talk",'me interesa','hablemos'),
          'pide_informacion':('how much','what exactly','what would you','cuánto cuesta','qué harías'),
          'no_es_el_momento':('not the right moment','not now','ahora no','no es el momento','más adelante'),
          'no_le_interesa':('not interested','no me interesa','do not contact','please remove me'),
          'otra_persona':('right person','talk to','habla con')}
    return {kind:0.9 if any(k in low for k in words) else 0.05 for kind,words in keys.items()}


def judge_reply_draft(reply):
    """Jev simulado para la revisión del líder (fase 6): responde a lo que dijo, no vende, no presiona, no inventa; el
    interesado tiene un paso fácil; el «no» no insiste; la redirección agradece."""
    low=(reply.get('texto') or '').lower()
    sells=any(k in low for k in ('our services','we help','discount','my team builds'))
    presses=any(k in low for k in ('today only','last chance','before friday'))
    return {'resp_responde':0.9,'resp_pitch':0.9 if sells else 0.05,'resp_presiona':0.9 if presses else 0.05,'resp_inventa':0.05,
            'resp_paso_facil':0.9,'resp_insiste':0.9 if 'reconsider' in low else 0.05,'resp_agradece':0.9 if 'thank' in low else 0.2}


class ReplyPathBase(SequencePathBase):
    """The path with BUYER_REPLY_ENABLED (phase 6) on top of phases 3–4: her reply is classified (Jev simulated), the team
    drafts the reply (Claude simulated) that Gustavo copies and sends, Cal.com's signed webhook books the meeting (the
    test client posts it, signed with the test secret) and the lead is handed over. Before phase 6 the steps find nothing
    to do and the endpoints do not exist: that is what the baseline measures."""
    def setUp(self):
        super().setUp()
        env=patch.dict(os.environ,{'BUYER_REPLY_ENABLED':'true','CALCOM_BOOKING_URL':BOOKING_URL,'CALCOM_WEBHOOK_SECRET':WEBHOOK_SECRET,
                                   'INBOX_THREADS_PER_RUN':'20','INBOX_READ_CAPS':'chats=200,messages=400'})
        env.start();self.addCleanup(env.stop)

    # -- steps (production code only)
    def replied(self,slug,name,text,at=None,headline='Founder & CEO at Acme',draft='',faltan=(),referido=''):
        """M1 «Hecho» at self.start, she answers a day later and the next cycle reads and classifies it (and the drafter,
        simulated, writes `draft`)."""
        contact=self.messaged(slug,name,headline=headline)
        if draft:self.write_reply(contact,draft,faltan=faltan,referido=referido)
        at=at or self.start+DAY
        self.she_replies(contact,text,at)
        self.cycle(at+HOUR)
        return Contact.objects.get(pk=contact.pk)

    def write_reply(self,contact,text,faltan=(),referido=''):
        """Claude simulado escribe, para esta persona, la respuesta (y lo que falta o a quién nombró)."""
        self.texts[('buyer-reply',contact.display_name)]=text
        self.texts[('buyer-reply-extra',contact.display_name)]={'faltan':list(faltan),'referido_nombre':referido}

    def webhook(self,trigger,uid,start=None,ref='',name='',email='',previous='',secret=WEBHOOK_SECRET,at=None,body=None):
        """Cal.com posts the booking (docs: cal.com/docs/developing/guides/automation/webhooks): anonymous, signed with
        X-Cal-Signature-256 = HMAC-SHA256(secret, raw body) in hex."""
        import hashlib
        import hmac
        from rest_framework.test import APIClient
        start=start or (timezone.now()+timedelta(days=3)).replace(microsecond=0)
        payload={'uid':uid,'bookingId':abs(hash(uid))%10**6,'title':'Intro con Gustavo','startTime':start.isoformat(),
                 'endTime':(start+timedelta(minutes=30)).isoformat(),'attendees':[{'name':name,'email':email,'timeZone':'America/Chicago'}],
                 'metadata':{'barrio':ref} if ref else {},'status':'CANCELLED' if trigger=='BOOKING_CANCELLED' else 'ACCEPTED'}
        if previous:payload['rescheduleUid']=previous
        raw=body if body is not None else json.dumps({'triggerEvent':trigger,'createdAt':timezone.now().isoformat(),'payload':payload}).encode()
        signature=hmac.new(secret.encode(),raw,hashlib.sha256).hexdigest() if secret else 'no-secret-provided'
        with self.clock(at or timezone.now()):
            return APIClient().post('/api/v1/comprador/calcom/webhook',data=raw,content_type='application/json',
                                    HTTP_X_CAL_SIGNATURE_256=signature)

    # -- reads
    def replies_of(self,contact):
        return self.drafts_of(contact,'respuesta')

    def reply(self,contact):
        rows=self.replies_of(contact)
        return rows[-1] if rows else None

    def reply_cards(self,contact,at):
        """Her reply cards in Tu turno (tasks.mensajes): «Mensaje sugerido» with the draft, or the conversation card «necesita
        tu respuesta» when there is none (otro, no booking link)."""
        def who(card):
            return (((card.get('message') or {}).get('person')) or ((card.get('conversation') or {}).get('person')) or {}).get('id')
        return [c for c in self.turn_at(at)['tasks']['mensajes'] if c['id'].startswith('respuesta:') and who(c)==str(contact.pk)]

    def booking_ref(self,contact):
        return getattr(self.journey(contact),'booking_ref',None)

    def handoffs(self,at=None):
        """GET /api/v1/comprador/entregas (read only); [] before phase 6."""
        with self.clock(at or timezone.now()):
            response=self.gustavo_api().get('/api/v1/comprador/entregas')
        return response.json().get('items',[]) if response.status_code==200 else []

    def handoff_of(self,contact,at=None):
        return next((h for h in self.handoffs(at) if (h.get('persona') or {}).get('contacto')==str(contact.pk)),None)

    def confirm_opportunity(self,contact,at):
        """Gustavo taps «Crear la oportunidad» on the handoff's card in Tu turno (PRS-09: only he creates it). Returns the
        handoff's opportunity as the read endpoint shows it, or None when there is no such card."""
        cards=[c for c in self.turn_at(at)['items'] if c['id'].startswith('entrega:') and (c.get('handoff') or {}).get('contacto')==str(contact.pk)]
        if not cards:return None
        action=next(a for a in cards[0]['actions'] if a.get('endpoint'))
        with self.clock(at):
            response=self.gustavo_api().post(action['endpoint'],action.get('body') or {},format='json')
        self.assertEqual(response.status_code,200,response.content)
        return (self.handoff_of(contact,at) or {}).get('oportunidad')



class ReplyBuyerPathTests(ReplyPathBase):
    """BAR-23 de punta a punta con las funciones de producción y el reloj simulado: elegida → calentada (dos comentarios
    y su respuesta) → invitada → aceptó → M1 «Hecho» → responde con interés → borrador con su enlace → «Hecho» → webhook
    firmado de Cal.com → reunión → entrega del lead → oportunidad con un toque → embudo con cada etapa en 1; y sus
    variantes."""

    def warm_messaged(self,slug,name,headline='Founder & CEO at Acme'):
        """Chosen, followed, the two warm-up comments and her answer to the second, invited, accepted and «Hecho, le
        escribí» on the first message at self.start."""
        contact=self.chosen_and_followed(slug,name,headline=headline)
        _,second=self.warm_up(contact)
        self.step_their_answer(contact,second)
        self.texts[('buyer-message',name)]=case_text('primer_mensaje_comprador','M1')
        self.invite(contact)
        contact=self.accepted(contact)
        self.prepare()
        cards=self.cards_of(contact,LATER)
        self.assertEqual(len(cards),1)
        self.close_at(cards[0],'enviado',self.start)
        return Contact.objects.get(pk=contact.pk)

    def link(self,contact):
        return f'{BOOKING_URL}?metadata%5Bbarrio%5D={self.booking_ref(contact)}'

    def interested(self,people):
        """Several buyers messaged first (one timeline), then each replies «flujo» a day later: [contact]."""
        contacts=[self.messaged(slug,name) for slug,name in people]
        for contact in contacts:
            self.write_reply(contact,reply_input('flujo','borrador'))
            self.she_replies(contact,reply_input('flujo'),self.start+DAY)
        self.cycle(self.start+DAY+HOUR)
        return [Contact.objects.get(pk=c.pk) for c in contacts]

    def test_the_whole_path_until_the_lead_is_handed_over(self):
        from team_backend.models import BuyerDraft, Conversation, Opportunity
        ana=self.warm_messaged('resp-e2e-ana','Ana Agenda')
        self.write_reply(ana,reply_input('flujo','borrador'))
        writes=self.fake.state['writes']
        at=self.start+DAY
        self.she_replies(ana,reply_input('flujo'),at)
        self.cycle(at+HOUR)

        # A. Classified with the methodology, reading the whole conversation: interesado.
        journey=self.journey(ana);row=self.reply(ana)
        self.assertEqual((journey.step,journey.reply_type,row.inputs['clasificacion']['tipo']),('interesado','interesado','interesado'))
        classify=next(j for j in self.jev if j['purpose']=='buyer-reply-classify')
        self.assertEqual(set(classify['questions']),{'interesado','pide_informacion','no_es_el_momento','no_le_interesa','otra_persona'})
        self.assertIn('LI-11-M006-K01',classify['state']['course_context'])
        self.assertEqual([(m['de'],m['texto']) for m in classify['state']['conversacion']],
                         [('Gustavo',case_text('primer_mensaje_comprador','M1')),('ella',reply_input('flujo'))])
        self.assertIn(('respuesta_clasificada','estado'),self.kinds(ana))

        # B. The draft: what the drafter wrote plus her booking link (appended by the code), reviewed by the lead.
        self.assertEqual(row.text,reply_input('flujo','borrador')+'\n'+self.link(ana))
        self.assertEqual((row.state,row.review['decision']),('listo','approve'))
        review=next(j for j in self.jev if j['purpose']=='lead-review-reply')
        self.assertEqual(set(review['questions']),{'resp_responde','resp_pitch','resp_presiona','resp_inventa','resp_paso_facil'})
        drafted=next(c for c in self.calls if c['purpose']=='buyer-reply')
        self.assertNotIn(BOOKING_URL,json.dumps(drafted['inputs']))  # the drafter never writes the link
        self.assertEqual((drafted['inputs']['tipo'],drafted['inputs']['su_mensaje']),('interesado',reply_input('flujo')))
        for uid in ('LI-11-M006-K01','LI-12-M001-K04','LI-08-M003-K05'):self.assertIn(uid,drafted['context'])

        # Tu turno: her card with its own label and «Agendó»; her inbox conversation does not show twice.
        cards=self.reply_cards(ana,at+2*HOUR)
        self.assertEqual(len(cards),1)
        card=cards[0]
        self.assertEqual((card['type'],card['title'],card['message']['text_label'],card['message']['text'],card['message']['comment']),
                         ('mensaje','Ana Agenda quiere hablar','Respuesta sugerida · con tu agenda',row.text,reply_input('flujo')))
        self.assertEqual([a['label'] for a in card['actions']],['Abrir la conversación','Hecho, le escribí','No escribirle','Agendó'])
        self.assertEqual(card['actions'][1]['endpoint'],f'/api/v1/respuestas/{row.pk}/mensaje')
        turn=self.turn_at(at+2*HOUR)
        self.assertFalse([c for c in turn['tasks']['conversaciones'] if (c.get('conversation') or {}).get('contact_id')==str(ana.pk)])

        # «Hecho, le escribí»: Gustavo sends it himself; the card goes, the journey keeps it.
        self.close_at(card,'enviado',at+2*HOUR)
        row.refresh_from_db()
        self.assertEqual(row.state,'enviado')
        self.assertIn(('respuesta_enviada','saliente'),self.kinds(ana))
        self.assertEqual(self.reply_cards(ana,at+3*HOUR),[])

        # C. She books through the link: Cal.com's signed webhook, matched by the link's identifier.
        booked=at+DAY;start=(booked+3*DAY).replace(microsecond=0)
        response=self.webhook('BOOKING_CREATED','e2e-booking-1',start=start,ref=self.booking_ref(ana),name='Ana Agenda',
                              email='ana@acme.example',at=booked)
        self.assertEqual((response.status_code,response.json()['emparejada_por']),(200,'enlace'),response.content)
        journey=self.journey(ana)
        self.assertEqual((journey.step,journey.meeting_date,journey.meeting_at),('reunion',start,booked))

        # D. The lead, handed over source-neutral and without qualification.
        handoff=self.handoff_of(ana,booked+HOUR)
        self.assertEqual((handoff['fuente'],handoff['estado'],handoff['oportunidad']),('linkedin','lista',None))
        self.assertEqual((handoff['persona']['contacto'],handoff['persona']['nombre']),(str(ana.pk),'Ana Agenda'))
        self.assertEqual(handoff['empresa'],{'nombre':'Acme','fuente':'titular de LinkedIn'})
        path=handoff['recorrido']
        self.assertEqual([(m['tipo'],m['numero']) for m in path['mensajes_enviados']],[('mensaje',1),('respuesta',1)])
        self.assertEqual((path['respondio_a']['numero'],path['respuesta']['tipo'],path['respuesta']['texto']),(1,'interesado',reply_input('flujo')))
        self.assertEqual((path['senal_de_entrada']['entrada'],path['senal_de_entrada']['senal']['tipo']),('saliente','respondio_comentario'))
        self.assertEqual((path['toques']['comentarios'],path['puente'],path['referido_por']),(2,[],None))
        self.assertEqual(len(handoff['conversacion']),3)
        self.assertIn(reply_input('flujo')[:40],handoff['conversacion'][1])
        self.assertEqual((handoff['reunion']['inicio'],handoff['reunion']['emparejada_por'],handoff['reunion']['correo']),
                         (start.isoformat(),'enlace','ana@acme.example'))
        self.assertIn({'hecho':'Trabaja en Acme: Founder & CEO at Acme','fuente':'titular de LinkedIn'},handoff['negocio'])
        self.assertTrue(all(f['hecho'] for f in handoff['negocio']))
        self.assertFalse({'calificacion','preguntas','presupuesto','necesidad'}&set(handoff))
        chat=Conversation.objects.get(contact=ana)
        self.assertEqual((handoff['recorrido_id'],handoff['conversacion_id']),(str(journey.pk),str(chat.pk)))

        # PRS-09: only Gustavo creates the opportunity, with one tap; the handoff links it to the conversation and journey.
        self.assertFalse(Opportunity.objects.filter(contact=ana).exists())
        opportunity=self.confirm_opportunity(ana,booked+2*HOUR)
        self.assertEqual(opportunity['etapa'],'reunion')
        item=Opportunity.objects.get(contact=ana)
        self.assertEqual((str(item.pk),item.channel,item.next_action_at,item.company),(opportunity['id'],'linkedin',start,'Acme'))
        handoff=self.handoff_of(ana,booked+2*HOUR)
        self.assertEqual((handoff['estado'],handoff['conversacion_id'],handoff['recorrido_id']),('confirmada',str(chat.pk),str(journey.pk)))
        self.assertFalse([c for c in self.turn_at(booked+3*HOUR)['items'] if c['id'].startswith('entrega:')])

        # H. The funnel: every stage at 1, her reply by type and the hours from her reply to the meeting.
        funnel=self.funnel()
        self.assertEqual(self.stages(funnel['acumulado']),{s:1 for s in ('elegidos','calentados','calentados_2','invitados','aceptaron',
                                                                       'recibieron_mensaje','respondieron','interesados','reunion')})
        replies=funnel['respuestas']
        self.assertEqual((replies['activa'],replies['clasificadas'],replies['por_tipo']['interesado'],replies['reuniones']),(True,1,1,1))
        self.assertEqual(journey.replied_at,at)  # her reply, a day before she booked
        self.assertEqual(replies['horas_respuesta_a_reunion'],{'mediana':24.0,'personas':1})
        self.assertEqual(funnel['borradores']['respuestas']['enviados'],1)
        self.assertEqual(self.fake.state['writes'],writes)  # the team never wrote a message (INB-08)
        self.assertFalse(BuyerDraft.objects.filter(contact=ana,state__in=['listo','en_revision']).exists())
        self.assertFalse(AuditEvent.objects.filter(action__in=['buyer.record_failed','buyer.reply_failed']).exists())

    def test_1_she_asks_for_information(self):
        bea=self.replied('resp-e2e-bea','Bea Pregunta',reply_input('P'),draft=reply_input('P','borrador'),faltan=reply_input('P','faltan'))
        row=self.reply(bea)
        self.assertEqual((row.inputs['clasificacion']['tipo'],row.state),('pide_informacion','listo'))
        self.assertTrue(row.text.endswith(self.link(bea)))
        self.assertEqual(self.journey(bea).step,'respondio')  # asking is not interest yet
        card=self.reply_cards(bea,self.start+DAY+2*HOUR)[0]
        self.assertIn('Falta confirmar antes de enviar: '+reply_input('P','faltan')[0],card['body'])
        self.assertEqual((card['message']['reply'],card['message']['reply_label']),(reply_input('P','faltan')[0],'Falta confirmar'))
        self.assertIn('Agendó',[a['label'] for a in card['actions']])

    def test_2_not_the_moment_with_a_date_rests_until_then_and_comes_back_with_what_she_said(self):
        cris=self.replied('resp-e2e-cris','Cris Enero',reply_input('N1'),draft=reply_input('N1','borrador'))
        journey=self.journey(cris);row=self.reply(cris)
        self.assertEqual((journey.step,journey.rest_reason,row.inputs['descanso']['lo_dijo']),('descanso','no_es_el_momento',True))
        until=journey.rest_until.astimezone(operador.local_tz())
        self.assertEqual((until.month,until.day,until.hour),(2,1,9))
        self.assertNotIn('http',row.text)
        card=self.reply_cards(cris,self.start+DAY+2*HOUR)[0]
        self.assertIn(f'descansa hasta {until:%d/%m/%Y}',card['body'])
        self.assertNotIn('Agendó',[a['label'] for a in card['actions']])
        self.close_at(card,'enviado',self.start+DAY+2*HOUR)
        # Before her date nothing happens; at her date she comes back with what she said as the angle.
        self.cycle(journey.rest_until-HOUR)
        self.assertEqual(self.journey(cris).step,'descanso')
        self.texts[('buyer-message','Cris Enero')]='Cris, you said after January was better, with the round closed. How is the Friday report doing now?'
        self.cycle(journey.rest_until+MINUTE)
        self.cycle(journey.rest_until+HOUR)
        journey=self.journey(cris)
        self.assertEqual(journey.attempt,2)
        retry=journey.touches.get(kind='reintento')
        self.assertEqual((retry.detail['tipo'],retry.detail['texto']),('lo_que_dijo',reply_input('N1')))
        first=next(d for d in self.drafts_of(cris,'mensaje') if d.attempt==2)
        self.assertEqual((first.number,first.state,first.anchor['tipo']),(1,'listo','lo_que_dijo'))
        call=next(c for c in reversed(self.calls) if c['purpose']=='buyer-message')
        self.assertEqual(call['inputs']['hechos'][0]['texto'],reply_input('N1'))
        self.assertIn('"lo_que_dijo"',call['system'])

    def test_2b_not_the_moment_without_a_date_rests_ninety_days_and_her_message_wakes_her(self):
        dani=self.replied('resp-e2e-dani','Dani Ahora',reply_input('N2'),draft=reply_input('N2','borrador'))
        journey=self.journey(dani)
        rest=journey.touches.get(kind='descanso')
        self.assertEqual((journey.rest_reason,round((journey.rest_until-rest.at)/DAY),self.reply(dani).inputs['descanso']['lo_dijo']),
                         ('no_es_el_momento',90,False))
        # She writes during the rest: that wakes her by itself and her new message is classified.
        self.write_reply(dani,'Dani, glad to hear it. Pick any slot that suits you and we look at the launch numbers.')
        self.she_replies(dani,'Actually things calmed down, happy to talk now.',self.start+5*DAY)
        self.cycle(self.start+5*DAY+HOUR)
        journey=self.journey(dani)
        self.assertEqual((journey.step,journey.attempt),('interesado',1))
        self.assertEqual([r.number for r in self.replies_of(dani)],[1,2])

    def test_3_not_interested_is_definitive(self):
        eva=self.replied('resp-e2e-eva','Eva Fuera',reply_input('X'),draft=reply_input('X','borrador'))
        journey=self.journey(eva)
        self.assertEqual((journey.step,journey.exit_reason),('salio','no_le_interesa'))
        self.assertIn('nadie le vuelve a escribir',self.reply_cards(eva,self.start+DAY+2*HOUR)[0]['body'])
        before=len(self.drafts_of(eva,'mensaje'))+len(self.replies_of(eva))
        self.she_replies(eva,reply_input('X','despues'),self.start+2*DAY)
        for days in (2,6,30,120):self.cycle(self.start+days*DAY+HOUR)
        self.assertEqual(len(self.drafts_of(eva,'mensaje'))+len(self.replies_of(eva)),before)
        self.assertEqual((self.journey(eva).step,self.journey(eva).attempt),('salio',1))

    def test_4_another_person_becomes_a_linked_contact_with_her_own_journey(self):
        from team_backend import mensajes_comprador
        self.fake.seed_person('bruno-globex','Bruno Ruiz','Head of Operations at Globex',location='Austin, Texas')
        fer=self.replied('resp-e2e-fer','Fer Redirige',reply_input('O'),headline='Founder & CEO at Globex',
                         draft=reply_input('O','borrador'),referido=reply_input('O','referido'))
        self.cycle(self.start+DAY+2*HOUR)
        bruno=Contact.objects.get(public_identifier='bruno-globex')
        journey=self.journey(bruno)
        self.assertEqual((bruno.source,bruno.stage,bruno.classification['referido_por']),('referido','fit',str(fer.pk)))
        self.assertEqual(journey.referred_by_id,self.journey(fer).pk)
        self.assertEqual(journey.touches.get(kind='referido').detail['respuesta'],str(self.reply(fer).pk))
        self.assertEqual(self.reply(fer).inputs['referido']['estado'],'creado')
        fact=mensajes_comprador.anchors(bruno)[0]  # her first note or message may name who referred her
        self.assertEqual((fact['tipo'],fact['nombre_de_quien_refiere']),('referido','Fer Redirige'))
        self.assertTrue(mensajes_comprador.warmed(journey))
        self.assertIn('Bruno Ruiz ya es un contacto',self.reply_cards(fer,self.start+DAY+3*HOUR)[0]['body'])

    def test_4b_without_her_profile_gustavo_pastes_it(self):
        gus=self.replied('resp-e2e-gus','Gus Redirige','I am not the right person for this, talk to Lia from operations.',
                         headline='Founder & CEO at Initech',draft='Gus, thanks for pointing me to Lia.',referido='Lia')
        card=self.reply_cards(gus,self.start+DAY+2*HOUR)[0]
        self.assertIn('Falta el perfil de Lia',card['body'])
        paste=next(a for a in card['actions'] if a['label']=='Pegar su perfil')
        self.fake.seed_person('lia-initech','Lia Ops','COO at Initech',location='Austin, Texas')
        with self.clock(self.start+DAY+2*HOUR):
            bad=self.gustavo_api().post(paste['endpoint'],{'note':'Lia'},format='json')
            good=self.gustavo_api().post(paste['endpoint'],{'note':'https://www.linkedin.com/in/lia-initech/'},format='json')
        self.assertEqual((bad.status_code,good.status_code),(400,200),good.content)
        self.cycle(self.start+DAY+3*HOUR)
        self.assertEqual(self.journey(Contact.objects.get(public_identifier='lia-initech')).referred_by_id,self.journey(gus).pk)

    def test_5_low_confidence_is_otro_with_a_card_and_no_draft(self):
        gil=self.replied('resp-e2e-gil','Gil Duda',reply_input('B'))
        row=self.reply(gil)
        self.assertEqual((row.inputs['clasificacion']['tipo'],row.text,row.state),('otro','','listo'))
        self.assertEqual(self.journey(gil).step,'respondio')
        self.assertFalse([c for c in self.calls if c['purpose']=='buyer-reply'])  # nothing paid to draft
        card=self.reply_cards(gil,self.start+DAY+2*HOUR)[0]
        self.assertEqual((card['type'],card['title']),('conversacion','Gil Duda te respondió: necesita tu respuesta'))
        self.assertIn('Sin confianza suficiente',card['body'])
        self.assertEqual([a['label'] for a in card['actions']],['Abrir la conversación','Hecho, le escribí','No escribirle'])
        self.assertEqual(card['conversation']['messages'][-1]['text'],reply_input('B'))
        self.close_at(card,'no',self.start+DAY+2*HOUR)
        self.assertEqual((self.reply(gil).state,self.journey(gil).step),('no_enviado','respondio'))  # «no» never exits her

    def test_6_without_the_booking_link_there_is_no_draft_and_an_alert(self):
        from team_backend import alertas_slack
        with patch.dict(os.environ,{'CALCOM_BOOKING_URL':''}):
            hugo=self.replied('resp-e2e-hugo','Hugo Sinenlace',reply_input('E'),draft=reply_input('flujo','borrador'))
            row=self.reply(hugo)
            self.assertEqual((row.inputs['clasificacion']['tipo'],row.text,row.stopped_by),('interesado','','agenda'))
            self.assertEqual(self.journey(hugo).step,'interesado')
            self.assertFalse([c for c in self.calls if c['purpose']=='buyer-reply'])
            self.assertIsNone(self.booking_ref(hugo))
            card=self.reply_cards(hugo,self.start+DAY+2*HOUR)[0]
            self.assertIn('CALCOM_BOOKING_URL',card['body'])
            self.assertTrue(AuditEvent.objects.filter(action='buyer.reply_no_link',target=str(hugo.pk)).exists())
            self.assertEqual([a.key for a in alertas_slack.falta_enlace_agenda(self.start+DAY+2*HOUR)],['comprador:falta_enlace_agenda'])

    def test_7_the_webhook_rejects_repeats_reschedules_and_cancels(self):
        from team_backend.models import MeetingBooking
        ana,=self.interested([('resp-e2e-wh','Ana Webhook')])
        ref=self.booking_ref(ana);at=self.start+2*DAY;start=(at+3*DAY).replace(microsecond=0)
        # Rejected: a bad signature, and no secret configured; nothing is stored.
        self.assertEqual(self.webhook('BOOKING_CREATED','wh-1',ref=ref,secret='wrong',at=at).status_code,403)
        with patch.dict(os.environ,{'CALCOM_WEBHOOK_SECRET':''}):
            self.assertEqual(self.webhook('BOOKING_CREATED','wh-1',ref=ref,at=at).status_code,403)
        self.assertFalse(MeetingBooking.objects.exists())
        self.assertEqual(self.journey(ana).step,'interesado')
        # Created, then the same delivery again: processed once.
        body=json.dumps({'triggerEvent':'BOOKING_CREATED','createdAt':at.isoformat(),'payload':{
            'uid':'wh-1','startTime':start.isoformat(),'endTime':(start+30*MINUTE).isoformat(),
            'attendees':[{'name':'Ana Webhook','email':'ana@acme.example'}],'metadata':{'barrio':ref}}}).encode()
        first=self.webhook('BOOKING_CREATED','wh-1',body=body,at=at)
        again=self.webhook('BOOKING_CREATED','wh-1',body=body,at=at+MINUTE)
        self.assertEqual((first.status_code,again.status_code,again.json()),(200,200,{'repetido':True}))
        self.assertEqual((MeetingBooking.objects.count(),self.journey(ana).touches.filter(kind='reunion').count()),(1,1))
        self.assertEqual(self.journey(ana).meeting_date,start)
        # Rescheduled: the new booking replaces the old one, the date moves, still one handoff.
        later=start+2*DAY
        self.webhook('BOOKING_RESCHEDULED','wh-2',start=later,ref=ref,previous='wh-1',at=at+HOUR)
        self.assertEqual(MeetingBooking.objects.get(uid='wh-1').state,'reprogramada')
        journey=self.journey(ana)
        self.assertEqual((journey.step,journey.meeting_date),('reunion',later))
        self.assertEqual(self.handoff_of(ana,at+2*HOUR)['reunion']['inicio'],later.isoformat())
        self.assertEqual(len(self.handoffs(at+2*HOUR)),1)
        # Cancelled: back to «interesado», the handoff cancelled, the funnel no longer counts the meeting.
        self.webhook('BOOKING_CANCELLED','wh-2',start=later,ref=ref,at=at+3*HOUR)
        journey=self.journey(ana)
        self.assertEqual((journey.step,journey.meeting_date,journey.meeting_at),('interesado',None,None))
        self.assertEqual(self.handoff_of(ana,at+4*HOUR)['estado'],'cancelada')
        self.assertEqual(self.stages(self.funnel()['acumulado'])['reunion'],0)

    def test_7b_an_unmatched_booking_waits_for_gustavo(self):
        from team_backend import alertas_slack
        from team_backend.models import MeetingBooking
        ana,=self.interested([('resp-e2e-wh2','Ana Sinref')])
        at=self.start+2*DAY
        response=self.webhook('BOOKING_CREATED','wh-x',name='Someone Else',email='someone@else.example',at=at)
        self.assertEqual(response.json()['emparejada_por'],'sin_emparejar')
        booking=MeetingBooking.objects.get(uid='wh-x')
        self.assertEqual((booking.journey_id,self.journey(ana).step),(None,'interesado'))
        self.assertEqual([a.key for a in alertas_slack.reserva_sin_emparejar(at)],[f'comprador:reserva:{booking.pk}'])
        card=next(c for c in self.turn_at(at+HOUR)['items'] if c['id']==f'reserva:{booking.pk}')
        self.assertEqual([a['label'] for a in card['actions']],['Es Ana Sinref','No es de un comprador'])
        with self.clock(at+HOUR):
            response=self.gustavo_api().post(card['actions'][0]['endpoint'],card['actions'][0]['body'],format='json')
        self.assertEqual((response.status_code,response.json()['emparejada_por']),(200,'gustavo'),response.content)
        self.assertEqual(self.journey(ana).step,'reunion')
        self.assertFalse([c for c in self.turn_at(at+2*HOUR)['items'] if c['id']==f'reserva:{booking.pk}'])

    def test_7c_her_email_in_the_conversation_or_her_exact_name_match_a_booking_without_the_identifier(self):
        ana,bea=self.interested([('resp-e2e-wh3','Ana Correo'),('resp-e2e-wh4','Béa Nombre')])
        self.she_replies(ana,'Booked it, my work email is ana.correo@acme.example',self.start+2*DAY)
        self.cycle(self.start+2*DAY+HOUR)
        response=self.webhook('BOOKING_CREATED','wh-mail',name='A. C.',email='ana.correo@acme.example',at=self.start+2*DAY+2*HOUR)
        self.assertEqual((response.json()['emparejada_por'],self.journey(ana).step),('correo','reunion'))
        response=self.webhook('BOOKING_CREATED','wh-name',name='bea  nombre',email='x@y.example',at=self.start+2*DAY+3*HOUR)
        self.assertEqual((response.json()['emparejada_por'],self.journey(bea).step),('nombre','reunion'))

    def test_8_gustavo_marks_it_booked_by_hand(self):
        ana,=self.interested([('resp-e2e-man','Ana Mano')])
        at=self.start+DAY+2*HOUR
        card=self.reply_cards(ana,at)[0]
        booked=next(a for a in card['actions'] if a['label']=='Agendó')
        when=(self.start+4*DAY).astimezone(operador.local_tz())
        with self.clock(at):
            first=self.gustavo_api().post(booked['endpoint'],{'note':f'{when:%d/%m/%Y} 10:30 por correo'},format='json')
            second=self.gustavo_api().post(booked['endpoint'],{},format='json')
        self.assertEqual((first.status_code,second.status_code),(200,200),first.content)
        self.assertEqual(first.json()['reserva'],second.json()['reserva'])
        journey=self.journey(ana)
        local=journey.meeting_date.astimezone(operador.local_tz())
        self.assertEqual((journey.step,local.date(),local.hour,local.minute),('reunion',when.date(),10,30))
        handoff=self.handoff_of(ana,at+HOUR)
        self.assertEqual((handoff['reunion']['emparejada_por'],handoff['reunion']['proveedor']),('manual','manual'))
        self.assertEqual(self.reply(ana).state,'cancelado')  # she booked: the draft no longer applies
        self.assertEqual(self.reply_cards(ana,at+HOUR),[])

    def test_9_with_the_switch_off_everything_is_as_in_phases_1_to_5(self):
        from team_backend.models import MeetingBooking
        with patch.dict(os.environ,{'BUYER_REPLY_ENABLED':'false'}):
            ana=self.replied('resp-e2e-off','Ana Apagada',reply_input('flujo'),draft=reply_input('flujo','borrador'))
            self.assertEqual((self.replies_of(ana),self.journey(ana).step),([],'respondio'))
            self.assertFalse([j for j in self.jev if j['purpose'] in ('buyer-reply-classify','lead-review-reply')])
            self.assertEqual(self.webhook('BOOKING_CREATED','off-1',name='Ana Apagada',at=self.start+2*DAY).status_code,202)
            self.assertFalse(MeetingBooking.objects.exists())
            self.assertEqual(self.reply_cards(ana,self.start+2*DAY),[])
            self.assertEqual(self.handoffs(self.start+2*DAY),[])
            self.assertFalse(self.funnel()['respuestas']['activa'])
            self.assertTrue(AuditEvent.objects.filter(action='buyer.sequence_replied',target=str(ana.pk)).exists())

    def test_10_the_booking_link_never_goes_in_messages_1_to_4(self):
        ana=self.messaged('resp-e2e-seq','Ana Secuencia');self.follow_ups(ana)
        sent=self.start
        for number in (2,3,4):
            due=sent+timedelta(days={2:4,3:5,4:7}[number])
            self.cycle(due+MINUTE)
            cards=self.sequence_cards(ana,due+HOUR)
            self.assertEqual(len(cards),1,number)
            self.close_at(cards[0],'enviado',due+HOUR);sent=due+HOUR
        texts=[d.text for d in self.drafts_of(ana,'mensaje')]
        self.assertEqual(len(texts),4)
        self.assertFalse(any('cal.com' in t or 'metadata' in t for t in texts))
        self.assertIsNone(self.booking_ref(ana))  # no link was ever made for her
        self.assertFalse(any(BOOKING_URL in json.dumps(c['inputs']) for c in self.calls))
        # A message 1–4 carrying the link would not pass its rules (RSP-07's: no links).
        self.assertIn('Primer mensaje con enlaces',respuestas.dm_text_issues(texts[0]+' '+BOOKING_URL,texts[0]))

    def test_11_the_weekly_reading_reads_this_funnel_and_a_small_sample_is_not_judged(self):
        ivo,_=self.messaged('resp-e2e-ivo','Ivo Lectura'),self.messaged('resp-e2e-jon','Jon Lectura')
        self.write_reply(ivo,reply_input('flujo','borrador'))
        self.she_replies(ivo,reply_input('flujo'),self.start+DAY)
        self.cycle(self.start+DAY+HOUR)
        response=self.human.get('/api/v1/comprador/lectura-semanal')
        self.assertEqual(response.status_code,200,response.content)
        reading=response.json()
        self.assertEqual((reading['activa'],reading['muestra_chica'],reading['invitaciones'],reading['se_rompe'],reading['cambio']),
                         (True,True,2,None,None))
        self.assertEqual(reading['borradores'],{'pendientes':1,'enviados':2})  # her reply waits; both first messages went
        self.assertIn('Muestra chica: 2 invitaciones en total, menos de 30',reading['lineas'][1])
        # Where it breaks first at scale (acceptance, then the reply): test_respuesta_comprador.WeeklyReadingTests.


class ProjectAppPathTests(WarmupPathBase):
    """BAR-25 (NETWORK_PROJECTAPP_BUYER_ENABLED): the ProjectApp buyer and the partner end to end, through discovery by
    audience, the classifier with the class 08 methodology, the web check with size and dated signals, the follow, the
    warm-up comments (the buyer's group, or «comunidad» for the partner), the invitation and the funnel by segment."""
    CTO='CTO at Lone Star Outfitters · family retail chain, 80 people · hiring software engineers'
    AGENCY='Founder at Brightside Marketing · campaigns and websites for local businesses, built with our development partners'

    def setUp(self):
        super().setUp()
        env=patch.dict(os.environ,{'NETWORK_PROJECTAPP_BUYER_ENABLED':'true'});env.start();self.addCleanup(env.stop)

    def providers(self,fit=True,note=''):
        from team_backend import research
        url='https://lonestar.example/careers'
        def claude(system,message,**kwargs):
            if kwargs['purpose']=='network-stage':
                self.assertIn('tamano',kwargs['output_schema']['properties'])  # the ProjectApp judge, not the startup one
                return {'text':json.dumps({'verdict':'confirmado','evidence':'Unas 80 personas y dos vacantes de Software Engineer.',
                                           'source_urls':[url],'tamano':'20_a_200',
                                           'senales':[{'tipo':'contrata_desarrolladores','fecha':'2026-11-10','source_url':url,
                                                       'evidencia':'Dos vacantes de Software Engineer.'}]}),'model':'claude-sonnet-5-5'}
            self.assertIn('buyer_segment',system)
            out=[]
            for p in json.loads(message)['people']:
                if 'Marketing' in (p.get('headline') or ''):
                    row={'role':'partner','buyer_profile':'','buyer_level':'','buyer_segment':'','company_size':'',
                         'reason':'Agencia de marketing que subcontrata el desarrollo web de sus clientes.',
                         'course_citations':['LI-03-M005-K06','LI-08-M001-K05']}
                else:
                    row={'role':'comprador','buyer_profile':'lider_tecnologia','buyer_level':'probable','buyer_segment':'retail_ecommerce',
                         'company_size':'20_a_200','reason':'Líder de tecnología de una cadena de retail de 80 personas que contrata.',
                         'course_citations':['LI-03-M005-K06','LI-08-M001-K05','LI-08-M004-K01']}
                out.append({'id':p['id'],'fit':fit,'modality':'projectapp','affinity':'desconocida','confidence':0.9,'us_market':True,
                            'invitation_note':'','note_reason':'',**row})
            return {'text':json.dumps({'contacts':out}),'model':kwargs.get('model'),'estimated_usd':0.001,'request_id':'req_pa'}
        def web(request):
            source=research.Source('s1',url,'Careers','Lone Star Outfitters has about 80 employees and two open Software Engineer jobs.',
                                   '2026-11-12T00:00:00+00:00')
            return research.ResearchResult(request.public_question,'complete','2026-11-12T00:00:00+00:00',
                                           (research.Finding('About 80 employees; two Software Engineer openings.',('s1',)),),(source,),
                                           usage={'model':'claude-sonnet-5-5'})
        claude_patch=patch('knowledge.providers.claude',side_effect=claude);web_patch=patch('team_backend.research.research',side_effect=web)
        claude_patch.start();web_patch.start()
        return lambda:(claude_patch.stop(),web_patch.stop())

    def found(self,slug,name,headline,search,location):
        """discover_network finds her with the search of her audience; classify_contacts classifies her and
        check_buyer_stages checks the web."""
        person=self.fake.seed_person(slug,name,headline=headline,search=search,location=location)
        self.job('discover_network')
        stop=self.providers()
        try:
            job=self.job('classify_contacts')
            self.step_check()
        finally:stop()
        self.assertEqual(job.state,'complete',job.error)
        return Contact.objects.get(account=self.account,provider_user_id=person['id'])

    def test_a_projectapp_buyer_chosen_by_her_audiences_search_warmed_invited_and_counted_in_her_segment(self):
        tomas=self.found('tomas-retail','Tomas Retail',self.CTO,'CTO retail','Dallas, Texas')
        self.assertEqual(AuditEvent.objects.get(action='network.searched',metadata__query='CTO retail').metadata['audience'],'projectapp')
        c=tomas.classification;b=c['buyer']
        self.assertEqual((tomas.stage,c['role'],c['course_methodology']),('fit','comprador','con_quien'))
        self.assertEqual({k:b[k] for k in ('line','papel','segment','company_size','level','score','score_version')},
                         {'line':'projectapp','papel':'lider_tecnologia','segment':'retail_ecommerce','company_size':'20_a_200',
                          'level':'confirmado','score':99,'score_version':'buyer_score_v2'})
        self.assertEqual(c['stage_check']['senales'][0]['tipo'],'contrata_desarrolladores')
        journey=self.journey(tomas)
        self.assertEqual((journey.line,journey.segment,journey.entry_score_version),('projectapp','retail_ecommerce','buyer_score_v2'))

        follow=self.step_follow(tomas)
        self.assertEqual(follow.state,'confirmed')
        first,second=self.warm_up(tomas)
        self.plan()
        invite=self.approve_open(tomas,'RED-02')
        self.assertEqual(invite.state,'confirmed')
        tomas=self.step_accept(tomas)
        self.assertEqual(self.journey(tomas).step,'acepto')

        funnel=self.funnel()
        self.assertEqual((funnel['por_linea']['projectapp']['invitaciones'],funnel['por_linea']['startup']['invitaciones']),(1,0))
        self.assertEqual(funnel['por_segmento']['retail_ecommerce']['invitaciones'],1)
        self.assertEqual(funnel['prueba_projectapp']['por_segmento']['retail_ecommerce']['aceptaron'],1)
        from team_backend import lectura_embudo
        self.assertTrue(any(line.startswith('Prueba ProjectApp') for line in lectura_embudo.read(account=self.account)['lineas']))

    def test_a_partner_is_followed_commented_as_community_and_invited_without_a_journey_or_messages(self):
        from team_backend import projectapp
        from team_backend.models import BuyerDraft
        with patch.dict(os.environ,{'NETWORK_SEARCH_AUDIENCE_SHARE':'partner=12'}):
            marco=self.found('marco-agencia','Marco Agencia',self.AGENCY,'marketing agency founder development partners',
                             'Austin, Texas')
        c=marco.classification
        self.assertEqual((marco.stage,c['role'],c['fit'],c['modality']),('fit','partner',True,'projectapp'))
        self.assertNotIn('buyer',c);self.assertNotIn('stage_check',c)
        follow=self.step_follow(marco)
        self.assertEqual((follow.state,marco.stage),('confirmed','followed'))
        # His posts are read like a warming buyer's (within the buyers' read cap) and feed the «comunidad» share.
        self.their_new_post(marco,'We launched a booking site for a dental clinic with our development partner in six weeks.')
        self.observe()
        self.assertTrue(AuditEvent.objects.filter(action=projectapp.PARTNER_READ).exists())
        post=ObservedPost.objects.get(author_provider_id=marco.provider_user_id)
        self.assertIsNone(post.referent_id)
        comment=self.autopilot_comment('Six weeks for a booking flow is fast. What did the clinic stop doing by hand first?')
        self.assertEqual((comment.state,comment.post_id),('confirmed',post.pk))
        self.assertEqual(calentamiento.group_of(post,calentamiento.buyer_ids(self.account),projectapp.partner_ids(self.account)),'comunidad')
        self.assertEqual(calentamiento.used(self.account,timezone.now())['comunidad'],1)
        invite=self.step_invite(marco)
        self.assertEqual((invite.state,marco.stage),('confirmed','invited'))
        self.assertFalse(BuyerJourney.objects.filter(contact=marco).exists())
        self.assertFalse(BuyerDraft.objects.exists())
