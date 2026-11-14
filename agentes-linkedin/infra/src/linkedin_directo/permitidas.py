"""What may leave, decided before anything is sent. The client checks every Request here and the navegador service
must run the same check before it calls LinkedIn.

Reads: any Voyager GET, the two pages the client reads (a post and the people search), the two server-driven UI
reads of the search filters and one server-driven UI screen, the analytics export dialog, with its body checked whole
(only two dates). Writes: only the five the connector makes, each with its payload checked, because the same route or
sduiid also undoes, withdraws, ignores or unfollows. A write sent as a read, or anything else, is refused."""
import re
from datetime import date
from urllib.parse import parse_qs, urlsplit

from . import rutas
from .errores import LinkedInError

PAGES = (re.compile(r'/feed/update/urn:li:activity:\d{1,25}/'), re.compile(r'/search/results/people/\?[^#\s]*'))
SDUI_READS = {rutas.FILTER_BAR: 'component', rutas.GEO_TYPEAHEAD: 'server-request'}
SDUI_WRITES = (rutas.REACT, rutas.FOLLOW, rutas.COMMENT)
REACTION_TYPES = {f'ReactionType_{kind}' for kind in rutas.REACTIONS.values()}
ACCEPT = re.compile(re.escape(rutas.VOYAGER) + r'/relationships/invitations/(\d{1,25})\?action=accept')
PROFILE_URN = re.compile(r'urn:li:fsd_profile:[A-Za-z0-9_\-]{2,100}')
DIGITS = re.compile(r'\d{1,25}')
# Screens opened as dialogs. Only the analytics export: opening it draws the dialog and changes nothing.
SCREENS = (rutas.ANALYTICS_SCREEN,)
ISO_DAY = re.compile(r'\d{4}-\d{2}-\d{2}')
ANALYTICS_DAYS = 366  # longest range asked in one export, both ends included (LinkedIn's own longest preset is 365)


def refuse(why):
    raise LinkedInError(f'Bloqueado antes de salir: {why}; no se envió nada.', kind='refused')


def check(request):
    """Raise LinkedInError(kind='refused') for anything outside the list."""
    if request.kind not in ('voyager', 'sdui', 'page') or not request.path.startswith('/') \
            or request.path.startswith('//') or any(c in request.path for c in '\r\n '):
        refuse('petición mal formada')
    if request.kind == 'page':
        if request.method != 'GET' or request.write or request.body is not None \
                or not any(p.fullmatch(request.path) for p in PAGES):
            refuse('página fuera de la lista')
    elif request.kind == 'voyager':
        if request.method == 'GET' and not request.write and request.body is None:
            if not request.path.startswith(rutas.VOYAGER + '/'):
                refuse('lectura fuera de Voyager')
            return
        if request.method != 'POST' or not request.write or not isinstance(request.body, dict):
            refuse('escritura Voyager fuera de la lista')
        if request.path == rutas.voyager(rutas.INVITE):
            invitation(request.body)
        elif ACCEPT.fullmatch(request.path):
            acceptance(ACCEPT.fullmatch(request.path).group(1), request.body)
        else:
            refuse('escritura Voyager fuera de la lista')
    else:
        sdui(request)


def sdui(request):
    parts = urlsplit(request.path)
    kind = parts.path[len(rutas.SDUI):] if parts.path.startswith(rutas.SDUI) else ''
    ids = parse_qs(parts.query).get('sduiid') or []
    sduiid = ids[0] if len(ids) == 1 else ''
    body = request.body if isinstance(request.body, dict) else {}
    if kind == 'navigation':
        return screen(request, sduiid, body)
    if request.method != 'POST' or kind not in ('server-request', 'component') or request.path != rutas.sdui(sduiid, kind):
        refuse('ruta de la UI del servidor mal formada')
    if sduiid in SDUI_READS:
        if request.write or SDUI_READS[sduiid] != kind:
            refuse('lectura de la UI del servidor mal marcada')
        return
    if sduiid not in SDUI_WRITES or not request.write or kind != 'server-request' or body.get('requestId') != sduiid:
        refuse('acción de la UI del servidor fuera de la lista')
    payload = (body.get('requestedArguments') or {}).get('payload')
    if not isinstance(payload, dict):
        refuse('acción sin payload')
    if sduiid == rutas.REACT:
        reaction(payload)
    elif sduiid == rutas.FOLLOW:
        follow(payload)
    else:
        comment(body, payload)


