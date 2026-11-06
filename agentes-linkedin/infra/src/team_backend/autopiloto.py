"""Autopilot: the operator cycle running as an autonomous machine.

Decision by Gustavo (2026-11-06): «todo debe funcionar como una máquina autónoma».
Agents' proposals are approved by policy after automatic content checks instead of
waiting for a human; Gustavo stays on the loop (pause, reject, resolve, configure).
Each tick only enqueues work; the worker performs provider calls with the operator's
gates (kill switch, account pause, window, spacing, daily/weekly caps, exactly-once).
"""
import os
import re
import uuid
from datetime import timedelta
from decimal import Decimal
from django.db.models import Q
from django.utils import timezone
from knowledge import db, memory
from . import guardas, operador
from .jobs import enqueue_operation
from .models import ActionExecution, ActionProposal, ConnectorAccount, Job, ObservedPost

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

def setting(name,default):
    return os.environ.get(name,default)

def autonomy(capability):
    """OPERATOR_AUTONOMY='INT-03=auto,INT-02=auto'; modes auto | approval | off. Default auto."""
    for item in filter(None,setting('OPERATOR_AUTONOMY','').split(',')):
        key,_,mode=item.partition('=')
        if key.strip()==capability and mode.strip() in ('auto','approval','off'):return mode.strip()
    return 'auto'

def enabled():
    return setting('OPERATOR_AUTOPILOT','false').lower()=='true'

def content_issues(proposal):
    """Deterministic gate replacing per-piece human approval. Returns reasons to discard."""
    if proposal.capability!=ActionProposal.Capability.COMMENT:return []
    text=proposal.payload.get('text','');issues=[]
    if not 40<=len(text)<=900:issues.append('Longitud fuera de 40–900 caracteres')
    for pattern,reason in ((PITCH,'Contiene pitch o petición de contacto'),(URL,'Contiene enlaces'),(EMAIL,'Contiene un correo'),
                           (PHONE,'Contiene un número de teléfono'),(HASHTAG,'Contiene hashtags')):
        if pattern.search(text):issues.append(reason)
    if any(str(r).startswith('Afirmación por verificar') for r in proposal.risks):issues.append('Incluye afirmaciones sin evidencia')
    if proposal.source=='agent' and not proposal.citations:issues.append('Sin fundamento citado del curso')
    issues+=guardas.private_leaks(text,memory.confirmed_blocks()[1])
    return issues

def policy_review(proposal):
    """Approve or discard a pending proposal according to the autonomy policy."""
    mode=autonomy(proposal.capability)
    if mode=='approval':return proposal
    issues=['Capacidad desactivada por configuración'] if mode=='off' else content_issues(proposal)
    proposal.decided_at=timezone.now()
    if issues:
        proposal.state=ActionProposal.State.DISCARDED;proposal.risks=list(proposal.risks)+issues
        proposal.decision_note=f'Descartada por política {POLICY_VERSION}'
        proposal.save(update_fields=['state','risks','decided_at','decision_note'])
        operador._audit(None,'operator.policy_discarded',proposal.id,issues=issues)
        return proposal
    if proposal.payload_hash!=operador.current_hash(proposal):
        proposal.state=ActionProposal.State.DISCARDED;proposal.decision_note='Hash inconsistente; descartada'
        proposal.save(update_fields=['state','decided_at','decision_note']);return proposal
    proposal.state=ActionProposal.State.APPROVED;proposal.approved_hash=proposal.payload_hash
    proposal.decision_note=f'Aprobada por política {POLICY_VERSION}'
    proposal.save(update_fields=['state','approved_hash','decided_at','decision_note'])
    operador._audit(None,'operator.policy_approved',proposal.id,payload_hash=proposal.payload_hash)
    return proposal

def llm_spent_today(now=None):
    day,_=operador.period_starts(now)
    with db.connect() as c:
        row=c.execute('''SELECT coalesce(sum(CASE WHEN status='complete' THEN actual_usd WHEN status IN ('reserved','uncertain')
            THEN reserved_usd ELSE 0 END),0) AS spent FROM usage_ledger WHERE provider='anthropic' AND purpose='propose-comment'
            AND created_at>=%s''',(day,)).fetchone()
    return Decimal(row['spent'])

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
    if operador.globally_paused():return dict(report,stopped='OPERATOR_PAUSED')
    ttl=timedelta(hours=int(setting('OPERATOR_PROPOSAL_TTL_HOURS','48')))
    stale=ActionProposal.objects.filter(state__in=['proposed','approved'],created_at__lt=now-ttl).filter(execution__isnull=True)
    for proposal in stale:operador._audit(None,'operator.expired',proposal.id)
    report['expired']=stale.update(state=ActionProposal.State.EXPIRED,decision_note='Caducada sin ejecutar')
    for proposal in ActionProposal.objects.select_related('post').filter(state=ActionProposal.State.PROPOSED):
        policy_review(proposal);report['reviewed']+=1
    for account in ConnectorAccount.objects.filter(paused=False):
        report['observe']+=_observe(user,account,now)
        report['propose']+=_propose(user,account,now)
        report['execute']+=_execute(user,account,now)
    report['reconcile']+=_reconcile(user,now)
    return report

def _observe(user,account,now):
    every=timedelta(minutes=int(setting('OPERATOR_OBSERVE_EVERY_MINUTES','180')))
    last=account.referents.filter(active=True).order_by('last_observed_at').values_list('last_observed_at',flat=True).first()
    if not account.referents.filter(active=True).exists() or (last and last>now-every) or _pending('observe',account=str(account.id)):return 0
    bucket=int(now.timestamp()//every.total_seconds())
    _,created=enqueue_operation(user,'observe',{'account':str(account.id),'limit':5,'referents':[]},request_id=_job_id('observe',account.id,bucket))
    return int(created)

def _propose(user,account,now):
    if autonomy('INT-03')=='off' or operador.capacity_left(account,'INT-03',now)<=0:return 0
    if llm_spent_today(now)>=Decimal(setting('OPERATOR_DAILY_LLM_USD','1')):return 0
    day,_=operador.period_starts(now)
    drafted=ActionProposal.objects.filter(account=account,source='agent',created_at__gte=day).count()
    pending=Job.objects.filter(kind='propose_comment',state__in=[Job.State.QUEUED,Job.State.RUNNING]).count()
    room=int(setting('OPERATOR_DAILY_PROPOSALS','6'))-drafted-pending
    if room<=0 or pending:return 0  # one paid draft at a time keeps spend within the daily cap
    max_age=timedelta(hours=int(setting('OPERATOR_MAX_POST_AGE_HOURS','72')))
    candidates=(ObservedPost.objects.filter(account=account,is_repost=False,posted_at__gte=now-max_age,referent__active=True)
                .exclude(text='').exclude(proposals__capability='INT-03').order_by('-posted_at'))
    for post in candidates[:1]:
        _,created=enqueue_operation(user,'propose_comment',{'post':str(post.id)},request_id=_job_id('propose',post.id))
        return int(created)
    return 0

def _execute(user,account,now):
    if not operador.within_window(now) or not operador.spacing_ok(account,now):return 0
    if _pending('execute_action'):return 0
    for proposal in ActionProposal.objects.select_related('post').filter(account=account,state='approved',execution__isnull=True).order_by('created_at'):
        if operador.capacity_left(account,proposal.capability,now)<=0:continue
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
