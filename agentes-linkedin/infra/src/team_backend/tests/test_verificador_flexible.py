"""A less rigid verifier for the daily piece (Gustavo, 19/11/2026): «el verificador es muy rígido… es un post… no tiene
que ser tan estricto… su propia rigidez nos perjudica… ayúdame a regularlo y a bajarlo más».

Only an invented fact about Gustavo, his company or his clients presented as real, and private material, stop a piece
(after the one repair round, which fixes that sentence). A figure or quote attributed to a source the evidence does not
hold, an explanation beyond a confirmed fact, an approximate figure, a selling tone or a quality problem are notes: the
repair may soften them and the piece goes out either way. Claude is patched: no spend."""
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from team_backend import compuertas, editorial, guardas, research
from team_backend.models import ActionProposal
from team_backend.tests import test_auditoria_editorial as tae
from team_backend.tests.test_publicacion import GOOD_POST, INVENTED, answers

# 12/11/2026 in production: public_facts said that letting agents talk to each other loses context; the post explained
# why, and the verifier blocked it: «public_facts only says that letting agents communicate loses context. It does not
# say why». An opinion post may explain why.
WHY='''Letting AI agents pass work to each other loses context. I have said it before, and the reason is simple.

Every hand-off compresses the task into a summary. The next agent reads the summary, not the conversation that produced it, so the constraints that never made it into the summary are gone. Two hand-offs later, the agent is solving a cleaner, easier problem than the one the founder actually has.

That is why I keep one agent holding the whole thread and give the others narrow, checkable jobs. It costs a longer prompt; it saves a week of chasing a bug that lives between two agents.

Where does context get lost in your pipeline?'''
EXPLANATION='Every hand-off compresses the task into a summary, so the constraints that never made it into the summary are gone.'
STAT='According to McKinsey, 72% of companies already use agents in production.'
SOFTENED=GOOD_POST.replace('Founders often arrive','Several reports suggest most companies are already testing agents. Founders often arrive')
WITH_STAT=GOOD_POST.replace('Founders often arrive',STAT+' Founders often arrive')


def review(*findings,verdict='blocked',unsupported=(),supported=()):
    return {'verdict':verdict,'findings':list(findings),'summary':'','citations':['LI-06-M002-K09'],
            'checked_claims':[{'text':t,'status':'unsupported','ref':''} for t in unsupported]+
                             [{'text':t,'status':'supported_source','ref':r} for t,r in supported]}


class SeverityTableTests(SimpleTestCase):
    def test_only_invented_facts_about_him_and_private_material_are_hard(self):
        self.assertEqual(set(compuertas.HARD),{'invented_experience','private_data','private_guidance_leak','first_person_appropriation'})
        for issue in ('unsourced_figure','unsupported_claim','fabricated_quote','unsourced_third_party_story','aggressive_pitch',
                      'hook_not_delivered','off_brief','other','cta_count','no_reader_need'):
            self.assertEqual(compuertas.severity(issue),'blanda',issue)
        reasons,soft=compuertas.split(review(unsupported=[EXPLANATION]))
        self.assertEqual((reasons,[s['issue'] for s in soft]),([],['unsupported_claim']))
        self.assertEqual(compuertas.split(review()),([],[{'issue':'other','quote':'','detail':'El verificador emitió blocked sin hallazgos concretos'}]))

    def test_the_verifier_reads_an_opinion_post_not_a_paper(self):
        verifier,repair=(' '.join(text.split()) for text in (editorial.VERIFIER_SYSTEM,editorial.REPAIR_SYSTEM))
        for text in (verifier,repair):self.assertIn('post de opinión de LinkedIn',text)
        self.assertIn('Explicar por qué ocurre un hecho confirmado es opinion, no unsupported',verifier)
        self.assertIn('nunca un motivo para recortar el texto',repair)


