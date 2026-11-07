import type { CSSProperties, ReactNode } from 'react';
import { ATLAS_HEIGHT, ATLAS_URL, ATLAS_WIDTH, LIBRARIAN_SPRITE, PORTRAIT_CROP_TOP, PORTRAIT_H, PORTRAIT_W, idleRow } from './atlas';

const K = 3;
/** Direction 3 (facing the viewer) starts at frame 18 of the idle row. */
const FIRST_FRAME_X = 18 * 16;

function idleStyle(sprite: number): CSSProperties {
  return {
    width: PORTRAIT_W * K,
    height: PORTRAIT_H * K,
    backgroundImage: `url(${ATLAS_URL})`,
    backgroundSize: `${ATLAS_WIDTH * K}px ${ATLAS_HEIGHT * K}px`,
    backgroundPosition: `${-K * FIRST_FRAME_X}px ${-K * (idleRow(sprite) + PORTRAIT_CROP_TOP)}px`,
  };
}

export interface EmptyStateProps {
  title: ReactNode;
  children?: ReactNode;
  /** Optional action: a Button or ButtonLink. */
  action?: ReactNode;
  /** Character sheet of the scene (0–13); the librarian by default. */
  sprite?: number;
  /** Left-aligned inside a card instead of centred. */
  align?: 'center' | 'start';
}

/** Empty state: a small idle character of the office (still with reduced motion), a sentence and an optional action. */
export function EmptyState({ title, children, action, sprite = LIBRARIAN_SPRITE, align = 'center' }: EmptyStateProps) {
  return (
    <div className={`empty-state ${align}`}>
      <span className="idle-sprite" aria-hidden="true" style={idleStyle(sprite)} />
      <p className="empty-title">{title}</p>
      {children ? <div className="empty-text">{children}</div> : null}
      {action ? <div className="empty-action">{action}</div> : null}
    </div>
  );
}
