// Ajustes › Captura y galería (rev 18): the microphone permission (asked here, or the phone's settings
// when it was blocked; checked again when Gustavo comes back from them) and the default «El equipo
// puede editar mis fotos con IA» (PATCH /api/v1/ajustes/preferencias).
import { usePreferencias, useSavePreferencias } from '@compartido/api/capturas';
import { isUnavailable } from '@compartido/logic/ajustes';
import { useEffect, useState } from 'react';
import { AppState, Linking, StyleSheet, View } from 'react-native';
import { useRecorder, type MicState } from '@/capture/recorder';
import { Icon } from '@/components/icons';
import { Badge, Button, Card, ErrorRetry, Note, Section, SwitchRow, T, errorMessage, useToast } from '@/components/ui';
import type { Tone } from '@/theme/tokens';
import { colors, space } from '@/theme/tokens';
import { CardHead } from './parts';

const MIC: Record<MicState | 'checking', { label: string; tone: Tone }> = {
  granted: { label: 'Permitido', tone: 'ok' },
  denied: { label: 'Bloqueado', tone: 'bad' },
  explain: { label: 'Sin pedir', tone: 'muted' },
  checking: { label: 'Comprobando…', tone: 'muted' },
};

function Microphone() {
  const { micState, requestMic } = useRecorder();
  const [mic, setMic] = useState<MicState | null>(null);
  const [asking, setAsking] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  // Now, and every time the app comes back (from the phone's settings, for example).
  useEffect(() => {
    let alive = true;
    const check = () =>
      micState()
        .then((state) => alive && setMic(state))
        .catch(() => undefined);
    void check();
    const subscription = AppState.addEventListener('change', (state) => {
      if (state === 'active') void check();
    });
    return () => {
      alive = false;
      subscription.remove();
    };
  }, [micState]);

  const ask = async () => {
    setAsking(true);
    setProblem(null);
    try {
      setMic(await requestMic());
    } catch (error) {
      setProblem(errorMessage(error));
    } finally {
      setAsking(false);
    }
  };

  const badge = MIC[mic ?? 'checking'];
  return (
    <>
      <CardHead title="Micrófono">
        <Badge tone={badge.tone}>{badge.label}</Badge>
      </CardHead>
      <T variant="detalle" soft>
        Se usa solo mientras mantienes el botón aguamarina o grabas desde la hoja de captura.
      </T>
      {mic === 'explain' ? (
        <Button block loading={asking} loadingLabel="Esperando al permiso…" icon={<Icon name="microfono" size={20} color={colors.ink} />} onPress={() => void ask()}>
          Permitir el micrófono
        </Button>
      ) : null}
      {mic === 'denied' ? (
        <Note
          tone="warn"
          title="Para volver a permitirlo"
          actions={
            <Button size="small" onPress={() => void Linking.openSettings()}>
              Abrir los ajustes del teléfono
            </Button>
          }
        >
          Cámbialo en los ajustes del teléfono: Apps › 0ff1ce › Permisos › Micrófono. Mientras tanto puedes seguir enviando fotos y notas.
        </Note>
      ) : null}
      {problem ? (
        <T variant="detalle" color={colors.alert}>
          {problem}
        </T>
      ) : null}
    </>
  );
}

function AiEditDefault() {
  const prefs = usePreferencias();
  const save = useSavePreferencias();
  const toast = useToast();
  const [pending, setPending] = useState<boolean | null>(null);
  const unavailable = isUnavailable(prefs.error);
  const checked = pending ?? prefs.data?.gallery_ai_edit_default ?? true;

  const change = (next: boolean) => {
    setPending(next);
    save.mutate(
      { gallery_ai_edit_default: next },
      {
        onSuccess: () => toast.show(next ? 'Las fotos nuevas se podrán editar con IA.' : 'Las fotos nuevas no se editarán con IA.'),
        onError: (error) => toast.show(errorMessage(error), { tone: 'error' }),
        onSettled: () => setPending(null),
      },
    );
  };

  return (
    <View style={styles.ai}>
      <SwitchRow label="El equipo puede editar mis fotos con IA" value={checked} disabled={!prefs.isSuccess || save.isPending} onChange={change} />
      <T variant="detalle" soft>
        {unavailable ? 'Aún no disponible: el servidor todavía no guarda esta preferencia.' : 'Es el valor por defecto de cada foto nueva; puedes cambiarlo foto por foto en la Galería.'}
      </T>
      {!unavailable ? <ErrorRetry error={prefs.error} onRetry={() => void prefs.refetch()} /> : null}
    </View>
  );
}

export function CapturaSection() {
  return (
    <Section label="Captura y galería">
      <Card>
        <Microphone />
        <AiEditDefault />
      </Card>
    </Section>
  );
}

const styles = StyleSheet.create({ ai: { gap: space[2] } });
