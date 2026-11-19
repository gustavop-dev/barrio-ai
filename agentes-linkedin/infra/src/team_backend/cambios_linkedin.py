"""LinkedIn cambió la página: what Barrio does when a shape LinkedIn gives (a page, an answer) changes.

The incident of 19/11/2026: the post page began to write the `<` of the createComment template's `optimisticKey` as a
JavaScript `\\x3C`. rutas.templates could not parse it and every comment failed with «la página del post no trae la caja
de comentarios» (kind template_missing). The daily canary only read, so it said all was fine; the failures were only job
errors, and the canary's result only reached the app. Since then:

1. The canary also prepares what the writes depend on, without writing (linkedin_directo/canario.py).
2. Use: a connector call that fails with a kind only a changed answer or page gives (SHAPE_KINDS) is recorded once as
   `linkedin.shape_changed` (target: the account; the operation, the kind, our own message and the diagnostic: counts,
   offsets and field NAMES, never a value), by connectors_directo. The canary's broken rows are recorded the same way
   (source 'canario').
3. Episodes: per account and operation within the local day. One opens with the first `linkedin.shape_changed` and
   closes with `linkedin.shape_recovered`: the operation succeeded in use, or a canary checked it and it passed (the
   daily one or `manage.py operador prueba-linkedin`). The day's end closes every episode without a word.
4. The waiting rule (held): while an episode opened by USE is open, the approved actions of the capabilities that depend
   on that operation (DEPENDE) wait, still approved: operador.execute and the autopilot do not start them, and the action
   that failed goes back to approved too (the error comes before the write: nothing was sent). Why: a changed page fails
   every attempt the same way, and each attempt costs a read and a failed action Gustavo would have to approve again;
   one failure is enough evidence for the day. Why only use: the canary looks at one post (one with comments turned off
   has no comment box) and at one account's lists, so its verdict alone could stop a whole day for one odd page; it
   tells (Slack) and its passing clears. Why the day: if nobody runs the canary, the next day one action probes LinkedIn
   again: at most one wasted attempt per capability a day.
5. alertas_slack.linkedin_cambio tells Slack, once per operation a day (and «recuperado»); flujos.py turns the flows
   that use the operation red and keeps the day's canary line in «Salud de la máquina».

Read and written only from the backend; every function here swallows its own failures (a record or a notice never
breaks the work that saw the change)."""
import logging
from dataclasses import dataclass, field
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger('team_backend.cambios_linkedin')

CHANGED, RECOVERED = 'linkedin.shape_changed', 'linkedin.shape_recovered'
USE, CANARY = 'uso', 'canario'
# What only a changed answer or page gives: a template the page no longer carries or parses (template_missing), an
# answer whose shape the parser does not know (unreadable), the analytics workbook changed (analytics_parse), a GraphQL
# query LinkedIn no longer answers (graphql). Pushback, sessions, budgets and network errors are never shape changes.
SHAPE_KINDS = ('template_missing', 'unreadable', 'analytics_parse', 'graphql')
COMMAND = '`manage.py operador --usuario <tu usuario> prueba-linkedin`'

