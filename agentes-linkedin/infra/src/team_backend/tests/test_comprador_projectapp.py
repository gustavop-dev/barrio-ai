"""BAR-25-comprador-projectapp: the ProjectApp buyer (traditional companies of 20 to 200 people in the United States that
need software), the startup buyer and the partner (agencies that subcontract development), Gustavo 17/11/2026.

The case (evaluaciones.PROJECTAPP_CASE) has eight synthetic people. Each one goes through the production path:
classification (red.classify, Claude faked), the web check (red.check_stages, research and judge faked) and the plan of
invitations (red.plan) once everyone who stayed is followed. The fake classifier answers what the prompt of 17/11/2026
(BAR-24) asks for (`antes`) or what the ProjectApp prompt asks for (`despues`), depending on the prompt it receives:
what is proven is what the code does with each answer, not how the real model answers. Synthetic people and sources."""
import hashlib
import json
import os
from datetime import datetime, timedelta
from io import StringIO
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from team_backend import (calentamiento, comprador, evaluaciones, identidad, lectura_embudo, lider, nivel_comprador, operador, posicionamiento,
                          preguntas, projectapp, red, reparto, research)
from team_backend.models import ActionProposal, AuditEvent, BuyerJourney, Contact, TeamQuestion
from team_backend.tests.test_red import NetworkBase

BOGOTA=ZoneInfo('America/Bogota')
CASE=evaluaciones.PROJECTAPP_CASE
WHO_CASE=evaluaciones.COURSE_CASES['con_quien']
MONDAY=datetime(2026,11,16,10,tzinfo=BOGOTA)
NOTHING=research.ResearchResult('q','unavailable','2026-11-16T15:00:00+00:00',usage={'model':'claude-sonnet-5-5'})
SWITCH='NETWORK_PROJECTAPP_BUYER_ENABLED'
# What the case gave with the code of origin/main (BAR-24), before the ProjectApp buyer existed: 2 of 8 right
# (docs/linea-base-comprador-projectapp.md, «Antes»). With the switch off the code must give exactly this again.
BASELINE_ERRORS=['P1:line','P1:segment','P1:papel','P2:line','P2:segment','P2:papel','P2:also','P3:line','P3:segment','P3:papel',
                 'P3:score_bajo','P4:kept','P5:kept','P7:line','order']


def outcome_of(contact,invited):
    c=contact.classification or {};buyer=c.get('buyer') or {}
    score=red.buyer_score(contact)
    papel=getattr(nivel_comprador,'papel_of',None)
    return {'kept':bool(c.get('fit')) and contact.stage not in ('discarded','closed'),'role':c.get('role'),
            # Only what the classification stores: a buyer of before has no line, segment or papel.
            'line':buyer.get('line'),'segment':buyer.get('segment'),'also':buyer.get('also_segments'),
            'papel':papel(contact) if papel and buyer.get('line')=='projectapp' else None,
            'level':buyer.get('level'),'score':score.get('score'),'breakdown':score.get('breakdown'),
            'journey':BuyerJourney.objects.filter(contact=contact).exists(),'invited':contact.pk in invited,'rule':c.get('rule','')}


class ProjectAppCaseBase(NetworkBase):
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
        """Claude faked: the classifier answers per variant and prompt; the judge reads the one finding it gets."""
        def fake(system,message,**kwargs):
            data=json.loads(message)
            if kwargs.get('purpose')=='network-stage':
                _,variant=self.by_name[data['persona']['nombre']];web=variant['web']
                properties=kwargs['output_schema']['properties']
                answer={'verdict':'confirmado' if 'tamano' in properties else 'probable',
                        'evidence':'La fuente dice que tiene unas 80 personas y vacantes de ingeniería.','source_urls':[web['url']]}
                if 'tamano' in properties:answer['tamano']='20_a_200'
                if 'senales' in properties:
                    kind='contrata_desarrolladores' if 'contrata_desarrolladores' in json.dumps(properties['senales']) else 'contratacion'
                    answer['senales']=[{'tipo':kind,'fecha':web['fecha'],'source_url':web['url'],'evidencia':'Dos vacantes de Software Engineer.'}]
                return {'text':json.dumps(answer),'model':'claude-sonnet-5-5'}
            new='buyer_segment' in system
            rows=[]
            for person in data['people']:
                vid,variant=self.by_name[person['name']];answer=dict(variant['despues' if new else 'antes'])
                if not new:
                    answer.pop('buyer_segment',None);answer.pop('company_size',None)
                # With the ProjectApp prompt the classifier also cites the class 08 units (con_quien) behind each verdict.
                cited=['LI-03-M005-K06',*(WHO_CASE['variants'].get(vid,[]) if new else [])]
                row={'id':person['id'],'affinity':'desconocida','confidence':0.9,'course_citations':cited,
                     'invitation_note':'','note_reason':'','buyer_profile':'','buyer_level':'','us_market':False,**answer}
                if new:row.setdefault('buyer_segment','');row.setdefault('company_size','')
                rows.append(row)
            return {'text':json.dumps({'contacts':rows}),'model':'claude-sonnet-5-5','estimated_usd':0.002}
        return patch('knowledge.providers.claude',side_effect=fake)

    def web(self,request):
        contact=Contact.objects.get(pk=request.key.split(':')[1])
        _,variant=self.by_name[contact.display_name]
        if not variant['web']:return NOTHING
        source=research.Source('s1',variant['web']['url'],'Careers',variant['web']['text'],'2026-11-16T15:00:00+00:00')
        return research.ResearchResult('q','complete','2026-11-16T15:00:00+00:00',(research.Finding(variant['web']['text'],('s1',)),),
                                       (source,),usage={'model':'claude-sonnet-5-5'})

    def run_case(self):
        """Classify on Monday, check the stages that day and the next ones, then plan the invitations with everyone who
        stayed followed three days ago. Returns (outcomes, invited ProjectApp variants in order)."""
        self.seed()
        with self.models(),patch('team_backend.research.research',side_effect=self.web):
            red.classify(self.bot,self.account,MONDAY)
            for n,days in enumerate((0,0,1,2,3)):
                red.check_stages(self.bot,self.account,MONDAY+timedelta(days=days,minutes=5*(n+1)))
            when=MONDAY+timedelta(days=3,hours=1)
            Contact.objects.filter(stage='fit').update(stage='followed',is_following=True,followed_at=when-timedelta(days=3))
            # Two plan cycles: each one proposes at most five invitations (politica_red in equipos/grafo.yaml).
            red.plan(self.bot,self.account,when);red.plan(self.bot,self.account,when+timedelta(hours=1))
        name_of={v['name']:vid for vid,v in CASE['variants'].items()}
        proposals=list(ActionProposal.objects.filter(capability='RED-02').order_by('created_at').values_list('contact_id','contact__display_name'))
        invited={pk for pk,_ in proposals}
        outcomes={name_of[c.display_name]:outcome_of(c,invited) for c in Contact.objects.all()}
        order=[name_of[name] for _,name in proposals if name_of[name] in ('P1','P2','P3','P4')]
        return outcomes,order


