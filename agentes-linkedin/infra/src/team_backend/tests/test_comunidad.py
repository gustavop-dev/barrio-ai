"""LEC-01–03: synthetic evidence, fake public reader/model/clock. Run only in CI."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
import json
import os
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TransactionTestCase
from rest_framework.test import APIClient
from knowledge import providers
from team_backend import comunidad as cm, editorial, evidencia as ev, evaluaciones, orquestacion
from team_backend.authentication import digest
from team_backend.exceptions import Conflict
from team_backend.grafo import load_graph
from team_backend.models import (CommunitySource, CommunityStudy, CommunityWithdrawal, ConnectorAccount,
    CycleLedger, DeviceToken, EvidencePerson, FitClassification, PersonEvidence, UsageEntry)


class CommunityTests(TransactionTestCase):
    def setUp(self):
        UsageEntry.objects.all().delete()
        self.now = datetime(2026, 11, 9, 15, tzinfo=dt_timezone.utc)
        self.at = self.now-timedelta(days=20)
        self.user = get_user_model().objects.create_user('community-owner', is_superuser=True)
        self.account = ConnectorAccount.objects.create(provider='fake', external_account_id='community-test', label='Fake')
        self.connector = Mock(spec=['list_comments', 'get_profile'])
        self.connector.list_comments.return_value = []
        self.connector.get_profile.side_effect = lambda uid: {'id': uid, 'headline': 'Product engineer', 'display_name': 'Synthetic Name'}
        for target, kwargs in [
            ('team_backend.comunidad.get_connector', {'return_value': self.connector}),
            ('django.utils.timezone.now', {'return_value': self.now}),
            ('team_backend.comunidad.operador.globally_paused', {'return_value': False}),
            ('team_backend.comunidad.red._read', {'return_value': None}),
            ('team_backend.comunidad.operador.course_context', {'return_value': ([{'unit_id': cm.operador.ANALYSIS_UNITS[0], 'text': 'Synthetic course'}], [])}),
            ('knowledge.providers.claude', {'side_effect': self.fake_analysis}),
            ('team_backend.notificaciones.avisar', {'return_value': None}),
            ('httpx.post', {'side_effect': AssertionError('Network forbidden')}),
        ]:
            guard = patch(target, **kwargs); guard.start(); self.addCleanup(guard.stop)

    def person(self, number, kind='own_comment', fit=True, role='par'):
        who = ev.person(self.account, f'opaque-{number}', 'Synthetic Name')
        ev.observe(who, kind=kind, source='post_metric' if kind == 'own_comment' else 'list_comments',
            source_id=f'event-{number}', observed_at=self.at, post_id='public-post', event_at=self.at)
        FitClassification.objects.create(person=who, key=f'fit-{number}', classified_at=self.at,
            criterion_version='test-v1', sufficient=fit is not None, fit=fit, details={'role': role})
        return who

    def study(self):
        return cm.enqueue(self.user, self.account, now=self.now)[0]

    def comment(self, who, cid='public-comment', **extra):
        return dict({'id': cid, 'text': 'How do you measure delivery cost?', 'created_at': self.at,
                     'author': {'id': who.provider_user_id, 'display_name': 'Synthetic Name'}, 'is_sender': False}, **extra)

    def source(self, study, who, number=0, **extra):
        return CommunitySource.objects.create(study=study, person=who, key=ev.digest(['test', number, str(who.pk)]),
            target=ev.digest(['comments', 'public-post']), kind='public_comment', observed_at=self.now,
            expires_at=self.now+timedelta(days=90), event_at=self.at,
            text=extra.pop('text', 'How do you measure delivery cost?'), **extra)

    def analysis_item(self, source, **changes):
        return dict({'source': str(source), 'professional': True, 'sensitive': False, 'instruction': False,
            'confidence': 'medium', 'topic': 'delivery', 'need': 'measurement', 'argument': 'question',
            'evidence': 'none', 'objection': 'cost', 'follow_status': 'unknown', 'follow_reason': 'unknown', 'follow_quote': ''}, **changes)

    def fake_analysis(self, system, message, **kwargs):
        payload = json.loads(message)
        return {'text': json.dumps({'items': [self.analysis_item(r['source']) for r in payload['public_excerpts']],
                                   'citations': [cm.operador.ANALYSIS_UNITS[0], 'not-a-unit']})}

    def analyzed(self, count=6):
        people = [self.person(i) for i in range(count)]
        study = self.study(); cm.sample(study)
        for i, who in enumerate(people): self.source(study, who, i)
        cm.analyze(study)
        return study

    def test_sampling_unique_bounded_balanced_and_potential_separate(self):
        for i in range(70): self.person(i, fit=None if i < 7 else False if i < 14 else True, role=cm.ROLES[i % 6])
        for i in range(70, 79): self.person(i, kind='referent_comment')
        study = self.study(); cm.sample(study)
        self.assertEqual(len({p['person'] for p in study.selection}), 50)
        self.assertGreaterEqual(sum(p['fit'] is not True for p in study.selection), 10)
        self.assertEqual(study.coverage['potential'], 9)
        self.assertEqual(study.window_end-study.window_start, timedelta(days=90))
        self.assertEqual(study.period.isoformat(), '2026-10-01')

    def test_old_connection_allows_recent_referent_activity_not_confirmed_follow(self):
        who = self.person(1, kind='referent_comment')
        ev.observe(who, kind='connection', source='relationship', source_id='connected', observed_at=self.now-timedelta(days=120))
        study = self.study(); cm.sample(study)
        self.assertEqual(study.coverage['sample_size'], 1)
        self.assertNotIn('follower', study.selection[0]['sources'])

    def test_public_adapter_only_short_comments_date_identity_and_three_slots(self):
        who = self.person(1); study = self.study(); cm.sample(study)
        self.connector.list_comments.return_value = [self.comment(who, str(i), text='Why?') for i in range(5)] + [
            self.comment(who, 'private', text='Private message: secret'),
            self.comment(who, 'old', created_at=self.now-timedelta(days=200)),
            self.comment(who, 'no-date', created_at=None), self.comment(who, 'future', created_at=self.now)]
        cm.read_public(cm.PublicRead(str(study.pk), 'comments', 'public-post'))
        cm.read_public(cm.PublicRead(str(study.pk), 'profile', str(who.pk)))
        self.assertEqual(study.sources.count(), 3)
        self.assertEqual(study.sources.filter(text='Why?').count(), 2)
        with self.assertRaises(ValueError): cm.read_public(cm.PublicRead(str(study.pk), 'inbox', 'anything'))
        self.assertNotIn('secret', json.dumps(list(study.sources.values('text'))))

    def test_reader_minimization_small_groups_and_declared_reason(self):
        study = self.analyzed(4)
        self.assertEqual(cm.panel_context(self.account)['status'], 'Sin estudio vigente')
        self.assertEqual(study.summary['findings'], [])
        for i in range(4, 6): self.source(study, self.person(i), i)
        cm.sample(study)
        cm.analyze(study)
        packet = cm.reader_packet(cm.panel_context(self.account))
        self.assertTrue(packet['findings'])
        encoded = json.dumps(packet)
        for forbidden in ('Synthetic Name', 'opaque-', 'https:', 'public-post', 'sources', 'follow_quote'):
            self.assertNotIn(forbidden, encoded)
        self.assertEqual(study.summary['units'], [cm.operador.ANALYSIS_UNITS[0]])

    def test_declared_follow_reason_requires_exact_public_quote_and_target(self):
        study = self.analyzed()
        rows = list(study.sources.all())
        for row in rows:
            row.text = 'I follow Gustavo because these delivery examples are practical.'; row.save()
        def answer(*args, **kwargs):
            return {'text': json.dumps({'items': [self.analysis_item(r.pk, follow_status='declared', follow_reason='practical',
                follow_quote=r.text) for r in rows], 'citations': []})}
        with patch('knowledge.providers.claude', side_effect=answer): cm.analyze(study)
        self.assertTrue(any(f['basis'] == 'declared' for f in study.summary['findings']))
        rows[0].text = 'A nearby comment does not prove a follow reason.'; rows[0].save()
        with patch('knowledge.providers.claude', side_effect=answer): cm.analyze(study)
        rows[0].refresh_from_db()
        self.assertEqual(rows[0].analysis['follow_status'], 'unknown')

    def test_withdrawal_invalidates_all_versions_and_blocks_recollection(self):
        study = self.analyzed(); row = study.sources.first()
        context = cm.panel_context(self.account)
        cm.withdraw(self.user, row, whole_person=True)
        row.refresh_from_db(); study.refresh_from_db()
        self.assertEqual((row.text, row.url, row.analysis), ('', '', {}))
        self.assertEqual(cm.reader_packet(context)['status'], 'Sin estudio vigente')
        self.assertTrue(cm.excluded(self.account, row.person_id))
        self.assertEqual(cm.read_public(cm.PublicRead(str(study.pk), 'profile', str(row.person_id))).status, 'excluded')
        self.assertTrue(EvidencePerson.objects.filter(pk=row.person_id).exists())

    def test_source_unavailable_and_retention_never_recreate_content(self):
        study = self.analyzed(); context = cm.panel_context(self.account)
        cm.read_public(cm.PublicRead(str(study.pk), 'comments', 'public-post'))
        self.assertFalse(study.sources.exclude(text='').exists())
        self.assertTrue(CommunityWithdrawal.objects.exists())
        self.assertEqual(cm.reader_packet(context)['status'], 'Sin estudio vigente')
        cm.maintain(self.now+timedelta(days=180)); study.refresh_from_db()
        self.assertEqual((study.state, study.summary, study.selection), ('expired', {}, []))

    def test_ninety_day_retention_and_forty_five_day_fallback_boundary(self):
        study = self.analyzed()
        self.assertTrue(cm.current(self.account, self.now+timedelta(days=45)-timedelta(seconds=1))[1])
        self.assertTrue(cm.current(self.account, self.now+timedelta(days=45))[1])
        self.assertFalse(cm.current(self.account, self.now+timedelta(days=45, seconds=1))[1])
        cm.maintain(self.now+timedelta(days=90))
        self.assertFalse(study.sources.exclude(text='').exists())
        self.assertFalse(CommunityWithdrawal.objects.exists())  # expiry allows a future verified public renewal

    def test_monthly_idempotency_second_version_same_ledger_and_no_third(self):
        study, job, created = cm.enqueue(self.user, self.account, now=self.now)
        self.assertTrue(created)
        self.assertEqual(cm.enqueue(self.user, self.account, now=self.now)[0].pk, study.pk)
        cm.run(self.user, study.pk, job)
        job.state = 'complete'; job.save()
        second, job2, _ = cm.enqueue(self.user, self.account, refresh=True, now=self.now)
        cm.run(self.user, second.pk, job2); job2.state = 'complete'; job2.save()
        self.assertEqual(CycleLedger.objects.filter(cycle='comunidad_mensual').count(), 1)
        with self.assertRaises(Conflict): cm.enqueue(self.user, self.account, refresh=True, now=self.now)

    def test_model_failure_and_empty_study_are_explicit(self):
        self.person(1); study = self.study()
        self.connector.list_comments.return_value = [self.comment(EvidencePerson.objects.first())]
        with patch('knowledge.providers.claude', return_value={'text': '{invalid'}): cm.run(self.user, study.pk)
        study.refresh_from_db()
        self.assertEqual(study.state, 'partial_error')
        self.assertTrue(study.sources.exists())
        self.assertEqual(cm.panel_context(self.account)['status'], 'Sin estudio vigente')

    def test_manual_revision_of_autopilot_artifact_preserves_execution_owner(self):
        study, job, _ = cm.enqueue(self.user, self.account, now=self.now)
        cm.run(job.owner, study.pk, job)
        job.state = 'complete'; job.save()
        other = get_user_model().objects.create_user('another-operator', is_superuser=True)
        revised, second, _ = cm.enqueue(other, self.account, now=self.now, refresh=True)
        self.assertEqual(second.owner_id, self.user.pk)
        cm.run(second.owner, revised.pk, second)
        self.assertEqual(CycleLedger.objects.filter(cycle='comunidad_mensual').count(), 1)

    def test_budget_reservation_is_shared_across_requests(self):
        env = patch.dict(os.environ, {'ANTHROPIC_LIMIT_USD': '100'})
        env.start(); self.addCleanup(env.stop)
        UsageEntry.objects.all().delete()
        study = self.study()
        run = orquestacion.Runtime.open('comunidad_mensual', 'budget-test', self.user)
        def paid():
            providers.reserve('anthropic', 'community-study', Decimal('.80'))
            return study
        with run.session(): run.call('analizar_comunidad', study, paid, key='v1')
        second = orquestacion.Runtime.open('comunidad_mensual', 'other-request-same-month', self.user)
        with second.session(), self.assertRaisesRegex(orquestacion.CycleStopped, 'cost_cap'):
            second.call('analizar_comunidad', study, lambda: providers.reserve('anthropic', 'community-study', Decimal('.25')))
        self.assertEqual(UsageEntry.objects.count(), 1)
        self.assertEqual(CycleLedger.objects.get(pk=run.id).budget_bucket, CycleLedger.objects.get(pk=second.id).budget_bucket)

    def test_panel_keeps_five_roles_cites_valid_ids_and_rejects_invented_evidence(self):
        study = self.analyzed()
        packet = cm.reader_packet(cm.panel_context(self.account))
        reference = {'study_id': str(study.pk), 'finding_id': packet['findings'][0]['id'],
                     'basis': 'observed_in_sample', 'effect': 'Clarify the delivery cost.', 'uncertainty': 'Limited sample.'}
        panel = {'readers': [{'reader': r, 'variant_a': {'community': [reference]}, 'variant_b': {'community': []}}
                            for r in editorial.READERS]}
        self.assertEqual(cm.trace_panel(panel, packet)['community_study']['version'], 1)
        bad = deepcopy(panel); bad['readers'][0]['variant_a']['community'][0]['finding_id'] = 'invented'
        with self.assertRaises(ValueError): cm.trace_panel(bad, packet)
        with self.assertRaises(ValueError): cm.trace_panel({'readers': panel['readers'][:4]}, packet)
        absent = cm.reader_packet({})
        self.assertEqual(cm.trace_panel(panel, absent)['readers'][0]['variant_a']['community'], [])

    def test_no_texts_no_inferred_psychology_and_evaluation_incorrect_alternative(self):
        for i in range(6): self.person(i)
        study = self.study(); cm.run(self.user, study.pk); study.refresh_from_db()
        self.assertEqual(study.summary['findings'], [])  # headlines alone never explain thinking
        result = {'sample_size': study.coverage['sample_size'], 'private_used': False,
                  'small_group_examples': bool(study.summary['findings']), 'reader_status': cm.panel_context(self.account)['status']}
        self.assertTrue(evaluaciones.grade_community_case(result)['passed'])
        self.assertFalse(evaluaciones.grade_community_case(evaluaciones.COMMUNITY_CASE['incorrect'])['passed'])

    def test_api_permissions_session_device_and_no_private_ingestion_route(self):
        client = APIClient(); path = '/api/v1/comunidad?account='+str(self.account.pk)
        self.assertIn(client.get(path).status_code, [401, 403])
        outsider = get_user_model().objects.create_user('outsider')
        client.force_authenticate(outsider); self.assertEqual(client.get(path).status_code, 403)
        outsider.user_permissions.add(Permission.objects.get(codename='access_knowledge'))
        outsider = get_user_model().objects.get(pk=outsider.pk)
        client.force_authenticate(outsider); self.assertEqual(client.get(path).status_code, 403)
        client.force_authenticate(None); client.force_login(self.user)
        self.assertEqual(client.get(path).status_code, 200)
        self.assertEqual(client.put('/api/v1/comunidad', {'text': 'private'}, format='json').status_code, 405)
        client.logout()
        token = '0ff1ce_dt_community-test'
        DeviceToken.objects.create(user=self.user, name='Fake', digest=digest(token))
        client.credentials(HTTP_AUTHORIZATION='Bearer '+token)
        self.assertEqual(client.get(path).status_code, 200)

    def test_public_read_checkpoint_is_reused_without_copying_excerpts(self):
        who = self.person(1); study = self.study(); cm.sample(study)
        self.connector.list_comments.return_value = [self.comment(who)]
        run = orquestacion.Runtime.open('comunidad_mensual', 'checkpoint-test', self.user)
        request = cm.PublicRead(str(study.pk), 'comments', 'public-post')
        operation = Mock(side_effect=lambda: cm.read_public(request))
        with run.session(): first = run.call('leer_comunidad', request, operation, key='read')
        with run.session(): second = run.call('leer_comunidad', request, operation, key='read')
        self.assertEqual(first, second); operation.assert_called_once()
        ledger = CycleLedger.objects.get(pk=run.id)
        self.assertEqual(ledger.calls, 1)
        self.assertNotIn('How do you measure', json.dumps(ledger.progress_ledger))
        self.assertEqual(study.sources.count(), 1)

    def test_withdrawal_purges_panel_explanations_but_keeps_trace_and_counters(self):
        from team_backend.models import EditorialPiece
        study = self.analyzed(); context = cm.panel_context(self.account)
        ref = {'study_id': str(study.pk), 'finding_id': 'h1', 'effect': 'Dependent explanation', 'uncertainty': 'Limited'}
        piece = EditorialPiece.objects.create(account=self.account, slot_date=self.now.date(), scheduled_for=self.now,
            panel={'community_study': context, 'readers': [{'variant_a': {'community': [ref]}}]})
        run = orquestacion.Runtime.open('pieza_diaria', str(piece.pk), self.user)
        with run.session():
            run.snapshot('community_context', lambda: context)
            run.snapshot('example_panel', lambda: piece.panel)
        before = CycleLedger.objects.get(pk=run.id)
        cm.withdraw(self.user, study.sources.first())
        piece.refresh_from_db(); after = CycleLedger.objects.get(pk=run.id)
        self.assertEqual(piece.panel['readers'][0]['variant_a']['community'][0]['effect'], '')
        self.assertNotIn('Dependent explanation', json.dumps(after.progress_ledger))
        self.assertEqual((before.calls, before.limits, before.budget_bucket), (after.calls, after.limits, after.budget_bucket))
        self.assertIn(str(study.pk), json.dumps(after.progress_ledger))

    def test_pausing_collection_does_not_withdraw_successful_sources(self):
        study = self.analyzed()
        with patch('team_backend.comunidad.operador.globally_paused', return_value=True):
            result = cm.read_public(cm.PublicRead(str(study.pk), 'comments', 'public-post'))
        self.assertEqual(result.status, 'paused')
        self.connector.list_comments.assert_not_called()
        self.assertTrue(cm.current(self.account)[1])

    def test_registry_uses_binding_3b_caps_and_one_owner(self):
        graph = load_graph()
        cycle = next(c for c in graph['cycles'] if c['id'] == 'comunidad_mensual')
        self.assertEqual(cycle['orchestrator'], 'director_editorial')
        limits = cycle['limits']
        self.assertEqual((limits['cost_cap_usd'], limits['max_calls'], limits['cycle_timeout_s'],
                          limits['call_timeout_s'], limits['max_depth']), (1, 20, 600, 120, 1))
        edges = [e for e in graph['edges'] if 'comunidad_mensual' in e['cycles']]
        self.assertEqual({e['from'] for e in edges}, {'director_editorial'})
        self.assertEqual(sum(e['max_calls_per_cycle'] for e in edges), limits['max_calls'])
