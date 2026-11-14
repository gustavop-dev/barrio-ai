// Resultados › Analítica de LinkedIn: LinkedIn's own analytics of the «directo» account, read from what the daily
// import stored (GET /api/v1/resultados/analitica, which never calls LinkedIn). The period lives in the route params,
// as in LinkedIn: ?periodo=7d|14d|28d|90d|365d (28 by default) or ?desde=&hasta= for «Personalizado», checked
// against the days already imported. A virtualized list: the blocks and every post are its rows. Pull to refresh.
// Without a «directo» account (production today) or before the first import it says so in one quiet card.
// The rules and texts live in compartido/src/logic/analitica.ts.
import { useAnalitica } from '@compartido/api/hooks';
import type { AnaliticaData, AnaliticaDemographicGroup, AnaliticaPost } from '@compartido/api/types';
import {
  ANALITICA_PRESETS,
  audienceLine,
  boundsLine,
  checkCustomRange,
  contentLine,
  coverageNote,
  demographicBars,
  followersView,
  freshnessLine,
  hasPayload,
  importErrorNote,
  nearestPoint,
  NOT_AVAILABLE_TEXT,
  NOT_AVAILABLE_TITLE,
  periodLine,
  pointText,
  postAsOf,
  postAudienceSplit,
  postFigures,
  postTitle,
  publicationsCount,
  rangeBounds,
  readPreset,
  readSelection,
  selectionParams,
  selectionQuery,
  SERIE_METRICS,
  serieChart,
  topBars,
  topLine,
  type AnaliticaSelection,
  type SerieChart,
  type SerieMetric,
  type SeriePoint,
} from '@compartido/logic/analitica';
import { sparklinePoints, withPeriod } from '@compartido/logic/resultados';
import { shortDate } from '@compartido/logic/personas';
import { router } from 'expo-router';
import { useCallback, useMemo, useState, type ReactNode } from 'react';
import { FlatList, Pressable, RefreshControl, StyleSheet, View, type GestureResponderEvent, type LayoutChangeEvent } from 'react-native';
import Svg, { Circle, Line, Path } from 'react-native-svg';
import { useContentInsets } from '@/components/shell/useContentInsets';
import { useParamState } from '@/components/shell/useParamState';
import { Button, ErrorRetry, Field, FilterChip, Note, Section, Segmented, Sheet, Skeleton, T, pageContent } from '@/components/ui';
import { ExternalLink } from '@/components/ui/ExternalLink';
import { colors, radius, space } from '@/theme/tokens';
import { BarList, ChartCard, KpiGrid, KpiTile, Sparkline } from './charts';

type Block = 'resumen' | 'serie' | 'seguidores' | 'posts' | 'top' | 'publico';
type Row = { key: Block; kind: 'block' } | { key: string; kind: 'post'; post: AnaliticaPost; position: number };

export const ANALITICA_PARAMS = ['periodo', 'desde', 'hasta'] as const;

/** The selected value of «Periodo» while a custom range is shown: none of the presets. */
const CUSTOM = 'personalizado';

/** The rows: the blocks, with the posts after their header. */
export function analiticaRows(posts: AnaliticaPost[]): Row[] {
  return [
    { key: 'resumen', kind: 'block' },
    { key: 'serie', kind: 'block' },
    { key: 'seguidores', kind: 'block' },
    { key: 'posts', kind: 'block' },
    ...posts.map((post, position): Row => ({ key: `post-${post.post_urn || position}`, kind: 'post', post, position })),
    { key: 'top', kind: 'block' },
    { key: 'publico', kind: 'block' },
  ];
}

