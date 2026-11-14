// The four blocks of Resultados («¿vamos bien?»): business, audience, content and team, each behind its own
// error boundary so a section that arrives broken shows its error while the others draw.
import {
  activeLink,
  activeNext,
  bestPostMeta,
  consistencyFormat,
  contenidoCut,
  definitionLines,
  NEGOCIO_PENDING_TEXT,
  networkFunnelAside,
  networkFunnelSteps,
  pillarLabel,
  postsCount,
  readNegocio,
  recurrentTop,
  roleSteps,
  sortPillars,
  spendSummary,
  teamCount,
  withPeriod,
  type NegocioOn,
} from '@compartido/logic/resultados';
import { GASP_LABEL } from '@compartido/api/estrategia';
import { formatNumber, formatPct } from '@compartido/logic/format';
import { MODALITY_SHORT } from '@compartido/logic/personas';
import type { Kpi, Resultados } from '@compartido/api/types';
import { router } from 'expo-router';
import { Component, type ErrorInfo, type ReactNode } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { Icon } from '@/components/icons';
import { Avatar, Button, Card, EmptyState, ErrorRetry, LabelChip, T } from '@/components/ui';
import { openLink } from '@/navigation';
import { colors, radius, space } from '@/theme/tokens';
import { BarList, ChartCard, Funnel, ImpressionsChart, InfoButton, KpiGrid, KpiTile, ModalitySplit } from './charts';

// ---------------------------------------------------------------- per-section errors

interface BoundaryProps {
  onRetry: () => void;
  children: ReactNode;
}

/** If one section cannot be drawn (an unexpected payload), only that section shows the error. */
export class SectionBoundary extends Component<BoundaryProps, { error: Error | null }> {
  override state: { error: Error | null } = { error: null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  override componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Resultados: no se pudo pintar una sección', error, info.componentStack);
  }

  override render() {
    if (this.state.error) {
      return (
        <ErrorRetry
          title="No se pudo mostrar esta sección"
          error={new Error('Los datos de esta sección llegaron con una forma inesperada.')}
          onRetry={() => {
            this.setState({ error: null });
            this.props.onRetry();
          }}
        />
      );
    }
    return this.props.children;
  }
}

function Muted({ children }: { children: ReactNode }) {
  return (
    <T variant="detalle" soft>
      {children}
    </T>
  );
}

/** A row that opens another screen: the whole row is the target, with a chevron. */
function LinkRow({ onPress, children, label }: { onPress: () => void; children: ReactNode; label?: string }) {
  return (
    <Pressable accessibilityRole="link" accessibilityLabel={label} onPress={onPress} style={({ pressed }) => [styles.linkRow, pressed ? styles.pressed : null]}>
      {children}
      <Icon name="chevronRight" size={20} color={colors.inkSoft} />
    </Pressable>
  );
}

function openPerson(contactId: string) {
  router.push({ pathname: '/personas/[id]', params: { id: contactId } });
}

function openPiece(pieceId: string) {
  router.push({ pathname: '/calendario/pieza/[id]', params: { id: pieceId } });
}

// ---------------------------------------------------------------- 1 · negocio

function ActiveOpportunities({ items }: { items: NegocioOn['activas'] }) {
  return (
    <ChartCard title="Oportunidades activas" definition="Las 5 que se movieron más recientemente, sin las cerradas. Cada una lleva a su ficha en Personas.">
      {items.length ? (
        <View style={styles.list}>
          {items.map((item) => {
            const next = activeNext(item);
            return (
              <LinkRow key={item.id} onPress={() => openLink(activeLink(item))}>
                <Avatar name={item.person} />
                <View style={styles.grow}>
                  <T>{item.person || 'Sin nombre'}</T>
                  {item.company ? <Muted>{item.company}</Muted> : null}
                  <View style={styles.chips}>
                    <LabelChip tone="muted">{MODALITY_SHORT[item.modality] ?? item.modality}</LabelChip>
                    <LabelChip tone="ok">{item.stage_label}</LabelChip>
                  </View>
                  {next ? <T variant="detalle">Siguiente: {next}</T> : null}
                </View>
              </LinkRow>
            );
          })}
        </View>
      ) : (
        <Muted>No hay oportunidades activas ahora mismo.</Muted>
      )}
    </ChartCard>
  );
}

