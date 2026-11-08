import { createCaptura } from '@compartido/api/capturas';
import '@/api/transport';
import { testQueryClient } from '@/test/render';
import { fakeServer } from '@/test/server';
import { subscribeCaptureReceipts } from './captureReceipts';

it('listens only to successful sends, once per capture, including sends before Oficina mounts', async () => {
  const server = fakeServer({ 'POST /api/v1/capturas': { status: 201, body: { id: 'c1' } } });
  const client = testQueryClient(), onReceipt = jest.fn();
  const cache = client.getMutationCache();
  const send = () => cache.build(client, { mutationFn: createCaptura }).execute({ nota: 'Una idea' });
  await send();
  const unsubscribe = subscribeCaptureReceipts(client, onReceipt);
  expect(onReceipt).toHaveBeenCalledTimes(1);
  await send(); // Same backend id cannot produce a second receipt.
  expect(onReceipt).toHaveBeenCalledTimes(1);
  server.on('POST /api/v1/capturas', { status: 500 });
  await expect(send()).rejects.toThrow();
  await cache.build(client, { mutationFn: async () => ({ id: 'other' }) }).execute(undefined);
  expect(onReceipt).toHaveBeenCalledTimes(1);
  server.on('POST /api/v1/capturas', { status: 201, body: { id: 'c2' } });
  await send(); expect(onReceipt).toHaveBeenCalledTimes(2);
  unsubscribe();
  const remounted = jest.fn();
  const stop = subscribeCaptureReceipts(client, remounted);
  expect(remounted).not.toHaveBeenCalled();
  stop();
});
