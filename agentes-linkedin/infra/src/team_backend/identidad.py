"""Identity out of the code (docs/plan-organizaciones.md, phase 3): who the team writes as, read from the database.

Two profiles, each a JSON on its row, validated and audited (every change leaves an IdentityRevision with who, when,
which fields and the whole profile before and after), editable without a deploy (`manage.py operador perfil`):

- the organization's (Organization.profile, ORGANIZATION_FIELDS): what it is and sells, shared because the goal is the
  same: the positioning version and status, language and market, pillars, services, offer, confirmed cases, modalities
  and the neighborhood of each, what it does not want. Only its active admin changes it.
- a member's (Member.profile, MEMBER_FIELDS): who she is: the name the team writes, how she presents herself
  (`identity`), her relation to the organization (`company_relation`: «Fundó y lidera ProjectApp…» or «Es CTO de
  ProjectApp…»), her limits (topics she does not master), whether the personal startup modality is hers, her own words
  for a modality and her profile brand. Only she changes it. Her voice is apart (voz.py, VoiceDocument).

of(member) is the one way to know who: it gives an Identity with both profiles, the name, its key token and the
`{nombre}` / `{decisor}` / `{alias}` rendering of every prompt template. Whose identity, by the same rule as her
LinkedIn rhythm (miembros.policy_key):
- no members at all (an installation before organizations, a test that never made one): the initial identity
  (recursos/identidad-inicial.json, ProjectApp and its founder), exactly the texts the code had before this phase;
- the first member: her stored profile; while it is empty, the initial one (she is that installation's person);
- any other member: her stored profile over neutral defaults, never the initial one and never another member's;
- several active members and no member named: miembros.MiembroRequerido (never a default identity).

The initial identity is data: migration 0058 copies it into ProjectApp's and its first member's rows, and
ensure_first_member does the same for an installation that gets its first member later (bootstrap_local).

Memory and orientation (phase 4): facts(), blocks() and orientation() give each member her own (hechos.py, orientacion.py):
the first member (or an installation without members) what they gave before, any other member hers. Never another
member's facts, private guidance or orientation; company facts, shared by the admin, are every member's."""
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path

from django.db import transaction

from . import miembros

SEED_PATH = Path(__file__).resolve().parent / 'recursos' / 'identidad-inicial.json'

# How a template names her: {nombre} her name, {decisor} who took a quoted decision of the organization (her name when
# she is the installation's first person, who took them; «la organización» for anyone else), {alias} the token of a
# key that carries a person (`hechos_publicos_de_{alias}`). Only {nombre} may appear in the organization's texts.
PLACEHOLDERS = ('{nombre}', '{decisor}', '{alias}')
ORGANIZATION_DECISOR = 'la organización'
# The token persisted keys were named with before organizations (brief['questions_for_…'], the reply's decision
# 'ask_…', a review's 'from_…'): stored rows and the PWA read those names, so they stay; keyed()/unkeyed() show each
# member her own token in a schema and bring her answer back to the stored names.
STORED_TOKEN = 'gustavo'

# A member with nothing of her own yet (the CTO before phase 7): her display name and rules without anybody's identity.
NEUTRAL_MEMBER = {
    'identity': '', 'company_relation': '',
    'limits': ('humo y promesas; temas que no domina; experiencias, clientes, cifras o resultados inventados; pitch '
               'agresivo; datos privados de cualquier persona'),
    'personal_startups': False, 'purposes': {}, 'brand_version': '',
}

ORGANIZATION_FIELDS = {
    'version': 'versión del posicionamiento (p. ej. posicionamiento-v3); la leen los experimentos y los estudios',
    'date': 'fecha de esa versión, AAAA-MM-DD',
    'status': 'estado del posicionamiento; puede nombrar al miembro con {nombre}',
    'language': 'idioma y mercado en que se publica',
    'pillars': 'pilares editoriales: JSON {clave: texto} con las claves de siempre',
    'not_wanted': 'a quién no se busca',
    'location': 'dónde se construye el barrio',
    'services': 'servicios que vende: JSON {clave: {label, source, terms}} con las claves de siempre',
    'offer': 'oferta y precios aproximados: JSON {equipo_dedicado, proyecto, argumento}',
    'cases': 'casos confirmados por segmento: JSON {segmento: texto}',
    'modalities': 'modalidades: JSON {modalidad: {purpose, neighborhood}}; purpose puede usar {nombre}',
    'neighborhood_before': 'barrio de antes del comprador de ProjectApp: JSON {modalidad: texto}',
}
MEMBER_FIELDS = {
    'name': 'cómo la nombra el equipo en sus textos y en lo que se dibuja (infografías, carruseles)',
    'identity': 'cómo se presenta: una o dos frases',
    'company_relation': 'su relación con la organización (p. ej. «Es CTO de ProjectApp, …»)',
    'limits': 'límites de lo que se escribe en su nombre (temas que no domina, lo que nunca se inventa)',
    'personal_startups': 'si le aplica la modalidad de trabajo personal en startups: si o no',
    'purposes': 'sus propias palabras para el propósito de una modalidad: JSON {modalidad: texto}',
    'brand_version': 'versión de la marca de su perfil de LinkedIn',
}
TEXT_MAX = 2000


