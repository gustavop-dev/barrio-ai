// Resultados › «Revisión mensual» (?pestana=mensual): the monthly review of the results analyst
// (GET /resultados/revision-mensual). Gustavo reads what happened in the month, what worked, what did not and what
// came of last month's changes, and decides each proposed strategy change apart: «Aprobar», «Editar y aprobar» or
// «Rechazar» (the same decisions as its Tu turno card); an approved one can be reverted here. «Generar ahora» sits
// behind the cost confirmation, as the weekly summary's. The rules and texts: compartido/src/logic/revisionMensual.ts.
// RevisionResumen is its teaser at the top of «Panorama».
import { useCambioEstrategia, useGenerarRevision, useRevisionMensual, useRevisionVista, type CambioDecision } from '@compartido/api/hooks';
import type { MonthlyReview, MonthlyReviewGenerate, StrategyChange } from '@compartido/api/types';
import { newRequestId, RESUMEN_ROLE, RESUMEN_ROLE_NAME } from '@compartido/logic/resultados';
import {
  APPROVE_HINT,
  automaticSentence,
  baselineText,
  changeBadge,
  changeToast,
  decidedSentence,
  EDIT_CHANGE_TEXT,
  EMPTY_TITLE,
  emptyText,
  evidenceLines,
  generateCost,
  generateText,
  generatingText,
  metricName,
  outcomeFigures,
  partialSentence,
  pendingSentence,
  REJECT_CHANGE_TEXT,
  REVERT_CHANGE_TEXT,
  REVIEW_LISTS,
  REVIEW_STATE_BADGE,
  reviewFooter,
  reviewItems,
  reviewLines,
  reviewPhrase,
  STRATEGY_CHANGE_MAX,
  verdictBadge,
} from '@compartido/logic/revisionMensual';
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Pressable, RefreshControl, ScrollView, StyleSheet, View } from 'react-native';
import Animated, { useAnimatedStyle, withTiming } from 'react-native-reanimated';
import { Icon } from '@/components/icons';
import { useContentInsets } from '@/components/shell/useContentInsets';
import { AgentPortrait, Badge, Button, Card, ConfirmSheet, EmptyState, EmptyText, ErrorRetry, Fold, FoldIn, Note, pageContent, Section, Skeleton, T, useToast } from '@/components/ui';
import { haptic, timing } from '@/theme/motion';
import { colors, radius, space } from '@/theme/tokens';
import { Items } from './ResumenSemanal';

// Built on the JS thread: timing() is not a worklet (see ResumenSemanal.tsx).
const FOLD = timing('fold');

function Quote({ children }: { children: string }) {
  return (
    <View style={styles.quote}>
      <T>{children}</T>
    </View>
  );
}

function Lines({ title, lines }: { title: string; lines: string[] }) {
  if (!lines.length) return null;
  return (
    <View style={styles.list}>
      <T variant="etiqueta" soft accessibilityRole="header">
        {title}
      </T>
      {lines.map((line, index) => (
        <T key={index}>{`• ${line}`}</T>
      ))}
    </View>
  );
}

/** «Qué pasó con los cambios del mes anterior»: each approved change with its verdict. */
function PreviousChanges({ review }: { review: MonthlyReview }) {
  const previous = Array.isArray(review.cambios_previos) ? review.cambios_previos : [];
  if (!previous.length) return null;
  return (
    <View style={styles.list} testID="revision-cambios-previos">
      <T variant="etiqueta" soft accessibilityRole="header">
        Qué pasó con los cambios del mes anterior
      </T>
      {previous.map((change, index) => {
        const verdict = verdictBadge(change.veredicto);
        return (
          <View key={change.id || index} style={styles.item} testID={`revision-previo-${change.id || index}`}>
            <View style={styles.cardHead}>
              <T style={styles.grow}>{change.titulo}</T>
              <Badge tone={verdict.tone}>{verdict.label}</Badge>
            </View>
            {change.texto ? (
              <T variant="detalle" soft>
                {change.texto}
              </T>
            ) : null}
            {change.cifra ? (
              <T variant="detalle" soft>
                Dato: {change.cifra}
              </T>
            ) : null}
          </View>
        );
      })}
    </View>
  );
}

