// An image the API serves only to the session (gallery photos, capture photos): expo-image with the
// API origin prefixed and the device token as a bearer header. URLs that are not a same-origin path
// (`/media/…`) are never loaded, as in the PWA (sameOrigin).
import { sameOrigin } from '@compartido/api/capturas';
import { Image, type ImageContentFit } from 'expo-image';
import { StyleSheet, View, type ImageStyle, type StyleProp } from 'react-native';
import { apiUrl } from '@/api/config';
import { authHeaders } from '@/api/transport';
import { Icon } from '@/components/icons';
import { colors } from '@/theme/tokens';

/** The expo-image source of an API path with the bearer token, or null for anything else. */
export function apiImageSource(path: string | null | undefined): { uri: string; headers: Record<string, string>; cacheKey: string } | null {
  const safe = sameOrigin(path);
  if (!safe) return null;
  // The cache key is the path: the same photo after a new login is still the same file.
  return { uri: apiUrl(safe), headers: authHeaders(), cacheKey: safe };
}

export function ApiImage({
  path,
  style,
  contentFit = 'cover',
  accessibilityLabel,
  recyclingKey,
  testID,
}: {
  path: string | null | undefined;
  style?: StyleProp<ImageStyle>;
  contentFit?: ImageContentFit;
  /** Leave it out when the parent already has the label (a tile button). */
  accessibilityLabel?: string;
  /** For recycled list cells: the photo id. */
  recyclingKey?: string;
  testID?: string;
}) {
  const source = apiImageSource(path);
  if (!source) {
    return (
      <View style={[styles.empty, style]} testID={testID}>
        <Icon name="galeria" size={22} color={colors.paper} />
      </View>
    );
  }
  return (
    <Image
      testID={testID}
      source={source}
      style={[styles.image, style]}
      contentFit={contentFit}
      recyclingKey={recyclingKey}
      accessible={Boolean(accessibilityLabel)}
      accessibilityLabel={accessibilityLabel}
      cachePolicy="memory-disk"
    />
  );
}

const styles = StyleSheet.create({
  image: { backgroundColor: colors.line },
  empty: { backgroundColor: colors.spriteBlue, alignItems: 'center', justifyContent: 'center' },
});
