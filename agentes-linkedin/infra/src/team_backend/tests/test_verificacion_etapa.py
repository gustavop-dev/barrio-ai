"""The buyers' web check runs in its own run of the network cycle (check_buyer_stages, with its own budget) and the
classification (classify_contacts) only classifies.

18/11/2026: every morning «Ciclo detenido: red. Se alcanzó el presupuesto del ciclo». Inside ONE run of classify_contacts
the classification (network-classify, ~0.22 USD since 17/11) and the reserve of the web research of a buyer
(web-research-tool, its worst case, ~0.85–0.89 USD, reserved before searching) passed the run's cost_cap_usd (1 USD): the
run stopped with cost_cap before checking anyone (0 checks that day, 6 buyers waiting).

The paid calls go through the real path: knowledge.providers.claude with a fake Anthropic SDK client (no network), the
configured prices and reserves (MODEL_PRICES, the WEB_* settings), the real cycle runtime (orquestacion.provider_metadata)
and the real worker. The fake client counts the tokens of the request it gets and answers with the worst case: each call
spends its whole reserve. A run whose worst case passes its cost_cap_usd stops here as it does in production."""
import json
import math
import os
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from django.conf import settings
from django.test import override_settings
from knowledge import db, providers
from knowledge.ingest import ENC
from team_backend import autopiloto, jobs, operador, orquestacion, red
from team_backend.grafo import load_graph
from team_backend.models import Contact, CycleLedger, Job, WebResearchRun
from team_backend.tests.test_red import NetworkBase

BOGOTA=ZoneInfo('America/Bogota')
# Paid calls through providers.claude with the fake SDK client below; the web is on for the research step.
LIVE={'LIVE_PROVIDERS':'true','ANTHROPIC_API_KEY':'fake-only','ANTHROPIC_LIMIT_USD':'','AI_MONTHLY_LIMIT_USD':'100',
      'AI_DAILY_FUSE_USD':'15','NETWORK_STAGE_CHECK':'true','NETWORK_BUYER_REGION':'us','NETWORK_STAGE_CHECKS_PER_DAY':'6',
      # Production since 17/11/2026: the ProjectApp buyer, the larger classifier prompt (9 more course units).
      'NETWORK_PROJECTAPP_BUYER_ENABLED':'true'}
# Claude's tokenizer can count more tokens than cl100k for the same text: the estimate takes 25 % more.
CLAUDE_PER_CL100K=1.25
# What count_tokens adds for the server web tools (their own instructions, not in the request): the research reserves of
# 0.85–0.89 USD in production (18/11/2026) are 4,900–8,100 counted input tokens for some 470 visible ones.
SERVER_TOOLS_TOKENS=7700
COURSE='Unidades del curso (course_units):'  # operador.course_block
URL='https://www.acmeoutfitters.com/careers'  # a public host: research keeps no source on .example (web_sources)
FACT='Acme Outfitters has about 80 employees, sells to paying customers in Texas and lists two Software Engineer openings. '


def cl100k(text):
    return len(ENC.encode(text))


def counted(params):
    """Input tokens of a request in its worst case: what it carries (system, message, tools, output schema) with Claude's
    margin; the course block at its ceiling (operador.COURSE_TOKEN_BUDGET), since the private corpus is not here; and the
    server web tools' own instructions."""
    course=any(b['text'].startswith(COURSE) for b in params['system'])
    visible=sum(cl100k(b['text']) for b in params['system'] if not b['text'].startswith(COURSE))
    visible+=sum(cl100k(m['content']) for m in params['messages'])
    visible+=cl100k(json.dumps({k:params[k] for k in ('tools','output_config') if k in params},ensure_ascii=False))
    return math.ceil((visible+(operador.COURSE_TOKEN_BUDGET if course else 0))*CLAUDE_PER_CL100K)+(SERVER_TOOLS_TOKENS if params.get('tools') else 0)


