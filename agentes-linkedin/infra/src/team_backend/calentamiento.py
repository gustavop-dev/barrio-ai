"""The buyer's warm-up, phase 2 of docs/plan-outbound.md (BAR-19): follow a chosen buyer, read their recent posts,
comment twice in 7–14 days with the «comentario_calentamiento» methodology (BIB-09-comentario-calentamiento) and invite
them after the second comment, sooner when they answer, at the latest BUYER_WARMUP_MAX_DAYS after the follow.

Everything here is behind BUYER_WARMUP_ENABLED (default false). With it off nothing in this module runs: operador.observe
reads only referents, autopiloto._propose comments only referents' posts, red.plan invites 48 h after the follow and the
journey's next_at says so, exactly as before. Caps and ramp are never touched: the comments still count against INT-03
(OPERATOR_DAILY_LIMITS/OPERATOR_WEEKLY_LIMITS, halved on weekends) and the invitations against RED-02 and its ramp.

- read_posts (operador.observe): the recent posts of buyers who are warming up, and of chosen ones whose follow is on
  its way, with their own daily read cap (BUYER_POSTS_READ_DAILY_LIMIT), each person at most every
  BUYER_POSTS_REREAD_HOURS. Stored as ObservedPost without a referent. A buyer without a commentable post in
  BUYER_NO_POSTS_READS reads within 10 days takes the route «sin_posts» (phase 5 builds that route).
- Comment groups (autopiloto._propose): the day's INT-03 cap is shared compradores/comunidad/referentes by
  BUYER_COMMENT_SHARE (8/2/5 of 15, 4/1/2 of a weekend's 7); a group with nothing to comment passes its slots on to the
  next one. «comunidad» has no source of posts yet, so its slots always go on.
- invite_at: the moment the warm-up is done: the BUYER_WARMUP_COMMENTS-th comment of the attempt, a reciprocity signal
  in the last 30 days (they answered a comment of the team, commented on Gustavo's post, invited him or wrote to him) or
  BUYER_WARMUP_MAX_DAYS after the follow, whichever comes first.
- heat: what the person did back (comprador's log, weighted by the reciprocity table, a signal older than 30 days
  weighs half) plus the buying signals the web stage check cited (class 08). It orders, it never adds people.
- sweep (red.plan): rest whoever got the comments, was invited and did not accept in BUYER_REST_AFTER_DAYS
  (BUYER_REST_DAYS, a year from the third attempt on), wake whoever gave a signal during the rest and start a new
  attempt when the rest is over. A pending invitation is never sent again nor withdrawn: old_invitations lists them.

With BUYER_NO_POSTS_ROUTE_ENABLED (phase 5, sin_posts.py, BAR-22) on top: the bridges of the buyers who do not post are
read, commented and invited like a buyer (their own role, no journey); invited with fewer comments (or none) also
rests; on the route without posts the bridge is tried before the rest; each retry records its angle and waits for one
web re-check of the buying signals when the rest ends.
"""
import logging
import os
import re
from datetime import datetime, time, timedelta, timezone as dt_timezone
from types import SimpleNamespace
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_date
from . import comprador, operador
from .connectors import ConnectorError, deferred
from .models import ActionExecution, ActionProposal, AuditEvent, BuyerJourney, BuyerTouch, Contact, ObservedPost

log=logging.getLogger(__name__)
Step=BuyerJourney.Step;Route=BuyerJourney.Route;Kind=BuyerTouch.Kind;RestReason=BuyerJourney.RestReason

def setting(name,default):
    return os.environ.get(name,default)

def _int(name,default,low,high):
    try:value=int(str(setting(name,default)).strip())
    except ValueError:return default
    return min(max(value,low),high)

def enabled():
    """BUYER_WARMUP_ENABLED=true turns phase 2 on; off (the default) everything behaves as before it existed."""
    return setting('BUYER_WARMUP_ENABLED','false').strip().lower()=='true'

