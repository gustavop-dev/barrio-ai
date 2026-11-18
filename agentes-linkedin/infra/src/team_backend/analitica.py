"""Creator analytics of a `directo` account (docs/metricas-resultados.md, «Analítica de LinkedIn»).

Import: LinkedIn's export dialog, one call through the navegador service (linkedin_directo.analitica reads it), kept in
AnalyticsDay (per UTC day), AnalyticsPost (lifetime figures per post), AnalyticsSnapshot (follower total and audience
demographics per capture day), AnalyticsRange (what only holds for the exact range: totals, top lists, content
demographics) and AnalyticsImport (one row per export asked, ok or not). Only reads LinkedIn.
- import_range: one range, upserted, then every post still without its piece linked to it once one of our ids names it
  (relink). LinkedIn's errors land in the AnalyticsImport row; one that stops the account (login, checkpoint,
  401/403/429/999, the service's stop) also pauses it, as the other directo reads do. A workbook that reads but brings
  no days or no posts where earlier imports did (a format change reads as headers only) is kept, state ok, with
  error_kind EMPTY and the reason (degraded).
- run: the daily job (import_analytics), queued by the autopilot once per UTC day after ANALYTICS_DAILY_AFTER
  (daily_due): the last ANALYTICS_DAILY_DAYS complete days (the refresh of the recent days), then each exact range of
  ANALYTICS_DAILY_RANGES ending yesterday (the app's presets), one export each, stopping at the first failure; those
  ranges at most once per UTC day. A degraded import does not stop it, but the job's state is then DEGRADED.
- backfill: back to the earliest day LinkedIn gives, in chunks of ANALYTICS_CHUNK_DAYS, newest first.

Read side: overview() is GET /api/v1/resultados/analitica; for_pieces() gives the figures of own posts by piece and
coverage() how many publications have theirs. All from stored data only; LinkedIn is never called at request time.
Days are UTC, as LinkedIn counts them. Null is no data, never zero."""
import os
import re
import uuid
from dataclasses import asdict
from datetime import date, datetime, time, timedelta, timezone as dt_timezone
from urllib.parse import unquote, urlsplit
from django.db import transaction
from django.db.models import F, Max, Min, Q
from django.utils import timezone
from linkedin_directo.analitica import post_urn
from linkedin_directo.permitidas import ANALYTICS_DAYS
from . import miembros, operador
from .connectors import ConnectorError, get_connector
from .resultados import kpi, ratio_kpi
from .models import (ActionExecution, AnalyticsDay, AnalyticsImport, AnalyticsPost, AnalyticsRange, AnalyticsSnapshot,
                     AuditEvent, ConnectorAccount, EditorialPiece, PostComment, PostMetric)
from .permissions import require

EARLIEST=date(2025,10,10)  # LinkedIn gave nothing older on 2026-11-13; ANALYTICS_EARLIEST moves it
PRESETS={'7d':7,'14d':14,'28d':28,'90d':90,'365d':365}
POST_FIELDS=('published','kind','impressions','network_pct','outside_pct','members_reached','followers_gained',
             'profile_views','reactions','comments','shares','saves','sends','button_clicks')
DAY_FIELDS=('impressions','engagements','new_followers')
LIFETIME=('impressions','reactions','comments','shares','saves','sends','profile_views','followers_gained','members_reached')
ACTIVITY=re.compile(r'\d{10,25}')
UTC=dt_timezone.utc
EMPTY='analytics_empty'  # AnalyticsImport.error_kind of a degraded import (state ok)
DEGRADED='degradada'  # run()'s state when one of its imports was degraded
# Rows that never go to zero once seen: every day of a range has its row, and the latest posts ignore the range.
WATCHED={'days':'días','posts':'publicaciones'}

def setting(name,default):
    return os.environ.get(name,default)

def earliest():
    try:return date.fromisoformat(setting('ANALYTICS_EARLIEST','').strip())
    except ValueError:return EARLIEST

