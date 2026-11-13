"""Creator analytics of a `directo` account (docs/metricas-resultados.md, «Analítica de LinkedIn»).

Import: LinkedIn's export dialog, one call through the navegador service (linkedin_directo.analitica reads it), kept in
AnalyticsDay (per UTC day), AnalyticsPost (lifetime figures per post), AnalyticsSnapshot (follower total and audience
demographics per capture day), AnalyticsRange (what only holds for the exact range: totals, top lists, content
demographics) and AnalyticsImport (one row per export asked, ok or not). Only reads LinkedIn.
- import_range: one range, upserted. LinkedIn's errors land in the AnalyticsImport row; one that stops the account
  (login, checkpoint, 401/403/429/999, the service's stop) also pauses it, as the other directo reads do.
- run: the daily job (import_analytics), the last ANALYTICS_DAILY_DAYS complete days, queued by the autopilot once per
  UTC day after ANALYTICS_DAILY_AFTER (daily_due).
- backfill: back to the earliest day LinkedIn gives, in chunks of ANALYTICS_CHUNK_DAYS, newest first.

Read side: overview() is GET /api/v1/resultados/analitica, from stored data only; LinkedIn is never called at request
time. Days are UTC, as LinkedIn counts them. Null is no data, never zero."""
import os
import re
import uuid
from dataclasses import asdict
from datetime import date, datetime, time, timedelta, timezone as dt_timezone
from django.db import transaction
from django.db.models import F, Max, Min, Q
from django.utils import timezone
from linkedin_directo.analitica import post_urn
from linkedin_directo.permitidas import ANALYTICS_DAYS
from . import operador
from .connectors import ConnectorError, get_connector
from .resultados import kpi, ratio_kpi
from .models import (ActionExecution, AnalyticsDay, AnalyticsImport, AnalyticsPost, AnalyticsRange, AnalyticsSnapshot,
                     ConnectorAccount, EditorialPiece, PostMetric)
from .permissions import require

EARLIEST=date(2025,10,10)  # LinkedIn gave nothing older on 2026-11-13; ANALYTICS_EARLIEST moves it
PRESETS={'7d':7,'14d':14,'28d':28,'90d':90,'365d':365}
POST_FIELDS=('published','kind','impressions','network_pct','outside_pct','members_reached','followers_gained',
             'profile_views','reactions','comments','shares','saves','sends','button_clicks')
DAY_FIELDS=('impressions','engagements','new_followers')
ACTIVITY=re.compile(r'\d{10,25}')
UTC=dt_timezone.utc

def setting(name,default):
    return os.environ.get(name,default)

def earliest():
    try:return date.fromisoformat(setting('ANALYTICS_EARLIEST','').strip())
    except ValueError:return EARLIEST

def daily_days():
    """Days refreshed by the daily import (recent days still move); 0 turns the daily import off."""
    return max(0,min(ANALYTICS_DAYS,int(setting('ANALYTICS_DAILY_DAYS','14'))))

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

def known_posts():
    """post urn -> piece id of the CONT-09 publications, from every id we keep of them: the official API's urn
    (ActionExecution), and the activity id or link a read found (PostMetric, EditorialPiece.metrics). Not filtered by
    account: pieces belong to the publishing account, the analytics to the directo one, and both are the same person."""
    index={}
    def add(value,piece):
        value=str(value or '')
        urn=post_urn(value) or (f'urn:li:activity:{value}' if ACTIVITY.fullmatch(value) else '')
        if urn:index.setdefault(urn,str(piece))
    for piece,external_id,url in ActionExecution.objects.filter(proposal__capability='CONT-09',proposal__piece__isnull=False
                                                                ).values_list('proposal__piece_id','external_id','external_url'):
        add(external_id,piece);add(url,piece)
    for piece,provider_id,url in PostMetric.objects.values_list('piece_id','provider_post_id','share_url'):
        add(provider_id,piece);add(url,piece)
    for piece,metrics in EditorialPiece.objects.exclude(metrics={}).values_list('id','metrics'):
        add((metrics or {}).get('unipile_post_id'),piece);add((metrics or {}).get('share_url'),piece)
    return index

