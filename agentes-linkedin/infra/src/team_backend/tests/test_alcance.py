"""Organizaciones, phase 5 (docs/plan-organizaciones.md «Fase 5: lo construido»): whose each route is, with TWO active
members. Gustavo, 17/11/2026: each member sees and handles only her own things; not even the admin sees another member's
conversations, drafts or private notes.

What it pins:
- every route of the API says whose its data are (alcance.RUTAS) and a route that does not is refused at runtime, so a
  new route cannot ship unclassified;
- every «del miembro» route, read by each of the two members over the same data (each with her contact, conversation,
  piece, image, comment, read post, proposal, question, capture, photo, summary, review, buyer draft, booking, lead,
  profile proposal, browser login, community source, job, memory, notice and device): no 500, nothing of the other one
  (neither her secret text nor any id of hers), and her own shows where it should;
- every route with an id, with the other member's id and with every method it has: 404 (exactly what an id that does
  not exist answers), and the other member's rows are untouched afterwards;
- organization routes answer the same to both; administrator routes refuse the CTO.
The clock is frozen (FIXED): nothing here depends on the real hour."""
import re
import uuid
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from unittest.mock import patch

from django.apps import apps
from django.core.files.base import ContentFile
from django.forms.models import model_to_dict
from django.test import SimpleTestCase
from django.utils import timezone
from rest_framework.test import APIClient

from knowledge import memory
from knowledge import db
from team_backend import alcance, imagenes, notificaciones, operador, urls
from team_backend.alerts import notify as REAL_NOTIFY  # EditorialBase mocks it; these tests push for real (fakes below)
from team_backend.models import (ActionProposal, BrowserLogin, BuyerDraft, BuyerJourney, Capture, CommunitySource,
                                 CommunityStudy, Contact, Conversation, DeviceToken, EditorialPiece, EvidencePerson,
                                 GalleryPhoto, Job, LeadHandoff, MeetingBooking, MonthlyReview, ObservedPost, Opportunity,
                                 PieceImage, PostComment, ProfileAsset, ProfileProposal, StrategyChange, TeamQuestion,
                                 WeeklySummary)
from team_backend.tests.test_organizaciones_e2e import DosMiembrosBase
from team_backend.tests.test_perfil import synthetic
from team_backend.tests.test_resumen_semanal import analysis as summary_analysis

FIXED = datetime(2026, 11, 18, 14, 36, 0, tzinfo=dt_timezone.utc)  # a Wednesday, 09:36 in Bogotá
PARAM = re.compile(r'<(?:(\w+):)?(\w+)>')
PARAM_NAMES = re.compile(r'<(?:\w+:)?(\w+)>')
METHODS = ('get', 'post', 'put', 'patch', 'delete')


def frozen(test):
    """timezone.now() and every model default built on it return FIXED until the test ends."""
    patcher = patch('django.utils.timezone.now', return_value=FIXED)
    patcher.start()
    test.addCleanup(patcher.stop)
    for model in apps.get_app_config('team_backend').get_models():
        for field in model._meta.fields:
            if getattr(field.default, '__module__', '') == 'django.utils.timezone':
                default = patch.object(field, '_get_default', new=lambda: timezone.now())
                default.start()
                test.addCleanup(default.stop)


def routes():
    """(route, view class, methods it answers) of every API route."""
    out = []
    for pattern in urls.urlpatterns:
        view = getattr(pattern.callback, 'view_class', None) or getattr(pattern.callback, 'cls', None)
        methods = [m for m in METHODS if view is not None and hasattr(view, m)]
        out.append((str(pattern.pattern), view, methods))
    return out


