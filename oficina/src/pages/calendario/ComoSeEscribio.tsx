// «Cómo se escribió»: brief, variants, readers, selection, verifier and sources, all folded by default.
import { useState, type ReactNode } from 'react';
import type { Assessment, PieceDetail, StageUsage, Variant } from '../../api/types';
import { IconChevronDown } from '../../components/icons';
import { Badge, Section, TabBar, type Tone } from '../../components/ui';
import { CLAIM_LABEL, FORMAT_LABEL, ISSUE_LABEL, label, MODALITY_LABEL, PILLAR_LABEL, readerLabel, SELECTION_LABEL, SEVERITY, VERDICT } from '../../lib/editorial';
import { excerpt, formatUsd } from '../../lib/format';

const filled = (value: object | null | undefined) => Boolean(value && Object.keys(value).length);
const list = <T,>(value: T[] | null | undefined): T[] => (Array.isArray(value) ? value : []);

function Fold({ title, children }: { title: string; children: ReactNode }) {
  return (
    <details className="pz-fold">
      <summary>
        {title}
        <IconChevronDown size={20} />
      </summary>
      <div className="pz-fold-body">{children}</div>
    </details>
  );
}

function Field({ name, children }: { name: string; children: ReactNode }) {
  if (children === null || children === undefined || children === '' || (Array.isArray(children) && !children.length)) return null;
  return (
    <div className="pz-field">
      <p className="section-label">{name}</p>
      <div className="pz-field-value">{children}</div>
    </div>
  );
}

function NotYet({ finished }: { finished: boolean }) {
  return <p className="t-detalle text-suave">{finished ? 'Esta etapa no llegó a correr.' : 'Esta etapa aún no ha corrido.'}</p>;
}

function BriefFold({ piece, finished }: { piece: PieceDetail; finished: boolean }) {
  const brief = piece.brief;
  return (
    <Fold title="Brief">
      {!filled(brief) ? (
        <p className="t-detalle text-suave">{finished ? 'El director no llegó a fijar el brief.' : 'El director todavía no ha fijado el brief.'}</p>
      ) : (
        <>
          {brief.decision === 'skip' ? <p>El director decidió no publicar este día: {brief.skip_reason || 'no había material genuino.'}</p> : null}
          <Field name="Lector">{brief.primary_reader ? readerLabel(brief.primary_reader) : null}</Field>
          <Field name="Modalidad">{brief.modality ? label(MODALITY_LABEL, brief.modality) : null}</Field>
          <Field name="Pilar">{brief.pillar ? label(PILLAR_LABEL, brief.pillar) : null}</Field>
          <Field name="Tesis">{brief.thesis ? <span lang="en">{brief.thesis}</span> : null}</Field>
          <Field name="Enfoque">{brief.approach || null}</Field>
          <Field name="Formato">{brief.format ? label(FORMAT_LABEL, brief.format) : null}</Field>
          <Field name="Valor para el lector">{brief.reader_value || null}</Field>
          <Field name="Criterio de éxito">{brief.success_criterion || null}</Field>
          <Field name="Qué evitar">{list(brief.avoid).length ? list(brief.avoid).join(' · ') : null}</Field>
          <Field name="Evidencia">
            {list(brief.evidence).length ? (
              <ul className="pz-list">
                {list(brief.evidence).map((item, index) => (
                  <li key={index}>
                    {item.note || item.ref}
                    {item.kind ? <span className="text-suave"> · {label(CLAIM_LABEL, item.kind)}</span> : null}
                  </li>
                ))}
              </ul>
            ) : null}
          </Field>
          <Field name="Por qué">{brief.rationale || null}</Field>
        </>
      )}
    </Fold>
  );
}

function VariantCard({ name, variant, chosen }: { name: 'A' | 'B'; variant: Variant | undefined; chosen: string | null }) {
  return (
    <div className="card compact pz-variant">
      <div className="pz-cut-head">
        <p className="section-label">
          Variante {name} · Copywriter {name}
        </p>
        {chosen ? <Badge tone="ok">{chosen}</Badge> : null}
      </div>
      {variant?.angle ? <p className="t-detalle text-suave">Ángulo: {variant.angle}</p> : null}
      {variant?.text ? (
        <p lang="en" className="pz-text">
          {variant.text}
        </p>
      ) : (
        <p className="t-detalle text-suave">Sin texto.</p>
      )}
      {list(variant?.uncertainties).length ? <p className="t-detalle text-suave">Incertidumbres: {list(variant?.uncertainties).join(' · ')}</p> : null}
    </div>
  );
}

