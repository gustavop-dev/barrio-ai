"""Monthly review of analista_barrio_resultados (docs/funcionalidades/revision-mensual.md): queued once on the first
Monday, the month's figures from stored data only (missing is never zero, «parcial» under four weeks with data), the
weekly summary's number validator applied to every change, the paid call (patched: no spend), each change decided apart
in Tu turno (approve, edit, reject, revert), what came of last month's changes and the notice."""
import json
import os
import uuid
from datetime import date, datetime, time, timedelta
from unittest.mock import patch

from django.utils import timezone

from knowledge import db
from team_backend import autopiloto, jobs, notificaciones, oficina_views, operador, orientacion, revision_mensual
from team_backend.models import (ActionExecution, ActionProposal, AudienceSnapshot, AuditEvent, EditorialPiece, Job, MonthlyReview,
                                 Notification, PostMetric, StrategyChange, WeeklySummary)
from team_backend.tests.test_metricas import MetricsBase

MONTH=date(2026,10,1)  # Mondays 5, 12, 19 and 26; long finished (never the real last month)
PREVIOUS=date(2026,9,1)
CITES=['LI-06-V008-K01','LI-06-V008-K02']
# Changes whose every figure is in the October fixture (por_tipo.A 1100, por_tipo.G 800 and 1.5, the month 1000 and 2.5,
# 4 posts against 1, 30 followers gained from 500).
CHANGE_A={'titulo':'Más posts de tipo A','propuesta':'Dedica más días de la semana a posts de tipo A (aplicado).',
          'razon':'Los posts de tipo A tuvieron la mediana más alta del mes.','cifra':'por_tipo.A.mediana_impresiones_72h: 1100',
          'comparado_con':'por_tipo.G.mediana_impresiones_72h: 800','refs':[],
          'espera':'Que suba la mediana de impresiones a las 72 h el mes que viene.','metrica':'mediana_impresiones_72h'}
CHANGE_B={'titulo':'Publicar cada semana','propuesta':'Mantén un post por semana sin saltarte ninguna.',
          'razon':'Octubre tuvo más posts que septiembre.','cifra':'metricas.publicaciones.mes: 4',
          'comparado_con':'metricas.publicaciones.mes_anterior: 1','refs':[],'espera':'Que no haya semanas sin post.','metrica':'publicaciones'}
CHANGE_C={'titulo':'Cerrar los G con una pregunta','propuesta':'Termina los posts de tipo G con una pregunta a founders.',
          'razon':'Los G tuvieron la interacción más baja.','cifra':'por_tipo.G.mediana_interaccion_pct_72h: 1.5',
          'comparado_con':'metricas.mediana_interaccion_pct_72h.mes: 2.5','refs':[],'espera':'Que suba la interacción de los G.',
          'metrica':'mediana_interaccion_pct_72h'}
CHANGE_D={'titulo':'Responder el mismo día','propuesta':'Responde a cada comentario de tus posts el mismo día.',
          'razon':'Los seguidores crecieron poco.','cifra':'audiencia.seguidores.ganados: 30',
          'comparado_con':'audiencia.seguidores.primera.valor: 500','refs':[],'espera':'Que crezcan más los seguidores.',
          'metrica':'seguidores_ganados'}


def model_answer(cambios=None,**overrides):
    """What the model returns for the October fixture: every number is in the stats except the invented one, and one
    entry lacks its course citation."""
    data={'titular':'Octubre con 4 posts y 1000 impresiones de mediana a las 72 h',
          'lo_que_paso':[{'texto':'Se publicaron 4 posts, frente a 1 en septiembre.','cifra':'metricas.publicaciones.mes: 4','course_citations':CITES}],
          'lo_que_funciono':[{'texto':'La mediana de impresiones a las 72 h subió a 1000.','cifra':'metricas.mediana_impresiones_72h.mes: 1000',
                              'course_citations':CITES},
                             {'texto':'Los posts de tipo A rindieron más.','cifra':'por_tipo.A.mediana_impresiones_72h: 1100','course_citations':[]}],
          'lo_que_no':[{'texto':'El alcance cayó un 4321 %.','cifra':'','course_citations':CITES}],
          'no_concluyente':['Con 3 posts medidos no se puede separar el efecto del tipo de post.'],
          'cambios_previos':[],'cambios':[CHANGE_A] if cambios is None else cambios}
    data.update(overrides)
    return data


