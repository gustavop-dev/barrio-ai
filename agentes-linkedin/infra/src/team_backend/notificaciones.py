"""Where each event goes (doc «Funciones nuevas del rediseño», rev 18, «Qué va a cada lado»).

Rule: if only Gustavo can solve it, it is a Tu turno card (computed live by rediseno_views.alerts and the team
questions); otherwise it is a Notificación kept 7 days. Each kind has a default push, and Gustavo can turn the
push of any kind off or on in Ajustes › Notificaciones (OfficePreference.push_disabled and push_enabled).

Whose (organizaciones, phase 5): every notice says whose it is, `avisar(..., member=)`: a member's notice is recorded for
her and pushed only to her devices, with her preferences; ORGANIZACION (the total stop, the lead, the gates, a cycle of
the machine) is one row per active member, each pushed with her own preferences. Without members (an installation before
organizations) everything is as before: one row and a push to every device. With members, a notice that names nobody is
dropped with a warning, never guessed. OPERATOR_ALERT_WEBHOOK is the first member's channel (Gustavo's, as before): it
gets her notices and the organization's, never another member's."""
import logging
from datetime import timedelta
from django.db import IntegrityError, transaction
from django.utils import timezone
from .models import Notification, OfficePreference

logger=logging.getLogger('team_backend.notificaciones')
ORGANIZACION='organizacion'  # avisar(member=ORGANIZACION): a notice of the whole organization, for every active member

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
    'dm_ready':('importante',True,'Mensaje sugerido para alguien que conversó contigo'),
    'day_request':('importante',True,'Una fecha que pediste no se puede cumplir'),
    'question':('cuando_puedas',True,'Pregunta nueva del equipo'),
    'profile_task':('cuando_puedas',True,'Tarea de perfil nueva'),
}
# Notificaciones kinds: (calendar layer, push by default, label in Ajustes).
FEED_KINDS={
    'profile_reviewed':('tuyo',False,'Revisión de perfil sin cambios'),
    'referents_review':('conversaciones',True,'Revisión mensual y experimentos de referentes'),
    'capture_scheduled':('publicaciones',True,'Fecha de una idea tuya'),
    'piece_scheduled':('publicaciones',True,'Pieza lista o programada'),
    'piece_published':('publicaciones',True,'Pieza publicada'),
    'piece_blocked':('sistema',True,'Pieza bloqueada por el verificador'),
    'piece_discarded':('publicaciones',False,'Pieza descartada por la política'),
    'connection_fit':('red',False,'Conexión nueva que encaja'),
    'network_doubt':('red',True,'El líder frenó a una persona que encaja'),
    'opportunity':('conversaciones',False,'Oportunidad nueva o que cambia de etapa'),
    'observatory':('conversaciones',False,'Hallazgos del Observatorio'),
    'invites_expected':('red',False,'Invitaciones previstas'),
    'capture_processed':('tuyo',False,'Captura procesada'),
    'machine_paused_env':('sistema',True,'Máquina detenida desde el servidor'),
    'lead_silent':('sistema',True,'El líder no aprueba nada en una capacidad'),
    'gate_alert':('sistema',True,'Una compuerta frena demasiado o un día quedó sin post'),
    'linkedin_canary':('sistema',True,'Prueba diaria de LinkedIn: rota, sin correr o de nuevo bien'),
    'navegador_salida':('sistema',True,'LinkedIn directo: el servicio no abre la cuenta por otra salida a internet'),
    'weekly_summary':('tuyo',True,'Resumen de la semana listo'),
    'weekly_plan':('publicaciones',True,'Plan de la semana listo'),
    'monthly_review':('tuyo',True,'Revisión mensual lista'),
}

# Computed every time «Próximo» is read: they push when they happen but are never stored in the feed.
COMPUTED_KINDS=('invites_expected','machine_paused_env')
# Notificaciones kinds that still push with high priority: the machine stopped from the server stops everything.
URGENT_FEED_KINDS=('machine_paused_env',)
# Kinds nothing can emit yet: profile_task now has the EST/TUR-18 emitter.
WITHOUT_EMITTER=()

