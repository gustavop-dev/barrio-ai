import { Canvas, Group, Picture, Skia, useImage } from '@shopify/react-native-skia';
import { useEffect, useMemo, useState } from 'react';
import { PixelRatio, StyleSheet, View } from 'react-native';
import { GestureDetector, useExclusiveGestures, usePanGesture, usePinchGesture, useSimultaneousGestures, useTapGesture, type NativeGesture } from 'react-native-gesture-handler';
import Animated, { runOnJS, runOnUI, useAnimatedReaction, useAnimatedStyle, useSharedValue, type SharedValue } from 'react-native-reanimated';
import { PLAN_HEIGHT, PLAN_WIDTH, ZONE_LABELS, zoneAt } from '@compartido/scene/plan';
import { actorById, hitScene, type SceneState } from '@compartido/scene/runtime';
import { LIBRARY, ROLES, TEAMS, type CharacterId, type ZoneId } from '@compartido/scene/roles';
import type { StatusMap } from '@compartido/scene/activity';
import { Button, Note, Skeleton, T } from '@/components/ui';
import { officeGestures } from '@/theme/motion';
import { colors, radius, space } from '@/theme/tokens';
import ATLAS_IMAGE from '../../assets/brand/sprites-atlas.png';
import { Decorations, Monitors } from './Decorations';
import { Sprites } from './Sprites';
import { roomPicture } from './room';
import { clampPan, zoomAt } from './viewport';

