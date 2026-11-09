"""Private profile packages and versioned manual decisions; never writes LinkedIn."""
import secrets
import uuid
from datetime import timedelta
from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from . import imagenes, orquestacion, perfil, perfil_galeria
from .capturas_views import FileView, serve
from .exceptions import Conflict
from .jobs import audit
from .models import ProfileAsset, ProfileProposal
from .operador_views import human_session, valid
from .permissions import require


def get(user,pid,lock=False):
    require(user,'operate_linkedin')
    rows=ProfileProposal.objects.select_for_update() if lock else ProfileProposal.objects.all()
    proposal=rows.filter(pk=pid,owner=user).first()
    if not proposal:raise NotFound()
    return proposal


def payload(proposal):
    invalid=perfil_galeria.stale(proposal.references,proposal.owner)
    rows=[]
    for section in proposal.sections:
        row=dict(section)
        if invalid and row['id'] in ('photo','banner'):
            row.update(readiness='blocked',copy='',issues=['Cambió o se revocó una referencia de Perfil; pide ajuste.'])
        if row.get('superseded_by'):row.update(readiness='blocked',copy='',issues=['Sustituida por una propuesta más reciente.'])
        rows.append(row)
    visual_superseded=any(s.get('superseded_by') for s in rows if s['id'] in ('photo','banner'))
    return {'id':str(proposal.id),'version':proposal.version,'revision':proposal.revision,'mode':proposal.mode,
        'state':proposal.state,'sections':rows,'photo_choice':proposal.photo_choice,'findings':proposal.findings,
        'microphone_note':perfil.content.MICROPHONE_NOTE,'markdown':perfil.markdown(proposal),
        'document_url':f'/api/v1/perfil/{proposal.id}/documento','references_valid':not invalid,
        'references':[{'id':r['id'],'role':r['role'],'note':r['note'],'version':r['version'],
            'url':f'/api/v1/galeria/{r["id"]}/imagen'} for r in proposal.references] if not invalid else [],
        'assets':[{'id':str(a.id),'kind':a.kind,'width':a.width,'height':a.height,'review':a.review,
                   'url':f'/api/v1/perfil/{proposal.id}/assets/{a.id}'} for a in proposal.assets.filter(version=proposal.version)
                  if a.review.get('ok')] if not invalid and not visual_superseded else []}


class Detail(APIView):
    def get(self,request,pid):return Response(payload(get(request.user,pid)))


class DecisionInput(serializers.Serializer):
    revision=serializers.IntegerField(min_value=1)
    section=serializers.CharField(required=False,allow_blank=True,default='')
    action=serializers.ChoiceField(choices=['accept','adjust','later','decline','applied','changed','choose_A','choose_B','verify'])
    note=serializers.CharField(required=False,allow_blank=True,max_length=12000,default='')


def revise(proposal,note,affected=None):
    used=sum(c['edge']=='perfil_copy' for c in proposal.cycle.progress_ledger.get('calls',{}).values()) if proposal.cycle_id else 0
    if proposal.version>=2 or used>=2:raise Conflict('Ya se usaron las dos rondas de esta propuesta. Se conserva el presupuesto; requiere revisión del ciclo.')
    if proposal.state in ('queued','running','cancelled'):raise Conflict('Espera al ciclo vigente antes de pedir un ajuste.')
    if proposal.cycle_id and proposal.cycle.state=='stopped':raise Conflict('El ciclo está detenido; concilia el motivo sin reiniciar saldo.')
    proposal.history.append({'version':proposal.version,'sections':proposal.sections,'photo_choice':proposal.photo_choice,
                             'at':timezone.now().isoformat(),'reason':note})
    proposal.version+=1;proposal.revision+=1;proposal.state='queued'
    refs=perfil_galeria.references(proposal.owner)
    if affected and {'photo','banner'} & set(affected):
        affected=list(dict.fromkeys(list(affected)+['photo','banner']))
    if affected and proposal.mode=='full' and refs!=proposal.references:
        affected=list(dict.fromkeys(list(affected)+['photo','banner']))
    if not affected or {'photo','banner'} & set(affected):proposal.photo_choice=''
    proposal.context['affected']=affected or []
    proposal.context['adjustment']=note
    proposal.references=refs
    proposal.save();perfil._job(proposal)


