"""The neighborhood in the United States (Gustavo, 12/11/2026): location and profile signals, the web check of a buyer's
stage, the lead's rest and his «Sí, encaja», invitations first and in order, the two network rounds, the new ramp and
the extraordinary referent review. Synthetic people and sources only."""
import importlib
import json
import os
from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.apps import apps
from django.test import SimpleTestCase
from django.utils import timezone

from team_backend import autopiloto, operador, orquestacion, red, referentes, research, ubicacion
from team_backend.connectors import UnipileConnector, _signals
from team_backend.jobs import Conflict
from team_backend.models import (ActionProposal, Contact, Notification, ReferentControl, ReferentReview,
                                 WebResearchRun)
from team_backend.tests.test_red import NetworkBase

BOGOTA=ZoneInfo('America/Bogota')
# A search that ran and found nothing citable (it has usage); one that did not run has none.
NOTHING=research.ResearchResult('q','unavailable','2026-11-12T00:00:00+00:00',usage={'model':'claude-sonnet-5-5'})


class LocationTests(SimpleTestCase):
    def test_region_reads_states_metros_and_latin_america(self):
        cases={'Miami, Florida, United States':'us','San Francisco Bay Area':'us','Atlanta, Georgia':'us','New Mexico':'us',
               'Greater Seattle Area':'us','Estados Unidos':'us','Bogotá, D.C., Capital District, Colombia':'latam',
               'San José, Costa Rica':'latam','Mexico City':'latam','Medellín, Antioquia':'latam',
               'Tbilisi, Georgia':'otro','Barcelona, Spain':'otro','':None}
        for text,expected in cases.items():
            with self.subTest(text):self.assertEqual(ubicacion.region(text),expected)

    def test_rank_puts_the_united_states_first_and_unknown_last(self):
        self.assertEqual(sorted(['','Madrid','Lima, Peru','Austin, Texas'],key=ubicacion.rank),['Austin, Texas','Lima, Peru','Madrid',''])


class SignalAndSearchTests(NetworkBase):
    def test_profile_signals_keep_counts_flags_bio_and_language(self):
        data={'id':'ACo1','followers_count':1520,'relations_count':480,'bio':'  Building seed-stage tools.  ','language':'es',
              'specifics':{'is_creator':True,'is_hiring':False,'is_open_to_work':False}}
        self.assertEqual(_signals(data),{'followers':1520,'connections':480,'is_creator':True,'is_hiring':False,
                                         'is_open_to_work':False,'bio':'Building seed-stage tools.','language':'es'})
        self.assertEqual(_signals({'followers_count':None}),{})  # not given is never zero

    def test_unipile_search_sends_location_and_profile_language(self):
        connector=object.__new__(UnipileConnector)
        answer={'data':[{'id':'ACo9','display_name':'Ana','headline':'Founder','location':'Austin, Texas','followers_count':300,
                         'network_distance':'SECOND_DEGREE'}]}
        with patch.object(UnipileConnector,'_path',return_value='/v2/acc/linkedin/search/people'), \
             patch.object(UnipileConnector,'_query',return_value=answer) as query:
            people=connector.search_people('founder saas',location=['103644278'],profile_language=['es'])
        query.assert_called_once_with('/v2/acc/linkedin/search/people',
                                      {'keywords':'founder saas','location':['103644278'],'profile_language':['es']})
        self.assertEqual((people[0]['location'],people[0]['signals']),('Austin, Texas',{'followers':300}))

    def test_discovery_searches_the_united_states_twice_per_run_and_keeps_signals(self):
        self.fake.seed_person('ana-us','Ana US',headline='Founder',search='founder saas',location='Miami, Florida',
                              signals={'followers':1200,'is_hiring':True})
        self.fake.seed_person('beto-es','Beto ES',headline='Fundador',search='fundador startup',location='Austin, Texas')
        with patch.dict(os.environ,{'NETWORK_SEARCH_QUERIES':'founder saas;fundador startup [es]','NETWORK_SEARCH_LOCATION':'United States'}):
            summary=red.discover(self.bot,self.account)
            red.discover(self.bot,self.account)
        self.assertEqual(summary['searches'],2)
        self.assertEqual(self.fake.state['search_calls'][:2],[
            {'keywords':'founder saas','location':['103644278'],'profile_language':None},
            {'keywords':'fundador startup','location':['103644278'],'profile_language':['es']}])
        self.assertEqual(self.fake.state['parameter_calls'],[('LOCATION','United States')])  # read once, then kept
        ana=Contact.objects.get(display_name='Ana US')
        self.assertEqual((ana.location,ana.signals['followers'],ana.signals['is_hiring']),('Miami, Florida',1200,True))
        self.assertEqual(Contact.objects.get(display_name='Beto ES').evidence['query'],'fundador startup [es]')


