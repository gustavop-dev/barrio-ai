"""Organizations and members (docs/plan-organizaciones.md, phase 1): the one way to know whose something is.

A member (models.Member) is one person of an organization (ProjectApp) with her own login and her own LinkedIn accounts:
the official API one that publishes (OFFICIAL) and the `directo` one that reads and acts (READERS). Every selector of
«the» account asks here instead of picking the newest or the first account of the whole database:

- member_of_user(user): the member a user is (None for the autopilot robot, a service user or anyone without one).
- member_of_account(account): whose account it is.
- default_member(): the member when the context does not say. While there is one active member it is that one; with
  several it raises MiembroRequerido instead of guessing, so a route that has no member yet stops with a clear reason
  (phases 2–5 give each route its member). Without any member at all (an installation before organizations, or a test
  that never made one) it is None, and then every account counts, exactly as before.
- member_for(user): the member a request or a job acts for: the user's own, else the default one.
  member_for_account(account): the same for a job that runs on one account.
- accounts(member, providers): a member's accounts; same_member(account): every account of that account's member.
- is_owner(user, account): only the member who owns an account opens its browser session or connects its credential.
  can_decide(user, account): the owner or the admin of the account's organization (referents and experiments, which the
  organization shares).

An account without a member (created before any member existed, or by a test) belongs to the only active member; once
there are several active members it belongs to nobody: no selector picks it and nobody owns it.

The first member: migration 0055 (and ensure_first_member, for bootstrap_local) makes the organization ProjectApp and its
first member, admin, with first_owner()'s user, and gives it every account without a member. Later members come from
`manage.py operador --usuario <admin> miembro` (save_member), never with LinkedIn accounts.

Phase 2, her LinkedIn rhythm (see the section below): policy_key(member) names the audit rows of a member's rhythm
('member' for the first member, so the state written before organizations is hers with no move; 'member:<id>' for the
others), active_members() the members a watcher or the autopilot goes through, mine(rows, member) narrows what her
accounts did, and setting(member, name, default) reads a variable of her rhythm: hers (Member.settings, set with
`manage.py operador ajustes` → save_settings, audited) else the .env's."""
import os

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q

OFFICIAL = ('linkedin', 'linkedin_fake')  # publishes the member's own posts (CONT-09)
READERS = ('fake', 'directo')  # reads LinkedIn and acts as the member (comments, network, inbox, analytics)
# Technical users of bootstrap_local: never a member, never the first owner.
ROBOTS = ('barrio-autopiloto', 'linkedin-service')
FIRST_ORGANIZATION = {'slug': 'projectapp', 'name': 'ProjectApp'}
FIRST_MEMBER = {'display_name': 'Gustavo', 'role': 'Fundador'}


class MiembroRequerido(ValueError):
    """No member can be named for this context (several active members and none given, or the user's member is
    inactive). A ValueError: views answer 400 with the reason and the autopilot's guards keep the rest of the tick."""


def _models():
    from .models import ConnectorAccount, Member, Organization
    return ConnectorAccount, Member, Organization


def exist():
    """Whether this installation has members at all. False: everything behaves as before organizations."""
    _, Member, _ = _models()
    return Member.objects.exists()


def member_of_user(user):
    """The member this user is, active or not; None for anonymous users and users without one (robots, services)."""
    if user is None or not getattr(user, 'is_authenticated', False):
        return None
    _, Member, _ = _models()
    return Member.objects.select_related('organization').filter(user_id=user.pk).first()


def default_member():
    """The only active member. None while there are no members at all (as before organizations). With several active
    members, or members but none active, MiembroRequerido: the caller must say whose."""
    _, Member, _ = _models()
    active = list(Member.objects.select_related('organization', 'user').filter(active=True)[:2])
    if len(active) == 1:
        return active[0]
    if not active and not Member.objects.exists():
        return None
    if active:
        raise MiembroRequerido('Hay varios miembros activos y esta operación no dice de cuál: hay que indicarlo.')
    raise MiembroRequerido('Ningún miembro de la organización está activo.')


