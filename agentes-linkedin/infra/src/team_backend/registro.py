"""The organization's shared register of people (organizaciones, phase 6; docs/plan-organizaciones.md «Fase 6: lo
construido»).

Gustavo, 17/11/2026: «un modelo basado en organizaciones donde se comparta la base de datos, porque tenemos un mismo
objetivo», and «cada una con su cuenta, y ya él maneje de su lado sus cosas». The proposal he accepted: whoever touches
a person first keeps her, and the two never comment on the same post. The course warns against two partners of the same
firm contacting the same company (LI-08-V006-K02) and recommends 2–3 people per company, never two of the same role.

What lives here, in one place:

1. The card (models.Person): one per LinkedIn person (provider_user_id: the directo connector's profile id, the same for
   every member's account since 14/11/2026, ConnectorAccount.ids_since) in an organization. It keeps what the
   organization shares: name, headline, company, the classification's role/level/score (the company's criteria), the
   general stage, an exclusion for everyone, and which member attends her since when. Every save of a Contact updates
   it (sync, a post_save receiver); the Contact keeps what is private to its member.
2. «Quien la toca primero se la queda»: claim(proposal, member) is called by operador.execute inside the member's lock,
   before anything is written, and takes the card's row FOR UPDATE: two members at once, one wins and the other sees her
   owner and writes nothing (her proposal is discarded). Classifying is not touching. issue() is the check every
   other place asks (operador.create_proposal, final_write_gate, red.execution_issues, the planners, the drafts).
3. A referent's post admits ONE member's comment: claim_post at proposal creation (PostClaim, unique per organization
   and post id).
4. Per company (company_issue): among the members, at most PEOPLE_PER_COMPANY_MAX (3) people of one company and never
   two of the same cargo; once a member attends someone of a company the other opens nobody new there without a reason
   (her affinity). A referral or a bridge keep their own rules (sin_posts, respuesta_comprador).
5. Release, pass and reassign (release, pass_to, reassign, release_stale): explicit, audited, with a reason; nothing
   private moves: the new owner starts with the basic card (card_for).
6. Colleagues (colleague_ids): the members' own LinkedIn profiles are never prospects; an evident employee of the
   organization (her headline names it) is never a buyer.
7. The share of untouched candidates (taker): affinity first (who commented on a member's post, invited her, wrote to
   her or was referred to her), then PEOPLE_ROLE_PREFERENCE (off by default; e.g. lider_tecnologia=CTO,dueno=Fundador),
   then a stable hash of the person over the members who operate. Deterministic and fair; the admin may assign an
   untouched person by hand (reassign).

One active member (or none): every rule here answers what the code answered before phase 6 (the owner is always her, the
share always gives her the person, the company rule and the share apply only among two or more members, an exclusion
never stops the member whose own history caused it). Without members nothing is recorded at all."""
import hashlib
import logging
import os
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from . import miembros
from .exceptions import Conflict

log = logging.getLogger(__name__)

# The classification keys the organization shares (its criteria); the rest of a contact's classification (its evidence,
# the invitation note, «confirmed by», the lead's doubts) is its member's.
SHARED_KEYS = ('fit', 'role', 'modality', 'affinity', 'confidence', 'region', 'reason', 'model', 'classified_at', 'rule',
               'buyer', 'stage_check', 'course_citations', 'minimum_confidence')
PRIVATE_CLASSIFICATION = ('evidence', 'invitation_note', 'note_reason', 'confirmed_by_gustavo')
TOUCHES = ('RED-01', 'RED-02', 'RED-04', 'INT-03', 'INT-04')  # seguir, invitar, aceptar, comentar su post, responderle
OPENING = ('RED-01', 'RED-02')  # the first approach to someone new (the company rule)
STAGE_OF = {'candidate': 'candidata', 'fit': 'candidata', 'incoming': 'candidata', 'followed': 'seguida',
            'invited': 'invitada', 'connected': 'conectada', 'discarded': 'descartada', 'closed': 'descartada'}
AFFINITY_SOURCES = ('own_post', 'incoming', 'referido')


class Atendida(Conflict):
    """Another member attends this person (or she is excluded for everyone, or a colleague): nothing is proposed or
    written. A Conflict: a view answers 409 with the reason; the planners skip the person (red._propose)."""


def setting(name, default):
    return os.environ.get(name, default)


def company_max():
    return max(1, int(setting('PEOPLE_PER_COMPANY_MAX', '3')))


def release_after():
    """PEOPLE_RELEASE_AFTER_DAYS: a person her owner left resting or out (without an exclusion for everyone) for this long
    is free again; 0 never frees anyone."""
    return max(0, int(setting('PEOPLE_RELEASE_AFTER_DAYS', '180')))


def role_preference():
    """PEOPLE_ROLE_PREFERENCE: {papel or role: member role or username}, e.g. «lider_tecnologia=CTO,dueno=Fundador» or
    «lider_tecnologia=<the CTO's username>»: an untouched buyer with that papel (or role) goes to the member whose role
    (or username) matches. Empty (the default): only affinity and the hash."""
    out = {}
    for item in filter(None, (x.strip() for x in setting('PEOPLE_ROLE_PREFERENCE', '').split(','))):
        key, sep, role = item.partition('=')
        if sep and key.strip() and role.strip():
            out[key.strip()] = role.strip().lower()
    return out