class RutasTests(SimpleTestCase):

    def test_every_route_says_whose_its_data_are(self):
        """Catch a new route shipped without a class: it must be in alcance.RUTAS, with a known class and a reason, and
        RUTAS names no route that no longer exists."""
        found = {route for route, _, _ in routes()}
        self.assertEqual(sorted(found - set(alcance.RUTAS)), [], 'rutas sin clasificar en team_backend/alcance.py')
        self.assertEqual(sorted(set(alcance.RUTAS) - found), [], 'alcance.RUTAS nombra rutas que ya no existen')
        for route, (kind, why) in alcance.RUTAS.items():
            kinds = kind.values() if isinstance(kind, dict) else [kind]
            self.assertTrue(set(kinds) <= set(alcance.CLASES) and why.strip(), route)
        from linkedin_backend import urls as root
        self.assertEqual({str(p.pattern) for p in root.urlpatterns} - {'api/v1/'}, set(alcance.RAIZ))

    def test_the_table_has_every_class_and_the_totals_the_docs_give(self):
        """The route table of docs/plan-organizaciones.md («Fase 5: lo construido») counts these: update both together."""
        count = {}
        for route, (kind, _) in alcance.RUTAS.items():
            for one in (set(kind.values()) if isinstance(kind, dict) else {kind}):
                count[one] = count.get(one, 0) + 1
        self.assertEqual(len(alcance.RUTAS), 144)  # app/errores is two: POST hers, GET the admin's
        self.assertEqual(count, {alcance.MIEMBRO: 116, alcance.ORGANIZACION: 18, alcance.ADMINISTRADOR: 4, alcance.SERVICIO: 7})

    def test_every_member_route_with_an_id_says_which_row_it_names(self):
        """Catch a new «del miembro» route with an id that RutaClasificada cannot check: OBJETOS names its row, and each
        model says whose its rows are (DUENO)."""
        for route in alcance.RUTAS:
            names = set(PARAM_NAMES.findall(route))
            if names and alcance.clase(route) == alcance.MIEMBRO:
                with self.subTest(route=route):
                    self.assertEqual(set(alcance.OBJETOS.get(route, {})), names)
        for models in alcance.OBJETOS.values():
            for model in models.values():
                self.assertTrue(model in alcance.DUENO or model in (alcance.RELATIVO, 'memory'), model)