class Decision(APIView):
    def post(self,request,pid):
        human_session(request);require(request.user,'approve_actions');data=valid(DecisionInput,request)
        action=data['action'];note=data['note'].strip()
        if action=='verify':return verify(request,pid,data)
        with transaction.atomic():
            proposal=get(request.user,pid,True)
            # Repeated network submissions acknowledge the already saved event without a second history entry.
            fingerprint=orquestacion.digest(dict(data,actor=request.user.pk))
            if any(e.get('request')==fingerprint for e in proposal.history):return Response(payload(proposal))
            if proposal.revision!=data['revision']:raise Conflict('La propuesta cambió; abre la versión vigente antes de decidir.')
            if proposal.state in ('queued','running','cancelled','superseded'):raise Conflict('Esta versión todavía no admite decisiones.')
            if action!='later':proposal.postponed_until=None
            section=next((r for r in proposal.sections if r['id']==data['section']),None)
            if action=='later':proposal.postponed_until=timezone.now()+timedelta(days=3)
            elif action=='adjust':
                if not note:raise ValidationError('Indica qué quieres ajustar.')
                if data['section'] and section is None:raise ValidationError('Elige una sección vigente.')
                revise(proposal,note,affected=[section['id']] if section else None)
            else:
                if section is None:raise ValidationError('Elige una sección.')
                if section.get('superseded_by'):raise Conflict('Esta sección tiene una propuesta más reciente; abre la versión vigente.')
                if action in ('decline','changed') and not note:raise ValidationError('Indica el motivo o pega el texto que usaste.')
                if action!='decline' and section['readiness']!='ready':raise Conflict('Esta sección está pendiente de información o fundamento.')
                if section['id'] in ('photo','banner') and perfil_galeria.stale(proposal.references,proposal.owner):
                    raise Conflict('Cambió una referencia o autorización; pide ajuste.')
                if section['id'] in ('photo','banner') and action!='decline':
                    kinds=set(proposal.assets.filter(version=proposal.version,review__ok=True).values_list('kind',flat=True))
                    if not perfil.SECTION_ASSETS[section['id']] <= kinds:raise Conflict('Los assets revisados de esta sección están incompletos.')
                if action in ('choose_A','choose_B'):
                    kinds=set(proposal.assets.filter(version=proposal.version,review__ok=True).values_list('kind',flat=True))
                    if section['id']!='photo' or not {'A','B'}<=kinds:raise Conflict('Necesitas ambas opciones válidas antes de elegir.')
                    if proposal.photo_choice!=action[-1]:
                        section['application']='pending'
                        for field in ('applied_at','applied_text','checked_at','check_evidence'):section.pop(field,None)
                    proposal.photo_choice=action[-1];section['decision']='accepted'
                elif action=='accept':
                    if section['id']=='activity' and not any(e.get('action')=='accept' and e.get('section')=='activity' and e.get('version')==proposal.version for e in proposal.history):
                        from .oficina_eventos import handoff
                        transaction.on_commit(lambda:handoff('perfil','director_editorial',cycle=proposal.cycle_id,edge='perfil_orientacion_editorial',phase='artifact'))
                    if section['id']=='photo' and not proposal.photo_choice:raise Conflict('Elige A o B; no hay selección automática.')
                    section['decision']='accepted'
                elif action=='decline':section['decision']='declined';section['note']=note
                elif action in ('applied','changed'):
                    if section['decision']!='accepted':raise Conflict('Acepta primero esta sección; foto requiere elegir A o B.')
                    section.update(application='applied',applied_at=timezone.now().isoformat(),applied_text=note if action=='changed' else section['copy'],
                        check_available=section['id']=='headline')
            proposal.revision+=1
            proposal.history.append({'request':fingerprint,'action':action,'section':data['section'],'actor':request.user.pk,
                'at':timezone.now().isoformat(),'note':note,'version':proposal.version})
            proposal.save()
            audit(request.user,'profile.decision',proposal.id,decision=action,section=data['section'],version=proposal.version)
        return Response(payload(proposal))


