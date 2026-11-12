import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, View, type LayoutChangeEvent } from 'react-native';
import Animated, { useAnimatedStyle, useSharedValue, withSpring, type SharedValue } from 'react-native-reanimated';
import { calendarSpring, haptic, useMotion } from '@/theme/motion';
import { colors, radius, space } from '@/theme/tokens';
import { T } from './Text';

const PAD = space[1];
const GAP = space[1];

/** The sliding superficie. It mounts once the track is measured, so its first frame is already in place. */
function Indicator({ seg, optionWidth, testID }: { seg: SharedValue<number>; optionWidth: number; testID?: string }) {
  const slide = useAnimatedStyle(() => ({ transform: [{ translateX: seg.value * (optionWidth + GAP) }] }), [optionWidth]);
  return <Animated.View testID={testID} pointerEvents="none" style={[styles.indicator, { width: optionWidth }, slide]} />;
}

/**
 * Segmented control (ui.css .segmented, the Calendario's Mes · Semana · Lista, Resultados' Periodo): a linea
 * track, the chosen one on superficie. The superficie is one piece that slides to the chosen option
 * (MovCalendario and MovResultados, `seg`); until the track is measured the chosen option paints it itself.
 */
export function Segmented<V extends string>({
  label,
  options,
  value,
  onChange,
  testID,
  showLabel = false,
}: {
  label: string;
  options: readonly { value: V; label: string }[];
  value: V;
  onChange: (value: V) => void;
  testID?: string;
  /** Shows the label above the track, as Select does (Resultados' «Periodo»). The Calendario's views go without it. */
  showLabel?: boolean;
}) {
  const index = Math.max(0, options.findIndex((option) => option.value === value));
  const [width, setWidth] = useState(0);
  const { reduced } = useMotion();
  const seg = useSharedValue(index);

  useEffect(() => {
    seg.set(reduced ? index : withSpring(index, calendarSpring('segment')));
  }, [index, reduced, seg]);

  const optionWidth = width ? (width - PAD * 2 - GAP * (options.length - 1)) / options.length : 0;

  const track = (
    <View
      style={styles.track}
      accessibilityRole="tablist"
      accessibilityLabel={label}
      testID={testID}
      onLayout={(event: LayoutChangeEvent) => setWidth(event.nativeEvent.layout.width)}
    >
      {width ? <Indicator seg={seg} optionWidth={optionWidth} testID={testID ? `${testID}-seleccion` : undefined} /> : null}
      {options.map((option) => {
        const selected = option.value === value;
        return (
          <Pressable
            key={option.value}
            accessibilityRole="tab"
            accessibilityState={{ selected }}
            hitSlop={4}
            onPress={() => {
              if (selected) return;
              haptic('tabChange');
              onChange(option.value);
            }}
            style={[styles.option, selected && !width ? styles.selected : null]}
          >
            <T variant="detalle" color={selected ? colors.ink : colors.inkSoft}>
              {option.label}
            </T>
          </Pressable>
        );
      })}
    </View>
  );
  if (!showLabel) return track;
  return (
    <View style={styles.field}>
      <T variant="detalle">{label}</T>
      {track}
    </View>
  );
}

const styles = StyleSheet.create({
  field: { gap: space[1] },
  track: { flexDirection: 'row', gap: GAP, padding: PAD, backgroundColor: colors.line, borderRadius: radius.md },
  indicator: { position: 'absolute', top: PAD, bottom: PAD, left: PAD, borderRadius: radius.sm, backgroundColor: colors.surface },
  option: { flex: 1, minHeight: 40, alignItems: 'center', justifyContent: 'center', borderRadius: radius.sm },
  selected: { backgroundColor: colors.surface },
});
