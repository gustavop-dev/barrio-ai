"""The daily canary, ported from spikes/linkedin-directo/canario.py: the connector's 14 reads, once (16 calls to
LinkedIn), checking that each answer still gives the fields Barrio's callers use; then what the writes depend on,
WITHOUT writing (one more call: 17). LinkedIn renames things without warning and an HTTP 200 with a field gone is a
silent break.

The writes (since 19/11/2026, when the comment box's template stopped parsing and every comment failed while this
canary, which only read, said all was fine): each write's Request is built as the client would send it and checked
against the allowlist (permitidas.check), and never sent.
- create_comment and comment_in_thread: one read of a post page (the comments' post), its createComment templates, the
  states of the box and the reply built from them.
- follow_user: the member id it needs, from the profile read and the people search already made (no call).
- accept_invitation: the shared secret it needs, from the received invitations already read (no call).
- add_reaction, react_to_comment and send_invitation go by a fixed route with a fixed body: nothing on a page tells
  whether they still work, only LinkedIn's answer to a real one ('sin_probar': «solo se sabe al escribir»).

It runs over any Transport: the backend's daily job sends it through the account's connector (team_backend/canario.py)
and `python -m navegador canario` through the running service, so its calls pass the service's budgets and stops like
any other. It reads only the account's own profile, posts and inbox, and the comments (and page) of the busiest post its
feed brings along, like the spike. The report keeps states, row counts and field names, never a value (no names, texts
or ids).

Result: 'ok' nothing broke (`broken`); 'roto' something broke (LinkedIn changed an answer or a page); 'alto' LinkedIn
pushed back or the service has the account stopped or without a session (do not retry: someone has to look);
'no_corrio' it could not run (the service unreachable, busy or out of budget, another internet exit, its configuration):
nothing to judge."""
import json
import time
from datetime import datetime

from . import lectura, permitidas, rutas
from .cliente import Cliente
from .errores import LinkedInError
from .transporte import Transport

OK, BROKEN, HALTED, NOT_RUN = 'ok', 'roto', 'alto', 'no_corrio'
UNTRIED = 'sin_probar'
WRITE = 'escritura'  # a row's `tipo` when it checks a write (the reads carry no `tipo`)
ONLY_BY_WRITING = 'solo se sabe al escribir'
# Nothing reached LinkedIn, or nothing came back: the run says nothing about LinkedIn and stops there.
NOT_RUN_KINDS = ('config', 'disabled', 'not_sent', 'budget', 'network', 'egress')
HALT_KINDS = ('stopped', 'login')
# The reply the canary prepares when no comment of the post has answers: never sent, any comment id builds the same.
ANY_COMMENT = '1'


def broken(row):
    """Whether a report row says something broke: a read that did not give its fields or could not be tried (a read
    before it found nothing), or a write whose Request could not be prepared. A write left untried is not: either a
    read before it found nothing to prepare it with, or it goes by a fixed route that only writing can test."""
    if row.get('tipo') == WRITE:
        return row.get('estado') == BROKEN
    return row.get('estado') != OK


class Skipped(Exception):
    """An earlier read found nothing for this one to read (not a LookupError: a KeyError from a changed answer must
    count as broken, not as skipped)."""


class Recorder(Transport):
    """Counts the calls and keeps the last answer's text: the busiest feed post and comment are picked from LinkedIn's
    own counters, as the spike did, without keeping them."""

    def __init__(self, transport):
        self.transport, self.last, self.calls = transport, '', 0

    def send(self, request):
        self.calls += 1
        answer = self.transport.send(request)
        self.last = answer.text
        return answer

    def live_query(self, prefixes, variables):
        return self.transport.live_query(prefixes, variables)

    def busiest(self, kind, skip=''):
        """The id (activity number or comment number) with the most comments among the last answer's counters."""
        try:
            counts = lectura._counts(json.loads(self.last))
        except (ValueError, AttributeError):
            return ''
        rows = sorted(((c.get('numComments') or 0, urn) for urn, c in counts.items()
                       if isinstance(urn, str) and urn.startswith(f'urn:li:{kind}:') and not (skip and skip in urn)),
                      reverse=True)
        if not rows or not rows[0][0]:
            return ''
        return rows[0][1].rstrip(')').rsplit(',' if kind == 'comment' else ':', 1)[-1]


# --- what each answer must carry ------------------------------------------------------------------------------------
def dig(value, path):
    for key in path.split('.'):
        value = value.get(key) if isinstance(value, dict) else None
    return value


def holds(value, kind):
    if kind == 'num':
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == 'fecha':
        return isinstance(value, datetime)
    if kind == 'sino':
        return isinstance(value, bool)
    return isinstance(value, str) and bool(value.strip())  # texto