def daily_days():
    """Days refreshed by the daily import (recent days still move); 0 turns the daily import off."""
    return max(0,min(ANALYTICS_DAYS,int(setting('ANALYTICS_DAILY_DAYS','14'))))

def daily_ranges():
    """The exact ranges (days ending yesterday) the daily job also imports after its refresh, in order: members reached,
    LinkedIn's top lists and the content demographics only hold for an exact range, so the app's presets need their own
    export. Empty (or 0) turns them off; the refresh's own length is not asked twice."""
    out=[]
    for part in setting('ANALYTICS_DAILY_RANGES','7,14,28,90,365').split(','):
        days=int(part) if part.strip() else 0
        if days>0:out.append(min(ANALYTICS_DAYS,days))
    return [days for days in dict.fromkeys(out) if days!=daily_days()]

def daily_after():
    hour,_,minute=setting('ANALYTICS_DAILY_AFTER','01:30').partition(':')
    return time(int(hour),int(minute or 0))

def chunk_days():
    return max(1,min(ANALYTICS_DAYS,int(setting('ANALYTICS_CHUNK_DAYS','365'))))

def date_order():
    """The account's date order (dmy or mdy), only needed if a workbook's dates were ambiguous."""
    order=setting('ANALYTICS_DATE_ORDER','').strip()
    return order if order in ('dmy','mdy') else None

def service_ready():
    """The directo connector is on and knows where its service is (it fails closed otherwise)."""
    from .connectors_directo import live
    return live() and bool(setting('NAVEGADOR_URL','').strip()) and bool(setting('NAVEGADOR_TOKEN','').strip())

def utc_today(now=None):
    return (now or timezone.now()).astimezone(UTC).date()

def last_days(days,now=None):
    """The `days` complete UTC days that end yesterday."""
    end=utc_today(now)-timedelta(days=1)
    return end-timedelta(days=days-1),end

def clamp(start,end,now=None):
    first,last=max(start,earliest()),min(end,utc_today(now))
    if first>last:raise ValueError(f'Rango vacío: LinkedIn da analítica desde el {earliest().isoformat()} hasta hoy.')
    if (last-first).days+1>ANALYTICS_DAYS:raise ValueError(f'Un rango de LinkedIn tiene como mucho {ANALYTICS_DAYS} días.')
    return first,last

# --------------------------------------------------------------------------- import

def url_key(value):
    """A post link as one key, whatever way it was written: no scheme, query, fragment or trailing slash, the host
    lowercased without «www.». '' for anything that is not a link to a page."""
    parts=urlsplit(unquote(str(value or '').strip()))
    if parts.scheme not in ('http','https') or not parts.netloc or not parts.path.strip('/'):return ''
    return parts.netloc.lower().removeprefix('www.')+parts.path.rstrip('/')

def post_keys(value):
    """The keys one stored id or link names its post by: the urn a link or an urn names (post_urn), else the bare
    activity number the connector uses as a post's id; and a link's url_key. Never another urn kind: nothing in the code
    base turns an activity into the share or ugcPost of the same post, so those only meet through the link."""
    value=str(value or '').strip()
    if not value:return []
    urn=post_urn(value) or (f'urn:li:activity:{value}' if ACTIVITY.fullmatch(value) else '')
    return [k for k in (urn,url_key(value)) if k]

def match(index,urn,url):
    """The piece id known_posts() gives a post LinkedIn linked as `url` (urn `urn`): by its urn, else by the link."""
    return next((index[k] for k in (urn,url_key(url)) if k and k in index),None)

