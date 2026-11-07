// The 5 preparation steps of a piece (the PWA's StageTrack «numbered», Pieza.dc.html «Preparándose»):
// 32 px circles, a check when done, the number otherwise, and «Hecho» / «Ahora» on the right.
import type { PreparationStage } from '@compartido/logic/piece';
import { StyleSheet, View } from 'react-native';
import { Icon } from '@/components/icons';
import { T } from '@/components/ui';
import { colors, radius, shell, space } from '@/theme/tokens';

const SPOKEN: Record<PreparationStage['state'], string> = { done: 'hecho', current: 'ahora', pending: 'pendiente' };
const RIGHT: Record<PreparationStage['state'], string> = { done: 'Hecho', current: 'Ahora', pending: '' };

export function PreparationTrack({ stages, label }: { stages: PreparationStage[]; label: string }) {
  return (
    <View accessibilityLabel={label} style={styles.track}>
      {stages.map((stage, index) => (
        <View key={stage.key} style={styles.step} accessible accessibilityLabel={`${index + 1}. ${stage.label}, ${SPOKEN[stage.state]}`}>
          <View style={[styles.mark, styles[stage.state]]}>
            {stage.state === 'done' ? (
              <Icon name="check" size={18} color={colors.brandDeep} />
            ) : (
              <T variant="detalle" color={stage.state === 'current' ? colors.ink : colors.inkSoft}>
                {String(index + 1)}
              </T>
            )}
          </View>
          <T style={styles.label} soft={stage.state === 'pending'}>
            {stage.label}
          </T>
          <T variant="detalle" soft>
            {RIGHT[stage.state]}
          </T>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  track: { gap: space[1] },
  step: { flexDirection: 'row', alignItems: 'center', gap: space[3], minHeight: shell.touch },
  mark: { width: 32, height: 32, borderRadius: radius.pill, borderWidth: 1, alignItems: 'center', justifyContent: 'center' },
  done: { backgroundColor: colors.brandLight, borderColor: colors.brandLight },
  current: { backgroundColor: colors.postIt, borderColor: colors.ink },
  pending: { backgroundColor: colors.surface, borderColor: colors.inkSoft },
  label: { flex: 1 },
});
