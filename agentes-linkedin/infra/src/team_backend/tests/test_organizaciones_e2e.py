"""Organizaciones, phase 1 (docs/plan-organizaciones.md), end to end with TWO members: Gustavo (admin, «Fundador») and a
test CTO, each with her own two accounts (the official API one that publishes and the simulated browser one that reads),
through the production functions and the fake connectors. No network and no spend.

What it pins:
- each member publishes on her own official account, never on another member's, even when that one is the newest
  official account of the installation and holds the newest credential;
- every reader (replies, Slack watchers, own-post read-back, profile, analytics) resolves the member's own account;
- a pause of one member's account stops only her writes (execute and final_write_gate); the total stop stops both;
- only the owner opens, polls, reopens or cancels her browser session and connects her official credential; the
  organization's admin cannot. Referents and experiments: the owner or the admin (referentes.require_gustavo);
- several active members and a context that does not say whose: MiembroRequerido, never a guess.
Plus: one member behaves as before organizations (existing suites re-run with one member, expectations untouched),
migration 0055, the `operador miembro` command and bootstrap_local (seed_qa: test_seed_qa).

This is the harness phases 2–7 extend. DosMiembrosBase gives each member a Persona (her member, user, client, accounts
and fakes) and the steps piece() / publish() / pause() / oauth(); a phase adds its steps here and its own test class.
What is still one for the whole installation (phase 2: caps, spacing, day schedule, ramp, notes, profile reads) is set
wide in setUp so that it does not hide a per-member rule; the phase that splits it removes the setting and tests it."""
import hashlib
import io
import os
from dataclasses import dataclass
from datetime import timedelta
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import httpx
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIClient

from team_backend import (alertas_slack, analitica, autopiloto, conexion, connectors_linkedin as li, editorial, imagenes,
                          metricas, miembros, operador, perfil, referentes, respuestas)
from team_backend.connectors import FakeConnector
from team_backend.models import (ActionExecution, AuditEvent, BrowserLogin, ConnectorAccount, EditorialPiece, Job,
                                 LinkedInCredential, Member, OperatorControl, Organization, Referent)
from team_backend.tests import test_conexion as cx
from team_backend.tests import test_metricas as met
from team_backend.tests import test_operador as op
from team_backend.tests import test_publicacion as pub
from team_backend.tests import test_respuestas as resp
from team_backend.tests.test_operador import ALL, OperatorBase
from team_backend.tests.test_publicacion import GOOD_POST, EditorialBase, answers

CTO_POST = GOOD_POST.replace('this week?', 'this quarter?')
BEFORE = ('team_backend', '0054_linea_segmento_comprador')
MIGRATION = ('team_backend', '0055_organizaciones')


@dataclass
class Persona:
    """One member as the tests drive her."""
    member: Member
    user: User
    reader: ConnectorAccount  # 'fake' (in production 'directo'): reads LinkedIn and acts as her
    official: ConnectorAccount  # 'linkedin_fake' (in production 'linkedin'): publishes her posts
    text: str  # the post she publishes here

    def client(self):
        client = APIClient()
        client.force_login(self.user)
        return client

    def browser(self):
        return FakeConnector(self.reader.external_account_id)

    def posts_api(self):
        return li.FakeLinkedInOfficial(self.official)