class ReviewBase(MetricsBase):
    def setUp(self):
        super().setUp()
        env=patch.dict(os.environ,{'MONTHLY_REVIEW_ENABLED':'true','MONTHLY_REVIEW_MAX_USD':'2.00','WEEKLY_SUMMARY_TIME':'07:30',
                                   'LEAD_ENABLED':'false','INBOX_ENABLED':'false','ANTHROPIC_MODEL':'claude-opus-5-5'})
        env.start();self.addCleanup(env.stop)
        notify=patch('team_backend.alerts.notify');self.notify=notify.start();self.addCleanup(notify.stop)
        self.calls=[]

    def at(self,day,hour=10,minute=0):
        return datetime.combine(day,time(hour,minute),tzinfo=operador.local_tz())

    def post_on(self,day,kind,cut=None):
        when=self.at(day,8)
        piece=EditorialPiece.objects.create(account=self.account,slot_date=day,scheduled_for=when,state='ready',final_text=f'Post del {day:%d/%m}',
                                            brief={'pillar':'applied_ai','gasp_type':kind,'thesis':'Tesis'})
        proposal=ActionProposal.objects.create(account=self.account,piece=piece,capability='CONT-09',payload={'text':piece.final_text},
                                               payload_hash='0'*64,state='confirmed')
        ActionExecution.objects.create(proposal=proposal,idempotency_key=uuid.uuid4().hex,provider='linkedin_fake',state='confirmed',
                                       executed_by=self.gustavo,started_at=when)
        if cut:PostMetric.objects.create(piece=piece,kind='72h',published_at=when,captured_at=when+timedelta(days=3),**cut)
        return piece

    def weekly(self,monday,measured=1):
        return WeeklySummary.objects.create(week_start=monday,analysis={'titular':f'Semana del {monday:%d/%m}','lo_que_funciono':[{'texto':'Un post de tipo A llegó lejos.'}],
                                                                        'lo_que_no':[],'recomendaciones':[]},
                                            stats={'semana':{'publicaciones':{'disponible':True,'publicados':1,
                                                   'cortes':{'72h':{'medidos':measured,'mediana_impresiones':1000 if measured else None}}}},
                                                   'avisos_de_datos':[]})

    def month_fixture(self,weeks_with_data=4):
        """October: posts A 1200, G 800 and A 1000 at 72 h and an S never measured; followers from 500 to 530; the weekly
        summaries. September: one post with 600 at 72 h and nothing else."""
        self.pieces=[self.post_on(date(2026,10,6),'A',{'impressions':1200,'reactions':30,'comments':8,'reposts':4}),   # 3.5 %
                     self.post_on(date(2026,10,13),'G',{'impressions':800,'reactions':10,'comments':2,'reposts':0}),   # 1.5 %
                     self.post_on(date(2026,10,20),'A',{'impressions':1000,'reactions':20,'comments':4,'reposts':1}),  # 2.5 %
                     self.post_on(date(2026,10,27),'S')]
        self.post_on(date(2026,9,15),'A',{'impressions':600,'reactions':9,'comments':3,'reposts':0})  # 2.0 %
        AudienceSnapshot.objects.create(day=date(2026,10,1),followers=500,profile_views=40,profile_views_days=14)
        AudienceSnapshot.objects.create(day=date(2026,10,31),followers=530,profile_views=55,profile_views_days=14)
        for n,monday in enumerate(revision_mensual.weeks(MONTH)):self.weekly(monday,measured=1 if n<weeks_with_data else 0)

    def review(self,month,**fields):
        return MonthlyReview.objects.create(month_start=month,stats=fields.pop('stats',{'mes':{}}),
                                            analysis=fields.pop('analysis',{'titular':'Mes con 4 posts','validacion':{'ok':True,'descartado':[]}}),**fields)

    def change(self,review,position,proposal,metric='mediana_impresiones_72h',**fields):
        return StrategyChange.objects.create(review=review,position=position,title=f'Cambio {position}',proposal=proposal,metric=metric,
                                             reason='Los datos lo respaldan.',expected='Que suba la métrica.',**fields)

    def ledger(self,provider,purpose,usd,when):
        with db.connect() as c:
            c.execute('INSERT INTO usage_ledger(id,provider,purpose,reserved_usd,actual_usd,status,created_at) VALUES(%s,%s,%s,%s,%s,%s,%s)',
                      (str(uuid.uuid4()),provider,purpose,usd,usd,'complete',when))

    def claude(self,answer):
        def fake(system,message,max_tokens=None,output_schema=None,effort=None,purpose='agent-run',model=None,context=None):
            self.calls.append({'system':system,'message':json.loads(message),'max_tokens':max_tokens,'schema':output_schema,
                               'effort':effort,'purpose':purpose,'model':model})
            return {'text':json.dumps(answer),'model':'claude-opus-5-5','estimated_usd':0.12,'request_id':'req_monthly',
                    'usage':{'input_tokens':14000,'output_tokens':5000,'stop_reason':'end_turn'}}
        return patch('knowledge.providers.claude',side_effect=fake)

    def run_job(self,month=MONTH,answer=None):
        jobs.enqueue_operation(self.bot,'monthly_review',{'month':month.isoformat()})
        with self.claude(model_answer() if answer is None else answer):
            while jobs.process_one(self.worker):pass
        return Job.objects.filter(kind='monthly_review').order_by('-created_at').first()