class ProjectAppCaseTests(ProjectAppCaseBase):
    def test_antes_the_case_shows_where_the_buyer_of_today_is_only_a_startup_buyer(self):
        outcomes,order=self.run_case()
        grade=evaluaciones.grade_projectapp_case(outcomes,order)
        self.assertEqual((grade['errors'],grade['right']),(BASELINE_ERRORS,'2/8'),(outcomes,order))
        # The buyers of a traditional company go by the score of a startup buyer: the 5-person business ties the academy.
        self.assertEqual(order,['P1','P4','P2','P3'])
        self.assertEqual({v:outcomes[v]['score'] for v in ('P1','P2','P3','P4','P7')},{'P1':82,'P2':59,'P3':59,'P4':70,'P7':99})

    def test_despues_with_the_switch_on_every_person_goes_where_gustavo_said(self):
        with patch.dict(os.environ,{SWITCH:'true'}):
            outcomes,order=self.run_case()
            grade=evaluaciones.grade_projectapp_case(outcomes,order)
            self.assertEqual((grade['errors'],grade['right']),([],'8/8'),(outcomes,order))
            self.assertEqual(order,['P1','P2','P3'])
            # Score v2: P1 confirmed, 80 people, hiring developers, in the US, decides; P3 a 5-person business, at the bottom.
            self.assertEqual({v:outcomes[v]['score'] for v in ('P1','P2','P3','P7')},{'P1':99,'P2':72,'P3':48,'P7':99})
            p1=Contact.objects.get(display_name='Tomas Retail')
            self.assertEqual(p1.classification['buyer']['score_breakdown']['senal']['value'],'contrata_desarrolladores')
            self.assertEqual(outcomes['P4']['rule'],red.projectapp.size_rule())
            # The classifier loaded the class 08 methodology and its verdicts cite it.
            self.assertEqual(p1.classification['course_methodology'],'con_quien')
            self.assertTrue(set(operador.WHO_UNITS)<=set(p1.classification['course_hashes']))
            self.assertTrue(set(WHO_CASE['variants']['P1'])<=set(p1.classification['course_citations']))
            # The reevaluation of 17/11/2026 finds nobody to move: everyone was classified with both lines already.
            self.assertEqual(nivel_comprador.reevaluate(self.gustavo,self.account)['total'],0)
            cited={uid for c in Contact.objects.all() for uid in (c.classification or {}).get('course_citations',[])}
            cited|=set(WHO_CASE['variants']['reevaluacion'])  # the reevaluation's rule (SAID_NO, REQUEUED_PROJECTAPP)
            result={'aciertos':grade['right'],'P1_linea':outcomes['P1']['line'],'P1_papel':outcomes['P1']['papel'],
                    'P1_segmento':outcomes['P1']['segment'],
                    'P1_senal':p1.classification['buyer']['score_breakdown']['senal']['value'],
                    'P2_segmento':outcomes['P2']['segment'],'P2_tambien':outcomes['P2']['also'],'P2_papel':outcomes['P2']['papel'],
                    'P3_puntaje':'bajo' if outcomes['P3']['score']<50 else 'alto','P4_fuera_por':'tamano' if outcomes['P4']['rule']==red.projectapp.size_rule() else '',
                    'P5_rol':outcomes['P5']['role'],'P5_recorrido':outcomes['P5']['journey'],'P6_rol':outcomes['P6']['role'],
                    'P7_linea':outcomes['P7']['line'],'orden':order,'linea_base_apagado':'2/8','course_citations':sorted(cited&set(operador.WHO_UNITS))}
            _,grounding=evaluaciones.course_case_context('con_quien')
            self.assertEqual(evaluaciones.grade_course_case('con_quien',result,grounding)['errors'],[])

    def test_more_than_1000_people_is_out_at_the_classification_before_any_follow_or_web_check(self):
        # The fake classifier keeps P4 «probable» with fit=true: the size rule in code takes her out right there.
        with patch.dict(os.environ,{SWITCH:'true'}):
            self.seed()
            with self.models():red.classify(self.bot,self.account,MONDAY)
        p4=Contact.objects.get(display_name='Diana Global');c=p4.classification
        self.assertEqual((c['fit'],c['rule'],c['buyer']['level'],c['buyer']['company_size'],'stage_check' in c),
                         (False,red.projectapp.size_rule(),'no_encaja','mas_de_1000',False))
        self.assertNotIn(p4.stage,('fit','followed'))


# --------------------------------------------------------------------------- targeted tests (BAR-25)

ON={SWITCH:'true','NETWORK_BUYER_REGION':'us'}
OFF={SWITCH:'false','NETWORK_BUYER_REGION':'us'}


