// The shared element of MovDetalle: the portrait and the name of a person fly from their row in a
// list into the header of the person card while the card is pushed, and the rest of the card enters
// staggered (navLayout.cardBlock). «‹ Personas», Android back or the edge drag send them back.
//
// Reanimated's shared element transitions need a native build flag (ENABLE_SHARED_ELEMENT_TRANSITIONS,
// off in Expo Go), so the flight is an overlay: the row measures its pieces when tapped, the card
// header registers where they land, and DetailScreen draws copies above both while the real pieces
// hide. Everything moves on the UI thread with the `flight` spring; with reduced motion nothing flies.
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode, type RefObject } from 'react';
import { StyleSheet, View, type LayoutChangeEvent } from 'react-native';
import Animated, { interpolateColor, makeMutable, runOnJS, useAnimatedStyle, useSharedValue, withSpring, type SharedValue } from 'react-native-reanimated';
import { navSpring } from '@/theme/motion';
import { colors, radius, type as typeScale } from '@/theme/tokens';
import { T } from '@/components/ui/Text';
import { layerAt } from './push';

export interface Rect {
  x: number;
  y: number;
  width: number;
  height: number;
}

/** Where the name is drawn: its top-left, its scale over the row's type (cuerpo) and its colour. */
export interface LabelEnd {
  x: number;
  y: number;
  scale: number;
  color: string;
}

/** One end of a flight: the portrait's box and the name. */
export interface FlightEnd {
  avatar: Rect;
  label: LabelEnd;
}

/** A tapped row: who it is and where its pieces were. */
export interface FlightSource {
  key: string;
  name: string;
  initials: string;
  avatar: Rect;
  label: Rect;
}

/** The type of the name in the rows (the copy is drawn with it and scaled). */
const SOURCE_TYPE = typeScale.cuerpo;

type Measurable = { getBoundingClientRect?: () => { x: number; y: number; width: number; height: number } };

/** A view's box on screen, or null when it is not laid out (or measuring is not available, as in tests). */
export function rectOf(node: unknown): Rect | null {
  const element = node as Measurable | null;
  if (!element || typeof element.getBoundingClientRect !== 'function') return null;
  const box = element.getBoundingClientRect();
  if (!(box.width > 0 && box.height > 0)) return null;
  return { x: box.x, y: box.y, width: box.width, height: box.height };
}

/** `rect` relative to `origin`'s top-left. */
export function relativeTo(rect: Rect, origin: Rect): Rect {
  return { x: rect.x - origin.x, y: rect.y - origin.y, width: rect.width, height: rect.height };
}

/** The name in a row, as a flight end. */
export function rowLabel(rect: Rect): LabelEnd {
  return { x: rect.x, y: rect.y, scale: 1, color: colors.ink };
}

/**
 * The name in the card, as a flight end: the copy grows by the ratio of the font sizes, so it lands at
 * the size of the real title, and its first line is centred on the title's first line.
 */
export function cardLabel(rect: Rect, type: { fontSize: number; lineHeight: number }, color: string): LabelEnd {
  const scale = type.fontSize / SOURCE_TYPE.fontSize;
  return { x: rect.x, y: rect.y + (type.lineHeight - SOURCE_TYPE.lineHeight * scale) / 2, scale, color };
}

function lerp(a: number, b: number, t: number): number {
  'worklet';
  return a + (b - a) * t;
}

/** The copies at `h` (0 the row, 1 the card): MovDetalle's `frame`, with the portrait sized and the name scaled. */
export function ghostFrame(from: FlightEnd, to: FlightEnd, h: number) {
  'worklet';
  return {
    avatar: { x: lerp(from.avatar.x, to.avatar.x, h), y: lerp(from.avatar.y, to.avatar.y, h), size: lerp(from.avatar.width, to.avatar.width, h) },
    label: { x: lerp(from.label.x, to.label.x, h), y: lerp(from.label.y, to.label.y, h), scale: lerp(from.label.scale, to.label.scale, h) },
  };
}

// ---------------------------------------------------------------- the rows (sources)

let pending: FlightSource | null = null;
const rows = new Map<string, { avatar: RefObject<View | null>; label: RefObject<View | null> }>();
/** The row whose portrait and name are hidden while their copies fly ('' none). */
const hiddenRow = makeMutable('');

/** The flight a row started for the screen being pushed now (taken once, by that screen). */
export function takeFlight(): FlightSource | null {
  const source = pending;
  pending = null;
  return source;
}

/** Starts a flight from a row (the next detail screen takes it). Exported for tests. */
export function beginFlight(source: FlightSource): void {
  pending = source;
}

