"""The buyer's journey (comprador.py, phase 1 of docs/plan-outbound.md): the append-only log, who is a buyer, the facts
each existing row gives (signals included), the transitions phases 2–6 will use (rest, retry, exit), the rebuild, the
isolation of the passive hooks and the funnel. The path end to end lives in test_comprador_e2e. Synthetic data only."""
import io
import json
import os
import uuid
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch
from django.contrib.auth.models import User
from django.core.management import call_command
from django.db import IntegrityError, connection, transaction
from django.test import SimpleTestCase
from django.utils import timezone
from rest_framework.test import APIClient
from team_backend import comprador, evidencia, operador, oportunidades
from team_backend.models import (ActionExecution, ActionOutcome, ActionProposal, AuditEvent, BuyerJourney, BuyerTouch, Contact,
                                 Conversation, EditorialPiece, ObservedPost, PostComment)
from team_backend.tests.test_red import NetworkBase

H=timedelta(hours=1);D=timedelta(days=1)


class BuyerBase(NetworkBase):
    def setUp(self):
        super().setUp()
        env=patch.dict(os.environ,{'BUYER_RECORD_ENABLED':'true'})
        env.start();self.addCleanup(env.stop)
        self.slots=0

    def buyer(self,slug='ana-acme',name='Ana Acme',**fields):
        """A fitting «comprador» (no web check pending), with its journey."""
        contact=self.contact(slug,name,stage=fields.pop('stage','fit'))
        if fields:Contact.objects.filter(pk=contact.pk).update(**fields)
        contact.refresh_from_db()
        return contact,comprador.update(contact)

    def executed(self,contact,capability,at,state='confirmed',wrote=True,post=None,comment=None):
        proposal=ActionProposal.objects.create(account=self.account,contact=None if post or comment else contact,post=post,comment=comment,
                                               capability=capability,payload={'text':'x'} if post or comment else {},
                                               payload_hash=uuid.uuid4().hex*2,state='confirmed')
        return ActionExecution.objects.create(proposal=proposal,idempotency_key=uuid.uuid4().hex,provider='fake',state=state,wrote=wrote,
                                              executed_by=self.gustavo,started_at=at,external_id='comment:'+uuid.uuid4().hex[:8])

    def their_post(self,contact):
        return ObservedPost.objects.create(account=self.account,provider_post_id='activity:'+uuid.uuid4().hex[:8],
                                           author_provider_id=contact.provider_user_id,author_name=contact.display_name,text='Their post')

    def their_comment(self,contact,at,**fields):
        """A comment of the person on one of Gustavo's posts (respuestas.py)."""
        self.slots+=1
        piece=EditorialPiece.objects.create(account=self.account,slot_date=timezone.now().date()-timedelta(days=500+self.slots),
                                            scheduled_for=at-D,state='ready',final_text='Own post',brief={'thesis':'t','approach':'opinion'})
        return PostComment.objects.create(account=self.account,piece=piece,provider_post_id='activity:me-0',
                                          provider_comment_id='comment:'+uuid.uuid4().hex[:8],author_provider_id=contact.provider_user_id,
                                          author_name=contact.display_name,text='Good point',commented_at=at,contact=contact,**fields)

    def conversation(self,contact,messages):
        return Conversation.objects.create(account=self.account,provider_chat_id='chat:'+uuid.uuid4().hex[:8],contact=contact,
                                           attendee_provider_id=contact.provider_user_id,
                                           messages=[{'id':f'm{i}','at':at.isoformat(),'from_me':me,'text':'x',**extra}
                                                     for i,(at,me,extra) in enumerate(messages)])

    def kinds(self,journey):
        return [t.kind for t in BuyerTouch.objects.filter(journey=journey).order_by('at','created_at')]


class LogTests(BuyerBase):
    def test_the_log_only_grows(self):
        _,journey=self.buyer()
        touch=journey.touches.get()
        touch.detail={'cambiado':True}
        with self.assertRaisesMessage(ValueError,'solo se añade'):touch.save()
        with self.assertRaisesMessage(ValueError,'no se borra'):touch.delete()
        with self.assertRaises(IntegrityError),transaction.atomic():  # one touch per key and journey
            BuyerTouch.objects.create(journey=journey,kind='elegido',direction='estado',at=timezone.now(),key='elegido')
        self.assertEqual(BuyerTouch.objects.get(pk=touch.pk).detail,{'rol':'comprador'})

    def test_contact_stage_keeps_its_values(self):
        self.assertEqual(set(Contact.Stage.values),{'candidate','fit','discarded','followed','invited','connected','closed','incoming'})

    def test_every_kind_has_one_direction_and_the_signals_are_the_persons(self):
        self.assertEqual(set(comprador.DIRECTION),set(BuyerTouch.Kind.values))
        # Phase 5: what her bridge did (senal_puente) is relayed as one of her signals; nothing the team does is.
        self.assertEqual(set(comprador.SIGNALS),{'respondio_comentario','comento_post','reacciono_post','nos_siguio','nos_invito',
                                                 'acepto_invitacion','abrio_conversacion','respondio_mensaje','reunion','senal_puente'})


