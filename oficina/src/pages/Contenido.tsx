import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState, type FormEvent } from 'react';
import { Link, Navigate, useParams, useSearchParams } from 'react-router-dom';
import { getCalendar, planPiece } from '../api/endpoints';
import { keys } from '../api/queryClient';
import type { EditorialCalendar, PieceStatus, PieceSummary } from '../api/types';
import { VetoPiece } from '../components/VetoPiece';
import { Badge, Empty, ErrorNote, ExternalLink, Loading, Modal, PageHeader } from '../components/ui';
import { label, MODALITY_LABEL, pieceStatus, PILLAR_LABEL, readerLabel, STAGE_LABEL, vetoable } from '../lib/editorial';
import { capitalize, formatDay, formatTime, shiftDay } from '../lib/format';

export const CALENDAR_DAYS = 15;
const DATE = /^\d{4}-\d{2}-\d{2}$/;
/** Pieces still on their way to LinkedIn. */
const UPCOMING: readonly PieceStatus[] = ['preparing', 'awaiting_approval', 'scheduled', 'publishing'];

function hours(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toLocaleString('es-CO', { maximumFractionDigits: 1 });
}

/** Always visible: pieces go out on their own unless Gustavo vetoes them. */
function AutonomyNote({ calendar }: { calendar: EditorialCalendar | undefined }) {
  const when = calendar?.post_time ? ` a las ${calendar.post_time} (${calendar.timezone})` : ' a su hora';
  return (
    <section className="note info" aria-labelledby="autonomy-title">
      <strong id="autonomy-title">Publicación autónoma: las piezas salen solas</strong>
      <p>
        Cada pieza que pasa el verificador se publica sola{when} por la política autónoma, sin revisión pieza a pieza. Solo deja de salir si
        la vetas antes de su hora.
        {calendar ? ` La preparación empieza ${hours(calendar.lead_hours)} h antes, para que tengas margen.` : ''}
      </p>
    </section>
  );
}

function newRequestId(): string | undefined {
  try {
    return typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function' ? crypto.randomUUID() : undefined;
  } catch {
    return undefined;
  }
}

/** POST /editorial/plan behind an explicit confirmation: the circuit calls Claude and costs money. */
function PlanNext() {
  const queryClient = useQueryClient();
  const [asking, setAsking] = useState(false);
  // One id per intent: a retry after a network error never queues a second preparation.
  const [requestId, setRequestId] = useState<string | undefined>(undefined);
  const mutation = useMutation({
    mutationFn: (id: string | undefined) => planPiece(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: keys.editorialAll });
      void queryClient.invalidateQueries({ queryKey: keys.overview });
      setAsking(false);
    },
  });
  const open = () => {
    mutation.reset();
    setRequestId(newRequestId());
    setAsking(true);
  };
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!mutation.isPending) mutation.mutate(requestId);
  };
  return (
    <>
      <div className="buttonrow">
        <button type="button" className="primary" onClick={open} disabled={mutation.isPending}>
          Preparar la siguiente pieza
        </button>
      </div>
      {mutation.isSuccess ? (
        <p className="note ok" role="status">
          Preparación en cola para el {formatDay(mutation.data.slot_date)}. El circuito tarda unos minutos y la pieza aparecerá en el
          calendario.
        </p>
      ) : null}
      {asking ? (
        <Modal title="Preparar la siguiente pieza" onClose={() => setAsking(false)}>
          <form onSubmit={submit}>
            <p>
              Pone en cola el circuito editorial para el próximo día libre (como mucho a siete días): director, dos redactores, panel de
              lectores, selección y verificador.
            </p>
            <p className="note warn">
              Tiene coste: cada etapa llama a Claude y gasta del presupuesto editorial del día. Si la pieza pasa el verificador, saldrá sola a
              su hora salvo que la vetes.
            </p>
            <ErrorNote error={mutation.error} />
            <div className="buttonrow">
              <button type="button" className="secondary" onClick={() => setAsking(false)}>
                Cancelar
              </button>
              <button type="submit" className="primary" disabled={mutation.isPending}>
                {mutation.isPending ? 'Enviando…' : 'Preparar'}
              </button>
            </div>
          </form>
        </Modal>
      ) : null}
    </>
  );
}

function pieceTitle(piece: PieceSummary): string {
  if (piece.thesis) return piece.thesis;
  if (piece.status === 'preparing') return 'Pieza en preparación';
  return 'Pieza sin brief';
}

