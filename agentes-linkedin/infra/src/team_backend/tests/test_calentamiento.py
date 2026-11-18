"""The buyer's warm-up (calentamiento.py, phase 2 of docs/plan-outbound.md, BAR-19) piece by piece: when the warm-up is
done, how warm a person is, the buying signals of the web stage check, the buyers' reads and their caps, the rest, the
wake and the retry, the read-only list of old invitations and what stays as before with the switch off. The path end to
end lives in test_comprador_e2e (WarmupBuyerPathTests). Synthetic data only, no paid call, no network."""
import json
import os
import uuid
from datetime import timedelta
from unittest.mock import patch
from django.test import SimpleTestCase
from django.utils import timezone
from team_backend import calentamiento, comprador, editorial, red, research
from team_backend.models import AuditEvent, BuyerJourney, BuyerTouch, Contact, ObservedPost
from team_backend.tests.test_comprador import BuyerBase

H = timedelta(hours=1)
D = timedelta(days=1)
ON = {'BUYER_WARMUP_ENABLED': 'true'}


class WarmupBase(BuyerBase):
    def setUp(self):
        super().setUp()
        env = patch.dict(os.environ, ON)
        env.start()
        self.addCleanup(env.stop)

    def followed(self, slug='ana-acme', name='Ana Acme', days=3, **fields):
        contact, journey = self.buyer(slug, name, stage='followed', followed_at=timezone.now() - days * D, **fields)
        return Contact.objects.get(pk=contact.pk), journey

    def commented(self, contact, at):
        execution = self.executed(contact, 'INT-03', at, post=self.their_post(contact))
        comprador.update(contact)
        return execution

    def refresh(self, contact):
        return comprador.update(Contact.objects.get(pk=contact.pk))


class InviteAtTests(WarmupBase):
    def test_at_the_latest_14_days_after_the_follow(self):
        contact, journey = self.followed()
        self.assertEqual(journey.next_at, contact.followed_at + 14 * D)
        self.assertFalse(calentamiento.invite_ready(contact))
        self.assertTrue(calentamiento.invite_ready(contact, contact.followed_at + 14 * D))

    def test_the_second_comment_ends_the_warm_up(self):
        contact, _ = self.followed()
        self.commented(contact, contact.followed_at + D)
        self.assertEqual(self.refresh(contact).next_at, contact.followed_at + 14 * D)
        self.commented(contact, contact.followed_at + 2 * D)
        self.assertEqual(self.refresh(contact).next_at, contact.followed_at + 2 * D)
        with patch.dict(os.environ, {'BUYER_WARMUP_COMMENTS': '3'}):
            self.assertEqual(self.refresh(contact).next_at, contact.followed_at + 14 * D)

    def test_an_accelerating_signal_of_the_last_month_ends_it_at_once(self):
        contact, _ = self.followed()
        self.their_comment(contact, contact.followed_at - 40 * D)  # too old: it does not count
        self.assertEqual(self.refresh(contact).next_at, contact.followed_at + 14 * D)
        self.their_comment(contact, contact.followed_at - 10 * D)  # before the follow but in the month: right away
        self.assertEqual(self.refresh(contact).next_at, contact.followed_at)
        self.assertTrue(calentamiento.invite_ready(contact))

    def test_whoever_commented_on_his_post_is_due_right_away_and_a_pending_invitation_is_never_due(self):
        contact, journey = self.followed(source=Contact.Source.OWN_POST)
        self.assertEqual(journey.next_at, contact.followed_at)
        state = comprador._fold(comprador._touches(journey))
        self.assertIsNone(calentamiento.invite_at(state, Contact(stage='invited', source='manual')))

    def test_with_the_switch_off_it_is_48_hours_after_the_follow(self):
        with patch.dict(os.environ, {'BUYER_WARMUP_ENABLED': 'false'}):
            contact, journey = self.followed()
            self.assertEqual(journey.next_at, contact.followed_at + 48 * H)


