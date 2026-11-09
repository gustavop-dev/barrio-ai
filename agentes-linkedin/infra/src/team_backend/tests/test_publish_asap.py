"""Natural-language priority uses the existing structured call or one Jev Noul call, never keywords alone."""
import json
import os
from datetime import datetime, timedelta
from unittest.mock import patch
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone
from team_backend import autopiloto, capture_intent, capturas, editorial, operador, urgente
from team_backend.models import Capture, EditorialPiece, Job, Notification
from team_backend.tests.test_publicacion import EditorialBase, answers
from team_backend.tests.test_capturas import CaptureBase, audio


class PriorityTests(EditorialBase):
    def idea(self,note='Publica esta idea cuanto antes.',earliest=None):
        return Capture.objects.create(created_by=self.gustavo,purpose='post',note=note,state='idea',publish_asap=True,
            publish_asap_evidence=note,publish_asap_not_before=earliest)

    def test_next_window_keeps_existing_piece_and_assigns_one_idea_per_slot(self):
        now=timezone.now();first=urgente.free_slot(self.official,now)
        existing=EditorialPiece.objects.create(account=self.official,slot_date=first.astimezone(operador.local_tz()).date(),
            scheduled_for=first,state='ready')
        one=self.idea();two=self.idea('Que salga ya.');urgente.assign_slots(now)
        one.refresh_from_db();two.refresh_from_db();existing.refresh_from_db()
        self.assertGreater(one.publish_asap_expected_slot,first)
        self.assertGreater(two.publish_asap_expected_slot,one.publish_asap_expected_slot)
        self.assertEqual(existing.scheduled_for,first)
        self.assertIn('conservan',one.publish_asap_reason)
        self.assertEqual(Notification.objects.filter(kind='capture_scheduled').count(),2)
        urgente.assign_slots(now);self.assertEqual(Notification.objects.filter(kind='capture_scheduled').count(),2)

    def test_tomorrow_and_veto_period_never_mean_publish_immediately(self):
        now=datetime(2026,11,9,8,20,tzinfo=operador.local_tz())
        with patch('django.utils.timezone.now',return_value=now):
            capture=self.idea(earliest=now.date()+timedelta(days=1));urgente.assign_slots(now);capture.refresh_from_db()
        self.assertEqual(capture.publish_asap_expected_slot.astimezone(operador.local_tz()).date(),now.date()+timedelta(days=1))
        self.assertGreaterEqual(capture.publish_asap_expected_slot,now+urgente.veto_window())

    def test_budget_and_approval_gates_still_apply(self):
        c=self.idea()
        with patch.dict(os.environ,{'EDITORIAL_DAILY_LLM_USD':'0'}):
            urgente.assign_slots();c.refresh_from_db();self.assertIn('presupuesto',c.publish_asap_reason)
            self.assertEqual(autopiloto._editorial(self.autobot,timezone.now()),0)
        with patch.dict(os.environ,{'OPERATOR_AUTONOMY':'CONT-09=off'}):
            urgente.assign_slots();c.refresh_from_db();self.assertIsNone(c.publish_asap_expected_slot)
        with patch.dict(os.environ,{'OPERATOR_AUTONOMY':'CONT-09=approval'}):
            plan=answers();plan['director']['ideas_used']=[str(c.id)];piece=self.plan(plan)
            proposal=piece.proposals.get();autopiloto.policy_review(proposal)
            self.assertEqual(proposal.state,'proposed');self.assertEqual(self.linkedin.state['posts'],[])
            c.refresh_from_db();self.assertEqual(c.state,'usado')
            self.assertEqual(self.calls[0][1]['priority_capture']['id'],str(c.id))

    def test_director_must_use_reserved_idea_or_skip_without_lowering_quality(self):
        c=self.idea();plan=answers();piece=self.plan(plan)
        self.assertEqual(piece.state,'skipped');self.assertFalse(piece.proposals.exists())
        c.refresh_from_db();self.assertEqual(c.state,'idea')
        self.assertEqual([x[0] for x in self.calls],['editorial-director'])

    def test_urgent_idea_still_passes_verifier_and_releases_on_block(self):
        c=self.idea();plan=answers();plan['director']['ideas_used']=[str(c.id)]
        plan['verificador']['verdict']='blocked';piece=self.plan(plan)
        self.assertEqual(piece.state,'blocked');c.refresh_from_db();self.assertEqual(c.state,'idea')
        self.assertFalse(piece.proposals.exists());self.assertEqual(self.linkedin.state['posts'],[])

    def test_slow_preparation_moves_slot_to_preserve_notice(self):
        now=timezone.now();piece=EditorialPiece.objects.create(account=self.official,slot_date=now.date(),
            scheduled_for=now+timedelta(minutes=5),state='preparing')
        c=self.idea();capturas.mark_used([str(c.id)],piece)
        urgente.ensure_veto(piece);c.refresh_from_db()
        self.assertGreaterEqual(piece.scheduled_for,now+urgente.veto_window())
        self.assertEqual(c.publish_asap_expected_slot,piece.scheduled_for)


