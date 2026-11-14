"""The daily canary of a `directo` account (docs/plan-linkedin-directo.md, «Prueba diaria»): the 14 reads checked
through the connector, what is kept (states, counts and names, never a value), the notices once per change, a stop that
pauses the account with what to do and one notice, the tries when it cannot run, the job and its autopilot guards. Every
LinkedIn answer is a hand-written fixture with invented values (directo_fixtures.py); nothing here reaches a network."""
import json
import os
import re
from datetime import datetime, time, timedelta, timezone as dt_timezone
from unittest.mock import patch
import httpx
from django.contrib.auth.models import Permission, User
from django.test import TestCase
from linkedin_directo import LinkedInError, Request, Transport, rutas
from linkedin_directo.servicio import ServiceTransport
from team_backend import analitica, autopiloto, canario, connectors_directo, jobs, operador
from team_backend.connectors_directo import DirectoConnector
from team_backend.models import AuditEvent, CanaryRun, ConnectorAccount, Job, Notification, Worker
from team_backend.serializers import AccountOutput
from team_backend.tests import directo_fixtures as F
from team_backend.tests.directo_fixtures import ANA, LUIS, OWN, POST, ok
from team_backend.tests.test_linkedin_directo import (COMMENTS, CONVERSATIONS, ME, MESSAGES, PROFILES, RECEIVED, SENT_AT, card,
                                                      sdui, search)
from team_backend.tests.test_metricas import MetricsBase

UTC=dt_timezone.utc
DAY=datetime(2026,11,13,tzinfo=UTC)
SERVICE={'LIVE_LINKEDIN_DIRECTO':'true','NAVEGADOR_URL':'http://navegador.interno:8080','NAVEGADOR_TOKEN':'token-ficticio',
         'LINKEDIN_CANARY_ENABLED':'true','LINKEDIN_CANARY_AFTER':'12:00','OPERATOR_PAUSED':'false'}
READS=['account_status','get_user','own_audience','profile_views','list_user_posts','get_post','list_comments',
       'list_comment_thread','search_people','search_parameters','list_invitations','list_sent_invitations','list_chats',
       'list_chat_messages']

def routes(views):
    """Every read of the canary, answered with the invented fixtures; `views` answers the profile views."""
    return [ME,PROFILES,card(OWN,own=True,followers=321,connections=210),
            ('GET',r'^/voyager/api/identity/wvmpCards$',views),
            ('GET',r'^/voyager/api/identity/profileUpdatesV2\?',ok(F.posts((POST,'Primer post',OWN,{'likes':5,'comments':2,'impressions':300})))),
            ('GET',r'^/voyager/api/feed/updates\?q=highlightedFeed',ok(F.highlighted(POST))),
            COMMENTS,search(),
            ('POST','^'+re.escape(rutas.sdui(rutas.FILTER_BAR,'component'))+'$',F.filter_bar()),
            sdui(rutas.GEO_TYPEAHEAD,F.typeahead([('900001','Ciudad Ficticia')])),
            RECEIVED,('GET',r'^/voyager/api/relationships/sentInvitationViewsV2\?',ok(F.invitations('sent',[('7000003',LUIS,SENT_AT,'Nota enviada')]))),
            CONVERSATIONS,MESSAGES]

def grant(user,*codes):
    user.user_permissions.add(*Permission.objects.filter(content_type__app_label='team_backend',codename__in=codes))

def service(status):
    return ServiceTransport('http://navegador.interno:8080/','token-ficticio','cuenta-prueba',
                            http_transport=httpx.MockTransport(lambda r:httpx.Response(status,json={'reason':'motivo corto'})))

class Refusing(Transport):
    """The service refusing before anything leaves (its budget, busy, unreachable)."""
    def __init__(self,error):self.error=error
    def send(self,request):raise self.error
    def live_query(self,prefixes,variables):return None


