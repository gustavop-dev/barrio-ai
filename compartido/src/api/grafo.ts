import { useQuery } from '@tanstack/react-query';
import { api } from './client';

export interface GraphActivity {
  jobs: { id: string; kind: string; state: string; at: string; stage: string | null }[];
  handoffs: { id: string; at: string; from: string; to: string; detail: string }[];
  records?: { id: string; at: string; label: string }[];
}

export interface GraphNode {
  id: string;
  label: string;
  group: string;
  role: 'orchestrator' | 'specialist' | 'gate' | 'executor';
  status: 'active' | 'planned';
  description: string;
  skills: string[];
  tools: string[];
  course_units: string[];
  course_note: string;
  recent_activity: GraphActivity;
}

export interface GraphEdge {
  id: string;
  from: string;
  to: string;
  cycles: string[];
  request_kind: 'workflow_step' | 'call' | 'handoff' | 'gate';
  request_schema: string;
  response_schema: string;
  status: 'active' | 'planned';
  call_group?: string;
}

export interface GraphCycle {
  id: string;
  label: string;
  status: 'active' | 'planned';
  orchestrator: string;
  participants: string[];
  triggers: { kind: string | null; cadence: string }[];
}

export interface TeamGraph {
  schema_version: number;
  graph_version: string;
  graph_hash: string;
  updated_at: string;
  scope: 'descriptive';
  groups: Record<string, string>;
  nodes: GraphNode[];
  edges: GraphEdge[];
  cycles: GraphCycle[];
}

export const graphKey = ['equipo', 'grafo'] as const;

export function useTeamGraph() {
  return useQuery({ queryKey: graphKey, queryFn: ({ signal }) => api.get<TeamGraph>('/api/v1/equipo/grafo', signal), staleTime: 30_000 });
}
