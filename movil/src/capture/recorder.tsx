// The one audio recorder of the app (expo-audio), shared by the capture button (press and hold)
// and the capture sheet (a locked recording carries on there). Nothing is uploaded while recording:
// the file stays on the phone until «Guardar y enviar al equipo».
//
// Two contexts: the controls and phase (change rarely) and the live meter (every LEVEL_INTERVAL_MS),
// so only the wave and the timer re-render while recording.
import { MAX_SECONDS, toBars, WAVE_BARS } from '@compartido/logic/audio';
import {
  getRecordingPermissionsAsync,
  RecordingPresets,
  requestRecordingPermissionsAsync,
  setAudioModeAsync,
  useAudioRecorder,
  useAudioRecorderState,
} from 'expo-audio';
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import type { RecordedAudio } from './types';

/** How often the meter and the timer refresh while recording (ms). */
export const LEVEL_INTERVAL_MS = 100;
const IDLE_INTERVAL_MS = 1000;
/** Metering arrives in dBFS (-160…0): this floor maps to an empty bar. */
const SILENCE_DB = -60;
const MIME = 'audio/mp4';

/** granted; explain (ask, with our sentence first); denied (only the system settings can fix it). */
export type MicState = 'granted' | 'explain' | 'denied';

export type RecorderPhase = 'idle' | 'starting' | 'recording' | 'paused';

export interface RecorderApi {
  phase: RecorderPhase;
  /** Set when starting failed (another app holds the microphone, for example). */
  failed: boolean;
  /** The recording stopped by itself at MAX_SECONDS: the finished audio. */
  autoStopped: RecordedAudio | null;
  /** Current permission, without prompting. */
  micState: () => Promise<MicState>;
  /** The system prompt (call it after explaining why). */
  requestMic: () => Promise<MicState>;
  /** Starts recording; false when it could not (permission or a device error). */
  start: () => Promise<boolean>;
  pause: () => void;
  resume: () => void;
  /** Ends the recording and hands back the audio (null if nothing was recorded). */
  stop: () => Promise<RecordedAudio | null>;
  /** Ends it without using it; the audio comes back for «Recuperar». */
  discard: () => Promise<RecordedAudio | null>;
  /** Forgets an auto-stopped recording once the sheet has taken it. */
  clearAutoStopped: () => void;
}

export interface RecorderLive {
  /** Seconds recorded. */
  elapsed: number;
  /** The last WAVE_BARS levels (0–1), newest last. */
  levels: number[];
}

const EMPTY_LEVELS = Array.from({ length: WAVE_BARS }, () => 0);

const RecorderContext = createContext<RecorderApi | null>(null);
const LiveContext = createContext<RecorderLive>({ elapsed: 0, levels: EMPTY_LEVELS });

export function useRecorder(): RecorderApi {
  const value = useContext(RecorderContext);
  if (!value) throw new Error('useRecorder() fuera de <RecorderProvider>');
  return value;
}

export function useRecorderLive(): RecorderLive {
  return useContext(LiveContext);
}

/** dBFS → 0–1 for the wave. */
export function levelOf(db: number | undefined): number {
  if (typeof db !== 'number' || !Number.isFinite(db)) return 0;
  return Math.min(1, Math.max(0, (db - SILENCE_DB) / -SILENCE_DB));
}

function toMicState(response: { granted: boolean; canAskAgain: boolean }): MicState {
  if (response.granted) return 'granted';
  return response.canAskAgain ? 'explain' : 'denied';
}

