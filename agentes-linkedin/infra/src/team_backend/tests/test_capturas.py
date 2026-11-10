"""Capture button, AssemblyAI transcription and the Galería (docs/capturas-galeria.md).
No network and no spend: AssemblyAI runs on httpx.MockTransport or a patched provider, Claude is patched, and every
test writes its files to a temporary MEDIA_ROOT."""
import json
import os
import shutil
import tempfile
import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
import httpx
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from knowledge import db, memory, providers
from team_backend import capturas, editorial, jobs, operador, preguntas
from team_backend.models import AuditEvent, Capture, Contact, EditorialPiece, GalleryPhoto, Job
from team_backend.tests.test_operador import OperatorBase
from team_backend.tests.test_publicacion import EditorialBase, answers

WEBM=b'\x1aE\xdf\xa3'+bytes(range(60))       # EBML header of a MediaRecorder webm
JPEG=b'\xff\xd8\xff\xe0'+b'\x00\x10JFIF'+bytes(54)
PNG=b'\x89PNG\r\n\x1a\n'+bytes(56)
KEY='aai-test-key-never-logged'

def audio(content=WEBM,mime='audio/webm;codecs=opus',name='nota.webm'):
    return SimpleUploadedFile(name,content,content_type=mime)

def photo(content=JPEG,mime='image/jpeg',name='foto.jpg'):
    return SimpleUploadedFile(name,content,content_type=mime)

def forbidden(request):
    raise AssertionError(f'Network forbidden: {request.method} {request.url}')

def stored_files(root):
    return sorted(os.path.relpath(os.path.join(d,f),root) for d,_,files in os.walk(root) for f in files)

def ledger():
    with db.connect() as c:
        return c.execute("SELECT status,purpose,reserved_usd,actual_usd,usage FROM usage_ledger WHERE provider='assemblyai' ORDER BY created_at").fetchall()

class MediaMixin:
    def use_media(self):
        self.media_root=tempfile.mkdtemp(prefix='capturas-test-')
        self.addCleanup(shutil.rmtree,self.media_root,ignore_errors=True)
        override=override_settings(MEDIA_ROOT=self.media_root);override.enable();self.addCleanup(override.disable)


class CaptureBase(MediaMixin,OperatorBase):
    def setUp(self):
        super().setUp();self.use_media()
        self.grant(self.gustavo,'confirm_memory','propose_memory')
        transport=patch.object(providers,'ASSEMBLYAI_TRANSPORT',httpx.MockTransport(forbidden));transport.start();self.addCleanup(transport.stop)
        self.transcribed=[]
        self.anonymous=APIClient()

    def transcriber(self,text='Hoy en una llamada salió algo bueno.',duration=40):
        def fake(path,duration_s=None,purpose='capture-transcribe'):
            with open(path,'rb') as handle:self.assertEqual(handle.read(),WEBM)
            self.transcribed.append((duration_s,purpose))
            return {'text':text,'language':'es','id':'tr_fake','audio_duration':duration,'model':'universal-3-5-pro','estimated_usd':0.002}
        return patch('knowledge.providers.assemblyai_transcribe',side_effect=fake)

    def send(self,client=None,expect=201,**data):
        response=(client or self.human).post('/api/v1/capturas',data,format='multipart')
        self.assertEqual(response.status_code,expect,response.content)
        return response.json()

    def drain(self):
        while jobs.process_one(self.worker):pass

    def capture(self,body):
        return Capture.objects.get(id=body['id'])

    def handoffs(self):
        return [(e.metadata['rol'],e.metadata['destino']) for e in AuditEvent.objects.filter(action='office.event').order_by('created_at')
                if e.metadata.get('tipo')=='entrega']


