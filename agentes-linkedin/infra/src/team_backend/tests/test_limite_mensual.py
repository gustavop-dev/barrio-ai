"""B5: provider spend limits are monthly (calendar month in OPERATOR_TIMEZONE); `total` keeps the lifetime sum."""
import os
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from django.db import connection
from django.test import TransactionTestCase
from knowledge import db, providers


class MonthlyLimitTests(TransactionTestCase):
    def setUp(self):
        self.assertTrue(connection.settings_dict['NAME'].startswith('test_'))
        env=patch.dict(os.environ,{'ANTHROPIC_LIMIT_USD':'10','OPERATOR_TIMEZONE':'America/Bogota'})
        env.start();self.addCleanup(env.stop)
        with db.connect() as c:c.execute('TRUNCATE usage_ledger')

    def spend(self,usd,when,status='complete'):
        with db.connect() as c:
            c.execute('INSERT INTO usage_ledger(id,provider,purpose,reserved_usd,actual_usd,status,created_at) VALUES(%s,%s,%s,%s,%s,%s,%s)',
                      (str(uuid.uuid4()),'anthropic','prueba',usd,usd if status=='complete' else None,status,when))

    def test_last_month_does_not_count_against_this_month(self):
        start=providers.limit_window_start('anthropic')
        self.spend(9,start-timedelta(days=3))
        self.spend(9,start-timedelta(days=40),status='uncertain')  # an old uncertain reservation no longer blocks forever
        providers.reserve('anthropic','prueba',5)  # 9+9 spent before this month: still allowed
        self.spend(6,start+timedelta(hours=1))
        with self.assertRaisesRegex(ValueError,'Límite local de anthropic alcanzado este mes'):
            providers.reserve('anthropic','prueba',0.5)  # 5 reserved + 6 spent this month > 10 - 0.5

    def test_total_window_keeps_the_lifetime_sum(self):
        self.spend(9,providers.limit_window_start('anthropic')-timedelta(days=3))
        with patch.dict(os.environ,{'ANTHROPIC_LIMIT_WINDOW':'total'}):
            self.assertIsNone(providers.limit_window_start('anthropic'))
            with self.assertRaisesRegex(ValueError,'Límite local de anthropic alcanzado; incluye'):
                providers.reserve('anthropic','prueba',2)

    def test_the_month_starts_at_local_midnight(self):
        now=datetime(2026,12,1,4,30,tzinfo=timezone.utc)  # still 30 Nov 23:30 in Bogotá
        self.assertEqual(providers.limit_window_start('anthropic',now).isoformat(),'2026-11-01T00:00:00-05:00')