def resolve(member=None):
    """The member given, else default_member() (which may be None or raise MiembroRequerido)."""
    return member if member is not None else default_member()


def member_for(user):
    """The member a request or a job acts for: the user's own (she has to be active), else the default member (the
    autopilot robot, service users and people without a member, while the context allows one)."""
    own = member_of_user(user)
    if own is None:
        return default_member()
    if not own.active:
        raise MiembroRequerido('Tu miembro está inactivo en la organización.')
    return own


def _sole(member):
    """Whether `member` is the only active member: then she also owns the accounts without a member."""
    _, Member, _ = _models()
    return member.active and not Member.objects.filter(active=True).exclude(pk=member.pk).exists()


def member_of_account(account):
    """Whose account it is: its member (even if inactive), or for an account without one the only active member. None
    when nobody can be named: no members at all, or an account without a member among several active ones."""
    if account.member_id:
        return account.member
    try:
        return default_member()
    except MiembroRequerido:
        return None


def member_for_account(account):
    """The member whose things an account's job reads or writes: member_of_account(), else default_member() (None with no
    members at all; MiembroRequerido for an account of nobody among several members, instead of reading someone else's)."""
    return member_of_account(account) or resolve()


def accounts(member=None, providers=None):
    """A member's accounts (with those without a member while she is the only active one), optionally of some providers.
    `member=None` means every account: an installation without members, or a scope with no member to name."""
    ConnectorAccount, _, _ = _models()
    rows = ConnectorAccount.objects.all()
    if member is not None:
        own = Q(member=member)
        if _sole(member):
            own |= Q(member__isnull=True)
        rows = rows.filter(own)
    if providers is not None:
        rows = rows.filter(provider__in=list(providers))
    return rows


def same_member(account):
    """Every account of the member this account belongs to, itself included: one person's pause stops only her own
    writes. With no member to name, every account (as before organizations)."""
    return accounts(member_of_account(account))


# --------------------------------------------------------------------------- who may

def legacy_owner_username():
    """The installation's human identity before organizations: REFERENTS_GUSTAVO_USERNAME (settings, else the
    environment, default 'gustavo'). Used only while there are no members, and by first_owner()."""
    return getattr(settings, 'REFERENTS_GUSTAVO_USERNAME', os.environ.get('REFERENTS_GUSTAVO_USERNAME', 'gustavo'))


def _human(user):
    return bool(user is not None and getattr(user, 'is_authenticated', False) and user.is_active)


def is_owner(user, account):
    """Whether `user` is the active member who owns this account. Without members at all, the legacy identity
    (legacy_owner_username), so an installation before organizations keeps working and nobody else gets in."""
    if not _human(user):
        return False
    owner = member_of_account(account)
    if owner is not None:
        return owner.active and owner.user_id == user.pk
    if exist():
        return False  # an account of nobody among several members
    return user.get_username() == legacy_owner_username()


def is_admin(user, organization=None):
    """Whether `user` is an active admin member (of `organization`, when given)."""
    member = member_of_user(user)
    return bool(_human(user) and member is not None and member.active and member.is_admin
                and (organization is None or member.organization_id == organization.pk))


def can_decide(user, account):
    """The owner of the account or the admin of its organization: decisions the organization shares (referents and their
    experiments). Never used to open a session or touch a credential: that is is_owner only."""
    if is_owner(user, account):
        return True
    owner = member_of_account(account)
    return owner is not None and is_admin(user, owner.organization)


# --------------------------------------------------------------------------- creating members

def first_owner():
    """The user who becomes the first member: REFERENTS_GUSTAVO_USERNAME's user if it exists and is active, else the first
    human superuser by date joined (robots and users without a usable password never count). Migration 0055 applies the
    same rule with the historical models."""
    User = get_user_model()
    user = User.objects.filter(username=legacy_owner_username(), is_active=True).exclude(username__in=ROBOTS).first()
    if user is not None:
        return user
    return (User.objects.filter(is_superuser=True, is_active=True).exclude(username__in=ROBOTS)
            .exclude(password__startswith='!').order_by('date_joined', 'pk').first())


