import { useId, useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import type { CalendarLayer } from '../../api/types';
import { AgentPortrait } from './AgentPortrait';
import { Badge, type Tone } from './Badge';
import { ExternalLink } from './ExternalLink';

export const LAYER_COLOR: Record<CalendarLayer, string> = {
  tuyo: 'var(--capa-tuyo)',
  publicaciones: 'var(--capa-publicaciones)',
  red: 'var(--capa-red)',
  conversaciones: 'var(--capa-conversaciones)',
  sistema: 'var(--capa-sistema)',
};

export const LAYER_LABEL: Record<CalendarLayer, string> = {
  tuyo: 'Tuyo',
  publicaciones: 'Publicaciones',
  red: 'Red',
  conversaciones: 'Conversaciones',
  sistema: 'Sistema',
};

/** List wrapper for TimelineItem rows. */
export function Timeline({ children, label }: { children: ReactNode; label?: string }) {
  return (
    <ul className="tl" aria-label={label}>
      {children}
    </ul>
  );
}

export interface TimelineItemProps {
  /** Calendar layer: colours the dot. */
  layer?: CalendarLayer;
  /** Dot colour when there is no layer. */
  color?: string;
  /** «09:00», or null for all-day items. */
  time?: string | null;
  /** The main sentence («Comentaste en el post de Ana»). */
  title: ReactNode;
  /** One line under it, tinta-suave. */
  sub?: ReactNode;
  /** Shown only when the state is not a normal success («Incierta», «Vetada por ti»). */
  badge?: { label: string; tone: Tone } | null;
  /** Role that did it: small portrait before the title. */
  agent?: string | null;
  /** In-app destination: renders «Abrir» (or `linkLabel`). */
  to?: string | null;
  linkLabel?: string;
  /** LinkedIn URL: renders «Ver en LinkedIn ↗» (https only). */
  externalUrl?: string | null;
  externalLabel?: string;
  /** Expandable content (post excerpt, full comment, «Por qué»). */
  children?: ReactNode;
  expandLabel?: string;
}

/** Timeline row: dot, time, sentence, optional badge, expandable content and link. */
export function TimelineItem({
  layer,
  color,
  time,
  title,
  sub,
  badge,
  agent,
  to,
  linkLabel = 'Abrir',
  externalUrl,
  externalLabel = 'Ver en LinkedIn',
  children,
  expandLabel = 'Ver más',
}: TimelineItemProps) {
  const [open, setOpen] = useState(false);
  const contentId = useId();
  const dot = color ?? (layer ? LAYER_COLOR[layer] : 'var(--color-linea)');
  return (
    <li className="tl-item">
      <span className="tl-dot" aria-hidden="true" style={{ background: dot }} />
      <span className="tl-time">{time || ''}</span>
      <div className="tl-body">
        <p className="tl-title">
          {agent ? <AgentPortrait role={agent} size="sm" /> : null}
          <span>{title}</span>
        </p>
        {sub ? <p className="tl-sub">{sub}</p> : null}
        {badge ? (
          <span className="tl-badge">
            <Badge tone={badge.tone}>{badge.label}</Badge>
          </span>
        ) : null}
        {children ? (
          <>
            <button type="button" className="tl-toggle" aria-expanded={open} aria-controls={contentId} onClick={() => setOpen((v) => !v)}>
              {open ? 'Ver menos' : expandLabel}
            </button>
            {open ? (
              <div id={contentId} className="tl-content">
                {children}
              </div>
            ) : null}
          </>
        ) : null}
        {to || externalUrl ? (
          <span className="tl-links">
            {to ? (
              <Link to={to} className="tl-link">
                {linkLabel}
              </Link>
            ) : null}
            <ExternalLink href={externalUrl} className="tl-link">
              {externalLabel}
            </ExternalLink>
          </span>
        ) : null}
      </div>
    </li>
  );
}
