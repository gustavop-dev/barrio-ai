// Calendario (DISENO-VISTAS «3. Calendario», Calendario.dc.html): day by day, what the team did, what it
// has scheduled and what is Gustavo's. Mes, Semana and Lista, with the view and the selected day in the route
// params. The period on screen (the week or the month) and the selected day are apart (period.ts): swiping turns
// only the period, and the selected day changes only when Gustavo taps one. A tap selects the day in place: no
// sheet and no scroll; its panel, under the calendar, changes to that day (its heading says which one, also when
// another week is on screen, where no cell is selected). There are no «‹ Hoy ›» buttons: screen readers turn the
// page with the Pager's actions. Semana ↔ Mes opens on the selected day's week or month. Days are Bogotá's.
//
// Motion (MovCalendario): the selection slides to the tapped day (Selection.tsx); the day panel enters from the
// side the date moved to (DaySwap.tsx); Semana ↔ Mes makes the week leave, the month enter row by row and the
// selection travel to its cell, while the calendar's height eases between both (ViewSwitch.tsx, Grids.tsx,
// Pager.tsx).
//
// Semana ends with «La semana» (PlanSemana.tsx): the GASP type and planned idea of each day of the week on screen.
import { getCalendario } from '@compartido/api/endpoints';
import { REFRESH, useActividad, useCalendario, useOverview } from '@compartido/api/hooks';
import { keys } from '@compartido/api/queryClient';
import type { Calendario, CalendarioDay } from '@compartido/api/types';
import { CALENDAR_TZ, deviceDiffers, monthOf, monthTitle, todayIn, weekRangeLabel } from '@compartido/logic/dates';
import { DEFAULT_VISTA, monthIsEmpty, toggledLayers, VISTAS, visibleLayers, type Vista } from '@compartido/logic/events';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { RefreshControl, ScrollView, StyleSheet, View } from 'react-native';
import { useSharedValue } from 'react-native-reanimated';
import { useContentInsets } from '@/components/shell/useContentInsets';
import { ErrorRetry, Note, PageHeader, Segmented, pageContent } from '@/components/ui';
import { useMotion } from '@/theme/motion';
import { colors, space } from '@/theme/tokens';
import { DayPanel } from './DayPanel';
import { DaySwap, useDaySwap } from './DaySwap';
import { MonthDots, WeekStrip, type GridProps } from './Grids';
import { LayerChips } from './LayerChips';
import { ListView } from './ListView';
import { Pager, type PageOffset } from './Pager';
import { useCalendarParams } from './params';
import { PlanSemana } from './PlanSemana';
import { rangeOf, shifted, useVisiblePeriod } from './period';
import { usePill } from './Selection';
import { useNow } from './useNow';
import { LeavingView, useViewSwitch, type GridVista } from './ViewSwitch';

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
  /** The selected day: the route's, or today. */
  const selected = routeFecha ?? clientToday;
  /** A day of the week or month on screen. */
  const { anchor, before, setAnchor } = useVisiblePeriod(vista, selected);
  const [desde, hasta] = rangeOf(vista, anchor);
  const calendar = useCalendario(desde, hasta);
  // The selected day's own period: the same query while it is on screen, and what keeps its panel loaded (and
  // refreshed) when Gustavo swipes away from it.
  const [selDesde, selHasta] = rangeOf(vista, selected);
  const sameRange = selDesde === desde && selHasta === hasta;
  const selectedCalendar = useCalendario(selDesde, selHasta);
  const actividad = useActividad();
  const upcoming = actividad.data?.pages[0]?.upcoming;
  const previous = useCachedRange(vista, shifted(vista, anchor, -1));
  const next = useCachedRange(vista, shifted(vista, anchor, 1));
  const [refreshing, setRefreshing] = useState(false);
  const { reduced } = useMotion();
  // The motion that outlives a view: the selection, the calendar's height (−1: not measured), the switch
  // between Semana and Mes, and the panel changing day.
  const pill = usePill(reduced);
  const calendarHeight = useSharedValue(-1);
  const viewSwitch = useViewSwitch(vista, reduced);
  const panelSwap = useDaySwap(vista === 'lista' ? null : selected, reduced);
  const { reset: resetPill } = pill;

  const data = calendar.data;
  const selectedData = selectedCalendar.data;
  const timeZone = data?.timezone || selectedData?.timezone || CALENDAR_TZ;
  const today = data?.today ?? selectedData?.today ?? clientToday;
  const { available, visible } = visibleLayers(data?.layers ?? selectedData?.layers, capas);
  const byDate = useMemo(() => {
    const map = new Map<string, CalendarioDay>();
    for (const source of [previous.data, next.data, selectedData, data]) for (const day of source?.days ?? []) map.set(day.date, day);
    return map;
  }, [data, selectedData, previous.data, next.data]);
  const selectedDay = selectedData?.days.find((day) => day.date === selected) ?? byDate.get(selected);
  const gridLoading = calendar.isPending || calendar.isPlaceholderData;
  const dayLoading = !selectedCalendar.isError && (selectedCalendar.isPending || selectedCalendar.isPlaceholderData) && !selectedDay;
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
      const [from, to] = rangeOf(vista, shifted(vista, anchor, direction));
      void client.prefetchQuery({ queryKey: keys.calendario(from, to), queryFn: () => getCalendario(from, to), staleTime: REFRESH.calendario });
    }
  }, [client, loaded, vista, anchor]);

  /** A day's data for a panel that is leaving: from the pages on screen, else from the cache. */
  const cachedDay = (day: string) =>
    byDate.get(day) ?? client.getQueryData<Calendario>(keys.calendario(...rangeOf(vista, day)))?.days.find((item) => item.date === day);

  /** A tap on a day: only the selection (and the panel under the calendar) changes. */
  const select = useCallback((day: string) => update({ fecha: day === today ? null : day }), [update, today]);
  /** A swipe (or the screen reader's action): only the period on screen turns. */
  const shift = useCallback((direction: 1 | -1) => setAnchor(shifted(vista, anchor, direction)), [setAnchor, vista, anchor]);

  const retry = () => {
    void calendar.refetch();
    if (!sameRange) void selectedCalendar.refetch();
  };

  const refresh = async () => {
    setRefreshing(true);
    try {
      await Promise.all([calendar.refetch(), sameRange ? null : selectedCalendar.refetch(), actividad.refetch(), overview.refetch()]);
    } finally {
      setRefreshing(false);
    }
  };

  const rango = vista === 'mes' ? monthTitle(anchor) : vista === 'semana' ? weekRangeLabel(anchor) : 'Línea de tiempo';
  const otherZone = deviceDiffers(timeZone, new Date(now));
  const monthEmpty = vista === 'mes' && loaded && monthIsEmpty(data?.days ?? [], monthOf(anchor));
  const previousLabel = vista === 'mes' ? 'Mes anterior' : 'Semana anterior';
  const nextLabel = vista === 'mes' ? 'Mes siguiente' : 'Semana siguiente';

  const header = (
    <View style={styles.top}>
      <PageHeader title="Calendario" subtitle={otherZone ? `${rango} · Horas de Bogotá` : rango} />
      <Segmented<Vista> label="Vista" testID="vista" options={VISTAS} value={vista} onChange={(value) => update({ vista: value === DEFAULT_VISTA ? null : value })} />
      <LayerChips layers={data?.layers ?? selectedData?.layers} visible={visible} onToggle={(layer) => update({ capas: toggledLayers(visible, available, layer) })} />
    </View>
  );

  const dayPanelProps = {
    today,
    timeZone,
    leadHours: data?.lead_hours ?? selectedData?.lead_hours,
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
      fecha={offset ? shifted(vista, anchor, offset) : anchor}
      selected={selected}
      today={today}
      byDate={byDate}
      visible={visible}
      onSelect={select}
      loading={offset ? false : gridLoading}
      preview={offset !== 0}
      pill={offset ? undefined : pill}
      enter={offset === 0 && viewSwitch.from !== null}
    />
  );

  return (
    <ScrollView
      testID="calendario"
      style={styles.screen}
      contentContainerStyle={[pageContent, styles.content, { paddingBottom: bottom }]}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => void refresh()} tintColor={colors.brandDeep} colors={[colors.brandDeep]} />}
    >
      {header}
      <View style={styles.calendar}>
        <ErrorRetry error={calendar.isError ? calendar.error : null} onRetry={retry} title="No se pudo cargar el calendario" />
        <View style={styles.viewport}>
          {viewSwitch.from ? (
            <LeavingView key={viewSwitch.from} onDone={viewSwitch.done}>
              <Grid vista={viewSwitch.from} fecha={before} selected={selected} today={today} byDate={byDate} visible={visible} onSelect={select} preview />
            </LeavingView>
          ) : null}
          <Pager key={vista} renderPage={renderPage} onShift={shift} previousLabel={previousLabel} nextLabel={nextLabel} testID={`pager-${vista}`} height={calendarHeight} />
        </View>
        {monthEmpty ? <Note tone="info">No hay nada registrado en este mes.</Note> : null}
      </View>
      <DaySwap
        date={selected}
        swap={panelSwap}
        render={(date, leaving) =>
          leaving ? (
            <DayPanel date={date} day={cachedDay(date)} loading={false} testID="panel-dia-saliente" {...dayPanelProps} />
          ) : (
            <DayPanel date={date} day={selectedDay} loading={dayLoading} failed={selectedCalendar.isError} {...dayPanelProps} />
          )
        }
      />
      {vista === 'semana' ? <PlanSemana fecha={anchor} today={today} /> : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.paper },
  content: { gap: space[4] },
  top: { gap: space[3] },
  calendar: { gap: space[3] },
  // The calendar's frame: what is still outside the eased height (the leaving month) is clipped.
  viewport: { overflow: 'hidden' },
});