class HeatTests(WarmupBase):
    def signal(self, contact, fecha, fuente='https://news.example/round'):
        senal = {'tipo': 'ronda', 'fecha': fecha, 'fuente': fuente, 'evidencia': 'Levantó una ronda.', 'visto': None}
        classification = dict(contact.classification, stage_check={'state': 'ok', 'senales': [senal]})
        Contact.objects.filter(pk=contact.pk).update(classification=classification)
        return Contact.objects.get(pk=contact.pk)

    def test_weights_halve_after_30_days_and_buying_signals_need_a_source(self):
        now = timezone.now()
        contact, _ = self.followed()
        self.their_comment(contact, now - 2 * D)    # Alta: 3
        self.their_comment(contact, now - 40 * D)   # Alta, old: 1.5
        comprador.update(contact)
        self.assertEqual(calentamiento.heat(contact, now)['peso'], 4.5)
        contact = self.signal(contact, (now - 5 * D).date().isoformat())
        heat = calentamiento.heat(contact, now)
        self.assertEqual((heat['peso'], heat['nivel'], heat['senales'], heat['senales_de_compra']), (6.5, 'caliente', 2, 1))
        self.assertEqual(calentamiento.heats([contact], now), {contact.pk: 6.5})
        contact = self.signal(contact, '', fuente='')  # without a source it never counts
        self.assertEqual(calentamiento.heat(contact, now)['peso'], 4.5)
        contact = self.signal(contact, '')  # undated: half
        self.assertEqual(calentamiento.heat(contact, now)['peso'], 5.5)
        self.assertEqual(calentamiento.level(0), 'frio')
        self.assertEqual(calentamiento.level(1), 'tibio')

    def test_temperature_carries_the_weight_only_with_the_switch(self):
        contact, _ = self.followed()
        self.their_comment(contact, timezone.now() - D)
        comprador.update(contact)
        self.assertEqual(comprador.temperature(contact)['peso'], 3)
        with patch.dict(os.environ, {'BUYER_WARMUP_ENABLED': 'false'}):
            self.assertNotIn('peso', comprador.temperature(contact))

    def test_the_warmest_buyer_goes_first_after_the_region_and_the_role(self):
        cold, _ = self.followed('bea-cold', 'Bea Cold')
        warm, _ = self.followed('cris-warm', 'Cris Warm')
        Contact.objects.filter(pk=cold.pk).update(classification=dict(cold.classification, confidence=0.95))
        warm = self.signal(warm, timezone.now().date().isoformat())
        rows = list(Contact.objects.filter(pk__in=[cold.pk, warm.pk]))
        self.assertEqual([c.display_name for c in red.prioritized(rows)], ['Cris Warm', 'Bea Cold'])
        with patch.dict(os.environ, {'BUYER_WARMUP_ENABLED': 'false'}):
            self.assertEqual([c.display_name for c in red.prioritized(rows)], ['Bea Cold', 'Cris Warm'])


