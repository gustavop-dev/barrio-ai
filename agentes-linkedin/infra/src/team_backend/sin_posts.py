"""Phase 5 of docs/plan-outbound.md «El sistema del comprador» (BAR-22): the route of the buyer who does not post, and the
retries the earlier phases left pending. Everything is behind BUYER_NO_POSTS_ROUTE_ENABLED (default false) and needs the
warm-up on (BUYER_WARMUP_ENABLED: the route «sin_posts» only exists there). Off, nothing here runs and the path is the
one of phases 2–4.

The route is Gustavo's design (plan, 17/11/2026: «apruebo entrar por el cofounder»), grounded in the course but not the
course's own: LI-07-M005-K01 («busca la llave»: follow and comment before connecting; a third-degree person is reached
through someone of their network), LI-07-M005-K02 (card 04: the people who comment where the client comments),
LI-08-M004-K04/K05 (two or three people per company, never two with the same role or doing the same, on two flanks;
decide · influye · usa) and LI-10-V008-K01 (the warm-up: visit, like, comment, follow, visit again; the visit counts
because the person is notified). Read in full from the library (SELECT, 17/11/2026). No agent loads these units: the
rules here are code.

1. Follow: RED-01 in red.plan, as today. «Visit the profile twice in 10 days»: NOT built. The connector has no visible
   visit (get_profile reads without the visit being checked; BAR-15: «no se simula una visita pública»), and profile
   reads spent on a visit nobody may see would only eat the shared cap of 80.
2. «Comment where he comments»: NOT built. The connector cannot read a person's comment activity (list_user_posts reads
   his posts, list_comments the comments of one post). Nothing is invented.
3. The bridge (`puente`): a colleague at his company who does post. The company comes from his headline; one people
   search under the «search» cap and its own daily cap (BUYER_BRIDGE_SEARCHES_PER_DAY); a profile read only for a
   result without a headline (the real search page has none), at most BUYER_BRIDGE_PROFILES_PER_SEARCH; a posts read
   under the buyers' cap to see that the person posts. No paid call. The bridge is its own contact (role «puente»,
   Contact.bridge_for → the buyer's journey), never a second buyer: red.plan follows it, the warm-up comments it (same
   methodology, rules, lead, author wait and the buyers' share of the day) and it is invited with the warm-up rule. At
   most COMPANY_MAX people per company and never two with the same role; a comment never repeats what the team wrote
   to the other one. What the bridge does (accepts, answers, writes) is a signal of the buyer (senal_puente): heat goes
   up and the note or first message may cite it; only an interaction lets a text say they talked.
4. Invited at 14 days (calentamiento.invite_at, as in phase 2). A strong, recent, sourced buying signal (or his
   bridge's) makes him a candidate for one of the month's notes, after the buyers the team warmed with comments.
5. First message: anchored on the signal or the bridge (mensajes_comprador.anchors); nothing real, no message.
6. Retries: (a) invited with fewer comments than the warm-up and not accepted in 21 days also rests; (b) on this route
   the bridge is tried before the rest (hold_rest); (c) each retry changes the angle and records its type (next_angle;
   three attempts, then a year: calentamiento.LONG_REST in every rest); (d) one web re-check of his buying signals when
   a rest ends, inside the day's stage-check allowance (red.check_stages, recheck_*).
7. funnel(): the route with and without a bridge, the bridges, the retries by angle and the re-checks.
"""
import logging
import os
import re
from datetime import datetime, timedelta
from types import SimpleNamespace
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from . import calentamiento, comprador, operador
from .connectors import ConnectorError, deferred
from .models import ActionProposal, AuditEvent, BuyerDraft, BuyerJourney, BuyerTouch, Contact

log=logging.getLogger(__name__)
Kind=BuyerTouch.Kind;Step=BuyerJourney.Step;Route=BuyerJourney.Route

ROLE='puente'
UNITS=('LI-07-M005-K01','LI-07-M005-K02','LI-08-M004-K04','LI-08-M004-K05','LI-10-V008-K01')
COMPANY_MAX=2              # LI-08-M004-K04: two or three people per company; Gustavo's route takes two (buyer + bridge)
CANDIDATE_READS=2          # posts reads per search to see whether a candidate posts
RECHECK_WAIT=timedelta(days=2)  # the retry waits this long, at most, for the one re-check of the rest
SEARCH_ACTION='buyer.bridge_search'
NOT_BUILT_VISIT=('El conector no registra una visita visible: get_profile lee el perfil sin que la visita se compruebe '
                 '(BAR-15). No se simula ni se gastan lecturas de perfil en ella.')
NOT_BUILT_WHERE=('El conector no lee la actividad de comentarios de una persona (solo sus posts y los comentarios de un post). '
                 'No se inventa.')

def setting(name,default):
    return os.environ.get(name,default)

def _int(name,default,low,high):
    try:value=int(str(setting(name,default)).strip())
    except ValueError:return default
    return min(max(value,low),high)

