import { useEffect, useRef, useState, type MutableRefObject, type PointerEvent, type ReactNode } from 'react';
import { IconCerrar } from '../components/icons';

/** Dragging the grip down more than this closes the sheet. */
export const SWIPE_CLOSE_PX = 72;

export interface BottomSheetProps {
  /** id of the panel's heading. */
  labelledBy: string;
  onClose: () => void;
  children: ReactNode;
  sheetRef?: MutableRefObject<HTMLElement | null>;
}

/**
 * Half-height panel over the bottom of the screen, above the bottom bar. Not modal: there is no backdrop,
 * the scene stays where it is and can still be tapped. It closes with «Cerrar», Esc, or by dragging the
 * grip down.
 */
export function BottomSheet({ labelledBy, onClose, children, sheetRef }: BottomSheetProps) {
  const own = useRef<HTMLElement | null>(null);
  const drag = useRef<{ startY: number; pointer: number } | null>(null);
  const [offset, setOffset] = useState(0);
  const closeRef = useRef(onClose);
  useEffect(() => {
    closeRef.current = onClose;
  });

  useEffect(() => {
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    own.current?.focus({ preventScroll: true });
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') closeRef.current();
    };
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('keydown', onKey);
      if (previous && previous !== document.body && previous.isConnected) previous.focus({ preventScroll: true });
    };
  }, []);

  const onPointerDown = (event: PointerEvent<HTMLDivElement>) => {
    if ((event.target as Element).closest('button')) return;
    drag.current = { startY: event.clientY, pointer: event.pointerId };
    event.currentTarget.setPointerCapture?.(event.pointerId);
  };
  const onPointerMove = (event: PointerEvent<HTMLDivElement>) => {
    if (!drag.current) return;
    setOffset(Math.max(0, event.clientY - drag.current.startY));
  };
  const onPointerEnd = (event: PointerEvent<HTMLDivElement>) => {
    if (!drag.current) return;
    const moved = event.clientY - drag.current.startY;
    drag.current = null;
    setOffset(0);
    if (moved > SWIPE_CLOSE_PX) closeRef.current();
  };

  return (
    <section
      ref={(node) => {
        own.current = node;
        if (sheetRef) sheetRef.current = node;
      }}
      className={offset ? 'of-sheet dragging' : 'of-sheet'}
      role="dialog"
      aria-modal="false"
      aria-labelledby={labelledBy}
      tabIndex={-1}
      style={offset ? { transform: `translateY(${offset}px)` } : undefined}
    >
      <div className="of-sheet-grip" data-testid="sheet-grip" onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={onPointerEnd} onPointerCancel={onPointerEnd}>
        <span className="of-sheet-handle" aria-hidden="true" />
        <button type="button" className="of-sheet-close" aria-label="Cerrar" onClick={onClose}>
          <IconCerrar size={20} />
        </button>
      </div>
      <div className="of-sheet-body">{children}</div>
    </section>
  );
}
