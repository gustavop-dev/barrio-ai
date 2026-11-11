// Usage hints are temporary: they leave by themselves, a sideways swipe removes them for good (a SecureStore flag per
// hint) and a short drag springs back; the screen reader gets «Quitar el aviso».
import { fireEvent, screen, waitFor } from '@testing-library/react-native';
import * as SecureStore from 'expo-secure-store';
import { Text } from 'react-native';
import { State } from 'react-native-gesture-handler';
import { fireGestureHandler, getByGestureTestId } from 'react-native-gesture-handler/jest-utils';
import { renderApp } from '@/test/render';
import { DismissibleHint, resetHintsForTests } from './Hint';

const store = (SecureStore as unknown as { __store: Map<string, string> }).__store;
const KEY = 'oficina.aviso.prueba';

beforeEach(() => {
  resetHintsForTests();
  store.clear();
  jest.mocked(SecureStore.setItemAsync).mockClear();
  jest.mocked(SecureStore.getItemAsync).mockClear();
});

function swipe(translationX: number) {
  fireGestureHandler(getByGestureTestId('hint-swipe'), [
    { state: State.BEGAN, translationX: 0 },
    { state: State.ACTIVE, translationX: translationX / 2, velocityX: 0 },
    { state: State.ACTIVE, translationX, velocityX: 0 },
    { state: State.END, translationX, velocityX: 0 },
  ]);
}

const persisted = (visibleMs = 60_000) => (
  <DismissibleHint persistId="prueba" testID="hint" visibleMs={visibleMs}>
    <Text>Así se usa</Text>
  </DismissibleHint>
);

it('shows once its flag loads and leaves by itself, without counting as swiped', async () => {
  await renderApp(persisted(200));
  expect(await screen.findByText('Así se usa')).toBeOnTheScreen();
  await waitFor(() => expect(screen.queryByText('Así se usa')).toBeNull(), { timeout: 2000 });
  // It comes back on the next visit: only a swipe removes it for good.
  expect(store.has(KEY)).toBe(false);
});

it('a sideways swipe removes it for good; a short drag springs back', async () => {
  const view = await renderApp(persisted());
  await screen.findByText('Así se usa');
  swipe(40);
  expect(screen.getByText('Así se usa')).toBeOnTheScreen();
  expect(SecureStore.setItemAsync).not.toHaveBeenCalled();

  swipe(-220);
  await waitFor(() => expect(screen.queryByText('Así se usa')).toBeNull());
  expect(SecureStore.setItemAsync).toHaveBeenCalledWith(KEY, '1');

  // Next launch: the flag is read again from the keystore and the hint stays away.
  await view.unmount();
  resetHintsForTests();
  await renderApp(persisted());
  await waitFor(() => expect(SecureStore.getItemAsync).toHaveBeenCalledWith(KEY));
  await waitFor(() => expect(store.get(KEY)).toBe('1'));
  expect(screen.queryByText('Así se usa')).toBeNull();
});

it('the screen reader removes it with «Quitar el aviso», and a hint without its own flag tells its owner', async () => {
  const onDismiss = jest.fn();
  await renderApp(
    <DismissibleHint onDismiss={onDismiss} testID="hint">
      <Text>Pista</Text>
    </DismissibleHint>,
  );
  // Without a flag to read it shows at once (the capture button's hint: its owner keeps the first-use flag).
  expect(screen.getByText('Pista')).toBeOnTheScreen();
  await fireEvent(screen.getByTestId('hint'), 'accessibilityAction', { nativeEvent: { actionName: 'dismiss' } });
  expect(onDismiss).toHaveBeenCalledTimes(1);
  await waitFor(() => expect(screen.queryByText('Pista')).toBeNull());
  expect(SecureStore.setItemAsync).not.toHaveBeenCalled();
});
