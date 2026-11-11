#!/usr/bin/env python3
"""Measured seconds of each Maestro flow, so scripts/qa/plan.py splits the flows evenly across the emulators.

The committed duraciones.json is the fallback. Every run on main uploads a fresh copy as the artifact `qa-duraciones`
(the seconds of the flows that passed there, over the committed ones), and the plan job of the next run uses it.

  duraciones.py actualizar <qa-artefactos> <salida.json>
"""
import json
import os
import sys
from pathlib import Path

BASE = Path(__file__).with_name('duraciones.json')


def load(path=None):
    """{flow: seconds} from `path` (the artifact from main) or the committed file; {} if neither is readable."""
    for candidate in (path, BASE):
        if not candidate or not Path(candidate).is_file():
            continue
        try:
            data = json.loads(Path(candidate).read_text())
            seconds = {str(name): int(value) for name, value in data['segundos'].items() if int(value) > 0}
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            continue
        if seconds:
            return seconds
    return {}


def measured(out):
    """Seconds of the flows that passed in this run (flujos-N.txt: «name code seconds [attempts]»)."""
    found = {}
    for path in sorted(Path(out).glob('flujos*.txt')):
        for line in path.read_text().splitlines():
            parts = line.split()
            if len(parts) >= 3 and parts[1] == '0' and parts[2].isdigit() and int(parts[2]) > 0:
                found[parts[0]] = int(parts[2])
    return found


def main():
    if len(sys.argv) != 4 or sys.argv[1] != 'actualizar':
        sys.exit(__doc__)
    seconds = load()
    fresh = measured(sys.argv[2])
    seconds.update(fresh)
    origin = os.environ.get('QA_DURACIONES_ORIGEN', '').strip() or 'ejecución en main'
    out = Path(sys.argv[3])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({'origen': origin, 'segundos': dict(sorted(seconds.items()))}, indent=1, ensure_ascii=False) + '\n')
    print(f'duraciones: {len(fresh)} medidas en esta ejecución, {len(seconds)} en total')


if __name__ == '__main__':
    main()