export function AnaliticaLinkedin({ top }: { top: ReactNode }) {
  const [params, setParams] = useParamState(ANALITICA_PARAMS);
  const selection = readSelection(params);
  const query = useAnalitica(selectionQuery(selection));
  const data = hasPayload(query.data) ? query.data : undefined;
  const ready = data?.disponible ? data : undefined;
  const [metric, setMetric] = useState<SerieMetric>('impressions');
  const [picking, setPicking] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const { bottom } = useContentInsets();
  const retry = useCallback(() => void query.refetch(), [query]);
  const stale = query.isPlaceholderData;

  const rows = useMemo(() => (ready ? analiticaRows(ready.posts.publicados) : []), [ready]);
  const choose = (next: AnaliticaSelection) => setParams(selectionParams(next));

  const refresh = async () => {
    setRefreshing(true);
    try {
      await query.refetch();
    } finally {
      setRefreshing(false);
    }
  };

  const failed = data ? importErrorNote(data) : null;
  const errorNote = failed ? (
    <View testID="ana-error-importacion">
      <Note tone="warn" title={failed.title}>
        {failed.text}
      </Note>
    </View>
  ) : null;

  let status: ReactNode = null;
  if (query.isPending) status = <Skeleton variant="card" label="Cargando…" />;
  else if (query.data && !ready) {
    // No «directo» account, or no import yet: one quiet card, without controls nor empty figures.
    status = (
      <View style={styles.unavailable} testID="ana-no-disponible">
        <T variant="subtitulo" accessibilityRole="header">
          {NOT_AVAILABLE_TITLE}
        </T>
        {query.data.motivo ? <T soft>{withPeriod(query.data.motivo)}</T> : null}
        <T variant="detalle" soft>
          {NOT_AVAILABLE_TEXT}
        </T>
        {errorNote}
      </View>
    );
  }

  const header = (
    <View style={styles.header}>
      {top}
      {ready ? (
        <View style={styles.controls}>
          <Segmented<string>
            label="Periodo"
            showLabel
            testID="ana-periodo"
            value={selection.kind === 'preset' ? selection.periodo : CUSTOM}
            options={ANALITICA_PRESETS}
            onChange={(value) => choose({ kind: 'preset', periodo: readPreset(value) })}
          />
          <View style={styles.custom}>
            <FilterChip pressed={selection.kind === 'custom'} onPress={() => setPicking(true)} testID="ana-personalizado">
              Personalizado
            </FilterChip>
          </View>
          <T variant="detalle" soft accessibilityLiveRegion="polite" testID="ana-periodo-nota">
            {periodLine(ready)}
          </T>
          {freshnessLine(ready) ? (
            <T variant="detalle" soft testID="ana-actualizado">
              {freshnessLine(ready)}
            </T>
          ) : null}
          {errorNote}
        </View>
      ) : null}
      {status}
      {query.isError ? <ErrorRetry title={query.data ? 'No se pudo actualizar' : 'No se pudo cargar la analítica de LinkedIn'} error={query.error} onRetry={retry} /> : null}
    </View>
  );

  const block = (key: Block, d: AnaliticaData) => {
    let body: ReactNode;
    if (key === 'resumen') body = <Resumen data={d} />;
    else if (key === 'serie') body = <PorDia data={d} metric={metric} onMetric={setMetric} />;
    else if (key === 'seguidores') body = <Seguidores data={d} />;
    else if (key === 'posts') body = <PostsHeader data={d} />;
    else if (key === 'top') body = <Principales data={d} />;
    else body = <Publico data={d} />;
    return (
      <View style={[styles.block, stale ? styles.stale : null]} testID={`ana-${key}`} accessibilityState={{ busy: stale }}>
        {body}
      </View>
    );
  };

  return (
    <>
      <FlatList
        testID="analitica-list"
        style={styles.screen}
        contentContainerStyle={[pageContent, styles.rows, { paddingBottom: bottom }]}
        data={rows}
        keyExtractor={(row) => row.key}
        initialNumToRender={10}
        ListHeaderComponent={header}
        renderItem={({ item }) => (!ready ? null : item.kind === 'block' ? block(item.key, ready) : <PostRow post={item.post} position={item.position} stale={stale} />)}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => void refresh()} tintColor={colors.brandDeep} colors={[colors.brandDeep]} />}
      />
      {picking && ready ? (
        <CustomRange
          data={ready}
          initial={selection.kind === 'custom' ? selection : { desde: ready.periodo.desde, hasta: ready.periodo.hasta }}
          onClose={() => setPicking(false)}
          onApply={(desde, hasta) => {
            setPicking(false);
            choose({ kind: 'custom', desde, hasta });
          }}
        />
      ) : null}
    </>
  );
}

// ---------------------------------------------------------------- «Periodo personalizado»

