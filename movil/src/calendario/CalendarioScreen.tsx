// Calendario (DISENO-VISTAS «3. Calendario», Calendario.dc.html): day by day, what the team did, what it
// has scheduled and what is Gustavo's. Mes, Semana and Lista, with the view and the date in the route
// params. Swipe the week or the month to turn it; tap a day to open its panel in a sheet (half and
// full, not modal: the calendar above stays usable); the selected day's panel also sits under the
// calendar. Days are Bogotá's.
import { getCalendario } from '@compartido/api/endpoints';
import { REFRESH, useActividad, useCalendario, useOverview } from '@compartido/api/hooks';
import { keys } from '@compartido/api/queryClient';
import type { CalendarioDay } from '@compartido/api/types';
import { addDays, addMonths, CALENDAR_TZ, deviceDiffers, longDayTitle, monthGrid, monthOf, monthTitle, todayIn, weekDays, weekRangeLabel } from '@compartido/logic/dates';
import { DEFAULT_VISTA, monthIsEmpty, toggledLayers, VISTAS, visibleLayers, type Vista } from '@compartido/logic/events';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { usePathname } from 'expo-router';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Pressable, RefreshControl, ScrollView, StyleSheet, View, type LayoutChangeEvent } from 'react-native';
import { Icon } from '@/components/icons';
import { useContentInsets } from '@/components/shell/useContentInsets';
import { ErrorRetry, Note, PageHeader, Segmented, SnapSheet, T, pageContent } from '@/components/ui';
import { colors, radius, shell, space } from '@/theme/tokens';
import { DayHeading, DayPanel } from './DayPanel';
import { MonthDots, WeekStrip } from './Grids';
import { LayerChips } from './LayerChips';
import { ListView } from './ListView';
import { Pager, type PageOffset, type PagerHandle } from './Pager';
import { useCalendarParams } from './params';
import { useNow } from './useNow';

/** The days a view asks for: the week, or the Monday-to-Sunday grid of the month. */
export function rangeOf(vista: Vista, fecha: string): [string, string] {
  const days = vista === 'mes' ? monthGrid(fecha) : weekDays(fecha);
  return [days[0]!, days[days.length - 1]!];
}

function shifted(vista: Vista, fecha: string, direction: number): string {
  return vista === 'mes' ? addMonths(fecha, direction) : addDays(fecha, 7 * direction);
}

function NavButton({ label, icon, text, onPress }: { label: string; icon?: 'chevronLeft' | 'chevronRight'; text?: string; onPress: () => void }) {
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={label} onPress={onPress} hitSlop={2} style={[styles.navButton, text ? styles.navText : null]}>
      {icon ? <Icon name={icon} size={20} /> : <T variant="detalle">{text}</T>}
    </Pressable>
  );
}

/** A neighbour page's data, if it is cached (the screen prefetches both neighbours). Never fetches by itself. */
function useCachedRange(vista: Vista, fecha: string) {
  const [desde, hasta] = rangeOf(vista, fecha);
  return useQuery({ queryKey: keys.calendario(desde, hasta), queryFn: () => getCalendario(desde, hasta), enabled: false });
}

