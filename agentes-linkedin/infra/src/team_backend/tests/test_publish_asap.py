"""Natural-language priority uses the existing structured call or one Jev Noul call, never keywords alone."""
import json
import os
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from unittest.mock import patch
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import SimpleTestCase, TransactionTestCase
from django.utils import timezone
from team_backend import autopiloto, capture_intent, capturas, cuando, editorial, operador, urgente
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
        with patch.dict(os.environ,{'AI_DAILY_FUSE_USD':'0'}):
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


class IdeaScheduleTests(EditorialBase):
    """Each idea of Gustavo gets its window on arrival and is prepared right away; his day/hour wins."""
    def idea(self,note='Una idea sobre decisiones de producto.',**fields):
        return Capture.objects.create(created_by=self.gustavo,purpose='post',note=note,state='idea',**fields)

    def test_an_idea_without_date_queues_behind_scheduled_posts_and_is_prepared_right_away(self):
        now=timezone.now();tz=operador.local_tz();first=urgente.free_slot(self.official,now).astimezone(tz).date()
        for i in range(3):  # the next three days already have a post
            day=first+timedelta(days=i)
            EditorialPiece.objects.create(account=self.official,slot_date=day,scheduled_for=editorial.scheduled_for(day),state='ready')
        c=self.idea();urgente.assign_slots(now);c.refresh_from_db()
        fourth=first+timedelta(days=3)
        self.assertEqual(c.publish_asap_expected_slot,editorial.scheduled_for(fourth))
        self.assertIn('El equipo empieza a prepararla ya',c.publish_asap_reason)
        self.assertEqual(Notification.objects.get(kind='capture_scheduled').title,'Tu idea ya tiene fecha')
        # Four days ahead is far outside EDITORIAL_LEAD_HOURS: the idea is prepared now anyway.
        self.assertEqual(autopiloto._editorial(self.autobot,now),1)
        self.assertEqual(Job.objects.get(kind='prepare_piece').params['slot'],fourth.isoformat())

    def test_a_requested_day_and_hour_wins_over_the_teams_own_post_which_moves_to_the_next_free_day(self):
        now=timezone.now();tz=operador.local_tz();tomorrow=now.astimezone(tz).date()+timedelta(days=1)
        team=EditorialPiece.objects.create(account=self.official,slot_date=tomorrow,scheduled_for=editorial.scheduled_for(tomorrow),state='ready')
        asked=datetime.combine(tomorrow,time(10,0),tzinfo=tz)
        c=self.idea('Publícalo mañana a las 10.',publish_at=asked,publish_at_evidence='Publícalo mañana a las 10.')
        urgente.assign_slots(now);c.refresh_from_db();team.refresh_from_db()
        self.assertEqual(c.publish_asap_expected_slot,asked);self.assertGreater(team.slot_date,tomorrow)
        self.assertEqual(urgente.reserved_at(tomorrow),asked)
        self.assertTrue(Notification.objects.filter(kind='capture_scheduled',title='Movimos un post para darle tu hora').exists())
        plan=answers();plan['director']['ideas_used']=[str(c.id)];piece=self.plan(plan)
        self.assertEqual((piece.slot_date,piece.scheduled_for),(tomorrow,asked))
        self.assertEqual(self.calls[0][1]['priority_capture']['id'],str(c.id))

    def test_an_idea_the_director_does_not_take_stays_on_the_table_without_being_retried(self):
        c=self.idea();urgente.assign_slots();c.refresh_from_db()
        day=c.publish_asap_expected_slot.astimezone(operador.local_tz()).date()
        piece=self.plan(answers())  # the director does not list the idea in ideas_used
        self.assertEqual((piece.state,piece.slot_date),('skipped',day))
        c.refresh_from_db();self.assertEqual((c.state,c.publish_asap_expected_slot,c.routed_to['declined_in']),('idea',None,str(piece.id)))
        self.assertIsNone(urgente.next_slot());c.refresh_from_db();self.assertIsNone(c.publish_asap_expected_slot)
        self.assertTrue(editorial.idea_retry(EditorialPiece.objects.filter(slot_date=day)))  # the day stays open for the daily post
        self.assertTrue(Notification.objects.filter(title='Tu idea no salió en su fecha').exists())

    def test_a_failed_preparation_counts_one_attempt_and_two_leave_the_idea_without_a_date(self):
        """10/11: the piece of an idea was blocked and the idea jumped to the next day and was prepared again at once,
        day after day, until the 14-day horizon was full."""
        now=timezone.now();tz=operador.local_tz()
        c=self.idea();urgente.assign_slots(now);c.refresh_from_db();first=c.publish_asap_expected_slot
        blocked=EditorialPiece.objects.create(account=self.official,slot_date=first.astimezone(tz).date(),scheduled_for=first,
            state='blocked',note='El verificador emitió blocked; Hallazgo material',brief={'reserved_capture':str(c.id)})
        urgente.assign_slots(now);c.refresh_from_db();second=c.publish_asap_expected_slot
        self.assertEqual(c.routed_to['intentos'],1);self.assertGreater(second,first)
        self.assertTrue(editorial.idea_retry([blocked]))  # that day stays free for the autopilot's own post
        urgente.assign_slots(now);c.refresh_from_db();self.assertEqual(c.routed_to['intentos'],1)  # counted once
        EditorialPiece.objects.create(account=self.official,slot_date=second.astimezone(tz).date(),scheduled_for=second,
            state='failed',note='Preparación fallida')
        urgente.assign_slots(now);c.refresh_from_db()
        self.assertEqual((c.routed_to['intentos'],c.publish_asap_expected_slot),(2,None))
        self.assertIn('dos veces',c.publish_asap_reason)
        self.assertIsNone(urgente.next_slot(now))

    def test_a_day_stopped_only_for_budget_stays_free_and_nothing_starts_without_budget(self):
        now=timezone.now();tz=operador.local_tz()
        c=self.idea();urgente.assign_slots(now);c.refresh_from_db();first=c.publish_asap_expected_slot;day=first.astimezone(tz).date()
        stopped=EditorialPiece.objects.create(account=self.official,slot_date=day,scheduled_for=first,state='blocked',note='Ciclo detenido: cost_cap')
        urgente.assign_slots(now);c.refresh_from_db()
        self.assertEqual((c.publish_asap_expected_slot,c.routed_to.get('intentos',0)),(first,0))  # same day, no attempt spent
        self.assertTrue(editorial.budget_retry([stopped],now+timedelta(days=1)))
        with patch.object(editorial,'budget_left',return_value=Decimal('2')):  # less than a whole preparation
            self.assertIsNone(urgente.next_slot(now));self.assertEqual(autopiloto._editorial(self.autobot,now),0)
        self.assertEqual(urgente.next_slot(now),day)


