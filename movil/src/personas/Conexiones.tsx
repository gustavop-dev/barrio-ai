// Personas › Conexiones (Gustavo, 12/11/2026): his people database, only the people who accepted. The network warnings,
// the role chips with their counts, the search box by name and the connections grouped by when they accepted («Esta
// semana», «Este mes», «Antes»), most recent first, in a virtualized list with «Cargar más». The agents' queue
// (candidate … discarded) is never listed here; the person card still opens anybody by id (notifications, cards).
import { asList } from '@compartido/api/endpoints';
import { useRedSummary } from '@compartido/api/hooks';
import { useConnectionPages } from '@compartido/api/personas';
import type { Contact, RedSummary } from '@compartido/api/types';
import { displayName } from '@compartido/logic/barrio';
import { acceptedLabel, connectionSections, roleChips, roleLabel } from '@compartido/logic/conexiones';
import { router } from 'expo-router';
import { useEffect, useRef, useState, type ComponentRef, type ReactNode } from 'react';
import { Pressable, RefreshControl, ScrollView, SectionList, StyleSheet, TextInput, View, type LayoutChangeEvent } from 'react-native';
import Animated from 'react-native-reanimated';
import { Icon } from '@/components/icons';
import { useFlightSource } from '@/components/shell/flight';
import { useContentInsets } from '@/components/shell/useContentInsets';
import { Avatar, Badge, Button, EmptyState, EmptyText, ErrorRetry, FilterChip, LabelChip, Note, Skeleton, T, initials, pageContent } from '@/components/ui';
import { CHECK_ROOM } from '@/components/ui/Chip';
import { durations, useMotion } from '@/theme/motion';
import { colors, fonts, radius, space } from '@/theme/tokens';

/** The search box writes ?q= after this pause (the PWA's 300 ms). */
const SEARCH_PAUSE_MS = 300;

export interface ConexionesFilters {
  q: string;
  /** A barrio role, `sin_etiqueta` or '' for all. */
  role: string;
}

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

function ConnectionRow({ contact, now }: { contact: Contact; now: Date }) {
  const accepted = acceptedLabel(contact, now);
  // MovDetalle: the portrait and the name fly into the person card (components/shell/flight.tsx).
  const { avatar, label, hidden, begin } = useFlightSource(contact.id);
  return (
    <Pressable
      accessibilityRole="link"
      testID={`person-${contact.id}`}
      onPress={() => {
        begin(displayName(contact), initials(contact.display_name));
        router.push({ pathname: '/personas/[id]', params: { id: contact.id } });
      }}
      style={({ pressed }) => [styles.row, pressed ? styles.pressed : null]}
    >
      <View ref={avatar} collapsable={false}>
        <Animated.View style={hidden}>
          <Avatar name={contact.display_name} />
        </Animated.View>
      </View>
      <View style={styles.rowBody}>
        <View style={styles.rowTop}>
          <View ref={label} collapsable={false} style={styles.grow}>
            <Animated.View style={hidden}>
              <T numberOfLines={2}>{displayName(contact)}</T>
            </Animated.View>
          </View>
          {contact.your_turn ? <Badge tone="warn">Te toca</Badge> : null}
        </View>
        <LabelChip tone={contact.classification?.role ? 'info' : 'muted'}>{roleLabel(contact)}</LabelChip>
        {contact.headline ? (
          <T variant="detalle" soft numberOfLines={1}>
            {contact.headline}
          </T>
        ) : null}
        {contact.location ? (
          <T variant="detalle" soft numberOfLines={1}>
            {contact.location}
          </T>
        ) : null}
        {accepted ? (
          <T variant="detalle" soft>
            {accepted}
          </T>
        ) : null}
      </View>
    </Pressable>
  );
}