class CaptureValidationTests(CaptureBase):
    def test_multipart_is_validated_before_anything_is_stored(self):
        empty=self.human.post('/api/v1/capturas',{},format='multipart')
        self.assertEqual(empty.status_code,400);self.assertIn('vacía',empty.json()['detail'])
        self.assertEqual(self.human.post('/api/v1/capturas',{'nota':'   '},format='multipart').status_code,400)
        bad=[{'audio':audio(mime='text/plain')},                                   # mime not admitted
             {'audio':audio(content=JPEG)},                                        # bytes are not a webm
             {'fotos':[photo(content=b'<html><script>alert(1)</script></html>',mime='image/png')]},
             {'fotos':[photo() for _ in range(11)]},                               # more than 10 photos
             {'nota':'x','contexto_tipo':'persona','contexto_id':str(uuid.uuid4())},   # context does not exist
             {'nota':'x','contexto_tipo':'pieza'},                                  # type without id
             {'nota':'x','para':'galeria'},                                         # gallery without photos
             {'nota':'x','para':'otra'},
             {'audio':audio(),'audio_duration_s':'4000'}]                           # more than 30 minutes
        for data in bad:
            response=self.human.post('/api/v1/capturas',data,format='multipart')
            self.assertEqual(response.status_code,400,(list(data),response.content))
        with override_settings(GALLERY_PHOTO_MAX_BYTES=16):
            self.assertEqual(self.human.post('/api/v1/capturas',{'fotos':[photo()]},format='multipart').status_code,400)
        with override_settings(CAPTURE_AUDIO_MAX_BYTES=16):
            self.assertEqual(self.human.post('/api/v1/capturas',{'audio':audio()},format='multipart').status_code,400)
        # A service token prepares but never sends in Gustavo's name; anonymous gets nothing.
        self.assertEqual(self.api.post('/api/v1/capturas',{'nota':'Hola'},format='multipart').status_code,403)
        self.assertIn(self.anonymous.post('/api/v1/capturas',{'nota':'Hola'},format='multipart').status_code,(401,403))
        self.assertEqual((Capture.objects.count(),GalleryPhoto.objects.count(),Job.objects.filter(kind='process_capture').count()),(0,0,0))
        self.assertEqual(stored_files(self.media_root),[])

    def test_a_capture_is_saved_queued_and_described(self):
        body=self.send(audio=audio(),audio_duration_s='42.5',fotos=[photo(),photo(PNG,'image/png','b.png')],nota='Para el post del jueves',
                       para='post')
        self.assertEqual((body['state'],body['state_label'],body['purpose'],body['purpose_label']),('recibida','Recibida','post','Idea para un post'))
        self.assertEqual((body['has_audio'],body['audio_duration_s'],body['audio_url']),(True,42.5,f'/api/v1/capturas/{body["id"]}/audio'))
        self.assertEqual(len(body['photos']),2);self.assertTrue(body['photos'][0]['url'].startswith('/api/v1/galeria/'))
        self.assertTrue(body['can_undo']);self.assertIsNone(body['context'])
        capture=self.capture(body)
        self.assertEqual(capture.audio_mime,'audio/webm')
        self.assertTrue(capture.audio.name.startswith('capturas/audio/') and capture.audio.name.endswith('.webm'))
        self.assertEqual({p.mime for p in capture.photos.all()},{'image/jpeg','image/png'})
        self.assertTrue(all(p.image.name.startswith('galeria/') for p in capture.photos.all()))
        job=Job.objects.get(kind='process_capture')
        self.assertEqual((job.params,job.id,job.execute),({'capture':body['id']},capturas.job_id(capture),True))
        listed=self.human.get('/api/v1/capturas').json()
        self.assertEqual([c['id'] for c in listed['results']],[body['id']])
        self.assertEqual(self.api.get(f'/api/v1/capturas/{body["id"]}').json()['id'],body['id'])  # reads need operate_linkedin only


