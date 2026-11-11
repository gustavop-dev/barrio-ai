"""A comment of Gustavo on a ready piece goes back to the team (retoque.py), and the visual package survives his
answers (binding v2). All providers use fakes."""
import io
import json
from datetime import timedelta
from unittest.mock import patch

from PIL import Image
from django.utils import timezone

from team_backend import autopiloto, capturas, connectors_images, editor_visual, editorial, guardas, imagenes, lider
from team_backend import jobs, operador, orquestacion, rescate, retoque, urgente
from team_backend.connectors_images import FakeImageConnector
from team_backend.models import ActionProposal, Capture, CycleLedger, EditorialPiece, GalleryPhoto, Job
from team_backend.tests import test_imagenes as image_cases
from team_backend.tests.test_imagenes import png, slide
from team_backend.tests.test_publicacion import GOOD_POST, EditorialBase, answers

NEW_POST = GOOD_POST.replace('Before writing a line of code for a new feature', 'Before you write a single line of code for a feature')
INSTRUCTION = 'Replace only the background with a bright coworking space; keep his face, clothes and the laptop.'


def decision(kind, route='ninguna', text='', fails='aplazar', instruction=''):
    claims = [{'text': 'A weekly decision rarely needs real-time data.', 'kind': 'general_knowledge', 'ref': ''}] if text else []
    return {'decision': kind, 'reason': 'Gustavo lo pidió en su comentario.', 'final_text': text, 'claims': claims,
            'changes': ['Cambio pedido'] if kind != 'nada' else [], 'image_route': route,
            'image_instruction': instruction, 'if_image_fails': fails,
            'summary_for_gustavo': 'Cambiamos lo que pediste.', 'citations': ['LI-06-M002-K09']}


class SequenceConnector(FakeImageConnector):
    """Each visual check answers the next verdict."""
    def __init__(self, verdicts):
        super().__init__()
        self.verdicts = iter(verdicts)

    def check(self, images, context, original=None, instruction='', from_gustavo=False):
        self.ok = next(self.verdicts)
        return super().check(images, context, original, instruction, from_gustavo)


class ReworkBase(EditorialBase):
    photo = image_cases.ImageWorkflowTests.photo
    factory = image_cases.ImageWorkflowTests.piece

    def setUp(self):
        super().setUp()
        self.grant(self.gustavo, 'run_agents', 'use_paid_providers', 'operate_linkedin')

    def ready(self, kind='foto', size=(1080, 1080), days=3, at=None):
        """A ready piece with its approved proposal, as the daily circuit leaves it."""
        photo = self.photo(size=size) if kind == 'foto' else None
        piece = self.factory(kind=kind, photo=photo)
        day = timezone.now().astimezone(operador.local_tz()).date() + timedelta(days=days)
        piece.scheduled_for = at or editorial.scheduled_for(day)
        piece.slot_date = piece.scheduled_for.astimezone(operador.local_tz()).date()
        piece.citations = ['LI-06-M002-K09']
        piece.save()
        if kind == 'foto':
            imagenes.prepare(piece, client=FakeImageConnector())
        else:
            with patch('knowledge.providers.claude', return_value={'text': json.dumps({'slides': [slide()]})}):
                imagenes.prepare(piece, client=FakeImageConnector())
        public, private = guardas.blocks()
        editor_visual.bind(piece, public, private)
        piece.state = EditorialPiece.State.READY
        piece.save()
        proposal = operador.create_proposal(self.autobot, None, 'CONT-09', {'text': piece.final_text, 'media': imagenes.manifest(piece)},
            rationale='Tesis', citations=piece.citations, source='agent', piece=piece)
        ActionProposal.objects.filter(pk=proposal.pk).update(state='approved', approved_hash=proposal.payload_hash)
        proposal.refresh_from_db()
        return piece, proposal

    def claude(self, plan):
        def fake(system, message, max_tokens=None, output_schema=None, effort=None, purpose='agent-run', **kwargs):
            data = json.loads(message)
            self.calls.append((purpose, data, system))
            answer = plan['design' if purpose.startswith('image-design') else purpose.split('-', 1)[1]]
            return {'text': json.dumps(answer), 'model': 'claude-opus-5-5', 'estimated_usd': 0.01, 'request_id': 'req_' + purpose}
        return patch('knowledge.providers.claude', side_effect=fake)

    def comment(self, piece, text):
        return Capture.objects.create(created_by=self.gustavo, note=text, context_type='pieza', context_id=str(piece.id),
            state=Capture.State.NOTED, routed_to={'kind': 'pieza', 'piece': str(piece.id), 'rework': 'pending'})

    def rework(self, capture, plan, fake=None):
        with self.claude(plan), patch('team_backend.connectors_images.ImageConnector', return_value=fake or FakeImageConnector()):
            retoque.run(capture)
        capture.refresh_from_db()
        return capture


