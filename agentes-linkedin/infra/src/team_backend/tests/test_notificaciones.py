"""Rev 18: Tu turno only holds what needs Gustavo (by priority, with states); everything else is a Notificación (7 days)."""
import os
from datetime import timedelta
from unittest.mock import patch
from django.utils import timezone
from team_backend import autopiloto, connectors_linkedin as li, notificaciones, operador, oportunidades, preguntas
from team_backend.models import ActionProposal, InboxSeen, Notification, OfficePreference
from team_backend.tests.test_operador import OperatorBase
from team_backend.tests.test_publicacion import PublicationBase

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
        self.assertEqual(order,[('uncertain','urgente','nueva'),('question','importante','nueva'),
                                ('referents_setup','importante','nueva'),('question','cuando_puedas','nueva')])
        self.assertNotIn('machine_paused_env',[c['id'] for c in turn['items']])  # a server stop is a Notificación
        self.assertEqual((turn['count'],turn['urgent_count'],turn['critical'],turn['notifications_unread']),(4,1,True,1))  # setup is a card; only the Observatorio notification is unread
        self.human.post('/api/v1/tu-turno/vistos',{'ids':[f'question:{calm.id}']},format='json')
        turn=self.human.get('/api/v1/tu-turno').json()
        self.assertEqual(next(c['state'] for c in turn['items'] if c['id']==f'question:{calm.id}'),'vista')
        self.assertEqual(turn['count'],4)  # seen still counts
        self.human.post(f'/api/v1/preguntas/{calm.id}/mas-tarde',{},format='json')
        turn=self.human.get('/api/v1/tu-turno').json()
        self.assertEqual(turn['count'],3);self.assertEqual(turn['later'][0]['state'],'pospuesta')
        self.assertEqual(self.api.post('/api/v1/tu-turno/vistos',{'ids':['x']},format='json').status_code,403)
        self.assertTrue(InboxSeen.objects.filter(item_id=f'question:{calm.id}').exists())
        self.assertEqual(soon.state,'open')

class PushSwitchTests(OperatorBase):
    """PUS-04: Ajustes can turn the push of any kind on or off, including the kinds whose push is off by default."""
    def setUp(self):
        super().setUp()
        push=patch('team_backend.alerts.notify');self.push=push.start();self.addCleanup(push.stop)

    def kinds(self):
        return {t['kind']:t for t in self.human.get('/api/v1/ajustes').json()['push_types']}

    def patch_preferences(self,body):
        return self.human.patch('/api/v1/ajustes/preferencias',body,format='json')

    def test_a_push_that_is_off_by_default_can_be_turned_on_and_off_again(self):
        """Catch the switch of a default-off kind (connection_fit, opportunity…) flipping back to off after saving."""
        self.assertEqual((self.kinds()['connection_fit']['default'],self.kinds()['connection_fit']['enabled']),(False,False))
        saved=self.patch_preferences({'push_disabled':[],'push_enabled':['connection_fit']})
        self.assertEqual(saved.status_code,200,saved.content)
        self.assertEqual((saved.json()['push_disabled'],saved.json()['push_enabled']),([],['connection_fit']))
        self.assertTrue(self.kinds()['connection_fit']['enabled'])
        notificaciones.avisar('connection_fit','Ana aceptó tu invitación','Founder · Comprador',link='/personas/1',ref='connection:1')
        self.assertEqual(self.push.call_count,1);self.assertEqual(self.push.call_args.kwargs['url'],'/personas/1')
        # An older client sends push_disabled only: what was turned on stays on, unless it is in that list.
        self.patch_preferences({'push_disabled':['question']})
        kinds=self.kinds();self.assertEqual((kinds['connection_fit']['enabled'],kinds['question']['enabled']),(True,False))
        self.patch_preferences({'push_disabled':['connection_fit']})
        kinds=self.kinds();self.assertEqual((kinds['connection_fit']['enabled'],kinds['question']['enabled']),(False,True))
        self.assertEqual(OfficePreference.current().push_enabled,[])
        self.push.reset_mock()
        notificaciones.avisar('connection_fit','Luis aceptó tu invitación',ref='connection:2')
        self.push.assert_not_called()

    def test_bad_bodies_are_refused(self):
        self.assertEqual(self.patch_preferences({'push_enabled':['nope']}).status_code,400)
        self.assertEqual(self.patch_preferences({'push_disabled':['question'],'push_enabled':['question']}).status_code,400)
        self.assertEqual(self.api.patch('/api/v1/ajustes/preferencias',{'push_enabled':['connection_fit']},format='json').status_code,403)
        self.assertEqual(OfficePreference.current().push_enabled,[])


