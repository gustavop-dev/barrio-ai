"""The weekly GASP strategy (estrategia.py, docs/plan-estrategia-semanal.md): the structure, the paid weekly plan, his
changes, the audience first, the public founder stories of P and the per-type findings."""
import os
import uuid
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from unittest import skipUnless
from unittest.mock import patch
from django.test import SimpleTestCase
from django.utils import timezone
from team_backend import editorial, estrategia, operador, research, resumen_semanal, urgente
from team_backend.models import Capture, EditorialPiece, Job, Notification, WeeklyPlan
from team_backend.tests.test_publicacion import EditorialBase, answers

MONDAY=date(2026,11,16)  # a normal week; the next one doubles S


class StructureTests(SimpleTestCase):
    def test_four_weeks_have_every_type_and_stay_near_40_30_20_10(self):
        weeks=[estrategia.allocate(MONDAY+timedelta(days=7*i)) for i in range(4)]
        for types in weeks:
            self.assertEqual(sorted(set(types)),['A','G','P','S']);self.assertEqual(estrategia.mix_warnings(types),[])
        self.assertEqual(sorted(t.count('S') for t in weeks),[1,1,2,2])  # a second S every other week
        share=estrategia.month_share(MONDAY)
        self.assertEqual({t:v['posts'] for t,v in share.items()},{'G':10,'A':8,'S':6,'P':4})
        for kind,value in share.items():self.assertLessEqual(abs(value['pct']-value['target_pct']),5,kind)

    def test_the_approved_week_and_its_settings(self):
        self.assertEqual(estrategia.allocate(MONDAY),['G','A','G','A','S','P','G'])
        self.assertEqual(estrategia.allocate(MONDAY+timedelta(days=7)),['G','A','G','A','S','P','S'])  # the Sunday G
        with patch.dict(os.environ,{'STRATEGY_WEEK_TEMPLATE':'G,A,X'}):self.assertEqual(estrategia.template(),list('GAGASPG'))
        with patch.dict(os.environ,{'STRATEGY_SALES_DOUBLE_EVERY':'0'}):
            self.assertEqual({tuple(estrategia.allocate(MONDAY+timedelta(days=7*i))) for i in range(4)},{tuple('GAGASPG')})
        self.assertEqual(len({estrategia.pain(MONDAY+timedelta(days=7*i))['key'] for i in range(len(estrategia.PAINS))}),
                         len(estrategia.PAINS))  # the pain of P rotates

    def test_mixture_warnings(self):
        self.assertEqual(estrategia.mix_warnings(list('SGAGAPG')),['La venta abre la semana: va mejor después de crecimiento y autoridad.'])
        self.assertIn('Dos posts de venta seguidos.',estrategia.mix_warnings(list('GASSAPG')))
        self.assertEqual(estrategia.mix_warnings(list('GAGAGAG')),['Falta un post de Venta esta semana.','Falta un post de Personal esta semana.'])

    def test_the_public_question_of_a_p_story_carries_only_the_pain(self):
        for key,_,_ in estrategia.PAINS:
            question=estrategia.story_question(key)
            with self.subTest(key=key):
                self.assertLessEqual(len(question),300);self.assertNotIn('Gustavo',question)
                self.assertEqual(research.safe_question(question),question)


class StrategyBase(EditorialBase):
    def setUp(self):
        super().setUp()
        env=patch.dict(os.environ,{'STRATEGY_ENABLED':'true'});env.start();self.addCleanup(env.stop)
        self.tz=operador.local_tz();self.today=timezone.now().astimezone(self.tz).date()
        self.next_monday=estrategia.week_start(self.today)+timedelta(days=7)

    def option(self,idea,evidence=None,fmt='foto'):
        return {'idea':idea,'reason':'Encaja con el tipo del día.','pillar':editorial.PILLARS[0],'modality':editorial.MODALITIES[0],
                'approach':editorial.APPROACH_UNITS[0],'format':fmt,'reader':editorial.READERS[0],
                'reader_need':'Decidir el alcance de su MVP esta semana.',
                'audience_evidence':evidence or {'kind':'comment_question','ref':'inventada','note':'Una señal que nadie ofreció.'}}

    def signal(self):
        return Capture.objects.create(created_by=self.gustavo,purpose='post',state='idea',
                                      note='Un comprador preguntó si un MVP necesita app móvil desde el primer día.')


