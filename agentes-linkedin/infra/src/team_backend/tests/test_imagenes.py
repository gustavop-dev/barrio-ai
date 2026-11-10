"""Image workflow contracts. All provider and LinkedIn IO uses explicit fakes/transports.
Run on CI only; these tests never need a paid key or a LinkedIn account.
"""
import base64
import copy
import io
import json
import os
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
import httpx
from PIL import Image
from django.core.files.base import ContentFile
from django.test import SimpleTestCase
from django.utils import timezone
from knowledge import db, providers
from team_backend import autopiloto, capturas, connectors_images, connectors_linkedin, imagenes, infografias, operador
from team_backend.connectors import ConnectorError, ConnectorUncertain
from team_backend.models import AuditEvent, Capture, EditorialPiece, GalleryPhoto, PieceImage
from team_backend.tests.test_publicacion import EditorialBase, PublicationBase, GOOD_POST, answers
from team_backend.tests.test_capturas import CaptureBase, photo


def png(size=(1080,1080),color='#F7F6F0'):
    buffer=io.BytesIO();Image.new('RGB',size,color).save(buffer,format='PNG');return buffer.getvalue()


def slide(template='pasos'):
    value=dict(infografias.fallback(),template=template,label='DECISIONS',title='Start with a decision',highlight='',subtitle='',body='')
    if template=='pasos':value.update(steps=['Name the decision','Compare the options','Record the reason'])
    if template=='portada':value.update(highlight='decision')
    if template=='numero':value.update(number='6',unit='days',source={'ref':'fact','label':'Public record','date':'2026','estimate':False})
    if template=='barras':value.update(bars=[{'label':'First','value':6,'focus':True},{'label':'Second','value':3,'focus':False}],
                                      source={'ref':'fact','label':'Public record','date':'2026','estimate':False})
    if template=='cierre':value.update(title='Which decision needs a clearer reason?')
    return value


def choice(photo,edit='none'):
    return {'id':str(photo.id),'reason':'Contexto de la propuesta','alt':'Gustavo shares a photograph from a product workshop.',
            'edit':edit,'edit_reason':'Está oscura' if edit=='light' else '', 'instruction':'','instruction_kind':'none'}


class RendererTests(SimpleTestCase):
    def test_four_board_templates_dimensions_palette_and_private_bundled_font(self):
        for name in ('portada','pasos','barras','numero'):
            with self.subTest(template=name):
                data={'slides':[slide(name)]};infografias.validate(data,'infografia',[{'key':'fact'}])
                raw=infografias.render(data['slides'][0]);im=Image.open(io.BytesIO(raw))
                self.assertEqual(im.size,(1080,1080));self.assertEqual(im.format,'PNG')
                expected=(30,30,43) if name in ('portada','numero') else (247,246,240)
                self.assertEqual(im.getpixel((95,95)),expected)
                self.assertEqual(im.getpixel((985,985)),expected)
                self.assertEqual(infografias.font(28).getname()[0],'Ubuntu')
        self.assertGreaterEqual(infografias.contrast(infografias.DEEP,infografias.PAPER),4.5)
        self.assertIn('"columnas": 6',infografias.rule());self.assertIn('Revisión antes de publicar',infografias.rule())
        self.assertIn(infografias.version(),infografias.with_rule('Diseña'))

    def test_carousel_has_cover_closing_numbering_and_tagged_alt_in_pdf(self):
        data={'slides':[slide('portada'),slide(),slide('cierre')]};infografias.validate(data,'carrusel')
        raws=[infografias.render(s,i+1,3,True) for i,s in enumerate(data['slides'])]
        self.assertTrue(all(Image.open(io.BytesIO(raw)).size==(1080,1350) for raw in raws))
        pdf=infografias.document(raws,[s['alt'] for s in data['slides']])
        self.assertTrue(pdf.startswith(b'%PDF-1.7'));self.assertEqual(pdf.count(b'/S /Figure'),3)
        self.assertEqual(pdf.count(b'/Alt <'),3);self.assertIn(b'/Marked true',pdf);self.assertIn(b'/Count 3',pdf)

    def test_rejects_long_text_forbidden_graphs_unsourced_data_and_missing_alt(self):
        mutations=[{'title':'one two three four five six seven eight nine'}, {'body':'word '*41},
                   {'template':'pie3d'}, {'steps':['one','two']}, {'steps':['one']*6}, {'alt':''}, {'title':'Hello 🚀'},
                   {'title':'SHOUTING headline'}, {'title':'#topic here'}, {'title':'A question!!'}]
        for mutation in mutations:
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):
                infografias.validate({'slides':[dict(slide(),**mutation)]},'infografia')
        for template in ('numero','barras'):
            with self.assertRaises(ValueError):infografias.validate({'slides':[slide(template)]},'infografia')
        value=slide('numero');value['source']['estimate']=True
        with self.assertRaises(ValueError):infografias.validate({'slides':[value]},'infografia',[{'key':'fact'}])
        value=slide('barras');value['bars']*=3
        with self.assertRaises(ValueError):infografias.validate({'slides':[value]},'infografia',[{'key':'fact'}])
        with self.assertRaises(ValueError):infografias.validate({'slides':[slide('portada')]*9},'carrusel')


