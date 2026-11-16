"""Desenlaces: what came after an own comment (INT-03, 72 h) or a network action (RED-01/02/04, 7 d). Readers over DB rows,
the windows of what is due, the autopilot queueing collect_outcomes, and the gap an execution that wrote nothing gives
back. Fixed clocks for every window; invented people and posts; never live services."""
import os
import uuid
from datetime import datetime, timedelta, timezone as dt_timezone
from unittest.mock import patch
from django.db import IntegrityError, transaction
from team_backend import autopiloto, desenlaces, operador
from team_backend.models import ActionExecution, ActionOutcome, ActionProposal, ConnectorAccount, Contact, Job, ObservedPost
from team_backend.tests.test_operador import OperatorBase

NOW=datetime(2026,11,9,15,tzinfo=dt_timezone.utc)  # Monday, 10:00 Bogota; 15:00 UTC also starts a 3 h bucket
TEXT='Evals catch the failures that demos hide; which one do you test first?'

class OutcomeBase(OperatorBase):
    def setUp(self):
        super().setUp()
        env=patch.dict(os.environ,{'OUTCOMES_ENABLED':'true','OUTCOMES_EVERY_MINUTES':'180'})
        env.start();self.addCleanup(env.stop)
        self.posts=0;self.people=0

    def post(self,author):
        self.posts+=1
        return ObservedPost.objects.create(account=self.account,provider_post_id=f'urn:li:activity:{self.posts}',
                                           author_provider_id=author,author_name='Autora Inventada')

    def contact(self):
        self.people+=1
        return Contact.objects.create(account=self.account,provider_user_id=f'ACoperson-{self.people}',display_name=f'Persona {self.people}',
                                      source='commenter',stage='followed')

    def executed(self,capability='INT-03',age=timedelta(hours=80),state='confirmed',wrote=True,author='ACoAuthor-a',contact=None):
        """An executed action started `age` before NOW: INT-* on a post by `author`, RED-* on a person."""
        if capability.startswith('INT'):target,payload={'post':self.post(author)},{'text':TEXT}
        else:
            contact=contact or self.contact();target,payload={'contact':contact},{'user_id':contact.provider_user_id}
        proposal=ActionProposal.objects.create(account=self.account,capability=capability,payload=payload,payload_hash='0'*64,state=state,**target)
        return ActionExecution.objects.create(proposal=proposal,provider='fake',executed_by=self.gustavo,state=state,wrote=wrote,
                                              idempotency_key=uuid.uuid4().hex,started_at=NOW-age)

    def outcome(self,execution,kind='72h',captured=None,source='read',**fields):
        """Captured at its age (72 h or 7 d after the execution) unless `captured` says otherwise."""
        captured=captured or execution.started_at+(timedelta(hours=72) if kind=='72h' else timedelta(days=7))
        return ActionOutcome.objects.create(execution=execution,kind=kind,source=source,captured_at=captured,**fields)


class DueTests(OutcomeBase):
    def test_each_execution_is_due_inside_its_window_until_it_has_its_outcome(self):
        self.executed(age=timedelta(hours=71))  # too recent
        boundary=self.executed(age=timedelta(hours=72))
        comment=self.executed(age=timedelta(hours=80))
        measured=self.executed(age=timedelta(hours=90));self.outcome(measured,'72h')
        self.executed(age=timedelta(days=11))  # too old: the moment is gone
        self.executed(age=timedelta(hours=80),state='failed',wrote=False)  # LinkedIn never saw it
        self.executed(age=timedelta(hours=80),wrote=False)  # an identical own comment was already there
        sent=self.executed(age=timedelta(days=9),state='sent')
        self.executed('INT-02',age=timedelta(hours=80))  # reactions are not measured
        follow=self.executed('RED-01',age=timedelta(days=8))
        self.executed('RED-02',age=timedelta(days=6))  # its 7 d have not passed
        accept=self.executed('RED-04',age=timedelta(days=20))
        self.executed('RED-04',age=timedelta(days=22))  # too old
        self.executed('RED-02',age=timedelta(days=8),state='failed',wrote=False)
        followed=self.executed('RED-01',age=timedelta(days=10));self.outcome(followed,'7d',source='derived')
        early=self.executed('RED-01',age=timedelta(days=9,hours=12));self.outcome(early,'72h',source='derived')  # only the 7 d one counts
        self.assertEqual(list(desenlaces.due(NOW)),[accept,early,sent,follow,comment,boundary])  # oldest first
        self.outcome(comment,'72h')
        self.assertNotIn(comment,list(desenlaces.due(NOW)))
        self.assertEqual(list(desenlaces.due(NOW-timedelta(days=30))),[])

    def test_an_age_is_captured_once_and_read_back_as_stored(self):
        execution=self.executed(age=timedelta(days=9))
        self.outcome(execution,'72h',reactions=2,replies=1,author_replied=True,repliers=['replier-inventado'],provider_comment_id='comment:1')
        self.outcome(execution,'7d',reactions=3,replies=1)
        self.assertEqual(desenlaces.for_execution(execution),[
            {'kind':'72h','source':'read','reactions':2,'replies':1,'author_replied':True,'signals':{},
             'captured_at':(NOW-timedelta(days=6)).isoformat()},
            {'kind':'7d','source':'read','reactions':3,'replies':1,'author_replied':None,'signals':{},
             'captured_at':(NOW-timedelta(days=2)).isoformat()}])
        with self.assertRaises(IntegrityError),transaction.atomic():self.outcome(execution,'72h')
        self.assertEqual(execution.outcomes.count(),2)