# operation -> (what cannot be done, in plain words after «no se puede», what stops while it lasts).
OPERACIONES = {
    'account_status': ('leer tu cuenta', 'no se lee ni se escribe nada en LinkedIn'),
    'get_user': ('leer un perfil', 'no se leen perfiles y seguir e invitar se detienen'),
    'get_profile': ('leer un perfil', 'no se leen perfiles y seguir e invitar se detienen'),
    'own_audience': ('leer tus seguidores y conexiones', 'no se mide tu audiencia'),
    'profile_views': ('leer las visitas a tu perfil', 'no se miden las visitas a tu perfil'),
    'list_user_posts': ('leer tus posts', 'no se miden tus posts ni se leen sus comentarios'),
    'get_post': ('leer un post', 'no salen reacciones y no se miden tus posts'),
    'list_comments': ('leer los comentarios de un post',
                      'no se leen los comentarios de tus posts y no salen comentarios en posts de otros'),
    'list_comment_thread': ('leer las respuestas de un comentario', 'no salen respuestas a los comentarios de tus posts'),
    'create_comment': ('comentar en un post', 'no salen comentarios en posts de otros'),
    'comment_in_thread': ('responder un comentario', 'no salen respuestas a los comentarios de tus posts'),
    'add_reaction': ('reaccionar a un post', 'no salen reacciones'),
    'react_to_comment': ('reaccionar a un comentario', 'no salen reacciones a comentarios'),
    'search_people': ('buscar personas', 'no se encuentran personas nuevas para tu red'),
    'search_parameters': ('elegir la ciudad en la búsqueda', 'la búsqueda de personas no filtra por ciudad'),
    'follow_user': ('seguir a una persona', 'no se puede seguir a nadie'),
    'send_invitation': ('invitar a conectar', 'no se pueden enviar invitaciones'),
    'list_invitations': ('leer las invitaciones recibidas', 'no se pueden aceptar invitaciones'),
    'list_sent_invitations': ('leer las invitaciones enviadas', 'no se sabe quién aceptó tus invitaciones'),
    'accept_invitation': ('aceptar una invitación', 'no se pueden aceptar invitaciones'),
    'list_chats': ('leer tu bandeja', 'no se leen tus mensajes privados'),
    'list_chat_messages': ('leer una conversación', 'no se leen tus mensajes privados'),
    'analytics': ('importar la analítica', 'no se importa la analítica de tus posts'),
}

# capability -> the operations its execution makes (operador.execute, respuestas.execute_action, red.execute_action):
# while one of them is held by use, its approved actions wait.
DEPENDE = {
    'INT-03': ('account_status', 'list_comments', 'create_comment'),
    'INT-04': ('account_status', 'list_comment_thread', 'comment_in_thread'),
    'INT-02': ('account_status', 'get_post', 'add_reaction', 'react_to_comment'),
    'RED-01': ('account_status', 'get_profile', 'follow_user'),
    'RED-02': ('account_status', 'get_profile', 'send_invitation'),
    'RED-04': ('account_status', 'list_invitations', 'get_profile', 'accept_invitation'),
}
ESPERAN = {'INT-03': ('comentario aprobado', 'comentarios aprobados'), 'INT-04': ('respuesta aprobada', 'respuestas aprobadas'),
           'INT-02': ('reacción aprobada', 'reacciones aprobadas'), 'RED-01': ('seguimiento aprobado', 'seguimientos aprobados'),
           'RED-02': ('invitación aprobada', 'invitaciones aprobadas'), 'RED-04': ('aceptación aprobada', 'aceptaciones aprobadas')}

# operation -> the flows of flujos.py that use it (they turn red while it is broken); any other goes to «salud».
FLUJOS = {
    'create_comment': ('comentarios',), 'list_comments': ('comentarios', 'respuestas'),
    'comment_in_thread': ('respuestas',), 'list_comment_thread': ('respuestas',), 'react_to_comment': ('respuestas',),
    'get_user': ('red',), 'get_profile': ('red',), 'search_people': ('red',), 'search_parameters': ('red',),
    'follow_user': ('red',), 'send_invitation': ('red',), 'list_invitations': ('red',), 'list_sent_invitations': ('red',),
    'accept_invitation': ('red',), 'list_chats': ('inbox',), 'list_chat_messages': ('inbox',),
    'list_user_posts': ('post_diario',), 'get_post': ('post_diario',), 'analytics': ('post_diario',),
}

# Operations the canary checks under other names: all of these rows passing clears them. Any other clears with its own.
COVERED = {'get_profile': ('get_user', 'own_audience')}


def plain(operation):
    return OPERACIONES.get(operation, (f'hacer {operation}', 'lo que depende de eso falla'))


def flows(operation):
    return FLUJOS.get(operation, ('salud',))


def capabilities(operation):
    return [capability for capability, operations in DEPENDE.items() if operation in operations]


def hint(detail):
    """The diagnostic in a few words (field names and counts only), or ''."""
    detail = detail if isinstance(detail, dict) else {}
    if 'apariciones' in detail:
        text = f'la página trae {detail["apariciones"]} plantillas y se leen {detail.get("leidas", 0)}'
        if detail.get('error'):
            text += f'; error JSON «{detail["error"]}» en la posición {detail.get("posicion")}'
            text += f' (campo «{detail["campo"]}»)' if detail.get('campo') else ''
        return text
    if detail.get('faltan'):
        return 'faltan ' + ', '.join(str(name) for name in detail['faltan'][:8])
    if detail.get('lectura'):
        return f'falla la lectura {detail["lectura"]} ({detail.get("error", "")})'
    return ''