class BuyingSignalTests(WarmupBase):
    def test_only_signals_citing_a_received_url_count(self):
        raw = [{'tipo': 'ronda', 'fecha': '2026-10', 'source_url': 'https://a.example', 'evidencia': 'Seed'},
               {'tipo': 'contratacion', 'fecha': 'last week', 'source_url': 'https://a.example', 'evidencia': 'AE'},
               {'tipo': 'expansion', 'fecha': '2026-11-02', 'source_url': 'https://other.example', 'evidencia': 'x'},
               {'tipo': 'otra', 'source_url': 'https://a.example'}, 'basura']
        out = calentamiento.buying_signals_from(raw, {'https://a.example'}, 'visto')
        self.assertEqual([(s['tipo'], s['fecha'], s['fuente']) for s in out],
                         [('ronda', '2026-10', 'https://a.example'), ('contratacion', '', 'https://a.example')])

    def stage_check(self, senales):
        contact, _ = self.followed()
        Contact.objects.filter(pk=contact.pk).update(stage='fit', classification=dict(contact.classification, stage_check={'state': 'pending'}))
        source = research.Source('s1', 'https://news.example/acme', 'Acme', 'Acme raised a seed round', '2026-11-12T00:00:00+00:00')
        result = research.ResearchResult('q', 'complete', '2026-11-12T00:00:00+00:00', (research.Finding('Acme raised a seed round.', ('s1',)),),
                                         (source,), usage={'model': 'claude-sonnet-5-5'})
        calls = []

        def claude(system, message, **kwargs):
            calls.append({'system': system, 'schema': kwargs['output_schema']})
            data = {'verdict': 'confirmado', 'evidence': 'Levantó una ronda semilla.', 'source_urls': ['https://news.example/acme']}
            if 'senales' in kwargs['output_schema']['properties']:
                data['senales'] = senales
            return {'text': json.dumps(data), 'model': 'claude-sonnet-5-5'}
        with patch('team_backend.research.research', return_value=result), patch('knowledge.providers.claude', side_effect=claude), \
                patch.dict(os.environ, {'NETWORK_STAGE_CHECK': 'true'}):
            red.check_stages(self.gustavo, self.account)
        return Contact.objects.get(pk=contact.pk), calls

    def test_the_stage_check_keeps_the_cited_signals_in_the_same_call(self):
        contact, calls = self.stage_check([
            {'tipo': 'ronda', 'fecha': '2026-11-01', 'source_url': 'https://news.example/acme', 'evidencia': 'Seed de 3 M'},
            {'tipo': 'contratacion', 'fecha': '', 'source_url': 'https://invented.example', 'evidencia': 'Sin fuente recibida'}])
        self.assertEqual(len(calls), 1)  # no new paid call
        self.assertIn(red.BUY_SIGNALS_SYSTEM, calls[0]['system'])
        check = contact.classification['stage_check']
        self.assertEqual((check['state'], [s['tipo'] for s in check['senales']]), ('ok', ['ronda']))
        self.assertEqual(calentamiento.buying_signals(contact)[0]['fuente'], 'https://news.example/acme')

    def test_with_the_switch_off_the_stage_check_is_todays(self):
        with patch.dict(os.environ, {'BUYER_WARMUP_ENABLED': 'false'}):
            contact, calls = self.stage_check([])
        self.assertEqual((calls[0]['system'], calls[0]['schema']), (red.stage_system(), red.STAGE_SCHEMA))
        self.assertNotIn('senales', contact.classification['stage_check'])


class ReadTests(WarmupBase):
    def post_of(self, contact, hours_ago=2, suffix='p'):
        user = self.fake.state['users'][contact.provider_user_id]
        pid = f'activity:{user["public_identifier"]}-{suffix}'
        self.fake.state['posts'][pid] = {'id': pid, 'share_url': 'https://www.linkedin.com/feed/update/urn:li:' + pid, 'text': 'A post',
                                         'created_at': (timezone.now() - hours_ago * H).isoformat(), 'author': user, 'comments_counter': 0,
                                         'reactions_counter': [], 'reposts_counter': 0, 'user_reacted': False, 'is_repost': False}
        self.fake.state['comments'][pid] = []
        return pid

    def connector(self):
        from team_backend.connectors import get_connector
        return get_connector(self.account)

    def test_its_own_daily_cap_and_the_reread_interval(self):
        ana, _ = self.followed()
        beto, _ = self.followed('beto-acme', 'Beto Acme')
        self.post_of(ana)
        self.post_of(beto, hours_ago=200, suffix='old')  # older than BUYER_POST_MAX_AGE_HOURS: read but not commentable
        with patch.dict(os.environ, {'BUYER_POSTS_READ_DAILY_LIMIT': '1'}):
            first = calentamiento.read_posts(self.account, self.connector())
            self.assertEqual((first['personas'], first['tope']), (1, True))
            self.assertFalse(calentamiento.reading_due(self.account))
        out = calentamiento.read_posts(self.account, self.connector())
        self.assertEqual((out['personas'], out['tope']), (1, False))  # only the one not read yet
        self.assertEqual(calentamiento.read_posts(self.account, self.connector())['personas'], 0)  # 72 h until the next read
        self.assertEqual(set(ObservedPost.objects.values_list('referent_id', flat=True)), {None})
        self.assertEqual(AuditEvent.objects.filter(action=calentamiento.READ_ACTION).count(), 2)

    def test_the_shared_profile_allowance_also_rules(self):
        ana, _ = self.followed()
        self.post_of(ana)
        with patch.dict(os.environ, {'OPERATOR_PROFILE_READ_DAILY_LIMIT': '0'}):
            out = calentamiento.read_posts(self.account, self.connector())
        self.assertEqual((out['personas'], out['tope']), (0, True))
        self.assertFalse(ObservedPost.objects.exists())

    def test_a_resting_or_gone_buyer_is_not_read(self):
        ana, journey = self.followed()
        self.post_of(ana)
        comprador.rest(journey, BuyerJourney.RestReason.NOT_NOW, timezone.now() + 30 * D)
        self.assertEqual(calentamiento.to_read(self.account), [])
        self.assertEqual(calentamiento.read_posts(self.account, self.connector())['personas'], 0)

    def test_with_the_switch_off_nobody_is_due(self):
        ana, _ = self.followed()
        with patch.dict(os.environ, {'BUYER_WARMUP_ENABLED': 'false'}):
            self.assertFalse(calentamiento.reading_due(self.account))


