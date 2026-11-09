"""Phase 5 regression/evaluation cases. Synthetic data, fake clock/model/web; no external calls.
Execution belongs to Claude/CI, not the implementation worktree.
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timedelta
from decimal import Decimal
from importlib import import_module
from threading import Barrier
from types import SimpleNamespace
from unittest.mock import patch
import uuid
import os

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import close_old_connections, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIClient
from knowledge import providers
from team_backend import experimentos as exp, referentes as refs, referentes_research as research_cycle
from team_backend import evidencia, orquestacion, research
from team_backend.exceptions import Conflict
from team_backend.models import (ActionExecution, ActionProposal, ApiCredential, AuditEvent, ConnectorAccount,
    CycleLedger, Job, Notification, ObservedPost, Referent, ReferentChange, ReferentControl,
    ReferentExperiment, ReferentNotice, ReferentReview, UsageEntry)
from team_backend.seed_referentes_qa import candidate


class MonthlyDataMixin:
    # Django reserves `fixtures` for the iterable passed to loaddata in setUpClass.
    def set_up_monthly_data(self):
        self.now = datetime(2026, 11, 1, 9, tzinfo=refs.TZ)
        self.user = get_user_model().objects.create_user('gustavo', is_superuser=True)
        self.other = get_user_model().objects.create_user('agent', is_superuser=True)
        self.account = ConnectorAccount.objects.create(provider='fake', external_account_id='monthly-fake', label='Synthetic')
        self.main = [Referent.objects.create(account=self.account, public_identifier=f'main-{n}', display_name=f'Main {n}',
            reason='Synthetic main', protected=True) for n in range(5)]
        self.control = ReferentControl.objects.create(account=self.account, initialized=True, initial_main=[str(r.pk) for r in self.main])
        self.review = ReferentReview.objects.create(account=self.account, month=self.now.date(), state='ready', deadline=refs.bounds(self.now.date())[1])
        push=patch('team_backend.alerts.notify',return_value=False)
        push.start();self.addCleanup(push.stop)
        for target in ('httpx.Client.send', 'knowledge.providers.claude', 'team_backend.operador.get_connector'):
            guard = patch(target, side_effect=AssertionError('No external calls in monthly tests'))
            guard.start(); self.addCleanup(guard.stop)

    def variable(self, n=1):
        return Referent.objects.create(account=self.account, public_identifier=f'variable-{n}', display_name=f'Variable {n}', reason='Synthetic')

    def change(self, kind='add', outgoing=None, slug=None):
        p = {'kind': kind, 'reason': 'Synthetic observed fit', 'evidence': ['synthetic-source']}
        if kind != 'remove': p['incoming'] = candidate('Incoming', slug or 'incoming-'+str(uuid.uuid4()))
        if outgoing: p['outgoing'] = str(outgoing.pk)
        return ReferentChange.objects.create(review=self.review, ordinal=self.review.changes.count(), proposal=p)

    def publish(self, at=None):
        self.review = refs.publish(self.review, at or self.now)

    def experiment(self):
        with patch('team_backend.experimentos.timezone.now', return_value=self.now):
            return exp.propose(self.review, {'referent': str(self.main[0].pk), 'hypothesis': 'More aligned arrivals',
                'audience': 'Early stage founders', 'comparison': 'Own baseline, no comparable control'})


@override_settings(REFERENTS_GUSTAVO_USERNAME='gustavo')
class MonthlyReferentTests(MonthlyDataMixin, TestCase):
    def setUp(self): self.set_up_monthly_data()

    def test_selection_evaluation_rejects_the_incorrect_alternative(self):
        from team_backend import evaluaciones
        case=evaluaciones.REFERENTS_CASE
        self.assertTrue(evaluaciones.grade_referents_case(case['expected'])['passed'])
        self.assertFalse(evaluaciones.grade_referents_case(case['incorrect'])['passed'])

    def test_monthly_bucket_changes_at_bogota_midnight_without_moving_old_usage(self):
        row=SimpleNamespace(limits={'cost_period':'month'},cycle='referentes_mensuales',budget_bucket='referentes_mensuales:2026-10')
        with patch('team_backend.orquestacion.timezone.now',return_value=self.now.replace(hour=0)-timedelta(microseconds=1)):
            self.assertEqual(orquestacion.effective_budget_bucket(row),'referentes_mensuales:2026-10')
        with patch('team_backend.orquestacion.timezone.now',return_value=self.now.replace(hour=0)):
            self.assertEqual(orquestacion.effective_budget_bucket(row),'referentes_mensuales:2026-11')
        self.assertEqual(row.budget_bucket,'referentes_mensuales:2026-10')

    def test_bogota_window_excludes_day_six_and_is_not_utc(self):
        start, end = refs.bounds(self.now.date())
        self.assertEqual((end.day, end.hour, end.utcoffset()), (6, 0, timedelta(hours=-5)))
        self.assertEqual(end-start, timedelta(days=5))
        item = self.change(); self.publish()
        refs.close(self.review, end-timedelta(microseconds=1))
        item.refresh_from_db(); self.assertIsNone(item.applied_at)
        refs.close(self.review, end)
        item.refresh_from_db(); self.assertEqual(item.state, 'aplicada_por_plazo')
        self.assertIsNone(AuditEvent.objects.get(action='referents.applied').actor)

    def test_auto_apply_and_close_notice_are_idempotent(self):
        item = self.change(); self.publish()
        refs.close(self.review, self.review.deadline)
        refs.close(self.review, self.review.deadline+timedelta(days=1))
        self.assertEqual(AuditEvent.objects.filter(action='referents.applied', target=str(item.pk)).count(), 1)
        self.assertEqual(ReferentNotice.objects.filter(review=self.review, event='closed').count(), 1)
        self.assertEqual(Referent.objects.filter(protected=True).count(), 5)

    def test_every_human_response_blocks_silence_and_versions_are_audited(self):
        items = [self.change() for _ in range(4)]; self.publish()
        for item, decision in zip(items, ['reject', 'later', 'adjust', 'edit']):
            refs.decide(self.user, item.pk, 1, decision, item.proposal if decision == 'edit' else None, now=self.now)
        refs.close(self.review, self.review.deadline)
        for item in items:
            item.refresh_from_db()
            self.assertIsNone(item.applied_at)
            self.assertEqual(item.version, 2)
            self.assertEqual(item.history[0]['actor'], str(self.user.pk))

    def test_edit_apply_saves_exact_version_and_keeps_original(self):
        item = self.change(); self.publish()
        revised = deepcopy(item.proposal); revised['reason'] = 'Gustavo revised the fit hypothesis'
        updated = refs.decide(self.user, item.pk, 1, 'edit_apply', revised, now=self.now)
        self.assertEqual(updated.state, 'approved')
        self.assertEqual(updated.history[0]['proposal']['reason'], 'Synthetic observed fit')
        self.assertTrue(Referent.objects.filter(reason=revised['reason']).exists())
        with self.assertRaises(Conflict): refs.decide(self.user, item.pk, 1, 'reject')

    def test_late_batch_never_auto_applies(self):
        item = self.change(); self.publish(self.now+timedelta(days=1))
        refs.close(self.review, self.review.deadline)
        item.refresh_from_db(); self.assertEqual(item.state, 'conflict')
        self.assertIsNone(item.applied_at)

    def test_initial_notice_failure_rolls_back_publication(self):
        with patch.object(Notification.objects, 'create', side_effect=RuntimeError('database unavailable')):
            with self.assertRaises(RuntimeError): self.publish()
        self.review.refresh_from_db()
        self.assertIsNone(self.review.published_at)
        self.assertFalse(self.review.notices.exists())

    def test_missing_initial_notice_and_changed_start_list_block_close(self):
        item = self.change(); self.publish()
        self.review.notices.all().delete()
        refs.close(self.review, self.review.deadline)
        item.refresh_from_db(); self.assertEqual(item.state, 'conflict')

    def test_agent_cannot_propose_main_removal_swap_or_protection(self):
        for kind in ['remove', 'swap']:
            item = self.change(kind, self.main[0])
            with self.assertRaisesRegex(ValueError, 'protegido'):
                refs.validate_proposal(self.account, item.proposal)
        with self.assertRaises(PermissionDenied):
            refs.manage(self.other, self.main[0], version=1, changes={'protected': False})
        with patch('team_backend.orquestacion.current', return_value=object()):
            with self.assertRaises(PermissionDenied): refs.manage(self.user, self.main[0], version=1, changes={'active': False})

    def test_gustavo_can_replace_main_atomically_and_audit_both(self):
        variable = self.variable()
        refs.manage(self.user, self.main[0], version=1, changes={}, replacement=variable.pk, source='tu_turno')
        variable.refresh_from_db(); self.main[0].refresh_from_db()
        self.assertTrue(variable.protected)
        self.assertFalse(self.main[0].active)
        self.assertEqual(Referent.objects.filter(active=True, protected=True).count(), 5)
        events = AuditEvent.objects.filter(action='referents.changed')
        self.assertEqual(events.count(), 2)
        self.assertTrue(all(e.actor == self.user and e.metadata['source'] == 'tu_turno' for e in events))

    def test_full_capacity_swap_succeeds_and_bad_add_rolls_back(self):
        variables = [self.variable(n) for n in range(10)]
        item = self.change('swap', variables[0]); extra = self.change(); self.publish()
        refs.decide(self.user, item.pk, 1, 'approve', now=self.now)
        self.assertEqual(refs.capacity(self.account)['total'], 15)
        with self.assertRaises(ValueError): refs.decide(self.user, extra.pk, 1, 'approve', now=self.now)
        extra.refresh_from_db(); self.assertIsNone(extra.responded_at)
        self.assertEqual(refs.capacity(self.account)['total'], 15)

    def test_capacity_rechecked_at_deadline_and_unprotect_cannot_overfill_variables(self):
        for n in range(10): self.variable(n)
        item = self.change(); self.publish()
        refs.close(self.review, self.review.deadline)
        item.refresh_from_db(); self.assertEqual(item.state, 'conflict')
        with self.assertRaises(ValueError): refs.manage(self.user, self.main[0], version=1, changes={'protected': False})
        self.main[0].refresh_from_db(); self.assertTrue(self.main[0].protected)

    def test_protection_change_invalidates_pending_batch(self):
        old = self.variable(); item = self.change('remove', old); self.publish()
        refs.manage(self.user, self.main[0], version=1, changes={'protected': False})
        refs.manage(self.user, old, version=1, changes={'protected': True})
        refs.close(self.review, self.review.deadline)
        item.refresh_from_db(); old.refresh_from_db()
        self.assertEqual(item.state, 'conflict'); self.assertTrue(old.active)

    def test_reminders_day1_day4_dedup_and_push_waits_for_window(self):
        self.change(); self.publish()
        with patch('team_backend.operador.within_window', return_value=False), patch('team_backend.alerts.notify') as push:
            refs.tick(self.user, self.now.replace(day=4, hour=8))
            self.assertEqual(self.review.notices.count(), 1)
            refs.tick(self.user, self.now.replace(day=4, hour=9)); refs.tick(self.user, self.now.replace(day=4, hour=10))
            self.assertEqual(self.review.notices.count(), 2); push.assert_not_called()
        with patch('team_backend.operador.within_window', return_value=True), patch('team_backend.alerts.notify') as push, patch('team_backend.notificaciones.push_enabled', return_value=True):
            refs.tick(self.user, self.now.replace(day=4, hour=11)); refs.tick(self.user, self.now.replace(day=4, hour=12))
            self.assertEqual(push.call_count, 2)

    def test_migration_protects_exact_five_or_blocks_without_guessing(self):
        self.control.delete()
        Referent.objects.all().update(protected=False)
        migrate = import_module('team_backend.migrations.0025_referentes_monthly').protect_current
        migrate(apps, SimpleNamespace(connection=SimpleNamespace(alias='default')))
        self.assertEqual(Referent.objects.filter(protected=True).count(), 5)
        self.assertTrue(ReferentControl.objects.get(account=self.account).initialized)
        ReferentControl.objects.all().delete(); Referent.objects.all().update(protected=False)
        self.variable()
        migrate(apps, SimpleNamespace(connection=SimpleNamespace(alias='default')))
        self.assertFalse(ReferentControl.objects.get(account=self.account).initialized)
        self.assertFalse(Referent.objects.filter(protected=True).exists())

    def test_human_only_api_refuses_service_credential_and_other_admin(self):
        item = self.change(); self.publish()
        client = APIClient()
        client.force_authenticate(self.user, token=ApiCredential(user=self.user, name='service', digest='fake'))
        path = f'/api/v1/referentes/cambios/{item.pk}/decidir'
        self.assertEqual(client.post(path, {'version': 1, 'decision': 'approve'}, format='json').status_code, 403)
        client.force_authenticate(self.other)
        self.assertEqual(client.post(path, {'version': 1, 'decision': 'approve'}, format='json').status_code, 403)
        client.force_authenticate(self.user)
        self.assertEqual(client.post(path, {'version': 1, 'decision': 'approve'}, format='json').status_code, 200)
        self.assertEqual(client.post(path, {'version': 1, 'decision': 'reject'}, format='json').status_code, 409)

    def test_experiment_requires_positive_approval_and_future_base(self):
        experiment = self.experiment()
        self.assertIsNone(exp.active_focus(self.account, experiment.focus_at))
        with patch('team_backend.experimentos.timezone.now', return_value=self.now):
            exp.decide(self.user, experiment.pk, 1, 'approve')
        self.assertIsNotNone(exp.active_focus(self.account, experiment.focus_at))
        with self.assertRaises(Conflict): exp.decide(self.user, experiment.pk, 1, 'stop')
        experiment.refresh_from_db()
        self.assertEqual((experiment.focus_at-experiment.starts_at).days, 14)
        self.assertEqual((experiment.followup_at-experiment.focus_at).days, 28)
        self.assertEqual((experiment.ends_at-experiment.followup_at).days, 7)

    def test_one_experiment_at_a_time_and_plan_revision_stops_old_focus(self):
        experiment = self.experiment()
        with patch('team_backend.experimentos.timezone.now', return_value=self.now):
            exp.decide(self.user, experiment.pk, 1, 'approve')
            another = ReferentExperiment.objects.create(account=self.account, referent=self.main[1], plan=experiment.plan,
                starts_at=experiment.starts_at, focus_at=experiment.focus_at, followup_at=experiment.followup_at, ends_at=experiment.ends_at)
            with self.assertRaises(Conflict): exp.decide(self.user, another.pk, 1, 'approve')
            plan = dict(experiment.plan, min_classified=12)
            exp.decide(self.user, experiment.pk, 2, 'edit', plan, (self.now+timedelta(days=2)).isoformat())
        experiment.refresh_from_db()
        self.assertEqual(experiment.state, 'proposed'); self.assertIsNone(experiment.approved_at)
        self.assertEqual(experiment.history[-1]['plan']['min_classified'], 10)
        self.assertEqual(experiment.plan['min_classified'], 12)

    def test_experiment_does_not_start_retroactively(self):
        experiment = self.experiment()
        with patch('team_backend.experimentos.timezone.now', return_value=experiment.starts_at):
            with self.assertRaisesRegex(Conflict, 'retroactivamente'): exp.decide(self.user, experiment.pk, 1, 'approve')

    def test_quality_not_volume_and_insufficient_sample_is_inconclusive(self):
        base = {'classified': 10, 'coverage': 1, 'fit': 2, 'exposure': 2, 'criterion_versions': ['v1']}
        focus = {'classified': 10, 'coverage': .8, 'fit': 9, 'exposure': 6, 'criterion_versions': ['v1']}
        request = {'plan': dict(exp.DEFAULTS), 'base': base, 'focus': focus, 'followup': {}}
        self.assertEqual(exp.evaluate(request)['outcome'], 'señal favorable')
        focus['classified'] = 1000; focus['fit'] = 1
        self.assertEqual(exp.evaluate(request)['outcome'], 'sin mejora observada')
        focus['fit'] = 9; focus['coverage'] = .2
        self.assertEqual(exp.evaluate(request)['outcome'], 'inconcluso')
        focus['coverage'] = .8; focus['exposure'] = 1
        self.assertEqual(exp.evaluate(request)['outcome'], 'inconcluso')
        self.assertEqual(Referent.objects.filter(active=True).count(), 5)

    def test_focus_two_comments_counts_uncertainty_and_rechecks_execution(self):
        experiment = self.experiment()
        with patch('team_backend.experimentos.timezone.now', return_value=self.now): exp.decide(self.user, experiment.pk, 1, 'approve')
        at = experiment.focus_at+timedelta(hours=1)
        for n in range(2):
            post = ObservedPost.objects.create(account=self.account, referent=self.main[0], provider_post_id=f'comment-{n}', text='Readable public post')
            action = ActionProposal.objects.create(account=self.account, post=post, capability='INT-03', payload={'text': 'Useful'}, payload_hash=str(n), state='confirmed')
            ActionExecution.objects.create(proposal=action, provider='fake', executed_by=self.user, idempotency_key=str(n), state='confirmed' if n else 'uncertain', started_at=at)
        draft = ActionProposal.objects.create(account=self.account, post=post, capability='INT-03', payload={'text': 'Another'}, payload_hash='draft', state='approved', referent_experiment=experiment, referent_experiment_version=2)
        with patch('team_backend.experimentos.timezone.now', return_value=at):
            self.assertFalse(exp.eligible(post))
            self.assertTrue(exp.execution_issues(draft))
        with patch('team_backend.experimentos.timezone.now', return_value=at): exp.decide(self.user, experiment.pk, 2, 'stop')
        draft.refresh_from_db(); self.assertEqual(draft.state, 'rejected')
        self.assertEqual(ActionExecution.objects.count(), 2)


@override_settings(REFERENTS_GUSTAVO_USERNAME='gustavo')
class MonthlyResearchAndConcurrencyTests(MonthlyDataMixin, TransactionTestCase):
    def setUp(self): self.set_up_monthly_data()

    def test_duplicate_job_does_not_cancel_an_inflight_review(self):
        self.review.state='preparing';self.review.save()
        job=Job.objects.create(owner=self.user,kind='review_referents',agent='operador',task='duplicate',request_hash='dup',
            params={'account':str(self.account.pk),'month':'2026-11-01'})
        runtime=orquestacion.Runtime.open('referentes_mensuales',str(self.review.pk),self.user,job)
        # Simulate another worker's committed lease without entering a nested cycle context.
        CycleLedger.objects.filter(pk=runtime.id).update(lease_token='another-worker')
        review=research_cycle.run(job)
        review.refresh_from_db()
        self.assertEqual(review.state,'preparing')
        self.assertFalse(review.changes.exists())

    def test_parallel_research_declared_calls_single_dossier_and_retry_no_spend(self):
        self.review.state = 'preparing'; self.review.save()
        job = Job.objects.create(owner=self.user, kind='review_referents', agent='operador', task='monthly', request_hash='fake',
            params={'account': str(self.account.pk), 'month': '2026-11-01'})
        ctx = {'positioning': {'version': 'v1'}, 'orientation': {'version': 'o1'}, 'memory': {'version': 'm1'},
            'grounding': {'course_status': 'disponible'}, 'course': 'Synthetic course', 'referents': [refs.snapshot(r) for r in self.main]}
        gate = Barrier(3)
        def web(request):
            gate.wait(timeout=10)
            slug = 'incoming-research'
            source = research.Source(request.key, f'https://www.linkedin.com/in/{slug}/', 'Synthetic public source', f'https://www.linkedin.com/in/{slug}/', self.now.isoformat())
            return research.ResearchResult(request.public_question, 'complete', self.now.isoformat(),
                (research.Finding('Synthetic audience of founders', (source.id,)),), (source,))
        def select(request):
            source = request['research'][0]['sources'][0]['id']
            incoming = candidate('Incoming research', 'incoming-research'); incoming['sources'] = [source]
            return {'summary': 'Synthetic dossier', 'changes': [{'kind': 'add', 'incoming': incoming, 'reason': 'Fit first', 'evidence': [source]}], 'continuity': []}
        evidence = evidencia.EvidenceResult(1, {}, {}, (), (), {})
        with patch.object(research_cycle, 'context', return_value=ctx), patch.object(research_cycle, 'select', side_effect=select), \
             patch('team_backend.research.research', side_effect=web) as tool, patch('team_backend.evidencia.report', return_value=evidence), \
             patch('team_backend.referentes_research.timezone.now', return_value=self.now):
            result = research_cycle.run(job)
            research_cycle.run(job)
        self.assertEqual(tool.call_count, 3)
        self.assertEqual(result.changes.count(), 1)
        ledger = CycleLedger.objects.get(cycle='referentes_mensuales')
        self.assertEqual(ledger.calls, 5)
        self.assertEqual(ledger.limits['cost_cap_usd'], 5)
        self.assertEqual(ledger.state, 'complete')

    @override_settings(WEB_RESEARCH_DAILY_USD=10)
    @patch.dict(os.environ, {"ANTHROPIC_LIMIT_USD": "1000000"})
    def test_monthly_budget_shared_between_accounts_and_all_branches(self):
        UsageEntry.objects.filter(usage__cycle='referentes_mensuales').delete()
        def operation():
            providers.reserve('anthropic', 'web-research-tool', Decimal('3'))
            return research.ResearchResult('public', 'complete', self.now.isoformat())
        first = orquestacion.Runtime.open('referentes_mensuales', 'first', self.user)
        second = orquestacion.Runtime.open('referentes_mensuales', 'another-account', self.user)
        request = research.ResearchRequest(key='synthetic')
        with first.session(): first.call('referentes_producto', request, operation)
        with second.session(), self.assertRaisesRegex(orquestacion.CycleStopped, 'cost_cap'):
            second.call('referentes_ia', request, operation)
        self.assertEqual(UsageEntry.objects.filter(usage__cycle='referentes_mensuales').count(), 1)

    def test_concurrent_decision_wins_before_close_and_swap_cannot_half_apply(self):
        outgoing = self.variable(); item = self.change('swap', outgoing); self.publish()
        ready, release = Barrier(2), Barrier(2)
        def reject():
            close_old_connections()
            try:
                with transaction.atomic():
                    refs.lock(self.account)
                    ready.wait(timeout=10)
                    release.wait(timeout=10)
                    refs.decide(self.user, item.pk, 1, 'reject', now=self.review.deadline-timedelta(seconds=1))
            finally: close_old_connections()
        def close():
            close_old_connections()
            try: refs.close(self.review, self.review.deadline)
            finally: close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            human = pool.submit(reject); ready.wait(timeout=10)
            worker = pool.submit(close); release.wait(timeout=10)
            human.result(timeout=15); worker.result(timeout=15)
        item.refresh_from_db(); outgoing.refresh_from_db()
        self.assertEqual(item.state, 'rejected'); self.assertTrue(outgoing.active)
        self.assertFalse(Referent.objects.filter(public_identifier=item.proposal['incoming']['identifier']).exists())