def _plain(item):
    return {k:v.isoformat() if isinstance(v,date) else v for k,v in asdict(item).items()}

def _top(items,index):
    return [{'post_urn':t.urn,'url':t.url,'piece_id':index.get(t.urn),'published':t.published.isoformat() if t.published else None,
             'value':t.value} for t in items]

def store(account,book,now):
    """Upsert one Workbook; returns how many rows of each kind it brought."""
    index=known_posts()
    for d in book.daily:
        seen={k:getattr(d,k) for k in DAY_FIELDS if getattr(d,k) is not None}  # a value seen is never erased by a gap
        AnalyticsDay.objects.update_or_create(account=account,day=d.day,defaults={**seen,'updated_at':now})
    without=0
    for p in book.recent_posts:
        if not p.urn:without+=1;continue  # an article or a newsletter: no urn to key it by
        fields={f:getattr(p,f) for f in POST_FIELDS}
        if index.get(p.urn):fields['piece_id']=index[p.urn]
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

def _finish(log,state,**fields):
    for key,value in fields.items():setattr(log,key,value)
    log.state=state;log.finished_at=timezone.now()
    log.save()

def import_range(account,start,end,trigger=AnalyticsImport.Trigger.MANUAL,now=None,connector=None):
    """One export of [start, end] (UTC days), stored. Returns its AnalyticsImport. Nothing is read while the machine
    or the account is paused (ValueError)."""
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
        rows=store(account,book,now)
        _finish(log,AnalyticsImport.State.OK,rows=rows,sheets=list(book.sheets))
    operador._audit(None,'analytics.imported',account.id,start=start.isoformat(),end=end.isoformat(),trigger=trigger,rows=rows)
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
    """import_analytics job: the last daily_days() complete days."""
    require(user,'operate_linkedin')
    start,end=last_days(max(1,daily_days()),now)
    log=import_range(account,start,end,AnalyticsImport.Trigger.DAILY,now)
    return {'state':log.state,'days':(log.rows or {}).get('days',0),'error':log.error}

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

def account_for(account_id=None):
    accounts=ConnectorAccount.objects.filter(provider='directo')
    if account_id:
        try:found=accounts.filter(id=uuid.UUID(str(account_id))).first()
        except ValueError:found=None
        if not found:raise ValueError('cuenta debe ser el id de una cuenta «directo».')
        return found
    # Several directo accounts: the one imported last (single workspace: normally there is one).
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

def overview(account_id=None,periodo=None,desde=None,hasta=None,now=None):
    now=now or timezone.now()
    account=account_for(account_id)
    if account is None:return {'disponible':False,'motivo':NO_ACCOUNT}
    bounds=AnalyticsDay.objects.filter(account=account).aggregate(first=Min('day'),last=Max('day'))
    first,last,preset=period(periodo,desde,hasta,bounds['last'],now)
    days=(last-first).days+1;previous=(first-timedelta(days=days),first-timedelta(days=1))
    stored={d.day:d for d in AnalyticsDay.objects.filter(account=account,day__gte=previous[0],day__lte=last)}
    now_rows=[stored[d] for d in _span(first,last) if d in stored];before_rows=[stored[d] for d in _span(*previous) if d in stored]
    ok=AnalyticsImport.objects.filter(account=account,state=AnalyticsImport.State.OK).order_by('-finished_at').first()
    latest=AnalyticsImport.objects.filter(account=account).exclude(state=AnalyticsImport.State.RUNNING).order_by('-started_at').first()
    failed=latest if latest and latest.state==AnalyticsImport.State.ERROR and (not ok or latest.started_at>ok.started_at) else None
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