@transaction.atomic
def ensure_first_member(actor=None):
    """An installation without members gets the organization ProjectApp and its first member (admin, «Fundador»), with
    first_owner()'s user, who adopts every account without a member. Nothing when a member already exists or nobody
    qualifies. Returns (member or None, created)."""
    ConnectorAccount, Member, Organization = _models()
    if Member.objects.exists():
        return None, False
    owner = first_owner()
    if owner is None:
        return None, False
    organization, _ = Organization.objects.get_or_create(slug=FIRST_ORGANIZATION['slug'],
                                                         defaults={'name': FIRST_ORGANIZATION['name']})
    member = Member.objects.create(organization=organization, user=owner, is_admin=True, role=FIRST_MEMBER['role'],
                                   display_name=(owner.get_full_name() or FIRST_MEMBER['display_name'])[:120])
    adopted = ConnectorAccount.objects.filter(member__isnull=True).update(member=member)
    content = adopt_content(member)
    from .jobs import audit
    audit(actor, 'organization.member_saved', member.pk, created=True, adopted=adopted, source='bootstrap',
          username=owner.get_username(), **({'content': content} if content else {}))
    from . import identidad, registro
    identidad.seed_first(member, actor)  # phase 3: the installation's identity and voice, as migration 0058 does
    registro.adopt(member)  # phase 6: the register of people, as migration 0063 does
    return member, True


@transaction.atomic
def save_member(admin, username, display_name, role='', *, make_admin=None, active=None, groups=()):
    """Add (or update) a member of the admin's organization with her own Django user; idempotent. A new user gets an
    unusable password (set it with `manage.py changepassword`). A new member starts inactive unless `active=True`: while
    phases 2–5 are not done, a second active member makes every route without a member stop (MiembroRequerido) instead
    of guessing. `make_admin`/`active` None keep what an existing member has; `groups` are only added. Never creates a
    LinkedIn account. Returns (member, user_created, member_created)."""
    ConnectorAccount, Member, _ = _models()
    acting = member_of_user(admin)
    if not is_admin_member(acting):
        raise PermissionError('Solo el administrador activo de una organización da de alta miembros.')
    username = (username or '').strip()
    display_name = (display_name or '').strip()
    role = (role or '').strip()
    try:
        UnicodeUsernameValidator()(username)
    except ValidationError:
        raise ValueError('Usuario inválido: letras, dígitos y @ . + - _') from None
    if not username or len(username) > 150:
        raise ValueError('Usuario inválido: entre 1 y 150 caracteres.')
    if username in ROBOTS:
        raise ValueError('Un usuario técnico no puede ser miembro.')
    if not display_name or len(display_name) > 120:
        raise ValueError('El nombre para mostrar va de 1 a 120 caracteres.')
    if len(role) > 120:
        raise ValueError('El rol tiene como mucho 120 caracteres.')
    wanted = list(dict.fromkeys(groups))
    found = list(Group.objects.filter(name__in=wanted))
    if len(found) != len(wanted):
        missing = sorted(set(wanted) - {g.name for g in found})
        raise ValueError(f'Grupo inexistente: {", ".join(missing)} (créalos con bootstrap_local).')
    User = get_user_model()
    user, user_created = User.objects.get_or_create(username=username)
    if user_created:
        user.set_unusable_password()
        user.save(update_fields=['password'])
    member = Member.objects.select_for_update().filter(user=user).first()
    if member is not None and member.organization_id != acting.organization_id:
        raise ValueError('Ese usuario ya es miembro de otra organización.')
    if member is not None and member.pk == acting.pk and (active is False or make_admin is False):
        raise ValueError('No puedes desactivarte ni quitarte el rol de administrador a ti mismo.')
    member_created = member is None
    if member_created:
        member = Member(organization=acting.organization, user=user, active=bool(active), is_admin=bool(make_admin))
    else:
        if active is not None:
            member.active = active
        if make_admin is not None:
            member.is_admin = make_admin
    member.display_name, member.role = display_name, role
    member.save()
    if found:
        user.groups.add(*found)
    from .jobs import audit
    audit(admin, 'organization.member_saved', member.pk, created=member_created, user_created=user_created,
          username=username, role=role, active=member.active, is_admin=member.is_admin, groups=wanted,
          accounts=ConnectorAccount.objects.filter(member=member).count())
    return member, user_created, member_created


