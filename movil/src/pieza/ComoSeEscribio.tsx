// «Cómo se escribió» (Pieza.dc.html): brief, variants, readers, selection, verifier, repair round and
// sources, every fold closed by default. The variants are tabs you can also swipe, marked «Elegida».
import type { PieceDetail, Variant } from '@compartido/api/types';
import { communityEffects, communityTrace } from '@compartido/logic/comunidad';
import {
  asArray,
  assessmentLine,
  CLAIM_LABEL,
  costRows,
  filled,
  FINISHED_STATUSES,
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
} from '@compartido/logic/editorial';
import { excerpt, formatUsd } from '@compartido/logic/format';
import type { Tone } from '@compartido/logic/tone';
import { useRef, useState, type ReactNode } from 'react';
import { ScrollView, StyleSheet, View, type LayoutChangeEvent, type NativeScrollEvent, type NativeSyntheticEvent, type ScrollViewInstance } from 'react-native';
import { Badge, Card, Fold, Section, T, TabBar } from '@/components/ui';
import { colors, space } from '@/theme/tokens';

/** A labelled fact; nothing when the value is empty. */
function Fact({ name, children }: { name: string; children: ReactNode }) {
  if (children === null || children === undefined || children === '' || (Array.isArray(children) && !children.length)) return null;
  return (
    <View style={styles.fact}>
      <T variant="etiqueta" soft>
        {name}
      </T>
      {typeof children === 'string' ? <T>{children}</T> : children}
    </View>
  );
}

function Bullets({ items }: { items: ReactNode[] }) {
  return (
    <View style={styles.bullets}>
      {items.map((item, index) => (
        <View key={index} style={styles.bullet}>
          <T importantForAccessibility="no">•</T>
          <View style={styles.bulletText}>{typeof item === 'string' ? <T>{item}</T> : item}</View>
        </View>
      ))}
    </View>
  );
}

function NotYet({ finished }: { finished: boolean }) {
  return (
    <T variant="detalle" soft>
      {notYetText(finished)}
    </T>
  );
}

function BriefFold({ piece, finished }: { piece: PieceDetail; finished: boolean }) {
  const brief = piece.brief;
  return (
    <Fold summary="Brief">
      {!filled(brief) ? (
        <T variant="detalle" soft>
          {finished ? 'El director no llegó a fijar el brief.' : 'El director todavía no ha fijado el brief.'}
        </T>
      ) : (
        <>
          {brief.decision === 'skip' ? <T>{`El director decidió no publicar este día: ${brief.skip_reason || 'no había material genuino.'}`}</T> : null}
          <Fact name="Lector">{brief.primary_reader ? readerLabel(brief.primary_reader) : null}</Fact>
          <Fact name="Modalidad">{brief.modality ? label(MODALITY_LABEL, brief.modality) : null}</Fact>
          <Fact name="Pilar">{brief.pillar ? label(PILLAR_LABEL, brief.pillar) : null}</Fact>
          <Fact name="Tesis">{brief.thesis || null}</Fact>
          <Fact name="Enfoque">{brief.approach || null}</Fact>
          <Fact name="Formato">{brief.format ? label(FORMAT_LABEL, brief.format) : null}</Fact>
          <Fact name="Valor para el lector">{brief.reader_value || null}</Fact>
          <Fact name="Criterio de éxito">{brief.success_criterion || null}</Fact>
          <Fact name="Qué evitar">{asArray(brief.avoid).length ? asArray(brief.avoid).join(' · ') : null}</Fact>
          <Fact name="Evidencia">
            {asArray(brief.evidence).length ? (
              <Bullets items={asArray(brief.evidence).map((item) => `${item.note || item.ref}${item.kind ? ` · ${label(CLAIM_LABEL, item.kind)}` : ''}`)} />
            ) : null}
          </Fact>
          <Fact name="Por qué">{brief.rationale || null}</Fact>
        </>
      )}
    </Fold>
  );
}

