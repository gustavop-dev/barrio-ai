// The UI kit moving as in MovHojas (bottom sheets: snaps with momentum, rubber band, haptic at snaps)
// and MovMicro (buttons, switch, chips, «Copiar», text field, loading).
import { act, fireEvent, screen, waitFor } from '@testing-library/react-native';
import * as Clipboard from 'expo-clipboard';
import * as Haptics from 'expo-haptics';
import { BackHandler } from 'react-native';
import { State } from 'react-native-gesture-handler';
import { fireGestureHandler, getByGestureTestId } from 'react-native-gesture-handler/jest-utils';
// Reanimated's default declarations expose web stubs; Jest installs its native matchers in jest.setup.
import type {} from 'react-native-reanimated/lib/typescript/jestUtils/index.native';
import { renderApp } from '@/test/render';
import { copiedLabelMs, FIRM, haptics, microMotion, sheetMotion } from '@/theme/motion';
import { colors } from '@/theme/tokens';
import { CopyButton } from './CopyButton';
import { FilterChip } from './Chip';
import { Field } from './Field';
import { Sheet, settleSnap } from './Sheet';
import { SnapSheet } from './SnapSheet';
import { SwitchRow } from './SwitchRow';
import { T } from './Text';

jest.mock('expo-clipboard', () => ({ setStringAsync: jest.fn(async () => true) }));

/** Lets an opening spring settle (FIRM is at rest well within this). */
async function letItOpen() {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 800));
  });
}

describe('MovHojas: where a released sheet goes', () => {
  const snaps = sheetMotion.snaps;

  it('uses the board values: snaps 0.5 and 0.9, 150 ms of momentum, closing under 0.25', () => {
    expect(snaps).toEqual([0.5, 0.9]);
    expect(sheetMotion.projectionS).toBe(0.15);
    expect(sheetMotion.closeBelow * snaps[0]).toBe(0.25);
    expect(haptics.sheetSnap).toEqual({ type: 'impact', style: 'light' });
  });

  it('goes to the nearest snap of its projected position, or closes under a quarter', () => {
    expect(settleSnap(0.3, 0, snaps)).toBe(0.5);
    expect(settleSnap(0.24, 0, snaps)).toBe(0);
    expect(settleSnap(0.75, 0, snaps)).toBe(0.9);
    expect(settleSnap(0.65, 0, snaps)).toBe(0.5);
    // A flick carries it: up from the half snap to the full one, down from the half one to closed.
    expect(settleSnap(0.5, 2, snaps)).toBe(0.9);
    expect(settleSnap(0.5, -2, snaps)).toBe(0);
    expect(settleSnap(0.9, -2, snaps)).toBe(0.5);
  });

  it('a sheet sized to its content has one snap: back up over half its height, closed under it', () => {
    expect(settleSnap(0.6, 0, [1])).toBe(1);
    expect(settleSnap(0.4, 0, [1])).toBe(0);
    expect(settleSnap(0.8, -3, [1])).toBe(0);
  });
});

