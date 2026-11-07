"""Resultados: «¿vamos bien?» for the office (DISENO-VISTAS §4), current period against the previous one of equal length.

GET /api/v1/resultados?dias=7|28|90&modalidad=todo|personal_startups|projectapp. Sections, in order: negocio
(opportunities and inbound), audiencia, contenido and equipo. The modality filter applies to the first two only.
Every KPI is one object: value, previous, delta, delta_pct, comparable, series, definition, formula, unavailable_reason.
Rules (docs/datos-y-resultados-del-equipo.md and the «Reglas» of the design):
- value is null when there is no data (its source did not run in the period), never 0; a ratio with a missing or zero
  denominator is null with a reason;
- a variation exists only between periods that both have data and whose previous one was fully covered by its source;
- posts are compared at the same age: the 7 d snapshot, or the 24 h one for both periods while the current posts are
  not 7 days old yet. Reach of different posts is never added up as unique people.
Periods are whole local days (OPERATOR_TIMEZONE); the current one ends now (datos_hasta)."""
import os
import statistics
from collections import namedtuple
from datetime import datetime, time, timedelta
from decimal import Decimal
from django.utils import timezone
from knowledge import db
from . import editorial, metricas, operador, red
from .models import ActionExecution, AudienceSnapshot, AuditEvent, Contact, EditorialPiece, Job, PostMetric

DAYS=(7,28,90)
MODALITIES=('todo','personal_startups','projectapp')
AGES=('24h','72h','7d')
PUBLISHED=('confirmed','sent')  # «sent» is a 201 of the Posts API not yet seen by Unipile: published, as in the calendar
NETWORK_EVENTS=('network.synced','network.planned','network.discovered','network.classified')
OPPORTUNITIES_PENDING='Mediremos oportunidades cuando registres la primera o conectemos el inbox'
ENGAGEMENT='(reacciones + comentarios + republicaciones) / impresiones × 100'
FUNNEL=['candidate','fit','followed','invited','connected']
CUT_LABEL={'7d':'a los 7 días','24h':'a las 24 h'}
Window=namedtuple('Window','first last start end')

# --------------------------------------------------------------------------- periods and the KPI object

def _local(moment):
    return moment.astimezone(operador.local_tz())

def _midnight(day):
    return datetime.combine(day,time(0),tzinfo=operador.local_tz())

def windows(days,now):
    first=_local(now).date()-timedelta(days=days-1);previous=first-timedelta(days=days)
    return Window(first,_local(now).date(),_midnight(first),now),Window(previous,first-timedelta(days=1),_midnight(previous),_midnight(first))

def _between(field,w):
    return {f'{field}__gte':w.start,f'{field}__lt':w.end}

def _num(value,digits=4):
    if isinstance(value,Decimal):value=float(value)
    return round(value,digits) if isinstance(value,float) else value

def kpi(value,previous=None,definition='',formula=None,reason=None,comparable=True,series=None,**extra):
    """One KPI card. comparable=False when the previous period was not fully covered by its source."""
    comparable=bool(comparable) and value is not None and previous is not None
    delta=value-previous if comparable else None
    return dict(value=_num(value),previous=_num(previous),delta=_num(delta),
                delta_pct=round(delta/previous*100,1) if comparable and previous else None,comparable=comparable,series=series,
                definition=definition,formula=formula,unavailable_reason=None if value is not None else reason or 'Sin datos en este periodo.',**extra)

def percent(numerator,denominator):
    return round(numerator/denominator*100,2) if numerator is not None and denominator else None

def ratio_kpi(current,previous,definition,formula,reason,zero_reason,comparable=True):
    """current/previous: (numerator, denominator), or None when the source did not run."""
    value=percent(*current) if current else None
    if current and value is None and not current[1]:reason=zero_reason
    return kpi(value,percent(*previous) if previous else None,definition,formula,reason,comparable,
               numerator=current[0] if current else None,denominator=current[1] if current else None)

def _earliest(qs,field):
    return qs.order_by(field).values_list(field,flat=True).first()