def enabled():
    """BUYER_NO_POSTS_ROUTE_ENABLED=true turns phase 5 on; off (the default) everything behaves as before it existed."""
    return setting('BUYER_NO_POSTS_ROUTE_ENABLED','false').strip().lower()=='true'

def active():
    """The route needs the warm-up: without it nobody takes the route «sin_posts»."""
    return enabled() and calentamiento.enabled()

def searches_cap():return _int('BUYER_BRIDGE_SEARCHES_PER_DAY',2,0,10)
def profiles_per_search():return _int('BUYER_BRIDGE_PROFILES_PER_SEARCH',3,0,5)
def bridge_wait():return timedelta(days=_int('BUYER_BRIDGE_WAIT_DAYS',21,7,60))
def signal_recent():return timedelta(days=_int('BUYER_SIGNAL_RECENT_DAYS',30,7,180))

def _when(value):
    return comprador._when(value)

# --------------------------------------------------------------------------- company and role, from the headline

PARTS=re.compile(r'\s*[|·•]\s*')
AT=re.compile(r'(?:@|\bat\b|\ben\b)\s*(.+)',re.I)
OF=re.compile(r'\b(?:co-?)?(?:fundador|fundadora|founder|ceo|cto|coo)\s+(?:de|of)\s+(.+)',re.I)
CUT=re.compile(r'\s*(?:,|;|\(|\)|\s[-–—]\s|/)\s*')
# The first one that matches names the role (cargo); the C-suite before «founder», so «Founder & CEO» is a CEO.
CARGOS=(('ceo',r'\bceo\b|chief executive|director general|gerente general'),('cto',r'\bcto\b|chief technology|chief technical'),
        ('coo',r'\bcoo\b|chief operating'),('cfo',r'\bcfo\b|chief financial'),('cmo',r'\bcmo\b|chief marketing'),
        ('cpo',r'\bcpo\b|chief product'),('cro',r'\bcro\b|chief revenue'),
        ('fundador',r'\b(?:co-?)?founder\b|\bco-?fundador|\bfundador'),('vp',r'\bvp\b|vice ?president|vicepresident'),
        ('direccion',r'\bhead of\b|\bdirector\b|\bdirectora\b|\bjef[ea]\b|\blead\b'),
        ('ingenieria',r'engineer|ingenier|developer|desarrollador'),('ventas',r'\bsales\b|\bventas\b|account executive|business development'),
        ('marketing',r'marketing|growth'),('producto',r'product manager|\bproducto\b'))

def _key(text):
    return ' '.join(re.findall(r'[a-z0-9]+',(text or '').lower()))

def company_of(headline):
    """The company the headline names («Founder & CEO at Acme», «CTO @ Acme | ex-…», «Fundador de Acme»), or ''."""
    for part in PARTS.split(headline or ''):
        for pattern in (AT,OF):
            match=pattern.search(part)
            if not match:continue
            name=CUT.split(match.group(1))[0].strip(' .')
            if 3<=len(_key(name))<=60:return name[:60]
    return ''

def mentions(headline,company):
    key=_key(company)
    return bool(key) and f' {key} ' in f' {_key(headline)} '

def same_company(headline,company):
    """Someone at that company: the company his headline names starts with that name («Acme» ~ «Acme Inc», not «Globex
    Acme Partners»), or, when it names none, it mentions it."""
    key=_key(company)
    if not key:return False
    theirs=_key(company_of(headline))
    if theirs:return f'{theirs} '.startswith(f'{key} ') or f'{key} '.startswith(f'{theirs} ')
    return mentions(headline,company)

def cargo_of(headline):
    low=(headline or '').lower()
    return next((name for name,pattern in CARGOS if re.search(pattern,low)),'')

def people_at(account,company,exclude=None):
    """The people of that company the team already goes after: buyers with a journey and bridges, in course (not left,
    discarded or closed)."""
    rows=(Contact.objects.filter(account=account).filter(Q(buyer_journey__isnull=False)|Q(bridge_for__isnull=False))
          .exclude(stage__in=['discarded','closed']).select_related('buyer_journey'))
    if exclude is not None:rows=rows.exclude(pk=exclude.pk)
    out=[]
    for c in rows:
        journey=getattr(c,'buyer_journey',None)
        if journey is not None and journey.step==Step.LEFT:continue
        if same_company(c.headline,company):out.append(c)
    return out

# --------------------------------------------------------------------------- the bridge of a journey

def bridges(account):
    """The bridges in course: their buyer did not leave, they were not discarded or closed."""
    return (Contact.objects.filter(account=account,bridge_for__isnull=False).exclude(bridge_for__step=Step.LEFT)
            .exclude(stage__in=['discarded','closed']))

def bridge_of(post):
    """The bridge who wrote this post (no referent), or None; None with the switch off."""
    if post is None or not active() or not post.author_provider_id or post.referent_id:return None
    return bridges(post.account_id).filter(provider_user_id=post.author_provider_id).first()

def bridge_of_journey(journey):
    return Contact.objects.filter(bridge_for=journey).first()

def _bridge_touches(journey):
    return list(journey.touches.filter(kind=Kind.BRIDGE).order_by('at','created_at'))