class CaptureIntentTests(CaptureBase):
    def test_transcript_and_note_share_structured_understanding_call(self):
        response={'destino':'post','motivo':'Idea para publicar','publish_asap':True,'evidence':'sácalo mañana',
                  'not_before':'','photo_instructions':[]}
        with self.transcriber('Esto es urgente, sácalo mañana.'),\
             patch('knowledge.providers.claude',return_value={'text':json.dumps(response)}) as model,\
             patch('knowledge.providers.typesafe',side_effect=AssertionError('extra call')):
            body=self.send(nota='Una idea sobre las decisiones de producto.',audio=audio());self.drain()
        c=self.capture(body);self.assertTrue(c.publish_asap);self.assertEqual(c.publish_asap_evidence,'sácalo mañana')
        self.assertEqual(model.call_count,1)
        data=json.loads(model.call_args.args[1]);self.assertIn('decisiones',data['texto']);self.assertIn('mañana',data['texto'])

    def test_explicit_destination_uses_noul_and_literal_evidence(self):
        def jev(state,questions,purpose):
            self.assertEqual(purpose,'capture-intent');self.assertTrue(all(q['type']=='noul' for q in questions.values()))
            return {'answers':{'span_0':{'noul':.99},'tomorrow':{'noul':.99}},'model':'fake'}
        with patch('knowledge.providers.typesafe',side_effect=jev) as model,\
             patch('knowledge.providers.claude',side_effect=AssertionError('extra Claude call')):
            body=self.send(para='post',nota='Esto es urgente, sácalo mañana.');self.drain()
        c=self.capture(body);self.assertTrue(c.publish_asap);self.assertEqual(model.call_count,1)
        self.assertEqual(c.publish_asap_evidence,c.note)
        self.assertEqual(c.publish_asap_not_before,timezone.now().astimezone(operador.local_tz()).date()+timedelta(days=1))

    def test_negation_low_confidence_and_invented_quote_never_set_priority(self):
        for note in ('No lo publiques aún; no es urgente.','Un cliente dijo «que salga ya».','La urgencia afecta al soporte.'):
            with patch('knowledge.providers.typesafe',return_value={'answers':{'span_0':{'noul':.1}},'model':'fake'}):
                body=self.send(para='post',nota=note);self.drain()
            self.assertFalse(self.capture(body).publish_asap)
        c=Capture.objects.create(created_by=self.gustavo,note='Una idea sin urgencia',state='procesando')
        capture_intent.apply(c,{'publish_asap':True,'evidence':'publícalo ya','not_before':'','photo_instructions':[]})
        self.assertFalse(c.publish_asap)

    def test_unavailable_jev_records_error_and_preserves_capture(self):
        with patch('knowledge.providers.typesafe',side_effect=ValueError('No disponible')) as model:
            body=self.send(para='post',nota='Una propuesta');self.drain()
        c=self.capture(body);self.assertEqual(c.state,'idea');self.assertFalse(c.publish_asap)
        self.assertEqual(c.understanding['error'],'No disponible');self.assertEqual(model.call_count,1)


class ImageMigrationTests(TransactionTestCase):
    """Exercise the historical schema, not a reimplementation of its boolean mapping."""
    def test_boolean_photos_and_preferences_are_migrated_without_loss(self):
        before=[('team_backend','0018_push_enabled')];after=[('team_backend','0019_imagenes_y_urgencia')]
        executor=MigrationExecutor(connection);executor.migrate(before)
        try:
            apps=executor.loader.project_state(before).apps
            Photo=apps.get_model('team_backend','GalleryPhoto');Preference=apps.get_model('team_backend','OfficePreference')
            allowed=Photo.objects.create(image='original-a.png',mime='image/png',size_bytes=1,allow_ai_edit=True)
            denied=Photo.objects.create(image='original-b.png',mime='image/png',size_bytes=1,allow_ai_edit=False)
            Preference.objects.update_or_create(pk=1,defaults={'gallery_ai_edit_default':False})
            executor=MigrationExecutor(connection);executor.migrate(after)
            apps=executor.loader.project_state(after).apps;Photo=apps.get_model('team_backend','GalleryPhoto')
            self.assertEqual(Photo.objects.get(pk=allowed.pk).ai_edit,'auto')
            self.assertEqual(Photo.objects.get(pk=denied.pk).ai_edit,'no')
            self.assertEqual(Photo.objects.get(pk=denied.pk).image.name,'original-b.png')
            self.assertEqual(apps.get_model('team_backend','OfficePreference').objects.get(pk=1).gallery_ai_edit,'no')
        finally:
            executor=MigrationExecutor(connection)
            executor.migrate(executor.loader.graph.leaf_nodes())
