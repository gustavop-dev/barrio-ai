"""The two LinkedIn id schemes (team_backend/ids_linkedin.py): every Unipile shape seen in production, translated to
directo and back, and every other shape refused. Ids are invented, in exactly those shapes."""
import base64
import json

from django.test import SimpleTestCase

from team_backend import ids_linkedin as ids

ACTIVITY = '7390000000000000001'
LATER = '7390000000000000099'  # a later activity: a repost of the one above
UGC = '7390000000000000050'
COMMENT = '7390000000000000123'
INVITATION = '7390000000000000777'
SECRET = 'aB3_x-9Z'
PERSON = 'ACoAAA' + 'x' * 33
THREAD = '2-' + 'QWJjZGVmZ2hpamtsbW5vcHFyc3R1dnd4eXphYmNkZWZnaGlqa2xtbm9wcQ' + '=='


def unipile_post(*urns):
    return base64.b64encode(json.dumps(list(urns), separators=(',', ':')).encode()).decode()


class ToDirectoTests(SimpleTestCase):
    def test_posts_become_their_activity_number(self):
        self.assertEqual(ids.to_directo('post', unipile_post(f'activity:{ACTIVITY}')), ACTIVITY)
        self.assertEqual(ids.to_directo('post', unipile_post(f'activity:{ACTIVITY}', f'ugcPost:{UGC}')), ACTIVITY)
        # A repost and the post it shares: the later activity, the one directo lists for the reposting person.
        self.assertEqual(ids.to_directo('post', unipile_post(f'activity:{ACTIVITY}', f'activity:{LATER}')), LATER)
        self.assertEqual(ids.to_directo('post', unipile_post(f'activity:{LATER}', f'activity:{ACTIVITY}')), LATER)

    def test_invitations_chats_people_and_comments(self):
        self.assertEqual(ids.to_directo('invitation', f'SENT_{INVITATION}'), INVITATION)
        self.assertEqual(ids.to_directo('invitation', f'RECEIVED_{INVITATION}_{SECRET}'), INVITATION)
        self.assertEqual(ids.to_directo('chat', f'CLASSIC_{THREAD}'), THREAD)
        self.assertEqual(ids.to_directo('person', PERSON), PERSON)
        self.assertEqual(ids.to_directo('comment', COMMENT), COMMENT)

    def test_any_other_shape_is_refused(self):
        refused = [
            ('post', 'activity:1'), ('post', 'no es base64!'), ('post', base64.b64encode(b'{"a":1}').decode()),
            ('post', unipile_post(f'ugcPost:{UGC}')), ('post', unipile_post(f'share:{UGC}')),
            ('post', unipile_post(f'activity:{ACTIVITY}', f'activity:{ACTIVITY}')),
            ('post', unipile_post(f'activity:{ACTIVITY}', f'activity:{LATER}', f'ugcPost:{UGC}')), ('post', ACTIVITY),
            ('invitation', INVITATION), ('invitation', f'RECEIVED_{INVITATION}_corto'), ('invitation', f'OTHER_{INVITATION}'),
            ('chat', THREAD), ('chat', f'INMAIL_{THREAD}'), ('chat', 'CLASSIC_3-abc'),
            ('person', f'urn:li:fsd_profile:{PERSON}'), ('comment', f'comment:{COMMENT}'), ('comment', ''),
        ]
        for kind, value in refused:
            with self.subTest(kind=kind, value=value), self.assertRaises(ids.Untranslatable):
                ids.to_directo(kind, value)


class ToUnipileTests(SimpleTestCase):
    def test_round_trips(self):
        self.assertEqual(ids.to_unipile('post', ACTIVITY), unipile_post(f'activity:{ACTIVITY}'))
        self.assertEqual(ids.to_directo('post', ids.to_unipile('post', ACTIVITY)), ACTIVITY)
        for value, direction, secret in ((f'SENT_{INVITATION}', 'sent', ''), (f'RECEIVED_{INVITATION}_{SECRET}', 'received', SECRET)):
            with self.subTest(value=value):
                self.assertEqual(ids.to_unipile('invitation', ids.to_directo('invitation', value), direction, secret), value)
        self.assertEqual(ids.to_unipile('chat', ids.to_directo('chat', f'CLASSIC_{THREAD}')), f'CLASSIC_{THREAD}')
        self.assertEqual(ids.to_unipile('person', PERSON), PERSON)
        self.assertEqual(ids.to_unipile('comment', COMMENT), COMMENT)

    def test_what_cannot_be_rebuilt_is_refused(self):
        # The two-activity and ugcPost forms are not rebuilt (only kept originals bring them back): the single form only.
        self.assertNotEqual(ids.to_unipile('post', LATER), unipile_post(f'activity:{ACTIVITY}', f'activity:{LATER}'))
        refused = [('post', unipile_post(f'activity:{ACTIVITY}')), ('invitation', INVITATION, ''),
                   ('invitation', INVITATION, 'received'), ('invitation', f'SENT_{INVITATION}', 'sent'),
                   ('chat', f'CLASSIC_{THREAD}'), ('comment', 'c1'), ('person', 'gustavo')]
        for kind, value, *direction in refused:
            with self.subTest(kind=kind, value=value), self.assertRaises(ids.Untranslatable):
                ids.to_unipile(kind, value, *direction)

    def test_the_shape_never_shows_the_id(self):
        self.assertEqual(ids.shape(f'RECEIVED_{INVITATION}_{SECRET}'), 'RECEIVED_' + '9' * 19 + '_xx9_x-9x')
        self.assertNotIn(ACTIVITY, ids.shape(ACTIVITY))
        self.assertTrue(ids.shape(f'CLASSIC_{THREAD}').startswith('CLASSIC_2-'))
