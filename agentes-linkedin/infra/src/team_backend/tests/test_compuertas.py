"""Gates that can stop a piece (docs/compuertas.md): severity, the scoped second review, the second attempt of the day and
the offline replay. Claude is patched: no spend. The privacy and invented-experience blocks stay covered by the
unchanged tests in test_publicacion and test_auditoria_editorial; here they are checked once more through the severity."""
import hashlib
import json
import os
from datetime import timedelta
from unittest.mock import patch

from django.test import SimpleTestCase
from django.utils import timezone

from team_backend import autopiloto, compuertas, editorial, evaluaciones, jobs, operador
from team_backend.models import ActionProposal, EditorialPiece, Job, ObservedPost
from team_backend.tests import test_auditoria_editorial as tae
from team_backend.tests import test_auditoria_lider as tal
from team_backend.tests import test_evaluaciones as te
from team_backend.tests import test_rediseno as tr
from team_backend.tests.test_publicacion import GOOD_POST, EditorialBase, answers

SOFT={'issue':'hook_not_delivered','severity':'material','quote':'Which decision','detail':'The hook promises more than the close.'}
HARD={'issue':'invented_experience','severity':'material','quote':'I thought scoping was easy','detail':'Not in public_facts.'}
MINOR={'issue':'other','severity':'minor','quote':'','detail':'Could be shorter.'}


def review(*findings,verdict='blocked',unsupported=()):
    return {'verdict':verdict,'findings':list(findings),
            'checked_claims':[{'text':t,'status':'unsupported','ref':''} for t in unsupported],'summary':'','citations':[]}


