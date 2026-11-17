"""READ_WINDOW and the comments of his own posts along the day (16/11/2026): the autopilot queues background reads only
inside the window, reads the newest post first, spaces out the posts that bring nothing and spends the «comments» cap
along the window so an afternoon comment is still read. Production functions at a simulated clock; fake connector only."""
import uuid
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo
from team_backend import autopiloto, jobs, operador, respuestas
from team_backend.models import ActionExecution, ActionProposal, AuditEvent, Contact, EditorialPiece, Job
from team_backend.tests.test_respuestas import QUESTION, RepliesBase

BOGOTA=ZoneInfo('America/Bogota')
DAY=datetime(2026,11,4,tzinfo=BOGOTA)  # a Wednesday; the window is 07:00-21:00 there
READ_JOBS={'observe','discover_network','classify_contacts','sync_network','collect_metrics','collect_outcomes',
           'import_analytics','check_linkedin','read_inbox','read_own_comments'}


def at(hour,minute=0,days=0):
    return DAY+timedelta(days=days,hours=hour,minutes=minute)


class WindowBase(RepliesBase):
    def setUp(self):
        super().setUp()
        env=patch.dict('os.environ',{'READ_WINDOW':'07:00-21:00','OPERATOR_TIMEZONE':'America/Bogota','REPLIES_PIECES_PER_RUN':'4',
                                     'REPLIES_NEWEST_HOURS':'48','REPLIES_IDLE_MAX_MINUTES':'240'})
        env.start();self.addCleanup(env.stop)
        self.clock=at(0);self.people=0

    def post_at(self,when,text):
        """A CONT-09 publication confirmed at `when`, whose id the write kept (no «posts» read to find it)."""
        pid=self.fake.seed_own_post(text);self.slots+=1
        piece=EditorialPiece.objects.create(account=self.account,slot_date=DAY.date()-timedelta(days=400+self.slots),scheduled_for=when,
                                            state='ready',final_text=text,brief={'thesis':text[:60],'approach':'opinion'})
        proposal=ActionProposal.objects.create(account=self.account,piece=piece,capability='CONT-09',payload={'text':text},
                                               payload_hash='0'*64,state='confirmed')
        ActionExecution.objects.create(proposal=proposal,idempotency_key=uuid.uuid4().hex,provider='linkedin_fake',state='confirmed',
                                       executed_by=self.gustavo,started_at=when,external_id=pid)
        return piece,pid

    def comment(self,pid,when):
        self.people+=1
        person=self.person(f'persona-{self.people}',f'Persona {self.people}')
        return self.fake.comment_on_own_post(pid,person['id'],f'{QUESTION} ({self.people})',at=when)

    def simulate(self,posts,comments=(),start=None,end=None,step=timedelta(minutes=5)):
        """posts: [(published_at, text)], published when the clock gets there; comments: [(when, post index)], left when
        the clock gets there. Each step is one autopilot pass of _replies and the worker, at the simulated clock; drafts
        are out of the picture (next_to_draft finds nothing). Returns {post index: (piece, pid)} and [(when, piece)]."""
        published={};left=[];waiting=sorted(comments,key=lambda c:c[0])
        self.clock=start or at(0)
        with patch('django.utils.timezone.now',side_effect=lambda:self.clock),patch.object(respuestas,'next_to_draft',return_value=None):
            while self.clock<(end or at(24)):
                for index,(when,text) in enumerate(posts):
                    if index not in published and when<=self.clock:published[index]=self.post_at(when,text)
                while waiting and waiting[0][0]<=self.clock:
                    when,index=waiting.pop(0);self.comment(published[index][1],when);left.append((when,published[index][0]))
                autopiloto._replies(self.bot,self.account,self.clock)
                self.drain()
                self.clock+=step
        return published,left

    def reads(self,day=0):
        """Local times of the «comments» reads of a day."""
        start=at(0,days=day)
        return sorted(t.astimezone(BOGOTA) for t in AuditEvent.objects.filter(action='replies.read',metadata__kind='comments',
                      created_at__gte=start,created_at__lt=start+timedelta(days=1)).values_list('created_at',flat=True))

    def scans(self,piece):
        return sorted(AuditEvent.objects.filter(action='replies.scanned',target=str(piece.id)).values_list('created_at',flat=True))

    def latency(self,when,piece):
        """How long a comment left at `when` waited for the read that brought it (None: not read by the end)."""
        read=next((t for t in self.scans(piece) if t>=when),None)
        return read-when if read else None