class SweepTests(WarmupBase):
    def invited_after_two_comments(self, days_ago=25):
        contact, _ = self.followed(days=days_ago + 5)
        self.commented(contact, contact.followed_at + D)
        self.commented(contact, contact.followed_at + 3 * D)
        self.executed(contact, 'RED-02', timezone.now() - days_ago * D)
        Contact.objects.filter(pk=contact.pk).update(stage='invited', invited_at=timezone.now() - days_ago * D)
        return Contact.objects.get(pk=contact.pk), self.refresh(contact)

    def test_rest_and_retry_when_the_rest_is_over(self):
        contact, journey = self.invited_after_two_comments()
        now = timezone.now()
        self.assertEqual(calentamiento.sweep(self.account, now)['descanso'], 1)
        journey.refresh_from_db()
        self.assertEqual((journey.step, journey.rest_reason, journey.rest_until), ('descanso', 'invitacion_no_aceptada', now + 60 * D))
        self.assertEqual(calentamiento.sweep(self.account, now + D)['reintentos'], 0)
        out = calentamiento.sweep(self.account, now + 61 * D)
        self.assertEqual(out['reintentos'], 1)
        journey.refresh_from_db()
        retry = journey.touches.get(kind=BuyerTouch.Kind.RETRY)
        self.assertEqual((journey.step, journey.attempt, retry.detail['angulo']),
                         ('calentando', 2, 'Nuevo intento tras el descanso: otro post y otro tema'))
        self.assertNotIn('por_senal', retry.detail)
        self.assertIsNone(journey.next_at)  # the invitation is still pending: nothing to invite

    def test_the_third_attempt_rests_a_year(self):
        contact, journey = self.invited_after_two_comments()
        BuyerJourney.objects.filter(pk=journey.pk).update(attempt=3)
        now = timezone.now()
        calentamiento.sweep(self.account, now)
        journey.refresh_from_db()
        self.assertEqual(journey.rest_until, now + 365 * D)

    def test_not_rested_without_the_comments_or_before_21_days(self):
        contact, _ = self.invited_after_two_comments(days_ago=10)
        self.assertEqual(calentamiento.sweep(self.account)['descanso'], 0)
        other, _ = self.followed('beto-acme', 'Beto Acme', days=40)
        self.executed(other, 'RED-02', timezone.now() - 30 * D)
        Contact.objects.filter(pk=other.pk).update(stage='invited', invited_at=timezone.now() - 30 * D)
        self.refresh(other)
        self.assertEqual(calentamiento.sweep(self.account)['descanso'], 0)  # invited without the warm-up: phase 5

    def test_one_failure_never_stops_the_sweep(self):
        self.invited_after_two_comments()
        with patch.object(comprador, 'rest', side_effect=RuntimeError('boom')):
            out = calentamiento.sweep(self.account)
        self.assertEqual((out['descanso'], out['fallos']), (0, 1))
        self.assertTrue(AuditEvent.objects.filter(action='buyer.warmup_failed').exists())


