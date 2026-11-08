"""Office redesign backend: agente líder (Jev), team questions and memory, orientation, opportunities, Tu turno,
activity and settings."""
import json
import os
from datetime import timedelta
from unittest.mock import patch
import httpx
from django.utils import timezone
from knowledge import db, memory, providers
from team_backend import autopiloto, guardas, jobs, operador, preguntas
from team_backend.connectors import ConnectorError, FakeConnector
from team_backend.models import ActionExecution, ActionProposal, Contact, Opportunity, Referent, TeamQuestion
from team_backend.tests.test_operador import OperatorBase
from team_backend.tests.test_publicacion import EditorialBase, answers

GOOD='Evals are where most of the work hides. Which failure modes do you test first?'

class JevMock:
    """httpx transport standing in for api.typesafe.ai: answers every question with the given probabilities."""
    def __init__(self,probabilities=None,status=200):
        self.requests=[];self.probabilities=probabilities or {};self.status=status
    def __call__(self,request):
        body=json.loads(request.content);self.requests.append(body)
        if self.status!=200:return httpx.Response(self.status,json={'detail':'overloaded'})
        answers={q:{'type':'noul','noul':self.probabilities.get(q,0.5)} for q in body['questions']}
        return httpx.Response(200,json={'model':'jev-1.14.0','answers':answers,'usage':{'input_tokens':500,'output_tokens':40}})

COMMENT_OK={'aporta':0.92,'pitch':0.03,'inventa':0.02,'respeto':0.98,'idioma':0.97,'orientacion':0.9}

class LeadBase(OperatorBase):
    def setUp(self):
        super().setUp()
        env=patch.dict(os.environ,{'LEAD_ENABLED':'true','LIVE_PROVIDERS':'true','TYPESAFE_API_KEY':'ts-test-key','TYPESAFE_LIMIT_USD':'1'})
        env.start();self.addCleanup(env.stop)
        self.jev=JevMock(COMMENT_OK)
        transport=patch.object(providers,'TYPESAFE_TRANSPORT',httpx.MockTransport(self.jev))
        transport.start();self.addCleanup(transport.stop)

    def agent_comment(self,text=GOOD):
        post=self.observed()[0]
        bot=self.gustavo
        return operador.create_proposal(bot,post,'INT-03',{'text':text},citations=['LI-03-M006-K02'],source='agent')


