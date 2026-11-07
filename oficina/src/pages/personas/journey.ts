// «Recorrido» of the person card: Descubierto → Seguido → Invitado → Conectado → En conversación → Oportunidad,
// with Cerrado and Descartado as alternative ends (DISENO-VISTAS, Personas, ficha 2).
import type { Contact, ContactEvent } from '../../api/types';
import type { Stage } from '../../components/ui';
import { shortDate } from './labels';

function eventDate(contact: Contact, event: ContactEvent): string | null {
  const found = [...(contact.history ?? [])].reverse().find((item) => item.event === event);
  return found?.at ?? null;
}

interface Step {
  key: string;
  label: string;
  reached: boolean;
  date?: string | null;
  detail?: string | null;
}

/** The steps of the track for a contact; the last reached one is «current». */
export function journey(contact: Contact): Stage[] {
  const stage = contact.stage;
  const incoming = contact.source === 'incoming' || stage === 'incoming';
  const connected = stage === 'connected' || Boolean(contact.connected_at);
  const opportunity = contact.opportunity ?? null;

  const steps: Step[] = [{ key: 'discovered', label: 'Descubierto', reached: true, date: contact.discovered_at }];
  if (incoming) {
    steps.push({ key: 'incoming', label: 'Te invitó', reached: true, date: eventDate(contact, 'incoming') ?? contact.discovered_at });
  } else {
    const invited = Boolean(contact.invited_at) || stage === 'invited' || connected || (stage === 'closed' && Boolean(eventDate(contact, 'invited')));
    const followed = Boolean(contact.followed_at) || stage === 'followed' || invited || contact.is_following;
    steps.push({ key: 'followed', label: 'Seguido', reached: followed, date: contact.followed_at ?? eventDate(contact, 'followed') });
    steps.push({ key: 'invited', label: 'Invitado', reached: invited, date: contact.invited_at ?? eventDate(contact, 'invited') });
  }
  steps.push({ key: 'connected', label: 'Conectado', reached: connected, date: contact.connected_at ?? eventDate(contact, 'connected') });

  if (stage === 'discarded' || stage === 'closed') {
    const reached = steps.filter((step) => step.reached);
    const end: Stage = {
      key: stage,
      label: stage === 'discarded' ? 'Descartado' : 'Cerrado',
      date: shortDate(eventDate(contact, stage)) || null,
      detail: stage === 'closed' ? 'Invitación ignorada o retirada' : null,
      state: 'alt',
    };
    return [...reached.map((step): Stage => ({ key: step.key, label: step.label, date: shortDate(step.date) || null, state: 'done' })), end];
  }

  // Conversations arrive with the inbox; an opportunity implies there was one.
  steps.push({ key: 'conversation', label: 'En conversación', reached: Boolean(opportunity) });
  steps.push({ key: 'opportunity', label: 'Oportunidad', reached: Boolean(opportunity), detail: opportunity?.stage_label ?? null });

  const last = steps.map((step) => step.reached).lastIndexOf(true);
  return steps.map((step, index) => ({
    key: step.key,
    label: step.label,
    date: step.reached ? shortDate(step.date) || null : null,
    detail: step.detail ?? null,
    state: index === last ? 'current' : step.reached ? 'done' : 'pending',
  }));
}