def screen(request, sduiid, body):
    """The analytics export dialog, a read: the exact route, the exact body and two ISO dates in order, at most
    ANALYTICS_DAYS apart. Anything more in the body is refused: the same route opens other screens."""
    if request.method != 'POST' or request.write or sduiid not in SCREENS or request.path != rutas.navigation(sduiid):
        refuse('pantalla de la UI del servidor fuera de la lista')
    args = body.get('clientArguments') if isinstance(body.get('clientArguments'), dict) else {}
    payload = args.get('payload') if isinstance(args.get('payload'), dict) else {}
    expected = rutas.analytics_export(payload.get('startDate'), payload.get('endDate'))
    if body != expected or set(payload) != {'startDate', 'endDate'}:
        refuse('exportación de analítica con un cuerpo fuera de la lista')
    try:
        start, end = (date.fromisoformat(payload[k]) for k in ('startDate', 'endDate')
                      if isinstance(payload[k], str) and ISO_DAY.fullmatch(payload[k]))
    except ValueError:
        refuse('exportación de analítica sin dos fechas ISO')
    if not start <= end or (end - start).days + 1 > ANALYTICS_DAYS:
        refuse(f'exportación de analítica con un rango invertido o de más de {ANALYTICS_DAYS} días')


def follow(payload):
    member = payload.get('memberUrn') if isinstance(payload.get('memberUrn'), dict) else {}
    if set(payload) != {'followStateType', 'memberUrn'} or payload['followStateType'] != 'FollowStateType_FOLLOW_ACTIVE' \
            or set(member) != {'memberId'} or not DIGITS.fullmatch(str(member['memberId'])):
        refuse('seguir solo admite FOLLOW_ACTIVE de un miembro')


def reaction(payload):
    thread = payload.get('threadUrn') if isinstance(payload.get('threadUrn'), dict) else {}
    target = {'Update': 'threadUrnActivityThreadUrn', 'Comment': 'threadUrnCommentThreadUrn'}.get(payload.get('reactionSource'))
    if set(payload) != {'threadUrn', 'reactionType', 'reactionSource'} or payload['reactionType'] not in REACTION_TYPES \
            or not target or set(thread) != {target}:
        refuse('reacción fuera de la lista')


def comment(body, payload):
    """A createComment from the post page's template, with the text in the box's plain field and no mention anywhere
    (the web pre-fills one of the parent's author in a reply box; Barrio never sends it)."""
    server = body.get('serverRequest') if isinstance(body.get('serverRequest'), dict) else {}
    binding = (payload.get('commentFieldBinding') or {}).get('key') if isinstance(payload.get('commentFieldBinding'), dict) else None
    texts = [s.get('value') for s in body.get('states') or [] if isinstance(s, dict) and s.get('key') == binding
             and s.get('originalProtoCase') == 'stringValue']
    if server.get('requestId') != rutas.COMMENT or not isinstance(payload.get('collection'), dict) or not binding \
            or not any(isinstance(t, str) and t.strip() for t in texts):
        refuse('comentario sin plantilla de la página o sin texto')
    if rutas.has_mention(body):
        refuse('comentario con una mención')


def invitation(body):
    note = body.get('customMessage')
    if not set(body) <= {'invitee', 'customMessage'} \
            or not isinstance(body.get('invitee'), dict) or set(body['invitee']) != {'inviteeUnion'} \
            or not isinstance(body['invitee']['inviteeUnion'], dict) or set(body['invitee']['inviteeUnion']) != {'memberProfile'} \
            or not PROFILE_URN.fullmatch(str(body['invitee']['inviteeUnion']['memberProfile'])) \
            or ('customMessage' in body and not (isinstance(note, str) and 0 < len(note) <= rutas.NOTE_LIMIT)):
        refuse('invitación fuera de la lista')


def acceptance(invitation_id, body):
    if set(body) != {'invitationId', 'invitationSharedSecret', 'isGenericInvitation'} \
            or body['invitationId'] != invitation_id or body['isGenericInvitation'] is not False \
            or not isinstance(body['invitationSharedSecret'], str) or not body['invitationSharedSecret']:
        refuse('aceptación fuera de la lista')