class ImageWorkflowTests(EditorialBase):
    def piece(self,kind='foto',photo=None,edit='none'):
        count=EditorialPiece.objects.count()+20;when=timezone.now()+timedelta(days=count)
        brief={'image':{'kind':kind,'reason':'La imagen explica el contexto','photos':[choice(photo,edit)] if photo else []},
               'gallery_offered':[str(photo.id)] if photo else []}
        return EditorialPiece.objects.create(account=self.official,slot_date=when.date(),scheduled_for=when,brief=brief,
            final_text=GOOD_POST,verification={'verdict':'ready_for_execution','text_sha256':imagenes.sha(GOOD_POST.encode())})

    def photo(self,ai='auto',instruction='',kind='none',size=(1080,1080)):
        raw=png(size);p=GalleryPhoto(mime='image/png',size_bytes=len(raw),created_by=self.gustavo,ai_edit=ai,
            instruction=instruction,instruction_kind=kind,note=instruction)
        p.image.save('original.png',ContentFile(raw),save=False);p.save();return p

    def test_edit_options_note_precedence_and_conservative_team_decision(self):
        cases=[('no','recórtala','edit','light',False,'prohibida'),('auto','úsala tal cual','original','light',False,'Gustavo'),
               ('auto','más luz','edit','none',True,'Gustavo'),('auto','','none','none',False,'no necesita'),
               ('auto','','none','light',True,'equipo'),('si','','none','none',True,'pedida'),
               ('auto','ponme en un coworking y arregla mi pelo','edit','none',True,'Gustavo'),
               ('si','cambia la persona','unsafe','none',False,'no segura')]
        for ai,note,kind,edit,should_edit,reason in cases:
            with self.subTest(ai=ai,note=note,edit=edit):
                p=self.photo(ai,note,kind);original=imagenes.read(p.image);piece=self.piece(photo=p,edit=edit)
                fake=connectors_images.FakeImageConnector(edited=png((1024,1024),'#dedfd4'))
                imagenes.prepare(piece,client=fake);row=piece.images.get();p.refresh_from_db()
                self.assertEqual(row.edited,should_edit);self.assertIn(reason,row.reason)
                self.assertEqual(imagenes.read(p.image),original)
                self.assertEqual([x[0] for x in fake.calls],['edit','check'] if should_edit else [])
                if should_edit:
                    self.assertNotEqual(row.image.name,p.image.name);self.assertEqual(p.state,'editada')
                    self.assertEqual(row.review['sha256'],[row.sha256])

    def test_disabled_or_missing_keys_use_original_and_rejection_or_error_discards_edit(self):
        for env in ({'LIVE_PROVIDERS':'false'},{'LIVE_PROVIDERS':'true','OPENAI_API_KEY':''}):
            with patch.dict(os.environ,env),patch.object(connectors_images.ImageConnector,'edit',side_effect=AssertionError('paid edit')):
                p=self.photo('si');piece=self.piece(photo=p);imagenes.prepare(piece)
                self.assertFalse(piece.images.get().edited)
        for fake in (connectors_images.FakeImageConnector(ok=False),connectors_images.FakeImageConnector(error='Presupuesto agotado')):
            p=self.photo('si');piece=self.piece(photo=p);imagenes.prepare(piece,client=fake)
            self.assertFalse(piece.images.get().edited);p.refresh_from_db();self.assertEqual(p.state,'elegida')
            self.assertEqual(imagenes.read(piece.images.get().image),imagenes.read(p.image))

    def test_no_gallery_no_keys_falls_back_to_private_brand_card_with_alt(self):
        piece=self.piece('infografia')
        with patch.dict(os.environ,{'LIVE_PROVIDERS':'false'}),patch('knowledge.providers.claude',side_effect=AssertionError('paid API')):
            imagenes.prepare(piece)
        row=piece.images.get();self.assertEqual(row.kind,'tarjeta');self.assertTrue(row.alt)
        self.assertEqual(imagenes.issues(piece,imagenes.manifest(piece)),[])
        data=self.human.get(f'/api/v1/editorial/pieces/{piece.id}').json();self.assertEqual(data['images'][0]['kind'],'tarjeta')
        url=data['images'][0]['url'];response=self.human.get(url)
        self.assertEqual(response.status_code,200);self.assertIn('private',response['Cache-Control']);response.close()
        from rest_framework.test import APIClient
        self.assertIn(APIClient().get(url).status_code,(401,403))

    def test_infographic_and_carousel_use_code_and_one_bounded_repair(self):
        for kind,slides in [('infografia',[slide()]),('carrusel',[slide('portada'),slide(),slide('cierre')])]:
            piece=self.piece(kind);fake=connectors_images.FakeImageConnector()
            bad={'slides':[dict(slide(),title='word '*9)]};good={'slides':slides}
            with patch('knowledge.providers.claude',side_effect=[{'text':json.dumps(bad)},{'text':json.dumps(good)}]) as model:
                imagenes.prepare(piece,client=fake)
            self.assertEqual(model.call_count,2);self.assertEqual(piece.images.count(),len(slides))
            self.assertEqual([c[0] for c in fake.calls],['check']);self.assertEqual(piece.image_kind,kind)
            self.assertIn(infografias.version(),model.call_args.args[0])
            self.assertEqual(bool(piece.image_document),kind=='carrusel')
            self.assertEqual(imagenes.issues(piece,imagenes.manifest(piece)),[])

    def test_bad_vision_falls_back_and_provider_failure_is_not_retried(self):
        piece=self.piece('infografia');fake=connectors_images.FakeImageConnector(ok=False)
        with patch('knowledge.providers.claude',return_value={'text':json.dumps({'slides':[slide()]})}) as model:
            imagenes.prepare(piece,client=fake)
        self.assertEqual(model.call_count,2);self.assertEqual(piece.image_kind,'tarjeta')
        self.assertIn('rechazada',piece.image_reason)
        piece=self.piece('infografia')
        with patch('knowledge.providers.claude',side_effect=ValueError('Proveedor incierto')) as model:
            imagenes.prepare(piece,client=connectors_images.FakeImageConnector())
        self.assertEqual(model.call_count,1);self.assertEqual(piece.image_kind,'tarjeta')

    def test_tampered_bytes_alt_and_document_never_pass_policy(self):
        piece=self.piece('infografia');imagenes.fallback(piece,'Fixture');expected=imagenes.manifest(piece);row=piece.images.get()
        row.alt='Changed';row.save(update_fields=['alt']);self.assertTrue(imagenes.issues(piece,expected))
        expected=imagenes.manifest(piece)
        with row.image.open('wb') as file:file.write(png(color='black'))
        self.assertIn('Los bytes de la imagen cambiaron',imagenes.issues(piece,expected))

    def test_gallery_usage_release_and_delete_all_versions(self):
        p=self.photo('si');piece=self.piece(photo=p);imagenes.prepare(piece,client=connectors_images.FakeImageConnector())
        p.refresh_from_db();self.assertEqual(p.chosen_piece_id,piece.id)
        data=capturas.photo_payload(p);self.assertIn('Usada en la pieza del',data['used_in']['text']);self.assertEqual(len(data['versions']),1)
        names=[p.image.name,piece.images.get().image.name];storage=p.image.storage
        imagenes.release(piece);p.refresh_from_db();self.assertEqual(p.state,'sin_usar')
        imagenes.published(piece);p.refresh_from_db();self.assertEqual(p.state,'publicada');self.assertIsNotNone(p.published_at)
        capturas.delete_photo(self.gustavo,p)
        self.assertFalse(piece.images.exists());self.assertTrue(all(not storage.exists(n) for n in names))

    def test_original_landscape_stays_untouched_and_deleted_choice_falls_back(self):
        p=self.photo('no',size=(1200,600));piece=self.piece(photo=p);imagenes.prepare(piece)
        self.assertEqual((piece.images.get().width,piece.images.get().height),(1200,600))
        p=self.photo();piece=self.piece(photo=p);capturas.delete_photo(self.gustavo,p);imagenes.prepare(piece)
        self.assertEqual(piece.image_kind,'tarjeta')

    def test_real_circuit_publishes_image_once_and_upload_failure_never_creates_post(self):
        piece=self.plan(answers());proposal=editorial_action(piece)
        autopiloto.policy_review(proposal);self.arrive(piece)
        self.linkedin.state['fail_next']='upload_error'
        result=operador.execute(self.autobot,proposal.id)
        self.assertEqual(result.state,'failed');self.assertFalse(result.wrote);self.assertEqual(self.linkedin.state['posts'],[])
        self.assertEqual(operador.execute(self.autobot,proposal.id).id,result.id)
        self.assertEqual(self.linkedin.state['uploads'],[])

    def test_post_uncertainty_does_not_repeat_upload_or_post(self):
        proposal=self.ready_piece(0);self.linkedin.state['fail_next']='uncertain_applied'
        first=operador.execute(self.autobot,proposal.id);second=operador.execute(self.autobot,proposal.id)
        self.assertEqual((first.state,first.id),('uncertain',second.id));self.assertEqual(len(self.linkedin.state['uploads']),1)
        body=self.linkedin.state['posts'][0]['body'];self.assertTrue(body['content']['media']['altText'])


