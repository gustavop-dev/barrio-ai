"""Agent evaluation harness (audit phase 3, docs/evaluaciones-agentes.md): cases from the history in the test database,
a dry run that never calls a model, and paid runs with mocked providers. No spend and no LinkedIn."""
import json
import os
import tempfile
from datetime import datetime, timedelta
from decimal import Decimal
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.core.management import CommandError, call_command
from django.utils import timezone

from knowledge import db
from team_backend import editorial, evaluaciones, operador
from team_backend.models import ActionProposal, AuditEvent, Contact, EditorialPiece, Job, ObservedPost, PostMetric
from team_backend.tests.fakes import FakeAnthropic, message
from team_backend.tests.test_operador import OperatorBase
from team_backend.tests.test_auditoria_editorial import WITH_LINK, EditorialAuditBase
from team_backend.tests.test_publicacion import EDITORIAL_UNITS, GOOD_POST, answers
from team_backend.tests.test_red import NetworkBase

PAID_ENV={'LIVE_PROVIDERS':'true','ANTHROPIC_API_KEY':'test-only','TYPESAFE_API_KEY':'test-only','EVAL_LIMIT_USD':'5',
          'ANTHROPIC_LIMIT_USD':'5','ANTHROPIC_MODEL':'claude-opus-5-5','NETWORK_CLASSIFIER_MODEL':'claude-sonnet-5-5'}
GOOD_COMMENT='Evals are where most of the work hides. Which failure modes do you test first when an agent reaches production?'
PASSING_LEAD={'aporta':0.9,'pitch':0.05,'inventa':0.05,'respeto':0.95,'idioma':0.95}

def verdict(value='ready_for_execution'):
    """A verifier answer valid against VERIFIER_SCHEMA (the shared fixture adds `kind` to checked_claims)."""
    answer=answers(verdict=value)['verificador']
    return dict(answer,checked_claims=[{k:c[k] for k in ('text','status','ref')} for c in answer['checked_claims']])

def forbidden(*args,**kwargs):
    raise AssertionError('A dry run must not call a model')

def recorder(calls,answer):
    """A providers.claude double that records each request and answers `answer(purpose, data)`."""
    def fake(system,message,max_tokens=None,output_schema=None,effort=None,purpose='agent-run',model=None,context=None):
        data=json.loads(message)
        calls.append({'system':system,'data':data,'max_tokens':max_tokens,'output_schema':output_schema,'effort':effort,'purpose':purpose,
                      'model':model,'context':context})
        return {'text':json.dumps(answer(purpose,data)),'model':model or 'claude-opus-5-5','estimated_usd':0.01,'request_id':'req_eval'}
    return fake

def jev(answers_by_qid,calls=None):
    def fake(state,questions,purpose='lead-review'):
        if calls is not None:calls.append({'state':state,'questions':questions,'purpose':purpose})
        return {'answers':{qid:{'noul':answers_by_qid.get(qid,0.5)} for qid in questions},'model':'jev-1.14.0','estimated_usd':0.00001}
    return fake


