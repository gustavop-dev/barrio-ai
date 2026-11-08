#!/usr/bin/env python3
"""Short Markdown coverage table for the GitHub job summary (barrio-ai.yml). Report-only: no thresholds.

  cobertura.py istanbul movil/coverage/coverage-summary.json --title "movil + compartido" \
      --area movil/src/ --area compartido/src/ --artifact cobertura-movil
  cobertura.py coveragepy agentes-linkedin/infra/coverage.json --title backend --artifact cobertura-backend

`istanbul` reads the `json-summary` of Jest or Vitest (statements, branches, functions and lines, one
row per --area plus the total). `coveragepy` reads `coverage json` (lines and branches). Standard
library only, so it runs on any runner without installing anything.
"""

import argparse
import json
import sys

ISTANBUL_KEYS = (('statements', 'Sentencias'), ('branches', 'Ramas'), ('functions', 'Funciones'), ('lines', 'Líneas'))


def cell(covered: int, total: int) -> str:
    if not total:
        return '—'
    return f'{round(covered * 100 / total, 1)} % ({covered}/{total})'


def istanbul(summary: dict, areas: list[str]) -> list[str]:
    header = '| | ' + ' | '.join(label for _, label in ISTANBUL_KEYS) + ' |'
    rows = [header, '|---|' + '---:|' * len(ISTANBUL_KEYS)]
    files = {path: metrics for path, metrics in summary.items() if path != 'total'}

    def row(name: str, metrics: list[dict]) -> str:
        cells = []
        for key, _ in ISTANBUL_KEYS:
            covered = sum(m[key]['covered'] for m in metrics)
            total = sum(m[key]['total'] for m in metrics)
            cells.append(cell(covered, total))
        return f'| {name} | ' + ' | '.join(cells) + ' |'

    for area in areas:
        rows.append(row(f'`{area}`', [m for path, m in files.items() if area in path.replace('\\', '/')]))
    rows.append(row('**total**', [summary['total']]))
    return rows


def coveragepy(report: dict) -> list[str]:
    totals = report['totals']
    return [
        '| | Líneas | Ramas |',
        '|---|---:|---:|',
        f"| **total** | {cell(totals['covered_lines'], totals['num_statements'])} "
        f"| {cell(totals.get('covered_branches', 0), totals.get('num_branches', 0))} |",
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('kind', choices=('istanbul', 'coveragepy'))
    parser.add_argument('report')
    parser.add_argument('--title', required=True)
    parser.add_argument('--area', action='append', default=[])
    parser.add_argument('--artifact', required=True)
    args = parser.parse_args()

    with open(args.report, encoding='utf-8') as handle:
        data = json.load(handle)
    table = istanbul(data, args.area) if args.kind == 'istanbul' else coveragepy(data)
    lines = [
        f'### Cobertura · {args.title}',
        '',
        *table,
        '',
        f'Solo informe, sin umbrales. El informe completo está en el artefacto `{args.artifact}`.',
        '',
    ]
    sys.stdout.write('\n'.join(lines) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
