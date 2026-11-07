"""APRE-01: snapshots of own-post metrics (24 h, 72 h and 7 d) and of the audience (once per local day).

Sources, all reads through the Unipile account (docs/metricas-resultados.md):
- own posts: GET users/me/posts, and GET posts/{id} once the Unipile id of a publication is known. Impressions come
  from analytics.impressions_counter, reactions from reactions_counter ([{reaction, count}]), comments from
  comments_counter and reposts from reposts_counter. Each capture also reads the post's comments once (GET
  posts/{id}/comments) to keep who commented, whether with substance (≥ 80 characters) and their neighborhood role;
- audience: GET users/me (followers_count, relations_count) and GET linkedin/analytics/profile-views
  (analytics.views_count over a trailing window of METRICS_PROFILE_VIEWS_DAYS).
Null means no data (hidden, absent or unread), never zero. A snapshot is captured once its age is reached, late if
need be, and never twice. Reads count against daily caps through the audit log (metrics.read), like the network."""
import os
from datetime import timedelta
from django.db import IntegrityError, transaction
from django.utils import timezone
from . import operador
from .connectors import ConnectorError, get_connector, same_text
from .models import ActionExecution, AudienceSnapshot, AuditEvent, Contact, EditorialPiece, PostMetric
from .permissions import require

AGES={'24h':timedelta(hours=24),'72h':timedelta(hours=72),'7d':timedelta(days=7)}
READ_CAPS={'posts':12,'post':20,'comments':20,'profile':3,'views':3}  # per local day; the autopilot runs ~8 times a day
SUBSTANTIVE_CHARS=80  # same threshold as a substantive comment in network discovery
VIEWS_RANGES=(14,28,90,365)  # date_range accepted by List Profile Views
PROVIDERS=('unipile','fake')

class ReadCapReached(ValueError):
    """The daily read cap of a kind is spent; nothing was read."""

def setting(name,default):
    return os.environ.get(name,default)

def max_age():
    """Publications older than this are no longer read; at least 8 days, so the 7 d snapshot always has room."""
    return max(timedelta(days=8),timedelta(days=int(setting('METRICS_MAX_AGE_DAYS','30'))))

def posts_limit():
    return max(1,min(100,int(setting('METRICS_POSTS_LIMIT','20'))))

def views_days():
    days=int(setting('METRICS_PROFILE_VIEWS_DAYS','28'))
    if days not in VIEWS_RANGES:raise ValueError('METRICS_PROFILE_VIEWS_DAYS debe ser 14, 28, 90 o 365.')
    return days

def read_caps():
    caps=dict(READ_CAPS)
    for item in filter(None,setting('METRICS_READ_CAPS','').split(',')):
        key,_,value=item.partition('=')
        if key.strip() in caps and value.strip().isdigit():caps[key.strip()]=int(value)
    return caps

def local_day(now=None):
    return (now or timezone.now()).astimezone(operador.local_tz()).date()

def reads_today(account,kind,now=None):
    day,_=operador.period_starts(now)
    return AuditEvent.objects.filter(action='metrics.read',target=str(account.id),metadata__kind=kind,created_at__gte=day).count()

def _read(account,kind,now=None):
    """Count a read before making it; a spent cap stops the read."""
    cap=read_caps()[kind]
    if reads_today(account,kind,now)>=cap:raise ReadCapReached(f'Tope diario de lecturas de métricas «{kind}» alcanzado ({cap}).')
    AuditEvent.objects.create(action='metrics.read',target=str(account.id),metadata={'kind':kind})

# --------------------------------------------------------------------------- what is due

def publications(now=None):
    """Confirmed CONT-09 executions within max_age, each with the snapshot ages it reached and still lacks."""
    now=now or timezone.now();rows=[]
    executions=(ActionExecution.objects.select_related('proposal__piece').prefetch_related('proposal__piece__post_metrics')
                .filter(state='confirmed',proposal__capability='CONT-09',proposal__piece__isnull=False,started_at__gte=now-max_age())
                .order_by('started_at'))
    for execution in executions:
        done={m.kind for m in execution.proposal.piece.post_metrics.all()}
        due=[kind for kind,age in AGES.items() if now-execution.started_at>=age and kind not in done]
        rows.append((execution,due))
    return rows

def due(now=None):
    """Cheap check for the autopilot (no reads): a snapshot age reached and missing, or no audience snapshot today."""
    return any(d for _,d in publications(now)) or not AudienceSnapshot.objects.filter(day=local_day(now)).exists()

# --------------------------------------------------------------------------- own posts

def _known_id(piece):
    """The Unipile id of a publication, once a previous read found it."""
    stored=next((m.provider_post_id for m in piece.post_metrics.all() if m.provider_post_id),'')
    return stored or (piece.metrics or {}).get('unipile_post_id') or ''

def _latest(post,now):
    return {'impressions':post['impressions'],'reactions':post['reactions_counter'],'comments':post['comments_counter'],
            'reposts':post['reposts_counter'],'observed_at':now.isoformat(),'source':'unipile','unipile_post_id':post['id'],
            'share_url':post['share_url']}

