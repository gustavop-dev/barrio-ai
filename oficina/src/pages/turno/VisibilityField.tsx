import { useId } from 'react';

export interface VisibilityFieldProps {
  /** true: Público; false: Privado. */
  value: boolean;
  onChange: (publicUse: boolean) => void;
  legend?: string;
  disabled?: boolean;
}

/** «Quién puede verlo»: Público (can be told in posts and comments) or Privado (only guides decisions). */
export function VisibilityField({ value, onChange, legend = 'Quién puede verlo', disabled }: VisibilityFieldProps) {
  const name = useId();
  return (
    <fieldset className="turno-options" disabled={disabled}>
      <legend className="turno-legend">{legend}</legend>
      <label className="turno-option">
        <input type="radio" name={name} value="publico" checked={value} onChange={() => onChange(true)} />
        <span className="turno-option-text">
          <span>Público</span>
          <span className="turno-option-hint">El equipo puede mencionarlo en posts y comentarios.</span>
        </span>
      </label>
      <label className="turno-option">
        <input type="radio" name={name} value="privado" checked={!value} onChange={() => onChange(false)} />
        <span className="turno-option-text">
          <span>Privado</span>
          <span className="turno-option-hint">Solo orienta decisiones; nunca aparece en un texto público.</span>
        </span>
      </label>
    </fieldset>
  );
}