class BuyerRegionTests(NetworkBase):
    def test_a_buyer_must_be_in_the_united_states_and_waits_for_the_web(self):
        for slug,name,location,stage in (('us-founder','Una US','Austin, Texas','candidate'),
                                         ('co-founder','Dos CO','Medellín, Antioquia','candidate'),
                                         ('mx-founder','Tres MX','Mexico City','incoming')):
            person=self.fake.seed_person(slug,name,headline='Founder',location=location,signals={'followers':900})
            Contact.objects.create(account=self.account,provider_user_id=person['id'],display_name=name,source='search',stage=stage)
        with patch.dict(os.environ,{'NETWORK_BUYER_REGION':'us','NETWORK_STAGE_CHECK':'true'}), \
             self.classifier({'Una US':(True,0.9),'Dos CO':(True,0.9),'Tres MX':(True,0.9)}), \
             patch('team_backend.research.research',return_value=NOTHING):
            red.classify(self.bot,self.account)
            people=self.classifier_calls[0]['data']['people']
            self.assertEqual({p['name']:p['region'] for p in people},{'Una US':'us','Dos CO':'latam','Tres MX':'latam'})
            self.assertEqual({p['name']:p['signals'] for p in people}['Una US'],{'followers':900})
            una,dos,tres=(Contact.objects.get(display_name=n) for n in ('Una US','Dos CO','Tres MX'))
            self.assertEqual((una.stage,una.classification['fit'],una.classification['stage_check']['state']),('fit',True,'pending'))
            self.assertEqual((dos.stage,dos.classification['fit']),('discarded',False))
            self.assertIn('fuera de EE. UU.',dos.classification['rule'])
            # A received invitation keeps the plain verdict: the location and stage rules shape outbound only.
            self.assertEqual((tres.classification['fit'],'stage_check' in tres.classification),(True,False))
            red.plan(self.bot,self.account)
            self.assertFalse(ActionProposal.objects.filter(contact=una).exists())  # waits for the web check
            manual=operador.create_proposal(self.bot,None,'RED-01',{'user_id':una.provider_user_id},source='agent',contact=una)
            self.assertIn('Falta que la web muestre su ronda semilla o clientes',red.network_issues(manual))


