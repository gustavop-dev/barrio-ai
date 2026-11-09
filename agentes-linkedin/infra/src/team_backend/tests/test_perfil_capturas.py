"""Natural profile requests and scope clarification through the capture worker."""
from unittest.mock import patch

from django.test import SimpleTestCase

from team_backend import capturas, jobs, perfil, preguntas
from team_backend.models import Capture, Job, ProfileProposal, TeamQuestion
from team_backend.tests.test_capturas import CaptureBase, audio


class ProfileRequestLanguageTests(SimpleTestCase):
    def test_natural_requests_and_audio_transcripts(self):
        requests=[
            'hazme la propuesta del perfil',
            '¡POR FAVOR! HAZ UNA PROPUESTA DE MI PERFIL.',
            'Porfa, prepárame una propuesta completa para mi perfil de LinkedIn. Gracias.',
            'preparame una propuesta de perfil',
            'Prepara la propuesta para mi perfil, por favor.',
            'Genera una propuesta completa de mi perfil de LinkedIn',
            'quiero una propuesta del perfil',
            'propuesta de perfil',
            'Propuesta para mi perfil, porfa',
            'Hola, buenos días. Quiero que me hagas una propuesta completa para mi perfil de LinkedIn. Muchas gracias.',
            '  por favor,\nHazme la propuesta de mi perfil.\nGracias  ',
        ]
        for text in requests:
            with self.subTest(text=text):self.assertIsNotNone(perfil.EXPLICIT.fullmatch(text))

    def test_mentions_third_parties_and_negations_are_not_profile_requests(self):
        notes=[
            'No hazme la propuesta del perfil',
            'No quiero una propuesta de mi perfil.',
            'Quiero un post sobre perfiles de otras personas',
            'Una idea sobre el perfil de Ana y su propuesta de valor',
            'Haz una propuesta de perfil para Ana',
            'Hazme una propuesta de mi perfil y publica un post',
            'Cuando diga «hazme la propuesta del perfil», lo revisamos.',
            'Mi perfil necesita un cambio',
        ]
        for text in notes:
            with self.subTest(text=text):self.assertIsNone(perfil.EXPLICIT.fullmatch(text))


class ProfileCaptureRoutingTests(CaptureBase):
    def test_audio_request_finishes_capture_job_and_queues_profile_once(self):
        transcript=('Hola, por favor, quiero que me hagas una propuesta completa '
                    'para mi perfil de LinkedIn. Muchas gracias.')
        body=self.send(audio=audio(),audio_duration_s='12')
        with self.transcriber(transcript),patch('knowledge.providers.claude') as classifier:
            self.assertTrue(jobs.process_one(self.worker))
        capture=self.capture(body)
        self.assertEqual(capture.transcript,transcript)
        self.assertEqual((capture.state,capture.error),(Capture.State.NOTED,''))
        self.assertEqual(capture.routed_to['kind'],'perfil')
        self.assertEqual(Job.objects.get(pk=capturas.job_id(capture)).state,'complete')
        proposal=ProfileProposal.objects.get(pk=capture.routed_to['proposal'])
        self.assertEqual((proposal.mode,proposal.state),('full','queued'))
        self.assertEqual(proposal.triggers,[{'capture':str(capture.pk)}])
        capturas.process(capture.pk)
        self.assertEqual(Job.objects.filter(kind='prepare_profile').count(),1)
        self.assertEqual(len(self.transcribed),1)
        classifier.assert_not_called()

    def test_ambiguous_profile_note_becomes_a_pending_question_and_can_be_undone(self):
        body=self.send(nota='Quiero mejorar mi perfil, pero no sé por dónde empezar.')
        with patch('knowledge.providers.claude') as classifier,patch('team_backend.research.research') as research:
            self.assertTrue(jobs.process_one(self.worker))
        capture=self.capture(body)
        self.assertEqual((capture.state,capture.error),(Capture.State.NOTED,''))
        self.assertEqual(capture.routed_to['kind'],'perfil_aclaracion')
        self.assertEqual(capture.outcome['link'],'/tu-turno')
        self.assertEqual(Job.objects.get(pk=capturas.job_id(capture)).state,'complete')
        question=TeamQuestion.objects.get(pk=capture.routed_to['question'])
        self.assertTrue(preguntas.is_pending(question))
        self.assertEqual(question.agent,'perfil')
        self.assertIn('hazme la propuesta del perfil',question.purpose)
        self.assertFalse(question.suggested_public)
        turn=self.human.get('/api/v1/tu-turno').json()
        card=next(item for item in turn['items'] if item['id']==f'question:{question.pk}')
        self.assertIn('hazme la propuesta del perfil',card['question']['purpose'])
        self.assertFalse(ProfileProposal.objects.exists())
        self.assertFalse(Job.objects.filter(kind='prepare_profile').exists())
        classifier.assert_not_called();research.assert_not_called()
        capturas.process(capture.pk)
        self.assertEqual(TeamQuestion.objects.filter(origin=f'captura:{capture.pk}').count(),1)
        capturas.undo(self.gustavo,capture.pk)
        question.refresh_from_db()
        self.assertFalse(preguntas.is_pending(question))

    def test_casual_profile_mention_with_post_purpose_stays_an_idea(self):
        body=self.send(nota='Una idea para una pieza sobre el perfil de Ana.',para='post')
        with patch('team_backend.capture_intent.jev',return_value={}),patch('knowledge.providers.claude') as classifier:
            self.assertTrue(jobs.process_one(self.worker))
        capture=self.capture(body)
        self.assertEqual(capture.state,Capture.State.IDEA)
        self.assertEqual(capture.routed_to['kind'],'idea')
        self.assertFalse(ProfileProposal.objects.exists())
        self.assertFalse(TeamQuestion.objects.exists())
        classifier.assert_not_called()

    def test_casual_mention_without_purpose_asks_instead_of_starting_profile_or_failing(self):
        body=self.send(nota='El perfil de Ana me dio una idea para un post.')
        self.assertTrue(jobs.process_one(self.worker))
        capture=self.capture(body)
        self.assertEqual(capture.state,Capture.State.NOTED)
        self.assertTrue(TeamQuestion.objects.filter(pk=capture.routed_to['question'],state='open').exists())
        self.assertFalse(ProfileProposal.objects.exists())