class ChosenTests(BuyerBase):
    def test_only_a_fitting_buyer_whose_stage_passed_gets_a_journey(self):
        cases={'par':{'fit':True,'role':'par'},'no-encaja':{'fit':False,'role':'comprador'},
               'web-pendiente':{'fit':True,'role':'comprador','stage_check':{'state':'pending'}},
               'web-ok':{'fit':True,'role':'comprador','stage_check':{'state':'ok','checked_at':timezone.now().isoformat()}},
               'encaja-gustavo':{'fit':True,'role':'comprador','stage_check':{'state':'doubt'},
                                 'confirmed_by_gustavo':{'at':timezone.now().isoformat(),'by':'gustavo'}}}
        for slug,classification in cases.items():
            contact=self.contact(slug,slug)
            Contact.objects.filter(pk=contact.pk).update(classification=classification)
            comprador.update(contact)
        self.assertEqual(set(BuyerJourney.objects.values_list('contact__display_name',flat=True)),{'web-ok','encaja-gustavo'})

    def test_a_buyer_the_team_acted_on_stays_and_leaves_by_rule_then_comes_back(self):
        contact,journey=self.buyer(stage='followed',followed_at=timezone.now()-3*D,
                                   classification={'fit':False,'role':'comprador','classified_at':(timezone.now()-H).isoformat()})
        self.assertEqual((journey.step,journey.exit_reason,journey.exit_step),('salio','fuera_de_criterio','calentando'))
        self.assertEqual(self.kinds(journey),['elegido','seguir','salida'])
        self.assertIsNone(journey.next_at)
        self.assertEqual(comprador.update(contact).touches.count(),3)  # nothing new
        Contact.objects.filter(pk=contact.pk).update(classification={'fit':True,'role':'comprador'})
        journey=comprador.update(contact)
        self.assertEqual((journey.step,journey.exit_reason),('calentando',''))
        self.assertEqual(self.kinds(journey)[-1],'reabierto')

    def test_discarded_by_gustavo_is_definitive_and_nothing_brings_the_person_back(self):
        contact,journey=self.buyer(stage='followed',followed_at=timezone.now()-3*D)
        self.human.post(f'/api/v1/red/contacts/{contact.pk}/discard',{'note':'No es comprador.'},format='json')
        journey.refresh_from_db()
        self.assertEqual((journey.step,journey.exit_reason),('salio','descartado_por_gustavo'))
        Contact.objects.filter(pk=contact.pk).update(stage='connected',connected_at=timezone.now())  # even a connection
        journey=comprador.update(contact)
        self.assertEqual((journey.step,journey.exit_reason,journey.accepted_at is not None),('salio','descartado_por_gustavo',True))

    def test_a_closed_invitation_leaves_by_rule_and_an_acceptance_reopens(self):
        invited=timezone.now()-5*D
        contact,journey=self.buyer(stage='closed',invited_at=invited,followed_at=invited-3*D,
                                   history=[{'event':'closed','at':(invited+D).isoformat(),'detail':'La invitación ya no está pendiente'}])
        self.assertEqual((journey.step,journey.exit_reason,journey.exited_at),('salio','invitacion_cerrada',invited+D))
        Contact.objects.filter(pk=contact.pk).update(stage='connected',connected_at=timezone.now())
        journey=comprador.update(contact)
        self.assertEqual((journey.step,journey.exit_reason),('acepto',''))


