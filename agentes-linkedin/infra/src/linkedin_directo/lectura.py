"""LinkedIn's answers read into the shapes Barrio's connector returns (team_backend/connectors.py: _user, _post,
_comment, _profile, _invitation, _chat, _message). Field names are the ones seen on 2026-11-13; the spike's canary
checks the same ones every day. Anything LinkedIn does not give stays absent (None, '' or False), never invented.

Voyager answers are normalized (`application/vnd.linkedin.normalized+json+2.1`): `data` holds the top list as urns
(REST `data.*elements`, GraphQL `data.data.<finder>.*elements`), every entity sits once in `included` keyed by its
`entityUrn`, and a `*field` holds the urn of another entity. A union may come wrapped in its type name
(`{"com.linkedin...MemberActor": {...}}`); `unwrap` takes it out.

Ids (docs/navegador-contrato.md): a person is the fsd_profile id (`ACo…`, Unipile's provider id); a post, the activity
number; a comment, its own number (the post goes alongside); an invitation, the number of its urn; a chat, the messaging
thread id (`2-…`); a message, the id after the comma in its urn."""
import json
import re
from datetime import datetime, timezone
from urllib.parse import unquote

from . import rutas

DISTANCE = {'SELF': 'SELF', 'DISTANCE_1': 'FIRST_DEGREE', 'DISTANCE_2': 'SECOND_DEGREE', 'DISTANCE_3': 'THIRD_DEGREE',
            'OUT_OF_NETWORK': 'OUT_OF_NETWORK'}
PROFILE = re.compile(r'urn:li:(?:fsd_profile|fs_miniProfile):([A-Za-z0-9_\-]+)')
MEMBER = re.compile(r'urn:li:member:(\d+)')
COMMENT = re.compile(r'urn:li:comment:\((?:activity|ugcPost):(\d+),(\d+)\)')
OBJECT_COMMENT = re.compile(r'urn:li:fs_objectComment:\((\d+),(?:activity|ugcPost):(\d+)\)')
INVITATION = re.compile(r'urn:li:(?:fsd_invitation|fs_relInvitation):(\d+)')
CONVERSATION = re.compile(r'urn:li:msg_conversation:\(urn:li:fsd_profile:[^,()]+,(2-[^,()]+)\)')
SLUG = re.compile(r'linkedin\.com/in/([^/?#]+)')
HIDDEN_FORMATS = ('RECALLED', 'SYSTEM')  # a deleted message, an event line


# --- normalized answers --------------------------------------------------------------------------------------------
def index(answer):
    return {e['entityUrn']: e for e in answer.get('included') or [] if isinstance(e, dict) and e.get('entityUrn')}


def typed(answer, suffix):
    return [e for e in answer.get('included') or [] if isinstance(e, dict) and str(e.get('$type', '')).endswith(suffix)]


def elements(answer):
    """The top list of an answer, as urns or inline rows."""
    data = answer.get('data') if isinstance(answer.get('data'), dict) else {}
    inner = data.get('data') if isinstance(data.get('data'), dict) else {}
    for block in [data] + [v for v in inner.values() if isinstance(v, dict)]:
        for key in ('*elements', 'elements'):
            if isinstance(block.get(key), list):
                return block[key]
    return []


def entity(by, ref):
    """The entity a urn points to, following a wrapper's `*value` (get_post's first element)."""
    found = by.get(ref, {}) if isinstance(ref, str) else ref if isinstance(ref, dict) else {}
    for _ in range(3):
        nxt = found.get('*value')
        if not isinstance(nxt, str) or nxt not in by:
            break
        found = by[nxt]
    return found


def unwrap(value):
    if isinstance(value, dict) and len(value) == 1:
        key, inner = next(iter(value.items()))
        if key.startswith('com.linkedin.') and isinstance(inner, dict):
            return inner
    return value if isinstance(value, dict) else {}


