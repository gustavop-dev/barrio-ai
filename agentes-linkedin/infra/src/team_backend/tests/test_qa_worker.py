"""Behavior-first QA of durable jobs and provider accounting; isolated PostgreSQL."""
import os
import tempfile
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import httpx
from django.contrib.auth.models import Permission, User
from django.db import close_old_connections, connection, connections
from django.test import TransactionTestCase
from psycopg.types.json import Jsonb

from knowledge import db, memory, providers
from team_backend import jobs
from team_backend.tests.fakes import FakeAnthropic, message, timeout_error
from team_backend.models import AuditEvent, Job, Worker

NOW = datetime(2026, 11, 6, 0, 0, tzinfo=timezone.utc)


class WorkerQATests(TransactionTestCase):
    def setUp(self):
        self.assertTrue(connection.settings_dict['NAME'].startswith('test_'))
        self.assertEqual(connection.vendor, 'postgresql')
        self.environment = patch.dict(os.environ, {
            'LIVE_PROVIDERS': 'false', 'ANTHROPIC_API_KEY': 'test-only',
            'OPENAI_API_KEY': 'test-only', 'OPENAI_LIMIT_USD': '1',
            'ANTHROPIC_LIMIT_USD': '1', 'ANTHROPIC_MODEL': 'claude-sonnet-4-6',
            'ANTHROPIC_MAX_TOKENS': '1800',
        })
        self.environment.start(); self.addCleanup(self.environment.stop)
        network = patch('httpx.post', side_effect=AssertionError('Paid network forbidden'))
        network.start(); self.addCleanup(network.stop)
        self.files = tempfile.TemporaryDirectory()
        self.addCleanup(self.files.cleanup)
        policy = Path(self.files.name) / 'LinkedIn Sales - Procesamiento completo/conocimiento-para-agentes/politica-de-uso.json'
        policy.parent.mkdir(parents=True)
        policy.write_text('{"rules": ["Citar las fuentes del contexto"]}')
        source = patch.dict(os.environ, {'SOURCE_ROOT': self.files.name})
        source.start(); self.addCleanup(source.stop)
        with db.connect() as c:
            c.execute('TRUNCATE memory,runs,usage_ledger,embedding_cache,unit_evidence,edges,chunks,units,source_files,evidence,unit_revisions CASCADE')
            c.execute("INSERT INTO source_files(path,sha256) VALUES('fixture','abc')")
            c.execute('''INSERT INTO units(id,session,title,original,sha256,source_path,pointer,metadata)
                VALUES('LI-01-M001-K01',1,'Titular comprador','{"title":"Titular comprador"}','abc','fixture','/units/0','{}')''')
            c.execute("INSERT INTO chunks(id,unit_id,section,text,sha256,tokens) VALUES('chunk','LI-01-M001-K01','title','Titular comprador','abc',3)")
        self.user = User.objects.create_user('worker-qa')
        self.user.user_permissions.add(*Permission.objects.filter(
            content_type__app_label='team_backend',
            codename__in=['access_knowledge', 'run_agents', 'use_paid_providers']))
        self.task = {'agent': 'perfil', 'task': 'Titular comprador', 'execute': False,
                     'mode': 'lexical', 'request_id': uuid.uuid4()}

    def ledger(self):
        with db.connect() as c:
            return c.execute('SELECT status,actual_usd,reserved_usd FROM usage_ledger ORDER BY id').fetchall()

    def response(self, input_tokens=100, output_tokens=20, text='Consejo [LI-01-M001-K01]', stop_reason='end_turn'):
        return message(text=text, input_tokens=input_tokens, output_tokens=output_tokens, stop_reason=stop_reason)

    def simulated_claude(self, payload, before_generation=None, input_tokens=100):
        # The SDK transport is replaced; httpx.post stays blocked by setUp.
        return patch('knowledge.providers.anthropic_client',
                     return_value=FakeAnthropic(payload, input_tokens=input_tokens, before_generation=before_generation))

    def test_concurrent_enqueue_persists_one_job_and_one_audit(self):
        """Duplicate simultaneous requests must not create two chargeable jobs."""
        barrier = threading.Barrier(2)
        def submit():
            close_old_connections()
            try:
                user = User.objects.get(pk=self.user.pk)
                barrier.wait(timeout=5)
                job, created = jobs.enqueue(user, self.task)
                return job.pk, created
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(submit); second = pool.submit(submit)
            results = [first.result(timeout=10), second.result(timeout=10)]
        self.assertEqual({item[0] for item in results}, {self.task['request_id']})
        self.assertEqual(sorted(item[1] for item in results), [False, True])
        self.assertEqual(Job.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.filter(action='job.enqueued').count(), 1)
        self.assertEqual(self.ledger(), [])

    def test_failed_enqueue_audit_rolls_back_job(self):
        """An audit DB error must not leave a queued job after an unsuccessful request."""
        with patch.object(AuditEvent.objects, 'create', side_effect=RuntimeError('Audit storage unavailable')):
            with self.assertRaisesRegex(RuntimeError, 'Audit storage unavailable'):
                jobs.enqueue(self.user, self.task)
        self.assertEqual(Job.objects.count(), 0)
        self.assertEqual(AuditEvent.objects.count(), 0)

    def test_paid_permission_revoked_after_enqueue_prevents_generation(self):
        """Revoked payment permission must block a previously queued paid task."""
        task = dict(self.task, execute=True)
        job, _ = jobs.enqueue(self.user, task)
        self.user.user_permissions.remove(Permission.objects.get(
            content_type__app_label='team_backend', codename='use_paid_providers'))
        jobs.process_one(Worker.objects.create())
        job.refresh_from_db()
        self.assertEqual(job.state, 'failed')
        self.assertEqual(job.result_status, 'failed')
        self.assertEqual(db.status()['runs'], 0)
        self.assertEqual(self.ledger(), [])

    def test_provider_failure_retains_uncertain_cost_and_never_requeues(self):
        """An ambiguous HTTP failure must preserve its reserve without an automatic second execution."""
        job, _ = jobs.enqueue(self.user, dict(self.task, execute=True))
        worker = Worker.objects.create()
        with patch.dict(os.environ, {'LIVE_PROVIDERS': 'true'}), self.simulated_claude(timeout_error()):
            jobs.process_one(worker)
            again = jobs.process_one(worker)
        job.refresh_from_db()
        self.assertEqual(job.state, 'failed')
        self.assertIsNone(again)
        self.assertEqual(self.ledger(), [{'status': 'uncertain', 'actual_usd': None, 'reserved_usd': Decimal('0.028335')}])
        with db.connect() as c:
            run = c.execute('SELECT status FROM runs WHERE id=%s', (job.pk,)).fetchone()
        self.assertEqual(run['status'], 'failed')

    def test_validation_failure_is_terminal_without_human_approval(self):
        """A technically completed answer with an unknown citation must remain validation_failed."""
        job, _ = jobs.enqueue(self.user, dict(self.task, execute=True))
        response = self.response(text='Consejo [LI-07-V001-K01]')
        with patch.dict(os.environ, {'LIVE_PROVIDERS': 'true'}), self.simulated_claude(response):
            jobs.process_one(Worker.objects.create())
        job.refresh_from_db()
        self.assertEqual((job.state, job.result_status), ('complete', 'validation_failed'))
        with db.connect() as c:
            saved = c.execute('SELECT payload FROM runs WHERE id=%s', (job.pk,)).fetchone()['payload']
        self.assertEqual(saved['human_review'], False)
        self.assertEqual(saved['citation_check']['unknown'], ['LI-07-V001-K01'])
        self.assertEqual(self.ledger()[0]['actual_usd'], Decimal('0.0006'))

    def test_late_success_cannot_resurrect_reconciled_job(self):
        """A late provider answer must not change an interrupted job back to complete."""
        worker = Worker.objects.create(last_seen=NOW-timedelta(seconds=181))
        job, _ = jobs.enqueue(self.user, dict(self.task, execute=True))
        with patch.dict(os.environ, {'LIVE_PROVIDERS': 'true'}), patch('team_backend.jobs.timezone.now', return_value=NOW), self.simulated_claude(self.response(), jobs.reconcile_interrupted):
            jobs.process_one(worker)
        job.refresh_from_db()
        self.assertEqual(job.state, 'interrupted')
        self.assertEqual(AuditEvent.objects.filter(action='job.complete').count(), 0)
        self.assertEqual(AuditEvent.objects.filter(action='job.interrupted').count(), 1)
        with db.connect() as c:
            saved = c.execute('SELECT status FROM runs WHERE id=%s', (job.pk,)).fetchone()
        self.assertEqual(saved['status'], 'needs_review')
        self.assertEqual(self.ledger()[0]['actual_usd'], Decimal('0.0006'))

    def test_simultaneous_memory_versions_have_one_winner(self):
        """Two writers with the same expected version must not silently overwrite each other."""
        barrier = threading.Barrier(2)
        def propose():
            barrier.wait(timeout=5)
            try:
                return memory.propose('user', 'nicho', 'B2B', 'tester', 'Declaración')['version']
            except ValueError:
                return 'conflict'
        with ThreadPoolExecutor(max_workers=2) as pool:
            first=pool.submit(propose); second=pool.submit(propose)
            results=[first.result(timeout=10), second.result(timeout=10)]
        self.assertCountEqual(results, [1, 'conflict'])
        self.assertEqual(len(memory.latest()), 1)
        self.assertEqual(memory.latest()[0]['value'], 'B2B')

    def test_historical_run_identifier_cannot_be_reenqueued(self):
        """A job must not reuse a pre-Django execution ID and expose or duplicate its work."""
        with db.connect() as c:
            c.execute('INSERT INTO runs(id,agent,task,status,payload) VALUES(%s,%s,%s,%s,%s)',
                (self.task['request_id'], 'perfil', 'Historical', 'preview', Jsonb({})))
        with self.assertRaisesRegex(jobs.Conflict, 'histórica'):
            jobs.enqueue(self.user, self.task)
        self.assertEqual(Job.objects.count(), 0)
        self.assertEqual(db.status()['runs'], 1)

    def test_claude_negative_usage_cannot_credit_the_budget(self):
        """Malformed provider token counts must not create a negative charge and expand the spending allowance."""
        response = self.response(input_tokens=-100, output_tokens=-20)
        with patch.dict(os.environ, {'LIVE_PROVIDERS': 'true'}), self.simulated_claude(response):
            with self.assertRaisesRegex(ValueError, 'inválida'):
                providers.claude('instructions', 'question')
        self.assertEqual(self.ledger(), [{'status': 'uncertain', 'actual_usd': None, 'reserved_usd': Decimal('0.028335')}])

    def test_embedding_negative_usage_cannot_credit_or_cache(self):
        """Malformed embedding usage must retain its reserve and leave the vector uncommitted."""
        response={'data':[{'index':0,'embedding':[1.0]*providers.DIMENSIONS}], 'usage':{'total_tokens':-100}}
        with patch.dict(os.environ, {'LIVE_PROVIDERS': 'true'}), patch('httpx.post', return_value=httpx.Response(200,json=response)):
            with self.assertRaisesRegex(ValueError, 'inválida'):
                providers.embeddings(['hello'])
        self.assertEqual(self.ledger(), [{'status':'uncertain','actual_usd':None,'reserved_usd':Decimal('0.00000004')}])
        self.assertEqual(db.status()['embedding_cache'], 0)

    def test_concurrent_embedding_misses_pay_once(self):
        """Two simultaneous identical queries must reuse one vector and one completed ledger entry."""
        barrier = threading.Barrier(2)
        vector = [1.0] * providers.DIMENSIONS
        response = {'data': [{'index': 0, 'embedding': vector}], 'usage': {'total_tokens': 1}}
        def query():
            barrier.wait(timeout=5)
            return providers.embeddings(['hello'])
        with patch.dict(os.environ, {'LIVE_PROVIDERS': 'true'}), patch('httpx.post', return_value=httpx.Response(200, json=response)):
            with ThreadPoolExecutor(max_workers=2) as pool:
                first=pool.submit(query); second=pool.submit(query)
                results=[first.result(timeout=10), second.result(timeout=10)]
        self.assertEqual(results, [[vector], [vector]])
        self.assertEqual(self.ledger(), [{'status': 'complete', 'actual_usd': Decimal('0.00000002'), 'reserved_usd': Decimal('0.00000004')}])
        self.assertEqual(db.status()['embedding_cache'], 1)

    def test_preexisting_running_execution_is_not_repeated(self):
        """Recovering a job with an ambiguous saved execution must leave it interrupted without a second charge."""
        task = dict(self.task, execute=True)
        job, _ = jobs.enqueue(self.user, task)
        identity = {key: task[key] for key in ['agent', 'task', 'execute', 'mode']}
        with db.connect() as c:
            c.execute('INSERT INTO runs(id,agent,task,status,payload) VALUES(%s,%s,%s,%s,%s)',
                (job.pk, task['agent'], task['task'], 'running', Jsonb({'request': identity})))
        reservation = providers.reserve('anthropic', 'interrupted-original', '0.05')
        providers.settle(reservation, 'uncertain')
        jobs.process_one(Worker.objects.create())
        job.refresh_from_db()
        self.assertEqual((job.state, job.result_status), ('interrupted', 'running'))
        self.assertEqual(db.status()['runs'], 1)
        self.assertEqual(self.ledger(), [{'status': 'uncertain', 'actual_usd': None, 'reserved_usd': Decimal('0.05')}])

    def test_preflight_boolean_token_count_cannot_start_generation(self):
        """A boolean token count must not be coerced to one token and allow generation."""
        with patch.dict(os.environ, {'LIVE_PROVIDERS': 'true'}), self.simulated_claude(self.response(), input_tokens=True):
            with self.assertRaises(ValueError):
                providers.claude('instructions', 'question')
        self.assertEqual(self.ledger(), [])

    def test_fractional_claude_usage_cannot_be_settled(self):
        """A fractional token count must not be accepted as billable provider usage."""
        response = self.response(input_tokens=1.5)
        with patch.dict(os.environ, {'LIVE_PROVIDERS': 'true'}), self.simulated_claude(response):
            with self.assertRaisesRegex(ValueError, 'inválida'):
                providers.claude('instructions', 'question')
        self.assertEqual(self.ledger(), [{'status': 'uncertain', 'actual_usd': None, 'reserved_usd': Decimal('0.028335')}])

    def test_string_embedding_usage_cannot_be_coerced(self):
        """A numeric string in embedding usage must not bypass the provider schema validation."""
        response={'data':[{'index':0,'embedding':[1.0]*providers.DIMENSIONS}], 'usage':{'total_tokens':'100'}}
        with patch.dict(os.environ, {'LIVE_PROVIDERS': 'true'}), patch('httpx.post', return_value=httpx.Response(200,json=response)):
            with self.assertRaisesRegex(ValueError, 'inválida'):
                providers.embeddings(['hello'])
        self.assertEqual(self.ledger(), [{'status':'uncertain','actual_usd':None,'reserved_usd':Decimal('0.00000004')}])
        self.assertEqual(db.status()['embedding_cache'], 0)
