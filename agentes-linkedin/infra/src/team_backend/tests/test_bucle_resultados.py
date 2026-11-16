"""Bucle de resultados (bucle_resultados.py, manage.py bucle_resultados): what arrives, what the agents froze as input and
what returns to its cycle, per flow, and one piece or action traced link by link. A small invented world at a fixed
clock; the diagnosis only reads: no row changes, no connector, no paid provider."""
import json
import os
import uuid
from contextlib import ExitStack
from datetime import date, datetime, timedelta, timezone as dt_timezone
from io import StringIO
from unittest.mock import patch
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase
from team_backend import bucle_resultados, desenlaces, metricas, operador, orquestacion
from team_backend.models import (ActionExecution, ActionOutcome, ActionProposal, AnalyticsPost, AudienceSnapshot, AuditEvent, CanaryRun,
                                 Contact, CycleLedger, EditorialPiece, Job, ObservedPost, PostMetric, WebResearchRun, WeeklyPlan,
                                 WeeklySummary)
from team_backend.tests.test_operador import OperatorBase

NOW=datetime(2026,11,16,15,tzinfo=dt_timezone.utc)  # Monday, 10:00 in Bogota: the week of 9 November just ended
DAY=timedelta(days=1)
MONDAY=date(2026,11,16)


class LoopBase(OperatorBase):
    def setUp(self):
        super().setUp()
        env=patch.dict(os.environ,{'OPERATOR_TIMEZONE':'America/Bogota','STRATEGY_ENABLED':'true','WEEKLY_SUMMARY_TIME':'07:30'})
        env.start();self.addCleanup(env.stop)
        self.n=0

    def day_of(self,moment):
        return moment.astimezone(operador.local_tz()).date()

    def published(self,age,cuts=()):
        """A CONT-09 publication `age` before NOW with the given cuts, each captured an hour after its age."""
        when=NOW-age;self.n+=1;text=f'Post inventado número {self.n}: qué decisión ayuda a tomar esta función.'
        piece=EditorialPiece.objects.create(account=self.account,slot_date=self.day_of(when),scheduled_for=when,state='ready',final_text=text,
                                            brief={'pillar':'applied_ai','gasp_type':'A'},created_at=when-timedelta(hours=12))
        proposal=ActionProposal.objects.create(account=self.account,piece=piece,capability='CONT-09',payload={'text':text},payload_hash='0'*64,
                                               state='confirmed')
        ActionExecution.objects.create(proposal=proposal,idempotency_key=uuid.uuid4().hex,provider='linkedin_fake',state='confirmed',
                                       executed_by=self.gustavo,started_at=when)
        for kind in cuts:
            PostMetric.objects.create(piece=piece,kind=kind,impressions=120,reactions=4,comments=1,reposts=0,published_at=when,
                                      captured_at=when+metricas.AGES[kind]+timedelta(hours=1))
        return piece

    def post(self,author):
        self.n+=1
        return ObservedPost.objects.create(account=self.account,provider_post_id=f'urn:li:activity:{900+self.n}',author_provider_id=author,
                                           author_name='Autora Inventada')

    def executed(self,capability,age,post=None):
        """An executed action started `age` before NOW: INT-03 on `post` (or a new one), RED-* on a new person."""
        if capability.startswith('INT'):target,payload={'post':post or self.post('ACoAutora-z')},{'text':'Comentario inventado.'}
        else:
            self.n+=1
            contact=Contact.objects.create(account=self.account,provider_user_id=f'ACoperson-{self.n}',display_name=f'Persona {self.n}',
                                           source='commenter',stage='followed')
            target,payload={'contact':contact},{'user_id':contact.provider_user_id}
        proposal=ActionProposal.objects.create(account=self.account,capability=capability,payload=payload,payload_hash='0'*64,state='confirmed',**target)
        return ActionExecution.objects.create(proposal=proposal,provider='fake',executed_by=self.gustavo,state='confirmed',
                                              idempotency_key=uuid.uuid4().hex,started_at=NOW-age)

    def outcome(self,execution,kind,**fields):
        return ActionOutcome.objects.create(execution=execution,kind=kind,source='read' if kind=='72h' else 'derived',
                                            captured_at=execution.started_at+desenlaces.WINDOWS[kind][0],**fields)

    def cycle(self,name,age,snapshots,trigger=None,post=None):
        """A cycle opened `age` before NOW whose ledger froze `snapshots`, packed as orquestacion.Runtime.snapshot does."""
        job=None
        if trigger:
            job=Job.objects.create(owner=self.gustavo,request_hash='x',agent='operador',task=trigger,kind=trigger,state='complete',
                                   params={'post':str(post.id)} if post else {},created_at=NOW-age)
        return CycleLedger.objects.create(cycle=name,key=str(job.id) if job else uuid.uuid4().hex,owner=self.gustavo,job=job,orchestrator='o',
                                          graph_version='1',graph_hash='h',budget_bucket='b',task_ledger={'facts':{'trigger':trigger} if trigger else {}},
                                          progress_ledger={'calls':{},'snapshots':{k:orquestacion.pack(v) for k,v in snapshots.items()}},
                                          state='complete',created_at=NOW-age)

    def world(self):
        w={}
        # Own posts: one with every cut and its LinkedIn analytics; one published two days ago still without its 24 h cut.
        w['full']=self.published(8*DAY,cuts=('24h','72h','7d'))
        w['missing']=self.published(2*DAY)
        AuditEvent.objects.create(action='metrics.collected',target=str(self.account.id),created_at=NOW-timedelta(hours=1),
                                  metadata={'pending':[{'piece':str(w['missing'].id),'cuts':['24h'],'reason':'sin_coincidencia'}]})
        AnalyticsPost.objects.create(account=self.account,post_urn='urn:li:activity:7390000000000000001',piece=w['full'],impressions=900)
        # Own comments: one measured at 72 h, one past its 72 h without outcome, one too recent.
        w['comment']=self.executed('INT-03',5*DAY,post=self.post('ACoAutora-a'))
        self.outcome(w['comment'],'72h',replies=1,author_replied=True)
        w['unmeasured']=self.executed('INT-03',4*DAY)
        self.executed('INT-03',DAY)
        # Network: a follow whose person later commented on an own post, and an invitation without its 7 d outcome.
        w['follow']=self.executed('RED-01',10*DAY)
        self.outcome(w['follow'],'7d',signals={'accepted':False,'commented_own_post':True})
        w['invite']=self.executed('RED-02',9*DAY)
        # Web research: one with findings, one without; a running and a skipped one do not count.
        WebResearchRun.objects.create(key=f'piece:{w["full"].id}',request_hash='h',state='complete',created_at=NOW-9*DAY,
                                      result={'findings':[{'text':'Hallazgo inventado.','source_ids':['s1']}]})
        w['empty_key']=f'etapa:{uuid.UUID(int=7)}:1:20261115'
        WebResearchRun.objects.create(key=w['empty_key'],request_hash='h',state='unavailable',created_at=NOW-DAY,result={'findings':[]})
        WebResearchRun.objects.create(key='piece:en-curso',request_hash='h',state='running',created_at=NOW-DAY)
        WebResearchRun.objects.create(key='piece:saltada',request_hash='h',state='skipped',created_at=NOW-DAY)
        # Summaries: the week of 2 November has one (its network section had no data); the week of 9 November has none.
        w['summary']=WeeklySummary.objects.create(week_start=date(2026,11,2),created_at=datetime(2026,11,9,13,tzinfo=dt_timezone.utc),
            stats={'semana':{'desde':'2026-11-02','publicaciones':{'disponible':True,'publicados':1,'cortes':{'72h':{'medidos':1}},
                                                                  'posts':[{'fecha':w['full'].slot_date.isoformat()}]},
                             'comentarios':{'disponible':True},'red':{'disponible':False,'motivo':'La red no funcionó esta semana.'}}},
            analysis={'recomendaciones':[{'texto':'Repetir el tipo A: 1 post medido.','cifra':'1'}],
                      'validacion':{'ok':False,'descartado':[{'campo':'lo_que_no'},{'campo':'recomendaciones'}]}})
        # The director: one cycle froze its context (an earlier piece with its 72 h metrics and the recommendations); a
        # later one stopped before freezing anything.
        history=[{'date':w['full'].slot_date,'status':'published','opening':w['full'].final_text[:280],
                  'results':{'72h':{'impressions':120,'reactions':4},'7d':'pendiente'}},
                 {'date':w['missing'].slot_date,'status':'published','opening':w['missing'].final_text[:280],
                  'results':{'72h':'pendiente','7d':'pendiente'}}]
        w['director']=self.cycle('pieza_diaria',DAY,{'editorial_context':{'director_input':{'history':history,
            'weekly_recommendations':{'semana':{'desde':'2026-11-02'},'recomendaciones':['Repetir el tipo A: 1 post medido.']}},'research':[]}})
        w['stopped']=self.cycle('pieza_diaria',timedelta(hours=12),{})
        # The comment drafter: two drafts carry referent_signals (the second without a referent) and never comment_outcomes;
        # the second is on the author of the measured comment. A classification cycle is not a comment draft.
        w['draft']=self.cycle('red',3*DAY,{'referent_signals':{'referent':{'id':str(uuid.UUID(int=1)),'reason':'Inventado'},'limitations':['x']}},
                              trigger='propose_comment',post=self.post('ACoAutora-b'))
        w['later_draft']=self.cycle('red',DAY,{'referent_signals':{'limitations':['Sin referente asociado.']}},trigger='propose_comment',
                                    post=self.post('ACoAutora-a'))
        self.cycle('red',2*DAY,{'evidence_request':{'account':'x'}},trigger='classify_contacts')
        # This week's plan, made on Sunday, and today's piece prepared after it with the day's type.
        w['plan']=WeeklyPlan.objects.create(week_start=MONDAY,state='planeada',created_at=NOW-DAY,
                                            slots=[{'date':(MONDAY+timedelta(days=i)).isoformat(),'type':t} for i,t in enumerate('GAGASPG')])
        w['today']=EditorialPiece.objects.create(account=self.account,slot_date=MONDAY,scheduled_for=NOW+timedelta(hours=2),state='ready',
                                                 final_text='Pieza de hoy.',brief={'gasp_type':'G'},created_at=NOW-timedelta(hours=3))
        # The account: a fresh canary, profile views missing in today's capture, two contacts classified in the window.
        w['canary']=CanaryRun.objects.create(account=self.account,state='ok',started_at=NOW-timedelta(hours=5),finished_at=NOW-timedelta(hours=5))
        AudienceSnapshot.objects.create(day=date(2026,11,15),followers=1000,profile_views=30,profile_views_days=28)
        AudienceSnapshot.objects.create(day=MONDAY,followers=1001)
        def classified(uid,age,signals):
            return Contact.objects.create(account=self.account,provider_user_id=uid,display_name='Persona Inventada',source='search',
                                          classification={'fit':True,'role':'comprador','classified_at':(NOW-age).isoformat()},signals=signals)
        classified('ACorich',2*DAY,{'bio':'Construye agentes de IA.','followers':1200})
        w['bare']=classified('ACobare',3*DAY,{})
        classified('ACoold',40*DAY,{})  # classified before the window
        return w


