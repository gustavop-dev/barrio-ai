// Charts of Resultados, plain HTML and CSS (no chart dependency): a card with an ⓘ definition, a bar list,
// the 60/40 modality split and the impressions per post with the median line.
import { useId, useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import type { Resultados } from '../../api/types';
import { IconInfo } from '../../components/icons';
import { formatNumber } from '../../lib/format';
import { shortDate } from '../personas/labels';
import type { NegocioOn } from './types';

/** An ⓘ toggle that shows the definition (and formula) of a chart or a compact stat. */
export function InfoToggle({ label, definition, formula }: { label: string; definition?: ReactNode; formula?: string | null }) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  if (!definition && !formula) return null;
  return (
    <>
      <button
        type="button"
        className="kpi-info res-info"
        aria-label={`Definición de ${label}`}
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((value) => !value)}
        onKeyDown={(event) => {
          if (event.key === 'Escape') setOpen(false);
        }}
      >
        <IconInfo size={16} />
      </button>
      {open ? (
        <div id={panelId} className="kpi-definition res-definition">
          {definition ? <div>{definition}</div> : null}
          {formula ? <p>Fórmula: {formula}</p> : null}
        </div>
      ) : null}
    </>
  );
}

/** A superficie card with an UPPERCASE title, an optional ⓘ and its content. */
export function ChartCard({ title, definition, formula, children, className }: { title: string; definition?: ReactNode; formula?: string | null; children: ReactNode; className?: string }) {
  return (
    <div className={['res-card', className ?? ''].filter(Boolean).join(' ')}>
      <div className="res-card-head">
        <h3 className="res-card-title">{title}</h3>
        <InfoToggle label={title} definition={definition} formula={formula} />
      </div>
      {children}
    </div>
  );
}

export interface BarItem {
  key: string;
  label: ReactNode;
  /** null is «sin dato» (a dash), never 0. */
  value: number | null;
  /** Text on the right; defaults to the number. */
  display?: string;
}

/** Horizontal bars relative to the largest value, like the Funnel but with any value format. */
export function BarList({ items, color, label }: { items: BarItem[]; color?: string; label: string }) {
  const max = Math.max(0, ...items.map((item) => item.value ?? 0));
  return (
    <ul className="funnel-steps res-bars" aria-label={label}>
      {items.map((item) => {
        const text = item.value === null ? '—' : (item.display ?? formatNumber(item.value));
        const width = item.value && max > 0 ? Math.max(2, (item.value / max) * 100) : item.value === null ? 0 : 2;
        return (
          <li key={item.key} className="funnel-step">
            <div className="funnel-head">
              <span>{item.label}</span>
              <span>
                {text}
                {item.value === null ? <span className="vh">, sin dato</span> : null}
              </span>
            </div>
            <div className="funnel-track" aria-hidden="true">
              <div className="funnel-bar" style={{ width: `${width}%`, background: color }} />
            </div>
          </li>
        );
      })}
    </ul>
  );
}