def lacking(rows, fields):
    """Fields no row carries with the right kind: one row with it is enough (a post may have no text), but a field no
    row has any more is a rename."""
    return [path for path, kind in fields if not any(holds(dig(row, path), kind) for row in rows)]


PERSON = (('id', 'texto'), ('public_identifier', 'texto'), ('display_name', 'texto'))
POST = (('id', 'texto'), ('created_at', 'fecha'), ('author.id', 'texto'), ('reactions_counter', 'num'),
        ('comments_counter', 'num'))
# author.id: the metrics count a commenter by it; is_sender: without it the account's own comments pass as third-party.
COMMENT = (('id', 'texto'), ('text', 'texto'), ('created_at', 'fecha'), ('author.id', 'texto'), ('author.display_name', 'texto'),
           ('is_sender', 'sino'))
INVITATION = (('id', 'texto'), ('user.id', 'texto'), ('created_at', 'fecha'))
CHAT = (('id', 'texto'), ('last_message_at', 'fecha'))
MESSAGE = (('id', 'texto'), ('at', 'fecha'), ('sender_id', 'texto'))


def verdict(rows, least, fields):
    """(state, reason, rows)."""
    rows = rows if isinstance(rows, list) else [rows]
    if len(rows) < least:  # with no rows the field list says nothing
        return BROKEN, f'{len(rows)} filas (se esperaba al menos {least})', len(rows)
    missing = lacking(rows, fields) if rows else []
    return (BROKEN, 'faltan campos: ' + ', '.join(missing), len(rows)) if missing else (OK, '', len(rows))


def steps(client, recorder, found):
    """The 14 reads in order, as (name, call -> (state, reason, rows)). Each fills `found` with what later ones
    need; Skipped means an earlier step found nothing to read here."""
    def need(key):
        if not found.get(key):
            raise Skipped(f'sin dato de una operación anterior ({key})')
        return found[key]

    def status():
        out = client.account_status()
        return (OK, '', 1) if out.get('status') == 'running' else (BROKEN, 'estado inesperado', 1)

    def user():
        # /me left the account's member id in `members`: out of it, so what follow_user checks is the profile read's.
        client.members.pop(client.me.get('fsd'), None)
        out = client.get_user('me')
        found['profile_member'] = client.members.get(out.get('id')) or 'falta'
        return verdict([out], 1, PERSON)

    def audience():
        out = client.own_audience()
        return verdict([out], 1, (('followers', 'num'), ('connections', 'num')))

    def views():
        out = client.profile_views(rutas.VIEWS_DAYS)
        return (OK, '', 1) if holds(out, 'num') else (BROKEN, 'sin número de visitas', 0)

    def posts():
        rows = client.list_user_posts('me', 5)
        if rows:
            found['post'] = rows[0]['id']
        # The text matches a published piece to its post; checked on the list, where one post with text is enough (a
        # repost or a photo alone has none, so get_post's single post is not held to it).
        return verdict(rows, 1, POST + (('impressions', 'num'), ('text', 'texto')))

    def post():
        out = client.get_post(need('post'))
        found['busy_post'] = recorder.busiest('activity', skip=found['post'])
        if out.get('id') != found['post']:
            return BROKEN, 'no es la publicación pedida', 1
        return verdict([out], 1, POST)

    def comments():
        target = found.get('busy_post') or need('post')
        rows = client.list_comments(target, 20)
        found['comment_post'], found['comment'] = target, recorder.busiest('comment')
        return verdict(rows, 1, COMMENT)

    def thread():
        rows = client.list_comment_thread(need('comment_post'), need('comment'), 10)
        return verdict(rows, 1, COMMENT + (('thread_id', 'texto'),))

    def people():
        rows = client.search_people('founder')
        found['search_members'] = [client.members.get(r['id']) or 'falta' for r in rows]
        return verdict(rows, 1, (('id', 'texto'),))

    def received():
        rows = client.list_invitations('received', 20)
        found['received'] = [r['id'] for r in rows] or 'ninguna'
        return verdict(rows, 0, INVITATION)

    def chats():
        rows = client.list_chats(10)
        if rows:
            found['chat'] = rows[0]['id']
        return verdict(rows, 1, CHAT)

    return [
        ('account_status', status),
        ('get_user', user),
        ('own_audience', audience),
        ('profile_views', views),
        ('list_user_posts', posts),
        ('get_post', post),
        ('list_comments', comments),
        ('list_comment_thread', thread),
        ('search_people', people),
        ('search_parameters', lambda: verdict(client.search_parameters('LOCATION', 'Bogota'), 1,
                                              (('id', 'texto'), ('name', 'texto')))),
        ('list_invitations', received),
        ('list_sent_invitations', lambda: verdict(client.list_invitations('sent', 20), 0, INVITATION)),
        ('list_chats', chats),
        ('list_chat_messages', lambda: verdict(client.list_chat_messages(need('chat'), 10), 1, MESSAGE)),
    ]


