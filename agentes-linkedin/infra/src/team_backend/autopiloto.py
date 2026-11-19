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
from django.db.models import Case, Count, Max, Q, When
from django.db.models.functions import Coalesce
from django.utils import timezone
from knowledge import db, memory
from . import guardas, idioma, lider, miembros, oficina_eventos, operador, red
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
# BIB-09-comentario-calentamiento (LI-07-M001-K04, LI-07-M005-K05): a warm-up comment on a buyer's post is an own
# contribution and one question, 25–40 words, without applause or selling. Fixed rules; the lead judges the rest.
WARMUP_WORDS=(25,40)
WORD=re.compile(r"[^\W_]+(?:['’\-][^\W_]+)*")
APPLAUSE=re.compile(r'great (?:post|read|share|insight|work)|love (?:this|it|how|that)|congrat|amazing (?:post|work|news)|well said|'
                    r'so true|spot on|kudos|excelente (?:post|publicaci[oó]n|aporte)|gran post|felicidades|felicitaciones|'
                    r'enhorabuena|me encant[oó]|👏|🙌|💯|🔥',re.I)
WARMUP_SELL=re.compile(r'our team builds|we help (?:startups|companies|founders|teams)|happy to (?:help|show)|i can help|'
                       r'let me know if you need|podemos ayudar|te ayudamos|te puedo ayudar|con gusto te (?:ayudo|muestro)',re.I)
POST_LENGTH=(200,2200)
POST_MAX_HASHTAGS=3

def setting(name,default):
    return os.environ.get(name,default)

def daily_proposals():
    """Paid comment drafts a day (OPERATOR_DAILY_PROPOSALS). 20 since 17/11/2026: 15 comments a day with the lead
    discarding some need room for their redrafts (docs/plan-outbound.md)."""
    return int(setting('OPERATOR_DAILY_PROPOSALS','20'))

# Capabilities that existed when Gustavo chose the autonomous machine default to auto; any newer capability
# (the network block RED-*) waits for human approval until OPERATOR_AUTONOMY lists it. INT-04 (replies on his own posts)
# is autonomous from the start by his decision (12/11/2026), with the lead as its gate.
AUTO_BY_DEFAULT=('INT-03','INT-04','INT-02','CONT-09')

def autonomy(capability,member=None):
    """OPERATOR_AUTONOMY='INT-03=auto,RED-01=approval'; modes auto | approval | off. The member's own value for a
    capability (miembros.setting) wins over the .env's (organizaciones, phase 2: the CTO starts in «approval» without
    touching Gustavo's). Without a member, the only active one (MiembroRequerido among several).
    While her voice is provisional (voz.current: a member without a confirmed voice, never the first member), her
    editorial autonomy (CONT-09) is «approval» whatever is configured: her posts never go out on their own until she
    confirms her voice (organizaciones, phase 4)."""
    member=operador.member_of(member=member)
    mode=_configured(capability,member)
    if capability in PROVISIONAL_HOLDS and mode=='auto' and provisional_voice(member):return 'approval'
    return mode

# Organizaciones, phase 7: nothing written in a provisional voice goes out without a person, in ANY capability. The
# capabilities that always write a text in her name are held in «approval» while her voice is provisional (phase 4 did it
# for the post); an invitation writes a text only with its note, so RED-02 is held per proposal (provisional_draft).
PROVISIONAL_HOLDS=('CONT-09','INT-03','INT-04')
TEXT_CAPABILITIES=PROVISIONAL_HOLDS+('RED-02',)

def _author(proposal):
    """Whose text a proposal is: its account's member; None for a draft without an account (the evaluation harness), which
    the text checks read as the default member, as always."""
    return operador.member_of(account=proposal.account) if proposal.account_id else None

def provisional_voice(member):
    """Whether her voice is provisional (no confirmed voice and not the installation's first person)."""
    if member is None:return False
    from . import voz
    return voz.current(member).provisional

def writes_text(proposal):
    """Whether the proposal puts a text in her name on LinkedIn: a post, a comment, a reply, or an invitation with a note."""
    return proposal.capability in PROVISIONAL_HOLDS or (proposal.capability=='RED-02' and bool((proposal.payload or {}).get('note')))

def provisional_draft(proposal):
    """A text written in a provisional voice: its own `voice` mark (or its piece's) says provisional, or it carries no mark
    at all (a path that did not record its voice) and its author's voice is provisional now. It never goes out on its own,
    even after she confirms her voice: a person approves it (policy_review leaves it waiting; operador.execute refuses it
    without her approval, voice_hold)."""
    if not writes_text(proposal):return False
    marks=[proposal.voice or {}]+([proposal.piece.voice or {}] if proposal.piece_id else [])
    if any(m.get('tipo')=='provisional' for m in marks):return True
    if any(m.get('tipo') for m in marks):return False  # written with a confirmed (or the initial) voice
    return provisional_voice(_author(proposal))

