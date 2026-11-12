"""Phase 2 regressions: synthetic units, fake connectors and fixed clocks; never live services."""
import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone as utc
from unittest.mock import patch

import httpx
from django.db import close_old_connections
from django.apps import apps
from django.utils import timezone

from team_backend import conversaciones, evaluaciones, lider, metricas, operador, red, resumen_semanal
from team_backend.connectors import ConnectorError, ConnectorUncertain, InvitationNoteQuota, UnipileConnector
from team_backend.models import ActionExecution, ActionProposal, AuditEvent, ConnectorAccount, Contact, Conversation
from team_backend.tests.test_red import NetworkBase


class ParticipationTests(NetworkBase):
    def setUp(self):
        super().setUp()
        self.weekend_patch.stop()
        self.now=datetime(2026,11,9,15,tzinfo=utc.utc)  # Monday, 10:00 Bogota
        self.clock=patch('django.utils.timezone.now',return_value=self.now)
        self.clock.start();self.addCleanup(self.clock.stop)
        # Django binds timezone.now when models load; freeze those field defaults too.
        for model in apps.get_app_config('team_backend').get_models():
            for field in model._meta.fields:
                if getattr(field.default,'__module__','')=='django.utils.timezone':
                    default=patch.object(field,'_get_default',new=lambda:timezone.now())
                    default.start();self.addCleanup(default.stop)
        env=patch.dict(os.environ,{'LINKEDIN_ACCOUNT_TIER':'free','LINKEDIN_INVITE_NOTE_MONTHLY_LIMIT':'3',
            'OPERATOR_PROFILE_READ_DAILY_LIMIT':'80','OPERATOR_INVITE_RAMP_ENABLED':'true',
            'OPERATOR_INVITE_RAMP_STAGES':'5/20,10/50,20/100','OPERATOR_INVITE_RAMP_MIN_DAYS':'7',
            'OPERATOR_WEEKEND_FACTOR':'0.5','OPERATOR_EXTERNAL_OUTREACH_ACTIVE':'false',
            'OPERATOR_INVITE_SAMPLE_MIN':'20','OPERATOR_INVITE_MATURITY_DAYS':'7','OPERATOR_INVITE_COHORT_DAYS':'28'})
        env.start();self.addCleanup(env.stop)
        notice=patch('team_backend.notificaciones.avisar')
        self.notice=notice.start();self.addCleanup(notice.stop)

    def approved(self,person=None,note=False,cap='RED-02'):
        person=person or self.contact('person-'+str(Contact.objects.count()),'Person',stage='followed',followed_hours=72)
        payload={'user_id':person.provider_user_id}
        if note:payload.update(note='Your architecture discussion raised a useful tradeoff.',note_reason='Specific shared product work; high fit.',without_note_fallback=True)
        proposal=operador.create_proposal(self.gustavo,None,cap,payload,contact=person,citations=red.NETWORK_UNITS)
        proposal.state='approved';proposal.approved_hash=proposal.payload_hash
        proposal.review={'decision':'approve','note_approved':note};proposal.save()
        return proposal

    def ramp(self,stage=0,days=8,rate=None,sample=''):
        red._save_ramp({'stage':stage,'stage_since':(self.now-timedelta(days=days)).isoformat(),
            'freeze_until':(self.now-timedelta(days=days)).isoformat(),'pause_until':(self.now-timedelta(days=days)).isoformat(),
            'last_rate':rate,'last_sample':sample},'fixture',self.now-timedelta(days=days))

    def cohort(self,count=20,accepted=10,age=8,unknown=0):
        people=[]
        for i in range(count):
            c=self.contact('cohort-'+str(Contact.objects.count()),'Synthetic Person',stage='invited')
            at=self.now-timedelta(days=age)
            c.invited_at=at;c.profile_checked_at=None if i<unknown else self.now
            if unknown<=i<unknown+accepted:c.connected_at=self.now-timedelta(days=1);c.stage='connected'
            c.save();p=self.approved(c);p.state='confirmed';p.save()
            ActionExecution.objects.create(proposal=p,provider='fake',executed_by=self.gustavo,state='confirmed',wrote=True,started_at=at,
                idempotency_key=str(p.id))
            people.append(c)
        return people

    def test_defaults_weekends_and_invitation_hard_ceilings(self):
        self.assertEqual(operador.limits(self.now),{'INT-03':(5,25),'INT-04':(10,40),'INT-02':(20,100),'CONT-09':(1,7),
            'RED-01':(10,50),'RED-02':(20,100),'RED-04':(10,40)})
        saturday=self.now+timedelta(days=5)
        self.assertEqual(operador.limits(saturday)['INT-03'],(2,25))
        self.assertEqual(operador.limits(saturday)['CONT-09'],(1,7))
        self.assertEqual(operador.capacity_left(self.account,'RED-02',saturday),0)
        # Reading a future weekend's cap must not create an invitation pause today.
        self.assertIsNone(red.ramp_state(self.now)['pause_until'])
        self.assertEqual(red.invites_blocked(self.now),(False,''))
        with patch.dict(os.environ,{'OPERATOR_DAILY_LIMITS':'RED-02=21','OPERATOR_WEEKLY_LIMITS':'RED-02=101'}):
            self.assertEqual(operador.limits(self.now)['RED-02'],(20,100))
            self.assertEqual(operador.capacity_left(self.account,'RED-02',self.now),5)

    def test_approved_invitation_cannot_execute_at_weekend_or_for_blocked_recipient(self):
        p=self.approved()
        with patch('django.utils.timezone.now',return_value=self.now+timedelta(days=5)),self.assertRaises(operador.OperatorBlocked):
            operador.execute(self.gustavo,p.id)
        self.assertFalse(ActionExecution.objects.filter(proposal=p).exists())
        operador._audit(None,'network.recipient_blocked',p.payload['user_id'],status=422)
        with self.assertRaisesRegex(operador.OperatorBlocked,'Destinatario'):operador.execute(self.gustavo,p.id)
        self.assertFalse(ActionExecution.objects.filter(proposal=p).exists())
        self.assertEqual(self.fake.state['writes'],0)

    def test_window_is_bogota_and_end_exclusive(self):
        with patch.dict(os.environ,{'OPERATOR_WINDOW':'07:00-21:00','OPERATOR_TIMEZONE':'America/Bogota'}):
            self.assertFalse(operador.within_window(self.now.replace(hour=11,minute=59)))
            self.assertTrue(operador.within_window(self.now.replace(hour=12,minute=0)))
            self.assertFalse(operador.within_window(self.now.replace(hour=2,minute=0)))

    def test_gap_is_persistent_shared_and_not_redrawn_by_retry(self):
        self.spacing_patch.stop()
        with patch('team_backend.operador.random.SystemRandom') as rng:
            rng.return_value.randint.return_value=1801
            first=self.approved();operador.execute(self.gustavo,first.id)
            next_at=operador.policy_event('operator.schedule').metadata['next_action_at']
            second=self.approved()
            with self.assertRaises(operador.OperatorBlocked):operador.execute(self.gustavo,second.id)
            self.assertEqual(operador.policy_event('operator.schedule').metadata['next_action_at'],next_at)
            self.assertEqual(rng.return_value.randint.call_count,1)
            other=ConnectorAccount.objects.create(provider='linkedin_fake',external_account_id='other',label='Same member')
            self.assertFalse(operador.spacing_ok(other,self.now+timedelta(seconds=1800)))
            self.assertTrue(operador.spacing_ok(other,self.now+timedelta(seconds=1801)))

    def test_opening_time_varies_even_if_rng_repeats_and_preserves_pending_wait(self):
        self.day_schedule_patch.stop()
        with patch('team_backend.operador.random.SystemRandom') as rng:
            rng.return_value.randint.return_value=600
            operador.prepare_day_schedule(self.now)
            first=operador.policy_event('operator.day_schedule').metadata
            operador.prepare_day_schedule(self.now)
            self.assertEqual(rng.return_value.randint.call_count,1)
            operador.prepare_day_schedule(self.now+timedelta(days=1))
            self.assertNotEqual(first['delay'],operador.policy_event('operator.day_schedule').metadata['delay'])

    def test_health_excludes_immature_unknown_and_deduplicates_recipients(self):
        people=self.cohort();self.cohort(count=15,accepted=0,age=2);self.cohort(count=2,accepted=0,unknown=2)
        c=people[0];p=self.approved(c);p.state='confirmed';p.save()
        ActionExecution.objects.create(proposal=p,provider='fake',executed_by=self.gustavo,state='confirmed',started_at=self.now-timedelta(days=8),idempotency_key=str(p.id))
        health=red.invitation_health(self.now)
        self.assertEqual((health['rate'],health['mature'],health['immature'],health['unknown']),(0.5,20,15,2))

    def test_ramp_needs_time_and_mature_sample_and_survives_env_change(self):
        self.assertEqual(red.ramp_limits(self.account,self.now),(5,20))
        self.assertEqual(red.ramp_limits(self.account,self.now+timedelta(days=8)),(5,20))
        self.cohort();self.ramp(stage=0,days=8)
        self.assertEqual(red.ramp_limits(self.account,self.now),(10,50))
        with patch.dict(os.environ,{'OPERATOR_DAILY_LIMITS':'RED-02=100','OPERATOR_INVITE_RAMP_STAGES':'99/999,99/999,99/999'}):
            self.assertEqual(red.ramp_limits(self.account,self.now),(10,50))
        self.assertEqual(red.ramp_state(self.now)['stage'],1)

    def test_ten_point_drop_reduces_once_and_below_quarter_pauses(self):
        people=self.cohort(accepted=10);self.ramp(stage=2,rate=0.60)
        state=red.review_health(self.account,self.now)
        self.assertEqual(state['stage'],1)
        self.assertEqual(red.review_health(self.account,self.now+timedelta(days=1))['stage'],1)
        Contact.objects.filter(pk__in=[c.pk for c in people[4:10]]).update(connected_at=None,stage='invited')
        state=red.review_health(self.account,self.now+timedelta(days=2))
        self.account.refresh_from_db();self.assertTrue(self.account.paused)
        self.assertEqual(red.ramp_limits(self.account,self.now+timedelta(days=2)),(0,0))
        self.notice.assert_called()

    def test_422_blocks_recipient_and_second_distinct_recipient_pauses_account(self):
        self.ramp(stage=2)
        p=self.approved();error=ConnectorError('cannot resend',status=422,kind='provider/cannot_resend_yet')
        red.provider_failure(self.account,p,error,self.gustavo)
        self.assertTrue(red.recipient_blocked(p.payload['user_id']))
        self.assertEqual(red.ramp_state()['stage'],1)
        red.provider_failure(self.account,p,error,self.gustavo)
        self.account.refresh_from_db();self.assertFalse(self.account.paused)
        red.provider_failure(self.account,self.approved(),error,self.gustavo)
        self.account.refresh_from_db();self.assertTrue(self.account.paused);self.notice.assert_called()

    def test_other_422_never_implies_global_limit_and_429_does(self):
        p=self.approved()
        red.provider_failure(self.account,p,ConnectorError('invalid',status=422,kind='invalid'))
        self.account.refresh_from_db();self.assertFalse(self.account.paused)
        red.provider_failure(self.account,p,ConnectorError('throttle',status=429,kind='rate_limit',pause=True))
        self.account.refresh_from_db();self.assertTrue(self.account.paused);self.assertTrue(red.invites_blocked()[0])

    def test_real_pause_deadline_survives_health_reviews_and_expiry_requires_account_review(self):
        p=self.approved()
        red.provider_failure(self.account,p,ConnectorError('throttle',status=429,kind='rate_limit',pause=True))
        until=self.now+timedelta(days=7)
        self.assertEqual(red.ramp_state()['pause_until'],until.isoformat())
        for when in (self.now,until-timedelta(seconds=1)):
            self.assertEqual(red.ramp_limits(self.account,when),(0,0))
            self.assertTrue(red.invites_blocked(when)[0])
        self.assertEqual(red.ramp_limits(self.account,until),(5,20))
        self.assertEqual(red.invites_blocked(until),(False,''))
        with patch('django.utils.timezone.now',return_value=until),self.assertRaisesRegex(operador.OperatorBlocked,'Cuenta en pausa'):
            operador.execute(self.gustavo,p.id)
        self.assertFalse(ActionExecution.objects.filter(proposal=p).exists())
        self.assertEqual(self.fake.state['writes'],0)

    def test_profile_reads_share_atomic_ceiling_across_accounts_and_paths(self):
        other=ConnectorAccount.objects.create(provider='fake',external_account_id='acc_other',label='Other connector')
        AuditEvent.objects.bulk_create([AuditEvent(action='operator.profile_read',target='member',metadata={}) for _ in range(79)])
        def attempt(account):
            close_old_connections()
            try:
                operador.reserve_profile_read(account,'test');return True
            except operador.ProfileReadCapReached:return False
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(attempt,[self.account,other]))
        self.assertEqual(sorted(results),[False,True])
        p=self.approved()
        with self.assertRaisesRegex(operador.OperatorBlocked,'lecturas'):operador.execute(self.gustavo,p.id)
        self.assertFalse(ActionExecution.objects.filter(proposal=p).exists())
        with self.assertRaises(metricas.ReadCapReached):metricas._read(self.account,'profile')
        with patch.dict(os.environ,{'OPERATOR_PROFILE_READ_DAILY_LIMIT':'1000'}):
            for _ in range(20):operador.reserve_profile_read(self.account,'test')
            with self.assertRaises(operador.ProfileReadCapReached):operador.reserve_profile_read(self.account,'test')

    def test_deployment_preserves_legacy_profile_usage_without_double_charging_new_reads(self):
        AuditEvent.objects.bulk_create([AuditEvent(action='network.read',target=str(self.account.id),metadata={'kind':'profile'}) for _ in range(79)])
        red._read(self.account,'profile')
        with self.assertRaises(operador.ProfileReadCapReached):operador.reserve_profile_read(self.account,'preflight')
        self.assertEqual(AuditEvent.objects.filter(action='operator.profile_read').count(),1)
        self.assertEqual(operador.policy_event('operator.profile_baseline').metadata['used'],79)

    def test_no_note_by_default_and_fourth_reserved_note_uses_approved_alternative(self):
        p=self.approved();operador.execute(self.gustavo,p.id)
        self.assertEqual(next(iter(self.fake.state['invitations']['sent'].values()))['message'],'')
        for _ in range(4):operador.execute(self.gustavo,self.approved(note=True).id)
        messages=[v['message'] for v in self.fake.state['invitations']['sent'].values()]
        self.assertEqual(sum(bool(m) for m in messages),3)
        self.assertEqual(AuditEvent.objects.filter(action='network.note_omitted').count(),1)

    def test_concurrent_invitation_workers_share_one_remaining_slot(self):
        first,second=self.approved(),self.approved()
        def execute(pk):
            close_old_connections()
            try:return operador.execute(self.gustavo,pk).state
            except operador.OperatorBlocked:return 'blocked'
            finally:close_old_connections()
        with patch.dict(os.environ,{'OPERATOR_DAILY_LIMITS':'RED-02=1'}),ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(execute,[first.pk,second.pk]))
        self.assertEqual(sorted(results),['blocked','confirmed'])
        self.assertEqual(self.fake.state['writes'],1)

    def test_concurrent_note_reservations_never_exceed_the_monthly_cap(self):
        proposals=[self.approved(note=True) for _ in range(4)]
        def reserve(proposal):
            close_old_connections()
            try:return red.reserve_note(proposal)
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(reserve,proposals))
        self.assertEqual(sum(results),3)
        self.assertEqual(AuditEvent.objects.filter(action='network.note_reserved').count(),3)
        self.assertEqual(AuditEvent.objects.filter(action='network.account_tier').count(),1)

    def test_pause_arriving_during_profile_preflight_stops_the_write(self):
        p=self.approved();real=type(self.fake).get_profile
        def read(connector,uid):
            profile=real(connector,uid)
            ConnectorAccount.objects.filter(pk=self.account.pk).update(paused=True)
            return profile
        with patch.object(type(self.fake),'get_profile',read):result=operador.execute(self.gustavo,p.id)
        self.assertFalse(result.wrote);self.assertEqual(result.error_kind,'policy_changed')
        self.assertEqual(self.fake.state['writes'],0)

    def test_note_rejection_queues_one_linked_fallback_without_resending_now(self):
        p=self.approved(note=True)
        self.spacing_patch.stop()
        rng=patch('team_backend.operador.random.SystemRandom')
        rng.start().return_value.randint.return_value=1800;self.addCleanup(rng.stop)
        with patch.object(type(self.fake),'send_invitation',side_effect=InvitationNoteQuota('note limit',422)) as send:
            result=operador.execute(self.gustavo,p.id)
        self.assertFalse(result.wrote);self.assertEqual(result.error_kind,'note_quota');self.assertEqual(send.call_count,1)
        fallback=ActionProposal.objects.get(previous=p)
        self.assertEqual(fallback.payload,{'user_id':p.payload['user_id']});self.assertEqual(fallback.state,'approved')
        self.assertTrue(red.note_blocked());self.assertFalse(red.invites_blocked()[0])
        with self.assertRaises(operador.OperatorBlocked):operador.execute(self.gustavo,fallback.id)
        with patch('django.utils.timezone.now',return_value=self.now+timedelta(seconds=1801)):
            result=operador.execute(self.gustavo,fallback.id)
        self.assertEqual(result.state,'confirmed');self.assertEqual(self.fake.state['writes'],1)
        with patch('django.utils.timezone.now',return_value=self.now+timedelta(days=40)):
            self.assertTrue(red.note_blocked())

    def test_ambiguous_note_write_and_generic_limit_do_not_fallback(self):
        p=self.approved(note=True)
        with patch.object(type(self.fake),'send_invitation',side_effect=ConnectorUncertain('timeout')):
            result=operador.execute(self.gustavo,p.id)
        self.assertEqual(result.state,'uncertain');self.assertTrue(result.wrote)
        self.assertFalse(ActionProposal.objects.filter(previous=p).exists())
        self.assertEqual(red.note_room(),2)
        p2=self.approved(note=True)
        with patch.object(type(self.fake),'send_invitation',side_effect=ConnectorError('quota',status=429,kind='quota',pause=True)):
            operador.execute(self.gustavo,p2.id)
        self.assertFalse(ActionProposal.objects.filter(previous=p2).exists())
        self.account.refresh_from_db();self.assertTrue(self.account.paused)

    def test_readback_failure_keeps_written_invitation_reserved(self):
        p=self.approved()
        real=type(self.fake).get_profile
        count=0
        def read(connector,uid):
            nonlocal count
            count+=1
            # The fake send itself also checks the profile.
            if count>=3:raise ConnectorError('read unavailable',status=503,kind='network')
            return real(connector,uid)
        with patch.object(type(self.fake),'get_profile',read):result=operador.execute(self.gustavo,p.id)
        self.assertEqual(result.state,'sent');self.assertTrue(result.wrote)
        self.assertEqual(operador.capacity_left(self.account,'RED-02'),4)

    def test_tier_validates_and_upgrade_preserves_notes_and_ramp(self):
        self.assertEqual(red.note_policy()['tier'],'free');self.assertIsNone(red.note_policy()['provider_remaining'])
        p=self.approved(note=True)
        self.assertTrue(red.reserve_note(p));self.ramp(stage=0)
        event=operador.policy_event('network.account_tier')
        self.assertIsNone(event.actor_id)
        self.assertEqual(event.metadata,{'tier':'free','previous':None,'change_source':'server_configuration',
                                        'capability_source':'local_product_cap'})
        with patch.dict(os.environ,{'LINKEDIN_ACCOUNT_TIER':'premium'}):
            self.assertEqual(red.note_room(),2);self.assertEqual(red.note_policy()['max_chars'],200)
            self.assertEqual(red.ramp_limits(self.account,self.now),(5,20))
            # Reusing the reservation records the new tier, without consuming another note.
            self.assertTrue(red.reserve_note(p));self.assertTrue(red.reserve_note(p))
            self.assertEqual(red.note_room(),2)
            event=operador.policy_event('network.account_tier')
            self.assertIsNone(event.actor_id)
            self.assertEqual(event.metadata,{'tier':'premium','previous':'free','change_source':'server_configuration',
                                            'capability_source':'local_product_cap'})
        self.assertEqual(AuditEvent.objects.filter(action='network.account_tier').count(),2)
        self.assertEqual(AuditEvent.objects.filter(action='network.note_reserved').count(),1)
        with patch.dict(os.environ,{'LINKEDIN_ACCOUNT_TIER':'unknown'}),self.assertRaises(ValueError):red.note_policy()

    def test_explicit_note_quota_contract_only(self):
        connector=object.__new__(UnipileConnector)
        exact={'scope':'invitation_note','reason':'monthly_limit','invitation_created':False,'type':'fixture/note_limit'}
        self.assertIsInstance(connector._error(httpx.Response(422,json=exact)),InvitationNoteQuota)
        for body in ({'type':'quota'},dict(exact,invitation_created=True),dict(exact,type='cannot_resend_yet')):
            self.assertNotIsInstance(connector._error(httpx.Response(422,json=body)),InvitationNoteQuota)
        self.assertNotIsInstance(connector._error(httpx.Response(429,json=exact)),InvitationNoteQuota)

    def test_table_does_not_turn_leaders_and_unknown_allies_into_invites(self):
        buyer=self.contact('buyer','Buyer',stage='followed',followed_hours=72)
        leader=self.contact('leader','Leader',stage='followed',followed_hours=72)
        other=self.contact('recommender','Recommender',stage='followed',followed_hours=72)
        leader.classification.update(role='lider');leader.save()
        other.classification.update(role='recomendador',confidence=0.95);other.save()
        self.assertEqual([c.pk for c in red.diverse_candidates([leader,other,buyer])],[buyer.pk,other.pk])
        plan=red.plan(self.gustavo,self.account,self.now)
        self.assertEqual([r['profiles'] for r in plan['distribution']],[20,15,20,10,25])
        self.assertFalse(ActionProposal.objects.filter(contact=leader,capability='RED-02').exists())
        self.assertEqual(plan['invite'],2)
        self.assertEqual(sum(plan['rhythm']['confirmed_social'].values()),0)

    def test_plan_reserves_notes_for_highest_fit_even_when_buyer_is_first(self):
        buyer=self.contact('buyer-note','Buyer',stage='followed',followed_hours=72)
        recommender=self.contact('high-fit','Recommender',stage='followed',followed_hours=72)
        for c,role,confidence in ((buyer,'comprador',0.91),(recommender,'recomendador',0.99)):
            c.classification.update(role=role,confidence=confidence,course_citations=['LI-03-M006-K01'],
                invitation_note='Your product architecture discussion raised a useful tradeoff.',note_reason='Specific public product work and strong shared context.')
            c.save()
        with patch.dict(os.environ,{'LINKEDIN_INVITE_NOTE_MONTHLY_LIMIT':'1'}):red.plan(self.gustavo,self.account,self.now)
        self.assertNotIn('note',ActionProposal.objects.get(contact=buyer).payload)
        self.assertIn('note',ActionProposal.objects.get(contact=recommender).payload)

    def test_weekly_goal_never_counts_drafts_failed_or_technical_reads(self):
        p=self.approved();operador.execute(self.gustavo,p.id)
        self.approved()
        operador._audit(None,'network.research_result',self.account.id,kind='profile',key='one',result_count=1)
        operador._audit(None,'network.research_result',self.account.id,kind='profile',key='one',result_count=1)
        operador._audit(None,'network.read',self.account.id,kind='execution')
        report=red.weekly_rhythm(self.now+timedelta(seconds=1))
        self.assertEqual(report['useful_total'],2);self.assertEqual(report['research_results'],1)
        self.assertEqual(report['deficit'],48)