class ReportTests(LoopBase):
    def test_what_arrives_what_the_agents_use_and_what_returns(self):
        w=self.world();r=bucle_resultados.report(14,NOW)
        self.assertEqual((r['desde'],r['hasta'],r['dias']),('2026-11-02','2026-11-16',14))
        self.assertEqual(list(r),['desde','hasta','dias','generado','llega','usan','vuelve','veredictos'])
        came=r['llega']
        posts=came['posts']  # the post with every cut is complete; the other one is listed with the reason of the collector
        self.assertEqual((posts['estado'],posts['publicados'],posts['n_faltan']),('parcial',2,1))
        self.assertEqual(posts['cortes'],{'24h':{'debidos':2,'con_corte':1},'72h':{'debidos':1,'con_corte':1},'7d':{'debidos':1,'con_corte':1}})
        self.assertEqual(posts['faltan'],[{'pieza':str(w['missing'].id),'cortes':['24h'],'motivo':'sin_coincidencia'}])
        analytics=came['analitica']
        self.assertEqual((analytics['estado'],analytics['con_analitica'],analytics['solo_rango'],analytics['sin_analitica'],analytics['total']),
                         ('parcial',1,0,[str(w['missing'].id)],{'publicados':2,'con_analitica':1,'sin_analitica':1}))
        comments=came['comentarios']
        self.assertEqual((comments['estado'],comments['medibles'],comments['con_desenlace'],comments['aun_no_toca']),('parcial',2,1,1))
        self.assertEqual(comments['sin_desenlace'],[{'ejecucion':str(w['unmeasured'].id),'propuesta':str(w['unmeasured'].proposal_id),'motivo':'en_plazo'}])
        self.assertEqual(comments['tasas'],{'measured':1,'with_reply':1,'author_replied':1})
        network=came['red']
        self.assertEqual((network['estado'],network['medibles'],network['con_desenlace'],network['interactuaron']),('parcial',2,1,1))
        self.assertEqual([m['ejecucion'] for m in network['sin_desenlace']],[str(w['invite'].id)])
        research=came['investigacion']
        self.assertEqual((research['estado'],research['corridas'],research['con_hallazgos']),('parcial',2,1))
        self.assertEqual(research['por_tipo'],{'piece':{'corridas':1,'con_hallazgos':1},'etapa':{'corridas':1,'con_hallazgos':0}})
        self.assertEqual(research['sin_hallazgos'],[{'clave':w['empty_key'],'estado':'unavailable'}])
        weekly=came['resumen_semanal']  # the week of 9 November ended and its summary was due this morning
        self.assertEqual(weekly['semanas'],[{'semana':'2026-11-02','estado':'ok','resumen':str(w['summary'].id),'estado_resumen':'nuevo',
                                             'recomendaciones':1,'descartadas':2},{'semana':'2026-11-09','estado':'falta'}])
        self.assertEqual((weekly['estado'],weekly['faltan']),('parcial',['2026-11-09']))
        self.assertEqual(came['canario'],{'estado':'ok','ultimo':{'id':w['canary'].pk,'estado':'ok','edad_horas':5.0,'error':None}})
        views=came['visitas_perfil']
        self.assertEqual((views['estado'],views['ultima'],views['con_visitas'],views['sin_visitas']),
                         ('parcial',{'dia':'2026-11-16','visitas_nulas':True,'ventana_dias':None},1,['2026-11-16']))
        people=came['contactos']
        self.assertEqual((people['estado'],people['clasificados'],people['con_bio'],people['con_seguidores'],people['pct_bio'],people['sin_senales']),
                         ('parcial',2,1,1,50.0,[str(w['bare'].id)]))

        used=r['usan']
        director=used['editorial_context']  # the frozen context carries the metrics of an earlier piece, not only sin_dato
        self.assertEqual({k:director[k] for k in ('estado','ciclos','con_snapshot','con_dato','esperaban_metricas','solo_sin_dato','con_recomendaciones','sin_snapshot')},
                         {'estado':'ok','ciclos':2,'con_snapshot':1,'con_dato':1,'esperaban_metricas':1,'solo_sin_dato':[],'con_recomendaciones':1,
                          'sin_snapshot':[str(w['stopped'].id)]})
        signals=used['referent_signals']
        self.assertEqual((signals['estado'],signals['ciclo'],signals['ciclos'],signals['con_dato'],signals['vacios']),
                         ('parcial','red:propose_comment',2,1,[str(w['later_draft'].id)]))
        # Never frozen by any comment cycle: «no se registra», not a zero.
        self.assertEqual((used['comment_outcomes']['estado'],used['comment_outcomes']['ciclos'],used['comment_outcomes']['con_dato']),('no_se_registra',2,None))
        self.assertEqual((used['network_engaged']['estado'],used['network_engaged']['ciclos']),('sin_datos',0))
        self.assertEqual(used['resumen_stats']['por_resumen'],[{'semana':'2026-11-02','resumen':str(w['summary'].id),'con_dato':['comentarios','publicaciones'],
                                                               'sin_dato':['red'],'publicados':1,'medidos_72h':1,'completo':False}])

        back=r['vuelve']
        recommendations=back['recomendaciones']
        self.assertEqual({k:recommendations[k] for k in ('estado','para_el_director','resumen','ciclos_despues','ciclos_con_recomendaciones')},
                         {'estado':'ok','para_el_director':{'semana':'2026-11-02','recomendaciones':1},'resumen':str(w['summary'].id),
                          'ciclos_despues':1,'ciclos_con_recomendaciones':1})
        plan=back['plan_semanal']
        self.assertEqual({k:plan[k] for k in ('estado','semana','plan','estado_plan','dias','dias_con_tipo','piezas','fallan','semana_siguiente')},
                         {'estado':'ok','semana':'2026-11-16','plan':str(w['plan'].id),'estado_plan':'planeada','dias':7,'dias_con_tipo':7,
                          'piezas':[{'fecha':'2026-11-16','pieza':str(w['today'].id),'despues_del_plan':True,'tipo':'coincide'}],'fallan':[],
                          'semana_siguiente':None})

        self.assertEqual({flow:v['veredicto'] for flow,v in r['veredictos'].items()},
                         {'posts':'parcial','comentarios':'parcial','red':'parcial','investigacion':'parcial','resumen_semanal':'parcial','cuenta':'parcial'})
        self.assertEqual(r['veredictos']['comentarios']['pendiente'],
                         ['llega.comentarios: parcial','usan.referent_signals: parcial','usan.comment_outcomes: no_se_registra'])

    def test_recommendations_that_never_reach_the_director_and_a_week_without_plan(self):
        r=bucle_resultados.report(14,NOW)
        self.assertEqual((r['usan']['editorial_context']['estado'],r['vuelve']['recomendaciones']['estado']),('sin_datos','sin_datos'))
        self.assertEqual((r['vuelve']['plan_semanal']['estado'],r['vuelve']['plan_semanal']['motivo']),('roto','Esta semana no tiene plan.'))
        # The validator dropped every recommendation: the director gets nothing, and the report says why.
        WeeklySummary.objects.create(week_start=date(2026,11,9),created_at=NOW-timedelta(hours=2),stats={},
                                     analysis={'recomendaciones':[],'validacion':{'ok':False,'descartado':[{'campo':'recomendaciones'}]*3}})
        check=bucle_resultados.report(14,NOW)['vuelve']['recomendaciones']
        self.assertEqual((check['estado'],check['para_el_director'],check['motivo'],check['descartadas_por_el_validador']),
                         ('roto',None,'sin_recomendaciones',3))
        WeeklySummary.objects.update(state=WeeklySummary.State.DISCARDED)  # a discarded summary is not passed on either
        self.assertEqual(bucle_resultados.report(14,NOW)['vuelve']['recomendaciones']['motivo'],'descartado')


