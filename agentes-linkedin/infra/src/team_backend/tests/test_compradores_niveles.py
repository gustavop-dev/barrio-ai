"""BAR-24-compradores: who of the buyers stays in the neighborhood, with what level, and in what order they are invited.

The case (evaluaciones.BUYERS_CASE) has seven synthetic people built from the verdicts measured in production on
17/11/2026. Each one goes through the production path: classification (red.classify, Claude faked), the web check of the
stage (red.check_stages, the research and the judge faked) for three days, and the plan of invitations (red.plan). The
fake classifier answers what the production model answered with the prompt of 12/11/2026 (`antes`) or what the prompt
of 17/11/2026 asks for (`despues`), depending on the prompt it receives: what is proven is what the code does with each
answer, not how the real model answers. Synthetic people and sources only."""
import json
import os
from datetime import datetime, timedelta
from io import StringIO
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.core.management import call_command
from django.utils import timezone

from team_backend import comprador, evaluaciones, lider, nivel_comprador, red, reparto, research
from team_backend.models import ActionProposal, AuditEvent, BuyerJourney, Contact
from team_backend.tests.test_red import NetworkBase

BOGOTA=ZoneInfo('America/Bogota')
CASE=evaluaciones.BUYERS_CASE
MONDAY=datetime(2026,11,16,10,tzinfo=BOGOTA)
# A search that ran and found nothing citable (it has usage).
NOTHING=research.ResearchResult('q','unavailable','2026-11-16T15:00:00+00:00',usage={'model':'claude-sonnet-5-5'})
# The outbound of PR #135, each phase behind its switch.
BUYER_SWITCHES=('BUYER_RECORD_ENABLED','BUYER_WARMUP_ENABLED','BUYER_FIRST_MESSAGE_ENABLED','BUYER_SEQUENCE_ENABLED',
                'BUYER_NO_POSTS_ROUTE_ENABLED','BUYER_REPLY_ENABLED')


