"""The buyer of the neighborhood: what kind of buyer, how much evidence there is, and an explainable score (BAR-24).

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
  (red.prioritized, with the outbound temperature: priority()) and never excludes anyone. A thin profile never loses
  points: missing data takes the middle value of its component and only raises a notice.
- entry (entry_of): the level and score the team went after a buyer with, on BuyerJourney (entry_level, entry_score).
  comprador keeps them in step with her level while she is only chosen and fixes them at the first follow or
  invitation; never overwritten after. They compare whether the «por confirmar» accept and answer like the confirmed
  ones (entry_funnel, inside comprador.funnel)."""
import re
import unicodedata
from datetime import timedelta

from django.utils import timezone

from . import projectapp

# BAR-25 (NETWORK_PROJECTAPP_BUYER_ENABLED): two more profiles, the buyers of the ProjectApp line (projectapp.PROFILES).
# With the switch off the classifier's schema never offers them.
PROFILES=('startup_financiada','bootstrapped','stealth','ejecutivo',*projectapp.PROFILES)
FOUNDER_PROFILES=('startup_financiada','bootstrapped','stealth')
LEVELS=('confirmado','probable','por_confirmar','no_encaja')
LEVEL_RANK={level:n for n,level in enumerate(LEVELS)}
# Verdicts of the web check until 17/11/2026: «sin_evidencia» was the absence of evidence, now por_confirmar.
LEGACY_VERDICTS={'semilla_o_mas':'confirmado','presemilla':'no_encaja','sin_evidencia':'por_confirmar'}
THIN_NOTICE='perfil con poca información'

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
    # BAR-25: the ProjectApp buyer. The same research call also asks for the size (tamano) and the class 08 signals
    # (red.STAGE_SCHEMA_PROJECTAPP): hiring developers, a digital launch, a legacy system to replace, growth.
    'dueno_empresa_tradicional':{
        'web':'{company}: number of employees, industry, location in the United States; open software or IT jobs, new '
              'digital products, online store or platform, legacy systems being replaced, growth or new locations.',
        'juez':'Dueño o CEO de una empresa tradicional en EE. UU.: ¿cuántas personas tiene (el objetivo es de 20 a 200) y '
               'opera de verdad (clientes, sedes, años)? Una fuente que muestre la empresa operando con un tamaño de 20 a 200 '
               'es confirmado; la empresa operando sin tamaño, o el tamaño sin operación, probable; más de 1000 personas, '
               'cerrada, o la persona no es dueña ni dirige, no_encaja.'},
    'lider_tecnologia':{
        'web':'{company}: number of employees, industry, location in the United States; who leads technology; open software '
              'engineering or IT jobs, new digital products, legacy systems being replaced, growth.',
        'juez':'Líder de tecnología (CTO, VP, Head o Director de ingeniería o TI, gerente de sistemas) de una empresa '
               'tradicional en EE. UU.: ¿cuántas personas tiene (el objetivo es de 20 a 200) y la persona dirige tecnología '
               'allí? Una fuente con la empresa operando, de 20 a 200 personas, y su cargo es confirmado; la empresa operando '
               'sin tamaño, probable; más de 1000 personas, cerrada, o no dirige tecnología (vende o recluta), no_encaja.'},
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

