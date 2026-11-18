"""The buyer's journey, phase 1 of docs/plan-outbound.md «El sistema del comprador»: a structured record per buyer and
the minimum funnel, without changing anything the team does.

- BuyerJourney (models.py) is one row per buyer beside Contact, whose Stage stays as it is. BuyerTouch is its
  append-only log: what the team or Gustavo did (saliente), what the person did (entrante: the signals) and changes
  of state (estado).
- Facts, not events: update(contact) reads every fact Barrio already keeps about the person (executions, comments on
  Gustavo's posts, comment outcomes, invitations, conversations, opportunities, the contact's own dates), appends the
  touches it does not have yet (each `key` names its source, so a fact is recorded once) and folds the whole log, in
  time order, into the journey. The live hooks and the rebuild run that same function; running it twice changes
  nothing.
- The hooks (on_contact, on_execution, on_comment_outcome) are passive: they run after the real action, each in its
  own savepoint, and a failure is audited (buyer.record_failed) and swallowed. Nothing here reads LinkedIn, sends or
  decides anything, and no gate, cap, ramp or priority reads these tables.
- Phases 2–6 write through record(), rest(), retry(), leave(), set_route() and set_angle(), which validate the
  transition, and read journey(), current() (a log without the stand-ins a better source replaced), temperature(),
  due(), drafts() and funnel().
"""
import logging
import os
import time
from datetime import timedelta
from types import SimpleNamespace
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from .models import (ActionExecution, ActionOutcome, AuditEvent, BuyerDraft, BuyerJourney, BuyerTouch, Contact, Conversation,
                     EvidencePerson, ObservedPost, Opportunity, PostComment)

log=logging.getLogger(__name__)
Step=BuyerJourney.Step;Kind=BuyerTouch.Kind;Direction=BuyerTouch.Direction;Source=BuyerTouch.Source
RestReason=BuyerJourney.RestReason;ExitReason=BuyerJourney.ExitReason;Route=BuyerJourney.Route

def signal_name(kind,account):
    """How a signal is named to the member whose buyer it is: the label of always («Comentó en un post de Gustavo») for
    the first member and without members; another member's own name instead (organizaciones, phase 5). The stored
    value never changes: «gustavo» in values and labels is «the member who owns it»."""
    from . import miembros
    label=Kind(kind).label
    member=miembros.member_of_account(account) if account is not None else None
    if member is None or miembros.is_first(member):return label
    return label.replace('Gustavo',member.display_name)

# The active steps in order; «descanso» and «salio» stand apart from them.
STEPS=[Step.CHOSEN,Step.WARMING,Step.INVITED,Step.ACCEPTED,Step.MESSAGE_1,Step.MESSAGE_2,Step.MESSAGE_3,Step.MESSAGE_4,
       Step.REPLIED,Step.INTERESTED,Step.MEETING]
MESSAGE_STEPS=[Step.MESSAGE_1,Step.MESSAGE_2,Step.MESSAGE_3,Step.MESSAGE_4]
OUT=Direction.OUT;IN=Direction.IN;STATE=Direction.STATE
DIRECTION={Kind.CHOSEN:STATE,Kind.ROUTE:STATE,Kind.ANGLE:STATE,Kind.REST:STATE,Kind.RETRY:STATE,Kind.EXIT:STATE,Kind.REOPENED:STATE,
           Kind.ALREADY_CONNECTED:STATE,Kind.NO_MESSAGE:STATE,Kind.DRAFT:STATE,Kind.OPPORTUNITY:STATE,Kind.INTERESTED:STATE,Kind.REFERRED:STATE,
           Kind.BRIDGE:STATE,Kind.RECHECK:STATE,Kind.REPLY_CLASSIFIED:STATE,Kind.MEETING_CANCELLED:STATE,
           Kind.FOLLOW:OUT,Kind.COMMENT:OUT,Kind.REACTION:OUT,Kind.THREAD_REPLY:OUT,Kind.VISIT:OUT,Kind.INVITATION:OUT,
           Kind.ACCEPTED_THEIRS:OUT,Kind.MESSAGE:OUT,Kind.MESSAGE_SEEN:OUT,Kind.REPLY_SENT:OUT,
           Kind.REPLIED_COMMENT:IN,Kind.COMMENTED_POST:IN,Kind.REACTED_POST:IN,Kind.FOLLOWED_US:IN,Kind.INVITED_US:IN,
           Kind.ACCEPTED_OURS:IN,Kind.OPENED_CONVERSATION:IN,Kind.REPLIED_MESSAGE:IN,Kind.MEETING:IN,
           Kind.BRIDGE_SIGNAL:IN}  # phase 5: her colleague (the bridge) accepted or interacted (sin_posts.relayed)
SIGNALS=[kind for kind,direction in DIRECTION.items() if direction==IN]
CONNECTION=(Kind.ACCEPTED_OURS,Kind.ACCEPTED_THEIRS,Kind.ALREADY_CONNECTED)
# Something the person did that brings a journey back from a rest or a closure by rule (never from a definitive exit).
WAKE=(*CONNECTION,Kind.REPLIED_MESSAGE,Kind.OPENED_CONVERSATION,Kind.MEETING)
# The person asked, said no, or Gustavo discarded them: the buyer machine never contacts them again.
DEFINITIVE=(ExitReason.DO_NOT_CONTACT,ExitReason.NOT_INTERESTED,ExitReason.DISCARDED_BY_GUSTAVO)
# Only rest(), retry() and leave() write these: they validate the transition.
TRANSITIONS=(Kind.REST,Kind.RETRY,Kind.EXIT,Kind.REOPENED)
ACTIVE_CONTACT_STAGES=('candidate','fit','followed','incoming')
SMALL_SAMPLE=30  # course rule (LI-12-M001-K04): fewer invitations than this are not judged
SMALL_SAMPLE_TEXT='Muestra chica: menos de 30 invitaciones; no se juzga.'

def enabled():
    """BUYER_RECORD_ENABLED=false stops the passive hooks (a kill switch for the deploy); the rebuild still works."""
    return os.environ.get('BUYER_RECORD_ENABLED','true').lower()=='true'

def _when(value):
    if not value:return None
    if hasattr(value,'tzinfo'):return value if value.tzinfo else None
    try:at=parse_datetime(str(value))
    except ValueError:return None
    return at if at and at.tzinfo else None

# --------------------------------------------------------------------------- who is a buyer

def chosen(contact):
    """The team goes after this buyer: classified as a fitting «comprador» and the web check found no evidence against
    (or Gustavo said the person fits). Since 17/11/2026 (BAR-24) a pending check holds nothing: the buyer is chosen with
    her level (nivel_comprador), of any region."""
    c=contact.classification or {}
    if c.get('role')!='comprador' or not c.get('fit'):return False
    check=c.get('stage_check')
    return not check or check.get('state')!='failed' or bool(c.get('confirmed_by_gustavo'))

def was_chosen(contact):
    """Chosen now, or a buyer the team already acted on (followed or invited) under earlier criteria."""
    c=contact.classification or {}
    return chosen(contact) or (c.get('role')=='comprador' and bool(contact.followed_at or contact.invited_at))

def _out_of_criteria(contact):
    c=contact.classification or {}
    if c.get('confirmed_by_gustavo'):return False
    return c.get('role')!='comprador' or not c.get('fit') or (c.get('stage_check') or {}).get('state')=='failed'

def _chosen_at(contact,earliest):
    """When the team chose the person: the classification, or the web check (or Gustavo's «Sí, encaja») that let them
    through; never after the first thing the team did to them."""
    c=contact.classification or {}
    moments=[_when(c.get('classified_at'))]
    check=c.get('stage_check') or {}
    if check.get('state')=='ok':moments.append(_when(check.get('checked_at')))
    elif check:moments.append(_when((c.get('confirmed_by_gustavo') or {}).get('at')))
    at=max([m for m in moments if m],default=None) or contact.discovered_at
    return min(at,earliest) if earliest else at

