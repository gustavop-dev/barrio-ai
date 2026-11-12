import { agree, isFeminineName } from './genero';

describe('label agreement with the person (backlog #18)', () => {
  it.each([
    ['Lucía Ficticia', true],
    ['María José Restrepo', true],
    ['Isabel Díaz', true],
    ['Dra. Pérez', true],
    ['  camila ortiz ', true],
    ['José María Gómez', false],
    ['Pedro Salazar', false],
    ['Luca Bianchi', false],
    ['Dr. Andrés Mejía', false],
    ['', false],
    [null, false],
  ])('reads «%s» as a woman: %s', (name, expected) => {
    expect(isFeminineName(name)).toBe(expected);
  });

  it('changes only the participles of the card', () => {
    expect(agree('Seguido', true)).toBe('Seguida');
    expect(agree('Descartado', true)).toBe('Descartada');
    expect(agree('Seguido', false)).toBe('Seguido');
    expect(agree('Te invitó', true)).toBe('Te invitó');
    expect(agree('En conversación', true)).toBe('En conversación');
  });
});
