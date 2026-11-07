// Small pieces the Ajustes sections share: the «Aún no disponible» state, a card head (title and
// badges), a labelled block inside a card, a cap or read line, and the big stop and resume buttons.
import { isMeterLine, type LimitLine } from '@compartido/logic/ajustes';
import type { ReactNode } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, View } from 'react-native';
import { KeyValue, Meter, T } from '@/components/ui';
import { colors, radius, space } from '@/theme/tokens';

/** The intentional «Aún no disponible» state: muted, dashed, never an error. */
export function Unavailable({ children }: { children?: string }) {
  return (
    <View style={styles.unavailable}>
      <T>Aún no disponible</T>
      {children ? (
        <T variant="detalle" soft>
          {children}
        </T>
      ) : null}
    </View>
  );
}

/** «Micrófono · PERMITIDO»: the card's subject on the left, its badges on the right. */
export function CardHead({ title, children }: { title?: string; children?: ReactNode }) {
  return (
    <View style={[styles.head, title ? null : styles.headBare]}>
      {title ? <T style={styles.headTitle}>{title}</T> : null}
      {children ? <View style={styles.badges}>{children}</View> : null}
    </View>
  );
}

/** A labelled block inside a card or a fold («VENTANA HORARIA»). */
export function Block({ label, children }: { label: string; children: ReactNode }) {
  return (
    <View style={styles.block} accessibilityRole="summary" accessibilityLabel={label}>
      <T variant="etiqueta" soft accessibilityRole="header">
        {label}
      </T>
      {children}
    </View>
  );
}

/** A cap or read: a meter with its usage, or the cap alone («sin dato de uso», never 0). */
export function LimitRow({ line }: { line: LimitLine }) {
  return isMeterLine(line) ? <Meter label={line.label} value={line.used} max={line.max} /> : <KeyValue label={line.label}>{line.text}</KeyValue>;
}

/** The big total-stop (alerta) and resume (0ff1ce) buttons: 56 dp, UPPERCASE. */
export function MachineButton({
  kind,
  children,
  onPress,
  disabled,
  busy,
}: {
  kind: 'stop' | 'resume';
  children: string;
  onPress: () => void;
  disabled?: boolean;
  busy?: boolean;
}) {
  const inactive = Boolean(disabled || busy);
  const fill = disabled ? colors.line : kind === 'stop' ? colors.alert : colors.brand;
  const fg = disabled ? colors.inkSoft : kind === 'stop' ? colors.onAlert : colors.onBrand;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={children}
      accessibilityState={{ disabled: inactive, busy: Boolean(busy) }}
      disabled={inactive}
      onPress={onPress}
      style={({ pressed }) => [styles.machine, { backgroundColor: fill, borderColor: fill }, pressed ? styles.pressed : null]}
    >
      {busy ? <ActivityIndicator size="small" color={fg} /> : null}
      <T color={fg} style={styles.machineText}>
        {children}
      </T>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  unavailable: { padding: space[4], gap: space[1], borderWidth: 1, borderStyle: 'dashed', borderColor: colors.inkSoft, borderRadius: radius.md },
  head: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: space[2], flexWrap: 'wrap' },
  headBare: { justifyContent: 'flex-start' },
  headTitle: { flexShrink: 1 },
  badges: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  block: { gap: 6 },
  machine: { minHeight: 56, borderWidth: 1, borderRadius: radius.md, paddingHorizontal: space[4], flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: space[2] },
  pressed: { opacity: 0.85 },
  machineText: { textTransform: 'uppercase', letterSpacing: 0.96 },
});
