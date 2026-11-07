// The full timeline of what the team did (GET /api/v1/actividad): vista Lista and «Ver todo lo del día».
import { useId } from 'react';
import { useActividad } from '../../api/hooks';
import type { ActividadTipo, ActivityItem, CalendarLayer } from '../../api/types';
import { Button, ChipStrip, EmptyState, ErrorRetry, FilterChip, Skeleton, Timeline, TimelineItem } from '../../components/ui';
import { formatTime } from '../../lib/format';
import { dayOf, longDayTitle, relativeDay, relativeDayInSentence } from './dates';
import { itemLayer, itemLink, itemSentence, itemSub, reactionLabel, stateBadge, TIPOS } from './events';
import { VetoButton } from './Veto';

/** One activity item as a timeline row, with the post excerpt, the full comment and «Por qué» folded. */
export function ActivityRow({ item, timeZone }: { item: ActivityItem; timeZone: string }) {
  const layer = itemLayer(item);
  const link = itemLink(item);
  const excerptText = item.target?.post_excerpt;
  const expandable = (item.capability === 'INT-03' || item.capability === 'INT-02') && Boolean(excerptText || item.text || item.rationale);
  return (
    <TimelineItem
      layer={layer ?? undefined}
      color={layer ? undefined : 'var(--color-tinta-suave)'}
      time={formatTime(item.at, timeZone)}
      title={itemSentence(item)}
      sub={itemSub(item)}
      badge={stateBadge(item)}
      agent={item.agent}
      to={link?.to}
      linkLabel={link?.label}
      externalUrl={item.url}
      expandLabel={item.capability === 'INT-03' ? 'Ver el comentario' : 'Ver el post'}
    >
      {expandable ? (
        <>
          {excerptText ? <p className="cal-excerpt">{excerptText}</p> : null}
          {item.capability === 'INT-03' && item.text ? <p className="cal-comment">{item.text}</p> : null}
          {item.rationale ? (
            <details className="cal-why">
              <summary>Por qué</summary>
              <p>{item.rationale}</p>
            </details>
          ) : null}
        </>
      ) : null}
    </TimelineItem>
  );
}

/** «Comentario en el post de Elena Prueba»: an approved action waiting for the window or the spacing. */
export function queuedSentence(item: ActivityItem): string {
  const name = item.target?.name || '';
  switch (item.capability) {
    case 'INT-03':
      return name ? `Comentario en el post de ${name}` : 'Comentario en un post';
    case 'INT-02': {
      const reaction = reactionLabel(item.reaction);
      return `Reacción${reaction ? ` ${reaction}` : ''} al post${name ? ` de ${name}` : ''}`;
    }
    case 'RED-01':
      return `Seguir a ${name || 'una persona'}`;
    case 'RED-02':
      return `Invitar a ${name || 'una persona'} (sin nota)`;
    case 'RED-04':
      return `Aceptar la invitación de ${name || 'una persona'}`;
    default:
      return name ? `${item.label}: ${name}` : item.label;
  }
}

/** «Saldrá cuando abra la ventana, mañana a las 08:00». */
export function queuedWhen(expectedAt: string | null, { today, timeZone, windowOpen }: { today: string; timeZone: string; windowOpen: boolean | undefined }): string {
  if (!expectedAt) return 'Saldrá en cuanto lo permitan la ventana y el espaciado';
  const day = dayOf(expectedAt, timeZone) ?? today;
  const when = `${relativeDayInSentence(day, today)} a las ${formatTime(expectedAt, timeZone)}`;
  return windowOpen === false ? `Saldrá cuando abra la ventana, ${when}` : `Saldrá ${when}, según el espaciado`;
}

