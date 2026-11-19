"""Web research that never stays `running` and never loses what the web returned (19/11/2026).

Production on 19/11/2026: 27 runs in team_backend_webresearchrun. 6 of them `running` forever (keys etapa:…, result {}):
the cycle stopped inside the research (cost_cap from orquestacion.provider_metadata) and research.research only caught
ValueError and friends, so its row was never closed and its key answered «en curso» for the rest of the day. 18 more
`unavailable` with «La web no devolvió hallazgos con citas verificables»: the web had answered, the prose came back without
native citations and everything was dropped. No real web, no paid API: providers.claude or the SDK client are doubles and
the clock is frozen."""
import hashlib
import json
import os
import uuid
from contextlib import ExitStack
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.test import override_settings
from django.utils import timezone
from knowledge import db
from knowledge.cycle_context import CycleStopped
from psycopg.types.json import Jsonb
from team_backend import jobs, research
from team_backend.models import WebResearchRun
from team_backend.tests.test_operador import OperatorBase
from team_backend.tests.test_verificacion_etapa import clock
from team_backend.tests.test_web_research import LIVE, QUESTION, URL, native_answer

BOGOTA=ZoneInfo('America/Bogota')
NOON=datetime(2026,11,19,12,0,tzinfo=BOGOTA)


def ledger(key,status='complete'):
    """The usage_ledger row providers.claude leaves for the research of `key` once its call was reserved."""
    with db.connect() as c:
        c.execute('INSERT INTO usage_ledger(id,provider,purpose,reserved_usd,actual_usd,status,request_hash,usage) '
                  'VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',
                  (str(uuid.uuid4()),'anthropic','web-research-tool',Decimal('0.85'),Decimal('0.05') if status=='complete' else None,
                   status,hashlib.sha256(key.encode()).hexdigest(),Jsonb({})))


@override_settings(WEB_RESEARCH_ENABLED=True,WEB_RESEARCH_DAILY_LIMIT=6)
class ResearchBase(OperatorBase):
    def setUp(self):
        super().setUp()
        stack=ExitStack();clock(stack,NOON);self.addCleanup(stack.close)
        env=patch.dict(os.environ,LIVE);env.start();self.addCleanup(env.stop)

    def call(self,key='tool:uno',**kwargs):
        return research.research(research.ResearchRequest(key,QUESTION,search=True,**kwargs))

    def row(self,key='tool:uno'):
        return WebResearchRun.objects.get(pk=key)


class InterruptedRunTests(ResearchBase):
    def test_an_unexpected_exception_closes_the_run_and_a_run_that_paid_nothing_runs_again(self):
        with patch('knowledge.providers.claude',side_effect=RuntimeError('boom')),self.assertRaises(RuntimeError):self.call()
        row=self.row()
        self.assertEqual(row.state,'interrupted')
        self.assertEqual(row.result['limitations'],['Interrumpida: error inesperado (RuntimeError); no llegó a pagar ninguna llamada y puede repetirse'])
        self.assertEqual(row.result['diagnostic'],{'motivo':'interrumpida','causa':'error inesperado (RuntimeError)','reintentable':True})
        self.assertNotIn('boom',json.dumps(row.result))  # the exception's text never reaches the row
        with patch('knowledge.providers.claude',return_value=native_answer()) as model:result=self.call()
        self.assertEqual((result.status,model.call_count,self.row().state),('complete',1,'complete'))

    def test_a_stopped_cycle_closes_the_run_and_the_stop_still_reaches_the_cycle(self):
        with patch('knowledge.providers.claude',side_effect=CycleStopped('cost_cap')),self.assertRaisesMessage(CycleStopped,'cost_cap'):
            self.call()
        self.assertEqual(self.row().state,'interrupted')
        self.assertEqual(self.row().result['limitations'][0],
                         'Interrumpida: el ciclo se detuvo (cost_cap); no llegó a pagar ninguna llamada y puede repetirse')

    def test_a_run_interrupted_after_its_call_was_reserved_keeps_the_money_and_is_not_paid_again(self):
        def reserved_then_stopped(*args,**kwargs):
            ledger('tool:uno','uncertain');raise CycleStopped('call_timeout')
        with patch('knowledge.providers.claude',side_effect=reserved_then_stopped),self.assertRaises(CycleStopped):self.call()
        self.assertEqual(self.row().result['limitations'],['Interrumpida: el ciclo se detuvo (call_timeout)'])
        self.assertIs(self.row().result['diagnostic']['reintentable'],False)
        with patch('knowledge.providers.claude') as model:again=self.call()
        model.assert_not_called();self.assertEqual(again.status,'interrupted')

    def test_an_interrupted_run_that_paid_nothing_takes_no_daily_allowance(self):
        with override_settings(WEB_RESEARCH_DAILY_LIMIT=1):
            with patch('knowledge.providers.claude',side_effect=CycleStopped('cost_cap')),self.assertRaises(CycleStopped):self.call()
            with patch('knowledge.providers.claude',return_value=native_answer()) as model:other=self.call('tool:dos')
            self.assertEqual((other.status,model.call_count),('complete',1))
            with patch('knowledge.providers.claude') as model:third=self.call('tool:tres')
        self.assertEqual(third.status,'skipped');model.assert_not_called()  # the completed one took the only slot

    def test_a_refused_budget_spent_nothing_and_may_run_again(self):
        with patch('knowledge.providers.claude',side_effect=ValueError('Presupuesto web diario agotado')):result=self.call()
        self.assertEqual((result.status,result.diagnostic),('unavailable',{'motivo':'presupuesto','reintentable':True}))
        with patch('knowledge.providers.claude',return_value=native_answer()) as model:again=self.call()
        self.assertEqual((again.status,model.call_count),('complete',1))