def _sha(value):
    text=value if isinstance(value,str) else json.dumps(value,sort_keys=True,ensure_ascii=False)
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def person(headline,location='Dallas, Texas, United States',bio='',**classification):
    """An unsaved contact with a classification (no database)."""
    return Contact(headline=headline,location=location,signals={'bio':bio} if bio else {},classification=classification)


def buyer(profile,level='probable',**extra):
    return {'profile':profile,'level':level,'us_market':True,'evidence':'','sources':[],'basis':'perfil',**extra}


class SwitchOffTests(TestCase):  # the prompts are read from the member's profile (phase 3)
    """K: NETWORK_PROJECTAPP_BUYER_ENABLED=false is the code of before 17/11/2026 (BAR-24). The hashes are those of
    origin/main at 6508245, computed from its own modules: a change to the prompts or criteria with the switch off fails."""

    def test_prompts_schemas_criteria_and_shares_are_the_ones_of_before(self):
        with patch.dict(os.environ,OFF):
            self.assertIs(red.classify_schema(),red.CLASSIFY_SCHEMA)
            # Phase 3 of organizations: the prompts are templates rendered for the member; for the installation's first
            # person they render to the same bytes (test_identidad_prompts pins all of them).
            ident=identidad.of()
            pins={'CLASSIFY_SYSTEM':_sha(red.classify_system()),'CLASSIFY_SCHEMA':_sha(red.CLASSIFY_SCHEMA),
                  'STAGE_SYSTEM':_sha(red.stage_system()),'STAGE_SCHEMA':_sha(red.STAGE_SCHEMA),
                  'network_criteria':_sha(posicionamiento.network_criteria()),'lead':_sha(lider.criteria_del_barrio()),
                  'ROLE_MEANING':_sha({k:ident.render(v) for k,v in lider.ROLE_MEANING.items() if k!='partner'})}
            self.assertEqual(pins,{'CLASSIFY_SYSTEM':'ede1f6aef1133af0','CLASSIFY_SCHEMA':'94b29b6babde1d63',
                                   'STAGE_SYSTEM':'8f2e44fc186827b7','STAGE_SCHEMA':'092a6c1e12973eb0',
                                   'network_criteria':'cb8975fd47bfc36c','lead':'af5c3d752e71f24c',
                                   'ROLE_MEANING':'92a3ad803d08452d'})
            self.assertEqual(red.roles(),['par','recomendador','lider','comprador','divulgador','aliado'])
            self.assertEqual(red.classify_units(),(red.NETWORK_UNITS,None))
            self.assertEqual(reparto.default_share(),'comprador=20,recomendador+aliado=15,divulgador=20,par=25')
            self.assertEqual(nivel_comprador.score_version(),'buyer_score_v1')
            self.assertEqual(nivel_comprador.actions(),nivel_comprador.ACTIONS)
            self.assertEqual(reparto.keys_of({'role':'comprador','buyer':buyer('lider_tecnologia')}),['comprador'])
            p1=person('CTO at Lone Star Outfitters',role='comprador',fit=True,buyer=buyer('lider_tecnologia',line='projectapp',
                                                                                        segment='retail_ecommerce'))
            self.assertIsNone(projectapp.case_for(p1))
            self.assertEqual(projectapp.case_issues('We built a retail platform in 6 months.',p1),[])
            self.assertEqual(projectapp.partner_ids(None),set())
            self.assertIsNone(calentamiento.group_of(ObservedPostStub('ACo-partner'),set()))

    def test_the_score_of_a_buyer_is_v1_with_the_switch_off(self):
        contact=person('Co-founder & CEO at Paylane · payments API',role='comprador',fit=True,confidence=0.9,
                       buyer=buyer('startup_financiada','confirmado'))
        with patch.dict(os.environ,OFF):result=nivel_comprador.score(contact)
        self.assertEqual((result['version'],set(result['breakdown'])),
                         ('buyer_score_v1',{'evidencia','mercado','papel','servicios','confianza'}))


class ObservedPostStub:
    referent_id=None

    def __init__(self,author):
        self.author_provider_id=author


class LineAndSegmentTests(SimpleTestCase):
    """B and C: the line comes from the profile; papel, size and segment only for a ProjectApp buyer, by the test's rules."""

    def complete(self,contact,profile,result):
        return projectapp.complete(contact,buyer(profile),result)

    def test_a_technology_leader_of_a_retail_chain_is_a_projectapp_buyer_of_retail(self):
        p1=person('CTO at Lone Star Outfitters · family retail chain')
        got=self.complete(p1,'lider_tecnologia',{'buyer_segment':'retail_ecommerce','company_size':'20_a_200','affinity':'desconocida'})
        self.assertEqual({k:got[k] for k in ('line','papel','segment','also_segments','company_size')},
                         {'line':'projectapp','papel':'lider_tecnologia','segment':'retail_ecommerce','also_segments':[],
                          'company_size':'20_a_200'})

    def test_a_latina_owner_in_the_us_keeps_her_industry_and_also_matches_the_latino_owners(self):
        p2=person('Fundadora y directora de Academia Clara',location='Miami, Florida, United States')
        got=self.complete(p2,'dueno_empresa_tradicional',{'buyer_segment':'educacion_en_linea','company_size':'20_a_200',
                                                          'affinity':'hispanohablante_declarada'})
        self.assertEqual((got['segment'],got['also_segments'],got['papel']),('educacion_en_linea',['duenos_latinos_eeuu'],'dueno'))
        # Another industry: the latino owners are her segment. Outside the US, or not declared, she is «otro».
        got=self.complete(p2,'dueno_empresa_tradicional',{'buyer_segment':'otro','affinity':'hispanohablante_declarada'})
        self.assertEqual((got['segment'],got['also_segments']),('duenos_latinos_eeuu',[]))
        away=person('Dueña de una academia',location='Bogotá, Colombia')
        got=projectapp.complete(away,dict(buyer('dueno_empresa_tradicional'),us_market=False),
                                {'buyer_segment':'duenos_latinos_eeuu','affinity':'hispanohablante_declarada'})
        self.assertEqual(got['segment'],'otro')
        got=self.complete(p2,'dueno_empresa_tradicional',{'buyer_segment':'duenos_latinos_eeuu','affinity':'desconocida'})
        self.assertEqual(got['segment'],'otro')

    def test_a_startup_buyer_has_the_startup_line_and_no_papel_or_segment(self):
        got=self.complete(person('Co-founder & CEO at Paylane'),'startup_financiada',{'buyer_segment':'retail_ecommerce'})
        self.assertEqual(got['line'],'startup')
        self.assertFalse({'papel','segment','also_segments'}&set(got))

    def test_a_size_the_classifier_did_not_read_is_empty_and_more_than_1000_is_too_big(self):
        p4=person('Director of IT, North America')
        self.assertEqual(self.complete(p4,'lider_tecnologia',{'company_size':'huge'})['company_size'],'')
        self.assertTrue(projectapp.too_big(self.complete(p4,'lider_tecnologia',{'company_size':'mas_de_1000'})))
        self.assertFalse(projectapp.too_big(self.complete(p4,'ejecutivo',{'company_size':'mas_de_1000'})))

    def test_the_papel_follows_the_profile_then_the_headline(self):
        self.assertEqual(projectapp.papel_from('','CTO & co-owner at Desert Plumbing'),'lider_tecnologia')
        self.assertEqual(projectapp.papel_from('','Owner at Desert Plumbing Co.'),'dueno')
        self.assertEqual(projectapp.papel_from('','Marketing coordinator'),'')
        self.assertEqual(projectapp.papel_from('dueno_empresa_tradicional','CTO'),'dueno')


