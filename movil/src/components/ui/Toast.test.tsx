// Toasts and sheets: a sheet is a Modal, a window over the app's, so a toast drawn in the app's window would sit under
// it. The toast is drawn in the newest open sheet's window (ToastOutlet) and, when that sheet closes, in the app's
// again, with the time it had left. Covers a toast while the sheet stays open («Envío deshecho.» in «Lo que enviaste»)
// and a toast followed by closing the sheet in the same handler («Foto guardada.», «Oportunidad registrada»).
import { act, fireEvent, screen } from '@testing-library/react-native';
import { useState } from 'react';
import { renderApp } from '@/test/render';
import { durations, toastDurations } from '@/theme/motion';
import { Button } from './Button';
import { Sheet } from './Sheet';
import { T } from './Text';
import { useToast } from './Toast';

function Harness() {
  const toast = useToast();
  const [open, setOpen] = useState(true);
  return (
    <>
      <T>Pantalla</T>
      {open ? (
        <Sheet label="Hoja" onClose={() => setOpen(false)} testID="hoja">
          <Button onPress={() => toast.show('Sigue abierta.')}>Avisar</Button>
          <Button
            onPress={() => {
              toast.show('Guardado.');
              setOpen(false);
            }}
          >
            Guardar y cerrar
          </Button>
          <Button onPress={() => setOpen(false)}>Cerrar</Button>
        </Sheet>
      ) : null}
    </>
  );
}

const advance = async (ms: number) =>
  act(async () => {
    await jest.advanceTimersByTimeAsync(ms);
  });

beforeEach(() => jest.useFakeTimers());
afterEach(() => jest.useRealTimers());

describe('toasts and sheets', () => {
  it('a toast shown while a sheet stays open is drawn in the sheet’s window, above it', async () => {
    await renderApp(<Harness />);
    await fireEvent.press(screen.getByText('Avisar'));
    expect(screen.getByTestId('hoja-modal')).toContainElement(screen.getByTestId('toast'));
    expect(screen.getByText('Sigue abierta.')).toBeOnTheScreen();
  });

  it('a toast shown right before its sheet closes, in the same handler, stays visible in the app’s window', async () => {
    await renderApp(<Harness />);
    await fireEvent.press(screen.getByText('Guardar y cerrar'));
    await advance(0);
    expect(screen.queryByTestId('hoja')).toBeNull();
    expect(screen.getByTestId('toast')).toBeOnTheScreen();
    expect(screen.getByText('Guardado.')).toBeOnTheScreen();
    // Still there after the frames that follow the close.
    await advance(durations.base);
    expect(screen.getByText('Guardado.')).toBeOnTheScreen();
  });

  it('when the sheet closes, the toast moves to the app’s window and keeps the time it had left', async () => {
    await renderApp(<Harness />);
    await fireEvent.press(screen.getByText('Avisar'));
    await advance(toastDurations.plain - 1000);
    await fireEvent.press(screen.getByText('Cerrar'));
    await advance(0);
    expect(screen.queryByTestId('hoja-modal')).toBeNull();
    expect(screen.getByText('Sigue abierta.')).toBeOnTheScreen();
    // The second it had left, and its fade: gone, not shown for a new full duration.
    await advance(1000 + durations.fast + 50);
    expect(screen.queryByText('Sigue abierta.')).toBeNull();
  });
});