def is_admin_member(member):
    return member is not None and member.active and member.is_admin


# --------------------------------------------------------------------------- her LinkedIn rhythm (phase 2)
# Each member is one LinkedIn member: her lock, spacing, day schedule, write caps, profile reads, invitation ramp and its
# health, notes, tier and provider blocks are hers (operador.py, red.py). What stays the whole machine's: the total stop
# (OPERATOR_PAUSED, OperatorControl), the AI budget, the navegador service's own caps (per account) and «one person, one
# invitation» (red.invitation_reserved, recipient_blocked).

LEGACY_KEY='member'  # the audit target of the rhythm before organizations


def first_member_id():
    """The oldest member of the installation (created_at, then id): she carries the rhythm the installation had before
    organizations. None without members."""
    _, Member, _ = _models()
    return Member.objects.order_by('created_at', 'pk').values_list('pk', flat=True).first()


def is_first(member):
    """Whether `member` is the first member, or there is none to name (an installation without members): her rhythm is
    the one of before organizations, under the same key and the same lock (operador.policy_lock)."""
    return member is None or member.pk == first_member_id()


def policy_key(member):
    """The audit target of a member's rhythm events (operator.schedule, network.ramp, network.notes_blocked…): 'member'
    for the first member and for an installation without members, so the state written before organizations (and a
    rollback to the code before this phase) keeps reading the same rows; 'member:<id>' for any later member."""
    return LEGACY_KEY if is_first(member) else f'member:{member.pk}'


def active_members():
    """Every active member, oldest first; [None] for an installation without members (one rhythm, as before)."""
    _, Member, _ = _models()
    members = list(Member.objects.filter(active=True).order_by('created_at', 'pk'))
    return members if members or Member.objects.exists() else [None]


def mine(rows, member, field='account'):
    """`rows` narrowed to what the member's accounts did (`field` names the account: 'account', 'proposal__account'…).
    `member=None` (an installation without members) leaves every row, as before organizations."""
    if member is None:
        return rows
    return rows.filter(**{f'{field}__in': accounts(member)})


# --------------------------------------------------------------------------- her content (phase 4)
# Pieces and their calendar, the weekly plan, the weekly summary, the monthly review, the audience, the team's questions,
# captures and the gallery carry their member (`member`, migration 0059; the rows of before organizations are the first
# member's, migration 0060). Her memory and orientation follow policy_key's rule instead (hechos.py, orientacion.py): the
# first member keeps the rows of before, untouched. What stays the organization's: the strategy template and pillars
# (Organization.profile), the course library and catalog, the AI budget, the referents and what their analysis learns,
# and the opportunities funnel.

def own(rows, member=None, field='member'):
    """`rows` of one member's content (`field` names the member: 'member', 'piece__member'…). `member=None`: the default
    member (MiembroRequerido among several active ones, never a guess); with no members at all, every row, as before
    organizations. The first member also owns rows without a member (written before migration 0060, or by a worker of
    the code before this phase during a deploy)."""
    member = resolve(member)
    if member is None:
        return rows
    mine = Q(**{field: member})
    if is_first(member):
        mine |= Q(**{f'{field}__isnull': True})
    return rows.filter(mine)


def content_member(member=None, account=None):
    """The member a new content row belongs to: `member`, else the owner of `account`, else the default member (None
    without members; MiembroRequerido among several active ones and nothing to say whose)."""
    if member is not None:
        return member
    if account is not None:
        return member_for_account(account)
    return resolve()


CONTENT_MODELS = ('EditorialPiece', 'WeeklyPlan', 'WeeklySummary', 'MonthlyReview', 'AudienceSnapshot', 'TeamQuestion',
                  'Capture', 'GalleryPhoto')


