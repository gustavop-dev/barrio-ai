"""La biblioteca guarda las clases 01–12; los agentes siguen leyendo solo 01–06.

Corpus sintético con la misma disposición de archivos que el privado, ingerido en la base efímera de pruebas. Sin red,
sin proveedores y sin el corpus real (eso lo cubre tests/test_infrastructure.py en local).
"""
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import Permission, User
from django.db import connection
from django.test import TransactionTestCase
from psycopg import errors
from rest_framework.test import APIClient

from knowledge import agents, db, ingest, retrieval
from knowledge.clases import CLASES_AGENTES, CLASES_BIBLIOTECA, patron, validar
from team_backend import catalogo, evaluaciones, grafo, operador
from team_backend.models import ApiCredential
from team_backend.office_bridge import command_request

INFRA = Path(__file__).resolve().parents[3]
FIRST = 'LinkedIn Sales - Entrega clase 01/01 - Clase 01/quality/'
COMPLETE = 'LinkedIn Sales - Procesamiento completo/'
LATER = 'LinkedIn Sales - Procesamiento clases 08-12/'
TABLES = 'memory,runs,usage_ledger,embedding_cache,unit_evidence,edges,chunks,units,source_files,evidence,unit_revisions'


def uid(n):
    return f'LI-{n:02}-V001-K01'


def unit(n, related=''):
    # «prospecto» aparece en todas las clases; «saludo» solo en las clases que leen los agentes.
    extra = ' Un saludo cordial abre la conversación.' if n in CLASES_AGENTES else ' Secuencia de seguimiento outbound.'
    return {'id': uid(n), 'title': f'Prospecto clase {n:02}',
            'explanation': f'Cómo hablar con un prospecto según la clase {n:02}.' + extra,
            'limits_errors': 'No prometer resultados.', 'related_learning': related, 'source_ids': ['qt00001']}


def write(base, path, data):
    target = base / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(data if isinstance(data, str) else json.dumps(data, ensure_ascii=False))


def synthetic_corpus(base, overrides=None):
    """Mismos archivos que el corpus privado: clase 01, bloque 02–07 y bloque 08–12 con sus fuentes y políticas."""
    overrides = overrides or {}
    # Relaciones que cruzan el límite: 03 cita 08 y 08 cita 03 y 07. 02 y 03 se citan entre sí.
    related = {2: uid(3), 3: f'{uid(2)} {uid(8)}', 8: f'{uid(3)} {uid(7)}'}
    units = {n: overrides.get(n, [unit(n, related.get(n, ''))]) for n in CLASES_BIBLIOTECA}
    write(base, FIRST + 'aprendizajes.json', {'learning_units': units[1]})
    write(base, FIRST + 'sources.json', {'data': {'transcript': [{'id': 'qt00001', 'text': 'Clase 01'}], 'materials': []}})
    write(base, FIRST + 'visual/evidence.json', {'visuals': []})
    lines = {'early': [], 'late': []}
    for n in CLASES_BIBLIOTECA[1:]:
        folder = (COMPLETE if n <= 7 else LATER) + 'revision-independiente/'
        write(base, folder + f'session-{n:02}-revisada.json', {'session': n, 'learning_units': units[n]})
        lines['early' if n <= 7 else 'late'].append(json.dumps({'key': f'{n:02}:qt00001', 'session': n, 'text': f'Fuente {n:02}'}))
    # Una fuente de una clase ajena al bloque se ignora, como antes la 07 en el bloque 02–06.
    lines['late'].append(json.dumps({'key': '13:qt00001', 'session': 13, 'text': 'Fuera de la biblioteca'}))
    write(base, COMPLETE + 'revision-independiente/fuentes.jsonl', '\n'.join(lines['early']) + '\n')
    write(base, LATER + 'conocimiento-para-agentes/fuentes.jsonl', '\n'.join(lines['late']) + '\n')
    write(base, COMPLETE + 'conocimiento-para-agentes/politica-de-uso.json', {'rules': ['Política 02–07']})
    write(base, LATER + 'conocimiento-para-agentes/politica-de-uso.json', {'rules': ['Política 08–12']})


