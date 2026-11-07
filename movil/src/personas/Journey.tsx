// «Recorrido» of the person card, vertical as the design asks at mobile size: a 24 px mark per step joined
// by a line, with its date. Reached steps carry a check; Cerrado and Descartado are a dashed alternative end.
import type { Stage, StageState } from '@compartido/logic/journey';
import { StyleSheet, View } from 'react-native';
import { Icon } from '@/components/icons';
import { T } from '@/components/ui';
import { colors, radius, space } from '@/theme/tokens';

const SPOKEN: Record<StageState, string> = { done: 'hecho', current: 'ahora', pending: 'pendiente', alt: 'final alternativo' };

const MARK: Record<StageState, { bg: string; border: string; fg: string; dashed?: boolean }> = {
  done: { bg: colors.brandLight, border: colors.brandDeep, fg: colors.brandDeep },
  current: { bg: colors.brand, border: colors.ink, fg: colors.ink },
  pending: { bg: colors.surface, border: colors.inkSoft, fg: colors.inkSoft },
  alt: { bg: colors.line, border: colors.inkSoft, fg: colors.inkSoft, dashed: true },
};

export function Journey({ stages, label }: { stages: Stage[]; label: string }) {
  return (
    <View accessibilityRole="list" accessibilityLabel={label} testID="journey">
      {stages.map((stage, index) => {
        const mark = MARK[stage.state];
        const sub = [stage.date, stage.detail].filter(Boolean).join(' · ');
        return (
          <View
            key={stage.key}
            style={styles.step}
            accessible
            accessibilityLabel={`${stage.label}, ${SPOKEN[stage.state]}${sub ? `, ${sub}` : ''}`}
            accessibilityState={{ selected: stage.state === 'current' }}
            testID={`journey-${stage.key}`}
          >
            {index < stages.length - 1 ? <View style={styles.line} /> : null}
            <View style={[styles.mark, { backgroundColor: mark.bg, borderColor: mark.border }, mark.dashed ? styles.dashed : null]}>
              {stage.state === 'done' || stage.state === 'current' ? <Icon name="check" size={14} color={mark.fg} /> : null}
            </View>
            <View style={styles.text}>
              <T color={stage.state === 'pending' ? colors.inkSoft : colors.ink}>{stage.label}</T>
              {sub ? (
                <T variant="detalle" soft>
                  {sub}
                </T>
              ) : null}
            </View>
          </View>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  step: { flexDirection: 'row', alignItems: 'flex-start', gap: space[3], paddingBottom: space[3] },
  line: { position: 'absolute', left: 11, top: 28, bottom: -6, width: 2, backgroundColor: colors.line },
  mark: { width: 24, height: 24, borderRadius: radius.pill, borderWidth: 1, alignItems: 'center', justifyContent: 'center' },
  dashed: { borderStyle: 'dashed' },
  text: { flex: 1 },
});
