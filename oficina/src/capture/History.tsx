// «Lo que enviaste»: the capture history inside the sheet (Captura.dc.html, rev 18).
import { useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { captureKeys, sameOrigin, undoCaptura, useCapturaLive, useCapturas, type CaptureOutput } from '../api/capturas';
import { keys } from '../api/queryClient';
import { IconChevronLeft, IconPausa, IconPlay } from '../components/icons';
import { Badge, Button, EmptyState, ErrorRetry, Skeleton, errorMessage, useToast } from '../components/ui';
import { excerpt } from '../lib/format';
import { publishAsapLines, canUndo, CONTEXT_PREFIX, contentsOf, purposeOf, STATE_TONE } from '../../../compartido/src/logic/capturas';
import { useAudioPlayback, whenLabel } from './parts';

// Labels shared with the native app (compartido/src/logic/capturas.ts).
export { contentsOf, purposeOf };

function Listen({ url }: { url: string }) {
  const { playing, toggle } = useAudioPlayback(url);
  return (
    <Button variant="secondary" size="small" icon={playing ? <IconPausa size={20} /> : <IconPlay size={20} />} onClick={toggle} aria-pressed={playing}>
      {playing ? 'Pausar' : 'Escuchar'}
    </Button>
  );
}

/** Re-renders when the 2 minutes of «Deshacer» run out, so the button goes away on time (CAP-10). */
function useUndoClock(capture: CaptureOutput): number {
  const [now, setNow] = useState(() => Date.now());
  const until = capture.can_undo && capture.undo_until ? Date.parse(capture.undo_until) : NaN;
  useEffect(() => {
    const left = until - Date.now();
    if (!(left > 0)) return;
    const timer = setTimeout(() => setNow(Date.now()), left + 50);
    return () => clearTimeout(timer);
  }, [until]);
  return now;
}

function CaptureCard({ initial, listUpdatedAt, onNavigate }: { initial: CaptureOutput; listUpdatedAt: number; onNavigate: () => void }) {
  const live = useCapturaLive(initial);
  const capture = live.data && live.dataUpdatedAt >= listUpdatedAt ? live.data : initial;
  const client = useQueryClient();
  const toast = useToast();
  const [undoing, setUndoing] = useState(false);
  const now = useUndoClock(capture);
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
      {capture.publish_asap ? (
        <div data-testid={`capture-asap-${capture.id}`}>
          {publishAsapLines(capture).map((line, index) => <p key={index} className="t-detalle text-suave">{line}</p>)}
        </div>
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
            <CaptureCard key={capture.id} initial={capture} listUpdatedAt={history.dataUpdatedAt} onNavigate={onNavigate} />
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
