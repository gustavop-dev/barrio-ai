"""INT-04: the team answers the comments on Gustavo's own posts. Fake connector and patched providers only: no LinkedIn
writes and no paid calls."""
import json
import uuid
from datetime import timedelta
from unittest.mock import patch
from django.utils import timezone
from knowledge import db
from team_backend import autopiloto, jobs, operador, respuestas
from team_backend.models import ActionExecution, ActionProposal, AuditEvent, Contact, EditorialPiece, Job, PostComment, TeamQuestion
from team_backend.tests.test_red import NetworkBase

POST='Most AI agents fail in production because nobody owns the evals. The model is rarely the bottleneck; the feedback loop is.'
QUESTION='How do you decide which evals to write first when the product changes every single week? We keep rewriting them.'
FOLLOW_UP=('Interesting, we tried golden datasets but they went stale in a month. Do you version them with the prompts or apart?')
REPLY=('Good question. Start with the evals that guard the flows people use every day: when the product changes weekly, '
       'those catch regressions first and survive the rewrites. Which part of your product moves the most?')
CLOSING=('Versioning them next to the prompts keeps both honest, and stale golden sets are a sign the flows moved first. '
         'This conversation is getting interesting, happy to connect and keep it going.')
UNIT='LI-03-M006-K02'


def draft(decision='reply',reply=REPLY,dm_opener='',question=None,citations=(UNIT,)):
    data={'decision':decision,'language':'en','reply':reply,'rationale':'Answers the concrete question about evals.',
          'citations':list(citations),'claims_needing_evidence':[],'risks':[],'dm_opener':dm_opener,
          'question_for_gustavo':question or {'question':'','purpose':'','memory_key':''}}
    return patch('knowledge.providers.claude',return_value={'text':json.dumps(data),'model':'claude-opus-5-5'})


class RepliesBase(NetworkBase):
    def setUp(self):
        super().setUp()
        env=patch.dict('os.environ',{'REPLIES_ENABLED':'true','REPLIES_READ_CAPS':'','REPLIES_WINDOW_HOURS':'72',
                                     'REPLIES_FRESH_EVERY_MINUTES':'120','REPLIES_LATE_EVERY_MINUTES':'720'})
        env.start();self.addCleanup(env.stop)
        self.slots=0
        # B14 (the reader's perspective) is not among the other roles' units: synthetic fixture rows, never course text.
        with db.connect() as c:
            for uid in operador.REPLY_UNITS:
                c.execute('''INSERT INTO units(id,session,title,original,sha256,source_path,pointer,metadata)
                    VALUES(%s,%s,%s,'{"title":"Synthetic course fixture","limits_errors":"Do not infer facts or authority"}',
                    'fixture-hash','fixture','/units/0','{}') ON CONFLICT(id) DO NOTHING''',(uid,int(uid[3:5]),uid))

    def publish(self,text=POST,hours_ago=5):
        """A CONT-09 publication confirmed `hours_ago`, and the own post Unipile shows for it."""
        when=timezone.now()-timedelta(hours=hours_ago);self.slots+=1
        piece=EditorialPiece.objects.create(account=self.account,slot_date=timezone.now().date()-timedelta(days=400+self.slots),scheduled_for=when,
                                            state='ready',final_text=text,brief={'thesis':'Nobody owns the evals','approach':'opinion'})
        proposal=ActionProposal.objects.create(account=self.account,piece=piece,capability='CONT-09',payload={'text':text},payload_hash='0'*64,state='confirmed')
        ActionExecution.objects.create(proposal=proposal,idempotency_key=uuid.uuid4().hex,provider='linkedin_fake',state='confirmed',
                                       executed_by=self.gustavo,started_at=when)
        return piece,self.fake.seed_own_post(text)

    def person(self,public_id='maria-pm',name='María PM',headline='Head of Product at a B2B SaaS startup'):
        return self.fake.seed_person(public_id,name,headline=headline)

    def read(self):
        jobs.enqueue_operation(self.bot,'read_own_comments',{'account':str(self.account.id)})
        self.drain()
        return Job.objects.filter(kind='read_own_comments').order_by('-created_at').first()

    def rescan(self):
        AuditEvent.objects.filter(action='replies.scanned').delete()  # the next read is due right away
        return self.read()

    def propose(self,row,patcher):
        with patcher as claude:
            jobs.enqueue_operation(self.bot,'propose_reply',{'comment':str(row.id)},request_id=uuid.uuid4());self.drain()
        return claude

    def execute_proposal(self,proposal):
        """The autonomous gate (rules, no lead in tests) and the operator."""
        proposal=autopiloto.policy_review(ActionProposal.objects.get(pk=proposal.pk))
        self.assertEqual(proposal.state,'approved',proposal.risks)
        return operador.execute(self.gustavo,proposal.id)


