"""Neighborhood network: discover, classify, follow, invite without note, accept; caps, gates and vetoes."""
import json
import os
from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth.models import User
from django.utils import timezone
from team_backend import autopiloto, jobs, operador, orquestacion, red
from team_backend.models import ActionExecution, ActionProposal, AuditEvent, Capture, Contact, CycleLedger, EditorialPiece, Job
from team_backend.tests.test_operador import OperatorBase

SUBSTANTIVE='The hard part is not the model, it is deciding which step of the sales workflow you automate first.'

class NetworkBase(OperatorBase):
    def setUp(self):
        super().setUp()
        env=patch.dict(os.environ,{'NETWORK_ENABLED':'true','NETWORK_SCAN_DAYS':'3650','NETWORK_SEARCH_QUERIES':'founder pre-seed',
                                   'NETWORK_INVITE_AFTER_HOURS':'48','NETWORK_DAILY_LLM_USD':'1','NETWORK_READ_CAPS':'',
                                   # The location and stage rules of 12/11/2026 have their own tests (test_red_eeuu).
                                   'NETWORK_BUYER_REGION':'','NETWORK_STAGE_CHECK':'false','NETWORK_SEARCH_LOCATION':'',
                                   'NETWORK_BATCHES':''})
        env.start();self.addCleanup(env.stop)
        self.bot,_=User.objects.get_or_create(username='barrio-autopiloto')
        self.grant(self.bot,'access_knowledge','run_agents','use_paid_providers','operate_linkedin','execute_actions')
        self.classifier_calls=[]

    def job(self,kind):
        jobs.enqueue_operation(self.bot,kind,{'account':str(self.account.id)})
        while jobs.process_one(self.worker):pass
        return Job.objects.filter(kind=kind).order_by('-created_at').first()

    def drain(self):
        while jobs.process_one(self.worker):pass

    def classifier(self,verdicts):
        """verdicts: {display_name: (fit, confidence)}"""
        def fake(system,message,max_tokens=None,output_schema=None,effort=None,purpose='agent-run',model=None,context=None):
            data=json.loads(message);self.classifier_calls.append({'purpose':purpose,'model':model,'data':data,'system':system,'context':context})
            out=[{'id':p['id'],'fit':verdicts[p['name']][0],'role':'comprador','modality':'projectapp','affinity':'desconocida',
                  'reason':f'Razón para {p["name"]}','confidence':verdicts[p['name']][1],'course_citations':['LI-03-M005-K06'], 'invitation_note':'','note_reason':''} for p in data['people'] if p['name'] in verdicts]
            return {'text':json.dumps({'contacts':out}),'model':model,'estimated_usd':0.002,'request_id':'req_net'}
        return patch('knowledge.providers.claude',side_effect=fake)

    def contact(self,public_id,name,stage='fit',followed_hours=None,fit=True):
        person=self.fake.seed_person(public_id,name,headline='Founder')
        contact=Contact.objects.create(account=self.account,provider_user_id=person['id'],display_name=name,source='manual',stage=stage,
            classification={'fit':fit,'role':'comprador','modality':'projectapp','affinity':'desconocida','reason':'r','confidence':0.9},
            followed_at=timezone.now()-timedelta(hours=followed_hours) if followed_hours is not None else None)
        return contact

    def approve_open(self,contact,capability):
        proposal=ActionProposal.objects.get(contact=contact,capability=capability,state='proposed')
        response=self.human.post(f'/api/v1/operador/actions/{proposal.id}/approve',{'expected_hash':proposal.payload_hash},format='json')
        self.assertEqual(response.status_code,202,response.content)
        self.drain()
        proposal.refresh_from_db();contact.refresh_from_db()
        return proposal


