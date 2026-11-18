"""Bucle de resultados: end-to-end proof that «the information we need arrives, the agents use it, and everything returns to
its cycle» (manage.py bucle_resultados). For the last N days it answers three questions per flow, with counts and the ids
of what is broken:
- ¿Llega? (llega) what the collectors stored: the cuts of own posts (PostMetric 24 h/72 h/7 d) with the pending reason of
  the latest metrics.collected, LinkedIn analytics (analitica), the outcome of own comments (INT-03, 72 h) and of network
  actions (RED-01/02/04, 7 d) in ActionOutcome, web research with findings, one WeeklySummary per finished week, the
  canary, profile views and the signals of the contacts classified;
- ¿Lo usan los agentes? (usan) whether the cycles of the window froze each input as a non-empty runtime snapshot
  (CycleLedger.progress_ledger['snapshots'], orquestacion.Runtime.snapshot): editorial_context (pieza_diaria; with
  metrics of earlier pieces, not only sin_dato), referent_signals and comment_outcomes (the comment drafter),
  network_engaged (the network plan); and which sections of WeeklySummary.stats had data. A snapshot name no cycle of
  the window carries is «no_se_registra», never zero;
- ¿Vuelve al ciclo? (vuelve) whether the latest summary's recommendations reach the director (resumen_semanal.for_director
  and the director's later snapshots), and whether this week's WeeklyPlan carries its types and its pieces were prepared
  after it.
Each check has an `estado`: ok, parcial, roto, sin_datos (nothing to check) or no_se_registra; `veredictos` folds them per
flow into completo, parcial or roto. trace_piece() and trace_action() follow one item link by link: ok, falta (with why),
aun_no_toca or no_aplica.

Read-only: it never writes, never calls LinkedIn (no connector) nor a paid provider. Ids, states and counts only, never a
text or a name. Pure functions returning dicts; the command renders them."""
import uuid
from datetime import datetime, time, timedelta
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone
from . import analitica, desenlaces, editorial, estrategia, metricas, miembros, operador, resumen_semanal
from .models import (ActionExecution, ActionOutcome, ActionProposal, AudienceSnapshot, AuditEvent, CanaryRun, Contact, CycleLedger,
                     EditorialPiece, ObservedPost, PostMetric, WebResearchRun, WeeklyPlan, WeeklySummary)

DIAS=14
MAX_IDS=50  # broken items listed per check; the counts always cover all of them
CANARY_HOURS=36  # the canary runs once a day: an older run is stale
# Snapshot name: (cycle, job kind that opened it or None, where it is frozen). comment_outcomes and network_engaged come
# with parallel work packages: until they land no cycle carries them.
SNAPSHOTS={'editorial_context':('pieza_diaria',None,'editorial.py _run'),
           'referent_signals':('red','propose_comment','operador.py propose_comment y run_job'),
           'comment_outcomes':('red','propose_comment','operador.py propose_comment (paquete paralelo)'),
           'network_engaged':('red','plan_network','red.py plan (paquete paralelo)')}
CORE_SECTIONS=('publicaciones','comentarios','red')  # the summary sections the results loop depends on
FLOWS={'posts':('llega.posts','llega.analitica','usan.editorial_context'),
       'comentarios':('llega.comentarios','usan.referent_signals','usan.comment_outcomes'),
       'red':('llega.red','llega.contactos','usan.network_engaged'),
       'investigacion':('llega.investigacion',),
       'resumen_semanal':('llega.resumen_semanal','usan.resumen_stats','vuelve.recomendaciones','vuelve.plan_semanal'),
       'cuenta':('llega.canario','llega.visitas_perfil')}
SECTION={'CONT-09':'publicaciones','INT-03':'comentarios','RED-01':'red','RED-02':'red','RED-04':'red'}
MISSING=object()

# --------------------------------------------------------------------------- helpers

def _local(moment):
    return moment.astimezone(operador.local_tz())

def _ids(values):
    return [str(v) for v in values][:MAX_IDS]

def _pct(part,total):
    return round(part*100/total,1) if total else None

def _state(total,good):
    """ok when every item is good, roto when none is, parcial in between; sin_datos with nothing to check."""
    if not total:return 'sin_datos'
    return 'ok' if good==total else 'roto' if not good else 'parcial'

def _uuid(value):
    try:return uuid.UUID(str(value))
    except ValueError:return None

def plain(value):
    """A stored snapshot as plain data (orquestacion.pack's markers undone) without touching the database: a model
    reference or a blob stays its marker."""
    if isinstance(value,list):return [plain(v) for v in value]
    if not isinstance(value,dict):return value
    if '__dict__' in value:return {k:plain(v) for k,v in value['__dict__'].items()}
    if '__tuple__' in value:return [plain(v) for v in value['__tuple__']]
    if '__dataclass__' in value:return plain(value.get('value'))
    return value

