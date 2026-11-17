"""The buyer of the neighborhood: what kind of buyer, how much evidence there is, and an explainable score (BAR-18).

Gustavo, 17/11/2026: «Siento que puede ser demasiado estricto, o que el verificador hace una pregunta demasiado rígida y
no deja pasar a nadie»; «estamos cortando con una misma tijera a todos; podríamos cambiar las preguntas dependiendo del
perfil»; «pueden entrar, pero con puntaje, al menos para saber cuáles son los que más». A stale or thin profile is not a
problem: the warm-up and the sales qualification settle it later.

The target does not change (a seed round or later, or paying customers: posicionamiento.MODALITIES, «Semilla por
delante»). What changes is that the absence of public evidence is no longer evidence against:
- profile (PROFILES): the kind of buyer, which decides the question the web check asks (QUESTIONS).
- level (LEVELS): confirmado, probable, por_confirmar or no_encaja. Only no_encaja leaves the neighborhood; the others
  stay, in that order.
- score (score(), SCORE_VERSION): 0–100, a sum of visible components. It orders the buyers inside their market tier
  (red.prioritized) and never excludes anyone. A thin profile never loses points: missing data takes the middle value of
  its component and only raises a notice.
- entry (record_entry): the level and score a buyer entered with, kept once and never overwritten, to compare later
  whether the «por confirmar» accept and answer like the confirmed ones (entry_funnel)."""
import re
import unicodedata

from django.utils import timezone

PROFILES=('startup_financiada','bootstrapped','stealth','ejecutivo')
FOUNDER_PROFILES=('startup_financiada','bootstrapped','stealth')
LEVELS=('confirmado','probable','por_confirmar','no_encaja')
LEVEL_RANK={level:n for n,level in enumerate(LEVELS)}
# Verdicts of the web check until 17/11/2026: «sin_evidencia» was the absence of evidence, now por_confirmar.
LEGACY_VERDICTS={'semilla_o_mas':'confirmado','presemilla':'no_encaja','sin_evidencia':'por_confirmar'}
THIN_NOTICE='perfil con poca información'
ENTRY_ACTION='network.buyer_entered'

# The question that applies to each kind of buyer: `web` is the public search (English, no private data; research.
# safe_question still filters it), `juez` is what the judge of the stage weighs. Same research call and same searches
# (WEB_SEARCH_MAX_USES): the question only says what to look for.
QUESTIONS={
    'startup_financiada':{
        'web':'Funding of {company}: seed, Series A or later round, investors and date; paying customers.',
        'juez':'Startup con inversión externa: ¿qué ronda levantó (semilla, serie A o posterior) y cuándo? Una ronda semilla o '
               'posterior con fuente es confirmado; inversores o aceleradora sin ronda publicada, probable.'},
    'bootstrapped':{
        'web':'{company}: paying customers, pricing, revenue, number of employees and years operating.',
        'juez':'Empresa sin inversión externa conocida: ¿tiene clientes que pagan, ingresos, empleados, años operando? Clientes '
               'que pagan o ingresos con fuente es confirmado; precios publicados, empleados o años operando, probable.'},
    'stealth':{
        'web':'{company}: team and hiring; previous companies, exits or acquisitions of the founder; backers or accelerator.',
        'juez':'Founder en stealth o con un perfil escueto: ¿tiene una salida previa, una trayectoria fuerte, un equipo, respaldo '
               '(inversores, aceleradora) o contrataciones abiertas? Eso es probable; una ronda o clientes que pagan, '
               'confirmado. Que la web no sepa nada de una empresa en stealth es por_confirmar, nunca no_encaja.'},
    'ejecutivo':{
        'web':'{company}: company size, employees, funding or revenue; who leads engineering and product decisions.',
        'juez':'Ejecutivo en una empresa establecida: ¿decide o influye en contratar desarrollo y qué tamaño tiene la empresa? '
               'Empresa con ingresos o ronda y un cargo que decide o influye es confirmado o probable; si no decide ni influye '
               '(vende, recluta o ejecuta para otros), no_encaja.'},
}
DEFAULT_QUESTION={
    'web':'Funding stage (pre-seed, seed, Series A or later) or paying customers of {company}.',
    'juez':'¿Levantó una ronda semilla o posterior, o tiene clientes que pagan? Señales indirectas, probable.'}

# --------------------------------------------------------------------------- level

def _buyer(contact):
    return dict((contact.classification or {}).get('buyer') or {})

def level_of(contact):
    """The buyer's current level, or None when the person is not a buyer (or an old discard with no level)."""
    c=contact.classification or {}
    if c.get('role')!='comprador':return None
    level=_buyer(contact).get('level')
    if level in LEVELS:return level
    check=c.get('stage_check') or {}
    if check.get('state') in ('ok','failed') and check.get('verdict') in LEGACY_VERDICTS:return LEGACY_VERDICTS[check['verdict']]
    if check.get('state')=='failed':return 'no_encaja'
    return 'por_confirmar' if c.get('fit') else None

