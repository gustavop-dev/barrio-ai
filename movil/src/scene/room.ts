// Cached once per atlas: floor, nine-slice rugs, walls and furniture, matching the PWA.
import { ClipOp, FilterMode, MipmapMode, Skia, type SkImage } from '@shopify/react-native-skia';
import { ATLAS } from '@compartido/scene/atlas';
import { PLAN_WIDTH, PLAN_HEIGHT } from '@compartido/scene/plan';
import { officeRoom as ROOM } from '@/theme/tokens';
export function roomPicture(atlas: SkImage) {
  const recorder = Skia.PictureRecorder();
  const ctx = recorder.beginRecording(Skia.XYWHRect(0, 0, PLAN_WIDTH, PLAN_HEIGHT));
  const paint = Skia.Paint();
  paint.setAntiAlias(false);
  const R = (x: number, y: number, w: number, h: number, color: string) => {
    paint.setColor(Skia.Color(color));
    ctx.drawRect(Skia.XYWHRect(x, y, w, h), paint);
  };

  R(0, 0, PLAN_WIDTH, PLAN_HEIGHT, ROOM.outside);
  const image = atlas;

  const S = (name: string, x: number, y: number) => {
    const r = ATLAS[name];
    if (r) ctx.drawImageRectOptions(image, Skia.XYWHRect(...r), Skia.XYWHRect(Math.round(x), Math.round(y), r[2], r[3]), FilterMode.Nearest, MipmapMode.None);
  };
  const clip = (x: number, y: number, w: number, h: number, paint: () => void) => {
    ctx.save();
    ctx.clipRect(Skia.XYWHRect(x, y, w, h), ClipOp.Intersect, false);
    paint();
    ctx.restore();
  };
  const tile = (name: string, x: number, y: number, w: number, h: number) => {
    const r = ATLAS[name];
    if (!r) return;
    clip(x, y, w, h, () => {
      for (let yy = y; yy < y + h; yy += r[3]) for (let xx = x; xx < x + w; xx += r[2]) S(name, xx, yy);
    });
  };
  // Rug in nine parts: fixed corners, repeated edges and centre, never scaled.
  const rug = (name: string, x: number, y: number, w: number, h: number, k: number) => {
    const r = ATLAS[name];
    if (!r) return;
    const [sx, sy, rw, rh] = r;
    const part = (px: number, py: number, pw: number, ph: number, dx: number, dy: number, dw: number, dh: number) =>
      clip(dx, dy, dw, dh, () => {
        // Edges and centre are one texel along the repeated axis. Nearest sampling
        // stretches that identical texel once instead of recording thousands of tiny draws.
        ctx.drawImageRectOptions(image, Skia.XYWHRect(sx + px, sy + py, pw, ph), Skia.XYWHRect(dx, dy, dw, dh), FilterMode.Nearest, MipmapMode.None);
      });
    const mw = rw - 2 * k;
    const mh = rh - 2 * k;
    part(0, 0, k, k, x, y, k, k);
    part(rw - k, 0, k, k, x + w - k, y, k, k);
    part(0, rh - k, k, k, x, y + h - k, k, k);
    part(rw - k, rh - k, k, k, x + w - k, y + h - k, k, k);
    part(k, 0, 1, k, x + k, y, w - 2 * k, k);
    part(k, rh - k, 1, k, x + k, y + h - k, w - 2 * k, k);
    part(0, k, k, 1, x, y + k, k, h - 2 * k);
    part(rw - k, k, k, 1, x + w - k, y + k, k, h - 2 * k);
    part(k + Math.floor(mw / 2), k + Math.floor(mh / 2), 1, 1, x + k, y + k, w - 2 * k, h - 2 * k);
  };
  // ---------------------------------------------------------------- room
  const W = PLAN_WIDTH;
  const H = PLAN_HEIGHT;
  tile('floor', 4, 30, 184, 302);
  tile('tile', 112, 30, 76, 76);
  R(110, 30, 2, 76, ROOM.kitchenEdge);
  R(0, 0, W, 22, ROOM.plaster);
  R(0, 0, W, 2, ROOM.plasterLight);
  R(0, 22, W, 6, ROOM.wainscot);
  R(0, 28, W, 2, ROOM.skirting);
  R(0, 0, 4, H, ROOM.wall);
  R(3, 2, 1, H - 4, ROOM.wallLight);
  R(188, 0, 4, H, ROOM.wall);
  R(188, 2, 1, H - 4, ROOM.wallLight);
  R(0, H - 4, W, 4, ROOM.base);
  rug('rugBlue', 6, 114, 72, 60, 8);
  rug('rugGreen', 114, 114, 72, 60, 6);
  rug('rugRust', 6, 184, 72, 68, 8);
  rug('rugGreen', 114, 184, 72, 64, 6);
  rug('rugBlue', 30, 260, 132, 72, 8);
  S('door', 88, 2);
  S('windowSmall', 52, 4);
  S('board', 160, 6);
  S('wallCabinet', 116, 8);
  S('wallCabinet', 134, 8);

  // ---------------------------------------------------------------- furniture behind the people
  S('library', 6, 22);
  S('books', 40, 28);
  S('plantSmall', 78, 30);
  S('cabinet', 113, 42);
  S('coffee', 120, 32);
  S('sink', 144, 40);
  S('stove', 152, 30);
  S('fridge', 171, 22);
  S('deskLight', 142, 58);
  S('fruit', 150, 62);
  S('cup', 168, 66);
  for (const [x, y] of [[8, 114], [44, 114], [116, 114], [152, 114]] as const) S('deskLight', x, y);
  S('chair', 18, 186);
  S('chair', 50, 186);
  S('desk', 10, 196);
  S('desk', 42, 196);
  S('laptop', 18, 210);
  S('laptop', 50, 210);
  S('cup', 66, 220);
  S('deskLight', 140, 188);
  S('plant', 114, 190);
  S('printer', 172, 226);
  S('sofa', 72, 262);
  S('lamp', 158, 266);
  S('palm', 8, 292);
  S('plant', 164, 298);
  S('roundChair', 45, 314);
  S('roundChair', 133, 314);
  S('coffeeTable', 81, 300);
  return recorder.finishRecordingAsPicture();
}
