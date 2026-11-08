// Calendario (DISENO-VISTAS «3. Calendario», Calendario.dc.html): day by day, what the team did, what it
// has scheduled and what is Gustavo's. Mes, Semana and Lista, with the view and the date in the route
// params. Swipe the week or the month to turn it; tap a day to open its panel in a sheet (half and
// full, not modal: the calendar above stays usable); the selected day's panel also sits under the
// calendar. Days are Bogotá's. While the sheet is open the calendar scrolls so the week strip (or the
// month) sits at the top, and the sheet's room starts under it: at full height it never covers the days,
// so another one can still be tapped. Closing the sheet scrolls back to where Gustavo was.
//
// Motion (MovCalendario): the selection slides to the tapped day (Selection.tsx); the day panel, inline
// and in the sheet, enters from the side the date moved to (DaySwap.tsx); Semana ↔ Mes makes the week
// leave, the month enter row by row and the selection travel to its cell, while the calendar's height
// eases between both (ViewSwitch.tsx, Grids.tsx, Pager.tsx).
import { getCalendario } from '@compartido/api/endpoints';
import { REFRESH, useActividad, useCalendario, useOverview } from '@compartido/api/hooks';
import { keys } from '@compartido/api/queryClient';
import type { Calendario, CalendarioDay } from '@compartido/api/types';
import { addDays, addMonths, CALENDAR_TZ, deviceDiffers, longDayTitle, monthGrid, monthOf, monthTitle, todayIn, weekDays, weekRangeLabel } from '@compartido/logic/dates';
import { DEFAULT_VISTA, monthIsEmpty, toggledLayers, VISTAS, visibleLayers, type Vista } from '@compartido/logic/events';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { usePathname } from 'expo-router';
import { useCallback, useEffect, useMemo, useRef, useState, type ComponentRef } from 'react';
import { Pressable, RefreshControl, ScrollView, StyleSheet, View, type LayoutChangeEvent } from 'react-native';
import { useSharedValue } from 'react-native-reanimated';
import { Icon } from '@/components/icons';
import { useContentInsets } from '@/components/shell/useContentInsets';
import { ErrorRetry, Note, PageHeader, Segmented, SnapSheet, T, pageContent } from '@/components/ui';
import { useMotion } from '@/theme/motion';
import { colors, radius, shell, space } from '@/theme/tokens';
import { DayHeading, DayPanel } from './DayPanel';
import { DaySwap, useDaySwap } from './DaySwap';
import { MonthDots, WeekStrip, type GridProps } from './Grids';
import { LayerChips } from './LayerChips';
import { ListView } from './ListView';
import { Pager, type PageOffset, type PagerHandle } from './Pager';
import { useCalendarParams } from './params';
import { usePill } from './Selection';
import { useNow } from './useNow';
import { LeavingView, useViewSwitch, type GridVista } from './ViewSwitch';

/** The days a view asks for: the week, or the Monday-to-Sunday grid of the month. */
export function rangeOf(vista: Vista, fecha: string): [string, string] {
  const days = vista === 'mes' ? monthGrid(fecha) : weekDays(fecha);
  return [days[0]!, days[days.length - 1]!];
}

/** The day sheet's top at its highest: just under the grid, but always leaving it at least 55 % of the screen. */
export function sheetTop(gridBottom: number, screenHeight: number): number {
  return Math.max(0, Math.min(gridBottom + space[2], screenHeight * 0.45));
}

function shifted(vista: Vista, fecha: string, direction: number): string {
  return vista === 'mes' ? addMonths(fecha, direction) : addDays(fecha, 7 * direction);
}

function NavButton({ label, icon, text, onPress, testID }: { label: string; icon?: 'chevronLeft' | 'chevronRight'; text?: string; onPress: () => void; testID?: string }) {
  return (
    <Pressable testID={testID} accessibilityRole="button" accessibilityLabel={label} onPress={onPress} hitSlop={2} style={[styles.navButton, text ? styles.navText : null]}>
      {icon ? <Icon name={icon} size={20} /> : <T variant="detalle">{text}</T>}
    </Pressable>
  );
}

