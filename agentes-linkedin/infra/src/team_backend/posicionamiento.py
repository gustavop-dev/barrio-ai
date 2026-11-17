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
# Gustavo, 12/11/2026: «la idea es que linkedin nos mande a posicionarnos allá»; 17/11/2026, de los compradores de
# Latinoamérica: «podríamos prospectarlos al inicio; queremos ir hacia USA pero no los descartamos de una». Only who the
# network goes after changes, not the editorial direction (identity, pillars, modalities): VERSION stays, so the reader
# study and the experiments tied to it stay valid; the classifier's criterion_version hashes this text anyway.
LOCATION=('el barrio se construye en EE. UU.: compradores (founders) y comunidad van primero si están allí; los de '
          'Latinoamérica también entran, después.')

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

# BAR-25, Gustavo 17/11/2026: «no se verticaliza el contenido: se verticaliza a quién se le escribe y con qué prueba». The
# editorial direction (identity, pillars, purposes) does not change, so VERSION stays; who the network goes after for
# ProjectApp, the offer and the proof do (only with NETWORK_PROJECTAPP_BUYER_ENABLED: projectapp.py). Three audiences:
# the ProjectApp buyer, the startup buyer (the one before) and the partner (a new role, not an `aliado`).
PROJECTAPP_BUYER=('empresas tradicionales de 20 a 200 personas en EE. UU. que necesitan digitalizarse, o que ya tienen '
                  'software y quieren ampliarlo: su dueño o CEO, o su líder de tecnología (CTO, VP, Head o Director de '
                  'ingeniería o de TI, gerente de sistemas)')
PARTNER=('agencias de marketing, diseño, consultoría o producto que subcontratan el desarrollo de software de sus clientes '
         '(partners: traen contratos, no compran para sí)')
# What ProjectApp offers, as Gustavo said it (17/11/2026). Approximate prices, never a quote: «desde unos».
OFFER={'equipo_dedicado':'un equipo dedicado, desde unos 20 millones de pesos colombianos al mes (unos 5.000 USD)',
       'proyecto':'un proyecto por requerimientos, desde unos 20 millones de pesos colombianos',
       'argumento':'nearshore: buena calidad a menor costo'}
# The only confirmed facts of ProjectApp's cases (17/11/2026). Nothing else is confirmed: no client names, figures,
# durations or results until Gustavo answers the case questions (projectapp.ask_case_questions).
CASES={'educacion_en_linea':'ProjectApp construyó una plataforma grande a la medida de educación en línea',
       'retail_ecommerce':'ProjectApp construyó una plataforma grande a la medida de retail'}

# Canonical modality -> what it is for Gustavo (editorial) and who belongs to it (neighborhood criteria).
MODALITIES={
    'personal_startups':{'purpose':'oportunidades de trabajo personal en startups',
        # Gustavo, 12/11/2026: «Semilla por delante»; presemilla rarely has money to hire.
        'neighborhood':'founders técnicos o de negocio de startups con ronda semilla o posterior, o con clientes que pagan, '
                       'líderes técnicos y personas que recomiendan talento en startups'},
    'projectapp':{'purpose':'contratos para ProjectApp, el equipo que Gustavo lidera',
        'neighborhood':f'{PROJECTAPP_BUYER}; founders u operadores de startups que necesitan una entrega externa, un proyecto '
                       f'definido o un equipo continuo; y {PARTNER}'},
    'alianzas':{'purpose':'relaciones con quienes recomiendan talento o proveedores',
        'neighborhood':'estudios o agencias complementarios, freelancers senior, aceleradoras, inversores o comunidades que '
                       'recomiendan talento o proveedores'},
    'comunidad':{'purpose':'comunidad y autoridad temática en el nicho',
        'neighborhood':'pares, divulgadores y líderes temáticos (producto, software, IA aplicada, startups) que sostienen la '
                       'conversación del nicho'},
}

# Domain -> {canonical id: stored value}. Order follows MODALITIES.
# With NETWORK_PROJECTAPP_BUYER_ENABLED off the classifier and the lead read the neighborhood as before 17/11/2026, word
# for word: off is exactly today's behavior (projectapp.enabled).
NEIGHBORHOOD_BEFORE={'projectapp':'founders u operadores que necesitan una entrega externa, un proyecto definido o un equipo continuo'}

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

def neighborhood(key,projectapp_buyer=False):
    """Who belongs to a modality: the refined ProjectApp neighborhood only with the ProjectApp buyer on (BAR-25)."""
    return MODALITIES[key]['neighborhood'] if projectapp_buyer else NEIGHBORHOOD_BEFORE.get(key,MODALITIES[key]['neighborhood'])

def offer_text():
    """What ProjectApp offers and the only confirmed facts of its cases, for the classifier and the lead."""
    return (f'Oferta de ProjectApp: {OFFER["equipo_dedicado"]}, o {OFFER["proyecto"]}; {OFFER["argumento"]}. Casos reales '
            f'confirmados: {CASES["educacion_en_linea"]}, y {CASES["retail_ecommerce"]}; ningún otro dato de esos casos está '
            'confirmado (ni nombres, ni cifras, ni plazos, ni resultados).')

def network_criteria(projectapp_buyer=False):
    """Who Gustavo is and the neighborhood criteria per modality, in the classifier's stored vocabulary. Without
    `projectapp_buyer` the exact text of before 17/11/2026."""
    lines=[f'- {to_stored("red",key)}: {neighborhood(key,projectapp_buyer)}.' for key in MODALITIES]
    extra=['',offer_text()] if projectapp_buyer else []
    return '\n'.join([f'{IDENTITY} {PROJECTAPP}','',f'Criterios de barrio por modalidad ({VERSION}):',*lines,*extra,'',
                      f'Ubicación: {LOCATION}'])

def lead_criteria(projectapp_buyer=False):
    """One paragraph for the lead agent's `criterios_del_barrio` (Jev reads it as state)."""
    return (f'{IDENTITY} {PROJECTAPP} Su barrio en LinkedIn: '+'; '.join(neighborhood(key,projectapp_buyer) for key in MODALITIES)+
            f'. Ubicación: {LOCATION} {NOT_WANTED}'+(f' {offer_text()}' if projectapp_buyer else ''))
