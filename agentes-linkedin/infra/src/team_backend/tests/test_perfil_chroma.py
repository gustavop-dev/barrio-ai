"""Synthetic mattes and HTTP fakes only; no real image/vision provider."""
import base64
import io
import json
from unittest.mock import patch
import httpx
from django.test import SimpleTestCase
from PIL import Image, ImageDraw
from knowledge import providers
from team_backend import connectors_images as images, imagenes, perfil_assets, perfil_chroma as chroma, perfil_visual as visual


def keyed_photo(*,hole=False,size=256):
    image=Image.new('RGB',(256,256),images.CHROMA_COLOR)
    draw=ImageDraw.Draw(image)
    draw.rectangle((75,20,180,255),fill=(170,120,85))
    if hole:draw.rectangle((100,100,150,160),fill=images.CHROMA_COLOR)
    if size!=256:image=image.resize((size,size))
    out=io.BytesIO();image.save(out,format='PNG');return out.getvalue()


def small_head():
    """Hair-to-neck is 320/800 (~40%); white chest extends below the frame."""
    image=Image.new('RGBA',(800,800))
    draw=ImageDraw.Draw(image)
    draw.polygon([(360,420),(440,420),(650,560),(700,799),(100,799),(150,560)],fill=(240,240,240,255))
    draw.rectangle((360,320,439,455),fill=(170,120,85,255))
    draw.ellipse((272,72,527,391),fill=(170,120,85,255))
    return image