class IdentidadInvalida(ValueError):
    """A profile value that fails validation: nothing is saved."""


@lru_cache(maxsize=1)
def _seed():
    return json.loads(SEED_PATH.read_text(encoding='utf-8'))


def initial():
    """A copy of the initial identity: {'organization': {...}, 'member': {...}, 'voice': {...}}."""
    return json.loads(json.dumps({k: v for k, v in _seed().items() if k != '_'}))


def alias_of(name):
    """The key token of a name: lowercase, no accents, words joined by «_» ('Gustavo' -> 'gustavo')."""
    plain = unicodedata.normalize('NFKD', name or '').encode('ascii', 'ignore').decode().lower()
    return '_'.join(re.findall(r'[a-z0-9]+', plain)) or 'miembro'


@dataclass(frozen=True)
class Identity:
    """Who the team writes as for one member (or for an installation without members)."""
    member: object
    organization_profile: dict
    member_profile: dict
    legacy: bool  # the installation's person before organizations: no members, or the first member

    @property
    def name(self):
        return self.member_profile['name']

    @property
    def alias(self):
        return alias_of(self.name)

    @property
    def decisor(self):
        return self.name if self.legacy else ORGANIZATION_DECISOR

    def org(self, field):
        return self.organization_profile[field]

    def me(self, field):
        return self.member_profile[field]

    def render(self, text):
        """A template with her {nombre}, {decisor} and {alias}. Every prompt goes through here."""
        return text.replace('{nombre}', self.name).replace('{decisor}', self.decisor).replace('{alias}', self.alias)

    def key(self, stored):
        """A stored key (`questions_for_gustavo`) as she reads it (`questions_for_<alias>`)."""
        return _TOKEN.sub(self.alias, stored)

    def keyed(self, value, values=True):
        """A schema or a state with her token in every key (and, with `values`, every identifier: a schema's `required`
        and `enum`) that carries the stored one. For the installation's first person nothing changes."""
        return _swap(value, self.key, values)

    def unkeyed(self, value, schema):
        """Her answer back to the stored names, for every keyed name of `schema`."""
        names = {}
        _collect(schema, names)
        back = {self.key(n): n for n in names if self.key(n) != n}
        return _swap(value, lambda name: back.get(name, name), True) if back else value

    def modalities(self):
        """Canonical modality -> {purpose, neighborhood} as it applies to her: without the personal startup modality when
        it is not hers, and with her own words for a purpose."""
        out = {}
        for key, item in self.org('modalities').items():
            if key == 'personal_startups' and not self.me('personal_startups'):
                continue
            purpose = self.me('purposes').get(key) or item['purpose']
            out[key] = {'purpose': self.render(purpose), 'neighborhood': item['neighborhood']}
        return out


_TOKEN = re.compile(r'(?<![a-z0-9])' + STORED_TOKEN + r'(?![a-z0-9])')
_IDENT = re.compile(r'[a-z0-9_]+')


def _collect(value, names):
    if isinstance(value, dict):
        for k, v in value.items():
            if _TOKEN.search(k):
                names[k] = True
            _collect(v, names)
    elif isinstance(value, (list, tuple)):
        for v in value:
            _collect(v, names)
    elif isinstance(value, str) and _IDENT.fullmatch(value) and _TOKEN.search(value):
        names[value] = True


def _swap(value, rename, values):
    if isinstance(value, dict):
        return {(rename(k) if isinstance(k, str) else k): _swap(v, rename, values) for k, v in value.items()}
    if isinstance(value, list):
        return [_swap(v, rename, values) for v in value]
    if isinstance(value, tuple):
        return tuple(_swap(v, rename, values) for v in value)
    if values and isinstance(value, str) and _IDENT.fullmatch(value):
        return rename(value)
    return value


