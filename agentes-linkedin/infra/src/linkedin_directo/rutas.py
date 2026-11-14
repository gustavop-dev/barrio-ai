"""LinkedIn's routes, query ids and request builders, as the 2026 web app sends them (spike of 2026-11-13, test
account; spikes/linkedin-directo/README.md has the state of each operation).

Two APIs live side by side:
- Voyager (`/voyager/api/...`, JSON): /me, profiles, the old feed format (posts, comments, replies, counters),
  invitations, messaging and profile views. The web app no longer calls most of these, but they still answer.
- The server-driven UI (`/flagship-web/rsc-action/actions/...`, POST, a React component stream): every button and
  pager of the feed (reactions, comments, follow) and the search filters. No Voyager route was seen for those writes.
  Its requests are `{requestId, requestedArguments}` plus `states`, the values of the UI fields the request binds; a
  page carries ready-made ones (templates) in its HTML.

What rotates with LinkedIn deploys: GraphQL query ids (a live one the page used wins over the fixed one here), sduiids
and the binding names of the comment box (taken from the page's template, never written by hand)."""
import copy
import json
import re
import uuid
from urllib.parse import quote, urlencode

WEB = 'https://www.linkedin.com'
VOYAGER = '/voyager/api'
SDUI = '/flagship-web/rsc-action/actions/'

PROFILE_DECO = 'com.linkedin.voyager.dash.deco.identity.profile.FullProfile-76'
# The web profile top card (still answering 2026-11-13): distance, pending invitation, follow state, connections and
# followers. Public client libraries note that this read registers a profile view (not checked).
TOP_CARD = 'voyagerIdentityDashProfiles.a3de77c32c473719f1c58fae6bff43a5'
# Messaging has its own GraphQL host; ids seen in the web app's own calls on 2026-11-13 (they rotate: live ones win).
MESSAGING = '/voyagerMessagingGraphQL/graphql'
CONVERSATIONS = 'messengerConversations.05bbed349f58585b3270fc478e2fc81c'
MESSAGES = 'messengerMessages.b88ffdf26effae7a346a4df9ee0e764c'
CONVERSATION_QUERIES = ('messengerConversations', 'voyagerMessagingDashMessengerConversations')
MESSAGE_QUERIES = ('messengerMessages', 'voyagerMessagingDashMessengerMessages')
RECEIVED_INVITATIONS = '/relationships/invitationViews'
SENT_INVITATIONS = '/relationships/sentInvitationViewsV2'
# The web app's own invitation call (decoration -3). Answering it, LinkedIn also makes the account follow the person.
INVITE = ('/voyagerRelationshipsDashMemberRelationships?action=verifyQuotaAndCreateV2'
          '&decorationId=com.linkedin.voyager.dash.deco.relationships.InvitationCreationResultWithInvitee-3')
# The libraries' legacy route; it worked with the list's sharedSecret on 2026-11-13.
ACCEPT = '/relationships/invitations/{}?action=accept'

REACT = 'com.linkedin.sdui.reactions.create'
FOLLOW = 'com.linkedin.sdui.requests.mynetwork.addaUpdateFollowState'
COMMENT = 'com.linkedin.sdui.comments.createComment'
FILTER_BAR = 'com.linkedin.sdui.generated.search.dsl.impl.lazyLoadedFilterBar'
GEO_TYPEAHEAD = 'com.linkedin.sdui.search.filters.requests.FiltersLocationTypeaheadRequest'
SNIPPETS = 'com.linkedin.sdui.requests.search.batchClassicSnippetRequest'
POST_SCREEN = 'com.linkedin.sdui.flagshipnav.feed.UpdateDetail'
SEARCH_SCREEN = 'com.linkedin.sdui.flagshipnav.search.SearchResultsPeople'
# The creator analytics «Export» dialog: opening it only draws the dialog (no side effect) and its answer already
# carries the whole workbook for the dates asked (analitica.py). Seen from /analytics/creator/content/ on 2026-11-13.
ANALYTICS_SCREEN = 'com.linkedin.sdui.flagshipnav.creatoranalytics.AggregateAnalyticsExportModal'

# Barrio's reaction names (connectors.REACTIONS) -> LinkedIn's. Only LIKE was tried on 2026-11-13.
REACTIONS = {'linkedin_like': 'LIKE', 'linkedin_celebrate': 'PRAISE', 'linkedin_support': 'APPRECIATION',
             'linkedin_love': 'EMPATHY', 'linkedin_insightful': 'INTEREST', 'linkedin_funny': 'ENTERTAINMENT'}
NOTE_LIMIT = 300  # characters LinkedIn takes in an invitation note
# The profile-views summary card counts LinkedIn's own window (the web says «past 90 days»; not checked against the
# answer): its number is only returned when the caller asks for that window.
VIEWS_DAYS = 90