function CustomRange({ data, initial, onClose, onApply }: { data: AnaliticaData; initial: { desde: string; hasta: string }; onClose: () => void; onApply: (desde: string, hasta: string) => void }) {
  const bounds = rangeBounds(data.limites);
  const [desde, setDesde] = useState(initial.desde);
  const [hasta, setHasta] = useState(initial.hasta);
  const [touched, setTouched] = useState(false);
  const check = checkCustomRange(desde, hasta, bounds);
  const apply = () => {
    setTouched(true);
    if (check.ok) onApply(desde.trim(), hasta.trim());
  };
  return (
    <Sheet
      label="Periodo personalizado"
      onClose={onClose}
      testID="ana-rango"
      header={
        <T variant="subtitulo" accessibilityRole="header">
          Periodo personalizado
        </T>
      }
    >
      <T variant="detalle" soft>
        {boundsLine(bounds)}
      </T>
      <Field
        label="Desde"
        value={desde}
        placeholder="AAAA-MM-DD"
        keyboardType="numbers-and-punctuation"
        maxLength={10}
        onChangeText={setDesde}
        error={touched ? check.desde : null}
        testID="ana-desde"
      />
      <Field
        label="Hasta"
        value={hasta}
        placeholder="AAAA-MM-DD"
        keyboardType="numbers-and-punctuation"
        maxLength={10}
        onChangeText={setHasta}
        error={touched ? check.hasta : null}
        testID="ana-hasta"
      />
      {touched && check.rango ? (
        <T variant="detalle" color={colors.alert} accessibilityRole="alert">
          {check.rango}
        </T>
      ) : null}
      <View style={styles.actions}>
        <Button variant="primary" block onPress={apply} testID="ana-rango-ver">
          Ver este periodo
        </Button>
        <Button block onPress={onClose}>
          Cancelar
        </Button>
      </View>
    </Sheet>
  );
}

// ---------------------------------------------------------------- the blocks

function Resumen({ data }: { data: AnaliticaData }) {
  const totals = data.totales;
  const note = coverageNote(data);
  return (
    <Section label="Resumen del periodo">
      <KpiGrid>
        <KpiTile label="Impresiones" kpi={totals.impressions} deltaAsPercent />
        <KpiTile label="Interacciones" kpi={totals.engagements} deltaAsPercent />
        <KpiTile label="Seguidores nuevos" kpi={totals.new_followers} />
        <KpiTile label="Tasa de interacción" kpi={totals.engagement_rate} unit="percent" />
      </KpiGrid>
      <KpiTile label="Miembros alcanzados" kpi={totals.members_reached} deltaAsPercent />
      {note ? (
        <View testID="ana-cobertura">
          <Note tone="info">{note}</Note>
        </View>
      ) : null}
    </Section>
  );
}

const CHART_HEIGHT = 140;
const INSET = 4;
const BASE = CHART_HEIGHT - INSET;

function yOf(point: SeriePoint): number {
  return INSET + ((point.y ?? 100) / 100) * (CHART_HEIGHT - INSET * 2);
}

/** The days of the period as a line (react-native-svg, already in the app); a missing day breaks it. Tap a day to read it. */
function DailyChart({ chart, metric }: { chart: SerieChart; metric: SerieMetric }) {
  const [width, setWidth] = useState(0);
  const [picked, setPicked] = useState<SeriePoint | null>(null);
  const px = useCallback((point: SeriePoint) => INSET + (point.x / 100) * Math.max(0, width - INSET * 2), [width]);
  // One line and its area per run of days with data; a lone day is a dot.
  const shapes = useMemo(
    () =>
      chart.segments.map((segment) => {
        const line = segment.map((point, i) => `${i ? 'L' : 'M'}${px(point).toFixed(1)} ${yOf(point).toFixed(1)}`).join('');
        return { line, area: `${line}L${px(segment.at(-1)!).toFixed(1)} ${BASE}L${px(segment[0]!).toFixed(1)} ${BASE}Z`, dot: segment.length === 1 ? segment[0]! : null };
      }),
    [chart, px],
  );
  const pick = (event: GestureResponderEvent) => {
    if (width > 0) setPicked(nearestPoint(chart, (event.nativeEvent.locationX - INSET) / Math.max(1, width - INSET * 2)));
  };

  return (
    <View style={styles.daily}>
      <T variant="detalle" soft importantForAccessibility="no" accessibilityElementsHidden>
        {chart.topText}
      </T>
      <Pressable
        style={styles.chart}
        onLayout={(event: LayoutChangeEvent) => setWidth(event.nativeEvent.layout.width)}
        onPress={pick}
        accessibilityRole="image"
        accessibilityLabel={chart.summary}
        testID="ana-grafico"
      >
        {width > 0 ? (
          <Svg width={width} height={CHART_HEIGHT} style={StyleSheet.absoluteFill} accessible={false} importantForAccessibility="no-hide-descendants">
            <Line x1={0} x2={width} y1={INSET} y2={INSET} stroke={colors.line} strokeWidth={1} strokeDasharray="4 4" />
            {shapes.map((shape, index) =>
              shape.dot ? <Circle key={index} cx={px(shape.dot)} cy={yOf(shape.dot)} r={3} fill={colors.brandDeep} /> : <Path key={index} d={shape.area} fill={colors.brandLight} />,
            )}
            {shapes.map((shape, index) => (shape.dot ? null : <Path key={`l${index}`} d={shape.line} fill="none" stroke={colors.brandDeep} strokeWidth={2} strokeLinejoin="round" />))}
            {picked ? <Line x1={px(picked)} x2={px(picked)} y1={INSET} y2={BASE} stroke={colors.ink} strokeWidth={1} /> : null}
            {picked && picked.y !== null ? <Circle cx={px(picked)} cy={yOf(picked)} r={4} fill={colors.brandDeep} stroke={colors.surface} strokeWidth={2} /> : null}
          </Svg>
        ) : null}
      </Pressable>
      <View style={styles.axis} importantForAccessibility="no-hide-descendants" accessibilityElementsHidden>
        <T variant="detalle" soft>
          {chart.first ? shortDate(chart.first) : ''}
        </T>
        <T variant="detalle" soft>
          {chart.last ? shortDate(chart.last) : ''}
        </T>
      </View>
      <T variant="detalle" soft={!picked} accessibilityLiveRegion="polite" testID="ana-dia">
        {picked ? pointText(picked, metric) : 'Toca el gráfico para ver un día.'}
      </T>
    </View>
  );
}

