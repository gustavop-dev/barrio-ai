// Ajustes › Orientación para el equipo (GET/PUT /api/v1/orientacion): how Gustavo steers the team.
// The field grows with the text; the screen's ScrollView keeps it above the keyboard.
import { useOrientacion, useSaveOrientacion } from '@compartido/api/hooks';
import { isUnavailable, ORIENTATION_MAX, orientationCounter, orientationUpdated } from '@compartido/logic/ajustes';
import { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { Button, Card, ErrorRetry, Field, Section, Skeleton, T, useToast } from '@/components/ui';
import { haptic } from '@/theme/motion';
import { space } from '@/theme/tokens';
import { Unavailable } from './parts';

export function OrientacionSection({ onFieldFocus }: { onFieldFocus?: () => void }) {
  const orientacion = useOrientacion();
  const save = useSaveOrientacion();
  const toast = useToast();
  /** null while the text is the saved one. */
  const [draft, setDraft] = useState<string | null>(null);
  const saved = orientacion.data?.text ?? '';
  const text = draft ?? saved;
  const tooLong = text.length > ORIENTATION_MAX;
  const changed = draft !== null && draft.trim() !== saved.trim();

  const submit = () => {
    if (!changed || tooLong || save.isPending) return;
    save.mutate(text.trim(), {
      onSuccess: () => {
        setDraft(null);
        haptic('actionSuccess');
        toast.show('Orientación guardada. El equipo la usa desde su próxima tarea.');
      },
      onError: () => haptic('actionError'),
    });
  };

  return (
    <Section
      label="Orientación para el equipo"
      intro="Tu dirección de alto nivel: temas, tono, prioridades o lo que debe evitar. La leen quien redacta los comentarios, el circuito editorial, el clasificador de la red y el agente líder."
    >
      {orientacion.isPending ? <Skeleton variant="card" label="Cargando la orientación…" /> : null}
      {isUnavailable(orientacion.error) ? (
        <Unavailable>El servidor todavía no guarda la orientación.</Unavailable>
      ) : (
        <ErrorRetry error={orientacion.error} onRetry={() => void orientacion.refetch()} />
      )}
      {orientacion.isSuccess ? (
        <Card>
          <Field
            label="Qué quieres que el equipo tenga en cuenta ahora"
            value={text}
            onChangeText={setDraft}
            multiline
            placeholder="Por ejemplo: este mes, más casos de ProjectApp y nada sobre rondas de inversión."
            hint={tooLong ? undefined : orientationCounter(text.length)}
            error={tooLong ? orientationCounter(text.length) : null}
            editable={!save.isPending}
            onFocus={onFieldFocus}
            testID="orientacion-field"
          />
          <ErrorRetry error={save.error} />
          <View style={styles.actions}>
            <Button variant="primary" disabled={!changed || tooLong} loading={save.isPending} loadingLabel="Guardando…" onPress={submit}>
              Guardar orientación
            </Button>
            {changed ? (
              <Button variant="ghost" onPress={() => setDraft(null)} disabled={save.isPending}>
                Descartar cambios
              </Button>
            ) : null}
          </View>
          <T variant="detalle" soft>
            {orientationUpdated(orientacion.data)}
          </T>
        </Card>
      ) : null}
    </Section>
  );
}

const styles = StyleSheet.create({ actions: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: space[2] } });