export type ScenePick = { kind: 'role'; id: CharacterId } | { kind: 'zone'; id: ZoneId };
export interface OfficeCanvasProps {
  scene: SharedValue<SceneState>; width: number; height: number; scale: number;
  selectedRole: CharacterId | null; selectedZone: ZoneId | null;
  scrollGesture?: NativeGesture; visibleHeight?: number; statuses: StatusMap; onPick: (pick: ScenePick) => void;
}
/** A retry remounts only the atlas loader, not the simulation or its cursor. */
export function OfficeCanvas(props: OfficeCanvasProps) {
  const [attempt, setAttempt] = useState(0);
  return <LoadedCanvas key={attempt} {...props} retry={() => setAttempt((n) => n + 1)} />;
}
function LoadedCanvas({ scene, width, height, scale, selectedRole, selectedZone, scrollGesture, visibleHeight = height, statuses, onPick, retry }: OfficeCanvasProps & { retry: () => void }) {
  const [error, setError] = useState<Error | null>(null);
  const atlas = useImage(ATLAS_IMAGE, setError);
  const room = useMemo(() => atlas ? roomPicture(atlas) : null, [atlas]);
  const density = PixelRatio.get();
  const view = useSharedValue({ x: (width - PLAN_WIDTH * scale) / 2, y: 0, scale });
  const panStart = useSharedValue({ x: 0, y: 0 });
  const pinchStart = useSharedValue(scale);
  const pinching = useSharedValue(false);
  const [initialMatrix] = useState(() => Skia.Matrix());
  const matrix = useSharedValue(initialMatrix);
  useAnimatedReaction(() => view.value, (v) => {
    matrix.modify((m) => m.identity().translate(Math.round(v.x * density) / density, Math.round(v.y * density) / density).scale(v.scale));
  });
  useEffect(() => {
    runOnUI(() => { view.set({ x: (width - PLAN_WIDTH * scale) / 2, y: 0, scale }); })();
  }, [width, height, scale, view]);
  useEffect(() => {
    if (!selectedRole && !selectedZone) return;
    runOnUI(() => {
      const actor = selectedRole ? actorById(scene.value, selectedRole) : null;
      const box = selectedZone === 'biblioteca' ? LIBRARY.box : TEAMS.find((t) => t.id === selectedZone)?.box;
      const x = actor ? actor.x : box ? box[0] + box[2] / 2 : PLAN_WIDTH / 2;
      const y = actor ? actor.y - 14 : box ? box[1] + box[3] / 2 : 0;
      view.modify((v) => {
        v.x = clampPan(width / 2 - x * v.scale, width, PLAN_WIDTH * v.scale);
        v.y = clampPan(visibleHeight / 2 - y * v.scale, visibleHeight, PLAN_HEIGHT * v.scale);
        return v;
      });
    })();
  }, [selectedRole, selectedZone, visibleHeight, width, scene, view]);
  const pan = usePanGesture({
    block: scrollGesture, testID: 'office-pan', minDistance: officeGestures.panDistance, maxPointers: 1,
    onActivate: () => { 'worklet'; panStart.value.x = view.value.x; panStart.value.y = view.value.y; },
    onUpdate: (event) => {
      'worklet';
      if (pinching.value) return;
      view.modify((v) => {
        v.x = clampPan(panStart.value.x + event.translationX, width, PLAN_WIDTH * v.scale);
        v.y = clampPan(panStart.value.y + event.translationY, visibleHeight, PLAN_HEIGHT * v.scale);
        return v;
      });
    },
  });
  const pinch = usePinchGesture({
    block: scrollGesture, testID: 'office-pinch',
    onActivate: () => { 'worklet'; pinchStart.value = view.value.scale; pinching.value = true; },
    onUpdate: (event) => {
      'worklet';
      view.modify((v) => { zoomAt(v, pinchStart.value * event.scale, event.focalX, event.focalY, width, visibleHeight, scale, density); return v; });
    },
    onFinalize: () => { 'worklet'; pinching.value = false; },
  });
  const reset = useTapGesture({
    testID: 'office-reset', numberOfTaps: 2, maxDelay: officeGestures.doubleTapMs, maxDistance: officeGestures.tapDistance, maxDuration: officeGestures.tapDurationMs,
    onActivate: () => { 'worklet'; view.set({ x: (width - PLAN_WIDTH * scale) / 2, y: 0, scale }); },
  });
  const tap = useTapGesture({
    testID: 'office-tap', maxDistance: officeGestures.tapDistance, maxDuration: officeGestures.tapDurationMs,
    onActivate: (event) => {
      'worklet';
      const v = view.value;
      const x = (event.x - v.x) / v.scale; const y = (event.y - v.y) / v.scale;
      const role = hitScene(scene.value, x, y, officeGestures.touchTarget / v.scale, officeGestures.touchTarget / v.scale);
      if (role) runOnJS(onPick)({ kind: 'role', id: role });
      else { const zone = zoneAt(x, y); if (zone) runOnJS(onPick)({ kind: 'zone', id: zone }); }
    },
  });
  const taps = useExclusiveGestures(reset, tap);
  const gesture = useSimultaneousGestures(pan, pinch, taps);
  // Labels follow gestures only; walking never changes this view or invokes React.
  const labels = useAnimatedStyle(() => ({ transform: [
    { translateX: Math.round(view.value.x * density) / density }, { translateY: Math.round(view.value.y * density) / density },
    { scale: view.value.scale / scale },
  ] }));
  return <View style={{ width, height }}>
    <GestureDetector gesture={gesture}>
      <View style={[styles.stage, { width, height }]} testID="office-scene">
        <Canvas style={StyleSheet.absoluteFill} accessibilityRole="image" accessibilityLabel="La oficina en pixel art. Toca a un personaje para ver su rol o una zona para ver su equipo. Lo mismo está en la tira de equipos, debajo.">
          {atlas && room ? <Group matrix={matrix} antiAlias={false}>
            <Picture picture={room} />
            <Monitors atlas={atlas} scene={scene} />
            <Sprites atlas={atlas} scene={scene} />
            <Decorations scene={scene} selected={selectedRole} zone={selectedZone} />
          </Group> : null}
        </Canvas>
        <Animated.View pointerEvents="none" importantForAccessibility="no-hide-descendants" style={[styles.labels, { width: PLAN_WIDTH * scale, height: PLAN_HEIGHT * scale }, labels]}>
          {ZONE_LABELS.map((label) => <T key={label.zone} variant="etiqueta" maxFontSizeMultiplier={1.3} style={[styles.label, { left: label.at[0] * scale, top: label.at[1] * scale }]}>{label.text}</T>)}
          {ROLES.filter((r) => statuses[r.id] === 'diseno').map((r) => <T key={r.id} variant="etiqueta" style={[styles.label, { left: Math.max(4, Math.min(r.home[0] * scale - 45, PLAN_WIDTH * scale - 98)), top: (r.home[1] - 7) * scale }]}>EN DISEÑO</T>)}
        </Animated.View>
        {!atlas && !error ? <View style={styles.loading}><Skeleton variant="card" count={1} /></View> : null}
      </View>
    </GestureDetector>
    {error ? <View style={styles.error}><Note tone="error" title="No se pudo cargar el dibujo de la oficina." actions={<Button onPress={retry}>Reintentar</Button>} /></View> : null}
  </View>;
}
const styles = StyleSheet.create({
  stage: { overflow: 'hidden', backgroundColor: colors.paper },
  labels: { position: 'absolute', top: 0, left: 0, transformOrigin: 'top left' },
  label: { position: 'absolute', backgroundColor: colors.surface, borderColor: colors.line, borderWidth: 1, borderRadius: radius.pill, paddingHorizontal: space[1] },
  loading: { padding: space[4], marginTop: space[10] },
  error: { position: 'absolute', top: space[10], left: space[4], right: space[4] },
});