function PorDia({ data, metric, onMetric }: { data: AnaliticaData; metric: SerieMetric; onMetric: (metric: SerieMetric) => void }) {
  const chart = useMemo(() => serieChart(data.serie, metric), [data.serie, metric]);
  return (
    <ChartCard title="Por día" definition="Las cifras diarias que da LinkedIn, en días UTC. Un día sin dato corta la línea: nunca se dibuja como 0.">
      <Segmented<SerieMetric> label="Cifra del gráfico" testID="ana-metrica" value={metric} options={SERIE_METRICS} onChange={onMetric} />
      {chart.empty ? (
        <T variant="detalle" soft>
          {chart.summary}
        </T>
      ) : (
        // A new period or figure starts without a day picked.
        <DailyChart key={`${data.periodo.desde}-${data.periodo.hasta}-${metric}`} chart={chart} metric={metric} />
      )}
    </ChartCard>
  );
}

const TONE = { good: colors.brandDeep, bad: colors.alert, flat: colors.inkSoft } as const;

function Seguidores({ data }: { data: AnaliticaData }) {
  const view = followersView(data.seguidores);
  const points = sparklinePoints(view.series);
  return (
    <ChartCard title="Seguidores" definition={data.seguidores.definition}>
      {view.total !== null ? (
        <View accessible accessibilityLabel={view.spoken} style={styles.followers}>
          <T variant="titulo">{view.total}</T>
          {view.at ? (
            <T variant="detalle" soft>
              {view.at}
            </T>
          ) : null}
          {view.growth ? (
            <T variant="detalle" color={TONE[view.tone]}>
              {view.growth}
            </T>
          ) : null}
          {points ? <Sparkline points={points} /> : null}
        </View>
      ) : (
        <>
          <T variant="titulo" soft accessibilityLabel="Sin dato">
            —
          </T>
          <T variant="detalle" soft>
            {data.seguidores.unavailable_reason}
          </T>
        </>
      )}
    </ChartCard>
  );
}

function PostsHeader({ data }: { data: AnaliticaData }) {
  const count = data.posts.publicados.length;
  return (
    <Section label="Publicaciones del periodo" intro={count ? `${publicationsCount(count)}. ${data.posts.definition}` : undefined}>
      {count ? null : (
        <T variant="detalle" soft>
          Sin publicaciones en este periodo.
        </T>
      )}
    </Section>
  );
}

function openPiece(pieceId: string) {
  router.push({ pathname: '/calendario/pieza/[id]', params: { id: pieceId } });
}