class CaptureRoutingTests(CaptureBase):
    def test_voice_answer_to_a_question_becomes_memory_with_the_chosen_visibility(self):
        q=preguntas.ask('director_editorial','¿Cuál fue tu primer agente en producción?','Para un post','experiencia.primer_agente',True)
        with self.transcriber('Un agente de soporte para un ERP en 2025.'):
            body=self.send(audio=audio(),audio_duration_s='42',contexto_tipo='pregunta',contexto_id=str(q.id),public_use='false')
            self.assertEqual(body['context'],{'tipo':'pregunta','id':str(q.id),'label':'¿Cuál fue tu primer agente en producción?'})
            self.drain()
        capture=self.capture(body);q.refresh_from_db()
        self.assertEqual(self.transcribed,[(42.0,'capture-transcribe')])
        self.assertEqual((capture.state,capture.transcript,capture.transcript_language,capture.audio_duration_s),
                         ('dato_guardado','Un agente de soporte para un ERP en 2025.','es',40.0))
        self.assertEqual(capture.outcome,{'kind':'dato_guardado','text':'Está en Lo que el equipo sabe de ti · Privado','link':'/tu-turno/sabe'})
        self.assertEqual((q.state,q.public_use,q.answered_by_id),('answered',False,self.gustavo.id))
        self.assertIn('¿Cuál fue tu primer agente en producción? Un agente de soporte para un ERP en 2025.',
                      [g['guidance']['texto'] for g in memory.confirmed_blocks()[1]])
        self.assertEqual(self.handoffs(),[('operador_cuenta','director_editorial')])  # handed to the agent that asked
        job=Job.objects.get(kind='process_capture')
        self.assertEqual((job.state,job.result_status),('complete','dato_guardado'))

    def test_a_typed_question_takes_the_spoken_answer_as_free_text(self):
        q=preguntas.ask('perfil','¿Aceptas proyectos de 3 meses?','Para saber qué priorizar','oferta.proyectos_cortos',
                        suggested_public=True,answer_type='yes_no')
        body=self.send(nota='Sí, pero solo remotos.',contexto_tipo='pregunta',contexto_id=str(q.id),para='respuesta');self.drain()
        self.assertEqual(self.capture(body).outcome['text'],'Está en Lo que el equipo sabe de ti · Público')  # the question's suggestion
        self.assertEqual([f['fact'] for f in memory.confirmed_blocks()[0]],['¿Aceptas proyectos de 3 meses? Sí, pero solo remotos.'])
        closed=self.human.post('/api/v1/capturas',{'nota':'Otra','contexto_tipo':'pregunta','contexto_id':str(q.id)},format='multipart')
        self.assertEqual(closed.status_code,409)

    def test_voice_note_about_a_person_lands_in_their_notes_and_undo_removes_it(self):
        contact=Contact.objects.create(account=self.account,provider_user_id='ACoana',display_name='Ana Founder',source='manual',stage='fit')
        with self.transcriber('Me habló de su piloto con IA.'):
            body=self.send(audio=audio(),nota='Evento del martes',contexto_tipo='persona',contexto_id=str(contact.id));self.drain()
        capture=self.capture(body);contact.refresh_from_db()
        self.assertEqual((capture.state,capture.outcome['text'],capture.outcome['link']),('anotado','Quedó en las notas de Ana Founder',f'/personas/{contact.id}'))
        note=contact.notes[-1]
        self.assertEqual((note['text'],note['source'],note['capture'],note['by']),('Evento del martes\n\nMe habló de su piloto con IA.','captura',body['id'],'gustavo-test'))
        self.assertEqual(self.human.get(f'/api/v1/red/contacts/{contact.id}').json()['notes'][-1]['source'],'captura')
        self.assertEqual(self.handoffs(),[('operador_cuenta','relaciones_comunidad')])
        undone=self.human.delete(f'/api/v1/capturas/{body["id"]}')
        self.assertEqual(undone.status_code,200,undone.content)
        self.assertEqual((undone.json()['state'],undone.json()['has_audio'],undone.json()['transcript']),('deshecha',False,''))
        contact.refresh_from_db();self.assertEqual(contact.notes,[])
        self.assertEqual(stored_files(self.media_root),[])
        self.assertEqual(self.human.get('/api/v1/capturas').json()['count'],0)

    def test_comment_on_a_piece_reaches_the_piece_detail_and_the_director(self):
        day=timezone.now().astimezone(operador.local_tz()).date()
        piece=EditorialPiece.objects.create(account=self.account,slot_date=day,scheduled_for=timezone.now(),state='skipped',
                                            brief={'thesis':'Scope features from the decision they support.'})
        body=self.send(nota='El gancho me suena a vendedor; más directo.',contexto_tipo='pieza',contexto_id=str(piece.id));self.drain()
        capture=self.capture(body)
        self.assertEqual((capture.state,capture.outcome['text']),('anotado',f'Quedó como comentario para el equipo en la pieza del {capturas.day_label(day)}'))
        self.assertEqual(body['context']['label'],'Scope features from the decision they support.')
        detail=self.human.get(f'/api/v1/editorial/pieces/{piece.id}').json()
        self.assertEqual([(c['id'],c['text'],c['has_audio']) for c in detail['team_comments']],[(body['id'],'El gancho me suena a vendedor; más directo.',False)])
        self.assertEqual(capturas.feedback_for_director()[0]['thesis'],'Scope features from the decision they support.')
        self.assertEqual(self.handoffs(),[('operador_cuenta','director_editorial')])

    def test_a_fact_is_private_memory_and_undo_withdraws_it(self):
        body=self.send(nota='Prefiero no nombrar clientes en público, ni siquiera con permiso.',para='dato');self.drain()
        capture=self.capture(body);key=capture.routed_to['memory_key']
        self.assertEqual((key,capture.state,capture.outcome['text']),(f'nota.captura-{capture.id.hex[:10]}','dato_guardado',
                                                                     'Está en Lo que el equipo sabe de ti · Privado'))
        facts={f['key']:f for f in self.human.get('/api/v1/memoria/hechos').json()}
        self.assertEqual((facts[key]['text'],facts[key]['public_use'],facts[key]['origin']['kind']),
                         ('Prefiero no nombrar clientes en público, ni siquiera con permiso.',False,'manual'))
        self.assertEqual(memory.confirmed_blocks()[0],[])  # never attributable in public
        self.assertEqual(self.handoffs(),[('operador_cuenta','posicionamiento')])
        self.assertEqual(self.human.delete(f'/api/v1/capturas/{body["id"]}').status_code,200)
        self.assertNotIn(key,{f['key'] for f in self.human.get('/api/v1/memoria/hechos').json()})
        self.assertEqual(memory.confirmed_blocks(),([],[]))

    def test_post_idea_and_photos_for_the_gallery(self):
        idea=self.send(nota='El founder no sabía qué pedir hasta que le pregunté qué decisión quería tomar.',para='post');self.drain()
        self.assertEqual((self.capture(idea).state,self.capture(idea).outcome),('idea',{'kind':'idea','text':'Mesa editorial lo tendrá en cuenta','link':None}))
        gallery=self.send(fotos=[photo(),photo(PNG,'image/png','b.png')],nota='Úsalas en el post del domingo',para='galeria');self.drain()
        capture=self.capture(gallery)
        self.assertEqual((capture.state,capture.outcome['text'],capture.outcome['link']),('dato_guardado','Está en tu Galería','/galeria'))
        listed=self.human.get('/api/v1/galeria').json()['results']
        self.assertEqual(len(listed),2)
        self.assertEqual({(p['note'],p['display_state'],p['label'],p['tone'],p['capture_id'],p['used_in']) for p in listed},
                         {('Úsalas en el post del domingo','nueva','Nueva','info',gallery['id'],None)})
        # The idea is also given its window on arrival (director → Gustavo), besides the two handoffs to the director.
        self.assertEqual(self.handoffs(),[('director_editorial','operador_cuenta')]+[('operador_cuenta','director_editorial')]*2)

    def test_photos_of_any_capture_reach_the_gallery(self):
        contact=Contact.objects.create(account=self.account,provider_user_id='ACoeva',display_name='Eva',source='manual',stage='fit')
        self.send(nota='Con Eva en el taller',fotos=[photo()],contexto_tipo='persona',contexto_id=str(contact.id));self.drain()
        self.assertEqual(GalleryPhoto.objects.get().capture.state,'anotado')

    def test_an_unlabeled_capture_is_classified_once_with_sonnet(self):
        calls=[]
        def fake(system,message,max_tokens=None,output_schema=None,effort=None,purpose='agent-run',model=None):
            calls.append({'message':json.loads(message),'schema':output_schema,'purpose':purpose,'model':model})
            return {'text':json.dumps({'destino':'dato','motivo':'Cuenta una preferencia suya, no una idea para publicar.'}),'model':model}
        with patch('knowledge.providers.claude',side_effect=fake),self.transcriber('No quiero hablar de cripto nunca.'):
            body=self.send(audio=audio());self.drain()
            only_photos=self.send(fotos=[photo()]);self.drain()
        self.assertEqual(len(calls),1)  # photos alone go to the gallery without asking anyone
        self.assertEqual((calls[0]['model'],calls[0]['purpose']),('claude-sonnet-5-5','capture-route'))
        self.assertEqual(calls[0]['schema']['properties']['destino']['enum'],['post','propuesta','dato'])
        # local_date lets the router resolve «mañana», «el lunes» for «publícalo lo antes posible» (CAP-16).
        self.assertEqual({k:v for k,v in calls[0]['message'].items() if k!='local_date'},{'texto':'No quiero hablar de cripto nunca.','fotos':0})
        self.assertRegex(calls[0]['message']['local_date'],r'^\d{4}-\d{2}-\d{2}$')
        capture=self.capture(body)
        self.assertEqual((capture.state,capture.routed_to['kind'],capture.routed_to['classified']),('dato_guardado','dato',True))
        detail=self.human.get(f'/api/v1/capturas/{body["id"]}').json()
        self.assertEqual(detail['team_decided'],{'purpose':'dato','label':'Dato sobre mí','reason':'Cuenta una preferencia suya, no una idea para publicar.'})
        self.assertIsNone(detail['purpose'])
        self.assertEqual(self.capture(only_photos).outcome['text'],'Está en tu Galería')

    def test_without_providers_an_unlabeled_capture_stays_in_error_with_its_text(self):
        body=self.send(nota='Algo que el equipo debería saber');self.drain()
        capture=self.capture(body)
        self.assertEqual(capture.state,'error');self.assertIn('No se pudo decidir a dónde va',capture.error)
        self.assertEqual(capture.note,'Algo que el equipo debería saber')
        self.assertEqual(Job.objects.get(kind='process_capture').state,'failed')

    def test_an_interrupted_capture_is_never_transcribed_twice(self):
        body=self.send(audio=audio())
        Capture.objects.filter(id=body['id']).update(state='transcribiendo')
        with self.transcriber():self.drain()
        self.assertEqual(self.transcribed,[])
        capture=self.capture(body)
        self.assertEqual(capture.state,'error');self.assertIn('no se repite',capture.error)