def comments_needed():return _int('BUYER_WARMUP_COMMENTS',2,1,5)
def max_days():return timedelta(days=_int('BUYER_WARMUP_MAX_DAYS',14,1,60))
def post_max_age():return timedelta(hours=_int('BUYER_POST_MAX_AGE_HOURS',168,24,720))
def read_cap():return _int('BUYER_POSTS_READ_DAILY_LIMIT',8,0,40)
def reread_after():return timedelta(hours=_int('BUYER_POSTS_REREAD_HOURS',72,6,720))
def no_posts_reads():return _int('BUYER_NO_POSTS_READS',2,1,10)
def rest_after():return timedelta(days=_int('BUYER_REST_AFTER_DAYS',21,7,90))
def rest_days():return timedelta(days=_int('BUYER_REST_DAYS',60,7,365))

NO_POSTS_WINDOW=timedelta(days=10)
POSTS_PER_READ=5
MAX_ATTEMPTS=3  # «Tres intentos; después, descanso de un año, sin borrarlo» (plan, 17/11/2026)
LONG_REST=timedelta(days=365)
READ_ACTION='buyer.read'          # one per LinkedIn call, counted per local day against read_cap()
POSTS_READ='buyer.posts_read'     # one per person read, target = contact pk: the reread interval and the no-posts route
OLD_SIGNAL=timedelta(days=30)
MEMBER_ID=re.compile(r'ACo[A-Za-z0-9_\-]{10,100}')  # linkedin_directo.cliente.PROFILE_ID: read posts without the profile

class ReadCapReached(Exception):
    """Today's buyer reads are spent: the rest wait for tomorrow."""

# --------------------------------------------------------------------------- who is warming up

def journey_of(post):
    """The buyer journey of the author of a post without a referent, or None."""
    if not post.author_provider_id or post.referent_id:return None
    return (BuyerJourney.objects.filter(contact__account_id=post.account_id,contact__provider_user_id=post.author_provider_id)
            .exclude(step=Step.LEFT).first())

def warmup_post(post):
    """A comment on this post is a warm-up comment: the switch is on and the author is a buyer of the team (not a
    referent's post), or (phase 5, sin_posts.bridge_of) the bridge to a buyer who does not post. Its draft, rules and
    review follow the «comentario_calentamiento» methodology."""
    if post is None or not enabled():return False
    from . import sin_posts
    return journey_of(post) is not None or sin_posts.bridge_of(post) is not None

def warming(account):
    """Buyers in warm-up who may get a comment: step «calentando», not on the route without posts, not left or resting."""
    return (BuyerJourney.objects.select_related('contact').filter(contact__account=account,step=Step.WARMING)
            .exclude(route=Route.NO_POSTS).exclude(contact__provider_user_id=''))

def second_touch(account):
    """Phase 3 (calentamiento 2, BUYER_FIRST_MESSAGE_ENABLED): accepted buyers who did not interact and got no comment
    since accepting: one more touch before the first message (LI-09-M002-K05). Same reads, rules, review and caps as
    the warm-up; empty with the switch off."""
    from . import mensajes_comprador
    return mensajes_comprador.awaiting_touch(account)

def buyer_ids(account):
    """Authors whose posts belong to the buyers' share of the day: the buyers and (phase 5) their bridges."""
    from . import sin_posts
    ids=set(BuyerJourney.objects.filter(contact__account=account).exclude(contact__provider_user_id='')
            .values_list('contact__provider_user_id',flat=True))
    if sin_posts.active():ids|=set(sin_posts.bridges(account).exclude(provider_user_id='').values_list('provider_user_id',flat=True))
    return ids

def buyer_ids_all():
    return set(BuyerJourney.objects.exclude(contact__provider_user_id='').values_list('contact__provider_user_id',flat=True))

# --------------------------------------------------------------------------- heat: what the person did back (E, H)

# The reciprocity table of docs/plan-outbound.md (17/11/2026): Máxima 5, Alta 3, Media 1. A conversation and a meeting
# are at least as strong as an invitation from them. Weights are a starting point to tune with the month's data.
WEIGHTS={Kind.INVITED_US:5,Kind.MEETING:5,Kind.REPLIED_MESSAGE:3,Kind.OPENED_CONVERSATION:3,Kind.REPLIED_COMMENT:3,
         Kind.COMMENTED_POST:3,Kind.FOLLOWED_US:1,Kind.REACTED_POST:1,Kind.ACCEPTED_OURS:1,
         Kind.BRIDGE_SIGNAL:1}  # phase 5: her colleague (the bridge) accepted or interacted: Media, it was not her