describe('Sheet', () => {
  it('opening is a snap («HÁPTICO · LEVE»), unless the opening belongs to another choreography', async () => {
    const view = await renderApp(
      <Sheet label="Prueba" onClose={() => undefined}>
        <T>Hola</T>
      </Sheet>,
    );
    expect(Haptics.impactAsync).toHaveBeenCalledWith('light');
    await view.unmount();
    jest.mocked(Haptics.impactAsync).mockClear();
    await renderApp(
      <Sheet label="Prueba" onClose={() => undefined} openHaptic={false}>
        <T>Hola</T>
      </Sheet>,
    );
    expect(Haptics.impactAsync).not.toHaveBeenCalled();
  });

  it('a flick down on the handle closes it; a short drag goes back up', async () => {
    const onClose = jest.fn();
    await renderApp(
      <Sheet label="Prueba" onClose={onClose}>
        <T>Hola</T>
      </Sheet>,
    );
    await letItOpen();
    await act(async () =>
      fireGestureHandler(getByGestureTestId('sheet-drag'), [
        { state: State.BEGAN, translationY: 0 },
        { state: State.ACTIVE, translationY: 0 },
        { state: State.ACTIVE, translationY: 40 },
        { state: State.END, translationY: 40, velocityY: 0 },
      ]),
    );
    expect(onClose).not.toHaveBeenCalled();
    await act(async () =>
      fireGestureHandler(getByGestureTestId('sheet-drag'), [
        { state: State.BEGAN, translationY: 0 },
        { state: State.ACTIVE, translationY: 0 },
        { state: State.ACTIVE, translationY: 300 },
        { state: State.END, translationY: 300, velocityY: 6000 },
      ]),
    );
    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));
  });

  it('a drag that wants to close asks first', async () => {
    const onClose = jest.fn();
    const canClose = jest.fn(() => false);
    await renderApp(
      <Sheet label="Prueba" onClose={onClose} canClose={canClose}>
        <T>Hola</T>
      </Sheet>,
    );
    await act(async () =>
      fireGestureHandler(getByGestureTestId('sheet-drag'), [
        { state: State.BEGAN, translationY: 0 },
        { state: State.ACTIVE, translationY: 0 },
        { state: State.ACTIVE, translationY: 300 },
        { state: State.END, translationY: 300, velocityY: 6000 },
      ]),
    );
    await waitFor(() => expect(canClose).toHaveBeenCalled());
    expect(onClose).not.toHaveBeenCalled();
  });

  it('the backdrop closes it, sliding away on FIRM', async () => {
    const onClose = jest.fn();
    await renderApp(
      <Sheet label="Prueba" onClose={onClose}>
        <T>Hola</T>
      </Sheet>,
    );
    await fireEvent.press(screen.getByLabelText('Cerrar'));
    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));
  });
});

describe('SnapSheet', () => {
  it('keeps its scroll viewport above the bottom bar at half and full height', async () => {
    await renderApp(
      <SnapSheet testID="panel" label="Mesa editorial" availableHeight={800} bottom={100} onClose={() => undefined}>
        <T>Editor visual</T>
      </SnapSheet>,
    );
    await letItOpen();
    const panel = screen.getByTestId('panel');
    const handle = screen.getByLabelText('Altura del panel');
    await waitFor(() => expect(panel).toHaveAnimatedStyle({ bottom: 100, height: 350 }), { timeout: 2000 });
    await fireEvent(handle, 'accessibilityAction', { nativeEvent: { actionName: 'increment' } });
    await waitFor(() => expect(panel).toHaveAnimatedStyle({ bottom: 100, height: 630 }), { timeout: 2000 });
    await fireEvent(handle, 'accessibilityAction', { nativeEvent: { actionName: 'decrement' } });
    await waitFor(() => expect(panel).toHaveAnimatedStyle({ bottom: 100, height: 350 }), { timeout: 2000 });
  });

  it('opens at the half snap with a haptic, and a flick up takes it to the full snap with another', async () => {
    await renderApp(
      <SnapSheet label="Mesa editorial" bottom={0} onClose={() => undefined}>
        <T>Equipo</T>
      </SnapSheet>,
    );
    expect(Haptics.impactAsync).toHaveBeenCalledTimes(1);
    await letItOpen();
    await act(async () =>
      fireGestureHandler(getByGestureTestId('snap-sheet-drag'), [
        { state: State.BEGAN, translationY: 0 },
        { state: State.ACTIVE, translationY: 0 },
        { state: State.ACTIVE, translationY: -200 },
        { state: State.END, translationY: -200, velocityY: -6000 },
      ]),
    );
    await waitFor(() => expect(Haptics.impactAsync).toHaveBeenCalledTimes(2));
    expect(Haptics.impactAsync).toHaveBeenLastCalledWith('light');
  });

  it('a flick down closes it', async () => {
    const onClose = jest.fn();
    await renderApp(
      <SnapSheet label="Mesa editorial" bottom={0} onClose={onClose}>
        <T>Equipo</T>
      </SnapSheet>,
    );
    await act(async () =>
      fireGestureHandler(getByGestureTestId('snap-sheet-drag'), [
        { state: State.BEGAN, translationY: 0 },
        { state: State.ACTIVE, translationY: 0 },
        { state: State.ACTIVE, translationY: 300 },
        { state: State.END, translationY: 300, velocityY: 6000 },
      ]),
    );
    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));
  });

  // BackHandler listeners are global: the Oficina's panel left open under another tab used to swallow Android back
  // there (back from the Calendario opened by «Ver en el Calendario» closed the hidden panel and stayed put).
  it('takes Android back only while its screen is shown (backCloses), and tells the snap it rests on', async () => {
    const listen = jest.spyOn(BackHandler, 'addEventListener');
    const onRest = jest.fn();
    await renderApp(
      <SnapSheet label="Mesa editorial" bottom={0} onClose={() => undefined} onRest={onRest} backCloses={false}>
        <T>Equipo</T>
      </SnapSheet>,
    );
    expect(listen).not.toHaveBeenCalled();
    expect(onRest).toHaveBeenLastCalledWith(sheetMotion.snaps[0]);
    await renderApp(
      <SnapSheet label="Mesa editorial" bottom={0} onClose={() => undefined}>
        <T>Equipo</T>
      </SnapSheet>,
    );
    expect(listen).toHaveBeenCalledWith('hardwareBackPress', expect.any(Function));
  });
});

