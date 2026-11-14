"""What the service keeps per account on disk, under <datos>/cuentas/<cuenta>/ (the data volume), so that a restart
forgets nothing that guards LinkedIn:

- perfil/        the Chromium profile. The LinkedIn session lives here and never leaves it.
- detenida.json  present = the account is stopped (LinkedIn pushed back). Only an operator removes it (`reanudar`).
- consumo.json   when each call left, over the last 24 h, per budget ('read', 'write' and each kind of write): the
                 budgets count from it.
- salida.json    the internet exit the session last went out by: a label (ajustes.Egress.label), never an address or
                 a credential. A different one is refused until an operator accepts it (`salida <cuenta> --aceptar`).
- salida-rechazada.json  since when that refusal lasts (only a time): the backend tells the owner once per episode. Gone
                 once the account opens by its exit again or an operator accepts the new one.
- escrituras/    one file per write's request_id: LinkedIn's answer, or `sending` while it is out (and forever if the
                 process died mid-send). A repeated id gets the stored answer back, never a second send.

Files are replaced atomically (temp file + rename) and only the service's user can read them."""
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

DAY = 86400
IMPORTED = 'otro-equipo'  # the egress of a profile copied from another machine: unknown, so never this one
KEEP_WRITES = 7 * DAY
KEEP_TEXT = 256 * 1024  # a stored answer longer than this is cut: enough for any write's answer


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    tmp = path.with_name(f'.{path.name}.{os.getpid()}.tmp')
    with open(tmp, 'w', encoding='utf-8') as handle:
        json.dump(data, handle, ensure_ascii=False)
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def read_json(path):
    try:
        return json.loads(Path(path).read_text('utf-8'))
    except FileNotFoundError:
        return None
    except (ValueError, OSError):
        return {}  # unreadable: present but empty, so a stop flag still stops


def stamp(now):
    return datetime.fromtimestamp(now, tz=timezone.utc).isoformat(timespec='seconds')


class Store:
    def __init__(self, root):
        self.root = Path(root)
        self.profile = self.root / 'perfil'
        self._usage = None

    def exists(self):
        return self.profile.is_dir()

    # --- the stop flag: read from disk every time, so an operator's `reanudar` counts at once ----------------------
    def stopped(self):
        data = read_json(self.root / 'detenida.json')
        if data is None:
            return None
        return data if isinstance(data, dict) and data else {'motivo': 'archivo de parada ilegible', 'desde': ''}

    def stop(self, reason, now=None):
        if not self.stopped():
            write_json(self.root / 'detenida.json', {'motivo': str(reason)[:300], 'desde': stamp(now or time.time())})

    def resume(self):
        """Clear the stop; returns what it said, or None when the account was not stopped."""
        was = self.stopped()
        (self.root / 'detenida.json').unlink(missing_ok=True)
        return was

    # --- budgets: the moments calls left, per budget ('read', 'write', or a kind of write such as 'comment') ---------
    def usage(self, kind, now):
        if self._usage is None:
            data = read_json(self.root / 'consumo.json')
            data = data if isinstance(data, dict) else {}
            self._usage = {k: [t for t in v if isinstance(t, (int, float))] for k, v in data.items() if isinstance(v, list)}
        self._usage[kind] = [t for t in self._usage.get(kind) or [] if now - t < DAY]
        return list(self._usage[kind])

    def count(self, kinds, now):
        """One call left now: it counts in each of `kinds` (a write in 'write' and in its own kind), in one file write."""
        for kind in (kinds,) if isinstance(kinds, str) else kinds:
            self.usage(kind, now)
            self._usage[kind].append(now)
        write_json(self.root / 'consumo.json', self._usage)

    # --- the internet exit: a session that hops between IPs is LinkedIn's first reason to end it ----------------------
    def egress(self):
        """The label the account last went out by; None when it never went out from here; '?' when unreadable."""
        data = read_json(self.root / 'salida.json')
        if data is None:
            return None
        return data['salida'] if isinstance(data, dict) and isinstance(data.get('salida'), str) else '?'

    def set_egress(self, label, now=None):
        write_json(self.root / 'salida.json', {'salida': str(label), 'desde': stamp(now or time.time())})
        self.egress_matches()

    def egress_refused(self, now):
        """When the refusal of another exit began: kept from the first refused call, so every refusal of one episode
        carries the same moment and the backend says it once."""
        data = read_json(self.root / 'salida-rechazada.json')
        if isinstance(data, dict) and isinstance(data.get('desde'), str) and data['desde']:
            return data['desde']
        since = stamp(now)
        write_json(self.root / 'salida-rechazada.json', {'desde': since})
        return since

    def egress_matches(self):
        """The episode is over: the configured exit is the session's again (accepted, or put back)."""
        (self.root / 'salida-rechazada.json').unlink(missing_ok=True)

    # --- writes by request_id ----------------------------------------------------------------------------------------
    def _write_path(self, request_id):
        return self.root / 'escrituras' / f'{request_id}.json'

    def write_record(self, request_id):
        """{'state': 'sending'|'answered', 'answer': {...}} of a write already sent with this id, or None."""
        data = read_json(self._write_path(request_id))
        if data is None:
            return None
        return data if isinstance(data, dict) and data.get('state') else {'state': 'sending'}

    def sending(self, request_id, now):
        write_json(self._write_path(request_id), {'state': 'sending', 'at': now})

    def answered(self, request_id, answer, now):
        kept = {**answer, 'text': (answer.get('text') or '')[:KEEP_TEXT]}
        write_json(self._write_path(request_id), {'state': 'answered', 'at': now, 'answer': kept})

    def prune_writes(self, now):
        folder = self.root / 'escrituras'
        for path in folder.glob('*.json') if folder.is_dir() else ():
            try:
                if now - path.stat().st_mtime > KEEP_WRITES:
                    path.unlink()
            except OSError:
                pass
