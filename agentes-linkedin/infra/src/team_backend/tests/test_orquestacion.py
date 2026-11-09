"""Phase 3b: fake tools only. No provider or LinkedIn network access."""
from contextvars import Context
from copy import deepcopy
from datetime import timedelta
from decimal import Decimal
import ast
import inspect
import os
import uuid
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import TransactionTestCase
from django.utils import timezone
from knowledge import providers
from team_backend import editorial, operador, orquestacion as runtime
from team_backend.grafo import load_graph, validate_graph
from team_backend.models import AuditEvent, CycleLedger, Job, UsageEntry, Worker


REQUEST = {'piece': 'synthetic-piece', 'stage': 'seleccion', 'units': [],
           'payload': {'brief': {}, 'variants': {}, 'panel': {}}}
SELECTION = {'decision': 'discard', 'final_text': '', 'rationale': 'No evidence', 'claims': [],
             'resolved_objections': [], 'kept_objections': [], 'citations': []}
RESULT = (SELECTION, 'fake-model')


class DispatcherTests(TransactionTestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('cycle-owner')
        self.job = Job.objects.create(owner=self.user, kind='prepare_piece', agent='operador', task='synthetic')
        self.graph = load_graph()
        self.loader = patch('team_backend.orquestacion.load_graph', side_effect=lambda:deepcopy(self.graph))
        self.loader.start();self.addCleanup(self.loader.stop)
        self.notice = patch('team_backend.notificaciones.avisar')
        self.notify = self.notice.start();self.addCleanup(self.notice.stop)
        UsageEntry.objects.all().delete()
        self.env = patch.dict(os.environ, {'ANTHROPIC_LIMIT_USD':'100','EDITORIAL_DAILY_LLM_USD':'2'})
        self.env.start();self.addCleanup(self.env.stop)

    def open(self, key=None, cycle='pieza_diaria'):
        return runtime.Runtime.open(cycle,key or str(uuid.uuid4()),self.user,self.job,
                                    facts={'source':'PRIVATE'},plan=['selection'])

    def cycle(self, cid='pieza_diaria'):
        return next(c for c in self.graph['cycles'] if c['id']==cid)

    def edge(self, eid='seleccionar'):
        return next(e for e in self.graph['edges'] if e['id']==eid)

    def test_allowed_call_validates_and_emits_real_handoff(self):
        run = self.open()
        fake = Mock(return_value=RESULT)
        with run.session():
            self.assertEqual(run.call('seleccionar',REQUEST,fake),RESULT)
        fake.assert_called_once()
        row = CycleLedger.objects.get(pk=run.id)
        self.assertEqual(row.calls,1)
        self.assertEqual(row.progress_ledger['calls']['seleccionar:1']['state'],'answered')
        self.assertEqual(row.task_ledger['facts'],{'source':'PRIVATE'})
        events = list(AuditEvent.objects.filter(action='office.event').values_list('metadata',flat=True))
        self.assertEqual([(e['rol'],e['destino']) for e in events],
                         [('director_editorial','seleccion_editorial'),('seleccion_editorial','director_editorial')])
        self.assertNotIn('PRIVATE',str(events))

    def test_missing_foreign_and_planned_edges_fail_before_tool(self):
        for edge in ('invented','observar','visual_futuro'):
            run = self.open();fake = Mock()
            with run.session(),self.assertRaises(runtime.UndeclaredCall):
                run.call(edge,REQUEST,fake)
            fake.assert_not_called()
            self.assertTrue(AuditEvent.objects.filter(target=str(run.id),action='cycle.rejected').exists())

    def test_specialist_cannot_delegate_even_back_to_owner(self):
        run = self.open();nested = Mock(return_value=RESULT)
        with run.session(),self.assertRaisesRegex(runtime.UndeclaredCall,'max_depth'):
            run.call('seleccionar',REQUEST,lambda:run.call('seleccionar',REQUEST,nested))
        nested.assert_not_called()

    def test_request_and_response_are_typed(self):
        run = self.open();fake = Mock()
        with run.session(),self.assertRaisesRegex(runtime.UndeclaredCall,'request_schema'):
            run.call('seleccionar',{},fake)
        fake.assert_not_called()
        run = self.open()
        with run.session(),self.assertRaisesRegex(ValueError,'schema'):
            run.call('seleccionar',REQUEST,lambda:({'decision':True},'fake'))
        self.assertTrue(AuditEvent.objects.filter(target=str(run.id),action='cycle.rejected').exists())

    def test_second_worker_cannot_take_an_active_instance(self):
        run = self.open(key='same')
        second = self.open(key='same')
        def competing():
            with second.session():self.fail('Two workers acquired one cycle')
        with run.session():
            with self.assertRaises(runtime.CycleStopped):Context().run(competing)
            self.assertEqual(run.call('seleccionar',REQUEST,lambda:RESULT),RESULT)
        self.assertEqual(CycleLedger.objects.filter(key='same').count(),1)

    def test_resume_reuses_confirmed_response_without_calling_tool(self):
        run = self.open(key='resume')
        with run.session():
            run.call('seleccionar',REQUEST,lambda:RESULT)
        again = self.open(key='resume');fake = Mock(side_effect=AssertionError('Paid replay'))
        with again.session():
            self.assertEqual(again.call('seleccionar',REQUEST,fake),RESULT)
        fake.assert_not_called()
        self.assertEqual(CycleLedger.objects.get(pk=run.id).calls,1)

    def test_changed_checkpoint_is_not_silently_reused(self):
        run = self.open(key='changed')
        with run.session():run.call('seleccionar',REQUEST,lambda:RESULT)
        again = self.open(key='changed')
        with again.session(),self.assertRaisesRegex(runtime.CycleStopped,'checkpoint_changed'):
            again.call('seleccionar',dict(REQUEST,payload={'brief':{'changed':True},'variants':{},'panel':{}}),lambda:RESULT)

    def test_crash_in_flight_is_not_replayed(self):
        run = self.open(key='in-flight')
        def crash():raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt),run.session():
            run.call('seleccionar',REQUEST,crash)
        again = self.open(key='in-flight');fake = Mock()
        with again.session(),self.assertRaisesRegex(runtime.CycleStopped,'uncertain'):
            again.call('seleccionar',REQUEST,fake)
        fake.assert_not_called()
        self.assertTrue(CycleLedger.objects.get(pk=run.id).needs_attention)

    def test_edge_and_global_limits_survive_resume(self):
        self.cycle()['limits']['max_calls']=1
        run = self.open(key='limit')
        with run.session():run.call('seleccionar',REQUEST,lambda:RESULT)
        again = self.open(key='limit')
        with again.session(),self.assertRaisesRegex(runtime.CycleStopped,'max_calls'):
            again.call('seleccionar',REQUEST,lambda:RESULT,key='new-attempt')
        self.cycle()['limits']['max_calls']=40
        run = self.open()
        with run.session():
            run.call('seleccionar',REQUEST,lambda:RESULT)
            with self.assertRaisesRegex(runtime.CycleStopped,'edge_limit'):
                run.call('seleccionar',REQUEST,lambda:RESULT)

    def test_late_result_is_not_applied_and_cycle_deadline_survives_resume(self):
        run = self.open()
        start = timezone.now()
        clock=[start]
        def late():
            clock[0]=start+timedelta(seconds=121)
            return RESULT
        with run.session(),patch('team_backend.orquestacion.timezone.now',side_effect=lambda:clock[0]):
            with self.assertRaisesRegex(runtime.CycleStopped,'call_timeout'):
                run.call('seleccionar',REQUEST,late)
        row = CycleLedger.objects.get(pk=run.id)
        self.assertEqual(row.progress_ledger['calls']['seleccionar:1']['state'],'pending')
        run = self.open()
        CycleLedger.objects.filter(pk=run.id).update(active_seconds=run.limits['cycle_timeout_s'])
        with run.session(),self.assertRaisesRegex(runtime.CycleStopped,'cycle_timeout'):
            run.call('seleccionar',REQUEST,lambda:RESULT)

    def test_stall_replans_once_then_escalates_and_waits_do_not_count(self):
        run = self.open()
        with run.session():
            run.progress('same')
            for _ in range(4):run.progress('same',waiting=True)
            run.progress('same');run.progress('same',replan=['Check missing evidence'])
            row = CycleLedger.objects.get(pk=run.id)
            self.assertEqual(row.task_ledger['plan_version'],2)
            run.progress('same')
            with self.assertRaisesRegex(runtime.CycleStopped,'stall'):
                run.progress('same',replan=['A second replan is forbidden'])
        self.assertEqual(CycleLedger.objects.get(pk=run.id).progress_ledger['replans'],1)
        self.notify.assert_called_once()

    def test_provider_reservation_counts_uncertain_and_confirmed_once(self):
        self.edge()['max_calls_per_cycle']=2
        self.cycle()['limits']['cost_cap_usd']=0.25
        run = self.open()
        def paid():
            rid=providers.reserve('anthropic','editorial-seleccion',Decimal('.20'))
            providers.settle(rid,'complete',cost=Decimal('.10'))
            return RESULT
        with run.session():
            run.call('seleccionar',REQUEST,paid)
            # Settled .10 replaces reserved .20; the next .15 fits exactly.
            def last():
                providers.reserve('anthropic','editorial-seleccion',Decimal('.15'))
                return RESULT
            with self.assertRaisesRegex(runtime.CycleStopped,'cost_cap'):
                run.call('seleccionar',REQUEST,last)
        self.assertEqual(runtime.amount(UsageEntry.objects.all()),Decimal('.25'))
        self.assertEqual(UsageEntry.objects.filter(usage__cycle_id=str(run.id)).count(),2)
        self.notify.assert_called_once()

    def test_reservation_over_cap_fails_before_provider_or_ledger_insert(self):
        self.cycle()['limits']['cost_cap_usd']=0.1
        run=self.open()
        with run.session(),self.assertRaisesRegex(runtime.CycleStopped,'cost_cap'):
            run.call('seleccionar',REQUEST,lambda:providers.reserve('anthropic','editorial-seleccion',Decimal('.11')))
        self.assertFalse(UsageEntry.objects.exists())

    def test_undeclared_provider_and_provider_outside_tool_are_audited(self):
        run=self.open()
        with run.session(),self.assertRaises(runtime.UndeclaredCall):
            providers.reserve('anthropic','editorial-seleccion',Decimal('.01'))
        run=self.open()
        with run.session(),self.assertRaises(runtime.UndeclaredCall):
            run.call('seleccionar',REQUEST,lambda:providers.reserve('openai','image-edit',Decimal('.01')))
        self.assertFalse(UsageEntry.objects.exists())

    def test_registry_change_stops_existing_instance(self):
        self.open(key='pinned')
        self.graph['graph_version']='next'
        with self.assertRaises(runtime.CycleStopped):self.open(key='pinned')
        self.assertEqual(CycleLedger.objects.get(key='pinned').stop_reason,'graph_changed')

    def test_stale_worker_requeues_only_confirmed_checkpoints(self):
        from team_backend.jobs import reconcile_interrupted
        from django.conf import settings
        worker=Worker.objects.create(last_seen=timezone.now()-timedelta(seconds=settings.WORKER_STALE_SECONDS+1))
        run=self.open()
        with run.session():run.call('seleccionar',REQUEST,lambda:RESULT)
        self.job.state='running';self.job.worker=worker;self.job.save()
        reconcile_interrupted();self.job.refresh_from_db()
        self.assertEqual(self.job.state,'queued')
        row=CycleLedger.objects.get(pk=run.id)
        row.progress_ledger['calls']['seleccionar:1']['state']='pending';row.save()
        self.job.state='running';self.job.worker=worker;self.job.save()
        reconcile_interrupted();self.job.refresh_from_db()
        self.assertEqual(self.job.state,'interrupted')
        self.assertEqual(CycleLedger.objects.get(pk=run.id).stop_reason,'uncertain')

    def test_map_reads_ledger_metadata_with_owner_filter(self):
        from team_backend.grafo_views import recent_activity
        run=self.open()
        with run.session():run.call('seleccionar',REQUEST,lambda:RESULT)
        data=recent_activity(self.graph,self.user)['seleccion_editorial']['records']
        self.assertEqual(data[0]['cycle_id'],str(run.id))
        self.assertNotIn('PRIVATE',str(data))
        other=get_user_model().objects.create_user('other-cycle-owner')
        self.assertEqual(recent_activity(self.graph,other)['seleccion_editorial']['records'],[])

    def test_workflow_calls_are_declared_and_not_direct_provider_calls(self):
        validate_graph(self.graph)
        edges={e['id'] for e in self.graph['edges'] if e.get('runtime')}
        declared=self.graph['code_bindings']
        self.assertLessEqual(set(declared['editorial_edges'].values()),edges)
        self.assertLessEqual(set(declared['network_edges'].values()),edges)
        for function in (editorial._run,editorial._check,editorial._repair_round,operador._run_job):
            tree=ast.parse(inspect.getsource(function))
            for call in (n for n in ast.walk(tree) if isinstance(n,ast.Call)):
                if isinstance(call.func,ast.Attribute) and isinstance(call.func.value,ast.Name):
                    self.assertNotEqual(call.func.value.id,'providers')
                if isinstance(call.func,ast.Name):self.assertNotEqual(call.func.id,'_stage')

    def test_grouped_writers_are_one_call_and_two_authorized_edges(self):
        run=self.open()
        variant={'angle':'criterion','text':'Synthetic text','claims':[],'uncertainties':[]}
        result=({'variant_a':variant,'variant_b':variant,'citations':[]},'fake')
        request={'piece':'synthetic','stage':'redactor','units':[],'payload':{'brief':{},'sources':[]}}
        with run.session():run.call('redactar_a',request,lambda:result)
        row=CycleLedger.objects.get(pk=run.id)
        self.assertEqual(row.calls,1)
        self.assertEqual(row.progress_ledger['calls']['redactar_a:1']['edges'],['redactar_a','redactar_b'])

    def test_monthly_bucket_is_shared_by_separate_instances(self):
        self.cycle('red')['limits'].update(cost_period='month',cost_cap_usd=1)
        request={'job':str(self.job.id),'kind':'classify_contacts','params':{}}
        first=self.open(cycle='red');second=self.open(cycle='red')
        def paid(amount):
            providers.reserve('anthropic','network-classify',Decimal(amount))
            return {'classified':1,'fit':1}
        with first.session():first.call('clasificar',request,lambda:paid('.80'))
        with second.session(),self.assertRaisesRegex(runtime.CycleStopped,'cost_cap'):
            second.call('clasificar',request,lambda:paid('.25'))
        self.assertEqual(UsageEntry.objects.count(),1)
        self.assertEqual(CycleLedger.objects.get(pk=first.id).budget_bucket,CycleLedger.objects.get(pk=second.id).budget_bucket)

    def test_business_caps_and_planned_cycles_cannot_be_enabled_by_invocation(self):
        by_id={c['id']:c for c in self.graph['cycles']}
        self.assertEqual(by_id['pieza_diaria']['limits']['cost_cap_usd'],2)
        self.assertEqual(by_id['referentes_mensuales']['limits']['cost_cap_usd'],5)
        self.assertEqual(by_id['referentes_mensuales']['limits']['cost_period'],'month')
        self.assertEqual(by_id['perfil_periodico']['limits']['cost_cap_usd'],10)
        with self.assertRaises(runtime.UndeclaredCall):self.open(cycle='referentes_mensuales')

    def test_human_resume_keeps_call_cost_and_plan_history(self):
        from django.contrib.auth.models import Permission
        self.user.user_permissions.add(Permission.objects.get(content_type__app_label='team_backend',codename='manage_jobs'))
        run=self.open()
        with run.session():
            run.call('seleccionar',REQUEST,lambda:RESULT)
            run.stop('stall')
        self.job.state='failed';self.job.save()
        before=CycleLedger.objects.get(pk=run.id)
        row=runtime.human_decision(self.user,run.id,'resume',['Use existing validated evidence'])
        self.job.refresh_from_db()
        self.assertEqual(self.job.state,'queued')
        self.assertEqual(row.calls,before.calls)
        self.assertEqual(row.progress_ledger['calls'],before.progress_ledger['calls'])
        self.assertEqual(row.task_ledger['plan_version'],2)
        self.assertEqual(row.task_ledger['decisions'][0]['actor'],self.user.pk)

    def test_read_activity_and_acknowledgement_never_repeat_a_paid_tool(self):
        run=self.open()
        with run.session():run.stop('cost_cap')
        from django.contrib.auth.models import Permission
        self.user.user_permissions.add(Permission.objects.get(content_type__app_label='team_backend',codename='manage_jobs'))
        row=runtime.human_decision(self.user,run.id,'acknowledge')
        self.assertFalse(row.needs_attention)
        self.assertEqual(row.state,'stopped')
        with self.assertRaises(runtime.CycleStopped):
            with self.open(key=row.key).session():self.fail('Acknowledging is not permission to spend')

    def test_concurrent_reservations_share_one_monthly_cap(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import close_old_connections
        self.cycle('red')['limits'].update(cost_period='month',cost_cap_usd=1)
        request={'job':str(self.job.id),'kind':'classify_contacts','params':{}}
        seed=self.open(cycle='red')
        def reserve(amount):
            providers.reserve('anthropic','network-classify',Decimal(amount))
            return {'classified':1,'fit':1}
        with seed.session():seed.call('clasificar',request,lambda:reserve('.80'))
        barrier=Barrier(2)
        def branch():
            close_old_connections()
            try:
                run=self.open(cycle='red')
                with run.session():
                    barrier.wait(timeout=10)
                    try:
                        run.call('clasificar',request,lambda:reserve('.15'))
                        return 'reserved'
                    except runtime.CycleStopped:return 'stopped'
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes=list(pool.map(lambda _:branch(),range(2)))
        self.assertEqual(sorted(outcomes),['reserved','stopped'])
        self.assertEqual(runtime.amount(UsageEntry.objects.all()),Decimal('.95'))

    def test_stopped_cycle_blocks_policy_even_with_jev_disabled(self):
        from types import SimpleNamespace
        from team_backend import autopiloto
        run=self.open(key=str(uuid.uuid4()))
        with run.session():run.stop('cost_cap')
        proposal=SimpleNamespace(piece_id=CycleLedger.objects.get(pk=run.id).key,origin_job='',capability='CONT-09')
        with patch.dict(os.environ,{'LEAD_ENABLED':'false'}),patch.object(autopiloto,'content_issues') as content:
            self.assertIs(autopiloto.policy_review(proposal),proposal)
        content.assert_not_called()
        self.assertEqual(runtime.cycle_issues(proposal),['Ciclo detenido: cost_cap'])

    def test_a_late_worker_cannot_apply_the_tool_response(self):
        run=self.open()
        def obsolete():
            CycleLedger.objects.filter(pk=run.id).update(lease_token='replacement-worker')
            return RESULT
        with run.session(),self.assertRaisesRegex(runtime.CycleStopped,'obsoleto'):
            run.call('seleccionar',REQUEST,obsolete)
        row=CycleLedger.objects.get(pk=run.id)
        self.assertNotIn('result',row.progress_ledger['calls']['seleccionar:1'])
        self.assertEqual(row.lease_token,'replacement-worker')
