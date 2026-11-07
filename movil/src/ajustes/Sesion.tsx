// Ajustes › Lo que el equipo sabe de ti (a link to the Sabe tab of Tu turno, with `facts_count`) and
// Sesión y Acerca de: who is signed in, «Cerrar sesión» (unregisters the push and revokes this
// device's token), the app version (expo-constants) and the art credit.
import { useAjustes } from '@compartido/api/hooks';
import { ART_CREDIT, ART_CREDIT_URL, factsLabel } from '@compartido/logic/ajustes';
import Constants from 'expo-constants';
import { router } from 'expo-router';
import { useState } from 'react';
import { Linking, Pressable, StyleSheet, View } from 'react-native';
import { API_URL } from '@/api/config';
import { useSession } from '@/auth/session';
import { Icon } from '@/components/icons';
import { Button, Card, ConfirmSheet, KeyValue, Section, T } from '@/components/ui';
import { colors, radius, shell, space } from '@/theme/tokens';

/** The version of app.json, as the build carries it. */
export function appVersion(): string {
  return Constants.expoConfig?.version ?? '—';
}

export function SabeLink() {
  const ajustes = useAjustes();
  return (
    <Pressable
      accessibilityRole="link"
      accessibilityLabel={`Lo que el equipo sabe de ti. ${factsLabel(ajustes.data?.facts_count)}`}
      onPress={() => router.navigate({ pathname: '/tu-turno', params: { tab: 'sabe' } })}
      style={({ pressed }) => [styles.link, pressed ? styles.linkPressed : null]}
      testID="sabe-link"
    >
      <View style={styles.linkText}>
        <T>Lo que el equipo sabe de ti</T>
        <T variant="detalle" soft>
          {factsLabel(ajustes.data?.facts_count)}
        </T>
      </View>
      <Icon name="chevronRight" size={22} color={colors.inkSoft} />
    </Pressable>
  );
}

export function SesionSection() {
  const session = useSession();
  const [leaving, setLeaving] = useState(false);
  return (
    <Section label="Sesión y Acerca de">
      <Card>
        <T>{session.user ? `Has entrado como ${session.user.username}.` : 'Sesión abierta.'}</T>
        <T variant="detalle" soft>
          Oficina: {API_URL.replace(/^https?:\/\//, '')}
        </T>
        <Button block onPress={() => setLeaving(true)} testID="logout">
          Cerrar sesión
        </Button>
        <T variant="detalle" soft>
          Cerrar sesión en este teléfono también apaga sus avisos.
        </T>
      </Card>
      <Card>
        <KeyValue label="Versión">{`app ${appVersion()}`}</KeyValue>
        <View style={styles.credit}>
          <T variant="detalle" soft style={styles.creditText}>
            {ART_CREDIT}
          </T>
          <Pressable accessibilityRole="link" accessibilityLabel="LimeZu en itch.io" onPress={() => void Linking.openURL(ART_CREDIT_URL)} style={styles.creditLink}>
            <Icon name="external" size={20} color={colors.brandDeep} />
          </Pressable>
        </View>
      </Card>
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
  link: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space[3],
    padding: space[4],
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.md,
  },
  linkPressed: { backgroundColor: colors.paper },
  linkText: { flex: 1, gap: 2 },
  credit: { flexDirection: 'row', alignItems: 'center', gap: space[2] },
  creditText: { flex: 1 },
  creditLink: { width: shell.touch + 4, height: shell.touch + 4, alignItems: 'center', justifyContent: 'center' },
});