class SeverityTests(SimpleTestCase):
    def test_hard_findings_block_soft_ones_become_observations_and_minor_never_counts(self):
        reasons,soft=compuertas.split(review(SOFT,HARD,MINOR))
        self.assertEqual(reasons,['Hallazgo material (invented_experience): Not in public_facts.'])
        self.assertEqual(soft,[{'issue':'hook_not_delivered','quote':'Which decision','detail':'The hook promises more than the close.'}])
        self.assertEqual(compuertas.split(review(SOFT)),([],[soft[0]]))
        self.assertEqual(compuertas.split(review(unsupported=['Most founders fail']))[0],['Afirmación sin respaldo: Most founders fail'])

    def test_a_bare_blocked_verdict_is_hard_and_a_ready_one_is_clean(self):
        self.assertEqual(compuertas.split(review()),(['El verificador emitió blocked'],[]))
        self.assertEqual(compuertas.split(review(MINOR,verdict='ready_for_execution')),([],[]))

    def test_every_safety_issue_is_hard_and_pitch_depends_on_the_policy(self):
        for issue in ('invented_experience','unsourced_figure','private_data','private_guidance_leak','unsupported_claim','aggressive_pitch'):
            self.assertEqual(compuertas.severity(issue),'dura',issue)
        for issue in ('hook_not_delivered','off_brief','other'):self.assertEqual(compuertas.severity(issue),'blanda',issue)
        self.assertEqual(compuertas.severity('aggressive_pitch',{'cta_max':1}),'blanda')
        self.assertEqual(compuertas.severity('invented_experience',{'cta_max':1}),'dura')
        with patch.dict(os.environ,{'COMPUERTAS_DURAS':'other'}):self.assertEqual(compuertas.severity('other'),'dura')

    def test_the_strategys_findings_follow_the_one_table_and_never_hide_a_bare_blocked_verdict(self):
        lines=['cta_count: 2 llamadas a la acción; una venta lleva una sola','fabricated_quote: «x» no aparece en las fuentes']
        self.assertEqual(compuertas.strategy_split(lines),([lines[1]],[lines[0]]))
        with patch.dict(os.environ,{'COMPUERTAS_DURAS':'cta_count'}):self.assertEqual(compuertas.strategy_split(lines),(lines,[]))
        found={'issue':'cta_count','quote':'','detail':'2 llamadas a la acción; una venta lleva una sola'}
        ready=compuertas.with_code_findings(review(verdict='ready_for_execution'),lines[:1])
        self.assertEqual(ready['findings'],[dict(found,severity='material',by=compuertas.BY_CODE)])
        self.assertEqual(compuertas.split(ready,{'cta_max':1}),([],[found]))  # soft: repaired, else an observation
        self.assertEqual(compuertas.split(compuertas.with_code_findings(review(),lines[:1]))[0],['El verificador emitió blocked'])
        model=review({'issue':'cta_count','severity':'material','quote':'q','detail':'d'},verdict='ready_for_execution')
        self.assertEqual(len(compuertas.with_code_findings(model,lines[:1])['findings']),1)  # one the model flagged is not doubled

    def test_the_default_policy_forbids_any_contact_request_and_a_post_type_may_allow_one(self):
        dm=GOOD_POST+' DM me if you want the checklist.';sell=GOOD_POST+' Book a call this week.'
        pitch='Contiene pitch agresivo o petición de contacto'
        self.assertIn(pitch,compuertas.form_rules(dm));self.assertIn(pitch,compuertas.form_rules(sell))
        self.assertNotIn(pitch,compuertas.form_rules(dm,{'cta_max':1}))
        self.assertIn(pitch,compuertas.form_rules(sell,{'cta_max':1}))  # hard selling never passes
        self.assertIn(pitch,compuertas.form_rules(dm+' Or message me.',{'cta_max':1}))  # one invitation, not two
        self.assertEqual(compuertas.form_rules(GOOD_POST),[])
        piece=EditorialPiece(brief={'gate_policy':{'cta_max':5}})
        self.assertEqual((compuertas.gate_policy(piece),compuertas.gate_policy(EditorialPiece(brief={}))),({'cta_max':1},{'cta_max':0}))
        self.assertFalse(compuertas.custom(compuertas.gate_policy(None)))

    def test_the_pitch_pattern_is_unchanged_for_everything_else(self):
        for text in ('hire me','dm me','message me','contact me','book a call','schedule a call','link in bio','reach out to me',
                     'send me a message','limited spots','sign up now','buy now','contrátame','escríbeme','agendamos una llamada','contáctame'):
            self.assertTrue(autopiloto.POST_PITCH.search(text),text)
            self.assertTrue(compuertas.pitch(text),text)

    def test_stop_reasons_become_categories_without_their_quotes(self):
        cases={'Hallazgo material (unsourced_figure): cuts costs by 40%':'unsourced_figure','Afirmación sin respaldo: X':'unsupported_claim',
               'El verificador emitió blocked':'veredicto_sin_hallazgos','Contiene enlaces':'enlaces',
               'Atribuye experiencia a Gustavo sin hechos públicos confirmados («I built»)':'invented_experience',
               'Deja traslucir orientación privada de Gustavo (prioridades, segmento o condiciones)':'private_guidance_leak',
               'Líder: no aporta una idea concreta (aporta=0.3)':'aporta','Prefiltro: es una promoción pura (promocion=0.9)':'promocion',
               'Ronda de reparación: la descartó: la cifra es el centro':'reparacion_descartada','algo nuevo':'otro'}
        for reason,expected in cases.items():self.assertEqual(compuertas.category(reason),expected,reason)


