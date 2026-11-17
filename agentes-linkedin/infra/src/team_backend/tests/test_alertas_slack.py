"""Slack alerts (alertas_slack, 16/11/2026). Slack is an httpx.MockTransport: nothing leaves the machine. The webhook
URLs below are placeholders of a reserved test domain, never real ones."""
import json
import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
import httpx
from knowledge import db, providers
from team_backend import alertas_slack, autopiloto, operador
from team_backend.models import ActionExecution, ActionProposal, AuditEvent, Contact, Conversation, Job, PostComment, Worker
from team_backend.tests.test_ventana_lectura import WindowBase, at

ALERTS='https://hooks.slack.test/services/ALERTAS'
SUMMARY='https://hooks.slack.test/services/RESUMEN'


class SlackBase(WindowBase):
    def setUp(self):
        super().setUp()
        env=patch.dict('os.environ',{'SLACK_WEBHOOK_URL':ALERTS,'SLACK_WEBHOOK_RESUMEN':'','SLACK_DAILY_SUMMARY':'true',
                                     'ALERT_CAP_THRESHOLD':'0.8','ALERT_REPLY_PENDING_HOURS':'4','ALERT_READS_GAP_HOURS':'3'})
        env.start();self.addCleanup(env.stop)
        self.sent=[];self.answer=200
        def slack(request):
            if self.answer=='down':raise httpx.ConnectError('down')
            self.sent.append((str(request.url),json.loads(request.content)))
            return httpx.Response(self.answer)
        transport=patch.object(alertas_slack,'TRANSPORT',httpx.MockTransport(slack));transport.start();self.addCleanup(transport.stop)
        alertas_slack._watched_at=None

    def watch(self,now):
        return alertas_slack.vigilar(now,force=True)

    def texts(self,url=ALERTS):
        return [body['text'] for to,body in self.sent if to==url]

    def reads(self,count,now,action='replies.read',kind='comments',target=None):
        AuditEvent.objects.bulk_create([AuditEvent(action=action,target=target or str(self.account.id),metadata={'kind':kind},
                                                   created_at=now) for _ in range(count)])

    def no_url_recorded(self):
        for metadata in AuditEvent.objects.values_list('metadata',flat=True):
            self.assertNotIn('hooks.slack.test',json.dumps(metadata))


