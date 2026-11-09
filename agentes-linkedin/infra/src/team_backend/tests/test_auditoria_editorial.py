"""Phases 2 and 3 of the AI architecture audit, editorial slice (docs/auditoria-arquitectura-ia.md): deterministic rules
before the verifier (R3), one repair round (R4), results in the director's history, one positioning artifact,
invented_experience against the facts and a model per stage as a setting (C3). Claude is patched: no spend."""
import hashlib
import json
import os
import re
import uuid
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from unittest import SkipTest
from unittest.mock import patch

from django.test import SimpleTestCase
from django.utils import timezone

from team_backend import autopiloto, editorial, guardas, lider, operador, orquestacion, posicionamiento, red
from team_backend.models import ActionExecution, ActionProposal, CycleLedger, EditorialPiece, Opportunity, PostMetric
from team_backend.tests.test_publicacion import GOOD_POST, INVENTED, EditorialBase, answers

FIXED=GOOD_POST.replace('Which decision is your product helping someone make this week?',
                        'Which decision is your product helping someone make this week, and who makes it?')
WITH_LINK=GOOD_POST+'\n\nMore at https://example.com/scoping'
PROJECTAPP_FACT=[{'key':'trayectoria.projectapp','version':1,'fact':'Founder of ProjectApp, a custom software studio.'}]


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


class EditorialAuditBase(EditorialBase):
    def purposes(self,since=0):
        return [c[0].split('-',1)[1] for c in self.calls[since:]]

    def message(self,stage):
        return next(m for p,m,_ in self.calls if p=='editorial-'+stage)

    def sequence(self,plan,**answers_by_call):
        """A plan whose stage answers change per call: {'verificador': [first, second]}."""
        seen={}
        def fake(system,message,max_tokens=None,output_schema=None,effort=None,purpose='agent-run',model=None):
            stage=purpose.split('-',1)[1];self.calls.append((purpose,json.loads(message),system))
            options=answers_by_call.get(stage);index=seen.get(stage,0);seen[stage]=index+1
            answer=options[min(index,len(options)-1)] if options else plan[stage]
            return {'text':json.dumps(answer),'model':model or 'claude-opus-5-5','estimated_usd':0.01,'request_id':'req_'+purpose}
        return patch('knowledge.providers.claude',side_effect=fake)

    def plan_with(self,plan,**answers_by_call):
        with self.sequence(plan,**answers_by_call):
            response=self.human.post('/api/v1/editorial/plan',{},format='json')
            self.assertEqual(response.status_code,202,response.content)
            self.drain()
        return EditorialPiece.objects.get(slot_date=response.json()['slot_date'],origin_job=response.json()['job']['id'])


