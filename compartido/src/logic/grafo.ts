import type { GraphNode, TeamGraph } from '../api/grafo';

export const graphRole: Record<GraphNode['role'], string> = {
  orchestrator: 'Coordina el ciclo', specialist: 'Especialista', gate: 'Revisión y control', executor: 'Ejecuta acciones',
};

export function graphGroups(graph: TeamGraph, cycleId?: string) {
  const cycle = graph.cycles.find((c) => c.id === cycleId);
  return Object.entries(graph.groups).map(([id, label]) => ({ id, label, nodes: graph.nodes.filter((n) => n.group === id && (!cycle || cycle.participants.includes(n.id))) })).filter((g) => g.nodes.length);
}

export function graphConnections(graph: TeamGraph, id: string, cycleId?: string) {
  return graph.edges.filter((e) => (e.from === id || e.to === id) && (!cycleId || e.cycles.includes(cycleId))).flatMap((edge) => {
    const outgoing = edge.from === id;
    const peer = graph.nodes.find((n) => n.id === (outgoing ? edge.to : edge.from));
    if (!peer) return [];
    const direction = edge.from === edge.to ? 'Paso propio' : outgoing
      ? edge.request_kind === 'handoff' ? 'Entrega a' : edge.request_kind === 'gate' ? 'Pasa por' : 'Solicita a'
      : 'Recibe de';
    return [{ edge, peer, direction, cycles: graph.cycles.filter((c) => edge.cycles.includes(c.id)).map((c) => c.label).join(' · ') }];
  });
}

export function graphJobLabel(state: string) {
  return ({ queued: 'En cola', running: 'En curso', complete: 'Terminado', failed: 'Falló', interrupted: 'Interrumpido', cancelled: 'Cancelado' } as Record<string, string>)[state] ?? state;
}
