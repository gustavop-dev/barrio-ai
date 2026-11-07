// Personas › Barrio: the warnings, the funnel as filter chips with counts, the search box and the role,
// modality and origin filters in a sheet, and the people as a virtualized list with «Cargar más».
import { asList } from '@compartido/api/endpoints';
import { useRedSummary } from '@compartido/api/hooks';
import { useContactPages } from '@compartido/api/personas';
import type { Contact, ContactStage, RedSummary } from '@compartido/api/types';
import { displayName, moreFiltersLabel, noResultsTitle, rowMeta, stageCount, totalCount, type BarrioFilters } from '@compartido/logic/barrio';
import { CONTACT_MODALITY_LABEL, CONTACT_ROLE_LABEL, labelOf } from '@compartido/logic/format';
import { FUNNEL_ASIDE, FUNNEL_MAIN, MODALITY_SHORT, personStage, SOURCE_FILTER, type PersonStage } from '@compartido/logic/personas';
import { router } from 'expo-router';
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { FlatList, Pressable, RefreshControl, ScrollView, StyleSheet, TextInput, View } from 'react-native';
import { Icon } from '@/components/icons';
import { useContentInsets } from '@/components/shell/useContentInsets';
import { Avatar, Badge, Button, EmptyState, EmptyText, ErrorRetry, FilterChip, LabelChip, Note, Sheet, Skeleton, T, pageContent } from '@/components/ui';
import { Select } from '@/components/ui/Select';
import { colors, fonts, radius, space } from '@/theme/tokens';

/** The search box writes ?q= after this pause (the PWA's 300 ms). */
const SEARCH_PAUSE_MS = 300;

const anyOf = (table: Record<string, string>) => [{ value: '', label: 'Todos' }, ...Object.entries(table).map(([value, label]) => ({ value, label }))];
const ROLE_OPTIONS = anyOf(CONTACT_ROLE_LABEL);
const MODALITY_OPTIONS = anyOf(CONTACT_MODALITY_LABEL);
const SOURCE_OPTIONS = anyOf(SOURCE_FILTER);

/** Warnings on top: the network off and invitations paused (red/summary). */
export function NetworkWarnings({ summary }: { summary: RedSummary | undefined }) {
  if (!summary) return null;
  return (
    <>
      {summary.enabled === false ? (
        <Note tone="warn" title="La red está apagada en el servidor">
          El equipo no descubre ni propone a nadie nuevo. Lo guardado sigue aquí.
        </Note>
      ) : null}
      {summary.invites_blocked?.blocked ? (
        <Note tone="warn" title="Invitaciones en pausa: LinkedIn las limitó">
          {summary.invites_blocked.reason ? <T variant="detalle">{summary.invites_blocked.reason}</T> : null}
          <T variant="detalle">El equipo sigue observando y siguiendo.</T>
        </Note>
      ) : null}
    </>
  );
}

function PersonRow({ contact }: { contact: Contact }) {
  const stage = personStage(contact.display_stage ?? contact.stage);
  const classification = contact.classification ?? {};
  const classified = Object.keys(classification).length > 0;
  return (
    <Pressable
      accessibilityRole="link"
      testID={`person-${contact.id}`}
      onPress={() => router.push({ pathname: '/personas/[id]', params: { id: contact.id } })}
      style={({ pressed }) => [styles.row, pressed ? styles.pressed : null]}
    >
      <Avatar name={contact.display_name} />
      <View style={styles.rowBody}>
        <View style={styles.rowTop}>
          <T style={styles.grow} numberOfLines={2}>
            {displayName(contact)}
          </T>
          <Badge tone={stage.tone}>{stage.label}</Badge>
        </View>
        {contact.headline ? (
          <T variant="detalle" soft numberOfLines={1}>
            {contact.headline}
          </T>
        ) : null}
        <View style={styles.chips}>
          {classified && classification.role ? <LabelChip tone="info">{labelOf(CONTACT_ROLE_LABEL, classification.role)}</LabelChip> : null}
          {classified && classification.modality ? <LabelChip tone="muted">{MODALITY_SHORT[classification.modality] ?? classification.modality}</LabelChip> : null}
          {!classified ? (
            <T variant="detalle" soft>
              Sin clasificar todavía
            </T>
          ) : null}
        </View>
        <T variant="detalle" soft>
          {rowMeta(contact)}
        </T>
        {contact.your_turn ? (
          <View style={styles.turn}>
            <Badge tone="warn">Te toca</Badge>
          </View>
        ) : null}
      </View>
    </Pressable>
  );
}