class ChromaTests(SimpleTestCase):
    def test_forty_percent_head_is_scaled_to_fifty_eight_for_both_portraits(self):
        source=small_head();alpha=source.getchannel('A')
        bounds=chroma.head_bounds(alpha)
        self.assertEqual(bounds['method'],'alpha-neck-minimum')
        self.assertAlmostEqual((bounds['neck']-bounds['top'])/800,.40,delta=.025)
        framed,framing=chroma.frame_portrait(source,(800,800))
        actual=chroma.head_bounds(framed.getchannel('A'))
        self.assertAlmostEqual((actual['neck']-actual['top'])/800,.58,delta=.025)
        self.assertAlmostEqual(actual['top']/800,.09,delta=.01)
        self.assertGreater(framing['scale'],1.4)
        self.assertLess(framing['crop_box'][3],800)  # Crop the chest, not padded full body.
        evidence=[]
        for kind in ('A','B'):
            raw,rows=visual.portrait(source,kind,with_evidence=True)
            measured={row['id']:row for row in rows};evidence.append(measured['render.framing'])
            self.assertTrue(all(row['ok'] for row in rows))
            self.assertEqual({row['sha256'] for row in rows},{imagenes.sha(raw)})
            self.assertAlmostEqual(measured['render.framing']['head_height'],.58,delta=.01)
            self.assertLessEqual(measured['render.framing']['eyes_y_estimate'],1/3)
            with Image.open(io.BytesIO(raw)) as final:
                outside=[rgb for rgb,a in zip(final.getdata(),framed.getchannel('A').getdata()) if a==0]
                self.assertGreater(len(outside),0)
                self.assertEqual(set(outside),{(15,241,206)})
                self.assertEqual(measured['render.background']['outside_pixels'],len(outside))
        self.assertEqual(evidence[0]['crop_box'],evidence[1]['crop_box'])

    def test_unidentifiable_neck_uses_bounded_fallback_and_records_reason(self):
        person=visual.cutout(keyed_photo())
        framed,evidence=chroma.frame_portrait(person,(800,800))
        self.assertEqual(evidence['method'],'alpha-width-fallback')
        self.assertIn('Sin mínimo',evidence['fallback_reason'])
        self.assertTrue(evidence['ok']);self.assertFalse(evidence['eyes_measured'])
        self.assertEqual(framed.size,(800,800))
        self.assertLess(evidence['scale'],4)

    def test_cyan_edges_and_light_shirt_are_corrected_without_changing_alpha_or_warm_skin(self):
        person=small_head();draw=ImageDraw.Draw(person)
        draw.rectangle((280,650,520,799),fill=(180,225,220,255))  # Cyan white shirt.
        draw.line((360,395,360,418),fill=(80,160,150,180),width=2)  # Mixed edge.
        original_alpha=person.getchannel('A').tobytes();skin=person.getpixel((400,200))
        cleaned,evidence=chroma.despill(person)
        self.assertGreater(evidence['before']['light']['affected_fraction'],.005)
        self.assertGreater(evidence['before']['edge']['affected_pixels'],0)
        self.assertGreater(evidence['corrected_pixels'],0);self.assertTrue(evidence['ok'])
        self.assertEqual(evidence['after']['light']['affected_pixels'],0)
        self.assertEqual(evidence['after']['edge']['affected_pixels'],0)
        self.assertEqual(cleaned.getchannel('A').tobytes(),original_alpha)
        self.assertEqual(cleaned.getpixel((400,200)),skin)
        unchanged,clean=chroma.despill(small_head())
        self.assertEqual(clean['corrected_pixels'],0)
        self.assertEqual(unchanged.tobytes(),small_head().tobytes())

    def test_review_uses_bound_measurements_but_keeps_identity_and_clothing_checks(self):
        raw,rows=visual.portrait(small_head(),'A',with_evidence=True)
        result={'ok':True,'checks':[{'point':n,'ok':True,'reason':'Synthetic'} for n in (1,2,3,7,8)],
            'identity_03':True,'smile_01':True,'clear_glasses':True,'pose_01':True,'body_02':True,'clothing':True,
            'face_height':.4,'eyes_y':.38,'head_top':.09,'reasons':[]}
        def provider(system,message,**kwargs):
            self.assertIn('no rechaces por no poder verificar #0FF1CE',system)
            self.assertNotIn('Ante duda ok=false',system)
            payload=json.loads(message[0]['text'])
            self.assertEqual(payload['render_evidence'],rows)
            return {'text':json.dumps(result)}
        with patch.object(providers,'claude',side_effect=provider):
            self.assertTrue(visual.check({'A':raw},{},{'render_evidence':rows})['ok'])
            for key in ('identity_03','smile_01','clear_glasses','clothing'):
                result[key]=False
                self.assertFalse(visual.check({'A':raw},{},{'render_evidence':rows})['ok'])
                result[key]=True
            result['checks'][-1]['ok']=False  # Text/logo still blocks.
            self.assertFalse(visual.check({'A':raw},{},{'render_evidence':rows})['ok'])
        result['checks'][-1]['ok']=True
        stale=[dict(row,sha256='old-bytes') for row in rows]
        with patch.object(providers,'claude',return_value={'text':json.dumps(result)}):
            self.assertFalse(visual.check({'A':raw},{},{'render_evidence':stale})['ok'])
            bad=[dict(row,ok=False) if row['id']=='render.spill' else row for row in rows]
            self.assertFalse(visual.check({'A':raw},{},{'render_evidence':bad})['ok'])

    def test_opaque_key_becomes_alpha_with_tolerance_despill_and_feather(self):
        source=Image.open(io.BytesIO(keyed_photo()))
        draw=ImageDraw.Draw(source)
        draw.rectangle((0,0,60,255),fill=(10,180,70))  # Near-key background.
        draw.line((75,25,75,250),fill=(60,157,71))  # Mixed key/person edge.
        out=io.BytesIO();source.save(out,format='PNG')
        person=visual.cutout(out.getvalue());alpha=person.getchannel('A')
        self.assertEqual(alpha.getpixel((10,10)),0)
        self.assertEqual(alpha.getpixel((120,120)),255)
        self.assertTrue(0<alpha.getpixel((75,100))<255)
        self.assertEqual(person.getpixel((120,120)),(170,120,85,255))
        r,g,b,_=person.getpixel((75,100));self.assertLessEqual(g,max(r,b))
        self.assertGreater(sum(alpha.histogram()[1:255]),0)

    def test_background_ratio_holes_fragmentation_and_wide_edges_are_rejected(self):
        with self.assertRaisesRegex(ValueError,'agujeros grandes'):visual.cutout(keyed_photo(hole=True))
        for color in (images.CHROMA_COLOR,'#ffffff'):
            raw=io.BytesIO();Image.new('RGB',(256,256),color).save(raw,format='PNG')
            with self.subTest(color=color),self.assertRaisesRegex(ValueError,'máscara fiable'):visual.cutout(raw.getvalue())
        person=visual.cutout(keyed_photo());draw=ImageDraw.Draw(person)
        draw.rectangle((10,30,35,100),fill=(170,120,85,255))
        with self.assertRaisesRegex(ValueError,'fragmentada'):chroma.validate(person)
        person=visual.cutout(keyed_photo());draw=ImageDraw.Draw(person)
        draw.rectangle((75,30,110,240),fill=(170,120,85,150))
        with self.assertRaisesRegex(ValueError,'bordes demasiado difusos'):chroma.validate(person)

    def test_final_assets_keep_dimensions_srgb_grayscale_and_brand_layout(self):
        copy={'lines':['Software that','holds up.'],'highlight':'holds','label':'FOUNDER, PROJECTAPP'}
        package=visual.render({kind:keyed_photo() for kind in ('A','B','banner')},copy)
        self.assertFalse(package['geometry']['errors'])
        self.assertEqual(set(package['masks']),{'A','B','banner'})
        for kind,size,color in [('A',(800,800),(15,241,206)),('B',(800,800),(15,241,206)),('banner',(1584,396),(30,30,43))]:
            with self.subTest(kind=kind),Image.open(io.BytesIO(package['files'][kind])) as image:
                self.assertEqual(image.size,size);self.assertTrue(image.info.get('icc_profile'))
                self.assertEqual(image.getpixel((0,0)),color)
                if kind=='A':self.assertEqual(len(set(image.getpixel((400,400)))),1)
                if kind=='B':self.assertGreater(len(set(image.getpixel((400,400)))),1)
        self.assertTrue(visual.inside(package['geometry']['figure'],visual.MOBILE))
        self.assertFalse(visual.overlaps(package['geometry']['figure'],visual.COVER))