/** The report: the three lists, what cannot be concluded yet, last month's changes and the data warnings. */
function ReviewBody({ review }: { review: MonthlyReview }) {
  const warnings = reviewLines(review.advertencias);
  const notices = reviewLines(review.avisos);
  return (
    <>
      {REVIEW_LISTS.map((list) => (
        <Items key={list.key} title={list.title} items={reviewItems(review, list.key)} empty={list.empty} />
      ))}
      <Lines title="Lo que todavía no se puede concluir" lines={reviewLines(review.no_concluyente)} />
      <PreviousChanges review={review} />
      {warnings.length ? (
        <Note tone="warn" title="Advertencias">
          {warnings.map((warning, index) => (
            <T key={index} variant="detalle">
              {`• ${warning}`}
            </T>
          ))}
        </Note>
      ) : null}
      {notices.length ? (
        <Fold summary={`Avisos sobre los datos · ${notices.length}`}>
          {notices.map((notice, index) => (
            <T key={index} variant="detalle" soft>
              {`• ${notice}`}
            </T>
          ))}
        </Fold>
      ) : null}
    </>
  );
}

/** Label, the «Nueva» and «Parcial» chips (and why it is partial) and the headline. */
function ReviewHead({ review }: { review: MonthlyReview }) {
  const badge = REVIEW_STATE_BADGE[review.state] ?? null;
  const partial = partialSentence(review);
  return (
    <>
      <View style={styles.cardHead}>
        <T variant="etiqueta" soft style={styles.grow}>
          {review.label}
        </T>
        {review.partial ? <Badge tone="warn">Parcial</Badge> : null}
        {badge ? <Badge tone={badge.tone}>{badge.label}</Badge> : null}
      </View>
      {partial ? (
        <T variant="detalle" soft testID="revision-parcial">
          {partial}
        </T>
      ) : null}
      {review.titular ? (
        <T variant="subtitulo" accessibilityRole="header">
          {review.titular}
        </T>
      ) : null}
    </>
  );
}

function ReviewCard({ review }: { review: MonthlyReview }) {
  return (
    <Card>
      <ReviewHead review={review} />
      <AgentPortrait role={RESUMEN_ROLE} showName name={RESUMEN_ROLE_NAME} />
      {review.metodo ? (
        <T variant="detalle" soft>
          {review.metodo}
        </T>
      ) : null}
      <ReviewBody review={review} />
      <T variant="detalle" soft>
        {reviewFooter(review)}
      </T>
    </Card>
  );
}

type Asking = 'editar' | 'rechazar' | 'revertir';