def verify(request,pid,data):
    """External reads are outside the decision transaction: failed checks keep their read/cycle ledger."""
    proposal=get(request.user,pid)
    fingerprint=orquestacion.digest(dict(data,actor=request.user.pk))
    if any(e.get('request')==fingerprint for e in proposal.history):return Response(payload(proposal))
    section=next((s for s in proposal.sections if s['id']==data['section']),None)
    if proposal.revision!=data['revision']:raise Conflict('La propuesta cambió; abre la versión vigente.')
    if proposal.state in ('queued','running','cancelled','superseded') or not section or section.get('superseded_by'):
        raise Conflict('Esta versión no admite comprobación.')
    if section.get('application')!='applied':raise Conflict('Registra primero la aplicación manual.')
    if section['id']!='headline':raise Conflict('Comprobación automática no disponible para esta sección.')
    if not proposal.cycle_id:raise Conflict('Esta propuesta de QA no tiene conector de comprobación.')
    try:
        runtime=orquestacion.Runtime.open('perfil_periodico',str(proposal.id),request.user)
        with runtime.session():
            current=runtime.call('perfil_lectura',{},perfil.read_profile,key=f'verify:{section["id"]}:{proposal.revision}')
    except (orquestacion.CycleStopped,ValueError) as exc:
        raise Conflict('Comprobación no disponible: '+str(exc))
    observed=current['sections'].get(section['id'])
    if not observed or observed['text']!=section['applied_text']:
        with transaction.atomic():
            proposal=get(request.user,pid,True)
            if proposal.revision==data['revision']:
                proposal.revision+=1
                proposal.history.append({'action':'verify_mismatch','section':section['id'],'actor':request.user.pk,
                    'at':current['at'],'version':proposal.version,'observed':observed})
                proposal.save()
        raise Conflict('La relectura no coincide o no está disponible; sigue Aplicado por Gustavo.')
    with transaction.atomic():
        proposal=get(request.user,pid,True)
        if proposal.revision!=data['revision']:raise Conflict('La propuesta cambió durante la comprobación.')
        section=next(s for s in proposal.sections if s['id']==data['section'])
        section.update(application='checked',checked_at=current['at'],check_evidence=observed)
        proposal.revision+=1
        proposal.history.append({'request':fingerprint,'action':'verify','section':section['id'],
            'actor':request.user.pk,'at':timezone.now().isoformat(),'version':proposal.version})
        proposal.save()
        audit(request.user,'profile.decision',proposal.id,decision='verify',section=section['id'],version=proposal.version)
    return Response(payload(proposal))


def document(proposal):
    response=HttpResponse(perfil.markdown(proposal),content_type='text/markdown; charset=utf-8')
    response['Content-Disposition']=f'attachment; filename="propuesta-perfil-v{proposal.version}.md"'
    response['Cache-Control']='private, no-store';response['X-Content-Type-Options']='nosniff'
    return response


def asset_file(request,proposal,aid):
    if (proposal.state in ('cancelled','superseded') or perfil_galeria.stale(proposal.references,proposal.owner)
            or any(s.get('superseded_by') for s in proposal.sections if s['id'] in ('photo','banner'))):
        raise Conflict('Recurso invalidado: revisa la propuesta vigente.')
    asset=ProfileAsset.objects.filter(pk=aid,proposal=proposal,version=proposal.version,review__ok=True).first()
    if not asset:raise NotFound()
    if imagenes.sha(imagenes.read(asset.image))!=asset.sha256:raise Conflict('Los bytes del recurso cambiaron.')
    response=serve(request,asset.image,'image/png');response['Cache-Control']='private, no-store'
    response['Content-Disposition']=f'attachment; filename="perfil-{asset.kind}-v{asset.version}.png"'
    return response


class Document(FileView):
    def get(self,request,pid):return document(get(request.user,pid))


class Asset(FileView):
    def get(self,request,pid,aid):return asset_file(request,get(request.user,pid),aid)


class DownloadTicket(APIView):
    """Native system download without disclosing a device bearer token to the browser.

    A 60-second, one-use capability is stored only as a digest, bound to a single
    resource and revision. Revoke/change/version checks run again when redeemed.
    """
    def post(self,request,pid):
        human_session(request)
        with transaction.atomic():
            proposal=get(request.user,pid,True)
            resource=str(request.data.get('resource','documento'))
            if resource!='documento':
                try:uuid.UUID(resource)
                except ValueError:raise ValidationError('Recurso inválido.')
            if resource!='documento' and not proposal.assets.filter(id=resource,version=proposal.version,review__ok=True).exists():raise NotFound()
            token=secrets.token_urlsafe(32);now=timezone.now()
            proposal.download_tickets={k:v for k,v in proposal.download_tickets.items() if v['expires']>now.isoformat()}
            if len(proposal.download_tickets)>=12:raise Conflict('Espera a que caduquen las descargas anteriores.')
            proposal.download_tickets[imagenes.sha(token.encode())]={'resource':resource,'revision':proposal.revision,
                'expires':(now+timedelta(seconds=60)).isoformat()}
            proposal.save(update_fields=['download_tickets'])
        return Response({'url':f'/api/v1/perfil/{proposal.id}/descarga/{token}'})


class Download(FileView):
    permission_classes=[AllowAny]
    authentication_classes=[]
    def get(self,request,pid,token):
        with transaction.atomic():
            proposal=ProfileProposal.objects.select_for_update().filter(pk=pid,owner__is_active=True).first()
            if not proposal:raise NotFound()
            ticket=proposal.download_tickets.pop(imagenes.sha(token.encode()),None)
            proposal.save(update_fields=['download_tickets'])
        require(proposal.owner,'operate_linkedin')
        if not ticket or ticket['expires']<=timezone.now().isoformat() or ticket['revision']!=proposal.revision:raise NotFound()
        response=document(proposal) if ticket['resource']=='documento' else asset_file(request,proposal,ticket['resource'])
        response['Referrer-Policy']='no-referrer'
        return response