class ReaderTests(OutcomeBase):
    def test_comment_history_is_per_author_newest_first_and_only_what_was_known(self):
        first=self.executed(age=timedelta(days=9))
        self.outcome(first,'72h',replies=0,reactions=1,author_replied=False)
        self.outcome(first,'7d',replies=2,reactions=3,author_replied=True)  # its latest age wins
        second=self.executed(age=timedelta(days=5));self.outcome(second,'72h',replies=1,reactions=0)
        other=self.executed(age=timedelta(days=4),author='ACoAuthor-b');self.outcome(other,'72h',replies=5)
        later=self.executed(age=timedelta(days=4));self.outcome(later,'72h',captured=NOW+timedelta(hours=1),replies=9)
        reaction=self.executed('INT-02',age=timedelta(days=4));self.outcome(reaction,'72h',reactions=7)  # not a comment
        self.assertEqual(desenlaces.comment_history('ACoAuthor-a',now=NOW),[
            {'commented_at':(NOW-timedelta(days=5)).isoformat(),'replies':1,'reactions':0,'author_replied':None,'kind':'72h'},
            {'commented_at':(NOW-timedelta(days=9)).isoformat(),'replies':2,'reactions':3,'author_replied':True,'kind':'7d'}])
        self.assertEqual([h['commented_at'] for h in desenlaces.comment_history('ACoAuthor-a',limit=1,now=NOW)],[(NOW-timedelta(days=5)).isoformat()])
        self.assertEqual(desenlaces.comment_history('ACoAuthor-b',now=NOW)[0]['replies'],5)
        self.assertEqual(desenlaces.comment_history('ACoAuthor-nadie',now=NOW),[])
        self.assertEqual(desenlaces.comment_history('',now=NOW),[])

    def test_comment_rates_count_each_comment_once_by_its_latest_outcome(self):
        replied=self.executed(age=timedelta(days=9))
        self.outcome(replied,'72h',replies=0);self.outcome(replied,'7d',replies=3,author_replied=True)
        unread=self.executed(age=timedelta(days=5));self.outcome(unread,'72h')  # replies null: not read, not a reply
        answered=self.executed(age=timedelta(days=4));self.outcome(answered,'72h',replies=1,author_replied=False)
        old=self.executed(age=timedelta(days=60));self.outcome(old,'72h',replies=4)  # outside the window
        follow=self.executed('RED-01',age=timedelta(days=8));self.outcome(follow,'7d',source='derived',replies=2)  # not a comment
        self.assertEqual(desenlaces.comment_rates(30,NOW),{'measured':3,'with_reply':2,'author_replied':1})
        # Three days earlier only the first comment's 72 h outcome existed.
        self.assertEqual(desenlaces.comment_rates(30,NOW-timedelta(days=3)),{'measured':1,'with_reply':0,'author_replied':0})

    def test_network_engaged_reads_follows_with_a_true_signal(self):
        warm,cold,invited=self.contact(),self.contact(),self.contact()
        quiet={'accepted':False,'commented_own_post':False,'replied_to_comment':False,'invited_us':False}
        self.outcome(self.executed('RED-01',age=timedelta(days=8),contact=warm),'7d',source='derived',
                     signals=dict(quiet,commented_own_post=True,invited_us=True))
        self.outcome(self.executed('RED-01',age=timedelta(days=8),contact=cold),'7d',source='derived',signals=quiet)
        self.outcome(self.executed('RED-02',age=timedelta(days=8),contact=invited),'7d',source='derived',signals=dict(quiet,accepted=True))
        self.assertEqual(desenlaces.network_engaged(now=NOW),{warm.id:['commented_own_post','invited_us']})
        self.assertEqual(desenlaces.network_engaged([str(warm.id),str(cold.id)],now=NOW),{warm.id:['commented_own_post','invited_us']})
        self.assertEqual(desenlaces.network_engaged([cold.id],now=NOW),{})
        self.assertEqual(desenlaces.network_engaged(now=NOW-timedelta(days=2)),{})  # not captured yet
        self.assertEqual(desenlaces.network_engaged(days=30,now=NOW+timedelta(days=31)),{})  # captured too long ago


