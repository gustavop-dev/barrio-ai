// Renders a piece of the app with the providers it needs: a fresh QueryClient (no retries), the
// toast and, on request, the session and the recorder.
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, type RenderOptions } from '@testing-library/react-native';
import type { ReactElement, ReactNode } from 'react';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { SessionProvider } from '@/auth/session';
import { RecorderProvider } from '@/capture/recorder';
import { ToastProvider } from '@/components/ui';

export function testQueryClient(): QueryClient {
  return new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity, staleTime: 0 }, mutations: { retry: false, gcTime: Infinity } } });
}

export interface RenderAppOptions extends Omit<RenderOptions, 'wrapper'> {
  client?: QueryClient;
  session?: boolean;
  recorder?: boolean;
}

export async function renderApp(ui: ReactElement, { client = testQueryClient(), session = false, recorder = false, ...options }: RenderAppOptions = {}) {
  function Wrapper({ children }: { children: ReactNode }) {
    let tree = <ToastProvider>{children}</ToastProvider>;
    if (recorder) tree = <RecorderProvider>{tree}</RecorderProvider>;
    if (session) tree = <SessionProvider autoRegisterPush={false}>{tree}</SessionProvider>;
    return (
      <GestureHandlerRootView style={{ flex: 1 }}>
        <QueryClientProvider client={client}>{tree}</QueryClientProvider>
      </GestureHandlerRootView>
    );
  }
  const result = await render(ui, { wrapper: Wrapper, ...options });
  return { client, ...result };
}
