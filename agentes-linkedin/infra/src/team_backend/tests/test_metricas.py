"""Metrics and Resultados: own-post snapshots at 24 h/72 h/7 d, the daily audience, autopilot queueing and the endpoint.
No network and no spend: the fake Unipile connector stands in for LinkedIn, the Unipile contract runs on MockTransport
and the directo account answers with the hand-written LinkedIn fixtures (directo_fixtures.py) through its real parser."""
import os
import uuid
from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from unittest.mock import patch
import httpx
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.test import SimpleTestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient
from knowledge import db
from linkedin_directo import rutas
from team_backend import autopiloto, connectors_directo, jobs, metricas, operador
from team_backend.connectors import ConnectorError, FakeConnector, UnipileConnector, _post
from team_backend.models import (ActionExecution, ActionProposal, AudienceSnapshot, AuditEvent, ConnectorAccount, Contact, EditorialPiece,
                                 Job, PostMetric)
from team_backend.tests import directo_fixtures as F
from team_backend.tests.test_ids_linkedin import ACTIVITY, UGC, unipile_post
from team_backend.tests.test_operador import OperatorBase

TEXT_A='Before writing a line of code for a new feature, ask which decision it helps someone make.'
TEXT_B='An AI feature earns its place only when someone can check its output against an outcome.'
SUBSTANTIVE='The hard part is not the model, it is deciding which step of the sales workflow you automate first.'

class MetricsBase(OperatorBase):
    def setUp(self):
        super().setUp()
        env=patch.dict(os.environ,{'OPERATOR_TIMEZONE':'America/Bogota','METRICS_EVERY_MINUTES':'180','METRICS_READ_CAPS':'',
                                   'METRICS_PROFILE_VIEWS_DAYS':'14','METRICS_MAX_AGE_DAYS':'30','METRICS_POSTS_LIMIT':'20',
                                   'NETWORK_ENABLED':'false','OPERATOR_AUTONOMY':'CONT-09=off'})
        env.start();self.addCleanup(env.stop)
        self.bot,_=User.objects.get_or_create(username='barrio-autopiloto')
        self.grant(self.bot,'access_knowledge','run_agents','use_paid_providers','operate_linkedin','execute_actions')
        self.slots=0

    def today(self):
        return timezone.now().astimezone(operador.local_tz()).date()

    def publish(self,text,hours_ago,pillar='applied_ai',seed=True,slot=None,state='confirmed',wrote=True):
        """A CONT-09 publication confirmed `hours_ago` and, when seeded, the own post Unipile shows for it."""
        when=timezone.now()-timedelta(hours=hours_ago);self.slots+=1
        piece=EditorialPiece.objects.create(account=self.account,slot_date=slot or self.today()-timedelta(days=400+self.slots),scheduled_for=when,
                                            state='ready',final_text=text,brief={'pillar':pillar,'thesis':'Tesis '+text[:20]})
        proposal=ActionProposal.objects.create(account=self.account,piece=piece,capability='CONT-09',payload={'text':text},payload_hash='0'*64,state=state)
        ActionExecution.objects.create(proposal=proposal,idempotency_key=uuid.uuid4().hex,provider='linkedin_fake',state=state,executed_by=self.gustavo,
                                       started_at=when,external_url=f'https://www.linkedin.com/feed/update/urn:li:share:{self.slots}/',wrote=wrote)
        return piece,(self.fake.seed_own_post(text) if seed else None)

    def age(self,piece,hours):
        ActionExecution.objects.filter(proposal__piece=piece).update(started_at=timezone.now()-timedelta(hours=hours))

    def collect(self):
        jobs.enqueue_operation(self.bot,'collect_metrics',{'account':str(self.account.id)})
        while jobs.process_one(self.worker):pass
        return Job.objects.filter(kind='collect_metrics').order_by('-created_at').first()

    def last_summary(self):
        return AuditEvent.objects.filter(action='metrics.collected').order_by('-created_at').first().metadata


