"""Organizaciones, phase 7: onboarding a member end to end, guided and safe (docs/plan-organizaciones.md «Fase 7»).

Three steps, each a `manage.py operador --usuario <admin> …` command, each idempotent and with a rehearsal (nothing
changes without --confirmar):

1. alta(): her Django user and her member, INACTIVE; the prudent settings of a free, long-unused LinkedIn account
   (PRUDENT); her minimal profile (name, role, relation to the organization) written by the admin while she has never
   saved her own; her voice provisional; optionally her `directo` account. It never sets a password, never connects a
   LinkedIn credential or session (only she does that) and never activates her. It ends with what is left by hand
   (checklist()).
2. activate(): only when every check passes (checks()): her official account connected, her `directo` account with a
   live, healthy session, a post hour apart from the others', her autonomy in approval for everything she writes while
   her voice is provisional, her invitation ramp at its low stage, a dry run of the autopilot and of every member route
   with her active that never raises MiembroRequerido (dry_run()), and enough free memory on the server.
3. deactivate(): she stops (her accounts are skipped by the autopilot, her queued jobs are cancelled, nothing approved of
   hers is written: operador.member_hold), her rows stay, and nothing of anybody else changes. Reversible: activate()
   again (with the same checks).

While she is inactive she can still see who she is, her profile and her voice, and connect her own LinkedIn
(alcance.DE_ALTA, miembros.is_owner(alta=True)); nothing else answers her, and the autopilot leaves her accounts alone."""
import logging
import os
from contextlib import ExitStack
from dataclasses import dataclass, field
from datetime import timedelta
from unittest import mock

from django.db import transaction
from django.utils import timezone

from . import autopiloto, editorial, identidad, miembros, operador, red, voz

logger = logging.getLogger('team_backend.alta')

GROUPS = ('operacion', 'revision')  # work her own account (fase 5: no manage_jobs, no administration)
# Every capability that writes on LinkedIn in her name (operador.DEFAULT_LIMITS): post, comment, reply, react, follow,
# invite, accept.
WRITE_CAPABILITIES = tuple(operador.DEFAULT_LIMITS)
HALVED = ('INT-03', 'INT-04', 'RED-01')  # comments, replies and follows: half the general daily caps
RAMP_STAGES = '5/25,8/40,10/50'
MIN_FREE_MB_DEFAULT = 400


def _general_daily(capability):
    """The .env's daily cap of a capability on a weekday (operador.DEFAULT_LIMITS under OPERATOR_DAILY_LIMITS), never a
    member's own value: the base a new member's caps are halved from."""
    return operador._parse_caps('OPERATOR_DAILY_LIMITS').get(capability, operador.DEFAULT_LIMITS[capability][0])


def _general_profile_reads():
    try:
        return max(0, int(os.environ.get('OPERATOR_PROFILE_READ_DAILY_LIMIT', '80')))
    except ValueError:
        return 80


def post_hour(organization, member=None):
    """A post hour one hour after the earliest active member's (Gustavo's 08:30 → 09:30), so two posts never meet; None
    when that falls outside OPERATOR_WINDOW (then she keeps the .env's and staggered_times moves her)."""
    from datetime import datetime
    from .models import Member
    first = Member.objects.filter(organization=organization, active=True).exclude(pk=getattr(member, 'pk', None)) \
        .order_by('created_at', 'pk').first()
    if first is None:
        return None
    at = editorial._configured_time(first)
    later = (datetime.combine(timezone.now().date(), at) + timedelta(hours=1)).time()
    try:
        return miembros.validate_setting('EDITORIAL_POST_TIME', f'{later:%H:%M}')
    except ValueError:
        return None