function PostRow({ post, position, stale }: { post: AnaliticaPost; position: number; stale: boolean }) {
  const split = postAudienceSplit(post);
  return (
    <View style={[styles.post, stale ? styles.stale : null]} testID={`ana-post-${position}`}>
      <T>{postTitle(post)}</T>
      <T variant="detalle" soft>
        {postAsOf(post)}
      </T>
      <View style={styles.figures}>
        {postFigures(post).map((item) => (
          <View key={item.key} style={styles.figure} accessible accessibilityLabel={`${item.label}: ${item.text === '—' ? 'sin dato' : item.text}`}>
            <T variant="detalle" soft>
              {item.label}
            </T>
            <T>{item.text}</T>
          </View>
        ))}
      </View>
      {split ? (
        <T variant="detalle" soft>
          {split}
        </T>
      ) : null}
      <View style={styles.links}>
        {post.piece_id ? (
          <Button variant="ghost" size="small" onPress={() => openPiece(post.piece_id!)}>
            Abrir la pieza
          </Button>
        ) : null}
        <ExternalLink href={post.url}>Ver en LinkedIn</ExternalLink>
      </View>
    </View>
  );
}

function Principales({ data }: { data: AnaliticaData }) {
  const top = data.posts.top_linkedin;
  return (
    <Section label="Principales según LinkedIn" intro={top ? topLine(top) : undefined}>
      {top ? (
        <>
          <ChartCard title="Por impresiones">
            {top.por_impresiones.length ? <BarList label="Principales por impresiones" items={topBars(top.por_impresiones)} /> : <T variant="detalle" soft>LinkedIn no dio ninguna.</T>}
          </ChartCard>
          <ChartCard title="Por interacciones">
            {top.por_interacciones.length ? <BarList label="Principales por interacciones" items={topBars(top.por_interacciones)} /> : <T variant="detalle" soft>LinkedIn no dio ninguna.</T>}
          </ChartCard>
        </>
      ) : (
        <T variant="detalle" soft testID="ana-top-motivo">
          {data.posts.top_unavailable_reason}
        </T>
      )}
    </Section>
  );
}

function Groups({ groups }: { groups: AnaliticaDemographicGroup[] }) {
  return (
    <>
      {groups.map((group, index) => (
        <View key={`${group.group}-${index}`} style={styles.group}>
          <T variant="detalle">{group.group || 'Sin grupo'}</T>
          <BarList label={group.group || 'Sin grupo'} items={demographicBars(group)} color={colors.spriteBlue} />
        </View>
      ))}
    </>
  );
}

function Publico({ data }: { data: AnaliticaData }) {
  const { audiencia, contenido } = data.demografia;
  return (
    <Section label="Público">
      <ChartCard title="Tus seguidores">
        {audiencia && audiencia.groups.length ? (
          <>
            <T variant="detalle" soft>
              {audienceLine(audiencia)}
            </T>
            <Groups groups={audiencia.groups} />
          </>
        ) : (
          <T variant="detalle" soft>
            LinkedIn aún no dio la demografía de tus seguidores.
          </T>
        )}
      </ChartCard>
      <ChartCard title="Quienes vieron tus publicaciones">
        {contenido && contenido.groups.length ? (
          <>
            <T variant="detalle" soft>
              {contentLine(contenido)}
            </T>
            <Groups groups={contenido.groups} />
          </>
        ) : (
          <T variant="detalle" soft>
            LinkedIn aún no dio la demografía de quienes vieron tus publicaciones.
          </T>
        )}
      </ChartCard>
    </Section>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.paper },
  rows: { gap: space[3] },
  header: { gap: space[4], marginBottom: space[3] },
  controls: { gap: space[3] },
  custom: { flexDirection: 'row' },
  unavailable: { padding: space[4], gap: space[2], backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.line, borderRadius: radius.md },
  block: { marginTop: space[3] },
  stale: { opacity: 0.6 },
  actions: { gap: space[2], marginTop: space[2] },
  daily: { gap: space[1] },
  chart: { height: CHART_HEIGHT, borderBottomWidth: 1, borderBottomColor: colors.line },
  axis: { flexDirection: 'row', justifyContent: 'space-between' },
  followers: { gap: space[1] },
  post: { padding: space[4], gap: space[2], backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.line, borderRadius: radius.md },
  figures: { flexDirection: 'row', flexWrap: 'wrap', rowGap: space[2] },
  figure: { flexBasis: '33%', flexGrow: 1 },
  links: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: space[3] },
  group: { gap: space[2] },
});
