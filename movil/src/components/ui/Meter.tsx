import { StyleSheet, View } from 'react-native';
import { colors, radius, space } from '@/theme/tokens';
import { T } from './Text';

export type MeterTone = 'ok' | 'warn' | 'bad';

/** Same thresholds as the PWA's Meter: 0ff1ce-hondo below 80 %, post-it from 80 %, alerta at 100 % (or over). */
export function meterTone(value: number, max: number): MeterTone {
  const fraction = max > 0 ? value / max : 0;
  if (fraction >= 1) return 'bad';
  if (fraction >= 0.8) return 'warn';
  return 'ok';
}

const FILL: Record<MeterTone, string> = { ok: colors.brandDeep, warn: colors.postIt, bad: colors.alert };

/** Usage against a cap (ui.css .meter): label, «6 de 10» on the right and an 8 px bar. */
export function Meter({ label, value, max, display }: { label: string; value: number; max: number; display?: string }) {
  const safe = Number.isFinite(value) ? value : 0;
  const fraction = max > 0 ? Math.min(1, Math.max(0, safe / max)) : 0;
  const text = display ?? `${safe} de ${max}`;
  return (
    <View style={styles.meter}>
      <View style={styles.head}>
        <T variant="detalle" style={styles.label}>
          {label}
        </T>
        <T variant="detalle" soft style={styles.value}>
          {text}
        </T>
      </View>
      <View
        accessible
        accessibilityRole="progressbar"
        accessibilityLabel={label}
        accessibilityValue={{ min: 0, max, now: safe, text }}
        style={styles.bar}
      >
        <View style={[styles.fill, { width: `${fraction * 100}%`, backgroundColor: FILL[meterTone(safe, max)] }]} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  meter: { gap: 6 },
  head: { flexDirection: 'row', alignItems: 'center', gap: space[2] },
  label: { flexShrink: 1 },
  value: { marginLeft: 'auto', textAlign: 'right' },
  bar: { height: 8, borderRadius: radius.pill, backgroundColor: colors.line, overflow: 'hidden' },
  fill: { height: 8 },
});