class StoppedCycleTests(NetworkBase):
    def cycle(self,reason='',piece=None):
        job=Job.objects.create(owner=self.bot,kind='prepare_piece' if piece else 'plan_network')
        run=orquestacion.Runtime.open('pieza_diaria' if piece else 'red',str(piece.id if piece else job.id),self.bot,job)
        if reason:run.stop(reason,business=False)
        return CycleLedger.objects.get(pk=run.id)

    def action(self,cycle=None,state='proposed'):
        contact=self.contact(f'person-{Contact.objects.count()}','Persona')
        return operador.create_proposal(self.bot,None,'RED-01',{'user_id':contact.provider_user_id},contact=contact,
            origin_job=str(cycle.job_id) if cycle else '',state=state)

    def piece_action(self):
        now=timezone.now()
        piece=EditorialPiece.objects.create(account=self.account,slot_date=now.date(),scheduled_for=now-timedelta(minutes=1),state='ready')
        return operador.create_proposal(self.bot,None,'CONT-09',{'text':'Pieza del día'},piece=piece,state='approved')

    def test_execution_skips_stopped_red_and_queues_younger_daily_piece(self):
        """A stopped oldest follow must neither retry its failed job nor block a younger CONT-09."""
        blocked=self.action(self.cycle('edge_limit'),'approved')
        failed=operador.enqueue_execution(self.bot,blocked)
        Job.objects.filter(pk=failed.pk).update(state='failed',error='Ciclo detenido: edge_limit')
        self.assertEqual(autopiloto._execute(self.bot,self.account,timezone.now()),0)
        self.assertEqual(autopiloto._execute(self.bot,self.account,timezone.now()+timedelta(minutes=1)),0)
        piece=self.piece_action()
        self.assertEqual(autopiloto._execute(self.bot,self.account,timezone.now()),1)
        queued=Job.objects.get(kind='execute_action',state='queued')
        self.assertEqual(queued.params,{'proposal':str(piece.id)})
        self.assertEqual(Job.objects.filter(kind='execute_action').count(),2)
        self.assertEqual(self.fake.state['writes'],0)

    def test_tick_expires_stopped_open_actions_once_and_keeps_other_cycles(self):
        """Stopped cycles close proposed/approved rows, but cost_cap, live cycles and executions survive."""
        stopped=self.cycle('edge_limit')
        proposed=self.action(stopped);approved=self.action(stopped,'approved')
        rejected=self.action(stopped,'rejected');executed=self.action(stopped,'approved')
        ActionExecution.objects.create(proposal=executed,idempotency_key=str(executed.id),provider='fake',
            executed_by=self.bot,state='failed',wrote=False)
        cost=self.cycle('cost_cap');cost_pending=self.action(cost);cost_approved=self.action(cost,'approved')
        running=self.action(self.cycle());complete=self.cycle()
        CycleLedger.objects.filter(pk=complete.pk).update(state='complete')
        completed=self.action(complete);legacy=self.action()
        stale=self.action();ActionProposal.objects.filter(pk=stale.pk).update(created_at=timezone.now()-timedelta(hours=49))
        self.account.paused=True;self.account.save()
        self.assertEqual(autopiloto.tick(self.bot)['expired'],3)
        for proposal in (proposed,approved):
            proposal.refresh_from_db()
            self.assertEqual((proposal.state,proposal.decision_note),('expired','Ciclo detenido: edge_limit'))
        for proposal,state in ((rejected,'rejected'),(executed,'approved'),(cost_pending,'proposed'),
                               (cost_approved,'approved'),(running,'proposed'),(completed,'proposed'),(legacy,'proposed')):
            proposal.refresh_from_db();self.assertEqual(proposal.state,state)
        stale.refresh_from_db();self.assertEqual(stale.decision_note,'Caducada sin ejecutar')
        self.assertEqual(autopiloto.tick(self.bot)['expired'],0)
        self.assertEqual(set(AuditEvent.objects.filter(action='operator.expired').values_list('target',flat=True)),
                         {str(proposed.id),str(approved.id),str(stale.id)})
        self.assertEqual(AuditEvent.objects.filter(action='operator.expired').count(),3)

    def test_a_deploy_does_not_stop_a_ready_post_at_its_gate(self):
        """10/11/2026: the 3:30 pm post ended «Ciclo detenido: graph_changed» because a deploy changed the graph while it
        waited for its hour. A finished cycle now runs its gate under the current graph."""
        from copy import deepcopy
        from team_backend.grafo import load_graph
        proposal=self.piece_action();ledger=self.cycle(piece=proposal.piece)
        CycleLedger.objects.filter(pk=ledger.pk).update(state='complete')
        graph=deepcopy(load_graph());graph['graph_version']='next'
        decision={'decision':'approve','reasons':['Jev aprueba'],'at':timezone.now().isoformat()}
        with patch('team_backend.orquestacion.load_graph',return_value=graph):
            self.assertEqual(orquestacion.review_gate(proposal,lambda:decision),decision)
        ledger.refresh_from_db()
        self.assertEqual((ledger.state,ledger.stop_reason,ledger.graph_version),('complete','','next'))
        self.assertEqual(orquestacion.cycle_issues(proposal),[])
        self.account.paused=True;self.account.save()  # the tick only expires here; it does not execute
        self.assertEqual(autopiloto.tick(self.bot)['expired'],0)
        proposal.refresh_from_db();self.assertEqual(proposal.state,'approved')

    def test_tick_releases_ideas_of_a_stopped_piece(self):
        """Expiring a stopped editorial cycle must return its ideas to the editorial table."""
        proposal=self.piece_action();self.cycle('graph_changed',proposal.piece)
        capture=Capture.objects.create(created_by=self.bot,state='usado',routed_to={'used_in':str(proposal.piece_id)})
        self.account.paused=True;self.account.save()
        self.assertEqual(autopiloto.tick(self.bot)['expired'],1)
        proposal.refresh_from_db();capture.refresh_from_db()
        self.assertEqual((proposal.state,proposal.decision_note),('expired','Ciclo detenido: graph_changed'))
        # An attempt is counted once per piece: two failed pieces leave it for the director.
        self.assertEqual((capture.state,capture.routed_to),('idea',{'intentos':1,'intentos_en':[str(proposal.piece_id)]}))
        self.assertEqual(capture.publish_asap_reason,'Vuelve a la mesa: Ciclo detenido: graph_changed')
        self.assertEqual(AuditEvent.objects.filter(action='operator.expired',target=str(proposal.id)).count(),1)