def find(value, pattern):
    """First match (group 1) of `pattern` in any string of a nested value, percent-encoded ones included."""
    if isinstance(value, dict):
        value = list(value.values())
    if isinstance(value, list):
        return next((hit for hit in (find(v, pattern) for v in value) if hit), '')
    match = pattern.search(unquote(value)) if isinstance(value, str) else None
    return match.group(1) if match else ''


def find_key(value, key):
    """First integer under `key` anywhere in a nested value."""
    if isinstance(value, dict):
        if isinstance(value.get(key), int) and not isinstance(value.get(key), bool):
            return value[key]
        value = list(value.values())
    if isinstance(value, list):
        return next((hit for hit in (find_key(v, key) for v in value) if hit is not None), None)
    return None


def text(value):
    """`{text: ...}` (a TextViewModel), `{text: {text: ...}}` (a post's commentary) or a plain string."""
    for _ in range(2):
        if isinstance(value, dict):
            value = value.get('text')
    return value if isinstance(value, str) else ''


def number(value):
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def moment(ms):
    if not isinstance(ms, (int, float)) or isinstance(ms, bool) or ms <= 0:
        return None
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


def activity_time(activity_id):
    """A post's creation time is in its id: activity id >> 22 is epoch milliseconds (there is no date field). A
    comment id carries it the same way (checked against the write's own time on 2026-11-13)."""
    return moment(int(activity_id) >> 22)


def tail(urn):
    return urn.rsplit(':', 1)[-1] if isinstance(urn, str) and urn.startswith('urn:li:') else ''


def profile_url(public_id):
    return f'{rutas.WEB}/in/{public_id}' if public_id else ''


def user(id='', public_identifier='', display_name='', headline='', kind=''):
    """The connector's _user shape."""
    return {'id': id or '', 'public_identifier': public_identifier or '', 'display_name': display_name or '',
            'profile_url': profile_url(public_identifier), 'headline': headline or '', 'type': kind or ''}


def full_name(first, last):
    return ' '.join(p for p in (text(first) or first, text(last) or last) if isinstance(p, str) and p).strip()


def mini_user(mini, members=None):
    """A MiniProfile (the old format's person card)."""
    fsd = tail(mini.get('entityUrn')) or tail(mini.get('dashEntityUrn'))
    member = MEMBER.search(mini.get('objectUrn') or '')
    if members is not None and fsd and member:
        members[fsd] = member.group(1)
    return user(fsd, mini.get('publicIdentifier'), full_name(mini.get('firstName'), mini.get('lastName')),
                mini.get('occupation'), 'individual' if fsd else '')


# --- own account, profiles -----------------------------------------------------------------------------------------
def own(me):
    """{public_id, fsd, member} of a /me answer, plain (`miniProfile`) or normalized (the mini profile in `included`)."""
    data = me.get('data') if isinstance(me.get('data'), dict) else me
    for mini in [me.get('miniProfile') or {}] + [e for e in me.get('included') or [] if isinstance(e, dict)]:
        if mini.get('publicIdentifier'):
            member = MEMBER.search(mini.get('objectUrn') or '')
            plain = data.get('plainId')
            return {'public_id': mini['publicIdentifier'],
                    'fsd': tail(mini.get('dashEntityUrn')) or tail(mini.get('entityUrn')),
                    'member': member.group(1) if member else str(plain) if number(plain) else ''}
    return {}


def person(answer, ident, members=None):
    """The person of a FullProfile-76 read: the connector's _user plus location, member id and bio, or None."""
    by = index(answer)
    rows = [r for r in (entity(by, r) for r in elements(answer)) if r] or typed(answer, 'identity.profile.Profile')
    found = next((r for r in rows if ident in (r.get('publicIdentifier'), tail(r.get('entityUrn')))),
                 rows[0] if rows else None)
    if not found:
        return None
    geo = by.get((found.get('geoLocation') or {}).get('*geo'), {}) if isinstance(found.get('geoLocation'), dict) else {}
    member = MEMBER.search(found.get('objectUrn') or '')
    fsd = tail(found.get('entityUrn'))
    if members is not None and fsd and member:
        members[fsd] = member.group(1)
    out = user(fsd, found.get('publicIdentifier'), full_name(found.get('firstName'), found.get('lastName')),
               text(found.get('headline')), 'individual')
    out.update(location=text(geo.get('defaultLocalizedName')) or text(found.get('locationName')),
               member=member.group(1) if member else '', bio=text(found.get('summary')).strip()[:800])
    return out


