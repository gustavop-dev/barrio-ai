// /calendario/pieza/:pieceId: the result, the veto, the final text and how it was written (DISENO-VISTAS «Detalle de una pieza»).
import { Link, useParams } from 'react-router-dom';
import { usePiece } from '../api/hooks';
import { useCapture } from '../capture/CaptureContext';
import { useTopBarBack, turnoAnchor } from '../components/Layout';
import { IconChevronLeft, IconMicrofono } from '../components/icons';
import { Badge, Button, Card, charCount, CopyButton, ErrorRetry, Note, Page, Section, Skeleton, StageTrack } from '../components/ui';
import { pieceStatus, vetoable } from '../lib/editorial';
import { formatNumber, formatTime, timeAgo } from '../lib/format';
import { ComoSeEscribio } from './calendario/ComoSeEscribio';
import { CALENDAR_TZ, longDay, todayIn } from './calendario/dates';
import { isOnItsWay, pieceLeaves, pieceWhen, preparationStages, publishedAt, stageShort } from './calendario/piece';
import { Resultado } from './calendario/Resultado';
import type { PieceDetailFull, TeamComment } from './calendario/types';
import { useIsDesktop, useNow } from './calendario/useMedia';
import { VetoButton } from './calendario/Veto';
import './calendario/calendario.css';

function StatusNote({ piece }: { piece: PieceDetailFull }) {
  const action = piece.action_detail;
  switch (piece.status) {
    case 'blocked': {
      const reasons = piece.verification?.blocking_reasons?.length ? piece.verification.blocking_reasons : piece.note ? [piece.note] : [];
      return (
        <Note tone="error" title="El verificador bloqueó la pieza" role={null}>
          {reasons.map((reason, index) => (
            <p key={index}>{reason}</p>
          ))}
        </Note>
      );
    }
    case 'skipped':
      return (
        <Note tone="info" title="Ese día no hubo publicación" role={null}>
          {piece.brief?.skip_reason || piece.note || 'El director decidió no publicar: no había material genuino.'}
        </Note>
      );
    case 'vetoed':
      return (
        <Note tone="info" title="La vetaste" role={null}>
          {action?.decision_note ? `Tu nota: ${action.decision_note}` : 'Ese día quedó sin publicación.'}
        </Note>
      );
    case 'discarded':
      return (
        <Note tone="info" title="La política no aprobó la pieza" role={null}>
          {action?.decision_note || piece.note || null}
        </Note>
      );
    case 'failed':
      return (
        <Note tone="error" title="La publicación falló" role={null}>
          {action?.execution?.note || piece.note || null}
        </Note>
      );
    case 'uncertain':
      return (
        <Note
          tone="error"
          title="No se sabe si salió"
          role={null}
          actions={action ? <Link to={`/tu-turno#${turnoAnchor(`uncertain:${action.id}`)}`}>Resuélvela en Tu turno</Link> : null}
        >
          Comprueba en LinkedIn si el post está publicado y dilo en Tu turno.
        </Note>
      );
    default:
      return null;
  }
}

function FinalText({ piece }: { piece: PieceDetailFull }) {
  const text = piece.final_text || piece.selection?.final_text || '';
  if (!text) {
    if (piece.status === 'skipped') return null;
    return (
      <Section label="Texto final" id="texto">
        <p className="text-suave">El texto final aparece cuando termine la selección.</p>
      </Section>
    );
  }
  const lines = text.split('\n').filter((line) => line.trim());
  return (
    <Section label="Texto final" id="texto">
      <Card>
        <div className="pz-final" lang="en">
          {lines.map((line, index) => (
            <p key={index}>{line}</p>
          ))}
        </div>
        <div className="pz-final-foot">
          <p className="t-detalle text-suave">{formatNumber(charCount(text), 0)} caracteres</p>
          <CopyButton text={text} size="small" />
        </div>
        <p className="t-detalle text-suave">Se publica tal cual, en inglés.</p>
      </Card>
    </Section>
  );
}