class UndoTests(CaptureBase):
    def test_undo_within_two_minutes_cancels_the_job_and_deletes_the_files(self):
        body=self.send(audio=audio(),fotos=[photo()],para='post')
        self.assertEqual(self.api.delete(f'/api/v1/capturas/{body["id"]}').status_code,403)
        undone=self.human.delete(f'/api/v1/capturas/{body["id"]}').json()
        self.assertEqual((undone['state'],undone['photos'],undone['can_undo']),('deshecha',[],False))
        self.assertEqual(Job.objects.get(kind='process_capture').state,'cancelled')
        self.assertEqual((GalleryPhoto.objects.count(),stored_files(self.media_root)),(0,[]))
        with self.transcriber():self.drain()
        self.assertEqual(self.transcribed,[])
        self.assertEqual(self.human.delete(f'/api/v1/capturas/{body["id"]}').status_code,200)  # idempotent

    def test_undo_after_the_window_is_a_conflict(self):
        body=self.send(nota='Idea vieja',para='post');self.drain()
        Capture.objects.filter(id=body['id']).update(created_at=timezone.now()-timedelta(minutes=3))
        late=self.human.delete(f'/api/v1/capturas/{body["id"]}')
        self.assertEqual(late.status_code,409);self.assertIn('2 minutos',late.json()['detail'])
        self.assertEqual(self.capture(body).state,'idea')
        self.assertFalse(self.human.get(f'/api/v1/capturas/{body["id"]}').json()['can_undo'])

    def test_answer_undo_reopens_the_question(self):
        q=preguntas.ask('posicionamiento','¿Dónde vives?','Para el perfil','identidad.ciudad')
        body=self.send(nota='Medellín',contexto_tipo='pregunta',contexto_id=str(q.id));self.drain()
        self.human.delete(f'/api/v1/capturas/{body["id"]}')
        q.refresh_from_db()
        self.assertEqual(q.state,'open');self.assertEqual(memory.confirmed_blocks(),([],[]))

    def test_a_stopped_job_shows_the_capture_in_error(self):
        body=self.send(nota='Una idea',para='post')
        Job.objects.filter(kind='process_capture').update(state='cancelled')
        Capture.objects.filter(id=body['id']).update(created_at=timezone.now()-timedelta(seconds=30))
        detail=self.human.get(f'/api/v1/capturas/{body["id"]}').json()
        self.assertEqual(detail['state'],'error');self.assertIn('no se repite',detail['error'])