/** One proposed change: what it says, why, what it rests on and how it will be measured; his decision or its result. */
function ChangeCard({ change }: { change: StrategyChange }) {
  const decide = useCambioEstrategia();
  const toast = useToast();
  const [asking, setAsking] = useState<Asking | null>(null);
  const badge = changeBadge(change);
  const decided = decidedSentence(change);
  const evidence = evidenceLines(change);
  const metric = metricName(change);
  const baseline = baselineText(change);
  const outcome = change.outcome ?? null;
  const verdict = outcome ? verdictBadge(outcome.veredicto) : null;
  const figures = outcome ? outcomeFigures(outcome) : null;
  const approved = change.state === 'aprobado';
  const busy = decide.isPending;

  const run = (input: CambioDecision) => {
    decide
      .mutateAsync(input)
      .then((answer) => {
        haptic('actionSuccess');
        setAsking(null);
        toast.show(changeToast(input.decision, answer));
      })
      .catch(() => {
        // Shown in the sheet, or under the buttons («Aprobar» asks nothing first).
        haptic('actionError');
      });
  };
  const ask = (next: Asking) => {
    decide.reset();
    setAsking(next);
  };
  const close = () => {
    setAsking(null);
    decide.reset();
  };

  return (
    <View testID={`revision-cambio-${change.id}`}>
      <Card>
        <View style={styles.cardHead}>
          <T variant="subtitulo" accessibilityRole="header" style={styles.grow}>
            {change.title}
          </T>
          <Badge tone={badge.tone}>{badge.label}</Badge>
        </View>
        {decided ? (
          <View style={styles.list}>
            <T variant="detalle" soft>
              {decided}
            </T>
            {approved && change.final_text ? <Quote>{change.final_text}</Quote> : null}
            {approved && change.final_text && change.proposal && change.final_text !== change.proposal ? (
              <T variant="detalle" soft>{`Propuesta original: «${change.proposal}»`}</T>
            ) : null}
            {change.decision_note ? <T variant="detalle" soft>{`Tu nota: ${change.decision_note}`}</T> : null}
          </View>
        ) : null}
        {!approved && change.proposal ? <Quote>{change.proposal}</Quote> : null}
        {change.reason ? (
          <View style={styles.item}>
            <T variant="etiqueta" soft>
              Por qué
            </T>
            <T>{change.reason}</T>
          </View>
        ) : null}
        {evidence.length ? (
          <View style={styles.item}>
            <T variant="etiqueta" soft>
              En qué se basa
            </T>
            {evidence.map((line, index) => (
              <View key={index}>
                {line.cifra ? <T variant="detalle">{`Dato: ${line.cifra}`}</T> : null}
                {line.comparado ? <T variant="detalle" soft>{`Comparado con: ${line.comparado}`}</T> : null}
              </View>
            ))}
          </View>
        ) : null}
        {change.expected ? (
          <View style={styles.item}>
            <T variant="etiqueta" soft>
              Qué se espera
            </T>
            <T>{change.expected}</T>
          </View>
        ) : null}
        {metric ? (
          <View style={styles.item}>
            <T variant="detalle" soft>{`Se medirá con: ${metric}`}</T>
            {baseline ? (
              <T variant="detalle" soft>
                {baseline}
              </T>
            ) : null}
          </View>
        ) : null}
        {outcome && verdict ? (
          <View style={styles.item} testID={`cambio-resultado-${change.id}`}>
            <View style={styles.cardHead}>
              <T variant="etiqueta" soft style={styles.grow}>
                Qué pasó después
              </T>
              <Badge tone={verdict.tone}>{verdict.label}</Badge>
            </View>
            {outcome.texto ? <T>{outcome.texto}</T> : null}
            {figures ? (
              <T variant="detalle" soft>
                {figures}
              </T>
            ) : null}
          </View>
        ) : null}
        {change.can_decide ? (
          <View style={styles.actions}>
            <T variant="detalle" soft>
              {APPROVE_HINT}
            </T>
            <Button
              variant="primary"
              block
              disabled={busy}
              loading={busy && !asking}
              onPress={() => run({ changeId: change.id, decision: 'aprobar' })}
              testID={`cambio-aprobar-${change.id}`}
            >
              Aprobar
            </Button>
            <Button block disabled={busy} onPress={() => ask('editar')} testID={`cambio-editar-${change.id}`}>
              Editar y aprobar
            </Button>
            <Button variant="danger" block disabled={busy} onPress={() => ask('rechazar')} testID={`cambio-rechazar-${change.id}`}>
              Rechazar
            </Button>
          </View>
        ) : null}
        {change.can_revert ? (
          <Button variant="danger" block disabled={busy} onPress={() => ask('revertir')} testID={`cambio-revertir-${change.id}`}>
            Revertir
          </Button>
        ) : null}
        <ErrorRetry error={asking ? null : decide.error} />
      </Card>
      {asking === 'editar' ? (
        <ConfirmSheet
          title="Editar y aprobar"
          confirmLabel="Aprobar"
          note="required"
          noteLabel="Texto del cambio"
          noteInitial={change.proposal}
          noteMax={STRATEGY_CHANGE_MAX}
          busy={busy}
          error={decide.error}
          onClose={close}
          onConfirm={(text) => run({ changeId: change.id, decision: 'aprobar', text })}
        >
          {EDIT_CHANGE_TEXT}
        </ConfirmSheet>
      ) : null}
      {asking === 'rechazar' ? (
        <ConfirmSheet
          title="Rechazar el cambio"
          confirmLabel="Rechazar"
          tone="danger"
          note="optional"
          noteLabel="Motivo"
          busy={busy}
          error={decide.error}
          onClose={close}
          onConfirm={(note) => run({ changeId: change.id, decision: 'rechazar', note })}
        >
          {REJECT_CHANGE_TEXT}
        </ConfirmSheet>
      ) : null}
      {asking === 'revertir' ? (
        <ConfirmSheet
          title="Revertir el cambio"
          confirmLabel="Revertir"
          tone="danger"
          busy={busy}
          error={decide.error}
          onClose={close}
          onConfirm={() => run({ changeId: change.id, decision: 'revertir' })}
        >
          <T soft>{REVERT_CHANGE_TEXT}</T>
          {change.final_text ? <Quote>{change.final_text}</Quote> : null}
        </ConfirmSheet>
      ) : null}
    </View>
  );
}