# --------------------------------------------------------------------------- facts Barrio already keeps

def _fact(kind,at,key,detail=None,**refs):
    return {'kind':kind,'at':at,'key':key[:200],'detail':detail or {},'refs':refs}

def _done(execution):
    """A write that happened: confirmed, or accepted by the provider and not yet read back."""
    return execution.state=='confirmed' or (execution.state=='sent' and execution.wrote)

def _note_sent(proposal):
    return AuditEvent.objects.filter(action='network.note_sent',target=str(proposal.pk)).exists()

def _network_facts(contact):
    facts=[]
    for e in ActionExecution.objects.select_related('proposal').filter(proposal__contact=contact).order_by('started_at'):
        if not _done(e):continue
        p=e.proposal
        if p.capability=='RED-01':kind,detail=Kind.FOLLOW,{'escribio':e.wrote}
        elif p.capability=='RED-02':kind,detail=Kind.INVITATION,{'con_nota':_note_sent(p),'escribio':e.wrote}
        elif p.capability=='RED-04':kind,detail=(Kind.ACCEPTED_THEIRS if e.wrote else Kind.ALREADY_CONNECTED),{}
        else:continue
        facts.append(_fact(kind,e.started_at,f'ejecucion:{e.pk}',detail,proposal=p,execution=e))
    return facts

def _post_facts(contact):
    """The team's comments and reactions on the person's posts (INT-03/INT-02, ObservedPost.author_provider_id) and its
    replies and reactions to the person's comments on Gustavo's posts (INT-04/INT-02 on a PostComment)."""
    facts=[];uid=contact.provider_user_id
    rows=(ActionExecution.objects.select_related('proposal','proposal__post')
          .filter(Q(proposal__account_id=contact.account_id,proposal__capability__in=['INT-03','INT-02'],proposal__post__author_provider_id=uid)
                  |Q(proposal__comment__contact=contact)) if uid else ActionExecution.objects.filter(proposal__comment__contact=contact))
    for e in rows.order_by('started_at'):
        if not _done(e):continue
        p=e.proposal
        if p.comment_id:kind=Kind.THREAD_REPLY if p.capability=='INT-04' else Kind.REACTION
        else:kind=Kind.COMMENT if p.capability=='INT-03' else Kind.REACTION
        facts.append(_fact(kind,e.started_at,f'ejecucion:{e.pk}',{'escribio':e.wrote,'capacidad':p.capability},
                           proposal=p,execution=e,post=p.post,comment=p.comment))
    return facts

def _contact_facts(contact,facts):
    """What the contact's own dates say when no execution does (a follow or an invitation found already in place by a
    pre-check, a connection the sync read)."""
    kinds={f['kind'] for f in facts};out=[]
    if contact.followed_at and Kind.FOLLOW not in kinds:out.append(_fact(Kind.FOLLOW,contact.followed_at,'contacto:seguido',{'origen':'contacto'}))
    if contact.invited_at and Kind.INVITATION not in kinds:
        out.append(_fact(Kind.INVITATION,contact.invited_at,'contacto:invitado',{'con_nota':None,'origen':'contacto'}))
    connected=contact.connected_at or (contact.updated_at if contact.stage=='connected' else None)
    if connected and not kinds&set(CONNECTION):
        invited=[f['at'] for f in facts+out if f['kind']==Kind.INVITATION]
        kind=Kind.ACCEPTED_OURS if invited and min(invited)<=connected else Kind.ALREADY_CONNECTED
        out.append(_fact(kind,connected,'contacto:conectado',{'origen':'contacto'}))
    return out

def _evidence_facts(contact):
    """Invitations the person sent Gustavo (evidencia.relationship, else the contact's history, else its source) and the
    follows or reactions the shared evidence identifies."""
    facts=[];received=[]
    person=EvidencePerson.objects.filter(account_id=contact.account_id,provider_user_id=contact.provider_user_id).first()
    if person:
        for obs in person.observations.filter(kind__in=['invitation','follower','reactor']).order_by('observed_at'):
            at=obs.event_at or obs.observed_at
            if obs.kind=='invitation' and (obs.details or {}).get('direction')=='received':
                received.append(_fact(Kind.INVITED_US,at,f'evidencia:{obs.key}',{'origen':'invitacion_recibida'}))
            elif obs.kind=='follower':facts.append(_fact(Kind.FOLLOWED_US,at,f'evidencia:{obs.key}',{'origen':obs.source}))
            elif obs.kind=='reactor':facts.append(_fact(Kind.REACTED_POST,at,f'evidencia:{obs.key}',{'origen':obs.source}))
    if not received:
        for event in contact.history or []:
            at=_when(event.get('at')) if isinstance(event,dict) and event.get('event')=='incoming' else None
            if at:received.append(_fact(Kind.INVITED_US,at,f'historial:incoming:{event["at"]}',{'origen':'historial'}))
    if not received and contact.source==Contact.Source.INCOMING:
        received.append(_fact(Kind.INVITED_US,contact.discovered_at,'contacto:entrante',{'origen':'contacto'}))
    return facts+received

def _own_post_facts(contact):
    """Comments the person left on Gustavo's posts, and Gustavo's answer to the suggested first message of that thread
    («Hecho, le escribí» / «No escribirle», respuestas.close_dm)."""
    facts=[]
    for row in PostComment.objects.filter(contact=contact,own=False).order_by('commented_at','observed_at'):
        facts.append(_fact(Kind.COMMENTED_POST,row.commented_at or row.observed_at,f'comentario_post:{row.pk}',{'hilo':bool(row.thread_id)},comment=row))
        closed=(row.decision or {}).get('dm_closed') or {}
        at=_when(closed.get('at'))
        if at:
            kind=Kind.MESSAGE if closed.get('how')=='enviado' else Kind.NO_MESSAGE
            facts.append(_fact(kind,at,f'mensaje_sugerido:{row.pk}',{'fuente':'mensaje_sugerido'},comment=row))
    return facts

def _outcome_facts(contact):
    """The person answered one of the team's comments (the 72 h outcome of an INT-03 lists who answered)."""
    uid=contact.provider_user_id
    if not uid:return []
    rows=(ActionOutcome.objects.select_related('execution__proposal__post')
          .filter(execution__proposal__capability='INT-03',execution__proposal__account_id=contact.account_id,repliers__contains=[uid]))
    out=[]
    for o in rows.order_by('captured_at'):
        post=o.execution.proposal.post
        out.append(_fact(Kind.REPLIED_COMMENT,o.captured_at,f'desenlace:{o.pk}',{'autor_del_post':bool(post and post.author_provider_id==uid),
                         'visto_a_las':o.kind},outcome=o,execution=o.execution,post=post))
    return out

def _conversation_facts(contact,facts,known):
    """Each message of the person's conversations, as the inbox snapshot keeps them: Gustavo's (mensaje_visto) and
    theirs, which answers a message of his when one came before it and opens the conversation otherwise."""
    rows=[]
    for conversation in Conversation.objects.filter(contact=contact):
        for message in conversation.messages or []:
            at=_when(message.get('at'))
            if at and message.get('id') and not message.get('hidden'):rows.append((at,conversation,message))
    rows.sort(key=lambda row:row[0])
    outbound=[f['at'] for f in facts if f['kind']==Kind.MESSAGE]+[t.at for t in known if t.kind in (Kind.MESSAGE,Kind.MESSAGE_SEEN)]
    outbound+=[at for at,_,message in rows if message.get('from_me')]
    first=min(outbound,default=None);out=[]
    for at,conversation,message in rows:
        if message.get('from_me'):kind=Kind.MESSAGE_SEEN
        else:kind=Kind.REPLIED_MESSAGE if first and first<at else Kind.OPENED_CONVERSATION
        out.append(_fact(kind,at,f'conversacion:{conversation.pk}:{message["id"]}',{},conversation=conversation))
    return out