def relation(card, public_id):
    """What the profile top card says about a person: distance, a pending invitation, whether the account follows
    them, connections and followers. The MemberRelationship union is `self`, `*connection` (first degree: a reference
    to a Connection, seen right after accepting) or `noConnection` with `memberDistance` (DISTANCE_2, DISTANCE_3,
    OUT_OF_NETWORK) and, when one is pending, its invitation.
    The card carries other people too (the account itself, someone in a highlight), each with its own FollowingState,
    and the account's own card has no publicIdentifier on its Profile: the person is the card's first element, and
    their relationship is the one whose urn ends with their profile id."""
    included = [e for e in card.get('included') or [] if isinstance(e, dict)]
    by = index(card)
    first = next((by[ref] for ref in elements(card) if isinstance(ref, str) and ref in by), {})
    profile = first if 'Profile' in str(first.get('$type', '')) else \
        next((e for e in included if public_id and e.get('publicIdentifier') == public_id), {})
    fsd = tail(profile.get('entityUrn'))
    links = [e for e in included if str(e.get('$type', '')).endswith('MemberRelationship')]
    link = next((e for e in links if fsd and str(e.get('entityUrn', '')).endswith(fsd)), links[0] if links else {})
    union = link.get('memberRelationship') if isinstance(link.get('memberRelationship'), dict) else {}
    far = union.get('noConnection') if isinstance(union.get('noConnection'), dict) else {}
    near = union.get('*connection') or union.get('connection')
    distance = 'SELF' if union.get('self') is not None else 'DISTANCE_1' if near else far.get('memberDistance')
    pending = far.get('invitation') if isinstance(far.get('invitation'), dict) else {}
    state = next((e for e in included if profile.get('*followingState') and e.get('entityUrn') == profile['*followingState']),
                 next((e for e in included if str(e.get('$type', '')).endswith('FollowingState')), {}))
    connections = profile.get('connections') if isinstance(profile.get('connections'), dict) else {}
    return {'network_distance': DISTANCE.get(distance or '', ''),
            'pending': bool(pending.get('invitation') or pending.get('*invitation')),
            'invitation_id': find(pending, INVITATION), 'is_following': bool(state.get('following')),
            'connections': number((connections.get('paging') or {}).get('total')),
            'followers': number(state.get('followerCount'))}


def profile_views(answer):
    """The library's path: the WvmpSummaryInsightCard's `numViews`."""
    return find_key(answer, 'numViews')


# --- posts and comments --------------------------------------------------------------------------------------------
def actor_user(actor, by, members=None):
    """The author of an update (old format `actor`): name, headline and profile link, and the profile id from the
    mini profile its image or link points to."""
    url = unquote((actor.get('navigationContext') or {}).get('actionTarget') or '')
    slug = SLUG.search(url)
    fsd = find(actor, PROFILE)
    mini = by.get(f'urn:li:fs_miniProfile:{fsd}', {}) if fsd else {}
    urn = actor.get('urn') or ''
    member = MEMBER.search(urn)
    if members is not None and fsd and member:
        members[fsd] = member.group(1)
    kind = 'individual' if member or fsd else 'company' if 'company' in urn else ''
    return user(fsd, mini.get('publicIdentifier') or (slug.group(1) if slug else ''),
                text(actor.get('name')) or full_name(mini.get('firstName'), mini.get('lastName')),
                text(actor.get('description')) or mini.get('occupation'), kind)


