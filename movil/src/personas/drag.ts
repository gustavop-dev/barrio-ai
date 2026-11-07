// Pure rules of the opportunity drag (Personas › Oportunidades), run on the UI thread while the finger moves:
// which stage group is under the finger, and how far the list scrolls near its edges.

/** A stage group of the list, in content coordinates of the scroll view. */
export interface DropZone {
  stage: string;
  top: number;
  bottom: number;
}

/** The stage under `y` (content coordinates); the gap between groups counts for the closest one. '' when none. */
export function stageAt(zones: readonly DropZone[], y: number, slack: number): string {
  'worklet';
  for (let index = 0; index < zones.length; index += 1) {
    const zone = zones[index]!;
    if (y >= zone.top - slack && y <= zone.bottom + slack) return zone.stage;
  }
  return '';
}

/** Points to scroll this frame: negative near the top edge, positive near the bottom, 0 elsewhere. */
export function autoScrollDelta(fingerY: number, top: number, height: number, edge: number, speed: number, frameMs: number): number {
  'worklet';
  if (height <= 0) return 0;
  const step = (speed * frameMs) / 1000;
  if (fingerY < top + edge) return -step;
  if (fingerY > top + height - edge) return step;
  return 0;
}