class DosMiembrosAlcanceBase(DosMiembrosBase):
    """Gustavo and the CTO, each with one row of everything a member owns, every text marked with her secret."""

    def setUp(self):
        frozen(self)
        super().setUp()
        self.today = FIXED.astimezone(operador.local_tz()).date()
        for persona in (self.g, self.cto):
            self.grant(persona.user, 'propose_memory', 'confirm_memory')
        env = patch.dict('os.environ', {'INBOX_ENABLED': 'true', 'BUYER_REPLY_ENABLED': 'true', 'BUYER_MESSAGES_ENABLED': 'true'})
        env.start()
        self.addCleanup(env.stop)
        self.secret = {self.g.member.pk: 'SECRETO-GUSTAVO', self.cto.member.pk: 'SECRETO-CTO'}
        self.rows = {p.member.pk: self.seed(p, self.secret[p.member.pk], tag) for p, tag in ((self.g, 'g'), (self.cto, 'c'))}

    def other(self, persona):
        return self.cto if persona is self.g else self.g

    def seed(self, p, secret, tag):
        now = FIXED
        rows = {'reader': p.reader, 'official': p.official}
        contact = rows['contact'] = Contact.objects.create(
            account=p.reader, provider_user_id=f'{tag}-persona', display_name=f'Ana {secret}', headline=secret,
            source='incoming', stage='connected', connected_at=now - timedelta(hours=2), discovered_at=now - timedelta(hours=3),
            network_distance='FIRST_DEGREE', classification={'fit': True, 'role': 'CTO'})
        message = {'id': f'{tag}-m1', 'from_me': False, 'at': (now - timedelta(hours=1)).isoformat(), 'text': secret}
        rows['conversation'] = Conversation.objects.create(
            account=p.reader, provider_chat_id=f'{tag}-chat', contact=contact, attendee_name=f'Ana {secret}',
            last_message_at=now - timedelta(hours=1), last_message_preview=secret, messages=[message],
            assessment={'message_id': message['id'], 'awaiting_reply': True, 'answers': {'espera': 0.9}})
        piece = rows['piece'] = EditorialPiece.objects.create(
            account=p.official, member=p.member, slot_date=self.today, scheduled_for=now + timedelta(hours=3), state='ready',
            final_text=f'{secret}: el post de hoy', brief={'thesis': secret})
        image = PieceImage(piece=piece, position=1, kind='foto', width=800, height=800, sha256=imagenes.sha(synthetic()), alt=secret)
        image.image.save(f'{tag}.png', ContentFile(synthetic()), save=False)
        image.save()
        rows['image'] = image
        rows['comment'] = PostComment.objects.create(
            account=p.reader, piece=piece, provider_post_id=f'urn:li:activity:{tag}', provider_comment_id=f'{tag}-comentario',
            author_name=f'Ana {secret}', text=f'{secret} ¿y cómo lo resolvieron?', commented_at=now - timedelta(hours=1),
            contact=contact)
        post = rows['post'] = ObservedPost.objects.create(account=p.reader, provider_post_id=f'{tag}-leido', author_name=secret,
                                                          text=f'{secret} post de un referente', posted_at=now - timedelta(hours=5))
        rows['proposal'] = ActionProposal.objects.create(account=p.reader, post=post, capability='INT-03',
                                                         payload={'text': f'{secret} comentario'}, payload_hash='h' * 64,
                                                         created_by=p.user)
        rows['question'] = TeamQuestion.objects.create(member=p.member, agent='director_contenido', question=f'¿{secret}?',
                                                       purpose=secret, memory_key=f'{tag}.dato')
        rows['capture'] = Capture.objects.create(created_by=p.user, member=p.member, note=secret, state='anotado')
        photo = GalleryPhoto(member=p.member, created_by=p.user, mime='image/png', size_bytes=len(synthetic()), note=secret)
        photo.image.save(f'{tag}-foto.png', ContentFile(synthetic()), save=False)
        photo.save()
        rows['photo'] = photo
        rows['summary'] = WeeklySummary.objects.create(member=p.member, week_start=self.today - timedelta(days=9),
                                                       analysis=summary_analysis(), stats={'semana': {'nota': secret}})
        review = rows['review'] = MonthlyReview.objects.create(
            member=p.member, month_start=self.today.replace(day=1) - timedelta(days=31),
            stats={'mes': {}}, analysis={'titular': secret, 'validacion': {'ok': True, 'descartado': []}})
        rows['change'] = StrategyChange.objects.create(review=review, title=secret, proposal=secret, metric='mediana_impresiones_72h',
                                                       reason=secret, expected='Que suba la métrica.')
        journey = rows['journey'] = BuyerJourney.objects.create(contact=contact, chosen_at=now - timedelta(days=5), step='respondio',
                                                                reply_type='interesado')
        rows['draft'] = BuyerDraft.objects.create(contact=contact, kind='respuesta', state='listo', text=f'{secret} borrador',
                                                  inputs={'clasificacion': {'tipo': 'interesado'}})
        rows['booking'] = MeetingBooking.objects.create(uid=f'{tag}-reserva', contact=contact, journey=journey,
                                                        attendee_name=f'Ana {secret}', start_at=now + timedelta(days=2))
        rows['handoff'] = LeadHandoff.objects.create(key=f'{tag}-lead', contact=contact, journey=journey, data={'nota': secret})
        profile = rows['profile'] = ProfileProposal.objects.create(owner=p.user, key=f'{tag}-perfil', state='ready')
        asset = ProfileAsset(proposal=profile, version=1, kind='banner', sha256=imagenes.sha(synthetic()), width=1584, height=396,
                             review={'ok': True})
        asset.image.save(f'{tag}-banner.png', ContentFile(synthetic()), save=False)
        asset.save()
        rows['asset'] = asset
        rows['login'] = BrowserLogin.objects.create(account=p.reader, user=p.user, session=f'{tag}-sesion',
                                                    expires_at=now + timedelta(minutes=30), state='esperando')
        study = CommunityStudy.objects.create(account=p.reader, period=self.today.replace(day=1), window_start=now - timedelta(days=30),
                                              window_end=now, expires_at=now + timedelta(days=30), positioning_version='1')
        who = EvidencePerson.objects.create(account=p.reader, provider_user_id=f'{tag}-evidencia', display_name=secret)
        rows['source'] = CommunitySource.objects.create(study=study, person=who, key=f'{tag}-fuente', target=f'{tag}-objetivo',
                                                        kind='comment', text=secret, expires_at=now + timedelta(days=30))
        rows['job'] = Job.objects.create(owner=p.user, request_hash=tag * 64, agent='operador', task=secret, kind='observe',
                                         params={'member': str(p.member.pk)})
        rows['device'] = DeviceToken.objects.create(user=p.user, name=f'Teléfono {secret}', digest=tag * 64)
        notificaciones.avisar('piece_published', f'Publicaste «{secret}»', ref=f'piece_published:{tag}', member=p.member)
        proposed = p.client().post('/api/v1/memory/proposals', {'namespace': 'user', 'key': f'perfil.{tag}', 'value': secret,
                                                                 'evidence': secret}, format='json')
        self.assertEqual(proposed.status_code, 201, proposed.content)
        rows['memory'] = proposed.json()['id']
        return rows

    # ------------------------------------------------------------------ helpers

    def ids_of(self, persona):
        """Every id of `persona`'s rows, as the API would print them."""
        return {str(getattr(row, 'pk', row)) for row in self.rows[persona.member.pk].values()}

    def param(self, route, name, persona):
        """The value of `name` in `route` that points at a row of `persona`; None when the route's id is not hers."""
        rows = self.rows[persona.member.pk]
        by_prefix = {
            'sid': [('comunidad/', 'source'), ('resultados/resumen-semanal/', 'summary')],
            'rid': [('runs/', 'job'), ('resultados/revision-mensual/', 'review')],
            'mid': [('memory/', 'memory')],
            'did': [('comprador/', 'draft'), ('auth/dispositivos/', 'device')],
            'bid': [('comprador/reservas/', 'booking')],
            'hid': [('comprador/entregas/', 'handoff')],
            'pid': [('perfil/', 'profile'), ('editorial/', 'piece'), ('galeria/', 'photo'), ('operador/posts/', 'post'),
                    ('operador/actions/', 'proposal')],
            'aid': [('perfil/', 'asset'), ('operador/accounts/', 'reader')],
            'qid': [('preguntas/', 'question')],
            'cid': [('red/contacts/', 'contact'), ('capturas/', 'capture'), ('resultados/revision-mensual/cambios/', 'change'),
                    ('conversaciones/', 'conversation'), ('respuestas/', 'comment')],
            'lid': [('operador/conexiones/', 'login')],
            'iid': [('editorial/', 'image')],
        }
        for prefix, key in by_prefix.get(name, []):
            if route.startswith(prefix):
                row = rows[key]
                return str(getattr(row, 'pk', row))
        return None

    def url(self, route, persona):
        """`route` with every id pointing at `persona`'s rows; None if one of its ids is not covered here."""
        values = {}
        for _, name in PARAM.findall(route):
            values[name] = self.param(route, name, persona)
            if values[name] is None:
                return None
        return '/api/v1/' + PARAM.sub(lambda m: values[m.group(2)], route)

    def snapshot(self, persona):
        out = {}
        for key, row in self.rows[persona.member.pk].items():
            if hasattr(row, 'pk'):
                fresh = type(row).objects.filter(pk=row.pk).first()
                out[key] = None if fresh is None else model_to_dict(fresh)
        with db.connect() as c:
            out['memory'] = dict(c.execute('SELECT * FROM memory WHERE id=%s', (self.rows[persona.member.pk]['memory'],)).fetchone())
        return out

    @staticmethod
    def body(response):
        streamed = getattr(response, 'streaming_content', None)
        return b''.join(streamed) if streamed is not None else response.content

    def call(self, client, method, path):
        kwargs = {'format': 'json'} if method != 'get' else {}
        return getattr(client, method)(path, *([{}] if method != 'get' else []), **kwargs)