def combine(current,found):
    """The level after the web check: evidence against wins; otherwise the stronger of the profile's and the web's."""
    if found=='no_encaja':return 'no_encaja'
    known=[level for level in (current,found) if level in LEVELS and level!='no_encaja']
    return min(known,key=LEVEL_RANK.get) if known else 'por_confirmar'

# --------------------------------------------------------------------------- the web question per profile

def company_of(headline):
    """The company a headline names after «@» or «at» («Founder & CEO at Acme Robotics · …» → «Acme Robotics»), or ''."""
    match=re.search(r'(?:@\s*|\bat\s+)([A-Za-z0-9][\w&.\'-]*(?:\s+[A-Za-z0-9][\w&.\'-]*){0,3})',headline or '')
    return match.group(1).strip(' .') if match else ''

def stage_question(contact,public):
    """The public question of the web check for the buyer's profile, at most 300 characters (research.safe_question).
    `public` is red's sanitizer: it takes out what the question must not carry (handles, our/my, digit runs)."""
    name=public(contact.display_name) or contact.display_name
    company=public(company_of(contact.headline))
    tail=QUESTIONS.get(_buyer(contact).get('profile'),DEFAULT_QUESTION)['web'].format(company=company or f'the company of {name}')
    headline=public(contact.headline)[:max(0,300-len(name)-len(tail)-5)].strip()
    return (f'{name} ({headline}). ' if headline else f'{name}. ')+tail

def from_classifier(contact,result,fit):
    """The buyer block the classifier leaves, before the web check: its profile, level and evidence (the profile)."""
    level=result.get('buyer_level')
    if level not in LEVELS:level='por_confirmar' if fit else 'no_encaja'  # an answer without a level
    return {'profile':result.get('buyer_profile') if result.get('buyer_profile') in PROFILES else '','level':level,
            'us_market':bool(result.get('us_market')),'evidence':(result.get('reason') or '')[:400],
            'sources':[contact.profile_url] if contact.profile_url else [],'basis':'perfil'}

def judge_question(contact):
    return QUESTIONS.get(_buyer(contact).get('profile'),DEFAULT_QUESTION)['juez']

# --------------------------------------------------------------------------- score

SCORE_VERSION='buyer_score_v1'
# The level weighs most. Within one market tier, the spacing of the levels (17) is larger than everything else can add
# (papel 6 + servicios 6 + confianza 2): a level is never overtaken by a lower one in the same tier.
EVIDENCE={'confirmado':50,'probable':33,'por_confirmar':16,'no_encaja':0}
MARKET={'objetivo':20,'negocio_en_eeuu':14,'sin_dato':12,'latam':8,'otro':4}
ROLE={'decide':12,'sin_dato':9,'influye':6}
SERVICES={'coincide':12,'sin_dato':9,'no_coincide':6}
CONFIDENCE_MAX=6
DECIDES=re.compile(r'(?<![a-z])(co-?founder|cofundador\w*|founder|fundador\w*|owner|duen[oa]|ceo|cto|coo|cpo|chief \w+ officer|'
                   r'president\w*|managing director)(?![a-z])')
INFLUENCES=re.compile(r'(?<![a-z])(vp|vice president|head of|director\w*|gerente|manager|lead)(?![a-z])')
# What Gustavo builds (posicionamiento.SERVICES and its pillars): software, product, applied AI, technical leadership.
TECH=re.compile(r'(?<![a-z])(software|saas|ai|ia|llm\w*|machine learning|artificial intelligence|inteligencia artificial|apps?|'
                r'platform\w*|plataforma\w*|products?|producto\w*|mvp|api\w*|\w*tech|tecnolog\w*|technolog\w*|engineering|'
                r'ingenier\w*|developer\w*|development|desarroll\w*|data|datos|automat\w*|marketplace\w*|digital)(?![a-z])')

def _plain(text):
    text=unicodedata.normalize('NFKD',(text or '').lower())
    return ''.join(ch for ch in text if not unicodedata.combining(ch))

def thin(contact):
    """A brief profile: a headline of at most four words and no bio. Only a notice, never fewer points."""
    return len((contact.headline or '').split())<=4 and not ((contact.signals or {}).get('bio') or '').strip()

def target_region():
    from . import red
    return red.buyer_region()

def in_market(contact):
    """In the target market, or with business or customers there (the classifier's us_market)."""
    from . import ubicacion
    target=target_region()
    return not target or ubicacion.region(contact.location)==target or bool(_buyer(contact).get('us_market'))

def _market(contact):
    from . import ubicacion
    region=ubicacion.region(contact.location);target=target_region()
    if not target or region==target:return 'objetivo',f'Mercado objetivo ({region or "sin preferencia"})'
    if _buyer(contact).get('us_market'):return 'negocio_en_eeuu','Negocio o clientes en EE. UU. desde otra región'
    if region is None:return 'sin_dato','Sin ubicación: valor neutro'
    return ('latam','Latinoamérica') if region=='latam' else ('otro','Otra región')