class RulesBeforeVerifierTests(EditorialAuditBase):
    """R3: length, links, email, phone, pitch, hashtags, private leaks and invented experience run right after the selection."""

    def test_a_rule_issue_is_repaired_before_the_verifier_is_ever_paid(self):
        plan=answers(final=WITH_LINK)
        plan['reparacion']=dict(plan['reparacion'],final_text=GOOD_POST,changes=[{'finding':'Contiene enlaces','change':'Quité el enlace.'}])
        piece=self.plan_with(plan)
        self.assertEqual(self.purposes(),['director','redactor','lectores','seleccion','reparacion','verificador'])
        self.assertEqual(piece.state,'ready')
        repair=piece.verification['repair']
        self.assertEqual((repair['trigger'],repair['outcome'],repair['original_text']),('reglas','reparada',WITH_LINK))
        self.assertEqual(repair['findings'],[{'source':'reglas','issue':'regla','quote':'','detail':'Contiene enlaces'}])
        self.assertIsNone(repair['first_review'])  # the verifier never saw the text with the link
        self.assertEqual((piece.final_text,piece.verification['text_sha256'],piece.verification['rules']),(GOOD_POST,sha(GOOD_POST),[]))
        self.assertEqual(self.message('verificador')['text'],GOOD_POST)
        # The repair stage gets the exact findings, the brief, the text, the memory and Gustavo's voice.
        sent=self.message('reparacion')
        self.assertEqual((sent['text'],sent['findings'][0]['detail'],sent['brief']['thesis']),(WITH_LINK,'Contiene enlaces',plan['director']['thesis']))
        self.assertIn('public_facts',sent);self.assertIn('private_guidance',sent)
        self.assertIn('<tono_de_voz',next(s for p,_,s in self.calls if p=='editorial-reparacion'))
        self.assertEqual([u['stage'] for u in piece.usage],['director','redactor','lectores','seleccion','reparacion','verificador'])
        proposal=ActionProposal.objects.get(piece=piece)
        self.assertEqual(proposal.payload['text'],GOOD_POST)
        self.assertTrue(any(r.startswith('Reparada en una ronda') for r in proposal.risks))
        # The final policy gate still runs every rule and approves the repaired, verified text.
        autopiloto.tick(self.autobot);proposal.refresh_from_db()
        self.assertEqual(proposal.state,'approved')
        detail=self.human.get(f'/api/v1/editorial/pieces/{piece.id}').json()
        self.assertEqual((detail['verification']['repair']['outcome'],detail['final_text'],detail['selection']['final_text']),
                         ('reparada',GOOD_POST,WITH_LINK))

    def test_a_text_still_breaking_a_rule_after_the_repair_is_blocked_without_paying_the_verifier(self):
        plan=answers(final=WITH_LINK)
        plan['reparacion']=dict(plan['reparacion'],final_text=WITH_LINK+' Contact me for details.')
        piece=self.plan_with(plan)
        self.assertNotIn('verificador',self.purposes())
        self.assertEqual(piece.state,'blocked')
        self.assertEqual(piece.verification['repair']['outcome'],'bloqueada')
        self.assertIn('Contiene pitch agresivo o petición de contacto',piece.note)
        self.assertIsNone(piece.verification['model_verdict'])
        self.assertIn('Las reglas de publicación bloquearon',self.notify.call_args.args[0])
        self.assertFalse(ActionProposal.objects.filter(piece=piece).exists())

    def test_without_the_repair_round_a_rule_issue_blocks_at_once(self):
        with patch.dict(os.environ,{'EDITORIAL_REPAIR':'false'}):
            piece=self.plan_with(answers(final=WITH_LINK))
        self.assertEqual(self.purposes(),['director','redactor','lectores','seleccion'])
        self.assertEqual((piece.state,piece.note),('blocked','Contiene enlaces'))
        self.assertNotIn('repair',piece.verification)

    def test_each_guard_runs_once_per_text_inside_the_circuit(self):
        with patch.object(guardas,'private_leaks',wraps=guardas.private_leaks) as leaks,\
             patch.object(guardas,'invented_experience',wraps=guardas.invented_experience) as invented:
            piece=self.plan_with(answers())
        self.assertEqual(piece.state,'ready')
        self.assertEqual((leaks.call_count,invented.call_count),(1,1))  # no second pass after the verifier

    def test_the_rules_are_the_policy_rules(self):
        """Same patterns and limits as autopiloto.post_issues: whatever the circuit flags, the policy flags too."""
        public,private=guardas.blocks()
        texts=[WITH_LINK,GOOD_POST+' Write to me at gustavo@example.com',GOOD_POST+' Call +1 415 555 0100',
               GOOD_POST+' DM me to book a call.',GOOD_POST+' #ai #product #startups #founders','Too short.',
               GOOD_POST.replace('Founders often arrive','Spanish-speaking founders often arrive'),INVENTED]
        for text in texts:
            issues=editorial.text_rules(text,public,private)
            self.assertTrue(issues,text)
            piece=EditorialPiece.objects.create(account=self.official,slot_date=timezone.now().date()-timedelta(days=50+texts.index(text)),
                                                scheduled_for=timezone.now(),state='ready',final_text=text,
                                                verification={'verdict':'ready_for_execution','text_sha256':sha(text)})
            proposal=ActionProposal(account=self.official,piece=piece,capability='CONT-09',payload={'text':text},citations=['x'],source='agent')
            self.assertLessEqual(set(issues),set(autopiloto.post_issues(proposal)),text)
        self.assertEqual(editorial.text_rules(GOOD_POST,public,private),[])