export function CalendarioScreen() {
  const { vista, fecha: routeFecha, capas, tipo, noSalio, update } = useCalendarParams();
  const now = useNow();
  const client = useQueryClient();
  const { bottom } = useContentInsets();
  const overview = useOverview();
  const clientToday = todayIn(CALENDAR_TZ, now);
  const fecha = routeFecha ?? clientToday;
  const [desde, hasta] = rangeOf(vista, fecha);
  const calendar = useCalendario(desde, hasta);
  const actividad = useActividad();
  const upcoming = actividad.data?.pages[0]?.upcoming;
  const previous = useCachedRange(vista, shifted(vista, fecha, -1));
  const next = useCachedRange(vista, shifted(vista, fecha, 1));
  const pager = useRef<PagerHandle>(null);
  const [sheetDay, setSheetDay] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [screenHeight, setScreenHeight] = useState<number | undefined>(undefined);
  // The tab stays mounted under other screens: its sheet (and the Android back it listens to) waits
  // until the calendar is back, and comes back open on the same day.
  const here = usePathname() === '/calendario';
  const openSheetDay = here ? sheetDay : null;

  const data = calendar.data;
  const timeZone = data?.timezone || CALENDAR_TZ;
  const today = data?.today ?? clientToday;
  const { available, visible } = visibleLayers(data?.layers, capas);
  const byDate = useMemo(() => {
    const map = new Map<string, CalendarioDay>();
    for (const source of [previous.data, next.data, data]) for (const day of source?.days ?? []) map.set(day.date, day);
    return map;
  }, [data, previous.data, next.data]);
  const selectedDay = data?.days.find((day) => day.date === fecha);
  const gridLoading = calendar.isPending || calendar.isPlaceholderData;
  const dayLoading = !calendar.isError && (calendar.isPending || (calendar.isPlaceholderData && !selectedDay));
  const windowOpen = overview.data?.window?.open_now;
  const loaded = calendar.isSuccess && !calendar.isPlaceholderData;

  // The neighbours, so a swipe lands on a page that already has its dots.
  useEffect(() => {
    if (!loaded || vista === 'lista') return;
    for (const direction of [-1, 1]) {
      const [from, to] = rangeOf(vista, shifted(vista, fecha, direction));
      void client.prefetchQuery({ queryKey: keys.calendario(from, to), queryFn: () => getCalendario(from, to), staleTime: REFRESH.calendario });
    }
  }, [client, loaded, vista, fecha]);

  const select = useCallback((day: string) => update({ fecha: day === today ? null : day }), [update, today]);
  const openDay = (day: string) => {
    select(day);
    setSheetDay(day);
  };
  const shift = useCallback((direction: 1 | -1) => select(shifted(vista, fecha, direction)), [select, vista, fecha]);

  const refresh = async () => {
    setRefreshing(true);
    try {
      await Promise.all([calendar.refetch(), actividad.refetch(), overview.refetch()]);
    } finally {
      setRefreshing(false);
    }
  };

  const rango = vista === 'mes' ? monthTitle(fecha) : vista === 'semana' ? weekRangeLabel(fecha) : 'Línea de tiempo';
  const otherZone = deviceDiffers(timeZone, new Date(now));
  const monthEmpty = vista === 'mes' && loaded && monthIsEmpty(data?.days ?? [], monthOf(fecha));
  const previousLabel = vista === 'mes' ? 'Mes anterior' : 'Semana anterior';
  const nextLabel = vista === 'mes' ? 'Mes siguiente' : 'Semana siguiente';

  const nav =
    vista === 'lista' ? undefined : (
      <View style={styles.nav}>
        <NavButton label={previousLabel} icon="chevronLeft" onPress={() => pager.current?.go(-1)} />
        <NavButton label="Hoy" text="Hoy" onPress={() => update({ fecha: null })} />
        <NavButton label={nextLabel} icon="chevronRight" onPress={() => pager.current?.go(1)} />
      </View>
    );

  const header = (
    <View style={styles.top}>
      <PageHeader title="Calendario" subtitle={otherZone ? `${rango} · Horas de Bogotá` : rango} actions={nav} />
      <Segmented<Vista> label="Vista" options={VISTAS} value={vista} onChange={(value) => update({ vista: value === DEFAULT_VISTA ? null : value })} />
      <LayerChips layers={data?.layers} visible={visible} onToggle={(layer) => update({ capas: toggledLayers(visible, available, layer) })} />
    </View>
  );

  const dayPanelProps = {
    today,
    timeZone,
    leadHours: data?.lead_hours,
    visible,
    upcoming,
    windowOpen,
    now,
  };

  if (vista === 'lista') {
    return (
      <ListView
        header={header}
        upcoming={upcoming}
        upcomingLoading={actividad.isPending}
        upcomingError={actividad.isError ? actividad.error : null}
        onRetryUpcoming={() => void actividad.refetch()}
        tipo={tipo}
        onTipo={(value) => update({ tipo: value === 'todo' ? null : value })}
        noSalio={noSalio}
        onNoSalio={(value) => update({ no_salio: value ? '1' : null })}
        today={today}
        timeZone={timeZone}
        visible={visible}
        windowOpen={windowOpen}
        now={now}
        refreshing={refreshing}
        onRefresh={() => void refresh()}
      />
    );
  }

  const renderPage = (offset: PageOffset) => {
    const grid = {
      fecha: offset ? shifted(vista, fecha, offset) : fecha,
      today,
      byDate,
      visible,
      onSelect: openDay,
      loading: offset ? false : gridLoading,
      preview: offset !== 0,
    };
    return vista === 'mes' ? <MonthDots {...grid} /> : <WeekStrip {...grid} />;
  };

  return (
    <View style={styles.screen} onLayout={(event: LayoutChangeEvent) => setScreenHeight(event.nativeEvent.layout.height)}>
      <ScrollView
        testID="calendario"
        style={styles.screen}
        contentContainerStyle={[pageContent, styles.content, { paddingBottom: bottom }]}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => void refresh()} tintColor={colors.brandDeep} colors={[colors.brandDeep]} />}
      >
        {header}
        <View style={styles.calendar}>
          <ErrorRetry error={calendar.isError ? calendar.error : null} onRetry={() => void calendar.refetch()} title="No se pudo cargar el calendario" />
          <Pager key={vista} ref={pager} renderPage={renderPage} onShift={shift} previousLabel={previousLabel} nextLabel={nextLabel} testID={`pager-${vista}`} />
          {monthEmpty ? <Note tone="info">No hay nada registrado en este mes.</Note> : null}
        </View>
        <DayPanel key={fecha} date={fecha} day={selectedDay} loading={dayLoading} {...dayPanelProps} />
      </ScrollView>
      {openSheetDay ? (
        <SnapSheet
          label={`Detalle del día, ${longDayTitle(openSheetDay)}`}
          bottom={bottom - space[10]}
          availableHeight={screenHeight}
          onClose={() => setSheetDay(null)}
          testID="hoja-dia"
        >
          <DayHeading date={openSheetDay} today={today} />
          <DayPanel
            date={openSheetDay}
            day={byDate.get(openSheetDay)}
            loading={!calendar.isError && !byDate.get(openSheetDay) && gridLoading}
            showHeading={false}
            testID="panel-dia-hoja"
            {...dayPanelProps}
          />
        </SnapSheet>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.paper },
  content: { gap: space[4] },
  top: { gap: space[3] },
  calendar: { gap: space[3] },
  nav: { flexDirection: 'row', gap: space[1] },
  navButton: {
    minWidth: shell.touch,
    height: shell.touch,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.md,
    backgroundColor: colors.surface,
  },
  navText: { paddingHorizontal: space[3] },
});
