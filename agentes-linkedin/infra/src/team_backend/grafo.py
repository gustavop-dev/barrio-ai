"""Registry shared by the phase 3b dispatcher, map and diagram generator.

The registry uses JSON, a strict subset of YAML 1.2. This keeps the standalone
diagram generator dependency-free and rejects duplicate keys, tags and aliases.
No Django, corpus, providers or environment secrets are needed to validate it.
"""
import ast
import hashlib
import json
import math
import re
from pathlib import Path


class GraphError(ValueError):
    pass


def registry_path():
    # Docker copies the same canonical file here; no second maintained registry.
    infra = Path(__file__).resolve().parents[2]
    packaged = infra / 'equipos/grafo.yaml'
    return packaged if packaged.exists() else infra.parent / 'equipos/grafo.yaml'


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise GraphError(f'Clave duplicada: {key}')
        result[key] = value
    return result


def load_graph(path=None):
    try:
        graph = json.loads(Path(path or registry_path()).read_text(encoding='utf-8'), object_pairs_hook=_unique)
    except (OSError, json.JSONDecodeError) as exc:
        raise GraphError('grafo.yaml debe usar el subconjunto JSON de YAML 1.2') from exc
    validate_graph(graph)
    return graph


def graph_hash(graph):
    return hashlib.sha256(json.dumps(graph, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _index(items, label):
    if not isinstance(items, list):
        raise GraphError(f'{label}: se esperaba una lista')
    result = {}
    for item in items:
        if not isinstance(item, dict) or not re.fullmatch(r'[a-z][a-z0-9_]*', str(item.get('id', ''))):
            raise GraphError(f'{label}: id inválido')
        if item['id'] in result:
            raise GraphError(f'{label}: id duplicado {item["id"]}')
        result[item['id']] = item
    return result


def _bounded(value):
    return (type(value) is int and value > 0) or (
        isinstance(value, dict) and isinstance(value.get('setting'), str)
        and re.fullmatch(r'[A-Z][A-Z0-9_]+', value['setting'])
        and type(value.get('default')) is int and value['default'] > 0)


def validate_graph(graph):
    def check(condition, message):
        if not condition:
            raise GraphError(message)

    check(isinstance(graph, dict) and graph.get('schema_version') == 1, 'schema_version inválida')
    check(graph.get('scope') in ('descriptive','runtime'), 'scope inválido')
    nodes = _index(graph.get('nodes'), 'nodos')
    edges = _index(graph.get('edges'), 'aristas')
    cycles = _index(graph.get('cycles'), 'ciclos')
    schemas = graph.get('schemas', {})
    lists = graph.get('course_lists', {})
    budgets = graph.get('budgets', {})
    gates = graph.get('gates', {})
    for ref, units in lists.items():
        check(isinstance(units, list) and all(isinstance(u, str) and re.fullmatch(r'LI-0[1-6]-[A-Z]\d{3}-K\d{2}', u) for u in units),
              f'lista {ref}: IDs de unidades inválidos (solo clases 01–06)')
    for sid, schema in schemas.items():
        check(schema.get('binding') and schema.get('kind'), f'schema {sid}: sin binding/tipo')
    for nid, node in nodes.items():
        for key in ('label', 'group', 'role', 'status', 'description', 'skills', 'tools', 'course_units',
                    'course_lists', 'model', 'effort', 'budget_ref', 'input_schemas', 'output_schemas', 'activity'):
            check(key in node, f'nodo {nid}: falta {key}')
        check(node['status'] in ('active', 'planned'), f'nodo {nid}: status inválido')
        check(node['role'] in ('orchestrator', 'specialist', 'gate', 'executor'), f'nodo {nid}: role inválido')
        check(node['group'] in graph.get('groups', {}), f'nodo {nid}: grupo desconocido')
        check(node['label'] and node['description'] and isinstance(node['skills'], list) and isinstance(node['tools'], list),
              f'nodo {nid}: descripción/skills/tools inválidos')
        check(node['budget_ref'] in budgets, f'nodo {nid}: presupuesto desconocido')
        check(all(ref in lists for ref in node['course_lists']), f'nodo {nid}: lista curada desconocida')
        allowed = {u for ref in node['course_lists'] for u in lists[ref]}
        check(set(node['course_units']) <= allowed, f'nodo {nid}: unidad fuera de listas curadas')
        check(len(node['course_units']) == len(set(node['course_units'])), f'nodo {nid}: unidad duplicada')
        check(all(s in schemas for s in node['input_schemas'] + node['output_schemas']), f'nodo {nid}: schema desconocido')
        if node['status'] == 'active':
            check(node.get('binding') and node['input_schemas'] and node['output_schemas'], f'nodo {nid}: sin binding/schemas')
        if 'linkedin_write' in node['tools']:
            check(nid == 'operador_cuenta' and node['role'] == 'executor', f'nodo {nid}: escritor LinkedIn no autorizado')
        activity = node['activity']
        check(isinstance(activity, dict) and isinstance(activity.get('job_kinds'), list) and isinstance(activity.get('event_roles'), list),
              f'nodo {nid}: atribución de actividad inválida')
        check(activity.get('piece_evidence') in (None, 'design', 'edited', 'review'), f'nodo {nid}: evidencia de pieza desconocida')
        check(activity.get('capture_evidence') in (None, 'route', 'intent', 'transcript'), f'nodo {nid}: evidencia de captura desconocida')
    check(all(role in nodes for role in graph.get('code_bindings', {}).get('job_roles', {}).values()), 'JOB_ROLES: nodo desconocido')
    for eid, edge in edges.items():
        a, b = edge.get('from'), edge.get('to')
        check(a in nodes and b in nodes, f'arista {eid}: extremo desconocido')
        check(edge.get('status') in ('active', 'planned'), f'arista {eid}: status inválido')
        check(not (nodes[a]['role'] == nodes[b]['role'] == 'specialist'), f'arista {eid}: especialista a especialista')
        check(edge.get('request_kind') in ('workflow_step', 'call', 'gate', 'handoff'), f'arista {eid}: tipo inválido')
        check(edge.get('request_schema') in schemas and edge.get('response_schema') in schemas, f'arista {eid}: schemas desconocidos')
        check(_bounded(edge.get('max_calls_per_cycle')), f'arista {eid}: límite no acotado')
        check(type(edge.get('response_required')) is bool, f'arista {eid}: respuesta sin declarar')
        check(edge.get('cycles') and all(c in cycles for c in edge['cycles']), f'arista {eid}: ciclo desconocido')
        if edge['status'] == 'active':
            check(nodes[a]['status'] == nodes[b]['status'] == 'active', f'arista {eid}: activa hacia nodo planned')
            check(all(cycles[c]['status'] == 'active' for c in edge['cycles']), f'arista {eid}: activa en ciclo planned')
        for cid in edge['cycles']:
            check(a in cycles[cid]['participants'] and b in cycles[cid]['participants'], f'arista {eid}: fuera de participantes de {cid}')

    reachable = set()
    for cid, cycle in cycles.items():
        owner = cycle.get('orchestrator')
        check(owner in nodes and nodes[owner]['role'] == 'orchestrator', f'ciclo {cid}: orquestador único inválido')
        check(cycle.get('status') in ('active', 'planned'), f'ciclo {cid}: status inválido')
        check(owner in cycle['participants'] and all(p in nodes for p in cycle['participants']), f'ciclo {cid}: participantes inválidos')
        check(cycle.get('triggers') and cycle.get('ledger') and cycle.get('limits'), f'ciclo {cid}: falta trigger/ledger/límites')
        check(cycle['limits'].get('max_depth') == 1, f'ciclo {cid}: profundidad máxima debe ser 1')
        if cycle['ledger']['status'] == 'runtime':
            limits = cycle['limits']
            for key in ('max_calls','max_provider_calls','call_timeout_s','cycle_timeout_s','max_stalls','max_replans','cost_cap_usd'):
                check(type(limits.get(key)) in (int,float) and math.isfinite(limits[key]) and limits[key] > 0,
                      f'ciclo {cid}: límite {key} inválido')
            for edge in edges.values():
                if cid not in edge['cycles'] or not edge.get('runtime'):continue
                check(type(edge['max_calls_per_cycle']) is int, f'arista {edge["id"]}: límite runtime sin resolver')
                check(all(schemas[edge[k]]['kind'] in ('json_schema','model','dataclass','bytes')
                          for k in ('request_schema','response_schema')), f'arista {edge["id"]}: contrato no ejecutable')

        check(all(b in budgets for b in cycle['limits']['budget_refs']), f'ciclo {cid}: presupuesto desconocido')
        check(all(g in gates and gates[g]['cycle'] == cid for g in cycle['gates']), f'ciclo {cid}: gate desconocido')
        local = [e for e in edges.values() if cid in e['cycles'] and e['status'] == 'active']
        loop_edges = set()
        for loop in cycle['loops']:
            check(loop.get('status') in ('active', 'planned'), f'ciclo {cid}: estado de bucle inválido')
            check(type(loop.get('max_rounds')) is int and 0 < loop['max_rounds'] <= 2, f'ciclo {cid}: bucle no acotado')
            check(all(e in edges and cid in edges[e]['cycles'] for e in loop['edges']), f'ciclo {cid}: arista de bucle desconocida')
            if loop['status'] == 'active':
                loop_edges.update(loop['edges'])
        if cycle['status'] != 'active':
            continue
        check(nodes[owner]['status'] == 'active', f'ciclo {cid}: orquestador planned')
        seen, pending = set(), [owner]
        while pending:
            current = pending.pop()
            if current in seen:
                continue
            seen.add(current)
            pending.extend(e['to'] for e in local if e['from'] == current)
        reachable.update(seen)
        for participant in cycle['participants']:
            check(nodes[participant]['status'] == 'planned' or participant in seen, f'ciclo {cid}: nodo no alcanzable {participant}')
        for edge in local:
            if edge['request_kind'] in ('call', 'workflow_step'):
                check(edge['from'] == owner or (edge['id'] in loop_edges and not edge.get('runtime')),
                      f'arista {edge["id"]}: profundidad > 1 desde {owner}')
            if nodes[edge['from']]['role'] == 'specialist':
                check(edge['request_kind'] in ('handoff', 'gate'), f'arista {edge["id"]}: especialista invoca agente')
    check(all(n['status'] == 'planned' or n['id'] in reachable for n in nodes.values()), 'nodo activo no alcanzable desde ningún ciclo')

    for gid, gate in gates.items():
        cid, chain = gate['cycle'], gate['chain']
        check(cid in cycles and gid in cycles[cid]['gates'], f'gate {gid}: ciclo no lo declara')
        check(chain and chain[0] == gate['entry'] and chain[-1] == 'operador_cuenta', f'gate {gid}: ruta ejecutable incompleta')
        check('lider_jev' in chain and 'gustavo' in chain, f'gate {gid}: falta líder/veto')
        if 'CONT-09' in gate['capabilities']:
            check(chain[0] == 'editor_verificador', f'gate {gid}: falta verificador')
        check(all(n in nodes for n in chain), f'gate {gid}: nodo desconocido')
        check(all(nodes[n]['role'] == 'gate' for n in chain[:-1]), f'gate {gid}: control no es gate')
        local = [e for e in edges.values() if cid in e['cycles'] and e['status'] == 'active']
        path = [gate['producer'], *chain]
        for a, b in zip(path, path[1:]):
            check(any(e['from'] == a and e['to'] == b for e in local), f'gate {gid}: falta tramo {a} → {b}')
        # Removing each mandatory gate must disconnect the producer from execution.
        # This catches bypasses even if the declared chain itself still exists.
        for stop in chain[:-1]:
            seen, pending = set(), [gate['producer']]
            while pending:
                current = pending.pop()
                if current in seen or current == stop:
                    continue
                seen.add(current)
                pending.extend(e['to'] for e in local if e['from'] == current)
            check('operador_cuenta' not in seen, f'gate {gid}: ruta evita {stop}')
    for edge in edges.values():
        if edge['status'] == 'active' and nodes[edge['to']]['role'] == 'executor':
            check(any(g['cycle'] in edge['cycles'] and g['chain'][-2:] == [edge['from'], edge['to']] for g in gates.values()),
                  f'arista {edge["id"]}: salida ejecutable sin gates')
    # Validate topology/gates first, then runtime authority. A bypass must be
    # diagnosed as such even if it also carries an unauthorized runtime binding.
    for cid, cycle in cycles.items():
        if cycle['ledger']['status'] != 'runtime':continue
        for edge in edges.values():
            if cid not in edge['cycles'] or not edge.get('runtime'):continue
            declared_gate = (edge['request_kind']=='gate' and edge['to']=='lider_jev'
                             and any(edge['id'] in gates[g].get('runtime_edges',[]) for g in cycle['gates']))
            check(edge['from'] == cycle['orchestrator'] or declared_gate,
                  f'arista {edge["id"]}: runtime fuera del orquestador')
    for name, group in graph.get('call_groups', {}).items():
        members = {e['to'] for e in edges.values() if e.get('call_group') == name}
        check(members == set(group['members']) and _bounded(group['max_calls_per_cycle']), f'llamada agrupada {name}: inconsistente')
    return graph


def validate_bindings(graph, source_root=None):
    """Check source symbols using AST only: never import handlers or contact providers."""
    source_root = Path(source_root or Path(__file__).resolve().parents[1])
    bindings = [s['binding'] for s in graph['schemas'].values()]
    bindings += [n['binding'] for n in graph['nodes'] if n['status'] == 'active']
    for binding in bindings:
        parts = binding.split('.')
        path = source_root.joinpath(*parts[:2]).with_suffix('.py')
        if not path.is_file():
            raise GraphError(f'binding inexistente: {binding}')
        body = ast.parse(path.read_text()).body
        for symbol in parts[2:]:
            found = None
            for item in body:
                names = [t.id for t in item.targets if isinstance(t, ast.Name)] if isinstance(item, ast.Assign) else [getattr(item, 'name', None)]
                if symbol in names:
                    found = item
                    break
            if found is None:
                raise GraphError(f'binding inexistente: {binding}')
            body = getattr(found, 'body', [])