def filled(value):
    """Whether an input carries something: a dict with any filled value (its 'limitations' notes do not count), a
    non-empty list, any other truthy value."""
    if isinstance(value,dict):return any(filled(v) for k,v in value.items() if k!='limitations')
    if isinstance(value,(list,tuple)):return bool(value)
    return bool(value)

def _mentions(value,needles):
    """Whether any key or scalar inside `value` is one of `needles` (ids or iso dates)."""
    if isinstance(value,dict):return any(str(k) in needles or _mentions(v,needles) for k,v in value.items())
    if isinstance(value,(list,tuple)):return any(_mentions(v,needles) for v in value)
    return value is not None and str(value) in needles

def _cycles(name,since,now):
    cycle,trigger,_=SNAPSHOTS[name]
    rows=CycleLedger.objects.filter(cycle=cycle,created_at__gte=since,created_at__lte=now)
    return rows.filter(task_ledger__facts__trigger=trigger) if trigger else rows

def _values(rows,name):
    """[(cycle id, created_at, plain snapshot or MISSING)] of the cycles `rows`, oldest first."""
    found=dict(rows.filter(progress_ledger__snapshots__has_key=name).values_list('id',f'progress_ledger__snapshots__{name}'))
    return [(str(i),at,plain(found[i]) if i in found else MISSING) for i,at in rows.order_by('created_at').values_list('id','created_at')]

def _pending(now):
    """{(piece id, cut): reason} of the latest metrics.collected of each account (metricas.collect's summary['pending'])."""
    out={};accounts=set()
    for target,metadata in AuditEvent.objects.filter(action='metrics.collected',created_at__lte=now).order_by('-created_at').values_list('target','metadata')[:20]:
        if target in accounts:continue
        accounts.add(target)
        pending=(metadata or {}).get('pending')
        for item in pending if isinstance(pending,list) else []:  # older events stored only a count
            if not isinstance(item,dict):continue
            for cut in item.get('cuts') or []:out.setdefault((str(item.get('piece')),cut),item.get('reason'))
    return out

def _summary_due(week):
    """When the autopilot queues the summary of `week`: the next Monday at WEEKLY_SUMMARY_TIME, local."""
    try:at=resumen_semanal.summary_time()
    except ValueError:at=time(7,30)
    return datetime.combine(week+timedelta(days=7),at,tzinfo=operador.local_tz())

def _weeks(since,now):
    """Mondays of the finished local ISO weeks that overlap the window, oldest first."""
    today=_local(now).date();monday=today-timedelta(days=today.weekday())
    week=_local(since).date();week-=timedelta(days=week.weekday());out=[]
    while week+timedelta(days=7)<=monday:out.append(week);week+=timedelta(days=7)
    return out

def _director_rows(value):
    """The published rows of the director's history in an editorial_context snapshot."""
    history=((value if isinstance(value,dict) else {}).get('director_input') or {}).get('history') or []
    return [r for r in history if isinstance(r,dict) and r.get('status')=='published']

def _has_metrics(row):
    return any(isinstance(v,dict) for v in (row.get('results') or {}).values())

def _expects_metrics(row):
    return any(v!='pendiente' for v in (row.get('results') or {}).values())

def _recommended(value):
    return bool(((value if isinstance(value,dict) else {}).get('director_input') or {}).get('weekly_recommendations'))

# --------------------------------------------------------------------------- ¿llega?

def _posts(since,now):
    """Published own posts of the window (metricas.PUBLISHED) and their due cuts; returns (check, piece ids)."""
    started={}
    for piece,at in (ActionExecution.objects.filter(metricas.PUBLISHED,proposal__capability='CONT-09',proposal__piece__isnull=False,
                                                    started_at__gte=since,started_at__lte=now).order_by('started_at')
                     .values_list('proposal__piece_id','started_at')):
        started.setdefault(str(piece),at)
    have={}
    for piece,kind in PostMetric.objects.filter(piece_id__in=list(started),captured_at__lte=now).values_list('piece_id','kind'):
        have.setdefault(str(piece),set()).add(kind)
    pending=_pending(now);cuts={k:{'debidos':0,'con_corte':0} for k in metricas.AGES};missing=[]
    for piece,at in started.items():
        due=[k for k,age in metricas.AGES.items() if now-at>=age];lacking=[k for k in due if k not in have.get(piece,set())]
        for k in due:cuts[k]['debidos']+=1;cuts[k]['con_corte']+=int(k not in lacking)
        if lacking:missing.append({'pieza':piece,'cortes':lacking,'motivo':next((pending[(piece,k)] for k in lacking if (piece,k) in pending),None)})
    due=sum(c['debidos'] for c in cuts.values())
    return {'estado':_state(due,due-sum(len(m['cortes']) for m in missing)),'publicados':len(started),'cortes':cuts,
            'faltan':missing[:MAX_IDS],'n_faltan':len(missing)},list(started)