# --------------------------------------------------------------------------- whose organization

def _models():
    from .models import ConnectorAccount, Contact, Member, Person, PostClaim
    return ConnectorAccount, Contact, Member, Person, PostClaim


def organization_id(account):
    """The organization an account works for (its member's, or the only active member's for an account without one);
    None without members or for an account of nobody."""
    if account is None:
        return None
    member = miembros.member_of_account(account)
    return member.organization_id if member is not None else None


def active(organization_id):
    """The organization's active members, oldest first."""
    _, _, Member, _, _ = _models()
    return list(Member.objects.filter(organization_id=organization_id, active=True).order_by('created_at', 'pk'))


def shared(organization_id):
    """Whether two or more members work this organization: the share and the company rule apply only then."""
    _, _, Member, _, _ = _models()
    return organization_id is not None and Member.objects.filter(organization_id=organization_id, active=True).count() > 1


def accounts(organization_id):
    """Every account of the organization's members (with the accounts without a member while one member is active)."""
    ConnectorAccount, _, _, _, _ = _models()
    if organization_id is None:
        return ConnectorAccount.objects.all()
    rows = Q(member__organization_id=organization_id)
    members = active(organization_id)
    if len(members) == 1:
        rows |= Q(member__isnull=True)
    return ConnectorAccount.objects.filter(rows)


def readers(organization_id):
    """The reader accounts (fake, directo) of the organization's active members, oldest first: who reads LinkedIn."""
    return list(accounts(organization_id).filter(provider__in=miembros.READERS, member__active=True)
                .order_by('created_at', 'pk')) or list(accounts(organization_id).filter(provider__in=miembros.READERS)
                                                      .order_by('created_at', 'pk'))


def reader_of(member):
    """Her reader account (the oldest), or None."""
    return miembros.accounts(member, miembros.READERS).order_by('created_at', 'pk').first()


# --------------------------------------------------------------------------- colleagues

def colleague_ids(organization_id):
    """The LinkedIn ids of the organization's members (their accounts' own profiles, learned from /me): never a prospect."""
    ids = set()
    for values in accounts(organization_id).values_list('linkedin_ids', flat=True):
        ids.update(str(v) for v in (values or []) if v)
    return ids


def employee(organization_id, headline):
    """An evident employee of the organization: her headline names its company («CTO at ProjectApp»)."""
    if organization_id is None or not headline:
        return False
    from .models import Organization
    from . import sin_posts
    name = Organization.objects.filter(pk=organization_id).values_list('name', flat=True).first()
    return bool(name) and sin_posts.same_company(headline, name)


def remember_own(account, connector):
    """check_account: keep the account's own profile ids (the directo client read /me) for colleague_ids."""
    me = getattr(getattr(connector, 'client', None), 'me', None) or {}
    ids = [str(me[k]) for k in ('fsd', 'public_id') if me.get(k)]
    if ids and sorted(ids) != sorted(account.linkedin_ids or []):
        ConnectorAccount, _, _, _, _ = _models()
        ConnectorAccount.objects.filter(pk=account.pk).update(linkedin_ids=ids)
        account.linkedin_ids = ids


# --------------------------------------------------------------------------- the card

def _uid(value):
    value = str(value or '').strip()
    return '' if value in ('', 'me') else value


def _row(organization_id, uid, lock=False, **defaults):
    """The card of `uid` (created when missing, never twice: a unique row per organization); FOR UPDATE with `lock`."""
    _, _, _, Person, _ = _models()
    rows = Person.objects.filter(organization_id=organization_id, provider_user_id=uid)
    found = (rows.select_for_update(of=('self',)) if lock else rows).first()
    if found is not None:
        return found
    Person.objects.bulk_create([Person(organization_id=organization_id, provider_user_id=uid, **defaults)],
                               ignore_conflicts=True)
    return (rows.select_for_update(of=('self',)) if lock else rows).get()


def card_of(contact):
    """The card of a contact (None without an organization)."""
    _, _, _, Person, _ = _models()
    if contact.person_id:
        return Person.objects.select_related('owner').filter(pk=contact.person_id).first()
    org = organization_id(contact.account)
    if org is None or not _uid(contact.provider_user_id):
        return None
    return Person.objects.select_related('owner').filter(organization_id=org, provider_user_id=contact.provider_user_id).first()


def _general_stage(contact):
    from .models import BuyerJourney
    journey = BuyerJourney.objects.filter(contact_id=contact.pk).values_list('step', 'exit_reason').first()
    if journey and journey[0] == BuyerJourney.Step.RESTING:
        return 'descanso', journey
    return STAGE_OF.get(contact.stage, 'candidata'), journey


@receiver(post_save, sender='team_backend.Contact')
def _on_contact_saved(sender, instance, update_fields=None, raw=False, **kwargs):
    if raw or (update_fields is not None and not set(update_fields) - {'notes', 'history', 'updated_at', 'person'}):
        return
    try:
        with transaction.atomic():  # a savepoint: the register never spoils the contact's own save
            sync(instance)
    except Exception:  # the card is a mirror: a failure here is logged, the work goes on
        log.exception('person_sync_failed contact=%s', instance.pk)