def editorial_action(piece):return piece.proposals.get()


class PolicyMediaAvailabilityTests(EditorialBase):
    def proposal(self,document=False,text=GOOD_POST):
        when=timezone.now()+timedelta(days=EditorialPiece.objects.count()+20)
        piece=EditorialPiece.objects.create(account=self.official,slot_date=when.date(),scheduled_for=when,state='ready',
            final_text=text,verification={'verdict':'ready_for_execution','text_sha256':imagenes.sha(text.encode())})
        imagenes.fallback(piece,'Fixture sin proveedores')
        if document:
            raw=b'%PDF-1.7\nfixture'
            piece.image_kind='carrusel';piece.image_document_sha256=imagenes.sha(raw)
            piece.image_document.save('fixture.pdf',ContentFile(raw),save=False);piece.save()
        return operador.create_proposal(self.gustavo,None,'CONT-09',{'text':text},citations=['LI-04-M005-K01'],source='agent',piece=piece)

    def test_unreadable_files_wait_and_a_later_tick_approves_after_recovery(self):
        """A missing mount must not permanently discard the day or release its captured ideas."""
        self.account.paused=True;self.account.save();self.official.paused=True;self.official.save()
        for kind,expected in (('image',['Imagen no disponible']),('document',['Documento no disponible']),
                              ('both',['Imagen no disponible','Documento no disponible'])):
            with self.subTest(kind=kind):
                proposal=self.proposal(document=kind!='image');piece=proposal.piece
                capture=Capture.objects.create(created_by=self.gustavo,state='usado',routed_to={'used_in':str(piece.id)})
                missing={piece.images.get().image.name} if kind=='image' else {piece.image_document.name}
                if kind=='both':missing.add(piece.images.get().image.name)
                read=imagenes.read
                def unavailable(field):
                    if field.name in missing:raise FileNotFoundError('Fixture: volumen no disponible')
                    return read(field)
                with patch('team_backend.imagenes.read',side_effect=unavailable):
                    self.assertEqual(autopiloto.post_issues(proposal),expected)
                    with self.assertLogs('team_backend.autopilot',level='WARNING') as logs:
                        autopiloto.tick(self.autobot)
                proposal.refresh_from_db();capture.refresh_from_db()
                self.assertEqual((proposal.state,proposal.decision_note,proposal.decided_at,proposal.risks),('proposed','',None,[]))
                self.assertEqual((capture.state,capture.routed_to),('usado',{'used_in':str(piece.id)}))
                self.assertIn(str(proposal.id),logs.output[0])
                self.assertEqual(AuditEvent.objects.filter(action='operator.policy_discarded',target=str(proposal.id)).count(),0)
                autopiloto.tick(self.autobot);proposal.refresh_from_db()
                self.assertEqual((proposal.state,proposal.approved_hash),('approved',proposal.payload_hash))

    def test_unreadable_image_with_content_problem_still_discards(self):
        """A missing image must not hide a content violation or turn it into an endless retry."""
        proposal=self.proposal(text=GOOD_POST+' Contact me for more.')
        with patch('team_backend.imagenes.read',side_effect=PermissionError('Fixture: permiso denegado')):
            autopiloto.policy_review(proposal)
        proposal.refresh_from_db()
        self.assertEqual(proposal.state,'discarded')
        self.assertIn('Contiene pitch agresivo o petición de contacto',proposal.risks)
        self.assertIn('Imagen no disponible',proposal.risks)
        self.assertEqual(AuditEvent.objects.filter(action='operator.policy_discarded',target=str(proposal.id)).count(),1)

    def test_unreadable_document_with_changed_image_still_discards(self):
        """Retryable storage errors must not bypass the exact-image integrity gate."""
        proposal=self.proposal(document=True)
        def unavailable_or_changed(field):
            if field.name==proposal.piece.image_document.name:raise OSError('Fixture: volumen no disponible')
            return b'changed bytes'
        with patch('team_backend.imagenes.read',side_effect=unavailable_or_changed):
            autopiloto.policy_review(proposal)
        proposal.refresh_from_db()
        self.assertEqual(proposal.state,'discarded')
        self.assertEqual(proposal.risks,['Los bytes de la imagen cambiaron','Documento no disponible'])


