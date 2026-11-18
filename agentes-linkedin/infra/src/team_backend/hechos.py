"""Her confirmed memory (organizaciones, phase 4): what the team knows about each member, and what is the company's.

Facts live in the legacy `memory` table (knowledge.memory), whose schema stays frozen; whose fact it is goes in its key:
- the first member's (and an installation's without members): the keys of before, without a prefix. Gustavo's memory,
  as it was, needs no move (miembros.policy_key's rule);
- any other member's: 'm:<member uuid>:<key>';
- the organization's: 'o:<organization uuid>:<key>'. A company fact (a confirmed ProjectApp case, a figure of the
  company) is available to every member of the organization.

Everything a member confirms (an answer in Tu turno, a fact from her capture, a note or a correction) is hers. Making a
fact the company's is an explicit act of the organization's active admin (share): her current value is copied into the
organization's key, audited (memory.shared_with_organization), and stays hers too; unshare withdraws the company's copy
(a confirmed tombstone, its history kept). One member's facts never reach another member's texts, images or decisions:
blocks(member) gives her own facts plus her organization's, never anyone else's."""
from knowledge import memory

from . import miembros

COMPANY_PREFIX = 'empresa.'  # how a company fact's key reads in a prompt: «empresa.<key>», never as hers


def legacy(member=None):
    """Whether `member` (the default one when None) keeps the memory of before: the first member, or no members at all."""
    return miembros.is_first(miembros.resolve(member))


def scope(member=None):
    """The key prefix of her facts: '' for the first member (and without members), 'm:<id>:' for any other."""
    member = miembros.resolve(member)
    return '' if miembros.is_first(member) else f'm:{member.pk}:'


def organization_scope(organization):
    return f'o:{organization.pk}:'


def key(member, plain):
    """The stored key of her fact `plain`."""
    return scope(member) + plain


def latest(member=None, confirmed_only=True):
    """Her latest version of each fact (keys without their prefix)."""
    return memory.latest(confirmed_only, scope(member))


def current_version(member, plain):
    return memory.current_version('user', key(member, plain))


def confirmed_history(member, plain):
    return memory.confirmed_history('user', key(member, plain))


def set_fact(member, plain, value, author, evidence, on_write=None):
    """Human-only: her fact, proposed and confirmed in one step (an answer, a correction or a withdrawal)."""
    return memory.set_fact(key(member, plain), value, author, evidence, on_write=on_write)


def _organization(member):
    member = miembros.resolve(member)
    return member.organization if member is not None else None


def company_rows(organization):
    """The organization's confirmed facts (keys without their prefix), withdrawn ones included."""
    if organization is None:
        return []
    return memory.latest(True, organization_scope(organization))


def confirmed_blocks(member=None):
    """(public_facts, private_guidance) of her confirmed memory plus her organization's company facts (their key reads
    «empresa.<key>»). Her own wins when she has the same key. For Gustavo before any company fact: exactly the memory of
    before. `member=None`: the default member (MiembroRequerido among several)."""
    public, private = memory.confirmed_blocks(scope(member))
    mine = {item['key'] for item in public + private}
    for row in company_rows(_organization(member)):
        value = row['value']
        if row['key'] in mine or memory.retired(value):
            continue
        base = {'key': COMPANY_PREFIX + row['key'], 'version': row['version']}
        if memory.publishable(value):
            fact = value['texto'] if isinstance(value.get('texto'), str) else {k: v for k, v in value.items() if k != 'uso_publico'}
            public.append(dict(base, fact=fact))
        else:
            private.append(dict(base, guidance=value))
    return public, private


def with_company(member=None):
    """Her latest confirmed facts plus her organization's (keys without prefix; hers win): what a reader of facts such as
    projectapp.case_facts sees."""
    own = latest(member)
    seen = {row['key'] for row in own}
    return own + [row for row in company_rows(_organization(member)) if row['key'] not in seen]


def share(admin, member, plain):
    """The organization's active admin makes her fact `plain` a company fact: every member of the organization may use it
    from now on. Audited; idempotent (the same value again changes nothing). Returns the company row's version."""
    from .jobs import audit
    member = miembros.resolve(member)
    if member is None or not miembros.is_admin(admin, member.organization):
        raise PermissionError('Solo el administrador activo de la organización comparte un hecho con la empresa.')
    row = next((r for r in latest(member) if r['key'] == plain), None)
    if row is None or memory.retired(row['value']):
        raise ValueError('Ese dato no está en la memoria confirmada de ese miembro.')
    stored = organization_scope(member.organization) + plain
    current = next((r for r in company_rows(member.organization) if r['key'] == plain), None)
    if current is not None and current['value'] == row['value']:
        return current['version']
    result = memory.set_fact(stored, row['value'], f'user:{admin.pk}',
                             f'Compartido con la organización desde el hecho {plain} v{row["version"]} de {member.pk}')
    audit(admin, 'memory.shared_with_organization', plain, member=str(member.pk), version=result['version'])
    return result['version']


def unshare(admin, organization, plain, reason=''):
    """The admin withdraws a company fact: no member uses it any more (a confirmed tombstone; its history stays)."""
    from .jobs import audit
    if not miembros.is_admin(admin, organization):
        raise PermissionError('Solo el administrador activo de la organización retira un hecho de la empresa.')
    current = next((r for r in company_rows(organization) if r['key'] == plain), None)
    if current is None or memory.retired(current['value']):
        raise ValueError('Ese dato no es un hecho de la empresa.')
    result = memory.set_fact(organization_scope(organization) + plain, {'retirado': True, 'motivo': (reason or '')[:500]},
                             f'user:{admin.pk}', 'El administrador lo retiró de la empresa')
    audit(admin, 'memory.unshared_from_organization', plain, version=result['version'])
    return result['version']