def sync(contact):
    """The contact's shared part onto the organization's card (name, headline, company, the classification's shared keys
    while this contact is its source, the stage of her owner's contact, an exclusion her journey asks for)."""
    org = organization_id(contact.account)
    uid = _uid(contact.provider_user_id)
    if org is None or not uid:
        return None
    from . import sin_posts
    from .models import BuyerJourney
    card = _row(org, uid)
    member = miembros.member_of_account(contact.account)
    fields = {}
    for name in ('public_identifier', 'display_name', 'headline'):
        value = getattr(contact, name) or ''
        if value and value != getattr(card, name):
            fields[name] = value
    company = sin_posts.company_of(contact.headline)[:120]
    if company and company != card.company:
        fields['company'] = company
    stage, journey = _general_stage(contact)
    if card.owner_id is None or (member is not None and card.owner_id == member.pk):
        if stage != card.stage:
            fields['stage'] = stage
    classification = contact.classification or {}
    source = (card.classification or {}).get('contact')
    if classification.get('classified_at') and source in (None, str(contact.pk)):
        shared_part = {k: classification[k] for k in SHARED_KEYS if k in classification}
        new = {**{k: v for k, v in (card.classification or {}).items() if k in ('criterion',)}, **shared_part,
               'contact': str(contact.pk), 'member': str(member.pk) if member else ''}
        if new != card.classification:
            fields['classification'] = new
    if journey and journey[1] in (BuyerJourney.ExitReason.DO_NOT_CONTACT, BuyerJourney.ExitReason.NOT_INTERESTED) and not card.excluded:
        fields.update(excluded='no_contactar', excluded_reason=f'Salida definitiva de su recorrido ({journey[1]}).',
                      excluded_at=timezone.now(), excluded_by=member)
    if fields:
        fields['updated_at'] = timezone.now()
        type(card).objects.filter(pk=card.pk).update(**fields)
    if contact.person_id != card.pk:
        type(contact).objects.filter(pk=contact.pk).update(person=card.pk)
        contact.person_id = card.pk
    return card


def classified(contact, criterion):
    """_classify_batch: the organization's criterion this classification was made with, so another member reuses it."""
    card = sync(contact)
    if card is None:
        return
    value = dict(type(card).objects.get(pk=card.pk).classification or {})
    if value.get('contact') == str(contact.pk) and value.get('criterion') != criterion:
        type(card).objects.filter(pk=card.pk).update(classification={**value, 'criterion': criterion})


def reusable(contact, criterion):
    """A classification of the same person by another member's contact, made with the same organization criterion:
    the classification to copy (None: pay for it). Classifying is not touching: nobody owns her for it."""
    if not criterion:
        return None
    card = card_of(contact)
    if card is None or (card.classification or {}).get('criterion') != criterion:
        return None
    _, Contact, _, _, _ = _models()
    source = Contact.objects.filter(pk=(card.classification or {}).get('contact')).exclude(pk=contact.pk).first()
    if source is None or not (source.classification or {}).get('classified_at'):
        return None
    value = {k: v for k, v in source.classification.items() if k not in PRIVATE_CLASSIFICATION}
    value.update(evidence=contact.evidence, shared_from=str(card.pk))
    return value


# --------------------------------------------------------------------------- who attends her

def person_of(proposal=None, contact=None, post=None, comment=None):
    """(uid, account) of the person an action or draft is about: the contact, the author of a buyer's post or of a comment
    on her own post. A referent's post is about the post (claim_post), not about the referent."""
    if proposal is not None:
        contact, post, comment = proposal.contact, proposal.post, proposal.comment
        account = proposal.account
    else:
        account = (contact or post or comment).account if (contact or post or comment) else None
    if contact is not None:
        return _uid(contact.provider_user_id), account
    if comment is not None:
        return _uid(comment.author_provider_id), account
    if post is not None and post.referent_id is None:
        return _uid(post.author_provider_id), account
    return '', account


def issue(member, organization, uid, opening=False, contact=None, colleagues=None):
    """Why `member` may not touch person `uid` ('' when she may): another member attends her, she is excluded for
    everyone (by another member's history or for the whole organization), she is a colleague, or, opening someone new,
    the company rule. With one member (or none) only what she could not do before stays."""
    uid = _uid(uid)
    if member is None or organization is None or not uid:
        return ''
    if uid in (colleagues if colleagues is not None else colleague_ids(organization)):
        return 'Es un colega de la organización: no es un prospecto.'
    _, _, _, Person, _ = _models()
    card = Person.objects.select_related('owner').filter(organization_id=organization, provider_user_id=uid).first()
    if card is not None:
        if card.owner_id and card.owner_id != member.pk:
            return f'La atiende {card.owner.display_name}.'
        if card.excluded and (card.excluded_by_id != member.pk or card.excluded == Person.Exclusion.DISCARDED):
            return f'Excluida para toda la organización: {card.get_excluded_display().lower()}.'
    if opening and (card is None or card.owner_id is None):
        return company_issue(member, organization, card, contact)
    return ''


def issue_for(proposal, member=None):
    """issue() for an action, with its owner member."""
    uid, account = person_of(proposal)
    member = member or miembros.member_of_account(account)
    return issue(member, organization_id(account), uid, opening=proposal.capability in OPENING, contact=proposal.contact)