class ProfilesAndQuestionsTests(SimpleTestCase):
    """B: the two new profiles carry their web and judge questions; the ProjectApp schemas ask for segment, size, the
    partner and dated signals with a source in the same call."""

    def test_each_new_profile_has_its_web_query_and_its_judge_question(self):
        for profile in projectapp.PROFILES:
            self.assertEqual(set(nivel_comprador.QUESTIONS[profile]),{'web','juez'})
            self.assertIn('{company}',nivel_comprador.QUESTIONS[profile]['web'])
            self.assertIn('20 a 200',nivel_comprador.QUESTIONS[profile]['juez'])

    def test_the_projectapp_schemas_name_the_partner_the_segment_the_size_and_the_signals(self):
        item=red.CLASSIFY_SCHEMA_PROJECTAPP['properties']['contacts']['items']
        self.assertIn('partner',item['properties']['role']['enum'])
        self.assertTrue(set(projectapp.PROFILES)<=set(item['properties']['buyer_profile']['enum']))
        self.assertTrue({'buyer_segment','company_size'}<=set(item['required']))
        self.assertNotIn('partner',red.CLASSIFY_SCHEMA['properties']['contacts']['items']['properties']['role']['enum'])
        signal=red.STAGE_SCHEMA_PROJECTAPP['properties']['senales']['items']
        self.assertEqual(set(signal['required']),{'tipo','fecha','source_url','evidencia'})
        self.assertEqual(signal['properties']['tipo']['enum'],list(projectapp.SIGNAL_KINDS))
        with patch.dict(os.environ,ON):
            self.assertIs(red.classify_schema(),red.CLASSIFY_SCHEMA_PROJECTAPP)
            self.assertIn('partner',red.roles())
            self.assertEqual(red.classify_units()[1],'con_quien')


class ScoreV2Tests(SimpleTestCase):
    """B: buyer_score_v2. The breakdown adds up to the score; a missing datum takes the middle of its component."""

    def scored(self,contact):
        with patch.dict(os.environ,ON):return nivel_comprador.score(contact)

    def test_a_confirmed_technology_leader_of_80_people_who_hires_developers(self):
        check={'state':'ok','verdict':'confirmado','senales':[{'tipo':'contrata_desarrolladores','fecha':'2026-11-10',
               'fuente':'https://lonestar.example/careers','evidencia':'Dos vacantes','visto':'2026-11-16T15:00:00+00:00'}]}
        p1=person('CTO at Lone Star Outfitters · family retail chain, 80 people',role='comprador',fit=True,confidence=0.9,
                  stage_check=check,buyer=buyer('lider_tecnologia','confirmado',line='projectapp',company_size='20_a_200',
                                                papel='lider_tecnologia',segment='retail_ecommerce'))
        result=self.scored(p1)
        points={k:v['points'] for k,v in result['breakdown'].items()}
        self.assertEqual(points,{'evidencia':32,'tamano':26,'senal':10,'mercado':14,'papel':12,'confianza':5})
        self.assertEqual((result['score'],result['version']),(99,'buyer_score_v2'))

    def test_every_missing_datum_takes_the_middle_of_its_component(self):
        thin=person('',location='',role='comprador',fit=True,confidence=0.5,
                    buyer=dict(buyer('dueno_empresa_tradicional','por_confirmar',line='projectapp'),us_market=False,papel=''))
        thin.classification['buyer']['profile']=''  # neither the profile nor the headline says the papel
        result=self.scored(thin);parts=result['breakdown']
        missing={component:(parts[component]['value'],parts[component]['points']) for component in ('tamano','senal','mercado','papel')}
        # Hand-checked middles: size (26+0)/2, signal 10/2, market (14+2)/2, papel (12+4)/2.
        self.assertEqual(missing,{'tamano':('sin_dato',13),'senal':('sin_dato',5),'mercado':('sin_dato',8),'papel':('sin_dato',8)})
        self.assertEqual(result['score'],10+13+5+8+8+3)
        self.assertIn('sin tamaño de empresa',result['warnings'])

    def test_a_signal_needs_a_date_and_an_old_one_weighs_less(self):
        def with_signal(fecha,tipo='contrata_desarrolladores'):
            check={'state':'ok','senales':[{'tipo':tipo,'fecha':fecha,'fuente':'https://x.example','evidencia':'',
                                            'visto':'2026-11-16T15:00:00+00:00'}]}
            contact=person('Owner at Desert Plumbing Co.',role='comprador',fit=True,stage_check=check,
                           buyer=buyer('dueno_empresa_tradicional',line='projectapp'))
            return self.scored(contact)['breakdown']['senal']['value']
        self.assertEqual([with_signal(''),with_signal('2026-11-01'),with_signal('2026-01-10'),with_signal('2026-11-01','crecimiento')],
                         ['sin_dato','contrata_desarrolladores','antigua','reciente'])

    def test_the_startup_line_keeps_the_components_and_points_of_v1(self):
        p7=person('Co-founder & CEO at Paylane · payments API for marketplaces',location='San Francisco, California, United States',
                  role='comprador',fit=True,confidence=0.9,buyer=buyer('startup_financiada','confirmado',line='startup'))
        v2=self.scored(p7)
        with patch.dict(os.environ,OFF):v1=nivel_comprador.score(p7)
        self.assertEqual((v2['score'],v2['breakdown']),(v1['score'],v1['breakdown']))
        self.assertEqual(v2['version'],'buyer_score_v2')


