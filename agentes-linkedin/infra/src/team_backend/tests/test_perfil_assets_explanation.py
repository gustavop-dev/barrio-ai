"""Post-#92 banner continuation; synthetic assets and injected providers only."""
import copy
import json
import uuid
from decimal import Decimal
from unittest.mock import Mock, patch
from django.test import SimpleTestCase
from django.utils import timezone
from knowledge import providers
from team_backend import imagenes, orquestacion, perfil, perfil_assets, perfil_galeria as gallery, perfil_visual as visual
from team_backend.models import CycleLedger, Job, UsageEntry
from team_backend.tests.test_perfil import ProfileBase, FakeProfileImages, brand_draft, brand_reviewer, synthetic, vision


REPAIRED={
    'reason':'La frase presenta utilidad para equipos según el posicionamiento y las unidades citadas; '
        'render.banner_fit acredita el ajuste del texto, no una comprobación móvil.',
    'benefit':'Comunica la orientación del servicio sin prometer resultados del cliente.',
    'steps':['Usar la fuente y colores de marca.fuente y marca.tokens.',
        'Comparar el resultado en LinkedIn antes de aplicarlo.'],
}


def explanation_review(context):
    result=perfil_assets.classified_review(brand_reviewer(context))
    for check in result['sections']:
        section=next(s for s in context['draft']['sections'] if s['id']==check['id'])
        if check['id']=='banner' and section['reason']!=REPAIRED['reason']:
            check.update(ok=False,explanation_ok=False,
                reason='Solo explicación: afirma comprobado en móvil sin preview y exagera el resultado del cliente.')
    return result


