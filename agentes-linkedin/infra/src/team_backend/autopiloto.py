"""Autopilot: the operator cycle running as an autonomous machine.

Decision by Gustavo (2026-11-06): «todo debe funcionar como una máquina autónoma».
Agents' proposals are approved by policy after automatic content checks instead of
waiting for a human; Gustavo stays on the loop (pause, reject, resolve, configure).
Each tick only enqueues work; the worker performs provider calls with the operator's
gates (kill switch, account pause, window, spacing, daily/weekly caps, exactly-once).
"""
import hashlib
import logging
import os
import re
import uuid
from collections import Counter
from datetime import timedelta
from decimal import Decimal
from django.db.models import Case, Count, Q, When
from django.utils import timezone
from knowledge import db, memory
from . import guardas, idioma, lider, oficina_eventos, operador, red
from .jobs import enqueue_operation
from .models import ActionExecution, ActionProposal, AuditEvent, ConnectorAccount, Contact, CycleLedger, EditorialPiece, Job, ObservedPost

logger=logging.getLogger('team_backend.autopilot')

POLICY_VERSION='autonomia-v1'
TICK_NAMESPACE=uuid.UUID('0b7f2c3e-1d7a-4c55-8f0e-2a6b9d4e8c31')
# Signals of a pitch, contact request or self-promotion. Comments must contribute, not sell.
PITCH=re.compile(r'projectapp|hire me|dm me|message me|contact me|book a call|schedule a call|my services|our services|'
                 r'link in (?:bio|comments)|reach out to me|contr[aá]tame|escr[ií]beme|agenda(?:mos)? una llamada|'
                 r'nuestros servicios|mis servicios|cont[aá]ctame',re.I)
URL=re.compile(r'https?://|www\.|\b[\w-]+\.(?:com|io|co|ai|dev|app)\b',re.I)
EMAIL=re.compile(r'[\w.+-]+@[\w-]+\.[\w.]+')
PHONE=re.compile(r'(?:\+?\d[\s().-]?){7,}')
HASHTAG=re.compile(r'(?<!\w)#\w')
# Own posts may name ProjectApp (modality projectapp); what they may not do is sell aggressively or ask for contact.
# Two halves (compuertas.pitch): hard selling never passes; a conversational call to action passes only within the piece's
# gate policy (cta_max, default 0). POST_PITCH is both, as before.
_POST_CTA=r'dm me|message me|contact me|reach out to me|send me a (?:dm|message)|escr[ií]beme|cont[aá]ctame'
_POST_SELL=(r'hire me|book a call|schedule a call|link in (?:bio|comments)|limited (?:spots|offer)|sign up now|buy now|'
            r'contr[aá]tame|agenda(?:mos)? una llamada')
POST_CTA=re.compile(_POST_CTA,re.I)
POST_SELL=re.compile(_POST_SELL,re.I)
POST_PITCH=re.compile(_POST_SELL+'|'+_POST_CTA,re.I)
POST_LENGTH=(200,2200)
POST_MAX_HASHTAGS=3

def setting(name,default):
    return os.environ.get(name,default)

# Capabilities that existed when Gustavo chose the autonomous machine default to auto; any newer capability
# (the network block RED-*) waits for human approval until OPERATOR_AUTONOMY lists it. INT-04 (replies on his own posts)
# is autonomous from the start by his decision (12/11/2026), with the lead as its gate.
AUTO_BY_DEFAULT=('INT-03','INT-04','INT-02','CONT-09')

def autonomy(capability):
    """OPERATOR_AUTONOMY='INT-03=auto,RED-01=approval'; modes auto | approval | off."""
    for item in filter(None,setting('OPERATOR_AUTONOMY','').split(',')):
        key,_,mode=item.partition('=')
        if key.strip()==capability and mode.strip() in ('auto','approval','off'):return mode.strip()
    return 'auto' if capability in AUTO_BY_DEFAULT else 'approval'

def enabled():
    return setting('OPERATOR_AUTOPILOT','false').lower()=='true'

def post_issues(proposal):
    """CONT-09: deterministic rules plus the mandatory verifier verdict on this exact text."""
    from . import compuertas
    text=proposal.payload.get('text','')
    issues=compuertas.form_rules(text,compuertas.gate_policy(proposal.piece if proposal.piece_id else None))
    public,private=guardas.blocks()
    issues+=guardas.private_leaks(text,private)+guardas.invented_experience(text,public)
    verification=proposal.piece.verification if proposal.piece_id else {}
    if (verification.get('override') or {}).get('text_sha256')==hashlib.sha256(text.encode()).hexdigest():
        # EDI-23: Gustavo dismissed the block of this exact text: only what LinkedIn needs remains (length, image).
        from . import imagenes
        return [i for i in issues if i.startswith('Longitud')]+imagenes.issues(proposal.piece,proposal.payload.get('media'))
    if verification.get('verdict')!='ready_for_execution':issues.append('Sin veredicto ready_for_execution del verificador')
    elif verification.get('text_sha256')!=hashlib.sha256(text.encode()).hexdigest():
        issues.append('El veredicto del verificador no corresponde a este texto exacto')
    if any(str(r).startswith('Afirmación por verificar') for r in proposal.risks):issues.append('Incluye afirmaciones sin evidencia')
    if proposal.source=='agent' and not proposal.citations:issues.append('Sin fundamento citado del curso')
    from . import imagenes
    issues+=imagenes.issues(proposal.piece,proposal.payload.get('media'))
    return issues