class ShareTests(SimpleTestCase):
    """F: the 80 a week by audience, 60/40 soft between papeles, overflow, and the deficit."""

    def order(self,candidates,counts=None):
        with patch.dict(os.environ,ON),patch('team_backend.reparto.week_counts',return_value=counts or {}),\
             patch('team_backend.reparto.weekly_invitations',return_value=80):
            return reparto.order(candidates,None)

    def projectapp_buyer(self,name,papel):
        profile='lider_tecnologia' if papel=='lider_tecnologia' else 'dueno_empresa_tradicional'
        contact=person(name,role='comprador',fit=True,buyer=buyer(profile,line='projectapp',papel=papel))
        contact.display_name=name
        return contact

    def names(self,contacts):
        return [c.display_name for c in contacts]

    def test_the_default_with_the_switch_on_is_gustavos_split_and_it_validates(self):
        with patch.dict(os.environ,ON):
            self.assertEqual(reparto.shares(),[(('comprador_projectapp',),28),(('comprador_startup',),12),(('partner',),12),
                                               (('recomendador','aliado'),8),(('par',),10),(('divulgador',),10)])
        with patch.dict(os.environ,dict(ON,NETWORK_ROLE_SHARE='comprador=20,comprador_projectapp=10')),self.assertRaises(ValueError):
            reparto.shares()
        with patch.dict(os.environ,dict(OFF,NETWORK_ROLE_SHARE='partner=10')),self.assertRaisesRegex(ValueError,'desconocido'):
            reparto.shares()

    def test_owners_and_leaders_alternate_softly_60_40(self):
        queue=[self.projectapp_buyer(f'L{n}','lider_tecnologia') for n in range(6)]+[self.projectapp_buyer(f'D{n}','dueno') for n in range(6)]
        ordered,report=self.order(queue)
        first_ten=self.names(ordered)[:10]
        self.assertEqual(sum(name.startswith('L') for name in first_ten),6)
        self.assertEqual(first_ten[:3],['L0','D0','L1'])
        self.assertEqual(report[0]['papel'],{'lider_tecnologia':{'share':60,'invited':0},'dueno':{'share':40,'invited':0}})
        # Leaders already ahead this week: the owners get the next turns.
        ordered,_=self.order(queue,{'comprador_projectapp':5,'papel:lider_tecnologia':5})
        self.assertEqual(self.names(ordered)[:2],['D0','D1'])

    def test_a_group_without_candidates_leaves_its_turn_and_nobody_waits_for_a_percentage(self):
        d1,d2=self.projectapp_buyer('D1','dueno'),self.projectapp_buyer('D2','dueno')
        startup=person('Founder at Acme',role='comprador',fit=True,buyer=buyer('stealth',line='startup'));startup.display_name='S'
        peer=person('Engineer',role='par',fit=True);peer.display_name='P'
        ordered,report=self.order([d1,d2,startup,peer])
        self.assertEqual(self.names(ordered),['D1','S','P','D2'])  # no leaders, partners or spreaders: the owners and the rest go
        with patch.dict(os.environ,ON):reparto.planned(report,ordered[:2])
        rows={tuple(row['roles']):row for row in report}
        self.assertEqual((rows[('comprador_projectapp',)]['weekly_target'],rows[('comprador_projectapp',)]['deficit'],
                          rows[('comprador_projectapp',)]['planned'],rows[('partner',)]['ready']),(28,28,1,0))


class CaseRuleTests(TestCase):  # the cases are the organization's profile (phase 3)
    """G (the fixed rule, without the database): a case only to a buyer of its segment and only with confirmed facts."""

    def setUp(self):
        facts=patch('team_backend.projectapp.case_facts',side_effect=lambda s,member=None:{'caso':posicionamiento.cases()[s]})  # its signature
        facts.start();self.addCleanup(facts.stop)
        env=patch.dict(os.environ,ON);env.start();self.addCleanup(env.stop)

    def buyer_of(self,segment,line='projectapp',also=()):
        profile='lider_tecnologia' if line=='projectapp' else 'startup_financiada'
        return person('CTO',role='comprador',fit=True,buyer=buyer(profile,line=line,segment=segment,also_segments=list(also)))

    def test_only_a_buyer_of_the_cases_segment_gets_it(self):
        self.assertEqual(projectapp.case_for(self.buyer_of('retail_ecommerce'))['segmento'],'retail_ecommerce')
        self.assertEqual(projectapp.case_for(self.buyer_of('duenos_latinos_eeuu')),None)
        self.assertEqual(projectapp.case_for(self.buyer_of('otro')),None)
        self.assertEqual(projectapp.case_for(self.buyer_of('retail_ecommerce',line='startup')),None)
        self.assertEqual(projectapp.case_for(self.buyer_of('educacion_en_linea',also=['duenos_latinos_eeuu']))['segmento'],
                         'educacion_en_linea')

    def test_another_segments_case_and_an_unconfirmed_figure_are_issues_the_offers_price_is_not(self):
        retail=self.buyer_of('retail_ecommerce')
        self.assertEqual(projectapp.case_issues('We built a large learning platform for an online academy.',retail),
                         ['Cita un caso de ProjectApp de otro segmento (Educación en línea): solo se cita a un comprador del mismo segmento'])
        self.assertEqual(projectapp.case_issues('We built a custom retail platform in 6 months and sales grew 40%.',retail),
                         ['Cifra del caso que Gustavo no confirmó (6, 40)'])
        self.assertEqual(projectapp.case_issues('We built a custom retail platform; a dedicated team starts near 5,000 USD a month.',retail),[])
        self.assertEqual(projectapp.case_issues('Retail teams often hire 3 developers first.',retail),[])  # no case cited
        self.assertTrue(projectapp.case_issues('We built an e-commerce platform.',self.buyer_of('otro'))[0]
                        .startswith('Cita un caso de ProjectApp de otro segmento (Retail y e-commerce)'))