class ReworkTests(ReworkBase):
    def test_a_photo_comment_edits_the_original_keeps_its_orientation_and_the_hour(self):
        piece, old = self.ready(size=(900, 1200))
        when = piece.scheduled_for
        original = imagenes.read(piece.images.get().source_photo.image)
        capture = self.comment(piece, 'Quiero que editen esa foto con un espacio de coworking detrás.')
        fake = FakeImageConnector(edited=png((1024, 1536), '#dedfd4'))
        capture = self.rework(capture, {'retoque': decision('imagen', 'editar_foto', instruction=INSTRUCTION)}, fake)
        piece.refresh_from_db()
        old.refresh_from_db()
        new = piece.proposals.get(state='proposed')
        self.assertEqual((old.state, new.previous_id, new.version), ('superseded', old.id, old.version + 1))
        self.assertEqual([c[0] for c in fake.calls], ['edit', 'check'])
        self.assertEqual((fake.calls[0][1], fake.calls[0][2]), (original, INSTRUCTION))
        self.assertTrue(fake.calls[1][5])  # his comment asked for it: the tolerant check (IMG-10, criterion 8)
        row = piece.images.get()
        self.assertTrue(row.edited)
        self.assertEqual((row.width, row.height), (1080, 1350))  # vertical stays vertical, never squashed
        self.assertEqual(Image.open(io.BytesIO(imagenes.read(row.image))).size, (1080, 1350))
        self.assertIn('Comentario de Gustavo', row.reason)
        self.assertTrue(row.review['from_gustavo'])
        self.assertEqual(GalleryPhoto.objects.get(pk=row.source_photo_id).state, 'editada')
        self.assertEqual(imagenes.read(row.source_photo.image), original)
        self.assertNotEqual(new.payload['media'], old.payload['media'])
        self.assertEqual(new.payload['text'], old.payload['text'])
        self.assertEqual(piece.scheduled_for, when)
        self.assertEqual(autopiloto.post_issues(new), [])  # the leader still reviews it
        self.assertEqual((capture.state, capture.routed_to['rework']['state']), ('anotado', 'rehecha'))
        self.assertEqual(capture.routed_to['rework']['proposal'], str(new.id))
        ledger = CycleLedger.objects.get(cycle='retoque_pieza', key=str(capture.id))
        self.assertEqual(ledger.state, 'complete')
        self.assertEqual(sorted(c['edge'] for c in ledger.progress_ledger['calls'].values()),
                         ['editar_foto', 'retocar', 'revisar_imagen'])
        self.assertEqual(retoque.run(capture), capture)  # never twice
        self.assertEqual(piece.proposals.count(), 2)

    def test_the_reworked_image_gets_a_new_url_so_no_client_shows_the_cached_previous_one(self):
        piece, old = self.ready()
        row = piece.images.get()
        before = imagenes.payload(row)['url']
        self.rework(self.comment(piece, 'Ponme en un coworking.'),
                    {'retoque': decision('imagen', 'editar_foto', instruction=INSTRUCTION)},
                    FakeImageConnector(edited=png((1024, 1024), '#dedfd4')))
        row.refresh_from_db()
        after = imagenes.payload(row)['url']
        self.assertNotEqual(before, after)
        self.assertEqual(after, f'/api/v1/editorial/pieces/{piece.id}/images/{row.id}?v={row.sha256[:16]}')
        response = self.human.get(after)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(imagenes.sha(b''.join(response.streaming_content)), row.sha256)

    def test_a_text_comment_is_verified_again_and_moves_when_the_veto_window_no_longer_fits(self):
        soon = timezone.now() + timedelta(minutes=20)
        piece, old = self.ready(at=soon)
        capture = self.comment(piece, 'Cambia la primera frase, que suene más directa.')
        plan = {'retoque': decision('texto', text=NEW_POST), 'verificador': answers(final=NEW_POST)['verificador']}
        capture = self.rework(capture, plan)
        piece.refresh_from_db()
        new = piece.proposals.get(state='proposed')
        self.assertEqual((piece.final_text, new.payload['text']), (NEW_POST, NEW_POST))
        self.assertEqual(piece.verification['text_sha256'], imagenes.sha(NEW_POST.encode()))
        self.assertEqual(piece.verification['rework'], str(capture.id))
        self.assertGreaterEqual(piece.scheduled_for, timezone.now() + urgente.veto_window())
        self.assertTrue(capture.routed_to['rework']['moved'])
        self.assertEqual(autopiloto.post_issues(new), [])
        purposes = [c[0] for c in self.calls]
        self.assertEqual(purposes, ['editorial-retoque', 'editorial-verificador'])
        self.assertEqual(self.calls[0][1]['comment'], capture.text)

    def test_an_opinion_changes_nothing_and_keeps_the_hour(self):
        piece, old = self.ready()
        when = piece.scheduled_for
        fake = FakeImageConnector()
        capture = self.rework(self.comment(piece, 'Me gusta mucho el tono.'), {'retoque': decision('nada')}, fake)
        piece.refresh_from_db()
        new = piece.proposals.get(state='proposed')
        self.assertEqual((new.payload, piece.scheduled_for), (old.payload, when))
        self.assertEqual(fake.calls, [])
        self.assertEqual(capture.routed_to['rework']['state'], 'sin_cambios')

    def test_a_failed_edit_never_publishes_the_old_version_and_postpones_it(self):
        piece, old = self.ready()
        idea = Capture.objects.create(created_by=self.gustavo, note='Idea con foto', purpose='post', state='usado',
                                      routed_to={'used_in': str(piece.id)})
        photo = piece.images.get().source_photo
        fake = FakeImageConnector(ok=False)
        capture = self.rework(self.comment(piece, 'Ponme en un coworking.'),
                              {'retoque': decision('imagen', 'editar_foto', instruction=INSTRUCTION)}, fake)
        piece.refresh_from_db()
        old.refresh_from_db()
        idea.refresh_from_db()
        photo.refresh_from_db()
        self.assertEqual([c[0] for c in fake.calls], ['edit', 'check'] * retoque.PHOTO_ATTEMPTS)
        self.assertEqual((piece.state, old.state), ('blocked', 'superseded'))
        self.assertFalse(piece.proposals.filter(state__in=['proposed', 'approved']).exists())
        self.assertEqual((idea.state, photo.state), ('idea', 'sin_usar'))  # back to the table and the gallery
        self.assertEqual(capture.routed_to['rework']['state'], 'aplazada')
        self.assertIn('revisión visual', piece.note)

    def test_when_the_edit_fails_the_director_can_fall_back_to_an_infographic(self):
        plan = {'retoque': decision('imagen', 'editar_foto', fails='infografia', instruction=INSTRUCTION),
                'design': {'slides': [slide()]}}
        piece, old = self.ready()
        photo = piece.images.get().source_photo
        fake = SequenceConnector([False] * retoque.PHOTO_ATTEMPTS + [True])  # the photo edits fail, the design passes
        capture = self.rework(self.comment(piece, 'Ponme en un coworking.'), plan, fake)
        piece.refresh_from_db()
        photo.refresh_from_db()
        self.assertEqual((piece.state, piece.image_kind, piece.images.get().kind), ('ready', 'infografia', 'infografia'))
        self.assertEqual((photo.state, capture.routed_to['rework']['state']), ('sin_usar', 'rehecha'))
        self.assertEqual(imagenes.issues(piece, piece.proposals.get(state='proposed').payload['media']), [])
        # Nothing passes: the old version still does not go out.
        piece, old = self.ready(days=4)
        capture = self.rework(self.comment(piece, 'Ponme en un coworking.'), plan, FakeImageConnector(ok=False))
        piece.refresh_from_db()
        self.assertEqual((piece.state, capture.routed_to['rework']['state']), ('blocked', 'aplazada'))

    def test_a_published_or_past_piece_only_keeps_the_comment(self):
        piece, old = self.ready()
        ActionProposal.objects.filter(pk=old.pk).update(state='sent')
        with patch('knowledge.providers.claude', side_effect=AssertionError('No paid call')):
            capture = self.rework(self.comment(piece, 'Cambia la foto.'), {})
        self.assertEqual(capture.routed_to['rework']['state'], 'sin_cambios')
        self.assertFalse(CycleLedger.objects.filter(cycle='retoque_pieza').exists())

    def test_without_leader_reviews_left_it_tells_him_instead_of_holding_the_piece(self):
        piece, old = self.ready()
        with patch.object(retoque, 'gate_left', return_value=0), \
                patch('knowledge.providers.claude', side_effect=AssertionError('No paid call')):
            capture = self.rework(self.comment(piece, 'Cambia la foto.'), {})
        old.refresh_from_db()
        self.assertEqual((old.state, capture.routed_to['rework']['state']), ('approved', 'sin_retoque'))

    def test_the_comment_job_routes_and_reworks_in_one_pass(self):
        piece, old = self.ready()
        fake = FakeImageConnector(edited=png((1024, 1024), '#dedfd4'))
        with self.claude({'retoque': decision('imagen', 'editar_foto', instruction=INSTRUCTION)}), \
                patch('team_backend.capture_intent.jev', return_value={}), patch('team_backend.capture_intent.apply'), \
                patch('team_backend.connectors_images.ImageConnector', return_value=fake):
            capture = capturas.create(self.gustavo, {'nota': 'Edítala con un coworking detrás.', 'contexto_tipo': 'pieza',
                                                     'contexto_id': str(piece.id)})
            self.drain()
        capture.refresh_from_db()
        self.assertEqual((capture.state, capture.routed_to['kind'], capture.routed_to['rework']['state']),
                         ('anotado', 'pieza', 'rehecha'))
        self.assertTrue(piece.images.get().edited)
        self.assertEqual([c['id'] for c in capturas.piece_comments(piece)], [str(capture.id)])


    def test_comments_left_before_the_flow_are_applied_once_and_earlier_feedback_is_not(self):
        piece, old = self.ready()
        earlier = Capture.objects.create(created_by=self.gustavo, note='Feedback previo', context_type='pieza',
                                         context_id=str(piece.id), state=Capture.State.NOTED, routed_to={'kind': 'pieza'})
        Capture.objects.filter(pk=earlier.pk).update(created_at=old.created_at - timedelta(minutes=5))
        later = Capture.objects.create(created_by=self.gustavo, note='Quiero que esta foto se edite con un coworking detrás.',
                                       context_type='pieza', context_id=str(piece.id), state=Capture.State.NOTED,
                                       routed_to={'kind': 'pieza', 'piece': str(piece.id)})
        self.assertEqual([c.id for c, _, _ in retoque.pending_comments()], [later.id])
        with self.claude({'retoque': decision('imagen', 'editar_foto', instruction=INSTRUCTION)}), \
                patch('team_backend.connectors_images.ImageConnector', return_value=FakeImageConnector()):
            done = retoque.apply_pending()
        self.assertEqual([(c.id, c.routed_to['rework']['state']) for c in done], [(later.id, 'rehecha')])
        self.assertEqual(retoque.pending_comments(), [])
        earlier.refresh_from_db()
        self.assertNotIn('rework', earlier.routed_to)

    def discard(self, piece, old):
        """What autopiloto.policy_review leaves when Jev discards the version: the piece stays ready, its ideas and
        photos go back to the table and the gallery."""
        reason = 'Líder: atribuye a Gustavo algo que no está en sus hechos (inventa=0.25)'
        ActionProposal.objects.filter(pk=old.pk).update(state='discarded', risks=list(old.risks) + [reason],
                                                        review={'decision': 'discard', 'reasons': [reason]})
        capturas.release_ideas(piece, 'la política no la aprobó')
        old.refresh_from_db()
        return reason

    def test_a_comment_on_a_version_the_lead_discarded_reworks_it_and_takes_back_its_photo_and_idea(self):
        piece, old = self.ready()
        idea = Capture.objects.create(created_by=self.gustavo, note='Idea con foto', purpose='post', state='usado',
                                      routed_to={'used_in': str(piece.id)})
        photo = piece.images.get().source_photo
        reason = self.discard(piece, old)
        idea.refresh_from_db()
        photo.refresh_from_db()
        self.assertEqual((idea.state, photo.state, photo.chosen_piece_id), ('idea', 'sin_usar', None))
        self.assertEqual(retoque.eligible(piece), old)
        later = Capture.objects.create(created_by=self.gustavo, note='Difumina las caras de la pantalla.', context_type='pieza',
                                       context_id=str(piece.id), state=Capture.State.NOTED, routed_to={'kind': 'pieza'})
        self.assertEqual([c.id for c, _, _ in retoque.pending_comments()], [later.id])
        fake = FakeImageConnector(edited=png((1024, 1024), '#dedfd4'))
        capture = self.rework(self.comment(piece, 'Difumina las caras de la pantalla.'),
                              {'retoque': decision('imagen', 'editar_foto', instruction=INSTRUCTION)}, fake)
        piece.refresh_from_db()
        old.refresh_from_db()
        idea.refresh_from_db()
        photo.refresh_from_db()
        new = piece.proposals.get(state='proposed')
        self.assertEqual((old.state, old.review['reworked_by'], new.previous_id), ('discarded', str(capture.id), old.id))
        self.assertEqual((capture.routed_to['rework']['state'], piece.state), ('rehecha', 'ready'))
        self.assertEqual((photo.state, photo.chosen_piece_id, photo.chosen_for), ('editada', piece.id, piece.slot_date))
        self.assertEqual((idea.state, idea.routed_to['used_in'], idea.routed_to['intentos'], idea.routed_to['intentos_en']),
                         ('usado', str(piece.id), 0, []))
        self.assertNotIn(reason, new.risks)  # the lead judges the new version afresh
        self.assertEqual(piece.images.get().review['instruction'], INSTRUCTION)
        self.assertEqual(retoque.eligible(piece), new)

    def test_a_discarded_version_is_reworked_once_and_a_photo_taken_by_another_piece_postpones_it(self):
        piece, old = self.ready()
        self.discard(piece, old)
        ActionProposal.objects.filter(pk=old.pk).update(review={'reworked_by': 'otro-comentario'})
        with patch('knowledge.providers.claude', side_effect=AssertionError('No paid call')):
            capture = self.rework(self.comment(piece, 'Cambia la foto.'), {})
        self.assertEqual(capture.routed_to['rework']['state'], 'sin_cambios')
        self.assertIn('ya está rehaciendo', capture.outcome['text'])
        other, _ = self.ready(days=5)
        piece, old = self.ready(days=4)
        self.discard(piece, old)
        GalleryPhoto.objects.filter(pk=piece.images.get().source_photo_id).update(state='elegida', chosen_piece=other)
        with patch('knowledge.providers.claude', side_effect=AssertionError('No paid call')):
            capture = self.rework(self.comment(piece, 'Cambia la foto.'), {})
        piece.refresh_from_db()
        self.assertEqual((piece.state, capture.routed_to['rework']['state']), ('blocked', 'aplazada'))
        self.assertEqual(GalleryPhoto.objects.get(pk=piece.images.get().source_photo_id).chosen_piece_id, other.id)

    def test_the_next_photo_comment_sees_the_edit_his_earlier_comment_asked_for(self):
        piece, old = self.ready()
        self.rework(self.comment(piece, 'Ponme en un coworking.'),
                    {'retoque': decision('imagen', 'editar_foto', instruction=INSTRUCTION)})
        self.calls = []
        self.rework(self.comment(piece, 'Difumina las caras de la pantalla.'),
                    {'retoque': decision('imagen', 'editar_foto', instruction=INSTRUCTION + ' Blur the faces on the screen.')})
        image = self.calls[0][1]['image']['images'][0]
        self.assertEqual(image['edit_instruction'], INSTRUCTION)
        self.assertIn('parte de la foto\n  original', editorial.RETOUCH_SYSTEM)


