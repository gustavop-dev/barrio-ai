// Ajustes › Mi voz (GET /api/v1/yo/voz, organizaciones phase 7): which voice the team writes with in her name, how many
// of her own texts it has learned from, and the proposal of her voice, which only she confirms or discards.
import { useDecideMiVoz, useMiVoz, useProposeMiVoz } from '@compartido/api/hooks';
import { isUnavailable } from '@compartido/logic/ajustes';
import { formatDateTime } from '@compartido/logic/format';
import {
  PROPOSE_COST,
  proposeBlocked,
  signalRows,
  VERSION_STATE_LABEL,
  VERSION_STATE_TONE,
  VOICE_TONE,
  voiceProgress,
  voiceSentence,
} from '@compartido/logic/miembro';
import { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { Badge, Button, Card, ConfirmSheet, ErrorRetry, Fold, KeyValue, Meter, Note, Section, Skeleton, T, useToast } from '@/components/ui';
import { haptic } from '@/theme/motion';
import { space } from '@/theme/tokens';
import { CardHead, Unavailable } from './parts';

type Asking = { kind: 'confirmar' | 'descartar'; number: number } | { kind: 'proponer' } | null;

export function MiVozSection() {
  const voz = useMiVoz();
  const decide = useDecideMiVoz();
  const propose = useProposeMiVoz();
  const toast = useToast();
  const [asking, setAsking] = useState<Asking>(null);
  const [reading, setReading] = useState(false);
  const data = voz.data;
  const proposal = data?.proposal ?? null;

  const close = () => {
    setAsking(null);
    decide.reset();
    propose.reset();
  };
  const done = (message: string) => {
    close();
    haptic('actionSuccess');
    toast.show(message);
  };

  return (
    <View testID="ajustes-mi-voz" collapsable={false}>
      <Section label="Mi voz" intro="El equipo aprende tu estilo de lo que apruebas, corriges, respondes y grabas. Tu voz solo cambia cuando tú confirmas una propuesta.">
        {voz.isPending ? <Skeleton variant="card" label="Cargando tu voz…" /> : null}
        {isUnavailable(voz.error) ? <Unavailable>El servidor todavía no muestra tu voz.</Unavailable> : <ErrorRetry error={voz.error} onRetry={() => void voz.refetch()} />}
        {data ? (
          <Card>
            <CardHead title="Voz del equipo en tu nombre">
              <View testID="voz-estado" collapsable={false}>
                <Badge tone={VOICE_TONE[data.state] ?? 'muted'} dot>
                  {data.label}
                </Badge>
              </View>
            </CardHead>
            <T variant="detalle">{voiceSentence(data)}</T>
            <View testID="voz-progreso" collapsable={false}>
              <Meter label="Muestra para una propuesta" value={data.signals.texts} max={data.signals.minimum} display={voiceProgress(data.signals)} />
            </View>
            {signalRows(data.signals).map((row) => (
              <KeyValue key={row.kind} label={row.label} testID={`voz-senal-${row.kind}`}>
                {String(row.count)}
              </KeyValue>
            ))}
            {proposal ? (
              <Note
                tone="info"
                title={`Propuesta de tu voz (versión ${proposal.number}) lista`}
                actions={
                  <View style={styles.actions}>
                    <Button size="small" onPress={() => setReading((value) => !value)} testID="voz-ver">
                      {reading ? 'Ocultar la propuesta' : 'Ver la propuesta'}
                    </Button>
                    <Button size="small" variant="primary" onPress={() => setAsking({ kind: 'confirmar', number: proposal.number })} testID="voz-confirmar">
                      Confirmar
                    </Button>
                    <Button size="small" variant="ghost" onPress={() => setAsking({ kind: 'descartar', number: proposal.number })} testID="voz-descartar">
                      Descartar
                    </Button>
                  </View>
                }
              >
                {`Preparada ${formatDateTime(proposal.created_at)}. No se usa hasta que la confirmes.${proposal.note ? ` ${proposal.note}` : ''}`}
              </Note>
            ) : null}
            {proposal && reading ? (
              <T variant="detalle" testID="voz-propuesta-texto">
                {proposal.text}
              </T>
            ) : null}
            {data.can_propose ? (
              <Button onPress={() => setAsking({ kind: 'proponer' })} testID="voz-proponer">
                Pedir propuesta de mi voz
              </Button>
            ) : (
              <T variant="detalle" soft testID="voz-sin-propuesta">
                {proposeBlocked(data)}
              </T>
            )}
            {data.versions.length ? (
              <Fold summary={`Versiones (${data.versions.length})`}>
                {data.versions.map((version) => (
                  <View key={version.number} style={styles.version} testID={`voz-version-${version.number}`}>
                    <T variant="detalle">{`#${version.number}`}</T>
                    <Badge tone={VERSION_STATE_TONE[version.state] ?? 'muted'}>{VERSION_STATE_LABEL[version.state] ?? version.state}</Badge>
                    <T variant="detalle" soft>
                      {`${version.source} · ${formatDateTime(version.decided_at ?? version.created_at)}`}
                    </T>
                  </View>
                ))}
              </Fold>
            ) : null}
          </Card>
        ) : null}
      </Section>

      {asking?.kind === 'confirmar' ? (
        <ConfirmSheet
          title={`Confirmar la versión ${asking.number} de tu voz`}
          confirmLabel="Confirmar mi voz"
          busy={decide.isPending}
          error={decide.error}
          onClose={close}
          onConfirm={() =>
            decide.mutate(
              { number: asking.number, decision: 'confirmar' },
              { onSuccess: () => done(`Voz ${asking.number} confirmada: desde ahora el equipo escribe con ella.`), onError: () => haptic('actionError') },
            )
          }
        >
          Desde ahora el equipo escribe con esta voz y tus borradores dejan de marcarse «Voz provisional». Lo que necesita tu aprobación no cambia: eso lo decide el administrador.
        </ConfirmSheet>
      ) : null}
      {asking?.kind === 'descartar' ? (
        <ConfirmSheet
          title={`Descartar la propuesta ${asking.number}`}
          confirmLabel="Descartar la propuesta"
          tone="danger"
          note="optional"
          noteLabel="Por qué no te representa"
          busy={decide.isPending}
          error={decide.error}
          onClose={close}
          onConfirm={(note) =>
            decide.mutate(
              { number: asking.number, decision: 'descartar', ...(note ? { note } : {}) },
              { onSuccess: () => done(`Propuesta ${asking.number} descartada. Sigue la voz que tenías.`), onError: () => haptic('actionError') },
            )
          }
        >
          Sigue la voz que tienes. Tus señales se quedan y sirven para una propuesta nueva.
        </ConfirmSheet>
      ) : null}
      {asking?.kind === 'proponer' ? (
        <ConfirmSheet
          title="Pedir una propuesta de tu voz"
          confirmLabel="Pedir propuesta"
          busy={propose.isPending}
          error={propose.error}
          onClose={close}
          onConfirm={() =>
            propose.mutate(undefined, { onSuccess: () => done('Propuesta lista: revísala y decide si te representa.'), onError: () => haptic('actionError') })
          }
        >
          {PROPOSE_COST}
        </ConfirmSheet>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  actions: { flexDirection: 'row', flexWrap: 'wrap', gap: space[2] },
  version: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: space[2] },
});
