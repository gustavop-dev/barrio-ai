import { Group, ImageShader, Picture, Rect, Skia, type SkImage, type SkPicture } from '@shopify/react-native-skia';
import { useMemo, useState } from 'react';
import { useAnimatedReaction, useDerivedValue, useSharedValue, type SharedValue } from 'react-native-reanimated';
import type { BubbleIcon } from '@compartido/scene/model';
import { sceneBracketLength, sceneStatus, type SceneState } from '@compartido/scene/runtime';
import { CHARACTERS, LIBRARY, TEAMS, type CharacterId, type ZoneId } from '@compartido/scene/roles';
import { ATLAS } from '@compartido/scene/atlas';
import { officeMotion } from '@/theme/motion';
import { colors, officeRoom } from '@/theme/tokens';
import { bubblePicture, mailPicture, pointerPicture, zonePicture } from './decorations';

export type BubblePictures = Record<BubbleIcon, SkPicture>;
export function useDecorations() {
  const [pictures] = useState(() => ({
    libro: bubblePicture('libro'), hoja: bubblePicture('hoja'), cafe: bubblePicture('cafe'), listo: bubblePicture('listo'),
    pregunta: bubblePicture('pregunta'), busca: bubblePicture('busca'), charla: bubblePicture('charla'),
  }));
  const [chatter] = useState(() => [pictures.charla, bubblePicture('charla', 1), bubblePicture('charla', 2)]);
  const [pointer] = useState(pointerPicture);
  return { pictures, chatter, pointer };
}
function ActorMarks({ index, scene, pictures, chatter, pointer, selected }: {
  index: number; scene: SharedValue<SceneState>; pictures: BubblePictures; chatter: SkPicture[]; pointer: SkPicture; selected: CharacterId | null;
}) {
  const [initialMatrix] = useState(() => Skia.Matrix());
  const matrix = useSharedValue(initialMatrix);
  useAnimatedReaction(() => scene.value, (s) => {
    const a = s.actors[index]!;
    matrix.modify((m) => m.identity().translate(Math.round(a.x), Math.round(a.y)));
  });
  const light = useDerivedValue(() => {
    const s = scene.value; const a = s.actors[index]!;
    return !s.paused && !s.frozen && !a.away && sceneStatus(s, a.id) === 'trabajando' ? 1 : 0;
  });
  const lightColor = useDerivedValue(() => scene.value.still || Math.floor(scene.value.clock / scene.value.motion.lightMs + index) % 3 !== 0 ? colors.brand : colors.brandDeep);
  const bubbleVisible = useDerivedValue(() => scene.value.actors[index]!.bubble ? 1 : 0);
  const bubble = useDerivedValue(() => {
    const s = scene.value; const kind = s.actors[index]!.bubble?.icon;
    if (kind === 'charla') return chatter[s.still ? 0 : Math.floor(s.clock / s.motion.bubbleFrameMs) % 3]!;
    return pictures[kind ?? 'libro'];
  });
  const pointerY = useDerivedValue<number>(() => scene.value.actors[index]!.bubble ? -58 : -46);
  const pointerMatrix = usePointerMatrix(pointerY);
  return <Group matrix={matrix}>
    <Group opacity={light}>
      <Rect x={5} y={-31} width={4} height={4} color={colors.ink} />
      <Rect x={6} y={-30} width={2} height={2} color={lightColor} />
    </Group>
    <Group transform={[{ translateY: -42 }]} opacity={bubbleVisible}><Picture picture={bubble} /></Group>
    {selected === CHARACTERS[index]!.id ? <Group origin={{ x: 0, y: 0 }}><Picture picture={pointer} matrix={pointerMatrix} /></Group> : null}
  </Group>;
}
// Always called by its own component (a selected pointer may mount/unmount independently).
function usePointerMatrix(y: SharedValue<number>) {
  return useDerivedValue(() => Skia.Matrix().translate(0, y.value));
}

function Monitor({ index, scene, atlas }: { index: number; scene: SharedValue<SceneState>; atlas: SkImage }) {
  const [x, y] = CHARACTERS[index]!.monitor!;
  const r = ATLAS.monitorFront!;
  const lit = useDerivedValue(() => {
    const s = scene.value; const a = s.actors[index]!;
    return !s.paused && !s.frozen && !a.away && sceneStatus(s, a.id) === 'trabajando' ? 1 : 0;
  });
  return <Group transform={[{ translateX: x }, { translateY: y }]}>
    <Rect x={0} y={0} width={r[2]} height={r[3]}>
      <ImageShader image={atlas} tx="clamp" ty="clamp" transform={[{ translateX: -r[0] }, { translateY: -r[1] }]} sampling={{ filter: 0, mipmap: 0 }} />
    </Rect>
    <Rect x={2} y={2} width={25} height={12} color={officeRoom.screenOff} />
    <Rect x={3} y={3} width={23} height={1} color={officeRoom.screenOffLine} />
    <Group opacity={lit}>
      <Rect x={2} y={2} width={25} height={12} color={colors.brandLight} />
      <Rect x={2} y={2} width={25} height={2} color={colors.brand} />
      <Rect x={4} y={6} width={13} height={1} color={colors.brandDeep} />
      <Rect x={4} y={9} width={17} height={1} color={officeRoom.screenLine} />
      <Rect x={4} y={12} width={9} height={1} color={officeRoom.screenLine} />
    </Group>
  </Group>;
}
export function Monitors({ scene, atlas }: { scene: SharedValue<SceneState>; atlas: SkImage }) {
  return CHARACTERS.map((a, index) => a.monitor ? <Monitor key={a.id} index={index} scene={scene} atlas={atlas} /> : null);
}
export function Decorations({ scene, selected, zone }: { scene: SharedValue<SceneState>; selected: CharacterId | null; zone: ZoneId | null }) {
  const pictures = useDecorations();
  const box = zone === 'biblioteca' ? LIBRARY.box : TEAMS.find((t) => t.id === zone)?.box;
  const brackets = useMemo(() => box ? Array.from({ length: officeMotion.bracketPx }, (_, i) => zonePicture(box, i + 1)) : [], [box]);
  const selectedZone = useDerivedValue(() => brackets[sceneBracketLength(scene.value) - 1]!);
  return <>
    {CHARACTERS.map((a, index) => <ActorMarks key={a.id} index={index} scene={scene} selected={selected} {...pictures} />)}
    <CaptureMail scene={scene} />
    {box ? <Picture picture={selectedZone} /> : null}
  </>;
}

function CaptureMail({ scene }: { scene: SharedValue<SceneState> }) {
  const [picture] = useState(mailPicture);
  const [initialMatrix] = useState(() => Skia.Matrix());
  const matrix = useSharedValue(initialMatrix);
  useAnimatedReaction(() => scene.value, (s) => {
    if (s.mail) matrix.modify((m) => m.identity().translate(Math.round(s.mail!.x), Math.round(s.mail!.y)));
  });
  const opacity = useDerivedValue(() => scene.value.mail && !scene.value.still ? 1 : 0);
  return <Group opacity={opacity} matrix={matrix}><Picture picture={picture} /></Group>;
}