function VariantsFold({ piece, desktop, finished }: { piece: PieceDetail; desktop: boolean; finished: boolean }) {
  const [tab, setTab] = useState<'A' | 'B'>(piece.selection?.decision === 'B' ? 'B' : 'A');
  const decision = piece.selection?.decision;
  const chosen = (name: 'A' | 'B') => (decision === name ? 'Elegida' : decision === 'merge' ? 'En la fusión' : null);
  const variants = piece.variants;
  return (
    <Fold title="Variantes A y B">
      {!filled(variants) ? (
        <NotYet finished={finished} />
      ) : desktop ? (
        <div className="pz-variants">
          <VariantCard name="A" variant={variants.variant_a} chosen={chosen('A')} />
          <VariantCard name="B" variant={variants.variant_b} chosen={chosen('B')} />
        </div>
      ) : (
        <>
          <TabBar
            label="Variante"
            idPrefix="variante"
            value={tab}
            onChange={setTab}
            tabs={[
              { value: 'A', label: decision === 'A' ? 'Variante A · Elegida' : 'Variante A' },
              { value: 'B', label: decision === 'B' ? 'Variante B · Elegida' : 'Variante B' },
            ]}
          />
          <div role="tabpanel" id={`variante-${tab}-panel`} aria-labelledby={`variante-${tab}`}>
            <VariantCard name={tab} variant={tab === 'A' ? variants.variant_a : variants.variant_b} chosen={chosen(tab)} />
          </div>
        </>
      )}
    </Fold>
  );
}

const SEVERITY_RANK: Record<string, number> = { material: 3, missing_data: 2, preference: 1 };
const SEVERITY_BADGE: Record<string, { label: string; tone: Tone }> = {
  material: { label: 'Objeción material', tone: 'bad' },
  missing_data: { label: 'Faltan datos', tone: 'warn' },
  preference: { label: 'Objeción menor', tone: 'muted' },
};

function assessmentLine(name: string, assessment: Assessment | undefined): string | null {
  const strengths = list(assessment?.strengths);
  const objections = list(assessment?.objections).map((o) => o.text);
  const parts = [strengths.length ? strengths.join('; ') : '', objections.length ? `Objeciones: ${objections.join('; ')}` : ''].filter(Boolean);
  return parts.length ? `${name}: ${parts.join('. ')}` : null;
}

function PanelFold({ piece, finished }: { piece: PieceDetail; finished: boolean }) {
  const panel = piece.panel;
  const readers = list(panel?.readers);
  return (
    <Fold title="Panel de lectores">
      {!filled(panel) ? (
        <NotYet finished={finished} />
      ) : (
        <>
          <p className="t-detalle text-suave">Cinco perspectivas simuladas: son hipótesis sobre comprensión y utilidad, no métricas.</p>
          {panel.summary ? <p>{panel.summary}</p> : null}
          <ul className="pz-readers">
            {readers.map((reader, index) => {
              const worst = [...list(reader.variant_a?.objections), ...list(reader.variant_b?.objections)].reduce<string | null>(
                (acc, objection) => ((SEVERITY_RANK[objection.severity] ?? 0) > (SEVERITY_RANK[acc ?? ''] ?? 0) ? objection.severity : acc),
                null,
              );
              const badge = worst ? SEVERITY_BADGE[worst] : { label: 'Sin objeciones', tone: 'ok' as Tone };
              return (
                <li key={`${reader.reader}-${index}`} className="pz-reader">
                  <div className="pz-reader-text">
                    <p>{readerLabel(reader.reader)}</p>
                    {[assessmentLine('A', reader.variant_a), assessmentLine('B', reader.variant_b)].filter(Boolean).map((line) => (
                      <p key={line} className="t-detalle text-suave">
                        {line}
                      </p>
                    ))}
                  </div>
                  {badge ? <Badge tone={badge.tone}>{badge.label}</Badge> : null}
                </li>
              );
            })}
          </ul>
        </>
      )}
    </Fold>
  );
}

function SelectionFold({ piece, finished }: { piece: PieceDetail; finished: boolean }) {
  const selection = piece.selection;
  return (
    <Fold title="Selección">
      {!filled(selection) ? (
        <NotYet finished={finished} />
      ) : (
        <>
          <Field name="Decisión">{selection.decision ? label(SELECTION_LABEL, selection.decision) : null}</Field>
          <Field name="Razonamiento">{selection.rationale || null}</Field>
          <Field name="Objeciones resueltas">{list(selection.resolved_objections).length ? list(selection.resolved_objections).join(' · ') : null}</Field>
          <Field name="Objeciones conservadas">{list(selection.kept_objections).length ? list(selection.kept_objections).join(' · ') : null}</Field>
        </>
      )}
    </Fold>
  );
}

