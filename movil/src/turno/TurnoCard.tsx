import { ProfileProposal } from './ProfileProposal';
// A Tu turno card (the PWA's TurnoCardView): type, priority, deadline, who asks, title, body by type,
// actions and «Creada hace X», inside a SwipeableCard (right: the primary action; left: «Más tarde»).
// MovTuTurno: once the backend confirms, the button that resolved it turns into a check and the card
// goes 0ff1ce-claro, then it leaves the list (exits.ts runs the steps; a swipe skips the check).
import { usePostponePregunta, useTurnoAction } from '@compartido/api/hooks';
import type { TurnoAction, TurnoCard as TurnoCardData, TurnoOpportunity, TurnoPriority } from '@compartido/api/types';
import { CONTACT_MODALITY_LABEL, CONTACT_ROLE_LABEL, labelOf } from '@compartido/logic/format';
import { messageText } from '@compartido/logic/personas';
import { createdText, dayAndTime, deadlineInfo, extras, longDate, PRIORITY_LABEL } from '@compartido/logic/turno';
import { router } from 'expo-router';
import { useState } from 'react';
import { Linking, Pressable, StyleSheet, View } from 'react-native';
import { Icon } from '@/components/icons';
import { AgentPortrait, Avatar, Badge, Button, Card, ConfirmSheet, ErrorRetry, LabelChip, T, useToast, type ButtonVariant } from '@/components/ui';
import { isHttps, openLink } from '@/navigation';
import { haptic } from '@/theme/motion';
import { colors, space } from '@/theme/tokens';
import { cardTitle, modalFor, orderedActions, successMessage, swipeIntents, TYPE_ICON, TYPE_LABEL, typeTone, withNote, type SwipeIntent } from './actions';
import { DoneButton } from './DoneButton';
import { buttonKey, useTurnoExitsApi, type CardExit } from './exits';
import { OpportunitySheet } from './OpportunitySheet';
import { QuestionForm } from './QuestionForm';
import { SwipeableCard } from './SwipeableCard';
import type { SwipeSide } from './swipe';

const TYPE_COLOR = { suave: colors.inkSoft, alerta: colors.alert, hondo: colors.brandDeep, info: colors.info } as const;

/** Runs card actions: the POST (with its modal when it needs one) and the toasts. Shared by the buttons and the swipe. */
function useActionRunner(card: TurnoCardData) {
  const cardId = card.id;
  const toast = useToast();
  const run = useTurnoAction();
  const exits = useTurnoExitsApi();
  const [asking, setAsking] = useState<TurnoAction | null>(null);
  const [running, setRunning] = useState<TurnoAction | null>(null);

  /** `flown`: a swipe already took the card off screen (no check in the button). */
  const execute = async (action: TurnoAction, note = '', flown = false): Promise<boolean> => {
    setRunning(action);
    exits.begin(cardId);
    try {
      await run.mutateAsync(withNote(action, note));
      setAsking(null);
      haptic('actionSuccess');
      toast.show(successMessage(action));
      exits.resolve(cardId, { kind: 'done', lead: flown ? 'flown' : 'check', by: buttonKey.action(action.label) });
      return true;
    } catch {
      haptic('actionError');
      exits.cancel(cardId);
      return false;
    } finally {
      setRunning(null);
    }
  };

  /** Tap or swipe: ask first when the action needs a note or a confirmation. */
  const start = async (action: TurnoAction, flown = false): Promise<boolean> => {
    run.reset();
    if (modalFor(action, card)) {
      setAsking(action);
      return false;
    }
    return execute(action, '', flown);
  };

  return { run, asking, setAsking, running, execute, start };
}

type Runner = ReturnType<typeof useActionRunner>;

interface CardActionsProps {
  card: TurnoCardData;
  runner: Runner;
  onOpportunity: (prefill: TurnoOpportunity) => void;
  /** The button that resolved the card (`buttonKey`): it shows the check. */
  resolvedBy: string | null;
}