def _analytics(pieces,now):
    """LinkedIn analytics of the window's posts (analitica.for_pieces: lifetime 'vida' or only 'rango') and the all-time
    coverage (analitica.coverage)."""
    figures=analitica.for_pieces(pieces);total=analitica.coverage(now)
    life=[p for p in pieces if (figures.get(p) or {}).get('source')=='vida']
    span=[p for p in pieces if (figures.get(p) or {}).get('source')=='rango']
    state=_state(len(pieces),len(life))
    if state=='roto' and span:state='parcial'
    return {'estado':state,'publicados':len(pieces),'con_analitica':len(life),'solo_rango':len(span),
            'sin_analitica':_ids(p for p in pieces if p not in figures),
            'total':{'publicados':total['published'],'con_analitica':total['linked'],'sin_analitica':len(total['unlinked_piece_ids'])}}

def _measured(capabilities,kind,since,now,**filters):
    """Executions done (desenlaces.DONE) in the window and old enough for their `kind` outcome: which have it by `now`
    and which not, the latter with whether its moment is still open (en_plazo) or gone (plazo_vencido)."""
    age,late=desenlaces.WINDOWS[kind]
    rows=list(ActionExecution.objects.filter(proposal__capability__in=capabilities,state__in=desenlaces.DONE,started_at__gte=since,
                                             started_at__lte=now,**filters).order_by('started_at').values_list('id','proposal_id','started_at'))
    due=[r for r in rows if now-r[2]>=age]
    have=set(ActionOutcome.objects.filter(execution_id__in=[r[0] for r in due],kind=kind,captured_at__lte=now).values_list('execution_id',flat=True))
    missing=[{'ejecucion':str(e),'propuesta':str(p),'motivo':'plazo_vencido' if now-at>late else 'en_plazo'} for e,p,at in due if e not in have]
    return {'estado':_state(len(due),len(have)),'medibles':len(due),'con_desenlace':len(have),'aun_no_toca':len(rows)-len(due),
            'sin_desenlace':missing[:MAX_IDS],'n_sin_desenlace':len(missing)}

def _research(since,now):
    """Web research runs of the window that ended (not running, skipped or withdrawn): with findings or not, per key kind."""
    rows=list(WebResearchRun.objects.filter(created_at__gte=since,created_at__lte=now).exclude(state__in=('running','skipped','withdrawn'))
              .order_by('created_at').values_list('key','state','result'))
    kinds={};empty=[]
    for key,state,result in rows:
        found=bool((result or {}).get('findings'));entry=kinds.setdefault(key.split(':',1)[0],{'corridas':0,'con_hallazgos':0})
        entry['corridas']+=1;entry['con_hallazgos']+=int(found)
        if not found:empty.append({'clave':key,'estado':state})
    return {'estado':_state(len(rows),len(rows)-len(empty)),'corridas':len(rows),'con_hallazgos':len(rows)-len(empty),'por_tipo':kinds,
            'sin_hallazgos':empty[:MAX_IDS],'n_sin_hallazgos':len(empty)}

def _summaries(weeks,now,member=None):
    """One WeeklySummary of hers per finished week, and how many entries its validator dropped."""
    stored={s.week_start:s for s in miembros.own(WeeklySummary.objects.filter(week_start__in=weeks,created_at__lte=now),member)}
    rows=[]
    for week in weeks:
        s=stored.get(week)
        if s:
            analysis=s.analysis or {}
            rows.append({'semana':week.isoformat(),'estado':'ok','resumen':str(s.id),'estado_resumen':s.state,
                         'recomendaciones':len(analysis.get('recomendaciones') or []),
                         'descartadas':len((analysis.get('validacion') or {}).get('descartado') or [])})
        else:rows.append({'semana':week.isoformat(),'estado':'aun_no_toca' if now<_summary_due(week) else 'falta'})
    due=[r for r in rows if r['estado']!='aun_no_toca'];missing=[r['semana'] for r in rows if r['estado']=='falta']
    return {'estado':_state(len(due),len(due)-len(missing)),'automatico':resumen_semanal.enabled(),'semanas':rows,'faltan':missing}

