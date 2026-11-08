import type { QueryClient } from '@tanstack/react-query';
import { createCaptura, type CaptureOutput } from '@compartido/api/capturas';

// The existing mutation cache is the send signal. No second request, capture-sheet change or
// success haptic. Remember receipts per session/client so remounting Oficina cannot replay them.
const received = new WeakMap<QueryClient, Set<string>>();

export function subscribeCaptureReceipts(client: QueryClient, onReceipt: () => void): () => void {
  const seen = received.get(client) ?? new Set<string>();
  received.set(client, seen);
  const cache = client.getMutationCache();
  const read = (mutation: ReturnType<typeof cache.getAll>[number]) => {
    if (mutation.options.mutationFn !== createCaptura || mutation.state.status !== 'success') return;
    const capture = mutation.state.data as CaptureOutput | undefined;
    if (!capture?.id || seen.has(capture.id)) return;
    seen.add(capture.id);
    onReceipt();
  };
  const unsubscribe = cache.subscribe((event) => {
    if (event.type === 'updated' && event.action.type === 'success') read(event.mutation);
  });
  // Also covers opening the app on another tab and visiting Oficina after sending there.
  cache.getAll().forEach(read);
  return unsubscribe;
}
