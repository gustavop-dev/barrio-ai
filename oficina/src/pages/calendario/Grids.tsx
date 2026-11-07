// The calendar itself: the compact mobile week strip and month dots, and the desktop month and week grids.
import { useRef, type CSSProperties } from 'react';
import { Link } from 'react-router-dom';
import type { CalendarEvent, CalendarLayer, CalendarioDay } from '../../api/types';
import { LAYER_COLOR, LAYER_LABEL } from '../../components/ui';
import {
  WEEKDAY_INITIALS,
  dayInitial,
  dayNumber,
  longDayTitle,
  minutesOfDay,
  monthGrid,
  monthOf,
  shortDay,
  weekDays,
  weekRangeLabel,
} from './dates';
import { chronological, dayDots, eventLink, eventSentence, eventShort, eventTime, hasPendingTuyo, importantEvents, isCritical, pieceOfDay, smallActions } from './events';

export interface GridProps {
  /** The selected day (AAAA-MM-DD). */
  fecha: string;
  today: string;
  byDate: ReadonlyMap<string, CalendarioDay>;
  visible: ReadonlySet<CalendarLayer>;
  onSelect: (day: string) => void;
  /** No data yet: cells render without dots or chips. */
  loading?: boolean;
  timeZone: string;
}

function Dots({ layers }: { layers: CalendarLayer[] }) {
  return (
    <span className="cal-dots" aria-hidden="true">
      {layers.map((layer) => (
        <span key={layer} className="cal-dot" style={{ background: LAYER_COLOR[layer] }} />
      ))}
    </span>
  );
}

/** «Sábado 7 de noviembre, hoy, Publicaciones y Red». */
function dayLabel(day: string, today: string, layers: CalendarLayer[], extra: string[] = []): string {
  const parts = [longDayTitle(day)];
  if (day === today) parts.push('hoy');
  if (layers.length) parts.push(layers.map((layer) => LAYER_LABEL[layer]).join(', '));
  return [...parts, ...extra].join(', ');
}

function dayClass(base: string, day: string, { fecha, today }: Pick<GridProps, 'fecha' | 'today'>, extra: (string | false)[] = []) {
  return [base, day === today ? 'today' : '', day === fecha ? 'selected' : '', day < today ? 'past' : '', ...extra].filter(Boolean).join(' ');
}

// ---------------------------------------------------------------- mobile

/** Mobile: 7 days with their initial, number and one dot per layer. Swipe to change week. */
export function WeekStrip({ fecha, today, byDate, visible, onSelect, loading, onShiftWeek }: GridProps & { onShiftWeek: (direction: 1 | -1) => void }) {
  const start = useRef<{ x: number; y: number } | null>(null);
  return (
    <div
      role="group"
      aria-label={`Semana del ${weekRangeLabel(fecha)}`}
      aria-busy={loading || undefined}
      className={loading ? 'cal-strip loading' : 'cal-strip'}
      onTouchStart={(event) => {
        const touch = event.touches[0];
        start.current = touch ? { x: touch.clientX, y: touch.clientY } : null;
      }}
      onTouchEnd={(event) => {
        const from = start.current;
        const touch = event.changedTouches[0];
        start.current = null;
        if (!from || !touch) return;
        const dx = touch.clientX - from.x;
        const dy = touch.clientY - from.y;
        if (Math.abs(dx) > 48 && Math.abs(dx) > Math.abs(dy) * 1.5) onShiftWeek(dx < 0 ? 1 : -1);
      }}
    >
      {weekDays(fecha).map((day) => {
        const layers = dayDots(byDate.get(day), visible);
        return (
          <button
            key={day}
            type="button"
            className={dayClass('cal-strip-day', day, { fecha, today })}
            aria-pressed={day === fecha}
            aria-current={day === today ? 'date' : undefined}
            aria-label={dayLabel(day, today, layers)}
            onClick={() => onSelect(day)}
          >
            <span className="cal-ini" aria-hidden="true">
              {dayInitial(day)}
            </span>
            <span className="cal-num" aria-hidden="true">
              {dayNumber(day)}
            </span>
            <Dots layers={layers} />
          </button>
        );
      })}
    </div>
  );
}

function WeekdayHeader({ className }: { className: string }) {
  return (
    <div className={className} aria-hidden="true">
      {WEEKDAY_INITIALS.map((initial) => (
        <span key={initial}>{initial}</span>
      ))}
    </div>
  );
}

