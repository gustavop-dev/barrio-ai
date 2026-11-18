"""Desenlaces: what came after an executed action (ActionOutcome). An own comment on someone else's post (INT-03) is
measured at 72 h and a follow, invitation or acceptance (RED-01/02/04) at 7 d. Readers only: the collector
(desenlaces_captura.py, job collect_outcomes) writes the rows and agents read them here. Never calls LinkedIn."""
from datetime import timedelta
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone
from .models import ActionExecution, ActionOutcome

COMMENT='INT-03'
NETWORK=('RED-01','RED-02','RED-04')
DONE=(ActionExecution.State.CONFIRMED,ActionExecution.State.SENT)
# Age at which an execution is measured and the oldest it may still be measured at; past it the moment is gone.
WINDOWS={'72h':(timedelta(hours=72),timedelta(days=10)),'7d':(timedelta(days=7),timedelta(days=21))}
RANK={'72h':0,'7d':1}

def _row(outcome):
    return {'kind':outcome.kind,'source':outcome.source,'reactions':outcome.reactions,'replies':outcome.replies,
            'author_replied':outcome.author_replied,'signals':outcome.signals,'captured_at':outcome.captured_at.isoformat()}

def for_execution(execution):
    """[{kind, source, reactions, replies, author_replied, signals, captured_at (iso)}] of one execution, oldest first."""
    return [_row(o) for o in ActionOutcome.objects.filter(execution=execution).order_by('captured_at')]

def _latest(outcomes):
    """{execution_id: outcome}: one outcome per execution, its latest age (7 d over 72 h), then its latest capture."""
    best={}
    for o in outcomes:
        kept=best.get(o.execution_id)
        if kept is None or (RANK.get(o.kind,-1),o.captured_at)>(RANK.get(kept.kind,-1),kept.captured_at):best[o.execution_id]=o
    return best

def _window(days,now):
    now=now or timezone.now()
    return Q(captured_at__gt=now-timedelta(days=days),captured_at__lte=now)

def comment_history(author_provider_id,limit=5,now=None):
    """What came of the owner's last comments (INT-03) on posts by this author, newest comment first, one per comment:
    [{commented_at (iso), replies, reactions, author_replied, kind}]. Only outcomes already captured at `now`."""
    if not author_provider_id:return []
    rows=ActionOutcome.objects.select_related('execution').filter(execution__proposal__capability=COMMENT,
        execution__proposal__post__author_provider_id=author_provider_id,captured_at__lte=now or timezone.now())
    latest=sorted(_latest(rows).values(),key=lambda o:o.execution.started_at,reverse=True)[:limit]
    return [{'commented_at':o.execution.started_at.isoformat(),'replies':o.replies,'reactions':o.reactions,
             'author_replied':o.author_replied,'kind':o.kind} for o in latest]

def comment_rates(days=30,now=None,accounts=None):
    """{'measured','with_reply','author_replied'} over the owner's comments (INT-03) whose outcome was captured in the
    last `days`; each comment counts once, by its latest outcome. A reply count unread (null) is not a reply. `accounts`:
    only those accounts' comments (a member's, organizaciones phase 5)."""
    rows=ActionOutcome.objects.filter(_window(days,now),execution__proposal__capability=COMMENT)
    if accounts is not None:rows=rows.filter(execution__proposal__account__in=accounts)
    latest=list(_latest(rows).values())
    return {'measured':len(latest),'with_reply':sum(1 for o in latest if o.replies),
            'author_replied':sum(1 for o in latest if o.author_replied)}

def network_engaged(contact_ids=None,days=30,now=None,accounts=None):
    """{contact_id: [signals]}: the people whose follow (RED-01) had an outcome captured in the last `days` with any
    true signal (accepted, commented_own_post, replied_to_comment, invited_us…). `contact_ids` narrows the lookup;
    membership (`id in result`) works as with a set."""
    rows=ActionOutcome.objects.filter(_window(days,now),execution__proposal__capability='RED-01')
    if contact_ids is not None:rows=rows.filter(execution__proposal__contact_id__in=list(contact_ids))
    if accounts is not None:rows=rows.filter(execution__proposal__account__in=accounts)
    engaged={}
    for contact_id,signals in rows.values_list('execution__proposal__contact_id','signals'):
        true=[name for name,value in (signals or {}).items() if value]
        if contact_id and true:engaged.setdefault(contact_id,set()).update(true)
    return {contact_id:sorted(names) for contact_id,names in engaged.items()}

def due(now=None):
    """Executions waiting for an outcome, oldest first: own comments (INT-03) that wrote, 72 h to 10 days old, without
    their 72 h outcome; follows, invitations and acceptances (RED-01/02/04) 7 to 21 days old without their 7 d one.
    Only confirmed or sent executions: a failed one changed nothing on LinkedIn."""
    now=now or timezone.now()
    (h72,late72),(d7,late7)=WINDOWS['72h'],WINDOWS['7d']
    measured=lambda kind:Exists(ActionOutcome.objects.filter(execution=OuterRef('pk'),kind=kind))
    rows=ActionExecution.objects.select_related('proposal','proposal__post','proposal__contact').filter(state__in=DONE).annotate(
        has_72h=measured('72h'),has_7d=measured('7d'))
    comments=Q(proposal__capability=COMMENT,wrote=True,has_72h=False,started_at__lte=now-h72,started_at__gte=now-late72)
    network=Q(proposal__capability__in=NETWORK,has_7d=False,started_at__lte=now-d7,started_at__gte=now-late7)
    return rows.filter(comments|network).order_by('started_at')