def adopt_content(member):
    """The installation's first member takes the content written before she existed (migration 0060's rule for a database
    that gets its first member later, through bootstrap_local). Returns how many rows moved."""
    from django.apps import apps
    moved = 0
    for name in CONTENT_MODELS:
        moved += apps.get_model('team_backend', name).objects.filter(member__isnull=True).update(member=member)
    moved += apps.get_model('team_backend', 'Orientation').objects.filter(pk=1, member__isnull=True).update(member=member)
    # Phase 5 (migration 0061's rule): her notices, her preferences of before and the opportunities she registered.
    moved += apps.get_model('team_backend', 'Notification').objects.filter(member__isnull=True).update(member=member)
    moved += apps.get_model('team_backend', 'OfficePreference').objects.filter(pk=1, user__isnull=True).update(user=member.user)
    Opportunity = apps.get_model('team_backend', 'Opportunity')
    moved += Opportunity.objects.filter(member__isnull=True).update(member=member)
    moved += Opportunity.objects.filter(origin_member__isnull=True).update(origin_member=member)
    return moved


def job_parts(member):
    """What a periodic job's deterministic id adds for her: nothing for the first member (and an installation without
    members), so a job queued before this phase keeps its id; ('member', id) for any other, so one member's job never
    deduplicates another's."""
    return () if is_first(member) else ('member', member.pk)


def job_params(member, params):
    """A content job's params for her: the first member's (and an installation without members) are the ones of before,
    without `member`, so a job queued before this phase keeps its params and its fingerprint; any other carries hers."""
    params = dict(params)
    if not is_first(member):
        params['member'] = str(member.pk)
    return params


def of_job(params):
    """Whose content a job prepares: params['member'], else the first member, who owns every content job without one
    (the encoding of job_params: what was queued before this phase was hers); None without members."""
    _, Member, _ = _models()
    if params.get('member'):
        return Member.objects.select_related('organization', 'user').get(pk=params['member'])
    first = first_member_id()
    return Member.objects.select_related('organization', 'user').get(pk=first) if first else None


def job_filter(member):
    """The JSON filter of her content jobs: {'params__member': id} for any member but the first, whose jobs carry no
    member (job_params); for the first, the jobs without one."""
    if is_first(member):
        return {'params__has_key': 'member'}, True  # (filter, exclude)
    return {'params__member': str(member.pk)}, False


def her_jobs(rows, member):
    """`rows` (Job) narrowed to her content jobs (job_params' encoding)."""
    if member is None:
        return rows
    condition, exclude = job_filter(member)
    return rows.exclude(**condition) if exclude else rows.filter(**condition)


# The variables of her rhythm a member may set apart from the .env, with the same names and formats (Member.settings).
# Phase 7 starts the CTO's free, long unused account low: OPERATOR_INVITE_RAMP_STAGES=5/25,8/40,10/50 with
# OPERATOR_INVITE_RAMP_START=0 (5 a day, up to 10; LI-09-V006-K01) and OPERATOR_AUTONOMY in «approval», without touching
# anyone else's.
MEMBER_SETTINGS = {
    'LINKEDIN_ACCOUNT_TIER': 'free, premium o sales_navigator',
    'LINKEDIN_INVITE_NOTE_MONTHLY_LIMIT': 'notas de invitación al mes (entero de 0 a 100)',
    'OPERATOR_DAILY_LIMITS': 'topes diarios por capacidad: CAP=n,CAP=n (las demás, las del .env)',
    'OPERATOR_WEEKLY_LIMITS': 'topes semanales por capacidad: CAP=n,CAP=n (las demás, las del .env)',
    'OPERATOR_INVITE_RAMP_STAGES': 'tres etapas día/semana, como mucho 8/40,16/80,20/100',
    'OPERATOR_INVITE_RAMP_START': 'etapa con la que empieza su rampa: 0, 1 o 2',
    'OPERATOR_PROFILE_READ_DAILY_LIMIT': 'lecturas de perfil al día (0 a 100)',
    'OPERATOR_AUTONOMY': 'CAP=auto|approval|off,… (las demás, las del .env)',
    'EDITORIAL_POST_TIME': 'hora del post del día, HH:MM dentro de OPERATOR_WINDOW',
}
# The .env's value when neither she nor the environment sets one (the defaults the modules already use).
SETTING_DEFAULTS = {'LINKEDIN_ACCOUNT_TIER': 'free', 'LINKEDIN_INVITE_NOTE_MONTHLY_LIMIT': '3', 'OPERATOR_DAILY_LIMITS': '',
                    'OPERATOR_WEEKLY_LIMITS': '', 'OPERATOR_INVITE_RAMP_STAGES': '8/40,16/80,20/100',
                    'OPERATOR_INVITE_RAMP_START': '1', 'OPERATOR_PROFILE_READ_DAILY_LIMIT': '80', 'OPERATOR_AUTONOMY': '',
                    'EDITORIAL_POST_TIME': '08:30'}


