import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { shell, space } from '@/theme/tokens';

/** Bottom padding for scrolling content under the floating bottom bar (and the toast above it). */
export function useContentInsets(): { bottom: number } {
  const insets = useSafeAreaInsets();
  return { bottom: shell.tabBarHeight + insets.bottom + space[10] };
}