class PostOnTimeTests(NetworkBase):
    """Every write reserves a random gap of up to 40 min: a follow started just before his post would push it late."""
    def setUp(self):
        super().setUp()
        env=patch.dict(os.environ,{'OPERATOR_MIN_SPACING_SECONDS':'1200','OPERATOR_MAX_SPACING_SECONDS':'2400'})
        env.start();self.addCleanup(env.stop)

    def follow(self):
        contact=self.contact(f'person-{Contact.objects.count()}','Persona')
        proposal=operador.create_proposal(self.bot,None,'RED-01',{'user_id':contact.provider_user_id},contact=contact,state='approved')
        ActionProposal.objects.filter(pk=proposal.pk).update(approved_hash=proposal.payload_hash)
        return proposal

    def post(self,minutes):
        when=timezone.now()+timedelta(minutes=minutes)
        piece=EditorialPiece.objects.create(account=self.account,slot_date=when.date(),scheduled_for=when,state='ready')
        return operador.create_proposal(self.bot,None,'CONT-09',{'text':'Pieza del día'},piece=piece,state='approved')

    def test_a_follow_waits_while_his_post_is_inside_the_spacing_gap(self):
        follow=self.follow();post=self.post(30)
        self.assertEqual(operador.post_due().id,post.id)
        self.assertEqual(autopiloto._execute(self.bot,self.account,timezone.now()),0)
        self.assertFalse(Job.objects.filter(kind='execute_action').exists())  # no failed job retried every tick
        with self.assertRaisesMessage(operador.OperatorBlocked,'sale primero'):operador.execute(self.bot,follow.id)
        follow.refresh_from_db();self.assertEqual(follow.state,'approved')

    def test_his_post_goes_first_at_its_hour_and_the_follow_after(self):
        follow=self.follow();post=self.post(-1)
        self.assertEqual(autopiloto._execute(self.bot,self.account,timezone.now()),1)
        self.assertEqual(Job.objects.get(kind='execute_action',state='queued').params['proposal'],str(post.id))
        ActionProposal.objects.filter(pk=post.pk).update(state='executing')  # the post is out
        self.assertIsNone(operador.post_due())
        Job.objects.filter(kind='execute_action').update(state='complete')
        self.assertEqual(autopiloto._execute(self.bot,self.account,timezone.now()),1)
        self.assertEqual(Job.objects.get(kind='execute_action',state='queued').params['proposal'],str(follow.id))

    def test_a_post_beyond_the_gap_does_not_hold_the_network(self):
        follow=self.follow();self.post(45)
        self.assertIsNone(operador.post_due())
        self.assertEqual(autopiloto._execute(self.bot,self.account,timezone.now()),1)
        self.assertEqual(Job.objects.get(kind='execute_action',state='queued').params['proposal'],str(follow.id))


