import { Pressable, StyleSheet, View } from 'react-native';
import { haptic } from '@/theme/motion';
import { colors, radius, space } from '@/theme/tokens';
import { T } from './Text';

/** Segmented control (ui.css .segmented, the Calendario's Mes · Semana · Lista): a linea track, the chosen one on superficie. */
export function Segmented<V extends string>({ label, options, value, onChange }: { label: string; options: readonly { value: V; label: string }[]; value: V; onChange: (value: V) => void }) {
  return (
    <View style={styles.track} accessibilityRole="tablist" accessibilityLabel={label}>
      {options.map((option) => {
        const selected = option.value === value;
        return (
          <Pressable
            key={option.value}
            accessibilityRole="tab"
            accessibilityState={{ selected }}
            hitSlop={4}
            onPress={() => {
              if (selected) return;
              haptic('tabChange');
              onChange(option.value);
            }}
            style={[styles.option, selected ? styles.selected : null]}
          >
            <T variant="detalle" color={selected ? colors.ink : colors.inkSoft}>
              {option.label}
            </T>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  track: { flexDirection: 'row', gap: space[1], padding: space[1], backgroundColor: colors.line, borderRadius: radius.md },
  option: { flex: 1, minHeight: 40, alignItems: 'center', justifyContent: 'center', borderRadius: radius.sm },
  selected: { backgroundColor: colors.surface },
});
