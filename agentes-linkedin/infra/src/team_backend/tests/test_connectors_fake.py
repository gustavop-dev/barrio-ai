"""The offline connector must not age out merely because the CI calendar advances."""
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from django.test import SimpleTestCase
from team_backend.connectors import FakeConnector


class FakePostDatesTests(SimpleTestCase):
    def setUp(self):
        env=patch.dict(os.environ,{'OPERATOR_ALLOW_FAKE':'true'})
        env.start();self.addCleanup(env.stop)
        FakeConnector.reset();self.addCleanup(FakeConnector.reset)

    def test_seeded_posts_are_recent_and_ordered_on_different_calendar_dates(self):
        for now in (datetime(2026,11,9,15,tzinfo=timezone.utc),datetime(2030,1,1,tzinfo=timezone.utc)):
            with self.subTest(now=now),patch('team_backend.connectors.datetime',wraps=datetime) as clock:
                clock.now.return_value=now
                fake=FakeConnector('dates-'+str(now.year))
                user=fake.seed_user('referente','Referente',posts=(text for text in ('First post','Second post')))
                posts=fake.list_user_posts(user['id'])
                self.assertEqual([p['text'] for p in posts],['First post','Second post'])
                self.assertLess(posts[0]['created_at'],posts[1]['created_at'])
                self.assertTrue(all(now-timedelta(hours=72)<p['created_at']<=now for p in posts))

    def test_reading_posts_does_not_refresh_their_age(self):
        now=datetime(2030,1,1,tzinfo=timezone.utc)
        with patch('team_backend.connectors.datetime',wraps=datetime) as clock:
            clock.now.return_value=now
            fake=FakeConnector('aging');user=fake.seed_user('referente','Referente',posts=['A post'])
            original=fake.list_user_posts(user['id'])[0]['created_at']
            clock.now.return_value=now+timedelta(days=4)
            reread=fake.list_user_posts(user['id'])[0]['created_at']
        self.assertEqual(reread,original)
        self.assertLess(reread,now+timedelta(days=4)-timedelta(hours=72))