class NetworkPlanLimitTests(NetworkBase):
    def test_ten_follows_are_split_across_cycles_at_the_graph_limit(self):
        """Ten eligible follows must not create a sixth politica_red review in one cycle."""
        for i in range(10):self.contact(f'candidate-{i}',f'Candidato {i}')
        first=self.job('plan_network')
        limit=next(e['max_calls_per_cycle'] for e in orquestacion.load_graph()['edges'] if e['id']=='politica_red')
        self.assertEqual(first.state,'complete')
        self.assertEqual(ActionProposal.objects.filter(origin_job=str(first.id)).count(),limit)
        self.assertEqual(Contact.objects.filter(proposals__isnull=True,stage='fit').count(),10-limit)
        second=self.job('plan_network')
        self.assertEqual(second.state,'complete')
        self.assertEqual(ActionProposal.objects.filter(origin_job=str(second.id)).count(),10-limit)
        self.assertEqual(ActionProposal.objects.count(),10)

    def test_follow_invite_and_accept_share_the_loaded_edge_limit(self):
        """The graph's limit applies to RED-01 + RED-02 + RED-04, not to each independently."""
        self.contact('follow','Seguir')
        self.contact('invite','Invitar',stage='followed',followed_hours=49)
        for i in range(2):
            contact=self.contact(f'accept-{i}',f'Aceptar {i}',stage='incoming')
            contact.invitation_id=f'invitation-{i}';contact.save()
        graph=orquestacion.load_graph()
        next(e for e in graph['edges'] if e['id']=='politica_red')['max_calls_per_cycle']=3
        with patch('team_backend.orquestacion.load_graph',return_value=graph):
            first=red.plan(self.bot,self.account)
            second=red.plan(self.bot,self.account)
        self.assertEqual([first[k] for k in ('follow','invite','accept')],[1,1,1])
        self.assertEqual([second[k] for k in ('follow','invite','accept')],[0,0,1])
        self.assertEqual(ActionProposal.objects.count(),4)

    def test_planning_again_in_the_same_cycle_does_not_replenish_review_slots(self):
        """A second plan invocation in the same cycle must count proposals it already created."""
        for i in range(10):self.contact(f'candidate-{i}',f'Candidato {i}')
        job=Job.objects.create(owner=self.bot,kind='plan_network')
        runtime=orquestacion.Runtime.open('red',str(job.id),self.bot,job)
        limit=next(e['max_calls_per_cycle'] for e in runtime.graph['edges'] if e['id']=='politica_red')
        with runtime.session():
            first=red.plan(self.bot,self.account)
            second=red.plan(self.bot,self.account)
        self.assertEqual((first['follow'],second['follow']),(limit,0))
        self.assertEqual(ActionProposal.objects.filter(origin_job=str(job.id)).count(),limit)


