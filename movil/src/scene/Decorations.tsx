import { Picture, Skia, type SkCanvas } from '@shopify/react-native-skia';
import { useMemo, useState } from 'react';
import { useDerivedValue, type SharedValue } from 'react-native-reanimated';
import { paintFloor, paintLights, type Pen, type ScenePalette } from '@compartido/scene/art';
import { PLAN_HEIGHT, PLAN_WIDTH } from '@compartido/scene/plan';
import { sceneBracketLength, type SceneState } from '@compartido/scene/runtime';
import { CHARACTERS, LIBRARY, TEAMS, type CharacterId, type ZoneId } from '@compartido/scene/roles';
import { officeMotion } from '@/theme/motion';
import { colors } from '@/theme/tokens';
import { mailPicture, pointerPicture, zonePicture } from './decorations';

const PALETTE: ScenePalette = {
  tinta: colors.ink, tintaSuave: colors.inkSoft, papel: colors.paper, ofc: colors.brand, hondo: colors.brandDeep, claro: colors.brandLight, postit: colors.postIt,
};

/** The shared art's pen over a Skia canvas being recorded on the UI thread. Only rectangles: the lights draw no sprites. */
function lightPen(canvas: SkCanvas): Pen {
  'worklet';
  const paint = Skia.Paint();
  paint.setAntiAlias(false);
  return {
    rect: (x, y, w, h, color, alpha = 1) => {
      if (alpha <= 0) return;
      paint.setColor(Skia.Color(color));
      paint.setAlphaf(Math.min(1, alpha));
      canvas.drawRect(Skia.XYWHRect(x, y, w, h), paint);
    },
    sprite: () => {},
  };
}

/**
 * The dance floor, under the people. Recorded again each frame the scene changes, on the UI thread: the scene's own
 * clock decides what is lit, so nothing here goes through React.
 */
export function SceneFloor({ scene }: { scene: SharedValue<SceneState> }) {
  const picture = useDerivedValue(() => {
    const recorder = Skia.PictureRecorder();
    const canvas = recorder.beginRecording(Skia.XYWHRect(0, 0, PLAN_WIDTH, PLAN_HEIGHT));
    paintFloor(lightPen(canvas), scene.value);
    return recorder.finishRecordingAsPicture();
  });
  return <Picture picture={picture} />;
}

/**
 * Over the people: the dark of the empty zones, the screens in use, the game room's lights, the working lights and the
 * speech bubbles (only while an actor has one: a bubble is never left drawn with its opacity at zero).
 */
export function SceneLights({ scene }: { scene: SharedValue<SceneState> }) {
  const picture = useDerivedValue(() => {
    const recorder = Skia.PictureRecorder();
    const canvas = recorder.beginRecording(Skia.XYWHRect(0, 0, PLAN_WIDTH, PLAN_HEIGHT));
    paintLights(lightPen(canvas), scene.value, PALETTE);
    return recorder.finishRecordingAsPicture();
  });
  return <Picture picture={picture} />;
}

export function Decorations({ scene, selected, zone }: { scene: SharedValue<SceneState>; selected: CharacterId | null; zone: ZoneId | null }) {
  const box = zone === 'biblioteca' ? LIBRARY.box : TEAMS.find((t) => t.id === zone)?.box;
  const index = selected ? CHARACTERS.findIndex((c) => c.id === selected) : -1;
  return <>
    <CaptureMail scene={scene} />
    {box ? <ZoneBrackets key={zone} scene={scene} box={box} /> : null}
    {index >= 0 ? <SelectedPointer key={selected} scene={scene} index={index} /> : null}
  </>;
}

// Its own component, mounted with the selection, so its derived matrix never belongs to the previous character.
function SelectedPointer({ scene, index }: { scene: SharedValue<SceneState>; index: number }) {
  const [picture] = useState(pointerPicture);
  const matrix = useDerivedValue(() => {
    const a = scene.value.actors[index]!;
    return Skia.Matrix().translate(Math.round(a.x), Math.round(a.y - 46 - (a.bubble ? 12 : 0)));
  });
  return <Picture picture={picture} matrix={matrix} />;
}

// Its own component, mounted with the zone: a derived value created in the parent still held the previous
// (empty) brackets when the zone appeared, and <Picture> received undefined and crashed the scene.
function ZoneBrackets({ scene, box }: { scene: SharedValue<SceneState>; box: readonly number[] }) {
  const brackets = useMemo(() => Array.from({ length: officeMotion.bracketPx }, (_, i) => zonePicture(box, i + 1)), [box]);
  const picture = useDerivedValue(() => brackets[Math.min(brackets.length, sceneBracketLength(scene.value)) - 1]!);
  return <Picture picture={picture} />;
}

// Hidden by moving it far off the plan, not by a zero opacity: the old bubbles, hidden with opacity 0, stayed on
// screen on Android.
const OFF_PLAN = -10000;
function CaptureMail({ scene }: { scene: SharedValue<SceneState> }) {
  const [picture] = useState(mailPicture);
  const matrix = useDerivedValue(() => {
    const s = scene.value;
    const mail = s.mail && !s.still ? s.mail : null;
    return Skia.Matrix().translate(mail ? Math.round(mail.x) : OFF_PLAN, mail ? Math.round(mail.y) : OFF_PLAN);
  });
  return <Picture picture={picture} matrix={matrix} />;
}
