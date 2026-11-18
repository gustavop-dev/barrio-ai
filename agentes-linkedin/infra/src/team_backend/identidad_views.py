"""Organizaciones, phase 7: «Mi perfil» and «Mi voz» in the apps (what phase 3 left in commands), and, for the admin,
«Organización»: its profile and its members with their state (nothing private of anyone).

- GET/PATCH /api/v1/yo/perfil: her profile (identidad.save_profile: validated, audited, with its history). Only she
  changes it; it also answers while she is inactive, being onboarded (alcance.DE_ALTA).
- GET /api/v1/yo/voz, POST /api/v1/yo/voz/proponer, POST /api/v1/yo/voz/decidir: her voice (voz.py): which one the team
  writes with, her signals against the minimum, the proposal waiting for her and her decision on it. Only she confirms
  or discards; proposing is one paid call (VOICE_LEARNING_ENABLED and the minimum sample).
- GET /api/v1/organizacion: the admin's view of the organization (alcance.ADMINISTRADOR)."""
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from . import alcance, identidad, miembros, voz
from .operador_views import human_session

PROFILE_FIELDS = ('name', 'role', 'identity', 'company_relation', 'limits', 'personal_startups')
ROLE_MAX = 120
HELP = {
    'name': identidad.MEMBER_FIELDS['name'],
    'role': 'su rol en la organización (p. ej. «CTO»): se muestra junto a su nombre',
    'identity': identidad.MEMBER_FIELDS['identity'],
    'company_relation': identidad.MEMBER_FIELDS['company_relation'],
    'limits': 'temas que no domina y lo que nunca se escribe en su nombre',
    'personal_startups': identidad.MEMBER_FIELDS['personal_startups'],
}


def _member(request):
    member = alcance.miembro(request)
    if member is None:
        raise ValidationError({'detail': 'No eres miembro de ninguna organización.'})
    return member


def _forbidden(exc):
    raise PermissionDenied(str(exc)) from None


# --------------------------------------------------------------------------- her profile

def profile_payload(member):
    ident = identidad.of(member)
    profile = ident.member_profile
    history = [{'number': r.number, 'created_at': r.created_at, 'source': r.source, 'changed': r.changed,
                'by': _actor(r.actor_id)} for r in identidad.revisions(member.organization, member).order_by('-number')]
    return {'member': {'id': str(member.pk), 'display_name': member.display_name, 'role': member.role, 'active': member.active},
            'profile': {'name': profile['name'], 'role': member.role, 'identity': profile['identity'],
                        'company_relation': profile['company_relation'], 'limits': profile['limits'],
                        'personal_startups': bool(profile['personal_startups'])},
            'own': bool(member.profile), 'help': HELP, 'history': history}


def _actor(user_id):
    """Who made a revision, by her name in the organization (a member) or «el sistema» (a migration, a seed)."""
    if user_id is None:
        return 'el sistema'
    _, Member, _ = miembros._models()
    found = Member.objects.filter(user_id=user_id).values_list('display_name', flat=True).first()
    return found or 'el administrador del servidor'


class Profile(APIView):
    def get(self, request):
        return Response(profile_payload(_member(request)))

    def patch(self, request):
        human_session(request)  # her decision: never a service credential
        member = _member(request)
        data = request.data if isinstance(request.data, dict) else {}
        unknown = sorted(set(data) - set(PROFILE_FIELDS))
        if unknown:
            raise ValidationError({'detail': f'Campo desconocido: {", ".join(unknown)}. Campos: {", ".join(PROFILE_FIELDS)}.'})
        values = {k: data[k] for k in PROFILE_FIELDS if k in data and k != 'role'}
        role = data.get('role')
        if role is not None and (not isinstance(role, str) or len(role.strip()) > ROLE_MAX):
            raise ValidationError({'detail': f'role: texto de como mucho {ROLE_MAX} caracteres.'})
        if not identidad.can_edit(request.user, member=member):
            _forbidden('Solo el propio miembro cambia su perfil.')
        try:
            _, revision = identidad.save_profile(request.user, member=member, values=values, source='app') if values else (None, None)
        except PermissionError as exc:
            _forbidden(exc)
        saved = revision is not None
        if role is not None and role.strip() != member.role:
            member.refresh_from_db()
            before = member.role
            member.role = role.strip()
            member.save(update_fields=['role'])
            from .jobs import audit
            audit(request.user, 'organization.member_role', str(member.pk), before=before, after=member.role, source='app')
            saved = True
        member.refresh_from_db()
        return Response({**profile_payload(member), 'saved': saved})