def execution_issue(proposal):
    """final_write_gate and red.execution_issues, right before writing: the person (or the referent's post) is still hers
    to touch. execute() already made her the owner (claim), so only a colleague or an exclusion that came meanwhile
    stops it here."""
    if proposal.capability not in TOUCHES:
        return ''
    member = miembros.member_of_account(proposal.account)
    if proposal.capability == 'INT-03' and proposal.post_id and proposal.post.referent_id:
        return post_issue(proposal.post, member)
    uid, account = person_of(proposal)
    return issue(member, organization_id(account), uid)


def _affinity(member, contact):
    """She has a reason of her own to open this person: the person commented on her post, invited her, wrote to her,
    was referred to her or is her bridge."""
    if contact is None:
        return False
    if contact.source in AFFINITY_SOURCES or contact.bridge_for_id:
        return member is not None and miembros.member_of_account(contact.account) == member
    return contact.conversations.exists()


def company_issue(member, organization, card=None, contact=None):
    """LI-08-V006-K02 among members (two or more): at most PEOPLE_PER_COMPANY_MAX people of one company attended in the
    organization, never two of the same cargo, and nobody new where another member already attends someone, unless she
    has a reason of her own (affinity). A referral and a bridge keep their own rules. '' when she may."""
    if not shared(organization):
        return ''
    from . import sin_posts
    headline = (contact.headline if contact is not None else '') or (card.headline if card is not None else '')
    company = sin_posts.company_of(headline)
    if not company or (contact is not None and (contact.source == 'referido' or contact.bridge_for_id)):
        return ''
    _, _, _, Person, _ = _models()
    uid = card.provider_user_id if card is not None else (contact.provider_user_id if contact is not None else '')
    attended = [p for p in Person.objects.filter(organization_id=organization, owner__isnull=False).exclude(provider_user_id=uid)
                .select_related('owner') if sin_posts.same_company(p.headline, company)]
    if not attended:
        return ''
    if any(p.owner_id != member.pk for p in attended) and not any(p.owner_id == member.pk for p in attended) \
            and not _affinity(member, contact):
        other = next(p.owner.display_name for p in attended if p.owner_id != member.pk)
        return f'{other} ya atiende a alguien de {company}: no se abre a otra persona de esa empresa sin motivo.'
    if len(attended) >= company_max():
        return f'Ya se atiende a {len(attended)} personas de {company} (máximo {company_max()} por empresa).'
    cargo = sin_posts.cargo_of(headline)
    if cargo and any(sin_posts.cargo_of(p.headline) == cargo for p in attended):
        return f'Ya se atiende a alguien de {company} con el mismo cargo ({cargo}).'
    return ''


def foreign_uids(member, organization):
    """The people another member attends, and those excluded for her: no comment on their posts, no reply, no draft."""
    if member is None or organization is None:
        return set()
    _, _, _, Person, _ = _models()
    rows = Person.objects.filter(organization_id=organization).filter(
        Q(owner__isnull=False) & ~Q(owner=member) | (~Q(excluded='') & (~Q(excluded_by=member) | Q(excluded='descarte'))))
    return set(rows.values_list('provider_user_id', flat=True)) | colleague_ids(organization)


@transaction.atomic
def claim(proposal, member, now=None):
    """The first real action of `member` on a person makes her the person's owner (operador.execute, inside her lock and
    before anything is written). The card's row is taken FOR UPDATE: two members at once, the second sees the first's
    ownership. Returns '' when the action may go on, else why not (the caller discards it and writes nothing). Another
    member's proposals and drafts for her leave their queues."""
    if proposal.capability not in TOUCHES:
        return ''
    if proposal.capability == 'INT-03' and proposal.post_id and proposal.post.referent_id:
        return claim_post(proposal.post, member, proposal)  # a claim that no longer holds passes to the one who writes
    uid, account = person_of(proposal)
    org = organization_id(account)
    if member is None or org is None or not uid:
        return ''
    now = now or timezone.now()
    card = _row(org, uid, lock=True)
    reason = issue(member, org, uid, opening=proposal.capability in OPENING, contact=proposal.contact)
    if reason:
        return reason
    if card.owner_id is None:
        type(card).objects.filter(pk=card.pk).update(owner=member, owned_since=now, touch=proposal.capability,
                                                     touch_proposal=proposal.pk, assigned_to=None, updated_at=now)
        from .jobs import audit
        audit(None, 'people.claimed', card.pk, member=str(member.pk), capability=proposal.capability, proposal=str(proposal.pk))
        _leave_queues(org, uid, member, now)
    return ''


def _leave_queues(org, uid, owner, now):
    """Another member's open proposals and pending drafts for a person her colleague now attends are discarded. A row
    another transaction holds right now (her execute has it FOR UPDATE and waits for this card) is skipped, never
    waited for (that would be a deadlock): her own claim sees the owner and discards it."""
    from .models import ActionProposal, BuyerDraft
    others = accounts(org).exclude(pk__in=miembros.accounts(owner).values('pk'))
    rows = ActionProposal.objects.filter(account__in=others, state__in=['proposed', 'approved']).filter(
        Q(contact__provider_user_id=uid) | Q(post__author_provider_id=uid, post__referent__isnull=True) |
        Q(comment__author_provider_id=uid))
    note = f'La atiende {owner.display_name}: otro miembro no la toca (registro de personas).'
    free = list(rows.select_for_update(of=('self',), skip_locked=True).values_list('pk', flat=True))
    ActionProposal.objects.filter(pk__in=free, state__in=['proposed', 'approved']).update(
        state=ActionProposal.State.DISCARDED, decided_at=now, decision_note=note)
    drafts = BuyerDraft.objects.filter(contact__account__in=others, contact__provider_user_id=uid,
                                       state__in=[BuyerDraft.State.REVIEWING, BuyerDraft.State.READY])
    free = list(drafts.select_for_update(of=('self',), skip_locked=True).values_list('pk', flat=True))
    BuyerDraft.objects.filter(pk__in=free).update(state=BuyerDraft.State.REPLACED, closed_at=now, closed_note=note)


