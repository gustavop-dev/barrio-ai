import { useEffect } from 'react';
import { StyleSheet, View } from 'react-native';
import Animated, { cancelAnimation, useAnimatedStyle, useSharedValue, withRepeat, withTiming } from 'react-native-reanimated';
import { timing, useMotion } from '@/theme/motion';
import { colors, radius, space } from '@/theme/tokens';
import { T } from './Text';

function Bar({ width, height = 14, round }: { width: `${number}%` | number; height?: number; round?: boolean }) {
  return <View style={{ width, height, borderRadius: round ? radius.pill : radius.sm, backgroundColor: colors.line }} />;
}

/** Loading placeholders: card (Tu turno) or row. The breathing stops with reduced motion. */
export function Skeleton({ variant = 'card', count = 1, label = 'Cargando…' }: { variant?: 'card' | 'row'; count?: number; label?: string }) {
  const { reduced } = useMotion();
  const opacity = useSharedValue(1);
  useEffect(() => {
    if (reduced) return;
    opacity.set(withRepeat(withTiming(0.45, timing('skeleton')), -1, true));
    return () => cancelAnimation(opacity);
  }, [reduced, opacity]);
  const breathing = useAnimatedStyle(() => ({ opacity: opacity.value }));
  return (
    <View accessibilityRole="progressbar" accessibilityLabel={label} accessibilityLiveRegion="polite" style={styles.group}>
      <T variant="detalle" soft style={styles.hidden}>
        {label}
      </T>
      {Array.from({ length: count }, (_, index) => (
        <Animated.View key={index} style={[variant === 'card' ? styles.card : styles.row, breathing]}>
          {variant === 'card' ? (
            <>
              <Bar width="30%" height={12} />
              <Bar width="80%" height={22} />
              <Bar width="95%" />
              <Bar width="60%" />
              <Bar width="100%" height={48} />
            </>
          ) : (
            <>
              <Bar width={40} height={40} round />
              <View style={styles.lines}>
                <Bar width="70%" />
                <Bar width="40%" />
              </View>
            </>
          )}
        </Animated.View>
      ))}
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
