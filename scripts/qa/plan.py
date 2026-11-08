#!/usr/bin/env python3
"""Which Maestro flows a QA run executes and how they are split across the emulator jobs (.github/workflows/qa-movil.yml).

Selection, first match wins:
  1. QA_SELECCION (the `flujos` input of a manual run);
  2. the last `[qa: …]` in QA_MENSAJE (the message of the PR's head commit), e.g. `[qa: 05-captura 09]`;
  3. every flow.
Tokens are separated by spaces or commas; a token selects the flows whose name equals it, starts with it or contains it
(`05`, `05-captura`, `captura`). `todo` or `todos` selects everything.

The selected flows are split into at most QA_MAX_SHARDS jobs, longest first onto the lightest job (by the flow's number
of lines, a fair proxy of its duration). Inside a job the flows keep their numeric order, so 11-ajustes (which logs out)
runs last in its job. Writes `matriz` (the JSON matrix) and `resumen` to $GITHUB_OUTPUT, or prints them.
"""
import json
import os
import re
import sys
from pathlib import Path

FLOWS = Path(__file__).resolve().parents[2] / 'movil' / '.maestro'
TAG = re.compile(r'\[qa:\s*([^\]]*)\]', re.I)


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
    chosen, why = select(available(), tokens())
    matrix = {'include': shards(chosen, int(os.environ.get('QA_MAX_SHARDS', '4')))}
    summary = f'{len(chosen)} flujos en {len(matrix["include"])} emuladores: {why}'
    out = os.environ.get('GITHUB_OUTPUT')
    if out:
        with open(out, 'a') as fh:
            fh.write(f'matriz={json.dumps(matrix)}\nresumen={summary}\n')
    print(summary)
    for job in matrix['include']:
        print(f"  emulador {job['shard']}: {job['flujos']}")


if __name__ == '__main__':
    main()