class DosMiembrosBase(EditorialBase):
    """ProjectApp with two ACTIVE members (the phase-7 situation): Gustavo, admin, with the accounts OperatorBase and
    EditorialBase register, and the CTO, who registers hers later, so hers are the newest of the installation."""

    def setUp(self):
        super().setUp()
        # Phase 2: CONT-09 caps are still counted for the whole installation; wide enough for both to publish today.
        env = patch.dict(os.environ, {'OPERATOR_DAILY_LIMITS': 'CONT-09=5', 'OPERATOR_WEEKLY_LIMITS': 'CONT-09=10'})
        env.start()
        self.addCleanup(env.stop)
        self.organization = Organization.objects.create(name='ProjectApp', slug='projectapp')
        gustavo = Member.objects.create(organization=self.organization, user=self.gustavo, display_name='Gustavo',
                                        role='Fundador', is_admin=True, created_at=timezone.now() - timedelta(days=90))
        month_ago = timezone.now() - timedelta(days=30)
        ConnectorAccount.objects.filter(pk__in=[self.account.pk, self.official.pk]).update(member=gustavo, created_at=month_ago)
        self.account.refresh_from_db()
        self.official.refresh_from_db()
        self.g = Persona(gustavo, self.gustavo, self.account, self.official, GOOD_POST)
        user = User.objects.create_user('cto-test', password='local-only-password')
        self.grant(user, *ALL)
        cto = Member.objects.create(organization=self.organization, user=user, display_name='CTO de prueba', role='CTO')
        # Production registration: a new account belongs to whoever registers it.
        reader = operador.register_account(user, 'fake', 'acc_fake_cto', 'Cuenta simulada del CTO')
        official = operador.register_account(user, 'linkedin_fake', 'urn:li:person:cto', 'LinkedIn simulado del CTO')
        self.cto = Persona(cto, user, reader, official, CTO_POST)
        for persona, headline in ((self.g, 'Founder of ProjectApp'), (self.cto, 'CTO at ProjectApp')):
            persona.browser().seed_person('me', persona.member.display_name, headline=headline)

    # ------------------------------------------------------------------ steps

    def piece(self, persona, days_ago=0):
        """A verified piece of `persona` on the account editorial.publishing_account picks for her, and its CONT-09
        proposal through the autonomy policy. Slot dates are still unique for the whole installation (phase 4): give
        each member her own day."""
        account = editorial.publishing_account(persona.member)
        now, text = timezone.now(), persona.text
        piece = EditorialPiece.objects.create(
            account=account, slot_date=(now - timedelta(days=days_ago)).astimezone(operador.local_tz()).date(),
            scheduled_for=now - timedelta(hours=1 + days_ago), state='ready', final_text=text,
            verification={'verdict': 'ready_for_execution', 'text_sha256': hashlib.sha256(text.encode()).hexdigest()})
        imagenes.fallback(piece, 'Fixture sin proveedores')
        proposal = operador.create_proposal(persona.user, None, 'CONT-09', {'text': text}, citations=['LI-04-M005-K01'],
                                            source='agent', piece=piece)
        proposal = autopiloto.policy_review(proposal)
        self.assertEqual(proposal.state, 'approved', proposal.risks)
        return proposal

    def publish(self, proposal):
        """The autopilot executes it: operador.execute, the only write path."""
        return operador.execute(self.autobot, proposal.id)

    def pause(self, persona, account, reason='Prueba: pausa de una cuenta'):
        operador.set_paused(persona.user, account, True, reason)

    def writes(self):
        return {'gustavo': self.g.posts_api().state['writes'], 'cto': self.cto.posts_api().state['writes']}

    def oauth(self, persona, sub, token):
        """`persona` goes through LinkedIn's OAuth and LinkedIn answers for member `sub`. Returns the redirect."""
        client = persona.client()
        start = client.get('/api/v1/linkedin/oauth/start')
        self.assertEqual(start.status_code, 302, start.content)
        state = parse_qs(urlparse(start['Location']).query)['state'][0]

        def linkedin(request):
            if request.url.path == '/oauth/v2/accessToken':
                return httpx.Response(200, json={'access_token': token, 'expires_in': 5184000,
                                                 'scope': 'openid,profile,w_member_social'})
            return httpx.Response(200, json={'sub': sub, 'name': persona.member.display_name})
        with patch.object(li, 'TRANSPORT', httpx.MockTransport(linkedin)):
            return client.get('/api/v1/linkedin/oauth/callback', {'code': 'c0de', 'state': state})['Location']

    def plan_as(self, persona, plan):
        """`persona` asks for the next piece (POST /editorial/plan) and the worker prepares it."""
        with self.claude(plan):
            response = persona.client().post('/api/v1/editorial/plan', {}, format='json')
            self.assertEqual(response.status_code, 202, response.content)
            self.drain()
        return EditorialPiece.objects.get(origin_job=response.json()['job']['id'])