# Eight posts of the week: one a day at 08:30 (today's included) plus a second one three days ago, so at midday four
# are under 72 h. Comments: four on today's post (one at 16:00), two on yesterday's, one on each of two older ones.
WEEK=[(at(8,30,days),f'Post del día {days}: {QUESTION}') for days in range(-7,1)]+[(at(17,0,-3),'Segundo post de hace tres días.')]
TODAY,YESTERDAY,OLDER,SECOND=7,6,2,8
COMMENTS=[(at(9,0,-1),YESTERDAY-1),(at(12,0,-1),YESTERDAY),(at(23,0,-1),YESTERDAY),
          (at(9,10),TODAY),(at(11,45),TODAY),(at(16,0),TODAY),(at(20,30),TODAY),
          (at(10,0),YESTERDAY),(at(14,0),YESTERDAY),(at(13,0),SECOND),(at(12,0),OLDER)]


class DayTests(WindowBase):
    def run_week(self,cap=None):
        if cap:
            env=patch.dict('os.environ',{'REPLIES_READ_CAPS':f'comments={cap}'});env.start();self.addCleanup(env.stop)
        # Yesterday first, so today starts with the history of reads a real day has.
        return self.simulate(WEEK,COMMENTS,start=at(0,days=-1),end=at(24))

    def report(self,label,left):
        reads=self.reads();hours={}
        for t in reads:hours[t.hour]=hours.get(t.hour,0)+1
        waits={f'{w.astimezone(BOGOTA):%H:%M} {p.final_text[:18]}':str(self.latency(w,p) or 'sin leer hoy') for w,p in left if w>=at(0)}
        print(f'\n[{label}] lecturas «comments» hoy={len(reads)} por hora={dict(sorted(hours.items()))} esperas={waits}')
        return reads

    def test_a_day_with_eight_posts_reads_only_inside_the_window_and_keeps_cap_for_the_evening(self):
        published,left=self.run_week()
        reads=self.report('tope 100',left)
        for day in (-1,0):
            self.assertTrue(all(7<=t.hour<21 for t in self.reads(day)),self.reads(day))  # nothing at night
        cap=respuestas.read_caps()['comments']
        self.assertEqual(cap,100)
        self.assertLess(len(reads),cap//2)  # the cap is margin, not pace
        self.assertGreaterEqual(reads[-1].hour,19)  # still reading in the evening
        # (b) The 16:00 comment on today's post is read within two hours; every comment on a post under 72 h, left
        # inside the window, within the idle ceiling (4 h).
        today=published[TODAY][0]
        self.assertLessEqual(self.latency(at(16),today),timedelta(hours=2))
        for when,piece in left:
            age=when-ActionExecution.objects.get(proposal__piece=piece).started_at
            if when>=at(7) and when<at(21)-respuestas.idle_max() and age<timedelta(hours=72):
                self.assertLessEqual(self.latency(when,piece),respuestas.idle_max(),(when,piece.final_text[:20]))
        # Last night's comment waits for the window to open, and is read when it does.
        self.assertEqual(self.latency(at(23,0,-1),published[YESTERDAY][0]),timedelta(hours=8))

    def test_a_tight_cap_is_spent_along_the_window_and_the_newest_post_keeps_its_reads(self):
        # The week needs about 28 reads; with 20 the share of the window decides who waits, never the newest post.
        _,left=self.run_week(cap=20)
        reads=self.report('tope 20',left)
        self.assertEqual(len(reads),20)
        self.assertLessEqual(sum(1 for t in reads if t.hour<12),12)  # the morning does not spend the day's cap
        self.assertGreaterEqual(reads[-1].hour,19)
        today=next(p for w,p in left if w==at(16))
        self.assertLessEqual(self.latency(at(16),today),timedelta(hours=2))


class CadenceTests(WindowBase):
    def test_posts_without_comments_space_out_and_a_new_comment_brings_them_back(self):
        env=patch.dict('os.environ',{'REPLIES_IDLE_MAX_MINUTES':'480'});env.start();self.addCleanup(env.stop)
        posts=[(at(9,0,-1),'Post de ayer.'),(at(6,0),'Post de hoy.')]
        published,_=self.simulate(posts,[(at(6,30),0),(at(13,30),0)],start=at(7),end=at(10,0,1))
        yesterday=published[0][0];scans=self.scans(yesterday)
        print(f'\n[cadencia 480] post de ayer leído a las {[f"{t.astimezone(BOGOTA):%d %H:%M}" for t in scans]}')
        # 07:00 brings the 06:30 comment → 2 h → 09:00 nothing → 4 h → 13:00 nothing → 8 h: due at 21:00, read when the
        # window opens; that read brings the 13:30 comment → back to 2 h.
        self.assertEqual([(b-a).total_seconds()/3600 for a,b in zip(scans,scans[1:])],[2.0,4.0,18.0,2.0])
        self.assertEqual(respuestas.cadence(timedelta(hours=30),idle=0),timedelta(hours=2))
        self.assertEqual(respuestas.cadence(timedelta(hours=30),idle=1),timedelta(hours=4))
        self.assertEqual(respuestas.cadence(timedelta(hours=30),idle=2),timedelta(hours=8))
        self.assertEqual(respuestas.cadence(timedelta(hours=30),idle=5),timedelta(hours=8))
        # The newest post keeps 2 h during its first REPLIES_NEWEST_HOURS, whatever its reads bring.
        self.assertEqual(respuestas.cadence(timedelta(hours=30),idle=5,newest=True),timedelta(hours=2))
        self.assertEqual(respuestas.cadence(timedelta(hours=50),idle=5,newest=True),timedelta(hours=8))
        # 72 h and day 7 stay the outer limits.
        self.assertEqual(respuestas.cadence(timedelta(hours=80),idle=0),timedelta(hours=12))
        self.assertEqual(respuestas.publications(at(6,1,7)),[])

    def test_the_default_ceiling_is_four_hours(self):
        self.assertEqual(respuestas.cadence(timedelta(hours=30),idle=3),timedelta(hours=4))

    def test_the_newest_post_and_the_active_ones_are_read_first(self):
        old,_=self.post_at(at(9,0,-2),'Hace dos días.')
        active,_=self.post_at(at(9,0,-1),'Ayer.')
        newest,_=self.post_at(at(6,0),'Hoy.')
        AuditEvent.objects.create(action='replies.scanned',target=str(old.id),metadata={'found':True,'new':0},created_at=at(4))
        AuditEvent.objects.create(action='replies.scanned',target=str(active.id),metadata={'found':True,'new':2},created_at=at(4))
        rows=respuestas.plan(at(9))
        self.assertEqual([r.piece for r in rows],[newest,active,old])
        env=patch.dict('os.environ',{'REPLIES_PIECES_PER_RUN':'1'});env.start();self.addCleanup(env.stop)
        self.assertEqual([p for _,p in respuestas.to_read(self.account,at(9))],[newest])


class CapTests(WindowBase):
    def test_a_spent_cap_stops_queueing_until_the_next_day_with_one_record(self):
        env=patch.dict('os.environ',{'REPLIES_READ_CAPS':'comments=3'});env.start();self.addCleanup(env.stop)
        posts=[(at(9,0,-1-n),f'Post {n}') for n in range(5)]
        self.simulate(posts,start=at(7),end=at(21))
        self.assertEqual(len(self.reads()),3)
        self.assertEqual(AuditEvent.objects.filter(action='replies.read_cap_reached').count(),1)
        self.assertLessEqual(Job.objects.filter(kind='read_own_comments').count(),3)  # no job only to record the stop
        # The next day reads again.
        self.simulate(posts,start=at(7,0,1),end=at(8,0,1))
        self.assertGreater(len(self.reads(1)),0)


class WindowTests(WindowBase):
    def test_read_window_and_bounds(self):
        self.assertFalse(operador.within_read_window(at(6,59)))
        self.assertTrue(operador.within_read_window(at(7)))
        self.assertTrue(operador.within_read_window(at(20,59)))
        self.assertFalse(operador.within_read_window(at(21)))
        self.assertEqual(operador.read_bounds(at(12)),(at(7),at(21)))
        with patch.dict('os.environ',{'READ_WINDOW':''}):
            self.assertIsNone(operador.read_window())
            self.assertTrue(operador.within_read_window(at(3)))
            self.assertEqual(operador.read_bounds(at(12)),(at(0),at(24)))

    def due_everywhere(self):
        """State where every periodic read of the autopilot would be queued: a referent to observe, people to discover
        and classify, a post to read, metrics, outcomes, analytics, the canary and the inbox due."""
        operador.add_referent(self.gustavo,self.account,'https://www.linkedin.com/in/referente-ai/','Habla de agentes')
        Contact.objects.create(account=self.account,provider_user_id='u-1',display_name='Sin clasificar',source='manual',stage='candidate')
        self.post_at(at(1),'Post de esta madrugada.')
        from team_backend import analitica, canario, conversaciones, desenlaces, metricas
        patches=[patch.object(metricas,'due',return_value=True),patch.object(analitica,'daily_due',return_value=True),
                 patch.object(canario,'daily_due',return_value=True),patch.object(conversaciones,'enabled',return_value=True),
                 patch.object(desenlaces,'due',return_value=MagicMock(exists=MagicMock(return_value=True)))]
        for p in patches:p.start();self.addCleanup(p.stop)

    def queued(self,now):
        before=set(Job.objects.values_list('id',flat=True))
        for function in (autopiloto._observe,autopiloto._network,autopiloto._metrics,autopiloto._outcomes,autopiloto._analytics,
                         autopiloto._canary,autopiloto._inbox,autopiloto._replies):
            function(self.bot,self.account,now)
        return set(Job.objects.exclude(id__in=before).values_list('kind',flat=True))

    def test_every_periodic_read_waits_for_the_window(self):
        self.due_everywhere()
        night=self.queued(at(3))
        self.assertEqual(night&READ_JOBS,set())
        self.assertEqual(night,{'plan_network'})  # the plan reads nothing: it turns judged people into proposals
        Job.objects.all().delete()
        self.assertEqual(self.queued(at(10))&READ_JOBS,READ_JOBS)

    def test_without_read_window_reads_are_queued_at_any_hour(self):
        self.due_everywhere()
        with patch.dict('os.environ',{'READ_WINDOW':''}):
            self.assertEqual(self.queued(at(3))&READ_JOBS,READ_JOBS)

    def test_writes_their_reconciliation_and_what_gustavo_asks_go_on_at_night(self):
        night=at(3)
        piece,pid=self.post_at(at(1),'Post de esta madrugada.')
        self.comment(pid,at(2))
        # What Gustavo asks from the app reads at any hour.
        with patch('django.utils.timezone.now',return_value=night):
            jobs.enqueue_operation(self.gustavo,'read_own_comments',{'account':str(self.account.id)});self.drain()
        self.assertEqual(len(self.reads()),1)
        # An approved write is executed, and an unconfirmed one reconciled, outside the read window.
        proposal=operador.create_proposal(self.gustavo,None,'INT-02',{'reaction':'linkedin_like'},rationale='r',source='agent',
                                          comment=piece.post_comments.get())
        ActionProposal.objects.filter(pk=proposal.pk).update(state='approved',approved_hash=proposal.payload_hash)
        self.assertEqual(autopiloto._execute(self.bot,self.account,night),1)
        sent=ActionExecution.objects.get(proposal__piece=piece)
        ActionExecution.objects.filter(pk=sent.pk).update(state='sent',started_at=night-timedelta(hours=1))
        self.assertEqual(autopiloto._reconcile(self.bot,night),1)