def _in_order(value, model):
    """`value` with its keys in the order of `model` (the initial identity), recursively; keys `model` lacks go after, as
    stored. PostgreSQL's jsonb does not keep the order a dict was written in, and the texts list pillars, services and
    modalities in that order: without this, a stored profile would reorder Gustavo's criteria (and change their hashes)."""
    if not isinstance(value, dict) or not isinstance(model, dict):
        return value
    keys = [k for k in model if k in value] + [k for k in value if k not in model]
    return {k: _in_order(value[k], model.get(k)) for k in keys}


def _organization_of(member):
    if member is not None:
        return member.organization
    return None


def organization_profile(organization):
    """The organization's profile: its own, or the initial one while it has none (and without any organization)."""
    base = initial()['organization']
    own = (organization.profile or {}) if organization is not None else {}
    return _in_order({**base, **own}, base) if own else base


def organization_profile_of(member=None):
    """The organization's profile when what is read belongs to the organization, not to a member (positioning version,
    services, offer, cases): her organization's (`member` may be an Identity), else the only organization's (the initial
    one when there is none). Several organizations and no member: MiembroRequerido."""
    if isinstance(member, Identity):
        return member.organization_profile
    if member is not None:
        return organization_profile(member.organization)
    from .models import Organization
    rows = list(Organization.objects.order_by('created_at')[:2])
    if len(rows) > 1:
        raise miembros.MiembroRequerido('Hay varias organizaciones: indica de qué miembro es.')
    return organization_profile(rows[0] if rows else None)


def member_profile(member, legacy=None):
    """Her profile: her own over neutral defaults; while it is empty, the initial one if she is the installation's first
    person (or there is no member at all), neutral defaults with her display name otherwise."""
    if member is None:
        return initial()['member']
    own = member.profile or {}
    if not own and (miembros.is_first(member) if legacy is None else legacy):
        return initial()['member']
    return _in_order({**NEUTRAL_MEMBER, 'name': member.display_name, **own}, initial()['member'])


def of(member=None):
    """Her Identity. `member=None`: the only active member, else (no members at all) the initial identity; several
    active members raise MiembroRequerido instead of guessing whose identity to write with."""
    if isinstance(member, Identity):
        return member
    member = miembros.resolve(member)
    legacy = miembros.is_first(member)
    return Identity(member, organization_profile(_organization_of(member)), member_profile(member, legacy), legacy)


def initial_identity():
    """The initial identity (the seed's organization and person, legacy) without reading the database: what a pure
    function (drawing, validation) uses when its caller passes no identity. Callers that know the member pass hers."""
    seed = initial()
    return Identity(None, seed['organization'], seed['member'], True)


def of_user(user):
    """The Identity of the member a person acts as (miembros.member_for: hers, else the default member)."""
    return of(miembros.member_for(user))


def private_names():
    """Every name the team writes for a person of the organization (members' names and their key tokens, and the
    initial one): what a public web question must never carry."""
    from .models import Member
    out = {initial()['member']['name'].lower()}
    for member in Member.objects.all():
        name = member_profile(member, miembros.is_first(member))['name']
        out.update(part.lower() for part in re.findall(r'\w+', name) if len(part) > 2)
    return sorted(out)


def of_account(account):
    """The Identity of the member who owns `account` (miembros.member_for_account)."""
    return of(miembros.member_for_account(account))


OWNER_FALLBACK = 'el dueño de la cuenta'


def owner_name(account):
    """Who decides on `account`, for a text a person reads («Solo {nombre} puede reanudarla»): the name of its member, or
    «el dueño de la cuenta» when no member can be named (an account of nobody among several members)."""
    try:
        return of_account(account).name
    except miembros.MiembroRequerido:
        return OWNER_FALLBACK


# --------------------------------------------------------------------------- her memory and orientation (phase 4)

def facts(member=None):
    """(public_facts, private) of her confirmed memory and her organization's company facts (hechos.confirmed_blocks):
    the first member's is the memory of before; any other member's, her own. Never another member's facts."""
    from . import hechos
    return hechos.confirmed_blocks(of(member).member)


