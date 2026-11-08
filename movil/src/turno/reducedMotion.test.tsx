// MovTuTurno with «menos movimiento»: every step happens at once. The card leaves as soon as the
// backend confirms (no check, no hold, no slide), the counters change and an empty label goes in the
// same moment, «Pospuestas» counts without flashing. The haptics stay.
import { CONVERSATION_CARD, questionCard, turnoFixture } from '@compartido/fixtures/turno';
import type { TuTurno } from '@compartido/api/types';
import { act, fireEvent, screen } from '@testing-library/react-native';
import * as Haptics from 'expo-haptics';
import { getAnimatedStyle } from 'react-native-reanimated';
import '@/api/transport';
import { renderApp } from '@/test/render';
import { fakeServer } from '@/test/server';
import { turnoMotion } from '@/theme/motion';
import { TuTurnoScreen } from './TuTurnoScreen';

jest.mock('@/theme/motion', () => ({ ...jest.requireActual('@/theme/motion'), useMotion: () => ({ reduced: true }) }));

const before = (): TuTurno => turnoFixture({ count: 2, items: [CONVERSATION_CARD, questionCard()] });

function serve(after: TuTurno, post: string, reply: unknown = {}) {
  let done = false;
  return fakeServer({
    'GET /api/v1/tu-turno': () => ({ body: done ? after : before() }),
    'POST /api/v1/tu-turno/vistos': { body: { count: 1 } },
    [`POST ${post}`]: () => {
      done = true;
      return { body: reply };
    },
  });
}

describe('Tu turno · reduced motion (MovTuTurno «menos movimiento»)', () => {
  it('a resolved card leaves at once, with its counters and its empty label', async () => {
    serve(turnoFixture({ count: 1, items: [questionCard()] }), '/api/v1/conversaciones/conv-1/cerrar');
    await renderApp(<TuTurnoScreen />);
    await fireEvent.press(await screen.findByText('Hecho, respondí'));
    expect(await screen.findByText('Anotado: respondiste')).toBeOnTheScreen();
    expect(Haptics.notificationAsync).toHaveBeenCalledWith('success');
    expect(screen.queryByTestId('turno-done')).toBeNull();
    expect(screen.queryByTestId(`turno-card-${CONVERSATION_CARD.id}`)).toBeNull();
    expect(screen.queryByRole('header', { name: /^Importante/ })).toBeNull();
    expect(screen.getByText('1 cuando puedas')).toBeOnTheScreen();
  });

  it('«Más tarde» sends the card to «Pospuestas» at once, without the flash', async () => {
    serve(
      turnoFixture({ count: 1, items: [CONVERSATION_CARD], later: [questionCard({}, { state: 'pospuesta' })] }),
      '/api/v1/preguntas/q1/mas-tarde',
      { id: 'q1', postponed_until: null },
    );
    await renderApp(<TuTurnoScreen />);
    await fireEvent.press(await screen.findByText('Más tarde'));
    expect(await screen.findByText('Pospuesta 3 días')).toBeOnTheScreen();
    expect(Haptics.impactAsync).toHaveBeenCalledWith('light');
    expect(screen.queryByTestId('turno-card-question:q1')).toBeNull();
    expect(screen.getByTestId('pospuestas')).toHaveAccessibleName('Pospuestas · 1');
    const glow = () => (getAnimatedStyle(screen.getByTestId('pospuestas-row')) as { backgroundColor?: string }).backgroundColor;
    const start = glow();
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, turnoMotion.postponedFlashMs / 2));
    });
    expect(glow()).toEqual(start);
  });
});