class SchedulingTests(ReviewBase):
    def setUp(self):
        super().setUp()
        Job.objects.create(owner=self.gustavo,request_hash='0'*64,agent='operador',task='observe',kind='observe',state='complete',
                           created_at=self.at(date(2026,10,14)))  # the machine worked in October

    def monday(self,hour,minute=0,day=0):
        return self.at(date(2026,11,2)+timedelta(days=day),hour,minute)  # 2 November 2026: the first Monday

    def test_the_month_its_weeks_and_the_first_monday_hour(self):
        self.assertEqual(revision_mensual.last_month(self.monday(9)),MONTH)
        self.assertEqual(revision_mensual.weeks(MONTH),[date(2026,10,5),date(2026,10,12),date(2026,10,19),date(2026,10,26)])
        self.assertEqual(revision_mensual.weeks(date(2027,2,1)),[date(2027,2,1),date(2027,2,8),date(2027,2,15),date(2027,2,22)])
        self.assertEqual(revision_mensual.due_at(self.monday(9,day=10)),self.monday(8,30))  # an hour after WEEKLY_SUMMARY_TIME
        self.assertEqual(revision_mensual.due_at(self.at(date(2027,2,10))),self.at(date(2027,2,1),8,30))  # the 1st can be the Monday
        w=revision_mensual.window(MONTH)
        self.assertEqual((w.first,w.last,w.start,w.end),(MONTH,date(2026,10,31),self.at(MONTH,0),self.at(date(2026,11,1),0)))

    def test_queued_once_on_the_first_monday_an_hour_after_the_weekly_summary(self):
        self.weekly(date(2026,10,26))
        self.assertEqual(revision_mensual.queue(self.bot,self.at(date(2026,11,1))),0)  # Sunday: the month ended, not its Monday
        self.assertEqual(revision_mensual.queue(self.bot,self.monday(8,29)),0)
        self.assertEqual(revision_mensual.queue(self.bot,self.monday(8,31)),1)
        job=Job.objects.get(kind='monthly_review')
        self.assertEqual((job.params,job.state,job.execute),({'month':'2026-10-01'},'queued',True))
        self.assertEqual(revision_mensual.queue(self.bot,self.monday(9)),0)  # one at a time
        Job.objects.filter(pk=job.pk).update(state='failed')
        self.assertEqual(revision_mensual.queue(self.bot,self.monday(10)),0)  # the same deterministic id: one automatic attempt
        self.assertEqual(revision_mensual.queue(self.bot,self.monday(10,day=14)),0)
        self.assertEqual(Job.objects.filter(kind='monthly_review').count(),1)

    def test_without_the_last_weekly_summary_it_waits_a_day(self):
        self.assertEqual(revision_mensual.queue(self.bot,self.monday(12)),0)
        self.assertEqual(revision_mensual.queue(self.bot,self.monday(8,29,day=1)),0)
        self.assertEqual(revision_mensual.queue(self.bot,self.monday(8,31,day=1)),1)

    def test_the_switch_and_a_stored_review_skip_it(self):
        self.weekly(date(2026,10,26))
        with patch.dict(os.environ,{'MONTHLY_REVIEW_ENABLED':'false'}):
            self.assertEqual(revision_mensual.queue(self.bot,self.monday(9)),0)
        self.review(MONTH)
        self.assertEqual(revision_mensual.queue(self.bot,self.monday(9)),0)
        self.assertFalse(Job.objects.filter(kind='monthly_review').exists())

    def test_an_idle_month_or_the_monthly_budget_skip_it(self):
        self.weekly(date(2026,10,26))
        Job.objects.filter(kind='observe').update(created_at=self.at(date(2026,9,14)))  # the machine only ran in September
        self.assertEqual(revision_mensual.queue(self.bot,self.monday(9)),0)
        Job.objects.filter(kind='observe').update(created_at=self.at(date(2026,10,14)))
        self.ledger('anthropic','monthly-review','2.00',self.monday(6))
        self.assertEqual(revision_mensual.queue(self.bot,self.monday(9)),0)
        self.assertFalse(Job.objects.filter(kind='monthly_review').exists())

    def test_the_autopilot_tick_reports_it(self):
        self.weekly(date(2026,10,26))
        self.assertEqual(autopiloto.tick(self.bot,self.monday(9))['monthly_review'],1)
        self.assertEqual(autopiloto.tick(self.bot,self.monday(9,5))['monthly_review'],0)

    def test_the_registries_know_the_job(self):
        self.assertEqual(oficina_views.JOB_ROLES['monthly_review'],'analista_barrio_resultados')
        self.assertEqual(oficina_views.DESCRIPTIONS['monthly_review'],'Revisando el mes y proponiendo cambios')
        self.assertEqual(jobs.OPERATION_PERMISSIONS['monthly_review'],['operate_linkedin','run_agents','use_paid_providers'])
        self.assertIn('monthly_review',jobs.PAID_OPERATIONS)
        self.assertEqual(notificaciones.FEED_KINDS['monthly_review'],('tuyo',True,'Revisión mensual lista'))
        self.assertTrue(notificaciones.push_enabled('monthly_review'))