class SoftLeadTests(ReworkBase):
    """A post Gustavo asked for is judged much more softly by the lead, with his own words as facts."""

    def setUp(self):
        super().setUp()
        from team_backend.tests.test_rediseno import JevMock
        import httpx
        from knowledge import providers
        env = patch.dict('os.environ', {'LEAD_ENABLED': 'true', 'LIVE_PROVIDERS': 'true', 'TYPESAFE_API_KEY': 'ts-test-key',
                                        'TYPESAFE_LIMIT_USD': '1'})
        env.start()
        self.addCleanup(env.stop)
        self.jev = JevMock({'clara': 0.84, 'pitch': 0.03, 'idioma': 0.98, 'inventa': 0.25})
        transport = patch.object(providers, 'TYPESAFE_TRANSPORT', httpx.MockTransport(self.jev))
        transport.start()
        self.addCleanup(transport.stop)

    def proposed(self):
        piece, old = self.ready()
        ActionProposal.objects.filter(pk=old.pk).update(state='proposed', approved_hash='')
        old.refresh_from_db()
        return piece, old

    def test_the_team_s_own_post_keeps_the_strict_thresholds(self):
        piece, proposal = self.proposed()
        verdict = lider.review(proposal)
        self.assertEqual((verdict['decision'], verdict['from_gustavo']), ('discard', False))
        self.assertEqual(verdict['thresholds']['inventa'], ['max', 0.2])
        self.assertNotIn('pedido_de_gustavo', self.jev.requests[-1]['state'])

    def test_his_idea_or_comment_makes_the_lead_soft_and_his_words_are_facts(self):
        piece, proposal = self.proposed()
        Capture.objects.create(created_by=self.gustavo, note='Cuento que di una clase de producto por Zoom.', purpose='post',
                               state='usado', routed_to={'used_in': str(piece.id)})
        Capture.objects.create(created_by=self.gustavo, note='Edita la foto con un coworking detrás.', context_type='pieza',
                               context_id=str(piece.id), state=Capture.State.NOTED, routed_to={'kind': 'pieza'})
        verdict = lider.review(proposal)
        self.assertEqual((verdict['decision'], verdict['from_gustavo'], verdict['reasons']), ('approve', True, []))
        self.assertEqual(verdict['thresholds'], {'clara': ['min', 0.3], 'pitch': ['max', 0.6], 'inventa': ['max', 0.6],
                                                 'idioma': ['min', 0.5]})
        body = self.jev.requests[-1]
        self.assertEqual(body['state']['pedido_de_gustavo'],
                         ['Cuento que di una clase de producto por Zoom.', 'Edita la foto con un coworking detrás.'])
        self.assertIn('pedido_de_gustavo', body['questions']['inventa']['instructions'])
        # Soft is not blind: a clear failure still stops it.
        self.jev.probabilities = dict(self.jev.probabilities, inventa=0.8)
        proposal.review = {}
        verdict = lider.review(proposal)
        self.assertEqual(verdict['decision'], 'discard')
        self.assertIn('inventa=0.8', verdict['reasons'][0])


