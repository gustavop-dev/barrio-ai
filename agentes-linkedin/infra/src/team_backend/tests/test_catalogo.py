"""Library catalog (catalogo.py): a version loads inactive, shelves adopt it one by one, and an agent without an active
shelf keeps its fixed list. Synthetic unit fixtures only: the real catalog is private course structure."""
import json
import tempfile
from copy import deepcopy
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.core.management import CommandError, call_command

from knowledge import db
from team_backend import catalogo, evaluaciones, operador
from team_backend.models import ActiveShelf, AuditEvent, CatalogEntry, LibraryCatalog
from team_backend.tests.test_evaluaciones import GOOD_COMMENT, recorder
from team_backend.tests.test_operador import OperatorBase

CORE=['LI-03-V010-K01','LI-03-M006-K02','LI-06-M001-K07']
CONSULT='LI-03-V011-K01'
DUPLICATE='LI-03-V020-K02'
VERSION='catalogo-prueba'


def catalog(version=VERSION):
    units={u:{'nivel':'nucleo','razon':None,'puntaje':0.9,'duplica':None} for u in CORE}
    units[CONSULT]={'nivel':'consulta','razon':None,'puntaje':0.7,'duplica':None}
    units[DUPLICATE]={'nivel':'referencia','razon':'dup','puntaje':0.8,'duplica':'LI-03-M006-K02'}
    return {'version':version,'metodo_niveles':'Fixture sintética.',
            'unidades':{u:{'principal':'responder' if u==CONSULT else 'comentar'} for u in units},
            'niveles':{'comentar':{'nucleo_orden':list(CORE),'unidades':units}}}