class WeeklyPlanTests(StrategyBase):
    def raw(self,days,evidence,summary='Una semana para founders que dudan del alcance.'):
        return {'days':[{'date':d.isoformat(),'options':[self.option(f'Sin señal {d}'),self.option(f'Con señal {d}',evidence)]} for d in days],
                'summary':summary,'signals_read':[evidence['ref']]}

    def test_the_plan_keeps_the_types_prefers_audience_evidence_and_keeps_his_changes(self):
        signal=self.signal();monday=self.next_monday;days=[monday+timedelta(days=i) for i in range(7)]
        estrategia.change(self.gustavo,days[1],'P')  # he turns Tuesday into a personal day before the plan
        backed={'kind':'owner_capture','ref':str(signal.id),'note':'Un comprador duda del alcance de un MVP.'}
        with self.claude({'plan':self.raw(days,backed)}):plan=estrategia.run(self.gustavo,monday,origin_job='job-test')
        expected=estrategia.allocate(monday);expected[1]='P'
        self.assertEqual([s['type'] for s in plan.slots],expected)  # the model plans ideas, never types
        self.assertEqual((plan.state,plan.summary,plan.cost_usd),('planeada','Una semana para founders que dudan del alcance.',Decimal('0.01')))
        [(purpose,data,system)]=self.calls
        self.assertEqual(purpose,'editorial-plan');self.assertIn('la audiencia primero',system)
        self.assertEqual([d['locked'] for d in data['week']['days']],[False,True,False,False,False,False,False])
        self.assertEqual(data['audience_signals']['owner_capture'][0]['id'],str(signal.id))
        tuesday=plan.slots[1];self.assertEqual((tuesday['idea'],tuesday['owner_edited']),('',True))
        for slot in plan.slots[:1]+plan.slots[2:]:
            self.assertEqual((slot['idea'],slot['audience_evidence'],slot['evidence_ok']),(f'Con señal {slot["date"]}',backed,True))
        self.assertTrue(any(s['format']=='carrusel' and s['type']=='A' for s in plan.slots))  # the week's carousel, by code
        self.assertTrue(any('más de tres veces' in w for w in plan.warnings))
        self.assertEqual(len(plan.signals['used']),6)
        self.assertTrue(Notification.objects.filter(kind='weekly_plan',title='La semana ya tiene plan').exists())
        # His later changes: a changed day keeps its idea for later; a discarded one stays discarded on a new plan.
        estrategia.change(self.gustavo,days[3],'G');estrategia.change(self.gustavo,days[2],discard=True)
        plan.refresh_from_db()
        self.assertEqual(plan.kept_ideas[-1]['idea'],f'Con señal {days[3].isoformat()}')
        self.assertEqual((plan.slots[3]['type'],plan.slots[3]['idea'],plan.slots[3]['type_reason']),('G','','Lo cambiaste tú'))
        self.calls.clear()
        with self.claude({'plan':self.raw(days,backed,'Otra semana.')}):plan=estrategia.run(self.gustavo,monday)
        self.assertEqual(self.calls[0][1]['kept_ideas'][-1]['idea'],f'Con señal {days[3].isoformat()}')
        self.assertEqual((plan.slots[2]['state'],plan.slots[2]['idea']),('discarded',''))
        self.assertEqual(plan.cost_usd,Decimal('0.02'))

    def test_an_idea_without_audience_evidence_is_kept_but_flagged(self):
        monday=self.next_monday;days=[monday+timedelta(days=i) for i in range(7)]
        raw={'days':[{'date':d.isoformat(),'options':[self.option(f'Sin señal {d}')]} for d in days],'summary':'','signals_read':[]}
        with self.claude({'plan':raw}):plan=estrategia.run(self.gustavo,monday)
        self.assertTrue(all(s['audience_evidence'] is None and not s['evidence_ok'] for s in plan.slots))
        self.assertTrue(any('sin señal de la audiencia' in w for w in plan.warnings))

    def test_the_plan_is_queued_once_on_sunday_afternoon(self):
        sunday=self.today+timedelta(days=(6-self.today.weekday())%7)
        at=lambda day,hour:datetime.combine(day,time(hour,0),tzinfo=self.tz)
        self.assertEqual(estrategia.queue(self.autobot,at(sunday,15)),0)
        self.assertEqual(estrategia.queue(self.autobot,at(sunday-timedelta(days=1),17)),0)
        with patch.dict(os.environ,{'STRATEGY_ENABLED':'false'}):self.assertEqual(estrategia.queue(self.autobot,at(sunday,17)),0)
        with patch.dict(os.environ,{'OPERATOR_AUTONOMY':'CONT-09=off'}):self.assertEqual(estrategia.queue(self.autobot,at(sunday,17)),0)
        self.assertEqual(estrategia.queue(self.autobot,at(sunday,17)),1)
        self.assertEqual(Job.objects.get(kind='plan_week').params['week'],(sunday+timedelta(days=1)).isoformat())
        self.assertEqual(estrategia.queue(self.autobot,at(sunday,18)),0)  # once

    def test_the_week_in_the_app(self):
        monday=self.next_monday;days=[monday+timedelta(days=i) for i in range(7)]
        body=self.human.get(f'/api/v1/estrategia/semana?dia={days[2]}').json()
        self.assertEqual((body['week_start'],body['state'],body['enabled']),(monday.isoformat(),'estructura',True))
        self.assertEqual([d['type'] for d in body['days']],estrategia.allocate(monday))
        self.assertEqual(body['month_share'],estrategia.month_share(estrategia.week_start(self.today)))
        self.assertGreater(body['regenerate']['max_usd'],body['regenerate']['estimated_usd'])
        # Change a type, discard an idea, swap two days.
        response=self.human.patch(f'/api/v1/estrategia/dias/{days[0]}',{'tipo':'S'},format='json')
        self.assertEqual(response.status_code,200,response.content)
        self.assertEqual((response.json()['days'][0]['type'],response.json()['days'][0]['owner_edited']),('S',True))
        self.assertIn('La venta abre la semana: va mejor después de crecimiento y autoridad.',response.json()['warnings'])
        self.assertEqual(self.human.patch(f'/api/v1/estrategia/dias/{days[0]}',{},format='json').status_code,400)
        self.assertEqual(self.human.patch(f'/api/v1/estrategia/dias/{days[0]}',{'tipo':'X'},format='json').status_code,400)
        self.assertEqual(self.human.patch(f'/api/v1/estrategia/dias/{self.today-timedelta(days=1)}',{'tipo':'G'},format='json').status_code,409)
        response=self.human.post('/api/v1/estrategia/mover',{'desde':days[0].isoformat(),'hasta':days[5].isoformat()},format='json')
        self.assertEqual(response.status_code,200,response.content)
        self.assertEqual((response.json()['days'][0]['type'],response.json()['days'][5]['type']),('P','S'))
        self.assertEqual(self.human.post('/api/v1/estrategia/mover',{'desde':days[0].isoformat(),'hasta':(days[0]+timedelta(days=7)).isoformat()},
                                         format='json').status_code,400)
        # A prepared day keeps its type.
        EditorialPiece.objects.create(account=self.official,slot_date=days[4],scheduled_for=editorial.scheduled_for(days[4]),state='ready')
        self.assertEqual(self.human.patch(f'/api/v1/estrategia/dias/{days[4]}',{'tipo':'G'},format='json').status_code,409)
        self.assertFalse(next(d for d in self.human.get(f'/api/v1/estrategia/semana?dia={monday}').json()['days'] if d['date']==days[4].isoformat())['editable'])
        history=WeeklyPlan.objects.get(week_start=monday).history
        self.assertEqual([h['event'] for h in history],['changed','swapped'])

    def test_planning_again_is_one_paid_job_for_this_week_or_the_next(self):
        request_id=str(uuid.uuid4())
        response=self.human.post('/api/v1/estrategia/planear',{'semana':self.next_monday.isoformat(),'request_id':request_id},format='json')
        self.assertEqual(response.status_code,202,response.content)
        self.assertEqual(response.json()['job']['kind'],'plan_week')
        self.assertEqual(self.human.post('/api/v1/estrategia/planear',{'semana':self.next_monday.isoformat(),'request_id':request_id},
                                         format='json').status_code,200)  # the same request
        self.assertEqual(self.human.post('/api/v1/estrategia/planear',{'semana':self.next_monday.isoformat()},format='json').status_code,409)
        self.assertEqual(self.human.post('/api/v1/estrategia/planear',{'semana':(self.next_monday+timedelta(days=14)).isoformat()},
                                         format='json').status_code,409)

    def test_the_calendar_shows_the_type_of_each_day(self):
        start=self.today;end=self.today+timedelta(days=6)
        piece_day=self.today+timedelta(days=1)
        EditorialPiece.objects.create(account=self.official,slot_date=piece_day,scheduled_for=editorial.scheduled_for(piece_day),
                                      state='ready',brief={'gasp_type':'P'})
        days={d['date']:d['gasp'] for d in self.human.get(f'/api/v1/calendario?desde={start}&hasta={end}').json()['days']}
        self.assertEqual(days[piece_day.isoformat()]['type'],'P')  # the type its post carried
        for offset in (0,2,3,4,5,6):
            day=self.today+timedelta(days=offset)
            self.assertEqual(days[day.isoformat()]['type'],estrategia.allocate(estrategia.week_start(day))[day.weekday()])
        with patch.dict(os.environ,{'STRATEGY_ENABLED':'false'}):
            days=self.human.get(f'/api/v1/calendario?desde={start}&hasta={end}').json()['days']
        self.assertTrue(all(d['gasp'] is None for d in days))

    def test_the_weekly_summary_says_which_signals_moved_the_next_plan(self):
        monday=estrategia.week_start(self.today)
        self.assertFalse(resumen_semanal.next_plan(monday)['disponible'])
        WeeklyPlan.objects.create(week_start=monday+timedelta(days=7),state='planeada',summary='Más dudas de alcance.',
            signals={'used':[{'date':(monday+timedelta(days=7)).isoformat(),'type':'A','kind':'comment_question','ref':'c1','note':'Preguntan por el alcance.'}]})
        found=resumen_semanal.next_plan(monday)
        self.assertEqual((found['disponible'],found['resumen']),(True,'Más dudas de alcance.'))
        self.assertEqual(found['senales_usadas'],[{'fecha':(monday+timedelta(days=7)).isoformat(),'tipo':'A','senal':'comment_question',
                                                  'nota':'Preguntan por el alcance.'}])
        self.assertFalse(resumen_semanal.by_type(resumen_semanal.window(monday),timezone.now(),True)['disponible'])


