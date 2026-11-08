#!/usr/bin/env python3
"""Which Maestro flows a QA run executes and how they are split across the emulator jobs (.github/workflows/qa-movil.yml).

Selection, first match wins:
  1. QA_SELECCION (the `flujos` input of a manual run);
  2. the last `[qa: …]` in QA_MENSAJE (the message of the PR's head commit), e.g. `[qa: 05-captura 09]`;
  3. changed PR paths from QA_CHANGED_FILES, using seleccion.json and the flows' # cubre: headers;
  4. every flow (always on pushes and schedules).
Tokens are separated by spaces or commas; a token selects the flows whose name equals it, starts with it or contains it
(`05`, `05-captura`, `captura`). `todo` or `todos` selects everything.

The selected flows are split into at most QA_MAX_SHARDS jobs, longest first onto the lightest job (by the flow's number
of lines, a fair proxy of its duration). Inside a job the flows keep their numeric order.
Writes `ejecutar`, `matriz` (the JSON matrix) and `resumen` to $GITHUB_OUTPUT, or prints them.
"""
import json
import os
import re
import sys
from pathlib import Path
from fnmatch import fnmatchcase

from cobertura import flow_covers

FLOWS = Path(__file__).resolve().parents[2] / 'movil' / '.maestro'
TAG = re.compile(r'\[qa:\s*([^\]]*)\]', re.I)
RULES = Path(__file__).with_name('seleccion.json')


def available():
    return sorted(p.stem for p in FLOWS.glob('[0-9][0-9]-*.yaml'))


def tokens():
    raw = os.environ.get('QA_SELECCION', '').strip()
    if not raw:
        found = TAG.findall(os.environ.get('QA_MENSAJE', ''))
        raw = found[-1].strip() if found else ''
    return [t for t in re.split(r'[\s,]+', raw) if t]


def select(names, wanted):
    if not wanted or any(t.lower() in ('todo', 'todos', 'all') for t in wanted):
        return names, 'todos los flujos'
    chosen = [n for n in names if any(n == t or n.startswith(t) or t in n for t in wanted)]
    if not chosen:
        sys.exit(f'Ningún flujo coincide con: {" ".join(wanted)} (hay: {" ".join(names)})')
    return chosen, f'solo {" ".join(chosen)} (pedido: {" ".join(wanted)})'


def automatic(names, changes_file):
    """Fail open to the full suite on missing/truncated input or any unrecognised path.

    Input is gh api --paginate --slurp pulls/N/files: one array per page. Include old
    names of renames, so moving code out of an area still exercises that area.
    """
    try:
        pages = json.loads(Path(changes_file).read_text())
        if not isinstance(pages, list) or not all(isinstance(page, list) for page in pages):
            raise ValueError('se esperaban páginas de archivos del PR')
        files = [file for page in pages for file in page]
        if not files or len(files) >= 3000:  # GitHub's PR-files endpoint is capped at 3000.
            return names, 'todos: lista de cambios vacía o posiblemente truncada'
        paths = {file['filename'] for file in files}
        paths.update(file['previous_filename'] for file in files if 'previous_filename' in file)
        rules = json.loads(RULES.read_text())
        covers = flow_covers()
        chosen = set()
        for path in sorted(paths):
            if any(fnmatchcase(path, pattern) for pattern in rules['todos']):
                return names, f'todos: código compartido o infraestructura ({path})'
            matched = False
            for rule in rules['areas']:
                if not any(fnmatchcase(path, pattern) for pattern in rule['rutas']):
                    continue
                matched = True
                affected = {
                    name for name in names
                    if any(fnmatchcase(name, pattern) for pattern in rule.get('flujos', []))
                    or any(fnmatchcase(feature, pattern)
                           for feature in covers.get(name, []) for pattern in rule.get('cubre', []))
                }
                if not affected:
                    return names, f'todos: regla sin cobertura ({path})'
                chosen.update(affected)
            if matched:
                continue
            # A changed top-level flow runs itself; shared helpers/deleted flows run all.
            flow = Path(path)
            if flow.parent.as_posix() == 'movil/.maestro' and flow.suffix == '.yaml' and flow.stem in names:
                chosen.add(flow.stem)
            elif not any(fnmatchcase(path, pattern) for pattern in rules['ignorar']):
                return names, f'todos: ruta sin mapa ({path})'
        return sorted(chosen), ('selección automática por rutas y # cubre: ' + ' '.join(sorted(chosen))
                                if chosen else 'solo documentación: no hay flujos que correr')
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f'No se pudo seleccionar por rutas; se ejecutan todos: {error}', file=sys.stderr)
        return names, 'todos: no se pudo leer la selección automática'


def shards(chosen, limit):
    weight = {n: len((FLOWS / f'{n}.yaml').read_text().splitlines()) for n in chosen}
    count = max(1, min(limit, len(chosen)))
    bins = [[] for _ in range(count)]
    load = [0] * count
    for name in sorted(chosen, key=lambda n: -weight[n]):
        i = load.index(min(load))
        bins[i].append(name)
        load[i] += weight[name]
    return [{'shard': i + 1, 'flujos': ' '.join(sorted(b))} for i, b in enumerate(bins) if b]


def main():
    names = available()
    if not names:
        sys.exit('No se encontraron flujos de Maestro')
    event = os.environ.get('GITHUB_EVENT_NAME', '')
    explicit = bool(os.environ.get('QA_SELECCION', '').strip() or TAG.search(os.environ.get('QA_MENSAJE', '')))
    if event in ('push', 'schedule'):
        chosen, why = names, 'todos los flujos (push o ejecución nocturna)'
    elif explicit:
        chosen, why = select(names, tokens())
    elif event == 'pull_request' and os.environ.get('QA_CHANGED_FILES'):
        chosen, why = automatic(names, os.environ['QA_CHANGED_FILES'])
    else:
        chosen, why = names, 'todos los flujos'
    jobs = shards(chosen, int(os.environ.get('QA_MAX_SHARDS', '8'))) if chosen else []
    # Skipped jobs still need a valid matrix expression.
    matrix = {'include': jobs or [{'shard': 1, 'flujos': ''}]}
    summary = ' '.join(f'{len(chosen)} flujos en {len(jobs)} emuladores: {why}'.splitlines())
    out = os.environ.get('GITHUB_OUTPUT')
    if out:
        with open(out, 'a') as fh:
            fh.write(f'ejecutar={str(bool(chosen)).lower()}\nmatriz={json.dumps(matrix)}\nresumen={summary}\n')
    print(summary)
    for job in jobs:
        print(f"  emulador {job['shard']}: {job['flujos']}")


if __name__ == '__main__':
    main()