def unclaim(proposal):
    """An execution that wrote nothing gives back the ownership it took (it was not a real touch)."""
    _, _, _, Person, _ = _models()
    Person.objects.filter(touch_proposal=proposal.pk).update(owner=None, owned_since=None, touch='', touch_proposal=None)


# A claim on a referent's post holds while its member may still comment it (organizaciones, phase 7, the risk phase 6
# left): her comment went out (or may have: executing, sent, confirmed, uncertain); or she is active and has a live
# proposal on it (proposed, approved); or she is active and has no proposal on it at all yet, for
# PEOPLE_POST_CLAIM_GRACE_MINUTES after the claim (create_proposal claims the post just before writing its row). A claim
# whose proposals all died (rejected, discarded, expired, failed, superseded) or whose member is inactive no longer
# holds: another member may comment the post, and her claim_post takes it over (audited).
WRITTEN_COMMENT = ('executing', 'sent', 'confirmed', 'uncertain')
PENDING_COMMENT = ('proposed', 'approved')


def claim_grace():
    try:
        return timedelta(minutes=max(0, int(setting('PEOPLE_POST_CLAIM_GRACE_MINUTES', '10'))))
    except ValueError:
        return timedelta(minutes=10)


def _holding(claims, now=None):
    """The claims among `claims` (PostClaim rows with their member) that still hold their post (see above). Two queries
    whatever their number."""
    claims = list(claims)
    if not claims:
        return []
    from .models import ActionProposal
    now = now or timezone.now()
    first = miembros.first_member_id()
    states = {}
    for post_id, member_id, state in ActionProposal.objects.filter(
            capability='INT-03', post__provider_post_id__in={c.provider_post_id for c in claims}) \
            .values_list('post__provider_post_id', 'account__member_id', 'state'):
        states.setdefault((post_id, member_id or first), set()).add(state)
    out = []
    for claim in claims:
        hers = states.get((claim.provider_post_id, claim.member_id), set())
        if hers & set(WRITTEN_COMMENT):
            out.append(claim)  # her comment is (or may be) on the post: never a second one
        elif not claim.member.active:
            continue
        elif hers & set(PENDING_COMMENT) or (not hers and claim.claimed_at >= now - claim_grace()):
            out.append(claim)
    return out


def post_issue(post, member):
    """Why `member` may not comment on this referent's post ('' when she may): another member holds it (_holding)."""
    if member is None or post is None or post.referent_id is None:
        return ''
    org = organization_id(post.account)
    if org is None:
        return ''
    _, _, _, _, PostClaim = _models()
    others = PostClaim.objects.filter(organization_id=org, provider_post_id=post.provider_post_id).exclude(member=member) \
        .select_related('member')
    held = _holding(others)
    return f'Este post ya lo comenta {held[0].member.display_name}.' if held else ''


def claim_post(post, member, proposal=None):
    """The first member with a proposal on a referent's post keeps it (unique per organization and post id); a claim that
    no longer holds (_holding) passes to her. Returns '' or why not."""
    if member is None or post is None or post.referent_id is None:
        return ''
    org = organization_id(post.account)
    if org is None:
        return ''
    _, _, _, _, PostClaim = _models()
    try:
        with transaction.atomic():
            claim, created = PostClaim.objects.select_for_update().select_related('member').get_or_create(
                organization_id=org, provider_post_id=post.provider_post_id,
                defaults={'member': member, 'proposal': getattr(proposal, 'pk', None)})
            if not created and claim.member_id != member.pk and not _holding([claim]):
                previous = claim.member_id
                claim.member, claim.proposal, claim.claimed_at = member, getattr(proposal, 'pk', None), timezone.now()
                claim.save(update_fields=['member', 'proposal', 'claimed_at'])
                from .jobs import audit
                audit(None, 'people.post_claim_passed', post.provider_post_id, organization=str(org),
                      before=str(previous), after=str(member.pk))
    except IntegrityError:
        pass
    return post_issue(post, member)


def claimed_by_others(account):
    """Post ids of the organization's referents' posts another member still holds (_holding)."""
    member = miembros.member_of_account(account)
    org = organization_id(account)
    if member is None or org is None:
        return []
    _, _, _, _, PostClaim = _models()
    return [c.provider_post_id for c in _holding(PostClaim.objects.filter(organization_id=org).exclude(member=member)
                                                 .select_related('member'))]


def check_proposal(account, capability, post=None, contact=None, comment=None, proposal=None, claim=True):
    """operador.create_proposal: an action on a person another member attends (or a post she comments) is never
    proposed. Raises Atendida with the reason. A live comment proposal on a referent's post claims the post (claim_post);
    `claim=False` only asks (the paid drafts ask before paying: precheck)."""
    if capability not in TOUCHES:
        return
    member = miembros.member_of_account(account)
    if capability == 'INT-03' and post is not None and post.referent_id is not None:
        reason = claim_post(post, member, proposal) if claim else post_issue(post, member)
    else:
        uid, _ = person_of(contact=contact, post=post, comment=comment)
        reason = issue(member, organization_id(account), uid, opening=capability in OPENING, contact=contact)
    if reason:
        raise Atendida(reason)


