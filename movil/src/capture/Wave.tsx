import { StyleSheet, View } from 'react-native';
import { colors } from '@/theme/tokens';

// A voice wave like WhatsApp's: thin rounded bars that follow the voice. The app's own sizes (the PWA keeps the
// 24 bars of compartido's WAVE_BARS).

/** Live levels the recorder keeps: enough 5 px bars to fill the widest sheet; the oldest leave on the left. */
export const LIVE_BARS = 80;
/** Bars of a finished recording, spread across its row. */
export const CLIP_BARS = 36;
const BAR_WIDTH = 3;
const BAR_GAP = 2;
const MIN_HEIGHT = 3;
const MAX_HEIGHT = 28;

export function barHeight(level: number): number {
  return MIN_HEIGHT + Math.round(Math.min(1, Math.max(0, level || 0)) * (MAX_HEIGHT - MIN_HEIGHT));
}

/**
 * `live` (recording): the newest bar is at the right and the wave moves left as levels arrive. `clip` (a finished
 * recording): its bars spread across the row. `hondo` in the sheet, `suave` while holding the capture button.
 */
export function Wave({ levels, tone = 'hondo', mode = 'live' }: { levels: number[]; tone?: 'hondo' | 'suave'; mode?: 'live' | 'clip' }) {
  const color = tone === 'hondo' ? colors.brandDeep : colors.inkSoft;
  const spread = mode === 'clip' && levels.length >= CLIP_BARS;
  return (
    <View
      style={[styles.wave, mode === 'live' ? styles.live : spread ? styles.spread : styles.start]}
      accessible={false}
      importantForAccessibility="no-hide-descendants"
      testID={`capture-wave-${mode}`}
    >
      {levels.map((level, index) => (
        <View key={index} style={[styles.bar, { height: barHeight(level), backgroundColor: color }]} />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  wave: { flex: 1, minWidth: 0, height: MAX_HEIGHT + 4, flexDirection: 'row', alignItems: 'center', gap: BAR_GAP, overflow: 'hidden' },
  live: { justifyContent: 'flex-end' },
  spread: { justifyContent: 'space-between' },
  start: { justifyContent: 'flex-start' },
  bar: { width: BAR_WIDTH, flexShrink: 0, borderRadius: BAR_WIDTH / 2 },
});