class PublicarTests(DosMiembrosBase):
    def test_each_member_publishes_on_her_own_official_account(self):
        """Catch a post going out on the wrong profile: each piece is planned on and written through its member's own official account."""
        mine, hers = self.piece(self.g, 0), self.piece(self.cto, 1)
        self.assertEqual((mine.account_id, hers.account_id), (self.g.official.pk, self.cto.official.pk))
        self.assertEqual((self.publish(mine).state, self.publish(hers).state), ('sent', 'sent'))
        self.assertEqual(self.writes(), {'gustavo': 1, 'cto': 1})
        self.assertEqual([p['body']['author'] for p in self.g.posts_api().state['posts']], ['urn:li:person:fake'])
        self.assertEqual([p['text'] for p in self.cto.posts_api().state['posts']], [CTO_POST])

    def test_never_through_another_members_account_even_the_newest_with_the_newest_credential(self):
        """Catch the old «newest official account» rule: the CTO's fresh OAuth account never receives Gustavo's post."""
        # The CTO connects her LinkedIn today: the newest official account and the newest credential are hers.
        self.assertEqual(self.oauth(self.cto, 'cto123', 'AQ-token-del-cto'), '/ajustes?linkedin=ok')
        hers = ConnectorAccount.objects.get(provider='linkedin', external_account_id='urn:li:person:cto123')
        self.assertEqual(hers.member, self.cto.member)
        newest = ConnectorAccount.objects.filter(provider__in=miembros.OFFICIAL).order_by('-created_at').first()
        self.assertEqual(newest, hers)
        self.assertEqual(editorial.publishing_account(self.g.member), self.g.official)
        self.assertEqual(editorial.publishing_account(self.cto.member), hers)
        proposal = self.piece(self.g)
        self.assertEqual(proposal.account_id, self.g.official.pk)
        self.assertEqual(self.publish(proposal).state, 'sent')
        self.assertEqual(self.writes(), {'gustavo': 1, 'cto': 0})
        self.assertFalse(ActionExecution.objects.filter(proposal__account=hers).exists())
        # Each one's Ajustes › LinkedIn shows her own credential only.
        self.assertFalse(self.g.client().get('/api/v1/linkedin/status').json()['connected'])
        self.assertEqual(self.cto.client().get('/api/v1/linkedin/status').json()['member_urn'], 'urn:li:person:cto123')

    def test_planning_waits_for_phase_4_with_two_active_members_and_is_his_with_the_cto_inactive(self):
        """The calendar and the queue of ideas are still the installation's (urgente.assign_slots, phase 4): with two
        active members planning stops with the reason instead of guessing. With the CTO inactive (how `operador miembro`
        adds her until phase 7) Gustavo plans and publishes on his account, though hers is the newest connected one."""
        response = self.g.client().post('/api/v1/editorial/plan', {}, format='json')
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn('varios miembros activos', response.json()['detail'])
        self.assertFalse(Job.objects.filter(kind='prepare_piece').exists())
        self.assertEqual(self.oauth(self.cto, 'cto123', 'AQ-token-del-cto'), '/ajustes?linkedin=ok')
        miembros.save_member(self.g.user, self.cto.user.username, 'CTO de prueba', 'CTO', active=False)
        piece = self.plan_as(self.g, answers())
        self.assertEqual((piece.state, piece.account_id), ('ready', self.g.official.pk), piece.note)
        proposal = piece.proposals.get()
        autopiloto.policy_review(proposal)
        self.arrive(piece)
        self.assertEqual(self.publish(proposal).state, 'sent')
        self.assertEqual(self.writes(), {'gustavo': 1, 'cto': 0})

    def test_without_saying_whose_nothing_is_guessed(self):
        """Two active members and no member in the context: MiembroRequerido (a ValueError: 400 in a view), never the
        newest or the first account of the database."""
        for selector in (editorial.publishing_account, respuestas.reader_account, operador._own_posts_reader,
                         alertas_slack._reader, perfil.read_profile, analitica.account_for, metricas.publications,
                         respuestas.publications):
            with self.subTest(selector=selector.__qualname__), self.assertRaises(miembros.MiembroRequerido):
                selector()
        nobody = User.objects.create_user('sin-miembro', password='local-only-password')
        self.grant(nobody, *ALL)
        client = APIClient()
        client.force_login(nobody)
        response = client.post('/api/v1/editorial/plan', {}, format='json')
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn('varios miembros activos', response.json()['detail'])
        self.assertFalse(Job.objects.filter(kind='prepare_piece').exists())
        # An account without a member belongs to nobody while there are several: no selector picks it, nobody owns it.
        orphan = ConnectorAccount.objects.create(provider='linkedin_fake', external_account_id='urn:li:person:huerfana',
                                                 label='Sin miembro')
        self.assertEqual(editorial.publishing_account(self.g.member), self.g.official)
        for persona in (self.g, self.cto):
            self.assertFalse(miembros.accounts(persona.member).filter(pk=orphan.pk).exists())
            self.assertFalse(miembros.is_owner(persona.user, orphan))
        # The CTO inactive (how `operador miembro` adds her until phase 7): Gustavo is the default again, and the
        # account of nobody is his again, as before organizations (the newest official one).
        Member.objects.filter(pk=self.cto.member.pk).update(active=False)
        self.assertEqual(editorial.publishing_account(), orphan)
        self.assertEqual(respuestas.reader_account(), self.g.reader)
        self.assertTrue(miembros.is_owner(self.g.user, orphan))