def precheck(account, capability, post=None, contact=None, comment=None):
    """Before a paid draft (propose_comment, a reply on her post, a buyer's message): why not ('' when it may go on)."""
    try:
        check_proposal(account, capability, post=post, contact=contact, comment=comment, claim=False)
    except Atendida as exc:
        return str(exc.detail)
    return ''


def peers(account):
    """The accounts whose comments count for the author's cooldown and the one comment per referent: among two or more
    members every account of the organization; alone, only this one (as before)."""
    org = organization_id(account)
    if not shared(org):
        return [account.pk]
    return list(accounts(org).values_list('pk', flat=True))


def draft_issue(contact):
    """A draft (first message, follow-up, reply) for a person another member attends is never prepared."""
    member = miembros.member_of_account(contact.account)
    return issue(member, organization_id(contact.account), contact.provider_user_id)


# --------------------------------------------------------------------------- the share of untouched candidates

def _stable(organization, uid):
    return int(hashlib.sha256(f'{organization}:{uid}'.encode()).hexdigest()[:12], 16)


def _papel(classification):
    buyer = (classification or {}).get('buyer') or {}
    return buyer.get('papel') or ''


def taker(card, members=None):
    """Which member may take an untouched person (the share; the owner when she has one). In order: the admin's
    assignment (reassign); affinity (the earliest member whose contact of her came from her own post, an invitation, a
    referral or a conversation); PEOPLE_ROLE_PREFERENCE; a stable hash of the person over the members who operate (a
    reader account). Deterministic: the same people go to the same member every time; even over many people."""
    if card.owner_id:
        return card.owner_id
    members = members if members is not None else [m for m in active(card.organization_id) if reader_of(m) is not None]
    if not members:
        return None
    ids = [m.pk for m in members]
    if card.assigned_to_id in ids:
        return card.assigned_to_id
    _, Contact, _, _, _ = _models()
    for contact in card.contacts.select_related('account').order_by('discovered_at', 'pk'):
        owner = miembros.member_of_account(contact.account)
        if owner is not None and owner.pk in ids and (contact.source in AFFINITY_SOURCES or contact.conversations.exists()):
            return owner.pk
    preference = role_preference()
    if preference:
        wanted = preference.get(_papel(card.classification)) or preference.get((card.classification or {}).get('role') or '')
        # Her username first (phase 7: lider_tecnologia=<her user>; only the admin sets it), then her role (CTO), which
        # each member edits in «Mi perfil»: a role never takes what the admin gave to a username.
        match = next((m.pk for m in members if wanted and wanted == m.user.get_username().lower()), None) or next(
            (m.pk for m in members if wanted and wanted == (m.role or '').strip().lower()), None)
        if match:
            return match
    return ids[_stable(card.organization_id, card.provider_user_id) % len(ids)]


def may_take(member, contact, members=None):
    """Whether `member`'s planner may go after this contact: she attends the person, or nobody does and the share gives
    her the person. Always True with one member (or none)."""
    org = organization_id(contact.account)
    if member is None or org is None or not shared(org):
        return True
    card = card_of(contact)
    if card is None:
        return True
    return taker(card, members) == member.pk


SHARE_REASON = 'El reparto de candidatos la da a otro miembro.'


def gate(member, account):
    """For a planner (red.plan, the stage checks, the comments and the drafts): a function (contact, capability) → '' or
    why not, with the organization's facts read once. It adds the share (taker) to issue(): an untouched person goes
    only to the member the share gives her to. With one member (or none) it answers what the planner did before."""
    org = organization_id(account)
    if member is None or org is None:
        return lambda contact, capability='': ''
    many = shared(org)
    colleagues = colleague_ids(org)
    members = [m for m in active(org) if reader_of(m) is not None] if many else None

    def check(contact, capability=''):
        uid = _uid(contact.provider_user_id)
        if not uid:
            return ''
        reason = issue(member, org, uid, opening=capability in OPENING, contact=contact, colleagues=colleagues)
        if reason or not many:
            return reason
        card = card_of(contact)
        return SHARE_REASON if card is not None and taker(card, members) != member.pk else ''
    return check


def known_uids(account):
    """red.discover: the people the organization already has (any member's contact, a card of the register) and the
    colleagues' own profiles: nobody discovers them again. Alone, only her own profile: the set of before."""
    org = organization_id(account)
    if org is None:
        return set()
    if not shared(org):
        return colleague_ids(org)  # alone: her own profile (discover already skipped her own comments)
    _, _, _, Person, _ = _models()
    return set(Person.objects.filter(organization_id=org).values_list('provider_user_id', flat=True)) | colleague_ids(org)