def content_issues(proposal):
    """Deterministic gate replacing per-piece human approval. Returns reasons to discard."""
    if proposal.capability==ActionProposal.Capability.PUBLISH:return post_issues(proposal)
    if proposal.contact_id:return red.network_issues(proposal)
    if proposal.comment_id:
        from . import respuestas
        return respuestas.content_issues(proposal)
    if proposal.capability!=ActionProposal.Capability.COMMENT:return []
    return comment_text_issues(proposal)+comment_author_issues(proposal)

def comment_text_issues(proposal):
    """INT-03 rules about the text itself: the ones a redraft can fix (operador.propose_comment asks for one)."""
    text=proposal.payload.get('text','');issues=[]
    if not 40<=len(text)<=900:issues.append('Longitud fuera de 40–900 caracteres')
    for pattern,reason in ((PITCH,'Contiene pitch o petición de contacto'),(URL,'Contiene enlaces'),(EMAIL,'Contiene un correo'),
                           (PHONE,'Contiene un número de teléfono'),(HASHTAG,'Contiene hashtags')):
        if pattern.search(text):issues.append(reason)
    if any(str(r).startswith('Afirmación por verificar') for r in proposal.risks):issues.append('Incluye afirmaciones sin evidencia')
    if proposal.source=='agent' and not proposal.citations:issues.append('Sin fundamento citado del curso')
    if proposal.source=='agent' and proposal.post_id and idioma.english_on_spanish(text,proposal.post.text):
        issues.append('Está en inglés y la publicación está en español')  # Gustavo, 2026-11-12
    public,private=guardas.blocks()
    return issues+guardas.private_leaks(text,private)+guardas.invented_experience(text,public)

def comment_author_issues(proposal):
    """INT-03 rule about the target, which no redraft can fix: one comment per referent within the cooldown."""
    if proposal.post and proposal.post.referent_id and proposal.post.referent_id in recent_comment_authors(
            proposal.account,timezone.now(),states=['approved','executing','sent','confirmed','uncertain'],exclude=proposal.pk):
        return [f'Ya hay un comentario para {proposal.post.author_name} en las últimas {int(author_cooldown().total_seconds()//3600)} h']
    return []