class LectoresTests(DosMiembrosBase):
    def test_every_reader_resolves_the_members_own_account(self):
        """Catch a reader picked from the whole database: replies, Slack watchers, read-back, profile and analytics use her own account."""
        for persona in (self.g, self.cto):
            with self.subTest(member=persona.member.display_name):
                self.assertEqual(respuestas.reader_account(persona.member), persona.reader)
                self.assertEqual(alertas_slack._reader(persona.member), persona.reader)
                self.assertEqual(operador._own_posts_reader(persona.member).account_id, persona.reader.external_account_id)
        self.assertEqual(perfil.read_profile(self.g.member)['sections']['headline']['text'], 'Founder of ProjectApp')
        self.assertEqual(perfil.read_profile(self.cto.member)['sections']['headline']['text'], 'CTO at ProjectApp')
        # Analytics: her `directo` account; another member's is refused like an unknown one.
        mine = operador.register_account(self.g.user, 'directo', 'directo-gustavo', 'Directo de Gustavo')
        hers = operador.register_account(self.cto.user, 'directo', 'directo-cto', 'Directo del CTO')
        self.assertEqual((analitica.account_for(member=self.g.member), analitica.account_for(member=self.cto.member)),
                         (mine, hers))
        with self.assertRaises(ValueError):
            analitica.account_for(mine.id, member=self.cto.member)
        response = self.cto.client().get('/api/v1/resultados/analitica', {'cuenta': str(mine.id)})
        self.assertEqual(response.status_code, 400, response.content)

    def test_reading_back_a_post_never_reads_another_members_profile(self):
        """The CTO's reader is the oldest of the installation and shows an identical post (she shared his text): it is
        not Gustavo's post, so his still goes out, and is confirmed only by reading his own profile."""
        ConnectorAccount.objects.filter(pk=self.cto.reader.pk).update(created_at=timezone.now() - timedelta(days=365))
        self.cto.browser().seed_own_post(GOOD_POST)
        proposal = self.piece(self.g)
        self.assertEqual(self.publish(proposal).state, 'sent')
        self.assertEqual(self.writes(), {'gustavo': 1, 'cto': 0})
        self.g.browser().seed_own_post(GOOD_POST, impressions=42)
        self.assertEqual(operador.reconcile(self.g.user, proposal.id).state, 'confirmed')
        proposal.piece.refresh_from_db()
        self.assertEqual(proposal.piece.metrics['impressions'], 42)

    def test_replies_and_metrics_follow_each_members_publications(self):
        """Catch replies or metrics reading another member's posts: each member's publications are hers only."""
        mine, hers = self.piece(self.g, 0), self.piece(self.cto, 1)
        self.publish(mine)
        self.publish(hers)
        self.assertEqual([p.pk for _, p in respuestas.publications(member=self.g.member)], [mine.piece_id])
        self.assertEqual([p.pk for _, p in respuestas.publications(member=self.cto.member)], [hers.piece_id])
        self.assertEqual([e.proposal_id for e, _ in metricas.publications(member=self.g.member)], [mine.pk])
        self.assertEqual([e.proposal_id for e, _ in metricas.publications(member=self.cto.member)], [hers.pk])


class PausasTests(DosMiembrosBase):
    def test_a_pause_of_one_member_stops_only_her_writes(self):
        """Catch a global pause check in execute: the CTO's pause blocks only her posts, and Gustavo's only his."""
        mine, hers = self.piece(self.g, 0), self.piece(self.cto, 1)
        self.pause(self.cto, self.cto.reader)
        self.assertEqual(self.publish(mine).state, 'sent')
        with self.assertRaisesMessage(operador.OperatorBlocked, 'Otro conector de la misma cuenta está en pausa.'):
            self.publish(hers)
        self.assertEqual(self.writes(), {'gustavo': 1, 'cto': 0})
        operador.set_paused(self.cto.user, self.cto.reader, False)
        self.pause(self.g, self.g.reader)
        self.assertEqual(self.publish(hers).state, 'sent')
        with self.assertRaisesMessage(operador.OperatorBlocked, 'Otro conector de la misma cuenta está en pausa.'):
            self.publish(self.piece(self.g, 2))
        self.assertEqual(self.writes(), {'gustavo': 1, 'cto': 1})

    def test_the_last_gate_before_writing_sees_only_her_own_pauses(self):
        """A pause that arrives during the slow preflight (the image upload) of a post: another member's lets it go
        out; her own stops it before the write (final_write_gate)."""
        upload = imagenes.upload

        def pausing(account):
            def slow_upload(piece, connector):
                ConnectorAccount.objects.filter(pk=account.pk).update(paused=True, paused_reason='Llegó durante la subida')
                return upload(piece, connector)
            return patch('team_backend.imagenes.upload', side_effect=slow_upload)
        with pausing(self.cto.reader):
            self.assertEqual(self.publish(self.piece(self.g, 0)).state, 'sent')
        operador.set_paused(self.cto.user, self.cto.reader, False)
        with pausing(self.cto.reader):
            execution = self.publish(self.piece(self.cto, 1))
        self.assertEqual((execution.state, execution.error_kind, execution.wrote), ('failed', 'policy_changed', False))
        self.assertIn('Cuenta o máquina en pausa', execution.note)
        self.assertEqual(self.writes(), {'gustavo': 1, 'cto': 0})

    def test_the_total_stop_stops_both(self):
        """Catch the total stop becoming per member: OperatorControl and OPERATOR_PAUSED stop both, also mid-preflight."""
        mine, hers = self.piece(self.g, 0), self.piece(self.cto, 1)
        control = OperatorControl.current()
        control.paused = True
        control.save()
        for proposal in (mine, hers):
            with self.assertRaisesMessage(operador.OperatorBlocked, 'Operación global pausada'):
                self.publish(proposal)
        control.paused = False
        control.save()
        with patch.dict(os.environ, {'OPERATOR_PAUSED': 'true'}):
            for proposal in (mine, hers):
                with self.assertRaisesMessage(operador.OperatorBlocked, 'Operación global pausada'):
                    self.publish(proposal)
        # And when it arrives during the preflight, the last gate stops the write.
        upload = imagenes.upload

        def stop_everything(piece, connector):
            OperatorControl.objects.filter(pk=1).update(paused=True)
            return upload(piece, connector)
        with patch('team_backend.imagenes.upload', side_effect=stop_everything):
            self.assertEqual(self.publish(hers).state, 'failed')
        self.assertEqual(self.writes(), {'gustavo': 0, 'cto': 0})