class IdeaTypeTests(StrategyBase):
    def test_a_typed_idea_takes_the_nearest_day_of_its_type_and_the_planned_idea_waits(self):
        for monday in (estrategia.week_start(self.today),self.next_monday):
            plan=estrategia.ensure(monday)
            WeeklyPlan.objects.filter(pk=plan.pk).update(slots=[dict(s,idea=f'Planeada {s["date"]}') for s in plan.slots])
        c=Capture.objects.create(created_by=self.gustavo,purpose='post',state='idea',note='Hoy sentí miedo antes de lanzar.',
                                 understanding={'gasp_type':'P'})
        urgente.assign_slots();c.refresh_from_db()
        day=c.publish_asap_expected_slot.astimezone(self.tz).date()
        self.assertEqual(estrategia.day_type(day),'P');self.assertIn('personal más cercano',c.publish_asap_reason)
        plan=WeeklyPlan.objects.get(week_start=estrategia.week_start(day))
        slot=next(s for s in plan.slots if s['date']==day.isoformat())
        self.assertEqual((slot['capture_id'],slot['state']),(str(c.id),'capture'))
        self.assertEqual(plan.kept_ideas,[{'date':day.isoformat(),'type':'P','idea':f'Planeada {day}','reader_need':'','audience_evidence':None}])
        # An idea without a clear type takes the first free day and is written for that day's type.
        other=Capture.objects.create(created_by=self.gustavo,purpose='post',state='idea',note='Una idea sobre alcance.')
        urgente.assign_slots();other.refresh_from_db()
        kind=estrategia.day_type(other.publish_asap_expected_slot.astimezone(self.tz).date())
        self.assertTrue(other.publish_asap_reason.startswith(f'Se escribe como post de {estrategia.LABELS[kind].lower()}'))