/** «Cambios propuestos»: up to three, each decided apart. */
function Changes({ review }: { review: MonthlyReview }) {
  const changes = Array.isArray(review.changes) ? review.changes : [];
  return (
    <Section label="Cambios propuestos" intro={pendingSentence(review)}>
      {changes.map((change) => (
        <ChangeCard key={change.id} change={change} />
      ))}
    </Section>
  );
}

/** «Generar ahora» behind the cost confirmation (POST /resultados/revision-mensual/generar). */
function Generate({ offer }: { offer: MonthlyReviewGenerate }) {
  const generate = useGenerarRevision();
  const [asking, setAsking] = useState(false);
  // One id per intent: a retry after a network error never queues a second review.
  const [requestId, setRequestId] = useState<string | undefined>(undefined);
  if (generate.isSuccess || offer.pending) return <Note tone="info">{generatingText(offer)}</Note>;
  if (!offer.available) return null;
  const open = () => {
    generate.reset();
    setRequestId(newRequestId());
    setAsking(true);
  };
  return (
    <View style={styles.list}>
      {offer.last_error ? (
        <Note tone="warn" title="El último intento no terminó">
          {offer.last_error}
        </Note>
      ) : null}
      <Button variant="secondary" block onPress={open} testID="revision-generar">
        Generar ahora
      </Button>
      {asking ? (
        <ConfirmSheet
          title="Generar la revisión mensual"
          confirmLabel="Generar"
          busy={generate.isPending}
          error={generate.error}
          onClose={() => setAsking(false)}
          onConfirm={() =>
            generate.mutate(requestId, {
              onSuccess: () => {
                haptic('actionSuccess');
                setAsking(false);
              },
              onError: () => haptic('actionError'),
            })
          }
        >
          <T>{generateText(offer)}</T>
          <Note tone="warn">{generateCost(offer)}</Note>
        </ConfirmSheet>
      ) : null}
    </View>
  );
}

/** One previous month, folded: its label and headline; open, the report and its changes (an approved one can still be
 * reverted). */
function Month({ review }: { review: MonthlyReview }) {
  const [open, setOpen] = useState(false);
  const chevron = useAnimatedStyle(() => ({ transform: [{ rotate: withTiming(open ? '180deg' : '0deg', FOLD) }] }), [open]);
  const changes = Array.isArray(review.changes) ? review.changes : [];
  return (
    <View style={styles.month}>
      <Pressable accessibilityRole="button" accessibilityState={{ expanded: open }} onPress={() => setOpen((value) => !value)} style={styles.monthHead}>
        <View style={styles.grow}>
          <T variant="detalle" soft>
            {review.label}
          </T>
          {review.titular ? <T>{review.titular}</T> : null}
        </View>
        {review.partial ? <Badge tone="warn">Parcial</Badge> : null}
        <Animated.View style={chevron}>
          <Icon name="chevronDown" size={20} color={colors.inkSoft} />
        </Animated.View>
      </Pressable>
      {open ? (
        <FoldIn style={styles.monthBody}>
          <ReviewBody review={review} />
          {changes.map((change) => (
            <ChangeCard key={change.id} change={change} />
          ))}
          <T variant="detalle" soft>
            {reviewFooter(review)}
          </T>
        </FoldIn>
      ) : null}
    </View>
  );
}

function PreviousMonths({ reviews }: { reviews: MonthlyReview[] }) {
  if (!reviews.length) return null;
  return (
    <Fold summary={`Ver meses anteriores · ${reviews.length}`}>
      {reviews.map((review) => (
        <Month key={review.id} review={review} />
      ))}
    </Fold>
  );
}