def _draft_facts(contact):
    """Phase 3 (mensajes_comprador.py): each decided draft (ready, discarded or not written, with who stopped it) and what
    Gustavo did with a first message of the journey («Hecho, le escribí» / «No escribirle»). The detail only holds what
    never changes once decided."""
    out=[];State=BuyerDraft.State
    for d in BuyerDraft.objects.filter(contact=contact).exclude(decided_at__isnull=True).order_by('decided_at'):
        out.append(_fact(Kind.DRAFT,d.decided_at,f'borrador:{d.pk}',{'tipo':d.kind,'numero':d.number,'intento':d.attempt,
                         'resultado':'parado' if d.stopped_by else 'listo','por':d.stopped_by}))
        if d.kind==BuyerDraft.Kind.REPLY and d.closed_at and d.state==State.SENT:
            # Phase 6: Gustavo answered what she wrote («Hecho, le escribí» on the reply card).
            out.append(_fact(Kind.REPLY_SENT,d.closed_at,f'borrador:{d.pk}:enviado',{'fuente':'respuesta','numero':d.number,
                             'intento':d.attempt}))
        if d.kind!=BuyerDraft.Kind.MESSAGE or not d.closed_at:continue
        if d.state==State.SENT:
            out.append(_fact(Kind.MESSAGE,d.closed_at,f'borrador:{d.pk}:enviado',{'fuente':'recorrido','numero':d.number}))
        elif d.state==State.NOT_SENT:
            out.append(_fact(Kind.NO_MESSAGE,d.closed_at,f'borrador:{d.pk}:no',{'fuente':'recorrido','numero':d.number}))
    return out

def _opportunity_facts(contact):
    return [_fact(Kind.OPPORTUNITY,o.created_at,f'oportunidad:{o.pk}',{'etapa':o.stage,'modalidad':o.modality},opportunity=o)
            for o in Opportunity.objects.filter(contact=contact).order_by('created_at')]

def _bridge_facts(contact):
    """Phase 5 (BUYER_NO_POSTS_ROUTE_ENABLED): what her bridge did (accepted Gustavo's invitation, answered a comment,
    commented on his post, invited or wrote to him), as signals of hers (senal_puente). Nothing with the switch off."""
    from . import sin_posts
    if not sin_posts.active():return []
    journey=BuyerJourney.objects.filter(contact=contact).first()
    return sin_posts.relayed(journey) if journey else []

def facts(contact,known=()):
    """Every touch and signal Barrio's own rows show for this person, as {kind, at, key, detail, refs}; no state changes."""
    out=_network_facts(contact)+_post_facts(contact)
    out+=_contact_facts(contact,out)
    out+=_evidence_facts(contact)+_own_post_facts(contact)+_outcome_facts(contact)
    out+=_draft_facts(contact)
    out+=_conversation_facts(contact,out,known)+_opportunity_facts(contact)
    out+=_bridge_facts(contact)
    return [f for f in out if f['at']]

# --------------------------------------------------------------------------- fold: the log, in order, into the journey

class _Fold:
    """The journey a log of touches describes. Milestones are the first time each thing happened, across attempts; the
    step belongs to the current attempt (a follow and a connection last; an invitation and messages do not)."""
    def __init__(self):
        self.first={};self.attempt=1;self.attempts=[{'numero':1,'desde':None,'angulo':'','hasta':None,'motivo':''}]
        self.following=self.connected=False;self.rest=None;self.exit=None;self.route=None;self.invite_note=None
        self.visits=0;self.comments=[];self.inbound=[];self.last_message=None
        self.booked={}  # phase 6: every meeting still booked, across attempts, {booking: when it was booked}
        self._attempt()
    def _attempt(self):
        self.invited_at=None;self.messages=0;self.seen=self.replied=self.interested=self.meeting=False;self.attempt_comments=[]
        self.drafted=False  # phase 3: the first message of this attempt was prepared, or the team decided not to write it
        self.sent=[]  # phase 4: this attempt's «Hecho, le escribí» (MESSAGE touches), in order
        self.replied_at=None  # phase 4: her first reply to a message of this attempt
        self.reply_type=''    # phase 6: the type of her latest classified reply in this attempt
        self.bookings={}      # phase 6: this attempt's meetings still booked, {booking: its start or None}
    def mark(self,name,at):
        if name not in self.first or at<self.first[name]:self.first[name]=at
    def wake(self):
        if self.rest:self.rest=None;self.attempts[-1].update(hasta=None,motivo='')
        if self.exit and self.exit[0] not in DEFINITIVE:self.exit=None
    def step(self):
        if self.exit:return Step.LEFT
        if self.rest:return Step.RESTING
        if self.meeting:return Step.MEETING
        if self.interested:return Step.INTERESTED
        if self.replied:return Step.REPLIED
        if self.messages or self.seen:return MESSAGE_STEPS[min(max(self.messages,1),4)-1]
        if self.connected:return Step.ACCEPTED
        if self.invited_at:return Step.INVITED
        if self.following:return Step.WARMING
        return Step.CHOSEN
    def apply(self,t):
        kind,at,d=t.kind,t.at,t.detail or {}
        if t.direction==IN:self.inbound.append(t)
        if kind==Kind.CHOSEN:
            self.mark('chosen',at)
            if not self.attempts[0]['desde'] or at<self.attempts[0]['desde']:self.attempts[0]['desde']=at
        elif kind==Kind.FOLLOW:self.mark('warming',at);self.following=True
        elif kind==Kind.COMMENT:self.comments.append(at);self.attempt_comments.append(at)
        elif kind==Kind.VISIT:self.visits+=1
        elif kind==Kind.INVITATION:
            if 'invited' not in self.first:self.invite_note=d.get('con_nota')
            self.mark('invited',at);self.invited_at=self.invited_at or at
        elif kind in CONNECTION:self.mark('accepted',at);self.connected=True
        elif kind in (Kind.MESSAGE,Kind.MESSAGE_SEEN):
            self.mark('first_message',at);self.last_message=max(filter(None,(self.last_message,at)))
            if kind==Kind.MESSAGE:self.messages+=1;self.sent.append(t)
            else:self.seen=True
        elif kind==Kind.REPLIED_MESSAGE:
            self.mark('replied',at);self.replied=True;self.replied_at=self.replied_at or at
        elif kind==Kind.INTERESTED:self.mark('interested',at);self.interested=True
        elif kind==Kind.MEETING:self._meeting(t,at,d)
        elif kind==Kind.MEETING_CANCELLED:self._cancelled(d.get('reserva') or '')
        elif kind==Kind.REPLY_CLASSIFIED:self.reply_type=d.get('tipo','')
        elif kind==Kind.REPLY_SENT:self.last_message=max(filter(None,(self.last_message,at)))
        elif kind==Kind.DRAFT:self.drafted=self.drafted or (d.get('tipo')==BuyerDraft.Kind.MESSAGE and d.get('numero',1)==1)
        elif kind==Kind.ROUTE:self.route=d.get('ruta') or self.route
        elif kind==Kind.ANGLE:self.attempts[-1]['angulo']=d.get('angulo','')
        elif kind==Kind.REST:
            self.rest=(d.get('motivo',''),_when(d.get('hasta')))
            self.attempts[-1].update(hasta=at,motivo=d.get('motivo',''))
        elif kind==Kind.RETRY:
            self.rest=None;self.attempt+=1;self._attempt()
            self.attempts.append({'numero':self.attempt,'desde':at,'angulo':d.get('angulo',''),'hasta':None,'motivo':''})
        elif kind==Kind.EXIT:
            if not (self.exit and self.exit[0] in DEFINITIVE):self.exit=(d.get('motivo',''),at,self.step())
        elif kind==Kind.REOPENED:
            if self.exit and self.exit[0] not in DEFINITIVE:self.exit=None
        if kind in WAKE:self.wake()
    def _meeting(self,t,at,d):
        """Phase 6 (agenda_calcom): a booked meeting. A reschedule (`reemplaza`) replaces the booking it moves and keeps
        when the first one was booked; the milestone is the earliest meeting still booked."""
        ref=d.get('reserva') or t.key;old=d.get('reemplaza') or ''
        booked=self.booked.pop(old,at) if old else at
        self.bookings.pop(old,None)
        self.bookings[ref]=_when(d.get('inicio'));self.booked[ref]=min(booked,self.booked.get(ref,booked))
        self.meeting=True;self.first['meeting']=min(self.booked.values())
    def _cancelled(self,ref):
        """Phase 6: the meeting was cancelled. With none left booked the journey goes back to «interesado» and the
        funnel no longer counts the meeting."""
        self.bookings.pop(ref,None);self.booked.pop(ref,None)
        self.meeting=bool(self.bookings)
        if self.booked:self.first['meeting']=min(self.booked.values())
        else:self.first.pop('meeting',None)
    def meeting_date(self):
        starts=[at for at in self.bookings.values() if at]
        return max(starts) if starts else None

