"""The positioning the agents read: the one source (audit «Un solo artefacto de posicionamiento»), now per member.

Before, the direction was copied in three places with different modality vocabularies: editorial.DIRECTION, the
classifier's red.CLASSIFY_SYSTEM and the lead agent's lider.CRITERIA_DEL_BARRIO. All three derive from this module, so a
change of direction is one edit of the profile and a new version.

Phase 3 of organizations (docs/plan-organizaciones.md): the texts are no longer code. What the organization is and sells
(version and status, language, pillars, services, offer, cases, modalities and their neighborhood, location, what it
does not want) is the organization's profile; who the member is (her presentation, her relation to the company, her
limits, whether the personal startup modality is hers) is her profile (identidad.py). Every function takes the member
it writes for (or her Identity) and composes the block for her. For the installation's first member, and for an
installation without members, the texts are exactly the ones of before (identidad.initial(), recursos/
identidad-inicial.json, from docs/brief-gustavo-posicionamiento.md and docs/propuesta-posicionamiento-gustavo-v1.md).
Private priorities (60/40, audience segment, conditions) are not here: they are private guidance (guardas).

Modalities have one canonical id each. Stored values keep the vocabulary of their domain, because they are persisted
and read by the PWA, and are never renamed:
- editorial: EditorialPiece.brief['modality'] (oficina lib/editorial.ts MODALITY_LABEL), same ids as the canonical ones;
- red: Contact.classification['modality'] (oficina lib/format.ts CONTACT_MODALITY_LABEL, personas/labels.ts
  MODALITY_SHORT); `comunidad` is stored as `comunidad_autoridad`;
- oportunidades: Opportunity.modality (models.Opportunity.Modality, personas/labels.ts OPPORTUNITY_MODALITY_LABEL);
  only the two business modalities exist there, plus `por_clasificar` for an opportunity whose modality is unknown.
  An alliance or a community contact is not a business opportunity by itself, so it has no opportunity modality.
VOCABULARIES is that explicit mapping; to_canonical / to_stored translate between domains. The keys of pillars,
services, offer and cases are contracts of the stored data and the schemas too: a profile changes their texts only."""
from . import identidad

PILLAR_KEYS=('business_to_product','applied_ai','architecture_delivery')
# An «industry referent» (referentes_industria.py) must sell one of these; `terms` (in the profile) are the English words a
# profile or a page uses for the same service, used to search and to match.
SERVICE_KEYS=('software_a_la_medida','producto','ia_aplicada','liderazgo_tecnico')

# Domain -> {canonical id: stored value}. Order follows the profile's modalities.
VOCABULARIES={
    'editorial':{'personal_startups':'personal_startups','projectapp':'projectapp','alianzas':'alianzas','comunidad':'comunidad'},
    'red':{'personal_startups':'personal_startups','projectapp':'projectapp','alianzas':'alianzas','comunidad':'comunidad_autoridad'},
    'oportunidades':{'personal_startups':'personal_startups','projectapp':'projectapp'},
}
UNKNOWN={'oportunidades':'por_clasificar'}  # stored value for «modality not known yet»

def modalities(domain):
    """Stored values of a domain, in canonical order (the unknown value, if any, is not included)."""
    return list(VOCABULARIES[domain].values())

def to_canonical(domain,value):
    """Canonical id of a stored value, or None when it has none (unknown or not a modality of that domain)."""
    return next((canonical for canonical,stored in VOCABULARIES[domain].items() if stored==value),None)

def to_stored(domain,canonical):
    """Stored value of a canonical id in a domain; the domain's unknown value (or None) when it has no equivalent."""
    return VOCABULARIES[domain].get(canonical,UNKNOWN.get(domain))

# --------------------------------------------------------------------------- the profile, for one member

def identity(member=None):
    """Her Identity (identidad.of): `member` may already be one."""
    return identidad.of(member)

def _organization(member=None):
    """What belongs to the organization needs no member (identidad.organization_profile_of)."""
    return identidad.organization_profile_of(member)

def version(member=None):
    """The positioning version of her organization (experiments, community studies and briefs record it)."""
    return _organization(member)['version']

