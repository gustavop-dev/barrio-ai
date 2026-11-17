"""BAR-25: the ProjectApp buyer, the startup buyer and the partner (Gustavo, 17/11/2026).

Gustavo approved it on 17/11/2026: «no se verticaliza el contenido: se verticaliza a quién se le escribe y con qué
prueba». Everything here is behind NETWORK_PROJECTAPP_BUYER_ENABLED (default false). Off, the classifier, the web check,
the searches, the shares of the invitations, the score and the funnel are exactly the ones of before (BAR-24): the
classifier never says «partner», no buyer has a line or a segment and the score is buyer_score_v1.

Three audiences (posicionamiento.PROJECTAPP_BUYER, PARTNER and the startup neighborhood):
- the ProjectApp buyer (line `projectapp`): a traditional company of 20 to 200 people in the United States that needs to
  go digital or already has software and wants more; its owner or CEO (papel `dueno`) or its technology leader (papel
  `lider_tecnologia`: CTO, VP, Head or Director of engineering or IT, systems manager). Soft target: about 60 % technology
  leaders and 40 % owners among the invitations (reparto).
- the startup buyer (line `startup`): the buyer of before (founders of startups with a seed round or later, or paying
  customers, and executives of technology companies).
- the partner (role `partner`, not `aliado`): marketing, design, consulting or product agencies that subcontract the
  development of their clients' software. Followed, commented (the «comunidad» share of the comments) and invited as
  community. No buyer journey and no messages in this phase.

The three-month test (TEST_START to TEST_END, 13 weeks): the segments educacion_en_linea, retail_ecommerce and
duenos_latinos_eeuu, plus otro, measured apart. Nothing is judged under 30 invitations (comprador.SMALL_SAMPLE).

Proof: a case of ProjectApp is cited only to a buyer of the same segment and only with confirmed facts (case_for,
case_issues and the lead's `caso_inventa`). The confirmed facts come from Gustavo's answers to the case questions
(ask_case_questions, queued once by `operador preguntas-casos-projectapp`). No weekly business post is scheduled."""
import os
import re
import unicodedata
from datetime import date, datetime, time, timedelta
from django.utils import timezone

SWITCH='NETWORK_PROJECTAPP_BUYER_ENABLED'
DECIDED='2026-11-17'

def enabled():
    """NETWORK_PROJECTAPP_BUYER_ENABLED=true turns the ProjectApp buyer, the segments and the partner on."""
    return os.environ.get(SWITCH,'false').strip().lower()=='true'

# --------------------------------------------------------------------------- lines, papel, segment, size

LINES=('projectapp','startup')
LINE_LABELS={'projectapp':'Comprador ProjectApp','startup':'Comprador startup'}
# The two kinds of buyer of the ProjectApp line (nivel_comprador.PROFILES) and what each one is inside the company.
PROFILES=('dueno_empresa_tradicional','lider_tecnologia')
PAPEL_OF_PROFILE={'dueno_empresa_tradicional':'dueno','lider_tecnologia':'lider_tecnologia'}
PAPELES=('lider_tecnologia','dueno')
PAPEL_LABELS={'lider_tecnologia':'Líder de tecnología','dueno':'Dueño o CEO'}
# «Meta suave ~60 % líderes técnicos / 40 % dueños» (17/11/2026): whose turn it is inside the ProjectApp buyers' share.
PAPEL_SHARE={'lider_tecnologia':60,'dueno':40}
TECH_LEADER=re.compile(r'(?<![a-z])(cto|cio|chief (?:technology|information|digital) officer|vp (?:of )?(?:engineering|technology|it)|'
                       r'vice president (?:of )?(?:engineering|technology|it)|head of (?:engineering|technology|it|software|systems)|'
                       r'(?:director|gerente|jefe) (?:of |de )?(?:engineering|technology|it|ti|sistemas|tecnolog\w*|ingenier\w*)|'
                       r'it (?:director|manager)|systems manager|engineering manager)(?![a-z])')