def post(update, by, counts, author_fsd=None, members=None):
    """One UpdateV2 as the connector's _post, or None when it is not an activity. In a person's activity list, an
    update whose author is someone else is a repost."""
    activity = re.fullmatch(r'urn:li:activity:(\d+)', str((update.get('updateMetadata') or {}).get('urn') or ''))
    if not activity:
        return None
    aid = activity.group(1)
    count = counts.get(f'urn:li:activity:{aid}') or {}
    author = actor_user(update.get('actor') or {}, by, members)
    reshared = bool(update.get('*resharedUpdate') or update.get('resharedUpdate'))
    return {'id': aid, 'share_url': f'{rutas.WEB}{rutas.post_page(aid)}', 'text': text(update.get('commentary')),
            'created_at': activity_time(aid), 'author': author,
            'comments_counter': number(count.get('numComments')), 'reactions_counter': number(count.get('numLikes')),
            'user_reacted': bool(count.get('liked')),
            'is_repost': reshared or bool(author_fsd and author['id'] and author['id'] != author_fsd),
            'reposts_counter': number(count.get('numShares')),
            # A number only in a list of the account's own posts; get_post leaves it null.
            'impressions': number(count.get('numImpressions'))}


def _counts(answer):
    return {e.get('urn'): e for e in typed(answer, 'SocialActivityCounts') if e.get('urn')}


def posts(answer, author_fsd=None, members=None):
    by, counts = index(answer), _counts(answer)
    found = (post(entity(by, ref), by, counts, author_fsd, members) for ref in elements(answer))
    return [p for p in found if p]


def highlighted(answer, activity_id, members=None):
    """get_post's finder answers the asked update first and then a page of the main feed: only the first counts."""
    rows = elements(answer)
    if not rows or str(activity_id) not in json.dumps(rows[0]):
        return None
    by = index(answer)
    found = post(entity(by, rows[0]), by, _counts(answer), None, members)
    return found if found and found['id'] == str(activity_id) else None


def commenter_user(comment, by, members=None):
    """Who wrote a comment: the MemberActor (`commenter`) and its mini profile. Like Unipile's comment author, no
    headline: the callers read the profile when they need one (and get distance and signals with it)."""
    actor = unwrap(comment.get('commenter'))
    dash = comment.get('commenterForDashConversion') if isinstance(comment.get('commenterForDashConversion'), dict) else {}
    fsd = find(actor.get('*miniProfile') or actor.get('miniProfile') or actor, PROFILE)
    mini = by.get(f'urn:li:fs_miniProfile:{fsd}', {}) if fsd else {}
    member = MEMBER.search(actor.get('urn') or '')
    if members is not None and fsd and member:
        members[fsd] = member.group(1)
    company = 'company' in str(actor.get('urn') or '') or 'Company' in str(actor.get('$type') or '')
    slug = SLUG.search(unquote(str(dash.get('navigationUrl') or dash.get('actorNavigationUrl') or '')))
    return user(fsd, mini.get('publicIdentifier') or (slug.group(1) if slug else ''),
                full_name(mini.get('firstName'), mini.get('lastName')) or text(dash.get('title')), '',
                'company' if company else 'individual' if fsd or member else '')


def comments(answer, own_fsd='', thread=None, members=None):
    """The comments of a post (top level) or of one comment's thread (`thread` = that comment's id), newest answer
    order kept. Only the answer's own list counts: a first reply embedded in `included` is not a top-level one."""
    by, counts, out = index(answer), _counts(answer), []
    for ref in elements(answer):
        row = entity(by, ref)
        ids, legacy = COMMENT.search(str(row.get('urn') or '')), OBJECT_COMMENT.search(str(row.get('entityUrn') or ''))
        if ids:
            post_id, comment_id = ids.groups()
        elif legacy:
            comment_id, post_id = legacy.groups()
        else:
            continue
        author = commenter_user(row, by, members)
        parent = COMMENT.search(str(row.get('parentCommentUrn') or ''))
        count = counts.get(row.get('urn')) or counts.get(f'urn:li:comment:(activity:{post_id},{comment_id})') or {}
        out.append({'id': comment_id, 'text': text(row.get('commentV2')) or text(row.get('comment')),
                    'created_at': moment(row.get('createdTime')),
                    'is_sender': bool(own_fsd and author['id'] == own_fsd),
                    'thread_id': parent.group(2) if parent else thread, 'author': author,
                    'reply_counter': number(count.get('numComments'))})
    return out


