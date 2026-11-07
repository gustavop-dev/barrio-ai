// The opportunity drag: the stage under the finger and the scroll near the edges.
import { autoScrollDelta, stageAt } from './drag';

const zones = [
  { stage: 'necesidad', top: 200, bottom: 440 },
  { stage: 'conversacion', top: 464, bottom: 704 },
];

describe('opportunity drag', () => {
  it('finds the stage under the finger, with the gap between groups going to the closest', () => {
    expect(stageAt(zones, 300, 12)).toBe('necesidad');
    expect(stageAt(zones, 450, 12)).toBe('necesidad');
    expect(stageAt(zones, 458, 12)).toBe('conversacion');
    expect(stageAt(zones, 100, 12)).toBe('');
  });

  it('scrolls up near the top edge and down near the bottom one', () => {
    expect(autoScrollDelta(110, 100, 600, 80, 700, 16)).toBeCloseTo(-11.2);
    expect(autoScrollDelta(650, 100, 600, 80, 700, 16)).toBeCloseTo(11.2);
    expect(autoScrollDelta(400, 100, 600, 80, 700, 16)).toBe(0);
    expect(autoScrollDelta(400, 100, 0, 80, 700, 16)).toBe(0);
  });
});
