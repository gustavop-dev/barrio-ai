import { useState, type ReactNode } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import Animated, { useAnimatedStyle, withTiming } from 'react-native-reanimated';
import { Icon } from '@/components/icons';
import { layout, timing } from '@/theme/motion';
import { colors, radius, shell, space } from '@/theme/tokens';
import { T } from './Text';

// Built on the JS thread: timing() is not a worklet, and calling it inside a style worklet crashes the app on the UI
// runtime («Tried to synchronously call a Remote Function»).
const FOLD = timing('fold');

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
  label: { flex: 1 },
  body: { gap: space[2], paddingBottom: space[3] },
});