# A fact read from the contact's dates or history stands in for one with its own row (an execution, the evidence) only
# until that row shows up: the log keeps both, the fold and the reads use the best one. Phase 4: her reply seen in the
# chat list (secuencia_comprador._stop) stands in until the inbox reads her thread.
FALLBACK_RANK={'historial:':1,'contacto:':2,'lista:':3}

def _rank(touch):
    key=getattr(touch,'key','') or ''
    return next((rank for prefix,rank in FALLBACK_RANK.items() if key.startswith(prefix)),0)

def _group(kind):
    return 'conexion' if kind in CONNECTION else kind

def current(touches):
    """The touches without the stand-ins a better source of the same kind replaced, in their order."""
    touches=list(touches);best={}
    for t in touches:best[_group(t.kind)]=min(best.get(_group(t.kind),9),_rank(t))
    return [t for t in touches if _rank(t)==best[_group(t.kind)]]

def _fold(touches):
    state=_Fold()
    for touch in current(touches):state.apply(touch)
    return state

def next_at(journey,state,contact):
    """When something is due. Phase 1 mirrors today's rule: a followed person may be invited NETWORK_INVITE_AFTER_HOURS
    after the follow (right away when they commented on his post); a rest ends at its date. Phase 2, with
    BUYER_WARMUP_ENABLED: when the warm-up is done (calentamiento.invite_at). Phase 3, with BUYER_FIRST_MESSAGE_ENABLED:
    when the first message is due after the acceptance (mensajes_comprador.message_at). Phase 4, with
    BUYER_SEQUENCE_ENABLED: when the next follow-up (or her rest after message 4) is due (secuencia_comprador.due). Each
    phase adds its own."""
    step=state.step()
    if step==Step.RESTING:return state.rest[1]
    if step in MESSAGE_STEPS:
        from . import secuencia_comprador
        return secuencia_comprador.due(state) if secuencia_comprador.enabled() else None
    if step==Step.ACCEPTED:
        from . import mensajes_comprador
        return mensajes_comprador.message_at(state) if mensajes_comprador.enabled() else None
    if step==Step.WARMING and 'warming' in state.first:
        if contact.source==Contact.Source.OWN_POST:return state.first['warming']
        from . import calentamiento
        if calentamiento.enabled():return calentamiento.invite_at(state,contact)
        from .red import invite_after
        return state.first['warming']+invite_after()
    return None

def _project(journey,state,contact,has_posts):
    first=state.first;invited=first.get('invited')
    journey.step=state.step()
    journey.chosen_at=first.get('chosen') or journey.chosen_at
    for field,name in (('warming_at','warming'),('invited_at','invited'),('accepted_at','accepted'),('first_message_at','first_message'),
                       ('replied_at','replied'),('interested_at','interested'),('meeting_at','meeting')):
        setattr(journey,field,first.get(name))
    journey.invite_note=state.invite_note if invited else None
    journey.last_message_at=state.last_message
    journey.messages_sent=state.messages
    journey.warm_comments=sum(1 for at in state.attempt_comments if not state.invited_at or at<state.invited_at)
    journey.comments_before_invite=sum(1 for at in state.comments if not invited or at<invited)
    journey.visits=state.visits
    journey.inbound_signals=len(state.inbound)
    journey.last_inbound_at=max((t.at for t in state.inbound),default=None)
    # Her own signals: what her bridge did (phase 5) warms her, but she did not do it.
    journey.signal_before_invite=any(not invited or t.at<invited for t in state.inbound if t.kind!=Kind.BRIDGE_SIGNAL)
    journey.route=state.route or (Route.COMMENTS if state.comments or has_posts else Route.UNKNOWN)
    journey.attempt=state.attempt
    journey.reply_type=state.reply_type
    journey.meeting_date=state.meeting_date() if state.meeting else None
    journey.attempts=[dict(a,desde=a['desde'].isoformat() if a['desde'] else None,hasta=a['hasta'].isoformat() if a['hasta'] else None)
                      for a in state.attempts]
    journey.rest_reason,journey.rest_until=(state.rest[0],state.rest[1]) if state.rest else ('',None)
    journey.exit_reason,journey.exited_at,journey.exit_step=(state.exit[0],state.exit[1],state.exit[2]) if state.exit else ('',None,'')
    journey.next_at=next_at(journey,state,contact)
    # BAR-24: the level and score the team went after her with. While she is only chosen they follow her level (the web
    # check usually answers the same day); the first thing the team does (the follow, or an invitation) fixes them.
    if not journey.entry_level or not (first.get('warming') or invited):
        from . import nivel_comprador
        for field,value in nivel_comprador.entry_of(contact).items():setattr(journey,field,value)
    # BAR-25: her line and segment, the same way (fixed by the first follow or invitation; once more while still empty).
    from . import projectapp
    if projectapp.enabled() and (not journey.line or not (first.get('warming') or invited)):
        line=projectapp.line_of(contact)
        if line:journey.line=line;journey.segment=projectapp.segment_of(contact)
    journey.updated_at=timezone.now()

# --------------------------------------------------------------------------- exits and reopenings the contact shows

def _history_at(contact,events):
    for event in reversed(contact.history or []):
        if isinstance(event,dict) and event.get('event') in events:
            at=_when(event.get('at'))
            if at:return at,event
    return None,{}

def exit_today(contact):
    """(reason, at) when the contact says the person is out under today's rules, else None."""
    if contact.stage=='closed':
        at,_=_history_at(contact,('closed',))
        return ExitReason.INVITATION_CLOSED,at or contact.updated_at
    if contact.stage=='discarded':
        at,event=_history_at(contact,('discarded','rejected','stage_checked','classified','requeued'))
        if event.get('event')=='rejected' or AuditEvent.objects.filter(action='network.contact_discarded',target=str(contact.pk)).exists():
            return ExitReason.DISCARDED_BY_GUSTAVO,at or contact.updated_at
        if event.get('event')=='discarded' and (event.get('detail') or '').startswith('Perfil restringido'):
            return ExitReason.RESTRICTED,at or contact.updated_at
        return ExitReason.OUT_OF_CRITERIA,at or contact.updated_at
    if contact.stage in ACTIVE_CONTACT_STAGES and _out_of_criteria(contact):
        c=contact.classification or {}
        at=_when((c.get('stage_check') or {}).get('checked_at')) or _when(c.get('classified_at'))
        if not at:at,_=_history_at(contact,('classified','stage_checked','requeued'))
        return ExitReason.OUT_OF_CRITERIA,at or contact.updated_at
    return None