class LeadTests(LeadBase):
    def test_lead_approves_a_good_comment_and_records_the_judgment(self):
        proposal=autopiloto.policy_review(self.agent_comment())
        proposal.refresh_from_db()
        self.assertEqual(proposal.state,'approved')
        self.assertEqual(proposal.decision_note,'Aprobada por el líder (jev-1.14.0) · política autonomia-v1')
        self.assertEqual(proposal.review['answers']['aporta'],0.92);self.assertFalse(proposal.review['with_orientation'])
        body=self.jev.requests[0]
        self.assertEqual(body['model'],'jev-1.14.0')
        self.assertEqual(set(body['questions']),{'aporta','pitch','inventa','respeto','idioma'})
        self.assertEqual(body['state']['comentario'],GOOD);self.assertEqual(body['state']['hechos_publicos_de_gustavo'],[])
        with db.connect() as c:
            row=c.execute("SELECT status,actual_usd,purpose FROM usage_ledger WHERE provider='typesafe'").fetchone()
        self.assertEqual((row['status'],row['purpose']),('complete','lead-review'))
        self.assertAlmostEqual(float(row['actual_usd']),500*0.042/1e6)

    def test_lead_discards_doubt_without_asking_gustavo(self):
        self.jev.probabilities=dict(COMMENT_OK,pitch=0.85)
        proposal=autopiloto.policy_review(self.agent_comment());proposal.refresh_from_db()
        self.assertEqual(proposal.state,'discarded');self.assertEqual(proposal.decision_note,'Descartada por el líder (jev-1.14.0)')
        self.assertTrue(any('suena a venta' in r for r in proposal.risks),proposal.risks)
        self.assertEqual(TeamQuestion.objects.count(),0)  # nothing escalated

    def test_orientation_is_judged_and_never_leaks(self):
        self.human.put('/api/v1/orientacion',{'text':'Priorizar founders técnicos de EE. UU.; nada de marketing de contenidos.'},format='json')
        autopiloto.policy_review(self.agent_comment())
        body=self.jev.requests[-1]
        self.assertIn('orientacion',body['questions']);self.assertIn('founders técnicos',body['state']['orientacion_de_gustavo'])
        self.assertIn('orientacion',{g['key'] for g in guardas.blocks()[1]})

    def test_unavailable_jev_keeps_the_proposal_pending_and_backs_off(self):
        self.jev.status=529
        proposal=autopiloto.policy_review(self.agent_comment());proposal.refresh_from_db()
        self.assertEqual(proposal.state,'proposed');self.assertIn('error_at',proposal.review)
        autopiloto.policy_review(proposal)
        self.assertEqual(len(self.jev.requests),1)  # no new request inside the back-off window
        self.assertEqual(ActionExecution.objects.count(),0)

    def test_lead_judges_people_before_following(self):
        self.jev.probabilities={'encaja':0.85,'riesgo':0.05}
        person=self.fake.seed_person('founder-ana','Ana Founder',headline='Founder @ Tiny')
        contact=Contact.objects.create(account=self.account,provider_user_id=person['id'],display_name='Ana Founder',headline='Founder @ Tiny',
            source='manual',stage='fit',classification={'fit':True,'role':'comprador','modality':'projectapp','reason':'r','confidence':0.9})
        proposal=operador.create_proposal(self.gustavo,None,'RED-01',{'user_id':person['id']},source='agent',contact=contact)
        with patch.dict(os.environ,{'OPERATOR_AUTONOMY':'RED-01=auto'}):autopiloto.policy_review(proposal)
        proposal.refresh_from_db()
        self.assertEqual(proposal.state,'approved');self.assertEqual(self.jev.requests[-1]['state']['persona']['titular'],'Founder @ Tiny')

    def test_disabled_lead_keeps_the_deterministic_policy(self):
        with patch.dict(os.environ,{'LEAD_ENABLED':'false'}):
            proposal=autopiloto.policy_review(self.agent_comment())
        proposal.refresh_from_db()
        self.assertEqual(proposal.decision_note,'Aprobada por política autonomia-v1');self.assertEqual(self.jev.requests,[])