class NotifierTests(SlackBase):
    def test_without_webhooks_nothing_is_sent_nor_recorded(self):
        with patch.dict('os.environ',{'SLACK_WEBHOOK_URL':'','SLACK_WEBHOOK_RESUMEN':''}):
            self.assertFalse(alertas_slack.send('prueba','texto',at(10)))
            self.reads(100,at(10))
            self.assertEqual(self.watch(at(10)),0)
        self.assertEqual((self.sent,AuditEvent.objects.filter(action__startswith='slack.').count()),([],0))

    def test_an_alert_goes_once_a_day_or_once_ever(self):
        self.assertTrue(alertas_slack.send('prueba','Texto corto',at(10)))
        self.assertFalse(alertas_slack.send('prueba','Texto corto',at(20)))
        self.assertTrue(alertas_slack.send('prueba','Texto corto',at(10,0,1)))
        self.assertTrue(alertas_slack.send('una-vez','Una vez',at(10),once='ever'))
        self.assertFalse(alertas_slack.send('una-vez','Una vez',at(10,0,3),once='ever'))
        self.assertEqual(self.sent,[(ALERTS,{'text':'Texto corto'}),(ALERTS,{'text':'Texto corto'}),(ALERTS,{'text':'Una vez'})])
        self.no_url_recorded()

    def test_a_slack_failure_is_recorded_without_the_url_and_never_raises(self):
        for answer,detail in ((500,{'http_status':500}),('down',{'error_type':'ConnectError'})):
            self.answer=answer
            with self.assertLogs('team_backend.alertas_slack','WARNING') as logs:
                self.assertTrue(alertas_slack.send(f'falla-{answer}','Texto',at(10)))
            self.assertNotIn('hooks.slack.test','\n'.join(logs.output))
            failed=AuditEvent.objects.get(action='slack.alert_failed',target=f'falla-{answer}')
            self.assertEqual({k:failed.metadata[k] for k in detail},detail)
        self.no_url_recorded()

    def test_summaries_go_to_their_channel_or_to_the_alerts_one(self):
        alertas_slack.send('r1','Resumen',at(10),channel='resumen')
        with patch.dict('os.environ',{'SLACK_WEBHOOK_RESUMEN':SUMMARY}):alertas_slack.send('r2','Resumen',at(10),channel='resumen')
        self.assertEqual([to for to,_ in self.sent],[ALERTS,SUMMARY])
        with patch.dict('os.environ',{'SLACK_WEBHOOK_URL':'','SLACK_WEBHOOK_RESUMEN':SUMMARY}):
            self.assertFalse(alertas_slack.send('a1','Alerta',at(10)))  # alerts have no channel of their own

    def test_a_broken_watcher_does_not_silence_the_others(self):
        def broken(now):raise RuntimeError('roto')
        def fine(now):return [alertas_slack.Aviso('bien','Funciona')]
        with patch.object(alertas_slack,'WATCHERS',[broken,fine]):
            self.assertEqual(self.watch(at(10)),1)
        self.assertEqual(self.texts(),['Funciona'])

    def test_the_tick_watches_at_most_every_five_minutes(self):
        with patch.object(alertas_slack,'WATCHERS',[lambda now:[alertas_slack.Aviso(f'k{now:%H%M}','x')]]):
            self.assertEqual(alertas_slack.vigilar(at(10)),1)
            self.assertEqual(alertas_slack.vigilar(at(10,3)),0)
            self.assertEqual(alertas_slack.vigilar(at(10,6)),1)


class CapAlertTests(SlackBase):
    def test_a_read_cap_warns_at_80_and_when_spent_once_a_day_each(self):
        self.reads(79,at(10))
        self.watch(at(10));self.assertEqual(self.texts(),[])
        self.reads(1,at(11))
        self.watch(at(11));self.watch(at(12))
        self.assertEqual(len(self.texts()),1)
        self.assertIn('respuestas.comments) va en 80/100 a las 11:00',self.texts()[0])
        self.assertIn('REPLIES_READ_CAPS=comments=N',self.texts()[0])
        self.reads(20,at(15))
        self.watch(at(15));self.watch(at(16))
        self.assertEqual(len(self.texts()),2)
        self.assertIn('Cupo de lecturas agotado',self.texts()[1])
        self.assertIn('100/100 a las 15:00',self.texts()[1])
        self.assertIn('no se leen comentarios nuevos en tus posts',self.texts()[1])
        # The next day starts over.
        self.reads(80,at(10,0,1));self.watch(at(10,0,1))
        self.assertEqual(len(self.texts()),3)
        keys=list(AuditEvent.objects.filter(action='slack.alert').order_by('created_at').values_list('target',flat=True))
        self.assertEqual(keys,['cupo:respuestas.comments:80','cupo:respuestas.comments:agotado','cupo:respuestas.comments:80'])

    def test_every_read_cap_is_watched_including_the_shared_profile_reads(self):
        self.reads(48,at(10),action='network.read',kind='comments')  # 48 of 60
        self.reads(64,at(10),action='operator.profile_read',kind='profile',target='member')
        self.reads(20,at(10),action='inbox.read',kind='chats')
        self.watch(at(10))
        keys=set(AuditEvent.objects.filter(action='slack.alert').values_list('target',flat=True))
        self.assertTrue({'cupo:red.comments:80','cupo:perfiles.profile:80','cupo:bandeja.chats:80'}<=keys,keys)
        self.assertTrue(any('perfiles.profile' in t and '64/80' in t for t in self.texts()))

    def test_a_spent_daily_write_cap(self):
        with patch.dict('os.environ',{'OPERATOR_DAILY_LIMITS':'RED-01=1'}):
            contact=Contact.objects.create(account=self.account,provider_user_id='u-9',display_name='Persona',source='manual')
            proposal=ActionProposal.objects.create(account=self.account,contact=contact,capability='RED-01',payload={},payload_hash='1'*64,
                                                   state='confirmed')
            ActionExecution.objects.create(proposal=proposal,idempotency_key=uuid.uuid4().hex,provider='linkedin_fake',state='confirmed',
                                           executed_by=self.gustavo,started_at=at(9),wrote=True)
            self.post_at(at(8,30),'El post del día llena su cupo de 1 cada día: no es una alerta.')
            self.watch(at(10));self.watch(at(11))
        texts=[t for t in self.texts() if 'escrituras' in t]
        self.assertEqual(len(texts),1)
        self.assertIn('Seguir a una persona (RED-01) llegó a 1/1 a las 10:00',texts[0])

    def test_slack_down_never_stops_the_tick_nor_the_reads(self):
        self.answer='down'
        self.post_at(at(6),'Post de hoy.')
        self.reads(90,at(9))
        with patch('django.utils.timezone.now',return_value=at(10)):
            report=autopiloto.tick(self.bot,now=at(10))
        self.assertEqual(report['replies'],1)  # the read was queued all the same
        self.assertTrue(Job.objects.filter(kind='read_own_comments').exists())
        self.assertTrue(AuditEvent.objects.filter(action='slack.alert_failed').exists())


