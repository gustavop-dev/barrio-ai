"""EST-01–05/GAL-08/TUR-18. Synthetic inputs, injected providers and connectors only.

CI runs this suite. No original reference photographs or private course text are fixtures.
"""
import base64
import io
import json
import os
import uuid
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import patch
from zoneinfo import ZoneInfo
import httpx
from PIL import Image, ImageDraw
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from django.utils import timezone
from knowledge import providers
from team_backend import capturas, connectors_images, imagenes, orquestacion, perfil, perfil_contenido as content, perfil_galeria as gallery, perfil_visual as visual
from team_backend.models import Capture, CycleLedger, EditorialPiece, GalleryPhoto, Job, PieceImage, ProfileProposal, ProfileSchedule, TeamQuestion, UsageEntry
from team_backend.research import ResearchResult
from team_backend.tests.test_capturas import MediaMixin
from team_backend.tests.test_operador import OperatorBase


def synthetic(alpha=True):
    image=Image.new('RGBA' if alpha else 'RGB',(800,800),(0,0,0,0) if alpha else '#0FF1CE')
    ImageDraw.Draw(image).rectangle((240,65,560,799),fill=(170,120,85,255) if alpha else (170,120,85))
    output=io.BytesIO();image.save(output,format='PNG');return output.getvalue()


def library(mode='full'):
    units=list(dict.fromkeys(content.POSITIONING_PROFILE_UNITS+content.PROFILE_COPY_UNITS+content.PROFILE_MONTHLY_UNITS+content.PROFILE_VISUAL_UNITS))
    return {'units':[{'unit_id':uid,'original':{'title':'Synthetic: audience usefulness; never invent facts'},'sha256':'synthetic'} for uid in units],'missing':[]}


def context(ids=None):
    return {'library':library(),'public_facts':[{'key':'offer','fact':'Product engineer: useful software for product teams','version':1}],
        'private_guidance':[],'snapshot':{'sections':{},'evidence':[]},'web':{'sources':[]},'section_ids':ids or list(content.SECTIONS)}


def draft(ctx):
    rows=[]
    for sid in ctx['section_ids']:
        rows.append({'id':sid,'action':'change','copy':'Useful software for product teams' if sid not in ('photo','banner') else '',
            'audience':'Product teams','benefit':'Make product decisions easier','reason':'Lead with utility',
            'citations':[{'unit_id':content.REQUIRED_CITATIONS.get(sid,['LI-02-V010-K03'])[0],'reason':'Lead with utility'}],
            'evidence':['offer'],'steps':['Open this section and paste the copy.'],'missing':[],'limit':0,'limit_source':''})
    return {'sections':rows,'banner':{'lines':['Build useful','software.'],'highlight':'useful','label':'PRODUCT ENGINEER','evidence':['offer']}}


def verdict(ctx):
    return {'sections':[{'id':r['id'],'ok':True,'reason':'Synthetic verified facts','missing_valid':True} for r in ctx['draft']['sections']],
            'banner_ok':True,'banner_reason':'Synthetic offer supported','reference_conflicts':[]}


class FakeProfileImages:
    def __init__(self):self.calls=[]
    def edit_profile(self,refs,prompt,rid):
        self.calls.append((set(refs),prompt,rid));return synthetic()


def vision(images,refs,ctx):
    return {'ok':True,'checks':[{'point':n,'ok':True,'reason':'Fake'} for n in range(1,9)],
        'identity_03':True,'smile_01':True,'clear_glasses':True,
        'sha256':[imagenes.sha(raw) for raw in images.values()]}