class Block(SimpleNamespace):
    def model_dump(self,**kwargs):
        return dict(vars(self))


class Stream:
    request_id='req_fake'
    def __init__(self,message):self.message=message
    def __enter__(self):return self
    def __exit__(self,*exc):return False
    def __iter__(self):return iter(())
    def get_final_message(self):return self.message


class WorstCaseClaude:
    """The Anthropic SDK client behind knowledge.providers.claude. Each answer spends its whole reserve: every input token a
    cache write, max_tokens of output and every search the tools allow. The classifier says «comprador» of the ProjectApp
    line for everyone; the web finds the company with a citation, filling its output; the judge confirms it with that source,
    the size and a hiring signal."""
    def __init__(self):
        self.purposes=[];outer=self
        class Messages:
            def count_tokens(self,**params):
                return SimpleNamespace(input_tokens=counted(params))
            def stream(self,max_tokens,**params):
                return Stream(outer.answer(params,max_tokens))
        self.messages=Messages()

    def with_options(self,**kwargs):
        return self

    def answer(self,params,max_tokens):
        tools={t['name']:t for t in params.get('tools',[])}
        tokens=counted(params);schema=(params.get('output_config',{}).get('format') or {}).get('schema',{}).get('properties',{})
        usage=SimpleNamespace(input_tokens=0,output_tokens=max_tokens,cache_creation_input_tokens=tokens+256,cache_read_input_tokens=0)
        if tools:
            web=providers.WebTools('web_search_20250305','web_fetch_20250910',tools.get('web_search',{}).get('max_uses',0),
                                   tools.get('web_fetch',{}).get('max_uses',0),tools.get('web_fetch',{}).get('max_content_tokens',1),
                                   settings.WEB_SEARCH_RESERVED_TOKENS,Decimal(settings.WEB_SEARCH_USD_PER_REQUEST))
            usage.cache_creation_input_tokens=web.reserved_input(tokens)
            usage.server_tool_use=SimpleNamespace(web_search_requests=web.searches,web_fetch_requests=0)
            text=FACT*math.ceil(max_tokens/cl100k(FACT))  # the findings fill the research's output, as the judge's worst case
            cite={'type':'web_search_result_location','url':URL,'title':'Acme careers','cited_text':FACT.strip()}
            content=[Block(type='server_tool_use',id='srv_1',name='web_search',input={'query':'Acme'}),
                     Block(type='web_search_tool_result',tool_use_id='srv_1',
                           content=[{'type':'web_search_result','url':URL,'title':'Acme careers','encrypted_content':'x'}])]
            content+=[Block(type='text',text=text[i:i+5500],citations=[cite]) for i in range(0,len(text),5500)]
            self.purposes.append('web-research-tool')
        elif 'contacts' in schema:
            people=json.loads(params['messages'][0]['content'])['people']
            rows=[{'id':p['id'],'fit':True,'role':'comprador','modality':'projectapp','affinity':'desconocida','confidence':0.9,
                   'reason':'Líder de tecnología de una cadena de 80 personas en Texas que contrata ingenieros.',
                   'course_citations':['LI-03-M005-K06'],'invitation_note':'','note_reason':'','buyer_profile':'lider_tecnologia',
                   'buyer_level':'probable','us_market':True,'buyer_segment':'retail_ecommerce','company_size':'20_a_200'} for p in people]
            content=[Block(type='text',text=json.dumps({'contacts':rows}))]
            self.purposes.append('network-classify')
        else:
            verdict={'verdict':'confirmado','evidence':'La fuente dice que tiene unas 80 personas y dos vacantes de ingeniería.',
                     'source_urls':[URL]}
            if 'tamano' in schema:verdict['tamano']='20_a_200'
            if 'senales' in schema:
                kind=schema['senales']['items']['properties']['tipo']['enum'][0]
                verdict['senales']=[{'tipo':kind,'fecha':'2026-11-10','source_url':URL,'evidencia':'Dos vacantes de Software Engineer.'}]
            content=[Block(type='text',text=json.dumps(verdict))]
            self.purposes.append('network-stage')
        return SimpleNamespace(content=content,stop_reason='end_turn',usage=usage)