class PrivateFilesTests(CaptureBase):
    def test_files_are_served_only_to_an_authenticated_reader(self):
        body=self.send(audio=audio(),fotos=[photo()],para='post')
        audio_url=body['audio_url'];image_url=body['photos'][0]['url']
        for url in (audio_url,image_url):
            self.assertIn(self.anonymous.get(url).status_code,(401,403))
        response=self.human.get(audio_url,HTTP_ACCEPT='audio/*')
        self.assertEqual(response.status_code,200)
        self.assertEqual(b''.join(response.streaming_content),WEBM)
        self.assertEqual((response['Content-Type'],response['Cache-Control'],response['Accept-Ranges']),('audio/webm','private, max-age=3600','bytes'))
        partial=self.human.get(audio_url,HTTP_RANGE='bytes=0-3')
        self.assertEqual((partial.status_code,partial.content,partial['Content-Range']),(206,WEBM[:4],f'bytes 0-3/{len(WEBM)}'))
        self.assertEqual(self.human.get(audio_url,HTTP_RANGE=f'bytes={len(WEBM)+5}-').status_code,416)
        image=self.human.get(image_url,HTTP_ACCEPT='image/avif,image/webp,*/*')
        self.assertEqual((image.status_code,image['Content-Type'],b''.join(image.streaming_content)),(200,'image/jpeg',JPEG))
        self.assertIn('sandbox',image['Content-Security-Policy'])
        name=self.capture(body).audio.name
        self.assertEqual(self.human.get('/media/'+name).status_code,404)  # never public static