class QuestionTests(OperatorBase):
    def setUp(self):
        super().setUp();self.grant(self.gustavo,'confirm_memory','propose_memory')

    def propose_fact(self,key,text,public):
        memory.propose('user',key,{'texto':text,'uso_publico':public},'agent:test','prueba')

    def test_pending_memory_becomes_confirmation_questions_and_answers_confirm_it(self):
        self.propose_fact('identidad.rol','Fundador de ProjectApp.',True)
        turn=self.human.get('/api/v1/tu-turno').json()
        self.assertEqual(turn['count'],1)
        question=turn['questions'][0]['question']
        self.assertEqual((question['kind'],question['memory_key'],question['suggested_public']),('confirm','identidad.rol',True))
        self.assertEqual(self.api.post(f'/api/v1/preguntas/{question["id"]}/responder',{'accept':True},format='json').status_code,403)
        answered=self.human.post(f'/api/v1/preguntas/{question["id"]}/responder',{'accept':True},format='json').json()
        self.assertEqual(answered['state'],'answered')
        public,_=memory.confirmed_blocks()
        self.assertEqual([f['fact'] for f in public],['Fundador de ProjectApp.'])
        self.assertEqual(self.human.get('/api/v1/tu-turno').json()['count'],0)

    def test_agent_questions_are_answered_declined_and_never_repeated(self):
        q=preguntas.ask('director_editorial','¿Cuál fue tu primer agente en producción?','Para contar una experiencia real en el post del jueves',
                        'experiencia.primer_agente',True,origin='piece:x')
        self.assertIsNotNone(q)
        self.assertIsNone(preguntas.ask('director_editorial','Otra forma de preguntarlo','x','experiencia.primer_agente'))
        self.human.post(f'/api/v1/preguntas/{q.id}/responder',{'text':'Un agente de soporte para un ERP en 2025.','public_use':True},format='json')
        self.assertIn('Un agente de soporte para un ERP en 2025.',[f['fact'] for f in memory.confirmed_blocks()[0]])
        self.assertIsNone(preguntas.ask('director_editorial','¿Y tu primer agente?','x','experiencia.primer_agente'))  # already known
        other=preguntas.ask('director_editorial','¿Cuánto cobras?','Para hablar de precios','precios.tarifa')
        self.assertEqual(self.human.post(f'/api/v1/preguntas/{other.id}/no-compartir',{},format='json').json()['state'],'declined')
        self.assertIsNone(preguntas.ask('director_editorial','¿Cuánto cobras por hora?','x','precios.tarifa'))

    def test_facts_can_be_corrected_and_withdrawn(self):
        q=preguntas.ask('posicionamiento','¿Dónde vives?','Para la ubicación del perfil','identidad.ciudad')
        self.human.post(f'/api/v1/preguntas/{q.id}/responder',{'text':'Medellín','public_use':False},format='json')
        facts=self.human.get('/api/v1/memoria/hechos').json()
        self.assertEqual([(f['key'],f['text'],f['public_use']) for f in facts],[('identidad.ciudad','Medellín',False)])
        facts=self.human.post('/api/v1/memoria/hechos/identidad.ciudad/corregir',{'text':'Bogotá','public_use':True},format='json').json()
        self.assertEqual(facts[0]['text'],'Bogotá')
        self.assertEqual(self.human.post('/api/v1/memoria/hechos/identidad.ciudad/retirar',{'reason':'Privado'},format='json').json(),[])
        self.assertEqual(memory.confirmed_blocks(),([],[]))
        self.assertIsNone(preguntas.ask('posicionamiento','¿Dónde vives ahora?','x','identidad.ciudad'))


class DirectorQuestionTests(EditorialBase):
    def test_director_can_ask_gustavo_for_a_real_experience(self):
        plan=answers(decision='skip')
        plan['director']['questions_for_gustavo']=[{'question':'¿Qué aprendiste al integrar IA en un ERP real?',
            'purpose':'Para escribir un post con una experiencia propia','memory_key':'Experiencia.IA ERP','public':True}]
        self.plan(plan)
        question=TeamQuestion.objects.get()
        self.assertEqual((question.agent,question.memory_key,question.suggested_public),('director_editorial','experiencia.ia_erp',True))
        self.assertIn('closed_keys',self.calls[0][1]['team_questions'])