class PersonalStoryTests(StrategyBase):
    """P without his material: a public, sourced story of a founder about the week's pain (Gustavo 14/11/2026)."""
    STORY={'protagonist':'Ana Ejemplo','company':'Ejemplo Labs','source_ref':'web:historia','pain':'miedo_a_fracasar',
           'summary':'Contó en un podcast que casi cierra antes de lanzar.'}
    SOURCE='In a podcast, Ana Ejemplo, cofounder of Ejemplo Labs, said: we almost shut the company down before launch.'
    TOLD=('Ana Ejemplo, cofounder of Ejemplo Labs, almost shut the company down before launch. The fear was loudest right '
          'before the first users arrived. Fear does not mean the idea is wrong; it often means the stakes are finally real. '
          'What would you need to hear to keep going?')

    def setUp(self):
        super().setUp()
        env=patch.dict(os.environ,{'STRATEGY_WEEK_TEMPLATE':'P,P,P,P,P,P,P','STRATEGY_SALES_DOUBLE_EVERY':'0'})
        env.start();self.addCleanup(env.stop)
        self.requests=[]

    def found(self,request):
        self.requests.append(request);at=timezone.now().isoformat()
        return research.ResearchResult(request.public_question,'complete',at,
            (research.Finding('A founder almost shut her company down before launch.',('web:historia',)),),
            (research.Source('web:historia','https://example.com/podcast','Ejemplo Labs podcast',self.SOURCE,at),),
            usage={'model':'claude-sonnet-5-5','estimated_usd':0.05})

    def story_plan(self,final,**story):
        plan=answers(final=final);plan['director'].update(gasp_type='P',story=dict(self.STORY,**story))
        return plan

    def test_a_p_day_researches_one_public_story_with_only_the_pain_and_tells_it_attributed(self):
        with patch.object(estrategia,'story_research_available',return_value=True),\
             patch('team_backend.research.research',side_effect=self.found):
            piece=self.plan(self.story_plan(self.TOLD))
        self.assertEqual(piece.state,'ready',piece.note)
        [request]=self.requests;pain=piece.brief['pain']
        self.assertEqual(request.public_question,estrategia.story_question(pain))
        self.assertEqual(research.safe_question(request.public_question),request.public_question)
        purposes=[c[0] for c in self.calls];self.assertEqual(purposes.count('editorial-director'),1)  # no second research
        strategy=self.calls[0][1]['strategy']
        self.assertEqual((strategy['type'],strategy['owner_personal_material'],strategy['pain']['key']),('P',False,pain))
        self.assertTrue(self.calls[0][1]['research_completed'])
        self.assertEqual((piece.brief['gasp_type'],piece.brief['story']['protagonist']),('P','Ana Ejemplo'))
        self.assertTrue(any(u.get('reason')=='historia_p' for u in piece.usage))
        self.assertEqual([s['protagonist'] for s in estrategia.used_stories()],['Ana Ejemplo'])
        # The next P post cannot tell it again: the director sees it and a repeat travels as a risk.
        self.assertEqual(estrategia.director_input(EditorialPiece(slot_date=self.today),[],None,timezone.now())['used_stories'][0]['protagonist'],
                         'Ana Ejemplo')

    def test_a_story_told_as_his_with_an_invented_quote_and_no_source_never_goes_out(self):
        final='I almost shut my company down before launch. As Ana said: "fear is the price of building something real".'
        with patch.object(estrategia,'story_research_available',return_value=True),\
             patch('team_backend.research.research',side_effect=self.found):
            piece=self.plan(self.story_plan(final,source_ref='web:otra'))
        self.assertEqual(piece.state,'blocked')
        self.assertEqual({estrategia.code(r) for r in piece.verification['rules']}-{None},
                         {'unsourced_third_party_story','first_person_appropriation','fabricated_quote'})
        self.assertNotIn('editorial-verificador',[c[0] for c in self.calls])  # the rules stop it first

    def test_his_own_material_wins_and_nothing_is_researched(self):
        c=Capture.objects.create(created_by=self.gustavo,purpose='post',state='idea',understanding={'gasp_type':'P'},
                                 note='Hoy casi no lanzo por miedo; lo hice igual.')
        plan=answers();plan['director'].update(gasp_type='P',ideas_used=[str(c.id)])
        with patch.object(estrategia,'story_research_available',return_value=True),\
             patch('team_backend.research.research') as web:
            piece=self.plan(plan)
        self.assertEqual(web.call_count,0);self.assertEqual(piece.state,'ready',piece.note)
        self.assertTrue(self.calls[0][1]['strategy']['owner_personal_material'])
        self.assertNotIn('story',piece.brief)


