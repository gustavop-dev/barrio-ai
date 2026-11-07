import { useId, useState } from 'react';
import type { Kpi, KpiPoint } from '../../api/types';
import { formatNumber, formatPct, formatUsd } from '../../lib/format';
import { IconInfo } from '../icons';

export type KpiUnit = 'number' | 'percent' | 'usd';

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

function formatValue(value: number, unit: KpiUnit, format?: (value: number) => string): string {
  if (format) return format(value);
  if (unit === 'percent') return formatPct(value);
  if (unit === 'usd') return formatUsd(value);
  return formatNumber(value);
}

type DeltaView = { text: string; spoken: string; tone: 'good' | 'bad' | 'flat' };

/** The variation line, per the contract: grey «sin comparación» unless `comparable`. */
export function kpiDelta(kpi: Kpi, unit: KpiUnit = 'number', better: 'up' | 'down' | 'none' = 'up', asPercent = false): DeltaView {
  if (!kpi.comparable || kpi.delta === null || kpi.delta === undefined) {
    return { text: 'sin comparación', spoken: 'Sin comparación con el periodo anterior', tone: 'flat' };
  }
  const delta = asPercent && kpi.delta_pct !== null && kpi.delta_pct !== undefined ? kpi.delta_pct : kpi.delta;
  if (delta === 0) return { text: '= igual que antes', spoken: 'Igual que en el periodo anterior', tone: 'flat' };
  const up = delta > 0;
  const magnitude = Math.abs(delta);
  let amount: string;
  if (asPercent && kpi.delta_pct !== null && kpi.delta_pct !== undefined) amount = formatPct(magnitude);
  else if (unit === 'percent') amount = `${formatNumber(magnitude)} pts`;
  else if (unit === 'usd') amount = formatUsd(magnitude);
  else amount = formatNumber(magnitude);
  const good = better === 'none' ? null : better === 'up' ? up : !up;
  return {
    text: up ? `▲ ${amount}` : `▼ −${amount}`,
    spoken: `${up ? 'Sube' : 'Baja'} ${amount} frente al periodo anterior`,
    tone: good === null ? 'flat' : good ? 'good' : 'bad',
  };
}

/** Points of the minichart in a 100×30 box; null values are skipped. */
export function sparklinePoints(series: KpiPoint[] | null | undefined): string | null {
  const values = (series ?? []).map((p, i) => ({ i, v: p.value })).filter((p): p is { i: number; v: number } => typeof p.v === 'number' && Number.isFinite(p.v));
  if (!series || values.length < 2) return null;
  const min = Math.min(...values.map((p) => p.v));
  const max = Math.max(...values.map((p) => p.v));
  const last = Math.max(1, series.length - 1);
  return values
    .map(({ i, v }) => {
      const x = (i / last) * 100;
      const y = max === min ? 16 : 28 - ((v - min) / (max - min)) * 24;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(' ');
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