class Coverage:
    """When each source started recording and whether it ran in a window: no run means no data, not zero."""
    def __init__(self):
        starts=[_earliest(Job.objects.all(),'created_at'),_earliest(ActionExecution.objects.all(),'started_at')]
        self.machine_since=min(filter(None,starts),default=None)
        self.network_since=_earliest(AuditEvent.objects.filter(action__in=NETWORK_EVENTS),'created_at')
        self.sync_since=_earliest(AuditEvent.objects.filter(action='network.synced'),'created_at')
    @staticmethod
    def machine(w):
        return Job.objects.filter(**_between('created_at',w)).exists() or ActionExecution.objects.filter(**_between('started_at',w)).exists()
    @staticmethod
    def network(w,actions=NETWORK_EVENTS):
        return AuditEvent.objects.filter(action__in=actions,**_between('created_at',w)).exists()
    @staticmethod
    def covers(since,w):
        return since is not None and since<=w.start

def counted(measure,ran,since,current,previous,definition,reason,**extra):
    return kpi(measure(current) if ran(current) else None,measure(previous) if ran(previous) else None,definition,
               reason=reason,comparable=Coverage.covers(since,previous),**extra)

def _modality(qs,modality):
    return qs if modality=='todo' else qs.filter(classification__modality=modality)

# --------------------------------------------------------------------------- 1. negocio

STAGES=['conversacion','necesidad','cualificada','reunion','propuesta','acuerdo']
TARGET={'personal_startups':60,'projectapp':40}

def _reached(item):
    """[(stage, moment)] each time the opportunity entered a stage (created or moved), from its history."""
    out=[]
    for event in item.history:
        if event.get('event') in ('created','stage') and event.get('stage'):
            out.append((event['stage'],datetime.fromisoformat(event['at'])))
    return out or [(item.stage,item.created_at)]

def negocio(current,previous,modality,coverage):
    """Opportunities registered by Gustavo (Personas → Oportunidades) and the inbound from the network."""
    from .models import Opportunity
    def inbound(w):
        return _modality(Contact.objects.filter(source=Contact.Source.INCOMING,classification__fit=True,**_between('discovered_at',w)),modality).count()
    inbound_kpi=counted(inbound,lambda w:coverage.network(w,('network.synced',)),coverage.sync_since,current,previous,
                        'Personas que encajan y te invitaron sin que las buscáramos: invitaciones recibidas que la red registró en el periodo.',
                        'La red no sincronizó invitaciones en este periodo.')
    everything=list(Opportunity.objects.select_related('contact'))
    if not everything:return {'disponible':False,'motivo':OPPORTUNITIES_PENDING,'inbound':inbound_kpi}
    since=min(o.created_at for o in everything)
    scoped=[o for o in everything if modality=='todo' or o.modality==modality]
    comparable=Coverage.covers(since,previous)
    def open_at(w):
        return sum(1 for o in scoped if o.created_at<w.end and not (o.closed_at and o.closed_at<w.end))
    def entered(stage,w):
        return sum(1 for o in scoped if any(s==stage and w.start<=at<w.end for s,at in _reached(o)))
    def tracked(w):return since<w.end
    def card(measure,definition,stage=None):
        return kpi(measure(current) if tracked(current) else None,measure(previous) if tracked(previous) else None,definition,
                   reason='Aún no habías registrado oportunidades en ese periodo.',comparable=comparable)
    # Funnel over the opportunities alive in the current period: how many reached each stage, and the conversion.
    alive=[o for o in scoped if o.created_at<current.end and not (o.closed_at and o.closed_at<current.start)]
    furthest=[max((STAGES.index(s) for s,_ in _reached(o) if s in STAGES),default=0) for o in alive]
    steps=[]
    for i,stage in enumerate(STAGES):
        n=sum(1 for f in furthest if f>=i)
        steps.append({'stage':stage,'label':Opportunity.Stage(stage).label,'count':n,
                      'conversion_pct':percent(n,steps[-1]['count']) if steps and steps[-1]['count'] else None})
    split={m:sum(1 for o in everything if o.modality==m and o.stage!='sin_acuerdo') for m in ('personal_startups','projectapp','por_clasificar')}
    classified=split['personal_startups']+split['projectapp']
    active=sorted((o for o in scoped if o.stage not in ('acuerdo','sin_acuerdo')),key=lambda o:o.updated_at,reverse=True)[:5]
    return {'disponible':True,
            'conversaciones':kpi(None,None,'Conversaciones con personas que encajan abiertas en el periodo.',
                                 reason='Disponible cuando conectemos el inbox.'),
            'abiertas':card(open_at,'Oportunidades abiertas al final del periodo (sin acuerdo ni cierre).'),
            'reuniones':card(lambda w:entered('reunion',w),'Oportunidades que llegaron a reunión en el periodo.'),
            'propuestas':card(lambda w:entered('propuesta',w),'Oportunidades a las que se envió una propuesta en el periodo.'),
            'acuerdos':card(lambda w:entered('acuerdo',w),'Oportunidades que terminaron en acuerdo en el periodo.'),
            'embudo':{'steps':steps,'sin_acuerdo':sum(1 for o in alive if o.stage=='sin_acuerdo'),
                      'definition':'Oportunidades vivas en el periodo según la etapa más lejana que alcanzaron; la conversión es el paso frente al anterior.'},
            'modalidades':{'counts':split,'pct':{m:percent(split[m],classified) for m in TARGET},'objetivo':TARGET,
                           'definition':'Oportunidades abiertas o ganadas por modalidad frente al objetivo 60/40 (sin las «por clasificar»).'},
            'inbound':inbound_kpi,
            'activas':[{'id':str(o.id),'person':o.contact.display_name if o.contact else o.person_name,'contact_id':str(o.contact_id) if o.contact_id else None,
                        'company':o.company,'modality':o.modality,'stage':o.stage,'stage_label':o.get_stage_display(),
                        'next_action':o.next_action,'next_action_at':o.next_action_at} for o in active]}