def policy_review(proposal,lead_budget=None):
    """Approve or discard a pending proposal according to the autonomy policy. `lead_budget` ({'left': n, 'deferred': 0},
    from tick) caps the lead's reviews: once spent, a proposal that needs the lead stays pending for a later tick."""
    from .orquestacion import cycle_issues
    if cycle_issues(proposal):return proposal
    mode=autonomy(proposal.capability)
    if mode=='approval':return proposal
    issues=['Capacidad desactivada por configuración'] if mode=='off' else content_issues(proposal)
    if proposal.capability==ActionProposal.Capability.PUBLISH and issues and set(issues)<={'Imagen no disponible','Documento no disponible'}:
        logger.warning('Propuesta %s pendiente por archivos no disponibles: %s',proposal.id,'; '.join(issues))
        return proposal
    verdict=None
    # Gustavo said this person fits after a doubt of the lead: his word replaces the lead's review for them.
    if not issues and lider.applies(proposal) and not red.confirmed_by_gustavo(proposal):
        # The agente líder replaces the human approval: Jev judges the exact text or person; doubt means no.
        if lider.waiting_retry(proposal):return proposal
        if lead_budget is not None:
            if lead_budget['left']<=0:
                lead_budget['deferred']+=1;return proposal
            lead_budget['left']-=1
        verdict=lider.review(proposal);proposal.review=verdict
        # Jev did not answer: do not wait up to its timeout again for every other proposal of this tick.
        if lead_budget is not None and verdict['decision']=='retry':lead_budget['left']=0
        operador._audit(None,'operator.lead_reviewed',proposal.id,decision=verdict['decision'],answers=verdict.get('answers'))
        oficina_eventos.lead_reviewed(proposal.capability,verdict['decision'])
        if verdict['decision']=='retry':
            proposal.save(update_fields=['review']);return proposal
        issues=verdict['reasons']
    proposal.decided_at=timezone.now()
    if issues:
        proposal.state=ActionProposal.State.DISCARDED;proposal.risks=list(proposal.risks)+issues
        proposal.decision_note=f'Descartada por el líder ({verdict["model"]})' if verdict else f'Descartada por política {POLICY_VERSION}'
        proposal.save(update_fields=['state','risks','decided_at','decision_note','review'])
        operador._audit(None,'operator.policy_discarded',proposal.id,issues=issues)
        if verdict and verdict['decision']=='discard':red.on_lead_discard(proposal)
        if proposal.piece_id:
            from . import capturas
            capturas.release_ideas(proposal.piece,'la política no la aprobó')
            from .notificaciones import avisar
            avisar('piece_discarded',f'La política no aprobó la pieza del {proposal.piece.slot_date:%d/%m}','; '.join(issues)[:300],
                   link=f'/calendario/pieza/{proposal.piece_id}',ref=f'piece_discarded:{proposal.id}')
        return proposal
    if proposal.payload_hash!=operador.current_hash(proposal):
        proposal.state=ActionProposal.State.DISCARDED;proposal.decision_note='Hash inconsistente; descartada'
        proposal.save(update_fields=['state','decided_at','decision_note'])
        if proposal.piece_id:
            from . import capturas
            capturas.release_ideas(proposal.piece,'se descartó por un cambio en el texto')
        return proposal
    proposal.state=ActionProposal.State.APPROVED;proposal.approved_hash=proposal.payload_hash
    proposal.decision_note=(f'Aprobada por el líder ({verdict["model"]}) · política {POLICY_VERSION}' if verdict
                            else f'Aprobada por política {POLICY_VERSION}')
    proposal.save(update_fields=['state','approved_hash','decided_at','decision_note','review'])
    operador._audit(None,'operator.policy_approved',proposal.id,payload_hash=proposal.payload_hash)
    if proposal.piece_id:
        when=proposal.piece.scheduled_for.astimezone(operador.local_tz())
        from .notificaciones import avisar
        avisar('piece_scheduled',f'La pieza del {when:%d/%m} está lista',f'Sale a las {when:%H:%M}. Puedes vetarla en el detalle hasta esa hora.',
               link=f'/calendario/pieza/{proposal.piece_id}',ref=f'piece_scheduled:{proposal.id}')
    return proposal

def llm_spent_today(now=None,purpose='propose-comment'):
    """Today's Claude spend (settled cost or pending reservation) for a ledger purpose; LIKE pattern allowed."""
    day,_=operador.period_starts(now)
    with db.connect() as c:
        row=c.execute('''SELECT coalesce(sum(CASE WHEN status='complete' THEN actual_usd WHEN status IN ('reserved','uncertain')
            THEN reserved_usd ELSE 0 END),0) AS spent FROM usage_ledger WHERE provider='anthropic' AND purpose LIKE %s
            AND created_at>=%s''',(purpose,day)).fetchone()
    return Decimal(row['spent'])

def lead_reviews_per_tick():
    return max(int(setting('LEAD_MAX_REVIEWS_PER_TICK','5')),0)

# --------------------------------------------------------------------------- the lead's silent inaction

_silence_checked_at=None  # in-process throttle; the alert itself is deduplicated durably by Notification.ref
ACTIVITY_TYPE={'INT-03':'comentarios','INT-04':'comentarios','INT-02':'reacciones','CONT-09':'publicaciones'}

def _lead_silence_due(now):
    global _silence_checked_at
    if _silence_checked_at is not None and abs(now-_silence_checked_at)<_every('LEAD_SILENCE_CHECK_MINUTES','60'):return False
    _silence_checked_at=now;return True

def _failing_checks(reviews):
    failing=Counter()
    for review in reviews:
        answers=review.get('answers') or {}
        for qid,(bound,threshold) in (review.get('thresholds') or {}).items():
            value=answers.get(qid)
            if value is None or (bound=='min' and value<threshold) or (bound=='max' and value>threshold):failing[qid]+=1
    return failing

