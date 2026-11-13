import hashlib
import os
import uuid
from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth.models import User, Permission
from django.core.cache import cache
from django.core.management import call_command
from django.db import connection
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient
from knowledge import db, memory
from team_backend import jobs
from team_backend.models import ApiCredential, Job, Worker, AuditEvent, SourceEvidence

class BackendTests(TransactionTestCase):
    def setUp(self):
        # The service layer opens independent connections: use a real isolated DB,
        # never a TestCase transaction or the production database.
        assert connection.settings_dict['NAME'].startswith('test_')
        cache.clear()
        self.live = patch.dict(os.environ, {'LIVE_PROVIDERS':'false'})
        self.live.start(); self.addCleanup(self.live.stop)
        self.network = patch('httpx.post', side_effect=AssertionError('Paid network forbidden in migration tests'))
        self.network.start(); self.addCleanup(self.network.stop)
        with db.connect() as c:
            c.execute('TRUNCATE memory,runs,usage_ledger,embedding_cache,unit_evidence,edges,chunks,units,source_files,evidence,unit_revisions CASCADE')
            c.execute("INSERT INTO source_files(path,sha256) VALUES('fixture','abc')")
            c.execute('''INSERT INTO units(id,session,title,original,sha256,source_path,pointer,metadata)
                VALUES('LI-01-M001-K01',1,'Titular comprador','{"title":"Titular comprador"}','abc','fixture','/units/0','{}')''')
            c.execute("INSERT INTO chunks(id,unit_id,section,text,sha256,tokens) VALUES('chunk','LI-01-M001-K01','title','Titular comprador','abc',3)")
            c.execute('INSERT INTO evidence(key,session,original) VALUES(%s,1,%s)',('01:test','{"text":"a\\u0000b"}'))
        self.user=User.objects.create_user('operator',password='test-password-local')
        self.grant(self.user,'access_knowledge','run_agents','propose_memory')
        self.token='local-test-token'
        self.credential=ApiCredential.objects.create(name='Test',user=self.user,digest=hashlib.sha256(self.token.encode()).hexdigest())
        self.client=APIClient(); self.client.credentials(HTTP_AUTHORIZATION='Bearer '+self.token)
        self.task={'agent':'perfil','task':'Titular comprador','execute':False,'mode':'lexical','request_id':str(uuid.uuid4())}

    def grant(self,user,*codes):
        user.user_permissions.add(*Permission.objects.filter(content_type__app_label='team_backend',codename__in=codes))
        for attr in ['_perm_cache','_user_perm_cache','_group_perm_cache']:
            if hasattr(user,attr):delattr(user,attr)

    def test_health_reports_the_deployed_revision(self):
        """The OTA workflow waits until /health reports a commit that holds the app's backend changes."""
        anon=APIClient()
        with patch.dict(os.environ,{'BARRIO_REVISION':'5800ca08e67eb9a8930ad798c84a76931072aca2'}):
            body=anon.get('/health').json()
        self.assertEqual(body,{'status':'ok','framework':'django','revision':'5800ca08e67eb9a8930ad798c84a76931072aca2'})
        with patch.dict(os.environ):
            os.environ.pop('BARRIO_REVISION',None)
            self.assertEqual(anon.get('/health').json()['revision'],'')

    def test_authentication_matrix_and_revocation(self):
        """Anonymous, unauthorized and revoked credentials must not expose knowledge."""
        anon=APIClient()
        self.assertEqual(anon.get('/health').status_code,200)
        self.assertEqual(anon.get('/api/v1/units').status_code,401)
        outsider=User.objects.create_user('outsider')
        anon.force_authenticate(outsider)
        self.assertEqual(anon.get('/api/v1/units').status_code,403)
        self.assertEqual(self.client.get('/api/v1/units').status_code,200)
        self.credential.revoked=True; self.credential.save()
        self.assertEqual(self.client.get('/api/v1/units').status_code,401)

    def test_expired_token_and_disabled_user(self):
        """Expiry and account suspension remain effective without restarting the API."""
        self.credential.expires_at=timezone.now()-timedelta(seconds=1);self.credential.save()
        self.assertEqual(self.client.get('/api/v1/units').status_code,401)
        self.credential.expires_at=None;self.credential.save()
        self.user.is_active=False;self.user.save()
        self.assertEqual(self.client.get('/api/v1/units').status_code,401)

    def test_read_original_json_and_search(self):
        """Adopted JSON evidence retains escaped NUL; retrieval shares the existing corpus."""
        self.assertEqual(SourceEvidence.objects.get(pk='01:test').original['text'],'a\x00b')
        self.assertEqual(self.client.get('/api/v1/sources/01:test').json()['text'],'a\x00b')
        result=self.client.post('/api/v1/search',{'query':'titular'},format='json')
        self.assertEqual(result.status_code,200)
        self.assertEqual(result.json()['results'][0]['id'],'LI-01-M001-K01')
        self.assertEqual(self.client.get('/api/v1/units/LI-07-V001-K01').status_code,404)

    def test_lists_bounded_and_no_original_blob(self):
        """Large page_size cannot return unbounded units or full original blobs."""
        with db.connect() as c:
            c.execute("INSERT INTO units SELECT 'test-'||i,1,'Test','{}','x','fixture','/','{}',true FROM generate_series(1,120) i")
        result=self.client.get('/api/v1/units?page_size=999').json()
        self.assertEqual(len(result['results']),100)
        self.assertEqual(result['count'],121)
        self.assertNotIn('original',result['results'][0])
        self.assertIsNotNone(result['next'])

    def test_enqueue_idempotency_and_conflict(self):
        """Re-sending the same request must not queue or charge twice."""
        first=self.client.post('/api/v1/runs',self.task,format='json')
        second=self.client.post('/api/v1/runs',self.task,format='json')
        self.assertEqual((first.status_code,second.status_code),(202,200))
        changed=dict(self.task,task='Different')
        self.assertEqual(self.client.post('/api/v1/runs',changed,format='json').status_code,409)
        self.assertEqual(Job.objects.count(),1)
        self.assertEqual(AuditEvent.objects.filter(action='job.enqueued').count(),1)
        self.assertEqual(db.status()['runs'],0)
        self.assertFalse(db.status()['usage'])

    def test_jobs_owner_isolation_and_cancel(self):
        """Other operators cannot inspect, reuse or cancel another owner's job."""
        response=self.client.post('/api/v1/runs',self.task,format='json');jid=response.json()['id']
        other=User.objects.create_user('other');self.grant(other,'access_knowledge','run_agents')
        client=APIClient();client.force_authenticate(other)
        self.assertEqual(client.get('/api/v1/runs/'+jid).status_code,404)
        self.assertEqual(client.post('/api/v1/runs/'+jid+'/cancel').status_code,404)
        self.assertEqual(client.post('/api/v1/runs',self.task,format='json').status_code,404)
        self.assertEqual(client.get('/api/v1/runs').json()['count'],0)
        self.assertEqual(self.client.post('/api/v1/runs/'+jid+'/cancel').json()['status'],'cancelled')
        self.assertEqual(self.client.post('/api/v1/runs/'+jid+'/cancel').status_code,409)

    def test_paid_permission_checked_before_enqueue(self):
        """A read/preview operator cannot activate Claude or query embeddings."""
        for changed in [dict(self.task,execute=True),dict(self.task,mode='hybrid')]:
            self.assertEqual(self.client.post('/api/v1/runs',changed,format='json').status_code,403)
        self.assertEqual(self.client.post('/api/v1/search',{'query':'titular','mode':'hybrid'},format='json').status_code,403)
        self.assertEqual(Job.objects.count(),0)

    def test_worker_executes_preview_once(self):
        """Actual service execution produces context without any provider calls."""
        jid=self.client.post('/api/v1/runs',self.task,format='json').json()['id']
        worker=Worker.objects.create()
        self.assertEqual(str(jobs.process_one(worker)),jid)
        self.assertIsNone(jobs.process_one(worker))
        result=self.client.get('/api/v1/runs/'+jid).json()
        self.assertEqual(result['status'],'complete')
        self.assertEqual(result['result']['status'],'preview')
        self.assertEqual(db.status()['runs'],1)
        self.assertFalse(db.status()['usage'])

    def test_worker_rechecks_revoked_permissions(self):
        """Permissions removed after enqueue prevent pending work from executing."""
        jid=self.client.post('/api/v1/runs',self.task,format='json').json()['id']
        self.user.user_permissions.clear()
        jobs.process_one(Worker.objects.create())
        self.assertEqual(Job.objects.get(pk=jid).state,'failed')
        self.assertEqual(db.status()['runs'],0)

    def test_stale_worker_never_requeues(self):
        """Crash recovery must not silently replay a potentially paid request."""
        jid=self.client.post('/api/v1/runs',self.task,format='json').json()['id']
        worker=Worker.objects.create(last_seen=timezone.now()-timedelta(minutes=5))
        jobs.claim(worker)
        self.assertEqual(jobs.reconcile_interrupted(),1)
        self.assertEqual(Job.objects.get(pk=jid).state,'interrupted')
        self.assertIsNone(jobs.process_one(Worker.objects.create()))
        self.assertEqual(db.status()['runs'],0)

    def test_claim_skips_locked_job(self):
        """Concurrent workers skip a locked job instead of claiming it twice."""
        first=jobs.enqueue(self.user,dict(self.task,request_id=uuid.uuid4()))[0]
        second=jobs.enqueue(self.user,dict(self.task,request_id=uuid.uuid4()))[0]
        with db.connect() as c:
            c.execute('SELECT id FROM team_backend_job WHERE id=%s FOR UPDATE',(first.pk,))
            self.assertEqual(jobs.claim(Worker.objects.create()).pk,second.pk)
        self.assertEqual(Job.objects.get(pk=first.pk).state,'queued')

    def test_memory_confirmation_requires_human_csrf(self):
        """Even an authorized service credential cannot approve personal facts."""
        self.grant(self.user,'confirm_memory')
        data={'namespace':'user','key':'nicho','value':'B2B','evidence':'Declaración del usuario'}
        proposal=self.client.post('/api/v1/memory/proposals',data,format='json').json()
        url='/api/v1/memory/'+proposal['id']+'/confirm'
        self.assertEqual(self.client.post(url,{'expected_version':1},format='json').status_code,403)
        human=APIClient(enforce_csrf_checks=True);human.force_login(self.user)
        self.assertEqual(human.post(url,{'expected_version':1},format='json').status_code,403)
        human.get('/')
        response=human.post(url,{'expected_version':1},format='json',HTTP_X_CSRFTOKEN=human.cookies['csrftoken'].value)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['status'],'confirmed')
        self.assertEqual(memory.latest(True)[0]['value'],'B2B')
        self.assertEqual(AuditEvent.objects.filter(action='memory.confirmed',actor=self.user).count(),1)

    def test_queue_capacity_rejects_new_work_but_allows_retry(self):
        """A full queue accepts idempotent reads but refuses extra jobs."""
        with self.settings(JOB_QUEUE_LIMIT=1):
            self.assertEqual(self.client.post('/api/v1/runs',self.task,format='json').status_code,202)
            self.assertEqual(self.client.post('/api/v1/runs',self.task,format='json').status_code,200)
            self.assertEqual(self.client.post('/api/v1/runs',dict(self.task,request_id=str(uuid.uuid4())),format='json').status_code,409)

    def test_bootstrap_preserves_revocation_and_existing_password(self):
        """Restarting the deployment must not resurrect revoked integration access."""
        with patch.dict(os.environ,{'KNOWLEDGE_API_TOKEN':self.token,'DJANGO_ADMIN_USERNAME':'operator','DJANGO_ADMIN_PASSWORD':'replacement'}):
            self.credential.revoked=True;self.credential.save()
            call_command('bootstrap_local',verbosity=0)
        self.credential.refresh_from_db();self.user.refresh_from_db()
        self.assertTrue(self.credential.revoked)
        self.assertTrue(self.user.check_password('test-password-local'))

    def test_memory_and_audit_commit_together(self):
        """An audit storage error must roll back the personal fact, not silently approve it."""
        data={'namespace':'user','key':'nicho','value':'B2B','evidence':'Declaración'}
        with patch('team_backend.jobs.audit',side_effect=RuntimeError('Simulated audit failure')):
            with self.assertRaises(RuntimeError):
                self.client.post('/api/v1/memory/proposals',data,format='json')
        self.assertFalse(memory.latest())
        proposal=self.client.post('/api/v1/memory/proposals',data,format='json').json()
        self.grant(self.user,'confirm_memory')
        human=APIClient();human.force_authenticate(self.user)
        with patch('team_backend.jobs.audit',side_effect=RuntimeError('Simulated audit failure')):
            with self.assertRaises(RuntimeError):
                human.post('/api/v1/memory/'+proposal['id']+'/confirm',{'expected_version':1},format='json')
        self.assertFalse(memory.latest(True))
        self.assertEqual(memory.latest()[0]['version'],1)

    def test_failed_heartbeat_stops_new_claims(self):
        """A dead heartbeat thread must stop the worker rather than accept more jobs."""
        import threading
        import time
        from team_backend.management.commands import runworker
        failed=threading.Event()
        def fail_tick(worker_id):
            failed.set()
            raise RuntimeError('Simulated DB disconnect')
        def first_job(worker):
            self.assertTrue(failed.wait(2))
            time.sleep(0.05)
            return uuid.uuid4()
        with patch.object(runworker,'HEARTBEAT_SECONDS',0.01), patch.object(runworker,'refresh_heartbeat',side_effect=fail_tick), patch.object(runworker,'process_one',side_effect=first_job) as process:
            call_command('runworker',verbosity=0)
        self.assertEqual(process.call_count,1)
        self.assertIsNotNone(Worker.objects.get().stopped_at)
