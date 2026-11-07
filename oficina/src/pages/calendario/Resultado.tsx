// «Resultado» of a published piece: the 24 h / 72 h / 7 d cuts and who commented. A missing value is never 0.
import type { PieceCommenter, PieceDetail, PieceSnapshot } from '../../api/types';
import { Badge, ExternalLink, LabelChip, Section } from '../../components/ui';
import { CONTACT_ROLE_LABEL, formatNumber, formatPct, formatTime, timeAgo } from '../../lib/format';
import { dayOf, longDay } from './dates';
import { CUT_HOURS, CUT_LABEL, publishedAt } from './piece';

const CUTS: PieceSnapshot['kind'][] = ['24h', '72h', '7d'];
const METRICS: { key: 'impressions' | 'reactions' | 'comments' | 'reposts'; label: string }[] = [
  { key: 'impressions', label: 'Impresiones' },
  { key: 'reactions', label: 'Reacciones' },
  { key: 'comments', label: 'Comentarios' },
  { key: 'reposts', label: 'Republicaciones' },
];
const ROLE_ORDER = ['comprador', 'par', 'recomendador', 'divulgador', 'lider', 'aliado'];

const value = (n: number | null | undefined) => (typeof n === 'number' ? formatNumber(n, 0) : '—');
const engagement = (n: number | null | undefined) => (typeof n === 'number' ? formatPct(n) : '—');

/** A cut not read yet: «Aún no · Llega el lunes 9 de noviembre a las 09:00.», or «Sin dato» once its hour passed. */
function pending(kind: PieceSnapshot['kind'], published: string, timeZone: string, now: number): { badge: string; text: string } {
  const due = new Date(new Date(published).getTime() + CUT_HOURS[kind] * 3_600_000);
  if (due.getTime() <= now) return { badge: 'Sin dato', text: 'El corte no se pudo leer a tiempo.' };
  return { badge: 'Aún no', text: `Llega el ${longDay(dayOf(due, timeZone) ?? '')} a las ${formatTime(due.toISOString(), timeZone)}.` };
}

function CutCard({ kind, snapshot, published, timeZone, now }: { kind: PieceSnapshot['kind']; snapshot?: PieceSnapshot; published: string; timeZone: string; now: number }) {
  const title = `A ${CUT_LABEL[kind]}`;
  if (!snapshot) {
    const missing = pending(kind, published, timeZone, now);
    return (
      <div className="card compact pz-cut">
        <div className="pz-cut-head">
          <p className="section-label">{title}</p>
          <Badge tone="muted">{missing.badge}</Badge>
        </div>
        <p className="t-detalle text-suave">{missing.text}</p>
      </div>
    );
  }
  return (
    <div className="card compact pz-cut">
      <div className="pz-cut-head">
        <p className="section-label">{title}</p>
        <p className="t-detalle">Interacción {engagement(snapshot.engagement_pct)}</p>
      </div>
      <dl className="pz-cut-grid">
        {METRICS.map((metric) => (
          <div key={metric.key}>
            <dt>{metric.label}</dt>
            <dd>{value(snapshot[metric.key])}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

/** Desktop: the cuts as a table (rows are cuts, columns the metrics). */
function CutTable({ byKind, published, timeZone, now }: { byKind: Map<string, PieceSnapshot>; published: string; timeZone: string; now: number }) {
  return (
    <table className="pz-table">
      <caption className="vh">Resultado por corte</caption>
      <thead>
        <tr>
          <th scope="col">Corte</th>
          {METRICS.map((metric) => (
            <th key={metric.key} scope="col">
              {metric.label}
            </th>
          ))}
          <th scope="col">Interacción</th>
        </tr>
      </thead>
      <tbody>
        {CUTS.map((kind) => {
          const snapshot = byKind.get(kind);
          const missing = snapshot ? null : pending(kind, published, timeZone, now);
          return (
            <tr key={kind}>
              <th scope="row">A {CUT_LABEL[kind]}</th>
              {snapshot ? (
                <>
                  {METRICS.map((metric) => (
                    <td key={metric.key}>{value(snapshot[metric.key])}</td>
                  ))}
                  <td>{engagement(snapshot.engagement_pct)}</td>
                </>
              ) : (
                <td colSpan={METRICS.length + 1} className="pz-table-pending">
                  <Badge tone="muted">{missing!.badge}</Badge> {missing!.text}
                </td>
              )}
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function Commenters({ commenters }: { commenters: PieceCommenter[] | null | undefined }) {
  if (commenters === null || commenters === undefined) return <p className="t-detalle text-suave">Los comentarios aún no se han leído.</p>;
  if (!commenters.length) return <p className="t-detalle text-suave">Nadie ha comentado todavía.</p>;
  const counts = new Map<string, number>();
  for (const person of commenters) counts.set(person.role ?? '', (counts.get(person.role ?? '') ?? 0) + 1);
  const roles = [...counts.keys()].filter(Boolean).sort((a, b) => {
    const ia = ROLE_ORDER.indexOf(a);
    const ib = ROLE_ORDER.indexOf(b);
    return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
  });
  return (
    <ul className="pz-chips" aria-label="Quién comentó, por rol">
      {roles.map((role) => (
        <li key={role}>
          <LabelChip tone="info">
            {CONTACT_ROLE_LABEL[role] ?? role} · {counts.get(role)}
          </LabelChip>
        </li>
      ))}
      {counts.get('') ? (
        <li>
          <LabelChip tone="muted">Sin clasificar · {counts.get('')}</LabelChip>
        </li>
      ) : null}
    </ul>
  );
}

export function Resultado({ piece, timeZone, now, desktop }: { piece: PieceDetail; timeZone: string; now: number; desktop: boolean }) {
  const byKind = new Map((piece.snapshots ?? []).map((snapshot) => [snapshot.kind, snapshot]));
  const published = publishedAt(piece);
  const url = piece.external_url || piece.metrics?.share_url || piece.action_detail?.execution?.external_url;
  const lastRead = typeof piece.metrics?.impressions === 'number' && !byKind.size ? piece.metrics : null;
  return (
    <Section label="Resultado" id="resultado" intro="Interacción = (reacciones + comentarios + republicaciones) / impresiones.">
      {desktop ? (
        <CutTable byKind={byKind} published={published} timeZone={timeZone} now={now} />
      ) : (
        CUTS.map((kind) => <CutCard key={kind} kind={kind} snapshot={byKind.get(kind)} published={published} timeZone={timeZone} now={now} />)
      )}
      {lastRead ? (
        <p className="t-detalle text-suave">
          Última lectura: {value(lastRead.impressions)} impresiones{lastRead.observed_at ? `, ${timeAgo(lastRead.observed_at, now)}` : ''}.
        </p>
      ) : null}
      <div className="pz-commenters">
        <p className="section-label">Quién comentó</p>
        <Commenters commenters={piece.commenters} />
      </div>
      <ExternalLink href={url}>Ver el post en LinkedIn</ExternalLink>
    </Section>
  );
}