/** «En conversación» before the inbox arrives: shown, dashed and not selectable. */
function UnavailableChip({ label }: { label: string }) {
  return (
    <View style={[styles.chip, styles.chipOff]} accessible accessibilityRole="button" accessibilityState={{ disabled: true }} accessibilityLabel={`${label} · aún no disponible`}>
      <T variant="detalle" soft>
        {label} · aún no disponible
      </T>
    </View>
  );
}

export function Barrio({ header, filters, onFilters }: { header: ReactNode; filters: BarrioFilters; onFilters: (changes: Partial<BarrioFilters>) => void }) {
  const { stage, q, role, modality, source } = filters;
  const [text, setText] = useState(q);
  const [lastQ, setLastQ] = useState(q);
  const [sheet, setSheet] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const summary = useRedSummary();
  const list = useContactPages({ stage: stage as PersonStage & ContactStage, q, role, modality, source });
  const { bottom } = useContentInsets();

  // A new link (or «Quitar filtros») brings its own search text.
  if (q !== lastQ) {
    setLastQ(q);
    if (q !== text.trim()) setText(q);
  }

  // The search box writes ?q= after a short pause.
  const latest = useRef(onFilters);
  useEffect(() => {
    latest.current = onFilters;
  });
  useEffect(() => {
    if (text.trim() === q) return;
    const timer = setTimeout(() => latest.current({ q: text.trim() }), SEARCH_PAUSE_MS);
    return () => clearTimeout(timer);
  }, [text, q]);

  const people = (list.data?.pages ?? []).flatMap((page) => asList(page));
  const extra = [role, modality, source].filter(Boolean).length;
  const anyFilter = Boolean(stage || q || extra);

  const clearAll = () => {
    setText('');
    onFilters({ stage: '', q: '', role: '', modality: '', source: '' });
  };

  const refresh = async () => {
    setRefreshing(true);
    try {
      await Promise.all([list.refetch(), summary.refetch()]);
    } finally {
      setRefreshing(false);
    }
  };

  const chip = (key: PersonStage) => {
    const count = stageCount(summary.data, key);
    const meta = personStage(key);
    if (key === 'conversation' && summary.data && count === null) return <UnavailableChip key={key} label={meta.label} />;
    return (
      <FilterChip key={key} pressed={stage === key} onPress={() => onFilters({ stage: stage === key ? '' : key })}>
        {`${meta.label}${count !== undefined && count !== null ? ` · ${count}` : ''}`}
      </FilterChip>
    );
  };
  const total = totalCount(summary.data);

  const top = (
    <View style={styles.header}>
      {header}
      <NetworkWarnings summary={summary.data} />
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.strip} accessibilityLabel="Filtrar por etapa" testID="stage-chips">
        <FilterChip pressed={!stage} onPress={() => onFilters({ stage: '' })}>
          {`Todas${total !== undefined ? ` · ${total}` : ''}`}
        </FilterChip>
        {FUNNEL_MAIN.map(chip)}
        <View style={styles.gap} />
        {FUNNEL_ASIDE.map(chip)}
      </ScrollView>
      <View style={styles.search}>
        <View style={styles.searchBox}>
          <Icon name="search" size={20} color={colors.inkSoft} />
          <TextInput
            accessibilityLabel="Buscar por nombre"
            placeholder="Buscar por nombre"
            placeholderTextColor={colors.inkSoft}
            value={text}
            onChangeText={setText}
            returnKeyType="search"
            autoCorrect={false}
            style={styles.searchInput}
            testID="barrio-search"
          />
          {text ? (
            <Pressable accessibilityRole="button" accessibilityLabel="Borrar la búsqueda" onPress={() => setText('')} style={styles.clear}>
              <Icon name="cerrar" size={18} color={colors.inkSoft} />
            </Pressable>
          ) : null}
        </View>
        <Pressable accessibilityRole="button" accessibilityLabel={moreFiltersLabel(extra)} onPress={() => setSheet(true)} style={[styles.filterButton, extra ? styles.filterOn : null]}>
          <Icon name="filtro" size={22} color={colors.ink} />
          {extra ? (
            <View style={styles.filterCount}>
              <T variant="etiqueta" color={colors.paper} style={styles.filterCountText}>
                {String(extra)}
              </T>
            </View>
          ) : null}
        </Pressable>
      </View>
      {list.isError && list.data ? <ErrorRetry title="No se pudo actualizar la lista" error={list.error} onRetry={() => void list.refetch()} /> : null}
    </View>
  );

  return (
    <>
      <FlatList
        testID="barrio-list"
        style={styles.screen}
        contentContainerStyle={[pageContent, styles.rows, { paddingBottom: bottom }]}
        data={people}
        keyExtractor={(contact) => contact.id}
        keyboardShouldPersistTaps="handled"
        keyboardDismissMode="on-drag"
        accessibilityLabel="Personas del barrio"
        ListHeaderComponent={top}
        renderItem={({ item }) => <PersonRow contact={item} />}
        ItemSeparatorComponent={() => <View style={styles.separator} />}
        ListEmptyComponent={
          list.isPending ? (
            <Skeleton variant="row" count={6} label="Cargando personas…" />
          ) : list.isError && !list.data ? (
            <ErrorRetry error={list.error} onRetry={() => void list.refetch()} />
          ) : anyFilter ? (
            <EmptyState
              title={noResultsTitle(filters)}
              action={
                <Button onPress={clearAll} block>
                  Quitar filtros
                </Button>
              }
            />
          ) : (
            <EmptyState title="Aún no hay personas">
              <EmptyText>El equipo empieza a descubrir cuando lee los comentarios de los referentes.</EmptyText>
            </EmptyState>
          )
        }
        ListFooterComponent={
          list.hasNextPage ? (
            <View style={styles.more}>
              <Button block onPress={() => void list.fetchNextPage()} loading={list.isFetchingNextPage} loadingLabel="Cargando…">
                Cargar más
              </Button>
            </View>
          ) : undefined
        }
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => void refresh()} tintColor={colors.brandDeep} colors={[colors.brandDeep]} />}
      />
      {sheet ? (
        <Sheet label="Más filtros" onClose={() => setSheet(false)} testID="barrio-filters" header={<T variant="subtitulo" accessibilityRole="header">Más filtros</T>}>
          <Select label="Rol del barrio" value={role} options={ROLE_OPTIONS} onChange={(value) => onFilters({ role: value })} testID="filter-role" />
          <Select label="Modalidad" value={modality} options={MODALITY_OPTIONS} onChange={(value) => onFilters({ modality: value })} testID="filter-modality" />
          <Select label="Origen" value={source} options={SOURCE_OPTIONS} onChange={(value) => onFilters({ source: value })} testID="filter-source" />
          <View style={styles.sheetActions}>
            <Button variant="primary" block onPress={() => setSheet(false)}>
              Ver resultados
            </Button>
            {extra ? (
              <Button block onPress={() => onFilters({ role: '', modality: '', source: '' })}>
                Quitar estos filtros
              </Button>
            ) : null}
          </View>
        </Sheet>
      ) : null}
    </>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.paper },
  rows: { gap: 0 },
  header: { gap: space[4], marginBottom: space[3] },
  strip: { gap: space[2], alignItems: 'center' },
  gap: { width: space[3] },
  chip: { minHeight: 44, paddingHorizontal: space[3], justifyContent: 'center', borderWidth: 1, borderColor: colors.line, borderRadius: radius.pill, backgroundColor: colors.surface },
  chipOff: { borderStyle: 'dashed', borderColor: colors.inkSoft, backgroundColor: 'transparent' },
  search: { flexDirection: 'row', alignItems: 'center', gap: space[2] },
  searchBox: {
    flex: 1,
    minHeight: 48,
    flexDirection: 'row',
    alignItems: 'center',
    gap: space[2],
    paddingLeft: space[3],
    borderWidth: 1,
    borderColor: colors.inkSoft,
    borderRadius: radius.sm,
    backgroundColor: colors.surface,
  },
  searchInput: { flex: 1, minHeight: 46, color: colors.ink, fontFamily: fonts.regular, fontSize: 16 },
  clear: { width: 44, height: 44, alignItems: 'center', justifyContent: 'center' },
  filterButton: { width: 48, height: 48, alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: colors.inkSoft, borderRadius: radius.sm, backgroundColor: colors.surface },
  filterOn: { borderColor: colors.ink, borderWidth: 2 },
  filterCount: { position: 'absolute', top: 4, right: 4, minWidth: 18, height: 18, paddingHorizontal: 4, borderRadius: radius.pill, backgroundColor: colors.ink, alignItems: 'center', justifyContent: 'center' },
  filterCountText: { letterSpacing: 0, lineHeight: 18 },
  row: { minHeight: 48, flexDirection: 'row', alignItems: 'flex-start', gap: space[3], paddingVertical: space[3], borderRadius: radius.sm },
  pressed: { backgroundColor: colors.surface },
  rowBody: { flex: 1, gap: 4 },
  rowTop: { flexDirection: 'row', alignItems: 'flex-start', gap: space[2] },
  grow: { flex: 1 },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: space[1], alignItems: 'center' },
  turn: { flexDirection: 'row' },
  separator: { height: 1, backgroundColor: colors.line },
  more: { marginTop: space[4] },
  sheetActions: { gap: space[2] },
});
