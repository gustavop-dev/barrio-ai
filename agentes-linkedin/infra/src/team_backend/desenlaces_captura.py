"""Desenlaces, the collector (job collect_outcomes): writes the ActionOutcome rows desenlaces.py reads.

- An own comment on someone else's post (INT-03), 72 h after it: read on LinkedIn (source 'read'). One comments read
  finds it (operador._find_own_comment: its id, or Gustavo's comment with the same text) and gives its reactions and
  answers; when it has answers, one thread read says who gave them (Gustavo's own left out) and whether the post's
  author is among them. Only who answered is kept, never who only reacted. A comment not on the page LinkedIn answers
  stays pending: never a zero outcome.
- A follow, invitation or acceptance (RED-01/02/04), 7 d after it: derived from Barrio's own rows without a LinkedIn
  read (source 'derived'). The row is always written: every signal false is that outcome.
Reads count against their own daily caps through the audit log (outcomes.read, OUTCOMES_READ_CAPS), like metrics; a
spent cap, a pause or the navegador service's «nothing left» stops the reads and leaves the rest pending for the next
run, another read error leaves only that comment pending. Each age is written once. Null means unread, never zero."""
import os
import re
from datetime import timedelta
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from . import desenlaces, metricas, operador
from .connectors import ConnectorError, deferred, get_connector
from .models import ActionOutcome, AuditEvent, Conversation, PostComment
from .permissions import require

READ_CAPS={'comments':20,'threads':20}  # per local day; the autopilot queues the job about every 3 h
THREAD_PAGE=50  # the answers one thread read brings
PERSON_ID=re.compile(r'ACo[A-Za-z0-9_\-]{1,100}')  # a member's profile id; a company page's id is another shape
# Why a due outcome was not written (summary['reasons']): the own comment was not on the page LinkedIn answered; a daily
# read cap stopped the reads; a read failed (or a pause or «nothing left» stopped them).
PENDING_REASONS=('sin_comentario','tope_de_lecturas','error_de_lectura')

class ReadCapReached(ValueError):
    """The daily read cap of a kind is spent; nothing was read."""

def setting(name,default):
    return os.environ.get(name,default)

def read_caps():
    caps=dict(READ_CAPS)
    for item in filter(None,setting('OUTCOMES_READ_CAPS','').split(',')):
        key,_,value=item.partition('=')
        if key.strip() in caps and value.strip().isdigit():caps[key.strip()]=int(value)
    return caps

def reads_today(account,kind,now=None):
    day,_=operador.period_starts(now)
    return AuditEvent.objects.filter(action='outcomes.read',target=str(account.id),metadata__kind=kind,
                                     created_at__gte=day,created_at__lt=day+timedelta(days=1)).count()

def _read(account,kind,now=None):
    """Count a read before making it; a spent cap stops the read."""
    now=now or timezone.now()  # The cap and the audit must use the same clock.
    cap=read_caps()[kind]
    if reads_today(account,kind,now)>=cap:raise ReadCapReached(f'Tope diario de lecturas de desenlaces «{kind}» alcanzado ({cap}).')
    AuditEvent.objects.create(action='outcomes.read',target=str(account.id),metadata={'kind':kind},created_at=now)

def _save(execution,kind,now,**fields):
    """One outcome per age. The unique (execution, kind) constraint keeps a concurrent run from writing twice: only that
    duplicate is nothing new (False); any other failure propagates."""
    try:
        with transaction.atomic():
            ActionOutcome.objects.create(execution=execution,kind=kind,captured_at=now,**fields)
    except IntegrityError:
        if ActionOutcome.objects.filter(execution=execution,kind=kind).exists():return False
        raise
    return True

def _tally(summary,capability,reason=''):
    summary['by_kind'][capability]['pending' if reason else 'captured']+=1
    if reason:summary['pending']+=1;summary['reasons'][reason]+=1
    else:summary['captured']+=1

# --------------------------------------------------------------------------- INT-03, read

def _comment(account,connector,execution,now,summary):
    """The 72 h outcome of one own comment. Returns '' once written, None when another run already wrote it, else why
    it stays pending. A spent comments cap and connector errors propagate; a spent threads cap still writes the
    outcome, without who answered (author_replied null, no repliers)."""
    proposal=execution.proposal;post=proposal.post
    if post is None or not post.provider_post_id:return 'sin_comentario'
    _read(account,'comments',now)
    found=operador._find_own_comment(connector,post.provider_post_id,proposal.payload.get('text'),execution.external_id or None)
    if found is None:return 'sin_comentario'  # maybe beyond the page LinkedIn answers: no outcome rather than a zero
    replies,repliers=found.get('reply_counter'),[]
    author_replied=False if replies==0 else None
    if replies:
        try:_read(account,'threads',now)
        except ReadCapReached as exc:summary['threads_error']=str(exc)
        else:
            thread=connector.list_comment_thread(post.provider_post_id,found['id'],limit=THREAD_PAGE)
            repliers=list(dict.fromkeys(c['author']['id'] for c in thread if not c['is_sender'] and c['author'].get('id')))
            # Only a person's id (`ACo…`) is compared; any other author id (a company page) is not.
            author=post.author_provider_id or ''
            author_replied=author in repliers if PERSON_ID.fullmatch(author) else None
    if not _save(execution,'72h',now,source=ActionOutcome.Source.READ,provider_comment_id=str(found['id'])[:255],
                 reactions=found.get('reaction_counter'),replies=replies,author_replied=author_replied,repliers=repliers):
        return None  # another run wrote it: nothing new
    if repliers:
        from . import comprador
        comprador.on_comment_outcome(execution,repliers)  # who answered: a buyer's signal, passive record only
    return ''

