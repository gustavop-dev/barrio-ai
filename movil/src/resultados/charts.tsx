// The pieces Resultados draws with: KPI tiles in two columns, chart cards with an ⓘ that opens the definition
// in a sheet, funnels and bar lists, the stacked 60/40 split, and the impressions per post (react-native-svg)
// with the dashed median line, where tapping a bar opens the piece. The numbers come from
// compartido/src/logic/resultados.ts, the same rules as the PWA.
// Motion (MovResultados, CountUp.tsx): the KPI figures and the funnel counts count up, and the bars of the
// funnels and bar lists grow in a cascade.
import {
  barRows,
  formatKpiValue,
  funnelRows,
  impressionsChart,
  kpiDelta,
  kpiState,
  MODALITY_SPLIT_MISSING,
  modalitySplit,
  sparklinePoints,
  type BarInput,
  type FunnelStepInput,
  type KpiUnit,
  type NegocioOn,
} from '@compartido/logic/resultados';
import type { Kpi, Resultados } from '@compartido/api/types';
import { router } from 'expo-router';
import { Children, useState, type ReactNode } from 'react';
import { Pressable, StyleSheet, View, type LayoutChangeEvent } from 'react-native';
import Svg, { Defs, Line, Path, Pattern, Polyline, Rect } from 'react-native-svg';
import { Icon } from '@/components/icons';
import { Sheet, T } from '@/components/ui';
import { colors, radius, space } from '@/theme/tokens';
import { CountUp, GrowBar } from './CountUp';

// ---------------------------------------------------------------- ⓘ definition

/** An ⓘ that opens the definition (and formula) of a KPI, a chart or a compact stat in a sheet. */
export function InfoButton({ label, definition, formula }: { label: string; definition?: string | readonly string[] | null; formula?: string | null }) {
  const [open, setOpen] = useState(false);
  const lines = (typeof definition === 'string' ? [definition] : (definition ?? [])).filter(Boolean);
  if (!lines.length && !formula) return null;
  return (
    <>
      <Pressable accessibilityRole="button" accessibilityLabel={`Definición de ${label}`} onPress={() => setOpen(true)} style={styles.info} hitSlop={4}>
        <Icon name="info" size={18} color={colors.inkSoft} />
      </Pressable>
      {open ? (
        <Sheet label={`Definición de ${label}`} onClose={() => setOpen(false)} testID="definition-sheet">
          <T variant="subtitulo" accessibilityRole="header">
            {label}
          </T>
          {lines.map((line) => (
            <T key={line}>{line}</T>
          ))}
          {formula ? <T soft>Fórmula: {formula}</T> : null}
        </Sheet>
      ) : null}
    </>
  );
}

/** A superficie card with an UPPERCASE title, an optional ⓘ and its content. */
export function ChartCard({ title, definition, formula, children, testID }: { title: string; definition?: string | null; formula?: string | null; children: ReactNode; testID?: string }) {
  return (
    <View style={styles.card} testID={testID}>
      <View style={styles.cardHead}>
        <T variant="etiqueta" soft accessibilityRole="header" style={styles.grow}>
          {title}
        </T>
        <InfoButton label={title} definition={definition} formula={formula} />
      </View>
      {children}
    </View>
  );
}

// ---------------------------------------------------------------- KPI tiles

const DELTA_COLOR = { good: colors.brandDeep, bad: colors.alert, flat: colors.inkSoft } as const;

export interface KpiTileProps {
  label: string;
  /** The KPI of GET /api/v1/resultados. Missing (undefined) reads as «aún no disponible». */
  kpi: Kpi | null | undefined;
  unit?: KpiUnit;
  better?: 'up' | 'down' | 'none';
  deltaAsPercent?: boolean;
  missingText?: string;
  format?: (value: number) => string;
}

export function Sparkline({ points }: { points: string }) {
  return (
    <View accessible={false} importantForAccessibility="no-hide-descendants">
      <Svg width="100%" height={28} viewBox="0 0 100 30" preserveAspectRatio="none">
        <Polyline points={points} fill="none" stroke={colors.brandDeep} strokeWidth={2} vectorEffect="non-scaling-stroke" />
      </Svg>
    </View>
  );
}

