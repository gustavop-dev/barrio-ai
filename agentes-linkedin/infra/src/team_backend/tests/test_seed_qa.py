"""seed_qa (the mobile app's UI QA world, .github/workflows/qa-movil.yml): it refuses to run outside the QA job, it builds
every state the Maestro flows need, the API serves it to the app's device token, and a second run gives the same world
while the app stays signed in. No network: OperatorBase forbids it."""
import io
import os
from unittest.mock import patch
from django.core.management import call_command
from django.core.management.base import CommandError
from rest_framework.test import APIClient
from team_backend import editorial
from team_backend.management.commands.seed_qa import EXTRA_DEVICE, QA_PASSWORD_DEFAULT
from team_backend.models import (ActionProposal, Capture, ConnectorAccount, Contact, EditorialPiece, GalleryPhoto, Notification, Opportunity,
                                 PostMetric, Referent, TeamQuestion, WeeklySummary)
from team_backend.tests.test_capturas import MediaMixin
from team_backend.tests.test_operador import OperatorBase

COUNTED=(ConnectorAccount,Referent,Contact,EditorialPiece,PostMetric,ActionProposal,Opportunity,TeamQuestion,Notification,Capture,GalleryPhoto,WeeklySummary)

class SeedQaTests(MediaMixin,OperatorBase):
    def setUp(self):
        super().setUp();self.use_media()
        env=patch.dict(os.environ,{'QA_SEED':'permitido','INBOX_ENABLED':'true','LIVE_LINKEDIN_OFFICIAL':'false','QA_PASSWORD':''})
        env.start();self.addCleanup(env.stop)

    def seed(self):
        out=io.StringIO();call_command('seed_qa',stdout=out)
        return out.getvalue()

    def counts(self):
        return {model.__name__:model.objects.count() for model in COUNTED}

    def device(self):
        response=APIClient().post('/api/v1/auth/token',{'username':'qa','password':QA_PASSWORD_DEFAULT,'device_name':'Emulador QA'},format='json')
        self.assertEqual(response.status_code,201,response.content)
        client=APIClient();client.credentials(HTTP_AUTHORIZATION='Bearer '+response.json()['token'])
        return client

    def test_refuses_outside_the_qa_job(self):
        """Catch the seed (which empties tables) running against a real office."""
        with patch.dict(os.environ,{'QA_SEED':''}):
            with self.assertRaises(CommandError):self.seed()
        with patch.dict(os.environ,{'LIVE_LINKEDIN':'true'}):
            with self.assertRaises(CommandError):self.seed()
        ConnectorAccount.objects.create(provider='unipile',external_account_id='real',label='Cuenta real')
        with self.assertRaises(CommandError):self.seed()
        self.assertEqual(ConnectorAccount.objects.count(),1)

    def test_builds_every_state_and_is_idempotent(self):
        """Catch a flow losing its data: every state the app shows exists, the API serves it, and reseeding repeats it."""
        self.assertIn('Mundo de QA listo',self.seed())
        first=self.counts()
        statuses={editorial.status(p,editorial.latest_action(p)) for p in EditorialPiece.objects.all()}
        self.assertTrue({'scheduled','published','blocked','skipped','failed'}<=statuses,statuses)
        self.assertTrue(set(Contact.Stage.values)<=set(Contact.objects.values_list('stage',flat=True)))
        self.assertEqual(set(PostMetric.objects.values_list('kind',flat=True)),{'24h','72h','7d'})
        self.assertGreaterEqual(Opportunity.objects.values('stage').distinct().count(),5)
        self.assertEqual(GalleryPhoto.objects.count(),4)
        self.assertTrue(all(photo.image.storage.exists(photo.image.name) for photo in GalleryPhoto.objects.all()))

        app=self.device()
        turno=app.get('/api/v1/tu-turno').json()
        self.assertEqual({c['type'] for c in turno['items']},{'aviso','pregunta','conversacion','resumen'})
        self.assertTrue(turno['critical']);self.assertEqual(len(turno['later']),1)
        notifications=app.get('/api/v1/notificaciones').json()
        self.assertEqual(notifications['unread'],5)
        self.assertEqual({u['kind'] for u in notifications['upcoming']},{'piece_scheduled','invites_expected'})
        blocked=EditorialPiece.objects.get(state='blocked')
        self.assertEqual(app.get(f'/api/v1/editorial/pieces/{blocked.id}').json()['verification']['repair']['outcome'],'bloqueada')
        settings=app.get('/api/v1/ajustes').json()
        self.assertIn(EXTRA_DEVICE,[d['name'] for d in settings['devices']])
        self.assertGreater(settings['ai_spend']['month_usd'],0)
        self.assertEqual(len(app.get('/api/v1/memoria/hechos').json()),3)
        for path in ('/api/v1/calendario','/api/v1/actividad','/api/v1/resultados?dias=7','/api/v1/resultados?dias=90',
                     '/api/v1/resultados/resumen-semanal','/api/v1/red/contacts','/api/v1/red/summary','/api/v1/oportunidades',
                     '/api/v1/operador/referents','/api/v1/galeria','/api/v1/capturas','/api/v1/oficina/actividad','/api/v1/operador/overview'):
            self.assertEqual(app.get(path).status_code,200,path)

        # A flow changes the world (answers, vetoes, reads); the next seed puts it back and keeps the app signed in.
        question=TeamQuestion.objects.get(question__startswith='¿Cuántos proyectos')
        self.assertEqual(app.post(f'/api/v1/preguntas/{question.id}/responder',{'text':'Doce proyectos.'},format='json').status_code,200)
        self.assertEqual(app.post('/api/v1/notificaciones/leer',{'todas':True},format='json').status_code,200)
        self.seed()
        self.assertEqual(self.counts(),first)
        self.assertEqual(TeamQuestion.objects.get(question__startswith='¿Cuántos proyectos').state,'open')
        self.assertEqual(Notification.objects.filter(read_at__isnull=True).count(),5)
        self.assertEqual(app.get('/api/v1/tu-turno').status_code,200)
