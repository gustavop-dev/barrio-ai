// Ajustes › Sesión y este teléfono: who is signed in, the devices with a token, how native pushes
// are doing on this phone, the LinkedIn reconnect (in the browser, it needs the cookie session) and
// «Cerrar sesión», which revokes this device's token.
import { asList, listDevices, revokeDevice } from '@compartido/api/endpoints';
import type { Device } from '@compartido/api/types';
import { whenLabel } from '@compartido/logic/capturas';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { Linking, StyleSheet, View } from 'react-native';
import { API_URL, apiUrl } from '@/api/config';
import { useSession } from '@/auth/session';
import { Icon } from '@/components/icons';
import { Badge, Button, Card, ConfirmSheet, ErrorRetry, Note, Section, T, errorMessage } from '@/components/ui';
import { PWA_LINKEDIN } from '@/navigation';
import { PUSH_UNAVAILABLE_TEXT, type PushResult } from '@/push/register';
import { colors, space } from '@/theme/tokens';

const DEVICES_KEY = ['auth', 'dispositivos'] as const;

export function pushNote(push: PushResult | null): { tone: 'ok' | 'info' | 'warn' | 'error'; title: string; text: string } {
  if (!push) return { tone: 'info', title: 'Avisos en este teléfono', text: 'Comprobando si este teléfono puede recibir avisos…' };
  if (push.status === 'registrado') return { tone: 'ok', title: 'Avisos activos en este teléfono', text: 'Los avisos de la oficina llegan aquí; al tocarlos se abre la vista que toca.' };
  if (push.status === 'denegado') return { tone: 'warn', title: 'Avisos bloqueados', text: 'Permite las notificaciones de 0ff1ce en los ajustes del teléfono para recibirlos.' };
  if (push.status === 'no-disponible') return { tone: 'info', title: 'Avisos push aún no disponibles', text: PUSH_UNAVAILABLE_TEXT[push.reason] };
  return { tone: 'error', title: 'No se pudieron activar los avisos', text: errorMessage(push.error) };
}

function DeviceRow({ device, onRevoke }: { device: Device; onRevoke: () => void }) {
  return (
    <View style={styles.device}>
      <View style={styles.deviceText}>
        <T>{device.name}</T>
        <T variant="detalle" soft>
          {device.last_used_at ? `Usado ${whenLabel(device.last_used_at).toLocaleLowerCase('es-CO')}` : `Desde ${whenLabel(device.created_at).toLocaleLowerCase('es-CO')}`}
          {device.push ? ' · recibe avisos' : ''}
        </T>
      </View>
      {device.current ? (
        <Badge tone="ok">Este</Badge>
      ) : (
        <Button size="small" variant="danger" onPress={onRevoke} accessibilityLabel={`Cerrar la sesión de ${device.name}`}>
          Cerrar
        </Button>
      )}
    </View>
  );
}

export function SesionBlock() {
  const session = useSession();
  const client = useQueryClient();
  const devices = useQuery({ queryKey: DEVICES_KEY, queryFn: async () => asList(await listDevices()) });
  const revoke = useMutation({ mutationFn: revokeDevice, onSettled: () => client.invalidateQueries({ queryKey: DEVICES_KEY }) });
  const [revoking, setRevoking] = useState<Device | null>(null);
  const [leaving, setLeaving] = useState(false);
  const note = pushNote(session.push);

  return (
    <Section label="Sesión y este teléfono">
      <Card>
        <T>{session.user ? `Has entrado como ${session.user.username}` : 'Sesión abierta'}</T>
        <T variant="detalle" soft>
          Oficina: {API_URL.replace(/^https?:\/\//, '')}
        </T>
        <Note tone={note.tone} title={note.title}>
          {note.text}
        </Note>
      </Card>
      <Card>
        <T variant="etiqueta" soft>
          Dispositivos con sesión
        </T>
        <ErrorRetry error={devices.error} onRetry={() => void devices.refetch()} />
        {devices.data?.map((device) => <DeviceRow key={device.id} device={device} onRevoke={() => setRevoking(device)} />)}
        {devices.isSuccess && !devices.data.length ? (
          <T variant="detalle" soft>
            Ningún dispositivo con sesión.
          </T>
        ) : null}
      </Card>
      <Card>
        <T variant="etiqueta" soft>
          LinkedIn oficial
        </T>
        <T variant="detalle">Reconectar LinkedIn necesita la sesión de la oficina web: se abre en el navegador.</T>
        <Button icon={<Icon name="external" size={18} color={colors.inkSoft} />} onPress={() => void Linking.openURL(apiUrl(PWA_LINKEDIN))}>
          Abrir Ajustes en el navegador
        </Button>
      </Card>
      <Button variant="danger" block onPress={() => setLeaving(true)} testID="logout">
        Cerrar sesión en este teléfono
      </Button>
      {revoking ? (
        <ConfirmSheet
          title={`Cerrar la sesión de ${revoking.name}`}
          tone="danger"
          confirmLabel="Cerrar su sesión"
          busy={revoke.isPending}
          error={revoke.error}
          onConfirm={() => revoke.mutate(revoking.id, { onSuccess: () => setRevoking(null) })}
          onClose={() => setRevoking(null)}
        >
          Ese dispositivo tendrá que volver a entrar con usuario y contraseña, y deja de recibir avisos.
        </ConfirmSheet>
      ) : null}
      {leaving ? (
        <ConfirmSheet
          title="Cerrar sesión"
          tone="danger"
          confirmLabel="Cerrar sesión"
          onConfirm={() => {
            setLeaving(false);
            void session.logout();
          }}
          onClose={() => setLeaving(false)}
        >
          Este teléfono deja de recibir avisos y olvida su acceso. Para volver, entra con tu usuario y contraseña.
        </ConfirmSheet>
      ) : null}
    </Section>
  );
}

const styles = StyleSheet.create({
  device: { flexDirection: 'row', alignItems: 'center', gap: space[3], paddingVertical: space[1] },
  deviceText: { flex: 1, gap: 2 },
});