class RepairRoundTests(EditorialAuditBase):
    """R4: one repair pass with the verifier's exact findings, then the rules and the verifier once more."""
    finding={'issue':'unsourced_figure','severity':'material','quote':'cuts costs by 40%','detail':'Figure without a source.'}

    def blocked(self):
        return dict(answers()['verificador'],verdict='blocked',findings=[self.finding])

    def test_a_verifier_finding_is_repaired_and_verified_again(self):
        plan=answers()
        plan['reparacion']=dict(plan['reparacion'],final_text=FIXED,changes=[{'finding':'unsourced_figure','change':'Quité la cifra.'}])
        piece=self.plan_with(plan,verificador=[self.blocked(),plan['verificador']])
        self.assertEqual(self.purposes(),['director','redactor','lectores','seleccion','verificador','reparacion','verificador'])
        self.assertEqual(piece.state,'ready')
        repair=piece.verification['repair']
        self.assertEqual((repair['trigger'],repair['outcome'],repair['original_sha256'],repair['repaired_sha256']),
                         ('verificador','reparada',sha(GOOD_POST),sha(FIXED)))
        self.assertEqual(repair['findings'],[{'source':'verificador','issue':'unsourced_figure','quote':'cuts costs by 40%','detail':'Figure without a source.'}])
        self.assertEqual(repair['first_review']['verdict'],'blocked');self.assertTrue(repair['first_review']['blocking_reasons'])
        self.assertEqual(repair['changes'][0]['change'],'Quité la cifra.')
        self.assertEqual(self.message('reparacion')['findings'],repair['findings'])
        self.assertEqual((piece.final_text,piece.verification['text_sha256'],piece.verification['verdict']),(FIXED,sha(FIXED),'ready_for_execution'))
        self.assertEqual([u['stage'] for u in piece.usage].count('verificador'),2)
        self.assertEqual(ActionProposal.objects.get(piece=piece).payload['text'],FIXED)

    def test_only_one_round_and_a_piece_still_blocked_ends_blocked(self):
        plan=answers()
        plan['reparacion']=dict(plan['reparacion'],final_text=FIXED)
        piece=self.plan_with(plan,verificador=[self.blocked()])
        self.assertEqual(self.purposes().count('reparacion'),1);self.assertEqual(self.purposes().count('verificador'),2)
        self.assertEqual((piece.state,piece.verification['repair']['outcome'],piece.final_text),('blocked','bloqueada',FIXED))
        self.assertIn('unsourced_figure',piece.note)
        self.assertIn('El verificador bloqueó',self.notify.call_args.args[0])

    def test_a_discarded_or_unchanged_repair_keeps_the_original_reasons(self):
        plan=answers()
        plan['reparacion']=dict(plan['reparacion'],decision='discard',final_text='',rationale='La cifra es el centro de la pieza.')
        piece=self.plan_with(plan,verificador=[self.blocked()])
        self.assertEqual(self.purposes().count('verificador'),1)
        self.assertEqual((piece.state,piece.final_text,piece.verification['repair']['outcome']),('blocked',GOOD_POST,'descartada'))
        self.assertIn('Ronda de reparación: la descartó: La cifra es el centro de la pieza.',piece.verification['blocking_reasons'])
        self.assertEqual(piece.verification['text_sha256'],sha(GOOD_POST))

    def test_a_bare_blocked_verdict_gives_the_repair_nothing_to_fix(self):
        piece=self.plan_with(answers(verdict='blocked'))
        self.assertNotIn('reparacion',self.purposes())
        self.assertEqual((piece.state,piece.note),('blocked','El verificador emitió blocked'))

    def test_a_spent_budget_skips_the_repair_and_the_piece_ends_blocked_not_failed(self):
        spent=lambda now=None:Decimal('5') if 'editorial-verificador' in [c[0] for c in self.calls] else Decimal('0')
        with patch.object(editorial,'spent_today',side_effect=spent):
            piece=self.plan_with(answers(),verificador=[self.blocked()])
        self.assertNotIn('reparacion',self.purposes())
        self.assertEqual((piece.state,piece.verification['repair']['outcome']),('blocked','sin_presupuesto'))
        ledger=CycleLedger.objects.get(cycle='pieza_diaria',key=str(piece.id))
        self.assertEqual((ledger.state,ledger.stop_reason,ledger.needs_attention),('stopped','cost_cap',True))
        self.assertEqual(orquestacion.unpack(ledger.progress_ledger['result']).pk,piece.pk)
        self.assertIn('Ronda de reparación: sin presupuesto editorial para repararla hoy',piece.note)
        self.assertFalse(editorial.budget_retry([piece],timezone.now()+timedelta(days=1)))  # a content block is not retried

    def test_a_budget_stop_before_the_second_verification_keeps_the_original_text(self):
        plan=answers();plan['reparacion']=dict(plan['reparacion'],final_text=FIXED)
        spent=lambda now=None:Decimal('5') if 'editorial-reparacion' in [c[0] for c in self.calls] else Decimal('0')
        with patch.object(editorial,'spent_today',side_effect=spent):
            piece=self.plan_with(plan,verificador=[self.blocked()])
        repair=piece.verification['repair']
        self.assertEqual((piece.state,repair['outcome'],repair['repaired_text'],piece.final_text),('blocked','sin_presupuesto',FIXED,GOOD_POST))
        self.assertEqual(piece.verification['text_sha256'],sha(GOOD_POST))
        ledger=CycleLedger.objects.get(cycle='pieza_diaria',key=str(piece.id))
        self.assertEqual((ledger.state,ledger.stop_reason),('stopped','cost_cap'))
        self.assertEqual(orquestacion.unpack(ledger.progress_ledger['result']).pk,piece.pk)
        self.assertEqual(self.purposes().count('verificador'),1)