def _transition(journey,touches,contact,now):
    """The exit or reopening the contact shows and the log does not have yet, as one fact (or None)."""
    state=_fold(touches);step=state.step();leaving=exit_today(contact)
    if leaving:
        reason,at=leaving;current=state.exit[0] if state.exit else ''
        if step==Step.LEFT and (current==reason or current in DEFINITIVE or reason not in DEFINITIVE):return None
        # A rest already says why the person is out and when they may come back; only a definitive reason ends it.
        if step==Step.RESTING and reason not in DEFINITIVE:return None
        n=sum(1 for t in touches if t.kind==Kind.EXIT and (t.detail or {}).get('motivo')==reason)
        return _fact(Kind.EXIT,max(at,state.first.get('chosen',at)),f'salida:{reason}:{n}',{'motivo':reason,'origen':'contacto'})
    if step==Step.LEFT and state.exit[0]==ExitReason.OUT_OF_CRITERIA and chosen(contact):
        n=sum(1 for t in touches if t.kind==Kind.REOPENED)
        return _fact(Kind.REOPENED,now,f'reabierto:{n}',{'motivo':'vuelve_al_criterio'})
    return None

# --------------------------------------------------------------------------- write

def _append(journey,rows,known,source):
    new=[BuyerTouch(journey=journey,kind=f['kind'],direction=DIRECTION[f['kind']],at=f['at'],key=f['key'],detail=f['detail'],
                    source=source,**{k:v for k,v in f['refs'].items() if v is not None})
         for f in rows if f['key'] not in known]
    if new:BuyerTouch.objects.bulk_create(new,ignore_conflicts=True)
    return len(new)

def _touches(journey):
    return list(BuyerTouch.objects.filter(journey=journey).order_by('at','created_at','id'))

def _refresh(journey,contact,touches=None):
    touches=_touches(journey) if touches is None else touches
    has_posts=ObservedPost.objects.filter(account_id=contact.account_id,author_provider_id=contact.provider_user_id).exists() \
        if contact.provider_user_id else False
    _project(journey,_fold(touches),contact,has_posts)
    journey.save()
    return journey

@transaction.atomic
def update(contact,source=Source.LIVE,now=None):
    """Bring the person's journey up to date with every fact Barrio keeps about them; idempotent. Creates the journey of
    a buyer the team chose (chosen/was_chosen) and returns None for anyone else."""
    now=now or timezone.now()
    contact=Contact.objects.filter(pk=contact.pk).first()
    if contact is None:return None
    journey=BuyerJourney.objects.select_for_update().filter(contact=contact).first()
    if journey is None:
        if not was_chosen(contact):
            # Phase 5: a bridge has no journey of its own; what it did is a signal of the buyer it leads to.
            if contact.bridge_for_id:
                from . import sin_posts
                buyer=BuyerJourney.objects.filter(pk=contact.bridge_for_id).values_list('contact_id',flat=True).first()
                if buyer and sin_posts.active():update(Contact(pk=buyer),source=source,now=now)
            return None
        origin=BuyerJourney.Origin.REBUILT if source==Source.REBUILT else BuyerJourney.Origin.LIVE
        entry=BuyerJourney.Entry.INBOUND if contact.source==Contact.Source.INCOMING else BuyerJourney.Entry.OUTBOUND
        journey,_=BuyerJourney.objects.get_or_create(contact=contact,defaults={'chosen_at':now,'entry':entry,'origin':origin})
        journey=BuyerJourney.objects.select_for_update().get(pk=journey.pk)
    known=_touches(journey)
    found=facts(contact,known)
    earliest=min((f['at'] for f in found if DIRECTION[f['kind']]==OUT),default=None)
    found.insert(0,_fact(Kind.CHOSEN,_chosen_at(contact,earliest),'elegido',{'rol':(contact.classification or {}).get('role')}))
    keys={t.key for t in known}
    added=_append(journey,found,keys,source)
    touches=_touches(journey) if added else known
    change=_transition(journey,touches,contact,now)
    if change and _append(journey,[change],{t.key for t in touches},source):touches=_touches(journey)
    journey._added=added+bool(change)
    return _refresh(journey,contact,touches)

def _locked(journey):
    return BuyerJourney.objects.select_for_update().select_related('contact').get(pk=journey.pk)

def _write(journey,kind,at,key,detail,refs=None):
    """Append one phase touch and refold; returns the touch, or None when its key was already there."""
    row=BuyerTouch(journey=journey,kind=kind,direction=DIRECTION[kind],at=at,key=key[:200],detail=detail or {},source=Source.PHASE,**(refs or {}))
    created=BuyerTouch.objects.bulk_create([row],ignore_conflicts=True)
    exists=BuyerTouch.objects.filter(journey=journey,key=row.key).first()
    _refresh(journey,journey.contact)
    return exists if created and exists and exists.pk==row.pk else None

@transaction.atomic
def record(journey,kind,at=None,key=None,detail=None,**refs):
    """Phases 2–6: append a touch (a comment, a visit, a message, a reply judged «interesado», a booked meeting…) with
    its references (proposal, execution, post, comment, conversation, opportunity, outcome). `key` names its source so
    it is recorded once; without one, the kind and the moment. Rests, retries and exits go through rest(), retry()
    and leave()."""
    if kind not in DIRECTION:raise ValueError(f'Tipo de toque desconocido: {kind}')
    if kind in TRANSITIONS:raise ValueError('Descanso, reintento, salida y reapertura se registran con rest(), retry() y leave().')
    at=at or timezone.now();journey=_locked(journey)
    return _write(journey,kind,at,key or f'{kind}:{at.isoformat()}',detail,refs)

@transaction.atomic
def rest(journey,reason,until,at=None,note=''):
    """The person rests until `until` (a temporary exit with its reason). Not from a rest, an exit or a booked meeting."""
    at=at or timezone.now();journey=_locked(journey)
    if reason not in RestReason.values:raise ValueError(f'Motivo de descanso desconocido: {reason}')
    if not until or until<=at:raise ValueError('El descanso necesita una fecha de vuelta posterior.')
    if journey.step in (Step.RESTING,Step.LEFT):raise ValueError(f'No se pasa a descanso desde «{journey.step}».')
    if journey.step==Step.MEETING:raise ValueError('Con la reunión agendada el recorrido terminó: se entrega el lead.')
    # Phase 6: a signal may end a rest without a new attempt (she wrote again); the next rest of that attempt keeps its own key.
    n=journey.touches.filter(kind=Kind.REST,detail__intento=journey.attempt).count()
    return _write(journey,Kind.REST,at,f'descanso:{journey.attempt}'+(f':{n}' if n else ''),
                  {'motivo':reason,'hasta':until.isoformat(),'intento':journey.attempt,'nota':(note or '')[:300]})

@transaction.atomic
def retry(journey,angle,at=None,signal=False,kind='',detail=None):
    """A new attempt once the rest is over, with the angle it will use. A follow and a connection carry over; the
    invitation, the messages and the reply of the earlier attempt do not. `signal`: the person gave a signal during the
    rest, which wakes them before its date (plan: «Una señal durante el descanso lo despierta de inmediato»). Phase 5:
    `kind` names the angle's type (senal_en_descanso, senal_nueva, puente, otro_tema; sin_posts.ANGLES) so the next
    attempt can change it, and `detail` keeps what it cites (the signal's source)."""
    at=at or timezone.now();journey=_locked(journey)
    if journey.step!=Step.RESTING:raise ValueError('Solo se reintenta desde el descanso.')
    if journey.rest_until and at<journey.rest_until and not signal:raise ValueError(f'El descanso termina el {journey.rest_until:%Y-%m-%d}.')
    if not (angle or '').strip():raise ValueError('Cada intento dice qué ángulo usa.')
    detail={**(detail or {}),'numero':journey.attempt+1,'angulo':angle.strip()[:300],**({'por_senal':True} if signal else {}),
            **({'tipo':kind} if kind else {})}
    return _write(journey,Kind.RETRY,at,f'reintento:{journey.attempt+1}',detail)

