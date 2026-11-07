import type { ReactNode } from 'react';

// Shared with the native app: compartido/src/logic/ajustes.ts.
export { isUnavailable } from '../../../../compartido/src/logic/ajustes';

/** A key/value row («Origen · Desde la app»). */
export function Row({ label, children }: { label: ReactNode; children: ReactNode }) {
  return (
    <div className="kv">
      <span>{label}</span>
      <span>{children}</span>
    </div>
  );
}

/** The intentional «Aún no disponible» state: muted, dashed, never an error. */
export function Unavailable({ children }: { children?: ReactNode }) {
  return (
    <div className="aj-unavailable">
      <p className="t-cuerpo">Aún no disponible</p>
      {children ? <p className="t-detalle text-suave">{children}</p> : null}
    </div>
  );
}

/** A switch row: label on the left, the checkbox (role="switch") on the right. */
export function SwitchRow({
  label,
  hint,
  checked,
  disabled,
  onChange,
}: {
  label: string;
  hint?: ReactNode;
  checked: boolean;
  disabled?: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label className="aj-switch">
      <span className="aj-switch-text">
        <span>{label}</span>
        {hint ? <span className="t-detalle text-suave">{hint}</span> : null}
      </span>
      <input type="checkbox" role="switch" checked={checked} disabled={disabled} onChange={(event) => onChange(event.target.checked)} />
    </label>
  );
}
