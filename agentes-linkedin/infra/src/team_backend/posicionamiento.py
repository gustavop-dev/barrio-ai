"""Gustavo's positioning: the one versioned source the agents read (audit «Un solo artefacto de posicionamiento»).

Before, the direction was copied in three places with different modality vocabularies: editorial.DIRECTION, the
classifier's red.CLASSIFY_SYSTEM and the lead agent's lider.CRITERIA_DEL_BARRIO. Those three constants now derive
from this module, so a change of direction is one edit here and a new VERSION.

Source: docs/brief-gustavo-posicionamiento.md and docs/propuesta-posicionamiento-gustavo-v1.md (an internal proposal
Gustavo supervises; not confirmed by him as final). Private priorities (60/40, audience segment, conditions) are not
here: they live in guardas.BASELINE_GUIDANCE as private guidance, never as positioning text.

Modalities have one canonical id each. Stored values keep the vocabulary of their domain, because they are persisted
and read by the PWA, and are never renamed:
- editorial: EditorialPiece.brief['modality'] (oficina lib/editorial.ts MODALITY_LABEL), same ids as the canonical ones;
- red: Contact.classification['modality'] (oficina lib/format.ts CONTACT_MODALITY_LABEL, personas/labels.ts
  MODALITY_SHORT); `comunidad` is stored as `comunidad_autoridad`;
- oportunidades: Opportunity.modality (models.Opportunity.Modality, personas/labels.ts OPPORTUNITY_MODALITY_LABEL);
  only the two business modalities exist there, plus `por_clasificar` for an opportunity whose modality is unknown.
  An alliance or a community contact is not a business opportunity by itself, so it has no opportunity modality.
VOCABULARIES is that explicit mapping; to_canonical / to_stored translate between domains."""

VERSION='posicionamiento-v2'
DATE='2026-11-12'
STATUS='propuesta interna v2; Gustavo la supervisa'

IDENTITY=('Gustavo es ingeniero de producto con criterio de negocio: convierte necesidades de negocio en software que '
          'funciona, lo evoluciona e integra IA cuando resuelve un problema concreto.')
PROJECTAPP='Fundó y lidera ProjectApp, un equipo de desarrollo de software a la medida.'
LANGUAGE='Publica en LinkedIn, en inglés.'
PILLARS={
    'business_to_product':'traducir problemas de negocio en decisiones de producto y de software',
    'applied_ai':'incorporar y evaluar IA en soluciones concretas',
    'architecture_delivery':'decisiones de arquitectura y de entrega al construir productos reales',
}
LIMITS=('humo y promesas; temas que Gustavo no domina; experiencias, clientes, cifras o resultados inventados; pitch '
        'agresivo; datos privados de cualquier persona')
NOT_WANTED='No buscan vendedores ni reclutadores masivos.'
# Gustavo, 12/11/2026: «la idea es que linkedin nos mande a posicionarnos allá».
LOCATION=('el barrio se construye en EE. UU.: los compradores (founders) deben estar allí; el resto de la comunidad va '
          'primero si está allí y también puede venir de Latinoamérica.')

# What Gustavo sells, restated from IDENTITY, PROJECTAPP, PILLARS and the two business modalities below; no new direction,
# so VERSION stays. An «industry referent» (referentes_industria.py) must sell one of these. `terms` are the English words
# a profile or a page uses for the same service (the barrio is built in the United States), used to search and to match.
SERVICES={
    'software_a_la_medida':{'label':'desarrollo de software a la medida (entrega externa, proyecto definido o equipo continuo)',
        'source':'PROJECTAPP, modalidad projectapp','terms':('custom software development','software development agency')},
    'producto':{'label':'convertir necesidades de negocio en un producto de software que funciona y evolucionarlo',
        'source':'IDENTITY, pilar business_to_product','terms':('product development','mvp development')},
    'ia_aplicada':{'label':'incorporar IA en soluciones concretas','source':'IDENTITY, pilar applied_ai',
        'terms':('applied ai','ai development')},
    'liderazgo_tecnico':{'label':'liderazgo técnico en startups: decisiones de arquitectura y de entrega',
        'source':'modalidad personal_startups, pilar architecture_delivery','terms':('fractional cto','technical leadership')},
}

# Canonical modality -> what it is for Gustavo (editorial) and who belongs to it (neighborhood criteria).
MODALITIES={
    'personal_startups':{'purpose':'oportunidades de trabajo personal en startups',
        # Gustavo, 12/11/2026: «Semilla por delante»; presemilla rarely has money to hire.
        'neighborhood':'founders técnicos o de negocio de startups con ronda semilla o posterior, o con clientes que pagan, '
                       'líderes técnicos y personas que recomiendan talento en startups'},
    'projectapp':{'purpose':'contratos para ProjectApp, el equipo que Gustavo lidera',
        'neighborhood':'founders u operadores que necesitan una entrega externa, un proyecto definido o un equipo continuo'},
    'alianzas':{'purpose':'relaciones con quienes recomiendan talento o proveedores',
        'neighborhood':'estudios o agencias complementarios, freelancers senior, aceleradoras, inversores o comunidades que '
                       'recomiendan talento o proveedores'},
    'comunidad':{'purpose':'comunidad y autoridad temática en el nicho',
        'neighborhood':'pares, divulgadores y líderes temáticos (producto, software, IA aplicada, startups) que sostienen la '
                       'conversación del nicho'},
}

# Domain -> {canonical id: stored value}. Order follows MODALITIES.
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

# --------------------------------------------------------------------------- texts for each agent

def editorial_direction():
    """Positioning block of the editorial system prompts (director, writers, selection, repair)."""
    pillars=', '.join(f'{key} ({text})' for key,text in PILLARS.items())
    modes=', '.join(f'{to_stored("editorial",key)} ({item["purpose"]})' for key,item in MODALITIES.items())
    return '\n'.join([f'Dirección editorial vigente ({VERSION}, {STATUS}):',f'- {IDENTITY} {PROJECTAPP} {LANGUAGE}',
                      f'- Pilares provisionales: {pillars}.',f'- Modalidades: {modes}. No conviertas cada pieza en una oferta.',
                      f'- Prohibido: {LIMITS}.'])

def network_criteria():
    """Who Gustavo is and the neighborhood criteria per modality, in the classifier's stored vocabulary."""
    lines=[f'- {to_stored("red",key)}: {item["neighborhood"]}.' for key,item in MODALITIES.items()]
    return '\n'.join([f'{IDENTITY} {PROJECTAPP}','',f'Criterios de barrio por modalidad ({VERSION}):',*lines,'',
                      f'Ubicación: {LOCATION}'])

def lead_criteria():
    """One paragraph for the lead agent's `criterios_del_barrio` (Jev reads it as state)."""
    return (f'{IDENTITY} {PROJECTAPP} Su barrio en LinkedIn: '+'; '.join(i['neighborhood'] for i in MODALITIES.values())+
            f'. Ubicación: {LOCATION} {NOT_WANTED}')
