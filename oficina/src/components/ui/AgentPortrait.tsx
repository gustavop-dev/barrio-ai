import type { CSSProperties } from 'react';
import { ROLE_BY_ID, type RoleId } from '../../scene/roles';
import { ATLAS_HEIGHT, ATLAS_URL, ATLAS_WIDTH, PORTRAIT_CROP_TOP, PORTRAIT_H, PORTRAIT_W, portraitOrigin, spriteOfRole } from './atlas';

export type PortraitSize = 'sm' | 'md' | 'lg';

/** sm 24×30 (×1.5), md 32×40 (×2, the design's list size), lg 48×60 (×3, the design's panel size). */
const SCALE: Record<PortraitSize, number> = { sm: 1.5, md: 2, lg: 3 };

/** Inline style that crops `sprite`'s portrait from the atlas at scale `k`. */
export function portraitStyle(sprite: number, k: number): CSSProperties {
  const [x, y] = portraitOrigin(sprite);
  return {
    width: PORTRAIT_W * k,
    height: PORTRAIT_H * k,
    backgroundImage: `url(${ATLAS_URL})`,
    backgroundSize: `${ATLAS_WIDTH * k}px ${ATLAS_HEIGHT * k}px`,
    backgroundPosition: `${-k * x}px ${-k * (y + PORTRAIT_CROP_TOP)}px`,
  };
}

export function roleName(role: string | null | undefined): string {
  if (role === 'bibliotecario') return 'Bibliotecario';
  return (role && ROLE_BY_ID[role as RoleId]?.name) || 'Operador de cuenta';
}

export interface AgentPortraitProps {
  /** Role id of scene/roles.ts (`agent` in the API), or 'bibliotecario'. Unknown ids use the account operator. */
  role: string | null | undefined;
  size?: PortraitSize;
  /** Shows the name next to the portrait (14px, tinta-suave), as in the Tu turno cards. */
  showName?: boolean;
  /** Name to show instead of the scene's (the API's `agent_label`). */
  name?: string;
  className?: string;
}

/** Pixel portrait of an agent, cropped from the sprite atlas. Decorative: the name carries the meaning. */
export function AgentPortrait({ role, size = 'md', showName = false, name, className }: AgentPortraitProps) {
  const image = <span className={['portrait-px', size, className ?? ''].filter(Boolean).join(' ')} aria-hidden="true" style={portraitStyle(spriteOfRole(role), SCALE[size])} />;
  if (!showName) return image;
  return (
    <span className="portrait-named">
      {image}
      <span className="portrait-name">{name || roleName(role)}</span>
    </span>
  );
}
