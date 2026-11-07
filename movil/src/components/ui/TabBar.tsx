import { Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { haptic } from '@/theme/motion';
import { colors, shell, space } from '@/theme/tokens';
import { T } from './Text';

/** Underlined tabs inside a view (ui.css .tabbar): «Pendiente · Lo que el equipo sabe de ti». */
export function TabBar<V extends string>({ label, tabs, value, onChange }: { label: string; tabs: readonly { value: V; label: string }[]; value: V; onChange: (value: V) => void }) {
  return (
    <View style={styles.bar} accessibilityRole="tablist" accessibilityLabel={label}>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.tabs}>
        {tabs.map((tab) => {
          const selected = tab.value === value;
          return (
            <Pressable
              key={tab.value}
              accessibilityRole="tab"
              accessibilityState={{ selected }}
              onPress={() => {
                if (selected) return;
                haptic('tabChange');
                onChange(tab.value);
              }}
              style={[styles.tab, selected ? styles.selected : null]}
            >
              <T>{tab.label}</T>
            </Pressable>
          );
        })}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  bar: { borderBottomWidth: 1, borderBottomColor: colors.line },
  tabs: { gap: 20 },
  tab: { minHeight: shell.touch, paddingHorizontal: space[1], justifyContent: 'center', borderBottomWidth: 2, borderBottomColor: 'transparent' },
  selected: { borderBottomColor: colors.ink },
});
