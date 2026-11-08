// MovMicro «Copiar»: copies a text (expo-clipboard). The copy icon turns 90° away while a check turns
// in from −90° growing from 0.6 (fast, EASE_OUT), and the label says «Copiado» for copiedLabelMs, with
// the success haptic; then both go back at once. Shared by every copy button.
import * as Clipboard from 'expo-clipboard';
import { useEffect, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import Animated, { useAnimatedStyle, useSharedValue, withTiming } from 'react-native-reanimated';
import Svg, { Path, Rect } from 'react-native-svg';
import { Icon } from '@/components/icons';
import { copiedLabelMs, durations, haptic, microMotion, timingWith } from '@/theme/motion';
import { colors } from '@/theme/tokens';
import { Button } from './Button';

const ICON = 18;

/** The board's copy glyph (two sheets), drawn here as the icon set has no copy icon. */
function CopyGlyph({ color }: { color: string }) {
  return (
    <Svg width={ICON} height={ICON} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <Rect x={9} y={9} width={12} height={12} rx={2} />
      <Path d="M5 15H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1" />
    </Svg>
  );
}

export function CopyButton({ text, testID }: { text: string; testID?: string }) {
  const [state, setState] = useState<'idle' | 'copied' | 'failed'>('idle');
  const turn = useSharedValue(0);
  useEffect(() => {
    if (state === 'idle') return;
    const timer = setTimeout(() => {
      setState('idle');
      turn.set(0);
    }, copiedLabelMs);
    return () => clearTimeout(timer);
  }, [state, turn]);
  const copy = async () => {
    try {
      await Clipboard.setStringAsync(text);
      haptic('copied');
      setState('copied');
      turn.set(0);
      turn.set(withTiming(1, timingWith(durations.fast, 'enter')));
    } catch {
      haptic('actionError');
      setState('failed');
    }
  };
  const away = useAnimatedStyle(() => ({ opacity: 1 - turn.value, transform: [{ rotate: `${microMotion.copyTurnDeg * turn.value}deg` }] }));
  const back = useAnimatedStyle(() => ({
    opacity: turn.value,
    transform: [{ rotate: `${-microMotion.copyTurnDeg * (1 - turn.value)}deg` }, { scale: microMotion.copyCheckFrom + (1 - microMotion.copyCheckFrom) * turn.value }],
  }));
  return (
    <Button
      size="small"
      onPress={() => void copy()}
      testID={testID}
      icon={
        <View style={styles.icons}>
          <Animated.View style={[styles.icon, away]}>
            <CopyGlyph color={colors.ink} />
          </Animated.View>
          <Animated.View style={[styles.icon, back]}>
            <Icon name="check" size={ICON} color={colors.brandDeep} />
          </Animated.View>
        </View>
      }
    >
      {state === 'copied' ? 'Copiado' : state === 'failed' ? 'No se pudo copiar' : 'Copiar'}
    </Button>
  );
}

const styles = StyleSheet.create({
  icons: { width: ICON, height: ICON },
  icon: { position: 'absolute', top: 0, left: 0, right: 0, bottom: 0 },
});