export function Negocio({ data, onRegister }: { data: Resultados['negocio']; onRegister: () => void }) {
  const negocio = readNegocio(data);
  if (!negocio.disponible) {
    return (
      <View style={styles.stack}>
        <Card>
          <EmptyState
            title={withPeriod(negocio.motivo || NEGOCIO_PENDING_TEXT)}
            action={
              <Button block onPress={onRegister}>
                Registrar una oportunidad
              </Button>
            }
          />
        </Card>
        <KpiGrid>
          <KpiTile label="Inbound" kpi={negocio.inbound} />
        </KpiGrid>
      </View>
    );
  }
  const steps = negocio.embudo?.steps ?? [];
  return (
    <View style={styles.stack}>
      <KpiGrid>
        <KpiTile label="Conversaciones pertinentes" kpi={negocio.conversaciones} missingText="Disponible cuando conectemos el inbox." />
        <KpiTile label="Oportunidades abiertas" kpi={negocio.abiertas} />
        <KpiTile label="Reuniones" kpi={negocio.reuniones} />
        <KpiTile label="Propuestas enviadas" kpi={negocio.propuestas} />
        <KpiTile label="Acuerdos" kpi={negocio.acuerdos} />
        <KpiTile label="Inbound" kpi={negocio.inbound} />
      </KpiGrid>
      <ChartCard title="Embudo de oportunidades" definition={negocio.embudo?.definition}>
        <Funnel
          steps={steps.map((step) => ({ key: step.stage, label: step.label, value: step.count }))}
          aside={`Cerrada sin acuerdo: ${formatNumber(negocio.embudo?.sin_acuerdo ?? 0)}`}
        />
      </ChartCard>
      <ChartCard title="Reparto por modalidad" definition={negocio.modalidades?.definition}>
        <ModalitySplit data={negocio.modalidades} />
      </ChartCard>
      <ActiveOpportunities items={negocio.activas ?? []} />
    </View>
  );
}

// ---------------------------------------------------------------- 2 · gente

export function Gente({ data }: { data: Resultados['audiencia'] }) {
  const roles = data.roles;
  const roleItems = roleSteps(roles?.items);
  const top = recurrentTop(data.recurrent_people);
  return (
    <View style={styles.stack}>
      <KpiGrid>
        <KpiTile label="Seguidores" kpi={data.followers} />
        <KpiTile label="Conexiones" kpi={data.connections} />
        <KpiTile label="Visitas al perfil" kpi={data.profile_views} />
        <KpiTile label="Conexiones nuevas que encajan" kpi={data.new_fit_connections} />
        <KpiTile label="Tasa de aceptación" kpi={data.acceptance_rate} unit="percent" />
        <KpiTile label="Personas recurrentes" kpi={data.recurrent_people} />
      </KpiGrid>
      <ChartCard title="Conexiones nuevas que encajan, por rol" definition={roles?.definition}>
        {roleItems ? <Funnel steps={roleItems} showConversion={false} color={colors.spriteBlue} /> : <Muted>— {roles?.unavailable_reason ?? 'Sin dato en este periodo.'}</Muted>}
      </ChartCard>
      <ChartCard title="Embudo de la red" definition={data.funnel?.definition}>
        <Funnel steps={networkFunnelSteps(data.funnel)} color={colors.spriteBlue} aside={networkFunnelAside(data.funnel)} />
      </ChartCard>
      {top.length ? (
        <ChartCard title="Personas recurrentes" definition={data.recurrent_people.definition}>
          <View style={styles.list}>
            {top.map((person) =>
              person.contactId ? (
                <LinkRow key={person.key} onPress={() => openPerson(person.contactId!)}>
                  <T style={styles.grow}>{person.label}</T>
                </LinkRow>
              ) : (
                <T key={person.key}>{person.label}</T>
              ),
            )}
          </View>
        </ChartCard>
      ) : null}
    </View>
  );
}

// ---------------------------------------------------------------- 3 · contenido

/** «· 2 posts · 1.400 impresiones» after a GASP type. */
function typeSub(item: { posts: number; median_impressions: number | null }): string {
  return `· ${postsCount(item.posts)}${item.median_impressions !== null ? ` · ${formatNumber(item.median_impressions)} impresiones` : ''}`;
}

