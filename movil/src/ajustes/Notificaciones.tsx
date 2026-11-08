// Ajustes › Notificaciones: the native push of this phone (the Expo token the session registered at
// launch, push/register.ts), «Probar notificación», one switch per push type (`push_types`, saved as
// `push_disabled` and `push_enabled`) and «Dispositivos con la app» with revoke; revoking this phone signs it out.
import { useSavePreferencias, type PushType } from '@compartido/api/capturas';
import { asList, listDevices, revokeDevice, sendTestPush } from '@compartido/api/endpoints';
import { useAjustes } from '@compartido/api/hooks';
import type { Device } from '@compartido/api/types';
import { pushPreferencesPatch, pushToggledMessage, pushTypeHint, pushTypesOf } from '@compartido/logic/ajustes';
import { whenLabel } from '@compartido/logic/capturas';
import { timeAgo } from '@compartido/logic/format';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { Linking, StyleSheet, View } from 'react-native';
import { useSession } from '@/auth/session';
import { Badge, Button, Card, ConfirmSheet, ErrorRetry, Fold, KeyValue, Note, Section, Skeleton, SwitchRow, T, errorMessage, useToast } from '@/components/ui';
import { PUSH_UNAVAILABLE_TEXT, registerForPush, type PushResult } from '@/push/register';
import { haptic } from '@/theme/motion';
import type { Tone } from '@/theme/tokens';
import { colors, space } from '@/theme/tokens';
import { CardHead, Unavailable } from './parts';

export const DEVICES_KEY = ['auth', 'dispositivos'] as const;

export function pushNote(push: PushResult | null): { tone: 'ok' | 'info' | 'warn' | 'error'; title: string; text: string } {
  if (!push) return { tone: 'info', title: 'Avisos en este teléfono', text: 'Comprobando si este teléfono puede recibir avisos…' };
  if (push.status === 'registrado') return { tone: 'ok', title: 'Avisos activos en este teléfono', text: 'Los avisos de la oficina llegan aquí; al tocarlos se abre la vista que toca.' };
  if (push.status === 'denegado') return { tone: 'warn', title: 'Avisos bloqueados', text: 'Permite las notificaciones de 0ff1ce en los ajustes del teléfono para recibirlos.' };
  if (push.status === 'no-disponible') return { tone: 'info', title: 'Avisos push aún no disponibles', text: PUSH_UNAVAILABLE_TEXT[push.reason] };
  return { tone: 'error', title: 'No se pudieron activar los avisos', text: errorMessage(push.error) };
}

/** The badge of «Este dispositivo», as the PWA's: Activadas, Bloqueadas, No disponibles… */
export function pushBadge(push: PushResult | null): { label: string; tone: Tone } {
  if (!push) return { label: 'Comprobando…', tone: 'muted' };
  if (push.status === 'registrado') return { label: 'Activadas', tone: 'ok' };
  if (push.status === 'denegado') return { label: 'Bloqueadas', tone: 'bad' };
  if (push.status === 'no-disponible') return { label: 'No disponibles', tone: 'muted' };
  return { label: 'Con error', tone: 'bad' };
}

function ThisPhone() {
  const session = useSession();
  const ajustes = useAjustes();
  const toast = useToast();
  // A new registration from here (after a refusal or an error) replaces the launch's.
  const [retried, setRetried] = useState<PushResult | null>(null);
  const push = retried ?? session.push;
  const note = pushNote(push);
  const badge = pushBadge(push);
  const expo = ajustes.data?.expo_push;
  const enable = useMutation({ mutationFn: registerForPush, onSuccess: setRetried });
  const test = useMutation({
    mutationFn: sendTestPush,
    onSuccess: () => {
      haptic('actionSuccess');
      toast.show('Notificación de prueba enviada. Debería llegar en unos segundos.');
    },
    onError: () => haptic('actionError'),
  });

  return (
    <>
      <CardHead title="Este dispositivo">
        <Badge tone={badge.tone}>{badge.label}</Badge>
      </CardHead>
      <T variant="detalle" soft>
        Te avisan aquí de lo que pide tu acción (Tu turno) y de lo importante que pasa (Notificaciones).
      </T>
      {push?.status !== 'registrado' ? (
        <Note tone={note.tone} title={note.title}>
          {note.text}
        </Note>
      ) : null}
      {expo ? (
        <View style={styles.rows}>
          <KeyValue label="Teléfonos que reciben avisos">{String(expo.active)}</KeyValue>
          {expo.last_success_at ? <KeyValue label="Último aviso entregado">{timeAgo(expo.last_success_at)}</KeyValue> : null}
          {expo.last_error ? <KeyValue label="Último error de Expo">{expo.last_error}</KeyValue> : null}
        </View>
      ) : null}
      <Button block loading={test.isPending} loadingLabel="Enviando…" onPress={() => test.mutate()}>
        Probar notificación
      </Button>
      {push?.status === 'denegado' ? (
        <Button block onPress={() => void Linking.openSettings()}>
          Abrir los ajustes del teléfono
        </Button>
      ) : null}
      {push?.status === 'error' ? (
        <Button variant="primary" block loading={enable.isPending} loadingLabel="Activando…" onPress={() => enable.mutate()}>
          Activar notificaciones
        </Button>
      ) : null}
      <ErrorRetry error={test.error ?? enable.error} />
    </>
  );
}