function VariantCard({ name, variant, chosen }: { name: 'A' | 'B'; variant: Variant | undefined; chosen: string | null }) {
  return (
    <Card compact>
      <View style={styles.head}>
        <T variant="etiqueta" soft style={styles.headText}>
          {`Variante ${name} · Copywriter ${name}`}
        </T>
        {chosen ? <Badge tone="ok">{chosen}</Badge> : null}
      </View>
      {variant?.angle ? (
        <T variant="detalle" soft>
          {`Ángulo: ${variant.angle}`}
        </T>
      ) : null}
      {variant?.text ? (
        <T selectable>{variant.text}</T>
      ) : (
        <T variant="detalle" soft>
          Sin texto.
        </T>
      )}
      {asArray(variant?.uncertainties).length ? (
        <T variant="detalle" soft>
          {`Incertidumbres: ${asArray(variant?.uncertainties).join(' · ')}`}
        </T>
      ) : null}
    </Card>
  );
}

type VariantName = 'A' | 'B';
const NAMES: readonly VariantName[] = ['A', 'B'];

/** The two variants as tabs over a horizontal pager: tap a tab or swipe the card. */
function VariantTabs({ piece }: { piece: PieceDetail }) {
  const decision = piece.selection?.decision;
  const [tab, setTab] = useState<VariantName>(decision === 'B' ? 'B' : 'A');
  const [width, setWidth] = useState(0);
  const pager = useRef<ScrollViewInstance>(null);
  const variants = piece.variants;

  const choose = (name: VariantName) => {
    setTab(name);
    pager.current?.scrollTo({ x: NAMES.indexOf(name) * width, animated: true });
  };
  /** Once the width is known, the pager starts on the chosen tab (B when B was chosen). */
  const laidOut = (next: number) => {
    if (next === width) return;
    setWidth(next);
    requestAnimationFrame(() => pager.current?.scrollTo({ x: NAMES.indexOf(tab) * next, animated: false }));
  };
  const settled = (event: NativeSyntheticEvent<NativeScrollEvent>) => {
    if (!width) return;
    const index = Math.round(event.nativeEvent.contentOffset.x / width);
    const name = NAMES[Math.min(NAMES.length - 1, Math.max(0, index))]!;
    if (name !== tab) setTab(name);
  };

  return (
    <View style={styles.variants}>
      <TabBar<VariantName>
        label="Variante"
        value={tab}
        onChange={choose}
        tabs={NAMES.map((name) => ({ value: name, label: decision === name ? `Variante ${name} · Elegida` : `Variante ${name}` }))}
      />
      <View onLayout={(event: LayoutChangeEvent) => laidOut(Math.round(event.nativeEvent.layout.width))}>
        <ScrollView
          ref={pager}
          testID="variantes"
          horizontal
          pagingEnabled
          showsHorizontalScrollIndicator={false}
          onMomentumScrollEnd={settled}
        >
          {NAMES.map((name) => (
            <View
              key={name}
              style={{ width: width || undefined }}
              importantForAccessibility={name === tab ? 'auto' : 'no-hide-descendants'}
              accessibilityElementsHidden={name !== tab}
              testID={`variante-${name}`}
            >
              <VariantCard name={name} variant={name === 'A' ? variants.variant_a : variants.variant_b} chosen={variantChosen(decision, name)} />
            </View>
          ))}
        </ScrollView>
      </View>
    </View>
  );
}

function VariantsFold({ piece, finished }: { piece: PieceDetail; finished: boolean }) {
  return <Fold summary="Variantes A y B">{!filled(piece.variants) ? <NotYet finished={finished} /> : <VariantTabs piece={piece} />}</Fold>;
}

