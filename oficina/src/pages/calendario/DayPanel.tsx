// «Panel del día»: what happened, what is scheduled and what is Gustavo's on the selected day.
import { useId, useRef, useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { usePiece } from '../../api/hooks';
import type { Actividad, ActividadTipo, CalendarEvent, CalendarLayer, CalendarioDay } from '../../api/types';
import { Badge, ButtonLink, Card, EmptyState, Skeleton, Timeline, TimelineItem } from '../../components/ui';
import { IconCheck, IconChevronDown } from '../../components/icons';
import { pieceStatus, vetoable } from '../../lib/editorial';
import { formatTime } from '../../lib/format';
import { ActivityList, QueuedRow } from './ActivityList';
import { dayOf, daysBetween, longDayTitle } from './dates';
import { chronological, eventBadge, eventLink, eventSentence, eventSub, eventTime, FAR_FUTURE_DAYS, importantEvents, leadText, pieceIdFromLink, pieceOfDay, summaryParts } from './events';
import { firstLines, isOnItsWay, pieceMeta, pieceWhen, publishedAt, resultLine } from './piece';
import { PlanNextButton, VetoButton } from './Veto';

export { FAR_FUTURE_DAYS };

export interface DayPanelProps {
  date: string;
  day: CalendarioDay | undefined;
  today: string;
  timeZone: string;
  leadHours: number | undefined;
  visible: ReadonlySet<CalendarLayer>;
  /** Calendar data still loading for this day. */
  loading: boolean;
  upcoming: Actividad['upcoming'] | undefined;
  windowOpen: boolean | undefined;
  now: number;
}

function Block({ label, children, className }: { label: string; children: ReactNode; className?: string }) {
  const id = useId();
  return (
    <div className={['cal-block', className ?? ''].filter(Boolean).join(' ')} role="group" aria-labelledby={id}>
      <h3 className="section-label" id={id}>
        {label}
      </h3>
      {children}
    </div>
  );
}

/** The day's piece: state, hour, thesis, three first lines, result, Vetar and «Ver cómo se escribió». */
function DayPiece({ event, today, timeZone, now }: { event: CalendarEvent; today: string; timeZone: string; now: number }) {
  const pieceId = pieceIdFromLink(event.link) ?? '';
  const query = usePiece(pieceId);
  const piece = query.data;
  const status = piece?.status ?? event.state ?? event.kind.replace(/^piece_/, '');
  const to = pieceId ? `/calendario/pieza/${encodeURIComponent(pieceId)}` : null;
  const titleId = useId();

  if (status === 'skipped') {
    const reason = event.skip_reason || piece?.brief?.skip_reason || piece?.note;
    return (
      <div className="cal-gap">
        <p>Sin publicación.{reason ? ` El director decidió no publicar: ${reason}` : ''}</p>
        {to ? (
          <Link to={to} className="cal-textlink">
            Ver cómo se decidió
          </Link>
        ) : null}
      </div>
    );
  }

  const badge = pieceStatus(status);
  const thesis = piece?.thesis ?? (event.title !== 'Publicación del día' ? event.title : null);
  const lines = firstLines(piece?.final_text);
  const meta = piece ? pieceMeta(piece) : '';
  const result = piece ? resultLine(piece, { today, timeZone }) : null;
  const when = pieceWhen(status, piece?.scheduled_for ?? event.at, { today, timeZone, now, published: piece ? publishedAt(piece) : null });
  return (
    <Card className="cal-piece" aria-labelledby={titleId}>
      <div className="cal-piece-head">
        <Badge tone={badge.tone}>{badge.label}</Badge>
        {when ? <span className="t-detalle text-suave">{when}</span> : null}
      </div>
      <p className="t-subtitulo" id={titleId} lang={thesis ? 'en' : undefined}>
        {thesis ?? 'El equipo prepara la pieza del día'}
      </p>
      {lines ? (
        <p lang="en" className="text-suave">
          {lines}
        </p>
      ) : null}
      {meta ? <p className="t-detalle text-suave">{meta}</p> : null}
      {result ? <p className="t-detalle">{result}</p> : null}
      {query.isPending && pieceId ? <Skeleton variant="line" label="Cargando la pieza…" /> : null}
      {piece?.action && vetoable(piece.action) ? (
        <VetoButton block describedBy={titleId} target={{ actionId: piece.action.id, kind: 'pieza', when: `a las ${formatTime(piece.scheduled_for, timeZone)}` }} />
      ) : null}
      {to ? (
        <Link to={to} className="cal-textlink">
          Ver cómo se escribió
        </Link>
      ) : null}
    </Card>
  );
}

/** «1 post · 6 comentarios…»: each number opens «Ver todo lo del día» filtered by its type. */
function Summary({ day, onPick }: { day: CalendarioDay | undefined; onPick: (tipo: ActividadTipo) => void }) {
  const parts = summaryParts(day);
  if (!parts.length) return <p className="text-suave">Sin actividad registrada.</p>;
  return (
    <p className="cal-summary">
      {parts.map((part, index) => (
        <span key={part.key} className="cal-summary-item">
          {index ? (
            <span className="cal-summary-sep" aria-hidden="true">
              ·
            </span>
          ) : null}
          <button type="button" className="cal-summary-part" onClick={() => onPick(part.tipo)}>
            {part.text}
          </button>
        </span>
      ))}
    </p>
  );
}

function ImportantItem({ event, timeZone }: { event: CalendarEvent; timeZone: string }) {
  return (
    <TimelineItem
      layer={event.layer}
      time={eventTime(event, timeZone)}
      title={eventSentence(event)}
      sub={eventSub(event)}
      badge={eventBadge(event)}
      agent={(event as CalendarEvent & { agent?: string }).agent ?? null}
      to={eventLink(event)}
      linkLabel={event.kind === 'action_uncertain' ? 'Resuélvela en la Bandeja' : 'Abrir'}
    />
  );
}

export function DayPanel({ date, day, today, timeZone, leadHours, visible, loading, upcoming, windowOpen, now }: DayPanelProps) {
  const [allOpen, setAllOpen] = useState(false);
  const [tipo, setTipo] = useState<ActividadTipo>('todo');
  const [noSalio, setNoSalio] = useState(false);
  const allRef = useRef<HTMLDetailsElement>(null);
  const diff = daysBetween(today, date);
  const kind = diff === 0 ? 'hoy' : diff < 0 ? 'pasado' : 'programado';
  const heading = (
    <div className="cal-panel-head">
      <h2 className="t-subtitulo">{longDayTitle(date)}</h2>
      {kind === 'hoy' ? <Badge tone="ink">Hoy</Badge> : kind === 'pasado' ? <Badge tone="muted">Pasado</Badge> : <Badge tone="info">Programado</Badge>}
    </div>
  );

  if (diff > FAR_FUTURE_DAYS) {
    return (
      <section className="cal-panel" aria-label="Detalle del día">
        {heading}
        <EmptyState title="Todavía no hay nada programado tan lejos." align="start">
          El equipo prepara cada pieza {leadText(leadHours)} antes de su hora.
        </EmptyState>
      </section>
    );
  }

  if (loading) {
    return (
      <section className="cal-panel" aria-label="Detalle del día" aria-busy="true">
        {heading}
        <Skeleton variant="card" label="Cargando el día…" />
        <Skeleton variant="row" count={2} label="Cargando los eventos…" />
      </section>
    );
  }

  const tuyo = visible.has('tuyo') ? chronological((day?.events ?? []).filter((event) => event.layer === 'tuyo')) : [];
  const piece = pieceOfDay(day);
  const queued = kind === 'pasado' ? [] : (upcoming?.queued ?? []).filter((item) => (dayOf(item.expected_at, timeZone) ?? today) === date);
  const expected = kind === 'pasado' ? [] : (day?.events ?? []).filter((event) => event.kind === 'invite_expected');
  const important = chronological(importantEvents(day, visible));
  const noUpcoming = upcoming !== undefined && !upcoming.pieces.some((p) => isOnItsWay(p.status));

  const pick = (value: ActividadTipo) => {
    setTipo(value);
    setAllOpen(true);
    window.setTimeout(() => {
      allRef.current?.scrollIntoView?.({ block: 'nearest' });
      allRef.current?.querySelector('summary')?.focus();
    }, 0);
  };

  return (
    <section className="cal-panel" aria-label="Detalle del día">
      {heading}

      {kind !== 'programado' ? <Summary day={day} onPick={pick} /> : null}

      {tuyo.length ? (
        <Block label="Tu parte">
          <ul className="cal-rows">
            {tuyo.map((event) => (
              <li key={event.id} className="cal-row">
                <span className="cal-dot big" aria-hidden="true" style={{ background: 'var(--capa-tuyo)' }} />
                <span className="cal-row-text">
                  <span>{event.kind === 'resolved' ? eventSentence(event) : event.title}</span>
                  {event.at && event.kind !== 'resolved' ? <span className="cal-row-sub">Plazo: {formatTime(event.at, timeZone)}</span> : null}
                </span>
                {event.kind === 'resolved' ? (
                  <span className="cal-done">
                    Hecho <IconCheck size={16} />
                  </span>
                ) : null}
              </li>
            ))}
          </ul>
          {tuyo.some((event) => event.kind !== 'resolved') ? (
            <ButtonLink to="/tu-turno" variant="secondary" block>
              Ir a la Bandeja
            </ButtonLink>
          ) : null}
        </Block>
      ) : null}

      <Block label="Publicación del día">
        {piece ? (
          <DayPiece key={piece.id} event={piece} today={today} timeZone={timeZone} now={now} />
        ) : (
          <div className="cal-gap">
            <p>
              {kind === 'pasado'
                ? 'Sin publicación.'
                : `Hueco libre. El equipo prepara cada pieza ${leadText(leadHours)} antes de su hora.`}
            </p>
            {kind !== 'pasado' && noUpcoming ? (
              <>
                <p className="t-detalle text-suave">No hay pieza programada para los próximos días.</p>
                <PlanNextButton block />
              </>
            ) : null}
          </div>
        )}
      </Block>

      {queued.length || expected.length ? (
        <Block label="Programado">
          <ul className="cal-rows">
            {queued.map((item) => (
              <QueuedRow key={item.id} item={item} today={today} timeZone={timeZone} windowOpen={windowOpen} />
            ))}
            {expected.map((event) => (
              <li key={event.id} className="cal-row">
                <span className="cal-row-text">
                  <span>
                    Invitaciones previstas: {event.people?.length ?? 0} {event.people?.length === 1 ? 'persona' : 'personas'}
                  </span>
                  <span className="cal-row-sub">{eventSub(event)}</span>
                </span>
              </li>
            ))}
          </ul>
        </Block>
      ) : null}

      <Block label="Lo importante del día">
        {important.length ? (
          <Timeline label="Lo importante del día">
            {important.map((event) => (
              <ImportantItem key={event.id} event={event} timeZone={timeZone} />
            ))}
          </Timeline>
        ) : (
          <p className="t-detalle text-suave">Nada importante en las capas visibles.</p>
        )}
      </Block>

      {kind !== 'programado' ? (
        <details ref={allRef} className="cal-all" open={allOpen} onToggle={(event) => setAllOpen(event.currentTarget.open)}>
          <summary>
            Ver todo lo del día
            <IconChevronDown size={20} />
          </summary>
          {allOpen ? (
            <ActivityList desde={date} hasta={date} tipo={tipo} onTipo={setTipo} noSalio={noSalio} onNoSalio={setNoSalio} today={today} timeZone={timeZone} />
          ) : null}
        </details>
      ) : null}
    </section>
  );
}
