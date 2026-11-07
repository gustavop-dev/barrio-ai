// «Conversación» of the person card (DISENO-VISTAS, Personas, ficha 6): the team's read of the latest message, the
// last messages with author and date, and «Abrir en LinkedIn». Read-only: the app never sends messages.
import type { Conversation, ConversationAssessment, ConversationMessage } from '../../api/types';
import { Badge, Card, ExternalLink, LabelChip } from '../../components/ui';
import { formatTime } from '../../lib/format';
import { OPPORTUNITY_MODALITY_LABEL, relativeDay } from './labels';

/** «hoy 10:12», «ayer 18:03» or «6 nov». */
export function messageWhen(iso: string | null | undefined): string {
  if (!iso) return '';
  const day = relativeDay(iso);
  return day === 'hoy' || day === 'ayer' ? `${day} ${formatTime(iso)}` : day;
}

function percent(value: number | undefined): string | null {
  return typeof value === 'number' ? `${Math.round(Math.min(1, Math.max(0, value)) * 100)} %` : null;
}

/** The message text, or what it carried when it has none. */
export function messageText(message: ConversationMessage): string {
  if (message.text) return message.text;
  return message.attachments ? 'Envió un adjunto.' : 'Mensaje sin texto.';
}

/** The team's read as chips, then the probabilities behind them. */
export function TeamRead({ assessment }: { assessment: ConversationAssessment | null }) {
  if (!assessment) return <p className="persona-meta">El equipo aún no ha leído su último mensaje.</p>;
  const answers = assessment.answers ?? {};
  const modality = assessment.modality && assessment.modality !== 'por_clasificar' ? OPPORTUNITY_MODALITY_LABEL[assessment.modality] : null;
  const numbers = [
    ['Oportunidad', percent(answers.oportunidad)],
    ['Espera respuesta', percent(answers.espera)],
    ['Venta o spam', percent(answers.venta)],
  ].filter((pair): pair is [string, string] => Boolean(pair[1]));
  const quiet = !assessment.opportunity && !assessment.awaiting_reply && !assessment.pitch;
  return (
    <div className="persona-field">
      <div className="persona-chips">
        {assessment.opportunity ? <Badge tone="ok">{modality ? `Posible oportunidad · ${modality}` : 'Posible oportunidad'}</Badge> : null}
        {assessment.awaiting_reply ? <Badge tone="warn">Espera tu respuesta</Badge> : null}
        {assessment.pitch ? <LabelChip tone="muted">Parece venta o spam</LabelChip> : null}
        {quiet ? <LabelChip tone="muted">Sin señales de negocio ni respuesta pendiente</LabelChip> : null}
      </div>
      {numbers.length ? <p className="persona-meta">{numbers.map(([label, value]) => `${label} ${value}`).join(' · ')}</p> : null}
    </div>
  );
}

function Messages({ conversation, name }: { conversation: Conversation; name: string }) {
  if (!conversation.messages.length) {
    return conversation.last_message_preview ? (
      <blockquote className="persona-quote">“{conversation.last_message_preview}”</blockquote>
    ) : (
      <p className="persona-meta">Sin mensajes recientes.</p>
    );
  }
  return (
    <ul className="persona-messages" aria-label="Últimos mensajes">
      {conversation.messages.map((message) => (
        <li key={message.id} className={message.from_me ? 'mine' : undefined}>
          <p className="persona-meta">
            {message.from_me ? 'Tú' : name}
            {message.at ? (
              <>
                {' · '}
                <time dateTime={message.at}>{messageWhen(message.at)}</time>
              </>
            ) : null}
          </p>
          <p className="persona-text">{messageText(message)}</p>
        </li>
      ))}
    </ul>
  );
}

/** The person card block; `profileUrl` is the fallback link when there is no conversation yet. */
export function ConversationBlock({ conversation, name, profileUrl }: { conversation: Conversation | null | undefined; name: string; profileUrl?: string }) {
  if (!conversation) {
    return (
      <Card tone="dashed" className="persona-block tight">
        <p className="persona-text">Aún no hay una conversación leída con esta persona</p>
        <p className="persona-meta">Cuando el equipo lea tu inbox de LinkedIn verás aquí sus últimos mensajes y su lectura. La app nunca envía mensajes.</p>
        <ExternalLink href={profileUrl}>Abrir en LinkedIn</ExternalLink>
      </Card>
    );
  }
  return (
    <Card className="persona-block tight">
      <TeamRead assessment={conversation.assessment} />
      <Messages conversation={conversation} name={conversation.attendee_name || name} />
      <p className="persona-meta">La app nunca envía mensajes: respondes tú en LinkedIn.</p>
      <ExternalLink href={conversation.chat_url}>Abrir en LinkedIn</ExternalLink>
    </Card>
  );
}