class FactsTests(BuyerBase):
    def test_each_row_barrio_keeps_becomes_one_touch_with_its_reference(self):
        now=timezone.now()
        contact,_=self.buyer(stage='followed',followed_at=now-9*D)
        follow=self.executed(contact,'RED-01',now-9*D)
        self.executed(contact,'RED-02',now-8*D,state='failed')  # wrote nothing: not a touch
        post=self.their_post(contact)
        comment=self.executed(contact,'INT-03',now-7*D,post=post)
        ActionOutcome.objects.create(execution=comment,kind='72h',captured_at=now-4*D,source='read',replies=1,repliers=[contact.provider_user_id])
        invite=self.executed(contact,'RED-02',now-3*D)
        operador._audit(self.gustavo,'network.note_sent',invite.proposal_id)
        Contact.objects.filter(pk=contact.pk).update(stage='connected',invited_at=now-3*D,connected_at=now-2*D)
        theirs=self.their_comment(contact,now-6*D,decision={'dm_closed':{'how':'no_escribir','at':(now-30*H).isoformat()}})
        reply=self.executed(contact,'INT-04',now-6*D+H,comment=theirs)
        chat=self.conversation(contact,[(now-26*H,True,{}),(now-25*H,False,{'hidden':True}),(now-24*H,False,{})])
        opportunity=oportunidades.create(self.gustavo,{'modality':'projectapp','contact':str(contact.pk)})
        journey=comprador.journey(contact)
        # The journey started before the follow had its execution: the contact's date stood in for it, and stays in the log.
        self.assertEqual(self.kinds(journey),['elegido','seguir','seguir','comentario','comento_post','respuesta_hilo','respondio_comentario',
                                              'invitacion','acepto_invitacion','no_escribirle','mensaje_visto','respondio_mensaje','oportunidad'])
        self.assertEqual([t.key for t in comprador.current(journey.touches.all()) if t.kind=='seguir'],[f'ejecucion:{follow.pk}'])
        rows={t.kind:t for t in comprador.current(journey.touches.all())}
        self.assertEqual((rows['seguir'].execution_id,rows['comentario'].post_id,rows['respuesta_hilo'].comment_id),(follow.pk,post.pk,theirs.pk))
        self.assertEqual((rows['invitacion'].execution_id,rows['invitacion'].detail['con_nota']),(invite.pk,True))
        self.assertEqual((rows['respondio_comentario'].outcome.execution_id,rows['comento_post'].direction),(comment.pk,'entrante'))
        self.assertEqual((rows['respondio_mensaje'].conversation_id,rows['oportunidad'].opportunity_id),(chat.pk,opportunity.pk))
        self.assertEqual(rows['acepto_invitacion'].at,now-2*D)
        self.assertEqual((journey.step,journey.invite_note,journey.comments_before_invite,journey.first_message_at,journey.replied_at),
                         ('respondio',True,1,now-26*H,now-24*H))
        self.assertEqual((journey.inbound_signals,journey.signal_before_invite),(4,True))
        self.assertEqual(comprador.update(contact)._added,0)  # idempotent

    def test_the_execution_replaces_the_contacts_date_that_stood_in_for_it(self):
        now=timezone.now()
        contact,journey=self.buyer(stage='invited',followed_at=now-5*D,invited_at=now-2*D)
        self.assertEqual((journey.invite_note,journey.touches.get(kind='invitacion').key),(None,'contacto:invitado'))  # with or without a note: unknown
        invite=self.executed(contact,'RED-02',now-2*D-H)
        operador._audit(self.gustavo,'network.note_sent',invite.proposal_id)
        journey=comprador.update(contact)
        self.assertEqual((journey.invite_note,journey.invited_at,journey.touches.filter(kind='invitacion').count()),(True,now-2*D-H,2))

    def test_a_message_before_any_of_gustavos_opens_the_conversation(self):
        now=timezone.now()
        contact,_=self.buyer()
        self.conversation(contact,[(now-2*H,False,{}),(now-H,True,{})])
        journey=comprador.update(contact)
        self.assertEqual([k for k in self.kinds(journey) if k!='elegido'],['abrio_conversacion','mensaje_visto'])
        self.assertIsNone(journey.replied_at)

    def test_an_invitation_he_received_is_a_signal_from_the_evidence_or_the_history(self):
        now=timezone.now()
        contact,_=self.buyer(source='incoming',stage='incoming')
        evidencia.relationship(contact,'invitation','received:inv1',now-H,event_at=now-2*H,direction='received')
        journey=comprador.update(contact)
        [signal]=[t for t in comprador.current(journey.touches.all()) if t.kind=='nos_invito']  # the evidence replaces the contact's source
        self.assertEqual((signal.direction,signal.at,signal.detail['origen'],journey.entry),('entrante',now-2*H,'invitacion_recibida','entrante'))
        self.assertEqual((journey.inbound_signals,comprador.temperature(journey)['total']),(1,1))
        other,_=self.buyer('beto','Beto',source='incoming',stage='incoming',history=[{'event':'incoming','at':(now-3*H).isoformat()}])
        self.assertEqual(comprador.journey(other).touches.get(kind='nos_invito').key,f'historial:incoming:{(now-3*H).isoformat()}')


