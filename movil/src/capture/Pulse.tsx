// Breathing loops of the capture: the red recording dot and the pulsing brand ball. Still with reduced motion.
import { useEffect, type ReactNode } from 'react';
import type { StyleProp, ViewStyle } from 'react-native';
import Animated, { cancelAnimation, useAnimatedStyle, useSharedValue, withRepeat, withTiming } from 'react-native-reanimated';
import { timing, useMotion, type TimingName } from '@/theme/motion';

export function Pulse({ kind, active = true, style, children }: { kind: Extract<TimingName, 'recordDot' | 'recordPulse'>; active?: boolean; style?: StyleProp<ViewStyle>; children?: ReactNode }) {
  const { reduced } = useMotion();
  const progress = useSharedValue(0);
  useEffect(() => {
    if (reduced || !active) {
      cancelAnimation(progress);
      progress.set(0);
      return;
    }
    const half = timing(kind);
    progress.set(withRepeat(withTiming(1, { ...half, duration: (half.duration ?? 0) / 2 }), -1, true));
    return () => cancelAnimation(progress);
  }, [reduced, active, kind, progress]);
  const animated = useAnimatedStyle(() =>
    kind === 'recordDot' ? { opacity: 1 - progress.value * 0.7 } : { transform: [{ scale: 1 + progress.value * 0.06 }] },
  );
  return <Animated.View style={[style, animated]}>{children}</Animated.View>;
}
