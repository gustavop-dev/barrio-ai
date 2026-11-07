import { useQuery } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { Link, useParams } from 'react-router-dom';
import { getPiece } from '../api/endpoints';
import { keys } from '../api/queryClient';
import type { Assessment, Claim, PieceDetail, StageUsage, Variant } from '../api/types';
import { VetoPiece } from '../components/VetoPiece';
import { Badge, Empty, ErrorNote, ExternalLink, Loading, PageHeader } from '../components/ui';
import {
  CLAIM_LABEL,
  FORMAT_LABEL,
  ISSUE_LABEL,
  label,
  MODALITY_LABEL,
  pieceStatus,
  PILLAR_LABEL,
  readerLabel,
  SELECTION_LABEL,
  SEVERITY,
  STAGE_LABEL,
  VERDICT,
  vetoable,
} from '../lib/editorial';
import { formatDateTime, formatDay, formatNumber, money } from '../lib/format';

const filled = (value: object | null | undefined) => Boolean(value && Object.keys(value).length);
const list = <T,>(value: T[] | null | undefined): T[] => (Array.isArray(value) ? value : []);

function UnitLink({ unit }: { unit: string }) {
  return (
    <Link className="chip" to={`/conocimiento?unidad=${encodeURIComponent(unit)}`}>
      {unit}
    </Link>
  );
}

function Section({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section className="card" aria-labelledby={id}>
      <h2 id={id}>{title}</h2>
      {children}
    </section>
  );
}

function Bullets({ title, items, lang }: { title: string; items: string[]; lang?: string }) {
  if (!items.length) return null;
  return (
    <>
      <p className="sectionlabel">{title}</p>
      <ul className="risks" lang={lang}>
        {items.map((item, index) => (
          <li key={index}>{item}</li>
        ))}
      </ul>
    </>
  );
}

function Claims({ claims, summary }: { claims: Claim[]; summary: string }) {
  if (!claims.length) return null;
  return (
    <details>
      <summary>
        {summary} ({claims.length})
      </summary>
      <ul className="claims">
        {claims.map((claim, index) => {
          const kind = claim.status ?? claim.kind ?? '';
          return (
            <li key={index}>
              <Badge tone={kind === 'unsupported' ? 'bad' : 'muted'}>{label(CLAIM_LABEL, kind)}</Badge> <span lang="en">{claim.text}</span>
            </li>
          );
        })}
      </ul>
    </details>
  );
}

// ---------------------------------------------------------------- status and veto

function StatusCard({ piece }: { piece: PieceDetail }) {
  const status = pieceStatus(piece.status);
  const action = piece.action_detail;
  const impressions = piece.metrics?.impressions;
  return (
    <section className="card" aria-labelledby="piece-status">
      <h2 id="piece-status" className="visually-hidden">
        Estado
      </h2>
      <div className="cardhead">
        <p>
          <Badge tone={status.tone}>{status.label}</Badge>
        </p>
        <p className="small">
          <span className="muted">Hora de salida: </span>
          <strong>{formatDateTime(piece.scheduled_for)}</strong>
        </p>
      </div>
      {piece.status === 'preparing' ? (
        <p className="small">
          En preparación{piece.stage ? <> · etapa: {label(STAGE_LABEL, piece.stage)}</> : null}. Podrás vetarla en cuanto pase el verificador.
        </p>
      ) : null}
      {piece.action && vetoable(piece.action) ? (
        <>
          {piece.action.state === 'approved' ? (
            <p className="note info">Aprobada por la política autónoma: saldrá sola a esa hora, salvo que la vetes antes.</p>
          ) : (
            <p className="note info">
              Espera a la política autónoma, que la aprueba si cumple sus reglas (o tu aprobación, si CONT-09 está en modo «approval»). Una
              vez aprobada, saldrá sola a esa hora salvo que la vetes.
            </p>
          )}
          <div className="buttonrow">
            <VetoPiece actionId={piece.action.id} slotDate={piece.slot_date} scheduledFor={piece.scheduled_for} />
            {piece.action.state === 'proposed' ? (
              <Link className="secondary buttonlink" to="/acciones?capacidad=publicaciones&state=proposed">
                Aprobar desde Acciones
              </Link>
            ) : null}
          </div>
        </>
      ) : null}
      {piece.note ? (
        <p className="small">
          <span className="muted">Nota del circuito: </span>
          {piece.note}
        </p>
      ) : null}
      {action?.decision_note ? (
        <p className="small">
          <span className="muted">Decisión{action.decided_at ? ` (${formatDateTime(action.decided_at)})` : ''}: </span>
          {action.decision_note}
        </p>
      ) : null}
      {action?.execution?.note ? <p className="small">{action.execution.note}</p> : null}
      <ExternalLink href={piece.external_url ?? action?.execution?.external_url}>Ver el post publicado en LinkedIn</ExternalLink>
      {typeof impressions === 'number' ? (
        <dl className="facts">
          <dt>Impresiones</dt>
          <dd>
            <strong>{formatNumber(impressions)}</strong>
            {piece.metrics?.source ? <span className="muted small"> · fuente: {piece.metrics.source}</span> : null}
          </dd>
        </dl>
      ) : null}
      {action && !vetoable(piece.action) ? (
        <p className="small">
          <Link to="/acciones?capacidad=publicaciones">Ver en Acciones</Link>
        </p>
      ) : null}
    </section>
  );
}

