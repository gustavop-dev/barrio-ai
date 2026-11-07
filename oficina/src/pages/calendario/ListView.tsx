// Vista Lista: the «Próximo» block on top (the side column on desktop) and every day with everything that happened.
import { useId } from 'react';
import { Link } from 'react-router-dom';
import type { Actividad, ActividadTipo, CalendarLayer, UpcomingPiece } from '../../api/types';
import { Badge, Card, ErrorRetry, Section, Skeleton } from '../../components/ui';
import { pieceStatus } from '../../lib/editorial';
import { formatTime } from '../../lib/format';
import { ActivityList, QueuedRow } from './ActivityList';
import { dayOf, relativeDay } from './dates';
import { firstLines, pieceMeta, pieceWhen, stageShort } from './piece';
import { PlanNextButton, VetoButton } from './Veto';

function UpcomingPieceCard({ piece, today, timeZone, now }: { piece: UpcomingPiece; today: string; timeZone: string; now: number }) {
  const titleId = useId();
  const badge = pieceStatus(piece.status);
  const when = pieceWhen(piece.status, piece.scheduled_for, { today, timeZone, now });
  const meta = pieceMeta(piece);
  return (
    <Card className="cal-piece" aria-labelledby={titleId}>
      <div className="cal-piece-head">
        <Badge tone={badge.tone}>{badge.label}</Badge>
        <span className="t-detalle text-suave">{when}</span>
      </div>
      <p className="t-subtitulo" id={titleId} lang={piece.thesis ? 'en' : undefined}>
        {piece.thesis || 'El equipo prepara la pieza'}
      </p>
      {piece.excerpt ? (
        <p lang="en" className="text-suave">
          {firstLines(piece.excerpt)}
        </p>
      ) : null}
      {piece.status === 'preparing' ? <p className="t-detalle text-suave">Etapa: {stageShort(piece.stage)}</p> : null}
      {meta ? <p className="t-detalle text-suave">{meta}</p> : null}
      {piece.vetoable && piece.action ? (
        <VetoButton block describedBy={titleId} target={{ actionId: piece.action.id, kind: 'pieza', when: `a las ${formatTime(piece.scheduled_for, timeZone)}` }} />
      ) : null}
      <Link to={`/calendario/pieza/${encodeURIComponent(piece.piece_id)}`} className="cal-textlink">
        Ver cómo se escribió
      </Link>
    </Card>
  );
}

/** «Próximo»: the scheduled piece with its countdown and Vetar, and the actions waiting their turn. */
export function Proximo({
  upcoming,
  loading,
  error,
  onRetry,
  today,
  timeZone,
  windowOpen,
  now,
}: {
  upcoming: Actividad['upcoming'] | undefined;
  loading: boolean;
  error: unknown;
  onRetry: () => void;
  today: string;
  timeZone: string;
  windowOpen: boolean | undefined;
  now: number;
}) {
  const pieces = upcoming?.pieces ?? [];
  const [first, ...later] = pieces;
  const queued = upcoming?.queued ?? [];
  return (
    <Section label="Próximo" id="proximo" className="cal-proximo">
      {loading ? <Skeleton variant="card" label="Cargando lo próximo…" /> : null}
      <ErrorRetry error={error} onRetry={onRetry} />
      {upcoming ? (
        first ? (
          <UpcomingPieceCard piece={first} today={today} timeZone={timeZone} now={now} />
        ) : (
          <Card tone="dashed">
            <p>No hay pieza programada para los próximos días.</p>
            <PlanNextButton block />
          </Card>
        )
      ) : null}
      {later.length ? (
        <ul className="cal-rows" aria-label="Después">
          {later.map((piece) => (
            <li key={piece.piece_id} className="cal-row">
              <span className="cal-row-text">
                <Link to={`/calendario/pieza/${encodeURIComponent(piece.piece_id)}`}>{piece.thesis || 'Pieza en preparación'}</Link>
                <span className="cal-row-sub">
                  {relativeDay(dayOf(piece.scheduled_for, timeZone) ?? piece.slot_date, today)} a las {formatTime(piece.scheduled_for, timeZone)} ·{' '}
                  {pieceStatus(piece.status).label}
                </span>
              </span>
            </li>
          ))}
        </ul>
      ) : null}
      {queued.length ? (
        <Card eyebrow="En cola" compact>
          <ul className="cal-rows">
            {queued.map((item) => (
              <QueuedRow key={item.id} item={item} today={today} timeZone={timeZone} windowOpen={windowOpen} />
            ))}
          </ul>
        </Card>
      ) : null}
    </Section>
  );
}

export interface ListViewProps {
  upcoming: Actividad['upcoming'] | undefined;
  upcomingLoading: boolean;
  upcomingError: unknown;
  onRetryUpcoming: () => void;
  tipo: ActividadTipo;
  onTipo: (tipo: ActividadTipo) => void;
  noSalio: boolean;
  onNoSalio: (value: boolean) => void;
  today: string;
  timeZone: string;
  visible: ReadonlySet<CalendarLayer>;
  windowOpen: boolean | undefined;
  now: number;
}

export function ListView(props: ListViewProps) {
  return (
    <div className="split cal-list">
      <div className="cal-list-side">
        <Proximo
          upcoming={props.upcoming}
          loading={props.upcomingLoading}
          error={props.upcomingError}
          onRetry={props.onRetryUpcoming}
          today={props.today}
          timeZone={props.timeZone}
          windowOpen={props.windowOpen}
          now={props.now}
        />
      </div>
      <div className="cal-list-main">
        <Section label="Lo que pasó" id="linea">
          <ActivityList
            tipo={props.tipo}
            onTipo={props.onTipo}
            noSalio={props.noSalio}
            onNoSalio={props.onNoSalio}
            grouped
            today={props.today}
            timeZone={props.timeZone}
            visible={props.visible}
          />
        </Section>
      </div>
    </div>
  );
}
