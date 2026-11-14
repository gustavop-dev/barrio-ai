"""Cambiar una cuenta entre Unipile y directo (team_backend/proveedor.py, `operador cambiar-proveedor`): the stored ids
translated in one go and put back exactly, the dry run, what depends on them (evidence keys, open proposals' hashes,
community keys and withdrawals, the inbox mark), and every refusal. Invented ids in the real shapes; nothing here
calls a provider."""
import base64
import json
import os
from datetime import date, timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import Permission, User
from django.core.management import CommandError, call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from team_backend.tests.test_operador import OperatorBase

from team_backend import conversaciones, evidencia, operador, proveedor
from team_backend.comunidad import tombstone
from team_backend.connectors import FakeConnector
from team_backend.models import (ActionProposal, AuditEvent, BrowserLogin, CommunitySource, CommunityStudy,
                                 CommunityWithdrawal, ConnectorAccount, Contact, Conversation, EditorialPiece, InboxSeen,
                                 Job, ObservedPost, PersonEvidence, PostComment, PostMetric, ProviderIdOriginal, Referent)

UNIPILE_ID = 'acc_prueba0001'
SLUG = 'cuenta-prueba'
A, LATER, UGC, B = '7390000000000000001', '7390000000000000099', '7390000000000000050', '7390000000000000200'
COMMENT, THREAD_ROOT = '7390000000000000123', '7390000000000000120'
SENT, RECEIVED, SECRET = '7390000000000000777', '7390000000000000778', 'aB3_x-9Z'
PERSON, OTHER = 'ACoAAA' + 'a' * 33, 'ACoAAA' + 'b' * 33
THREAD = '2-QWJjZGVmZ2hpamtsbW5vcHFyc3R1dnd4eXphYmNkZWZnaGlqa2xtbm9wcQ=='


def unipile_post(*urns):
    return base64.b64encode(json.dumps(list(urns), separators=(',', ':')).encode()).decode()


SINGLE, WITH_UGC, REPOST = unipile_post(f'activity:{A}'), unipile_post(f'activity:{B}', f'ugcPost:{UGC}'), \
    unipile_post(f'activity:{UGC}', f'activity:{LATER}')


