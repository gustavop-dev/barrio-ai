"""QA-only failure switch (movil/.maestro/README.md, «Fallos simulados»): makes chosen endpoints answer 5xx, 413 or 429,
time out, go slow or come back empty, so the mobile app's error and empty states can be tested on the emulator.

It exists only under linkedin_backend.settings_qa (QA_MODE=true): production settings never list the middleware or the
control endpoint, and the middleware refuses to load unless settings.QA_MODE is True (team_backend.tests.test_qa_fallos).

Rules live in a JSON file (settings.QA_FAULTS_FILE) shared by every gunicorn worker. Each rule:
    {"ruta": "^/api/v1/capturas$", "metodo": "POST", "efecto": "500", "veces": 1, "segundos": 30}
- ruta: regex searched in the request path (required); metodo: an HTTP method or "*" (default "*");
- efecto: "500" | "502" | "503" | "504" | "413" | "429" | "timeout" (waits `segundos`, then 504) |
  "lento" (waits `segundos`, then answers normally) | "vacio" (normal answer with its lists emptied and counters at 0);
- veces: how many requests it hits before it is spent (default 1; -1 = until cleared); segundos: default 30 / 5.
A request may also carry `X-QA-Fallo: <efecto>` (used by curl and the backend tests).

Control (QA URLconf only, linkedin_backend.urls_qa): GET /api/v1/qa/fallos lists the rules, POST adds one rule or a
list of them, DELETE clears them all."""
import fcntl
import json
import re
import time
import uuid
from pathlib import Path
from django.conf import settings
from django.core.exceptions import MiddlewareNotUsed
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

STATUS_EFFECTS = {'500', '502', '503', '504', '413', '429'}
EFFECTS = STATUS_EFFECTS | {'timeout', 'lento', 'vacio'}
DEFAULT_SECONDS = {'timeout': 30, 'lento': 5}
MAX_SECONDS = 110  # below gunicorn's --timeout 120 in the QA workflow
COUNTERS = {'count', 'unread', 'urgent_count', 'total'}
CONTROL_PATH = '/api/v1/qa/fallos'


def active():
    return getattr(settings, 'QA_MODE', False) is True


def _path():
    return Path(getattr(settings, 'QA_FAULTS_FILE', '/tmp/qa-fallos.json'))


def _locked(update):
    """Reads the rules under an exclusive lock, lets `update` change them, writes them back; returns its result."""
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'a+') as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        fh.seek(0)
        raw = fh.read().strip()
        try:
            rules = json.loads(raw) if raw else []
        except json.JSONDecodeError:
            rules = []
        result = update(rules)
        fh.seek(0)
        fh.truncate()
        fh.write(json.dumps(rules))
        return result


def clean(rule):
    """A validated rule, or ValueError."""
    if not isinstance(rule, dict):
        raise ValueError('Cada regla es un objeto')
    effect = str(rule.get('efecto', '')).strip().lower()
    if effect not in EFFECTS:
        raise ValueError(f'efecto debe ser uno de {", ".join(sorted(EFFECTS))}')
    route = str(rule.get('ruta', '')).strip()
    if not route:
        raise ValueError('Falta ruta (una expresión regular sobre el path)')
    re.compile(route)
    method = str(rule.get('metodo', '*')).strip().upper() or '*'
    times = int(rule.get('veces', 1))
    seconds = min(MAX_SECONDS, max(0, float(rule.get('segundos', DEFAULT_SECONDS.get(effect, 0)))))
    return {'id': uuid.uuid4().hex[:8], 'ruta': route, 'metodo': method, 'efecto': effect, 'veces': times, 'segundos': seconds}


def add(rules):
    cleaned = [clean(r) for r in (rules if isinstance(rules, list) else [rules])]
    _locked(lambda current: current.extend(cleaned))
    return cleaned


def clear():
    _locked(lambda current: current.clear())


def listed():
    return _locked(lambda current: list(current))


def take(method, path):
    """The first rule matching the request, spending one of its uses; None when nothing matches."""
    def pick(rules):
        for rule in rules:
            if rule['metodo'] not in ('*', method) or not re.search(rule['ruta'], path):
                continue
            if rule['veces'] > 0:
                rule['veces'] -= 1
            hit = dict(rule)
            if rule['veces'] == 0:
                rules.remove(rule)
            return hit
        return None
    if not _path().exists():
        return None
    return _locked(pick)


def emptied(value, depth=0):
    """The same JSON shape with no data: lists empty, counters 0, the «top» card gone."""
    if isinstance(value, list):
        return []
    if isinstance(value, dict) and depth < 2:
        out = {}
        for key, item in value.items():
            if isinstance(item, list):
                out[key] = []
            elif key in COUNTERS and isinstance(item, (int, float)) and not isinstance(item, bool):
                out[key] = 0
            elif key == 'top':
                out[key] = None
            elif isinstance(item, dict):
                out[key] = emptied(item, depth + 1)
            else:
                out[key] = item
        return out
    return value


class QaFaultMiddleware:
    """Applies the armed rules (or an X-QA-Fallo header). Never loads outside QA_MODE."""

    def __init__(self, get_response):
        if not active():
            raise MiddlewareNotUsed('Interruptor de fallos de QA: solo con QA_MODE')
        self.get_response = get_response

    def __call__(self, request):
        if request.path == CONTROL_PATH:
            return self.get_response(request)
        header = request.headers.get('X-QA-Fallo', '').strip().lower()
        rule = {'efecto': header, 'segundos': DEFAULT_SECONDS.get(header, 0)} if header in EFFECTS else take(request.method, request.path)
        if rule is None:
            return self.get_response(request)
        effect = rule['efecto']
        if effect in STATUS_EFFECTS:
            return JsonResponse({'detail': f'Fallo simulado por QA ({effect}).'}, status=int(effect))
        if effect == 'timeout':
            time.sleep(rule['segundos'])
            return JsonResponse({'detail': 'Tiempo de espera simulado por QA.'}, status=504)
        if effect == 'lento':
            time.sleep(rule['segundos'])
            return self.get_response(request)
        response = self.get_response(request)
        if response.get('Content-Type', '').startswith('application/json') and 200 <= response.status_code < 300:
            try:
                data = json.loads(response.content)
            except ValueError:
                return response
            response.content = json.dumps(emptied(data)).encode()
            response['Content-Length'] = str(len(response.content))
        return response


@csrf_exempt
def control(request):
    """GET lists, POST adds (a rule or a list), DELETE clears. Only routed by linkedin_backend.urls_qa."""
    if not active():
        return JsonResponse({'detail': 'No encontrado.'}, status=404)
    if request.method == 'GET':
        return JsonResponse({'reglas': listed()})
    if request.method == 'DELETE':
        clear()
        return JsonResponse({'reglas': []})
    if request.method == 'POST':
        try:
            body = json.loads(request.body or b'null')
            added = add(body)
        except (ValueError, TypeError, re.error) as exc:
            return JsonResponse({'detail': str(exc)}, status=400)
        return JsonResponse({'reglas': added}, status=201)
    return JsonResponse({'detail': 'Método no permitido.'}, status=405)