def lead_silence(now=None):
    """The lead can only discard, so it fails by silent inaction. For each capability it reviews in `auto`: if over the last
    7 days it reviewed at least LEAD_SILENCE_MIN_REVIEWS proposals and approved none, notify once per capability and week."""
    if not lider.enabled():return 0
    now=now or timezone.now();minimum=int(setting('LEAD_SILENCE_MIN_REVIEWS','5'));sent=0
    year,week,_=now.astimezone(operador.local_tz()).isocalendar()
    from .notificaciones import avisar
    for capability in lider.capabilities():
        if autonomy(capability)!='auto':continue
        reviewed=ActionProposal.objects.filter(capability=capability,decided_at__gte=now-timedelta(days=7),
                                               review__decision__in=['approve','discard'])
        total=reviewed.count()
        if total<max(minimum,1) or reviewed.filter(review__decision='approve').exists():continue
        top=', '.join(f'{qid} ({n})' for qid,n in _failing_checks(reviewed.values_list('review',flat=True)).most_common(3))
        label=ActionProposal.Capability(capability).label if capability in ActionProposal.Capability.values else capability
        created=avisar('lead_silent',f'El líder no aprobó nada de {capability} en 7 días',
                       f'{label}: revisó {total} propuestas y descartó todas.'+(f' Lo que más falla: {top}.' if top else '')+
                       ' Revisa los umbrales del líder, la orientación o lo que proponen los agentes.',
                       link=f'/calendario?vista=lista&tipo={ACTIVITY_TYPE.get(capability,"red")}&no_salio=1',
                       ref=f'lead_silent:{capability}:{year}-W{week:02d}')
        sent+=int(created is not None)
    return sent

def _job_id(*parts):
    return uuid.uuid5(TICK_NAMESPACE,':'.join(str(p) for p in parts))

def _pending(kind,**params):
    return Job.objects.filter(kind=kind,state__in=[Job.State.QUEUED,Job.State.RUNNING],
                              **{f'params__{k}':v for k,v in params.items()}).exists()

def tick(user,now=None):
    """One autonomous cycle. Idempotent: deterministic job ids prevent duplicate work."""
    now=now or timezone.now();report={'expired':0,'reviewed':0,'observe':0,'propose':0,'execute':0,'reconcile':0}
    from .connectors_linkedin import check_tokens
    report['linkedin_token']=check_tokens(now)  # expiry alerts reach Gustavo even with the machine stopped
    if operador.check_env_pause():report['env_paused_alert']=1  # the server stop pushes once per stop
    from . import comunidad, referentes
    try:referentes.tick(user,now)
    except Exception as exc:report['referents_error']=type(exc).__name__
    comunidad.maintain(now)  # retention also runs when collection/the machine is paused
    if operador.globally_paused():return dict(report,stopped='OPERATOR_PAUSED')
    stopped={(cycle,key):reason for cycle,key,reason in CycleLedger.objects.filter(state='stopped').exclude(
        stop_reason='cost_cap').values_list('cycle','key','stop_reason')}
    for proposal in ActionProposal.objects.select_related('piece').filter(state__in=['proposed','approved'],execution__isnull=True):
        if not proposal.piece_id and not proposal.origin_job:continue
        key=('pieza_diaria',str(proposal.piece_id)) if proposal.piece_id else ('red',proposal.origin_job)
        if key not in stopped:continue
        proposal.state=ActionProposal.State.EXPIRED;proposal.decision_note='Ciclo detenido: '+stopped[key]
        proposal.save(update_fields=['state','decision_note'])
        operador._audit(None,'operator.expired',proposal.id)
        if proposal.piece_id:
            from .capturas import release_ideas
            release_ideas(proposal.piece,proposal.decision_note)
        report['expired']+=1
    ttl=timedelta(hours=int(setting('OPERATOR_PROPOSAL_TTL_HOURS','48')))
    # Own pieces are prepared ahead of time: their TTL runs from the scheduled hour, not from creation.
    stale=ActionProposal.objects.filter(state__in=['proposed','approved'],execution__isnull=True).filter(
        Q(piece__isnull=True,created_at__lt=now-ttl)|Q(piece__isnull=False,piece__scheduled_for__lt=now-ttl))
    for proposal in stale:
        operador._audit(None,'operator.expired',proposal.id)
        if proposal.piece_id:
            from .capturas import release_ideas
            release_ideas(proposal.piece,'caducó sin publicar')
    report['expired']+=stale.update(state=ActionProposal.State.EXPIRED,decision_note='Caducada sin ejecutar')
    # The lead (Jev, up to 60 s per call) reviews at most LEAD_MAX_REVIEWS_PER_TICK proposals per tick, oldest first; after
    # a plan_network the rest wait for the next ticks instead of blocking this one for minutes.
    lead_budget={'left':lead_reviews_per_tick(),'deferred':0}
    for proposal in ActionProposal.objects.select_related('post','piece','contact').filter(state=ActionProposal.State.PROPOSED).order_by('created_at'):
        policy_review(proposal,lead_budget);report['reviewed']+=1
    if lead_budget['deferred']:report['lead_deferred']=lead_budget['deferred']
    if _lead_silence_due(now):
        report['lead_silent']=lead_silence(now)
        try:
            from . import auditoria_compuertas
            report['gate_alerts']=auditoria_compuertas.vigilar(now)
        except Exception as exc:report['gate_alerts_error']=type(exc).__name__  # the audit never stops the tick
    try:report['plan']=_editorial(user,now)
    except ValueError as exc:report.update(plan=0,editorial_error=str(exc))  # misconfigured editorial never stops the rest
    for account in ConnectorAccount.objects.filter(paused=False):
        try:report['community_study']=report.get('community_study',0)+comunidad.schedule(user,account,now)
        except Exception as exc:report['community_error']=type(exc).__name__
        report['observe']+=_observe(user,account,now)
        redrafted=_lead_redraft(user,account,now)  # before a new draft: it holds the one draft at a time
        if redrafted:report['lead_redraft']=report.get('lead_redraft',0)+redrafted
        report['propose']+=_propose(user,account,now)
        report['network']=report.get('network',0)+_network(user,account,now)
        try:report['metrics']=report.get('metrics',0)+_metrics(user,account,now)
        except Exception as exc:report['metrics_error']=type(exc).__name__  # metrics never stop the rest of the tick
        try:report['analytics']=report.get('analytics',0)+_analytics(user,account,now)
        except Exception as exc:report['analytics_error']=type(exc).__name__  # analytics never stop the rest of the tick
        try:report['canary']=report.get('canary',0)+_canary(user,account,now)
        except Exception as exc:report['canary_error']=type(exc).__name__  # the canary never stops the rest of the tick
        try:report['inbox']=report.get('inbox',0)+_inbox(user,account,now)
        except Exception as exc:report['inbox_error']=type(exc).__name__  # the inbox never stops the rest of the tick
        try:report['replies']=report.get('replies',0)+_replies(user,account,now)
        except Exception as exc:report['replies_error']=type(exc).__name__  # replies never stop the rest of the tick
        report['execute']+=_execute(user,account,now)
    report['reconcile']+=_reconcile(user,now)
    try:
        from .perfil import schedule
        report['profile']=schedule(user,now)
    except Exception as exc:report['profile_error']=type(exc).__name__
    try:
        from . import urgente
        report['day_requests']=urgente.tick_day_requests(now)
    except Exception as exc:report['day_requests_error']=type(exc).__name__  # never stops the rest of the tick
    try:report['weekly_summary']=_weekly_summary(user,now)
    except Exception as exc:report['weekly_summary_error']=type(exc).__name__  # the weekly summary never stops the rest
    try:
        from . import estrategia
        report['weekly_plan']=estrategia.queue(user,now)  # Sunday afternoon: next week's GASP plan, once
    except Exception as exc:report['weekly_plan_error']=type(exc).__name__  # the plan never stops the rest
    return report