class RuleTallyTests(SimpleTestCase):
    """C (19/11/2026): each verification keeps, per rule, how many notes and how many blocks it gave."""
    def test_each_rule_counts_its_notes_and_its_blocks(self):
        hard={'issue':'invented_experience','severity':'material','quote':'q','detail':'Not in public_facts.'}
        soft={'issue':'unsourced_figure','severity':'material','quote':STAT,'detail':'McKinsey no está en la evidencia.'}
        minor={'issue':'other','severity':'minor','quote':'','detail':'Could be shorter.'}
        final=dict(review(hard,soft,minor,unsupported=[EXPLANATION]),source_notes=['Afirmación web sin contraste del verificador: x'],
                   experience_flags=['Experiencia en primera persona: «Last month I rebuilt…»'])
        reasons=['Hallazgo material (invented_experience): Not in public_facts.','Ronda de reparación: la descartó: sin motivo']
        repair={'findings':[{'source':'reglas','issue':'regla','quote':'','detail':'Contiene enlaces'}],
                'resolution':[{'source':'reglas','issue':'regla','resolved':True}]}
        self.assertEqual(compuertas.rule_tally(reasons,final,repair),{
            'invented_experience':{'notas':0,'bloqueos':1},'unsourced_figure':{'notas':1,'bloqueos':0},
            'unsupported_claim':{'notas':1,'bloqueos':0},'other':{'notas':1,'bloqueos':0},'fuente_web':{'notas':1,'bloqueos':0},
            'experiencia_por_redaccion':{'notas':1,'bloqueos':0},'enlaces':{'notas':1,'bloqueos':0}})

    def test_rules_that_stop_the_text_are_blocks_and_a_soft_strategy_line_is_a_note(self):
        rules=['Contiene enlaces','cta_count: 2 llamadas a la acción; una venta lleva una sola',
               'Cifra sobre el trabajo de Ana que no consta en sus hechos públicos («3» en «x»)']
        self.assertEqual(compuertas.rule_tally(rules),{'enlaces':{'notas':0,'bloqueos':1},'cta_count':{'notas':1,'bloqueos':0},
                                                       'invented_experience':{'notas':0,'bloqueos':1}})
        self.assertEqual(compuertas.rule_tally([],review()),{'veredicto_sin_hallazgos':{'notas':1,'bloqueos':0}})
        self.assertEqual(compuertas.rule_tally([],review(verdict='ready_for_execution')),{})


class ExperienceRuleTests(SimpleTestCase):
    FACTS=[{'key':'trayectoria.projectapp','fact':'Gustavo founded ProjectApp, a software studio that builds products for startups.'}]

    def test_questions_hypotheses_and_what_a_source_reports_are_not_lived_experience(self):
        for text in ('If we built agents that talk to each other, we would lose context.','Should my team rewrite everything?',
                     'Last year I read that a study found 70% of AI projects fail.','Imagine we launched without a waitlist.',
                     'Según un estudio, el 60% de los equipos migramos tarde.'):
            with self.subTest(text):
                self.assertEqual((guardas.invented_experience(text,[]),guardas.invented_figures(text,[])),([],[]))

    def test_a_year_is_a_date_and_a_figure_about_his_work_is_a_fact(self):
        self.assertEqual(guardas.invented_figures('In 2024 we launched the beta for our clients.',self.FACTS),[])
        self.assertEqual(guardas.invented_figures(INVENTED,self.FACTS),
            ['Cifra sobre el trabajo de Gustavo que no consta en sus hechos públicos («40» en «Last year I built an AI pipeline for a '
             'fintech client that cut their review costs by 40% in three months.»)'])

    def test_the_wording_alone_only_points_the_sentence_out_to_the_verifier(self):
        text=GOOD_POST.replace('Founders often arrive','Last month I rebuilt a reporting flow for a retailer. Founders often arrive')
        self.assertEqual(editorial.text_rules(text,self.FACTS,[]),[])  # not a rule: no figure about his work
        payload=editorial.verifier_payload(SimpleNamespace(signals=[],brief={}),{'public_facts':self.FACTS},{},text,[])
        self.assertEqual(len(payload['experience_flags']),1)
        self.assertNotIn('experience_flags',editorial.verifier_payload(SimpleNamespace(signals=[],brief={}),{'public_facts':[]},{},GOOD_POST,[]))