class StageCheckTests(NetworkBase):
    def setUp(self):
        super().setUp()
        env=patch.dict(os.environ,{'NETWORK_STAGE_CHECK':'true','NETWORK_BUYER_REGION':'us'});env.start();self.addCleanup(env.stop)
        self.judged=[]

    def test_the_classify_step_declares_every_paid_purpose_of_the_stage_check(self):
        # The job was blocked («undeclared_provider») every time a buyer waited for the web check: nobody was ever checked.
        from team_backend.grafo import load_graph
        edge=next(e for e in load_graph()['edges'] if e['id']=='clasificar')
        self.assertLessEqual({'network-classify','web-research-tool','network-stage'},set(edge['runtime']['purposes']['anthropic']))
        self.assertGreaterEqual(edge['call_timeout_s'],300)  # one classification and up to three web checks in one call

    def buyer(self,slug,name):
        contact=self.contact(slug,name)
        contact.location='Austin, Texas';contact.headline='Founder & CEO at Acme Robotics'
        contact.classification=dict(contact.classification,region='us',stage_check={'state':'pending'})
        contact.save();return contact

    def found(self):
        source=research.Source('s1','https://news.example/acme-seed','Acme seed','Acme raised a seed round','2026-11-12T00:00:00+00:00')
        return research.ResearchResult('q','complete','2026-11-12T00:00:00+00:00',
                                       (research.Finding('Acme Robotics raised a seed round.',('s1',)),),(source,))

    def judge(self,verdict):
        def fake(system,message,**kwargs):
            self.judged.append(kwargs.get('purpose'))
            return {'text':json.dumps({'verdict':verdict,'evidence':'La fuente dice que levantó una ronda semilla.',
                                       'source_urls':['https://news.example/acme-seed','https://invented.example']}),
                    'model':'claude-sonnet-5-5'}
        return patch('knowledge.providers.claude',side_effect=fake)

    def test_a_seed_round_on_the_web_lets_the_buyer_go_ahead(self):
        ana=self.buyer('ana-seed','Ana Seed')
        self.assertTrue(red.stage_pending(self.account))
        with patch('team_backend.research.research',return_value=self.found()) as web,self.judge('semilla_o_mas'):
            summary=red.check_stages(self.bot,self.account)
        ana.refresh_from_db();check=ana.classification['stage_check']
        self.assertEqual((summary,check['state'],check['sources']),({'checked':1,'passed':1},'ok',['https://news.example/acme-seed']))
        self.assertTrue(ana.classification['fit']);self.assertEqual(self.judged,['network-stage'])
        request=web.call_args.args[0]
        self.assertTrue(request.key.startswith(f'etapa:{ana.pk}:1:'));self.assertTrue(request.search)
        self.assertIn('Ana Seed',request.public_question)
        self.assertEqual(research.safe_question(request.public_question),request.public_question)
        self.assertFalse(red.stage_pending(self.account))
        red.plan(self.bot,self.account)
        self.assertTrue(ActionProposal.objects.filter(contact=ana,capability='RED-01').exists())

    def test_pre_seed_leaves_and_no_evidence_retries_until_the_third_day(self):
        ana=self.buyer('ana-pre','Ana Pre');beto=self.buyer('beto-none','Beto None')
        web=lambda request:self.found() if request.key.startswith(f'etapa:{ana.pk}:') else NOTHING
        with patch('team_backend.research.research',side_effect=web),self.judge('presemilla'):
            red.check_stages(self.bot,self.account)
        ana.refresh_from_db();beto.refresh_from_db()
        self.assertEqual((ana.stage,ana.classification['fit'],ana.classification['stage_check']['state']),('discarded',False,'failed'))
        self.assertIn('ronda semilla',ana.classification['rule'])
        self.assertEqual((beto.classification['stage_check']['state'],beto.classification['stage_check']['attempts']),('pending',1))
        self.assertFalse(red.stage_pending(self.account))  # the retry is due tomorrow
        when=timezone.now()
        for _ in range(2):
            when+=timedelta(days=1,minutes=5)
            with patch('team_backend.research.research',return_value=NOTHING):red.check_stages(self.bot,self.account,when)
        beto.refresh_from_db();check=beto.classification['stage_check']
        self.assertEqual((beto.stage,beto.classification['fit'],check['state'],check['attempts'],check['verdict']),
                         ('discarded',False,'failed',3,'sin_evidencia'))
        red.plan(self.bot,self.account)
        self.assertFalse(ActionProposal.objects.filter(contact__in=[ana,beto]).exists())

    def test_a_search_that_did_not_run_spends_no_attempt(self):
        ana=self.buyer('ana-wait','Ana Wait')
        skipped=research.ResearchResult('q','skipped','2026-11-12T00:00:00+00:00',limitations=('Límite diario de investigaciones alcanzado',))
        down=research.ResearchResult('q','unavailable','2026-11-12T00:00:00+00:00',limitations=('Investigación incompleta',))
        for result in (skipped,down):
            with patch('team_backend.research.research',return_value=result):summary=red.check_stages(self.bot,self.account)
            ana.refresh_from_db()
            self.assertEqual((summary['checked'],ana.stage,ana.classification['stage_check']),(0,'fit',{'state':'pending'}))
            self.assertEqual(summary['stopped'],result.limitations[0])

    def test_stage_checks_have_their_own_daily_allowance(self):
        WebResearchRun.objects.create(key='piece:editorial-1',request_hash='x',state='complete')
        with patch.dict(os.environ,{'NETWORK_STAGE_CHECKS_PER_DAY':'1'}),self.settings(WEB_RESEARCH_DAILY_LIMIT=1):
            run,cached=research._claim(research.ResearchRequest(key='etapa:a:1',public_question='q',search=True),'q')
            self.assertIsNotNone(run);self.assertIsNone(cached)  # the editorial run of the day does not count
            run,cached=research._claim(research.ResearchRequest(key='etapa:b:1',public_question='q',search=True),'q')
            self.assertEqual((run,cached.status),(None,'skipped'))
            run,cached=research._claim(research.ResearchRequest(key='piece:editorial-2',public_question='q',search=True),'q')
            self.assertEqual((run,cached.status),(None,'skipped'))  # and the stage check does not free editorial room
            self.assertEqual(red.stage_checks_left(),0)


