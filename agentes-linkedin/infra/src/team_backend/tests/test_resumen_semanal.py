"""Weekly results summary of analista_barrio_resultados (docs/resumen-semanal.md): scheduling once per ISO week, the
deterministic stats (missing data is never zero), the number validator, the paid call (patched: no spend), Gustavo's
decisions (aplicar, descartar, deshacer), the Tu turno card, the notification and the director's input."""
import json
import os
import uuid
from datetime import date, datetime, time, timedelta
from unittest.mock import patch

from django.utils import timezone

from knowledge import db
from team_backend import autopiloto, editorial, jobs, notificaciones, oficina_views, operador, orientacion, resumen_semanal
from team_backend.models import (ActionExecution, ActionProposal, AuditEvent, Capture, Contact, EditorialPiece, Job, Notification,
                                 ObservedPost, Opportunity, PostMetric, WeeklySummary)
from team_backend.tests.test_auditoria_editorial import EditorialAuditBase
from team_backend.tests.test_metricas import MetricsBase
from team_backend.tests.test_publicacion import answers

WEEK=date(2026,10,12)  # a Monday, long finished (never the real last week)
LABEL_WEEK=date(2026,10,26)  # a week across two months, for the labels
PROPOSAL='Prioriza IA aplicada en los posts de la próxima semana.'


def analysis(**overrides):
    """A stored analysis (already validated) for the API, card and director tests."""
    data={'titular':'Semana con 3 posts','lo_que_funciono':[{'texto':'El post de IA aplicada llegó a 1.200 impresiones.','cifra':'1200'}],
          'lo_que_no':[],'recomendaciones':[{'texto':'Repetir applied_ai: 3,5 % de interacción.','cifra':'3.5'}],
          'orientacion_propuesta':PROPOSAL,'advertencias':['Pocos datos: 2 posts.'],'validacion':{'ok':True,'descartado':[]}}
    data.update(overrides)
    for field in ('lo_que_funciono','lo_que_no','recomendaciones'):
        for item in data.get(field,[]):item.setdefault('course_citations',['LI-06-V008-K01','LI-06-V008-K02'])
    return data


def model_answer(**overrides):
    """What the model returns for the full week fixture: every number is in the stats, except the two traps."""
    data={'titular':'Semana con 3 posts publicados y 840 impresiones de mediana a las 72 h',
          'lo_que_funciono':[{'texto':'El post de IA aplicada llegó a 1.200 impresiones a las 72 h.','cifra':'publicaciones.posts.72h.impresiones: 1200'}],
          'lo_que_no':[{'texto':'Solo 1 de 2 invitaciones resueltas acabó en conexión.','cifra':'red.aceptacion.conectadas: 1'},
                       {'texto':'El alcance cayó un 37 % frente a la semana anterior.','cifra':''}],
          'recomendaciones':[{'texto':'Repetir el pilar applied_ai: su post tuvo 3,5 % de interacción.','cifra':'interaccion_pct: 3.5'},
                             {'texto':'Publicar con más constancia.','cifra':'ninguna'}],
          'orientacion_propuesta':PROPOSAL,'advertencias':['Pocos datos: 2 posts con corte de 72 h.']}
    data.update(overrides)
    for field in ('lo_que_funciono','lo_que_no','recomendaciones'):
        for item in data.get(field,[]):item.setdefault('course_citations',['LI-06-V008-K01','LI-06-V008-K02'])
    return data