class BannerRecoveryTests(SimpleTestCase):
    def test_invalid_highlight_is_repaired_even_when_existing_lines_are_preserved(self):
        lines=['Your workflow,','built to ship.']
        for highlight in ('','missing','workflow,','SHIP.','built to'):
            previous={'lines':lines,'highlight':highlight,'label':'','evidence':['offer']}
            recovered=perfil_assets.recover_banner({'copy':'\n'.join(lines)},previous)
            expected={'workflow,':'workflow','SHIP.':'ship'}.get(highlight,'built')
            self.assertEqual(recovered['highlight'],expected)
            self.assertEqual(recovered['lines'],lines)
            fit=visual.banner_fit(recovered)
            self.assertTrue(fit['ok'],fit['error'])
            self.assertEqual(fit['input'],{k:recovered[k] for k in ('lines','highlight','label')})
            self.assertEqual(previous['highlight'],highlight)

    def test_normalized_duplicates_choose_unique_word_and_impossible_copy_fails(self):
        fit=visual.banner_fit({'lines':['Ship, ship.','Build it.'],'highlight':'ship','label':''})
        self.assertTrue(fit['ok']);self.assertEqual(fit['input']['highlight'],'build')
        impossible=visual.banner_fit({'lines':['Ship,','ship.'],'highlight':'ship','label':''})
        self.assertFalse(impossible['ok'])
        self.assertIn('exactamente una palabra',impossible['error'])

    def test_punctuation_normalization_paints_exactly_one_complete_word(self):
        with patch.object(ImageDraw.ImageDraw,'text') as text:
            visual.banner(None,{'lines':['Your workflow,','built to ship.'],'highlight':'WORKFLOW','label':''})
        accented=[call.args[1] for call in text.call_args_list if call.kwargs.get('fill')==visual.ACCENT]
        self.assertEqual(accented,['workflow,'])

    def test_section_recovers_phrase_label_and_highlight_without_context_or_writer(self):
        variants=[
            {'copy':'Software that holds up.','label':'FOUNDER, PROJECTAPP'},
            {'copy':'FOUNDER, PROJECTAPP\nSoftware that holds up.'},
            {'copy':'Software that holds up.\nFOUNDER, PROJECTAPP'},
            {'copy':'**Etiqueta:** «FOUNDER, PROJECTAPP»\n**Frase:** «Software that holds up.»'},
            {'copy':'Software that holds up.','steps':['Etiqueta: FOUNDER, PROJECTAPP']},
        ]
        for section in variants:
            with self.subTest(section=section),patch.object(providers,'claude',side_effect=AssertionError('writer forbidden')):
                banner=perfil_assets.recover_banner(dict(section,evidence=['offer']),{})
            self.assertEqual(banner,{'lines':['Software that','holds up.'],'highlight':'holds',
                'label':'FOUNDER, PROJECTAPP','evidence':['offer']})

    def test_existing_checkpoint_is_retained_and_missing_label_is_never_invented(self):
        previous={'lines':['Build useful','software.'],'highlight':'useful','label':'PRODUCT ENGINEER','evidence':['offer']}
        self.assertEqual(perfil_assets.recover_banner({'copy':''},previous),previous)
        recovered=perfil_assets.recover_banner({'copy':'Software that holds up.','evidence':['offer']},previous)
        self.assertEqual(recovered['label'],'');self.assertEqual(recovered['lines'],['Software that','holds up.'])


