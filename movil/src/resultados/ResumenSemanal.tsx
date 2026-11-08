// Resultados › «Resumen de la semana»: the weekly summary of the results analyst (GET /resultados/resumen-semanal).
// Gustavo reads it, adopts its proposed orientation (undoable for 5 s) or discards it, and can generate a missing
// one behind the cost confirmation. The same rules and texts as the PWA (compartido/src/logic/resultados.ts).
import { useGenerarResumen, useResumenDecision, useResumenSemanal } from '@compartido/api/hooks';
import type { WeeklySummary, WeeklySummaryGenerate, WeeklySummaryItem } from '@compartido/api/types';
import { formatUsd } from '@compartido/logic/format';
import {
  automaticSentence,
  decidedSentence,
  decisionToast,
  newRequestId,
  RESUMEN_ROLE,
  RESUMEN_ROLE_NAME,
  SUMMARY_LISTS,
  SUMMARY_STATE_BADGE,
  summaryFooter,
  summaryItems,
  summaryPending,
  weekPhrase,
} from '@compartido/logic/resultados';
import { useEffect, useRef, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import Animated, { useAnimatedStyle, withTiming } from 'react-native-reanimated';
import { Icon } from '@/components/icons';
import { AgentPortrait, Badge, Button, Card, ConfirmSheet, EmptyState, EmptyText, ErrorRetry, errorMessage, Fold, FoldIn, Note, Section, Skeleton, T, useToast } from '@/components/ui';
import { haptic, timing } from '@/theme/motion';
import { colors, radius, space } from '@/theme/tokens';

// Built on the JS thread: timing() is not a worklet, and calling it inside a style worklet crashes the app on the UI
// runtime («Tried to synchronously call a Remote Function»).
const FOLD = timing('fold');

function Items({ title, items, empty }: { title: string; items: WeeklySummaryItem[]; empty: string }) {
  return (
    <View style={styles.list}>
      <T variant="etiqueta" soft accessibilityRole="header">
        {title}
      </T>
      {items.length ? (
        items.map((item, index) => (
          <View key={index} style={styles.item}>
            <T>{item.texto}</T>
            {item.cifra ? (
              <T variant="detalle" soft>
                Dato: {item.cifra}
              </T>
            ) : null}
          </View>
        ))
      ) : (
        <T variant="detalle" soft>
          {empty}
        </T>
      )}
    </View>
  );
}

/** The three lists and the warnings: what the data supports, and when it is too thin to conclude. */
function SummaryBody({ summary }: { summary: WeeklySummary }) {
  const analysis = summary.analysis;
  return (
    <>
      {SUMMARY_LISTS.map((list) => (
        <Items key={list.key} title={list.title} items={summaryItems(analysis, list.key)} empty={list.empty} />
      ))}
      {analysis.advertencias?.length ? (
        <Note tone="warn" title="Advertencias">
          {analysis.advertencias.map((warning, index) => (
            <T key={index} variant="detalle">
              {`• ${warning}`}
            </T>
          ))}
        </Note>
      ) : null}
    </>
  );
}

type Decide = (summary: WeeklySummary, decision: 'aplicar' | 'descartar') => void;

/** «Orientación propuesta»: only Gustavo's decision turns it into the team's orientation. */
function Proposal({ summary, onDecide, busy, error }: { summary: WeeklySummary; onDecide: Decide; busy: boolean; error: unknown }) {
  const text = summary.analysis.orientacion_propuesta;
  if (!text) return null;
  return (
    <View style={styles.list}>
      <T variant="etiqueta" soft accessibilityRole="header">
        Orientación propuesta
      </T>
      <View style={styles.quote}>
        <T>{text}</T>
      </View>
      {summaryPending(summary) ? (
        <>
          <T variant="detalle" soft>
            Si la usas, sustituye la orientación del equipo (Ajustes). Podrás deshacerlo durante 5 segundos.
          </T>
          <View style={styles.actions}>
            <Button variant="primary" block disabled={busy} onPress={() => onDecide(summary, 'aplicar')} testID="resumen-usar">
              Usar como orientación
            </Button>
            <Button variant="danger" block disabled={busy} onPress={() => onDecide(summary, 'descartar')} testID="resumen-descartar">
              Descartar
            </Button>
          </View>
          <ErrorRetry error={error} />
        </>
      ) : (
        <T variant="detalle" soft>
          {decidedSentence(summary)}
        </T>
      )}
    </View>
  );
}

function SummaryCard({ summary, onDecide, busy, error }: { summary: WeeklySummary; onDecide: Decide; busy: boolean; error: unknown }) {
  const badge = SUMMARY_STATE_BADGE[summary.state];
  return (
    <Card>
      <View style={styles.cardHead}>
        <T variant="etiqueta" soft style={styles.grow}>
          {summary.label}
        </T>
        {badge ? <Badge tone={badge.tone}>{badge.label}</Badge> : null}
      </View>
      <T variant="subtitulo" accessibilityRole="header">
        {summary.analysis.titular}
      </T>
      <AgentPortrait role={RESUMEN_ROLE} showName name={RESUMEN_ROLE_NAME} />
      <SummaryBody summary={summary} />
      <Proposal summary={summary} onDecide={onDecide} busy={busy} error={error} />
      <T variant="detalle" soft>
        {summaryFooter(summary)}
      </T>
    </Card>
  );
}

/** «Generar ahora» behind the cost confirmation (POST /resultados/resumen-semanal/generar). */
function Generate({ offer }: { offer: WeeklySummaryGenerate }) {
  const generate = useGenerarResumen();
  const [asking, setAsking] = useState(false);
  // One id per intent: a retry after a network error never queues a second summary.
  const [requestId, setRequestId] = useState<string | undefined>(undefined);
  const week = weekPhrase(offer.label);
  if (generate.isSuccess || offer.pending) {
    return <Note tone="info">{`El analista está escribiendo el resumen de ${week}. Tarda uno o dos minutos y aparecerá aquí.`}</Note>;
  }
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
      <Button variant="secondary" block onPress={open}>
        Generar ahora
      </Button>
      {asking ? (
        <ConfirmSheet
          title="Generar el resumen de la semana"
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
          <T>{`El analista lee las cifras de ${week} y escribe qué funcionó, qué no y qué cambiar, con una llamada a Claude.`}</T>
          <Note tone="warn">{`Tiene coste: unos ${formatUsd(offer.estimated_usd)} (como mucho ${formatUsd(offer.max_usd)}), del presupuesto del resumen semanal.`}</Note>
        </ConfirmSheet>
      ) : null}
    </View>
  );
}