class DiscoveryAndFollowTests(NetworkBase):
    def test_discovers_commenters_and_search_classifies_and_follows_after_approval(self):
        posts=self.observed()
        self.fake.seed_person('founder-ana','Ana Founder',headline='Co-founder & CEO at Tiny (pre-seed)',
                              comment_on=posts[0].provider_post_id,comment=SUBSTANTIVE)
        self.fake.seed_person('saludo-bob','Bob Saludo',comment_on=posts[0].provider_post_id,comment='Gran post!')
        self.fake.seed_person('empresa-x','Empresa X',comment_on=posts[0].provider_post_id,comment=SUBSTANTIVE,kind='organization')
        self.fake.seed_person('cto-carla','Carla CTO',headline='CTO',search='founder pre-seed')
        self.fake.seed_person('amigo-dan','Dan Amigo',distance='FIRST_DEGREE',search='founder pre-seed')
        self.job('discover_network')
        found={c.display_name:c for c in Contact.objects.all()}
        self.assertEqual(set(found),{'Ana Founder','Carla CTO'})  # no greeting, organization, 1st degree or referent
        ana=found['Ana Founder']
        self.assertEqual((ana.source,ana.stage,ana.evidence['referent'],ana.evidence['comment']),('commenter','candidate','Ana Referente',SUBSTANTIVE))
        self.assertEqual(found['Carla CTO'].evidence,{'query':'founder pre-seed'})
        self.job('discover_network')  # posts are scanned once: no duplicates
        self.assertEqual(Contact.objects.count(),2)

        with self.classifier({'Ana Founder':(True,0.9),'Carla CTO':(True,0.5)}):self.job('classify_contacts')
        call=self.classifier_calls[0]
        self.assertEqual((call['purpose'],call['model']),('network-classify','claude-sonnet-5-5'))
        # Comment authors come without a headline: the profile is read first (1 read; the search result already had one).
        headlines={p['name']:p['headline'] for p in call['data']['people']}
        self.assertEqual(headlines,{'Ana Founder':'Co-founder & CEO at Tiny (pre-seed)','Carla CTO':'CTO'})
        self.assertEqual(red.reads_today(self.account,'profile'),1)
        self.assertIn('Nunca la infieras por nombre',call['system'])
        self.assertIn('brief.prioridad',{g['key'] for g in call['data']['private_guidance']})
        ana.refresh_from_db()
        self.assertEqual(ana.stage,'fit');self.assertEqual(Contact.objects.get(display_name='Carla CTO').stage,'discarded')  # below 0.6

        self.job('plan_network')
        follow=ActionProposal.objects.get(contact=ana)
        self.assertEqual((follow.capability,follow.state,follow.payload),('RED-01','proposed',{'user_id':'ACofounder-ana'}))
        autopiloto.tick(self.bot);self.drain()  # RED-* wait for Gustavo by default
        follow.refresh_from_db();self.assertEqual(follow.state,'proposed');self.assertEqual(self.fake.state['writes'],0)

        listed=self.human.get('/api/v1/operador/actions?capability=RED-01').json()['results'][0]
        self.assertEqual((listed['post'],listed['contact']['display_name'],listed['contact']['evidence']['referent']),(None,'Ana Founder','Ana Referente'))
        contact_json=self.human.get('/api/v1/red/contacts?stage=fit').json()['results'][0]
        self.assertEqual(contact_json['open_action']['capability'],'RED-01')

        follow=self.approve_open(ana,'RED-01')
        self.assertEqual(follow.state,'confirmed');self.assertEqual(ana.stage,'followed');self.assertIsNotNone(ana.followed_at)
        self.assertEqual(self.fake.state['writes'],1)
        self.job('plan_network')  # nothing new: the warm-up has not passed
        self.assertEqual(ActionProposal.objects.filter(contact=ana).count(),1)

    def test_read_caps_stop_discovery(self):
        posts=self.observed()
        for i,post in enumerate(posts):
            self.fake.seed_person(f'persona-{i}',f'Persona {i}',comment_on=post.provider_post_id,comment=SUBSTANTIVE)
        with patch.dict(os.environ,{'NETWORK_READ_CAPS':'comments=1,search=0'}):job=self.job('discover_network')
        self.assertEqual(Contact.objects.count(),1);self.assertIn('Tope diario',job.error)
        summary=self.human.get('/api/v1/red/summary').json()
        self.assertEqual(summary['reads_today']['comments'],1)
        self.assertEqual(summary['capacity']['RED-02']['mode'],'approval')


class InvitationTests(NetworkBase):
    def test_invitation_waits_for_the_warm_up_goes_without_note_and_sync_settles_it(self):
        eva=self.contact('founder-eva','Eva Founder',stage='followed',followed_hours=1)
        self.job('plan_network');self.assertFalse(ActionProposal.objects.filter(contact=eva).exists())
        Contact.objects.filter(pk=eva.pk).update(followed_at=timezone.now()-timedelta(hours=49))
        self.job('plan_network')
        invite=ActionProposal.objects.get(contact=eva)
        self.assertEqual((invite.capability,invite.payload),('RED-02',{'user_id':'ACofounder-eva'}))
        invite=self.approve_open(eva,'RED-02')
        self.assertEqual((invite.state,eva.stage),('confirmed','invited'))
        self.assertEqual(self.fake.state['invitations']['sent'][eva.invitation_id]['message'],'')  # no note
        self.job('plan_network');self.assertEqual(ActionProposal.objects.filter(contact=eva).count(),1)  # never twice
        self.fake.accept_sent('ACofounder-eva')
        self.job('sync_network');eva.refresh_from_db()
        self.assertEqual(eva.stage,'connected');self.assertIsNotNone(eva.connected_at)

    def test_a_limit_refusal_pauses_invitations_for_a_week(self):
        eva=self.contact('founder-eva','Eva Founder',stage='followed',followed_hours=60)
        self.job('plan_network')
        proposal=ActionProposal.objects.get(contact=eva,capability='RED-02')
        ActionExecution.objects.create(proposal=proposal,idempotency_key='k',provider='fake',executed_by=self.gustavo,state='failed',
                                       error_kind='provider/limit_exceeded')
        self.assertTrue(red.invites_blocked()[0])
        other=self.contact('founder-ivo','Ivo Founder',stage='followed',followed_hours=60)
        self.job('plan_network');self.assertFalse(ActionProposal.objects.filter(contact=other).exists())
        self.assertTrue(self.human.get('/api/v1/red/summary').json()['invites_blocked']['blocked'])

    def test_previous_ignored_invitation_closes_the_person(self):
        eva=self.contact('founder-eva','Eva Founder',stage='followed',followed_hours=60)
        self.fake.state['network']['ACofounder-eva']['relation_request_status']='IGNORED'
        self.job('plan_network')  # the plan reads nothing (audit R1): the execution's pre-check closes the person
        invite=self.approve_open(eva,'RED-02')
        self.assertEqual((invite.state,invite.execution.error_kind,invite.execution.wrote),('failed','previous_invitation',False))
        self.assertEqual(eva.stage,'closed');self.assertEqual(self.fake.state['writes'],0)
        self.job('plan_network');self.assertEqual(ActionProposal.objects.filter(contact=eva).count(),1)  # never re-invited


