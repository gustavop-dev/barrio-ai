// MovTuTurno in the app: a card resolved with its button shows the check (ÉXITO), holds it, collapses,
// and only then do its group counter, the summary and the top bar badge change; an empty group label
// goes last. «Más tarde» (LEVE) slides the card away before the gap closes and «Pospuestas» counts it
// and flashes. A swiped card skips the check and goes through the same gap and counters.
import { CONVERSATION_CARD, questionCard, turnoFixture } from '@compartido/fixtures/turno';
import type { TuTurno } from '@compartido/api/types';
import { act, fireEvent, screen, within } from '@testing-library/react-native';
import * as Haptics from 'expo-haptics';
import { State } from 'react-native-gesture-handler';
import { fireGestureHandler, getByGestureTestId } from 'react-native-gesture-handler/jest-utils';
import { getAnimatedStyle } from 'react-native-reanimated';
import '@/api/transport';
import { TopBar } from '@/components/shell/TopBar';
import { renderApp } from '@/test/render';
import { fakeServer } from '@/test/server';
import { turnoMotion, turnoTimings } from '@/theme/motion';
import { leadMs } from './exits';
import { TuTurnoScreen } from './TuTurnoScreen';

const CARD = `turno-card-${CONVERSATION_CARD.id}`;
const QUESTION = 'turno-card-question:q1';

const before = (): TuTurno => turnoFixture({ count: 2, items: [CONVERSATION_CARD, questionCard()] });

/** GET /tu-turno before and after the POST (the backend drops the card at once, before the POST resolves). */
function serve(after: TuTurno, post: string, reply: unknown = {}) {
  let done = false;
  return fakeServer({
    'GET /api/v1/tu-turno': () => ({ body: done ? after : before() }),
    'POST /api/v1/tu-turno/vistos': { body: { count: 1 } },
    'GET /api/v1/operador/overview': { body: { control: { paused: false }, accounts: [] } },
    [`POST ${post}`]: () => {
      done = true;
      return { body: reply };
    },
  });
}

const advance = async (ms: number) => {
  await act(async () => {
    jest.advanceTimersByTime(ms);
  });
};

const header = (name: string) => screen.queryByRole('header', { name });

beforeEach(() => jest.useFakeTimers());
afterEach(() => jest.useRealTimers());

describe('Tu turno · a card resolved with its button (MovTuTurno)', () => {
  it('shows the check, holds it, collapses, then the counters change and the empty label goes', async () => {
    serve(turnoFixture({ count: 1, items: [questionCard()] }), '/api/v1/conversaciones/conv-1/cerrar');
    await renderApp(<TuTurnoScreen />);
    await fireEvent.press(await screen.findByText('Hecho, respondí'));

    // The backend confirmed: ÉXITO, the button is a check and the card is still there, counted.
    const done = await screen.findByTestId('turno-done');
    expect(done).toHaveAccessibleName('Hecho, respondí');
    expect(Haptics.notificationAsync).toHaveBeenCalledWith('success');
    expect(screen.getByTestId(CARD)).toBeOnTheScreen();
    expect(header('Importante · 1')).toBeOnTheScreen();
    expect(screen.getByText('1 importante · 1 cuando puedas')).toBeOnTheScreen();

    // After the hold it collapses: it leaves the list, but still counts while the gap closes.
    await advance(turnoMotion.doneHoldMs);
    expect(screen.queryByTestId(CARD)).toBeNull();
    expect(header('Importante · 1')).toBeOnTheScreen();

    // Gone: the group counter rolls to 0 and the summary changes; the label is still there…
    await advance(turnoTimings.collapse.duration);
    expect(header('Importante · 0')).toBeOnTheScreen();
    expect(screen.getByText('1 cuando puedas')).toBeOnTheScreen();

    // …until it collapses labelDelayMs later.
    await advance(turnoMotion.labelDelayMs);
    expect(screen.queryByRole('header', { name: /^Importante/ })).toBeNull();
    expect(header('Cuando puedas · 1')).toBeOnTheScreen();
  });

  it('keeps the top bar badge on the card until it has left, then rolls it and pops it back with SOFT', async () => {
    serve(turnoFixture({ count: 1, items: [questionCard()] }), '/api/v1/conversaciones/conv-1/cerrar');
    await renderApp(
      <>
        <TopBar />
        <TuTurnoScreen />
      </>,
    );
    await fireEvent.press(await screen.findByText('Hecho, respondí'));
    await screen.findByTestId('turno-done');
    // GET /tu-turno already says 1, but the card is still on the list.
    expect(screen.getByTestId('turn-counter')).toHaveTextContent('2');
    expect(screen.getByLabelText('Tu turno, 2 pendientes')).toBeOnTheScreen();

    await advance(turnoMotion.doneHoldMs + turnoTimings.collapse.duration);
    const counter = screen.getByTestId('turn-counter');
    expect(counter).toHaveTextContent('1');
    expect(screen.getByLabelText('Tu turno, 1 pendiente')).toBeOnTheScreen();
    const scale = () => (getAnimatedStyle(screen.getByTestId('turn-counter')) as { transform?: { scale: number }[] }).transform?.[0]?.scale ?? 1;
    await advance(16);
    expect(scale()).toBeGreaterThan(1);
    expect(scale()).toBeLessThanOrEqual(turnoMotion.badgePop);
    await advance(1500);
    expect(scale()).toBeCloseTo(1, 2);
  });

  it('a card the backend still lists after the POST stays (no exit)', async () => {
    const server = fakeServer({
      'GET /api/v1/tu-turno': { body: before() },
      'POST /api/v1/tu-turno/vistos': { body: { count: 1 } },
      'POST /api/v1/conversaciones/conv-1/cerrar': { body: {} },
    });
    await renderApp(<TuTurnoScreen />);
    await fireEvent.press(await screen.findByText('Hecho, respondí'));
    expect(await screen.findByText('Anotado: respondiste')).toBeOnTheScreen();
    expect(server.find('POST', '/api/v1/conversaciones/conv-1/cerrar')).toHaveLength(1);
    await advance(turnoMotion.doneHoldMs + turnoTimings.collapse.duration + turnoMotion.labelDelayMs);
    expect(screen.queryByTestId('turno-done')).toBeNull();
    expect(screen.getByTestId(CARD)).toBeOnTheScreen();
    expect(header('Importante · 1')).toBeOnTheScreen();
  });
});

