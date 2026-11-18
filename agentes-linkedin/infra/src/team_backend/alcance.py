"""Whose data each route reads or writes (organizaciones, phase 5; docs/plan-organizaciones.md «Fase 5: lo construido»).

Gustavo, 17/11/2026: «cada una con su cuenta, y ya él maneje de su lado sus cosas». Each member sees and handles only
her own things; not even the organization's admin sees another member's conversations, drafts or private notes. This
module is the one place that says it, in three parts:

1. RUTAS classifies every route of team_backend.urls (and RAIZ the project's own): MIEMBRO (what the user's member owns;
   another member's id answers 404, never 403, so it does not reveal that it exists), ORGANIZACION (the same for every
   member: the opportunities funnel, the referents, the library, the AI spend, the total stop), ADMINISTRADOR (the
   organization's active admin only) and SERVICIO (a credential of its own: a webhook signature, a one-use ticket, the
   login itself). A route that is not here is refused at runtime (RutaClasificada, in DEFAULT_PERMISSION_CLASSES) and
   tests/test_alcance.py fails, so a new route cannot ship without saying whose it is.
2. DUENO says, for each model a member owns, the path from a row to its owner: a member (`member`, 'piece__member'…),
   a LinkedIn account (`account`, 'contact__account'…) or a user. `de(rows, member)` narrows any queryset to hers and
   `obtener(request, Model, **lookup)` fetches one object of hers or raises 404. Views use only these two.
3. `miembro(request)`: the member of the authenticated user, explicitly. A user who is not a member (a service
   credential, the autopilot robot) acts for the only active member while there is one, as before organizations; with
   several active members she gets MiembroRequerido (400), never another member's data. With no members at all
   (an installation before organizations, the CI's base) it is None and everything reads as before.

`de(rows, None)` with members in the installation raises MiembroRequerido: no helper may fall back to «the» member.
`de(rows, TODOS)` reads every member's rows on purpose: the autopilot, the Slack summary and other machine readers that
work for the whole installation, never a screen."""
from django.db.models import Q
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import BasePermission

from . import miembros

MIEMBRO = 'miembro'
ORGANIZACION = 'organizacion'
ADMINISTRADOR = 'administrador'
SERVICIO = 'servicio'
CLASES = (MIEMBRO, ORGANIZACION, ADMINISTRADOR, SERVICIO)

_LIB = 'La biblioteca del curso es de la organización: se ingiere una vez y sirve a todos.'
_REF = 'Los referentes son de la organización (decisión del 17/11/2026); decide el dueño de la cuenta o el administrador.'
_OPP = 'Un solo embudo de oportunidades de la empresa, visible para todos sus miembros (decisión del 17/11/2026).'
_SES = 'Su propia sesión, sus dispositivos y sus suscripciones: siempre las del usuario que pide.'