class ReadingTests(RepliesBase):
    def test_comments_become_people_and_the_read_respects_its_cadence(self):
        piece,pid=self.publish()
        maria=self.person()
        self.fake.comment_on_own_post(pid,maria['id'],QUESTION)
        job=self.read()
        self.assertEqual(job.state,'complete',job.error)
        row=PostComment.objects.get()
        self.assertEqual((row.piece_id,row.provider_post_id,row.state,row.author_name),(piece.id,pid,'new','María PM'))
        self.assertEqual(row.decision['turn'],1)
        contact=row.contact
        self.assertEqual((contact.source,contact.stage),(Contact.Source.OWN_POST,'candidate'))
        self.assertEqual(contact.evidence['comment'],QUESTION)
        self.assertEqual(contact.history[-1]['event'],'discovered')
        self.assertEqual(AuditEvent.objects.get(action='replies.scanned').metadata['post_id'],pid)
        piece.refresh_from_db();self.assertEqual(piece.metrics,{})  # piece.metrics belongs to metricas
        # Inside the 2 h cadence nothing is due; reading again later adds nothing twice.
        self.assertFalse(respuestas.reading_due(self.account))
        self.rescan()
        self.assertEqual(PostComment.objects.count(),1)
        self.assertEqual(self.fake.state['writes'],0)

    def test_a_short_congratulation_only_gets_a_reaction_and_stale_comments_close(self):
        _,pid=self.publish(hours_ago=100)
        maria,juan=self.person(),self.person('juan-dev','Juan Dev','Engineer')
        self.fake.comment_on_own_post(pid,maria['id'],'Great post! 👏')
        self.fake.comment_on_own_post(pid,juan['id'],QUESTION,at=timezone.now()-timedelta(hours=80))
        self.read()
        congrats=PostComment.objects.get(author_name='María PM');stale=PostComment.objects.get(author_name='Juan Dev')
        self.assertEqual(congrats.state,'react')
        reaction=ActionProposal.objects.get(comment=congrats)
        self.assertEqual((reaction.capability,reaction.payload),('INT-02',{'reaction':'linkedin_like'}))
        self.assertEqual(stale.state,'closed')
        self.assertIn('72 h',stale.decision['reason'])
        execution=self.execute_proposal(reaction)
        self.assertEqual(execution.state,'confirmed')
        self.assertEqual(self.fake.state['comment_reactions'],{congrats.provider_comment_id:'linkedin_like'})

    def test_the_team_steps_back_when_gustavo_answers_himself(self):
        _,pid=self.publish()
        maria=self.person()
        root=self.fake.comment_on_own_post(pid,maria['id'],QUESTION,at=timezone.now()-timedelta(minutes=30))
        self.fake.state['threads'][root]=[{'id':'comment:own-manual','text':'Thanks María, I usually start with the flows that pay.',
            'is_sender':True,'thread_id':root,'author':{'id':'me','display_name':'Cuenta conectada'},'created_at':timezone.now().isoformat()}]
        self.read()
        row=PostComment.objects.get(provider_comment_id=root)
        self.assertEqual(row.state,'closed')
        self.assertEqual(PostComment.objects.get(provider_comment_id='comment:own-manual').state,'own')