BUY_SIGNAL_WEIGHT=2  # class 08: «La señal no crea listas: ordena a quién primero» (LI-08-M004-K02)
# Signals that end the warm-up at once: they answered a comment of the team or commented on Gustavo's post (Alta), or
# they already invited him or wrote to him.
ACCELERATORS=(Kind.REPLIED_COMMENT,Kind.COMMENTED_POST,Kind.INVITED_US,Kind.OPENED_CONVERSATION,Kind.REPLIED_MESSAGE)
BUY_SIGNAL_KINDS=('ronda','contratacion','expansion')

def _age_factor(at,now):
    return 0.5 if at is None or now-at>OLD_SIGNAL else 1.0

def buying_signals(contact):
    """The buying signals the web stage check cited for the person's company (red.check_stages): [{tipo, fecha, fuente,
    evidencia, visto}]. A signal without a source never counts."""
    check=(contact.classification or {}).get('stage_check') or {}
    return [s for s in check.get('senales') or [] if s.get('fuente') and s.get('tipo') in BUY_SIGNAL_KINDS]

def _signal_date(signal):
    raw=str(signal.get('fecha') or '')
    try:day=parse_date(raw) if len(raw)==10 else parse_date(raw+'-01') if len(raw)==7 else None
    except ValueError:day=None
    return datetime.combine(day,time(12),tzinfo=dt_timezone.utc) if day else None

def buying_signals_from(raw,known_urls,seen_at=None):
    """The signals of a stage verdict (red._judge_stage) that cite one of the URLs the research returned; at most 5."""
    out=[]
    for item in raw or []:
        if not isinstance(item,dict) or item.get('tipo') not in BUY_SIGNAL_KINDS:continue
        url=str(item.get('source_url') or '').strip()
        if url not in known_urls:continue
        fecha=str(item.get('fecha') or '').strip()[:10]
        if fecha and not re.fullmatch(r'\d{4}-\d{2}(?:-\d{2})?',fecha):fecha=''
        out.append({'tipo':item['tipo'],'fecha':fecha,'fuente':url,'evidencia':str(item.get('evidencia') or '')[:300],
                    'visto':seen_at})
    return out[:5]

def weigh(touches,contact,now):
    """The weight of these inbound touches (.kind, .at) plus the person's buying signals, and how many of those."""
    peso=0.0
    for t in touches:peso+=WEIGHTS.get(t.kind,0)*_age_factor(t.at,now)
    buys=buying_signals(contact)
    for s in buys:peso+=BUY_SIGNAL_WEIGHT*_age_factor(_signal_date(s),now)
    return round(peso,2),len(buys)

def heats(contacts,now=None):
    """{contact pk: weight} for these people: their signals in the buyer's log (one query for all) and their buying
    signals. Someone without a journey weighs only their buying signals."""
    now=now or timezone.now();contacts=list(contacts)
    logs={}
    for contact_id,kind,at,key in (BuyerTouch.objects.filter(journey__contact__in=[c.pk for c in contacts],direction=BuyerTouch.Direction.IN)
                                   .order_by('at','created_at').values_list('journey__contact_id','kind','at','key')):
        logs.setdefault(contact_id,[]).append(SimpleNamespace(kind=kind,at=at,key=key))
    return {c.pk:weigh(comprador.current(logs.get(c.pk,[])),c,now)[0] for c in contacts}

def level(peso):
    """frio, tibio or caliente (LI-07-M003-K01): one Alta signal of the last month makes a person warm enough to call hot."""
    return 'caliente' if peso>=3 else 'tibio' if peso>0 else 'frio'

def heat(contact,now=None):
    """How warm the person is (comprador.temperature, weighed): {peso, nivel, senales, senales_de_compra}."""
    t=comprador.temperature(contact,now=now,weigh=True)
    return {'peso':t['peso'],'nivel':t['nivel'],'senales':t['total'],'senales_de_compra':len(t['senales_de_compra'])}

# --------------------------------------------------------------------------- A. read the buyers' posts

def _reads_today(account,now):
    day,_=operador.period_starts(now)
    return AuditEvent.objects.filter(action=READ_ACTION,target=str(account.id),created_at__gte=day).count()