class SesionesTests(DosMiembrosBase):
    """The browser session (Conectar LinkedIn) and the official credential: only their owner. There is no route that
    disconnects a credential or closes a session other than cancelling a login (conexion.cancel)."""

    def setUp(self):
        super().setUp()
        env = patch.dict(os.environ, cx.ENV)
        env.start()
        self.addCleanup(env.stop)
        self.service = cx.FakeService()

        def request(method, url, **options):
            with httpx.Client(transport=httpx.MockTransport(self.service)) as client:
                return client.request(method, url, headers=options.get('headers'))
        mocked = patch.object(httpx, 'request', request)
        mocked.start()
        self.addCleanup(mocked.stop)
        self.directo = {p.member.pk: operador.register_account(p.user, 'directo', f'directo-{p.user.username}', 'Navegador')
                        for p in (self.g, self.cto)}

    def start(self, persona, owner):
        return persona.client().post(f'/api/v1/operador/accounts/{self.directo[owner.member.pk].id}/conexion')

    def test_only_the_owner_opens_polls_reopens_or_cancels_her_session(self):
        """Catch someone else, even the admin, reaching another member's live LinkedIn session through any login route."""
        self.assertEqual(self.start(self.cto, self.g).status_code, 403)
        self.assertEqual(self.start(self.g, self.cto).status_code, 403)  # the admin neither
        self.assertEqual(self.service.calls, [])
        started = self.start(self.g, self.g)
        self.assertEqual(started.status_code, 201, started.content)
        lid = started.json()['login']['id']
        hers = self.cto.client()
        self.assertEqual(hers.get(f'/api/v1/operador/conexiones/{lid}').status_code, 403)
        self.assertEqual(hers.post(f'/api/v1/operador/conexiones/{lid}/enlace').status_code, 403)
        self.assertEqual(hers.post(f'/api/v1/operador/conexiones/{lid}/cancelar').status_code, 403)
        self.assertEqual(BrowserLogin.objects.get(pk=lid).state, 'esperando')
        self.assertEqual(self.g.client().get(f'/api/v1/operador/conexiones/{lid}').status_code, 200)
        self.assertEqual(self.start(self.cto, self.cto).status_code, 201)
        self.assertEqual(sorted(AuditEvent.objects.filter(action='linkedin.login_started').values_list('actor__username', 'target')),
                         sorted([(p.user.username, str(self.directo[p.member.pk].id)) for p in (self.g, self.cto)]))

    def test_an_open_view_closes_when_the_account_is_no_longer_hers(self):
        """Catch a remote view that outlives its owner: the cookie stops working once the account changes hands."""
        body = self.start(self.g, self.g).json()
        cookie = self.client.get('/api/v1/linkedin/pantalla/entrar', {'ticket': body['url'].split('ticket=', 1)[1]}
                                 ).cookies[conexion.COOKIE].value
        self.assertEqual(conexion.allow(cookie), conexion.view_key(cx.SESSION))
        ConnectorAccount.objects.filter(pk=self.directo[self.g.member.pk].pk).update(member=self.cto.member)
        self.assertIsNone(conexion.allow(cookie))

    def test_the_cto_cannot_connect_or_replace_gustavos_credential(self):
        """Catch an OAuth callback overwriting another member's official credential; each one's status shows her own."""
        self.assertEqual(self.oauth(self.g, 'gus123', 'AQ-token-de-gustavo'), '/ajustes?linkedin=ok')
        his = LinkedInCredential.objects.select_related('account').get()
        self.assertEqual(his.account.member, self.g.member)
        # The CTO's browser is still logged into LinkedIn as Gustavo: LinkedIn answers with his member.
        self.assertEqual(self.oauth(self.cto, 'gus123', 'AQ-token-del-cto'), '/ajustes?linkedin=error&motivo=dueno')
        his.refresh_from_db()
        self.assertEqual((his.connected_by, li.decrypt(his.token_encrypted)), (self.g.user, 'AQ-token-de-gustavo'))
        failed = AuditEvent.objects.get(action='linkedin.oauth_failed')
        self.assertEqual((failed.actor, failed.metadata['kind']), (self.cto.user, 'owner'))
        self.assertEqual(self.oauth(self.cto, 'cto123', 'AQ-token-del-cto'), '/ajustes?linkedin=ok')
        self.assertEqual(LinkedInCredential.objects.get(member_urn='urn:li:person:cto123').account.member, self.cto.member)
        self.assertEqual(self.g.client().get('/api/v1/linkedin/status').json()['member_urn'], 'urn:li:person:gus123')
        self.assertEqual(self.cto.client().get('/api/v1/linkedin/status').json()['member_urn'], 'urn:li:person:cto123')


