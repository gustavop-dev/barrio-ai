// Platform-independent sprite rectangles; each renderer loads its own texture.
export type Rect = readonly [x: number, y: number, w: number, h: number];

export const ATLAS: Readonly<Record<string, Rect>> = {
  'p0-idle_anim': [0, 0, 384, 32], 'p0-run': [0, 33, 384, 32], 'p0-reading': [0, 66, 288, 32],
  'p1-idle_anim': [0, 99, 384, 32], 'p1-run': [0, 132, 384, 32], 'p1-reading': [0, 165, 288, 32],
  'p2-idle_anim': [0, 198, 384, 32], 'p2-run': [0, 231, 384, 32], 'p2-reading': [0, 264, 288, 32],
  'p3-idle_anim': [0, 297, 384, 32], 'p3-run': [0, 330, 384, 32], 'p3-reading': [0, 363, 288, 32],
  'p4-idle_anim': [0, 396, 384, 32], 'p4-run': [0, 429, 384, 32], 'p4-reading': [0, 462, 288, 32],
  'p5-idle_anim': [0, 495, 384, 32], 'p5-run': [0, 528, 384, 32], 'p5-reading': [0, 561, 288, 32],
  'p6-idle_anim': [0, 594, 384, 32], 'p6-run': [0, 627, 384, 32], 'p6-reading': [0, 660, 288, 32],
  'p7-idle_anim': [0, 693, 384, 32], 'p7-run': [0, 726, 384, 32], 'p7-reading': [0, 759, 288, 32],
  'p8-idle_anim': [0, 792, 384, 32], 'p8-run': [0, 825, 384, 32], 'p8-reading': [0, 858, 288, 32],
  'p9-idle_anim': [0, 891, 384, 32], 'p9-run': [0, 924, 384, 32], 'p9-reading': [0, 957, 288, 32],
  'p10-idle_anim': [0, 990, 384, 32], 'p10-run': [0, 1023, 384, 32], 'p10-reading': [0, 1056, 288, 32],
  'p11-idle_anim': [0, 1089, 384, 32], 'p11-run': [0, 1122, 384, 32],
  'p12-idle_anim': [0, 1155, 384, 32], 'p12-run': [0, 1188, 384, 32], 'p12-reading': [0, 1221, 288, 32],
  'p13-idle_anim': [0, 1254, 384, 32], 'p13-run': [0, 1287, 384, 32], 'p13-reading': [0, 1320, 288, 32],
  plant: [17, 1353, 23, 30], plantSmall: [41, 1353, 22, 30], coffeeTable: [64, 1353, 30, 18], lamp: [95, 1353, 15, 33],
  books: [111, 1353, 32, 33], library: [144, 1353, 32, 39], board: [177, 1353, 26, 13], map: [204, 1353, 32, 19],
  book: [237, 1353, 28, 35], fridge: [266, 1353, 16, 35], sink: [283, 1353, 24, 14], stove: [308, 1353, 16, 24],
  coffee: [325, 1353, 16, 16], cup: [342, 1353, 9, 15], cabinet: [352, 1353, 29, 14], wallCabinet: [382, 1353, 16, 10],
  fruit: [399, 1353, 14, 17], roundChair: [414, 1353, 14, 15], printer: [429, 1353, 15, 16], desk: [445, 1353, 32, 37],
  deskLight: [478, 1353, 32, 37], sofa: [0, 1393, 48, 26], chair: [49, 1393, 16, 26], window: [66, 1393, 44, 26],
  windowSmall: [111, 1393, 25, 15], rugRust: [137, 1393, 60, 40], rugBlue: [198, 1393, 60, 40], rugGreen: [259, 1393, 30, 46],
  table: [290, 1393, 32, 37], door: [323, 1393, 16, 28], palm: [340, 1393, 23, 31], floor: [364, 1393, 32, 32],
  tile: [397, 1393, 32, 32], laptop: [430, 1393, 16, 16], monitor: [447, 1393, 32, 32], chairBack: [480, 1393, 14, 22],
  chairNorth: [0, 1440, 22, 19], chairNorthGold: [23, 1440, 22, 19], monitorFront: [46, 1440, 29, 20],
  // The game room (Sala de juegos), appended by scripts/oficina/atlas_sala_de_juegos.py.
  tvConsole: [0, 1461, 60, 34], speaker: [61, 1461, 32, 37], cueRack: [94, 1461, 13, 33], arcades: [108, 1461, 33, 39],
  poolTable: [142, 1461, 48, 38], drums: [191, 1461, 43, 31], pouf: [235, 1461, 20, 24], mic: [256, 1461, 13, 27],
  guitar: [270, 1461, 15, 31], armchair: [286, 1461, 19, 27],
};