def setting(member, name, default):
    """One variable of her rhythm: hers when she set it (Member.settings), else the .env's, else `default`."""
    own = (member.settings or {}) if member is not None else {}
    if name in own:
        return own[name]
    return os.environ.get(name, default)


def setting_source(member, name):
    own = (member.settings or {}) if member is not None else {}
    return 'miembro' if name in own else 'entorno' if name in os.environ else 'por defecto'


def _pairs(value, name):
    items = []
    for item in filter(None, (x.strip() for x in value.split(','))):
        key, sep, rest = item.partition('=')
        if not sep or not key.strip() or not rest.strip():
            raise ValueError(f'{name}: «{item}» no tiene la forma CAP=valor.')
        items.append((key.strip(), rest.strip()))
    if not items:
        raise ValueError(f'{name}: vacío; usa --quitar para volver al valor del .env.')
    if len({k for k, _ in items}) != len(items):
        raise ValueError(f'{name}: una capacidad aparece dos veces.')
    return items


def validate_setting(name, value):
    """The value normalized as the .env would hold it, or ValueError with the reason (never a silent default)."""
    from datetime import time
    from . import operador, red
    from .models import ActionProposal
    if name not in MEMBER_SETTINGS:
        raise ValueError(f'Ajuste desconocido: {name}. Se pueden fijar: {", ".join(MEMBER_SETTINGS)}.')
    value = str(value).strip()
    if name == 'LINKEDIN_ACCOUNT_TIER':
        if value not in ('free', 'premium', 'sales_navigator'):
            raise ValueError('LINKEDIN_ACCOUNT_TIER: free, premium o sales_navigator.')
        return value
    if name in ('LINKEDIN_INVITE_NOTE_MONTHLY_LIMIT', 'OPERATOR_PROFILE_READ_DAILY_LIMIT'):
        if not value.isdigit() or int(value) > 100:
            raise ValueError(f'{name}: un entero de 0 a 100.')
        return str(int(value))
    if name in ('OPERATOR_DAILY_LIMITS', 'OPERATOR_WEEKLY_LIMITS'):
        pairs = _pairs(value, name)
        for cap, n in pairs:
            if cap not in operador.DEFAULT_LIMITS:
                raise ValueError(f'{name}: capacidad desconocida «{cap}» ({", ".join(operador.DEFAULT_LIMITS)}).')
            if not n.isdigit():
                raise ValueError(f'{name}: «{cap}={n}» necesita un entero.')
        return ','.join(f'{cap}={int(n)}' for cap, n in pairs)
    if name == 'OPERATOR_INVITE_RAMP_STAGES':
        stages = [x.strip() for x in value.split(',')]
        if len(stages) != len(red.RAMP_STAGES):
            raise ValueError('OPERATOR_INVITE_RAMP_STAGES: tres etapas día/semana, p. ej. 5/25,8/40,10/50.')
        out = []
        for (top_day, top_week), stage in zip(red.RAMP_STAGES, stages):
            day, sep, week = stage.partition('/')
            if not sep or not day.strip().isdigit() or not week.strip().isdigit():
                raise ValueError(f'OPERATOR_INVITE_RAMP_STAGES: «{stage}» no es día/semana.')
            if int(day) > top_day or int(week) > top_week:
                raise ValueError('OPERATOR_INVITE_RAMP_STAGES: solo puede bajar cada etapa (como mucho 8/40,16/80,20/100).')
            out.append(f'{int(day)}/{int(week)}')
        return ','.join(out)
    if name == 'OPERATOR_INVITE_RAMP_START':
        if value not in ('0', '1', '2'):
            raise ValueError('OPERATOR_INVITE_RAMP_START: 0, 1 o 2.')
        return value
    if name == 'OPERATOR_AUTONOMY':
        pairs = _pairs(value, name)
        for cap, mode in pairs:
            if cap not in ActionProposal.Capability.values:
                raise ValueError(f'OPERATOR_AUTONOMY: capacidad desconocida «{cap}».')
            if mode not in ('auto', 'approval', 'off'):
                raise ValueError(f'OPERATOR_AUTONOMY: «{cap}={mode}»; los modos son auto, approval y off.')
        return ','.join(f'{cap}={mode}' for cap, mode in pairs)
    hours, sep, minutes = value.partition(':')  # EDITORIAL_POST_TIME
    try:
        if not sep:
            raise ValueError
        at = time(int(hours), int(minutes))
    except ValueError:
        raise ValueError('EDITORIAL_POST_TIME: HH:MM.') from None
    if not operador.within_window(timezone_now_at(at)):
        raise ValueError('EDITORIAL_POST_TIME: queda fuera de OPERATOR_WINDOW.')
    return f'{at:%H:%M}'


