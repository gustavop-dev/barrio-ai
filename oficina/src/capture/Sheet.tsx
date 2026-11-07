import { useEffect, useRef, type ReactNode } from 'react';

const FOCUSABLE = 'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

export interface SheetProps {
  /** Accessible name of the dialog («Captura para el equipo», «Foto»). */
  label: string;
  /** Esc and a tap outside. */
  onClose: () => void;
  /** While true (a request in flight, or a confirmation open on top) Esc, Tab and the backdrop do nothing here. */
  suspended?: boolean;
  className?: string;
  children: ReactNode;
}

/**
 * Bottom sheet (mobile) or centred panel (desktop, from 640px) of Captura.dc.html and Galeria.dc.html:
 * focus moves into it and stays there, Esc and a tap outside close it, focus returns where it was,
 * and the page behind does not scroll.
 */
export function Sheet({ label, onClose, suspended = false, className, children }: SheetProps) {
  const panel = useRef<HTMLDivElement>(null);
  const closeRef = useRef(onClose);
  const suspendedRef = useRef(suspended);
  useEffect(() => {
    closeRef.current = onClose;
    suspendedRef.current = suspended;
  });

  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const node = panel.current;
    node?.focus();
    const { overflow } = document.body.style;
    document.body.style.overflow = 'hidden';
    const onKey = (event: KeyboardEvent) => {
      if (suspendedRef.current || !node) return;
      if (event.key === 'Escape') {
        event.preventDefault();
        closeRef.current();
        return;
      }
      if (event.key !== 'Tab') return;
      const items = Array.from(node.querySelectorAll<HTMLElement>(FOCUSABLE)).filter((item) => !item.closest('[hidden]'));
      if (!items.length) return;
      const first = items[0]!;
      const last = items[items.length - 1]!;
      const active = document.activeElement;
      if (event.shiftKey && (active === first || active === node)) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && active === last) {
        event.preventDefault();
        first.focus();
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
      className="sheet-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !suspendedRef.current) onClose();
      }}
    >
      <div ref={panel} className={['sheet', className ?? ''].filter(Boolean).join(' ')} role="dialog" aria-modal="true" aria-label={label} tabIndex={-1}>
        {children}
      </div>
    </div>
  );
}
