"""Phase 4: synthetic DB evidence, fake connectors/model/clock; no network or spend.

Execution is delegated to Claude/CI. These cases do not require private corpus.
"""
from dataclasses import asdict
from datetime import datetime, timedelta, timezone as dt_timezone
import json
import uuid
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIClient

from team_backend import evidencia as ev, evaluaciones, metricas, operador, orquestacion, red, resumen_semanal
from team_backend.models import (ActionExecution, ActionProposal, AudienceSnapshot, ConnectorAccount, Contact,
    CycleLedger, EditorialPiece, EvidenceCoverage, EvidencePerson, FitClassification, ObservedPost,
    PersonEvidence, PostMetric, Referent, ReferentAttribution)


class SharedEvidenceTests(TestCase):
    def setUp(self):
        self.t = datetime(2026, 11, 1, 12, tzinfo=dt_timezone.utc)
        self.user = get_user_model().objects.create_user('evidence-owner', is_superuser=True)
        self.account = ConnectorAccount.objects.create(provider='fake', external_account_id='synthetic', label='Fake')
        self.ref = Referent.objects.create(account=self.account, public_identifier='referent-a', reason='Synthetic')
        self.post = ObservedPost.objects.create(account=self.account, referent=self.ref, provider_post_id='opaque-post',
            author_provider_id='ref-a', posted_at=self.t, share_url='https://www.linkedin.com/posts/synthetic')
        self.piece = EditorialPiece.objects.create(account=self.account, slot_date=self.t.date(), scheduled_for=self.t)
        # Any accidental provider/connector access from the shared service fails closed.
        for target in ('team_backend.connectors.get_connector', 'knowledge.providers.claude'):
            guard = patch(target, side_effect=AssertionError('Unexpected external call'))
            guard.start(); self.addCleanup(guard.stop)

    def request(self, start=None, end=None):
        end = end or self.t+timedelta(days=7)
        return ev.EvidenceRequest(str(self.account.pk), (start or self.t-timedelta(days=1)).isoformat(),
                                  end.isoformat(), end.isoformat())

    def comment(self, uid='person-a', cid='comment-a', **overrides):
        return dict({'id': cid, 'text': 'Public reasoning about product architecture. '*3,
                     'created_at': self.t.isoformat(), 'is_sender': False,
                     'author': {'id': uid, 'display_name': 'Same Name', 'type': 'individual'}}, **overrides)

    def metric(self, kind='24h', commenters=None, reactions=None, at=None):
        return PostMetric.objects.create(piece=self.piece, kind=kind, provider_post_id='own-opaque',
            published_at=self.t, captured_at=at or self.t+timedelta(days=1), commenters=commenters, reactions=reactions)

    def contact(self, uid='person-a', fit=True, confidence=.9, version='criterion-a', at=None):
        return Contact.objects.create(account=self.account, provider_user_id=uid, source='manual', headline='Product founder',
            discovered_at=self.t, classification={'fit': fit, 'confidence': confidence, 'reason': 'Public headline',
                'classified_at': (at or self.t+timedelta(hours=1)).isoformat(), 'criterion_version': version,
                'minimum_confidence': .6, 'role': 'par', 'course_citations': ['LI-03-M005-K06']})

    def test_identity_is_account_and_opaque_id_not_name_slug_or_prefix(self):
        first = ev.person(self.account, 'ACo-person', 'Same Name')
        self.assertEqual(first, ev.person(self.account, 'ACo-person', 'Renamed'))
        other_id = ev.person(self.account, 'urn:li:person:ACo-person', 'Same Name')
        other_account = ConnectorAccount.objects.create(provider='fake', external_account_id='second', label='Other')
        isolated = ev.person(other_account, 'ACo-person', 'Same Name')
        self.assertEqual(len({first.pk, other_id.pk, isolated.pk}), 3)
        with self.assertRaises(ValueError): ev.person(self.account, '', 'Same Name')

    def test_known_person_keeps_multiple_referents_interactions_and_dates(self):
        contact = self.contact()
        second = Referent.objects.create(account=self.account, public_identifier='referent-b', reason='Synthetic')
        post2 = ObservedPost.objects.create(account=self.account, referent=second, provider_post_id='second-post')
        ev.referent_comments(self.post, [self.comment(), self.comment(cid='comment-b')], self.t+timedelta(hours=1))
        ev.referent_comments(self.post, [self.comment()], self.t+timedelta(hours=2))
        ev.referent_comments(post2, [self.comment(cid='comment-c')], self.t+timedelta(hours=3))
        self.assertEqual(EvidencePerson.objects.count(), 1)
        self.assertEqual(PersonEvidence.objects.count(), 3)
        self.assertEqual({e['referent'] for e in ev.contact_context(contact)}, {str(self.ref.pk), str(second.pk)})
        first = PersonEvidence.objects.get(interaction_id='comment-a')
        self.assertEqual((first.event_at, first.observed_at), (self.t, self.t+timedelta(hours=1)))
        contact.refresh_from_db(); self.assertEqual(contact.evidence, {})

    def test_three_cuts_and_repeated_comments_count_one_person_and_latest_counter(self):
        entries = [{'provider_user_id': 'person-a', 'name': 'A', 'substantive': True}]*2
        for kind, days, count in [('24h', 1, 3), ('72h', 3, 6), ('7d', 7, 9)]:
            metric = self.metric(kind, entries, count, self.t+timedelta(days=days))
            ev.ingest_metric(metric); ev.ingest_metric(metric)
        result = ev.report(self.request(end=self.t+timedelta(days=8)))
        self.assertEqual(result.coverage['observed'], 1)
        self.assertEqual(result.aggregates['reactions']['value'], 9)
        self.assertEqual(result.aggregates['reactions']['identity'], 'sin identidad')
        self.assertEqual(PersonEvidence.objects.count(), 3)
        self.assertTrue(all(e.event_at is None and not e.interaction_id for e in PersonEvidence.objects.all()))
        self.assertTrue(all(e.details['comments_in_cut'] == 2 for e in PersonEvidence.objects.all()))
        self.assertFalse(Contact.objects.exists())  # Observing someone never initiates outreach.

    def test_fit_uses_eight_sufficient_of_twelve_not_missing_or_low_confidence(self):
        self.metric(commenters=[{'provider_user_id': f'p-{i}'} for i in range(12)])
        for i in range(10):
            ev.record_classification(self.contact(f'p-{i}', fit=i < 5, confidence=.9 if i < 8 else .4))
        result = ev.report(self.request())
        self.assertEqual(result.coverage['classification_coverage'], '8/12')
        self.assertEqual((result.coverage['fit'], result.coverage['fit_pct'], result.coverage['unknown']), (5, 62.5, 4))
        self.assertEqual(result.coverage['criterion_versions'], ['criterion-a'])
        self.assertTrue(all(p['classification']['classified_at'] for p in result.people if p['classification']['sufficient']))
        self.assertTrue(evaluaciones.grade_evidence_case(result)['passed'])
        result.coverage.update(evaluaciones.EVIDENCE_CASE['incorrect'])
        self.assertFalse(evaluaciones.grade_evidence_case(result)['passed'])

    def test_classification_history_preserves_previous_cut_and_insufficient_reclassification(self):
        contact = self.contact()
        old = ev.record_classification(contact)
        contact.classification.update(fit=False, confidence=.3, criterion_version='criterion-b',
                                      classified_at=(self.t+timedelta(days=3)).isoformat())
        contact.save()
        ev.record_classification(contact)
        ev.record_classification(contact)
        early = ev.report(self.request(end=self.t+timedelta(days=2)))
        late = ev.report(self.request())
        self.assertEqual(early.people[0]['classification']['version_id'], str(old.pk))
        self.assertTrue(early.people[0]['classification']['fit'])
        self.assertIsNone(late.people[0]['classification']['fit'])
        self.assertEqual(FitClassification.objects.count(), 2)

    def test_missing_failed_ambiguous_and_observed_zero_are_distinct(self):
        self.metric(commenters=None, reactions=None)
        ev.referent_comments(self.post, None, self.t)
        result = ev.report(self.request())
        self.assertIsNone(result.coverage['fit_pct'])
        self.assertIsNone(result.aggregates['reactions']['value'])
        self.assertIsNone(result.referents[0]['discovered'])
        self.assertEqual(result.coverage['reads'], {'missing': 2})
        self.metric('72h', [], 0, self.t+timedelta(days=3))
        ev.referent_comments(self.post, [self.comment(author={'display_name': 'Ambiguous'})], self.t+timedelta(days=1))
        result = ev.report(self.request())
        self.assertEqual(result.aggregates['reactions']['value'], 0)
        self.assertEqual(EvidencePerson.objects.count(), 0)
        read = EvidenceCoverage.objects.get(source='referent_comments', status='partial')
        self.assertEqual(read.details['without_identity'], 1)
        self.assertEqual(result.referents[0]['discovered'], 0)  # zero observed in a partial page, not zero audience

    def test_attribution_shared_baseline_exposure_and_observation_never_causality(self):
        ref2 = Referent.objects.create(account=self.account, public_identifier='b', reason='Synthetic')
        post2 = ObservedPost.objects.create(account=self.account, referent=ref2, provider_post_id='b')
        ev.referent_comments(self.post, [self.comment()], self.t-timedelta(days=2))
        ev.referent_comments(post2, [self.comment(cid='b')], self.t)
        self.metric(commenters=[{'provider_user_id': 'person-a'}])
        for state in ('confirmed', 'uncertain'):
            proposal = ActionProposal.objects.create(account=self.account, post=self.post, capability='INT-03',
                payload={}, payload_hash=uuid.uuid4().hex, state=state)
            ActionExecution.objects.create(proposal=proposal, state=state, idempotency_key=uuid.uuid4().hex,
                provider='fake', executed_by=self.user, started_at=self.t, finished_at=self.t+timedelta(minutes=1))
        result = ev.report(self.request())
        self.assertEqual(result.coverage['observed'], 1)
        by_id = {r['referent']: r for r in result.referents}
        self.assertEqual(by_id[str(self.ref.pk)]['baseline']['observed_before_window'], 1)
        self.assertEqual(by_id[str(self.ref.pk)]['exposure_count'], 1)
        for row in result.referents:
            association = row['associations'][0]
            self.assertEqual(association['origin'], 'coincidencia_observable')
            self.assertEqual(len(association['shared_with']), 1)
            self.assertTrue(association['own_after_referent'])
            self.assertFalse(association['causal_claim'])
        self.assertIsNone(result.people[0]['arrival_at'])
        ev.report(self.request())
        self.assertEqual(ReferentAttribution.objects.count(), 2)

    def test_invitation_connection_manual_follower_are_separate_and_private(self):
        contact = self.contact()
        ev.relationship(contact, 'invitation', 'invite-1', self.t, direction='received')
        ev.relationship(contact, 'connection', 'connection-1', self.t+timedelta(days=1))
        manual = ev.add_manual(self.user, self.account, provider_user_id='person-a', source_id='manual-1',
            observed_at=self.t+timedelta(days=2), evidence_ref='capture:'+str(uuid.uuid4()),
            kind='follower', referent=self.ref, origin='declared')
        result = ev.report(self.request())
        self.assertEqual(result.coverage['observed'], 1)
        self.assertTrue(result.people[0]['follower_identified'])
        self.assertEqual(result.referents[0]['associations'][0]['origin'], 'declarado_por_persona')
        self.assertFalse(result.referents[0]['causal_claim'])
        self.assertNotIn(manual.details['evidence_ref'], json.dumps(asdict(result)))
        self.assertIsNone(manual.event_at)
        with self.assertRaises(ValueError):
            ev.observe(manual.person, kind='reactor', source='unipile', source_id='x', observed_at=self.t)
        with self.assertRaises(ValueError):
            ev.add_manual(self.user, self.account, provider_user_id='person-a', source_id='bad',
                          observed_at=self.t, evidence_ref='PRIVATE INBOX TEXT')

    def test_legacy_backfill_is_idempotent_and_does_not_export_invitation_or_guess_referent(self):
        contact = self.contact(version='legacy-unknown')
        contact.evidence = {'referent': self.ref.display_name, 'invitation_message': 'PRIVATE INBOX TEXT'}
        contact.invited_at = self.t
        contact.save()
        ev.report(self.request()); ev.report(self.request())
        self.assertEqual(EvidencePerson.objects.count(), 1)
        self.assertEqual(PersonEvidence.objects.count(), 2)
        self.assertFalse(PersonEvidence.objects.filter(referent__isnull=False).exists())
        self.assertNotIn('PRIVATE INBOX TEXT', str(list(PersonEvidence.objects.values())))
        self.assertIsNone(FitClassification.objects.get().fit)

    def test_aggregate_followers_are_net_and_need_two_known_compatible_dates(self):
        for day, count in [(0, 100), (1, 105)]:
            at = self.t+timedelta(days=day)
            snap = AudienceSnapshot.objects.create(day=at.date(), followers=count, captured_at=at)
            ev.ingest_audience(self.account, snap)
        result = ev.report(self.request())
        self.assertEqual(result.aggregates['followers_net']['value'], 5)
        self.assertEqual(result.people, ())
        with self.assertRaises(ValueError):
            ev.report(self.request(start=self.t+timedelta(days=9)))
        bad = ev.EvidenceRequest(str(self.account.pk), '2026-11-01', '2026-11-02', '2026-11-03')
        with self.assertRaises(ValueError): ev.report(bad)

    def test_tool_is_typed_registered_checkpointed_and_permission_checked(self):
        first = ev.consult(self.user, self.request())
        with patch.object(ev, 'report', side_effect=AssertionError('Checkpoint must be reused')):
            self.assertEqual(ev.consult(self.user, self.request()), first)
        row = CycleLedger.objects.get(cycle='consulta_evidencia')
        self.assertEqual((row.state, row.calls), ('complete', 1))
        user = get_user_model().objects.create_user('no-permission')
        with self.assertRaises(PermissionDenied): ev.consult(user, self.request())
        run = orquestacion.Runtime.open('consulta_evidencia', 'invalid-result', self.user)
        with run.session(), self.assertRaises(orquestacion.ContractError):
            run.call('evidencia_analista', self.request(), lambda: {'invented': 'result'})
        run = orquestacion.Runtime.open('red', 'evidence-red', self.user)
        with run.session():
            self.assertEqual(ev.consult(self.user, self.request(), runtime=run), first)
        wrong = ev.EvidenceRequest(123, self.request().start, self.request().end, self.request().as_of)
        run = orquestacion.Runtime.open('consulta_evidencia', 'invalid-request', self.user)
        with run.session(), self.assertRaises(orquestacion.UndeclaredCall):
            run.call('evidencia_analista', wrong, lambda: first)

    def test_archiving_hides_from_list_preserves_history_and_stops_new_scans(self):
        ev.referent_comments(self.post, [self.comment()], self.t)
        client = APIClient(); client.force_login(self.user)
        response = client.delete(f'/api/v1/operador/referents/{self.ref.pk}')
        self.assertEqual(response.status_code, 204)
        self.ref.refresh_from_db()
        self.assertFalse(self.ref.active); self.assertIsNotNone(self.ref.archived_at)
        self.assertEqual(client.get('/api/v1/operador/referents').json()['results'], [])
        self.post.refresh_from_db()
        ev.referent_comments(self.post, [self.comment(cid='later')], self.t+timedelta(days=1))
        self.assertEqual(PersonEvidence.objects.count(), 1)
        restored, created = operador.add_referent(self.user, self.account, self.ref.public_identifier, 'Restored')
        self.assertFalse(created); self.assertEqual(restored.pk, self.ref.pk)
        self.assertIsNone(restored.archived_at); self.assertTrue(restored.active)

    def test_discovery_fake_preserves_known_people_and_caps_without_extra_reads(self):
        self.contact()
        fake = Mock()
        fake.list_comments.return_value = [self.comment(), self.comment(uid='new-person', cid='new')]
        with patch('team_backend.red.get_connector', return_value=fake), \
             patch('team_backend.operador.role_context', return_value=('', {})), \
             patch('team_backend.red.search_queries', return_value=[]):
            result = red.discover(self.user, self.account, now=self.t+timedelta(days=1))
        self.assertEqual(result['new'], 1)
        self.assertEqual(PersonEvidence.objects.filter(kind='referent_comment').count(), 2)
        fake.list_comments.assert_called_once_with(self.post.provider_post_id, limit=50)
        fake.get_profile.assert_not_called()

    def test_metric_adapter_populates_evidence_without_changing_compact_commenters(self):
        proposal = ActionProposal.objects.create(account=self.account, piece=self.piece, capability='CONT-09', payload={}, payload_hash='f'*64)
        execution = ActionExecution.objects.create(proposal=proposal, state='confirmed', idempotency_key='metric-fake',
            provider='fake', executed_by=self.user, started_at=self.t)
        commenters = [{'provider_user_id': 'person-a', 'name': 'A', 'substantive': True, 'role': None, 'fit': None}]
        count = metricas._capture(execution, ['24h', '72h'], {'id': 'own', 'share_url': '', 'impressions': None,
            'reactions_counter': None, 'comments_counter': 1, 'reposts_counter': None}, self.t+timedelta(days=3), commenters)
        self.assertEqual(count, 2)
        self.assertEqual(EvidencePerson.objects.count(), 1)
        self.assertEqual(PersonEvidence.objects.count(), 2)
        self.assertTrue(all(m.commenters == commenters for m in PostMetric.objects.all()))

    def test_fake_classifier_records_criterion_and_unknown_low_confidence_without_outreach(self):
        a, b = self.contact('a'), self.contact('b')
        Contact.objects.filter(pk__in=[a.pk, b.pk]).update(classification={})
        citations = ['LI-03-M005-K06']
        grounding = {'course_missing': False, 'course_citations': citations, 'course_version': 'fake-course'}
        answer = {'model': 'fake', 'text': json.dumps({'contacts': [
            {'id': str(c.pk), 'fit': True, 'confidence': confidence, 'reason': 'Public product headline',
             'role': 'par', 'course_citations': citations} for c, confidence in [(a, .9), (b, .3)]]})}
        with patch('team_backend.red.spent_today', return_value=0), \
             patch('team_backend.red.min_confidence', return_value=.6), \
             patch('team_backend.operador.role_context', return_value=('', grounding)), \
             patch('team_backend.guardas.blocks', return_value=('', '')), \
             patch('team_backend.orientacion.text', return_value='Synthetic orientation'), \
             patch('knowledge.providers.claude', return_value=answer), \
             patch('team_backend.red.timezone.now', return_value=self.t+timedelta(hours=1)):
            summary = red.classify(self.user, self.account)
        self.assertEqual((summary['classified'], summary['fit']), (2, 1))
        self.assertEqual(FitClassification.objects.filter(fit=True).count(), 1)
        self.assertEqual(FitClassification.objects.filter(fit__isnull=True).count(), 1)
        self.assertTrue(all(v.criterion_version.startswith(ev.CRITERION_VERSION+':') for v in FitClassification.objects.all()))
        self.assertFalse(ActionProposal.objects.exists())

    def test_weekly_analysis_does_not_use_identifiers_as_counts_or_claim_causal_arrivals(self):
        data = {'evidencia_compartida': [{'coverage': {'fit': 5}, 'person': 'person-999999',
            'criterion_versions': ['criterion-888888'], 'referents': ['ref-777777']} ]}
        self.assertEqual(resumen_semanal.allowed_numbers(data), {5})
        raw = {'titular': '5 personas llegaron gracias al referente', 'lo_que_funciono': [
            {'texto': '5 personas observadas encajan; la procedencia es una coincidencia.', 'cifra': 'fit: 5'},
            {'texto': '999999 personas nuevas', 'cifra': 'fit: 999999'}]}
        clean = resumen_semanal.validate(raw, data, self.t.date())
        self.assertNotEqual(clean['titular'], raw['titular'])
        self.assertEqual(len(clean['lo_que_funciono']), 1)
