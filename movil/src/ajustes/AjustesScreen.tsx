// Ajustes (Ajustes.dc.html, DISENO-VISTAS «6. Ajustes», rev 18), opened from the top bar: the
// machine controls, the team's orientation, autonomy and caps (folded), AI spend, the official
// LinkedIn, capture and gallery, this phone's notifications and devices, what the team knows, and
// the session. `/ajustes#maquina` (the `ancla` param) scrolls to that section, also while the
// sections above it are still loading; `?linkedin=…&motivo=…` shows the OAuth return message.
import { isAjustesSection, type AjustesSection } from '@compartido/logic/ajustes';
import { router, useLocalSearchParams } from 'expo-router';
import { useCallback, useEffect, useRef, type ReactNode } from 'react';
import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet, View, type LayoutChangeEvent, type ScrollViewInstance } from 'react-native';
import { useContentInsets } from '@/components/shell/useContentInsets';
import { Button, PageHeader, pageContent } from '@/components/ui';
import { colors, space } from '@/theme/tokens';
import { AutonomiaSection } from './Autonomia';
import { CapturaSection } from './Captura';
import { GastoSection } from './Gasto';
import { LinkedInSection } from './LinkedIn';
import { MaquinaSection } from './Maquina';
import { NotificacionesSection } from './Notificaciones';
import { OrientacionSection } from './Orientacion';
import { SabeLink, SesionSection } from './Sesion';

type Params = { ancla?: string; linkedin?: string; motivo?: string };

/** Room left above a section when a link scrolls to it. */
const ANCHOR_MARGIN = space[3];

export function AjustesScreen() {
  const params = useLocalSearchParams<Params>();
  const { bottom } = useContentInsets();
  const scroll = useRef<ScrollViewInstance>(null);
  const positions = useRef<Partial<Record<AjustesSection, number>>>({});
  /** The section a link asked for, until it is on screen and Gustavo scrolls by himself. */
  const pending = useRef<AjustesSection | null>(null);
  const anchor = isAjustesSection(params.ancla) ? params.ancla : null;

  const scrollTo = useCallback((id: AjustesSection, animated = true) => {
    const y = positions.current[id];
    if (y === undefined) return false;
    scroll.current?.scrollTo({ y: Math.max(0, y - ANCHOR_MARGIN), animated });
    return true;
  }, []);

  useEffect(() => {
    pending.current = anchor;
    if (anchor) scrollTo(anchor);
  }, [anchor, scrollTo]);

  // Sections above the target grow as their data arrives: follow the target until Gustavo scrolls.
  const onLayout = useCallback(
    (id: AjustesSection) => (event: LayoutChangeEvent) => {
      positions.current[id] = event.nativeEvent.layout.y;
      if (pending.current === id) scrollTo(id);
    },
    [scrollTo],
  );

  const anchorProps = (id: AjustesSection) => ({ onLayout: onLayout(id), testID: `ajustes-${id}` });

  return (
    <KeyboardAvoidingView style={styles.screen} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView
        ref={scroll}
        testID="screen-ajustes"
        style={styles.screen}
        contentContainerStyle={[pageContent, { paddingBottom: bottom }]}
        keyboardShouldPersistTaps="handled"
        automaticallyAdjustKeyboardInsets
        onScrollBeginDrag={() => {
          pending.current = null;
        }}
      >
        <PageHeader title="Ajustes" />
        <Button testID="ajustes-mapa-equipo" variant="ghost" onPress={() => router.push('/equipo')}>Mapa del equipo</Button>
        <Anchor {...anchorProps('maquina')}>
          <MaquinaSection />
        </Anchor>
        <Anchor {...anchorProps('orientacion')}>
          <OrientacionSection onFieldFocus={() => scrollTo('orientacion')} />
        </Anchor>
        <Anchor {...anchorProps('autonomia')}>
          <AutonomiaSection open={anchor === 'autonomia'} />
        </Anchor>
        <Anchor {...anchorProps('gasto')}>
          <GastoSection />
        </Anchor>
        <Anchor {...anchorProps('linkedin')}>
          <LinkedInSection returnParams={params} onDismissReturn={() => router.setParams({ linkedin: undefined, motivo: undefined })} />
        </Anchor>
        <Anchor {...anchorProps('captura')}>
          <CapturaSection />
        </Anchor>
        <Anchor {...anchorProps('notificaciones')}>
          <NotificacionesSection />
        </Anchor>
        <Anchor {...anchorProps('sabe')}>
          <SabeLink />
        </Anchor>
        <Anchor {...anchorProps('sesion')}>
          <SesionSection />
        </Anchor>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

function Anchor({ children, onLayout, testID }: { children: ReactNode; onLayout: (event: LayoutChangeEvent) => void; testID: string }) {
  return (
    <View onLayout={onLayout} testID={testID} collapsable={false}>
      {children}
    </View>
  );
}

const styles = StyleSheet.create({ screen: { flex: 1, backgroundColor: colors.paper } });
