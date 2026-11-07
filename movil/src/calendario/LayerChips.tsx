// The layer chips (Calendario.dc.html): a dot of the layer's colour, outlined in tinta when on; a layer
// the backend does not have yet is dashed and disabled («aún no disponible»).
import type { CalendarLayer } from '@compartido/api/types';
import { CALENDAR_LAYERS } from '@compartido/api/types';
import { LAYER_LABEL } from '@compartido/logic/events';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { T } from '@/components/ui';
import { haptic } from '@/theme/motion';
import { colors, layers as LAYER_COLOR, radius, shell, space } from '@/theme/tokens';

const PARTIAL_HINT = 'Por ahora solo las oportunidades: las conversaciones llegan con el inbox';

export function LayerChips({
  layers,
  visible,
  onToggle,
}: {
  layers: Partial<Record<CalendarLayer, boolean | 'parcial'>> | undefined;
  visible: ReadonlySet<CalendarLayer>;
  onToggle: (layer: CalendarLayer) => void;
}) {
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.strip} accessibilityLabel="Capas" style={styles.scroll}>
      {CALENDAR_LAYERS.map((layer) => {
        const state = layers?.[layer];
        const unavailable = state === false;
        const on = visible.has(layer);
        const text = unavailable ? `${LAYER_LABEL[layer]} · aún no disponible` : state === 'parcial' ? `${LAYER_LABEL[layer]} · parcial` : LAYER_LABEL[layer];
        return (
          <Pressable
            key={layer}
            testID={`capa-${layer}`}
            accessibilityRole="button"
            accessibilityLabel={text}
            accessibilityHint={state === 'parcial' ? PARTIAL_HINT : undefined}
            accessibilityState={{ selected: on, disabled: unavailable }}
            disabled={unavailable}
            onPress={() => {
              haptic('toggle');
              onToggle(layer);
            }}
            style={[styles.chip, unavailable ? styles.unavailable : on ? styles.on : styles.off]}
          >
            <View style={[styles.dot, { backgroundColor: LAYER_COLOR[layer] }]} />
            <T variant="detalle" color={on && !unavailable ? colors.ink : colors.inkSoft} numberOfLines={1}>
              {text}
            </T>
          </Pressable>
        );
      })}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  scroll: { marginHorizontal: -shell.gutter },
  strip: { gap: space[2], paddingHorizontal: shell.gutter },
  chip: { minHeight: shell.touch, paddingHorizontal: space[3], flexDirection: 'row', alignItems: 'center', gap: space[2], borderRadius: radius.pill, borderWidth: 1 },
  on: { borderColor: colors.ink, backgroundColor: colors.surface },
  off: { borderColor: colors.line, backgroundColor: 'transparent' },
  unavailable: { borderColor: colors.inkSoft, borderStyle: 'dashed', backgroundColor: 'transparent' },
  dot: { width: 10, height: 10, borderRadius: radius.pill, borderWidth: 1, borderColor: colors.ink },
});