class SchedulerTests(OutcomeBase):
    def test_queued_one_at_a_time_only_when_something_is_due(self):
        self.assertEqual(autopiloto._outcomes(self.gustavo,self.account,NOW),0)  # nothing due
        self.assertFalse(Job.objects.filter(kind='collect_outcomes').exists())
        self.executed(age=timedelta(hours=80))
        self.assertEqual(autopiloto._outcomes(self.gustavo,self.account,NOW),1)
        job=Job.objects.get(kind='collect_outcomes')
        self.assertEqual((job.params,job.execute,job.state),({'account':str(self.account.id)},False,'queued'))  # never a paid job
        self.assertEqual(autopiloto._outcomes(self.gustavo,self.account,NOW),0)  # one at a time
        Job.objects.filter(pk=job.pk).update(state=Job.State.COMPLETE)
        self.assertEqual(autopiloto._outcomes(self.gustavo,self.account,NOW+timedelta(minutes=5)),0)  # same bucket: its id was used
        self.assertEqual(autopiloto._outcomes(self.gustavo,self.account,NOW+timedelta(minutes=181)),1)
        self.assertEqual(Job.objects.filter(kind='collect_outcomes').count(),2)

    def test_switched_off_or_without_an_account_that_reads_nothing_is_queued(self):
        self.executed(age=timedelta(hours=80))
        with patch.dict(os.environ,{'OUTCOMES_ENABLED':'false'}):
            self.assertEqual(autopiloto._outcomes(self.gustavo,self.account,NOW),0)
        with patch.dict(os.environ,{'OUTCOMES_EVERY_MINUTES':'0'}):
            self.assertEqual(autopiloto._outcomes(self.gustavo,self.account,NOW),0)
        official=operador.register_account(self.gustavo,'linkedin','urn:li:person:inventado','LinkedIn oficial')
        self.assertEqual(autopiloto._outcomes(self.gustavo,official,NOW),0)
        self.assertFalse(Job.objects.filter(kind='collect_outcomes').exists())

    def test_the_tick_reports_it_and_a_failure_never_breaks_the_rest(self):
        self.assertEqual(autopiloto.tick(self.gustavo)['outcomes'],0)
        with patch('team_backend.desenlaces.due',side_effect=RuntimeError('boom')):report=autopiloto.tick(self.gustavo)
        self.assertEqual(report['outcomes_error'],'RuntimeError')
        self.assertIn('execute',report);self.assertIn('reconcile',report)


class SpacingReleaseTests(OperatorBase):
    """An execution whose pre-check found nothing to write does not delay the next write (operador.spacing_ok)."""
    def setUp(self):
        super().setUp()
        self.spacing_patch.stop()  # the real, persisted reservation

    def approved(self,post):
        proposal=operador.create_proposal(self.gustavo,post,'INT-03',{'text':TEXT})
        proposal.state='approved';proposal.approved_hash=proposal.payload_hash;proposal.save()
        return proposal

    def test_a_failed_pre_check_gives_its_gap_back_and_a_write_keeps_it(self):
        first,second=self.observed()
        self.fake.state['status']='disconnected'
        execution=operador.execute(self.gustavo,self.approved(first).id)
        self.assertEqual((execution.state,execution.error_kind,execution.wrote),('failed','account_not_running',False))
        self.assertEqual(operador.policy_event('operator.schedule').metadata['released_for'],str(execution.id))
        self.assertTrue(operador.spacing_ok(self.account,capability='INT-03'))
        self.fake.state['status']='running'
        ConnectorAccount.objects.filter(pk=self.account.pk).update(paused=False,paused_reason='')  # the stop paused it
        written=operador.execute(self.gustavo,self.approved(second).id)
        self.assertEqual((written.state,written.wrote),('confirmed',True))
        self.assertNotIn('released_for',operador.policy_event('operator.schedule').metadata)
        self.assertFalse(operador.spacing_ok(self.account,capability='INT-03'))
        self.assertEqual(self.fake.state['writes'],1)
