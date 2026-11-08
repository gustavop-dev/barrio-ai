// MovDetalle: the geometry of the portrait and the name in flight, and the hand-off from a tapped row
// to the card (the header shows the name while the card loads).
import { screen } from '@testing-library/react-native';
import { Text } from 'react-native';
import '@/api/transport';
import { PersonaScreen } from '@/personas/PersonaScreen';
import { renderApp } from '@/test/render';
import { fakeServer } from '@/test/server';
import { navValues } from '@/theme/motion';
import { colors, type as typeScale } from '@/theme/tokens';
import { DetailScreen } from './DetailScreen';
import { beginFlight, cardLabel, ghostFrame, rectOf, relativeTo, rowLabel, takeFlight, useFlightName, type FlightEnd } from './flight';

const expoRouter = jest.requireMock('expo-router') as Record<string, unknown>;

const row: FlightEnd = { avatar: { x: 16, y: 300, width: 40, height: 40 }, label: rowLabel({ x: 68, y: 302, width: 200, height: 24 }) };
const card: FlightEnd = { avatar: { x: 16, y: 120, width: 48, height: 48 }, label: cardLabel({ x: 16, y: 176, width: 300, height: 40 }, typeScale.titulo, colors.brandDeep) };

describe('the flight (MovDetalle)', () => {
  it('starts on the row and lands on the card', () => {
    expect(ghostFrame(row, card, 0)).toEqual({ avatar: { x: 16, y: 300, size: 40 }, label: { x: 68, y: 302, scale: 1 } });
    const landed = ghostFrame(row, card, 1);
    expect(landed.avatar).toEqual({ x: 16, y: 120, size: 48 });
    expect(landed.label.scale).toBe(2);
    const half = ghostFrame(row, card, 0.5);
    expect(half.avatar.size).toBe(44);
    expect(half.label.x).toBe(42);
  });

  it('grows the name to the title size and centres it on the title line', () => {
    // 16/24 copy scaled ×2 is 48 high; the title line is 40: it starts 4 points higher.
    expect(cardLabel({ x: 16, y: 176, width: 300, height: 40 }, typeScale.titulo, colors.ink)).toEqual({ x: 16, y: 172, scale: 2, color: colors.ink });
  });

  it('measures views that can be measured, relative to another', () => {
    expect(rectOf({ getBoundingClientRect: () => ({ x: 400, y: 10, width: 40, height: 40 }) })).toEqual({ x: 400, y: 10, width: 40, height: 40 });
    expect(rectOf({ getBoundingClientRect: () => ({ x: 0, y: 0, width: 0, height: 0 }) })).toBeNull();
    expect(rectOf({})).toBeNull();
    expect(rectOf(null)).toBeNull();
    expect(relativeTo({ x: 400, y: 10, width: 40, height: 40 }, { x: 390, y: 0, width: 390, height: 844 })).toEqual({ x: 10, y: 10, width: 40, height: 40 });
  });

  it('staggers the rest of the card as the board', () => {
    expect([navValues.cardBlockRise, navValues.cardBlockDelayMs, navValues.cardBlockStepMs]).toEqual([8, 120, 30]);
  });
});

describe('from a row to the card', () => {
  const navigation = { getState: () => ({ index: 1, routes: [{ key: 'tabs' }, { key: 'detail' }] }) };
  const source = { key: 'c-1', name: 'Lucía Ficticia', initials: 'LF', avatar: row.avatar, label: { x: 68, y: 302, width: 200, height: 24 } };

  beforeEach(() => {
    expoRouter.useNavigation = () => navigation;
    expoRouter.useRoute = () => ({ key: 'detail', name: 'personas/[id]' });
    expoRouter.usePreventRemove = () => () => undefined;
  });

  function NameProbe({ id }: { id: string }) {
    return <Text testID="flight-name">{useFlightName(id) ?? '—'}</Text>;
  }

  it('the pushed screen takes the flight of the row that was tapped, once', async () => {
    fakeServer({});
    beginFlight(source);
    await renderApp(
      <DetailScreen back="Personas" fallback="/personas">
        <NameProbe id="c-1" />
      </DetailScreen>,
    );
    expect(screen.getByTestId('flight-name')).toHaveTextContent('Lucía Ficticia');
    expect(takeFlight()).toBeNull();
  });

  it('another person does not get it', async () => {
    fakeServer({});
    beginFlight(source);
    await renderApp(
      <DetailScreen back="Personas" fallback="/personas">
        <NameProbe id="c-2" />
      </DetailScreen>,
    );
    expect(screen.getByTestId('flight-name')).toHaveTextContent('—');
  });

  it('the card shows the header with the name while it loads', async () => {
    const api = fakeServer({});
    api.fetch.mockImplementation(() => new Promise(() => undefined));
    beginFlight(source);
    await renderApp(
      <DetailScreen back="Personas" fallback="/personas">
        <PersonaScreen contactId="c-1" />
      </DetailScreen>,
    );
    expect(screen.getByText('Lucía Ficticia')).toBeOnTheScreen();
    expect(screen.getByLabelText('Cargando la ficha…')).toBeOnTheScreen();
  });
});
