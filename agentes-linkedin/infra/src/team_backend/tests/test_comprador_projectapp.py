"""BAR-25-comprador-projectapp: the ProjectApp buyer (traditional companies of 20 to 200 people in the United States that
need software), the startup buyer and the partner (agencies that subcontract development), Gustavo 17/11/2026.

The case (evaluaciones.PROJECTAPP_CASE) has eight synthetic people. Each one goes through the production path:
classification (red.classify, Claude faked), the web check (red.check_stages, research and judge faked) and the plan of
invitations (red.plan) once everyone who stayed is followed. The fake classifier answers what the prompt of 17/11/2026
(BAR-24) asks for (`antes`) or what the ProjectApp prompt asks for (`despues`), depending on the prompt it receives:
what is proven is what the code does with each answer, not how the real model answers. Synthetic people and sources."""
import json
import os
from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from team_backend import evaluaciones, nivel_comprador, operador, red, research
from team_backend.models import ActionProposal, BuyerJourney, Contact
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
            self.assertEqual(outcomes['P4']['rule'],red.projectapp.SIZE_RULE)
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
                    'P3_puntaje':'bajo' if outcomes['P3']['score']<50 else 'alto','P4_fuera_por':'tamano' if outcomes['P4']['rule']==red.projectapp.SIZE_RULE else '',
                    'P5_rol':outcomes['P5']['role'],'P5_recorrido':outcomes['P5']['journey'],'P6_rol':outcomes['P6']['role'],
                    'P7_linea':outcomes['P7']['line'],'orden':order,'linea_base_apagado':'2/8','course_citations':sorted(cited&set(operador.WHO_UNITS))}
            _,grounding=evaluaciones.course_case_context('con_quien')
            self.assertEqual(evaluaciones.grade_course_case('con_quien',result,grounding)['errors'],[])