def known_posts(pieces=None):
    """post key (post_keys) -> piece id of the CONT-09 publications, from every id we keep of them: the official API's
    urn or the activity id the publish found (ActionExecution), the activity id or link a metrics read found
    (PostMetric, EditorialPiece.metrics) and the post id the replies read used (PostComment, and its replies.scanned
    audit, for a publication only). The first source to name a key wins. `pieces` (ids) limits it to those pieces.
    Not filtered by account: pieces belong to the publishing account, the analytics to the directo one, and both are
    the same person."""
    index,published={},set()
    def add(value,piece):
        for key in post_keys(value):index.setdefault(key,str(piece))
    def only(rows,field):return rows if pieces is None else rows.filter(**{f'{field}__in':list(pieces)})
    for piece,external_id,url in only(ActionExecution.objects.filter(proposal__capability='CONT-09',proposal__piece__isnull=False),
                                      'proposal__piece_id').values_list('proposal__piece_id','external_id','external_url'):
        add(external_id,piece);add(url,piece);published.add(str(piece))
    for piece,provider_id,url in only(PostMetric.objects,'piece_id').values_list('piece_id','provider_post_id','share_url'):
        add(provider_id,piece);add(url,piece)
    for piece,metrics in only(EditorialPiece.objects.exclude(metrics={}),'id').values_list('id','metrics'):
        add((metrics or {}).get('provider_post_id'),piece);add((metrics or {}).get('share_url'),piece)
    for piece,post_id in only(PostComment.objects,'piece_id').order_by().values_list('piece_id','provider_post_id').distinct():
        add(post_id,piece)
    scans=AuditEvent.objects.filter(action='replies.scanned',metadata__has_key='post_id')
    if pieces is not None:scans=scans.filter(target__in=[str(p) for p in pieces])
    for target,post_id in scans.order_by().values_list('target','metadata__post_id').distinct():
        if target in published:add(post_id,target)  # an audit target is only text: kept for a publication we know
    return index

def relink(index=None):
    """Links every AnalyticsPost still without its piece to the one known_posts() now names: an id learnt after the post
    was imported (a later metrics, replies or reconciliation read). Never unlinks nor moves a linked post, so it can
    run on every import. Returns how many it linked."""
    index=known_posts() if index is None else index
    linked=0
    for pk,urn,url in AnalyticsPost.objects.filter(piece__isnull=True).values_list('pk','post_urn','url'):
        piece=match(index,urn,url)
        if piece:linked+=AnalyticsPost.objects.filter(pk=pk,piece__isnull=True).update(piece_id=piece)
    return linked

def _plain(item):
    return {k:v.isoformat() if isinstance(v,date) else v for k,v in asdict(item).items()}

def _top(items,index):
    return [{'post_urn':t.urn,'url':t.url,'piece_id':match(index,t.urn,t.url),'published':t.published.isoformat() if t.published else None,
             'value':t.value} for t in items]

def store(account,book,now,index=None):
    """Upsert one Workbook; returns how many rows of each kind it brought. Posts are linked to their pieces by relink."""
    index=known_posts() if index is None else index
    for d in book.daily:
        seen={k:getattr(d,k) for k in DAY_FIELDS if getattr(d,k) is not None}  # a value seen is never erased by a gap
        AnalyticsDay.objects.update_or_create(account=account,day=d.day,defaults={**seen,'updated_at':now})
    without=0
    for p in book.recent_posts:
        if not p.urn:without+=1;continue  # an article or a newsletter: no urn to key it by
        fields={f:getattr(p,f) for f in POST_FIELDS}
        AnalyticsPost.objects.update_or_create(account=account,post_urn=p.urn,defaults={**fields,'url':p.url,'last_seen_at':now},
                                               create_defaults={**fields,'url':p.url,'first_seen_at':now,'last_seen_at':now})
    AnalyticsSnapshot.objects.update_or_create(account=account,day=utc_today(now),defaults={
        'followers':book.followers_total,'audience':[_plain(r) for r in book.audience],'captured_at':now})
    AnalyticsRange.objects.update_or_create(account=account,start=book.start,end=book.end,defaults={
        'impressions':book.impressions,'members_reached':book.members_reached,
        'top_by_engagements':_top(book.top_by_engagements,index),'top_by_impressions':_top(book.top_by_impressions,index),
        'content':None if book.content is None else [_plain(r) for r in book.content],'captured_at':now})
    return {'days':len(book.daily),'posts':len(book.recent_posts)-without,'posts_without_urn':without,
            'top_by_engagements':len(book.top_by_engagements),'top_by_impressions':len(book.top_by_impressions),
            'audience':len(book.audience),'content':None if book.content is None else len(book.content)}

