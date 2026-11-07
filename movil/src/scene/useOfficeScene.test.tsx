import { act, screen } from '@testing-library/react-native';
import { renderApp } from '@/test/render';
import { T } from '@/components/ui';
import { useOfficeScene } from './useOfficeScene';

interface TestFrame { active: boolean; callback: (frame: { timeSincePreviousFrame: number | null }) => void }
const mockFrame: TestFrame = { active: false, callback: () => undefined };
jest.mock('react-native-reanimated', () => {
  const actual = jest.requireActual('react-native-reanimated');
  return { ...actual, useFrameCallback: (callback: TestFrame['callback']) => {
    mockFrame.callback = callback;
    return require('react').useMemo(() => ({ setActive: (active: boolean) => { mockFrame.active = active; } }), []);
  } };
});
const statuses = { copywriter_a: 'trabajando' as const };
const page = { now: '2026-11-07T15:00:00Z', events: [{ id: 1, ts: '2026-11-07T15:00:00Z', tipo: 'consulta_biblioteca' as const, rol: 'copywriter_a', destino: 'biblioteca', detalle: 'clase 03' }] };
const renders = jest.fn();
function Probe({ active = true, reduced = false }: { active?: boolean; reduced?: boolean }) {
  const { snapshot } = useOfficeScene({ active, live: true, paused: false, reduced, statuses, page });
  renders();
  return <T>{snapshot.now?.text ?? 'Cargando'}</T>;
}
it('keeps ordinary frames off React, disables the callback on blur and in reduced motion, and cleans up', async () => {
  const view = await renderApp(<Probe />);
  await screen.findByText('Copywriter A va a la biblioteca: “clase 03”');
  await act(async () => undefined);
  expect(mockFrame.active).toBe(true);
  const before = renders.mock.calls.length;
  await act(async () => {
    for (let i = 0; i < 50; i++) mockFrame.callback({ timeSincePreviousFrame: 16 });
  });
  expect(renders).toHaveBeenCalledTimes(before);
  await view.rerender(<Probe active={false} />); expect(mockFrame.active).toBe(false);
  await view.rerender(<Probe reduced />); expect(mockFrame.active).toBe(false);
  await view.rerender(<Probe />); expect(mockFrame.active).toBe(true);
  await view.unmount(); expect(mockFrame.active).toBe(false);
});
