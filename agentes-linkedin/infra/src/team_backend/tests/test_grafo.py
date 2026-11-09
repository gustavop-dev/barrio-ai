"""Phase 3a: contracts, drift and a read-only API. Only local DB data/fakes."""
import ast
from copy import deepcopy
import inspect
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from team_backend import autopiloto, conversaciones, editorial, lider, metricas, oficina_views, operador, red, resumen_semanal
from team_backend.grafo import GraphError, load_graph, validate_bindings, validate_graph
from team_backend.jobs import OPERATION_PERMISSIONS
from team_backend.models import AuditEvent, Capture, ConnectorAccount, DeviceToken, EditorialPiece, Job, WebResearchRun
from team_backend.authentication import digest


class GraphTests(SimpleTestCase):
    def setUp(self):
        self.graph = load_graph()

    def test_registry_and_source_bindings(self):
        validate_graph(self.graph)
        validate_bindings(self.graph)

    def test_curated_lists_and_stage_units_match_code(self):
        actual = {f'{module.__name__.split(".")[-1]}.{name}': getattr(module, name)
                  for module in (operador, editorial) for name in dir(module) if name.endswith('_UNITS')}
        actual['editorial.TEXT_FORMAT_UNIT'] = [editorial.TEXT_FORMAT_UNIT]
        self.assertEqual(self.graph['course_lists'], actual)
        nodes = {n['id']: n for n in self.graph['nodes']}
        stages = {'director': ['director_editorial'], 'redactor': ['copywriter_a', 'copywriter_b'],
                  'lectores': editorial.READERS, 'seleccion': ['seleccion_editorial'],
                  'reparacion': ['reparacion_editorial'], 'verificador': ['editor_verificador']}
        for stage, ids in stages.items():
            expected = set(editorial.STAGES[stage][2])
            if stage == 'redactor':
                expected.update(editorial.APPROACH_UNITS)  # chosen brief approach, not all nine at once
            for nid in ids:
                self.assertEqual(set(nodes[nid]['course_units']), expected, nid)
                self.assertEqual(nodes[nid]['effort'], editorial.STAGES[stage][5], nid)
        for nid, ids in [('investigador_referentes', operador.REFERENTS_UNITS),
                         ('descubrimiento_red', operador.REFERENTS_UNITS), ('clasificador_red', red.NETWORK_UNITS),
                         ('plan_red', red.NETWORK_UNITS), ('relaciones_comunidad', operador.COMMENT_UNITS),
                         ('metricas', metricas.ANALYSIS_UNITS), ('analista_barrio_resultados', resumen_semanal.WEEKLY_UNITS),
                         ('conversaciones_inbox', conversaciones.INBOX_UNITS), ('lider_jev', lider.LEAD_UNITS)]:
            self.assertEqual(nodes[nid]['course_units'], ids, nid)

    def test_jobs_autopilot_and_office_mapping_cannot_drift(self):
        bindings = self.graph['code_bindings']
        self.assertEqual(bindings['job_roles'], oficina_views.JOB_ROLES)
        self.assertEqual(bindings['stage_roles'], editorial.STAGE_ROLES)
        self.assertEqual(bindings['network_ramp_stages'], [list(stage) for stage in red.RAMP_STAGES])
        self.assertEqual(bindings['network_read_caps'], red.READ_CAPS)
        declared = {t['kind'] for c in self.graph['cycles'] if c['status'] == 'active' for t in c['triggers']}
        self.assertEqual(declared, set(OPERATION_PERMISSIONS) | {'agent_run'})
        direct = set()
        for call in ast.walk(ast.parse(inspect.getsource(autopiloto))):
            if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Name):
                continue
            position = {'enqueue_operation': 1, 'enqueue': 0}.get(call.func.id)
            if position is not None and len(call.args) > position:
                value = call.args[position]
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    direct.add(value.value)
        self.assertEqual(sorted(direct), bindings['autopilot_direct_kinds'])
        self.assertLessEqual(direct, declared)

    def bad(self, mutate, message):
        graph = deepcopy(self.graph)
        mutate(graph)
        with self.assertRaisesRegex(GraphError, message):
            validate_graph(graph)

    def test_unreachable_duplicate_unknown_and_planned_nodes(self):
        self.bad(lambda g: g['nodes'].append(dict(g['nodes'][1], id='orphan')), 'no alcanzable')
        self.bad(lambda g: g['nodes'].append(g['nodes'][0]), 'duplicado')
        self.bad(lambda g: g['edges'][0].update(to='missing'), 'extremo desconocido')
        self.bad(lambda g: next(e for e in g['edges'] if e['id'] == 'visual_futuro').update(status='active'), 'planned')

    def test_specialists_depth_contracts_and_units(self):
        self.bad(lambda g: next(e for e in g['edges'] if e['id'] == 'redactar_a').update(**{'from': 'copywriter_b'}), 'especialista a especialista')
        self.bad(lambda g: next(e for e in g['edges'] if e['id'] == 'redactar_a').update(**{'from': 'editor_verificador'}), 'profundidad')
        self.bad(lambda g: g['edges'][0].update(response_schema='invented'), 'schemas desconocidos')
        self.bad(lambda g: g['nodes'][0]['course_units'].append('LI-99-FAKE'), 'fuera de listas curadas')
        self.bad(lambda g: g['nodes'][0].update(budget_ref='unknown'), 'presupuesto desconocido')
        self.bad(lambda g: g['edges'][0].update(max_calls_per_cycle=0), 'no acotado')
        self.bad(lambda g: g['cycles'][0]['loops'][0].update(max_rounds=3), 'bucle no acotado')

    def test_executable_paths_cannot_bypass_gates(self):
        for stop in ('editor_verificador', 'lider_jev', 'gustavo'):
            def bypass(g):
                chain = ['director_editorial', 'editor_verificador', 'lider_jev', 'gustavo', 'operador_cuenta']
                i = chain.index(stop)
                g['edges'].append(dict(g['edges'][0], id='bypass', request_kind='gate',
                                       **{'from': chain[i-1], 'to': chain[i+1]}))
            self.bad(bypass, 'ruta evita')
        self.bad(lambda g: g['nodes'][1]['tools'].append('linkedin_write'), 'escritor LinkedIn')
        self.bad(lambda g: g['gates']['publicacion']['chain'].remove('editor_verificador'), 'ruta ejecutable incompleta')

    def test_loader_rejects_duplicate_yaml_keys(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / 'grafo.yaml'
            path.write_text('{"schema_version": 1, "schema_version": 2}')
            with self.assertRaisesRegex(GraphError, 'Clave duplicada'):
                load_graph(path)


class GraphAPITests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('map-reader')
        self.other = get_user_model().objects.create_user('other-map-reader')
        self.user.user_permissions.add(*Permission.objects.filter(
            content_type__app_label='team_backend', codename__in=['access_knowledge', 'operate_linkedin']))
        self.client = APIClient()

    def test_auth_permissions_and_get_only(self):
        self.assertIn(self.client.get('/api/v1/equipo/grafo').status_code, [401, 403])
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get('/api/v1/equipo/grafo').status_code, 403)
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.post('/api/v1/equipo/grafo', {}, format='json').status_code, 405)

    def test_session_and_device_token_can_read_the_same_graph(self):
        self.client.force_login(self.user)
        session = self.client.get('/api/v1/equipo/grafo')
        self.assertEqual(session.status_code, 200)
        self.client.logout()
        token = '0ff1ce_dt_graph-test-only'
        DeviceToken.objects.create(user=self.user, name='Fake phone', digest=digest(token))
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + token)
        device = self.client.get('/api/v1/equipo/grafo')
        self.assertEqual(device.status_code, 200)
        self.assertEqual(device.data['graph_hash'], session.data['graph_hash'])

    def test_activity_is_real_bounded_and_does_not_expose_job_contents(self):
        own = [Job.objects.create(owner=self.user, kind='observe', agent='operador', task='PRIVATE', params={'secret': 'PRIVATE'}, state='complete') for _ in range(7)]
        foreign = Job.objects.create(owner=self.other, kind='observe', agent='operador', task='PRIVATE')
        AuditEvent.objects.create(action='office.event', target='investigador_referentes', metadata={
            'tipo': 'entrega', 'rol': 'investigador_referentes', 'destino': 'relaciones_comunidad',
            'detalle': '2 publicaciones nuevas', 'private': 'PRIVATE'})
        self.client.force_authenticate(self.user)
        before = Job.objects.count(), AuditEvent.objects.count()
        with patch('knowledge.providers.claude', side_effect=AssertionError('No provider calls')), patch('knowledge.providers.typesafe', side_effect=AssertionError('No provider calls')):
            response = self.client.get('/api/v1/equipo/grafo')
        self.assertEqual(response.status_code, 200)
        nodes = {n['id']: n for n in response.data['nodes']}
        recent = nodes['investigador_referentes']['recent_activity']
        self.assertEqual(len(recent['jobs']), 5)
        self.assertEqual(recent['jobs'][0]['id'], str(own[-1].id))
        self.assertNotIn(str(foreign.id), json.dumps(response.data, default=str))
        self.assertNotIn('PRIVATE', json.dumps(response.data, default=str))
        self.assertEqual(recent['handoffs'][0]['detail'], '2 publicaciones nuevas')
        self.assertEqual(nodes['editor_visual']['recent_activity'], {'jobs': [], 'handoffs': [], 'records': []})
        self.assertEqual(before, (Job.objects.count(), AuditEvent.objects.count()))

    def test_prepare_job_does_not_invent_activity_for_stages_that_did_not_run(self):
        Job.objects.create(owner=self.user, kind='prepare_piece', agent='operador', task='fake', state='complete')
        self.client.force_authenticate(self.user)
        response = self.client.get('/api/v1/equipo/grafo')
        self.assertEqual(response.status_code, 200)
        node = next(n for n in response.data['nodes'] if n['id'] == 'copywriter_a')
        self.assertEqual(node['recent_activity']['jobs'], [])

    def test_inline_steps_require_persisted_evidence_and_keep_research_private(self):
        now = timezone.now()
        account = ConnectorAccount.objects.create(provider='fake', external_account_id='graph-only', label='Synthetic')
        job = Job.objects.create(owner=self.user, kind='prepare_piece', agent='operador', task='fake', state='running')
        EditorialPiece.objects.create(account=account, slot_date=now.date(), scheduled_for=now, created_by=self.user,
                                      origin_job=str(job.id), usage=[{'stage': 'redactor'}], stage='lectores')
        capture = Capture.objects.create(created_by=self.user, understanding={'destino': 'post', 'evidence': 'PRIVATE'},
                                         transcript_provider_id='fake-transcript')
        capture_job = Job.objects.create(owner=self.user, kind='process_capture', agent='operador', task='fake',
                                        params={'capture': str(capture.id)}, state='complete')
        WebResearchRun.objects.create(key=f'capture:{capture.id}', request_hash='fake', state='complete', result={'question': 'PRIVATE'})
        WebResearchRun.objects.create(key='capture:unowned', request_hash='fake', state='complete', result={'question': 'PRIVATE'})
        self.client.force_authenticate(self.user)
        response = self.client.get('/api/v1/equipo/grafo')
        self.assertEqual(response.status_code, 200)
        nodes = {n['id']: n for n in response.data['nodes']}
        self.assertEqual(nodes['copywriter_a']['recent_activity']['jobs'][0]['id'], str(job.id))
        self.assertEqual(nodes['lector_comprador']['recent_activity']['jobs'][0]['id'], str(job.id))
        self.assertEqual(nodes['reparacion_editorial']['recent_activity']['jobs'], [])
        for nid in ('ruteador_capturas', 'transcripcion'):
            self.assertEqual(nodes[nid]['recent_activity']['jobs'][0]['id'], str(capture_job.id))
        self.assertEqual(nodes['intencion_captura']['recent_activity']['jobs'], [])
        self.assertEqual([r['id'] for r in nodes['investigacion_web']['recent_activity']['records']], [f'capture:{capture.id}'])
        self.assertNotIn('PRIVATE', json.dumps(response.data, default=str))