def _editorial(user,now):
    """CONT-07: queue the preparation of the next slot (EDITORIAL_POST_TIME, EDITORIAL_LEAD_HOURS ahead), one at a time,
    within the editorial daily budget and the CONT-09 caps. Each slot gets one automatic attempt at most."""
    from . import editorial, editor_visual
    editorial.recover_stuck()
    editor_visual.upgrade_bindings()  # a still valid v1 visual package stops depending on his confirmed facts
    if autonomy('CONT-09')=='off' or _pending('prepare_piece'):return 0
    account=editorial.publishing_account()
    if not editorial.can_publish(account):return 0
    if not editorial.can_afford_preparation(now):return 0
    from . import urgente
    extra=urgente.next_extra(now)
    if extra:
        # The post he asked for at a day and hour is an order: prepared right away, outside the CONT-09 caps.
        attempt=EditorialPiece.objects.filter(slot_date=extra,second_of_day=True).count()
        _,created=enqueue_operation(user,'prepare_piece',{'slot':extra.isoformat(),'extra':True},
                                    request_id=_job_id('extra',extra) if not attempt else _job_id('extra',extra,attempt))
        return int(created)
    slot=urgente.next_slot(now) or editorial.next_slot(now)
    if slot is None or operador.capacity_left(account,'CONT-09',urgente.reserved_at(slot) or editorial.scheduled_for(slot))<=0:return 0
    attempt=EditorialPiece.objects.filter(slot_date=slot,second_of_day=False).count()  # a renewed-budget retry gets its own job id
    _,created=enqueue_operation(user,'prepare_piece',{'slot':slot.isoformat()},
                                request_id=_job_id('piece',slot) if not attempt else _job_id('piece',slot,attempt))
    return int(created)

def author_cooldown():
    return timedelta(hours=int(setting('OPERATOR_AUTHOR_COOLDOWN_HOURS','48')))

LIVE_COMMENT_STATES=['proposed','approved','executing','sent','confirmed','uncertain']

def recent_comment_authors(account,now,states=LIVE_COMMENT_STATES,exclude=None):
    """Referents who already got (or are about to get) a comment within the cooldown: one person, one comment at a time."""
    qs=ActionProposal.objects.filter(account=account,capability=ActionProposal.Capability.COMMENT,state__in=states,
                                     created_at__gte=now-author_cooldown(),post__referent__isnull=False)
    if exclude:qs=qs.exclude(pk=exclude)
    return set(qs.values_list('post__referent_id',flat=True))