class BindingV2Tests(EditorialBase):
    photo = image_cases.ImageWorkflowTests.photo
    factory = image_cases.ImageWorkflowTests.piece

    def bound(self):
        piece = self.factory(photo=self.photo())
        imagenes.prepare(piece, client=FakeImageConnector())
        public, private = guardas.blocks()
        editor_visual.bind(piece, public, private)
        piece.state = 'ready'
        piece.save()
        return piece

    def test_a_new_confirmed_fact_no_longer_makes_the_package_stale(self):
        piece = self.bound()
        self.remember('experiencia.nueva', {'texto': 'Gustavo dio una charla sobre agentes en Medellín.', 'uso_publico': True})
        self.assertEqual(editor_visual.freshness_issues(piece), [])
        self.assertEqual(imagenes.issues(piece, imagenes.manifest(piece)), [])

    def test_the_live_guards_still_catch_a_private_fact_the_package_now_exposes(self):
        piece = self.bound()
        self.remember('objetivo.nuevo', {'texto': 'Gustavo shares a photograph from a product workshop with clients.', 'uso_publico': False})
        self.assertTrue(any('privada' in p for p in editor_visual.freshness_issues(piece)))

    def test_changed_text_or_sources_still_need_a_new_package(self):
        piece = self.bound()
        piece.final_text = NEW_POST
        self.assertTrue(editor_visual.freshness_issues(piece))
        piece.final_text = GOOD_POST
        piece.signals = [{'id': 'nuevo', 'text': 'Otra fuente'}]
        self.assertTrue(editor_visual.freshness_issues(piece))

    def test_a_still_valid_v1_binding_is_upgraded_and_a_stale_one_keeps_failing(self):
        piece = self.bound()
        binding = {k: v for k, v in piece.image_review['visual_binding'].items() if k not in ('version', 'content_sha256')}
        piece.image_review = dict(piece.image_review, visual_binding=binding)
        piece.save()
        stale = self.bound()
        stale.image_review = dict(stale.image_review, visual_binding=dict(binding, context_sha256='otro'))
        stale.save()
        self.assertEqual(editor_visual.upgrade_bindings(), 1)
        piece.refresh_from_db()
        stale.refresh_from_db()
        self.assertEqual(piece.image_review['visual_binding']['version'], 2)
        self.assertNotIn('version', stale.image_review['visual_binding'])
        self.remember('experiencia.otra', {'texto': 'Gustavo enseña producto a founders.', 'uso_publico': True})
        self.assertEqual(editor_visual.freshness_issues(piece), [])
        self.assertTrue(editor_visual.freshness_issues(stale))
        self.assertEqual(editor_visual.upgrade_bindings(), 0)