/** KPIs, the chart, the best post, the pillars and the GASP types; the posts follow as rows of the list. */
export function Contenido({ data }: { data: Resultados['contenido'] }) {
  const kpis = data.kpis;
  const best = data.best_post;
  const pillars = sortPillars(data.by_pillar?.items);
  const types = data.by_type?.items ?? [];
  return (
    <View style={styles.stack}>
      <KpiGrid>
        <KpiTile label="Impresiones" kpi={kpis.median_impressions} deltaAsPercent />
        <KpiTile label="Interacción" kpi={kpis.engagement_pct} unit="percent" />
        <KpiTile label="Comentarios con sustancia" kpi={kpis.substantive_comments} />
        <KpiTile label="Constancia" kpi={kpis.consistency} unit="percent" format={consistencyFormat(kpis.consistency)} />
      </KpiGrid>
      <ImpressionsChart chart={data.chart} cut={contenidoCut(data)} />
      <ChartCard title="Mejor post del periodo">
        {best ? (
          <>
            <T variant="subtitulo">{best.first_line || 'Pieza sin texto'}</T>
            <Muted>{bestPostMeta(best)}</Muted>
            <Button variant="ghost" style={styles.start} onPress={() => openPiece(best.piece_id)}>
              Ver la pieza
            </Button>
          </>
        ) : (
          <Muted>Aún ningún post del periodo tiene su corte de impresiones.</Muted>
        )}
      </ChartCard>
      <ChartCard title="Interacción media por pilar" formula={data.by_pillar?.formula}>
        {pillars.length ? (
          <BarList
            label="Interacción media por pilar"
            items={pillars.map((item) => ({
              key: item.pillar,
              label: pillarLabel(item.pillar),
              sub: `· ${postsCount(item.posts)}`,
              value: item.value,
              display: item.value === null ? undefined : formatPct(item.value),
            }))}
          />
        ) : (
          <Muted>Sin posts con corte en el periodo.</Muted>
        )}
      </ChartCard>
      {types.length ? (
        // The weekly GASP strategy (estrategia.py): hidden until a post of the period carries a type.
        <ChartCard title="Interacción media por tipo de post" formula={data.by_type?.formula}>
          <BarList
            label="Interacción media por tipo de post"
            items={types.map((item) => ({
              key: item.type,
              label: GASP_LABEL[item.type] ?? item.type,
              sub: typeSub(item),
              value: item.value,
              display: item.value === null ? undefined : formatPct(item.value),
            }))}
          />
        </ChartCard>
      ) : null}
    </View>
  );
}

// ---------------------------------------------------------------- 4 · equipo

/** «24 publicados · — con respuesta», read as «… · sin dato de con respuesta». */
function statLine(parts: [Kpi | undefined, string, string][]): { text: string; spoken: string } {
  const values = parts.map(([kpi, one, many]) => ({ value: teamCount(kpi, one, many), many }));
  return {
    text: values.map((part) => part.value ?? `— ${part.many}`).join(' · '),
    spoken: values.map((part) => part.value ?? `sin dato de ${part.many}`).join(' · '),
  };
}

function Stat({ label, definition, text, spoken, sub }: { label: string; definition?: string | readonly string[] | null; text: string; spoken?: string; sub?: string | null }) {
  return (
    <View style={styles.stat} testID={`stat-${label}`}>
      <View style={styles.statHead}>
        <T variant="detalle" soft style={styles.grow}>
          {label}
        </T>
        <InfoButton label={label} definition={definition} />
      </View>
      <T accessibilityLabel={spoken}>{text}</T>
      {sub ? <Muted>{sub}</Muted> : null}
    </View>
  );
}

export function Equipo({ data }: { data: Resultados['equipo'] }) {
  const comments = statLine([
    [data.comments_published, 'publicado', 'publicados'],
    [data.comments_replied, 'con respuesta', 'con respuesta'],
  ]);
  const network = statLine([
    [data.follows, 'seguido', 'seguidos'],
    [data.invites, 'invitado', 'invitados'],
    [data.accepts, 'aceptado', 'aceptados'],
  ]);
  const pieces = statLine([
    [data.pieces_published, 'publicada', 'publicadas'],
    [data.pieces_blocked, 'bloqueada', 'bloqueadas'],
    [data.pieces_vetoed, 'vetada', 'vetadas'],
  ]);
  const spend = spendSummary(data.spend);
  return (
    <KpiGrid>
      <Stat
        label="Comentarios"
        definition={definitionLines([
          ['Publicados', data.comments_published],
          ['Con respuesta', data.comments_replied],
        ])}
        {...comments}
      />
      <Stat
        label="Red"
        definition={definitionLines([
          ['Seguidos', data.follows],
          ['Invitados', data.invites],
          ['Aceptados', data.accepts],
        ])}
        {...network}
      />
      <Stat
        label="Piezas"
        definition={definitionLines([
          ['Publicadas', data.pieces_published],
          ['Bloqueadas', data.pieces_blocked],
          ['Vetadas', data.pieces_vetoed],
        ])}
        {...pieces}
      />
      <Stat label="Gasto de IA" definition={data.spend?.definition} text={spend ? spend.today : '—'} spoken={spend ? undefined : 'Sin dato'} sub={spend?.month} />
    </KpiGrid>
  );
}

const styles = StyleSheet.create({
  stack: { gap: space[3] },
  list: { gap: space[1] },
  grow: { flex: 1, gap: 2 },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: space[1], marginTop: 2 },
  linkRow: { minHeight: 48, flexDirection: 'row', alignItems: 'center', gap: space[3], paddingVertical: space[2], borderRadius: radius.sm },
  pressed: { backgroundColor: colors.paper },
  start: { alignSelf: 'flex-start' },
  stat: { flex: 1, padding: space[3], gap: space[1], backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.line, borderRadius: radius.md },
  statHead: { flexDirection: 'row', alignItems: 'center', gap: space[2] },
});