def _observe(user,account,now):
    every=timedelta(minutes=int(setting('OPERATOR_OBSERVE_EVERY_MINUTES','180')))
    last=account.referents.filter(active=True).order_by('last_observed_at').values_list('last_observed_at',flat=True).first()
    if not account.referents.filter(active=True).exists() or (last and last>now-every) or _pending('observe',account=str(account.id)):return 0
    bucket=int(now.timestamp()//every.total_seconds())
    _,created=enqueue_operation(user,'observe',{'account':str(account.id),'limit':5,'referents':[]},request_id=_job_id('observe',account.id,bucket))
    return int(created)

def open_comments(account):
    """Comments already drafted and waiting for their turn (proposed or approved, not executed yet)."""
    return ActionProposal.objects.filter(account=account,capability=ActionProposal.Capability.COMMENT,
                                         state__in=[ActionProposal.State.PROPOSED,ActionProposal.State.APPROVED]).count()

# R5: Jev judges whether a post deserves a comment before Opus is paid to draft one.
PREFILTER_ACTION='operator.comment_prefilter'
PREFILTER_PER_TICK=3  # Jev questions per tick at most (each may wait up to its 60 s timeout)

def prefilter_enabled():
    return lider.enabled() and setting('COMMENT_PREFILTER','true').lower()=='true'

def prefilter_verdicts(since):
    """{post id: 'comment' | 'skip'} remembered from the AuditEvent each judgment leaves (the latest one wins)."""
    rows=AuditEvent.objects.filter(action=PREFILTER_ACTION,created_at__gte=since).order_by('created_at').values_list('target','metadata')
    return {target:meta.get('decision') for target,meta in rows if meta.get('decision') in ('comment','skip')}

def _prefilter(post):
    verdict=lider.comment_worthy(post)
    operador._audit(None,PREFILTER_ACTION,post.id,**verdict)
    if verdict['decision']=='unavailable':
        # Never block drafting on Jev: draft as before the prefilter existed, and leave a trace.
        logger.warning('comment_prefilter_unavailable post=%s %s',post.id,'; '.join(verdict['reasons']))
    return verdict['decision']

def _propose(user,account,now):
    # A paid draft only when a write slot is left after the comments already waiting for one.
    if autonomy('INT-03')=='off' or operador.capacity_left(account,'INT-03',now)-open_comments(account)<=0:return 0
    from knowledge import presupuesto
    if presupuesto.left(now)<=0:return 0
    day,_=operador.period_starts(now)
    drafted=ActionProposal.objects.filter(account=account,capability=ActionProposal.Capability.COMMENT,source='agent',created_at__gte=day).count()
    pending=Job.objects.filter(kind='propose_comment',state__in=[Job.State.QUEUED,Job.State.RUNNING]).count()
    room=int(setting('OPERATOR_DAILY_PROPOSALS','6'))-drafted-pending
    if room<=0 or pending:return 0  # one paid draft at a time keeps spend within the daily cap
    max_age=timedelta(hours=int(setting('OPERATOR_MAX_POST_AGE_HOURS','72')))
    prefilter=prefilter_enabled()
    # A verdict is never older than its post, so verdicts from before the oldest candidate are irrelevant.
    verdicts=prefilter_verdicts(now-max_age-timedelta(days=1)) if prefilter else {}
    candidates=(ObservedPost.objects.filter(account=account,is_repost=False,posted_at__gte=now-max_age,referent__active=True)
                .exclude(text='').exclude(proposals__capability='INT-03').exclude(referent_id__in=recent_comment_authors(account,now))
                .exclude(id__in=[pid for pid,decision in verdicts.items() if decision=='skip']).order_by('-posted_at'))
    from . import experimentos
    focus=experimentos.active_focus(account,now)
    selected=list(candidates[:30])
    if focus:selected.sort(key=lambda post:post.referent_id!=focus.referent_id)
    asked=0
    for post in selected:
        if not experimentos.eligible(post,now):continue
        if prefilter and str(post.id) not in verdicts:
            if asked>=PREFILTER_PER_TICK:return 0  # the next candidates are judged on the next tick
            asked+=1
            if _prefilter(post)=='skip':continue
        _,created=enqueue_operation(user,'propose_comment',{'post':str(post.id)},request_id=_job_id('propose',post.id))
        return int(created)
    return 0

def _lead_redraft(user,account,now):
    """A comment the lead discarded in the last 24 h gets ONE redraft with the lead's reasons (docs/compuertas.md): same
    write slot, budget, daily room and one-draft-at-a-time as _propose. The redraft goes through the rules and the lead
    again; a post that already has two comment drafts is never redrafted."""
    from . import compuertas
    if not compuertas.lead_redraft() or not lider.enabled() or autonomy('INT-03')!='auto':return 0
    if 'INT-03' not in lider.capabilities() or operador.capacity_left(account,'INT-03',now)-open_comments(account)<=0:return 0
    from knowledge import presupuesto
    if presupuesto.left(now)<=0 or Job.objects.filter(kind='propose_comment',state__in=[Job.State.QUEUED,Job.State.RUNNING]).exists():
        return 0
    day,_=operador.period_starts(now)
    drafted=ActionProposal.objects.filter(account=account,capability=ActionProposal.Capability.COMMENT,source='agent',created_at__gte=day).count()
    if int(setting('OPERATOR_DAILY_PROPOSALS','6'))-drafted<=0:return 0
    max_age=timedelta(hours=int(setting('OPERATOR_MAX_POST_AGE_HOURS','72')))
    discarded=(ActionProposal.objects.filter(account=account,capability=ActionProposal.Capability.COMMENT,source='agent',
                                             state=ActionProposal.State.DISCARDED,review__decision='discard',
                                             decided_at__gte=now-timedelta(hours=24),post__posted_at__gte=now-max_age,
                                             post__referent__active=True)
               .exclude(post__referent_id__in=recent_comment_authors(account,now))
               .annotate(drafts=Count('post__proposals',filter=Q(post__proposals__capability='INT-03'))).filter(drafts=1)
               .select_related('post').order_by('-decided_at'))
    from . import experimentos
    for proposal in discarded[:10]:
        if not experimentos.eligible(proposal.post,now):continue
        _,created=enqueue_operation(user,'propose_comment',{'post':str(proposal.post_id),'redraft_of':str(proposal.id)},
                                    request_id=_job_id('redraft',proposal.id))
        if created:return 1
    return 0

def _every(name,default):
    return timedelta(minutes=int(setting(name,default)))

def _network(user,account,now):
    """DESC/RED: queue discovery, classification, planning and sync for the Unipile account, each on its own clock.
    Reads and the cheaper classifier run on their own; follows, invitations and acceptances become proposals."""
    if not red.enabled() or account.provider not in ('unipile','fake','directo'):return 0
    queued=0
    def enqueue(kind,every,condition=True):
        nonlocal queued
        if not condition or _pending(kind,account=str(account.id)):return
        bucket=int(now.timestamp()//every.total_seconds())
        _,created=enqueue_operation(user,kind,{'account':str(account.id)},request_id=_job_id(kind,account.id,bucket))
        queued+=int(created)
    enqueue('discover_network',_every('NETWORK_DISCOVER_EVERY_MINUTES','360'),red.discovery_room(account)>0)  # B4
    unclassified=Contact.objects.filter(account=account,classification={},stage__in=['candidate','incoming']).exists()
    enqueue('classify_contacts',_every('NETWORK_CLASSIFY_EVERY_MINUTES','30'),
            (unclassified or red.stage_pending(account,now)) and red.budget_left(now)>0)
    enqueue('plan_network',_every('NETWORK_PLAN_EVERY_MINUTES','60'))
    enqueue('sync_network',_every('NETWORK_SYNC_EVERY_MINUTES','360'))
    return queued

def _metrics(user,account,now):
    """APRE-01: queue collect_metrics (own posts at 24 h/72 h/7 d, daily audience) about every METRICS_EVERY_MINUTES,
    one at a time and only when something is due, for the Unipile account. METRICS_EVERY_MINUTES=0 turns it off."""
    from . import metricas
    every=_every('METRICS_EVERY_MINUTES','180')
    if account.provider not in metricas.PROVIDERS or every<=timedelta(0) or _pending('collect_metrics',account=str(account.id)):return 0
    if not metricas.due(now):return 0
    bucket=int(now.timestamp()//every.total_seconds())
    _,created=enqueue_operation(user,'collect_metrics',{'account':str(account.id)},request_id=_job_id('metrics',account.id,bucket))
    return int(created)

def _analytics(user,account,now):
    """Creator analytics (analitica.py): queue import_analytics once per UTC day after ANALYTICS_DAILY_AFTER for a
    `directo` account whose navegador service is configured; one job a day, whatever its outcome."""
    from . import analitica
    if _pending('import_analytics',account=str(account.id)) or not analitica.daily_due(account,now):return 0
    day=analitica.utc_today(now)
    _,created=enqueue_operation(user,'import_analytics',{'account':str(account.id)},request_id=_job_id('analytics',account.id,day))
    return int(created)

def _canary(user,account,now):
    """The daily canary (canario.py): queue check_linkedin once per UTC day after LINKEDIN_CANARY_AFTER for a `directo`
    account whose navegador service is configured; a run that could not run is queued again an hour later, up to
    canario.TRIES a day (the attempt number keeps each try's job id apart)."""
    from . import analitica, canario
    if _pending('check_linkedin',account=str(account.id)) or not canario.daily_due(account,now):return 0
    day=analitica.utc_today(now)
    _,created=enqueue_operation(user,'check_linkedin',{'account':str(account.id)},
                                request_id=_job_id('canary',account.id,day,canario.tries(account,now)))
    return int(created)

def _inbox(user,account,now):
    """conversaciones_inbox: queue read_inbox about every INBOX_EVERY_MINUTES, one at a time, for a Unipile account that
    is not paused (the job itself refreshes the status and only reads a running account). Off unless INBOX_ENABLED."""
    from . import conversaciones
    every=conversaciones.every()
    if not conversaciones.enabled() or account.provider not in conversaciones.PROVIDERS or every<=timedelta(0):return 0
    if _pending('read_inbox',account=str(account.id)):return 0
    bucket=int(now.timestamp()//every.total_seconds())
    _,created=enqueue_operation(user,'read_inbox',{'account':str(account.id)},request_id=_job_id('inbox',account.id,bucket))
    return int(created)

def _replies(user,account,now):
    """INT-04: read the comments on his recent own posts when one is due (respuestas.cadence), then one paid draft at a
    time for the oldest comment waiting for one, while the INT-04 caps leave a slot after the replies already waiting."""
    from . import respuestas
    from knowledge import presupuesto
    if not respuestas.enabled() or account.provider not in respuestas.PROVIDERS:return 0
    queued=0
    if respuestas.reading_due(account,now) and not _pending('read_own_comments',account=str(account.id)):
        bucket=int(now.timestamp()//1800)
        _,created=enqueue_operation(user,'read_own_comments',{'account':str(account.id)},request_id=_job_id('replies',account.id,bucket))
        queued+=int(created)
    if _pending('read_own_comments') or _pending('propose_reply'):return queued
    if operador.capacity_left(account,'INT-04',now)-respuestas.open_replies(account)<=0 or presupuesto.left(now)<=0:return queued
    row=respuestas.next_to_draft(account,now)
    if row is None:return queued
    attempt=int((row.decision or {}).get('attempts',0))
    _,created=enqueue_operation(user,'propose_reply',{'comment':str(row.id)},request_id=_job_id('reply',row.id,attempt))
    return queued+int(created)

def _weekly_summary(user,now):
    """analista_barrio_resultados: on Monday after WEEKLY_SUMMARY_TIME, queue the summary of the week that just ended
    (resumen_semanal.queue: one per week, deterministic job id). Off with WEEKLY_SUMMARY_ENABLED=false."""
    from . import resumen_semanal
    return resumen_semanal.queue(user,now)

def _execute(user,account,now):
    from .orquestacion import cycle_issues
    if not operador.within_window(now):return 0
    if _pending('execute_action'):return 0
    rounds=bool(operador.network_batches())
    # Without network rounds every write shares one spacing; with them a network write inside its round waits less.
    # His own post does not wait for the day's opening (operador.spacing_ok).
    due=operador.post_due(now)  # a network action or comment now could push his post past its hour
    # A reply on his own post goes first: the person who commented is waiting, and its window counts from the comment.
    first=Case(When(capability=ActionProposal.Capability.REPLY,then=0),default=1)
    for proposal in ActionProposal.objects.select_related('post','piece','contact','comment').filter(account=account,state='approved',execution__isnull=True).order_by(first,'created_at'):
        if cycle_issues(proposal):continue
        if due and not proposal.piece_id:continue
        if proposal.piece_id and proposal.piece.scheduled_for>now:continue  # an own piece waits for its hour
        if rounds and not proposal.piece_id and operador.batch_issue(proposal.capability,now):continue
        if not operador.spacing_ok(account,now,proposal.capability):continue
        if operador.capped(proposal) and operador.capacity_left(account,proposal.capability,now)<=0:continue
        if not proposal.piece_id and operador.deferred_until(account,proposal.capability,now):continue  # its last write left nothing
        job=operador.enqueue_execution(user,proposal)
        return int(job.state==Job.State.QUEUED)
    return 0

def _reconcile(user,now):
    due=ActionExecution.objects.filter(state__in=['sent','uncertain'],started_at__lt=now-timedelta(minutes=10)).filter(
        Q(reconciled_at__isnull=True)|Q(reconciled_at__lt=now-timedelta(hours=1)))
    count=0
    for execution in due[:3]:
        hour=int(now.timestamp()//3600)
        _,created=enqueue_operation(user,'reconcile_action',{'proposal':str(execution.proposal_id)},request_id=_job_id('reconcile',execution.id,hour))
        count+=int(created)
    return count