def substantive(text):
    return len(' '.join((text or '').split()))>=SUBSTANTIVE_CHARS

def _commenters(account,connector,post_id,now):
    """Who commented on an own post (one read): one compact entry per comment, Gustavo's own replies left out, with the
    neighborhood role when the person is already a Contact."""
    _read(account,'comments',now)
    comments=[c for c in connector.list_comments(post_id,limit=50) if not c['is_sender'] and c['author'].get('id')]
    known=dict(Contact.objects.filter(account=account,provider_user_id__in=[c['author']['id'] for c in comments])
               .values_list('provider_user_id','classification'))
    return [{'provider_user_id':c['author']['id'],'name':c['author'].get('display_name') or '','substantive':substantive(c['text']),
             'role':(known.get(c['author']['id']) or {}).get('role'),'fit':(known.get(c['author']['id']) or {}).get('fit')} for c in comments]

def _capture(execution,kinds,post,now,commenters=None):
    """One PostMetric per due age; the unique (piece, kind) constraint keeps a concurrent run from capturing twice."""
    created=0
    for kind in kinds:
        try:
            with transaction.atomic():
                PostMetric.objects.create(piece=execution.proposal.piece,kind=kind,provider_post_id=post['id'],share_url=post['share_url'],
                    impressions=post['impressions'],reactions=post['reactions_counter'],comments=post['comments_counter'],
                    reposts=post['reposts_counter'],commenters=commenters,published_at=execution.started_at,captured_at=now)
            created+=1
        except IntegrityError:continue
    return created

def collect_posts(account,connector,now,summary):
    """Find each recent publication among Gustavo's own posts (stored id first, exact text otherwise), capture the
    snapshots it is due and refresh EditorialPiece.metrics with the latest values read."""
    rows=publications(now)
    if not any(d for _,d in rows):return
    _read(account,'posts',now)
    recent=connector.list_user_posts('me',limit=posts_limit())
    by_id={p['id']:p for p in recent}
    for execution,kinds in rows:
        piece=execution.proposal.piece;known=_known_id(piece)
        post=by_id.get(known) if known else next((p for p in recent if not p['is_repost'] and same_text(p['text'],execution.proposal.payload.get('text'))),None)
        if post is None and known and kinds:
            # Older than the list: read it by id (one read), so a late 7 d snapshot is never lost.
            _read(account,'post',now)
            try:post=connector.get_post(known)
            except ConnectorError as exc:
                if exc.pause:raise
                post=None
        if post is None:
            summary['pending']+=len(kinds);continue
        EditorialPiece.objects.filter(pk=piece.pk).update(metrics=_latest(post,now))
        commenters=None
        if kinds:
            # One comments read serves every age captured now; if it fails the snapshot keeps commenters=null (not read).
            try:commenters=_commenters(account,connector,post['id'],now)
            except ReadCapReached as exc:summary['comments_error']=str(exc)
            except ConnectorError as exc:
                if exc.pause:raise
                summary['comments_error']=str(exc)
        summary['refreshed']+=1;summary['captured']+=_capture(execution,kinds,post,now,commenters)

# --------------------------------------------------------------------------- audience

def collect_audience(account,connector,now,summary):
    """One AudienceSnapshot per local day. Profile views are optional: if LinkedIn refuses them they stay null."""
    day=local_day(now)
    if AudienceSnapshot.objects.filter(day=day).exists():summary['audience']='ya';return
    _read(account,'profile',now)
    audience=connector.own_audience()
    views,days=None,views_days()
    try:
        _read(account,'views',now);views=connector.profile_views(days)
    except (ReadCapReached,ConnectorError) as exc:summary['views_error']=str(exc)  # never pauses: profile views are a bonus
    try:
        with transaction.atomic():
            AudienceSnapshot.objects.create(day=day,followers=audience['followers'],connections=audience['connections'],
                                            profile_views=views,profile_views_days=days if views is not None else None,captured_at=now)
        summary['audience']='creada'
    except IntegrityError:summary['audience']='ya'

# --------------------------------------------------------------------------- job entry point

def collect(user,account,now=None):
    """collect_metrics job: own-post snapshots and today's audience. Idempotent; only reads."""
    require(user,'operate_linkedin')
    if account.provider not in PROVIDERS:raise ValueError('Las métricas se leen con la cuenta Unipile.')
    now=now or timezone.now();connector=get_connector(account)
    summary={'captured':0,'pending':0,'refreshed':0,'audience':'no','stopped':''}
    for step in (collect_posts,collect_audience):
        try:step(account,connector,now,summary)
        except (ReadCapReached,ConnectorError) as exc:
            summary['stopped']='; '.join(filter(None,[summary['stopped'],str(exc)]))
            if getattr(exc,'pause',False):
                operador.set_account_pause(account,f'Métricas detenidas por el proveedor: {exc}');break
    operador._audit(user,'metrics.collected',account.id,**summary)
    return summary