class PauseAlertTests(SlackBase):
    def test_a_paused_account_alerts_once_per_pause(self):
        operador.set_account_pause(self.account,'Sesión de LinkedIn cerrada: vuelve a iniciar sesión en el navegador.')
        operador.set_account_pause(self.account,'Sesión de LinkedIn cerrada: vuelve a iniciar sesión en el navegador.')
        self.watch(at(10));self.watch(at(10,0,1))
        self.assertEqual(len(self.texts()),1)
        self.assertIn('Sesión de LinkedIn cerrada: «Cuenta simulada» está en pausa',self.texts()[0])
        operador.set_paused(self.gustavo,self.account,False)
        self.watch(at(11,0,1));self.assertEqual(len(self.texts()),1)
        operador.set_account_pause(self.account,'El proveedor limitó la cuenta.')
        self.watch(at(12,0,1))
        self.assertEqual(len(self.texts()),2)
        self.assertIn('Cuenta de LinkedIn en pausa',self.texts()[1])

    def test_the_invitation_ramp_paused(self):
        operador._audit(None,'network.ramp','member',stage=0,pause_until=at(10,0,3).isoformat(),reason='aceptación baja')
        self.watch(at(10));self.watch(at(10,0,1))
        self.assertEqual(len(self.texts()),1)
        self.assertIn('Invitaciones en pausa hasta el 07/11 a las 10:00',self.texts()[0])
        self.watch(at(11,0,3))  # the pause is over: nothing to say
        self.assertEqual(len(self.texts()),1)


class ProviderAlertTests(SlackBase):
    def test_a_refused_key_alerts_once_a_day(self):
        self.assertIn(alertas_slack.provider_refused,providers.CREDENTIAL_LISTENERS)  # apps.ready
        for status in (401,401,500):
            rid=providers.reserve('openai','embeddings',Decimal('0.001'))
            with patch('knowledge.providers.post',return_value=httpx.Response(status)):
                with self.assertRaises(ValueError):providers.request('openai','https://api.openai.test/v1/x',{},rid,{})
        self.assertEqual(len(self.texts()),1)
        self.assertIn('OpenAI rechazó la credencial (HTTP 401)',self.texts()[0])
        self.assertIn('OPENAI_API_KEY',self.texts()[0])
        providers.credentials_refused('typesafe',403);providers.credentials_refused('anthropic',429)
        self.assertEqual(len(self.texts()),2)
        self.assertIn('TypeSafe',self.texts()[1])

    def test_a_listener_failure_never_breaks_the_call(self):
        with patch.object(providers,'CREDENTIAL_LISTENERS',[lambda p,s:1/0]):providers.credentials_refused('openai',401)