class IncomingTests(NetworkBase):
    def test_received_invitation_is_accepted_only_when_the_person_fits(self):
        self.fake.seed_person('founder-eva','Eva Founder',headline='Founder at Seedco');self.fake.seed_person('vendedor-fred','Fred Ventas')
        self.fake.receive_invitation('ACofounder-eva','Hola Gustavo');self.fake.receive_invitation('ACovendedor-fred')
        self.job('sync_network')
        self.assertEqual(set(Contact.objects.filter(stage='incoming').values_list('display_name',flat=True)),{'Eva Founder','Fred Ventas'})
        with self.classifier({'Eva Founder':(True,0.8),'Fred Ventas':(False,0.9)}):self.job('classify_contacts')
        self.job('plan_network')
        accept=ActionProposal.objects.get(capability='RED-04')
        self.assertEqual(accept.contact.display_name,'Eva Founder')
        with patch.dict(os.environ,{'OPERATOR_AUTONOMY':'RED-04=auto'}):
            autopiloto.tick(self.bot);self.drain()
        accept.refresh_from_db();eva=accept.contact;eva.refresh_from_db()
        self.assertEqual((accept.state,accept.decision_note),('confirmed','Aprobada por política autonomia-v1'))
        self.assertEqual(eva.stage,'connected')
        self.assertEqual(Contact.objects.get(display_name='Fred Ventas').stage,'incoming')  # left pending, never declined
        self.assertEqual(self.fake.state['writes'],1)