def collect_comments(account,executions,now,summary):
    """INT-03 outcomes, oldest first. A spent comments cap, a pause or «nothing left» (connectors.deferred) stops the
    reads and leaves the rest pending; any other read error leaves only that comment pending."""
    connector=None;stop=''
    for execution in executions:
        if stop:_tally(summary,desenlaces.COMMENT,stop);continue
        try:
            connector=connector or get_connector(account)
            reason=_comment(account,connector,execution,now,summary)
        except ReadCapReached as exc:
            reason=stop='tope_de_lecturas'
            summary['stopped']=f'{exc} El resto queda pendiente para la próxima corrida.'
        except ConnectorError as exc:
            reason='error_de_lectura'
            if exc.pause or deferred(exc) or connector is None:
                stop=reason;summary['stopped']=f'Lectura de desenlaces detenida: {exc}'
                if exc.pause:operador.set_account_pause(account,f'Desenlaces detenidos por el proveedor: {exc}')
        if reason is not None:_tally(summary,desenlaces.COMMENT,reason)

# --------------------------------------------------------------------------- RED-01/02/04, derived

def _when(value):
    try:at=parse_datetime(str(value or ''))
    except ValueError:return None
    return at if at and at.tzinfo else None

def signals(account,execution,now):
    """What the person did after a follow, invitation or acceptance, from Barrio's own rows (no LinkedIn read); each
    counts only between the execution and `now`: the connection (connected_at, as the invitation health reads it), a
    comment on an own post, an answer to an own comment (repliers of an INT-03 outcome captured after it), an invitation
    received (the 'incoming' event red.sync notes in the person's history when it sees one) and a conversation with
    activity."""
    contact=execution.proposal.contact;since=execution.started_at;uid=contact.provider_user_id
    after=lambda at:bool(at and since<at<=now)
    return {'accepted':bool(contact.connected_at and since<=contact.connected_at<=now),
            'commented_own_post':PostComment.objects.filter(contact=contact,own=False,commented_at__gt=since,commented_at__lte=now).exists(),
            'replied_to_comment':bool(uid) and ActionOutcome.objects.filter(
                execution__proposal__capability=desenlaces.COMMENT,execution__proposal__account=account,
                captured_at__gt=since,captured_at__lte=now,repliers__contains=[uid]).exists(),
            'invited_us':any(isinstance(e,dict) and e.get('event')=='incoming' and after(_when(e.get('at'))) for e in contact.history or []),
            'conversation':Conversation.objects.filter(contact=contact,last_message_at__gt=since,last_message_at__lte=now).exists()}

def collect_network(account,executions,now,summary):
    """RED-01/02/04 outcomes: one row each at 7 d, whatever its signals say; no read, so nothing stops them."""
    for execution in executions:
        if _save(execution,'7d',now,source=ActionOutcome.Source.DERIVED,signals=signals(account,execution,now)):
            _tally(summary,execution.proposal.capability)

# --------------------------------------------------------------------------- job entry point

def collect(user,account,now=None):
    """collect_outcomes job: the outcomes of this account's executions that are due (desenlaces.due), comments first so
    an answer read now already counts for the network's signals. Idempotent. Returns {captured, pending (ints),
    stopped (why the reads stopped, '' if they did not), by_kind ({capability: {captured, pending}}), reasons (pending
    per PENDING_REASONS)} and, when the threads cap left outcomes without who answered, threads_error."""
    require(user,'operate_linkedin')
    if account.provider not in metricas.PROVIDERS:raise ValueError('Los desenlaces se leen con la cuenta que lee LinkedIn.')
    now=now or timezone.now()
    summary={'captured':0,'pending':0,'stopped':'','by_kind':{c:{'captured':0,'pending':0} for c in (desenlaces.COMMENT,*desenlaces.NETWORK)},
             'reasons':dict.fromkeys(PENDING_REASONS,0)}
    due=list(desenlaces.due(now).filter(proposal__account=account))
    collect_comments(account,[e for e in due if e.proposal.capability==desenlaces.COMMENT],now,summary)
    collect_network(account,[e for e in due if e.proposal.capability in desenlaces.NETWORK and e.proposal.contact_id],now,summary)
    operador._audit(user,'outcomes.collected',account.id,**summary)
    return summary
