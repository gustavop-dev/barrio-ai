import type { ReactNode } from 'react';
import { funnelRows, type FunnelStepInput } from '../../../../compartido/src/logic/resultados';

/** A step: null is «sin dato» (shown as —), never 0. The bar rules are shared with the native app. */
export type FunnelStep = FunnelStepInput;

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
  return (
    <div className="funnel">
      <ol className="funnel-steps">
        {funnelRows(steps, showConversion).map((row) => (
          <li key={row.key} className="funnel-step">
            <div className="funnel-head">
              <span>{row.label}</span>
              <span>
                {row.valueText}
                {row.conversion !== null ? ` · ${row.conversion} %` : null}
              </span>
            </div>
            <div className="funnel-track" role="img" aria-label={row.spoken}>
              <div className="funnel-bar" style={{ width: `${row.width}%`, background: color }} />
            </div>
          </li>
        ))}
      </ol>
      {aside ? <p className="funnel-aside">{aside}</p> : null}
    </div>
  );
}