class PostSnapshotTests(MetricsBase):
    def test_each_age_is_captured_once_and_hidden_counters_stay_null(self):
        piece,pid=self.publish(TEXT_A,hours_ago=25)
        fresh,fresh_pid=self.publish(TEXT_B,hours_ago=2)
        self.fake.set_post_counters(pid,impressions=150,reactions=7,comments=0,reposts=None)  # LinkedIn hides the reposts
        self.fake.set_post_counters(fresh_pid,impressions=40,reactions=1,comments=0,reposts=0)
        job=self.collect()
        self.assertEqual((job.state,job.result_status,job.error),('complete','cortes:1 audiencia:creada',''))
        metric=PostMetric.objects.get()
        self.assertEqual((metric.piece_id,metric.kind,metric.provider_post_id,metric.impressions,metric.reactions),(piece.id,'24h',pid,150,7))
        self.assertEqual(metric.comments,0);self.assertIsNone(metric.reposts)  # an observed zero is zero; hidden is null
        self.assertGreaterEqual(metric.captured_at-metric.published_at,timedelta(hours=24))
        piece.refresh_from_db();fresh.refresh_from_db()
        # EditorialPiece.metrics keeps the latest values read (backwards compatible keys) for every recent publication.
        self.assertEqual((piece.metrics['impressions'],piece.metrics['reposts'],piece.metrics['source'],piece.metrics['unipile_post_id']),(150,None,'unipile',pid))
        self.assertEqual(fresh.metrics['impressions'],40);self.assertFalse(PostMetric.objects.filter(piece=fresh).exists())

        self.fake.set_post_counters(pid,impressions=300,reactions=9,comments=2,reposts=1)
        self.collect()  # nothing due: no read, and the 24 h snapshot is never captured again
        self.assertEqual(list(PostMetric.objects.values_list('kind','impressions')),[('24h',150)])
        self.assertEqual(metricas.reads_today(self.account,'posts'),1)

        self.age(piece,73);self.collect()
        self.age(piece,7*24+1);self.fake.set_post_counters(pid,impressions=480,reactions=12,comments=3,reposts=2);self.collect()
        self.collect()
        self.assertEqual({m.kind:(m.impressions,m.reactions,m.comments,m.reposts) for m in PostMetric.objects.filter(piece=piece)},
                         {'24h':(150,7,0,None),'72h':(300,9,2,1),'7d':(480,12,3,2)})
        self.assertEqual(self.fake.state['writes'],0)

    def test_who_commented_is_read_once_per_capture(self):
        piece,pid=self.publish(TEXT_A,hours_ago=8*24)  # late: the three ages share one comments read
        self.fake.set_post_counters(pid,impressions=500,reactions=9,comments=3,reposts=0)
        self.fake.seed_person('founder-ana','Ana Founder',comment_on=pid,comment=SUBSTANTIVE)
        self.fake.seed_person('saludo-bob','Bob Saludo',comment_on=pid,comment='Great post!')
        self.fake.state['comments'][pid].append({'id':'comment:own','text':'Thanks Ana, '+SUBSTANTIVE,'is_sender':True,
                                                 'created_at':'2026-11-06T15:00:00+00:00','author':{'id':'me','display_name':'Gustavo'}})
        Contact.objects.create(account=self.account,provider_user_id='ACofounder-ana',display_name='Ana Founder',source='commenter',stage='fit',
                               classification={'fit':True,'role':'comprador','modality':'projectapp'})
        self.collect()
        expected=[{'provider_user_id':'ACofounder-ana','name':'Ana Founder','substantive':True,'role':'comprador','fit':True},
                  {'provider_user_id':'ACosaludo-bob','name':'Bob Saludo','substantive':False,'role':None,'fit':None}]
        by_id=lambda commenters:sorted(commenters,key=lambda c:c['provider_user_id'])
        self.assertEqual([by_id(m.commenters) for m in PostMetric.objects.order_by('kind')],[expected]*3)  # Gustavo's own reply is left out
        self.assertEqual(metricas.reads_today(self.account,'comments'),1)
        # Bob is classified later: the piece detail shows today's role.
        Contact.objects.create(account=self.account,provider_user_id='ACosaludo-bob',display_name='Bob',source='commenter',stage='discarded',
                               classification={'fit':False,'role':'par'})
        detail=self.human.get(f'/api/v1/editorial/pieces/{piece.id}').json()
        self.assertEqual([(s['kind'],s['impressions'],s['engagement_pct']) for s in detail['snapshots']],[('24h',500,2.4),('72h',500,2.4),('7d',500,2.4)])
        self.assertEqual(sorted((c['name'],c['role'],c['fit']) for c in detail['commenters']),[('Ana Founder','comprador',True),('Bob Saludo','par',False)])
        with patch.object(FakeConnector,'list_comments',side_effect=ConnectorError('Simulado: HTTP 500.',status=500,kind='errors/internal')):
            other,other_pid=self.publish(TEXT_B,hours_ago=25);self.collect()
        self.assertIsNone(PostMetric.objects.get(piece=other).commenters)  # not read is null, never an empty list
        self.assertEqual(self.human.get(f'/api/v1/editorial/pieces/{other.id}').json()['commenters'],None)

    def test_late_snapshots_are_all_captured_and_a_known_id_outlives_edits_and_the_recent_list(self):
        old,old_pid=self.publish(TEXT_A,hours_ago=9*24)  # the collector was down: every age is due at once
        self.fake.set_post_counters(old_pid,impressions=900,reactions=30,comments=4,reposts=2)
        ghost,_=self.publish('A post Unipile never shows back.',hours_ago=30,seed=False)
        job=self.collect()
        self.assertEqual(job.result_status,'cortes:3 audiencia:creada')
        self.assertEqual(sorted(PostMetric.objects.filter(piece=old).values_list('kind',flat=True)),['24h','72h','7d'])
        self.assertTrue(all(m.captured_at-m.published_at>=timedelta(days=9) for m in PostMetric.objects.all()))  # lateness is visible
        self.assertFalse(PostMetric.objects.filter(piece=ghost).exists())
        # Visible: which publication, which cuts and why (no own post with its text, none dated near the write).
        self.assertEqual(self.last_summary()['pending'],[{'piece':str(ghost.id),'cuts':['24h'],'reason':'sin_coincidencia'}])

        other,other_pid=self.publish(TEXT_B,hours_ago=25)
        self.fake.set_post_counters(other_pid,impressions=100,reactions=1,comments=1,reposts=0)
        self.collect()  # matched by its exact text
        self.assertEqual(PostMetric.objects.get(piece=other).provider_post_id,other_pid)
        self.fake.state['posts'][other_pid]['text']='Edited on LinkedIn after publishing.'
        self.fake.set_post_counters(other_pid,impressions=250,reactions=3,comments=2,reposts=1)
        self.age(other,73)
        # Out of the recent list: found by its stored id in the longest list, whose counters carry the impressions.
        with patch.dict(os.environ,{'METRICS_POSTS_LIMIT':'1'}):self.collect()
        self.assertEqual(PostMetric.objects.get(piece=other,kind='72h').impressions,250)
        self.assertEqual((metricas.reads_today(self.account,'posts'),metricas.reads_today(self.account,'post')),(4,0))

    def test_an_evidence_failure_is_not_taken_for_an_already_captured_cut(self):
        piece,pid=self.publish(TEXT_A,hours_ago=25)
        with patch('team_backend.evidencia.ingest_metric',side_effect=IntegrityError('Simulado: evidencia rota.')), \
                self.assertRaisesRegex(IntegrityError,'evidencia rota'):
            metricas.collect(self.bot,self.account)
        self.assertFalse(PostMetric.objects.exists())  # undone with its evidence: still due, never silently lost
        metricas.collect(self.bot,self.account)
        self.assertEqual(list(PostMetric.objects.values_list('piece_id','kind')),[(piece.id,'24h')])
        # Only the very duplicate (a concurrent run captured the age first) counts as already captured.
        execution=ActionExecution.objects.get(proposal__piece=piece)
        self.assertEqual(metricas._capture(execution,['24h'],self.fake.get_post(pid),timezone.now()),0)

    def test_read_caps_and_which_publications_are_measured(self):
        piece,pid=self.publish(TEXT_A,hours_ago=25)
        sent,_=self.publish(TEXT_B,hours_ago=30,state='sent')  # a 201 not read back yet: published, as in the calendar
        for state,wrote in (('failed',False),('uncertain',True),('executing',True),('sent',False)):  # nothing published
            self.publish(f'Not measured: {state}, wrote={wrote}.',hours_ago=26,state=state,wrote=wrote)
        with patch.dict(os.environ,{'METRICS_READ_CAPS':'posts=0'}):job=self.collect()
        self.assertEqual(job.state,'complete');self.assertIn('Tope diario',job.error)
        self.assertFalse(PostMetric.objects.exists());self.assertTrue(AudienceSnapshot.objects.exists())  # the audience still ran
        self.assertEqual(sorted((p['piece'],p['reason']) for p in self.last_summary()['pending']),
                         sorted((str(p.id),'tope_de_lecturas') for p in (piece,sent)))
        self.collect()
        self.assertEqual(set(PostMetric.objects.values_list('piece_id',flat=True)),{piece.id,sent.id})


