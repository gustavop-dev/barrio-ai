import { useId } from 'react';
import type { AIEdit } from '../../../../compartido/src/api/imagenes';
import { AI_EDIT_OPTIONS } from '../../../../compartido/src/logic/imagenes';
import './imagenes.css';

export function AIEditControl({ value, onChange, disabled, testID }: {
  value: AIEdit | null;
  onChange: (value: AIEdit) => void;
  disabled?: boolean;
  testID: string;
}) {
  const name = useId();
  return (
    <fieldset className="ai-edit-control" disabled={disabled} data-testid={testID}>
      <legend className="section-label">Edición con IA</legend>
      {AI_EDIT_OPTIONS.map((option) => (
        <label key={option.value}>
          <input type="radio" name={name} value={option.value} checked={value === option.value} onChange={() => onChange(option.value)} />
          {option.label}
        </label>
      ))}
    </fieldset>
  );
}