def blocks(member=None):
    """guardas.blocks() for her: her confirmed memory, the brief's private guidance (the first member's) and her
    orientation."""
    from . import guardas
    return guardas.blocks(of(member).member)


def orientation(member=None):
    """Her current orientation (orientacion.text)."""
    from . import orientacion
    return orientacion.text(of(member).member)


# --------------------------------------------------------------------------- validation

def _text(field, value, *, required=True, limit=TEXT_MAX, placeholders=()):
    if not isinstance(value, str):
        raise IdentidadInvalida(f'{field}: debe ser texto.')
    value = value.strip()
    if required and not value:
        raise IdentidadInvalida(f'{field}: no puede quedar vacío.')
    if len(value) > limit:
        raise IdentidadInvalida(f'{field}: como mucho {limit} caracteres.')
    rest = value
    for mark in placeholders:
        rest = rest.replace(mark, '')
    if '{' in rest or '}' in rest:
        allowed = ', '.join(placeholders) or 'ninguna'
        raise IdentidadInvalida(f'{field}: sin llaves salvo las marcas permitidas ({allowed}).')
    return value


def _same_keys(field, value, expected):
    if not isinstance(value, dict):
        raise IdentidadInvalida(f'{field}: debe ser un objeto JSON.')
    if set(value) != set(expected):
        missing, extra = sorted(set(expected) - set(value)), sorted(set(value) - set(expected))
        raise IdentidadInvalida(f'{field}: las claves son {", ".join(expected)}'
                                + (f'; faltan {", ".join(missing)}' if missing else '')
                                + (f'; sobran {", ".join(extra)}' if extra else '') + '.')
    return value


def validate_organization(profile):
    """The whole organization profile, normalized, or IdentidadInvalida with the reason. The keys of pillars, services,
    offer, cases and modalities are the ones the code and the stored data use; only their texts change."""
    from . import posicionamiento
    base = initial()['organization']
    unknown = sorted(set(profile) - set(ORGANIZATION_FIELDS))
    if unknown:
        raise IdentidadInvalida(f'Campo desconocido: {", ".join(unknown)}. Campos: {", ".join(ORGANIZATION_FIELDS)}.')
    p = {**base, **profile}
    out = {}
    out['version'] = _text('version', p['version'], limit=60)
    if not re.fullmatch(r'[A-Za-z0-9._-]+', out['version']):
        raise IdentidadInvalida('version: letras, dígitos, «.», «_» y «-».')
    try:
        out['date'] = date.fromisoformat(str(p['date']).strip()).isoformat()
    except ValueError:
        raise IdentidadInvalida('date: AAAA-MM-DD.') from None
    out['status'] = _text('status', p['status'], limit=300, placeholders=('{nombre}',))
    for field in ('language', 'not_wanted', 'location'):
        out[field] = _text(field, p[field], limit=600)
    out['pillars'] = {k: _text(f'pillars.{k}', v, limit=300)
                      for k, v in _same_keys('pillars', p['pillars'], posicionamiento.PILLAR_KEYS).items()}
    services = _same_keys('services', p['services'], posicionamiento.SERVICE_KEYS)
    out['services'] = {}
    for key, item in services.items():
        _same_keys(f'services.{key}', item, ('label', 'source', 'terms'))
        terms = item['terms']
        if not isinstance(terms, list) or not terms or not all(isinstance(t, str) and t.strip() for t in terms):
            raise IdentidadInvalida(f'services.{key}.terms: una lista de términos en inglés, no vacía.')
        out['services'][key] = {'label': _text(f'services.{key}.label', item['label'], limit=300),
                                'source': _text(f'services.{key}.source', item['source'], limit=300),
                                'terms': [t.strip().lower() for t in terms]}
    out['offer'] = {k: _text(f'offer.{k}', v, limit=600)
                    for k, v in _same_keys('offer', p['offer'], tuple(base['offer'])).items()}
    out['cases'] = {k: _text(f'cases.{k}', v, limit=600)
                    for k, v in _same_keys('cases', p['cases'], tuple(base['cases'])).items()}
    modalities = _same_keys('modalities', p['modalities'], tuple(posicionamiento.VOCABULARIES['editorial']))
    out['modalities'] = {}
    for key, item in modalities.items():
        _same_keys(f'modalities.{key}', item, ('purpose', 'neighborhood'))
        out['modalities'][key] = {'purpose': _text(f'modalities.{key}.purpose', item['purpose'], limit=300,
                                                   placeholders=('{nombre}',)),
                                  'neighborhood': _text(f'modalities.{key}.neighborhood', item['neighborhood'])}
    before = p['neighborhood_before']
    if not isinstance(before, dict) or set(before) - set(modalities):
        raise IdentidadInvalida('neighborhood_before: JSON {modalidad: texto} con modalidades existentes.')
    out['neighborhood_before'] = {k: _text(f'neighborhood_before.{k}', v) for k, v in before.items()}
    return out