class EvalBase(OperatorBase):
    def setUp(self):
        super().setUp()
        with db.connect() as c:
            for uid in EDITORIAL_UNITS:
                c.execute('''INSERT INTO units(id,session,title,original,sha256,source_path,pointer,metadata)
                    VALUES(%s,5,%s,'{"title":"Unidad de prueba"}','abc','fixture','/units/0','{}')''',(uid,uid))
        env=patch.dict(os.environ,{'EVAL_LIMIT_USD':'0','LEAD_ENABLED':'false','ANTHROPIC_MODEL':'claude-opus-5-5','ANTHROPIC_MAX_TOKENS':'8000',
                                   'NETWORK_CLASSIFIER_MODEL':'claude-sonnet-5-5','NETWORK_MIN_CONFIDENCE':'0.6'})
        env.start();self.addCleanup(env.stop)
        self.slots=0

    # ----- pieces with a known fate
    def piece(self,state='ready',fate=None,final=GOOD_POST,model_verdict='ready_for_execution',decision='write',pillar='business_to_product',
              modality='personal_startups',created_at=None):
        self.slots+=1;plan=answers(final=final)
        now=timezone.now();slot=(now+timedelta(days=self.slots)).astimezone(operador.local_tz()).date()
        brief=dict(plan['director'],decision=decision,pillar=pillar,modality=modality);written=decision=='write'
        piece=EditorialPiece.objects.create(account=self.account,slot_date=slot,scheduled_for=now+timedelta(days=self.slots),state=state,brief=brief,
            variants=plan['redactor'] if written else {},panel=plan['lectores'] if written else {},selection=plan['seleccion'] if written else {},
            final_text=final if written else '',signals=[],usage=[{'stage':'lectores','estimated_usd':0.05}] if written else [],
            verification={'verdict':'blocked' if state=='blocked' else 'ready_for_execution','model_verdict':model_verdict} if written else {},
            created_at=created_at or now)
        if fate:
            proposal=operador.create_proposal(self.gustavo,None,'CONT-09',{'text':final},citations=['LI-04-M005-K01'],source='agent',piece=piece)
            fields={'state':fate}
            if fate=='discarded':fields.update(decision_note='Descartada por política autonomia-v1',risks=['Contiene enlaces'],decided_at=now)
            ActionProposal.objects.filter(pk=proposal.pk).update(**fields)
        return piece

    def pieces(self):
        return {'published':self.piece(fate='confirmed'),'blocked':self.piece(state='blocked',model_verdict='blocked'),
                'vetoed':self.piece(fate='rejected'),'discarded':self.piece(fate='discarded'),'pending':self.piece(fate='approved'),
                'skipped':self.piece(state='skipped',decision='skip'),
                'old':self.piece(state='blocked',created_at=timezone.make_aware(datetime(2026,11,1,9,0)))}

    # ----- comment drafts with their fate
    def post(self,n):
        return ObservedPost.objects.create(account=self.account,provider_post_id=f'activity:eval-{n}',author_name='Ana Referente',
                                           text='Shipping AI agents to production is mostly evals.',posted_at=timezone.now())

    def draft(self,n,fate,text=GOOD_COMMENT):
        post=self.post(n);now=timezone.now()
        if fate=='saltado':
            return operador.create_proposal(self.gustavo,post,'INT-03',{'text':''},source='agent',state=ActionProposal.State.DISCARDED)
        proposal=operador.create_proposal(self.gustavo,post,'INT-03',{'text':text},citations=['LI-03-M006-K02'],source='agent')
        fields={'confirmado':{'state':'confirmed','approved_hash':proposal.payload_hash,'decided_at':now},
                'descartado_lider':{'state':'discarded','decided_at':now,'review':{'decision':'discard','reasons':['Líder: no aporta una idea concreta (aporta=0.3)']}},
                'descartado_reglas':{'state':'discarded','decided_at':now,'decision_note':'Descartada por política autonomia-v1'},
                'vetado':{'state':'rejected','decided_at':now},'pendiente':{}}[fate]
        ActionProposal.objects.filter(pk=proposal.pk).update(**fields)
        return proposal

    # ----- classified contacts with later signals
    def person(self,uid,fit=True,stage='fit',**fields):
        return Contact.objects.create(account=self.account,provider_user_id=uid,display_name=uid,headline='Founder at a pre-seed startup',
            source='commenter',stage=stage,evidence={'comment':'We learned the hard way that evals come first.'},
            classification={'fit':fit,'role':'comprador','modality':'projectapp','affinity':'desconocida','reason':'r','confidence':0.9},**fields)

    def contacts(self):
        vetoed=self.person('u-vetoed')
        proposal=operador.create_proposal(self.gustavo,None,'RED-01',{'user_id':'u-vetoed'},contact=vetoed)
        ActionProposal.objects.filter(pk=proposal.pk).update(state='rejected')
        risky=self.person('u-risky')
        proposal=operador.create_proposal(self.gustavo,None,'RED-01',{'user_id':'u-risky'},contact=risky)
        ActionProposal.objects.filter(pk=proposal.pk).update(state='discarded',review={'decision':'discard',
            'reasons':['Líder: parece vendedor, reclutador o cuenta ajena al nicho (riesgo=0.8)']})
        discarded=self.person('u-discarded',fit=False,stage='discarded')
        AuditEvent.objects.create(action='network.contact_discarded',target=str(discarded.id))
        accepted=self.person('u-accepted',stage='connected',invited_at=timezone.now()-timedelta(days=1))
        commenter=self.person('u-commenter',fit=False,stage='discarded')
        piece=self.piece(fate='confirmed')
        PostMetric.objects.create(piece=piece,kind='24h',impressions=120,reactions=5,comments=2,reposts=0,
                                  commenters=[{'provider_user_id':'u-commenter','substantive':True}])
        self.person('u-silent')  # classified, no later signal: not a case
        Contact.objects.create(account=self.account,provider_user_id='u-new',source='commenter')  # not classified
        return {'vetoed':vetoed,'risky':risky,'discarded':discarded,'accepted':accepted,'commenter':commenter}

    def evaluate(self,agents,**kwargs):
        return evaluaciones.evaluate(agents,**kwargs)


