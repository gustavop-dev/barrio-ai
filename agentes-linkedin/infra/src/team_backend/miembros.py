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
`manage.py operador --usuario <admin> miembro` (save_member), never with LinkedIn accounts."""
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
    from .jobs import audit
    audit(actor, 'organization.member_saved', member.pk, created=True, adopted=adopted, source='bootstrap',
          username=owner.get_username())
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