class TemperatureTests(BuyerBase):
    def test_signals_newest_first_with_age_and_source_without_weights(self):
        now=timezone.now()
        contact,_=self.buyer(stage='invited',invited_at=now-2*D)
        row=self.their_comment(contact,now-5*D)
        self.conversation(contact,[(now-10*H,False,{})])
        comprador.update(contact)
        heat=comprador.temperature(contact,now=now)
        self.assertEqual([(s['tipo'],s['dias'],s['antes_de_invitar']) for s in heat['senales']],
                         [('abrio_conversacion',0.4,False),('comento_post',5.0,True)])
        self.assertEqual((heat['total'],heat['antes_de_invitar'],heat['dias_desde_ultima']),(2,1,0.4))
        self.assertEqual(heat['por_tipo'],{'abrio_conversacion':1,'comento_post':1})
        self.assertEqual(heat['senales'][1]['ref'],{'comment':str(row.pk)})
        self.assertNotIn('peso',json.dumps(heat))
        self.assertEqual(comprador.temperature(comprador.journey(contact),now=now)['total'],2)

    def test_anyone_has_a_temperature_even_without_a_journey(self):
        contact=self.contact('par-luis','Luis Par')
        Contact.objects.filter(pk=contact.pk).update(classification={'fit':True,'role':'par'})
        self.their_comment(contact,timezone.now()-D)
        heat=comprador.temperature(Contact.objects.get(pk=contact.pk))
        self.assertEqual((heat['recorrido'],heat['total'],heat['senales'][0]['tipo']),(None,1,'comento_post'))
        self.assertFalse(BuyerJourney.objects.exists())