class VetoAndSafetyTests(NetworkBase):
    def test_rejecting_or_discarding_a_person_is_final(self):
        ana=self.contact('founder-ana','Ana Founder')
        self.job('plan_network')
        proposal=ActionProposal.objects.get(contact=ana)
        response=self.human.post(f'/api/v1/operador/actions/{proposal.id}/reject',{'note':'No es mi público'},format='json')
        self.assertEqual(response.status_code,200,response.content)
        ana.refresh_from_db();self.assertEqual(ana.stage,'discarded')
        self.job('plan_network');self.assertEqual(ActionProposal.objects.filter(contact=ana).count(),1)

        carla=self.contact('cto-carla','Carla CTO')
        self.job('plan_network')
        self.assertEqual(self.api.post(f'/api/v1/red/contacts/{carla.id}/discard',{'note':'x'},format='json').status_code,403)
        self.assertEqual(self.human.post(f'/api/v1/red/contacts/{carla.id}/discard',{},format='json').status_code,400)
        body=self.human.post(f'/api/v1/red/contacts/{carla.id}/discard',{'note':'Ya la conozco'},format='json').json()
        self.assertEqual((body['stage'],body['open_action']),('discarded',None))
        self.assertEqual(ActionProposal.objects.get(contact=carla).state,'rejected')
        self.assertEqual(self.human.post(f'/api/v1/red/contacts/{carla.id}/discard',{'note':'otra vez'},format='json').status_code,409)
        self.assertEqual(self.fake.state['writes'],0)

    def test_uncertain_follow_is_reconciled_by_reading_the_profile_never_repeated(self):
        ana=self.contact('founder-ana','Ana Founder')
        self.job('plan_network')
        self.fake.state['fail_next']='uncertain_applied'
        follow=self.approve_open(ana,'RED-01')
        self.assertEqual(follow.state,'uncertain');self.assertEqual(self.fake.state['writes'],1)
        ActionExecution.objects.filter(proposal=follow).update(started_at=timezone.now()-timedelta(minutes=20))
        autopiloto.tick(self.bot);self.drain()
        follow.refresh_from_db();ana.refresh_from_db()
        self.assertEqual((follow.state,ana.stage),('confirmed','followed'));self.assertEqual(self.fake.state['writes'],1)

    def test_policy_gate_and_autopilot_queue(self):
        ana=self.contact('founder-ana','Ana Founder',fit=False)
        proposal=red._propose(self.bot,ana,'RED-01',{'user_id':ana.provider_user_id})
        with patch.dict(os.environ,{'OPERATOR_AUTONOMY':'RED-01=auto'}):autopiloto.policy_review(proposal)
        proposal.refresh_from_db()
        self.assertEqual(proposal.state,'discarded');self.assertIn('La clasificación no confirma que encaje',proposal.risks)
        with self.assertRaises(ValueError):red.operador.validate_payload('RED-02',{'user_id':'ACo1','message':'Hola'})
        report=autopiloto.tick(self.bot)
        self.assertGreaterEqual(report['network'],3)  # discover, plan and sync (classify only with unclassified people)
        self.assertEqual(set(Job.objects.filter(state='queued').values_list('kind',flat=True))&{'discover_network','plan_network','sync_network'},
                         {'discover_network','plan_network','sync_network'})
        self.assertEqual(autopiloto.tick(self.bot)['network'],0)  # one job of each kind at a time
        with patch.dict(os.environ,{'NETWORK_ENABLED':'false'}):
            Job.objects.all().delete();self.assertEqual(autopiloto.tick(self.bot).get('network',0),0)


class CommentRoomTests(NetworkBase):
    def test_network_proposals_do_not_use_up_the_daily_comment_drafts(self):
        for i in range(7):self.contact(f'persona-{i}',f'Persona {i}')
        self.job('plan_network')
        # One cycle proposes at most what politica_red can review (5); the daily drafts cap is set to that same number.
        self.assertEqual(ActionProposal.objects.filter(capability='RED-01').count(),5)
        self.observed()
        with patch.dict(os.environ,{'OPERATOR_DAILY_PROPOSALS':'5'}),\
             patch('team_backend.autopiloto.enqueue_operation',wraps=autopiloto.enqueue_operation) as enqueue:
            autopiloto.tick(self.bot)
        self.assertIn('propose_comment',[c.args[1] for c in enqueue.call_args_list])


class EnrichmentTests(NetworkBase):
    def test_commenters_without_a_readable_profile_wait_instead_of_being_judged_blind(self):
        posts=self.observed()
        self.fake.seed_person('founder-ana','Ana Founder',headline='Founder',comment_on=posts[0].provider_post_id,comment=SUBSTANTIVE)
        with patch.dict(os.environ,{'NETWORK_SEARCH_QUERIES':''}):self.job('discover_network')
        with patch.dict(os.environ,{'NETWORK_READ_CAPS':'profile=0'}),self.classifier({'Ana Founder':(True,0.9)}):
            job=self.job('classify_contacts')
        self.assertEqual(self.classifier_calls,[]);self.assertIn('mañana',job.error)
        self.assertEqual(Contact.objects.get().classification,{})
        with self.classifier({'Ana Founder':(True,0.9)}):self.job('classify_contacts')
        self.assertEqual(Contact.objects.get().stage,'fit')

    def test_commenters_leave_room_for_the_search(self):
        posts=self.observed()
        for i in range(12):
            self.fake.seed_person(f'persona-{i}',f'Persona {i}',comment_on=posts[0].provider_post_id,comment=SUBSTANTIVE)
        self.fake.seed_person('cto-carla','Carla CTO',headline='CTO',search='founder pre-seed')
        self.job('discover_network')
        self.assertEqual(Contact.objects.filter(source='commenter').count(),10)
        self.assertTrue(Contact.objects.filter(source='search').exists())
