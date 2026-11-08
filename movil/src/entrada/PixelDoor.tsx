// The login picture with its pixel door (MovEntrada), drawn with Skia and nearest-neighbour sampling
// so the pixels stay crisp at any size and through the integer zoom (2×, 3×). The door leaf folds on
// its hinge and the dark doorway shows; everything reads shared values, so it moves on the UI thread.
import { Canvas, FilterMode, Group, Image, MipmapMode, Rect, rect, useImage, type Transforms3d } from '@shopify/react-native-skia';
import { useMemo } from 'react';
import { useDerivedValue, type SharedValue } from 'react-native-reanimated';
import ATLAS from '../../assets/brand/sprites-atlas.png';
import PICTURE from '../../assets/brand/login-oficina-tarde.png';
import { DOOR } from './door';

const NEAREST = { filter: FilterMode.Nearest, mipmap: MipmapMode.None };

export interface DoorValues {
  /** 1, 2 or 3: the zoom on the top of the door. */
  zoom: SharedValue<number>;
  /** The leaf's width over its closed width (1 closed). */
  leaf: SharedValue<number>;
  /** The doorway's opacity. */
  hole: SharedValue<number>;
}

export function PixelDoor({ width, door, accessibilityLabel }: { width: number; door: DoorValues; accessibilityLabel: string }) {
  const picture = useImage(PICTURE);
  const atlas = useImage(ATLAS);
  const leafClip = useMemo(() => rect(DOOR.leaf.x, DOOR.leaf.y, DOOR.leaf.width, DOOR.leaf.height), []);
  const fit = width / DOOR.picture.width;
  const { x: ox, y: oy } = DOOR.zoomOrigin;
  const { zoom, leaf, hole } = door;
  const view = useDerivedValue<Transforms3d>(() => [{ scale: fit }, { translateX: ox }, { translateY: oy }, { scale: zoom.value }, { translateX: -ox }, { translateY: -oy }]);
  const hinge = useDerivedValue<Transforms3d>(() => [{ translateX: DOOR.leaf.x }, { scaleX: leaf.value }, { translateX: -DOOR.leaf.x }]);
  return (
    <Canvas style={{ width, height: DOOR.picture.height * fit }} accessibilityRole="image" accessibilityLabel={accessibilityLabel} testID="login-door">
      <Group transform={view}>
        {picture ? <Image image={picture} x={0} y={0} width={DOOR.picture.width} height={DOOR.picture.height} fit="fill" sampling={NEAREST} /> : null}
        <Rect x={DOOR.hole.x} y={DOOR.hole.y} width={DOOR.hole.width} height={DOOR.hole.height} color={DOOR.hole.color} opacity={hole} />
        {atlas ? (
          <Group transform={hinge} clip={leafClip}>
            <Image
              image={atlas}
              x={DOOR.leaf.x - DOOR.leaf.atlas.x * DOOR.leaf.scale}
              y={DOOR.leaf.y - DOOR.leaf.atlas.y * DOOR.leaf.scale}
              width={DOOR.atlas.width * DOOR.leaf.scale}
              height={DOOR.atlas.height * DOOR.leaf.scale}
              fit="fill"
              sampling={NEAREST}
            />
          </Group>
        ) : null}
      </Group>
    </Canvas>
  );
}