# --------------------------------------------------------------------------- episodes

@dataclass
class Episodio:
    operacion: str
    eventos: list = field(default_factory=list)  # its linkedin.shape_changed events, in order
    recuperado: object = None  # the linkedin.shape_recovered that closed it; None while open

    @property
    def abierto(self):
        return self.recuperado is None

    @property
    def desde(self):
        return self.eventos[0].created_at

    @property
    def fuentes(self):
        return {e.metadata.get('fuente') for e in self.eventos}

    @property
    def ultimo(self):
        """The last shape_changed: the one whose diagnostic and kind are the freshest."""
        return self.eventos[-1]


def _day(now):
    from .operador import period_starts
    return period_starts(now)[0]


def episodes(account, now=None):
    """{operation: [Episodio, …]} of the account's local day up to `now`, oldest first."""
    from .models import AuditEvent
    now = now or timezone.now()
    out = {}
    rows = AuditEvent.objects.filter(action__in=(CHANGED, RECOVERED), target=str(account.id), created_at__gte=_day(now),
                                     created_at__lte=now).order_by('created_at', 'id')
    for event in rows:
        operation = str(event.metadata.get('operacion') or '')
        found = out.setdefault(operation, [])
        if event.action == CHANGED:
            if not found or not found[-1].abierto:
                found.append(Episodio(operation))
            found[-1].eventos.append(event)
        elif found and found[-1].abierto:
            found[-1].recuperado = event
    return out


def open_episodes(account, now=None):
    """{operation: Episodio} still open today."""
    return {op: found[-1] for op, found in episodes(account, now).items() if found and found[-1].abierto}


def problemas(accounts, now=None):
    """[(account, Episodio)] open today for these accounts (the flows report)."""
    return [(account, episode) for account in accounts if account.provider == 'directo'
            for episode in open_episodes(account, now).values()]


# --------------------------------------------------------------------------- records

def _tell(account, now):
    """Slack at once (alertas_slack.linkedin_cambio, the same alerts the watcher sends every few minutes)."""
    try:
        from . import alertas_slack
        for alert in alertas_slack.cambio_avisos(account, now):
            alertas_slack.send(alert.key, alert.text, now, alert.once, alert.channel)
    except Exception as exc:  # noqa: BLE001 - a notice never breaks the work that saw the change
        logger.warning('linkedin_change_notice_failed account=%s error=%s', account.pk, type(exc).__name__)


def record_changed(account, operation, kind, message, detail=None, source=USE, now=None):
    """One linkedin.shape_changed per source and episode: True when recorded now. Never raises."""
    now = now or timezone.now()
    try:
        from .models import AuditEvent
        with transaction.atomic():  # a savepoint: never spoils the caller's transaction
            episode = open_episodes(account, now).get(operation)
            if episode and source in episode.fuentes:
                return False
            AuditEvent.objects.create(action=CHANGED, target=str(account.id), created_at=now, metadata={
                'operacion': operation, 'kind': str(kind or '')[:40], 'motivo': str(message or '')[:200],
                'diagnostico': detail if isinstance(detail, dict) else {}, 'fuente': source})
    except Exception as exc:  # noqa: BLE001
        logger.warning('linkedin_change_not_recorded operation=%s error=%s', operation, type(exc).__name__)
        return False
    _tell(account, now)
    return True


def record_recovered(account, operation, source, now=None):
    """Close the operation's open episode: True when it was open. Never raises."""
    now = now or timezone.now()
    try:
        from .models import AuditEvent
        with transaction.atomic():
            if operation not in open_episodes(account, now):
                return False
            AuditEvent.objects.create(action=RECOVERED, target=str(account.id), created_at=now,
                                      metadata={'operacion': operation, 'fuente': source})
    except Exception as exc:  # noqa: BLE001
        logger.warning('linkedin_recovery_not_recorded operation=%s error=%s', operation, type(exc).__name__)
        return False
    _tell(account, now)
    return True