class DelMiembroTests(DosMiembrosAlcanceBase):

    def member_routes(self):
        return [(route, view, methods) for route, view, methods in routes() if alcance.clase(route) == alcance.MIEMBRO
                or (isinstance(alcance.RUTAS[route][0], dict) and alcance.MIEMBRO in alcance.RUTAS[route][0].values())]

    def test_each_member_reads_only_hers_on_every_member_route(self):
        """Catch a list that forgot its filter: every «del miembro» GET route without an id, read by each member, never
        prints the other's secret or any id of hers, and never fails."""
        seen = {}
        for persona in (self.g, self.cto):
            client, other = persona.client(), self.other(persona)
            foreign_secret, foreign_ids = self.secret[other.member.pk], self.ids_of(other)
            for route, _, methods in self.member_routes():
                if PARAM.search(route) or 'get' not in methods or alcance.clase(route, 'GET') != alcance.MIEMBRO:
                    continue
                with self.subTest(route=route, quien=persona.member.display_name):
                    response = client.get('/api/v1/' + route)
                    text = self.body(response).decode('utf-8', 'replace')
                    self.assertLess(response.status_code, 500, text[:300])
                    self.assertNotIn(foreign_secret, text)
                    leaked = sorted(i for i in foreign_ids if i in text)
                    self.assertEqual(leaked, [], f'{route} muestra ids de {other.member.display_name}')
                    mine = self.secret[persona.member.pk] in text or any(i in text for i in self.ids_of(persona))
                    seen.setdefault(route, set()).add(mine)
        # Her own rows do show where they belong (else «nothing of the other's» would prove nothing).
        own = {route for route, shown in seen.items() if shown == {True}}
        self.assertTrue({'red/contacts', 'tu-turno', 'calendario', 'editorial/calendar', 'capturas', 'galeria', 'preguntas',
                         'notificaciones', 'operador/actions', 'operador/posts', 'runs', 'memory', 'comprador/entregas',
                         'auth/dispositivos'} <= own, sorted(set(seen) - own))

    def test_another_members_id_is_404_on_every_route_and_method_and_changes_nothing(self):
        """Catch an object permission that is missing or answers 403 (which says the object exists): every route with
        an id, with every method, given the other member's id answers what an id that does not exist answers, 404; and
        the other member's rows are exactly as before."""
        uncovered = []
        for persona in (self.g, self.cto):
            client, other = persona.client(), self.other(persona)
            before = self.snapshot(other)
            for route, _, methods in self.member_routes():
                if not PARAM.search(route) or route == 'perfil/<uuid:pid>/descarga/<str:token>':
                    continue
                if route.startswith('memoria/hechos/') or route.startswith('estrategia/dias/'):
                    continue  # keys and days are relative to her own memory and plan: FactsKeysTests
                path = self.url(route, other)
                if path is None:
                    uncovered.append(route)
                    continue
                for method in methods:
                    with self.subTest(route=route, method=method, quien=persona.member.display_name):
                        response = self.call(client, method, path)
                        self.assertEqual(response.status_code, 404, self.body(response)[:300])
            self.assertEqual(self.snapshot(other), before)
        self.assertEqual(sorted(set(uncovered)), [])

    def test_her_own_ids_answer_her(self):
        """The other side of the 404s: with her own ids, the detail routes answer her (else the 404 would be for all)."""
        for persona in (self.g, self.cto):
            client = persona.client()
            for route in ('red/contacts/<uuid:cid>', 'editorial/pieces/<uuid:pid>', 'capturas/<uuid:cid>', 'galeria/<uuid:pid>',
                          'galeria/<uuid:pid>/imagen', 'editorial/pieces/<uuid:pid>/images/<uuid:iid>', 'perfil/<uuid:pid>',
                          'perfil/<uuid:pid>/assets/<uuid:aid>', 'operador/actions/<uuid:pid>', 'operador/conexiones/<uuid:lid>',
                          'comprador/entregas/<uuid:hid>', 'runs/<uuid:rid>', 'resultados/resumen-semanal/<uuid:sid>',
                          'resultados/revision-mensual/<uuid:rid>'):
                with self.subTest(route=route, quien=persona.member.display_name):
                    response = client.get(self.url(route, persona))
                    self.assertEqual(response.status_code, 200, self.body(response)[:300])

    def test_an_id_that_does_not_exist_looks_the_same(self):
        """A random id answers 404 on the same routes, so the other member's 404 says nothing about her rows."""
        client = self.cto.client()
        for route in ('red/contacts/<uuid:cid>', 'operador/actions/<uuid:pid>/approve', 'conversaciones/<uuid:cid>/cerrar',
                      'comprador/respuestas/<uuid:did>/agendo', 'preguntas/<uuid:qid>/responder'):
            path = '/api/v1/' + PARAM.sub(lambda m: str(uuid.uuid4()), route)
            method = 'get' if not route.endswith(('approve', 'cerrar', 'agendo', 'responder')) else 'post'
            with self.subTest(route=route):
                self.assertEqual(self.call(client, method, path).status_code, 404)