def emptied(account,rows,log):
    """The WATCHED rows this import brought none of while an earlier import of the account did. A workbook whose
    format changed reads as headers only (linkedin_directo.analitica skips every row before the first it knows), never
    as an error; [] when nothing earlier had them (a new or quiet account)."""
    brought={'days':rows['days'],'posts':rows['posts']+rows['posts_without_urn']}
    earlier=AnalyticsImport.objects.filter(account=account,state=AnalyticsImport.State.OK).exclude(pk=log.pk)
    return [k for k in WATCHED if not brought[k] and earlier.filter(**{f'rows__{k}__gt':0}).exists()]

def degraded(log):
    """An import kept although it came back without rows earlier imports had (import_range); log.error says which."""
    return log.state==AnalyticsImport.State.OK and log.error_kind==EMPTY

def _finish(log,state,**fields):
    for key,value in fields.items():setattr(log,key,value)
    log.state=state;log.finished_at=timezone.now()
    log.save()

def import_range(account,start,end,trigger=AnalyticsImport.Trigger.MANUAL,now=None,connector=None):
    """One export of [start, end] (UTC days), stored, then the posts still without their piece relinked. Returns its
    AnalyticsImport: degraded (state ok, error_kind EMPTY, the reason in error) when it brought no days or no posts
    where earlier imports did. Nothing is read while the machine or the account is paused (ValueError)."""
    now=now or timezone.now()
    if account.provider!='directo':raise ValueError('La analítica de LinkedIn se importa solo de una cuenta «directo».')
    if operador.globally_paused() or ConnectorAccount.objects.filter(pk=account.pk,paused=True).exists():
        raise ValueError('Máquina o cuenta en pausa: no se lee la analítica de LinkedIn.')
    start,end=clamp(start,end,now)
    log=AnalyticsImport.objects.create(account=account,start=start,end=end,trigger=trigger,started_at=now)
    try:
        book=(connector or get_connector(account)).analytics(start,end,date_order())
    except ConnectorError as exc:
        _finish(log,AnalyticsImport.State.ERROR,error_kind=str(exc.kind)[:40],error=str(exc)[:1000])
        if exc.pause:operador.set_account_pause(account,f'Analítica detenida por el proveedor: {exc}')
        return log
    except Exception as exc:
        _finish(log,AnalyticsImport.State.ERROR,error_kind='internal',error=type(exc).__name__)
        raise
    with transaction.atomic():
        index=known_posts()
        rows=store(account,book,now,index)
        relinked=relink(index)
        empty=emptied(account,rows,log)
        reason=(f'LinkedIn devolvió el libro sin filas de {" ni de ".join(WATCHED[k] for k in empty)}, que las importaciones '
                'anteriores sí traían: puede que haya cambiado de formato. Lo que sí se leyó quedó guardado.') if empty else ''
        _finish(log,AnalyticsImport.State.OK,rows=rows,sheets=list(book.sheets),error_kind=EMPTY if empty else '',error=reason)
    operador._audit(None,'analytics.imported',account.id,start=start.isoformat(),end=end.isoformat(),trigger=trigger,rows=rows,
                    relinked=relinked,degraded=empty)
    return log

def daily_due(account,now=None):
    """Cheap check for the autopilot (no reads): a directo account with its service configured, past the hour, and no
    daily import tried yet this UTC day (one attempt a day: the next day's window covers a failed one)."""
    now=now or timezone.now()
    if account.provider!='directo' or daily_days()<=0 or not service_ready():return False
    moment=now.astimezone(UTC)
    if moment.time()<daily_after():return False
    midnight=datetime.combine(moment.date(),time(0),tzinfo=UTC)
    return not AnalyticsImport.objects.filter(account=account,trigger=AnalyticsImport.Trigger.DAILY,started_at__gte=midnight).exists()