class DirectorResultsTests(EditorialAuditBase):
    """The director's history carries the 72 h and 7 d results of published pieces and a 30-day summary."""

    def publish(self,days_ago,pillar,modality,cuts=None,thesis='Tesis'):
        now=timezone.now();when=now-timedelta(days=days_ago)
        piece=EditorialPiece.objects.create(account=self.official,slot_date=when.astimezone(operador.local_tz()).date(),scheduled_for=when,
            state='ready',final_text=f'{thesis} {days_ago}',brief={'pillar':pillar,'modality':modality,'thesis':f'{thesis} {days_ago}'})
        proposal=ActionProposal.objects.create(account=self.official,piece=piece,capability='CONT-09',payload={'text':piece.final_text},
                                               payload_hash='0'*64,state='confirmed')
        ActionExecution.objects.create(proposal=proposal,idempotency_key=uuid.uuid4().hex,provider='linkedin_fake',state='confirmed',
                                       executed_by=self.gustavo,started_at=when)
        for kind,values in (cuts or {}).items():
            PostMetric.objects.create(piece=piece,kind=kind,published_at=when,captured_at=when+timedelta(days=1),**values)
        return piece

    def test_published_results_reach_the_director_and_missing_data_is_never_zero(self):
        self.publish(9,'applied_ai','personal_startups',{'72h':{'impressions':400,'reactions':10,'comments':2,'reposts':1,
            'commenters':[{'provider_user_id':'a','substantive':True},{'provider_user_id':'b','substantive':False}]},
            '7d':{'impressions':600,'reactions':None,'comments':3,'reposts':None}})
        self.publish(8,'applied_ai','projectapp',{'72h':{'impressions':200,'reactions':4,'comments':None,'reposts':0}})
        self.publish(1,'business_to_product','personal_startups')  # too young for any cut
        self.publish(12,'architecture_delivery','comunidad')           # old enough, never measured
        self.publish(45,'applied_ai','alianzas',{'72h':{'impressions':9000,'reactions':1,'comments':1,'reposts':1}})  # outside 30 days
        self.plan_with(answers(decision='skip'))
        sent=self.message('director')
        rows={r['date']:r for r in sent['history']}
        first=next(r for r in sent['history'] if r['thesis']=='Tesis 9')
        self.assertEqual(first['results']['72h'],{'impressions':400,'reactions':10,'comments':2,'reposts':1,'substantive_comments':1,'engagement_pct':3.25})
        self.assertEqual(first['results']['7d'],{'impressions':600,'reactions':None,'comments':3,'reposts':None,'substantive_comments':None,'engagement_pct':None})
        second=next(r for r in sent['history'] if r['thesis']=='Tesis 8')
        self.assertEqual((second['results']['72h']['comments'],second['results']['7d']),(None,'sin_dato'))
        young=next(r for r in sent['history'] if r['thesis']=='Tesis 1')
        self.assertEqual(young['results'],{'72h':'pendiente','7d':'pendiente'})
        never=next(r for r in sent['history'] if r['thesis']=='Tesis 12')
        self.assertEqual(never['results'],{'72h':'sin_dato','7d':'sin_dato'})
        self.assertEqual(len(rows),5)
        performance=sent['performance_30d']
        self.assertEqual((performance['days'],performance['all']['published']),(30,4))
        self.assertEqual(performance['all']['72h'],{'measured':2,'median_impressions':300,'median_reactions':7,'median_comments':2})
        applied=performance['by_pillar']['applied_ai']
        self.assertEqual((applied['published'],applied['72h']['measured'],applied['7d']['measured']),(2,2,1))
        self.assertEqual(applied['7d'],{'measured':1,'median_impressions':600,'median_reactions':None,'median_comments':3})
        self.assertEqual(performance['by_pillar']['architecture_delivery']['72h'],
                         {'measured':0,'median_impressions':None,'median_reactions':None,'median_comments':None})
        self.assertEqual(set(performance['by_modality']),{'personal_startups','projectapp','comunidad'})
        self.assertNotIn('alianzas',performance['by_modality'])
        self.assertIn('performance_30d',editorial.DIRECTOR_SYSTEM);self.assertIn('nunca un cero',editorial.DIRECTOR_SYSTEM)

    def test_unpublished_pieces_carry_no_results(self):
        piece=self.publish(3,'applied_ai','projectapp')
        ActionProposal.objects.filter(piece=piece).update(state='rejected')
        self.plan_with(answers(decision='skip'))
        row=next(r for r in self.message('director')['history'] if r['thesis']=='Tesis 3')
        self.assertEqual(row['status'],'vetoed');self.assertNotIn('results',row)
        self.assertEqual(self.message('director')['performance_30d']['all']['published'],0)