class FlexibleVerifierTests(tae.EditorialAuditBase):
    def test_the_12_11_explanation_beyond_a_confirmed_fact_goes_out(self):
        plan=answers(final=WHY)
        production=review({'issue':'unsourced_figure','severity':'material','quote':EXPLANATION,
                           'detail':'public_facts only says that letting agents communicate loses context. It does not say why.'},
                          unsupported=[EXPLANATION])
        piece=self.plan_with(plan,verificador=[production,production])  # even a verifier that keeps the note
        v=piece.verification
        self.assertEqual((piece.state,v['verdict'],v['blocking_reasons']),('ready','ready_for_execution',[]))
        self.assertEqual(sorted(o['issue'] for o in v['observations']),['unsourced_figure','unsupported_claim'])
        self.assertEqual({f['severity'] for f in v['repair']['findings']},{'blanda'})
        self.assertEqual(v['conteo_reglas'],{'unsourced_figure':{'notas':1,'bloqueos':0},'unsupported_claim':{'notas':1,'bloqueos':0}})
        self.assertIn('post de opinión de LinkedIn',' '.join([s for p,_,s in self.calls if p=='editorial-verificador'][0].split()))
        self.assertTrue(ActionProposal.objects.filter(piece=piece).exists())

    def test_a_fabricated_client_result_still_blocks_after_the_repair(self):
        plan=answers()
        plan['reparacion']=dict(plan['reparacion'],final_text=tae.FIXED)
        invented={'issue':'invented_experience','severity':'material','quote':'Last year a fintech client of mine cut costs',
                  'detail':'Ni el cliente ni el resultado están en public_facts.'}
        piece=self.plan_with(plan,verificador=[review(invented),review(invented)])
        self.assertEqual((piece.state,piece.verification['repair']['outcome']),('blocked','bloqueada'))
        self.assertEqual(piece.verification['blocking_reasons'],['Hallazgo material (invented_experience): Ni el cliente ni el resultado están en public_facts.'])
        self.assertEqual(piece.verification['repair']['findings'][0]['severity'],'dura')
        self.assertEqual(piece.verification['conteo_reglas'],{'invented_experience':{'notas':0,'bloqueos':1}})
        self.assertFalse(ActionProposal.objects.filter(piece=piece).exists())

    def test_an_invented_figure_about_his_work_is_a_rule_and_blocks_if_the_repair_keeps_it(self):
        piece=self.plan_with(answers(final=INVENTED))  # the default repair returns the same text
        self.assertEqual(piece.state,'blocked')
        self.assertTrue(any(r.startswith('Cifra sobre el trabajo de Gustavo') for r in piece.verification['blocking_reasons']))
        self.assertEqual(piece.verification['conteo_reglas'],{'invented_experience':{'notas':0,'bloqueos':1}})
        self.assertNotIn('verificador',self.purposes())

    def test_a_statistic_attributed_to_a_source_not_in_the_evidence_is_repaired_and_never_blocks(self):
        figure={'issue':'unsourced_figure','severity':'material','quote':STAT,'detail':'McKinsey no está en la evidencia.'}
        plan=answers(final=WITH_STAT)
        plan['reparacion']=dict(plan['reparacion'],final_text=SOFTENED,changes=[{'finding':'unsourced_figure','change':'Sin atribución.'}])
        piece=self.plan_with(plan,verificador=[review(figure),dict(answers()['verificador'])])
        self.assertEqual((piece.state,piece.final_text,piece.verification['repair']['outcome']),('ready',SOFTENED,'reparada'))
        self.assertEqual(piece.verification['repair']['resolution'],[{'source':'verificador','issue':'unsourced_figure','resolved':True}])
        self.assertEqual(piece.verification['conteo_reglas'],{'unsourced_figure':{'notas':1,'bloqueos':0}})  # repaired: a note
        self.calls.clear()
        plan['reparacion']=dict(plan['reparacion'],decision='discard',final_text='',rationale='La cifra es el centro.')
        kept=self.plan_with(plan,verificador=[review(figure)])
        self.assertEqual((kept.state,kept.final_text),('ready',WITH_STAT))  # the repair did not happen: it still goes out
        self.assertIn('unsourced_figure',[o['issue'] for o in kept.verification['observations']])
        self.assertEqual(kept.verification['conteo_reglas']['unsourced_figure'],{'notas':1,'bloqueos':0})

    def test_an_approximate_figure_with_its_source_passes_untouched(self):
        found=research.ResearchResult('agents','partial','2026-11-19T12:00:00+00:00',
            (research.Finding('Around 40% of teams that chain agents lose context between steps.',('web:aprox',),'aproximada'),),
            (research.Source('web:aprox','https://techcrunch.com/2026/11/12/agents/','Agents lose context','Agents lose context',
                             '2026-11-19T12:00:00+00:00','search_result',False,'techcrunch.com','November 12, 2026'),),
            (research.APPROXIMATE_NOTE,))
        claim={'text':'Roughly four in ten teams that chain agents lose context.','kind':'web_source','ref':'web:aprox'}
        piece=SimpleNamespace(research=[found.to_dict()],signals=[],brief={})
        approved=review(verdict='ready_for_execution',supported=[(claim['text'],claim['ref'])])
        with patch.object(editorial,'_stage',return_value=(approved,'fake')):
            checked,reasons,rules=editorial._check(piece,{},{},GOOD_POST,[claim],[],[])
        self.assertEqual((reasons,rules,checked.get('source_notes')),([],[],None))