class ReplyPendingTests(SlackBase):
    def row(self,piece,when,text='¿Cómo decides qué evals escribir primero cuando el producto cambia cada semana?',**fields):
        fields={'decision':{'turn':1},'observed_at':when,**fields}
        return PostComment.objects.create(account=self.account,piece=piece,provider_post_id='p',provider_comment_id=uuid.uuid4().hex,
                                          author_name='Ana Pérez',text=text,commented_at=when,**fields)

    def pending(self):
        return [t for t in self.texts() if 'Comentario sin responder' in t]

    def test_a_comment_waiting_more_than_four_window_hours_alerts_once(self):
        piece,_=self.post_at(at(8,0,-1),'Los agentes fallan en producción porque nadie es dueño de las evaluaciones del sistema.')
        night=self.row(piece,at(20,0,-1))
        waiting=self.row(piece,at(9))
        self.row(piece,at(11))  # 3 h by 14:00: not yet
        self.watch(at(9,30))  # 13 h 30 since last night's comment, only 3 h 30 of them inside the window
        self.assertEqual(self.pending(),[])
        self.watch(at(10,5))
        self.assertEqual(len(self.pending()),1)
        self.assertIn('Ana Pérez comentó hace 14 h 05 min',self.pending()[0])
        self.watch(at(13,30));self.watch(at(14))
        self.assertEqual(len(self.pending()),2)
        text=self.pending()[1]
        self.assertIn('Ana Pérez comentó hace 4 h 30 min en tu post «Los agentes fallan en producción porque nadie es…»',text)
        self.assertIn('«¿Cómo decides qué evals escribir primero cuando el producto cambia cada semana?»',text)
        self.assertIn('Atascado en: sin borrador todavía (espera su turno de redacción).',text)
        self.assertEqual(list(AuditEvent.objects.filter(action='slack.alert',target__startswith='respuesta:').order_by('created_at')
                              .values_list('target',flat=True)),[f'respuesta:pendiente:{night.id}',f'respuesta:pendiente:{waiting.id}'])

    def test_the_stage_where_it_is_held(self):
        piece,_=self.post_at(at(8),'Post.')
        discarded=self.row(piece,at(8,30),state='reply')
        ActionProposal.objects.create(account=self.account,comment=discarded,capability='INT-04',payload={'text':'r'},payload_hash='2'*64,
                                      state='discarded',review={'decision':'discard'})
        approved=self.row(piece,at(8,30),state='reply')
        ActionProposal.objects.create(account=self.account,comment=approved,capability='INT-04',payload={'text':'r2'},payload_hash='3'*64,
                                      state='approved')
        self.row(piece,at(8,30),state='asked')
        answered=self.row(piece,at(8,30),state='reply')
        ActionProposal.objects.create(account=self.account,comment=answered,capability='INT-04',payload={'text':'r3'},payload_hash='4'*64,
                                      state='confirmed')
        self.row(piece,at(8,30),text='¡Felicitaciones, gran post!',decision={})  # not judged yet: a reaction is enough
        self.row(piece,at(8,30),state='ignored')
        self.watch(at(14))
        stages=sorted(t.split('Atascado en: ')[1] for t in self.pending())
        self.assertEqual(stages,['aprobado, sin publicar todavía (espera turno de escritura).','descartado por el líder.',
                                 'espera a que respondas la pregunta del equipo en Tu turno.'])


