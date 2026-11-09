"""Profile-owned strategy cycle. Manual application only; no LinkedIn write API.

Every tool runs under Runtime (3b). Same proposal, retries, questions and one
adjustment share the $10 bucket; an uncertain call is never automatically paid again.
"""
import calendar
import io
import os
import re
import uuid
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from PIL import Image
from . import guardas, imagenes, orquestacion, perfil_contenido as content, perfil_galeria as gallery, perfil_visual as visual, research
from .models import ActionExecution, Capture, ConnectorAccount, Job, ProfileAsset, ProfileProposal, ProfileSchedule
from .jobs import audit, enqueue_operation

NS=uuid.UUID('0ff1ce08-0000-4000-8000-000000000008')
EXPLICIT=re.compile(r'^\s*(?:por favor[, ]*)?(?:hazme|prepara|genera|quiero)\s+(?:la|una)\s+propuesta\s+(?:del|de mi)\s+perfil[.!?\s]*$',re.I)
READ_SCHEMA={'type':'object','required':['sections','evidence','at','limitations']}
ASSET_KINDS={'A','B','banner','mobile_A','mobile_B','desktop_A','desktop_B'}
PUBLIC_QUESTION='LinkedIn Help personal profile headline About character limits custom profile URL requirements'


def read_profile():
    """Only the connected owner's reduced profile; missing fields remain explicitly unreadable."""
    from .connectors import get_connector, ConnectorError
    from .red import _read, ReadCapReached
    at=timezone.now().isoformat();result={'sections':{},'evidence':[],'at':at,'limitations':['El conector no expone todas las secciones.']}
    account=ConnectorAccount.objects.filter(provider__in=['unipile','fake'],paused=False,is_locked=False).order_by('created_at').first()
    if not account:return result
    try:
        _read(account,'profile',purpose='profile-strategy')
        value=get_connector(account).get_profile('me')
        if value.get('headline'):
            ref=f'profile:{account.id}:headline:{at}'
            result['sections']['headline']={'text':value['headline'],'source':ref,'at':at}
            result['evidence'].append(ref)
    except (ValueError,ConnectorError,ReadCapReached):result['limitations'].append('No pudimos leer tu perfil actual.')
    return result


def facts(mode):
    public,private=guardas.blocks()
    pieces=[]
    executions=ActionExecution.objects.filter(proposal__capability='CONT-09',state__in=['confirmed','sent'],
        proposal__piece__isnull=False).select_related('proposal__piece').order_by('-started_at')[:12]
    for execution in executions:
        piece=execution.proposal.piece
        metric=piece.post_metrics.order_by('-captured_at').first()
        pieces.append({'id':'piece:'+str(piece.id),'text':piece.final_text,'published_at':execution.started_at,
            'url':(metric.share_url if metric else '') or execution.external_url,
            'metrics':{key:getattr(metric,key) for key in ('impressions','reactions','comments','reposts','captured_at')} if metric else {},
            'signals':piece.signals})
    return orquestacion.plain({'public_facts':public,'private_guidance':private,'recent_pieces':pieces,
        'section_ids':list(content.MONTHLY if mode=='monthly' else content.SECTIONS),'mode':mode,
        'brand_version':content.BRAND_VERSION})


def _job(proposal):
    job,_=enqueue_operation(proposal.owner,'prepare_profile',{'proposal':str(proposal.id),'version':proposal.version},
        request_id=uuid.uuid5(NS,f'{proposal.id}:v{proposal.version}'))
    return job


@transaction.atomic
def queue(user,trigger,mode='full',key=None):
    # Serialize enqueue/dedup for this owner, including concurrent capture and scheduled triggers.
    get_user_model().objects.select_for_update().get(pk=user.pk)
    key=key or f'capture:{trigger["capture"]}'
    old=ProfileProposal.objects.filter(owner=user,key=key).first()
    if not old and trigger.get('capture'):
        old=ProfileProposal.objects.filter(owner=user,triggers__contains=[trigger]).first()
    if old:return old
    refs=gallery.references(user)
    active=ProfileProposal.objects.filter(owner=user,mode=mode,state__in=['queued','running']).first()
    if active and active.references==refs:
        if trigger not in active.triggers:active.triggers.append(trigger);active.save(update_fields=['triggers','updated_at'])
        return active
    proposal=ProfileProposal.objects.create(owner=user,key=key,mode=mode,triggers=[trigger],references=refs)
    _job(proposal)
    return proposal