describe('Tu turno · «Más tarde» (MovTuTurno)', () => {
  const postponed = () =>
    turnoFixture({ count: 1, items: [CONVERSATION_CARD], later: [questionCard({ postponed_until: '2026-11-10T09:00:00-05:00' }, { state: 'pospuesta' })] });

  it('slides the card away (LEVE), closes the gap, then «Pospuestas» counts it and flashes', async () => {
    serve(postponed(), '/api/v1/preguntas/q1/mas-tarde', { id: 'q1', postponed_until: '2026-11-10T09:00:00-05:00' });
    await renderApp(<TuTurnoScreen />);
    expect(await screen.findByText('Más tarde')).toBeOnTheScreen();
    expect(screen.queryByTestId('pospuestas')).toBeNull();
    await fireEvent.press(screen.getByText('Más tarde'));

    expect(await screen.findByText(/^Pospuesta\. Vuelve el /)).toBeOnTheScreen();
    expect(Haptics.impactAsync).toHaveBeenCalledWith('light');
    // Sliding: still on the list, no check.
    expect(screen.getByTestId(QUESTION)).toBeOnTheScreen();
    expect(screen.queryByTestId('answer-done-q1')).toBeNull();

    await advance(turnoTimings.laterSlide.duration);
    expect(screen.queryByTestId(QUESTION)).toBeNull();
    expect(screen.queryByTestId('pospuestas')).toBeNull();

    await advance(turnoTimings.collapse.duration);
    expect(screen.getByTestId('pospuestas')).toHaveAccessibleName('Pospuestas · 1');
    expect(header('Cuando puedas · 0')).toBeOnTheScreen();
    const glow = () => (getAnimatedStyle(screen.getByTestId('pospuestas-row')) as { backgroundColor?: string }).backgroundColor;
    const start = glow();
    await advance(turnoMotion.postponedFlashMs / 2);
    expect(glow()).not.toEqual(start);

    await advance(turnoMotion.labelDelayMs);
    expect(screen.queryByRole('header', { name: /^Cuando puedas/ })).toBeNull();
  });

  it('a question answered with «Responder» shows the check in place of the button', async () => {
    serve(turnoFixture({ count: 1, items: [CONVERSATION_CARD] }), '/api/v1/preguntas/q1/responder', { id: 'q1', state: 'answered' });
    await renderApp(<TuTurnoScreen />);
    await fireEvent.press(await screen.findByText('Sí'));
    await fireEvent.press(screen.getByTestId('answer-submit-q1'));
    expect(await screen.findByTestId('answer-done-q1')).toHaveAccessibleName('Responder');
    expect(screen.queryByTestId('answer-submit-q1')).toBeNull();
    await advance(leadMs({ kind: 'done', lead: 'check' }) + turnoTimings.collapse.duration);
    expect(screen.queryByTestId(QUESTION)).toBeNull();
  });
});

describe('Tu turno · swiped cards go through the same gap (MovTuTurno)', () => {
  function swipe(testID: string, translationX: number) {
    fireGestureHandler(getByGestureTestId(`${testID}-swipe`), [
      { state: State.BEGAN, translationX: 0 },
      { state: State.ACTIVE, translationX: translationX / 2, velocityX: 0 },
      { state: State.ACTIVE, translationX, velocityX: 0 },
      { state: State.END, translationX, velocityX: 0 },
    ]);
  }

  it('a swipe right skips the check, holds the one underneath, then collapses and counts down', async () => {
    serve(turnoFixture({ count: 1, items: [questionCard()] }), '/api/v1/conversaciones/conv-1/cerrar');
    await renderApp(<TuTurnoScreen />);
    await screen.findByText('Hecho, respondí');
    await act(async () => swipe(CARD, 320));
    expect(await screen.findByText('Anotado: respondiste')).toBeOnTheScreen();
    expect(screen.queryByTestId('turno-done')).toBeNull();
    expect(screen.getByTestId(CARD)).toBeOnTheScreen();

    await advance(leadMs({ kind: 'done', lead: 'flown' }));
    expect(screen.queryByTestId(CARD)).toBeNull();
    await advance(turnoTimings.collapse.duration);
    expect(header('Importante · 0')).toBeOnTheScreen();
  });

  it('a swipe left closes the gap at once (it already flew off) and «Pospuestas» counts it', async () => {
    serve(
      turnoFixture({ count: 1, items: [CONVERSATION_CARD], later: [questionCard({}, { state: 'pospuesta' })] }),
      '/api/v1/preguntas/q1/mas-tarde',
      { id: 'q1', postponed_until: null },
    );
    await renderApp(<TuTurnoScreen />);
    await screen.findByText('Más tarde');
    await act(async () => swipe(QUESTION, -320));
    expect(await screen.findByText('Pospuesta 3 días')).toBeOnTheScreen();
    expect(screen.queryByTestId(QUESTION)).toBeNull();
    expect(Haptics.impactAsync).toHaveBeenCalledWith('light');
    await advance(turnoTimings.collapse.duration);
    expect(within(screen.getByTestId('pospuestas')).getByText('1')).toBeOnTheScreen();
  });
});