class ReadsStalledTests(SlackBase):
    def stalled(self):
        return [t for t in self.texts() if 'No se están leyendo' in t]

    def test_no_reads_for_three_window_hours_while_a_post_waits_alerts_once_with_the_reason(self):
        piece,_=self.post_at(at(6),'Post de hoy.')
        self.reads(1,at(7))
        AuditEvent.objects.create(action='replies.scanned',target=str(piece.id),metadata={'found':True,'new':0},created_at=at(7))
        Job.objects.create(owner=self.bot,request_hash='h',agent='operador',task='read_own_comments',kind='read_own_comments',
                           params={'account':str(self.account.id)},created_at=at(9))
        self.watch(at(9,30))  # 2 h 30 without reads: not yet
        self.assertEqual(self.stalled(),[])
        self.watch(at(10,30));self.watch(at(12))
        self.assertEqual(len(self.stalled()),1)
        self.assertIn('No se están leyendo los comentarios de tus posts desde las 07:00: la lectura está en cola desde las 09:00',self.stalled()[0])
        self.assertIn('revisa que el worker esté corriendo',self.stalled()[0])

    def test_quiet_posts_and_closed_window_say_nothing(self):
        piece,_=self.post_at(at(9,0,-4),'Post viejo.')  # read every 12 h
        self.reads(1,at(7))
        AuditEvent.objects.create(action='replies.scanned',target=str(piece.id),metadata={'found':True,'new':0},created_at=at(7))
        self.watch(at(12))
        self.watch(at(22))  # outside the window
        self.assertEqual(self.stalled(),[])

    def test_the_spent_cap_is_the_reason(self):
        self.post_at(at(6),'Post de hoy.')
        self.reads(100,at(6,59))  # spent before the window (an app read at dawn)
        self.watch(at(11))
        reasons=self.stalled()
        self.assertEqual(len(reasons),1)
        self.assertIn('se agotó el cupo diario de lecturas (100/100; REPLIES_READ_CAPS)',reasons[0])


class SummaryTests(SlackBase):
    def test_the_daily_summary_goes_once_at_the_close_of_the_window(self):
        self.reads(3,at(9))
        with patch.dict('os.environ',{'SLACK_WEBHOOK_RESUMEN':SUMMARY}):
            self.watch(at(20,55))
            self.assertEqual(self.texts(SUMMARY),[])
            self.watch(at(21));self.watch(at(22))
        self.assertEqual(len(self.texts(SUMMARY)),1)
        text=self.texts(SUMMARY)[0]
        self.assertIn('Resumen del 04/11 al cierre de la ventana (21:00)',text)
        self.assertIn('• Lecturas respuestas.comments: 3/100',text)
        self.assertIn('• Lecturas perfiles.profile: 0/80',text)
        self.assertIn('• Escrituras INT-04',text)
        self.assertIn('por hora: 09 h 3',text)

    def test_the_summary_can_be_turned_off(self):
        with patch.dict('os.environ',{'SLACK_DAILY_SUMMARY':'false'}):self.watch(at(21,30))
        self.assertEqual(self.texts(),[])


