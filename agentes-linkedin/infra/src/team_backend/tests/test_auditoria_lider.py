"""Phases 2 and 3 of the AI architecture audit (docs/auditoria-arquitectura-ia.md), lead and comments slice:
R5 (Jev prefilter before a paid draft), B3 (lead reviews per tick), the lead's silence alert, the comment half of R4
(one redraft for a fixed-rule failure), C1 (course units cached in the system prompt) and C5 (one Anthropic client per key)."""
import json
import os
import uuid
from datetime import timedelta
from unittest.mock import patch

import httpx
from django.utils import timezone

from knowledge import db, providers
from team_backend import autopiloto, jobs, notificaciones, operador, voz
from team_backend.models import ActionProposal, AuditEvent, Contact, Job, Notification, ObservedPost
from team_backend.tests.fakes import FakeAnthropic
from team_backend.tests.test_operador import OperatorBase
from team_backend.tests.test_rediseno import GOOD, LeadBase

UNIT='LI-03-M006-K02'


def draft(text=GOOD,decision='comment',claims=(),citations=(UNIT,)):
    answer={'decision':decision,'language':'en','comment':text,'rationale':'Aporta un ángulo concreto.','citations':list(citations),
            'claims_needing_evidence':list(claims),'risks':[]}
    return {'text':json.dumps(answer),'model':'claude-opus-5-5'}


class ProviderCacheTests(OperatorBase):
    """C1 and C5: stable context is cached with the instructions; the SDK client is built once per key."""

    def call(self,**kwargs):
        env={'LIVE_PROVIDERS':'true','ANTHROPIC_API_KEY':'test-only','ANTHROPIC_LIMIT_USD':'5','ANTHROPIC_MODEL':'claude-opus-5-5'}
        with patch.dict(os.environ,env),patch('knowledge.providers.anthropic_client',return_value=FakeAnthropic()) as client:
            providers.claude('Instrucciones','Tarea',purpose='prueba',**kwargs)
        (count,counted),(stream,streamed)=client.return_value.calls
        self.assertEqual((count,stream),('count_tokens','stream'))
        self.assertEqual(counted['system'],streamed['system'])  # the reservation counts exactly what is sent
        return streamed

    def test_without_context_the_system_prompt_is_the_same_single_cached_block(self):
        sent=self.call()
        self.assertEqual(sent['system'],[{'type':'text','text':'Instrucciones','cache_control':{'type':'ephemeral'}}])
        self.assertEqual(sent['messages'],[{'role':'user','content':'Tarea'}])

    def test_stable_context_goes_in_cached_system_blocks_before_the_task(self):
        sent=self.call(context='Unidades del curso')
        self.assertEqual(sent['system'],[{'type':'text','text':'Instrucciones','cache_control':{'type':'ephemeral'}},
                                         {'type':'text','text':'Unidades del curso','cache_control':{'type':'ephemeral'}}])
        blocks=self.call(context=['A','','B','C'])['system']
        self.assertEqual([b['text'] for b in blocks],['Instrucciones','A','B','C'])
        self.assertEqual([('cache_control' in b) for b in blocks],[True,False,False,True])  # 2 of the 4 breakpoints

    def test_the_client_is_reused_per_key(self):
        providers._anthropic_client.cache_clear();self.addCleanup(providers._anthropic_client.cache_clear)
        first=providers.anthropic_client('k-test-1')
        self.assertIs(providers.anthropic_client('k-test-1'),first)
        self.assertIsNot(providers.anthropic_client('k-test-2'),first)
        self.assertEqual(first.max_retries,0)  # paid generations are still never retried by the SDK


