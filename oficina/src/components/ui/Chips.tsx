import type { ButtonHTMLAttributes, ReactNode } from 'react';

export interface FilterChipProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'children'> {
  pressed: boolean;
  /** Shown as «Encaja · 5». null/undefined hides it. */
  count?: number | null;
  /** solid: tinta when pressed (funnel, filters). layer: colour dot, outlined when pressed (calendar layers). */
  variant?: 'solid' | 'layer';
  /** Dot colour for the layer variant, e.g. 'var(--capa-red)'. */
  color?: string;
  /** Layer not available yet (phase 1): dashed and disabled, with this text after the name. */
  unavailableLabel?: string;
  children: ReactNode;
}

/** Toggle chip with an optional count. 44px tall. */
export function FilterChip({ pressed, count, variant = 'solid', color, unavailableLabel, className, children, disabled, ...rest }: FilterChipProps) {
  const unavailable = Boolean(unavailableLabel);
  return (
    <button
      type="button"
      aria-pressed={pressed}
      disabled={disabled || unavailable}
      className={['chip-filter', variant, unavailable ? 'unavailable' : '', className ?? ''].filter(Boolean).join(' ')}
      {...rest}
    >
      {variant === 'layer' ? <span className="chip-dot" aria-hidden="true" style={{ background: color }} /> : null}
      <span>
        {children}
        {count !== undefined && count !== null ? ` · ${count}` : null}
        {unavailable ? ` · ${unavailableLabel}` : null}
      </span>
    </button>
  );
}

export interface ChipStripProps {
  /** Accessible name of the group («Filtrar por etapa», «Capas»). */
  label: string;
  /** Horizontal scroll on one line (mobile strips) instead of wrapping. */
  scroll?: boolean;
  className?: string;
  children: ReactNode;
}

export function ChipStrip({ label, scroll = true, className, children }: ChipStripProps) {
  return (
    <div role="group" aria-label={label} className={['chip-strip', scroll ? 'scroll' : 'wrap', className ?? ''].filter(Boolean).join(' ')}>
      {children}
    </div>
  );
}

export interface LabelChipProps {
  /** info: role of the barrio (COMPRADOR); muted: modality or pillar (PROJECTAPP); ok and warn when needed. */
  tone?: 'info' | 'muted' | 'ok' | 'warn';
  children: ReactNode;
}

/** Small UPPERCASE label: role, modality or pillar. Not interactive. */
export function LabelChip({ tone = 'info', children }: LabelChipProps) {
  return <span className={`chip-label ${tone}`}>{children}</span>;
}