class CaseTests(EvalBase):
    def test_verifier_cases_are_pieces_with_a_known_fate(self):
        p=self.pieces()
        cases={c['id']:c for c in evaluaciones.verifier_cases(evaluaciones.Run(None))}
        self.assertEqual({k:cases[str(p[k].id)]['label'] for k in ('published','blocked','vetoed','discarded')},
                         {'published':'publicada','blocked':'bloqueada','vetoed':'vetada','discarded':'descartada_politica'})
        self.assertEqual(cases[str(p['published'].id)]['expected'],'ready_for_execution')
        self.assertEqual({cases[str(p[k].id)]['expected'] for k in ('blocked','vetoed','discarded')},{'blocked'})
        for excluded in ('pending','skipped','old'):self.assertNotIn(str(p[excluded].id),cases)  # pending, never verified, before go-live

    def test_a_discard_that_says_nothing_about_the_text_is_not_a_case(self):
        piece=self.piece(fate='discarded')
        ActionProposal.objects.filter(piece=piece).update(decision_note='Hash inconsistente; descartada',risks=[])
        self.assertEqual(evaluaciones.verifier_cases(evaluaciones.Run(None)),[])

    def test_comment_cases_carry_the_fate_of_the_draft(self):
        for n,fate in enumerate(['confirmado','descartado_lider','descartado_reglas','vetado','saltado','pendiente']):self.draft(n,fate)
        cases=evaluaciones.comment_cases(evaluaciones.Run(None))
        self.assertEqual(sorted((c['label'],c['expected']) for c in cases),
                         [('confirmado','pasa'),('descartado_lider','no_pasa'),('descartado_reglas','no_pasa'),('saltado','saltado'),('vetado','no_pasa')])

    def test_classifier_cases_need_a_later_human_lead_or_person_signal(self):
        c=self.contacts()
        cases={x['id']:x for x in evaluaciones.classifier_cases(evaluaciones.Run(None))}
        self.assertEqual({k:(cases[str(v.id)]['label'],cases[str(v.id)]['expected']) for k,v in c.items()},
                         {'vetoed':('descartado_por_gustavo',False),'risky':('riesgo_lider',False),'discarded':('descartado_por_gustavo',False),
                          'accepted':('acepto_invitacion',True),'commenter':('comento_post_propio',True)})
        self.assertEqual(len(cases),5)  # the silent and the unclassified contacts are not cases