class CommentDraftTests(OperatorBase):
    """C1 in the comment drafter and the comment half of R4: one redraft naming the fixed rule that failed."""

    def setUp(self):
        super().setUp();self.post,self.other=self.observed()

    def propose(self,*answers,post=None):
        with patch('knowledge.providers.claude',side_effect=list(answers)) as claude:
            proposal=operador.propose_comment(self.gustavo,(post or self.post).id)
        return proposal,claude

    def test_the_course_units_are_cached_context_not_part_of_the_message(self):
        proposal,claude=self.propose(draft())
        args,kwargs=claude.call_args
        self.assertEqual(args[0],voz.with_voice(operador.COMMENT_SYSTEM))
        self.assertNotIn('course_units',json.loads(args[1]))
        self.assertIn(UNIT,kwargs['context']);self.assertTrue(kwargs['context'].startswith('Unidades del curso'))
        self.assertEqual((kwargs['purpose'],kwargs['output_schema']),('propose-comment',operador.COMMENT_SCHEMA))
        self.assertEqual((proposal.state,proposal.citations),('proposed',[UNIT]))
        # The context is byte-identical across drafts, so the second one reads it from the cache.
        _,again=self.propose(draft(),post=self.other)
        self.assertEqual(again.call_args.kwargs['context'],kwargs['context'])

    def test_a_draft_that_breaks_a_fixed_rule_gets_one_redraft_naming_it(self):
        proposal,claude=self.propose(draft(GOOD+' #evals #AI'),draft())
        self.assertEqual(claude.call_count,2)
        revision=json.loads(claude.call_args_list[1].args[1])['revision']
        self.assertEqual(revision['previous_comment'],GOOD+' #evals #AI');self.assertEqual(revision['rule_violations'],['Contiene hashtags'])
        self.assertEqual(claude.call_args_list[1].kwargs['context'],claude.call_args_list[0].kwargs['context'])  # cached prefix
        self.assertEqual(proposal.payload['text'],GOOD)
        self.assertIn('Reescrito una vez por las reglas fijas: Contiene hashtags',proposal.risks)
        self.assertEqual(autopiloto.policy_review(proposal).state,'approved')

    def test_unsupported_claims_are_named_in_the_redraft(self):
        proposal,claude=self.propose(draft(GOOD,claims=['80% menos latencia']),draft())
        revision=json.loads(claude.call_args_list[1].args[1])['revision']
        self.assertEqual(revision['rule_violations'],['Incluye afirmaciones sin evidencia'])
        self.assertEqual(revision['claims_needing_evidence'],['80% menos latencia'])
        self.assertFalse(any(r.startswith('Afirmación por verificar') for r in proposal.risks))

    def test_a_redraft_that_still_fails_is_discarded_by_the_policy_as_before(self):
        proposal,claude=self.propose(draft(GOOD+' #evals'),draft(GOOD+' more at https://example.com'))
        self.assertEqual(claude.call_count,2)  # only one redraft
        proposal=autopiloto.policy_review(proposal);proposal.refresh_from_db()
        self.assertEqual(proposal.state,'discarded');self.assertIn('Contiene enlaces',proposal.risks)

    def test_a_redraft_may_skip(self):
        proposal,_=self.propose(draft(GOOD+' #evals'),draft('',decision='skip'))
        self.assertEqual(proposal.state,'discarded')

    def test_a_failed_redraft_keeps_the_first_draft(self):
        proposal,claude=self.propose(draft(GOOD+' #evals'),ValueError('anthropic: HTTP 529. Sin reintento automático.'))
        self.assertEqual(claude.call_count,2)
        self.assertEqual(proposal.payload['text'],GOOD+' #evals')
        self.assertTrue(any(r.startswith('No se pudo reescribir') for r in proposal.risks),proposal.risks)

    def test_no_redraft_without_budget_in_approval_mode_or_when_the_author_is_blocked(self):
        with patch.dict(os.environ,{'OPERATOR_AUTONOMY':'INT-03=approval'}):
            _,claude=self.propose(draft(GOOD+' #evals'))
        self.assertEqual(claude.call_count,1)  # Gustavo approves by hand: the fixed rules are not applied
        ActionProposal.objects.all().delete()
        providers.reserve('anthropic','propose-comment','1')  # today's comment budget is spent
        _,claude=self.propose(draft(GOOD+' #evals'))
        self.assertEqual(claude.call_count,1)
        ActionProposal.objects.all().delete()
        with db.connect() as c:c.execute('TRUNCATE usage_ledger')
        first=operador.create_proposal(self.gustavo,self.other,'INT-03',{'text':GOOD},citations=[UNIT],source='agent')
        ActionProposal.objects.filter(pk=first.pk).update(state='approved')
        _,claude=self.propose(draft(GOOD+' #evals'))
        self.assertEqual(claude.call_count,1)  # same referent within the cooldown: no text fixes that