class StaleRunTests(ResearchBase):
    def running(self,key,minutes):
        WebResearchRun.objects.create(key=key,request_hash=research._digest(research.ResearchRequest(key,QUESTION,search=True)),
                                      created_at=timezone.now()-timedelta(minutes=minutes))

    def test_the_worker_reconciliation_closes_runs_left_running_by_a_dead_process(self):
        self.running('etapa:1:1:20261119',20);self.running('etapa:2:1:20261119',20);self.running('tool:fresca',5)
        ledger('etapa:2:1:20261119','reserved')  # its call was reserved before the process died
        jobs.reconcile_interrupted()
        free,paid,fresh=(self.row(k) for k in ('etapa:1:1:20261119','etapa:2:1:20261119','tool:fresca'))
        self.assertEqual((free.state,paid.state,fresh.state),('interrupted','interrupted','running'))
        self.assertEqual(free.result['limitations'],['Interrumpida: el proceso terminó sin cerrarla; no llegó a pagar ninguna llamada y puede repetirse'])
        self.assertEqual(paid.result['limitations'],['Interrumpida: el proceso terminó sin cerrarla'])
        from team_backend import red
        self.assertEqual(red.stage_checks_left(NOON),5)  # only the one that may have paid takes the allowance

    def test_a_stale_run_found_by_its_own_key_is_closed_and_run_again(self):
        self.running('tool:uno',30)
        with patch('knowledge.providers.claude',return_value=native_answer()) as model:result=self.call()
        self.assertEqual((result.status,model.call_count),('complete',1))
        self.running('tool:viva',2)  # a run still inside its call keeps its key: nothing is paid twice
        with patch('knowledge.providers.claude') as model:self.assertEqual(self.call('tool:viva').status,'running')
        model.assert_not_called()


SECOND='https://techcrunch.com/2026/11/12/agents-context/'


def answer(*blocks,stop='end_turn'):
    """A research answer as providers.claude returns it, with its server blocks."""
    return {'text':'','model':'fake','stop_reason':stop,'estimated_usd':.03,'ledger_id':'fake',
            'usage':{'web_search_requests':1,'input_tokens':900,'output_tokens':200},'content':list(blocks)}


def search(*results,error=None):
    return [{'type':'server_tool_use','id':'srv_1','name':'web_search','input':{'query':QUESTION}},
            {'type':'web_search_tool_result','tool_use_id':'srv_1',
             'content':{'type':'web_search_tool_result_error','error_code':error} if error else
             [{'type':'web_search_result','url':url,'title':title,'encrypted_content':'SECRETO-CIFRADO','page_age':age}
              for url,title,age in results]}]


def text(value,**cited):
    return {'type':'text','text':value,**({'citations':[cited]} if cited else {})}