def status(journey):
    """The bridge of this buyer: None (never asked in this attempt), 'pedido' (asked, not searched yet), 'en_curso' (found,
    being warmed or invited), 'senal' (it accepted or interacted) or 'sin_puente' (nobody, or it fell through)."""
    bridge=bridge_of_journey(journey)
    if bridge is not None:
        if journey.touches.filter(kind=Kind.BRIDGE_SIGNAL).exists():return 'senal'
        return 'sin_puente' if bridge.stage in ('discarded','closed') else 'en_curso'
    states={t.detail.get('estado') for t in _bridge_touches(journey) if t.detail.get('intento')==journey.attempt}
    return 'sin_puente' if 'sin_puente' in states else 'pedido' if 'pedido' in states else None  # a search answers its request

def tried(journey):
    """A search for his bridge already came back (found or not), in any attempt: the route does not search it again by
    itself (a retry may still choose the bridge angle while none was found)."""
    return any(t.detail.get('estado') in ('encontrado','sin_puente') for t in _bridge_touches(journey))

def request(journey,why,now=None):
    """Ask for a bridge in this attempt (the observe job searches it). Once per attempt."""
    now=now or timezone.now()
    return comprador.record(journey,Kind.BRIDGE,at=now,key=f'puente:pedido:{journey.attempt}',
                            detail={'estado':'pedido','intento':journey.attempt,'motivo':why})

def _resolve(journey,state,why,now,**extra):
    comprador.record(journey,Kind.BRIDGE,at=now,key=f'puente:{state}:{journey.attempt}',
                     detail={'estado':state,'intento':journey.attempt,'motivo':why,**extra})
    operador._audit(None,'buyer.bridge_'+('found' if state=='encontrado' else 'none'),journey.contact_id,motivo=why,**extra)

def requests(account):
    """Journeys whose bridge is asked for and not searched yet, oldest request first."""
    out=[];seen=set()
    for t in (BuyerTouch.objects.select_related('journey__contact').filter(kind=Kind.BRIDGE,journey__contact__account=account,
                                                                            detail__estado='pedido').order_by('at')):
        journey=t.journey
        if journey.pk in seen or journey.step==Step.LEFT or t.detail.get('intento')!=journey.attempt:continue
        seen.add(journey.pk)
        if status(journey)=='pedido':out.append(journey)
    return out

def early(journey,now=None):
    """calentamiento.sweep: a buyer on this route with nothing real to cite (no signal, no interaction) gets his bridge
    asked for right away (Gustavo's route, step 3). Returns 1 when asked."""
    from .mensajes_comprador import anchors
    if journey.route!=Route.NO_POSTS or journey.step not in (Step.WARMING,Step.INVITED):return 0
    if status(journey) is not None or tried(journey) or anchors(journey.contact,journey):return 0
    return int(bool(request(journey,'sin_ancla',now)))

def signal_times(state):
    """When his bridge accepted or interacted (the fold's inbound touches)."""
    return [t.at for t in state.inbound if t.kind==Kind.BRIDGE_SIGNAL]

def hold_rest(journey,now=None):
    """6b. «No publica y la ruta alterna no dio resultado → puente»: a buyer of this route due to rest tries the bridge
    first. True while the rest waits: the bridge is asked for now, or asked and not searched yet, or found and in
    course, each for BUYER_BRIDGE_WAIT_DAYS at most. Without a company in his headline, or once the bridge answered,
    fell through or was never found, he rests."""
    now=now or timezone.now();state=status(journey)
    if state is None:
        if tried(journey):return False  # an earlier attempt already searched it
        if not company_of(journey.contact.headline):
            _resolve(journey,'sin_puente','sin_empresa',now);return False
        request(journey,'ruta_sin_resultado',now);return True
    touches=_bridge_touches(journey)
    if state=='pedido':
        asked=max((t.at for t in touches if t.detail.get('estado')=='pedido' and t.detail.get('intento')==journey.attempt),default=now)
        return now<asked+bridge_wait()
    if state=='en_curso':
        found=max((t.at for t in touches if t.detail.get('estado')=='encontrado'),default=None)
        found=found or bridge_of_journey(journey).discovered_at
        return now<found+bridge_wait()
    return False

# --------------------------------------------------------------------------- the search (observe job, READ_WINDOW)

def _searches_today(account,now):
    day,_=operador.period_starts(now)
    return AuditEvent.objects.filter(action=SEARCH_ACTION,target=str(account.id),created_at__gte=day).count()

def _eligible(person,known,company,cargo):
    """'' when this search result may be the bridge, else why not."""
    if person.get('id') in known:return 'conocido'
    if person.get('network_distance') in ('FIRST_DEGREE','SELF'):return 'conocido'
    if person.get('type') and person['type']!='individual':return 'no_es_persona'
    if not person.get('headline'):return 'sin_titular'
    if not same_company(person['headline'],company):return 'otra_empresa'
    theirs=cargo_of(person['headline'])
    if not theirs:return 'sin_cargo'
    if theirs==cargo:return 'mismo_cargo'
    return ''

