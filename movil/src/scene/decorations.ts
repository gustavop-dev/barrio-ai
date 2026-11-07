import { Skia, type SkCanvas } from '@shopify/react-native-skia';
import type { BubbleIcon } from '@compartido/scene/model';
import { colors, officeRoom as ROOM } from '@/theme/tokens';
const C = { tinta: colors.ink, tintaSuave: colors.inkSoft, papel: colors.paper, ofc: colors.brand, hondo: colors.brandDeep, claro: colors.brandLight, postit: colors.postIt };
function pixels(ctx: SkCanvas) {
  const paint = Skia.Paint(); paint.setAntiAlias(false);
  return (x: number, y: number, w: number, h: number, color: string) => {
    paint.setColor(Skia.Color(color)); ctx.drawRect(Skia.XYWHRect(x, y, w, h), paint);
  };
}
export function bubblePicture(kind: BubbleIcon, frame = 0) {
  const recorder = Skia.PictureRecorder();
  const ctx = recorder.beginRecording(Skia.XYWHRect(-7, 0, 13, 12));
  const R = pixels(ctx);
  const still = false;
  const icon = (kind: BubbleIcon, x: number, y: number) => {
    const t = C.tinta;
    if (kind === 'libro') {
      R(x, y + 1, 7, 5, ROOM.book);
      R(x + 1, y + 2, 5, 3, C.papel);
      R(x + 3, y + 1, 1, 5, ROOM.bookSpine);
    } else if (kind === 'hoja') {
      R(x + 1, y, 5, 6, ROOM.white);
      R(x + 2, y + 2, 3, 1, C.tintaSuave);
      R(x + 2, y + 4, 3, 1, C.tintaSuave);
    } else if (kind === 'cafe') {
      R(x + 1, y + 2, 4, 4, ROOM.white);
      R(x + 5, y + 3, 1, 2, ROOM.white);
      R(x + 2, y + 3, 2, 1, ROOM.coffee);
      R(x + 2, y, 1, 1, ROOM.steam);
      R(x + 3, y + 1, 1, 1, ROOM.steam);
    } else if (kind === 'listo') {
      for (const [dx, dy] of [[5, 1], [4, 2], [3, 3], [2, 4], [1, 3], [0, 2], [2, 5]] as const) R(x + dx, y + dy, 1, 1, C.hondo);
    } else if (kind === 'pregunta') {
      R(x + 2, y, 3, 1, t);
      R(x + 5, y + 1, 1, 1, t);
      R(x + 4, y + 2, 1, 1, t);
      R(x + 3, y + 3, 1, 1, t);
      R(x + 3, y + 5, 1, 1, t);
    } else if (kind === 'busca') {
      R(x + 1, y, 3, 1, t);
      R(x, y + 1, 1, 2, t);
      R(x + 4, y + 1, 1, 2, t);
      R(x + 1, y + 3, 3, 1, t);
      R(x + 4, y + 4, 1, 1, t);
      R(x + 5, y + 5, 1, 1, t);
    } else {
      const f = frame % 3;
      for (let d = 0; d < 3; d++) R(x + d * 3, y + 3 - (f === d && !still ? 1 : 0), 1, 1, C.tintaSuave);
    }
  };
  const x = 0, y = 0;
    R(x - 7, y, 13, 10, C.tinta);
    R(x - 6, y + 1, 11, 8, ROOM.white);
    R(x - 1, y + 10, 3, 2, C.tinta);
    R(x, y + 9, 1, 2, ROOM.white);
  icon(kind, x - 3, y + 2);
  return recorder.finishRecordingAsPicture();
}
export function pointerPicture() {
  const recorder = Skia.PictureRecorder();
  const ctx = recorder.beginRecording(Skia.XYWHRect(-4, 0, 9, 5));
  const R = pixels(ctx); const x = 0, y = 0;
    R(x - 4, y, 9, 1, C.tinta);
    R(x - 3, y + 1, 7, 1, C.tinta);
    R(x - 2, y + 2, 5, 1, C.tinta);
    R(x - 1, y + 3, 3, 1, C.tinta);
    R(x, y + 4, 1, 1, C.tinta);
    R(x - 3, y, 7, 1, C.postit);
    R(x - 2, y + 1, 5, 1, C.postit);
    R(x - 1, y + 2, 3, 1, C.postit);
    R(x, y + 3, 1, 1, C.postit);

  return recorder.finishRecordingAsPicture();
}

export function zonePicture(box: readonly number[]) {
  const recorder = Skia.PictureRecorder();
  const ctx = recorder.beginRecording(Skia.XYWHRect(0, 0, 192, 336));
  const R = pixels(ctx);
  const brackets = (box: readonly number[]) => {
    const x = box[0]! + 1;
    const y = box[1]! + 1;
    const w = box[2]! - 2;
    const h = box[3]! - 2;
    const L = 7;
    for (const [cx, cy, dx, dy] of [[x, y, 1, 1], [x + w, y, -1, 1], [x, y + h, 1, -1], [x + w, y + h, -1, -1]] as const) {
      R(Math.min(cx, cx + dx * L), dy > 0 ? cy : cy - 2, L, 3, C.tinta);
      R(dx > 0 ? cx : cx - 2, Math.min(cy, cy + dy * L), 3, L, C.tinta);
      R(Math.min(cx, cx + dx * L) + (dx > 0 ? 1 : 0), dy > 0 ? cy + 1 : cy - 1, L - 1, 1, C.postit);
      R(dx > 0 ? cx + 1 : cx - 1, Math.min(cy, cy + dy * L) + (dy > 0 ? 1 : 0), 1, L - 1, C.postit);
    }
  };

  brackets(box);
  return recorder.finishRecordingAsPicture();
}
