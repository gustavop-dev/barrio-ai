// Small pieces shared by the capture button, the capture sheet and the Galería.
import { useCallback, useEffect, useRef, useState } from 'react';
import { toBars, WAVE_BARS } from './recorder';

/** The wave of Captura.dc.html: 24 bars from 4 to 32 px. `hondo` in the sheet, `suave` while holding. */
export function Wave({ levels, tone = 'hondo' }: { levels: number[]; tone?: 'hondo' | 'suave' }) {
  const bars = toBars(levels, WAVE_BARS);
  return (
    <div className={`cap-wave ${tone}`} aria-hidden="true">
      {bars.map((level, index) => (
        <span key={index} style={{ height: `${4 + Math.round(Math.min(1, Math.max(0, level)) * 28)}px` }} />
      ))}
    </div>
  );
}

function objectUrl(blob: Blob): string | null {
  return typeof URL.createObjectURL === 'function' ? URL.createObjectURL(blob) : null;
}

/**
 * Plays an audio (a same-origin URL or a recorded Blob). The element is created on the first tap, so a
 * Blob gets its object URL only when listened to; it is paused and released when the component goes.
 */
export function useAudioPlayback(source: string | Blob | null) {
  const audio = useRef<HTMLAudioElement | null>(null);
  const created = useRef<string | null>(null);
  const [playing, setPlaying] = useState(false);

  useEffect(
    () => () => {
      audio.current?.pause();
      audio.current = null;
      if (created.current) URL.revokeObjectURL(created.current);
      created.current = null;
    },
    [],
  );

  const toggle = useCallback(() => {
    if (!source) return;
    let element = audio.current;
    if (!element) {
      const src = typeof source === 'string' ? source : objectUrl(source);
      if (!src) return;
      if (typeof source !== 'string') created.current = src;
      element = new Audio(src);
      element.addEventListener('play', () => setPlaying(true));
      element.addEventListener('pause', () => setPlaying(false));
      element.addEventListener('ended', () => setPlaying(false));
      audio.current = element;
    }
    if (element.paused) {
      try {
        const started = element.play() as Promise<void> | undefined;
        started?.catch(() => setPlaying(false));
      } catch {
        setPlaying(false);
      }
    } else {
      element.pause();
    }
  }, [source]);

  return { playing, toggle };
}

/** Thumbnail of a picked File; its object URL lives exactly as long as the image. */
export function FileThumb({ file, alt }: { file: File; alt: string }) {
  const image = useRef<HTMLImageElement>(null);
  useEffect(() => {
    const node = image.current;
    if (!node) return;
    const url = objectUrl(file);
    if (!url) return;
    node.src = url;
    return () => URL.revokeObjectURL(url);
  }, [file]);
  return <img ref={image} alt={alt} />;
}

// Pure labels shared with the native app (compartido/src/logic/capturas.ts).
export { fotosLabel, shortDay, whenLabel } from '../../../compartido/src/logic/capturas';
