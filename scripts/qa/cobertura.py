#!/usr/bin/env python3
"""E2E coverage of the feature catalog: «X de Y funcionalidades de la app cubiertas por E2E».

Y: the features of docs/funcionalidades/*.md whose «Dónde» includes `app` and whose «Estado» is `funciona` or `parcial`.
X: those of them listed in the `# cubre: ID, ID` header of some movil/.maestro/NN-*.yaml (before its `---`).
Standard library only. Run alone (`cobertura.py [--json]`) or imported by informe.py, which adds which of the covering
flows passed in the run.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / 'docs' / 'funcionalidades'
FLOWS = ROOT / 'movil' / '.maestro'
FEATURE = re.compile(r'\b[A-Z]{3}(?:-[A-Z]{3})?-\d{2}\b')
HEADING = re.compile(r'^###\s+(' + FEATURE.pattern[2:-2] + r')\s*·\s*(.*?)\s*(?:<a id=.*)?$')
FIELD = re.compile(r'^-\s*\*\*(Dónde|Estado):\*\*\s*(.+?)\s*$')
COUNTED = ('funciona', 'parcial')


def catalog():
    """{id: {title, area, where, status}} for every feature of the catalog."""
    features = {}
    for doc in sorted(CATALOG.glob('*.md')):
        if doc.name == 'README.md':
            continue
        current = None
        for line in doc.read_text().splitlines():
            m = HEADING.match(line)
            if m:
                current = features.setdefault(m.group(1), {'title': m.group(2), 'area': doc.stem, 'where': [], 'status': ''})
                continue
            f = FIELD.match(line)
            if f and current is not None:
                if f.group(1) == 'Dónde':
                    current['where'] = [w.strip().lower() for w in f.group(2).split('·')]
                else:
                    current['status'] = f.group(2).strip().strip('`').lower()
    return features


def app_features(features=None):
    """The features E2E should cover: in the app, and working or partial."""
    features = features if features is not None else catalog()
    return {i: f for i, f in features.items() if 'app' in f['where'] and f['status'] in COUNTED}


def flow_covers():
    """{flow name: [ids]} from the `# cubre:` header of every flow."""
    out = {}
    for path in sorted(FLOWS.glob('[0-9][0-9]-*.yaml')):
        ids = []
        for line in path.read_text().splitlines():
            if line.strip() == '---':
                break
            if line.startswith('# cubre:'):
                ids += FEATURE.findall(line)
        out[path.stem] = ids
    return out


def summary(passed_flows=None):
    """Coverage numbers; `passed_flows` (names) also counts what the flows that passed in this run cover."""
    features = catalog()
    wanted = app_features(features)
    covers = flow_covers()
    declared = {i for ids in covers.values() for i in ids}
    covered = sorted(i for i in wanted if i in declared)
    passing = sorted(i for i in covered if passed_flows is not None and any(i in covers.get(f, []) for f in passed_flows))
    missing = sorted(i for i in wanted if i not in declared)
    unknown = sorted(i for i in declared if i not in features)
    other = sorted(i for i in declared if i in features and i not in wanted)
    return {'total': len(wanted), 'covered': covered, 'passing': passing if passed_flows is not None else None,
            'missing': [{'id': i, 'title': wanted[i]['title'], 'area': wanted[i]['area'], 'status': wanted[i]['status']} for i in missing],
            'unknown': unknown, 'other': [{'id': i, 'status': features[i]['status'], 'where': features[i]['where']} for i in other]}


def markdown(data):
    lines = [f"**{len(data['covered'])} de {data['total']} funcionalidades de la app cubiertas por E2E** "
             f"(`docs/funcionalidades/`, Dónde: app, Estado: funciona o parcial)"]
    if data['passing'] is not None:
        lines.append(f"- de ellas, en flujos que pasaron en esta ejecución: {len(data['passing'])}")
    if data['missing']:
        by_area = {}
        for item in data['missing']:
            by_area.setdefault(item['area'], []).append(item)
        lines += ['', f"<details><summary>Sin cubrir ({len(data['missing'])})</summary>", '']
        for area, items in by_area.items():
            lines.append(f"- **{area}**: " + ', '.join(f"{i['id']} {i['title']}" + (' (parcial)' if i['status'] == 'parcial' else '') for i in items))
        lines += ['', '</details>']
    if data['unknown']:
        lines.append(f"- IDs en `# cubre:` que no existen en el catálogo: {', '.join(data['unknown'])}")
    if data['other']:
        lines.append(f"- También cubiertas, fuera del recuento (no son de la app o no están en funciona/parcial): "
                     f"{', '.join(o['id'] + ' (' + o['status'] + ')' for o in data['other'])}")
    return '\n'.join(lines)


if __name__ == '__main__':
    result = summary()
    print(json.dumps(result, ensure_ascii=False, indent=2) if '--json' in sys.argv else markdown(result))
