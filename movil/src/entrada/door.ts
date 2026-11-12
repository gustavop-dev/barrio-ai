// The login picture and its door, in the picture's own pixels (assets/brand/login-oficina-tarde.png
// is 384 × 224 and its art is drawn at 2×). These are the artwork's coordinates from MovEntrada, not
// motion values: the timings are in theme/motion.ts (`entrada`).

export const DOOR = {
  /** The login picture. */
  picture: { width: 384, height: 224 },
  /** The zoom is centred on the top of the door (the board's `transform-origin: 192px 32px`). */
  zoomOrigin: { x: 192, y: 32 },
  /** The dark doorway seen when the leaf folds. Artwork colour, like the office palette. */
  hole: { x: 178, y: 6, width: 28, height: 48, color: '#12121b' },
  /** The door leaf: a tile of the sprite atlas drawn at 2×, hinged on its left edge. */
  leaf: { x: 176, y: 4, width: 32, height: 56, scale: 2, atlas: { x: 323, y: 1393 } },
  /** The sprite atlas (assets/brand/sprites-atlas.png). */
  atlas: { width: 512, height: 1500 },
} as const;