class SecondReviewTests(tae.EditorialAuditBase):
    """The one repair round, then a second review that only blocks on hard findings."""

    def soft(self):
        return dict(answers()['verificador'],verdict='blocked',findings=[SOFT])

    def test_a_soft_finding_still_open_after_the_repair_goes_out_as_an_observation(self):
        plan=answers()
        plan['reparacion']=dict(plan['reparacion'],final_text=tae.FIXED,changes=[{'finding':'hook_not_delivered','change':'Sharper close.'}])
        piece=self.plan_with(plan,verificador=[self.soft(),self.soft()])
        self.assertEqual(self.purposes(),['director','redactor','lectores','seleccion','verificador','reparacion','verificador'])
        self.assertNotIn('previous_attempts',self.message('director'))  # a first attempt reads what it always read
        v=piece.verification
        self.assertEqual((piece.state,piece.final_text,v['verdict'],v['model_verdict'],v['blocking_reasons']),
                         ('ready',tae.FIXED,'ready_for_execution','blocked',[]))
        self.assertEqual(v['observations'],[{'issue':'hook_not_delivered','quote':SOFT['quote'],'detail':SOFT['detail']}])
        self.assertEqual((v['repair']['outcome'],v['repair']['resolution']),
                         ('reparada',[{'source':'verificador','issue':'hook_not_delivered','resolved':False}]))
        self.assertEqual(v['day_attempt'],{'number':1,'of':2})
        self.assertEqual(set(v['context']),{'public_facts','private_guidance','orientation'})
        first,second=[m for p,m,_ in self.calls if p=='editorial-verificador']
        self.assertNotIn('second_review',first)
        self.assertEqual(second['second_review']['previous_findings'],[{'source':'verificador','issue':'hook_not_delivered',
                                                                       'quote':SOFT['quote'],'detail':SOFT['detail']}])
        self.assertEqual(second['second_review']['changes'],[{'finding':'hook_not_delivered','change':'Sharper close.'}])
        self.assertNotIn('gate_policy',second)  # the default policy is never sent
        proposal=ActionProposal.objects.get(piece=piece)
        self.assertIn(f'Conservada como observación (hook_not_delivered): {SOFT["detail"]}',proposal.risks)
        autopiloto.tick(self.autobot);proposal.refresh_from_db()
        self.assertEqual(proposal.state,'approved')  # the final policy gate trusts the settled verdict on this exact text

    def test_without_the_repair_round_a_soft_finding_does_not_stop_the_piece(self):
        with patch.dict(os.environ,{'EDITORIAL_REPAIR':'false'}):
            piece=self.plan_with(answers(),verificador=[self.soft()])
        self.assertNotIn('reparacion',self.purposes())
        self.assertEqual((piece.state,piece.verification['observations'][0]['issue']),('ready','hook_not_delivered'))

    def test_a_discarded_repair_of_a_soft_finding_keeps_the_original_text(self):
        plan=answers();plan['reparacion']=dict(plan['reparacion'],decision='discard',final_text='',rationale='The close is the point.')
        piece=self.plan_with(plan,verificador=[self.soft()])
        self.assertEqual((piece.state,piece.final_text,piece.verification['repair']['outcome']),('ready',GOOD_POST,'descartada'))
        self.assertEqual(piece.verification['text_sha256'],hashlib.sha256(GOOD_POST.encode()).hexdigest())

    def test_a_hard_problem_at_the_second_review_still_blocks(self):
        plan=answers();plan['reparacion']=dict(plan['reparacion'],final_text=tae.FIXED)
        hard=dict(answers()['verificador'],verdict='blocked',findings=[HARD])
        piece=self.plan_with(plan,verificador=[self.soft(),hard])
        self.assertEqual((piece.state,piece.verification['repair']['outcome']),('blocked','bloqueada'))
        self.assertIn('invented_experience',piece.note)
        self.assertEqual(piece.verification['observations'],[])
        self.assertFalse(ActionProposal.objects.filter(piece=piece).exists())

    def test_a_resolved_finding_is_recorded_as_resolved(self):
        plan=answers();plan['reparacion']=dict(plan['reparacion'],final_text=tae.FIXED)
        piece=self.plan_with(plan,verificador=[dict(answers()['verificador'],verdict='blocked',findings=[tae.RepairRoundTests.finding]),
                                               plan['verificador']])
        self.assertEqual(piece.verification['repair']['resolution'],[{'source':'verificador','issue':'unsourced_figure','resolved':True}])

    def test_the_eval_second_review_is_the_production_second_review(self):
        plan=answers()
        plan['reparacion']=dict(plan['reparacion'],final_text=tae.FIXED,changes=[{'finding':'hook_not_delivered','change':'Sharper close.'}])
        piece=self.plan_with(plan,verificador=[self.soft(),plan['verificador']])
        data,system=[(m,s) for p,m,s in self.calls if p=='editorial-verificador'][1]
        repair=piece.verification['repair']
        second={'previous_findings':[{k:f.get(k) for k in ('source','issue','quote','detail')} for f in repair['findings']],
                'changes':repair['changes']}
        request=evaluaciones.verifier_request(evaluaciones.Run(None),piece,tae.FIXED,plan['reparacion']['claims'],second)
        self.assertEqual((json.loads(request['message']),request['system']),(data,system))

    def test_a_post_type_policy_reaches_the_verifier_and_the_final_gate(self):
        text=GOOD_POST+' DM me if you want the checklist.'
        piece=EditorialPiece.objects.create(account=self.official,slot_date=timezone.now().date()-timedelta(days=60),scheduled_for=timezone.now(),
            state='ready',final_text=text,brief={'gate_policy':{'cta_max':1}},
            verification={'verdict':'ready_for_execution','text_sha256':hashlib.sha256(text.encode()).hexdigest()})
        proposal=ActionProposal(account=self.official,piece=piece,capability='CONT-09',payload={'text':text},citations=['x'],source='agent')
        self.assertNotIn('Contiene pitch agresivo o petición de contacto',autopiloto.post_issues(proposal))
        piece.brief={};piece.save(update_fields=['brief'])
        self.assertIn('Contiene pitch agresivo o petición de contacto',autopiloto.post_issues(proposal))
        piece.brief={'gate_policy':{'cta_max':1}}
        payload=editorial.verifier_payload(piece,{'public_facts':[]},{},text,[])
        self.assertEqual(payload['gate_policy'],{'cta_max':1})