/** One previous week, folded: its label, headline and badge; open, the lists and the proposal. */
function Week({ summary }: { summary: WeeklySummary }) {
  const [open, setOpen] = useState(false);
  const badge = SUMMARY_STATE_BADGE[summary.state];
  const chevron = useAnimatedStyle(() => ({ transform: [{ rotate: withTiming(open ? '180deg' : '0deg', FOLD) }] }), [open]);
  return (
    <View style={styles.week}>
      <Pressable accessibilityRole="button" accessibilityState={{ expanded: open }} onPress={() => setOpen((value) => !value)} style={styles.weekHead}>
        <View style={styles.grow}>
          <T variant="detalle" soft>
            {summary.label}
          </T>
          <T>{summary.analysis.titular}</T>
        </View>
        {badge ? <Badge tone={badge.tone}>{badge.label}</Badge> : null}
        <Animated.View style={chevron}>
          <Icon name="chevronDown" size={20} color={colors.inkSoft} />
        </Animated.View>
      </Pressable>
      {open ? (
        <FoldIn style={styles.weekBody}>
          <SummaryBody summary={summary} />
          {summary.analysis.orientacion_propuesta ? (
            <T variant="detalle" soft>
              {`Orientación propuesta: «${summary.analysis.orientacion_propuesta}»`}
            </T>
          ) : null}
          <T variant="detalle" soft>
            {summaryFooter(summary)}
          </T>
        </FoldIn>
      ) : null}
    </View>
  );
}