def drafted(write):
    """A write the client prepared (a Request) or the LinkedInError that stopped it: the Request must pass the
    allowlist as it would leave. It is never sent."""
    if isinstance(write, LinkedInError):
        raise write
    permitidas.check(write)
    return OK, '', 1


def write_steps(client, found):
    """What the writes depend on, after the reads, as (name, call): the same shape as `steps`. One call in all (the
    post page of the comments); everything else comes from what the reads already brought."""
    def need(key):
        if not found.get(key):
            raise Skipped(f'sin dato de una operación anterior ({key})')
        return found[key]

    def comment(operation):
        def check():
            if 'writes' not in found:
                found['writes'] = {}  # one page read for both: if it fails here, the reply says so without reading
                found['writes'] = client.comment_writes(need('comment_post'), found.get('comment') or ANY_COMMENT)
            if operation not in found['writes']:
                raise Skipped('sin la página del post')
            return drafted(found['writes'][operation])
        return check

    def follow():
        members = [need('profile_member')] + list(found.get('search_members') or ())
        if 'falta' in members:
            return BROKEN, 'el perfil o la búsqueda no traen el id de miembro (memberUrn)', 0
        return drafted(client.follow_request(members[0]))

    def accept():
        ids = need('received')
        if ids == 'ninguna':
            raise Skipped('no hay invitaciones recibidas para mirar')
        if not all(i in client.secrets for i in ids):
            return BROKEN, 'las invitaciones recibidas no traen su secreto (sharedSecret)', 0
        return drafted(client.accept_request(ids[0]))

    def by_writing():
        raise Skipped(ONLY_BY_WRITING)

    return [
        ('create_comment', comment('create_comment')),
        ('comment_in_thread', comment('comment_in_thread')),
        ('follow_user', follow),
        ('accept_invitation', accept),
        ('add_reaction', by_writing),
        ('react_to_comment', by_writing),
        ('send_invitation', by_writing),
    ]


def run(transport, out=None, clock=time.time):
    """{resultado, operaciones: [{operacion, estado, motivo, filas, (tipo), (diagnostico)}], llamadas, segundos,
    error}. A write's row has tipo 'escritura'; a row whose LinkedInError carried a detail (a template that did not
    parse, the box fields missing) keeps it as `diagnostico` (counts and field names). `error` is the LinkedInError
    that ended it early ({kind, pausa, motivo}: the service's or our own message, never LinkedIn's data), or None.
    `out` gets one line per row."""
    started, recorder = clock(), Recorder(transport)
    client, found, rows, result, error = Cliente(recorder), {}, [], None, None
    checks = [(name, check, None) for name, check in steps(client, recorder, found)]
    checks += [(name, check, WRITE) for name, check in write_steps(client, found)]
    for name, check, kind in checks:
        row = {'operacion': name, **({'tipo': kind} if kind else {})}
        try:
            row['estado'], row['motivo'], row['filas'] = check()
        except Skipped as exc:
            row.update(estado=UNTRIED, motivo=str(exc))
        except LinkedInError as exc:
            row.update(estado=BROKEN, motivo=str(exc)[:300])
            if isinstance(exc.detail, dict) and exc.detail:
                row['diagnostico'] = exc.detail
            if exc.kind in NOT_RUN_KINDS:
                row['estado'] = result = NOT_RUN
            elif exc.pause or exc.kind in HALT_KINDS:
                row['estado'] = result = HALTED
            if result:
                error = {'kind': exc.kind, 'pausa': exc.pause, 'motivo': str(exc)[:600]}  # keeps what to do
                if exc.since is not None:
                    error['desde'] = exc.since  # another internet exit: since when (team_backend tells it once)
        except Exception as exc:  # an answer so changed that reading it failed: that is what the canary is for
            row.update(estado=BROKEN, motivo=f'respuesta ilegible ({type(exc).__name__})')
        rows.append(row)
        if out:
            done = (' (preparada, sin enviar)' if kind else f' ({row["filas"]} filas)') if row['estado'] == OK else ''
            out(f'{row["estado"]:10} {name}{done}' + (f': {row["motivo"]}' if row.get('motivo') else '')
                + (f' {json.dumps(row["diagnostico"], ensure_ascii=False)}' if row.get('diagnostico') else ''))
        if result:
            break
    result = result or (BROKEN if any(broken(r) for r in rows) else OK)
    return {'resultado': result, 'operaciones': rows, 'llamadas': recorder.calls,
            'segundos': round(clock() - started), 'error': error}