class TraceTests(LoopBase):
    def links(self,trace):
        return [(l['eslabon'],l['estado']) for l in trace['eslabones']]

    def test_a_piece_from_its_publication_to_the_summary_of_its_week(self):
        w=self.world()
        trace=bucle_resultados.trace_piece(w['full'].id,NOW)
        self.assertEqual(self.links(trace),[('pieza','ok'),('ejecucion','ok'),('corte_24h','ok'),('corte_72h','ok'),('corte_7d','ok'),
                                            ('analitica','ok'),('director','ok'),('resumen','ok')])
        by_name={l['eslabon']:l for l in trace['eslabones']}
        self.assertEqual((by_name['analitica']['fuente'],by_name['director']['ciclo'],by_name['director']['cortes'],by_name['resumen']['semana']),
                         ('vida',str(w['director'].id),['72h'],'2026-11-02'))
        trace=bucle_resultados.trace_piece(str(w['missing'].id),NOW)
        self.assertEqual(self.links(trace),[('pieza','ok'),('ejecucion','ok'),('corte_24h','falta'),('corte_72h','aun_no_toca'),('corte_7d','aun_no_toca'),
                                            ('analitica','falta'),('director','aun_no_toca'),('resumen','falta')])
        self.assertEqual((trace['eslabones'][2]['motivo'],trace['eslabones'][-1]['semana']),('sin_coincidencia','2026-11-09'))
        # Not published yet: its hour has not come.
        self.assertEqual(self.links(bucle_resultados.trace_piece(w['today'].id,NOW)),[('pieza','ok')]+[(n,'aun_no_toca') for n in
                         ('ejecucion','corte_24h','corte_72h','corte_7d','analitica','director','resumen')])
        self.assertEqual(self.links(bucle_resultados.trace_piece('no-es-un-uuid',NOW)),[('pieza','falta')])

    def test_an_action_from_its_execution_to_its_later_use(self):
        w=self.world()
        trace=bucle_resultados.trace_action(w['comment'].proposal_id,NOW)
        self.assertEqual(self.links(trace),[('propuesta','ok'),('ejecucion','ok'),('desenlace','ok'),('uso','falta'),('resumen','falta')])
        use=trace['eslabones'][3]  # a later draft on the same author exists, but no cycle ever froze comment_outcomes
        self.assertEqual((use['motivo'],use['ciclos']),('comment_outcomes no se registra en ningún ciclo.',[str(w['later_draft'].id)]))
        trace=bucle_resultados.trace_action(w['unmeasured'].proposal_id,NOW)
        self.assertEqual(self.links(trace),[('propuesta','ok'),('ejecucion','ok'),('desenlace','falta'),('uso','aun_no_toca'),('resumen','falta')])
        self.assertEqual(trace['eslabones'][2]['motivo'],'En plazo y aún sin desenlace: collect_outcomes no lo midió.')
        trace=bucle_resultados.trace_action(w['follow'].proposal_id,NOW)
        self.assertEqual(self.links(trace),[('propuesta','ok'),('ejecucion','ok'),('desenlace','ok'),('uso','aun_no_toca'),('resumen','falta')])
        self.assertEqual((trace['eslabones'][3]['motivo'],trace['eslabones'][4]['motivo']),
                         ('Aún no hubo un plan de red después del desenlace.','El resumen de su semana no tiene datos de red.'))
        self.assertEqual(self.links(bucle_resultados.trace_action(w['invite'].proposal_id,NOW))[2:4],[('desenlace','falta'),('uso','no_aplica')])
        self.assertEqual(self.links(bucle_resultados.trace_action(uuid.uuid4(),NOW)),[('propuesta','falta')])

    def test_a_later_draft_that_froze_the_outcome_closes_the_loop(self):
        w=self.world()
        closing=self.cycle('red',timedelta(hours=6),{'comment_outcomes':desenlaces.comment_history('ACoAutora-a',now=NOW)},
                           trigger='propose_comment',post=self.post('ACoAutora-a'))
        link=bucle_resultados.trace_action(w['comment'].proposal_id,NOW)['eslabones'][3]
        self.assertEqual((link['eslabon'],link['estado'],link['ciclo'],link['snapshot']),('uso','ok',str(closing.id),'comment_outcomes'))
        used=bucle_resultados.report(14,NOW)['usan']['comment_outcomes']
        self.assertEqual((used['estado'],used['ciclos'],used['con_snapshot'],used['con_dato']),('ok',3,1,1))
        self.assertEqual(used['sin_snapshot'],[str(w['draft'].id),str(w['later_draft'].id)])


