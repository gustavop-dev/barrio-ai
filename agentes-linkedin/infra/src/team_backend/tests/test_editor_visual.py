"""EDI-21/OFI-10 evaluation and regression cases. All providers use fakes; CI only."""
import copy
import json
import os
from decimal import Decimal
from unittest.mock import Mock, patch

from django.utils import timezone
from knowledge import providers
from team_backend import editor_visual, editorial, guardas, imagenes, orquestacion, oficina_views
from team_backend.connectors_images import FakeImageConnector
from team_backend.grafo import load_graph
from team_backend.grafo_views import recent_activity
from team_backend.models import AuditEvent, CycleLedger, EditorialPiece, Job
from team_backend.tests import test_imagenes as image_cases
from team_backend.tests.test_imagenes import png, slide
from team_backend.tests.test_publicacion import EditorialBase, answers


class VisualTests(EditorialBase):
    # Share only the synthetic factories, not the image suite's test methods.
    photo = image_cases.ImageWorkflowTests.photo
    piece = image_cases.ImageWorkflowTests.piece

    def visual(self, piece, client=None, available=False):
        public, private = guardas.blocks()
        run = orquestacion.Runtime.open('pieza_diaria', str(piece.id), self.gustavo)
        with run.session(), patch('team_backend.connectors_images.available', return_value=available), \
                patch('team_backend.connectors_images.ImageConnector', return_value=client or FakeImageConnector()):
            editorial._visual(piece, public, private)
        return run

    def test_empty_gallery_uses_existing_brand_card_and_hands_back_once(self):
        piece = self.piece(kind='infografia')
        # Use the real unavailable connector so IMG chooses its no-provider fallback.
        public, private = guardas.blocks()
        run = orquestacion.Runtime.open('pieza_diaria', str(piece.id), self.gustavo)
        with patch('team_backend.connectors_images.available', return_value=False), \
                patch('knowledge.providers.claude', side_effect=AssertionError('No paid call')):
            with run.session():
                editorial._visual(piece, public, private)
            count = AuditEvent.objects.filter(action='office.orchestration').count()
            with run.session():
                editorial._visual(piece, public, private)
        self.assertEqual(piece.image_kind, 'tarjeta')
        self.assertEqual(piece.images.count(), 1)
        self.assertEqual(imagenes.issues(piece, imagenes.manifest(piece)), [])
        self.assertEqual(piece.selection['visual']['decided_by'], 'director_editorial')
        self.assertEqual(piece.selection['visual']['final_kind'], 'tarjeta')
        self.assertEqual(piece.usage, [{'stage': 'visual', 'mode': 'fallback', 'model': None}])
        ledger = CycleLedger.objects.get(pk=run.id)
        self.assertEqual(ledger.calls, 2)
        events = list(AuditEvent.objects.filter(action='office.orchestration').order_by('id').values_list('metadata', flat=True))
        self.assertEqual(len(events), count)
        self.assertEqual([(e['rol'], e['destino']) for e in events],
            [('director_editorial', 'editor_visual'), ('editor_visual', 'director_editorial')] * 2)
        self.assertNotIn('public_facts', str(events))
        self.assertFalse(piece.proposals.exists())

    def test_visual_usage_records_the_selector_model(self):
        piece = self.piece(photo=self.photo(ai='no'))
        with patch('knowledge.providers.claude', return_value={'text': json.dumps(piece.brief['image'])}) as model:
            self.visual(piece, available=True)
        model.assert_called_once()
        self.assertEqual(model.call_args.kwargs['purpose'], 'editorial-visual')
        self.assertEqual(piece.usage, [{'stage': 'visual', 'mode': 'model', 'model': model.call_args.kwargs['model']}])
        self.assertEqual(piece.image_kind, 'foto')
        self.assertFalse(piece.images.get().edited)

    def test_no_edit_and_vision_rejection_keep_img_outcomes(self):
        for ai, ok, edited in [('no', True, False), ('si', False, False), ('si', True, True)]:
            with self.subTest(ai=ai, ok=ok):
                photo = self.photo(ai=ai)
                piece = self.piece(photo=photo, edit='light')
                fake = FakeImageConnector(ok=ok, edited=png(color='#dedfd4'))
                run = self.visual(piece, fake)
                row = piece.images.get()
                self.assertEqual(row.edited, edited)
                self.assertEqual(row.source_photo_id, photo.id)
                self.assertEqual(imagenes.issues(piece, imagenes.manifest(piece)), [])
                if not edited:
                    self.assertEqual(imagenes.read(row.image), imagenes.read(photo.image))
                calls = CycleLedger.objects.get(pk=run.id).progress_ledger['calls'].values()
                edits = [c for c in calls if c['edge'] == 'editar_foto']
                self.assertEqual(len(edits), 0 if ai == 'no' else 1)
                if edits:
                    self.assertEqual(edits[0]['nodes'], ['editor_visual'])
                legacy = self.piece(photo=self.photo(ai=ai), edit='light')
                imagenes.prepare(legacy, client=FakeImageConnector(ok=ok, edited=png(color='#dedfd4')))
                previous = legacy.images.get()
                self.assertEqual((row.kind, row.sha256, row.alt, row.edited, row.reason),
                    (previous.kind, previous.sha256, previous.alt, previous.edited, previous.reason))

    def test_carousel_reuses_structured_design_render_and_vision_gate(self):
        piece = self.piece(kind='carrusel')
        data = {'slides': [slide('portada'), slide(), slide('cierre')]}
        fake = FakeImageConnector()
        with patch('knowledge.providers.claude', return_value={'text': json.dumps(data)}) as model:
            run = self.visual(piece, fake)
        self.assertEqual(piece.image_kind, 'carrusel')
        self.assertEqual(piece.images.count(), 3)
        self.assertTrue(imagenes.read(piece.image_document).startswith(b'%PDF-1.7'))
        self.assertEqual([call[0] for call in fake.calls], ['check'])
        self.assertEqual(model.call_args.kwargs['purpose'], 'image-design')
        self.assertEqual(imagenes.issues(piece, imagenes.manifest(piece)), [])
        calls = CycleLedger.objects.get(pk=run.id).progress_ledger['calls']
        # JSONB objects have no execution order. Check dispatch by key, then the chronological handoffs.
        self.assertEqual({key: (c['edge'], c['nodes'], c['state']) for key, c in calls.items()}, {
            'visual:proposal': ('proponer_visual', ['editor_visual'], 'answered'),
            'design:0': ('disenar', ['editor_visual'], 'answered'),
            'check:design:0': ('revisar_imagen', ['revision_visual'], 'answered'),
            'visual:package': ('entregar_visual', ['editor_visual'], 'answered'),
        })
        requests = AuditEvent.objects.filter(action='office.orchestration', metadata__cycle_id=str(run.id),
            metadata__phase='request').order_by('created_at', 'id')
        self.assertEqual(list(requests.values_list('metadata__edge', flat=True)),
            ['proponer_visual', 'disenar', 'revisar_imagen', 'entregar_visual'])

    def test_known_selector_budget_failure_keeps_original_without_retry(self):
        piece = self.piece(photo=self.photo(ai='no'))
        with patch.object(editor_visual, 'propose', side_effect=ValueError('Presupuesto de planificación agotado')) as selector:
            run = self.visual(piece)
        self.assertEqual(selector.call_count, 1)
        self.assertEqual(piece.image_kind, 'foto')
        self.assertFalse(piece.images.get().edited)
        self.assertEqual(piece.selection['visual']['mode'], 'fallback')
        calls = CycleLedger.objects.get(pk=run.id).progress_ledger['calls']
        self.assertEqual(calls['visual:proposal']['state'], 'failed')
        self.assertEqual(calls['visual:package']['state'], 'answered')

    def test_invalid_design_or_render_failure_keeps_img_fallback_and_block(self):
        for rendered in (True, False):
            with self.subTest(fallback_can_render=rendered):
                piece = self.piece(kind='infografia')
                with patch('knowledge.providers.claude', return_value={'text': '{}'}):
                    if rendered:
                        self.visual(piece)
                        self.assertEqual(piece.image_kind, 'tarjeta')
                    else:
                        with patch('team_backend.infografias.render', side_effect=ValueError('Render no disponible')):
                            with self.assertRaisesRegex(ValueError, 'Render no disponible'):
                                self.visual(piece)
                        self.assertFalse(piece.images.exists())
                self.assertFalse(piece.proposals.exists())

    def test_uncertain_selector_reservation_stops_before_preparing_and_is_not_retried(self):
        piece = self.piece(kind='infografia')
        def uncertain(request):
            reservation = providers.reserve('anthropic', 'editorial-visual', Decimal('.01'))
            providers.settle(reservation, 'uncertain')
            raise ValueError('Respuesta incierta; reserva retenida')
        with patch.dict(os.environ, {'ANTHROPIC_LIMIT_USD': '100', 'EDITORIAL_DAILY_LLM_USD': '2'}), \
                patch.object(editor_visual, 'propose', side_effect=uncertain) as selector:
            with self.assertRaisesRegex(orquestacion.CycleStopped, 'uncertain'):
                self.visual(piece)
            with self.assertRaises(orquestacion.CycleStopped):
                self.visual(piece)
        selector.assert_called_once()
        row = CycleLedger.objects.get(cycle='pieza_diaria', key=str(piece.id))
        self.assertEqual((row.state, row.stop_reason), ('stopped', 'uncertain'))
        self.assertFalse(piece.images.exists())
        self.assertFalse(piece.proposals.exists())

    def test_selector_uses_exact_winner_and_director_accepts_before_preparation(self):
        piece = self.piece(kind='infografia')
        public, private = guardas.blocks()
        request = editor_visual.request(piece, public, private)
        choice = {'kind': 'carrusel', 'reason': 'El ganador explica un proceso', 'photos': []}
        with patch('team_backend.connectors_images.available', return_value=True), \
                patch('knowledge.providers.claude', return_value={'text': json.dumps(choice)}) as model:
            proposal = editor_visual.propose(request)
        self.assertEqual(json.loads(model.call_args.args[1][0]['text'])['post'], piece.final_text)
        self.assertEqual(model.call_args.kwargs['purpose'], 'editorial-visual')
        self.assertEqual(piece.brief['image']['kind'], 'infografia')
        editor_visual.accept(piece, proposal, public, private)
        self.assertEqual(piece.brief['image']['kind'], 'carrusel')
        self.assertFalse(piece.images.exists())
        piece.final_text += ' Changed.'
        with self.assertRaisesRegex(ValueError, 'otro texto'):
            editor_visual.accept(piece, proposal, public, private)

    def test_unoffered_photos_and_invalid_contract_never_prepare_or_publish(self):
        piece = self.piece(photo=self.photo())
        public, private = guardas.blocks()
        request = editor_visual.request(piece, public, private)
        proposal = copy.deepcopy(editor_visual.fallback(request, 'synthetic'))
        proposal['mode'] = 'model'
        proposal['choice']['photos'][0]['id'] = str(self.photo().id)
        with self.assertRaisesRegex(ValueError, 'no ofrecidas'):
            editor_visual.accept(piece, proposal, public, private)
        run = orquestacion.Runtime.open('pieza_diaria', str(piece.id), self.gustavo)
        with run.session(), self.assertRaises(orquestacion.ContractError):
            run.call('proponer_visual', request, lambda: {'publish': True})
        self.assertFalse(piece.images.exists())
        self.assertFalse(piece.proposals.exists())

    def test_visual_tool_cannot_delegate_or_gain_linkedin_authority(self):
        piece = self.piece(kind='infografia')
        request = editor_visual.request(piece, *guardas.blocks())
        run = orquestacion.Runtime.open('pieza_diaria', str(piece.id), self.gustavo)
        action = Mock()
        with run.session(), self.assertRaisesRegex(orquestacion.UndeclaredCall, 'max_depth'):
            run.call('proponer_visual', request, lambda: run.call('editar_foto', {}, action))
        action.assert_not_called()
        graph = load_graph()
        visual = next(n for n in graph['nodes'] if n['id'] == 'editor_visual')
        self.assertNotIn('linkedin_write', visual['tools'])
        self.assertEqual(graph['gates']['publicacion']['chain'], ['editor_verificador', 'lider_jev', 'gustavo', 'operador_cuenta'])

    def test_changed_text_evidence_permission_and_original_invalidate_package(self):
        for change in ('text', 'source', 'permission', 'original'):
            with self.subTest(change=change):
                photo = self.photo(ai='no')
                piece = self.piece(photo=photo)
                self.visual(piece)
                if change == 'text':
                    piece.final_text += ' Changed.'
                elif change == 'source':
                    piece.signals = [{'id': 'new-source', 'text': 'Changed evidence'}]
                elif change == 'permission':
                    photo.ai_edit = 'si';photo.save(update_fields=['ai_edit'])
                else:
                    from django.core.files.base import ContentFile
                    photo.image.save('changed.png', ContentFile(png(color='#abcdef')), save=True)
                self.assertTrue(any('otro texto, fuentes o permisos' in e for e in imagenes.issues(piece, imagenes.manifest(piece))))

    def test_gallery_publication_bookkeeping_does_not_invalidate_verified_bytes(self):
        piece = self.piece(photo=self.photo(ai='no'))
        self.visual(piece)
        imagenes.published(piece)
        self.assertEqual(imagenes.issues(piece, imagenes.manifest(piece)), [])

    def test_office_and_map_only_attribute_visual_work_that_happened(self):
        now = timezone.now()
        job = Job.objects.create(owner=self.gustavo, kind='prepare_piece', agent='operador', task='synthetic', state='running', started_at=now)
        piece = self.piece(kind='infografia')
        piece.origin_job = str(job.id);piece.stage = 'verificador';piece.save()
        self.assertNotIn('editor_visual', oficina_views._roles(job))
        self.assertEqual(recent_activity(load_graph(), self.gustavo)['editor_visual']['jobs'], [])
        piece.stage = 'visual';piece.save(update_fields=['stage'])
        self.assertEqual(oficina_views._roles(job), ['editor_visual'])
        activity = self.human.get('/api/v1/oficina/actividad').json()['roles']['editor_visual']
        self.assertEqual((activity['status'], activity['piece_id']), ('trabajando', str(piece.id)))
        self.assertEqual(recent_activity(load_graph(), self.gustavo)['editor_visual']['jobs'][0]['id'], str(job.id))
        job.state = 'failed';job.save(update_fields=['state'])
        self.assertIn('editor_visual', oficina_views._roles(job))
        piece.stage = 'verificador';piece.save(update_fields=['stage'])
        self.assertNotIn('editor_visual', oficina_views._roles(job))

    def test_full_editorial_pipeline_preserves_gates_and_adds_real_visual_handoffs(self):
        piece = self.plan(answers())
        self.assertEqual(piece.state, EditorialPiece.State.READY)
        self.assertEqual(piece.verification['verdict'], 'ready_for_execution')
        self.assertEqual(piece.selection['visual']['text_sha256'], piece.verification['text_sha256'])
        self.assertEqual(piece.proposals.get().payload['media'], imagenes.manifest(piece))
        self.assertEqual([c[0] for c in self.calls], ['editorial-director', 'editorial-redactor',
            'editorial-lectores', 'editorial-seleccion', 'editorial-verificador'])