/** Stacked Startups / ProjectApp bar against the 60/40 target, marked with a line. */
export function ModalitySplit({ data }: { data: NegocioOn['modalidades'] }) {
  const startups = data.pct.personal_startups ?? null;
  const projectapp = data.pct.projectapp ?? null;
  const target = data.objetivo.personal_startups ?? 60;
  const pending = data.counts.por_clasificar ?? 0;
  const pendingNote =
    pending > 0 ? (
      <p className="res-muted">
        {pending} {pending === 1 ? 'oportunidad por clasificar no cuenta' : 'oportunidades por clasificar no cuentan'} en el reparto.
      </p>
    ) : null;
  if (startups === null || projectapp === null) {
    return (
      <>
        <p className="res-muted">Sin dato: aún no hay oportunidades con modalidad Startups o ProjectApp.</p>
        {pendingNote}
      </>
    );
  }
  const spoken = `Startups ${formatNumber(startups, 0)} %, ProjectApp ${formatNumber(projectapp, 0)} %, objetivo ${target}/${100 - target}`;
  return (
    <>
      <div className="res-split" role="img" aria-label={spoken}>
        <div className="res-split-bar">
          {startups > 0 ? <span className="res-split-a" style={{ width: `${startups}%` }} /> : null}
          {projectapp > 0 ? <span className="res-split-b" style={{ width: `${projectapp}%` }} /> : null}
        </div>
        <span className="res-split-target" style={{ left: `${target}%` }} />
      </div>
      <div className="res-legend" aria-hidden="true">
        <span className="res-legend-item">
          <span className="res-dot a" />
          Startups {formatNumber(startups, 0)} % · {data.counts.personal_startups ?? 0}
        </span>
        <span className="res-legend-item">
          <span className="res-dot b" />
          ProjectApp {formatNumber(projectapp, 0)} % · {data.counts.projectapp ?? 0}
        </span>
        <span className="res-legend-target">
          Objetivo {target}/{100 - target}
        </span>
      </div>
      {pendingNote}
    </>
  );
}

type Chart = Resultados['contenido']['chart'];

/** Impressions per post over the period with the median of the 4 previous weeks; each bar opens the piece. */
export function ImpressionsChart({ chart, cut }: { chart: Chart; cut: '7d' | '24h' | null }) {
  const bars = chart.bars ?? [];
  const reference = (cut ? chart.median_previous_4_weeks?.[cut] : chart.median_previous_4_weeks?.['7d']) ?? null;
  const max = Math.max(1, reference ?? 0, ...bars.map((bar) => bar.impressions ?? 0)) * 1.08;
  const title = cut === '24h' ? 'Impresiones por post a las 24 h' : 'Impresiones por post a los 7 días';
  const anyFallback = bars.some((bar) => bar.fallback);

  return (
    <ChartCard title={title} definition={chart.definition}>
      {bars.length ? (
        <>
          <div className="res-chart">
            {bars.map((bar, index) => {
              const value = bar.impressions;
              const height = value === null ? 0 : Math.max(2, (value / max) * 100);
              const above = reference === null || (value ?? 0) >= reference;
              const label = `Post ${index + 1}, ${shortDate(bar.date)}: ${value === null ? 'sin dato' : `${formatNumber(value)} impresiones`}${bar.fallback ? ' a las 24 h' : ''}`;
              return (
                <Link
                  key={`${bar.piece_id}-${index}`}
                  to={`/calendario/pieza/${encodeURIComponent(bar.piece_id)}`}
                  className="res-bar-slot"
                  aria-label={label}
                  title={label}
                >
                  <span className={['res-bar', above ? 'above' : 'below', bar.fallback ? 'fallback' : '', value === null ? 'empty' : ''].filter(Boolean).join(' ')} style={{ height: `${height}%` }} />
                </Link>
              );
            })}
            {reference !== null ? <span className="res-median" aria-hidden="true" style={{ bottom: `${(reference / max) * 100}%` }} /> : null}
          </div>
          <div className="res-legend" aria-hidden="true">
            {reference !== null ? (
              <>
                <span className="res-legend-item">
                  <span className="res-dot a" />
                  Sobre la mediana
                </span>
                <span className="res-legend-item">
                  <span className="res-dot b" />
                  Bajo la mediana
                </span>
              </>
            ) : null}
            {anyFallback ? (
              <span className="res-legend-item">
                <span className="res-dot hatch" />A las 24 h (aún sin 7 días)
              </span>
            ) : null}
          </div>
          <p className="res-muted">
            {reference !== null
              ? `La línea es la mediana de las 4 semanas anteriores (${formatNumber(reference)}). Toca una barra para ver la pieza.`
              : 'Aún no hay mediana de las 4 semanas anteriores. Toca una barra para ver la pieza.'}
          </p>
        </>
      ) : (
        <p className="res-muted">Sin posts publicados en el periodo.</p>
      )}
    </ChartCard>
  );
}