class PositioningTests(EditorialAuditBase):
    """One versioned positioning source; stored modality values keep their vocabularies."""

    def test_the_three_agents_derive_from_the_same_source(self):
        self.assertIn(posicionamiento.editorial_direction(),editorial.DIRECTION)
        self.assertIn(posicionamiento.network_criteria(),red.CLASSIFY_SYSTEM)
        self.assertEqual(lider.CRITERIA_DEL_BARRIO,posicionamiento.lead_criteria())
        for text in (editorial.DIRECTION,red.CLASSIFY_SYSTEM,lider.CRITERIA_DEL_BARRIO):
            self.assertIn(posicionamiento.IDENTITY,text)
        self.assertIn(posicionamiento.VERSION,editorial.DIRECTION);self.assertIn(posicionamiento.VERSION,red.CLASSIFY_SYSTEM)
        for stage in ('director','redactor','seleccion','reparacion'):self.assertIn(posicionamiento.editorial_direction(),editorial.STAGES[stage][0])

    def test_stored_vocabularies_are_unchanged_and_mapped(self):
        self.assertEqual(editorial.MODALITIES,['personal_startups','projectapp','alianzas','comunidad'])
        self.assertEqual(editorial.BRIEF_SCHEMA['properties']['modality']['enum'],editorial.MODALITIES)
        self.assertEqual(red.MODALITIES,posicionamiento.modalities('red'))
        self.assertEqual(red.CLASSIFY_SCHEMA['properties']['contacts']['items']['properties']['modality']['enum'],posicionamiento.modalities('red'))
        self.assertEqual(Opportunity.Modality.values,posicionamiento.modalities('oportunidades')+[posicionamiento.UNKNOWN['oportunidades']])
        self.assertEqual(editorial.PILLARS,editorial.BRIEF_SCHEMA['properties']['pillar']['enum'])
        self.assertEqual(posicionamiento.to_stored('red','comunidad'),'comunidad_autoridad')
        self.assertEqual(posicionamiento.to_canonical('red','comunidad_autoridad'),'comunidad')
        self.assertEqual(posicionamiento.to_canonical('editorial','comunidad'),'comunidad')
        self.assertEqual(posicionamiento.to_stored('oportunidades','alianzas'),'por_clasificar')
        self.assertIsNone(posicionamiento.to_canonical('oportunidades','por_clasificar'))
        for domain,mapping in posicionamiento.VOCABULARIES.items():
            self.assertLessEqual(set(mapping),set(posicionamiento.MODALITIES),domain)

    def test_the_pwa_has_a_label_for_every_stored_value(self):
        root=Path(__file__).resolve().parents[5]/'oficina'/'src'
        if not root.exists():raise SkipTest('oficina/ no está en este árbol')
        def keys(path,table):
            # Follow `export * from '…'` re-exports: shared tables live in compartido/ (used by the PWA and the app).
            file=(root/path).resolve()
            for _ in range(3):
                source=file.read_text(encoding='utf-8')
                found=re.search(table+r'[^=]*=\s*\{(.*?)\n\};',source,re.S)
                if found:return set(re.findall(r'^\s*([a-z_]+):',found.group(1),re.M))
                again=re.search(r"export \* from '([^']+)'",source)
                if not again:break
                file=(file.parent/again.group(1)).with_suffix('.ts').resolve()
            self.fail(f'{table} no está en {path} ni en lo que reexporta')
        self.assertLessEqual(set(posicionamiento.modalities('editorial')),keys('lib/editorial.ts','MODALITY_LABEL'))
        self.assertLessEqual(set(posicionamiento.modalities('red')),keys('lib/format.ts','CONTACT_MODALITY_LABEL'))
        self.assertLessEqual(set(posicionamiento.modalities('red')),keys('pages/personas/labels.ts','MODALITY_SHORT'))
        self.assertEqual(set(Opportunity.Modality.values),keys('pages/personas/labels.ts','OPPORTUNITY_MODALITY_LABEL'))

    def test_the_brief_records_the_positioning_version(self):
        piece=self.plan_with(answers(decision='skip'))
        self.assertEqual(piece.brief['positioning_version'],posicionamiento.VERSION)


