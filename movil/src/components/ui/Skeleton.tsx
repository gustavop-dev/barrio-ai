import { useEffect } from 'react';
import { StyleSheet, View } from 'react-native';
import Animated, { cancelAnimation, useAnimatedStyle, useSharedValue, withRepeat, withTiming, type SharedValue } from 'react-native-reanimated';
import { microMotion, timelineWith, useMotion } from '@/theme/motion';
import { colors, radius, space } from '@/theme/tokens';
import { T } from './Text';

/** Blocks per placeholder, so each block knows its place in the wave. */
const CARD_BARS = 5;
const ROW_BARS = 3;

/**
 * MovMicro «Cargando»: one block that breathes in opacity (no gradient, as the brand asks), between 55 %
 * and 100 % every 1.2 s, `index` · 0.4 rad behind the first one. Still at 70 % with reduced motion.
 */
function Bar({ width, height = 14, round, index, clock, still }: { width: `${number}%` | number; height?: number; round?: boolean; index: number; clock: SharedValue<number>; still: boolean }) {
  const breathing = useAnimatedStyle(() => {
    if (still) return { opacity: microMotion.skeletonStill };
    const wave = 0.5 + 0.5 * Math.sin(clock.value * Math.PI * 2 - index * microMotion.skeletonLag);
    return { opacity: microMotion.skeletonLow + (1 - microMotion.skeletonLow) * wave };
  });
  return <Animated.View style={[{ width, height, borderRadius: round ? radius.pill : radius.sm, backgroundColor: colors.line }, breathing]} />;
}

/** Loading placeholders: card (Tu turno) or row. */
export function Skeleton({ variant = 'card', count = 1, label = 'Cargando…' }: { variant?: 'card' | 'row'; count?: number; label?: string }) {
  const { reduced } = useMotion();
  const clock = useSharedValue(0);
  useEffect(() => {
    if (reduced) return;
    clock.set(withRepeat(withTiming(1, timelineWith(microMotion.skeletonPeriodMs)), -1, false));
    return () => cancelAnimation(clock);
  }, [reduced, clock]);
  return (
    <View accessibilityRole="progressbar" accessibilityLabel={label} accessibilityLiveRegion="polite" style={styles.group}>
      <T variant="detalle" soft style={styles.hidden}>
        {label}
      </T>
      {Array.from({ length: count }, (_, index) => {
        const first = index * (variant === 'card' ? CARD_BARS : ROW_BARS);
        const bar = { clock, still: reduced };
        return (
          <View key={index} style={variant === 'card' ? styles.card : styles.row}>
            {variant === 'card' ? (
              <>
                <Bar width="30%" height={12} index={first} {...bar} />
                <Bar width="80%" height={22} index={first + 1} {...bar} />
                <Bar width="95%" index={first + 2} {...bar} />
                <Bar width="60%" index={first + 3} {...bar} />
                <Bar width="100%" height={48} index={first + 4} {...bar} />
              </>
            ) : (
              <>
                <Bar width={40} height={40} round index={first} {...bar} />
                <View style={styles.lines}>
                  <Bar width="70%" index={first + 1} {...bar} />
                  <Bar width="40%" index={first + 2} {...bar} />
                </View>
              </>
            )}
          </View>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  group: { gap: space[3] },
  hidden: { position: 'absolute', width: 1, height: 1, opacity: 0 },
  card: { padding: space[4], gap: space[3], backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.line, borderRadius: radius.md },
  row: { flexDirection: 'row', alignItems: 'center', gap: space[3], paddingVertical: space[2] },
  lines: { flex: 1, gap: space[2] },
});