# route (as in team_backend.urls) → class, or {METHOD: class} when the methods differ; then why.
RUTAS = {
    'referentes/revisiones': (ORGANIZACION, _REF),
    'referentes/analisis': (ORGANIZACION, _REF),
    'referentes/main-inicial': (ORGANIZACION, _REF),
    'referentes/cambios/<uuid:cid>/decidir': (ORGANIZACION, _REF),
    'referentes/experimentos/<uuid:eid>/decidir': (ORGANIZACION, _REF),
    'comunidad': (MIEMBRO, 'El estudio de comunidad es de una cuenta: solo las suyas.'),
    'comunidad/fuentes/<uuid:sid>/retirar': (MIEMBRO, 'Una fuente del estudio de una cuenta suya.'),
    'equipo/grafo': (ORGANIZACION, 'El mapa del equipo: metadatos sin contenido; los trabajos y ciclos ya se filtran por dueño.'),
    'equipo/ciclos/<uuid:cid>/decision': (ADMINISTRADOR, 'Reconocer un ciclo detenido es administrar trabajos de todo el equipo.'),
    'status': (ORGANIZACION, _LIB),
    'search': (ORGANIZACION, _LIB),
    'units': (ORGANIZACION, _LIB),
    'units/<str:uid>': (ORGANIZACION, _LIB),
    'sources/<path:key>': (ORGANIZACION, _LIB),
    'runs': (MIEMBRO, 'Sus trabajos (los de su usuario); el administrador ve los de la máquina, nunca los de otro miembro.'),
    'runs/<uuid:rid>': (MIEMBRO, 'Un trabajo suyo.'),
    'runs/<uuid:rid>/cancel': (MIEMBRO, 'Un trabajo suyo.'),
    'memory': (MIEMBRO, 'Sus hechos y los de la empresa, con la clave tal como está guardada.'),
    'memory/proposals': (MIEMBRO, 'Lo que propone queda en su memoria.'),
    'memory/<uuid:mid>/confirm': (MIEMBRO, 'Solo confirma hechos de su memoria.'),
    'integrity': (ADMINISTRADOR, 'Verificar la biblioteca es mantenimiento de la instalación.'),
    'audit': (ADMINISTRADOR, 'El registro de auditoría de toda la instalación es diagnóstico del administrador.'),
    'auth/session': (MIEMBRO, _SES),
    'auth/login': (SERVICIO, 'La credencial es el usuario y la contraseña; después, cada uno entra como sí mismo.'),
    'auth/logout': (MIEMBRO, _SES),
    'yo': (MIEMBRO, 'Quién es: su miembro, su rol, su organización y si su voz es provisional.'),
    'operador/overview': (MIEMBRO, 'Sus cuentas, sus cupos y sus propuestas; la parada total y el gasto de IA son de la organización.'),
    'operador/control': (ORGANIZACION, 'La parada total es de toda la máquina: cualquier miembro la detiene y la reanuda.'),
    'operador/feed': (MIEMBRO, 'Los eventos de sus propuestas, sus cuentas y sus trabajos.'),
    'oficina/actividad': (MIEMBRO, 'La escena del equipo, con el detalle de una pieza solo para su dueña.'),
    'oficina/eventos': (ORGANIZACION, 'La escena del equipo: rol, destino y un conteo, sin contenido ni ids.'),
    'push/key': (ORGANIZACION, 'La clave pública VAPID de la instalación.'),
    'push/subscriptions': (MIEMBRO, _SES),
    'push/unsubscribe': (MIEMBRO, _SES),
    'push/test': (MIEMBRO, _SES),
    'linkedin/oauth/start': (MIEMBRO, 'Conecta su propia cuenta oficial.'),
    'linkedin/oauth/callback': (SERVICIO, 'Vuelve de LinkedIn: la credencial es el state guardado en su sesión.'),
    'linkedin/status': (MIEMBRO, 'Su credencial oficial.'),
    'red/contacts': (MIEMBRO, 'Sus contactos (el registro compartido es la fase 6).'),
    'red/contacts/<uuid:cid>': (MIEMBRO, 'Un contacto suyo.'),
    'red/contacts/<uuid:cid>/discard': (MIEMBRO, 'Un contacto suyo.'),
    'red/contacts/<uuid:cid>/encaja': (MIEMBRO, 'Un contacto suyo.'),
    'red/summary': (MIEMBRO, 'Su red y su ritmo.'),
    'red/invitaciones-pendientes': (MIEMBRO, 'Sus invitaciones.'),
    'resultados': (MIEMBRO, 'Su audiencia, su contenido y sus acciones; el embudo de oportunidades y el gasto de IA, de la organización.'),
    'resultados/analitica': (MIEMBRO, 'La analítica de su cuenta.'),
    'resultados/embudo-comprador': (MIEMBRO, 'Sus compradores.'),
    'comprador/calcom/webhook': (SERVICIO, 'Cal.com: la credencial es la firma HMAC.'),
    'comprador/respuestas/<uuid:did>/agendo': (MIEMBRO, 'Una respuesta de un comprador suyo.'),
    'comprador/respuestas/<uuid:did>/referido': (MIEMBRO, 'Una respuesta de un comprador suyo.'),
    'comprador/reservas/<uuid:bid>/emparejar': (MIEMBRO, 'Una reserva de un comprador suyo (sin emparejar: del primer miembro, dueño del enlace de Cal.com).'),
    'comprador/entregas': (MIEMBRO, 'Los leads que ella entregó.'),
    'comprador/entregas/<uuid:hid>': (MIEMBRO, 'Un lead suyo.'),
    'comprador/entregas/<uuid:hid>/oportunidad': (MIEMBRO, 'Un lead suyo; la oportunidad que crea es de la organización y dice de quién vino.'),
    'comprador/lectura-semanal': (MIEMBRO, 'La lectura de su embudo del comprador.'),
    'perfil/<uuid:pid>': (MIEMBRO, 'Su propuesta de perfil (ya era por usuario).'),
    'perfil/<uuid:pid>/decision': (MIEMBRO, 'Su propuesta de perfil.'),
    'perfil/<uuid:pid>/documento': (MIEMBRO, 'Su propuesta de perfil.'),
    'perfil/<uuid:pid>/assets/<uuid:aid>': (MIEMBRO, 'Su propuesta de perfil.'),
    'perfil/<uuid:pid>/descarga': (MIEMBRO, 'Su propuesta de perfil.'),
    'perfil/<uuid:pid>/descarga/<str:token>': (SERVICIO, 'Descarga nativa: la credencial es un ticket de un uso, atado a su propuesta.'),
    'tu-turno': (MIEMBRO, 'Lo que le toca a ella.'),
    'tu-turno/vistos': (MIEMBRO, 'Lo que ella ya vio.'),
    'notificaciones': (MIEMBRO, 'Sus avisos y los de la organización.'),
    'notificaciones/leer': (MIEMBRO, 'Sus avisos.'),
    'preguntas': (MIEMBRO, 'Sus preguntas.'),
    'preguntas/<uuid:qid>/responder': (MIEMBRO, 'Una pregunta suya.'),
    'preguntas/<uuid:qid>/no-compartir': (MIEMBRO, 'Una pregunta suya.'),
    'preguntas/<uuid:qid>/deshacer': (MIEMBRO, 'Una pregunta suya.'),
    'preguntas/<uuid:qid>/mas-tarde': (MIEMBRO, 'Una pregunta suya.'),
    'memoria/hechos': (MIEMBRO, 'Sus hechos.'),
    'memoria/hechos/<str:key>/corregir': (MIEMBRO, 'Un hecho suyo.'),
    'memoria/hechos/<str:key>/retirar': (MIEMBRO, 'Un hecho suyo.'),
    'orientacion': (MIEMBRO, 'Su orientación.'),
    'oportunidades': (ORGANIZACION, _OPP),
    'oportunidades/<uuid:oid>': (ORGANIZACION, _OPP),
    'actividad': (MIEMBRO, 'Lo que hicieron sus cuentas.'),
    'calendario': (MIEMBRO, 'Su calendario; las oportunidades y la parada total, de la organización.'),
    'ajustes': (MIEMBRO, 'Su autonomía, sus topes, sus hechos y sus dispositivos; el gasto de IA, de la organización.'),
    'estrategia/semana': (MIEMBRO, 'Su plan de la semana.'),
    'estrategia/dias/<str:day>': (MIEMBRO, 'Su plan de la semana.'),
    'estrategia/mover': (MIEMBRO, 'Su plan de la semana.'),
    'estrategia/planear': (MIEMBRO, 'Su plan de la semana.'),
    'red/contacts/<uuid:cid>/notas': (MIEMBRO, 'Sus notas de un contacto suyo.'),
    'operador/referents/<uuid:rid>': (ORGANIZACION, _REF),
    'editorial/calendar': (MIEMBRO, 'Sus piezas.'),
    'editorial/pieces/<uuid:pid>': (MIEMBRO, 'Una pieza suya.'),
    'editorial/plan': (MIEMBRO, 'Su próxima pieza.'),
    'editorial/pieces/<uuid:pid>/images/<uuid:iid>': (MIEMBRO, 'Una pieza suya.'),
    'editorial/pieces/<uuid:pid>/images/<uuid:iid>/descartada': (MIEMBRO, 'Una pieza suya.'),
    'editorial/pieces/<uuid:pid>/document': (MIEMBRO, 'Una pieza suya.'),
    'editorial/pieces/<uuid:pid>/desestimar': (MIEMBRO, 'Una pieza suya.'),
    'capturas': (MIEMBRO, 'Sus capturas.'),
    'capturas/<uuid:cid>': (MIEMBRO, 'Una captura suya.'),
    'capturas/<uuid:cid>/audio': (MIEMBRO, 'Una captura suya.'),
    'capturas/<uuid:cid>/fecha': (MIEMBRO, 'Una captura suya.'),
    'galeria': (MIEMBRO, 'Sus fotos.'),
    'galeria/<uuid:pid>': (MIEMBRO, 'Una foto suya.'),
    'galeria/<uuid:pid>/imagen': (MIEMBRO, 'Una foto suya.'),
    'ajustes/preferencias': (MIEMBRO, 'Sus preferencias de fotos y de avisos.'),
    'operador/accounts': (MIEMBRO, 'Sus cuentas de LinkedIn.'),
    'operador/accounts/<uuid:aid>/check': (MIEMBRO, 'Una cuenta suya.'),
    'operador/accounts/<uuid:aid>/pause': (MIEMBRO, 'Una cuenta suya.'),
    'operador/accounts/<uuid:aid>/conexion': (MIEMBRO, 'Su sesión del navegador: solo la dueña (fase 1).'),
    'operador/conexiones/<uuid:lid>': (MIEMBRO, 'Su sesión del navegador.'),
    'operador/conexiones/<uuid:lid>/enlace': (MIEMBRO, 'Su sesión del navegador.'),
    'operador/conexiones/<uuid:lid>/cancelar': (MIEMBRO, 'Su sesión del navegador.'),
    'linkedin/pantalla/entrar': (SERVICIO, 'La vista remota: la credencial es un ticket de un uso de su dueña.'),
    'linkedin/pantalla/permitir': (SERVICIO, 'forward_auth de Caddy: la credencial es la cookie de la vista.'),
    'operador/referents': (ORGANIZACION, _REF),
    'operador/observe': (MIEMBRO, 'Lee referentes con una cuenta suya.'),
    'operador/posts': (MIEMBRO, 'Lo que leyeron sus cuentas.'),
    'operador/posts/<uuid:pid>/propose-comment': (MIEMBRO, 'Un post que leyó una cuenta suya.'),
    'operador/actions': (MIEMBRO, 'Sus propuestas.'),
    'operador/actions/<uuid:pid>': (MIEMBRO, 'Una propuesta suya.'),
    'operador/actions/<uuid:pid>/revise': (MIEMBRO, 'Una propuesta suya.'),
    'operador/actions/<uuid:pid>/approve': (MIEMBRO, 'Una propuesta suya.'),
    'operador/actions/<uuid:pid>/reject': (MIEMBRO, 'Una propuesta suya.'),
    'operador/actions/<uuid:pid>/execute': (MIEMBRO, 'Una propuesta suya.'),
    'operador/actions/<uuid:pid>/reconcile': (MIEMBRO, 'Una propuesta suya.'),
    'operador/actions/<uuid:pid>/resolve': (MIEMBRO, 'Una propuesta suya.'),
    'conversaciones/<uuid:cid>/cerrar': (MIEMBRO, 'Una conversación suya: nadie más la ve.'),
    'respuestas/<uuid:cid>/mensaje': (MIEMBRO, 'Un mensaje sugerido suyo.'),
    'resultados/resumen-semanal': (MIEMBRO, 'Su resumen.'),
    'resultados/resumen-semanal/generar': (MIEMBRO, 'Su resumen.'),
    'resultados/resumen-semanal/<uuid:sid>': (MIEMBRO, 'Un resumen suyo.'),
    'resultados/resumen-semanal/<uuid:sid>/visto': (MIEMBRO, 'Un resumen suyo.'),
    'resultados/resumen-semanal/<uuid:sid>/aplicar': (MIEMBRO, 'Un resumen suyo.'),
    'resultados/resumen-semanal/<uuid:sid>/descartar': (MIEMBRO, 'Un resumen suyo.'),
    'resultados/resumen-semanal/<uuid:sid>/deshacer': (MIEMBRO, 'Un resumen suyo.'),
    'auth/token': (SERVICIO, 'Entrar desde el teléfono: la credencial es el usuario y la contraseña.'),
    'auth/token/revocar': (MIEMBRO, _SES),
    'auth/dispositivos': (MIEMBRO, _SES),
    'auth/dispositivos/<uuid:did>': (MIEMBRO, _SES),
    'push/expo': (MIEMBRO, _SES),
    'app/errores': ({'GET': ADMINISTRADOR, 'POST': MIEMBRO},
                    'Informar un error es del usuario; leer los de todos es diagnóstico del administrador.'),
    'resultados/revision-mensual': (MIEMBRO, 'Su revisión.'),
    'resultados/revision-mensual/generar': (MIEMBRO, 'Su revisión.'),
    'resultados/revision-mensual/<uuid:rid>': (MIEMBRO, 'Una revisión suya.'),
    'resultados/revision-mensual/<uuid:rid>/visto': (MIEMBRO, 'Una revisión suya.'),
    'resultados/revision-mensual/cambios/<uuid:cid>/aprobar': (MIEMBRO, 'Un cambio de una revisión suya.'),
    'resultados/revision-mensual/cambios/<uuid:cid>/editar': (MIEMBRO, 'Un cambio de una revisión suya.'),
    'resultados/revision-mensual/cambios/<uuid:cid>/rechazar': (MIEMBRO, 'Un cambio de una revisión suya.'),
    'resultados/revision-mensual/cambios/<uuid:cid>/revertir': (MIEMBRO, 'Un cambio de una revisión suya.'),
}