export function PieceCard({ piece, timeZone, idPrefix = 'piece' }: { piece: PieceSummary; timeZone?: string | undefined; idPrefix?: string }) {
  const status = pieceStatus(piece.status);
  const titleId = `${idPrefix}-${piece.id}`;
  const facts = [
    formatTime(piece.scheduled_for, timeZone),
    piece.pillar ? label(PILLAR_LABEL, piece.pillar) : null,
    piece.modality ? label(MODALITY_LABEL, piece.modality) : null,
    piece.primary_reader ? readerLabel(piece.primary_reader) : null,
  ].filter(Boolean);
  const showNote = piece.note && (piece.status === 'skipped' || piece.status === 'blocked' || piece.status === 'failed');
  return (
    <article className="piece" aria-labelledby={titleId}>
      <div className="cardhead">
        <h4 id={titleId}>
          <Link to={`/contenido/${encodeURIComponent(piece.id)}`}>{pieceTitle(piece)}</Link>
        </h4>
        <Badge tone={status.tone}>{status.label}</Badge>
      </div>
      <p className="muted small">{facts.join(' · ')}</p>
      {piece.status === 'preparing' && piece.stage ? <p className="small">Etapa: {label(STAGE_LABEL, piece.stage)}</p> : null}
      {showNote ? <p className="small">{piece.note}</p> : null}
      <ExternalLink href={piece.external_url}>Ver el post publicado</ExternalLink>
      {piece.action && vetoable(piece.action) ? (
        <div className="buttonrow">
          <span className="small muted">Sale sola salvo veto.</span>
          <VetoPiece
            actionId={piece.action.id}
            slotDate={piece.slot_date}
            scheduledFor={piece.scheduled_for}
            timeZone={timeZone}
            describedBy={titleId}
          />
        </div>
      ) : null}
    </article>
  );
}

function CalendarDays({ calendar }: { calendar: EditorialCalendar }) {
  return (
    <ol className="calendar" aria-labelledby="calendar-title">
      {calendar.days.map((day) => {
        const today = day.date === calendar.today;
        return (
          <li key={day.date} className={today ? 'day today' : 'day'} aria-current={today ? 'date' : undefined}>
            <h3>
              <time dateTime={day.date}>{capitalize(formatDay(day.date))}</time> {today ? <Badge tone="info">Hoy</Badge> : null}
            </h3>
            {day.pieces.length ? (
              day.pieces.map((piece) => <PieceCard key={piece.id} piece={piece} timeZone={calendar.timezone} />)
            ) : (
              <p className="gap">{day.date < calendar.today ? 'Sin publicación.' : 'Hueco libre: aún sin pieza.'}</p>
            )}
          </li>
        );
      })}
    </ol>
  );
}

export function Contenido() {
  const [params, setParams] = useSearchParams();
  const raw = params.get('desde') ?? '';
  const desde = DATE.test(raw) ? raw : '';
  const query = useQuery({
    queryKey: keys.calendar(desde),
    queryFn: () => getCalendar(desde, CALENDAR_DAYS),
    placeholderData: keepPreviousData,
    refetchInterval: 60_000,
  });
  const calendar = query.data;
  const first = calendar?.days[0]?.date;
  const upcoming = calendar
    ? calendar.days
        .filter((day) => day.date >= calendar.today)
        .flatMap((day) => day.pieces)
        .filter((piece) => UPCOMING.includes(piece.status))
    : [];
  const next = upcoming[0];
  const move = (date: string | null) => setParams(date ? { desde: date } : {}, { replace: true });

  return (
    <div className="stack">
      <PageHeader eyebrow="PUBLICACIÓN DIARIA" title="Contenido">
        El circuito editorial prepara una pieza al día: director, dos redactores, panel de lectores y verificador. Aquí ves el calendario, el
        detalle de cada pieza y puedes vetarla.
      </PageHeader>
      <AutonomyNote calendar={calendar} />
      {calendar?.config_error ? (
        <p className="note warn" role="note">
          Configuración editorial inválida en el servidor: {calendar.config_error}
        </p>
      ) : null}

      <section className="card" aria-labelledby="next-title">
        <h2 id="next-title">Próxima pieza</h2>
        {next ? (
          <>
            <p className="small muted">{capitalize(formatDay(next.slot_date))}</p>
            <PieceCard piece={next} timeZone={calendar?.timezone} idPrefix="next" />
          </>
        ) : query.isSuccess ? (
          <Empty>No hay ninguna pieza en preparación ni programada en estas fechas.</Empty>
        ) : null}
        <PlanNext />
      </section>

      <section className="stack" aria-labelledby="calendar-title">
        <div className="cardhead">
          <h2 id="calendar-title">Calendario</h2>
          {first ? (
            <div className="buttonrow calendarnav">
              <button type="button" className="secondary" onClick={() => move(shiftDay(first, -CALENDAR_DAYS))}>
                ← Anteriores
              </button>
              <button type="button" className="secondary" onClick={() => move(null)} disabled={!desde}>
                Hoy
              </button>
              <button type="button" className="secondary" onClick={() => move(shiftDay(first, CALENDAR_DAYS))}>
                Siguientes →
              </button>
            </div>
          ) : null}
        </div>
        {query.isPending ? <Loading label="Cargando el calendario…" /> : null}
        {query.isError ? <ErrorNote error={query.error} onRetry={() => void query.refetch()} /> : null}
        {calendar ? <CalendarDays calendar={calendar} /> : null}
      </section>
    </div>
  );
}

/** Push notifications of the backend open `/editorial/<id>`: same piece, PWA route. */
export function EditorialRedirect() {
  const { pieceId } = useParams();
  return <Navigate to={pieceId ? `/contenido/${encodeURIComponent(pieceId)}` : '/contenido'} replace />;
}
