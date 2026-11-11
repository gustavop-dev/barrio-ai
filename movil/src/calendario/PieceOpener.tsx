// The piece cards of the Calendario open the piece with a tap on their text, not on a link at the bottom: they show
// the badge, the hour and a short preview (thesis and first lines, clamped with «…»), and the piece detail has the
// rest. Vetar stays outside, its own button in the card.
import type { pieceStatus } from '@compartido/logic/editorial';
import type { ReactNode } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { Icon } from '@/components/icons';
import { Badge, T } from '@/components/ui';
import { openLink } from '@/navigation';
import { colors, space } from '@/theme/tokens';

/** The thesis in 2 lines and the first lines in 2 more: enough to know what the piece is about. */
export const PIECE_PREVIEW_LINES = 2;

export function PieceOpener({ to, children, testID }: { to: string | null; children: ReactNode; testID?: string }) {
  if (!to) return <View style={styles.body}>{children}</View>;
  return (
    <Pressable
      accessibilityRole="link"
      accessibilityHint="Abre la pieza"
      onPress={() => openLink(to)}
      testID={testID}
      style={({ pressed }) => [styles.body, pressed ? styles.pressed : null]}
    >
      {children}
    </Pressable>
  );
}

/** Badge and hour on one line, with the chevron that says the card opens. */
export function PieceHead({ badge, when, opens }: { badge: ReturnType<typeof pieceStatus>; when: string | null | undefined; opens: boolean }) {
  return (
    <View style={styles.head}>
      <Badge tone={badge.tone}>{badge.label}</Badge>
      <View style={styles.headEnd}>
        {when ? (
          <T variant="detalle" soft style={styles.when}>
            {when}
          </T>
        ) : null}
        {opens ? <Icon name="chevronRight" size={20} color={colors.inkSoft} /> : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  body: { gap: space[2] },
  pressed: { opacity: 0.7 },
  head: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: space[2] },
  headEnd: { flexDirection: 'row', alignItems: 'center', gap: space[1], flexShrink: 1 },
  when: { flexShrink: 1 },
});