# The project's own routes (linkedin_backend.urls), outside the API.
RAIZ = {
    'admin/': (ADMINISTRADOR, 'El admin de Django es la herramienta del superusuario del servidor, no un rol de miembro.'),
    'health': (SERVICIO, 'Chequeo de salud: no lee datos.'),
    '': (ORGANIZACION, 'La consola de la biblioteca (una página estática).'),
}


def clase(route, method='GET'):
    """The class of `route` for `method`, or None when the route is not classified."""
    entry = RUTAS.get(route)
    if entry is None:
        return None
    kind = entry[0]
    return kind.get(method.upper(), kind.get('GET')) if isinstance(kind, dict) else kind


def _route(request, view):
    match = getattr(request, 'resolver_match', None)
    if match is not None and match.route:
        route = match.route
        return route[len('api/v1/'):] if route.startswith('api/v1/') else route
    return _routes_of_view().get(type(view))  # a test that calls the view without resolving a URL


_BY_VIEW = None


def _routes_of_view():
    global _BY_VIEW
    if _BY_VIEW is None:
        from . import urls
        found = {}
        for pattern in urls.urlpatterns:
            view_class = getattr(pattern.callback, 'view_class', None) or getattr(pattern.callback, 'cls', None)
            if view_class is not None:
                found.setdefault(view_class, str(pattern.pattern))
        _BY_VIEW = found
    return _BY_VIEW