class BuyersCase(NetworkBase):
    def setUp(self):
        super().setUp()
        env=patch.dict(os.environ,{'NETWORK_BUYER_REGION':'us','NETWORK_STAGE_CHECK':'true'})
        env.start();self.addCleanup(env.stop)
        self.by_name={v['name']:(vid,v) for vid,v in CASE['variants'].items()}

    def seed(self):
        for vid,v in CASE['variants'].items():
            signals={'bio':v['bio']} if v['bio'] else {}
            person=self.fake.seed_person(vid.lower(),v['name'],headline=v['headline'],location=v['location'],signals=signals)
            Contact.objects.create(account=self.account,provider_user_id=person['id'],display_name=v['name'],headline=v['headline'],
                                   location=v['location'],profile_url=person['profile_url'],signals=signals,source='search',
                                   stage='candidate')

    def models(self):
        """Claude faked: the classifier answers per variant and prompt; the judge of the stage reads the one finding."""
        def fake(system,message,**kwargs):
            data=json.loads(message)
            if kwargs.get('purpose')=='network-stage':
                _,variant=self.by_name[data['persona']['nombre']]
                verdict='semilla_o_mas' if 'semilla_o_mas' in system else 'confirmado'
                return {'text':json.dumps({'verdict':verdict,'evidence':'La fuente dice que tiene clínicas que pagan y precios.',
                                           'source_urls':[variant['web']['url']]}),'model':'claude-sonnet-5-5'}
            new='buyer_level' in system
            rows=[]
            for person in data['people']:
                _,variant=self.by_name[person['name']];answer=variant['despues' if new else 'antes']
                row={'id':person['id'],'fit':answer['fit'],'role':'comprador','modality':'projectapp','affinity':'desconocida',
                     'reason':answer['reason'],'confidence':0.8,'course_citations':['LI-03-M005-K06'],'invitation_note':'','note_reason':''}
                if new:row.update({k:answer[k] for k in ('buyer_profile','buyer_level','us_market')})
                rows.append(row)
            return {'text':json.dumps({'contacts':rows}),'model':'claude-sonnet-5-5','estimated_usd':0.002}
        return patch('knowledge.providers.claude',side_effect=fake)

    def web(self,request):
        contact=Contact.objects.get(pk=request.key.split(':')[1])
        _,variant=self.by_name[contact.display_name]
        if not variant['web']:return NOTHING
        source=research.Source('s1',variant['web']['url'],'Pricing',variant['web']['text'],'2026-11-16T15:00:00+00:00')
        return research.ResearchResult('q','complete','2026-11-16T15:00:00+00:00',(research.Finding(variant['web']['text'],('s1',)),),(source,))

    def run_case(self):
        """Classify on Monday, check the stages that day and the two next ones, then plan the invitations (every person
        who stayed is taken as followed three days ago). Returns (outcomes, invited variants in order)."""
        self.seed()
        with self.models(),patch('team_backend.research.research',side_effect=self.web):
            red.classify(self.bot,self.account,MONDAY)
            for n,days in enumerate((0,0,1,2,3)):
                red.check_stages(self.bot,self.account,MONDAY+timedelta(days=days,minutes=5*(n+1)))
            when=MONDAY+timedelta(days=3,hours=1)
            Contact.objects.filter(stage='fit').update(stage='followed',is_following=True,followed_at=when-timedelta(days=3))
            red.plan(self.bot,self.account,when)
        name_of={v['name']:vid for vid,v in CASE['variants'].items()}
        outcomes={}
        for contact in Contact.objects.all():
            c=contact.classification or {}
            score=red.buyer_score(contact)
            outcomes[name_of[contact.display_name]]={
                'kept':bool(c.get('fit')) and contact.stage not in ('discarded','closed'),'stage':contact.stage,
                'level':(c.get('buyer') or {}).get('level'),'score':score.get('score'),'breakdown':score.get('breakdown'),
                'warnings':score.get('warnings'),'rule':c.get('rule','')}
        invited=[name_of[name] for name in ActionProposal.objects.filter(capability='RED-02').order_by('created_at')
                 .values_list('contact__display_name',flat=True)]
        return outcomes,invited

    def test_the_buyers_case_keeps_who_lacks_evidence_and_drops_who_has_evidence_against(self):
        outcomes,invited=self.run_case()
        grade=evaluaciones.grade_buyers_case(outcomes,invited)
        self.assertTrue(grade['passed'],(grade,outcomes,invited))
        kept={CASE['variants'][vid]['name'] for vid,row in outcomes.items() if row['kept']}
        self.assertEqual(set(BuyerJourney.objects.values_list('contact__display_name',flat=True)),kept)  # every kept buyer has a journey

    def test_with_every_buyer_switch_off_the_case_is_the_same_and_nothing_is_recorded(self):
        with patch.dict(os.environ,{name:'false' for name in BUYER_SWITCHES}):
            outcomes,invited=self.run_case()
        grade=evaluaciones.grade_buyers_case(outcomes,invited)
        self.assertTrue(grade['passed'],(grade,outcomes,invited))
        self.assertFalse(BuyerJourney.objects.exists())


class BuyerBase(NetworkBase):
    def setUp(self):
        super().setUp()
        env=patch.dict(os.environ,{'NETWORK_BUYER_REGION':'us','NETWORK_STAGE_CHECK':'true'});env.start();self.addCleanup(env.stop)

    def buyer(self,slug,name,level='por_confirmar',location='Austin, Texas',headline='Founder & CEO at Acme Robotics · AI software',
              stage='fit',bio='',profile='stealth',us_market=False,confidence=0.9,**extra):
        contact=self.contact(slug,name,stage=stage,followed_hours=72 if stage=='followed' else None)
        contact.location=location;contact.headline=headline;contact.signals={'bio':bio} if bio else {}
        contact.classification=dict(contact.classification,confidence=confidence,region='',stage_check={'state':'pending'},
                                    buyer={'profile':profile,'level':level,'us_market':us_market},**extra)
        contact.save();return contact

    def judge(self,verdict,url='https://news.example/acme'):
        def fake(system,message,**kwargs):
            return {'text':json.dumps({'verdict':verdict,'evidence':'La fuente lo dice.','source_urls':[url]}),'model':'claude-sonnet-5-5'}
        return patch('knowledge.providers.claude',side_effect=fake)

    def found(self,url='https://news.example/acme'):
        source=research.Source('s1',url,'Acme','Acme raised a seed round','2026-11-16T15:00:00+00:00')
        return research.ResearchResult('q','complete','2026-11-16T15:00:00+00:00',(research.Finding('Acme raised a seed round.',('s1',)),),
                                       (source,),usage={'model':'claude-sonnet-5-5'})