RA = 'proto.sdui.actions.requests.RequestedArguments'
META = {'$type': 'proto.sdui.common.RequestMetadata'}
TEXT_MODEL = 'proto.sdui.components.core.text.TextModel'
# The comment box: payload field -> (state type, empty value). The text goes in the first two. Field names come from
# the page; the binding keys only need to match between payload and states.
COMMENT_BOX = (
    ('commentFieldBinding', 'stringValue', ''),
    ('richCommentFieldBinding', 'textModelForWrite', None),
    ('linkPreviewIngestedContentId', 'stringValue', ''),
    ('externalImageUrl', 'stringValue', ''),
    ('externalImageId', 'stringValue', ''),
    ('lastPasteCharacterCount', 'intValue', 0),
    ('pasteToCreateDuration', 'signedLongValue', 0),
    ('hasEditsSinceLastPaste', 'booleanValue', False),
)
ACTIVITY = re.compile(r'(?:urn:li:activity:)?(\d{1,25})')
COMMENT_ID = re.compile(r'\d{1,25}')
# A LinkedIn messaging thread id, as it appears in linkedin.com/messaging/thread/<id>/ and in the conversation urn.
THREAD = re.compile(r'2-[A-Za-z0-9_=+/\-]{1,200}')


def voyager(path, params=None):
    """`path` may carry its own query (Rest.li literals are written by hand to keep `( : ,` raw); `params` are plain
    values, percent-encoded."""
    query = urlencode(params or {}, quote_via=quote)
    return VOYAGER + path + (('&' if '?' in path else '?') + query if query else '')


def graphql(host, query_id, variables):
    """A GraphQL GET (path under VOYAGER) with a Rest.li literal whose values the caller already percent-encoded, in
    the parameter order the web app uses on each host."""
    literal = '(' + ','.join(f'{k}:{v}' for k, v in variables.items()) + ')'
    if host.startswith(MESSAGING):
        return f'{host}?queryId={query_id}&variables={literal}'
    return f'{host}?includeWebMetadata=true&variables={literal}&queryId={query_id}'


def top_card(public_id):
    return graphql('/graphql', TOP_CARD, {'vanityName': quote(public_id, safe='')})


def sdui(sduiid, kind='server-request'):
    component = f'componentId={quote(sduiid, safe="")}&' if kind == 'component' else ''
    return f'{SDUI}{kind}?{component}sduiid={quote(sduiid, safe="")}'


def navigation(screen):
    """A server-driven UI screen opened as a dialog: the screen is named twice, as the web app does."""
    return f'{SDUI}navigation?screenId={quote(screen, safe="")}&sduiid={quote(screen, safe="")}'


def analytics_export(start, end):
    """The body of the analytics export dialog for [start, end] (ISO dates, both included)."""
    return {'clientArguments': {'$type': RA, 'requestedStateKeys': [], 'payload': {'startDate': start, 'endDate': end},
                                'requestMetadata': META, 'states': [], 'screenId': ANALYTICS_SCREEN,
                                'knownTemplateIds': []}, 'isModal': True}


def post_page(activity_id):
    return f'/feed/update/urn:li:activity:{activity_id}/'


def search_page(keywords, regions=None, languages=None, page=1):
    """The people search page. `regions` are geo ids from the location typeahead; `languages` two-letter codes (the
    web app's `profileLanguage` filter, not tried in the spike)."""
    query = f'?keywords={quote(keywords)}&origin=GLOBAL_SEARCH_HEADER'
    for name, values in (('geoUrn', regions), ('profileLanguage', languages)):
        if values:
            query += f'&{name}=' + quote(json.dumps([str(v) for v in values], separators=(',', ':')))
    if page > 1:
        query += f'&page={page}'
    return '/search/results/people/' + query


def unescape(html):
    """The page keeps its component tree in script strings: `\\"` -> `"` makes it parseable JSON again."""
    return html.replace('\\"', '"')


def templates(text, request_id):
    """Every ready-made request with this requestId in a page or component stream (dicts, in page order)."""
    found, decoder = [], json.JSONDecoder()
    for m in re.finditer(r'\{"requestId":"' + re.escape(request_id) + '"', text):
        try:
            found.append(decoder.raw_decode(text, m.start())[0])
        except ValueError:  # a template cut by the page's own string splitting
            pass
    return found


def state(key, case, value, namespace='MemoryNamespace'):
    return {'key': key, 'namespace': namespace, 'value': value, 'originalProtoCase': case,
            'protoKey': {'$type': 'proto.sdui.Key', 'value': {'$case': 'id', 'id': key}}}