class PrefilterTests(LeadBase):
    """R5: Jev decides whether a post deserves a comment before Opus is paid to draft one."""

    def setUp(self):
        super().setUp()
        posts=self.observed();now=timezone.now()
        self.newest,self.older=posts[1],posts[0]
        ObservedPost.objects.filter(pk=self.newest.pk).update(posted_at=now-timedelta(hours=1),
                                                              text='We are hiring! Senior backend engineer, remote. Apply now.')
        ObservedPost.objects.filter(pk=self.older.pk).update(posted_at=now-timedelta(hours=2))
        self.requests=self.jev_by_post()

    def jev_by_post(self,noise=('hiring',),status=200,sustancia=0.9):
        """TypeSafe transport: posts containing a `noise` word look like a hiring announcement."""
        requests=[]
        def handler(request):
            body=json.loads(request.content);requests.append(body)
            if status!=200:return httpx.Response(status,json={'detail':'overloaded'})
            hiring=any(word in body['state']['publicacion']['texto'] for word in noise)
            probabilities={'sustancia':sustancia,'tema':0.9,'vacante':0.95 if hiring else 0.03,'promocion':0.05,'hito':0.02}
            answers={q:{'type':'noul','noul':probabilities.get(q,0.5)} for q in body['questions']}
            return httpx.Response(200,json={'model':'jev-1.14.0','answers':answers,'usage':{'input_tokens':300}})
        transport=patch.object(providers,'TYPESAFE_TRANSPORT',httpx.MockTransport(handler))
        transport.start();self.addCleanup(transport.stop)
        return requests

    def propose(self):
        return autopiloto._propose(self.gustavo,self.account,timezone.now())

    def drafted(self):
        return list(Job.objects.filter(kind='propose_comment').values_list('params__post',flat=True))

    def verdicts(self):
        return list(AuditEvent.objects.filter(action=autopiloto.PREFILTER_ACTION).order_by('id').values_list('target','metadata__decision'))

    def test_a_hiring_post_is_skipped_and_the_next_candidate_is_drafted(self):
        self.assertEqual(self.propose(),1)
        self.assertEqual(self.drafted(),[str(self.older.id)])
        self.assertEqual(self.verdicts(),[(str(self.newest.id),'skip'),(str(self.older.id),'comment')])
        self.assertEqual(set(self.requests[0]['questions']),{'sustancia','tema','vacante','promocion','hito'})
        skip=AuditEvent.objects.get(action=autopiloto.PREFILTER_ACTION,target=str(self.newest.id)).metadata
        self.assertTrue(any('vacantes' in r for r in skip['reasons']),skip)
        with db.connect() as c:
            purposes=[r['purpose'] for r in c.execute("SELECT purpose FROM usage_ledger WHERE provider='typesafe'").fetchall()]
        self.assertEqual(purposes,['comment-prefilter']*2)
        with db.connect() as c:  # never an LLM for the filter
            self.assertEqual(c.execute("SELECT count(*) AS n FROM usage_ledger WHERE provider='anthropic'").fetchone()['n'],0)

    def test_verdicts_are_remembered_instead_of_asked_every_tick(self):
        self.requests=self.jev_by_post(noise=('hiring','evals'))  # both posts look like noise
        self.assertEqual(self.propose(),0)
        self.assertEqual(self.propose(),0)
        self.assertEqual(len(self.requests),2)  # asked once per post, never again
        self.assertEqual([d for _,d in self.verdicts()],['skip','skip']);self.assertEqual(self.drafted(),[])

    def test_a_positive_verdict_is_not_asked_again_either(self):
        self.assertEqual(self.propose(),1)
        Job.objects.filter(kind='propose_comment').update(state=Job.State.FAILED)  # the paid draft failed
        self.assertEqual(self.propose(),0)  # a failed paid draft is not retried automatically, as before
        self.assertEqual(len(self.requests),2)

    def test_unavailable_jev_falls_back_to_drafting_and_logs_it(self):
        self.requests=self.jev_by_post(status=529)
        with self.assertLogs('team_backend.autopilot','WARNING') as logs:
            self.assertEqual(self.propose(),1)
        self.assertEqual(self.drafted(),[str(self.newest.id)])  # today's behaviour: the newest post
        self.assertEqual(self.verdicts(),[(str(self.newest.id),'unavailable')])
        self.assertIn('comment_prefilter_unavailable',logs.output[0])

    def test_threshold_and_switch(self):
        self.requests=self.jev_by_post(noise=(),sustancia=0.9)
        with patch.dict(os.environ,{'COMMENT_PREFILTER_THRESHOLD':'0.95'}):
            self.assertEqual(self.propose(),0)  # 0.9 < 0.95: neither post passes
        self.assertEqual([d for _,d in self.verdicts()],['skip','skip'])
        with patch.dict(os.environ,{'COMMENT_PREFILTER':'false'}):
            self.assertEqual(self.propose(),1)  # switched off, the remembered verdicts no longer apply
        self.assertEqual(self.drafted(),[str(self.newest.id)]);self.assertEqual(len(self.requests),2)

    def test_at_most_three_questions_per_tick(self):
        now=timezone.now()
        for i in range(3):
            ObservedPost.objects.create(account=self.account,referent=self.older.referent,provider_post_id=f'activity:extra-{i}',
                                        author_name='Ana Referente',text=f'We are hiring engineer number {i}.',posted_at=now-timedelta(hours=3+i))
        self.jev_by_post(noise=('hiring','evals'))
        self.assertEqual(self.propose(),0);self.assertEqual(len(self.verdicts()),3)
        self.assertEqual(self.propose(),0);self.assertEqual(len(self.verdicts()),5)
        self.assertEqual(self.propose(),0);self.assertEqual(len(self.verdicts()),5)

    def test_orientation_informs_the_topic_question(self):
        self.human.put('/api/v1/orientacion',{'text':'Comentar más sobre contratación técnica en startups.'},format='json')
        self.propose()
        body=self.requests[0]
        self.assertIn('contratación técnica',body['state']['orientacion_de_gustavo'])
        self.assertIn('orientacion_de_gustavo',body['questions']['tema']['instructions'])

    def test_no_prefilter_without_the_lead(self):
        with patch.dict(os.environ,{'LEAD_ENABLED':'false'}):
            self.assertEqual(self.propose(),1)
        self.assertEqual((self.requests,self.drafted()),([],[str(self.newest.id)]))