def approved_by_her(proposal):
    """Whether a person approved this exact version: the user of the member who owns the account (her own approval; the
    policy never sets decided_by). Without members, any human user (the installation's person)."""
    if not proposal.decided_by_id or proposal.approved_hash!=proposal.payload_hash:return False
    owner=_author(proposal)
    if owner is not None:return proposal.decided_by_id==owner.user_id
    return proposal.decided_by.get_username() not in miembros.ROBOTS

def voice_hold(proposal):
    """'' or why an approved proposal may not be written: a provisional-voice text that no person approved."""
    if provisional_draft(proposal) and not approved_by_her(proposal):
        return 'Escrito con la voz provisional: sale solo con la aprobación de su dueña.'
    return ''

def _configured(capability,member):
    own=(member.settings or {}).get('OPERATOR_AUTONOMY','') if member is not None else ''
    for source in (own,setting('OPERATOR_AUTONOMY','')):
        for item in filter(None,source.split(',')):
            key,_,mode=item.partition('=')
            if key.strip()==capability and mode.strip() in ('auto','approval','off'):return mode.strip()
    return 'auto' if capability in AUTO_BY_DEFAULT else 'approval'

def autonomy_of(proposal):
    """The autonomy of a proposal's capability for the member who owns its account."""
    return autonomy(proposal.capability,operador.member_of(account=proposal.account))

def enabled():
    return setting('OPERATOR_AUTOPILOT','false').lower()=='true'

def post_issues(proposal):
    """CONT-09: deterministic rules plus the mandatory verifier verdict on this exact text."""
    from . import compuertas
    text=proposal.payload.get('text','')
    issues=compuertas.form_rules(text,compuertas.gate_policy(proposal.piece if proposal.piece_id else None))
    # Her memory only (phase 4). Of the first-person experience regex only an invented figure about her work is a rule of
    # the post (19/11/2026, editorial.text_rules); the verdict on this exact text, required below, judges the rest.
    issues+=guardas.text_checks(text,_author(proposal),experience='figures')
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
    from . import calentamiento
    if proposal.post_id and calentamiento.warmup_post(proposal.post):
        from . import sin_posts
        issues+=warmup_text_issues(text)+sin_posts.repeat_issues(proposal)  # phase 5: never the same to two of a company
    return issues+guardas.text_checks(text,_author(proposal))  # her memory only (phase 4)

def warmup_text_issues(text):
    """The fixed rules of a warm-up comment (calentamiento.warmup_post): 25–40 words, ends with one question, no
    applause, no offer of help. Selling, links and the rest are the rules of every comment."""
    text=text or '';issues=[];words=len(WORD.findall(text));low,high=WARMUP_WORDS
    if not low<=words<=high:issues.append(f'Comentario de calentamiento fuera de {low}–{high} palabras ({words})')
    if not text.rstrip().rstrip('"\'”’»)').endswith('?'):issues.append('Comentario de calentamiento que no termina en una pregunta')
    elif text.count('?')>1:issues.append('Comentario de calentamiento con más de una pregunta')
    if APPLAUSE.search(text):issues.append('Comentario de calentamiento que aplaude o felicita')
    if WARMUP_SELL.search(text):issues.append('Comentario de calentamiento que ofrece ayuda o servicios')
    return issues

