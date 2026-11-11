// EDI-23 (docs/funcionalidades/motor-editorial.md): a blocked piece shows why and lets Gustavo decide. «Pedir un
// cambio» opens the capture sheet: his comment reworks it. «Desestimar el bloqueo» sends it out as it is with his
// approval, without the leader (the team prepares its image first when it lacks one). Same copy as the PWA.
import type { PieceDetailFull } from '@compartido/api/calendario';
import { useOverridePiece } from '@compartido/api/hooks';
import { OVERRIDE_DONE, overrideConsequence } from '@compartido/logic/piece';
import { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { newRequestId } from '@/calendario/Veto';
import { openCaptureSheet } from '@/capture/store';
import { Button, ConfirmSheet, T, useToast } from '@/components/ui';
import { haptic } from '@/theme/motion';
import { space } from '@/theme/tokens';

export function RescueActions({ piece, label }: { piece: PieceDetailFull; label: string }) {
  const override = useOverridePiece(piece.id);
  const toast = useToast();
  const [asking, setAsking] = useState(false);
  const [requestId, setRequestId] = useState<string | undefined>(undefined);
  const rescue = piece.rescue;
  if (!rescue) return null;
  if (rescue.why_not) {
    return (
      <T variant="detalle" soft>
        {rescue.why_not}
      </T>
    );
  }
  const open = () => {
    override.reset();
    setRequestId(newRequestId());
    setAsking(true);
  };
  return (
    <View style={styles.actions}>
      {rescue.change ? (
        <Button block onPress={() => openCaptureSheet({ tipo: 'pieza', id: piece.id, label })}>
          Pedir un cambio
        </Button>
      ) : null}
      {rescue.override ? (
        <Button block variant="primary" onPress={open} disabled={override.isPending}>
          Desestimar el bloqueo
        </Button>
      ) : null}
      {asking ? (
        <ConfirmSheet
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
                  haptic('actionSuccess');
                  setAsking(false);
                  toast.show(OVERRIDE_DONE);
                },
                onError: () => haptic('actionError'),
              },
            )
          }
        >
          {overrideConsequence(piece)}
        </ConfirmSheet>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({ actions: { gap: space[2], width: '100%' } });
