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

class BackgroundWorkEventTests(OperatorBase):
    """OFI-03 and OFI-01: background work moves the scene too, not only the editorial circuit and the comments. Each job that
    produced something hands it off (oficina_eventos.job_done); a job that found nothing stays quiet."""

    def handoffs(self):
        return [(e.metadata['rol'],e.metadata['destino'],e.metadata['detalle'])
                for e in AuditEvent.objects.filter(action='office.event',metadata__tipo='entrega').order_by('created_at','id')]

    def test_observing_referents_hands_the_new_posts_to_relations(self):
        posts=self.observed()
        new=[h for h in self.handoffs() if h[0]=='investigador_referentes']
        self.assertEqual(len(new),1)
        self.assertEqual(new[0][1],'relaciones_comunidad')
        self.assertRegex(new[0][2],rf'^{len(posts)} publicaci(ón nueva|ones nuevas) de referentes$')

    def test_each_background_job_hands_off_only_what_it_produced(self):
        from team_backend import oficina_eventos
        cases=[('discover_network',{'new':3},('investigador_referentes','','3 personas nuevas para el barrio')),
               ('classify_contacts',{'classified':4,'fit':1},('investigador_referentes','relaciones_comunidad','1 de 4 personas encajan en el barrio')),
               ('read_inbox',{'chats':3,'read':3,'flagged':1},('conversaciones_inbox','','1 conversación te toca')),
               ('read_inbox',{'chats':2,'read':2,'flagged':0},('conversaciones_inbox','','2 conversaciones leídas')),
               ('collect_metrics',{'captured':5,'audience':'creada'},('analista_barrio_resultados','director_editorial','Métricas de 5 cortes y la audiencia del día')),
               ('collect_metrics',{'captured':0,'audience':'creada'},('analista_barrio_resultados','director_editorial','La audiencia del día'))]
        for kind,result,expected in cases:
            AuditEvent.objects.filter(action='office.event').delete()
            oficina_eventos.job_done(kind,result)
            self.assertEqual(self.handoffs(),[expected],kind)
        for kind,result in [('observe',{'new_posts':0}),('discover_network',{'new':0}),('classify_contacts',{'classified':0,'fit':0}),
                            ('read_inbox',{'chats':0,'read':0,'flagged':0}),('collect_metrics',{'captured':0,'audience':'ya'}),
                            ('sync_network',{'received':2}),('read_inbox',None)]:
            AuditEvent.objects.filter(action='office.event').delete()
            oficina_eventos.job_done(kind,result)
            self.assertEqual(self.handoffs(),[],kind)

    def test_the_worker_tells_the_scene_what_a_job_produced(self):
        from team_backend import operador
        from team_backend.models import Job
        job=Job.objects.create(owner=self.gustavo,request_hash='inbox',agent='conversaciones_inbox',task='read_inbox',kind='read_inbox',
                               params={'account':str(self.account.id)})
        with patch('team_backend.conversaciones.read_inbox',return_value={'chats':3,'read':3,'assessed':3,'flagged':1,'stopped':''}):
            self.assertEqual(operador.run_job(job)[0],'complete')
        self.assertEqual(self.handoffs(),[('conversaciones_inbox','','1 conversación te toca')])