class SummaryBase(MetricsBase):
    def setUp(self):
        super().setUp()
        env=patch.dict(os.environ,{'WEEKLY_SUMMARY_ENABLED':'true','WEEKLY_SUMMARY_TIME':'07:30','WEEKLY_SUMMARY_LLM_USD':'1',
                                   'LEAD_ENABLED':'false','INBOX_ENABLED':'false','ANTHROPIC_MODEL':'claude-opus-5-5'})
        env.start();self.addCleanup(env.stop)
        notify=patch('team_backend.alerts.notify');self.notify=notify.start();self.addCleanup(notify.stop)
        self.calls=[];self.posts=0

    def at(self,day,hour=10,week=WEEK):
        return datetime.combine(week+timedelta(days=day),time(hour),tzinfo=operador.local_tz())

    def after(self,week=WEEK):
        """Monday 01:00 right after the week: when the figures are read."""
        return self.at(7,1,week)

    def post_on(self,day,cuts=None,pillar='applied_ai',week=WEEK,state='ready'):
        when=self.at(day,8,week)
        piece=EditorialPiece.objects.create(account=self.account,slot_date=when.date(),scheduled_for=when,state=state,final_text=f'Post del día {day}',
                                            brief={'pillar':pillar,'modality':'personal_startups','thesis':f'Tesis {day}'})
        if state!='ready':return piece
        proposal=ActionProposal.objects.create(account=self.account,piece=piece,capability='CONT-09',payload={'text':piece.final_text},
                                               payload_hash='0'*64,state='confirmed')
        ActionExecution.objects.create(proposal=proposal,idempotency_key=uuid.uuid4().hex,provider='linkedin_fake',state='confirmed',
                                       executed_by=self.gustavo,started_at=when)
        for kind,values in (cuts or {}).items():
            PostMetric.objects.create(piece=piece,kind=kind,published_at=when,captured_at=when+timedelta(days=3),**values)
        return piece

    def observed(self):
        self.posts+=1
        return ObservedPost.objects.create(account=self.account,provider_post_id=f'obs-{self.posts}',author_name='Ana Referente',text='Texto')

    def comment(self,state,created,**fields):
        return ActionProposal.objects.create(account=self.account,post=self.observed(),capability='INT-03',payload={'text':'Comentario'},
                                             payload_hash='0'*64,state=state,source='agent',created_at=created,**fields)

    def ledger(self,provider,purpose,usd,when):
        with db.connect() as c:
            c.execute('INSERT INTO usage_ledger(id,provider,purpose,reserved_usd,actual_usd,status,created_at) VALUES(%s,%s,%s,%s,%s,%s,%s)',
                      (str(uuid.uuid4()),provider,purpose,usd,usd,'complete',when))

    def contact(self,uid,**fields):
        return Contact.objects.create(account=self.account,provider_user_id=uid,display_name=uid,source=fields.pop('source','commenter'),**fields)

    def event(self,action,when,**metadata):
        return AuditEvent.objects.create(action=action,target='x',metadata=metadata,created_at=when)

    def week_fixture(self):
        """A full week: 3 posts (one blocked piece), 5 drafted comments, network moves, an opportunity, the inbox, captures,
        spend, the lead and a stop; and a previous week with one post and nothing else."""
        first=self.post_on(0,{'72h':{'impressions':1200,'reactions':30,'comments':8,'reposts':4,
                                     'commenters':[{'provider_user_id':'a','substantive':True},{'provider_user_id':'b','substantive':False}]}})
        self.post_on(2,{'72h':{'impressions':480,'reactions':10,'comments':None,'reposts':2}})  # LinkedIn hid the comments
        self.post_on(6)  # Sunday: its 72 h have not passed yet on Monday
        self.post_on(4,state='blocked')
        self.post_on(1,{'72h':{'impressions':600,'reactions':12,'comments':3,'reposts':0},'7d':{'impressions':900,'reactions':15,'comments':4,'reposts':1}},
                     week=WEEK-timedelta(days=7))
        # Comments: one of each fate.
        published=self.comment('confirmed',self.at(0),review={'decision':'approve'},decided_at=self.at(0,11))
        ActionExecution.objects.create(proposal=published,idempotency_key=uuid.uuid4().hex,provider='fake',state='confirmed',
                                       executed_by=self.gustavo,started_at=self.at(0,12))
        self.comment('rejected',self.at(1),decided_at=self.at(1,11),decided_by=self.gustavo)
        self.comment('discarded',self.at(2),decided_at=self.at(2,11),
                     review={'decision':'discard','answers':{'aporta':0.2},'thresholds':{'aporta':['min',0.6]}})
        self.comment('discarded',self.at(3),decided_at=self.at(3,11))
        self.comment('discarded',self.at(3,12))
        self.event('operator.comment_prefilter',self.at(1),decision='skip')
        # Network.
        self.event('network.classified',self.at(1),classified=10,fit=4)
        self.contact('c1',discovered_at=self.at(1),followed_at=self.at(2),stage='followed')
        self.contact('c2',discovered_at=self.at(-20),invited_at=self.at(-3),connected_at=self.at(3),stage='connected',
                     classification={'fit':True,'role':'comprador'},history=[{'at':self.at(3).isoformat(),'event':'connected','detail':''}])
        self.contact('c3',discovered_at=self.at(-20),invited_at=self.at(1),stage='closed',
                     history=[{'at':self.at(5).isoformat(),'event':'closed','detail':''}])
        self.contact('c4',discovered_at=self.at(2),source='incoming',stage='incoming')
        # An opportunity created and moved.
        Opportunity.objects.create(person_name='Mario Externo',modality='projectapp',stage='reunion',created_at=self.at(1),
                                   history=[{'at':self.at(1).isoformat(),'event':'created','stage':'conversacion','detail':''},
                                            {'at':self.at(4).isoformat(),'event':'stage','stage':'reunion','detail':''}])
        # The inbox.
        self.event('inbox.read_run',self.at(1),chats=4,read=2,assessed=3,flagged=2,stopped='')
        self.event('conversation.closed',self.at(2),how='respondi')
        # Captures: an idea used in the Monday piece and a comment on it.
        idea=Capture.objects.create(created_by=self.gustavo,note='Idea',purpose='post',state='usado',routed_to={'used_in':str(first.id)})
        comment=Capture.objects.create(created_by=self.gustavo,note='Me gustó el tono directo.',context_type='pieza',context_id=str(first.id),state='anotado')
        Capture.objects.filter(pk__in=[idea.pk,comment.pk]).update(created_at=self.at(2))
        # Spend.
        self.ledger('anthropic','propose-comment','0.30',self.at(1))
        self.ledger('anthropic','editorial-director','0.50',self.at(2))
        self.ledger('typesafe','lead-review','0.01',self.at(2))
        self.ledger('anthropic','editorial-director','0.70',self.at(-2))  # previous week
        # A stop.
        self.event('operator.machine_paused',self.at(5),reason='Viaje')
        return first

    def claude(self,answer):
        def fake(system,message,max_tokens=None,output_schema=None,effort=None,purpose='agent-run',model=None,context=None):
            self.calls.append({'system':system,'message':json.loads(message),'max_tokens':max_tokens,'schema':output_schema,
                               'effort':effort,'purpose':purpose,'model':model})
            return {'text':json.dumps(answer),'model':'claude-opus-5-5','estimated_usd':0.12,'request_id':'req_weekly',
                    'usage':{'input_tokens':9000,'output_tokens':3500,'stop_reason':'end_turn'}}
        return patch('knowledge.providers.claude',side_effect=fake)

    def run_job(self,week=WEEK,answer=None):
        jobs.enqueue_operation(self.bot,'weekly_summary',{'week':week.isoformat()})
        with self.claude(answer or model_answer()):
            while jobs.process_one(self.worker):pass
        return Job.objects.filter(kind='weekly_summary').order_by('-created_at').first()

    def summary(self,week=None,state='nuevo',**fields):
        return WeeklySummary.objects.create(week_start=week or resumen_semanal.last_week(),state=state,
                                            analysis=fields.pop('analysis',analysis()),stats={'semana':{}},**fields)


