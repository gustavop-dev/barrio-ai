// A link that leaves the app (a LinkedIn profile, a post, a conversation): 0ff1ce-hondo text with the ↗
// icon, opened by the system. Only https addresses render; anything else renders nothing.
import type { ReactNode } from 'react';
import { Linking, Pressable, StyleSheet } from 'react-native';
import { Icon } from '@/components/icons';
import { isHttps } from '@/navigation';
import { colors, space } from '@/theme/tokens';
import { T } from './Text';

export function ExternalLink({
  href,
  children,
  hint = 'Se abre fuera de la app',
  accessibilityLabel,
  testID,
}: {
  href: string | null | undefined;
  children: ReactNode;
  hint?: string;
  accessibilityLabel?: string;
  testID?: string;
}) {
  if (!href || !isHttps(href)) return null;
  return (
    <Pressable
      testID={testID}
      accessibilityRole="link"
      accessibilityLabel={accessibilityLabel}
      accessibilityHint={hint}
      onPress={() => void Linking.openURL(href)}
      style={({ pressed }) => [styles.link, pressed ? styles.pressed : null]}
    >
      {typeof children === 'string' ? <T color={colors.brandDeep}>{children}</T> : children}
      <Icon name="external" size={16} color={colors.brandDeep} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  link: { minHeight: 48, flexDirection: 'row', alignItems: 'center', gap: space[1], alignSelf: 'flex-start' },
  pressed: { opacity: 0.7 },
});