class ReadOnlyTests(LoopBase):
    def test_it_never_writes_nor_calls_linkedin_or_a_paid_provider(self):
        w=self.world()
        tables=(ActionExecution,ActionOutcome,ActionProposal,AnalyticsPost,AudienceSnapshot,AuditEvent,CanaryRun,Contact,CycleLedger,
                EditorialPiece,Job,ObservedPost,PostMetric,WebResearchRun,WeeklyPlan,WeeklySummary)
        before={m.__name__:m.objects.count() for m in tables}
        stamps=list(CycleLedger.objects.order_by('id').values_list('updated_at',flat=True))
        refuse=AssertionError('El diagnóstico no debe llamar a LinkedIn ni a un proveedor de pago.')
        with ExitStack() as stack:
            for target in ('team_backend.connectors.get_connector','team_backend.metricas.get_connector','team_backend.analitica.get_connector',
                           'team_backend.operador.get_connector','knowledge.providers.claude'):
                stack.enter_context(patch(target,side_effect=refuse))
            stack.enter_context(patch('django.utils.timezone.now',return_value=NOW))  # the command reads the clock
            bucle_resultados.report(14,NOW)
            bucle_resultados.trace_piece(w['full'].id,NOW);bucle_resultados.trace_action(w['comment'].proposal_id,NOW)
            bucle_resultados.trace_action(w['follow'].proposal_id,NOW)
            call_command('bucle_resultados','--json',stdout=StringIO())
        self.assertEqual({m.__name__:m.objects.count() for m in tables},before)
        self.assertEqual(list(CycleLedger.objects.order_by('id').values_list('updated_at',flat=True)),stamps)
        self.assertEqual(self.fake.state['writes'],0)