class DryRunTests(EvalBase):
    def setUp(self):
        super().setUp()
        for target in ('knowledge.providers.claude','knowledge.providers.typesafe','knowledge.providers.anthropic_client'):
            p=patch(target,side_effect=forbidden);p.start();self.addCleanup(p.stop)

    def test_dry_run_counts_cases_shows_the_gap_and_estimates_cost_per_model(self):
        self.pieces();self.draft(1,'confirmado');self.contacts()
        report=self.evaluate(evaluaciones.AGENTS)
        verifier=report['agentes']['verificador']
        self.assertEqual((report['modo'],verifier['casos'],verifier['faltan']),('ensayo',5,{'para_20':15,'para_30':25}))  # + the contacts' piece
        self.assertEqual(verifier['por_etiqueta'],{'publicada':2,'bloqueada':1,'vetada':1,'descartada_politica':1})
        self.assertEqual(verifier['modelo_produccion'],'claude-opus-5-5')
        costs=verifier['coste_estimado']
        self.assertEqual(set(costs),{'claude-opus-5-5','claude-sonnet-5-5','claude-haiku-5-5','claude-sonnet-4-6'})
        self.assertGreater(costs['claude-opus-5-5']['usd'],costs['claude-sonnet-5-5']['usd'])
        self.assertGreater(costs['claude-sonnet-5-5']['usd'],costs['claude-haiku-5-5']['usd'])
        self.assertEqual(costs['claude-opus-5-5']['llamadas_claude'],5)
        self.assertEqual(report['agentes']['lectores']['coste_estimado']['claude-opus-5-5']['llamadas_claude'],2*report['agentes']['lectores']['usados'])
        comments=report['agentes']['comentarios']['coste_estimado']['claude-opus-5-5']
        self.assertEqual((comments['llamadas_claude'],comments['llamadas_jev']),(1,1))  # the draft and the lead's questions
        classifier=report['agentes']['clasificador']
        self.assertEqual(classifier['modelo_produccion'],'claude-sonnet-5-5')
        self.assertEqual(classifier['coste_estimado']['claude-sonnet-5-5']['llamadas_claude'],1)  # five contacts, one batch
        self.assertEqual(classifier['coste_estimado']['jev']['llamadas_jev'],5)
        self.assertEqual(classifier['linea_base'],{'aciertos':2,'total':5,'pct':40.0})  # the stored fit against the signals
        director=report['agentes']['director']
        self.assertEqual((director['calificacion'],'coste_estimado' in director),('descriptiva',False))
        self.assertGreater(report['total_estimado_usd'],0)
        with db.connect() as c:self.assertEqual(c.execute('SELECT count(*) AS n FROM usage_ledger').fetchone()['n'],0)

    def test_estimates_use_the_ledger_output_and_the_provider_prices(self):
        piece=self.piece(fate='confirmed')
        with db.connect() as c:
            c.execute("""INSERT INTO usage_ledger(id,provider,purpose,reserved_usd,actual_usd,status,usage)
                VALUES(gen_random_uuid(),'anthropic','editorial-verificador',1,0.1,'complete','{"output_tokens": 1000}')""")
        report=self.evaluate(['verificador'])
        self.assertEqual(report['salida_tipica']['tokens']['editorial-verificador'],1000)
        run=evaluaciones.Run(None)
        tokens=evaluaciones.input_tokens(evaluaciones.verifier_request(run,piece,*evaluaciones.gate_input(piece)))
        expected=(Decimal(tokens)*Decimal('4')*Decimal('1.25')+Decimal(1000)*Decimal('20'))/Decimal(1_000_000)
        self.assertAlmostEqual(report['agentes']['verificador']['coste_estimado']['claude-opus-5-5']['usd'],float(expected),places=3)

    def test_the_command_prints_the_report_and_can_write_it_to_a_path(self):
        self.pieces()
        out=StringIO()
        call_command('evaluar',stdout=out)
        text=out.getvalue()
        for expected in ('ensayo: no se llamó a ningún modelo','ESTIMACIÓN','verificador · calificación determinista','faltan 16 para 20',
                         'claude-opus-5-5 (producción)','director · calificación descriptiva','Total estimado'):
            self.assertIn(expected,text)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'informe.json'
            call_command('evaluar','--agentes','verificador,director','--salida',str(path),stdout=StringIO())
            data=json.loads(path.read_text())
        self.assertEqual(set(data['agentes']),{'verificador','director'})

    def test_limit_and_unknown_agents(self):
        self.pieces()
        self.assertEqual(self.evaluate(['verificador'],limit=2)['agentes']['verificador']['usados'],2)
        with self.assertRaises(CommandError):call_command('evaluar','--agentes','inventado',stdout=StringIO())
        with self.assertRaises(CommandError):call_command('evaluar','--modelo','gpt-x',stdout=StringIO())

    def test_paid_execution_needs_a_cap_an_eval_budget_and_live_providers(self):
        with self.assertRaisesRegex(CommandError,'--max-usd'):call_command('evaluar','--ejecutar',stdout=StringIO())
        with self.assertRaisesRegex(CommandError,'EVAL_LIMIT_USD'):call_command('evaluar','--ejecutar','--max-usd','2',stdout=StringIO())
        with patch.dict(os.environ,{'EVAL_LIMIT_USD':'5','LIVE_PROVIDERS':'false'}):
            with self.assertRaisesRegex(CommandError,'Proveedores desactivados'):call_command('evaluar','--ejecutar','--max-usd','2',stdout=StringIO())

    def test_director_is_descriptive_with_the_metrics_that_exist(self):
        written=self.piece(fate='confirmed',pillar='applied_ai',modality='projectapp')
        self.piece(state='skipped',decision='skip')
        PostMetric.objects.create(piece=written,kind='24h',impressions=100,reactions=4,comments=1,reposts=0)
        PostMetric.objects.create(piece=written,kind='72h',impressions=300,reactions=9,comments=3,reposts=1)
        d=self.evaluate(['director'])['agentes']['director']['descripcion']
        self.assertEqual((d['escritos'],d['saltados'],d['pilares'],d['modalidades']),(1,1,{'applied_ai':1},{'projectapp':1}))
        self.assertEqual(d['desenlace_escritos'],{'publicada':1})
        self.assertEqual(d['resultados']['pillar']['applied_ai'],{'piezas':1,'impresiones_media':300,'interacciones_media':13})  # the latest age