class SchedulingTests(SummaryBase):
    def setUp(self):
        super().setUp()
        self.ran(date(2026,11,2))  # the machine worked in the week being summarized

    def ran(self,week):
        Job.objects.create(owner=self.gustavo,request_hash='0'*64,agent='operador',task='observe',kind='observe',state='complete',
                           created_at=self.at(2,week=week))

    def monday(self,hour,minute=0,day=0):
        return datetime.combine(date(2026,11,9)+timedelta(days=day),time(hour,minute),tzinfo=operador.local_tz())

    def test_queued_once_per_week_on_monday_after_the_hour_for_the_week_that_ended(self):
        self.assertEqual(resumen_semanal.queue(self.bot,self.monday(7,29)),0)
        self.assertEqual(resumen_semanal.queue(self.bot,self.monday(7,31)),1)
        job=Job.objects.get(kind='weekly_summary')
        self.assertEqual((job.params,job.state,job.execute),({'week':'2026-11-02'},'queued',True))
        self.assertIn(job.id,list(jobs.lane_jobs('general').values_list('id',flat=True)))  # general lane
        self.assertNotIn(job.id,list(jobs.lane_jobs('acciones').values_list('id',flat=True)))
        self.assertEqual(resumen_semanal.queue(self.bot,self.monday(9)),0)  # one at a time
        Job.objects.filter(pk=job.pk).update(state='failed')
        self.assertEqual(resumen_semanal.queue(self.bot,self.monday(10)),0)  # the same deterministic id: one automatic attempt
        self.assertEqual(Job.objects.filter(kind='weekly_summary').count(),1)

    def test_a_week_the_machine_never_ran_is_not_paid_for(self):
        Job.objects.all().delete()
        self.assertEqual(resumen_semanal.queue(self.bot,self.monday(9)),0)
        self.ran(date(2026,10,26))  # activity in another week does not count
        self.assertEqual(resumen_semanal.queue(self.bot,self.monday(9)),0)
        self.ran(date(2026,11,2))
        self.assertEqual(resumen_semanal.queue(self.bot,self.monday(9)),1)

    def test_a_week_with_its_summary_or_the_switch_off_is_skipped_and_a_later_day_catches_up(self):
        with patch.dict(os.environ,{'WEEKLY_SUMMARY_ENABLED':'false'}):
            self.assertEqual(resumen_semanal.queue(self.bot,self.monday(9)),0)
        self.assertEqual(resumen_semanal.queue(self.bot,self.monday(9,day=2)),1)  # Wednesday, still the week of 2 November
        self.assertEqual(Job.objects.get(kind='weekly_summary').params,{'week':'2026-11-02'})
        Job.objects.filter(kind='weekly_summary').delete()
        self.summary(week=date(2026,11,2))
        self.assertEqual(resumen_semanal.queue(self.bot,self.monday(9)),0)

    def test_the_hour_is_configurable_and_the_budget_stops_it(self):
        with patch.dict(os.environ,{'WEEKLY_SUMMARY_TIME':'10:00'}):
            self.assertEqual(resumen_semanal.queue(self.bot,self.monday(9)),0)
        self.ledger('anthropic','weekly-summary','1.00',self.monday(6))
        self.assertEqual(resumen_semanal.queue(self.bot,self.monday(9)),0)
        with patch.dict(os.environ,{'WEEKLY_SUMMARY_TIME':'7h'}),self.assertRaisesRegex(ValueError,'WEEKLY_SUMMARY_TIME'):
            resumen_semanal.queue(self.bot,self.monday(9))

    def test_the_autopilot_tick_queues_it(self):
        report=autopiloto.tick(self.bot,self.monday(8))
        self.assertEqual(report['weekly_summary'],1)
        self.assertEqual(autopiloto.tick(self.bot,self.monday(8,5))['weekly_summary'],0)

    def test_the_office_scene_knows_the_job(self):
        self.assertEqual(oficina_views.JOB_ROLES['weekly_summary'],'analista_barrio_resultados')
        self.assertEqual(oficina_views.DESCRIPTIONS['weekly_summary'],'Escribiendo el resumen de la semana')