class PlanOrderTests(NetworkBase):
    def person(self,slug,name,role,location,stage='followed',confidence=0.8):
        contact=self.contact(slug,name,stage=stage,followed_hours=72 if stage=='followed' else None)
        contact.location=location;contact.classification.update(role=role,confidence=confidence);contact.save()
        return contact

    def test_invitations_fill_from_us_buyers_to_the_latam_community(self):
        self.person('latam-par','Par LatAm','par','Bogotá, Colombia',confidence=0.99)
        self.person('us-ally','Aliado US','aliado','New York, NY',confidence=0.7)
        self.person('us-buyer','Comprador US','comprador','Austin, Texas',confidence=0.6)
        leader=self.person('us-leader','Líder US','lider','Miami, Florida',confidence=0.95)
        abroad=self.person('mx-buyer','Comprador MX','comprador','Monterrey, Mexico',confidence=0.95)
        graph=orquestacion.load_graph()
        next(e for e in graph['edges'] if e['id']=='politica_red')['max_calls_per_cycle']=3
        with patch.dict(os.environ,{'NETWORK_BUYER_REGION':'us'}),patch('team_backend.orquestacion.load_graph',return_value=graph):
            summary=red.plan(self.bot,self.account)
        self.assertEqual((summary['invite'],summary['follow'],summary['outbound_rules']['outside']),(3,0,1))
        invited=list(ActionProposal.objects.filter(capability='RED-02').order_by('created_at').values_list('contact__display_name',flat=True))
        self.assertEqual(invited,['Comprador US','Aliado US','Par LatAm'])
        self.assertFalse(ActionProposal.objects.filter(contact__in=[leader,abroad]).exists())
        abroad.refresh_from_db();self.assertFalse(abroad.classification['fit'])  # classified before the rule

    def test_follows_take_what_invitations_leave_and_include_leaders(self):
        leader=self.person('fit-leader','Líder por seguir','lider','Miami, Florida',stage='fit')
        self.person('us-peer','Par US','par','Austin, Texas')
        summary=red.plan(self.bot,self.account)
        self.assertEqual((summary['invite'],summary['follow']),(1,1))
        self.assertTrue(ActionProposal.objects.filter(contact=leader,capability='RED-01').exists())