class StatsTests(ReviewBase):
    def test_the_month_in_figures_next_to_the_previous_one(self):
        self.month_fixture()
        data=revision_mensual.stats(MONTH,self.at(date(2026,11,2),9))
        month=data['mes'];posts=month['publicaciones']
        self.assertEqual((month['desde'],month['hasta'],data['mes_anterior']['desde']),('2026-10-01','2026-10-31','2026-09-01'))
        self.assertEqual(posts['publicados'],4)
        self.assertEqual(posts['cortes']['72h'],{'medidos':3,'pendientes':0,'sin_dato':1,'mediana_impresiones':1000,'mediana_interaccion_pct':2.5})
        self.assertEqual(posts['posts'][0]['pieza_id'],str(self.pieces[0].id))
        self.assertEqual((posts['posts'][0]['tipo'],posts['posts'][0]['impresiones_72h'],posts['posts'][0]['interaccion_pct_72h']),('A',1200,3.5))
        types=month['por_tipo']['tipos']
        self.assertEqual(types['A'],{'publicados':2,'medidos_72h':2,'mediana_impresiones_72h':1100,'mediana_interaccion_pct_72h':3.0})
        self.assertEqual(types['G'],{'publicados':1,'medidos_72h':1,'mediana_impresiones_72h':800,'mediana_interaccion_pct_72h':1.5})
        self.assertEqual(types['S'],{'publicados':1,'medidos_72h':0,'mediana_impresiones_72h':None,'mediana_interaccion_pct_72h':None})
        self.assertEqual(month['audiencia']['seguidores'],{'primera':{'dia':'2026-10-01','valor':500},'ultima':{'dia':'2026-10-31','valor':530},'ganados':30})
        self.assertEqual(month['audiencia']['visitas_al_perfil']['ventana_dias'],14)
        # Sources that did not run are missing, never zero.
        self.assertFalse(month['comentarios']['disponible']);self.assertFalse(month['red']['disponible'])
        metrics=data['metricas']
        self.assertEqual(metrics['publicaciones'],{'etiqueta':'Posts publicados en el mes','mes':4,'mes_anterior':1,'diferencia':3.0,'variacion_pct':300.0})
        self.assertEqual((metrics['mediana_impresiones_72h']['mes'],metrics['mediana_impresiones_72h']['mes_anterior'],
                          metrics['mediana_impresiones_72h']['diferencia'],metrics['mediana_impresiones_72h']['variacion_pct']),(1000,600,400.0,66.7))
        self.assertEqual((metrics['mediana_interaccion_pct_72h']['mes'],metrics['mediana_interaccion_pct_72h']['mes_anterior']),(2.5,2.0))
        self.assertEqual((metrics['seguidores_ganados']['mes'],metrics['seguidores_ganados']['mes_anterior'],metrics['seguidores_ganados']['diferencia']),(30,None,None))
        self.assertEqual((metrics['tasa_respuesta_comentarios']['mes'],metrics['aceptacion_invitaciones']['mes']),(None,None))
        self.assertEqual(set(metrics),set(revision_mensual.METRICS))
        # The weekly summaries of the month, compact.
        self.assertEqual((data['semanas_del_mes'],data['semanas_con_datos'],data['semanas_necesarias'],data['parcial']),(4,4,4,False))
        week=data['semanas'][0]
        self.assertEqual((week['desde'],week['hasta'],week['con_datos'],week['titular'],week['lo_que_funciono']),
                         ('2026-10-05','2026-10-11',True,'Semana del 05/10',['Un post de tipo A llegó lejos.']))
        self.assertEqual(week['cifras']['publicaciones.cortes.72h.mediana_impresiones'],1000)
        self.assertEqual((data['cambios_previos'],data['rechazados']),([],[]))
        self.assertEqual(data['avisos_de_datos'],['Posts del mes aún sin su corte de 7d: 1.',
                                                  'Sin datos de comentarios: El equipo no comentó en posts de otros este mes.',
                                                  'Sin datos de red: La red no funcionó este mes.'])

    def test_fewer_than_four_weeks_with_data_make_it_partial(self):
        self.month_fixture(weeks_with_data=2)
        WeeklySummary.objects.filter(week_start=date(2026,10,26)).delete()
        data=revision_mensual.stats(MONTH,self.at(date(2026,11,2),9))
        self.assertEqual((data['semanas_con_datos'],data['parcial']),(2,True))
        self.assertEqual(data['avisos_de_datos'][:3],['Revisión parcial: 2 de 4 semanas con posts medidos; hacen falta 4 para comparar el mes.',
                                                      'La semana del 2026-10-19 no tiene posts medidos a las 72 h.',
                                                      'La semana del 2026-10-26 no tiene resumen semanal.'])
        result=revision_mensual.validate(model_answer(),data,MONTH)
        self.assertIn('Revisión parcial: 2 de 4 semanas con posts medidos.',result['metodo'])

    def test_a_month_without_data_is_missing_never_zero(self):
        data=revision_mensual.stats(date(2026,8,1),self.at(date(2026,9,7),9))
        self.assertEqual(data['mes']['publicaciones'],{'disponible':False,'motivo':'No se publicó ningún post en el mes.'})
        self.assertEqual(data['metricas']['publicaciones'],{'etiqueta':'Posts publicados en el mes','mes':None,'mes_anterior':None,
                                                            'diferencia':None,'variacion_pct':None})
        self.assertEqual((data['semanas_del_mes'],data['semanas_con_datos'],data['parcial']),(5,0,True))
        self.assertIn('El mes anterior no tiene datos con que comparar.',data['avisos_de_datos'])