class SecondAttemptTests(EditorialBase):
    """A day a content gate blocked gets one more attempt while there is time; money, failures and his reworks do not."""

    def blocked(self,slot,created,**fields):
        values=dict(state='blocked',note='Hallazgo material (unsourced_figure): Needs a source.',
                    verification={'verdict':'blocked','blocking_reasons':['Hallazgo material (unsourced_figure): Needs a source.']},
                    brief={'thesis':'Scope from the decision.','pillar':'business_to_product','approach':'LI-05-M001-K02'})
        values.update(fields)
        piece=EditorialPiece.objects.create(account=self.official,slot_date=slot,scheduled_for=editorial.scheduled_for(slot),**values)
        EditorialPiece.objects.filter(pk=piece.pk).update(created_at=created)
        piece.refresh_from_db()
        return piece

    def tomorrow(self):
        today=timezone.now().astimezone(operador.local_tz()).date()
        slot=today+timedelta(days=1)
        return slot,editorial.scheduled_for(slot)

    def test_a_day_a_gate_blocked_gets_one_more_attempt_while_there_is_time(self):
        slot,when=self.tomorrow();now=when-timedelta(hours=3)
        first=self.blocked(slot,now-timedelta(hours=1))
        self.assertTrue(compuertas.gate_blocked(first))
        self.assertEqual(editorial.next_slot(now),slot)
        self.assertIsNone(editorial.next_slot(when-timedelta(minutes=60)))  # too close to its hour
        with patch.dict(os.environ,{'EDITORIAL_DAY_ATTEMPTS':'1'}):self.assertIsNone(editorial.next_slot(now))
        second=self.blocked(slot,now-timedelta(minutes=30))
        self.assertEqual((compuertas.attempt_number(first),compuertas.attempt_number(second)),(1,2))
        self.assertIsNone(editorial.next_slot(now))  # two attempts: the day ends here

    def test_money_stops_failures_and_his_reworks_are_not_content_attempts(self):
        slot,when=self.tomorrow();now=when-timedelta(hours=3)
        for fields in ({'note':editorial.BUDGET_STOP+' (AI_DAILY_FUSE_USD); se reanuda cuando haya presupuesto.'},
                       {'note':'Ciclo detenido: uncertain'},{'note':'No se pudo aplicar el comentario de Gustavo: x'},
                       {'state':'failed','note':'Error interno en la preparación; no se repite el gasto.'},
                       {'state':'skipped','note':'No genuine material today.'}):
            piece=self.blocked(slot,now-timedelta(hours=1),**fields)
            self.assertFalse(compuertas.gate_blocked(piece),fields)
            self.assertIsNone(editorial.next_slot(now),fields)
            piece.delete()

    def test_an_extra_post_he_asked_for_is_never_the_days_attempt_and_never_holds_it(self):
        """The weekly strategy's extra post (second_of_day) sits next to the daily one: it is not an attempt of the daily
        post, an open one or its queued job does not hold the daily post, and the daily post still gets exactly one more."""
        slot,when=self.tomorrow();now=when-timedelta(hours=3)
        extra=self.blocked(slot,now-timedelta(hours=2),second_of_day=True)
        self.assertEqual(editorial.next_slot(now),slot)  # only his extra post so far: the daily post is still due
        first=self.blocked(slot,now-timedelta(hours=1))
        self.assertEqual(compuertas.attempt_number(first),1)
        self.assertEqual(editorial.next_slot(now),slot)  # its one second attempt
        EditorialPiece.objects.filter(pk=extra.pk).update(state='ready')
        jobs.enqueue_operation(self.gustavo,'prepare_piece',{'slot':slot.isoformat(),'extra':True})
        self.assertEqual(editorial.next_slot(now),slot)  # an open extra post or its job does not hold the daily one
        self.blocked(slot,now-timedelta(minutes=30))
        self.assertIsNone(editorial.next_slot(now))  # two daily attempts: the day ends here
        with patch.dict(os.environ,{'OPERATOR_AUTOPILOT':'true'}):
            self.assertFalse(compuertas.retry_left(extra,now))  # an extra post is never retried

    def test_the_second_attempt_tells_the_director_why_the_first_stopped(self):
        slot=editorial.next_slot(manual=True)
        self.blocked(slot,timezone.now()-timedelta(hours=1))
        piece=self.plan(answers())
        self.assertEqual(piece.slot_date,slot)
        director=self.calls[0][1]
        self.assertEqual(director['previous_attempts'],[{'thesis':'Scope from the decision.','pillar':'business_to_product',
            'approach':'LI-05-M001-K02','blocked_by':'texto','categories':['unsourced_figure'],
            'reasons':['Hallazgo material (unsourced_figure): Needs a source.']}])
        self.assertEqual(piece.verification['day_attempt'],{'number':2,'of':2})

    def test_only_the_autopilot_announces_a_second_attempt(self):
        slot,when=self.tomorrow()
        piece=self.blocked(slot,timezone.now(),state='preparing',note='')
        now=when-timedelta(hours=3)
        with patch.dict(os.environ,{'OPERATOR_AUTOPILOT':'false'}):self.assertFalse(compuertas.retry_left(piece,now))
        with patch.dict(os.environ,{'OPERATOR_AUTOPILOT':'true'}):
            self.assertTrue(compuertas.retry_left(piece,now))
            self.assertFalse(compuertas.retry_left(piece,when-timedelta(minutes=30)))