class LeadDoubtTests(NetworkBase):
    def setUp(self):
        super().setUp()
        env=patch.dict(os.environ,{'LEAD_ENABLED':'true','OPERATOR_AUTONOMY':'RED-01=auto,RED-02=auto,RED-04=auto'})
        env.start();self.addCleanup(env.stop)
        self.asked=[]
        def jev(state,questions,purpose='lead-review'):
            self.asked.append(questions)
            return {'answers':{q:{'noul':0.9 if q=='reclutador' else 0.1} for q in questions},'model':'jev-1.14.0','estimated_usd':0.00003}
        typesafe=patch('knowledge.providers.typesafe',side_effect=jev);typesafe.start();self.addCleanup(typesafe.stop)

    def test_a_lead_doubt_rests_the_person_until_gustavo_says_it_fits(self):
        ana=self.contact('founder-ana','Ana Founder')
        red.plan(self.bot,self.account)
        proposal=ActionProposal.objects.get(contact=ana,capability='RED-01')
        autopiloto.policy_review(proposal);proposal.refresh_from_db()
        self.assertEqual((proposal.state,proposal.review['decision']),('discarded','discard'))
        notice=Notification.objects.get(kind='network_doubt')
        self.assertEqual((notice.link,notice.layer),(f'/personas/{ana.pk}','red'))
        red.plan(self.bot,self.account)
        self.assertEqual(ActionProposal.objects.filter(contact=ana).count(),1)  # it rests instead of another lottery
        body=self.human.get(f'/api/v1/red/contacts/{ana.pk}').json()
        self.assertEqual((body['lead_doubt']['capability'],body['next_step']['owner']),('RED-01','gustavo'))
        self.assertEqual(self.api.post(f'/api/v1/red/contacts/{ana.pk}/encaja',format='json').status_code,403)
        response=self.human.post(f'/api/v1/red/contacts/{ana.pk}/encaja',format='json')
        self.assertEqual(response.status_code,200,response.content)
        self.assertIsNone(response.json()['lead_doubt'])
        self.assertIn('confirmed_by_gustavo',response.json()['classification'])
        asked=len(self.asked)
        red.plan(self.bot,self.account)
        again=ActionProposal.objects.get(contact=ana,state='proposed')
        autopiloto.policy_review(again);again.refresh_from_db()
        self.assertEqual(again.state,'approved');self.assertEqual(len(self.asked),asked)  # his word replaces the lead's

    def test_the_rest_ends_after_its_days(self):
        ana=self.contact('founder-bea','Bea Founder')
        red.plan(self.bot,self.account)
        proposal=ActionProposal.objects.get(contact=ana)
        autopiloto.policy_review(proposal)
        ActionProposal.objects.filter(pk=proposal.pk).update(decided_at=timezone.now()-timedelta(days=31))
        red.plan(self.bot,self.account)
        self.assertTrue(ActionProposal.objects.filter(contact=ana,state='proposed').exists())

    def test_a_discard_of_the_old_single_risk_question_no_longer_rests_the_person(self):
        ana=self.contact('founder-cora','Cora Founder')
        red.plan(self.bot,self.account)
        proposal=ActionProposal.objects.get(contact=ana)
        ActionProposal.objects.filter(pk=proposal.pk).update(state='discarded',decided_at=timezone.now(),review={
            'decision':'discard','reasons':['Líder: parece vendedor, reclutador o cuenta ajena al nicho (riesgo=0.45)'],
            'answers':{'riesgo':0.45},'thresholds':{'riesgo':['max',0.3]}})
        self.assertIsNone(self.human.get(f'/api/v1/red/contacts/{ana.pk}').json()['lead_doubt'])
        red.plan(self.bot,self.account)
        self.assertTrue(ActionProposal.objects.filter(contact=ana,state='proposed').exists())

    def test_people_in_the_queue_classified_under_earlier_criteria_go_back_to_the_classifier(self):
        cutoff=timezone.now()-timedelta(days=1)
        def person(slug,when,stage='fit',**extra):
            contact=self.contact(slug,slug.title(),stage=stage)
            contact.classification=dict(contact.classification,classified_at=when.isoformat(),**extra);contact.save();return contact
        old=person('founder-old',cutoff-timedelta(days=2))
        recent=person('founder-new',cutoff+timedelta(hours=1))
        followed=person('founder-seg',cutoff-timedelta(days=2),stage='followed')
        confirmed=person('founder-ok',cutoff-timedelta(days=2),confirmed_by_gustavo={'at':'2026-11-13T00:00:00+00:00','by':'gustavo'})
        red.plan(self.bot,self.account)  # whatever it proposed for them is open
        self.assertEqual(red.requeue(self.bot,self.account,cutoff),{'found':1,'requeued':0})
        old.refresh_from_db();self.assertEqual(old.stage,'fit')
        self.assertEqual(red.requeue(self.bot,self.account,cutoff,confirm=True),{'found':1,'requeued':1})
        for contact in (old,recent,followed,confirmed):contact.refresh_from_db()
        self.assertEqual((old.stage,old.classification,old.history[-1]['event']),('candidate',{},'requeued'))
        self.assertFalse(ActionProposal.objects.filter(contact=old,state__in=['proposed','approved']).exists())
        self.assertEqual((recent.stage,followed.stage,confirmed.stage),('fit','followed','fit'))
        self.assertTrue(recent.classification and followed.classification and confirmed.classification)

    def test_only_a_fitting_person_in_course_can_be_confirmed(self):
        out=self.contact('founder-out','Out Founder',fit=False)
        self.assertEqual(self.human.post(f'/api/v1/red/contacts/{out.pk}/encaja',format='json').status_code,409)


