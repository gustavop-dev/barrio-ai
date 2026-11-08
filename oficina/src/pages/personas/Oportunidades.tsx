import { useQueryClient } from '@tanstack/react-query';
import { useState, type DragEvent } from 'react';
import { Link } from 'react-router-dom';
import { useUpdateOportunidad } from '../../api/hooks';
import type { Opportunity, OpportunityStage } from '../../api/types';
import { OPPORTUNITY_STAGES } from '../../api/types';
import { IconChevronDown, IconPlus } from '../../components/icons';
import { Avatar, Badge, Button, EmptyState, ErrorRetry, Skeleton, useToast } from '../../components/ui';
import { nextActionText, undoFailedToast } from '../../../../compartido/src/logic/barrio';
import { OPPORTUNITY_BOARD_KEY, useOpportunityBoard } from './api';
import { BOARD_STAGES, daysInStage, longDate, MODALITY_SHORT, OPPORTUNITY_STAGE_LABEL } from './labels';
import { OportunidadForm } from './OportunidadForm';
import { useMediaQuery, WIDE } from './useMediaQuery';

const BOARD_KEY = OPPORTUNITY_BOARD_KEY;

function PersonName({ opportunity }: { opportunity: Opportunity }) {
  const name = opportunity.person || opportunity.person_name || 'Sin nombre';
  if (opportunity.contact) {
    return (
      <Link className="opp-name" to={`/personas/${encodeURIComponent(opportunity.contact.id)}`}>
        {name}
      </Link>
    );
  }
  return <span className="opp-name plain">{name}</span>;
}

interface CardProps {
  opportunity: Opportunity;
  onMove: (opportunity: Opportunity, stage: OpportunityStage) => void;
  onEdit: (opportunity: Opportunity) => void;
  draggable?: boolean;
}

function OpportunityCard({ opportunity, onMove, onEdit, draggable = false }: CardProps) {
  const next = nextActionText(opportunity);
  const name = opportunity.person || opportunity.person_name || 'Sin nombre';
  return (
    <article
      className="opp-card"
      draggable={draggable || undefined}
      onDragStart={
        draggable
          ? (event: DragEvent) => {
              event.dataTransfer.setData('text/plain', opportunity.id);
              event.dataTransfer.effectAllowed = 'move';
            }
          : undefined
      }
      aria-label={`${name}, ${OPPORTUNITY_STAGE_LABEL[opportunity.stage]}`}
    >
      <div className="opp-card-head">
        <Avatar name={name} />
        <div className="opp-card-who">
          <PersonName opportunity={opportunity} />
          {opportunity.company ? <p className="opp-sub">{opportunity.company}</p> : null}
        </div>
        <Badge tone="muted">{MODALITY_SHORT[opportunity.modality] ?? opportunity.modality}</Badge>
      </div>
      {next ? (
        <div className="opp-next">
          <p className="opp-label">Siguiente acción</p>
          <p>{next}</p>
        </div>
      ) : null}
      {daysInStage(opportunity.days_in_stage) ? <p className="opp-sub">{daysInStage(opportunity.days_in_stage)}</p> : null}
      <label className="opp-stage">
        <span>
          Etapa <span className="vh">de {name}</span>
        </span>
        <select value={opportunity.stage} onChange={(event) => onMove(opportunity, event.target.value as OpportunityStage)}>
          {OPPORTUNITY_STAGES.map((stage) => (
            <option key={stage} value={stage}>
              {OPPORTUNITY_STAGE_LABEL[stage]}
            </option>
          ))}
        </select>
      </label>
      <Button variant="ghost" size="small" className="opp-edit" onClick={() => onEdit(opportunity)}>
        Editar <span className="vh">la oportunidad con {name}</span>
      </Button>
    </article>
  );
}

function ClosedList({ items, onEdit }: { items: Opportunity[]; onEdit: (opportunity: Opportunity) => void }) {
  if (!items.length) return null;
  return (
    <details className="opp-closed">
      <summary>
        Cerradas sin acuerdo · {items.length}
        <IconChevronDown size={20} />
      </summary>
      <ul className="opp-closed-list">
        {items.map((opportunity) => {
          const name = opportunity.person || opportunity.person_name || 'Sin nombre';
          const meta = [opportunity.company, MODALITY_SHORT[opportunity.modality], opportunity.closed_at ? `cerrada el ${longDate(opportunity.closed_at)}` : '']
            .filter(Boolean)
            .join(' · ');
          return (
            <li key={opportunity.id} className="opp-closed-row">
              <Avatar name={name} />
              <div className="opp-card-who">
                <PersonName opportunity={opportunity} />
                {meta ? <p className="opp-sub">{meta}</p> : null}
              </div>
              <Button variant="ghost" size="small" onClick={() => onEdit(opportunity)}>
                Editar <span className="vh">la oportunidad con {name}</span>
              </Button>
            </li>
          );
        })}
      </ul>
    </details>
  );
}