class TransitionTests(BuyerBase):
    def test_rest_then_retry_with_a_new_angle(self):
        now=timezone.now()
        contact,journey=self.buyer(stage='followed',followed_at=now-20*D)
        comprador.record(journey,'invitacion',at=now-18*D,key='prueba:invitacion',detail={'con_nota':False})
        comprador.set_angle(journey,'Su piloto pagado',at=now-19*D)
        with self.assertRaisesMessage(ValueError,'Motivo de descanso'):comprador.rest(journey,'cansado',now+D,at=now)
        with self.assertRaisesMessage(ValueError,'fecha de vuelta'):comprador.rest(journey,'invitacion_no_aceptada',now,at=now)
        comprador.rest(journey,'invitacion_no_aceptada',now+30*D,at=now,note='Tres semanas sin aceptar.')
        journey.refresh_from_db()
        self.assertEqual((journey.step,journey.rest_reason,journey.rest_until,journey.next_at),('descanso','invitacion_no_aceptada',now+30*D,now+30*D))
        self.assertEqual(journey.attempts[0]['motivo'],'invitacion_no_aceptada')
        self.assertEqual(comprador.due(now+31*D).get(),journey)
        with self.assertRaisesMessage(ValueError,'No se pasa a descanso'):comprador.rest(journey,'no_es_el_momento',now+40*D,at=now)
        with self.assertRaisesMessage(ValueError,'El descanso termina'):comprador.retry(journey,'Otro ángulo',at=now+D)
        with self.assertRaisesMessage(ValueError,'qué ángulo'):comprador.retry(journey,'  ',at=now+31*D)
        comprador.retry(journey,'Su contratación de ingenieros',at=now+31*D)
        journey.refresh_from_db()
        # The follow carries over; the invitation of the first attempt does not, though the funnel keeps its milestone.
        self.assertEqual((journey.step,journey.attempt,journey.rest_reason,journey.invited_at),('calentando',2,'',now-18*D))
        self.assertEqual([(a['numero'],a['angulo'],a['motivo']) for a in journey.attempts],
                         [(1,'Su piloto pagado','invitacion_no_aceptada'),(2,'Su contratación de ingenieros','')])
        with self.assertRaisesMessage(ValueError,'Solo se reintenta'):comprador.retry(journey,'Otro',at=now+32*D)

    def test_a_definitive_exit_is_final_and_a_rule_does_not_end_a_rest(self):
        now=timezone.now()
        contact,journey=self.buyer(stage='invited',invited_at=now-30*D)
        comprador.rest(journey,'invitacion_no_aceptada',now+D,at=now)
        Contact.objects.filter(pk=contact.pk).update(stage='closed')  # a rule closure while resting: the rest stays
        journey=comprador.update(contact)
        self.assertEqual((journey.step,journey.rest_reason),('descanso','invitacion_no_aceptada'))
        with self.assertRaisesMessage(ValueError,'Motivo de salida'):comprador.leave(journey,'aburrido')
        comprador.leave(journey,'pidio_no_contacto',at=now+H,note='Pidió que no le escribamos.')
        journey.refresh_from_db()
        self.assertEqual((journey.step,journey.exit_reason,journey.exit_step,journey.next_at),('salio','pidio_no_contacto','descanso',None))
        with self.assertRaisesMessage(ValueError,'definitiva'):comprador.leave(journey,'no_le_interesa')
        with self.assertRaisesMessage(ValueError,'No se pasa a descanso'):comprador.rest(journey,'no_es_el_momento',now+9*D)
        comprador.record(journey,'respondio_mensaje',at=now+2*H,key='prueba:respuesta')  # a signal never reopens it
        journey.refresh_from_db()
        self.assertEqual((journey.step,journey.replied_at),('salio',now+2*H))
        self.assertFalse(comprador.due(now+9*D).exists())

    def test_a_reply_wakes_a_rest_and_a_rule_exit_can_end_in_a_definitive_one(self):
        now=timezone.now()
        _,journey=self.buyer(stage='invited',invited_at=now-30*D)
        comprador.rest(journey,'invitacion_no_aceptada',now+20*D,at=now-D)
        comprador.record(journey,'acepto_invitacion',at=now,key='prueba:acepto')
        journey.refresh_from_db()
        self.assertEqual((journey.step,journey.rest_reason,journey.attempt),('acepto','',1))
        comprador.leave(journey,'invitacion_cerrada',at=now+H)
        with self.assertRaisesMessage(ValueError,'Ya está fuera'):comprador.leave(journey,'fuera_de_criterio')
        comprador.leave(journey,'no_le_interesa',at=now+2*H)
        journey.refresh_from_db()
        self.assertEqual((journey.step,journey.exit_reason),('salio','no_le_interesa'))

    def test_record_refuses_transitions_and_records_each_key_once(self):
        _,journey=self.buyer()
        for kind in ('descanso','reintento','salida','reabierto'):
            with self.assertRaisesMessage(ValueError,'rest(), retry() y leave()'):comprador.record(journey,kind)
        with self.assertRaisesMessage(ValueError,'desconocido'):comprador.record(journey,'abrazo')
        first=comprador.record(journey,'visita',key='visita:1');again=comprador.record(journey,'visita',key='visita:1')
        self.assertEqual((first.direction,again),('saliente',None))
        comprador.set_route(journey,'sin_posts',reason='No publicó en 90 días.')
        with self.assertRaisesMessage(ValueError,'Ruta inválida'):comprador.set_route(journey,'sin_definir')
        journey.refresh_from_db()
        self.assertEqual((journey.visits,journey.route),(1,'sin_posts'))

    def test_a_booked_meeting_ends_the_journey_for_the_rests(self):
        _,journey=self.buyer()
        comprador.record(journey,'reunion',key='cal:1')
        journey.refresh_from_db();self.assertEqual(journey.step,'reunion')
        with self.assertRaisesMessage(ValueError,'reunión'):comprador.rest(journey,'no_es_el_momento',timezone.now()+D)

    def test_nothing_in_phase_1_puts_anyone_to_rest(self):
        import inspect
        from team_backend import conversaciones, desenlaces_captura, red, respuestas
        for module in (red,operador,respuestas,conversaciones,oportunidades,desenlaces_captura):
            source=inspect.getsource(module)
            for call in ('comprador.rest(','comprador.retry(','comprador.leave(','comprador.record('):
                self.assertNotIn(call,source,module.__name__)


