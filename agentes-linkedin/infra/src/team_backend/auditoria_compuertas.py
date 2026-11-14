"""Gate audit (docs/compuertas.md): per gate, what entered, passed at once, passed after a repair or a retry, stopped or
waits; its top reasons and a few examples; the days without a post and their cause; the stops nobody retried or
dismissed; and Gustavo's word as labels («paradas N, no estuvo de acuerdo en M»).

Read-only: it reads what the system already stores (pieces, proposals, audit events) and never calls a model or writes.
The output carries ids and categories only, never a post's text, a quote or a name: it can be pasted anywhere.
`manage.py compuertas auditar --dias N [--json]` prints it; resumen_semanal keeps its summary for the week; vigilar()
pushes one notice when a gate stops too much or a day ended without a post because of a gate."""
import os
from collections import Counter, defaultdict
from datetime import timedelta
from django.utils import timezone
from . import compuertas, editorial, operador
from .models import ActionProposal, AuditEvent, EditorialPiece

TOP=5;EXAMPLES=5
NAMES={'reglas_post':'Reglas fijas del post','verificador':'Verificador del post','reparacion':'Ronda de reparación',
       'imagen':'Revisión visual de la imagen','retoque':'Retoque por un comentario tuyo','prefiltro':'Prefiltro de comentarios (Jev)',
       'dinero':'Presupuesto de IA','fallos':'Fallos de proveedor o del ciclo'}
ORDER=('reglas_post','verificador','reparacion','imagen','retoque','prefiltro','dinero','fallos')
# Not gates on content: their stop rate says nothing about rigidity (prefilter skips are its job; money and failures
# have their own notices: cycle_stopped, budget).
NOT_ALERTED=('reparacion','prefiltro','dinero','fallos')
NON_CONTENT=('Capacidad desactivada','Hash inconsistente')

def label(key):
    if key.startswith('lider:'):return f'Líder (Jev) · {key[6:]}'
    if key.startswith('politica:'):return f'Reglas de la política · {key[9:]}'
    return NAMES.get(key,key)

def _categories(reasons):
    return [compuertas.category(r) for r in (reasons or [])] or ['otro']

class Gate:
    def __init__(self,key):
        self.key=key;self.entered=self.first=self.after=self.stopped=self.waiting=self.observations=0
        self.reasons=Counter();self.examples=[];self.disagreed=0;self.vetoed=0;self.extra={}

    def stop(self,ident,categories):
        self.stopped+=1;self.reasons.update(categories)
        if len(self.examples)<EXAMPLES:self.examples.append({'id':str(ident),'categoria':categories[0]})

    def row(self):
        decided=self.first+self.after+self.stopped
        return dict({'compuerta':self.key,'nombre':label(self.key),'entraron':self.entered,'pasaron_a_la_primera':self.first,
                     'pasaron_tras_reintento':self.after,'paradas':self.stopped,'en_espera':self.waiting,
                     'tasa_parada':round(self.stopped/decided,3) if decided else None,'con_observaciones':self.observations,
                     'motivos':[[k,n] for k,n in self.reasons.most_common(TOP)],'ejemplos':self.examples,
                     'gustavo':{'no_estuvo_de_acuerdo':self.disagreed,'vetadas_tras_pasar':self.vetoed}},**self.extra)

class Gates(dict):
    def __missing__(self,key):
        self[key]=Gate(key);return self[key]

# --------------------------------------------------------------------------- the post: preparation gates

def _money(note):
    if note.startswith('Ciclo detenido: cost_cap'):return 'tope_del_ciclo'
    if 'Límite local' in note:return 'limite_del_proveedor'
    return 'presupuesto'

def _failure(note):
    for prefix,name in (('Ciclo detenido','ciclo_detenido'),('Preparación interrumpida','interrumpida'),
                        ('Biblioteca no disponible','biblioteca'),('Error interno','error_interno')):
        if note.startswith(prefix):return name
    return 'fallo_de_proveedor'

def _rework(reason):
    reason=reason or ''
    for needle,name in (('revisión visual','foto_rechazada'),('no pasó la verificación','texto_bloqueado'),
                        ('ya la usa otra pieza','foto_en_uso'),('hueco','sin_hueco'),('Infografía rechazada','infografia_rechazada')):
        if needle in reason:return name
    return 'otro'