OWNER=re.compile(r'(?<![a-z])(owner|co-?owner|duen[oa]|propietari[oa]|ceo|president\w*|presidente|founder|fundador\w*|'
                 r'co-?founder|cofundador\w*|managing director|gerente general|general manager)(?![a-z])')

SEGMENTS=('educacion_en_linea','retail_ecommerce','duenos_latinos_eeuu','otro')
SEGMENT_LABELS={'educacion_en_linea':'Educación en línea','retail_ecommerce':'Retail y e-commerce',
                'duenos_latinos_eeuu':'Dueños latinos en EE. UU.','otro':'Otro'}
INDUSTRY_SEGMENTS=('educacion_en_linea','retail_ecommerce')
LATINO_AFFINITY='hispanohablante_declarada'

SIZES=('menos_de_20','20_a_200','201_a_1000','mas_de_1000')
SIZE_LABELS={'menos_de_20':'menos de 20 personas','20_a_200':'20 a 200 personas','201_a_1000':'201 a 1000 personas',
             'mas_de_1000':'más de 1000 personas'}
# The class 08 signals that a traditional company needs software now (LI-08-M004-K01), strongest first. Each one needs
# a source and a date; the web check of a ProjectApp buyer asks for them in the same call (red.STAGE_SCHEMA_PROJECTAPP).
SIGNAL_KINDS=('contrata_desarrolladores','lanzamiento_digital','sistema_legado','crecimiento')
TARGET_SIZE='20_a_200'
OUT_SIZE='mas_de_1000'
SIZE_RULE=('Empresa de más de 1000 personas: fuera del comprador de ProjectApp (empresas de 20 a 200 personas, Gustavo '
           '17/11/2026).')

def _plain(text):
    text=unicodedata.normalize('NFKD',(text or '').lower())
    return ''.join(ch for ch in text if not unicodedata.combining(ch))

def buyer_of(contact):
    return dict((contact.classification or {}).get('buyer') or {})

def line_for(profile):
    """The line of a buyer profile: the two traditional-company profiles are ProjectApp; every other buyer, startup."""
    return 'projectapp' if profile in PROFILES else 'startup'

def line_in(classification):
    """The line of a classification: `projectapp`, `startup` or None (not a buyer). A buyer classified before the line
    existed is a startup buyer: that is who the classifier looked for until 17/11/2026."""
    c=classification or {}
    if c.get('role')!='comprador':return None
    buyer=c.get('buyer') or {}
    return buyer.get('line') if buyer.get('line') in LINES else line_for(buyer.get('profile'))

def line_of(contact):
    return line_in(contact.classification)

def papel_from(profile,headline):
    """dueno or lider_tecnologia: the profile says it; otherwise the headline (a technology title first: «CTO & co-owner»
    leads technology). '' when neither is clear."""
    if profile in PAPEL_OF_PROFILE:return PAPEL_OF_PROFILE[profile]
    text=_plain(headline)
    if TECH_LEADER.search(text):return 'lider_tecnologia'
    if OWNER.search(text):return 'dueno'
    return ''

def papel_of(contact):
    """What a ProjectApp buyer is inside her company (stored at classification), or ''."""
    buyer=buyer_of(contact)
    return buyer.get('papel') or papel_from(buyer.get('profile'),contact.headline)

def size_of(contact):
    return buyer_of(contact).get('company_size') if buyer_of(contact).get('company_size') in SIZES else ''

def segments(segment,affinity,papel,in_us):
    """(segment, also_segments) of a ProjectApp buyer, by the rules of the test (17/11/2026):
    1. the industry wins: educacion_en_linea or retail_ecommerce when the classifier (or the reevaluation) says so;
    2. duenos_latinos_eeuu is an owner (papel dueno) in the United States who declares Spanish (affinity
       hispanohablante_declarada: never inferred from a name or a photo). It is the segment when the industry is not
       one of the two, and an additional match (`also`) when it is; the funnel counts each person once, by segment;
    3. everyone else, otro. A classifier's duenos_latinos_eeuu that does not meet rule 2 is otro."""
    latino=papel=='dueno' and affinity==LATINO_AFFINITY and in_us
    if segment in INDUSTRY_SEGMENTS:return segment,(['duenos_latinos_eeuu'] if latino else [])
    return ('duenos_latinos_eeuu' if latino else 'otro'),[]

