// Coordinates in sprites-atlas.png (512×1500), from the design's atlas map. Each app serves the image
// itself (the PWA at /brand/sprites-atlas.png, the native app from its assets).
// Character sheets p0–p12 are the LimeZu people of the scene; p13 is the librarian (person9 recoloured).
import { ROLE_BY_ID, type RoleId } from './roles';

export const ATLAS_WIDTH = 512;
export const ATLAS_HEIGHT = 1500;

/** Top-left of each 16×32 portrait frame. */
const PORTRAIT: readonly (readonly [number, number])[] = [
  [289, 1320],
  [306, 1320],
  [323, 1320],
  [340, 1320],
  [357, 1320],
  [374, 1320],
  [391, 1320],
  [408, 1320],
  [425, 1320],
  [442, 1320],
  [459, 1320],
  [476, 1320],
  [493, 1320],
  [0, 1353],
];

/** y of each idle animation row (4 directions × 6 frames of 16×32). */
const IDLE_ROW: readonly number[] = [0, 99, 198, 297, 396, 495, 594, 693, 792, 891, 990, 1089, 1155, 1254];

/** The design crops 9 empty rows above the head: portraits are 16×20 logical pixels. */
export const PORTRAIT_CROP_TOP = 9;
export const PORTRAIT_W = 16;
export const PORTRAIT_H = 20;

export const LIBRARIAN_SPRITE = 13;
/** System notices use the account operator's portrait. */
export const FALLBACK_ROLE: RoleId = 'operador_cuenta';

export function spriteOfRole(role: string | null | undefined): number {
  if (role === 'bibliotecario') return LIBRARIAN_SPRITE;
  const known = role ? ROLE_BY_ID[role as RoleId] : undefined;
  return (known ?? ROLE_BY_ID[FALLBACK_ROLE]).sprite;
}

export function portraitOrigin(sprite: number): readonly [number, number] {
  return PORTRAIT[sprite] ?? PORTRAIT[LIBRARIAN_SPRITE]!;
}

export function idleRow(sprite: number): number {
  return IDLE_ROW[sprite] ?? IDLE_ROW[LIBRARIAN_SPRITE]!;
}