class PaidRunTests(EvalBase):
    def setUp(self):
        super().setUp()
        env=patch.dict(os.environ,PAID_ENV);env.start();self.addCleanup(env.stop)

    def test_verifier_agreement_with_the_known_fates(self):
        texts={k:GOOD_POST+f'\n\nCase {k}.' for k in ('published','blocked','vetoed','discarded')}
        published=str(self.piece(fate='confirmed',final=texts['published']).id)
        self.piece(state='blocked',model_verdict='blocked',final=texts['blocked'])
        self.piece(fate='rejected',final=texts['vetoed']);self.piece(fate='discarded',final=texts['discarded'])
        calls=[]
        def answer(purpose,data):
            # Agrees with every fate except the vetoed piece, which it lets through.
            ready=data['text'] in (texts['published'],texts['vetoed'])
            return verdict('ready_for_execution' if ready else 'blocked')
        with patch('knowledge.providers.claude',side_effect=recorder(calls,answer)),patch('knowledge.providers.typesafe',side_effect=forbidden):
            report=self.evaluate(['verificador'],execute=True,max_usd=Decimal('2'))
        result=report['agentes']['verificador']['resultados']['claude-opus-5-5']
        self.assertEqual({c['purpose'] for c in calls},{'eval-verificador'})
        self.assertEqual({c['model'] for c in calls},{'claude-opus-5-5'})
        self.assertEqual((calls[0]['effort'],calls[0]['max_tokens']),('high',16000))
        cases={c['id']:c for c in result['casos']}
        self.assertEqual(cases[published]['compuerta'],'ready_for_execution')
        metrics=result['metricas']
        self.assertEqual(metrics['evaluados'],4)
        self.assertEqual(metrics['acuerdo_compuerta']['aciertos'],3)
        self.assertEqual(metrics['matriz_compuerta']['positivo_que_falto'],1)
        self.assertEqual(metrics['acuerdo_modelo']['aciertos'],3)
        self.assertEqual((metrics['paradas_por_reglas'],metrics['reparaciones']),(0,{}))  # no findings: nothing to repair
        self.assertEqual(metrics['esquema_valido'],{'aciertos':4,'total':4,'pct':100.0})
        self.assertEqual(report['gasto_usd'],0.04)
        self.assertEqual(report['detenida'],'')

    def test_the_gate_runs_the_rules_first_and_one_repair_round_as_in_production(self):
        piece=self.piece(fate='confirmed',final=WITH_LINK);calls=[]
        repaired=dict(answers()['reparacion'],final_text=GOOD_POST,changes=[{'finding':'Contiene enlaces','change':'Quité el enlace.'}])
        answer=lambda purpose,data:repaired if 'findings' in data else verdict()
        with patch('knowledge.providers.claude',side_effect=recorder(calls,answer)):
            report=self.evaluate(['verificador'],execute=True,max_usd=Decimal('2'),models=['claude-sonnet-5-5'])
        # The rules stop the link before the verifier is paid; the repair keeps the production model; the verifier sees the fix.
        self.assertEqual([('findings' in c['data'],c['model']) for c in calls],[(True,'claude-opus-5-5'),(False,'claude-sonnet-5-5')])
        self.assertEqual(calls[0]['data']['findings'],[{'source':'reglas','issue':'regla','quote':'','detail':'Contiene enlaces'}])
        self.assertIn('<tono_de_voz',calls[0]['system'])
        self.assertEqual((calls[0]['data']['text'],calls[1]['data']['text']),(WITH_LINK,GOOD_POST))
        self.assertEqual({c['purpose'] for c in calls},{'eval-verificador'})
        case=report['agentes']['verificador']['resultados']['claude-sonnet-5-5']['casos'][0]
        self.assertEqual((case['id'],case['compuerta'],case['modelo'],case['reparacion'],case['reglas']),
                         (str(piece.id),'ready_for_execution',None,'reparada',['Contiene enlaces']))
        metrics=report['agentes']['verificador']['resultados']['claude-sonnet-5-5']['metricas']
        self.assertEqual((metrics['paradas_por_reglas'],metrics['reparaciones'],metrics['acuerdo_modelo']['total']),(1,{'reparada':1},0))
        with patch.dict(os.environ,{'EDITORIAL_REPAIR':'false'}),patch('knowledge.providers.claude',side_effect=forbidden):
            report=self.evaluate(['verificador'],execute=True,max_usd=Decimal('2'))
        self.assertEqual(report['agentes']['verificador']['resultados']['claude-opus-5-5']['casos'][0]['compuerta'],'blocked')

    def test_comment_drafts_are_graded_by_the_rules_and_the_lead_without_creating_proposals(self):
        self.draft(1,'confirmado');self.draft(2,'descartado_lider');self.draft(3,'saltado')
        before=(ActionProposal.objects.count(),Job.objects.count(),EditorialPiece.objects.count())
        # Newest case first: the skip, the lead discard, then the confirmed one, whose hashtag survives its one redraft.
        drafts=iter(['',GOOD_COMMENT,GOOD_COMMENT+' #evals',GOOD_COMMENT+' #evals #again'])
        calls=[];jev_calls=[]
        def answer(purpose,data):
            text=next(drafts)
            return {'decision':'comment' if text else 'skip','language':'en','comment':text,'rationale':'r','citations':['LI-03-M006-K02'],
                    'claims_needing_evidence':[],'risks':[]}
        with patch('knowledge.providers.claude',side_effect=recorder(calls,answer)),patch('knowledge.providers.typesafe',side_effect=jev(PASSING_LEAD,jev_calls)):
            report=self.evaluate(['comentarios'],execute=True,max_usd=Decimal('2'))
        self.assertEqual(before,(ActionProposal.objects.count(),Job.objects.count(),EditorialPiece.objects.count()))
        self.assertEqual({c['purpose'] for c in calls},{'eval-comentarios'})
        self.assertEqual({c['purpose'] for c in jev_calls},{'eval-comentarios'})
        self.assertEqual(calls[0]['data']['existing_comments'],[])  # LinkedIn is never read
        self.assertIn('course_units',calls[0]['context'])  # the units go in the cached system context, as in production
        self.assertEqual(calls[3]['data']['revision'],{'previous_comment':GOOD_COMMENT+' #evals','rule_violations':['Contiene hashtags'],
                                                       'claims_needing_evidence':[]})
        cases={c['etiqueta']:c for c in report['agentes']['comentarios']['resultados']['claude-opus-5-5']['casos']}
        self.assertEqual(cases['saltado']['nuevo'],'saltado')
        self.assertEqual(cases['descartado_lider']['nuevo'],'pasa')
        self.assertEqual((cases['confirmado']['nuevo'],cases['confirmado']['reglas'],cases['confirmado']['reescrito']),
                         ('no_pasa',['Contiene hashtags'],True))
        self.assertFalse(cases['descartado_lider']['reescrito'])
        metrics=report['agentes']['comentarios']['resultados']['claude-opus-5-5']['metricas']
        self.assertEqual((metrics['mejoras'],metrics['regresiones'],metrics['reescritos']),(1,1,1))
        self.assertEqual(metrics['lider_aprueba'],{'aciertos':2,'total':2,'pct':100.0})

    def test_the_lead_can_fail_a_draft_that_passes_the_rules(self):
        self.draft(1,'confirmado')
        answer=lambda purpose,data:{'decision':'comment','language':'en','comment':GOOD_COMMENT,'rationale':'r','citations':['LI-03-M006-K02'],
                                    'claims_needing_evidence':[],'risks':[]}
        with patch('knowledge.providers.claude',side_effect=recorder([],answer)),patch('knowledge.providers.typesafe',side_effect=jev(dict(PASSING_LEAD,aporta=0.3))):
            report=self.evaluate(['comentarios'],execute=True,max_usd=Decimal('2'))
        case=report['agentes']['comentarios']['resultados']['claude-opus-5-5']['casos'][0]
        self.assertEqual((case['nuevo'],case['reglas'],case['lider']['aprueba']),('no_pasa',[],False))
        with patch('knowledge.providers.claude',side_effect=recorder([],answer)),patch('knowledge.providers.typesafe',side_effect=forbidden):
            report=self.evaluate(['comentarios'],execute=True,max_usd=Decimal('2'),lead=False)
        self.assertEqual(report['agentes']['comentarios']['resultados']['claude-opus-5-5']['casos'][0]['nuevo'],'pasa')

    def test_classifier_fit_agreement_in_one_batch_and_with_jev(self):
        c=self.contacts();calls=[]
        fits={str(c['accepted'].id):True,str(c['commenter'].id):True,str(c['risky'].id):True}  # one disagreement: the risky one
        answer=lambda purpose,data:{'contacts':[{'id':p['id'],'fit':fits.get(p['id'],False),'role':'par','modality':'comunidad_autoridad',
                                                 'affinity':'desconocida','reason':'r','confidence':0.8,'course_citations':['LI-03-M005-K06'],'invitation_note':'','note_reason':''} for p in data['people']]}
        with patch('knowledge.providers.claude',side_effect=recorder(calls,answer)):
            report=self.evaluate(['clasificador'],execute=True,max_usd=Decimal('2'),models=['claude-haiku-5-5'])
        self.assertEqual(len(calls),1)
        self.assertEqual((calls[0]['purpose'],calls[0]['model'],calls[0]['effort'],calls[0]['max_tokens']),('eval-clasificador','claude-haiku-5-5','medium',16000))
        metrics=report['agentes']['clasificador']['resultados']['claude-haiku-5-5']['metricas']
        self.assertEqual(metrics['acuerdo_encaje'],{'aciertos':4,'total':5,'pct':80.0})
        self.assertEqual(metrics['acuerdo_linea_base'],{'aciertos':2,'total':5,'pct':40.0})
        jev_calls=[]
        with patch('knowledge.providers.claude',side_effect=forbidden),patch('knowledge.providers.typesafe',side_effect=jev({'encaja':0.9,'riesgo':0.1},jev_calls)):
            report=self.evaluate(['clasificador'],execute=True,max_usd=Decimal('2'),models=['jev'])
        self.assertEqual(len(jev_calls),5)
        self.assertEqual(set(jev_calls[0]['questions']),{'encaja','riesgo'})
        metrics=report['agentes']['clasificador']['resultados']['jev']['metricas']
        self.assertEqual(metrics['acuerdo_encaje'],{'aciertos':2,'total':5,'pct':40.0})  # Jev said yes to everyone

    def test_readers_ablation_reruns_the_selection_with_and_without_the_panel(self):
        self.piece(fate='confirmed');calls=[]
        def answer(purpose,data):
            choice='A' if 'panel' in data else 'B'
            return dict(answers()['seleccion'],decision=choice,final_text=GOOD_POST if choice=='A' else GOOD_POST.replace('one question','two questions'))
        with patch('knowledge.providers.claude',side_effect=recorder(calls,answer)):
            report=self.evaluate(['lectores'],execute=True,max_usd=Decimal('2'))
        self.assertEqual([('panel' in c['data'],c['purpose']) for c in calls],[(True,'eval-lectores'),(False,'eval-lectores')])
        self.assertEqual(calls[0]['data']['panel'],answers()['lectores'])
        metrics=report['agentes']['lectores']['resultados']['claude-opus-5-5']['metricas']
        self.assertEqual(metrics['cambia_la_decision'],{'aciertos':1,'total':1,'pct':100.0})
        self.assertEqual(metrics['ruido_entre_corridas'],{'aciertos':0,'total':1,'pct':0.0})
        self.assertEqual(metrics['similitud_ruido'],1.0)
        self.assertLess(metrics['similitud_con_y_sin_panel'],1.0)
        self.assertIn('conservarlo',metrics['veredicto'])
        self.assertIn('Orientativo',metrics['veredicto'])

    def test_max_usd_stops_the_run_before_a_call_that_could_exceed_it(self):
        self.pieces()
        with patch('knowledge.providers.claude',side_effect=forbidden):
            report=self.evaluate(['verificador','lectores'],execute=True,max_usd=Decimal('0.01'))
        self.assertIn('--max-usd',report['detenida'])
        self.assertEqual(report['agentes']['verificador']['resultados']['claude-opus-5-5']['casos'],[])
        self.assertNotIn('claude-opus-5-5',report['agentes']['lectores']['resultados'])  # nothing more after the stop

    def test_the_monthly_eval_budget_counts_the_eval_spend_in_the_ledger(self):
        self.pieces()
        with db.connect() as c:
            c.execute("""INSERT INTO usage_ledger(id,provider,purpose,reserved_usd,actual_usd,status)
                VALUES(gen_random_uuid(),'anthropic','eval-verificador',5,4.99,'complete')""")
            c.execute("""INSERT INTO usage_ledger(id,provider,purpose,reserved_usd,actual_usd,status)
                VALUES(gen_random_uuid(),'anthropic','editorial-verificador',50,40,'complete')""")  # production spend is not counted
        with patch('knowledge.providers.claude',side_effect=forbidden):
            report=self.evaluate(['verificador'],execute=True,max_usd=Decimal('3'))
        self.assertIn('EVAL_LIMIT_USD=5',report['detenida'])
        self.assertIn('$4.9900',report['detenida'])

    def test_every_paid_call_lands_in_the_ledger_under_its_eval_purpose(self):
        self.piece(fate='confirmed')
        answer=message(text=json.dumps(verdict()),input_tokens=9000,output_tokens=3000)
        with patch('knowledge.providers.anthropic_client',return_value=FakeAnthropic(answer)):
            report=self.evaluate(['verificador'],execute=True,max_usd=Decimal('2'))
        with db.connect() as c:
            rows=c.execute('SELECT provider,purpose,status,actual_usd FROM usage_ledger').fetchall()
        self.assertEqual([(r['provider'],r['purpose'],r['status']) for r in rows],[('anthropic','eval-verificador','complete')])
        self.assertAlmostEqual(float(rows[0]['actual_usd']),report['gasto_usd'],places=4)
        self.assertAlmostEqual(report['gasto_usd'],(9000*4+3000*20)/1_000_000,places=6)