class OpaqueImageContractTests(SimpleTestCase):
    def test_unsupported_and_unknown_models_omit_background_and_reserve_final_payload(self):
        output=keyed_photo(size=1024)
        for model in ('gpt-image-2','unlisted-model'):
            requests=[]
            def handler(request):
                requests.append(request)
                self.assertNotIn(b'name="background"',request.content)
                self.assertIn(b'name="output_format"\r\n\r\npng',request.content)
                self.assertEqual(request.content.count(b'name="image[]"'),3)
                self.assertIn(b'#00B140',request.content)
                self.assertIn(b'opaque',request.content)
                return httpx.Response(200,json={'data':[{'b64_json':base64.b64encode(output).decode()}],
                    'usage':{'input_tokens_details':{'text_tokens':100,'image_tokens':200},'output_tokens':30}})
            with self.subTest(model=model),patch.object(images,'EDIT_MODEL',model), \
                 patch.object(images,'TRANSPORT',httpx.MockTransport(handler)),patch.object(images,'live',return_value='fake-key'), \
                 patch.object(providers,'reserve',return_value='fake-ledger') as reserve,patch.object(providers,'settle'):
                prompt=visual.prompt('banner',[],adjustment='x'*12000)
                result=images.ImageConnector().edit_profile({role:output for role in ('01','02','03')},prompt,'opaque')
                self.assertEqual(result,output);self.assertEqual(len(requests),1)
                actual=requests[0].content.split(b'name="prompt"\r\n\r\n',1)[1].split(b'\r\n--',1)[0]
                self.assertEqual(actual,prompt.encode());self.assertLessEqual(len(prompt),12000)
                metadata=reserve.call_args.kwargs['metadata']
                self.assertEqual(metadata['estimate']['text_tokens'],len(actual)+32)
                self.assertEqual(metadata['estimate']['image_tokens'],3*(65+129*4))
                self.assertEqual(metadata['estimate']['output_tokens'],1056)
                self.assertEqual(metadata['request']['model'],model)
                self.assertNotIn('background',metadata['request'])

    def test_error_body_is_bounded_and_sensitive_echoes_are_removed(self):
        prompt='private reference notes';key='sk-private-example'
        response=httpx.Response(400,json={'error':{'message':f'Invalid input: {prompt} {key} person@example.com https://private.example/photo 1234567890 "Private Name"',
            'param':'background','code':'invalid_value','extra':'do not persist'}})
        error=images.openai_error(response,prompt,key)
        self.assertEqual(set(error),{'message','param','code'})
        for private in (prompt,key,'person@example.com','https://private.example','1234567890','Private Name'):
            self.assertNotIn(private,error['message'])
        self.assertLessEqual(len(error['message']),600)
        quoted=httpx.Response(400,json={'error':{'message':"Unsupported 'transparent'; input 'Private Name'"}})
        message=images.openai_error(quoted,'','')['message']
        self.assertIn("'transparent'",message);self.assertNotIn('Private Name',message)
        for body in ('not json','[]','{"error":null}'):
            self.assertEqual(images.openai_error(httpx.Response(400,text=body),'',''),{})