class SwitchBase(TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {'OPERATOR_PAUSED': 'false'})
        env.start()
        self.addCleanup(env.stop)
        self.admin = User.objects.create_user('gustavo', password='x')
        self.admin.user_permissions.add(Permission.objects.get(content_type__app_label='team_backend', codename='manage_jobs'))
        self.account = ConnectorAccount.objects.create(provider='unipile', external_account_id=UNIPILE_ID, label='LinkedIn',
                                                       status='running', last_checked_at=timezone.now(), paused=True,
                                                       paused_reason='Cambio de proveedor')
        self.now = timezone.now()

    def fresh(self):
        return ConnectorAccount.objects.get(pk=self.account.pk)

    def seed(self):
        """One of each stored id, as Unipile left them."""
        acc, now = self.account, self.now
        self.referent = Referent.objects.create(account=acc, public_identifier='referente', provider_user_id=OTHER, reason='r')
        self.single = ObservedPost.objects.create(account=acc, referent=self.referent, provider_post_id=SINGLE, author_provider_id=OTHER)
        self.ugc = ObservedPost.objects.create(account=acc, referent=self.referent, provider_post_id=WITH_UGC, author_provider_id=OTHER)
        self.repost = ObservedPost.objects.create(account=acc, referent=self.referent, provider_post_id=REPOST,
                                                  author_provider_id=OTHER, is_repost=True)
        # An own post, as metrics and replies read it through this account (the first LinkedIn one).
        self.piece = EditorialPiece.objects.create(account=acc, slot_date=date(2026, 11, 10), scheduled_for=now, state='skipped',
                                                   metrics={'source': 'unipile', 'unipile_post_id': SINGLE, 'impressions': 10})
        self.metric = PostMetric.objects.create(piece=self.piece, kind='24h', provider_post_id=SINGLE,
                                                commenters=[{'provider_user_id': OTHER, 'substantive': True}])
        self.comment = PostComment.objects.create(account=acc, piece=self.piece, provider_post_id=SINGLE, provider_comment_id=COMMENT,
                                                  thread_id=THREAD_ROOT, author_provider_id=OTHER, text='Buen punto')
        self.invited = Contact.objects.create(account=acc, provider_user_id=OTHER, source='manual', stage='invited',
                                              invitation_id=f'SENT_{SENT}')
        self.incoming = Contact.objects.create(account=acc, provider_user_id=PERSON, source='incoming', stage='incoming',
                                               invitation_id=f'RECEIVED_{RECEIVED}_{SECRET}')
        who = evidencia.person(acc, OTHER, 'Persona')
        self.seen = evidencia.observe(who, kind='referent_comment', source='list_comments', source_id=COMMENT,
                                      observed_at=now, referent=self.referent, post_id=SINGLE, interaction_id=COMMENT)
        self.received = evidencia.relationship(self.incoming, 'invitation', f'received:RECEIVED_{RECEIVED}_{SECRET}', now,
                                               direction='received')
        study = CommunityStudy.objects.create(account=acc, period=date(2026, 11, 1), window_start=now - timedelta(days=90),
                                              window_end=now, expires_at=now + timedelta(days=90), state='complete',
                                              positioning_version='v1')
        self.source = CommunitySource.objects.create(study=study, person=who, key=evidencia.digest(['comment', SINGLE, COMMENT]),
                                                     target=evidencia.digest(['comments', SINGLE]), kind='public_comment',
                                                     expires_at=now + timedelta(days=90))
        self.withdrawn = CommunityWithdrawal.objects.create(account=acc, key=tombstone(who.pk, self.source.key), reason='excluded')
        self.whole = CommunityWithdrawal.objects.create(account=acc, key=tombstone(who.pk), reason='excluded')
        self.comment_action = self.approved(post=self.single, capability='INT-03', payload={'text': 'Un comentario'})
        self.accept_action = self.approved(contact=self.incoming, capability='RED-04',
                                           payload={'request_id': f'RECEIVED_{RECEIVED}_{SECRET}', 'user_id': PERSON})
        inbound = {'id': 'msg-unipile-1', 'at': (now - timedelta(hours=1)).isoformat(), 'from_me': False, 'text': 'Hola, ¿hablamos?'}
        self.chat = Conversation.objects.create(account=acc, provider_chat_id=f'CLASSIC_{THREAD}', attendee_provider_id=PERSON,
                                                messages=[inbound], assessment={'message_id': 'msg-unipile-1', 'opportunity': True},
                                                closed_message_id='msg-unipile-1', last_message_at=now - timedelta(hours=1))
        InboxSeen.objects.create(item_id=conversaciones.card_id(self.chat))

    def approved(self, **fields):
        proposal = ActionProposal(account=self.account, state='approved', payload_hash='', **fields)
        proposal.payload_hash = proposal.approved_hash = operador.current_hash(proposal)
        proposal.save()
        return proposal

    def stored(self):
        """Every value a switch may touch, to compare before and after."""
        return {
            'posts': sorted(ObservedPost.objects.values_list('pk', 'provider_post_id')),
            'metrics': sorted(PostMetric.objects.values_list('pk', 'provider_post_id', 'commenters')),
            'pieces': sorted(EditorialPiece.objects.values_list('pk', 'metrics')),
            'comments': sorted(PostComment.objects.values_list('pk', 'provider_post_id', 'provider_comment_id', 'thread_id')),
            'contacts': sorted(Contact.objects.values_list('pk', 'provider_user_id', 'invitation_id')),
            'evidence': sorted(PersonEvidence.objects.values_list('pk', 'post_id', 'source_id', 'interaction_id', 'key')),
            'proposals': sorted(ActionProposal.objects.values_list('pk', 'payload', 'payload_hash', 'approved_hash', 'state')),
            'chats': sorted(Conversation.objects.values_list('pk', 'provider_chat_id', 'closed_message_id')),
            'community': sorted(CommunitySource.objects.values_list('pk', 'key', 'target')),
            'withdrawals': sorted(CommunityWithdrawal.objects.values_list('pk', 'key')),
        }