class ProfileContentTests(SimpleTestCase):
    def test_edit_contract_uses_multiple_role_named_images_and_transparency_only_with_mock_transport(self):
        output=io.BytesIO()
        Image.open(io.BytesIO(synthetic())).resize((1024,1024)).save(output,format='PNG')
        calls=[]
        def handler(request):
            calls.append(request)
            self.assertEqual(str(request.url),connectors_images.EDIT_URL)
            self.assertEqual(request.content.count(b'name="image[]"'),3)
            for role in ('01','02','03'):self.assertIn(('filename="'+role+'.png"').encode(),request.content)
            self.assertIn(b'transparent',request.content)
            self.assertIn(connectors_images.EDIT_MODEL.encode(),request.content)
            return httpx.Response(200,json={'data':[{'b64_json':base64.b64encode(output.getvalue()).decode()}],
                'usage':{'input_tokens_details':{'text_tokens':100,'image_tokens':200},'output_tokens':30}})
        with patch.object(connectors_images,'TRANSPORT',httpx.MockTransport(handler)), \
                patch.object(connectors_images,'live',return_value='fake-key'), \
                patch.object(providers,'reserve',return_value='fake-ledger') as reserve,patch.object(providers,'settle') as settle:
            result=connectors_images.ImageConnector().edit_profile({role:synthetic() for role in ('01','02','03')},'Only person edits','fake-request')
        self.assertEqual(result,output.getvalue());self.assertEqual(len(calls),1)
        self.assertEqual(reserve.call_args.args,('openai','profile-image-edit',Decimal('2')))
        self.assertEqual(settle.call_args.args[1],'complete')

    def test_vision_requires_all_eight_points_and_identity_despite_positive_overall_verdict(self):
        result={'ok':True,'checks':[{'point':n,'ok':True,'reason':'Synthetic'} for n in range(1,9)],
            'identity_03':True,'smile_01':True,'clear_glasses':True,'pose_01':True,'body_02':True,'clothing':True,
            'face_height':.57,'eyes_y':.3,'head_top':.08,'reasons':[]}
        images={'B':synthetic(),'banner':synthetic()};refs={role:synthetic() for role in ('01','02','03')}
        for changed in ({'identity_03':False},{'smile_01':False},{'clear_glasses':False},{'checks':result['checks'][:-1]}):
            with patch.object(providers,'claude',return_value={'text':json.dumps(dict(result,**changed))}):
                self.assertFalse(visual.check(images,refs,{'option':'B'})['ok'])

    def test_missing_or_unknown_course_citations_block_even_with_positive_reviewer(self):
        for citations in ([],[{'unit_id':'LI-07-V001-K01','reason':'invented'}],
                          [{'unit_id':'LI-02-V011-K02','reason':'irrelevant to headline'}]):
            ctx=context(['headline']);data=draft(ctx);data['sections'][0]['citations']=citations
            rows,_=content.validate(data,ctx,verdict(dict(ctx,draft=data)))
            self.assertEqual((rows[0]['readiness'],rows[0]['copy']),('blocked',''))

    def test_unknown_evidence_and_unverified_limits_do_not_become_ready_copy(self):
        ctx=context(['headline']);data=draft(ctx);data['sections'][0].update(evidence=['invented'],limit=220,limit_source='invented')
        rows,_=content.validate(data,ctx,verdict(dict(ctx,draft=data)))
        self.assertEqual(rows[0]['readiness'],'blocked');self.assertEqual(rows[0]['limit'],0)

    def test_speaker_cannot_be_inferred_from_a_microphone_or_generic_offer(self):
        ctx=context();data=draft(ctx);data['banner']['label']='SPEAKER'
        rows,banner=content.validate(data,ctx,verdict(dict(ctx,draft=data)))
        self.assertEqual(banner,{});self.assertEqual(next(r for r in rows if r['id']=='banner')['readiness'],'blocked')

    def test_missing_fact_keeps_only_its_section_pending_and_known_key_is_not_asked(self):
        ctx=context(['headline','experience']);data=draft(ctx)
        data['sections'][1].update(action='missing',copy='',missing=[{'key':'perfil.experience.start_date','question':'¿En qué fecha empezaste ese cargo?','purpose':'Fechar experiencia.'}])
        rows,_=content.validate(data,ctx,verdict(dict(ctx,draft=data)))
        self.assertEqual(rows[0]['readiness'],'ready');self.assertEqual(rows[1]['readiness'],'blocked')
        self.assertEqual(len(rows[1]['missing']),1)
        ctx['public_facts'].append({'key':'perfil.experience.start_date','fact':'2020','version':1})
        rows,_=content.validate(data,ctx,verdict(dict(ctx,draft=data)))
        self.assertEqual(rows[1]['missing'],[])

    def test_reviewer_rejection_hides_copy_and_technical_questions(self):
        ctx=context(['about']);data=draft(ctx);data['sections'][0]['missing']=[{'key':'perfil.library','question':'¿Cuál es el curso?','purpose':'Technical'}]
        check=verdict(dict(ctx,draft=data));check['sections'][0].update(ok=False,missing_valid=False,reason='Unsupported')
        rows,_=content.validate(data,ctx,check)
        self.assertEqual((rows[0]['copy'],rows[0]['missing']),('',[]))

    def test_exact_size_colors_grayscale_and_mobile_geometry(self):
        package=visual.render({k:synthetic() for k in ('A','B','banner')},draft(context())['banner'])
        self.assertEqual(set(package['files']),{'A','B','banner','mobile_A','mobile_B','desktop_A','desktop_B'})
        for kind,size in [('A',(800,800)),('B',(800,800)),('banner',(1584,396))]:
            with Image.open(io.BytesIO(package['files'][kind])) as image:
                self.assertEqual(image.size,size);self.assertTrue(image.info['icc_profile'])
                self.assertEqual(image.getpixel((0,0)),(30,30,43) if kind=='banner' else (15,241,206))
                if kind=='A':self.assertEqual(len(set(image.getpixel((400,400)))),1)
                if kind=='B':self.assertGreater(len(set(image.getpixel((400,400)))),1)
        self.assertTrue(visual.inside(package['geometry']['figure'],visual.MOBILE))
        self.assertFalse(visual.overlaps(package['geometry']['figure'],visual.COVER))
        self.assertTrue(all(visual.inside(box,visual.SAFE) for box in package['geometry']['text_boxes']))

    def test_no_alpha_and_overflow_fail_closed_without_font_shrink(self):
        with self.assertRaisesRegex(ValueError,'máscara'):visual.portrait(synthetic(False),'A')
        with self.assertRaisesRegex(ValueError,'Acorta'):
            visual.banner(None,{'lines':['This is a very long sentence that cannot possibly fit','software.'],'highlight':'software.', 'label':'ENGINEER'})

    def test_calendar_months_preserve_anchor_even_at_end_of_month(self):
        self.assertEqual(perfil.add_months(date(2026,8,31),6),date(2027,2,28))
        self.assertEqual(perfil.add_months(date(2026,8,31),12),date(2027,8,31))


