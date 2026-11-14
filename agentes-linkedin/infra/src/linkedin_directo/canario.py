"""The daily canary, ported from spikes/linkedin-directo/canario.py: the connector's 14 reads, once and READ-ONLY (16
calls to LinkedIn), checking that each answer still gives the fields Barrio's callers use. LinkedIn renames things
without warning and an HTTP 200 with a field gone is a silent break.

It runs over any Transport: the backend's daily job sends it through the account's connector (team_backend/canario.py)
and `python -m navegador canario` through the running service, so its calls pass the service's budgets and stops like
any other. It reads only the account's own profile, posts and inbox, and the comments of the busiest post its feed
brings along, like the spike. The report keeps states, row counts and field names, never a value (no names, texts or
ids).

Result: 'ok' every read gave its fields; 'roto' something broke (LinkedIn changed an answer); 'alto' LinkedIn pushed
back or the service has the account stopped or without a session (do not retry: someone has to look); 'no_corrio' it
could not run (the service unreachable, busy or out of budget, another internet exit, its configuration): nothing to
judge."""
import json
import time
from datetime import datetime

from . import lectura, rutas
from .cliente import Cliente
from .errores import LinkedInError
from .transporte import Transport

OK, BROKEN, HALTED, NOT_RUN = 'ok', 'roto', 'alto', 'no_corrio'
# Nothing reached LinkedIn, or nothing came back: the run says nothing about LinkedIn and stops there.
NOT_RUN_KINDS = ('config', 'disabled', 'not_sent', 'budget', 'network', 'egress')
HALT_KINDS = ('stopped', 'login')


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
    return isinstance(value, str) and bool(value.strip())  # texto


def lacking(rows, fields):
    """Fields no row carries with the right kind: one row with it is enough (a post may have no text), but a field no
    row has any more is a rename."""
    return [path for path, kind in fields if not any(holds(dig(row, path), kind) for row in rows)]


PERSON = (('id', 'texto'), ('public_identifier', 'texto'), ('display_name', 'texto'))
POST = (('id', 'texto'), ('created_at', 'fecha'), ('author.id', 'texto'), ('reactions_counter', 'num'),
        ('comments_counter', 'num'))
COMMENT = (('id', 'texto'), ('text', 'texto'), ('created_at', 'fecha'), ('author.display_name', 'texto'))
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
        return verdict(rows, 1, POST + (('impressions', 'num'),))

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

    def chats():
        rows = client.list_chats(10)
        if rows:
            found['chat'] = rows[0]['id']
        return verdict(rows, 1, CHAT)

    return [
        ('account_status', status),
        ('get_user', lambda: verdict([client.get_user('me')], 1, PERSON)),
        ('own_audience', audience),
        ('profile_views', views),
        ('list_user_posts', posts),
        ('get_post', post),
        ('list_comments', comments),
        ('list_comment_thread', thread),
        ('search_people', lambda: verdict(client.search_people('founder'), 1, (('id', 'texto'),))),
        ('search_parameters', lambda: verdict(client.search_parameters('LOCATION', 'Bogota'), 1,
                                              (('id', 'texto'), ('name', 'texto')))),
        ('list_invitations', lambda: verdict(client.list_invitations('received', 20), 0, INVITATION)),
        ('list_sent_invitations', lambda: verdict(client.list_invitations('sent', 20), 0, INVITATION)),
        ('list_chats', chats),
        ('list_chat_messages', lambda: verdict(client.list_chat_messages(need('chat'), 10), 1, MESSAGE)),
    ]


def run(transport, out=None, clock=time.time):
    """{resultado, operaciones: [{operacion, estado, motivo, filas}], llamadas, segundos, error}. `error` is the
    LinkedInError that ended it early ({kind, pausa, motivo}: the service's or our own message, never LinkedIn's
    data), or None. `out` gets one line per read."""
    started, recorder = clock(), Recorder(transport)
    client, found, rows, result, error = Cliente(recorder), {}, [], None, None
    for name, check in steps(client, recorder, found):
        row = {'operacion': name}
        try:
            row['estado'], row['motivo'], row['filas'] = check()
        except Skipped as exc:
            row.update(estado='sin_probar', motivo=str(exc))
        except LinkedInError as exc:
            row.update(estado=BROKEN, motivo=str(exc)[:300])
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
            out(f'{row["estado"]:10} {name}' + (f' ({row["filas"]} filas)' if row['estado'] == OK else '')
                + (f': {row["motivo"]}' if row.get('motivo') else ''))
        if result:
            break
    result = result or (OK if all(r['estado'] == OK for r in rows) else BROKEN)
    return {'resultado': result, 'operaciones': rows, 'llamadas': recorder.calls,
            'segundos': round(clock() - started), 'error': error}
