// The pieces MovCaptura draws for its choreography: the lock with its shackle, the trash with its lid,
// the bin of the sheet and the envelope. Each moving part takes an animated style from its owner.
import type { ComponentProps } from 'react';
import { StyleSheet, View } from 'react-native';
import Animated from 'react-native-reanimated';
import Svg, { Path, Rect } from 'react-native-svg';
import { colors } from '@/theme/tokens';

type MovingStyle = ComponentProps<typeof Animated.View>['style'];

const STROKE = { fill: 'none', strokeWidth: 2, strokeLinecap: 'round', strokeLinejoin: 'round' } as const;

/** The lock of the hold (24 × 28): its shackle drops when the recording locks. */
export function LockGlyph({ shackle }: { shackle: MovingStyle }) {
  return (
    <View style={styles.lock}>
      <Animated.View style={[StyleSheet.absoluteFill, shackle]}>
        <Svg width={24} height={28} viewBox="0 0 24 28" stroke={colors.ink} {...STROKE}>
          <Path d="M7 13V9a5 5 0 0 1 10 0v4" />
        </Svg>
      </Animated.View>
      <Svg width={24} height={28} viewBox="0 0 24 28" stroke={colors.ink} {...STROKE}>
        <Rect x={4} y={13} width={16} height={12} rx={2} />
      </Svg>
    </View>
  );
}

/** The trash of the hold (24 px): its lid opens as the finger goes left. */
export function TrashGlyph({ lid }: { lid: MovingStyle }) {
  return (
    <View style={styles.trash}>
      <Animated.View style={[StyleSheet.absoluteFill, styles.trashLid, lid]}>
        <Svg width={24} height={24} viewBox="0 0 24 24" stroke={colors.alert} {...STROKE}>
          <Path d="M4 7h16M9 7V4h6v3" />
        </Svg>
      </Animated.View>
      <Svg width={24} height={24} viewBox="0 0 24 24" stroke={colors.alert} {...STROKE}>
        <Path d="M6 7l1 13h10l1-13M10 11v6M14 11v6" />
      </Svg>
    </View>
  );
}

export const BIN = { width: 64, height: 72 } as const;

/** The bin that takes a discarded recording in the sheet (64 × 72). */
export function BinGlyph({ lid }: { lid: MovingStyle }) {
  return (
    <View style={styles.bin}>
      <Animated.View style={[styles.binLid, lid]} />
      <View style={styles.binHandle} />
      <View style={styles.binBody} />
    </View>
  );
}

export const ENVELOPE = { width: 72, height: 50 } as const;

/** The envelope that takes the capture away (72 × 50): its flap closes before it flies. */
export function EnvelopeGlyph({ flap }: { flap: MovingStyle }) {
  return (
    <View style={styles.envelope}>
      <View style={styles.envelopeBox} />
      <Svg style={StyleSheet.absoluteFill} width={72} height={50} viewBox="0 0 72 50" fill="none" stroke={colors.ink} strokeWidth={2} strokeLinejoin="round">
        <Path d="M2 48l26-22M70 48L44 26" />
      </Svg>
      <Animated.View style={[styles.flap, flap]}>
        <Svg width={72} height={30} viewBox="0 0 72 30">
          <Path d="M2 2h68L36 28z" fill={colors.brand} stroke={colors.ink} strokeWidth={2} strokeLinejoin="round" />
        </Svg>
      </Animated.View>
    </View>
  );
}

const styles = StyleSheet.create({
  lock: { width: 24, height: 28 },
  trash: { width: 24, height: 24 },
  trashLid: { transformOrigin: '4px 7px' },
  bin: { width: BIN.width, height: BIN.height },
  binLid: { position: 'absolute', left: 4, top: 6, width: 56, height: 8, borderRadius: 3, backgroundColor: colors.alert, transformOrigin: '6px 8px' },
  binHandle: { position: 'absolute', left: 24, top: 0, width: 16, height: 8, borderTopLeftRadius: 3, borderTopRightRadius: 3, borderWidth: 2, borderBottomWidth: 0, borderColor: colors.alert },
  binBody: {
    position: 'absolute',
    left: 8,
    top: 18,
    width: 48,
    height: 52,
    borderWidth: 3,
    borderTopWidth: 0,
    borderColor: colors.alert,
    borderBottomLeftRadius: 8,
    borderBottomRightRadius: 8,
    backgroundColor: colors.surface,
  },
  envelope: { width: ENVELOPE.width, height: ENVELOPE.height },
  envelopeBox: { position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, borderWidth: 2, borderColor: colors.ink, borderRadius: 6, backgroundColor: colors.surface },
  flap: { position: 'absolute', left: 0, top: 0, width: 72, height: 30, transformOrigin: '36px 1px' },
});