class StatsTests(SummaryBase):
    def test_the_week_in_figures_compared_with_the_previous_one(self):
        with patch.dict(os.environ,{'LEAD_ENABLED':'true'}):
            self.week_fixture()
            data=resumen_semanal.stats(WEEK,self.after())
        week=data['semana']
        self.assertEqual((week['desde'],week['hasta']),('2026-10-12','2026-10-18'))
        posts=week['publicaciones']
        self.assertEqual((posts['publicados'],posts['piezas_por_estado']),(3,{'blocked':1,'published':3}))
        self.assertEqual(posts['cortes']['72h'],{'medidos':2,'pendientes':1,'mediana_impresiones':840,'mediana_interaccion_pct':3.5,
                                                 'comentarios_con_sustancia':1})
        self.assertEqual(posts['cortes']['7d']['medidos'],0);self.assertEqual(posts['cortes']['7d']['pendientes'],3)
        monday=posts['posts'][0]
        self.assertEqual(monday['72h'],{'impresiones':1200,'reacciones':30,'comentarios':8,'compartidos':4,'comentarios_con_sustancia':1,
                                        'interaccion_pct':3.5})
        self.assertEqual(monday['7d'],'pendiente')
        self.assertIsNone(posts['posts'][1]['72h']['comentarios'])  # hidden by LinkedIn: missing, never zero
        self.assertIsNone(posts['posts'][1]['72h']['interaccion_pct'])
        self.assertEqual(posts['posts'][2]['72h'],'pendiente')
        self.assertEqual(week['comentarios'],{'disponible':True,'redactados':5,'publicados':1,
            'destino_de_los_borradores':{'descartado_por_el_lider':1,'descartado_por_la_politica':1,'publicado':1,
                                         'saltado_por_el_redactor':1,'vetado_por_gustavo':1},
            'lider':{'aprobados':1,'descartados':1},'posts_saltados_por_el_prefiltro':1})
        self.assertEqual(week['red'],{'disponible':True,'descubiertos':1,'clasificados':10,'clasificados_que_encajan':4,'seguidos':1,
            'invitados':1,'conectados':1,'conectados_que_encajan':1,'invitaciones_recibidas':1,
            'aceptacion':{'conectadas':1,'resueltas':2,'tasa_pct':50.0}})
        self.assertEqual(week['oportunidades'],{'disponible':True,'creadas':1,'creadas_por_etapa':{'conversacion':1},'movidas':1,
            'movidas_a_etapa':{'reunion':1},'abiertas_al_cierre':1,'creadas_por_modalidad':{'projectapp':1}})
        self.assertEqual(week['conversaciones'],{'disponible':True,'lecturas':1,'mensajes_juzgados':3,'te_tocaron':2,
            'cerradas_respondiste':1,'cerradas_sin_responder':0,'respondidas_en_linkedin':0})
        self.assertEqual(week['capturas'],{'disponible':True,'enviadas':2,'por_destino':{'post':1,'sin_indicar':1},
            'por_estado':{'anotado':1,'usado':1},'comentarios_sobre_piezas':1,'ideas_usadas_en_piezas_de_la_semana':1})
        spend=week['gasto_ia']
        self.assertEqual((spend['total_usd'],spend['anthropic_por_presupuesto_usd'],spend['otros_proveedores_usd']),
                         (0.81,{'general':0.3,'editorial':0.5,'red':0.0,'resumen_semanal':0.0,'imagenes':0.0,'otros':0.0},{'typesafe':0.01}))
        self.assertEqual(week['lider'],{'disponible':True,'por_capacidad':{'INT-03':{'aprobadas':1,'descartadas':1,
                                                                                    'preguntas_que_mas_fallan':{'aporta':1}}}})
        stops=week['pausas_y_bloqueos']
        self.assertEqual((stops['eventos'],stops['piezas_bloqueadas']),([{'tipo':'maquina_detenida','fecha':'2026-10-17'}],1))
        # The previous week: one post and nothing else measured.
        previous=data['semana_anterior']
        self.assertEqual(previous['publicaciones']['cortes']['7d']['mediana_impresiones'],900)
        self.assertFalse(previous['red']['disponible']);self.assertFalse(previous['oportunidades']['disponible'])
        compared=data['comparacion']
        self.assertEqual(compared['publicaciones.cortes.72h.mediana_impresiones'],{'semana':840,'semana_anterior':600,'diferencia':240,'variacion_pct':40.0})
        self.assertEqual(compared['publicaciones.publicados'],{'semana':3,'semana_anterior':1,'diferencia':2,'variacion_pct':200.0})
        self.assertEqual(compared['red.seguidos'],{'semana':1,'semana_anterior':None,'diferencia':None,'variacion_pct':None})
        self.assertEqual(compared['gasto_ia.total_usd']['semana_anterior'],0.7)
        self.assertEqual(data['avisos_de_datos'],['Pocos datos: 2 de 3 posts con corte de 72 h.'])

    def test_a_week_without_data_is_missing_never_zero(self):
        data=resumen_semanal.stats(WEEK,self.after())
        week=data['semana']
        for key in ('publicaciones','comentarios','red','oportunidades','conversaciones'):
            self.assertFalse(week[key]['disponible'],key);self.assertTrue(week[key]['motivo'],key)
        self.assertNotIn('publicados',week['publicaciones'])
        self.assertEqual(week['lider'],{'disponible':False,'motivo':'El líder (LEAD_ENABLED) está apagado.'})
        self.assertEqual(week['capturas']['enviadas'],0)  # he sent nothing: a real zero
        self.assertEqual(week['gasto_ia']['total_usd'],0.0)  # the ledger always runs: a real zero
        self.assertEqual(data['comparacion']['publicaciones.publicados'],{'semana':None,'semana_anterior':None,'diferencia':None,'variacion_pct':None})
        self.assertIn('Sin datos de publicaciones: La máquina no funcionó esta semana.',data['avisos_de_datos'])
        self.assertIn('Sin datos de inbox: El inbox no se leyó esta semana (INBOX_ENABLED apagado o sin lecturas).',data['avisos_de_datos'])