def status(member=None):
    """The positioning status, with her name where it names the member who supervises it."""
    ident=identity(member)
    return ident.render(ident.org('status'))

def pillars(member=None):
    return _organization(member)['pillars']

def services(member=None):
    """What her organization sells: {key: {label, source, terms}} (SERVICE_KEYS)."""
    return _organization(member)['services']

def offer(member=None):
    return _organization(member)['offer']

def cases(member=None):
    """The only confirmed facts of the organization's cases (17/11/2026): {segment: text}. Nothing else is confirmed: no
    client names, figures, durations or results until the owner answers the case questions (projectapp)."""
    return _organization(member)['cases']

def modality_purposes(member=None):
    """Canonical modality -> what it is for her (editorial), only the modalities that apply to her."""
    return {key:item['purpose'] for key,item in identity(member).modalities().items()}

# --------------------------------------------------------------------------- texts for each agent

def _who(ident):
    """How the blocks present her: her presentation and her relation to the organization."""
    return ' '.join(part for part in (ident.me('identity'),ident.me('company_relation')) if part)

def editorial_direction(member=None):
    """Positioning block of the editorial system prompts (director, writers, selection, repair) for her."""
    ident=identity(member)
    pillars_text=', '.join(f'{key} ({text})' for key,text in ident.org('pillars').items())
    modes=', '.join(f'{to_stored("editorial",key)} ({item["purpose"]})' for key,item in ident.modalities().items())
    who=' '.join(part for part in (_who(ident),ident.org('language')) if part)
    return '\n'.join([f'Dirección editorial vigente ({ident.org("version")}, {status(ident)}):',f'- {who}',
                      f'- Pilares provisionales: {pillars_text}.',f'- Modalidades: {modes}. No conviertas cada pieza en una oferta.',
                      f'- Prohibido: {ident.me("limits")}.'])

def neighborhood(key,projectapp_buyer=False,member=None):
    """Who belongs to a modality: the refined ProjectApp neighborhood only with the ProjectApp buyer on (BAR-25). With
    NETWORK_PROJECTAPP_BUYER_ENABLED off the classifier and the lead read the neighborhood as before 17/11/2026, word for
    word (the profile's `neighborhood_before`)."""
    profile=identity(member).organization_profile
    item=profile['modalities'][key]['neighborhood']
    return item if projectapp_buyer else profile['neighborhood_before'].get(key,item)

def offer_text(member=None):
    """What the organization offers and the only confirmed facts of its cases, for the classifier and the lead."""
    o,c=offer(member),cases(member)
    return (f'Oferta de ProjectApp: {o["equipo_dedicado"]}, o {o["proyecto"]}; {o["argumento"]}. Casos reales '
            f'confirmados: {c["educacion_en_linea"]}, y {c["retail_ecommerce"]}; ningún otro dato de esos casos está '
            'confirmado (ni nombres, ni cifras, ni plazos, ni resultados).')

def network_criteria(member=None,projectapp_buyer=False):
    """Who she is and the neighborhood criteria per modality (hers), in the classifier's stored vocabulary. Without
    `projectapp_buyer` the exact text of before 17/11/2026."""
    ident=identity(member)
    lines=[f'- {to_stored("red",key)}: {neighborhood(key,projectapp_buyer,ident)}.' for key in ident.modalities()]
    extra=['',offer_text(ident)] if projectapp_buyer else []
    return '\n'.join([_who(ident),'',f'Criterios de barrio por modalidad ({ident.org("version")}):',*lines,*extra,'',
                      f'Ubicación: {ident.org("location")}'])

def lead_criteria(member=None,projectapp_buyer=False):
    """One paragraph for the lead agent's `criterios_del_barrio` (Jev reads it as state), for her."""
    ident=identity(member)
    return (f'{_who(ident)} Su barrio en LinkedIn: '+'; '.join(neighborhood(key,projectapp_buyer,ident) for key in ident.modalities())+
            f'. Ubicación: {ident.org("location")} {ident.org("not_wanted")}'+(f' {offer_text(ident)}' if projectapp_buyer else ''))
