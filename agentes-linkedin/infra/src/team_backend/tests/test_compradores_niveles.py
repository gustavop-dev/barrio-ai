"""BAR-18-compradores: who of the buyers stays in the neighborhood, with what level, and in what order they are invited.

The case (evaluaciones.BUYERS_CASE) has seven synthetic people built from the verdicts measured in production on
17/11/2026. Each one goes through the production path: classification (red.classify, Claude faked), the web check of the
stage (red.check_stages, the research and the judge faked) for three days, and the plan of invitations (red.plan). The
fake classifier answers what the production model answered with the prompt of 12/11/2026 (`antes`) or what the prompt
of 17/11/2026 asks for (`despues`), depending on the prompt it receives: what is proven is what the code does with each
answer, not how the real model answers. Synthetic people and sources only."""
import json
import os
from datetime import datetime, timedelta
from unittest import expectedFailure
from unittest.mock import patch
from zoneinfo import ZoneInfo

from team_backend import evaluaciones, red, research
from team_backend.models import ActionProposal, Contact
from team_backend.tests.test_red import NetworkBase

BOGOTA=ZoneInfo('America/Bogota')
CASE=evaluaciones.BUYERS_CASE
MONDAY=datetime(2026,11,16,10,tzinfo=BOGOTA)
# A search that ran and found nothing citable (it has usage).
NOTHING=research.ResearchResult('q','unavailable','2026-11-16T15:00:00+00:00',usage={'model':'claude-sonnet-5-5'})


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
            score=red.buyer_score(contact) if hasattr(red,'buyer_score') else {}
            outcomes[name_of[contact.display_name]]={
                'kept':bool(c.get('fit')) and contact.stage not in ('discarded','closed'),'stage':contact.stage,
                'level':(c.get('buyer') or {}).get('level'),'score':score.get('score'),'breakdown':score.get('breakdown'),
                'warnings':score.get('warnings'),'rule':c.get('rule','')}
        invited=[name_of[name] for name in ActionProposal.objects.filter(capability='RED-02').order_by('created_at')
                 .values_list('contact__display_name',flat=True)]
        return outcomes,invited

    # Línea base (docs/linea-base-compradores.md): hoy C1, C2 y C4 salen del barrio y nadie lleva nivel ni puntaje.
    @expectedFailure
    def test_the_buyers_case_keeps_who_lacks_evidence_and_drops_who_has_evidence_against(self):
        outcomes,invited=self.run_case()
        grade=evaluaciones.grade_buyers_case(outcomes,invited)
        self.assertTrue(grade['passed'],(grade,outcomes,invited))
