import { Atlas, FilterMode, MipmapMode, useColorBuffer, useRectBuffer, useRSXformBuffer, type SkImage } from '@shopify/react-native-skia';
import { useState } from 'react';
import { useAnimatedReaction, useSharedValue, type SharedValue } from 'react-native-reanimated';
import type { SceneState } from '@compartido/scene/runtime';
import { createSpriteBuffer, SPRITE_SLOTS, updateSprites } from './sprites';

export function Sprites({ atlas, scene }: { atlas: SkImage; scene: SharedValue<SceneState> }) {
  const [initial] = useState(createSpriteBuffer);
  const buffer = useSharedValue(initial);
  useAnimatedReaction(() => scene.value, (s) => {
    buffer.modify((b) => { updateSprites(s, b); return b; });
  });
  const rects = useRectBuffer(SPRITE_SLOTS, (rect, i) => {
    'worklet';
    const b = buffer.value.slots[i]!;
    rect.setXYWH(b.sx, b.sy, b.w, b.h);
  });
  const transforms = useRSXformBuffer(SPRITE_SLOTS, (form, i) => {
    'worklet';
    const b = buffer.value.slots[i]!;
    form.set(1, 0, b.x, b.y);
  });
  const colors = useColorBuffer(SPRITE_SLOTS, (color, i) => {
    'worklet';
    color[0] = 1; color[1] = 1; color[2] = 1; color[3] = buffer.value.slots[i]!.alpha;
  });
  return <Atlas image={atlas} sprites={rects} transforms={transforms} colors={colors} colorBlendMode="modulate" sampling={{ filter: FilterMode.Nearest, mipmap: MipmapMode.None }} />;
}
