// «Vetar» (the confirm sheet with its mandatory note, then «Vetada» with «Deshacer» for 5 s: the reject
// waits that window in pendingVeto.ts) and «Preparar la siguiente pieza» behind the cost confirmation.
import { usePlanPiece } from '@compartido/api/hooks';
import { longDay } from '@compartido/logic/dates';
import { vetoConsequence, type VetoTarget } from '@compartido/logic/events';
import { useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { Button, ConfirmSheet, Note, T, errorMessage, useToast } from '@/components/ui';
import { haptic } from '@/theme/motion';
import { space } from '@/theme/tokens';
import { scheduleVeto, usePendingVeto } from './pendingVeto';

export type { VetoTarget };

export function VetoButton({ target, block = false, size, accessibilityHint }: { target: VetoTarget; block?: boolean; size?: 'normal' | 'small'; accessibilityHint?: string }) {
  const [open, setOpen] = useState(false);
  const toast = useToast();
  const client = useQueryClient();
  const waiting = usePendingVeto(target.actionId);

  const confirm = (note: string) => {
    setOpen(false);
    haptic('actionSuccess');
    const veto = scheduleVeto({
      actionId: target.actionId,
      note,
      client,
      onSettled: (error) => {
        if (!error) return;
        haptic('actionError');
        toast.show(`No se pudo vetar. ${errorMessage(error)}`, { tone: 'error' });
      },
    });
    // The veto goes when this toast leaves the screen: «Deshacer» is never on screen once it has gone.
    toast.show('Vetada', {
      undo: () => {
        toast.show(veto.undo() ? 'Veto deshecho' : 'El veto ya se había enviado');
      },
      onExpire: veto.send,
    });
  };

  if (waiting) {
    return (
      <Button variant="danger" block={block} size={size} disabled accessibilityHint="Puedes deshacerlo en el aviso de abajo">
        Vetada
      </Button>
    );
  }

  return (
    <>
      <Button variant="danger" block={block} size={size} accessibilityHint={accessibilityHint} onPress={() => setOpen(true)}>
        Vetar
      </Button>
      {open ? (
        <ConfirmSheet
          title={target.kind === 'pieza' ? 'Vetar la pieza' : 'Vetar la acción'}
          tone="danger"
          note="required"
          noteLabel="Nota"
          notePlaceholder="Por qué no debe salir"
          confirmLabel="Vetar"
          onClose={() => setOpen(false)}
          onConfirm={confirm}
        >
          {vetoConsequence(target)}
        </ConfirmSheet>
      ) : null}
    </>
  );
}

/** One id per intent, so a retry after a network error never queues a second preparation. */
export function newRequestId(): string {
  const native = (globalThis as { crypto?: { randomUUID?: () => string } }).crypto?.randomUUID?.();
  if (native) return native;
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (char) => {
    const random = Math.floor(Math.random() * 16);
    return (char === 'x' ? random : (random % 4) + 8).toString(16);
  });
}

/** «Preparar la siguiente pieza» behind the cost confirmation (POST /editorial/plan). */
export function PlanNextButton({ block = false }: { block?: boolean }) {
  const plan = usePlanPiece();
  const [asking, setAsking] = useState(false);
  const [requestId, setRequestId] = useState<string | undefined>(undefined);
  const open = () => {
    plan.reset();
    setRequestId(newRequestId());
    setAsking(true);
  };
  return (
    <View style={styles.plan}>
      <Button block={block} onPress={open} disabled={plan.isPending}>
        Preparar la siguiente pieza
      </Button>
      {plan.isSuccess ? (
        <Note tone="ok">{`Preparación en cola para el ${longDay(plan.data.slot_date)}. El circuito tarda unos minutos y la pieza aparecerá en el calendario.`}</Note>
      ) : null}
      {asking ? (
        <ConfirmSheet
          title="Preparar la siguiente pieza"
          confirmLabel="Preparar"
          busy={plan.isPending}
          error={plan.error}
          onClose={() => setAsking(false)}
          onConfirm={() =>
            plan.mutate(requestId, {
              onSuccess: () => {
                haptic('actionSuccess');
                setAsking(false);
              },
              onError: () => haptic('actionError'),
            })
          }
        >
          <T soft>
            Pone en cola el circuito editorial para el próximo día libre (como mucho a siete días): director, dos redactores, panel de lectores, selección y
            verificador.
          </T>
          <Note tone="warn">
            Tiene coste: cada etapa llama a Claude y gasta del presupuesto editorial. Si la pieza pasa el verificador, saldrá sola a su hora salvo que la vetes.
          </Note>
        </ConfirmSheet>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({ plan: { gap: space[2] } });
