"""Desenlaces, the collector (desenlaces_captura.py, job collect_outcomes): an own comment's 72 h outcome read through the
directo connector's real parser from hand-written LinkedIn answers (directo_fixtures.py), its daily read caps, what
stops the reads and what skips one, and the network's 7 d outcome derived from Barrio's own rows. Fixed clocks;
invented people, posts and texts; never a live service."""
import os
import uuid
from datetime import date, timedelta
from unittest.mock import patch
from django.contrib.auth.models import User
from django.utils import timezone
from linkedin_directo import Answer, LinkedInError
from team_backend import connectors_directo, desenlaces, desenlaces_captura, jobs
from team_backend.models import (ActionExecution, ActionOutcome, ActionProposal, AuditEvent, ConnectorAccount, Contact, Conversation,
                                 EditorialPiece, Job, ObservedPost, PostComment)
from team_backend.tests import directo_fixtures as F
from team_backend.tests.test_operador import OperatorBase

WRITTEN=F.POSTED+timedelta(hours=2)  # when the team's comment went out (F.COMMENT_B's time)
NOW=WRITTEN+timedelta(hours=80)  # its 72 h outcome is due; 20:00 in Bogota
MINE='Los evals encuentran los fallos que las demos esconden. ¿Cuál pruebas primero?'
NO_SIGNAL=dict.fromkeys(('accepted','commented_own_post','replied_to_comment','invited_us','conversation'),False)
ME=('GET',r'^/voyager/api/me$',F.ok(F.me()))

def comments_of(post,answer):
    return ('GET',r'^/voyager/api/feed/comments\?q=comments&updateId=activity%3A'+post+'&',answer)

def thread_of(post,cid,answer):
    return ('GET',r'^/voyager/api/feed/comments\?q=comments&updateId=comment%3A%28activity%3A'+post+'%2C'+cid+'%29&',answer)

def top(post,own=MINE,replies=2):
    """A post's top-level comments: Luis's and, unless `own` is None, the account's (F.COMMENT_B) with `replies`
    answers. Each carries one reaction (F.comments)."""
    rows=[(F.comment(post,F.COMMENT_A,'Muy buen punto sobre los evals.',F.LUIS,F.POSTED+timedelta(hours=1)),0)]
    if own is not None:rows.append((F.comment(post,F.COMMENT_B,own,F.OWN,WRITTEN),replies))
    return F.ok(F.comments(post,rows))

def answers(post):
    """The thread of the account's comment: the post's author (Ana) answered and the account thanked her. Luis is among
    the answer's profiles but wrote nothing in it."""
    rows=[(F.comment(post,F.REPLY,'Justo eso nos pasó en el piloto.',F.ANA,WRITTEN+timedelta(hours=3),parent=F.COMMENT_B),0),
          (F.comment(post,F.snowflake(WRITTEN+timedelta(hours=4),6),'¡Gracias, Ana!',F.OWN,WRITTEN+timedelta(hours=4),parent=F.COMMENT_B),0)]
    return F.ok(F.comments(post,rows))


class OutcomeCaptureBase(OperatorBase):
    def setUp(self):
        super().setUp()
        env=patch.dict(os.environ,{'OPERATOR_TIMEZONE':'America/Bogota','OUTCOMES_READ_CAPS':''})
        env.start();self.addCleanup(env.stop)
        self.bot,_=User.objects.get_or_create(username='barrio-autopiloto')
        self.grant(self.bot,'operate_linkedin')
        self.directo=ConnectorAccount.objects.create(provider='directo',external_account_id='cuenta-prueba',label='Cuenta directa de prueba')
        self.people=0

    def executed(self,capability,at,payload,external_id='',**target):
        proposal=ActionProposal.objects.create(account=self.directo,capability=capability,payload=payload,payload_hash='0'*64,
                                               state='confirmed',**target)
        return ActionExecution.objects.create(proposal=proposal,idempotency_key=uuid.uuid4().hex,provider='directo',state='confirmed',
                                              executed_by=self.gustavo,started_at=at,external_id=external_id)

    def commented(self,post,at=WRITTEN,external_id='',text=MINE):
        """A confirmed INT-03: the team commented `text` at `at` on Ana's post `post` (an activity id)."""
        observed=ObservedPost.objects.create(account=self.directo,provider_post_id=post,author_provider_id=F.ANA[0],author_name='Ana Ficticia')
        return self.executed('INT-03',at,{'text':text},external_id,post=observed)

    def person(self,stage='followed',**fields):
        self.people+=1
        return Contact.objects.create(account=self.directo,provider_user_id=f'ACoPersonaFicticia{self.people:04d}',
                                      display_name=f'Persona Ficticia {self.people}',source='commenter',stage=stage,**fields)

    def networked(self,capability,contact,at):
        return self.executed(capability,at,{'user_id':contact.provider_user_id},contact=contact)

    def collect_at(self,*routes,now=NOW,**env):
        transport=F.FakeTransport(ME,*routes)
        with patch.object(connectors_directo,'TRANSPORT',transport),patch.dict(os.environ,env):
            return desenlaces_captura.collect(self.bot,self.directo,now=now),transport