class LevelTests(BuyerBase):
    def test_only_evidence_against_lowers_and_the_stronger_level_wins(self):
        cases={('probable','no_encaja'):'no_encaja',('confirmado','por_confirmar'):'confirmado',('por_confirmar','probable'):'probable',
               (None,'por_confirmar'):'por_confirmar',('no_encaja','confirmado'):'confirmado'}
        for (current,found),expected in cases.items():
            with self.subTest(current=current,found=found):self.assertEqual(nivel_comprador.combine(current,found),expected)

    def test_the_classifier_keeps_a_founder_without_public_data_and_drops_one_with_evidence_against(self):
        for slug,name in (('cora','Cora Stealth'),('gabi','Gabi Idea')):
            person=self.fake.seed_person(slug,name,headline='Founder @Lumora')
            Contact.objects.create(account=self.account,provider_user_id=person['id'],display_name=name,headline='Founder @Lumora',
                                   location='San Francisco Bay Area',profile_url=f'https://linkedin.example/in/{slug}',source='search',stage='candidate')
        answers={'Cora Stealth':{'fit':True,'buyer_level':'por_confirmar','buyer_profile':'stealth','us_market':True},
                 # an inconsistent answer: fit with evidence against still leaves
                 'Gabi Idea':{'fit':True,'buyer_level':'no_encaja','buyer_profile':'stealth','us_market':True}}
        def fake(system,message,**kwargs):
            rows=[dict(answers[p['name']],id=p['id'],role='comprador',modality='projectapp',affinity='desconocida',reason='Founder.',
                       confidence=0.8,course_citations=['LI-03-M005-K06'],invitation_note='',note_reason='')
                  for p in json.loads(message)['people']]
            return {'text':json.dumps({'contacts':rows}),'model':'claude-sonnet-5-5'}
        with patch('knowledge.providers.claude',side_effect=fake),patch('team_backend.research.research',return_value=research.ResearchResult(
                'q','skipped','2026-11-16T15:00:00+00:00',limitations=('Límite diario',))):
            red.classify(self.bot,self.account)
        cora,gabi=Contact.objects.get(display_name='Cora Stealth'),Contact.objects.get(display_name='Gabi Idea')
        buyer=cora.classification['buyer']
        self.assertEqual((cora.stage,cora.classification['fit'],cora.classification['stage_check']['state']),('fit',True,'pending'))
        self.assertEqual((buyer['level'],buyer['profile'],buyer['us_market'],buyer['basis'],buyer['sources']),
                         ('por_confirmar','stealth',True,'perfil',['https://linkedin.example/in/cora']))
        self.assertEqual((buyer['score'],buyer['score_version']),(red.buyer_score(cora)['score'],'buyer_score_v1'))
        journey=comprador.journey(cora)  # the journey keeps the level and score she entered with
        self.assertEqual((journey.entry_level,journey.entry_score,journey.entry_score_version),('por_confirmar',buyer['score'],'buyer_score_v1'))
        self.assertEqual((gabi.stage,gabi.classification['fit'],gabi.classification['rule']),('discarded',False,red.NO_FIT_RULE))
        self.assertIsNone(comprador.journey(gabi))

    def test_each_profile_asks_its_own_public_question(self):
        questions={}
        for profile in ('startup_financiada','bootstrapped','stealth','ejecutivo'):
            contact=self.buyer(f'q-{profile}',f'Ana {profile.title()}',profile=profile,headline='Founder & CEO at Acme Robotics · '+'x'*280)
            question=red.stage_question(contact);questions[profile]=question
            with self.subTest(profile):
                self.assertEqual(research.safe_question(question),question)  # under 300 characters, nothing private
                self.assertIn(f'Ana {profile.title()}',question);self.assertIn('Acme Robotics',question)
        self.assertEqual(len(set(questions.values())),4)
        self.assertIn('Funding',questions['startup_financiada']);self.assertIn('paying customers',questions['bootstrapped'])
        self.assertIn('exits',questions['stealth'])

    def test_a_verdict_without_a_received_source_stays_por_confirmar(self):
        contact=self.buyer('ana-memoria','Ana Memoria',level='probable')
        with patch('team_backend.research.research',return_value=self.found()),self.judge('no_encaja',url='https://invented.example'):
            red.check_stages(self.bot,self.account)
        contact.refresh_from_db()
        self.assertEqual((contact.stage,contact.classification['buyer']['level'],contact.classification['stage_check']['verdict']),
                         ('fit','probable','por_confirmar'))  # the model's memory is not the web: the profile's level stays

    def test_a_question_that_cannot_be_asked_does_not_hold_the_queue(self):
        first=self.buyer('ana-privada','Ana Privada');second=self.buyer('beto-sigue','Beto Sigue')
        asked=lambda question:'' if 'Ana Privada' in question else question
        with patch('team_backend.research.safe_question',side_effect=asked), \
             patch('team_backend.research.research',return_value=self.found()) as web,self.judge('confirmado'):
            summary=red.check_stages(self.bot,self.account)
        first.refresh_from_db();second.refresh_from_db()
        self.assertEqual((first.classification['stage_check']['evidence'],first.classification['buyer']['level']),
                         (red.STAGE_UNASKABLE,'por_confirmar'))
        self.assertEqual((web.call_count,second.classification['buyer']['level'],summary['passed']),(1,'confirmado',2))

    def test_the_web_check_waits_for_the_reading_window_and_retries_at_its_start(self):
        contact=self.buyer('ana-ventana','Ana Ventana')
        night=datetime(2026,11,16,23,tzinfo=BOGOTA)
        with patch.dict(os.environ,{'READ_WINDOW':'07:00-21:00'}):
            with patch('team_backend.research.research',return_value=NOTHING) as web:
                self.assertEqual(red.check_stages(self.bot,self.account,night),{'checked':0,'passed':0,'stopped':red.STAGE_OUTSIDE})
                self.assertEqual(web.call_count,0)
                contact.refresh_from_db();self.assertEqual(contact.classification['stage_check'],{'state':'pending'})
                red.check_stages(self.bot,self.account,MONDAY)
        contact.refresh_from_db();check=contact.classification['stage_check']
        self.assertEqual((check['attempts'],datetime.fromisoformat(check['next_at'])),(1,datetime(2026,11,17,7,tzinfo=BOGOTA)))

    def test_the_lead_reads_the_level_and_asks_no_new_question(self):
        contact=self.buyer('ana-lider','Ana Lider')
        state,questions,_=lider._questions(ActionProposal(capability='RED-01',contact=contact),'')
        self.assertEqual(state['clasificacion']['nivel'],'por_confirmar')
        self.assertEqual(set(questions),{'falsa','empresa','reclutador','prospector','proveedor'})
        self.assertIn('stealth',questions['proveedor']['criteria']['false'])  # a brief founder does not read as a seller