class OpportunityAndTurnTests(OperatorBase):
    def test_opportunities_follow_the_form_with_history(self):
        self.assertEqual(self.api.post('/api/v1/oportunidades',{'person_name':'x','modality':'projectapp'},format='json').status_code,403)
        self.assertEqual(self.human.post('/api/v1/oportunidades',{'modality':'projectapp'},format='json').status_code,400)  # who is it?
        created=self.human.post('/api/v1/oportunidades',{'person_name':'Laura Gómez','company':'Retail SAS','modality':'projectapp',
            'channel':'email','attribution':'lo_dijo','need':'ERP de inventario','next_action':'Llamada de alcance',
            'next_action_at':'2026-11-10T15:00:00Z'},format='json')
        self.assertEqual(created.status_code,201,created.content)
        body=created.json();oid=body['id']
        self.assertEqual((body['person'],body['stage'],body['days_in_stage'],body['contact']),('Laura Gómez','conversacion',0,None))
        moved=self.human.patch(f'/api/v1/oportunidades/{oid}',{'stage':'acuerdo','notes':'Firmado'},format='json').json()
        self.assertEqual((moved['stage'],moved['notes']),('acuerdo','Firmado'));self.assertIsNotNone(moved['closed_at'])
        self.assertIn('Conversación → Acuerdo',moved['history'][-1]['detail'])
        self.assertEqual(len(self.human.get('/api/v1/oportunidades?modality=projectapp').json()['results']),1)
        self.assertEqual(self.human.delete(f'/api/v1/oportunidades/{oid}').status_code,204)

    def test_tu_turno_alerts_follow_the_spec(self):
        post=self.observed()[0]
        proposal=operador.create_proposal(self.gustavo,post,'INT-03',{'text':GOOD})
        ActionProposal.objects.filter(pk=proposal.pk).update(state='uncertain')
        operador.set_global_pause(self.gustavo,True,'Revisar el tono')
        with patch('team_backend.connectors_linkedin.status_payload',return_value={'connected':True,'expiring_soon':True,'expired':False,
                                                                                   'days_left':4,'expires_at':'2026-11-11T10:00:00+00:00'}):
            turn=self.human.get('/api/v1/tu-turno').json()
        ids={a['id'].split(':')[0] for a in turn['alerts']}
        self.assertEqual(ids,{'linkedin_expiring','uncertain','machine_paused'})
        uncertain=next(a for a in turn['alerts'] if a['id'].startswith('uncertain'))
        self.assertTrue(uncertain['critical']);self.assertEqual(uncertain['attempt']['text'],GOOD)
        self.assertEqual([a['body'] for a in uncertain['actions']],[{'outcome':'confirmed'},{'outcome':'failed'}])
        self.assertEqual((turn['count'],turn['critical'],turn['counts']),(3,True,{'avisos':3,'preguntas':0,'tareas':0}))
        self.assertTrue(turn['top']['critical']);self.assertEqual(turn['tasks'],{'perfil':[],'conversaciones':[],'resumen':[]})
        expiring=next(a for a in turn['alerts'] if a['id']=='linkedin_expiring')
        self.assertFalse(expiring['critical'])

    def test_list_view_upcoming_and_settings(self):
        post=self.observed()[0]
        done=self.approve(self.proposal(post))
        self.assertEqual(done.state,'confirmed')
        discarded=operador.create_proposal(self.gustavo,post,'INT-02',{'reaction':'linkedin_like'})
        ActionProposal.objects.filter(pk=discarded.pk).update(state='discarded',decision_note='Descartada por el líder (jev-1.14.0)',
                                                              review={'decision':'discard','reasons':['Líder: no aporta']})
        listed=self.human.get('/api/v1/actividad').json()
        self.assertEqual([i['capability'] for i in listed['items']],['INT-03'])  # what did not go out stays hidden
        item=listed['items'][0]
        self.assertEqual((item['label'],item['target']['kind'],item['decided_by'],item['agent'],item['state_label']),
                         ('Comentario','post','gustavo','relaciones_comunidad',None))
        self.assertIn('Shipping AI agents',item['target']['post_excerpt'])
        with_hidden=self.human.get('/api/v1/actividad?no_salio=1').json()['items']
        self.assertEqual(next(i for i in with_hidden if i['capability']=='INT-02')['decided_by'],'lider')
        self.assertEqual(self.human.get('/api/v1/actividad?tipo=red').json()['items'],[])
        self.assertEqual(self.human.get('/api/v1/actividad?tipo=otra').status_code,404)
        settings=self.human.get('/api/v1/ajustes').json()
        self.assertEqual((settings['autonomy']['INT-03'],settings['autonomy']['RED-02']),('auto','approval'))
        self.assertEqual([b['budget'] for b in settings['ai_spend']['today']],['general','editorial','red'])
        self.assertIn('open_now',settings['window']);self.assertFalse(settings['lead']['enabled'])