def envelope(request, states=(), screen=None):
    """The body the web app POSTs for a server request: the request (requestId + requestedArguments), the bound
    field values in `states` (twice, as the app does) and the screen. `{requestId, requestedArguments: {payload}}`
    alone answers 500; the RequestedArguments `$type`, `requestedStateKeys`, `requestMetadata` and `states` are enough
    for reactions and follow. Comments only went through with the page's whole action as `serverRequest`, the screen
    and an `_ExecutionId`, so a page template (more than requestId and requestedArguments) is sent that way."""
    args = {'$type': RA, 'requestedStateKeys': [], 'requestMetadata': META, **request['requestedArguments'],
            'states': list(states)}
    body = {'requestId': request['requestId'], 'states': list(states), 'requestedArguments': args}
    if set(request) - {'requestId', 'requestedArguments'}:
        args['payload'] = {**args['payload'], '_ExecutionId': str(uuid.uuid4())}
        body['serverRequest'] = request
    if screen:
        args.update(screenId=screen, knownTemplateIds=[])
    return body


def _collection(template):
    return template['requestedArguments']['payload']['collection']


def comment_template(found, activity_id, parent=None):
    """The createComment request for the post's box, or for a reply to `parent`, from the page's templates (None when
    there is no base). The page only draws the reply boxes of its first comments (4 of 42 on 2026-11-13); a reply to
    any other one reuses another comment's reply template with the parent swapped, or turns the post's box into a
    reply. The binding keys are opaque: they only need to match the states, and the states are built from them."""
    box = [t for t in found if 'parentCommentUrn' not in _collection(t)]
    if not parent:
        return box[0] if box else None
    replies = [t for t in found if 'parentCommentUrn' in _collection(t)]
    exact = [t for t in replies if str((_collection(t)['parentCommentUrn'] or {}).get('commentId')) == str(parent)]
    if exact or not (replies or box):
        return exact[0] if exact else None
    built = copy.deepcopy(replies[0] if replies else box[0])
    urn = {'commentId': str(parent), 'thread': f'urn:li:activity:{activity_id}'}
    collection = _collection(built)
    collection['threadUrn'] = {'threadUrnCommentThreadUrn': {'commentUrn': dict(urn)}}
    collection['parentThreadUrn'] = {'threadUrnActivityThreadUrn': {'activityUrn': {'activityId': str(activity_id)}}}
    collection['parentCommentUrn'] = dict(urn)
    return built


def has_mention(value):
    """True when a nested value carries a mention (the web pre-fills one of the parent's author in a reply box)."""
    if isinstance(value, dict):
        return value.get('$case') == 'mention' or 'mention' in value or any(has_mention(v) for v in value.values())
    if isinstance(value, list):
        return any(has_mention(v) for v in value)
    return False


def comment_states(template, text):
    """Fill a createComment template: every binding of the box gets its state, the text in the plain and rich field.
    A template without one of the box's fields raises KeyError (the page changed: nothing is sent)."""
    states = []
    for field, case, empty in COMMENT_BOX:
        key = template['requestedArguments']['payload'][field]['key']
        if case == 'textModelForWrite':
            value = {'$type': TEXT_MODEL, 'text': text, 'attribute': [], 'webDataAttributes': []}
        else:
            value = text if field == 'commentFieldBinding' else empty
        states.append(state(key, case, value))
    return states


def reaction(activity_id, kind):
    return {'requestId': REACT, 'requestedArguments': {'payload': {
        'threadUrn': {'threadUrnActivityThreadUrn': {'activityUrn': {'activityId': str(activity_id)}}},
        'reactionType': f'ReactionType_{kind}', 'reactionSource': 'Update'}}}


def comment_reaction(activity_id, comment_id, kind):
    return {'requestId': REACT, 'requestedArguments': {'payload': {
        'threadUrn': {'threadUrnCommentThreadUrn': {'commentUrn': {
            'commentId': str(comment_id), 'thread': f'urn:li:activity:{activity_id}'}}},
        'reactionType': f'ReactionType_{kind}', 'reactionSource': 'Comment'}}}


def follow(member_id):
    """`member_id` is the number in urn:li:member:<n>. The app also sends a followStateBinding and post-action
    configs; the server does not need them."""
    return {'requestId': FOLLOW, 'requestedArguments': {'payload': {
        'followStateType': 'FollowStateType_FOLLOW_ACTIVE', 'memberUrn': {'memberId': str(member_id)}}}}


def invitation(profile_id, note=''):
    body = {'invitee': {'inviteeUnion': {'memberProfile': f'urn:li:fsd_profile:{profile_id}'}}}
    if note:
        body['customMessage'] = note
    return body


def acceptance(invitation_id, secret):
    return {'invitationId': str(invitation_id), 'invitationSharedSecret': secret, 'isGenericInvitation': False}