function TeamComments({ comments, now }: { comments: TeamComment[]; now: number }) {
  return (
    <ul className="pz-comments">
      {comments.map((comment) => {
        const body = [comment.note, comment.transcript].filter(Boolean);
        return (
          <li key={comment.id} className="card compact">
            <p className="t-detalle text-suave">{timeAgo(comment.created_at, now)}</p>
            {(body.length ? body : [comment.text]).filter(Boolean).map((paragraph, index) => (
              <p key={index}>{paragraph}</p>
            ))}
            {comment.has_audio && comment.audio_url && comment.audio_url.startsWith('/') ? (
              <audio controls preload="none" src={comment.audio_url} className="pz-audio">
                Tu navegador no puede reproducir el audio.
              </audio>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}

export function PiezaDetalle() {
  const { pieceId = '' } = useParams();
  const query = usePiece(pieceId);
  const piece = query.data as PieceDetailFull | undefined;
  const { openCapture } = useCapture();
  const desktop = useIsDesktop();
  const now = useNow();
  const timeZone = CALENDAR_TZ;
  const today = todayIn(timeZone, now);
  const backTo = piece ? `/calendario?fecha=${piece.slot_date}` : '/calendario';
  useTopBarBack(piece ? { to: backTo, label: 'Calendario' } : null);

  const back = (
    <Link to={backTo} className="pz-back">
      <IconChevronLeft size={20} />
      Calendario
    </Link>
  );

  if (!piece) {
    return (
      <Page title="Detalle de la pieza" width="narrow">
        {back}
        {query.isPending ? <Skeleton variant="card" count={2} label="Cargando la pieza…" /> : null}
        <ErrorRetry error={query.isError ? query.error : null} onRetry={() => void query.refetch()} title="No se pudo cargar la pieza" />
      </Page>
    );
  }

  const status = pieceStatus(piece.status);
  const day = longDay(piece.slot_date);
  const when =
    piece.status === 'preparing'
      ? `Etapa: ${stageShort(piece.stage)}`
      : isOnItsWay(piece.status)
        ? pieceLeaves(piece.scheduled_for, { today, timeZone })
        : pieceWhen(piece.status, piece.scheduled_for, { today, timeZone, now, published: publishedAt(piece) });
  const canVeto = Boolean(piece.action && vetoable(piece.action));
  const hour = formatTime(piece.scheduled_for, timeZone);
  const comments = piece.team_comments ?? [];
  const captureButton = (
    <Button variant="secondary" block icon={<IconMicrofono size={20} />} onClick={() => openCapture({ tipo: 'pieza', id: piece.id, label: `Pieza del ${day}` })}>
      Comentario para el equipo
    </Button>
  );

  return (
    <Page
      title={`Pieza del ${day}`}
      width="narrow"
      subtitle={
        <span className="pz-status">
          <Badge tone={status.tone}>{status.label}</Badge>
          {when && when !== 'Día sin pieza' ? <span className="t-detalle">{when}</span> : null}
        </span>
      }
    >
      {back}
      <ErrorRetry error={query.isError ? query.error : null} onRetry={() => void query.refetch()} title="No se pudo actualizar la pieza" />
      <StatusNote piece={piece} />

      {piece.status === 'published' || piece.snapshots?.length ? <Resultado piece={piece} timeZone={timeZone} now={now} desktop={desktop} /> : null}

      {canVeto ? (
        <Section label="Veto" id="veto">
          <Card>
            <p>El equipo publica solo. Si no quieres que salga, vétala antes de las {hour}: ese día quedará sin publicación.</p>
            <VetoButton block target={{ actionId: piece.action!.id, kind: 'pieza', when: `a las ${hour}` }} />
          </Card>
        </Section>
      ) : null}

      {piece.status === 'preparing' ? (
        <Section label="Preparándose" id="preparando">
          <Card>
            <StageTrack variant="numbered" stages={preparationStages(piece.stage)} label="Etapas de la preparación" />
            <p className="t-detalle text-suave">{pieceLeaves(piece.scheduled_for, { today, timeZone })}. Puedes vetarla cuando esté lista.</p>
          </Card>
        </Section>
      ) : null}

      <FinalText piece={piece} />

      {comments.length ? (
        <Section label="Tus comentarios para el equipo" id="comentarios">
          <TeamComments comments={comments} now={now} />
          {captureButton}
        </Section>
      ) : (
        captureButton
      )}

      <ComoSeEscribio piece={piece} desktop={desktop} />
    </Page>
  );
}
