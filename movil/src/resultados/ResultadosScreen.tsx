// Resultados, in two tabs (?pestana=, as Personas). «Panorama»: the weekly summary on top, then «¿vamos bien?» in
// the order business → audience → content → team. Periodo and Modalidad live in the route params
// (?dias=&modalidad=, as in the PWA); the chips jump to each section. A virtualized list: the sections and every
// post card are its rows. Pull to refresh. «Analítica de LinkedIn» is AnaliticaLinkedin.tsx.
// Motion (MovResultados): Periodo is a segmented control whose selection slides (`seg`); the figures count
// and the bars grow (CountUp.tsx).
import { useResultados, useResumenSemanal } from '@compartido/api/hooks';
import type { Resultados, ResultadosPost } from '@compartido/api/types';
import {
  NOT_SPLIT_BY_MODALITY,
  periodNote,
  readDias,
  readModalidad,
  RESULTADOS_MODALITIES,
  RESULTADOS_PERIODS,
  RESULTADOS_SECTIONS,
  sortPosts,
  type PostSortKey,
  type ResultadosSectionId,
} from '@compartido/logic/resultados';
import { useLocalSearchParams } from 'expo-router';
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { FlatList, Pressable, RefreshControl, ScrollView, StyleSheet, View } from 'react-native';
import { useParamState } from '@/components/shell/useParamState';
import { useContentInsets } from '@/components/shell/useContentInsets';
import { ErrorRetry, PageHeader, Section, Segmented, Skeleton, T, TabBar, pageContent } from '@/components/ui';
import { Select } from '@/components/ui/Select';
import { OportunidadForm } from '@/personas/OportunidadForm';
import { useMotion } from '@/theme/motion';
import { colors, radius, space } from '@/theme/tokens';
import { AnaliticaLinkedin } from './AnaliticaLinkedin';
import { PostCard, PostsHeader } from './PostCard';
import { ResumenSemanal } from './ResumenSemanal';
import { Contenido, Equipo, Gente, Negocio, SectionBoundary } from './sections';

type Row = { key: ResultadosSectionId; kind: 'section' } | { key: string; kind: 'post'; post: ResultadosPost };

const PERIOD_OPTIONS = RESULTADOS_PERIODS.map((option) => ({ value: String(option.value), label: option.label }));

/** The rows: the four sections, with the post cards after «3 · Contenido». */
export function buildRows(posts: ResultadosPost[]): Row[] {
  return [
    { key: 'res-negocio', kind: 'section' },
    { key: 'res-gente', kind: 'section' },
    { key: 'res-contenido', kind: 'section' },
    ...posts.map((post): Row => ({ key: `post-${post.piece_id}`, kind: 'post', post })),
    { key: 'res-equipo', kind: 'section' },
  ];
}

function readPosts(data: Resultados | undefined): ResultadosPost[] {
  const posts = (data?.contenido as Resultados['contenido'] | null | undefined)?.posts;
  return Array.isArray(posts) ? posts : [];
}

type Tab = 'panorama' | 'linkedin';

const TABS: readonly { value: Tab; label: string }[] = [
  { value: 'panorama', label: 'Panorama' },
  { value: 'linkedin', label: 'Analítica de LinkedIn' },
];

export function ResultadosScreen() {
  const [params, setParams] = useParamState(['pestana'] as const);
  const tab: Tab = params.pestana === 'linkedin' ? 'linkedin' : 'panorama';
  const top = (
    <View style={styles.top}>
      <PageHeader title="Resultados" />
      <TabBar<Tab> label="Resultados" tabs={TABS} value={tab} onChange={(next) => setParams({ pestana: next === 'panorama' ? '' : next })} testIDPrefix="res-pestana" />
    </View>
  );
  return tab === 'linkedin' ? <AnaliticaLinkedin top={top} /> : <Panorama top={top} />;
}