def _piece(gates,p):
    """One piece through the preparation gates, in the order they ran."""
    v=p.verification or {};repair=v.get('repair') or {}
    money=gates['dinero'];money.entered+=1
    if editorial.budget_stopped(p):
        money.stop(p.id,[_money(p.note)]);return
    money.first+=1
    failed=gates['fallos'];failed.entered+=1
    if p.state==EditorialPiece.State.FAILED or p.note.startswith(('Ciclo detenido','Preparación interrumpida')):
        failed.stop(p.id,[_failure(p.note)]);return
    failed.first+=1
    if p.state==EditorialPiece.State.SKIPPED or not ('rules' in v or v.get('model_verdict') is not None or repair):return
    rules=gates['reglas_post'];rules.entered+=1
    if v.get('rules'):rules.stop(p.id,_categories(v['rules']))
    elif repair.get('trigger')=='reglas':rules.after+=1
    else:rules.first+=1
    if v.get('model_verdict') is not None or repair.get('first_review'):
        verifier=gates['verificador'];verifier.entered+=1
        if v.get('observations'):verifier.observations+=1
        if v.get('verdict')=='ready_for_execution':
            if repair.get('trigger')=='verificador':verifier.after+=1
            else:verifier.first+=1
        elif not v.get('rules'):verifier.stop(p.id,_categories(v.get('blocking_reasons')))
    if repair:
        fixed=gates['reparacion'];fixed.entered+=1
        if repair.get('outcome')=='reparada':fixed.first+=1
        else:fixed.stop(p.id,['reparacion_'+str(repair.get('outcome') or 'otro')])
    if v.get('verdict')=='ready_for_execution' and p.state in (EditorialPiece.State.READY,EditorialPiece.State.BLOCKED) and not v.get('rework'):
        image=gates['imagen'];image.entered+=1
        if compuertas.gate_blocked(p):image.stop(p.id,['imagen'])
        else:image.first+=1

def _owner_overrides(gates,since,until,pieces):
    for event in AuditEvent.objects.filter(action='editorial.block_overridden',created_at__gte=since,created_at__lt=until):
        kind=(event.metadata or {}).get('kind')
        if kind=='lider':gates['lider:CONT-09'].disagreed+=1;continue
        if kind=='imagen':gates['imagen'].disagreed+=1;continue
        piece=pieces.get(event.target) or EditorialPiece.objects.filter(id=event.target).first()
        gates['reglas_post' if piece and (piece.verification or {}).get('rules') else 'verificador'].disagreed+=1

def _reworks(gates,since,until):
    gate=gates['retoque']
    for event in AuditEvent.objects.filter(action__in=['editorial.reworked','editorial.rework_failed'],
                                           created_at__gte=since,created_at__lt=until).order_by('created_at'):
        gate.entered+=1
        if event.action=='editorial.reworked':gate.first+=1
        else:gate.stop(event.target,[_rework((event.metadata or {}).get('reason'))])

# --------------------------------------------------------------------------- proposals: policy and lead

def _lead(gate,p):
    """One decision of the lead: passed at once, passed after its redraft, or stopped."""
    review=p.review or {};gate.entered+=1
    if review.get('decision')=='approve':
        if any(str(r).startswith(compuertas.LEAD_REDRAFT) for r in p.risks):gate.after+=1
        else:gate.first+=1
    else:gate.stop(str(p.id),_categories(review.get('reasons')))