class InventedExperienceTests(SimpleTestCase):
    """invented_experience compares each first-person claim with the confirmed public facts instead of turning off."""

    def test_without_facts_any_first_person_experience_is_invented(self):
        reasons=guardas.invented_experience(INVENTED,[])
        self.assertEqual(reasons,['Atribuye experiencia a Gustavo sin hechos públicos confirmados («Last year I»)'])
        self.assertEqual(guardas.invented_experience(GOOD_POST,[]),[])

    def test_a_single_unrelated_fact_no_longer_turns_the_rule_off(self):
        reasons=guardas.invented_experience(INVENTED,PROJECTAPP_FACT)
        self.assertEqual(len(reasons),1);self.assertIn('«40»',reasons[0]);self.assertIn('no consta en sus hechos públicos',reasons[0])
        story='I rebuilt a payments ledger for a regional bank. It taught me to start from the audit trail.'
        self.assertEqual(guardas.invented_experience(story,PROJECTAPP_FACT),
                         ['Atribuye a Gustavo una experiencia que no consta en sus hechos públicos («I rebuilt a payments ledger for a regional bank.»)'])
        self.assertTrue(guardas.invented_experience('Uy, construí algo parecido y no jsjs.',PROJECTAPP_FACT))

    def test_claims_backed_by_the_facts_pass(self):
        self.assertEqual(guardas.invented_experience('At ProjectApp, my team learned to scope from the decision first.',PROJECTAPP_FACT),[])
        spanish=[{'key':'trayectoria.estudio','version':1,'fact':'Fundador de un estudio de software a la medida.'}]
        self.assertEqual(guardas.invented_experience('My team scopes every feature from the decision it supports.',spanish),[])
        self.assertEqual(guardas.invented_experience('En mi empresa empezamos siempre por la decisión.',PROJECTAPP_FACT),[])
        twelve=[{'key':'historia.inicio','version':1,'fact':'Empezó a programar a los 12 años.'}]
        self.assertEqual(guardas.invented_experience('I built my first game at 12.',twelve),[])
        self.assertTrue(guardas.invented_experience('I built my first game at 14.',twelve))
        self.assertEqual(guardas.invented_experience(GOOD_POST,PROJECTAPP_FACT),[])

    def test_each_unsupported_claim_is_quoted_up_to_a_limit(self):
        text='\n'.join(['I migrated a hospital to Kubernetes.','We launched a crypto exchange.','I hired twelve engineers in Lisbon.',
                        'I closed a seed round.'])
        reasons=guardas.invented_experience(text,PROJECTAPP_FACT)
        self.assertEqual(len(reasons),guardas.MAX_CLAIMS);self.assertIn('Kubernetes',reasons[0])


