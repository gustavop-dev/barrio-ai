import { useEffect, useState, type ReactNode } from 'react';
import { Pressable, StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';
import Animated, { useAnimatedStyle, useSharedValue, withTiming } from 'react-native-reanimated';
import { Icon } from '@/components/icons';
import { timing, useMotion } from '@/theme/motion';
import { colors, radius, shell, space } from '@/theme/tokens';
import { T } from './Text';

// Built on the JS thread: timing() is not a worklet, and calling it inside a style worklet crashes the app on the UI
// runtime («Tried to synchronously call a Remote Function»).
const FOLD = timing('fold');

/**
 * Content that fades in (`fold`) when it opens, driven by a shared value rather than a Reanimated `entering`: in the QA
 * emulator an entering fade sometimes never started and left the content at opacity 0, taking its room but invisible to
 * Gustavo and to TalkBack («Ronda de reparación», 07-pieza-estados; the Select's options, 08-resultados). With reduced
 * motion it is there at once.
 */
export function FoldIn({ style, children, ...props }: { style?: StyleProp<ViewStyle>; children: ReactNode; accessibilityRole?: 'radiogroup'; accessibilityLabel?: string }) {
  const { reduced } = useMotion();
  const shown = useSharedValue(reduced ? 1 : 0);
  useEffect(() => {
    shown.set(reduced ? 1 : withTiming(1, FOLD));
  }, [reduced, shown]);
  const fade = useAnimatedStyle(() => ({ opacity: shown.value }));
  return (
    <Animated.View {...props} style={[style, fade]}>
      {children}
    </Animated.View>
  );
}

/** A folded block («Pospuestas · 2»): tap the summary to open it. */
export function Fold({ summary, children, initiallyOpen = false }: { summary: string; children: ReactNode; initiallyOpen?: boolean }) {
  const [open, setOpen] = useState(initiallyOpen);
  const chevron = useAnimatedStyle(() => ({ transform: [{ rotate: withTiming(open ? '180deg' : '0deg', FOLD) }] }), [open]);
  return (
    <View style={styles.fold}>
      <Pressable accessibilityRole="button" accessibilityState={{ expanded: open }} onPress={() => setOpen((value) => !value)} style={styles.summary}>
        <T style={styles.label}>{summary}</T>
        <Animated.View style={chevron}>
          <Icon name="chevronDown" size={20} color={colors.inkSoft} />
        </Animated.View>
      </Pressable>
      {open ? (
        <FoldIn style={styles.body}>{children}</FoldIn>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  fold: { borderTopWidth: 1, borderTopColor: colors.line },
  summary: { minHeight: shell.touch + 4, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: space[2], borderRadius: radius.sm },
  label: { flex: 1 },
  body: { gap: space[2], paddingBottom: space[3] },
});