class FactsKeysTests(DosMiembrosAlcanceBase):

    def test_a_fact_key_and_a_day_are_hers_whoever_names_them(self):
        """Facts and the week plan are addressed by key and day inside her own memory and plan: the CTO naming Gustavo's
        key touches nothing of his (409: she has no such fact), and her day shows only her plan."""
        key = f'perfil.g'
        response = self.cto.client().post(f'/api/v1/memoria/hechos/{key}/corregir', {'text': 'otro'}, format='json')
        self.assertEqual(response.status_code, 409, response.content)  # she has no such fact
        self.assertIn(key, {row['key'] for row in memory.latest()})  # his proposal is still there, untouched
        day = self.cto.client().get(f'/api/v1/estrategia/dias/{self.today.isoformat()}')
        self.assertLess(day.status_code, 500)
        self.assertNotIn('SECRETO-GUSTAVO', day.content.decode())


class OrganizacionYAdministradorTests(DosMiembrosAlcanceBase):

    def test_organization_routes_answer_the_same_to_both(self):
        """Catch an organization route filtered by member: both get the same status, never a 500; the opportunities are
        the same list for both and each says who brought it."""
        Opportunity.objects.create(modality='projectapp', person_name='Lead de la empresa', contact=self.rows[self.g.member.pk]['contact'],
                                   member=self.g.member, origin_member=self.g.member, created_by=self.g.user)
        for route, _, methods in routes():
            if alcance.clase(route) != alcance.ORGANIZACION or PARAM.search(route) or 'get' not in methods:
                continue
            with self.subTest(route=route):
                answers = [persona.client().get('/api/v1/' + route) for persona in (self.g, self.cto)]
                self.assertEqual(answers[0].status_code, answers[1].status_code)
                self.assertNotEqual(answers[0].status_code, 500, self.body(answers[0])[:300])  # push/key: 503 without VAPID
        lists = [[o['id'] for o in persona.client().get('/api/v1/oportunidades').json()['results']] for persona in (self.g, self.cto)]
        self.assertEqual(lists[0], lists[1])
        self.assertEqual(len(lists[0]), 1)
        theirs = self.cto.client().get('/api/v1/oportunidades').json()['results'][0]
        self.assertEqual((theirs['brought_by']['display_name'], theirs['registered_by']['display_name']), ('Gustavo', 'Gustavo'))
        # The funnel names its lead for everyone (it is the organization's); the card of his person stays his: no link
        # to his Personas until phase 6 shares the registry.
        self.assertEqual((theirs['person'], theirs['contact']), ('Ana SECRETO-GUSTAVO', None))
        self.assertIsNotNone(self.g.client().get('/api/v1/oportunidades').json()['results'][0]['contact'])

    def test_administrator_routes_refuse_the_cto(self):
        """Catch a member reading the installation's diagnostics: integrity, audit and the app's error reports are the
        admin's; the CTO gets 403 even with manage_jobs."""
        for path in ('/api/v1/integrity', '/api/v1/audit', '/api/v1/app/errores'):
            with self.subTest(path=path), patch('team_backend.views.ingest.verify', return_value={'ok': True}):
                self.assertEqual(self.cto.client().get(path).status_code, 403)
                self.assertNotEqual(self.g.client().get(path).status_code, 403)
        cycle = f'/api/v1/equipo/ciclos/{uuid.uuid4()}/decision'
        self.assertEqual(self.cto.client().post(cycle, {}, format='json').status_code, 403)
        self.assertEqual(self.cto.client().post('/api/v1/app/errores', {'message': 'x'}, format='json').status_code
                         in (201, 400), True)  # reporting is hers

    def test_an_unclassified_route_is_refused(self):
        """Catch the fail-closed default: a route missing from alcance.RUTAS is refused (403), whoever asks."""
        rutas = dict(alcance.RUTAS)
        rutas.pop('yo')
        with patch.object(alcance, 'RUTAS', rutas):
            response = self.g.client().get('/api/v1/yo')
        self.assertEqual(response.status_code, 403)
        self.assertIn('alcance.py', response.json()['detail'])


