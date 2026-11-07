import { useState } from 'react';
import { usePlanPiece, useVeto } from '../../api/hooks';
import { Button, ConfirmModal, Note, useToast } from '../../components/ui';
import { longDay } from './dates';

export interface VetoTarget {
  /** The action to reject: the piece's CONT-09 or a queued action. */
  actionId: string;
  kind: 'pieza' | 'accion';
  /** «a las 09:00»: when the piece would go out. */
  when?: string;
  /** A network action (RED-*): vetoing it discards the person for good. */
  network?: boolean;
  person?: string | null;
}

function consequence(target: VetoTarget): string {
  if (target.kind === 'pieza') return `La pieza no saldrá${target.when ? ` ${target.when}` : ''} y ese día quedará sin publicación. Queda registrada con tu nota.`;
  if (target.network) return `No saldrá, y vetar una acción de red descarta a ${target.person || 'esa persona'} para siempre: el equipo no la volverá a proponer.`;
  return 'La acción no saldrá. Queda registrada con tu nota.';
}

/** «Vetar» with the mandatory-note modal (POST /operador/actions/<id>/reject). */
export function VetoButton({
  target,
  block = false,
  size,
  describedBy,
}: {
  target: VetoTarget;
  block?: boolean;
  size?: 'normal' | 'small';
  describedBy?: string;
}) {
  const [open, setOpen] = useState(false);
  const veto = useVeto();
  const toast = useToast();
  const close = () => {
    setOpen(false);
    veto.reset();
  };
  return (
    <>
      <Button variant="danger" block={block} size={size} aria-describedby={describedBy} onClick={() => setOpen(true)}>
        Vetar
      </Button>
      {open ? (
        <ConfirmModal
          title={target.kind === 'pieza' ? 'Vetar la pieza' : 'Vetar la acción'}
          tone="danger"
          note="required"
          noteLabel="Nota"
          notePlaceholder="Por qué no debe salir"
          confirmLabel="Vetar"
          busy={veto.isPending}
          error={veto.error}
          onClose={close}
          onConfirm={(note) =>
            veto.mutate(
              { actionId: target.actionId, note },
              {
                onSuccess: () => {
                  setOpen(false);
                  toast.show('Vetada');
                },
              },
            )
          }
        >
          <p>{consequence(target)}</p>
        </ConfirmModal>
      ) : null}
    </>
  );
}

function newRequestId(): string | undefined {
  try {
    return typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function' ? crypto.randomUUID() : undefined;
  } catch {
    return undefined;
  }
}

/** «Preparar la siguiente pieza» behind the cost confirmation (POST /editorial/plan). */
export function PlanNextButton({ block = false }: { block?: boolean }) {
  const plan = usePlanPiece();
  const [asking, setAsking] = useState(false);
  // One id per intent: a retry after a network error never queues a second preparation.
  const [requestId, setRequestId] = useState<string | undefined>(undefined);
  const open = () => {
    plan.reset();
    setRequestId(newRequestId());
    setAsking(true);
  };
  return (
    <>
      <Button variant="secondary" block={block} onClick={open} disabled={plan.isPending}>
        Preparar la siguiente pieza
      </Button>
      {plan.isSuccess ? (
        <Note tone="ok">
          Preparación en cola para el {longDay(plan.data.slot_date)}. El circuito tarda unos minutos y la pieza aparecerá en el calendario.
        </Note>
      ) : null}
      {asking ? (
        <ConfirmModal
          title="Preparar la siguiente pieza"
          confirmLabel="Preparar"
          busy={plan.isPending}
          error={plan.error}
          onClose={() => setAsking(false)}
          onConfirm={() =>
            plan.mutate(requestId, { onSuccess: () => setAsking(false) })
          }
        >
          <p>
            Pone en cola el circuito editorial para el próximo día libre (como mucho a siete días): director, dos redactores, panel de lectores,
            selección y verificador.
          </p>
          <Note tone="warn" role={null}>
            Tiene coste: cada etapa llama a Claude y gasta del presupuesto editorial. Si la pieza pasa el verificador, saldrá sola a su hora salvo
            que la vetes.
          </Note>
        </ConfirmModal>
      ) : null}
    </>
  );
}
