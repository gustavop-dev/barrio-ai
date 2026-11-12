// The still marks recorded once: the selection pointer, the zone brackets and the capture envelope. The bubbles and
// the lights are the shared art, recorded each frame (Decorations.tsx).
import { Skia, type SkCanvas } from '@shopify/react-native-skia';
import { ROOM } from '@compartido/scene/art';
import { PLAN_HEIGHT, PLAN_WIDTH } from '@compartido/scene/plan';
import { officeMotion } from '@/theme/motion';
import { colors } from '@/theme/tokens';
const C = { tinta: colors.ink, ofc: colors.brand, postit: colors.postIt };
function pixels(ctx: SkCanvas) {
  const paint = Skia.Paint(); paint.setAntiAlias(false);
  return (x: number, y: number, w: number, h: number, color: string) => {
    paint.setColor(Skia.Color(color)); ctx.drawRect(Skia.XYWHRect(x, y, w, h), paint);
  };
}
export function pointerPicture() {
  const recorder = Skia.PictureRecorder();
  const R = pixels(recorder.beginRecording(Skia.XYWHRect(-4, 0, 9, 5)));
  R(-4, 0, 9, 1, C.tinta);
  R(-3, 1, 7, 1, C.tinta);
  R(-2, 2, 5, 1, C.tinta);
  R(-1, 3, 3, 1, C.tinta);
  R(0, 4, 1, 1, C.tinta);
  R(-3, 0, 7, 1, C.postit);
  R(-2, 1, 5, 1, C.postit);
  R(-1, 2, 3, 1, C.postit);
  R(0, 3, 1, 1, C.postit);
  return recorder.finishRecordingAsPicture();
}

export function zonePicture(box: readonly number[], length = officeMotion.bracketPx) {
  const recorder = Skia.PictureRecorder();
  const R = pixels(recorder.beginRecording(Skia.XYWHRect(0, 0, PLAN_WIDTH, PLAN_HEIGHT)));
  const x = box[0]! + 1;
  const y = box[1]! + 1;
  const w = box[2]! - 2;
  const h = box[3]! - 2;
  const L = length;
  for (const [cx, cy, dx, dy] of [[x, y, 1, 1], [x + w, y, -1, 1], [x, y + h, 1, -1], [x + w, y + h, -1, -1]] as const) {
    R(Math.min(cx, cx + dx * L), dy > 0 ? cy : cy - 2, L, 3, C.tinta);
    R(dx > 0 ? cx : cx - 2, Math.min(cy, cy + dy * L), 3, L, C.tinta);
    R(Math.min(cx, cx + dx * L) + (dx > 0 ? 1 : 0), dy > 0 ? cy + 1 : cy - 1, L - 1, 1, C.postit);
    R(dx > 0 ? cx + 1 : cx - 1, Math.min(cy, cy + dy * L) + (dy > 0 ? 1 : 0), 1, L - 1, C.postit);
  }
  return recorder.finishRecordingAsPicture();
}

/** MovOficina's 11×8 envelope, recorded once; only its integer position changes on UI. */
export function mailPicture() {
  const recorder = Skia.PictureRecorder();
  const R = pixels(recorder.beginRecording(Skia.XYWHRect(-5, -4, 11, 8)));
  const x = -5, y = -4;
  R(x, y, 11, 8, C.tinta); R(x + 1, y + 1, 9, 6, ROOM.white);
  R(x + 1, y + 1, 1, 1, C.tinta); R(x + 2, y + 2, 1, 1, C.tinta);
  R(x + 3, y + 3, 1, 1, C.tinta); R(x + 4, y + 4, 3, 1, C.tinta);
  R(x + 7, y + 3, 1, 1, C.tinta); R(x + 8, y + 2, 1, 1, C.tinta);
  R(x + 9, y + 1, 1, 1, C.tinta); R(x + 4, y + 5, 3, 1, C.ofc);
  return recorder.finishRecordingAsPicture();
}
