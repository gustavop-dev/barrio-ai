"""The daily canary, ported from spikes/linkedin-directo/canario.py: the connector's 14 reads, once and READ-ONLY,
through the running service exactly as the backend calls it (linkedin_directo's Cliente over ServiceTransport), checking
that each answer still gives the fields Barrio's callers use. LinkedIn renames things without warning and an HTTP 200
with a field gone is a silent break.

    python -m navegador canario <cuenta> [--url http://127.0.0.1:8790]

One line per operation (ok / roto / sin_probar, and why) and <datos>/canario/canario-<cuenta>-<fecha>.json with states,
counts and field names, never values (no names, texts or ids). Exit code: 0 all ok; 2 something broke; 3 hard stop
(the account is stopped, has no session, or LinkedIn pushed back: do not retry, look at it by hand); 4 it did not run
(the service is not reachable, the token is wrong or the account is unknown). It reads only the account's own profile,
posts and inbox, and the comments of the busiest post its feed brings along, like the spike."""
import json
import sys
import time
from datetime import datetime

from linkedin_directo import Cliente, LinkedInError, lectura, rutas
from linkedin_directo.servicio import ServiceTransport

OK, BROKEN, HALTED, NOT_RUN = 0, 2, 3, 4
NOT_RUN_KINDS = ('config', 'not_sent')
HALT_KINDS = ('stopped', 'login')


class Recorder(ServiceTransport):
    """Keeps the last answer's text: the busiest feed post and comment are picked from LinkedIn's own counters, as
    the spike did, without printing them."""
    last = ''

    def send(self, request):
        answer = super().send(request)
        self.last = answer.text
        return answer

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
        return 'roto', f'{len(rows)} filas (se esperaba al menos {least})', len(rows)
    missing = lacking(rows, fields) if rows else []
    return ('roto', 'faltan campos: ' + ', '.join(missing), len(rows)) if missing else ('ok', '', len(rows))


def steps(client, recorder, found):
    """The 14 reads in order, as (name, call -> (state, reason, rows)). Each fills `found` with what later ones
    need; LookupError means an earlier step found nothing to read here."""
    def need(key):
        if not found.get(key):
            raise LookupError(f'sin dato de una operación anterior ({key})')
        return found[key]

    def status():
        out = client.account_status()
        return ('ok', '', 1) if out.get('status') == 'running' else ('roto', 'estado inesperado', 1)

    def audience():
        out = client.own_audience()
        return verdict([out], 1, (('followers', 'num'), ('connections', 'num')))

    def views():
        out = client.profile_views(rutas.VIEWS_DAYS)
        return ('ok', '', 1) if holds(out, 'num') else ('roto', 'sin número de visitas', 0)

    def posts():
        rows = client.list_user_posts('me', 5)
        if rows:
            found['post'] = rows[0]['id']
        return verdict(rows, 1, POST + (('impressions', 'num'),))

    def post():
        out = client.get_post(need('post'))
        found['busy_post'] = recorder.busiest('activity', skip=found['post'])
        if out.get('id') != found['post']:
            return 'roto', 'no es la publicación pedida', 1
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


def run(url, token, account, data_dir, out=print):
    started = time.time()
    report = {'fecha': time.strftime('%Y-%m-%d'), 'hora': time.strftime('%H:%M:%S'), 'cuenta': account}
    recorder = Recorder(url, token, account)
    client, found, results, code = Cliente(recorder), {}, [], None
    for name, check in steps(client, recorder, found):
        row = {'operacion': name}
        try:
            row['estado'], row['motivo'], row['filas'] = check()
        except LookupError as exc:
            row.update(estado='sin_probar', motivo=str(exc))
        except LinkedInError as exc:
            row.update(estado='roto', motivo=str(exc)[:200])
            if exc.pause or exc.kind in HALT_KINDS:
                row['estado'], code = 'alto', HALTED
            elif exc.kind in NOT_RUN_KINDS and not results:
                code = NOT_RUN
        results.append(row)
        out(f'{row["estado"]:10} {name}' + (f' ({row["filas"]} filas)' if row['estado'] == 'ok' else '')
            + (f': {row["motivo"]}' if row.get('motivo') else ''))
        if code is not None:
            break
    if code is None:
        code = OK if all(r['estado'] == 'ok' for r in results) else BROKEN
    report.update(operaciones=results, segundos=round(time.time() - started), codigo=code,
                  resultado={OK: 'ok', BROKEN: 'roto', HALTED: 'alto', NOT_RUN: 'no_corrio'}[code])
    folder = data_dir / 'canario'
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = folder / f'canario-{account}-{report["fecha"]}.json'
    path.write_text(json.dumps(report, ensure_ascii=False, indent=1))
    out(f'canario: {report["resultado"]} ({report["segundos"]} s) -> {path}')
    if code == HALTED:
        out('DETENIDO: no reintentar; revisar a mano (python -m navegador estado).')
    return code


if __name__ == '__main__':
    sys.exit('Uso: python -m navegador canario <cuenta>')