class NetworkRoundTests(NetworkBase):
    ROUNDS={'NETWORK_BATCHES':'09:00-11:00,15:00-17:00','OPERATOR_TIMEZONE':'America/Bogota'}

    def at(self,hour,minute=0):
        return datetime(2026,11,9,hour,minute,tzinfo=BOGOTA)  # a Monday

    def test_rounds_split_network_writes_from_comments(self):
        with patch.dict(os.environ,dict(self.ROUNDS,NETWORK_BATCH_SPACING_SECONDS='60-90')):
            self.assertEqual((operador.network_batch(self.at(9,30)),operador.network_batch(self.at(16))),(0,1))
            self.assertIsNone(operador.network_batch(self.at(12)))
            self.assertIn('dos tandas',operador.batch_issue('RED-02',self.at(12)))
            self.assertEqual(operador.batch_issue('RED-02',self.at(9,30)),'')
            self.assertIn('espera',operador.batch_issue('INT-03',self.at(9,30)))
            self.assertEqual((operador.batch_issue('INT-03',self.at(12)),operador.batch_issue('CONT-09',self.at(9,30))),('',''))
            self.assertEqual(operador.spacing_range('RED-01',self.at(9,30)),(120,120))  # never under two minutes
            self.assertEqual(operador.spacing_range('RED-01',self.at(12))[0],1200)
        self.assertEqual(operador.batch_issue('RED-02',self.at(12)),'')  # without rounds nothing waits for them

    def test_the_first_round_sends_half_of_the_day_and_a_write_outside_waits(self):
        contact=self.contact('round-person','Round Person',stage='followed',followed_hours=72)
        with patch.dict(os.environ,self.ROUNDS):
            self.assertEqual(operador.capacity_left(self.account,'RED-02',self.at(9,30)),8)  # half of 16
            self.assertEqual(operador.capacity_left(self.account,'RED-02',self.at(15,30)),16)
            proposal=operador.create_proposal(self.gustavo,None,'RED-02',{'user_id':contact.provider_user_id},contact=contact)
            proposal.state='approved';proposal.approved_hash=proposal.payload_hash;proposal.save()
            with patch('django.utils.timezone.now',return_value=self.at(12)), \
                 self.assertRaisesRegex(operador.OperatorBlocked,'dos tandas'):
                operador.execute(self.gustavo,proposal.id)
        self.assertEqual(self.fake.state['writes'],0)


class RampMigrationTests(NetworkBase):
    def test_the_current_stage_moves_to_the_new_scale(self):
        migration=importlib.import_module('team_backend.migrations.0031_red_senales_rampa')
        migration.ramp_v2(apps,None)
        self.assertFalse(operador.policy_event('network.ramp'))  # a new ramp starts at 16/80 by itself
        for old,new in ((0,1),(1,1),(2,2)):
            with self.subTest(old):
                red._save_ramp({'stage':old,'stage_since':'2026-11-01T00:00:00+00:00','freeze_until':'2026-11-01T00:00:00+00:00',
                                'pause_until':None},'fixture',timezone.now())
                migration.ramp_v2(apps,None)
                state=red.ramp_state()
                self.assertEqual((state['stage'],state['previous_scale_stage'],state['scale']),(new,old,'8/40,16/80,20/100'))


class ExtraordinaryReviewTests(NetworkBase):
    def test_it_queues_once_and_its_proposals_need_his_decision(self):
        now=datetime(2026,11,12,15,tzinfo=BOGOTA)
        with self.assertRaises(ValueError):referentes.extraordinary(self.gustavo,self.account,now)  # main five first
        ReferentControl.objects.update_or_create(account=self.account,defaults={'initialized':True})
        job=referentes.extraordinary(self.gustavo,self.account,now)
        self.assertEqual((job.kind,job.params),('review_referents',{'account':str(self.account.pk),'month':'2026-11-01','extraordinaria':True}))
        self.assertEqual(referentes.extraordinary(self.gustavo,self.account,now).pk,job.pk)  # one job per month
        review=ReferentReview.objects.create(account=self.account,month=now.date().replace(day=1),deadline=now+timedelta(days=7),
                                             state='ready',dossier={'extraordinaria':True})
        review=referentes.publish(review,now)
        self.assertEqual(review.state,'late')  # explicit decisions only
        notice=Notification.objects.get(kind='referents_review')
        self.assertEqual(notice.title,'Revisión extraordinaria de referentes')
        self.assertIn('19/11',notice.detail);self.assertIn('nada se aplica sin tu decisión',notice.detail)
        with self.assertRaises(Conflict):referentes.extraordinary(self.gustavo,self.account,now)
