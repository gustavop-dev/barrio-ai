"""Estado de cada flujo: one Slack report that reads in a minute (Gustavo, 19/11/2026: «¿cuántos flujos tenemos?
Organícelos para que los podamos auditar uno a uno… repórtame a Slack el estado de cada flujo y sus etapas»).

Why: in the two days before, several flows degraded for days and nobody noticed: the daily post was not prepared for
two days (a job id collision), follows and invitations failed 151 times because research spent the shared profile reads,
web research runs stayed «running» forever, buyers left by a classification rule and 4 of 14 posts went out with the
generic fallback image. Each alert of alertas_slack watches one symptom; this report walks every flow stage by stage, so
a silent one shows the same day.

FLUJOS is the registry and the audit map: the user-facing flows, each with its ordered stages, its switches and how
each number is measured. docs/funcionalidades/estado-de-flujos.md explains it to Gustavo, one section per flow; a test
keeps both in step. The 17 cycles of equipos/grafo.yaml map onto these flows (the document has the table).

Read only. The report reads the database (jobs, proposals, executions, pieces, captures, contacts, research runs, audit
events) and the AI ledger; it never reads LinkedIn, never calls a provider and writes nothing (alertas_slack.send writes
its own audit row when it goes out).

Per stage and per local day (today and yesterday): what entered, what advanced, what was discarded on purpose, what
failed and its most frequent reason in plain words (motivo), and what waits now and since when. Status rules (juzgar):
- ⚪ apagado: the flow's switch is off; the switch is named.
- 🔴 detenido: what should have happened has not (each flow's expected checks: the post of today or tomorrow not
  prepared inside its lead window, comments not read, the queue stopped…), or a stage failed every attempt of the last
  24 hours with at least ESTADO_FLUJOS_FALLOS_MIN failures, or something waits in a machine queue for more than
  ESTADO_FLUJOS_DETENIDO_HORAS.
- 🟡 con atención: a stage failed at least ESTADO_FLUJOS_FALLOS_MIN times in the last 24 hours and more than
  ESTADO_FLUJOS_FALLOS_PCT of its attempts; a machine queue waits more than its stage's limit; an output used a fallback
  (the generic image); or a finding of the flow (buyers discarded with a level that keeps them, research left running,
  the actions out of profile reads, the lead discarding almost everything…).
- 🟢 funcionando: none of the above.
What waits for Gustavo (his approval, a message he sends) is shown but never turns a flow yellow: the machine is fine.
"""
import logging
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Callable, Optional

from django.db.models import Q
from django.utils import timezone

logger = logging.getLogger('team_backend.flujos')

VERDE, AMARILLO, ROJO, APAGADO = 'verde', 'amarillo', 'rojo', 'apagado'
EMOJI = {VERDE: '🟢', AMARILLO: '🟡', ROJO: '🔴', APAGADO: '⚪'}
PALABRA = {VERDE: 'funcionando', AMARILLO: 'con atención', ROJO: 'detenido', APAGADO: 'apagado'}
GRAVEDAD = {VERDE: 0, AMARILLO: 1, ROJO: 2}
DIAS = ['lun', 'mar', 'mié', 'jue', 'vie', 'sáb', 'dom']
PREPARACION = timedelta(hours=2)  # what a daily post may take once its lead window opened before it counts as not prepared
GENERICAS_MAX = 2  # pieces of the last seven days (and tomorrow's) with a fallback image that keep the daily post yellow
INVESTIGACION_A_MEDIAS = timedelta(minutes=30)  # a web research run still «running» after this was left half way
CAPTURA_A_MEDIAS = timedelta(hours=1)  # a capture still being transcribed or processed after this is stuck
ESPERA_RED = timedelta(hours=24)  # approved network actions wait for their rounds and caps: a day is still normal
FAILED_JOBS = ('failed', 'interrupted')
ACTIVE_JOBS = ('queued', 'running')


# --------------------------------------------------------------------------- settings

def _setting(name, default):
    return os.environ.get(name, default)


def _number(name, default, low, high):
    from .alertas_slack import _number as number
    return number(name, default, low, high)


def fallos_pct():
    """ESTADO_FLUJOS_FALLOS_PCT (0.2): the share of a stage's attempts in 24 hours that may fail before it is yellow."""
    return _number('ESTADO_FLUJOS_FALLOS_PCT', 0.2, 0.01, 1.0)


def fallos_min():
    """ESTADO_FLUJOS_FALLOS_MIN (3): failures in 24 hours below this never change a flow's status."""
    return int(_number('ESTADO_FLUJOS_FALLOS_MIN', 3, 1, 1000))


def espera_horas():
    """ESTADO_FLUJOS_ESPERA_HORAS (6): how long work may wait in a machine queue before the flow is yellow."""
    return timedelta(hours=_number('ESTADO_FLUJOS_ESPERA_HORAS', 6, 0.5, 72))


def detenido_horas():
    """ESTADO_FLUJOS_DETENIDO_HORAS (24): how long work may wait in a machine queue before the flow is stopped (red)."""
    return timedelta(hours=_number('ESTADO_FLUJOS_DETENIDO_HORAS', 24, 2, 24 * 14))


def _on(name, default='true'):
    return _setting(name, default).strip().lower() == 'true'


# --------------------------------------------------------------------------- plain reasons

# (pattern of the internal error, the reason in plain words, what to do or ''). The first match wins; the order goes
# from the most specific to the most general. The cycle stops (orquestacion: cost_cap, call_timeout…) come bare from a
# blocked job or after «Ciclo detenido: » in a piece's note.
MOTIVOS = [
    (r'Tope compartido de lecturas de perfil', 'sin lecturas de perfil: el cupo del día se gastó',
     'Sube OPERATOR_PROFILE_READ_DAILY_LIMIT (hasta 100) o baja OPERATOR_PROFILE_READ_RESEARCH_SHARE.'),
    (r'Parte de las acciones del cupo de lecturas', 'sin lecturas de perfil: la investigación dejó sin cupo a las acciones',
     'Baja OPERATOR_PROFILE_READ_RESEARCH_SHARE o sube OPERATOR_PROFILE_READ_DAILY_LIMIT (hasta 100).'),
    (r'Parte de la investigación del cupo de lecturas', 'sin lecturas de perfil para investigar', ''),
    (r'Sin perfiles legibles hoy', 'sin lecturas de perfil: el cupo del día se gastó',
     'Sube OPERATOR_PROFILE_READ_DAILY_LIMIT (hasta 100) o baja OPERATOR_PROFILE_READ_RESEARCH_SHARE.'),
    (r'cost_cap|presupuesto del ciclo', 'se acabó el presupuesto de su ciclo', ''),
    (r'call_timeout', 'una llamada a la IA tardó más que su límite', ''),
    (r'cycle_timeout', 'el ciclo superó su tiempo máximo', ''),
    (r'\bstall\b', 'el ciclo dejó de avanzar', 'Míralo en Equipo (ciclos detenidos).'),
    (r'^uncertain$|Ciclo detenido: uncertain', 'una llamada quedó sin resultado confirmado', 'Concíliala en Equipo antes de repetirla.'),
    (r'max_calls|edge_limit|provider_calls', 'el ciclo llegó a su máximo de llamadas', ''),
    (r'Presupuesto de IA agotado|Presupuesto editorial diario agotado|AI_MONTHLY_LIMIT_USD|AI_DAILY_FUSE_USD|Tope mensual',
     'sin presupuesto de IA', 'Sube AI_MONTHLY_LIMIT_USD o AI_DAILY_FUSE_USD, o espera a que se renueve.'),
    (r'Presupuesto de investigación', 'sin presupuesto para investigar', ''),
    (r'Cuenta en pausa|account_not_running|Otro conector de la misma cuenta', 'la cuenta de LinkedIn está en pausa',
     'Reanúdala desde la app cuando esté resuelto.'),
    (r'Operación global pausada|OPERATOR_PAUSED', 'la máquina está detenida', ''),
    (r'Fuera de la ventana horaria|Fuera del horario de lecturas', 'fuera del horario de actividad', ''),
    (r'Tope diario o semanal', 'se llenó el cupo de escrituras', ''),
    (r'Espaciado mínimo', 'esperaba el espacio entre escrituras', ''),
    (r'salen en dos tandas|Durante una tanda de red', 'esperaba su tanda de red', ''),
    (r'no salió; queda aprobada hasta', 'la escritura anterior no salió; espera', ''),
    (r'voz provisional', 'escrita con voz provisional: espera la aprobación de su dueña', ''),
    (r'perdió su latido', 'el worker se reinició a mitad del trabajo', 'Revisa el contenedor del worker.'),
    (r'No se completó el trabajo|Error interno', 'error interno (ver el registro del worker)', 'Revisa los logs del worker.'),
    (r'Límite diario de investigaciones', 'se llenó el cupo diario de investigaciones', ''),
    (r'Investigación en curso o interrumpida', 'quedó a medias', ''),
    (r'no devuelve hallazgos|no devolvió hallazgos', 'la web no devolvió hallazgos con citas', ''),
    (r'Investigación web desactivada|Búsqueda web desactivada|Lectura web desactivada', 'la investigación web está apagada', ''),
    (r'proveedor o fuente no disponible', 'el proveedor o la fuente no respondió', ''),
    (r'filtrado dinámico|WEB_SEARCH_TOOL_TYPE', 'la herramienta web no devuelve citas', 'Revisa WEB_SEARCH_TOOL_TYPE.'),
    (r'rate_limit|throttle|\b429\b', 'LinkedIn pidió frenar', ''),
    (r'Sin veredicto|verificador|content_gate|bloque', 'la verificación del texto no pasó', ''),
    (r'Infografía rechazada', 'la revisión visual rechazó la infografía', ''),
    (r'Sin proveedor visual', 'no hay proveedor de imágenes configurado', 'Revisa ANTHROPIC_API_KEY en el servidor.'),
    (r'fotos elegidas', 'las fotos elegidas ya no estaban disponibles', ''),
    (r'Referencia inexistente|ya no existe', 'apuntaba a algo que ya no existe', ''),
    (r'Preparación interrumpida', 'la preparación se cortó a mitad', ''),
    (r'no se encontró|not_found|\b404\b', 'LinkedIn no encontró la publicación o el perfil', ''),
]
_IDS = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|(?:https?://|www\.)\S+?(?=[.,;:)]*(?:\s|$))|'
                  r'[\w.+-]+@[\w-]+\.[\w.]+|'
                  r'\b[0-9a-f]{16,}\b|\d[\d ()+.-]{6,}\d', re.I)


def motivo(error):
    """The internal error of a job, a piece or a research run in plain words: one of MOTIVOS, or its first clause without
    ids, links or numbers (never the whole text: it may quote a provider)."""
    text = ' '.join(str(error or '').split())
    if not text:
        return 'sin detalle'
    for pattern, plain, _ in MOTIVOS:
        if re.search(pattern, text, re.I):
            return plain
    first = re.split(r'(?<=[.;:])\s', _IDS.sub('…', text))[0].rstrip('.;:')
    first = first[:90] + ('…' if len(first) > 90 else '')
    return first[:1].lower() + first[1:]


def que_hacer(plain):
    """The action of a plain reason (MOTIVOS), or ''."""
    return next((action for _, reason, action in MOTIVOS if reason == plain and action), '')


# A job that ended «complete» but stopped with one of these did what the rules ask (wait for the hours, the caps or the
# rounds): never a failure. Any other stop (a cycle stop, no profile reads, the provider…) counts as one.
BENIGNOS = {'fuera del horario de actividad', 'se llenó el cupo de escrituras', 'esperaba el espacio entre escrituras',
            'esperaba su tanda de red', 'la escritura anterior no salió; espera'}


# --------------------------------------------------------------------------- what a stage measures

@dataclass
class Conteo:
    """One stage over one window: what entered, advanced, was discarded on purpose and failed (with its reasons)."""
    entraron: int = 0
    avanzaron: int = 0
    descartados: int = 0
    fallaron: int = 0
    motivos: Counter = field(default_factory=Counter)

    def motivo(self):
        return self.motivos.most_common(1)[0][0] if self.motivos else ''


@dataclass
class Etapa:
    nombre: str
    hoy: Conteo
    ayer: Conteo
    dia: Conteo  # the last 24 hours: what the status rules judge
    esperando: int = 0
    desde: object = None  # the oldest waiting item's moment
    espera: Optional[timedelta] = None  # a machine queue's limit (None: no limit, or it waits for Gustavo)
    entra: str = ''  # «de N {entra}» in the line, e.g. «propuestos»
    descarta: str = 'descartados'
    cola: str = 'en cola'
    apagada: str = ''  # the switch that turns this stage off, when it is off