// ---------------------------------------------------------------- final text and verifier

function FinalText({ piece }: { piece: PieceDetail }) {
  if (!piece.final_text) return null;
  return (
    <Section id="final-title" title="Texto final">
      <div className="proposed finaltext" lang="en">
        {piece.final_text}
      </div>
      <p className="muted small">{formatNumber(piece.final_text.length)} caracteres · se publica tal cual, en inglés.</p>
    </Section>
  );
}

const VERDICT_TEXT: Record<string, string> = { ready_for_execution: 'lista para publicar', blocked: 'bloqueada' };

function Verifier({ piece }: { piece: PieceDetail }) {
  const v = piece.verification;
  if (!filled(v)) return null;
  const verdict = v.verdict ? (VERDICT[v.verdict] ?? { label: v.verdict, tone: 'muted' as const }) : null;
  const corrected = v.model_verdict && v.verdict && v.model_verdict !== v.verdict;
  return (
    <Section id="verifier-title" title="Veredicto del verificador">
      {verdict ? (
        <p>
          <Badge tone={verdict.tone}>{verdict.label}</Badge>
        </p>
      ) : null}
      {corrected ? (
        <p className="small muted">
          El modelo dijo «{label(VERDICT_TEXT, v.model_verdict)}», pero las guardas deterministas bloquean la pieza.
        </p>
      ) : null}
      <Bullets title="MOTIVOS DEL BLOQUEO" items={list(v.blocking_reasons)} />
      {v.summary ? <p>{v.summary}</p> : null}
      {list(v.findings).length ? (
        <>
          <p className="sectionlabel">HALLAZGOS</p>
          <ul className="findings">
            {list(v.findings).map((finding, index) => {
              const severity = SEVERITY[finding.severity] ?? { label: finding.severity, tone: 'muted' as const };
              return (
                <li key={index}>
                  <Badge tone={severity.tone}>{severity.label}</Badge> <strong>{label(ISSUE_LABEL, finding.issue)}</strong>
                  {finding.quote ? (
                    <q className="quote" lang="en">
                      {finding.quote}
                    </q>
                  ) : null}
                  {finding.detail ? <span className="small"> {finding.detail}</span> : null}
                </li>
              );
            })}
          </ul>
        </>
      ) : null}
      <Claims claims={list(v.checked_claims)} summary="Afirmaciones comprobadas" />
      {v.text_sha256 ? (
        <p className="muted small">
          Veredicto sobre el texto exacto (SHA-256 <code>{v.text_sha256.slice(0, 12)}…</code>): si el texto cambia, deja de valer.
        </p>
      ) : null}
    </Section>
  );
}

// ---------------------------------------------------------------- brief