@override_settings(WEB_RESEARCH_ENABLED=True)
class StageCheckRunBase(NetworkBase):
    def setUp(self):
        super().setUp()
        env=patch.dict(os.environ,LIVE);env.start();self.addCleanup(env.stop)
        self.claude=WorstCaseClaude()
        client=patch.object(providers,'anthropic_client',return_value=self.claude);client.start();self.addCleanup(client.stop)
        self.cap=Decimal(str(next(c for c in load_graph()['cycles'] if c['id']=='red')['limits']['cost_cap_usd']))

    def people(self,n=10):
        """`n` people to classify as a batch, with the fields the classifier reads at a realistic length."""
        for i in range(n):
            Contact.objects.create(account=self.account,provider_user_id=f'ACo-buyer-{i}',display_name=f'Tomas Retail {i}',
                headline=f'CTO at Acme Outfitters {i} · family retail chain, 80 people · hiring software engineers'[:300],
                location='Dallas, Texas, United States',source='search',stage='candidate',evidence={'query':'CTO retail'},
                signals={'bio':'We run fourteen stores and an online shop, and we are rebuilding the systems behind them. '*3,
                         'followers':900,'connections':500})

    def waiting(self):
        """A buyer already waiting for her web check (the old classify run checked her inside its own run)."""
        buyer=self.contact('ana-waiting','Ana Waiting')
        buyer.location='Austin, Texas';buyer.headline='Founder & CEO at Acme Robotics'
        buyer.classification=dict(buyer.classification,region='us',stage_check={'state':'pending'})
        buyer.save();return buyer

    def one_run(self,kind):
        """One job through the worker: (job, its cycle ledger, its paid calls as [(purpose, reserved, actual)])."""
        job,_=jobs.enqueue_operation(self.bot,kind,{'account':str(self.account.id)})
        self.drain();job.refresh_from_db()
        ledger=CycleLedger.objects.get(job=job)
        with db.connect() as c:
            rows=c.execute("SELECT purpose,reserved_usd,actual_usd FROM usage_ledger WHERE usage->>'cycle_id'=%s ORDER BY created_at",
                           (str(ledger.pk),)).fetchall()
        return job,ledger,[(r['purpose'],r['reserved_usd'],r['actual_usd']) for r in rows]

    def checked(self):
        return Contact.objects.filter(classification__stage_check__state='ok')