@dataclass
class Hallazgo:
    nivel: str  # AMARILLO | ROJO
    texto: str
    accion: str = ''


@dataclass
class Resultado:
    flujo: 'Flujo'
    estado: str = VERDE
    etapas: list = field(default_factory=list)
    hallazgos: list = field(default_factory=list)
    clave: str = ''  # the day's key number, for the collapsed green line
    apagado: str = ''  # the switch that turns the flow off
    anoche: list = field(default_factory=list)  # morning: what was prepared overnight
    para_hoy: list = field(default_factory=list)  # morning: what is pending today (Gustavo's and the machine's)
    notas: list = field(default_factory=list)  # extra lines of an expanded flow (the machine's spend and writes)


@dataclass(frozen=True)
class Flujo:
    id: str
    nombre: str
    que_hace: str
    etapas: tuple  # (name, how it is measured) in order, for the document
    interruptores: tuple  # the variables that switch it (or its stages) off
    medir: Callable
    maquina: bool = False  # the installation's, not a member's: only in the first active member's report


class Ctx:
    """The moment and the member a report is for, its three windows and a small cache."""

    def __init__(self, now, member=None, first=True, several=False):
        from .operador import period_starts
        self.now, self.member, self.first, self.several = now, member, first, several
        day, _ = period_starts(now)
        self.hoy = (day, now)
        self.ayer = (day - timedelta(days=1), day)
        self.dia = (now - timedelta(days=1), now)
        self.today = day
        self.cache = {}

    def windows(self):
        return self.hoy, self.ayer, self.dia


def _in(field_name, window):
    start, end = window
    return {f'{field_name}__gte': start, f'{field_name}__lt': end}


def etapa(ctx, nombre, contar, pendiente=None, **opciones):
    """A stage from `contar(window) -> Conteo` and `pendiente() -> (count, oldest)` (what waits now and since when)."""
    hoy, ayer, dia = (contar(w) for w in ctx.windows())
    waiting, since = pendiente() if pendiente else (0, None)
    return Etapa(nombre, hoy, ayer, dia, waiting, since, **opciones)


def apagada(nombre, switch):
    return Etapa(nombre, Conteo(), Conteo(), Conteo(), apagada=switch)


# --------------------------------------------------------------------------- shared measures

def _accounts(ctx):
    from . import miembros
    from .models import ConnectorAccount
    return miembros.accounts(ctx.member) if ctx.member is not None else ConnectorAccount.objects.all()


def _mine(rows, ctx, field_name='account'):
    from . import miembros
    return miembros.mine(rows, ctx.member, field_name)


def _own(rows, ctx, field_name='member'):
    from . import miembros
    return miembros.own(rows, ctx.member, field_name)


def _jobs(ctx, kinds):
    """Jobs of these kinds that are the member's: with several members, her content jobs (job_params) and the jobs of her
    accounts; with one (or none), every job."""
    from . import miembros
    from .models import Job
    rows = Job.objects.filter(kind__in=list(kinds))
    if not ctx.several or ctx.member is None:
        return rows
    accounts = [str(pk) for pk in _accounts(ctx).values_list('pk', flat=True)]
    content, exclude = miembros.job_filter(ctx.member)
    hers = ~Q(**content) if exclude else Q(**content)
    return rows.filter(Q(params__account__in=accounts) | (~Q(params__has_key='account') & hers))


def _ended(rows, window):
    """(done, [plain reasons of the failures]) of the jobs that ended in the window. A job that completed with a stop
    (network, inbox and metrics jobs keep their stop in `error`) failed unless the stop is BENIGNOS."""
    done, reasons = 0, []
    for state, error in rows.filter(state__in=('complete',) + FAILED_JOBS, **_in('finished_at', window)).values_list('state', 'error'):
        reason = motivo(error) if (state != 'complete' or error) else ''
        if state == 'complete' and (not error or reason in BENIGNOS):
            done += 1
        else:
            reasons.append(reason)
    return done, reasons


def contar_trabajos(ctx, kinds):
    """entraron: jobs queued in the window; avanzaron: done; fallaron: failed, interrupted or stopped, with their reasons."""
    def contar(window):
        rows = _jobs(ctx, kinds)
        done, reasons = _ended(rows, window)
        return Conteo(rows.filter(**_in('created_at', window)).count(), done, 0, len(reasons), Counter(reasons))
    return contar


def cola_trabajos(ctx, kinds):
    def cola():
        rows = _jobs(ctx, kinds).filter(state__in=ACTIVE_JOBS)
        return rows.count(), rows.order_by('created_at').values_list('created_at', flat=True).first()
    return cola


def _execution_failures(ctx, window):
    """{capability: Counter(reason)} of the execute_action jobs that failed in the window (a gate that stopped it, or a
    write LinkedIn refused), the member's only."""
    key = ('fallos', window)
    if key not in ctx.cache:
        from .models import ActionProposal, Job
        rows = list(Job.objects.filter(kind='execute_action', state__in=FAILED_JOBS, **_in('finished_at', window))
                    .values_list('params__proposal', 'error'))
        mine = _mine(ActionProposal.objects.filter(pk__in=[p for p, _ in rows if p]), ctx)
        capability = dict((str(pk), cap) for pk, cap in mine.values_list('pk', 'capability'))
        found = {}
        for proposal, error in rows:
            reason = motivo(error)
            if str(proposal) in capability and reason not in BENIGNOS:
                found.setdefault(capability[str(proposal)], Counter())[reason] += 1
        ctx.cache[key] = found
    return ctx.cache[key]


def contar_escrituras(ctx, capability):
    """entraron: proposals of the capability created in the window; avanzaron: written on LinkedIn (sent, confirmed or
    uncertain); descartados: discarded or vetoed; fallaron: execute_action jobs that failed."""
    from .models import ActionExecution, ActionProposal

    def contar(window):
        proposals = _mine(ActionProposal.objects.filter(capability=capability), ctx)
        written = _mine(ActionExecution.objects.filter(proposal__capability=capability, wrote=True), ctx, 'proposal__account')
        reasons = _execution_failures(ctx, window).get(capability, Counter())
        return Conteo(proposals.filter(**_in('created_at', window)).count(),
                      written.exclude(state='failed').filter(**_in('started_at', window)).count(),
                      proposals.filter(state__in=['discarded', 'rejected'], **_in('decided_at', window)).count(),
                      sum(reasons.values()), reasons)
    return contar


def cola_escrituras(ctx, capability, states=('approved',)):
    from .models import ActionProposal

    def cola():
        rows = _mine(ActionProposal.objects.filter(capability=capability, state__in=list(states), execution__isnull=True), ctx)
        return rows.count(), rows.order_by('created_at').values_list('created_at', flat=True).first()
    return cola


def contar_revision(ctx, capability):
    """The rules and the lead (Jev): entraron: proposals created; avanzaron: approved in the window; descartados: discarded
    or vetoed in the window."""
    from .models import ActionProposal

    def contar(window):
        rows = _mine(ActionProposal.objects.filter(capability=capability), ctx)
        decided = rows.filter(**_in('decided_at', window))
        return Conteo(rows.filter(**_in('created_at', window)).count(),
                      decided.exclude(state__in=['discarded', 'rejected', 'proposed']).count(),
                      decided.filter(state__in=['discarded', 'rejected']).count())
    return contar


def _autonomy(capability, ctx):
    from .autopiloto import autonomy
    return autonomy(capability, ctx.member)


def _approval_queue(capability, ctx):
    """'esperan tu aprobación' when the capability waits for Gustavo, else the machine's queue label."""
    return 'esperan tu aprobación' if _autonomy(capability, ctx) == 'approval' else 'en cola'


def _lead_discards(etapa_, ctx):
    """The lead (Jev) discarding almost everything it reviewed in 24 hours (alertas_slack.lead_discard_ratio)."""
    from .alertas_slack import lead_discard_ratio
    ratio, minimum = lead_discard_ratio()
    d = etapa_.dia
    reviewed = d.avanzaron + d.descartados
    if reviewed >= minimum and d.descartados > ratio * reviewed:
        return [Hallazgo(AMARILLO, f'{etapa_.nombre}: el líder descartó {d.descartados} de {reviewed} en 24 h. Casi nada sale.',
                         'Mira los motivos en el calendario («Mostrar lo que no salió»).')]
    return []


def _at(moment, now):
    from .alertas_slack import at_text
    return at_text(moment, now)


def _since(moment, now):
    from .alertas_slack import since_text
    return since_text(moment, now)


def _hhmm(moment):
    from .alertas_slack import hhmm
    return hhmm(moment)


def _plural(n, one, many):
    return f'{n} {one if n == 1 else many}'


def _of(done, one, many, total, total_one, total_many):
    """«hoy 2 comentarios publicados de 5 propuestos»."""
    return f'hoy {_plural(done, one, many)} de {total} {total_one if total == 1 else total_many}'


# --------------------------------------------------------------------------- 1. the daily post

PIECE_STAGE = {'preparing': 'sigue preparándose', 'ready': 'está lista sin publicación propuesta',
               'blocked': 'la verificación la bloqueó', 'failed': 'su preparación falló', 'skipped': 'el director la saltó',
               'awaiting_approval': 'espera tu aprobación', 'scheduled': 'está aprobada pero no salió',
               'publishing': 'se está publicando', 'uncertain': 'no se sabe si salió', 'failed_action': 'la publicación falló',
               'vetoed': 'la vetaste', 'discarded': 'el líder la descartó', 'expired': 'caducó sin publicarse',
               'superseded': 'se está rehaciendo con tu comentario', 'published': 'publicada'}


def _piece_status(piece):
    from . import editorial
    action = editorial.latest_action(piece)
    status = editorial.status(piece, action)
    if status == 'failed' and action is not None:
        status = 'failed_action'
    return status, action


RESPALDOS = {'contenido': 'la tarjeta con la frase del post', 'foto': 'una foto de la galería', 'marca': 'la tarjeta genérica'}


def fallback_level(piece):
    """Which fallback carries the piece's image when its own could not be made, or None for its own image. Since #144
    (imagenes.fallback) the post's key line goes first, then the editor's photo, and only then the fixed brand card."""
    from .imagenes import FALLBACKS
    review = piece.image_review if isinstance(piece.image_review, dict) else {}
    level = {mode: name for name, mode in FALLBACKS.items()}.get(review.get('mode'))
    return level or ('marca' if piece.image_kind == 'tarjeta' else None)


def fallback_reason(piece):
    """Why the piece's own image did not go out, in plain words: the fallback's own reason (image_reason carries it
    behind a «Respaldo con…» prefix)."""
    review = piece.image_review if isinstance(piece.image_review, dict) else {}
    fallback = review.get('fallback') if isinstance(review.get('fallback'), dict) else {}
    return motivo(fallback.get('reason') or piece.image_reason)


def _post_switch(ctx):
    from . import editorial, operador
    if operador.globally_paused():
        return 'la máquina está detenida (OPERATOR_PAUSED o el interruptor de la oficina)'
    if _autonomy('CONT-09', ctx) == 'off':
        return 'OPERATOR_AUTONOMY CONT-09=off'
    if not editorial.can_publish(editorial.publishing_account(ctx.member)):
        return 'sin cuenta que publique (LIVE_LINKEDIN_OFFICIAL o la cuenta oficial en pausa)'
    return ''


def _why_not_prepared(ctx, day):
    from . import editorial
    from .models import Job
    from knowledge import presupuesto
    jobs = _jobs(ctx, ['prepare_piece']).filter(params__slot=day.isoformat()).exclude(params__contains={'extra': True})
    failed = jobs.filter(state__in=FAILED_JOBS).order_by('-finished_at').first()
    if failed is not None:
        return f'su preparación falló ({motivo(failed.error)})'
    left = presupuesto.left(ctx.now)
    if left < editorial.prepare_min():
        return f'falta presupuesto de IA (quedan {left:.2f} USD y la preparación reserva {editorial.prepare_min()})'
    if Job.objects.filter(kind='prepare_piece', state__in=ACTIVE_JOBS).exists():
        return 'otra preparación ocupa la cola desde hace rato'
    if jobs.filter(state='complete').exists():
        return 'el trabajo de ese día ya había corrido y el autopiloto no lo volvió a encargar'
    return 'el autopiloto no encargó su preparación'