class QuienSoyTests(DosMiembrosAlcanceBase):

    def test_yo_says_who_she_is(self):
        me = self.cto.client().get('/api/v1/yo').json()
        self.assertEqual((me['username'], me['member']['display_name'], me['member']['is_admin'], me['organization']['name']),
                         ('cto-test', 'CTO de prueba', False, 'ProjectApp'))
        self.assertTrue(me['provisional_voice'])
        his = self.g.client().get('/api/v1/yo').json()
        self.assertEqual((his['member']['display_name'], his['is_admin'], his['members']), ('Gustavo', True, 2))
        self.assertIn(APIClient().get('/api/v1/yo').status_code, (401, 403))

    def test_a_buyers_signal_names_the_member_whose_buyer_it_is(self):
        """Catch «Comentó en un post de Gustavo» on the CTO's buyer: the stored value is the same, its name is hers;
        his stays the label of always."""
        from team_backend import comprador
        self.assertEqual(comprador.signal_name('comento_post', self.cto.reader), 'Comentó en un post de CTO de prueba')
        self.assertEqual(comprador.signal_name('nos_siguio', self.cto.reader), 'Siguió a CTO de prueba')
        self.assertEqual(comprador.signal_name('comento_post', self.g.reader), 'Comentó en un post de Gustavo')