class CommandTests(LoopBase):
    def setUp(self):
        super().setUp()
        clock=patch('django.utils.timezone.now',return_value=NOW);clock.start();self.addCleanup(clock.stop)

    def test_text_json_and_traces(self):
        w=self.world()
        out=StringIO();call_command('bucle_resultados',stdout=out)
        for title in ('Bucle de resultados · 14 días (2026-11-02 → 2026-11-16)','¿Llega?','¿Lo usan los agentes?','¿Vuelve al ciclo?',
                      'comment_outcomes · no se registra','Veredicto por flujo','  comentarios: parcial'):
            self.assertIn(title,out.getvalue())
        out=StringIO();call_command('bucle_resultados','--json','--dias','30',stdout=out)
        body=json.loads(out.getvalue())
        self.assertEqual((list(body),body['desde'],body['dias'],list(body['veredictos'])),
                         (['desde','hasta','dias','generado','llega','usan','vuelve','veredictos'],'2026-10-17',30,list(bucle_resultados.FLOWS)))
        out=StringIO();call_command('bucle_resultados','--pieza',str(w['full'].id),'--accion',str(w['comment'].proposal_id),stdout=out)
        self.assertIn(f'Traza de la pieza {w["full"].id}',out.getvalue())
        self.assertIn(f'Traza de la acción (propuesta) {w["comment"].proposal_id}',out.getvalue())
        out=StringIO();call_command('bucle_resultados','--pieza',str(w['full'].id),'--json',stdout=out)
        self.assertEqual([l['eslabon'] for l in json.loads(out.getvalue())['pieza']['eslabones']],
                         ['pieza','ejecucion','corte_24h','corte_72h','corte_7d','analitica','director','resumen'])
        with self.assertRaisesRegex(CommandError,'--dias'):call_command('bucle_resultados','--dias','0')