def _week_full(ctx, when):
    """The member's CONT-09 week is full (OPERATOR_WEEKLY_LIMITS): a day without a post on purpose."""
    from . import editorial, operador
    try:
        return operador.capacity_left(editorial.publishing_account(ctx.member), 'CONT-09', when) <= 0
    except Exception:  # noqa: BLE001 - unknown: the day is expected
        return False


def _post_expected(ctx):
    """Today's post out at its hour (ALERT_POST_LATE_MINUTES after it), and today's and tomorrow's prepared once their
    lead window (EDITORIAL_LEAD_HOURS) opened PREPARACION ago. A day the director skipped on purpose, or a week whose
    posts are all out (OPERATOR_WEEKLY_LIMITS CONT-09), asks nothing."""
    from . import editorial
    from .alertas_slack import post_late_minutes
    from .models import EditorialPiece
    findings, morning, today = [], [], ctx.today.date()
    for offset, label in ((0, 'de hoy'), (1, 'de mañana')):
        day = today + timedelta(days=offset)
        try:
            when = editorial.scheduled_for(day, ctx.member)
        except ValueError as exc:
            return [Hallazgo(ROJO, f'La hora del post está mal configurada: {exc}', 'Corrige EDITORIAL_POST_TIME.')], []
        pieces = _own(EditorialPiece.objects.filter(slot_date=day, second_of_day=False), ctx).order_by('-created_at')
        piece = pieces.first()
        status = _piece_status(piece)[0] if piece is not None else None
        if offset == 0 and piece is not None:
            morning.append(f'Post de hoy: {PIECE_STAGE.get(status, status)}' + (f', sale a las {_hhmm(when)}' if
                                                                               status in ('scheduled', 'awaiting_approval') else ''))
        if status == 'skipped' or (piece is None and _week_full(ctx, when)):
            continue
        if offset == 0 and ctx.now >= when + post_late_minutes():
            if status != 'published':
                stage = PIECE_STAGE.get(status, status) if piece is not None else 'no hay pieza preparada'
                findings.append(Hallazgo(ROJO, f'El post de hoy no salió a su hora ({_hhmm(when)}): {stage}.',
                                         'Míralo en el calendario.'))
            continue
        opens = when - editorial.lead_time()
        if piece is None and ctx.now >= opens + PREPARACION and ctx.now < when + post_late_minutes():
            active = _jobs(ctx, ['prepare_piece']).filter(state__in=ACTIVE_JOBS, params__slot=day.isoformat()).exists()
            if not active:
                findings.append(Hallazgo(ROJO, f'El post {label} no está preparado: su preparación debía empezar '
                                               f'{_at(opens, ctx.now)} y {_why_not_prepared(ctx, day)}.',
                                         'Prepáralo a mano desde el calendario («Planificar») y revisa el autopiloto.'))
                if offset == 0:
                    morning.append('Post de hoy: no está preparado')
    return findings, morning


def medir_post(ctx):
    from .models import ActionExecution, EditorialPiece, PostMetric
    res = Resultado(FLUJOS_POR_ID['post_diario'], apagado=_post_switch(ctx))
    if res.apagado:
        return res
    pieces = _own(EditorialPiece.objects.all(), ctx)

    def preparacion(window):
        rows = list(pieces.filter(**_in('created_at', window)).values_list('state', 'note'))
        bad = [motivo(note) for state, note in rows if state in ('failed', 'blocked')]
        return Conteo(len(rows), sum(1 for s, _ in rows if s == 'ready'), sum(1 for s, _ in rows if s == 'skipped'),
                      len(bad), Counter(bad))

    def preparando():
        rows = pieces.filter(state='preparing')
        return rows.count(), rows.order_by('created_at').values_list('created_at', flat=True).first()

    def imagen(window):
        ready = list(pieces.filter(state='ready', **_in('created_at', window)))
        generic = [p for p in ready if fallback_level(p)]
        return Conteo(len(ready), len(ready) - len(generic), 0, len(generic), Counter(fallback_reason(p) for p in generic))

    def metricas(window):
        captured = _own(PostMetric.objects.all(), ctx, 'piece__member').filter(**_in('captured_at', window)).count()
        jobs = contar_trabajos(ctx, ['collect_metrics'])(window)
        return Conteo(captured, captured, 0, jobs.fallaron, jobs.motivos)

    def cortes_pendientes():
        from . import metricas as module
        due = [(execution.started_at + module.AGES[kind]) for execution, kinds in module.publications(ctx.now, ctx.member)
               for kind in kinds]
        return len(due), min(due) if due else None

    res.etapas = [
        etapa(ctx, 'Plan del día', contar_trabajos(ctx, ['prepare_piece']), cola_trabajos(ctx, ['prepare_piece']),
              espera=timedelta(hours=3), entra='encargados'),
        etapa(ctx, 'Preparación', preparacion, preparando, espera=timedelta(hours=3), entra='empezadas',
              descarta='saltadas por el director', cola='preparándose'),
        etapa(ctx, 'Imagen propia', imagen, entra='piezas listas'),
        etapa(ctx, 'Programado', contar_revision(ctx, 'CONT-09'), cola_escrituras(ctx, 'CONT-09', ('proposed',)),
              entra='propuestos', descarta='descartados o vetados', cola=_approval_queue('CONT-09', ctx)),
        etapa(ctx, 'Publicado', contar_escrituras(ctx, 'CONT-09'), entra='propuestos', descarta='descartados o vetados'),
        etapa(ctx, 'Métricas', metricas, cortes_pendientes, espera=timedelta(hours=12), cola='cortes pendientes'),
    ]
    # The image: a fallback (the post's key line, a gallery photo or the generic brand card) is never a failure of the
    # post: yellow with which one and why, when one was made in the last 24 hours or GENERICAS_MAX of the week's pieces
    # carry one (17–18/11/2026: 4 of 14 with the brand card).
    image = res.etapas[2]
    week = list(pieces.filter(state='ready', slot_date__gt=ctx.today.date() - timedelta(days=7),
                              slot_date__lte=ctx.today.date() + timedelta(days=1)))
    generic = [p for p in week if fallback_level(p)]
    if image.dia.fallaron or len(generic) >= GENERICAS_MAX:
        recent = [p for p in pieces.filter(state='ready', **_in('created_at', ctx.dia)) if fallback_level(p)]
        kinds = ' y '.join(dict.fromkeys(RESPALDOS[fallback_level(p)] for p in recent or generic))
        reason = image.dia.motivo() or Counter(fallback_reason(p) for p in generic).most_common(1)[0][0]
        lead = (f'{_plural(image.dia.fallaron, "pieza lista lleva", "piezas listas llevan")} un respaldo en vez de su imagen '
                'propia' if image.dia.fallaron else 'Varias piezas llevan un respaldo en vez de su imagen propia')
        res.hallazgos.append(Hallazgo(AMARILLO, f'{lead} ({kinds}: {reason}); {len(generic)} de {len(week)} esta semana.',
                                      'Revisa por qué falló la imagen propia en el detalle de la pieza.'))
    image.dia = Conteo(image.dia.entraron, image.dia.avanzaron)  # judged above: not again as a failure rate
    found, morning = _post_expected(ctx)
    res.hallazgos += found
    res.anoche += morning
    published = _mine(ActionExecution.objects.filter(proposal__capability='CONT-09', wrote=True).exclude(state='failed'), ctx,
                      'proposal__account').filter(**_in('started_at', ctx.hoy)).order_by('started_at').first()
    tomorrow = pieces.filter(slot_date=ctx.today.date() + timedelta(days=1), second_of_day=False, state='ready').exists()
    res.clave = ((f'publicado hoy a las {_hhmm(published.started_at)}' if published else 'hoy no se ha publicado') +
                 ('; el de mañana, listo' if tomorrow else ''))
    return res


# --------------------------------------------------------------------------- 2. the weekly plan and the summaries

def medir_plan(ctx):
    from . import estrategia, operador, resumen_semanal, revision_mensual
    from .models import MonthlyReview, WeeklyPlan, WeeklySummary
    res = Resultado(FLUJOS_POR_ID['plan_resumenes'])
    switches = {'plan': estrategia.enabled(), 'resumen': resumen_semanal.enabled(), 'revision': revision_mensual.enabled()}
    if not any(switches.values()):
        res.apagado = 'STRATEGY_ENABLED, WEEKLY_SUMMARY_ENABLED y MONTHLY_REVIEW_ENABLED en false'
        return res
    local = ctx.now.astimezone(operador.local_tz())
    monday = local.date() - timedelta(days=local.weekday())

    def made(model, field_name):
        def contar(window):
            return Conteo(0, _own(model.objects.all(), ctx).filter(**_in(field_name, window)).count())
        return contar

    def with_jobs(model, field_name, kind):
        def contar(window):
            jobs = contar_trabajos(ctx, [kind])(window)
            done = made(model, field_name)(window)
            return Conteo(jobs.entraron, done.avanzaron, 0, jobs.fallaron, jobs.motivos)
        return contar

    stages = []
    if switches['plan']:
        stages.append(etapa(ctx, 'Plan de la semana', with_jobs(WeeklyPlan, 'created_at', 'plan_week'), cola_trabajos(ctx, ['plan_week']),
                            espera=timedelta(hours=3), entra='encargados'))
        plan_at = datetime.combine(monday + timedelta(days=6), estrategia.plan_time(), tzinfo=operador.local_tz())
        next_week = _own(WeeklyPlan.objects.filter(week_start=monday + timedelta(days=7), state=WeeklyPlan.State.PLANNED), ctx)
        if ctx.now >= plan_at + PREPARACION and not next_week.exists() and not _post_switch(ctx):
            res.hallazgos.append(Hallazgo(AMARILLO, 'La semana que viene aún no tiene plan (debía hacerse el domingo '
                                                    f'{_at(plan_at, ctx.now)}). El director planea cada día sin él.',
                                          'Pide «Volver a planear» en Estrategia.'))
    else:
        stages.append(apagada('Plan de la semana', 'STRATEGY_ENABLED=false'))
    if switches['resumen']:
        stages.append(etapa(ctx, 'Resumen semanal', with_jobs(WeeklySummary, 'created_at', 'weekly_summary'),
                            cola_trabajos(ctx, ['weekly_summary']), espera=timedelta(hours=3), entra='encargados'))
        due = resumen_semanal.due_at(ctx.now)
        week = resumen_semanal.last_week(ctx.now)
        if ctx.now >= due + PREPARACION and not _own(WeeklySummary.objects.filter(week_start=week), ctx).exists() \
                and not _jobs(ctx, ['weekly_summary']).filter(state__in=ACTIVE_JOBS).exists() \
                and _machine_ran(lambda: resumen_semanal.window(week)):
            res.hallazgos.append(Hallazgo(AMARILLO, f'No se generó el resumen de la semana pasada (tocaba el lunes '
                                                    f'{_at(due, ctx.now)}).', 'Pídelo con «Generar ahora» en Resultados.'))
    else:
        stages.append(apagada('Resumen semanal', 'WEEKLY_SUMMARY_ENABLED=false'))
    if switches['revision']:
        stages.append(etapa(ctx, 'Revisión mensual', with_jobs(MonthlyReview, 'created_at', 'monthly_review'),
                            cola_trabajos(ctx, ['monthly_review']), espera=timedelta(hours=3), entra='encargadas'))
        due = revision_mensual.due_at(ctx.now)
        month = revision_mensual.last_month(ctx.now)
        if ctx.now >= due + timedelta(days=1) + PREPARACION and \
                not _own(MonthlyReview.objects.filter(month_start=month), ctx).exists() and \
                not _jobs(ctx, ['monthly_review']).filter(state__in=ACTIVE_JOBS).exists() and \
                (ctx.now - due) < timedelta(days=7) and _machine_ran(lambda: revision_mensual.window(month)):
            res.hallazgos.append(Hallazgo(AMARILLO, 'No se generó la revisión del mes pasado (tocaba el primer lunes).',
                                          'Pídela con «Generar ahora» en Resultados.'))
    else:
        stages.append(apagada('Revisión mensual', 'MONTHLY_REVIEW_ENABLED=false'))
    res.etapas = stages
    this_week = _own(WeeklyPlan.objects.filter(week_start=monday, state=WeeklyPlan.State.PLANNED), ctx).exists()
    summary = _own(WeeklySummary.objects.filter(week_start=resumen_semanal.last_week(ctx.now)), ctx).exists()
    res.clave = (('plan de esta semana listo' if this_week else 'esta semana sin plan (el director planea cada día)') +
                 ('; resumen de la semana pasada listo' if summary else ''))
    return res