def _reserve(account,contact,now):
    """Count a read before making it, under the operator's policy lock; a person known only by a public id also takes a
    read from the shared profile allowance (OPERATOR_PROFILE_READ_DAILY_LIMIT)."""
    with transaction.atomic():
        operador.policy_lock()
        if _reads_today(account,now)>=read_cap():raise ReadCapReached(f'Tope diario de lecturas de compradores alcanzado ({read_cap()}).')
        if not MEMBER_ID.fullmatch(contact.provider_user_id or ''):
            try:operador.reserve_profile_read(account,'buyer_posts',now)
            except operador.ProfileReadCapReached as exc:raise ReadCapReached(str(exc)) from exc
        AuditEvent.objects.create(action=READ_ACTION,target=str(account.id),created_at=now,metadata={'contact':str(contact.pk)})

def to_read(account,now=None):
    """Journeys whose posts are due for a read, warmest first: warming up (or chosen with the follow on its way), still
    short of comments, not on the route without posts, not read in the last BUYER_POSTS_REREAD_HOURS; with phase 3, also
    the accepted ones waiting for their touch before the first message (second_touch)."""
    now=now or timezone.now()
    recent=set(AuditEvent.objects.filter(action=POSTS_READ,created_at__gte=now-reread_after()).values_list('target',flat=True))
    following=ActionProposal.objects.filter(capability='RED-01',state__in=['proposed','approved','executing']).values('contact_id')
    second={j.pk for j in second_touch(account)}
    rows=(BuyerJourney.objects.select_related('contact').filter(contact__account=account).exclude(route=Route.NO_POSTS)
          .exclude(contact__provider_user_id='').filter(Q(step=Step.WARMING)|Q(step=Step.CHOSEN,contact_id__in=following)|Q(pk__in=second)))
    due=[j for j in rows if str(j.contact_id) not in recent and (j.pk in second or j.warm_comments<comments_needed())]
    weight=heats([j.contact for j in due],now)
    return sorted(due,key=lambda j:(-weight.get(j.contact_id,0),j.warming_at or j.chosen_at))

def reading_due(account,now=None):
    now=now or timezone.now()
    return enabled() and read_cap()>_reads_today(account,now) and bool(to_read(account,now))

def commentable(post,now):
    return bool((post.get('text') or '').strip()) and not post.get('is_repost') and _when(post.get('created_at'))>=now-post_max_age()

def _when(value):
    at=comprador._when(value)
    return at or timezone.now()-timedelta(days=3650)

def _store(account,post):
    """The post as observe stores a referent's, without a referent: an existing row keeps its referent."""
    fields={'share_url':post['share_url'],'author_name':post['author']['display_name'],
            'author_public_identifier':post['author']['public_identifier'],'author_provider_id':post['author']['id'],
            'text':post['text'],'posted_at':post['created_at'],'comments_count':post['comments_counter'],
            'reactions_count':post['reactions_counter'],'is_repost':post['is_repost']}
    row,created=ObservedPost.objects.get_or_create(account=account,provider_post_id=post['id'],defaults=fields)
    if not created:
        for key in ('text','comments_count','reactions_count','share_url'):setattr(row,key,fields[key])
        row.save(update_fields=['text','comments_count','reactions_count','share_url'])
    return row,created

def read_posts(account,connector,now=None):
    """A. Read the recent posts of the buyers due (to_read), within today's buyer reads. Returns a summary; a connector
    failure stops like observe does (a pausing error pauses the account, a deferred one waits for the next run). Only
    inside READ_WINDOW, like every periodic read of the team: an observe Gustavo asks for at night reads his referents,
    never the buyers (`fuera_de_ventana`)."""
    now=now or timezone.now()
    out={'personas':0,'nuevos':0,'vistos':0,'comentables':0,'sin_posts':0,'tope':False,'errores':[]}
    if not operador.within_read_window(now):return dict(out,fuera_de_ventana=True)
    for journey in to_read(account,now):
        contact=journey.contact
        try:
            _reserve(account,contact,now)
            posts=connector.list_user_posts(contact.provider_user_id,limit=POSTS_PER_READ)
        except ReadCapReached:out['tope']=True;break
        except ConnectorError as exc:
            out['errores'].append({'persona':str(contact.pk),'error':str(exc)[:200]})
            if exc.pause:operador.set_account_pause(account,f'Lectura detenida: {exc}');break
            if deferred(exc):break
            continue
        out['personas']+=1;fresh=0;new=0
        for post in posts:
            if not (post.get('text') or '').strip():continue
            _,created=_store(account,post);new+=int(created)
            fresh+=int(commentable(post,now))
        out['nuevos']+=new;out['vistos']+=len(posts)-new;out['comentables']+=fresh
        AuditEvent.objects.create(action=POSTS_READ,target=str(contact.pk),created_at=now,
                                  metadata={'account':str(account.id),'posts':len(posts),'comentables':fresh,'nuevos':new})
        if not fresh:out['sin_posts']+=_maybe_no_posts(journey,now)
    return out

