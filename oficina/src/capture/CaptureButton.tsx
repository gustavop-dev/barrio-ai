// The aguamarina capture button of the mobile bar (Captura.dc.html), with press-and-hold to record:
// - a short tap (or Enter) opens the sheet without recording;
// - holding grows the button to 72 px and records, with the red dot, the time, the wave and the lock;
// - sliding up locks the recording: it carries on in the sheet, on the pulsing ball;
// - sliding left discards it, with «Recuperar» in the toast;
// - releasing without locking ends it and opens the sheet with the audio ready (never sent alone).
// The microphone is asked for only after explaining why (in the sheet). No vibration: iPhone has none.
import { useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react';
import { IconMicrofono } from '../components/icons';
import { useToast } from '../components/ui';
import { CAPTURE_LABEL, useCapture } from './CaptureContext';
import { IconCandado, IconChevronUp } from './icons';
import { Wave } from './parts';
import { getMicState, mmss, Recorder, useMicState, useRecorder } from './recorder';
import { markCaptureUsed, useCaptureUsed } from './store';
import './capture.css';

/** Hold this long before recording starts (shorter is a tap). */
export const HOLD_DELAY_MS = 220;
/** A hold released sooner than this (from the press) records nothing: it counts as a tap. */
export const MIN_HOLD_MS = 600;
/** Slide up this far to lock, or left this far to discard. */
export const LOCK_DISTANCE = 64;
export const DISCARD_DISTANCE = 110;

interface Gesture {
  pointerId: number | null;
  x0: number;
  y0: number;
  t0: number;
  timer: ReturnType<typeof setTimeout> | null;
  /** The press became a hold (recording, or the sheet opened to explain the microphone). */
  held: boolean;
  recorder: Recorder | null;
  stopWatching: (() => void) | null;
  /** The click that follows a hold must not open the sheet a second time. */
  suppressClickUntil: number;
}

function HoldOverlay({ recorder, dy }: { recorder: Recorder; dy: number }) {
  const snapshot = useRecorder(recorder);
  const lift = Math.max(dy, -60);
  return (
    <div className="cap-hold">
      <div className="cap-lock" aria-hidden="true" style={{ transform: `translate(-50%, ${lift}px)` }}>
        <IconCandado size={22} />
        <IconChevronUp size={18} />
      </div>
      <p className="cap-lock-hint" aria-hidden="true">
        <span>Desliza hacia arriba para bloquear</span>
      </p>
      <div className="cap-holdbar" aria-hidden="true">
        <span className="cap-dot" />
        <span className="cap-holdtime">{mmss(snapshot.elapsed)}</span>
        <Wave levels={snapshot.levels} tone="suave" />
        <span className="cap-cancel-hint">‹ Desliza para cancelar</span>
      </div>
      <p className="vh" role="status">
        Grabando audio. Suelta para terminar, desliza hacia arriba para bloquear o hacia la izquierda para descartar.
      </p>
    </div>
  );
}

export function CaptureButton() {
  const { openCapture } = useCapture();
  const toast = useToast();
  const used = useCaptureUsed();
  // Subscribing keeps the permission known before the first hold.
  useMicState();
  const [hold, setHold] = useState<{ recorder: Recorder; dy: number } | null>(null);
  const gesture = useRef<Gesture>({ pointerId: null, x0: 0, y0: 0, t0: 0, timer: null, held: false, recorder: null, stopWatching: null, suppressClickUntil: 0 });

  // Never leave the microphone open if the bar goes away mid-hold.
  useEffect(
    () => () => {
      const g = gesture.current;
      if (g.timer) clearTimeout(g.timer);
      g.stopWatching?.();
      void g.recorder?.discard();
    },
    [],
  );

  /** Ends the hold state and hands back the recorder (if any). The pointer stays captured until it lifts. */
  const endHold = (): Recorder | null => {
    const g = gesture.current;
    if (g.timer) clearTimeout(g.timer);
    g.timer = null;
    g.stopWatching?.();
    g.stopWatching = null;
    const recorder = g.recorder;
    g.recorder = null;
    setHold(null);
    return recorder;
  };

  const beginHold = () => {
    const g = gesture.current;
    g.timer = null;
    g.held = true;
    // Until the finger lifts (capped, in case the browser never tells).
    g.suppressClickUntil = Date.now() + 10_000;
    markCaptureUsed();
    const mic = getMicState();
    if (mic !== 'granted') {
      // Explain before the browser asks; or say why there is no audio.
      openCapture(undefined, { mic: mic === 'denied' ? 'denied' : mic === 'unsupported' ? 'unsupported' : 'explain' });
      return;
    }
    const recorder = Recorder.start();
    g.recorder = recorder;
    g.stopWatching = recorder.subscribe(() => {
      if (recorder.state !== 'error' || gesture.current.recorder !== recorder) return;
      endHold();
      openCapture(undefined, { mic: recorder.problem?.problem ?? 'error' });
    });
    setHold({ recorder, dy: 0 });
  };

  const onPointerDown = (event: ReactPointerEvent<HTMLButtonElement>) => {
    if (event.button !== 0 || !event.isPrimary) return;
    const g = gesture.current;
    if (g.recorder) return;
    g.pointerId = event.pointerId;
    g.x0 = event.clientX;
    g.y0 = event.clientY;
    g.t0 = Date.now();
    g.held = false;
    g.suppressClickUntil = 0;
    try {
      event.currentTarget.setPointerCapture?.(event.pointerId);
    } catch {
      // jsdom and old browsers: the button still gets the events while the finger stays on it.
    }
    if (g.timer) clearTimeout(g.timer);
    g.timer = setTimeout(beginHold, HOLD_DELAY_MS);
  };

  const onPointerMove = (event: ReactPointerEvent<HTMLButtonElement>) => {
    const g = gesture.current;
    if (!g.recorder || event.pointerId !== g.pointerId) return;
    const dy = Math.min(0, event.clientY - g.y0);
    const dx = Math.min(0, event.clientX - g.x0);
    if (dy < -LOCK_DISTANCE) {
      const recorder = endHold();
      if (recorder) openCapture(undefined, { recorder });
      return;
    }
    if (dx < -DISCARD_DISTANCE) {
      const recorder = endHold();
      if (!recorder) return;
      void recorder.discard().then((audio) => {
        toast.show('Grabación descartada.', audio ? { undo: () => openCapture(undefined, { audio }), undoLabel: 'Recuperar' } : {});
      });
      return;
    }
    setHold((current) => (current ? { ...current, dy } : current));
  };

  const onPointerUp = (event: ReactPointerEvent<HTMLButtonElement>) => {
    const g = gesture.current;
    if (g.pointerId !== null && event.pointerId !== g.pointerId) return;
    g.pointerId = null;
    if (g.timer) {
      // Released before the hold started: a tap. The click that follows opens the sheet.
      clearTimeout(g.timer);
      g.timer = null;
      return;
    }
    if (!g.held) return;
    g.suppressClickUntil = Date.now() + 400;
    const startedAt = g.t0;
    const recorder = endHold();
    if (!recorder) return;
    if (Date.now() - startedAt < MIN_HOLD_MS) {
      void recorder.discard();
      openCapture();
      return;
    }
    void recorder.stop().then((audio) => {
      if (audio) openCapture(undefined, { audio });
      else if (recorder.problem) openCapture(undefined, { mic: recorder.problem.problem });
      else openCapture();
    });
  };

  const onClick = () => {
    if (Date.now() < gesture.current.suppressClickUntil) return;
    markCaptureUsed();
    openCapture();
  };

  return (
    <div className="capture-slot">
      {!used && !hold ? (
        <div className="cap-hint" aria-hidden="true">
          Mantén oprimido para grabar. Toca para foto o nota.
        </div>
      ) : null}
      {hold ? <HoldOverlay recorder={hold.recorder} dy={hold.dy} /> : null}
      <button
        type="button"
        className={hold ? 'capture-button holding' : 'capture-button'}
        style={hold ? { transform: `translateY(${Math.max(hold.dy, -60)}px)` } : undefined}
        aria-label={CAPTURE_LABEL}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        onClick={onClick}
        onContextMenu={(event) => event.preventDefault()}
      >
        <IconMicrofono size={hold ? 30 : 26} />
      </button>
    </div>
  );
}
