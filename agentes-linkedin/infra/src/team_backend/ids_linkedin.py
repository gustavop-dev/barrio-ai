"""LinkedIn ids as Unipile stores them and as LinkedIn directo does (linkedin_directo/lectura.py), and the translation
between the two for a provider switch (proveedor.py). Pure: no database, no network.

Unipile's shapes were read from the production database on 2026-11-14 (shapes only, never values):
- person: the profile id `ACo…`, the same for both;
- post: base64 of a JSON list of LinkedIn urns: `["activity:<n>"]`, `["activity:<n>","ugcPost:<m>"]` or
  `["activity:<a>","activity:<b>"]`; directo's id is the activity number;
- comment: LinkedIn's comment number, the same for both;
- invitation: `SENT_<n>`, or `RECEIVED_<n>_<shared secret>`; directo's id is the number (it reads the secret from the
  received list before accepting);
- chat: `CLASSIC_<thread id>`; directo's id is the thread id `2-…`.

A post with two activities: LinkedIn's activity numbers grow with time (`n >> 22` is the creation time in ms), and a
repost is a later activity than the post it shares. Directo ids a repost in a person's activity list by its own update
urn, the reposting activity, so the later number is the one directo returns for that same row.

Strict both ways: a value of any other shape raises Untranslatable, never a guess. Message ids are not here: nothing
ties Unipile's to LinkedIn's (conversaciones.carry handles them)."""
import base64
import binascii
import json
import re

KINDS = ('person', 'post', 'comment', 'invitation', 'chat')
PERSON = re.compile(r'ACo[A-Za-z0-9_\-]{1,100}')
NUMBER = re.compile(r'\d{1,25}')  # directo's post, comment and invitation ids (linkedin_directo/rutas.py)
URN = re.compile(r'(activity|ugcPost):(\d{1,25})')
SENT = re.compile(r'SENT_(\d{1,25})')
RECEIVED = re.compile(r'RECEIVED_(\d{1,25})_([A-Za-z0-9_\-]{8})')
THREAD = re.compile(r'2-[A-Za-z0-9_=+/\-]{1,200}')  # as linkedin_directo/rutas.THREAD
CLASSIC = 'CLASSIC_'
DIRECTIONS = ('sent', 'received')


class Untranslatable(ValueError):
    """A value whose shape is not one of the known ones for that kind and provider."""


def _fail(kind, provider):
    raise Untranslatable(f'{kind}: forma desconocida para {provider}')


def post_urns(value):
    """The (type, number) pairs inside a Unipile post id, or Untranslatable."""
    try:
        decoded = json.loads(base64.b64decode(str(value), validate=True).decode())
    except (binascii.Error, ValueError, UnicodeDecodeError):
        _fail('post', 'unipile')
    if not isinstance(decoded, list) or not 1 <= len(decoded) <= 2 or not all(isinstance(u, str) for u in decoded):
        _fail('post', 'unipile')
    urns = [URN.fullmatch(u) for u in decoded]
    if not all(urns):
        _fail('post', 'unipile')
    return [(m.group(1), m.group(2)) for m in urns]


def _activity(value):
    pairs = post_urns(value)
    activities = [n for kind, n in pairs if kind == 'activity']
    if not activities or (len(pairs) == 2 and pairs[0] == pairs[1]):
        _fail('post', 'unipile')
    return max(activities, key=int)  # one activity, or a repost and the post it shares: the later one (module doc)


def to_directo(kind, value):
    """The directo id of a value Unipile stored."""
    value = str(value)
    if kind == 'person':
        if not PERSON.fullmatch(value):
            _fail(kind, 'unipile')
        return value
    if kind == 'comment':
        if not NUMBER.fullmatch(value):
            _fail(kind, 'unipile')
        return value
    if kind == 'post':
        return _activity(value)
    if kind == 'invitation':
        found = SENT.fullmatch(value) or RECEIVED.fullmatch(value)
        if not found:
            _fail(kind, 'unipile')
        return found.group(1)
    if kind == 'chat':
        if not value.startswith(CLASSIC) or not THREAD.fullmatch(value[len(CLASSIC):]):
            _fail(kind, 'unipile')
        return value[len(CLASSIC):]
    raise ValueError(f'Tipo de id desconocido: {kind}')


def to_unipile(kind, value, direction='', secret=''):
    """The Unipile id of a value directo stored. An invitation needs its direction, and a received one its shared
    secret (only the original Unipile value has it). A post gets the single-activity form."""
    value = str(value)
    if kind == 'person':
        if not PERSON.fullmatch(value):
            _fail(kind, 'directo')
        return value
    if kind == 'comment':
        if not NUMBER.fullmatch(value):
            _fail(kind, 'directo')
        return value
    if kind == 'post':
        if not NUMBER.fullmatch(value):
            _fail(kind, 'directo')
        return base64.b64encode(json.dumps([f'activity:{value}'], separators=(',', ':')).encode()).decode()
    if kind == 'invitation':
        if not NUMBER.fullmatch(value) or direction not in DIRECTIONS:
            _fail(kind, 'directo')
        if direction == 'sent':
            return f'SENT_{value}'
        if not re.fullmatch(r'[A-Za-z0-9_\-]{8}', secret or ''):
            raise Untranslatable('invitation: una invitación recibida necesita su secreto, que solo guarda Unipile')
        return f'RECEIVED_{value}_{secret}'
    if kind == 'chat':
        if not THREAD.fullmatch(value):
            _fail(kind, 'directo')
        return CLASSIC + value
    raise ValueError(f'Tipo de id desconocido: {kind}')


def translate(kind, value, to, **context):
    """`value` as the provider `to` stores it ('directo' or 'unipile')."""
    if to == 'directo':
        return to_directo(kind, value)
    if to == 'unipile':
        return to_unipile(kind, value, **context)
    raise ValueError(f'Proveedor desconocido: {to}')


def shape(value):
    """A value's shape for reports, never the id: a known prefix, then digits as 9 and letters as x."""
    value = str(value)
    prefix = next((p for p in ('RECEIVED_', 'SENT_', 'CLASSIC_2-', '2-', 'ACo') if value.startswith(p)), '')
    return (prefix + re.sub(r'[A-Za-z]', 'x', re.sub(r'\d', '9', value[len(prefix):])))[:60]