def _maybe_no_posts(journey,now):
    """F. After BUYER_NO_POSTS_READS reads in 10 days without a commentable post, the buyer takes the route «sin_posts»:
    no more reads or comments here; invited at the latest BUYER_WARMUP_MAX_DAYS after the follow (phase 5 builds the
    rest of that route)."""
    empty=AuditEvent.objects.filter(action=POSTS_READ,target=str(journey.contact_id),created_at__gte=now-NO_POSTS_WINDOW,
                                    metadata__comentables=0).count()
    if empty<no_posts_reads():return 0
    comprador.set_route(journey,Route.NO_POSTS,at=now,reason=f'Sin posts para comentar en {empty} lecturas en 10 días.')
    return 1

# --------------------------------------------------------------------------- B. the comment groups

GROUPS=('compradores','comunidad','referentes')
# 17/11/2026 (Gustavo): keep commenting on referents and comment on possible buyers, 15 a day: 8 buyers, 5 referents and
# 2 for the community, which has no source of posts yet, so its 2 pass on. Off, the 15 all go to referents as before.
DEFAULT_SHARE={'compradores':8,'comunidad':2,'referentes':5}

def shares():
    """BUYER_COMMENT_SHARE='compradores=8,comunidad=2,referentes=5': the weights of each group in the day's INT-03 cap."""
    out=dict(DEFAULT_SHARE)
    for item in filter(None,setting('BUYER_COMMENT_SHARE','').split(',')):
        key,_,value=item.partition('=')
        if key.strip() in out and value.strip().isdigit():out[key.strip()]=int(value)
    return out if sum(out.values())>0 else dict(DEFAULT_SHARE)

def quotas(cap):
    """The day's INT-03 cap split by the shares, largest remainder first: 15 → 8/2/5, a weekend's 7 → 4/1/2."""
    share=shares();total=sum(share.values());cap=max(int(cap),0)
    exact={g:cap*share[g]/total for g in GROUPS}
    out={g:int(exact[g]) for g in GROUPS}
    for g in sorted(GROUPS,key=lambda g:(-(exact[g]-out[g]),GROUPS.index(g)))[:cap-sum(out.values())]:out[g]+=1
    return out

def group_of(post,buyers):
    if post.referent_id:return 'referentes'
    return 'compradores' if post.author_provider_id and post.author_provider_id in buyers else None

def used(account,now):
    """Per group: today's comments that wrote (what the cap counts) plus the ones waiting for their turn."""
    day,_=operador.period_starts(now);buyers=buyer_ids(account)
    rows=list(ActionExecution.objects.filter(proposal__account=account,proposal__capability='INT-03',wrote=True,started_at__gte=day)
              .values_list('proposal__post__referent_id','proposal__post__author_provider_id'))
    rows+=list(ActionProposal.objects.filter(account=account,capability='INT-03',state__in=['proposed','approved'],execution__isnull=True)
               .values_list('post__referent_id','post__author_provider_id'))
    out={g:0 for g in GROUPS}
    for referent,author in rows:
        group='referentes' if referent else 'compradores' if author in buyers else None
        if group:out[group]+=1
    return out

