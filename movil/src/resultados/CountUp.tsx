// Resultados in motion (MovResultados): the figures count, the bars grow.
// - The first time a figure appears it counts up from 0 (600 ms); when it changes (another period, another
//   modality, a refresh) it counts from the value on screen to the new one (TOK.slow).
// - The count runs on the UI thread: a read-only TextInput whose text Reanimated writes each frame (no React
//   render per frame). The last frame shows the figure exactly as formatKpiValue writes it, and screen
//   readers only ever hear that final figure.
// - The bars grow to their length in a cascade: 40 ms per bar, plus 120 ms the first time.
// «Sin dato» never comes through here: it is a dash, never a count from (or to) 0.
// With reduced motion the figures and the bars are simply there.
import type { KpiUnit } from '@compartido/logic/resultados';
import { useEffect, useRef } from 'react';
import { StyleSheet, TextInput, View, type TextInputProps } from 'react-native';
import Animated, { useAnimatedProps, useAnimatedStyle, useSharedValue, withDelay, withTiming } from 'react-native-reanimated';
import { resultsChoreography, resultsTiming, useMotion } from '@/theme/motion';
import { colors, radius, type as typeScale, type TypeVariant } from '@/theme/tokens';

const AnimatedTextInput = Animated.createAnimatedComponent(TextInput);

/** Decimals a figure counts with: those formatKpiValue would show for its final value. */
export function countDecimals(value: number, unit: KpiUnit): number {
  if (unit === 'usd') return 2;
  return Number.isInteger(value) ? 0 : 1;
}

/**
 * A figure on its way, written like formatNumber/formatPct/formatUsd (es-CO: «1.520», «3,5 %»,
 * «3,10 USD») without Intl, so it can run on the UI thread. Worklet.
 */
export function formatCount(value: number, unit: KpiUnit, decimals: number): string {
  'worklet';
  const factor = Math.pow(10, decimals);
  const rounded = Math.round(Math.abs(value) * factor) / factor;
  const whole = Math.floor(rounded);
  let fraction = decimals ? String(Math.round((rounded - whole) * factor)) : '';
  while (fraction.length < decimals) fraction = `0${fraction}`;
  // formatNumber and formatPct show at most one decimal, and none when it is 0; formatUsd always two.
  if (unit !== 'usd') while (fraction.endsWith('0')) fraction = fraction.slice(0, -1);
  let digits = String(whole);
  let grouped = '';
  while (digits.length > 3) {
    grouped = `.${digits.slice(-3)}${grouped}`;
    digits = digits.slice(0, -3);
  }
  const body = `${value < 0 && rounded > 0 ? '-' : ''}${digits}${grouped}${fraction ? `,${fraction}` : ''}`;
  if (unit === 'percent') return `${body} %`;
  if (unit === 'usd') return `${body} USD`;
  return body;
}

export interface CountUpProps {
  value: number;
  /** The final figure as the screen writes it (formatKpiValue). */
  text: string;
  unit?: KpiUnit;
  variant?: TypeVariant;
  color?: string;
  testID?: string;
}

/** A figure that counts to `value`: from 0 the first time, from the figure on screen afterwards. */
export function CountUp({ value, text, unit = 'number', variant = 'titulo', color = colors.ink, testID }: CountUpProps) {
  const { reduced } = useMotion();
  const decimals = countDecimals(value, unit);
  const shown = useSharedValue(reduced ? value : 0);
  const last = useRef<number | null>(null);

  useEffect(() => {
    if (last.current === value) return;
    const first = last.current === null;
    last.current = value;
    shown.set(reduced ? value : withTiming(value, resultsTiming(first ? 'countFirst' : 'count')));
  }, [value, reduced, shown]);

  const animatedProps = useAnimatedProps(() => {
    const now = shown.value;
    const figure = now === value ? text : formatCount(now, unit, decimals);
    return { text: figure, defaultValue: figure } as TextInputProps;
  }, [value, text, unit, decimals]);

  return (
    <View testID={testID} accessible accessibilityRole="text" accessibilityLabel={text}>
      <AnimatedTextInput
        testID={testID ? `${testID}-cifra` : undefined}
        editable={false}
        caretHidden
        contextMenuHidden
        underlineColorAndroid="transparent"
        pointerEvents="none"
        importantForAccessibility="no-hide-descendants"
        accessibilityElementsHidden
        defaultValue={reduced ? text : formatCount(0, unit, decimals)}
        animatedProps={animatedProps}
        style={[typeScale[variant], { color }, styles.figure]}
      />
    </View>
  );
}

/** A bar growing to `width` (0–100 % of its track), `index` places it in the cascade. */
export function GrowBar({ width, color, index }: { width: number; color: string; index: number }) {
  const { reduced } = useMotion();
  const shown = useSharedValue(reduced ? width : 0);
  const last = useRef<number | null>(null);

  useEffect(() => {
    if (last.current === width) return;
    const first = last.current === null;
    last.current = width;
    if (reduced) {
      shown.set(width);
      return;
    }
    const { barFirstDelayMs, barStaggerMs } = resultsChoreography;
    const config = resultsTiming('bar');
    shown.set(withDelay((first ? barFirstDelayMs : 0) + index * barStaggerMs, withTiming(width, config), config.reduceMotion));
  }, [width, index, reduced, shown]);

  const style = useAnimatedStyle(() => ({ width: `${shown.value}%` as `${number}%` }));
  return <Animated.View testID="barra" style={[styles.bar, { backgroundColor: color }, style]} />;
}

const styles = StyleSheet.create({
  // A TextInput draws its text with padding on Android: none here, so it sits like the T it replaces.
  figure: { padding: 0, margin: 0, borderWidth: 0 },
  bar: { height: 8, borderRadius: radius.pill },
});