function CardActions({ card, runner, onOpportunity, resolvedBy }: CardActionsProps) {
  const ordered = orderedActions(card.actions ?? []);
  if (!ordered.length) return null;
  const [first, second, ...rest] = ordered;

  const render = (action: TurnoAction, variant: ButtonVariant) => {
    const block = variant !== 'ghost';
    if (resolvedBy === buttonKey.action(action.label)) return <DoneButton key={action.label} label={action.label} block={block} />;
    if (action.opportunity) {
      const prefill = action.opportunity;
      return (
        <Button key={action.label} variant={variant} block={block} onPress={() => onOpportunity(prefill)}>
          {action.label}
        </Button>
      );
    }
    if (action.href) {
      const href = action.href;
      return (
        <Button
          key={action.label}
          variant={variant}
          block={block}
          icon={isHttps(href) || href.startsWith('/api/') ? <Icon name="external" size={18} color={variant === 'primary' ? colors.onBrand : colors.inkSoft} /> : undefined}
          accessibilityHint={href.startsWith('/api/') ? 'Se abre la oficina en el navegador para reconectar con tu sesión' : isHttps(href) ? 'Se abre en el navegador' : undefined}
          onPress={() => openLink(href)}
        >
          {action.label}
        </Button>
      );
    }
    const spec = modalFor(action, card);
    return (
      <Button
        key={action.label}
        variant={variant}
        block={block}
        disabled={runner.run.isPending}
        loading={runner.running === action && !spec}
        onPress={() => void runner.start(action)}
      >
        {action.label}
      </Button>
    );
  };

  return (
    <View style={styles.actions}>
      {first ? render(first, first.primary ? 'primary' : 'secondary') : null}
      {second ? render(second, 'secondary') : null}
      {rest.length ? <View style={styles.ghosts}>{rest.map((action) => render(action, 'ghost'))}</View> : null}
      {!runner.asking ? <ErrorRetry error={runner.run.error} /> : null}
    </View>
  );
}

// ---------------------------------------------------------------- bodies

function Quote({ children }: { children: string }) {
  return (
    <View style={styles.quote}>
      <T>“{children}”</T>
    </View>
  );
}

function Attempt({ card }: { card: TurnoCardData }) {
  const attempt = card.attempt!;
  const target = attempt.target;
  const where = !target ? '' : target.kind === 'post' ? ` en el post de ${target.name}` : target.kind === 'own' ? ' en tu perfil' : target.name ? ` · ${target.name}` : '';
  const when = dayAndTime(attempt.at);
  const url = attempt.url ?? target?.url;
  return (
    <View style={styles.block}>
      <T variant="detalle" soft>
        {attempt.label}
        {where}
        {when ? ` · ${when}` : ''}
      </T>
      {attempt.text ? <Quote>{attempt.text}</Quote> : null}
      {attempt.reaction ? <T>Reacción: {attempt.reaction}</T> : null}
      {card.body ? <T>{card.body}</T> : null}
      {url && isHttps(url) ? (
        <Pressable accessibilityRole="link" accessibilityHint="Se abre en el navegador" onPress={() => void Linking.openURL(url)} style={styles.link}>
          <T color={colors.brandDeep}>Ver en LinkedIn</T>
          <Icon name="external" size={16} color={colors.brandDeep} />
        </Pressable>
      ) : null}
    </View>
  );
}

/** What an approval card asks for: the action and its target, the exact text when there is one, and why the team proposes it. */
function ApprovalBody({ card }: { card: TurnoCardData }) {
  const approval = card.approval!;
  const target = approval.target;
  const where = !target ? '' : target.kind === 'post' ? ` en el post de ${target.name}` : target.kind === 'own' ? '' : target.name ? ` · ${target.name}` : '';
  return (
    <View style={styles.block}>
      <T variant="detalle" soft>
        {approval.label}
        {where}
      </T>
      {target?.kind === 'person' && target.headline ? <T soft>{target.headline}</T> : null}
      {approval.text ? <Quote>{approval.text}</Quote> : null}
      {approval.reaction ? <T>Reacción: {approval.reaction}</T> : null}
      {card.body ? (
        <View style={styles.block}>
          <T variant="etiqueta" soft>
            Por qué
          </T>
          <T>{card.body}</T>
        </View>
      ) : null}
      <T variant="detalle" soft>
        Si no la apruebas, no sale.
      </T>
    </View>
  );
}

function NoticeBody({ card }: { card: TurnoCardData }) {
  const extra = extras(card);
  if (card.id === 'linkedin_expiring' && extra.expires_at && typeof extra.days_left === 'number') {
    const days = extra.days_left;
    return (
      <T>
        El permiso para publicar caduca el {longDate(extra.expires_at)} ({days === 1 ? 'queda 1 día' : `quedan ${days} días`}). LinkedIn no deja renovarlo solo.
      </T>
    );
  }
  return (
    <>
      {card.body ? <T>{card.body}</T> : null}
      {card.id === 'machine_paused' && (extra.stopped_by || card.created_at) ? (
        <T variant="detalle" soft>
          Detenida{extra.stopped_by ? ` por ${extra.stopped_by}` : ''}
          {card.created_at ? ` · ${dayAndTime(card.created_at)}` : ''}
        </T>
      ) : null}
    </>
  );
}

