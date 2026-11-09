"""Events that move the characters of the office scene (0ff1ce canvas, note «Qué mueve a cada personaje»).

Every event comes from real work, never from a simulation:
- consulta_biblioteca: an agent reads course units from the knowledge base (embeddings) before writing;
- entrega: a handoff between roles (an editorial stage passes its work to the next one, a drafted comment
  goes to the operator);
- publicacion: the operator executed a public write that LinkedIn confirmed (own post or comment).
Background work hands off too (job_done, lead_reviewed), so the office does not look idle while the team works: the
referents' new posts and the people of the barrio go from the researcher to Relaciones, the inbox reading reaches
Gustavo, the metrics go to the editorial desk, and an approved proposal goes to Operación.
The scene replays them in order, as a queue, and summarizes when many arrive."""
from datetime import timedelta
from django.utils import timezone
from .models import AuditEvent

TYPES=('consulta_biblioteca','entrega','publicacion')
NEXT_ROLE={'director':'copywriter_a','redactor':'lector_comprador','lectores':'director_editorial','seleccion':'editor_verificador',
           'verificador':'operador_cuenta','reparacion':'editor_verificador'}

def emit(kind,role,target='',detail=''):
    """Never breaks the work that emits it."""
    if kind not in TYPES:return
    try:AuditEvent.objects.create(action='office.event',target=role[:120],metadata={'tipo':kind,'rol':role,'destino':target,'detalle':(detail or '')[:200]})
    except Exception:pass

def handoff(role,target,*,cycle,edge,phase):
    """Add dispatcher traffic without replacing the workflow's existing events."""
    label='Solicitud' if phase=='request' else 'Respuesta'
    try:
        AuditEvent.objects.create(action='office.orchestration',target=role[:120],metadata={
            'tipo':'entrega','rol':role,'destino':target,'detalle':f'{label}: {edge}'[:200],
            'cycle_id':str(cycle),'edge':edge,'phase':phase})
    except Exception:pass

def since(moment=None,limit=50):
    moment=moment or timezone.now()-timedelta(minutes=10)
    rows=AuditEvent.objects.filter(action__in=['office.event','office.orchestration'],created_at__gt=moment).order_by('created_at','id')[:limit]
    return [dict(id=row.id,ts=row.created_at,**{k:row.metadata.get(k,'') for k in ('tipo','rol','destino','detalle')},
                 **({'source':'orchestration'} if row.action=='office.orchestration' else {})) for row in rows]

def _count(n,one,many):
    return f'{n} {one if n==1 else many}'

def job_done(kind,result):
    """The handoff a finished background job makes in the scene, only when it produced something (operador.run_job)."""
    r=result if isinstance(result,dict) else {}
    if kind=='observe' and r.get('new_posts'):
        emit('entrega','investigador_referentes','relaciones_comunidad',
             _count(r['new_posts'],'publicación nueva de referentes','publicaciones nuevas de referentes'))
    elif kind=='discover_network' and r.get('new'):
        emit('entrega','investigador_referentes','',_count(r['new'],'persona nueva para el barrio','personas nuevas para el barrio'))
    elif kind=='classify_contacts' and r.get('classified'):
        emit('entrega','investigador_referentes','relaciones_comunidad',f"{r.get('fit',0)} de {r['classified']} {'persona encaja' if r['classified']==1 else 'personas encajan'} en el barrio")
    elif kind=='read_inbox' and (r.get('flagged') or r.get('read')):
        detail=_count(r['flagged'],'conversación te toca','conversaciones te tocan') if r.get('flagged') else _count(r['read'],'conversación leída','conversaciones leídas')
        emit('entrega','conversaciones_inbox','',detail)
    elif kind=='collect_metrics' and (r.get('captured') or r.get('audience')=='creada'):
        parts=[_count(r['captured'],'corte','cortes')] if r.get('captured') else []
        detail=f"Métricas de {parts[0]} y la audiencia del día" if parts and r.get('audience')=='creada' else (f'Métricas de {parts[0]}' if parts else 'La audiencia del día')
        emit('entrega','analista_barrio_resultados','director_editorial',detail)

LEAD_DRAFTERS={'INT-03':('relaciones_comunidad','Comentario aprobado por el líder','Comentario descartado por el líder'),
               'CONT-09':('director_editorial','Pieza aprobada por el líder','Pieza descartada por el líder')}
NETWORK_DRAFT=('relaciones_comunidad','Acción de red aprobada por el líder','Acción de red descartada por el líder')

def lead_reviewed(capability,decision):
    """The agente líder judged a proposal (autopiloto.policy_review): approved, its drafter takes it to Operación; discarded,
    the drafter takes it back. A retry (Jev unavailable) moves nobody."""
    role,approved,discarded=LEAD_DRAFTERS.get(capability,NETWORK_DRAFT)
    if decision=='approve':emit('entrega',role,'operador_cuenta',approved)
    elif decision=='discard':emit('entrega',role,'',discarded)
