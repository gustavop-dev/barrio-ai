import { renderHook } from '@testing-library/react-native';
import '@/api/transport';
import { fakeServer } from '@/test/server';
import { SEEN_BATCH_MS, useSeenCards } from './useSeenCards';

describe('Nueva → Vista', () => {
  beforeEach(() => jest.useFakeTimers());
  afterEach(() => jest.useRealTimers());

  it('gathers the cards seen in a burst into one POST /tu-turno/vistos, each id once', async () => {
    const server = fakeServer({ 'POST /api/v1/tu-turno/vistos': { body: { count: 2 } } });
    const { result } = await renderHook(() => useSeenCards());
    result.current(['uncertain:a1']);
    result.current(['uncertain:a1', 'conversation:c1']);
    expect(server.requests).toHaveLength(0);
    jest.advanceTimersByTime(SEEN_BATCH_MS);
    expect(server.find('POST', '/api/v1/tu-turno/vistos').map((r) => r.body)).toEqual([{ ids: ['uncertain:a1', 'conversation:c1'] }]);
    result.current(['uncertain:a1']);
    jest.advanceTimersByTime(SEEN_BATCH_MS);
    expect(server.find('POST', '/api/v1/tu-turno/vistos')).toHaveLength(1);
  });
});
