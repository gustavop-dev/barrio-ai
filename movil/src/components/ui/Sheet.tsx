// Bottom sheet (capture sheet, confirmations), as in MovHojas with the backdrop on: a Modal with the
// tinta backdrop. The sheet's position `p` (0 closed, 1 open at its content height) rises on FIRM and
// follows the handle; past the top it resists (rubber band). Released, it is projected along its
// velocity: under half its height it closes, otherwise it goes back up. The backdrop follows `p`, and
// opening is a snap («HÁPTICO · LEVE»). Inside a Modal Android starts a new root, so it brings its
// GestureHandlerRootView.
import { createContext, useCallback, useContext, useEffect, useImperativeHandle, useRef, type ReactNode, type Ref } from 'react';
import { KeyboardAvoidingView, Modal, Pressable, StyleSheet, View, useWindowDimensions } from 'react-native';
import { GestureDetector, GestureHandlerRootView, usePanGesture } from 'react-native-gesture-handler';
import Animated, {
  cancelAnimation,
  runOnJS,
  useAnimatedReaction,
  useAnimatedRef,
  useAnimatedStyle,
  useScrollOffset,
  useSharedValue,
  withSpring,
  type SharedValue,
} from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { haptic, rubberBand, sheetMotion, spring } from '@/theme/motion';
import { colors, radius, space } from '@/theme/tokens';
import { ToastOutlet } from './Toast';

/**
 * MovHojas: where a released sheet goes. `position` and the `snaps` share one unit (a fraction of the
 * screen, or of the sheet); `velocity` is that unit per second, positive upwards. The release is
 * projected `sheetMotion.projectionS` ahead; under `closeBelow` of the lowest snap it closes (0),
 * otherwise it goes to the nearest snap.
 */
export function settleSnap(position: number, velocity: number, snaps: readonly number[]): number {
  'worklet';
  const projected = position + velocity * sheetMotion.projectionS;
  const lowest = snaps[0] ?? 1;
  if (projected < lowest * sheetMotion.closeBelow) return 0;
  let best = lowest;
  for (const snap of snaps) if (Math.abs(snap - projected) < Math.abs(best - projected)) best = snap;
  return best;
}

export interface SheetHandle {
  /** Slides the sheet down, then calls onClose (as the backdrop does). */
  dismiss: () => void;
  /** Slides the sheet down without closing it: the owner closes it later (the capture's «Guardar»). */
  hide: () => void;
}

/** Where the sheet is, for choreographies drawn over it (the capture ball). Layout values are in the modal's coordinates. */
export interface SheetFrame {
  /** 0 closed, 1 open. */
  progress: SharedValue<number>;
  /** The panel's height. */
  height: SharedValue<number>;
  /** The panel's top when open. */
  panelY: SharedValue<number>;
  /** Where the scrolling content starts inside the panel. */
  contentX: SharedValue<number>;
  contentY: SharedValue<number>;
  /** How far the content is scrolled. */
  scroll: SharedValue<number>;
  /** The modal's size. */
  width: SharedValue<number>;
  rootHeight: SharedValue<number>;
  /** True once the sheet is dragged or closing. */
  moved: SharedValue<boolean>;
}

const SheetFrameContext = createContext<SheetFrame | null>(null);

/** The frame of the sheet around this component, or null outside a sheet. */
export function useSheetFrame(): SheetFrame | null {
  return useContext(SheetFrameContext);
}

export interface SheetProps {
  /** Accessible name of the sheet. */
  label: string;
  onClose: () => void;
  children: ReactNode;
  /** Header that stays put above the scrolling content (handle included by the sheet). */
  header?: ReactNode;
  /** While another dialog is on top: the back button and the backdrop do nothing. */
  suspended?: boolean;
  /** Asked before closing from the backdrop, the back button or a drag; false keeps the sheet (the caller asks first). */
  canClose?: () => boolean;
  /** Drawn over the whole modal, above the sheet, without touches (the capture's ball and envelope). */
  overlay?: ReactNode;
  /** The light haptic when it opens (MovHojas); off when the opening is part of another choreography. */
  openHaptic?: boolean;
  /** Fades the header and the content (not the handle), for a choreography that empties the sheet. */
  contentOpacity?: SharedValue<number>;
  ref?: Ref<SheetHandle>;
  testID?: string;
}