class ValidationTests(ReviewBase):
    def setUp(self):
        super().setUp()
        self.month_fixture()
        self.data=revision_mensual.stats(MONTH,self.at(date(2026,11,2),9))

    def check(self,*changes,**fields):
        return revision_mensual.validate(model_answer(list(changes),**fields),self.data,MONTH)

    def dropped(self,result):
        return {d['texto']:d for d in result['validacion']['descartado'] if d['campo']=='cambios'}

    def test_a_change_quoting_figures_of_the_stats_passes_with_only_known_refs(self):
        piece=str(self.pieces[0].id)
        result=self.check(dict(CHANGE_A,refs=[piece,'pieza-inventada']))
        self.assertEqual(result['cambios'],[dict(CHANGE_A,refs=[piece])])
        self.assertIn('no es una prueba estadística',result['metodo'])
        self.assertEqual(result['no_concluyente'],['Con 3 posts medidos no se puede separar el efecto del tipo de post.'])

    def test_an_invented_figure_drops_the_change_and_the_sentence(self):
        result=self.check(dict(CHANGE_A,titulo='Más carruseles',propuesta='Publica más carruseles.',cifra='metricas.mediana_impresiones_72h.mes: 4321'),
                          dict(CHANGE_B,titulo='Sin comparación',propuesta='Publica los viernes.',comparado_con='nada'))
        self.assertEqual(result['cambios'],[])
        dropped=self.dropped(result)
        self.assertEqual(dropped['Más carruseles'],{'campo':'cambios','texto':'Más carruseles','cifras_no_encontradas':['4321'],
                                                    'sin_cifra':False,'sin_comparacion':False})
        self.assertTrue(dropped['Sin comparación']['sin_comparacion'])
        self.assertEqual([i['texto'] for i in result['lo_que_no']],[])
        self.assertIn({'campo':'lo_que_no','texto':'El alcance cayó un 4321 %.','cifras_no_encontradas':['4321'],'sin_cifra':False},
                      result['validacion']['descartado'])
        self.assertIn('Se descartaron 2 cambios propuestos (ver validación).',result['advertencias'])

    def test_more_than_three_changes_keep_the_first_three(self):
        result=self.check(CHANGE_A,CHANGE_B,CHANGE_C,CHANGE_D,CHANGE_A)
        self.assertEqual([c['titulo'] for c in result['cambios']],[CHANGE_A['titulo'],CHANGE_B['titulo'],CHANGE_C['titulo']])
        self.assertTrue(self.dropped(result)[CHANGE_D['titulo']]['mas_de_tres'])
        self.assertIn({'campo':'cambios','texto':CHANGE_A['titulo'],'repetido':True},result['validacion']['descartado'])

    def test_a_rejected_proposal_a_gate_a_prompt_or_an_unknown_metric_is_dropped(self):
        old=self.review(PREVIOUS)
        self.change(old,0,'Publica los martes en vez de los lunes.',state='rechazado',decision_note='Los lunes rinden.')
        data=revision_mensual.stats(MONTH,self.at(date(2026,11,2),9))
        self.assertEqual(data['rechazados'],[{'titulo':'Cambio 0','propuesta':'Publica los martes en vez de los lunes.','mes':'2026-09-01',
                                              'nota':'Los lunes rinden.'}])
        result=revision_mensual.validate(model_answer([
            dict(CHANGE_B,titulo='Mover el día',propuesta='Publica los MARTES en vez de los lunes'),
            dict(CHANGE_A,titulo='Más comentarios',propuesta='Baja el umbral de la compuerta de comentarios.'),
            dict(CHANGE_A,titulo='Redactor más breve',propuesta='Acorta el prompt del redactor.'),
            dict(CHANGE_A,titulo='Más invitaciones',propuesta='Sube el límite diario de invitaciones.'),
            dict(CHANGE_B,titulo='Más likes',propuesta='Busca más likes.',metrica='likes'),
            CHANGE_A]),data,MONTH)
        self.assertEqual([c['titulo'] for c in result['cambios']],[CHANGE_A['titulo']])
        dropped=self.dropped(result)
        self.assertTrue(dropped['Mover el día']['repite_rechazado'])
        for title in ('Más comentarios','Redactor más breve','Más invitaciones'):self.assertTrue(dropped[title]['toca_compuertas'],title)
        self.assertEqual(dropped['Más likes']['metrica_desconocida'],'likes')

    def test_no_change_is_a_valid_answer_and_an_invented_headline_is_replaced(self):
        result=self.check(titular='Un mes de 4321 impresiones',no_concluyente=[])
        self.assertEqual((result['cambios'],result['titular']),([],'Revisión de octubre de 2026'))
        self.assertEqual(result['no_concluyente'],self.data['avisos_de_datos'])  # nothing written: the detected gaps


