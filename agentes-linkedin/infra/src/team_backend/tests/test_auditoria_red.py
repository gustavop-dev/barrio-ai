"""Phase 2 of the AI architecture audit, network slice (docs/auditoria-arquitectura-ia.md): R1, R2 and B4."""
import os
from datetime import timedelta
from unittest.mock import patch

from django.utils import timezone

from team_backend import autopiloto, operador, red
from team_backend.connectors import ConnectorError, FakeConnector
from team_backend.models import ActionExecution, ActionProposal, AuditEvent, Contact, Job
from team_backend.tests.test_red import SUBSTANTIVE, NetworkBase


def execution_reads(account):
    return list(AuditEvent.objects.filter(action='network.read',target=str(account.id),metadata__kind='execution')
                .order_by('created_at').values_list('metadata__read',flat=True))


class PlanWithoutReadsTests(NetworkBase):
    """R1: the plan reads no profile; the execution's pre-check covers every state and its reads are counted."""

    def test_the_plan_reads_nothing_and_an_already_followed_person_starts_the_warm_up(self):
        ana=self.contact('founder-ana','Ana Founder')
        self.fake.state['network'][ana.provider_user_id]['is_following']=True
        self.job('plan_network')
        self.assertFalse(AuditEvent.objects.filter(action='network.read').exists())
        follow=self.approve_open(ana,'RED-01')
        self.assertEqual((follow.state,follow.execution.wrote),('confirmed',False))
        self.assertEqual(ana.stage,'followed');self.assertIsNotNone(ana.followed_at)  # the invite clock starts
        self.assertEqual(self.fake.state['writes'],0)
        self.assertEqual(execution_reads(self.account),['profile'])  # the pre-check only

    def test_a_follow_counts_its_pre_check_and_read_back_and_no_read_cap_stops_them(self):
        ana=self.contact('founder-ana','Ana Founder')
        with patch.dict(os.environ,{'NETWORK_READ_CAPS':'comments=0,search=0,profile=0,sync=0'}):
            self.job('plan_network')
            follow=self.approve_open(ana,'RED-01')
            summary=self.human.get('/api/v1/red/summary').json()
        self.assertEqual((follow.state,follow.execution.wrote,ana.stage),('confirmed',True,'followed'))
        self.assertEqual(self.fake.state['writes'],1)
        self.assertEqual(execution_reads(self.account),['profile','profile'])
        self.assertEqual((summary['reads_today']['execution'],summary['reads_today']['profile']),(2,0))
        self.assertNotIn('execution',summary['read_caps'])  # counted, never capped

    def test_the_follow_pre_check_settles_every_state_without_writing(self):
        cases={'founder-con':({'network_distance':'FIRST_DEGREE'},'connected','already_connected'),
               'founder-pen':({'relation_request_status':'PENDING'},'invited','invitation_pending'),
               'founder-ign':({'relation_request_status':'IGNORED'},'closed','previous_invitation'),
               'founder-wit':({'relation_request_status':'WITHDRAWN'},'closed','previous_invitation')}
        people={slug:self.contact(slug,slug.title()) for slug in cases}
        for slug,(state,_,_) in cases.items():self.fake.state['network'][people[slug].provider_user_id].update(state)
        with patch.dict(os.environ,{'OPERATOR_DAILY_LIMITS':'RED-01=4'}):
            self.job('plan_network')
            for slug,(_,stage,kind) in cases.items():
                with self.subTest(slug):
                    follow=self.approve_open(people[slug],'RED-01')
                    self.assertEqual((follow.state,follow.execution.error_kind,follow.execution.wrote),('failed',kind,False))
                    self.assertEqual(people[slug].stage,stage)
            self.assertEqual(operador.capacity_left(self.account,'RED-01'),4)
        self.assertIsNotNone(people['founder-con'].connected_at);self.assertIsNotNone(people['founder-pen'].invited_at)
        self.assertEqual(self.fake.state['writes'],0)
        self.job('plan_network');self.assertEqual(ActionProposal.objects.filter(capability='RED-01').count(),4)  # none again

    def test_a_connection_already_followed_stays_connected_and_a_restricted_profile_is_discarded(self):
        carla=self.contact('cto-carla','Carla CTO')
        self.fake.state['network'][carla.provider_user_id].update(network_distance='FIRST_DEGREE',is_following=True)
        self.job('plan_network')
        follow=self.approve_open(carla,'RED-01')
        self.assertEqual((follow.state,carla.stage,carla.is_following),('confirmed','connected',True))

        ana=self.contact('founder-ana','Ana Founder')
        self.job('plan_network')
        read=FakeConnector.get_profile
        with patch.object(FakeConnector,'get_profile',autospec=True,side_effect=lambda conn,uid:dict(read(conn,uid),is_restricted=True)):
            follow=self.approve_open(ana,'RED-01')
        self.assertEqual((follow.state,follow.execution.error_kind,ana.stage),('failed','restricted','discarded'))
        self.assertEqual(self.fake.state['writes'],0)

    def test_the_invite_pre_check_settles_connections_pending_invitations_and_people_out_of_reach(self):
        con=self.contact('founder-con','Con Founder',stage='followed',followed_hours=60)
        pen=self.contact('founder-pen','Pen Founder',stage='followed',followed_hours=60)
        far=self.contact('founder-far','Far Founder',stage='followed',followed_hours=60)
        self.fake.state['network'][con.provider_user_id]['network_distance']='FIRST_DEGREE'
        self.fake.state['network'][pen.provider_user_id]['relation_request_status']='PENDING'
        self.fake.state['network'][far.provider_user_id]['network_distance']='OUT_OF_NETWORK'
        self.job('plan_network')
        invite=self.approve_open(con,'RED-02')
        self.assertEqual((invite.state,invite.execution.error_kind,con.stage),('failed','already_connected','connected'))
        invite=self.approve_open(pen,'RED-02')
        self.assertEqual((invite.state,invite.execution.wrote,pen.stage),('confirmed',False,'invited'))
        invite=self.approve_open(far,'RED-02')
        self.assertEqual((invite.state,invite.execution.error_kind,invite.execution.wrote),('failed','out_of_network',False))
        self.assertEqual(far.stage,'followed');self.assertEqual(far.history[-1]['detail'],'Fuera de la red alcanzable; no se invita.')
        self.assertEqual(self.fake.state['writes'],0)
        # Without a refresh in the plan, the person out of reach rests instead of being proposed every hour.
        self.job('plan_network');self.assertEqual(ActionProposal.objects.filter(contact=far).count(),1)
        ActionExecution.objects.filter(proposal=invite).update(started_at=timezone.now()-timedelta(hours=49))
        self.job('plan_network');self.assertEqual(ActionProposal.objects.filter(contact=far).count(),2)

    def test_a_failed_pre_check_read_writes_nothing_and_uses_neither_cap_nor_spacing(self):
        ana=self.contact('founder-ana','Ana Founder')
        with patch.dict(os.environ,{'OPERATOR_DAILY_LIMITS':'RED-01=1'}):
            self.job('plan_network')
            down=ConnectorError('Simulado: HTTP 500.',status=500,kind='provider/server_error')
            with patch.object(FakeConnector,'get_profile',side_effect=down),patch.object(FakeConnector,'follow_user') as follow_user:
                follow=self.approve_open(ana,'RED-01')
            follow_user.assert_not_called()  # a write never goes without its pre-check
            self.assertEqual((follow.state,follow.execution.wrote,follow.execution.error_kind),('failed',False,'provider/server_error'))
            self.assertEqual(operador.capacity_left(self.account,'RED-01'),1)
            with patch.dict(os.environ,{'OPERATOR_MIN_SPACING_SECONDS':'1200'}):self.assertTrue(operador.spacing_ok(self.account))
            self.assertEqual(ana.stage,'fit')
            self.job('plan_network');self.assertEqual(ActionProposal.objects.filter(contact=ana).count(),1)  # it rests

    def test_accepting_counts_the_invitation_check_and_the_read_back(self):
        self.fake.seed_person('founder-eva','Eva Founder',headline='Founder at Seedco')
        self.fake.receive_invitation('ACofounder-eva','Hola Gustavo');self.job('sync_network')
        with self.classifier({'Eva Founder':(True,0.8)}):self.job('classify_contacts')
        AuditEvent.objects.filter(action='network.read').delete()
        self.job('plan_network')
        eva=Contact.objects.get(display_name='Eva Founder')
        accept=self.approve_open(eva,'RED-04')
        self.assertEqual((accept.state,eva.stage),('confirmed','connected'))
        self.assertEqual(execution_reads(self.account),['invitations','profile'])


