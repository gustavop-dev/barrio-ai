"""APRE-01: snapshots of own-post metrics (24 h, 72 h and 7 d) and of the audience (once per local day).

Sources, all reads through the directo account (docs/metricas-resultados.md):
- own posts: list_user_posts('me'), and get_post once the id of a publication is known. Impressions, reactions,
  comments and reposts are the post's counters. Each capture also reads the post's comments once (list_comments) to
  keep who commented, whether with substance (≥ 80 characters) and their neighborhood role;
- audience: own_audience (followers, connections) and profile_views (over a trailing window of
  METRICS_PROFILE_VIEWS_DAYS, or the connector's own window when it counts only one: directo's summary card, 90 days).
Null means no data (hidden, absent or unread), never zero.
A snapshot is captured once its age is reached, late if need be, and never twice; one that cannot be captured yet
stays pending with its reason in metrics.collected. Reads count against daily caps through the audit log
(metrics.read), like the network."""
import os
import re
from datetime import timedelta
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from . import operador
from .connectors import ConnectorError, get_connector, same_text
from .models import ActionExecution, AudienceSnapshot, AuditEvent, Contact, EditorialPiece, PostMetric
from .permissions import require

AGES={'24h':timedelta(hours=24),'72h':timedelta(hours=72),'7d':timedelta(days=7)}
ANALYSIS_UNITS=operador.ANALYSIS_UNITS
READ_CAPS={'posts':12,'post':20,'comments':20,'profile':3,'views':3}  # per local day; the autopilot runs ~8 times a day
SUBSTANTIVE_CHARS=80  # same threshold as a substantive comment in network discovery
VIEWS_RANGES=(14,28,90,365)  # date_range accepted by List Profile Views
PROVIDERS=('fake','directo')
# Published, as in the calendar and Resultados: confirmed, or sent after writing (a 201 of the Posts API not read back
# yet; the reconcile stops re-reading it after OPERATOR_RECONCILE_HOURS). Failed, uncertain and executing are not.
PUBLISHED=Q(state='confirmed')|Q(state='sent',wrote=True)
POSTS_MAX=100  # the longest own-post list one read asks for (METRICS_POSTS_LIMIT's ceiling)
NEAR=timedelta(minutes=20)  # the only own post LinkedIn dates this close to the write is that publication
POST_URN=re.compile(r'urn:li:(activity|ugcPost|share):(\d{1,25})')
ACTIVITY_ID=re.compile(r'\d{1,25}')  # the connector's post id (linkedin_directo/rutas.py)
# Why a due cut was not captured (summary['pending']): no own post matched; several own posts were dated around the
# write; a daily read cap stopped the read; the read failed or LinkedIn did not find the post.
PENDING_REASONS=('sin_coincidencia','varias_candidatas','tope_de_lecturas','sin_lectura')

class ReadCapReached(ValueError):
    """The daily read cap of a kind is spent; nothing was read."""

def setting(name,default):
    return os.environ.get(name,default)

def max_age():
    """Publications older than this are no longer read; at least 8 days, so the 7 d snapshot always has room."""
    return max(timedelta(days=8),timedelta(days=int(setting('METRICS_MAX_AGE_DAYS','30'))))

def posts_limit():
    return max(1,min(POSTS_MAX,int(setting('METRICS_POSTS_LIMIT','20'))))

def views_days():
    days=int(setting('METRICS_PROFILE_VIEWS_DAYS','28'))
    if days not in VIEWS_RANGES:raise ValueError('METRICS_PROFILE_VIEWS_DAYS debe ser 14, 28, 90 o 365.')
    return days

def views_window(connector):
    """The window profile views are asked for: the connector's own when it answers only one (directo:
    profile_views_days, LinkedIn's summary card), else METRICS_PROFILE_VIEWS_DAYS."""
    return getattr(connector,'profile_views_days',None) or views_days()

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
    return AuditEvent.objects.filter(action='metrics.read',target=str(account.id),metadata__kind=kind,
                                     created_at__gte=day,created_at__lt=day+timedelta(days=1)).count()

def _read(account,kind,now=None):
    """Count a read before making it; a spent cap stops the read."""
    now=now or timezone.now()  # The cap, shared reservation and audit must use the same clock.
    cap=read_caps()[kind]
    if reads_today(account,kind,now)>=cap:raise ReadCapReached(f'Tope diario de lecturas de métricas «{kind}» alcanzado ({cap}).')
    if kind=='profile':
        try:operador.reserve_profile_read(account,'metrics',now)
        except operador.ProfileReadCapReached as exc:raise ReadCapReached(str(exc)) from exc
    AuditEvent.objects.create(action='metrics.read',target=str(account.id),metadata={'kind':kind},created_at=now)

# --------------------------------------------------------------------------- what is due