class ProjectAppDatabaseTests(ProjectAppCaseBase):
    """G, I and J with the database: the case questions and facts, the reevaluation and the test's reading."""

    def setUp(self):
        super().setUp()
        env=patch.dict(os.environ,ON);env.start();self.addCleanup(env.stop)

    def contact(self,name,headline,classification,stage,history=(),**fields):
        return Contact.objects.create(account=self.account,provider_user_id='ACo'+name.replace(' ','').lower(),display_name=name,
                                      headline=headline,location='Austin, Texas, United States',classification=classification,
                                      stage=stage,history=list(history),source='search',**fields)

    def test_the_case_questions_are_queued_once_and_only_public_confirmed_answers_become_facts(self):
        self.grant(self.gustavo,'confirm_memory')
        out=StringIO()
        call_command('operador','--usuario',self.gustavo.username,'preguntas-casos-projectapp',stdout=out)
        self.assertIn('creadas ahora: 10 de 10',out.getvalue())
        self.assertEqual(TeamQuestion.objects.filter(origin=projectapp.CASE_ORIGIN).count(),10)
        again=StringIO()
        call_command('operador','--usuario',self.gustavo.username,'preguntas-casos-projectapp',stdout=again)
        self.assertIn('creadas ahora: 0 de 10',again.getvalue())
        ask=lambda what:TeamQuestion.objects.get(memory_key=projectapp.case_key('retail_ecommerce',what))
        preguntas.answer(self.gustavo,ask('duracion').pk,'La primera versión salió en 6 meses.',public_use=True)
        preguntas.answer(self.gustavo,ask('cliente').pk,'No',public_use=True)
        preguntas.answer(self.gustavo,ask('cambio').pk,'Las ventas en línea crecieron 40 %.',public_use=False)
        self.assertEqual(projectapp.ask_case_questions(),[])  # answered keys are never asked again
        facts=projectapp.case_facts('retail_ecommerce')
        self.assertEqual(facts,{'caso':posicionamiento.cases()['retail_ecommerce'],'duracion':'La primera versión salió en 6 meses.'})
        retail=self.contact('Tomas Retail','CTO at Lone Star Outfitters',{'role':'comprador','fit':True,'buyer':buyer(
            'lider_tecnologia',line='projectapp',segment='retail_ecommerce')},'followed')
        self.assertEqual(projectapp.case_issues('We built a custom retail platform; the first version took 6 months.',retail),[])
        self.assertEqual(projectapp.case_issues('We built a custom retail platform and online sales grew 40%.',retail),
                         ['Cifra del caso que Gustavo no confirmó (40)'])

    def test_the_reevaluation_lists_without_changing_then_moves_each_person_once(self):
        startup=buyer('startup_financiada')
        followed=self.contact('Ana Followed','Founder & CEO at Acme',{'role':'comprador','fit':True,'buyer':startup},'followed',
                              followed_at=MONDAY)
        untouched=self.contact('Ben Untouched','CEO at Family Retail Co',{'role':'comprador','fit':True,'buyer':startup},'fit')
        agency=self.contact('Marco Agencia','Founder at Brightside Marketing agency · websites for local businesses',
                            {'role':'aliado','fit':False,'reason':'Vende marketing a negocios locales.'},'discarded')
        self.contact('Vetoed Agency','Founder at Bold Design studio · web design',{'role':'aliado','fit':False},'discarded',
                     history=[{'event':'rejected','at':'2026-11-10T00:00:00+00:00','detail':'Gustavo: no'}])
        self.contact('Cfo Aliada','Fractional CFO for seed-stage startups',{'role':'aliado','fit':False},'discarded')
        dry=nivel_comprador.reevaluate(self.gustavo,self.account)
        self.assertEqual({row['name']:(row['group'],row['action'],row['line']) for row in dry['people']},
                         {'Ana Followed':('linea','completar','startup'),'Ben Untouched':('otra_linea','reclasificar','startup'),
                          'Marco Agencia':('posible_partner','reclasificar','partner?')})
        self.assertEqual((dry['applied'],Contact.objects.get(pk=untouched.pk).stage),(0,'fit'))
        done=nivel_comprador.reevaluate(self.gustavo,self.account,confirm=True)
        self.assertEqual(done['applied'],3)
        followed.refresh_from_db();untouched.refresh_from_db();agency.refresh_from_db()
        self.assertEqual((followed.stage,followed.classification['buyer']['line'],followed.classification['buyer']['score_version']),
                         ('followed','startup','buyer_score_v2'))
        self.assertEqual((untouched.stage,untouched.classification,agency.stage,agency.classification),('candidate',{},'candidate',{}))
        self.assertEqual(agency.history[-1]['detail'],nivel_comprador.REQUEUED_PROJECTAPP)
        self.assertEqual(AuditEvent.objects.filter(action=nivel_comprador.REEVALUATED).count(),3)
        self.assertEqual(nivel_comprador.reevaluate(self.gustavo,self.account)['total'],0)
        # The classifier discards the agency again as an ally: she already went back once, so she is not sent again.
        Contact.objects.filter(pk=agency.pk).update(stage='discarded',classification={'role':'aliado','fit':False})
        self.assertEqual(nivel_comprador.reevaluate(self.gustavo,self.account)['total'],0)

    def test_the_reevaluation_with_the_switch_off_finds_only_the_groups_of_before(self):
        self.contact('Ana Followed','Founder & CEO at Acme',{'role':'comprador','fit':True,'buyer':buyer('startup_financiada')},'followed')
        self.contact('Marco Agencia','Founder at Brightside Marketing agency',{'role':'aliado','fit':False},'discarded')
        with patch.dict(os.environ,OFF):result=nivel_comprador.reevaluate(self.gustavo,self.account)
        self.assertEqual((result['total'],set(result['found'])),(0,set(nivel_comprador.ACTIONS)))

    def test_the_funnel_and_the_monday_reading_split_by_line_and_segment_and_count_the_test_weeks(self):
        self.assertEqual([projectapp.test_week(datetime(2026,11,17,9,tzinfo=BOGOTA)),projectapp.test_week(datetime(2026,11,24,9,tzinfo=BOGOTA)),
                          projectapp.test_week(datetime(2027,2,17,9,tzinfo=BOGOTA)),projectapp.test_week(datetime(2027,2,18,9,tzinfo=BOGOTA))],
                         [1,2,13,14])
        now=datetime(2026,11,25,10,tzinfo=BOGOTA)
        for n in range(3):
            c=self.contact(f'Retail {n}','CTO at Shop',{'role':'comprador','fit':True,'buyer':buyer(
                'lider_tecnologia',line='projectapp',segment='retail_ecommerce')},'invited')
            BuyerJourney.objects.create(contact=c,entry=BuyerJourney.Entry.OUTBOUND,line='projectapp',segment='retail_ecommerce',
                                        chosen_at=now-timedelta(days=4),invited_at=now-timedelta(days=2))
        c=self.contact('Seed Founder','Founder at Paylane',{'role':'comprador','fit':True,'buyer':buyer('startup_financiada',line='startup')},'invited')
        BuyerJourney.objects.create(contact=c,entry=BuyerJourney.Entry.OUTBOUND,line='startup',chosen_at=now-timedelta(days=4),
                                    invited_at=now-timedelta(days=2))
        funnel=comprador.funnel(weeks=2,now=now,account=self.account)
        self.assertEqual((funnel['por_linea']['projectapp']['invitaciones'],funnel['por_linea']['startup']['invitaciones']),(3,1))
        self.assertEqual(funnel['por_segmento']['retail_ecommerce']['invitaciones'],3)
        self.assertTrue(funnel['por_segmento']['retail_ecommerce']['muestra_chica'])
        test=funnel['prueba_projectapp']
        self.assertEqual((test['semana'],test['de'],test['revision'],test['por_segmento']['retail_ecommerce']['invitaciones'],
                          test['por_segmento']['retail_ecommerce']['muestra']),(2,13,'2027-02-17',3,False))
        reading=lectura_embudo.read(now,self.account)
        self.assertEqual(reading['por_segmento']['retail_ecommerce']['invitaciones'],3)
        self.assertLessEqual(len(reading['lineas']),5)
        line=next(text for text in reading['lineas'] if text.startswith('Prueba ProjectApp'))
        self.assertIn('semana 2 de 13',line);self.assertIn('retail y e-commerce 3',line);self.assertIn('17/02/2027',line)
        self.assertIn('ningún segmento tiene muestra todavía (30 invitaciones)',line.lower())
        with patch.dict(os.environ,OFF):
            self.assertFalse({'por_linea','por_segmento','prueba_projectapp'}&set(comprador.funnel(weeks=2,now=now,account=self.account)))
            self.assertFalse(any(text.startswith('Prueba ProjectApp') for text in lectura_embudo.read(now,self.account)['lineas']))