# --------------------------------------------------------------------------- 2. audiencia

def _daily(field,w):
    return list(AudienceSnapshot.objects.filter(day__gte=w.first,day__lte=w.last).exclude(**{field:None}).order_by('day').values_list('day',field))

def _audience(field,current,previous,label):
    now,before=_daily(field,current),_daily(field,previous)
    return kpi(now[-1][1] if now else None,before[-1][1] if before else None,
               f'{label} de la cuenta en la última captura del periodo. La variación es el crecimiento neto desde la última captura '
               'del periodo anterior; no dice cuántas altas y bajas hubo. No se separa por modalidad.',
               reason='Sin captura de audiencia en este periodo.',series=[{'date':d,'value':v} for d,v in now] or None,
               measured={'from':before[-1][0] if before else None,'to':now[-1][0] if now else None})

def _profile_views(current,previous):
    def rows(w):
        return list(AudienceSnapshot.objects.filter(day__gte=w.first,day__lte=w.last).exclude(profile_views=None).order_by('day')
                    .values_list('day','profile_views','profile_views_days'))
    now,before=rows(current),rows(previous)
    days=now[-1][2] if now else None
    return kpi(now[-1][1] if now else None,before[-1][1] if before else None,
               f'Visitas al perfil que LinkedIn informa para los últimos {days or metricas.views_days()} días, en la última captura del periodo '
               '(List Profile Views). No se separa por modalidad.',
               reason='LinkedIn no entregó visitas al perfil en este periodo.',comparable=bool(now and before and now[-1][2]==before[-1][2]),
               series=[{'date':d,'value':v} for d,v,_ in now] or None,window_days=days)

def _resolution(contact):
    """When and how an invitation sent by Gustavo was resolved: the first «connected» or «closed» event after it."""
    for item in contact.history or []:
        if item.get('event') in ('connected','closed'):
            try:at=datetime.fromisoformat(item['at'])
            except (KeyError,TypeError,ValueError):continue
            if at>=contact.invited_at-timedelta(minutes=1):return at,item['event']
    if contact.stage==Contact.Stage.CONNECTED and contact.connected_at:return contact.connected_at,'connected'
    return None,None

