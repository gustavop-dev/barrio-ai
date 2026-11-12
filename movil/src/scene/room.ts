// Cached once per atlas: the still room (the office and the game room), the shared art that the PWA also draws.
import { ClipOp, FilterMode, MipmapMode, Skia, type SkImage } from '@shopify/react-native-skia';
import { ATLAS } from '@compartido/scene/atlas';
import { paintRoom } from '@compartido/scene/art';
import { PLAN_WIDTH, PLAN_HEIGHT } from '@compartido/scene/plan';
export function roomPicture(atlas: SkImage) {
  const recorder = Skia.PictureRecorder();
  const ctx = recorder.beginRecording(Skia.XYWHRect(0, 0, PLAN_WIDTH, PLAN_HEIGHT));
  const paint = Skia.Paint();
  paint.setAntiAlias(false);
  const rect = (x: number, y: number, w: number, h: number, color: string, alpha = 1) => {
    paint.setColor(Skia.Color(color));
    paint.setAlphaf(alpha);
    ctx.drawRect(Skia.XYWHRect(x, y, w, h), paint);
  };
  const sprite = (name: string, x: number, y: number) => {
    const r = ATLAS[name];
    if (r) ctx.drawImageRectOptions(atlas, Skia.XYWHRect(...r), Skia.XYWHRect(Math.round(x), Math.round(y), r[2], r[3]), FilterMode.Nearest, MipmapMode.None);
  };
  const clip = (x: number, y: number, w: number, h: number, draw: () => void) => {
    ctx.save();
    ctx.clipRect(Skia.XYWHRect(x, y, w, h), ClipOp.Intersect, false);
    draw();
    ctx.restore();
  };
  const tile = (name: string, x: number, y: number, w: number, h: number) => {
    const r = ATLAS[name];
    if (!r) return;
    clip(x, y, w, h, () => {
      for (let yy = y; yy < y + h; yy += r[3]) for (let xx = x; xx < x + w; xx += r[2]) sprite(name, xx, yy);
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
        ctx.drawImageRectOptions(atlas, Skia.XYWHRect(sx + px, sy + py, pw, ph), Skia.XYWHRect(dx, dy, dw, dh), FilterMode.Nearest, MipmapMode.None);
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
  paintRoom({ rect, sprite, tile, rug });
  return recorder.finishRecordingAsPicture();
}