function PanelFold({ piece, finished }: { piece: PieceDetail; finished: boolean }) {
  const panel = piece.panel;
  return (
    <Fold summary="Panel de lectores">
      {!filled(panel) ? (
        <NotYet finished={finished} />
      ) : (
        <>
          <T variant="detalle" soft>
            Cinco perspectivas simuladas: son hipótesis sobre comprensión y utilidad, no métricas.
          </T>
          {panel.summary ? <T>{panel.summary}</T> : null}
          <T>{communityTrace(panel)}</T>
          <View>
            {asArray(panel.readers).map((reader, index) => {
              const badge = readerBadge(reader);
              return (
                <View key={`${reader.reader}-${index}`} style={styles.reader}>
                  <View style={styles.readerText}>
                    <T>{readerLabel(reader.reader)}</T>
                    {communityEffects(reader).map((line, i) => <T key={i}>{line}</T>)}
                    {[assessmentLine('A', reader.variant_a), assessmentLine('B', reader.variant_b)].filter(Boolean).map((line) => (
                      <T key={line} variant="detalle" soft>
                        {line}
                      </T>
                    ))}
                  </View>
                  <Badge tone={badge.tone}>{badge.label}</Badge>
                </View>
              );
            })}
          </View>
        </>
      )}
    </Fold>
  );
}

function SelectionFold({ piece, finished }: { piece: PieceDetail; finished: boolean }) {
  const selection = piece.selection;
  return (
    <Fold summary="Selección">
      {!filled(selection) ? (
        <NotYet finished={finished} />
      ) : (
        <>
          <Fact name="Decisión">{selection.decision ? label(SELECTION_LABEL, selection.decision) : null}</Fact>
          <Fact name="Razonamiento">{selection.rationale || null}</Fact>
          <Fact name="Objeciones resueltas">{asArray(selection.resolved_objections).length ? asArray(selection.resolved_objections).join(' · ') : null}</Fact>
          <Fact name="Objeciones conservadas">{asArray(selection.kept_objections).length ? asArray(selection.kept_objections).join(' · ') : null}</Fact>
        </>
      )}
    </Fold>
  );
}

function findingLine(issue: string, quote: string | undefined, detail: string | undefined): string {
  return `${issue}${quote ? ` «${quote}»` : ''}${detail ? ` · ${detail}` : ''}`;
}

function VerifierFold({ piece, finished }: { piece: PieceDetail; finished: boolean }) {
  const v = piece.verification;
  if (!filled(v)) {
    return (
      <Fold summary="Verificador">
        <NotYet finished={finished} />
      </Fold>
    );
  }
  const { verdict, guards, supported, claims } = verifierSummary(v);
  return (
    <Fold summary="Verificador">
      <View style={styles.verdict}>
        {verdict ? <Badge tone={verdict.tone}>{verdict.label}</Badge> : null}
        <T variant="detalle" soft style={styles.headText}>
          {guards}
        </T>
      </View>
      {v.summary ? <T>{v.summary}</T> : null}
      <Fact name="Motivos del bloqueo">{asArray(v.blocking_reasons).length ? <Bullets items={asArray(v.blocking_reasons)} /> : null}</Fact>
      <Fact name="Hallazgos">
        {asArray(v.findings).length ? (
          <Bullets
            items={asArray(v.findings).map((finding) => {
              const severity = SEVERITY[finding.severity] ?? { label: finding.severity, tone: 'muted' as Tone };
              return findingLine(`${severity.label}: ${label(ISSUE_LABEL, finding.issue)}`, finding.quote, finding.detail);
            })}
          />
        ) : null}
      </Fact>
      <Fact name="Afirmaciones comprobadas">{claims ? `${supported} de ${claims}` : null}</Fact>
    </Fold>
  );
}