class PushEmitterTests(OperatorBase):
    """PUS-05: every push type Ajustes offers has an emitter where its event happens."""
    def setUp(self):
        super().setUp()
        push=patch('team_backend.alerts.notify');self.push=push.start();self.addCleanup(push.stop)

    def pushed(self):
        return [(c.args[0],c.kwargs.get('url'),c.kwargs.get('urgent')) for c in self.push.call_args_list]

    def test_stopping_the_machine_from_the_app_pushes_machine_paused(self):
        """Catch «Máquina detenida desde la app» never being sent although its switch is on by default."""
        operador.set_global_pause(self.gustavo,True,'Revisar el tono')
        self.assertEqual(self.pushed(),[('Máquina detenida','/tu-turno',True)])
        self.assertIn('Revisar el tono',self.push.call_args.args[1])
        self.push.reset_mock();operador.set_global_pause(self.gustavo,False)
        self.push.assert_not_called()  # resuming asks nothing of Gustavo

    def test_the_server_stop_pushes_once_per_stop_and_stays_out_of_the_feed(self):
        """Catch «Máquina detenida desde el servidor» never being sent (it was only computed in «Próximo»)."""
        with patch.dict(os.environ,{'OPERATOR_PAUSED':'true'}):
            self.assertEqual(autopiloto.tick(self.gustavo).get('stopped'),'OPERATOR_PAUSED')
            autopiloto.tick(self.gustavo)  # the same stop: no second push
            self.assertIn('machine_paused_env',[u['kind'] for u in self.human.get('/api/v1/notificaciones').json()['upcoming']])
        self.assertEqual(self.pushed(),[('Máquina detenida desde el servidor','/notificaciones',True)])
        self.assertEqual(Notification.objects.count(),0)  # «Próximo» shows it while it lasts; the feed does not keep it
        self.assertFalse(operador.check_env_pause())  # lifted: recorded, nothing to push
        with patch.dict(os.environ,{'OPERATOR_PAUSED':'true'}):self.assertTrue(operador.check_env_pause())  # a new stop pushes again
        self.assertEqual(len(self.push.call_args_list),2)

    def test_profile_task_has_no_switch_until_its_event_exists(self):
        """Catch a switch for a push that nothing can send (profile tasks are not implemented, TUR-18)."""
        kinds=[t['kind'] for t in self.human.get('/api/v1/ajustes').json()['push_types']]
        self.assertNotIn('profile_task',kinds)
        self.assertTrue({'linkedin_expired','machine_paused','machine_paused_env'}<=set(kinds))
        self.assertEqual(self.human.patch('/api/v1/ajustes/preferencias',{'push_disabled':['profile_task']},format='json').status_code,200)  # still accepted