class ReplyTests(RepliesBase):
    def test_a_grounded_reply_follows_the_thread_and_is_written_once(self):
        piece,pid=self.publish()
        maria=self.person()
        self.fake.comment_on_own_post(pid,maria['id'],QUESTION)
        self.read()
        row=PostComment.objects.get()
        claude=self.propose(row,draft())
        message=json.loads(claude.call_args.args[1])
        self.assertEqual(claude.call_args.kwargs['output_schema'],respuestas.REPLY_SCHEMA)
        self.assertEqual(claude.call_args.kwargs['purpose'],'propose-reply')
        # Grounded in the library, not in the model's memory: every INT-04 unit travels whole in the context.
        context=claude.call_args.kwargs['context']
        self.assertTrue(context.startswith('Unidades del curso'))
        for uid in operador.REPLY_UNITS:self.assertIn(uid,context)
        self.assertEqual(message['post']['thesis'],'Nobody owns the evals')
        self.assertEqual(message['post']['text'],POST)
        self.assertTrue(message['thread'][0]['this_comment'])
        self.assertEqual(message['person']['headline'],'Head of Product at a B2B SaaS startup')  # profile read before drafting
        self.assertEqual((message['turn'],message['closing_allowed']),(1,False))
        proposal=ActionProposal.objects.get(capability='INT-04')
        self.assertEqual((proposal.comment_id,proposal.payload,proposal.citations),(row.id,{'text':REPLY},[UNIT]))
        execution=self.execute_proposal(proposal)
        self.assertEqual(execution.state,'confirmed')
        own=self.fake.state['threads'][row.provider_comment_id]
        self.assertEqual([c['text'] for c in own],[REPLY])
        self.assertEqual(self.fake.state['writes'],1)
        row.refresh_from_db();row.contact.refresh_from_db()
        self.assertEqual(row.state,'reply');self.assertIn('replied_at',row.decision)
        self.assertEqual(row.contact.history[-1]['event'],'replied')
        # The answer read back is shown once, as the team's comment in the thread.
        self.rescan()
        payload=respuestas.piece_payload(piece)
        thread=payload['threads'][0]
        self.assertEqual((thread['comment']['status'],thread['comment']['reply']),('respondido',None))
        self.assertEqual([(a['own'],a['status'],a['text']) for a in thread['answers']],[(True,'equipo',REPLY)])
        self.assertEqual(payload['count'],1)

    def test_without_the_library_there_is_no_draft(self):
        _,pid=self.publish()
        maria=self.person()
        self.fake.comment_on_own_post(pid,maria['id'],QUESTION)
        self.read();row=PostComment.objects.get()
        with db.connect() as c:c.execute("DELETE FROM units WHERE id='LI-05-V005-K05'")
        claude=self.propose(row,draft())
        self.assertEqual(claude.call_count,0)
        job=Job.objects.get(kind='propose_reply')
        self.assertEqual(job.state,'failed');self.assertIn('Biblioteca',job.error)
        self.assertFalse(ActionProposal.objects.filter(capability='INT-04').exists())

    def test_an_identical_answer_already_in_the_thread_is_not_written_again(self):
        _,pid=self.publish()
        maria=self.person()
        root=self.fake.comment_on_own_post(pid,maria['id'],QUESTION)
        self.read();row=PostComment.objects.get()
        self.propose(row,draft())
        proposal=ActionProposal.objects.get(capability='INT-04')
        self.fake.comment_in_thread(pid,root,REPLY);writes=self.fake.state['writes']
        execution=self.execute_proposal(proposal)
        self.assertEqual((execution.state,execution.wrote),('confirmed',False))
        self.assertEqual(self.fake.state['writes'],writes)

    def test_selling_or_proposing_to_connect_on_the_first_reply_is_redrafted_then_discarded(self):
        _,pid=self.publish()
        maria=self.person()
        self.fake.comment_on_own_post(pid,maria['id'],QUESTION)
        self.read();row=PostComment.objects.get()
        claude=self.propose(row,draft(reply='Great question, happy to connect and talk privately about it, send me a DM.'))
        self.assertEqual(claude.call_count,2)  # one redraft naming the broken rules
        revision=json.loads(claude.call_args.args[1])['revision']
        self.assertTrue(any('conectar' in issue for issue in revision['rule_violations']))
        proposal=autopiloto.policy_review(ActionProposal.objects.get(capability='INT-04'))
        self.assertEqual(proposal.state,'discarded')
        self.assertEqual(self.fake.state['writes'],0)

    def test_second_turn_closes_by_proposing_to_connect_and_leaves_a_drafted_message(self):
        _,pid=self.publish()
        maria=self.person()
        root=self.fake.comment_on_own_post(pid,maria['id'],QUESTION,at=timezone.now()-timedelta(minutes=20))
        self.read();first=PostComment.objects.get()
        self.propose(first,draft());self.execute_proposal(ActionProposal.objects.get(capability='INT-04'))
        Contact.objects.filter(pk=first.contact_id).update(classification={'fit':True,'role':'comprador','confidence':0.9})
        self.fake.comment_on_own_post(pid,maria['id'],FOLLOW_UP,thread=root,at=timezone.now()+timedelta(seconds=5))
        self.rescan()
        second=PostComment.objects.get(text=FOLLOW_UP)
        self.assertEqual((second.thread_id,second.state,second.decision['turn']),(root,'new',2))
        opener='Hi María, I kept thinking about your golden datasets going stale. How are you versioning them now?'
        claude=self.propose(second,draft(reply=CLOSING,dm_opener=opener))
        message=json.loads(claude.call_args.args[1])
        self.assertEqual((message['turn'],message['closing_allowed'],message['already_connected']),(2,True,False))
        self.assertEqual([t['text'] for t in message['thread']][:2],[QUESTION,REPLY])
        proposal=ActionProposal.objects.get(capability='INT-04',comment=second)
        self.assertEqual(self.execute_proposal(proposal).state,'confirmed')
        self.assertEqual([c['text'] for c in self.fake.state['threads'][root] if c['is_sender']],[REPLY,CLOSING])
        contact=Contact.objects.get(pk=first.contact_id)
        self.assertTrue(contact.evidence['conversed'])
        # Not a connection yet: no card. Once connected, Tu turno brings the drafted first message; the team never sends it.
        self.assertEqual(respuestas.cards(lambda *a,**k:k),[])
        Contact.objects.filter(pk=contact.pk).update(stage='connected',connected_at=timezone.now(),network_distance='FIRST_DEGREE')
        respuestas.on_connected(Contact.objects.get(pk=contact.pk))
        turno=self.human.get('/api/v1/tu-turno').json()
        card=turno['tasks']['mensajes'][0]
        self.assertEqual((card['type'],card['id']),('mensaje',f'dm:{second.id}'))
        self.assertEqual(card['message']['text'],opener)
        self.assertEqual(card['message']['reply'],CLOSING)
        closed=self.human.post(f'/api/v1/respuestas/{second.id}/mensaje',{'how':'enviado'},format='json')
        self.assertEqual(closed.status_code,200,closed.content)
        self.assertEqual(self.human.get('/api/v1/tu-turno').json()['tasks']['mensajes'],[])
        self.assertEqual(Contact.objects.get(pk=contact.pk).history[-1]['event'],'dm')
        writes=self.fake.state['writes']
        self.assertEqual(writes,2)  # two public replies, no message
        # A third comment never gets a third public reply.
        self.fake.comment_on_own_post(pid,maria['id'],'And how do you handle evals for agents that call tools? Same approach?',
                                      thread=root,at=timezone.now()+timedelta(seconds=30))
        self.rescan()
        third=PostComment.objects.get(text__startswith='And how')
        self.assertEqual(third.state,'closed')

    def test_closing_is_not_allowed_with_someone_who_does_not_fit(self):
        _,pid=self.publish()
        maria=self.person()
        root=self.fake.comment_on_own_post(pid,maria['id'],QUESTION,at=timezone.now()-timedelta(minutes=20))
        self.read();first=PostComment.objects.get()
        self.propose(first,draft());self.execute_proposal(ActionProposal.objects.get(capability='INT-04'))
        self.fake.comment_on_own_post(pid,maria['id'],FOLLOW_UP,thread=root,at=timezone.now()+timedelta(seconds=5))
        self.rescan()
        second=PostComment.objects.get(text=FOLLOW_UP)
        claude=self.propose(second,draft(reply=CLOSING,dm_opener='Hi!'))
        self.assertFalse(json.loads(claude.call_args_list[0].args[1])['closing_allowed'])
        proposal=autopiloto.policy_review(ActionProposal.objects.get(comment=second))
        self.assertEqual(proposal.state,'discarded')
        second.refresh_from_db();self.assertEqual(second.decision['dm_opener'],'')

    def test_a_thin_follow_up_gets_a_reaction(self):
        _,pid=self.publish()
        maria=self.person()
        root=self.fake.comment_on_own_post(pid,maria['id'],QUESTION,at=timezone.now()-timedelta(minutes=20))
        self.read();first=PostComment.objects.get()
        self.propose(first,draft());self.execute_proposal(ActionProposal.objects.get(capability='INT-04'))
        self.fake.comment_on_own_post(pid,maria['id'],'Makes sense, thanks!',thread=root,at=timezone.now()+timedelta(seconds=5))
        self.rescan()
        thanks=PostComment.objects.get(text='Makes sense, thanks!')
        self.assertEqual(thanks.state,'react')
        self.assertEqual(ActionProposal.objects.get(comment=thanks).capability,'INT-02')