class RutaClasificada(BasePermission):
    """DEFAULT_PERMISSION_CLASSES (after KnowledgeAccess): a route that is not classified is refused (fail closed), and an
    ADMINISTRADOR route asks for the organization's active admin once the installation has members (before them, the
    view's own permission, as always). Views with their own permission_classes (login, device token, webhook, ticket
    download) are SERVICIO or her own session; tests/test_alcance.py checks every route anyway."""

    def has_permission(self, request, view):
        kind = clase(_route(request, view) or '', request.method)
        if kind is None:
            raise PermissionDenied('Esta ruta no dice de quién son sus datos (team_backend/alcance.py): se rechaza.')
        if kind == ADMINISTRADOR and miembros.exist() and not miembros.is_admin(request.user):
            raise PermissionDenied('Solo el administrador de la organización.')
        return True


# --------------------------------------------------------------------------- whose a row is

CUENTA = 'cuenta'      # the path ends at a ConnectorAccount: hers are miembros.accounts(member)
MIEMBRO_FK = 'miembro'  # the path ends at a Member: hers, plus rows without one when she is the first member
USUARIO = 'usuario'    # the path ends at a user: her own

# Model name → (lookup path, kind). A row whose path is empty (no account, no member) is the first member's: it was
# written before organizations, or by a worker of the code before this phase during a deploy.
DUENO = {
    'ConnectorAccount': ('', CUENTA),
    'ActionProposal': ('account', CUENTA),
    'ActionExecution': ('proposal__account', CUENTA),
    'ObservedPost': ('account', CUENTA),
    'Contact': ('account', CUENTA),
    'Conversation': ('account', CUENTA),
    'PostComment': ('account', CUENTA),
    'BrowserLogin': ('account', CUENTA),
    'BuyerJourney': ('contact__account', CUENTA),
    'BuyerDraft': ('contact__account', CUENTA),
    'MeetingBooking': ('contact__account', CUENTA),
    'LeadHandoff': ('contact__account', CUENTA),
    'CommunityStudy': ('account', CUENTA),
    'CommunitySource': ('study__account', CUENTA),
    'EditorialPiece': ('member', MIEMBRO_FK),
    'PieceImage': ('piece__member', MIEMBRO_FK),
    'PostMetric': ('piece__member', MIEMBRO_FK),
    'Capture': ('member', MIEMBRO_FK),
    'GalleryPhoto': ('member', MIEMBRO_FK),
    'TeamQuestion': ('member', MIEMBRO_FK),
    'WeeklySummary': ('member', MIEMBRO_FK),
    'WeeklyPlan': ('member', MIEMBRO_FK),
    'MonthlyReview': ('member', MIEMBRO_FK),
    'StrategyChange': ('review__member', MIEMBRO_FK),
    'AudienceSnapshot': ('member', MIEMBRO_FK),
    'Notification': ('member', MIEMBRO_FK),
    'ProfileProposal': ('owner', USUARIO),
    'Job': ('owner', USUARIO),
}


