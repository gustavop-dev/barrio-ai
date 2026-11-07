// Audio recording for the capture (MediaRecorder) and the microphone permission.
// The audio stays in memory until «Guardar y enviar al equipo»: nothing is uploaded while recording.
import { useCallback, useSyncExternalStore } from 'react';

export interface RecordedAudio {
  blob: Blob;
  mime: string;
  /** Seconds, measured here (the backend replaces it with the real one after transcribing). */
  duration: number;
  /** 24 bars between 0 and 1, for the wave of the finished audio. */
  levels: number[];
}

export type RecorderState = 'starting' | 'recording' | 'paused' | 'stopped' | 'error';

/** Why the microphone could not be used: denied by the person or the browser, missing, or another failure. */
export type MicProblem = 'denied' | 'unsupported' | 'error';

export class MicError extends Error {
  readonly problem: MicProblem;
  constructor(problem: MicProblem, message: string) {
    super(message);
    this.name = 'MicError';
    this.problem = problem;
  }
}

export const WAVE_BARS = 24;
/** The contract caps `audio_duration_s` at 1800: the recording stops by itself at 30 minutes. */
export const MAX_SECONDS = 1800;

const MIME_CANDIDATES = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg;codecs=opus', 'audio/aac'];

/** File name for the multipart part, by type (webm/opus, mp4/m4a, ogg, aac, wav). */
export function audioFilename(mime: string): string {
  const type = mime.toLowerCase();
  if (type.includes('webm')) return 'captura.webm';
  if (type.includes('mp4') || type.includes('m4a')) return 'captura.m4a';
  if (type.includes('ogg')) return 'captura.ogg';
  if (type.includes('aac')) return 'captura.aac';
  if (type.includes('wav')) return 'captura.wav';
  if (type.includes('mpeg') || type.includes('mp3')) return 'captura.mp3';
  return 'captura.webm';
}