class ValidatorTests(SummaryBase):
    DATA={'semana':{'desde':'2026-10-26','hasta':'2026-11-01','publicados':3,'mediana':840,'interaccion_pct':3.5,'visitas':1840,
                    'cortes':{'72h':{'medidos':2}},'gasto':0.81,'tasa_pct':-12.5},'avisos_de_datos':['Pocos datos: 2 de 3 posts.']}

    def test_numbers_are_read_in_spanish_and_english_and_rounding_is_allowed(self):
        allowed=resumen_semanal.allowed_numbers(self.DATA)
        for text in ('840 impresiones','1.840 visitas','1,840 visitas','3,5 %','3.5 %','4 %','0,81 USD','12,5 puntos','72 h','del 26 de octubre',
                     'Semana del 26 al 1 de noviembre'):
            self.assertEqual(resumen_semanal.unknown_numbers(text,allowed),[],text)
        self.assertEqual(resumen_semanal.unknown_numbers('subió un 37 % hasta 1.900',allowed),['37','1.900'])
        self.assertEqual(resumen_semanal._readings('1.840'),[(1840.0,0),(1.84,3)])
        self.assertEqual(resumen_semanal._readings('1.234,5'),[(1234.5,1)])

    def test_claims_with_invented_or_no_numbers_are_dropped_and_recorded(self):
        raw={'titular':'Semana con 3 posts y 840 impresiones de mediana',
             'lo_que_funciono':[{'texto':'La mediana fue de 840 impresiones.','cifra':'semana.mediana: 840'},
                                {'texto':'Las visitas subieron un 37 %.','cifra':'semana.visitas'}],
             'lo_que_no':[{'texto':'Hubo poca constancia.','cifra':'ninguna'}],
             'recomendaciones':[{'texto':'Repetir el pilar con 3,5 % de interacción.','cifra':'semana.interaccion_pct: 3.5'}],
             'orientacion_propuesta':'Prioriza IA aplicada.','advertencias':['Pocos datos: 2 posts.','El 90 % de la audiencia es nueva.']}
        clean=resumen_semanal.validate(raw,self.DATA,LABEL_WEEK)
        self.assertEqual(clean['titular'],raw['titular'])
        self.assertEqual([i['texto'] for i in clean['lo_que_funciono']],['La mediana fue de 840 impresiones.'])
        self.assertEqual(clean['lo_que_no'],[])
        self.assertEqual(len(clean['recomendaciones']),1)
        self.assertEqual(clean['orientacion_propuesta'],'Prioriza IA aplicada.')
        self.assertEqual(clean['advertencias'],['Pocos datos: 2 posts.','Se quitaron 3 frases del análisis con cifras que no están en los datos de la semana.'])
        self.assertFalse(clean['validacion']['ok'])
        self.assertEqual([(d['campo'],d['cifras_no_encontradas'],d['sin_cifra']) for d in clean['validacion']['descartado']],
                         [('lo_que_funciono',['37'],False),('lo_que_no',[],True),('advertencias',['90'],False)])

    def test_an_invented_headline_or_orientation_is_replaced_or_dropped(self):
        raw={'titular':'Las impresiones crecieron 55 %','lo_que_funciono':[],'lo_que_no':[],'recomendaciones':[],
             'orientacion_propuesta':'Publica 5 veces por semana.','advertencias':[]}
        clean=resumen_semanal.validate(raw,self.DATA,LABEL_WEEK)
        self.assertEqual(clean['titular'],'Semana del 26 de octubre al 1 de noviembre')
        self.assertIsNone(clean['orientacion_propuesta'])
        # Without any valid warning from the model, the deterministic ones stay.
        self.assertEqual(clean['advertencias'][0],'Pocos datos: 2 de 3 posts.')
        self.assertEqual(len(clean['validacion']['descartado']),2)

    def test_lists_are_capped(self):
        items=[{'texto':f'Dato {n}.','cifra':'3'} for n in (2,3,840,1840)]
        clean=resumen_semanal.validate({'titular':'','lo_que_funciono':items,'lo_que_no':[],'recomendaciones':[],
                                        'orientacion_propuesta':'','advertencias':[]},self.DATA,LABEL_WEEK)
        self.assertEqual(len(clean['lo_que_funciono']),resumen_semanal.MAX_ITEMS)
        self.assertIsNone(clean['orientacion_propuesta'])