def run(user,account,now=None):
    """import_analytics job: the last daily_days() complete days (the refresh that upserts the recent days), then each
    daily_ranges() range ending yesterday, one after the other, each with its own AnalyticsImport. Stops at the first
    failure: an account LinkedIn stopped is not asked again. The ranges go at most once per UTC day: one already tried
    today (a job run twice, or resumed) is not asked again, and none after a failure of the day. A degraded import does
    not stop the batch (the other sheets still read), but its state is then DEGRADED with the first reason in error:
    the job's text says «analitica:degradada» instead of a silent ok."""
    require(user,'operate_linkedin')
    # The batch's days come from one moment; each import keeps its own start time (overview orders them by it).
    moment=now or timezone.now()
    start,end=last_days(max(1,daily_days()),moment)
    log=import_range(account,start,end,AnalyticsImport.Trigger.DAILY,now)
    result={'state':log.state,'days':(log.rows or {}).get('days',0),'ranges':0,'error':log.error}
    if log.state!=AnalyticsImport.State.OK:return result
    def outcome(r):return {**r,'state':DEGRADED} if r['error'] else r  # past here only a degraded import sets error
    midnight=datetime.combine(utc_today(moment),time(0),tzinfo=UTC)
    today=AnalyticsImport.objects.filter(account=account,trigger=AnalyticsImport.Trigger.DAILY,started_at__gte=midnight).exclude(pk=log.pk)
    if today.filter(state=AnalyticsImport.State.ERROR).exists():return outcome(result)
    tried=set(today.values_list('start','end'))
    for days in daily_ranges():
        start,end=last_days(days,moment)
        if (start,end) in tried:continue
        log=import_range(account,start,end,AnalyticsImport.Trigger.DAILY,now)
        if log.state!=AnalyticsImport.State.OK:return {**result,'state':log.state,'error':log.error}
        result['ranges']+=1;result['error']=result['error'] or (log.error if degraded(log) else '')
    return outcome(result)

def backfill(account,start=None,chunk=None,now=None):
    """From yesterday back to `start` (the earliest day LinkedIn gives), `chunk` days per export, newest first. Stops at
    the first import that fails: an account LinkedIn stopped is not asked again."""
    chunk=chunk_days() if chunk is None else chunk
    if not 1<=chunk<=ANALYTICS_DAYS:raise ValueError(f'El trozo va de 1 a {ANALYTICS_DAYS} días.')
    first=max(start or earliest(),earliest());end=utc_today(now)-timedelta(days=1);logs=[]
    while end>=first:
        begin=max(first,end-timedelta(days=chunk-1))
        logs.append(import_range(account,begin,end,AnalyticsImport.Trigger.BACKFILL,now))
        if logs[-1].state!=AnalyticsImport.State.OK:break
        end=begin-timedelta(days=1)
    return logs

# --------------------------------------------------------------------------- read side (GET /api/v1/resultados/analitica)

NO_ACCOUNT='Aún no hay una cuenta de LinkedIn conectada por el navegador (proveedor «directo»).'
REACHED_REASON=('LinkedIn da los miembros alcanzados solo para un rango completo y no se pueden sumar por días; este '
                'periodo exacto no se ha importado.')
TOP_REASON=('LinkedIn da sus publicaciones principales solo para el rango que se le pide; este periodo exacto no se ha '
            'importado.')

def _day(value,name):
    try:return date.fromisoformat(str(value))
    except ValueError:raise ValueError(f'{name} debe ser una fecha AAAA-MM-DD.') from None

def account_for(account_id=None,member=None):
    """The member's directo account whose analytics are shown: `account_id` if it is one of hers, else the one imported
    last. Without a member, miembros.default_member() (organizaciones, phase 1); another member's account is refused like
    an unknown one."""
    accounts=miembros.accounts(miembros.resolve(member),['directo'])
    if account_id:
        try:found=accounts.filter(id=uuid.UUID(str(account_id))).first()
        except ValueError:found=None
        if not found:raise ValueError('cuenta debe ser el id de una cuenta «directo».')
        return found
    # Several directo accounts of the member: the one imported last (normally there is one).
    return accounts.annotate(last=Max('analytics_imports__finished_at',filter=Q(analytics_imports__state='ok'))).order_by(
        F('last').desc(nulls_last=True),'created_at').first()