def _canary(now):
    run=CanaryRun.objects.filter(started_at__lte=now).order_by('-started_at').first()
    if run is None:return {'estado':'sin_datos','ultimo':None,'motivo':'El canario nunca corrió (sin cuenta directo).'}
    hours=round((now-run.started_at).total_seconds()/3600,1)
    state=('roto' if run.state in (CanaryRun.State.BROKEN,CanaryRun.State.HALTED,CanaryRun.State.NOT_RUN)
           else 'parcial' if run.state==CanaryRun.State.RUNNING or hours>CANARY_HOURS else 'ok')
    return {'estado':state,'ultimo':{'id':run.pk,'estado':run.state,'edad_horas':hours,'error':run.error_kind or None}}

def _profile_views(since,now,member=None):
    today=_local(now).date();audience=miembros.own(AudienceSnapshot.objects.all(),member)  # her audience
    rows=list(audience.filter(day__gte=_local(since).date(),day__lte=today).order_by('-day').values_list('day','profile_views'))
    latest=audience.filter(day__lte=today).order_by('-day').values_list('day','profile_views','profile_views_days').first()
    if latest is None:return {'estado':'roto','ultima':None,'motivo':'Ninguna captura de audiencia.'}
    views=sum(1 for _,v in rows if v is not None)
    return {'estado':'ok' if latest[1] is not None else 'parcial' if views else 'roto',
            'ultima':{'dia':latest[0].isoformat(),'visitas_nulas':latest[1] is None,'ventana_dias':latest[2]},
            'capturas':len(rows),'con_visitas':views,'sin_visitas':[d.isoformat() for d,v in rows if v is None][:MAX_IDS]}

def _contacts(since,now):
    """Contacts classified in the window (classification.classified_at) whose profile signals had a bio or followers."""
    classified=[]
    for cid,at,signals in Contact.objects.filter(classification__has_key='classified_at').values_list('id','classification__classified_at','signals'):
        try:moment=datetime.fromisoformat(str(at))
        except ValueError:continue
        if moment.tzinfo is not None and since<=moment<=now:classified.append((cid,signals or {}))
    bio=sum(1 for _,s in classified if s.get('bio'));followers=sum(1 for _,s in classified if s.get('followers') is not None)
    bare=[cid for cid,s in classified if not s.get('bio') and s.get('followers') is None]
    return {'estado':_state(len(classified),len(classified)-len(bare)),'clasificados':len(classified),'con_bio':bio,'con_seguidores':followers,
            'pct_bio':_pct(bio,len(classified)),'pct_seguidores':_pct(followers,len(classified)),'sin_senales':_ids(bare),'n_sin_senales':len(bare)}

# --------------------------------------------------------------------------- ¿lo usan los agentes?

def _usage(name,since,now):
    cycle,trigger,producer=SNAPSHOTS[name]
    rows=_values(_cycles(name,since,now),name);carried=[(i,v) for i,_,v in rows if v is not MISSING]
    out={'ciclo':cycle+(f':{trigger}' if trigger else ''),'productor':producer,'ciclos':len(rows),'con_snapshot':len(carried),
         'sin_snapshot':_ids(i for i,_,v in rows if v is MISSING)}
    if not rows:return dict(out,estado='sin_datos',con_dato=None)
    if not carried:return dict(out,estado='no_se_registra',con_dato=None)
    if name=='editorial_context':
        # The director's history: a published piece whose cut is due should come with its metrics, not only sin_dato.
        expecting=[i for i,v in carried if any(_expects_metrics(r) for r in _director_rows(v))]
        good={i for i,v in carried if any(_has_metrics(r) for r in _director_rows(v))}&set(expecting)
        return dict(out,estado=_state(len(expecting),len(good)),con_dato=len(good),esperaban_metricas=len(expecting),
                    solo_sin_dato=_ids(i for i in expecting if i not in good),con_recomendaciones=sum(_recommended(v) for _,v in carried))
    good={i for i,v in carried if filled(v)}
    return dict(out,estado=_state(len(carried),len(good)),con_dato=len(good),vacios=_ids(i for i,_ in carried if i not in good))

def _summary_stats(weeks,now,member=None):
    """Which sections of each summary of hers had data; complete when the core ones did and its posts had 72 h cuts."""
    rows=[]
    for s in miembros.own(WeeklySummary.objects.filter(week_start__in=weeks,created_at__lte=now),member).order_by('week_start'):
        week=(s.stats or {}).get('semana') or {}
        sections={k:v for k,v in week.items() if isinstance(v,dict) and 'disponible' in v}
        posts=sections.get('publicaciones') or {};measured=((posts.get('cortes') or {}).get('72h') or {}).get('medidos')
        rows.append({'semana':s.week_start.isoformat(),'resumen':str(s.id),'con_dato':sorted(k for k,v in sections.items() if v.get('disponible')),
                     'sin_dato':sorted(k for k,v in sections.items() if not v.get('disponible')),'publicados':posts.get('publicados'),
                     'medidos_72h':measured,'completo':all((sections.get(k) or {}).get('disponible') for k in CORE_SECTIONS)
                     and not (posts.get('publicados') and not measured)})
    return {'estado':_state(len(rows),sum(r['completo'] for r in rows)),'resumenes':len(rows),'nucleo':list(CORE_SECTIONS),'por_resumen':rows}

