import { useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { ApiError } from '../api/client';
import { useMarkNotificacionesRead, useNotificaciones, type NotificationFilter, type NotificationItem } from '../api/notificaciones';
import { CALENDAR_LAYERS } from '../api/types';
import { Badge, Button, Card, ChipStrip, ErrorRetry, FilterChip, LAYER_COLOR, Page, Section, Skeleton } from '../components/ui';
import { groupNotifications, isUnread, timeLabel } from './notificaciones/model';
import './notificaciones/notificaciones.css';

const FILTERS: readonly { value: NotificationFilter; label: string }[] = [
  { value: 'todas', label: 'Todas' },
  { value: 'sin_leer', label: 'Sin leer' },
];

/** The backend does not serve Notificaciones yet (404/501): the intentional «Aún no disponible», never an error. */
function isUnavailable(error: unknown): boolean {
  return error instanceof ApiError && (error.status === 404 || error.status === 501);
}

function dotColor(item: NotificationItem): string {
  return (CALENDAR_LAYERS as readonly string[]).includes(item.layer) ? LAYER_COLOR[item.layer] : 'var(--color-linea)';
}

function Row({ item, upcoming, onOpen }: { item: NotificationItem; upcoming: boolean; onOpen: (item: NotificationItem) => void }) {
  const unread = isUnread(item);
  const time = timeLabel(item, upcoming);
  const content: ReactNode = (
    <>
      <span className="notif-dot" aria-hidden="true" style={{ background: dotColor(item) }} />
      <span className="notif-text">
        {time ? <span className="notif-time">{time}</span> : null}
        <span className="notif-title">{item.title}</span>
        {item.detail ? <span className="notif-detail">{item.detail}</span> : null}
      </span>
      {unread ? (
        <Badge tone="ok" className="notif-new">
          Nueva
        </Badge>
      ) : null}
    </>
  );
  const className = unread ? 'notif-row unread' : 'notif-row';
  // In-app destinations only; anything else marks the item read and stays here.
  if (item.link && item.link.startsWith('/') && !item.link.startsWith('//')) {
    return (
      <Link to={item.link} className={className} onClick={() => onOpen(item)}>
        {content}
      </Link>
    );
  }
  return unread ? (
    <button type="button" className={className} onClick={() => onOpen(item)}>
      {content}
    </button>
  ) : (
    <div className={className}>{content}</div>
  );
}

/**
 * Notificaciones (/notificaciones): what is coming or happened and asks nothing of Gustavo, 7 days.
 * Opening an item marks it read; the bell dot follows through Tu turno's `notifications_unread`.
 */
export function Notificaciones() {
  const [filtro, setFiltro] = useState<NotificationFilter>('todas');
  const query = useNotificaciones(filtro);
  const mark = useMarkNotificacionesRead();
  const groups = groupNotifications(query.data, filtro);
  const unread = query.data?.unread ?? 0;

  const open = (item: NotificationItem) => {
    if (isUnread(item)) mark.mutate({ ids: [item.id] });
  };

  return (
    <Page
      title="Notificaciones"
      subtitle={
        <>
          Lo que viene y lo que pasó. Nada de esto necesita que hagas algo; lo que sí, está en <Link to="/tu-turno">tu Bandeja</Link>.
        </>
      }
      width="narrow"
    >
      <div className="notif-bar">
        <ChipStrip label="Filtrar" className="notif-filters">
          {FILTERS.map((filter) => (
            <FilterChip key={filter.value} pressed={filtro === filter.value} onClick={() => setFiltro(filter.value)}>
              {filter.label}
            </FilterChip>
          ))}
        </ChipStrip>
        <Button variant="ghost" size="small" className="notif-readall" disabled={!query.data || unread <= 0 || mark.isPending} onClick={() => mark.mutate({ todas: true })}>
          Marcar todo como leído
        </Button>
      </div>
      <ErrorRetry error={mark.error} title="No se pudo marcar como leído" />
      {query.isPending ? <Skeleton variant="row" count={4} label="Cargando notificaciones…" /> : null}
      {query.error && !query.data && isUnavailable(query.error) ? (
        <Card tone="dashed">
          <p className="t-cuerpo">Aún no disponible</p>
          <p className="t-detalle text-suave">Mientras tanto, lo que viene y lo que pasó está en el Calendario.</p>
        </Card>
      ) : query.error ? (
        <ErrorRetry error={query.error} onRetry={() => void query.refetch()} title={query.data ? 'No se pudo actualizar' : undefined} />
      ) : null}
      {groups.map((group) => (
        <Section key={group.key} id={`notif-${group.key}`} label={group.title} className="notif-group">
          <ul className="notif-list">
            {group.items.map((item) => (
              <li key={item.id}>
                <Row item={item} upcoming={group.upcoming} onOpen={open} />
              </li>
            ))}
          </ul>
        </Section>
      ))}
      {query.data && !groups.length ? <p className="notif-empty">No hay nada nuevo. Lo de días anteriores sigue en el Calendario.</p> : null}
      <p className="notif-foot">
        Se guardan 7 días. Lo anterior está en el <Link to="/calendario">Calendario</Link>.
      </p>
    </Page>
  );
}