/** «0:42», «12:05». */
export function mmss(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds));
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`;
}

/** Downsamples (or pads) levels to `bars` values. */
export function toBars(levels: number[], bars = WAVE_BARS): number[] {
  if (!levels.length) return Array.from({ length: bars }, () => 0);
  if (levels.length <= bars) return [...Array.from({ length: bars - levels.length }, () => 0), ...levels];
  const size = levels.length / bars;
  return Array.from({ length: bars }, (_, i) => {
    const slice = levels.slice(Math.floor(i * size), Math.max(Math.floor(i * size) + 1, Math.floor((i + 1) * size)));
    return Math.max(...slice);
  });
}

function pickMime(): string {
  const Recorder = globalThis.MediaRecorder as typeof MediaRecorder | undefined;
  if (!Recorder || typeof Recorder.isTypeSupported !== 'function') return '';
  return MIME_CANDIDATES.find((type) => Recorder.isTypeSupported(type)) ?? '';
}

export function canRecord(): boolean {
  return typeof navigator !== 'undefined' && Boolean(navigator.mediaDevices?.getUserMedia) && typeof globalThis.MediaRecorder === 'function';
}

function micErrorFrom(error: unknown): MicError {
  const name = error instanceof Error || (typeof DOMException !== 'undefined' && error instanceof DOMException) ? (error as Error).name : '';
  if (name === 'NotAllowedError' || name === 'SecurityError' || name === 'PermissionDeniedError') {
    return new MicError('denied', 'El micrófono está bloqueado para 0ff1ce.');
  }
  if (name === 'NotFoundError' || name === 'DevicesNotFoundError' || name === 'OverconstrainedError') {
    return new MicError('unsupported', 'No se encontró ningún micrófono en este dispositivo.');
  }
  return new MicError('error', 'No se pudo usar el micrófono. Vuelve a intentarlo.');
}

// ---------------------------------------------------------------- microphone permission

export type MicState = 'granted' | 'denied' | 'prompt' | 'unsupported' | 'unknown';

const GRANTED_FLAG = 'oficina.microfono.permitido';
let micState: MicState = 'unknown';
const micListeners = new Set<() => void>();
let watching = false;

function setMicState(next: MicState) {
  if (next === micState) return;
  micState = next;
  try {
    if (next === 'granted') localStorage.setItem(GRANTED_FLAG, '1');
    if (next === 'denied') localStorage.removeItem(GRANTED_FLAG);
  } catch {
    // Private mode or blocked storage: the permission API (or the next request) still knows.
  }
  micListeners.forEach((listener) => listener());
}

function storedGrant(): boolean {
  try {
    return localStorage.getItem(GRANTED_FLAG) === '1';
  } catch {
    return false;
  }
}

/** Reads the permission (Permissions API when there is one) and keeps following its changes. */
export async function refreshMicState(): Promise<MicState> {
  if (!canRecord()) {
    setMicState('unsupported');
    return micState;
  }
  try {
    const status = await navigator.permissions.query({ name: 'microphone' as PermissionName });
    setMicState(status.state as MicState);
    if (!watching) {
      watching = true;
      status.addEventListener?.('change', () => setMicState(status.state as MicState));
    }
  } catch {
    // Without the Permissions API, only a granted request tells: remember it on this device.
    setMicState(micState === 'unknown' ? (storedGrant() ? 'granted' : 'prompt') : micState);
  }
  return micState;
}

export function getMicState(): MicState {
  return micState;
}

function subscribeMic(listener: () => void) {
  micListeners.add(listener);
  if (micState === 'unknown') void refreshMicState();
  return () => micListeners.delete(listener);
}

/** The microphone permission, kept up to date (Ajustes › Captura y galería, the capture button). */
export function useMicState(): MicState {
  return useSyncExternalStore(subscribeMic, getMicState, () => 'unknown');
}

/** Asks the browser for the microphone and lets it go at once (Ajustes «Permitir el micrófono»). */
export async function requestMic(): Promise<MicState> {
  if (!canRecord()) throw new MicError('unsupported', 'Este navegador no permite grabar audio.');
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    stream.getTracks().forEach((track) => track.stop());
    setMicState('granted');
    return 'granted';
  } catch (error) {
    const problem = micErrorFrom(error);
    if (problem.problem === 'denied') setMicState('denied');
    throw problem;
  }
}

/** For tests: forget what is known about the permission. */
export function resetMicStateForTests(state: MicState = 'unknown') {
  micState = state;
  watching = false;
}

// ---------------------------------------------------------------- recorder

type Listener = () => void;

/**
 * One recording. `Recorder.start()` returns at once in `starting` (so the button can grow while the
 * browser opens the microphone) and moves to `recording`, or to `error` with `problem`.
 * Subscribers hear every state change and a tick ~4 times a second (time and wave).
 */
export class Recorder {
  state: RecorderState = 'starting';
  problem: MicError | null = null;
  /** The last WAVE_BARS levels, newest last. */
  levels: number[] = Array.from({ length: WAVE_BARS }, () => 0);
  /** Set when the recording stopped by itself at MAX_SECONDS. */
  autoStopped: RecordedAudio | null = null;

  private listeners = new Set<Listener>();
  private media: MediaRecorder | null = null;
  private stream: MediaStream | null = null;
  private chunks: Blob[] = [];
  private history: number[] = [];
  private accumulated = 0;
  private resumedAt = 0;
  private ticker: ReturnType<typeof setInterval> | null = null;
  private audioContext: AudioContext | null = null;
  private analyser: AnalyserNode | null = null;
  private ready: Promise<void>;
  private result: Promise<RecordedAudio | null> | null = null;
  private discarded = false;

  private constructor() {
    this.ready = this.open();
  }

  static start(): Recorder {
    return new Recorder();
  }

  subscribe(listener: Listener): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  /** Seconds recorded, without the paused time. */
  elapsed(): number {
    const running = this.state === 'recording' && this.resumedAt ? Date.now() - this.resumedAt : 0;
    return (this.accumulated + running) / 1000;
  }

  get active(): boolean {
    return this.state === 'starting' || this.state === 'recording' || this.state === 'paused';
  }

  /** Stable between changes, for useSyncExternalStore. */
  snapshot: RecorderSnapshot = { state: 'starting', elapsed: 0, levels: this.levels };

  private emit() {
    this.snapshot = { state: this.state, elapsed: this.elapsed(), levels: this.levels };
    this.listeners.forEach((listener) => listener());
  }

  private async open() {
    if (!canRecord()) {
      this.fail(new MicError('unsupported', 'Este navegador no permite grabar audio.'));
      return;
    }
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (error) {
      const problem = micErrorFrom(error);
      if (problem.problem === 'denied') setMicState('denied');
      this.fail(problem);
      return;
    }
    setMicState('granted');
    if (this.discarded) {
      this.release();
      return;
    }
    try {
      const mime = pickMime();
      this.media = mime ? new MediaRecorder(this.stream, { mimeType: mime }) : new MediaRecorder(this.stream);
      this.media.addEventListener('dataavailable', (event: BlobEvent) => {
        if (event.data && event.data.size > 0) this.chunks.push(event.data);
      });
      this.media.start(1000);
    } catch {
      this.release();
      this.fail(new MicError('error', 'Este navegador no pudo empezar a grabar.'));
      return;
    }
    this.listenLevels();
    this.state = 'recording';
    this.resumedAt = Date.now();
    this.ticker = setInterval(() => this.tick(), reducedMotion() ? 1000 : 250);
    this.emit();
  }

  private fail(problem: MicError) {
    this.problem = problem;
    this.state = 'error';
    this.emit();
  }

  private listenLevels() {
    const Context = (globalThis.AudioContext ?? (globalThis as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext) as
      | typeof AudioContext
      | undefined;
    if (!Context || !this.stream) return;
    try {
      this.audioContext = new Context();
      const source = this.audioContext.createMediaStreamSource(this.stream);
      this.analyser = this.audioContext.createAnalyser();
      this.analyser.fftSize = 512;
      source.connect(this.analyser);
    } catch {
      this.audioContext = null;
      this.analyser = null;
    }
  }

  private level(): number {
    if (!this.analyser) return 0;
    const data = new Uint8Array(this.analyser.fftSize);
    this.analyser.getByteTimeDomainData(data);
    let sum = 0;
    for (const value of data) sum += ((value - 128) / 128) ** 2;
    return Math.min(1, Math.sqrt(sum / data.length) * 4);
  }

  private tick() {
    if (this.state === 'recording') {
      const level = this.level();
      this.history.push(level);
      this.levels = [...this.levels.slice(1), level];
      if (this.elapsed() >= MAX_SECONDS) {
        void this.stop().then((audio) => {
          this.autoStopped = audio;
          this.emit();
        });
        return;
      }
    }
    this.emit();
  }

  pause() {
    if (this.state !== 'recording' || !this.media || typeof this.media.pause !== 'function') return;
    this.media.pause();
    this.accumulated += Date.now() - this.resumedAt;
    this.resumedAt = 0;
    this.state = 'paused';
    this.emit();
  }

  resume() {
    if (this.state !== 'paused' || !this.media) return;
    this.media.resume();
    this.resumedAt = Date.now();
    this.state = 'recording';
    this.emit();
  }

  get canPause(): boolean {
    return Boolean(this.media && typeof this.media.pause === 'function');
  }

  /** Ends the recording and returns the audio (null if nothing was recorded or it failed). */
  stop(): Promise<RecordedAudio | null> {
    this.result ??= this.finish();
    return this.result;
  }

  /** Stops and throws the audio away. Returns it anyway, for «Recuperar». */
  discard(): Promise<RecordedAudio | null> {
    this.discarded = true;
    return this.stop();
  }

  private async finish(): Promise<RecordedAudio | null> {
    await this.ready;
    if (this.state === 'recording') this.accumulated += Date.now() - this.resumedAt;
    this.resumedAt = 0;
    const media = this.media;
    if (!media || this.state === 'error') {
      this.release();
      if (this.state !== 'error') this.state = 'stopped';
      this.emit();
      return null;
    }
    const mime = media.mimeType || pickMime() || 'audio/webm';
    if (media.state !== 'inactive') {
      await new Promise<void>((resolve) => {
        media.addEventListener('stop', () => resolve(), { once: true });
        try {
          media.stop();
        } catch {
          resolve();
        }
      });
    }
    this.release();
    this.state = 'stopped';
    this.emit();
    const duration = this.accumulated / 1000;
    if (!this.chunks.length) return null;
    return { blob: new Blob(this.chunks, { type: mime }), mime, duration, levels: toBars(this.history) };
  }

  private release() {
    if (this.ticker) clearInterval(this.ticker);
    this.ticker = null;
    this.stream?.getTracks().forEach((track) => track.stop());
    this.stream = null;
    void this.audioContext?.close().catch(() => undefined);
    this.audioContext = null;
    this.analyser = null;
  }
}

function reducedMotion(): boolean {
  return typeof window !== 'undefined' && typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

export interface RecorderSnapshot {
  state: RecorderState;
  elapsed: number;
  levels: number[];
}

const NO_RECORDING: RecorderSnapshot = { state: 'stopped', elapsed: 0, levels: [] };

/** Re-renders on every recorder change (state, time, wave). */
export function useRecorder(recorder: Recorder | null): RecorderSnapshot {
  const subscribe = useCallback((listener: () => void) => (recorder ? recorder.subscribe(listener) : () => {}), [recorder]);
  return useSyncExternalStore(
    subscribe,
    () => (recorder ? recorder.snapshot : NO_RECORDING),
    () => NO_RECORDING,
  );
}

/** Re-renders only when the recording changes state (not on every tick). */
export function useRecorderStatus(recorder: Recorder | null): string {
  const subscribe = useCallback((listener: () => void) => (recorder ? recorder.subscribe(listener) : () => {}), [recorder]);
  return useSyncExternalStore(
    subscribe,
    () => (recorder ? `${recorder.state}${recorder.autoStopped ? ':auto' : ''}` : 'none'),
    () => 'none',
  );
}
