"""Move a LinkedIn account between Unipile and directo on the same ConnectorAccount row (`operador cambiar-proveedor`),
so its contacts, posts, proposals and history stay attached (navegador-contrato.md «Cambiar de proveedor»).

The ids stored for the account are rewritten in the same transaction (ids_linkedin.py has the two id schemes):
posts, invitations and chats change; people and comments are the same for both and are only checked. What depends on
them is recomputed: the evidence keys, the community study's keys and withdrawals, and the hash that binds an open
proposal to its target and payload (an approval stays valid: same text on the same LinkedIn object, renamed). Message
ids cannot be translated; each conversation gets a mark instead and conversaciones.carry moves what the old ids had
onto the new ones at the next read. Audit events keep the ids of their time; the two that are read back as ids
(the search location, the replies scan) are not reused across a switch (ConnectorAccount.switched_at).

Every rewritten value is kept with the one it replaced (ProviderIdOriginal), so switching back restores the exact
original where the translation is not one to one (a post with two activities, a received invitation's secret), as
long as the value was not changed since. The provider and external id are kept on the row (`previous_provider`).

A value with an unknown shape, or one that would collide with another row once translated, is never guessed: the
switch refuses and lists it, unless told to leave such rows as they are (`keep_ids`); then open proposals that depend
on them expire instead of running with the other provider's id. It also refuses with an execution in flight, a
login from the app, a job of the account running, a community study being built, or the account not paused (a run
in progress could store ids of the provider before). It pauses and resumes nothing; the status goes back to unknown."""
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from django.db import transaction
from django.utils import timezone

from . import ids_linkedin as ids
from .comunidad import tombstone
from .connectors_directo import ACCOUNT as DIRECTO_ACCOUNT
from .evidencia import digest
from .models import (ActionExecution, ActionProposal, BrowserLogin, CommunitySource, CommunityStudy, CommunityWithdrawal,
                     ConnectorAccount, Contact, Conversation, EditorialPiece, EvidencePerson, Job, ObservedPost,
                     PersonEvidence, PostComment, PostMetric, ProviderIdOriginal, Referent)
from .operador import _audit, globally_paused, payload_hash
from .permissions import require
from .respuestas import reader_account

# The external id each provider takes (connectors.UnipileConnector, connectors_directo.ACCOUNT).
EXTERNAL={'unipile':(re.compile(r'acc_[A-Za-z0-9_\-]+'),'el id de la cuenta en Unipile (acc_…)'),
          'directo':(DIRECTO_ACCOUNT,'el nombre de la cuenta en el servicio navegador (minúsculas, cifras, - y _)')}
IN_FLIGHT=(ActionProposal.State.EXECUTING,ActionProposal.State.SENT,ActionProposal.State.UNCERTAIN)
OPEN=(ActionProposal.State.PROPOSED,ActionProposal.State.APPROVED)
LOGIN_ACTIVE=(BrowserLogin.State.STARTING,BrowserLogin.State.WAITING)
STAGE_DIRECTION={'invited':'sent','incoming':'received','discarded':'received'}
UNIQUE={('ObservedPost','provider_post_id'),('Conversation','provider_chat_id')}  # unique per account


class Refused(ValueError):
    """The switch did not happen; the message says why."""


@dataclass(eq=False)
class Item:
    """One stored id: the row, where it is (a column or `json.key`), its kind and value (without `prefix`)."""
    obj: object
    model: str
    field: str
    kind: str
    value: str
    direction: str = ''
    prefix: str = ''
    new: str = None
    restored: bool = False
    error: str = ''

    @property
    def key(self):
        return (self.model,str(self.obj.pk),self.field)

    @property
    def full(self):
        return self.prefix+self.value

    @property
    def changed(self):
        return self.new is not None and self.new!=self.full