/** The tab «Revisión mensual» of Resultados (the monthly_review notification and «Ver la revisión» lead here). */
export function RevisionMensual({ top }: { top: ReactNode }) {
  const query = useRevisionMensual();
  const seen = useRevisionVista();
  const { bottom } = useContentInsets();
  const [refreshing, setRefreshing] = useState(false);
  const data = query.data;
  const latest = data?.latest ?? null;
  const markedSeen = useRef<string | null>(null);

  // nuevo → visto once the review is on screen.
  const latestId = latest?.id;
  const latestState = latest?.state;
  const markSeen = seen.mutate;
  useEffect(() => {
    if (!latestId || latestState !== 'nuevo' || markedSeen.current === latestId) return;
    markedSeen.current = latestId;
    markSeen(latestId);
  }, [latestId, latestState, markSeen]);

  const refresh = async () => {
    setRefreshing(true);
    try {
      await query.refetch();
    } finally {
      setRefreshing(false);
    }
  };

  let content: ReactNode;
  if (!data) {
    content = query.isError ? (
      <ErrorRetry title="No se pudo cargar la revisión mensual" error={query.error} onRetry={() => void query.refetch()} />
    ) : (
      <Skeleton variant="card" label="Cargando la revisión mensual…" />
    );
  } else {
    const offer = data.generate;
    const missingMonth = offer.available || offer.pending ? offer : null;
    content = (
      <>
        {latest ? (
          <>
            {missingMonth && latest.month_start !== offer.month_start ? (
              <Note tone="info">{`Aún no está ${reviewPhrase(offer.label)}.${automaticSentence(offer)}`}</Note>
            ) : null}
            {missingMonth ? <Generate offer={offer} /> : null}
            <ReviewCard review={latest} />
            <Changes review={latest} />
          </>
        ) : (
          <Card>
            <EmptyState title={EMPTY_TITLE} action={missingMonth ? <Generate offer={offer} /> : undefined}>
              <EmptyText>{emptyText(offer)}</EmptyText>
              {!missingMonth && offer.reason ? <EmptyText>{offer.reason}</EmptyText> : null}
            </EmptyState>
          </Card>
        )}
        <PreviousMonths reviews={Array.isArray(data.previous) ? data.previous : []} />
      </>
    );
  }

  return (
    <ScrollView
      style={styles.screen}
      contentContainerStyle={[pageContent, styles.content, { paddingBottom: bottom }]}
      keyboardShouldPersistTaps="handled"
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => void refresh()} tintColor={colors.brandDeep} colors={[colors.brandDeep]} />}
    >
      {top}
      <View testID="revision-mensual" style={styles.content}>
        {content}
      </View>
    </ScrollView>
  );
}

/** Its teaser at the top of «Panorama», under the weekly summary: only once there is a review. */
export function RevisionResumen({ onOpen }: { onOpen: () => void }) {
  const query = useRevisionMensual();
  const latest = query.data?.latest ?? null;
  if (!latest) return null;
  return (
    <View testID="revision-mensual-resumen">
      <Section label="Revisión mensual">
        <Card>
          <ReviewHead review={latest} />
          <T variant="detalle" soft>
            {pendingSentence(latest)}
          </T>
          <Button variant="secondary" block onPress={onOpen} testID="revision-mensual-abrir">
            Ver la revisión
          </Button>
        </Card>
      </Section>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.paper },
  content: { gap: space[6] },
  grow: { flex: 1, gap: 2 },
  list: { gap: space[2] },
  item: { gap: 2 },
  cardHead: { flexDirection: 'row', alignItems: 'center', gap: space[2] },
  quote: { borderLeftWidth: 3, borderLeftColor: colors.brand, paddingLeft: space[3], paddingVertical: space[1] },
  actions: { gap: space[2] },
  month: { borderTopWidth: 1, borderTopColor: colors.line },
  monthHead: { minHeight: 48, flexDirection: 'row', alignItems: 'center', gap: space[2], paddingVertical: space[2], borderRadius: radius.sm },
  monthBody: { gap: space[3], paddingBottom: space[3] },
});