class StageCheckRunTests(StageCheckRunBase):
    def test_a_classification_of_ten_never_checks_the_web_nor_stops_for_its_budget(self):
        self.people(10)
        waiting=self.waiting()
        job,ledger,calls=self.one_run('classify_contacts')
        self.assertEqual((job.state,job.result_status,job.error),('complete','encajan:10/10',''))
        self.assertEqual((ledger.state,ledger.stop_reason,ledger.needs_attention),('complete','',False))
        self.assertEqual([purpose for purpose,_,_ in calls],['network-classify'])
        self.assertEqual(self.claude.purposes,['network-classify'])
        self.assertLessEqual(sum(reserved for _,reserved,_ in calls),self.cap)
        self.assertFalse(WebResearchRun.objects.exists())
        waiting.refresh_from_db();self.assertEqual(waiting.classification['stage_check'],{'state':'pending'})
        self.assertEqual(Contact.objects.filter(classification__stage_check__state='pending').count(),11)  # ten new buyers wait

    def test_the_check_runs_alone_with_its_own_budget_and_leaves_one_buyer_checked(self):
        self.people(10)
        self.one_run('classify_contacts')
        job,ledger,calls=self.one_run('check_buyer_stages')
        self.assertEqual((job.state,job.result_status,job.error),('complete','etapas:1/1',''))
        self.assertEqual((ledger.state,ledger.stop_reason,ledger.needs_attention),('complete','',False))
        self.assertEqual([purpose for purpose,_,_ in calls],['web-research-tool','network-stage'])
        self.assertEqual(self.checked().count(),1)
        buyer=self.checked().get();check=buyer.classification['stage_check']
        self.assertEqual((check['verdict'],check['sources'],check['tamano'],check['attempts']),('confirmado',[URL],'20_a_200',1))
        self.assertEqual([(s['tipo'],s['fuente']) for s in check['senales']],[('contrata_desarrolladores',URL)])
        self.assertEqual((buyer.classification['buyer']['level'],buyer.classification['buyer']['basis'],buyer.stage),('confirmado','web','fit'))
        self.assertEqual(Contact.objects.filter(classification__stage_check__state='pending').count(),9)

    def test_one_check_a_run_and_six_a_day(self):
        self.people(10)
        self.one_run('classify_contacts')
        for n in range(1,7):
            job,ledger,_=self.one_run('check_buyer_stages')
            self.assertEqual((job.result_status,ledger.state,self.checked().count()),('etapas:1/1','complete',n))
        self.assertEqual(red.stage_checks_left(),0)
        self.assertFalse(red.stage_pending(self.account))
        autopiloto._network(self.bot,self.account,datetime.now(BOGOTA))  # READ_WINDOW='': any hour reads
        self.assertFalse(Job.objects.filter(kind='check_buyer_stages',state='queued').exists())  # nothing to queue today
        Job.objects.filter(state='queued').delete()
        job,ledger,calls=self.one_run('check_buyer_stages')  # and a run anyway spends nothing
        self.assertEqual((job.result_status,calls,self.checked().count()),('etapas:0/0',[],6))


class CycleWorstCaseTests(StageCheckRunBase):
    """The sum of the reserves a run of the network cycle can make stays within its cost_cap_usd, with the configured
    prices and reserves: if a prompt, a price, max_tokens or a WEB_* setting grows past it, this fails here instead of
    stopping a run in production every day."""
    def test_each_paid_run_of_the_network_cycle_fits_its_cost_cap_in_the_worst_case(self):
        graph=load_graph();edges={e['id']:e for e in graph['edges']}
        paid={kind for kind,edge in graph['code_bindings']['network_edges'].items() if (edges[edge].get('runtime') or {}).get('purposes',{}).get('anthropic')}
        # propose_comment (comentar) is not a network job of the worker: its drafts are not covered here.
        self.assertEqual(paid-{'propose_comment'},{'classify_contacts','check_buyer_stages'})
        self.people(10)
        for kind in ('classify_contacts','check_buyer_stages'):
            job,ledger,calls=self.one_run(kind)
            with self.subTest(kind=kind):
                self.assertEqual((job.state,ledger.state,ledger.stop_reason),('complete','complete',''))
                self.assertTrue(calls)
                self.assertTrue(all(actual==reserved for _,reserved,actual in calls))  # each call spent its whole reserve
                self.assertLessEqual(sum(reserved for _,reserved,_ in calls),self.cap)
        research=next(reserved for purpose,reserved,_ in calls if purpose=='web-research-tool')
        # The estimate is not below what production reserved for one research (0.85–0.89 USD on 18/11/2026).
        self.assertGreaterEqual(research,Decimal('0.85'))


