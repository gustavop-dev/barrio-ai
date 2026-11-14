"""Cambiar una cuenta entre Unipile y directo (team_backend/proveedor.py, `operador cambiar-proveedor`): the same row
switched and switched back, what it keeps and audits, and every refusal: same provider, a malformed external id,
another row with that provider and id, an execution in flight, a login from the app in progress, nothing to go back
to, no permission, and stored provider ids unless accepted. Nothing here calls a provider."""
from datetime import timedelta
from io import StringIO

from django.contrib.auth.models import Permission, User
from django.core.management import CommandError, call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from team_backend import proveedor
from team_backend.models import ActionProposal, AuditEvent, BrowserLogin, ConnectorAccount, Contact, ObservedPost

UNIPILE_ID = 'acc_prueba0001'
SLUG = 'cuenta-prueba'


class SwitchBase(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user('gustavo', password='x')
        self.admin.user_permissions.add(Permission.objects.get(content_type__app_label='team_backend', codename='manage_jobs'))
        self.account = ConnectorAccount.objects.create(provider='unipile', external_account_id=UNIPILE_ID, label='LinkedIn',
                                                       status='running', last_checked_at=timezone.now())
        # A person id is the same for both providers: it does not stop a switch.
        self.contact = Contact.objects.create(account=self.account, provider_user_id='ACoPrueba1', source='manual')

    def fresh(self):
        return ConnectorAccount.objects.get(pk=self.account.pk)

    def post(self, **fields):
        return ObservedPost.objects.create(account=self.account, provider_post_id='WyJhY3Rpdml0eTowIl0=', **fields)

    def refused(self, call, *words):
        with self.assertRaises(proveedor.Refused) as caught:
            call()
        for word in words:
            self.assertIn(word, str(caught.exception))
        account = self.fresh()
        self.assertEqual((account.provider, account.external_account_id), ('unipile', UNIPILE_ID))
        self.assertFalse(AuditEvent.objects.filter(action='operator.account_provider_switched').exists())


class SwitchTests(SwitchBase):
    def test_the_same_row_goes_to_directo_and_back(self):
        account = proveedor.switch(self.admin, self.account, 'directo', SLUG)
        self.assertEqual(account.pk, self.account.pk)
        account = self.fresh()
        self.assertEqual((account.provider, account.external_account_id), ('directo', SLUG))
        self.assertEqual(account.previous_provider['provider'], 'unipile')
        self.assertEqual(account.previous_provider['external_account_id'], UNIPILE_ID)
        self.assertEqual(account.previous_provider['by'], 'gustavo')
        # The old provider's status is not the new one's; nothing is paused.
        self.assertEqual((account.status, account.is_locked, account.last_checked_at, account.paused), ('unknown', False, None, False))
        self.assertEqual(Contact.objects.get(pk=self.contact.pk).account_id, account.pk)
        event = AuditEvent.objects.get(action='operator.account_provider_switched')
        self.assertEqual(event.metadata, {'from_provider': 'unipile', 'to_provider': 'directo', 'back': False, 'kept_ids': {}})

        proveedor.switch_back(self.admin, account)
        account = self.fresh()
        self.assertEqual((account.provider, account.external_account_id), ('unipile', UNIPILE_ID))
        self.assertEqual((account.previous_provider['provider'], account.previous_provider['external_account_id']), ('directo', SLUG))
        self.assertTrue(AuditEvent.objects.filter(action='operator.account_provider_switched', metadata__back=True).exists())

    def test_the_command_switches_and_goes_back(self):
        out = StringIO()
        call_command('operador', '--usuario', 'gustavo', 'cambiar-proveedor', '--cuenta', str(self.account.id),
                     '--a', 'directo', '--slug', SLUG, stdout=out)
        self.assertIn('de unipile a directo', out.getvalue())
        self.assertIn('comprobar', out.getvalue())
        self.assertEqual(self.fresh().provider, 'directo')
        call_command('operador', '--usuario', 'gustavo', 'cambiar-proveedor', '--cuenta', str(self.account.id), '--volver',
                     stdout=StringIO())
        self.assertEqual(self.fresh().external_account_id, UNIPILE_ID)
        with self.assertRaises(CommandError):
            call_command('operador', '--usuario', 'gustavo', 'cambiar-proveedor', '--cuenta', str(self.account.id),
                         '--a', 'directo', '--slug', 'Con Mayúsculas', stdout=StringIO())

    def test_stored_provider_ids_stop_it_unless_accepted(self):
        self.post()
        Contact.objects.filter(pk=self.contact.pk).update(invitation_id='inv-prueba')
        self.refused(lambda: proveedor.switch(self.admin, self.account, 'directo', SLUG),
                     '1 publicaciones observadas', '1 invitaciones con su id', '--aceptar-ids-viejos')
        proveedor.switch(self.admin, self.account, 'directo', SLUG, keep_ids=True)
        self.assertEqual(self.fresh().provider, 'directo')
        self.assertEqual(ObservedPost.objects.get().account_id, self.account.pk)  # kept as it was, not translated
        event = AuditEvent.objects.get(action='operator.account_provider_switched')
        self.assertEqual(event.metadata['kept_ids'], {'publicaciones observadas': 1, 'invitaciones con su id': 1})


class RefusalTests(SwitchBase):
    def test_same_provider_bad_external_id_or_another_provider(self):
        self.refused(lambda: proveedor.switch(self.admin, self.account, 'unipile', 'acc_otra'), 'ya es de unipile')
        self.refused(lambda: proveedor.switch(self.admin, self.account, 'directo', ''), 'servicio navegador')
        self.refused(lambda: proveedor.switch(self.admin, self.account, 'directo', 'Cuenta/Prueba'), 'servicio navegador')
        fake = ConnectorAccount.objects.create(provider='fake', external_account_id='simulada', label='Simulada')
        with self.assertRaises(proveedor.Refused):
            proveedor.switch(self.admin, fake, 'directo', SLUG)
        directo = ConnectorAccount.objects.create(provider='directo', external_account_id='otra-cuenta', label='Directa')
        with self.assertRaisesMessage(proveedor.Refused, 'acc_'):
            proveedor.switch(self.admin, directo, 'unipile', 'sin-prefijo')

    def test_another_row_with_that_provider_and_id(self):
        ConnectorAccount.objects.create(provider='directo', external_account_id=SLUG, label='Cuenta de rodaje')
        self.refused(lambda: proveedor.switch(self.admin, self.account, 'directo', SLUG), 'Cuenta de rodaje')

    def test_an_execution_in_flight(self):
        post = self.post()
        for state in ('executing', 'sent', 'uncertain'):
            with self.subTest(state=state):
                ActionProposal.objects.all().delete()
                ActionProposal.objects.create(account=self.account, post=post, capability='INT-02', payload={'reaction': 'like'},
                                              payload_hash='0' * 64, state=state)
                self.refused(lambda: proveedor.switch(self.admin, self.account, 'directo', SLUG, keep_ids=True), 'en curso')

    def test_a_login_from_the_app_in_progress(self):
        directo = ConnectorAccount.objects.create(provider='directo', external_account_id='otra-cuenta', label='Directa')
        BrowserLogin.objects.create(account=directo, user=self.admin, session='sesion-ficticia',
                                    expires_at=timezone.now() + timedelta(minutes=10), state='esperando')
        with self.assertRaisesMessage(proveedor.Refused, 'conexión desde la app'):
            proveedor.switch(self.admin, directo, 'unipile', UNIPILE_ID.replace('0001', '0002'))

    def test_nothing_to_go_back_to(self):
        self.refused(lambda: proveedor.switch_back(self.admin, self.account), 'no tiene un proveedor anterior')

    def test_without_manage_jobs(self):
        other = User.objects.create_user('otra', password='x')
        with self.assertRaises(PermissionDenied):
            proveedor.switch(other, self.account, 'directo', SLUG)
        self.assertEqual(self.fresh().provider, 'unipile')
