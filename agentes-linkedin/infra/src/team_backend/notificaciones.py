"""Where each event goes (doc «Funciones nuevas del rediseño», rev 18, «Qué va a cada lado»).

Rule: if only Gustavo can solve it, it is a Tu turno card (computed live by rediseno_views.alerts and the team
questions); otherwise it is a Notificación kept 7 days. Each kind has a default push, and Gustavo can turn the
push of any kind off or on in Ajustes › Notificaciones (OfficePreference.push_disabled and push_enabled)."""
from datetime import timedelta
from django.db import IntegrityError, transaction
from django.utils import timezone
from .models import Notification, OfficePreference

RETENTION=timedelta(days=7)
# Tu turno kinds: (priority, push by default, label in Ajustes). The card itself is computed, not stored.
INBOX_KINDS={
    'cycle_stopped':('importante',True,'Ciclo detenido'),
    'uncertain':('urgente',True,'Acción incierta'),
    'linkedin_expired':('urgente',True,'LinkedIn caducado'),
    'machine_paused':('urgente',True,'Máquina detenida desde la app'),
    'linkedin_expiring':('importante',True,'LinkedIn caduca pronto'),
    'account_paused':('importante',True,'Cuenta en pausa'),
    'conversation':('importante',True,'Conversación que te toca'),
    'question':('cuando_puedas',True,'Pregunta nueva del equipo'),
    'profile_task':('cuando_puedas',True,'Tarea de perfil nueva'),
}
# Notificaciones kinds: (calendar layer, push by default, label in Ajustes).
FEED_KINDS={
    'referents_review':('conversaciones',True,'Revisión mensual y experimentos de referentes'),
    'capture_scheduled':('publicaciones',True,'Fecha de una idea urgente'),
    'piece_scheduled':('publicaciones',True,'Pieza lista o programada'),
    'piece_published':('publicaciones',True,'Pieza publicada'),
    'piece_blocked':('sistema',True,'Pieza bloqueada por el verificador'),
    'piece_discarded':('publicaciones',False,'Pieza descartada por la política'),
    'connection_fit':('red',False,'Conexión nueva que encaja'),
    'opportunity':('conversaciones',False,'Oportunidad nueva o que cambia de etapa'),
    'observatory':('conversaciones',False,'Hallazgos del Observatorio'),
    'invites_expected':('red',False,'Invitaciones previstas'),
    'capture_processed':('tuyo',False,'Captura procesada'),
    'machine_paused_env':('sistema',True,'Máquina detenida desde el servidor'),
    'lead_silent':('sistema',True,'El líder no aprueba nada en una capacidad'),
    'weekly_summary':('tuyo',True,'Resumen de la semana listo'),
}

# Computed every time «Próximo» is read: they push when they happen but are never stored in the feed.
COMPUTED_KINDS=('invites_expected','machine_paused_env')
# Notificaciones kinds that still push with high priority: the machine stopped from the server stops everything.
URGENT_FEED_KINDS=('machine_paused_env',)
# Kinds nothing can emit yet: no switch in Ajustes until their event exists (profile tasks, TUR-18).
WITHOUT_EMITTER=('profile_task',)

def _switches():
    """(off, on): what Gustavo turned off, and what he turned on although its default is off."""
    current=OfficePreference.current()
    return set(current.push_disabled or []),set(current.push_enabled or [])

def _enabled(kind,default,switches):
    off,on=switches
    return kind not in off and (default or kind in on)

def push_enabled(kind):
    default=(INBOX_KINDS.get(kind) or FEED_KINDS.get(kind) or (None,False))[1]
    return _enabled(kind,default,_switches())

def push_types():
    switches=_switches()
    rows=[{'kind':k,'label':v[2],'goes_to':'tu_turno','default':v[1],'enabled':_enabled(k,v[1],switches)} for k,v in INBOX_KINDS.items()
          if k not in WITHOUT_EMITTER]
    rows+=[{'kind':k,'label':v[2],'goes_to':'notificaciones','default':v[1],'enabled':_enabled(k,v[1],switches)} for k,v in FEED_KINDS.items()]
    return rows

def avisar(kind,title,detail='',link='',ref=None):
    """Record (Notificaciones) and push an event according to the table. Never breaks the work that calls it."""
    from .alerts import notify
    try:
        created=None
        if kind in COMPUTED_KINDS:pass  # pushed only: «Próximo» computes it while it lasts
        elif kind in FEED_KINDS:
            try:
                with transaction.atomic():
                    created=Notification.objects.create(kind=kind,layer=FEED_KINDS[kind][0],title=title[:300],detail=detail or '',
                                                        link=link[:300],ref=ref[:160] if ref else None)
            except IntegrityError:return None  # the same event was already recorded
        elif kind not in INBOX_KINDS:return None
        if push_enabled(kind):
            notify(title[:120],detail[:200] or title[:200],url='/tu-turno' if kind in INBOX_KINDS else (link or '/notificaciones'),tag=f'0ff1ce-{kind}',
                   urgent=INBOX_KINDS.get(kind,('',))[0]=='urgente' or kind in URGENT_FEED_KINDS)
        return created
    except Exception:
        return None

def purge(now=None):
    Notification.objects.filter(created_at__lt=(now or timezone.now())-RETENTION).delete()

def unread():
    return Notification.objects.filter(read_at__isnull=True,created_at__gte=timezone.now()-RETENTION).count()

def upcoming(now=None):
    """Computed «PRÓXIMO»: the next piece within 48 h, invitations expected in the next day, a server-side stop."""
    from . import editorial, operador, red
    from .models import Contact, EditorialPiece
    now=now or timezone.now();tz=operador.local_tz();out=[]
    for piece in EditorialPiece.objects.filter(state='ready',scheduled_for__gt=now,scheduled_for__lte=now+timedelta(hours=48)).order_by('scheduled_for')[:2]:
        action=editorial.latest_action(piece)
        if action and action.state in ('proposed','approved'):
            when=piece.scheduled_for.astimezone(tz)
            out.append({'id':f'piece_scheduled:{piece.id}','kind':'piece_scheduled','layer':'publicaciones',
                        'title':f'Sale la pieza «{(piece.brief or {}).get("thesis") or piece.final_text[:80]}»',
                        'detail':f'Puedes vetarla en el detalle hasta las {when:%H:%M}.','link':f'/calendario/pieza/{piece.id}','at':piece.scheduled_for})
    due=[c for c in Contact.objects.filter(stage='followed',followed_at__isnull=False) if c.followed_at+red.invite_after()<=now+timedelta(hours=24)]
    if due and not red.invites_blocked(now)[0]:
        out.append({'id':'invites_expected','kind':'invites_expected','layer':'red',
                    'title':f'El equipo invitará a {len(due)} {"persona" if len(due)==1 else "personas"} que encajan',
                    'detail':'Si los topes del día lo permiten.','link':'/personas?etapa=followed','at':now+timedelta(hours=24)})
    if operador.env_paused():
        out.append({'id':'machine_paused_env','kind':'machine_paused_env','layer':'sistema','title':'La máquina está detenida desde el servidor',
                    'detail':'La parada viene de OPERATOR_PAUSED y no se levanta desde la app.','link':'/ajustes#maquina','at':now})
    return out
