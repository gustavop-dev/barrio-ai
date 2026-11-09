import type { AIEdit } from '@compartido/api/imagenes';
import { AI_EDIT_OPTIONS } from '@compartido/logic/imagenes';
import { Options } from './Options';

export function AIEditControl({ value, onChange, disabled, testID }: {
  value: AIEdit | null;
  onChange: (value: AIEdit) => void;
  disabled?: boolean;
  testID: string;
}) {
  return <Options legend="Edición con IA" options={AI_EDIT_OPTIONS} value={value} onChange={onChange} disabled={disabled} testID={testID} />;
}