function Panorama({ top }: { top: ReactNode }) {
  const [params, setParams] = useParamState(['dias', 'modalidad'] as const);
  const route = useLocalSearchParams<{ ancla?: string }>();
  const dias = readDias(params.dias);
  const modalidad = readModalidad(params.modalidad);
  const query = useResultados(dias, modalidad);
  const resumen = useResumenSemanal();
  const data = query.data;
  const { bottom } = useContentInsets();
  const { reduced } = useMotion();
  const list = useRef<FlatList<Row>>(null);
  const [registering, setRegistering] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [sort, setSort] = useState<PostSortKey>('date');
  const retry = useCallback(() => void query.refetch(), [query]);

  const posts = useMemo(() => sortPosts(readPosts(data), sort, 'desc'), [data, sort]);
  const rows = useMemo(() => buildRows(posts), [posts]);
  const notSplit = modalidad !== 'todo' ? NOT_SPLIT_BY_MODALITY : undefined;
  const stale = query.isPlaceholderData;

  // /resultados#resumen (the weekly_summary notification): the summary is the top of the list.
  useEffect(() => {
    if (route.ancla === 'resumen') list.current?.scrollToOffset({ offset: 0, animated: !reduced });
  }, [route.ancla, reduced]);

  const jump = (id: ResultadosSectionId) => {
    const index = rows.findIndex((row) => row.key === id);
    if (index >= 0) list.current?.scrollToIndex({ index, viewPosition: 0, animated: !reduced });
  };

  const refresh = async () => {
    setRefreshing(true);
    try {
      await Promise.all([query.refetch(), resumen.refetch()]);
    } finally {
      setRefreshing(false);
    }
  };

  const block = (render: (data: Resultados) => ReactNode) => {
    if (data) return <SectionBoundary onRetry={retry}>{render(data)}</SectionBoundary>;
    if (query.isPending) return <Skeleton variant="card" label="Cargando…" />;
    return (
      <T variant="detalle" soft>
        No se pudo cargar esta sección.
      </T>
    );
  };

  const section = (id: ResultadosSectionId) => {
    const meta = RESULTADOS_SECTIONS.find((item) => item.id === id)!;
    let body: ReactNode;
    let intro: string | undefined;
    if (id === 'res-negocio') body = block((d) => <Negocio data={d.negocio} onRegister={() => setRegistering(true)} />);
    else if (id === 'res-gente') body = block((d) => <Gente data={d.audiencia} />);
    else if (id === 'res-contenido') {
      intro = notSplit;
      body = (
        <>
          {block((d) => (
            <Contenido data={d.contenido} />
          ))}
          {data ? <PostsHeader count={posts.length} sort={sort} onSort={setSort} /> : null}
        </>
      );
    } else {
      intro = notSplit;
      body = block((d) => <Equipo data={d.equipo} />);
    }
    return (
      <View style={[styles.section, stale ? styles.stale : null]} testID={id} accessibilityState={{ busy: stale }}>
        <Section label={meta.label} intro={intro}>
          {body}
        </Section>
      </View>
    );
  };

  const header = (
    <View style={styles.header}>
      {top}
      <ResumenSemanal />
      <View style={styles.controls}>
        <Segmented label="Periodo" showLabel testID="res-periodo" value={String(dias)} options={PERIOD_OPTIONS} onChange={(value) => setParams({ dias: value === '28' ? '' : value })} />
        <View style={styles.selects}>
          <View style={styles.select}>
            <Select label="Modalidad" value={modalidad} options={RESULTADOS_MODALITIES} onChange={(value) => setParams({ modalidad: value === 'todo' ? '' : value })} testID="res-modalidad" />
          </View>
        </View>
        <T variant="detalle" soft accessibilityLiveRegion="polite">
          {periodNote(data, query.isPending, dias)}
        </T>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chips} accessibilityLabel="Secciones de Resultados">
          {RESULTADOS_SECTIONS.map((item) => (
            <Pressable key={item.id} accessibilityRole="link" accessibilityHint={`Baja a «${item.label}»`} onPress={() => jump(item.id)} style={({ pressed }) => [styles.chip, pressed ? styles.chipPressed : null]}>
              <T variant="detalle">{item.chip}</T>
            </Pressable>
          ))}
        </ScrollView>
      </View>
      {query.isError ? <ErrorRetry title={data ? 'No se pudo actualizar' : 'No se pudieron cargar los resultados'} error={query.error} onRetry={retry} /> : null}
    </View>
  );

  return (
    <>
      <FlatList
        ref={list}
        testID="resultados-list"
        style={styles.screen}
        contentContainerStyle={[pageContent, styles.rows, { paddingBottom: bottom }]}
        data={rows}
        keyExtractor={(row) => row.key}
        initialNumToRender={12}
        keyboardShouldPersistTaps="handled"
        ListHeaderComponent={header}
        renderItem={({ item }) => (item.kind === 'section' ? section(item.key) : <PostCard post={item.post} />)}
        onScrollToIndexFailed={({ index, averageItemLength }) => {
          list.current?.scrollToOffset({ offset: index * averageItemLength, animated: false });
          setTimeout(() => list.current?.scrollToIndex({ index, viewPosition: 0, animated: !reduced }), 120);
        }}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => void refresh()} tintColor={colors.brandDeep} colors={[colors.brandDeep]} />}
      />
      {registering ? <OportunidadForm onClose={() => setRegistering(false)} /> : null}
    </>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.paper },
  rows: { gap: space[3] },
  top: { gap: space[4] },
  header: { gap: space[6], marginBottom: space[3] },
  controls: { gap: space[3] },
  selects: { flexDirection: 'row', flexWrap: 'wrap', gap: space[3] },
  select: { flexGrow: 1, flexBasis: 150 },
  chips: { gap: space[2] },
  chip: { minHeight: 48, paddingHorizontal: space[3], justifyContent: 'center', borderWidth: 1, borderColor: colors.line, borderRadius: radius.pill, backgroundColor: colors.surface },
  chipPressed: { backgroundColor: colors.paper },
  section: { marginTop: space[6] },
  stale: { opacity: 0.6 },
});
