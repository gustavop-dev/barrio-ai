// «Recorrido» of the person card: Descubierto → Seguido → Invitado → Conectado → En conversación → Oportunidad,
// with Cerrado and Descartado as alternative ends (DISENO-VISTAS, Personas, ficha 2). Shared by the PWA
// (its StageTrack) and the native app.
import type { Contact, ContactEvent } from '../api/types';
import { agree, isFeminineName } from './genero';
import { shortDate } from './personas';

export type StageState = 'done' | 'current' | 'pending' | 'alt';

/** A step of the track: the shape of the PWA's StageTrack `Stage`. */
export interface Stage {
  key: string;
  label: string;
  /** «21 oct». */
  date?: string | null;
  /** Extra line («Necesidad identificada»). */
  detail?: string | null;
  /** done: reached; current: where it is now; pending: not yet; alt: an alternative end (Cerrado, Descartado). */
  state: StageState;
}

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

/** The steps of the track for a contact; the last reached one is «current». Labels agree with the person («Seguida»). */
export function journey(contact: Contact): Stage[] {
  const feminine = isFeminineName(contact.display_name);
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
      label: agree(stage === 'discarded' ? 'Descartado' : 'Cerrado', feminine),
      date: shortDate(eventDate(contact, stage)) || null,
      detail: stage === 'closed' ? 'Invitación ignorada o retirada' : null,
      state: 'alt',
    };
    return [...reached.map((step): Stage => ({ key: step.key, label: agree(step.label, feminine), date: shortDate(step.date) || null, state: 'done' })), end];
  }

  // A conversation read from the inbox, or an opportunity (which implies there was one).
  const conversation = contact.conversation ?? null;
  const talked = Boolean(conversation?.messages.length || conversation?.last_message_preview);
  steps.push({ key: 'conversation', label: 'En conversación', reached: Boolean(opportunity) || talked, date: talked ? conversation?.messages[0]?.at : null });
  steps.push({ key: 'opportunity', label: 'Oportunidad', reached: Boolean(opportunity), detail: opportunity?.stage_label ?? null });

  const last = steps.map((step) => step.reached).lastIndexOf(true);
  return steps.map((step, index) => ({
    key: step.key,
    label: agree(step.label, feminine),
    date: step.reached ? shortDate(step.date) || null : null,
    detail: step.detail ?? null,
    state: index === last ? 'current' : step.reached ? 'done' : 'pending',
  }));
}