class ScoreTests(BuyerBase):
    def test_the_breakdown_adds_up_to_the_score_and_says_why(self):
        for level in nivel_comprador.LEVELS:
            contact=self.buyer(f's-{level}',f'Ana {level}',level=level)
            result=red.buyer_score(contact)
            with self.subTest(level):
                self.assertEqual(sum(part['points'] for part in result['breakdown'].values()),result['score'])
                self.assertTrue(all(part['why'] and part['points']<=part['max'] for part in result['breakdown'].values()))
                self.assertLessEqual(result['score'],100)
        self.assertEqual(red.buyer_score(self.buyer('s-top','Ana Top',level='confirmado',confidence=1.0))['score'],100)
        self.assertEqual(red.buyer_score(Contact(classification={'role':'par','fit':True})),{})

    def test_a_thin_profile_raises_a_notice_and_never_loses_points(self):
        thin=self.buyer('s-thin','Beto Escueto',headline='Founder @Lumora')
        full=self.buyer('s-full','Bea Panaderia',headline='Founder & CEO at Lumora · bakery chain with twelve stores',
                        bio='We bake bread and pastries for the neighborhood every morning.')
        thin_score,full_score=red.buyer_score(thin),red.buyer_score(full)
        self.assertIn(nivel_comprador.THIN_NOTICE,thin_score['warnings']);self.assertNotIn(nivel_comprador.THIN_NOTICE,full_score['warnings'])
        self.assertEqual(thin_score['breakdown']['servicios']['value'],'sin_dato')
        self.assertGreater(thin_score['score'],full_score['score'])  # missing data takes the middle value, not the floor

    def test_buyers_go_by_market_tier_then_score_and_a_low_score_is_still_invited(self):
        people=[self.buyer('o-latam','LatAm Probable',level='probable',location='Bogotá, Colombia',stage='followed'),
                self.buyer('o-pc','US Por Confirmar',level='por_confirmar',stage='followed'),
                # Probable and selling in the US scores above «US Por Confirmar» (76 > 65): the region still goes first.
                self.buyer('o-usm','LatAm Con Negocio',level='probable',location='Lima, Peru',us_market=True,stage='followed'),
                self.buyer('o-conf','US Confirmado',level='confirmado',stage='followed'),
                self.buyer('o-prob','US Probable',level='probable',stage='followed',headline='Founder @Lumora')]
        order=[c.display_name for c in red.prioritized(people)]
        self.assertEqual(order,['US Confirmado','US Probable','US Por Confirmar','LatAm Con Negocio','LatAm Probable'])
        red.plan(self.bot,self.account)
        invited=list(ActionProposal.objects.filter(capability='RED-02').order_by('created_at').values_list('contact__display_name',flat=True))
        self.assertEqual(invited,order)  # nobody is left out for a low score

    def test_the_temperature_adds_to_the_score_only_with_the_warm_up_on_and_never_jumps_a_region(self):
        cold=self.buyer('t-cold','US Confirmado Frio',level='confirmado',stage='followed')
        warm=self.buyer('t-warm','US Por Confirmar Caliente',level='por_confirmar',stage='followed')
        latam=self.buyer('t-latam','LatAm Caliente',level='confirmado',location='Bogotá, Colombia',stage='followed')
        heat={cold.pk:0,warm.pk:20,latam.pk:20}
        names=lambda:[c.display_name for c in red.prioritized([latam,warm,cold])]
        with patch('team_backend.calentamiento.heats',return_value=heat):
            self.assertEqual(names(),['US Confirmado Frio','US Por Confirmar Caliente','LatAm Caliente'])
            with patch.dict(os.environ,{'BUYER_WARMUP_ENABLED':'true'}):
                self.assertEqual(names(),['US Por Confirmar Caliente','US Confirmado Frio','LatAm Caliente'])
        self.assertEqual((nivel_comprador.priority(65,20),nivel_comprador.priority(65,1),nivel_comprador.priority(None)),(105,70,0))

    def test_a_level_up_recomputes_the_score_and_the_entry_is_fixed_by_the_follow(self):
        chosen=self.buyer('s-elegida','Ana Elegida',level='por_confirmar')
        followed=self.buyer('s-seguido','Beto Seguido',level='por_confirmar',stage='followed')
        before={c.pk:comprador.update(c) for c in (chosen,followed)}  # chosen with a pending check: a journey each
        self.assertEqual({j.entry_level for j in before.values()},{'por_confirmar'})
        with patch('team_backend.research.research',return_value=self.found()),self.judge('confirmado'):
            red.check_stages(self.bot,self.account)
        for contact in (chosen,followed):
            contact.refresh_from_db();buyer=contact.classification['buyer']
            self.assertEqual((buyer['level'],buyer['score']),('confirmado',red.buyer_score(contact)['score']))
            self.assertGreater(buyer['score'],before[contact.pk].entry_score)
        # Nobody had acted on Ana yet: she is gone after as confirmed. Beto was already followed: he stays as he came.
        ana,beto=comprador.journey(chosen),comprador.journey(followed)
        self.assertEqual((ana.entry_level,ana.entry_score),('confirmado',chosen.classification['buyer']['score']))
        self.assertEqual((beto.pk,beto.entry_level,beto.entry_score),(before[followed.pk].pk,'por_confirmar',before[followed.pk].entry_score))

    def test_the_contact_api_shows_the_score_and_the_buyer_funnel_splits_by_entry(self):
        contact=self.buyer('s-api','Ana Api',level='probable',stage='followed')
        contact.followed_at=timezone.now()-timedelta(days=3);contact.save()
        other=self.buyer('s-api2','Beto Api',level='por_confirmar',headline='Founder @Lumora')
        for person in (contact,other):comprador.update(person)
        peer=self.contact('s-par','Par Api');peer.classification=dict(peer.classification,role='par');peer.save()
        body=self.human.get(f'/api/v1/red/contacts/{contact.pk}').json()
        self.assertEqual((body['buyer']['level'],body['buyer']['score']),('probable',red.buyer_score(contact)['score']))
        self.assertEqual(sum(part['points'] for part in body['buyer']['breakdown'].values()),body['buyer']['score'])
        self.assertEqual((body['buyer']['entry']['level'],body['buyer']['entry']['score']),('probable',body['buyer']['score']))
        self.assertIsNone(self.human.get(f'/api/v1/red/contacts/{peer.pk}').json()['buyer'])
        entry=self.human.get('/api/v1/resultados/embudo-comprador').json()['entrada_comprador']
        self.assertEqual(entry['por_nivel']['probable'],{'elegidos':1,'seguidos':1,'calentados':0,'invitados':0,'aceptaron':0,'respondieron':0})
        self.assertEqual((entry['por_nivel']['por_confirmar']['elegidos'],entry['por_nivel']['por_confirmar']['seguidos']),(1,0))
        expected={}
        for person in (contact,other):
            label=nivel_comprador.band(red.buyer_score(person)['score']);expected[label]=expected.get(label,0)+1
        self.assertEqual({label:row['elegidos'] for label,row in entry['por_puntaje'].items() if row['elegidos']},expected)