@dataclass
class Plan:
    account: ConnectorAccount
    to: str
    external: str
    items: list = field(default_factory=list)
    blocks: list = field(default_factory=list)  # refusals that no flag lifts
    evidence_keys: dict = field(default_factory=dict)  # PersonEvidence pk -> new key
    hashes: dict = field(default_factory=dict)  # ActionProposal pk -> (payload_hash, approved_hash or None)
    expire: list = field(default_factory=list)  # open proposals that depend on an id left untranslated
    community: dict = field(default_factory=lambda:{'sources':{},'withdrawals':{},'left':0})
    conversations: int = 0

    @property
    def untranslated(self):
        return [i for i in self.items if i.error]

    def counts(self):
        """{model.field: Counter(traducidos, restaurados, idénticos, sin traducir)}"""
        out=defaultdict(Counter)
        for i in self.items:
            label=f'{i.model}.{i.field}'
            out[label]['sin traducir' if i.error else 'traducidos' if i.changed else 'idénticos']+=1
            if i.restored and i.changed:out[label]['restaurados']+=1
        return out

    def summary(self):
        return {'fields':{k:dict(v) for k,v in self.counts().items()},'untranslated':len(self.untranslated),
                'evidence_keys':len(self.evidence_keys),'proposals_rehashed':len(self.hashes),'proposals_expired':len(self.expire),
                'community_sources':len(self.community['sources']),'community_withdrawals':len(self.community['withdrawals']),
                'conversations_marked':self.conversations}


def _get(obj,path):
    name,_,key=path.partition('.')
    value=getattr(obj,name)
    return (value or {}).get(key) if key else value


def _items(account,reader):
    """Every stored id of the account, by where it is (navegador-contrato.md «Cambiar de proveedor» has the table)."""
    def each(rows,model,path,kind,direction=None,prefix=''):
        for obj in rows:
            value=str(_get(obj,path) or '')
            if prefix:
                if not value.startswith(prefix):continue
                value=value[len(prefix):]
            if value:yield Item(obj,model,path,kind,value,direction(obj) if direction else '',prefix)
    posts=ObservedPost.objects.filter(account=account)
    comments=PostComment.objects.filter(account=account)
    evidence=PersonEvidence.objects.filter(person__account=account)
    contacts=Contact.objects.filter(account=account)
    executions=ActionExecution.objects.filter(proposal__account=account)
    conversations=Conversation.objects.filter(account=account)
    yield from each(posts,'ObservedPost','provider_post_id','post')
    yield from each(posts,'ObservedPost','author_provider_id','person')
    yield from each(comments,'PostComment','provider_post_id','post')
    yield from each(comments,'PostComment','provider_comment_id','comment')
    yield from each(comments,'PostComment','thread_id','comment')
    yield from each(comments,'PostComment','author_provider_id','person')
    if reader:  # own posts are read (metrics, replies) through the first LinkedIn account
        yield from each(PostMetric.objects.all(),'PostMetric','provider_post_id','post')
        yield from each(EditorialPiece.objects.filter(metrics__has_key='unipile_post_id'),'EditorialPiece','metrics.unipile_post_id','post')
    yield from each(evidence,'PersonEvidence','post_id','post')
    yield from each(evidence.filter(source='list_comments'),'PersonEvidence','interaction_id','comment')
    yield from each(evidence.filter(source='relationship'),'PersonEvidence','source_id','invitation',lambda o:'received','received:')
    yield from each(EvidencePerson.objects.filter(account=account),'EvidencePerson','provider_user_id','person')
    yield from each(contacts,'Contact','provider_user_id','person')
    yield from each(contacts,'Contact','invitation_id','invitation',lambda o:STAGE_DIRECTION.get(o.stage,''))
    yield from each(Referent.objects.filter(account=account),'Referent','provider_user_id','person')
    yield from each(account.proposals.filter(capability=ActionProposal.Capability.ACCEPT,state__in=OPEN),
                    'ActionProposal','payload.request_id','invitation',lambda o:'received')
    yield from each(executions.filter(proposal__capability=ActionProposal.Capability.INVITE),'ActionExecution','external_id',
                    'invitation',lambda o:'sent')
    yield from each(executions.filter(proposal__capability__in=[ActionProposal.Capability.COMMENT,ActionProposal.Capability.REPLY]),
                    'ActionExecution','external_id','comment')
    yield from each(conversations,'Conversation','provider_chat_id','chat')
    yield from each(conversations,'Conversation','attendee_provider_id','person')


def _resolve(item,to,originals):
    """The value for `to`: the exact original if this very value was translated from it, else the translation."""
    side=originals.get(item.key)
    if side is not None and side.translated==item.full:
        item.new,item.restored=side.original,True
        return
    context={'direction':item.direction} if to=='unipile' else {}
    try:
        item.new=item.prefix+ids.translate(item.kind,item.value,to,**context)
    except ids.Untranslatable as exc:
        item.error=str(exc)


