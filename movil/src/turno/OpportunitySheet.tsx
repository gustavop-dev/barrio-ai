// «Marcar como oportunidad» from a conversation card: the person, modality, channel and a note,
// prefilled by the card; nothing is created until Gustavo saves it. The full opportunity form
// (stage, need, budget, next step…) comes with the Personas port.
import { useCreateOportunidad } from '@compartido/api/hooks';
import type { OpportunityChannel, OpportunityModality, TurnoOpportunity } from '@compartido/api/types';
import { CHANNEL_LABEL, OPPORTUNITY_MODALITY_LABEL } from '@compartido/logic/personas';
import { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { Avatar, Button, ErrorRetry, Field, Options, Sheet, T, useToast } from '@/components/ui';
import { haptic } from '@/theme/motion';
import { space } from '@/theme/tokens';

const MODALITIES: OpportunityModality[] = ['personal_startups', 'projectapp'];
const CHANNELS = Object.keys(CHANNEL_LABEL) as OpportunityChannel[];

export function OpportunitySheet({ prefill, onClose }: { prefill: TurnoOpportunity; onClose: () => void }) {
  const toast = useToast();
  const create = useCreateOportunidad();
  const [modality, setModality] = useState<OpportunityModality | null>(prefill.modality === 'personal_startups' || prefill.modality === 'projectapp' ? prefill.modality : null);
  const [channel, setChannel] = useState<OpportunityChannel>(prefill.channel ?? 'linkedin');
  const [notes, setNotes] = useState(prefill.notes ?? '');

  const save = async () => {
    if (!modality || create.isPending) return;
    try {
      await create.mutateAsync({ contact: prefill.contact, modality, channel, stage: 'conversacion', notes: notes.trim() });
      haptic('actionSuccess');
      toast.show('Oportunidad creada');
      onClose();
    } catch {
      haptic('actionError');
    }
  };

  return (
    <Sheet label="Nueva oportunidad" onClose={onClose} suspended={create.isPending} testID="opportunity-sheet">
      <T variant="subtitulo" accessibilityRole="header">
        Nueva oportunidad
      </T>
      <View style={styles.person}>
        <Avatar name={prefill.display_name} />
        <View style={styles.personText}>
          <T>{prefill.display_name}</T>
          {prefill.headline ? (
            <T variant="detalle" soft numberOfLines={2}>
              {prefill.headline}
            </T>
          ) : null}
        </View>
      </View>
      <Options legend="Modalidad" value={modality} onChange={setModality} options={MODALITIES.map((value) => ({ value, label: OPPORTUNITY_MODALITY_LABEL[value] }))} />
      <Options legend="Canal" horizontal={false} value={channel} onChange={setChannel} options={CHANNELS.map((value) => ({ value, label: CHANNEL_LABEL[value] }))} />
      <Field label="Notas" optional value={notes} onChangeText={setNotes} multiline />
      <ErrorRetry error={create.error} />
      <View style={styles.actions}>
        <Button variant="primary" block disabled={!modality} loading={create.isPending} loadingLabel="Guardando…" onPress={() => void save()}>
          Guardar oportunidad
        </Button>
        <Button block onPress={onClose} disabled={create.isPending}>
          Cancelar
        </Button>
      </View>
    </Sheet>
  );
}

const styles = StyleSheet.create({
  person: { flexDirection: 'row', alignItems: 'center', gap: space[3] },
  personText: { flex: 1, gap: 2 },
  actions: { gap: space[2] },
});