# --------------------------------------------------------------------------- the level decides (18/11/2026)
# Measured in production on 18/11/2026: of 16 buyers classified after BAR-24/BAR-25, 10 left the neighborhood with level
# por_confirmar (9) or probable (1). The model answered fit=false next to a level that keeps the person («es una hipótesis
# de comprador», «tamaño no consta»), its confidence for a hypothesis sat under NETWORK_MIN_CONFIDENCE, and red._classify_batch
# took that fit. From now on a buyer's fit is derived from her level in code: only no_encaja leaves, and no_encaja needs
# one of these motives (the classifier's `buyer_against`, the web check's `en_contra`); without one it is por_confirmar.
# «Tamaño no consta», «sin datos públicos» or «es una hipótesis» are not motives: they are the absence of evidence.
AGAINST={
    'no_decide':'no es dueño, founder ni decide: vende, recluta o ejecuta para otros',
    'vende_servicios':'vive de vender sus servicios profesionales (consultor, freelance, coach, agencia) en vez de dirigir una '
                      'empresa con producto u operación propia',
    'competidor_software':'su empresa vende desarrollo de software (competidor de ProjectApp)',
    'demasiado_grande':'empresa de más de 1000 personas (línea ProjectApp)',
    'idea_sin_empresa':'idea sin empresa, estudiante, o presemilla declarada sin ingresos',
    'empresa_cerrada':'la empresa cerró o ya no opera',
    'no_contactar':'pide no ser contactado',
}
# What a web source can show against (the web never sees a «do not contact» or a student better than the profile did).
AGAINST_WEB=('no_decide','competidor_software','demasiado_grande','idea_sin_empresa','empresa_cerrada')
# The one motive that wins over any level: whoever asks not to be contacted is never contacted.
ALWAYS_OUT=('no_contactar',)
OVERRIDDEN='network.buyer_fit_overridden'
CORRECTIONS={'fit_del_modelo':'el fit del modelo contradecía su nivel: gana el nivel',
             'no_encaja_sin_motivo':'no_encaja sin un motivo válido de evidencia en contra: queda por_confirmar',
             'sin_nivel':'comprador sin nivel: por_confirmar (o no_encaja si dio un motivo válido)',
             'motivo_sin_no_encaja':'un motivo de evidencia en contra con un nivel que no es no_encaja: gana el nivel',
             'no_contactar':'pide no ser contactado: no_encaja aunque el nivel dijera otra cosa'}

def decide(result):
    """(level, against, corrections) of the classifier's answer about a buyer. The level decides; the model's `fit` and
    its confidence never do. `against` is the motive of a no_encaja (AGAINST) or ''; `corrections` names each place the
    answer contradicted itself (CORRECTIONS), for the audit."""
    level=result.get('buyer_level');against=result.get('buyer_against') if result.get('buyer_against') in AGAINST else ''
    corrections=[]
    if level not in LEVELS:
        level='no_encaja' if against else 'por_confirmar';corrections.append('sin_nivel')
    if against in ALWAYS_OUT and level!='no_encaja':level='no_encaja';corrections.append('no_contactar')
    if level=='no_encaja' and not against:level='por_confirmar';corrections.append('no_encaja_sin_motivo')
    if level!='no_encaja' and against:against='';corrections.append('motivo_sin_no_encaja')
    if 'fit' in result and bool(result.get('fit'))!=(level!='no_encaja'):corrections.append('fit_del_modelo')
    return level,against,corrections

def web_verdict(verdict,against):
    """The web check's level: a no_encaja without a motive a web source can show (AGAINST_WEB) is por_confirmar."""
    if verdict=='no_encaja' and against not in AGAINST_WEB:return 'por_confirmar',''
    return verdict,(against if verdict=='no_encaja' else '')

def record_correction(contact,result,level,against,corrections,source='clasificador',fit=None):
    """One audit event per buyer whose answer contradicted itself (OVERRIDDEN): what the model said and what the code
    kept. `fit`: what she ended with after every rule (an uncited verdict, a colleague…); by default, her level's.
    corrections_count() reads them back."""
    if not corrections:return
    from . import operador
    operador._audit(None,OVERRIDDEN,contact.pk,source=source,model_fit=result.get('fit'),model_level=result.get('buyer_level'),
                    model_against=result.get('buyer_against',''),level=level,against=against,
                    fit=level!='no_encaja' if fit is None else bool(fit),
                    corrections=list(corrections),account=str(contact.account_id),reason=(result.get('reason') or '')[:200])

def corrections_count(since,until=None,accounts=None):
    """{total, por_correccion: {correction: n}, entraron: n}: the buyers whose fit the code derived against what the model
    said, since `since` (read only; `accounts` narrows to those accounts)."""
    from .models import AuditEvent
    events=AuditEvent.objects.filter(action=OVERRIDDEN,created_at__gte=since)
    if until is not None:events=events.filter(created_at__lt=until)
    if accounts is not None:events=events.filter(metadata__account__in=[str(a) for a in accounts])
    counts={};kept=0
    for meta in events.values_list('metadata',flat=True):
        for name in meta.get('corrections') or []:counts[name]=counts.get(name,0)+1
        kept+=int(bool(meta.get('fit')) and meta.get('model_fit') is False)
    return {'total':events.count(),'por_correccion':counts,'entraron':kept}