class AvisosTests(DosMiembrosAlcanceBase):
    """Each notice is someone's: hers goes to her devices only, the organization's to everyone with each one's own
    switches; preferences and «Vista» are each person's; Slack never names a member's private things."""

    def setUp(self):
        super().setUp()
        import httpx
        from unittest.mock import MagicMock
        from team_backend import alerts, expo, push
        from team_backend.models import ExpoPushToken, PushSubscription
        from team_backend.tests.test_app_movil import ExpoFake
        self.expo = ExpoFake()
        channel = MagicMock(HTTPError=httpx.HTTPError)  # alerts' own httpx: the OPERATOR_ALERT_WEBHOOK posts
        for patcher in (patch.object(expo, 'TRANSPORT', httpx.MockTransport(self.expo)),
                        patch.object(push, 'configured', return_value=True),
                        patch.object(push, 'send', side_effect=lambda s, *a, **k: self.web.append(s.user_id) or True),
                        patch.dict('os.environ', {'OPERATOR_ALERT_WEBHOOK': 'https://ntfy.example/barrio'}),
                        patch.object(alerts, 'httpx', channel)):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.webhook = channel.Client
        self.notify.side_effect = REAL_NOTIFY  # through push.broadcast and expo.broadcast, to the fakes
        self.web = []
        for persona, tag in ((self.g, 'g'), (self.cto, 'c')):
            ExpoPushToken.objects.create(user=persona.user, token=f'ExponentPushToken[{tag}]', device_name=f'Teléfono {tag}')
            PushSubscription.objects.create(user=persona.user, endpoint=f'https://push.example/{tag}', p256dh='k', auth='a')
        self.phones = {self.g.user.pk: 'ExponentPushToken[g]', self.cto.user.pk: 'ExponentPushToken[c]'}
        self.sent()  # the seed's own notices

    def sent(self):
        """(Expo tokens, web push users, webhook posts) since the last call."""
        out = (sorted(m['to'] for m in self.expo.messages), sorted(self.web), self.webhook.return_value.__enter__.return_value.post.call_count)
        self.expo.messages.clear()
        self.expo.sent.clear()
        self.web.clear()
        self.webhook.return_value.__enter__.return_value.post.reset_mock()
        return out

    def listed(self, persona):
        return [n['title'] for n in persona.client().get('/api/v1/notificaciones').json()['items']]

    def test_her_notice_goes_to_her_devices_only_and_never_to_his_channel(self):
        """Catch a push to every device: the CTO's question reaches her phone and her browser only, not Gustavo's nor
        his channel (OPERATOR_ALERT_WEBHOOK); his reaches his, and his channel, as before."""
        notificaciones.avisar('question', 'El director pregunta al CTO', member=self.cto.member)  # Tu turno's kind
        self.assertEqual(self.sent(), (['ExponentPushToken[c]'], [self.cto.user.pk], 0))
        notificaciones.avisar('piece_published', 'Publicaste «La del CTO»', member=self.cto.member)  # a Notificación
        self.assertEqual(self.sent(), (['ExponentPushToken[c]'], [self.cto.user.pk], 0))
        notificaciones.avisar('piece_published', 'Publicaste «La de Gustavo»', member=self.g.member)
        self.assertEqual(self.sent(), (['ExponentPushToken[g]'], [self.g.user.pk], 1))
        self.assertIn('Publicaste «La del CTO»', self.listed(self.cto))
        self.assertNotIn('Publicaste «La del CTO»', self.listed(self.g))
        self.assertNotIn('Publicaste «La de Gustavo»', self.listed(self.cto))

    def test_the_organizations_notice_is_everyones_with_each_ones_switches(self):
        """Catch global preferences: the total stop is everyone's (one row each, each read on her own), and Gustavo
        turning its push off silences only his devices."""
        off = self.g.client().patch('/api/v1/ajustes/preferencias', {'push_disabled': ['machine_paused']}, format='json')
        self.assertEqual(off.status_code, 200, off.content)
        operador.set_global_pause(self.cto.user, True, 'Prueba: parada total')  # Tu turno's card, pushed to everyone
        self.assertEqual(self.sent()[:2], (['ExponentPushToken[c]'], [self.cto.user.pk]))
        notificaciones.avisar('gate_alert', 'Una compuerta frena demasiado', member=notificaciones.ORGANIZACION)
        self.assertEqual(self.sent(), (['ExponentPushToken[c]', 'ExponentPushToken[g]'], [self.g.user.pk, self.cto.user.pk], 1))
        for persona in (self.g, self.cto):
            self.assertIn('Una compuerta frena demasiado', self.listed(persona))
        self.g.client().post('/api/v1/notificaciones/leer', {'todas': True}, format='json')
        unread = {p.member.display_name: p.client().get('/api/v1/notificaciones').json()['unread'] for p in (self.g, self.cto)}
        self.assertEqual(unread['Gustavo'], 0)
        self.assertGreater(unread['CTO de prueba'], 0)

    def test_preferences_are_each_ones_and_his_are_the_ones_of_before(self):
        """Catch one preferences row for everyone: the CTO's switches are hers; Gustavo keeps row 1, the configuration he
        had before organizations."""
        from team_backend.models import OfficePreference
        OfficePreference.objects.filter(pk=1).update(push_disabled=['connection_fit'])
        self.cto.client().patch('/api/v1/ajustes/preferencias', {'push_disabled': ['question']}, format='json')
        mine = {t['kind']: t['enabled'] for t in self.cto.client().get('/api/v1/ajustes').json()['push_types']}
        his = {t['kind']: t['enabled'] for t in self.g.client().get('/api/v1/ajustes').json()['push_types']}
        self.assertEqual((mine['question'], his['question']), (False, True))
        self.assertEqual(OfficePreference.of(self.g.user).pk, 1)
        self.assertEqual(OfficePreference.of(self.g.user).push_disabled, ['connection_fit'])
        self.assertEqual(OfficePreference.of(self.cto.user).push_disabled, ['question'])

    def test_vista_is_each_ones(self):
        """Catch one «Vista» for everyone: the total stop's card is in both Tu turno; Gustavo opening it leaves hers new."""
        from team_backend.models import InboxSeen
        operador.set_global_pause(self.g.user, True, 'Prueba: parada total')
        cards = lambda p: {c['id']: c['state'] for c in p.client().get('/api/v1/tu-turno').json()['alerts']}
        self.assertEqual((cards(self.g)['machine_paused'], cards(self.cto)['machine_paused']), ('nueva', 'nueva'))
        self.g.client().post('/api/v1/tu-turno/vistos', {'ids': ['machine_paused']}, format='json')
        self.assertEqual((cards(self.g)['machine_paused'], cards(self.cto)['machine_paused']), ('vista', 'nueva'))
        self.cto.client().post('/api/v1/tu-turno/vistos', {'ids': ['machine_paused']}, format='json')
        self.assertEqual(sorted(InboxSeen.objects.values_list('item_id', flat=True)),
                         sorted(['machine_paused', f'u:{self.cto.user.pk}:machine_paused']))

    def test_a_notice_that_names_nobody_is_dropped_never_guessed(self):
        with self.assertLogs('team_backend.notificaciones', 'WARNING'):
            self.assertIsNone(notificaciones.avisar('question', 'Sin dueño', member=None))
        self.assertEqual(self.sent(), ([], [], 0))
        self.assertNotIn('Sin dueño', self.listed(self.g) + self.listed(self.cto))

    def test_slack_never_names_a_members_private_things_with_two_members(self):
        """Catch the organization's one Slack channel showing who writes to a member: with two members the
        conversation alert only says that one waits, and where."""
        from team_backend import alertas_slack
        alerts = alertas_slack.conversacion_espera(FIXED)
        self.assertEqual(len(alerts), 2)
        for alert in alerts:
            self.assertNotIn('SECRETO', alert.text)
            self.assertTrue(alert.text.startswith('Barrio · Una conversación de LinkedIn espera respuesta.'))
        self.cto.member.active = False
        self.cto.member.save()
        alone = alertas_slack.conversacion_espera(FIXED)  # one member: the alert of before, his channel
        self.assertTrue(any('Ana SECRETO-GUSTAVO te escribió' in a.text for a in alone))