function ConversationBody({ card }: { card: TurnoCardData }) {
  const conversation = card.conversation!;
  const person = conversation.person;
  const name = person?.display_name || conversation.attendee_name || 'Esta persona';
  const last = [...conversation.messages].reverse().find((message) => !message.from_me);
  const when = dayAndTime(last?.at);
  return (
    <>
      <View style={styles.person}>
        <Avatar name={name} />
        <View style={styles.personText}>
          {person ? (
            <Pressable accessibilityRole="link" onPress={() => router.push({ pathname: '/personas/[id]', params: { id: person.id } })}>
              <T color={colors.brandDeep}>{name}</T>
            </Pressable>
          ) : (
            <T>{name}</T>
          )}
          {person?.headline ? (
            <T variant="detalle" soft>
              {person.headline}
            </T>
          ) : null}
          {person?.role || person?.modality ? (
            <View style={styles.chips}>
              {person.role ? <LabelChip tone="info">{labelOf(CONTACT_ROLE_LABEL, person.role)}</LabelChip> : null}
              {person.modality ? <LabelChip tone="muted">{labelOf(CONTACT_MODALITY_LABEL, person.modality)}</LabelChip> : null}
            </View>
          ) : null}
        </View>
      </View>
      {card.body ? (
        <View style={styles.block}>
          <T variant="etiqueta" soft>
            Por qué importa
          </T>
          <T>{card.body}</T>
        </View>
      ) : null}
      {last ? (
        <View style={styles.block}>
          <T variant="etiqueta" soft>
            Último mensaje{when ? ` · ${when}` : ''}
          </T>
          <Quote>{messageText(last)}</Quote>
        </View>
      ) : null}
      <T variant="detalle" soft>
        La app nunca envía mensajes: respondes tú en LinkedIn.
      </T>
    </>
  );
}

function QuestionBody({ card, resolvedBy }: { card: TurnoCardData; resolvedBy: string | null }) {
  const question = card.question!;
  const purpose = question.purpose || card.body;
  return (
    <>
      {purpose ? (
        <View style={styles.block}>
          <T variant="etiqueta" soft>
            Para qué
          </T>
          <T soft>{purpose}</T>
        </View>
      ) : null}
      <QuestionForm question={question} cardId={card.id} resolved={resolvedBy === buttonKey.answer} />
    </>
  );
}

// ---------------------------------------------------------------- card

export interface TurnoCardProps {
  card: TurnoCardData;
  /** null for an expired card (neutral tone, no swipe). */
  priority: TurnoPriority | null;
  /** Shows «NUEVA». */
  isNew?: boolean;
  /** MovTuTurno: the card is on its way out (exits.ts). */
  exit?: CardExit;
}

