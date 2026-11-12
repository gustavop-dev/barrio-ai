import { Canvas, Group, Picture, Skia, useImage } from '@shopify/react-native-skia';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { PixelRatio, StyleSheet, View } from 'react-native';
import { GestureDetector, useExclusiveGestures, usePanGesture, usePinchGesture, useSimultaneousGestures, useTapGesture, type NativeGesture } from 'react-native-gesture-handler';
import Animated, { cancelAnimation, runOnJS, runOnUI, useAnimatedReaction, useAnimatedStyle, useSharedValue, withDecay, withSpring, type SharedValue } from 'react-native-reanimated';
import { PLAN_HEIGHT, PLAN_WIDTH, ZONE_LABELS, zoneAt } from '@compartido/scene/plan';
import { actorById, hitScene, type SceneState } from '@compartido/scene/runtime';
import { LIBRARY, ROLES, TEAMS, type CharacterId, type ZoneId } from '@compartido/scene/roles';
import type { StatusMap } from '@compartido/scene/activity';
import { Button, Note, Skeleton, T } from '@/components/ui';
import { officeGestures, rubberBand, spring } from '@/theme/motion';
import { colors, radius, space } from '@/theme/tokens';
import ATLAS_IMAGE from '../../assets/brand/sprites-atlas.png';
import { Decorations, SceneFloor, SceneLights } from './Decorations';
import { Sprites } from './Sprites';
import { roomPicture } from './room';
import { clampPan, zoomAt } from './viewport';

const ZONE_NAME: Record<ZoneId, string> = { ...Object.fromEntries(TEAMS.map((team) => [team.id, team.name])), biblioteca: LIBRARY.name } as Record<ZoneId, string>;

