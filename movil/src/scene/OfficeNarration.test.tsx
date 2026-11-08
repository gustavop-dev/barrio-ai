import { act, screen } from '@testing-library/react-native';
import { renderApp } from '@/test/render';
import { officeNarration, timings } from '@/theme/motion';
import { OfficeNarration } from './OfficeNarration';

const line = { text: 'Llegó tu captura a la oficina.', role: 'operador_cuenta' as const };
beforeEach(() => jest.useFakeTimers());
afterEach(() => jest.useRealTimers());
const advance = async (ms: number) => act(async () => { await jest.advanceTimersByTimeAsync(ms); });

it('retires after the 3.5 s hold plus 180 ms exit and does not reappear on ordinary rerenders', async () => {
  const view = await renderApp(<OfficeNarration line={line} revision={1} reduced={false} />);
  await advance(officeNarration.holdMs);
  expect(screen.getByTestId('office-narration')).toBeOnTheScreen();
  await advance(timings.officeNowRetire.duration);
  expect(screen.queryByTestId('office-narration')).toBeNull();
  await view.rerender(<OfficeNarration line={{ ...line }} revision={1} reduced={false} />);
  expect(screen.queryByTestId('office-narration')).toBeNull();
  await view.rerender(<OfficeNarration line={line} revision={2} reduced={false} />);
  expect(screen.getByText(line.text)).toBeOnTheScreen();
});

it('cancels the old retirement when another narration arrives', async () => {
  const view = await renderApp(<OfficeNarration line={line} revision={1} reduced={false} />);
  await advance(officeNarration.holdMs - 100);
  const next = { ...line, text: 'Operación lleva tu captura a Mesa editorial.' };
  await view.rerender(<OfficeNarration line={next} revision={2} reduced={false} />);
  await advance(100 + timings.officeNowRetire.duration);
  expect(screen.getByText(next.text)).toBeOnTheScreen();
  await advance(officeNarration.holdMs);
  expect(screen.queryByTestId('office-narration')).toBeNull();
});

it('reduced motion replaces text immediately and keeps it visible, as the board does', async () => {
  const view = await renderApp(<OfficeNarration line={line} revision={1} reduced />);
  await advance(officeNarration.holdMs * 2);
  expect(screen.getByText(line.text)).toBeOnTheScreen();
  await view.rerender(<OfficeNarration line={{ ...line, text: 'Otra captura' }} revision={2} reduced />);
  expect(screen.queryByText(line.text)).toBeNull();
  expect(screen.getByText('Otra captura')).toBeOnTheScreen();
  await view.unmount();
  await advance(officeNarration.holdMs * 2);
});