class ImageProviderContracts(PublicationBase):
    def test_profile_edits_fit_one_dollar_month_after_embeddings_and_report_shortfall(self):
        raw=png((1024,1024));calls=[]
        def handler(request):
            calls.append(request)
            self.assertEqual(request.content.count(b'name="image[]"'),2 if len(calls)<3 else 3)
            return httpx.Response(200,json={'data':[{'b64_json':base64.b64encode(raw).decode()}],
                'usage':{'input_tokens_details':{'text_tokens':500,'image_tokens':1200},'output_tokens':1056}})
        with patch.dict(os.environ,{'LIVE_PROVIDERS':'true','OPENAI_API_KEY':'fake-only','OPENAI_LIMIT_USD':'1'}), \
             patch.object(connectors_images,'TRANSPORT',httpx.MockTransport(handler)):
            rid=providers.reserve('openai','embedding',Decimal('.036'));providers.settle(rid,'complete',{},Decimal('.036'))
            for kind in ('A','B','banner'):
                refs={'01':raw,'03':raw}
                if kind=='banner':refs['02']=raw
                connectors_images.ImageConnector().edit_profile(refs,'Only the authorized edit',kind)
            self.assertEqual(len(calls),3)
            with db.connect() as c:
                rows=c.execute("SELECT * FROM usage_ledger WHERE purpose='profile-image-edit'").fetchall()
            self.assertEqual(len(rows),3)
            self.assertTrue(all(r['status']=='complete' and r['actual_usd']==Decimal('.05674') for r in rows))
            self.assertTrue(all(Decimal('.05')<=r['reserved_usd']<Decimal('.25') for r in rows))
            with self.assertRaisesRegex(ValueError,r'faltan [0-9.]+ USD; límite 1, gastado'):
                providers.reserve('openai','profile-image-edit',Decimal('1'))
            self.assertEqual(len(calls),3)

    def test_openai_multipart_usage_and_never_retry_timeout(self):
        calls=[];raw=png((1024,1024))
        def handler(request):
            calls.append(request);self.assertEqual(str(request.url),connectors_images.EDIT_URL)
            self.assertIn('multipart/form-data',request.headers['Content-Type'])
            self.assertIn(b'name="image"',request.content);self.assertIn(connectors_images.EDIT_MODEL.encode(),request.content)
            return httpx.Response(200,json={'data':[{'b64_json':base64.b64encode(raw).decode()}],
                'usage':{'input_tokens_details':{'text_tokens':100,'image_tokens':200},'output_tokens':30}})
        # PublicationBase caps editorial at $1. Images now count there too: leave room for the
        # settled first edit plus the next estimated reservation so this test actually reaches the timeout.
        env={'LIVE_PROVIDERS':'true','OPENAI_API_KEY':'fake-only','OPENAI_LIMIT_USD':'10','IMAGE_DAILY_USD':'10',
             'EDITORIAL_DAILY_LLM_USD':'10'}
        with patch.dict(os.environ,env),patch.object(connectors_images,'TRANSPORT',httpx.MockTransport(handler)):
            self.assertEqual(connectors_images.ImageConnector().edit(raw,'Only light','first'),raw)
        with db.connect() as c:row=c.execute("SELECT * FROM usage_ledger WHERE purpose='image-edit'").fetchone()
        self.assertEqual(row['status'],'complete');self.assertEqual(row['actual_usd'],Decimal('0.0037'))
        def timeout(request):calls.append(request);raise httpx.ReadTimeout('fake',request=request)
        with patch.dict(os.environ,env),patch.object(connectors_images,'TRANSPORT',httpx.MockTransport(timeout)):
            with self.assertRaisesRegex(ValueError,'Edición incierta; no se repite'):
                connectors_images.ImageConnector().edit(raw,'Only light','second')
            self.assertEqual(len(calls),2)  # one success, one timed-out request; no automatic retry
            with db.connect() as c:
                uncertain=c.execute("SELECT * FROM usage_ledger WHERE request_hash='second'").fetchone()
            self.assertEqual(uncertain['status'],'uncertain')
            self.assertEqual(uncertain['reserved_usd'],row['reserved_usd'])
            self.assertGreaterEqual(uncertain['reserved_usd'],connectors_images.EDIT_MINIMUM)
            self.assertLess(uncertain['reserved_usd'],Decimal('0.25'))
            self.assertIsNone(uncertain['actual_usd'])
            # Re-invoking the same request is also blocked before HTTP, without a new ledger row.
            with self.assertRaisesRegex(ValueError,'solicitud idéntica pendiente o incierta'):
                connectors_images.ImageConnector().edit(raw,'Only light','second')
        self.assertEqual(len(calls),2)
        with db.connect() as c:
            rows=c.execute("SELECT * FROM usage_ledger WHERE purpose='image-edit' ORDER BY created_at,id").fetchall()
        self.assertEqual(len(rows),2)
        self.assertEqual(next(r for r in rows if r['request_hash']=='second'),uncertain)

    def test_images_of_both_providers_count_in_the_team_budget_and_the_editorial_total(self):
        with patch.dict(os.environ,{'AI_DAILY_FUSE_USD':'0.10','OPENAI_LIMIT_USD':'10','ANTHROPIC_LIMIT_USD':'10'}):
            rid=providers.reserve('openai','image-edit',Decimal('.08'))
            with self.assertRaises(ValueError):providers.reserve('anthropic','image-check',Decimal('.03'))
            providers.settle(rid,'complete',{},Decimal('.04'))
            providers.reserve('anthropic','image-check',Decimal('.03'))
        self.assertEqual(imagenes.spent_today(),Decimal('.07'))
        from team_backend import editorial
        self.assertEqual(editorial.spent_today(),Decimal('.07'));self.assertEqual(autopiloto.llm_spent_today(),0)
        budgets=self.human.get('/api/v1/ajustes').json()['ai_spend']['today']
        self.assertEqual(next(b for b in budgets if b['budget']=='imagenes')['spent_usd'],.07)

    def test_vision_sees_original_edit_instruction_post_and_hashes_exact_output(self):
        original=png();edited=png(color='gray')
        verdict={'ok':True,'reasons':[],'checks':[]}
        with patch.dict(os.environ,{'LIVE_PROVIDERS':'true','ANTHROPIC_API_KEY':'fake-only'}),\
             patch('knowledge.providers.claude',return_value={'text':json.dumps(verdict)}) as model:
            result=connectors_images.ImageConnector().check([edited],{'post':GOOD_POST},original,'more light')
        self.assertEqual(result['sha256'],[imagenes.sha(edited)])
        self.assertEqual(model.call_args.kwargs['purpose'],'image-check')
        self.assertEqual(sum(b['type']=='image' for b in model.call_args.args[1]),2)
        self.assertIn('more light',model.call_args.args[1][0]['text'])

    def test_linkedin_image_document_upload_and_multimage_shapes(self):
        cred=self.credential();seen=[]
        def handler(request):
            seen.append((request.method,request.url.path))
            if request.url.query==b'action=initializeUpload':
                self.assertEqual(json.loads(request.content),{'initializeUploadRequest':{'owner':cred.member_urn}})
                key='document' if request.url.path.endswith('documents') else 'image'
                return httpx.Response(200,json={'value':{key:f'urn:li:{key}:123','uploadUrl':'https://www.linkedin.com/upload'}})
            if request.method=='PUT':return httpx.Response(201)
            if request.method=='GET':return httpx.Response(200,json={'status':'AVAILABLE'})
            body=json.loads(request.content);self.assertIn('content',body)
            return httpx.Response(201,headers={'x-restli-id':'urn:li:share:123'})
        with patch.dict(os.environ,{'LIVE_LINKEDIN_OFFICIAL':'true'}),patch.object(connectors_linkedin,'TRANSPORT',httpx.MockTransport(handler)):
            client=connectors_linkedin.LinkedInOfficialConnector(cred.account)
            image=client.upload_media(png(),'image/png','The photo description')
            client.create_post('The post',[image])
            doc=client.upload_media(b'%PDF-1.7','application/pdf','Alt in PDF','A process')
            client.create_post('A carousel',[doc])
        body=connectors_linkedin.post_body(cred.member_urn,'Text',[image,image]);self.assertIn('multiImage',body['content'])
        body=connectors_linkedin.post_body(cred.member_urn,'Text',[doc]);self.assertEqual(body['content']['media'],{'id':'urn:li:document:123','title':'A process'})
        self.assertEqual(len(seen),8)

    def test_upload_auth_rate_limit_and_timeout_are_definite_and_pause_as_required(self):
        cred=self.credential()
        for status in (401,403,429,500):
            def handler(request):return httpx.Response(status)
            with patch.dict(os.environ,{'LIVE_LINKEDIN_OFFICIAL':'true'}),patch.object(connectors_linkedin,'TRANSPORT',httpx.MockTransport(handler)):
                with self.assertRaises(ConnectorError) as err:
                    connectors_linkedin.LinkedInOfficialConnector(cred.account).upload_media(png(),'image/png','Alt')
            self.assertEqual(err.exception.pause,status in (401,403,429));self.assertEqual(err.exception.kind,'upload')