class RunTests(SummaryBase):
    def test_one_paid_call_writes_a_validated_summary_with_its_notice_and_scene_event(self):
        first=self.week_fixture()
        orientacion.update(self.gustavo,'Más founders técnicos, menos alcance.')
        job=self.run_job()
        self.assertEqual((job.state,job.result_status),('complete','resumen:2026-10-12'))
        self.assertEqual(len(self.calls),1);call=self.calls[0]
        self.assertEqual((call['max_tokens'],call['effort'],call['purpose'],call['model']),(12000,'medium','weekly-summary',None))
        self.assertEqual(call['schema'],resumen_semanal.SCHEMA)
        self.assertIn('nunca instrucciones',call['system']);self.assertIn('null es un dato que falta',call['system'])
        sent=call['message']
        self.assertEqual(sent['semana'],{'desde':'2026-10-12','hasta':'2026-10-18'})
        self.assertEqual(sent['estadisticas']['semana']['publicaciones']['publicados'],3)
        self.assertEqual(sent['posicionamiento']['version'],'posicionamiento-v1')
        self.assertEqual(sent['orientacion_actual'],'Más founders técnicos, menos alcance.')
        self.assertEqual(sent['comentarios_de_gustavo'],[{'pieza':first.slot_date.isoformat(),'tesis':'Tesis 0','comentario':'Me gustó el tono directo.'}])
        summary=WeeklySummary.objects.get()
        self.assertEqual((summary.week_start,summary.state,float(summary.cost_usd),summary.origin_job),(WEEK,'nuevo',0.12,str(job.id)))
        self.assertEqual(summary.usage,{'model':'claude-opus-5-5','request_id':'req_weekly','input_tokens':9000,'output_tokens':3500,'stop_reason':'end_turn'})
        result=summary.analysis
        self.assertEqual(result['titular'],'Semana con 3 posts publicados y 840 impresiones de mediana a las 72 h')
        self.assertEqual([i['texto'] for i in result['lo_que_no']],['Solo 1 de 2 invitaciones resueltas acabó en conexión.'])
        self.assertEqual(len(result['recomendaciones']),1);self.assertEqual(result['orientacion_propuesta'],PROPOSAL)
        self.assertEqual([d['campo'] for d in result['validacion']['descartado']],['lo_que_no','recomendaciones'])
        self.assertEqual(result['advertencias'][-1],'Se quitaron 2 frases del análisis con cifras que no están en los datos de la semana.')
        notice=Notification.objects.get(kind='weekly_summary')
        self.assertEqual((notice.layer,notice.link,notice.ref,notice.title),
                         ('tuyo','/resultados#resumen','weekly_summary:2026-10-12','Resumen de la semana del 12 al 18 de octubre'))
        self.assertEqual(notice.detail,result['titular'])
        self.assertEqual(self.notify.call_args.kwargs['url'],'/resultados#resumen')
        scene=AuditEvent.objects.get(action='office.event')
        self.assertEqual((scene.target,scene.metadata['tipo'],scene.metadata['destino']),('analista_barrio_resultados','entrega','director_editorial'))

    def test_a_stored_week_is_never_paid_again(self):
        self.run_job()
        job=self.run_job()
        self.assertEqual(job.state,'failed');self.assertIn('Ya hay un resumen',job.error)
        self.assertEqual(len(self.calls),1);self.assertEqual(WeeklySummary.objects.count(),1)

    def test_the_weekly_budget_stops_the_call(self):
        self.ledger('anthropic','weekly-summary','1.00',timezone.now())
        job=self.run_job()
        self.assertEqual(job.state,'failed');self.assertIn('WEEKLY_SUMMARY_LLM_USD',job.error)
        self.assertEqual(self.calls,[]);self.assertFalse(WeeklySummary.objects.exists())

    def test_an_unfinished_week_or_a_broken_answer_stores_nothing(self):
        job=self.run_job(week=resumen_semanal.last_week()+timedelta(days=7))
        self.assertEqual(job.state,'failed');self.assertIn('aún no terminó',job.error)
        with self.claude('no es un objeto'):
            jobs.enqueue_operation(self.bot,'weekly_summary',{'week':WEEK.isoformat()})
            while jobs.process_one(self.worker):pass
        self.assertIn('no devolvió un objeto',Job.objects.filter(kind='weekly_summary').order_by('-created_at').first().error)
        self.assertFalse(WeeklySummary.objects.exists())


