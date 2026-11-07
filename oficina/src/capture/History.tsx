// «Lo que enviaste»: the capture history inside the sheet (Captura.dc.html, rev 18).
import { useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { captureKeys, isProcessing, sameOrigin, undoCaptura, useCapturaLive, useCapturas, type CaptureOutput } from '../api/capturas';
import { keys } from '../api/queryClient';
import { IconChevronLeft, IconPausa, IconPlay } from '../components/icons';
import { Badge, Button, EmptyState, ErrorRetry, Skeleton, errorMessage, useToast, type Tone } from '../components/ui';
import { excerpt } from '../lib/format';
import { fotosLabel, useAudioPlayback, whenLabel } from './parts';
import { mmss } from './recorder';

const STATE_TONE: Record<string, Tone> = {
  recibida: 'info',
  transcribiendo: 'info',
  procesando: 'info',
  dato_guardado: 'ok',
  anotado: 'ok',
  idea: 'ok',
  usado: 'ok',
  sin_usar: 'muted',
  error: 'bad',
  deshecha: 'muted',
};

const CONTEXT_PREFIX: Record<string, string> = {
  pregunta: 'Responde a',
  persona: 'Sobre',
  pieza: 'Sobre la pieza',
};

/** «AUDIO 0:42», «2 FOTOS», «NOTA». */
export function contentsOf(capture: Pick<CaptureOutput, 'has_audio' | 'audio_duration_s' | 'photos' | 'note'>): string[] {
  const parts: string[] = [];
  if (capture.has_audio) parts.push(capture.audio_duration_s ? `Audio ${mmss(capture.audio_duration_s)}` : 'Audio');
  if (capture.photos?.length) parts.push(fotosLabel(capture.photos.length));
  if (capture.note?.trim()) parts.push('Nota');
  return parts;
}

/** «Idea para un post», «Dato sobre mí · lo decidió el equipo», «El equipo decide». */
export function purposeOf(capture: Pick<CaptureOutput, 'purpose_label' | 'team_decided' | 'state'>): string {
  if (capture.purpose_label) return capture.purpose_label;
  if (capture.team_decided?.label) return `${capture.team_decided.label} · lo decidió el equipo`;
  return isProcessing(capture.state) ? 'El equipo lo transcribe y decide' : 'Sin elegir';
}

function canUndo(capture: CaptureOutput, now: number): boolean {
  if (!capture.can_undo || !capture.undo_until) return false;
  const until = Date.parse(capture.undo_until);
  return Number.isFinite(until) && until > now;
}

function Listen({ url }: { url: string }) {
  const { playing, toggle } = useAudioPlayback(url);
  return (
    <Button variant="secondary" size="small" icon={playing ? <IconPausa size={20} /> : <IconPlay size={20} />} onClick={toggle} aria-pressed={playing}>
      {playing ? 'Pausar' : 'Escuchar'}
    </Button>
  );
}

function CaptureCard({ initial, onNavigate }: { initial: CaptureOutput; onNavigate: () => void }) {
  const live = useCapturaLive(initial);
  const capture = live.data ?? initial;
  const client = useQueryClient();
  const toast = useToast();
  const [undoing, setUndoing] = useState(false);
  const [now] = useState(() => Date.now());
  const contents = contentsOf(capture);
  const text = capture.transcript?.trim() ? `«${excerpt(capture.transcript, 240)}»` : capture.note?.trim() ? excerpt(capture.note, 240) : '';
  const noteToo = Boolean(capture.transcript?.trim() && capture.note?.trim());
  const audioUrl = capture.has_audio ? sameOrigin(capture.audio_url) : null;
  const outcomeLink = capture.outcome?.link && capture.outcome.link.startsWith('/') ? capture.outcome.link : null;

  const undo = async () => {
    setUndoing(true);
    try {
      await undoCaptura(capture.id);
      toast.show('Envío deshecho.');
    } catch (error) {
      toast.show(errorMessage(error), { tone: 'error' });
    } finally {
      setUndoing(false);
      void client.invalidateQueries({ queryKey: captureKeys.all });
      void client.invalidateQueries({ queryKey: keys.tuTurno });
    }
  };

  return (
    <li className="card cap-sent">
      <div className="cap-sent-chips">
        {contents.map((part) => (
          <Badge key={part} tone="ink">
            {part}
          </Badge>
        ))}
      </div>
      <p className="t-detalle text-suave">
        {whenLabel(capture.created_at)} · {purposeOf(capture)}
      </p>
      {capture.context ? (
        <p className="t-detalle text-suave">
          {CONTEXT_PREFIX[capture.context.tipo] ?? 'Sobre'}: {capture.context.label}
        </p>
      ) : null}
      {text ? <p className="cap-sent-text">{text}</p> : null}
      {noteToo ? <p className="t-detalle text-suave">Nota: {excerpt(capture.note, 200)}</p> : null}
      <div className="cap-sent-state">
        <Badge tone={STATE_TONE[capture.state] ?? 'muted'}>{capture.state_label || capture.state}</Badge>
        <p className="t-detalle text-suave">
          {capture.outcome?.text ? (
            outcomeLink ? (
              <Link to={outcomeLink} onClick={onNavigate}>
                {capture.outcome.text}
              </Link>
            ) : (
              capture.outcome.text
            )
          ) : null}
          {capture.state === 'error' && capture.error ? <span className="cap-sent-error"> {capture.error}</span> : null}
        </p>
      </div>
      {audioUrl || canUndo(capture, now) ? (
        <div className="cap-sent-actions">
          {audioUrl ? <Listen url={audioUrl} /> : null}
          {canUndo(capture, now) ? (
            <Button variant="ghost" size="small" loading={undoing} loadingLabel="Deshaciendo…" onClick={() => void undo()}>
              Deshacer
            </Button>
          ) : null}
        </div>
      ) : null}
    </li>
  );
}

export function CaptureHistory({ onBack, onNavigate }: { onBack: () => void; onNavigate: () => void }) {
  const history = useCapturas();
  return (
    <div className="cap-history">
      <button type="button" className="cap-back" onClick={onBack}>
        <IconChevronLeft size={20} />
        Volver a la captura
      </button>
      {history.isPending ? <Skeleton variant="card" count={2} label="Cargando lo que enviaste…" /> : null}
      <ErrorRetry error={history.error} onRetry={() => void history.refetch()} />
      {history.isSuccess && history.items.length === 0 ? (
        <EmptyState title="Todavía no has enviado nada">Lo que mandes aparecerá aquí, con lo que hizo el equipo.</EmptyState>
      ) : null}
      {history.items.length ? (
        <ul className="cap-sent-list">
          {history.items.map((capture) => (
            <CaptureCard key={capture.id} initial={capture} onNavigate={onNavigate} />
          ))}
        </ul>
      ) : null}
      {history.hasNextPage ? (
        <Button variant="secondary" block loading={history.isFetchingNextPage} loadingLabel="Cargando…" onClick={() => void history.fetchNextPage()}>
          Ver envíos anteriores
        </Button>
      ) : null}
    </div>
  );
}
