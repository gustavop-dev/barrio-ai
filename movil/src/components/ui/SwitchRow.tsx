import { useEffect } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import Animated, { useAnimatedStyle, useSharedValue, withSpring, withTiming } from 'react-native-reanimated';
import { durations, haptic, microMotion, springWith, timingWith } from '@/theme/motion';
import { colors, radius, space } from '@/theme/tokens';
import { T } from './Text';

/** MovMicro's switch: a 52 × 32 track and a 26 px knob 3 px from its edges. */
const TRACK_WIDTH = 52;
const TRACK_HEIGHT = 32;
const KNOB = 26;
const INSET = 3;
const TRAVEL = TRACK_WIDTH - KNOB - INSET * 2;

/** The knob slides on FIRM; the track and the knob's border turn 0ff1ce-hondo halfway through a fast EASE_OUT. */
function SwitchGraphic({ value, disabled }: { value: boolean; disabled?: boolean }) {
  const knob = useSharedValue(value ? 1 : 0);
  const tone = useSharedValue(value ? 1 : 0);
  useEffect(() => {
    knob.set(withSpring(value ? 1 : 0, springWith(microMotion.switchKnob)));
    tone.set(withTiming(value ? 1 : 0, timingWith(durations.fast, 'enter')));
  }, [value, knob, tone]);
  const track = useAnimatedStyle(() => ({ backgroundColor: tone.value > microMotion.switchColorAt ? colors.brandDeep : colors.line }));
  const thumb = useAnimatedStyle(() => ({
    borderColor: tone.value > microMotion.switchColorAt ? colors.brandDeep : colors.inkSoft,
    transform: [{ translateX: knob.value * TRAVEL }],
  }));
  return (
    <Animated.View style={[styles.track, disabled ? styles.disabled : null, track]}>
      <Animated.View style={[styles.knob, thumb]} />
    </Animated.View>
  );
}

/**
 * A switch row (Ajustes, the photo sheet): label and optional hint on the left, the switch on the
 * right, a 1 px line on top. The whole row (48 dp) is the control. MovMicro: a selection haptic.
 */
export function SwitchRow({
  label,
  hint,
  value,
  disabled,
  onChange,
  divider = true,
  testID,
}: {
  label: string;
  hint?: string;
  value: boolean;
  disabled?: boolean;
  onChange: (value: boolean) => void;
  /** The line on top; off for the first row of a card. */
  divider?: boolean;
  testID?: string;
}) {
  const toggle = () => {
    if (disabled) return;
    haptic('switchToggle');
    onChange(!value);
  };
  return (
    <Pressable
      testID={testID}
      accessibilityRole="switch"
      accessibilityLabel={label}
      accessibilityHint={hint}
      accessibilityState={{ checked: value, disabled: Boolean(disabled) }}
      disabled={disabled}
      onPress={toggle}
      style={[styles.row, divider ? styles.divider : null]}
    >
      <View style={styles.text}>
        <T color={disabled ? colors.inkSoft : colors.ink}>{label}</T>
        {hint ? (
          <T variant="detalle" soft>
            {hint}
          </T>
        ) : null}
      </View>
      <View pointerEvents="none" importantForAccessibility="no-hide-descendants" accessibilityElementsHidden>
        <SwitchGraphic value={value} disabled={disabled} />
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: { minHeight: 48, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: space[3], paddingVertical: space[1] },
  divider: { borderTopWidth: 1, borderTopColor: colors.line },
  text: { flex: 1, gap: 2 },
  track: { width: TRACK_WIDTH, height: TRACK_HEIGHT, borderRadius: radius.pill, padding: INSET, backgroundColor: colors.line },
  knob: { width: KNOB, height: KNOB, borderRadius: radius.pill, borderWidth: 1, borderColor: colors.inkSoft, backgroundColor: colors.surface },
  disabled: { opacity: 0.5 },
});