def _failed(account,out,who,exc):
    out['errores'].append({'persona':str(who),'error':str(exc)[:200]})
    if exc.pause:operador.set_account_pause(account,f'Lectura detenida: {exc}')
    return exc.pause or deferred(exc)

def _pick(account,connector,journey,company,cargo,people,known,now,out):
    """(person, posts) of the first result who may be the bridge and posts, or (None, why)."""
    from . import red
    reasons=[];profiles=0;checked=0
    for person in people:
        if checked>=CANDIDATE_READS:break
        why=_eligible(person,known,company,cargo)
        if why=='sin_titular':  # the real search page has no headline: one capped profile read
            if profiles>=profiles_per_search():reasons.append('sin_lectura');continue
            try:
                red._read(account,'profile',purpose='buyer_bridge')
                profile=connector.get_profile(person['id'])
            except red.ReadCapReached:return None,'tope'
            except ConnectorError as exc:
                if _failed(account,out,person.get('id'),exc):return None,'tope'
                continue
            profiles+=1;out['perfiles']+=1
            person=dict(person,**{k:profile[k] for k in ('display_name','public_identifier','profile_url','headline','location',
                                                         'network_distance') if profile.get(k)})
            why=_eligible(person,known,company,cargo)
        if why:reasons.append(why);continue
        try:
            calentamiento._reserve(account,SimpleNamespace(pk=f'puente:{journey.pk}',provider_user_id=person['id']),now)
            posts=connector.list_user_posts(person['id'],limit=calentamiento.POSTS_PER_READ)
        except calentamiento.ReadCapReached:return None,'tope'
        except ConnectorError as exc:
            if _failed(account,out,person.get('id'),exc):return None,'tope'
            continue
        checked+=1;out['lecturas']+=1
        if any(calentamiento.commentable(p,now) for p in posts):return (person,posts),''
        reasons.append('no_publica')
    # A result left unread (the per-search profile cap) may have been the bridge: that says more than the ones discarded.
    for why in ('no_publica','sin_lectura','mismo_cargo','sin_cargo','otra_empresa','conocido'):
        if why in reasons:return None,why
    return None,'sin_resultados'

def _create(account,journey,company,cargo,person,posts,now):
    from . import red
    buyer=journey.contact;theirs=cargo_of(person.get('headline'))
    info={'comprador':str(buyer.pk),'recorrido':str(journey.pk),'empresa':company,'cargo':theirs,'cargo_comprador':cargo}
    contact=Contact(account=account,provider_user_id=person['id'],public_identifier=person.get('public_identifier',''),
                    display_name=person.get('display_name',''),headline=person.get('headline',''),profile_url=person.get('profile_url',''),
                    location=person.get('location',''),source=Contact.Source.SEARCH,network_distance=person.get('network_distance',''),
                    stage=Contact.Stage.FIT,bridge_for=journey,evidence={'query':company,'puente':info},
                    classification={'fit':True,'role':ROLE,'confidence':0.9,'model':'regla','classified_at':now.isoformat(),
                                    'reason':(f'Colega de {buyer.display_name} en {company} ({theirs}) que sí publica: el puente '
                                              'hacia un comprador que no publica (ruta de Gustavo, 17/11/2026).')[:500],
                                    'course_citations':list(UNITS),'puente':info})
    red.note(contact,'discovered',f'Puente hacia {buyer.display_name} ({company}).')
    contact.save()
    fresh=0
    for post in posts:
        if not (post.get('text') or '').strip():continue
        calentamiento._store(account,post);fresh+=int(calentamiento.commentable(post,now))
    AuditEvent.objects.create(action=calentamiento.POSTS_READ,target=str(contact.pk),created_at=now,
                              metadata={'account':str(account.id),'posts':len(posts),'comentables':fresh,'puente':True})
    _resolve(journey,'encontrado','busqueda',now,puente=str(contact.pk),nombre=contact.display_name,empresa=company,cargo=theirs)
    return contact

def search(account,connector,now,out):
    """The bridges asked for: one search each, within BUYER_BRIDGE_SEARCHES_PER_DAY and the «search» cap."""
    from . import red
    known=set(Contact.objects.filter(account=account).values_list('provider_user_id',flat=True))
    for journey in requests(account):
        if _searches_today(account,now)>=searches_cap():out['tope']='busquedas';break
        buyer=journey.contact;company=company_of(buyer.headline);cargo=cargo_of(buyer.headline)
        if not company:_resolve(journey,'sin_puente','sin_empresa',now);out['sin_puente']+=1;continue
        if len(people_at(account,company,exclude=buyer))>=COMPANY_MAX-1:
            _resolve(journey,'sin_puente','empresa_completa',now,empresa=company);out['sin_puente']+=1;continue
        try:
            red._read(account,'search')
            AuditEvent.objects.create(action=SEARCH_ACTION,target=str(account.id),created_at=now,
                                      metadata={'recorrido':str(journey.pk),'empresa':company})
            people=connector.search_people(company)
        except red.ReadCapReached:out['tope']='search';break
        except ConnectorError as exc:
            if _failed(account,out,buyer.pk,exc):break
            continue
        out['busquedas']+=1
        found,why=_pick(account,connector,journey,company,cargo,people,known,now,out)
        if why=='tope':out['tope']='lecturas';break
        if found is None:
            _resolve(journey,'sin_puente',why,now,empresa=company);out['sin_puente']+=1;continue
        person,posts=found
        contact=_create(account,journey,company,cargo,person,posts,now)
        known.add(contact.provider_user_id);out['encontrados']+=1