function BriefSection({ piece }: { piece: PieceDetail }) {
  const brief = piece.brief;
  if (!filled(brief)) {
    return (
      <Section id="brief-title" title="Brief">
        <Empty>El director todavía no ha fijado el brief.</Empty>
      </Section>
    );
  }
  const evidence = list(brief.evidence);
  return (
    <Section id="brief-title" title="Brief">
      {brief.decision === 'skip' ? (
        <p className="note warn">El director decidió no publicar este día: {brief.skip_reason || 'sin material genuino.'}</p>
      ) : null}
      <dl className="facts">
        <dt>Lector principal</dt>
        <dd>{readerLabel(brief.primary_reader)}</dd>
        <dt>Modalidad</dt>
        <dd>{label(MODALITY_LABEL, brief.modality)}</dd>
        <dt>Pilar</dt>
        <dd>{label(PILLAR_LABEL, brief.pillar)}</dd>
        <dt>Tesis</dt>
        <dd>{brief.thesis || '—'}</dd>
        <dt>Enfoque</dt>
        <dd>{brief.approach ? <Link to={`/conocimiento?unidad=${encodeURIComponent(brief.approach)}`}>{brief.approach}</Link> : '—'}</dd>
        <dt>Formato</dt>
        <dd>{label(FORMAT_LABEL, brief.format)}</dd>
        {brief.reader_value ? (
          <>
            <dt>Valor para el lector</dt>
            <dd>{brief.reader_value}</dd>
          </>
        ) : null}
        {brief.success_criterion ? (
          <>
            <dt>Criterio de éxito</dt>
            <dd>{brief.success_criterion}</dd>
          </>
        ) : null}
      </dl>
      <Bullets title="QUÉ EVITAR" items={list(brief.avoid)} />
      {evidence.length ? (
        <>
          <p className="sectionlabel">EVIDENCIA</p>
          <ul className="risks">
            {evidence.map((item, index) => (
              <li key={index}>
                <span className="muted">{label(CLAIM_LABEL, item.kind)}:</span> {item.note || item.ref}
              </li>
            ))}
          </ul>
        </>
      ) : null}
      {brief.rationale ? (
        <>
          <p className="sectionlabel">POR QUÉ ESTA IDEA</p>
          <p>{brief.rationale}</p>
        </>
      ) : null}
    </Section>
  );
}

// ---------------------------------------------------------------- variants, readers and selection

function VariantBlock({ name, author, variant, chosen }: { name: string; author: string; variant: Variant | undefined; chosen: boolean }) {
  return (
    <div className="variant">
      <h3>
        {name} <span className="muted small">· {author}</span> {chosen ? <Badge tone="ok">Elegida</Badge> : null}
      </h3>
      {variant ? (
        <>
          {variant.angle ? <p className="muted small">Ángulo: {variant.angle}</p> : null}
          {variant.text ? (
            <div className="proposed" lang="en">
              {variant.text}
            </div>
          ) : null}
          <Bullets title="INCERTIDUMBRES" items={list(variant.uncertainties)} />
          <Claims claims={list(variant.claims)} summary="Afirmaciones" />
        </>
      ) : (
        <Empty>Sin texto.</Empty>
      )}
    </div>
  );
}

function VariantsSection({ piece }: { piece: PieceDetail }) {
  const { variants, selection } = piece;
  if (!filled(variants)) return null;
  return (
    <Section id="variants-title" title="Variantes A y B">
      <div className="grid two">
        <VariantBlock name="Variante A" author="Copywriter A" variant={variants.variant_a} chosen={selection.decision === 'A'} />
        <VariantBlock name="Variante B" author="Copywriter B" variant={variants.variant_b} chosen={selection.decision === 'B'} />
      </div>
    </Section>
  );
}

function AssessmentBlock({ title, assessment }: { title: string; assessment: Assessment | undefined }) {
  const strengths = list(assessment?.strengths);
  const objections = list(assessment?.objections);
  return (
    <div>
      <h4 className="sectionlabel">{title}</h4>
      {strengths.length ? (
        <>
          <p className="small muted">Fortalezas</p>
          <ul className="risks">
            {strengths.map((item, index) => (
              <li key={index}>{item}</li>
            ))}
          </ul>
        </>
      ) : null}
      {objections.length ? (
        <>
          <p className="small muted">Objeciones</p>
          <ul className="risks">
            {objections.map((objection, index) => {
              const severity = SEVERITY[objection.severity] ?? { label: objection.severity, tone: 'muted' as const };
              return (
                <li key={index}>
                  <Badge tone={severity.tone}>{severity.label}</Badge> {objection.text}
                </li>
              );
            })}
          </ul>
        </>
      ) : null}
      {!strengths.length && !objections.length ? <p className="small muted">Sin comentarios.</p> : null}
    </div>
  );
}