class DecidirTests(DosMiembrosBase):
    def test_referents_and_experiments_are_decided_by_the_owner_or_the_admin(self):
        """Catch require_gustavo still meaning «a username»: the owner or the admin decides, the other member does not."""
        cases = [(self.cto, self.g.reader, False), (self.cto, self.cto.reader, True),
                 (self.g, self.cto.reader, True), (self.g, self.g.reader, True)]  # Gustavo is the admin
        for persona, account, allowed in cases:
            with self.subTest(user=persona.user.username, account=account.external_account_id):
                self.assertEqual(referentes.is_gustavo(persona.user, account), allowed)
        with self.assertRaises(PermissionDenied):
            referentes.require_gustavo(self.cto.user, self.g.reader)
        referentes.require_gustavo(self.cto.user, self.cto.reader)
        self.assertEqual((referentes.is_gustavo(self.g.user), referentes.is_gustavo(self.cto.user)), (True, False))
        # With members, the legacy username grants nothing.
        legacy = User.objects.create_user(miembros.legacy_owner_username(), password='local-only-password')
        self.grant(legacy, *ALL)
        self.assertFalse(referentes.is_gustavo(legacy, self.g.reader))
        # Through the API: protecting one of Gustavo's referents.
        self.observed()
        referent = Referent.objects.get(account=self.g.reader)
        change = {'version': referent.revision, 'protected': True}
        self.assertEqual(self.cto.client().patch(f'/api/v1/operador/referents/{referent.id}', change, format='json').status_code, 403)
        listed = {r['id']: r for r in self.cto.client().get('/api/v1/operador/referents').json()['results']}
        self.assertFalse(listed[str(referent.id)]['can_manage_protected'])
        response = self.g.client().patch(f'/api/v1/operador/referents/{referent.id}', change, format='json')
        self.assertEqual((response.status_code, response.json()['protected']), (200, True))


# ---------------------------------------------------------------------- one member behaves as before

class UnMiembro:
    """Re-runs an existing suite with the installation's only member made by production (ensure_first_member, the rule
    of migration 0055) owning every account; the expectations are not touched."""
    # quality: allow-duplicate (same bodies on purpose: the fixture differs, one member instead of none)

    def setUp(self):
        super().setUp()
        with override_settings(REFERENTS_GUSTAVO_USERNAME=self.gustavo.get_username()):
            self.member, created = miembros.ensure_first_member()
        self.assertTrue(created)
        self.assertFalse(ConnectorAccount.objects.filter(member__isnull=True).exists())


class UnMiembroOperatorTests(UnMiembro, op.OperatorTests):
    pass


class UnMiembroOAuthTests(UnMiembro, pub.LinkedInOAuthTests):
    pass


class UnMiembroEditorialCircuitTests(UnMiembro, pub.EditorialCircuitTests):
    pass


class UnMiembroReadingTests(UnMiembro, resp.ReadingTests):
    pass


class UnMiembroPostSnapshotTests(UnMiembro, met.PostSnapshotTests):
    pass


class UnMiembroStartTests(UnMiembro, cx.StartTests):
    pass


class UnMiembroTicketTests(UnMiembro, cx.TicketTests):
    pass


class UnMiembroEndTests(UnMiembro, cx.EndTests):
    pass


class UnMiembroTests(UnMiembro, EditorialBase):
    def test_without_saying_whose_it_is_hers_as_before(self):
        """Catch a single-member installation behaving differently: every selector without a member gives what it gave before."""
        self.assertEqual(miembros.default_member(), self.member)
        self.assertEqual(editorial.publishing_account(), editorial.publishing_account(self.member))
        self.assertEqual(editorial.publishing_account(), self.official)
        self.assertEqual(respuestas.reader_account(), self.account)
        # An account registered later without a member (the robot, a script) is still hers.
        later = ConnectorAccount.objects.create(provider='linkedin_fake', external_account_id='urn:li:person:otra',
                                                label='Registrada sin miembro')
        self.assertEqual(editorial.publishing_account(), later)
        self.assertTrue(miembros.is_owner(self.gustavo, later))
        self.assertTrue(referentes.is_gustavo(self.gustavo, later))

    def test_a_pause_of_her_reader_still_stops_her_posts(self):
        """Catch the per-member pause loosening the one-member rule: her reader's pause still stops her official posts."""
        proposal = self.ready_piece(0)
        operador.set_paused(self.gustavo, self.account, True, 'Prueba')
        with self.assertRaisesMessage(operador.OperatorBlocked, 'Otro conector de la misma cuenta está en pausa.'):
            operador.execute(self.autobot, proposal.id)
        self.assertEqual(self.linkedin.state['writes'], 0)


# ---------------------------------------------------------------------- migration 0055