function PreviousWeeks({ summaries }: { summaries: WeeklySummary[] }) {
  if (!summaries.length) return null;
  return (
    <Fold summary={`Ver semanas anteriores · ${summaries.length}`}>
      {summaries.map((summary) => (
        <Week key={summary.id} summary={summary} />
      ))}
    </Fold>
  );
}

/** Top of Resultados (the weekly_summary notification links to /resultados#resumen). */
export function ResumenSemanal() {
  const query = useResumenSemanal();
  const decide = useResumenDecision();
  const seen = useResumenDecision();
  const toast = useToast();
  const data = query.data;
  const latest = data?.latest ?? null;
  const markedSeen = useRef<string | null>(null);

  // nuevo → visto once the summary is on screen.
  const latestId = latest?.id;
  const latestState = latest?.state;
  const markSeen = seen.mutate;
  useEffect(() => {
    if (!latestId || latestState !== 'nuevo' || markedSeen.current === latestId) return;
    markedSeen.current = latestId;
    markSeen({ summaryId: latestId, decision: 'visto' });
  }, [latestId, latestState, markSeen]);

  const undo = (summary: WeeklySummary) => {
    decide
      .mutateAsync({ summaryId: summary.id, decision: 'deshacer' })
      .then(() => toast.show('Deshecho'))
      .catch((error: unknown) => {
        haptic('actionError');
        toast.show(errorMessage(error), { tone: 'error' });
      });
  };

  const onDecide: Decide = (summary, decision) => {
    decide
      .mutateAsync({ summaryId: summary.id, decision })
      .then(() => {
        haptic('actionSuccess');
        toast.show(decisionToast(decision), { undo: () => undo(summary) });
      })
      .catch(() => {
        // Shown under the buttons (decide.error).
        haptic('actionError');
      });
  };

  let content;
  if (!data) {
    content = query.isError ? (
      <T variant="detalle" soft>
        No se pudo cargar el resumen de la semana.
      </T>
    ) : (
      <Skeleton variant="card" label="Cargando el resumen de la semana…" />
    );
  } else {
    const offer = data.generate;
    const missingWeek = offer.available || offer.pending ? offer : null;
    const automatic = automaticSentence(offer);
    content = (
      <>
        {latest ? (
          <>
            {missingWeek && latest.week_start !== offer.week_start ? <Note tone="info">{`Aún no hay resumen de ${weekPhrase(offer.label)}.${automatic}`}</Note> : null}
            {missingWeek ? <Generate offer={offer} /> : null}
            <SummaryCard summary={latest} onDecide={onDecide} busy={decide.isPending} error={decide.error} />
          </>
        ) : (
          <Card>
            <EmptyState title="Todavía no hay resúmenes semanales" action={missingWeek ? <Generate offer={offer} /> : undefined}>
              <EmptyText>{`Cada semana el analista resume qué funcionó, qué no y qué cambiar, con las cifras de la semana.${automatic}`}</EmptyText>
            </EmptyState>
          </Card>
        )}
        <PreviousWeeks summaries={data.previous} />
      </>
    );
  }

  return (
    <View testID="resumen-semanal">
      <Section label="Resumen de la semana">{content}</Section>
    </View>
  );
}

const styles = StyleSheet.create({
  grow: { flex: 1, gap: 2 },
  list: { gap: space[2] },
  item: { gap: 2 },
  cardHead: { flexDirection: 'row', alignItems: 'center', gap: space[2] },
  quote: { borderLeftWidth: 3, borderLeftColor: colors.brand, paddingLeft: space[3], paddingVertical: space[1] },
  actions: { gap: space[2] },
  week: { borderTopWidth: 1, borderTopColor: colors.line },
  weekHead: { minHeight: 48, flexDirection: 'row', alignItems: 'center', gap: space[2], paddingVertical: space[2], borderRadius: radius.sm },
  weekBody: { gap: space[3], paddingBottom: space[3] },
});