class CaptureImageApiTests(CaptureBase):
    def test_tri_state_defaults_legacy_alias_and_capture_context_all_destinations(self):
        self.assertEqual(self.human.patch('/api/v1/ajustes/preferencias',{'gallery_ai_edit':'si'},format='json').status_code,200)
        body=self.send(para='propuesta',nota='Una propuesta con fotos',ai_edit='no',fotos=[photo()])
        self.drain();capture=self.capture(body);p=capture.photos.get()
        self.assertEqual((capture.ai_edit,p.ai_edit,p.note),('no','no','Una propuesta con fotos'))
        response=self.human.patch(f'/api/v1/galeria/{p.id}',{'ai_edit':'auto'},format='json')
        self.assertEqual(response.json()['ai_edit'],'auto')
        self.assertEqual(self.human.patch(f'/api/v1/galeria/{p.id}',{'ai_edit':'maybe'},format='json').status_code,400)
        self.assertEqual(self.human.patch(f'/api/v1/galeria/{p.id}',{'allow_ai_edit':False},format='json').json()['ai_edit'],'no')

    def test_structured_understanding_assigns_per_photo_instructions_without_a_second_call(self):
        instruction='la primera tal cual; a la segunda más luz'
        answer={'destino':'propuesta','motivo':'Recomienda un post con fotos','publish_asap':True,'evidence':'publícalo cuanto antes',
                'not_before':'','photo_instructions':[{'index':1,'instruction':'tal cual','kind':'original'},
                                                     {'index':2,'instruction':'más luz','kind':'edit'}]}
        with patch('knowledge.providers.claude',return_value={'text':json.dumps(answer)}) as model:
            body=self.send(nota=instruction+'; publícalo cuanto antes',fotos=[photo(),photo()]);self.drain()
        capture=self.capture(body);self.assertTrue(capture.publish_asap);self.assertEqual(model.call_count,1)
        self.assertEqual(set(capture.photos.values_list('instruction_kind',flat=True)),{'original','edit'})
        self.assertTrue(all(p.note==capture.note for p in capture.photos.all()))