class StageModelTests(EditorialAuditBase):
    """C3: a model per editorial stage is a setting; the default does not change."""

    def test_by_default_no_stage_overrides_the_model(self):
        self.assertEqual({name:editorial.stage_model(name) for name in editorial.STAGES},dict.fromkeys(editorial.STAGES))
        models=[]
        def fake(system,message,max_tokens=None,output_schema=None,effort=None,purpose='agent-run',**kwargs):
            models.append(kwargs.get('model','default'));return {'text':json.dumps(answers()[purpose.split('-',1)[1]]),'model':'claude-opus-5-5'}
        with patch('knowledge.providers.claude',side_effect=fake):
            self.assertEqual(self.human.post('/api/v1/editorial/plan',{},format='json').status_code,202);self.drain()
        self.assertEqual(models,['default']*5)

    def test_a_stage_override_reaches_only_that_stage_and_the_repair_follows_the_selection(self):
        env={'EDITORIAL_MODEL_LECTORES':'claude-sonnet-5-5','EDITORIAL_MODEL_SELECCION':'claude-sonnet-5-5'}
        seen={}
        def fake(system,message,max_tokens=None,output_schema=None,effort=None,purpose='agent-run',model=None):
            stage=purpose.split('-',1)[1];seen[stage]=model
            return {'text':json.dumps(answers()[stage]),'model':model or 'claude-opus-5-5','estimated_usd':0.01}
        with patch.dict(os.environ,env),patch('knowledge.providers.claude',side_effect=fake):
            self.assertEqual(self.human.post('/api/v1/editorial/plan',{},format='json').status_code,202);self.drain()
            self.assertEqual(editorial.stage_model('reparacion'),'claude-sonnet-5-5')
        self.assertEqual(seen,{'director':None,'redactor':None,'lectores':'claude-sonnet-5-5','seleccion':'claude-sonnet-5-5','verificador':None})
        piece=EditorialPiece.objects.get()
        self.assertEqual({u['stage']:u['model'] for u in piece.usage}['lectores'],'claude-sonnet-5-5')

    def test_an_override_without_a_verified_price_fails_before_any_spend(self):
        with patch.dict(os.environ,{'EDITORIAL_MODEL_VERIFICADOR':'modelo-inventado'}):
            piece=self.plan_with(answers())
        self.assertEqual(self.calls,[])
        self.assertEqual(piece.state,'failed');self.assertIn('EDITORIAL_MODEL_VERIFICADOR=modelo-inventado',piece.note)
