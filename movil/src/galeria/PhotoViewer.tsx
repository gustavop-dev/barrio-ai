// The full-screen photo viewer of the Galería: swipe between photos (a paged list), pinch or
// double-tap to zoom, drag the zoomed photo around, and drag an unzoomed photo up or down to close.
// Every limit and spring comes from motion.ts (gestures.zoom, gestures.viewer, springs.zoomSettle).
import type { PhotoOutput } from '@compartido/api/capturas';
import { photoName } from '@compartido/logic/galeria';
import { useCallback, useRef, useState } from 'react';
import { FlatList, Modal, Pressable, StyleSheet, View, useWindowDimensions, type NativeScrollEvent, type NativeSyntheticEvent } from 'react-native';
import { GestureDetector, GestureHandlerRootView, usePanGesture, usePinchGesture, useSimultaneousGestures, useTapGesture } from 'react-native-gesture-handler';
import Animated, { runOnJS, useAnimatedStyle, useSharedValue, withSpring } from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Icon } from '@/components/icons';
import { ApiImage, T } from '@/components/ui';
import { gestures, layout, spring } from '@/theme/motion';
import { colors, radius, shell, space } from '@/theme/tokens';

function clamp(value: number, min: number, max: number): number {
  'worklet';
  return Math.min(max, Math.max(min, value));
}

/** One page: the photo fitted to the screen, with its own zoom. */
function ZoomablePhoto({
  photo,
  width,
  height,
  onZoomChange,
  onClose,
}: {
  photo: PhotoOutput;
  width: number;
  height: number;
  onZoomChange: (zoomed: boolean) => void;
  onClose: () => void;
}) {
  const [zoomed, setZoomed] = useState(false);
  const scale = useSharedValue(1);
  const savedScale = useSharedValue(1);
  const x = useSharedValue(0);
  const y = useSharedValue(0);
  const savedX = useSharedValue(0);
  const savedY = useSharedValue(0);
  const drag = useSharedValue(0);

  const report = useCallback(
    (next: boolean) => {
      setZoomed(next);
      onZoomChange(next);
    },
    [onZoomChange],
  );

  /** Keeps the zoomed photo covering the screen: no empty border past its edges. */
  const settle = (nextScale: number) => {
    'worklet';
    const maxX = (width * (nextScale - 1)) / 2;
    const maxY = (height * (nextScale - 1)) / 2;
    const toX = clamp(x.value, -maxX, maxX);
    const toY = clamp(y.value, -maxY, maxY);
    x.set(withSpring(toX, spring('zoomSettle')));
    y.set(withSpring(toY, spring('zoomSettle')));
    savedX.set(toX);
    savedY.set(toY);
  };

  const pinch = usePinchGesture({
    onUpdate: (event) => {
      'worklet';
      scale.set(clamp(savedScale.value * event.scale, 1, gestures.zoom.maxScale));
    },
    onDeactivate: () => {
      'worklet';
      const next = scale.value;
      savedScale.set(next);
      if (next <= 1) {
        x.set(withSpring(0, spring('zoomSettle')));
        y.set(withSpring(0, spring('zoomSettle')));
        savedX.set(0);
        savedY.set(0);
      } else {
        settle(next);
      }
      runOnJS(report)(next > 1);
    },
  });

  // Moving around a zoomed photo (the pager is locked meanwhile).
  const pan = usePanGesture({
    enabled: zoomed,
    onUpdate: (event) => {
      'worklet';
      x.set(savedX.value + event.translationX);
      y.set(savedY.value + event.translationY);
    },
    onDeactivate: () => {
      'worklet';
      settle(scale.value);
    },
  });

  // An unzoomed photo dragged up or down closes the viewer; sideways is the pager's.
  const dismiss = usePanGesture({
    enabled: !zoomed,
    activeOffsetY: [-gestures.viewer.activeOffsetY, gestures.viewer.activeOffsetY],
    failOffsetX: [-gestures.viewer.failOffsetX, gestures.viewer.failOffsetX],
    onUpdate: (event) => {
      'worklet';
      drag.set(event.translationY);
    },
    onDeactivate: (event) => {
      'worklet';
      if (Math.abs(event.translationY) > gestures.viewer.dismissDistance || Math.abs(event.velocityY) > gestures.viewer.dismissVelocity) {
        runOnJS(onClose)();
      } else {
        drag.set(withSpring(0, spring('zoomSettle')));
      }
    },
  });

  const doubleTap = useTapGesture({
    numberOfTaps: 2,
    maxDelay: gestures.zoom.doubleTapMaxDelayMs,
    onActivate: (event) => {
      'worklet';
      if (scale.value > 1) {
        scale.set(withSpring(1, spring('zoomSettle')));
        x.set(withSpring(0, spring('zoomSettle')));
        y.set(withSpring(0, spring('zoomSettle')));
        savedScale.set(1);
        savedX.set(0);
        savedY.set(0);
        runOnJS(report)(false);
        return;
      }
      const next = gestures.zoom.doubleTapScale;
      const maxX = (width * (next - 1)) / 2;
      const maxY = (height * (next - 1)) / 2;
      const toX = clamp((width / 2 - event.x) * (next - 1), -maxX, maxX);
      const toY = clamp((height / 2 - event.y) * (next - 1), -maxY, maxY);
      scale.set(withSpring(next, spring('zoomSettle')));
      x.set(withSpring(toX, spring('zoomSettle')));
      y.set(withSpring(toY, spring('zoomSettle')));
      savedScale.set(next);
      savedX.set(toX);
      savedY.set(toY);
      runOnJS(report)(true);
    },
  });

  const gesture = useSimultaneousGestures(doubleTap, pinch, pan, dismiss);

  const moved = useAnimatedStyle(() => ({
    transform: [{ translateX: x.value }, { translateY: y.value + drag.value }, { scale: scale.value }],
    opacity: 1 - gestures.viewer.dragFade * Math.min(1, Math.abs(drag.value) / gestures.viewer.dismissDistance),
  }));

  return (
    <GestureDetector gesture={gesture}>
      <Animated.View style={[{ width, height }, styles.page, moved]}>
        <ApiImage path={photo.url} style={{ width, height }} contentFit="contain" accessibilityLabel={photoName(photo)} recyclingKey={photo.id} />
      </Animated.View>
    </GestureDetector>
  );
}