class _Todos:
    """Every member's rows, said explicitly (machine readers only, never a view)."""
    def __repr__(self):
        return 'alcance.TODOS'


TODOS = _Todos()


def _require(member):
    """`member` itself; None only for an installation without members, where everything counts as before."""
    if member is None and miembros.exist():
        raise miembros.MiembroRequerido('Hay miembros y esta lectura no dice de cuál: hay que indicarlo.')
    return member


def mine(member, path, kind):
    """The Q of the rows of `member` along `path` (DUENO's kinds). Q() (every row) without members."""
    if member is TODOS:
        return Q()
    member = _require(member)
    if member is None:
        return Q()
    if kind == USUARIO:
        return Q(**{path: member.user_id})
    first = miembros.is_first(member)
    if kind == CUENTA:
        own = Q(**{f'{path}__in' if path else 'pk__in': miembros.accounts(member).values('pk')})
        if first and path:
            own |= Q(**{f'{path}__isnull': True})
        return own
    own = Q(**{path: member})
    if first:
        own |= Q(**{f'{path}__isnull': True})
    return own


def de(rows, member):
    """`rows` (a queryset of a model in DUENO) narrowed to what `member` owns. `member=None`: every row in an installation
    without members; MiembroRequerido when there are members (never a guess)."""
    name = rows.model.__name__
    if name not in DUENO:
        raise LookupError(f'{name} no está en alcance.DUENO: di de quién es antes de filtrarlo.')
    return rows.filter(mine(member, *DUENO[name]))


