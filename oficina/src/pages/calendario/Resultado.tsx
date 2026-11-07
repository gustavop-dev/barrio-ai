// «Resultado» of a published piece: the 24 h / 72 h / 7 d cuts and who commented. A missing value is never 0.
import type { PieceCommenter, PieceDetail, PieceSnapshot } from '../../api/types';
import { Badge, ExternalLink, LabelChip, Section } from '../../components/ui';
import { timeAgo } from '../../lib/format';
import {
  commenterRoles,
  CUT_LABEL,
  cutPending as pending,
  engagementValue as engagement,
  metricValue as value,
  pieceUrl,
  publishedAt,
  RESULT_CUTS as CUTS,
  RESULT_METRICS as METRICS,
} from './piece';

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
  const { roles, unclassified } = commenterRoles(commenters);
  return (
    <ul className="pz-chips" aria-label="Quién comentó, por rol">
      {roles.map(({ role, label, count }) => (
        <li key={role}>
          <LabelChip tone="info">
            {label} · {count}
          </LabelChip>
        </li>
      ))}
      {unclassified ? (
        <li>
          <LabelChip tone="muted">Sin clasificar · {unclassified}</LabelChip>
        </li>
      ) : null}
    </ul>
  );
}

export function Resultado({ piece, timeZone, now, desktop }: { piece: PieceDetail; timeZone: string; now: number; desktop: boolean }) {
  const byKind = new Map((piece.snapshots ?? []).map((snapshot) => [snapshot.kind, snapshot]));
  const published = publishedAt(piece);
  const url = pieceUrl(piece);
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
