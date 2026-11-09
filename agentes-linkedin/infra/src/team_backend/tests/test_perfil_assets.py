"""Offline regression scenarios: injected review/images/vision; never real providers."""
import copy
import io
import os
import uuid
import httpx
from decimal import Decimal
from unittest.mock import patch
from django.core.management import call_command
from django.test import SimpleTestCase
from django.utils import timezone
from PIL import Image
from knowledge import providers
from team_backend import connectors_images as images, orquestacion, perfil, perfil_assets, perfil_visual as visual, preguntas
from team_backend.models import CycleLedger, Job, ProfileProposal, TeamQuestion, UsageEntry
from team_backend.tests.test_perfil import ProfileBase, FakeProfileImages, brand_draft, brand_reviewer, vision, synthetic
from team_backend.tests.test_perfil_chroma import keyed_photo


def preview(size):
    out=io.BytesIO();Image.new('RGB',size).save(out,format='PNG')
    return images.thumbnail(out.getvalue())


class ReservationEstimateTests(SimpleTestCase):
    def test_dimensions_count_prompt_quality_and_actual_thumbnail_drive_estimate(self):
        large=preview((4000,2000));small=preview((256,256))
        amount,metadata=images.edit_reservation([large,small],'Hola, identidad 🙂','1024x1024','medium')
        estimate=metadata['estimate']
        self.assertEqual(estimate['dimensions'],[[1024,512],[256,256]])
        self.assertEqual(estimate['image_tokens'],65+129*2+65+129)
        expected=(Decimal(estimate['text_tokens'])*5+Decimal(estimate['image_tokens'])*10+Decimal(1056)*40)/1_000_000*Decimal('1.5')
        self.assertGreaterEqual(amount,expected);self.assertLess(amount,expected+Decimal('0.000001'))
        self.assertGreater(images.edit_reservation([large,small,large],'Hola, identidad 🙂','1024x1024','medium')[0],amount)
        self.assertGreater(images.edit_reservation([large,small],'x'*12000,'1024x1024','medium')[0],amount)
        self.assertGreater(images.edit_reservation([large,small],'Hola','1024x1536','high')[0],amount)
        self.assertEqual(images.edit_reservation([small],'','1024x1024','low')[0],images.EDIT_MINIMUM)


