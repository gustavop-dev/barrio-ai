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

Phase 2 (RitmoPorMiembroTests, ConcurrenciaTests, AjustesTests, EstadoDeGustavoTests, VigilantesTests): each member is
one LinkedIn member with her own rhythm (lock, spacing and day schedule, daily and weekly caps, profile reads, the
invitation ramp and its health, notes and tier, provider blocks); the total stop, the AI budget and «one person, one
invitation» stay the organization's; Gustavo's state of before organizations is his first member's, untouched."""
import hashlib
import importlib
import io
import json
import logging
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from datetime import timezone as dt_timezone
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import httpx
from django.apps import apps
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import OperationalError, close_old_connections, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIClient

from knowledge import db
from team_backend import (alertas_slack, analitica, autopiloto, bucle_resultados, capturas, conexion, connectors_linkedin as li, editor_visual,
                          editorial, estrategia, guardas, hechos, identidad, imagenes, metricas, miembros, operador, perfil,
                          posicionamiento, red, referentes, respuestas, voz)
from team_backend.connectors import ConnectorError, FakeConnector
from team_backend.models import (ActionExecution, ActionProposal, AudienceSnapshot, AuditEvent, BrowserLogin, BuyerJourney,
                                 Capture, ConnectorAccount, Contact, EditorialPiece, IdentityRevision, Job, LinkedInCredential,
                                 Member, MonthlyReview, Notification, ObservedPost, OperatorControl, Organization, PostComment,
                                 Referent, TeamQuestion, VoiceDocument, WeeklyPlan, WeeklySummary)
