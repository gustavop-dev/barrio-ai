import type { ReactNode } from 'react';

/** The five tones of the vocabularies in DISENO-VISTAS.md. */
export type Tone = 'ok' | 'warn' | 'bad' | 'muted' | 'info';

/**
 * Status chip, UPPERCASE (etiqueta).
 * - ok: 0ff1ce-hondo on 0ff1ce-claro (5.3:1)
 * - info: #3d5a7a on #e4ecf3 (6.0:1)
 * - warn: tinta on post-it (11.5:1)
 * - bad: alerta outline on superficie (5.6:1); `solid` for white on alerta (CRÍTICO, DETENIDA)
 * - muted: tinta-suave on superficie with a linea border
 * - ink: papel on tinta (HOY, OPORTUNIDAD)
 */
export interface BadgeProps {
  tone?: Tone | 'ink';
  solid?: boolean;
  /** Small status dot before the text, in the tone colour. */
  dot?: boolean;
  className?: string;
  title?: string;
  children: ReactNode;
}

export function Badge({ tone = 'muted', solid = false, dot = false, className, title, children }: BadgeProps) {
  return (
    <span className={['badge', tone, solid ? 'solid' : '', className ?? ''].filter(Boolean).join(' ')} title={title}>
      {dot ? <span className="badge-dot" aria-hidden="true" /> : null}
      {children}
    </span>
  );
}