class QuestionTests(RepliesBase):
    def test_an_unknown_fact_becomes_a_question_and_his_answer_feeds_the_reply(self):
        _,pid=self.publish()
        maria=self.person()
        self.fake.comment_on_own_post(pid,maria['id'],'Which eval framework do you use in your own projects?')
        self.read();row=PostComment.objects.get()
        ask={'question':'¿Qué framework de evals usas en tus proyectos?','purpose':'Para responderle a María en tu post.',
             'memory_key':'gustavo.evals.framework'}
        self.propose(row,draft(decision='ask_gustavo',reply='',question=ask))
        row.refresh_from_db()
        self.assertEqual(row.state,'asked')
        question=TeamQuestion.objects.get(id=row.decision['question'])
        self.assertEqual((question.origin,question.memory_key,question.suggested_public),(f'respuesta:{row.id}','gustavo.evals.framework',True))
        self.assertEqual(respuestas.next_to_draft(self.account),None)  # waits for him
        TeamQuestion.objects.filter(pk=question.pk).update(state='answered',answer='Uso promptfoo y evals propias en pytest.',public_use=True)
        again=respuestas.next_to_draft(self.account)
        self.assertEqual(again.pk,row.pk)
        inputs=respuestas.context(again)
        self.assertTrue(inputs['no_ask'])
        self.assertEqual(inputs['gustavo_answer'],{'question':question.question,'answer':'Uso promptfoo y evals propias en pytest.','public':True})