class FindingTests(StrategyBase):
    SOURCE={'question':'q','status':'complete','researched_at':'2026-11-14T00:00:00+00:00','findings':[],'limitations':[],'usage':{},
            'schema_version':1,'sources':[{'id':'web:historia','url':'https://example.com/podcast','title':'Ejemplo Labs podcast',
                                           'quoted_text':'Ana Ejemplo said: we almost shut the company down before launch.',
                                           'retrieved_at':'2026-11-14T00:00:00+00:00','kind':'web','truncated':False}]}
    STORY={'protagonist':'Ana Ejemplo','company':'Ejemplo Labs','source_ref':'web:historia','pain':'miedo_a_fracasar','summary':'x'}

    def codes(self,kind,text,**brief):
        piece=EditorialPiece(slot_date=self.today,brief={'gasp_type':kind,'reader_value':'Una pregunta útil.',**brief},research=[self.SOURCE])
        return [estrategia.code(i) for i in estrategia.findings(piece,text)]

    def test_findings_by_type(self):
        self.assertEqual(self.codes('S','Escríbeme si te pasa. Also, comment below.'),['cta_count'])
        self.assertEqual(self.codes('S','Escríbeme si te pasa.'),[])  # one invitation to talk is the Sales post
        self.assertEqual(self.codes('P','Tell me in the comments.'),['cta_count'])
        self.assertEqual(self.codes('G','Work with me on your MVP.'),['offer_in_growth'])
        self.assertEqual(self.codes('P','Hire me for your next build.'),['offer_in_personal'])
        self.assertEqual(self.codes('A','A framework to scope an MVP.'),[])
        self.assertEqual(self.codes(None,'Work with me. Tell me in the comments.'),[])  # no GASP type: nothing here
        told='Ana Ejemplo said: «we almost shut the company down before launch». Fear means the stakes are real.'
        self.assertEqual(self.codes('P',told,story=self.STORY),[])  # a quote that is in the source
        self.assertEqual(self.codes('P',told,story=dict(self.STORY,source_ref='web:otra')),['unsourced_third_party_story'])
        self.assertEqual(self.codes('P','I almost shut my company down before launch.',story=self.STORY),['first_person_appropriation'])
        self.assertEqual(self.codes('P','Ana Ejemplo once said: «fear is the price of building anything».',story=self.STORY),['fabricated_quote'])
        self.assertEqual({k for k,v in estrategia.SEVERITY.items() if v=='hard'},
                         {'unsourced_third_party_story','fabricated_quote','first_person_appropriation'})

    def test_what_the_brief_decided_is_a_risk_never_a_block(self):
        piece=EditorialPiece(slot_date=self.today,brief={'gasp_type':'A','reader_value':''})
        self.assertEqual([estrategia.code(n) for n in estrategia.notes(piece)],['no_reader_need'])
        piece.brief={'gasp_type':'A','reader_value':'Una pregunta útil.','audience_evidence_missing':True}
        self.assertEqual([estrategia.code(n) for n in estrategia.notes(piece)],['no_reader_need'])
        EditorialPiece.objects.create(account=self.official,slot_date=self.today-timedelta(days=7),scheduled_for=timezone.now()-timedelta(days=7),
                                      state='ready',brief={'gasp_type':'P','story':self.STORY})
        piece.brief={'gasp_type':'P','reader_value':'Una pregunta útil.','story':self.STORY}
        self.assertEqual([estrategia.code(n) for n in estrategia.notes(piece)],['repeated_story'])
        self.assertEqual(estrategia.findings(piece,'Ana Ejemplo almost shut Ejemplo Labs down.'),[])

    def test_the_code_keeps_the_type_and_the_audience_evidence_honest(self):
        signals={'owner_capture':[{'id':'c1','text':'x'}],'comment_question':[],'referent_outlier':[],'results_by_type':[]}
        valid={'kind':'owner_capture','ref':'c1','note':'Un comprador preguntó.'}
        strategy={'extra':False,'type':'A','audience_signals':signals,
                  'planned':{'reader_need':'Decidir el alcance.','audience_evidence':valid}}
        brief=estrategia.finalize_brief({'gasp_type':'G','audience_evidence':{'kind':'owner_capture','ref':'inventada','note':''},
                                         'story':self.STORY,'reader_value':'Otra cosa.'},strategy)
        self.assertEqual((brief['gasp_type'],brief['audience_evidence'],brief['reader_need'],brief['audience_evidence_missing']),
                         ('A',valid,'Decidir el alcance.',False))
        self.assertNotIn('story',brief)  # only a P post tells a founder's story
        brief=estrategia.finalize_brief({'reader_value':'Algo.'},dict(strategy,planned=None))
        self.assertEqual((brief['audience_evidence'],brief['audience_evidence_missing']),(None,True))
        brief=estrategia.finalize_brief({'gasp_type':'S','reader_value':'Algo.'},{'extra':True,'type':None,'audience_signals':{}})
        self.assertEqual((brief['gasp_type'],brief['audience_evidence_missing']),('S',False))  # no signals yet: not punished


