// Pixel characters of the office, pre-scaled with nearest neighbour (scripts/generate-icons.mjs):
// assets/brand/retratos.png has one 16×20 portrait per character sheet at 4×.
import { useEffect, useState } from 'react';
import { Image, StyleSheet, View } from 'react-native';
import { LIBRARIAN_SPRITE, PORTRAIT_H, PORTRAIT_W, spriteOfRole } from '@compartido/logic/atlas';
import { ROLE_BY_ID, type RoleId } from '@compartido/logic/roles';
import { spriteFrameMs, useMotion } from '@/theme/motion';
import { colors, space } from '@/theme/tokens';
import LIBRARIAN_IDLE from '../../../assets/brand/bibliotecario-reposo.png';
import PORTRAITS from '../../../assets/brand/retratos.png';
import { T } from './Text';

const SHEETS = 14;
const IDLE_FRAMES = 6;

function Frame({ source, frames, index, scale }: { source: number; frames: number; index: number; scale: number }) {
  const width = PORTRAIT_W * scale;
  const height = PORTRAIT_H * scale;
  return (
    <View style={{ width, height, overflow: 'hidden' }} accessible={false} importantForAccessibility="no-hide-descendants">
      <Image source={source} style={{ width: width * frames, height, transform: [{ translateX: -index * width }] }} />
    </View>
  );
}

export function roleName(role: string | null | undefined): string {
  if (role === 'bibliotecario') return 'Bibliotecario';
  return (role && ROLE_BY_ID[role as RoleId]?.name) || 'Operador de cuenta';
}

export type PortraitSize = 'sm' | 'md' | 'lg';
const SCALE: Record<PortraitSize, number> = { sm: 1.5, md: 2, lg: 3 };

/** Pixel portrait of an agent, with its name (14 px, tinta-suave) as on the Tu turno cards. */
export function AgentPortrait({ role, size = 'md', showName = false, name }: { role: string | null | undefined; size?: PortraitSize; showName?: boolean; name?: string }) {
  const sprite = Math.min(spriteOfRole(role), SHEETS - 1);
  const image = <Frame source={PORTRAITS} frames={SHEETS} index={sprite} scale={SCALE[size]} />;
  if (!showName) return image;
  return (
    <View style={styles.named}>
      {image}
      <T variant="detalle" soft numberOfLines={1} style={styles.name}>
        {name || roleName(role)}
      </T>
    </View>
  );
}

/** The librarian idling (still with reduced motion): the empty states' character. */
export function IdleLibrarian({ scale = 3 }: { scale?: number }) {
  const { reduced } = useMotion();
  const [frame, setFrame] = useState(0);
  useEffect(() => {
    if (reduced) return;
    const timer = setInterval(() => setFrame((current) => (current + 1) % IDLE_FRAMES), spriteFrameMs);
    return () => clearInterval(timer);
  }, [reduced]);
  return <Frame source={LIBRARIAN_IDLE} frames={IDLE_FRAMES} index={reduced ? 0 : frame} scale={scale} />;
}

export { LIBRARIAN_SPRITE };

const styles = StyleSheet.create({
  named: { flexDirection: 'row', alignItems: 'center', gap: space[2] },
  name: { flexShrink: 1, color: colors.inkSoft },
});