class ApprovalTests(OperatorBase):
    """BAR-13, CAL-15: a proposal in `approval` mode waits for Gustavo in Tu turno and in the calendar's «En cola», with Aprobar."""
    def setUp(self):
        super().setUp()
        push=patch('team_backend.alerts.notify');push.start();self.addCleanup(push.stop)

    def approvals(self):
        return [c for c in self.human.get('/api/v1/tu-turno').json()['items'] if c['type']=='aprobacion']

    def queued(self):
        return self.human.get('/api/v1/actividad').json()['upcoming']['queued']

    def test_a_proposal_in_approval_mode_can_be_approved_from_tu_turno_and_the_queue(self):
        """Catch an `approval` proposal that can only be vetoed or left to expire: no screen offered Aprobar."""
        post=self.observed()[0]
        action=self.proposal(post)
        self.assertEqual(self.approvals(),[])  # INT-03 is `auto`: the policy decides, not Gustavo
        with patch.dict(os.environ,{'OPERATOR_AUTONOMY':'INT-03=approval'}):
            turn=self.human.get('/api/v1/tu-turno').json()
            card=next(c for c in turn['items'] if c['type']=='aprobacion')
            self.assertEqual((card['id'],card['priority'],card['state']),(f'approval:{action["id"]}','importante','nueva'))
            self.assertTrue(card['title'].startswith('¿Apruebas el comentario en el post de'),card['title'])
            self.assertEqual((turn['count'],turn['counts']['aprobaciones']),(2,1))
            self.assertEqual({c['id'] for c in turn['items']},
                             {f'approval:{action["id"]}',f'referents_setup:{self.account.id}'})
            approve,reject=card['actions'][:2]
            self.assertEqual((approve['label'],approve['body'],approve['primary']),('Aprobar',{'expected_hash':action['payload_hash']},True))
            self.assertEqual((reject['label'],reject['note_required']),('Vetar',True))
            self.assertEqual(card['approval']['text'],action['payload']['text'])
            self.assertEqual([(q['id'],q['awaiting_approval'],q['payload_hash']) for q in self.queued()],[(action['id'],True,action['payload_hash'])])
            self.assertEqual(self.human.post(approve['endpoint'],approve['body'],format='json').status_code,202)
            self.assertEqual(self.approvals(),[])
            recent=self.human.get('/api/v1/tu-turno').json()['recent']
            self.assertIn((f'approval:{action["id"]}','Aprobada'),[(r['id'],r['how']) for r in recent])
            self.assertEqual([(q['id'],q['state'],q['awaiting_approval']) for q in self.queued()],[(action['id'],'approved',False)])

    def test_vetoing_from_the_card_rejects_it(self):
        post=self.observed()[0]
        action=self.proposal(post)
        with patch.dict(os.environ,{'OPERATOR_AUTONOMY':'INT-03=approval'}):
            reject=self.approvals()[0]['actions'][1]
            self.assertEqual(self.human.post(reject['endpoint'],{'note':'No aporta'},format='json').status_code,200)
            self.assertEqual(self.approvals(),[]);self.assertEqual(self.queued(),[])
        self.assertEqual(ActionProposal.objects.get(id=action['id']).state,'rejected')


class LinkedInExpiredTests(PublicationBase):
    """PUS-05, TUR-05: an expired token pushes «LinkedIn caducado» and Tu turno shows «Reconecta LinkedIn» (urgente)."""
    def setUp(self):
        super().setUp()
        push=patch('team_backend.alerts.notify');self.push=push.start();self.addCleanup(push.stop)

    def test_an_expired_token_pushes_linkedin_expired_once_and_shows_its_card(self):
        """Catch the expired token arriving as «cuenta en pausa» and its urgent card never showing."""
        credential=self.credential(expires_in=timedelta(days=-1))
        self.assertEqual(li.check_tokens(),1)
        self.assertEqual([(c.args[0],c.kwargs.get('url'),c.kwargs.get('urgent')) for c in self.push.call_args_list],[('LinkedIn caducado','/tu-turno',True)])
        credential.account.refresh_from_db();self.assertTrue(credential.account.paused)
        self.assertEqual(li.check_tokens(),0);self.assertEqual(self.push.call_count,1)  # once
        turn=self.human.get('/api/v1/tu-turno').json()
        ids=[c['id'] for c in turn['items']]
        card=next(c for c in turn['items'] if c['id']=='linkedin_expired')
        self.assertEqual((card['priority'],card['body']),('urgente','El acceso caducó y la publicación diaria está en pausa.'))
        self.assertFalse([i for i in ids if i.startswith('account_paused:')])  # resuming the account would not help
