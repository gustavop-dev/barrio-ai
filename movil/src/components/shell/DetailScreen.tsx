import { router } from 'expo-router';
import type { ReactNode } from 'react';
import { StyleSheet, View } from 'react-native';
import { colors } from '@/theme/tokens';
import { TopBar } from './TopBar';

/** A detail view above the tabs: the top bar with «‹ {back}» instead of the signature. */
export function DetailScreen({ back, fallback, children }: { back: string; fallback: '/calendario' | '/personas'; children: ReactNode }) {
  return (
    <View style={styles.screen}>
      <TopBar back={{ label: back, onPress: () => (router.canGoBack() ? router.back() : router.replace(fallback)) }} />
      {children}
    </View>
  );
}

const styles = StyleSheet.create({ screen: { flex: 1, backgroundColor: colors.paper } });