class CatalogTests(OperatorBase):
    def setUp(self):
        super().setUp()
        with db.connect() as c:
            for uid in CORE+[CONSULT,DUPLICATE]:
                c.execute('''INSERT INTO units(id,session,title,original,sha256,source_path,pointer,metadata)
                    VALUES(%s,%s,%s,'{"title":"Synthetic course fixture"}','fixture-hash','fixture','/units/0','{}')
                    ON CONFLICT(id) DO NOTHING''',(uid,int(uid[3:5]),uid))

    def test_a_version_loads_inactive_and_the_agents_keep_their_fixed_lists(self):
        summary=catalogo.load(catalog())
        self.assertEqual(summary['versiones'][VERSION]['estantes'],{'comentar':{'nucleo':3,'consulta':1,'referencia':1}})
        self.assertEqual(summary['activos'],{})
        self.assertEqual(catalogo.units_for('comentar',operador.COMMENT_UNITS),(operador.COMMENT_UNITS,'lista_fija'))
        self.assertEqual(catalogo.core('comentar',VERSION),CORE)  # in the order they were chosen, not alphabetical
        duplicate=CatalogEntry.objects.get(unit_id=DUPLICATE)
        self.assertEqual((duplicate.tier,duplicate.reason,duplicate.duplicate_of,duplicate.home,duplicate.core_rank),
                         ('referencia','dup','LI-03-M006-K02',True,None))
        self.assertFalse(CatalogEntry.objects.get(unit_id=CONSULT).home)  # it lives in another shelf

    def test_activation_is_per_shelf_and_deactivation_returns_to_the_fixed_list(self):
        catalogo.load(catalog())
        catalogo.activate(VERSION,['comentar'])
        self.assertEqual(catalogo.units_for('comentar',operador.COMMENT_UNITS),(CORE,f'catalogo:{VERSION}'))
        self.assertEqual(catalogo.units_for('responder',operador.REPLY_UNITS),(operador.REPLY_UNITS,'lista_fija'))
        with self.assertRaisesRegex(ValueError,'no tiene núcleo para: responder'):catalogo.activate(VERSION,['responder'])
        with self.assertRaisesRegex(ValueError,'Estantes inválidos'):catalogo.activate(VERSION,['ventas'])
        catalogo.deactivate(['comentar'])
        self.assertEqual(catalogo.units_for('comentar',operador.COMMENT_UNITS)[1],'lista_fija')

    def test_an_invalid_catalog_is_refused_whole(self):
        unknown=catalog('desconocida');unknown['niveles']['comentar']['unidades']['LI-03-V999-K09']={'nivel':'consulta'}
        mismatch=catalog('desajuste');mismatch['niveles']['comentar']['nucleo_orden']=CORE[:2]
        shelf=catalog('estante');shelf['niveles']={'ventas':deepcopy(shelf['niveles']['comentar'])}
        tier=catalog('nivel');tier['niveles']['comentar']['unidades'][CONSULT]['nivel']='a veces'
        for data,error in ((unknown,'no existen o no están activas'),(mismatch,'no coincide'),(shelf,'Estante desconocido'),
                           (tier,'nivel inválido'),({'version':'Mal Nombre'},'Versión del catálogo')):
            with self.assertRaisesRegex(ValueError,error):catalogo.load(data)
        with patch.object(catalogo,'CORE_TOKEN_BUDGET',10),self.assertRaisesRegex(ValueError,'el núcleo supera 10 tokens'):
            catalogo.load(catalog('grande'))
        self.assertFalse(LibraryCatalog.objects.exists());self.assertFalse(CatalogEntry.objects.exists())
        catalogo.load(catalog())
        with self.assertRaisesRegex(ValueError,'ya está cargada'):catalogo.load(catalog())

    def test_a_comment_draft_loads_the_active_core_and_records_where_it_came_from(self):
        catalogo.load(catalog());catalogo.activate(VERSION,['comentar'])
        post=self.observed()[0];calls=[]
        answer=lambda purpose,data:{'decision':'comment','language':'en','comment':GOOD_COMMENT,'rationale':'r','citations':['LI-03-M006-K02'],
                                    'claims_needing_evidence':[],'risks':[]}
        with patch('knowledge.providers.claude',side_effect=recorder(calls,answer)):operador.propose_comment(self.gustavo,post.id)
        grounded=AuditEvent.objects.get(action='operator.comment_grounded').metadata
        self.assertEqual((grounded['course_source'],grounded['course_citations']),(f'catalogo:{VERSION}',CORE))
        # The evaluator measures what production loads by default, and can still pin the fixed lists or another version.
        production,_=evaluaciones.comment_request(evaluaciones.Run(None),post)
        self.assertEqual(production['context'],calls[0]['context'])
        fixed,_=evaluaciones.comment_request(evaluaciones.Run(None,catalog=evaluaciones.FIXED),post)
        self.assertNotEqual(fixed['context'],calls[0]['context'])
        self.assertEqual(evaluaciones.Run(None,catalog=evaluaciones.FIXED).units('comentar',operador.COMMENT_UNITS)[0],operador.COMMENT_UNITS)

    def test_the_evaluator_measures_an_inactive_version_in_shadow(self):
        catalogo.load(catalog())
        report=evaluaciones.evaluate(['comentarios'],catalog=VERSION)
        self.assertEqual(report['agentes']['comentarios']['unidades'],{'ids':CORE,'origen':f'catalogo:{VERSION}'})
        self.assertFalse(ActiveShelf.objects.exists())  # measuring does not adopt it
        self.assertEqual(evaluaciones.evaluate(['comentarios'])['agentes']['comentarios']['unidades']['origen'],'lista_fija')
        with self.assertRaisesRegex(ValueError,'No hay catálogo otra'):evaluaciones.evaluate(['comentarios'],catalog='otra')

    def test_the_command_loads_activates_and_reports_counts_only(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'catalogo.json';path.write_text(json.dumps(catalog()),encoding='utf-8')
            out=StringIO();call_command('catalogo','cargar',str(path),stdout=out)
        self.assertEqual(json.loads(out.getvalue())['versiones'][VERSION]['nucleos'],{'comentar':CORE})
        out=StringIO();call_command('catalogo','activar',VERSION,'--estantes','comentar',stdout=out)
        self.assertEqual(json.loads(out.getvalue())['activos'],{'comentar':VERSION})
        out=StringIO();call_command('catalogo','estado',stdout=out)
        self.assertNotIn('Synthetic course fixture',out.getvalue())  # IDs and counts, never unit text
        call_command('catalogo','desactivar','--estantes','comentar',stdout=StringIO())
        self.assertFalse(ActiveShelf.objects.exists())
        with self.assertRaisesRegex(CommandError,'No se pudo leer el catálogo'):call_command('catalogo','cargar','/no/existe.json')
