import { ProfileProposal } from './ProfileProposal';
import { ReferentDecision } from './ReferentDecision';
import { useEffect, useId, useRef, useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { useTurnoAction } from '../../api/hooks';
import type { TurnoAction, TurnoCard, TurnoCardType, TurnoOpportunity, TurnoPriority } from '../../api/types';
import { turnoAnchor } from '../../components/Layout';
import { APPROVED_MESSAGE } from '../calendario/events';
import { IconAviso, IconCalendario, IconCheck, IconConversacion, IconPerfil, IconPregunta, IconResultados } from '../../components/icons';
import { AgentPortrait, Avatar, Badge, Button, ButtonLink, ConfirmModal, CopyButton, ErrorRetry, ExternalLink, isHttps, LabelChip, useToast } from '../../components/ui';
import { CONTACT_MODALITY_LABEL, CONTACT_ROLE_LABEL, labelOf } from '../../lib/format';
import { messageText } from '../personas/ConversationBlock';
import { OportunidadForm } from '../personas/OportunidadForm';
import { createdText, dayAndTime, deadlineInfo, extras, longDate, PRIORITY_LABEL } from './model';
import { QuestionForm } from './QuestionForm';
import type { ObserveCard } from './useSeenCards';

const TYPE_LABEL: Record<TurnoCardType, string> = {
  referente: 'Referentes del mes',
  experimento: 'Experimento',
  aviso: 'Aviso',
  pregunta: 'Pregunta',
  perfil: 'Perfil',
  conversacion: 'Conversación',
  mensaje: 'Mensaje sugerido',
  fecha: 'Fecha pedida',
  resumen: 'Resumen semanal',
  aprobacion: 'Aprobación',
};

const TYPE_ICON: Record<TurnoCardType, typeof IconAviso> = {
  referente: IconAviso,
  experimento: IconAviso,
  aviso: IconAviso,
  pregunta: IconPregunta,
  perfil: IconPerfil,
  conversacion: IconConversacion,
  mensaje: IconConversacion,
  fecha: IconCalendario,
  resumen: IconResultados,
  aprobacion: IconCheck,
};

/** Colour of the type label: alerta for urgent notices, info for questions and conversations, hondo for profile tasks. */
function typeTone(card: TurnoCard, priority: TurnoPriority | null): string {
  if (!priority) return 'suave';
  if (card.type === 'aviso') return priority === 'urgente' ? 'alerta' : 'suave';
  if (card.type === 'perfil' || card.type === 'aprobacion') return 'hondo';
  return 'info';
}

/** «Comprueba si salió tu comentario» for an uncertain action; the backend's title otherwise. */
const UNCERTAIN_TITLE: Record<string, string> = {
  'INT-03': 'Comprueba si salió tu comentario',
  'INT-04': 'Comprueba si salió tu respuesta',
  'INT-02': 'Comprueba si salió tu reacción',
  'CONT-09': 'Comprueba si salió tu publicación',
  'RED-01': 'Comprueba si se aplicó el seguimiento',
  'RED-02': 'Comprueba si salió tu invitación',
  'RED-04': 'Comprueba si se aceptó la invitación',
};

function cardTitle(card: TurnoCard): string {
  if (card.question?.question) return card.question.question;
  if (card.attempt && UNCERTAIN_TITLE[card.attempt.capability]) return UNCERTAIN_TITLE[card.attempt.capability]!;
  return card.title;
}

// ---------------------------------------------------------------- actions

/** A view of the office («/resultados#resumen»): navigates inside the app. API routes (the LinkedIn OAuth start) stay full navigations. */
const isInApp = (href: string) => href.startsWith('/') && !href.startsWith('//') && !href.startsWith('/api/');
const isMachineResume = (action: TurnoAction) => action.endpoint === '/api/v1/operador/control' && action.body?.paused === false;
const isResolve = (action: TurnoAction) => Boolean(action.endpoint?.endsWith('/resolve'));
const isConversationClose = (action: TurnoAction) => Boolean(action.endpoint?.startsWith('/api/v1/conversaciones/') && action.endpoint.endsWith('/cerrar'));
const isMessageClose = (action: TurnoAction) => Boolean(action.endpoint?.startsWith('/api/v1/respuestas/') && action.endpoint.endsWith('/mensaje'));
const isApprove = (action: TurnoAction) => Boolean(action.endpoint?.startsWith('/api/v1/operador/actions/') && action.endpoint.endsWith('/approve'));
const isReject = (action: TurnoAction) => Boolean(action.endpoint?.startsWith('/api/v1/operador/actions/') && action.endpoint.endsWith('/reject'));

function successMessage(action: TurnoAction): string {
  if (isResolve(action)) return action.body?.outcome === 'failed' ? 'Anotado: no se aplicó' : 'Anotado: se aplicó';
  if (isConversationClose(action)) return action.body?.how === 'no_responder' ? 'Anotado: no responderás' : 'Anotado: respondiste';
  if (isMessageClose(action)) return action.body?.how === 'no' ? 'Anotado: no le escribirás' : 'Anotado: le escribiste';
  if (isApprove(action)) return APPROVED_MESSAGE;
  if (isReject(action)) return 'Vetada';
  if (isMachineResume(action)) return 'Máquina reanudada';
  if (action.endpoint?.endsWith('/pause') && action.body?.paused === false) return 'Cuenta reanudada';
  if (action.endpoint?.startsWith('/api/v1/resultados/resumen-semanal/') && action.endpoint.endsWith('/descartar')) return 'Resumen descartado';
  return 'Hecho';
}

interface ModalSpec {
  title: string;
  text: ReactNode;
  note: 'required' | 'optional';
  noteLabel: string;
  placeholder?: string;
}

/** Which actions ask first: a required note (uncertain actions and any `note_required`) or the optional reason to resume. */
function modalFor(action: TurnoAction): ModalSpec | null {
  if (isReject(action)) {
    return {
      title: 'Vetar la acción',
      text: 'No saldrá. Vetar una acción de red descarta a esa persona para siempre: el equipo no la volverá a proponer.',
      note: 'required',
      noteLabel: 'Nota',
      placeholder: 'Por qué no debe salir',
    };
  }
  if (isResolve(action) && action.note_required) {
    const applied = action.body?.outcome !== 'failed';
    return {
      title: applied ? 'Confirmar que se aplicó' : 'Confirmar que no se aplicó',
      text: applied ? 'La acción queda como hecha en LinkedIn.' : 'La acción queda como no aplicada.',
      note: 'required',
      noteLabel: 'Qué comprobaste',
      placeholder: applied ? 'Por ejemplo: el comentario aparece en el post.' : 'Por ejemplo: no aparece en el post ni en mi actividad.',
    };
  }
  if (action.note_required) return { title: action.label, text: null, note: 'required', noteLabel: 'Nota' };
  if (action.note_optional) {
    return {
      title: action.label,
      text: isConversationClose(action)
        ? 'La tarjeta sale de la Bandeja hasta que te vuelva a escribir. Nadie le responde por ti.'
        : isMessageClose(action)
          ? 'La tarjeta sale de la Bandeja. Nadie le escribe por ti.'
          : null,
      note: 'optional',
      noteLabel: 'Motivo',
    };
  }
  if (isMachineResume(action)) {
    return { title: 'Reanudar la máquina', text: 'El equipo vuelve a trabajar dentro de la ventana horaria y los topes.', note: 'optional', noteLabel: 'Motivo' };
  }
  return null;
}

/** The card's actions: POSTs through useTurnoAction (with their modal when they need one) and `href` as full navigations. */
function CardActions({ card }: { card: TurnoCard }) {
  const toast = useToast();
  const run = useTurnoAction();
  const [asking, setAsking] = useState<TurnoAction | null>(null);
  const [running, setRunning] = useState<TurnoAction | null>(null);
  const [opportunity, setOpportunity] = useState<TurnoOpportunity | null>(null);
  const actions = card.actions ?? [];
  if (!actions.length) return null;

  const execute = async (action: TurnoAction, note?: string) => {
    setRunning(action);
    try {
      // The machine takes its optional reason as `reason`, not `note`.
      if (isMachineResume(action)) await run.mutateAsync({ action: { ...action, body: { ...action.body, ...(note ? { reason: note } : {}) } } });
      else await run.mutateAsync({ action, note });
      setAsking(null);
      toast.show(successMessage(action));
    } catch {
      // Shown in the modal, or under the buttons.
    } finally {
      setRunning(null);
    }
  };

  const primaryIndex = Math.max(
    0,
    actions.findIndex((action) => action.primary),
  );
  const ordered = [actions[primaryIndex]!, ...actions.filter((_, index) => index !== primaryIndex)];
  const [first, second, ...rest] = ordered;

  const render = (action: TurnoAction, variant: 'primary' | 'secondary' | 'ghost') => {
    if (action.opportunity) {
      const prefill = action.opportunity;
      return (
        <Button key={action.label} variant={variant} block={variant !== 'ghost'} onClick={() => setOpportunity(prefill)}>
          {action.label}
        </Button>
      );
    }
    if (action.href && isInApp(action.href)) {
      return (
        <ButtonLink key={action.label} to={action.href} variant={variant} block={variant !== 'ghost'}>
          {action.label}
        </ButtonLink>
      );
    }
    if (action.href) {
      const external = isHttps(action.href);
      return (
        <ButtonLink
          key={action.label}
          href={action.href}
          variant={variant}
          block={variant !== 'ghost'}
          {...(external ? { target: '_blank', rel: 'noopener noreferrer' } : {})}
        >
          {action.label}
        </ButtonLink>
      );
    }
    const spec = modalFor(action);
    return (
      <Button
        key={action.label}
        variant={variant}
        block={variant !== 'ghost'}
        disabled={run.isPending}
        loading={running === action && !spec}
        onClick={() => {
          run.reset();
          if (spec) setAsking(action);
          else void execute(action);
        }}
      >
        {action.label}
      </Button>
    );
  };

  const spec = asking ? modalFor(asking) : null;
  return (
    <div className="turno-actions">
      {first ? render(first, first.primary ? 'primary' : 'secondary') : null}
      {second ? render(second, 'secondary') : null}
      {rest.length ? <div className="turno-ghosts">{rest.map((action) => render(action, 'ghost'))}</div> : null}
      {!asking ? <ErrorRetry error={run.error} /> : null}
      {asking && spec ? (
        <ConfirmModal
          title={spec.title}
          confirmLabel={asking.label}
          note={spec.note}
          noteLabel={spec.noteLabel}
          notePlaceholder={spec.placeholder}
          busy={run.isPending}
          error={run.error}
          onConfirm={(note) => void execute(asking, note)}
          onClose={() => {
            run.reset();
            setAsking(null);
          }}
        >
          {spec.text ? <p>{spec.text}</p> : null}
        </ConfirmModal>
      ) : null}
      {opportunity ? (
        <OportunidadForm
          person={{ id: opportunity.contact, display_name: opportunity.display_name, headline: opportunity.headline, modality: opportunity.modality }}
          defaults={{ channel: opportunity.channel, notes: opportunity.notes }}
          onClose={() => setOpportunity(null)}
        />
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------- bodies

/** What an uncertain action tried: kind, target and time, the text or reaction, and «Ver en LinkedIn». */
function Attempt({ card }: { card: TurnoCard }) {
  const attempt = card.attempt!;
  const target = attempt.target;
  const where = !target
    ? ''
    : target.kind === 'post'
      ? ` en el post de ${target.name}`
      : target.kind === 'own'
        ? ' en tu perfil'
        : target.name
          ? ` · ${target.name}`
          : '';
  const when = dayAndTime(attempt.at);
  return (
    <div className="turno-block wide">
      <p className="turno-meta">
        {attempt.label}
        {where}
        {when ? ` · ${when}` : ''}
      </p>
      {attempt.text ? <blockquote className="quote">“{attempt.text}”</blockquote> : null}
      {attempt.reaction ? <p className="turno-body">Reacción: {attempt.reaction}</p> : null}
      {card.body ? <p className="turno-body">{card.body}</p> : null}
      <ExternalLink href={attempt.url ?? target?.url}>Ver en LinkedIn</ExternalLink>
    </div>
  );
}

function NoticeBody({ card }: { card: TurnoCard }) {
  const extra = extras(card);
  if (card.id === 'linkedin_expiring' && extra.expires_at && typeof extra.days_left === 'number') {
    const days = extra.days_left;
    return (
      <p className="turno-body">
        El permiso para publicar caduca el {longDate(extra.expires_at)} ({days === 1 ? 'queda 1 día' : `quedan ${days} días`}). LinkedIn no deja renovarlo solo.
      </p>
    );
  }
  return (
    <>
      {card.body ? <p className="turno-body">{card.body}</p> : null}
      {card.id === 'machine_paused' && (extra.stopped_by || card.created_at) ? (
        <p className="turno-meta">
          Detenida{extra.stopped_by ? ` por ${extra.stopped_by}` : ''}
          {card.created_at ? ` · ${dayAndTime(card.created_at)}` : ''}
        </p>
      ) : null}
    </>
  );
}

/** C2 «Conversación que te toca»: who wrote, why it matters (the team's read), the latest message, and a reminder that
 * Gustavo answers on LinkedIn himself. */
function ConversationBody({ card }: { card: TurnoCard }) {
  const conversation = card.conversation!;
  const person = conversation.person;
  const name = person?.display_name || conversation.attendee_name || 'Esta persona';
  const last = [...conversation.messages].reverse().find((message) => !message.from_me);
  const when = dayAndTime(last?.at);
  return (
    <>
      <div className="turno-person">
        <Avatar name={name} size={40} />
        <div className="turno-person-text">
          {person ? <Link to={`/personas/${person.id}`}>{name}</Link> : <p className="turno-body">{name}</p>}
          {person?.headline ? <p className="turno-meta">{person.headline}</p> : null}
          {person?.role || person?.modality ? (
            <span className="turno-chips">
              {person.role ? <LabelChip tone="info">{labelOf(CONTACT_ROLE_LABEL, person.role)}</LabelChip> : null}
              {person.modality ? <LabelChip tone="muted">{labelOf(CONTACT_MODALITY_LABEL, person.modality)}</LabelChip> : null}
            </span>
          ) : null}
        </div>
      </div>
      {card.body ? (
        <div className="turno-block">
          <p className="turno-label">Por qué importa</p>
          <p className="turno-body">{card.body}</p>
        </div>
      ) : null}
      {last ? (
        <div className="turno-block">
          <p className="turno-label">Último mensaje{when ? ` · ${when}` : ''}</p>
          <blockquote className="quote">“{messageText(last)}”</blockquote>
        </div>
      ) : null}
      <p className="turno-meta">La app nunca envía mensajes: respondes tú en LinkedIn.</p>
    </>
  );
}

/** «Mensaje sugerido»: someone who conversed with the team on his post is now a connection. The team drafts a first
 * private message; Gustavo copies it and sends it himself from LinkedIn. */
function MessageBody({ card }: { card: TurnoCard }) {
  const message = card.message!;
  const person = message.person;
  return (
    <>
      <div className="turno-person">
        <Avatar name={person.display_name} size={40} />
        <div className="turno-person-text">
          <Link to={`/personas/${person.id}`}>{person.display_name}</Link>
          {person.headline ? <p className="turno-meta">{person.headline}</p> : null}
          {person.role ? (
            <span className="turno-chips">
              <LabelChip tone="info">{labelOf(CONTACT_ROLE_LABEL, person.role)}</LabelChip>
            </span>
          ) : null}
        </div>
      </div>
      <div className="turno-block">
        <p className="turno-label">Lo que comentó en tu post</p>
        <blockquote className="quote">“{message.comment}”</blockquote>
      </div>
      {message.reply ? (
        <div className="turno-block">
          <p className="turno-label">Lo que le respondió el equipo</p>
          <blockquote className="quote">“{message.reply}”</blockquote>
        </div>
      ) : null}
      <div className="turno-block">
        <p className="turno-label">Mensaje sugerido</p>
        <p className="turno-body" data-testid="suggested-message">
          {message.text}
        </p>
        <CopyButton text={message.text} data-testid="copy-suggested-message" />
      </div>
      <p className="turno-meta">La app nunca envía mensajes: lo envías tú desde LinkedIn.</p>
    </>
  );
}

function QuestionBody({ card }: { card: TurnoCard }) {
  const question = card.question!;
  const purpose = question.purpose || card.body;
  return (
    <>
      {purpose ? (
        <div className="turno-block">
          <p className="turno-label">Para qué</p>
          <p className="turno-body suave">{purpose}</p>
        </div>
      ) : null}
      <QuestionForm question={question} />
    </>
  );
}

// ---------------------------------------------------------------- card

export interface TurnoCardViewProps {
  card: TurnoCard;
  /** null for an expired card (neutral tone). */
  priority: TurnoPriority | null;
  /** Shows «NUEVA». */
  isNew?: boolean;
  /** Reports the card as seen once it is on screen (only while it is new). */
  observe?: ObserveCard;
}

/** A Tu turno card: type, priority, deadline, who asks, title, body by type, actions and «Creada hace X». */
export function TurnoCardView({ card, priority, isNew = false, observe }: TurnoCardViewProps) {
  const ref = useRef<HTMLElement>(null);
  const titleId = useId();
  useEffect(() => {
    if (!observe || !isNew) return;
    return observe(card.id, ref.current);
  }, [observe, isNew, card.id]);

  const expired = priority === null;
  const deadline = expired ? null : deadlineInfo(card);
  const created = createdText(card.created_at);
  const Icon = TYPE_ICON[card.type] ?? IconAviso;
  const tone = priority === 'urgente' ? 'tone-bad' : '';

  return (
    <article ref={ref} id={turnoAnchor(card.id)} className={['card', 'turno-card', tone].filter(Boolean).join(' ')} aria-labelledby={titleId}>
      <div className="turno-head">
        <p className="turno-type" data-tone={typeTone(card, priority)}>
          <Icon size={18} />
          {TYPE_LABEL[card.type] ?? 'Aviso'}
        </p>
        <span className="turno-badges">
          {isNew ? <Badge tone="ok">Nueva</Badge> : null}
          {priority === 'urgente' ? (
            <Badge tone="bad" solid>
              {PRIORITY_LABEL.urgente}
            </Badge>
          ) : null}
          {priority === 'importante' ? <Badge tone="warn">{PRIORITY_LABEL.importante}</Badge> : null}
          {priority === 'cuando_puedas' ? <Badge tone="info">{PRIORITY_LABEL.cuando_puedas}</Badge> : null}
          {expired ? <Badge tone="muted">Caducada</Badge> : null}
        </span>
      </div>
      {deadline ? <p className={deadline.soon ? 'turno-deadline soon' : 'turno-deadline'}>{deadline.text}</p> : null}
      {expired ? <p className="turno-meta">Ya no es urgente, pero sigue siendo útil.</p> : null}
      <AgentPortrait role={card.agent} showName name={card.agent_label} />
      <h3 className="turno-title" id={titleId}>
        {cardTitle(card)}
      </h3>
      {card.profile_id ? (
        <ProfileProposal id={card.profile_id} />
      ) : card.referent_change || card.referent_experiment ? (
        <ReferentDecision card={card} />
      ) : card.question ? (
        <QuestionBody card={card} />
      ) : card.attempt ? (
        <Attempt card={card} />
      ) : card.conversation ? (
        <ConversationBody card={card} />
      ) : card.message ? (
        <MessageBody card={card} />
      ) : (
        <NoticeBody card={card} />
      )}
      {card.question ? null : <CardActions card={card} />}
      {created ? <p className="card-footer">{created}</p> : null}
    </article>
  );
}