# --------------------------------------------------------------------------- her voice

LABELS = {voz.PROVISIONAL_KIND: 'Provisional', voz.INITIAL: 'Inicial de la instalación'}


def voice_payload(member, actor):
    current = voz.current(member)
    proposal = voz.pending_proposal(member)
    signals = voz.progress(member)
    return {
        'state': current.kind, 'version': current.number,
        'label': f'Confirmada v{current.number}' if current.kind == voz.CONFIRMED else LABELS[current.kind],
        'learning_enabled': voz.enabled(), 'signals': signals,
        'can_propose': bool(voz.enabled() and proposal is None and signals['texts'] >= signals['minimum']
                            and voz._can_propose(actor, member)),
        'proposal': {'number': proposal.number, 'created_at': proposal.created_at, 'note': proposal.note,
                     'text': voz._text_of(proposal)} if proposal is not None else None,
        'versions': [{'number': d.number, 'state': d.state, 'source': d.source, 'created_at': d.created_at,
                      'decided_at': d.decided_at} for d in voz.documents(member).order_by('-number')],
    }


class Voice(APIView):
    def get(self, request):
        return Response(voice_payload(_member(request), request.user))


class VoicePropose(APIView):
    def post(self, request):
        human_session(request)
        member = _member(request)
        try:
            voz.propose(request.user, member)
        except PermissionError as exc:
            _forbidden(exc)
        return Response(voice_payload(member, request.user), status=201)


class VoiceDecide(APIView):
    def post(self, request):
        human_session(request)
        member = _member(request)
        data = request.data if isinstance(request.data, dict) else {}
        number, decision, note = data.get('number'), data.get('decision'), data.get('note') or ''
        if not isinstance(number, int) or isinstance(number, bool) or number < 1:
            raise ValidationError({'detail': 'number: el número de la propuesta.'})
        if decision not in ('confirmar', 'descartar'):
            raise ValidationError({'detail': 'decision: confirmar o descartar.'})
        if not isinstance(note, str) or len(note) > 1000:
            raise ValidationError({'detail': 'note: texto de como mucho 1000 caracteres.'})
        try:
            if decision == 'confirmar':
                voz.confirm(request.user, member, number)
            else:
                voz.discard(request.user, member, number, note.strip())
        except PermissionError as exc:
            _forbidden(exc)
        return Response(voice_payload(member, request.user))


# --------------------------------------------------------------------------- the organization (its admin)

ORGANIZATION_SHOWN = ('version', 'date', 'status', 'language', 'location', 'not_wanted', 'pillars', 'services', 'offer',
                      'cases', 'modalities')


def organization_payload(organization):
    from .models import ConnectorAccount, Member
    profile = identidad.organization_profile(organization)
    members = []
    for member in Member.objects.filter(organization=organization).order_by('created_at', 'pk'):
        providers = set(ConnectorAccount.objects.filter(member=member).values_list('provider', flat=True))
        members.append({'id': str(member.pk), 'display_name': member.display_name, 'role': member.role,
                        'active': member.active, 'is_admin': member.is_admin, 'first': miembros.is_first(member),
                        'voice': voz.current(member).kind,
                        'accounts': {'official': bool(providers & set(miembros.OFFICIAL)),
                                     'reader': bool(providers & set(miembros.READERS))},
                        'since': member.created_at.date()})
    return {'organization': {'id': str(organization.pk), 'name': organization.name, 'slug': organization.slug},
            'profile': {k: profile[k] for k in ORGANIZATION_SHOWN}, 'members': members}


class OrganizationView(APIView):
    def get(self, request):
        member = miembros.member_of_user(request.user)
        if member is None or not miembros.is_admin(request.user, member.organization):
            raise PermissionDenied('Solo el administrador de la organización.')
        return Response(organization_payload(member.organization))