/** Mobile month: a compact grid of dots, no text. Tapping a day opens it. */
export function MonthDots({ fecha, today, byDate, visible, onSelect, loading }: GridProps) {
  const month = monthOf(fecha);
  return (
    <div className="cal-mdots-wrap">
      <WeekdayHeader className="cal-weekdays" />
      <div role="group" aria-label="Días del mes" aria-busy={loading || undefined} className={loading ? 'cal-mdots loading' : 'cal-mdots'}>
        {monthGrid(fecha).map((day) => {
          const layers = dayDots(byDate.get(day), visible);
          const outside = monthOf(day) !== month;
          return (
            <button
              key={day}
              type="button"
              className={dayClass('cal-mdots-day', day, { fecha, today }, [outside && 'outside'])}
              aria-pressed={day === fecha}
              aria-current={day === today ? 'date' : undefined}
              aria-label={dayLabel(day, today, layers)}
              onClick={() => onSelect(day)}
            >
              <span className="cal-num" aria-hidden="true">
                {dayNumber(day)}
              </span>
              <Dots layers={layers} />
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- desktop

/** Event chip: layer colour, optional hour and short text. Opens its destination directly. */
function EventChip({ event, timeZone, past }: { event: CalendarEvent; timeZone: string; past: boolean }) {
  const time = eventTime(event, timeZone);
  const to = eventLink(event);
  const sentence = eventSentence(event);
  const className = ['cal-chip', past ? 'past' : '', isCritical(event) ? 'critical' : ''].filter(Boolean).join(' ');
  const style = { '--chip-color': LAYER_COLOR[event.layer] } as CSSProperties;
  const content = (
    <>
      <span className="cal-chip-dot" aria-hidden="true" />
      {time ? <span className="cal-chip-time">{time}</span> : null}
      <span className="cal-chip-text">{eventShort(event)}</span>
    </>
  );
  const label = [time, sentence].filter(Boolean).join(' · ');
  return to ? (
    <Link to={to} className={className} style={style} title={sentence} aria-label={label}>
      {content}
    </Link>
  ) : (
    <span className={className} style={style} title={sentence}>
      {content}
      <span className="vh">{label}</span>
    </span>
  );
}

const MAX_CHIPS = 3;

/** Desktop month: up to 3 chips per day, «+N más», the «te toca» dot and «sin post» on past days without a piece. */
export function MonthGrid({ fecha, today, byDate, visible, onSelect, loading, timeZone }: GridProps) {
  const month = monthOf(fecha);
  return (
    <div className="cal-month-wrap">
      <WeekdayHeader className="cal-weekdays cal-month-head" />
      <div className={loading ? 'cal-month loading' : 'cal-month'} aria-busy={loading || undefined}>
        {monthGrid(fecha).map((day) => {
          const data = byDate.get(day);
          const events = importantEvents(data, visible);
          const shown = events.slice(0, MAX_CHIPS);
          const more = events.length - shown.length;
          const outside = monthOf(day) !== month;
          const pending = visible.has('tuyo') && hasPendingTuyo(data);
          const noPost = Boolean(data) && day < today && !outside && !pieceOfDay(data);
          const layers = dayDots(data, visible);
          const extra = [pending ? 'te toca algo' : '', noPost ? 'sin post' : ''].filter(Boolean);
          return (
            <div key={day} className={dayClass('cal-mcell', day, { fecha, today }, [outside && 'outside', noPost && 'nopost'])}>
              <button
                type="button"
                className="cal-mcell-select"
                aria-pressed={day === fecha}
                aria-current={day === today ? 'date' : undefined}
                aria-label={dayLabel(day, today, layers, extra)}
                onClick={() => onSelect(day)}
              >
                <span className="cal-mcell-num" aria-hidden="true">
                  {dayNumber(day)}
                </span>
                {pending ? <span className="cal-mcell-pending" aria-hidden="true" /> : null}
                {noPost ? (
                  <span className="cal-mcell-nopost" aria-hidden="true">
                    sin post
                  </span>
                ) : null}
              </button>
              {shown.length ? (
                <ul className="cal-mcell-chips">
                  {shown.map((event) => (
                    <li key={event.id}>
                      <EventChip event={event} timeZone={timeZone} past={day < today} />
                    </li>
                  ))}
                </ul>
              ) : null}
              {more > 0 ? (
                <button type="button" className="cal-mcell-more" onClick={() => onSelect(day)} aria-label={`${more} más el ${longDayTitle(day)}`}>
                  +{more} más
                </button>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}

const HOUR_PX = 44;
const EVENT_MINUTES = 55;

function toMinutes(value: string | undefined, fallback: number): number {
  const match = /^(\d{1,2}):(\d{2})/.exec(value ?? '');
  return match ? Number(match[1]) * 60 + Number(match[2]) : fallback;
}

interface Placed {
  event: CalendarEvent;
  minute: number;
  lane: number;
}

function placeEvents(events: CalendarEvent[], timeZone: string): { placed: Placed[]; lanes: number } {
  const timed = events
    .map((event) => ({ event, minute: event.at ? minutesOfDay(event.at, timeZone) : null }))
    .filter((entry): entry is { event: CalendarEvent; minute: number } => entry.minute !== null)
    .sort((a, b) => a.minute - b.minute);
  const ends: number[] = [];
  const placed = timed.map(({ event, minute }) => {
    let lane = ends.findIndex((end) => end <= minute);
    if (lane === -1) {
      lane = ends.length;
      ends.push(0);
    }
    ends[lane] = minute + EVENT_MINUTES;
    return { event, minute, lane };
  });
  return { placed, lanes: Math.max(1, ends.length) };
}

/**
 * Desktop week: 7 columns, an all-day strip (deadlines, grouped connections, counts) and an hour axis bounded by
 * the activity window, with a «now» line on today.
 */
export function WeekGrid({
  fecha,
  today,
  byDate,
  visible,
  onSelect,
  loading,
  timeZone,
  window: activityWindow,
  now,
}: GridProps & { window?: { start: string; end: string } | undefined; now: number }) {
  const days = weekDays(fecha);
  const perDay = days.map((day) => {
    const events = importantEvents(byDate.get(day), visible);
    return { day, allDay: chronological(events.filter((event) => !event.at)), ...placeEvents(events, timeZone) };
  });
  const minutes = perDay.flatMap((entry) => entry.placed.map((p) => p.minute));
  const start = Math.floor(Math.min(toMinutes(activityWindow?.start, 7 * 60), ...minutes) / 60) * 60;
  const end = Math.ceil(Math.max(toMinutes(activityWindow?.end, 21 * 60), ...minutes.map((m) => m + 60)) / 60) * 60;
  const hours = Array.from({ length: (end - start) / 60 }, (_, index) => start / 60 + index);
  const nowMinute = minutesOfDay(new Date(now).toISOString(), timeZone);
  const columns = { gridTemplateColumns: `56px repeat(7, minmax(0, 1fr))` };

  return (
    <div className={loading ? 'cal-week loading' : 'cal-week'} aria-busy={loading || undefined}>
      <div className="cal-week-row cal-week-head" style={columns}>
        <span />
        {days.map((day) => (
          <button
            key={day}
            type="button"
            className={dayClass('cal-week-day', day, { fecha, today })}
            aria-pressed={day === fecha}
            aria-current={day === today ? 'date' : undefined}
            aria-label={dayLabel(day, today, dayDots(byDate.get(day), visible))}
            onClick={() => onSelect(day)}
          >
            {shortDay(day)}
          </button>
        ))}
      </div>
      <div className="cal-week-row cal-week-allday" style={columns}>
        <span className="cal-week-axis-label">Todo el día</span>
        {perDay.map(({ day, allDay }) => {
          const small = smallActions(byDate.get(day));
          return (
            <ul key={day} className={day === fecha ? 'cal-week-cell selected' : 'cal-week-cell'} aria-label={`Todo el día, ${longDayTitle(day)}`}>
              {allDay.map((event) => (
                <li key={event.id}>
                  <EventChip event={event} timeZone={timeZone} past={day < today} />
                </li>
              ))}
              {small ? (
                <li className="cal-week-small" title="Comentarios, reacciones, seguimientos e invitaciones">
                  {small === 1 ? '1 acción' : `${small} acciones`}
                </li>
              ) : null}
            </ul>
          );
        })}
      </div>
      <div className="cal-week-row cal-week-body" style={columns}>
        <div className="cal-week-axis" aria-hidden="true">
          {hours.map((hour) => (
            <span key={hour} style={{ height: HOUR_PX }}>
              {String(hour).padStart(2, '0')}:00
            </span>
          ))}
        </div>
        {perDay.map(({ day, placed, lanes }) => (
          <ul
            key={day}
            className={day === fecha ? 'cal-week-col selected' : 'cal-week-col'}
            style={{ height: hours.length * HOUR_PX }}
            aria-label={`Con hora, ${longDayTitle(day)}`}
          >
            {placed.map(({ event, minute, lane }) => (
              <li
                key={event.id}
                className="cal-week-event"
                style={{ top: ((minute - start) / 60) * HOUR_PX, left: `${(lane / lanes) * 100}%`, width: `${100 / lanes}%` }}
              >
                <EventChip event={event} timeZone={timeZone} past={day < today} />
              </li>
            ))}
            {day === today && nowMinute !== null && nowMinute >= start && nowMinute <= end ? (
              <li className="cal-week-now" style={{ top: ((nowMinute - start) / 60) * HOUR_PX }}>
                <span className="vh">Ahora</span>
              </li>
            ) : null}
          </ul>
        ))}
      </div>
    </div>
  );
}