/** A queued action with its Vetar (a network action discards the person). */
export function QueuedRow({
  item,
  today,
  timeZone,
  windowOpen,
}: {
  item: ActivityItem & { expected_at: string | null };
  today: string;
  timeZone: string;
  windowOpen: boolean | undefined;
}) {
  const titleId = useId();
  return (
    <li className="cal-row">
      <span className="cal-row-text">
        <span id={titleId}>{queuedSentence(item)}</span>
        <span className="cal-row-sub">{queuedWhen(item.expected_at, { today, timeZone, windowOpen })}</span>
      </span>
      <VetoButton
        size="small"
        describedBy={titleId}
        target={{ actionId: item.id, kind: 'accion', network: String(item.capability).startsWith('RED-'), person: item.target?.name }}
      />
    </li>
  );
}

export interface ActivityListProps {
  desde?: string;
  hasta?: string;
  tipo: ActividadTipo;
  onTipo: (tipo: ActividadTipo) => void;
  noSalio: boolean;
  onNoSalio: (value: boolean) => void;
  /** Groups by day (Hoy, Ayer, «Jueves 5 de noviembre») for the Lista view. */
  grouped?: boolean;
  today: string;
  timeZone: string;
  /** Hides the important items of layers turned off. */
  visible?: ReadonlySet<CalendarLayer>;
}

/** Type chips, «Mostrar lo que no salió», the items and «Cargar más». */
export function ActivityList({ desde = '', hasta = '', tipo, onTipo, noSalio, onNoSalio, grouped = false, today, timeZone, visible }: ActivityListProps) {
  const query = useActividad({ tipo, desde, hasta, noSalio });
  const switchId = useId();
  const items = (query.data?.pages.flatMap((page) => page.items) ?? []).filter((item) => {
    const layer = itemLayer(item);
    return !layer || !visible || visible.has(layer);
  });

  const groups: { date: string; items: ActivityItem[] }[] = [];
  for (const item of items) {
    const date = item.date || dayOf(item.at, timeZone) || '';
    const last = groups[groups.length - 1];
    if (last && last.date === date) last.items.push(item);
    else groups.push({ date, items: [item] });
  }

  return (
    <div className="cal-activity">
      <ChipStrip label="Filtrar por tipo">
        {TIPOS.map((option) => (
          <FilterChip key={option.value} pressed={tipo === option.value} onClick={() => onTipo(option.value)}>
            {option.label}
          </FilterChip>
        ))}
      </ChipStrip>
      <label className="cal-switch" htmlFor={switchId}>
        <span>
          Mostrar lo que no salió
          <span className="cal-switch-hint">Vetadas, descartadas, caducadas y sustituidas. Las fallidas y las inciertas se ven siempre.</span>
        </span>
        <input id={switchId} type="checkbox" role="switch" checked={noSalio} onChange={(event) => onNoSalio(event.target.checked)} />
      </label>

      {query.isPending ? <Skeleton variant="row" count={3} label="Cargando la actividad…" /> : null}
      <ErrorRetry error={query.isError ? query.error : null} onRetry={() => void query.refetch()} />
      {query.isSuccess && !items.length ? (
        <EmptyState title={desde ? 'Nada registrado ese día con este filtro.' : 'No hay nada registrado con este filtro.'} align="start" />
      ) : null}

      {grouped
        ? groups.map((group) => (
            <section key={group.date} className="cal-group" aria-labelledby={`dia-${group.date}`}>
              <h3 className="section-label" id={`dia-${group.date}`}>
                {group.date ? relativeDay(group.date, today) : 'Sin fecha'}
                {group.date && relativeDay(group.date, today) !== longDayTitle(group.date) ? <span className="vh">, {longDayTitle(group.date)}</span> : null}
              </h3>
              <Timeline>
                {group.items.map((item) => (
                  <ActivityRow key={item.id} item={item} timeZone={timeZone} />
                ))}
              </Timeline>
            </section>
          ))
        : items.length ? (
            <Timeline label="Todo lo del día">
              {items.map((item) => (
                <ActivityRow key={item.id} item={item} timeZone={timeZone} />
              ))}
            </Timeline>
          ) : null}

      {query.hasNextPage ? (
        <Button variant="secondary" block loading={query.isFetchingNextPage} loadingLabel="Cargando…" onClick={() => void query.fetchNextPage()}>
          Cargar más
        </Button>
      ) : null}
    </div>
  );
}