class QuestionFlowTests(OperatorBase):
    def setUp(self):
        super().setUp();self.grant(self.gustavo,'confirm_memory','propose_memory')

    def test_typed_answers_postpone_undo_and_expiry(self):
        yes=preguntas.ask('director_editorial','¿Aceptas proyectos de 3 meses?','Para saber qué oportunidades priorizar','oferta.proyectos_cortos',
                          answer_type='yes_no')
        self.assertEqual(self.human.post(f'/api/v1/preguntas/{yes.id}/responder',{'value':'quizas'},format='json').status_code,400)
        self.human.post(f'/api/v1/preguntas/{yes.id}/responder',{'value':'si','text':'Solo remotos','public_use':False},format='json')
        _,private=memory.confirmed_blocks()
        self.assertIn('¿Aceptas proyectos de 3 meses? Sí. Solo remotos',[g['guidance']['texto'] for g in private])
        undone=self.human.post(f'/api/v1/preguntas/{yes.id}/deshacer',{},format='json').json()
        self.assertEqual(undone['state'],'open');self.assertEqual(memory.confirmed_blocks(),([],[]))
        choice=preguntas.ask('perfil','¿Qué modalidad prefieres?','Para el titular','oferta.modalidad',answer_type='choice',options=['Tiempo completo','Parcial'])
        self.human.post(f'/api/v1/preguntas/{choice.id}/mas-tarde',{},format='json')
        late=preguntas.ask('perfil','¿En qué ciudad vives?','Para el perfil','identidad.ciudad',deadline=timezone.now()-timedelta(hours=1))
        turn=self.human.get('/api/v1/tu-turno').json()
        self.assertEqual(turn['counts']['preguntas'],1)  # the undone one; postponed and expired do not count
        self.assertEqual({c['question']['id'] for c in turn['later']},{str(choice.id),str(late.id)})
        self.assertTrue(next(c for c in turn['later'] if c['question']['id']==str(late.id))['question']['expired'])

    def test_facts_show_their_origin_and_gustavo_can_add_one(self):
        q=preguntas.ask('director_editorial','¿Cuál fue tu primer cliente con IA?','Para un post','experiencia.primer_cliente_ia')
        self.human.post(f'/api/v1/preguntas/{q.id}/responder',{'text':'Una firma jurídica.','public_use':True},format='json')
        added=self.human.post('/api/v1/memoria/hechos',{'text':'No trabajo con apuestas.','public_use':False,'topic':'Límites'},format='json')
        self.assertEqual(added.status_code,201)
        facts={f['topic']:f for f in added.json()}
        self.assertEqual(facts['¿Cuál fue tu primer cliente con IA?']['origin']['agent_label'],'Director editorial')
        self.assertEqual((facts['Límites']['origin']['kind'],facts['Límites']['public_use']),('manual',False))
        key=facts['Límites']['key']
        self.human.post(f'/api/v1/memoria/hechos/{key}/corregir',{'text':'Nada de apuestas ni cripto.','public_use':False},format='json')
        edited=next(f for f in self.human.get('/api/v1/memoria/hechos').json() if f['key']==key)
        self.assertEqual((edited['edits'],edited['topic']),(2,'Límites'))