class ProfileAssetsTests(ProfileBase):
    def blocked_proposal(self):
        self.references()
        class Denied(FakeProfileImages):
            def edit_profile(self,*args):raise ValueError('Límite local de openai alcanzado')
        return self.run_proposal(self.proposal(),drafter=brand_draft,reviewer=brand_reviewer,image_client=Denied())

    def run_assets(self,proposal,**kwargs):
        job=perfil_assets.queue(self.gustavo,proposal.id)
        options={'reviewer':brand_reviewer,'image_client':FakeProfileImages(),'image_checker':vision};options.update(kwargs)
        result=perfil_assets.run(job,**options)
        Job.objects.filter(pk=job.pk).update(state='complete')
        return result

    def test_only_visual_review_preserves_copy_decisions_version_and_original_budget(self):
        proposal=self.blocked_proposal();old_cycle=proposal.cycle
        for row in proposal.sections:
            if row['id']=='headline':row.update(decision='accepted',application='applied',applied_text=row['copy'])
        proposal.save();before=copy.deepcopy(proposal.sections);reviewed=[];client=FakeProfileImages()
        # Emulate #88's rejected banner: the raw copy lives only in the private checkpoint.
        proposal.context['banner']={}
        next(s for s in proposal.sections if s['id']=='banner')['copy']=''
        proposal.save()
        old_cycle.graph_hash='pre-deploy';old_cycle.save(update_fields=['graph_hash'])
        def review(ctx):
            reviewed.append(ctx)
            self.assertEqual(ctx['section_ids'],['photo','banner'])
            self.assertTrue(ctx['render_evidence'][0]['ok'])
            return brand_reviewer(ctx)
        with patch('team_backend.perfil_contenido.draft',side_effect=AssertionError('copy forbidden')), \
             patch('team_backend.perfil_contenido.positioning',side_effect=AssertionError('positioning forbidden')), \
             patch('team_backend.research.research',side_effect=AssertionError('web forbidden')):
            result=self.run_assets(proposal,reviewer=review,image_client=client)
        self.assertEqual(result.id,proposal.id);self.assertEqual(result.version,1);self.assertEqual(result.cycle_id,old_cycle.id)
        self.assertEqual(result.state,'ready',result.findings);self.assertEqual(len(reviewed),1)
        self.assertEqual([s for s in result.sections if s['id'] not in ('photo','banner')],
                         [s for s in before if s['id'] not in ('photo','banner')])
        child=CycleLedger.objects.get(cycle='perfil_assets')
        self.assertEqual(child.budget_bucket,old_cycle.budget_bucket)
        self.assertEqual(len(client.calls),3)
        self.assertEqual(set(result.assets.values_list('kind',flat=True)),perfil.ASSET_KINDS)
        again=perfil_assets.queue(self.gustavo,result.id)
        self.assertEqual(Job.objects.filter(kind='prepare_profile_assets').count(),1)
        perfil_assets.run(again,reviewer=review,image_client=client,image_checker=vision)
        self.assertEqual(len(client.calls),3);self.assertEqual(len(reviewed),1)

    def test_each_edit_is_checked_and_saved_before_next_and_failures_are_independent(self):
        proposal=self.blocked_proposal();events=[]
        class Images(FakeProfileImages):
            def edit_profile(inner,refs,prompt,rid):
                kind=rid.rsplit(':',1)[1];events.append('edit:'+kind)
                if kind=='B':
                    self.assertTrue(proposal.assets.filter(kind='A').exists())
                    raise ValueError('B no cabe en el límite')
                return super().edit_profile(refs,prompt,rid)
        def check(selected,refs,ctx):events.append('check:'+ctx['option']);return vision(selected,refs,ctx)
        result=self.run_assets(proposal,image_client=Images(),image_checker=check)
        self.assertEqual(events,['edit:A','check:A','edit:B','edit:banner','check:banner'])
        self.assertEqual(result.state,'partial')
        self.assertEqual(next(s for s in result.sections if s['id']=='banner')['readiness'],'ready')
        self.assertEqual(set(result.assets.values_list('kind',flat=True)),{'A','banner','mobile_A','desktop_A'})

    def test_empty_context_banner_recovers_current_section_before_fit_and_preserves_other_copy(self):
        proposal=self.blocked_proposal();proposal.context['banner']={}
        row=next(s for s in proposal.sections if s['id']=='banner')
        row['copy']='Frase: «Software that holds up.»\nEtiqueta: «FOUNDER, PROJECTAPP»'
        proposal.save();before=copy.deepcopy(proposal.sections)
        expected={'lines':['Software that','holds up.'],'highlight':'holds','label':'FOUNDER, PROJECTAPP'}
        real_fit=visual.banner_fit
        def fit(copy):
            saved=ProfileProposal.objects.get(pk=proposal.pk).context['banner']
            self.assertEqual({k:saved[k] for k in expected},expected)
            return real_fit(copy)
        with patch.object(visual,'banner_fit',side_effect=fit), \
             patch('team_backend.perfil_contenido.draft',side_effect=AssertionError('whole proposal forbidden')), \
             patch.object(providers,'claude',side_effect=AssertionError('unexpected paid call')):
            result=self.run_assets(proposal)
        self.assertEqual(result.state,'ready',result.findings)
        self.assertEqual({k:result.context['banner'][k] for k in expected},expected)
        self.assertTrue(result.context['render_evidence'][0]['ok'])
        self.assertEqual(result.context['render_evidence'][0]['input'],expected)
        self.assertEqual([s for s in result.sections if s['id'] not in ('photo','banner')],
                         [s for s in before if s['id'] not in ('photo','banner')])

    def test_bad_chroma_mask_stays_pending_and_never_reaches_vision_or_assets(self):
        proposal=self.blocked_proposal();checked=[]
        class Images(FakeProfileImages):
            def edit_profile(self,refs,prompt,rid):return keyed_photo(hole=True)
        result=self.run_assets(proposal,image_client=Images(),image_checker=lambda *args:checked.append(args))
        self.assertEqual(result.state,'partial');self.assertFalse(result.assets.exists());self.assertEqual(checked,[])
        for row in result.sections:
            if row['id'] in ('photo','banner'):
                self.assertEqual(row['readiness'],'blocked')
                self.assertTrue(any('agujeros grandes' in issue for issue in row['issues']),row['issues'])

    def test_opaque_edits_keep_identity_reference_and_store_private_mattes(self):
        proposal=self.blocked_proposal();checked=[]
        class Images(FakeProfileImages):
            def edit_profile(self,refs,prompt,rid):return keyed_photo()
        def check(selected,refs,ctx):
            checked.append(ctx['option']);self.assertIn('03',refs)
            if ctx['option']=='banner':self.assertIn('02',refs)
            else:self.assertIn('circle_'+ctx['option']+'_32',selected)
            return vision(selected,refs,ctx)
        result=self.run_assets(proposal,image_client=Images(),image_checker=check)
        self.assertEqual(result.state,'ready');self.assertEqual(checked,['A','B','banner'])
        for asset in result.assets.filter(kind__in=['A','B','banner']):
            matte=orquestacion.unpack(asset.provenance['mask'])
            with Image.open(io.BytesIO(matte)) as im:self.assertEqual(im.getchannel('A').getextrema(),(0,255))

    def test_openai_400_message_param_and_code_reach_ledger_and_pending_reasons(self):
        proposal=self.blocked_proposal();calls=[]
        error={'message':'Transparent background is not supported for this model.','param':'background','code':'invalid_value'}
        def handler(request,**kwargs):calls.append(request);return httpx.Response(400,json={'error':error})
        with patch.object(httpx.Client,'send',side_effect=handler),patch.object(images,'live',return_value='fake-key'), \
             patch.dict(os.environ,{'OPENAI_LIMIT_USD':'10'}):
            result=self.run_assets(proposal,image_client=images.ImageConnector())
        self.assertEqual(len(calls),3);self.assertFalse(result.assets.exists());self.assertEqual(result.state,'partial')
        entries=list(UsageEntry.objects.filter(provider='openai',purpose='profile-image-edit'))
        self.assertEqual(len(entries),3)
        for entry in entries:
            self.assertEqual(entry.status,'rejected');self.assertEqual(entry.usage['http_status'],400)
            self.assertEqual(entry.usage['error'],error)
        for row in result.sections:
            if row['id'] in ('photo','banner'):
                for value in (error['message'],'param=background','code=invalid_value'):
                    self.assertTrue(any(value in issue for issue in row['issues']),row['issues'])

    def test_completed_legacy_assets_job_does_not_swallow_corrected_request(self):
        from team_backend import perfil_galeria as gallery
        proposal=self.blocked_proposal();refs=gallery.references(self.gustavo)
        old_signature=orquestacion.digest({'references':refs,'brand':perfil_assets.content.BRAND_VERSION})
        old_id=uuid.uuid5(perfil.NS,f'{proposal.id}:v{proposal.version}:assets:{old_signature}')
        Job.objects.create(id=old_id,owner=self.gustavo,kind='prepare_profile_assets',state='complete',
            params={'proposal':str(proposal.id),'version':proposal.version,'references':refs})
        job=perfil_assets.queue(self.gustavo,proposal.id)
        self.assertNotEqual(job.pk,old_id);self.assertEqual(job.state,'queued')
        self.assertEqual(perfil_assets.queue(self.gustavo,proposal.id).pk,job.pk)

    def test_current_v5_notes_and_brand_reach_small_review_and_each_edit(self):
        from team_backend import perfil_galeria as gallery
        from team_backend.models import GalleryPhoto
        proposal=self.blocked_proposal()
        for photo in GalleryPhoto.objects.all():
            gallery.update(self.gustavo,photo,{'note':'v5: camiseta blanca oversized y gafas claras.'})
        seen=[]
        def review(ctx):seen.extend(ctx['references']);return brand_reviewer(ctx)
        result=self.run_assets(proposal,reviewer=review)
        self.assertEqual(len(seen),3);self.assertTrue(all('v5:' in r['note'] for r in seen))
        self.assertEqual(result.references,gallery.references(self.gustavo))
        self.assertEqual(result.state,'ready')

    def test_reference_conflict_stops_images_but_keeps_nonvisual_copy(self):
        proposal=self.blocked_proposal();client=FakeProfileImages()
        def conflict(ctx):return dict(brand_reviewer(ctx),reference_conflicts=['Notas contradictorias'])
        result=self.run_assets(proposal,reviewer=conflict,image_client=client)
        self.assertEqual(client.calls,[]);self.assertEqual(result.state,'partial')
        self.assertTrue(next(s for s in result.sections if s['id']=='headline')['copy'])

    def test_successful_original_edits_are_reused_and_existing_assets_are_skipped(self):
        self.references();proposal=self.run_proposal(self.proposal(),drafter=brand_draft,reviewer=brand_reviewer,
            image_checker=lambda *args:dict(vision(*args),ok=False))
        client=FakeProfileImages();result=self.run_assets(proposal,image_client=client)
        self.assertEqual(client.calls,[]);self.assertEqual(result.state,'ready')

    def test_partial_package_preserves_existing_asset_ids_and_checks_only_missing_b(self):
        self.references()
        proposal=self.run_proposal(self.proposal(),drafter=brand_draft,reviewer=brand_reviewer,
            image_checker=lambda selected,refs,ctx:dict(vision(selected,refs,ctx),ok=ctx['option']!='B'))
        before=dict(proposal.assets.values_list('kind','id'));checks=[]
        def check(selected,refs,ctx):checks.append(ctx['option']);return vision(selected,refs,ctx)
        client=FakeProfileImages();result=self.run_assets(proposal,image_client=client,image_checker=check)
        self.assertEqual(checks,['B']);self.assertEqual(client.calls,[])
        self.assertEqual({k:v for k,v in result.assets.values_list('kind','id') if k in before},before)
        self.assertEqual(result.state,'ready')

    def test_shared_cap_counts_parent_actual_uncertain_and_other_asset_cycles(self):
        proposal=self.blocked_proposal()
        UsageEntry.objects.create(id=uuid.uuid4(),created_at=timezone.now(),provider='anthropic',purpose='profile-copy',
            status='complete',reserved_usd=Decimal('2.5'),actual_usd=Decimal('2.3'),usage={'cycle_id':str(proposal.cycle_id)})
        UsageEntry.objects.create(id=uuid.uuid4(),created_at=timezone.now(),provider='openai',purpose='profile-image-edit',
            status='uncertain',reserved_usd=Decimal('7.6'),usage={'budget_bucket':proposal.cycle.budget_bucket})
        with patch.dict(os.environ,{'OPENAI_LIMIT_USD':'100'}):
            runtime=orquestacion.Runtime.open('perfil_assets','cap-assets',self.gustavo,budget_parent=proposal.cycle)
            def paid():providers.reserve('openai','profile-image-edit',Decimal('.11'));return synthetic()
            with runtime.session(),self.assertRaisesRegex(orquestacion.CycleStopped,'cost_cap'):
                runtime.call('perfil_editar_persona',{'proposal':str(proposal.id),'kind':'A','references':[],'instruction':'Synthetic'},paid)
        self.assertEqual(UsageEntry.objects.count(),2)
        self.assertEqual(orquestacion.amount(orquestacion.budget_usage(proposal.cycle)),Decimal('9.9'))

    def test_api_double_submit_command_and_ownership(self):
        proposal=self.blocked_proposal();path=f'/api/v1/perfil/{proposal.id}/decision'
        data={'revision':proposal.revision,'action':'prepare_assets'}
        first=self.human.post(path,data,format='json');second=self.human.post(path,data,format='json')
        self.assertEqual(first.status_code,200,first.data);self.assertEqual(first.data,second.data)
        self.assertTrue(first.data['assets_pending']);self.assertEqual(Job.objects.filter(kind='prepare_profile_assets').count(),1)
        output=io.StringIO();call_command('perfil_assets',str(proposal.id)[:8],stdout=output)
        self.assertEqual(Job.objects.filter(kind='prepare_profile_assets').count(),1)
        self.assertIn(self.api.post(path,data,format='json').status_code,(403,404))

    def test_cancelled_proposal_cannot_be_resurrected_during_review(self):
        proposal=self.blocked_proposal()
        def cancel(ctx):
            ProfileProposal.objects.filter(pk=proposal.id).update(state='cancelled')
            return brand_reviewer(ctx)
        client=FakeProfileImages();result=self.run_assets(proposal,reviewer=cancel,image_client=client)
        self.assertEqual(result.state,'cancelled');self.assertEqual(client.calls,[])