class ApiTests(SummaryBase):
    URL='/api/v1/resultados/resumen-semanal'

    def test_latest_previous_weeks_and_detail(self):
        older=self.summary(week=resumen_semanal.last_week()-timedelta(days=7),state='descartado')
        latest=self.summary(cost_usd='0.14')
        data=self.api.get(self.URL).json()  # a service token can read
        self.assertEqual((data['latest']['id'],data['latest']['state'],data['latest']['cost_usd']),(str(latest.id),'nuevo',0.14))
        self.assertEqual(data['latest']['analysis']['orientacion_propuesta'],PROPOSAL)
        self.assertNotIn('stats',data['latest'])
        self.assertEqual([s['id'] for s in data['previous']],[str(older.id)])
        self.assertEqual((data['generate']['available'],data['generate']['reason']),(False,'La semana pasada ya tiene su resumen.'))
        detail=self.api.get(f'{self.URL}/{latest.id}').json()
        self.assertEqual(detail['stats'],{'semana':{}})

    def test_generate_offers_the_estimated_cost_and_queues_one_job(self):
        data=self.human.get(self.URL).json()
        self.assertIsNone(data['latest'])
        offer=data['generate']
        self.assertEqual((offer['available'],offer['week_start'],offer['estimated_usd'],offer['max_usd']),
                         (True,resumen_semanal.last_week().isoformat(),0.13,0.34))
        self.assertEqual(self.api.post(f'{self.URL}/generar',{},format='json').status_code,403)  # human session only
        request_id=str(uuid.uuid4())
        response=self.human.post(f'{self.URL}/generar',{'request_id':request_id},format='json')
        self.assertEqual(response.status_code,202,response.content)
        self.assertEqual((response.json()['week_start'],response.json()['job']['id']),(resumen_semanal.last_week().isoformat(),request_id))
        again=self.human.post(f'{self.URL}/generar',{'request_id':request_id},format='json')
        self.assertEqual((again.status_code,again.json()['job']['id']),(200,request_id))  # a retry is the same job
        self.assertEqual(self.human.post(f'{self.URL}/generar',{},format='json').status_code,409)  # already being prepared
        self.assertTrue(self.human.get(self.URL).json()['generate']['pending'])
        Job.objects.all().update(state='failed',error='Claude no respondió.')
        offer=self.human.get(self.URL).json()['generate']
        self.assertEqual((offer['available'],offer['last_error']),(True,'Claude no respondió.'))
        self.summary()
        self.assertEqual(self.human.post(f'{self.URL}/generar',{},format='json').status_code,409)

    def test_estimate_follows_past_costs(self):
        self.summary(week=WEEK,cost_usd='0.11');self.summary(week=WEEK+timedelta(days=7),cost_usd='0.17')
        self.assertEqual(resumen_semanal.estimate()['estimated_usd'],0.14)

    def test_apply_replaces_the_orientation_keeps_the_previous_one_and_can_be_undone(self):
        orientacion.update(self.gustavo,'Orientación de antes.')
        summary=self.summary()
        self.assertEqual(self.human.post(f'{self.URL}/{summary.id}/visto').json()['summary']['state'],'visto')
        self.assertEqual(self.api.post(f'{self.URL}/{summary.id}/aplicar').status_code,403)
        response=self.human.post(f'{self.URL}/{summary.id}/aplicar')
        self.assertEqual(response.status_code,200,response.content)
        body=response.json()
        self.assertEqual((body['summary']['state'],body['summary']['can_undo'],body['orientation']['text'],body['previous_orientation']),
                         ('aplicado',True,PROPOSAL,'Orientación de antes.'))
        self.assertEqual(orientacion.text(),PROPOSAL)
        self.assertTrue(AuditEvent.objects.filter(action='orientation.updated').exists())  # the orientation path, with its audit
        self.assertEqual(self.human.post(f'{self.URL}/{summary.id}/aplicar').status_code,409)
        undone=self.human.post(f'{self.URL}/{summary.id}/deshacer').json()
        self.assertEqual((undone['summary']['state'],undone['orientation']['text']),('visto','Orientación de antes.'))
        summary.refresh_from_db();self.assertEqual((summary.previous_orientation,summary.decided_at),('',None))

    def test_undo_refuses_when_the_orientation_changed_since(self):
        summary=self.summary()
        self.human.post(f'{self.URL}/{summary.id}/aplicar')
        self.human.put('/api/v1/orientacion',{'text':'La edité en Ajustes.'},format='json')
        response=self.human.post(f'{self.URL}/{summary.id}/deshacer')
        self.assertEqual(response.status_code,409);self.assertIn('Ajustes',response.json()['detail'])
        self.assertEqual(orientacion.text(),'La edité en Ajustes.')

    def test_discard_and_its_undo(self):
        summary=self.summary()
        self.assertEqual(self.human.post(f'{self.URL}/{summary.id}/descartar').json()['summary']['state'],'descartado')
        self.assertEqual(self.human.post(f'{self.URL}/{summary.id}/descartar').status_code,409)
        self.assertEqual(self.human.post(f'{self.URL}/{summary.id}/deshacer').json()['summary']['state'],'visto')
        self.assertEqual(self.human.post(f'{self.URL}/{summary.id}/deshacer').status_code,409)  # nothing left to undo
        without=self.summary(week=WEEK,analysis=analysis(orientacion_propuesta=None))
        self.assertEqual(self.human.post(f'{self.URL}/{without.id}/aplicar').status_code,409)
        self.assertEqual(self.human.post(f'{self.URL}/{uuid.uuid4()}/aplicar').status_code,404)