export function TurnoCard({ card, priority, isNew = false, exit }: TurnoCardProps) {
  const toast = useToast();
  const runner = useActionRunner(card);
  const exits = useTurnoExitsApi();
  const postpone = usePostponePregunta();
  const [opportunity, setOpportunity] = useState<TurnoOpportunity | null>(null);
  const expired = priority === null;
  const deadline = expired ? null : deadlineInfo(card);
  const created = createdText(card.created_at);
  const tone = typeTone(card, priority);
  const intents = swipeIntents(card, expired);

  /** `flown`: the finger swiped the card off screen; false from the screen reader's actions (the card leaves as with its button). */
  const swipe = async (side: SwipeSide, flown: boolean): Promise<boolean> => {
    const intent: SwipeIntent | null = side === 'right' ? intents.right : intents.left;
    if (!intent) return false;
    if (intent.kind === 'run') return runner.start(intent.action, flown);
    exits.begin(card.id);
    try {
      const result = await postpone.mutateAsync(intent.questionId);
      const back = longDate(result?.postponed_until);
      haptic('turnoLater');
      toast.show(back ? `Pospuesta. Vuelve el ${back}` : 'Pospuesta 3 días');
      exits.resolve(card.id, { kind: 'later', lead: flown ? 'flown' : 'slide' });
      return true;
    } catch (error) {
      haptic('actionError');
      exits.cancel(card.id);
      toast.show(error instanceof Error ? error.message : 'No se pudo posponer', { tone: 'error' });
      return false;
    }
  };

  const spec = runner.asking ? modalFor(runner.asking, card) : null;
  // MovTuTurno: after the backend confirms, the resolving button holds a check and the card turns 0ff1ce-claro.
  const resolvedBy = exit && exit.phase !== 'acting' && exit.lead === 'check' ? (exit.by ?? null) : null;

  return (
    <>
      <SwipeableCard testID={`turno-card-${card.id}`} rightLabel={intents.right?.label ?? null} leftLabel={intents.left?.label ?? null} onSwipe={swipe}>
        <Card tone={priority === 'urgente' ? 'bad' : null} style={resolvedBy ? styles.resolved : null}>
          <View style={styles.head}>
            <View style={styles.type}>
              <Icon name={TYPE_ICON[card.type] ?? 'aviso'} size={18} color={TYPE_COLOR[tone]} />
              <T variant="etiqueta" color={TYPE_COLOR[tone]}>
                {TYPE_LABEL[card.type] ?? 'Aviso'}
              </T>
            </View>
            <View style={styles.badges}>
              {isNew ? <Badge tone="ok">Nueva</Badge> : null}
              {priority === 'urgente' ? (
                <Badge tone="bad" solid>
                  {PRIORITY_LABEL.urgente}
                </Badge>
              ) : null}
              {priority === 'importante' ? <Badge tone="warn">{PRIORITY_LABEL.importante}</Badge> : null}
              {priority === 'cuando_puedas' ? <Badge tone="info">{PRIORITY_LABEL.cuando_puedas}</Badge> : null}
              {expired ? <Badge tone="muted">Caducada</Badge> : null}
            </View>
          </View>
          {deadline ? (
            <T variant="detalle" color={deadline.soon ? colors.alert : colors.ink}>
              {deadline.text}
            </T>
          ) : null}
          {expired ? (
            <T variant="detalle" soft>
              Ya no es urgente, pero sigue siendo útil.
            </T>
          ) : null}
          <AgentPortrait role={card.agent} showName name={card.agent_label} />
          <T variant="subtitulo" accessibilityRole="header">
            {cardTitle(card)}
          </T>
          {card.profile_id ? (
            <ProfileProposal id={card.profile_id} />
          ) : card.question ? (
            <QuestionBody card={card} resolvedBy={resolvedBy} />
          ) : card.attempt ? (
            <Attempt card={card} />
          ) : card.conversation ? (
            <ConversationBody card={card} />
          ) : card.approval ? (
            <ApprovalBody card={card} />
          ) : (
            <NoticeBody card={card} />
          )}
          {card.question ? null : <CardActions card={card} runner={runner} onOpportunity={setOpportunity} resolvedBy={resolvedBy} />}
          {created ? (
            <T variant="detalle" soft>
              {created}
            </T>
          ) : null}
        </Card>
      </SwipeableCard>
      {runner.asking && spec ? (
        <ConfirmSheet
          title={spec.title}
          confirmLabel={runner.asking.label}
          note={spec.note}
          noteLabel={spec.noteLabel}
          notePlaceholder={spec.placeholder}
          busy={runner.run.isPending}
          error={runner.run.error}
          onConfirm={(note) => void runner.execute(runner.asking!, note)}
          onClose={() => {
            runner.run.reset();
            runner.setAsking(null);
          }}
        >
          {spec.text ?? undefined}
        </ConfirmSheet>
      ) : null}
      {opportunity ? <OpportunitySheet prefill={opportunity} onClose={() => setOpportunity(null)} /> : null}
    </>
  );
}

const styles = StyleSheet.create({
  head: { flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between', gap: space[2] },
  type: { flexDirection: 'row', alignItems: 'center', gap: 6, flexShrink: 1 },
  badges: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'flex-end', gap: 6, flexShrink: 1 },
  block: { gap: space[1] },
  quote: { paddingLeft: space[3], borderLeftWidth: 3, borderLeftColor: colors.line },
  link: { flexDirection: 'row', alignItems: 'center', gap: space[1], minHeight: 44 },
  person: { flexDirection: 'row', gap: space[3] },
  personText: { flex: 1, gap: 2 },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: space[1] },
  actions: { gap: space[2] },
  ghosts: { flexDirection: 'row', flexWrap: 'wrap', gap: space[2], justifyContent: 'center' },
  resolved: { backgroundColor: colors.brandLight },
});