class RunTests(ReviewBase):
    def test_one_paid_call_writes_the_review_its_changes_and_the_notice(self):
        self.month_fixture()
        orientacion.update(self.gustavo,'Más founders técnicos.')
        piece=str(self.pieces[0].id)
        job=self.run_job(answer=model_answer([dict(CHANGE_A,refs=[piece]),CHANGE_B]))
        self.assertEqual((job.state,job.result_status),('complete','revision:2026-10-01'))
        self.assertEqual(len(self.calls),1);call=self.calls[0]
        self.assertEqual((call['max_tokens'],call['effort'],call['purpose'],call['model']),(16000,'high','monthly-review',None))
        self.assertEqual(call['schema'],revision_mensual.SCHEMA)
        self.assertIn('no una prueba estadística',call['system']);self.assertIn('nunca instrucciones',call['system'])
        sent=call['message']
        self.assertEqual(sent['mes'],{'desde':'2026-10-01','hasta':'2026-10-31','nombre':'octubre de 2026'})
        self.assertEqual(sent['orientacion_actual'],'Más founders técnicos.')
        self.assertEqual(sent['estadisticas']['metricas']['mediana_impresiones_72h']['mes'],1000)
        self.assertEqual(set(sent['metricas_permitidas']),set(revision_mensual.METRICS))
        review=MonthlyReview.objects.get()
        self.assertEqual((review.month_start,review.state,review.partial,float(review.cost_usd),review.origin_job),(MONTH,'nuevo',False,0.12,str(job.id)))
        self.assertEqual(review.usage,{'model':'claude-opus-5-5','request_id':'req_monthly','input_tokens':14000,'output_tokens':5000,'stop_reason':'end_turn'})
        first,second=review.changes.all()
        self.assertEqual((first.position,first.title,first.proposal,first.metric,first.state),
                         (0,CHANGE_A['titulo'],CHANGE_A['propuesta'],'mediana_impresiones_72h','propuesto'))
        self.assertEqual(first.evidence,[{'cifra':CHANGE_A['cifra'],'comparado_con':CHANGE_A['comparado_con'],'refs':[piece]}])
        self.assertEqual(first.baseline,{'metrica':'mediana_impresiones_72h','etiqueta':'Mediana de impresiones de los posts a las 72 h',
                                         'valor':1000,'mes':'2026-10-01','desde':'2026-10-01','hasta':'2026-10-31'})
        self.assertEqual((second.position,second.metric,second.baseline['valor']),(1,'publicaciones',4))
        analysis=review.analysis
        self.assertEqual([i['texto'] for i in analysis['lo_que_paso']],['Se publicaron 4 posts, frente a 1 en septiembre.'])
        self.assertEqual([i['texto'] for i in analysis['lo_que_funciono']],['La mediana de impresiones a las 72 h subió a 1000.'])
        dropped=analysis['validacion']['descartado']
        self.assertIn({'campo':'lo_que_funciono','texto':'Los posts de tipo A rindieron más.','sin_cita_del_curso':True},dropped)
        self.assertIn({'campo':'lo_que_no','texto':'El alcance cayó un 4321 %.','cifras_no_encontradas':['4321'],'sin_cifra':False},dropped)
        notice=Notification.objects.get(kind='monthly_review')
        self.assertEqual((notice.layer,notice.link,notice.ref,notice.title),
                         ('tuyo','/resultados#revision-mensual','monthly_review:2026-10-01','Revisión de octubre de 2026'))
        self.assertEqual(notice.detail,f'{analysis["titular"]} · 2 cambios de estrategia esperan tu decisión en Tu turno.')
        self.assertEqual(self.notify.call_args.kwargs['url'],'/resultados#revision-mensual')
        created=AuditEvent.objects.get(action='monthly_review.created')
        self.assertEqual((created.metadata['changes'],created.metadata['partial']),(2,False))
        scene=AuditEvent.objects.get(action='office.event')
        self.assertEqual((scene.target,scene.metadata['tipo'],scene.metadata['destino']),('analista_barrio_resultados','entrega','director_editorial'))
        self.assertEqual(orientacion.text(),'Más founders técnicos.')  # nothing reaches the orientation without Gustavo

    def test_no_change_is_stored_and_announced(self):
        self.month_fixture()
        self.run_job(answer=model_answer([]))
        review=MonthlyReview.objects.get()
        self.assertEqual((review.changes.count(),review.analysis['cambios']),(0,[]))
        self.assertEqual(Notification.objects.get(kind='monthly_review').detail,f'{review.analysis["titular"]} · Este mes no propone cambios de estrategia.')

    def test_a_stored_month_is_never_paid_again_and_an_unfinished_one_never_runs(self):
        self.run_job()
        job=self.run_job()
        self.assertEqual(job.state,'failed');self.assertIn('Ya hay una revisión',job.error)
        self.assertEqual((len(self.calls),MonthlyReview.objects.count()),(1,1))
        job=self.run_job(month=revision_mensual.next_month(revision_mensual.last_month()))
        self.assertEqual(job.state,'failed');self.assertIn('aún no terminó',job.error)
        with self.assertRaisesRegex(Exception,'Ya hay una revisión'):revision_mensual.run(self.bot,MONTH)

    def test_the_monthly_budget_stops_the_call(self):
        self.ledger('anthropic','monthly-review','2.00',timezone.now())
        job=self.run_job()
        self.assertEqual(job.state,'failed');self.assertIn('MONTHLY_REVIEW_MAX_USD',job.error)
        self.assertEqual(self.calls,[]);self.assertFalse(MonthlyReview.objects.exists())

    def test_a_broken_answer_stores_nothing(self):
        job=self.run_job(answer='no es un objeto')
        self.assertEqual(job.state,'failed');self.assertIn('no devolvió un objeto',job.error)
        self.assertFalse(MonthlyReview.objects.exists());self.assertFalse(Notification.objects.filter(kind='monthly_review').exists())

    def test_the_next_review_writes_what_came_of_the_approved_changes(self):
        self.month_fixture()
        old=self.review(PREVIOUS)
        kept=self.change(old,0,'Más posts de tipo A.',state='aprobado',baseline={'valor':600,'mes':'2026-09-01'},
                         decided_at=self.at(date(2026,10,2)))
        ignored=self.change(old,1,'Otra cosa.',state='rechazado')
        unmeasured=self.change(old,2,'Más conexiones.',metric='aceptacion_invitaciones',state='aprobado',
                               baseline={'valor':40.0,'mes':'2026-09-01'})
        data=revision_mensual.stats(MONTH,self.at(date(2026,11,2),9))
        self.assertEqual(data['cambios_previos'][0],{'id':str(kept.id),'titulo':'Cambio 0','propuesta':'Más posts de tipo A.','estado':'aprobado',
                                                     'metrica':'mediana_impresiones_72h','aprobado_el':'2026-10-02','mes_de_la_linea_base':'2026-09-01',
                                                     'antes':600,'ahora':1000,'diferencia':400.0,'variacion_pct':66.7})
        verdict={'id':str(kept.id),'veredicto':'se_conserva','texto':'La mediana pasó de 600 a 1000 impresiones.','cifra':'cambios_previos.ahora: 1000'}
        self.run_job(answer=model_answer([],cambios_previos=[verdict,dict(verdict,id=str(uuid.uuid4()))]))  # an unknown id is ignored
        review=MonthlyReview.objects.get(month_start=MONTH)
        for c in (kept,ignored,unmeasured):c.refresh_from_db()
        self.assertEqual(kept.outcome,{'veredicto':'se_conserva','texto':'La mediana pasó de 600 a 1000 impresiones.','cifra':'cambios_previos.ahora: 1000',
                                       'metrica':'mediana_impresiones_72h','antes':600,'despues':1000,'diferencia':400.0,
                                       'revision':str(review.id),'mes':'2026-10-01'})
        self.assertEqual((unmeasured.outcome['veredicto'],unmeasured.outcome['antes'],unmeasured.outcome['despues']),('sin_dato',40.0,None))
        self.assertEqual(ignored.outcome,{})
        self.assertEqual([(p['id'],p['veredicto']) for p in review.analysis['cambios_previos']],
                         [(str(kept.id),'se_conserva'),(str(unmeasured.id),'sin_dato')])