class AudienceTests(MetricsBase):
    def test_read_caps_and_reservations_use_the_supplied_local_day(self):
        late=datetime(2026,11,7,4,30,tzinfo=dt_timezone.utc)   # 6 Nov in Bogotá
        early=late+timedelta(hours=1)                       # 7 Nov in Bogotá
        # A different wall clock must not charge either collection to another day. Revisit the earlier day
        # after recording the later one: neither future reads nor a recomputed baseline may charge it twice.
        with patch('django.utils.timezone.now',return_value=early+timedelta(days=7)), \
                patch.dict(os.environ,{'METRICS_READ_CAPS':'profile=2','OPERATOR_PROFILE_READ_DAILY_LIMIT':'2'}):
            metricas._read(self.account,'profile',early)
            metricas._read(self.account,'profile',late)
            self.assertEqual(metricas.reads_today(self.account,'profile',late),1)
            self.assertEqual(metricas.reads_today(self.account,'profile',early),1)
            operador.reserve_profile_read(self.account,'preflight',late+timedelta(minutes=5))
            with self.assertRaisesRegex(metricas.ReadCapReached,'Tope compartido'):
                metricas._read(self.account,'profile',late+timedelta(minutes=20))
            metricas._read(self.account,'profile',early+timedelta(minutes=10))
            with self.assertRaisesRegex(metricas.ReadCapReached,'Tope diario'):
                metricas._read(self.account,'profile',early+timedelta(minutes=20))
        self.assertEqual(list(AuditEvent.objects.filter(action='metrics.read').order_by('created_at')
            .values_list('created_at',flat=True)),[late,early,early+timedelta(minutes=10)])
        self.assertEqual(list(AuditEvent.objects.filter(action='operator.profile_read').order_by('created_at')
            .values_list('created_at',flat=True)),[late,late+timedelta(minutes=5),early,early+timedelta(minutes=10)])
        baselines=AuditEvent.objects.filter(action='operator.profile_baseline').order_by('created_at')
        self.assertEqual(list(baselines.values_list('metadata',flat=True)),
            [{'day':'2026-11-06','used':0},{'day':'2026-11-07','used':0}])

    def test_read_caps_use_the_supplied_clock_and_preserve_each_local_day(self):
        before=datetime(2026,11,7,4,50,tzinfo=dt_timezone.utc)  # Nov 6 in Bogota
        after=datetime(2026,11,7,5,10,tzinfo=dt_timezone.utc)   # Nov 7 in Bogota
        with patch.dict(os.environ,{'METRICS_READ_CAPS':'profile=2','OPERATOR_PROFILE_READ_DAILY_LIMIT':'2'}), \
             patch('django.utils.timezone.now',return_value=after+timedelta(days=30)):
            metricas._read(self.account,'profile',now=before)
            metricas._read(self.account,'profile',now=after)
            # A later day's reservation cannot replace the earlier baseline or consume its remaining slot.
            metricas._read(self.account,'profile',now=before+timedelta(minutes=1))
            self.assertEqual(metricas.reads_today(self.account,'profile',before),2)
            self.assertEqual(metricas.reads_today(self.account,'profile',after),1)
            with self.assertRaises(metricas.ReadCapReached):
                metricas._read(self.account,'profile',now=before+timedelta(minutes=2))
            with self.assertRaises(operador.ProfileReadCapReached):
                operador.reserve_profile_read(self.account,'preflight',now=before+timedelta(minutes=2))
        expected={before,before+timedelta(minutes=1),after}
        for action in ('metrics.read','operator.profile_read'):
            rows=AuditEvent.objects.filter(action=action)
            self.assertEqual(rows.count(),3)
            self.assertEqual(set(rows.values_list('created_at',flat=True)),expected)
        baselines=list(AuditEvent.objects.filter(action='operator.profile_baseline').values_list('metadata',flat=True))
        self.assertEqual({b['day']:b['used'] for b in baselines},{'2026-11-06':0,'2026-11-07':0})
        self.assertEqual(len(baselines),2)

    def _collect_at(self,now):
        """Collect «at» a simulated time. The audit rows of this call get that time too, so the daily read caps count
        the simulated day, not the real date the suite runs on (it failed on 2026-11-09, the test's last day)."""
        from team_backend.models import AuditEvent
        before=set(AuditEvent.objects.values_list('pk',flat=True))
        try:return metricas.collect(self.bot,self.account,now=now)
        finally:AuditEvent.objects.exclude(pk__in=before).update(created_at=now)

    def test_one_snapshot_per_local_day(self):
        self.fake.seed_audience(followers=1200,connections=480,views=35)
        late=datetime(2026,11,7,4,30,tzinfo=dt_timezone.utc)   # 23:30 on 6 Nov in Bogotá
        early=datetime(2026,11,7,5,30,tzinfo=dt_timezone.utc)  # 00:30 on 7 Nov: same UTC date, new local day
        self.assertEqual(self._collect_at(late)['audience'],'creada')
        snapshot=AudienceSnapshot.objects.get()
        self.assertEqual((snapshot.day.isoformat(),snapshot.followers,snapshot.connections,snapshot.profile_views,snapshot.profile_views_days),
                         ('2026-11-06',1200,480,35,14))
        self.assertEqual(self._collect_at(late+timedelta(minutes=20))['audience'],'ya')
        self.fake.seed_audience(followers=1205)  # relations and profile views hidden this time
        self._collect_at(early)
        snapshot=AudienceSnapshot.objects.get(day='2026-11-07')
        self.assertEqual((snapshot.followers,snapshot.connections,snapshot.profile_views,snapshot.profile_views_days),(1205,None,None,None))
        self.assertEqual(AudienceSnapshot.objects.count(),2)

        refused=ConnectorError('Simulado: HTTP 403.',status=403,kind='errors/forbidden',pause=True)
        with patch.object(FakeConnector,'profile_views',side_effect=refused):
            summary=self._collect_at(early+timedelta(days=1))
        self.assertIn('403',summary['views_error']);self.assertEqual(AudienceSnapshot.objects.get(day='2026-11-08').followers,1205)
        self.account.refresh_from_db();self.assertFalse(self.account.paused)  # profile views are a bonus: never a pause

        expired=ConnectorError('Simulado: HTTP 401.',status=401,kind='provider/invalid_authorization',pause=True)
        with patch.object(FakeConnector,'own_audience',side_effect=expired),patch('team_backend.alerts.notify'):
            summary=self._collect_at(early+timedelta(days=2))
        self.assertIn('401',summary['stopped']);self.assertFalse(AudienceSnapshot.objects.filter(day='2026-11-09').exists())
        self.account.refresh_from_db();self.assertTrue(self.account.paused)