def prudent(organization, member=None):
    """[(VARIABLE, value, why)]: the settings of a free LinkedIn account that was barely used for a long time. Course:
    LI-09-V006-K01 and LI-10-M001-K03 (start with 5–10 invitations a day and go up over 3–4 weeks; «la cuenta se calienta
    antes de la campaña, no durante»)."""
    halved = ','.join(f'{cap}={max(1, _general_daily(cap) // 2)}' for cap in HALVED)
    autonomy = ','.join(f'{cap}=approval' for cap in WRITE_CAPABILITIES)
    out = [
        ('LINKEDIN_ACCOUNT_TIER', 'free', 'Su cuenta es gratuita: las notas de invitación y las búsquedas tienen los '
                                          'límites de una cuenta free.'),
        ('OPERATOR_INVITE_RAMP_STAGES', RAMP_STAGES, 'Rampa de cuenta dormida: 5 invitaciones al día (25 a la semana), '
                                                     'luego 8/40 y 10/50 (LI-09-V006-K01: arrancar con 5–10 al día).'),
        ('OPERATOR_INVITE_RAMP_START', '0', 'Empieza en la etapa más baja; sube sola con la aceptación sana en 3–4 '
                                            'semanas (LI-10-M001-K03).'),
        ('OPERATOR_DAILY_LIMITS', halved, 'Comentarios, respuestas y seguimientos a la mitad de los generales mientras la '
                                          'cuenta se calienta («antes de la campaña, no durante»).'),
        ('OPERATOR_PROFILE_READ_DAILY_LIMIT', str(max(1, _general_profile_reads() // 2)),
         'Las lecturas de perfil también se notan: a la mitad mientras la cuenta despierta.'),
        ('OPERATOR_AUTONOMY', autonomy, 'Todo lo que escribe en su nombre espera su aprobación mientras su voz es '
                                        'provisional; levantarla es decisión del administrador.'),
    ]
    hour = post_hour(organization, member)
    if hour:
        out.append(('EDITORIAL_POST_TIME', hour, 'Una hora después del post del primer miembro: dos posts de la empresa '
                                                 'nunca salen a la vez.'))
    return out


def role_preference_proposal(username):
    """What the share of untouched candidates could say for her (registro.taker, PEOPLE_ROLE_PREFERENCE): proposed, never
    applied (it lives in the .env and Gustavo has not confirmed it)."""
    return f'PEOPLE_ROLE_PREFERENCE=lider_tecnologia={username}'


# --------------------------------------------------------------------------- 1. alta

@dataclass
class Step:
    what: str
    state: str  # 'hecho', 'ya estaba', 'se dejó', 'propuesto'
    detail: str = ''


@dataclass
class Result:
    member: object
    steps: list = field(default_factory=list)
    confirmed: bool = False


def _organization_of(admin):
    acting = miembros.member_of_user(admin)
    if not miembros.is_admin_member(acting):
        raise PermissionError('Solo el administrador activo de una organización da de alta miembros.')
    return acting


def alta(admin, username, display_name, role, *, company_relation='', identity='', directo='', groups=GROUPS,
         confirm=False):
    """Prepare a member (see the module docstring). Without `confirm` everything runs in a transaction that is rolled
    back: the steps say what WOULD be done. Returns a Result."""
    acting = _organization_of(admin)
    from .models import Member
    existing = Member.objects.filter(user__username=(username or '').strip()).first()
    if existing is not None and existing.active:
        raise ValueError(f'«{username}» ya es un miembro activo: el alta solo prepara miembros inactivos (usa ajustes, '
                         'perfil o desactivar-miembro).')
    with transaction.atomic():
        result = _alta(admin, acting, username, display_name, role, company_relation, identity, directo, groups)
        result.confirmed = confirm
        if not confirm:
            transaction.set_rollback(True)
    return result


def _alta(admin, acting, username, display_name, role, company_relation, identity, directo, groups):
    from .jobs import audit
    from .models import ConnectorAccount
    member, user_created, member_created = miembros.save_member(admin, username, display_name, role, groups=groups)
    result = Result(member)
    steps = result.steps
    steps.append(Step('Usuario y miembro (inactivo)', 'hecho' if member_created else 'ya estaba',
                      f'{member.display_name} · {member.role or "sin rol"} · {member.organization.name}'
                      + (' · usuario nuevo sin contraseña' if user_created else '')))
    steps.append(Step(f'Grupos {", ".join(groups)}', 'hecho', 'trabaja su cuenta; sin manage_jobs ni administración'))
    if not member.user.is_active:  # deactivated with --sin-acceso and prepared again: she enters to reconnect
        member.user.is_active = True
        member.user.save(update_fields=['is_active'])
        steps.append(Step('Acceso', 'hecho', 'puede volver a entrar (solo a sus ajustes mientras siga inactiva)'))
    own = dict(member.settings or {})
    wanted, kept = {}, []
    for name, value, why in prudent(acting.organization, member):
        if name not in own:
            wanted[name] = value
            steps.append(Step(f'{name}={value}', 'hecho', why))
        elif own[name] == value:
            steps.append(Step(f'{name}={value}', 'ya estaba', why))
        else:
            kept.append(name)
            steps.append(Step(f'{name}={own[name]}', 'se dejó', f'lo fijó el administrador; el prudente sería {value}'))
    if wanted:
        member, _ = miembros.save_settings(admin, member, wanted)
    if identidad.may_start(admin, member):
        values = {'name': member.display_name}
        relation = company_relation.strip() or (f'Es {member.role} de {member.organization.name}.' if member.role else '')
        if relation:
            values['company_relation'] = relation
        if identity.strip():
            values['identity'] = identity.strip()
        _, revision = identidad.save_profile(admin, member=member, values=values, source='alta', on_behalf=True)
        steps.append(Step('Perfil mínimo (nombre y relación con la empresa)', 'hecho' if revision else 'ya estaba',
                          '; '.join(f'{k}: {v}' for k, v in values.items())))
    else:
        steps.append(Step('Perfil mínimo', 'se dejó', 'ella ya cambió su perfil: desde entonces solo ella lo cambia'))
    current = voz.current(member)
    steps.append(Step('Voz', 'ya estaba' if current.provisional else 'se dejó',
                      'provisional: sus borradores salen marcados y esperan su aprobación' if current.provisional else
                      f'tiene voz {current.kind}'))
    if directo:
        account = ConnectorAccount.objects.filter(provider=ConnectorAccount.Provider.DIRECTO, external_account_id=directo).first()
        if account is not None and account.member_id != member.pk:
            raise ValueError(f'La cuenta directo «{directo}» ya es de otro miembro (o de nadie): no se reasigna aquí.')
        if account is None:
            account = ConnectorAccount.objects.create(provider=ConnectorAccount.Provider.DIRECTO, external_account_id=directo,
                                                      member=member, label=f'LinkedIn directo · {member.display_name}')
            audit(admin, 'operator.account_registered', account.id, provider='directo', member=str(member.pk), source='alta')
            steps.append(Step(f'Cuenta directo «{directo}»', 'hecho', 'suya; su sesión la abre ella'))
        else:
            steps.append(Step(f'Cuenta directo «{directo}»', 'ya estaba', 'suya'))
    steps.append(Step(role_preference_proposal(member.user.get_username()), 'propuesto',
                      'reparto de candidatos sin dueño: los líderes de tecnología a ella; apagado hasta que el '
                      'administrador lo confirme y lo ponga en el .env'))
    audit(admin, 'organization.member_onboarded', str(member.pk), created=member_created, settings=sorted(wanted),
          kept=kept, directo=bool(directo))
    return result


def checklist(member):
    """[(done, what)]: what is left BY HAND for her to be activated, with its state now."""
    from .models import BrowserLogin, ConnectorAccount, LinkedInCredential
    username = member.user.get_username()
    official = miembros.accounts(member, miembros.OFFICIAL)
    readers = list(miembros.accounts(member, miembros.READERS))
    connected = LinkedInCredential.objects.filter(account__in=official, expires_at__gt=timezone.now()).exists()
    session = BrowserLogin.objects.filter(account__in=readers, state=BrowserLogin.State.CONNECTED).exists() or any(
        a.status == 'running' and not a.paused and not a.is_locked and a.last_checked_at for a in readers)
    directo = [a for a in readers if a.provider == ConnectorAccount.Provider.DIRECTO]
    return [
        (member.user.has_usable_password(),
         f'Su contraseña: `manage.py changepassword {username}` en el servidor; entrégasela en persona o por un canal '
         'privado (nunca por Slack ni en un archivo).'),
        (bool(directo),
         'Su cuenta del navegador: `operador --usuario <admin> alta-miembro … --cuenta-directo <id> --confirmar` '
         '(el id es el nombre de su carpeta en el servicio navegador).'),
        (connected, 'Ella entra en la PWA y conecta su LinkedIn oficial: Ajustes › LinkedIn › Conectar (OAuth).'),
        (session, 'Ella abre la sesión de su navegador: Ajustes › Máquina › «Conectar LinkedIn» (LINKEDIN_CONEXION_APP=true) '
                  'o, por SSH, `python -m navegador login <cuenta>` con ella escribiendo su clave.'),
        (bool(member.profile) and bool((member.profile or {}).get('identity')),
         'Ella completa su perfil: Ajustes › Mi perfil (cómo se presenta, temas que no domina).'),
        (None, '`OPERATOR_ALERT_WEBHOOK` del servidor debe ser un canal privado del primer miembro (recibe sus avisos y '
               'los de la organización, nunca los de ella): verificarlo en deploy/.env antes de activarla.'),
        (None, f'Decidir el reparto de candidatos: {role_preference_proposal(username)} (apagado por defecto).'),
        (None, f'Activarla: `operador --usuario <admin> activar-miembro --miembro {username}` (ensayo) y luego con '
               '--confirmar.'),
    ]


# --------------------------------------------------------------------------- 2. activation and its checks

@dataclass
class Check:
    code: str
    ok: bool
    label: str
    detail: str = ''


def _official(member, now):
    from .models import LinkedInCredential
    accounts = list(miembros.accounts(member, miembros.OFFICIAL))
    if not accounts:
        return Check('cuenta_oficial', False, 'Cuenta oficial conectada', 'no conectó su LinkedIn oficial (Ajustes › LinkedIn)')
    credential = LinkedInCredential.objects.filter(account__in=accounts).order_by('-connected_at').first()
    if credential is None or credential.expires_at <= now:
        return Check('cuenta_oficial', False, 'Cuenta oficial conectada', 'sin credencial vigente: que vuelva a conectar')
    paused = [a for a in accounts if a.paused]
    if paused:
        return Check('cuenta_oficial', False, 'Cuenta oficial conectada', f'en pausa: {paused[0].paused_reason}')
    return Check('cuenta_oficial', True, 'Cuenta oficial conectada', credential.member_urn)


def _reader(member, live):
    from .connectors import ConnectorError
    accounts = list(miembros.accounts(member, miembros.READERS))
    if not accounts:
        return Check('cuenta_directo', False, 'Cuenta directo con sesión sana', 'sin cuenta directo (alta-miembro --cuenta-directo)')
    account = accounts[0]
    if live:
        try:
            account = operador.check_account(account)
        except ConnectorError as exc:
            return Check('cuenta_directo', False, 'Cuenta directo con sesión sana', f'el servicio no la ve sana: {exc}')
    if account.paused or account.is_locked or account.status != 'running':
        return Check('cuenta_directo', False, 'Cuenta directo con sesión sana',
                     account.paused_reason or f'estado {account.status}{" (bloqueada)" if account.is_locked else ""}')
    return Check('cuenta_directo', True, 'Cuenta directo con sesión sana', f'{account.external_account_id}: activa')


def _post_hour(member):
    from .models import Member
    try:
        mine = editorial._configured_time(member)
    except ValueError as exc:
        return Check('hora_post', False, 'Hora de publicación propia', str(exc))
    step = editorial.post_stagger()
    minutes = mine.hour * 60 + mine.minute
    for other in Member.objects.filter(organization=member.organization, active=True).exclude(pk=member.pk):
        theirs = editorial.post_time(other)
        if abs(theirs.hour * 60 + theirs.minute - minutes) < step:
            return Check('hora_post', False, 'Hora de publicación propia',
                         f'{mine:%H:%M} choca con la de {other.display_name} ({theirs:%H:%M}); fija otra con '
                         f'`ajustes --fijar EDITORIAL_POST_TIME=HH:MM`')
    return Check('hora_post', True, 'Hora de publicación propia', f'{mine:%H:%M}')


def _autonomy(member):
    if not voz.current(member).provisional:
        return Check('autonomia', True, 'Autonomía en aprobación mientras su voz es provisional',
                     'su voz ya está confirmada: la autonomía la decide el administrador')
    loose = [cap for cap in WRITE_CAPABILITIES if autopiloto._configured(cap, member) == 'auto']
    if loose:
        return Check('autonomia', False, 'Autonomía en aprobación mientras su voz es provisional',
                     f'en auto: {", ".join(loose)} (fija OPERATOR_AUTONOMY con approval para todas)')
    return Check('autonomia', True, 'Autonomía en aprobación mientras su voz es provisional',
                 'publicar, comentar, responder, reaccionar, seguir, invitar y aceptar esperan su aprobación')


def _ramp(member, now):
    state = red.ramp_state(now, member)
    try:
        daily, weekly = red.ramp_limits(None, now, member)
    except ValueError as exc:
        return Check('rampa', False, 'Rampa de invitaciones en la etapa baja', str(exc))
    if state.get('stage') != 0 or daily > 10:
        return Check('rampa', False, 'Rampa de invitaciones en la etapa baja',
                     f'etapa {state.get("stage")}, {daily} al día: fija OPERATOR_INVITE_RAMP_STAGES={RAMP_STAGES} y '
                     'OPERATOR_INVITE_RAMP_START=0')
    return Check('rampa', True, 'Rampa de invitaciones en la etapa baja', f'etapa 0: {daily} al día, {weekly} a la semana')


def free_memory_mb(path=None):
    """MemAvailable of the server in MB (from /proc/meminfo: inside a container it is the host's), or None if unreadable."""
    path = path or os.environ.get('SERVER_MEMINFO', '/proc/meminfo')
    try:
        with open(path, encoding='ascii') as handle:
            for line in handle:
                if line.startswith('MemAvailable:'):
                    return int(line.split()[1]) // 1024
    except (OSError, ValueError, IndexError):
        return None
    return None


def min_free_mb():
    try:
        return max(0, int(os.environ.get('MEMBER_ACTIVATION_MIN_FREE_MB', str(MIN_FREE_MB_DEFAULT))))
    except ValueError:
        return MIN_FREE_MB_DEFAULT


def _memory():
    free, needed = free_memory_mb(), min_free_mb()
    label = 'Memoria libre del servidor con su navegador abierto'
    if free is None:
        return Check('memoria', False, label, 'no se pudo leer MemAvailable (SERVER_MEMINFO)')
    if free < needed:
        return Check('memoria', False, label, f'{free} MB libres, hacen falta {needed} (MEMBER_ACTIVATION_MIN_FREE_MB); '
                                              'ver deploy/README.md «Cuándo ampliar el servidor»')
    return Check('memoria', True, label, f'{free} MB libres (mínimo {needed})')


def _access(member):
    user = member.user
    if not user.is_active or not user.has_usable_password():
        return Check('acceso', False, 'Puede entrar', f'sin contraseña: `manage.py changepassword {user.get_username()}`')
    return Check('acceso', True, 'Puede entrar', user.get_username())


def checks(member, now=None, live=True):
    """Every check activation asks for, in order. `live`: the `directo` session is asked to the browser service now
    (operador.check_account, which opens her browser) and the dry run goes through the autopilot and the routes."""
    now = now or timezone.now()
    out = [_access(member), _official(member, now), _reader(member, live), _post_hour(member), _autonomy(member),
           _ramp(member, now)]
    problems = dry_run(member, now) if live else []
    out.append(Check('sin_miembro_requerido', not problems, 'Ninguna ruta ni trabajo pide «el» miembro con ella activa',
                     '; '.join(problems[:6]) if problems else 'pasada en seco del autopiloto, de sus trabajos y de las rutas'))
    out.append(_memory())  # after the session check, which opened her browser
    return out


class _Captured(logging.Handler):
    def __init__(self):
        super().__init__(logging.WARNING)
        self.found = []

    def emit(self, record):
        text = record.getMessage()
        if record.exc_info and record.exc_info[1] is not None:
            text += f' {type(record.exc_info[1]).__name__}: {record.exc_info[1]}'
        if 'MiembroRequerido' in text or 'no dice de cuál' in text:
            self.found.append(f'{record.name}: {text[:200]}')


class _Offline(RuntimeError):
    """Raised by anything that would leave the machine during a dry run."""


REQUIRED = ('no dice de cuál', 'Ningún miembro de la organización está activo', 'Tu miembro está inactivo')


def dry_run(member, now=None):
    """A dry run with her ACTIVE, rolled back: one autopilot tick, the jobs it queued for her or her accounts, and every
    member route (GET, without an id) as each active member. Every way out of the machine is blocked (HTTP, the course
    providers, files). Returns the places where «the» member was asked for (MiembroRequerido) or a route failed."""
    from django.conf import settings
    from django.test import Client
    from . import alcance
    from .models import Job, Member
    now = now or timezone.now()
    problems = []
    handler = _Captured()
    root = logging.getLogger()

    def offline(*args, **kwargs):
        raise _Offline('pasada en seco: sin salida')

    with ExitStack() as stack, transaction.atomic():
        for target in ('httpx.Client.send', 'httpx.AsyncClient.send', 'requests.Session.send',
                       'urllib.request.urlopen', 'knowledge.providers.claude', 'django.core.files.storage.Storage.save'):
            try:
                stack.enter_context(mock.patch(target, side_effect=offline))
            except (AttributeError, ModuleNotFoundError, ImportError):
                continue
        root.addHandler(handler)
        stack.callback(root.removeHandler, handler)
        Member.objects.filter(pk=member.pk).update(active=True)
        type(member.user).objects.filter(pk=member.user_id).update(is_active=True)
        robot = _robot()
        before = set(Job.objects.values_list('pk', flat=True))
        try:
            report = autopiloto.tick(robot, now)
        except miembros.MiembroRequerido as exc:
            problems.append(f'autopiloto: {exc}')
            report = {}
        except Exception as exc:  # anything else blocked offline is expected; the tick guards its parts itself
            logger.info('dry_run_tick %s', type(exc).__name__)
            report = {}
        problems += [f'autopiloto.{k}' for k, v in report.items() if v == 'MiembroRequerido']
        mine = miembros.accounts(member).values_list('pk', flat=True)
        for job in Job.objects.exclude(pk__in=before).order_by('created_at'):
            params = job.params or {}
            if params.get('member') != str(member.pk) and str(params.get('account')) not in {str(pk) for pk in mine}:
                continue
            try:
                with transaction.atomic():
                    operador.run_job(job)
            except miembros.MiembroRequerido as exc:
                problems.append(f'trabajo {job.kind}: {exc}')
            except Exception:
                continue  # blocked offline, or a provider it needs: not a question of whose
        hosts = [h for h in settings.ALLOWED_HOSTS if h not in ('*',) and not h.startswith('.')] or ['localhost']
        for other in Member.objects.filter(organization=member.organization).filter(active=True).select_related('user'):
            client = Client(HTTP_HOST=hosts[0])
            client.force_login(other.user)
            for route, (kind, _) in alcance.RUTAS.items():
                if '<' in route or (kind.get('GET') if isinstance(kind, dict) else kind) != alcance.MIEMBRO:
                    continue
                response = client.get(f'/api/v1/{route}', secure=True)
                body = response.content[:2000].decode('utf-8', 'replace')
                if response.status_code == 400 and any(text in body for text in REQUIRED):
                    problems.append(f'GET /{route} ({other.display_name}): pide «el» miembro')
                elif response.status_code >= 500:
                    problems.append(f'GET /{route} ({other.display_name}): HTTP {response.status_code}')
        problems += handler.found
        transaction.set_rollback(True)
    return list(dict.fromkeys(problems))


def _robot():
    """The autopilot's user (bootstrap_local's robot), or any active superuser to run the tick as."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return (User.objects.filter(username='barrio-autopiloto', is_active=True).first()
            or User.objects.filter(is_superuser=True, is_active=True).order_by('pk').first())


def activate(admin, member, now=None, confirm=False, live=True):
    """(activated, checks). Only with every check passing and `confirm`. Her Django user is enabled again if a
    deactivation had disabled it."""
    acting = _organization_of(admin)
    if acting.organization_id != member.organization_id:
        raise PermissionError('Solo el administrador de su organización la activa.')
    if member.active:
        raise ValueError(f'{member.display_name} ya está activa.')
    blocked = not member.user.is_active
    member.user.is_active = True  # her access comes back with her (deactivate --sin-acceso): checked as if it had
    found = checks(member, now, live)
    if not confirm or not all(c.ok for c in found):
        member.user.is_active = not blocked
        return False, found
    from .jobs import audit
    with transaction.atomic():
        if blocked:
            member.user.save(update_fields=['is_active'])
        miembros.save_member(admin, member.user.get_username(), member.display_name, member.role, active=True)
        audit(admin, 'organization.member_activated', str(member.pk), checks=[c.code for c in found], access_restored=blocked)
    return True, found


# --------------------------------------------------------------------------- 3. deactivation

def her_jobs(member):
    """Her queued jobs: of her user, for her content (params['member']) or on her accounts (params['account'])."""
    from django.db.models import Q
    from .models import Job
    accounts = [str(pk) for pk in miembros.accounts(member).values_list('pk', flat=True)]
    return Job.objects.filter(state=Job.State.QUEUED).filter(
        Q(owner_id=member.user_id) | (Q(params__has_key='member') & Q(params__member=str(member.pk)))
        | (Q(params__has_key='account') & Q(params__account__in=accounts)))


def deactivate(admin, member, reason, confirm=False, block_access=False):
    """Stop a member (see the module docstring). Returns {'jobs': n cancelled, 'proposals': n waiting, 'access': bool}."""
    from .jobs import audit
    from .models import ActionProposal, Job
    acting = _organization_of(admin)
    if acting.organization_id != member.organization_id:
        raise PermissionError('Solo el administrador de su organización la desactiva.')
    if acting.pk == member.pk:
        raise ValueError('No puedes desactivarte a ti mismo.')
    reason = (reason or '').strip()
    if not reason:
        raise ValueError('Indica el motivo (--motivo).')
    jobs = her_jobs(member)
    waiting = ActionProposal.objects.filter(account__in=miembros.accounts(member), state__in=['proposed', 'approved'],
                                            execution__isnull=True).count()
    summary = {'jobs': jobs.count(), 'proposals': waiting, 'access': not block_access, 'was_active': member.active}
    if not confirm:
        return summary
    with transaction.atomic():
        miembros.save_member(admin, member.user.get_username(), member.display_name, member.role, active=False)
        jobs.update(state=Job.State.CANCELLED, result_status='inactive_member', error=operador.INACTIVE_HOLD,
                    finished_at=timezone.now())
        if block_access and member.user.is_active:
            member.user.is_active = False
            member.user.save(update_fields=['is_active'])
        audit(admin, 'organization.member_deactivated', str(member.pk), reason=reason[:500], **summary)
    return summary