class SwitchTests(SwitchBase):
    def test_every_id_is_translated_and_what_depends_on_it_recomputed(self):
        self.seed()
        account, plan = proveedor.switch(self.admin, self.account, 'directo', SLUG)
        self.assertEqual(plan.untranslated, [])
        account.refresh_from_db()
        self.assertEqual((account.provider, account.external_account_id, account.status, account.paused), ('directo', SLUG, 'unknown', True))
        self.assertEqual(account.previous_provider['provider'], 'unipile')
        # Posts: the activity; with a ugcPost, the activity; a repost, the later activity.
        posts = dict(ObservedPost.objects.values_list('pk', 'provider_post_id'))
        self.assertEqual((posts[self.single.pk], posts[self.ugc.pk], posts[self.repost.pk]), (A, B, LATER))
        comment = PostComment.objects.get()
        self.assertEqual((comment.provider_post_id, comment.provider_comment_id, comment.thread_id), (A, COMMENT, THREAD_ROOT))
        self.assertEqual(Contact.objects.get(pk=self.invited.pk).invitation_id, SENT)
        self.assertEqual(Contact.objects.get(pk=self.incoming.pk).invitation_id, RECEIVED)
        self.assertEqual(Contact.objects.get(pk=self.incoming.pk).provider_user_id, PERSON)
        self.assertEqual(Conversation.objects.get().provider_chat_id, THREAD)
        # The own post's ids that metrics and replies call the connector with; the `source` label stays.
        self.assertEqual(PostMetric.objects.get().provider_post_id, A)
        self.assertEqual(EditorialPiece.objects.get().metrics, {'source': 'unipile', 'unipile_post_id': A, 'impressions': 10})
        # Evidence keys follow evidencia.observe's recipe with the new ids, so the next read dedupes against them.
        seen = PersonEvidence.objects.get(pk=self.seen.pk)
        self.assertEqual(seen.post_id, A)
        self.assertEqual(seen.key, evidencia.digest(['referent_comment', 'list_comments', COMMENT, str(self.referent.pk), A, COMMENT]))
        self.assertEqual(PersonEvidence.objects.get(pk=self.received.pk).source_id, f'received:{RECEIVED}')
        # Open proposals stay approved and valid for the translated target and payload.
        for action in (self.comment_action, self.accept_action):
            action.refresh_from_db()
            self.assertEqual(action.state, 'approved')
            self.assertEqual(action.approved_hash, action.payload_hash)
            self.assertEqual(action.payload_hash, operador.current_hash(action))
        self.assertEqual(self.accept_action.payload['request_id'], RECEIVED)
        # Community: the comment source and its withdrawal follow; the whole-person withdrawal never depended on ids.
        source = CommunitySource.objects.get()
        self.assertEqual((source.key, source.target), (evidencia.digest(['comment', A, COMMENT]), evidencia.digest(['comments', A])))
        self.assertEqual(CommunityWithdrawal.objects.get(pk=self.withdrawn.pk).key, tombstone(source.person_id, source.key))
        self.assertEqual(CommunityWithdrawal.objects.get(pk=self.whole.pk).key, self.whole.key)
        self.assertEqual(Conversation.objects.get().carry['from'], 'unipile')
        event = AuditEvent.objects.get(action='operator.account_provider_switched')
        self.assertEqual(event.metadata['fields']['ObservedPost.provider_post_id'], {'traducidos': 3})

    def test_switching_back_restores_the_exact_originals_and_forward_again_too(self):
        self.seed()
        before = self.stored()
        proveedor.switch(self.admin, self.account, 'directo', SLUG)
        translated = self.stored()
        self.assertNotEqual(translated, before)
        _, plan = proveedor.switch_back(self.admin, self.fresh())
        self.assertEqual(self.stored(), before)  # the two-activity post, the ugcPost and the invitation secret included
        self.assertEqual((self.fresh().provider, self.fresh().external_account_id), ('unipile', UNIPILE_ID))
        self.assertEqual(plan.counts()['ObservedPost.provider_post_id']['restaurados'], 3)
        proveedor.switch(self.admin, self.fresh(), 'directo', SLUG)
        self.assertEqual(self.stored(), translated)
        self.assertTrue(ProviderIdOriginal.objects.filter(account=self.account, provider='unipile').exists())

    def test_a_value_changed_since_the_switch_is_translated_not_restored(self):
        self.seed()
        proveedor.switch(self.admin, self.account, 'directo', SLUG)
        Contact.objects.filter(pk=self.invited.pk).update(invitation_id=B)  # a new invitation read under directo
        proveedor.switch_back(self.admin, self.fresh())
        self.assertEqual(Contact.objects.get(pk=self.invited.pk).invitation_id, f'SENT_{B}')
        self.assertEqual(Contact.objects.get(pk=self.incoming.pk).invitation_id, f'RECEIVED_{RECEIVED}_{SECRET}')

    def test_the_dry_run_counts_by_table_and_field_and_writes_nothing(self):
        self.seed()
        before = self.stored()
        plan = proveedor.preview(self.account, 'directo', SLUG)
        counts = plan.counts()
        self.assertEqual(counts['ObservedPost.provider_post_id'], {'traducidos': 3})
        self.assertEqual(counts['ObservedPost.author_provider_id'], {'idénticos': 3})
        self.assertEqual(counts['Contact.invitation_id'], {'traducidos': 2})
        self.assertEqual(counts['Conversation.provider_chat_id'], {'traducidos': 1})
        self.assertEqual(counts['PostComment.provider_comment_id'], {'idénticos': 1})
        self.assertEqual(counts['ActionProposal.payload.request_id'], {'traducidos': 1})
        self.assertEqual((len(plan.evidence_keys), len(plan.hashes), plan.conversations), (2, 2, 1))
        lines = '\n'.join(proveedor.report(plan))
        self.assertIn('ObservedPost.provider_post_id: 3 traducidos', lines)
        self.assertNotIn(A, lines)
        self.assertEqual(self.stored(), before)
        self.assertEqual(self.fresh().provider, 'unipile')
        self.assertFalse(ProviderIdOriginal.objects.exists())

    def test_an_unknown_shape_or_a_collision_refuses_unless_accepted(self):
        self.seed()
        odd = ObservedPost.objects.create(account=self.account, provider_post_id='activity:fake-1')
        twin = ObservedPost.objects.create(account=self.account, provider_post_id=unipile_post(f'activity:{B}'))  # same as self.ugc
        reaction = self.approved(post=odd, capability='INT-02', payload={'reaction': 'like'})
        before = self.stored()
        with self.assertRaises(proveedor.Refused) as caught:
            proveedor.switch(self.admin, self.account, 'directo', SLUG)
        message = str(caught.exception)
        self.assertIn('Sin traducir: ObservedPost', message)
        self.assertIn('choca con otra fila', message)
        self.assertIn('--aceptar-ids-viejos', message)
        self.assertNotIn('fake-1', message)  # the shape, never the value
        self.assertEqual(self.stored(), before)
        proveedor.switch(self.admin, self.account, 'directo', SLUG, keep_ids=True)
        posts = dict(ObservedPost.objects.values_list('pk', 'provider_post_id'))
        self.assertEqual((posts[odd.pk], posts[twin.pk], posts[self.ugc.pk], posts[self.single.pk]),
                         ('activity:fake-1', unipile_post(f'activity:{B}'), WITH_UGC, A))
        reaction.refresh_from_db()
        self.assertEqual(reaction.state, 'expired')  # never runs with the other provider's id
        self.assertEqual(ActionProposal.objects.get(pk=self.comment_action.pk).state, 'approved')

    def test_the_inbox_keeps_what_was_judged_closed_and_seen(self):
        self.seed()
        proveedor.switch(self.admin, self.account, 'directo', SLUG)
        chat = Conversation.objects.get()
        sender = {'id': PERSON, 'display_name': 'Persona', 'public_identifier': 'persona'}
        at = timezone.now() - timedelta(hours=1)
        same = {'id': '2-bWVuc2FqZQ==', 'text': 'Hola,  ¿hablamos?', 'at': at + timedelta(seconds=30), 'is_sender': False,
                'sender': sender, 'hidden': False, 'attachments': 0}
        conversaciones._from_messages(self.account, chat, [same], timezone.now())
        chat.refresh_from_db()
        self.assertEqual((chat.assessment['message_id'], chat.closed_message_id, chat.carry), (same['id'], same['id'], {}))
        self.assertTrue(InboxSeen.objects.filter(item_id=conversaciones.card_id(chat)).exists())
        self.assertNotIn(chat, conversaciones._to_assess(self.account, timezone.now()))

    def test_a_message_that_arrived_since_is_judged_as_usual(self):
        self.seed()
        proveedor.switch(self.admin, self.account, 'directo', SLUG)
        chat = Conversation.objects.get()
        newer = {'id': '2-bnVldm8=', 'text': 'Otra cosa', 'at': timezone.now(), 'is_sender': False,
                 'sender': {'id': PERSON, 'display_name': 'Persona'}, 'hidden': False, 'attachments': 0}
        conversaciones._from_messages(self.account, chat, [newer], timezone.now())
        chat.refresh_from_db()
        self.assertEqual((chat.assessment['message_id'], chat.carry), ('msg-unipile-1', {}))
        self.assertIn(chat, conversaciones._to_assess(self.account, timezone.now()))

    def test_the_command_dry_run_switch_back_and_forget(self):
        self.seed()
        out = StringIO()
        call_command('operador', '--usuario', 'gustavo', 'cambiar-proveedor', '--cuenta', str(self.account.id),
                     '--a', 'directo', '--slug', SLUG, '--prueba', stdout=out)
        self.assertIn('ObservedPost.provider_post_id: 3 traducidos', out.getvalue())
        self.assertEqual(self.fresh().provider, 'unipile')
        out = StringIO()
        call_command('operador', '--usuario', 'gustavo', 'cambiar-proveedor', '--cuenta', str(self.account.id),
                     '--a', 'directo', '--slug', SLUG, stdout=out)
        self.assertIn('de unipile a directo', out.getvalue())
        call_command('operador', '--usuario', 'gustavo', 'cambiar-proveedor', '--cuenta', str(self.account.id), '--volver',
                     stdout=StringIO())
        self.assertEqual(self.fresh().external_account_id, UNIPILE_ID)
        call_command('operador', '--usuario', 'gustavo', 'cambiar-proveedor', '--cuenta', str(self.account.id),
                     '--olvidar-originales', stdout=StringIO())
        self.assertFalse(ProviderIdOriginal.objects.exists())
        with self.assertRaises(CommandError):
            call_command('operador', '--usuario', 'gustavo', 'cambiar-proveedor', '--cuenta', str(self.account.id),
                         '--a', 'directo', '--slug', 'Con Mayúsculas', stdout=StringIO())