def comments_done(bridge):
    """The team's comments written on the bridge's posts (what the warm-up counts)."""
    return sum(1 for f in comprador._post_facts(bridge) if f['kind']==Kind.COMMENT)

def warming(account):
    """Bridges being warmed: followed, short of the warm-up comments. [] with the switch off."""
    if not active():return []
    return [b for b in bridges(account).filter(stage='followed').exclude(provider_user_id='')
            if comments_done(b)<calentamiento.comments_needed()]

def to_read(account,now):
    recent=set(AuditEvent.objects.filter(action=calentamiento.POSTS_READ,created_at__gte=now-calentamiento.reread_after())
               .values_list('target',flat=True))
    return [b for b in warming(account) if str(b.pk) not in recent]

def read_bridges(account,connector,now,out):
    """The posts of the bridges being warmed, under the buyers' read cap, at most every BUYER_POSTS_REREAD_HOURS."""
    for bridge in to_read(account,now):
        try:
            calentamiento._reserve(account,bridge,now)
            posts=connector.list_user_posts(bridge.provider_user_id,limit=calentamiento.POSTS_PER_READ)
        except calentamiento.ReadCapReached:out['tope']=out['tope'] or 'lecturas';break
        except ConnectorError as exc:
            if _failed(account,out,bridge.pk,exc):break
            continue
        out['personas']+=1;fresh=0
        for post in posts:
            if not (post.get('text') or '').strip():continue
            calentamiento._store(account,post);fresh+=int(calentamiento.commentable(post,now))
        AuditEvent.objects.create(action=calentamiento.POSTS_READ,target=str(bridge.pk),created_at=now,
                                  metadata={'account':str(account.id),'posts':len(posts),'comentables':fresh,'puente':True})

def read(account,connector,now=None):
    """operador.observe, after the buyers' posts: the bridge searches due, then the posts of the bridges being warmed.
    Only inside READ_WINDOW. Returns a summary."""
    now=now or timezone.now()
    out={'busquedas':0,'encontrados':0,'sin_puente':0,'perfiles':0,'lecturas':0,'personas':0,'tope':'','errores':[]}
    if not active() or not operador.within_read_window(now):return out
    search(account,connector,now,out)
    account.refresh_from_db(fields=['paused'])
    if not account.paused and out['tope']!='lecturas':read_bridges(account,connector,now,out)
    return out

def reading_due(account,now=None):
    """autopiloto._observe: a bridge search or a bridge's posts are due and their caps have room."""
    now=now or timezone.now()
    if not active():return False
    if requests(account) and _searches_today(account,now)<searches_cap():return True
    return calentamiento.read_cap()>calentamiento._reads_today(account,now) and bool(to_read(account,now))

# --------------------------------------------------------------------------- the bridge's comments and invitation

def _texts_to(contact):
    """What the team wrote to this person: its comments on their posts and the buyer's notes and messages."""
    texts=[(payload or {}).get('text','') for payload in ActionProposal.objects.filter(
        account_id=contact.account_id,capability='INT-03',post__author_provider_id=contact.provider_user_id,
        state__in=['proposed','approved','executing','sent','confirmed','uncertain']).values_list('payload',flat=True)]
    texts+=list(BuyerDraft.objects.filter(contact=contact).exclude(text='').values_list('text',flat=True))
    return [t for t in texts if t]

def counterpart(account_id,uid):
    """The other person of the same company: the buyer of a bridge, or the bridge of a buyer. None otherwise."""
    if not active() or not uid:return None
    bridge=bridges(account_id).filter(provider_user_id=uid).select_related('bridge_for__contact').first()
    if bridge is not None:return bridge.bridge_for.contact
    journey=BuyerJourney.objects.filter(contact__account_id=account_id,contact__provider_user_id=uid).first()
    return bridge_of_journey(journey) if journey else None

def repeat_issues(proposal):
    """autopiloto.comment_text_issues: «no se le escribe a la segunda lo mismo que a la primera» (LI-08-M004-K04)."""
    if not active() or not proposal.post_id:return []
    other=counterpart(proposal.account_id,proposal.post.author_provider_id)
    if other is None:return []
    from .secuencia_comprador import repeats
    if repeats(proposal.payload.get('text',''),_texts_to(other)):
        return [f'Comentario que repite lo que el equipo le escribió a {other.display_name or "su colega"}, de su misma empresa']
    return []