from team_backend.tests import test_capturas as cap
from team_backend.tests import test_conexion as cx
from team_backend.tests import test_estrategia as est
from team_backend.tests import test_metricas as met
from team_backend.tests import test_operador as op
from team_backend.tests import test_publicacion as pub
from team_backend.tests import test_rediseno as rd
from team_backend.tests import test_respuestas as resp
from team_backend.tests import test_resumen_semanal as rsm
from team_backend.tests import test_revision_mensual as rvm
from team_backend.tests.test_identidad_prompts import PINNED
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
        proposal through the autonomy policy. Her calendar is hers (phase 4): two members may share a day. While her
        voice is provisional (the CTO's here) the policy leaves her post waiting and she approves it, as in production."""
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
        if autopiloto.provisional_voice(persona.member):
            self.assertEqual(proposal.state, 'proposed', proposal.risks)
            operador.approve(persona.user, proposal.id, proposal.payload_hash)
            proposal.refresh_from_db()
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
        """Catch someone else, even the admin, reaching another member's live LinkedIn session through any login route.
        Phase 5: another member's account or login does not exist for her (404), as every object of another member."""
        self.assertEqual(self.start(self.cto, self.g).status_code, 404)
        self.assertEqual(self.start(self.g, self.cto).status_code, 404)  # the admin neither
        self.assertEqual(self.service.calls, [])
        started = self.start(self.g, self.g)
        self.assertEqual(started.status_code, 201, started.content)
        lid = started.json()['login']['id']
        hers = self.cto.client()
        self.assertEqual(hers.get(f'/api/v1/operador/conexiones/{lid}').status_code, 404)
        self.assertEqual(hers.post(f'/api/v1/operador/conexiones/{lid}/enlace').status_code, 404)
        self.assertEqual(hers.post(f'/api/v1/operador/conexiones/{lid}/cancelar').status_code, 404)
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

class Migraciones:
    """Moves the test database to a migration and back to the latest one when the test ends."""

    def setUp(self):
        self.addCleanup(self.latest)

    def at(self, target):
        executor = MigrationExecutor(connection)
        executor.migrate([target])
        return executor.loader.project_state([target]).apps

    def latest(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())


class MigracionTests(Migraciones, TransactionTestCase):
    """Migration 0055 on the historical models: an empty database, today's (Gustavo and his two accounts), no
    REFERENTS_GUSTAVO_USERNAME user, and back."""

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


# ---------------------------------------------------------------------- phase 2: one LinkedIn rhythm per member

class RitmoBase(DosMiembrosBase):
    """Phase 2 steps: what each member wrote, invited and noted, through the production models."""

    def contact(self, persona, uid=None, **fields):
        uid = uid or f'{persona.user.username}-{uuid.uuid4().hex[:8]}'
        return Contact.objects.create(account=persona.reader, provider_user_id=uid, display_name=uid, source='manual', **fields)

    def proposal(self, persona, capability, account=None, contact=None, payload=None, state='approved'):
        contact = contact or self.contact(persona)
        return ActionProposal.objects.create(account=account or persona.reader, contact=contact, capability=capability,
                                             payload=payload or {'user_id': contact.provider_user_id},
                                             payload_hash=uuid.uuid4().hex * 2, state=state)

    def wrote(self, persona, capability, account=None, at=None, contact=None):
        """One write of hers that LinkedIn took (what her caps count)."""
        proposal = self.proposal(persona, capability, account, contact, state='confirmed')
        return ActionExecution.objects.create(proposal=proposal, idempotency_key=uuid.uuid4().hex, provider='fake',
                                              state='confirmed', executed_by=persona.user, started_at=at or timezone.now(),
                                              wrote=True)

    def set(self, persona, **values):
        """The admin (Gustavo) sets her rhythm; production reads her accounts fresh, the test refreshes them."""
        miembros.save_settings(self.g.user, persona.member, values)
        for row in (persona.member, persona.reader, persona.official):
            row.refresh_from_db()

    def key(self, persona):
        return miembros.policy_key(persona.member)


class RitmoPorMiembroTests(RitmoBase):
    def test_each_member_publishes_her_post_of_the_day_under_her_own_cap(self):
        """Catch caps counted for the whole installation: CONT-09 is the .env's 1 a day for EACH member, so both publish
        today and neither gets a second one."""
        mine, hers = self.piece(self.g, 0), self.piece(self.cto, 1)
        self.assertEqual(self.publish(mine).state, 'sent')
        self.assertEqual((operador.capacity_left(self.g.official, 'CONT-09'), operador.capacity_left(self.cto.official, 'CONT-09')),
                         (0, 1))
        self.assertEqual(self.publish(hers).state, 'sent')
        self.assertEqual(self.writes(), {'gustavo': 1, 'cto': 1})
        with self.assertRaisesMessage(operador.OperatorBlocked, 'Tope diario o semanal de CONT-09 alcanzado'):
            self.publish(self.piece(self.g, 2))
        self.assertEqual(self.writes(), {'gustavo': 1, 'cto': 1})

    def test_spacing_and_day_schedule_are_hers_and_shared_by_her_connectors(self):
        """Catch one spacing for everybody: Gustavo's reserved gap and his last write hold both his connectors and never
        the CTO's; each one draws her own day's opening, once."""
        self.spacing_patch.stop()
        self.day_schedule_patch.stop()
        now = timezone.now()
        accounts = (self.g.reader, self.g.official, self.cto.reader, self.cto.official)
        with patch.dict(os.environ, {'OPERATOR_MIN_SPACING_SECONDS': '1200', 'OPERATOR_MAX_SPACING_SECONDS': '2400'}):
            for persona in (self.g, self.cto, self.g):  # his again the same day: never redrawn
                operador.prepare_day_schedule(now, persona.member)
            days = AuditEvent.objects.filter(action='operator.day_schedule').values_list('target', flat=True)
            self.assertEqual(sorted(days), sorted(['member', f'member:{self.cto.member.pk}']))  # the first keeps the old key
            later = now + timedelta(hours=1)  # both openings (at most 20 minutes) are over
            operador.reserve_spacing(later, member=self.g.member)
            gap = operador.policy_event('operator.schedule', member=self.g.member).metadata['gap_seconds']
            self.assertEqual([operador.spacing_ok(a, later + timedelta(seconds=60)) for a in accounts], [False, False, True, True])
            # Each one's last write holds only her own connectors.
            self.wrote(self.g, 'RED-01', at=later)
            after = later + timedelta(seconds=gap + 1)
            self.wrote(self.cto, 'RED-01', account=self.cto.official, at=after)
            self.assertEqual([operador.spacing_ok(a, after + timedelta(seconds=1)) for a in accounts], [True, True, False, False])

    def test_daily_caps_are_hers_and_her_settings_change_only_hers(self):
        """Catch writes counted across members: Gustavo spends RED-01 on his two connectors, the CTO keeps hers, and
        lowering hers never lowers his."""
        with patch.dict(os.environ, {'OPERATOR_DAILY_LIMITS': 'RED-01=2'}):
            self.wrote(self.g, 'RED-01')
            self.wrote(self.g, 'RED-01', account=self.g.official)

            def left():
                return [operador.capacity_left(a, 'RED-01') for a in (self.g.reader, self.g.official, self.cto.reader)]
            self.assertEqual(left(), [0, 0, 2])
            self.set(self.cto, OPERATOR_DAILY_LIMITS='RED-01=1')
            self.assertEqual(left(), [0, 0, 1])
            self.assertEqual((operador.limits(member=self.g.member)['RED-01'], operador.limits(member=self.cto.member)['RED-01']),
                             ((2, 100), (1, 100)))
            self.wrote(self.cto, 'RED-01')
            self.assertEqual(left(), [0, 0, 0])

    def test_profile_reads_are_hers_and_shared_by_her_connectors(self):
        """Catch one profile-read ceiling for everybody: each member's connectors share her own ceiling."""
        with patch.dict(os.environ, {'OPERATOR_PROFILE_READ_DAILY_LIMIT': '2'}):
            operador.reserve_profile_read(self.g.reader, 'prueba')
            operador.reserve_profile_read(self.g.official, 'prueba')
            with self.assertRaises(operador.ProfileReadCapReached):
                operador.reserve_profile_read(self.g.reader, 'prueba')
            operador.reserve_profile_read(self.cto.reader, 'prueba')
            self.set(self.cto, OPERATOR_PROFILE_READ_DAILY_LIMIT='1')
            with self.assertRaises(operador.ProfileReadCapReached):
                operador.reserve_profile_read(self.cto.official, 'prueba')
            self.assertEqual((operador.profile_reads_used(self.g.member), operador.profile_reads_used(self.cto.member)), (2, 1))
            self.assertEqual(alertas_slack.read_caps(self.cto.reader, timezone.now())[-1], ('perfiles', 'profile', 1, 1))
        self.assertEqual(sorted(AuditEvent.objects.filter(action='operator.profile_read').values_list('target', flat=True)),
                         sorted(['member', 'member', self.key(self.cto)]))

    def test_the_ramp_is_hers_the_cto_starts_low_and_gustavo_keeps_his(self):
        """Phase 7's CTO: her ramp starts at 5 a day (5/25,8/40,10/50 from stage 0) while Gustavo's goes on at his stage;
        each saved under her own key."""
        now = timezone.now()
        operador._audit(None, 'network.ramp', 'member', stage=2, stage_since=(now - timedelta(days=20)).isoformat(),
                        freeze_until=(now - timedelta(days=13)).isoformat(), pause_until=None, last_sample='', last_rate=None)
        self.set(self.cto, OPERATOR_INVITE_RAMP_STAGES='5/25,8/40,10/50', OPERATOR_INVITE_RAMP_START='0')
        self.assertEqual((red.ramp_limits(self.g.reader, now), red.ramp_limits(self.cto.reader, now)), ((20, 100), (5, 25)))
        self.assertEqual((red.ramp_state(now, self.g.member)['stage'], red.ramp_state(now, self.cto.member)['stage']), (2, 0))
        self.assertEqual(sorted(set(AuditEvent.objects.filter(action='network.ramp').values_list('target', flat=True))),
                         sorted(['member', self.key(self.cto)]))

    def test_her_acceptance_pauses_only_her_invitations(self):
        """Catch one invitation health for everybody: 20 mature invitations of the CTO that nobody accepted pause hers;
        Gustavo's ramp, account and invitations go on."""
        now = timezone.now()
        for _ in range(20):
            person = self.contact(self.cto, stage='invited', invited_at=now - timedelta(days=10),
                                  profile_checked_at=now - timedelta(hours=1))
            self.wrote(self.cto, 'RED-02', at=now - timedelta(days=10), contact=person)
        health = red.review_health(self.cto.reader, now)['health']
        self.assertEqual((health['mature'], health['accepted']), (20, 0))
        self.assertTrue(red.invites_blocked(now, self.cto.member)[0])
        self.assertEqual(red.ramp_limits(self.cto.reader, now), (0, 0))
        self.assertEqual(red.review_health(self.g.reader, now)['health']['mature'], 0)
        self.assertEqual(red.invites_blocked(now, self.g.member), (False, ''))
        self.assertEqual(red.ramp_limits(self.g.reader, now), (16, 80))
        self.assertEqual([ConnectorAccount.objects.get(pk=p.reader.pk).paused for p in (self.g, self.cto)], [False, True])

    def test_notes_tier_and_month_are_hers(self):
        """Catch one note quota for everybody: Gustavo's month (free, 3) and the CTO's (premium, 5) are counted, noted
        and blocked apart."""
        def noted(persona):
            person = self.contact(persona)
            proposal = self.proposal(persona, 'RED-02', contact=person, payload={
                'user_id': person.provider_user_id, 'note': 'Your post on evals was useful.', 'note_reason': 'Shared work.'})
            self.assertTrue(red.reserve_note(proposal))
        with patch.dict(os.environ, {'LINKEDIN_ACCOUNT_TIER': 'free', 'LINKEDIN_INVITE_NOTE_MONTHLY_LIMIT': '3'}):
            self.set(self.cto, LINKEDIN_ACCOUNT_TIER='premium', LINKEDIN_INVITE_NOTE_MONTHLY_LIMIT='5')
            for persona in (self.g, self.g, self.cto):
                noted(persona)
            rooms = lambda: (red.note_room(member=self.g.member), red.note_room(member=self.cto.member))  # noqa: E731
            self.assertEqual(rooms(), (1, 4))
            operador._audit(None, 'network.notes_blocked', self.key(self.cto), kind='note_quota', status=429)
            self.assertEqual(rooms(), (1, 0))  # LinkedIn refused one of hers: hers stop, his go on
        self.assertEqual(dict(AuditEvent.objects.filter(action='network.account_tier').values_list('target', 'metadata__tier')),
                         {'member': 'free', self.key(self.cto): 'premium'})

    def test_repeated_cannot_resend_pauses_only_her_invitations_and_the_person_stays_blocked_for_all(self):
        """Catch provider blocks counted for everybody: one refusal each pauses nobody; a second recipient refused to the
        CTO pauses hers. The refused person stays blocked for everyone."""
        refuse = ConnectorError('cannot resend', status=422, kind='provider/cannot_resend_yet')
        his = self.proposal(self.g, 'RED-02')
        red.provider_failure(self.g.reader, his, refuse, self.g.user)
        hers = [self.proposal(self.cto, 'RED-02') for _ in range(2)]
        red.provider_failure(self.cto.reader, hers[0], refuse, self.cto.user)

        def blocked():
            return [red.invites_blocked(member=p.member)[0] for p in (self.g, self.cto)]
        self.assertEqual(blocked(), [False, False])  # two refusals of the installation, one each
        red.provider_failure(self.cto.reader, hers[1], refuse, self.cto.user)
        self.assertEqual(blocked(), [False, True])
        self.assertEqual([ConnectorAccount.objects.get(pk=p.reader.pk).paused for p in (self.g, self.cto)], [False, True])
        self.assertTrue(red.recipient_blocked(his.payload['user_id']))
        self.assertEqual(sorted(AuditEvent.objects.filter(action='network.provider_limit').values_list('target', flat=True)),
                         sorted(['member', self.key(self.cto), self.key(self.cto)]))

    def test_a_429_pauses_only_her_invitations(self):
        """Catch a provider limit stopping the other member: LinkedIn's 429 to the CTO stops her invitations only."""
        red.provider_failure(self.cto.reader, self.proposal(self.cto, 'RED-02'),
                             ConnectorError('throttle', status=429, kind='rate_limit', pause=True))
        self.assertEqual([red.invites_blocked(member=p.member)[0] for p in (self.g, self.cto)], [False, True])
        self.assertEqual((red.ramp_limits(None, member=self.g.member), red.ramp_limits(None, member=self.cto.member)),
                         ((16, 80), (0, 0)))
        self.assertEqual([ConnectorAccount.objects.get(pk=p.reader.pk).paused for p in (self.g, self.cto)], [False, True])

    def test_one_person_is_never_invited_by_both(self):
        """«One person, one invitation» stays the organization's: once Gustavo invited someone, the CTO's invitation to
        the same person waits; another person's does not."""
        uid = self.wrote(self.g, 'RED-02').proposal.payload['user_id']
        same = self.proposal(self.cto, 'RED-02', contact=self.contact(self.cto, uid=uid))
        other = self.proposal(self.cto, 'RED-02')
        reason = 'Ya existe otra intención o envío para el destinatario'
        self.assertEqual((reason in red.execution_issues(same), reason in red.execution_issues(other)), (True, False))

    def test_the_tick_goes_on_with_two_members_and_skips_an_account_of_nobody(self):
        """Catch the autopilot stopping on an account of nobody among several members: it is skipped and counted."""
        orphan = ConnectorAccount.objects.create(provider='fake', external_account_id='acc_huerfana', label='Sin miembro')
        self.proposal(self.g, 'RED-01', account=orphan, state='proposed')
        report = autopiloto.tick(self.autobot)
        self.assertEqual(report['unowned'], 2, report)  # the account and its proposal
        self.assertFalse(ActionExecution.objects.filter(proposal__account=orphan).exists())


class ConcurrenciaTests(RitmoBase):
    def test_her_connectors_wait_for_each_other_and_two_members_never_do(self):
        """Two reservations at once on Gustavo's two connectors with one read left: exactly one gets it. While his lock is
        held, the CTO reserves hers at once and his other connector waits (lock_timeout: it never got the lock)."""
        with patch.dict(os.environ, {'OPERATOR_PROFILE_READ_DAILY_LIMIT': '1'}):
            start = threading.Barrier(2)

            def race(account):
                close_old_connections()
                try:
                    start.wait(5)
                    operador.reserve_profile_read(account, 'carrera')
                    return True
                except operador.ProfileReadCapReached:
                    return False
                finally:
                    close_old_connections()
            with ThreadPoolExecutor(max_workers=2) as pool:
                self.assertEqual(sorted(pool.map(race, [self.g.reader, self.g.official])), [False, True])
            held, done = threading.Event(), threading.Event()

            def hold():
                close_old_connections()
                try:
                    with transaction.atomic():
                        operador.policy_lock(self.g.member)
                        held.set()
                        done.wait(20)
                finally:
                    close_old_connections()

            def reserve(account):
                held.wait(5)
                close_old_connections()
                try:
                    with transaction.atomic():
                        with connection.cursor() as cursor:
                            cursor.execute("SET LOCAL lock_timeout = '3s'")
                        operador.reserve_profile_read(account, 'mientras')
                    return 'reservó'
                except OperationalError:
                    return 'esperó'
                except operador.ProfileReadCapReached:
                    return 'tope'
                finally:
                    close_old_connections()
            with ThreadPoolExecutor(max_workers=3) as pool:
                holder = pool.submit(hold)
                attempts = [pool.submit(reserve, account) for account in (self.cto.reader, self.g.official)]
                outcome = [attempt.result(30) for attempt in attempts]
                done.set()
                holder.result(30)
        self.assertEqual(outcome, ['reservó', 'esperó'])
        self.assertEqual((operador.profile_reads_used(self.g.member), operador.profile_reads_used(self.cto.member)), (1, 1))


class AjustesTests(RitmoBase):
    def run_command(self, *args, user='gustavo-test', member='cto-test'):
        out = io.StringIO()
        call_command('operador', '--usuario', user, 'ajustes', '--miembro', member, *args, stdout=out)
        return out.getvalue()

    def test_the_admin_sets_her_rhythm_validated_audited_and_only_hers(self):
        """`operador ajustes`: the admin sets the CTO's rhythm (phase 7: low ramp, «approval»); it is validated as a
        whole, audited with before and after, idempotent, and never touches Gustavo's."""
        out = self.run_command('--fijar', 'OPERATOR_INVITE_RAMP_STAGES=5/25, 8/40, 10/50', '--fijar', 'OPERATOR_INVITE_RAMP_START=0',
                               '--fijar', 'OPERATOR_AUTONOMY=INT-03=approval,RED-02=approval')
        wanted = {'OPERATOR_INVITE_RAMP_STAGES': '5/25,8/40,10/50', 'OPERATOR_INVITE_RAMP_START': '0',
                  'OPERATOR_AUTONOMY': 'INT-03=approval,RED-02=approval'}
        self.assertEqual(Member.objects.get(pk=self.cto.member.pk).settings, wanted)
        for line in ('Ritmo actualizado (auditado).', 'OPERATOR_INVITE_RAMP_START=0  [miembro]', 'OPERATOR_DAILY_LIMITS=  [entorno]'):
            self.assertIn(line, out)
        event = AuditEvent.objects.get(action='organization.member_settings')
        self.assertEqual((event.actor, event.target, event.metadata), (self.g.user, str(self.cto.member.pk), {'before': {}, 'after': wanted}))
        self.assertIn('Sin cambios', self.run_command('--fijar', 'OPERATOR_INVITE_RAMP_START=0'))
        cto = Member.objects.get(pk=self.cto.member.pk)
        self.assertEqual((autopiloto.autonomy('INT-03', cto), autopiloto.autonomy('INT-03', self.g.member)), ('approval', 'auto'))
        self.assertEqual((red.ramp_limits(None, member=cto), red.ramp_limits(None, member=self.g.member)), ((5, 25), (16, 80)))
        # Wrong input, or someone who is not the admin: nothing changes.
        with patch.dict(os.environ, {'OPERATOR_WINDOW': '07:00-21:00'}):
            for args, reason in ((('--fijar', 'OPERATOR_INVITE_RAMP_STAGES=30/150,16/80,20/100'), 'solo puede bajar'),
                                 (('--fijar', 'NO_EXISTE=1'), 'Ajuste desconocido'),
                                 (('--fijar', 'EDITORIAL_POST_TIME=23:30'), 'fuera de OPERATOR_WINDOW'),
                                 (('--fijar', 'OPERATOR_DAILY_LIMITS=RED-09=3'), 'capacidad desconocida'),
                                 (('--fijar', 'LINKEDIN_ACCOUNT_TIER=gold'), 'free, premium o sales_navigator'),
                                 (('--fijar', 'OPERATOR_INVITE_RAMP_START=0', '--quitar', 'OPERATOR_INVITE_RAMP_START'), 'a la vez')):
                with self.subTest(args=args), self.assertRaisesMessage(CommandError, reason):
                    self.run_command(*args)
        with self.assertRaisesMessage(CommandError, 'Solo el administrador'):
            self.run_command('--fijar', 'OPERATOR_INVITE_RAMP_START=2', user='cto-test', member='gustavo-test')
        self.assertEqual((Member.objects.get(pk=self.cto.member.pk).settings, Member.objects.get(pk=self.g.member.pk).settings),
                         (wanted, {}))
        self.assertEqual(AuditEvent.objects.filter(action='organization.member_settings').count(), 1)
        self.run_command('--quitar', 'OPERATOR_AUTONOMY')  # back to the .env's
        self.assertEqual(autopiloto.autonomy('INT-03', Member.objects.get(pk=self.cto.member.pk)), 'auto')


class EstadoDeGustavoTests(OperatorBase):
    """Production before phase 2: Gustavo's rhythm lives on audit events with target 'member'. Migration 0056 moves
    nothing: his first member reads the very same rows (no reset), and a second member starts her own."""

    def note(self, uid):
        contact = Contact.objects.create(account=self.account, provider_user_id=uid, display_name=uid, source='manual')
        proposal = ActionProposal.objects.create(
            account=self.account, contact=contact, capability='RED-02', state='approved', payload_hash=uuid.uuid4().hex * 2,
            payload={'user_id': uid, 'note': 'Your post on evals was useful.', 'note_reason': 'Shared work.'})
        self.assertTrue(red.reserve_note(proposal))
        ActionExecution.objects.create(proposal=ActionProposal.objects.create(
            account=self.account, contact=contact, capability='RED-01', state='confirmed', payload={'user_id': uid},
            payload_hash=uuid.uuid4().hex * 2), idempotency_key=uuid.uuid4().hex, provider='fake', state='confirmed',
            executed_by=self.gustavo, started_at=timezone.now(), wrote=True)

    def state(self, now, member=None):
        """What his rhythm says now: ramp, notes left, profile reads, the schedule he waits for, spacing and caps."""
        schedule = operador.policy_event('operator.schedule', member=member)
        return {'ramp': red.ramp_state(now, member)['stage'], 'invitations': red.ramp_limits(None, now, member),
                'notes_left': red.note_room(now, member), 'profile_reads': operador.profile_reads_used(member, now),
                'schedule': schedule.pk if schedule else None, 'spacing_ok': operador.spacing_ok(self.account, now),
                'follows_left': operador.capacity_left(self.account, 'RED-01', now)}

    def events(self):
        """Every audit row but the ones that create his member and seed his identity (phase 3)."""
        bootstrap = ['organization.member_saved', 'organization.identity_saved']
        return sorted(AuditEvent.objects.exclude(action__in=bootstrap).values_list('action', 'target', 'id'))

    def test_his_state_of_before_is_his_first_members_and_a_second_starts_her_own(self):
        """Catch a reset on deploy: the ramp at stage 1, this month's notes, today's schedule and today's profile reads
        written before organizations read exactly the same for his first member, with or without naming him, and with a
        second active member; she starts fresh under her own key."""
        self.spacing_patch.stop()
        self.day_schedule_patch.stop()
        now = timezone.now()
        env = {'LINKEDIN_INVITE_NOTE_MONTHLY_LIMIT': '3', 'OPERATOR_MIN_SPACING_SECONDS': '1200', 'LINKEDIN_ACCOUNT_TIER': 'free'}
        with patch.dict(os.environ, env):
            operador._audit(None, 'network.ramp', 'member', stage=1, stage_since=(now - timedelta(days=3)).isoformat(),
                            freeze_until=(now + timedelta(days=4)).isoformat(), pause_until=None, last_sample='', last_rate=0.5)
            operador.prepare_day_schedule(now)
            for _ in range(5):
                operador.reserve_profile_read(self.account, 'antes', now)
            self.note('antes-1')
            self.note('antes-2')
            before, rows = self.state(now), self.events()
        self.assertEqual((before['ramp'], before['notes_left'], before['profile_reads'], before['follows_left']), (1, 1, 5, 18))
        with override_settings(REFERENTS_GUSTAVO_USERNAME=self.gustavo.get_username()):
            gustavo, _ = miembros.ensure_first_member()
        self.account.refresh_from_db()
        with patch.dict(os.environ, env):
            self.assertEqual((self.state(now, gustavo), self.state(now)), (before, before))
            operador.prepare_day_schedule(now, gustavo)  # today's opening is drawn already: not again
            self.assertEqual(self.events(), rows)  # nothing moved, rewritten or added
            user = User.objects.create_user('cto-test', password='local-only-password')
            self.grant(user, *ALL)
            cto = Member.objects.create(organization=gustavo.organization, user=user, display_name='CTO de prueba', role='CTO')
            operador.register_account(user, 'fake', 'acc_fake_cto', 'Cuenta simulada del CTO')
            self.assertEqual(self.state(now, gustavo), before)
            self.assertEqual((red.ramp_state(now, cto)['stage'], red.note_room(now, cto), operador.profile_reads_used(cto, now),
                              operador.policy_event('operator.schedule', member=cto)), (1, 3, 0, None))
            self.assertEqual(miembros.policy_key(cto), f'member:{cto.pk}')


class VigilantesTests(OperatorBase):
    """Every Slack watcher without members, with one member and with two active members (the CI of phase 1: a watcher
    that cannot name a member must neither fail nor silence the others). Slack is an httpx.MockTransport."""

    def setUp(self):
        super().setUp()
        env = patch.dict(os.environ, {
            'SLACK_WEBHOOK_URL': 'https://hooks.slack.test/services/ALERTAS', 'SLACK_WEBHOOK_RESUMEN': '',
            'OPERATOR_PROFILE_READ_DAILY_LIMIT': '1', 'OPERATOR_DAILY_LIMITS': 'RED-01=1', 'OPERATOR_AUTONOMY': 'RED-01=approval',
            'OPERATOR_PROPOSAL_TTL_HOURS': '48', 'AI_MONTHLY_LIMIT_USD': '1', 'AI_DAILY_FUSE_USD': '1000',
            'BUYER_REPLY_ENABLED': 'true', 'BUYER_SEQUENCE_ENABLED': 'true', 'CALCOM_BOOKING_URL': ''})
        env.start()
        self.addCleanup(env.stop)
        self.sent = []

        def slack(request):
            self.sent.append(json.loads(request.content)['text'])
            return httpx.Response(200)
        transport = patch.object(alertas_slack, 'TRANSPORT', httpx.MockTransport(slack))
        transport.start()
        self.addCleanup(transport.stop)
        alertas_slack._watched_at = None
        self.now = timezone.now()

    def troubles(self, user, account):
        """What a member's own watchers report: her profile reads and a write cap spent today, her ramp paused and her
        account paused by LinkedIn's 429, a proposal of hers in «approval» about to expire."""
        operador.reserve_profile_read(account, 'vigilantes', self.now)
        contact = Contact.objects.create(account=account, provider_user_id=f'v-{uuid.uuid4().hex[:8]}', display_name='P', source='manual')

        def proposal(capability, state, **fields):
            return ActionProposal.objects.create(account=account, contact=contact, capability=capability, state=state,
                                                 payload={'user_id': contact.provider_user_id}, payload_hash=uuid.uuid4().hex * 2, **fields)
        ActionExecution.objects.create(proposal=proposal('RED-01', 'confirmed'), idempotency_key=uuid.uuid4().hex, provider='fake',
                                       state='confirmed', executed_by=user, started_at=self.now, wrote=True)
        red.provider_failure(account, proposal('RED-02', 'approved'), ConnectorError('throttle', status=429, kind='rate_limit', pause=True))
        proposal('RED-01', 'proposed', created_at=self.now - timedelta(hours=40))

    def watchers(self):
        """Every watcher called by itself: none may raise. [(watcher, key, text)]; a lazy text stays unbuilt."""
        alerts = []
        for watcher in alertas_slack.WATCHERS:
            for alert in watcher(self.now) or ():
                alerts.append((watcher.__name__, alert.key, '<lazy>' if callable(alert.text) else alert.text))
        return alerts

    def test_every_watcher_with_no_member_one_member_and_two(self):
        from knowledge import db
        self.troubles(self.gustavo, self.account)
        with db.connect() as c:  # the month's AI spend over AI_MONTHLY_LIMIT_USD: the organization's, one alert
            c.execute("INSERT INTO usage_ledger(id,provider,purpose,reserved_usd,actual_usd,status,usage,created_at) "
                      "VALUES(%s,'anthropic','prueba',2,2,'complete','{}',%s)", (str(uuid.uuid4()), self.now))
        AuditEvent.objects.create(action='buyer.reply_no_link', target=str(uuid.uuid4()), created_at=self.now - timedelta(minutes=1),
                                  metadata={'tipo': 'interesado'})
        nobody = self.watchers()
        his = {'cupos_de_lectura': 'cupo:perfiles.profile:agotado', 'cupos_de_escritura': 'cupo:escritura.RED-01:agotado',
               'propuestas_por_caducar': 'tuturno:caducan'}
        keys = {(name, key) for name, key, _ in nobody}
        self.assertTrue(set(his.items()) <= keys, keys)
        self.assertTrue({'rampa_en_pausa', 'cuenta_en_pausa', 'gasto_ia', 'falta_enlace_agenda'} <= {name for name, _ in keys}, keys)
        # One member (ensure_first_member, the rule of migration 0055): exactly the same keys and texts.
        with override_settings(REFERENTS_GUSTAVO_USERNAME=self.gustavo.get_username()):
            gustavo, _ = miembros.ensure_first_member()
        self.account.refresh_from_db()
        self.assertEqual(self.watchers(), nobody)
        # Two active members, the CTO with the same troubles: nothing fails, his alerts keep their keys and say his
        # name, hers carry her id and her name, and what is the organization's goes once.
        user = User.objects.create_user('cto-test', password='local-only-password')
        self.grant(user, *ALL)
        cto = Member.objects.create(organization=gustavo.organization, user=user, display_name='CTO de prueba', role='CTO')
        hers = operador.register_account(user, 'fake', 'acc_fake_cto', 'Cuenta simulada del CTO')
        self.troubles(user, hers)
        both = self.watchers()
        by_key = {key: (name, text) for name, key, text in both}
        for name, key, text in nobody:
            with self.subTest(watcher=name):
                self.assertIn(key, by_key)
                if name in ('gasto_ia', 'falta_enlace_agenda'):
                    self.assertEqual(by_key[key][1], text)  # the organization's: once, nobody's name
                    self.assertEqual([k for n, k, _ in both if n == name], [key])
                elif text != '<lazy>':
                    self.assertTrue(by_key[key][1].startswith('Barrio · Gustavo · '), by_key[key][1])
        for name, key in his.items():
            with self.subTest(watcher=name):
                self.assertTrue(by_key[f'{key}:{cto.pk}'][1].startswith('Barrio · CTO de prueba · '))
        self.assertTrue(any(n == 'rampa_en_pausa' and k.endswith(f':{cto.pk}') and t.startswith('Barrio · CTO de prueba · ')
                            for n, k, t in both))
        self.assertTrue(any(n == 'cuenta_en_pausa' and k.startswith(f'pausa:cuenta:{hers.id}:') and 'CTO de prueba' in t
                            for n, k, t in both))
        # One member's failing reader never silences the other's alerts.
        ramp_state = red.ramp_state

        def broken(now=None, member=None):
            if member is not None and member.pk == cto.pk:
                raise RuntimeError('rota')
            return ramp_state(now, member)
        with patch('team_backend.red.ramp_state', side_effect=broken), self.assertLogs('team_backend.alertas_slack', 'WARNING'):
            self.assertEqual([k for k in (a.key for a in alertas_slack.rampa_en_pausa(self.now))],
                             [k for n, k, _ in nobody if n == 'rampa_en_pausa'])
        # vigilar sends every one of them, each once.
        alertas_slack.vigilar(self.now, force=True)
        alertas_slack.vigilar(self.now, force=True)
        sent = set(AuditEvent.objects.filter(action='slack.alert').values_list('target', flat=True))
        self.assertTrue({key for _, key, text in both if text != '<lazy>'} <= sent)
        self.assertEqual(len(self.sent), len(sent))


# ====================================================================== phase 3: the identity out of the code

CTO_PROFILE = {
    'name': 'Laura Gómez',
    'identity': 'Laura Gómez es CTO: decide la arquitectura y la calidad técnica de lo que construye el equipo.',
    'company_relation': 'Es la CTO de ProjectApp.',
    'limits': 'precios y propuestas comerciales; diseño visual; experiencias o cifras inventadas; datos privados de cualquier persona',
    'personal_startups': 'no',
    'purposes.projectapp': 'contratos para ProjectApp, cuya tecnología ella dirige',
}
COMMENT = {'decision': 'comment', 'language': 'en', 'comment': 'Evals are where most of the work hides. Which failure mode do '
           'you test first in production?', 'rationale': 'Aporta un ángulo concreto.', 'citations': ['LI-03-M006-K02'],
           'claims_needing_evidence': [], 'risks': []}


def gustavo_marks():
    """What only Gustavo's identity and voice carry: his name and key token, his presentation, his relation to the
    company, his limits and his voice (the guide and his own document)."""
    seed = identidad.initial()
    member = seed['member']
    document = voz.resource(seed['voice']['resource'])
    return ['Gustavo', 'gustavo', member['identity'], member['company_relation'], member['limits'],
            seed['voice']['guide'].splitlines()[0], document.splitlines()[4][:80]]


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


class IdentidadBase(DosMiembrosBase):
    """Gustavo as migration 0058 leaves him (his profile, ProjectApp's and his voice document 1) and the CTO with the
    profile she set herself (`operador perfil`), still without a voice document."""

    def setUp(self):
        super().setUp()
        identidad.seed_first(self.g.member)
        args = [arg for field, value in CTO_PROFILE.items() for arg in ('--fijar', f'{field}={value}')]
        self.assertIn('Perfil actualizado: revisión 1 (auditada).', self.command('cto-test', 'perfil', *args))
        for persona in (self.g, self.cto):  # as a job reads them: fresh rows, not the ones cached before the profiles
            for row in (persona.member, persona.user, persona.reader, persona.official):
                row.refresh_from_db()
        self.sent = []

    def command(self, user, *args):
        out = io.StringIO()
        call_command('operador', '--usuario', user, *args, stdout=out)
        return out.getvalue()

    def model(self, *answers):
        """providers.claude, recorded: each call's system, message, schema and purpose; the answers in order."""
        queue = list(answers)

        def fake(system, message, **kwargs):
            self.sent.append({'system': system, 'message': message, 'schema': kwargs.get('output_schema'),
                              'purpose': kwargs.get('purpose')})
            return {'text': json.dumps(queue.pop(0)), 'model': 'claude-opus-5-5', 'estimated_usd': 0.01,
                    'request_id': 'req_' + str(kwargs.get('purpose'))}
        return patch('knowledge.providers.claude', side_effect=fake)

    def assertHers(self, call, name='Laura Gómez'):
        """The call carries her name and nothing that is only Gustavo's (instructions, message and schema alike)."""
        everything = json.dumps(call, ensure_ascii=False, default=str)
        for mark in gustavo_marks():
            self.assertNotIn(mark, everything)
        self.assertIn(name, call['system'])

    def observed(self, persona, pid):
        return ObservedPost.objects.create(account=persona.reader, provider_post_id=f'urn:li:activity:{pid}',
                                           author_name='Ana Autora', share_url=f'https://www.linkedin.com/feed/update/urn:li:activity:{pid}/',
                                           text='Most teams skip evals until the first incident. What do you test first?')


class IdentidadPorMiembroTests(IdentidadBase):
    """What the team writes in the CTO's name is hers: her name, presentation, limits and (provisional) voice, never
    Gustavo's. Gustavo's own texts are the ones of before (test_identidad_prompts pins all 109)."""

    def test_a_comment_is_drafted_with_her_identity_and_voice_and_his_with_his(self):
        """operador.propose_comment on each one's observed post: hers carries her name and the provisional voice (and the
        proposal says so); his system prompt is the pinned one and his proposal records his confirmed voice 1."""
        with self.model(COMMENT, COMMENT):
            hers = operador.propose_comment(self.cto.user, self.observed(self.cto, 7001).id)
            his = operador.propose_comment(self.g.user, self.observed(self.g, 7002).id)
        self.assertHers(self.sent[0])
        self.assertIn('<tono_de_voz autor="Laura Gómez" estado="provisional">', self.sent[0]['system'])
        self.assertIn(voz.resource('voz-provisional.md'), self.sent[0]['system'])
        self.assertEqual((hers.account, hers.voice), (self.cto.reader, {'tipo': 'provisional'}))
        self.assertEqual(sha(self.sent[1]['system']), PINNED['operador.comment'])
        self.assertEqual((his.account, his.voice), (self.g.reader, {'tipo': 'confirmada', 'version': 1}))

    def test_a_reply_reads_and_writes_her_key_names_and_stores_the_usual_ones(self):
        """respuestas.propose on a comment to her post: her schema asks `question_for_laura_gomez` / `ask_laura_gomez`,
        her answer is read back to the stored names, and the INT-04 proposal is hers, in the provisional voice."""
        with db.connect() as c:
            for uid in operador.REPLY_UNITS:
                c.execute('''INSERT INTO units(id,session,title,original,sha256,source_path,pointer,metadata)
                    VALUES(%s,%s,%s,'{"title":"Synthetic course fixture","limits_errors":"Do not infer facts or authority"}',
                    'fixture-hash','fixture','/units/0','{}') ON CONFLICT(id) DO NOTHING''', (uid, int(uid[3:5]), uid))
        now = timezone.now()
        piece = EditorialPiece.objects.create(account=self.cto.official, slot_date=now.date() - timedelta(days=400),
                                              scheduled_for=now - timedelta(hours=5), state='ready', final_text=CTO_POST,
                                              brief={'thesis': 'Nobody owns the evals', 'approach': 'opinion'})
        row = PostComment.objects.create(account=self.cto.reader, piece=piece, provider_post_id='urn:li:share:cto1',
                                         provider_comment_id='c-cto-1', author_name='María PM', text=resp.QUESTION,
                                         commented_at=now - timedelta(hours=1))
        answer = {'decision': 'reply', 'language': 'en', 'reply': resp.REPLY, 'rationale': 'Responde la pregunta.',
                  'citations': [resp.UNIT], 'claims_needing_evidence': [], 'risks': [], 'dm_opener': '',
                  'question_for_laura_gomez': {'question': '', 'purpose': '', 'memory_key': ''}}
        with self.model(answer), patch.dict(os.environ, {'REPLIES_ENABLED': 'true', 'REPLIES_WINDOW_HOURS': '72'}):
            result = respuestas.propose(self.cto.user, row.id)
        self.assertEqual(result['decision'], 'reply')
        call = self.sent[0]
        self.assertHers(call)
        self.assertIn('question_for_laura_gomez', call['schema']['properties'])
        self.assertIn('ask_laura_gomez', call['schema']['properties']['decision']['enum'])
        proposal = ActionProposal.objects.get(pk=result['proposal'])
        self.assertEqual((proposal.account, proposal.payload, proposal.voice), (self.cto.reader, {'text': resp.REPLY},
                                                                                {'tipo': 'provisional'}))

    def test_a_first_message_is_hers(self):
        """The steps of mensajes_comprador._draft for a buyer of her account (inputs_for, then _write): her name in the
        moment it explains and in the instructions, her provisional voice, nothing of Gustavo's."""
        from team_backend import mensajes_comprador as mc
        contact = Contact.objects.create(account=self.cto.reader, provider_user_id='ACoTom', display_name='Tom Buyer',
                                         headline='CEO at Lone Star Outfitters', location='Austin, Texas, United States',
                                         classification={'role': 'comprador', 'fit': True}, stage='connected', source='search')
        journey = BuyerJourney(contact=contact, accepted_at=timezone.now() - timedelta(days=2))
        facts = [{'id': 'h1', 'tipo': 'post', 'texto': 'Publicó sobre el inventario de sus tiendas.', 'fuente': 'post'}]
        ident = identidad.of_account(contact.account)
        data = mc.inputs_for(contact, journey, mc.MESSAGE, facts, timezone.now())
        units, _, _ = operador.course_context(operador.COMMENT_UNITS)
        answer = {'decision': 'write', 'language': 'en', 'message': 'Hi Tom, your post on inventory stuck with me.',
                  'anchor': 'h1', 'rationale': 'r', 'citations': [], 'claims_needing_evidence': [], 'risks': []}
        with self.model(answer):
            mc._write(mc.MESSAGE, data, units, 1, ident)
        self.assertHers(self.sent[0])
        self.assertIn('Aceptó la invitación de Laura Gómez', self.sent[0]['message'])
        self.assertIn('estado="provisional"', self.sent[0]['system'])

    def test_a_classification_reads_her_neighborhood_and_her_limits(self):
        """red._classify_batch on her account: the classifier reads her presentation and only her modalities; its
        criterion_version is hers, and his stays the pinned one."""
        contact = Contact.objects.create(account=self.cto.reader, provider_user_id='ACoCand', display_name='Cand Idate',
                                         headline='VP Engineering at Acme', location='Austin, Texas, United States',
                                         classification={}, stage='candidate', source='search')
        grounding = {'course_missing': [], 'course_version': 'bib-v2', 'criterion_sources': {}}
        with self.model({'contacts': []}), patch('team_backend.operador.role_context', return_value=('ctx', grounding)), \
                patch('team_backend.red._enrich', side_effect=lambda account, rows: rows):
            red._classify_batch(self.cto.user, self.cto.reader, timezone.now(), 10)
        call = self.sent[0]
        self.assertHers(call)
        self.assertIn(CTO_PROFILE['identity'], call['system'])
        self.assertNotIn('personal_startups', call['system'])  # not her modality
        self.assertIn(str(contact.id), call['message'])
        his = red.criterion_version(red.classify_system(self.g.member), 0.6, 'bib-v2', '').rsplit(':', 1)[1]
        hers = red.criterion_version(call['system'], 0.6, 'bib-v2', '').rsplit(':', 1)[1]
        self.assertEqual(sha(his), PINNED['red.criterion_version'])
        self.assertNotEqual(hers, his)

    def test_an_editorial_piece_is_directed_and_written_as_hers(self):
        """editorial._stage (director, then redactor) on her piece: her limits and key names reach the director, the
        stored brief keeps `questions_for_gustavo`, and the writer uses her provisional voice, recorded on the piece."""
        now = timezone.now()
        piece = EditorialPiece.objects.create(account=self.cto.official, slot_date=now.date() + timedelta(days=30),
                                              scheduled_for=now + timedelta(days=30), state='preparing')
        brief = {'skip': False, 'questions_for_laura_gomez': [{'question': '¿Qué pasó?', 'purpose': 'p', 'memory_key': 'k',
                                                              'public': True}]}
        with self.model(brief, {'post': CTO_POST, 'citations': []}):
            directed, _ = editorial._stage(piece, 'director', {'ideas_from_gustavo': [], 'feedback_from_gustavo': []})
            editorial._stage(piece, 'redactor', {'brief': {'thesis': 'Evals first'}})
        director, writer = self.sent
        self.assertHers(director)
        self.assertIn('ideas_from_laura_gomez', director['message'])
        self.assertIn('questions_for_laura_gomez', director['schema']['properties'])
        self.assertIn(CTO_PROFILE['limits'], director['system'])
        self.assertEqual(directed['questions_for_gustavo'][0]['question'], '¿Qué pasó?')  # stored with the usual name
        self.assertHers(writer)
        self.assertIn('estado="provisional"', writer['system'])
        piece.refresh_from_db()
        self.assertEqual(piece.voice, {'tipo': 'provisional'})

    def test_drawn_names_are_hers(self):
        from team_backend import infografias
        ident = identidad.of_account(self.cto.official)
        self.assertEqual((infografias.author(ident), imagenes.document_title(EditorialPiece(account=self.cto.official))),
                         ('Laura Gómez', 'Ideas · Laura Gómez'))
        self.assertEqual(imagenes.document_title(EditorialPiece(account=self.g.official)), 'Ideas · Gustavo')
        self.assertEqual(sha(infografias.author(identidad.of_account(self.g.official))), PINNED['infografias.author'])
        # The designer's rule shows example slides signed by the first person: hers are signed with her name.
        design = imagenes.design_system(EditorialPiece(account=self.cto.official))
        for mark in gustavo_marks():
            self.assertNotIn(mark, design)
        self.assertIn('Laura Gómez', design)
        self.assertIn(f'<regla_infografias version="{infografias.version()}">', design)  # the same rule version as his

    def test_no_members_name_goes_to_a_public_web_question(self):
        """research.safe_question drops a question that names any member (hers too), and keeps a public one."""
        from team_backend import research
        for question in ('Noticias de Laura Gómez en 2026', 'Entrevista a Gómez sobre evals', 'Noticias de Gustavo'):
            with self.subTest(question=question):
                self.assertEqual(research.safe_question(question), '')
        self.assertEqual(research.safe_question('How do startups test LLM evals'), 'How do startups test LLM evals')

    def test_without_saying_whose_identity_several_active_members_raise(self):
        """No default member with two active: every identity read without one is MiembroRequerido, never Gustavo's."""
        for read in (identidad.of, voz.current, posicionamiento.status, red.classify_system, operador.comment_system):
            with self.subTest(read=read.__qualname__), self.assertRaises(miembros.MiembroRequerido):
                read()
        self.assertEqual(identidad.owner_name(ConnectorAccount.objects.create(provider='fake', external_account_id='nadie',
                                                                              label='Sin miembro')), 'el dueño de la cuenta')
        # A text a person reads names the owner of the account, never Gustavo by default (the «account paused» push).
        with patch('team_backend.notificaciones.avisar') as pushed:
            operador.set_account_pause(self.cto.reader, 'Prueba de pausa.')
        kind, _, detail = pushed.call_args.args
        self.assertEqual(kind, 'account_paused')
        self.assertIn('Solo Laura Gómez puede reanudarla.', detail)
        Member.objects.filter(pk=self.cto.member.pk).update(active=False)
        self.assertEqual(identidad.of().name, 'Gustavo')


class VozTests(IdentidadBase):
    """Her voice: provisional until she confirms one learned from her own signals; never another member's."""

    def setUp(self):
        super().setUp()
        env = patch.dict(os.environ, {'VOICE_LEARNING_ENABLED': 'true', 'VOICE_LEARNING_MIN_TEXTS': '2'})
        env.start()
        self.addCleanup(env.stop)

    def approved(self, persona, text, edited_from=None):
        """A comment the team drafted on her account that she approved as it was (`text`), or rewrote with
        operador.revise (`edited_from` is her version; the draft is superseded)."""
        post = self.observed(persona, uuid.uuid4().int % 10**9)
        draft = ActionProposal.objects.create(account=persona.reader, post=post, capability='INT-03', payload={'text': text},
                                              payload_hash=uuid.uuid4().hex * 2, source='agent')
        if edited_from is not None:
            return operador.revise(persona.user, draft.id, {'text': edited_from})
        ActionProposal.objects.filter(pk=draft.pk).update(state='confirmed', decided_by=persona.user, decided_at=timezone.now())
        return draft

    def test_the_provisional_voice_is_hers_neutral_and_marked(self):
        voice = voz.current(self.cto.member)
        self.assertEqual((voice.kind, voice.meta, voice.author), ('provisional', {'tipo': 'provisional'}, 'Laura Gómez'))
        block = voice.block()
        for mark in gustavo_marks():
            self.assertNotIn(mark, block)
        self.assertIn(voz.resource('voz-provisional.md'), block)
        self.assertEqual(sha(voz.block(self.g.member)), PINNED['voz.block'])
        self.assertIn('PROVISIONAL', self.command('cto-test', 'voz'))

    def test_a_short_sample_proposes_nothing_and_pays_nothing(self):
        self.approved(self.cto, 'Solo uno.')
        with self.model() as claude, self.assertRaisesMessage(voz.MuestraInsuficiente, '1 de 2'):
            voz.propose(self.cto.user, self.cto.member)
        claude.assert_not_called()
        self.assertFalse(VoiceDocument.objects.filter(member=self.cto.member).exists())
        with patch.dict(os.environ, {'VOICE_LEARNING_ENABLED': 'false'}), self.assertRaisesMessage(ValueError, 'apagado'):
            voz.propose(self.cto.user, self.cto.member)

    def test_a_proposal_reads_only_her_signals_is_unused_until_she_confirms_and_is_versioned(self):
        """voz.propose reads her approved and edited texts (never his, nor his captures); the proposal is not her voice
        until she confirms it with `operador voz --confirmar 1` (the admin cannot); then it is version 1, audited."""
        self.approved(self.cto, 'Medimos antes de opinar.')
        self.approved(self.cto, 'Primero el dato, luego la decisión.', edited_from='Primero el dato y después decidimos.')
        self.approved(self.g, 'Uy, qué pro, me dio curiosidad.')  # his: never in her sample
        Capture.objects.create(created_by=self.g.user, note='Nota de Gustavo con su estilo', state='anotado')
        document = '# Tono de voz de Laura Gómez\n\nFrases cortas y precisas; primero el dato.'
        with self.model({'documento': document, 'notas': 'Muestra pequeña.'}):
            proposal = voz.propose(self.cto.user, self.cto.member)
        call = self.sent[0]
        self.assertEqual(call['purpose'], 'voice-proposal')
        self.assertHers(call)
        texts = [item['texto'] for item in json.loads(call['message'])['senales']]
        self.assertEqual(sorted(texts), sorted(['Medimos antes de opinar.', 'Primero el dato y después decidimos.']))
        self.assertNotIn('qué pro', call['message'])
        self.assertEqual((proposal.number, proposal.state, proposal.usage['texts']), (1, 'propuesta', 2))
        self.assertEqual(voz.current(self.cto.member).kind, 'provisional')  # not used until she confirms
        with self.assertRaises(PermissionError):
            voz.confirm(self.g.user, self.cto.member, 1)  # only she, not even the admin
        self.assertIn('Voz 1 confirmada', self.command('cto-test', 'voz', '--confirmar', '1'))
        voice = voz.current(self.cto.member)
        self.assertEqual((voice.kind, voice.number, voice.meta), ('confirmada', 1, {'tipo': 'confirmada', 'version': 1}))
        self.assertIn(document, voice.block())
        self.assertNotIn('estado="provisional"', voice.block())
        self.assertEqual(sha(voz.block(self.g.member)), PINNED['voz.block'])  # his, untouched
        self.assertEqual(AuditEvent.objects.filter(action__in=['organization.voice_proposed', 'organization.voice_confirmed'],
                                                   target=str(self.cto.member.pk)).count(), 2)


class PerfilComandoTests(IdentidadBase):
    """`operador perfil` and `perfil-organizacion`: validated, audited with before and after, and only hers / the admin's."""

    def test_her_profile_is_validated_audited_and_only_hers(self):
        """`operador perfil`: her revision 1 records before and after; invalid values and another user's change are
        refused without a revision; the same value again changes nothing; anyone may read it with its history."""
        revision = IdentityRevision.objects.get(subject=f'member:{self.cto.member.pk}')
        self.assertEqual((revision.number, revision.actor, revision.after['name'], revision.before['name']),
                         (1, self.cto.user, 'Laura Gómez', 'CTO de prueba'))
        self.assertEqual(self.cto.member.profile['personal_startups'], False)
        for args, reason in ((('--fijar', 'name=L4ura'), 'solo letras'),
                             (('--fijar', 'limits={nombre} no inventa'), 'llaves'),
                             (('--fijar', 'purposes.alianzas_x=algo'), 'purposes'),
                             (('--fijar', 'color=azul'), 'Campo desconocido')):
            with self.subTest(args=args), self.assertRaisesMessage(CommandError, reason):
                self.command('cto-test', 'perfil', *args)
        with self.assertRaisesMessage(CommandError, 'Solo el propio miembro'):
            self.command('gustavo-test', 'perfil', '--miembro', 'cto-test', '--fijar', 'limits=otra cosa')
        self.assertIn('Sin cambios', self.command('cto-test', 'perfil', '--fijar', 'name=Laura Gómez'))
        self.assertEqual(IdentityRevision.objects.filter(subject=f'member:{self.cto.member.pk}').count(), 1)
        shown = self.command('gustavo-test', 'perfil', '--miembro', 'cto-test', '--historial')  # anyone may read it
        self.assertIn('limits [propio]: ' + CTO_PROFILE['limits'], shown)
        self.assertIn('#1 · ', shown)

    def test_the_organizations_profile_is_the_admins(self):
        out = self.command('gustavo-test', 'perfil-organizacion', '--fijar', 'version=posicionamiento-v3')
        self.assertIn('revisión 2 (auditada)', out)  # 1 is migration 0058's (seed_first here)
        self.assertEqual((posicionamiento.version(self.g.member), posicionamiento.version(self.cto.member)),
                         ('posicionamiento-v3', 'posicionamiento-v3'))
        last = IdentityRevision.objects.filter(subject='organization').last()
        self.assertEqual((last.before['version'], last.after['version'], last.changed, last.actor),
                         ('posicionamiento-v2', 'posicionamiento-v3', ['version'], self.g.user))
        with self.assertRaisesMessage(CommandError, 'administrador'):
            self.command('cto-test', 'perfil-organizacion', '--fijar', 'version=posicionamiento-v4')
        with self.assertRaisesMessage(CommandError, 'claves'):
            self.command('gustavo-test', 'perfil-organizacion', '--fijar', 'pillars={"otra": "x"}')
        self.assertEqual(posicionamiento.version(self.g.member), 'posicionamiento-v3')


# ---------------------------------------------------------------------- phase 4: each member's content

HIS_WEEK = ['Recortar el alcance de un MVP sin perder clientes', 'Medir la retención antes de escalar el marketing',
            'Contratar el primer ingeniero senior de producto', 'Validar precios con diez entrevistas reales',
            'Lanzar una beta cerrada con usuarios exigentes', 'Documentar decisiones técnicas para inversores',
            'Priorizar deuda técnica frente a nuevas funciones']
HER_FACT = {'texto': 'Migramos la plataforma a Postgres 17 en 2025 sin una hora de caída.', 'uso_publico': True}
HER_PRIVATE = {'texto': 'No nombrar nunca al cliente Northwind Retail.', 'uso_publico': False}
HIS_FACT = {'texto': 'Gustavo acompañó 40 lanzamientos de producto con founders.', 'uso_publico': True}
COMPANY_FACT = {'texto': 'El caso retail de ProjectApp redujo un 30 % el tiempo de reposición.', 'uso_publico': True}


class ContenidoBase(DosMiembrosBase):
    """Phase 4 (docs/plan-organizaciones.md): each member's content. A frozen clock, never the real hour: Tuesday 10
    November 2026 at 06:00 local, before both post hours (08:30 his, 08:45 hers by the stagger)."""
    DAY = date(2026, 11, 10)

    def setUp(self):
        self.now = datetime.combine(self.DAY, time(6), tzinfo=operador.local_tz())
        clock = patch('django.utils.timezone.now', side_effect=lambda: self.now)
        clock.start()
        self.addCleanup(clock.stop)
        # Django binds timezone.now when models load: freeze those field defaults too (test_fase2_curso).
        for model in apps.get_app_config('team_backend').get_models():
            for field in model._meta.fields:
                if getattr(field.default, '__module__', '') == 'django.utils.timezone':
                    frozen = patch.object(field, '_get_default', new=lambda: timezone.now())
                    frozen.start()
                    self.addCleanup(frozen.stop)
        super().setUp()
        for persona in (self.g, self.cto):
            self.grant(persona.user, 'confirm_memory', 'propose_memory')

    def at(self, day, hour, minute=0):
        return datetime.combine(day, time(hour, minute), tzinfo=operador.local_tz())

    def paid(self, **answers_by_purpose):
        """providers.claude, simulated and recorded: each purpose ('editorial-plan' → 'plan', 'weekly-summary' → 'summary')
        answers its fixture."""
        def fake(system, message, max_tokens=None, output_schema=None, effort=None, purpose='agent-run', **kwargs):
            self.calls.append((purpose, json.loads(message), system))
            return {'text': json.dumps(answers_by_purpose[purpose.split('-', 1)[1]]), 'model': 'claude-opus-5-5',
                    'estimated_usd': 0.01, 'request_id': 'req_' + purpose,
                    'usage': {'input_tokens': 1000, 'output_tokens': 200, 'stop_reason': 'end_turn'}}
        return patch('knowledge.providers.claude', side_effect=fake)

    def day_pieces(self, plan=None):
        """CONT-07 for both: one autopilot pass queues each member's post of the day and the worker writes both."""
        with self.claude(plan or answers()):
            self.assertEqual(autopiloto._editorial(self.autobot, self.now), 2)
            self.drain()
        pieces = {p.member_id: p for p in EditorialPiece.objects.filter(slot_date=self.DAY, second_of_day=False)}
        self.assertEqual(set(pieces), {self.g.member.pk, self.cto.member.pk})
        return pieces[self.g.member.pk], pieces[self.cto.member.pk]

    def director(self, persona):
        """The director's request for `persona`'s piece: her identity keys it (ideas_from_<her>)."""
        key = identidad.of(persona.member).key('ideas_from_gustavo')
        [data] = [d for purpose, d, _ in self.calls if purpose == 'editorial-director' and key in d]
        return data

    def published(self, persona, day):
        """One of her posts went out that day at 08:30 (its piece, its CONT-09 proposal and the execution)."""
        when = self.at(day, 8, 30)
        piece = EditorialPiece.objects.create(account=persona.official, slot_date=day, scheduled_for=when, state='ready',
                                              final_text=persona.text, brief={'pillar': editorial.PILLARS[0], 'thesis': f'Tesis {day}'})
        proposal = ActionProposal.objects.create(account=persona.official, piece=piece, capability='CONT-09',
                                                 payload={'text': piece.final_text}, payload_hash='0' * 64, state='confirmed')
        ActionExecution.objects.create(proposal=proposal, idempotency_key=uuid.uuid4().hex, provider='linkedin_fake',
                                       state='confirmed', executed_by=persona.user, started_at=when)
        return piece


class ContenidoTests(ContenidoBase):
    def test_each_member_has_her_post_of_the_day_on_the_same_day_at_her_own_hour(self):
        """Catch one calendar for the installation: both posts of the day are prepared, each on her own account, at her
        own hour (the CTO's EDITORIAL_POST_STAGGER_MINUTES after Gustavo's) and by her own job; his job is the one of before."""
        mine, hers = self.day_pieces()
        self.assertEqual((mine.state, hers.state), ('ready', 'ready'), (mine.note, hers.note))
        self.assertEqual((mine.account_id, hers.account_id), (self.g.official.pk, self.cto.official.pk))
        self.assertEqual([p.scheduled_for.astimezone(operador.local_tz()).time() for p in (mine, hers)], [time(8, 30), time(8, 45)])
        queued = {miembros.of_job(job.params).pk: job for job in Job.objects.filter(kind='prepare_piece')}
        self.assertEqual((queued[self.g.member.pk].params, queued[self.g.member.pk].id),
                         ({'slot': '2026-11-10'}, autopiloto._job_id('piece', self.DAY)))
        self.assertEqual((queued[self.cto.member.pk].params, queued[self.cto.member.pk].id),
                         ({'slot': '2026-11-10', 'member': str(self.cto.member.pk)},
                          autopiloto._job_id('piece', self.DAY, 'member', self.cto.member.pk)))
        self.assertEqual(autopiloto._editorial(self.autobot, self.now), 0)  # each day is taken by her own piece
        with patch.dict(os.environ, {'EDITORIAL_POST_STAGGER_MINUTES': '40'}):  # the first member never moves
            self.assertEqual((editorial.post_time(self.g.member), editorial.post_time(self.cto.member)), (time(8, 30), time(9, 10)))

    def test_a_post_in_a_provisional_voice_never_goes_out_on_its_own(self):
        """Catch a provisional voice publishing alone: the CTO's post waits for a person with her CONT-09 set to «auto» and
        even after she confirms her voice (it was written in the provisional one); Gustavo's goes out at his hour."""
        miembros.save_settings(self.g.user, self.cto.member, {'OPERATOR_AUTONOMY': 'CONT-09=auto'})
        self.cto.member.refresh_from_db()
        self.assertEqual((autopiloto.autonomy('CONT-09', self.g.member), autopiloto.autonomy('CONT-09', self.cto.member)),
                         ('auto', 'approval'))
        mine, hers = self.day_pieces()
        his_post, her_post = mine.proposals.get(), hers.proposals.get()
        self.assertEqual((hers.voice, her_post.voice), ({'tipo': 'provisional'}, {'tipo': 'provisional'}))
        self.assertNotEqual(mine.voice.get('tipo'), 'provisional')
        self.now = self.at(self.DAY, 9)  # both hours have passed
        autopiloto.tick(self.autobot, self.now)
        self.drain()
        his_post.refresh_from_db(), her_post.refresh_from_db()
        self.assertEqual((his_post.state, her_post.state), ('sent', 'proposed'))
        self.assertEqual(self.writes(), {'gustavo': 1, 'cto': 0})
        VoiceDocument.objects.create(member=self.cto.member, number=1, source='aprendida', text='Directa, técnica y sin adornos.')
        voz.confirm(self.cto.user, self.cto.member, 1)
        self.assertEqual(autopiloto.autonomy('CONT-09', self.cto.member), 'auto')  # her next posts may go alone
        autopiloto.tick(self.autobot, self.now)
        self.drain()
        her_post.refresh_from_db()
        self.assertEqual((her_post.state, self.writes()['cto']), ('proposed', 0))
        operador.approve(self.cto.user, her_post.id, her_post.payload_hash)  # a person decides: then it goes out, on hers
        self.drain()
        self.assertEqual(self.writes(), {'gustavo': 1, 'cto': 1})
        self.assertEqual([p['text'] for p in self.cto.posts_api().state['posts']], [GOOD_POST])

    def test_her_facts_never_reach_his_post_and_his_never_hers_but_the_companys_reach_both(self):
        """Catch shared memory: each director reads her own facts and guidance only, the experience check of a text
        backs a claim with its author's facts only, and a fact the admin made the company's reaches both."""
        hechos.set_fact(self.cto.member, 'stack.migracion', HER_FACT, f'user:{self.cto.user.pk}', 'Prueba')
        hechos.set_fact(self.cto.member, 'limites.clientes', HER_PRIVATE, f'user:{self.cto.user.pk}', 'Prueba')
        hechos.set_fact(self.cto.member, 'caso.retail', COMPANY_FACT, f'user:{self.cto.user.pk}', 'Prueba')
        hechos.set_fact(self.g.member, 'trayectoria.lanzamientos', HIS_FACT, f'user:{self.g.user.pk}', 'Prueba')
        out = io.StringIO()
        with self.assertRaisesMessage(CommandError, 'administrador'):
            call_command('operador', '--usuario', 'cto-test', 'hecho-empresa', '--compartir', 'caso.retail', '--miembro', 'cto-test', stdout=out)
        call_command('operador', '--usuario', 'gustavo-test', 'hecho-empresa', '--compartir', 'caso.retail', '--miembro', 'cto-test', stdout=out)
        self.assertIn('Hechos de la empresa ProjectApp: 1.\n  empresa.caso.retail · versión', out.getvalue())
        self.day_pieces()
        his, hers = (json.dumps(self.director(p), ensure_ascii=False) for p in (self.g, self.cto))
        for text in (HER_FACT['texto'], HER_PRIVATE['texto'], 'stack.migracion', 'limites.clientes'):
            self.assertNotIn(text, his)
            self.assertIn(text, hers)
        self.assertNotIn(HIS_FACT['texto'], hers)
        self.assertIn(HIS_FACT['texto'], his)
        for request in (his, hers):  # his as the company's; hers as her own (hers wins on the same key)
            self.assertIn(COMPANY_FACT['texto'], request)
        self.assertIn('empresa.caso.retail', his)
        # A decision: her confirmed fact backs the claim in her post and never in his.
        claim = 'Migramos la plataforma a Postgres 17 en 2025 sin una hora de caída.'
        self.assertEqual(guardas.text_checks(claim, self.cto.member), [])
        self.assertTrue(any('Gustavo' in reason for reason in guardas.text_checks(claim, self.g.member)))
        call_command('operador', '--usuario', 'gustavo-test', 'hecho-empresa', '--retirar', 'caso.retail', stdout=out)
        self.assertNotIn('empresa.caso.retail', json.dumps(hechos.confirmed_blocks(self.g.member)))
        self.assertIn('caso.retail', json.dumps(hechos.confirmed_blocks(self.cto.member)))  # still hers

    def test_her_audio_and_her_photos_feed_only_her_pieces(self):
        """Catch a shared table of ideas or gallery: the CTO's voice note becomes her idea only, each one's photo is
        offered to her own piece only, and each one lists only what she sent."""
        self.transcribed = []
        with cap.CaptureBase.transcriber(self, 'Quiero contar cómo elegimos la base de datos del primer año.'):
            body = self.cto.client().post('/api/v1/capturas', {'audio': cap.audio(), 'para': 'post'}, format='multipart').json()
            self.drain()
        capture = Capture.objects.get(id=body['id'])
        self.assertEqual((capture.member, capture.state), (self.cto.member, 'idea'))
        photos = {}
        for persona in (self.g, self.cto):
            response = persona.client().post('/api/v1/galeria', {'fotos': [cap.photo()]}, format='multipart')
            self.assertEqual(response.status_code, 201, response.content)
            photos[persona.member.pk] = response.json()[0]['id']
        self.assertEqual([i['id'] for i in capturas.ideas_for_director(self.now, self.cto.member)], [body['id']])
        self.assertEqual(capturas.ideas_for_director(self.now, self.g.member), [])
        for persona in (self.g, self.cto):
            self.assertEqual([p['id'] for p in imagenes.candidates((), persona.member)], [photos[persona.member.pk]])
            self.assertEqual([p['id'] for p in persona.client().get('/api/v1/galeria').json()['results']], [photos[persona.member.pk]])
        self.assertEqual([c['id'] for c in self.g.client().get('/api/v1/capturas').json()['results']], [])
        self.assertEqual([c['id'] for c in self.cto.client().get('/api/v1/capturas').json()['results']], [body['id']])
        mine, hers = self.day_pieces()
        his, her = self.director(self.g), self.director(self.cto)
        self.assertNotIn('base de datos del primer año', json.dumps(his, ensure_ascii=False))
        self.assertIn('base de datos del primer año', json.dumps(her, ensure_ascii=False))
        self.assertEqual([p['id'] for p in his['gallery']], [photos[self.g.member.pk]])
        self.assertEqual([p['id'] for p in her['gallery']], [photos[self.cto.member.pk]])
        mine.brief = dict(mine.brief, gallery_offered=list(photos.values()))  # even if offered, her photo is not his
        self.assertEqual([p['id'] for p in editor_visual.gallery(mine)], [photos[self.g.member.pk]])

    def test_a_team_question_goes_to_the_member_who_owns_the_piece(self):
        """Catch one Tu turno for everyone: each director's question is asked to its piece's member, each sees hers,
        only she answers it, and her answer is her memory."""
        ask = {'question': '¿Qué base de datos usa la plataforma?', 'purpose': 'Para el post técnico',
               'memory_key': 'stack.base_de_datos', 'public': True}
        plan = answers()
        plan['director'] = dict(plan['director'], questions_for_gustavo=[ask])
        mine, hers = self.day_pieces(plan)
        questions = {q.member_id: q for q in TeamQuestion.objects.filter(memory_key='stack.base_de_datos', state='open')}
        self.assertEqual(set(questions), {self.g.member.pk, self.cto.member.pk})  # one open question per member and key
        self.assertEqual((questions[self.cto.member.pk].origin, questions[self.g.member.pk].origin), (f'piece:{hers.id}', f'piece:{mine.id}'))
        for persona in (self.g, self.cto):
            listed = persona.client().get('/api/v1/preguntas', {'state': 'open'}).json()['results']
            self.assertEqual([q['id'] for q in listed], [str(questions[persona.member.pk].id)])
            turn = persona.client().get('/api/v1/tu-turno')  # Tu turno too: hers only, and it works with two members
            self.assertEqual(turn.status_code, 200, turn.content)
            self.assertEqual([c['id'] for c in turn.json()['questions']], [f'question:{questions[persona.member.pk].id}'])
        hers_q = questions[self.cto.member.pk]
        self.assertEqual(self.g.client().post(f'/api/v1/preguntas/{hers_q.id}/responder', {'text': 'MySQL'}, format='json').status_code, 404)
        response = self.cto.client().post(f'/api/v1/preguntas/{hers_q.id}/responder', {'text': 'Postgres 17', 'public_use': True}, format='json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIn('stack.base_de_datos', {r['key'] for r in hechos.latest(self.cto.member)})
        self.assertNotIn('stack.base_de_datos', {r['key'] for r in hechos.latest(self.g.member)})
        self.assertIn('stack.base_de_datos', {f['key'] for f in self.cto.client().get('/api/v1/memoria/hechos').json()})
        self.assertNotIn('stack.base_de_datos', {f['key'] for f in self.g.client().get('/api/v1/memoria/hechos').json()})
        self.assertEqual(TeamQuestion.objects.get(pk=questions[self.g.member.pk].pk).state, 'open')  # his is still his to answer

    def test_each_member_plans_her_week_and_the_second_plan_avoids_the_first_ones_topics(self):
        """Catch two members posting the same topic the same week, or paying for it: each plan is hers (one paid call
        each); the CTO's sees what Gustavo planned and an option that repeats it is never chosen."""
        monday = date(2026, 11, 16)
        days = [monday + timedelta(days=i) for i in range(7)]

        def option(idea):
            return {'idea': idea, 'reason': 'Encaja con el tipo del día.', 'pillar': editorial.PILLARS[0], 'modality': editorial.MODALITIES[0],
                    'approach': editorial.APPROACH_UNITS[0], 'format': 'foto', 'reader': editorial.READERS[0],
                    'reader_need': 'Decidir algo concreto esta semana.', 'audience_evidence': None}

        def week(options):
            return {'days': [{'date': d.isoformat(), 'options': [option(i) for i in ideas]} for d, ideas in zip(days, options)],
                    'summary': 'Una semana.', 'signals_read': []}
        hers = [['Cómo recortar el alcance del MVP sin perder clientes', 'Elegir la base de datos del primer año'],
                ['Medir la retención antes de escalar el marketing'],  # only his topic: that day stays without an idea
                ['Automatizar pruebas de integración con contenedores'], ['Observabilidad mínima para un equipo pequeño'],
                ['Migrar a Postgres sin tiempo de inactividad'], ['Revisar código sin frenar entregas'],
                ['Presupuestar la nube de una startup']]
        with patch.dict(os.environ, {'STRATEGY_ENABLED': 'true'}):
            for persona, options in ((self.g, [[idea] for idea in HIS_WEEK]), (self.cto, hers)):
                with self.paid(plan=week(options)):
                    response = persona.client().post('/api/v1/estrategia/planear', {'semana': monday.isoformat()}, format='json')
                    self.assertEqual(response.status_code, 202, response.content)
                    self.drain()
            plans = {p.member_id: p for p in WeeklyPlan.objects.filter(week_start=monday)}
            weeks = {persona.member.pk: persona.client().get('/api/v1/estrategia/semana', {'dia': monday.isoformat()}).json()
                     for persona in (self.g, self.cto)}
        requests = [data for purpose, data, _ in self.calls if purpose == 'editorial-plan']
        self.assertEqual(len(requests), 2)  # coordinating is free: no extra paid call
        self.assertNotIn('team_planned', requests[0])  # Gustavo alone that week: his request is the one of before
        self.assertEqual([t['idea'] for t in requests[1]['team_planned']['topics']], HIS_WEEK)
        self.assertEqual([s['idea'] for s in plans[self.g.member.pk].slots], HIS_WEEK)
        planned = [s['idea'] for s in plans[self.cto.member.pk].slots]
        self.assertEqual(planned[:2], ['Elegir la base de datos del primer año', ''])
        self.assertFalse(any(estrategia.same_topic(a, b) for a in planned for b in HIS_WEEK))
        self.assertIn('1 día(s) sin idea: sus opciones repetían un tema que otro miembro ya planeó esta semana.',
                      plans[self.cto.member.pk].warnings)
        for persona in (self.g, self.cto):
            self.assertEqual([d['idea'] or '' for d in weeks[persona.member.pk]['days']], [s['idea'] for s in plans[persona.member.pk].slots])
        self.assertEqual(Notification.objects.filter(kind='weekly_plan').count(), 2)  # each one hears of her own plan

    def test_each_member_has_her_summary_and_review_with_her_posts_and_her_audience(self):
        """Catch mixed results: last week's summary and October's review are one per member, each with her own posts and
        her own audience (one snapshot per member and day), and each notice is hers."""
        for persona, days in ((self.g, (2, 4)), (self.cto, (3,))):
            for day in days:
                self.published(persona, date(2026, 11, day))
        for persona, first, last in ((self.g, 500, 530), (self.cto, 90, 140)):
            for day, followers in ((date(2026, 10, 1), first), (date(2026, 10, 31), last)):
                persona.browser().seed_audience(followers=followers, connections=10, views=5)
                self.now = self.at(day, 12)
                self.assertEqual(metricas.collect(self.autobot, persona.reader, now=self.now)['audience'], 'creada')
        self.assertEqual(AudienceSnapshot.objects.filter(day=date(2026, 10, 31)).count(), 2)
        self.now = self.at(self.DAY, 9)
        env = {'WEEKLY_SUMMARY_ENABLED': 'true', 'MONTHLY_REVIEW_ENABLED': 'true', 'WEEKLY_SUMMARY_LLM_USD': '1',
               'MONTHLY_REVIEW_MAX_USD': '2.00'}
        with patch.dict(os.environ, env), self.paid(summary=rsm.model_answer(), review=rvm.model_answer()):
            for persona in (self.g, self.cto):
                for path in ('resumen-semanal', 'revision-mensual'):
                    response = persona.client().post(f'/api/v1/resultados/{path}/generar', {}, format='json')
                    self.assertEqual(response.status_code, 202, response.content)
            self.drain()
        summaries = {s.member_id: s for s in WeeklySummary.objects.filter(week_start=date(2026, 11, 2))}
        reviews = {r.member_id: r for r in MonthlyReview.objects.filter(month_start=date(2026, 10, 1))}
        self.assertEqual({k: s.stats['semana']['publicaciones']['publicados'] for k, s in summaries.items()},
                         {self.g.member.pk: 2, self.cto.member.pk: 1})
        self.assertEqual({k: r.stats['mes']['audiencia']['seguidores']['ganados'] for k, r in reviews.items()},
                         {self.g.member.pk: 30, self.cto.member.pk: 50})
        review_requests = [json.dumps(data) for purpose, data, _ in self.calls if purpose == 'monthly-review']
        self.assertEqual(len(review_requests), 2)
        self.assertEqual(sorted('"valor": 530' in r for r in review_requests), [False, True])  # his audience in one only
        self.assertEqual(sorted('"valor": 140' in r for r in review_requests), [False, True])
        for persona in (self.g, self.cto):  # each one's Resultados shows hers, and «Generar ahora» knows hers is done
            summary = persona.client().get('/api/v1/resultados/resumen-semanal').json()
            review = persona.client().get('/api/v1/resultados/revision-mensual').json()
            self.assertEqual((summary['latest']['id'], summary['previous']), (str(summaries[persona.member.pk].id), []))
            self.assertEqual((review['latest']['id'], review['previous']), (str(reviews[persona.member.pk].id), []))
            self.assertEqual((summary['generate']['available'], review['generate']['available']), (False, False))
        refs = set(Notification.objects.filter(kind__in=['weekly_summary', 'monthly_review']).values_list('ref', flat=True))
        self.assertEqual(refs, {'weekly_summary:2026-11-02', f'weekly_summary:2026-11-02:{self.cto.member.pk}',
                                'monthly_review:2026-10-01', f'monthly_review:2026-10-01:{self.cto.member.pk}'})

    def test_one_members_failing_pass_never_stops_the_others(self):
        """Catch a loop that stops at the first error: a broken post hour fails only its member's pass, whichever of the
        two it is; when every member fails the error reaches the autopilot's report."""
        for broken, fine in ((self.cto, self.g), (self.g, self.cto)):
            with self.subTest(broken=broken.member.display_name):
                Job.objects.filter(kind='prepare_piece').delete()
                Member.objects.filter(pk=broken.member.pk).update(settings={'EDITORIAL_POST_TIME': '25:99'})
                Member.objects.filter(pk=fine.member.pk).update(settings={})
                with self.assertLogs('team_backend.autopilot', 'ERROR') as logs:
                    self.assertEqual(autopiloto._editorial(self.autobot, self.now), 1)
                self.assertIn(f'editorial_failed member={broken.member.pk}', logs.output[0])
                [job] = Job.objects.filter(kind='prepare_piece')
                self.assertEqual(miembros.of_job(job.params), fine.member)
        Job.objects.filter(kind='prepare_piece').delete()
        Member.objects.update(settings={'EDITORIAL_POST_TIME': '25:99'})
        with self.assertLogs('team_backend.autopilot', 'ERROR'):
            report = autopiloto.tick(self.autobot, self.now)
        self.assertIn('EDITORIAL_POST_TIME inválida', report['editorial_error'])

    def test_each_active_member_plans_her_own_piece_and_an_inactive_one_cannot(self):
        """POST /editorial/plan is hers: each active member plans her own next piece (the same day, her hour, her account);
        an inactive member is refused, and alone again Gustavo's hour is the one of before."""
        mine = self.plan_as(self.g, answers())
        hers = self.plan_as(self.cto, answers(final=CTO_POST))
        self.assertEqual([(p.member, p.account_id, p.slot_date) for p in (mine, hers)],
                         [(self.g.member, self.g.official.pk, self.DAY), (self.cto.member, self.cto.official.pk, self.DAY)])
        self.assertEqual([p.state for p in (mine, hers)], ['ready', 'ready'], (mine.note, hers.note))
        miembros.save_member(self.g.user, self.cto.user.username, 'CTO de prueba', 'CTO', active=False)
        response = self.cto.client().post('/api/v1/editorial/plan', {}, format='json')
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn('inactivo', response.json()['detail'])
        self.assertEqual(editorial.post_time(), time(8, 30))

    def test_the_autopilot_never_asks_whose_content_it_is_with_two_active_members(self):
        """Catch a periodic job still reading «the» member: ticks on Sunday afternoon (next week's plans), Monday morning
        (the summaries and October's review are due) and at a post hour never stop at MiembroRequerido, neither in the
        tick's report nor in one member's logged failure, and each member gets her own weekly plan job."""
        for persona in (self.g, self.cto):
            self.published(persona, date(2026, 10, 20))
            self.published(persona, date(2026, 11, 12))
        env = {'STRATEGY_ENABLED': 'true', 'WEEKLY_SUMMARY_ENABLED': 'true', 'MONTHLY_REVIEW_ENABLED': 'true'}
        reports = []
        with patch.dict(os.environ, env), self.assertLogs(level='INFO') as logs:
            logging.getLogger('team_backend.autopilot').info('ticks with two active members')  # assertLogs needs one
            for moment in (self.at(date(2026, 11, 15), 17), self.at(date(2026, 11, 16), 10), self.at(date(2026, 11, 16), 8, 40)):
                self.now = moment
                reports.append(autopiloto.tick(self.autobot, self.now))
        for report in reports:
            self.assertNotIn('unowned', report)
            self.assertNotIn('MiembroRequerido', json.dumps(report, default=str))
        self.assertEqual([r.getMessage() for r in logs.records if r.exc_info and isinstance(r.exc_info[1], miembros.MiembroRequerido)], [])
        self.assertEqual({miembros.of_job(job.params) for job in Job.objects.filter(kind='plan_week')}, {self.g.member, self.cto.member})

    def test_the_results_loop_reads_the_plan_of_the_member_asked_and_never_picks_one(self):
        """Catch a diagnosis that guesses: `bucle_resultados` checks the weekly plan of the member it is asked about
        (--miembro); asked about nobody while two members are active, it says MiembroRequerido instead of picking one."""
        monday = self.DAY - timedelta(days=self.DAY.weekday())
        plans = {persona.member.pk: WeeklyPlan.objects.create(member=persona.member, week_start=monday, state='planeada',
                                                              slots=[{'date': monday.isoformat(), 'type': 'G'}])
                 for persona in (self.g, self.cto)}
        with patch.dict(os.environ, {'STRATEGY_ENABLED': 'true'}):
            for persona in (self.g, self.cto):
                out = io.StringIO()
                call_command('bucle_resultados', '--miembro', persona.user.username, '--json', stdout=out)
                self.assertEqual(json.loads(out.getvalue())['vuelve']['plan_semanal']['plan'], str(plans[persona.member.pk].id))
            unsaid = bucle_resultados.report(now=self.now)['vuelve']
        for check in ('plan_semanal', 'recomendaciones'):
            self.assertEqual(unsaid[check]['estado'], 'error')
            self.assertIn('MiembroRequerido', unsaid[check]['motivo'])
        with self.assertRaisesMessage(CommandError, 'no es miembro'):
            call_command('bucle_resultados', '--miembro', 'nadie', stdout=io.StringIO())


class ContenidoMigracionTests(Migraciones, TransactionTestCase):
    """Migration 0060 on production-like data: Gustavo's history of before organizations and a CTO added later with
    her own uploads. Every row is the first member's except a capture or a photo of the CTO's; nothing is duplicated;
    running it again moves nothing; it goes back (to 0058, dropping the columns) and forward again to the same result."""
    BASE = ('team_backend', '0058_identidad_inicial')
    BEFORE = ('team_backend', '0059_contenido_por_miembro')
    AFTER = ('team_backend', '0060_contenido_del_primer_miembro')
    TABLES = ('EditorialPiece', 'WeeklyPlan', 'WeeklySummary', 'MonthlyReview', 'AudienceSnapshot', 'TeamQuestion',
              'Capture', 'GalleryPhoto', 'Orientation')
    T0 = datetime(2026, 5, 4, 13, tzinfo=dt_timezone.utc)

    def production(self, apps):
        get = lambda name: apps.get_model('team_backend', name)
        User = apps.get_model('auth', 'User')
        gustavo, cto, robot = (User.objects.create(username=name, password='pbkdf2$x', date_joined=self.T0)
                               for name in ('gustavo', 'cto', 'barrio-autopiloto'))
        organization = get('Organization').objects.create(name='ProjectApp', slug='projectapp')
        first = get('Member').objects.create(organization=organization, user=gustavo, display_name='Gustavo', role='Fundador',
                                             is_admin=True, created_at=self.T0)
        later = get('Member').objects.create(organization=organization, user=cto, display_name='CTO', role='CTO',
                                             created_at=self.T0 + timedelta(days=180))
        official = get('ConnectorAccount').objects.create(provider='linkedin', external_account_id='urn:li:person:abc',
                                                          label='LinkedIn oficial', member=first)
        start = date(2026, 5, 4)  # a Monday
        for i in range(60):  # two months of daily pieces; some days a failed first attempt and the published second
            day = start + timedelta(days=i)
            if i % 9 == 0:
                get('EditorialPiece').objects.create(account=official, slot_date=day, scheduled_for=self.T0 + timedelta(days=i),
                                                     state='failed', created_at=self.T0)
            get('EditorialPiece').objects.create(account=official, slot_date=day, scheduled_for=self.T0 + timedelta(days=i),
                                                 state='ready', created_at=self.T0)
            get('AudienceSnapshot').objects.create(day=day, followers=500 + i, captured_at=self.T0 + timedelta(days=i))
        for week in range(8):
            get('WeeklyPlan').objects.create(week_start=start + timedelta(days=7 * week), created_at=self.T0)
            get('WeeklySummary').objects.create(week_start=start + timedelta(days=7 * week), created_at=self.T0)
        for month in (date(2026, 5, 1), date(2026, 6, 1)):
            get('MonthlyReview').objects.create(month_start=month, created_at=self.T0)
        for n, state in enumerate(('open', 'answered', 'declined')):
            get('TeamQuestion').objects.create(agent='director_editorial', question=f'Pregunta {n}', memory_key=f'dato.{n}',
                                               state=state, created_at=self.T0)
        Capture, Photo = get('Capture'), get('GalleryPhoto')
        his = [Capture.objects.create(created_by=gustavo, note=f'Idea {n}', created_at=self.T0) for n in range(4)]
        Capture.objects.create(created_by=robot, note='Del robot', created_at=self.T0)  # nobody's member: the first's
        Capture.objects.create(created_by=None, note='Sin autor', created_at=self.T0)
        hers = Capture.objects.create(created_by=cto, note='Su nota de voz', created_at=self.T0)
        photo = lambda **fields: Photo.objects.create(image='galeria/x.jpg', mime='image/jpeg', size_bytes=10, created_at=self.T0, **fields)
        photo(created_by=gustavo), photo(created_by=gustavo, capture=his[0])
        photo(created_by=robot, capture=hers)  # a photo of her capture is hers, whoever stored it
        photo(created_by=cto)
        get('Orientation').objects.update_or_create(pk=1, defaults={'text': 'Prioriza IA aplicada.'})
        return first, later

    def owners(self, apps):
        return {name: sorted((str(pk), str(member)) for pk, member in
                             apps.get_model('team_backend', name).objects.values_list('pk', 'member_id'))
                for name in self.TABLES}

    def test_the_first_member_takes_the_content_of_before_once_and_it_goes_back(self):
        """Catch a migration that loses, duplicates or misassigns content: every row of before is the first member's (an
        upload of the CTO's, hers), running it again moves nothing, and reverting leaves the tables as they were."""
        apps = self.at(self.BEFORE)
        first, later = self.production(apps)
        apps = self.at(self.AFTER)
        owners = self.owners(apps)
        expected = {str(first.pk): 0, str(later.pk): 0}
        for name, rows in owners.items():
            for pk, member in rows:
                self.assertIn(member, expected, (name, pk))
                expected[member] += 1
        Capture, Photo = (apps.get_model('team_backend', n) for n in ('Capture', 'GalleryPhoto'))
        self.assertEqual(sorted(Capture.objects.filter(member_id=later.pk).values_list('note', flat=True)), ['Su nota de voz'])
        self.assertEqual(Photo.objects.filter(member_id=later.pk).count(), 2)
        self.assertEqual(expected[str(later.pk)], 3)
        counts = {name: len(rows) for name, rows in owners.items()}
        self.assertEqual(counts, {'EditorialPiece': 67, 'WeeklyPlan': 8, 'WeeklySummary': 8, 'MonthlyReview': 2,
                                  'AudienceSnapshot': 60, 'TeamQuestion': 3, 'Capture': 7, 'GalleryPhoto': 4, 'Orientation': 1})
        # Idempotent: running it again on the migrated rows moves nothing.
        migration = importlib.import_module('team_backend.migrations.0060_contenido_del_primer_miembro')
        migration.forwards(apps, None)
        self.assertEqual(self.owners(apps), owners)
        # Back: the first member's rows lose their member (the state 0059 had), hers stay hers; then 0059 drops the columns.
        apps = self.at(self.BEFORE)
        back = self.owners(apps)
        self.assertEqual({member for rows in back.values() for _, member in rows}, {'None', str(later.pk)})
        apps = self.at(self.BASE)
        columns = {c.name for c in connection.introspection.get_table_description(connection.cursor(), 'team_backend_editorialpiece')}
        self.assertNotIn('member_id', columns)
        self.assertEqual(apps.get_model('team_backend', 'EditorialPiece').objects.count(), 67)
        # And forward again: the same owners.
        apps = self.at(self.AFTER)
        self.assertEqual(self.owners(apps), owners)


# One member behaves as before for her content (phase 4): the suites of the plan, the calendar, Tu turno's questions and
# facts, the captures, the gallery, the summary and the review run again with one member, expectations untouched.

class UnMiembroWeeklyPlanTests(UnMiembro, est.WeeklyPlanTests):
    pass


class UnMiembroQuestionTests(UnMiembro, rd.QuestionTests):
    pass


class UnMiembroQuestionFlowTests(UnMiembro, rd.QuestionFlowTests):
    pass


class UnMiembroPersonasAndCalendarTests(UnMiembro, rd.PersonasAndCalendarTests):
    pass


class UnMiembroCaptureRoutingTests(UnMiembro, cap.CaptureRoutingTests):
    pass


class UnMiembroGalleryTests(UnMiembro, cap.GalleryTests):
    pass


class UnMiembroDirectorIdeasTests(UnMiembro, cap.DirectorIdeasTests):
    pass


class UnMiembroSummaryRunTests(UnMiembro, rsm.RunTests):
    pass


class UnMiembroSummaryApiTests(UnMiembro, rsm.ApiTests):
    pass


class UnMiembroReviewApiTests(UnMiembro, rvm.ApiTests):
    pass


class UnMiembroReviewDecisionTests(UnMiembro, rvm.DecisionTests):
    pass


class RecorridoDelCtoTests(DosMiembrosBase):
    """Phase 5: the CTO's day with Gustavo active beside her, through the routes the office and the phone use. The
    registration gives her the groups that work her own account (operador miembro --grupo operacion --grupo revision),
    the admin hands her a password (manage.py changepassword), and every screen is hers."""

    def test_the_cto_logs_in_works_her_account_and_never_sees_gustavos(self):
        """Catch a second member who cannot log in, needs Gustavo's permissions, or reads his things: she enters on the
        office and on her phone, connects her LinkedIn, approves her own draft (marked «voz provisional»), publishes,
        gets her notice, brings an opportunity to the shared funnel, and none of his things reach her."""
        from team_backend.models import Opportunity
        from team_backend.tests.test_alcance import frozen
        frozen(self)
        call_command('bootstrap_local', stdout=io.StringIO())
        cto = self.cto.user
        cto.user_permissions.clear()  # only what the registration gives her
        member, _, created = miembros.save_member(self.gustavo, 'cto-test', 'CTO de prueba', 'CTO', active=True,
                                                  groups=['operacion', 'revision'])
        self.assertEqual((member, created), (self.cto.member, False))
        cto.set_password('clave-local-del-cto')  # what `manage.py changepassword cto-test` does
        cto.save()
        cto = User.objects.get(pk=cto.pk)

        office = APIClient()
        self.assertEqual(office.post('/api/v1/auth/login', {'username': 'cto-test', 'password': 'nope'}, format='json').status_code, 400)
        entered = office.post('/api/v1/auth/login', {'username': 'cto-test', 'password': 'clave-local-del-cto'}, format='json')
        self.assertEqual(entered.status_code, 200, entered.content)
        me = office.get('/api/v1/yo').json()
        self.assertEqual((me['member']['display_name'], me['is_admin'], me['provisional_voice'], me['members']),
                         ('CTO de prueba', False, True, 2))
        issued = APIClient().post('/api/v1/auth/token', {'username': 'cto-test', 'password': 'clave-local-del-cto',
                                                         'device_name': 'Pixel del CTO'}, format='json')
        self.assertEqual(issued.status_code, 201, issued.content)
        phone = APIClient()
        phone.credentials(HTTP_AUTHORIZATION='Bearer ' + issued.json()['token'])
        self.assertEqual(phone.get('/api/v1/yo').json()['member']['id'], str(self.cto.member.pk))

        # Her LinkedIn, her settings; Gustavo pausing his account is not her warning.
        self.assertEqual(self.oauth(self.cto, 'cto123', 'AQ-token-del-cto'), '/ajustes?linkedin=ok')
        self.assertEqual(office.get('/api/v1/linkedin/status').json()['member_urn'], 'urn:li:person:cto123')
        self.pause(self.g, self.g.official, 'Prueba: Gustavo pausa su cuenta')
        alerts = lambda client: {c['id'] for c in client.get('/api/v1/tu-turno').json()['alerts']}
        self.assertIn(f'account_paused:{self.g.official.pk}', alerts(self.g.client()))
        self.assertFalse(any(a.startswith('account_paused') for a in alerts(office)))

        # Her draft waits for her with «voz provisional»; she approves it and it goes out on her account.
        account = editorial.publishing_account(self.cto.member)
        text = self.cto.text
        piece = EditorialPiece.objects.create(
            account=account, slot_date=timezone.now().astimezone(operador.local_tz()).date(),
            scheduled_for=timezone.now() - timedelta(hours=1), state='ready', final_text=text,
            voice=voz.meta(self.cto.member),  # the voice that wrote it, as the editorial pipeline records it
            verification={'verdict': 'ready_for_execution', 'text_sha256': hashlib.sha256(text.encode()).hexdigest()})
        imagenes.fallback(piece, 'Fixture sin proveedores')
        proposal = autopiloto.policy_review(operador.create_proposal(cto, None, 'CONT-09', {'text': text},
                                                                     citations=['LI-04-M005-K01'], source='agent', piece=piece))
        self.assertEqual(proposal.state, 'proposed')
        waiting = [c for c in office.get('/api/v1/tu-turno').json()['items'] if c['id'] == f'approval:{proposal.id}']
        self.assertEqual(len(waiting), 1)
        self.assertTrue(waiting[0]['approval']['provisional_voice'])
        approved = office.post(f'/api/v1/operador/actions/{proposal.id}/approve', {'expected_hash': proposal.payload_hash}, format='json')
        self.assertEqual(approved.status_code, 202, approved.content)
        self.assertEqual(self.publish(proposal).state, 'sent')
        self.assertEqual(self.writes(), {'gustavo': 0, 'cto': 1})
        titles = lambda client: [n['kind'] for n in client.get('/api/v1/notificaciones').json()['items']]
        self.assertIn('piece_published', titles(phone))
        self.assertNotIn('piece_published', titles(self.g.client()))
        self.assertIn(str(piece.id), office.get('/api/v1/calendario').content.decode())
        self.assertNotIn(str(piece.id), self.g.client().get('/api/v1/calendario').content.decode())

        # His things are not hers, on the office nor on the phone.
        his = self.piece(self.g)
        for client in (office, phone):
            self.assertEqual(client.get(f'/api/v1/editorial/pieces/{his.piece_id}').status_code, 404)
            self.assertEqual(client.post(f'/api/v1/operador/actions/{his.id}/reject', {'note': 'no'}, format='json').status_code, 404)
        self.assertNotIn(str(his.piece_id), phone.get('/api/v1/editorial/calendar').content.decode())

        # The funnel is the organization's: what she brings, Gustavo sees, and it says who brought it.
        person = Contact.objects.create(account=self.cto.reader, provider_user_id='lead-del-cto', display_name='Lead del CTO',
                                        source='incoming', stage='connected')
        created = office.post('/api/v1/oportunidades', {'contact': str(person.id), 'modality': 'projectapp', 'channel': 'linkedin'},
                              format='json')
        self.assertEqual(created.status_code, 201, created.content)
        item = Opportunity.objects.get()
        self.assertEqual((item.member, item.origin_member), (self.cto.member, self.cto.member))
        seen = self.g.client().get(f'/api/v1/oportunidades/{item.id}').json()
        self.assertEqual((seen['brought_by']['display_name'], seen['contact']), ('CTO de prueba', None))
        # A service credential, which is nobody's member, reads nothing of either with two members.
        self.assertEqual(self.api.get('/api/v1/tu-turno').status_code, 400)
        self.assertEqual(self.api.get('/api/v1/notificaciones').status_code, 400)