class SearchRotationTests(SimpleTestCase):
    """D: the searches rotate by audience in proportion to 28/12/12, each audience through its own queries."""

    def test_thirteen_searches_go_seven_three_three_and_each_audience_rotates_its_queries(self):
        done={};seen=[]
        with patch.dict(os.environ,dict(ON,NETWORK_SEARCH_QUERIES='founder pre-seed')):
            for _ in range(13):
                audience,query=projectapp.next_search(done);seen.append((audience,query));done[audience]=done.get(audience,0)+1
        self.assertEqual(done,{'projectapp':7,'startup':3,'partner':3})
        self.assertEqual(seen[:4],[('projectapp','CTO retail'),('startup','founder pre-seed'),
                                   ('partner','marketing agency founder development partners'),('projectapp','Director of IT ecommerce')])
        self.assertEqual([q for a,q in seen if a=='projectapp'],
                         ['CTO retail','Director of IT ecommerce','Head of Technology online education','Owner online academy',
                          'VP Engineering retail','CEO family business','dueño de empresa [es]'])

    def test_a_bad_share_is_ignored_and_an_audience_without_queries_never_gets_a_turn(self):
        with patch.dict(os.environ,dict(ON,NETWORK_SEARCH_QUERIES='',NETWORK_SEARCH_AUDIENCE_SHARE='projectapp=x,partner=12')):
            self.assertEqual(projectapp.audience_shares(),{'partner':12})
            self.assertEqual(projectapp.next_search({}),('partner','marketing agency founder development partners'))
        with patch.dict(os.environ,dict(ON,NETWORK_SEARCH_QUERIES='',NETWORK_SEARCH_QUERIES_PROJECTAPP='',NETWORK_SEARCH_QUERIES_PARTNER='')):
            self.assertIsNone(projectapp.next_search({}))