export function PhotoViewer({
  photos,
  index,
  onIndex,
  onClose,
}: {
  photos: readonly PhotoOutput[];
  /** The photo shown first. */
  index: number;
  /** The photo on screen changed (a swipe or a screen-reader action). */
  onIndex: (index: number) => void;
  onClose: () => void;
}) {
  const { width, height } = useWindowDimensions();
  const insets = useSafeAreaInsets();
  const list = useRef<FlatList<PhotoOutput>>(null);
  const [current, setCurrent] = useState(() => Math.min(Math.max(0, index), Math.max(0, photos.length - 1)));
  const [zoomed, setZoomed] = useState(false);
  const photo = photos[current];

  const show = useCallback(
    (next: number) => {
      if (next < 0 || next >= photos.length) return;
      setCurrent(next);
      onIndex(next);
    },
    [photos.length, onIndex],
  );

  const onSettled = (event: NativeSyntheticEvent<NativeScrollEvent>) => {
    const next = Math.round(event.nativeEvent.contentOffset.x / Math.max(1, width));
    if (next !== current) show(next);
  };

  const step = (delta: number) => {
    const next = current + delta;
    if (next < 0 || next >= photos.length) return;
    list.current?.scrollToIndex({ index: next, animated: true });
    show(next);
  };

  return (
    <Modal transparent visible animationType="none" statusBarTranslucent navigationBarTranslucent onRequestClose={onClose}>
      <GestureHandlerRootView style={styles.root}>
        <Animated.View entering={layout.viewerIn()} exiting={layout.viewerOut()} style={styles.backdrop} testID="photo-viewer">
          <FlatList
            ref={list}
            data={photos as PhotoOutput[]}
            keyExtractor={(item) => item.id}
            horizontal
            pagingEnabled
            scrollEnabled={!zoomed}
            showsHorizontalScrollIndicator={false}
            initialScrollIndex={current}
            getItemLayout={(_, i) => ({ length: width, offset: width * i, index: i })}
            onMomentumScrollEnd={onSettled}
            windowSize={3}
            initialNumToRender={1}
            maxToRenderPerBatch={2}
            accessible
            accessibilityRole="adjustable"
            accessibilityLabel={photo ? `${photoName(photo)}. Foto ${current + 1} de ${photos.length}` : 'Foto'}
            accessibilityActions={[
              { name: 'increment', label: 'Foto siguiente' },
              { name: 'decrement', label: 'Foto anterior' },
            ]}
            onAccessibilityAction={(event) => step(event.nativeEvent.actionName === 'increment' ? 1 : -1)}
            renderItem={({ item }) => <ZoomablePhoto photo={item} width={width} height={height} onZoomChange={setZoomed} onClose={onClose} />}
          />
          <View style={[styles.top, { paddingTop: insets.top + space[2] }]} pointerEvents="box-none">
            <T variant="detalle" color={colors.paper} testID="photo-viewer-count">
              {photos.length > 1 ? `${current + 1} de ${photos.length}` : ''}
            </T>
            <Pressable accessibilityRole="button" accessibilityLabel="Cerrar" onPress={onClose} style={styles.close} hitSlop={4} testID="photo-viewer-close">
              <Icon name="cerrar" size={24} color={colors.paper} />
            </Pressable>
          </View>
          {photo ? (
            <View style={[styles.bottom, { paddingBottom: insets.bottom + space[4] }]} pointerEvents="none">
              <T variant="detalle" color={colors.paper}>
                {photo.label}
                {photo.used_in?.text ? ` · ${photo.used_in.text}` : ''}
              </T>
            </View>
          ) : null}
        </Animated.View>
      </GestureHandlerRootView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  backdrop: { flex: 1, backgroundColor: colors.ink },
  page: { alignItems: 'center', justifyContent: 'center' },
  top: { position: 'absolute', top: 0, left: 0, right: 0, paddingHorizontal: space[4], flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  close: { width: shell.touch + 4, height: shell.touch + 4, borderRadius: radius.pill, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.backdrop },
  bottom: { position: 'absolute', bottom: 0, left: 0, right: 0, paddingHorizontal: space[4], paddingTop: space[3], backgroundColor: colors.backdrop },
});