class RealStopTests(StageCheckRunBase):
    def test_a_run_that_really_passes_its_budget_still_stops_and_tells_gustavo(self):
        """The alert stays as it was: a run that passes its cost_cap_usd stops, leaves its card in Tu turno and pushes
        (OPERATOR_ALERT_WEBHOOK: Slack). Here a WEB_SEARCH_RESERVED_TOKENS four times larger makes one research reserve
        more than the run's budget."""
        waiting=self.waiting()
        hook=MagicMock();hook.__enter__.return_value.post.return_value.status_code=200
        with override_settings(WEB_SEARCH_RESERVED_TOKENS=100000),patch.dict(os.environ,{'OPERATOR_ALERT_WEBHOOK':'https://hooks.example/barrio'}), \
             patch('team_backend.alerts.httpx.Client',return_value=hook):
            job,ledger,calls=self.one_run('check_buyer_stages')
        self.assertEqual((job.state,job.result_status,job.error),('failed','blocked','cost_cap'))
        self.assertEqual((ledger.state,ledger.stop_reason,ledger.needs_attention),('stopped','cost_cap',True))
        self.assertEqual(calls,[])  # nothing was reserved, nothing spent
        cards=orquestacion.attention_cards(self.gustavo,lambda key,kind,title,detail,actions,**extra:(key,title,detail))
        self.assertIn((f'cycle:{ledger.pk}','Ciclo detenido: red',orquestacion.REASONS['cost_cap']),cards)
        sent=hook.__enter__.return_value.post.call_args
        self.assertEqual(sent.args[0],'https://hooks.example/barrio')
        self.assertEqual(sent.kwargs['json']['text'],'El ciclo se ha detenido\nSe conserva el progreso. Motivo: cost_cap')
        waiting.refresh_from_db();self.assertEqual(waiting.classification['stage_check'],{'state':'pending'})  # no attempt spent


class StageCheckQueueTests(NetworkBase):
    """autopiloto._network: the check has its own job and clock, only with a check due, room in the day's allowance, the
    team's budget and inside READ_WINDOW, never twice at once; classify_contacts only for people to classify."""
    def setUp(self):
        super().setUp()
        env=patch.dict(os.environ,{'NETWORK_STAGE_CHECK':'true','READ_WINDOW':'07:00-21:00','OPERATOR_TIMEZONE':'America/Bogota'})
        env.start();self.addCleanup(env.stop)
        self.noon=datetime(2026,11,18,12,tzinfo=BOGOTA)
        buyer=self.contact('ana-waiting','Ana Waiting')
        buyer.classification=dict(buyer.classification,stage_check={'state':'pending'});buyer.save()

    def queued(self,now):
        before=set(Job.objects.values_list('id',flat=True))
        autopiloto._network(self.bot,self.account,now)
        return sorted(Job.objects.exclude(id__in=before).exclude(kind__in=['plan_network','discover_network','sync_network'])
                      .values_list('kind',flat=True))

    def test_a_buyer_waiting_for_the_web_queues_the_check_and_not_the_classification(self):
        self.assertEqual(self.queued(self.noon),['check_buyer_stages'])
        self.assertEqual(self.queued(self.noon),[])  # it is pending: not twice
        Job.objects.filter(kind='check_buyer_stages').update(state='complete')
        later=self.noon.replace(minute=25)  # the next 20-minute bucket of NETWORK_STAGE_CHECK_EVERY_MINUTES
        self.assertEqual(self.queued(later),['check_buyer_stages'])
        Contact.objects.create(account=self.account,provider_user_id='ACo-new',display_name='Nuevo',source='search',stage='candidate')
        self.assertEqual(self.queued(later),['classify_contacts'])  # the check is still pending; the classification has its own

    def test_nothing_is_queued_without_the_switch_the_window_the_allowance_or_the_budget(self):
        cases={'switch off':(patch.dict(os.environ,{'NETWORK_STAGE_CHECK':'false'}),self.noon),
               'outside READ_WINDOW':(patch.dict(os.environ,{}),self.noon.replace(hour=3)),
               'allowance spent':(patch.dict(os.environ,{'NETWORK_STAGE_CHECKS_PER_DAY':'0'}),self.noon),
               'team budget spent':(patch.object(red,'budget_left',return_value=Decimal(0)),self.noon)}
        for name,(condition,now) in cases.items():
            with self.subTest(name),condition:self.assertEqual(self.queued(now),[])
        self.assertEqual(self.queued(self.noon),['check_buyer_stages'])