/** A list row that can fly into a card: refs for its portrait and name, the style that hides them while their copies fly, and `begin` for the tap. */
export function useFlightSource(key: string) {
  const avatar = useRef<View>(null);
  const label = useRef<View>(null);
  useEffect(() => {
    const entry = { avatar, label };
    rows.set(key, entry);
    return () => {
      if (rows.get(key) === entry) rows.delete(key);
    };
  }, [key]);
  const hidden = useAnimatedStyle(() => ({ opacity: hiddenRow.value === key ? 0 : 1 }), [key]);
  const begin = useCallback(
    (name: string, initials: string) => {
      const a = rectOf(avatar.current);
      const l = rectOf(label.current);
      pending = a && l ? { key, name, initials, avatar: a, label: l } : null;
    },
    [key],
  );
  return { avatar, label, hidden, begin };
}

// ---------------------------------------------------------------- the card (targets) and the copies

type Phase = 'waiting' | 'opening' | 'open' | 'closing' | 'done';

interface FlightContextValue {
  key: string | null;
  /** The name of the person, to show the header while the card loads. */
  name: string | null;
  cardHidden: SharedValue<number>;
  target: (key: string, piece: 'avatar' | 'label', node: unknown, type?: { fontSize: number; lineHeight: number }, color?: string) => void;
}

const FlightContext = createContext<FlightContextValue | null>(null);
const NEVER_HIDDEN = makeMutable(0);

/** The name a row handed to this card, so its header can show while the rest loads (null otherwise). */
export function useFlightName(key: string): string | null {
  const flight = useContext(FlightContext);
  return flight?.key === key ? flight.name : null;
}

/**
 * A piece of the card header where a row's piece lands: put `ref` and `onLayout` on a plain view around
 * it and `style` on an Animated.View (it hides while the copy flies). Outside a detail screen it does nothing.
 */
export function useFlightTarget(key: string, piece: 'avatar' | 'label', type?: { fontSize: number; lineHeight: number }, color?: string) {
  const flight = useContext(FlightContext);
  const ref = useRef<View>(null);
  const hiddenValue = flight?.cardHidden ?? NEVER_HIDDEN;
  const style = useAnimatedStyle(() => ({ opacity: hiddenValue.value ? 0 : 1 }), [hiddenValue]);
  const onLayout = useCallback(
    (_event: LayoutChangeEvent) => {
      flight?.target(key, piece, ref.current, type, color);
    },
    [flight, key, piece, type, color],
  );
  return { ref, onLayout, style };
}

export function FlightProvider({ value, children }: { value: FlightContextValue; children: ReactNode }) {
  return <FlightContext.Provider value={value}>{children}</FlightContext.Provider>;
}

interface HostOptions {
  /** Level of the detail screen in the (app) stack (the row is in the screen below). */
  level: number;
  /** A view filling the pushed panel, to measure the header against it. */
  panel: RefObject<View | null>;
  reduced: boolean;
  /** Bottom of the top bar: a header scrolled above it does not fly back. */
  headerBottom: number;
}