def audiencia(current,previous,modality,coverage):
    def fit_connected(w):
        return _modality(Contact.objects.filter(classification__fit=True,**_between('connected_at',w)),modality)
    invited=[(c,)+_resolution(c) for c in _modality(Contact.objects.filter(invited_at__isnull=False),modality)
             .only('history','invited_at','connected_at','stage')]
    def resolved(w):
        if not coverage.network(w):return None
        events=[event for _,at,event in invited if at and w.start<=at<w.end]
        return events.count('connected'),len(events)
    roles=None
    if coverage.network(current):
        roles={r:0 for r in red.ROLES}
        for role in fit_connected(current).values_list('classification__role',flat=True):roles[role or 'sin_rol']=roles.get(role or 'sin_rol',0)+1
    contacts=_modality(Contact.objects.all(),modality)
    return {
        'followers':_audience('followers',current,previous,'Seguidores'),
        'connections':_audience('connections',current,previous,'Conexiones'),
        'profile_views':_profile_views(current,previous),
        'new_fit_connections':counted(lambda w:fit_connected(w).count(),coverage.network,coverage.network_since,current,previous,
                                      'Contactos que pasaron a conectado en el periodo y que el clasificador marcó como encaja.',
                                      'La red no funcionó en este periodo.'),
        'roles':{'items':[{'role':r,'value':n} for r,n in roles.items()] if roles is not None else None,
                 'definition':'Rol del barrio (classification.role) de las conexiones nuevas que encajan, en el periodo.',
                 'unavailable_reason':None if roles is not None else 'La red no funcionó en este periodo.'},
        'acceptance_rate':ratio_kpi(resolved(current),resolved(previous),
                                    'De las invitaciones que enviamos y se resolvieron en el periodo, cuántas acabaron en conexión.',
                                    'conectados / (conectados + cerrados) × 100','La red no funcionó en este periodo.',
                                    'Ninguna invitación se resolvió en el periodo.',Coverage.covers(coverage.network_since,previous)),
        'funnel':{'stages':{s:contacts.filter(stage=s).count() for s in Contact.Stage.values},'order':FUNNEL,'aside':['discarded','closed','incoming'],
                  'definition':'Personas del barrio por etapa hoy (lo mismo que red/summary.stages, filtrado por modalidad).'},
        'recurrent_people':kpi(None,None,'Personas que interactuaron 2 o más veces en el periodo.',
                               reason='Aún no medimos las interacciones repetidas por persona.',top=None)}

# --------------------------------------------------------------------------- 3. contenido

def engagement_pct(metric):
    parts=(metric.reactions,metric.comments,metric.reposts)
    return percent(None if None in parts else sum(parts),metric.impressions)

def _with_roles(commenters):
    """Stored commenters with the role refreshed from today's classification (people get classified after commenting)."""
    if commenters is None:return None
    known=dict(Contact.objects.filter(provider_user_id__in=[c['provider_user_id'] for c in commenters]).values_list('provider_user_id','classification'))
    return [dict(c,role=(known.get(c['provider_user_id']) or {}).get('role') or c.get('role'),
                 fit=(known.get(c['provider_user_id']) or {}).get('fit',c.get('fit'))) for c in commenters]

def by_role(commenters):
    """Unique people per neighborhood role; null when the comments were never read."""
    if commenters is None:return None
    people={c['provider_user_id']:c.get('role') or 'sin_clasificar' for c in commenters}
    counts={}
    for role in people.values():counts[role]=counts.get(role,0)+1
    return counts

def first_line(text):
    return next((line.strip() for line in (text or '').splitlines() if line.strip()),'')[:140]

class Post:
    """A published piece with its snapshots by age."""
    def __init__(self,execution):
        self.execution=execution;self.piece=execution.proposal.piece
        self.cuts={m.kind:m for m in self.piece.post_metrics.all()}
    def impressions(self,kind):
        return self.cuts[kind].impressions if kind in self.cuts else None
    def latest(self):
        return next((self.cuts[k] for k in reversed(AGES) if k in self.cuts),None)
    def commenters(self):
        cut=next((self.cuts[k] for k in reversed(AGES) if k in self.cuts and self.cuts[k].commenters is not None),None)
        return _with_roles(cut.commenters) if cut else None

def _posts(w):
    return [Post(e) for e in ActionExecution.objects.select_related('proposal__piece').prefetch_related('proposal__piece__post_metrics')
            .filter(proposal__capability='CONT-09',proposal__piece__isnull=False,state__in=PUBLISHED,**_between('started_at',w)).order_by('started_at')]

def _median(values):
    values=[v for v in values if v is not None]
    return _num(statistics.median(values)) if values else None

def medians_before(start):
    """Median impressions at 7 d and 24 h of own posts published in the 4 weeks before `start`."""
    rows=PostMetric.objects.filter(published_at__gte=start-timedelta(days=28),published_at__lt=start).exclude(impressions=None)
    return {kind:_median(rows.filter(kind=kind).values_list('impressions',flat=True)) for kind in ('7d','24h')}