class ReplayTests(te.EvalBase):
    """evaluar replays the post gate offline on what each piece stored: no model is called."""

    def stored(self,piece,*findings,**extra):
        verification=dict(piece.verification,findings=list(findings),**extra)
        EditorialPiece.objects.filter(pk=piece.pk).update(verification=verification)
        return str(piece.id)

    def test_the_offline_replay_reuses_the_stored_findings_with_the_current_severity(self):
        soft=self.stored(self.piece(state='blocked',model_verdict='blocked'),SOFT)
        hard=self.stored(self.piece(state='blocked',model_verdict='blocked'),HARD)
        dismissed=self.stored(self.piece(state='blocked',model_verdict='blocked'),SOFT,override={'text_sha256':'x'})
        self.piece(fate='confirmed');self.piece(fate='rejected')
        with patch('knowledge.providers.claude',side_effect=te.forbidden),patch('knowledge.providers.typesafe',side_effect=te.forbidden):
            report=evaluaciones.evaluate(['verificador'])
        replay=report['repeticion_compuertas']
        self.assertEqual((replay['casos'],replay['sin_repeticion_sin_pagar']),(5,0))
        self.assertEqual(sorted(r['id'] for r in replay['bloqueadas_que_ahora_pasan']),sorted([soft,dismissed]))
        self.assertEqual({r['observaciones'][0] for r in replay['bloqueadas_que_ahora_pasan']},{'hook_not_delivered'})
        self.assertEqual(replay['duras_que_siguen_bloqueando'],{'aciertos':1,'total':1,'pct':100.0})
        self.assertEqual(replay['pasaron_y_siguen_pasando'],{'aciertos':2,'total':2,'pct':100.0})
        self.assertEqual(replay['etiquetas_de_gustavo'],{'desestimo_bloqueo':{'casos':1,'ahora_pasan':1},'vetada':{'casos':1,'ahora_pasan':1}})
        self.assertEqual(next(r for r in replay['filas'] if r['id']==hard)['duras'],['invented_experience'])
        text=evaluaciones.render(report)
        self.assertIn('Repetición de la compuerta del post',text);self.assertIn('Bloqueadas que ahora pasan: 2',text)
        self.assertNotIn(SOFT['detail'],json.dumps(replay))  # ids and categories only


