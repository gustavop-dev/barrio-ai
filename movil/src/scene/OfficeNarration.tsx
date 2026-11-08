import { useEffect, useState } from 'react';
import { StyleSheet } from 'react-native';
import Animated, { cancelAnimation, useAnimatedStyle, useSharedValue, withDelay, withTiming } from 'react-native-reanimated';
import type { NowLine } from '@compartido/scene/presentation';
import { AgentPortrait, T } from '@/components/ui';
import { officeLayout, officeNarration, timing, timings } from '@/theme/motion';
import { colors, radius, space } from '@/theme/tokens';

/** Text changes and box retirement have independent clocks, as in MovOficina's CAP layers. */
export function OfficeNarration({ line, revision, reduced }: { line: NowLine | null; revision: number; reduced: boolean }) {
  const identity = line ? `${revision}:${line.role}:${line.text}` : '';
  const [retired, setRetired] = useState<string | null>(null);
  const opacity = useSharedValue(1);
  const y = useSharedValue(0);
  useEffect(() => {
    cancelAnimation(opacity); cancelAnimation(y);
    opacity.set(1); y.set(0);
    if (!identity || reduced) return;
    const config = timing('officeNowRetire');
    opacity.set(withDelay(officeNarration.holdMs, withTiming(0, config), config.reduceMotion));
    y.set(withDelay(officeNarration.holdMs, withTiming(officeNarration.retireY, config), config.reduceMotion));
    // Only one React update per narration, to retire the accessibility node after its visual exit.
    const timer = setTimeout(() => setRetired(identity), officeNarration.holdMs + timings.officeNowRetire.duration);
    return () => { clearTimeout(timer); cancelAnimation(opacity); cancelAnimation(y); };
  }, [identity, reduced, opacity, y]);
  const style = useAnimatedStyle(() => ({ opacity: opacity.value, transform: [{ translateY: y.value }] }));
  if (!line || !reduced && retired === identity) return null;
  return <Animated.View testID="office-narration" pointerEvents="none" style={[styles.box, style]}>
    <Animated.View key={identity} entering={reduced ? undefined : officeLayout.nowIn()} exiting={reduced ? undefined : officeLayout.nowOut()} style={styles.line}>
      <AgentPortrait role={line.role} /><T variant="detalle" accessibilityLiveRegion="polite" style={styles.text}>{line.text}</T>
    </Animated.View>
  </Animated.View>;
}

const styles = StyleSheet.create({
  box: { position: 'absolute', top: space[2], left: space[2], right: space[2], backgroundColor: colors.surface,
    borderColor: colors.line, borderWidth: 1, borderRadius: radius.md, padding: space[2], overflow: 'hidden' },
  line: { gap: space[2], flexDirection: 'row', alignItems: 'center' },
  text: { flex: 1 },
});