export function Sheet({ label, onClose, children, header, suspended, canClose, overlay, openHaptic = true, contentOpacity, ref, testID }: SheetProps) {
  const window = useWindowDimensions();
  const insets = useSafeAreaInsets();
  const progress = useSharedValue(0);
  const height = useSharedValue(window.height);
  const panelY = useSharedValue(0);
  const contentX = useSharedValue(0);
  const contentY = useSharedValue(0);
  const width = useSharedValue(window.width);
  const rootHeight = useSharedValue(window.height);
  const moved = useSharedValue(false);
  const closing = useSharedValue(false);
  const notify = useSharedValue(false);
  const start = useSharedValue(0);
  const from = useSharedValue(0);
  const scrollRef = useAnimatedRef<Animated.ScrollView>();
  const scroll = useScrollOffset(scrollRef);
  const closed = useRef(false);
  const latestClose = useRef(onClose);
  const firm = spring('sheetOpen');

  useEffect(() => {
    latestClose.current = onClose;
  }, [onClose]);

  // Opening: p springs to 1 (FIRM), and it is a snap. Only when it mounts.
  const opened = useRef(false);
  useEffect(() => {
    if (opened.current) return;
    opened.current = true;
    progress.set(withSpring(1, spring('sheetOpen')));
    if (openHaptic) haptic('sheetSnap');
  }, [progress, openHaptic]);

  const finish = useCallback(() => {
    if (closed.current) return;
    closed.current = true;
    latestClose.current();
  }, []);

  // The sheet closes on FIRM too; it is gone the moment p reaches 0, before the spring settles.
  useAnimatedReaction(
    () => closing.value && progress.value <= 0,
    (gone, was) => {
      if (gone && !was && notify.value) runOnJS(finish)();
    },
  );

  const slide = useCallback(
    (thenClose: boolean) => {
      if (thenClose) notify.set(true);
      if (closing.get()) return;
      closing.set(true);
      moved.set(true);
      progress.set(withSpring(0, spring('sheetOpen')));
    },
    [closing, moved, notify, progress],
  );
  const dismiss = useCallback(() => slide(true), [slide]);
  const hide = useCallback(() => slide(false), [slide]);
  useImperativeHandle(ref, () => ({ dismiss, hide }), [dismiss, hide]);

  const requestClose = useCallback(() => {
    if (!suspended && (canClose?.() ?? true)) dismiss();
  }, [suspended, canClose, dismiss]);

  /** End of a drag that wants to close: close (unless another dialog is on top or the caller asks first), or go back up. */
  const release = useCallback(() => {
    if (!suspended && (canClose?.() ?? true)) dismiss();
    else progress.set(withSpring(1, spring('sheetOpen')));
  }, [suspended, canClose, dismiss, progress]);

  const drag = usePanGesture({
    testID: 'sheet-drag',
    activeOffsetY: [-sheetMotion.activation, sheetMotion.activation],
    onActivate: (event) => {
      'worklet';
      if (closing.value) return;
      cancelAnimation(progress);
      moved.set(true);
      start.set(progress.value);
      from.set(event.translationY);
    },
    onUpdate: (event) => {
      'worklet';
      if (closing.value) return;
      const raw = start.value - (event.translationY - from.value) / height.value;
      progress.set(Math.max(0, rubberBand(raw, 1)));
    },
    onDeactivate: (event) => {
      'worklet';
      if (closing.value) return;
      if (settleSnap(progress.value, -event.velocityY / height.value, [1]) === 0) runOnJS(release)();
      else progress.set(withSpring(1, firm));
    },
  });

  const panel = useAnimatedStyle(() => ({
    transform: [{ translateY: (1 - Math.max(0, progress.value)) * (height.value + sheetMotion.closedGap) }],
  }));
  const shade = useAnimatedStyle(() => ({ opacity: Math.min(1, Math.max(0, progress.value)) }));
  const faded = useAnimatedStyle(() => ({ opacity: contentOpacity ? contentOpacity.value : 1 }));

  const frame: SheetFrame = { progress, height, panelY, contentX, contentY, scroll, width, rootHeight, moved };

  return (
    <Modal transparent visible animationType="none" statusBarTranslucent navigationBarTranslucent onRequestClose={requestClose}>
      <SheetFrameContext.Provider value={frame}>
        <GestureHandlerRootView
          style={styles.root}
          testID={testID ? `${testID}-modal` : undefined}
          onLayout={(event) => {
            width.set(event.nativeEvent.layout.width);
            rootHeight.set(event.nativeEvent.layout.height);
          }}
        >
          <Animated.View style={[StyleSheet.absoluteFill, styles.backdrop, shade]}>
            <Pressable style={StyleSheet.absoluteFill} accessibilityLabel="Cerrar" accessibilityRole="button" onPress={requestClose} />
          </Animated.View>
          {/* The app is drawn edge to edge, so on Android too the window no longer shrinks for the keyboard: the
              sheet pads itself by it and shrinks (flexShrink), so a note and the buttons under it stay above it. */}
          <KeyboardAvoidingView behavior="padding" style={styles.avoid} pointerEvents="box-none">
            <Animated.View
              testID={testID}
              accessibilityViewIsModal
              accessibilityLabel={label}
              onLayout={(event) => {
                height.set(event.nativeEvent.layout.height);
                panelY.set(event.nativeEvent.layout.y);
              }}
              style={[styles.sheet, { maxHeight: window.height * 0.94, paddingBottom: space[4] + insets.bottom }, panel]}
            >
              {/* Under the panel, so the rubber band past the top never opens a gap. */}
              <View pointerEvents="none" style={[styles.skirt, { height: window.height }]} />
              <GestureDetector gesture={drag}>
                <View style={styles.grab}>
                  <View style={styles.handle} />
                  {header ? <Animated.View style={faded}>{header}</Animated.View> : null}
                </View>
              </GestureDetector>
              <Animated.ScrollView
                ref={scrollRef}
                onLayout={(event) => {
                  contentX.set(event.nativeEvent.layout.x);
                  contentY.set(event.nativeEvent.layout.y);
                }}
                keyboardShouldPersistTaps="handled"
                style={faded}
                contentContainerStyle={styles.content}
                showsVerticalScrollIndicator={false}
              >
                {children}
              </Animated.ScrollView>
            </Animated.View>
          </KeyboardAvoidingView>
          {overlay ? (
            <View pointerEvents="none" style={StyleSheet.absoluteFill}>
              {overlay}
            </View>
          ) : null}
          {/* A toast shown while this sheet is open is drawn here, in its window: in the app's it would sit under it. */}
          <ToastOutlet />
        </GestureHandlerRootView>
      </SheetFrameContext.Provider>
    </Modal>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  backdrop: { backgroundColor: colors.backdrop },
  avoid: { flex: 1, justifyContent: 'flex-end' },
  sheet: {
    flexShrink: 1,
    backgroundColor: colors.surface,
    borderTopLeftRadius: radius.sheet,
    borderTopRightRadius: radius.sheet,
    paddingHorizontal: space[4],
    paddingTop: space[3],
  },
  skirt: { position: 'absolute', top: '100%', left: 0, right: 0, backgroundColor: colors.surface },
  grab: { gap: space[2], paddingBottom: space[2] },
  handle: { alignSelf: 'center', width: 40, height: 4, borderRadius: radius.pill, backgroundColor: colors.line },
  content: { gap: 14, paddingBottom: space[2] },
});