def _consistency(w,now,coverage):
    """(days with an own publication, days the circuit planned a piece whose hour has passed); None without data."""
    pieces=EditorialPiece.objects.filter(slot_date__gte=w.first,slot_date__lte=w.last,scheduled_for__lte=min(w.end,now))
    planned=set(pieces.values_list('slot_date',flat=True))
    if not planned and not coverage.machine(w):return None
    published=set(ActionExecution.objects.filter(proposal__capability='CONT-09',state__in=PUBLISHED,proposal__piece__in=pieces)
                  .values_list('proposal__piece__slot_date',flat=True))
    return len(published),len(planned)

def contenido(current,previous,now,coverage):
    posts,before=_posts(current),_posts(previous)
    # Same age for both periods: 7 d, or 24 h while no post of the current period has reached 7 days.
    cut='7d' if any(p.impressions('7d') is not None for p in posts) or not any(p.impressions('24h') is not None for p in posts) else '24h'
    note='' if cut=='7d' else ' Los posts del periodo aún no cumplen 7 días: se comparan a las 24 h.';label=CUT_LABEL[cut]
    def at(group):return [p.cuts[cut] for p in group if cut in p.cuts]
    def median(group):return _median([m.impressions for m in at(group)])
    def engagement(group):
        complete=[m for m in at(group) if engagement_pct(m) is not None]
        return (sum(m.reactions+m.comments+m.reposts for m in complete),sum(m.impressions for m in complete)) if complete else None
    def substantive_comments(group):
        read=[m.commenters for m in at(group) if m.commenters is not None]
        return sum(c['substantive'] for cs in read for c in cs) if read else None
    no_posts='Sin posts publicados en el periodo.' if not posts else f'Ningún post del periodo tiene aún su corte {label}.'
    eng,eng_before=engagement(posts),engagement(before)
    eng_reason=(no_posts if not at(posts) else 'LinkedIn oculta algún contador de los posts del periodo.' if not eng
                else 'Los posts del periodo no registran impresiones.')
    kpis={'median_impressions':kpi(median(posts),median(before),f'Mediana de impresiones por post {label}.{note}',reason=no_posts,cut=cut,
                                   posts_measured=len(at(posts)),posts_total=len(posts)),
          'engagement_pct':kpi(percent(*eng) if eng else None,percent(*eng_before) if eng_before else None,
                               f'Interacción de los posts del periodo {label}, sumando sus contadores.{note}',ENGAGEMENT,
                               reason=eng_reason,cut=cut,
                               numerator=eng[0] if eng else None,denominator=eng[1] if eng else None),
          'substantive_comments':kpi(substantive_comments(posts),substantive_comments(before),
                                     f'Comentarios de otras personas con al menos {metricas.SUBSTANTIVE_CHARS} caracteres en los posts del periodo, {label}.{note}',
                                     reason='Aún no se leyeron los comentarios de los posts del periodo.' if posts else no_posts,cut=cut),
          'consistency':ratio_kpi(_consistency(current,now,coverage),_consistency(previous,now,coverage),
                                  'Días con publicación propia frente a días en que el circuito editorial previó una pieza (ya pasada su hora).',
                                  'días publicados / días previstos × 100','La máquina no funcionó en este periodo.','No hubo días previstos en el periodo.')}
    reference=medians_before(current.start)
    bars=[]
    for p in posts:
        kind='7d' if p.impressions('7d') is not None else '24h' if p.impressions('24h') is not None else None
        bars.append({'piece_id':str(p.piece.id),'date':p.piece.slot_date,'impressions':p.impressions(kind) if kind else None,'cut':kind,'fallback':kind=='24h'})
    def row(p,kind):
        m=p.cuts.get(kind)
        return {'piece_id':str(p.piece.id),'first_line':first_line(p.piece.final_text),'date':p.piece.slot_date,'pillar':(p.piece.brief or {}).get('pillar'),
                'impressions':m.impressions if m else None,'engagement_pct':engagement_pct(m) if m else None,'cut':kind}
    ranked=[p for p in posts if p.impressions(cut) is not None]
    best=max(ranked,key=lambda p:(p.impressions(cut),engagement_pct(p.cuts[cut]) or 0),default=None)
    pillars={}
    for p in posts:
        value=engagement_pct(p.cuts[cut]) if cut in p.cuts else None
        if value is not None:pillars.setdefault((p.piece.brief or {}).get('pillar') or 'sin_pilar',[]).append(value)
    table=[]
    for p in posts:
        latest=p.latest();commenters=p.commenters()
        table.append({'piece_id':str(p.piece.id),'date':p.piece.slot_date,'published_at':p.execution.started_at,'first_line':first_line(p.piece.final_text),
                      'pillar':(p.piece.brief or {}).get('pillar'),'url':(latest.share_url if latest else '') or p.execution.external_url or None,
                      'impressions_24h':p.impressions('24h'),'impressions_7d':p.impressions('7d'),
                      'reactions':latest.reactions if latest else None,'comments':latest.comments if latest else None,
                      'reposts':latest.reposts if latest else None,'engagement_pct':engagement_pct(latest) if latest else None,
                      'cut':latest.kind if latest else None,'commenters_by_role':by_role(commenters)})
    return {'kpis':kpis,
            'chart':{'bars':bars,'median_previous_4_weeks':reference,
                     'definition':'Impresiones de cada post a los 7 días (o a las 24 h, con fallback=true, si aún no los cumple) y la mediana '
                                  'a la misma edad de los posts de las 4 semanas anteriores al periodo.'},
            'best_post':row(best,cut) if best else None,
            'by_pillar':{'cut':cut,'formula':ENGAGEMENT,'items':[{'pillar':k,'value':_num(statistics.mean(pillars[k]),2) if pillars.get(k) else None,
                                                                    'posts':len(pillars.get(k,[]))}
                                                                   for k in list(dict.fromkeys(editorial.PILLARS+list(pillars)))]},
            'posts':table}