# --------------------------------------------------------------------------- ¿vuelve al ciclo?

def _recommendations(since,now,member=None):
    """resumen_semanal.for_director now (hers), why it gives nothing, and whether the director's later snapshots carried it."""
    given=resumen_semanal.for_director(now,member)
    floor=_local(now).date()-timedelta(days=7*(resumen_semanal.DIRECTOR_WEEKS+1))
    summaries=miembros.own(WeeklySummary.objects.all(),member);recent=summaries.filter(week_start__gte=floor);source=recent.exclude(state=WeeklySummary.State.DISCARDED).first()
    out={'para_el_director':{'semana':given['semana']['desde'],'recomendaciones':len(given['recomendaciones'])} if given else None,
         'resumen':str(source.id) if source else None}
    if given is None:
        if source is None:out['motivo']='descartado' if recent.exists() else 'sin_resumen_reciente'
        else:
            out['motivo']='sin_recomendaciones'
            out['descartadas_por_el_validador']=len(((source.analysis or {}).get('validacion') or {}).get('descartado') or [])
        return dict(out,estado='roto' if summaries.exists() else 'sin_datos')
    after=[(i,v) for i,_,v in _values(_cycles('editorial_context',max(since,source.created_at),now),'editorial_context') if v is not MISSING]
    carried={i for i,v in after if _recommended(v)}
    return dict(out,estado='ok' if not after else _state(len(after),len(carried)),ciclos_despues=len(after),
                ciclos_con_recomendaciones=len(carried),ciclos_sin_recomendaciones=_ids(i for i,_ in after if i not in carried))

def _plan(now,member=None):
    """Her WeeklyPlan of this week: its slots carry a GASP type, and each piece of hers of the week was prepared after the
    plan with the slot's type. Never another member's plan or pieces (organizaciones, phase 4)."""
    today=_local(now).date();monday=today-timedelta(days=today.weekday())
    plans=miembros.own(WeeklyPlan.objects.all(),member)
    following=plans.filter(week_start=monday+timedelta(days=7)).values_list('id','state').first()
    out={'semana':monday.isoformat(),'semana_siguiente':{'plan':str(following[0]),'estado_plan':following[1]} if following else None}
    if not estrategia.enabled():return dict(out,estado='sin_datos',motivo='La estrategia semanal está apagada (STRATEGY_ENABLED=false).')
    plan=plans.filter(week_start=monday,created_at__lte=now).first()
    if plan is None:return dict(out,estado='roto',plan=None,motivo='Esta semana no tiene plan.')
    slots=[s for s in plan.slots or [] if isinstance(s,dict)];typed=[s for s in slots if s.get('type') in estrategia.TYPES]
    pieces={}
    for p in miembros.own(EditorialPiece.objects.all(),member).filter(slot_date__gte=monday,slot_date__lte=monday+timedelta(days=6),second_of_day=False,created_at__lte=now).order_by('created_at'):
        pieces[p.slot_date.isoformat()]=p  # the day's latest attempt
    days=[]
    for s in typed:
        p=pieces.get(s['date'])
        if p is None:
            if s['date']<today.isoformat():days.append({'fecha':s['date'],'pieza':None,'despues_del_plan':None,'tipo':'sin_pieza'})
            continue
        kind=(p.brief or {}).get('gasp_type')
        days.append({'fecha':s['date'],'pieza':str(p.id),'despues_del_plan':p.created_at>=plan.created_at,
                     'tipo':'sin_tipo' if kind is None else 'coincide' if kind==s['type'] else 'distinto'})
    wrong=[d['fecha'] for d in days if d['pieza'] is None or not d['despues_del_plan'] or d['tipo']=='distinto']
    state='roto' if not slots or len(typed)<len(slots) else 'parcial' if wrong else 'ok'
    return dict(out,estado=state,plan=str(plan.id),estado_plan=plan.state,creado=plan.created_at.isoformat(),dias=len(slots),
                dias_con_tipo=len(typed),piezas=days,fallan=wrong)

# --------------------------------------------------------------------------- report