/** R4: only when the rules or the verifier found concrete problems and the round ran. */
function RepairFold({ piece }: { piece: PieceDetail }) {
  const repair = piece.verification?.repair;
  if (!repair) return null;
  const outcome = repairOutcome(repair);
  return (
    <Fold summary="Ronda de reparación">
      <View style={styles.verdict}>
        <Badge tone={outcome.tone}>{outcome.label}</Badge>
        <T variant="detalle" soft style={styles.headText}>
          {repairTrigger(repair)}
        </T>
      </View>
      <Fact name="Qué había que corregir">
        {asArray(repair.findings).length ? (
          <Bullets
            items={asArray(repair.findings).map((finding) =>
              finding.source === 'reglas' ? findingLine(finding.detail ?? '', finding.quote, undefined) : findingLine(label(ISSUE_LABEL, finding.issue), finding.quote, finding.detail),
            )}
          />
        ) : null}
      </Fact>
      <Fact name="Qué cambió">{asArray(repair.changes).length ? <Bullets items={asArray(repair.changes).map((item) => item.change)} /> : null}</Fact>
      <Fact name="Nota">{repair.note || repair.rationale || null}</Fact>
      <Fact name="Texto antes de reparar">{repair.original_text ? <T selectable>{repair.original_text}</T> : null}</Fact>
    </Fold>
  );
}

function SourcesFold({ piece }: { piece: PieceDetail }) {
  const citations = asArray(piece.citations);
  const signals = asArray(piece.signals);
  const rows = costRows(asArray(piece.usage));
  const total = rows.reduce((sum, row) => sum + row.usd, 0);
  return (
    <Fold summary="Fuentes y coste">
      <Fact name="Citas del curso">{citations.length ? citations.join(' · ') : null}</Fact>
      <Fact name="Señales de terceros">
        {signals.length ? <Bullets items={signals.map((signal) => `${signal.author || 'Autor desconocido'}${signal.text ? `: ${excerpt(signal.text, 140)}` : ''}`)} /> : null}
      </Fact>
      <View style={styles.fact}>
        <T variant="etiqueta" soft>
          Coste
        </T>
        {rows.length ? (
          <View>
            {rows.map((row) => (
              <View key={row.label} style={styles.cost}>
                <T>{row.label}</T>
                <T>{formatUsd(row.usd)}</T>
              </View>
            ))}
            <View style={[styles.cost, styles.total]}>
              <T>Total</T>
              <T>{formatUsd(total)}</T>
            </View>
          </View>
        ) : (
          <T variant="detalle" soft>
            Sin dato de coste.
          </T>
        )}
      </View>
      {!citations.length && !signals.length ? (
        <T variant="detalle" soft>
          Sin citas ni señales registradas.
        </T>
      ) : null}
    </Fold>
  );
}

export function ComoSeEscribio({ piece }: { piece: PieceDetail }) {
  const finished = FINISHED_STATUSES.has(piece.status);
  return (
    <Section label="Cómo se escribió">
      <View>
        <BriefFold piece={piece} finished={finished} />
        <VariantsFold piece={piece} finished={finished} />
        <PanelFold piece={piece} finished={finished} />
        <SelectionFold piece={piece} finished={finished} />
        <VerifierFold piece={piece} finished={finished} />
        <RepairFold piece={piece} />
        <SourcesFold piece={piece} />
      </View>
    </Section>
  );
}

const styles = StyleSheet.create({
  fact: { gap: 2 },
  bullets: { gap: space[1] },
  bullet: { flexDirection: 'row', gap: space[2] },
  bulletText: { flex: 1 },
  head: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: space[2] },
  headText: { flex: 1 },
  variants: { gap: space[3] },
  reader: { flexDirection: 'row', alignItems: 'flex-start', gap: space[2], paddingVertical: space[2], borderTopWidth: 1, borderTopColor: colors.line },
  readerText: { flex: 1, gap: 2 },
  verdict: { flexDirection: 'row', alignItems: 'center', gap: space[2] },
  cost: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: space[1] },
  total: { borderTopWidth: 1, borderTopColor: colors.line, marginTop: space[1] },
});