class AuditTests(EditorialBase):
    """compuertas auditar: per gate, days without a post and Gustavo's word, from what is stored; ids and categories only."""

    def piece(self,days_ago,verification,state='blocked',note='',published=False):
        tz=operador.local_tz();now=timezone.now()
        piece=EditorialPiece.objects.create(account=self.official,slot_date=(now-timedelta(days=days_ago)).astimezone(tz).date(),
            scheduled_for=now-timedelta(days=days_ago),state=state,note=note,final_text=GOOD_POST,verification=verification)
        if published:
            proposal=operador.create_proposal(self.gustavo,None,'CONT-09',{'text':GOOD_POST},citations=['x'],source='agent',piece=piece)
            ActionProposal.objects.filter(pk=proposal.pk).update(state='confirmed',approved_hash=proposal.payload_hash,decided_at=now)
        return piece

    def history(self):
        from team_backend.models import AuditEvent
        hard='Hallazgo material (unsourced_figure): Needs a source.'
        blocked=self.piece(3,{'verdict':'blocked','model_verdict':'blocked','blocking_reasons':[hard],'rules':[]},note=hard)
        repaired=self.piece(4,{'verdict':'ready_for_execution','model_verdict':'blocked','blocking_reasons':[],'rules':[],
                               'observations':[{'issue':'hook_not_delivered','quote':'q','detail':'Secret detail.'}],
                               'repair':{'trigger':'verificador','outcome':'reparada','findings':[]}},state='ready',published=True)
        rules=self.piece(1,{'verdict':'blocked','model_verdict':None,'blocking_reasons':['Contiene enlaces'],'rules':['Contiene enlaces']},
                         note='Contiene enlaces')
        money=self.piece(6,{},note='Ciclo detenido: cost_cap')
        AuditEvent.objects.create(action='editorial.block_overridden',target=str(blocked.id),metadata={'kind':'verificador'})
        posts=self.observed();now=timezone.now()
        approved=operador.create_proposal(self.gustavo,posts[0],'INT-03',{'text':'A comment that passed.'},citations=['x'],source='agent')
        ActionProposal.objects.filter(pk=approved.pk).update(state='approved',approved_hash=approved.payload_hash,decided_at=now,
                                                             review={'decision':'approve','reasons':[]})
        lead=['Líder: no aporta una idea concreta (aporta=0.3)']
        discarded=operador.create_proposal(self.gustavo,posts[1],'INT-03',{'text':'A comment the lead stopped.'},citations=['x'],source='agent')
        ActionProposal.objects.filter(pk=discarded.pk).update(state='discarded',decided_at=now,review={'decision':'discard','reasons':lead})
        AuditEvent.objects.create(action='operator.policy_discarded',target=str(discarded.id),metadata={'issues':lead})
        return {'blocked':blocked,'repaired':repaired,'rules':rules,'money':money,'discarded':discarded}

    def test_each_gate_reports_what_entered_passed_and_stopped_with_categories_only(self):
        from team_backend import auditoria_compuertas
        h=self.history()
        report=auditoria_compuertas.auditar(7)
        rows={r['compuerta']:r for r in report['compuertas']}
        verifier=rows['verificador']
        self.assertEqual((verifier['entraron'],verifier['pasaron_a_la_primera'],verifier['pasaron_tras_reintento'],verifier['paradas']),(2,0,1,1))
        self.assertEqual((verifier['motivos'],verifier['ejemplos']),([['unsourced_figure',1]],[{'id':str(h['blocked'].id),'categoria':'unsourced_figure'}]))
        self.assertEqual((verifier['con_observaciones'],verifier['gustavo']['no_estuvo_de_acuerdo']),(1,1))
        self.assertEqual((rows['reglas_post']['paradas'],rows['reglas_post']['motivos']),(1,[['enlaces',1]]))
        self.assertEqual((rows['reparacion']['entraron'],rows['reparacion']['pasaron_a_la_primera']),(1,1))
        self.assertEqual((rows['dinero']['paradas'],rows['dinero']['motivos']),(1,[['tope_del_ciclo',1]]))
        lead=rows['lider:INT-03']
        self.assertEqual((lead['entraron'],lead['pasaron_a_la_primera'],lead['paradas'],lead['motivos'],lead['descartes_sin_reescritura']),
                         (2,1,1,[['aporta',1]],1))
        causes={d['fecha']:d['causa'] for d in report['dias_sin_post']}
        tz=operador.local_tz();day=lambda n:(timezone.now()-timedelta(days=n)).astimezone(tz).date().isoformat()
        self.assertEqual((causes[day(1)],causes[day(3)],causes[day(6)],causes[day(2)]),
                         ('compuerta:reglas_post','compuerta:verificador','dinero','sin_pieza'))
        self.assertNotIn(day(4),causes)  # the repaired piece went out
        self.assertEqual({d['fecha'] for d in report['callejones_sin_salida']},{day(1),day(3)})
        dumped=json.dumps(report,ensure_ascii=False)
        for secret in ('Needs a source','Secret detail','A comment','Which decision'):self.assertNotIn(secret,dumped)

    def test_the_command_prints_the_audit_and_its_json(self):
        from io import StringIO
        from django.core.management import call_command
        self.history()
        out=StringIO();call_command('compuertas','auditar','--dias','7',stdout=out)
        for expected in ('Auditoría de compuertas · 7 días','Verificador del post: 2 entraron','Gustavo: paradas 1, no estuvo de acuerdo en 1',
                         'Líder (Jev) · INT-03','Callejones sin salida'):
            self.assertIn(expected,out.getvalue())
        out=StringIO();call_command('compuertas','auditar','--json',stdout=out)
        self.assertIn('verificador',{r['compuerta'] for r in json.loads(out.getvalue())['compuertas']})

    def test_one_notice_per_gate_and_week_and_one_per_day_a_gate_left_without_a_post(self):
        from team_backend import auditoria_compuertas
        from team_backend.models import Notification
        h=self.history()
        with patch.dict(os.environ,{'COMPUERTAS_ALERTA_MIN':'2','COMPUERTAS_ALERTA_TASA':'0.5'}):
            self.assertGreaterEqual(auditoria_compuertas.vigilar(),2)
            refs=set(Notification.objects.filter(kind='gate_alert').values_list('ref',flat=True))
            self.assertTrue(any(r.startswith('gate_alert:verificador:') for r in refs))
            self.assertIn(f'gate_day:{h["rules"].slot_date.isoformat()}',refs)
            self.assertEqual(auditoria_compuertas.vigilar(),0)  # once per gate and week, once per day
        with patch.dict(os.environ,{'COMPUERTAS_ALERTAS':'false'}):self.assertEqual(auditoria_compuertas.vigilar(),0)

    def test_the_weekly_summary_keeps_the_gates_without_ids(self):
        from team_backend import resumen_semanal
        h=self.history()
        today=timezone.now().astimezone(operador.local_tz()).date()
        data=resumen_semanal.gates(resumen_semanal.window(today-timedelta(days=today.weekday())))
        self.assertTrue(data['disponible'])
        self.assertIn('lider:INT-03',data['por_compuerta'])
        self.assertNotIn(str(h['blocked'].id),json.dumps(data))