def segment_of(contact):
    """The ProjectApp buyer's segment, or '' (not a ProjectApp buyer, or classified before the segments)."""
    if line_of(contact)!='projectapp':return ''
    segment=buyer_of(contact).get('segment')
    return segment if segment in SEGMENTS else ''

def in_us(contact,buyer=None):
    from . import ubicacion
    return ubicacion.region(contact.location)=='us' or bool((buyer if buyer is not None else buyer_of(contact)).get('us_market'))

def complete(contact,buyer,result=None):
    """The classification's buyer block with its line and, for a ProjectApp buyer, papel, size and segment (rules above).
    `result` is the classifier's answer (buyer_segment, company_size, affinity); without it, what the buyer block keeps."""
    result=result or {}
    buyer=dict(buyer)
    buyer['line']=line_for(buyer.get('profile'))
    if buyer['line']!='projectapp':
        for key in ('papel','segment','also_segments'):buyer.pop(key,None)
        return buyer
    size=result.get('company_size',buyer.get('company_size'))
    buyer['company_size']=size if size in SIZES else ''
    buyer['papel']=papel_from(buyer.get('profile'),contact.headline)
    affinity=result.get('affinity') if 'affinity' in result else (contact.classification or {}).get('affinity')
    segment,also=segments(result.get('buyer_segment',buyer.get('segment')),affinity,buyer['papel'],in_us(contact,buyer))
    buyer['segment']=segment;buyer['also_segments']=also
    return buyer

def too_big(buyer):
    """A ProjectApp buyer of a company of more than 1000 people: evidence against (SIZE_RULE)."""
    return buyer.get('line')=='projectapp' and buyer.get('company_size')==OUT_SIZE

# --------------------------------------------------------------------------- D. searches per audience

AUDIENCES=('projectapp','startup','partner')
# Keywords only: the connector's people search takes keywords, a location (the United States, NETWORK_SEARCH_LOCATION) and
# the profile language («[es]»). It has no company size, industry, seniority or hiring filter (those are Sales Navigator):
# the classifier and the web check judge size and industry after the search.
DEFAULT_QUERIES={
    'projectapp':('CTO retail;Director of IT ecommerce;Head of Technology online education;Owner online academy;'
                  'VP Engineering retail;CEO family business;dueño de empresa [es];gerente de sistemas [es]'),
    'partner':('marketing agency founder development partners;design agency owner web development;'
               'digital agency white label development;product consultancy founder;agencia de marketing [es]'),
}
QUERY_SETTINGS={'projectapp':'NETWORK_SEARCH_QUERIES_PROJECTAPP','partner':'NETWORK_SEARCH_QUERIES_PARTNER',
                'startup':'NETWORK_SEARCH_QUERIES'}
# Searches in proportion to the week's invitations of each audience (28 ProjectApp buyers, 12 startup, 12 partners):
# about 7 of every 13 searches look for ProjectApp buyers. Within the same search cap (NETWORK_READ_CAPS search=20 a day)
# and NETWORK_SEARCHES_PER_RUN: nothing searches more than before.
DEFAULT_AUDIENCE_SHARE='projectapp=28,startup=12,partner=12'

def audience_queries():
    """{audience: [queries]} of the audiences that have queries. The startup line keeps NETWORK_SEARCH_QUERIES."""
    out={}
    for audience in AUDIENCES:
        raw=os.environ.get(QUERY_SETTINGS[audience],DEFAULT_QUERIES.get(audience,''))
        queries=[q.strip() for q in raw.split(';') if q.strip()]
        if queries:out[audience]=queries
    return out

def audience_shares():
    """NETWORK_SEARCH_AUDIENCE_SHARE='projectapp=28,startup=12,partner=12'; a bad item is ignored, never fatal."""
    out={}
    for item in os.environ.get('NETWORK_SEARCH_AUDIENCE_SHARE',DEFAULT_AUDIENCE_SHARE).split(','):
        key,_,value=item.partition('=')
        if key.strip() in AUDIENCES and value.strip().isdigit() and int(value)>0:out[key.strip()]=int(value)
    return out or {'projectapp':28,'startup':12,'partner':12}