def accounts(member):
    """Her accounts, as a queryset (every account without members)."""
    from .models import ConnectorAccount
    return de(ConnectorAccount.objects.all(), member)


def is_hers(obj, member):
    """Whether one row is hers (the object form of `de`)."""
    return de(type(obj).objects.filter(pk=obj.pk), member).exists()


def suyos(model, member, ids):
    """Which of `ids` (an audit trail's targets, as strings) are rows of `model` that are hers: what «Hecho
    recientemente» and the feed may name. Ids that are not keys of `model` are nobody's."""
    from django.core.exceptions import ValidationError
    keys = []
    for value in set(ids):
        try:
            keys.append(model._meta.pk.to_python(value))
        except (ValidationError, TypeError, ValueError):
            continue
    return {str(pk) for pk in de(model.objects.filter(pk__in=keys), member).values_list('pk', flat=True)}


def vista(user, item_id):
    """InboxSeen's key of a card she opened: the card id itself for the first member's user (the «Vista» of before
    organizations are hers) and for everyone in an installation without members; «u:<user id>:<card id>» for anyone
    else, so one person's «Vista» never marks another's card."""
    first = miembros.first_member_id()
    if first is None:
        return item_id
    _, Member, _ = miembros._models()
    if Member.objects.filter(pk=first, user_id=user.pk).exists():
        return item_id
    return f'u:{user.pk}:{item_id}'


