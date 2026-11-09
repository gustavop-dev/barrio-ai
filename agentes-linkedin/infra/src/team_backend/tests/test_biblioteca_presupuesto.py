"""Whole curated contexts: token omissions are not knowledge-store failures."""
import json
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from psycopg import OperationalError

from team_backend import editorial, evaluaciones, operador, resumen_semanal


class CourseBudgetTests(SimpleTestCase):
    def setUp(self):
        super().setUp()
        self.row={'original':{'title':'Synthetic whole unit','limits_errors':'Do not invent facts'},'sha256':'fixture'}
        for target,options in (
            ('knowledge.retrieval.unit',{'return_value':self.row}),
            ('team_backend.operador.ENC.encode',{'return_value':range(3000)}),
            ('team_backend.operador.orientacion.text',{'return_value':''}),
            ('team_backend.red.note_policy',{'return_value':{'default':'without_note'}}),
        ):
            mocked=patch(target,**options);mocked.start();self.addCleanup(mocked.stop)

    def test_old_budget_omits_existing_units_without_marking_library_unavailable(self):
        ids=operador.NETWORK_UNITS
        units,missing,omitted=operador.course_context(ids+[ids[0]],12000)
        self.assertEqual([u['unit_id'] for u in units],ids[:4])
        self.assertEqual(missing,[])
        self.assertEqual(omitted,ids[4:])
        self.assertEqual(units[0]['original'],self.row['original'])
        context,grounding=operador.role_context('relaciones',ids,{'red':ids},token_budget=12000)
        self.assertEqual(grounding['course_status'],'disponible')
        self.assertEqual(grounding['course_missing'],[])
        self.assertEqual(grounding['course_omitted'],omitted)
        self.assertEqual(grounding['course_citations'],ids[:4])
        self.assertEqual(list(grounding['course_hashes']),ids[:4])
        self.assertEqual(grounding['criterion_sources'],{'red':ids[:4]})
        for uid in omitted:self.assertNotIn(uid,context)
        with self.assertRaisesRegex(ValueError,'no recuperadas'):
            operador.validate_course_citations([omitted[0]],grounding)
        self.assertEqual(operador.validate_course_citations([ids[0]],grounding),[ids[0]])

    def test_even_a_zero_budget_is_not_a_library_outage(self):
        _,grounding=operador.role_context('relaciones',operador.NETWORK_UNITS,token_budget=0)
        self.assertEqual(grounding['course_status'],'disponible')
        self.assertEqual(grounding['course_missing'],[])
        self.assertEqual(grounding['course_citations'],[])
        self.assertEqual(grounding['course_omitted'],operador.NETWORK_UNITS)

    def test_missing_unreadable_and_excluded_units_still_block_after_budget_fills(self):
        first,absent,omitted=operador.NETWORK_UNITS[:3]
        excluded='LI-07-V001-K01'
        for error in (ValueError('absent'),OperationalError('knowledge store unavailable')):
            with self.subTest(error=type(error).__name__),patch('knowledge.retrieval.unit',side_effect=[self.row,error,self.row]):
                _,grounding=operador.role_context('relaciones',[first,absent,omitted,excluded],token_budget=3000)
            self.assertEqual(grounding['course_status'],'Biblioteca no disponible')
            self.assertEqual(grounding['course_missing'],[absent,excluded])
            self.assertEqual(grounding['course_omitted'],[omitted])
            self.assertEqual(grounding['course_citations'],[first])

    def test_all_curated_lists_fit_default_and_explicit_stage_budgets(self):
        lists={name:getattr(operador,name) for name in (
            'COMMENT_UNITS','NETWORK_UNITS','ANALYSIS_UNITS','INBOX_UNITS','LEAD_UNITS','REFERENTS_UNITS')}
        lists['WEEKLY_UNITS']=resumen_semanal.WEEKLY_UNITS
        for name,ids in lists.items():
            with self.subTest(name=name):
                _,grounding=operador.role_context(name,ids)
                self.assertEqual(grounding['course_citations'],list(dict.fromkeys(ids)))
                self.assertEqual((grounding['course_missing'],grounding['course_omitted']),([],[]))
        for name,stage in editorial.STAGES.items():
            ids=stage[2]
            if name=='redactor':ids=[editorial.APPROACH_UNITS[0]]+ids
            with self.subTest(stage=name):
                units,missing,omitted=operador.course_context(ids,stage[3])
                self.assertEqual([u['unit_id'] for u in units],list(dict.fromkeys(ids)))
                self.assertEqual((missing,omitted),([],[]))

    def test_evaluation_classifier_uses_complete_curated_context_but_rejects_real_absences(self):
        # Use the real evaluation cache without constructing a run that reads memory.
        cache=SimpleNamespace(_units={})
        run=SimpleNamespace(private=[],orientation='',context=lambda *args:evaluaciones.Run.context(cache,*args))
        request=evaluaciones.classify_request(run,[])
        units=json.loads(request['context'].split('\n',1)[1])
        self.assertEqual([u['unit_id'] for u in units],operador.NETWORK_UNITS)
        cache._units.clear()
        with patch('knowledge.retrieval.unit',side_effect=ValueError('absent')):
            with self.assertRaisesRegex(ValueError,'Biblioteca no disponible'):
                evaluaciones.classify_request(run,[])
