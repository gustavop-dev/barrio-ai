"""Language of comments and replies (Gustavo, 2026-11-12) as a fixed rule, and the comment drafter's context: what it
must flag for evidence and his recent comments so it does not retell an anecdote. Fake connector, no paid calls."""
import json
from unittest.mock import patch

from django.utils import timezone

from team_backend import autopiloto, idioma, jobs, lider, operador, respuestas
from team_backend.models import ActionProposal, ObservedPost, PostComment
from team_backend.tests.test_respuestas import QUESTION, REPLY, UNIT, RepliesBase

SPANISH_POST=('Esta semana probamos un agente que llama a los leads que no contestaron la primera vez. Lo difícil no fue la '
              'voz, fue decidir quién es dueño del lead cuando nadie responde. ¿Ustedes cómo lo resuelven?')
SPANISH_COMMENT=('Me dio curiosidad lo del dueño del lead, porque siento que ahí es donde más se pierde. ¿Lo decide un área o '
                 'una regla del proceso?')
ENGLISH_COMMENT=('The ownership part is the one that got me thinking. When nobody owns the lead after the first call, '
                 'it just sits there. Is that decided by a team or by a rule in the process?')
SPANISH_REPLY=('Buena pregunta. Yo empezaría por las pruebas que cuidan los flujos que la gente usa todos los días, porque son '
               'las que más se rompen cuando el producto cambia.')


class LanguageTests(RepliesBase):
    def test_detect_tells_spanish_from_english_and_abstains_on_short_texts(self):
        self.assertEqual(idioma.detect(SPANISH_POST),'es')
        self.assertEqual(idioma.detect(ENGLISH_COMMENT),'en')
        self.assertEqual(idioma.detect(QUESTION),'en')
        for short in ('Great post! 👏','Ya estamos en vivo!','Evals first, then tooling.',''):
            self.assertIsNone(idioma.detect(short),short)

    def comment(self,post,text,source='agent'):
        return ActionProposal(account=self.account,post=post,capability='INT-03',payload={'text':text},citations=[UNIT],source=source)

    def test_an_agent_comment_in_english_on_a_spanish_post_breaks_a_fixed_rule(self):
        spanish=ObservedPost.objects.create(account=self.account,provider_post_id='activity:es-1',author_name='Ana Referente',
                                            text=SPANISH_POST,posted_at=timezone.now())
        english=self.observed()[0]
        rule='Está en inglés y la publicación está en español'
        self.assertIn(rule,autopiloto.comment_text_issues(self.comment(spanish,ENGLISH_COMMENT)))
        self.assertNotIn(rule,autopiloto.comment_text_issues(self.comment(spanish,SPANISH_COMMENT)))
        # Spanish on an English post is right when the conversation is in Spanish, which only the drafter sees.
        self.assertNotIn(rule,autopiloto.comment_text_issues(self.comment(english,SPANISH_COMMENT)))
        # A comment Gustavo asked for is his call.
        self.assertNotIn(rule,autopiloto.comment_text_issues(self.comment(spanish,ENGLISH_COMMENT,source='human')))

    def test_a_reply_goes_in_the_language_of_the_comment(self):
        piece,pid=self.publish()
        row=PostComment.objects.create(account=self.account,piece=piece,provider_post_id=pid,provider_comment_id='comment:q',
                                       author_name='María PM',text=QUESTION,commented_at=timezone.now())
        def issues(text):
            return respuestas.reply_text_issues(ActionProposal(account=self.account,comment=row,capability=respuestas.REPLY,
                                                               payload={'text':text},citations=[UNIT],source='agent'))
        self.assertIn('No está en el idioma del comentario (en)',issues(SPANISH_REPLY))
        self.assertFalse([i for i in issues(REPLY) if 'idioma' in i])

    def test_the_lead_no_longer_asks_jev_about_the_language_of_comments_or_replies(self):
        for kind in ('text','reply'):
            self.assertNotIn('idioma',[check[0] for check in lider.CHECKS[kind]],kind)


class DrafterContextTests(RepliesBase):
    def test_the_drafter_sees_his_recent_comments_and_flags_only_facts(self):
        posts=self.observed()
        ActionProposal.objects.create(account=self.account,post=posts[1],capability='INT-03',source='agent',state='confirmed',
                                      payload={'text':'Earlier comment: evals are where the work hides.'},citations=[UNIT])
        ActionProposal.objects.create(account=self.account,post=posts[1],capability='INT-03',source='agent',state='discarded',
                                      payload={'text':'A discarded draft never reaches LinkedIn.'},citations=[UNIT])
        answer={'decision':'skip','language':'en','comment':'','rationale':'Nada genuino que aportar.','citations':[],
                'claims_needing_evidence':[],'risks':[]}
        with patch('knowledge.providers.claude',return_value={'text':json.dumps(answer),'model':'claude-opus-5-5'}) as claude:
            jobs.enqueue_operation(self.gustavo,'propose_comment',{'post':str(posts[0].id)});jobs.process_one(self.worker)
        sent=json.loads(claude.call_args.args[1])
        self.assertEqual(sent['recent_own_comments'],[{'author':posts[1].author_name,'text':'Earlier comment: evals are where the work hides.'}])
        self.assertEqual(operador.recent_own_comments(self.account,exclude_post=posts[1]),[])
        # Opinions, questions and the post's own figures are not claims to verify: they used to discard good drafts.
        self.assertNotIn('cualquier afirmación que Gustavo deba comprobar',operador.COMMENT_SYSTEM)
        self.assertIn('atribuidas a su autor',operador.COMMENT_SYSTEM)
        self.assertIn('recent_own_comments',operador.COMMENT_SYSTEM)