class AutopilotTests(RepliesBase):
    def test_the_autopilot_reads_when_due_then_drafts_one_comment_at_a_time(self):
        _,pid=self.publish()
        maria,juan=self.person(),self.person('juan-dev','Juan Dev','Staff engineer')
        self.fake.comment_on_own_post(pid,maria['id'],QUESTION,at=timezone.now()-timedelta(minutes=10))
        self.fake.comment_on_own_post(pid,juan['id'],FOLLOW_UP,at=timezone.now()-timedelta(minutes=5))
        now=timezone.now()
        self.assertEqual(autopiloto._replies(self.bot,self.account,now),1)
        self.assertEqual(autopiloto._replies(self.bot,self.account,now),0)  # the read is pending
        self.drain()
        self.assertEqual(autopiloto._replies(self.bot,self.account,now),1)
        job=Job.objects.get(kind='propose_reply')
        self.assertEqual(job.params,{'comment':str(PostComment.objects.get(author_name='María PM').id)})
        with draft():self.drain()
        self.assertEqual(ActionProposal.objects.filter(capability='INT-04').count(),1)
        with patch.dict('os.environ',{'OPERATOR_AUTONOMY':'INT-04=off'}):
            self.assertEqual(autopiloto._replies(self.bot,self.account,now),0)

    def test_a_reply_goes_before_other_approved_actions(self):
        _,pid=self.publish()
        follow=self.contact('founder-eva','Eva Founder')
        other=operador.create_proposal(self.bot,None,'RED-01',{'user_id':follow.provider_user_id},contact=follow,state='approved')
        ActionProposal.objects.filter(pk=other.pk).update(approved_hash=other.payload_hash)
        maria=self.person()
        self.fake.comment_on_own_post(pid,maria['id'],QUESTION)
        self.read();row=PostComment.objects.get()
        self.propose(row,draft())
        reply=autopiloto.policy_review(ActionProposal.objects.get(capability='INT-04'))
        self.assertEqual(autopiloto._execute(self.bot,self.account,timezone.now()),1)
        self.assertEqual(Job.objects.get(kind='execute_action').params,{'proposal':str(reply.id)})


class NetworkTests(RepliesBase):
    def test_a_fitting_commenter_on_his_post_is_invited_without_the_warm_up(self):
        eva=self.contact('founder-eva','Eva Founder',stage='followed',followed_hours=1)
        Contact.objects.filter(pk=eva.pk).update(source=Contact.Source.OWN_POST)
        self.job('plan_network')
        invite=ActionProposal.objects.get(contact=eva)
        self.assertEqual(invite.capability,'RED-02')


class RulesTests(RepliesBase):
    def test_reply_rules(self):
        _,pid=self.publish()
        maria=self.person()
        self.fake.comment_on_own_post(pid,maria['id'],QUESTION)
        self.read();row=PostComment.objects.get()
        def issues(text,closing=False):
            proposal=ActionProposal(account=self.account,comment=row,capability='INT-04',payload={'text':text},citations=[UNIT],source='agent')
            proposal._closing=closing
            return respuestas.reply_text_issues(proposal)
        self.assertEqual(issues(REPLY),[])
        self.assertIn('Contiene venta o pitch',issues(REPLY+' Book a call with our services team.'))
        self.assertIn('Contiene enlaces',issues(REPLY+' https://example.com'))
        self.assertTrue(any('conectar' in i for i in issues(CLOSING)))
        self.assertEqual(issues(CLOSING,closing=True),[])
        self.assertTrue(respuestas.congratulation('Congrats, great post! 🔥'))
        self.assertFalse(respuestas.congratulation('Great post, but how do you measure it?'))
