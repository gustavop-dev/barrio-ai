import { Component, type ErrorInfo, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import type { Kpi, Resultados } from '../../api/types';
import { Avatar, Button, EmptyState, ErrorRetry, Funnel, KpiCard, LabelChip } from '../../components/ui';
import { CONTACT_ROLE_LABEL, contactStageLabel, formatNumber, formatPct, formatUsd } from '../../lib/format';
import { MODALITY_SHORT, relativeDay, shortDate } from '../personas/labels';
import { BarList, ChartCard, ImpressionsChart, InfoToggle, ModalitySplit } from './charts';
import { pillarLabel, PostsTable } from './PostsTable';
import { readNegocio, type NegocioOn } from './types';

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

function withPeriod(text: string): string {
  const clean = text.trim();
  return /[.!?…]$/.test(clean) ? clean : `${clean}.`;
}

// ---------------------------------------------------------------- 1 · negocio

function ActiveOpportunities({ items }: { items: NegocioOn['activas'] }) {
  return (
    <ChartCard title="Oportunidades activas" definition="Las 5 que se movieron más recientemente, sin las cerradas. Cada una lleva a su ficha en Personas.">
      {items.length ? (
        <ul className="res-activas">
          {items.map((item) => {
            const next = [item.next_action, relativeDay(item.next_action_at)].filter(Boolean).join(' · ');
            return (
              <li key={item.id}>
                <Link to={item.contact_id ? `/personas/${encodeURIComponent(item.contact_id)}` : '/personas?pestana=oportunidades'} className="res-activa">
                  <Avatar name={item.person} />
                  <span className="res-activa-body">
                    <span className="res-activa-name">{item.person || 'Sin nombre'}</span>
                    {item.company ? <span className="res-muted">{item.company}</span> : null}
                    <span className="res-chips">
                      <LabelChip tone="muted">{MODALITY_SHORT[item.modality] ?? item.modality}</LabelChip>
                      <LabelChip tone="ok">{item.stage_label}</LabelChip>
                    </span>
                    {next ? <span className="res-activa-next">Siguiente: {next}</span> : null}
                  </span>
                </Link>
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="res-muted">No hay oportunidades activas ahora mismo.</p>
      )}
    </ChartCard>
  );
}

export function Negocio({ data, onRegister }: { data: Resultados['negocio']; onRegister: () => void }) {
  const negocio = readNegocio(data);
  if (!negocio.disponible) {
    return (
      <div className="res-stack">
        <div className="res-card res-pending">
          <EmptyState
            align="start"
            title={withPeriod(negocio.motivo || 'Mediremos oportunidades cuando registres la primera o conectemos el inbox')}
            action={
              <Button block onClick={onRegister}>
                Registrar una oportunidad
              </Button>
            }
          />
        </div>
        <div className="kpi-grid">
          <KpiCard label="Inbound" kpi={negocio.inbound} />
        </div>
      </div>
    );
  }
  const steps = negocio.embudo?.steps ?? [];
  return (
    <div className="res-stack">
      <div className="kpi-grid">
        <KpiCard label="Conversaciones pertinentes" kpi={negocio.conversaciones} missingText="Disponible cuando conectemos el inbox." />
        <KpiCard label="Oportunidades abiertas" kpi={negocio.abiertas} />
        <KpiCard label="Reuniones" kpi={negocio.reuniones} />
        <KpiCard label="Propuestas enviadas" kpi={negocio.propuestas} />
        <KpiCard label="Acuerdos" kpi={negocio.acuerdos} />
        <KpiCard label="Inbound" kpi={negocio.inbound} />
      </div>
      <div className="res-charts">
        <ChartCard title="Embudo de oportunidades" definition={negocio.embudo?.definition}>
          <Funnel
            steps={steps.map((step) => ({ key: step.stage, label: step.label, value: step.count }))}
            aside={`Cerrada sin acuerdo: ${formatNumber(negocio.embudo?.sin_acuerdo ?? 0)}`}
          />
        </ChartCard>
        <ChartCard title="Reparto por modalidad" definition={negocio.modalidades?.definition}>
          <ModalitySplit data={negocio.modalidades} />
        </ChartCard>
      </div>
      <ActiveOpportunities items={negocio.activas ?? []} />
    </div>
  );
}

// ---------------------------------------------------------------- 2 · gente

const ROLE_ORDER = ['comprador', 'par', 'recomendador', 'divulgador', 'lider', 'aliado'];
const ASIDE_LABEL: Record<string, string> = { discarded: 'Descartados', closed: 'Cerrados', incoming: 'Te invitaron' };

export function Gente({ data }: { data: Resultados['audiencia'] }) {
  const roles = data.roles;
  const roleItems = roles?.items
    ? [...roles.items].sort((a, b) => {
        const ia = ROLE_ORDER.indexOf(a.role);
        const ib = ROLE_ORDER.indexOf(b.role);
        return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
      })
    : null;
  const funnel = data.funnel;
  const top = data.recurrent_people?.top ?? [];
  return (
    <div className="res-stack">
      <div className="kpi-grid">
        <KpiCard label="Seguidores" kpi={data.followers} />
        <KpiCard label="Conexiones" kpi={data.connections} />
        <KpiCard label="Visitas al perfil" kpi={data.profile_views} />
        <KpiCard label="Conexiones nuevas que encajan" kpi={data.new_fit_connections} />
        <KpiCard label="Tasa de aceptación" kpi={data.acceptance_rate} unit="percent" />
        <KpiCard label="Personas recurrentes" kpi={data.recurrent_people} />
      </div>
      <div className="res-charts">
        <ChartCard title="Conexiones nuevas que encajan, por rol" definition={roles?.definition}>
          {roleItems ? (
            <Funnel
              steps={roleItems.map((item) => ({ key: item.role, label: CONTACT_ROLE_LABEL[item.role] ?? (item.role === 'sin_rol' ? 'Sin rol' : item.role), value: item.value }))}
              showConversion={false}
              color="var(--color-azul-sprite)"
            />
          ) : (
            <p className="res-muted">
              <span aria-hidden="true">— </span>
              {roles?.unavailable_reason ?? 'Sin dato en este periodo.'}
            </p>
          )}
        </ChartCard>
        <ChartCard title="Embudo de la red" definition={funnel?.definition}>
          <Funnel
            steps={(funnel?.order ?? []).map((stage) => ({ key: stage, label: contactStageLabel(stage), value: funnel.stages[stage] ?? 0 }))}
            color="var(--color-azul-sprite)"
            aside={(funnel?.aside ?? []).map((stage) => `${ASIDE_LABEL[stage] ?? contactStageLabel(stage)}: ${formatNumber(funnel.stages[stage] ?? 0)}`).join(' · ')}
          />
        </ChartCard>
      </div>
      {top.length ? (
        <ChartCard title="Personas recurrentes" definition={data.recurrent_people.definition}>
          <ul className="res-top">
            {top.slice(0, 5).map((person, index) => {
              const count = person.interactions ?? person.count;
              const id = person.contact_id ?? person.id;
              const label = `${person.name}${typeof count === 'number' ? ` · ${count} interacciones` : ''}`;
              return <li key={id ?? `${person.name}-${index}`}>{id ? <Link to={`/personas/${encodeURIComponent(id)}`}>{label}</Link> : label}</li>;
            })}
          </ul>
        </ChartCard>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------- 3 · contenido

/** «24 de 28» when the ratio brings its parts. */
function consistencyFormat(kpi: Kpi | undefined) {
  if (kpi && typeof kpi.numerator === 'number' && typeof kpi.denominator === 'number') {
    const { numerator, denominator } = kpi;
    return () => `${formatNumber(numerator)} de ${formatNumber(denominator)}`;
  }
  return undefined;
}

export function Contenido({ data }: { data: Resultados['contenido'] }) {
  const kpis = data.kpis;
  const cut = kpis?.median_impressions?.cut ?? data.by_pillar?.cut ?? null;
  const best = data.best_post;
  // Highest engagement first; pillars without data last.
  const pillars = [...(data.by_pillar?.items ?? [])].sort((a, b) => (b.value ?? -1) - (a.value ?? -1));
  return (
    <div className="res-stack">
      <div className="kpi-grid">
        <KpiCard label="Impresiones" kpi={kpis.median_impressions} deltaAsPercent />
        <KpiCard label="Interacción" kpi={kpis.engagement_pct} unit="percent" />
        <KpiCard label="Comentarios con sustancia" kpi={kpis.substantive_comments} />
        <KpiCard label="Constancia" kpi={kpis.consistency} unit="percent" format={consistencyFormat(kpis.consistency)} />
      </div>
      <ImpressionsChart chart={data.chart} cut={cut} />
      <div className="res-charts">
        <ChartCard title="Mejor post del periodo" className="res-best">
          {best ? (
            <>
              <p className="res-best-text">{best.first_line || 'Pieza sin texto'}</p>
              <p className="res-muted">
                {[
                  shortDate(best.date),
                  best.pillar ? pillarLabel(best.pillar) : '',
                  best.impressions !== null ? `${formatNumber(best.impressions)} impresiones` : '',
                  best.engagement_pct !== null ? formatPct(best.engagement_pct) : '',
                ]
                  .filter(Boolean)
                  .join(' · ')}
              </p>
              <Link to={`/calendario/pieza/${encodeURIComponent(best.piece_id)}`} className="res-link">
                Ver la pieza
              </Link>
            </>
          ) : (
            <p className="res-muted">Aún ningún post del periodo tiene su corte de impresiones.</p>
          )}
        </ChartCard>
        <ChartCard title="Interacción media por pilar" formula={data.by_pillar?.formula}>
          {pillars.length ? (
            <BarList
              label="Interacción media por pilar"
              items={pillars.map((item) => ({
                key: item.pillar,
                label: (
                  <>
                    {pillarLabel(item.pillar)}
                    <span className="res-muted"> · {item.posts} {item.posts === 1 ? 'post' : 'posts'}</span>
                  </>
                ),
                value: item.value,
                display: item.value === null ? undefined : formatPct(item.value),
              }))}
            />
          ) : (
            <p className="res-muted">Sin posts con corte en el periodo.</p>
          )}
        </ChartCard>
      </div>
      <div className="res-subsection">
        <h3 className="res-card-title">Posts del periodo</h3>
        <PostsTable posts={data.posts ?? []} />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- 4 · equipo

function Value({ kpi, one, many }: { kpi: Kpi | undefined; one: string; many: string }) {
  const value = kpi?.value;
  if (value === null || value === undefined) {
    return (
      <span>
        <span aria-hidden="true">—</span>
        <span className="vh">sin dato de</span> {many}
      </span>
    );
  }
  return (
    <span>
      {formatNumber(value)} {value === 1 ? one : many}
    </span>
  );
}

function Definitions({ items }: { items: [string, Kpi | undefined][] }) {
  return (
    <ul className="res-deflist">
      {items
        .filter(([, kpi]) => kpi?.definition)
        .map(([label, kpi]) => (
          <li key={label}>
            {label}: {kpi?.definition}
            {kpi?.value === null && kpi.unavailable_reason ? ` ${kpi.unavailable_reason}` : ''}
          </li>
        ))}
    </ul>
  );
}

function Stat({ label, definition, children }: { label: string; definition?: ReactNode; children: ReactNode }) {
  return (
    <div className="res-stat">
      <div className="res-card-head">
        <p className="res-muted">{label}</p>
        <InfoToggle label={label} definition={definition} />
      </div>
      <p className="res-stat-value">{children}</p>
    </div>
  );
}

/** «3,10»: money with two decimals, without the unit. */
function amount(value: number): string {
  return value.toLocaleString('es-CO', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function sum(values: (number | null | undefined)[]): number {
  return values.reduce<number>((total, value) => total + (typeof value === 'number' ? value : 0), 0);
}

export function Equipo({ data }: { data: Resultados['equipo'] }) {
  const spend = data.spend;
  const today = Object.values(spend?.today ?? {});
  const todaySpent = sum(today.map((line) => line.spent));
  const todayBudget = sum(today.map((line) => line.budget));
  const month = (spend?.month as Record<string, { spent: number; budget: number | null }> | undefined)?.total?.spent ?? null;
  return (
    <div className="res-stats-row">
      <Stat
        label="Comentarios"
        definition={
          <Definitions
            items={[
              ['Publicados', data.comments_published],
              ['Con respuesta', data.comments_replied],
            ]}
          />
        }
      >
        <Value kpi={data.comments_published} one="publicado" many="publicados" /> · <Value kpi={data.comments_replied} one="con respuesta" many="con respuesta" />
      </Stat>
      <Stat
        label="Red"
        definition={
          <Definitions
            items={[
              ['Seguidos', data.follows],
              ['Invitados', data.invites],
              ['Aceptados', data.accepts],
            ]}
          />
        }
      >
        <Value kpi={data.follows} one="seguido" many="seguidos" /> · <Value kpi={data.invites} one="invitado" many="invitados" /> ·{' '}
        <Value kpi={data.accepts} one="aceptado" many="aceptados" />
      </Stat>
      <Stat
        label="Piezas"
        definition={
          <Definitions
            items={[
              ['Publicadas', data.pieces_published],
              ['Bloqueadas', data.pieces_blocked],
              ['Vetadas', data.pieces_vetoed],
            ]}
          />
        }
      >
        <Value kpi={data.pieces_published} one="publicada" many="publicadas" /> · <Value kpi={data.pieces_blocked} one="bloqueada" many="bloqueadas" /> ·{' '}
        <Value kpi={data.pieces_vetoed} one="vetada" many="vetadas" />
      </Stat>
      <Stat label="Gasto de IA" definition={spend?.definition}>
        {spend ? (
          <>
            {todayBudget > 0 ? `${amount(todaySpent)} de ${formatUsd(todayBudget)} hoy` : `${formatUsd(todaySpent)} hoy`}
            {month !== null ? <span className="res-stat-sub">{formatUsd(month)} este mes</span> : null}
          </>
        ) : (
          <>
            <span aria-hidden="true">—</span>
            <span className="vh">sin dato</span>
          </>
        )}
      </Stat>
    </div>
  );
}
