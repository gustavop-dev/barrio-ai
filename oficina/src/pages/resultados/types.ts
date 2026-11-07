// Section 1 of GET /api/v1/resultados when `disponible` (resultados.py, negocio()); the shared type leaves it open.
import type { Kpi, OpportunityModality, OpportunityStage, Resultados } from '../../api/types';

export interface NegocioStep {
  stage: OpportunityStage;
  label: string;
  count: number;
  conversion_pct: number | null;
}

export interface NegocioActiva {
  id: string;
  person: string;
  contact_id: string | null;
  company: string;
  modality: OpportunityModality;
  stage: OpportunityStage;
  stage_label: string;
  next_action: string;
  next_action_at: string | null;
}

export type BusinessModality = 'personal_startups' | 'projectapp';

export interface NegocioOn {
  disponible: true;
  motivo?: string | null;
  conversaciones: Kpi;
  abiertas: Kpi;
  reuniones: Kpi;
  propuestas: Kpi;
  acuerdos: Kpi;
  inbound: Kpi;
  embudo: { steps: NegocioStep[]; sin_acuerdo: number; definition: string };
  modalidades: {
    counts: Partial<Record<OpportunityModality, number>>;
    pct: Partial<Record<BusinessModality, number | null>>;
    objetivo: Partial<Record<BusinessModality, number>>;
    definition: string;
  };
  activas: NegocioActiva[];
}

export interface NegocioOff {
  disponible: false;
  motivo: string | null;
  inbound: Kpi;
}

export type Negocio = NegocioOn | NegocioOff;

export function readNegocio(data: Resultados['negocio']): Negocio {
  return data as unknown as Negocio;
}