class GalleryTests(CaptureBase):
    def test_upload_filters_patch_and_delete(self):
        self.assertEqual(self.human.post('/api/v1/galeria',{},format='multipart').status_code,400)
        self.assertEqual(self.human.post('/api/v1/galeria',{'fotos':[photo(b'GIF89a'+bytes(40),'image/gif')]},format='multipart').status_code,400)
        self.assertEqual(self.api.post('/api/v1/galeria',{'fotos':[photo()]},format='multipart').status_code,403)
        created=self.human.post('/api/v1/galeria',{'fotos':[photo() for _ in range(4)]},format='multipart')
        self.assertEqual(created.status_code,201,created.content)
        ids=[p['id'] for p in created.json()]
        self.assertEqual({(p['display_state'],p['allow_ai_edit'],p['capture_id']) for p in created.json()},{('nueva',True,None)})
        day=timezone.now().astimezone(operador.local_tz()).date()+timedelta(days=2)
        piece=EditorialPiece.objects.create(account=self.account,slot_date=day,scheduled_for=timezone.now()+timedelta(days=2),state='skipped')
        GalleryPhoto.objects.filter(id=ids[1]).update(created_at=timezone.now()-timedelta(days=2))
        GalleryPhoto.objects.filter(id=ids[2]).update(state='elegida',chosen_piece=piece)
        published=timezone.now()-timedelta(days=5)
        GalleryPhoto.objects.filter(id=ids[3]).update(state='publicada',published_at=published,chosen_piece=piece,chosen_for=day)
        listed={p['id']:p for p in self.human.get('/api/v1/galeria').json()['results']}
        self.assertEqual((listed[ids[0]]['label'],listed[ids[0]]['tone']),('Nueva','info'))
        self.assertEqual((listed[ids[1]]['display_state'],listed[ids[1]]['label'],listed[ids[1]]['tone']),('sin_usar','Sin usar','muted'))
        self.assertEqual((listed[ids[2]]['label'],listed[ids[2]]['tone']),(f'Elegida · {capturas.short_day(day)}','info'))
        self.assertEqual(listed[ids[2]]['used_in'],{'piece_id':str(piece.id),'date':str(day),'text':f'Usada en la pieza del {capturas.day_label(day)}'})
        local=published.astimezone(operador.local_tz()).date()
        self.assertEqual((listed[ids[3]]['label'],listed[ids[3]]['tone']),(f'Publicada · {capturas.date_label(local)}','ok'))
        def filtered(key):return {p['id'] for p in self.human.get(f'/api/v1/galeria?filtro={key}').json()['results']}
        self.assertEqual((filtered('sin_usar'),filtered('elegidas'),filtered('publicadas')),({ids[0],ids[1]},{ids[2]},{ids[3]}))
        self.assertEqual(len(filtered('todas')),4)
        self.assertEqual(self.human.get('/api/v1/galeria?filtro=otra').status_code,400)
        self.assertEqual(self.api.patch(f'/api/v1/galeria/{ids[0]}',{'note':'x'},format='json').status_code,403)
        patched=self.human.patch(f'/api/v1/galeria/{ids[0]}',{'note':' Recórtala para que no se lean nombres. ','allow_ai_edit':False},format='json').json()
        self.assertEqual((patched['note'],patched['allow_ai_edit']),('Recórtala para que no se lean nombres.',False))
        name=GalleryPhoto.objects.get(id=ids[0]).image.name
        self.assertIn(name,stored_files(self.media_root))
        self.assertEqual(self.human.delete(f'/api/v1/galeria/{ids[0]}').status_code,204)
        self.assertNotIn(name,stored_files(self.media_root))
        self.assertEqual(self.human.get(f'/api/v1/galeria/{ids[0]}').status_code,404)

    def test_preferences_set_the_default_of_new_photos(self):
        self.assertEqual(self.human.get('/api/v1/ajustes/preferencias').json()['gallery_ai_edit_default'],True)
        self.assertEqual(self.api.patch('/api/v1/ajustes/preferencias',{'gallery_ai_edit_default':False},format='json').status_code,403)
        changed=self.human.patch('/api/v1/ajustes/preferencias',{'gallery_ai_edit_default':False},format='json')
        self.assertEqual((changed.status_code,changed.json()['gallery_ai_edit_default']),(200,False))
        self.assertEqual(self.human.patch('/api/v1/ajustes/preferencias',{},format='json').status_code,400)
        created=self.human.post('/api/v1/galeria',{'fotos':[photo()]},format='multipart').json()
        self.assertFalse(created[0]['allow_ai_edit'])
        self.send(fotos=[photo()]);self.assertFalse(GalleryPhoto.objects.filter(capture__isnull=False).get().allow_ai_edit)