class RefusalTests(SwitchBase):
    def refused(self, call, *words):
        with self.assertRaises(proveedor.Refused) as caught:
            call()
        for word in words:
            self.assertIn(word, str(caught.exception))
        self.assertEqual(self.fresh().provider, 'unipile')
        self.assertFalse(AuditEvent.objects.filter(action='operator.account_provider_switched').exists())

    def switch(self, **options):
        return lambda: proveedor.switch(self.admin, self.fresh(), options.get('to', 'directo'), options.get('slug', SLUG))

    def test_same_provider_bad_external_id_or_another_row(self):
        self.refused(self.switch(to='unipile', slug='acc_otra'), 'ya es de unipile')
        self.refused(self.switch(slug=''), 'servicio navegador')
        self.refused(self.switch(slug='Cuenta/Prueba'), 'servicio navegador')
        ConnectorAccount.objects.create(provider='directo', external_account_id=SLUG, label='Cuenta de rodaje')
        self.refused(self.switch(), 'Cuenta de rodaje')
        fake = ConnectorAccount.objects.create(provider='fake', external_account_id='simulada', label='Simulada', paused=True)
        with self.assertRaisesMessage(proveedor.Refused, 'Unipile o directo'):
            proveedor.switch(self.admin, fake, 'directo', 'otra-cuenta')

    def test_not_paused_in_flight_login_job_or_study(self):
        ConnectorAccount.objects.filter(pk=self.account.pk).update(paused=False)
        self.refused(self.switch(), 'Pausa la cuenta')
        ConnectorAccount.objects.filter(pk=self.account.pk).update(paused=True)
        post = ObservedPost.objects.create(account=self.account, provider_post_id=SINGLE)
        for state in ('executing', 'sent', 'uncertain'):
            with self.subTest(state=state):
                ActionProposal.objects.all().delete()
                ActionProposal.objects.create(account=self.account, post=post, capability='INT-02', payload={'reaction': 'like'},
                                              payload_hash='0' * 64, state=state)
                self.refused(self.switch(), 'en curso')
        ActionProposal.objects.all().delete()
        login = BrowserLogin.objects.create(account=self.account, user=self.admin, session='sesion-ficticia',
                                            expires_at=timezone.now() + timedelta(minutes=10), state='esperando')
        self.refused(self.switch(), 'conexión desde la app')
        login.delete()
        job = Job.objects.create(owner=self.admin, request_hash='0' * 64, agent='operador', task='', kind='observe',
                                 params={'account': str(self.account.id)}, state='running')
        self.refused(self.switch(), 'trabajo de esta cuenta')
        job.delete()
        CommunityStudy.objects.create(account=self.account, period=date(2026, 11, 1), window_start=timezone.now(),
                                      window_end=timezone.now(), expires_at=timezone.now(), positioning_version='v1')
        self.refused(self.switch(), 'estudio de comunidad')

    def test_nothing_to_go_back_to_and_no_permission(self):
        self.refused(lambda: proveedor.switch_back(self.admin, self.account), 'no tiene un proveedor anterior')
        other = User.objects.create_user('otra', password='x')
        with self.assertRaises(PermissionDenied):
            proveedor.switch(other, self.account, 'directo', SLUG)
        self.assertEqual(self.fresh().provider, 'unipile')


