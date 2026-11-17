// A button's text is drawn whatever its children compile to: one string, a string with an interpolated value
// (`Descargar {name}` is an array of strings) or a number. Drawn outside a <Text>, that array showed as a blank
// button in the release build (Personas › Referentes, «Gestionar protección de …»). Elements are rendered as given.
import { fireEvent, screen } from '@testing-library/react-native';
import { renderApp } from '@/test/render';
import { Button } from './Button';
import { T } from './Text';

describe('Button', () => {
  it('draws an interpolated label as text and names the button with it', async () => {
    const name = 'Inés Ejemplo';
    const onPress = jest.fn();
    await renderApp(<Button onPress={onPress}>Gestionar protección de {name}</Button>);
    expect(screen.getByText('Gestionar protección de Inés Ejemplo')).toBeOnTheScreen();
    await fireEvent.press(screen.getByRole('button', { name: 'Gestionar protección de Inés Ejemplo' }));
    expect(onPress).toHaveBeenCalledTimes(1);
  });

  it('skips empty parts, keeps numbers and an explicit accessibility label', async () => {
    await renderApp(
      <>
        <Button>
          Paso {2}
          {false}
          {null}
        </Button>
        <Button accessibilityLabel="Quitar a Inés">Quitar</Button>
      </>,
    );
    expect(screen.getByRole('button', { name: 'Paso 2' })).toBeOnTheScreen();
    expect(screen.getByRole('button', { name: 'Quitar a Inés' })).toBeOnTheScreen();
  });

  it('renders element children as given and shows the loading label while busy', async () => {
    await renderApp(
      <>
        <Button>
          <T>Hecho a medida</T>
        </Button>
        <Button loading loadingLabel="Guardando…">
          Guardar {'decisión'}
        </Button>
      </>,
    );
    expect(screen.getByText('Hecho a medida')).toBeOnTheScreen();
    expect(screen.getByRole('button', { name: 'Guardando…' })).toBeOnTheScreen();
    expect(screen.queryByText('Guardar decisión')).toBeNull();
  });
});
