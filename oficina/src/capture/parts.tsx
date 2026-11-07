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

const LOCALE = 'es-CO';

function sameDay(a: Date, b: Date): boolean {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

/** «3 nov», «10 nov 2026»: the short day of the designs (es-CO writes «3 de nov.»). */
export function shortDay(date: Date, withYear = false): string {
  const options: Intl.DateTimeFormatOptions = { day: 'numeric', month: 'short' };
  if (withYear) options.year = 'numeric';
  return date.toLocaleDateString(LOCALE, options).replace(/\./g, '').replace(/ de /g, ' ');
}

/** «Hoy, 10:40», «Ayer, 19:05», «3 nov» (and the year when it is not this one). */
export function whenLabel(iso: string | null | undefined, now: Date = new Date()): string {
  if (!iso) return '—';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '—';
  const time = date.toLocaleTimeString(LOCALE, { hour: '2-digit', minute: '2-digit', hour12: false });
  if (sameDay(date, now)) return `Hoy, ${time}`;
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  if (sameDay(date, yesterday)) return `Ayer, ${time}`;
  return shortDay(date, date.getFullYear() !== now.getFullYear());
}

/** «1 foto», «3 fotos». */
export function fotosLabel(count: number): string {
  return `${count} ${count === 1 ? 'foto' : 'fotos'}`;
}