# --- network -------------------------------------------------------------------------------------------------------
def invitations(answer, kind, members=None):
    """(rows in the connector's _invitation shape, {id: shared secret}). Received ones: only connection invitations
    from a person (a ProfileInvitee and no generic view); newsletter and page invitations come in the same list and
    are left out. `paging.total` stays 0 even with rows, so it is never read."""
    by, rows, secrets = index(answer), [], {}
    for ref in elements(answer):
        view = entity(by, ref)
        if view.get('*genericInvitationView') or view.get('genericInvitationView'):
            continue
        invitation = entity(by, view.get('*invitation') or view.get('invitation')) or view
        invitee = unwrap(invitation.get('invitee'))
        person_invitee = str(invitee.get('$type', '')).endswith('ProfileInvitee') or bool(invitee.get('*miniProfile'))
        found = INVITATION.search(str(invitation.get('entityUrn') or ''))
        if not found or (kind == 'received' and not person_invitee):
            continue
        other = by.get(invitation.get('*fromMember' if kind == 'received' else '*toMember')) \
            or (by.get(invitee.get('*miniProfile')) if kind == 'sent' else None) or {}
        who = mini_user(other, members)
        if not who['id']:  # nobody to act on or match with a person
            continue
        note = invitation.get('message')
        rows.append({'id': found.group(1), 'type': kind, 'created_at': moment(invitation.get('sentTime')),
                     'message': note if isinstance(note, str) else '', 'user': who})
        if isinstance(invitation.get('sharedSecret'), str) and invitation['sharedSecret']:
            secrets[found.group(1)] = invitation['sharedSecret']
    return rows, secrets


def invitation_id(answer):
    """The id of the invitation an invite answer created, when it names one."""
    return find(answer, INVITATION)


def search_results(html):
    """What a people search page says of each result, in order: {id, member, public_identifier}. The page does not
    draw its cards (the browser asks for them later, in the batchClassicSnippetRequest it carries): that request lists
    the profile ids and maps each to its member urn, and the first few results (3 of 10 on 2026-11-13) also have a
    profile prefetch with their public id. Names, headlines, places and distance are not on the page."""
    page = rutas.unescape(html)
    snippet = next(iter(rutas.templates(page, rutas.SNIPPETS)), {})
    payload = (snippet.get('requestedArguments') or {}).get('payload') or {}
    ids = [str(p).rsplit(':', 1)[-1] for p in payload.get('memberProfileIds') or []]
    urns = payload.get('memberEntityUrns') or {}
    if isinstance(urns, list):  # an older form: one urn per profile id, same order
        urns = dict(zip(ids, urns))
    public, decoder = {}, json.JSONDecoder()
    for m in re.finditer(r'\{"vanityName":"', page):
        try:
            found = decoder.raw_decode(page, m.start())[0]
        except ValueError:
            continue
        if isinstance(found.get('vieweeProfileId'), str) and isinstance(found.get('vanityName'), str):
            public.setdefault(found['vieweeProfileId'], found['vanityName'])
    out = []
    for p in ids:
        member = str(urns.get(p) or '').rsplit(':', 1)[-1] if isinstance(urns, dict) else ''
        if p:
            out.append({'id': p, 'member': member if member.isdigit() else '', 'public_identifier': public.get(p, '')})
    return out


def places(stream):
    """Location ids and labels of the typeahead's component stream; labels come in the ids' order."""
    stream = rutas.unescape(stream)
    ids = list(dict.fromkeys(re.findall(r'"newString":"(\d+)","key":\{"key":\{"value":\{"\$case":"id","id":'
                                        r'"SEARCH_FILTER_geoUrn"', stream)))
    labels = list(dict.fromkeys(re.findall(r'"children":\["([^"$][^"]{1,120})"\]', stream)))
    return [{'id': g, 'name': labels[i] if i < len(labels) else ''} for i, g in enumerate(ids)]