class ExplanationContinuationTests(ProfileBase):
    def pending_banner(self,all_assets=False):
        if not gallery.references(self.gustavo):self.references()
        proposal=self.run_proposal(self.proposal(),drafter=brand_draft,reviewer=brand_reviewer,
            image_checker=lambda selected,refs,ctx:dict(vision(selected,refs,ctx),ok=not all_assets and ctx['option']!='banner'))
        row=next(s for s in proposal.sections if s['id']=='banner')
        row.update(reason='Comprobado en móvil; resuelve el problema del cliente.',
            benefit='Garantiza el éxito del cliente.',steps=['Aplicar el banner ya comprobado en móvil.'],
            decision='accepted',application='pending',note='Conservar decisión manual')
        proposal.save()
        return proposal

    def run_assets(self,proposal,**kwargs):
        job=perfil_assets.queue(self.gustavo,proposal.id)
        options={'reviewer':explanation_review,'writer':lambda ctx:copy.deepcopy(REPAIRED),
            'image_client':FakeProfileImages(),'image_checker':vision}
        options.update(kwargs)
        result=perfil_assets.run(job,**options)
        Job.objects.filter(pk=job.pk).update(state='complete')
        return result

    def test_repairs_only_banner_then_reviews_once_preserving_photos_copy_decisions_and_budget(self):
        proposal=self.pending_banner();before=copy.deepcopy(proposal.sections)
        photos=list(proposal.assets.filter(kind__in=['A','B']).values())
        usage=list(UsageEntry.objects.values());client=FakeProfileImages();events=[]
        def review(ctx):
            events.append('review');self.assertEqual(ctx['section_ids'],['banner'])
            for key in ('lines','highlight','label'):
                self.assertEqual(ctx['draft']['banner'][key],proposal.context['banner'][key])
            self.assertNotIn('render.preview_mobile',{e['id'] for e in ctx['evidence_catalog']})
            return explanation_review(ctx)
        def writer(ctx):
            events.append('repair');self.assertEqual(ctx['section']['id'],'banner')
            self.assertEqual(ctx['positioning'],proposal.context['positioning'])
            allowed={e['id'] for e in ctx['evidence_catalog']}
            self.assertIn('render.banner_fit',allowed)
            self.assertTrue(all(e.startswith('marca.') or e=='render.banner_fit' or e in ctx['positioning']['evidence'] for e in allowed))
            return copy.deepcopy(REPAIRED)
        def checker(selected,refs,ctx):
            events.append('vision');self.assertEqual(ctx['option'],'banner')
            self.assertEqual(set(selected),{'banner','mobile_A','desktop_A','mobile_B','desktop_B'})
            return vision(selected,refs,ctx)
        result=self.run_assets(proposal,reviewer=review,writer=writer,image_client=client,image_checker=checker)
        self.assertEqual(events,['review','repair','review','vision'])
        self.assertEqual(client.calls,[])  # Original confirmed banner person edit is also reused.
        self.assertEqual(list(result.assets.filter(kind__in=['A','B']).values()),photos)
        self.assertTrue(all(p['width']==p['height']==800 for p in photos))
        self.assertEqual(list(UsageEntry.objects.values()),usage)
        self.assertEqual([s for s in result.sections if s['id']!='banner'],[s for s in before if s['id']!='banner'])
        row=next(s for s in result.sections if s['id']=='banner');old=next(s for s in before if s['id']=='banner')
        for key in ('copy','citations','decision','application','note','version'):
            self.assertEqual(row[key],old[key])
        self.assertEqual({k:row[k] for k in REPAIRED},REPAIRED)
        self.assertEqual(row['readiness'],'ready');self.assertEqual(result.version,proposal.version)
        child=CycleLedger.objects.get(cycle='perfil_assets')
        self.assertEqual(child.budget_bucket,proposal.cycle.budget_bucket)
        self.assertEqual(child.calls,6)
        checks=result.context['assets_verdict']['sections']
        self.assertTrue(checks[0]['asset_ok'] and checks[0]['explanation_ok'])
        banner=result.assets.get(kind='banner')
        previews={e['id']:e for e in banner.provenance['render_evidence']}
        for viewport in ('mobile','desktop'):
            evidence=previews['render.preview_'+viewport]
            self.assertTrue(evidence['reviewed']);self.assertEqual(evidence['banner_sha256'],banner.sha256)
            for kind,sha in evidence['hashes'].items():self.assertEqual(result.assets.get(kind=kind).sha256,sha)
        # Retry the same job: all confirmed calls, including repair and its review, are reused.
        self.run_assets(result,reviewer=review,writer=writer,image_client=client,image_checker=checker)
        self.assertEqual(events,['review','repair','review','vision']);self.assertEqual(client.calls,[])

    def test_second_explanation_rejection_stays_needs_input_but_generates_asset_without_loop(self):
        proposal=self.pending_banner();writer=Mock(return_value=copy.deepcopy(REPAIRED));seen=[]
        def reject(ctx):
            seen.append(ctx['section_ids']);result=explanation_review(ctx)
            result['sections'][0].update(ok=False,explanation_ok=False,reason='Explicación aún no acreditada')
            return result
        result=self.run_assets(proposal,reviewer=reject,writer=writer)
        self.assertEqual(seen,[['banner'],['banner']]);writer.assert_called_once()
        row=next(s for s in result.sections if s['id']=='banner')
        self.assertEqual(row['readiness'],'needs_input');self.assertTrue(row['copy'])
        self.assertIn('Explicación aún no acreditada',' '.join(row['issues']))
        self.assertTrue(result.assets.filter(kind='banner',review__ok=True).exists())
        self.assertFalse(result.context['assets_verdict']['sections'][0]['explanation_ok'])

    def test_writer_failure_or_attempt_to_change_visible_copy_does_not_block_asset(self):
        for answer in (ValueError('Redacción no disponible'),dict(REPAIRED,copy='Invented claim')):
            with self.subTest(answer=answer):
                proposal=self.pending_banner();old=copy.deepcopy(proposal.sections)
                writer=Mock(side_effect=answer) if isinstance(answer,Exception) else Mock(return_value=answer)
                reviewer=Mock(side_effect=explanation_review)
                result=self.run_assets(proposal,writer=writer,reviewer=reviewer)
                writer.assert_called_once();reviewer.assert_called_once()
                row=next(s for s in result.sections if s['id']=='banner')
                self.assertEqual(row['readiness'],'needs_input')
                self.assertEqual(row['copy'],next(s for s in old if s['id']=='banner')['copy'])
                self.assertTrue(result.assets.filter(kind='banner').exists())
                self.assertIn('no se pudo reparar/revisar',' '.join(row['issues']))

    def test_failed_or_incomplete_second_review_keeps_original_explanation_pending(self):
        for failure in ('error','missing_section'):
            with self.subTest(failure=failure):
                proposal=self.pending_banner();seen=[]
                def review(ctx):
                    seen.append(ctx)
                    if len(seen)==1:return explanation_review(ctx)
                    if failure=='error':raise ValueError('Revisión no disponible')
                    return dict(explanation_review(ctx),sections=[])
                result=self.run_assets(proposal,reviewer=review)
                row=next(s for s in result.sections if s['id']=='banner')
                self.assertEqual(row['readiness'],'needs_input');self.assertEqual(len(seen),2)
                self.assertIn('Comprobado en móvil',row['reason'])
                self.assertTrue(result.assets.filter(kind='banner').exists())

    def test_visual_or_visible_phrase_rejection_blocks_without_explanation_repair(self):
        for defect in ('visible_phrase','label','design','references','fit'):
            with self.subTest(defect=defect):
                proposal=self.pending_banner();writer=Mock(side_effect=AssertionError('Repair forbidden'))
                client=FakeProfileImages();checker=Mock(side_effect=AssertionError('Vision forbidden'))
                if defect=='fit':
                    proposal.context['banner']['lines']=['Much too long '*20,'software.'];proposal.save()
                def review(ctx):
                    result=explanation_review(ctx)
                    if defect=='references':result['reference_conflicts']=['Notas incompatibles']
                    elif defect!='fit':
                        result['sections'][0].update(ok=False,asset_ok=False,reason=defect)
                        if defect in ('visible_phrase','label'):result.update(banner_ok=False,banner_reason=defect)
                    return result
                result=self.run_assets(proposal,reviewer=review,writer=writer,image_client=client,image_checker=checker)
                writer.assert_not_called();checker.assert_not_called();self.assertEqual(client.calls,[])
                self.assertFalse(result.assets.filter(kind='banner').exists())
                self.assertEqual(next(s for s in result.sections if s['id']=='banner')['readiness'],'blocked')

    def test_visual_rejection_after_repair_still_blocks_and_does_not_repeat_photo_checks(self):
        proposal=self.pending_banner();checks=[]
        def reject(selected,refs,ctx):checks.append(ctx['option']);return dict(vision(selected,refs,ctx),ok=False)
        result=self.run_assets(proposal,image_checker=reject)
        self.assertEqual(checks,['banner']);self.assertFalse(result.assets.filter(kind='banner').exists())
        self.assertEqual(next(s for s in result.sections if s['id']=='banner')['readiness'],'blocked')

    def test_final_review_may_find_a_blocking_asset_defect(self):
        proposal=self.pending_banner();seen=[]
        def review(ctx):
            seen.append(ctx);result=explanation_review(ctx)
            if len(seen)==2:
                result['sections'][0].update(ok=False,asset_ok=False,reason='Etiqueta no acreditada')
                result.update(banner_ok=False,banner_reason='Etiqueta no acreditada')
            return result
        result=self.run_assets(proposal,reviewer=review)
        self.assertEqual(len(seen),2);self.assertFalse(result.assets.filter(kind='banner').exists())
        self.assertEqual(next(s for s in result.sections if s['id']=='banner')['readiness'],'blocked')

    def test_original_call_cap_reserves_all_three_assets_and_skips_optional_repair(self):
        proposal=self.pending_banner(all_assets=True);writer=Mock(side_effect=AssertionError('No call allowance'))
        result=self.run_assets(proposal,writer=writer)
        writer.assert_not_called()
        child=CycleLedger.objects.get(cycle='perfil_assets')
        self.assertEqual(child.calls,10);self.assertEqual(child.limits['max_calls'],10)
        self.assertEqual(set(result.assets.values_list('kind',flat=True)),perfil.ASSET_KINDS)
        self.assertEqual(next(s for s in result.sections if s['id']=='banner')['readiness'],'needs_input')

    def test_shared_cost_cap_stops_repair_without_changing_saved_photos_or_usage(self):
        proposal=self.pending_banner();photos=list(proposal.assets.values());called=[]
        UsageEntry.objects.create(id=uuid.uuid4(),created_at=timezone.now(),provider='anthropic',purpose='profile-copy',
            status='complete',reserved_usd=Decimal('10'),actual_usd=Decimal('10'),usage={'cycle_id':str(proposal.cycle_id)})
        before=list(UsageEntry.objects.values())
        result=self.run_assets(proposal,writer=lambda ctx:called.append(ctx))
        self.assertEqual(called,[]);self.assertEqual(list(result.assets.values()),photos)
        self.assertEqual(list(UsageEntry.objects.values()),before)
        self.assertEqual(CycleLedger.objects.get(cycle='perfil_assets').stop_reason,'cost_cap')

    def test_deployment_reuses_confirmed_repair_and_reviews_after_render_failure(self):
        proposal=self.pending_banner();writer=Mock(return_value=copy.deepcopy(REPAIRED))
        first=self.run_assets(proposal,writer=writer,image_checker=lambda *args:dict(vision(*args),ok=False))
        writer.assert_called_once()
        with patch.object(perfil_assets,'ASSETS_VERSION','next-explanation-version'):
            result=self.run_assets(first,writer=Mock(side_effect=AssertionError('Confirmed repair must be reused')),
                reviewer=Mock(side_effect=AssertionError('Confirmed section review must be reused')))
        self.assertTrue(result.assets.filter(kind='banner',review__ok=True).exists())

    def test_new_assets_version_does_not_reuse_the_completed_pre_fix_job(self):
        proposal=self.pending_banner();refs=gallery.references(self.gustavo)
        signature=orquestacion.digest({'references':refs,'brand':perfil_assets.content.BRAND_VERSION,
            'matte':visual.perfil_chroma.VERSION,'render':visual.RENDER_VERSION,'review':visual.REVIEW_VERSION,
            'model':perfil_assets.connectors_images.EDIT_MODEL,'transparent':perfil_assets.connectors_images.supports_transparency()})
        old_id=uuid.uuid5(perfil.NS,f'{proposal.id}:v{proposal.version}:assets:{signature}')
        Job.objects.create(id=old_id,owner=self.gustavo,kind='prepare_profile_assets',state='complete',
            params={'proposal':str(proposal.id),'version':proposal.version,'references':refs})
        self.assertNotEqual(perfil_assets.queue(self.gustavo,proposal.id).pk,old_id)


