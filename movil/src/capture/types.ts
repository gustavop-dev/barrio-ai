import type { CapturePurpose } from '@compartido/api/capturas';

/** What a capture is attached to; without it the capture goes loose and the team decides. */
export interface CaptureTarget {
  tipo: 'pregunta' | 'persona' | 'pieza';
  id: string;
  /** Shown as a removable chip at the top of the sheet («¿Aceptas proyectos de 3 meses?»). */
  label?: string;
}

/** A finished recording: a local file (expo-audio writes it to the cache). */
export interface RecordedAudio {
  uri: string;
  mime: string;
  /** Seconds, measured here (the backend replaces it with the real one after transcribing). */
  duration: number;
  /** 24 bars between 0 and 1, for the wave of the finished audio. */
  levels: number[];
}

/** A photo picked from the camera or the gallery. */
export interface PickedPhoto {
  id: string;
  uri: string;
  name: string;
  type: string;
  size: number | null;
}

/** A draft given back to the sheet (after «Deshacer», the sent content returns to it). */
export interface CaptureDraft {
  audio: RecordedAudio | null;
  fotos: PickedPhoto[];
  nota: string;
  para: CapturePurpose | null;
  publicUse: boolean | null;
}

export type MicNoteKind = 'explain' | 'denied' | 'error';

/** MovCaptura: the capture button as it turned into the sheet (its lift and scale at that moment). */
export interface CaptureOrigin {
  lift: number;
  scale: number;
}

/**
 * How the sheet opens, beyond the context:
 * - `recording`: a live recording locked by sliding up (the sheet shows the pulsing ball);
 * - `audio`: the finished audio of a hold released without locking (never sent alone);
 * - `mic`: the microphone could not be used: `explain` asks first;
 * - `view: 'history'`: «Lo que enviaste» (the capture_processed notification, /?enviado=1);
 * - `draft`: content to put back in the sheet;
 * - `from`: opened by the capture button, which turns into the sheet's audio ball (MovCaptura).
 */
export interface CaptureSeed {
  recording?: boolean;
  audio?: RecordedAudio;
  mic?: MicNoteKind;
  view?: 'history';
  draft?: CaptureDraft;
  from?: CaptureOrigin;
}