def card_for(card, member, now=None, source=None):
    """The basic card of a person for a member who has no contact of her yet (the share or a pass): name, headline,
    profile and the organization's classification. Nothing private (notes, history, messages, drafts) is copied."""
    _, Contact, _, Person, _ = _models()
    account = reader_of(member)
    if account is None:
        return None
    existing = Contact.objects.filter(account=account, provider_user_id=card.provider_user_id).first()
    if existing is not None:
        return existing
    origin = card.contacts.order_by('discovered_at', 'pk').first()
    classification = {}
    if origin is not None and (origin.classification or {}).get('classified_at'):
        classification = {k: v for k, v in origin.classification.items() if k not in PRIVATE_CLASSIFICATION}
        classification.update(evidence={}, shared_from=str(card.pk))
    fit = bool(classification.get('fit'))
    contact = Contact(account=account, provider_user_id=card.provider_user_id, public_identifier=card.public_identifier,
                      display_name=card.display_name, headline=card.headline,
                      profile_url=origin.profile_url if origin is not None else '',
                      location=origin.location if origin is not None else '',
                      source=source or (origin.source if origin is not None and origin.source != 'own_post' else 'manual'),
                      classification=classification, stage='fit' if fit else ('discarded' if classification else 'candidate'),
                      person_id=card.pk)
    from . import red
    red.note(contact, 'shared', 'Ficha básica del registro de la organización; sin notas ni mensajes de otro miembro.')
    contact.save()
    return contact


def share_assigned(member, account, limit=20):
    """red.plan: the untouched fitting candidates the share gives her that she has no contact of yet get their basic
    card on her account (discovered by a colleague's account; classified once, by whoever discovered them)."""
    org = organization_id(account)
    if member is None or org is None or not shared(org):
        return 0
    _, Contact, _, Person, _ = _models()
    members = [m for m in active(org) if reader_of(m) is not None]
    mine = Contact.objects.filter(account__in=miembros.accounts(member)).values('provider_user_id')
    rows = (Person.objects.filter(organization_id=org, owner__isnull=True, excluded='', stage='candidata',
                                  classification__fit=True, contacts__isnull=False).distinct().exclude(provider_user_id__in=mine)
            .exclude(provider_user_id__in=list(colleague_ids(org))).order_by('created_at', 'pk'))
    made = 0
    for card in rows[:200]:
        if made >= limit:
            break
        if taker(card, members) == member.pk and card_for(card, member) is not None:
            made += 1
    return made


# --------------------------------------------------------------------------- release, pass, reassign

def _audit(actor, action, card, **metadata):
    from .jobs import audit
    audit(actor, action, card.pk, **metadata)


def _reason(text):
    text = (text or '').strip()
    if not text:
        raise ValueError('Indica el motivo.')
    return text[:500]


@transaction.atomic
def release(user, contact, reason):
    """Her owner lets her go: the person is free (the share decides again). Audited with the reason."""
    reason = _reason(reason)
    member = miembros.member_for(user)
    card = card_of(contact)
    if card is None:
        raise ValueError('Esta persona no está en el registro de la organización.')
    card = _row(card.organization_id, card.provider_user_id, lock=True)
    if member is None or card.owner_id != member.pk:
        raise PermissionError('Solo quien la atiende la libera.')
    type(card).objects.filter(pk=card.pk).update(owner=None, owned_since=None, touch='', touch_proposal=None,
                                                 updated_at=timezone.now())
    _audit(user, 'people.released', card, member=str(member.pk), reason=reason)
    card.refresh_from_db()
    return card


@transaction.atomic
def pass_to(user, contact, target_id, reason):
    """Her owner passes her to another active member of the organization, who starts with the basic card (card_for);
    notes, messages and drafts stay with the one who had them. Audited with the reason."""
    from .models import Member
    reason = _reason(reason)
    member = miembros.member_for(user)
    card = card_of(contact)
    if card is None:
        raise ValueError('Esta persona no está en el registro de la organización.')
    card = _row(card.organization_id, card.provider_user_id, lock=True)
    if member is None or card.owner_id != member.pk:
        raise PermissionError('Solo quien la atiende la pasa a otro miembro.')
    target = Member.objects.filter(pk=target_id, organization_id=card.organization_id, active=True).exclude(pk=member.pk).first()
    if target is None:
        raise ValueError('Ese miembro no existe o no está activo en la organización.')
    if reader_of(target) is None:
        raise ValueError(f'{target.display_name} todavía no tiene una cuenta de LinkedIn que lea.')
    now = timezone.now()
    type(card).objects.filter(pk=card.pk).update(owner=target, owned_since=now, touch='traspaso', touch_proposal=None,
                                                 updated_at=now)
    card.refresh_from_db()
    new = card_for(card, target, now)
    _leave_queues(card.organization_id, card.provider_user_id, target, now)
    _audit(user, 'people.passed', card, member=str(member.pk), to=str(target.pk), reason=reason, contact=str(new.pk))
    return card, new


@transaction.atomic
def reassign(user, contact, target_id, reason):
    """The admin gives an untouched person to a member (who may take her first); never one somebody already attends."""
    from .models import Member
    reason = _reason(reason)
    card = card_of(contact)
    if card is None:
        raise ValueError('Esta persona no está en el registro de la organización.')
    if not miembros.is_admin(user):
        raise PermissionError('Solo el administrador de la organización reasigna personas.')
    card = _row(card.organization_id, card.provider_user_id, lock=True)
    if card.owner_id is not None:
        raise ValueError(f'La atiende {card.owner.display_name}: solo se reasigna a quien nadie ha tocado.')
    target = Member.objects.filter(pk=target_id, organization_id=card.organization_id, active=True).first()
    if target is None:
        raise ValueError('Ese miembro no existe o no está activo en la organización.')
    type(card).objects.filter(pk=card.pk).update(assigned_to=target, updated_at=timezone.now())
    _audit(user, 'people.reassigned', card, to=str(target.pk), reason=reason)
    card.refresh_from_db()
    return card