/** KPI tile: name with its ⓘ, big value, variation and minichart. A null value is «sin dato»: a dash and the reason, never 0. */
export function KpiTile({ label, kpi, unit = 'number', better = 'up', deltaAsPercent = false, missingText, format }: KpiTileProps) {
  const { available, reason } = kpiState(kpi, missingText);
  const delta = available && kpi ? kpiDelta(kpi, unit, better, deltaAsPercent) : null;
  const points = available && kpi ? sparklinePoints(kpi.series) : null;
  return (
    <View style={styles.kpi} testID={`kpi-${label}`}>
      <View style={styles.cardHead}>
        <T variant="detalle" soft style={styles.grow}>
          {label}
        </T>
        <InfoButton label={label} definition={kpi?.definition} formula={kpi?.formula} />
      </View>
      {available && kpi ? (
        <>
          {format ? (
            // A figure with its own wording («24 de 28») has nothing to count.
            <T variant="titulo">{formatKpiValue(kpi.value as number, unit, format)}</T>
          ) : (
            <CountUp value={kpi.value as number} text={formatKpiValue(kpi.value as number, unit)} unit={unit} testID={`kpi-cifra-${label}`} />
          )}
          {delta ? (
            <T variant="detalle" color={DELTA_COLOR[delta.tone]} accessibilityLabel={delta.spoken}>
              {delta.text}
            </T>
          ) : null}
          {points ? <Sparkline points={points} /> : null}
        </>
      ) : (
        <>
          <T variant="titulo" soft accessibilityLabel="Sin dato">
            —
          </T>
          <T variant="detalle" soft>
            {reason}
          </T>
        </>
      )}
    </View>
  );
}

/** Two columns of tiles (the design at mobile width); an odd last tile keeps half the width. */
export function KpiGrid({ children }: { children: ReactNode }) {
  const items = Children.toArray(children);
  const rows: ReactNode[][] = [];
  for (let index = 0; index < items.length; index += 2) rows.push(items.slice(index, index + 2));
  return (
    <View style={styles.grid}>
      {rows.map((row, index) => (
        <View key={index} style={styles.gridRow}>
          {row.map((item, column) => (
            <View key={column} style={styles.gridCell}>
              {item}
            </View>
          ))}
          {row.length === 1 ? <View style={styles.gridCell} /> : null}
        </View>
      ))}
    </View>
  );
}

// ---------------------------------------------------------------- bars

function Track({ width, color, spoken, index }: { width: number; color: string; spoken?: string; index: number }) {
  return (
    <View
      style={styles.track}
      accessible={Boolean(spoken)}
      accessibilityRole={spoken ? 'image' : undefined}
      accessibilityLabel={spoken}
      importantForAccessibility={spoken ? 'yes' : 'no-hide-descendants'}
    >
      <GrowBar width={width} color={color} index={index} />
    </View>
  );
}

/** Horizontal bars with their count and the conversion between steps (opportunities, the network, roles). */
export function Funnel({ steps, showConversion = true, color = colors.brandDeep, aside }: { steps: readonly FunnelStepInput[]; showConversion?: boolean; color?: string; aside?: string | null }) {
  return (
    <View style={styles.bars}>
      {funnelRows(steps, showConversion).map((row, index) => (
        <View key={row.key} style={styles.barRow}>
          <View style={styles.barHead} importantForAccessibility="no-hide-descendants" accessibilityElementsHidden>
            <T variant="detalle" style={styles.grow}>
              {row.label}
            </T>
            <View style={styles.count}>
              {row.value === null ? (
                <T variant="detalle">{row.valueText}</T>
              ) : (
                <CountUp value={row.value} text={row.valueText} variant="detalle" />
              )}
              {row.conversion !== null ? <T variant="detalle">{` · ${row.conversion} %`}</T> : null}
            </View>
          </View>
          <Track width={row.width} color={color} spoken={row.spoken} index={index} />
        </View>
      ))}
      {aside ? (
        <T variant="detalle" soft>
          {aside}
        </T>
      ) : null}
    </View>
  );
}

export interface BarItem extends BarInput {
  label: string;
  /** After the label, in tinta-suave («· 2 posts»). */
  sub?: string;
}