class CommentOutcomeTests(OutcomeCaptureBase):
    def test_an_own_comment_found_by_its_text_gives_reactions_answers_and_the_authors_reply(self):
        execution=self.commented(F.POST)  # the write did not name the new comment: no external_id
        shown=MINE.replace('. ','.\n\n').upper()  # LinkedIn shows the same words with other spacing and case
        summary,t=self.collect_at(comments_of(F.POST,top(F.POST,own=shown)),thread_of(F.POST,F.COMMENT_B,answers(F.POST)))
        outcome=ActionOutcome.objects.get(execution=execution)
        self.assertEqual((outcome.kind,outcome.source,outcome.provider_comment_id,outcome.reactions,outcome.replies,outcome.author_replied,
                          outcome.repliers,outcome.signals,outcome.captured_at),('72h','read',F.COMMENT_B,1,2,True,[F.ANA[0]],{},NOW))
        # Only who answered is kept: not the account's own thanks, not Luis, whom the answer names without his writing.
        self.assertNotIn(F.LUIS[0],outcome.repliers);self.assertNotIn(F.OWN[0],outcome.repliers)
        self.assertEqual(t.paths(),['/voyager/api/me',
            f'/voyager/api/feed/comments?q=comments&updateId=activity%3A{F.POST}&count=50&start=0&sortOrder=RELEVANCE',
            f'/voyager/api/feed/comments?q=comments&updateId=comment%3A%28activity%3A{F.POST}%2C{F.COMMENT_B}%29&count=50&start=0&sortOrder=CHRONOLOGICAL'])
        self.assertEqual([desenlaces_captura.reads_today(self.directo,kind,NOW) for kind in ('comments','threads')],[1,1])
        self.assertEqual((summary['captured'],summary['pending'],summary['stopped'],summary['by_kind']['INT-03']),(1,0,'',{'captured':1,'pending':0}))
        audit=AuditEvent.objects.get(action='outcomes.collected').metadata
        self.assertEqual((audit['captured'],audit['by_kind']['INT-03'],audit['reasons']),
                         (1,{'captured':1,'pending':0},{'sin_comentario':0,'tope_de_lecturas':0,'error_de_lectura':0}))
        self.assertEqual(desenlaces.comment_history(F.ANA[0],now=NOW)[0]['author_replied'],True)  # what the readers see

    def test_a_comment_edited_on_linkedin_is_found_by_its_id_and_without_answers_no_thread_is_read(self):
        execution=self.commented(F.POST,external_id=F.COMMENT_B)
        summary,t=self.collect_at(comments_of(F.POST,top(F.POST,own='Texto editado después en LinkedIn.',replies=0)))
        outcome=ActionOutcome.objects.get(execution=execution)
        self.assertEqual((outcome.provider_comment_id,outcome.reactions,outcome.replies,outcome.author_replied,outcome.repliers),
                         (F.COMMENT_B,1,0,False,[]))
        self.assertEqual((len(t.sent),desenlaces_captura.reads_today(self.directo,'threads',NOW)),(2,0))  # /me and the comments

    def test_an_own_comment_not_on_the_page_stays_pending_and_writes_nothing(self):
        execution=self.commented(F.POST)
        # The page has an own comment with another text and no id to match: not that one (it may be beyond the page).
        summary,_=self.collect_at(comments_of(F.POST,top(F.POST,own='Otro comentario propio en ese post.')))
        self.assertFalse(ActionOutcome.objects.exists())  # never a zero outcome
        self.assertEqual((summary['captured'],summary['pending'],summary['reasons']['sin_comentario'],summary['stopped']),(0,1,1,''))
        self.assertIn(execution,list(desenlaces.due(NOW)))  # the next run looks again

    def test_the_daily_caps_stop_the_reads_and_the_next_day_continues_where_they_stopped(self):
        first=self.commented(F.POST);second=self.commented(F.OTHER_POST,at=WRITTEN+timedelta(hours=1))
        routes=(comments_of(F.POST,top(F.POST)),comments_of(F.OTHER_POST,top(F.OTHER_POST,replies=0)))
        caps={'OUTCOMES_READ_CAPS':'comments=1,threads=0'}
        summary,t=self.collect_at(*routes,**caps)
        # The threads cap: the oldest is written all the same, without who answered.
        outcome=ActionOutcome.objects.get()
        self.assertEqual((outcome.execution_id,outcome.replies,outcome.reactions,outcome.author_replied,outcome.repliers),(first.id,2,1,None,[]))
        self.assertIn('«threads»',summary['threads_error'])
        # The comments cap: the other one is not read and waits.
        self.assertEqual((summary['captured'],summary['pending'],summary['reasons']['tope_de_lecturas']),(1,1,1))
        self.assertEqual(summary['stopped'],'Tope diario de lecturas de desenlaces «comments» alcanzado (1). El resto queda pendiente para la próxima corrida.')
        self.assertNotIn(f'activity%3A{F.OTHER_POST}',' '.join(t.paths()))
        later=NOW+timedelta(days=1)  # another local day, its own reads
        summary,_=self.collect_at(*routes,now=later,**caps)
        self.assertEqual((summary['captured'],summary['pending'],summary['stopped']),(1,0,''))
        self.assertEqual((ActionOutcome.objects.get(execution=second).replies,ActionOutcome.objects.count()),(0,2))
        self.assertEqual([desenlaces_captura.reads_today(self.directo,'comments',at) for at in (NOW,later)],[1,1])

    def test_a_second_run_writes_nothing_new(self):
        execution=self.commented(F.POST);follow=self.networked('RED-01',self.person(),NOW-timedelta(days=8))
        routes=(comments_of(F.POST,top(F.POST,replies=0)),)
        self.collect_at(*routes)
        summary,t=self.collect_at(*routes)
        self.assertEqual((summary['captured'],summary['pending'],len(t.sent),ActionOutcome.objects.count()),(0,0,0,2))  # nothing due or read
        # A run that had them due while another one wrote them (a race): the unique age keeps one row each, no error.
        racing=ActionExecution.objects.filter(pk__in=[execution.pk,follow.pk]).select_related('proposal').order_by('started_at')
        with patch.object(desenlaces,'due',return_value=racing):
            summary,_=self.collect_at(*routes)
        self.assertEqual((summary['captured'],summary['pending'],ActionOutcome.objects.count()),(0,0,2))

    def test_a_refusal_that_pauses_the_account_stops_the_reads(self):
        first=self.commented(F.POST);self.commented(F.OTHER_POST,at=WRITTEN+timedelta(hours=1))
        follow=self.networked('RED-01',self.person(),NOW-timedelta(days=8))
        summary,t=self.collect_at(comments_of(F.POST,Answer(429,'{}','application/json')),comments_of(F.OTHER_POST,top(F.OTHER_POST,replies=0)))
        self.directo.refresh_from_db()
        self.assertTrue(self.directo.paused);self.assertIn('Desenlaces detenidos por el proveedor',self.directo.paused_reason)
        self.assertNotIn(f'activity%3A{F.OTHER_POST}',' '.join(t.paths()))  # nothing else is read
        self.assertEqual((summary['by_kind']['INT-03'],summary['reasons']['error_de_lectura']),({'captured':0,'pending':2},2))
        self.assertIn('HTTP 429',summary['stopped'])
        self.assertFalse(ActionOutcome.objects.filter(execution=first).exists())
        # The network's outcomes read nothing on LinkedIn: they are written all the same.
        self.assertEqual(ActionOutcome.objects.get(execution=follow).signals,NO_SIGNAL)

    def test_nothing_left_from_the_navegador_service_stops_the_reads_without_a_pause(self):
        def busy(request):raise LinkedInError('El servicio del navegador no tiene cupo; no salió nada.',kind='budget',retry_after=600)
        self.commented(F.POST);self.commented(F.OTHER_POST,at=WRITTEN+timedelta(hours=1))
        summary,t=self.collect_at(comments_of(F.POST,busy),comments_of(F.OTHER_POST,top(F.OTHER_POST,replies=0)))
        self.directo.refresh_from_db();self.assertFalse(self.directo.paused)
        self.assertEqual((summary['captured'],summary['pending'],summary['reasons']['error_de_lectura']),(0,2,2))
        self.assertIn('no tiene cupo',summary['stopped'])
        self.assertNotIn(f'activity%3A{F.OTHER_POST}',' '.join(t.paths()))
        self.assertFalse(ActionOutcome.objects.exists())

    def test_another_read_error_leaves_only_that_comment_pending(self):
        first=self.commented(F.POST);second=self.commented(F.OTHER_POST,at=WRITTEN+timedelta(hours=1))
        summary,_=self.collect_at(comments_of(F.POST,Answer(404,'{}','application/json')),comments_of(F.OTHER_POST,top(F.OTHER_POST,replies=0)))
        self.assertFalse(ActionOutcome.objects.filter(execution=first).exists())
        self.assertEqual(ActionOutcome.objects.get(execution=second).replies,0)
        self.assertEqual((summary['captured'],summary['pending'],summary['reasons']['error_de_lectura'],summary['stopped']),(1,1,1,''))
        self.directo.refresh_from_db();self.assertFalse(self.directo.paused)
        self.assertIn(first,list(desenlaces.due(NOW)))