/** One switch per push type; the notice itself still reaches Tu turno or Notificaciones. */
function PerType() {
  const ajustes = useAjustes();
  const save = useSavePreferencias();
  const toast = useToast();
  const [overrides, setOverrides] = useState<Record<string, boolean>>({});
  const types: PushType[] | undefined = pushTypesOf(ajustes.data);
  const enabled = (type: PushType) => overrides[type.kind] ?? type.enabled;

  const toggle = (type: PushType, next: boolean) => {
    const previous = overrides;
    const updated = { ...overrides, [type.kind]: next };
    setOverrides(updated);
    save.mutate(
      pushPreferencesPatch(types ?? [], updated),
      {
        onSuccess: () => toast.show(pushToggledMessage(type, next)),
        onError: (error) => {
          setOverrides(previous);
          toast.show(errorMessage(error), { tone: 'error' });
        },
      },
    );
  };

  return (
    <Fold summary="Por tipo de notificación">
      {ajustes.isSuccess && !types ? <Unavailable>El servidor todavía no envía los tipos de notificación.</Unavailable> : null}
      <ErrorRetry error={ajustes.error} onRetry={() => void ajustes.refetch()} />
      {types?.length ? (
        <>
          <T variant="detalle" soft>
            Apagar la push de un tipo no lo borra: el aviso sigue llegando a Tu turno o a Notificaciones.
          </T>
          <View>
            {types.map((type) => (
              <SwitchRow
                key={type.kind}
                label={type.label}
                hint={pushTypeHint(type)}
                value={enabled(type)}
                disabled={save.isPending}
                onChange={(next) => toggle(type, next)}
                testID={`push-${type.kind}`}
              />
            ))}
          </View>
        </>
      ) : null}
    </Fold>
  );
}

function DeviceRow({ device, onRevoke }: { device: Device; onRevoke: () => void }) {
  return (
    <View style={styles.device} testID={`device-${device.id}`}>
      <View style={styles.deviceText}>
        <View style={styles.deviceName}>
          <T style={styles.deviceLabel}>{device.name}</T>
          {device.current ? <Badge tone="ok">Este</Badge> : null}
        </View>
        <T variant="detalle" soft>
          {device.last_used_at ? `Usado ${whenLabel(device.last_used_at).toLocaleLowerCase('es-CO')}` : `Desde ${whenLabel(device.created_at).toLocaleLowerCase('es-CO')}`}
          {device.push ? ' · recibe avisos' : ''}
        </T>
      </View>
      <Button size="small" variant="danger" onPress={onRevoke} accessibilityLabel={device.current ? 'Cerrar la sesión de este teléfono' : `Cerrar la sesión de ${device.name}`}>
        Cerrar
      </Button>
    </View>
  );
}

function Devices() {
  const session = useSession();
  const client = useQueryClient();
  const toast = useToast();
  const devices = useQuery({ queryKey: DEVICES_KEY, queryFn: async () => asList(await listDevices()) });
  const revoke = useMutation({ mutationFn: revokeDevice, onSettled: () => client.invalidateQueries({ queryKey: DEVICES_KEY }) });
  const [revoking, setRevoking] = useState<Device | null>(null);

  const confirm = () => {
    if (!revoking) return;
    // This phone: the same as «Cerrar sesión» (unregisters the push, revokes the token, back to the login).
    if (revoking.current) {
      setRevoking(null);
      void session.logout();
      return;
    }
    revoke.mutate(revoking.id, {
      onSuccess: () => {
        toast.show(`Sesión cerrada en ${revoking.name}.`);
        setRevoking(null);
      },
    });
  };

  return (
    <View style={styles.devices}>
      <T variant="etiqueta" soft accessibilityRole="header">
        Dispositivos con la app
      </T>
      {devices.isPending ? <Skeleton variant="row" count={2} label="Cargando los dispositivos…" /> : null}
      <ErrorRetry error={devices.error} onRetry={() => void devices.refetch()} />
      {devices.data?.map((device) => <DeviceRow key={device.id} device={device} onRevoke={() => setRevoking(device)} />)}
      {devices.isSuccess && !devices.data.length ? (
        <T variant="detalle" soft>
          Ningún dispositivo con sesión.
        </T>
      ) : null}
      {revoking ? (
        <ConfirmSheet
          title={revoking.current ? 'Cerrar la sesión de este teléfono' : `Cerrar la sesión de ${revoking.name}`}
          tone="danger"
          confirmLabel={revoking.current ? 'Cerrar sesión' : 'Cerrar su sesión'}
          busy={revoke.isPending}
          error={revoke.error}
          onConfirm={confirm}
          onClose={() => setRevoking(null)}
        >
          {revoking.current
            ? 'Este teléfono deja de recibir avisos y olvida su acceso. Para volver, entra con tu usuario y contraseña.'
            : 'Ese dispositivo tendrá que volver a entrar con usuario y contraseña, y deja de recibir avisos.'}
        </ConfirmSheet>
      ) : null}
    </View>
  );
}

export function NotificacionesSection() {
  return (
    <Section label="Notificaciones">
      <Card>
        <ThisPhone />
        <PerType />
        <Devices />
      </Card>
    </Section>
  );
}

const styles = StyleSheet.create({
  rows: { gap: 6 },
  devices: { gap: space[2], paddingTop: space[3], borderTopWidth: 1, borderTopColor: colors.line },
  device: { flexDirection: 'row', alignItems: 'center', gap: space[3], paddingVertical: space[1] },
  deviceText: { flex: 1, gap: 2 },
  deviceName: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: space[2] },
  deviceLabel: { flexShrink: 1 },
});