class DecisionTests(ReviewBase):
    URL='/api/v1/resultados/revision-mensual'

    def setUp(self):
        super().setUp()
        self.current=self.review(MONTH)
        self.a=self.change(self.current,0,'Dedica más días a posts de tipo A.')
        self.b=self.change(self.current,1,'Comenta en hilos con conversación.',metric='tasa_respuesta_comentarios')

    def cards(self):
        data=self.human.get('/api/v1/tu-turno').json()
        return data,[c for c in data['items'] if c['type']=='cambio_estrategia']

    def test_each_change_is_its_own_card_until_decided(self):
        old=self.change(self.review(PREVIOUS),0,'Una propuesta de septiembre.')
        data,cards=self.cards()
        self.assertEqual({c['id'] for c in cards},{f'strategy_change:{self.a.id}',f'strategy_change:{self.b.id}'})  # the latest review only
        card=next(c for c in cards if c['id']==f'strategy_change:{self.a.id}')
        self.assertEqual((card['priority'],card['agent'],card['agent_label'],card['title'],card['body'],card['state']),
                         ('cuando_puedas','analista_barrio_resultados','Analista del barrio','Cambio de estrategia: Cambio 0',
                          'Dedica más días a posts de tipo A.','nueva'))
        base=f'{self.URL}/cambios/{self.a.id}'
        self.assertEqual(card['actions'],[{'label':'Aprobar','endpoint':f'{base}/aprobar','primary':True},
                                          {'label':'Editar y aprobar','endpoint':f'{base}/editar',
                                           'editable':{'field':'text','value':'Dedica más días a posts de tipo A.'}},
                                          {'label':'Rechazar','endpoint':f'{base}/rechazar','note_optional':True},
                                          {'label':'Ver la revisión','href':'/resultados#revision-mensual'}])
        self.assertEqual((card['strategy_change']['metric'],card['strategy_change']['can_decide'],card['review']['label'],card['review']['partial']),
                         ('mediana_impresiones_72h',True,'Revisión de octubre de 2026',False))
        self.assertEqual(len(data['tasks']['estrategia']),2);self.assertGreaterEqual(data['counts']['tareas'],2)
        self.human.post('/api/v1/tu-turno/vistos',{'ids':[card['id']]},format='json')
        self.assertEqual(next(c for c in self.cards()[1] if c['id']==card['id'])['state'],'vista')
        self.assertEqual(self.human.post(card['actions'][0]['endpoint']).status_code,200)
        self.assertEqual(self.human.post(f'{self.URL}/cambios/{self.b.id}/rechazar',{'note':'No ahora.'},format='json').status_code,200)
        self.assertEqual(self.cards()[1],[])
        self.assertEqual(self.human.post(f'{self.URL}/cambios/{old.id}/rechazar').status_code,200)  # still decidable from Resultados

    def test_approve_appends_to_the_orientation_and_revert_removes_exactly_that(self):
        orientacion.update(self.gustavo,'Orientación de antes.')
        self.assertEqual(self.api.post(f'{self.URL}/cambios/{self.a.id}/aprobar').status_code,403)  # a human session only
        # «Editar y aprobar» has its own address and refuses an empty text: an older client cannot approve by accident.
        self.assertEqual(self.human.post(f'{self.URL}/cambios/{self.a.id}/editar',{},format='json').status_code,400)
        response=self.human.post(f'{self.URL}/cambios/{self.a.id}/aprobar',{},format='json')
        self.assertEqual(response.status_code,200,response.content)
        self.a.refresh_from_db();added=revision_mensual.block(self.a)
        self.assertTrue(added.startswith('[Revisión mensual de octubre de 2026 · cambio aprobado el '))
        self.assertTrue(added.endswith(f' · {self.a.id}]\nDedica más días a posts de tipo A.'))
        self.assertEqual(orientacion.text(),f'Orientación de antes.\n\n{added}')
        body=response.json()
        self.assertEqual((body['change']['state'],body['change']['can_revert'],body['change']['final_text'],body['orientation']['text']),
                         ('aprobado',True,'Dedica más días a posts de tipo A.',orientacion.text()))
        self.assertEqual((self.a.orientation_before,self.a.decided_by,self.a.state),('Orientación de antes.',self.gustavo,'aprobado'))
        self.assertTrue(AuditEvent.objects.filter(action='orientation.updated').exists())  # the orientation path, with its audit
        self.assertTrue(AuditEvent.objects.filter(action='strategy_change.approved',metadata__edited=False).exists())
        self.assertEqual(self.human.post(f'{self.URL}/cambios/{self.a.id}/aprobar').status_code,409)
        # «Editar y aprobar» the second one, then Gustavo edits the orientation in Ajustes.
        edited=self.human.post(f'{self.URL}/cambios/{self.b.id}/aprobar',{'text':'  Comenta solo en hilos   con founders. '},format='json')
        self.assertEqual(edited.status_code,200,edited.content)
        self.b.refresh_from_db();self.assertEqual(self.b.final_text,'Comenta solo en hilos con founders.')
        self.human.put('/api/v1/orientacion',{'text':orientacion.text()+'\n\nNota mía.'},format='json')
        reverted=self.human.post(f'{self.URL}/cambios/{self.a.id}/revertir').json()
        self.assertEqual((reverted['change']['state'],reverted['found'],reverted['message']),('revertido',True,None))
        self.assertEqual(orientacion.text(),f'Orientación de antes.\n\n{revision_mensual.block(self.b)}\n\nNota mía.')
        self.human.post(f'{self.URL}/cambios/{self.b.id}/revertir')
        self.assertEqual(orientacion.text(),'Orientación de antes.\n\nNota mía.')
        self.assertEqual(self.human.post(f'{self.URL}/cambios/{self.b.id}/revertir').status_code,409)
        self.assertEqual(self.human.post(f'{self.URL}/cambios/{uuid.uuid4()}/revertir').status_code,404)

    def test_approve_on_an_empty_orientation_and_its_revert(self):
        self.human.post(f'{self.URL}/cambios/{self.a.id}/aprobar')
        self.a.refresh_from_db()
        self.assertEqual(orientacion.text(),revision_mensual.block(self.a))
        self.human.post(f'{self.URL}/cambios/{self.a.id}/revertir')
        self.assertEqual(orientacion.text(),'')

    def test_revert_when_the_orientation_no_longer_has_the_change_leaves_it_alone(self):
        self.human.post(f'{self.URL}/cambios/{self.a.id}/aprobar')
        self.human.put('/api/v1/orientacion',{'text':'La reescribí entera.'},format='json')
        body=self.human.post(f'{self.URL}/cambios/{self.a.id}/revertir').json()
        self.assertEqual((body['found'],body['message'],body['change']['state']),(False,revision_mensual.NOT_FOUND,'revertido'))
        self.assertEqual(orientacion.text(),'La reescribí entera.')

    def test_a_rejection_is_remembered_by_the_next_reviews(self):
        self.assertEqual(self.api.post(f'{self.URL}/cambios/{self.a.id}/rechazar').status_code,403)
        body=self.human.post(f'{self.URL}/cambios/{self.a.id}/rechazar',{'note':'Ya hay muchos A.'},format='json').json()
        self.assertEqual((body['change']['state'],body['change']['decision_note'],body['change']['can_decide']),('rechazado','Ya hay muchos A.',False))
        self.assertEqual(self.human.post(f'{self.URL}/cambios/{self.a.id}/aprobar').status_code,409)
        self.assertEqual(orientacion.text(),'')
        later=revision_mensual.stats(date(2026,11,1),self.at(date(2026,12,7),9))
        self.assertEqual(later['rechazados'],[{'titulo':'Cambio 0','propuesta':'Dedica más días a posts de tipo A.','mes':'2026-10-01',
                                               'nota':'Ya hay muchos A.'}])
        self.assertEqual(revision_mensual.stats(date(2027,2,1),self.at(date(2027,3,1),9))['rechazados'],[])  # three months later