class EditSizeTests(EditorialBase):
    def test_the_edit_keeps_the_orientation_of_the_photo(self):
        self.assertEqual(connectors_images.edit_size(png((900, 1200))), '1024x1536')
        self.assertEqual(connectors_images.edit_size(png((1600, 900))), '1536x1024')
        self.assertEqual(connectors_images.edit_size(png((1000, 1050))), '1024x1024')
        self.assertEqual(imagenes.post_size(900, 1200), (1080, 1350))
        self.assertEqual(imagenes.post_size(1600, 900), (1080, 1080))  # never horizontal (IMG-12)
        self.assertEqual(imagenes.post_size(1080, 1080), (1080, 1080))

    def test_reframing_a_vertical_original_keeps_it_vertical(self):
        photo = image_cases.ImageWorkflowTests.photo(self, size=(900, 1200))
        piece = image_cases.ImageWorkflowTests.piece(self, photo=photo)
        fake = FakeImageConnector(edited=png((1024, 1536), '#dedfd4'))
        imagenes.prepare(piece, client=fake)
        row = piece.images.get()
        self.assertEqual([c[0] for c in fake.calls], ['edit', 'check'])
        self.assertEqual(fake.calls[0][2], imagenes.SAFE_EDITS['crop'])
        self.assertEqual((row.edited, row.width, row.height), (True, 1080, 1350))
        self.assertEqual(Image.open(io.BytesIO(imagenes.read(row.image))).size, (1080, 1350))
        self.assertIsNone(orquestacion.current())