class ProfileQuestionTests(ProfileBase):
    def question(self,proposal,key,state='open',section='education'):
        proposal.sections.append({'id':section,'missing':[{'key':key,'question':'Dato','purpose':'Completar'}]})
        proposal.save()
        return TeamQuestion.objects.create(agent='perfil',memory_key=key,question='Dato',origin=f'perfil:{proposal.id}',state=state)

    def test_terminal_transitions_retire_pending_not_answered_or_declined(self):
        for state in ('superseded','cancelled'):
            proposal=self.proposal()
            pending=self.question(proposal,'perfil.'+state+'.education')
            pending.postponed_until=timezone.now();pending.save()
            answered=self.question(proposal,'perfil.'+state+'.date','answered')
            declined=self.question(proposal,'perfil.'+state+'.languages','declined')
            proposal.state=state;proposal.save()
            pending.refresh_from_db();answered.refresh_from_db();declined.refresh_from_db()
            self.assertEqual(pending.state,'withdrawn');self.assertEqual(answered.state,'answered');self.assertEqual(declined.state,'declined')

    def test_cleanup_replaced_sections_different_languages_owner_and_idempotency(self):
        old=ProfileProposal.objects.create(owner=self.gustavo,key='old',state='partial')
        a=self.question(old,'perfil.educacion.titulo')
        new=ProfileProposal.objects.create(owner=self.gustavo,key='new',state='partial')
        b=self.question(new,'perfil.education.degree')
        other=ProfileProposal.objects.create(owner=self.service,key='other',state='partial')
        c=self.question(other,'perfil.education.institution')
        self.assertEqual(preguntas.clean_profile_questions(self.gustavo),1)
        self.assertEqual(preguntas.clean_profile_questions(self.gustavo),0)
        a.refresh_from_db();b.refresh_from_db();c.refresh_from_db()
        self.assertEqual((a.state,b.state,c.state),('withdrawn','open','open'))
        old.state='superseded';ProfileProposal.objects.filter(pk=old.pk).update(state='superseded')
        TeamQuestion.objects.filter(pk=a.pk).update(state='open')
        call_command('perfil_preguntas',stdout=io.StringIO())
        a.refresh_from_db();self.assertEqual(a.state,'withdrawn')
        out=io.StringIO();call_command('perfil_preguntas',stdout=out);self.assertIn('retiradas: 0',out.getvalue())
