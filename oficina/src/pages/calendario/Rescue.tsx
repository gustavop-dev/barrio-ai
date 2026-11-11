// EDI-23 (docs/funcionalidades/motor-editorial.md): a blocked piece shows why and lets Gustavo decide. «Pedir un
// cambio» opens the capture: his comment reworks it. «Desestimar el bloqueo» sends it out as it is with his approval,
// without the leader (the team prepares its image first when it lacks one). The app has the same (movil/src/pieza/Rescue.tsx).
import { useState } from 'react';
import { useOverridePiece } from '../../api/hooks';
import { useCapture } from '../../capture/CaptureContext';
import { Button, ConfirmModal, useToast } from '../../components/ui';
import { OVERRIDE_DONE, overrideConsequence } from './piece';
import type { PieceDetailFull } from './types';

/** One id per intent, so a retry after a network error never queues a second job. */
function newRequestId(): string | undefined {
  try {
    return typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function' ? crypto.randomUUID() : undefined;
  } catch {
    return undefined;
  }
}

export function RescueActions({ piece, label }: { piece: PieceDetailFull; label: string }) {
  const override = useOverridePiece(piece.id);
  const toast = useToast();
  const { openCapture } = useCapture();
  const [asking, setAsking] = useState(false);
  const [requestId, setRequestId] = useState<string | undefined>(undefined);
  const rescue = piece.rescue;
  if (!rescue) return null;
  if (rescue.why_not) return <p className="t-detalle text-suave">{rescue.why_not}</p>;
  const open = () => {
    override.reset();
    setRequestId(newRequestId());
    setAsking(true);
  };
  return (
    <>
      {rescue.change ? (
        <Button variant="secondary" onClick={() => openCapture({ tipo: 'pieza', id: piece.id, label })}>
          Pedir un cambio
        </Button>
      ) : null}
      {rescue.override ? (
        <Button variant="primary" onClick={open} disabled={override.isPending}>
          Desestimar el bloqueo
        </Button>
      ) : null}
      {asking ? (
        <ConfirmModal
          title="Desestimar el bloqueo"
          confirmLabel="Desestimar"
          note="optional"
          noteLabel="Nota para el equipo"
          busy={override.isPending}
          error={override.error}
          onClose={() => setAsking(false)}
          onConfirm={(note) =>
            override.mutate(
              { requestId, note },
              {
                onSuccess: () => {
                  setAsking(false);
                  toast.show(OVERRIDE_DONE);
                },
              },
            )
          }
        >
          <p>{overrideConsequence(piece)}</p>
        </ConfirmModal>
      ) : null}
    </>
  );
}