class SalesGateTests(StrategyBase):
    """TODO(gate_policy): a Sales post may carry ONE invitation to talk, which POST_PITCH and aggressive_pitch still block.
    These pass once gate_policy(piece) lands (branch feat/compuertas-auditoria-reintento) and are skipped until then."""
    @skipUnless(hasattr(editorial,'gate_policy'),'gate_policy aún no existe (feat/compuertas-auditoria-reintento)')
    def test_a_sales_post_with_one_invitation_to_talk_goes_out(self):
        piece=EditorialPiece(slot_date=self.today,brief={'gasp_type':'S','reader_value':'Una pregunta útil.'})
        self.assertEqual(estrategia.findings(piece,'Si te pasa con tu MVP, escríbeme.'),[])
        self.assertIsNotNone(editorial.gate_policy(piece))  # its exact shape is gate_policy's; one CTA must not block S

    @skipUnless(hasattr(editorial,'gate_policy'),'gate_policy aún no existe (feat/compuertas-auditoria-reintento)')
    def test_a_sales_post_with_two_invitations_is_repaired_and_else_kept_as_a_risk(self):
        piece=EditorialPiece(slot_date=self.today,brief={'gasp_type':'S','reader_value':'Una pregunta útil.'})
        issues=estrategia.findings(piece,'Escríbeme. Also, comment below.')
        self.assertEqual([estrategia.code(i) for i in issues],['cta_count'])
        self.assertEqual(estrategia.SEVERITY['cta_count'],'soft')