class OldInvitationsTests(WarmupBase):
    def test_the_read_only_list_of_old_pending_invitations(self):
        old, _ = self.followed('ana-acme', 'Ana Acme', days=40)
        Contact.objects.filter(pk=old.pk).update(stage='invited', invited_at=timezone.now() - 25 * D)
        self.refresh(old)
        recent = self.contact('par-luis', 'Luis Par', stage='invited')
        Contact.objects.filter(pk=recent.pk).update(invited_at=timezone.now() - 5 * D)
        response = self.human.get('/api/v1/red/invitaciones-pendientes')
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual((data['dias'], data['total']), (21, 1))
        row = data['invitaciones'][0]
        self.assertEqual((row['nombre'], row['dias'], row['papel'], row['recorrido']['paso']), ('Ana Acme', 25, 'comprador', 'invitado'))
        self.assertEqual(self.human.get('/api/v1/red/invitaciones-pendientes?dias=3').json()['total'], 2)
        self.assertEqual(self.human.get('/api/v1/red/invitaciones-pendientes?dias=0').status_code, 400)
        self.assertEqual(self.human.get('/api/v1/red/invitaciones-pendientes?dias=abc').status_code, 400)
        self.assertEqual(self.human.get(f'/api/v1/red/invitaciones-pendientes?account={uuid.uuid4()}').status_code, 404)
        from rest_framework.test import APIClient
        self.assertIn(APIClient().get('/api/v1/red/invitaciones-pendientes').status_code, (401, 403))
        self.assertEqual(self.fake.state['writes'], 0)


class EditorialSignalsTests(WarmupBase):
    def test_a_buyers_post_is_not_an_editorial_signal(self):
        contact, _ = self.followed()
        ObservedPost.objects.create(account=self.account, provider_post_id='activity:buyer-1', author_provider_id=contact.provider_user_id,
                                    author_name=contact.display_name, text='Buyer post', posted_at=timezone.now() - H)
        self.assertEqual(editorial._signals(timezone.now()), [])
        with patch.dict(os.environ, {'BUYER_WARMUP_ENABLED': 'false'}):
            self.assertEqual([s['text'] for s in editorial._signals(timezone.now())], ['Buyer post'])


class SharesTests(SimpleTestCase):
    def test_the_share_is_configurable_and_always_sums_the_cap(self):
        with patch.dict(os.environ, {'BUYER_COMMENT_SHARE': 'compradores=8,comunidad=0,referentes=2,otro=5'}):
            self.assertEqual(calentamiento.quotas(10), {'compradores': 8, 'comunidad': 0, 'referentes': 2})
        with patch.dict(os.environ, {'BUYER_COMMENT_SHARE': 'compradores=0,comunidad=0,referentes=0'}):
            self.assertEqual(calentamiento.quotas(15), {'compradores': 8, 'comunidad': 2, 'referentes': 5})
        for cap in range(0, 30):
            self.assertEqual(sum(calentamiento.quotas(cap).values()), cap)

    def test_bounded_settings(self):
        with patch.dict(os.environ, {'BUYER_WARMUP_COMMENTS': '9', 'BUYER_WARMUP_MAX_DAYS': 'x', 'BUYER_POSTS_READ_DAILY_LIMIT': '500'}):
            self.assertEqual((calentamiento.comments_needed(), calentamiento.max_days(), calentamiento.read_cap()), (5, 14 * D, 40))
        self.assertFalse(calentamiento.enabled())