export function Conexiones({ header, filters, onFilters }: { header: ReactNode; filters: ConexionesFilters; onFilters: (changes: Partial<ConexionesFilters>) => void }) {
  const { q, role } = filters;
  const [text, setText] = useState(q);
  const [lastQ, setLastQ] = useState(q);
  /** The last search this box wrote to ?q= itself. */
  const [written, setWritten] = useState(q);
  const [refreshing, setRefreshing] = useState(false);
  const summary = useRedSummary();
  const list = useConnectionPages({ q, role });
  const { bottom } = useContentInsets();

  // A new link (or «Quitar filtros») brings its own search text. The box's own search coming back never does: a letter
  // typed in the instant it was written would be lost («zzzqa» became «zzz» in 09-personas on the emulator).
  if (q !== lastQ) {
    setLastQ(q);
    if (q !== written && q !== text.trim()) setText(q);
  }

  // The search box writes ?q= after a short pause.
  const latest = useRef(onFilters);
  useEffect(() => {
    latest.current = onFilters;
  });
  useEffect(() => {
    if (text.trim() === q) return;
    const timer = setTimeout(() => {
      setWritten(text.trim());
      latest.current({ q: text.trim() });
    }, SEARCH_PAUSE_MS);
    return () => clearTimeout(timer);
  }, [text, q]);

  // The chosen role chip comes fully into view (backlog #17: a chip stayed half off the right edge). It grows by its
  // check when chosen, so the strip waits for that animation and leaves room for the check. Back to «Todas», the first
  // chip, the strip goes back to its start.
  const { reduced } = useMotion();
  const strip = useRef<ComponentRef<typeof ScrollView>>(null);
  const boxes = useRef(new Map<string, { x: number; width: number }>());
  const shown = useRef({ x: 0, width: 0 });
  useEffect(() => {
    const timer = setTimeout(() => {
      const { x: left, width } = shown.current;
      if (!role) {
        if (left > 0) strip.current?.scrollTo({ x: 0, animated: !reduced });
        return;
      }
      const box = boxes.current.get(role);
      if (!box || !width) return;
      const end = box.x + box.width + CHECK_ROOM;
      if (box.x < left) strip.current?.scrollTo({ x: Math.max(0, box.x - space[4]), animated: !reduced });
      else if (end > left + width) strip.current?.scrollTo({ x: end - width + space[4], animated: !reduced });
    }, durations.fast);
    return () => clearTimeout(timer);
  }, [role, reduced]);
  const measured = (key: string) => (event: LayoutChangeEvent) => {
    const { x, width } = event.nativeEvent.layout;
    boxes.current.set(key, { x, width });
  };

  const now = new Date();
  const people = (list.data?.pages ?? []).flatMap((page) => asList(page));
  const sections = connectionSections(people, now);
  const anyFilter = Boolean(q || role);
  const chips = roleChips(summary.data);

  const clearAll = () => {
    setText('');
    onFilters({ q: '', role: '' });
  };

  const refresh = async () => {
    setRefreshing(true);
    try {
      await Promise.all([list.refetch(), summary.refetch()]);
    } finally {
      setRefreshing(false);
    }
  };

  const top = (
    <View style={styles.header}>
      {header}
      <NetworkWarnings summary={summary.data} />
      <ScrollView
        ref={strip}
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.strip}
        accessibilityLabel="Filtrar por etiqueta"
        testID="role-chips"
        onLayout={(event) => {
          shown.current.width = event.nativeEvent.layout.width;
        }}
        onScroll={(event) => {
          shown.current.x = event.nativeEvent.contentOffset.x;
        }}
        scrollEventThrottle={16}
      >
        <FilterChip pressed={!role} onPress={() => onFilters({ role: '' })}>
          {chips.all}
        </FilterChip>
        {chips.chips.map((chip) => (
          <View key={chip.value} onLayout={measured(chip.value)}>
            <FilterChip pressed={role === chip.value} onPress={() => onFilters({ role: role === chip.value ? '' : chip.value })}>
              {chip.label}
            </FilterChip>
          </View>
        ))}
      </ScrollView>
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
      {list.isError && list.data ? <ErrorRetry title="No se pudo actualizar la lista" error={list.error} onRetry={() => void list.refetch()} /> : null}
    </View>
  );

  return (
    <SectionList
      // `barrio-list` and `barrio-search` stay the testIDs the E2E flows wait for (02, 05, 12, 13, 14, 19).
      testID="barrio-list"
      style={styles.screen}
      contentContainerStyle={[pageContent, styles.rows, { paddingBottom: bottom }]}
      sections={sections}
      keyExtractor={(contact) => contact.id}
      keyboardShouldPersistTaps="handled"
      keyboardDismissMode="on-drag"
      accessibilityLabel="Lista de conexiones"
      stickySectionHeadersEnabled={false}
      ListHeaderComponent={top}
      renderSectionHeader={({ section }) => (
        <View style={styles.sectionHead} testID={`conexiones-${section.key}`}>
          <T variant="etiqueta" soft accessibilityRole="header">
            {section.title}
          </T>
        </View>
      )}
      renderItem={({ item }) => <ConnectionRow contact={item} now={now} />}
      ItemSeparatorComponent={() => <View style={styles.separator} />}
      ListEmptyComponent={
        list.isPending ? (
          <Skeleton variant="row" count={6} label="Cargando conexiones…" />
        ) : list.isError && !list.data ? (
          <ErrorRetry error={list.error} onRetry={() => void list.refetch()} />
        ) : anyFilter ? (
          <EmptyState
            title="Nadie coincide"
            action={
              <Button onPress={clearAll} block>
                Quitar filtros
              </Button>
            }
          />
        ) : (
          <EmptyState title="Todavía no hay conexiones">
            <EmptyText>Aquí aparece cada persona cuando acepta la invitación.</EmptyText>
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
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.paper },
  rows: { gap: 0 },
  header: { gap: space[4], marginBottom: space[1] },
  strip: { gap: space[2], alignItems: 'center' },
  searchBox: {
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
  sectionHead: { paddingTop: space[4], paddingBottom: space[1], backgroundColor: colors.paper },
  row: { minHeight: 48, flexDirection: 'row', alignItems: 'flex-start', gap: space[3], paddingVertical: space[3], borderRadius: radius.sm },
  pressed: { backgroundColor: colors.surface },
  rowBody: { flex: 1, gap: 4 },
  rowTop: { flexDirection: 'row', alignItems: 'flex-start', gap: space[2] },
  grow: { flex: 1 },
  separator: { height: 1, backgroundColor: colors.line },
  more: { marginTop: space[4] },
});