def add_months(day,n):
    value=day.year*12+day.month-1+n;year,month=divmod(value,12);month+=1
    return day.replace(year=year,month=month,day=min(day.day,calendar.monthrange(year,month)[1]))


@transaction.atomic
def schedule(user,now=None):
    if os.environ.get('PROFILE_ENABLED','false').lower()!='true':return 0
    username=os.environ.get('PROFILE_OWNER_USERNAME','').strip()
    if not username:return 0
    user=get_user_model().objects.filter(username=username,is_active=True).first()
    if user is None:return 0
    from .operador import local_tz
    day=(now or timezone.now()).astimezone(local_tz()).date();month=day.strftime('%Y-%m')
    get_user_model().objects.select_for_update().get(pk=user.pk)
    row,_=ProfileSchedule.objects.get_or_create(owner=user,defaults={'anchor':day})
    months=(day.year-row.anchor.year)*12+day.month-row.anchor.month
    period=max(0,months//6)
    if add_months(row.anchor,period*6)>day:period=max(0,period-1)
    full=add_months(row.anchor,period*6).isoformat()
    if row.full_period!=full:
        queue(user,{'scheduled':'full','period':full},key=f'scheduled:{user.pk}:full:{full}')
        row.full_period=full;row.monthly_period=month;row.save();return 1
    if row.monthly_period!=month:
        # A full on-demand proposal in this month already covers monthly sections.
        full_row=ProfileProposal.objects.filter(owner=user,mode='full',created_at__year=day.year,
            created_at__month=day.month).exclude(state__in=['cancelled','superseded']).first()
        if full_row:
            trigger={'scheduled':'monthly','period':month}
            if trigger not in full_row.triggers:full_row.triggers.append(trigger);full_row.save()
        else:queue(user,{'scheduled':'monthly','period':month},mode='monthly',key=f'scheduled:{user.pk}:monthly:{month}')
        row.monthly_period=month;row.save();return int(full_row is None)
    return 0


def capture_request(capture,user,text):
    proposal=queue(user,{'capture':str(capture.id)})
    return ({'proposal':str(proposal.id)}, {'kind':'perfil','text':'Perfil está preparando tu propuesta',
        'link':f'/tu-turno#turno-perfil:{proposal.id}'},Capture.State.NOTED,'perfil')


@transaction.atomic
def withdraw_capture(capture):
    proposal=ProfileProposal.objects.select_for_update().filter(pk=capture.routed_to.get('proposal')).first()
    if not proposal:return
    proposal.triggers=[t for t in proposal.triggers if t.get('capture')!=str(capture.id)]
    if not proposal.triggers:
        proposal.state='cancelled'
        Job.objects.filter(kind='prepare_profile',params__proposal=str(proposal.id),state='queued').update(state='cancelled',finished_at=timezone.now())
        if proposal.cycle_id:
            runtime=orquestacion.Runtime(proposal.cycle,orquestacion.load_graph());runtime.stop('cancelled',business=False)
    proposal.save()


def _persist(proposal,**fields):
    # Never resurrect cancelled requests while a provider call was in flight.
    if not ProfileProposal.objects.filter(pk=proposal.pk).exclude(state='cancelled').update(**fields,updated_at=timezone.now()):
        raise orquestacion.CycleStopped('cancelled')
    for k,v in fields.items():setattr(proposal,k,v)


def save_asset(proposal,kind,raw,review,provenance):
    existing=proposal.assets.filter(version=proposal.version,kind=kind).first()
    if existing:return existing
    with Image.open(io.BytesIO(raw)) as im:width,height=im.size
    row=ProfileAsset(proposal=proposal,version=proposal.version,kind=kind,sha256=imagenes.sha(raw),width=width,height=height,
        review=review,provenance=provenance)
    row.image.save(kind+'.png',ContentFile(raw),save=False);row.save()
    return row


def assets(proposal,runtime,banner,client=None,checker=None):
    client=client or imagenes.connector.ImageConnector();checker=checker or visual.check
    gallery.roles(proposal.references)
    refs=gallery.raw_references(proposal.references,proposal.owner)
    edits={};provenance={'references':proposal.references,'brand_version':content.BRAND_VERSION,'base_prompt':visual.BASE_PROMPT,
        'model':imagenes.connector.EDIT_MODEL,'effective_prompts':{}}
    for kind in ('A','B','banner'):
        scoped=[r for r in proposal.references if r['role'] in (('01','03') if kind!='banner' else ('01','02','03'))]
        instruction=visual.prompt(kind,scoped,proposal.context.get('adjustment',''));provenance['effective_prompts'][kind]=instruction
        request={'proposal':str(proposal.id),'kind':kind,'references':scoped,'instruction':instruction}
        # Keys include input fingerprint: same edits are reused across copy revisions, never paid twice on retry.
        edits[kind]=runtime.call('perfil_editar_persona',request,
            lambda:client.edit_profile({r['role']:refs[r['role']] for r in scoped},instruction,f'{proposal.id}:{kind}'),
            key='person:'+orquestacion.digest(request))
    render_input={'sha256':{k:imagenes.sha(v) for k,v in edits.items()},'copy':banner,'brand':content.BRAND_VERSION}
    package=runtime.call('perfil_render',render_input,lambda:visual.render_tool(edits,banner),key='render:'+orquestacion.digest(render_input))
    files={kind:orquestacion.unpack(blob) for kind,blob in package['files'].items()};reviews={}
    for option in ('A','B'):
        selected={key:files[key] for key in (option,'banner',f'mobile_{option}',f'desktop_{option}')}
        context={'option':option,'geometry':package['geometry'],'copy':banner,
                 'library':[u for u in proposal.context.get('library',{}).get('units',[]) if u['unit_id'] in content.PROFILE_VISUAL_UNITS]}
        request={'hashes':{k:imagenes.sha(v) for k,v in selected.items()},'references':proposal.references,'context':context}
        review=runtime.call('perfil_revision_visual',request,lambda:checker(selected,refs,context),key='vision:'+orquestacion.digest(request))
        if not review.get('ok') or review.get('sha256')!=[imagenes.sha(v) for v in selected.values()]:
            raise ValueError('Revisión visual bloqueada o incierta: '+option)
        reviews[option]=review
    if gallery.stale(proposal.references,proposal.owner):raise ValueError('Referencias cambiadas durante la edición')
    provenance['geometry']=package['geometry']
    for kind,raw in files.items():save_asset(proposal,kind,raw,{'ok':True,'options':reviews,'sha256':[imagenes.sha(raw)]},provenance)


def run(job,*,library=None,positioning=None,drafter=None,reviewer=None,reader=None,researcher=None,image_client=None,image_checker=None):
    proposal=ProfileProposal.objects.get(pk=job.params['proposal'],owner=job.owner)
    if proposal.state in ('cancelled','ready','partial') or proposal.version!=job.params['version']:return proposal
    runtime=orquestacion.Runtime.open('perfil_periodico',str(proposal.id),job.owner,job,
        facts={'proposal':str(proposal.id),'mode':proposal.mode},plan=['biblioteca','lecturas','posicionamiento','copy','revisión','assets','Tu turno'])
    _persist(proposal,state='running',cycle_id=runtime.id)
    try:
        with runtime.session():
            prefix=f'v{proposal.version}:'
            previous_context=runtime.snapshot(prefix+'prior',lambda:proposal.context)
            context=runtime.snapshot(prefix+'facts',lambda:facts(proposal.mode))
            affected=previous_context.get('affected',[])
            if affected:context['section_ids']=affected
            context['library']=runtime.call('perfil_biblioteca',{'mode':proposal.mode},lambda:(library or content.library)(proposal.mode),key=prefix+'library')
            context['snapshot']=runtime.call('perfil_lectura',{},reader or read_profile,key=prefix+'read')
            web_request=research.ResearchRequest(key=f'profile:{proposal.id}',public_question=PUBLIC_QUESTION,search=True)
            web=runtime.call('perfil_web',web_request,lambda:(researcher or research.research)(web_request),key='web')
            context['web']=web.to_dict()
            context['references']=proposal.references
            context['adjustment']=previous_context.get('adjustment','')
            _persist(proposal,context=context)
            if not context['library']['units']:
                sections=[content.pending(sid,'Falta fundamento: biblioteca no disponible; reintentar sin cuestionario.') for sid in context['section_ids']]
                banner={}
            else:
                context['positioning']=runtime.call('perfil_posicionamiento',context,
                    lambda:(positioning or content.positioning)(context),key=prefix+'positioning')
                for attempt in range(2):
                    data=runtime.call('perfil_copy',context,lambda:(drafter or content.draft)(context),key=prefix+f'copy:{attempt}')
                    check_context=dict(context,draft=data)
                    verdict=runtime.call('perfil_revision_copy',check_context,lambda:(reviewer or content.review)(check_context),key=prefix+f'review:{attempt}')
                    sections,banner=content.validate(data,context,verdict)
                    if verdict['reference_conflicts']:
                        for row in sections:
                            if row['id'] in ('photo','banner'):row.update(readiness='blocked',issues=verdict['reference_conflicts'],copy='')
                    try:
                        if proposal.mode=='full' and banner and any(s['id']=='banner' and s['readiness']=='ready' for s in sections):
                            visual.banner(None,banner)  # Check exact Ubuntu dimensions BEFORE any paid person edit.
                        break
                    except (ValueError,OSError) as exc:
                        if attempt or proposal.version>1:
                            banner={}
                            for row in sections:
                                if row['id']=='banner':row.update(readiness='blocked',issues=[str(exc)],copy='')
                            break
                        context=dict(context,previous_draft=data,findings=[str(exc)+' Acorta frase/etiqueta manteniendo fuentes y tamaño.'])
            if affected and not {'photo','banner'} & set(affected):banner=previous_context.get('banner',{})
            context['banner']=banner
            # Keep manual history for identical content. A changed section always requires a fresh decision.
            previous={s['id']:s for s in proposal.sections}
            for row in sections:
                old=previous.get(row['id'])
                if old and row['id'] not in ('photo','banner') and all(old.get(k)==row.get(k) for k in ('copy','action','citations','evidence')):
                    for field in ('decision','application','applied_at','applied_text','checked_at','check_evidence','note'):
                        if field in old:row[field]=old[field]
                row['version']=proposal.version
            if affected:
                replacements={s['id']:s for s in sections}
                sections=[replacements.get(s['id'],s) for s in proposal.sections]
                for row in sections:row['version']=proposal.version
            _persist(proposal,sections=sections,context=context)
            from .preguntas import ask
            for row in sections:
                for missing in row.get('missing',[]):
                    ask('perfil',missing['question'],f'{row["title"]}: {missing["purpose"]}',missing['key'],origin=f'perfil:{proposal.id}',suggested_public=True)
            if proposal.mode=='full':
                try:
                    if affected and not {'photo','banner'} & set(affected) and not gallery.stale(proposal.references,proposal.owner):
                        for asset in proposal.assets.filter(version=proposal.version-1):
                            save_asset(proposal,asset.kind,imagenes.read(asset.image),asset.review,asset.provenance)
                    elif not ASSET_KINDS <= set(proposal.assets.filter(version=proposal.version).values_list('kind',flat=True)):
                        visual_rows=[r for r in sections if r['id'] in ('photo','banner')]
                        if not banner or any(r['readiness']!='ready' for r in visual_rows):raise ValueError('Falta fundamento o copy del banner; assets pendientes.')
                        assets(proposal,runtime,banner,image_client,image_checker)
                except (ValueError,OSError) as exc:
                    for row in sections:
                        if row['id'] in ('photo','banner'):row.update(readiness='blocked',issues=[str(exc)],copy='')
            reconcile_previous(proposal,sections)
            _persist(proposal,sections=sections,state='partial' if any(s['readiness']=='blocked' for s in sections) else 'ready')
            runtime.finish({'proposal':str(proposal.id),'version':proposal.version,'state':proposal.state})
    except (orquestacion.CycleStopped,ValueError,OSError) as exc:
        proposal.refresh_from_db()
        if proposal.state!='cancelled':
            if proposal.mode=='full' and not ASSET_KINDS <= set(proposal.assets.filter(version=proposal.version).values_list('kind',flat=True)):
                for row in proposal.sections:
                    if row['id'] in ('photo','banner'):row.update(readiness='blocked',copy='',issues=['Assets incompletos: '+str(exc)])
            _persist(proposal,state='stopped',sections=proposal.sections,findings=[str(exc)])
    notify(proposal)
    return proposal


def notify(proposal):
    if proposal.state=='cancelled':return
    from .notificaciones import avisar
    if no_changes(proposal):
        detail=' · '.join(s['title']+': '+s['reason']+' '+', '.join(c['unit_id'] for c in s['citations']) for s in proposal.sections)
        avisar('profile_reviewed','Revisión mensual del perfil: sin cambios recomendados',detail,
            ref=f'profile:{proposal.id}:v{proposal.version}:{proposal.state}')
    else:
        avisar('profile_task','Tu propuesta de perfil está disponible','Revisa el documento y aplica cada sección cuando decidas.',
            link=f'/tu-turno#turno-perfil:{proposal.id}',ref=f'profile:{proposal.id}:v{proposal.version}:{proposal.state}')
    for trigger in proposal.triggers:
        if trigger.get('capture'):
            Capture.objects.filter(pk=trigger['capture']).exclude(state='deshecha').update(outcome={'kind':'perfil',
                'text':'Propuesta de perfil: '+proposal.state,'link':f'/tu-turno#turno-perfil:{proposal.id}',
                'cycle_id':str(proposal.cycle_id or '')})


def markdown(proposal):
    lines=[f'# Propuesta de perfil · v{proposal.version}',f'\nMarca: {content.BRAND_VERSION}. Ciclo: {proposal.cycle_id or "QA"}.',
        '\nAplicación manual por Gustavo. Aceptar no significa aplicar ni comprobar.',
        '\n'+content.MICROPHONE_NOTE,'\nRetrato elegido: '+(proposal.photo_choice or 'Pendiente: elige A o B.')]
    invalid=gallery.stale(proposal.references,proposal.owner)
    for row in proposal.sections:
        lines+=['',f'## {row["title"]}',f'Acción: {row["action"]}. Estado: {row["readiness"]}.',
                f'Decisión: {row.get("decision","pending")}. Aplicación: {row.get("application","pending")}.']
        if row.get('superseded_by'):lines.append('Sustituida por propuesta: '+row['superseded_by'])
        current=row.get('current')
        lines+=['Actual: '+(f'{current["text"]} — {current["source"]} · {current["at"]}' if current else 'No pudimos leer tu perfil actual'),
                'Audiencia: '+row.get('audience',''),'Utilidad: '+row.get('benefit',''),'Motivo: '+row.get('reason','')]
        for c in row.get('citations',[]):lines.append(f'- [{c["unit_id"]}] {c["reason"]}')
        lines+=['Evidencia: '+', '.join(row.get('evidence',[])),
            'Límite: '+(str(row['limit'])+' · '+row['limit_source'] if row.get('limit') else 'Pendiente de comprobar')]
        if row.get('copy') and not row.get('superseded_by') and row['readiness']=='ready' and not (invalid and row['id'] in ('photo','banner')):
            lines+=['\nCopy público (English):','```text',row['copy'],'```']
        lines+=['- '+s for s in row.get('steps',[])]
        lines+=['Pendiente: '+s for s in row.get('issues',[])]
        for missing in row.get('missing',[]):lines.append('Falta información: '+missing['question'])
        if row.get('applied_text'):lines+=['Texto aplicado por Gustavo:',row['applied_text']]
    if invalid:lines+=['\nReferencias revocadas o cambiadas: revisa los assets antes de aplicarlos.']
    else:
        for asset in proposal.assets.filter(version=proposal.version):
            lines.append(f'\n[{asset.kind}](/api/v1/perfil/{proposal.id}/assets/{asset.id}) · SHA-256 {asset.sha256}')
    return '\n'.join(lines)+'\n'


def no_changes(proposal):
    return (proposal.mode=='monthly' and bool(proposal.sections) and
        all(s['readiness']=='ready' and s['action'] in ('keep','not_applicable') for s in proposal.sections))


def editorial_guidance():
    """Accepted activity suggestions are data for the next brief, never a scheduled publication."""
    result=[]
    for p in ProfileProposal.objects.filter(state__in=['ready','partial'],updated_at__gte=timezone.now()-timedelta(days=35))[:12]:
        for row in p.sections:
            if (row['id']=='activity' and row['readiness']=='ready' and row['decision']=='accepted'
                    and row['copy'] and not row.get('superseded_by')):
                result.append({'proposal':str(p.id),'version':p.version,'text':row['copy'],
                    'citations':row['citations'],'evidence':row['evidence']})
    return result[:3]


def cards(user,card,postponed=False):
    rows=ProfileProposal.objects.exclude(state__in=['cancelled','superseded']).filter(owner=user)
    result=[]
    for proposal in rows.order_by('-created_at')[:12]:
        if no_changes(proposal):continue
        is_postponed=bool(proposal.postponed_until and proposal.postponed_until>timezone.now())
        if is_postponed!=postponed:continue
        if proposal.sections and all(s.get('superseded_by') or s.get('decision')=='declined' or s.get('application')=='checked' or
            s.get('application')=='applied' and s['id']!='headline' or
            s['action'] in ('keep','not_applicable') and s.get('decision')=='accepted' for s in proposal.sections):continue
        result.append(card(f'perfil:{proposal.id}','perfil','Propuesta de perfil'+(' · mensual' if proposal.mode=='monthly' else ''),
            'Cambios por sección. Tú decides y los aplicas en LinkedIn.',[],agent='perfil',priority='cuando_puedas',
            created_at=proposal.created_at,profile_id=str(proposal.id),
            **({'state_override':'pospuesta','postponed_until':proposal.postponed_until} if postponed else {})))
    return result


@transaction.atomic
def reconcile_previous(proposal,sections):
    """Replace overlapping pending tasks visibly, retaining applied decisions and earlier documents."""
    current={s['id']:s for s in sections}
    for previous in ProfileProposal.objects.select_for_update().filter(owner=proposal.owner,state__in=['ready','partial']).exclude(pk=proposal.pk):
        changed=False
        for row in previous.sections:
            replacement=current.get(row['id'])
            if not replacement or row.get('superseded_by'):continue
            if (row['id'] not in ('photo','banner') and row.get('application') in ('applied','checked')
                    and all(row.get(k)==replacement.get(k) for k in ('copy','action','citations','evidence'))):
                for field in ('decision','application','applied_at','applied_text','checked_at','check_evidence'):
                    if field in row:replacement[field]=row[field]
            row['superseded_by']=str(proposal.id);changed=True
        if changed:previous.revision+=1;previous.save()


def fact_answered(memory_key):
    """A confirmed answer can use the remaining round; only dependent sections change."""
    from .perfil_views import revise
    from .exceptions import Conflict
    for proposal in ProfileProposal.objects.filter(state__in=['ready','partial']):
        affected=[s['id'] for s in proposal.sections if not s.get('superseded_by') and
                  any(m['key']==memory_key for m in s.get('missing',[]))]
        if not affected:continue
        with transaction.atomic():
            proposal=ProfileProposal.objects.select_for_update().get(pk=proposal.pk)
            try:revise(proposal,'Hecho respondido en Tu turno: '+memory_key,affected=affected)
            except Conflict:
                proposal.findings=list(dict.fromkeys(proposal.findings+['Dato recibido; hace falta revisión del ciclo para incorporarlo.']))
                proposal.save(update_fields=['findings','updated_at'])