def verdicts(report):
    """Per flow: completo when every check that had something to check is ok, roto when all of them are roto or not
    registered, parcial otherwise (also when nothing in the window could be checked)."""
    out={}
    for flow,checks in FLOWS.items():
        states={c:report[c.split('.')[0]][c.split('.')[1]]['estado'] for c in checks}
        live=[s for s in states.values() if s!='sin_datos']
        verdict=('parcial' if not live else 'completo' if all(s=='ok' for s in live)
                 else 'roto' if all(s in ('roto','no_se_registra') for s in live) else 'parcial')
        out[flow]={'veredicto':verdict,'pendiente':[f'{c}: {s}' for c,s in states.items() if s!='ok']}
    return out

def _check(build):
    """One check of the diagnosis. Stored history has shapes no fixture has (its first run in production died on an
    old audit event): a check that cannot read its data says so and the rest of the report still comes out."""
    try:return build()
    except Exception as exc:return {'estado':'error','motivo':f'{type(exc).__name__}: {str(exc)[:160]}'}

def report(dias=DIAS,now=None,member=None):
    """The whole diagnosis of the last `dias` days up to `now`. Summaries, audience, recommendations and the weekly plan
    are one member's (`member`; organizaciones, phase 4): without one, the only active member; among several active ones
    those checks say MiembroRequerido (estado error) instead of picking one."""
    now=now or timezone.now();since=now-timedelta(days=dias);weeks=_weeks(since,now)
    try:posts,pieces=_posts(since,now)
    except Exception as exc:posts,pieces={'estado':'error','motivo':f'{type(exc).__name__}: {str(exc)[:160]}'},[]
    out={'desde':_local(since).date().isoformat(),'hasta':_local(now).date().isoformat(),'dias':dias,'generado':now.isoformat(),
         'llega':{'posts':posts,'analitica':_check(lambda:_analytics(pieces,now)),
                  'comentarios':_check(lambda:dict(_measured((desenlaces.COMMENT,),'72h',since,now,wrote=True),tasas=desenlaces.comment_rates(dias,now))),
                  'red':_check(lambda:dict(_measured(desenlaces.NETWORK,'7d',since,now),interactuaron=len(desenlaces.network_engaged(days=dias,now=now)))),
                  'investigacion':_check(lambda:_research(since,now)),'resumen_semanal':_check(lambda:_summaries(weeks,now,member)),
                  'canario':_check(lambda:_canary(now)),'visitas_perfil':_check(lambda:_profile_views(since,now,member)),
                  'contactos':_check(lambda:_contacts(since,now))},
         'usan':{**{name:_check(lambda name=name:_usage(name,since,now)) for name in SNAPSHOTS},
                 'resumen_stats':_check(lambda:_summary_stats(weeks,now,member))},
         'vuelve':{'recomendaciones':_check(lambda:_recommendations(since,now,member)),'plan_semanal':_check(lambda:_plan(now,member))}}
    out['veredictos']=verdicts(out)
    return out

# --------------------------------------------------------------------------- one item, link by link

def _link(name,state,why=None,**data):
    return {'eslabon':name,'estado':state,'motivo':why,**data}

def _week_link(day,now,section,included=None,member=None):
    """Her WeeklySummary of the week of local `day` (the item's member): ok when its `section` had data and, given
    `included`, it holds the item; aun_no_toca before the summary of that week is due."""
    week=day-timedelta(days=day.weekday());summary=miembros.own(WeeklySummary.objects.all(),member).filter(week_start=week,created_at__lte=now).first()
    if summary is None:
        late=now>=_summary_due(week)
        return _link('resumen','falta' if late else 'aun_no_toca','Su semana no tiene resumen.' if late
                     else 'Su semana aún no termina o su resumen aún no se debe.',semana=week.isoformat())
    data=((summary.stats or {}).get('semana') or {}).get(section) if section else {'disponible':True}
    ids={'semana':week.isoformat(),'resumen':str(summary.id)}
    if not (isinstance(data,dict) and data.get('disponible')):
        return _link('resumen','falta',f'El resumen de su semana no tiene datos de {section}.',**ids)
    if included is not None and not included(data):return _link('resumen','falta','El resumen de su semana no la incluye.',**ids)
    return _link('resumen','ok',**ids)