class AssemblyAIMock:
    """httpx transport standing in for api.assemblyai.com (upload, create, poll)."""
    def __init__(self,final=None,statuses=('processing',),create_status=200):
        self.requests=[];self.reserved_at_upload=None;self.create_status=create_status
        self.final=final or {'status':'completed','text':'Hola equipo, una idea para el jueves.','language_code':'es',
                             'audio_duration':40,'speech_model_used':'universal-3-5-pro'}
        self.statuses=list(statuses)
    def __call__(self,request):
        self.requests.append((request.method,request.url.path,dict(request.headers),request.content))
        assert request.headers['authorization']==KEY
        if request.url.path=='/v2/upload':
            self.reserved_at_upload=[r['status'] for r in ledger()]
            assert request.headers['content-type']=='application/octet-stream'
            return httpx.Response(200,json={'upload_url':'https://cdn.assemblyai.com/upload/f756988d'})
        if request.url.path=='/v2/transcript' and request.method=='POST':
            if self.create_status!=200:return httpx.Response(self.create_status,json={'error':'down'})
            return httpx.Response(200,json={'id':'tr_123','status':'queued'})
        if request.url.path=='/v2/transcript/tr_123':
            if self.statuses:return httpx.Response(200,json={'id':'tr_123','status':self.statuses.pop(0)})
            return httpx.Response(200,json=dict(self.final,id='tr_123'))
        raise AssertionError(f'Unexpected {request.method} {request.url}')
    def created(self):
        return [json.loads(r[3]) for r in self.requests if r[0]=='POST' and r[1]=='/v2/transcript']


class AssemblyAITests(CaptureBase):
    def setUp(self):
        super().setUp()
        env=patch.dict(os.environ,{'LIVE_PROVIDERS':'true','ASSEMBLYAI_API_KEY':KEY,'ASSEMBLYAI_LIMIT_USD':'1',
                                   'ASSEMBLYAI_USD_PER_HOUR':'0.21','ASSEMBLYAI_TIMEOUT_S':'30'})
        env.start();self.addCleanup(env.stop)
        poll=patch.object(providers,'ASSEMBLYAI_POLL_SECONDS',0);poll.start();self.addCleanup(poll.stop)
        self.path=os.path.join(self.media_root,'nota.webm')
        with open(self.path,'wb') as handle:handle.write(WEBM)

    def mock(self,service):
        return patch.object(providers,'ASSEMBLYAI_TRANSPORT',httpx.MockTransport(service))

    def test_capture_is_transcribed_reserved_and_settled_with_the_real_duration(self):
        service=AssemblyAIMock()
        with self.mock(service):
            body=self.send(audio=audio(),audio_duration_s='42',para='post');self.drain()
        capture=self.capture(body)
        self.assertEqual((capture.state,capture.transcript,capture.transcript_language,capture.transcript_provider_id,capture.audio_duration_s),
                         ('idea','Hola equipo, una idea para el jueves.','es','tr_123',40.0))
        self.assertEqual([r[3] for r in service.requests if r[1]=='/v2/upload'],[WEBM])
        self.assertEqual(service.created(),[{'audio_url':'https://cdn.assemblyai.com/upload/f756988d',
                                            'speech_models':['universal-3-5-pro','universal-2'],'language_detection':True}])
        self.assertEqual(service.reserved_at_upload,['reserved'])  # reserved before any byte left
        row=ledger()[0]
        self.assertEqual((row['status'],row['purpose']),('complete','capture-transcribe'))
        self.assertEqual(row['reserved_usd'],Decimal('42')*Decimal('0.21')/3600)
        self.assertEqual(row['actual_usd'],Decimal('40')*Decimal('0.21')/3600)
        self.assertEqual((row['usage']['transcript_id'],row['usage']['speech_model_used']),('tr_123','universal-3-5-pro'))
        self.assertEqual(len([r for r in service.requests if r[0]=='GET']),2)  # processing, then completed
        settings=self.human.get('/api/v1/ajustes').json()['ai_spend']
        self.assertAlmostEqual(settings['transcription_month_usd'],40*0.21/3600)

    def test_universal_2_is_settled_at_its_price_and_an_unknown_duration_reserves_the_cap(self):
        service=AssemblyAIMock(final={'status':'completed','text':'Olá','language_code':'pt','audio_duration':60,'speech_model_used':'universal-2'})
        with self.mock(service):result=providers.assemblyai_transcribe(self.path,None)
        self.assertEqual((result['text'],result['language'],result['model']),('Olá','pt','universal-2'))
        row=ledger()[0]
        self.assertEqual(row['reserved_usd'],Decimal('1800')*Decimal('0.21')/3600)
        self.assertEqual(row['actual_usd'],Decimal('60')*Decimal('0.15')/3600)

    def test_an_errored_transcript_is_not_charged(self):
        service=AssemblyAIMock(final={'status':'error','error':'File does not appear to contain audio.'})
        with self.mock(service):
            body=self.send(audio=audio(),audio_duration_s='10',para='post');self.drain()
        capture=self.capture(body)
        self.assertEqual(capture.state,'error')
        self.assertEqual(capture.error,'AssemblyAI no pudo transcribir el audio: File does not appear to contain audio.')
        row=ledger()[0];self.assertEqual((row['status'],row['actual_usd']),('rejected',None))

    def test_a_timeout_leaves_the_capture_in_error_and_never_retries(self):
        service=AssemblyAIMock(statuses=['processing']*1000)
        with patch.dict(os.environ,{'ASSEMBLYAI_TIMEOUT_S':'0'}),self.mock(service):
            body=self.send(audio=audio(),audio_duration_s='10',para='post');self.drain()
        capture=self.capture(body)
        self.assertEqual(capture.state,'error');self.assertIn('no terminó en 0 s',capture.error)
        self.assertEqual(len(service.created()),1)
        self.assertEqual(ledger()[0]['status'],'uncertain')  # AssemblyAI may still bill it
        # The same audio cannot be sent again while that attempt is uncertain.
        with self.mock(service),self.assertRaisesRegex(ValueError,'solicitud idéntica'):providers.assemblyai_transcribe(self.path,10)

    def test_server_errors_on_create_are_uncertain_and_not_repeated(self):
        service=AssemblyAIMock(create_status=503)
        with self.mock(service),self.assertRaisesRegex(ValueError,'HTTP 503'):providers.assemblyai_transcribe(self.path,10)
        self.assertEqual((len(service.created()),ledger()[0]['status']),(1,'uncertain'))

    def test_limit_and_switch_are_checked_before_any_request(self):
        service=AssemblyAIMock()
        with patch.dict(os.environ,{'ASSEMBLYAI_LIMIT_USD':'0.001'}),self.mock(service),self.assertRaisesRegex(ValueError,'Límite local de assemblyai'):
            providers.assemblyai_transcribe(self.path,600)
        with patch.dict(os.environ,{'LIVE_PROVIDERS':'false'}),self.mock(service),self.assertRaisesRegex(ValueError,'Proveedores desactivados'):
            providers.assemblyai_transcribe(self.path,10)
        with patch.dict(os.environ,{'ASSEMBLYAI_API_KEY':''}),self.mock(service),self.assertRaisesRegex(ValueError,'ASSEMBLYAI_API_KEY'):
            providers.assemblyai_transcribe(self.path,10)
        self.assertEqual((service.requests,ledger()),([],[]))