class Stub:
    """One provider's view of the same two LinkedIn posts: Unipile's base64 ids or directo's activity numbers."""
    POSTS = ((A, 'Shipping agents to production is mostly evals.'), (B, 'Second post'))

    def __init__(self, provider):
        self.provider, self.written, self.comments = provider, [], {}

    def id(self, number):
        return number if self.provider == 'directo' else unipile_post(f'activity:{number}')

    def account_status(self):
        return {'status': 'running', 'is_locked': False}

    def list_user_posts(self, user_id, limit=5):
        return [{'id': self.id(n), 'share_url': f'https://www.linkedin.com/feed/update/urn:li:activity:{n}/', 'text': text,
                 'created_at': timezone.now(), 'author': {'id': OTHER, 'display_name': 'Ana', 'public_identifier': 'referente'},
                 'comments_counter': 0, 'reactions_counter': 0, 'is_repost': False} for n, text in self.POSTS]

    def list_comments(self, post_id, limit=50):
        return list(self.comments.get(post_id, []))

    def create_comment(self, post_id, text):
        self.written.append(post_id)
        self.comments.setdefault(post_id, []).append({'id': COMMENT, 'text': text, 'is_sender': True, 'author': {'id': PERSON},
                                                      'created_at': timezone.now(), 'thread_id': None, 'reply_counter': 0})
        return {'id': COMMENT}


