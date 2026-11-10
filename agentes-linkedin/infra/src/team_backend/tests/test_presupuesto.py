"""One AI budget for the whole team (Gustavo, 10/11/2026): AI_MONTHLY_LIMIT_USD per calendar month plus the
AI_DAILY_FUSE_USD safety fuse, every provider and purpose together; no per-area daily caps."""
import os
import uuid
from datetime import timedelta
from unittest.mock import patch
from django.db import connection
from django.test import TransactionTestCase
from knowledge import db, presupuesto, providers


class GeneralBudgetTests(TransactionTestCase):
    def setUp(self):
        self.assertTrue(connection.settings_dict['NAME'].startswith('test_'))
        env = patch.dict(os.environ, {'AI_MONTHLY_LIMIT_USD': '100', 'AI_DAILY_FUSE_USD': '15', 'OPERATOR_TIMEZONE': 'America/Bogota'})
        env.start(); self.addCleanup(env.stop)
        for name in ('ANTHROPIC_LIMIT_USD', 'OPENAI_LIMIT_USD', 'EDITORIAL_DAILY_LLM_USD', 'IMAGE_DAILY_USD'):
            os.environ.pop(name, None)
        with db.connect() as c: c.execute('TRUNCATE usage_ledger')

    def spend(self, usd, when, provider='anthropic', purpose='prueba'):
        with db.connect() as c:
            c.execute('INSERT INTO usage_ledger(id,provider,purpose,reserved_usd,actual_usd,status,created_at) VALUES(%s,%s,%s,%s,%s,%s,%s)',
                      (str(uuid.uuid4()), provider, purpose, usd, usd, 'complete', when))

    def test_a_post_with_images_is_no_longer_cut_by_a_per_area_daily_cap(self):
        """The old caps (editorial 2 USD/day, images 1 USD/day) stopped a post with images half way."""
        providers.reserve('anthropic', 'editorial-redactor', 3)
        providers.reserve('openai', 'image-edit', 2.5)  # no OPENAI_LIMIT_USD: only the team's budget applies
        providers.reserve('anthropic', 'editorial-verificador', 2)
        self.assertEqual(presupuesto.status()['today_usd'], 7.5)

    def test_the_month_counts_every_provider_together(self):
        start = presupuesto.month_start()
        self.spend(60, start + timedelta(hours=1))
        self.spend(38, start + timedelta(hours=2), provider='openai', purpose='image-edit')
        self.spend(50, start - timedelta(days=2))  # last month does not count
        with self.assertRaisesRegex(ValueError, 'Presupuesto mensual de IA agotado'):
            providers.reserve('typesafe', 'lead-review', 2.5)
        providers.reserve('typesafe', 'lead-review', 2)

    def test_the_daily_fuse_stops_a_runaway_and_renews_tomorrow(self):
        providers.reserve('anthropic', 'editorial-director', 14)
        with self.assertRaisesRegex(ValueError, 'Tope de seguridad diario de IA'):
            providers.reserve('anthropic', 'network-classify', 1.5)
        self.assertEqual(presupuesto.left(), 1)
        tomorrow = presupuesto.day_start() + timedelta(days=1, hours=8)
        self.assertEqual(presupuesto.status(tomorrow)['left_usd'], 15)

    def test_a_piece_whose_reservation_the_ledger_refused_for_money_does_not_take_its_day(self):
        from team_backend import editorial
        from team_backend.models import ConnectorAccount, EditorialPiece
        from django.utils import timezone
        account = ConnectorAccount.objects.create(provider='linkedin_fake', external_account_id='fake-official', label='Oficial')
        today = timezone.now().date()
        for note in ('Tope de seguridad diario de IA alcanzado (AI_DAILY_FUSE_USD=15): hoy van 15 USD',
                     'Presupuesto mensual de IA agotado (AI_MONTHLY_LIMIT_USD=100): este mes van 100 USD',
                     'Ciclo detenido: cost_cap'):
            piece = EditorialPiece.objects.create(account=account, slot_date=today, scheduled_for=timezone.now(), state='failed', note=note)
            self.assertTrue(editorial.budget_stopped(piece), note)
            self.assertTrue(EditorialPiece.objects.filter(editorial.budget_stopped_q(), pk=piece.pk).exists())
        content = EditorialPiece.objects.create(account=account, slot_date=today, scheduled_for=timezone.now(), state='blocked',
                                                note='El verificador emitió blocked')
        self.assertFalse(editorial.budget_stopped(content))

    def test_a_provider_limit_is_an_optional_extra_ceiling(self):
        with patch.dict(os.environ, {'OPENAI_LIMIT_USD': '1'}):
            with self.assertRaisesRegex(ValueError, 'Límite local de openai alcanzado este mes'):
                providers.reserve('openai', 'image-edit', 1.5)