/** A bar list relative to the largest value (the engagement by pillar); null is a dash, never 0. */
export function BarList({ items, label, color = colors.brandDeep }: { items: readonly BarItem[]; label: string; color?: string }) {
  return (
    <View style={styles.bars} accessibilityLabel={label} testID={`bars-${label}`}>
      {barRows(items).map((item, index) => (
        <View key={item.key} style={styles.barRow} accessible accessibilityLabel={`${item.label}${item.sub ? ` ${item.sub}` : ''}: ${item.text}${item.value === null ? ', sin dato' : ''}`}>
          <View style={styles.barHead}>
            <T variant="detalle" style={styles.grow}>
              {item.label}
              {item.sub ? <T variant="detalle" soft>{` ${item.sub}`}</T> : null}
            </T>
            <T variant="detalle">{item.text}</T>
          </View>
          <Track width={item.width} color={color} index={index} />
        </View>
      ))}
    </View>
  );
}

function Dot({ color, hatch }: { color: string; hatch?: boolean }) {
  return <View style={[styles.dot, hatch ? { borderWidth: 1, borderColor: color, backgroundColor: colors.surface, borderRadius: 2 } : { backgroundColor: color }]} />;
}

function Legend({ items }: { items: { key: string; text: string; color?: string; hatch?: boolean }[] }) {
  return (
    <View style={styles.legend} importantForAccessibility="no-hide-descendants" accessibilityElementsHidden>
      {items.map((item) => (
        <View key={item.key} style={styles.legendItem}>
          {item.color ? <Dot color={item.color} hatch={item.hatch} /> : null}
          <T variant="detalle" soft>
            {item.text}
          </T>
        </View>
      ))}
    </View>
  );
}

/** Stacked Startups / ProjectApp bar against the 60/40 target, marked with a line. */
export function ModalitySplit({ data }: { data: NegocioOn['modalidades'] }) {
  const view = modalitySplit(data);
  const note = view.pendingNote ? (
    <T variant="detalle" soft>
      {view.pendingNote}
    </T>
  ) : null;
  if (view.startups === null || view.projectapp === null) {
    return (
      <>
        <T variant="detalle" soft>
          {MODALITY_SPLIT_MISSING}
        </T>
        {note}
      </>
    );
  }
  return (
    <>
      <View style={styles.split} accessible accessibilityRole="image" accessibilityLabel={view.spoken}>
        <View style={styles.splitBar}>
          {view.startups > 0 ? <View style={{ width: `${view.startups}%`, backgroundColor: colors.brandDeep }} /> : null}
          {view.projectapp > 0 ? <View style={{ width: `${view.projectapp}%`, backgroundColor: colors.spriteBlue }} /> : null}
        </View>
        <View style={[styles.splitTarget, { left: `${view.target}%` }]} />
      </View>
      <Legend
        items={[
          { key: 'a', text: view.legendStartups, color: colors.brandDeep },
          { key: 'b', text: view.legendProjectapp, color: colors.spriteBlue },
          { key: 't', text: view.legendTarget },
        ]}
      />
      {note}
    </>
  );
}

// ---------------------------------------------------------------- impressions per post

const CHART_HEIGHT = 140;
const BAR_GAP = 4;

type Chart = Resultados['contenido']['chart'];

function openPiece(pieceId: string) {
  router.push({ pathname: '/calendario/pieza/[id]', params: { id: pieceId } });
}