class CanaryBase(TestCase):
    def setUp(self):
        env=patch.dict(os.environ,SERVICE);env.start();self.addCleanup(env.stop)
        push=patch('team_backend.alerts.notify');self.push=push.start();self.addCleanup(push.stop)
        self.views=ok(F.profile_views(37))
        self.transport=F.FakeTransport(*routes(lambda request:self.views))
        fake=patch.object(connectors_directo,'TRANSPORT',self.transport);fake.start();self.addCleanup(fake.stop)
        self.account=ConnectorAccount.objects.create(provider='directo',external_account_id='cuenta-prueba',label='Cuenta directa de prueba')

    def at(self,days=0,hours=13):
        return DAY+timedelta(days=days,hours=hours)

    def notices(self):
        return Notification.objects.filter(kind='linkedin_canary')


class CanaryTests(CanaryBase):
    def test_the_14_reads_once_keeping_states_and_counts_never_values(self):
        log=canario.run(self.account,now=self.at())
        self.assertEqual((log.state,log.calls,log.error_kind,log.error),('ok',16,'',''))
        self.assertEqual([r['operacion'] for r in log.operations],READS)
        self.assertTrue(all(r['estado']=='ok' and r['filas']>=1 for r in log.operations if r['operacion']!='list_sent_invitations'))
        self.assertEqual(len(self.transport.sent),16);self.assertFalse(any(r.write for r in self.transport.sent))
        kept=json.dumps(log.operations)
        for value in (OWN[0],OWN[1],ANA[0],POST,'Primer post','Ana'):self.assertNotIn(value,kept)
        self.assertTrue(AuditEvent.objects.filter(action='linkedin.canary',target=str(self.account.id)).exists())
        self.assertFalse(self.notices().exists());self.push.assert_not_called()  # a first run that is fine says nothing
        self.assertFalse(canario.daily_due(self.account,self.at(hours=20)))  # one run a day once it judged LinkedIn
        self.assertTrue(canario.daily_due(self.account,self.at(days=1,hours=12)))
        shown=AccountOutput(self.account).data['canary']
        self.assertEqual({k:shown[k] for k in ('state','calls','failing','error_kind','error')},
                         {'state':'ok','calls':16,'failing':[],'error_kind':'','error':''})
        self.assertTrue(shown['started_at'] and shown['finished_at'])
        other=ConnectorAccount.objects.create(provider='fake',external_account_id='fake-prueba',label='Simulada')
        self.assertIsNone(AccountOutput(other).data['canary'])

    def test_a_field_gone_is_told_once_and_so_is_the_recovery(self):
        self.views=ok({'data':{},'included':[]})
        log=canario.run(self.account,now=self.at())
        self.assertEqual((log.state,canario.failing(log)),('roto',['profile_views']))
        [notice]=self.notices()
        self.assertEqual((notice.layer,notice.title),('sistema','La prueba diaria de LinkedIn encontró lecturas rotas'))
        self.assertIn('profile_views',notice.detail);self.assertEqual(self.push.call_count,1)
        self.assertEqual(AccountOutput(self.account).data['canary']['failing'],['profile_views'])
        canario.run(self.account,now=self.at(days=1))
        self.assertEqual(self.notices().count(),1)  # still broken: nothing new
        self.views=ok(F.profile_views(37))
        self.assertEqual(canario.run(self.account,now=self.at(days=2)).state,'ok')
        self.assertEqual((self.notices().count(),self.notices().first().title),(2,'La prueba diaria de LinkedIn vuelve a pasar'))
        canario.run(self.account,now=self.at(days=3))
        self.assertEqual(self.notices().count(),2)
        self.account.refresh_from_db();self.assertFalse(self.account.paused)  # a broken read never pauses

    def test_an_answer_too_changed_to_read_is_broken_not_a_crash(self):
        log=canario.run(self.account,now=self.at(),connector=DirectoConnector('cuenta-prueba',transport=Refusing(TypeError('x'))))
        self.assertEqual(log.state,'roto')
        self.assertEqual(log.operations[0],{'operacion':'account_status','estado':'roto','motivo':'respuesta ilegible (TypeError)'})
        self.assertIn('sin_probar',[r['estado'] for r in log.operations])  # what needed an earlier answer is not tried

    def test_a_stop_pauses_the_account_with_what_to_do_and_one_notice(self):
        log=canario.run(self.account,now=self.at(),connector=DirectoConnector('cuenta-prueba',transport=service(423)))
        self.assertEqual((log.state,log.calls,log.error_kind),('alto',1,'login'))
        self.account.refresh_from_db();self.assertTrue(self.account.paused)
        self.assertTrue(self.account.paused_reason.startswith('La prueba diaria de LinkedIn se detuvo: Servicio navegador: HTTP 423'))
        self.assertIn('python -m navegador login cuenta-prueba',self.account.paused_reason)
        self.assertNotIn('token-ficticio',self.account.paused_reason)
        self.assertFalse(self.notices().exists())  # the pause's own notice says it
        [call]=self.push.call_args_list
        self.assertEqual(call.args[0],'LinkedIn: cuenta en pausa')
        # A job already queued that hits the same stop updates the reason without a second notice.
        operador.set_account_pause(self.account,'Red detenida por el proveedor: la misma parada')
        self.assertEqual(self.push.call_count,1)
        self.account.refresh_from_db();self.assertEqual(self.account.paused_reason,'Red detenida por el proveedor: la misma parada')
        self.assertEqual(AuditEvent.objects.filter(action='operator.account_paused').count(),2)
        self.assertIsNone(canario.run(self.account,now=self.at(days=1)))  # nothing is read while paused
        self.assertFalse(canario.daily_due(self.account,self.at(days=1)))
        ConnectorAccount.objects.filter(pk=self.account.pk).update(paused=False,paused_reason='')  # Gustavo resumes it
        operador.set_account_pause(self.account,'Otra parada más tarde')
        self.assertEqual(self.push.call_count,2)  # a new pause after a resume is told again
        ConnectorAccount.objects.filter(pk=self.account.pk).update(paused=False,paused_reason='');self.account.refresh_from_db()
        self.assertEqual(canario.run(self.account,now=self.at(days=2)).state,'ok')
        self.assertEqual(self.notices().first().title,'La prueba diaria de LinkedIn vuelve a pasar')

    def test_the_service_stop_says_what_the_owner_has_to_do(self):
        read=Request('GET','/voyager/api/me','voyager',operation='account_status')
        for status,command in ((409,'python -m navegador reanudar cuenta-prueba'),(423,'python -m navegador login cuenta-prueba')):
            with self.subTest(status=status),self.assertRaises(LinkedInError) as e:service(status).send(read)
            self.assertIn(command,str(e.exception));self.assertTrue(str(e.exception).endswith('en Barrio.'))
            self.assertTrue(e.exception.pause)
        with self.assertRaises(LinkedInError) as e:service(503).send(read)
        self.assertNotIn('python -m navegador',str(e.exception))  # busy: nothing to do by hand

    def test_when_it_cannot_run_it_tries_again_and_tells_only_after_the_last_try(self):
        spent=DirectoConnector('cuenta-prueba',transport=Refusing(LinkedInError(
            'Servicio navegador: presupuesto de la cuenta agotado en account_status (tope de lecturas por hora agotado; no '
            'salió nada); vuelve a haber cupo en 10 min.',kind='budget',status=422,retry_after=600)))
        self.assertFalse(canario.daily_due(self.account,self.at(hours=11)+timedelta(minutes=59)))
        self.assertTrue(canario.daily_due(self.account,self.at(hours=12)))
        for attempt,hour in enumerate((12,13,14),1):
            log=canario.run(self.account,now=self.at(hours=hour),connector=spent)
            self.assertEqual((log.state,log.calls,log.error_kind),('no_corrio',1,'budget'))
            self.assertEqual(self.notices().count(),int(attempt==canario.TRIES))
            self.assertFalse(canario.daily_due(self.account,self.at(hours=hour)+timedelta(minutes=59)))  # an hour apart
        self.assertFalse(canario.daily_due(self.account,self.at(hours=23)))  # three a day at most
        notice=self.notices().get()
        self.assertEqual(notice.title,'La prueba diaria de LinkedIn no pudo correr hoy');self.assertIn('presupuesto',notice.detail)
        self.account.refresh_from_db();self.assertFalse(self.account.paused)  # LinkedIn was not reached: nothing to pause
        self.assertTrue(canario.daily_due(self.account,self.at(days=1,hours=12)))
        for hour in (12,13,14):canario.run(self.account,now=self.at(days=1,hours=hour),connector=spent)
        self.assertEqual(self.notices().count(),1)  # the same the next day: once per change
        self.assertEqual(canario.run(self.account,now=self.at(days=2)).state,'ok')
        self.assertEqual(self.notices().count(),2)

    def test_another_internet_exit_is_told_at_once_and_never_pauses(self):
        body={'reason':'la salida a internet cambió; no salió nada','code':'egress','since':'2026-11-13T11:00:00+00:00'}
        refused=DirectoConnector('cuenta-prueba',transport=ServiceTransport(
            'http://navegador.interno:8080/','token-ficticio','cuenta-prueba',
            http_transport=httpx.MockTransport(lambda r:httpx.Response(503,json=body))))
        log=canario.run(self.account,now=self.at(hours=12),connector=refused)
        self.assertEqual((log.state,log.calls,log.error_kind),('no_corrio',1,'egress'))
        self.assertIn('python -m navegador salida cuenta-prueba --aceptar',log.error)
        [notice]=Notification.objects.filter(kind='navegador_salida')
        self.assertIn('python -m navegador salida cuenta-prueba --aceptar',notice.detail)
        self.assertFalse(self.notices().exists())  # the canary's own notice still waits for the day's last try
        canario.run(self.account,now=self.at(hours=13),connector=refused)
        self.assertEqual(Notification.objects.filter(kind='navegador_salida').count(),1)  # the same episode
        self.account.refresh_from_db();self.assertFalse(self.account.paused)

    def test_only_the_last_runs_stay_and_the_latest_shown_is_a_finished_one(self):
        for n in range(canario.KEEP+3):
            CanaryRun.objects.create(account=self.account,state='ok',started_at=self.at(days=n-40),finished_at=self.at(days=n-40))
        log=canario.run(self.account,now=self.at())
        self.assertEqual((self.account.canary_runs.count(),self.account.canary_runs.first()),(canario.KEEP,log))
        self.assertFalse(self.account.canary_runs.filter(started_at__lt=self.at(days=-36)).exists())
        CanaryRun.objects.create(account=self.account,started_at=self.at(hours=14))  # one in course
        self.assertEqual(canario.latest(self.account)['started_at'],log.started_at)
        self.assertFalse(canario.daily_due(self.account,self.at(hours=20)))

    def test_off_without_the_service_its_switch_or_for_other_providers(self):
        at=self.at(hours=12)
        for env in ({'LIVE_LINKEDIN_DIRECTO':'false'},{'NAVEGADOR_URL':' '},{'NAVEGADOR_TOKEN':''},{'LINKEDIN_CANARY_ENABLED':'false'}):
            with self.subTest(env=env),patch.dict(os.environ,env):self.assertFalse(canario.daily_due(self.account,at))
        with patch.dict(os.environ,{'LINKEDIN_CANARY_AFTER':'15:30'}):
            self.assertFalse(canario.daily_due(self.account,self.at(hours=15)+timedelta(minutes=29)))
            self.assertTrue(canario.daily_due(self.account,self.at(hours=15)+timedelta(minutes=30)))
        other=ConnectorAccount.objects.create(provider='unipile',external_account_id='acc_prueba',label='Unipile')
        self.assertFalse(canario.daily_due(other,at))
        with self.assertRaises(ValueError):canario.run(other,now=at)
        self.assertTrue(canario.daily_due(self.account,at))

    def test_the_job_runs_it_and_says_how_it_went(self):
        bot=User.objects.create_user('autopiloto-prueba');grant(bot,'operate_linkedin')
        worker=Worker.objects.create()
        jobs.enqueue_operation(bot,'check_linkedin',{'account':str(self.account.id)})
        jobs.process_one(worker)
        job=Job.objects.get(kind='check_linkedin')
        self.assertEqual((job.state,job.result_status,job.error),('complete','prueba:ok llamadas:16',''))
        ConnectorAccount.objects.filter(pk=self.account.pk).update(paused=True)
        paused,_=jobs.enqueue_operation(bot,'check_linkedin',{'account':str(self.account.id)})
        jobs.process_one(worker);paused.refresh_from_db()
        self.assertEqual((paused.state,paused.result_status),('failed','blocked'))
        self.assertEqual(CanaryRun.objects.count(),1)