def release_stale(organization, now=None):
    """A person her owner left resting or out without an exclusion for everyone, for PEOPLE_RELEASE_AFTER_DAYS, is free
    again (audited). Only among two or more members: alone, nobody else could take her."""
    days = release_after()
    if not days or not shared(organization):
        return 0
    from .models import BuyerJourney, Contact
    now = now or timezone.now()
    since = now - timedelta(days=days)
    freed = 0
    _, _, _, Person, _ = _models()
    for card in Person.objects.filter(organization_id=organization, owner__isnull=False, excluded='',
                                      stage__in=['descanso', 'descartada'], updated_at__lte=since):
        own = Contact.objects.filter(provider_user_id=card.provider_user_id, account__in=miembros.accounts(card.owner))
        quiet = not own.filter(updated_at__gt=since).exists()
        journeys = BuyerJourney.objects.filter(contact__in=own)
        definitive = journeys.filter(exit_reason__in=['pidio_no_contacto', 'no_le_interesa']).exists()
        if quiet and not definitive:
            Person.objects.filter(pk=card.pk, owner=card.owner).update(owner=None, owned_since=None, touch='',
                                                                      touch_proposal=None, updated_at=now)
            _audit(None, 'people.released', card, member=str(card.owner_id), reason=f'plazo de {days} días sin actividad')
            freed += 1
    return freed


# --------------------------------------------------------------------------- exclusions

def exclusion_issue(contact):
    """red.discard(for_everyone): only the member who attends her (or anyone while nobody does) excludes her for the
    whole organization; '' when she may."""
    card = card_of(contact)
    member = miembros.member_of_account(contact.account)
    if card is not None and card.owner_id and (member is None or card.owner_id != member.pk):
        return f'La atiende {card.owner.display_name}: solo quien la atiende la descarta para toda la organización.'
    return ''


def exclude(uid, account, kind, reason, member=None):
    """She is excluded for the organization (LinkedIn refused her invitation; she asked not to be contacted; a member
    discarded her for everyone). The member whose history caused it keeps today's rules for her own contact."""
    org = organization_id(account)
    uid = _uid(uid)
    if org is None or not uid:
        return None
    member = member or miembros.member_of_account(account)
    card = _row(org, uid)
    if card.excluded:
        return card
    type(card).objects.filter(pk=card.pk).update(excluded=kind, excluded_reason=(reason or '')[:500],
                                                 excluded_at=timezone.now(), excluded_by=member)
    _audit(None, 'people.excluded', card, kind=kind, member=str(member.pk) if member else '')
    return card


# --------------------------------------------------------------------------- what the screens show

def view(contact, member=None):
    """ContactOutput's `registro` (only with two or more active members): who attends her, and to whom she may pass her."""
    org = organization_id(contact.account)
    if org is None or not shared(org):
        return None
    card = card_of(contact)
    member = member or miembros.member_of_account(contact.account)
    attended = None
    if card is not None and card.owner_id and (member is None or card.owner_id != member.pk):
        attended = {'id': str(card.owner_id), 'display_name': card.owner.display_name,
                    'since': card.owned_since.isoformat() if card.owned_since else None}
    mine = bool(card is not None and member is not None and card.owner_id == member.pk)
    others = [{'id': str(m.pk), 'display_name': m.display_name} for m in active(org)
              if member is None or m.pk != member.pk] if mine else []
    return {'attended_by': attended, 'mine': mine, 'pass_to': others,
            'excluded': card.get_excluded_display() if card is not None and card.excluded else None}


# --------------------------------------------------------------------------- the data of before (migration 0063)

def adopt(member):
    """The installation's first member keeps the people she already touched; the untouched stay free. Idempotent (the
    rule of migration 0063 for a database that gets its first member later, through bootstrap_local)."""
    from .models import Contact
    done = 0
    for contact in Contact.objects.filter(person__isnull=True).select_related('account').iterator():
        if sync(contact) is not None:
            done += 1
    _, _, _, Person, _ = _models()
    for card in Person.objects.filter(organization=member.organization, owner__isnull=True):
        if touched(card):
            Person.objects.filter(pk=card.pk).update(owner=member, owned_since=card.created_at, touch='antes')
    return done


def touched(card):
    """Whether someone already touched this person before the register: her contact went past fit or a write reached
    her (an executed follow, invitation, acceptance, comment on her post or reply to her)."""
    from .models import ActionExecution
    contacts = card.contacts.all()
    if contacts.exclude(stage__in=['candidate', 'fit', 'incoming', 'discarded']).exists() or \
            contacts.filter(Q(followed_at__isnull=False) | Q(invited_at__isnull=False) | Q(connected_at__isnull=False)).exists():
        return True
    uid = card.provider_user_id
    return ActionExecution.objects.filter(wrote=True).filter(
        Q(proposal__contact__provider_user_id=uid) | Q(proposal__post__author_provider_id=uid, proposal__post__referent__isnull=True)
        | Q(proposal__comment__author_provider_id=uid)).exists()
