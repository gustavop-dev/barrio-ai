import { useId, useState } from 'react';
import { formatKpiValue as formatValue, kpiDelta, sparklinePoints, type KpiUnit } from '../../../../compartido/src/logic/resultados';
import type { Kpi } from '../../api/types';
import { IconInfo } from '../icons';

// The KPI rules are shared with the native app (compartido/src/logic/resultados.ts).
export { kpiDelta, sparklinePoints, type KpiUnit };

export interface KpiCardProps {
  label: string;
  /** The KPI object of GET /api/v1/resultados. Missing (undefined) reads as «aún no disponible». */
  kpi: Kpi | null | undefined;
  /** percent: value in percent units and delta in points («▼ −4 pts»). */
  unit?: KpiUnit;
  /** Which direction is good: up (default) paints a rise green; down paints a fall green; none keeps grey. */
  better?: 'up' | 'down' | 'none';
  /** Show the relative change (delta_pct, «▲ 12 %») instead of the absolute one. */
  deltaAsPercent?: boolean;
  /** Draws `series` as a small line when it has two points or more (default true). */
  sparkline?: boolean;
  /** Text when the KPI did not arrive at all. */
  missingText?: string;
  /** Custom value formatter, overrides `unit`. */
  format?: (value: number) => string;
}

/**
 * KPI tile: name with an ⓘ definition, big value, variation and minichart. A null value is
 * «sin dato»: a long dash and `unavailable_reason`, never 0.
 */
export function KpiCard({ label, kpi, unit = 'number', better = 'up', deltaAsPercent = false, sparkline = true, missingText = 'Aún no disponible', format }: KpiCardProps) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const available = kpi !== null && kpi !== undefined && kpi.value !== null && kpi.value !== undefined;
  const reason = kpi ? (kpi.unavailable_reason ?? 'Sin dato en este periodo.') : missingText;
  const delta = available ? kpiDelta(kpi, unit, better, deltaAsPercent) : null;
  const points = available && sparkline ? sparklinePoints(kpi.series) : null;
  const hasDefinition = Boolean(kpi?.definition || kpi?.formula);

  return (
    <div className="kpi">
      <div className="kpi-head">
        <span className="kpi-label">{label}</span>
        {hasDefinition ? (
          <button
            type="button"
            className="kpi-info"
            aria-label={`Definición de ${label}`}
            aria-expanded={open}
            aria-controls={panelId}
            onClick={() => setOpen((v) => !v)}
            onKeyDown={(event) => {
              if (event.key === 'Escape') setOpen(false);
            }}
          >
            <IconInfo size={16} />
          </button>
        ) : null}
      </div>
      {hasDefinition && open ? (
        <div id={panelId} className="kpi-definition">
          {kpi?.definition ? <p>{kpi.definition}</p> : null}
          {kpi?.formula ? <p>Fórmula: {kpi.formula}</p> : null}
        </div>
      ) : null}
      {available ? (
        <>
          <p className="kpi-value">{formatValue(kpi.value as number, unit, format)}</p>
          {delta ? (
            <p className={`kpi-delta ${delta.tone}`}>
              <span aria-hidden="true">{delta.text}</span>
              <span className="vh">{delta.spoken}</span>
            </p>
          ) : null}
          {points ? (
            <svg className="kpi-spark" aria-hidden="true" width="100%" height="28" viewBox="0 0 100 30" preserveAspectRatio="none">
              <polyline points={points} fill="none" stroke="currentColor" strokeWidth="2" vectorEffect="non-scaling-stroke" />
            </svg>
          ) : null}
        </>
      ) : (
        <>
          <p className="kpi-value empty">
            <span aria-hidden="true">—</span>
            <span className="vh">Sin dato</span>
          </p>
          <p className="kpi-reason">{reason}</p>
        </>
      )}
    </div>
  );
}