class QuotaTests(BuyerBase):
    def person(self,slug,role,stage='followed'):
        contact=self.contact(slug,slug.title(),stage=stage,followed_hours=72)
        contact.location='Austin, Texas';contact.classification=dict(contact.classification,role=role);contact.save()
        return contact

    def test_the_shares_are_read_and_a_bad_value_is_a_configuration_error(self):
        self.assertEqual(reparto.shares(),[(('comprador',),20),(('recomendador','aliado'),15),(('divulgador',),20),(('par',),25)])
        for raw in ('lider=10','comprador=20,comprador=5','vendedor=5','comprador=0','comprador'):
            with self.subTest(raw),patch.dict(os.environ,{'NETWORK_ROLE_SHARE':raw}),self.assertRaises(ValueError):reparto.shares()
        people=[self.person('q-par','par'),self.person('q-buyer','comprador')]
        with patch.dict(os.environ,{'NETWORK_ROLE_SHARE':''}):
            self.assertEqual(reparto.order(people,self.account),(people,[]))  # off: the plan's order as it was

    def test_the_role_furthest_below_its_share_goes_first_and_the_others_take_what_is_left(self):
        pars=[self.person(f'q-par{n}','par') for n in range(3)]
        for par in pars[:2]:operador_proposal(self,par)  # two invitations to peers already this week
        ally=self.person('q-ally','aliado');buyer=self.person('q-buyer','comprador');spreader=self.person('q-div','divulgador')
        ordered,report=reparto.order([pars[2],ally,spreader,buyer],self.account)
        self.assertEqual([c.display_name for c in ordered],['Q-Buyer','Q-Ally','Q-Div','Q-Par2'])
        rows={tuple(row['roles']):row for row in report}
        self.assertEqual((rows[('par',)]['invited'],rows[('par',)]['ready']),(2,1))
        self.assertEqual(rows[('recomendador','aliado')]['ready'],1)  # an ally takes the recommenders' turn
        only=[self.person(f'q-solo{n}','par') for n in range(2)]
        self.assertEqual(reparto.order(only,self.account)[0],only)  # without buyers the peers take the turns

    def test_the_weekly_target_follows_the_ramp(self):
        for stage,target in ((0,10),(1,20),(2,25)):
            red._save_ramp({'stage':stage,'stage_since':'2026-11-01T00:00:00+00:00','freeze_until':'2026-11-01T00:00:00+00:00',
                            'pause_until':None},'fixture',datetime(2026,11,1,tzinfo=BOGOTA))
            with self.subTest(stage):
                _,report=reparto.order([self.person(f'q-r{stage}','comprador')],self.account)
                self.assertEqual(report[0]['weekly_target'],target)

    def test_the_plan_records_the_shares_with_what_it_planned(self):
        self.person('q-p1','par');self.person('q-b1','comprador')
        summary=red.plan(self.bot,self.account)
        rows={tuple(row['roles']):row for row in summary['role_quota']}
        self.assertEqual((rows[('comprador',)]['planned'],rows[('par',)]['planned'],rows[('divulgador',)]['planned']),(1,1,0))
        event=AuditEvent.objects.filter(action='network.planned').latest('created_at')
        self.assertEqual(event.metadata['role_quota'],summary['role_quota'])