describe('MovMicro', () => {
  it('uses the board values: press 0.97 on k 900 / c 60 and back on FIRM, the switch on FIRM, «Copiado» 1.5 s, loading 55–100 % every 1.2 s', () => {
    expect(microMotion.pressDown).toEqual({ damping: 60, stiffness: 900, mass: 1 });
    expect(microMotion.pressedScale).toBe(0.97);
    expect(microMotion.pressUp).toBe(FIRM);
    expect(microMotion.switchKnob).toBe(FIRM);
    expect(copiedLabelMs).toBe(1500);
    expect(microMotion).toMatchObject({ skeletonPeriodMs: 1200, skeletonLow: 0.55, skeletonLag: 0.4, skeletonStill: 0.7, chipCheckShift: 6, toastRise: 12 });
  });

  it('a chip toggles with a selection haptic', async () => {
    const onPress = jest.fn();
    await renderApp(
      <FilterChip pressed={false} onPress={onPress}>
        Comprador
      </FilterChip>,
    );
    await fireEvent.press(screen.getByText('Comprador'));
    expect(onPress).toHaveBeenCalled();
    expect(Haptics.selectionAsync).toHaveBeenCalled();
    expect(screen.getByRole('button', { name: 'Comprador' })).not.toBeSelected();
  });

  it('a switch row flips with a selection haptic', async () => {
    const onChange = jest.fn();
    await renderApp(<SwitchRow label="El equipo puede editar mis fotos con IA" value={false} onChange={onChange} />);
    await fireEvent.press(screen.getByRole('switch', { name: 'El equipo puede editar mis fotos con IA' }));
    expect(onChange).toHaveBeenCalledWith(true);
    expect(Haptics.selectionAsync).toHaveBeenCalled();
  });

  it('«Copiar» says «Copiado» with the success haptic, then «Copiar» again', async () => {
    await renderApp(<CopyButton text="Hola" testID="copiar" />);
    await fireEvent.press(screen.getByText('Copiar'));
    expect(Clipboard.setStringAsync).toHaveBeenCalledWith('Hola');
    expect(await screen.findByText('Copiado')).toBeOnTheScreen();
    expect(Haptics.notificationAsync).toHaveBeenCalledWith('success');
    expect(await screen.findByText('Copiar', {}, { timeout: copiedLabelMs + 2000 })).toBeOnTheScreen();
  });

  it('a focused field turns its label 0ff1ce-hondo', async () => {
    await renderApp(<Field label="Nota para el equipo" testID="nota" />);
    await fireEvent(screen.getByTestId('nota'), 'focus');
    await waitFor(() => expect(screen.getByText('Nota para el equipo')).toHaveStyle({ color: colors.brandDeep }));
    await fireEvent(screen.getByTestId('nota'), 'blur');
    await waitFor(() => expect(screen.getByText('Nota para el equipo')).toHaveStyle({ color: colors.ink }));
  });
});