class DirectorIdeasTests(MediaMixin,EditorialBase):
    def setUp(self):
        super().setUp();self.use_media()

    def test_director_receives_ideas_and_feedback_and_marks_used_ideas(self):
        now=timezone.now()
        idea=Capture.objects.create(created_by=self.gustavo,note='La pizarra del piloto: decidir qué medir antes de construir.',
                                    purpose='post',state='idea')
        stale=Capture.objects.create(created_by=self.gustavo,note='Idea vieja',purpose='post',state='idea')
        Capture.objects.filter(pk=stale.pk).update(created_at=now-timedelta(days=20))
        yesterday=now.astimezone(operador.local_tz()).date()-timedelta(days=1)
        old=EditorialPiece.objects.create(account=self.official,slot_date=yesterday,scheduled_for=now-timedelta(days=1),state='skipped',
                                          brief={'thesis':'Evals before features.'})
        Capture.objects.create(created_by=self.gustavo,note='Muy largo; recorta.',context_type='pieza',context_id=str(old.id),state='anotado')
        plan=answers();plan['director']=dict(plan['director'],ideas_used=[str(idea.id),'no-es-un-id',str(stale.id)])
        piece=self.plan(plan)
        director=self.calls[0][1]
        # Each idea now also carries its purpose, «lo antes posible» and its photos (IMG-06, CAP-16).
        self.assertEqual([{k:i[k] for k in ('id','text','date')} for i in director['ideas_from_gustavo']],
                         [{'id':str(idea.id),'text':idea.note,'date':now.astimezone(operador.local_tz()).date().isoformat()}])
        self.assertEqual({k:director['ideas_from_gustavo'][0][k] for k in ('publish_asap','photos')},{'publish_asap':False,'photos':[]})
        self.assertEqual(director['feedback_from_gustavo'],[{'piece_date':yesterday.isoformat(),'thesis':'Evals before features.',
                                                              'comment':'Muy largo; recorta.','date':now.astimezone(operador.local_tz()).date().isoformat()}])
        self.assertIn('ideas_from_gustavo',self.calls[0][2])
        idea.refresh_from_db();stale.refresh_from_db()
        self.assertEqual(idea.state,'usado')
        self.assertEqual(idea.outcome,{'kind':'usado','text':f'El Director editorial lo usó en el brief del {capturas.day_label(piece.slot_date)}',
                                       'link':f'/calendario/pieza/{piece.id}'})
        self.assertEqual(stale.state,'sin_usar')  # 14 days without fitting a brief; never offered, never marked
        self.assertIn('ideas_used',editorial.BRIEF_SCHEMA['required'])