class ExplanationContractTests(SimpleTestCase):
    def test_small_writer_contract_and_mobile_scope_with_fake_provider(self):
        with patch.object(providers,'claude',return_value={'text':json.dumps(REPAIRED)}) as provider:
            self.assertEqual(perfil_assets.repair_explanation({'section':{'id':'banner'}}),REPAIRED)
        args,kwargs=provider.call_args
        self.assertEqual(kwargs['max_tokens'],900);self.assertEqual(kwargs['effort'],'low')
        self.assertEqual(set(kwargs['output_schema']['properties']),{'reason','benefit','steps'})
        self.assertIn('render.preview_mobile',args[0]);self.assertIn('sin promesas adicionales',args[0])

    def test_legacy_rejection_cannot_be_guessed_to_be_explanation_only(self):
        result=perfil_assets.classified_review({'sections':[{'id':'banner','ok':False,'missing_valid':False,
            'reason':'El reason afirma comprobado en móvil'}], 'banner_ok':True,'banner_reason':'Frase válida','reference_conflicts':[]})
        self.assertFalse(result['sections'][0]['asset_ok'])

    def test_preview_evidence_requires_actual_bytes_and_never_certifies_linkedin(self):
        raw=synthetic();self.assertEqual(visual.preview_evidence({'banner':raw}),[])
        files={'banner':raw,'mobile_A':visual.preview(raw,raw,True),'desktop_A':visual.preview(raw,raw)}
        evidence=visual.preview_evidence(files)
        self.assertEqual({e['id'] for e in evidence},{'render.preview_mobile','render.preview_desktop'})
        for row in evidence:
            self.assertFalse(row['reviewed']);self.assertIn('no acredita la app real',row['scope'])
            self.assertEqual(row['banner_sha256'],imagenes.sha(raw))
            self.assertEqual(row['hashes'],{k:imagenes.sha(files[k]) for k in row['hashes']})

    def test_uncertain_explanation_call_is_never_repeated_and_confirmed_answer_is_reused(self):
        request={'section':'banner'};operation=Mock(side_effect=AssertionError('Must reuse'))
        call={'edge':'perfil_reparar_explicacion','request_hash':orquestacion.digest(request),'state':'pending'}
        ledger=Mock(progress_ledger={'calls':{'repair:banner':call}})
        with self.assertRaisesRegex(ValueError,'conciliar'):
            perfil_assets.reuse_exact('perfil_reparar_explicacion',request,[ledger],operation)
        call.update(state='answered',result=orquestacion.pack(REPAIRED))
        self.assertEqual(perfil_assets.reuse_exact('perfil_reparar_explicacion',request,[ledger],operation),REPAIRED)
        operation.assert_not_called()

    def test_vision_discards_preview_evidence_for_other_bytes(self):
        raw=synthetic();files={'banner':raw,'mobile_A':visual.preview(raw,raw,True)}
        evidence=visual.preview_evidence(files);evidence[0]['banner_sha256']='stale'
        answer={'ok':True,'checks':[{'point':n,'ok':True,'reason':'Fake'} for n in (4,5,6,7,8)],
            'identity_03':True,'smile_01':True,'clear_glasses':True,'pose_01':True,'body_02':True,'clothing':True,
            'face_height':0,'eyes_y':0,'head_top':0,'reasons':[]}
        with patch.object(providers,'claude',return_value={'text':json.dumps(answer)}) as provider:
            visual.check(files,{}, {'render_evidence':evidence,'evidence_catalog':evidence})
        context=json.loads(provider.call_args.args[1][0]['text'])
        self.assertEqual(context['render_evidence'],[]);self.assertEqual(context['evidence_catalog'],[])
