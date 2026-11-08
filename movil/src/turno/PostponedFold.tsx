// «Pospuestas · N»: the Fold of the UI kit, with MovTuTurno's motion. When «Más tarde» sends a card
// here its number rolls (`roll`) and the row flashes 0ff1ce-claro, rising and falling along a sine
// (postponedFlashMs, linear). Reduced motion: the number just changes, no flash. It stays mounted
// (drawing nothing) while there is nothing postponed, so the first card sent here flashes it too.
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import Animated, { interpolateColor, useAnimatedStyle, useSharedValue, withTiming } from 'react-native-reanimated';
import { Icon } from '@/components/icons';
import { T } from '@/components/ui';
import { layout, postponedFlashTiming, timing, useMotion } from '@/theme/motion';
import { colors, radius, shell, space } from '@/theme/tokens';
import { RollingNumber } from './RollingNumber';

/** 0ff1ce-claro, fully transparent: the flash fades from and back to it. */
const CLEAR = `${colors.brandLight}00`;

/** `flash` grows by one for each card sent here on this visit. */
export function PostponedFold({ count, flash, children }: { count: number; flash: number; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const { reduced } = useMotion();
  const glow = useSharedValue(0);
  const seen = useRef<number | null>(null);

  useEffect(() => {
    const before = seen.current;
    seen.current = flash;
    if (reduced || before === null || before === flash) return;
    glow.set(0);
    glow.set(withTiming(1, postponedFlashTiming()));
  }, [flash, glow, reduced]);

  const fold = timing('fold');
  const chevron = useAnimatedStyle(() => ({ transform: [{ rotate: withTiming(open ? '180deg' : '0deg', fold) }] }), [open]);
  const lit = useAnimatedStyle(() => ({ backgroundColor: interpolateColor(Math.sin(glow.value * Math.PI), [0, 1], [CLEAR, colors.brandLight]) }));

  if (count <= 0) return null;
  return (
    <View style={styles.fold}>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={`Pospuestas · ${count}`}
        accessibilityState={{ expanded: open }}
        onPress={() => setOpen((value) => !value)}
        testID="pospuestas"
      >
        <Animated.View style={[styles.summary, lit]} testID="pospuestas-row">
          <View style={styles.label}>
            <T>Pospuestas · </T>
            <RollingNumber value={String(count)} />
          </View>
          <Animated.View style={chevron}>
            <Icon name="chevronDown" size={20} color={colors.inkSoft} />
          </Animated.View>
        </Animated.View>
      </Pressable>
      {open ? (
        <Animated.View entering={layout.foldIn()} exiting={layout.foldOut()} style={styles.body}>
          {children}
        </Animated.View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  fold: { borderTopWidth: 1, borderTopColor: colors.line },
  summary: { minHeight: shell.touch + 4, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: space[2], borderRadius: radius.sm },
  label: { flex: 1, flexDirection: 'row', alignItems: 'center' },
  body: { gap: space[2], paddingBottom: space[3] },
});