class MigracionTests(TransactionTestCase):
    """Migration 0055 on the historical models: an empty database, today's (Gustavo and his two accounts), no
    REFERENTS_GUSTAVO_USERNAME user, and back."""

    def setUp(self):
        self.addCleanup(self.latest)

    def at(self, target):
        executor = MigrationExecutor(connection)
        executor.migrate([target])
        return executor.loader.project_state([target]).apps

    def latest(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    def users(self, apps, *rows):
        User = apps.get_model('auth', 'User')
        start = timezone.now() - timedelta(days=400)
        return [User.objects.create(username=name, password=password, is_superuser=superuser, is_active=active,
                                    date_joined=start + timedelta(days=i), first_name=first, last_name=last)
                for i, (name, password, superuser, active, first, last) in enumerate(rows)]

    def todays_accounts(self, apps):
        Account = apps.get_model('team_backend', 'ConnectorAccount')
        return [Account.objects.create(provider='linkedin', external_account_id='urn:li:person:abc', label='LinkedIn oficial'),
                Account.objects.create(provider='directo', external_account_id='cuenta-gustavo', label='Navegador')]

    def test_an_empty_database_gets_no_member(self):
        """Catch the migration inventing a member on the CI or QA database (robots never count)."""
        apps = self.at(BEFORE)
        self.users(apps, ('barrio-autopiloto', '!robot', True, True, '', ''), ('linkedin-service', 'pbkdf2$x', True, True, '', ''))
        Account = apps.get_model('team_backend', 'ConnectorAccount')
        Account.objects.create(provider='fake', external_account_id='acc', label='Simulada')
        with override_settings(REFERENTS_GUSTAVO_USERNAME='gustavo'):
            apps = self.at(MIGRATION)
        self.assertFalse(apps.get_model('team_backend', 'Organization').objects.exists())
        self.assertFalse(apps.get_model('team_backend', 'Member').objects.exists())
        self.assertEqual(list(apps.get_model('team_backend', 'ConnectorAccount').objects.values_list('member', flat=True)), [None])

    @override_settings(REFERENTS_GUSTAVO_USERNAME='gustavo')
    def test_todays_database_gives_gustavo_both_accounts_and_goes_back(self):
        apps = self.at(BEFORE)
        self.users(apps, ('admin-antiguo', 'pbkdf2$x', True, True, '', ''), ('barrio-autopiloto', '!robot', False, True, '', ''),
                   ('gustavo', 'pbkdf2$x', True, True, 'Gustavo', 'P'))
        ids = sorted(str(a.pk) for a in self.todays_accounts(apps))
        for attempt in ('first', 'again after going back'):
            with self.subTest(attempt=attempt):
                apps = self.at(MIGRATION)
                member = apps.get_model('team_backend', 'Member').objects.select_related('organization', 'user').get()
                self.assertEqual((member.user.username, member.display_name, member.role, member.is_admin, member.active),
                                 ('gustavo', 'Gustavo P', 'Fundador', True, True))
                self.assertEqual((member.organization.slug, member.organization.name), ('projectapp', 'ProjectApp'))
                Account = apps.get_model('team_backend', 'ConnectorAccount')
                self.assertEqual(sorted(str(pk) for pk in Account.objects.filter(member=member).values_list('pk', flat=True)), ids)
                apps = self.at(BEFORE)
                tables = connection.introspection.table_names()
                self.assertFalse({'team_backend_member', 'team_backend_organization'} & set(tables))
                self.assertEqual(sorted(str(pk) for pk in apps.get_model('team_backend', 'ConnectorAccount').objects
                                        .values_list('pk', flat=True)), ids)

    @override_settings(REFERENTS_GUSTAVO_USERNAME='gustavo')
    def test_without_that_user_the_first_human_superuser(self):
        """Catch the fallback choosing a robot, an inactive user or one without a usable password."""
        apps = self.at(BEFORE)
        self.users(apps, ('barrio-autopiloto', 'pbkdf2$x', True, True, '', ''),  # a robot, even as superuser
                   ('baja', 'pbkdf2$x', True, False, '', ''),  # inactive
                   ('sin-clave', '!unusable', True, True, '', ''),  # no usable password
                   ('operator', 'pbkdf2$x', True, True, '', ''), ('posterior', 'pbkdf2$x', True, True, '', ''))
        self.todays_accounts(apps)
        apps = self.at(MIGRATION)
        member = apps.get_model('team_backend', 'Member').objects.select_related('user').get()
        self.assertEqual((member.user.username, member.display_name), ('operator', 'Gustavo'))
        self.assertEqual(apps.get_model('team_backend', 'ConnectorAccount').objects.filter(member=member).count(), 2)


# ---------------------------------------------------------------------- adding members

class AltaDeMiembrosTests(OperatorBase):
    def run_command(self, *args, user='gustavo-test'):
        out = io.StringIO()
        call_command('operador', '--usuario', user, *args, stdout=out)
        return out.getvalue()

    def first(self):
        with override_settings(REFERENTS_GUSTAVO_USERNAME=self.gustavo.get_username()):
            return miembros.ensure_first_member()[0]

    def test_the_command_adds_a_member_idempotently_and_never_a_linkedin_account(self):
        """Catch the command duplicating members, activating them by default or touching LinkedIn accounts."""
        gustavo = self.first()
        accounts = list(ConnectorAccount.objects.values_list('pk', 'member'))
        out = self.run_command('miembro', '--nombre', 'Ana CTO', '--usuario-nuevo', 'ana-cto', '--rol', 'CTO')
        self.assertIn('Miembro creado: Ana CTO (ana-cto) · CTO · inactivo · ProjectApp.', out)
        self.assertIn('manage.py changepassword ana-cto', out)
        self.assertIn('No se creó ninguna cuenta de LinkedIn', out)
        ana = Member.objects.select_related('user').get(user__username='ana-cto')
        self.assertEqual((ana.organization, ana.active, ana.is_admin), (gustavo.organization, False, False))
        self.assertFalse(ana.user.has_usable_password())
        self.assertEqual(list(ConnectorAccount.objects.values_list('pk', 'member')), accounts)
        self.assertEqual(miembros.default_member(), gustavo)  # an inactive member changes nothing yet
        out = self.run_command('miembro', '--nombre', 'Ana Pérez', '--usuario-nuevo', 'ana-cto', '--rol', 'CTO y socia', '--activo')
        self.assertIn('Miembro actualizado: Ana Pérez (ana-cto) · CTO y socia · activo · ProjectApp.', out)
        self.assertNotIn('changepassword', out)
        self.run_command('miembro', '--nombre', 'Ana Pérez', '--usuario-nuevo', 'ana-cto', '--rol', 'CTO y socia')
        self.assertEqual((Member.objects.count(), User.objects.filter(username='ana-cto').count()), (2, 1))
        self.assertTrue(Member.objects.get(pk=ana.pk).active)  # not saying keeps what she has
        self.assertEqual(AuditEvent.objects.filter(action='organization.member_saved').count(), 4)  # bootstrap + 3
        with self.assertRaises(miembros.MiembroRequerido):
            miembros.default_member()
        listing = self.run_command('miembros')
        self.assertIn('  Ana Pérez · CTO y socia · usuario ana-cto · activo', listing)
        self.assertIn(f'    fake: Cuenta simulada ({self.account.id})', listing)

    def test_only_an_active_admin_adds_members_and_wrong_input_is_refused(self):
        """Catch a non-admin, a robot, bad input or a self-demotion getting through, and any partial write when refused."""
        self.first()
        miembros.save_member(self.gustavo, 'ana-cto', 'Ana', active=True)
        before = (Member.objects.count(), User.objects.count())
        refused = [(['miembro', '--nombre', 'Otro', '--usuario-nuevo', 'otro'], 'ana-cto', 'Solo el administrador'),
                   (['miembro', '--nombre', 'Robot', '--usuario-nuevo', 'barrio-autopiloto'], 'gustavo-test', 'técnico'),
                   (['miembro', '--nombre', 'Otro', '--usuario-nuevo', 'otro usuario'], 'gustavo-test', 'Usuario inválido'),
                   (['miembro', '--nombre', 'Otro', '--usuario-nuevo', 'otro', '--grupo', 'inventado'], 'gustavo-test', 'Grupo inexistente'),
                   (['miembro', '--nombre', 'Yo', '--usuario-nuevo', 'gustavo-test', '--no-activo'], 'gustavo-test', 'No puedes desactivarte'),
                   (['miembro', '--nombre', 'Yo', '--usuario-nuevo', 'gustavo-test', '--no-admin'], 'gustavo-test', 'No puedes desactivarte')]
        for args, user, message in refused:
            with self.subTest(args=args), self.assertRaisesMessage(CommandError, message):
                self.run_command(*args, user=user)
        other = Organization.objects.create(name='Otra', slug='otra')
        stranger = User.objects.create_user('ajena')
        Member.objects.create(organization=other, user=stranger, display_name='Ajena')
        with self.assertRaisesMessage(ValueError, 'otra organización'):
            miembros.save_member(self.gustavo, 'ajena', 'Ajena')
        self.assertEqual((Member.objects.count(), User.objects.count()), (before[0] + 1, before[1] + 1))

    def test_bootstrap_local_makes_the_first_member_once(self):
        """Catch bootstrap_local (run on every start) creating a second first member or leaving accounts without owner."""
        env = {'DJANGO_ADMIN_USERNAME': 'gustavo', 'DJANGO_ADMIN_PASSWORD': 'local-only-password', 'KNOWLEDGE_API_TOKEN': ''}
        with patch.dict(os.environ, env), override_settings(REFERENTS_GUSTAVO_USERNAME='gustavo'):
            out = io.StringIO()
            call_command('bootstrap_local', stdout=out)
            self.assertIn('Organización ProjectApp: primer miembro Gustavo (gustavo), administrador.', out.getvalue())
            again = io.StringIO()
            call_command('bootstrap_local', stdout=again)
        self.assertNotIn('primer miembro', again.getvalue())
        member = Member.objects.select_related('user').get()
        self.assertEqual((member.user.username, member.is_admin, member.role), ('gustavo', True, 'Fundador'))
        self.assertEqual(list(ConnectorAccount.objects.values_list('member', flat=True)), [member.pk])