function PanelSection({ piece }: { piece: PieceDetail }) {
  const panel = piece.panel;
  if (!filled(panel)) return null;
  const readers = list(panel.readers);
  return (
    <Section id="panel-title" title="Panel de lectores">
      <p className="muted small">Cinco perspectivas simuladas: son hipótesis sobre comprensión y utilidad, no métricas.</p>
      {panel.summary ? <p>{panel.summary}</p> : null}
      <ul className="readers">
        {readers.map((reader, index) => (
          <li key={`${reader.reader}-${index}`}>
            <h3>{readerLabel(reader.reader)}</h3>
            <div className="grid two">
              <AssessmentBlock title="VARIANTE A" assessment={reader.variant_a} />
              <AssessmentBlock title="VARIANTE B" assessment={reader.variant_b} />
            </div>
          </li>
        ))}
      </ul>
    </Section>
  );
}

function SelectionSection({ piece }: { piece: PieceDetail }) {
  const selection = piece.selection;
  if (!filled(selection)) return null;
  return (
    <Section id="selection-title" title="Selección">
      <p>
        <strong>{label(SELECTION_LABEL, selection.decision)}</strong>
      </p>
      {selection.rationale ? <p>{selection.rationale}</p> : null}
      <Bullets title="OBJECIONES RESUELTAS" items={list(selection.resolved_objections)} />
      <Bullets title="OBJECIONES CONSERVADAS" items={list(selection.kept_objections)} />
    </Section>
  );
}

// ---------------------------------------------------------------- sources and cost

function totalUsd(usage: StageUsage[]): number | null {
  const values = usage.map((u) => Number(u.estimated_usd)).filter((n) => Number.isFinite(n));
  return values.length ? values.reduce((a, b) => a + b, 0) : null;
}

function SourcesSection({ piece }: { piece: PieceDetail }) {
  const citations = list(piece.citations);
  const signals = list(piece.signals);
  const usage = list(piece.usage);
  if (!citations.length && !signals.length && !usage.length) return null;
  const total = totalUsd(usage);
  return (
    <Section id="sources-title" title="Fuentes y coste">
      {citations.length ? (
        <>
          <p className="sectionlabel">CITAS DEL CURSO</p>
          <ul className="chips">
            {citations.map((unit) => (
              <li key={unit}>
                <UnitLink unit={unit} />
              </li>
            ))}
          </ul>
        </>
      ) : null}
      {signals.length ? (
        <>
          <p className="sectionlabel">SEÑALES USADAS (DATOS DE TERCEROS)</p>
          <ul className="list">
            {signals.map((signal) => (
              <li key={signal.id}>
                <p className="small">
                  <strong>{signal.author || 'Autor desconocido'}</strong>
                  {signal.posted_at ? <span className="muted"> · {formatDateTime(signal.posted_at)}</span> : null}
                </p>
                {signal.text ? <blockquote className="posttext">{signal.text}</blockquote> : null}
              </li>
            ))}
          </ul>
        </>
      ) : null}
      {usage.length ? (
        <details>
          <summary>Coste estimado{total !== null ? `: ${money(total)}` : ''}</summary>
          <ul className="risks">
            {usage.map((u, index) => (
              <li key={index}>
                {label(STAGE_LABEL, u.stage)} · {u.model || 'modelo desconocido'}
                {u.estimated_usd !== null && u.estimated_usd !== undefined ? ` · ${money(u.estimated_usd)}` : ''}
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </Section>
  );
}

export function Pieza() {
  const { pieceId = '' } = useParams();
  const query = useQuery({ queryKey: keys.piece(pieceId), queryFn: () => getPiece(pieceId), enabled: Boolean(pieceId), refetchInterval: 30_000 });
  const piece = query.data;
  return (
    <div className="stack">
      <p className="small">
        <Link to="/contenido">← Calendario</Link>
      </p>
      <PageHeader eyebrow="PIEZA DE LA PUBLICACIÓN DIARIA" title={piece ? `Pieza del ${formatDay(piece.slot_date)}` : 'Pieza'} />
      {query.isPending ? <Loading label="Cargando la pieza…" /> : null}
      {query.isError ? <ErrorNote error={query.error} onRetry={() => void query.refetch()} /> : null}
      {piece ? (
        <>
          <StatusCard piece={piece} />
          <FinalText piece={piece} />
          <Verifier piece={piece} />
          <BriefSection piece={piece} />
          <VariantsSection piece={piece} />
          <PanelSection piece={piece} />
          <SelectionSection piece={piece} />
          <SourcesSection piece={piece} />
        </>
      ) : null}
    </div>
  );
}
