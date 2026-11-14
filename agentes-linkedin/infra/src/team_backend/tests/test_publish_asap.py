"""Natural-language priority uses the existing structured call or one Jev Noul call, never keywords alone."""
import json
import os
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from unittest.mock import patch
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import SimpleTestCase, TransactionTestCase
from django.utils import timezone
from team_backend import autopiloto, capture_intent, capturas, cuando, editorial, operador, urgente
from team_backend.models import ActionExecution, Capture, EditorialPiece, Job, Notification
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
        fields.setdefault('state','idea')  # a capture of the old flow comes already used
        return Capture.objects.create(created_by=self.gustavo,purpose='post',note=note,**fields)

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

    def test_a_requested_day_and_hour_is_an_extra_post_and_the_days_own_never_moves(self):
        """Gustavo, 14/11/2026: «una fecha explícita es una orden». Before, his dated idea could take the next free day,
        move the team's post or wait for a «sí» in Tu turno days later. Now it goes out that day at that hour as an extra
        post next to the daily one, outside the CONT-09 caps, and nobody asks."""
        now=timezone.now();tz=operador.local_tz();tomorrow=now.astimezone(tz).date()+timedelta(days=1)
        team=EditorialPiece.objects.create(account=self.official,slot_date=tomorrow,scheduled_for=editorial.scheduled_for(tomorrow),
            state='ready',brief={'reserved_capture':'otra-idea','thesis':'Los ciclos entre agentes son la decisión difícil'})
        asked=datetime.combine(tomorrow,time(10,0),tzinfo=tz)
        c=self.idea('Publícalo mañana a las 10.',publish_at=asked,publish_at_evidence='Publícalo mañana a las 10.')
        urgente.assign_slots(now);c.refresh_from_db();team.refresh_from_db()
        self.assertEqual((c.publish_asap_expected_slot,c.day_request),(asked,{}))
        self.assertEqual((team.slot_date,team.scheduled_for,team.second_of_day),(tomorrow,editorial.scheduled_for(tomorrow),False))
        self.assertIn('además del post diario',c.publish_asap_reason)
        self.assertEqual((urgente.extra_at(tomorrow),urgente.reserved_at(tomorrow)),(asked,None))
        self.assertEqual(self.human.get('/api/v1/tu-turno').json()['tasks']['fechas'],[])  # nothing to ask
        self.assertEqual(urgente.next_slot(now),None)  # the day's own post is not his idea's
        plan=answers();plan['director']['ideas_used']=[str(c.id)];piece=self.plan(plan)
        self.assertEqual((piece.slot_date,piece.scheduled_for,piece.second_of_day),(tomorrow,asked,True))
        self.assertEqual(self.calls[0][1]['priority_capture']['id'],str(c.id))
        self.assertEqual([i['id'] for i in self.calls[0][1]['ideas_from_gustavo']],[str(c.id)])  # about his idea only
        team.refresh_from_db();self.assertEqual(team.scheduled_for,editorial.scheduled_for(tomorrow))
        # Two posts that day at most.
        with self.assertRaises(IntegrityError),transaction.atomic():
            EditorialPiece.objects.create(account=self.official,slot_date=tomorrow,scheduled_for=asked,state='preparing',second_of_day=True)
        # Outside the caps: the extra post neither counts for CONT-09 nor waits for it.
        proposal=piece.proposals.get();self.assertFalse(operador.capped(proposal))
        before=operador.capacity_left(self.official,'CONT-09')
        ActionExecution.objects.create(proposal=proposal,idempotency_key='extra-post',provider='fake',state='confirmed',executed_by=self.gustavo)
        self.assertEqual(operador.capacity_left(self.official,'CONT-09'),before)

    def test_the_autopilot_prepares_the_extra_post_right_away_and_once(self):
        now=timezone.now();tz=operador.local_tz();day=now.astimezone(tz).date()+timedelta(days=2)
        asked=datetime.combine(day,time(18,0),tzinfo=tz)
        self.idea('Que salga pasado mañana a las 6.',publish_at=asked,publish_at_evidence='pasado mañana a las 6')
        self.assertEqual(autopiloto._editorial(self.autobot,now),1)  # two days ahead: outside EDITORIAL_LEAD_HOURS anyway
        job=Job.objects.get(kind='prepare_piece');self.assertEqual((job.params['slot'],job.params.get('extra')),(day.isoformat(),True))
        self.assertIsNone(urgente.next_extra(now))  # queued once
        self.assertEqual(autopiloto._editorial(self.autobot,now),0)
        self.assertEqual(Job.objects.filter(kind='prepare_piece').count(),1)

    def test_a_date_that_cannot_be_kept_asks_in_the_bandeja_at_once_and_waits_for_his_answer(self):
        now=timezone.now();tz=operador.local_tz();tomorrow=now.astimezone(tz).date()+timedelta(days=1)
        asked=datetime.combine(tomorrow,time(12,0),tzinfo=tz)
        # Another idea of his already holds tomorrow's extra post: a third post that day is the one thing not done.
        EditorialPiece.objects.create(account=self.official,slot_date=tomorrow,scheduled_for=asked-timedelta(hours=3),state='ready',second_of_day=True)
        c=self.idea('Publícalo mañana al mediodía.',publish_at=asked,publish_at_evidence='mañana al mediodía')
        urgente.assign_slots(now);c.refresh_from_db()
        self.assertEqual((c.day_request['state'],c.day_request['problem'],c.publish_asap_expected_slot),('problem','llena',None))
        self.assertIn('Esperando tu respuesta',c.publish_asap_reason)
        self.assertNotIn(str(c.id),[i['id'] for i in capturas.ideas_for_director(now)])  # not written meanwhile
        self.assertEqual(urgente.tick_day_requests(now),1);self.assertEqual(urgente.tick_day_requests(now),0)  # one push
        [card]=self.human.get('/api/v1/tu-turno').json()['tasks']['fechas']
        self.assertEqual((card['type'],card['day_request']['problem'],card['day_request']['piece']),('fecha','llena',None))
        self.assertIn('Ese día ya tiene dos posts',card['body']);self.assertIn('mañana al mediodía',card['body'])
        self.assertEqual([a['body'] for a in card['actions'] if 'body' in a],[{'decision':'siguiente'},{'decision':'descartar'}])
        self.assertEqual(self.human.post(f'/api/v1/capturas/{c.id}/fecha',{'decision':'mismo_dia'},format='json').status_code,400)
        response=self.human.post(f'/api/v1/capturas/{c.id}/fecha',{'decision':'siguiente'},format='json')
        self.assertEqual(response.status_code,200,response.content)
        c.refresh_from_db()
        self.assertEqual((c.day_request['state'],c.publish_at,response.json()['state']),('next_free',None,'idea'))
        self.assertIsNotNone(c.publish_asap_expected_slot);self.assertFalse(urgente.is_extra(c))
        self.assertEqual(self.human.get('/api/v1/tu-turno').json()['tasks']['fechas'],[])
        self.assertEqual(self.human.post(f'/api/v1/capturas/{c.id}/fecha',{'decision':'descartar'},format='json').status_code,409)
        self.assertEqual(urgente.recently_resolved()[0]['how'],'Va al primer día libre')

    def test_discarding_an_idea_whose_date_cannot_be_kept(self):
        now=timezone.now()
        c=self.idea('Publícalo hoy a las 10.',publish_at=now-timedelta(hours=1),publish_at_evidence='hoy a las 10')
        urgente.assign_slots(now);c.refresh_from_db();self.assertEqual(c.day_request['problem'],'pasada')
        response=self.human.post(f'/api/v1/capturas/{c.id}/fecha',{'decision':'descartar'},format='json')
        self.assertEqual(response.status_code,200,response.content)
        c.refresh_from_db();self.assertEqual((c.state,c.day_request['state'],c.publish_asap_expected_slot),('sin_usar','discarded',None))

    def test_a_question_of_the_old_flow_moves_his_post_to_his_date_when_it_still_can(self):
        """Before 14/11 his post waited on the next free day for a «sí» (state pending). His date is an order now."""
        now=timezone.now();tz=operador.local_tz();tomorrow=now.astimezone(tz).date()+timedelta(days=1)
        asked=datetime.combine(tomorrow,time(12,0),tzinfo=tz);later=editorial.scheduled_for(tomorrow+timedelta(days=3))
        piece=EditorialPiece.objects.create(account=self.official,slot_date=tomorrow+timedelta(days=3),scheduled_for=later,state='ready')
        c=self.idea('Publícalo mañana al mediodía.',publish_at=asked,publish_at_evidence='mañana al mediodía',state='usado',
                    routed_to={'used_in':str(piece.id)},day_request={'state':'pending','asked':asked.isoformat()})
        urgente.tick_day_requests(now);c.refresh_from_db();piece.refresh_from_db()
        self.assertEqual((piece.slot_date,piece.scheduled_for,piece.second_of_day),(tomorrow,asked,True))
        self.assertEqual(c.day_request['state'],'same_day')
        # One the old flow left too late expires; its post keeps its day.
        other=EditorialPiece.objects.create(account=self.official,slot_date=tomorrow+timedelta(days=4),
            scheduled_for=editorial.scheduled_for(tomorrow+timedelta(days=4)),state='ready')
        d=self.idea('Publícalo ya.',publish_at=now+timedelta(minutes=5),publish_at_evidence='ya',state='usado',
                    routed_to={'used_in':str(other.id)},day_request={'state':'pending','asked':(now+timedelta(minutes=5)).isoformat()})
        urgente.tick_day_requests(now);d.refresh_from_db();other.refresh_from_db()
        self.assertEqual((d.day_request['state'],other.second_of_day),('expired',False))

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

    def test_a_date_that_cannot_be_kept_is_a_problem_never_another_day(self):
        tz=operador.local_tz();now=datetime(2026,11,10,15,0,tzinfo=tz)  # a Tuesday afternoon
        ask=lambda words:capture_intent.requested('Una idea. '+words,words,now)
        self.assertEqual(ask('Publícalo hoy a las 10'),(datetime(2026,11,10,10,0,tzinfo=tz),'Publícalo hoy a las 10','pasada'))
        self.assertEqual(ask('el 30 de noviembre a las 10')[2],'lejana')
        self.assertEqual(ask('dale cuando veas'),(None,'dale cuando veas','ambigua'))
        # A day without an hour goes out at EDITORIAL_EXTRA_TIME, away from the daily post; today, as soon as the notice allows.
        self.assertEqual(ask('Publícalo el jueves'),(datetime(2026,11,12,12,0,tzinfo=tz),'Publícalo el jueves',None))
        with patch.dict(os.environ,{'EDITORIAL_EXTRA_TIME':'09:00'}):
            when,_,problem=ask('súbelo esta tarde')
        self.assertIsNone(problem);self.assertGreaterEqual(when,now+urgente.veto_window());self.assertEqual(when.minute%15,0)
        self.assertEqual(capture_intent.requested('Una idea.','el viernes',now),(None,'',None))  # not literal: nothing asked
        # The capture keeps no date and the Bandeja asks him at once.
        c=Capture.objects.create(created_by=self.gustavo,note='Una idea. Publícalo hoy a las 10.',state='idea')
        with patch('django.utils.timezone.now',return_value=now):
            capture_intent.apply(c,{'publish_asap':False,'evidence':'','not_before':'','publish_when':'Publícalo hoy a las 10',
                                    'photo_instructions':[]})
        c.refresh_from_db()
        self.assertEqual((c.publish_at,c.day_request['state'],c.day_request['problem']),(None,'problem','pasada'))
        self.assertEqual(c.day_request['asked'],datetime(2026,11,10,10,0,tzinfo=tz).isoformat())

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
