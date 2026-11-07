// «Lo que enviaste»: the capture history inside the sheet (Captura.dc.html, rev 18), with the same
// labels as the PWA (compartido/src/logic/capturas.ts).
import { captureKeys, sameOrigin, undoCaptura, useCapturaLive, useCapturas, type CaptureOutput } from '@compartido/api/capturas';
import { canUndo, CONTEXT_PREFIX, contentsOf, purposeOf, STATE_TONE, whenLabel } from '@compartido/logic/capturas';
import { excerpt } from '@compartido/logic/format';
import { useQueryClient } from '@tanstack/react-query';
import { useAudioPlayer, useAudioPlayerStatus } from 'expo-audio';
import { router } from 'expo-router';
import { useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { apiUrl } from '@/api/config';
import { keys } from '@/api/queryClient';
import { authHeaders } from '@/api/transport';
import { Icon } from '@/components/icons';
import { Badge, Button, Card, EmptyState, EmptyText, ErrorRetry, Skeleton, T, errorMessage, useToast } from '@/components/ui';
import { routeForUrl } from '@/push/routes';
import { colors, shell, space } from '@/theme/tokens';

function Listen({ path }: { path: string }) {
  const player = useAudioPlayer({ uri: apiUrl(path), headers: authHeaders() });
  const status = useAudioPlayerStatus(player);
  return (
    <Button size="small" icon={<Icon name={status.playing ? 'pausa' : 'play'} size={20} />} onPress={() => (status.playing ? player.pause() : player.play())}>
      {status.playing ? 'Pausar' : 'Escuchar'}
    </Button>
  );
}

function CaptureCard({ initial, onNavigate }: { initial: CaptureOutput; onNavigate: () => void }) {
  const live = useCapturaLive(initial);
  const capture = live.data ?? initial;
  const client = useQueryClient();
  const toast = useToast();
  const [undoing, setUndoing] = useState(false);
  const [now] = useState(() => Date.now());
  const contents = contentsOf(capture);
  const text = capture.transcript?.trim() ? `«${excerpt(capture.transcript, 240)}»` : capture.note?.trim() ? excerpt(capture.note, 240) : '';
  const noteToo = Boolean(capture.transcript?.trim() && capture.note?.trim());
  const audioPath = capture.has_audio ? sameOrigin(capture.audio_url) : null;
  const outcomeRoute = routeForUrl(capture.outcome?.link);
  const undoable = canUndo(capture, now);

  const undo = async () => {
    setUndoing(true);
    try {
      await undoCaptura(capture.id);
      toast.show('Envío deshecho.');
    } catch (error) {
      toast.show(errorMessage(error), { tone: 'error' });
    } finally {
      setUndoing(false);
      void client.invalidateQueries({ queryKey: captureKeys.all });
      void client.invalidateQueries({ queryKey: keys.tuTurno });
    }
  };

  return (
    <Card>
      {contents.length ? (
        <View style={styles.chips}>
          {contents.map((part) => (
            <Badge key={part} tone="ink">
              {part}
            </Badge>
          ))}
        </View>
      ) : null}
      <T variant="detalle" soft>
        {whenLabel(capture.created_at)} · {purposeOf(capture)}
      </T>
      {capture.context ? (
        <T variant="detalle" soft>
          {CONTEXT_PREFIX[capture.context.tipo] ?? 'Sobre'}: {capture.context.label}
        </T>
      ) : null}
      {text ? <T>{text}</T> : null}
      {noteToo ? (
        <T variant="detalle" soft>
          Nota: {excerpt(capture.note, 200)}
        </T>
      ) : null}
      <View style={styles.state}>
        <Badge tone={STATE_TONE[capture.state] ?? 'muted'}>{capture.state_label || capture.state}</Badge>
        {capture.outcome?.text ? (
          outcomeRoute ? (
            <Pressable
              accessibilityRole="link"
              onPress={() => {
                onNavigate();
                router.push({ pathname: outcomeRoute.pathname as never, params: outcomeRoute.params });
              }}
            >
              <T variant="detalle" color={colors.brandDeep}>
                {capture.outcome.text}
              </T>
            </Pressable>
          ) : (
            <T variant="detalle" soft>
              {capture.outcome.text}
            </T>
          )
        ) : null}
      </View>
      {capture.state === 'error' && capture.error ? (
        <T variant="detalle" color={colors.alert}>
          {capture.error}
        </T>
      ) : null}
      {audioPath || undoable ? (
        <View style={styles.actions}>
          {audioPath ? <Listen path={audioPath} /> : null}
          {undoable ? (
            <Button variant="ghost" size="small" loading={undoing} loadingLabel="Deshaciendo…" onPress={() => void undo()}>
              Deshacer
            </Button>
          ) : null}
        </View>
      ) : null}
    </Card>
  );
}

export function CaptureHistory({ onBack, onNavigate }: { onBack: () => void; onNavigate: () => void }) {
  const history = useCapturas();
  return (
    <View style={styles.history}>
      <Pressable accessibilityRole="button" onPress={onBack} style={styles.back}>
        <Icon name="chevronLeft" size={20} />
        <T>Volver a la captura</T>
      </Pressable>
      {history.isPending ? <Skeleton count={2} label="Cargando lo que enviaste…" /> : null}
      <ErrorRetry error={history.error} onRetry={() => void history.refetch()} />
      {history.isSuccess && history.items.length === 0 ? (
        <EmptyState title="Todavía no has enviado nada">
          <EmptyText>Lo que mandes aparecerá aquí, con lo que hizo el equipo.</EmptyText>
        </EmptyState>
      ) : null}
      {history.items.map((capture) => (
        <CaptureCard key={capture.id} initial={capture} onNavigate={onNavigate} />
      ))}
      {history.hasNextPage ? (
        <Button block loading={history.isFetchingNextPage} loadingLabel="Cargando…" onPress={() => void history.fetchNextPage()}>
          Ver envíos anteriores
        </Button>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  history: { gap: space[3] },
  back: { minHeight: shell.touch, flexDirection: 'row', alignItems: 'center', gap: space[1] },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  state: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: space[2] },
  actions: { flexDirection: 'row', flexWrap: 'wrap', gap: space[2] },
});