def trace_piece(piece_id,now=None):
    """piece → its CONT-09 execution → PostMetric cuts → AnalyticsPost (analitica.for_piece) → a later director snapshot
    carrying its results → the WeeklySummary of its week."""
    now=now or timezone.now();key=_uuid(piece_id)
    piece=EditorialPiece.objects.filter(id=key).first() if key else None
    if piece is None:return {'pieza':str(piece_id),'eslabones':[_link('pieza','falta','No existe esa pieza.')]}
    links=[_link('pieza','ok',fecha=piece.slot_date.isoformat(),estado_pieza=piece.state)]
    execution=ActionExecution.objects.filter(proposal__piece=piece,proposal__capability='CONT-09',started_at__lte=now).order_by('-started_at').first()
    if execution is None or not ActionExecution.objects.filter(metricas.PUBLISHED,pk=execution.pk).exists():
        early=execution is None and piece.scheduled_for>now;state='aun_no_toca' if early else 'falta'
        why=('Aún no llega su hora.' if early else 'Sin ejecución CONT-09: no se publicó.' if execution is None
             else f'La ejecución quedó en «{execution.state}»: no cuenta como publicada.')
        links.append(_link('ejecucion',state,why,**({'ejecucion':str(execution.id),'estado_ejecucion':execution.state} if execution else {})))
        links+=[_link(name,state,'Sin publicación.') for name in ('corte_24h','corte_72h','corte_7d','analitica','director','resumen')]
        return {'pieza':str(piece.id),'eslabones':links}
    started=execution.started_at
    links.append(_link('ejecucion','ok',ejecucion=str(execution.id),estado_ejecucion=execution.state,inicio=started.isoformat()))
    cuts={m.kind:m for m in PostMetric.objects.filter(piece=piece,captured_at__lte=now)};pending=_pending(now)
    for kind,age in metricas.AGES.items():
        if kind in cuts:links.append(_link(f'corte_{kind}','ok',capturado=cuts[kind].captured_at.isoformat()))
        elif now-started<age:links.append(_link(f'corte_{kind}','aun_no_toca',f'Se mide al cumplir {kind}.'))
        else:links.append(_link(f'corte_{kind}','falta',pending.get((str(piece.id),kind)) or 'El último metrics.collected no dice por qué.'))
    figures=analitica.for_piece(piece.pk)
    if figures:links.append(_link('analitica','ok',fuente=figures.get('source')))
    elif now-started<timedelta(days=1):links.append(_link('analitica','aun_no_toca','La analítica de LinkedIn se importa una vez al día.'))
    else:links.append(_link('analitica','falta','Ninguna AnalyticsPost enlazada a la pieza ni en el último rango importado.'))
    measured=[m.captured_at for k,m in cuts.items() if k in editorial.RESULT_AGES]
    if not measured:
        links.append(_link('director','aun_no_toca' if now-started<metricas.AGES['72h'] else 'falta','Sin corte de 72 h ni de 7 d: el director no tiene qué leer.'))
    else:
        carried=[(c,v) for c,_,v in _values(_cycles('editorial_context',min(measured),now),'editorial_context') if v is not MISSING]
        seen=[]
        for cycle,value in carried:
            rows=[r for r in _director_rows(value) if r.get('date')==piece.slot_date.isoformat()]
            row=next((r for r in rows if r.get('opening')==piece.final_text[:280]),rows[0] if len(rows)==1 else None)
            if row is not None:seen.append((cycle,row))
        hit=next(((c,r) for c,r in seen if _has_metrics(r)),None)
        if hit:links.append(_link('director','ok',ciclo=hit[0],cortes=sorted(k for k,v in (hit[1].get('results') or {}).items() if isinstance(v,dict))))
        elif seen:links.append(_link('director','falta','Los ciclos posteriores la leen sin métricas (sin_dato).',ciclos=_ids(c for c,_ in seen)))
        elif carried:links.append(_link('director','falta','Ningún ciclo del director posterior a su corte la incluye en el historial.',ciclos=len(carried)))
        else:links.append(_link('director','aun_no_toca','Aún no hubo un ciclo del director después de su primer corte.'))
    day=piece.slot_date.isoformat()
    links.append(_week_link(_local(started).date(),now,'publicaciones',
                            lambda data:any(isinstance(r,dict) and r.get('fecha')==day for r in data.get('posts') or []),
                            piece.member or miembros.member_for_account(piece.account)))
    return {'pieza':str(piece.id),'eslabones':links}