function Grid({ vista, ...props }: GridProps & { vista: GridVista }) {
  return vista === 'mes' ? <MonthDots {...props} /> : <WeekStrip {...props} />;
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
  // The day sheet's room starts under the grid: the screen, the grid's frame and the scroll that brings it to the top.
  const screenRef = useRef<ComponentRef<typeof View>>(null);
  const scrollRef = useRef<ComponentRef<typeof ScrollView>>(null);
  const gridRef = useRef<ComponentRef<typeof View>>(null);
  const scrollY = useRef(0);
  const scrollBeforeSheet = useRef<number | null>(null);
  const [gridBottom, setGridBottom] = useState(0);
  /** While the sheet is open: the scroll that puts the grid on top, and the content height that keeps it reachable. */
  const [sheetScroll, setSheetScroll] = useState<number | null>(null);
  // The tab stays mounted under other screens: its sheet (and the Android back it listens to) waits
  // until the calendar is back, and comes back open on the same day.
  const here = usePathname() === '/calendario';
  const openSheetDay = here ? sheetDay : null;
  const { reduced } = useMotion();
  // The motion that outlives a view: the selection, the calendar's height (−1: not measured), the switch
  // between Semana and Mes, and the panels changing day.
  const pill = usePill(reduced);
  const calendarHeight = useSharedValue(-1);
  const viewSwitch = useViewSwitch(vista, reduced);
  const panelSwap = useDaySwap(vista === 'lista' ? null : fecha, reduced);
  const sheetSwap = useDaySwap(openSheetDay, reduced);
  const { reset: resetPill } = pill;

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

  // Lista replaces the calendar: coming back, the selection and the height start where they land.
  useEffect(() => {
    if (vista !== 'lista') return;
    resetPill();
    calendarHeight.set(-1);
  }, [vista, resetPill, calendarHeight]);

  // The neighbours, so a swipe lands on a page that already has its dots.
  useEffect(() => {
    if (!loaded || vista === 'lista') return;
    for (const direction of [-1, 1]) {
      const [from, to] = rangeOf(vista, shifted(vista, fecha, direction));
      void client.prefetchQuery({ queryKey: keys.calendario(from, to), queryFn: () => getCalendario(from, to), staleTime: REFRESH.calendario });
    }
  }, [client, loaded, vista, fecha]);

  /** A day's data for a panel that is leaving: from the pages on screen, else from the cache. */
  const cachedDay = (day: string) =>
    byDate.get(day) ?? client.getQueryData<Calendario>(keys.calendario(...rangeOf(vista, day)))?.days.find((item) => item.date === day);

  const select = useCallback((day: string) => update({ fecha: day === today ? null : day }), [update, today]);

  /**
   * Scrolls the grid to the top, under a small gap (`scroll`), or only measures where it ends on screen. While the sheet
   * is open the content keeps at least the height that scroll needs (sheetScroll + the screen), so a short day panel,
   * or one loading after a swipe, never pulls the calendar back under the header.
   */
  const placeGrid = useCallback((scroll: boolean) => {
    const grid = gridRef.current;
    const screen = screenRef.current;
    if (!grid || !screen || typeof grid.measureLayout !== 'function') return;
    grid.measureLayout(screen, (_x, y, _width, height) => {
      if (!scroll) {
        setGridBottom(Math.max(0, y + height));
        return;
      }
      setSheetScroll(Math.max(0, scrollY.current + y - space[2]));
      setGridBottom(space[2] + height);
    });
  }, []);

  // The scroll goes once the content is tall enough for it (the floor below renders with it).
  useEffect(() => {
    if (sheetScroll !== null) scrollRef.current?.scrollTo({ y: sheetScroll, animated: !reduced });
  }, [sheetScroll, reduced]);

  // While the sheet is open, keep the grid on top when the day or the week changes.
  useEffect(() => {
    if (openSheetDay) placeGrid(true);
  }, [openSheetDay, fecha, placeGrid]);

  const openDay = (day: string) => {
    select(day);
    if (!sheetDay) scrollBeforeSheet.current = scrollY.current;
    setSheetDay(day);
    placeGrid(true);
  };

  const closeSheet = () => {
    setSheetDay(null);
    setSheetScroll(null);
    const before = scrollBeforeSheet.current;
    scrollBeforeSheet.current = null;
    if (before !== null) scrollRef.current?.scrollTo({ y: before, animated: !reduced });
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
        <NavButton label={previousLabel} icon="chevronLeft" onPress={() => pager.current?.go(-1)} testID="calendario-anterior" />
        <NavButton label="Hoy" text="Hoy" onPress={() => update({ fecha: null })} testID="calendario-hoy" />
        <NavButton label={nextLabel} icon="chevronRight" onPress={() => pager.current?.go(1)} testID="calendario-siguiente" />
      </View>
    );

  const header = (
    <View style={styles.top}>
      <PageHeader title="Calendario" subtitle={otherZone ? `${rango} · Horas de Bogotá` : rango} actions={nav} />
      <Segmented<Vista> label="Vista" testID="vista" options={VISTAS} value={vista} onChange={(value) => update({ vista: value === DEFAULT_VISTA ? null : value })} />
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

  const renderPage = (offset: PageOffset) => (
    <Grid
      vista={vista}
      fecha={offset ? shifted(vista, fecha, offset) : fecha}
      today={today}
      byDate={byDate}
      visible={visible}
      onSelect={openDay}
      loading={offset ? false : gridLoading}
      preview={offset !== 0}
      pill={offset ? undefined : pill}
      enter={offset === 0 && viewSwitch.from !== null}
    />
  );

  return (
    <View ref={screenRef} style={styles.screen} onLayout={(event: LayoutChangeEvent) => setScreenHeight(event.nativeEvent.layout.height)}>
      <ScrollView
        ref={scrollRef}
        testID="calendario"
        style={styles.screen}
        scrollEventThrottle={32}
        onScroll={(event) => {
          scrollY.current = event.nativeEvent.contentOffset.y;
        }}
        onScrollEndDrag={() => {
          if (openSheetDay) placeGrid(false);
        }}
        onMomentumScrollEnd={() => {
          if (openSheetDay) placeGrid(false);
        }}
        contentContainerStyle={[
          pageContent,
          styles.content,
          { paddingBottom: bottom },
          openSheetDay && sheetScroll !== null && screenHeight ? { minHeight: sheetScroll + screenHeight } : null,
        ]}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => void refresh()} tintColor={colors.brandDeep} colors={[colors.brandDeep]} />}
      >
        {header}
        <View style={styles.calendar}>
          <ErrorRetry error={calendar.isError ? calendar.error : null} onRetry={() => void calendar.refetch()} title="No se pudo cargar el calendario" />
          <View ref={gridRef} style={styles.viewport} collapsable={false}>
            {viewSwitch.from ? (
              <LeavingView key={viewSwitch.from} onDone={viewSwitch.done}>
                <Grid vista={viewSwitch.from} fecha={fecha} today={today} byDate={byDate} visible={visible} onSelect={openDay} preview />
              </LeavingView>
            ) : null}
            <Pager
              key={vista}
              ref={pager}
              renderPage={renderPage}
              onShift={shift}
              previousLabel={previousLabel}
              nextLabel={nextLabel}
              testID={`pager-${vista}`}
              height={calendarHeight}
            />
          </View>
          {monthEmpty ? <Note tone="info">No hay nada registrado en este mes.</Note> : null}
        </View>
        <DaySwap
          date={fecha}
          swap={panelSwap}
          render={(date, leaving) =>
            leaving ? (
              <DayPanel date={date} day={cachedDay(date)} loading={false} testID="panel-dia-saliente" {...dayPanelProps} />
            ) : (
              <DayPanel date={date} day={selectedDay} loading={dayLoading} failed={calendar.isError} {...dayPanelProps} />
            )
          }
        />
      </ScrollView>
      {openSheetDay ? (
        <SnapSheet
          label={`Detalle del día, ${longDayTitle(openSheetDay)}`}
          bottom={bottom - space[10]}
          availableHeight={screenHeight === undefined ? undefined : screenHeight - sheetTop(gridBottom, screenHeight)}
          onClose={closeSheet}
          testID="hoja-dia"
        >
          <DaySwap
            date={openSheetDay}
            swap={sheetSwap}
            render={(date, leaving) => (
              <View style={styles.sheetDay}>
                <DayHeading date={date} today={today} />
                <DayPanel
                  date={date}
                  day={leaving ? cachedDay(date) : byDate.get(date)}
                  loading={!leaving && !calendar.isError && !byDate.get(date) && gridLoading}
                  failed={!leaving && calendar.isError}
                  showHeading={false}
                  testID={leaving ? 'panel-dia-hoja-saliente' : 'panel-dia-hoja'}
                  {...dayPanelProps}
                />
              </View>
            )}
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
  // The calendar's frame: what is still outside the eased height (the leaving month) is clipped.
  viewport: { overflow: 'hidden' },
  sheetDay: { gap: space[3] },
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