/** Impressions per post over the period with the median of the 4 previous weeks; each bar opens the piece. */
export function ImpressionsChart({ chart, cut }: { chart: Chart; cut: '7d' | '24h' | null }) {
  const view = impressionsChart(chart, cut);
  const [width, setWidth] = useState(0);
  const count = view.bars.length;
  const slot = count ? (width - BAR_GAP * (count - 1)) / count : 0;
  const median = view.referenceHeight === null ? null : CHART_HEIGHT - (view.referenceHeight / 100) * CHART_HEIGHT;

  return (
    <ChartCard title={view.title} definition={chart.definition}>
      {count ? (
        <>
          <View style={styles.chart} onLayout={(event: LayoutChangeEvent) => setWidth(event.nativeEvent.layout.width)}>
            {width > 0 ? (
              <Svg width={width} height={CHART_HEIGHT} style={StyleSheet.absoluteFill} accessible={false} importantForAccessibility="no-hide-descendants">
                <Defs>
                  <Pattern id="hatch-above" width={6} height={6} patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                    <Rect width={6} height={6} fill={colors.surface} />
                    <Line x1={0} y1={0} x2={0} y2={6} stroke={colors.brandDeep} strokeWidth={3} />
                  </Pattern>
                  <Pattern id="hatch-below" width={6} height={6} patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                    <Rect width={6} height={6} fill={colors.surface} />
                    <Line x1={0} y1={0} x2={0} y2={6} stroke={colors.spriteBlue} strokeWidth={3} />
                  </Pattern>
                </Defs>
                {view.bars.map((bar, index) => {
                  if (bar.empty) return null;
                  const height = (bar.height / 100) * CHART_HEIGHT;
                  const x = index * (slot + BAR_GAP);
                  const color = bar.above ? colors.brandDeep : colors.spriteBlue;
                  const r = Math.min(3, slot / 2, height);
                  const top = CHART_HEIGHT - height;
                  // A bar with rounded top corners.
                  const d = `M${x} ${CHART_HEIGHT}V${top + r}Q${x} ${top} ${x + r} ${top}H${x + slot - r}Q${x + slot} ${top} ${x + slot} ${top + r}V${CHART_HEIGHT}Z`;
                  return (
                    <Path
                      key={bar.key}
                      d={d}
                      fill={bar.fallback ? `url(#hatch-${bar.above ? 'above' : 'below'})` : color}
                      stroke={bar.fallback ? color : undefined}
                      strokeWidth={bar.fallback ? 1 : 0}
                    />
                  );
                })}
                {median !== null ? <Line x1={0} x2={width} y1={median} y2={median} stroke={colors.ink} strokeWidth={2} strokeDasharray="5 4" /> : null}
              </Svg>
            ) : null}
            <View style={styles.slots}>
              {view.bars.map((bar) => (
                <Pressable
                  key={bar.key}
                  accessibilityRole="link"
                  accessibilityLabel={bar.label}
                  onPress={() => openPiece(bar.pieceId)}
                  style={({ pressed }) => [styles.slot, pressed ? styles.slotPressed : null]}
                />
              ))}
            </View>
          </View>
          <Legend
            items={[
              ...(view.reference !== null
                ? [
                    { key: 'a', text: 'Sobre la mediana', color: colors.brandDeep },
                    { key: 'b', text: 'Bajo la mediana', color: colors.spriteBlue },
                  ]
                : []),
              ...(view.anyFallback ? [{ key: 'h', text: 'A las 24 h (aún sin 7 días)', color: colors.spriteBlue, hatch: true }] : []),
            ]}
          />
          <T variant="detalle" soft>
            {view.caption}
          </T>
        </>
      ) : (
        <T variant="detalle" soft>
          Sin posts publicados en el periodo.
        </T>
      )}
    </ChartCard>
  );
}

const styles = StyleSheet.create({
  grow: { flex: 1 },
  info: { width: 48, height: 48, marginVertical: -12, marginRight: -12, alignItems: 'center', justifyContent: 'center' },
  card: { padding: space[4], gap: space[3], backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.line, borderRadius: radius.md },
  cardHead: { flexDirection: 'row', alignItems: 'center', gap: space[2] },
  kpi: { flex: 1, padding: space[3], gap: space[1], backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.line, borderRadius: radius.md },
  grid: { gap: space[3] },
  gridRow: { flexDirection: 'row', gap: space[3] },
  gridCell: { flex: 1 },
  bars: { gap: space[3] },
  barRow: { gap: 6 },
  barHead: { flexDirection: 'row', alignItems: 'flex-end', gap: space[2] },
  count: { flexDirection: 'row', alignItems: 'flex-end' },
  track: { height: 8, borderRadius: radius.pill, backgroundColor: colors.line, overflow: 'hidden' },
  dot: { width: 10, height: 10, borderRadius: radius.pill },
  legend: { flexDirection: 'row', flexWrap: 'wrap', columnGap: space[4], rowGap: space[1] },
  legendItem: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  split: { paddingVertical: space[1] },
  splitBar: { height: 24, flexDirection: 'row', gap: 2, borderRadius: radius.sm, overflow: 'hidden', backgroundColor: colors.line },
  splitTarget: { position: 'absolute', top: 0, bottom: 0, width: 2, marginLeft: -1, backgroundColor: colors.ink },
  chart: { height: CHART_HEIGHT, borderBottomWidth: 1, borderBottomColor: colors.line },
  slots: { position: 'absolute', top: 0, right: 0, bottom: 0, left: 0, flexDirection: 'row', gap: BAR_GAP },
  slot: { flex: 1, borderRadius: 3 },
  slotPressed: { backgroundColor: colors.backdrop, opacity: 0.15 },
});
