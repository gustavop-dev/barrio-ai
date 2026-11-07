// Charts of Resultados, plain HTML and CSS (no chart dependency): a card with an ⓘ definition, a bar list,
// the 60/40 modality split and the impressions per post with the median line.
import { useId, useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { barRows, impressionsChart, MODALITY_SPLIT_MISSING, modalitySplit } from '../../../../compartido/src/logic/resultados';
import type { Resultados } from '../../api/types';
import { IconInfo } from '../../components/icons';
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
  return (
    <ul className="funnel-steps res-bars" aria-label={label}>
      {barRows(items).map((item) => (
        <li key={item.key} className="funnel-step">
          <div className="funnel-head">
            <span>{item.label}</span>
            <span>
              {item.text}
              {item.value === null ? <span className="vh">, sin dato</span> : null}
            </span>
          </div>
          <div className="funnel-track" aria-hidden="true">
            <div className="funnel-bar" style={{ width: `${item.width}%`, background: color }} />
          </div>
        </li>
      ))}
    </ul>
  );
}

/** Stacked Startups / ProjectApp bar against the 60/40 target, marked with a line. */
export function ModalitySplit({ data }: { data: NegocioOn['modalidades'] }) {
  const view = modalitySplit(data);
  const { startups, projectapp, target } = view;
  const pendingNote = view.pendingNote ? <p className="res-muted">{view.pendingNote}</p> : null;
  if (startups === null || projectapp === null) {
    return (
      <>
        <p className="res-muted">{MODALITY_SPLIT_MISSING}</p>
        {pendingNote}
      </>
    );
  }
  return (
    <>
      <div className="res-split" role="img" aria-label={view.spoken}>
        <div className="res-split-bar">
          {startups > 0 ? <span className="res-split-a" style={{ width: `${startups}%` }} /> : null}
          {projectapp > 0 ? <span className="res-split-b" style={{ width: `${projectapp}%` }} /> : null}
        </div>
        <span className="res-split-target" style={{ left: `${target}%` }} />
      </div>
      <div className="res-legend" aria-hidden="true">
        <span className="res-legend-item">
          <span className="res-dot a" />
          {view.legendStartups}
        </span>
        <span className="res-legend-item">
          <span className="res-dot b" />
          {view.legendProjectapp}
        </span>
        <span className="res-legend-target">{view.legendTarget}</span>
      </div>
      {pendingNote}
    </>
  );
}

type Chart = Resultados['contenido']['chart'];

/** Impressions per post over the period with the median of the 4 previous weeks; each bar opens the piece. */
export function ImpressionsChart({ chart, cut }: { chart: Chart; cut: '7d' | '24h' | null }) {
  const { title, reference, referenceHeight, bars, anyFallback, caption } = impressionsChart(chart, cut);

  return (
    <ChartCard title={title} definition={chart.definition}>
      {bars.length ? (
        <>
          <div className="res-chart">
            {bars.map((bar) => (
              <Link key={bar.key} to={`/calendario/pieza/${encodeURIComponent(bar.pieceId)}`} className="res-bar-slot" aria-label={bar.label} title={bar.label}>
                <span
                  className={['res-bar', bar.above ? 'above' : 'below', bar.fallback ? 'fallback' : '', bar.empty ? 'empty' : ''].filter(Boolean).join(' ')}
                  style={{ height: `${bar.height}%` }}
                />
              </Link>
            ))}
            {referenceHeight !== null ? <span className="res-median" aria-hidden="true" style={{ bottom: `${referenceHeight}%` }} /> : null}
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
          <p className="res-muted">{caption}</p>
        </>
      ) : (
        <p className="res-muted">Sin posts publicados en el periodo.</p>
      )}
    </ChartCard>
  );
}
