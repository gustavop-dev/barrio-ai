"""The 21 operations Barrio asks of LinkedIn, made directly (ported from spikes/linkedin-directo/directo.py), with the
same arguments and answers as team_backend.connectors.UnipileConnector.

Every call goes through `_send`: the allowlist first (permitidas.check), then the Transport, then check_answer. Some
operations need more than one call (shown per method); a write never makes a read after sending, so a failure after
the write can never be mistaken for one before it. Reads that need the account's own ids (/me) make it once per
client. Ids are described in lectura.py and docs/navegador-contrato.md."""
import json
import re
from urllib.parse import quote

from . import lectura, permitidas, rutas
from .errores import LinkedInError, NoteQuota
from .transporte import Request, check_answer

# LinkedIn error codes that prove an invitation was refused for its note alone and none was created. None has been
# seen yet: until one is captured, every rejected invitation stays a plain error (a note quota needs proof).
NOTE_QUOTA_CODES = frozenset()
PROFILE_ID = re.compile(r'ACo[A-Za-z0-9_\-]{10,100}')
IDENTITY = re.compile(r'[A-Za-z0-9][A-Za-z0-9\-_%.]{1,99}')
QUERY_ID = re.compile(r'[A-Za-z][A-Za-z0-9_]{1,100}\.[0-9a-f]{16,64}')
PARSE_ERRORS = (KeyError, TypeError, ValueError, AttributeError, IndexError)


def invalid(what):
    return LinkedInError(f'{what} inválido; no se envió nada.', kind='invalid')


def activity_id(post_id):
    found = rutas.ACTIVITY.fullmatch(str(post_id or ''))
    if not found:
        raise invalid('Identificador de publicación')
    return found.group(1)


def comment_id(value):
    if not rutas.COMMENT_ID.fullmatch(str(value or '')):
        raise invalid('Identificador de comentario')
    return str(value)


def reaction_type(reaction):
    if reaction not in rutas.REACTIONS:
        raise LinkedInError('Reacción no admitida.', kind='invalid')
    return rutas.REACTIONS[reaction]


