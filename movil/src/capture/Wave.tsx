import { toBars, WAVE_BARS } from '@compartido/logic/audio';
import { StyleSheet, View } from 'react-native';
import { colors } from '@/theme/tokens';

/** The wave of Captura.dc.html: 24 bars from 4 to 32 px. `hondo` in the sheet, `suave` while holding. */
export function Wave({ levels, tone = 'hondo' }: { levels: number[]; tone?: 'hondo' | 'suave' }) {
  const bars = toBars(levels, WAVE_BARS);
  const color = tone === 'hondo' ? colors.brandDeep : colors.inkSoft;
  return (
    <View style={styles.wave} accessible={false} importantForAccessibility="no-hide-descendants">
      {bars.map((level, index) => (
        <View key={index} style={[styles.bar, { height: 4 + Math.round(Math.min(1, Math.max(0, level)) * 28), backgroundColor: color }]} />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  wave: { flex: 1, minWidth: 0, height: 32, flexDirection: 'row', alignItems: 'center', gap: 2, overflow: 'hidden' },
  bar: { flex: 1, minWidth: 2, borderRadius: 2 },
});