def timezone_now_at(at):
    """Today at `at` in OPERATOR_TIMEZONE (to check an hour against the operator's window)."""
    from datetime import datetime
    from django.utils import timezone
    from . import operador
    return datetime.combine(timezone.now().astimezone(operador.local_tz()).date(), at, tzinfo=operador.local_tz())


def effective_settings(member):
    """[(name, value, source)] of every variable of her rhythm: hers, the .env's or the default."""
    return [(name, str(setting(member, name, SETTING_DEFAULTS[name])), setting_source(member, name)) for name in MEMBER_SETTINGS]


@transaction.atomic
def save_settings(admin, member, values=None, remove=()):
    """Set (or remove, back to the .env's) variables of a member's rhythm; only the active admin of her organization.
    Validated as a whole before anything changes; idempotent; audited with before and after. Returns (member, changed)."""
    _, Member, _ = _models()
    acting = member_of_user(admin)
    if not is_admin_member(acting) or acting.organization_id != member.organization_id:
        raise PermissionError('Solo el administrador activo de su organización cambia el ritmo de un miembro.')
    values = dict(values or {})
    remove = list(dict.fromkeys(remove))
    unknown = sorted((set(values) | set(remove)) - set(MEMBER_SETTINGS))
    if unknown:
        raise ValueError(f'Ajuste desconocido: {", ".join(unknown)}. Se pueden fijar: {", ".join(MEMBER_SETTINGS)}.')
    if set(values) & set(remove):
        raise ValueError('Un mismo ajuste no se fija y se quita a la vez.')
    clean = {name: validate_setting(name, value) for name, value in values.items()}
    member = Member.objects.select_for_update().get(pk=member.pk)
    before = dict(member.settings or {})
    after = {**before, **clean}
    for name in remove:
        after.pop(name, None)
    if after == before:
        return member, False
    member.settings = after
    member.save(update_fields=['settings'])
    from .jobs import audit
    audit(admin, 'organization.member_settings', member.pk, before=before, after=after)
    return member, True


def each_member(work, label):
    """Run a periodic content job for every active member (one [None] for an installation without members), each apart:
    the failure of one member's never stops another's. Returns the sum of what each returned; when every member that ran
    failed, the last error is raised (the autopilot reports it as before organizations); a failure next to a success is
    logged with whose it was."""
    import logging
    total, failed, error = 0, 0, None
    members = active_members()
    for member in members:
        try:
            total += work(member) or 0
        except Exception as exc:  # her job failing never stops the next member's
            failed += 1
            error = exc
            logging.getLogger('team_backend.autopilot').exception('%s_failed member=%s', label, getattr(member, 'pk', None))
    if error is not None and failed == len(members):
        raise error
    return total