class LibraryClassesTests(TransactionTestCase):
    def setUp(self):
        self.assertTrue(connection.settings_dict['NAME'].startswith('test_'))
        for patcher in (patch.dict(os.environ, {'LIVE_PROVIDERS': 'false'}),
                        patch('httpx.post', side_effect=AssertionError('Sin red en estas pruebas'))):
            patcher.start(); self.addCleanup(patcher.stop)
        self.files = tempfile.TemporaryDirectory(); self.addCleanup(self.files.cleanup)
        self.base = Path(self.files.name)
        source = patch.dict(os.environ, {'SOURCE_ROOT': self.files.name})
        source.start(); self.addCleanup(source.stop)
        self.truncate(); self.addCleanup(self.truncate)

    def truncate(self):
        with db.connect() as c: c.execute(f'TRUNCATE {TABLES} CASCADE')

    def ingest(self):
        synthetic_corpus(self.base)
        return ingest.ingest()

    def api(self):
        user = User.objects.create_user('biblioteca')
        user.user_permissions.add(*Permission.objects.filter(content_type__app_label='team_backend',
                                                             codename__in=['access_knowledge']))
        ApiCredential.objects.create(name='Pruebas', user=user, digest=hashlib.sha256(b'token-biblioteca').hexdigest())
        client = APIClient(); client.credentials(HTTP_AUTHORIZATION='Bearer token-biblioteca')
        return client

    # (a) La ingesta acepta las clases 07–12.

    def test_ingestion_loads_all_twelve_classes_with_their_sources_and_both_policies(self):
        result = self.ingest()
        self.assertEqual((result['units'], result['scope']), (12, '01–12'))
        status = db.status()
        self.assertEqual([r['session'] for r in status['classes']], list(CLASES_BIBLIOTECA))
        with db.connect() as c:
            keys = [r['key'] for r in c.execute('SELECT key FROM evidence ORDER BY key')]
            linked = {r['unit_id']: r['source_key'] for r in c.execute('SELECT * FROM unit_evidence')}
            files = {r['path'] for r in c.execute('SELECT path FROM source_files')}
        self.assertEqual(keys, [f'{n:02}:qt00001' for n in CLASES_BIBLIOTECA])  # 13:… se ignora
        self.assertEqual(linked[uid(8)], '08:qt00001')
        self.assertIn(COMPLETE + 'conocimiento-para-agentes/politica-de-uso.json', files)
        self.assertIn(LATER + 'conocimiento-para-agentes/politica-de-uso.json', files)
        self.assertIn(LATER + 'conocimiento-para-agentes/fuentes.jsonl', files)
        policies = ingest.load_corpus()[4]
        self.assertEqual([p['rules'] for p in policies.values()], [['Política 02–07'], ['Política 08–12']])
        self.assertTrue(ingest.verify()['passed'])
        self.assertEqual([s for s, _ in ingest.paths()], list(CLASES_BIBLIOTECA))

    def test_ingestion_still_fails_on_duplicates_unresolved_evidence_and_a_class_that_is_not_its_file(self):
        cases = {
            'IDs de unidad duplicados': {9: [unit(9), dict(unit(9), title='Otra')]},
            'Evidencias sin resolver': {10: [dict(unit(10), source_ids=['qt99999'])]},
            'clase distinta': {12: [dict(unit(12), id='LI-13-V001-K01')]},
        }
        for message, overrides in cases.items():
            with self.subTest(message=message):
                synthetic_corpus(self.base, overrides)
                with self.assertRaisesRegex(ValueError, message): ingest.load_corpus()
        with db.connect() as c: self.assertEqual(c.execute('SELECT count(*) AS n FROM units').fetchone()['n'], 0)

    # (b) Lo que reciben los agentes no cambia.

    def test_default_search_and_agent_context_stay_in_01_06_and_rank_as_without_07_12(self):
        self.ingest()
        found = retrieval.search('prospecto saludo', agent='perfil', limit=20)
        self.assertEqual(found['scope'], [1, 2, 3, 4, 5, 6])
        self.assertEqual(sorted(r['id'] for r in found['results']), [uid(n) for n in CLASES_AGENTES])
        relations = {(e['source_id'], e['target_id']) for e in found['relations']}
        self.assertEqual(relations, {(uid(2), uid(3)), (uid(3), uid(2))})
        context = agents.context('prospecto saludo', 'perfil')
        self.assertEqual(sorted(u['unit_id'] for u in context['units']), [uid(n) for n in CLASES_AGENTES])
        self.assertEqual(context['retrieval']['scope'], [1, 2, 3, 4, 5, 6])
        # Mismo orden y puntuación que una biblioteca con solo 01–06: 07–12 tampoco mueven las frecuencias.
        with db.connect() as c: c.execute('UPDATE units SET active=false WHERE session>6')
        alone = retrieval.search('prospecto saludo', agent='perfil', limit=20)
        self.assertEqual([(r['id'], r['score']) for r in alone['results']], [(r['id'], r['score']) for r in found['results']])

    def test_relations_reach_an_agent_only_inside_its_classes(self):
        self.ingest()
        self.assertEqual({(e['source_id'], e['target_id']) for e in retrieval.unit(uid(3))['relations']},
                         {(uid(2), uid(3)), (uid(3), uid(2))})
        full = retrieval.unit(uid(3), clases=CLASES_BIBLIOTECA)['relations']
        self.assertIn((uid(3), uid(8)), {(e['source_id'], e['target_id']) for e in full})
        # El contexto curado del operador lleva las relaciones de cada unidad al prompt: siguen siendo solo 01–06.
        units, missing, _ = operador.course_context([uid(3)])
        self.assertEqual(missing, [])
        self.assertTrue(all(re.fullmatch(rf'LI-{patron(CLASES_AGENTES)}-.+', end)
                            for e in units[0]['relations'] for end in (e['source_id'], e['target_id'])))

    def test_agent_loaders_and_validators_reject_classes_07_12(self):
        self.ingest()
        for n in range(7, 13):
            with self.subTest(clase=n):
                units, missing, _ = operador.course_context([uid(n)])
                self.assertEqual((units, missing), ([], [uid(n)]))
                self.assertIsNone(catalogo.LOADABLE.fullmatch(uid(n)))
        graph = grafo.load_graph()
        ref = next(iter(graph['course_lists']))
        graph['course_lists'][ref] = graph['course_lists'][ref] + ['LI-08-V001-K01']
        with self.assertRaisesRegex(grafo.GraphError, 'solo clases 01–06'): grafo.validate_graph(graph)
        role, case = next(iter(evaluaciones.COURSE_CASES.items()))
        grade = evaluaciones.grade_course_case(role, dict(case['expected'], course_citations=[uid(8)]),
                                               {'course_citations': [uid(8)]})
        self.assertIn('Cita fuera de las clases que leen los agentes', grade['errors'])

    # (c) Una unidad de la clase 08 se consulta por ID y por búsqueda explícita.

    def test_class_08_unit_by_id_and_by_explicit_search(self):
        self.ingest()
        row = retrieval.unit(uid(8))
        self.assertEqual((row['session'], [s['key'] for s in row['sources']]), (8, ['08:qt00001']))
        found = retrieval.search('prospecto seguimiento', clases=[8])
        self.assertEqual(([r['id'] for r in found['results']], found['scope']), ([uid(8)], [8]))
        client = self.api()
        self.assertEqual(client.get(f'/api/v1/units/{uid(8)}').json()['id'], uid(8))
        self.assertEqual([u['id'] for u in client.get('/api/v1/units?session=8').json()['results']], [uid(8)])
        self.assertEqual(client.get('/api/v1/sources/08:qt00001').json()['text'], 'Fuente 08')
        explicit = client.post('/api/v1/search', {'query': 'prospecto', 'clases': [8, 12]}, format='json').json()
        self.assertEqual(sorted(r['id'] for r in explicit['results']), [uid(8), uid(12)])
        default = client.post('/api/v1/search', {'query': 'prospecto', 'limit': 20}, format='json').json()
        self.assertEqual(sorted(r['id'] for r in default['results']), [uid(n) for n in CLASES_AGENTES])
        self.assertEqual(command_request({'operation': 'unit', 'body': {'id': uid(8)}})[1], f'/api/v1/units/{uid(8)}')
        self.assertEqual(command_request({'operation': 'source', 'body': {'id': '12:qt00001'}})[1], '/api/v1/sources/12:qt00001')

    # (d) La clase 13 se rechaza.

    def test_class_13_is_rejected_everywhere(self):
        with db.connect() as c:
            c.execute("INSERT INTO source_files(path,sha256) VALUES('fixture','abc')")
            c.execute("INSERT INTO evidence(key,session,original) VALUES('12:x',12,'{}')")
        for table, values in (('evidence', "('13:x',13,'{}')"),
                              ('units', "('LI-13-V001-K01',13,'T','{}','x','fixture','/','{}',true)")):
            with self.subTest(table=table), self.assertRaises(errors.CheckViolation):
                with db.connect() as c: c.execute(f'INSERT INTO {table} VALUES {values}')
        for bad in ([13], [0], [8, 13], [], 'abc', [True]):
            with self.subTest(clases=bad), self.assertRaises(ValueError): validar(bad)
        with self.assertRaisesRegex(ValueError, 'fuera de la biblioteca'): retrieval.search('prospecto', clases=[13])
        client = self.api()
        self.assertEqual(client.get('/api/v1/units?session=13').status_code, 400)
        self.assertEqual(client.post('/api/v1/search', {'query': 'prospecto', 'clases': [13]}, format='json').status_code, 400)
        self.assertEqual(client.get('/api/v1/units/LI-13-V001-K01').status_code, 404)
        for operation, ident in (('unit', 'LI-13-V001-K01'), ('source', '13:qt00001')):
            with self.subTest(operation=operation), self.assertRaisesRegex(ValueError, 'Referencia inválida'):
                command_request({'operation': operation, 'body': {'id': ident}})

    def test_schema_for_new_installs_matches_the_library_classes(self):
        schema = (INFRA / 'src/knowledge/schema.sql').read_text()
        self.assertEqual(re.findall(r'CHECK\(session BETWEEN (\d+) AND (\d+)\)', schema),
                         [(str(min(CLASES_BIBLIOTECA)), str(max(CLASES_BIBLIOTECA)))] * 2)