def rooms(account,now,available):
    """Slots left today per group. A group with nothing to comment now (not in `available`) passes its slots to the
    next group that has something, in order and wrapping around. The overall cap still rules (operador.capacity_left)."""
    quota=quotas(operador.limits(now).get('INT-03',(0,0))[0]);spent=used(account,now)
    room={g:max(0,quota[g]-spent[g]) for g in GROUPS}
    if not any(g in available for g in GROUPS):return room
    for i,group in enumerate(GROUPS):
        if group in available or not room[group]:continue
        nxt=next(GROUPS[(i+k)%len(GROUPS)] for k in range(1,len(GROUPS)+1) if GROUPS[(i+k)%len(GROUPS)] in available)
        room[nxt]+=room[group];room[group]=0
    return room

def open_comments(account):
    """Warm-up comments drafted and not executed yet, per author."""
    out={}
    for author in (ActionProposal.objects.filter(account=account,capability='INT-03',state__in=['proposed','approved','executing'],
                                                 post__referent__isnull=True).values_list('post__author_provider_id',flat=True)):
        out[author]=out.get(author,0)+1
    return out

def buyer_posts(account,now,recent_authors=(),skips=()):
    """The buyers' posts that may get a comment now, warmest author first, then the newest: the author is warming up
    and still short of BUYER_WARMUP_COMMENTS (written and waiting), the post is recent, nobody commented it, and the
    author got no comment within the author wait (autopiloto.author_cooldown). Phase 3: an accepted buyer waiting for the
    touch before the first message (second_touch) needs one comment, unless one is already on its way."""
    journeys={j.contact.provider_user_id:j for j in warming(account)}
    waiting=open_comments(account)
    need={uid for uid,j in journeys.items() if j.warm_comments+waiting.get(uid,0)<comments_needed()}
    for j in second_touch(account):
        uid=j.contact.provider_user_id
        if not waiting.get(uid):journeys[uid]=j;need.add(uid)
    people={uid:j.contact for uid,j in journeys.items()}
    from . import sin_posts
    for bridge in sin_posts.warming(account):  # phase 5: the bridges, warmed with the same rules ([] with it off)
        uid=bridge.provider_user_id
        if sin_posts.comments_done(bridge)+waiting.get(uid,0)<comments_needed():people[uid]=bridge;need.add(uid)
    posts=list(ObservedPost.objects.filter(account=account,referent__isnull=True,is_repost=False,author_provider_id__in=list(need),
                                           posted_at__gte=now-post_max_age()).exclude(text='').exclude(proposals__capability='INT-03')
               .exclude(author_provider_id__in=list(recent_authors)).exclude(id__in=list(skips)))
    weight=heats([people[uid] for uid in need],now)
    by_author={uid:weight.get(people[uid].pk,0) for uid in need}
    return sorted(posts,key=lambda p:(-by_author.get(p.author_provider_id,0),-p.posted_at.timestamp()))

def draft_inputs(post):
    """What the drafter reads about the buyer besides the post (operador.propose_comment)."""
    journey=journey_of(post);contact=journey.contact if journey else None
    if journey is None:
        from . import sin_posts
        bridge=sin_posts.bridge_of(post)
        if bridge is not None:return sin_posts.draft_inputs(post,bridge)  # phase 5: the bridge's own purpose
    return {'autor':{'nombre':post.author_name,'titular':(contact.headline if contact else '')[:300]},
            'comentarios_del_equipo_en_sus_posts':journey.warm_comments if journey else 0,
            'para_que':'Posible cliente de Gustavo al que todavía no le escribió: el comentario es para que lo reconozca antes de '
                       'la invitación, nunca para venderle.'}

# --------------------------------------------------------------------------- D. when the warm-up is done

PENDING_OR_DONE=('invited','connected','closed','discarded')

def invite_at(state,contact,now=None):
    """When the person may be invited (the fold of their log): the BUYER_WARMUP_COMMENTS-th comment of the attempt, an
    accelerating signal of the last 30 days, or BUYER_WARMUP_MAX_DAYS after the follow. Someone who commented on his
    post (source OWN_POST) right away, as before. None before the follow, and None while an invitation of an earlier
    attempt is still pending (stage «invited»): nothing to invite, it is never sent again."""
    start=state.first.get('warming')
    if start is None or contact.stage in PENDING_OR_DONE:return None
    if contact.source==Contact.Source.OWN_POST:return start
    times=[start+max_days()]
    done=sorted(state.attempt_comments)
    if len(done)>=comments_needed():times.append(done[comments_needed()-1])
    signals=[t.at for t in state.inbound if t.kind in ACCELERATORS and t.at>=start-OLD_SIGNAL]
    if signals:times.append(max(start,min(signals)))
    return min(times)