class RebuildTests(BuyerBase):
    def test_the_rebuild_fills_what_the_hooks_missed_and_is_idempotent(self):
        eva=self.contact('founder-eva','Eva Founder',stage='followed',followed_hours=49)
        with patch.dict(os.environ,{'BUYER_RECORD_ENABLED':'false'}):  # history from before the journey existed
            self.job('plan_network');self.approve_open(eva,'RED-02')
        self.assertFalse(BuyerJourney.objects.exists())
        dry=comprador.rebuild(dry_run=True)
        self.assertEqual((dry['personas'],dry['recorridos'],dry['nuevos'],dry['toques_nuevos'],dry['seco']),(1,1,1,3,True))
        self.assertFalse(BuyerJourney.objects.exists())
        summary=comprador.rebuild()
        self.assertEqual((summary['recorridos'],summary['nuevos'],summary['toques_nuevos'],summary['fallos']),(1,1,3,0))
        journey=comprador.journey(eva)
        self.assertEqual((journey.step,journey.origin,self.kinds(journey)),('invitado','reconstruido',['elegido','seguir','invitacion']))
        self.assertEqual(set(journey.touches.values_list('source',flat=True)),{'reconstruido'})
        again=comprador.rebuild()
        self.assertEqual((again['recorridos'],again['nuevos'],again['toques_nuevos']),(1,0,0))
        self.assertEqual(AuditEvent.objects.filter(action='buyer.rebuilt').count(),2)

    def test_one_person_failing_does_not_stop_the_rebuild(self):
        ana,_=self.buyer();beto,_=self.buyer('beto','Beto')
        BuyerJourney.objects.all().delete()
        real=comprador.facts
        def facts(contact,known=()):
            if contact.pk==ana.pk:raise RuntimeError('fila rota')
            return real(contact,known)
        with patch('team_backend.comprador.facts',side_effect=facts):summary=comprador.rebuild()
        self.assertEqual((summary['personas'],summary['recorridos'],summary['fallos']),(2,1,1))
        self.assertIn('fila rota',summary['errores'][0]['error'])
        self.assertEqual(list(BuyerJourney.objects.values_list('contact',flat=True)),[beto.pk])

    def test_the_command_rebuilds_and_prints_the_funnel(self):
        self.buyer();BuyerJourney.objects.all().delete()
        out=io.StringIO();call_command('comprador','reconstruir','--seco',stdout=out)
        self.assertIn('En seco (sin guardar): 1 personas leídas, 1 recorridos (1 nuevos)',out.getvalue())
        self.assertFalse(BuyerJourney.objects.exists())
        call_command('comprador','reconstruir',stdout=io.StringIO())
        out=io.StringIO();call_command('comprador','embudo','--semanas','2',stdout=out)
        data=json.loads(out.getvalue())
        self.assertEqual((data['acumulado']['personas'],len(data['semanas'])),(1,2))


class HookIsolationTests(BuyerBase):
    def test_a_failing_record_never_stops_the_follow(self):
        eva=self.contact('founder-eva','Eva Founder')
        self.job('plan_network')
        with patch('team_backend.comprador.update',side_effect=RuntimeError('registro roto')):
            follow=self.approve_open(eva,'RED-01')
        self.assertEqual((follow.state,eva.stage,self.fake.state['writes']),('confirmed','followed',1))
        failed=AuditEvent.objects.get(action='buyer.record_failed')
        self.assertEqual((failed.target,failed.metadata['error'],failed.metadata['detail']),('ejecucion','RuntimeError','registro roto'))
        self.assertTrue(AuditEvent.objects.filter(action='operator.execution_confirmed',target=str(follow.pk)).exists())

    def broken(self,contact,**kwargs):
        """A failure PostgreSQL sees: without its own savepoint it would abort the action's transaction."""
        with connection.cursor() as cursor:cursor.execute('SELECT * FROM tabla_que_no_existe')

    def test_a_database_error_in_the_record_is_rolled_back_alone(self):
        eva=self.contact('founder-eva','Eva Founder',stage='followed',followed_hours=49)
        self.job('plan_network')
        with patch('team_backend.comprador.update',side_effect=self.broken):
            invite=self.approve_open(eva,'RED-02')
        self.assertEqual((invite.state,eva.stage),('confirmed','invited'))
        self.assertEqual(AuditEvent.objects.get(action='buyer.record_failed').metadata['error'],'ProgrammingError')
        self.assertTrue(AuditEvent.objects.filter(action='operator.execution_confirmed',target=str(invite.pk)).exists())
        self.assertFalse(BuyerTouch.objects.filter(kind='invitacion').exists())  # the failed record left nothing half-written
        self.assertEqual(comprador.update(eva).step,'invitado')  # the rebuild (or the next hook) catches up

    def test_a_database_error_inside_gustavos_discard_does_not_undo_it(self):
        """red.discard calls the hook inside its own transaction: only the savepoint keeps the discard."""
        eva,_=self.buyer('founder-eva','Eva Founder')
        with patch('team_backend.comprador.update',side_effect=self.broken):
            response=self.human.post(f'/api/v1/red/contacts/{eva.pk}/discard',{'note':'No es comprador.'},format='json')
        self.assertEqual(response.status_code,200,response.content)
        self.assertEqual(Contact.objects.get(pk=eva.pk).stage,'discarded')
        self.assertTrue(AuditEvent.objects.filter(action='network.contact_discarded',target=str(eva.pk)).exists())
        self.assertEqual(AuditEvent.objects.get(action='buyer.record_failed').target,'descarte')

    def test_a_failing_record_never_stops_the_classification(self):
        self.fake.seed_person('cto-carla','Carla CTO',headline='CTO',search='founder pre-seed')
        self.job('discover_network')
        with self.classifier({'Carla CTO':(True,0.9)}),patch('team_backend.comprador.update',side_effect=RuntimeError('x')):
            job=self.job('classify_contacts')
        self.assertEqual((job.state,Contact.objects.get().stage),('complete','fit'))
        self.assertEqual(AuditEvent.objects.get(action='buyer.record_failed').target,'clasificacion')

    def test_the_kill_switch_stops_the_hooks_but_not_the_rebuild(self):
        eva=self.contact('founder-eva','Eva Founder')
        self.job('plan_network')
        with patch.dict(os.environ,{'BUYER_RECORD_ENABLED':'false'}),patch('team_backend.comprador.update') as update:
            self.approve_open(eva,'RED-01')
        update.assert_not_called()
        self.assertEqual(comprador.rebuild()['recorridos'],1)


