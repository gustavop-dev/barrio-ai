// The shared QueryClient (compartido/src/api/queryClient.ts) plus what React Native lacks: refetch
// when the app comes back to the foreground, and pause while there is no network.
import NetInfo from '@react-native-community/netinfo';
import { focusManager, onlineManager } from '@tanstack/react-query';
import { AppState, type AppStateStatus } from 'react-native';

export { createQueryClient, keys, shouldRetry } from '@compartido/api/queryClient';

let wired = false;

/** Call once at start-up. */
export function wireQueryManagers(): void {
  if (wired) return;
  wired = true;
  focusManager.setEventListener((setFocused) => {
    const subscription = AppState.addEventListener('change', (status: AppStateStatus) => setFocused(status === 'active'));
    return () => subscription.remove();
  });
  onlineManager.setEventListener((setOnline) =>
    NetInfo.addEventListener((state) => {
      setOnline(state.isConnected !== false);
    }),
  );
}