@transaction.atomic
def leave(journey,reason,at=None,note=''):
    """The person leaves the journey. A definitive reason (DEFINITIVE) is final; the others are closures by a rule of
    today that something the person does may reopen. A definitive exit may follow a closure or a rest, never the reverse."""
    at=at or timezone.now();journey=_locked(journey)
    if reason not in ExitReason.values:raise ValueError(f'Motivo de salida desconocido: {reason}')
    if journey.step==Step.LEFT and journey.exit_reason in DEFINITIVE:raise ValueError('Ya salió de forma definitiva.')
    if journey.step==Step.LEFT and reason not in DEFINITIVE:raise ValueError('Ya está fuera del recorrido.')
    n=journey.touches.filter(kind=Kind.EXIT,detail__motivo=reason).count()
    return _write(journey,Kind.EXIT,at,f'salida:{reason}:{n}',{'motivo':reason,'nota':(note or '')[:300]})

@transaction.atomic
def set_route(journey,route,at=None,reason=''):
    """Phases 2 and 5: whether the person publishes (comentarios) or not (sin_posts), decided from reading their posts."""
    if route not in Route.values or route==Route.UNKNOWN:raise ValueError(f'Ruta inválida: {route}')
    at=at or timezone.now();journey=_locked(journey)
    return _write(journey,Kind.ROUTE,at,f'ruta:{route}:{at.isoformat()}',{'ruta':route,'motivo':(reason or '')[:300]})

@transaction.atomic
def set_angle(journey,angle,at=None):
    """The angle of the current attempt (the first one has none until a phase sets it)."""
    if not (angle or '').strip():raise ValueError('El ángulo no puede ir vacío.')
    at=at or timezone.now();journey=_locked(journey)
    return _write(journey,Kind.ANGLE,at,f'angulo:{journey.attempt}:{at.isoformat()}',{'angulo':angle.strip()[:300],'intento':journey.attempt})

# --------------------------------------------------------------------------- passive hooks (never stop the real action)

def _failed(hook,ref,exc):
    log.exception('Registro del comprador: fallo en %s (%s)',hook,ref)
    try:
        with transaction.atomic():
            AuditEvent.objects.create(action='buyer.record_failed',target=str(hook)[:120],
                                      metadata={'ref':str(ref)[:120],'error':type(exc).__name__,'detail':str(exc)[:300]})
    except Exception:  # noqa: BLE001 - not even the audit may reach the action
        log.exception('Registro del comprador: tampoco se pudo auditar el fallo')

def _guard(hook,ref,fn):
    """Run fn in its own savepoint: a failure is rolled back alone, audited and swallowed."""
    if not enabled():return None
    try:
        with transaction.atomic():return fn()
    except Exception as exc:  # noqa: BLE001 - the record never stops what the team does
        _failed(hook,ref,exc)
        return None

def on_contact(contact,hook='contacto'):
    """After anything that changes what Barrio knows of a person: classification, web check, «Sí, encaja», invitation
    sync, discard, veto, a comment on Gustavo's post, «Hecho, le escribí», a conversation read, an opportunity."""
    if contact is None or getattr(contact,'pk',None) is None:return None
    return _guard(hook,contact.pk,lambda:update(contact))

def _people_of(proposal):
    ids=set()
    if proposal.contact_id:ids.add(proposal.contact_id)
    if proposal.comment_id:
        pk=PostComment.objects.filter(pk=proposal.comment_id).values_list('contact_id',flat=True).first()
        if pk:ids.add(pk)
    if proposal.post_id and proposal.capability in ('INT-03','INT-02'):
        author=ObservedPost.objects.filter(pk=proposal.post_id).values_list('author_provider_id',flat=True).first()
        if author:ids.update(Contact.objects.filter(account_id=proposal.account_id,provider_user_id=author).values_list('pk',flat=True))
    return ids

def on_execution(proposal,execution):
    """After operador._finish: a follow, invitation, acceptance, comment or reaction (whatever its state; the facts say
    what counts), or a pre-check that settled the person's stage."""
    for pk in _guard('ejecucion',execution.pk,lambda:_people_of(proposal)) or ():
        _guard('ejecucion',pk,lambda pk=pk:update(Contact(pk=pk)))

def on_comment_outcome(execution,people):
    """After desenlaces_captura wrote the 72 h outcome of an own comment: the people who answered it."""
    ids=_guard('desenlace',execution.pk,lambda:list(Contact.objects.filter(account_id=execution.proposal.account_id,
                                                                         provider_user_id__in=list(people or [])).values_list('pk',flat=True)))
    for pk in ids or ():
        _guard('desenlace',pk,lambda pk=pk:update(Contact(pk=pk)))

# --------------------------------------------------------------------------- rebuild from the history

def rebuild(account=None,dry_run=False,now=None):
    """Fill the journeys from what production already keeps (executions, outcomes, audit, comments, conversations,
    opportunities and the contacts' dates). Idempotent: a second run adds nothing. Each person commits on its own, so
    the live hooks wait for one person at most and an interrupted run keeps what it did; dry_run runs everything in
    one transaction, rolls it back and only reports. Returns {personas, recorridos, nuevos, toques_nuevos, fallos,
    errores, seco, segundos}."""
    started=time.monotonic();now=now or timezone.now()
    summary={'personas':0,'recorridos':0,'nuevos':0,'toques_nuevos':0,'fallos':0,'errores':[],'seco':dry_run}
    people=Contact.objects.filter(Q(classification__role='comprador')|Q(buyer_journey__isnull=False)|Q(bridge_for__isnull=False))
    if account is not None:people=people.filter(account=account)
    def run():
        before=set(BuyerJourney.objects.values_list('pk',flat=True))
        for contact in people.order_by('discovered_at').distinct():
            summary['personas']+=1
            try:
                with transaction.atomic():journey=update(contact,source=Source.REBUILT,now=now)
            except Exception as exc:  # noqa: BLE001 - one person never stops the rebuild
                summary['fallos']+=1;summary['errores'].append({'persona':str(contact.pk),'error':f'{type(exc).__name__}: {exc}'[:300]})
                continue
            if journey is None:continue
            summary['recorridos']+=1;summary['nuevos']+=int(journey.pk not in before)
            summary['toques_nuevos']+=getattr(journey,'_added',0)
        summary['segundos']=round(time.monotonic()-started,2)
    if dry_run:
        with transaction.atomic():run();transaction.set_rollback(True)
    else:
        run()
        AuditEvent.objects.create(action='buyer.rebuilt',target=str(account.pk if account else 'todas'),
                                  metadata={k:v for k,v in summary.items() if k!='errores'})
    return summary

# --------------------------------------------------------------------------- read

def journey(contact):
    return BuyerJourney.objects.filter(contact=contact).first()

REFS=('proposal','execution','post','comment','conversation','opportunity','outcome')

def temperature(person,now=None,weigh=None):
    """The signals a person gave (direction «entrante»), newest first, each with its age in days and its source, and
    what they are worth (phase 2, calentamiento.WEIGHTS: Máxima 5, Alta 3, Media 1; a signal older than 30 days weighs
    half) plus the buying signals with a source the web stage check cited (class 08); the weight only with
    BUYER_WARMUP_ENABLED or `weigh=True`. Works for anyone: a buyer's journey keeps them all; for someone else they are
    read from Barrio's rows as they are now."""
    now=now or timezone.now()
    row=person if isinstance(person,BuyerJourney) else journey(person)
    contact=row.contact if row else person
    if row:
        found=[(t.at,t.kind,t.detail,{k:str(getattr(t,k+'_id')) for k in REFS if getattr(t,k+'_id')})
               for t in current(row.touches.all()) if t.direction==IN]
        invited=row.invited_at
    else:
        found=[(f['at'],f['kind'],f['detail'],{k:str(v.pk) for k,v in f['refs'].items() if v is not None})
               for f in facts(contact) if DIRECTION[f['kind']]==IN]
        invited=contact.invited_at
    found.sort(key=lambda s:s[0],reverse=True)
    signals=[{'tipo':kind,'nombre':signal_name(kind,contact.account),'at':at.isoformat(),'dias':round((now-at).total_seconds()/86400,1),
              'antes_de_invitar':not invited or at<invited,'detalle':detail,'ref':refs} for at,kind,detail,refs in found]
    by_kind={}
    for s in signals:by_kind[s['tipo']]=by_kind.get(s['tipo'],0)+1
    from . import calentamiento
    weight={}
    if calentamiento.enabled() if weigh is None else weigh:
        peso,_=calentamiento.weigh([SimpleNamespace(kind=kind,at=at) for at,kind,_d,_r in found],contact,now)
        weight={'peso':peso,'nivel':calentamiento.level(peso),'senales_de_compra':calentamiento.buying_signals(contact)}
    return {**weight,'persona':str(contact.pk),'recorrido':str(row.pk) if row else None,'senales':signals,'total':len(signals),'por_tipo':by_kind,
            'ultima':signals[0]['at'] if signals else None,'dias_desde_ultima':signals[0]['dias'] if signals else None,
            'antes_de_invitar':sum(1 for s in signals if s['antes_de_invitar'])}