class FunnelTests(BuyerBase):
    def test_the_shape_is_final_even_with_nobody(self):
        funnel=comprador.funnel(3)
        self.assertEqual([s['etapa'] for s in funnel['acumulado']['etapas']],
                         ['elegidos','calentados','calentados_2','invitados','aceptaron','recibieron_mensaje','respondieron','interesados','reunion'])
        self.assertEqual({s['personas'] for s in funnel['acumulado']['etapas']},{0})
        self.assertEqual((len(funnel['semanas']),funnel['acumulado']['muestra_chica']),(3,True))
        self.assertEqual(set(funnel['comparaciones']),{'ruta','calentamiento','nota','senal','senal_de_compra','entrada'})
        self.assertEqual(set(funnel['comparaciones']['senal']),{'con_senal','sin_senal'})
        self.assertEqual(set(funnel['comparaciones']['senal_de_compra']),{'con_senal_de_compra','sin_senal_de_compra'})
        self.assertEqual(set(funnel['estado_actual']),set(BuyerJourney.Step.values))
        for bad in (0,27,'x'):
            with self.assertRaisesMessage(ValueError,'semanas'):comprador.funnel(bad)

    def test_thirty_invitations_are_no_longer_a_small_sample(self):
        now=timezone.now()
        people=[SimpleNamespace(comments_before_invite=0,invited_at=now,accepted_at=None,first_message_at=None,replied_at=None,
                                interested_at=None,meeting_at=None) for _ in range(30)]
        self.assertEqual((comprador.block(people)['muestra_chica'],comprador.block(people)['aviso']),(False,None))
        self.assertTrue(comprador.block(people[:29])['muestra_chica'])

    def test_stages_rates_cohorts_and_comparisons(self):
        now=timezone.now()
        ana,a=self.buyer('ana','Ana',stage='followed',followed_at=now-10*D)
        beto,b=self.buyer('beto','Beto',stage='followed',followed_at=now-10*D)
        carla,c=self.buyer('carla','Carla')
        self.buyer('dora','Dora',source='incoming',stage='incoming')  # came with her invitation: only in comparaciones.entrada
        # Carla, chosen early in the week three weeks back: alone in her cohort whatever the weekday (Ana and Beto follow
        # 10 days ago, which on a Tuesday or Wednesday falls in the week of «15 days ago»).
        _,week=operador.period_starts(now)
        BuyerJourney.objects.filter(pk=c.pk).update(chosen_at=week-timedelta(days=21)+timedelta(hours=1))
        for i,at in enumerate((now-9*D,now-8*D)):comprador.record(a,'comentario',at=at,key=f'c{i}')
        comprador.record(a,'invitacion',at=now-7*D,key='ia',detail={'con_nota':True})
        comprador.record(a,'acepto_invitacion',at=now-6*D,key='aa')
        comprador.record(a,'mensaje',at=now-5*D,key='ma')
        comprador.record(a,'respondio_mensaje',at=now-4*D,key='ra')
        comprador.record(b,'comentario',at=now-9*D,key='cb')
        comprador.record(b,'comento_post',at=now-8*D,key='sb')
        comprador.record(b,'invitacion',at=now-7*D,key='ib',detail={'con_nota':False})
        funnel=comprador.funnel(4,now=now)
        total=funnel['acumulado']
        self.assertEqual({s['etapa']:(s['personas'],s['paso_pct'],s['desde_elegidos_pct']) for s in total['etapas']},
                         {'elegidos':(3,None,100.0),'calentados':(2,66.67,66.67),'calentados_2':(1,50.0,33.33),'invitados':(2,100.0,66.67),
                          'aceptaron':(1,50.0,33.33),'recibieron_mensaje':(1,100.0,33.33),'respondieron':(1,100.0,33.33),
                          'interesados':(0,0.0,0.0),'reunion':(0,None,0.0)})
        compare=funnel['comparaciones']
        people=lambda block:block['personas']
        self.assertEqual((people(compare['nota']['con_nota']),people(compare['nota']['sin_nota'])),(1,1))
        self.assertEqual((people(compare['calentamiento']['calentados']),people(compare['calentamiento']['no_calentados'])),(2,1))
        self.assertEqual((people(compare['senal']['con_senal']),people(compare['senal']['sin_senal'])),(1,2))
        self.assertEqual({s['etapa']:s['personas'] for s in compare['senal']['con_senal']['etapas']}['invitados'],1)
        self.assertEqual((people(compare['entrada']['saliente']),people(compare['entrada']['entrante'])),(3,1))
        self.assertEqual((funnel['estado_actual']['respondio'],funnel['estado_actual']['invitado'],funnel['estado_actual']['elegido']),(1,1,1))
        # Cohorts: the week each person was chosen; Carla's is the oldest of the four.
        self.assertEqual(funnel['semanas'][3]['cohorte']['personas'],1)
        self.assertEqual(sum(w['cohorte']['personas'] for w in funnel['semanas']),3)
        self.assertEqual(sum(w['actividad']['comentarios'] for w in funnel['semanas']),3)
        self.assertEqual(sum(w['actividad']['mensajes_enviados'] for w in funnel['semanas']),1)

    def test_the_endpoint_needs_the_permission_and_a_valid_number_of_weeks(self):
        self.buyer()
        response=self.human.get('/api/v1/resultados/embudo-comprador')
        self.assertEqual((response.status_code,len(response.json()['semanas']),response.json()['acumulado']['personas']),(200,8,1))
        self.assertEqual(self.human.get('/api/v1/resultados/embudo-comprador?semanas=0').status_code,400)
        self.assertEqual(self.human.get('/api/v1/resultados/embudo-comprador?semanas=x').status_code,400)
        stranger=APIClient();stranger.force_login(User.objects.create_user('sin-permisos'))
        self.assertEqual(stranger.get('/api/v1/resultados/embudo-comprador').status_code,403)
        self.assertEqual(APIClient().get('/api/v1/resultados/embudo-comprador').status_code,401)