def invite_ready(contact,now=None):
    """D. Whether a followed buyer with a journey may be invited now: warming up (not resting nor gone) and invite_at
    reached, folded from the log right now (a stored next_at may predate the switch)."""
    now=now or timezone.now();journey=comprador.journey(contact)
    if journey is None or journey.step!=Step.WARMING:return False
    at=invite_at(comprador._fold(comprador._touches(journey)),contact,now)
    return at is not None and at<=now

def invitable(contacts,now=None):
    """red.plan: the invitation candidates. People without a buyer journey keep today's rule (48 h after the follow, or
    right away if they commented on his post); buyers with one wait for invite_ready."""
    from .red import invite_after
    from . import sin_posts
    now=now or timezone.now()
    others=contacts.filter(buyer_journey__isnull=True)
    if sin_posts.active():
        # Phase 5: a bridge is invited with the warm-up rule, not 48 h after the follow.
        ready=[c.pk for c in others.filter(bridge_for__isnull=False) if sin_posts.invite_ready(c,now)]
        others=others.filter(bridge_for__isnull=True)
    else:ready=[]
    others=others.filter(Q(followed_at__lte=now-invite_after())|Q(source=Contact.Source.OWN_POST))
    ready+=[c.pk for c in contacts.filter(buyer_journey__isnull=False) if invite_ready(c,now)]
    return contacts.filter(Q(pk__in=others.values('pk'))|Q(pk__in=ready))

# --------------------------------------------------------------------------- G. rest, wake and retry

def _last_rest(journey):
    return journey.touches.filter(kind=Kind.REST).order_by('-at','-created_at').first()

def wake(journey,now=None):
    """A resting buyer: a signal of hers since the rest began wakes her (retry with that signal as the angle); the end of
    the rest, a new attempt with another post and topic. Returns 'despiertan', 'reintentos' or None. The warm-up's sweep
    and the sequence's rests (secuencia_comprador) use it."""
    from . import sin_posts
    now=now or timezone.now();route=sin_posts.active()
    began=_last_rest(journey)
    signal=(journey.touches.filter(direction=BuyerTouch.Direction.IN,at__gt=began.at).order_by('at').first() if began else None)
    if signal:
        comprador.retry(journey,f'Señal en el descanso: {Kind(signal.kind).label}',at=now,signal=True,
                        kind='senal_en_descanso' if route else '');return 'despiertan'
    if journey.rest_until and journey.rest_until<=now:
        if not route:
            comprador.retry(journey,'Nuevo intento tras el descanso: otro post y otro tema',at=now);return 'reintentos'
        # Phase 5: one web re-check of her buying signals first (6d), then an angle no earlier attempt used (6c).
        if sin_posts.recheck_waiting(journey,now):return None
        return sin_posts.retry(journey,now)
    return None