def due(now=None,steps=None):
    """Journeys with something due (next_at reached), soonest first; never a person who left."""
    rows=BuyerJourney.objects.select_related('contact').filter(next_at__lte=now or timezone.now()).exclude(step=Step.LEFT)
    if steps:rows=rows.filter(step__in=list(steps))
    return rows.order_by('next_at')

def drafts(journeys=None):
    """Messages drafted for buyers: pending (a card waiting in Tu turno), sent («Hecho, le escribí») and not sent («No
    escribirle»), from both sources: the suggested first message after a conversation on his post (RSP-07) and the
    first message of the journey (phase 3, BuyerDraft). `recorrido` breaks the phase 3 drafts down (prepared, stopped and
    by whom) and `notas` the invitation notes. Phase 4: `por_numero` breaks the journey's messages down by number (1 the
    first, 2–4 the follow-ups of the sequence), with the cancelled ones (she replied)."""
    from .respuestas import _dm_rows
    rows=list(journeys) if journeys is not None else list(BuyerJourney.objects.all())
    people={j.contact_id for j in rows};ids=[j.pk for j in rows]
    State=BuyerDraft.State
    own=BuyerDraft.objects.filter(contact_id__in=people)
    messages=own.filter(kind=BuyerDraft.Kind.MESSAGE);notes=own.filter(kind=BuyerDraft.Kind.NOTE)
    from . import mensajes_comprador, secuencia_comprador
    first=messages.filter(number=1)
    ready=first.filter(state=State.READY).count();follow_ups=messages.filter(number__gt=1,state=State.READY).count()
    # A journey draft is pending only while its card can show (its switch on); RSP-07's as before.
    from . import alcance
    pending=(sum(1 for row in _dm_rows(alcance.TODOS) if row.contact_id in people)+(ready if mensajes_comprador.enabled() else 0)
             +(follow_ups if secuencia_comprador.enabled() else 0))
    sent=BuyerTouch.objects.filter(journey_id__in=ids,kind=Kind.MESSAGE).count()
    declined=BuyerTouch.objects.filter(journey_id__in=ids,kind=Kind.NO_MESSAGE).count()
    def stopped(q):
        return {by:q.filter(stopped_by=by).count() for by in BuyerDraft.StoppedBy.values}
    return {'pendientes':pending,'enviados':sent,'no_enviados':declined,'enviados_pct':_pct(sent,sent+pending),
            'fuentes':['mensaje_sugerido','recorrido'],
            'recorrido':{'preparados':first.filter(stopped_by='',decided_at__isnull=False).count(),
                         'pendientes':ready,'enviados':first.filter(state=State.SENT).count(),
                         'no_enviados':first.filter(state=State.NOT_SENT).count(),'parados':stopped(first)},
            'por_numero':{str(n):{'preparados':q.filter(stopped_by='',decided_at__isnull=False).count(),
                                  'pendientes':q.filter(state=State.READY).count(),'enviados':q.filter(state=State.SENT).count(),
                                  'no_enviados':q.filter(state=State.NOT_SENT).count(),'cancelados':q.filter(state=State.CANCELLED).count(),
                                  'parados':sum(stopped(q).values())}
                          for n,q in ((n,messages.filter(number=n)) for n in range(1,5))},
            'notas':{'preparadas':notes.filter(stopped_by='',decided_at__isnull=False).count(),
                     'con_invitacion':notes.filter(state__in=[State.USED,State.SENT,State.NOT_SENT]).count(),
                     'enviadas':notes.filter(state=State.SENT).count(),'parados':stopped(notes)},
            # Phase 6: the replies to what she wrote (BuyerDraft «respuesta»); pending only while their cards can show.
            'respuestas':_replies_drafts(own)}

def _replies_drafts(own):
    from . import respuesta_comprador
    State=BuyerDraft.State;rows=own.filter(kind=BuyerDraft.Kind.REPLY)
    shown=respuesta_comprador.enabled()
    return {'preparados':rows.filter(stopped_by='',decided_at__isnull=False).exclude(text='').count(),
            'pendientes':rows.filter(state=State.READY).exclude(text='').count() if shown else 0,
            'sin_borrador':rows.filter(state=State.READY,text='').count() if shown else 0,
            'enviados':rows.filter(state=State.SENT).count(),'no_enviados':rows.filter(state=State.NOT_SENT).count(),
            'parados':{by:rows.filter(stopped_by=by).exclude(state=State.READY).count() for by in BuyerDraft.StoppedBy.values}}

# --------------------------------------------------------------------------- the funnel (LI-12-M001-K03)

FUNNEL=(('elegidos','Elegidos',lambda j:True),
        ('calentados','Calentados (1 comentario o más)',lambda j:j.comments_before_invite>=1),
        ('calentados_2','Calentados (2 comentarios o más)',lambda j:j.comments_before_invite>=2),
        ('invitados','Invitados',lambda j:j.invited_at is not None),
        ('aceptaron','Aceptaron',lambda j:j.accepted_at is not None),
        ('recibieron_mensaje','Recibieron mensaje',lambda j:j.first_message_at is not None),
        ('respondieron','Respondieron',lambda j:j.replied_at is not None),
        ('interesados','Interesados',lambda j:j.interested_at is not None),
        ('reunion','Reunión agendada',lambda j:j.meeting_at is not None))
DEFINITIONS={
    'cohorte':'Una semana agrupa a quienes se eligieron esa semana (lunes a domingo, hora local) y cuenta hasta dónde llegaron.',
    'paso_pct':'De quienes llegaron a la etapa anterior, qué porcentaje llegó a esta.',
    'desde_elegidos_pct':'Porcentaje de los elegidos que llegó a esta etapa.',
    'calentados':'Comentarios del equipo en posts suyos antes de su primera invitación.',
    'calentados_2':'Dos comentarios o más antes de su primera invitación: el calentamiento completo de la fase 2.',
    'senal_de_compra':'La verificación web de su empresa citó una señal de compra con fuente (ronda, contratación o expansión).',
    'aceptaron':'Conectados: aceptó la invitación de Gustavo o Gustavo aceptó la suya.',
    'recibieron_mensaje':'Gustavo marcó «Hecho, le escribí» o el inbox muestra un mensaje suyo.',
    'respondieron':'Un mensaje de la persona después del primero de Gustavo.',
    'interesados':('Fase 6 (BUYER_REPLY_ENABLED): su respuesta clasificada como interés, o una reunión agendada (quien agenda '
                   'mostró interés). En cero con la fase apagada.'),
    'reunion':('Fase 6: reunión agendada por su enlace de Cal.com (el webhook firmado) o marcada a mano («Agendó»); una '
               'reunión cancelada sin otra agendada deja de contar.'),
    'respuestas':('Fase 6: sus respuestas por tipo (la clasificación de Jev, «otro» cuando no hay confianza), los borradores de '
                  'respuesta (pendientes en Tu turno, enviados y no enviados) y las horas de su primera respuesta a la reunión.'),
    'secuencia':('Fase 4: cuántos recibieron los mensajes 1 a 4 (por «Hecho, le escribí», en algún intento) y tras cuántos '
                 'mensajes respondieron los que respondieron. El curso dice que la mayoría responde al 2.º o 3.º: se mide, no se asume.'),
    'muestra_chica':SMALL_SAMPLE_TEXT,
    'con_senal':'La persona dio una señal (comentó su post, respondió un comentario, lo invitó, le escribió…) antes de su primera invitación.',
    'entrada_comprador':('BAR-24: los compradores salientes por el nivel (confirmado, probable, por confirmar) y el tramo de '
                         'puntaje (buyer_score_v1) con que el equipo fue por ellos (fijados con el primer follow o la primera '
                         'invitación); cuántos se siguieron, calentaron (un comentario antes de invitar), invitaron, aceptaron '
                         'y respondieron.'),
    'acumulado':'Todos los compradores elegidos por el equipo (entrada saliente); los que llegaron con su invitación van en comparaciones.entrada.'}