def trabajos(request):
    """The jobs this request may see (jobs.visible_jobs: her own; every one with manage_jobs), never another member's:
    neither a job of another member's user, nor a content job queued for another member (miembros.job_params), nor a job
    on another member's account. The machine's own jobs (the autopilot's, without a member) stay for manage_jobs."""
    from . import jobs
    from .models import ConnectorAccount
    rows = jobs.visible_jobs(request.user)
    member = miembro(request)
    if member is None:
        return rows
    _, Member, _ = miembros._models()
    others = Member.objects.exclude(pk=member.pk)
    rows = rows.exclude(owner_id__in=others.values('user_id'))
    rows = rows.exclude(params__member__in=[str(pk) for pk in others.values_list('pk', flat=True)])
    foreign = ConnectorAccount.objects.exclude(pk__in=accounts(member).values('pk')).values_list('pk', flat=True)
    return rows.exclude(params__account__in=[str(pk) for pk in foreign])


def miembro(request):
    """The member whose data this request reads or writes: the authenticated user's own member (inactive:
    MiembroRequerido). A user without a member acts for the only active member (as before organizations) and gets
    MiembroRequerido among several; None without members. Kept on the request: one lookup per request."""
    holder = getattr(request, '_request', request)
    if not hasattr(holder, '_alcance_miembro'):
        holder._alcance_miembro = miembros.member_for(request.user)
    return holder._alcance_miembro


def obtener(request, model, **lookup):
    """One object of the request's member (a model or a queryset), or 404: another member's id looks like one that
    does not exist."""
    from django.core.exceptions import ValidationError
    from django.db.models import QuerySet
    rows = model if isinstance(model, QuerySet) else model.objects.all()
    try:
        found = de(rows.filter(**lookup), miembro(request)).first()
    except ValidationError:  # a malformed id is a missing object too
        found = None
    if found is None:
        raise NotFound()
    return found


def cuenta(request, account_id):
    """The account `account_id` if it is hers, else 404; None when no id was given."""
    if not account_id:
        return None
    from .models import ConnectorAccount
    return obtener(request, ConnectorAccount, pk=account_id)


def solo_administrador(request):
    """403 unless the user is the organization's active admin (with members) or, before members, holds manage_jobs."""
    if miembros.exist():
        if not miembros.is_admin(request.user):
            raise PermissionDenied('Solo el administrador de la organización.')
    elif not request.user.has_perm('team_backend.manage_jobs'):
        raise PermissionDenied('No tienes permiso para esta operación')
