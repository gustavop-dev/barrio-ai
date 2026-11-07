// /calendario: day by day, what the team did, what it has scheduled and what is Gustavo's (DISENO-VISTAS «3. Calendario»).
import { useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useActividad, useCalendario, useOverview } from '../api/hooks';
import type { ActividadTipo, CalendarLayer, CalendarioDay } from '../api/types';
import { CALENDAR_LAYERS } from '../api/types';
import { IconChevronLeft, IconChevronRight } from '../components/icons';
import { Button, ChipStrip, ErrorRetry, FilterChip, LAYER_COLOR, LAYER_LABEL, Note, Page, Segmented } from '../components/ui';
import { CALENDAR_TZ, addDays, addMonths, deviceDiffers, isIsoDay, monthGrid, monthOf, monthTitle, todayIn, weekDays, weekRangeLabel } from './calendario/dates';
import { DayPanel } from './calendario/DayPanel';
import { DEFAULT_VISTA, isLayer, isTipo, isVista, monthIsEmpty, toggledLayers, VISTAS, visibleLayers, type Vista } from './calendario/events';
import { MonthDots, MonthGrid, WeekGrid, WeekStrip } from './calendario/Grids';
import { ListView } from './calendario/ListView';
import { useIsDesktop, useNow } from './calendario/useMedia';
import './calendario/calendario.css';

/** URL state: `?vista=mes|semana|lista&fecha=AAAA-MM-DD&capas=tuyo,publicaciones` (plus `tipo` and `no_salio` in Lista). */
function useCalendarParams() {
  const [params, setParams] = useSearchParams();
  const rawVista = params.get('vista');
  const vista: Vista = isVista(rawVista) ? rawVista : DEFAULT_VISTA;
  const rawFecha = params.get('fecha');
  const fecha = isIsoDay(rawFecha) ? rawFecha : null;
  const rawCapas = params.get('capas');
  const capas = rawCapas === null ? null : new Set(rawCapas.split(',').filter(isLayer));
  const rawTipo = params.get('tipo');
  const tipo: ActividadTipo = isTipo(rawTipo) ? rawTipo : 'todo';
  const noSalio = params.get('no_salio') === '1';
  const update = (changes: Record<string, string | null>) =>
    setParams(
      (previous) => {
        const next = new URLSearchParams(previous);
        for (const [key, value] of Object.entries(changes)) {
          if (value === null) next.delete(key);
          else next.set(key, value);
        }
        return next;
      },
      { replace: true },
    );
  return { vista, fecha, capas, tipo, noSalio, update };
}

export function Calendario() {
  const { vista, fecha: urlFecha, capas, tipo, noSalio, update } = useCalendarParams();
  const isDesktop = useIsDesktop();
  const now = useNow();
  const overview = useOverview();
  const clientToday = todayIn(CALENDAR_TZ, now);
  const fecha = urlFecha ?? clientToday;

  const range = vista === 'mes' ? monthGrid(fecha) : weekDays(fecha);
  const calendar = useCalendario(range[0]!, range[range.length - 1]!);
  const actividad = useActividad();
  const upcoming = actividad.data?.pages[0]?.upcoming;

  const data = calendar.data;
  const timeZone = data?.timezone || CALENDAR_TZ;
  const today = data?.today ?? clientToday;
  const layers = data?.layers;
  const { available, visible } = visibleLayers(layers, capas);
  const byDate = useMemo(() => new Map<string, CalendarioDay>((data?.days ?? []).map((day) => [day.date, day])), [data]);
  const selectedDay = byDate.get(fecha);
  const gridLoading = calendar.isPending || calendar.isPlaceholderData;
  const dayLoading = !calendar.isError && (calendar.isPending || (calendar.isPlaceholderData && !selectedDay));
  const windowOpen = overview.data?.window?.open_now;

  const select = (day: string) => update({ fecha: day === today ? null : day });
  const move = (direction: 1 | -1) => select(vista === 'mes' ? addMonths(fecha, direction) : addDays(fecha, 7 * direction));
  const toggleLayer = (layer: CalendarLayer) => update({ capas: toggledLayers(visible, available, layer) });

  const rango = vista === 'mes' ? monthTitle(fecha) : vista === 'semana' ? weekRangeLabel(fecha) : 'Línea de tiempo';
  const otherZone = deviceDiffers(timeZone, new Date(now));
  const monthEmpty = vista === 'mes' && calendar.isSuccess && !calendar.isPlaceholderData && monthIsEmpty(data?.days ?? [], monthOf(fecha));

  const nav =
    vista === 'lista' ? undefined : (
      <div className="cal-nav">
        <Button
          size="small"
          className="cal-navbtn"
          aria-label={vista === 'mes' ? 'Mes anterior' : 'Semana anterior'}
          onClick={() => move(-1)}
          icon={<IconChevronLeft size={20} />}
        />
        <Button size="small" onClick={() => update({ fecha: null })}>
          Hoy
        </Button>
        <Button
          size="small"
          className="cal-navbtn"
          aria-label={vista === 'mes' ? 'Mes siguiente' : 'Semana siguiente'}
          onClick={() => move(1)}
          icon={<IconChevronRight size={20} />}
        />
      </div>
    );

  const grid = { fecha, today, byDate, visible, onSelect: select, loading: gridLoading, timeZone };

  return (
    <Page
      title="Calendario"
      subtitle={
        <>
          <span aria-live="polite">{rango}</span>
          {otherZone ? <span className="cal-zone"> · Horas de Bogotá</span> : null}
        </>
      }
      actions={nav}
    >
      <div className="cal-controls">
        <Segmented label="Vista" options={VISTAS} value={vista} onChange={(value) => update({ vista: value === DEFAULT_VISTA ? null : value })} />
        <ChipStrip label="Capas">
          {CALENDAR_LAYERS.map((layer) => {
            const state = layers?.[layer];
            return (
              <FilterChip
                key={layer}
                variant="layer"
                color={LAYER_COLOR[layer]}
                pressed={visible.has(layer)}
                unavailableLabel={state === false ? 'aún no disponible' : undefined}
                title={state === 'parcial' ? 'Por ahora solo las oportunidades: las conversaciones llegan con el inbox' : undefined}
                onClick={() => toggleLayer(layer)}
              >
                {state === 'parcial' ? `${LAYER_LABEL[layer]} · parcial` : LAYER_LABEL[layer]}
              </FilterChip>
            );
          })}
        </ChipStrip>
      </div>

      {vista === 'lista' ? (
        <ListView
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
        />
      ) : (
        <div className="split cal-split">
          <div className="cal-main">
            <ErrorRetry error={calendar.isError ? calendar.error : null} onRetry={() => void calendar.refetch()} title="No se pudo cargar el calendario" />
            {vista === 'semana' ? (
              isDesktop ? (
                <WeekGrid {...grid} window={overview.data?.window} now={now} />
              ) : (
                <WeekStrip {...grid} onShiftWeek={(direction) => select(addDays(fecha, 7 * direction))} />
              )
            ) : isDesktop ? (
              <MonthGrid {...grid} />
            ) : (
              <MonthDots {...grid} />
            )}
            {monthEmpty ? <Note tone="info">No hay nada registrado en este mes.</Note> : null}
          </div>
          <DayPanel
            key={fecha}
            date={fecha}
            day={selectedDay}
            today={today}
            timeZone={timeZone}
            leadHours={data?.lead_hours}
            visible={visible}
            loading={dayLoading}
            upcoming={upcoming}
            windowOpen={windowOpen}
            now={now}
          />
        </div>
      )}
    </Page>
  );
}