class ApiTests(ReviewBase):
    URL='/api/v1/resultados/revision-mensual'

    def test_generate_offers_the_estimated_cost_and_queues_one_job(self):
        data=self.api.get(self.URL).json()  # a service token can read
        self.assertIsNone(data['latest'])
        offer=data['generate']
        self.assertEqual((offer['available'],offer['month_start'],offer['estimated_usd'],offer['max_usd']),
                         (True,revision_mensual.last_month().isoformat(),0.19,0.47))
        self.assertEqual(self.api.post(f'{self.URL}/generar',{},format='json').status_code,403)  # human session only
        request_id=str(uuid.uuid4())
        response=self.human.post(f'{self.URL}/generar',{'request_id':request_id},format='json')
        self.assertEqual(response.status_code,202,response.content)
        self.assertEqual((response.json()['month_start'],response.json()['job']['id']),(revision_mensual.last_month().isoformat(),request_id))
        again=self.human.post(f'{self.URL}/generar',{'request_id':request_id},format='json')
        self.assertEqual((again.status_code,again.json()['job']['id']),(200,request_id))  # a retry is the same job
        self.assertEqual(self.human.post(f'{self.URL}/generar',{},format='json').status_code,409)  # already being prepared
        Job.objects.all().update(state='failed',error='Claude no respondió.')
        offer=self.human.get(self.URL).json()['generate']
        self.assertEqual((offer['available'],offer['last_error']),(True,'Claude no respondió.'))
        self.review(revision_mensual.last_month())
        self.assertEqual(self.human.post(f'{self.URL}/generar',{},format='json').status_code,409)

    def test_latest_previous_months_detail_and_seen(self):
        older=self.review(PREVIOUS)
        latest=self.review(MONTH,cost_usd='0.21',partial=True)
        self.change(latest,0,'Dedica más días a posts de tipo A.')
        data=self.api.get(self.URL).json()
        self.assertEqual((data['latest']['id'],data['latest']['label'],data['latest']['partial'],data['latest']['cost_usd'],data['pending']),
                         (str(latest.id),'Revisión de octubre de 2026',True,0.21,1))
        self.assertEqual(data['latest']['changes'][0]['endpoints']['approve'],f'{self.URL}/cambios/{latest.changes.get().id}/aprobar')
        self.assertNotIn('stats',data['latest'])
        self.assertEqual([r['id'] for r in data['previous']],[str(older.id)])
        self.assertEqual(self.api.get(f'{self.URL}/{latest.id}').json()['stats'],{'mes':{}})
        self.assertEqual(self.api.post(f'{self.URL}/{latest.id}/visto').status_code,403)
        self.assertEqual(self.human.post(f'{self.URL}/{latest.id}/visto').json()['review']['state'],'visto')