def draft_inputs(post,bridge):
    """What the comment drafter reads about a bridge (calentamiento.draft_inputs)."""
    buyer=bridge.bridge_for.contact if bridge.bridge_for_id else None
    return {'autor':{'nombre':post.author_name,'titular':(bridge.headline or '')[:300]},
            'comentarios_del_equipo_en_sus_posts':comments_done(bridge),
            'para_que':calentamiento._of(post).render('Colega de un posible cliente de {nombre}, de su misma empresa: el '
                        'comentario es para que lo reconozca antes de la invitación. Nunca le vendas ni menciones a su colega.'),
            'no_repitas':[t[:300] for t in _texts_to(buyer)][:5] if buyer else []}

def _fold(bridge):
    rows=[SimpleNamespace(kind=f['kind'],at=f['at'],key=f['key'],detail=f['detail'],direction=comprador.DIRECTION[f['kind']])
          for f in sorted(comprador.facts(bridge),key=lambda f:f['at'])]
    return comprador._fold(rows)

def invite_ready(bridge,now=None):
    """calentamiento.invitable: the bridge is invited with the warm-up rule (its 2nd comment, an accelerating signal or
    BUYER_WARMUP_MAX_DAYS after the follow), while its buyer is still in course."""
    now=now or timezone.now()
    if not active() or bridge.bridge_for_id is None:return False
    if BuyerJourney.objects.filter(pk=bridge.bridge_for_id,step=Step.LEFT).exists():return False
    at=calentamiento.invite_at(_fold(bridge),bridge,now)
    return at is not None and at<=now

# --------------------------------------------------------------------------- what the bridge did, for the buyer

RELAY={Kind.ACCEPTED_OURS:('acepto',False),Kind.REPLIED_COMMENT:('respondio_comentario',True),
       Kind.COMMENTED_POST:('comento_post',True),Kind.INVITED_US:('nos_invito',True),
       Kind.OPENED_CONVERSATION:('conversacion',True),Kind.REPLIED_MESSAGE:('conversacion',True)}
ONCE=('acepto','nos_invito')  # one per bridge, whatever source first showed it

def relayed(journey):
    """comprador.facts of a buyer: what his bridges did, as senal_puente facts (one acceptance and one invitation per
    bridge; each comment answer, comment on Gustavo's post and message on its own). Follows and reactions do not count."""
    out=[]
    for bridge in Contact.objects.filter(bridge_for=journey):
        info=(bridge.classification or {}).get('puente') or {};seen=set()
        for f in sorted(comprador.facts(bridge),key=lambda f:f['at']):
            if f['kind'] not in RELAY:continue
            tipo,interaction=RELAY[f['kind']]
            key=f'puente:{bridge.pk}:'+(tipo if tipo in ONCE else f['key'])
            if key in seen:continue
            seen.add(key)
            out.append(comprador._fact(Kind.BRIDGE_SIGNAL,f['at'],key,{'puente':str(bridge.pk),'nombre':bridge.display_name,
                       'empresa':info.get('empresa',''),'cargo':info.get('cargo',''),'tipo':tipo,'interaccion':interaction,
                       'perfil':bridge.profile_url}))
    return out

WHAT={'acepto':'aceptó la invitación de {nombre}','respondio_comentario':'respondió un comentario del equipo',
      'comento_post':'comentó en un post de {nombre}','nos_invito':'invitó a {nombre} a conectar','conversacion':'le escribió a {nombre}'}

def fact(touch):
    """The anchor a senal_puente gives a note or a first message (mensajes_comprador.anchors)."""
    d=touch.detail or {}
    who=d.get('nombre') or 'Un colega suyo';where=f' de {d["empresa"]}' if d.get('empresa') else ''
    from . import identidad
    ident=identidad.of_account(touch.journey.contact.account)  # her name, never another member's
    what=ident.render(WHAT.get(d.get('tipo'),'interactuó con el equipo'))
    return {'tipo':'puente','texto':f'{who}{where} {what}.','interaccion':bool(d.get('interaccion')),
            'puente':d.get('nombre') or '','que_paso':('Su colega (el puente) interactuó con el equipo.' if d.get('interaccion')
                                                       else ident.render('Su colega (el puente) aceptó la invitación de {nombre}; no hubo conversación.')),
            'fecha':touch.at.isoformat(),'fuente':d.get('perfil') or 'su colega'}

# --------------------------------------------------------------------------- 4. the note by signal

def strong_signal(contact,now=None):
    """A buying signal with its source dated within BUYER_SIGNAL_RECENT_DAYS (class 08), newest first; None otherwise.
    A signal without a date is not recent."""
    now=now or timezone.now()
    dated=[(calentamiento._signal_date(s),s) for s in calentamiento.buying_signals(contact)]
    dated=sorted(((at,s) for at,s in dated if at and now-at<=signal_recent()),key=lambda x:x[0],reverse=True)
    return dated[0][1] if dated else None