class FindingsAreNotLostTests(ResearchBase):
    def run_with(self,reply,key='tool:uno',**kwargs):
        with patch('knowledge.providers.claude',return_value=reply):return self.call(key,**kwargs)

    def test_search_results_without_native_citations_become_approximate_findings(self):
        reply=answer(text('Voy a buscar datos recientes.'),
                     *search((URL,'Release notes','November 12, 2026'),(SECOND,'Agents lose context','November 12, 2026')),
                     text('Según TechCrunch, el 40 % de los equipos que encadenan agentes pierde contexto entre pasos '
                          '([fuente](https://inventada.example.com/x)); la versión de Python añade una función pública.'))
        result=self.run_with(reply)
        self.assertEqual(result.status,'partial')
        self.assertEqual([(f.citation,len(f.source_ids)) for f in result.findings],[('aproximada',2)])
        finding=result.findings[0].text
        self.assertTrue(finding.startswith('Según TechCrunch, el 40 %'));self.assertNotIn('inventada',finding)
        self.assertNotIn('Voy a buscar',finding)  # the chatter before the search is not the summary
        self.assertEqual([(s.url,s.title,s.kind,s.site,s.published) for s in result.sources],
                         [(URL,'Release notes','search_result','news.example.com','November 12, 2026'),
                          (SECOND,'Agents lose context','search_result','techcrunch.com','November 12, 2026')])
        self.assertIn(research.APPROXIMATE_NOTE,result.limitations)
        diagnostic=self.row().result['diagnostic']
        self.assertEqual({k:diagnostic[k] for k in ('busquedas','resultados_busqueda','hallazgos_nativos','hallazgos_aproximados',
                                                    'textos_sin_cita','textos_citados')},
                         {'busquedas':1,'resultados_busqueda':2,'hallazgos_nativos':0,'hallazgos_aproximados':1,
                          'textos_sin_cita':2,'textos_citados':0})
        self.assertNotIn('SECRETO',json.dumps(diagnostic));self.assertNotIn('40 %',json.dumps(diagnostic))  # counts only

    def test_without_a_summary_each_search_result_is_its_own_approximate_finding(self):
        result=self.run_with(answer(*search((URL,'Release notes','2 days ago'),(SECOND,'Agents lose context',''))))
        self.assertEqual([f.text for f in result.findings],
                         ['Release notes (news.example.com, 2 days ago)','Agents lose context (techcrunch.com)'])
        self.assertTrue(all(f.citation=='aproximada' for f in result.findings))

    def test_native_citations_still_win_and_carry_their_date(self):
        reply=answer(*search((URL,'Release notes','November 12, 2026')),
                     text('La versión añade una función pública.',type='web_search_result_location',url=URL,
                          title='Release notes',cited_text='A new public feature is available.'))
        result=self.run_with(reply)
        self.assertEqual((result.status,[f.citation for f in result.findings]),('complete',['nativa']))
        source=result.sources[0]
        self.assertEqual((source.kind,source.quoted_text,source.published),('web','A new public feature is available.','November 12, 2026'))
        self.assertEqual(self.row().result['diagnostic']['citas'],{'web_search_result_location':1})

    def test_urls_written_in_the_prose_are_never_evidence(self):
        result=self.run_with(answer(text('Un informe dice que el 90 % lo usa: https://inventada.example.com/informe')))
        self.assertEqual((result.status,result.findings,result.sources),('unavailable',(),()))

    def test_every_unavailable_run_says_which_case_it_was(self):
        cases={'sin_resultados':(answer(*search()),'La búsqueda no devolvió resultados'),
               'busqueda_fallida':(answer(*search(error='too_many_requests')),'La búsqueda falló (too_many_requests)'),
               'sin_busqueda':(answer(text('No necesito buscar.')),'El modelo terminó sin buscar ni leer ninguna página')}
        for n,(code,(reply,why)) in enumerate(cases.items()):
            with self.subTest(code):
                result=self.run_with(reply,f'tool:caso{n}')
                self.assertEqual(result.status,'unavailable');self.assertIn(why,result.limitations)
                self.assertEqual(result.diagnostic['motivo'],code)
        fetch=answer({'type':'server_tool_use','id':'srv_2','name':'web_fetch','input':{'url':URL}},
                     {'type':'web_fetch_tool_result','tool_use_id':'srv_2',
                      'content':{'type':'web_fetch_tool_result_error','error_code':'url_not_accessible'}})
        with patch.object(research.web_sources,'public_addresses',return_value=['93.184.216.34']), \
             patch('knowledge.providers.claude',return_value=fetch):
            read=research.research(research.ResearchRequest('tool:lectura',urls=(URL,)))
        self.assertIn('No se pudo leer ninguna de las páginas indicadas',read.limitations)
        self.assertEqual((read.diagnostic['motivo'],read.diagnostic['errores_lectura']),('lectura_fallida',['url_not_accessible']))
        with patch('knowledge.providers.claude',side_effect=ValueError('anthropic: HTTP 529. Sin reintento automático.')):
            failed=self.call('tool:proveedor')
        self.assertEqual(failed.diagnostic['motivo'],'error_proveedor')