class LeadReviewCapTests(LeadBase):
    """B3: the lead reviews at most LEAD_MAX_REVIEWS_PER_TICK proposals per tick, oldest first."""

    def setUp(self):
        super().setUp()
        self.jev.probabilities={'encaja':0.85,'riesgo':0.05}
        env=patch.dict(os.environ,{'OPERATOR_AUTONOMY':'RED-01=auto','LEAD_MAX_REVIEWS_PER_TICK':'5'})
        env.start();self.addCleanup(env.stop)

    def follows(self,n,fit=True):
        out=[];start=timezone.now()-timedelta(hours=1)
        for i in range(n):
            contact=Contact.objects.create(account=self.account,provider_user_id=f'ACoperson-{uuid.uuid4().hex[:12]}',display_name=f'Persona {i}',
                headline='Founder @ Tiny',source='manual',stage='fit',classification={'fit':fit,'role':'comprador','reason':'r','confidence':0.9})
            proposal=operador.create_proposal(self.gustavo,None,'RED-01',{'user_id':contact.provider_user_id},source='agent',contact=contact)
            ActionProposal.objects.filter(pk=proposal.pk).update(created_at=start+timedelta(minutes=i))
            out.append(proposal)
        return out

    def lead_calls(self):
        return len([r for r in self.jev.requests if 'encaja' in r['questions']])

    def states(self,proposals):
        return [ActionProposal.objects.get(pk=p.pk).state for p in proposals]

    def test_the_lead_reviews_at_most_the_cap_per_tick_oldest_first(self):
        proposals=self.follows(7)
        report=autopiloto.tick(self.gustavo)
        self.assertEqual((self.lead_calls(),report['reviewed'],report['lead_deferred']),(5,7,2))
        self.assertEqual(self.states(proposals),['approved']*5+['proposed']*2)
        report=autopiloto.tick(self.gustavo)
        self.assertEqual(self.lead_calls(),7);self.assertNotIn('lead_deferred',report)
        self.assertNotIn('proposed',self.states(proposals))

    def test_an_unavailable_lead_is_not_waited_for_again_in_the_same_tick(self):
        proposals=self.follows(3);self.jev.status=529
        report=autopiloto.tick(self.gustavo)
        self.assertEqual((len(self.jev.requests),report['lead_deferred']),(1,2))
        self.assertEqual(self.states(proposals),['proposed']*3)
        self.assertIn('error_at',ActionProposal.objects.get(pk=proposals[0].pk).review)

    def test_deterministic_decisions_and_expiry_do_not_wait_for_the_cap(self):
        waiting,=self.follows(1);misfit,=self.follows(1,fit=False);stale,=self.follows(1)
        ActionProposal.objects.filter(pk=stale.pk).update(created_at=timezone.now()-timedelta(hours=49))
        with patch.dict(os.environ,{'LEAD_MAX_REVIEWS_PER_TICK':'0'}):
            report=autopiloto.tick(self.gustavo)
        self.assertEqual(self.states([waiting,misfit,stale]),['proposed','discarded','expired'])
        self.assertEqual((self.lead_calls(),report['expired'],report['lead_deferred']),(0,1,1))


