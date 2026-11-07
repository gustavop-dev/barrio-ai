// The capture button (centre of the mobile bar, «Capturar» in the desktop sidebar) and the
// in-context entry points (a Tu turno question, a person, a piece) all call openCapture().
// App.tsx passes openCaptureSheet (capture/store.ts) as `onCapture`; the sheet itself is
// mounted once by the Layout (CaptureSheetHost). See Captura.dc.html.
import { createContext, useContext, useMemo, type ReactNode } from 'react';
import type { RecordedAudio, Recorder } from './recorder';

/** What a capture is attached to; without it the capture goes loose and the team decides. */
export interface CaptureTarget {
  tipo: 'pregunta' | 'persona' | 'pieza';
  id: string;
  /** Shown as a removable chip at the top of the sheet («¿Aceptas proyectos de 3 meses?»). */
  label?: string;
}

/** A draft given back to the sheet (after «Deshacer», the sent content returns to it). */
export interface CaptureDraft {
  audio: RecordedAudio | null;
  fotos: File[];
  nota: string;
  para: 'post' | 'dato' | 'respuesta' | 'galeria' | null;
  publicUse: boolean | null;
}

/**
 * How the sheet opens, beyond the context. Only the capture button and the sheet use it:
 * - `recorder`: a live recording locked by sliding up (the sheet shows the pulsing ball);
 * - `audio`: the finished audio of a hold released without locking (ready to listen, never sent alone);
 * - `mic`: the microphone could not be used: `explain` asks first, the rest open without audio and a note;
 * - `view: 'history'`: «Lo que enviaste» (the capture_processed notification, /?enviado=1);
 * - `draft`: content to put back in the sheet.
 */
export interface CaptureSeed {
  recorder?: Recorder;
  audio?: RecordedAudio;
  mic?: 'explain' | 'denied' | 'unsupported' | 'error';
  view?: 'history';
  draft?: CaptureDraft;
}

export interface CaptureApi {
  openCapture: (context?: CaptureTarget, seed?: CaptureSeed) => void;
}

const NOOP: CaptureApi = { openCapture: () => {} };

const CaptureContext = createContext<CaptureApi>(NOOP);

export function useCapture(): CaptureApi {
  return useContext(CaptureContext);
}

export interface CaptureProviderProps {
  /** Opens the capture sheet (App.tsx passes openCaptureSheet). Tests pass a spy. */
  onCapture?: (context?: CaptureTarget, seed?: CaptureSeed) => void;
  children: ReactNode;
}

export function CaptureProvider({ onCapture, children }: CaptureProviderProps) {
  const value = useMemo<CaptureApi>(
    () => ({
      // Without a seed the handler gets the context alone, as the in-context entry points expect.
      openCapture: (context, seed) => (seed ? onCapture?.(context, seed) : onCapture?.(context)),
    }),
    [onCapture],
  );
  return <CaptureContext.Provider value={value}>{children}</CaptureContext.Provider>;
}

export const CAPTURE_LABEL = 'Capturar: mantén oprimido para grabar audio, o toca para foto o nota';
