// Notificaciones (/notificaciones, FUNCIONES-NUEVAS rev 18): what is coming or happened and asks
// nothing of Gustavo, 7 days. PRÓXIMO (computed, never unread) and then one group per day, each row
// with its calendar layer's dot. Tapping a row marks it read and opens its link in the app; the bell
// dot follows through Tu turno's `notifications_unread` (useMarkNotificacionesRead keeps it in sync).
import { useMarkNotificacionesRead, useNotificaciones, type NotificationFilter, type NotificationItem } from '@compartido/api/notificaciones';
import { CALENDAR_LAYERS } from '@compartido/api/types';
import { isUnavailable } from '@compartido/logic/ajustes';
import { groupNotifications, isUnread, timeLabel, type NotificationGroup } from '@compartido/logic/notificaciones';
import { router } from 'expo-router';
import { useCallback, useMemo, useState } from 'react';
import { Pressable, RefreshControl, SectionList, StyleSheet, View } from 'react-native';
import Animated from 'react-native-reanimated';
import { useContentInsets } from '@/components/shell/useContentInsets';
import { Badge, Button, Card, ErrorRetry, FilterChip, Skeleton, T, pageContent } from '@/components/ui';
import { openLink } from '@/navigation';
import { isInAppPath } from '@/push/routes';
import { layout } from '@/theme/motion';
import { colors, layers, radius, space } from '@/theme/tokens';

const FILTERS: readonly { value: NotificationFilter; label: string }[] = [
  { value: 'todas', label: 'Todas' },
  { value: 'sin_leer', label: 'Sin leer' },
];

function dotColor(item: NotificationItem): string {
  return (CALENDAR_LAYERS as readonly string[]).includes(item.layer) ? layers[item.layer] : colors.line;
}

function Row({ item, upcoming, onOpen }: { item: NotificationItem; upcoming: boolean; onOpen: (item: NotificationItem) => void }) {
  const unread = isUnread(item);
  const time = timeLabel(item, upcoming);
  const goes = isInAppPath(item.link);
  const label = [time, item.title, item.detail, unread ? 'Nueva' : ''].filter(Boolean).join('. ');
  const content = (
    <>
      <View style={[styles.dot, { backgroundColor: dotColor(item) }]} />
      <View style={styles.text}>
        {time ? (
          <T variant="detalle" soft>
            {time}
          </T>
        ) : null}
        <T>{item.title}</T>
        {item.detail ? (
          <T variant="detalle" soft>
            {item.detail}
          </T>
        ) : null}
      </View>
      {unread ? (
        <View style={styles.badge}>
          <Badge tone="ok">Nueva</Badge>
        </View>
      ) : null}
    </>
  );
  // In-app destinations open; anything else only marks the item read and stays here. A read item without a link is plain text.
  if (!goes && !unread) {
    return (
      <View style={styles.row} accessible accessibilityLabel={label} testID={`notif-${item.id}`}>
        {content}
      </View>
    );
  }
  return (
    <Pressable
      accessibilityRole={goes ? 'link' : 'button'}
      accessibilityLabel={label}
      accessibilityHint={goes ? undefined : 'Marca la notificación como leída'}
      onPress={() => onOpen(item)}
      style={({ pressed }) => [styles.row, unread ? styles.unread : null, pressed ? styles.pressed : null]}
      testID={`notif-${item.id}`}
    >
      {content}
    </Pressable>
  );
}

/** «Tu turno» or «Calendario» inside running text: a tappable word in 0ff1ce-hondo. */
function InlineLink({ children, onPress }: { children: string; onPress: () => void }) {
  return (
    <T accessibilityRole="link" color={colors.brandDeep} onPress={onPress} suppressHighlighting={false} style={styles.inline}>
      {children}
    </T>
  );
}