# --------------------------------------------------------------------------- 4. equipo

COST="CASE WHEN status='complete' THEN actual_usd WHEN status IN ('reserved','uncertain') THEN reserved_usd ELSE 0 END"

def _bucket(purpose):
    if purpose=='propose-comment':return 'general'
    for prefix,name in (('editorial-','editorial'),('network-','network')):
        if (purpose or '').startswith(prefix):return name
    return 'other'

def spend(now):
    """AI spend today and this local month per budget (settled cost or pending reservation, as the daily caps count it)."""
    day,_=operador.period_starts(now);month=_midnight(_local(now).date().replace(day=1))
    with db.connect() as c:
        rows=c.execute(f'''SELECT provider,purpose,coalesce(sum({COST}) FILTER (WHERE created_at>=%s),0) AS today,
            coalesce(sum({COST}) FILTER (WHERE created_at>=%s),0) AS month,coalesce(sum({COST}),0) AS total
            FROM usage_ledger GROUP BY provider,purpose''',(day,month)).fetchall()
    budgets={'general':Decimal(os.environ.get('OPERATOR_DAILY_LLM_USD','1')),'editorial':editorial.daily_budget(),'network':red.daily_budget()}
    sums={};providers={}
    for r in rows:
        if r['provider']=='anthropic':
            entry=sums.setdefault(_bucket(r['purpose']),{'today':Decimal(0),'month':Decimal(0)})
            entry['today']+=r['today'];entry['month']+=r['month']
        entry=providers.setdefault(r['provider'],{'today':Decimal(0),'month':Decimal(0),'total':Decimal(0)})
        for key in ('today','month','total'):entry[key]+=r[key]
    def spent(bucket,key):return _num(sums.get(bucket,{}).get(key,Decimal(0)))
    def limit(provider):return _num(Decimal(os.environ.get(provider.upper()+'_LIMIT_USD','1')))
    anthropic=providers.get('anthropic',{'today':Decimal(0),'month':Decimal(0),'total':Decimal(0)})
    return {'today':{b:{'spent':spent(b,'today'),'budget':_num(budgets[b])} for b in budgets}|{'other':{'spent':spent('other','today'),'budget':None}},
            'month':{b:{'spent':spent(b,'month'),'budget':None} for b in (*budgets,'other')}
                    |{'total':{'spent':_num(anthropic['month']),'budget':limit('anthropic')}},
            'accumulated':{'spent':_num(anthropic['total']),'budget':limit('anthropic')},
            'other_providers':{p:{'today':_num(v['today']),'month':_num(v['month']),'accumulated':_num(v['total']),'budget':limit(p)}
                               for p,v in sorted(providers.items()) if p!='anthropic'},
            'month_start':month.date(),
            'definition':'Gasto de Anthropic por presupuesto diario: general (comentarios, OPERATOR_DAILY_LLM_USD), editorial '
                         '(EDITORIAL_DAILY_LLM_USD) y red (NETWORK_DAILY_LLM_USD). ANTHROPIC_LIMIT_USD es un techo acumulado sobre todo '
                         'el ledger (accumulated), no mensual; month.total lo usa como referencia.'}