def _switches(user):
    """(off, on): what she turned off, and what she turned on although its default is off (her OfficePreference)."""
    current=OfficePreference.of(user)
    return set(current.push_disabled or []),set(current.push_enabled or [])

def _enabled(kind,default,switches):
    off,on=switches
    return kind not in off and (default or kind in on)

def push_enabled(kind,user):
    """Whether `user` gets the push of `kind` (her own switches; `user=None` only without members: the only ones)."""
    default=(INBOX_KINDS.get(kind) or FEED_KINDS.get(kind) or (None,False))[1]
    return _enabled(kind,default,_switches(user))

def push_types(user):
    """Ajustes › Notificaciones: every kind with her own switch."""
    switches=_switches(user)
    rows=[{'kind':k,'label':v[2],'goes_to':'tu_turno','default':v[1],'enabled':_enabled(k,v[1],switches)} for k,v in INBOX_KINDS.items()
          if k not in WITHOUT_EMITTER]
    rows+=[{'kind':k,'label':v[2],'goes_to':'notificaciones','default':v[1],'enabled':_enabled(k,v[1],switches)} for k,v in FEED_KINDS.items()]
    return rows

def _recipients(member):
    """Whose a notice is: [member]; every active member for ORGANIZACION; [None] without members (as before). None when
    nobody can be named (members exist and the caller named none): the notice is dropped, never guessed."""
    from . import miembros
    if member==ORGANIZACION:return miembros.active_members()
    if member is None:return None if miembros.exist() else [None]
    return [member]

def _ref(ref,member):
    """The dedup key of her copy: the first member's (and an installation without members) is the one of before, and so
    is a ref that already names her (weekly_summary:<week>:<member id>, …)."""
    from . import miembros
    if not ref:return None
    return ref[:160] if miembros.is_first(member) or str(member.pk) in ref else f'{ref[:120]}@{member.pk}'

def avisar(kind,title,detail='',link='',ref=None,*,member):
    """Record (Notificaciones) and push an event according to the table, for `member` (a Member, or ORGANIZACION for the
    whole organization; None only without members). Never breaks the work that calls it."""
    from . import miembros
    from .alerts import notify
    try:
        recipients=_recipients(member)
        if recipients is None:
            logger.warning('notice_without_member kind=%s',kind);return None
        if kind not in COMPUTED_KINDS and kind not in FEED_KINDS and kind not in INBOX_KINDS:return None
        created=None
        for target in recipients:
            if kind in FEED_KINDS and kind not in COMPUTED_KINDS:  # COMPUTED_KINDS push only: «Próximo» computes them
                try:
                    with transaction.atomic():
                        row=Notification.objects.create(kind=kind,layer=FEED_KINDS[kind][0],title=title[:300],detail=detail or '',
                                                        link=link[:300],ref=_ref(ref,target),member=target)
                except IntegrityError:continue  # the same event was already recorded for her
                created=created or row
            if target is not None and not (target.active and target.user.is_active):continue  # recorded; no push
            user=target.user if target is not None else None
            if push_enabled(kind,user):
                notify(title[:120],detail[:200] or title[:200],url='/tu-turno' if kind in INBOX_KINDS else (link or '/notificaciones'),tag=f'0ff1ce-{kind}',
                       urgent=INBOX_KINDS.get(kind,('',))[0]=='urgente' or kind in URGENT_FEED_KINDS,
                       users=None if user is None else [user],webhook=miembros.is_first(target))
        return created
    except Exception:
        logger.warning('notice_failed kind=%s',kind,exc_info=True)
        return None