def from_classifier(contact,result,level,against=''):
    """The buyer block the classifier leaves, before the web check: its profile, level (decide) and evidence (the
    profile); `against`, the motive of a no_encaja."""
    buyer={'profile':result.get('buyer_profile') if result.get('buyer_profile') in PROFILES else '','level':level,
           'us_market':bool(result.get('us_market')),'evidence':(result.get('reason') or '')[:400],
           'sources':[contact.profile_url] if contact.profile_url else [],'basis':'perfil'}
    if against:buyer['against']=against
    return buyer

def judge_question(contact):
    return QUESTIONS.get(_buyer(contact).get('profile'),DEFAULT_QUESTION)['juez']

def papel_of(contact):
    """BAR-25: what a ProjectApp buyer is inside her company, `dueno` or `lider_tecnologia` ('' when the headline does
    not say it); '' for anyone who is not a ProjectApp buyer."""
    return projectapp.papel_of(contact) if projectapp.line_of(contact)=='projectapp' else ''

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
    The points of the breakdown always add up to the score. With NETWORK_PROJECTAPP_BUYER_ENABLED, buyer_score_v2."""
    level=level or level_of(contact)
    if level is None:return {}
    if projectapp.enabled():return score_v2(contact,level)
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

# --------------------------------------------------------------------------- score v2 (BAR-25)

SCORE_VERSION_V2='buyer_score_v2'
# v2, with NETWORK_PROJECTAPP_BUYER_ENABLED. The startup line keeps v1's components and points. The ProjectApp line
# weighs what Gustavo asked for on 17/11/2026: the size (20 to 200 people), the class 08 signal with its source and
# date (hiring developers first, LI-08-M004-K01/K02: «la señal no crea campañas, decide a quién primero») and whether
# the person decides on technology (owner/CEO or technology leader, LI-08-M001-K05). In both lines a missing datum takes
# exactly the middle of its component's known values (sin_dato), so a thin profile never loses points; it only raises a
# notice. Each component's points and why go in the breakdown, which always adds up to the score.
V2_EVIDENCE={'confirmado':32,'probable':21,'por_confirmar':10,'no_encaja':0}
V2_SIZE={'20_a_200':26,'sin_dato':13,'201_a_1000':8,'menos_de_20':2,'mas_de_1000':0}
V2_SIGNAL={'contrata_desarrolladores':10,'reciente':8,'antigua':6,'sin_dato':5}
V2_MARKET={'objetivo':14,'negocio_en_eeuu':10,'sin_dato':8,'latam':4,'otro':2}
V2_PAPEL={'decide':12,'sin_dato':8,'otro':4}
V2_CONFIDENCE_MAX=6
SIGNAL_RECENT=timedelta(days=90)  # «más reciente y más cerca, más fuerte» (LI-08-M004-K01): age when the web check saw it

def _size(contact):
    size=projectapp.size_of(contact)
    if not size:return 'sin_dato','La empresa no dice su tamaño: valor neutro'
    basis='la web' if _buyer(contact).get('size_basis')=='web' else 'su perfil'
    return size,f'{projectapp.SIZE_LABELS[size].capitalize()} según {basis}'

def _signal(contact):
    """The strongest class 08 signal with its source and date: hiring developers, then any other, recent or old."""
    from . import calentamiento
    best=None
    for s in calentamiento.buying_signals(contact):
        at=calentamiento._signal_date(s);seen=_seen(s)
        if at is None:continue  # a signal needs a date (17/11/2026)
        recent=seen is None or seen-at<=SIGNAL_RECENT
        value='contrata_desarrolladores' if recent and s['tipo']=='contrata_desarrolladores' else 'reciente' if recent else 'antigua'
        if best is None or V2_SIGNAL[value]>V2_SIGNAL[best[0]]:best=(value,s)
    if best is None:return 'sin_dato','Sin señal con fuente y fecha: valor neutro'
    value,s=best
    return value,f'{calentamiento.SIGNAL_LABELS.get(s["tipo"],s["tipo"])} ({s.get("fecha")}, {s["fuente"]})'

def _seen(signal):
    from django.utils.dateparse import parse_datetime
    try:return parse_datetime(str(signal.get('visto') or ''))
    except ValueError:return None

def _papel_v2(contact):
    papel=projectapp.papel_of(contact)
    if papel:return 'decide',f'{projectapp.PAPEL_LABELS[papel]}: decide sobre tecnología'
    if thin(contact):return 'sin_dato','Su titular no dice su cargo: valor neutro'
    return 'otro','Ni dueño ni líder de tecnología según su titular'

def score_v2(contact,level):
    """buyer_score_v2: v1's components for the startup line; for the ProjectApp line evidence, size, signal, market,
    papel and confidence (V2_*)."""
    confidence=max(0.0,min(1.0,float((contact.classification or {}).get('confidence') or 0)))
    market,market_why=_market(contact)
    if projectapp.line_of(contact)!='projectapp':
        role,role_why=_role(contact);services,services_why=_services(contact)
        breakdown={
            'evidencia':{'points':EVIDENCE[level],'max':EVIDENCE['confirmado'],'value':level,'why':'Nivel de evidencia de etapa'},
            'mercado':{'points':MARKET[market],'max':MARKET['objetivo'],'value':market,'why':market_why},
            'papel':{'points':ROLE[role],'max':ROLE['decide'],'value':role,'why':role_why},
            'servicios':{'points':SERVICES[services],'max':SERVICES['coincide'],'value':services,'why':services_why},
            'confianza':{'points':round(CONFIDENCE_MAX*confidence),'max':CONFIDENCE_MAX,'value':round(confidence,2),
                         'why':'Confianza del clasificador'}}
        line='startup'
    else:
        size,size_why=_size(contact);signal,signal_why=_signal(contact);papel,papel_why=_papel_v2(contact)
        breakdown={
            'evidencia':{'points':V2_EVIDENCE[level],'max':V2_EVIDENCE['confirmado'],'value':level,'why':'Nivel de evidencia'},
            'tamano':{'points':V2_SIZE[size],'max':V2_SIZE['20_a_200'],'value':size,'why':size_why},
            'senal':{'points':V2_SIGNAL[signal],'max':V2_SIGNAL['contrata_desarrolladores'],'value':signal,'why':signal_why},
            'mercado':{'points':V2_MARKET[market],'max':V2_MARKET['objetivo'],'value':market,'why':market_why},
            'papel':{'points':V2_PAPEL[papel],'max':V2_PAPEL['decide'],'value':papel,'why':papel_why},
            'confianza':{'points':round(V2_CONFIDENCE_MAX*confidence),'max':V2_CONFIDENCE_MAX,'value':round(confidence,2),
                         'why':'Confianza del clasificador'}}
        line='projectapp'
    warnings=[THIN_NOTICE] if thin(contact) else []
    if market=='sin_dato':warnings.append('sin ubicación')
    if line=='projectapp' and breakdown['tamano']['value']=='sin_dato':warnings.append('sin tamaño de empresa')
    return {'score':sum(part['points'] for part in breakdown.values()),'breakdown':breakdown,'warnings':warnings,
            'version':SCORE_VERSION_V2,'level':level,'line':line}

def score_version():
    return SCORE_VERSION_V2 if projectapp.enabled() else SCORE_VERSION

def with_score(contact,buyer):
    """`buyer` (the classification's buyer block) with the score of its level; contact.classification is not changed."""
    previous=contact.classification
    contact.classification=dict(previous or {},buyer=buyer)
    try:result=score(contact,buyer.get('level'))
    finally:contact.classification=previous
    return dict(buyer,score=result.get('score'),score_breakdown=result.get('breakdown'),score_version=score_version(),
                warnings=result.get('warnings',[]))

# --------------------------------------------------------------------------- with the temperature of the outbound

# priority = score + TEMPERATURE_POINTS × min(weight, TEMPERATURE_CAP). The score says who the person is (evidence,
# market, role, fit); the temperature (calentamiento.weigh: Máxima 5, Alta 3, Media 1, buying signals 2, half after
# 30 days) says what she did back. One Alta signal (+15) is worth about one level (17 points); the weight counts up to
# 8 (+40), so what a person does can lift her over a stronger profile, never without limit.
TEMPERATURE_POINTS=5
TEMPERATURE_CAP=8

def priority(score_value,weight=0):
    return (score_value or 0)+TEMPERATURE_POINTS*min(max(float(weight or 0),0.0),TEMPERATURE_CAP)

# --------------------------------------------------------------------------- entry, fixed by the first follow or invitation

def entry_of(contact):
    """The entry fields of the buyer's journey for her current level and score (comprador._project), or {}."""
    result=score(contact)
    if not result:return {}
    return {'entry_level':result['level'],'entry_score':result['score'],'entry_score_version':result['version']}

BANDS=((80,'80-100'),(60,'60-79'),(40,'40-59'),(0,'0-39'))

def band(value):
    return next(label for floor,label in BANDS if (value or 0)>=floor)

ENTRY_STAGES=(('elegidos',lambda j:True),('seguidos',lambda j:j.warming_at is not None),
              ('calentados',lambda j:j.comments_before_invite>=1),('invitados',lambda j:j.invited_at is not None),
              ('aceptaron',lambda j:j.accepted_at is not None),('respondieron',lambda j:j.replied_at is not None))

def entry_funnel(journeys):
    """Read only, for comprador.funnel: the journeys by the level and the score band they entered with, and how many of
    each were followed, warmed (a comment before the invitation), invited, accepted and answered."""
    def counts(group):
        return {name:sum(1 for j in group if reached(j)) for name,reached in ENTRY_STAGES}
    journeys=list(journeys)
    levels=[*[level for level in LEVELS if level!='no_encaja'],'no_encaja','sin_nivel']
    by_level={level:counts([j for j in journeys if (j.entry_level or 'sin_nivel')==level]) for level in levels}
    by_band={label:counts([j for j in journeys if j.entry_score is not None and band(j.entry_score)==label]) for _,label in BANDS}
    by_band['sin_puntaje']=counts([j for j in journeys if j.entry_score is None])
    return {'por_nivel':by_level,'por_puntaje':by_band,'version':score_version()}

# --------------------------------------------------------------------------- who left before 17/11/2026

REEVALUATED='network.buyer_reevaluated'
REGION_RULE='Comprador fuera de EE. UU.'
# The classifier's reasons for a buyer it discarded for lack of public evidence, not for evidence against.
ABSENCE=re.compile(r'sin evidencia|no hay evidencia|ninguna evidencia|hip[oó]tesis|falta (?:de )?(?:informaci[oó]n|evidencia|datos)|'
                   r'sin (?:datos|informaci[oó]n|se[nñ]ales)|no (?:se )?(?:muestra|ve|menciona|consta|indica|declara)|'
                   r'no (?:est[aá] )?claro|insuficiente|sin (?:ronda|clientes|tracci[oó]n) visible',re.I)
# What a person's memory keeps when Gustavo (a veto, a discard) or LinkedIn (a restricted profile) said no.
SAID_NO=('rejected','discarded')
# 18/11/2026: the buyers the classifier's fit took out with a level that keeps them (red.classifier_fit). They already
# have level, line, segment and evidence: they come back as they were, with their score, without a paid call.
LEFT_BY_FIT='descartado_con_nivel'
KEPT_LEVELS=('confirmado','probable','por_confirmar')
ACTIONS={'fuera_de_eeuu':'restaurar','sin_evidencia_web':'restaurar','sin_evidencia_clasificador':'reclasificar',
         'sin_nivel':'completar',LEFT_BY_FIT:'restaurar'}

def left_by_model_fit(contact):
    """A buyer who left the neighborhood with a level that keeps her: stage discarded, not fit, a stored level other than
    no_encaja, no rule of the code (a size, a missing citation, the organization) and no web check against. Before
    18/11/2026 that was the model's fit=false (or its confidence) overriding her level; after it, it should not happen."""
    c=contact.classification or {};buyer=c.get('buyer') or {}
    return (c.get('role')=='comprador' and contact.stage=='discarded' and not c.get('fit') and buyer.get('level') in KEPT_LEVELS
            and not c.get('rule') and (c.get('stage_check') or {}).get('state')!='failed')
# BAR-25 (NETWORK_PROJECTAPP_BUYER_ENABLED): the buyers of before get their line (and segment), whoever was not acted on
# yet goes back to the classifier to be judged with both lines, and the agencies discarded for selling to «another
# public» go back to it too, because they may be partners.
ACTIONS_PROJECTAPP={'linea':'completar','otra_linea':'reclasificar','posible_partner':'reclasificar'}
PARTNER_ROLES=('aliado','recomendador','divulgador')
AGENCY=re.compile(r'(?<![a-z])(agenc(?:y|ia|ies|ias)|studio|estudio|consultanc(?:y|ies)|consultora|consulting)(?![a-z])')
AGENCY_WORK=re.compile(r'(?<![a-z])(marketing|design|disen\w*|brand\w*|web\w*|digital|product\w*|ux|creativ\w*|growth)(?![a-z])')
OPEN_STATES=('proposed','approved','executing','sent','uncertain')
REQUEUED_PROJECTAPP=('Vuelve al clasificador con el comprador de ProjectApp y el partner (17/11/2026): puede ser de la otra '
                     'línea o un partner.')


def actions():
    return {**ACTIONS,**ACTIONS_PROJECTAPP} if projectapp.enabled() else dict(ACTIONS)


def _projectapp_group(contact):
    """BAR-25: linea (a fitting buyer in course without a line: completar, by her profile), otra_linea (one the team has
    not acted on yet: reclasificar, so the classifier may say ProjectApp, startup or partner) or posible_partner (an
    agency discarded as aliado, recomendador or divulgador: reclasificar). None otherwise."""
    c=contact.classification or {};role=c.get('role')
    # Whoever already went back once is not sent again: the classifier judged her with both lines and the partner.
    requeued=any(event.get('event')=='requeued' and event.get('detail')==REQUEUED_PROJECTAPP[:300] for event in contact.history or [])
    if role=='comprador' and c.get('fit') and contact.stage in ('fit','followed','invited','connected') and not (c.get('buyer') or {}).get('line'):
        untouched=(contact.stage=='fit' and not c.get('confirmed_by_gustavo') and not contact.followed_at and not contact.invited_at
                   and not contact.proposals.filter(state__in=OPEN_STATES).exists())
        return 'otra_linea' if untouched and not requeued else 'linea'
    if role in PARTNER_ROLES and not c.get('fit') and contact.stage=='discarded' and not requeued:
        text=_plain(' '.join([contact.headline or '',(contact.signals or {}).get('bio') or '',c.get('reason') or '']))
        if AGENCY.search(text) and AGENCY_WORK.search(text):return 'posible_partner'
    return None


def reevaluation_group(contact):
    """Why a buyer is reevaluated under the levels of 17/11/2026, or None:
    - fuera_de_eeuu: the region rule of 12/11 took out someone the classifier said fits (restaurar, in place);
    - sin_evidencia_web: three web checks without findings took them out (restaurar, por_confirmar, no new search);
    - sin_evidencia_clasificador: the classifier said no for lack of public evidence (reclasificar: back to the queue,
      the normal classify job judges them with the new prompt);
    - sin_nivel: a buyer in course without level or score (completar, nothing else changes);
    - descartado_con_nivel (18/11/2026): the classifier's fit took her out with a level that keeps her (restaurar, with
      her level, line, segment, evidence and score; no paid call). It goes before sin_evidencia_clasificador, whose
      «sin datos» reasons she often carries, so she is never sent to be classified (and paid) again.
    Nobody Gustavo or LinkedIn said no to, nobody he confirmed, nobody invited, connected or closed."""
    c=contact.classification or {}
    if any(event.get('event') in SAID_NO for event in contact.history or []):return None
    if left_by_model_fit(contact):return LEFT_BY_FIT
    # BAR-25: a buyer without a level is completed first (with her line); then the line and the partners.
    if projectapp.enabled() and not (c.get('role')=='comprador' and c.get('fit') and contact.stage in ('fit','followed') and not c.get('buyer')):
        group=_projectapp_group(contact)
        if group:return group
    if c.get('role')!='comprador' or c.get('confirmed_by_gustavo') or contact.stage not in ('discarded','fit','followed'):return None
    check=c.get('stage_check') or {};rule=c.get('rule') or ''
    if c.get('fit'):return 'sin_nivel' if contact.stage!='discarded' and not c.get('buyer') else None
    if rule.startswith(REGION_RULE):return 'fuera_de_eeuu'
    if check.get('state')=='failed' and check.get('verdict')=='sin_evidencia':return 'sin_evidencia_web'
    # A buyer already judged with levels has hers: a stored no_encaja is evidence against, even when its reason says
    # «no consta» (until 18/11/2026 a fit=false no_encaja carried no rule), and it is never sent to be paid for again.
    if (not rule and contact.stage=='discarded' and not (c.get('buyer') or {}).get('level')
            and ABSENCE.search(c.get('reason') or '')):return 'sin_evidencia_clasificador'
    return None


def _restored(contact,group,now):
    """The classification of a buyer who comes back in place, at por_confirmar."""
    from . import red
    c=dict(contact.classification);c.pop('rule',None);c['fit']=True
    check=c.get('stage_check') or {}
    if group=='sin_evidencia_web':
        c['stage_check']=dict(check,state='ok',verdict='por_confirmar',reevaluated_at=now.isoformat())
    elif red.stage_check_enabled() and check.get('state')!='ok':c['stage_check']={'state':'pending'}
    buyer={'profile':'','level':'por_confirmar','us_market':False,'evidence':(c.get('reason') or '')[:400],
           'sources':[contact.profile_url] if contact.profile_url else [],'basis':'perfil'}
    if projectapp.enabled():buyer=projectapp.complete(contact,buyer)  # BAR-25: a buyer of before is a startup buyer
    return c,buyer


def reevaluate(user,account,confirm=False,now=None):
    """The buyers who left or stayed without a level under the rules before 17/11/2026, with the action each one gets.
    Without `confirm` it only lists them (no change, no paid call). With it, each one changes in its own transaction
    and leaves an audit event; running it again finds nobody (idempotent). Restoring and completing spend nothing;
    whoever is sent back to the classifier is judged by the normal classify job, in its batches and budget."""
    from django.db import transaction
    from . import comprador, operador, red
    from .evidencia import record_classification
    from .models import Contact
    from .permissions import require
    require(user,'operate_linkedin')
    now=now or timezone.now()
    rows=[];groups=actions()
    roles=('comprador',*PARTNER_ROLES) if projectapp.enabled() else ('comprador',)
    from . import registro
    # Whoever another member attends, or the organization excluded, is not brought back (organizaciones, phase 6); with
    # one member nobody is held here.
    held=registro.gate(operador.member_of(account=account),account)
    for contact in Contact.objects.filter(account=account,classification__role__in=roles).order_by('discovered_at'):
        group=reevaluation_group(contact)
        if group is None or (groups.get(group)=='restaurar' and held(contact)):continue
        level='por_confirmar' if group not in ('sin_nivel',LEFT_BY_FIT,*ACTIONS_PROJECTAPP) else level_of(contact)
        line=''
        if group=='posible_partner':result={};line='partner?'
        elif group=='sin_nivel' and not projectapp.enabled():result=score(contact,level)
        elif group in ('sin_nivel','linea','otra_linea',LEFT_BY_FIT):
            previous=contact.classification
            buyer=dict((previous or {}).get('buyer') or {})
            if group!=LEFT_BY_FIT or (projectapp.enabled() and not buyer.get('line')):buyer=projectapp.complete(contact,buyer)
            contact.classification=dict(previous,fit=True,buyer=buyer) if group==LEFT_BY_FIT else dict(previous,buyer=buyer)
            line=buyer.get('line') or ''
            try:result=score(contact,level)
            finally:contact.classification=previous
        else:
            previous=contact.classification
            buyer=_restored(contact,group,now)[1];line=buyer.get('line') or ''
            contact.classification=dict(previous,fit=True,buyer=buyer)
            try:result=score(contact,level)
            finally:contact.classification=previous
        row={'id':str(contact.pk),'name':contact.display_name,'group':group,'action':groups[group],'level':level,
             'score':result.get('score'),'provisional':groups[group]=='reclasificar',
             'reason':((contact.classification or {}).get('rule') or (contact.classification or {}).get('reason') or '')[:160]}
        if projectapp.enabled():row['line']=line
        rows.append(row)
    rows.sort(key=lambda row:(-(row['score'] or 0),row['name']))
    found={group:sum(row['group']==group for row in rows) for group in groups}
    applied=0
    if confirm:
        for row in rows:
            with transaction.atomic():
                contact=Contact.objects.select_for_update().get(pk=row['id'])
                group=reevaluation_group(contact)
                if group!=row['group'] or contact.proposals.filter(state__in=['executing','sent','uncertain']).exists():continue
                if groups[group]=='restaurar' and held(contact):continue
                if group==LEFT_BY_FIT:
                    # Her own level, line, segment and evidence; only the fit, the stage, the score and (with the web check
                    # on) a pending check change. Nothing is paid here.
                    classification=dict(contact.classification,fit=True)
                    if red.stage_check_enabled() and (classification.get('stage_check') or {}).get('state')!='ok':
                        classification['stage_check']={'state':'pending'}
                    buyer=dict(classification.get('buyer') or {})
                    if projectapp.enabled() and not buyer.get('line'):buyer=projectapp.complete(contact,buyer)
                    contact.classification=classification
                    contact.classification['buyer']=with_score(contact,buyer)
                    red._stage(contact,'fit','reevaluated',f"Vuelve al barrio con su nivel {buyer['level']} (18/11/2026): el fit del "
                               'modelo la había sacado; solo no_encaja con evidencia en contra saca a un comprador.')
                elif group=='sin_evidencia_clasificador':
                    contact.classification={}
                    red._stage(contact,'candidate','requeued','Vuelve al clasificador con los niveles del comprador (17/11/2026): '
                               'antes salió por falta de evidencia pública.')
                elif group in ('otra_linea','posible_partner'):
                    contact.classification={}
                    red._stage(contact,'candidate','requeued',REQUEUED_PROJECTAPP)
                elif group in ('sin_nivel','linea'):
                    buyer=dict(contact.classification.get('buyer') or {},level=level_of(contact))
                    buyer.setdefault('evidence',(contact.classification.get('reason') or '')[:400])
                    buyer.setdefault('sources',[contact.profile_url] if contact.profile_url else [])
                    buyer.setdefault('basis','perfil')
                    if projectapp.enabled():buyer=projectapp.complete(contact,buyer)
                    contact.classification=dict(contact.classification,buyer=with_score(contact,buyer))
                    what=f"línea {buyer['line']}" if group=='linea' else f"nivel {buyer['level']} y puntaje"
                    red.note(contact,'reevaluated',f"{what.capitalize()} del comprador (17/11/2026).")
                else:
                    classification,buyer=_restored(contact,group,now)
                    contact.classification=classification
                    contact.classification['buyer']=with_score(contact,buyer)
                    stage='fit' if contact.stage=='discarded' else contact.stage
                    red._stage(contact,stage,'reevaluated','Vuelve al barrio por confirmar (17/11/2026): solo la evidencia en '
                               'contra saca a un comprador.')
                contact.save()
                if contact.classification:record_classification(contact,observed_at=now)
                operador._audit(user,REEVALUATED,contact.pk,group=group,step=groups[group],score=row['score'])
                applied+=1
            comprador.on_contact(contact,'reevaluacion')  # the journey (and its entry) of whoever is a buyer again
    return {'found':found,'total':len(rows),'applied':applied,'people':rows}