class DiscoverByAudienceTests(ProjectAppCaseBase):
    """D with the fake connector: discovery takes its turn by audience inside NETWORK_SEARCHES_PER_RUN and the daily search
    cap (NETWORK_READ_CAPS search), and records the class 08 methodology."""

    def test_two_searches_a_run_by_audience_until_the_daily_cap(self):
        with patch.dict(os.environ,dict(ON,NETWORK_READ_CAPS='search=4',NETWORK_SEARCHES_PER_RUN='2')):
            first=red.discover(self.bot,self.account);second=red.discover(self.bot,self.account);third=red.discover(self.bot,self.account)
        self.assertEqual([r['searches'] for r in (first,second,third)],[2,2,0])
        self.assertIn('Tope diario de lecturas «search»',third['stopped'])
        self.assertEqual([call['keywords'] for call in self.fake.state['search_calls']],
                         ['CTO retail','founder pre-seed','marketing agency founder development partners','Director of IT ecommerce'])
        audiences=list(AuditEvent.objects.filter(action='network.searched').order_by('created_at').values_list('metadata__audience',flat=True))
        self.assertEqual(audiences[:4],['projectapp','startup','partner','projectapp'])
        self.assertEqual(first['course_methodology'],'con_quien')
        self.assertTrue(set(operador.WHO_UNITS)<=set(first['course_citations']))

    def test_with_the_switch_off_discovery_searches_as_before(self):
        with patch.dict(os.environ,dict(OFF,NETWORK_SEARCHES_PER_RUN='2')):result=red.discover(self.bot,self.account)
        self.assertEqual([call['keywords'] for call in self.fake.state['search_calls']],['founder pre-seed'])
        self.assertNotIn('course_methodology',result)
        self.assertFalse(AuditEvent.objects.filter(action='network.searched',metadata__has_key='audience').exists())


class PartnerLeadTests(SimpleTestCase):
    """E: the lead asks of a partner whether he sells development himself (a competitor is a peer, never a partner)."""

    def test_the_partner_check_and_its_meaning(self):
        checks=[qid for qid,*_ in lider.network_checks(lider.CAP.INVITE,'partner')]
        self.assertEqual(checks,['falsa','empresa','reclutador','prospector','competidor'])
        self.assertNotIn('competidor',[qid for qid,*_ in lider.network_checks(lider.CAP.INVITE,'comprador')])
        self.assertIn('subcontrata',lider.ROLE_MEANING['partner'])
        self.assertEqual(red.ROLE_LABELS['partner'],'Partner')


class WhoActivationTests(SimpleTestCase):
    """H: the class 08 methodology «con_quien» opens only its nine units, only when named, only in its roles."""

    def test_the_activated_list_is_the_case_and_the_graph_list(self):
        from knowledge.clases import CLASES_AGENTES, METODOLOGIAS_ACTIVAS, legible_por_agentes
        from team_backend.orquestacion import load_graph
        activa=METODOLOGIAS_ACTIVAS['con_quien']
        self.assertEqual(CLASES_AGENTES,tuple(range(1,7)))
        self.assertEqual(list(activa['unidades']),operador.WHO_UNITS)
        self.assertEqual((activa['evaluacion'],activa['lista']),(WHO_CASE['id'],'operador.WHO_UNITS'))
        self.assertEqual((WHO_CASE['units'],set(WHO_CASE['required'])),(operador.WHO_UNITS,set(operador.WHO_UNITS)))
        for uid in operador.WHO_UNITS:
            self.assertTrue(legible_por_agentes(uid,'con_quien'))
            self.assertFalse(legible_por_agentes(uid))
        # Not adopted: the G×S×T×E campaigns, the lists' tools and the rest of class 08 stay closed.
        for uid in ('LI-08-M001-K03','LI-08-M004-K03','LI-08-M005-K01','LI-08-V001-K01'):
            self.assertFalse(legible_por_agentes(uid,'con_quien'),uid)
        graph=load_graph()
        self.assertEqual(graph['course_lists']['operador.WHO_UNITS'],operador.WHO_UNITS)
        self.assertEqual([n['id'] for n in graph['nodes'] if 'operador.WHO_UNITS' in n['course_lists']],list(activa['roles']))

    def test_the_reading_registry_matches_the_activation(self):
        from pathlib import Path
        from knowledge.clases import METODOLOGIAS_ACTIVAS
        activa=METODOLOGIAS_ACTIVAS['con_quien']
        path=Path(operador.__file__).resolve().parents[3]/'equipos'/activa['registro']
        if not path.exists():self.skipTest('La imagen solo empaqueta grafo.yaml; el registro vive en equipos/observatorio.')
        registry=json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual((registry['metodologia'],registry['evaluacion'],registry['lista'],tuple(registry['roles'])),
                         ('con_quien',activa['evaluacion'],activa['lista'],activa['roles']))
        self.assertEqual([u['unidad_id'] for u in registry['unidades']],operador.WHO_UNITS)
        self.assertEqual(registry['alcance']['por_clase'],{'08':9})
        for unit in registry['unidades']:
            self.assertEqual(unit['clase'],8);self.assertTrue(unit['lectura_completa'])
            self.assertRegex(unit['hash'],r'^[0-9a-f]{64}$');self.assertRegex(unit['pointer'],r'^/learning_units/\d+$')
            self.assertTrue(unit['criterio_derivado'] and unit['limites_y_excepciones'] and unit['uso'])
            sources=unit['fuentes_con_prefijo_de_clase']
            self.assertTrue(sources and all(key.startswith('08:') for key in sources),unit['unidad_id'])
        decisions=' '.join(registry['decisiones_vigentes_que_ganan'])
        for item in ('60 %','LI-08-M004-K04','28','NETWORK_PROJECTAPP_BUYER_ENABLED=false'):self.assertIn(item,decisions)
        not_adopted=' '.join(registry['no_convertido_en_regla'])
        for item in ('G×S×T×E','lemlist','Sales Navigator','pago'):self.assertIn(item,not_adopted)