class LeadSilenceTests(LeadBase):
    """The lead's failure mode is silent inaction: alert when a capability gets no approval in 7 days."""

    def setUp(self):
        super().setUp();self.post=self.observed()[0]
        autopiloto._silence_checked_at=None;self.addCleanup(setattr,autopiloto,'_silence_checked_at',None)

    def reviewed(self,decision='discard',days=1,n=1):
        for _ in range(n):
            proposal=operador.create_proposal(self.gustavo,self.post,'INT-03',{'text':GOOD},citations=[UNIT],source='agent')
            ActionProposal.objects.filter(pk=proposal.pk).update(state='discarded' if decision=='discard' else 'confirmed',
                decided_at=timezone.now()-timedelta(days=days),
                review={'decision':decision,'answers':{'aporta':0.4,'pitch':0.05},'thresholds':{'aporta':['min',0.7],'pitch':['max',0.2]}})

    def test_alerts_once_per_capability_and_week(self):
        self.reviewed(n=5)
        with patch('team_backend.alerts.notify') as notify:
            self.assertEqual(autopiloto.lead_silence(),1)
            self.assertEqual(autopiloto.lead_silence(),0)  # same capability, same week
        notification=Notification.objects.get(kind='lead_silent')
        self.assertEqual(notification.layer,'sistema');self.assertTrue(notification.ref.startswith('lead_silent:INT-03:'))
        self.assertIn('revisó 5 propuestas',notification.detail);self.assertIn('aporta (5)',notification.detail)
        self.assertEqual(notification.link,'/calendario?vista=lista&tipo=comentarios&no_salio=1')
        notify.assert_called_once()
        push={t['kind']:t for t in notificaciones.push_types()}['lead_silent']
        self.assertEqual((push['goes_to'],push['default']),('notificaciones',True))

    def test_no_alert_with_an_approval_too_few_reviews_or_outside_auto(self):
        self.reviewed(n=4);self.reviewed(days=8)  # the old one is outside the window
        self.assertEqual(autopiloto.lead_silence(),0)
        self.reviewed();self.reviewed('approve')
        self.assertEqual(autopiloto.lead_silence(),0)
        ActionProposal.objects.filter(review__decision='approve').update(review={})
        with patch.dict(os.environ,{'OPERATOR_AUTONOMY':'INT-03=approval'}):self.assertEqual(autopiloto.lead_silence(),0)
        with patch.dict(os.environ,{'LEAD_SILENCE_MIN_REVIEWS':'6'}):self.assertEqual(autopiloto.lead_silence(),0)
        with patch.dict(os.environ,{'LEAD_ENABLED':'false'}):self.assertEqual(autopiloto.lead_silence(),0)
        self.assertEqual(autopiloto.lead_silence(),1)

    def test_the_tick_checks_at_a_low_frequency(self):
        with patch('team_backend.autopiloto.lead_silence',return_value=0) as check:
            autopiloto.tick(self.gustavo);autopiloto.tick(self.gustavo)
            self.assertEqual(check.call_count,1)
            with patch.dict(os.environ,{'LEAD_SILENCE_CHECK_MINUTES':'0'}):autopiloto.tick(self.gustavo)
            self.assertEqual(check.call_count,2)