class AutopilotMetricsTests(MetricsBase):
    def test_queued_one_at_a_time_only_when_due_and_never_breaks_the_tick(self):
        official=operador.register_account(self.gustavo,'linkedin','urn:li:person:abc','LinkedIn oficial')
        every=180*60;t0=datetime.fromtimestamp(int(timezone.now().timestamp())//every*every+60,tz=dt_timezone.utc)  # start of a bucket
        report=autopiloto.tick(self.bot,now=t0)
        self.assertEqual(report['metrics'],1)  # no audience snapshot today
        job=Job.objects.get(kind='collect_metrics')
        self.assertEqual((job.params,job.execute,job.state),({'account':str(self.account.id)},False,'queued'))
        self.assertEqual(autopiloto.tick(self.bot,now=t0)['metrics'],0)  # one at a time
        while jobs.process_one(self.worker):pass
        self.assertEqual(Job.objects.get(kind='collect_metrics').state,'complete')
        # A new bucket, whose job id is unused: only due() keeps it from queueing. Its local day has its audience
        # snapshot whatever the wall clock's day was when the job ran.
        later=t0+timedelta(minutes=181)
        AudienceSnapshot.objects.get_or_create(day=metricas.local_day(later))
        self.assertFalse(metricas.due(later))
        self.assertEqual(autopiloto.tick(self.bot,now=later)['metrics'],0)  # nothing due: no job, no read
        self.assertEqual(Job.objects.filter(kind='collect_metrics').count(),1)
        self.publish(TEXT_A,hours_ago=28)
        self.assertEqual(autopiloto.tick(self.bot,now=t0+timedelta(minutes=5))['metrics'],0)  # same bucket: its id was already used
        self.assertEqual(autopiloto.tick(self.bot,now=later)['metrics'],1)  # the bucket nothing was due in queues now
        self.assertFalse(Job.objects.filter(kind='collect_metrics',params__account=str(official.id)).exists())  # only Unipile reads
        Job.objects.filter(kind='collect_metrics').delete()
        with patch.dict(os.environ,{'METRICS_EVERY_MINUTES':'0'}):self.assertEqual(autopiloto.tick(self.bot)['metrics'],0)
        with patch('team_backend.metricas.due',side_effect=RuntimeError('boom')):report=autopiloto.tick(self.bot)
        self.assertEqual(report['metrics_error'],'RuntimeError')
        self.assertIn('execute',report);self.assertIn('reconcile',report)  # the rest of the tick still ran


class DirectoMetricsTests(MetricsBase):
    """metricas on a directo account at a fixed clock: LinkedIn answers with the hand-written fixtures, read by the
    connector's real parser."""
    NOW=F.POSTED+timedelta(hours=25)  # the 24 h cut of a post written at F.POSTED is due
    LATER=F.POSTED+timedelta(days=8)  # every cut is due

    def setUp(self):
        super().setUp()
        self.directo=ConnectorAccount.objects.create(provider='directo',external_account_id='cuenta-prueba',label='Cuenta directa de prueba')

    def written(self,text,at,**execution):
        """A confirmed CONT-09 publication whose write started at `at`."""
        self.slots+=1
        piece=EditorialPiece.objects.create(account=self.directo,slot_date=self.today()-timedelta(days=400+self.slots),scheduled_for=at,
                                            state='ready',final_text=text,brief={'pillar':'applied_ai','thesis':'Tesis de prueba'})
        proposal=ActionProposal.objects.create(account=self.directo,piece=piece,capability='CONT-09',payload={'text':text},
                                               payload_hash='0'*64,state='confirmed')
        ActionExecution.objects.create(proposal=proposal,idempotency_key=uuid.uuid4().hex,provider='linkedin',state='confirmed',
                                       executed_by=self.gustavo,started_at=at,**execution)
        return piece

    def scanned(self,piece,post_id):
        """The id the replies scan found and kept for the piece (respuestas.read)."""
        AuditEvent.objects.create(action='replies.scanned',target=str(piece.id),metadata={'found':True,'post_id':post_id})

    def linkedin(self,recent,longest=(),views=37):
        """The account's LinkedIn: its own posts (F.posts rows; the longest list also has `longest`), get_post of
        F.POST, no comments, its top card and its profile views summary."""
        def own_posts(request):return F.ok(F.posts(*recent,*(longest if f'count={metricas.POSTS_MAX}&' in request.path else ())))
        return F.FakeTransport(('GET',r'^/voyager/api/me$',F.ok(F.me())),('GET',r'^/voyager/api/identity/profileUpdatesV2\?',own_posts),
                               ('GET',r'^/voyager/api/feed/updates\?q=highlightedFeed',F.ok(F.highlighted(F.POST))),
                               ('GET',r'^/voyager/api/feed/comments\?',F.ok(F.comments(F.POST,[]))),
                               ('GET',r'^/voyager/api/graphql\?includeWebMetadata=true&variables=\(vanityName:',F.ok(F.top_card(F.OWN,own=True))),
                               ('GET',r'^/voyager/api/identity/wvmpCards$',F.ok(F.profile_views(views))))

    def collect_at(self,transport,now=NOW,**env):
        with patch.object(connectors_directo,'TRANSPORT',transport),patch.dict(os.environ,env):
            return metricas.collect(self.bot,self.directo,now=now)

    def test_profile_views_are_asked_for_the_window_directo_answers(self):
        with patch.dict(os.environ):
            del os.environ['METRICS_PROFILE_VIEWS_DAYS']  # the default (28): not a window directo answers
            summary=self.collect_at(self.linkedin([]))
        snapshot=AudienceSnapshot.objects.get()
        self.assertEqual((snapshot.followers,snapshot.connections,snapshot.profile_views,snapshot.profile_views_days),(120,80,37,rutas.VIEWS_DAYS))
        self.assertNotIn('views_error',summary)
        # A summary card without the number: absent, and the run says so.
        next_day=self.NOW+timedelta(days=1)
        summary=self.collect_at(self.linkedin([],views=None),now=next_day)
        self.assertIsNone(AudienceSnapshot.objects.get(day=metricas.local_day(next_day)).profile_views)
        self.assertIn(f'{rutas.VIEWS_DAYS} días',summary['views_error'])

    def test_a_post_whose_text_changed_is_found_by_the_id_the_replies_scan_kept(self):
        piece=self.written(TEXT_A,F.POSTED-timedelta(hours=3))  # too far from the post's date for the time fallback
        self.scanned(piece,F.POST)
        summary=self.collect_at(self.linkedin([(F.POST,'Texto editado en LinkedIn después de publicar.',F.OWN,{'likes':4,'impressions':210})]))
        metric=PostMetric.objects.get(piece=piece)
        self.assertEqual((metric.kind,metric.provider_post_id,metric.share_url,metric.impressions,metric.reactions),
                         ('24h',F.POST,f'https://www.linkedin.com/feed/update/urn:li:activity:{F.POST}/',210,4))
        self.assertEqual(summary['pending'],[])

    def test_the_only_own_post_dated_near_the_write_is_that_publication(self):
        share='urn:li:share:7390000000000000001'  # the Posts API's urn: another kind than directo's activity, never converted
        piece=self.written(TEXT_A,F.POSTED-timedelta(minutes=6),external_id=share,external_url=f'https://www.linkedin.com/feed/update/{share}/')
        far=F.snowflake(F.POSTED-timedelta(hours=2),8)
        self.collect_at(self.linkedin([(F.POST,'El texto como LinkedIn lo muestra.',F.OWN,{'impressions':150}),
                                       (far,'Otro post propio de esa mañana.',F.OWN,{'impressions':90})]))
        metric=PostMetric.objects.get(piece=piece)
        self.assertEqual((metric.provider_post_id,metric.impressions),(F.POST,150))
        piece.refresh_from_db();self.assertEqual(piece.metrics['unipile_post_id'],F.POST)  # found once, known from now on

    def test_two_own_posts_dated_near_the_write_leave_it_pending(self):
        piece=self.written(TEXT_A,F.POSTED)
        summary=self.collect_at(self.linkedin([(F.POST,'Uno.',F.OWN,{}),(F.snowflake(F.POSTED+timedelta(minutes=12),9),'Dos.',F.OWN,{})]))
        self.assertFalse(PostMetric.objects.exists())
        self.assertEqual(summary['pending'],[{'piece':str(piece.id),'cuts':['24h'],'reason':'varias_candidatas'}])
        self.assertEqual(self.last_summary()['pending'],summary['pending'])  # in the metrics.collected audit too

    def test_a_post_another_publication_has_is_never_taken_by_the_time_fallback(self):
        first=self.written(TEXT_A,F.POSTED-timedelta(minutes=5));second=self.written(TEXT_B,F.POSTED+timedelta(minutes=5))
        summary=self.collect_at(self.linkedin([(F.POST,TEXT_A,F.OWN,{'impressions':40})]))  # the second never shows back
        self.assertEqual(list(PostMetric.objects.values_list('piece_id','provider_post_id')),[(first.id,F.POST)])
        self.assertEqual(summary['pending'],[{'piece':str(second.id),'cuts':['24h'],'reason':'sin_coincidencia'}])

    def test_a_late_cut_of_an_older_post_keeps_its_impressions_from_the_longest_list(self):
        piece=self.written(TEXT_A,F.POSTED);self.scanned(piece,F.POST)
        newer=[(F.snowflake(F.POSTED+timedelta(days=d),20+d),f'Post del día {d}.',F.OWN,{}) for d in (1,2)]
        summary=self.collect_at(self.linkedin(newer,longest=[(F.POST,TEXT_A,F.OWN,{'likes':30,'impressions':900})]),
                                now=self.LATER,METRICS_POSTS_LIMIT='2')
        self.assertEqual({m.kind:(m.impressions,m.reactions) for m in PostMetric.objects.filter(piece=piece)},
                         {'24h':(900,30),'72h':(900,30),'7d':(900,30)})
        self.assertEqual((metricas.reads_today(self.directo,'posts',self.LATER),metricas.reads_today(self.directo,'post',self.LATER)),(2,0))
        self.assertEqual((summary['pending'],summary['no_impressions']),([],[]))

    def test_a_post_read_alone_is_captured_without_impressions_and_says_why(self):
        piece=self.written(TEXT_A,F.POSTED);self.scanned(piece,F.POST)
        newer=[(F.snowflake(F.POSTED+timedelta(days=1),21),'Post del día siguiente.',F.OWN,{})]
        summary=self.collect_at(self.linkedin(newer),now=self.LATER,METRICS_POSTS_LIMIT='1')  # in no list: read by its id
        self.assertEqual({m.kind:(m.impressions,m.reactions) for m in PostMetric.objects.filter(piece=piece)},
                         {'24h':(None,4),'72h':(None,4),'7d':(None,4)})
        self.assertEqual(summary['no_impressions'],[{'piece':str(piece.id),'cuts':['24h','72h','7d'],'reason':'lectura_individual'}])
        self.assertEqual(metricas.reads_today(self.directo,'post',self.LATER),1)


class SamePostTests(SimpleTestCase):
    def test_post_ids_are_compared_like_with_like(self):
        unipile=unipile_post(f'activity:{ACTIVITY}',f'ugcPost:{UGC}')
        self.assertEqual(metricas._urns(unipile),{('activity',ACTIVITY),('ugcPost',UGC)})
        self.assertTrue(metricas._urns(f'urn:li:ugcPost:{UGC}')&metricas._urns(unipile))  # the Posts API's urn inside Unipile's id
        self.assertFalse(metricas._urns(f'urn:li:share:{UGC}')&metricas._urns(unipile))  # same number, another kind
        self.assertEqual(metricas._urns(F.POST,f'https://www.linkedin.com/feed/update/urn:li:activity:{F.POST}/'),{('activity',F.POST)})
        self.assertEqual(metricas._urns('activity:me-0','',None),set())  # the fake's ids name no urn


class UnipileMetricsContractTests(TransactionTestCase):
    def test_audience_profile_views_and_reposts_shapes(self):
        """Shapes confirmed against the real account on 2026-11-06 (fields only)."""
        seen=[]
        def handler(request):
            seen.append((request.url.path,dict(request.url.params)))
            if request.url.path.endswith('/users/me'):
                return httpx.Response(200,json={'object':'UserProfile','id':'ACoMe','display_name':'G','provider':'LINKEDIN','is_blocked':False,
                    'specifics':{'network_distance':'SELF'},'followers_count':1234,'relations_count':567})
            return httpx.Response(200,json={'object':'ProfileViews','entities':[],'analytics':{'object':'ProfileViewsAnalytics','views_count':42}})
        with patch.dict(os.environ,{'LIVE_LINKEDIN':'true'}):
            connector=UnipileConnector('acc_TEST1',api_key='k-test',transport=httpx.MockTransport(handler))
        self.assertEqual(connector.own_audience(),{'followers':1234,'connections':567})
        self.assertEqual(connector.profile_views(14),42)
        self.assertEqual(seen,[('/v2/acc_TEST1/users/me',{}),('/v2/acc_TEST1/linkedin/analytics/profile-views',{'date_range':'14','limit':'1'})])
        self.assertEqual(_post({'id':'p','reposts_counter':3})['reposts_counter'],3)
        self.assertIsNone(_post({'id':'p','reposts_counter':None})['reposts_counter'])


class ResultadosTests(MetricsBase):
    def setUp(self):
        super().setUp()
        env=patch.dict(os.environ,{'ANTHROPIC_LIMIT_USD':'2','OPENAI_LIMIT_USD':'1','EDITORIAL_DAILY_LLM_USD':'1','NETWORK_DAILY_LLM_USD':'0.3'})
        env.start();self.addCleanup(env.stop)

    def job_at(self,when):
        return Job.objects.create(owner=self.bot,request_hash='x',agent='operador',task='observe',kind='observe',state='complete',created_at=when)

    def contact(self,uid,**fields):
        return Contact.objects.create(account=self.account,provider_user_id=uid,display_name=uid,source=fields.pop('source','manual'),**fields)

    def executed(self,capability,when,post=None,contact=None):
        proposal=ActionProposal.objects.create(account=self.account,post=post,contact=contact,capability=capability,
                                               payload={'text':'x'} if post else {'user_id':contact.provider_user_id},payload_hash='1'*64,state='confirmed')
        ActionExecution.objects.create(proposal=proposal,idempotency_key=uuid.uuid4().hex,provider='fake',state='confirmed',executed_by=self.bot,started_at=when)

    def snapshot(self,piece,kind,impressions,reactions,comments,reposts,commenters=None):
        execution=ActionExecution.objects.get(proposal__piece=piece)
        PostMetric.objects.create(piece=piece,kind=kind,provider_post_id='p'+str(piece.id)[:6],impressions=impressions,reactions=reactions,comments=comments,
                                  reposts=reposts,commenters=commenters,published_at=execution.started_at,
                                  captured_at=execution.started_at+(timedelta(hours=25) if kind=='24h' else timedelta(days=7)))

    def spend(self,purpose,usd,when,provider='anthropic',status='complete'):
        with db.connect() as c:
            c.execute('INSERT INTO usage_ledger(id,provider,purpose,reserved_usd,actual_usd,status,created_at) VALUES(%s,%s,%s,%s,%s,%s,%s)',
                      (str(uuid.uuid4()),provider,purpose,Decimal(usd),Decimal(usd) if status=='complete' else None,status,when))

    def get(self,**params):
        response=self.human.get('/api/v1/resultados',params)
        self.assertEqual(response.status_code,200,response.content)
        return response.json()

    def seed(self):
        now=timezone.now();today=self.today();day=timedelta(days=1)
        self.first_job=self.job_at(now-14*day)  # the machine has been running since before the previous week
        for when in (now-14*day,now-day,now-9*day):
            self.job_at(when);AuditEvent.objects.create(action='network.synced',target=str(self.account.id),created_at=when)
        for offset,followers,connections,views in ((14,1000,400,20),(7,1010,405,25),(0,1030,412,31)):
            AudienceSnapshot.objects.create(day=today-timedelta(days=offset),followers=followers,connections=connections,profile_views=views,profile_views_days=28)
        fit=lambda role,modality='projectapp':{'fit':True,'role':role,'modality':modality}
        self.contact('in-1',source='incoming',stage='incoming',classification=fit('comprador'),discovered_at=now-day)
        self.contact('in-2',source='incoming',stage='incoming',classification={'fit':False,'role':'par','modality':'projectapp'},discovered_at=now-day)
        self.contact('in-3',source='incoming',stage='incoming',discovered_at=now-2*day)
        self.contact('in-4',source='incoming',stage='incoming',classification=fit('lider','personal_startups'),discovered_at=now-9*day)
        for uid,role,when in (('c-1','comprador',now-2*day),('c-2','comprador',now-3*day),('c-3','par',now-2*day),('c-4','comprador',now-10*day)):
            self.contact(uid,stage='connected',classification=fit(role),connected_at=when)
        self.contact('c-5',stage='connected',classification={'fit':False,'role':'par'},connected_at=now-day)
        event=lambda when,name:{'at':when.isoformat(),'event':name,'detail':''}
        # Invitations resolved this week: one connection, one closed; the week before: two connections.
        self.contact('i-1',stage='connected',invited_at=now-5*day,connected_at=now-day,history=[event(now-5*day,'invited'),event(now-day,'connected')])
        self.contact('i-2',stage='closed',invited_at=now-6*day,history=[event(now-6*day,'invited'),event(now-2*day,'closed')])
        self.contact('i-3',stage='invited',invited_at=now-3*day,history=[event(now-3*day,'invited')])
        self.contact('i-4',stage='connected',invited_at=now-12*day,connected_at=now-9*day,history=[event(now-9*day,'connected')])
        self.contact('i-5',stage='connected',invited_at=now-12*day,connected_at=now-8*day)  # history trimmed: connected_at settles it
        commenters=[{'provider_user_id':'c-1','name':'C1','substantive':True,'role':None,'fit':None},
                    {'provider_user_id':'x-9','name':'X9','substantive':False,'role':None,'fit':None}]
        self.p1,_=self.publish(TEXT_A+'\nSecond line.',hours_ago=48,slot=today-2*day,seed=False);self.snapshot(self.p1,'24h',300,10,5,0,commenters)
        self.p2,_=self.publish(TEXT_B,hours_ago=72,slot=today-3*day,seed=False);self.snapshot(self.p2,'24h',120,2,1,None)
        self.p0,_=self.publish('Previous week post.',hours_ago=240,pillar='business_to_product',slot=today-10*day,seed=False)
        self.snapshot(self.p0,'24h',200,4,2,0,[commenters[0]]);self.snapshot(self.p0,'7d',500,10,4,1,[commenters[0]])
        EditorialPiece.objects.create(account=self.account,slot_date=today-day,scheduled_for=now-day,state='skipped',note='Sin material')
        vetoed=EditorialPiece.objects.create(account=self.account,slot_date=today-4*day,scheduled_for=now-4*day,state='ready',final_text='Vetoed.')
        ActionProposal.objects.create(account=self.account,piece=vetoed,capability='CONT-09',payload={'text':'Vetoed.'},payload_hash='2'*64,state='rejected')
        self.executed('INT-03',now-day,post=self.observed()[0]);self.executed('RED-01',now-day,contact=Contact.objects.get(provider_user_id='c-1'))
        self.spend('propose-comment','0.05',now);self.spend('editorial-director','0.5',now);self.spend('network-classify','0.1',now,status='reserved')
        self.spend('editorial-director','0.2',now-40*day);self.spend('embeddings','0.05',now,provider='openai')
        return now,today,day

    def test_shape_and_comparison_with_the_previous_period(self):
        now,today,day=self.seed()
        body=self.get(dias='7')
        self.assertEqual(list(body),['periodo','modalidad','zona_horaria','negocio','audiencia','contenido','equipo'])
        period=body['periodo']
        self.assertEqual((period['desde'],period['hasta'],period['dias'],period['anterior']),
                         ((today-6*day).isoformat(),today.isoformat(),7,{'desde':(today-13*day).isoformat(),'hasta':(today-7*day).isoformat()}))
        self.assertTrue(period['datos_hasta'])
        kpi_keys={'value','previous','delta','delta_pct','comparable','series','definition','formula','unavailable_reason'}

        business=body['negocio']
        self.assertEqual((business['disponible'],business['motivo']),(False,'Mediremos oportunidades cuando registres la primera o conectemos el inbox'))
        self.assertLessEqual(kpi_keys,set(business['inbound']))
        self.assertEqual({k:business['inbound'][k] for k in ('value','previous','delta','delta_pct','comparable')},
                         {'value':1,'previous':1,'delta':0,'delta_pct':0.0,'comparable':True})

        reach=body['audiencia']
        followers=reach['followers']
        self.assertEqual((followers['value'],followers['previous'],followers['delta'],followers['delta_pct'],followers['comparable']),(1030,1010,20,2.0,True))
        self.assertEqual((followers['series'],followers['measured']),([{'date':today.isoformat(),'value':1030}],
                                                                      {'from':(today-7*day).isoformat(),'to':today.isoformat()}))
        self.assertEqual(reach['connections']['delta'],7)
        self.assertEqual((reach['profile_views']['value'],reach['profile_views']['delta'],reach['profile_views']['window_days']),(31,6,28))
        self.assertEqual((reach['new_fit_connections']['value'],reach['new_fit_connections']['previous'],reach['new_fit_connections']['delta_pct']),(3,1,200.0))
        roles={r['role']:r['value'] for r in reach['roles']['items']}
        self.assertEqual((roles['comprador'],roles['par'],roles['aliado']),(2,1,0))
        rate=reach['acceptance_rate']
        self.assertEqual((rate['value'],rate['previous'],rate['delta'],rate['numerator'],rate['denominator'],rate['formula']),
                         (50.0,100.0,-50.0,1,2,'conectados / (conectados + cerrados) × 100'))
        self.assertEqual((reach['funnel']['stages']['connected'],reach['funnel']['stages']['incoming'],reach['funnel']['stages']['closed']),(8,4,1))
        self.assertEqual(reach['funnel']['order'],['candidate','fit','followed','invited','connected'])
        self.assertEqual((reach['recurrent_people']['value'],reach['recurrent_people']['unavailable_reason']),
                         (None,'Aún no medimos las interacciones repetidas por persona.'))

        content=body['contenido'];kpis=content['kpis']
        median=kpis['median_impressions']  # this week's posts are not 7 days old: both periods are compared at 24 h
        self.assertEqual((median['value'],median['previous'],median['delta'],median['delta_pct'],median['cut'],median['posts_measured']),(210,200,10,5.0,'24h',2))
        self.assertIn('24 h',median['definition'])
        engagement=kpis['engagement_pct']
        self.assertEqual((engagement['value'],engagement['previous'],engagement['delta'],engagement['numerator'],engagement['denominator']),(5.0,3.0,2.0,15,300))
        self.assertEqual(engagement['formula'],'(reacciones + comentarios + republicaciones) / impresiones × 100')
        self.assertEqual((kpis['substantive_comments']['value'],kpis['substantive_comments']['previous']),(1,1))
        consistency=kpis['consistency']  # published 2 of 4 planned days (one skipped, one vetoed) against 1 of 1
        self.assertEqual((consistency['value'],consistency['previous'],consistency['numerator'],consistency['denominator']),(50.0,100.0,2,4))
        self.assertEqual(content['chart']['bars'],[{'piece_id':str(self.p2.id),'date':(today-3*day).isoformat(),'impressions':120,'cut':'24h','fallback':True},
                                                   {'piece_id':str(self.p1.id),'date':(today-2*day).isoformat(),'impressions':300,'cut':'24h','fallback':True}])
        self.assertEqual(content['chart']['median_previous_4_weeks'],{'7d':500,'24h':200})
        self.assertEqual(content['best_post'],{'piece_id':str(self.p1.id),'first_line':TEXT_A,'date':(today-2*day).isoformat(),'pillar':'applied_ai',
                                               'impressions':300,'engagement_pct':5.0,'cut':'24h'})
        pillars={p['pillar']:(p['value'],p['posts']) for p in content['by_pillar']['items']}
        self.assertEqual(pillars,{'business_to_product':(None,0),'applied_ai':(5.0,1),'architecture_delivery':(None,0)})  # hidden reposts: p2 left out
        self.assertEqual(content['by_type']['items'],[])  # posts from before the GASP strategy carry no type
        rows={r['piece_id']:r for r in content['posts']}
        first=rows[str(self.p1.id)]
        self.assertEqual((first['impressions_24h'],first['impressions_7d'],first['reactions'],first['comments'],first['reposts'],first['engagement_pct']),
                         (300,None,10,5,0,5.0))
        self.assertEqual(first['commenters_by_role'],{'comprador':1,'sin_clasificar':1})  # roles refreshed from today's contacts
        self.assertEqual((rows[str(self.p2.id)]['engagement_pct'],rows[str(self.p2.id)]['commenters_by_role']),(None,None))

        team=body['equipo']
        self.assertEqual((team['comments_published']['value'],team['comments_published']['previous'],team['comments_published']['delta_pct']),(1,0,None))
        self.assertEqual((team['comments_replied']['value'],team['comments_replied']['unavailable_reason']),(None,'Aún no leemos las respuestas a tus comentarios.'))
        self.assertEqual([team[k]['value'] for k in ('follows','invites','accepts','pieces_published','pieces_blocked','pieces_vetoed')],[1,0,0,2,0,1])
        self.assertEqual(team['pieces_published']['delta_pct'],100.0)
        spend=team['spend']
        # No per-area caps: the areas show their spend; the month carries the team's limit (every provider).
        self.assertEqual(spend['today'],{'general':{'spent':0.05,'budget':None},'editorial':{'spent':0.5,'budget':None},
                                         'network':{'spent':0.1,'budget':None},'other':{'spent':0.0,'budget':None}})
        self.assertEqual((spend['month']['total'],spend['accumulated']),({'spent':0.7,'budget':100.0},{'spent':0.85,'budget':2.0}))
        self.assertEqual(spend['other_providers']['openai']['month'],0.05)

        # Modality filter: sections 1 and 2 only.
        projectapp=self.get(dias='7',modalidad='projectapp')
        self.assertEqual((projectapp['negocio']['inbound']['value'],projectapp['negocio']['inbound']['previous']),(1,0))
        self.assertEqual(projectapp['audiencia']['funnel']['stages']['connected'],4)
        self.assertEqual(projectapp['contenido']['kpis']['median_impressions']['value'],210)
        self.assertEqual(self.get(dias='7',modalidad='personal_startups')['negocio']['inbound']['value'],0)
        # 28 days: last week's post has its 7 d snapshot, so posts are compared at 7 d; the period before has none.
        month=self.get()
        self.assertEqual((month['periodo']['dias'],month['periodo']['desde']),(28,(today-27*day).isoformat()))
        median=month['contenido']['kpis']['median_impressions']
        self.assertEqual((median['value'],median['previous'],median['comparable'],median['cut'],median['posts_measured'],median['posts_total']),
                         (500,None,False,'7d',1,3))
        # A previous period not fully covered by the machine has values but no variation.
        self.first_job.delete();Job.objects.filter(created_at__lt=now-13*day).delete()
        partial=self.get(dias='7')['equipo']['comments_published']
        self.assertEqual((partial['value'],partial['previous'],partial['comparable'],partial['delta']),(1,0,False,None))

    def test_parameters_and_permissions(self):
        for params in ({'dias':'30'},{'dias':'x'},{'modalidad':'alianzas'}):
            self.assertEqual(self.human.get('/api/v1/resultados',params).status_code,400)
        self.assertEqual(self.api.get('/api/v1/resultados').status_code,200)  # read-only: operate_linkedin is enough
        stranger=APIClient();stranger.force_login(User.objects.create_user('sin-permisos'))
        self.assertEqual(stranger.get('/api/v1/resultados').status_code,403)

    def test_without_data_every_metric_is_null_never_zero(self):
        body=self.get()
        self.assertEqual((body['periodo']['dias'],body['modalidad']),(28,'todo'))
        def null(card):return card['value'] is None and card['delta'] is None and not card['comparable'] and bool(card['unavailable_reason'])
        reach=body['audiencia'];content=body['contenido'];team=body['equipo']
        for card in (body['negocio']['inbound'],reach['followers'],reach['connections'],reach['profile_views'],reach['new_fit_connections'],
                     reach['acceptance_rate'],reach['recurrent_people'],*content['kpis'].values(),team['comments_published'],team['follows'],
                     team['pieces_published']):
            self.assertTrue(null(card),card)
        self.assertEqual(reach['acceptance_rate']['unavailable_reason'],'La red no funcionó en este periodo.')
        self.assertEqual(content['kpis']['median_impressions']['unavailable_reason'],'Sin posts publicados en el periodo.')
        self.assertEqual((reach['roles']['items'],content['chart']['bars'],content['best_post'],content['posts']),(None,[],None,[]))
        self.assertEqual(team['spend']['today']['general'],{'spent':0.0,'budget':None})  # the ledger records every paid call: an observed zero

        # One snapshot gives a total without growth; a machine that ran and did nothing reports a real zero.
        AudienceSnapshot.objects.create(day=self.today(),followers=1000)
        self.job_at(timezone.now())
        AuditEvent.objects.create(action='network.synced',target=str(self.account.id))
        body=self.get()
        followers=body['audiencia']['followers']
        self.assertEqual((followers['value'],followers['previous'],followers['delta'],followers['comparable']),(1000,None,None,False))
        self.assertEqual(body['equipo']['comments_published']['value'],0)
        rate=body['audiencia']['acceptance_rate']
        self.assertEqual((rate['value'],rate['denominator'],rate['unavailable_reason']),(None,0,'Ninguna invitación se resolvió en el periodo.'))


class BusinessSectionTests(OperatorBase):
    def test_opportunities_feed_the_business_section(self):
        from team_backend import oportunidades, resultados
        self.grant(self.gustavo,'approve_actions')
        empty=resultados.build('28')['negocio']
        self.assertFalse(empty['disponible'])
        a=oportunidades.create(self.gustavo,{'person_name':'Laura','modality':'projectapp'})
        oportunidades.update(self.gustavo,a.id,{'stage':'reunion'})
        oportunidades.create(self.gustavo,{'person_name':'Marta','modality':'personal_startups','stage':'acuerdo'})
        oportunidades.create(self.gustavo,{'person_name':'Pedro','modality':'por_clasificar'})
        business=resultados.build('28')['negocio']
        self.assertTrue(business['disponible'])
        self.assertEqual((business['abiertas']['value'],business['reuniones']['value'],business['acuerdos']['value']),(2,1,1))
        self.assertIsNone(business['conversaciones']['value']);self.assertIn('inbox',business['conversaciones']['unavailable_reason'])
        steps={s['stage']:s['count'] for s in business['embudo']['steps']}
        self.assertEqual((steps['conversacion'],steps['reunion'],steps['acuerdo']),(3,2,1))
        self.assertEqual(business['modalidades']['pct'],{'personal_startups':50.0,'projectapp':50.0})
        self.assertEqual({o['person'] for o in business['activas']},{'Laura','Pedro'})
        only=resultados.build('28',modalidad='projectapp')['negocio']
        self.assertEqual(only['abiertas']['value'],1)