class PersonasAndCalendarTests(OperatorBase):
    def setUp(self):
        super().setUp();from django.contrib.auth.models import User
        self.fit=Contact.objects.create(account=self.account,provider_user_id='ACoana',display_name='Ana Founder',headline='Founder @ Tiny',
            source='commenter',stage='followed',followed_at=timezone.now()-timedelta(hours=10),
            classification={'fit':True,'role':'comprador','modality':'projectapp','reason':'r','confidence':0.9})

    def test_person_card_next_step_notes_opportunity_and_filters(self):
        card=self.human.get(f'/api/v1/red/contacts/{self.fit.id}').json()
        self.assertEqual((card['display_stage'],card['next_step']['owner']),('followed','equipo'))
        self.human.post(f'/api/v1/red/contacts/{self.fit.id}/notas',{'text':'La conocí en un evento'},format='json')
        self.human.post('/api/v1/oportunidades',{'contact':str(self.fit.id),'modality':'projectapp','stage':'reunion',
                                                  'next_action':'Reunión de alcance','next_action_at':timezone.now().isoformat()},format='json')
        card=self.human.get(f'/api/v1/red/contacts/{self.fit.id}').json()
        self.assertEqual((card['display_stage'],card['opportunity']['stage'],card['notes'][0]['text']),('opportunity','reunion','La conocí en un evento'))
        self.assertEqual(card['next_step']['owner'],'gustavo')
        self.assertEqual(len(self.human.get('/api/v1/red/contacts?stage=opportunity').json()['results']),1)
        self.assertEqual(len(self.human.get('/api/v1/red/contacts?q=tiny&role=comprador').json()['results']),1)
        self.assertEqual(self.human.get('/api/v1/red/summary').json()['stages']['opportunity'],1)

    def test_referents_can_be_deactivated_and_removed(self):
        self.observed()
        referent=self.human.get('/api/v1/operador/referents').json()['results'][0]
        self.assertEqual(referent['contacts_count'],0)
        off=self.human.patch(f'/api/v1/operador/referents/{referent["id"]}',{'active':False},format='json').json()
        self.assertFalse(off['active'])
        self.assertEqual(self.human.delete(f'/api/v1/operador/referents/{referent["id"]}').status_code,204)

    def test_adding_a_referent_linkedin_cannot_find_says_why_instead_of_a_500(self):
        # PRS-12: found by the QA flow 13-referentes. The provider's 404 used to escape as a server error.
        add=lambda identifier:self.human.post('/api/v1/operador/referents',{'account':str(self.account.id),'identifier':identifier,
                                                                             'reason':'Habla de producto'},format='json')
        missing=add('https://www.linkedin.com/in/nadie-con-este-perfil/')
        self.assertEqual(missing.status_code,400,missing.content)
        self.assertEqual(missing.json()['detail'],'No encontramos ese perfil en LinkedIn: revisa la URL.')
        with patch.object(FakeConnector,'get_user',side_effect=ConnectorError('Simulado: sin conexión.',kind='not_sent')):
            down=add('referente-ai')
        self.assertEqual(down.status_code,503,down.content)
        self.assertEqual(down.json()['detail'],'No se pudo consultar LinkedIn: Simulado: sin conexión.')
        self.assertFalse(Referent.objects.exists())
        self.assertEqual(add('referente-ai').status_code,201)

    def test_calendar_days_bring_counts_and_layered_events(self):
        post=self.observed()[0]
        self.approve(self.proposal(post))
        Contact.objects.create(account=self.account,provider_user_id='ACoeva',display_name='Eva',source='commenter',stage='connected',
                               connected_at=timezone.now(),classification={'fit':True,'role':'par'})
        q=preguntas.ask('director_editorial','¿Lideraste una migración?','Para el post del jueves','experiencia.migracion',deadline=timezone.now()+timedelta(hours=2))
        operador.set_global_pause(self.gustavo,True,'Prueba');operador.set_global_pause(self.gustavo,False)
        today=timezone.now().astimezone(operador.local_tz()).date()
        body=self.human.get(f'/api/v1/calendario?desde={today}&hasta={today+timedelta(days=3)}').json()
        day=next(d for d in body['days'] if d['date']==str(today))
        self.assertEqual((day['counts']['comments'],day['counts']['connections_fit']),(1,1))
        kinds={(e['layer'],e['kind']) for e in day['events']}
        self.assertTrue({('red','connection_fit'),('sistema','machine_paused'),('sistema','machine_resumed')}<=kinds,kinds)
        deadline_day=next(d for d in body['days'] if any(e['kind']=='deadline' for e in d['events']))
        self.assertEqual(next(e for e in deadline_day['events'] if e['kind']=='deadline')['link'],'/tu-turno')
        expected=[e for d in body['days'] for e in d['events'] if e['kind']=='invite_expected']
        self.assertEqual(expected[0]['people'][0]['name'],'Ana Founder');self.assertFalse(expected[0]['important'])
        self.assertEqual(self.human.get('/api/v1/calendario?desde=2026-01-01&hasta=2026-12-31').status_code,400)