class CardAndNoticeTests(SummaryBase):
    def cards(self):
        data=self.human.get('/api/v1/tu-turno').json()
        return data,[c for c in data['items'] if c['type']=='resumen']

    def test_a_pending_orientation_proposal_is_a_cuando_puedas_card_until_decided(self):
        summary=self.summary()
        data,cards=self.cards()
        self.assertEqual(len(cards),1);card=cards[0]
        self.assertEqual((card['id'],card['priority'],card['agent'],card['agent_label'],card['title'],card['body'],card['state']),
                         (f'weekly_summary:{summary.id}','cuando_puedas','analista_barrio_resultados','Analista del barrio',
                          'El analista propone una orientación',PROPOSAL,'nueva'))
        self.assertEqual(card['actions'],[{'label':'Ver el resumen','href':'/resultados#resumen','primary':True},
                                          {'label':'Descartar','endpoint':f'/api/v1/resultados/resumen-semanal/{summary.id}/descartar'}])
        self.assertEqual(card['summary']['titular'],'Semana con 3 posts')
        self.assertEqual((data['tasks']['resumen'][0]['id'],data['counts']['tareas']),(card['id'],1))
        self.human.post('/api/v1/tu-turno/vistos',{'ids':[card['id']]},format='json')
        self.assertEqual(self.cards()[1][0]['state'],'vista')
        self.human.post(card['actions'][1]['endpoint'])
        self.assertEqual(self.cards()[1],[])

    def test_no_card_without_a_proposal_or_once_applied(self):
        self.summary(analysis=analysis(orientacion_propuesta=None))
        self.assertEqual(self.cards()[1],[])
        WeeklySummary.objects.all().delete()
        summary=self.summary()
        self.human.post(f'/api/v1/resultados/resumen-semanal/{summary.id}/aplicar')
        self.assertEqual(self.cards()[1],[])

    def test_the_notification_kind_pushes_by_default(self):
        self.assertEqual(notificaciones.FEED_KINDS['weekly_summary'],('tuyo',True,'Resumen de la semana listo'))
        self.assertTrue(notificaciones.push_enabled('weekly_summary'))
        self.assertIn('weekly_summary',[row['kind'] for row in notificaciones.push_types() if row['goes_to']=='notificaciones'])


class DirectorInputTests(SummaryBase):
    def test_the_latest_recent_recommendations_reach_the_director_unless_discarded(self):
        self.assertIsNone(resumen_semanal.for_director())
        summary=self.summary()
        week=resumen_semanal.last_week()
        self.assertEqual(resumen_semanal.for_director(),{'semana':{'desde':week.isoformat(),'hasta':(week+timedelta(days=6)).isoformat()},
                                                         'recomendaciones':['Repetir applied_ai: 3,5 % de interacción.']})
        WeeklySummary.objects.filter(pk=summary.pk).update(state='descartado')
        self.assertIsNone(resumen_semanal.for_director())
        WeeklySummary.objects.filter(pk=summary.pk).update(state='aplicado',week_start=week-timedelta(days=35))
        self.assertIsNone(resumen_semanal.for_director())  # too old to steer this week


class DirectorPayloadTests(EditorialAuditBase):
    def test_the_director_brief_carries_the_recommendations_as_input(self):
        WeeklySummary.objects.create(week_start=resumen_semanal.last_week(),analysis=analysis())
        self.plan_with(answers(decision='skip'))
        sent=self.message('director')
        self.assertEqual(sent['weekly_recommendations']['recomendaciones'],['Repetir applied_ai: 3,5 % de interacción.'])
        self.assertIn('weekly_recommendations',editorial.DIRECTOR_SYSTEM)
        self.assertIn('no una orientación',editorial.DIRECTOR_SYSTEM)

    def test_without_a_summary_the_field_is_null(self):
        self.plan_with(answers(decision='skip'))
        self.assertIsNone(self.message('director')['weekly_recommendations'])