class NetworkOutcomeTests(OutcomeCaptureBase):
    def test_network_outcomes_are_derived_from_own_rows_and_written_even_when_nothing_happened(self):
        since=NOW-timedelta(days=8)
        def at(days):return since+timedelta(days=days)
        def noted(days):return [{'at':at(days).isoformat(),'event':'incoming','detail':'Te envió una invitación.'}]
        warm=self.person(connected_at=at(2),history=noted(1))
        cold=self.person(stage='invited',history=noted(-1))  # it invited before the action: not after it
        follow=self.networked('RED-01',warm,since);invite=self.networked('RED-02',cold,since)
        piece=EditorialPiece.objects.create(account=self.directo,slot_date=date(2026,11,1),scheduled_for=at(-3),state='ready',
                                            final_text='Un post propio de prueba.')
        for n,(contact,days) in enumerate(((warm,3),(cold,-2))):
            PostComment.objects.create(account=self.directo,piece=piece,provider_post_id=F.POST,provider_comment_id=F.snowflake(at(days),40+n),
                                       author_provider_id=contact.provider_user_id,commented_at=at(days),contact=contact)
        PostComment.objects.create(account=self.directo,piece=piece,provider_post_id=F.POST,provider_comment_id=F.snowflake(at(4),50),
                                   commented_at=at(4),own=True,contact=cold)  # own: never theirs
        # Answers to the team's comments, kept by earlier INT-03 outcomes.
        for post,days,contact in ((F.OTHER_POST,4,warm),(F.snowflake(F.POSTED-timedelta(days=9),11),-2,cold)):
            ActionOutcome.objects.create(execution=self.commented(post,at=at(days)-timedelta(hours=72)),kind='72h',source='read',
                                         captured_at=at(days),replies=1,repliers=[contact.provider_user_id])
        Conversation.objects.create(account=self.directo,provider_chat_id=F.THREAD,contact=warm,last_message_at=at(5))
        Conversation.objects.create(account=self.directo,provider_chat_id=F.GROUP,contact=cold,last_message_at=at(-1))
        summary,t=self.collect_at()
        self.assertEqual(t.sent,[])  # derived: not one LinkedIn read
        self.assertEqual(ActionOutcome.objects.get(execution=follow).signals,dict.fromkeys(NO_SIGNAL,True))
        quiet=ActionOutcome.objects.get(execution=invite)
        self.assertEqual((quiet.kind,quiet.source,quiet.signals,quiet.reactions,quiet.replies,quiet.author_replied,quiet.captured_at),
                         ('7d','derived',NO_SIGNAL,None,None,None,NOW))
        self.assertEqual((summary['captured'],summary['pending'],summary['by_kind']['RED-01'],summary['by_kind']['RED-02']),
                         (2,0,{'captured':1,'pending':0},{'captured':1,'pending':0}))
        self.assertEqual(desenlaces.network_engaged(now=NOW),{warm.id:sorted(NO_SIGNAL)})  # what the readers see


class OutcomesJobTests(OutcomeCaptureBase):
    def test_the_job_runs_the_collector_and_says_what_it_wrote(self):
        now=timezone.now()
        self.commented(F.POST,at=now-timedelta(hours=80))
        self.networked('RED-01',self.person(),now-timedelta(days=8))
        transport=F.FakeTransport(ME,comments_of(F.POST,top(F.POST,replies=0)))
        jobs.enqueue_operation(self.bot,'collect_outcomes',{'account':str(self.directo.id)})
        with patch.object(connectors_directo,'TRANSPORT',transport):
            while jobs.process_one(self.worker):pass
        job=Job.objects.get(kind='collect_outcomes')
        self.assertEqual(job.state,'complete');self.assertTrue(job.result_status.startswith('desenlaces:'))
        self.assertEqual((job.result_status,job.error),('desenlaces:2 pendientes:0',''))
        self.assertEqual(set(ActionOutcome.objects.values_list('kind','source')),{('72h','read'),('7d','derived')})