class AutopilotCanaryTests(MetricsBase):
    def test_queued_once_a_day_again_an_hour_later_if_it_did_not_run_and_never_breaks_the_tick(self):
        env=patch.dict(os.environ,SERVICE);env.start();self.addCleanup(env.stop)
        directo=ConnectorAccount.objects.create(provider='directo',external_account_id='cuenta-prueba',label='Cuenta directa de prueba',
                                                paused=True)
        midnight=datetime.combine(analitica.utc_today(),time(0),tzinfo=UTC)
        early,late=midnight+timedelta(hours=11,minutes=59),midnight+timedelta(hours=12,minutes=1)
        self.assertEqual(autopiloto.tick(self.bot,now=late)['canary'],0)  # a paused account is not even looked at
        ConnectorAccount.objects.filter(pk=directo.pk).update(paused=False);directo.refresh_from_db()
        self.assertEqual(autopiloto.tick(self.bot,now=early)['canary'],0)
        self.assertEqual(autopiloto.tick(self.bot,now=late)['canary'],1)
        job=Job.objects.get(kind='check_linkedin')
        self.assertEqual((job.id,job.params,job.execute,job.state),
                         (autopiloto._job_id('canary',directo.id,midnight.date(),0),{'account':str(directo.id)},False,'queued'))
        self.assertEqual(autopiloto.tick(self.bot,now=late)['canary'],0)  # already queued
        # It could not run (the service was busy): another try an hour later, with its own job.
        Job.objects.filter(kind='check_linkedin').update(state='failed')
        CanaryRun.objects.create(account=directo,state='no_corrio',started_at=late,finished_at=late)
        self.assertEqual(autopiloto.tick(self.bot,now=late+timedelta(minutes=30))['canary'],0)
        self.assertEqual(autopiloto.tick(self.bot,now=late+timedelta(hours=1))['canary'],1)
        self.assertTrue(Job.objects.filter(id=autopiloto._job_id('canary',directo.id,midnight.date(),1)).exists())
        Job.objects.filter(kind='check_linkedin').update(state='complete')
        CanaryRun.objects.create(account=directo,state='ok',started_at=late+timedelta(hours=1),finished_at=late+timedelta(hours=1))
        self.assertEqual(autopiloto.tick(self.bot,now=late+timedelta(hours=5))['canary'],0)  # it judged LinkedIn: done today
        self.assertFalse(Job.objects.filter(kind='check_linkedin',params__account=str(self.account.id)).exists())  # only directo
        with patch('team_backend.canario.daily_due',side_effect=RuntimeError('boom')):report=autopiloto.tick(self.bot,now=late)
        self.assertEqual(report['canary_error'],'RuntimeError')
        self.assertIn('execute',report);self.assertIn('reconcile',report)  # the rest of the tick still ran
        with patch.dict(os.environ,{'OPERATOR_PAUSED':'true'}):report=autopiloto.tick(self.bot,now=late)
        self.assertNotIn('canary',report)
        with patch.dict(os.environ,{'LINKEDIN_CANARY_ENABLED':'false'}):
            self.assertEqual(autopiloto._canary(self.bot,directo,late+timedelta(days=1)),0)
        self.assertEqual(autopiloto._canary(self.bot,directo,late+timedelta(days=1)),1)  # the next day