def sweep(account,now=None):
    """From red.plan: rest the buyers who got their comments, were invited and did not accept within
    BUYER_REST_AFTER_DAYS (the invitation stays pending: never sent again, never withdrawn); wake a resting buyer who gave
    a signal since the rest began (retry with that signal as the angle); retry when the rest is over. Also refreshes the
    next_at of journeys folded before the switch. Each person on its own savepoint: one failure never stops the plan."""
    from . import sin_posts
    now=now or timezone.now();out={'descanso':0,'despiertan':0,'reintentos':0,'proximo':0,'fallos':0}
    route=sin_posts.active()
    if route:out.update(puente_antes_del_descanso=0,puentes_pedidos=0)  # phase 5
    def guarded(fn,journey):
        try:
            with transaction.atomic():return fn(journey)
        except Exception as exc:  # noqa: BLE001 - the sweep never stops the network plan
            log.exception('Calentamiento: fallo con el recorrido %s',journey.pk)
            out['fallos']+=1
            AuditEvent.objects.create(action='buyer.warmup_failed',target=str(journey.pk),metadata={'error':type(exc).__name__,'detail':str(exc)[:300]})
            return None
    def rest(journey):
        # Phase 5 (6a): invited with fewer comments than the warm-up (or none, on the route without posts) rests too.
        if journey.warm_comments<comments_needed() and not route:return False
        state=comprador._fold(comprador._touches(journey))
        moments=[state.invited_at,*state.attempt_comments]
        if route:
            began=state.attempts[-1]['desde']
            # What her bridge did in this attempt gives her more time; an invitation still pending from an earlier attempt
            # (never sent again) counts from the start of this one.
            moments+=[at for at in sin_posts.signal_times(state) if not began or at>=began]
            if state.invited_at is None and began:moments.append(began)
        last=max([at for at in moments if at],default=None)
        if last is None or now<last+rest_after():return False
        # Phase 5 (6b): «no publica y la ruta alterna no dio resultado»: the bridge first, then the rest.
        if route and journey.route==Route.NO_POSTS and sin_posts.hold_rest(journey,now):
            out['puente_antes_del_descanso']+=1;return False
        until=now+(LONG_REST if journey.attempt>=MAX_ATTEMPTS else rest_days())
        comprador.rest(journey,RestReason.INVITE_NOT_ACCEPTED,until,at=now,
                       note=f'{journey.warm_comments} comentarios e invitación sin aceptar en {rest_after().days} días.')
        return True
    pending=BuyerJourney.objects.select_related('contact').filter(contact__account=account,contact__stage='invited',
                                                                  step__in=[Step.INVITED,Step.WARMING])
    for journey in pending:out['descanso']+=int(bool(guarded(rest,journey)))
    resting=BuyerJourney.objects.select_related('contact').filter(contact__account=account,step=Step.RESTING)
    from . import respuesta_comprador
    if respuesta_comprador.active():
        # Phase 6: «no es el momento» comes back on the date she said, with what she said (respuesta_comprador._wake);
        # a message of hers during the rest wakes her by itself (comprador.WAKE).
        resting=resting.exclude(rest_reason=BuyerJourney.RestReason.NOT_NOW)
    for journey in resting:
        result=guarded(lambda j:wake(j,now),journey)
        if result:out[result]+=1
    for journey in BuyerJourney.objects.select_related('contact').filter(contact__account=account,step=Step.WARMING):
        if route and journey.route==Route.NO_POSTS:  # phase 5: nothing real to cite → his bridge, right away
            out['puentes_pedidos']+=guarded(lambda j:sin_posts.early(j,now),journey) or 0
        at=invite_at(comprador._fold(comprador._touches(journey)),journey.contact,now)
        if at!=journey.next_at:
            BuyerJourney.objects.filter(pk=journey.pk).update(next_at=at);out['proximo']+=1
    return out

def old_invitations(days=21,account=None,now=None):
    """Invitations still pending after `days` (1–365), oldest first, for Gustavo to withdraw by hand if he wants: the
    team never withdraws nor sends one again (linkedin_directo/permitidas.py). Read-only."""
    try:days=int(days)
    except (TypeError,ValueError):raise ValueError('dias debe ser un número entre 1 y 365.') from None
    if not 1<=days<=365:raise ValueError('dias debe ser un número entre 1 y 365.')
    now=now or timezone.now()
    rows=Contact.objects.filter(stage='invited',invited_at__lte=now-timedelta(days=days)).select_related('buyer_journey').order_by('invited_at')
    if account is not None:rows=rows.filter(account=account)
    out=[]
    for c in rows:
        journey=getattr(c,'buyer_journey',None)
        out.append({'persona':str(c.pk),'nombre':c.display_name,'titular':(c.headline or '')[:200],'perfil':c.profile_url,
                    'invitada':c.invited_at.isoformat(),'dias':(now-c.invited_at).days,'papel':(c.classification or {}).get('role') or '',
                    'recorrido':{'paso':journey.step,'comentarios':journey.warm_comments,'intento':journey.attempt,
                                 'descanso_hasta':journey.rest_until.isoformat() if journey.rest_until else None} if journey else None})
    return {'generado':now.isoformat(),'dias':days,'total':len(out),'invitaciones':out,
            'nota':'Retirar una invitación es manual, en LinkedIn. El equipo no retira ni vuelve a invitar mientras siga pendiente.'}
