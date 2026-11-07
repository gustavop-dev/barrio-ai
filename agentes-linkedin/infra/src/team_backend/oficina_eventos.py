"""Events that move the characters of the office scene (0ff1ce canvas, note «Qué mueve a cada personaje»).

Every event comes from real work, never from a simulation:
- consulta_biblioteca: an agent reads course units from the knowledge base (embeddings) before writing;
- entrega: a handoff between roles (an editorial stage passes its work to the next one, a drafted comment
  goes to the operator);
- publicacion: the operator executed a public write that LinkedIn confirmed (own post or comment).
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

def since(moment=None,limit=50):
    moment=moment or timezone.now()-timedelta(minutes=10)
    rows=AuditEvent.objects.filter(action='office.event',created_at__gt=moment).order_by('created_at')[:limit]
    return [dict(id=row.id,ts=row.created_at,**{k:row.metadata.get(k,'') for k in ('tipo','rol','destino','detalle')}) for row in rows]
