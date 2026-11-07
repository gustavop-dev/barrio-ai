import type { ReactNode } from 'react';
import { formatNumber } from '../../lib/format';

export interface FunnelStep {
  key?: string;
  label: string;
  /** null is «sin dato» (shown as —), never 0. */
  value: number | null;
}

export interface FunnelProps {
  steps: FunnelStep[];
  /** «3 · 75 %»: conversion from the previous step. Off for plain distributions (roles). */
  showConversion?: boolean;
  /** Bar colour: 0ff1ce-hondo by default; 'var(--color-azul-sprite)' for distributions. */
  color?: string;
  /** Under the bars, e.g. «Cerrada sin acuerdo: 1» or the discarded contacts. */
  aside?: ReactNode;
}

/** Horizontal bars with their count and the conversion between steps. Widths are relative to the largest step. */
export function Funnel({ steps, showConversion = true, color, aside }: FunnelProps) {
  const max = Math.max(0, ...steps.map((s) => s.value ?? 0));
  return (
    <div className="funnel">
      <ol className="funnel-steps">
        {steps.map((step, index) => {
          const previous = index > 0 ? steps[index - 1]!.value : null;
          const conversion =
            showConversion && index > 0 && step.value !== null && previous !== null && previous > 0 ? Math.round((step.value / previous) * 100) : null;
          const width = step.value && max > 0 ? Math.max(2, (step.value / max) * 100) : 2;
          const valueText = step.value === null ? '—' : formatNumber(step.value);
          return (
            <li key={step.key ?? step.label} className="funnel-step">
              <div className="funnel-head">
                <span>{step.label}</span>
                <span>
                  {valueText}
                  {conversion !== null ? ` · ${conversion} %` : null}
                </span>
              </div>
              <div className="funnel-track" role="img" aria-label={`${step.label}: ${step.value === null ? 'sin dato' : valueText}${conversion !== null ? `, ${conversion} % del paso anterior` : ''}`}>
                <div className="funnel-bar" style={{ width: `${step.value === null ? 0 : width}%`, background: color }} />
              </div>
            </li>
          );
        })}
      </ol>
      {aside ? <p className="funnel-aside">{aside}</p> : null}
    </div>
  );
}