class SingleFitJudgeTests(NetworkBase):
    """R2: the classifier is the single judge of fit; the lead only weighs risk (and the orientation) for RED-*."""

    def setUp(self):
        super().setUp()
        env=patch.dict(os.environ,{'LEAD_ENABLED':'true','OPERATOR_AUTONOMY':'RED-01=auto,RED-02=auto,RED-04=auto'})
        env.start();self.addCleanup(env.stop)
        self.asked=[]
        def jev(state,questions,purpose='lead-review'):
            self.asked.append({'state':state,'questions':questions})
            return {'answers':{q:{'noul':0.1 if q=='riesgo' else 0.9} for q in questions},'model':'jev-1.14.0','estimated_usd':0.00003}
        typesafe=patch('knowledge.providers.typesafe',side_effect=jev);typesafe.start();self.addCleanup(typesafe.stop)

    def test_the_lead_asks_only_risk_for_every_network_action(self):
        thresholds={'RED-01':0.3,'RED-02':0.2,'RED-04':0.3}
        for capability,threshold in thresholds.items():
            with self.subTest(capability):
                contact=self.contact(f'founder-{capability.lower()}',f'Founder {capability}',
                                     stage='incoming' if capability=='RED-04' else 'fit')
                payload={'request_id':'inv:1','user_id':contact.provider_user_id} if capability=='RED-04' else {'user_id':contact.provider_user_id}
                if capability=='RED-04':Contact.objects.filter(pk=contact.pk).update(invitation_id='inv:1')
                proposal=operador.create_proposal(self.bot,None,capability,payload,source='agent',contact=Contact.objects.get(pk=contact.pk))
                autopiloto.policy_review(proposal);proposal.refresh_from_db()
                self.assertEqual(set(self.asked[-1]['questions']),{'riesgo'})
                self.assertIn('criterios_del_barrio',self.asked[-1]['state'])
                self.assertEqual((proposal.state,proposal.review['thresholds']),('approved',{'riesgo':['max',threshold]}))
        self.human.put('/api/v1/orientacion',{'text':'Priorizar founders técnicos.'},format='json')
        proposal=red._propose(self.bot,self.contact('founder-ori','Ori Founder'),'RED-01',{'user_id':'ACofounder-ori'})
        autopiloto.policy_review(proposal)
        self.assertEqual(set(self.asked[-1]['questions']),{'riesgo','orientacion'})

    def test_a_low_risk_never_stands_in_for_the_classifier(self):
        ana=self.contact('founder-ana','Ana Founder',fit=False)
        proposal=red._propose(self.bot,ana,'RED-01',{'user_id':ana.provider_user_id})
        autopiloto.policy_review(proposal);proposal.refresh_from_db()
        self.assertEqual(proposal.state,'discarded');self.assertIn('La clasificación no confirma que encaje',proposal.risks)
        self.assertEqual(self.asked,[])  # the lead is not even asked

    def test_an_incoming_invitation_is_accepted_only_after_the_classifier_says_it_fits(self):
        self.fake.seed_person('founder-eva','Eva Founder',headline='Founder at Seedco')
        self.fake.receive_invitation('ACofounder-eva','Hola Gustavo');self.job('sync_network')
        eva=Contact.objects.get(display_name='Eva Founder')
        self.assertEqual((eva.stage,eva.classification),('incoming',{}))
        self.job('plan_network');self.assertFalse(ActionProposal.objects.filter(contact=eva).exists())  # never classified
        # Even a proposal made by hand is stopped by the deterministic gate before the lead.
        unjudged=red._propose(self.bot,eva,'RED-04',{'request_id':eva.invitation_id,'user_id':eva.provider_user_id})
        autopiloto.policy_review(unjudged);unjudged.refresh_from_db()
        self.assertEqual(unjudged.state,'discarded');self.assertEqual(self.asked,[])
        with self.classifier({'Eva Founder':(True,0.8)}):self.job('classify_contacts')
        eva.refresh_from_db();self.assertEqual((eva.stage,eva.classification['fit']),('incoming',True))
        self.job('plan_network')
        accept=ActionProposal.objects.get(contact=eva,state='proposed')
        autopiloto.policy_review(accept);accept.refresh_from_db()
        self.assertEqual((accept.capability,accept.state),('RED-04','approved'))
        self.assertEqual(set(self.asked[-1]['questions']),{'riesgo'})