def operador_proposal(case,contact):
    from team_backend import operador
    operador.create_proposal(case.bot,None,'RED-02',{'user_id':contact.provider_user_id},source='agent',contact=contact)


class ReevaluationTests(BuyerBase):
    def setUp(self):
        super().setUp()
        def left(slug,name,location='Austin, Texas',stage='discarded',events=('classified',),**classification):
            contact=self.contact(slug,name,stage=stage,followed_hours=72 if stage=='followed' else None)
            contact.location=location;contact.headline='Founder & CEO at Acme · SaaS'
            contact.classification=dict(contact.classification,**classification)
            contact.history=[{'at':'2026-11-13T00:00:00+00:00','event':event,'detail':''} for event in events];contact.save()
            return contact
        self.region=left('r-region','Rosa Region',location='Bogotá, Colombia',fit=False,
                         rule='Comprador fuera de EE. UU.: el barrio busca founders allí (Gustavo, 12/11/2026).')
        self.web=left('r-web','Walter Web',fit=False,rule='Sin ronda semilla o clientes visibles en la web: no es comprador (Gustavo, 12/11/2026).',
                      stage_check={'state':'failed','verdict':'sin_evidencia','attempts':3},events=('classified','stage_checked'))
        self.absent=left('r-absent','Ada Ausente',fit=False,reason='Founder en EE. UU., sin evidencia de ronda semilla ni clientes que pagan.')
        self.against=left('r-against','Gabi Idea',fit=False,reason='Presemilla declarada, en etapa de idea y sin ingresos.')
        self.vetoed=left('r-veto','Vera Veto',location='Lima, Peru',fit=False,events=('classified','discarded'),
                         rule='Comprador fuera de EE. UU.: el barrio busca founders allí (Gustavo, 12/11/2026).')
        self.followed=left('r-seguido','Sergio Seguido',location='Mexico City',stage='followed',fit=True)
        self.invited=left('r-invitado','Ines Invitada',stage='invited',fit=False,
                          rule='Comprador fuera de EE. UU.: el barrio busca founders allí (Gustavo, 12/11/2026).')

    def test_the_dry_run_lists_by_score_and_changes_nothing(self):
        before={c.pk:(c.stage,c.classification) for c in Contact.objects.all()}
        result=nivel_comprador.reevaluate(self.bot,self.account)
        self.assertEqual(result['found'],{'fuera_de_eeuu':1,'sin_evidencia_web':1,'sin_evidencia_clasificador':1,'sin_nivel':1})
        self.assertEqual((result['total'],result['applied']),(4,0))
        scores=[row['score'] for row in result['people']]
        self.assertEqual(scores,sorted(scores,reverse=True))
        self.assertEqual({row['name'] for row in result['people']},{'Rosa Region','Walter Web','Ada Ausente','Sergio Seguido'})
        self.assertEqual({c.pk:(c.stage,c.classification) for c in Contact.objects.all()},before)
        out=StringIO()
        call_command('operador','--usuario','gustavo-test','reevaluar-compradores','--cuenta',str(self.account.id),stdout=out)
        self.assertIn('Compradores a reevaluar: 4',out.getvalue());self.assertIn('Sin --confirmar no se cambia nada.',out.getvalue())
        self.assertIn('Ada Ausente',out.getvalue())

    def test_confirming_restores_requeues_and_completes_once(self):
        result=nivel_comprador.reevaluate(self.bot,self.account,confirm=True)
        self.assertEqual(result['applied'],4)
        for contact in (self.region,self.web,self.absent,self.against,self.vetoed,self.followed,self.invited):contact.refresh_from_db()
        self.assertEqual((self.region.stage,self.region.classification['fit'],self.region.classification['stage_check']),('fit',True,{'state':'pending'}))
        self.assertNotIn('rule',self.region.classification)
        self.assertEqual((self.web.stage,self.web.classification['stage_check']['state'],self.web.classification['stage_check']['verdict']),
                         ('fit','ok','por_confirmar'))
        for contact in (self.region,self.web,self.followed):
            with self.subTest(contact.display_name):
                buyer=contact.classification['buyer']
                self.assertEqual((buyer['level'],comprador.journey(contact).entry_level,buyer['score']),
                                 ('por_confirmar','por_confirmar',red.buyer_score(contact)['score']))
        self.assertEqual((self.absent.stage,self.absent.classification),('candidate',{}))
        self.assertEqual((self.against.stage,self.vetoed.stage,self.invited.stage,self.followed.stage),('discarded','discarded','invited','followed'))
        self.assertEqual(AuditEvent.objects.filter(action=nivel_comprador.REEVALUATED).count(),4)
        again=nivel_comprador.reevaluate(self.bot,self.account,confirm=True)
        self.assertEqual((again['total'],again['applied']),(0,0))