def equipo(current,previous,now,coverage):
    def confirmed(capability):
        return lambda w:ActionExecution.objects.filter(proposal__capability=capability,state='confirmed',**_between('started_at',w)).count()
    def pieces(label):
        def measure(w):
            group=EditorialPiece.objects.filter(slot_date__gte=w.first,slot_date__lte=w.last).prefetch_related('proposals')
            return sum(editorial.status(p,max(p.proposals.all(),key=lambda a:a.created_at,default=None))==label for p in group)
        return measure
    def ran_or_pieces(w):
        return coverage.machine(w) or EditorialPiece.objects.filter(slot_date__gte=w.first,slot_date__lte=w.last).exists()
    def team(measure,definition,ran=coverage.machine):
        return counted(measure,ran,coverage.machine_since,current,previous,definition,'La máquina no funcionó en este periodo.')
    return {'comments_published':team(confirmed('INT-03'),'Comentarios publicados y confirmados en posts ajenos (INT-03).'),
            'comments_replied':kpi(None,None,'Comentarios publicados que recibieron respuesta.',reason='Aún no leemos las respuestas a tus comentarios.'),
            'follows':team(confirmed('RED-01'),'Personas seguidas y confirmadas (RED-01).'),
            'invites':team(confirmed('RED-02'),'Invitaciones sin nota enviadas y confirmadas (RED-02).'),
            'accepts':team(confirmed('RED-04'),'Invitaciones recibidas aceptadas y confirmadas (RED-04).'),
            'pieces_published':team(pieces('published'),'Piezas propias publicadas, por día de la pieza.',ran_or_pieces),
            'pieces_blocked':team(pieces('blocked'),'Piezas que el verificador bloqueó, por día de la pieza.',ran_or_pieces),
            'pieces_vetoed':team(pieces('vetoed'),'Piezas que vetaste antes de su hora, por día de la pieza.',ran_or_pieces),
            'spend':spend(now)}

# --------------------------------------------------------------------------- piece detail (editorial_views.PieceDetail)

def piece_snapshots(piece):
    return [{'kind':m.kind,'impressions':m.impressions,'reactions':m.reactions,'comments':m.comments,'reposts':m.reposts,
             'engagement_pct':engagement_pct(m),'captured_at':m.captured_at,
             'age_hours':round((m.captured_at-m.published_at).total_seconds()/3600,1) if m.published_at else None}
            for m in sorted(piece.post_metrics.all(),key=lambda m:AGES.index(m.kind))]

def piece_commenters(piece):
    """Who commented, from the latest snapshot whose comments were read; null if they never were."""
    cut=next((m for m in sorted(piece.post_metrics.all(),key=lambda m:AGES.index(m.kind),reverse=True) if m.commenters is not None),None)
    return _with_roles(cut.commenters) if cut else None

# --------------------------------------------------------------------------- endpoint payload

def build(dias='28',modalidad='todo',now=None):
    try:days=int(dias)
    except (TypeError,ValueError):days=None
    if days not in DAYS:raise ValueError('dias debe ser 7, 28 o 90.')
    if modalidad not in MODALITIES:raise ValueError('modalidad debe ser todo, personal_startups o projectapp.')
    now=now or timezone.now();current,previous=windows(days,now);coverage=Coverage()
    return {'periodo':{'desde':current.first,'hasta':current.last,'dias':days,'datos_hasta':now,
                       'anterior':{'desde':previous.first,'hasta':previous.last}},
            'modalidad':modalidad,'zona_horaria':str(operador.local_tz()),
            'negocio':negocio(current,previous,modalidad,coverage),'audiencia':audiencia(current,previous,modalidad,coverage),
            'contenido':contenido(current,previous,now,coverage),'equipo':equipo(current,previous,now,coverage)}