class LeadRedraftTests(tr.LeadBase):
    """A comment the lead discarded gets ONE redraft with its reasons; the lead judges the new text; never a third draft."""
    BETTER='Evals hide most of the work, and the hard part is choosing which failure to measure first. What did you start with?'

    def setUp(self):
        super().setUp();self.post,self.other=self.observed()
        ObservedPost.objects.filter(pk__in=[self.post.pk,self.other.pk]).update(posted_at=timezone.now()-timedelta(hours=2))
        self.jev.probabilities=dict(tr.COMMENT_OK,aporta=0.4)
        first=operador.create_proposal(self.gustavo,self.post,'INT-03',{'text':tr.GOOD},citations=[tal.UNIT],source='agent')
        self.first=autopiloto.policy_review(first);self.first.refresh_from_db()

    def queue(self):
        return autopiloto._lead_redraft(self.gustavo,self.account,timezone.now())

    def redraft(self,*answers):
        self.assertEqual(self.queue(),1)
        with patch('knowledge.providers.claude',side_effect=list(answers)) as claude:jobs.process_one(self.worker)
        job=Job.objects.get(kind='propose_comment');self.assertEqual(job.state,'complete',job.error)
        return claude,ActionProposal.objects.exclude(pk=self.first.pk).get(post=self.post)

    def test_a_comment_the_lead_discarded_is_redrafted_once_with_its_reasons(self):
        self.assertEqual((self.first.state,self.first.review['decision']),('discarded','discard'))
        claude,redraft=self.redraft(tal.draft(self.BETTER))
        self.assertEqual(Job.objects.get(kind='propose_comment').params,{'post':str(self.post.id),'redraft_of':str(self.first.id)})
        revision=json.loads(claude.call_args.args[1])['revision']
        self.assertEqual(revision,{'previous_comment':tr.GOOD,'lead_reasons':self.first.review['reasons']})
        self.assertIn('aporta=0.4',revision['lead_reasons'][0])
        self.assertIn('lead_reasons',claude.call_args.args[0])  # the drafter knows what the revision holds
        self.assertEqual(redraft.payload['text'],self.BETTER)
        self.assertIn(compuertas.LEAD_REDRAFT+': '+'; '.join(self.first.review['reasons']),redraft.risks)
        self.jev.probabilities=tr.COMMENT_OK
        self.assertEqual(autopiloto.policy_review(redraft).state,'approved')  # the lead judges the new text
        from team_backend import auditoria_compuertas
        lead={r['compuerta']:r for r in auditoria_compuertas.auditar(7)['compuertas']}['lider:INT-03']
        self.assertEqual((lead['entraron'],lead['pasaron_a_la_primera'],lead['pasaron_tras_reintento'],lead['paradas'],
                          lead['descartes_sin_reescritura']),(2,0,1,1,0))

    def test_a_redraft_is_final_no_rules_redraft_and_no_second_lead_redraft(self):
        claude,redraft=self.redraft(tal.draft(self.BETTER+' #evals'))
        self.assertEqual(claude.call_count,1)  # the lead redraft was the one redraft
        redraft=autopiloto.policy_review(redraft);redraft.refresh_from_db()
        self.assertEqual(redraft.state,'discarded');self.assertIn('Contiene hashtags',redraft.risks)
        self.assertEqual(self.queue(),0)
        with self.assertRaises(operador.Conflict):operador.propose_comment(self.gustavo,self.post.id,redraft_of=self.first.id)
        with self.assertRaises(ValueError):operador.propose_comment(self.gustavo,self.other.id,redraft_of=self.first.id)

    def test_only_recent_lead_discards_with_the_lead_on_and_room_to_draft(self):
        for env in ({'COMMENT_LEAD_REDRAFT':'false'},{'LEAD_ENABLED':'false'},{'OPERATOR_AUTONOMY':'INT-03=approval'},
                    {'OPERATOR_DAILY_PROPOSALS':'1'}):
            with patch.dict(os.environ,env):self.assertEqual(self.queue(),0,env)
        ActionProposal.objects.filter(pk=self.first.pk).update(decided_at=timezone.now()-timedelta(hours=25))
        self.assertEqual(self.queue(),0)
        ActionProposal.objects.filter(pk=self.first.pk).update(decided_at=timezone.now())
        jobs.enqueue_operation(self.gustavo,'propose_comment',{'post':str(self.other.id)})
        self.assertEqual(self.queue(),0)  # one paid draft at a time
        Job.objects.filter(kind='propose_comment').delete()  # never ran: nothing refers to it
        rules=operador.create_proposal(self.gustavo,self.other,'INT-03',{'text':tr.GOOD+' #evals'},citations=[tal.UNIT],source='agent')
        self.assertEqual(autopiloto.policy_review(rules).state,'discarded')  # a rule, not the lead: R4 already redrafts that
        self.assertEqual(self.queue(),1)
        self.assertEqual(Job.objects.get(kind='propose_comment').params['redraft_of'],str(self.first.id))