def _role(contact):
    text=_plain(contact.headline)
    if DECIDES.search(text):return 'decide',f'Su titular dice «{DECIDES.search(text).group(1)}»'
    if _buyer(contact).get('profile') in FOUNDER_PROFILES:return 'decide','El clasificador lo ve como founder'
    if INFLUENCES.search(text):return 'influye',f'Su titular dice «{INFLUENCES.search(text).group(1)}»'
    return 'sin_dato','Su titular no dice su cargo: valor neutro'

def _services(contact):
    text=_plain(' '.join([contact.headline or '',(contact.signals or {}).get('bio') or '',(contact.evidence or {}).get('comment') or '']))
    match=TECH.search(text)
    if match:return 'coincide',f'Construye software, producto o IA («{match.group(1)}»)'
    if thin(contact):return 'sin_dato','Perfil escueto: valor neutro'
    return 'no_coincide','Su perfil no habla de software, producto ni IA'

def score(contact,level=None):
    """{score, breakdown: {component: {points, max, value, why}}, warnings, version, level} for a buyer; {} otherwise.
    The points of the breakdown always add up to the score."""
    level=level or level_of(contact)
    if level is None:return {}
    market,market_why=_market(contact);role,role_why=_role(contact);services,services_why=_services(contact)
    confidence=max(0.0,min(1.0,float((contact.classification or {}).get('confidence') or 0)))
    breakdown={
        'evidencia':{'points':EVIDENCE[level],'max':EVIDENCE['confirmado'],'value':level,'why':'Nivel de evidencia de etapa'},
        'mercado':{'points':MARKET[market],'max':MARKET['objetivo'],'value':market,'why':market_why},
        'papel':{'points':ROLE[role],'max':ROLE['decide'],'value':role,'why':role_why},
        'servicios':{'points':SERVICES[services],'max':SERVICES['coincide'],'value':services,'why':services_why},
        'confianza':{'points':round(CONFIDENCE_MAX*confidence),'max':CONFIDENCE_MAX,'value':round(confidence,2),
                     'why':'Confianza del clasificador'},
    }
    warnings=[THIN_NOTICE] if thin(contact) else []
    if market=='sin_dato':warnings.append('sin ubicación')
    return {'score':sum(part['points'] for part in breakdown.values()),'breakdown':breakdown,'warnings':warnings,
            'version':SCORE_VERSION,'level':level}

def with_score(contact,buyer):
    """`buyer` (the classification's buyer block) with the score of its level; contact.classification is not changed."""
    previous=contact.classification
    contact.classification=dict(previous or {},buyer=buyer)
    try:result=score(contact,buyer.get('level'))
    finally:contact.classification=previous
    return dict(buyer,score=result.get('score'),score_breakdown=result.get('breakdown'),score_version=SCORE_VERSION,
                warnings=result.get('warnings',[]))

# --------------------------------------------------------------------------- entry, kept once

def record_entry(contact,now=None):
    """The level and score the buyer entered the neighborhood with: one audit event per person, never overwritten (a
    reclassification keeps the first). Returns the entry, which classify copies into the buyer block."""
    from .models import AuditEvent
    from . import operador
    event=AuditEvent.objects.filter(action=ENTRY_ACTION,target=str(contact.pk)).order_by('created_at','id').first()
    if event:return {k:event.metadata.get(k) for k in ('level','score','version','profile','at')}
    buyer=_buyer(contact);now=now or timezone.now()
    entry={'level':buyer.get('level'),'score':buyer.get('score'),'version':SCORE_VERSION,'profile':buyer.get('profile',''),
           'at':now.isoformat()}
    operador._audit(None,ENTRY_ACTION,contact.pk,**entry)
    return entry

BANDS=((80,'80-100'),(60,'60-79'),(40,'40-59'),(0,'0-39'))

def band(value):
    return next(label for floor,label in BANDS if (value or 0)>=floor)

def entry_funnel(account=None):
    """Read only: the buyers by the level and the score band they entered with, and how many were followed, invited and
    accepted since. The whole funnel (warm-up, messages, answers) lives in the outbound branch."""
    from .models import AuditEvent, Contact
    entries={e.target:e.metadata for e in AuditEvent.objects.filter(action=ENTRY_ACTION).order_by('created_at','id')}
    contacts=Contact.objects.filter(pk__in=list(entries))
    if account is not None:contacts=contacts.filter(account=account)
    empty=lambda:{'entraron':0,'seguidos':0,'invitados':0,'aceptaron':0}
    out={'por_nivel':{level:empty() for level in LEVELS if level!='no_encaja'},'por_puntaje':{label:empty() for _,label in reversed(BANDS)},
         'version':SCORE_VERSION}
    for contact in contacts:
        entry=entries.get(str(contact.pk)) or {}
        rows=[out['por_nivel'].setdefault(entry.get('level') or 'sin_nivel',empty()),out['por_puntaje'][band(entry.get('score'))]]
        for row in rows:
            row['entraron']+=1;row['seguidos']+=bool(contact.followed_at);row['invitados']+=bool(contact.invited_at)
            row['aceptaron']+=bool(contact.connected_at)
    return out
