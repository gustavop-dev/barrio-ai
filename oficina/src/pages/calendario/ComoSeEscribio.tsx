// «Cómo se escribió»: brief, variants, readers, selection, verifier, repair round and sources, all folded by default.
import { useState, type ReactNode } from 'react';
import type { PieceDetail, Variant } from '../../api/types';
import { IconChevronDown } from '../../components/icons';
import { Badge, Section, TabBar, type Tone } from '../../components/ui';
import {
  asArray as list,
  assessmentLine,
  CLAIM_LABEL,
  costRows,
  filled,
  FINISHED_STATUSES as FINISHED,
  FORMAT_LABEL,
  ISSUE_LABEL,
  label,
  MODALITY_LABEL,
  notYetText,
  PILLAR_LABEL,
  readerBadge,
  readerLabel,
  repairOutcome,
  repairTrigger,
  SELECTION_LABEL,
  SEVERITY,
  variantChosen,
  verifierSummary,
} from '../../lib/editorial';
import { excerpt, formatUsd } from '../../lib/format';

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
  return <p className="t-detalle text-suave">{notYetText(finished)}</p>;
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
  const chosen = (name: 'A' | 'B') => variantChosen(decision, name);
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
              const badge = readerBadge(reader);
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
  const { verdict, guards, supported, claims } = verifierSummary(v);
  return (
    <Fold title="Verificador">
      <div className="pz-verdict">
        {verdict ? <Badge tone={verdict.tone}>{verdict.label}</Badge> : null}
        <p className="t-detalle text-suave">{guards}</p>
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
      <Field name="Afirmaciones comprobadas">{claims ? `${supported} de ${claims}` : null}</Field>
    </Fold>
  );
}

/** R4: shown only when the rules or the verifier found concrete problems and the round ran. */
function RepairFold({ piece }: { piece: PieceDetail }) {
  const repair = piece.verification?.repair;
  if (!repair) return null;
  const outcome = repairOutcome(repair);
  return (
    <Fold title="Ronda de reparación">
      <div className="pz-verdict">
        <Badge tone={outcome.tone}>{outcome.label}</Badge>
        <p className="t-detalle text-suave">{repairTrigger(repair)}</p>
      </div>
      <Field name="Qué había que corregir">
        {list(repair.findings).length ? (
          <ul className="pz-list">
            {list(repair.findings).map((finding, index) => (
              <li key={index}>
                {finding.source === 'reglas' ? finding.detail : label(ISSUE_LABEL, finding.issue)}
                {finding.quote ? (
                  <>
                    {' '}
                    <q lang="en">{finding.quote}</q>
                  </>
                ) : null}
                {finding.source !== 'reglas' && finding.detail ? <span className="text-suave"> · {finding.detail}</span> : null}
              </li>
            ))}
          </ul>
        ) : null}
      </Field>
      <Field name="Qué cambió">
        {list(repair.changes).length ? (
          <ul className="pz-list">
            {list(repair.changes).map((item, index) => (
              <li key={index}>{item.change}</li>
            ))}
          </ul>
        ) : null}
      </Field>
      <Field name="Nota">{repair.note || repair.rationale || null}</Field>
      <Field name="Texto antes de reparar">
        {repair.original_text ? (
          <p lang="en" className="pz-text">
            {repair.original_text}
          </p>
        ) : null}
      </Field>
    </Fold>
  );
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
        <RepairFold piece={piece} />
        <SourcesFold piece={piece} />
      </div>
    </Section>
  );
}