def _proposals(gates,since,until):
    discards={e.target:(e.metadata or {}).get('issues') or [] for e in AuditEvent.objects.filter(
        action='operator.policy_discarded',created_at__gte=since,created_at__lt=until)}
    lead_discarded_comments=[]
    # On the network the lead reviews the same person again and again (one was reviewed 53 times in a week): a person
    # counts once per gate, by the lead's latest decision in the window; `revisiones` keeps the raw number of reviews.
    people={}
    for p in ActionProposal.objects.filter(decided_at__gte=since,decided_at__lt=until).order_by('decided_at'):
        cap=p.capability;review=p.review or {};decision=review.get('decision');pid=str(p.id)
        policy=gates['politica:'+cap];lead=gates['lider:'+cap]
        issues=discards.get(pid)
        if issues and any(str(i).startswith(NON_CONTENT) for i in issues):continue  # says nothing about the content
        if issues is not None or p.approved_hash or decision in ('approve','discard'):
            policy.entered+=1
            if issues is not None and decision!='discard':policy.stop(pid,_categories(issues))
            else:policy.first+=1
        if decision in ('approve','discard'):
            if cap in operador.NETWORK and p.contact_id:
                people[(cap,p.contact_id)]=p;lead.extra['revisiones']=lead.extra.get('revisiones',0)+1
            else:
                _lead(lead,p)
                if decision=='discard' and cap==ActionProposal.Capability.COMMENT and p.post_id:lead_discarded_comments.append(p)
        if p.state==ActionProposal.State.REJECTED and p.approved_hash:
            (lead if decision=='approve' else policy).vetoed+=1
            if cap==ActionProposal.Capability.PUBLISH:gates['verificador'].vetoed+=1
    for (cap,_),p in people.items():_lead(gates['lider:'+cap],p)
    for p in ActionProposal.objects.filter(state=ActionProposal.State.PROPOSED,review__decision='retry'):
        gates['lider:'+p.capability].waiting+=1  # Jev did not answer: it is asked again later
    if lead_discarded_comments:
        later={(post,created) for post,created in ActionProposal.objects.filter(
            capability=ActionProposal.Capability.COMMENT,post_id__in=[p.post_id for p in lead_discarded_comments]).values_list('post_id','created_at')}
        gates['lider:INT-03'].extra['descartes_sin_reescritura']=sum(
            1 for p in lead_discarded_comments if not any(post==p.post_id and created>p.created_at for post,created in later))

def _network_labels(gates,since,until):
    """«Sí, encaja» after a doubt of the lead is Gustavo disagreeing with that stop; his discard of a contact the
    classifier let through is him disagreeing with a pass."""
    confirmed=list(AuditEvent.objects.filter(action='network.fit_confirmed',created_at__gte=since,created_at__lt=until).values_list('target',flat=True))
    for target in confirmed:
        last=(ActionProposal.objects.filter(contact_id=target,review__decision='discard').order_by('-decided_at')
              .values_list('capability',flat=True).first())
        gates['lider:'+(last or 'RED-01')].disagreed+=1
    return {'si_encaja':len(confirmed),
            'descartadas_por_ti':AuditEvent.objects.filter(action='network.contact_discarded',created_at__gte=since,created_at__lt=until).count()}

def _prefilter(gates,since,until):
    gate=gates['prefiltro']
    for event in AuditEvent.objects.filter(action='operator.comment_prefilter',created_at__gte=since,created_at__lt=until):
        meta=event.metadata or {};gate.entered+=1
        if meta.get('decision')=='comment':gate.first+=1
        elif meta.get('decision')=='skip':gate.stop(event.target,_categories(meta.get('reasons')))
        else:gate.waiting+=1

# --------------------------------------------------------------------------- days without a post

def _day_cause(rows):
    """(cause, piece id) of a day whose pieces (oldest first) published nothing."""
    if not rows:return 'sin_pieza',None
    piece,status,action=rows[-1];v=piece.verification or {}
    if editorial.budget_stopped(piece):return 'dinero',str(piece.id)
    if status=='skipped':return 'saltada_por_el_director',str(piece.id)
    if status=='failed' or (status=='blocked' and piece.note.startswith(('Ciclo detenido','Preparación interrumpida'))):
        return 'fallo',str(piece.id)
    if status=='blocked':
        if piece.note.startswith('No se pudo aplicar el comentario'):return 'compuerta:retoque',str(piece.id)
        if v.get('verdict')=='blocked':return ('compuerta:reglas_post' if v.get('rules') else 'compuerta:verificador'),str(piece.id)
        return 'compuerta:imagen',str(piece.id)
    if status=='discarded':
        lead=(getattr(action,'review',None) or {}).get('decision')=='discard'
        return ('compuerta:lider:CONT-09' if lead else 'compuerta:politica:CONT-09'),str(piece.id)
    return {'vetoed':'vetada_por_ti','expired':'caducada','uncertain':'incierta'}.get(status,'sin_publicar'),str(piece.id)

def _days(first,last):
    by_day=defaultdict(list)
    for p in EditorialPiece.objects.filter(slot_date__gte=first,slot_date__lte=last,second_of_day=False).order_by('created_at'):
        action=editorial.latest_action(p);by_day[p.slot_date].append((p,editorial.status(p,action),action))
    out=[];second={'dias':0,'salvados':0};day=first
    while day<=last:
        rows=by_day.get(day,[])
        published=any(status=='published' for _,status,_ in rows)
        if len(rows)>1 and compuertas.gate_blocked(rows[0][0]):
            second['dias']+=1;second['salvados']+=int(published)
        if not published:
            cause,piece=_day_cause(rows)
            out.append({'fecha':day.isoformat(),'causa':cause,'pieza':piece,'intentos':len(rows)})
        day+=timedelta(days=1)
    return out,second