def validate_member(profile, modalities):
    """Her whole profile, normalized, or IdentidadInvalida with the reason. No braces: her texts are hers, literal."""
    unknown = sorted(set(profile) - set(MEMBER_FIELDS))
    if unknown:
        raise IdentidadInvalida(f'Campo desconocido: {", ".join(unknown)}. Campos: {", ".join(MEMBER_FIELDS)}.')
    p = {**NEUTRAL_MEMBER, **profile}
    out = {'name': _text('name', p.get('name', ''), limit=60)}
    if not re.fullmatch(r"[^\W\d_]+(?:[ '\-][^\W\d_]+)*", out['name']):
        raise IdentidadInvalida('name: solo letras, espacios, apóstrofo o guion.')
    out['identity'] = _text('identity', p['identity'], required=False, limit=600)
    out['company_relation'] = _text('company_relation', p['company_relation'], required=False, limit=300)
    out['limits'] = _text('limits', p['limits'], limit=600)
    flag = p['personal_startups']
    if isinstance(flag, str):
        lowered = flag.strip().lower()
        if lowered not in ('si', 'sí', 'no', 'true', 'false'):
            raise IdentidadInvalida('personal_startups: si o no.')
        flag = lowered in ('si', 'sí', 'true')
    if not isinstance(flag, bool):
        raise IdentidadInvalida('personal_startups: si o no.')
    out['personal_startups'] = flag
    purposes = p['purposes']
    if not isinstance(purposes, dict) or set(purposes) - set(modalities):
        raise IdentidadInvalida(f'purposes: JSON {{modalidad: texto}} con modalidades de la organización ({", ".join(modalities)}).')
    out['purposes'] = {k: _text(f'purposes.{k}', v, limit=300) for k, v in purposes.items()}
    out['brand_version'] = _text('brand_version', p['brand_version'], required=False, limit=80)
    return out


def parse_value(field, raw):
    """A command's VALUE for a field: JSON for the structured ones, text otherwise."""
    structured = ('pillars', 'services', 'offer', 'cases', 'modalities', 'neighborhood_before', 'purposes')
    if field.split('.')[0] in structured and '.' not in field:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            raise IdentidadInvalida(f'{field}: debe ser JSON.') from None
    if field.endswith('.terms'):
        return [t.strip() for t in raw.split(',') if t.strip()]
    return raw


def _set_path(profile, path, value, fields):
    """profile with `path` (field or field.key.key) set to value; only paths that exist, except a new purpose."""
    head, *rest = path.split('.')
    if head not in fields:
        raise IdentidadInvalida(f'Campo desconocido: {head}. Campos: {", ".join(fields)}.')
    if not rest:
        return {**profile, head: value}
    out = json.loads(json.dumps(profile))
    node = out[head]
    for i, key in enumerate(rest):
        last = i == len(rest) - 1
        if not isinstance(node, dict) or (key not in node and not (head == 'purposes' and last)):
            raise IdentidadInvalida(f'{path}: no existe.')
        if last:
            node[key] = value
        else:
            node = node[key]
    return out


def _remove_path(profile, path, fields, base):
    head, *rest = path.split('.')
    if head not in fields:
        raise IdentidadInvalida(f'Campo desconocido: {head}. Campos: {", ".join(fields)}.')
    out = json.loads(json.dumps(profile))
    if not rest:
        out[head] = json.loads(json.dumps(base[head]))
        return out
    if head != 'purposes' or len(rest) != 1:
        raise IdentidadInvalida(f'{path}: solo se quita un campo entero o un propósito propio (purposes.<modalidad>).')
    out['purposes'].pop(rest[0], None)
    return out


# --------------------------------------------------------------------------- saving (validated, audited, versioned)

def subject_of(member):
    return 'organization' if member is None else f'member:{member.pk}'


def revisions(organization, member=None):
    from .models import IdentityRevision
    return IdentityRevision.objects.filter(organization=organization, subject=subject_of(member)).order_by('number')