class GraderTests(EvalBase):
    def test_schema_errors_follow_the_production_schemas(self):
        self.assertEqual(evaluaciones.schema_errors(verdict(),editorial.VERIFIER_SCHEMA),[])
        broken=dict(answers()['verificador'],verdict='maybe',extra=1);broken.pop('summary')
        self.assertEqual(sorted(evaluaciones.schema_errors(broken,editorial.VERIFIER_SCHEMA)),
                         ['$.checked_claims[0].kind: no permitido','$.extra: no permitido','$.summary: falta','$.verdict: valor fuera de la lista'])

    def test_jev_verdict_uses_the_lead_thresholds(self):
        checks=[('aporta','min',0.7,'no aporta'),('pitch','max',0.2,'pitch')]
        self.assertEqual(evaluaciones.jev_verdict({'aporta':{'noul':0.8},'pitch':{'noul':0.1}},checks)[:2],(True,[]))
        self.assertEqual(evaluaciones.jev_verdict({'aporta':{'noul':0.8}},checks)[:2],(False,['pitch']))


class MirrorEditorialTests(EditorialAuditBase):
    """The eval requests are the production requests: same system, payload, units, caps and effort."""

    def test_verifier_repair_and_selection_requests_mirror_the_circuit(self):
        self.observed()
        finding={'issue':'unsourced_figure','severity':'material','quote':'a weekly decision','detail':'Needs a source.'}
        blocked=dict(answers()['verificador'],verdict='blocked',findings=[finding])
        plan=answers()
        plan['reparacion']=dict(plan['reparacion'],final_text=GOOD_POST+'\n\nWho makes it?')
        piece=self.plan_with(plan,verificador=[blocked,plan['verificador']])
        self.assertEqual(piece.verification['repair']['outcome'],'reparada')
        sent={}
        for purpose,data,system in self.calls:sent.setdefault(purpose,(data,system))  # the first call of each stage
        run=evaluaciones.Run(None)
        text,claims=evaluaciones.gate_input(piece)
        self.assertEqual(text,GOOD_POST)  # the selection's text, not the repaired piece.final_text
        verifier=evaluaciones.verifier_request(run,piece,text,claims)
        self.assertEqual((json.loads(verifier['message']),verifier['system']),sent['editorial-verificador'])
        self.assertEqual((verifier['max_tokens'],verifier['effort']),(16000,'high'))
        repair=evaluaciones.repair_request(run,piece,text,claims,editorial._findings(blocked,[]))
        self.assertEqual((json.loads(repair['message']),repair['system']),sent['editorial-reparacion'])
        selection=evaluaciones.selection_request(run,piece,panel=True)
        self.assertEqual((json.loads(selection['message']),selection['system']),sent['editorial-seleccion'])
        without=json.loads(evaluaciones.selection_request(run,piece,panel=False)['message'])
        expected=dict(sent['editorial-seleccion'][0]);expected.pop('panel')
        self.assertEqual(without,expected)