class AfterTheSwitchTests(OperatorBase):
    """The real observe and execute paths before and after a switch, through one connector per provider."""

    def setUp(self):
        super().setUp()
        self.linkedin = ConnectorAccount.objects.create(provider='unipile', external_account_id=UNIPILE_ID, label='LinkedIn')
        Referent.objects.create(account=self.linkedin, public_identifier='referente', provider_user_id=OTHER, reason='r')
        self.stubs = {'unipile': Stub('unipile'), 'directo': Stub('directo')}
        connector = patch('team_backend.operador.get_connector',
                          side_effect=lambda account: self.stubs.get(account.provider) or FakeConnector(account.external_account_id))
        connector.start()
        self.addCleanup(connector.stop)
        notices = patch('team_backend.notificaciones.avisar')
        self.avisar = notices.start()
        self.addCleanup(notices.stop)

    def switch(self):
        ConnectorAccount.objects.filter(pk=self.linkedin.pk).update(paused=True)
        proveedor.switch(self.gustavo, ConnectorAccount.objects.get(pk=self.linkedin.pk), 'directo', SLUG)
        ConnectorAccount.objects.filter(pk=self.linkedin.pk).update(paused=False)
        return ConnectorAccount.objects.get(pk=self.linkedin.pk)

    def observatory_notices(self):
        return [c for c in self.avisar.call_args_list if c.args and c.args[0] == 'observatory']

    def test_observing_after_the_switch_finds_the_same_posts_and_says_nothing(self):
        self.assertEqual(operador.observe(self.gustavo, self.linkedin)['new_posts'], 2)
        self.assertEqual(len(self.observatory_notices()), 1)
        account = self.switch()
        summary = operador.observe(self.gustavo, account)
        self.assertEqual((summary['new_posts'], summary['seen_posts']), (0, 2))
        self.assertEqual(sorted(ObservedPost.objects.filter(account=account).values_list('provider_post_id', flat=True)), [A, B])
        self.assertEqual(len(self.observatory_notices()), 1)  # no «posts nuevos» for the same posts

    def test_an_approved_comment_runs_once_after_the_switch_on_the_same_post(self):
        operador.observe(self.gustavo, self.linkedin)
        post = ObservedPost.objects.get(account=self.linkedin, provider_post_id=unipile_post(f'activity:{A}'))
        proposal = ActionProposal(account=self.linkedin, post=post, capability='INT-03', state='approved', payload_hash='',
                                  payload={'text': 'Evals are where most of the work hides.'})
        proposal.payload_hash = proposal.approved_hash = operador.current_hash(proposal)
        proposal.save()
        account = self.switch()
        execution = operador.execute(self.gustavo, proposal.id)
        self.assertEqual((execution.state, execution.provider), ('confirmed', 'directo'))
        self.assertEqual(self.stubs['directo'].written, [A])  # the activity number, not Unipile's id
        operador.observe(self.gustavo, account)
        # Still one row per post: the autopilot's «already commented» exclusion covers it, so no second comment.
        self.assertEqual(ObservedPost.objects.filter(account=account).count(), 2)
        self.assertFalse(ObservedPost.objects.filter(account=account, provider_post_id=A)
                         .exclude(proposals__capability='INT-03').exists())
        self.assertEqual(operador.execute(self.gustavo, proposal.id).id, execution.id)
        self.assertEqual(self.stubs['directo'].written, [A])