class ProfileCycleTests(MediaMixin,OperatorBase):
    def setUp(self):
        super().setUp();self.use_media()
        for target in ('knowledge.providers.claude','httpx.Client.send','team_backend.connectors.get_connector'):
            mock=patch(target,side_effect=AssertionError('No real provider or LinkedIn in profile tests'))
            mock.start();self.addCleanup(mock.stop)
        notices=patch('team_backend.notificaciones.avisar');self.notice=notices.start();self.addCleanup(notices.stop)
        values=patch('team_backend.perfil.facts',side_effect=lambda mode:dict(context(list(content.MONTHLY) if mode=='monthly' else None),mode=mode,brand_version=content.BRAND_VERSION))
        values.start();self.addCleanup(values.stop)

    def references(self):
        for role in ('01','02','03'):
            photo=GalleryPhoto(created_by=self.gustavo,mime='image/png',size_bytes=len(synthetic()),note='Synthetic role '+role)
            photo.image.save('reference.png',ContentFile(synthetic()),save=False);photo.save()
            gallery.update(self.gustavo,photo,{'category':'perfil','profile_role':role})

    def proposal(self,mode='full'):
        return perfil.queue(self.gustavo,{'capture':str(uuid.uuid4())},mode=mode)

    def run_proposal(self,proposal,**kwargs):
        job=Job.objects.get(kind='prepare_profile',params__proposal=str(proposal.id),params__version=proposal.version)
        options={'library':library,'positioning':lambda ctx:{'audience':'Teams','benefit':'Useful software','direction':'Audience first',
            'citations':[{'unit_id':'LI-01-M006-K02','reason':'Utility'}],'evidence':['offer']},'drafter':draft,'reviewer':verdict,
            'reader':lambda:{'sections':{},'evidence':[],'at':timezone.now().isoformat(),'limitations':[]},
            'researcher':lambda req:ResearchResult(question=req.public_question,status='unavailable',researched_at=timezone.now().isoformat()),
            'image_client':FakeProfileImages(),'image_checker':vision}
        options.update(kwargs);return perfil.run(job,**options)

    def test_full_cycle_has_all_sections_assets_citations_and_no_linkedin_write(self):
        self.references();proposal=self.proposal();client=FakeProfileImages()
        result=self.run_proposal(proposal,image_client=client)
        self.assertEqual(result.state,'ready',result.findings)
        self.assertEqual({r['id'] for r in result.sections},set(content.SECTIONS))
        self.assertEqual(result.assets.count(),7);self.assertEqual(result.photo_choice,'')
        self.assertEqual([c[0] for c in client.calls],[{'01','03'},{'01','03'},{'01','02','03'}])
        text=perfil.markdown(result)
        self.assertIn('LI-02-M015-K03',text);self.assertIn(content.MICROPHONE_NOTE,text)
        ledger=CycleLedger.objects.get(pk=result.cycle_id)
        self.assertEqual(ledger.limits['cost_cap_usd'],10)
        self.assertFalse(any(c['edge'].startswith('ejecutar') for c in ledger.progress_ledger['calls'].values()))
        self.run_proposal(result,image_client=client)
        self.assertEqual(len(client.calls),3)

    def test_monthly_never_edits_people_and_full_request_deduplicates(self):
        client=FakeProfileImages();proposal=self.proposal('monthly')
        result=self.run_proposal(proposal,image_client=client)
        self.assertEqual({r['id'] for r in result.sections},set(content.MONTHLY));self.assertEqual(client.calls,[])
        capture=Capture.objects.create(created_by=self.gustavo,note='hazme la propuesta del perfil')
        self.assertEqual(capturas._destination(capture)[0],'perfil')
        first=perfil.queue(self.gustavo,{'capture':str(capture.id)})
        self.assertEqual(perfil.queue(self.gustavo,{'capture':str(capture.id)}).pk,first.pk)
        self.assertEqual(Job.objects.filter(params__proposal=str(first.id)).count(),1)
        capture.note='No hazme la propuesta del perfil'
        self.assertEqual(capturas._destination(capture)[0],'perfil_aclaracion')

    def test_monthly_no_changes_is_informative_and_activity_artifacts_do_not_schedule_posts(self):
        def unchanged(ctx):
            data=draft(ctx)
            for row in data['sections']:row.update(action='keep',copy='')
            return data
        unchanged_proposal=self.run_proposal(self.proposal('monthly'),drafter=unchanged)
        self.assertTrue(perfil.no_changes(unchanged_proposal))
        self.assertEqual(perfil.cards(self.gustavo,lambda *a,**kw:kw),[])
        self.assertEqual(self.notice.call_args.args[0],'profile_reviewed')
        proposal=self.run_proposal(self.proposal('monthly'))
        self.assertEqual(perfil.editorial_guidance(),[])
        before=EditorialPiece.objects.count()
        response=self.human.post(f'/api/v1/perfil/{proposal.id}/decision',
            {'revision':proposal.revision,'section':'activity','action':'accept'},format='json')
        self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(perfil.editorial_guidance()[0]['proposal'],str(proposal.id))
        self.assertEqual(EditorialPiece.objects.count(),before)

    def test_empty_gallery_and_library_remain_partial_without_spurious_questions(self):
        result=self.run_proposal(self.proposal(),library=lambda mode:{'units':[],'missing':content.PROFILE_COPY_UNITS})
        self.assertEqual(result.state,'partial');self.assertFalse(TeamQuestion.objects.exists())
        self.assertEqual(result.assets.count(),0)

    def test_missing_fact_asked_once_across_sections_and_known_fact_not_invented(self):
        def missing(ctx):
            data=draft(ctx)
            for row in data['sections']:
                if row['id'] in ('experience','education'):
                    row.update(action='missing',copy='',missing=[{'key':'perfil.start_date','question':'¿Cuál fue la fecha de inicio?','purpose':'Fechar el puesto.'}])
            return data
        result=self.run_proposal(self.proposal(),drafter=missing)
        self.assertEqual(TeamQuestion.objects.filter(memory_key='perfil.start_date').count(),1)
        self.assertEqual(next(s for s in result.sections if s['id']=='headline')['readiness'],'ready')

    def test_vision_identity_failure_blocks_all_assets(self):
        self.references();result=self.run_proposal(self.proposal(),image_checker=lambda *a:dict(vision(*a),ok=False))
        self.assertEqual(result.state,'partial');self.assertEqual(result.assets.count(),0)
        self.assertTrue(all(s['readiness']=='blocked' for s in result.sections if s['id'] in ('photo','banner')))

    def test_schedule_and_on_demand_do_not_reset_calendar_anchor(self):
        zone=ZoneInfo('America/Bogota')
        with patch.dict(os.environ,{'PROFILE_ENABLED':'true','PROFILE_OWNER_USERNAME':self.gustavo.username}):
            self.assertEqual(perfil.schedule(self.gustavo,datetime(2026,8,31,9,tzinfo=zone)),1)
            self.assertEqual(perfil.schedule(self.gustavo,datetime(2026,8,31,10,tzinfo=zone)),0)
            for p in ProfileProposal.objects.all():p.state='ready';p.save()
            self.assertEqual(perfil.schedule(self.gustavo,datetime(2026,9,1,9,tzinfo=zone)),1)
            self.proposal()
            self.assertEqual(perfil.schedule(self.gustavo,datetime(2027,2,28,9,tzinfo=zone)),1)
        self.assertEqual(ProfileSchedule.objects.get(owner=self.gustavo).anchor,date(2026,8,31))

    def test_category_upload_scoped_consent_and_sticky_editorial_exclusion(self):
        upload=SimpleUploadedFile('synthetic.png',synthetic(False),content_type='image/png')
        response=self.human.post('/api/v1/galeria',{'fotos':upload,'category':'perfil'},format='multipart')
        self.assertEqual(response.status_code,201,response.data)
        photo=GalleryPhoto.objects.get(pk=response.data[0]['id'])
        self.assertTrue(photo.profile_edit);self.assertEqual(photo.category,'perfil')
        again=self.human.post('/api/v1/galeria',{'fotos':SimpleUploadedFile('renamed.png',synthetic(False),content_type='image/png'),'category':'perfil'},format='multipart')
        self.assertEqual(again.data[0]['id'],str(photo.id))
        self.assertEqual(GalleryPhoto.objects.count(),1)
        self.assertNotIn(str(photo.id),[r['id'] for r in imagenes.candidates([{'photos':[{'id':str(photo.id)}]}])])
        with self.assertRaisesRegex(ValueError,'excluido'):
            imagenes._photo(None,photo,{},0,None,[],[])
        refs=gallery.references(self.gustavo);gallery.update(self.gustavo,photo,{'profile_edit':False})
        self.assertTrue(gallery.stale(refs,self.gustavo))

    def test_a_preexisting_post_derivative_stays_excluded_after_source_changes_and_deletion(self):
        photo=GalleryPhoto(created_by=self.gustavo,mime='image/png',size_bytes=len(synthetic()))
        photo.image.save('synthetic.png',ContentFile(synthetic()),save=False);photo.save()
        piece=EditorialPiece.objects.create(account=self.account,slot_date=date(2026,11,9),scheduled_for=timezone.now())
        row=PieceImage.objects.create(piece=piece,position=1,source_photo=photo,kind='foto',image=photo.image.name,
            width=800,height=800,sha256=imagenes.sha(synthetic()),alt='Synthetic blocks')
        gallery.update(self.gustavo,photo,{'category':'perfil'})
        gallery.update(self.gustavo,photo,{'category':'posts'})
        row.refresh_from_db();self.assertTrue(row.profile_exclusive)
        photo.delete();row.refresh_from_db()
        self.assertIsNone(row.source_photo_id);self.assertTrue(row.profile_exclusive)

    def test_only_an_exact_authorized_reread_marks_headline_checked(self):
        proposal=self.run_proposal(self.proposal())
        path=f'/api/v1/perfil/{proposal.id}/decision'
        accepted=self.human.post(path,{'revision':1,'section':'headline','action':'accept'},format='json').data
        applied=self.human.post(path,{'revision':accepted['revision'],'section':'headline','action':'applied'},format='json').data
        headline=next(s for s in applied['sections'] if s['id']=='headline')
        reading={'sections':{'headline':{'text':headline['applied_text'],'source':'fake:own-profile','at':timezone.now().isoformat()}},
            'evidence':['fake:own-profile'],'at':timezone.now().isoformat(),'limitations':[]}
        with patch('team_backend.perfil.read_profile',return_value=reading):
            result=self.human.post(path,{'revision':applied['revision'],'section':'headline','action':'verify'},format='json')
        self.assertEqual(result.status_code,200,result.data)
        self.assertEqual(next(s for s in result.data['sections'] if s['id']=='headline')['application'],'checked')

    def test_mismatched_reread_keeps_ledger_and_allows_a_later_explicit_check(self):
        proposal=self.run_proposal(self.proposal())
        path=f'/api/v1/perfil/{proposal.id}/decision'
        first=self.human.post(path,{'revision':1,'section':'headline','action':'accept'},format='json').data
        applied=self.human.post(path,{'revision':first['revision'],'section':'headline','action':'applied'},format='json').data
        reading={'sections':{},'evidence':[],'at':timezone.now().isoformat(),'limitations':['Not available']}
        with patch('team_backend.perfil.read_profile',return_value=reading):
            result=self.human.post(path,{'revision':applied['revision'],'section':'headline','action':'verify'},format='json')
        self.assertEqual(result.status_code,409)
        proposal.refresh_from_db();self.assertGreater(proposal.revision,applied['revision'])
        calls=CycleLedger.objects.get(pk=proposal.cycle_id).progress_ledger['calls']
        self.assertTrue(any(k.startswith('verify:') and v['state']=='answered' for k,v in calls.items()))
        headline=next(s for s in proposal.sections if s['id']=='headline')
        self.assertEqual(headline['application'],'applied')
        reading['sections']['headline']={'text':headline['applied_text'],'source':'fake:own-profile','at':reading['at']}
        with patch('team_backend.perfil.read_profile',return_value=reading):
            result=self.human.post(path,{'revision':proposal.revision,'section':'headline','action':'verify'},format='json')
        self.assertEqual(result.status_code,200,result.data)

    def test_partial_adjustment_reuses_images_and_cycle_budget(self):
        self.references();client=FakeProfileImages();proposal=self.run_proposal(self.proposal(),image_client=client)
        cycle_id=proposal.cycle_id
        result=self.human.post(f'/api/v1/perfil/{proposal.id}/decision',
            {'revision':proposal.revision,'section':'headline','action':'adjust','note':'Shorten only the headline.'},format='json')
        self.assertEqual(result.status_code,200,result.data)
        proposal.refresh_from_db();self.assertEqual(proposal.context['affected'],['headline'])
        result=self.run_proposal(proposal,image_client=client)
        self.assertEqual(result.cycle_id,cycle_id);self.assertEqual(len(client.calls),3)
        self.assertEqual(result.assets.filter(version=2).count(),7)
        self.assertTrue(all(s['version']==2 for s in result.sections))

    def test_visual_adjustment_changes_effective_prompt_and_reopens_both_visual_decisions(self):
        self.references();client=FakeProfileImages();proposal=self.run_proposal(self.proposal(),image_client=client)
        response=self.human.post(f'/api/v1/perfil/{proposal.id}/decision',
            {'revision':proposal.revision,'section':'photo','action':'adjust','note':'Keep more shoulder room within the specified face geometry.'},format='json')
        self.assertEqual(response.status_code,200,response.data)
        proposal.refresh_from_db();self.assertEqual(set(proposal.context['affected']),{'photo','banner'})
        result=self.run_proposal(proposal,image_client=client)
        self.assertEqual(len(client.calls),6)
        self.assertTrue(all('Keep more shoulder room' in call[1] for call in client.calls[3:]))
        self.assertEqual(result.photo_choice,'')
        self.assertTrue(all(row['decision']=='pending' for row in result.sections if row['id'] in ('photo','banner')))

    def test_manual_apply_is_not_checked_and_stale_decisions_are_rejected(self):
        proposal=self.run_proposal(self.proposal('monthly'))
        path=f'/api/v1/perfil/{proposal.id}/decision'
        response=self.human.post(path,{'revision':1,'section':'featured','action':'accept'},format='json')
        self.assertEqual(response.status_code,200,response.data)
        applied={'revision':response.data['revision'],'section':'featured','action':'applied'}
        response=self.human.post(path,applied,format='json')
        self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(next(s for s in response.data['sections'] if s['id']=='featured')['application'],'applied')
        self.assertEqual(self.human.post(path,applied,format='json').data['revision'],response.data['revision'])
        self.assertEqual(self.human.post(path,dict(applied,action='verify',revision=response.data['revision']),format='json').status_code,409)
        self.assertEqual(self.human.post(path,dict(applied,action='decline',note='No'),format='json').status_code,409)
        self.assertEqual(self.api.get(f'/api/v1/perfil/{proposal.id}').status_code,404)

    def test_postponed_profile_stays_accessible_without_counting_as_pending(self):
        proposal=self.run_proposal(self.proposal('monthly'))
        response=self.human.post(f'/api/v1/perfil/{proposal.id}/decision',{'revision':proposal.revision,'action':'later'},format='json')
        self.assertEqual(response.status_code,200,response.data)
        from team_backend.rediseno_views import _card
        self.assertEqual(perfil.cards(self.gustavo,_card),[])
        later=perfil.cards(self.gustavo,_card,postponed=True)
        self.assertEqual(later[0]['profile_id'],str(proposal.id));self.assertEqual(later[0]['state_override'],'pospuesta')

    def test_revoked_references_block_pending_downloads_and_selection(self):
        self.references();proposal=self.run_proposal(self.proposal())
        asset=proposal.assets.get(kind='A');url=f'/api/v1/perfil/{proposal.id}/assets/{asset.id}'
        self.assertEqual(self.human.get(url).status_code,200)
        photo=GalleryPhoto.objects.get(profile_role='03');gallery.update(self.gustavo,photo,{'note':'Changed instruction'})
        self.assertEqual(self.human.get(url).status_code,409)
        self.assertEqual(self.human.post(f'/api/v1/perfil/{proposal.id}/decision',{'revision':1,'section':'photo','action':'choose_A'},format='json').status_code,409)

    def test_download_ticket_is_one_use_specific_and_no_device_token_in_url(self):
        from rest_framework.test import APIClient
        proposal=self.run_proposal(self.proposal('monthly'))
        ticket=self.human.post(f'/api/v1/perfil/{proposal.id}/descarga',{},format='json')
        self.assertEqual(ticket.status_code,200)
        anon=APIClient();self.assertEqual(anon.get(ticket.data['url']).status_code,200)
        self.assertEqual(anon.get(ticket.data['url']).status_code,404)
        self.assertIn(anon.get(f'/api/v1/perfil/{proposal.id}/documento').status_code,(401,403))

    def test_aggregate_cap_keeps_uncertain_reservations_and_never_pays_twice(self):
        with patch.dict(os.environ,{'OPENAI_LIMIT_USD':'100'}):
            run=orquestacion.Runtime.open('perfil_periodico','cap-test',self.gustavo)
            UsageEntry.objects.create(id=uuid.uuid4(),created_at=timezone.now(),provider='anthropic',purpose='profile-copy',status='uncertain',
                reserved_usd=Decimal('9'),usage={'cycle_id':str(run.id)})
            request={'proposal':'fake','kind':'A','references':[],'instruction':'Synthetic'}
            def paid():providers.reserve('openai','profile-image-edit',Decimal('2'));return synthetic()
            with run.session(),self.assertRaisesRegex(orquestacion.CycleStopped,'cost_cap'):
                run.call('perfil_editar_persona',request,paid,key='cap')
            self.assertEqual(orquestacion.amount(UsageEntry.objects.filter(usage__cycle_id=str(run.id))),Decimal('9'))
            self.assertEqual(CycleLedger.objects.get(pk=run.id).stop_reason,'cost_cap')

    def test_capture_withdrawal_cancels_only_its_own_trigger(self):
        capture=Capture.objects.create(created_by=self.gustavo,note='hazme la propuesta del perfil')
        proposal=perfil.queue(self.gustavo,{'capture':str(capture.id)})
        capture.routed_to={'kind':'perfil','proposal':str(proposal.id)};capture.save()
        perfil.withdraw_capture(capture);proposal.refresh_from_db();self.assertEqual(proposal.state,'cancelled')
        capture2=Capture.objects.create(created_by=self.gustavo,note='hazme la propuesta del perfil')
        scheduled=perfil.queue(self.gustavo,{'scheduled':'full','period':'2026-11-01'},key='period')
        joined=perfil.queue(self.gustavo,{'capture':str(capture2.id)})
        self.assertEqual(scheduled.pk,joined.pk)
        capture2.routed_to={'kind':'perfil','proposal':str(joined.id)};capture2.save()
        perfil.withdraw_capture(capture2);joined.refresh_from_db();self.assertEqual(joined.state,'queued')