/** Personas → Oportunidades: a stage board on desktop, a list grouped by stage on mobile. */
export function Oportunidades() {
  const wide = useMediaQuery(WIDE);
  const board = useOpportunityBoard();
  const update = useUpdateOportunidad();
  const client = useQueryClient();
  const toast = useToast();
  const [form, setForm] = useState<{ opportunity: Opportunity | null } | null>(null);
  const [dropTarget, setDropTarget] = useState<OpportunityStage | null>(null);

  const setStageLocally = (id: string, stage: OpportunityStage) => {
    client.setQueryData<Opportunity[]>(BOARD_KEY, (list) => list?.map((item) => (item.id === id ? { ...item, stage, days_in_stage: 0 } : item)));
  };

  const move = (opportunity: Opportunity, stage: OpportunityStage) => {
    if (stage === opportunity.stage) return;
    const previous = opportunity.stage;
    setStageLocally(opportunity.id, stage);
    update.mutate(
      { opportunityId: opportunity.id, patch: { stage } },
      {
        onSuccess: () =>
          toast.show(`Movida a «${OPPORTUNITY_STAGE_LABEL[stage]}»`, {
            undo: () => {
              setStageLocally(opportunity.id, previous);
              update.mutate(
                { opportunityId: opportunity.id, patch: { stage: previous } },
                {
                  // The undo failed: the card goes back to where the server still has it, and Gustavo is told.
                  onError: () => {
                    setStageLocally(opportunity.id, stage);
                    toast.show(undoFailedToast(stage), { tone: 'error' });
                  },
                },
              );
            },
          }),
        onError: () => {
          setStageLocally(opportunity.id, previous);
          toast.show('No se pudo cambiar la etapa', { tone: 'error' });
        },
      },
    );
  };

  const edit = (opportunity: Opportunity) => setForm({ opportunity });
  const items = board.data ?? [];
  const byStage = (stage: OpportunityStage) => items.filter((item) => item.stage === stage);
  const closed = byStage('sin_acuerdo');

  const drop = (stage: OpportunityStage) => (event: DragEvent) => {
    event.preventDefault();
    setDropTarget(null);
    const id = event.dataTransfer.getData('text/plain');
    const opportunity = items.find((item) => item.id === id);
    if (opportunity) move(opportunity, stage);
  };

  return (
    <div className="oportunidades">
      <Button variant="primary" block className="opp-new" icon={<IconPlus size={20} />} onClick={() => setForm({ opportunity: null })}>
        Nueva oportunidad
      </Button>
      {board.isPending ? <Skeleton variant="card" count={2} label="Cargando oportunidades…" /> : null}
      <ErrorRetry error={board.error} onRetry={() => void board.refetch()} />
      {board.isSuccess && !items.length ? (
        <EmptyState title="Aún no hay oportunidades">
          Regístrala cuando una conversación tenga una necesidad real. Así Resultados empieza a medir el negocio.
        </EmptyState>
      ) : null}

      {items.length && wide ? (
        <div className="opp-board" role="list" aria-label="Tablero de oportunidades por etapa">
          {BOARD_STAGES.map((stage) => {
            const column = byStage(stage);
            return (
              <section
                key={stage}
                role="listitem"
                className={dropTarget === stage ? 'opp-column droptarget' : 'opp-column'}
                aria-label={`${OPPORTUNITY_STAGE_LABEL[stage]}: ${column.length}`}
                onDragOver={(event) => {
                  event.preventDefault();
                  event.dataTransfer.dropEffect = 'move';
                  if (dropTarget !== stage) setDropTarget(stage);
                }}
                onDragLeave={() => setDropTarget((current) => (current === stage ? null : current))}
                onDrop={drop(stage)}
              >
                <h3 className="opp-label">
                  {OPPORTUNITY_STAGE_LABEL[stage]} · {column.length}
                </h3>
                {column.map((opportunity) => (
                  <OpportunityCard key={opportunity.id} opportunity={opportunity} onMove={move} onEdit={edit} draggable />
                ))}
              </section>
            );
          })}
        </div>
      ) : null}

      {items.length && !wide
        ? [...BOARD_STAGES].reverse().map((stage) => {
            const group = byStage(stage);
            if (!group.length) return null;
            return (
              <section key={stage} className="opp-group" aria-label={`${OPPORTUNITY_STAGE_LABEL[stage]}: ${group.length}`}>
                <h3 className="opp-label">
                  {OPPORTUNITY_STAGE_LABEL[stage]} · {group.length}
                </h3>
                {group.map((opportunity) => (
                  <OpportunityCard key={opportunity.id} opportunity={opportunity} onMove={move} onEdit={edit} />
                ))}
              </section>
            );
          })
        : null}

      <ClosedList items={closed} onEdit={edit} />

      {form ? <OportunidadForm opportunity={form.opportunity} onClose={() => setForm(null)} /> : null}
    </div>
  );
}