class Cliente:
    def __init__(self, transport):
        self.t = transport
        self.me = {}  # public_id, fsd and member of the account, from /me
        self.members = {}  # profile id -> member id, from every read that shows both: follow needs the member id
        self.secrets = {}  # received invitation id -> its shared secret: accepting needs it
        self.geo = None  # the location typeahead request, kept per client (two calls to get it)

    # --- calls -------------------------------------------------------------------------------------------------------
    def _send(self, request):
        permitidas.check(request)
        return check_answer(request, self.t.send(request))

    def _get(self, path, params=None, operation=''):
        return self._send(Request('GET', rutas.voyager(path, params), 'voyager', operation=operation))

    def _page(self, path, operation):
        return rutas.unescape(self._send(Request('GET', path, 'page', operation=operation)))

    def _write(self, request, operation, states=(), screen=None):
        """One server-driven UI write. Its answer is a component stream whose `errors` list says whether the server
        did it; a 2xx without the list is taken as done (the callers confirm every write by reading)."""
        body = rutas.envelope(request, states, screen)
        stream = self._send(Request('POST', rutas.sdui(request['requestId']), 'sdui', body, True, operation))
        errors = lectura.stream_errors(stream)
        if errors:
            raise LinkedInError(f'LinkedIn rechazó {operation} ({len(errors)} errores).', kind='rejected')

    def _graphql(self, prefixes, variables, fallback, host, operation):
        """A query id the page used itself, for a call with the same variable names, wins over the fixed one."""
        live = self.t.live_query(prefixes, list(variables)) or {}
        path = str(live.get('path') or '')
        path = path[len(rutas.VOYAGER):] if path.startswith(rutas.VOYAGER + '/') else path  # either form of the path
        if QUERY_ID.fullmatch(str(live.get('query_id') or '')) and re.fullmatch(r'/[A-Za-z0-9/_\-]{1,100}', path):
            host, query_id = path, live['query_id']
            variables = {k: v for k, v in variables.items() if k in (live.get('variables') or variables)}
        else:
            query_id = fallback
        return self._get(rutas.graphql(host, query_id, variables), operation=operation)

    def _read(self, parse, *args):
        """Parse an answer; a shape LinkedIn changed becomes a plain error, never a crash in the caller."""
        try:
            return parse(*args)
        except PARSE_ERRORS:
            raise LinkedInError('LinkedIn: respuesta con una forma inesperada.', kind='unreadable') from None

    def _own(self):
        if not self.me.get('fsd'):
            self.account_status()
        return self.me

    def _person(self, identifier, operation):
        ident = self._own()['public_id'] if identifier == 'me' else str(identifier or '')
        if not IDENTITY.fullmatch(ident):
            raise invalid('Identificador de perfil')
        answer = self._get('/identity/dash/profiles', {'q': 'memberIdentity', 'memberIdentity': ident,
                                                       'decorationId': rutas.PROFILE_DECO}, operation)
        found = self._read(lectura.person, answer, ident, self.members)
        if not found or not found['id']:
            raise LinkedInError('LinkedIn: perfil no encontrado.', kind='not_found', status=404)
        return found

    def _profile_id(self, user_id, operation):
        """The fsd_profile id the routes take: as given when it looks like one, else read once."""
        if user_id == 'me':
            return self._own()['fsd']
        return user_id if PROFILE_ID.fullmatch(str(user_id or '')) else self._person(user_id, operation)['id']

    # --- account and profiles ----------------------------------------------------------------------------------------
    def account_status(self):
        """/me: answering it means the session works (one call)."""
        me = self._read(lectura.own, self._get('/me', operation='account_status'))
        if not me.get('fsd') or not me.get('public_id'):
            raise LinkedInError('LinkedIn: /me sin el perfil de la cuenta.', kind='unreadable')
        self.me = me
        if me.get('member'):
            self.members[me['fsd']] = me['member']
        return {'status': 'running', 'is_locked': False}

    def get_user(self, identifier):
        """Public id, profile id or 'me' (one call; /me once for 'me')."""
        found = self._person(identifier, 'get_user')
        return {k: found[k] for k in ('id', 'public_identifier', 'display_name', 'profile_url', 'headline', 'type')}

    def get_profile(self, user_id):
        """The profile and, from the top card, distance, a pending invitation, follow state and the person's reach
        (two calls; public client libraries note that the top card registers a profile view). The account's own
        profile skips the top card."""
        found = self._person(user_id, 'get_profile')
        out = {k: found[k] for k in ('id', 'public_identifier', 'display_name', 'profile_url', 'headline', 'type')}
        out.update(location=found['location'], network_distance='', is_following=False, relation_request_status='',
                   invitation_id='', is_restricted=False, signals={'bio': found['bio']} if found['bio'] else {})
        if user_id == 'me' or (self.me.get('fsd') and found['id'] == self.me['fsd']):
            out['network_distance'] = 'SELF'
            return out
        if not found['public_identifier']:
            return out
        card = self._get(rutas.top_card(found['public_identifier']), operation='get_profile')
        relation = self._read(lectura.relation, card, found['public_identifier'])
        signals = {k: relation[k] for k in ('followers', 'connections') if relation[k] is not None}
        out.update(network_distance=relation['network_distance'], is_following=relation['is_following'],
                   relation_request_status='PENDING' if relation['pending'] else '',
                   invitation_id=relation['invitation_id'], signals={**signals, **out['signals']})
        return out

    def own_audience(self):
        """Followers and connections from the account's own top card (/me once, then one call)."""
        me = self._own()
        card = self._get(rutas.top_card(me['public_id']), operation='own_audience')
        relation = self._read(lectura.relation, card, me['public_id'])
        return {'followers': relation['followers'], 'connections': relation['connections']}

    def profile_views(self, days=14):
        """LinkedIn's summary of profile views counts its own window (VIEWS_DAYS); any other window is not available
        and stays absent without calling."""
        if int(days) != rutas.VIEWS_DAYS:
            return None
        return self._read(lectura.profile_views, self._get('/identity/wvmpCards', operation='profile_views'))

    # --- posts and comments ------------------------------------------------------------------------------------------
    def list_user_posts(self, user_id, limit=10):
        """The old feed's member shares (one call; the profile read first only for a public id). For the account's
        own posts the counters carry the impressions."""
        fsd = self._profile_id(user_id, 'list_user_posts')
        answer = self._get('/identity/profileUpdatesV2', {
            'q': 'memberShareFeed', 'profileUrn': f'urn:li:fsd_profile:{fsd}', 'moduleKey': 'member-shares:phone',
            'count': int(limit), 'start': 0, 'includeLongTermHistory': 'true'}, 'list_user_posts')
        return self._read(lectura.posts, answer, fsd, self.members)[:int(limit)]

    def get_post(self, post_id):
        """One post (one call): the highlightedFeed finder answers the asked update first. Impressions come null."""
        aid = activity_id(post_id)
        urn = quote(f'urn:li:activity:{aid}', safe='')
        answer = self._get(f'/feed/updates?q=highlightedFeed&highlightedUpdateUrns=List({urn})', operation='get_post')
        found = self._read(lectura.highlighted, answer, aid, self.members)
        if not found:
            raise LinkedInError('LinkedIn: el primer resultado no es la publicación pedida.', kind='not_found', status=404)
        return found

    def list_comments(self, post_id, limit=50):
        """Top-level comments (one call, /me once to know which are the account's own)."""
        aid, own = activity_id(post_id), self._own()
        answer = self._get('/feed/comments', {'q': 'comments', 'updateId': f'activity:{aid}', 'count': int(limit),
                                              'start': 0, 'sortOrder': 'RELEVANCE'}, 'list_comments')
        return self._read(lectura.comments, answer, own['fsd'], None, self.members)[:int(limit)]

    def list_comment_thread(self, post_id, comment, limit=50):
        """The answers of one comment (one call): the same finder with the comment's thread, percent-encoded as a
        plain string (written raw, Rest.li reads it as a record and answers 400)."""
        aid, cid, own = activity_id(post_id), comment_id(comment), self._own()
        thread = quote(f'comment:(activity:{aid},{cid})', safe='')
        answer = self._get(f'/feed/comments?q=comments&updateId={thread}&count={int(limit)}&start=0'
                           f'&sortOrder=CHRONOLOGICAL', operation='list_comment_thread')
        return self._read(lectura.comments, answer, own['fsd'], cid, self.members)[:int(limit)]

    def _comment_template(self, aid, parent, operation):
        """The post page carries one createComment request for its box and one per comment it draws (about the first
        8); the text goes in the box's states. Without the right template nothing is sent."""
        found = rutas.templates(self._page(rutas.post_page(aid), operation), rutas.COMMENT)
        try:
            mine = [t for t in found if str((t['requestedArguments']['payload']['collection'].get('parentCommentUrn') or {})
                    .get('commentId')) == parent] if parent else \
                [t for t in found if 'parentCommentUrn' not in t['requestedArguments']['payload']['collection']]
        except PARSE_ERRORS:
            mine = []
        if not mine:
            raise LinkedInError('La página del post no trae ' + ('ese comentario' if parent else 'la caja de comentarios')
                                + '; no se envió nada.', kind='template_missing')
        return mine[0]

    def _written(self, text, thread=None):
        """What a comment write returns: LinkedIn's answer is a component stream with no reliable id of the new
        comment, so the id stays empty and the callers find it by reading (own comment with the same text)."""
        return {'id': '', 'text': text, 'created_at': None, 'is_sender': True, 'thread_id': thread,
                'author': lectura.user(self.me.get('fsd', ''), self.me.get('public_id', ''), kind='individual'),
                'reply_counter': None}

    def _comment(self, aid, parent, text, operation):
        if not isinstance(text, str) or not text.strip():
            raise invalid('Texto del comentario')
        template = self._comment_template(aid, parent, operation)
        try:
            states = rutas.comment_states(template, text)
        except PARSE_ERRORS:
            raise LinkedInError('La caja de comentarios cambió; no se envió nada.', kind='template_missing') from None
        self._write(template, operation, states, rutas.POST_SCREEN)

    def create_comment(self, post_id, text):
        """Two calls: the post page (for the box's template) and the write."""
        self._comment(activity_id(post_id), None, text, 'create_comment')
        return self._written(text)

    def comment_in_thread(self, post_id, comment, text):
        """Two calls: the post page and the write. Only works on a comment the page draws (about the first 8). The text
        goes as it is: no mention of the comment's author is added."""
        cid = comment_id(comment)
        self._comment(activity_id(post_id), cid, text, 'comment_in_thread')
        return self._written(text, cid)

    def react_to_comment(self, post_id, comment, reaction):
        kind, aid, cid = reaction_type(reaction), activity_id(post_id), comment_id(comment)
        self._write(rutas.comment_reaction(aid, cid, kind), 'react_to_comment')
        return {'reaction': reaction}

    def add_reaction(self, post_id, reaction):
        kind, aid = reaction_type(reaction), activity_id(post_id)
        self._write(rutas.reaction(aid, kind), 'add_reaction')
        return {'reaction': reaction}

    # --- network -----------------------------------------------------------------------------------------------------
    def search_people(self, keywords, location=None, profile_language=None):
        """The people search page (one call): 10 results with their profile and member ids. Names, headlines and
        distance are NOT read here (that would be one profile read per result): they come empty and the callers'
        capped profile read fills them, as for a commenter."""
        if not isinstance(keywords, str) or not keywords.strip():
            raise invalid('Búsqueda')
        regions = [str(r) for r in location or [] if str(r).isdigit()] or None
        languages = [str(l) for l in profile_language or [] if re.fullmatch(r'[a-z]{2}', str(l))] or None
        html = self._page(rutas.search_page(keywords, regions, languages), 'search_people')
        found = self._read(lectura.search_results, html)
        own = self.me.get('fsd')
        for fsd, member in found:
            if member:
                self.members[fsd] = member
        return [dict(lectura.user(fsd, kind='individual'), location='', network_distance='SELF' if fsd == own else '',
                     signals={}) for fsd, _ in found]

    def _geo_template(self):
        """The location typeahead request: the search page names a lazy filter bar, the filter bar carries the
        typeahead (two calls, once per client). The one fired on focus ignores the text (`emptyStateKeyword`)."""
        if self.geo:
            return self.geo
        html = self._page(rutas.search_page('a'), 'search_parameters')
        try:
            start = html.index(f'"newComponentId":"{rutas.FILTER_BAR}"')
            action = json.JSONDecoder().raw_decode(html, html.rindex('{"$type"', 0, start))[0]
            body = {'componentId': rutas.FILTER_BAR, 'clientArguments': {
                **action['requestedArguments'], 'states': [], 'screenId': rutas.SEARCH_SCREEN, 'knownTemplateIds': []}}
        except PARSE_ERRORS:
            raise LinkedInError('La página de búsqueda no trae la barra de filtros.', kind='template_missing') from None
        bar = self._send(Request('POST', rutas.sdui(rutas.FILTER_BAR, 'component'), 'sdui', body,
                                 operation='search_parameters'))
        typing = [t for t in rutas.templates(rutas.unescape(bar), rutas.GEO_TYPEAHEAD)
                  if 'emptyStateKeyword' not in ((t.get('requestedArguments') or {}).get('payload') or {})]
        if not typing or not isinstance(typing[0]['requestedArguments']['payload'].get('keywordsField'), dict):
            raise LinkedInError('La barra de filtros no trae el typeahead de ubicación.', kind='template_missing')
        self.geo = typing[0]
        return self.geo

    def search_parameters(self, kind, keywords, limit=5):
        """Location ids for the people search (three calls the first time, then one). Only locations exist here."""
        if kind != 'LOCATION':
            raise LinkedInError('Solo hay parámetros de ubicación.', kind='invalid')
        template = self._geo_template()
        field = template['requestedArguments']['payload']['keywordsField']
        body = rutas.envelope(template, [rutas.state(field.get('key'), 'stringValue', keywords,
                                                     field.get('namespace') or 'MemoryNamespace')], rutas.SEARCH_SCREEN)
        stream = self._send(Request('POST', rutas.sdui(rutas.GEO_TYPEAHEAD), 'sdui', body, operation='search_parameters'))
        return self._read(lectura.places, stream)[:int(limit)]

    def follow_user(self, user_id):
        """One write. It needs the member id: the read that found the person keeps it (profile, comment, search);
        otherwise the profile is read first."""
        fsd = self._profile_id(user_id, 'follow_user')
        member = self.members.get(fsd) or self._person(fsd, 'follow_user')['member']
        if not member:
            raise LinkedInError('LinkedIn: perfil sin id de miembro; no se envió nada.', kind='not_found')
        self._write(rutas.follow(member), 'follow_user')
        return {'user_id': user_id}

    def send_invitation(self, user_id, note=None):
        """One write (the profile read first only for a public id). Answering it, LinkedIn also makes the account
        follow the person. A refusal is NoteQuota only when LinkedIn's code proves the note alone was refused."""
        fsd = self._profile_id(user_id, 'send_invitation')
        if note and len(note) > rutas.NOTE_LIMIT:
            raise invalid('Nota de invitación')
        request = Request('POST', rutas.voyager(rutas.INVITE), 'voyager', rutas.invitation(fsd, note or ''), True,
                          'send_invitation')
        try:
            answer = self._send(request)
        except LinkedInError as exc:
            if note and exc.kind.startswith('linkedin/') and exc.kind.split('/', 1)[1] in NOTE_QUOTA_CODES:
                raise NoteQuota('LinkedIn: cuota de notas agotada; no se creó la invitación.', exc.status) from None
            raise
        return {'id': lectura.invitation_id(answer), 'type': 'sent', 'created_at': None, 'message': note or '',
                'user': lectura.user(fsd, kind='individual')}

    def list_invitations(self, kind, limit=100):
        """Received or sent connection invitations (one call). Received ones keep their shared secret for accepting."""
        if kind not in ('sent', 'received'):
            raise LinkedInError('Tipo de invitación inválido.', kind='invalid')
        count = max(1, min(int(limit), 100))
        if kind == 'received':
            answer = self._get(rutas.RECEIVED_INVITATIONS, {'q': 'receivedInvitation', 'start': 0, 'count': count,
                                                            'includeInsights': 'true'}, 'list_invitations')
        else:
            answer = self._get(rutas.SENT_INVITATIONS, {'q': 'invitationType', 'invitationType': 'CONNECTION',
                                                        'start': 0, 'count': count}, 'list_invitations')
        rows, secrets = self._read(lectura.invitations, answer, kind, self.members)
        if kind == 'received':
            self.secrets.update(secrets)
        return rows[:int(limit)]

    def accept_invitation(self, request_id):
        """One write with the invitation's shared secret, kept by the received list read just before; without it the
        list is read once more."""
        iid = str(request_id or '')
        if not rutas.COMMENT_ID.fullmatch(iid):
            raise invalid('Identificador de invitación')
        if iid not in self.secrets:
            self.list_invitations('received')
        if iid not in self.secrets:
            raise LinkedInError('La invitación ya no está entre las recibidas; no se envió nada.',
                                kind='invitation_gone', status=404)
        self._send(Request('POST', rutas.voyager(rutas.ACCEPT.format(iid)), 'voyager',
                           rutas.acceptance(iid, self.secrets[iid]), True, 'accept_invitation'))
        return {'request_id': request_id}

    # --- inbox (reads only: nothing here sends, marks or edits a message) --------------------------------------------
    def list_chats(self, limit=20, inbox='CLASSIC_PRIMARY'):
        """The account's own conversations (one call, /me once). Company page inboxes are not read here."""
        if inbox != 'CLASSIC_PRIMARY':
            return []
        own = self._own()
        answer = self._graphql(rutas.CONVERSATION_QUERIES, {'mailboxUrn': quote(f'urn:li:fsd_profile:{own["fsd"]}', safe='')},
                               rutas.CONVERSATIONS, rutas.MESSAGING, 'list_chats')
        return self._read(lectura.chats, answer, own['fsd'])[:int(limit)]

    def list_chat_messages(self, chat_id, limit=10):
        """The newest messages of a chat (one call, /me once): `chat_id` is the thread id list_chats gives."""
        if not rutas.THREAD.fullmatch(str(chat_id or '')):
            raise invalid('Identificador de conversación')
        own = self._own()
        urn = f'urn:li:msg_conversation:(urn:li:fsd_profile:{own["fsd"]},{chat_id})'
        answer = self._graphql(rutas.MESSAGE_QUERIES, {'conversationUrn': quote(urn, safe='')}, rutas.MESSAGES,
                               rutas.MESSAGING, 'list_chat_messages')
        return self._read(lectura.messages, answer, own['fsd'])[:int(limit)]