/** The flight of one detail screen: the context for its card, `flyBack` for its exit, and the copies to draw. */
export function useFlightHost({ level, panel, reduced, headerBottom }: HostOptions) {
  const [source] = useState(takeFlight);
  const h = useSharedValue(0);
  const on = useSharedValue(0);
  const cardHidden = useSharedValue(0);
  const start: FlightEnd = useMemo(
    () => (source ? { avatar: source.avatar, label: rowLabel(source.label) } : { avatar: { x: 0, y: 0, width: 1, height: 1 }, label: { x: 0, y: 0, scale: 1, color: colors.ink } }),
    [source],
  );
  const ends = useSharedValue<{ row: FlightEnd; card: FlightEnd }>({ row: start, card: start });
  const phase = useRef<Phase>(source && !reduced ? 'waiting' : 'done');
  const targets = useRef<{ avatar?: { node: unknown }; label?: { node: unknown; type: { fontSize: number; lineHeight: number }; color: string } }>({});

  const finishOpen = useCallback(() => {
    if (phase.current !== 'opening') return;
    phase.current = 'open';
    on.set(0);
    cardHidden.set(0);
    hiddenRow.set('');
  }, [on, cardHidden]);

  const finishBack = useCallback(() => {
    phase.current = 'done';
    on.set(0);
    hiddenRow.set('');
  }, [on]);

  /** Where the header pieces are now, relative to the resting panel (null when not laid out). */
  const measureCard = useCallback((): FlightEnd | null => {
    const origin = rectOf(panel.current);
    const avatar = rectOf(targets.current.avatar?.node);
    const label = targets.current.label;
    const labelRect = rectOf(label?.node);
    if (!origin || !avatar || !label || !labelRect) return null;
    return { avatar: relativeTo(avatar, origin), label: cardLabel(relativeTo(labelRect, origin), label.type, label.color) };
  }, [panel]);

  const target = useCallback<FlightContextValue['target']>(
    (key, piece, node, type, color) => {
      if (!source || key !== source.key) return;
      if (piece === 'avatar') targets.current.avatar = { node };
      else targets.current.label = { node, type: type ?? typeScale.titulo, color: color ?? colors.ink };
      const card = measureCard();
      if (!card) return;
      if (phase.current === 'opening') {
        // The loaded header replaced the loading one: land where it is now.
        ends.modify((value) => {
          'worklet';
          value.card = card;
          return value;
        });
        return;
      }
      if (phase.current !== 'waiting') return;
      phase.current = 'opening';
      ends.set({ row: start, card });
      h.set(0);
      on.set(1);
      cardHidden.set(1);
      hiddenRow.set(source.key);
      h.set(
        withSpring(1, navSpring('flight'), (finished) => {
          if (finished) runOnJS(finishOpen)();
        }),
      );
    },
    [source, measureCard, ends, start, h, on, cardHidden, finishOpen],
  );

  /** Sends the pieces back to their row; `offsetX` is how far right the panel is already (after a drag). */
  const flyBack = useCallback(
    (offsetX: number) => {
      if (!source || reduced) return;
      const back = () =>
        h.set(
          withSpring(0, navSpring('flight'), (finished) => {
            if (finished) runOnJS(finishBack)();
          }),
        );
      if (phase.current === 'opening') {
        phase.current = 'closing';
        back();
        return;
      }
      if (phase.current !== 'open') return;
      const row = rows.get(source.key);
      const base = rectOf(layerAt(level - 1));
      const avatar = rectOf(row?.avatar.current);
      const label = rectOf(row?.label.current);
      const card = measureCard();
      if (!base || !avatar || !label || !card || card.avatar.y + card.avatar.height <= headerBottom) return;
      phase.current = 'closing';
      const shift = (end: FlightEnd): FlightEnd => ({ avatar: { ...end.avatar, x: end.avatar.x + offsetX }, label: { ...end.label, x: end.label.x + offsetX } });
      ends.set({ row: { avatar: relativeTo(avatar, base), label: rowLabel(relativeTo(label, base)) }, card: shift(card) });
      h.set(1);
      on.set(1);
      cardHidden.set(1);
      hiddenRow.set(source.key);
      back();
    },
    [source, reduced, level, measureCard, headerBottom, ends, h, on, cardHidden, finishBack],
  );

  // A screen that goes away mid-flight gives the row its pieces back.
  useEffect(
    () => () => {
      if (source && hiddenRow.get() === source.key) hiddenRow.set('');
    },
    [source],
  );

  const context = useMemo<FlightContextValue>(() => ({ key: source?.key ?? null, name: source?.name ?? null, cardHidden, target }), [source, cardHidden, target]);
  const ghost = source && !reduced ? <FlightGhost source={source} h={h} on={on} ends={ends} /> : null;
  return { context, flyBack, ghost };
}

function FlightGhost({ source, h, on, ends }: { source: FlightSource; h: SharedValue<number>; on: SharedValue<number>; ends: SharedValue<{ row: FlightEnd; card: FlightEnd }> }) {
  const base = source.avatar.width;
  const circle = useAnimatedStyle(() => {
    const frame = ghostFrame(ends.value.row, ends.value.card, h.value);
    return { opacity: on.value, transform: [{ translateX: frame.avatar.x }, { translateY: frame.avatar.y }, { scale: frame.avatar.size / base }] };
  });
  const initials = useAnimatedStyle(() => {
    const frame = ghostFrame(ends.value.row, ends.value.card, h.value);
    const inset = (frame.avatar.size - base) / 2;
    return { opacity: on.value, transform: [{ translateX: frame.avatar.x + inset }, { translateY: frame.avatar.y + inset }] };
  });
  const label = useAnimatedStyle(() => {
    const frame = ghostFrame(ends.value.row, ends.value.card, h.value);
    return {
      opacity: on.value,
      color: interpolateColor(h.value, [0, 1], [ends.value.row.label.color, ends.value.card.label.color]),
      transform: [{ translateX: frame.label.x }, { translateY: frame.label.y }, { scale: frame.label.scale }],
    };
  });
  return (
    <View pointerEvents="none" style={StyleSheet.absoluteFill} accessible={false} importantForAccessibility="no-hide-descendants" testID="flight-ghost">
      <Animated.View style={[styles.circle, { width: base, height: base }, circle]} />
      <Animated.View style={[styles.initials, { width: base, height: base }, initials]}>
        <T variant="detalle" color={colors.info}>
          {source.initials}
        </T>
      </Animated.View>
      <Animated.Text numberOfLines={1} style={[styles.label, SOURCE_TYPE, label]}>
        {source.name}
      </Animated.Text>
    </View>
  );
}

const styles = StyleSheet.create({
  circle: { position: 'absolute', left: 0, top: 0, borderRadius: radius.pill, backgroundColor: colors.infoLight, transformOrigin: 'top left' },
  initials: { position: 'absolute', left: 0, top: 0, alignItems: 'center', justifyContent: 'center' },
  label: { position: 'absolute', left: 0, top: 0, transformOrigin: 'top left' },
});