def _machine_ran(window):
    """Whether the machine ran in that week or month (resultados.Coverage.machine): without it the autopilot pays for no
    summary (resumen_semanal.queue, revision_mensual.queue), so none is expected."""
    try:
        from . import resultados
        return bool(resultados.Coverage.machine(window()))
    except Exception:  # noqa: BLE001 - without the coverage the summary is expected, as the autopilot would try it
        return True


# --------------------------------------------------------------------------- 3. his ideas (captures)

def _captures(ctx):
    from .models import Capture
    return _own(Capture.objects.exclude(state=Capture.State.UNDONE).exclude(context_type='pieza'), ctx)


def medir_ideas(ctx):
    from . import capturas
    from .models import ActionExecution, Capture, EditorialPiece
    res = Resultado(FLUJOS_POR_ID['ideas'])
    rows = _captures(ctx)
    progress = [s.value for s in capturas.IN_PROGRESS]
    ideas = Q(state__in=[Capture.State.IDEA, Capture.State.USED, Capture.State.UNUSED])

    def recibidas(window):
        got = list(rows.filter(**_in('created_at', window)).values_list('state', 'error'))
        failed = [motivo(e) for s, e in got if s == 'error']
        return Conteo(len(got), sum(1 for s, _ in got if s not in progress and s != 'error'), 0, len(failed), Counter(failed))

    def procesando():
        stuck = rows.filter(state__in=progress)
        return stuck.count(), stuck.order_by('created_at').values_list('created_at', flat=True).first()

    def en_la_mesa(window):
        return Conteo(0, rows.filter(ideas, **_in('created_at', window)).count())

    def mesa():
        waiting = rows.filter(state='idea')
        return waiting.count(), waiting.order_by('created_at').values_list('created_at', flat=True).first()

    def con_fecha(window):
        dated = rows.filter(Q(publish_at__isnull=False) | Q(publish_asap=True), **_in('created_at', window))
        return Conteo(dated.count(), dated.filter(publish_asap_expected_slot__isnull=False).count())

    def preguntas():
        asked = rows.filter(state='idea', day_request__state='problem')
        return asked.count(), asked.order_by('created_at').values_list('created_at', flat=True).first()

    pieces = _own(EditorialPiece.objects.all(), ctx)

    def preparadas(window):
        made = [str(pk) for pk in pieces.filter(**_in('created_at', window)).values_list('pk', flat=True)]
        return Conteo(0, rows.filter(state='usado', routed_to__used_in__in=made).count() if made else 0)

    def publicadas(window):
        out = [str(pk) for pk in _mine(ActionExecution.objects.filter(proposal__capability='CONT-09', wrote=True,
                                                                       **_in('started_at', window)).exclude(state='failed'),
                                       ctx, 'proposal__account').values_list('proposal__piece_id', flat=True)]
        return Conteo(0, rows.filter(state='usado', routed_to__used_in__in=out).count() if out else 0)

    def descartadas(window):
        start, end = window
        days = timedelta(days=capturas.IDEA_DAYS)
        return Conteo(0, 0, rows.filter(Q(**_in('created_at', window)) | Q(created_at__gte=start - days, created_at__lt=end - days),
                                        state=Capture.State.UNUSED).count())

    res.etapas = [
        etapa(ctx, 'Recibidas', recibidas, procesando, espera=CAPTURA_A_MEDIAS, entra='recibidas', cola='procesándose'),
        etapa(ctx, 'En la mesa editorial', en_la_mesa, mesa, cola='esperan un brief'),
        etapa(ctx, 'Con fecha', con_fecha, preguntas, entra='pedidas', cola='esperan tu respuesta sobre el día'),
        etapa(ctx, 'Preparadas en un post', preparadas),
        etapa(ctx, 'Publicadas', publicadas),
        etapa(ctx, 'Descartadas', descartadas, descarta='sin usar'),
    ]
    today = res.etapas[0].hoy
    waiting = res.etapas[1].esperando
    res.clave = (f'hoy {_plural(today.entraron, "captura recibida", "capturas recibidas")}; '
                 f'{_plural(waiting, "idea espera", "ideas esperan")} en la mesa editorial')
    if res.etapas[2].esperando:
        res.para_hoy.append(f'{_plural(res.etapas[2].esperando, "idea espera", "ideas esperan")} que confirmes el día')
    return res


# --------------------------------------------------------------------------- 4. his corrections to a post (retoque)

RETOQUE = {'rehecha': 'avanzaron', 'sin_cambios': 'avanzaron', 'sin_retoque': 'fallaron', 'aplazada': 'fallaron'}
RETOQUE_MOTIVO = {'sin_retoque': 'no se pudo rehacer (sin revisiones del líder o sin presupuesto)',
                  'aplazada': 'no se pudo aplicar: la pieza no sale así'}


def medir_retoque(ctx):
    from . import capturas
    from .models import Capture
    res = Resultado(FLUJOS_POR_ID['retoque'])
    rows = _own(Capture.objects.filter(context_type='pieza').exclude(state=Capture.State.UNDONE), ctx)

    def contar(window):
        conteo = Conteo()
        for routed in rows.filter(**_in('created_at', window)).values_list('routed_to', flat=True):
            conteo.entraron += 1
            rework = (routed or {}).get('rework')
            state = rework.get('state') if isinstance(rework, dict) else None
            outcome = RETOQUE.get(state)
            if outcome == 'avanzaron':
                conteo.avanzaron += 1
            elif outcome == 'fallaron':
                conteo.fallaron += 1
                conteo.motivos[RETOQUE_MOTIVO[state]] += 1
            elif rework is None:
                conteo.descartados += 1  # a piece that can no longer change: his comment stays as a note for the team
        return conteo

    def pendientes():
        waiting = rows.filter(Q(routed_to__rework='pending') | Q(state__in=[s.value for s in capturas.IN_PROGRESS]))
        return waiting.count(), waiting.order_by('created_at').values_list('created_at', flat=True).first()

    res.etapas = [etapa(ctx, 'Correcciones aplicadas', contar, pendientes, espera=CAPTURA_A_MEDIAS, entra='recibidas',
                        descarta='quedaron como nota', cola='aplicándose')]
    today = res.etapas[0].hoy
    res.clave = (_of(today.avanzaron, 'corrección aplicada', 'correcciones aplicadas', today.entraron, 'recibida', 'recibidas')
                 if today.entraron else 'hoy no mandaste correcciones')
    return res


# --------------------------------------------------------------------------- 5. comments on referents' posts (INT-03)

