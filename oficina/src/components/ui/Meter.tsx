export type MeterTone = 'ok' | 'warn' | 'bad';

/** Green below 80 %, amber from 80 %, red at 100 % (or over). */
export function meterTone(value: number, max: number): MeterTone {
  const fraction = max > 0 ? value / max : 0;
  if (fraction >= 1) return 'bad';
  if (fraction >= 0.8) return 'warn';
  return 'ok';
}

export interface MeterProps {
  label: string;
  value: number;
  max: number;
  /** Text on the right; defaults to «6 de 10». Also the aria-valuetext. */
  display?: string;
}

/** Usage against a cap: label, «used de cap» and an 8px bar. */
export function Meter({ label, value, max, display }: MeterProps) {
  const safeValue = Number.isFinite(value) ? value : 0;
  const fraction = max > 0 ? Math.min(1, Math.max(0, safeValue / max)) : 0;
  const tone = meterTone(safeValue, max);
  const text = display ?? `${safeValue} de ${max}`;
  return (
    <div className="meter">
      <div className="meterhead">
        <span>{label}</span>
        <span className="metervalue">{text}</span>
      </div>
      <div
        className={`meterbar ${tone}`}
        role="meter"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={max}
        aria-valuenow={safeValue}
        aria-valuetext={text}
      >
        <span style={{ width: `${fraction * 100}%` }} />
      </div>
    </div>
  );
}