def empujar(kind,title,detail,url,tag,*,member):
    """Push only (the row was recorded by its own transaction, like the referents' notices): to `member`'s devices with
    her switches, as avisar does. Returns whether anything was sent."""
    from . import miembros
    from .alerts import notify
    recipients=_recipients(member)
    if recipients is None:
        logger.warning('push_without_member kind=%s',kind);return False
    sent=False
    for target in recipients:
        if target is not None and not (target.active and target.user.is_active):continue
        user=target.user if target is not None else None
        if push_enabled(kind,user):
            sent=notify(title,detail,url=url,tag=tag,users=None if user is None else [user],webhook=miembros.is_first(target)) or sent
    return sent

def de_cuenta(account):
    """Whose notice it is when it is about an account: its member (None without members, or for an account of nobody
    among several members: then avisar drops it)."""
    from . import miembros
    return miembros.member_of_account(account) if account is not None else None

def de_contenido(row):
    """Whose notice it is when it is about her content (a piece, a capture): its member; a row without one is the first
    member's (alcance.DUENO's rule)."""
    from . import miembros
    return row.member if row.member_id else miembros.of_job({})

def de_usuario(user):
    """A notice about the work of `user`: her member's; the machine's own users (the autopilot robot, a service) work for
    the organization, so their notices go to everyone."""
    from . import miembros
    member=miembros.member_of_user(user)
    if member is not None:return member
    return ORGANIZACION if miembros.exist() else None

def purge(now=None):
    Notification.objects.filter(created_at__lt=(now or timezone.now())-RETENTION).delete()

def de_ella(rows,member):
    """Her notices (alcance.de: hers, and the first member's also those without a member)."""
    from . import alcance
    return alcance.de(rows,member)

def unread(member):
    return de_ella(Notification.objects.filter(read_at__isnull=True,created_at__gte=timezone.now()-RETENTION),member).count()

def upcoming(now=None,member=None):
    """Computed «PRÓXIMO»: the next piece within 48 h, invitations expected in the next day (the member's people, unless
    her invitations are blocked), a server-side stop. Without a member, the only active one."""
    from . import editorial, operador, red
    from .models import Contact, EditorialPiece
    from . import alcance
    now=now or timezone.now();tz=operador.local_tz();out=[];member=operador.member_of(member=member)
    pieces=alcance.de(EditorialPiece.objects.all(),member) if member is not None else EditorialPiece.objects.all()  # hers
    for piece in pieces.filter(state='ready',scheduled_for__gt=now,scheduled_for__lte=now+timedelta(hours=48)).order_by('scheduled_for')[:2]:
        action=editorial.latest_action(piece)
        if action and action.state in ('proposed','approved'):
            when=piece.scheduled_for.astimezone(tz)
            out.append({'id':f'piece_scheduled:{piece.id}','kind':'piece_scheduled','layer':'publicaciones',
                        'title':f'Sale la pieza «{(piece.brief or {}).get("thesis") or piece.final_text[:80]}»',
                        'detail':f'Puedes vetarla en el detalle hasta las {when:%H:%M}.','link':f'/calendario/pieza/{piece.id}','at':piece.scheduled_for})
    from . import miembros
    due=[c for c in miembros.mine(Contact.objects.filter(stage='followed',followed_at__isnull=False),member)
         if c.followed_at+red.invite_after()<=now+timedelta(hours=24)]
    if due and not red.invites_blocked(now,member)[0]:
        out.append({'id':'invites_expected','kind':'invites_expected','layer':'red',
                    'title':f'El equipo invitará a {len(due)} {"persona" if len(due)==1 else "personas"} que encajan',
                    'detail':'Si los topes del día lo permiten.','link':None,'at':now+timedelta(hours=24)})  # Personas lists only connections
    if operador.env_paused():
        out.append({'id':'machine_paused_env','kind':'machine_paused_env','layer':'sistema','title':'La máquina está detenida desde el servidor',
                    'detail':'La parada viene de OPERATOR_PAUSED y no se levanta desde la app.','link':'/ajustes#maquina','at':now})
    return out