def after_canary(account, log, now=None):
    """A canary that judged LinkedIn (ok or roto): its broken rows open (or join) an episode, and an open episode
    whose operation it checked and found ok closes. A run that stopped early or did not run says nothing."""
    from linkedin_directo import canario as prueba
    from .models import CanaryRun
    if log is None or log.state not in (CanaryRun.State.OK, CanaryRun.State.BROKEN):
        return
    now = now or timezone.now()
    rows = {row.get('operacion'): row for row in log.operations or []}
    for name, row in rows.items():
        if row.get('estado') == prueba.BROKEN:
            record_changed(account, name, 'canario', row.get('motivo'), row.get('diagnostico'), CANARY, now)
    try:
        still = open_episodes(account, now)
    except Exception:  # noqa: BLE001
        return
    for operation in still:
        names = COVERED.get(operation, (operation,))
        if all((rows.get(name) or {}).get('estado') == prueba.OK for name in names):
            record_recovered(account, operation, CANARY, now)


class Seguimiento:
    """What one DirectoConnector (one account, usually one job) needs to record use: its account and the operations
    open today, looked up once and kept up to date as it records. Off (silently) without a database or an account
    (unit tests, the navegador service)."""

    def __init__(self, external_id):
        self.external_id, self.account, self.open, self.off = external_id, None, None, False

    def _ready(self):
        if self.open is None and not self.off:
            try:
                from .models import ConnectorAccount
                with transaction.atomic():
                    self.account = ConnectorAccount.objects.filter(provider='directo',
                                                                   external_account_id=self.external_id).first()
                    self.open = set(open_episodes(self.account)) if self.account else set()
            except Exception:  # noqa: BLE001 - no database here: nothing to record
                self.off, self.open = True, set()
        return not self.off and self.account is not None

    def failed(self, operation, kind, message, detail):
        if kind not in SHAPE_KINDS or not self._ready():
            return
        record_changed(self.account, operation, kind, message, detail)
        self.open.add(operation)

    def succeeded(self, operation, own=False):
        """`own`: the account's own /me answered in this connector (every call that needs it reads it first)."""
        if not self._ready() or not self.open:
            return
        for done in [operation] + (['account_status'] if own else []):
            if done in self.open:
                self.open.discard(done)
                record_recovered(self.account, done, USE)


# --------------------------------------------------------------------------- the waiting rule

def held_capabilities(account, now=None):
    """{capability: why it waits} for the account's capabilities held by an open episode of use (the module's rule 4)."""
    now = now or timezone.now()
    try:
        used = {op: e for op, e in open_episodes(account, now).items() if USE in e.fuentes}
    except Exception:  # noqa: BLE001 - unreadable state never stops a write by itself
        return {}
    from .alertas_slack import hhmm
    out = {}
    for capability, operations in DEPENDE.items():
        stuck = [op for op in operations if op in used]
        if stuck:
            op = stuck[0]
            out[capability] = (f'LinkedIn cambió la página: no se puede {plain(op)[0]} ({op}) desde las '
                               f'{hhmm(used[op].desde)}. No se envió nada; queda aprobada hasta que la prueba de LinkedIn '
                               'vuelva a pasar o hasta mañana.')
    return out


def held(account, capability, now=None):
    """'' or why an action of `capability` waits (operador.execute)."""
    if getattr(account, 'provider', '') != 'directo':
        return ''
    return held_capabilities(account, now).get(capability, '')


def waiting(account, operation):
    """[(capability, approved actions that have not started)] of the capabilities that depend on the operation."""
    from .models import ActionProposal
    caps = capabilities(operation)
    counts = dict.fromkeys(caps, 0)
    for capability in ActionProposal.objects.filter(account=account, state=ActionProposal.State.APPROVED,
                                                    execution__isnull=True, piece__isnull=True,
                                                    capability__in=caps).values_list('capability', flat=True):
        counts[capability] += 1
    return [(capability, n) for capability, n in counts.items() if n]


def waiting_text(rows):
    """«3 comentarios aprobados y 1 respuesta aprobada»."""
    parts = [f'{n} {ESPERAN[cap][0] if n == 1 else ESPERAN[cap][1]}' for cap, n in rows]
    return parts[0] if len(parts) == 1 else ', '.join(parts[:-1]) + ' y ' + parts[-1]
