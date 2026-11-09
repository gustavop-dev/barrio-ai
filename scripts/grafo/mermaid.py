#!/usr/bin/env python3
"""Generate the team graph with stdlib only; --check never changes the file.

grafo.yaml uses the JSON subset of YAML 1.2, parsed by team_backend.grafo.
No Django imports, network, corpus or provider keys are needed.
"""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'agentes-linkedin/infra/src'))
from team_backend.grafo import graph_hash, load_graph  # noqa: E402


def label(value):
    return value.replace('&', '&amp;').replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;').replace('\n', ' ')


def diagram(nodes, edges):
    lines = ['```mermaid', 'flowchart TD', '  classDef planned stroke-dasharray: 5 5,fill:#f5f5f5,color:#555;']
    for group in dict.fromkeys(n['group'] for n in nodes):
        lines.append(f'  subgraph grupo_{group}["{group}"]')
        for node in nodes:
            if node['group'] != group:
                continue
            suffix = ' · En diseño' if node['status'] == 'planned' else ''
            lines.append(f'    {node["id"]}["{label(node["label"] + suffix)} · {node["role"]}"]')
            if node['status'] == 'planned':
                lines.append(f'    class {node["id"]} planned;')
        lines.append('  end')
    for edge in edges:
        arrow = '-.->' if edge['status'] == 'planned' else '-->'
        limit = edge['max_calls_per_cycle']
        cap = str(limit) if isinstance(limit, int) else f'{limit["setting"]}={limit["default"]}'
        group = f' · agrupada {edge["call_group"]}' if edge.get('call_group') else ''
        text = f'{edge["id"]} · {edge["request_kind"]} · ≤{cap}{group}'
        lines.append(f'  {edge["from"]} {arrow}|"{label(text)}"| {edge["to"]}')
    return '\n'.join([*lines, '```'])


def render(graph):
    active = sum(n['status'] == 'active' for n in graph['nodes'])
    lines = ['# Grafo del equipo', '', '<!-- Generado por scripts/grafo/mermaid.py. No editar a mano. -->', '',
             f'Versión `{graph["graph_version"]}` · SHA-256 `{graph_hash(graph)}`.', '',
             f'{len(graph["nodes"])} nodos ({active} activos), {len(graph["edges"])} aristas y {len(graph["cycles"])} ciclos.', '',
             'Pieza diaria, red y Perfil ejecutan sus llamadas mediante el registro y un ledger persistido. Las flechas de pasos y gates pertenecen al workflow determinista; no conceden permisos a los especialistas. Las respuestas vuelven al dueño del ciclo. A/B comparten una llamada y los cinco lectores otra; sus contadores sobreviven a un reinicio.', '',
             'Los trazos discontinuos siguen en diseño. Los ciclos migrados reutilizan checkpoints confirmados y detienen llamadas inciertas para conciliación. Los otros ciclos conservan su estado y contratos descriptivos; referentes continúa en diseño. Perfil entrega propuestas privadas y no escribe LinkedIn.', '', '## Grafo completo', '', diagram(graph['nodes'], graph['edges'])]
    for cycle in graph['cycles']:
        lines += ['', f'## {cycle["label"]}', '', f'Estado: `{cycle["status"]}`. Orquestador: `{cycle["orchestrator"]}`.', '']
        lines += [f'- `{t["kind"] or "planned"}`: {t["cadence"]}' for t in cycle['triggers']]
        lines += ['', diagram([n for n in graph['nodes'] if n['id'] in cycle['participants']],
                              [e for e in graph['edges'] if cycle['id'] in e['cycles']])]
        for loop in cycle['loops']:
            lines += ['', f'Bucle `{loop["id"]}` ({loop["status"]}, máximo {loop["max_rounds"]} rondas): {loop["description"]}']
        for gid in cycle['gates']:
            gate = graph['gates'][gid]
            lines += ['', f'Gate `{gid}` ({", ".join(gate["capabilities"])}): ' + ' → '.join(gate['chain']) + '.']
            lines += [f'- {condition}' for condition in gate['conditions']]
    lines += ['', '## Contratos referenciados', '',
              'Los nombres siguientes enlazan las definiciones existentes. Las aristas con runtime validan JSON Schema, modelos, dataclasses o bytes según el contrato. Los demás contratos conservan su naturaleza descriptiva hasta que se migre su ciclo.', '',
              '| Nombre | Tipo | Código |', '| --- | --- | --- |']
    for sid, schema in graph['schemas'].items():
        module = '/'.join(schema['binding'].split('.')[:2]) + '.py'
        lines.append(f'| `{sid}` | `{schema["kind"]}` | [{schema["binding"]}](../../agentes-linkedin/infra/src/{module}) |')
    lines += ['', '## Aristas y contratos', '', '| Arista | Solicitud | Respuesta |', '| --- | --- | --- |']
    lines += [f'| `{e["id"]}` | `{e["request_schema"]}` | `{e["response_schema"]}` |' for e in graph['edges']]
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    output = ROOT / 'docs/arquitectura/grafo.md'
    expected = render(load_graph())
    if args.check:
        if not output.exists() or output.read_text(encoding='utf-8') != expected:
            parser.exit(1, 'Diagrama desactualizado: ejecutar python3 scripts/grafo/mermaid.py\n')
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(expected, encoding='utf-8')


if __name__ == '__main__':
    main()