def note_by_route(journey,now=None):
    """A buyer of this route may take one of the month's notes: a strong recent signal or his bridge's signal."""
    if not active() or journey.route!=Route.NO_POSTS:return False
    return bool(strong_signal(journey.contact,now)) or journey.touches.filter(kind=Kind.BRIDGE_SIGNAL).exists()

def warmed_waiting(account,now=None):
    """Buyers warmed with comments (one or more in this attempt), still warming, without a note decided: the notes go
    to them first."""
    from .mensajes_comprador import NOTE, decision
    rows=BuyerJourney.objects.select_related('contact').filter(contact__account=account,step=Step.WARMING,contact__stage='followed',
                                                              contact__classification__fit=True,warm_comments__gte=1)
    return sum(1 for j in rows if decision(j.contact,NOTE,j.attempt) is None)

# --------------------------------------------------------------------------- 6c. the angle of a retry

ANGLES={'senal_en_descanso':'Una señal suya durante el descanso','senal_nueva':'Una señal de compra nueva de su empresa',
        'puente':'Otra persona de su empresa (el puente)','otro_tema':'Otro post y otro tema'}

def _cited(journey):
    """The signals earlier attempts already used: their retries' and the notes' and messages' anchors."""
    out={(t.detail or {}).get('senal') for t in journey.touches.filter(kind=Kind.RETRY)}
    used=BuyerDraft.objects.filter(contact_id=journey.contact_id,stopped_by='').exclude(text='')  # a text that cited it
    for anchor in used.values_list('anchor',flat=True):
        if (anchor or {}).get('tipo')=='senal_de_compra':out.add(anchor.get('fuente'))
    return out-{None,''}

def next_angle(journey,now=None):
    """(angle, type, detail) of the next attempt, never the same as an earlier one: a buying signal no attempt cited yet
    (newest first; the re-check may have just found it), else the bridge (this route, none yet, room at the company),
    else another topic (numbered from the second one on)."""
    contact=journey.contact
    kinds=[(t.detail or {}).get('tipo') for t in journey.touches.filter(kind=Kind.RETRY)]
    cited=_cited(journey)
    oldest=datetime.min.replace(tzinfo=timezone.get_current_timezone())
    fresh=sorted((s for s in calentamiento.buying_signals(contact) if s['fuente'] not in cited),
                 key=lambda s:calentamiento._signal_date(s) or oldest,reverse=True)
    if fresh:
        s=fresh[0]
        return f'Señal nueva de su empresa: {(s.get("evidencia") or s["tipo"])[:200]}','senal_nueva',{'senal':s['fuente']}
    company=company_of(contact.headline)
    if (journey.route==Route.NO_POSTS and 'puente' not in kinds and bridge_of_journey(journey) is None and not tried(journey) and company
            and len(people_at(contact.account,company,exclude=contact))<COMPANY_MAX-1):
        return 'Otra persona de su empresa: el puente','puente',{}
    n=kinds.count('otro_tema')
    return ('Nuevo intento tras el descanso: otro post y otro tema'+(f' ({n+1}.º)' if n else '')),'otro_tema',{}

def retry(journey,now=None):
    """calentamiento.wake at the end of a rest: a new attempt with an angle the last one did not use; the bridge angle
    asks for the bridge of the new attempt."""
    now=now or timezone.now()
    angle,kind,detail=next_angle(journey,now)
    comprador.retry(journey,angle,at=now,kind=kind,detail=detail)
    if kind=='puente':request(BuyerJourney.objects.get(pk=journey.pk),'reintento',now)
    return 'reintentos'

# --------------------------------------------------------------------------- 6d. one re-check of the signals per rest

def _check(contact):
    return dict((contact.classification or {}).get('stage_check') or {})

def _save_check(contact,check):
    with transaction.atomic():
        row=Contact.objects.select_for_update().get(pk=contact.pk)
        row.classification=dict(row.classification or {},stage_check=check);row.save(update_fields=['classification'])
    contact.classification=row.classification
    return row

def recheck_waiting(journey,now=None):
    """calentamiento.wake at the end of a rest: True while the retry waits for the one web re-check of his buying signals
    for this rest (asked now, or asked and not run yet, RECHECK_WAIT at most). Only for a buyer whose stage the web
    already checked, and only with the stage check on; without allowance it never runs and the retry goes without it."""
    from . import red
    now=now or timezone.now();contact=journey.contact;check=_check(contact)
    if not red.stage_check_enabled() or check.get('state')!='ok':return False
    rest=journey.attempt;asked=check.get('recheck') or {}
    if asked.get('intento')!=rest:
        _save_check(contact,dict(check,recheck={'intento':rest,'estado':'pendiente','pedida':now.isoformat()}))
        comprador.record(journey,Kind.RECHECK,at=now,key=f'reverificacion:{rest}:pedida',detail={'intento':rest,'estado':'pedida'})
        return True
    if asked.get('estado')!='pendiente':return False
    if now<(_when(asked.get('pedida')) or now)+RECHECK_WAIT:return True
    _save_check(contact,dict(check,recheck=dict(asked,estado='vencida')))
    comprador.record(journey,Kind.RECHECK,at=now,key=f'reverificacion:{rest}:vencida',detail={'intento':rest,'estado':'vencida'})
    return False