PITCH = 'DM me if you want to talk about it.'


class RescueTests(ReworkBase):
    """EDI-23: a blocked piece shows why and offers «Pedir un cambio» and «Desestimar el bloqueo»."""
    def setUp(self):
        super().setUp()
        self.grant(self.gustavo, 'approve_actions', 'execute_actions')

    def blocked(self, days=3, reasons=('Contiene pitch agresivo o petición de contacto',)):
        """A piece the text verifier blocked, as editorial.prepare leaves it: its text, no image, no proposal."""
        piece = self.factory(kind='foto', photo=self.photo())
        day = timezone.now().astimezone(operador.local_tz()).date() + timedelta(days=days)
        piece.scheduled_for = editorial.scheduled_for(day)
        piece.slot_date = piece.scheduled_for.astimezone(operador.local_tz()).date()
        piece.citations = ['LI-06-M002-K09']
        piece.final_text = GOOD_POST + '\n\n' + PITCH
        piece.state = EditorialPiece.State.BLOCKED
        piece.note = '; '.join(reasons)
        piece.verification = {'verdict': 'blocked', 'blocking_reasons': list(reasons),
                              'text_sha256': imagenes.sha(piece.final_text.encode())}
        piece.save()
        return piece

    def no_vision(self):
        return patch('team_backend.connectors_images.available', return_value=False)

    def test_dismissing_a_verifier_block_prepares_its_image_and_schedules_it_with_his_approval(self):
        piece = self.blocked()
        url = f'/api/v1/editorial/pieces/{piece.id}'
        self.assertEqual(self.human.get(url).json()['rescue'], {'kind': 'verificador', 'override': True, 'change': True, 'why_not': ''})
        with self.no_vision(), patch('team_backend.connectors_images.ImageConnector', return_value=FakeImageConnector()), \
                patch.object(lider, 'review', side_effect=AssertionError('el líder no revisa lo que él desestimó')):
            response = self.human.post(url + '/desestimar', {'note': 'Sale así'}, format='json')
            self.assertEqual(response.status_code, 202)
            job = Job.objects.get(pk=response.json()['job']['id'])
            self.assertEqual((job.kind, job.params['piece']), ('override_piece', str(piece.id)))
            jobs.process_one(self.worker)
        job.refresh_from_db()
        piece.refresh_from_db()
        self.assertEqual(job.state, Job.State.COMPLETE)
        self.assertEqual(piece.state, EditorialPiece.State.READY)
        self.assertTrue(piece.images.exists())  # every post goes out with an image
        proposal = piece.proposals.get()
        self.assertEqual((proposal.state, proposal.decided_by, proposal.source), ('approved', self.gustavo, 'human'))
        self.assertEqual(proposal.decision_note, 'Gustavo desestimó el bloqueo: Sale así')
        self.assertTrue(Job.objects.filter(kind='execute_action').exists())
        # The verifier's verdict stays on record; his override binds this exact text and only LinkedIn's needs remain.
        self.assertEqual(piece.verification['verdict'], 'blocked')
        self.assertEqual(piece.verification['override']['text_sha256'], imagenes.sha(piece.final_text.encode()))
        self.assertEqual(piece.verification['override']['reasons'], ['Contiene pitch agresivo o petición de contacto'])
        self.assertEqual(autopiloto.post_issues(proposal), [])
        self.assertEqual(editorial.status(piece, proposal), 'scheduled')
        detail = self.human.get(url).json()
        self.assertIsNone(detail['rescue'])
        self.assertEqual(detail['override']['kind'], 'verificador')
        # Another text is not covered by his override.
        piece.verification = dict(piece.verification, override=dict(piece.verification['override'], text_sha256='0' * 64))
        piece.save()
        self.assertIn('Contiene pitch agresivo o petición de contacto', autopiloto.post_issues(proposal))

    def test_dismissing_the_leaders_discard_approves_a_new_version_without_the_leader(self):
        piece, old = self.ready()
        ActionProposal.objects.filter(pk=old.pk).update(state='discarded', review={'reasons': ['Líder: inventa 0.8']},
                                                        decision_note='Descartada por el líder')
        self.assertEqual(rescate.options(piece), {'kind': 'lider', 'override': True, 'change': True, 'why_not': ''})
        self.assertEqual(rescate.reasons(piece), ['Líder: inventa 0.8'])
        with patch.object(lider, 'review', side_effect=AssertionError('el líder no revisa lo que él desestimó')):
            new = rescate.override(self.gustavo, piece.id)
        old.refresh_from_db()
        piece.refresh_from_db()
        self.assertEqual((new.state, new.previous_id, new.version, new.decided_by), ('approved', old.id, old.version + 1, self.gustavo))
        self.assertEqual(new.payload['text'], old.payload['text'])
        self.assertEqual(autopiloto.post_issues(new), [])
        self.assertIsNone(rescate.options(piece))
        self.assertEqual(piece.verification['override']['kind'], 'lider')

    def test_no_way_out_when_the_day_has_another_piece_its_hour_passed_or_a_budget_stop(self):
        piece = self.blocked(days=4)
        self.ready(days=4)
        self.assertEqual(rescate.options(piece)['why_not'], 'Ese día ya tiene otra pieza programada.')
        response = self.human.post(f'/api/v1/editorial/pieces/{piece.id}/desestimar', {}, format='json')
        self.assertEqual(response.status_code, 409)
        self.assertFalse(Job.objects.filter(kind='override_piece').exists())
        late = self.blocked(days=5)
        EditorialPiece.objects.filter(pk=late.pk).update(scheduled_for=timezone.now() - timedelta(minutes=5))
        late.refresh_from_db()
        self.assertEqual(rescate.options(late)['why_not'], 'Su hora ya pasó: ya no se puede publicar ni rehacer.')
        self.assertFalse(retoque.rescatable(late))
        stopped = self.blocked(days=6, reasons=('Ciclo detenido: cost_cap',))
        stopped.verification = {}
        stopped.save()
        self.assertIsNone(rescate.options(stopped))  # the autopilot redoes it
        self.assertIsNone(self.human.get(f'/api/v1/editorial/pieces/{stopped.id}').json()['rescue'])

    def test_a_comment_on_a_blocked_piece_reopens_it_and_the_new_version_goes_to_the_leader(self):
        piece = self.blocked()
        routed, _outcome, _state, _role = capturas._route_piece(self.comment(piece, 'x'), self.gustavo, 'x')
        self.assertEqual(routed['rework'], 'pending')
        capture = self.comment(piece, 'Quita la frase de venta del final.')
        plan = {'retoque': decision('texto', text=NEW_POST), 'verificador': answers(final=NEW_POST)['verificador']}
        with self.no_vision():
            capture = self.rework(capture, plan)
        piece.refresh_from_db()
        self.assertEqual(capture.routed_to['rework']['state'], 'rehecha')
        self.assertEqual(piece.state, EditorialPiece.State.READY)
        self.assertTrue(piece.images.exists())
        base = piece.proposals.get(state='discarded')
        new = piece.proposals.get(state='proposed')  # the autopilot sends it to the leader, soft for his comment
        self.assertEqual((new.previous_id, new.payload['text']), (base.id, NEW_POST))
        self.assertFalse(any(str(r).startswith('Bloqueada por') for r in new.risks))
        self.assertEqual(self.calls[0][0], 'editorial-retoque')
        self.assertEqual(self.calls[0][1]['bloqueo'], ['Contiene pitch agresivo o petición de contacto'])
        self.assertEqual(piece.verification['verdict'], 'ready_for_execution')
        self.assertEqual(autopiloto.post_issues(new), [])