def written_comment(stream, activity_id, parent=None):
    """The id of the comment a createComment made, from its answer: the stream draws the post's comment list again
    holding only the new comment (and, for a reply, its parent). '' unless exactly one other comment of the post is
    named. Its creation time is in the id, as for a post (activity_time)."""
    ids = {c for a, c in COMMENT.findall(stream or '') if a == str(activity_id)} - {str(parent or '')}
    return ids.pop() if len(ids) == 1 else ''


def stream_errors(stream):
    """The `errors` list of a server request's answer: [] when the server did it, None when the answer has none."""
    found = re.search(r'"errors":(\[[^\]]*\])', stream or '')
    try:
        return json.loads(found.group(1)) if found else None
    except ValueError:
        return None


# --- messaging -----------------------------------------------------------------------------------------------------
def participant_user(participant):
    member = unwrap((participant.get('participantType') or {}).get('member')) \
        if isinstance(participant.get('participantType'), dict) else {}
    fsd = find(participant.get('hostIdentityUrn') or participant.get('entityUrn') or '', PROFILE)
    slug = SLUG.search(unquote(str(member.get('profileUrl') or '')))
    return user(fsd, slug.group(1) if slug else '', full_name(member.get('firstName'), member.get('lastName')),
                text(member.get('headline')), 'individual' if member else '')


def message(row, by, own_fsd):
    """One Message as the connector's _message."""
    urn = str(row.get('entityUrn') or '')
    mid = re.search(r',([^,()]+)\)$', urn)
    sender = participant_user(by.get(row.get('*sender'), {}))
    if not sender['id']:
        sender['id'] = find(row.get('*sender') or '', PROFILE)
    return {'id': mid.group(1) if mid else tail(row.get('backendUrn')) or urn, 'text': text(row.get('body')),
            'at': moment(row.get('deliveredAt')), 'is_sender': bool(own_fsd and sender['id'] == own_fsd),
            'sender_id': sender['id'], 'sender': sender,
            'hidden': row.get('messageBodyRenderFormat') in HIDDEN_FORMATS,
            'attachments': len(row.get('renderContent') or [])}


def chats(answer, own_fsd):
    """Conversations as the connector's _chat; the chat id is the thread id. A 1to1 chat names the other member."""
    by, out = index(answer), []
    rows = [entity(by, r) for r in elements(answer)] or typed(answer, 'messenger.Conversation')
    for row in rows:
        thread = CONVERSATION.search(str(row.get('entityUrn') or ''))
        if not thread:
            continue
        people = [participant_user(by.get(u, {'entityUrn': u})) for u in row.get('*conversationParticipants') or []]
        others = [p for p in people if p['id'] != own_fsd]
        group = bool(row.get('groupChat')) or len(others) > 1
        other = others[0] if len(others) == 1 and not group else None
        last = next((entity(by, u) for u in (row.get('messages') or {}).get('*elements') or []), None) \
            if isinstance(row.get('messages'), dict) else None
        last = message(last, by, own_fsd) if last else None
        out.append({'id': thread.group(1), 'name': (other or {}).get('display_name') or text(row.get('title')),
                    'type': 'group' if group else '1to1', 'user_id': (other or {}).get('id') or '',
                    'unread_count': number(row.get('unreadCount')) or 0, 'is_readonly': False,
                    'last_message_at': moment(row.get('lastActivityAt')) or (last or {}).get('at'),
                    'last_message': {'id': last['id'], 'text': last['text'], 'is_sender': last['is_sender']} if last else None})
    return out


def messages(answer, own_fsd):
    """A conversation's messages as the connector's _message, newest first."""
    by = index(answer)
    rows = [entity(by, r) for r in elements(answer)] or typed(answer, 'messenger.Message')
    found = [message(r, by, own_fsd) for r in rows if r.get('entityUrn')]
    return sorted(found, key=lambda m: m['at'] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