def period(periodo,desde,hasta,last_stored,now):
    """(first, last, preset). A preset ends yesterday, or on the last day stored when the imports are behind."""
    if desde or hasta:
        if not (desde and hasta):raise ValueError('desde y hasta van juntos (AAAA-MM-DD).')
        first,last=_day(desde,'desde'),_day(hasta,'hasta')
        if first>last:raise ValueError('desde no puede ser posterior a hasta.')
        if (last-first).days+1>ANALYTICS_DAYS:raise ValueError(f'El periodo tiene como mucho {ANALYTICS_DAYS} días.')
        return first,last,None
    preset=periodo or '28d'
    if preset not in PRESETS:raise ValueError('periodo debe ser 7d, 14d, 28d, 90d o 365d.')
    last=utc_today(now)-timedelta(days=1)
    if last_stored and last_stored<last:last=last_stored
    return last-timedelta(days=PRESETS[preset]-1),last,preset

def _span(first,last):
    return [first+timedelta(days=i) for i in range((last-first).days+1)]

def _sum(rows,field):
    values=[getattr(r,field) for r in rows if getattr(r,field) is not None]
    return (sum(values) if values else None),len(values)

def totals(now_rows,before_rows,days):
    """Sum of each daily figure over the days that have it. Compared only when both periods have every day."""
    labels={'impressions':'Impresiones de tus publicaciones por día, sumadas en el periodo (LinkedIn).',
            'engagements':'Interacciones con tus publicaciones por día, sumadas en el periodo (LinkedIn).',
            'new_followers':'Seguidores nuevos que LinkedIn cuenta por día, sumados en el periodo.'}
    out={}
    for field,definition in labels.items():
        value,seen=_sum(now_rows,field);previous,seen_before=_sum(before_rows,field)
        out[field]=kpi(value,previous if seen_before==days else None,definition,
                       reason='Sin datos importados de LinkedIn en este periodo.',comparable=seen==days and seen_before==days,
                       days=days,days_with_data=seen)
    def pair(rows):
        both=[r for r in rows if r.impressions is not None and r.engagements is not None]
        return (sum(r.engagements for r in both),sum(r.impressions for r in both)) if both else None
    out['engagement_rate']=ratio_kpi(pair(now_rows),pair(before_rows),'Interacciones frente a impresiones en el periodo (LinkedIn).',
                                     'interacciones / impresiones × 100','Sin datos importados de LinkedIn en este periodo.',
                                     'Sin impresiones en el periodo.',
                                     comparable=out['impressions']['comparable'] and out['engagements']['comparable'])
    return out

def _reached(account,first,last,previous):
    exact=AnalyticsRange.objects.filter(account=account,start=first,end=last).first()
    before=AnalyticsRange.objects.filter(account=account,start=previous[0],end=previous[1]).first()
    return kpi(exact.members_reached if exact else None,before.members_reached if before else None,
               'Personas distintas que vieron tus publicaciones en el periodo, según LinkedIn para ese rango exacto.',
               reason=REACHED_REASON if not exact else 'LinkedIn no dio el dato.',captured_at=exact.captured_at if exact else None)

def _post(p):
    return {'post_urn':p.post_urn,'url':p.url,'piece_id':str(p.piece_id) if p.piece_id else None,'published':p.published,
            **{f:getattr(p,f) for f in POST_FIELDS if f!='published'},'as_of':p.last_seen_at}

def grouped(rows):
    """Demographic rows by LinkedIn's own group labels, in its order."""
    groups={}
    for row in rows or []:groups.setdefault(row.get('group') or '',[]).append(
        {k:row.get(k) for k in ('label','pct','below','value')})
    return [{'group':g,'rows':r} for g,r in groups.items()]