class VerdictTests(SimpleTestCase):
    def report(self,**states):
        out={'llega':{},'usan':{},'vuelve':{}}
        for checks in bucle_resultados.FLOWS.values():
            for check in checks:
                question,key=check.split('.');out[question][key]={'estado':states.get(key,'ok')}
        return out

    def test_a_flow_is_complete_broken_or_partial(self):
        self.assertEqual({v['veredicto'] for v in bucle_resultados.verdicts(self.report()).values()},{'completo'})
        verdicts=bucle_resultados.verdicts(self.report(comentarios='roto',referent_signals='roto',comment_outcomes='no_se_registra',
                                                       network_engaged='sin_datos',investigacion='sin_datos',canario='parcial'))
        self.assertEqual({flow:v['veredicto'] for flow,v in verdicts.items()},
                         {'posts':'completo','comentarios':'roto','red':'completo','investigacion':'parcial','resumen_semanal':'completo',
                          'cuenta':'parcial'})
        self.assertEqual(verdicts['red']['pendiente'],['usan.network_engaged: sin_datos'])

    def test_snapshots_are_read_back_without_the_database(self):
        packed=orquestacion.pack({'a':(1,[{'b':None}]),'c':{'limitations':['x'],'d':''}})
        self.assertEqual(bucle_resultados.plain(packed),{'a':[1,[{'b':None}]],'c':{'limitations':['x'],'d':''}})
        self.assertFalse(bucle_resultados.filled({'limitations':['Sin referente asociado.'],'dossier':None,'audience':{'coverage':None}}))
        self.assertTrue(bucle_resultados.filled({'referent':{'id':'r-1'}}))
        self.assertFalse(bucle_resultados.filled([]))
