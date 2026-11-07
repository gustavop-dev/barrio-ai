import { useEffect, useId, useRef, type ReactNode } from 'react';
import { IconCerrar } from '../icons';

const FOCUSABLE = 'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

export interface ModalProps {
  title: string;
  onClose: () => void;
  children: ReactNode;
  /** Action row, pinned under the body. */
  footer?: ReactNode;
  /** While true, Esc, the close button and the backdrop do nothing (a request is in flight). */
  busy?: boolean;
  /** id of the element that explains the consequence, for aria-describedby. */
  describedBy?: string;
}

/**
 * Accessible modal without <dialog>, so it behaves the same in every browser and in tests:
 * focus goes to the first field (or button), Tab stays inside, Esc and a click outside close it,
 * and focus returns to where it was. Bottom sheet on mobile, centred card from 640px.
 */
export function Modal({ title, onClose, children, footer, busy = false, describedBy }: ModalProps) {
  const titleId = useId();
  const panel = useRef<HTMLDivElement>(null);
  const closeRef = useRef(onClose);
  const busyRef = useRef(busy);
  useEffect(() => {
    closeRef.current = onClose;
    busyRef.current = busy;
  });

  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const node = panel.current;
    const first =
      node?.querySelector<HTMLElement>('textarea, input, select') ??
      node?.querySelector<HTMLElement>('.modal-body button:not(.modalclose), .modal-footer button:not([disabled])');
    first?.focus();
    const { overflow } = document.body.style;
    document.body.style.overflow = 'hidden';

    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        if (!busyRef.current) closeRef.current();
        return;
      }
      if (event.key !== 'Tab' || !node) return;
      const items = Array.from(node.querySelectorAll<HTMLElement>(FOCUSABLE));
      if (!items.length) return;
      const firstItem = items[0]!;
      const lastItem = items[items.length - 1]!;
      if (event.shiftKey && document.activeElement === firstItem) {
        event.preventDefault();
        lastItem.focus();
      } else if (!event.shiftKey && document.activeElement === lastItem) {
        event.preventDefault();
        firstItem.focus();
      }
    };
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = overflow;
      previous?.focus?.();
    };
  }, []);

  return (
    <div
      className="backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !busy) onClose();
      }}
    >
      <div className="modal" role="dialog" aria-modal="true" aria-labelledby={titleId} aria-describedby={describedBy} ref={panel}>
        <div className="modal-head">
          <h2 id={titleId} className="modal-title">
            {title}
          </h2>
          <button type="button" className="modalclose" aria-label="Cerrar" onClick={onClose} disabled={busy}>
            <IconCerrar size={20} />
          </button>
        </div>
        <div className="modal-body">{children}</div>
        {footer ? <div className="modal-footer">{footer}</div> : null}
      </div>
    </div>
  );
}