def _collisions(plan):
    """A translated value that another row of the account already has, or gets: both stay as they are."""
    for _ in range(3):
        groups=defaultdict(list)
        for i in plan.items:
            if (i.model,i.field) in UNIQUE:groups[(i.model,i.field,i.new if i.changed else i.full)].append(i)
        clash=[i for rows in groups.values() if len(rows)>1 for i in rows if i.changed]
        if not clash:return
        for i in clash:i.new,i.restored,i.error=None,False,'choca con otra fila una vez traducido'


def _evidence_keys(plan):
    """PersonEvidence.key is a digest of what identifies the observation, ids included (evidencia.observe)."""
    final=defaultdict(dict)
    for i in plan.items:
        if i.model=='PersonEvidence':final[i.obj.pk][i.field]=i
    taken={(p,k) for p,k in PersonEvidence.objects.filter(person__account=plan.account).values_list('person_id','key')}
    for pk,fields in final.items():
        if not any(i.changed for i in fields.values()):continue
        row=next(iter(fields.values())).obj
        def inputs(use_new):
            values={f:(i.new if use_new and i.changed else i.full) for f,i in fields.items()}
            return [row.kind,row.source,values.get('source_id',row.source_id),str(row.referent_id) if row.referent_id else '',
                    values.get('post_id',row.post_id),values.get('interaction_id',row.interaction_id)]
        new=digest(inputs(True))
        problem='su clave no sigue la receta de evidencia.observe' if digest(inputs(False))!=row.key else \
            'choca con otra observación una vez traducida' if (row.person_id,new) in taken else ''
        if problem:
            for i in fields.values():
                if i.changed:i.new,i.restored,i.error=None,False,problem
            continue
        taken.add((row.person_id,new));plan.evidence_keys[pk]=new


def _proposals(plan):
    """Open proposals: the hash that binds them is recomputed for the translated target and payload; an approval that
    was valid stays valid. One whose post, comment's post or invitation could not be translated expires (keep_ids)."""
    posts={i.obj.pk:i for i in plan.items if (i.model,i.field)==('ObservedPost','provider_post_id')}
    threads={i.obj.pk:i for i in plan.items if (i.model,i.field)==('PostComment','provider_post_id')}
    requests={i.obj.pk:i for i in plan.items if i.model=='ActionProposal'}
    for p in plan.account.proposals.filter(state__in=OPEN).select_related('post','piece','contact','comment'):
        post,thread,request=posts.get(p.post_id),threads.get(p.comment_id),requests.get(p.pk)
        if any(i is not None and i.error for i in (post,thread,request)):
            plan.expire.append(p);continue
        def target(new):
            if p.comment_id:return f'comment:{p.comment.provider_comment_id}'
            if p.post_id:return post.new if new and post and post.changed else p.post.provider_post_id
            if p.contact_id:return f'user:{p.contact.provider_user_id}'
            return f'piece:{p.piece_id}'
        payload=dict(p.payload,request_id=request.new) if request and request.changed else p.payload
        old,new=payload_hash(p.account_id,p.capability,target(False),p.payload),payload_hash(p.account_id,p.capability,target(True),payload)
        if new==old:continue
        valid=p.state==ActionProposal.State.APPROVED and p.approved_hash==p.payload_hash==old
        plan.hashes[p.pk]=(new,new if valid else None)


def _community(plan):
    """The community study keys its sources by digests of the post and comment ids (comunidad.read_public), and a
    withdrawal by a digest of the person and that key (comunidad.tombstone). Recomputed from the account's known
    (post, comment) pairs; a source that cannot be traced is left (it expires in 90 days), a withdrawal cannot."""
    moved={}
    for i in plan.items:
        if i.kind=='post' and i.changed:moved.setdefault(i.full,set()).add(i.new)
    moved={old:news.pop() for old,news in moved.items() if len(news)==1}
    pairs=set(PersonEvidence.objects.filter(person__account=plan.account,source='list_comments').exclude(interaction_id='')
              .values_list('post_id','interaction_id'))
    pairs|=set(PostComment.objects.filter(account=plan.account).values_list('provider_post_id','provider_comment_id'))
    targets={digest(['comments',old]):digest(['comments',new]) for old,new in moved.items()}
    keys={digest(['comment',post,cid]):digest(['comment',moved[post],cid]) for post,cid in pairs if post in moved}
    stones,stable={},set()
    for person in EvidencePerson.objects.filter(account=plan.account).values_list('pk',flat=True):
        stable|={tombstone(person),tombstone(person,digest(['profile',str(person)]))}
    for source in CommunitySource.objects.filter(study__account=plan.account):
        if source.kind!='public_comment':
            stable.add(tombstone(source.person_id,source.key));continue
        if source.target in targets and source.key in keys:
            plan.community['sources'][source.pk]=(targets[source.target],keys[source.key])
            stones[tombstone(source.person_id,source.key)]=tombstone(source.person_id,keys[source.key])
        elif source.target in targets.values() or source.key in keys.values():
            stable.add(tombstone(source.person_id,source.key))  # already in the provider's ids
        else:plan.community['left']+=1
    for withdrawal in CommunityWithdrawal.objects.filter(account=plan.account):
        if withdrawal.key in stones:plan.community['withdrawals'][withdrawal.pk]=stones[withdrawal.key]
        elif withdrawal.key not in stable:
            plan.items.append(Item(withdrawal,'CommunityWithdrawal','key','community','',error='no se sabe de qué fuente es'))