class DiscoveryBacklogTests(NetworkBase):
    """B4: discovery waits while the unclassified backlog is full and never queues beyond it."""

    def unclassified(self,slug):
        contact=self.contact(slug,slug.title(),stage='candidate')
        Contact.objects.filter(pk=contact.pk).update(classification={})
        return contact

    def test_the_default_backlog_is_40_and_incoming_people_do_not_count(self):
        self.assertEqual(red.discovery_room(self.account),40)
        incoming=self.contact('founder-inc','Inc Founder',stage='incoming')
        Contact.objects.filter(pk=incoming.pk).update(classification={})
        self.unclassified('founder-one')
        self.assertEqual(red.discovery_room(self.account),39)

    def test_discovery_waits_for_the_backlog_and_never_overfills_it(self):
        posts=self.observed()
        for i in range(3):self.fake.seed_person(f'persona-{i}',f'Persona {i}',comment_on=posts[0].provider_post_id,comment=SUBSTANTIVE)
        first,_=self.unclassified('founder-one'),self.unclassified('founder-two')
        with patch.dict(os.environ,{'NETWORK_DISCOVER_MAX_BACKLOG':'2','NETWORK_SEARCH_QUERIES':''}):
            autopiloto._network(self.bot,self.account,timezone.now())
            queued=set(Job.objects.filter(state='queued').values_list('kind',flat=True))
            self.assertNotIn('discover_network',queued);self.assertIn('classify_contacts',queued)
            summary=red.discover(self.bot,self.account)
            self.assertEqual(summary['new'],0);self.assertIn('2 candidatos esperan',summary['held'])
            self.assertEqual(red.reads_today(self.account,'comments'),0)  # nothing read while waiting
            Contact.objects.filter(pk=first.pk).update(classification={'fit':False},stage='discarded')
            summary=red.discover(self.bot,self.account)
            self.assertEqual(summary['new'],1);self.assertEqual(red.unclassified_backlog(self.account),2)
            Job.objects.all().delete();Contact.objects.filter(stage='candidate').update(classification={'fit':False},stage='discarded')
            autopiloto._network(self.bot,self.account,timezone.now())
            self.assertTrue(Job.objects.filter(kind='discover_network',state='queued').exists())