class FoldTests(SimpleTestCase):
    """The fold alone: the log in order makes the journey, whatever wrote it."""
    def touch(self,kind,at,**detail):
        return SimpleNamespace(kind=kind,at=at,direction=comprador.DIRECTION[kind],detail=detail)

    def test_milestones_are_the_first_time_and_the_step_is_the_current_attempt(self):
        now=timezone.now()
        state=comprador._fold([self.touch('elegido',now),self.touch('seguir',now+H),self.touch('invitacion',now+2*H,con_nota=True),
                               self.touch('descanso',now+3*H,motivo='invitacion_no_aceptada',hasta=(now+9*D).isoformat()),
                               self.touch('reintento',now+10*D,angulo='Otro'),self.touch('invitacion',now+11*D,con_nota=False),
                               self.touch('acepto_invitacion',now+12*D),self.touch('mensaje',now+13*D),self.touch('mensaje',now+17*D)])
        self.assertEqual((state.step(),state.first['invited'],state.invite_note,state.attempt,state.messages),('mensaje_2',now+2*H,True,2,2))
        self.assertEqual(state.attempts[0]['motivo'],'invitacion_no_aceptada')

    def test_a_fourth_message_is_the_last_message_step(self):
        now=timezone.now()
        state=comprador._fold([self.touch('elegido',now)]+[self.touch('mensaje',now+i*D) for i in range(1,6)])
        self.assertEqual(state.step(),'mensaje_4')