def _use_link(proposal,execution,outcomes,now):
    """A later snapshot carrying this outcome: comment_outcomes of a later comment on the same author (INT-03), or
    network_engaged of a later network plan (RED-01, only when the person engaged)."""
    if proposal.capability not in (desenlaces.COMMENT,'RED-01'):
        return _link('uso','no_aplica','network_engaged solo lleva los seguimientos (RED-01).')
    if not outcomes:return _link('uso','aun_no_toca','Sin desenlace que usar todavía.')
    first=outcomes[0].captured_at
    if proposal.capability==desenlaces.COMMENT:
        name='comment_outcomes';author=proposal.post.author_provider_id if proposal.post_id else ''
        posts=[str(p) for p in ObservedPost.objects.filter(author_provider_id=author).values_list('id',flat=True)] if author else []
        rows=_values(_cycles(name,first,now).filter(job__params__post__in=posts),name) if posts else []
        needles={execution.started_at.isoformat(),DjangoJSONEncoder().default(execution.started_at),str(execution.id)}
        if not rows:return _link('uso','aun_no_toca','Aún no se redactó otro comentario a ese autor después del desenlace.')
    else:
        if not any(v for o in outcomes for v in (o.signals or {}).values()):
            return _link('uso','no_aplica','La persona no interactuó: network_engaged no la lleva.')
        name='network_engaged';rows=_values(_cycles(name,first,now),name);needles={str(proposal.contact_id)}
        if not rows:return _link('uso','aun_no_toca','Aún no hubo un plan de red después del desenlace.')
    carried=[(c,v) for c,_,v in rows if v is not MISSING]
    if not carried:
        anywhere=CycleLedger.objects.filter(progress_ledger__snapshots__has_key=name).exists()
        return _link('uso','falta',f'{name} no se registra en ningún ciclo.' if not anywhere else f'Los ciclos posteriores no llevan {name}.',
                     ciclos=_ids(c for c,_,_ in rows))
    hit=next((c for c,v in carried if _mentions(v,needles)),None)
    if hit:return _link('uso','ok',ciclo=hit,snapshot=name)
    return _link('uso','falta',f'Los ciclos posteriores llevan {name} sin este desenlace.',ciclos=_ids(c for c,_ in carried))

def trace_action(proposal_id,now=None):
    """proposal → its execution → ActionOutcome(s) → a later snapshot that carries it → the WeeklySummary of its week."""
    now=now or timezone.now();key=_uuid(proposal_id)
    proposal=ActionProposal.objects.select_related('post').filter(id=key).first() if key else None
    if proposal is None:return {'accion':str(proposal_id),'eslabones':[_link('propuesta','falta','No existe esa propuesta.')]}
    cap=proposal.capability
    links=[_link('propuesta','ok',capacidad=cap,estado_propuesta=proposal.state)]
    execution=ActionExecution.objects.filter(proposal=proposal,started_at__lte=now).first()
    if execution is None or execution.state not in desenlaces.DONE:
        waiting=execution is None and proposal.state in ('proposed','approved');state='aun_no_toca' if waiting else 'falta'
        why=('Aún sin ejecutar.' if waiting else 'Sin ejecución.' if execution is None
             else f'La ejecución quedó en «{execution.state}»: nada cambió en LinkedIn.')
        links.append(_link('ejecucion',state,why,**({'ejecucion':str(execution.id),'estado_ejecucion':execution.state} if execution else {})))
        links+=[_link(name,state,'Sin ejecución hecha.') for name in ('desenlace','uso','resumen')]
        return {'accion':str(proposal.id),'eslabones':links}
    links.append(_link('ejecucion','ok',ejecucion=str(execution.id),estado_ejecucion=execution.state,inicio=execution.started_at.isoformat(),
                       escribio=execution.wrote))
    kind='72h' if cap==desenlaces.COMMENT else '7d' if cap in desenlaces.NETWORK else None
    if kind is None:
        links+=[_link('desenlace','no_aplica','Solo se miden INT-03 (72 h) y RED-01/02/04 (7 d).'),_link('uso','no_aplica')]
    elif cap==desenlaces.COMMENT and not execution.wrote:
        links+=[_link('desenlace','no_aplica','No escribió nada en LinkedIn: no se mide.'),_link('uso','no_aplica')]
    else:
        age,late=desenlaces.WINDOWS[kind]
        outcomes=list(ActionOutcome.objects.filter(execution=execution,captured_at__lte=now).order_by('captured_at'))
        own=[o for o in outcomes if o.kind==kind];elapsed=now-execution.started_at
        if own:links.append(_link('desenlace','ok',cortes=[o.kind for o in outcomes],capturado=own[0].captured_at.isoformat()))
        elif elapsed<age:links.append(_link('desenlace','aun_no_toca',f'Se mide al cumplir {kind}.'))
        else:links.append(_link('desenlace','falta','Plazo vencido sin desenlace.' if elapsed>late else 'En plazo y aún sin desenlace: collect_outcomes no lo midió.'))
        links.append(_use_link(proposal,execution,outcomes,now))
    links.append(_week_link(_local(execution.started_at).date(),now,SECTION.get(cap),member=miembros.member_for_account(proposal.account)))
    return {'accion':str(proposal.id),'eslabones':links}