def next_search(done_by_audience):
    """(audience, query) of the next search: the audience furthest below its share of the searches done (ties in the
    order of AUDIENCES), then its next query in rotation. `done_by_audience`: {audience: searches done}. None without
    queries."""
    queries=audience_queries();shares=audience_shares()
    ready=[a for a in AUDIENCES if a in queries and a in shares]
    if not ready:return None
    audience=min(ready,key=lambda a:(done_by_audience.get(a,0)/shares[a],AUDIENCES.index(a)))
    rotation=queries[audience]
    return audience,rotation[done_by_audience.get(audience,0)%len(rotation)]

def searches_done(account):
    """{audience: searches done}: network.searched events that name their audience (the ones before have none)."""
    from django.db.models import Count
    from .models import AuditEvent
    rows=(AuditEvent.objects.filter(action='network.searched',target=str(account.id),metadata__has_key='audience')
          .values('metadata__audience').annotate(n=Count('id')))
    return {row['metadata__audience']:row['n'] for row in rows}

# --------------------------------------------------------------------------- E. the partners' posts (comment share «comunidad»)

PARTNER_COMMENTS=2          # comments per partner in PARTNER_WINDOW, like a buyer's warm-up
PARTNER_WINDOW=timedelta(days=30)
PARTNER_READ='partner.posts_read'

def partners(account):
    """Partners the team follows (or invited or connected): their posts feed the «comunidad» share of the comments."""
    from .models import Contact
    return (Contact.objects.filter(account=account,classification__role='partner',classification__fit=True,
                                   stage__in=['followed','invited','connected']).exclude(provider_user_id=''))

def partner_ids(account):
    return set(partners(account).values_list('provider_user_id',flat=True)) if enabled() else set()

def _comments_to(account,uid,now):
    from .models import ActionProposal
    return ActionProposal.objects.filter(account=account,capability='INT-03',post__author_provider_id=uid,
                                         state__in=['proposed','approved','executing','sent','confirmed','uncertain'],
                                         created_at__gte=now-PARTNER_WINDOW).count()