def _content(account,first,last):
    """The content demographics of the imported range nearest to the period, labelled with its own range."""
    ranges=list(AnalyticsRange.objects.filter(account=account,content__isnull=False).order_by('-captured_at'))
    if not ranges:return None
    best=min(ranges,key=lambda r:abs((r.start-first).days)+abs((r.end-last).days))
    return {'desde':best.start,'hasta':best.end,'exacto':(best.start,best.end)==(first,last),'captured_at':best.captured_at,
            'groups':grouped(best.content)}

def overview(account_id=None,periodo=None,desde=None,hasta=None,now=None,member=None):
    now=now or timezone.now()
    account=account_for(account_id,member)
    if account is None:return {'disponible':False,'motivo':NO_ACCOUNT}
    bounds=AnalyticsDay.objects.filter(account=account).aggregate(first=Min('day'),last=Max('day'))
    first,last,preset=period(periodo,desde,hasta,bounds['last'],now)
    days=(last-first).days+1;previous=(first-timedelta(days=days),first-timedelta(days=1))
    stored={d.day:d for d in AnalyticsDay.objects.filter(account=account,day__gte=previous[0],day__lte=last)}
    now_rows=[stored[d] for d in _span(first,last) if d in stored];before_rows=[stored[d] for d in _span(*previous) if d in stored]
    ok=AnalyticsImport.objects.filter(account=account,state=AnalyticsImport.State.OK).order_by('-finished_at').first()
    latest=AnalyticsImport.objects.filter(account=account).exclude(state=AnalyticsImport.State.RUNNING).order_by('-started_at').first()
    # The last import failed, or was kept although it came back empty (degraded): either is shown until one goes well.
    failed=latest if latest and (latest.state==AnalyticsImport.State.ERROR and (not ok or latest.started_at>ok.started_at)
                                 or degraded(latest)) else None
    snapshots=list(AnalyticsSnapshot.objects.filter(account=account,day__gte=first,day__lte=last+timedelta(days=1)).order_by('day'))
    audience=AnalyticsSnapshot.objects.filter(account=account).order_by('-day').first()
    top=AnalyticsRange.objects.filter(account=account,start=first,end=last).first()
    posts=AnalyticsPost.objects.filter(account=account,published__gte=first,published__lte=last).order_by(
        F('impressions').desc(nulls_last=True),'-published')
    return {
        'disponible':ok is not None,
        'motivo':None if ok else 'Aún no se ha importado la analítica de LinkedIn de esta cuenta.',
        'cuenta':{'id':str(account.id),'label':account.label},
        'periodo':{'desde':first,'hasta':last,'dias':days,'preset':preset,'zona_horaria':'UTC',
                   'anterior':{'desde':previous[0],'hasta':previous[1]}},
        'limites':{'primer_dia':bounds['first'],'ultimo_dia':bounds['last'],'linkedin_desde':earliest()},
        'actualizado':{'at':ok.finished_at,'desde':ok.start,'hasta':ok.end,'tipo':ok.trigger} if ok else None,
        'ultimo_error':{'at':failed.started_at,'tipo':failed.trigger,'kind':failed.error_kind,'error':failed.error} if failed else None,
        'totales':{**totals(now_rows,before_rows,days),'members_reached':_reached(account,first,last,previous)},
        'serie':[{'date':d,**{f:getattr(stored[d],f) if d in stored else None for f in DAY_FIELDS}} for d in _span(first,last)],
        'seguidores':{'total':snapshots[-1].followers if snapshots else None,'at':snapshots[-1].day if snapshots else None,
                      'serie':[{'date':s.day,'value':s.followers} for s in snapshots],
                      'definition':'Total de seguidores que LinkedIn da el día en que se importa (no el de una fecha pasada); '
                                   'la última captura del periodo o del día siguiente.',
                      'unavailable_reason':None if snapshots else 'Sin captura del total de seguidores en este periodo.'},
        'posts':{'publicados':[_post(p) for p in posts],
                 'definition':'Publicaciones del periodo con sus cifras de toda la vida, tal como LinkedIn las dio la última vez '
                              'que estaban entre las más recientes (as_of).',
                 'top_linkedin':{'desde':top.start,'hasta':top.end,'captured_at':top.captured_at,
                                 'por_interacciones':top.top_by_engagements,'por_impresiones':top.top_by_impressions} if top else None,
                 'top_unavailable_reason':None if top else TOP_REASON},
        'demografia':{'audiencia':{'at':audience.day,'groups':grouped(audience.audience)} if audience else None,
                      'contenido':_content(account,first,last)},
    }

