"""Rev 18: Tu turno only holds what needs Gustavo (by priority, with states); everything else is a Notificación (7 days)."""
import os
from datetime import timedelta
from unittest.mock import patch
from django.utils import timezone
from team_backend import notificaciones, operador, oportunidades, preguntas
from team_backend.models import ActionProposal, InboxSeen, Notification
from team_backend.tests.test_operador import OperatorBase

class NotificationTests(OperatorBase):
    def setUp(self):
        super().setUp();self.grant(self.gustavo,'confirm_memory')
        push=patch('team_backend.alerts.notify');self.push=push.start();self.addCleanup(push.stop)

    def test_feed_events_are_recorded_once_and_push_follows_the_table(self):
        notificaciones.avisar('piece_published','Publicaste «X»','Las impresiones a las 24 h llegan mañana.',link='/calendario/pieza/1',ref='piece_published:1')
        notificaciones.avisar('piece_published','Publicaste «X»',ref='piece_published:1')  # same event: recorded once
        notificaciones.avisar('connection_fit','Ana aceptó tu invitación','Founder · Comprador',link='/personas/1',ref='connection:1')
        self.assertEqual(Notification.objects.count(),2)
        self.assertEqual(self.push.call_count,1)  # published pushes by default; a new connection does not
        self.assertEqual(self.push.call_args.kwargs['url'],'/calendario/pieza/1')
        body=self.human.get('/api/v1/notificaciones').json()
        self.assertEqual((body['unread'],[i['kind'] for i in body['items']]),(2,['connection_fit','piece_published']))
        first=body['items'][0]['id']
        self.assertEqual(self.human.post('/api/v1/notificaciones/leer',{'ids':[first]},format='json').json()['unread'],1)
        self.assertEqual(len(self.human.get('/api/v1/notificaciones?filtro=sin_leer').json()['items']),1)
        self.assertEqual(self.human.post('/api/v1/notificaciones/leer',{'todas':True},format='json').json()['unread'],0)
        Notification.objects.update(created_at=timezone.now()-timedelta(days=8))
        self.assertEqual(self.human.get('/api/v1/notificaciones').json()['items'],[])  # kept 7 days

    def test_inbox_events_push_to_tu_turno_and_push_can_be_turned_off(self):
        preguntas.ask('director_editorial','¿Lideraste una migración?','Para el post del jueves','experiencia.migracion')
        self.assertEqual(self.push.call_args.kwargs['url'],'/tu-turno');self.assertEqual(Notification.objects.count(),0)
        settings=self.human.get('/api/v1/ajustes').json()
        kinds={t['kind']:t for t in settings['push_types']}
        self.assertEqual((kinds['question']['goes_to'],kinds['question']['enabled'],kinds['connection_fit']['default']),('tu_turno',True,False))
        self.assertEqual(self.human.patch('/api/v1/ajustes/preferencias',{'push_disabled':['nope']},format='json').status_code,400)
        self.human.patch('/api/v1/ajustes/preferencias',{'push_disabled':['question']},format='json')
        self.push.reset_mock()
        preguntas.ask('director_editorial','¿Qué stack usas?','Para un post','experiencia.stack')
        self.push.assert_not_called()

    def test_upcoming_and_events_from_real_work(self):
        oportunidades.create(self.gustavo,{'person_name':'Laura','modality':'projectapp'})
        self.observed()
        kinds=set(Notification.objects.values_list('kind',flat=True))
        self.assertTrue({'opportunity','observatory'}<=kinds,kinds)
        with patch.dict(os.environ,{'OPERATOR_PAUSED':'true'}):
            upcoming=self.human.get('/api/v1/notificaciones').json()['upcoming']
        self.assertIn('machine_paused_env',[u['kind'] for u in upcoming])

class TuTurnoPriorityTests(OperatorBase):
    def setUp(self):
        super().setUp();self.grant(self.gustavo,'confirm_memory')
        push=patch('team_backend.alerts.notify');push.start();self.addCleanup(push.stop)

    def test_cards_are_grouped_by_priority_with_states_and_the_counter(self):
        post=self.observed()[0]
        proposal=operador.create_proposal(self.gustavo,post,'INT-03',{'text':'A useful contribution about evals in production.'})
        ActionProposal.objects.filter(pk=proposal.pk).update(state='uncertain')
        soon=preguntas.ask('director_editorial','¿Lideraste una migración?','Para el post de mañana','experiencia.migracion',deadline=timezone.now()+timedelta(hours=20))
        calm=preguntas.ask('perfil','¿Qué modalidad prefieres?','Para el titular','oferta.modalidad')
        with patch.dict(os.environ,{'OPERATOR_PAUSED':'true'}):
            turn=self.human.get('/api/v1/tu-turno').json()
        order=[(c['id'].split(':')[0],c['priority'],c['state']) for c in turn['items']]
        self.assertEqual(order,[('uncertain','urgente','nueva'),('question','importante','nueva'),('question','cuando_puedas','nueva')])
        self.assertNotIn('machine_paused_env',[c['id'] for c in turn['items']])  # a server stop is a Notificación
        self.assertEqual((turn['count'],turn['urgent_count'],turn['critical'],turn['notifications_unread']),(3,1,True,1))  # the Observatorio found posts
        self.human.post('/api/v1/tu-turno/vistos',{'ids':[f'question:{calm.id}']},format='json')
        turn=self.human.get('/api/v1/tu-turno').json()
        self.assertEqual(next(c['state'] for c in turn['items'] if c['id']==f'question:{calm.id}'),'vista')
        self.assertEqual(turn['count'],3)  # seen still counts
        self.human.post(f'/api/v1/preguntas/{calm.id}/mas-tarde',{},format='json')
        turn=self.human.get('/api/v1/tu-turno').json()
        self.assertEqual(turn['count'],2);self.assertEqual(turn['later'][0]['state'],'pospuesta')
        self.assertEqual(self.api.post('/api/v1/tu-turno/vistos',{'ids':['x']},format='json').status_code,403)
        self.assertTrue(InboxSeen.objects.filter(item_id=f'question:{calm.id}').exists())
        self.assertEqual(soon.state,'open')