export type ScenePick = { kind: 'role'; id: CharacterId } | { kind: 'zone'; id: ZoneId };
/** Where the camera opens: the top of the office, or the game room at the bottom when nobody works. */
export type SceneFocus = 'arriba' | 'sala';
export interface OfficeCanvasProps {
  scene: SharedValue<SceneState>; width: number; height: number; scale: number;
  selectedRole: CharacterId | null; selectedZone: ZoneId | null;
  scrollGesture?: NativeGesture; visibleHeight?: number; statuses: StatusMap; onPick: (pick: ScenePick) => void;
  /** Applied while the person has not moved the scene yet; a later change never takes the camera from them. */
  focus?: SceneFocus | null;
  /** The scene fills the screen, so the pull to refresh starts on it: a drag down from the top of the plan. */
  onPullRefresh?: () => void;
}
function restingY(focus: SceneFocus | null | undefined, height: number, content: number) {
  'worklet';
  return focus === 'sala' ? clampPan(height - content, height, content) : clampPan(0, height, content);
}
/** A retry remounts only the atlas loader, not the simulation or its cursor. */
export function OfficeCanvas(props: OfficeCanvasProps) {
  const [attempt, setAttempt] = useState(0);
  return <LoadedCanvas key={attempt} {...props} retry={() => setAttempt((n) => n + 1)} />;
}
function LoadedCanvas({ scene, width, height, scale, selectedRole, selectedZone, scrollGesture, visibleHeight = height, statuses, onPick, focus, onPullRefresh, retry }: OfficeCanvasProps & { retry: () => void }) {
  const [error, setError] = useState<Error | null>(null);
  const atlas = useImage(ATLAS_IMAGE, setError);
  const room = useMemo(() => atlas ? roomPicture(atlas) : null, [atlas]);
  const density = PixelRatio.get();
  const view = useSharedValue({ x: (width - PLAN_WIDTH * scale) / 2, y: restingY(focus, height, PLAN_HEIGHT * scale), scale });
  const panStart = useSharedValue({ x: 0, y: 0, top: false });
  const pinchStart = useSharedValue(scale);
  const pinching = useSharedValue(false);
  // Once the person pans, zooms, taps or picks, the opening focus no longer moves the camera.
  const touched = useSharedValue(false);
  // How far the plan follows a pull down from its top (rubber band); it springs back on release.
  const pull = useSharedValue(0);
  const [springBack] = useState(() => spring('snapBack'));
  // Let go with some speed, the plan glides on like a scroll: it slows down and bounces at the plan's ends (Gustavo, 11/11:
  // it stopped dead under the finger and felt rigid). The glide runs on two numbers of its own, copied into the view while
  // it lasts. Any touch on the scene and any other move of the camera stop it.
  const glideX = useSharedValue(0);
  const glideY = useSharedValue(0);
  const gliding = useSharedValue(false);
  // A touch that stops a glide only stops it, as in a scroll: it does not pick what is under the finger.
  const caught = useSharedValue(false);
  useAnimatedReaction(() => (gliding.get() ? { x: glideX.get(), y: glideY.get() } : null), (glide) => {
    if (glide) view.modify((v) => { v.x = glide.x; v.y = glide.y; return v; });
  });
  /** Stops a glide in course; true when there was one. */
  const stopGlide = useCallback(() => {
    'worklet';
    if (!gliding.get()) return false;
    cancelAnimation(glideX); cancelAnimation(glideY);
    gliding.set(false);
    return true;
  }, [glideX, glideY, gliding]);
  const focusRef = useRef(focus);
  useEffect(() => { focusRef.current = focus; }, [focus]);
  // The zone labels are the way into a team (the team strip under the scene is gone): their boxes in logical pixels,
  // measured once laid out, take a tap before the characters under them. The boxes gather on the JS side and each
  // write carries all of them: the labels lay out in one batch, and a shared value read back on JS between two writes
  // could still be the old one, so a read-modify-write per label kept only the last label (QA run 43091761036).
  const measured = useRef<Record<string, readonly [number, number, number, number]>>({});
  const labelBoxes = useSharedValue<Record<string, readonly [number, number, number, number]>>({});
  const [initialMatrix] = useState(() => Skia.Matrix());
  const matrix = useSharedValue(initialMatrix);
  useAnimatedReaction(() => ({ x: view.value.x, y: view.value.y + pull.value, scale: view.value.scale }), (v) => {
    matrix.modify((m) => m.identity().translate(Math.round(v.x * density) / density, Math.round(v.y * density) / density).scale(v.scale));
  });
  // A new size (a banner over the scene, the panel opening or closing, a rotation). Before the person moves the scene it
  // rests on its focus. Afterwards it keeps their place, only clamped to the new bounds: the pause banner no longer sends
  // the camera back to the game room, and a closed panel leaves no blank under the plan (QA run 43125990840).
  useEffect(() => {
    const at = focusRef.current;
    runOnUI(() => {
      stopGlide();
      if (!touched.get()) {
        view.set({ x: (width - PLAN_WIDTH * scale) / 2, y: restingY(at, visibleHeight, PLAN_HEIGHT * scale), scale });
        return;
      }
      view.modify((v) => {
        v.scale = Math.max(v.scale, scale);
        v.x = clampPan(v.x, width, PLAN_WIDTH * v.scale);
        v.y = clampPan(v.y, visibleHeight, PLAN_HEIGHT * v.scale);
        return v;
      });
    })();
  }, [width, visibleHeight, scale, view, touched, stopGlide]);
  useEffect(() => {
    if (!focus) return;
    runOnUI(() => {
      if (touched.get()) return;
      view.modify((v) => { v.y = restingY(focus, height, PLAN_HEIGHT * v.scale); return v; });
    })();
  }, [focus, height, touched, view]);
  useEffect(() => {
    if (!selectedRole && !selectedZone) return;
    runOnUI(() => {
      stopGlide();
      touched.set(true);
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
  }, [selectedRole, selectedZone, visibleHeight, width, scene, view, touched, stopGlide]);
  const pan = usePanGesture({
    block: scrollGesture, testID: 'office-pan', minDistance: officeGestures.panDistance, maxPointers: 1,
    onBegin: () => { 'worklet'; caught.set(stopGlide()); },
    onActivate: () => {
      'worklet';
      touched.set(true);
      panStart.value.x = view.value.x; panStart.value.y = view.value.y;
      panStart.value.top = view.value.y >= clampPan(0, visibleHeight, PLAN_HEIGHT * view.value.scale) - 0.5;
    },
    onUpdate: (event) => {
      'worklet';
      if (pinching.value) return;
      const y = panStart.value.y + event.translationY;
      view.modify((v) => {
        v.x = clampPan(panStart.value.x + event.translationX, width, PLAN_WIDTH * v.scale);
        v.y = clampPan(y, visibleHeight, PLAN_HEIGHT * v.scale);
        return v;
      });
      // Past either end the plan gives under the finger, as a scroll does; from the top it is also the pull to refresh.
      const past = y - view.value.y;
      pull.set(Math.sign(past) * rubberBand(Math.abs(past), 0));
    },
    onDeactivate: (event) => {
      'worklet';
      const pulled = panStart.value.top && !pinching.value && event.translationY >= officeGestures.pullRefresh && event.translationY > Math.abs(event.translationX);
      if (onPullRefresh && pulled && !event.canceled) runOnJS(onPullRefresh)();
      // Let go past an end, the plan only springs back (onFinalize); inside it, it glides on.
      if (event.canceled || pinching.value || pull.get() !== 0) return;
      const v = view.value;
      const planWidth = PLAN_WIDTH * v.scale; const planHeight = PLAN_HEIGHT * v.scale;
      const decay = (velocity: number, viewport: number, content: number) => {
        'worklet';
        return withDecay({
          velocity, deceleration: officeGestures.flingDeceleration, rubberBandEffect: true, rubberBandFactor: officeGestures.flingBounce,
          clamp: [clampPan(-Infinity, viewport, content), clampPan(Infinity, viewport, content)],
        });
      };
      glideX.set(v.x); glideY.set(v.y); gliding.set(true);
      // Sideways only when zoomed in: at the opening size the plan fills the width and never moves sideways.
      if (planWidth > width) glideX.set(decay(event.velocityX, width, planWidth));
      if (planHeight > visibleHeight) glideY.set(decay(event.velocityY, visibleHeight, planHeight));
    },
    onFinalize: () => { 'worklet'; pull.set(withSpring(0, springBack)); },
  });
  const pinch = usePinchGesture({
    block: scrollGesture, testID: 'office-pinch',
    onActivate: () => { 'worklet'; stopGlide(); touched.set(true); pinchStart.value = view.value.scale; pinching.value = true; },
    onUpdate: (event) => {
      'worklet';
      view.modify((v) => { zoomAt(v, pinchStart.value * event.scale, event.focalX, event.focalY, width, visibleHeight, scale, density); return v; });
    },
    onFinalize: () => { 'worklet'; pinching.value = false; },
  });
  const reset = useTapGesture({
    testID: 'office-reset', numberOfTaps: 2, maxDelay: officeGestures.doubleTapMs, maxDistance: officeGestures.tapDistance, maxDuration: officeGestures.tapDurationMs,
    // Back to the opening size, at the top of the office.
    onActivate: () => { 'worklet'; stopGlide(); touched.set(true); view.set({ x: (width - PLAN_WIDTH * scale) / 2, y: clampPan(0, visibleHeight, PLAN_HEIGHT * scale), scale }); },
  });
  const tap = useTapGesture({
    testID: 'office-tap', maxDistance: officeGestures.tapDistance, maxDuration: officeGestures.tapDurationMs,
    onActivate: (event) => {
      'worklet';
      if (caught.get()) return;
      touched.set(true);
      const v = view.value;
      const x = (event.x - v.x) / v.scale; const y = (event.y - v.y) / v.scale;
      const boxes = labelBoxes.value;
      for (const zone of Object.keys(boxes)) {
        const [bx, by, bw, bh] = boxes[zone]!;
        if (x >= bx && x < bx + bw && y >= by && y < by + bh) { runOnJS(onPick)({ kind: 'zone', id: zone as ZoneId }); return; }
      }
      const role = hitScene(scene.value, x, y, officeGestures.touchTarget / v.scale, officeGestures.touchTarget / v.scale);
      if (role) runOnJS(onPick)({ kind: 'role', id: role });
      else { const zone = zoneAt(x, y); if (zone) runOnJS(onPick)({ kind: 'zone', id: zone }); }
    },
  });
  const taps = useExclusiveGestures(reset, tap);
  const gesture = useSimultaneousGestures(pan, pinch, taps);
  // Labels follow gestures only; walking never changes this view or invokes React.
  const labels = useAnimatedStyle(() => ({ transform: [
    { translateX: Math.round(view.value.x * density) / density }, { translateY: Math.round((view.value.y + pull.value) * density) / density },
    { scale: view.value.scale / scale },
  ] }));
  return <View style={{ width, height }}>
    <GestureDetector gesture={gesture}>
      <View style={[styles.stage, { width, height }]} testID="office-scene">
        <Canvas style={StyleSheet.absoluteFill} accessibilityRole="image" accessibilityLabel="La oficina en pixel art. Toca a un personaje para ver su rol o una zona para ver su equipo. Los nombres de las zonas también abren su equipo.">
          {atlas && room ? <Group matrix={matrix} antiAlias={false}>
            <Picture picture={room} />
            <SceneFloor scene={scene} />
            <Sprites atlas={atlas} scene={scene} />
            <SceneLights scene={scene} />
            <Decorations scene={scene} selected={selectedRole} zone={selectedZone} />
          </Group> : null}
        </Canvas>
        {/* Touches pass through to the scene's tap, which hit-tests the measured labels; a screen reader activates them. */}
        <Animated.View pointerEvents="none" style={[styles.labels, { width: PLAN_WIDTH * scale, height: PLAN_HEIGHT * scale }, labels]}>
          {ZONE_LABELS.map((label) => <T key={label.zone} variant="etiqueta" maxFontSizeMultiplier={1.3} testID={`zone-label-${label.zone}`}
            accessibilityRole="button" accessibilityLabel={ZONE_NAME[label.zone]} accessibilityState={{ selected: selectedZone === label.zone }}
            accessibilityActions={[{ name: 'activate' }]} onAccessibilityAction={() => onPick({ kind: 'zone', id: label.zone })}
            onLayout={(event) => {
              const { x, y, width: w, height: h } = event.nativeEvent.layout;
              measured.current = { ...measured.current, [label.zone]: [x / scale, y / scale, w / scale, h / scale] };
              labelBoxes.value = measured.current;
            }}
            style={[styles.label, { left: label.at[0] * scale, top: label.at[1] * scale }]}>{label.text}</T>)}
          {ROLES.filter((r) => statuses[r.id] === 'diseno').map((r) => <T key={r.id} variant="etiqueta" accessible={false} importantForAccessibility="no" style={[styles.label, { left: Math.max(4, Math.min(r.home[0] * scale - 45, PLAN_WIDTH * scale - 98)), top: (r.home[1] - 7) * scale }]}>EN DISEÑO</T>)}
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
