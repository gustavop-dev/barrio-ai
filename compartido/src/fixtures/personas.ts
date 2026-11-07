// Personas data shaped like CONTRATO-API («Red», «Personas»). Invented people only.
import type { Account, Contact, Conversation, Opportunity, RedSummary, Referent } from '../api/types';

export function redSummaryFixture(extra: Partial<RedSummary> = {}): RedSummary {
  return {
    enabled: true,
    stages: { candidate: 12, fit: 9, discarded: 6, followed: 8, invited: 6, connected: 7, closed: 2, incoming: 1, opportunity: 1, conversation: null },
    capacity: {},
    reads_today: {},
    read_caps: {},
    llm: { spent_today: 0.04, daily: 0.3, model: 'claude-sonnet-5-5' },
    invites_blocked: { blocked: false, reason: '' },
    last_discovery_at: null,
    last_sync_at: null,
    ...extra,
  };
}

export function contactFixture(id = 'c-1', extra: Partial<Contact> = {}): Contact {
  return {
    id,
    account_id: 'acc-1',
    provider_user_id: `ACo${id}`,
    public_identifier: `persona-${id}`,
    display_name: 'Lucía Ficticia',
    headline: 'Cofundadora @ Huerta Labs (pre-seed)',
    profile_url: `https://www.linkedin.com/in/persona-${id}`,
    location: 'Medellín, Colombia',
    source: 'commenter',
    evidence: {
      post_id: 'post-9',
      post_url: 'https://www.linkedin.com/feed/update/urn:li:activity:9',
      referent: 'Elena Prueba',
      comment: 'We keep adding AI to the roadmap and nobody can say which step it fixes.',
      query: null,
      invitation_message: null,
    },
    network_distance: 'SECOND_DEGREE',
    is_following: false,
    stage: 'fit',
    display_stage: 'fit',
    classification: {
      fit: true,
      role: 'comprador',
      modality: 'projectapp',
      affinity: 'hispanohablante_declarada',
      reason: 'Cofundadora de una startup pre-seed que está decidiendo qué construir con IA.',
      confidence: 0.82,
      model: 'claude-sonnet-5-5',
      classified_at: '2026-10-21T15:00:00Z',
    },
    history: [
      { at: '2026-10-21T14:00:00Z', event: 'discovered', detail: 'Comentó en un post de Elena Prueba.' },
      { at: '2026-10-21T15:00:00Z', event: 'classified', detail: 'comprador · projectapp' },
    ],
    notes: [],
    followed_at: null,
    invited_at: null,
    connected_at: null,
    discovered_at: '2026-10-21T14:00:00Z',
    updated_at: '2026-10-21T15:00:00Z',
    open_action: null,
    opportunity: null,
    next_step: { owner: 'equipo', text: 'El equipo la seguirá', at: null },
    your_turn: false,
    last_event: { at: '2026-10-21T15:00:00Z', event: 'classified', detail: 'comprador · projectapp' },
    ...extra,
  };
}

export function opportunityFixture(id = 'o-1', extra: Partial<Opportunity> = {}): Opportunity {
  return {
    id,
    person: 'Lucía Ficticia',
    contact: { id: 'c-1', display_name: 'Lucía Ficticia', headline: 'Cofundadora @ Huerta Labs', profile_url: 'https://www.linkedin.com/in/persona-c-1', stage: 'connected', role: 'comprador' },
    person_name: '',
    company: 'Huerta Labs',
    modality: 'projectapp',
    channel: 'linkedin',
    stage: 'necesidad',
    attribution: 'cito_contenido',
    need: 'Decidir y construir una primera funcionalidad de IA.',
    budget: '',
    dedication: '',
    next_action: 'Enviar la propuesta de piloto',
    next_action_at: '2026-11-12T17:00:00Z',
    notes: '',
    history: [{ at: '2026-11-06T15:00:00Z', event: 'created', detail: 'Necesidad identificada' }],
    days_in_stage: 1,
    created_at: '2026-11-06T15:00:00Z',
    updated_at: '2026-11-06T15:00:00Z',
    stage_changed_at: '2026-11-06T15:00:00Z',
    closed_at: null,
    ...extra,
  };
}

export function referentFixture(id = 'r-1', extra: Partial<Referent> = {}): Referent {
  return {
    id,
    account_id: 'acc-1',
    public_identifier: `ref-${id}`,
    display_name: 'Elena Prueba',
    profile_url: `https://www.linkedin.com/in/ref-${id}/`,
    reason: 'Escribe sobre IA aplicada al producto para founders.',
    active: true,
    created_at: '2026-10-01T10:00:00Z',
    last_observed_at: null,
    contacts_count: 14,
    ...extra,
  };
}

export function accountFixture(id = 'acc-1', label = 'LinkedIn de Gustavo'): Account {
  return { id, label, provider: 'unipile', status: 'ok', is_locked: false, paused: false, paused_reason: '', last_checked_at: null };
}

/** A DRF page. */
export function page<T>(results: T[], next: string | null = null) {
  return { body: { count: results.length, next, previous: null, results } };
}

/** A LinkedIn conversation read by conversaciones_inbox (CONTRATO-API «Conversaciones»). */
export function conversationFixture(extra: Partial<Conversation> = {}): Conversation {
  return {
    id: 'conv-1',
    chat_url: 'https://www.linkedin.com/messaging/thread/2-SHVlcnRhTGFicw==/',
    attendee_name: 'Lucía Ficticia',
    contact_id: 'c-1',
    last_message_at: '2026-10-06T15:12:00Z',
    last_from_me: false,
    last_message_preview: 'Hola Gustavo, ¿tienes disponibilidad para un proyecto corto de IA en enero?',
    messages: [
      { id: 'm-1', at: '2026-10-05T14:00:00Z', from_me: true, text: 'Thanks Lucía! Happy to share how we scoped it if useful.' },
      { id: 'm-2', at: '2026-10-05T16:00:00Z', from_me: false, text: 'Would love that. We are stuck on where AI actually helps.' },
      { id: 'm-3', at: '2026-10-06T15:12:00Z', from_me: false, text: 'Hola Gustavo, ¿tienes disponibilidad para un proyecto corto de IA en enero?' },
    ],
    assessment: {
      message_id: 'm-3',
      opportunity: true,
      awaiting_reply: true,
      pitch: false,
      modality: 'projectapp',
      answers: { oportunidad: 0.86, espera: 0.81, venta: 0.04, startups: 0.2, projectapp: 0.9 },
      model: 'jev-1.14.0',
      at: '2026-10-06T16:00:00Z',
    },
    why: 'Posible oportunidad: ProjectApp (86 %) · Espera tu respuesta (81 %)',
    needs_you: true,
    ...extra,
  };
}