class UrgentAlertTests(SlackBase):
    def with_word(self,word):
        return [t for t in self.texts() if word in t]

    def job(self,kind,created,**fields):
        return Job.objects.create(owner=self.bot,request_hash=uuid.uuid4().hex,agent='operador',task=kind,kind=kind,
                                  created_at=created,**fields)

    def test_a_lane_whose_worker_takes_nothing(self):
        Worker.objects.update(last_seen=at(8))
        self.job('read_inbox',at(9,50))
        self.job('observe',at(9),state='complete',started_at=at(9,40),finished_at=at(9,41))
        self.watch(at(10))
        self.assertEqual(self.with_word('worker'),[])  # 10 min: not yet
        self.watch(at(10,30));self.watch(at(11))
        texts=self.with_word('El worker')
        self.assertEqual(len(texts),1)
        self.assertIn('El worker de «general» (lecturas, borradores, piezas y lo demás) no está procesando: no da señales de vida. '
                      '1 trabajo(s) en cola sin empezar, el más viejo («read_inbox») desde las 09:50',texts[0])

    def test_a_lane_that_moves_or_a_long_job_is_told_apart(self):
        self.job('read_inbox',at(9))
        self.job('observe',at(9),state='complete',started_at=at(9,55),finished_at=at(9,58))
        self.job('execute_action',at(9,10))
        self.job('reconcile_action',at(8),state='running',started_at=at(8,5))
        self.watch(at(10))
        texts=self.with_word('El worker')
        self.assertEqual(len(texts),1)  # «general» started a job 5 min ago: it moves
        self.assertIn('El worker de «acciones» (las escrituras en LinkedIn y su conciliación) no está procesando: sigue con '
                      '«reconcile_action» desde las 08:05',texts[0])

    def test_an_uncertain_write_alerts_once(self):
        contact=Contact.objects.create(account=self.account,provider_user_id='u-7',display_name='P',source='manual')
        proposal=ActionProposal.objects.create(account=self.account,contact=contact,capability='RED-01',payload={},payload_hash='5'*64,
                                               state='uncertain')
        ActionExecution.objects.create(proposal=proposal,idempotency_key=uuid.uuid4().hex,provider='linkedin_fake',state='uncertain',
                                       executed_by=self.gustavo,started_at=at(9))
        self.watch(at(10));self.watch(at(10,0,1))
        texts=self.with_word('¿Salió o no?')
        self.assertEqual(texts,['Barrio · ¿Salió o no? Seguir a una persona (RED-01) de las 09:00: LinkedIn no confirmó si se aplicó y '
                                'no se repite sola. Compruébalo en LinkedIn y respóndelo en Tu turno («¿Salió o no?»).'])

    def test_the_navegador_not_sending_and_another_exit(self):
        for minute in (0,10):
            AuditEvent.objects.create(action=operador.WRITE_DEFERRED,target=str(self.account.id),
                                      metadata={'kind':'not_sent','capability':'RED-01'},created_at=at(9,minute))
        AuditEvent.objects.create(action=operador.WRITE_DEFERRED,target=str(self.account.id),metadata={'kind':'budget'},created_at=at(9,5))
        self.watch(at(9,30))
        self.assertEqual(self.with_word('navegador'),[])  # two in an hour: a busy browser, not an outage
        AuditEvent.objects.create(action=operador.WRITE_DEFERRED,target=str(self.account.id),metadata={'kind':'not_sent'},created_at=at(9,20))
        AuditEvent.objects.create(action='navegador.egress_refused',target=str(self.account.id),metadata={'since':'x'},created_at=at(9,25))
        self.watch(at(9,40));self.watch(at(9,50))
        texts=self.with_word('navegador')
        self.assertEqual(len(texts),2)
        self.assertIn('3 escrituras aplazadas sin salir desde las 09:00',texts[0])
        self.assertIn('no abre «Cuenta simulada» por otra salida a internet (desde las 09:25)',texts[1])


class MoneyAlertTests(SlackBase):
    def spend(self,amount,when):
        with db.connect() as c:
            c.execute("INSERT INTO usage_ledger(id,provider,purpose,reserved_usd,actual_usd,status,usage,created_at) "
                      "VALUES(%s,'anthropic','prueba',%s,%s,'complete','{}',%s)",(str(uuid.uuid4()),amount,amount,when))

    def test_the_month_spend_at_80_and_spent_once_each(self):
        with patch.dict('os.environ',{'AI_MONTHLY_LIMIT_USD':'100','AI_DAILY_FUSE_USD':'1000'}):
            self.spend(79,at(9))
            self.watch(at(10));self.assertEqual(self.texts(),[])
            self.spend(2,at(10))
            self.watch(at(11));self.watch(at(11,0,1))
            self.spend(20,at(12,0,1))
            self.watch(at(13,0,1));self.watch(at(14,0,2))
        texts=[t for t in self.texts() if ' IA ' in t]
        self.assertEqual(len(texts),2)
        self.assertIn('Gasto de IA del mes al 80 %: 81,00 de 100,00 USD (AI_MONTHLY_LIMIT_USD)',texts[0])
        self.assertIn('Tope mensual de IA agotado: 101,00 de 100,00 USD',texts[1])

    def test_low_acceptance_once_per_sample(self):
        health={'rate':0.3,'mature':20,'accepted':6,'sample_key':'a'*64}
        operador._audit(None,'network.ramp','member',stage=1,pause_until=None,health=health)
        self.watch(at(10));self.watch(at(10,0,1))
        texts=[t for t in self.texts() if 'Aceptación' in t]
        self.assertEqual(len(texts),1)
        self.assertIn('Aceptación de invitaciones baja: 6 de 20 (30%), bajo el 40% (OPERATOR_INVITE_ACCEPTANCE_MIN)',texts[0])
        operador._audit(None,'network.ramp','member',stage=1,pause_until=None,health=dict(health,mature=10,sample_key='b'*64))
        operador._audit(None,'network.ramp','member',stage=1,pause_until=None,health=dict(health,rate=0.45,sample_key='c'*64))
        self.watch(at(10,0,2))  # too few mature invitations, then a healthy rate: nothing to say
        self.assertEqual(len([t for t in self.texts() if 'Aceptación' in t]),1)


