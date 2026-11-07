"""Neighborhood network: discover, classify, follow, invite without note, accept; caps, gates and vetoes."""
import json
import os
from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth.models import User
from django.utils import timezone
from team_backend import autopiloto, jobs, red
from team_backend.models import ActionExecution, ActionProposal, Contact, Job
from team_backend.tests.test_operador import OperatorBase

SUBSTANTIVE='The hard part is not the model, it is deciding which step of the sales workflow you automate first.'

class NetworkBase(OperatorBase):
    def setUp(self):
        super().setUp()
        env=patch.dict(os.environ,{'NETWORK_ENABLED':'true','NETWORK_SCAN_DAYS':'3650','NETWORK_SEARCH_QUERIES':'founder pre-seed',
                                   'NETWORK_INVITE_AFTER_HOURS':'48','NETWORK_DAILY_LLM_USD':'1','NETWORK_READ_CAPS':''})
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
        def fake(system,message,max_tokens=None,output_schema=None,effort=None,purpose='agent-run',model=None):
            data=json.loads(message);self.classifier_calls.append({'purpose':purpose,'model':model,'data':data,'system':system})
            out=[{'id':p['id'],'fit':verdicts[p['name']][0],'role':'comprador','modality':'projectapp','affinity':'desconocida',
                  'reason':f'Razón para {p["name"]}','confidence':verdicts[p['name']][1]} for p in data['people'] if p['name'] in verdicts]
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


class DiscoveryAndFollowTests(NetworkBase):
    def test_discovers_commenters_and_search_classifies_and_follows_after_approval(self):
        posts=self.observed()
        self.fake.seed_person('founder-ana','Ana Founder',headline='Co-founder & CEO at Tiny (pre-seed)',
                              comment_on=posts[0].provider_post_id,comment=SUBSTANTIVE)
        self.fake.seed_person('saludo-bob','Bob Saludo',comment_on=posts[0].provider_post_id,comment='Gran post!')
        org=self.fake.seed_person('empresa-x','Empresa X',comment_on=posts[0].provider_post_id,comment=SUBSTANTIVE)
        org['type']='organization'
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
        self.job('plan_network');eva.refresh_from_db()
        self.assertEqual(eva.stage,'closed');self.assertFalse(ActionProposal.objects.filter(contact=eva).exists())


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
        self.assertEqual(ActionProposal.objects.filter(capability='RED-01').count(),7)
        self.observed()
        with patch('team_backend.autopiloto.enqueue_operation',wraps=autopiloto.enqueue_operation) as enqueue:
            autopiloto.tick(self.bot)
        self.assertIn('propose_comment',[c.args[1] for c in enqueue.call_args_list])