export function RecorderProvider({ children }: { children: ReactNode }) {
  const recorder = useAudioRecorder({ ...RecordingPresets.HIGH_QUALITY, isMeteringEnabled: true });
  const [phase, setPhase] = useState<RecorderPhase>('idle');
  // Poll fast only while there is a recording.
  const status = useAudioRecorderState(recorder, phase === 'idle' ? IDLE_INTERVAL_MS : LEVEL_INTERVAL_MS);
  const [failed, setFailed] = useState(false);
  const [autoStopped, setAutoStopped] = useState<RecordedAudio | null>(null);
  const [live, setLive] = useState<RecorderLive>({ elapsed: 0, levels: EMPTY_LEVELS });
  const history = useRef<number[]>([]);
  const elapsed = useRef(0);
  const phaseRef = useRef<RecorderPhase>('idle');

  const setPhaseBoth = useCallback((next: RecorderPhase) => {
    phaseRef.current = next;
    setPhase(next);
  }, []);

  // The meter: one level per tick while recording.
  useEffect(() => {
    if (phase !== 'recording' || !status.isRecording) return;
    history.current.push(levelOf(status.metering));
    const recent = history.current.slice(-WAVE_BARS);
    elapsed.current = status.durationMillis / 1000;
    setLive({ elapsed: elapsed.current, levels: toBars(recent, WAVE_BARS) });
  }, [phase, status.isRecording, status.durationMillis, status.metering]);

  const finish = useCallback(async (): Promise<RecordedAudio | null> => {
    if (phaseRef.current === 'idle') return null;
    const duration = Math.max(elapsed.current, recorder.currentTime || 0);
    setPhaseBoth('idle');
    try {
      await recorder.stop();
    } catch {
      // Already stopped (or never started): use whatever file there is.
    }
    setAudioModeAsync({ allowsRecording: false }).catch(() => undefined);
    const uri = recorder.uri;
    const levels = toBars(history.current, WAVE_BARS);
    history.current = [];
    elapsed.current = 0;
    setLive({ elapsed: 0, levels: EMPTY_LEVELS });
    return uri ? { uri, mime: MIME, duration, levels } : null;
  }, [recorder, setPhaseBoth]);

  // The contract caps audio at 1800 s: stop by itself, and let the sheet pick the audio up.
  useEffect(() => {
    if (phase === 'recording' && live.elapsed >= MAX_SECONDS) void finish().then(setAutoStopped);
  }, [phase, live.elapsed, finish]);

  const micState = useCallback(async () => toMicState(await getRecordingPermissionsAsync()), []);
  const requestMic = useCallback(async () => toMicState(await requestRecordingPermissionsAsync()), []);

  const start = useCallback(async () => {
    if (phaseRef.current !== 'idle') return true;
    setFailed(false);
    setAutoStopped(null);
    history.current = [];
    setPhaseBoth('starting');
    try {
      if ((await micState()) !== 'granted') {
        setPhaseBoth('idle');
        return false;
      }
      await setAudioModeAsync({ allowsRecording: true, playsInSilentMode: true });
      await recorder.prepareToRecordAsync();
      // Released (or discarded) while the microphone was opening (the ref changes meanwhile).
      if ((phaseRef.current as RecorderPhase) !== 'starting') {
        await recorder.stop().catch(() => undefined);
        return false;
      }
      recorder.record();
      setPhaseBoth('recording');
      return true;
    } catch {
      setPhaseBoth('idle');
      setFailed(true);
      return false;
    }
  }, [micState, recorder, setPhaseBoth]);

  const pause = useCallback(() => {
    if (phaseRef.current !== 'recording') return;
    recorder.pause();
    setPhaseBoth('paused');
  }, [recorder, setPhaseBoth]);

  const resume = useCallback(() => {
    if (phaseRef.current !== 'paused') return;
    recorder.record();
    setPhaseBoth('recording');
  }, [recorder, setPhaseBoth]);

  const stop = useCallback(() => {
    if (phaseRef.current === 'starting') {
      setPhaseBoth('idle');
      return Promise.resolve(null);
    }
    return finish();
  }, [finish, setPhaseBoth]);

  const clearAutoStopped = useCallback(() => setAutoStopped(null), []);

  const api = useMemo<RecorderApi>(
    () => ({ phase, failed, autoStopped, micState, requestMic, start, pause, resume, stop, discard: stop, clearAutoStopped }),
    [phase, failed, autoStopped, micState, requestMic, start, pause, resume, stop, clearAutoStopped],
  );

  return (
    <RecorderContext.Provider value={api}>
      <LiveContext.Provider value={live}>{children}</LiveContext.Provider>
    </RecorderContext.Provider>
  );
}