class CourseGroundingTests(NetworkBase):
    def test_network_plan_continues_with_complete_units_above_the_old_budget(self):
        self.contact('follow-budget','Follow Budget')
        self.contact('invite-budget','Invite Budget',stage='followed',followed_hours=72)
        incoming=self.contact('accept-budget','Accept Budget',stage='incoming')
        incoming.invitation_id='inv-budget';incoming.save(update_fields=['invitation_id'])
        with patch('team_backend.operador.ENC.encode',return_value=range(3000)):
            result=red.plan(self.gustavo,self.account)
        self.assertNotIn('stopped',result)
        self.assertEqual((result['follow'],result['invite'],result['accept']),(1,1,1))
        self.assertEqual(result['course_status'],'disponible')
        self.assertEqual((result['course_missing'],result['course_omitted']),([],[]))
        self.assertEqual(result['course_citations'],red.NETWORK_UNITS)
        self.assertEqual(self.fake.state['writes'],0)

    def test_network_plan_stops_for_a_real_missing_unit_and_distinguishes_a_paused_account(self):
        unit=red.NETWORK_UNITS[-1]
        from knowledge import db
        with db.connect() as connection:connection.execute('UPDATE units SET active=false WHERE id=%s',(unit,))
        result=red.plan(self.gustavo,self.account)
        self.assertEqual(result['stopped'],'Biblioteca no disponible')
        self.assertEqual(result['course_missing'],[unit])
        self.assertNotIn(unit,result['course_citations'])
        self.assertFalse(ActionProposal.objects.exists())
        with db.connect() as connection:connection.execute('UPDATE units SET active=true WHERE id=%s',(unit,))
        self.account.paused=True;self.account.save(update_fields=['paused'])
        result=red.plan(self.gustavo,self.account)
        self.assertEqual(result['stopped'],'Cuenta pausada')
        self.assertEqual(result['course_status'],'disponible')

    def test_observatory_returns_sources_and_evidence_without_changing_referents(self):
        from team_backend.models import Referent
        self.observed();before=list(Referent.objects.values_list('pk','active'))
        result=operador.observe(self.gustavo,self.account)
        _,grounding=evaluaciones.course_case_context('investigador')
        self.assertTrue(evaluaciones.grade_course_case('investigador',result,grounding)['passed'])
        self.assertIn('LI-03-V009-K04',result['course_context']);self.assertTrue(result['evidence'])
        self.assertEqual(list(Referent.objects.values_list('pk','active')),before)

    def test_every_role_loads_whole_versioned_sources_and_rejects_wrong_behaviour(self):
        for role,case in evaluaciones.COURSE_CASES.items():
            context,grounding=evaluaciones.course_case_context(role)
            self.assertIn('limits_errors',context);self.assertEqual(grounding['course_missing'],[])
            result=dict(case['expected'],course_citations=case['required'])
            self.assertTrue(evaluaciones.grade_course_case(role,result,grounding)['passed'])
            key=next(iter(case['expected']));result[key]='wrong'
            self.assertFalse(evaluaciones.grade_course_case(role,result,grounding)['passed'])
            result=dict(case['expected'],course_citations=['LI-07-V001-K01'])
            self.assertFalse(evaluaciones.grade_course_case(role,result,grounding)['passed'])

    def test_missing_units_do_not_produce_citations_or_paid_judgment(self):
        with patch('knowledge.retrieval.unit',side_effect=ValueError('absent')),patch('knowledge.providers.typesafe') as jev:
            post=self.observed()[0]
            result=lider.comment_worthy(post)
        self.assertEqual(result['decision'],'unavailable');self.assertEqual(result['course_citations'],[]);jev.assert_not_called()

    def test_a_single_missing_comment_unit_blocks_before_the_paid_draft(self):
        from knowledge import db
        post=self.observed()[0]
        unit=operador.COMMENT_UNITS[-1]
        with db.connect() as connection:connection.execute('UPDATE units SET active=false WHERE id=%s',(unit,))
        with patch('knowledge.providers.claude') as draft,self.assertRaisesRegex(ValueError,'Biblioteca no disponible'):
            operador.propose_comment(self.gustavo,post.pk)
        draft.assert_not_called()

    def test_inbox_and_lead_criteria_are_grounded_in_the_actual_typed_request(self):
        conversation=Conversation(account=self.account,provider_chat_id='fake',attendee_name='Synthetic',messages=[
            {'id':'m','from_me':False,'text':'Thanks for connecting','at':timezone.now().isoformat()}])
        state,questions=conversaciones._questions(conversation)
        self.assertIn('LI-03-V020-K01',questions['oportunidad']['instructions'])
        self.assertIn('saludo',questions['oportunidad']['criteria']['false'])
        self.assertEqual(state['course_grounding']['criterion_sources']['oportunidad'],
            ['LI-03-V019-K04','LI-03-V020-K01','LI-06-V006-K04'])
        post=self.observed()[0]
        state,questions,checks=lider._questions(ActionProposal(capability='INT-03',post=post,payload={'text':'Great post! Buy now.'}),'')
        self.assertIn('LI-03-M006-K01',questions['pitch']['instructions'])
        self.assertIn('inglés',questions['idioma']['instructions'])
        self.assertIn('español cuando la `publicacion` está en español',questions['idioma']['instructions'])  # Gustavo, 2026-11-12
        self.assertIn(('pitch','max',0.2,'suena a venta o pide contacto'),checks)

    def test_classifier_puts_course_in_stable_context_and_validates_citations(self):
        person=self.fake.seed_person('peer','Relevant Peer',headline='Product engineer')
        Contact.objects.create(account=self.account,provider_user_id=person['id'],display_name='Relevant Peer',headline='Product engineer',source='search')
        requests=[]
        def classify(system,message,**kwargs):
            requests.append(kwargs)
            return {'text':json.dumps({'contacts':[{'id':json.loads(message)['people'][0]['id'],'fit':True,'role':'par',
                'modality':'comunidad_autoridad','affinity':'desconocida','reason':'Specific product architecture discussion',
                'confidence':0.9,'course_citations':['LI-03-M005-K06','LI-03-V018-K03'],'invitation_note':'','note_reason':''}]}),'model':'fake'}
        with patch('knowledge.providers.claude',side_effect=classify):result=red.classify(self.gustavo,self.account)
        contact=Contact.objects.get()
        self.assertEqual(result['classified'],1)
        self.assertIn('LI-03-M005-K06',requests[0]['context'])
        self.assertEqual(contact.classification['course_version'],operador.COURSE_VERSION)
        self.assertTrue(evaluaciones.grade_course_case('clasificador',contact.classification,contact.classification)['passed'])

    def test_inbox_case_runs_real_assess_with_a_fake_jev_and_sends_nothing(self):
        outcomes=[];case=evaluaciones.COURSE_CASES['inbox']
        def jev(state,questions,**kwargs):
            need='architecture' in state['conversacion'][-1]['texto']
            scores={'oportunidad':0.9 if need else 0.05,'espera':0.9 if need else 0.1,'venta':0.05,'startups':0.9,'projectapp':0.1}
            return {'answers':{k:{'noul':scores[k]} for k in questions},'model':'fake','estimated_usd':0}
        for label in ('greeting','need'):
            c=Conversation.objects.create(account=self.account,provider_chat_id=label,messages=[
                {'id':label,'from_me':False,'text':case['input'][label],'at':timezone.now().isoformat()}])
            with patch('knowledge.providers.typesafe',side_effect=jev):self.assertTrue(conversaciones.assess(c))
            outcomes.append(c.assessment['opportunity'])
        result=dict(c.assessment,greeting_opportunity=outcomes[0],need_opportunity=outcomes[1],messages_sent=self.fake.state['writes'])
        self.assertTrue(evaluaciones.grade_course_case('inbox',result,c.assessment)['passed'])

    def test_lead_case_applies_real_thresholds_to_fake_typed_judgments(self):
        post=self.observed()[0];case=evaluaciones.COURSE_CASES['lider'];outcomes=[]
        def jev(state,questions,**kwargs):
            pitch='Buy our service' in state['comentario']
            scores={'aporta':0.05 if pitch else 0.9,'pitch':0.95 if pitch else 0.05,'inventa':0.05,'respeto':0.95,'idioma':0.95}
            return {'answers':{k:{'noul':scores.get(k,0.9)} for k in questions},'model':'fake','estimated_usd':0}
        for text in (case['input']['good'],case['input']['bad']):
            p=ActionProposal(capability='INT-03',post=post,payload={'text':text})
            with patch('knowledge.providers.typesafe',side_effect=jev):result=lider.review(p)
            outcomes.append(result['decision'])
        result.update(grounded_decision=outcomes[0],pitch_decision=outcomes[1])
        self.assertTrue(evaluaciones.grade_course_case('lider',result,result)['passed'])

    def test_weekly_citations_stay_out_of_numeric_evidence_and_unknown_citations_fail(self):
        _,grounding=operador.role_context('semanal',resumen_semanal.WEEKLY_UNITS)
        data={'value':3}
        raw={'titular':'3 posts','lo_que_funciono':[],'lo_que_no':[],
             'recomendaciones':[{'texto':'Escuchar tras 3 posts','cifra':'3','course_citations':['LI-06-V008-K02']}],
             'orientacion_propuesta':'','advertencias':[]}
        result=resumen_semanal.validate(raw,data,timezone.now().date(),grounding)
        self.assertTrue(result['validacion']['ok'])
        raw['recomendaciones'][0]['course_citations']=['LI-07-V001-K01']
        with self.assertRaises(ValueError):resumen_semanal.validate(raw,data,timezone.now().date(),grounding)
        self.assertIs(resumen_semanal.WEEKLY_UNITS,metricas.ANALYSIS_UNITS)