def comment_author_issues(proposal):
    """INT-03 rule about the target, which no redraft can fix: one comment per referent within the cooldown and, with
    BUYER_WARMUP_ENABLED, one per author of the post (a buyer has no referent)."""
    from . import calentamiento
    states=['approved','executing','sent','confirmed','uncertain'];now=timezone.now()
    hours=int(author_cooldown().total_seconds()//3600)
    if proposal.post and proposal.post.referent_id and proposal.post.referent_id in recent_comment_authors(
            proposal.account,now,states=states,exclude=proposal.pk):
        return [f'Ya hay un comentario para {proposal.post.author_name} en las últimas {hours} h']
    if (calentamiento.enabled() and proposal.post and proposal.post.author_provider_id and
            proposal.post.author_provider_id in recent_comment_author_ids(proposal.account,now,states=states,exclude=proposal.pk)):
        return [f'Ya hay un comentario para {proposal.post.author_name} en las últimas {hours} h']
    return []

def policy_review(proposal,lead_budget=None):
    """Approve or discard a pending proposal according to the autonomy policy. `lead_budget` ({'left': n, 'deferred': 0},
    from tick) caps the lead's reviews: once spent, a proposal that needs the lead stays pending for a later tick."""
    from .orquestacion import cycle_issues
    if cycle_issues(proposal):return proposal
    mode=autonomy_of(proposal)
    if mode=='approval':return proposal
    if mode=='auto' and provisional_draft(proposal):return proposal  # a provisional voice's post waits for a person
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
            from .notificaciones import avisar, de_contenido
            avisar('piece_discarded',f'La política no aprobó la pieza del {proposal.piece.slot_date:%d/%m}','; '.join(issues)[:300],
                   link=f'/calendario/pieza/{proposal.piece_id}',ref=f'piece_discarded:{proposal.id}',member=de_contenido(proposal.piece))
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
        from .notificaciones import avisar, de_contenido
        avisar('piece_scheduled',f'La pieza del {when:%d/%m} está lista',f'Sale a las {when:%H:%M}. Puedes vetarla en el detalle hasta esa hora.',
               link=f'/calendario/pieza/{proposal.piece_id}',ref=f'piece_scheduled:{proposal.id}',member=de_contenido(proposal.piece))
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
    from .notificaciones import ORGANIZACION, avisar
    members=miembros.active_members()
    for capability in lider.capabilities():
        # The lead is the organization's; what it reviews in `auto` is the proposals of the members who have it in `auto`.
        auto=[m for m in members if autonomy(capability,m)=='auto']
        if not auto:continue
        reviewed=ActionProposal.objects.filter(capability=capability,decided_at__gte=now-timedelta(days=7),
                                               review__decision__in=['approve','discard'])
        if None not in auto:reviewed=reviewed.filter(account__member__in=auto) if len(auto)<len(members) else reviewed
        total=reviewed.count()
        if total<max(minimum,1) or reviewed.filter(review__decision='approve').exists():continue
        top=', '.join(f'{qid} ({n})' for qid,n in _failing_checks(reviewed.values_list('review',flat=True)).most_common(3))
        label=ActionProposal.Capability(capability).label if capability in ActionProposal.Capability.values else capability
        created=avisar('lead_silent',f'El líder no aprobó nada de {capability} en 7 días',
                       f'{label}: revisó {total} propuestas y descartó todas.'+(f' Lo que más falla: {top}.' if top else '')+
                       ' Revisa los umbrales del líder, la orientación o lo que proponen los agentes.',
                       link=f'/calendario?vista=lista&tipo={ACTIVITY_TYPE.get(capability,"red")}&no_salio=1',
                       ref=f'lead_silent:{capability}:{year}-W{week:02d}',member=ORGANIZACION)  # the lead is the organization's
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
    from . import alertas_slack
    report['slack']=alertas_slack.vigilar(now)  # reads the state, also with the machine stopped; never raises
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
    for proposal in ActionProposal.objects.select_related('post','piece','contact','account__member').filter(state=ActionProposal.State.PROPOSED).order_by('created_at'):
        if inactive(proposal.account):  # organizaciones, phase 7: an inactive member's proposals wait, untouched
            report['inactive']=report.get('inactive',0)+1;continue
        try:policy_review(proposal,lead_budget)
        except miembros.MiembroRequerido:  # an account of nobody among several members: no rhythm decides for it
            report['unowned']=report.get('unowned',0)+1;continue
        report['reviewed']+=1
    if lead_budget['deferred']:report['lead_deferred']=lead_budget['deferred']
    if _lead_silence_due(now):
        report['lead_silent']=lead_silence(now)
        try:
            from . import auditoria_compuertas
            report['gate_alerts']=auditoria_compuertas.vigilar(now)
        except Exception as exc:report['gate_alerts_error']=type(exc).__name__  # the audit never stops the tick
    try:report['plan']=_editorial(user,now)
    except ValueError as exc:report.update(plan=0,editorial_error=str(exc))  # misconfigured editorial never stops the rest
    members=miembros.exist()
    for account in ConnectorAccount.objects.select_related('member').filter(paused=False):
        if members and miembros.member_of_account(account) is None:  # organizaciones, phase 2: an account of nobody among
            report['unowned']=report.get('unowned',0)+1;continue  # several members has no rhythm: it neither reads nor writes
        if inactive(account):  # phase 7: a member in onboarding or deactivated: her accounts neither read nor write
            report['inactive']=report.get('inactive',0)+1;continue
        try:report['community_study']=report.get('community_study',0)+comunidad.schedule(user,account,now)
        except Exception as exc:report['community_error']=type(exc).__name__
        report['observe']+=_observe(user,account,now)
        redrafted=_lead_redraft(user,account,now)  # before a new draft: it holds the one draft at a time
        if redrafted:report['lead_redraft']=report.get('lead_redraft',0)+redrafted
        report['propose']+=_propose(user,account,now)
        try:  # phase 3: before the plan, so a warmed buyer's note is decided when the invitation is proposed
            drafted=_buyer_drafts(user,account,now)
            if drafted:report['buyer_drafts']=report.get('buyer_drafts',0)+drafted
        except Exception as exc:report['buyer_drafts_error']=type(exc).__name__  # never stops the rest of the tick
        report['network']=report.get('network',0)+_network(user,account,now)
        try:report['metrics']=report.get('metrics',0)+_metrics(user,account,now)
        except Exception as exc:report['metrics_error']=type(exc).__name__  # metrics never stop the rest of the tick
        try:report['outcomes']=report.get('outcomes',0)+_outcomes(user,account,now)
        except Exception as exc:report['outcomes_error']=type(exc).__name__  # outcomes never stop the rest of the tick
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
    try:report['monthly_review']=_monthly_review(user,now)
    except Exception as exc:report['monthly_review_error']=type(exc).__name__  # the monthly review never stops the rest
    return report

def inactive(account):
    """Whether `account` belongs to an inactive member (organizaciones, phase 7: one being onboarded, or deactivated). The
    autopilot leaves it alone: nothing is read, proposed, reviewed or written for her until she is active."""
    return bool(account is not None and account.member_id and not account.member.active)

def _editorial(user,now):
    """CONT-07: queue the preparation of each member's next slot (her EDITORIAL_POST_TIME, EDITORIAL_LEAD_HOURS ahead),
    one at a time per member, within the editorial daily budget and her CONT-09 caps. Each slot of hers gets one
    automatic attempt at most. Each member apart (organizaciones, phase 4): her job carries her (miembros.job_params) and
    its id her (miembros.job_parts), so one member's job never deduplicates another's, and her failure never stops the
    next member's (miembros.each_member)."""
    from . import editorial, editor_visual
    editorial.recover_stuck()
    editor_visual.upgrade_bindings()  # a still valid v1 visual package stops depending on her confirmed facts
    return miembros.each_member(lambda member:_editorial_for(user,now,member),'editorial')

def _pending_for(kind,member):
    """Whether a job of hers of `kind` is queued or running (job_params' encoding; every job without members)."""
    rows=Job.objects.filter(kind=kind,state__in=[Job.State.QUEUED,Job.State.RUNNING])
    return miembros.her_jobs(rows,member).exists()

def _editorial_for(user,now,member):
    from . import editorial, urgente
    if autonomy('CONT-09',member)=='off' or _pending_for('prepare_piece',member):return 0
    account=editorial.publishing_account(member)
    if not editorial.can_publish(account):return 0
    if not editorial.can_afford_preparation(now):return 0
    pieces=miembros.own(EditorialPiece.objects.all(),member);parts=miembros.job_parts(member)
    extra=urgente.next_extra(now,member)
    if extra:
        # The post she asked for at a day and hour is an order: prepared right away, outside the CONT-09 caps.
        attempt=pieces.filter(slot_date=extra,second_of_day=True).count()
        _,created=enqueue_operation(user,'prepare_piece',miembros.job_params(member,{'slot':extra.isoformat(),'extra':True}),
                                    request_id=_job_id('extra',extra,*parts) if not attempt else _job_id('extra',extra,attempt,*parts))
        return int(created)
    slot=urgente.next_slot(now,member=member) or editorial.next_slot(now,member=member)
    if slot is None or operador.capacity_left(account,'CONT-09',urgente.reserved_at(slot,member) or editorial.scheduled_for(slot,member))<=0:return 0
    _,created=enqueue_operation(user,'prepare_piece',miembros.job_params(member,{'slot':slot.isoformat()}),
                                request_id=_daily_job_id(pieces,slot,parts))
    return int(created)

def _daily_job_id(pieces,slot,parts):
    """The id of her day's next automatic attempt: one per piece the day already has (a renewed-budget retry gets its
    own). A piece prepared for the day and later moved away as another day's extra (urgente: «a la hora que pediste»)
    leaves the day free but its job keeps that attempt's id, so the attempt is skipped: 19/11/2026, two days stayed
    without a post because every tick asked again for a job that had already run."""
    attempt=pieces.filter(slot_date=slot,second_of_day=False).count()
    while True:
        jid=_job_id('piece',slot,*parts) if not attempt else _job_id('piece',slot,attempt,*parts)
        if not pieces.filter(origin_job=str(jid)).exclude(slot_date=slot,second_of_day=False).exists():return jid
        attempt+=1

def author_cooldown():
    return timedelta(hours=int(setting('OPERATOR_AUTHOR_COOLDOWN_HOURS','48')))

LIVE_COMMENT_STATES=['proposed','approved','executing','sent','confirmed','uncertain']

def recent_comment_authors(account,now,states=LIVE_COMMENT_STATES,exclude=None):
    """Referents who already got (or are about to get) a comment within the cooldown: one person, one comment at a time.
    Among two or more members, any member's comment counts (registro.peers, phase 6)."""
    from . import registro
    qs=ActionProposal.objects.filter(account__in=registro.peers(account),capability=ActionProposal.Capability.COMMENT,state__in=states,
                                     created_at__gte=now-author_cooldown(),post__referent__isnull=False)
    if exclude:qs=qs.exclude(pk=exclude)
    return set(qs.values_list('post__referent_id',flat=True))

def recent_comment_author_ids(account,now,states=LIVE_COMMENT_STATES,exclude=None):
    """Authors (author_provider_id) who already got (or are about to get) a comment within the cooldown: the wait of
    phase 2 is per author of the post, referent or buyer. Among two or more members, any member's comment counts."""
    from . import registro
    qs=ActionProposal.objects.filter(account__in=registro.peers(account),capability=ActionProposal.Capability.COMMENT,state__in=states,
                                     created_at__gte=now-author_cooldown())
    if exclude:qs=qs.exclude(pk=exclude)
    return set(filter(None,qs.values_list('post__author_provider_id',flat=True)))

def _observe(user,account,now):
    if not operador.within_read_window(now):return 0
    every=timedelta(minutes=int(setting('OPERATOR_OBSERVE_EVERY_MINUTES','180')))
    from . import referentes
    mine=referentes.to_read(account)  # phase 6: alone her referents; among members, the ones this account reads
    last=mine.order_by('last_observed_at').values_list('last_observed_at',flat=True).first()
    referents_due=mine.exists() and not (last and last>now-every)
    if _pending('observe',account=str(account.id)):return 0
    bucket=int(now.timestamp()//every.total_seconds())
    if not referents_due:
        # Phase 2: the buyers warming up have their own reads; when only they are due, observe reads only them.
        from . import calentamiento, projectapp, sin_posts
        # Phase 5: a bridge search or a bridge's posts due count as the buyers' reads; BAR-25: so do the partners' posts.
        if not (calentamiento.enabled() and (calentamiento.reading_due(account,now) or sin_posts.reading_due(account,now)
                                             or projectapp.reading_due(account,now))):return 0
        _,created=enqueue_operation(user,'observe',{'account':str(account.id),'limit':5,'referents':[],'solo_compradores':True},
                                    request_id=_job_id('observe-buyers',account.id,bucket))
        return int(created)
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
    if autonomy('INT-03',operador.member_of(account=account))=='off' or operador.capacity_left(account,'INT-03',now)-open_comments(account)<=0:return 0
    from knowledge import presupuesto
    if presupuesto.left(now)<=0:return 0
    day,_=operador.period_starts(now)
    drafted=ActionProposal.objects.filter(account=account,capability=ActionProposal.Capability.COMMENT,source='agent',created_at__gte=day).count()
    pending=Job.objects.filter(kind='propose_comment',state__in=[Job.State.QUEUED,Job.State.RUNNING]).count()
    room=daily_proposals()-drafted-pending
    if room<=0 or pending:return 0  # one paid draft at a time keeps spend within the daily cap
    max_age=timedelta(hours=int(setting('OPERATOR_MAX_POST_AGE_HOURS','72')))
    prefilter=prefilter_enabled()
    from . import calentamiento
    if calentamiento.enabled():return _propose_groups(user,account,now,max_age,prefilter)
    # A verdict is never older than its post, so verdicts from before the oldest candidate are irrelevant.
    verdicts=prefilter_verdicts(now-max_age-timedelta(days=1)) if prefilter else {}
    from . import registro
    candidates=(ObservedPost.objects.filter(account=account,is_repost=False,posted_at__gte=now-max_age,referent__active=True)
                .exclude(text='').exclude(proposals__capability='INT-03').exclude(referent_id__in=recent_comment_authors(account,now))
                .exclude(provider_post_id__in=registro.claimed_by_others(account))  # phase 6: another member comments it
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

def _propose_groups(user,account,now,max_age,prefilter):
    """Phase 2 (BUYER_WARMUP_ENABLED): the same one-draft-at-a-time within the same caps, budget and daily drafts, but
    the day's INT-03 slots are shared by group (calentamiento.rooms: compradores 8, comunidad 2, referentes 5 of 15) and a
    group with nothing to comment passes its slots on. Buyers' posts first, warmest author first; then the referents' as
    today. The wait is per author of the post. The prefilter judges both, with the buyer's own wording for a buyer."""
    from . import calentamiento, experimentos
    verdicts=prefilter_verdicts(now-max(max_age,calentamiento.post_max_age())-timedelta(days=1)) if prefilter else {}
    skips=[pid for pid,decision in verdicts.items() if decision=='skip']
    authors=recent_comment_author_ids(account,now)
    from . import registro
    referents=list(ObservedPost.objects.filter(account=account,is_repost=False,posted_at__gte=now-max_age,referent__active=True)
                   .exclude(text='').exclude(proposals__capability='INT-03').exclude(referent_id__in=recent_comment_authors(account,now))
                   .exclude(provider_post_id__in=registro.claimed_by_others(account))  # phase 6: another member comments it
                   .exclude(author_provider_id__in=list(authors)).exclude(id__in=skips).order_by('-posted_at')[:30])
    # Phase 6: a buyer or partner another member attends (or excluded for everyone, or a colleague) is not commented.
    authors=set(authors)|registro.foreign_uids(operador.member_of(account=account),registro.organization_id(account))
    focus=experimentos.active_focus(account,now)
    if focus:referents.sort(key=lambda post:post.referent_id!=focus.referent_id)
    # BAR-25: «comunidad» is the partners' posts with NETWORK_PROJECTAPP_BUYER_ENABLED; off it has none, as before.
    from . import projectapp
    groups={'compradores':calentamiento.buyer_posts(account,now,authors,skips)[:30],
            'comunidad':projectapp.partner_posts(account,now,authors,skips)[:30],'referentes':referents}
    room=calentamiento.rooms(account,now,{group for group,posts in groups.items() if posts})
    asked=0
    for group in calentamiento.GROUPS:
        if room[group]<=0:continue
        for post in groups[group]:
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
    if not compuertas.lead_redraft() or not lider.enabled() or autonomy('INT-03',operador.member_of(account=account))!='auto':return 0
    if 'INT-03' not in lider.capabilities() or operador.capacity_left(account,'INT-03',now)-open_comments(account)<=0:return 0
    from knowledge import presupuesto
    if presupuesto.left(now)<=0 or Job.objects.filter(kind='propose_comment',state__in=[Job.State.QUEUED,Job.State.RUNNING]).exists():
        return 0
    day,_=operador.period_starts(now)
    drafted=ActionProposal.objects.filter(account=account,capability=ActionProposal.Capability.COMMENT,source='agent',created_at__gte=day).count()
    if daily_proposals()-drafted<=0:return 0
    max_age=timedelta(hours=int(setting('OPERATOR_MAX_POST_AGE_HOURS','72')))
    from . import calentamiento, registro
    warm=calentamiento.enabled()
    target=Q(post__posted_at__gte=now-max_age,post__referent__active=True)
    if warm:  # phase 2: a warming buyer's comment the lead discarded gets its one redraft too
        from . import sin_posts
        target|=Q(post__posted_at__gte=now-calentamiento.post_max_age(),post__referent__isnull=True,
                  post__author_provider_id__in=[j.contact.provider_user_id for j in
                                                [*calentamiento.warming(account),*calentamiento.second_touch(account)]]
                  +[b.provider_user_id for b in sin_posts.warming(account)])
    discarded=(ActionProposal.objects.filter(account=account,capability=ActionProposal.Capability.COMMENT,source='agent',
                                             state=ActionProposal.State.DISCARDED,review__decision='discard',
                                             decided_at__gte=now-timedelta(hours=24)).filter(target)
               .exclude(post__referent_id__in=recent_comment_authors(account,now))
               .exclude(post__provider_post_id__in=registro.claimed_by_others(account))  # phase 6: only one member comments
               .exclude(post__author_provider_id__in=list(registro.foreign_uids(operador.member_of(account=account),
                                                                              registro.organization_id(account))))
               .annotate(drafts=Count('post__proposals',filter=Q(post__proposals__capability='INT-03'))).filter(drafts=1)
               .select_related('post').order_by('-decided_at'))
    if warm:discarded=discarded.exclude(post__author_provider_id__in=list(recent_comment_author_ids(account,now)))
    from . import experimentos
    rows=list(discarded[:10]);room=None
    if warm:
        buyers=calentamiento.buyer_ids(account)
        room=calentamiento.rooms(account,now,{calentamiento.group_of(p.post,buyers) for p in rows})
    for proposal in rows:
        if room is not None and room.get(calentamiento.group_of(proposal.post,buyers),0)<=0:continue
        if not experimentos.eligible(proposal.post,now):continue
        _,created=enqueue_operation(user,'propose_comment',{'post':str(proposal.post_id),'redraft_of':str(proposal.id)},
                                    request_id=_job_id('redraft',proposal.id))
        if created:return 1
    return 0

def _buyer_drafts(user,account,now):
    """Phase 3 (BUYER_FIRST_MESSAGE_ENABLED, with the lead on): the decisions that need no paid call (nothing real to cite,
    no note left, a conversation already, drafts that no longer apply) and then one paid draft at a time
    (prepare_buyer_draft): the note of a warmed buyer about to be invited, or the first message of an accepted one when
    it is due. Never sends anything (INB-08). Returns the decisions plus the job queued. Only inside READ_WINDOW, like the
    periodic reads: a draft builds on what the reads brought (her posts, the inbox), and its card is for the day.
    Phase 4 (BUYER_SEQUENCE_ENABLED, secuencia_comprador.step): messages 2–4 to whoever did not reply, the same job with
    its `number`; her reply, her rest after message 4 and the inbox-off notice are decided there too, without a paid call.
    Phase 6 (BUYER_REPLY_ENABLED, respuesta_comprador.step): her reply classified and answered (a draft he sends), the
    same job with kind «respuesta» and her reply's `number`; the rests that end and the referrals, without a paid call."""
    from . import mensajes_comprador, respuesta_comprador, secuencia_comprador
    from knowledge import presupuesto
    if not mensajes_comprador.active() or account.provider not in ('fake','directo'):return 0
    if not operador.within_read_window(now):return 0
    if _pending('prepare_buyer_draft'):return 0
    decided,item=mensajes_comprador.step(account,now)
    if secuencia_comprador.active():
        more,follow_up=secuencia_comprador.step(account,now)
        decided+=more;item=item or follow_up
    if respuesta_comprador.active():
        # Phase 6 (BUYER_REPLY_ENABLED): her reply goes first; the sequence's step already stopped it and moved her to «respondio».
        more,reply=respuesta_comprador.step(account,now)
        decided+=more;item=reply or item
    if item is None or presupuesto.left(now)<=0:return decided
    contact,kind,attempt,number=item
    tries=mensajes_comprador.tries(contact,kind,attempt,number)
    params={'contact':str(contact.pk),'kind':kind,'attempt':attempt,'at':now.isoformat()}
    if number>1 or kind==mensajes_comprador.REPLY:
        params['number']=number
        request_id=_job_id('buyer_draft',contact.pk,kind,attempt,number,tries)
    else:request_id=_job_id('buyer_draft',contact.pk,kind,attempt,tries)
    _,created=enqueue_operation(user,'prepare_buyer_draft',params,request_id=request_id)
    return decided+int(created)

def _every(name,default):
    return timedelta(minutes=int(setting(name,default)))

def _network(user,account,now):
    """DESC/RED: queue discovery, classification, the buyers' web check, planning and sync for the operating account,
    each on its own clock. Reads and the cheaper classifier run on their own; follows, invitations and acceptances become
    proposals. Discovery, classification (profile reads), the web check and sync read: only inside READ_WINDOW. The plan
    reads nothing. The web check is its own job (its own run of the cycle and its own budget): inside the classification's
    run its reserve passed the run's cost_cap_usd every morning (18/11/2026)."""
    if not red.enabled() or account.provider not in ('fake','directo'):return 0
    queued=0;reading=operador.within_read_window(now)
    def enqueue(kind,every,condition=True):
        nonlocal queued
        if not condition or _pending(kind,account=str(account.id)):return
        bucket=int(now.timestamp()//every.total_seconds())
        _,created=enqueue_operation(user,kind,{'account':str(account.id)},request_id=_job_id(kind,account.id,bucket))
        queued+=int(created)
    enqueue('discover_network',_every('NETWORK_DISCOVER_EVERY_MINUTES','360'),reading and red.discovery_room(account)>0)  # B4
    unclassified=Contact.objects.filter(account=account,classification={},stage__in=['candidate','incoming']).exists()
    enqueue('classify_contacts',_every('NETWORK_CLASSIFY_EVERY_MINUTES','30'),reading and unclassified and red.budget_left(now)>0)
    enqueue('check_buyer_stages',_every('NETWORK_STAGE_CHECK_EVERY_MINUTES','20'),
            reading and red.budget_left(now)>0 and red.stage_pending(account,now))
    enqueue('plan_network',_every('NETWORK_PLAN_EVERY_MINUTES','60'))
    enqueue('sync_network',_every('NETWORK_SYNC_EVERY_MINUTES','360'),reading)
    return queued

def _metrics(user,account,now):
    """APRE-01: queue collect_metrics (own posts at 24 h/72 h/7 d, daily audience) about every METRICS_EVERY_MINUTES,
    one at a time and only when something is due, for the operating account. METRICS_EVERY_MINUTES=0 turns it off."""
    from . import metricas
    every=_every('METRICS_EVERY_MINUTES','180')
    if not operador.within_read_window(now):return 0
    if account.provider not in metricas.PROVIDERS or every<=timedelta(0) or _pending('collect_metrics',account=str(account.id)):return 0
    if not metricas.due(now,miembros.member_for_account(account)):return 0
    bucket=int(now.timestamp()//every.total_seconds())
    _,created=enqueue_operation(user,'collect_metrics',{'account':str(account.id)},request_id=_job_id('metrics',account.id,bucket))
    return int(created)

def _outcomes(user,account,now):
    """Desenlaces (desenlaces.py): queue collect_outcomes about every OUTCOMES_EVERY_MINUTES, one at a time and only when
    an own comment reached 72 h or a network action 7 d without its outcome, for the account that reads LinkedIn.
    OUTCOMES_ENABLED=false or OUTCOMES_EVERY_MINUTES=0 turns it off."""
    from . import desenlaces, metricas
    every=_every('OUTCOMES_EVERY_MINUTES','180')
    if setting('OUTCOMES_ENABLED','true').strip().lower()!='true' or every<=timedelta(0) or not operador.within_read_window(now):return 0
    if account.provider not in metricas.PROVIDERS or _pending('collect_outcomes',account=str(account.id)):return 0
    if not desenlaces.due(now).exists():return 0
    bucket=int(now.timestamp()//every.total_seconds())
    _,created=enqueue_operation(user,'collect_outcomes',{'account':str(account.id)},request_id=_job_id('outcomes',account.id,bucket))
    return int(created)

def _analytics(user,account,now):
    """Creator analytics (analitica.py): queue import_analytics once per UTC day after ANALYTICS_DAILY_AFTER for a
    `directo` account whose navegador service is configured; one job a day, whatever its outcome."""
    from . import analitica
    if not operador.within_read_window(now):return 0
    if _pending('import_analytics',account=str(account.id)) or not analitica.daily_due(account,now):return 0
    day=analitica.utc_today(now)
    _,created=enqueue_operation(user,'import_analytics',{'account':str(account.id)},request_id=_job_id('analytics',account.id,day))
    return int(created)

def _canary(user,account,now):
    """The daily canary (canario.py): queue check_linkedin once per UTC day after LINKEDIN_CANARY_AFTER for a `directo`
    account whose navegador service is configured; a run that could not run is queued again an hour later, up to
    canario.TRIES a day (the attempt number keeps each try's job id apart)."""
    from . import analitica, canario
    if not operador.within_read_window(now):return 0
    if _pending('check_linkedin',account=str(account.id)) or not canario.daily_due(account,now):return 0
    day=analitica.utc_today(now)
    _,created=enqueue_operation(user,'check_linkedin',{'account':str(account.id)},
                                request_id=_job_id('canary',account.id,day,canario.tries(account,now)))
    return int(created)

def _inbox(user,account,now):
    """conversaciones_inbox: queue read_inbox about every INBOX_EVERY_MINUTES, one at a time, for an operating account that
    is not paused (the job itself refreshes the status and only reads a running account). Off unless INBOX_ENABLED."""
    from . import conversaciones
    every=conversaciones.every()
    if not conversaciones.enabled() or account.provider not in conversaciones.PROVIDERS or every<=timedelta(0):return 0
    if not operador.within_read_window(now):return 0
    if _pending('read_inbox',account=str(account.id)):return 0
    bucket=int(now.timestamp()//every.total_seconds())
    _,created=enqueue_operation(user,'read_inbox',{'account':str(account.id)},request_id=_job_id('inbox',account.id,bucket))
    return int(created)

def _replies(user,account,now):
    """INT-04: read the comments on his recent own posts when one is due and the day's share leaves room
    (respuestas.reading_due), then one paid draft at a time for the oldest comment waiting for one, while the INT-04 caps
    leave a slot after the replies already waiting. Only inside READ_WINDOW: a draft reads the commenter's profile too."""
    from . import respuestas
    from knowledge import presupuesto
    if not respuestas.enabled(operador.member_of(account=account)) or account.provider not in respuestas.PROVIDERS or not operador.within_read_window(now):return 0
    queued=0
    due=respuestas.reading_due(account,now)
    if due and not _pending('read_own_comments',account=str(account.id)):
        # One read per half hour and first post: the newest post never waits for the slot another post's read took.
        bucket=int(now.timestamp()//1800)
        _,created=enqueue_operation(user,'read_own_comments',{'account':str(account.id)},
                                    request_id=_job_id('replies',account.id,bucket,due[0][1].pk))
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

def _monthly_review(user,now):
    """analista_barrio_resultados: on the first Monday of the month, an hour after the weekly summary, queue the review of
    the month that ended (revision_mensual.queue: one per month, deterministic job id). Off with MONTHLY_REVIEW_ENABLED=false."""
    from . import revision_mensual
    return revision_mensual.queue(user,now)

RETRY_BASE,RETRY_CAP=timedelta(minutes=1),timedelta(hours=1)

def _stopped_recently(proposal,now):
    """A gate only operador.execute knows (the shared profile reads, a stopped experiment, the thread of a reply, another
    connector in pause…) stops the job and leaves the proposal approved. The first stop is tried again at once; from the
    second on the proposal waits 2, 4, 8… minutes up to an hour after its last stopped job, and meanwhile the others
    go: one proposal was queued again every minute for hours (573 failed jobs) and nothing else was executed."""
    stops=Job.objects.filter(kind='execute_action',state=Job.State.FAILED,params__proposal=str(proposal.id))
    count=stops.count()
    if count<2:return False
    last=stops.aggregate(at=Max(Coalesce('finished_at','created_at')))['at']
    return bool(last) and now-last<min(RETRY_BASE*2**min(count-1,10),RETRY_CAP)

def _executing(member):
    """Whether an execution of the member's is queued or running: one at a time per member (another member's never
    holds hers back; organizaciones, phase 2). Without members, any execution, as before."""
    pending=[pk for pk in Job.objects.filter(kind='execute_action',state__in=[Job.State.QUEUED,Job.State.RUNNING])
             .values_list('params__proposal',flat=True)]
    if not pending:return False
    if member is None:return True
    return miembros.mine(ActionProposal.objects.filter(pk__in=pending),member).exists()

def _execute(user,account,now):
    from .orquestacion import cycle_issues
    if not operador.within_window(now):return 0
    member=operador.member_of(account=account)
    if _executing(member):return 0
    rounds=bool(operador.network_batches())
    # Without network rounds every write of a member shares one spacing; with them a network write inside its round
    # waits less. Her own post does not wait for the day's opening (operador.spacing_ok).
    due=operador.post_due(now,member)  # a network action or comment of hers now could push her post past its hour
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
        if _stopped_recently(proposal,now):continue  # a gate keeps stopping it: it waits and the next one goes
        job=operador.enqueue_execution(user,proposal)
        return int(job.state==Job.State.QUEUED)
    return 0

def reconcile_window():
    """How long an unconfirmed write keeps being read back. After it the execution stays as it is, with its note, for
    Gustavo: two follows LinkedIn never showed were read every hour without end, out of the daily profile reads."""
    try:return timedelta(hours=max(1,int(os.environ.get('OPERATOR_RECONCILE_HOURS','24'))))
    except ValueError:return timedelta(hours=24)

def _reconcile(user,now):
    due=ActionExecution.objects.filter(state__in=['sent','uncertain'],started_at__lt=now-timedelta(minutes=10),
                                       started_at__gte=now-reconcile_window()).filter(
        Q(reconciled_at__isnull=True)|Q(reconciled_at__lt=now-timedelta(hours=1)))
    count=0
    for execution in due[:3]:
        hour=int(now.timestamp()//3600)
        _,created=enqueue_operation(user,'reconcile_action',{'proposal':str(execution.proposal_id)},request_id=_job_id('reconcile',execution.id,hour))
        count+=int(created)
    return count