export function NotificacionesScreen() {
  const [filtro, setFiltro] = useState<NotificationFilter>('todas');
  const query = useNotificaciones(filtro);
  const mark = useMarkNotificacionesRead();
  const { bottom } = useContentInsets();
  const [refreshing, setRefreshing] = useState(false);
  const groups = useMemo(() => groupNotifications(query.data, filtro), [query.data, filtro]);
  const unread = query.data?.unread ?? 0;
  const sections = useMemo(() => groups.map((group) => ({ ...group, data: group.items })), [groups]);

  const open = useCallback(
    (item: NotificationItem) => {
      if (isUnread(item)) mark.mutate({ ids: [item.id] });
      if (isInAppPath(item.link)) openLink(item.link);
    },
    [mark],
  );

  const refresh = useCallback(async () => {
    setRefreshing(true);
    try {
      await query.refetch();
    } finally {
      setRefreshing(false);
    }
  }, [query]);

  const header = (
    <View style={styles.header}>
      <View style={styles.title}>
        <T variant="titulo" accessibilityRole="header">
          Notificaciones
        </T>
        <T soft>
          Lo que viene y lo que pasó. Nada de esto necesita que hagas algo; lo que sí, está en{' '}
          <InlineLink onPress={() => router.navigate('/tu-turno')}>Tu turno</InlineLink>.
        </T>
      </View>
      <View style={styles.bar}>
        <View style={styles.filters} accessibilityRole="toolbar" accessibilityLabel="Filtrar">
          {FILTERS.map((option) => (
            <FilterChip key={option.value} pressed={filtro === option.value} onPress={() => setFiltro(option.value)} testID={`filtro-${option.value}`}>
              {option.label}
            </FilterChip>
          ))}
        </View>
        <Button variant="ghost" size="small" disabled={!query.data || unread <= 0 || mark.isPending} onPress={() => mark.mutate({ todas: true })}>
          Marcar todo como leído
        </Button>
      </View>
      <ErrorRetry error={mark.error} title="No se pudo marcar como leído" />
      {query.isPending ? <Skeleton variant="row" count={4} label="Cargando notificaciones…" /> : null}
      {query.error && !query.data && isUnavailable(query.error) ? (
        <Card tone="dashed">
          <T>Aún no disponible</T>
          <T variant="detalle" soft>
            Mientras tanto, lo que viene y lo que pasó está en el Calendario.
          </T>
        </Card>
      ) : query.error ? (
        <ErrorRetry error={query.error} onRetry={() => void query.refetch()} title={query.data ? 'No se pudo actualizar' : undefined} />
      ) : null}
    </View>
  );

  const footer = (
    <View style={styles.footer}>
      {query.data && !groups.length ? (
        <T soft center style={styles.empty}>
          No hay nada nuevo. Lo de días anteriores sigue en el Calendario.
        </T>
      ) : null}
      <T variant="detalle" soft>
        Se guardan 7 días. Lo anterior está en el <InlineLink onPress={() => router.navigate('/calendario')}>Calendario</InlineLink>.
      </T>
    </View>
  );

  return (
    <SectionList<NotificationItem, NotificationGroup & { data: NotificationItem[] }>
      testID="screen-notificaciones"
      style={styles.screen}
      contentContainerStyle={[pageContent, styles.content, { paddingBottom: bottom }]}
      sections={sections}
      keyExtractor={(item) => item.id}
      stickySectionHeadersEnabled={false}
      ListHeaderComponent={header}
      ListFooterComponent={footer}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => void refresh()} colors={[colors.brandDeep]} tintColor={colors.brandDeep} />}
      initialNumToRender={30}
      renderSectionHeader={({ section }) => (
        <T variant="etiqueta" soft accessibilityRole="header" style={styles.group}>
          {section.title}
        </T>
      )}
      renderItem={({ item, section }) => (
        <Animated.View entering={layout.listEnter()} layout={layout.listMove()}>
          <Row item={item} upcoming={section.upcoming} onOpen={open} />
        </Animated.View>
      )}
    />
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.paper },
  content: { gap: 2 },
  header: { gap: space[4], marginBottom: space[2] },
  title: { gap: space[1] },
  inline: { textDecorationLine: 'underline' },
  bar: { flexDirection: 'row', alignItems: 'center', gap: space[2] },
  filters: { flex: 1, flexDirection: 'row', flexWrap: 'wrap', gap: space[2] },
  group: { marginTop: space[4], marginBottom: space[1] },
  row: {
    marginHorizontal: -space[3],
    padding: space[3],
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: space[3],
    borderWidth: 1,
    borderColor: 'transparent',
    borderRadius: radius.md,
  },
  unread: { backgroundColor: colors.surface, borderColor: colors.line },
  pressed: { backgroundColor: colors.surface },
  dot: { width: 10, height: 10, marginTop: 7, borderRadius: radius.pill, borderWidth: 1, borderColor: colors.ink },
  text: { flex: 1, minWidth: 0, gap: 2 },
  badge: { marginTop: space[1] },
  footer: { gap: space[4], marginTop: space[4] },
  empty: { paddingVertical: space[6] },
});
