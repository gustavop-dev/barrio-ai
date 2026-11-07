import { StyleSheet, View } from 'react-native';
import { colors, radius } from '@/theme/tokens';
import { T } from './Text';

/** Two initials of a name («Lucía Ficticia» → LF). */
export function initials(name: string | null | undefined): string {
  const words = (name ?? '').trim().split(/\s+/).filter(Boolean);
  if (!words.length) return '?';
  const first = words[0]!.charAt(0);
  const last = words.length > 1 ? words[words.length - 1]!.charAt(0) : '';
  return (first + last).toLocaleUpperCase('es-CO');
}

/** Person avatar: initials on the info tone. Decorative. */
export function Avatar({ name, size = 40 }: { name: string | null | undefined; size?: 32 | 40 | 48 }) {
  return (
    <View style={[styles.avatar, { width: size, height: size }]} accessible={false} importantForAccessibility="no-hide-descendants">
      <T variant="detalle" color={colors.info}>
        {initials(name)}
      </T>
    </View>
  );
}

const styles = StyleSheet.create({
  avatar: { borderRadius: radius.pill, backgroundColor: colors.infoLight, alignItems: 'center', justifyContent: 'center' },
});