def _blocks(account,to,external):
    blocks=[]
    if account.provider not in EXTERNAL:
        return [f'Solo se cambia una cuenta de Unipile o directo; esta es «{account.provider}».']
    if to==account.provider:blocks.append(f'La cuenta ya es de {to}.')
    pattern,what=EXTERNAL.get(to,(None,''))
    if pattern is None:blocks.append(f'Proveedor desconocido: {to}.')
    elif not pattern.fullmatch(external or ''):blocks.append(f'Para {to} hace falta {what}.')
    other=ConnectorAccount.objects.filter(provider=to,external_account_id=external).exclude(pk=account.pk).first()
    if other:blocks.append(f'Ya hay otra cuenta de {to} con ese nombre: «{other.label}» ({other.id}). Usa otro nombre.')
    flying=account.proposals.filter(state__in=IN_FLIGHT).count()
    if flying:
        blocks.append(f'La cuenta tiene {flying} acción(es) en curso o por conciliar con {account.provider}. '
                      'Espera a que terminen (o concílialas) antes de cambiar.')
    if account.browser_logins.filter(state__in=LOGIN_ACTIVE).exists():
        blocks.append('Hay una conexión desde la app en curso para esta cuenta. Termínala o cancélala antes.')
    if Job.objects.filter(state=Job.State.RUNNING,params__account=str(account.id)).exists():
        blocks.append('Hay un trabajo de esta cuenta en marcha. Espera a que termine.')
    if CommunityStudy.objects.filter(account=account,state='building').exists():
        blocks.append('Se está armando un estudio de comunidad de esta cuenta. Espera a que termine.')
    if not (account.paused or globally_paused()):
        blocks.append('Pausa la cuenta (o la máquina) antes de cambiar, y espera a que termine la vuelta en curso: '
                      'un trabajo a medias podría guardar ids del proveedor de antes después del cambio.')
    return blocks


def plan(account,to,external):
    """What a switch of `account` to `to` would do, without writing anything."""
    plan=Plan(account,to,external,blocks=_blocks(account,to,external))
    if account.provider not in EXTERNAL or to not in EXTERNAL or to==account.provider:return plan
    originals={(o.model,o.object_id,o.field):o for o in ProviderIdOriginal.objects.filter(account=account,provider=to)}
    plan.items=list(_items(account,reader_account()==account))
    for item in plan.items:_resolve(item,to,originals)
    _collisions(plan)
    _evidence_keys(plan)
    _proposals(plan)
    _community(plan)
    plan.conversations=Conversation.objects.filter(account=account).exclude(messages=[]).count()
    return plan


def report(plan):
    """The plan in lines, for the command: per table and field, then every row that cannot be translated."""
    lines=[f'De {plan.account.provider} a {plan.to} ({plan.external or "sin id"}):']
    lines+=[f'  No se puede: {b}' for b in plan.blocks]
    for label,counts in sorted(plan.counts().items()):
        lines.append(f'  {label}: '+', '.join(f'{n} {k}' for k,n in sorted(counts.items())))
    s=plan.summary()
    lines.append(f'  Claves de evidencia recalculadas: {s["evidence_keys"]}. Propuestas abiertas con su huella recalculada: '
                 f'{s["proposals_rehashed"]}; que caducarían por un id sin traducir: {s["proposals_expired"]}.')
    lines.append(f'  Estudio de comunidad: {s["community_sources"]} fuentes y {s["community_withdrawals"]} retiradas '
                 f'recalculadas; {plan.community["left"]} fuentes sin rastrear (caducan solas).')
    lines.append(f'  Conversaciones marcadas para conservar lo leído y cerrado en su próxima lectura: {s["conversations_marked"]}.')
    for i in plan.untranslated:
        lines.append(f'  Sin traducir: {i.model} {i.obj.pk} {i.field} «{ids.shape(i.full)}»: {i.error}')
    return lines