# --------------------------------------------------------------------------- entry points

def audit(since,until):
    """The audit between two moments; days without a post are the local days in between, up to the day before `until`."""
    gates=Gates();tz=operador.local_tz()
    pieces={str(p.id):p for p in EditorialPiece.objects.filter(created_at__gte=since,created_at__lt=until).order_by('created_at')}
    for p in pieces.values():
        if p.state!=EditorialPiece.State.PREPARING:_piece(gates,p)
    _owner_overrides(gates,since,until,pieces);_reworks(gates,since,until);_proposals(gates,since,until);_prefilter(gates,since,until)
    network=_network_labels(gates,since,until)
    days,second=_days(since.astimezone(tz).date(),(until.astimezone(tz)-timedelta(days=1)).date())
    ordered=[k for k in ORDER if k in gates]+sorted(k for k in gates if k not in ORDER)
    rows=[gates[k].row() for k in ordered if gates[k].entered or gates[k].disagreed or gates[k].waiting]
    return {'desde':since.astimezone(tz).date().isoformat(),'hasta':(until.astimezone(tz)-timedelta(days=1)).date().isoformat(),
            'compuertas':rows,'dias_sin_post':days,'dias_sin_post_por_causa':dict(Counter(d['causa'] for d in days)),
            'callejones_sin_salida':[d for d in days if d['causa'].startswith('compuerta:')],'segundo_intento':second,'red':network}

def auditar(dias=7,now=None):
    """The last `dias` local days, today excluded from the days without a post (its hour may not have come)."""
    now=now or timezone.now();tz=operador.local_tz()
    from datetime import datetime, time
    today=datetime.combine(now.astimezone(tz).date(),time(0),tzinfo=tz)
    report=audit(today-timedelta(days=max(1,int(dias))),now)
    report['dias_sin_post']=[d for d in report['dias_sin_post'] if d['fecha']<today.date().isoformat()]
    report['callejones_sin_salida']=[d for d in report['callejones_sin_salida'] if d['fecha']<today.date().isoformat()]
    report['dias_sin_post_por_causa']=dict(Counter(d['causa'] for d in report['dias_sin_post']))
    report['hasta']=(today.date()-timedelta(days=1)).isoformat();report['dias']=int(dias)
    return report

def weekly(w):
    """resumen_semanal: a compact view of the week (no ids): enough for the analysis to name a gate that stops too much."""
    report=audit(w.start,min(w.end,timezone.now()))  # a week still running has no future days without a post
    return {'disponible':True,'por_compuerta':{r['compuerta']:{'entraron':r['entraron'],'paradas':r['paradas'],
            'pasaron_tras_reintento':r['pasaron_tras_reintento'],'con_observaciones':r['con_observaciones'],
            'tasa_parada_pct':None if r['tasa_parada'] is None else round(100*r['tasa_parada'],1),
            'motivo_principal':r['motivos'][0][0] if r['motivos'] else None,
            'gustavo_no_estuvo_de_acuerdo':r['gustavo']['no_estuvo_de_acuerdo']} for r in report['compuertas']},
            'dias_sin_post_por_causa':report['dias_sin_post_por_causa'],'segundo_intento':report['segundo_intento']}

# --------------------------------------------------------------------------- notice

def alert_rate():
    try:return float(os.environ.get('COMPUERTAS_ALERTA_TASA','0.5'))
    except ValueError:return 0.5

def alert_minimum():
    try:return max(1,int(os.environ.get('COMPUERTAS_ALERTA_MIN','4')))
    except ValueError:return 4