def read_share():
    """Partner reads a day: a quarter of the buyers' read cap (BUYER_POSTS_READ_DAILY_LIMIT), at least 1 when it is on.
    Buyers are read first in the same run, and a partner never takes more than this share of the cap."""
    from . import calentamiento
    cap=calentamiento.read_cap()
    return max(1,cap//4) if cap else 0

def _partner_reads_today(account,now):
    from . import operador
    from .models import AuditEvent
    day,_=operador.period_starts(now)
    return AuditEvent.objects.filter(action=PARTNER_READ,target=str(account.id),created_at__gte=day).count()

def partners_to_read(account,now=None):
    """Partners whose posts are due for a read: short of PARTNER_COMMENTS in 30 days and not read within
    BUYER_POSTS_REREAD_HOURS; the ones read longest ago first."""
    from django.db.models import Max
    from . import calentamiento
    from .models import AuditEvent
    now=now or timezone.now()
    if not (enabled() and calentamiento.enabled()):return []
    last={row['target']:row['at'] for row in AuditEvent.objects.filter(action=calentamiento.POSTS_READ,
          created_at__gte=now-PARTNER_WINDOW).values('target').annotate(at=Max('created_at'))}
    due=[c for c in partners(account) if (last.get(str(c.pk)) is None or last[str(c.pk)]<now-calentamiento.reread_after())
         and _comments_to(account,c.provider_user_id,now)<PARTNER_COMMENTS]
    never=now-PARTNER_WINDOW
    return sorted(due,key=lambda c:(last.get(str(c.pk)) or never,c.discovered_at))

def reading_due(account,now=None):
    """Some partner is due for a read and today's partner reads have room (autopiloto._observe)."""
    now=now or timezone.now()
    return enabled() and _partner_reads_today(account,now)<read_share() and bool(partners_to_read(account,now))

def read_partner_posts(account,connector,now=None):
    """The recent posts of the partners due, inside READ_WINDOW and the buyers' read cap (calentamiento._reserve), at most
    read_share() a day. Stored like a buyer's post (ObservedPost without a referent). A connector failure stops the
    run the way calentamiento.read_posts does."""
    from . import calentamiento, operador
    from .connectors import ConnectorError, deferred
    from .models import AuditEvent
    now=now or timezone.now()
    out={'personas':0,'nuevos':0,'comentables':0,'tope':False,'errores':[]}
    if not operador.within_read_window(now):return dict(out,fuera_de_ventana=True)
    for contact in partners_to_read(account,now):
        if _partner_reads_today(account,now)>=read_share():out['tope']=True;break
        try:
            calentamiento._reserve(account,contact,now)
            posts=connector.list_user_posts(contact.provider_user_id,limit=calentamiento.POSTS_PER_READ)
        except calentamiento.ReadCapReached:out['tope']=True;break
        except ConnectorError as exc:
            out['errores'].append({'persona':str(contact.pk),'error':str(exc)[:200]})
            if exc.pause:operador.set_account_pause(account,f'Lectura detenida: {exc}');break
            if deferred(exc):break
            continue
        AuditEvent.objects.create(action=PARTNER_READ,target=str(account.id),created_at=now,metadata={'contact':str(contact.pk)})
        out['personas']+=1;fresh=0;new=0
        for post in posts:
            if not (post.get('text') or '').strip():continue
            _,created=calentamiento._store(account,post);new+=int(created)
            fresh+=int(calentamiento.commentable(post,now))
        out['nuevos']+=new;out['comentables']+=fresh
        AuditEvent.objects.create(action=calentamiento.POSTS_READ,target=str(contact.pk),created_at=now,
                                  metadata={'account':str(account.id),'posts':len(posts),'comentables':fresh,'nuevos':new,'partner':True})
    return out

def partner_posts(account,now,recent_authors=(),skips=()):
    """The partners' posts that may get a comment now (the «comunidad» share): recent, not commented, the author short of
    PARTNER_COMMENTS and outside the author wait; newest first. [] with the switch off."""
    from . import calentamiento
    from .models import ObservedPost
    if not enabled():return []
    need=[c.provider_user_id for c in partners(account) if _comments_to(account,c.provider_user_id,now)<PARTNER_COMMENTS]
    return list(ObservedPost.objects.filter(account=account,referent__isnull=True,is_repost=False,author_provider_id__in=need,
                                            posted_at__gte=now-calentamiento.post_max_age()).exclude(text='')
                .exclude(proposals__capability='INT-03').exclude(author_provider_id__in=list(recent_authors))
                .exclude(id__in=list(skips)).order_by('-posted_at'))

# --------------------------------------------------------------------------- G. the case as proof

CASE_SEGMENTS=('educacion_en_linea','retail_ecommerce')
CASE_LABELS={'educacion_en_linea':'la plataforma de educación en línea','retail_ecommerce':'la plataforma de retail'}
# What a text must say to cite one of the cases: that ProjectApp (or we, or I) built it, and its industry.
BUILT=re.compile(r"\b(?:we|our team|i)\s+(?:built|build|developed|created|delivered|designed|shipped)\b|"
                 r"\b(?:constru(?:imos|[ií])|desarroll(?:amos|[ée])|hicimos|entregamos|creamos|dise[ñn]amos)\b|\bprojectapp\b",re.I)
CASE_WORDS={'educacion_en_linea':re.compile(r"\b(?:online (?:education|learning|courses?|academy|school)|e-?learning|edtech|lms|"
                                            r"learning platform|education platform|educaci[oó]n (?:en l[ií]nea|online)|"
                                            r"plataforma educativa|cursos (?:en l[ií]nea|online)|academia (?:en l[ií]nea|online))\b",re.I),
            'retail_ecommerce':re.compile(r"\b(?:retail|e-?commerce|online store|tienda (?:en l[ií]nea|online)|"
                                          r"comercio electr[oó]nico|minorista)\b",re.I)}
FIGURE=re.compile(r'\d+(?:[.,]\d+)*')
# The questions to Gustavo about each case: the answers become confirmed memory (preguntas.answer), the only source of
# case facts a text may use. Keys: projectapp.caso.<segment>.<what>.
CASE_QUESTIONS=(
    ('problema','¿Qué problema tenía el cliente de {case} cuando llegó a ProjectApp?',
     'Para contar el caso solo con hechos: el problema de negocio, en una o dos frases.','text',None),
    ('construccion','¿Qué construyó ProjectApp en {case}: la plataforma y sus partes principales?',
     'Para que el equipo diga qué se construyó sin inventar funciones.','text',None),
    ('duracion','¿Cuánto tiempo tomó {case}, desde el inicio hasta la primera versión en uso (y si sigue)?',
     'Para no inventar plazos: solo se cita el que confirmes.','text',None),
    ('cambio','¿Qué cambió para el cliente después de {case}? Solo lo que puedas afirmar; cifras solo si las tienes medidas.',
     'Para contar el resultado sin inventar cifras ni resultados.','text',None),
    ('cliente','¿Se puede nombrar al cliente de {case} en mensajes a otros compradores? Si sí, escribe el nombre tal como se '
     'puede decir; si no, escribe «no».','Si respondes «no», el equipo habla del caso sin nombrar al cliente.','text',None),
)
CASE_AGENT='relaciones_comunidad'
CASE_ORIGIN='projectapp:casos'

def case_key(segment,what):
    return f'projectapp.caso.{segment}.{what}'

def ask_case_questions():
    """Queue the case questions to Gustavo (TeamQuestion, Tu turno): five per case. Idempotent: preguntas.ask never
    asks a key that is open, answered, declined or withdrawn, so running it again creates nothing. Returns the
    questions created now."""
    from . import posicionamiento, preguntas
    created=[]
    for segment in CASE_SEGMENTS:
        for what,question,purpose,kind,options in CASE_QUESTIONS:
            item=preguntas.ask(CASE_AGENT,question.format(case=CASE_LABELS[segment]),
                               f'Caso real de ProjectApp ({posicionamiento.CASES[segment]}). {purpose} Se usa solo con '
                               'compradores del mismo segmento y solo con lo que confirmes.',
                               case_key(segment,what),suggested_public=True,origin=CASE_ORIGIN,answer_type=kind,options=options)
            if item is not None:created.append(item)
    return created

def case_facts(segment):
    """{what: text} of the case answers Gustavo confirmed for public use (uso_publico), plus the base fact of
    posicionamiento.CASES; a «no» to `cliente` keeps the client unnamed."""
    from knowledge import memory
    from . import posicionamiento
    facts={'caso':posicionamiento.CASES[segment]}
    wanted={case_key(segment,what):what for what,*_ in CASE_QUESTIONS}
    for row in memory.latest(True):
        what=wanted.get(row['key']);value=row['value']
        if what is None or memory.retired(value) or not memory.publishable(value):continue
        text=str(value.get('texto') or '').strip()
        if what=='cliente' and _plain(text).strip(' .') in ('no','no se puede','no se puede nombrar'):continue
        if text:facts[what]=text[:600]
    return facts

def case_for(contact):
    """The case a text to this buyer may cite: {segmento, caso, hechos} when the switch is on, she is a ProjectApp buyer
    and her segment (or an additional match) is the case's. None otherwise: no case to anyone else."""
    if not enabled() or line_of(contact)!='projectapp':return None
    mine=[segment_of(contact),*buyer_of(contact).get('also_segments',[])]
    segment=next((s for s in mine if s in CASE_SEGMENTS),None)
    if segment is None:return None
    return {'segmento':segment,'caso':CASE_LABELS[segment],'hechos':case_facts(segment)}

def cited_cases(text):
    """The case segments a text cites (says ProjectApp, we or I built it and names its industry)."""
    if not BUILT.search(text or ''):return []
    return [segment for segment,words in CASE_WORDS.items() if words.search(text)]

def case_issues(text,contact):
    """The fixed rule of the proof (pure but for the case facts): a case is cited only to a buyer of the same segment,
    and a figure in a text that cites a case must be among the confirmed facts (or the offer's prices). [] with the
    switch off."""
    if not enabled() or not (text or '').strip():return []
    cited=cited_cases(text)
    if not cited:return []
    allowed=case_for(contact)
    issues=[]
    other=[s for s in cited if not allowed or s!=allowed['segmento']]
    if other:
        issues.append('Cita un caso de ProjectApp de otro segmento ('+', '.join(SEGMENT_LABELS[s] for s in other)+
                      '): solo se cita a un comprador del mismo segmento')
    from . import posicionamiento
    # The offer's prices (posicionamiento.OFFER) are confirmed facts too; any other figure must come from the case.
    confirmed=set(re.findall(r'\d+',' '.join([*(allowed or {}).get('hechos',{}).values(),*posicionamiento.OFFER.values()])))
    figures=[m.group(0) for m in FIGURE.finditer(text) if not set(re.findall(r'\d+',m.group(0)))<=confirmed]
    if figures:issues.append('Cifra del caso que Gustavo no confirmó ('+', '.join(dict.fromkeys(figures))+')')
    return issues

CASE_RULES='''
`caso_projectapp` es un caso real de ProjectApp del mismo segmento de la persona: puedes mencionarlo solo si viene al caso
y solo con `caso_projectapp.hechos`, sin agregar nombres de clientes, cifras, plazos ni resultados que no estén ahí. Sin
`caso_projectapp`, no menciones ningún proyecto ni cliente de ProjectApp.'''

# --------------------------------------------------------------------------- J. the test's progress

TEST_START=date(2026,11,17)
TEST_END=date(2027,2,17)
TEST_WEEKS=13
REVIEW='17/02/2027'

def test_week(now=None):
    """Week N of 13 of the test (1 the week of 17/11/2026), 0 before it and 14 after its review date."""
    from . import operador
    today=timezone.localtime(now or timezone.now(),operador.local_tz()).date()
    if today<TEST_START:return 0
    if today>TEST_END:return TEST_WEEKS+1
    return min(TEST_WEEKS,(today-TEST_START).days//7+1)

def test_progress(account=None,now=None):
    """The three-month test: week N of 13, invitations per segment of the ProjectApp buyers (by the segment they
    entered with) and of the other audiences, and whether each one has a sample yet (30 invitations). Read only."""
    from . import comprador, operador
    from .models import ActionExecution, BuyerJourney
    now=now or timezone.now()
    start=timezone.make_aware(datetime.combine(TEST_START,time(0)),operador.local_tz())
    journeys=BuyerJourney.objects.filter(invited_at__gte=start,entry=BuyerJourney.Entry.OUTBOUND)
    if account is not None:journeys=journeys.filter(contact__account=account)
    journeys=list(journeys.values('line','segment','accepted_at','replied_at','meeting_at'))
    def row(group):
        invited=len(group)
        return {'invitaciones':invited,'aceptaron':sum(1 for j in group if j['accepted_at']),
                'respondieron':sum(1 for j in group if j['replied_at']),'reunion':sum(1 for j in group if j['meeting_at']),
                'muestra':invited>=comprador.SMALL_SAMPLE}
    segments={s:row([j for j in journeys if j['line']=='projectapp' and j['segment']==s]) for s in SEGMENTS}
    lines={line:row([j for j in journeys if (j['line'] or 'startup')==line]) for line in LINES}
    sent=ActionExecution.objects.filter(proposal__capability='RED-02',wrote=True,started_at__gte=start,
                                        proposal__contact__classification__role='partner')
    if account is not None:sent=sent.filter(proposal__account=account)
    partners_invited=sent.count()
    return {'semana':test_week(now),'de':TEST_WEEKS,'desde':TEST_START.isoformat(),'revision':TEST_END.isoformat(),
            'activo':enabled(),'por_segmento':segments,'por_linea':lines,
            'partner':{'invitaciones':partners_invited,'muestra':partners_invited>=comprador.SMALL_SAMPLE},
            'regla':comprador.SMALL_SAMPLE_TEXT}