# --------------------------------------------------------------------------- by piece (agents and results views)

def _in_range(pieces):
    """{piece id: what the latest range imported says of it} for pieces among its top posts: the range ending last, the
    longest of those (the one most posts fit in). Matched by the same ids as known_posts(), now: an id learnt after
    the import counts. Values hold for that range only, never for the post's lifetime."""
    span=AnalyticsRange.objects.order_by('-end','start','-captured_at').first()
    if span is None:return {}
    index=known_posts(pieces);days=(span.end-span.start).days+1;out={}
    for field,top in (('engagements',span.top_by_engagements),('impressions',span.top_by_impressions)):
        for entry in top or []:
            piece=entry.get('piece_id') or match(index,entry.get('post_urn') or '',entry.get('url') or '')
            if piece in pieces:
                out.setdefault(piece,{'impressions':None,'engagements':None,'source':'rango','label':f'{days} días, del '
                               f'{span.start.isoformat()} al {span.end.isoformat()}','days':days,'desde':span.start,'hasta':span.end,
                               'captured_at':span.captured_at})[field]=entry.get('value')
    return out

def for_pieces(piece_ids):
    """{piece id, as given: figures} of own posts, for agents and views, from stored data only:
    - a piece linked to an AnalyticsPost: LIFETIME and last_seen_at, as LinkedIn last listed it among the latest posts,
      'source': 'vida'. One query for all of them (the post seen last, should two name the same piece);
    - else a piece among the top posts of the latest range imported (_in_range): impressions and engagements IN THAT
      RANGE, 'source': 'rango', with its label, days and dates, so they are never taken for lifetime figures. Read
      only when a piece is left, and nothing is stored for it;
    - else nothing: the piece is left out (no data, never zero)."""
    given={str(p):p for p in piece_ids}
    out={}
    for row in AnalyticsPost.objects.filter(piece_id__in=list(given)).order_by('last_seen_at').values('piece_id',*LIFETIME,'last_seen_at'):
        key=given[str(row.pop('piece_id'))];out[key]={**row,'source':'vida'}  # the right side is evaluated first: pop before
    left={key for key,p in given.items() if p not in out}
    if left:out.update({given[key]:figures for key,figures in _in_range(left).items()})
    return out

def for_piece(piece):
    """for_pieces() of one piece (or its id); None when nothing is stored for it."""
    pid=getattr(piece,'pk',piece)
    return for_pieces([pid]).get(pid)

def coverage(now=None):
    """How many own publications have their LinkedIn analytics: the pieces of CONT-09 executions that wrote (confirmed
    or sent, wrote=True) and started by `now`, those linked to an AnalyticsPost, and the ids of the others in order of
    publication (the gap a results view or a diagnosis shows)."""
    now=now or timezone.now()
    rows=ActionExecution.objects.filter(proposal__capability='CONT-09',proposal__piece__isnull=False,wrote=True,started_at__lte=now,
                                        state__in=(ActionExecution.State.CONFIRMED,ActionExecution.State.SENT)).order_by('started_at')
    pieces=list(dict.fromkeys(str(p) for p in rows.values_list('proposal__piece_id',flat=True)))
    linked={str(p) for p in AnalyticsPost.objects.filter(piece_id__in=pieces).values_list('piece_id',flat=True)}
    return {'published':len(pieces),'linked':len(linked),'unlinked_piece_ids':[p for p in pieces if p not in linked]}