def rechecks_due(account):
    """red.check_stages: resting buyers whose re-check is asked for and not run yet."""
    if not active():return Contact.objects.none()
    return (Contact.objects.filter(account=account,classification__stage_check__recheck__estado='pendiente',buyer_journey__step=Step.RESTING)
            .order_by('updated_at'))

def recheck_done(contact,signals,now=None):
    """The re-check ran: only the signals with a source not seen before are added; the verdict, the state and the fit
    never change here. Recorded on the journey (reverificacion «hecha»)."""
    now=now or timezone.now();check=_check(contact);asked=dict(check.get('recheck') or {})
    known={s.get('fuente') for s in check.get('senales') or []}
    new=[s for s in signals or [] if s.get('fuente') and s['fuente'] not in known]
    check.update(senales=[*(check.get('senales') or []),*new][-10:],recheck=dict(asked,estado='hecha',hecha=now.isoformat(),nuevas=len(new)))
    _save_check(contact,check)
    journey=comprador.journey(contact)
    if journey is not None:
        rest=asked.get('intento')
        comprador.record(journey,Kind.RECHECK,at=now,key=f'reverificacion:{rest}:hecha',
                         detail={'intento':rest,'estado':'hecha','nuevas':len(new),'fuentes':[s['fuente'] for s in new]})
    operador._audit(None,'buyer.signals_rechecked',contact.pk,nuevas=len(new),intento=asked.get('intento'))
    return new

# --------------------------------------------------------------------------- 7. measurement

DEFINITIONS={
    'con_puente':'Compradores de la ruta sin posts a los que el equipo les encontró un puente (un colega que sí publica).',
    'puentes':'Pedidos, búsquedas, encontrados y por qué no se encontró; de los encontrados, seguidos, invitados y los que aceptaron o interactuaron.',
    'reintentos':'Nuevos intentos por tipo de ángulo: señal durante el descanso, señal nueva, puente u otro tema.',
    'reverificaciones':'Una verificación web de sus señales de compra al terminar cada descanso, dentro del cupo diario de verificaciones.',
}

def funnel(journeys):
    """comprador.funnel (GET /api/v1/resultados/embudo-comprador) → ruta_sin_posts, only with the switch on."""
    journeys=list(journeys);ids=[j.pk for j in journeys]
    route=[j for j in journeys if j.route==Route.NO_POSTS]
    found=list(Contact.objects.filter(bridge_for_id__in=ids))
    with_bridge={b.bridge_for_id for b in found}
    asked=set();reasons={};kinds={};rechecks={'pedidas':0,'hechas':0,'con_senal_nueva':0,'vencidas':0};signals=set();talked=set()
    for jid,kind,d in BuyerTouch.objects.filter(journey_id__in=ids,kind__in=[Kind.BRIDGE,Kind.BRIDGE_SIGNAL,Kind.RETRY,Kind.RECHECK]).values_list('journey_id','kind','detail'):
        d=d or {}
        if kind==Kind.BRIDGE and d.get('estado')=='pedido':asked.add((jid,d.get('intento')))
        elif kind==Kind.BRIDGE and d.get('estado')=='sin_puente':reasons[d.get('motivo') or '']=reasons.get(d.get('motivo') or '',0)+1
        elif kind==Kind.BRIDGE_SIGNAL:
            signals.add(jid)
            if d.get('interaccion'):talked.add(jid)
        elif kind==Kind.RETRY:kinds[d.get('tipo') or 'sin_tipo']=kinds.get(d.get('tipo') or 'sin_tipo',0)+1
        elif kind==Kind.RECHECK:
            state=d.get('estado')
            if state=='pedida':rechecks['pedidas']+=1
            elif state=='vencida':rechecks['vencidas']+=1
            elif state=='hecha':rechecks['hechas']+=1;rechecks['con_senal_nueva']+=int(bool(d.get('nuevas')))
    searched=AuditEvent.objects.filter(action=SEARCH_ACTION,metadata__recorrido__in=[str(i) for i in ids]).count()
    return {'activa':True,'definiciones':DEFINITIONS,
            'comparacion':{'con_puente':comprador.block(j for j in route if j.pk in with_bridge),
                           'sin_puente':comprador.block(j for j in route if j.pk not in with_bridge)},
            'puentes':{'pedidos':len(asked),'busquedas':searched,'encontrados':len(found),'sin_puente':reasons,
                       'seguidos':sum(1 for b in found if b.followed_at),'invitados':sum(1 for b in found if b.invited_at),
                       'aceptaron':sum(1 for b in found if b.connected_at or b.stage=='connected'),
                       'compradores_con_senal_del_puente':len(signals),'compradores_con_interaccion_del_puente':len(talked)},
            'donde_comenta':{'disponible':False,'motivo':NOT_BUILT_WHERE},
            'visitas':{'disponible':False,'motivo':NOT_BUILT_VISIT},
            'reintentos':{'por_angulo':kinds},'reverificaciones':rechecks}