class MirrorCommentTests(OperatorBase):
    def test_comment_request_mirrors_propose_comment(self):
        post=self.observed()[0];calls=[]
        answer=lambda purpose,data:{'decision':'comment','language':'en','comment':GOOD_COMMENT,'rationale':'r','citations':['LI-03-M006-K02'],
                                    'claims_needing_evidence':[],'risks':[]}
        with patch('knowledge.providers.claude',side_effect=recorder(calls,answer)):operador.propose_comment(self.gustavo,post.id)
        request,_=evaluaciones.comment_request(evaluaciones.Run(None),post)
        production=calls[0]
        self.assertEqual(json.loads(request['message']),production['data'])  # the fake post has no comments to read
        for key in ('system','max_tokens','output_schema','effort','context'):self.assertEqual(request[key],production[key],key)

    def test_the_redraft_request_mirrors_the_rules_redraft(self):
        post=self.observed()[0];calls=[]
        texts=iter([GOOD_COMMENT+' #evals',GOOD_COMMENT])
        answer=lambda purpose,data:{'decision':'comment','language':'en','comment':next(texts),'rationale':'r','citations':['LI-03-M006-K02'],
                                    'claims_needing_evidence':[],'risks':[]}
        with patch('knowledge.providers.claude',side_effect=recorder(calls,answer)):operador.propose_comment(self.gustavo,post.id)
        self.assertEqual(len(calls),2)
        revision=calls[1]['data']['revision']
        request,_=evaluaciones.comment_request(evaluaciones.Run(None),post,revision)
        self.assertEqual(json.loads(request['message']),calls[1]['data'])


class MirrorClassifierTests(NetworkBase):
    def test_classify_request_mirrors_red_classify(self):
        person=self.fake.seed_person('founder-eva','Eva Founder',headline='Founder at a pre-seed startup')
        contact=Contact.objects.create(account=self.account,provider_user_id=person['id'],display_name='Eva Founder',headline='Founder at a pre-seed startup',
                                       source='search',evidence={'query':'founder pre-seed'},stage='candidate')
        calls=[]
        answer=lambda purpose,data:{'contacts':[{'id':p['id'],'fit':True,'role':'comprador','modality':'projectapp','affinity':'desconocida',
                                                 'reason':'r','confidence':0.9,'course_citations':['LI-03-M005-K06'],'invitation_note':'','note_reason':''} for p in data['people']]}
        with patch('knowledge.providers.claude',side_effect=recorder(calls,answer)):self.job('classify_contacts')
        contact.refresh_from_db()
        request=evaluaciones.classify_request(evaluaciones.Run(None),[contact])
        production=calls[0]
        self.assertEqual(json.loads(request['message']),production['data'])
        for key in ('system','max_tokens','output_schema','effort','context'):self.assertEqual(request[key],production[key],key)
