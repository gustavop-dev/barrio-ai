// Draws the apartment with the licensed LimeZu sprites. Ported from the previous
// office (apartamento-agentes/public/scene.js), keeping layout, art and order.

import { ROLES, ROLE_BY_ID, TEAMS, type RoleId, type TeamId } from './roles';
import type { Actor, StatusMap } from './simulation';

export const SCENE_WIDTH = 480;
export const SCENE_HEIGHT = 330;
export const SCENE_SCALE = 2;

type ImageLike = CanvasImageSource & { width: number; height: number };

export interface DrawState {
  actors: readonly Actor[];
  statuses: StatusMap;
  selectedTeam: TeamId | null;
  selectedRole: RoleId | null;
  evening: boolean;
  /** Ambient clock in ms; advances only while motion is enabled. */
  elapsed: number;
  moving: boolean;
}

const WINDOWS_X = [65, 195, 282];
const NIGHT_LAMPS: readonly (readonly [number, number])[] = [
  [89, 103], [150, 103], [245, 103], [306, 103], [404, 230], [332, 250], [402, 124],
];

export function drawScene(ctx: CanvasRenderingContext2D, images: Record<string, ImageLike> | null, state: DrawState): void {
  const { actors, statuses, selectedTeam, selectedRole, evening, elapsed, moving } = state;
  const ready = images !== null;

  ctx.save();
  ctx.setTransform(SCENE_SCALE, 0, 0, SCENE_SCALE, 0, 0);
  ctx.imageSmoothingEnabled = false;

  const fill = (x: number, y: number, w: number, h: number, color: string) => {
    ctx.fillStyle = color;
    ctx.fillRect(x, y, w, h);
  };
  const sprite = (name: string, x: number, y: number, w?: number, h?: number) => {
    const image = images?.[name];
    if (image) ctx.drawImage(image, Math.round(x), Math.round(y), w ?? image.width, h ?? image.height);
  };
  const tile = (name: string, x: number, y: number, w: number, h: number) => {
    const image = images?.[name];
    if (!image) return;
    ctx.save();
    ctx.beginPath();
    ctx.rect(x, y, w, h);
    ctx.clip();
    for (let yy = y; yy < y + h; yy += image.height) for (let xx = x; xx < x + w; xx += image.width) sprite(name, xx, yy);
    ctx.restore();
  };
  // A monitor shows work only while its owner is really working.
  const monitor = (x: number, y: number, w: number, h: number, kind: number, lit: boolean) => {
    sprite('monitorFront', x, y, w, h);
    if (!lit) {
      fill(x + 2, y + 2, w - 4, h - 7, '#33403f');
      fill(x + 3, y + 3, w - 6, 1, '#3f4e4c');
      fill(x + w - 4, y + h - 4, 1, 1, '#d9a35c');
      return;
    }
    fill(x + 2, y + 2, w - 4, h - 7, '#d8edf0');
    fill(x + 2, y + 2, w - 4, 2, '#427b97');
    fill(x + 3, y + 5, 4, h - 11, '#8bb9c6');
    if (kind === 1) {
      fill(x + 9, y + 10, 2, 3, '#719e87');
      fill(x + 12, y + 8, 2, 5, '#57968b');
      fill(x + 15, y + 6, 3, 7, '#427b97');
    } else {
      fill(x + 9, y + 5, 9, 2, '#78a9b7');
      fill(x + 9, y + 9, 7, 1, '#638b9d');
      fill(x + 9, y + 12, 9, 1, '#83b6ba');
      if (kind === 2) fill(x + 18, y + 9, 2, 3, '#79aa74');
    }
    fill(x + w - 4, y + h - 4, 1, 1, '#a9ebae');
  };

  fill(0, 0, SCENE_WIDTH, SCENE_HEIGHT, '#c4d1c4');
  // Soft exterior shadow and raised foundation.
  fill(24, 36, 438, 269, '#758d7c');
  fill(21, 32, 438, 269, '#92a591');
  fill(18, 25, 438, 270, '#4b5655');
  if (!ready) {
    fill(24, 52, 426, 235, '#d4c0a2');
    ctx.restore();
    return;
  }
  tile('floor', 24, 53, 426, 236);
  // Cream plaster wall, sage wainscot and oak skirting.
  fill(24, 28, 426, 27, '#eee5cc');
  fill(24, 46, 426, 10, '#9ba998');
  fill(24, 53, 426, 3, '#667b70');
  fill(24, 27, 426, 3, '#fff5dd');
  fill(18, 25, 6, 270, '#536b61');
  fill(21, 28, 3, 263, '#b9c5ae');
  fill(450, 25, 6, 270, '#536b61');
  fill(450, 29, 3, 261, '#b9c5ae');
  // Windows overlook a quiet canopy.
  for (const x of WINDOWS_X) {
    fill(x + 3, 30, 40, 18, evening ? '#5f7f95' : '#a0c9ca');
    fill(x + 3, 40, 40, 8, evening ? '#3f5a4c' : '#728f79');
    sprite('window', x, 26);
  }
  sprite('board', 133, 31, 30, 18);
  sprite('books', 248, 30);
  sprite('plantSmall', 37, 32);
  // Compact kitchen, separated only by its tiled floor.
  tile('tile', 352, 55, 98, 102);
  fill(350, 55, 2, 102, '#aa987f');
  for (let x = 357; x < 419; x += 31) sprite('cabinet', x, 64, 31, 25);
  sprite('sink', 357, 62, 29, 17);
  sprite('stove', 389, 59, 18, 29);
  sprite('fridge', 423, 52, 20, 40);
  sprite('wallCabinet', 361, 29, 27, 19);
  sprite('wallCabinet', 392, 29, 27, 19);
  sprite('coffee', 409, 68, 14, 16);
  sprite('desk', 370, 112, 60, 26);
  sprite('fruit', 390, 108, 13, 13);
  sprite('cup', 414, 114, 8, 8);
  // The two gold kitchen chairs are now Relations' seats; they are drawn with the other chairs below.
  // Rugs define the teams without dividing the room.
  sprite('rugGreen', 52, 87, 130, 68);
  sprite('rugBlue', 207, 87, 135, 68);
  sprite('rugRust', 48, 194, 130, 98);
  sprite('rugBlue', 211, 194, 132, 98);
  sprite('rugGreen', 370, 209, 72, 73);

  // Selected team's warm brass corner brackets.
  const team = TEAMS.find((t) => t.id === selectedTeam);
  if (team) {
    const [x, y, w, h] = team.box;
    ctx.strokeStyle = '#f8d47d';
    ctx.lineWidth = 1.5;
    const corners: [number, number, number, number][] = [
      [x - 3, y - 3, 1, 1], [x + w + 3, y - 3, -1, 1], [x - 3, y + h + 3, 1, -1], [x + w + 3, y + h + 3, -1, -1],
    ];
    for (const [xx, yy, dx, dy] of corners) {
      ctx.beginPath();
      ctx.moveTo(xx, yy + dy * 8);
      ctx.lineTo(xx, yy);
      ctx.lineTo(xx + dx * 8, yy);
      ctx.stroke();
    }
  }

  // Strategy and listening benches.
  for (const [x, y] of [[67, 93], [127, 93], [222, 93], [282, 93]] as const) {
    sprite('deskLight', x, y, 48, 29);
    sprite('cup', x + 36, y + 9, 6, 7);
  }
  for (const role of ROLES) {
    if (role.monitor) {
      const m = role.monitor;
      monitor(m.x, m.y, m.w, m.h, m.kind, statuses[role.id] === 'trabajando');
    }
  }
  // Low bookcases, pinboard and plants line the shared central passage.
  sprite('library', 198, 146, 64, 28);
  sprite('books', 269, 148, 32, 26);
  sprite('plantSmall', 319, 148);
  sprite('plant', 32, 137, 20, 32);
  // Editorial table: three people, room for notes.
  sprite('chair', 70, 223, 16, 24);
  sprite('chair', 135, 223, 16, 24);
  sprite('desk', 65, 231, 96, 32);
  sprite('laptop', 72, 232, 16, 16);
  sprite('laptop', 137, 232, 16, 16);
  sprite('book', 105, 237, 18, 14);
  sprite('cup', 122, 247, 7, 7);
  // The barrio is a living room: a long sofa and two easy chairs.
  sprite('sofa', 222, 205, 104, 35);
  sprite('roundChair', 229, 261, 24, 28);
  sprite('roundChair', 296, 261, 24, 28);
  sprite('coffeeTable', 251, 245, 45, 23);
  sprite('book', 262, 242, 14, 12);
  sprite('cup', 283, 246, 6, 7);
  sprite('lamp', 329, 237, 12, 32);
  // Quiet review desk; no enclosed office.
  sprite('deskLight', 380, 217, 52, 30);
  sprite('printer', 430, 270, 15, 15);
  sprite('plant', 350, 242, 20, 35);
  sprite('plant', 429, 176, 20, 35);
  sprite('plantSmall', 173, 267);
  sprite('palm', 30, 253, 21, 35);
  // Entry, communal project wall and coat-free circulation.
  sprite('door', 183, 29, 16, 28);
  sprite('map', 363, 172, 38, 25);
  sprite('board', 405, 170, 26, 20);
  // Operations: a low cabinet with the printer beside the entry.
  sprite('cabinet', 203, 72, 29, 14);
  sprite('printer', 210, 63, 15, 16);

  // Characters use the pack's frame animations.
  const person = (actor: Actor) => {
    const image = images?.[`person${actor.sprite}-${actor.action}`] ?? images?.[`person${actor.sprite}-idle_anim`];
    if (!image) return;
    const frameWidth = 16;
    const perDirection = 6;
    const reading = actor.action === 'reading' && Boolean(images?.[`person${actor.sprite}-reading`]);
    const direction = reading ? 2 : actor.direction % 4;
    const frame = moving && actor.animated ? Math.floor(elapsed / 210 + actor.index) % perDirection : 0;
    ctx.save();
    if (actor.dimmed) ctx.globalAlpha = 0.42;
    ctx.drawImage(
      image,
      (direction * perDirection + frame) * frameWidth, 0, frameWidth, 32,
      Math.round(actor.x - frameWidth / 2), Math.round(actor.y - 29), frameWidth, 32,
    );
    ctx.restore();
  };
  const chair = (id: RoleId) => {
    const role = ROLE_BY_ID[id];
    const [x, y] = role.home;
    if (role.chair === 'north') sprite('chairNorth', x - 11, y - 6, 22, 20);
    if (role.chair === 'gold') sprite('chairNorthGold', x - 10, y - 6, 20, 18);
  };

  // Empty chairs remain at the desks while their owners take a break.
  for (const actor of actors) if (actor.away) chair(actor.role);
  [...actors].sort((a, b) => a.y - b.y).forEach(person);
  for (const actor of actors) if (!actor.away) chair(actor.role);

  // A small green light above whoever is really working.
  for (const actor of actors) {
    if (actor.status !== 'trabajando' || actor.away) continue;
    const blink = moving && Math.floor(elapsed / 600 + actor.index) % 2 === 0;
    const x = Math.round(actor.x + 8);
    const y = Math.round(actor.y - 17);
    fill(x - 1, y - 1, 4, 4, '#2c4a3a');
    fill(x, y, 2, 2, blink ? '#c9f2a8' : '#79c46a');
  }

  for (const actor of actors.filter((a) => a.talking)) {
    const x = Math.round(actor.x);
    const y = Math.round(actor.y - 40);
    fill(x - 9, y, 19, 10, '#354c48');
    fill(x - 8, y + 1, 17, 8, '#fff4d6');
    fill(x - 2, y + 10, 3, 3, '#fff4d6');
    for (let d = 0; d < 3; d++) fill(x - 5 + d * 4, y + 4 - (moving && Math.floor(elapsed / 300) % 3 === d ? 1 : 0), 2, 2, '#64796c');
  }

  // Sunlight and subtle room depth, composited above the sprites.
  if (!evening) {
    ctx.fillStyle = 'rgba(255,240,184,.10)';
    for (const x of WINDOWS_X) {
      ctx.beginPath();
      ctx.moveTo(x, 56);
      ctx.lineTo(x + 45, 56);
      ctx.lineTo(x + 17, 148);
      ctx.lineTo(x - 27, 148);
      ctx.fill();
    }
  }
  fill(24, 56, 426, 4, '#3a41421b');
  fill(24, 56, 4, 233, '#3a414217');
  // Balcony garden.
  fill(171, 290, 167, 25, '#889b8c');
  tile('floor', 175, 292, 159, 19);
  fill(171, 312, 167, 3, '#475d56');
  for (let x = 175; x < 338; x += 12) fill(x, 306, 2, 8, '#536b61');
  sprite('plantSmall', 178, 284, 12, 22);
  sprite('plantSmall', 319, 284, 12, 22);
  fill(18, 289, 153, 6, '#526c61');
  fill(338, 289, 118, 6, '#526c61');
  fill(22, 289, 149, 2, '#c6ceae');
  fill(338, 289, 114, 2, '#c6ceae');

  if (evening) {
    fill(18, 25, 438, 270, '#17224446');
    ctx.globalCompositeOperation = 'screen';
    for (const [x, y] of NIGHT_LAMPS) {
      const glow = ctx.createRadialGradient(x, y, 0, x, y, 32);
      glow.addColorStop(0, '#ffc87540');
      glow.addColorStop(1, '#ffc87500');
      ctx.fillStyle = glow;
      ctx.fillRect(x - 32, y - 32, 64, 64);
    }
    ctx.globalCompositeOperation = 'source-over';
  }

  // «en diseño» tags under the faded characters, above the lighting so they stay legible.
  ctx.font = '600 5px system-ui, -apple-system, "Segoe UI", sans-serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  const placed: [number, number, number][] = [];
  for (const actor of [...actors].sort((a, b) => a.x - b.x)) {
    if (!actor.tag) continue;
    const width = Math.ceil(ctx.measureText(actor.tag).width) + 4;
    const x = Math.round(actor.x - width / 2);
    let y = Math.round(actor.y + 3);
    // Neighbours on the sofa sit closer than a tag is wide: stagger instead of overlapping.
    while (placed.some(([px, py, pw]) => x < px + pw + 2 && px < x + width + 2 && Math.abs(py - y) < 10)) y += 10;
    placed.push([x, y, width]);
    fill(x - 1, y - 1, width + 2, 9, '#354c48');
    fill(x, y, width, 7, '#efe7d2');
    ctx.fillStyle = '#4c5b55';
    ctx.fillText(actor.tag, actor.x, y + 3.8);
  }

  // Brass pointer over the selected character.
  const chosen = actors.find((a) => a.role === selectedRole);
  if (chosen) {
    const x = Math.round(chosen.x);
    const y = Math.round(chosen.y - 40 - (chosen.talking ? 12 : 0));
    ctx.fillStyle = '#354c48';
    ctx.beginPath();
    ctx.moveTo(x - 5, y - 1);
    ctx.lineTo(x + 5, y - 1);
    ctx.lineTo(x, y + 6);
    ctx.fill();
    ctx.fillStyle = '#f8d47d';
    ctx.beginPath();
    ctx.moveTo(x - 3, y);
    ctx.lineTo(x + 3, y);
    ctx.lineTo(x, y + 4);
    ctx.fill();
  }

  ctx.restore();
}
