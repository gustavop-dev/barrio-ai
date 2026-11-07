"""Office scene events: library visits, handoffs and publications come from real work only."""
import json
from datetime import timedelta
from unittest.mock import patch
from django.utils import timezone
from team_backend import jobs
from team_backend.models import AuditEvent
from team_backend.tests.test_operador import OperatorBase
from team_backend.tests.test_publicacion import EditorialBase, answers

class OfficeEventTests(OperatorBase):
    def test_comment_work_emits_library_handoff_and_publication(self):
        post=self.observed()[0]
        answer={'decision':'comment','language':'en','comment':'Evals first. Which failure mode do you test first?','rationale':'r',
                'citations':['LI-03-M006-K02'],'claims_needing_evidence':[],'risks':[]}
        with patch('knowledge.providers.claude',return_value={'text':json.dumps(answer),'model':'claude-opus-5-5'}):
            jobs.enqueue_operation(self.gustavo,'propose_comment',{'post':str(post.id)});jobs.process_one(self.worker)
        from team_backend.models import ActionProposal
        drafted=ActionProposal.objects.get(post=post,capability='INT-03')
        self.approve({'id':str(drafted.id),'payload_hash':drafted.payload_hash})
        kinds=[(e['tipo'],e['rol'],e['destino']) for e in self.human.get('/api/v1/oficina/eventos').json()['events']]
        self.assertEqual(kinds,[('consulta_biblioteca','relaciones_comunidad','biblioteca'),('entrega','relaciones_comunidad','operador_cuenta'),
                                ('publicacion','operador_cuenta','linkedin')])
        later=(timezone.now()+timedelta(minutes=1)).isoformat()
        self.assertEqual(self.human.get('/api/v1/oficina/eventos',{'desde':later}).json()['events'],[])
        self.assertEqual(self.human.get('/api/v1/oficina/eventos?desde=ayer').status_code,400)

class EditorialEventTests(EditorialBase):
    def test_each_stage_visits_the_library_and_hands_off(self):
        self.observed();self.plan(answers(signals_used=['first']))
        events=[e.metadata for e in AuditEvent.objects.filter(action='office.event').order_by('created_at')]
        library=[e['rol'] for e in events if e['tipo']=='consulta_biblioteca']
        self.assertEqual(library,['director_editorial','copywriter_a','lector_comprador','director_editorial','editor_verificador'])
        handoffs=[(e['rol'],e['destino']) for e in events if e['tipo']=='entrega']
        self.assertEqual(handoffs[0],('director_editorial','copywriter_a'));self.assertEqual(handoffs[-1],('editor_verificador','operador_cuenta'))