def medir_comentarios(ctx):
    from . import alertas_slack, operador
    from .models import ActionExecution, ObservedPost, Referent
    res = Resultado(FLUJOS_POR_ID['comentarios'])
    if operador.globally_paused():
        res.apagado = 'la máquina está detenida (OPERATOR_PAUSED o el interruptor de la oficina)'
    elif _autonomy('INT-03', ctx) == 'off':
        res.apagado = 'OPERATOR_AUTONOMY INT-03=off'
    elif not Referent.objects.filter(active=True, account__in=_accounts(ctx)).exists():
        res.apagado = 'sin referentes activos'
    if res.apagado:
        return res

    def observados(window):
        new = _mine(ObservedPost.objects.all(), ctx).filter(**_in('observed_at', window)).count()
        jobs = contar_trabajos(ctx, ['observe'])(window)
        return Conteo(new, new, 0, jobs.fallaron, jobs.motivos)

    def propuestos(window):
        jobs = contar_trabajos(ctx, ['propose_comment'])(window)
        made = contar_revision(ctx, 'INT-03')(window)
        return Conteo(jobs.entraron, made.entraron, 0, jobs.fallaron, jobs.motivos)

    def confirmados(window):
        rows = _mine(ActionExecution.objects.filter(proposal__capability='INT-03', wrote=True), ctx, 'proposal__account')
        rows = rows.filter(**_in('started_at', window))
        uncertain = rows.filter(state='uncertain').count()
        return Conteo(rows.count(), rows.filter(state='confirmed').count(), 0, uncertain,
                      Counter({'LinkedIn no confirmó si salió': uncertain} if uncertain else {}))

    res.etapas = [
        etapa(ctx, 'Posts observados', observados, cola_trabajos(ctx, ['observe']), espera=espera_horas()),
        etapa(ctx, 'Comentario propuesto', propuestos, cola_trabajos(ctx, ['propose_comment']), espera=espera_horas(),
              entra='encargados'),
        etapa(ctx, 'Revisado por el líder', contar_revision(ctx, 'INT-03'), cola_escrituras(ctx, 'INT-03', ('proposed',)),
              espera=None if _autonomy('INT-03', ctx) == 'approval' else espera_horas(), entra='propuestos',
              cola=_approval_queue('INT-03', ctx)),
        etapa(ctx, 'Publicado', contar_escrituras(ctx, 'INT-03'), cola_escrituras(ctx, 'INT-03'), espera=timedelta(hours=12),
              entra='propuestos', cola='aprobados en cola'),
        etapa(ctx, 'Confirmado en LinkedIn', confirmados, entra='publicados'),
    ]
    res.hallazgos += _lead_discards(res.etapas[2], ctx)
    if alertas_slack.sin_comentarios.__wrapped__(ctx.now, ctx.member):
        hours = int(alertas_slack.no_comments_hours().total_seconds() // 3600)
        if res.etapas[2].cola == 'esperan tu aprobación' and res.etapas[2].esperando:
            res.hallazgos.append(Hallazgo(AMARILLO, f'Ningún comentario publicado en {hours} horas de ventana: '
                                                    f'{res.etapas[2].esperando} esperan tu aprobación.', 'Apruébalos en Tu turno.'))
        else:
            res.hallazgos.append(Hallazgo(ROJO, f'Ningún comentario publicado en {hours} horas de ventana.',
                                          'Revisa el calendario («Mostrar lo que no salió»).'))
    today = res.etapas[3].hoy
    res.clave = _of(today.avanzaron, 'comentario publicado', 'comentarios publicados', today.entraron, 'propuesto', 'propuestos')
    waiting = res.etapas[3].esperando
    if waiting:
        res.anoche.append(f'{_plural(waiting, "comentario aprobado espera", "comentarios aprobados esperan")} su turno')
    if res.etapas[2].cola == 'esperan tu aprobación' and res.etapas[2].esperando:
        res.para_hoy.append(f'{_plural(res.etapas[2].esperando, "comentario espera", "comentarios esperan")} tu aprobación')
    return res


# --------------------------------------------------------------------------- 6. replies on his own posts (INT-04)

def medir_respuestas(ctx):
    from . import alertas_slack, operador, respuestas
    from .models import PostComment
    res = Resultado(FLUJOS_POR_ID['respuestas'])
    if operador.globally_paused():
        res.apagado = 'la máquina está detenida (OPERATOR_PAUSED o el interruptor de la oficina)'
    elif not respuestas.enabled(ctx.member):
        res.apagado = 'REPLIES_ENABLED=false u OPERATOR_AUTONOMY INT-04=off'
    if res.apagado:
        return res
    comments = _mine(PostComment.objects.filter(own=False), ctx)

    def leidos(window):
        new = comments.filter(**_in('observed_at', window)).count()
        jobs = contar_trabajos(ctx, ['read_own_comments'])(window)
        return Conteo(new, new, 0, jobs.fallaron, jobs.motivos)

    def propuestas(window):
        jobs = contar_trabajos(ctx, ['propose_reply'])(window)
        made = contar_revision(ctx, 'INT-04')(window)
        return Conteo(made.entraron, made.avanzaron, made.descartados, jobs.fallaron, jobs.motivos)

    def sin_responder():
        """Comments that deserve an answer and wait for the machine (a draft, the lead, a write turn): not those that wait
        for Gustavo (a question of the team, «¿Salió o no?») nor those the lead discarded or whose drafts failed."""
        waiting = []
        for row in comments.filter(state__in=['new', 'reply'], commented_at__gte=ctx.now - respuestas.window()):
            decision = row.decision or {}
            if row.state == 'new' and 'turn' not in decision:
                continue
            proposal = row.proposals.filter(capability='INT-04').order_by('-created_at').first()
            if proposal is None and int(decision.get('attempts', 0)) >= respuestas.MAX_DRAFTS:
                continue
            if proposal is None or proposal.state in ('proposed', 'approved', 'executing'):
                waiting.append(row.commented_at)
        return len(waiting), min(waiting) if waiting else None

    res.etapas = [
        etapa(ctx, 'Comentarios leídos', leidos, cola_trabajos(ctx, ['read_own_comments']), espera=espera_horas()),
        etapa(ctx, 'Respuesta propuesta', propuestas, sin_responder, espera=alertas_slack.reply_pending_hours(),
              entra='propuestas', cola='comentarios esperan respuesta'),
        etapa(ctx, 'Publicada', contar_escrituras(ctx, 'INT-04'), cola_escrituras(ctx, 'INT-04'), espera=espera_horas(),
              entra='propuestas', cola='aprobadas en cola'),
    ]
    res.hallazgos += _lead_discards(res.etapas[1], ctx)
    stopped = alertas_slack.lecturas_detenidas.__wrapped__(ctx.now, ctx.member)
    if stopped:
        reader = respuestas.reader_account(ctx.member)
        why = _IDS.sub('…', alertas_slack._why_not_reading(reader, ctx.now, ctx.member))[:160]
        res.hallazgos.append(Hallazgo(ROJO, f'No se están leyendo los comentarios de tus posts: {why}.'))
    today = res.etapas[2].hoy
    res.clave = (f'hoy {_plural(today.avanzaron, "respuesta publicada", "respuestas publicadas")}; '
                 f'{_plural(res.etapas[1].esperando, "comentario espera", "comentarios esperan")} respuesta')
    return res


# --------------------------------------------------------------------------- 7. growing the network (RED-*)

def medir_red(ctx):
    from . import alertas_slack, nivel_comprador, operador, red
    from .models import AuditEvent, Contact
    res = Resultado(FLUJOS_POR_ID['red'])
    if operador.globally_paused():
        res.apagado = 'la máquina está detenida (OPERATOR_PAUSED o el interruptor de la oficina)'
    elif not red.enabled():
        res.apagado = 'NETWORK_ENABLED=false'
    if res.apagado:
        return res
    contacts = _mine(Contact.objects.all(), ctx)
    accounts = [str(pk) for pk in _accounts(ctx).values_list('pk', flat=True)]

    def encontrados(window):
        new = contacts.filter(**_in('discovered_at', window)).count()
        jobs = contar_trabajos(ctx, ['discover_network'])(window)
        return Conteo(new, new, 0, jobs.fallaron, jobs.motivos)

    def clasificados(window):
        done = AuditEvent.objects.filter(action='network.classified', target__in=accounts, **_in('created_at', window))
        classified = sum(int((m or {}).get('classified') or 0) for m in done.values_list('metadata', flat=True))
        jobs = contar_trabajos(ctx, ['classify_contacts'])(window)
        discarded = contacts.filter(stage='discarded', **_in('updated_at', window)).count()
        return Conteo(classified, classified, discarded, jobs.fallaron, jobs.motivos)

    def sin_clasificar():
        rows = contacts.filter(classification={}, stage__in=['candidate', 'incoming'])
        return rows.count(), rows.order_by('discovered_at').values_list('discovered_at', flat=True).first()

    def verificados(window):
        jobs = contar_trabajos(ctx, ['check_buyer_stages'])(window)
        return Conteo(jobs.entraron, jobs.avanzaron, 0, jobs.fallaron, jobs.motivos)

    def por_verificar():
        rows = contacts.filter(stage__in=list(red.ACTIVE_STAGES), classification__stage_check__state='pending')
        return rows.count(), None  # each has its own next try: a count, not an age

    def aceptaron(window):
        return Conteo(0, contacts.filter(**_in('connected_at', window)).count())

    def invitaciones_abiertas():
        rows = contacts.filter(stage='invited')
        return rows.count(), None

    asked = 0  # proposals waiting for his approval (his OPERATOR_AUTONOMY=approval): his, never the machine's queue

    def accion(nombre, capability):
        nonlocal asked
        if _autonomy(capability, ctx) == 'off':
            return apagada(nombre, f'OPERATOR_AUTONOMY {capability}=off')
        if _autonomy(capability, ctx) == 'approval':
            asked += cola_escrituras(ctx, capability, ('proposed',))()[0]
        return etapa(ctx, nombre, contar_escrituras(ctx, capability), cola_escrituras(ctx, capability), espera=ESPERA_RED,
                     entra='propuestos', cola='aprobados en cola')

    res.etapas = [
        etapa(ctx, 'Perfiles encontrados', encontrados, cola_trabajos(ctx, ['discover_network']), espera=espera_horas()),
        etapa(ctx, 'Clasificados', clasificados, sin_clasificar, espera=ESPERA_RED, descarta='descartados',
              cola='sin clasificar'),
        etapa(ctx, 'Verificados en la web', verificados, por_verificar, entra='encargados', cola='por verificar')
        if red.stage_check_enabled() else apagada('Verificados en la web', 'NETWORK_STAGE_CHECK=false'),
        accion('Seguidos', 'RED-01'),
        accion('Invitados', 'RED-02'),
        etapa(ctx, 'Aceptaron tu invitación', aceptaron, invitaciones_abiertas, cola='invitaciones sin respuesta'),
        accion('Invitaciones recibidas aceptadas', 'RED-04'),
    ]
    # Buyers out of the neighborhood with a level that keeps them (18/11/2026): a classification rule, not the level.
    left = [c for c in contacts.filter(stage='discarded', classification__role='comprador', **_in('updated_at', ctx.dia))
            .only('id', 'stage', 'classification', 'account_id') if nivel_comprador.left_by_model_fit(c)]
    if left:
        res.hallazgos.append(Hallazgo(AMARILLO, f'{_plural(len(left), "comprador salió", "compradores salieron")} del barrio en '
                                                '24 h con un nivel que lo mantiene (una regla de clasificación, no su nivel).',
                                      'Recupéralos sin pagar otra clasificación con el comando del operador '
                                      '«reevaluar-compradores» (sin --confirmar no cambia nada).'))
    member = operador.member_of(member=ctx.member)
    ran_out = operador.actions_ran_out_at(member, ctx.now)
    if ran_out is not None:
        pools = operador.profile_read_pools(member, ctx.now)
        res.hallazgos.append(Hallazgo(AMARILLO, f'Seguir e invitar se quedaron sin lecturas de perfil a las {_hhmm(ran_out)} '
                                                f'(acciones {pools["acciones"]["usadas"]}/{pools["acciones"]["tope"]}, investigación '
                                                f'{pools["investigacion"]["usadas"]}/{pools["investigacion"]["tope"]}).',
                                      que_hacer('sin lecturas de perfil: la investigación dejó sin cupo a las acciones')))
    if AuditEvent.objects.filter(action='network.stage_check_paused', target__in=accounts, **_in('created_at', ctx.dia)).exists():
        res.hallazgos.append(Hallazgo(AMARILLO, 'La investigación web no devuelve hallazgos: se pausaron las verificaciones '
                                                'de compradores.', 'Revisa la investigación en internet (flujo de abajo).'))
    ramp = alertas_slack.rampa_en_pausa.__wrapped__(ctx.now, ctx.member)
    if ramp:
        until = red.ramp_state(ctx.now, ctx.member).get('pause_until')
        res.hallazgos.append(Hallazgo(AMARILLO, f'Invitaciones en pausa hasta {_since(datetime.fromisoformat(until), ctx.now)} '
                                                '(aceptación baja o un límite de LinkedIn).', 'Revisa en Personas a quién se invita.'))
    by_name = {e.nombre: e for e in res.etapas}
    follows, invites = by_name['Seguidos'].hoy, by_name['Invitados'].hoy
    res.clave = (f'hoy {follows.avanzaron} seguidos, {invites.avanzaron} invitados y '
                 f'{by_name["Aceptaron tu invitación"].hoy.avanzaron} aceptaron tu invitación')
    approved = sum(e.esperando for e in res.etapas if e.cola == 'aprobados en cola')
    if approved:
        res.anoche.append(f'{_plural(approved, "acción de red aprobada espera", "acciones de red aprobadas esperan")} su tanda')
    if asked:
        res.para_hoy.append(f'{_plural(asked, "acción de red espera", "acciones de red esperan")} tu aprobación')
    return res


# --------------------------------------------------------------------------- 8. the buyer (outbound, phases 2–6)

def medir_comprador(ctx):
    from . import calentamiento, lider, mensajes_comprador, respuesta_comprador, secuencia_comprador
    from .models import AuditEvent, BuyerDraft, BuyerJourney, MeetingBooking
    res = Resultado(FLUJOS_POR_ID['comprador'])
    switches = {'calentamiento': calentamiento.enabled(), 'primero': mensajes_comprador.enabled(),
                'secuencia': secuencia_comprador.enabled(), 'respuesta': respuesta_comprador.enabled()}
    if not any(switches.values()):
        res.apagado = 'BUYER_WARMUP_ENABLED, BUYER_FIRST_MESSAGE_ENABLED, BUYER_SEQUENCE_ENABLED y BUYER_REPLY_ENABLED en false'
        return res
    journeys = _mine(BuyerJourney.objects.all(), ctx, 'contact__account')
    drafts = _mine(BuyerDraft.objects.all(), ctx, 'contact__account')

    def calentando(window):
        return Conteo(journeys.filter(**_in('chosen_at', window)).count(), journeys.filter(**_in('invited_at', window)).count())

    def en_calentamiento():
        rows = journeys.filter(step=BuyerJourney.Step.WARMING)
        return rows.count(), None

    def borradores(rows, which):
        def contar(window):
            made = rows.filter(**_in('created_at', window))
            jobs = _jobs(ctx, ['prepare_buyer_draft']).filter(which)
            failed = list(jobs.filter(state__in=FAILED_JOBS, **_in('finished_at', window)).values_list('error', flat=True))
            return Conteo(made.count(), rows.filter(state__in=['listo', 'enviado', 'usada'], **_in('decided_at', window)).count(),
                          rows.filter(state__in=['descartado', 'sin_borrador'], **_in('decided_at', window)).count(),
                          len(failed), Counter(motivo(e) for e in failed))
        return contar

    def listos(rows):
        def cola():
            ready = rows.filter(state='listo')
            return ready.count(), ready.order_by('decided_at').values_list('decided_at', flat=True).first()
        return cola

    first = drafts.filter(kind=BuyerDraft.Kind.MESSAGE, number=1)
    follow = drafts.filter(kind=BuyerDraft.Kind.MESSAGE, number__gt=1)
    replies = drafts.filter(kind=BuyerDraft.Kind.REPLY)
    # Their jobs (autopiloto._buyer_drafts): a first message carries no `number`, a follow-up and a reply do.
    first_jobs = Q(params__kind=BuyerDraft.Kind.MESSAGE) & ~Q(params__has_key='number')
    follow_jobs = Q(params__kind=BuyerDraft.Kind.MESSAGE, params__has_key='number')
    reply_jobs = Q(params__kind=BuyerDraft.Kind.REPLY)

    def reunion(window):
        return Conteo(journeys.filter(**_in('replied_at', window)).count(), journeys.filter(**_in('meeting_at', window)).count())

    def sin_emparejar():
        rows = MeetingBooking.objects.filter(matched_by=MeetingBooking.MatchedBy.NONE, state=MeetingBooking.State.BOOKED)
        return rows.count(), rows.order_by('created_at').values_list('created_at', flat=True).first()

    lead_off = '' if lider.enabled() else ' (y LEAD_ENABLED)'
    res.etapas = [
        etapa(ctx, 'Calentamiento', calentando, en_calentamiento, entra='elegidos', cola='calentando')
        if switches['calentamiento'] else apagada('Calentamiento', 'BUYER_WARMUP_ENABLED=false'),
        etapa(ctx, 'Primer mensaje', borradores(first, first_jobs), listos(first), entra='preparados',
              cola='listos para que los envíes')
        if mensajes_comprador.active() else apagada('Primer mensaje', 'BUYER_FIRST_MESSAGE_ENABLED' + lead_off),
        etapa(ctx, 'Secuencia (mensajes 2 a 4)', borradores(follow, follow_jobs), listos(follow), entra='preparados',
              cola='listos para que los envíes')
        if secuencia_comprador.active() else apagada('Secuencia (mensajes 2 a 4)', 'BUYER_SEQUENCE_ENABLED' + lead_off),
        etapa(ctx, 'Respuesta a quien respondió', borradores(replies, reply_jobs), listos(replies), entra='preparadas',
              cola='listas para que las envíes')
        if respuesta_comprador.active() else apagada('Respuesta a quien respondió', 'BUYER_REPLY_ENABLED'),
        etapa(ctx, 'Reunión', reunion, sin_emparejar, entra='respondieron', cola='reservas sin emparejar')
        if switches['respuesta'] else apagada('Reunión', 'BUYER_REPLY_ENABLED=false'),
    ]
    if secuencia_comprador.enabled() and AuditEvent.objects.filter(action=secuencia_comprador.WAITING, **_in('created_at', ctx.dia)).exists():
        res.hallazgos.append(Hallazgo(AMARILLO, 'La secuencia está detenida: no se leyó la bandeja y no se sabe si respondieron.',
                                      'Enciende INBOX_ENABLED o revisa la cuenta y sus cupos de lectura.'))
    if respuesta_comprador.enabled() and AuditEvent.objects.filter(action=respuesta_comprador.NO_LINK, **_in('created_at', ctx.dia)).exists():
        res.hallazgos.append(Hallazgo(AMARILLO, 'Respuestas de compradores sin borrador: falta tu enlace de agenda.',
                                      'Configura CALCOM_BOOKING_URL.'))
    ready = sum(e.esperando for e in res.etapas if e.cola.startswith('listo'))
    warming = res.etapas[0].esperando
    res.clave = (f'{_plural(warming, "comprador calentándose", "compradores calentándose")}; '
                 f'{_plural(ready, "mensaje listo", "mensajes listos")} para que {"lo" if ready == 1 else "los"} envíes')
    if ready:
        res.para_hoy.append(f'{_plural(ready, "mensaje a un comprador está listo", "mensajes a compradores están listos")} '
                            'para que los envíes')
    return res


# --------------------------------------------------------------------------- 9. private messages (inbox)

def medir_inbox(ctx):
    from . import conversaciones, operador
    from .models import Conversation
    res = Resultado(FLUJOS_POR_ID['inbox'])
    if operador.globally_paused():
        res.apagado = 'la máquina está detenida (OPERATOR_PAUSED o el interruptor de la oficina)'
    elif not conversaciones.enabled():
        res.apagado = 'INBOX_ENABLED=false'
    if res.apagado:
        return res
    rows = _mine(Conversation.objects.all(), ctx)

    def leidos(window):
        jobs = contar_trabajos(ctx, ['read_inbox'])(window)
        new = rows.filter(last_from_me=False, **_in('last_message_at', window)).count()
        return Conteo(jobs.entraron, jobs.avanzaron, 0, jobs.fallaron, jobs.motivos) if jobs.entraron else Conteo(new, new)

    def te_tocan():
        waiting = [c.last_message_at for c in rows.filter(last_from_me=False, last_message_at__gte=ctx.now - conversaciones.max_age())
                   if conversaciones.needs_gustavo(c, ctx.now)]
        return len(waiting), min(waiting) if waiting else None

    res.etapas = [
        etapa(ctx, 'Bandeja leída', leidos, cola_trabajos(ctx, ['read_inbox']), espera=espera_horas(), entra='lecturas'),
        etapa(ctx, 'Te tocan a ti', lambda window: Conteo(), te_tocan, cola='esperan tu respuesta'),
    ]
    if operador.within_read_window(ctx.now) and ctx.now - operador.read_bounds(ctx.now)[0] > 3 * conversaciones.every():
        last = _jobs(ctx, ['read_inbox']).filter(state='complete').order_by('-finished_at').values_list('finished_at', flat=True).first()
        if last is None or ctx.now - last > 3 * conversaciones.every():
            res.hallazgos.append(Hallazgo(AMARILLO, 'No se lee la bandeja ' + (f'desde {_since(last, ctx.now)}' if last else
                                                                              'desde hace días') + '.',
                                          'Revisa la cuenta de LinkedIn y el worker.'))
    waiting = res.etapas[1].esperando
    reads = res.etapas[0].hoy.avanzaron
    res.clave = (f'bandeja leída {reads} {"vez" if reads == 1 else "veces"} hoy; '
                 f'{_plural(waiting, "conversación te espera", "conversaciones te esperan")}')
    if waiting:
        res.para_hoy.append(f'{_plural(waiting, "conversación de LinkedIn te espera", "conversaciones de LinkedIn te esperan")}')
    return res


# --------------------------------------------------------------------------- 10. referents

def medir_referentes(ctx):
    from . import analisis_referentes
    from .models import ObservedPost, Referent, ReferentChange, ReferentExperiment, ReferentReview
    res = Resultado(FLUJOS_POR_ID['referentes'])
    accounts = _accounts(ctx)
    reviews = ReferentReview.objects.filter(account__in=accounts)

    def revision(kind):
        def contar(window):
            made = reviews.filter(kind=kind)
            jobs = _jobs(ctx, ['review_referents'])
            jobs = jobs.filter(params__has_key='industria') if kind == 'industria' else jobs.exclude(params__has_key='industria')
            failed = list(jobs.filter(state__in=FAILED_JOBS, **_in('finished_at', window)).values_list('error', flat=True))
            return Conteo(made.filter(**_in('created_at', window)).count(), made.filter(**_in('published_at', window)).count(),
                          0, len(failed), Counter(motivo(e) for e in failed))
        return contar

    def cambios():
        rows = ReferentChange.objects.filter(review__account__in=accounts, state='pending', responded_at__isnull=True,
                                             review__closed_at__isnull=True)
        return rows.count(), None

    def analizados(window):
        posts = ObservedPost.objects.filter(account__in=accounts, referent__kind=Referent.Kind.INDUSTRIA, **_in('observed_at', window))
        return Conteo(0, posts.count())

    def experimentos(window):
        jobs = contar_trabajos(ctx, ['advance_experiments'])(window)
        return Conteo(jobs.entraron, jobs.avanzaron, 0, jobs.fallaron, jobs.motivos)

    def activos():
        return ReferentExperiment.objects.filter(account__in=accounts, state='approved').count(), None

    res.etapas = [
        etapa(ctx, 'Revisión mensual', revision('mensual'), cambios, entra='preparadas', cola='cambios esperan tu respuesta'),
        etapa(ctx, 'Búsqueda de referentes de industria', revision('industria'), entra='pedidas'),
        etapa(ctx, 'Análisis de posts', analizados) if analisis_referentes.enabled()
        else apagada('Análisis de posts', 'REFERENTES_ANALISIS=false'),
        etapa(ctx, 'Experimentos', experimentos, activos, cola='en curso'),
    ]
    preparing = reviews.filter(state='preparing', created_at__lt=ctx.now - timedelta(days=1)).exists()
    if preparing:
        res.hallazgos.append(Hallazgo(AMARILLO, 'Una revisión de referentes lleva más de un día preparándose.',
                                      'Míralo en Personas › Referentes.'))
    active = Referent.objects.filter(account__in=accounts, active=True).count()
    res.clave = (f'{_plural(active, "referente activo", "referentes activos")}; '
                 f'{_plural(res.etapas[0].esperando, "cambio espera", "cambios esperan")} tu respuesta')
    if res.etapas[0].esperando:
        res.para_hoy.append(f'{_plural(res.etapas[0].esperando, "cambio de referentes espera", "cambios de referentes esperan")} '
                            'tu respuesta')
    return res


# --------------------------------------------------------------------------- 11. web research (the installation's)

RESEARCH_KINDS = (('piece:', 'Para los posts'), ('capture:', 'Para tus ideas'), ('etapa:', 'Para verificar compradores'),
                  ('referents:', 'Para referentes'), ('profile:', 'Para tu perfil'))


def medir_investigacion(ctx):
    from . import red, web_sources
    from .models import WebResearchRun
    res = Resultado(FLUJOS_POR_ID['investigacion'])
    try:
        web_sources.live_web()
    except ValueError:
        res.apagado = 'WEB_RESEARCH_ENABLED o LIVE_PROVIDERS en false'
        return res
    stale = ctx.now - INVESTIGACION_A_MEDIAS

    def contar(prefix):
        def inner(window):
            rows = list(WebResearchRun.objects.filter(key__startswith=prefix, **_in('created_at', window))
                        .values_list('state', 'result', 'created_at'))
            conteo = Conteo(len(rows))
            for state, result, created in rows:
                limits = (result or {}).get('limitations') or []
                if state in ('complete', 'partial'):
                    conteo.avanzaron += 1
                elif state == 'skipped':
                    conteo.descartados += 1
                elif state == 'running' and created < stale:
                    conteo.fallaron += 1
                    conteo.motivos['quedó a medias'] += 1
                elif state == 'unavailable':
                    conteo.fallaron += 1
                    conteo.motivos[motivo(limits[0] if limits else 'sin hallazgos')] += 1
            return conteo
        return inner

    def a_medias(prefix):
        def cola():
            rows = WebResearchRun.objects.filter(key__startswith=prefix, state='running')
            return rows.count(), rows.order_by('created_at').values_list('created_at', flat=True).first()
        return cola

    res.etapas = [etapa(ctx, name, contar(prefix), a_medias(prefix), espera=INVESTIGACION_A_MEDIAS, entra='pedidas',
                        descarta='omitidas', cola='en curso') for prefix, name in RESEARCH_KINDS]
    stuck = WebResearchRun.objects.filter(state='running', created_at__lt=stale)
    if stuck.exists():
        oldest = stuck.order_by('created_at').values_list('created_at', flat=True).first()
        res.hallazgos.append(Hallazgo(AMARILLO, f'{_plural(stuck.count(), "investigación quedó", "investigaciones quedaron")} a '
                                                f'medias (en curso desde {_since(oldest, ctx.now)}): su gasto no se repite y su '
                                                'resultado no llegó.', 'Revisa el registro del worker en esa hora.'))
    if red.research_silent(ctx.now):
        res.hallazgos.append(Hallazgo(AMARILLO, 'Las últimas investigaciones no trajeron ningún hallazgo con citas.',
                                      'Revisa WEB_SEARCH_TOOL_TYPE y el proveedor.'))
    done = sum(e.hoy.avanzaron for e in res.etapas)
    asked = sum(e.hoy.entraron for e in res.etapas)
    res.clave = (_of(done, 'investigación hecha', 'investigaciones hechas', asked, 'pedida', 'pedidas') if asked
                 else 'hoy no se pidió ninguna')
    return res


# --------------------------------------------------------------------------- 12. profile and positioning

def medir_perfil(ctx):
    from .models import CommunityStudy, ProfileProposal
    res = Resultado(FLUJOS_POR_ID['perfil'])
    accounts = _accounts(ctx)
    proposals = _own(ProfileProposal.objects.all(), ctx, 'owner__member')
    open_states = ['ready', 'partial']  # perfil.proposal_state: waiting for his review

    def propuestas(window):
        rows = proposals.filter(**_in('created_at', window))
        jobs = contar_trabajos(ctx, ['prepare_profile', 'prepare_profile_assets'])(window)
        stopped = rows.filter(state='stopped').count()
        return Conteo(rows.count(), rows.filter(state__in=open_states).count(), 0, stopped + jobs.fallaron,
                      Counter({'el ciclo de perfil se detuvo': stopped} if stopped else {}) + jobs.motivos)

    def abiertas():
        rows = proposals.filter(state__in=open_states, updated_at__gte=ctx.now - timedelta(days=35))
        return rows.count(), None

    def estudio(window):
        rows = CommunityStudy.objects.filter(account__in=accounts, **_in('created_at', window))
        jobs = contar_trabajos(ctx, ['community_study'])(window)
        errors = rows.filter(state='partial_error').count()
        return Conteo(rows.count(), rows.exclude(state__in=['building', 'partial_error']).count(), 0, errors + jobs.fallaron,
                      Counter({'el estudio terminó con errores': errors} if errors else {}) + jobs.motivos)

    def construyendo():
        rows = CommunityStudy.objects.filter(account__in=accounts, state='building')
        return rows.count(), rows.order_by('created_at').values_list('created_at', flat=True).first()

    res.etapas = [
        etapa(ctx, 'Propuesta de perfil', propuestas, abiertas, entra='encargadas', cola='esperan tu revisión')
        if _on('PROFILE_ENABLED', 'false') else apagada('Propuesta de perfil', 'PROFILE_ENABLED=false'),
        etapa(ctx, 'Estudio de la comunidad', estudio, construyendo, espera=timedelta(hours=24), entra='empezados',
              cola='construyéndose'),
    ]
    res.clave = (f'{_plural(res.etapas[0].esperando, "propuesta espera", "propuestas esperan")} tu revisión'
                 if res.etapas[0].esperando else 'al día')
    if all(e.apagada for e in res.etapas[:1]) and not res.etapas[1].hoy.entraron and not res.etapas[1].esperando:
        res.clave = 'propuestas de perfil apagadas; estudio de la comunidad al día'
    return res


# --------------------------------------------------------------------------- 13. the machine's health

ESCRITURAS = {'CONT-09': 'posts', 'INT-03': 'comentarios', 'INT-04': 'respuestas', 'INT-02': 'reacciones', 'RED-01': 'seguir',
              'RED-02': 'invitar', 'RED-04': 'aceptar'}

def medir_salud(ctx):
    from knowledge import presupuesto
    from . import alertas_slack, autopiloto, operador
    from .models import ActionProposal, CanaryRun, Job
    res = Resultado(FLUJOS_POR_ID['salud'])
    if not autopiloto.enabled():
        res.hallazgos.append(Hallazgo(ROJO, 'El autopiloto está apagado: nada se encola solo.', 'Enciende OPERATOR_AUTOPILOT.'))
    if operador.globally_paused():
        res.hallazgos.append(Hallazgo(ROJO, 'La máquina está detenida (OPERATOR_PAUSED o el interruptor de la oficina).',
                                      'Reanúdala desde la Oficina cuando quieras que siga.'))
    lines = []
    if ctx.first:
        try:
            money = presupuesto.status(ctx.now)
            spent, limit = money['month_usd'], money['monthly_limit_usd']
            lines.append(f'IA: {alertas_slack.usd(money["today_usd"])} USD hoy, {alertas_slack.usd(spent)} de '
                         f'{alertas_slack.usd(limit)} en el mes')
            if limit > 0 and spent >= limit:
                res.hallazgos.append(Hallazgo(ROJO, f'Se acabó el presupuesto de IA del mes ({alertas_slack.usd(spent)} de '
                                                    f'{alertas_slack.usd(limit)} USD): nada pagado avanza.',
                                              que_hacer('sin presupuesto de IA')))
            elif money['left_usd'] <= 0:
                res.hallazgos.append(Hallazgo(ROJO, 'Se acabó el presupuesto de IA de hoy (AI_DAILY_FUSE_USD): nada pagado avanza '
                                                    'hasta mañana.', que_hacer('sin presupuesto de IA')))
            elif limit > 0 and spent >= limit * Decimal(str(alertas_slack.cap_threshold())):
                res.hallazgos.append(Hallazgo(AMARILLO, f'El gasto de IA del mes va en {alertas_slack.usd(spent)} de '
                                                        f'{alertas_slack.usd(limit)} USD.'))
        except Exception:  # noqa: BLE001 - the ledger unreadable is itself worth a line, never a broken report
            lines.append('IA: sin dato (no se pudo leer el registro de gasto)')
    reader = alertas_slack._reader(ctx.member)
    full = []
    if reader is not None:
        for scope, kind, used, cap in alertas_slack.read_caps(reader, ctx.now, ctx.member):
            if cap > 0 and used >= cap:
                full.append(alertas_slack._what(scope, kind)[0])
    if full:  # a daily cap is a limit, not a fault (cupos_de_lectura alerts it); what it stops shows in its own flow
        lines.append(f'Cupos de lectura agotados hoy: {", ".join(full[:4])}' + (f' y {len(full) - 4} más' if len(full) > 4 else ''))
    writes = [f'{ESCRITURAS.get(cap, cap)} {used}/{daily}' for cap, used, daily in alertas_slack.write_caps(ctx.now, ctx.member)]
    if writes:
        lines.append('Escrituras de hoy: ' + ', '.join(writes))
    for account in _accounts(ctx).filter(paused=True):
        res.hallazgos.append(Hallazgo(ROJO, f'La cuenta «{account.label}» está en pausa: no lee ni escribe.',
                                      'Reanúdala desde la app cuando esté resuelto.'))
    canary = CanaryRun.objects.filter(account__in=_accounts(ctx), **_in('started_at', ctx.dia)).order_by('-started_at').first()
    if canary is not None and canary.state == CanaryRun.State.BROKEN:
        res.hallazgos.append(Hallazgo(AMARILLO, 'La prueba diaria de LinkedIn encontró algo que cambió.',
                                      'Mírala en Ajustes › LinkedIn.'))

    def cola_general(window):
        rows = Job.objects.filter(**_in('created_at', window))
        failed = list(Job.objects.filter(state__in=FAILED_JOBS, **_in('finished_at', window)).values_list('kind', flat=True))
        return Conteo(rows.count(), Job.objects.filter(state='complete', **_in('finished_at', window)).count(), 0, len(failed),
                      Counter(failed))

    def en_cola():
        rows = Job.objects.filter(state='queued')
        return rows.count(), rows.order_by('created_at').values_list('created_at', flat=True).first()

    if ctx.first:
        jobs = etapa(ctx, 'Cola de trabajos', cola_general, en_cola, espera=None)
        jobs.dia = Conteo(jobs.dia.entraron, jobs.dia.avanzaron)  # each flow judges its own failures
        res.etapas.append(jobs)
        for alert in alertas_slack.cola_detenida(ctx.now):
            lane = alert.key.rsplit(':', 1)[-1]
            res.hallazgos.append(Hallazgo(ROJO, f'El worker de «{lane}» no está procesando su cola.',
                                          'Revisa ese contenedor en el servidor (docker compose ps y logs).'))
        if alertas_slack.navegador_no_disponible(ctx.now):
            res.hallazgos.append(Hallazgo(AMARILLO, 'El navegador de LinkedIn no responde: escrituras aplazadas en la última hora.',
                                          'Revisa el servicio navegador en el servidor.'))
        uncertain = ActionProposal.objects.filter(state='uncertain').count()
        if uncertain:
            res.hallazgos.append(Hallazgo(AMARILLO, f'{_plural(uncertain, "escritura", "escrituras")} sin confirmar en LinkedIn.',
                                          'Respóndelas en Tu turno («¿Salió o no?»).'))
            res.para_hoy.append(f'{_plural(uncertain, "«¿Salió o no?» espera", "«¿Salió o no?» esperan")} tu respuesta')
    res.clave = '; '.join(lines[:1]) or 'al día'
    res.notas = lines
    return res


# --------------------------------------------------------------------------- the registry

FLUJOS = (
    Flujo('post_diario', 'Post diario',
          'Prepara, revisa, ilustra y publica tu post de cada día a su hora, y después lee cómo le fue.',
          (('Plan del día', 'el autopiloto encarga la preparación del hueco (trabajos prepare_piece)'),
           ('Preparación', 'director, investigación, redacción, lectores, verificación y reparación (piezas creadas, '
                           'listas, saltadas por el director, fallidas o bloqueadas con su nota)'),
           ('Imagen propia', 'piezas listas con su propia imagen; los respaldos (la frase del post, una foto de la galería '
                             'o la tarjeta genérica) cuentan aparte'),
           ('Programado', 'la propuesta de publicación aprobada por el líder o por ti, o descartada (CONT-09)'),
           ('Publicado', 'escrituras CONT-09 en LinkedIn; los intentos fallidos de execute_action, con su motivo'),
           ('Métricas', 'cortes de 24 h, 72 h y 7 días leídos (PostMetric) y los cortes vencidos sin leer')),
          ('OPERATOR_AUTONOMY CONT-09', 'LIVE_LINKEDIN_OFFICIAL', 'EDITORIAL_POST_TIME', 'EDITORIAL_LEAD_HOURS', 'OPERATOR_PAUSED'),
          medir_post),
    Flujo('plan_resumenes', 'Plan semanal y resúmenes',
          'El domingo planea la semana siguiente; el lunes resume la semana pasada; el primer lunes del mes revisa el mes.',
          (('Plan de la semana', 'trabajos plan_week y planes guardados (WeeklyPlan)'),
           ('Resumen semanal', 'trabajos weekly_summary y resúmenes guardados (WeeklySummary)'),
           ('Revisión mensual', 'trabajos monthly_review y revisiones guardadas (MonthlyReview)')),
          ('STRATEGY_ENABLED', 'STRATEGY_PLAN_TIME', 'WEEKLY_SUMMARY_ENABLED', 'WEEKLY_SUMMARY_TIME', 'MONTHLY_REVIEW_ENABLED'),
          medir_plan),
    Flujo('ideas', 'Tus ideas',
          'Lo que mandas con el botón de captura (audio, nota, fotos): se transcribe, se entiende y llega a la mesa editorial.',
          (('Recibidas', 'capturas nuevas; procesadas o con error (Capture.error); las que siguen procesándose'),
           ('En la mesa editorial', 'ideas para un post que esperan un brief'),
           ('Con fecha', 'ideas con un día pedido; las que esperan que confirmes el día'),
           ('Preparadas en un post', 'ideas que el director usó en una pieza creada ese día'),
           ('Publicadas', 'ideas cuya pieza salió en LinkedIn ese día'),
           ('Descartadas', 'ideas sin usar: vacías o que pasaron 14 días sin encajar')),
          ('ninguno: siempre encendido',), medir_ideas),
    Flujo('retoque', 'Correcciones tuyas a un post',
          'Un comentario tuyo sobre una pieza lista: el director decide y la rehace (texto, imagen o ambos) antes de que salga.',
          (('Correcciones aplicadas', 'comentarios sobre una pieza: rehecha o sin cambios, o no aplicada con su motivo'),),
          ('EDITORIAL_REWORK_MIN_USD',), medir_retoque),
    Flujo('comentarios', 'Comentarios en referentes',
          'Lee los posts de tus referentes (y de compradores calentándose), propone un comentario, el líder lo revisa y sale.',
          (('Posts observados', 'posts nuevos leídos (ObservedPost) y lecturas observe fallidas'),
           ('Comentario propuesto', 'borradores encargados (propose_comment) y propuestas INT-03 creadas'),
           ('Revisado por el líder', 'propuestas aprobadas o descartadas por las reglas y el líder'),
           ('Publicado', 'comentarios escritos en LinkedIn y los intentos fallidos con su motivo'),
           ('Confirmado en LinkedIn', 'comentarios que LinkedIn mostró; los inciertos cuentan como fallos')),
          ('OPERATOR_AUTONOMY INT-03', 'OPERATOR_DAILY_PROPOSALS', 'OPERATOR_DAILY_LIMITS INT-03', 'LEAD_ENABLED'),
          medir_comentarios),
    Flujo('respuestas', 'Respuestas en tus posts',
          'Lee los comentarios de tus posts, propone una respuesta a los que la merecen, el líder la revisa y sale.',
          (('Comentarios leídos', 'comentarios nuevos (PostComment) y lecturas read_own_comments fallidas'),
           ('Respuesta propuesta', 'propuestas INT-04 aprobadas o descartadas; comentarios que siguen sin respuesta'),
           ('Publicada', 'respuestas escritas en LinkedIn y los intentos fallidos con su motivo')),
          ('REPLIES_ENABLED', 'OPERATOR_AUTONOMY INT-04', 'REPLIES_READ_CAPS', 'READ_WINDOW'), medir_respuestas),
    Flujo('red', 'Crecimiento de red',
          'Encuentra personas, las clasifica por rol y nivel de comprador, verifica a los compradores en la web y las sigue, '
          'invita y acepta.',
          (('Perfiles encontrados', 'personas descubiertas (Contact) y búsquedas discover_network fallidas'),
           ('Clasificados', 'personas clasificadas (network.classified), descartadas, y las que esperan clasificación'),
           ('Verificados en la web', 'verificaciones check_buyer_stages; compradores por verificar'),
           ('Seguidos', 'RED-01: propuestas, seguimientos escritos e intentos fallidos con su motivo'),
           ('Invitados', 'RED-02: propuestas, invitaciones enviadas e intentos fallidos con su motivo'),
           ('Aceptaron tu invitación', 'personas que pasaron a conexión; invitaciones sin respuesta'),
           ('Invitaciones recibidas aceptadas', 'RED-04: invitaciones de otros que aceptaste')),
          ('NETWORK_ENABLED', 'NETWORK_STAGE_CHECK', 'OPERATOR_AUTONOMY RED-01/RED-02/RED-04', 'OPERATOR_PROFILE_READ_DAILY_LIMIT',
           'OPERATOR_PROFILE_READ_RESEARCH_SHARE'), medir_red),
    Flujo('comprador', 'Comprador',
          'El recorrido de un comprador: calentamiento con comentarios, invitación, primer mensaje, seguimientos, su respuesta '
          'y la reunión. Los mensajes los envías tú.',
          (('Calentamiento', 'compradores elegidos e invitados tras calentarse (BuyerJourney)'),
           ('Primer mensaje', 'borradores del mensaje 1 preparados, descartados o fallidos; listos para que los envíes'),
           ('Secuencia (mensajes 2 a 4)', 'borradores de seguimiento; listos para que los envíes'),
           ('Respuesta a quien respondió', 'borradores de respuesta; listos para que los envíes'),
           ('Reunión', 'compradores que respondieron y reuniones agendadas; reservas sin emparejar')),
          ('BUYER_WARMUP_ENABLED', 'BUYER_FIRST_MESSAGE_ENABLED', 'BUYER_SEQUENCE_ENABLED', 'BUYER_REPLY_ENABLED', 'LEAD_ENABLED',
           'INBOX_ENABLED'), medir_comprador),
    Flujo('inbox', 'Mensajes privados',
          'Lee tu bandeja de LinkedIn y te avisa de las conversaciones que te tocan. El equipo no responde mensajes.',
          (('Bandeja leída', 'lecturas read_inbox completas o fallidas'),
           ('Te tocan a ti', 'conversaciones que esperan tu respuesta')),
          ('INBOX_ENABLED', 'INBOX_EVERY_MINUTES', 'INBOX_READ_CAPS'), medir_inbox),
    Flujo('referentes', 'Referentes',
          'Revisa cada mes a quién observas, busca referentes de tu industria, analiza sus posts y corre experimentos.',
          (('Revisión mensual', 'revisiones preparadas y publicadas; cambios que esperan tu respuesta'),
           ('Búsqueda de referentes de industria', 'búsquedas pedidas (a mano) y publicadas'),
           ('Análisis de posts', 'posts de referentes de industria leídos para el análisis'),
           ('Experimentos', 'avances advance_experiments; experimentos en curso')),
          ('REFERENTES_ANALISIS', 'REFERENTES_INDUSTRIA_TOPE_USD'), medir_referentes),
    Flujo('investigacion', 'Investigación en internet',
          'Busca y lee fuentes públicas con citas para los posts, tus ideas, los compradores, los referentes y tu perfil.',
          tuple((name, f'investigaciones con clave «{prefix}…»: hechas, omitidas, sin hallazgos o a medias')
                for prefix, name in RESEARCH_KINDS),
          ('WEB_RESEARCH_ENABLED', 'LIVE_PROVIDERS', 'WEB_RESEARCH_DAILY_LIMIT', 'NETWORK_STAGE_CHECKS_PER_DAY'),
          medir_investigacion, maquina=True),
    Flujo('perfil', 'Perfil y posicionamiento',
          'Propone cambios a tu perfil cada seis meses (y cada mes destacados y actividad) y estudia tu comunidad cada mes.',
          (('Propuesta de perfil', 'propuestas de perfil y de fotos y banner: listas, detenidas o fallidas'),
           ('Estudio de la comunidad', 'estudios mensuales empezados, terminados o con errores')),
          ('PROFILE_ENABLED',), medir_perfil),
    Flujo('salud', 'Salud de la máquina',
          'Lo que todo lo demás necesita: presupuesto de IA, cupos de lectura y escritura, cola de trabajos, cuentas y navegador.',
          (('Cola de trabajos', 'trabajos encolados, terminados y la cola actual; cada flujo juzga sus propios fallos'),),
          ('OPERATOR_AUTOPILOT', 'OPERATOR_PAUSED', 'AI_MONTHLY_LIMIT_USD', 'AI_DAILY_FUSE_USD', 'ALERT_QUEUE_STUCK_MINUTES'),
          medir_salud),
)
FLUJOS_POR_ID = {f.id: f for f in FLUJOS}


# --------------------------------------------------------------------------- the rules

def _stage_findings(res, ctx):
    found = []
    for e in res.etapas:
        if e.apagada:
            continue
        d = e.dia
        if d.fallaron >= fallos_min():
            reason = d.motivo()
            if d.avanzaron == 0:
                found.append(Hallazgo(ROJO, f'{e.nombre}: los {d.fallaron} intentos de las últimas 24 h fallaron ({reason}).',
                                      que_hacer(reason)))
            elif d.fallaron > fallos_pct() * (d.fallaron + d.avanzaron):
                found.append(Hallazgo(AMARILLO, f'{e.nombre}: {d.fallaron} intentos fallaron en 24 h, {d.avanzaron} salieron '
                                                f'({reason}).', que_hacer(reason)))
        if e.espera is not None and e.esperando and e.desde is not None:
            age = ctx.now - e.desde
            if age >= max(detenido_horas(), e.espera):
                found.append(Hallazgo(ROJO, f'{e.nombre}: {e.esperando} {e.cola} desde {_since(e.desde, ctx.now)}.'))
            elif age >= e.espera:
                found.append(Hallazgo(AMARILLO, f'{e.nombre}: {e.esperando} {e.cola} desde {_since(e.desde, ctx.now)}.'))
    return found


def juzgar(res, ctx):
    """The flow's single status, from its switch, its own findings and the stage rules (the module docstring)."""
    if res.apagado:
        res.estado = APAGADO
        return res
    res.hallazgos = res.hallazgos + _stage_findings(res, ctx)
    level = max((GRAVEDAD[h.nivel] for h in res.hallazgos), default=0)
    res.estado = {0: VERDE, 1: AMARILLO, 2: ROJO}[level]
    res.hallazgos.sort(key=lambda h: -GRAVEDAD[h.nivel])
    return res


def informe(now=None, member=None, flujos=None):
    """[Resultado] of every flow for the member (None: an installation without members), judged. Read only."""
    from . import miembros
    now = now or timezone.now()
    members = miembros.active_members()
    first = member is None or not members or members[0] is None or member.pk == members[0].pk
    ctx = Ctx(now, member, first, len(members) > 1)
    out = []
    for flujo in flujos or FLUJOS:
        if flujo.maquina and not first:
            continue
        try:
            res = flujo.medir(ctx)
        except Exception as exc:  # noqa: BLE001 - one broken measure never hides the other flows
            logger.warning('flujo_failed flujo=%s error=%s', flujo.id, type(exc).__name__, exc_info=True)
            res = Resultado(flujo, hallazgos=[Hallazgo(AMARILLO, 'No se pudo medir este flujo (error al leer su estado).',
                                                       'Revisa el registro del autopiloto.')])
        out.append(juzgar(res, ctx))
    return out


# --------------------------------------------------------------------------- the message

def _count_text(c, e):
    text = str(c.avanzaron)
    if e.entra and c.entraron != c.avanzaron:
        text += f' de {c.entraron} {e.entra}'
    if c.descartados:
        text += f', {c.descartados} {e.descarta}'
    if c.fallaron:
        text += f', {c.fallaron} fallaron'
    return text


def stage_line(e, now):
    if e.apagada:
        return f'  · {e.nombre}: apagada ({e.apagada})'
    line = f'  · {e.nombre}: hoy {_count_text(e.hoy, e)} · ayer {_count_text(e.ayer, e)}'
    if e.esperando:
        line += f' · {e.esperando} {e.cola}' + (f' desde {_since(e.desde, now)}' if e.desde is not None else '')
    return line


def _header(now, morning):
    from .operador import local_tz
    local = now.astimezone(local_tz())
    title = 'Buenos días: estado de los flujos' if morning else 'Estado de los flujos'
    return f'Barrio · *{title}* · {DIAS[local.weekday()]} {local:%d/%m} · {local:%H:%M}'


def verdict(results):
    counts = Counter(r.estado for r in results)
    if not counts[ROJO] and not counts[AMARILLO]:
        line = f'🟢 Todo funciona: {_plural(counts[VERDE], "flujo al día", "flujos al día")}.'
    else:
        parts = [f'🔴 {_plural(counts[ROJO], "detenido", "detenidos")}' if counts[ROJO] else '',
                 f'🟡 {counts[AMARILLO]} con atención' if counts[AMARILLO] else '',
                 f'🟢 {counts[VERDE]} funcionando' if counts[VERDE] else '']
        line = ' · '.join(p for p in parts if p)
    if counts[APAGADO]:
        line += f' · ⚪ {_plural(counts[APAGADO], "apagado", "apagados")}'
    return line


ORDEN = {ROJO: 0, AMARILLO: 1, VERDE: 2, APAGADO: 3}


def _moved(res):
    """Something entered or advanced today in one of the flow's stages (the machine's queue does not count)."""
    return res.flujo.id != 'salud' and any(e.hoy.entraron or e.hoy.avanzaron for e in res.etapas)


def texto(now, results, morning=False):
    """The phone layout: date and verdict, one line per flow; then the 🔴/🟡 flows by stage with the plain reason and
    what to do; then the 🟢 ones with their key number. Morning: the first block, what was prepared overnight, what is
    pending today and one line per problem."""
    ordered = sorted(results, key=lambda r: ORDEN[r.estado])
    blocks = [_header(now, morning) + '\n' + verdict(results),
              '\n'.join(f'{EMOJI[r.estado]} {r.flujo.nombre}' + (f' ({r.apagado})' if r.estado == APAGADO else '') for r in ordered)]
    bad = [r for r in ordered if r.estado in (ROJO, AMARILLO)]
    if morning:
        # Since midnight: each flow's own lines (the post of the day…), else its key number when something moved.
        overnight = [line for r in ordered if r.estado != APAGADO
                     for line in (r.anoche or ([f'{r.flujo.nombre}: {r.clave}'] if _moved(r) else []))]
        today = [line for r in results for line in r.para_hoy]
        if overnight:
            blocks.append('*Desde medianoche*\n' + '\n'.join(f'• {line}' for line in overnight))
        if today:
            blocks.append('*Pendiente para hoy*\n' + '\n'.join(f'• {line}' for line in today))
        if bad:
            lines = []
            for r in bad:
                first = r.hallazgos[0] if r.hallazgos else Hallazgo(r.estado, 'revisa el informe de la tarde')
                lines.append(f'{EMOJI[r.estado]} *{r.flujo.nombre}*: {first.texto}' + (f'\n   👉 {first.accion}' if first.accion else ''))
            blocks.append('*Lo que pide atención*\n' + '\n'.join(lines))
        return '\n\n'.join(blocks)
    for r in bad:
        lines = [f'{EMOJI[r.estado]} *{r.flujo.nombre}* — {PALABRA[r.estado]}']
        for h in r.hallazgos[:4]:
            lines.append(f'⚠️ {h.texto}')
        lines += [stage_line(e, now) for e in r.etapas]
        lines += [f'  · {note}' for note in r.notas]
        actions = list(dict.fromkeys(h.accion for h in r.hallazgos if h.accion))
        if actions:
            lines.append(f'👉 Qué hacer: {actions[0]}')
        blocks.append('\n'.join(lines))
    good = [r for r in ordered if r.estado == VERDE]
    if good:
        blocks.append('\n'.join(f'🟢 *{r.flujo.nombre}*: {r.clave or "al día"}' for r in good))
    return '\n\n'.join(blocks)


def text_for(now, member=None, morning=False):
    """The report's text for one member (por_miembro names her when there are several)."""
    return texto(now, informe(now, member), morning)


# --------------------------------------------------------------------------- when it goes (alertas_slack's watcher)

def enabled():
    """SLACK_ESTADO_FLUJOS (true): on by default; it goes out through the summaries channel when a webhook exists."""
    return _on('SLACK_ESTADO_FLUJOS', 'true')


def _hour(name, default):
    from .operador import _minutes
    raw = _setting(name, default).strip() or default
    try:
        minutes = _minutes(raw)
    except (TypeError, ValueError):
        minutes = _minutes(default)
    return min(max(minutes, 0), 23 * 60 + 59)


def evening_minutes():
    """SLACK_ESTADO_FLUJOS_HORA (18:00, local): the full report."""
    return _hour('SLACK_ESTADO_FLUJOS_HORA', '18:00')


def morning_minutes():
    """SLACK_ESTADO_FLUJOS_MANANA (08:45, local): the short morning report; empty or after the evening hour turns it off."""
    raw = _setting('SLACK_ESTADO_FLUJOS_MANANA', '08:45').strip()
    if not raw:
        return None
    minutes = _hour('SLACK_ESTADO_FLUJOS_MANANA', '08:45')
    return minutes if minutes < evening_minutes() else None


def slot(now):
    """'tarde' from the evening hour, 'manana' from the morning hour until the evening one, None before."""
    from .operador import local_tz
    local = now.astimezone(local_tz())
    minutes = local.hour * 60 + local.minute
    if minutes >= evening_minutes():
        return 'tarde'
    morning = morning_minutes()
    return 'manana' if morning is not None and minutes >= morning else None


# --------------------------------------------------------------------------- the document (the audit map)

def documented_names():
    """Every flow's name and its stages' names: what docs/funcionalidades/estado-de-flujos.md must cover."""
    return [(f.nombre, [name for name, _ in f.etapas]) for f in FLUJOS]