def publications(now=None):
    """Published CONT-09 executions (PUBLISHED) within max_age, each with the snapshot ages it reached and still lacks."""
    now=now or timezone.now();rows=[]
    executions=(ActionExecution.objects.select_related('proposal__piece').prefetch_related('proposal__piece__post_metrics')
                .filter(PUBLISHED,proposal__capability='CONT-09',proposal__piece__isnull=False,started_at__gte=now-max_age())
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

def _known_id(piece,execution=None,account=None):
    """The reading account's id of a publication, once something found it: a metrics read (PostMetric, piece.metrics;
    both kept in the connector's ids), a replies scan (respuestas keeps the id in replies.scanned) or the execution,
    when its write found the post already there and kept the reader's id. Those two only count when made after
    the account's ids last changed scheme (ConnectorAccount.ids_since). A Posts API urn is not the reader's id: _urns compares it like with like."""
    stored=next((m.provider_post_id for m in piece.post_metrics.all() if m.provider_post_id),'')
    stored=stored or (piece.metrics or {}).get('provider_post_id') or ''
    if stored:return stored
    switched=account.ids_since if account is not None else None
    scans=AuditEvent.objects.filter(action='replies.scanned',target=str(piece.id),metadata__has_key='post_id')
    if switched:scans=scans.filter(created_at__gt=switched)  # an id of the scheme before
    scanned=scans.order_by('-created_at').values_list('metadata__post_id',flat=True).first()
    if scanned:return scanned
    own=str(getattr(execution,'external_id','') or '')
    if own and not own.startswith('urn:li:') and not (switched and (execution.finished_at or execution.started_at)<=switched):return own
    return ''

def _urns(*values):
    """(kind, number) of each LinkedIn post urn the values name: a link or urn (activity, ugcPost, share) or
    the connector's id (the activity number). Kinds are never converted into
    each other, so two posts are the same only by the same kind and number."""
    found=set()
    for value in (str(v) for v in values if v):
        found.update(POST_URN.findall(value))
        if ACTIVITY_ID.fullmatch(value):found.add(('activity',value))
    return found

def _near(recent,execution,rows,known):
    """Own posts (no reposts) LinkedIn dates within NEAR of the write, but none another publication already has (its
    known id or its exact text)."""
    def taken(post):
        return any(e.pk!=execution.pk and (post['id']==known[e.pk] or same_text(post['text'],e.proposal.payload.get('text')))
                   for e,_ in rows)
    return [p for p in recent if not p['is_repost'] and p['created_at'] and p['created_at'].tzinfo
            and abs(p['created_at']-execution.started_at)<=NEAR and not taken(p)]

def _pending(summary,execution,kinds,reason):
    summary['pending'].append({'piece':str(execution.proposal.piece_id),'cuts':list(kinds),'reason':reason})

def _longest(account,connector,now):
    """{id: post} of the longest own-post list (one read), for posts older than the recent list: its counters carry the
    impressions, which a single post read does not on directo (cliente.get_post). {} when the recent list already was
    the longest, or the read is not possible now (its cap, a refusal that does not pause)."""
    if posts_limit()>=POSTS_MAX:return {}
    try:
        _read(account,'posts',now)
        return {p['id']:p for p in connector.list_user_posts('me',limit=POSTS_MAX)}
    except ReadCapReached:return {}
    except ConnectorError as exc:
        if exc.pause:raise
        return {}

def _latest(post,now):
    return {'impressions':post['impressions'],'reactions':post['reactions_counter'],'comments':post['comments_counter'],
            'reposts':post['reposts_counter'],'observed_at':now.isoformat(),'source':'linkedin','provider_post_id':post['id'],
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
    """One PostMetric per due age, with the id and link of the post it was read from. The unique (piece, kind)
    constraint keeps a concurrent run from capturing twice: only that duplicate counts as already captured; any other
    failure, the evidence's included, propagates."""
    from .evidencia import ingest_metric
    created=0;piece=execution.proposal.piece
    for kind in kinds:
        with transaction.atomic():
            try:
                with transaction.atomic():
                    metric=PostMetric.objects.create(piece=piece,kind=kind,provider_post_id=post['id'],share_url=post['share_url'],
                        impressions=post['impressions'],reactions=post['reactions_counter'],comments=post['comments_counter'],
                        reposts=post['reposts_counter'],commenters=commenters,published_at=execution.started_at,captured_at=now)
            except IntegrityError:
                if PostMetric.objects.filter(piece=piece,kind=kind).exists():continue
                raise
            ingest_metric(metric)
        created+=1
    return created

def collect_posts(account,connector,now,summary):
    """Find each recent publication among Gustavo's own posts: by an id already known (_known_id), by the urn of its
    write like with like, by its exact text, or as the only own post LinkedIn dates within NEAR of the write. Capture
    the snapshots it is due and refresh EditorialPiece.metrics with the latest values read; a due cut not captured is
    listed in summary['pending'] with its reason (PENDING_REASONS)."""
    rows=publications(now)
    if not any(d for _,d in rows):return
    try:
        _read(account,'posts',now)
        recent=connector.list_user_posts('me',limit=posts_limit())
    except (ReadCapReached,ConnectorError) as exc:
        for execution,kinds in rows:
            if kinds:_pending(summary,execution,kinds,'tope_de_lecturas' if isinstance(exc,ReadCapReached) else 'sin_lectura')
        raise
    by_id={p['id']:p for p in recent};longest=None
    ids={e.pk:_known_id(e.proposal.piece,e,account) for e,_ in rows}
    for execution,kinds in rows:
        piece=execution.proposal.piece;known=ids[execution.pk];reason='';single=False
        refs=_urns(execution.external_id,execution.external_url)
        post=by_id.get(known) or (next((p for p in recent if refs&_urns(p['id'],p['share_url'])),None) if refs else None)
        if post is None and not known:
            post=next((p for p in recent if not p['is_repost'] and same_text(p['text'],execution.proposal.payload.get('text'))),None)
            near=_near(recent,execution,rows,ids) if post is None else []
            if len(near)==1:post=near[0]
            reason='varias_candidatas' if len(near)>1 else 'sin_coincidencia'
        if post is None and known and kinds:
            # Older than the recent list: the longest list (one read a run), then the post by id (one read), so a late
            # 7 d snapshot is never lost.
            if longest is None:longest=_longest(account,connector,now)
            post=longest.get(known)
            if post is None:
                try:_read(account,'post',now);post=connector.get_post(known);single=True
                except ReadCapReached:reason='tope_de_lecturas'
                except ConnectorError as exc:
                    if exc.pause:raise
                    reason='sin_lectura'
        if post is None:
            if kinds:_pending(summary,execution,kinds,reason or 'sin_lectura')
            continue
        if single and kinds and post['impressions'] is None:
            # Captured anyway: a single post read carries no impressions on directo; null, never dropped.
            summary['no_impressions'].append({'piece':str(piece.id),'cuts':list(kinds),'reason':'lectura_individual'})
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
    """One AudienceSnapshot per local day. Profile views are optional: if LinkedIn refuses or does not give them they
    stay null and summary['views_error'] says why; they are asked for the window the connector answers (views_window)."""
    day=local_day(now)
    if AudienceSnapshot.objects.filter(day=day).exists():summary['audience']='ya';return
    _read(account,'profile',now)
    audience=connector.own_audience()
    views,days=None,views_window(connector)
    try:
        _read(account,'views',now);views=connector.profile_views(days)
        if views is None:summary['views_error']=f'LinkedIn no dio las visitas al perfil de los últimos {days} días.'
    except (ReadCapReached,ConnectorError) as exc:summary['views_error']=str(exc)  # never pauses: profile views are a bonus
    try:
        with transaction.atomic():
            snapshot=AudienceSnapshot.objects.create(day=day,followers=audience['followers'],connections=audience['connections'],
                                            profile_views=views,profile_views_days=days if views is not None else None,captured_at=now)
            from .evidencia import ingest_audience
            ingest_audience(account,snapshot)
        summary['audience']='creada'
    except IntegrityError:summary['audience']='ya'

# --------------------------------------------------------------------------- job entry point

def collect(user,account,now=None):
    """collect_metrics job: own-post snapshots and today's audience. Idempotent; only reads. In the summary, `pending`
    lists each publication with due cuts not captured ({piece, cuts, reason}; len() is the number pending) and
    `no_impressions` the cuts captured without impressions and why."""
    require(user,'operate_linkedin')
    if account.provider not in PROVIDERS:raise ValueError('Las métricas se leen con la cuenta de LinkedIn directo.')
    now=now or timezone.now();connector=get_connector(account)
    context,grounding=operador.role_context('analista',ANALYSIS_UNITS,
        {'ventanas':['LI-06-V008-K01','LI-06-V008-K02'],'limites_de_inferencia':['LI-06-V006-K04','LI-06-V007-K05']})
    summary={'captured':0,'pending':[],'no_impressions':[],'refreshed':0,'audience':'no','stopped':'',**grounding,'course_context':context,
             'sales_inferred':False,'identities_inferred':False,'divulgadores_have_value':True,
             'interpretation_limits':'Contadores observados; sin causalidad, identidades nuevas ni ventas inferidas. Ventanas por edad de publicación; audiencia con su ventana propia.'}
    for step in (collect_posts,collect_audience):
        try:step(account,connector,now,summary)
        except (ReadCapReached,ConnectorError) as exc:
            from .evidencia import record_coverage
            record_coverage(account,'metrics_read',f'{step.__name__}:{now.isoformat()}',now,'missing',
                            {'step':step.__name__,'reason':'source_unavailable'})
            summary['stopped']='; '.join(filter(None,[summary['stopped'],str(exc)]))
            if getattr(exc,'pause',False):
                operador.set_account_pause(account,f'Métricas detenidas por el proveedor: {exc}');break
    operador._audit(user,'metrics.collected',account.id,**{k:v for k,v in summary.items() if k!='course_context'})
    return summary