def _pct(n,d):
    return round(n/d*100,2) if d else None

def block(journeys):
    """One funnel over these journeys: each stage with how many reached it, its step from the stage before and from the
    chosen, and the course rule on the sample."""
    journeys=list(journeys);stages=[];previous=None
    for name,label,reached in FUNNEL:
        group=[j for j in journeys if reached(j)]
        stages.append({'etapa':name,'nombre':label,'personas':len(group),'desde_elegidos_pct':_pct(len(group),len(journeys)),
                       'paso_pct':None if previous is None else _pct(sum(1 for j in previous if reached(j)),len(previous))})
        previous=group
    invited=sum(1 for j in journeys if j.invited_at)
    small=invited<SMALL_SAMPLE
    return {'personas':len(journeys),'etapas':stages,'invitaciones':invited,'muestra_chica':small,'aviso':SMALL_SAMPLE_TEXT if small else None}

ACTIVITY=(('elegidos','chosen_at'),('seguidos','warming_at'),('invitados','invited_at'),('aceptaron','accepted_at'),
          ('recibieron_mensaje','first_message_at'),('respondieron','replied_at'),('interesados','interested_at'),('reunion','meeting_at'))
ACTIVITY_TOUCHES={'comentarios':Kind.COMMENT,'mensajes_enviados':Kind.MESSAGE,'no_escribirle':Kind.NO_MESSAGE}

def _activity(journeys,touches,start,end):
    out={name:sum(1 for j in journeys if getattr(j,field) and start<=getattr(j,field)<end) for name,field in ACTIVITY}
    for name,kind in ACTIVITY_TOUCHES.items():out[name]=sum(1 for t in touches if t.kind==kind and start<=t.at<end)
    out['senales_entrantes']=sum(1 for t in touches if t.direction==IN and start<=t.at<end)
    return out

def _buying(journey):
    from . import calentamiento
    return bool(calentamiento.buying_signals(journey.contact))

def _sequence(journeys):
    from . import secuencia_comprador
    return secuencia_comprador.funnel(journeys)

def _entry(journeys):
    from . import nivel_comprador
    return nivel_comprador.entry_funnel(journeys)

def _replies(journeys):
    from . import respuesta_comprador
    return respuesta_comprador.funnel(journeys)

def funnel(weeks=8,now=None,account=None,accounts=None):
    """The buyer's funnel (GET /api/v1/resultados/embudo-comprador): cumulative and by week (cohorts by the week they
    were chosen, plus that week's activity), the comparisons that matter and the drafts. Stages that do not exist yet
    (messages 2–4, interested, meeting) come at zero with their final shape. Read-only. `accounts`: only the buyers of
    those accounts (a member's, alcance.accounts; organizaciones phase 5)."""
    from . import operador
    try:weeks=int(weeks)
    except (TypeError,ValueError):raise ValueError('semanas debe ser un número entre 1 y 26.') from None
    if not 1<=weeks<=26:raise ValueError('semanas debe ser un número entre 1 y 26.')
    now=now or timezone.now()
    rows=BuyerJourney.objects.select_related('contact')
    if account is not None:rows=rows.filter(contact__account=account)
    if accounts is not None:rows=rows.filter(contact__account__in=accounts)
    rows=list(rows)
    outbound=[j for j in rows if j.entry==BuyerJourney.Entry.OUTBOUND]
    inbound=[j for j in rows if j.entry==BuyerJourney.Entry.INBOUND]
    _,week=operador.period_starts(now)
    starts=[week-timedelta(days=7*i) for i in range(weeks)]
    logs={}  # each journey's log whole, so a stand-in is dropped even when what replaced it falls outside the weeks
    for t in (BuyerTouch.objects.filter(journey__in=outbound).filter(Q(kind__in=[*ACTIVITY_TOUCHES.values(),*CONNECTION])|Q(direction=IN))
              .only('journey_id','kind','direction','at','key').order_by('at','created_at')):
        logs.setdefault(t.journey_id,[]).append(t)
    touches=[t for entries in logs.values() for t in current(entries) if starts[-1]<=t.at<now]
    weekly=[]
    for start in starts:
        end=start+timedelta(days=7)
        weekly.append({'semana':start.date().isoformat(),'hasta':(end-timedelta(days=1)).date().isoformat(),
                       'cohorte':block(j for j in outbound if start<=j.chosen_at<end),'actividad':_activity(outbound,touches,start,end)})
    steps={s:0 for s in Step.values}
    for j in outbound:steps[j.step]+=1
    count=lambda field,values:{v:sum(1 for j in outbound if getattr(j,field)==v) for v in values}
    from . import sin_posts
    route=sin_posts.funnel(outbound) if sin_posts.active() else None  # phase 5: only with its switch on
    # BAR-25 (NETWORK_PROJECTAPP_BUYER_ENABLED): the funnel by line and by segment of the ProjectApp buyers (the ones they
    # entered with), each with the course rule on the sample (block: under 30 invitations nothing is judged), and the
    # three-month test's progress. Off, none of it.
    from . import projectapp
    test={}
    if projectapp.enabled():
        test={'por_linea':{line:block(j for j in outbound if (j.line or 'startup')==line) for line in projectapp.LINES},
              'por_segmento':{s:block(j for j in outbound if j.line=='projectapp' and j.segment==s) for s in projectapp.SEGMENTS},
              'prueba_projectapp':projectapp.test_progress(account,now,accounts=accounts)}
    return {**({'ruta_sin_posts':route} if route else {}),**test,
            'generado':now.isoformat(),'zona_horaria':str(operador.local_tz()),'definiciones':DEFINITIONS,
            'acumulado':block(outbound),'semanas':weekly,
            'comparaciones':{
                'ruta':{route:block(j for j in outbound if j.route==route) for route in Route.values},
                'calentamiento':{'calentados':block(j for j in outbound if j.comments_before_invite>=1),
                                 'no_calentados':block(j for j in outbound if j.comments_before_invite==0)},
                'nota':{'con_nota':block(j for j in outbound if j.invite_note is True),'sin_nota':block(j for j in outbound if j.invite_note is False)},
                'senal':{'con_senal':block(j for j in outbound if j.signal_before_invite),'sin_senal':block(j for j in outbound if not j.signal_before_invite)},
                'senal_de_compra':{'con_senal_de_compra':block(j for j in outbound if _buying(j)),
                                   'sin_senal_de_compra':block(j for j in outbound if not _buying(j))},
                'entrada':{'saliente':block(outbound),'entrante':block(inbound)}},
            'entrada_comprador':_entry(outbound),
            'borradores':drafts(outbound),'secuencia':_sequence(outbound),'respuestas':_replies(outbound),'estado_actual':steps,
            'descanso':count('rest_reason',RestReason.values),'salidas':count('exit_reason',ExitReason.values)}