class WhenTests(SimpleTestCase):
    def test_spanish_days_and_hours(self):
        today=date(2026,11,10)  # a Tuesday
        cases={'Publícalo mañana a las 10':(date(2026,11,11),time(10,0)),
               'que salga el jueves a las 3 de la tarde':(date(2026,11,12),time(15,0)),
               'pasado mañana a las 9 de la mañana':(date(2026,11,12),time(9,0)),
               'el 14 de noviembre a las 10:30':(date(2026,11,14),time(10,30)),
               'mañana por la mañana':(date(2026,11,11),None),
               'a las 6 y media':(None,time(18,30)),
               'el martes al mediodía':(date(2026,11,17),time(12,0)),
               'publícalo a las ocho de la noche':(None,time(20,0)),
               'publícalo esta mañana a las 11':(date(2026,11,10),time(11,0)),
               'hoy a las 10am':(date(2026,11,10),time(10,0)),
               'súbelo esta tarde':(date(2026,11,10),None),
               'mañana a las 7:15 p.m.':(date(2026,11,11),time(19,15)),
               'dale 5 a mis contactos':(None,None),
               'Una idea sobre decisiones de producto':(None,None)}
        for text,expected in cases.items():
            with self.subTest(text=text):self.assertEqual(cuando.parse(text,today),expected)


class CaptureIntentTests(CaptureBase):
    def test_a_requested_day_and_hour_comes_only_from_a_literal_fragment(self):
        tz=operador.local_tz();tomorrow=timezone.now().astimezone(tz).date()+timedelta(days=1)
        def jev(state,questions,purpose):
            return {'answers':{'when_1':{'noul':.99}},'model':'fake'}
        with patch('knowledge.providers.typesafe',side_effect=jev):
            body=self.send(para='post',nota='Una idea sobre decisiones. Publícalo mañana a las 10.');self.drain()
        c=self.capture(body)
        self.assertEqual((c.publish_at,c.publish_at_evidence),(datetime.combine(tomorrow,time(10,0),tzinfo=tz),'Publícalo mañana a las 10.'))
        capture_intent.apply(c,{'publish_asap':False,'evidence':'','not_before':'','publish_when':'el viernes a las 9','photo_instructions':[]})
        self.assertIsNone(c.publish_at)  # not literal in what he sent

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