def _record(actor, organization, member, before, after, changed, source):
    from .jobs import audit
    from .models import IdentityRevision
    last = revisions(organization, member).last()
    revision = IdentityRevision.objects.create(organization=organization, member=member, subject=subject_of(member),
                                               number=(last.number + 1) if last else 1, changed=changed, before=before,
                                               after=after, actor=actor, source=source)
    audit(actor, 'organization.identity_saved', str(member.pk if member else organization.pk), subject=revision.subject,
          number=revision.number, changed=changed, source=source)
    return revision


def can_edit(actor, organization=None, member=None):
    """Her own profile: only she (also while she is being onboarded, inactive: phase 7, «Mi perfil» in the apps). The
    organization's: only its active admin."""
    if member is not None:
        own = miembros.member_of_user(actor)
        return bool(own is not None and own.pk == member.pk and miembros._human(actor))
    return miembros.is_admin(actor, organization)


def may_start(actor, member):
    """Organizaciones, phase 7: the admin writes the minimal profile of a member she is onboarding (alta.py): only while
    that member is inactive and has never saved her profile herself. From then on it is only hers."""
    from .models import IdentityRevision
    return (member is not None and not member.active and miembros.is_admin(actor, member.organization)
            and not IdentityRevision.objects.filter(member=member, actor=member.user).exists())


@transaction.atomic
def save_profile(actor, *, organization=None, member=None, values=None, remove=(), source='comando', on_behalf=False):
    """Set (or bring back to the initial or neutral value) fields of a profile: the organization's or a member's.
    Validated as a whole before anything changes; idempotent; each change is an IdentityRevision with the profile
    before and after, and an audit event. `on_behalf`: the admin onboarding an inactive member (may_start). Returns
    (profile, revision or None)."""
    from .models import Member, Organization
    if member is not None:
        member = Member.objects.select_for_update().select_related('organization').get(pk=member.pk)
        organization = member.organization
    else:
        organization = Organization.objects.select_for_update().get(pk=organization.pk)
    if on_behalf and not may_start(actor, member):
        raise PermissionError('Solo el administrador escribe el perfil inicial de un miembro en alta (inactivo y sin '
                              'cambios propios); después, solo ella lo cambia.')
    if not on_behalf and not can_edit(actor, organization, member):
        raise PermissionError('Solo el propio miembro cambia su perfil.' if member is not None else
                              'Solo el administrador activo de la organización cambia su perfil.')
    values = dict(values or {})
    remove = list(dict.fromkeys(remove))
    if set(values) & set(remove):
        raise IdentidadInvalida('Un mismo campo no se fija y se quita a la vez.')
    fields = MEMBER_FIELDS if member is not None else ORGANIZATION_FIELDS
    before = member_profile(member) if member is not None else organization_profile(organization)
    base = ({**NEUTRAL_MEMBER, 'name': member.display_name} if member is not None else initial()['organization'])
    after = before
    for path, raw in values.items():
        after = _set_path(after, path, parse_value(path, raw) if isinstance(raw, str) else raw, fields)
    for path in remove:
        after = _remove_path(after, path, fields, base)
    if member is not None:
        after = validate_member(after, tuple(organization_profile(organization)['modalities']))
    else:
        after = validate_organization(after)
    stored = member.profile if member is not None else organization.profile
    if after == before and stored:
        return after, None
    changed = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
    if member is not None:
        member.profile = after
        member.save(update_fields=['profile'])
    else:
        organization.profile = after
        organization.save(update_fields=['profile'])
    return after, _record(actor, organization, member, before, after, changed, source)


@transaction.atomic
def seed_first(member, actor=None, source='semilla'):
    """The installation's first member (and her organization) get the initial identity and her voice, when they have
    none: what migration 0058 does for a database that already had her. Idempotent."""
    from .models import Organization, VoiceDocument
    organization = Organization.objects.select_for_update().get(pk=member.organization_id)
    data = initial()
    if not organization.profile:
        organization.profile = data['organization']
        organization.save(update_fields=['profile'])
        _record(actor, organization, None, {}, organization.profile, sorted(organization.profile), source)
    if not member.profile:
        member.profile = data['member']
        member.save(update_fields=['profile'])
        _record(actor, organization, member, {}, member.profile, sorted(member.profile), source)
    if not VoiceDocument.objects.filter(member=member).exists():
        from . import voz
        voz.record_initial(member, actor)
