import type { GraphNode, TeamGraph } from '../api/grafo';

/** Synthetic API data; both clients exercise the same contract without a network. */
export function graphFixture(): TeamGraph {
  const node = (id: string, label: string, extra: Partial<GraphNode> = {}): GraphNode => ({
    id, label, group: 'editorial', role: 'specialist', status: 'active', description: 'Aporta una propuesta al director.',
    skills: [], tools: [], course_units: [], course_note: 'Este paso no carga una lista curada del curso.',
    recent_activity: { jobs: [], handoffs: [] }, ...extra,
  });
  return {
    schema_version: 1, graph_version: 'fixture', graph_hash: 'fake', scope: 'descriptive', updated_at: '2026-11-08T12:00:00Z',
    groups: { editorial: 'Mesa editorial' },
    nodes: [
      node('director_editorial', 'Director editorial', {
        role: 'orchestrator', description: 'Elige el brief de la pieza y coordina las herramientas.', course_units: ['LI-04-M005-K01'], course_note: 'Lista curada del director.',
        recent_activity: { jobs: [{ id: 'job-1', kind: 'prepare_piece', state: 'complete', at: '2026-11-08T11:00:00Z', stage: 'director' }],
          handoffs: [{ id: 'event-1', from: 'director_editorial', to: 'copywriter_a', at: '2026-11-08T11:01:00Z', detail: 'Brief entregado' }] },
      }),
      node('copywriter_a', 'Copywriter A'),
      node('editor_visual', 'Especialista visual · EDI-21', { status: 'planned' }),
    ],
    edges: [
      { id: 'redactar', from: 'director_editorial', to: 'copywriter_a', request_kind: 'workflow_step', request_schema: 'brief', response_schema: 'variants', status: 'active', cycles: ['pieza_diaria'], call_group: 'redactor' },
      { id: 'visual', from: 'director_editorial', to: 'editor_visual', request_kind: 'workflow_step', request_schema: 'brief', response_schema: 'choice', status: 'planned', cycles: ['pieza_diaria'] },
    ],
    cycles: [{ id: 'pieza_diaria', label: 'Pieza diaria', status: 'active', orchestrator: 'director_editorial', participants: ['director_editorial', 'copywriter_a', 'editor_visual'], triggers: [{ kind: 'prepare_piece', cadence: 'Diaria' }] }],
  };
}
