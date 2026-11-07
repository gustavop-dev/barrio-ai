// Audio helpers of the capture, shared by the PWA recorder (MediaRecorder) and the native one (expo-audio).

export const WAVE_BARS = 24;
/** The contract caps `audio_duration_s` at 1800: the recording stops by itself at 30 minutes. */
export const MAX_SECONDS = 1800;

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