def _write(plan,user):
    account,before=plan.account,plan.account.provider
    for i in plan.items:
        if not i.changed:continue
        name,_,key=i.field.partition('.')
        model=type(i.obj)
        if key:
            current=model.objects.filter(pk=i.obj.pk).values_list(name,flat=True).get() or {}
            model.objects.filter(pk=i.obj.pk).update(**{name:dict(current,**{key:i.new})})
        else:model.objects.filter(pk=i.obj.pk).update(**{name:i.new})
        ProviderIdOriginal.objects.update_or_create(account=account,provider=before,model=i.model,object_id=str(i.obj.pk),
                                                    field=i.field,defaults={'original':i.full,'translated':i.new})
    for pk,key in plan.evidence_keys.items():PersonEvidence.objects.filter(pk=pk).update(key=key)
    for pk,(new,approved) in plan.hashes.items():
        ActionProposal.objects.filter(pk=pk).update(payload_hash=new,**({'approved_hash':approved} if approved else {}))
    for p in plan.expire:
        ActionProposal.objects.filter(pk=p.pk,state__in=OPEN).update(
            state=ActionProposal.State.EXPIRED,decision_note=f'Caducada al cambiar de {before} a {plan.to}: un id suyo no se pudo traducir.')
    for pk,(target,key) in plan.community['sources'].items():CommunitySource.objects.filter(pk=pk).update(target=target,key=key)
    for pk,key in plan.community['withdrawals'].items():CommunityWithdrawal.objects.filter(pk=pk).update(key=key)
    Conversation.objects.filter(account=account).exclude(messages=[]).update(carry={'from':before,'at':timezone.now().isoformat()})


def _switch(user,account_id,to,external,keep_ids,back):
    require(user,'manage_jobs')
    with transaction.atomic():
        account=ConnectorAccount.objects.select_for_update().get(pk=account_id)
        if back:
            previous=account.previous_provider or {}
            if not previous.get('provider'):raise Refused('Esta cuenta no tiene un proveedor anterior guardado.')
            to,external=previous['provider'],previous.get('external_account_id','')
        found=plan(account,to,external)
        if found.blocks:raise Refused(' '.join(found.blocks))
        if found.untranslated and not keep_ids:
            raise Refused('\n'.join(report(found)+['Hay ids que no se pueden traducir. Para dejarlos como están (y que caduquen las '
                                                   'propuestas abiertas que dependen de ellos): --aceptar-ids-viejos.']))
        before=account.provider
        _write(found,user)
        account.previous_provider={'provider':before,'external_account_id':account.external_account_id,
                                   'until':timezone.now().isoformat(),'by':user.username}
        account.provider,account.external_account_id=to,external
        # The status was the old provider's; the next check (comprobar, the inbox read) asks the new one.
        account.status,account.is_locked,account.last_checked_at='unknown',False,None
        account.save(update_fields=['provider','external_account_id','previous_provider','status','is_locked','last_checked_at'])
        _audit(user,'operator.account_provider_switched',account.id,from_provider=before,to_provider=to,back=back,
               **found.summary())
    return account,found


def switch(user,account,to,external,keep_ids=False):
    """`account` now goes through `to` (unipile|directo) as `external`, its stored ids translated. (account, plan)"""
    return _switch(user,account.pk,to,external,keep_ids,back=False)


def switch_back(user,account,keep_ids=False):
    """Back to the provider and external id the account had before its last switch, originals restored."""
    return _switch(user,account.pk,None,None,keep_ids,back=True)


def preview(account,to=None,external=None,back=False):
    """The plan of a switch (or of switching back) without writing: the dry run."""
    if back:
        previous=account.previous_provider or {}
        if not previous.get('provider'):raise Refused('Esta cuenta no tiene un proveedor anterior guardado.')
        to,external=previous['provider'],previous.get('external_account_id','')
    return plan(account,to,external)


def forget_originals(user,account):
    """The kept originals of the account go: switching back then translates instead of restoring."""
    require(user,'manage_jobs')
    count,_=ProviderIdOriginal.objects.filter(account=account).delete()
    _audit(user,'operator.provider_originals_forgotten',account.id,count=count)
    return count