class GustavoAlertTests(SlackBase):
    def test_a_suggested_message_and_a_conversation_once_each_without_the_message_text(self):
        piece,_=self.post_at(at(8,0,-1),'Post de ayer sobre evaluaciones en producción.')
        row=PostComment.objects.create(account=self.account,piece=piece,provider_post_id='p',provider_comment_id='c1',author_name='Ana',
                                       text='x',commented_at=at(9),observed_at=at(9),state='reply',decision={'turn':2,'dm_opener':'Hola Ana'})
        with patch('team_backend.respuestas._dm_rows',return_value=[row]):
            self.watch(at(10));self.watch(at(11))
        conversation=Conversation.objects.create(account=self.account,provider_chat_id='chat-1',attendee_name='Luis',last_message_at=at(9),
            messages=[{'id':'m1','at':at(9).isoformat(),'from_me':False,'text':'Texto privado del mensaje'}],
            assessment={'message_id':'m1','awaiting_reply':True,'answers':{'espera':0.74}})
        self.watch(at(12));self.watch(at(13))
        Conversation.objects.filter(pk=conversation.pk).update(closed_message_id='m1')  # he closed it
        self.watch(at(14))
        texts=self.texts()
        self.assertEqual([t for t in texts if 'Mensaje sugerido' in t],
                         ['Barrio · Mensaje sugerido listo: Ana conversó contigo en tu post «Post de ayer sobre evaluaciones en producción.» '
                          'y ya es contacto. El primer mensaje está redactado en Tu turno para que lo envíes tú desde LinkedIn.'])
        self.assertEqual([t for t in texts if 'Luis' in t],
                         ['Barrio · Luis te escribió por LinkedIn: Espera tu respuesta (74 %). Está en Tu turno; el equipo no responde mensajes.'])
        self.assertNotIn('Texto privado',' '.join(texts))

    def test_proposals_about_to_expire_go_together_once_a_day(self):
        with patch.dict('os.environ',{'OPERATOR_AUTONOMY':'RED-01=approval,RED-04=auto','OPERATOR_PROPOSAL_TTL_HOURS':'48'}):
            for n,(capability,hours) in enumerate((('RED-01',40),('RED-01',45),('RED-01',10),('RED-04',45))):
                contact=Contact.objects.create(account=self.account,provider_user_id=f'u-{n}',display_name='P',source='manual')
                ActionProposal.objects.create(account=self.account,contact=contact,capability=capability,payload={},payload_hash=f'{n}'*64,
                                              state='proposed',created_at=at(12)-timedelta(hours=hours))
            self.watch(at(12));self.watch(at(14))
        texts=[t for t in self.texts() if 'caducan' in t]
        self.assertEqual(texts,['Barrio · 2 propuesta(s) esperan tu aprobación y caducan en menos de 12 h (2 × Seguir a una persona); '
                                'la primera caduca a las 15:00. Apruébalas o recházalas en Tu turno; si no, caducan sin salir.'])