def vigilar(now=None):
    """One notice per gate and week when its 7-day stop rate reaches COMPUERTAS_ALERTA_TASA (with at least
    COMPUERTAS_ALERTA_MIN decisions), and one per day that ended without a post because of a gate. COMPUERTAS_ALERTAS=false
    turns both off."""
    if os.environ.get('COMPUERTAS_ALERTAS','true').strip().lower()=='false':return 0
    from .notificaciones import avisar
    now=now or timezone.now();report=auditar(7,now);sent=0
    year,week,_=now.astimezone(operador.local_tz()).isocalendar()
    for row in report['compuertas']:
        decided=row['pasaron_a_la_primera']+row['pasaron_tras_reintento']+row['paradas']
        if row['compuerta'] in NOT_ALERTED or decided<alert_minimum() or (row['tasa_parada'] or 0)<alert_rate():continue
        top=', '.join(f'{k} ({n})' for k,n in row['motivos'][:3])
        created=avisar('gate_alert',f'{row["nombre"]}: frenó {row["paradas"]} de {decided} en 7 días',
                       (f'Lo que más la para: {top}. ' if top else '')+'Antes de tocar umbrales, mira la auditoría (compuertas auditar).',
                       link='/calendario?vista=lista&no_salio=1',ref=f'gate_alert:{row["compuerta"]}:{year}-W{week:02d}')
        sent+=int(created is not None)
    yesterday=(now.astimezone(operador.local_tz())-timedelta(days=1)).date().isoformat()
    for day in report['callejones_sin_salida']:
        if day['fecha']!=yesterday:continue
        gate=day['causa'].split(':',1)[1]
        created=avisar('gate_alert',f'El {day["fecha"][8:10]}/{day["fecha"][5:7]} no salió post: lo paró {label(gate)}',
                       'Nadie lo reintentó ni desestimó el bloqueo. Revisa el motivo en el detalle de la pieza.',
                       link=f'/calendario/pieza/{day["pieza"]}' if day['pieza'] else '/calendario?vista=lista&no_salio=1',
                       ref=f'gate_day:{day["fecha"]}')
        sent+=int(created is not None)
    return sent

def render(report):
    out=[f'Auditoría de compuertas · {report.get("dias","?")} días ({report["desde"]} → {report["hasta"]}). Solo ids y categorías.','']
    for r in report['compuertas']:
        rate='—' if r['tasa_parada'] is None else f'{round(100*r["tasa_parada"])} %'
        out.append(f'{r["nombre"]}: {r["entraron"]} entraron · {r["pasaron_a_la_primera"]} a la primera · '
                   f'{r["pasaron_tras_reintento"]} tras reparar o reintentar · {r["paradas"]} paradas ({rate}) · {r["en_espera"]} en espera')
        if r['con_observaciones']:out.append(f'  Salieron con observaciones: {r["con_observaciones"]}')
        if r['motivos']:out.append('  Motivos: '+' · '.join(f'{k} {n}' for k,n in r['motivos']))
        if r['ejemplos']:out.append('  Ejemplos: '+' · '.join(f'{e["id"]} ({e["categoria"]})' for e in r['ejemplos']))
        g=r['gustavo']
        if g['no_estuvo_de_acuerdo'] or g['vetadas_tras_pasar']:
            out.append(f'  Gustavo: paradas {r["paradas"]}, no estuvo de acuerdo en {g["no_estuvo_de_acuerdo"]} · '
                       f'vetó {g["vetadas_tras_pasar"]} de las que pasaron')
        if r.get('descartes_sin_reescritura') is not None:out.append(f'  Descartes sin reescritura: {r["descartes_sin_reescritura"]}')
        if r.get('revisiones') is not None:out.append(f'  Cuenta personas: {r["entraron"]} personas en {r["revisiones"]} revisiones del líder')
    if not report['compuertas']:out.append('Sin actividad de compuertas en el periodo.')
    out.append('')
    days=report['dias_sin_post']
    out.append(f'Días sin post: {len(days)}'+(' ('+' · '.join(f'{k} {n}' for k,n in sorted(report['dias_sin_post_por_causa'].items()))+')' if days else ''))
    for d in days:out.append(f'  {d["fecha"]} · {d["causa"]}'+(f' · pieza {d["pieza"]}' if d['pieza'] else '')+f' · {d["intentos"]} intento(s)')
    out.append(f'Callejones sin salida (una compuerta paró el día y nadie lo reintentó ni desestimó): {len(report["callejones_sin_salida"])}')
    second=report['segundo_intento']
    out.append(f'Segundo intento: {second["dias"]} día(s), con post al final en {second["salvados"]}.')
    net=report['red']
    out.append(f'Red: «Sí, encaja» tras una duda del líder {net["si_encaja"]} · personas que descartaste {net["descartadas_por_ti"]}.')
    return '\n'.join(out)