function VerifierFold({ piece, finished }: { piece: PieceDetail; finished: boolean }) {
  const v = piece.verification;
  if (!filled(v)) {
    return (
      <Fold title="Verificador">
        <NotYet finished={finished} />
      </Fold>
    );
  }
  const verdict = v.verdict ? (VERDICT[v.verdict] ?? { label: v.verdict, tone: 'muted' as Tone }) : null;
  const corrected = Boolean(v.model_verdict && v.verdict && v.model_verdict !== v.verdict);
  const claims = list(v.checked_claims);
  const supported = claims.filter((claim) => (claim.status ?? claim.kind) !== 'unsupported').length;
  return (
    <Fold title="Verificador">
      <div className="pz-verdict">
        {verdict ? <Badge tone={verdict.tone}>{v.verdict === 'ready_for_execution' ? 'Aprobada' : verdict.label}</Badge> : null}
        <p className="t-detalle text-suave">{corrected ? 'Las guardas corrigieron al modelo' : 'Sin correcciones de las guardas'}</p>
      </div>
      {v.summary ? <p>{v.summary}</p> : null}
      <Field name="Motivos del bloqueo">
        {list(v.blocking_reasons).length ? (
          <ul className="pz-list">
            {list(v.blocking_reasons).map((reason, index) => (
              <li key={index}>{reason}</li>
            ))}
          </ul>
        ) : null}
      </Field>
      <Field name="Hallazgos">
        {list(v.findings).length ? (
          <ul className="pz-list">
            {list(v.findings).map((finding, index) => {
              const severity = SEVERITY[finding.severity] ?? { label: finding.severity, tone: 'muted' as Tone };
              return (
                <li key={index}>
                  {severity.label}: {label(ISSUE_LABEL, finding.issue)}
                  {finding.quote ? (
                    <>
                      {' '}
                      <q lang="en">{finding.quote}</q>
                    </>
                  ) : null}
                  {finding.detail ? <span className="text-suave"> · {finding.detail}</span> : null}
                </li>
              );
            })}
          </ul>
        ) : null}
      </Field>
      <Field name="Afirmaciones comprobadas">{claims.length ? `${supported} de ${claims.length}` : null}</Field>
    </Fold>
  );
}

const COST_STAGES: { key: string; label: string }[] = [
  { key: 'director', label: 'Director' },
  { key: 'redactor', label: 'Redactores' },
  { key: 'lectores', label: 'Lectores' },
  { key: 'seleccion', label: 'Selección' },
  { key: 'verificador', label: 'Verificador' },
];

function costRows(usage: StageUsage[]): { label: string; usd: number }[] {
  const totals = new Map<string, number>();
  for (const row of usage) {
    const usd = Number(row.estimated_usd);
    if (row.estimated_usd === null || row.estimated_usd === undefined || !Number.isFinite(usd)) continue;
    totals.set(row.stage, (totals.get(row.stage) ?? 0) + usd);
  }
  const known = COST_STAGES.filter((stage) => totals.has(stage.key)).map((stage) => ({ label: stage.label, usd: totals.get(stage.key)! }));
  const other = [...totals.entries()].filter(([stage]) => !COST_STAGES.some((s) => s.key === stage)).map(([stage, usd]) => ({ label: stage, usd }));
  return [...known, ...other];
}

function SourcesFold({ piece }: { piece: PieceDetail }) {
  const citations = list(piece.citations);
  const signals = list(piece.signals);
  const rows = costRows(list(piece.usage));
  const total = rows.reduce((sum, row) => sum + row.usd, 0);
  return (
    <Fold title="Fuentes y coste">
      <Field name="Citas del curso">{citations.length ? citations.join(' · ') : null}</Field>
      <Field name="Señales de terceros">
        {signals.length ? (
          <ul className="pz-list">
            {signals.map((signal) => (
              <li key={signal.id}>
                {signal.author || 'Autor desconocido'}
                {signal.text ? (
                  <>
                    : <span lang="en">{excerpt(signal.text, 140)}</span>
                  </>
                ) : null}
              </li>
            ))}
          </ul>
        ) : null}
      </Field>
      <div className="pz-field">
        <p className="section-label">Coste</p>
        {rows.length ? (
          <dl className="pz-cost">
            {rows.map((row) => (
              <div key={row.label}>
                <dt>{row.label}</dt>
                <dd>{formatUsd(row.usd)}</dd>
              </div>
            ))}
            <div className="pz-cost-total">
              <dt>Total</dt>
              <dd>{formatUsd(total)}</dd>
            </div>
          </dl>
        ) : (
          <p className="t-detalle text-suave">Sin dato de coste.</p>
        )}
      </div>
      {!citations.length && !signals.length ? <p className="t-detalle text-suave">Sin citas ni señales registradas.</p> : null}
    </Fold>
  );
}

/** States where the circuit will not run any further stage. */
const FINISHED = new Set(['skipped', 'blocked', 'failed', 'discarded', 'vetoed', 'expired', 'superseded', 'published', 'uncertain']);

export function ComoSeEscribio({ piece, desktop }: { piece: PieceDetail; desktop: boolean }) {
  const finished = FINISHED.has(piece.status);
  return (
    <Section label="Cómo se escribió" id="como">
      <div className="pz-folds">
        <BriefFold piece={piece} finished={finished} />
        <VariantsFold piece={piece} desktop={desktop} finished={finished} />
        <PanelFold piece={piece} finished={finished} />
        <SelectionFold piece={piece} finished={finished} />
        <VerifierFold piece={piece} finished={finished} />
        <SourcesFold piece={piece} />
      </div>
    </Section>
  );
}
