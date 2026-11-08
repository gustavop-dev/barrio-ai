import { useState, type ReactNode } from 'react';
import { StyleSheet, View } from 'react-native';
import { space } from '@/theme/tokens';
import { Button } from './Button';
import { ErrorRetry } from './ErrorRetry';
import { Field } from './Field';
import { Sheet } from './Sheet';
import { T } from './Text';

export interface ConfirmSheetProps {
  title: string;
  confirmLabel: string;
  cancelLabel?: string;
  /** A note field: required (confirm disabled until written) or optional. */
  note?: 'required' | 'optional';
  noteLabel?: string;
  notePlaceholder?: string;
  tone?: 'default' | 'danger';
  busy?: boolean;
  error?: unknown;
  onConfirm: (note: string) => void;
  onClose: () => void;
  children?: ReactNode;
}

/** The PWA's ConfirmModal as a bottom sheet: title, text, optional note, Cancelar and the action. */
export function ConfirmSheet({
  title,
  confirmLabel,
  cancelLabel = 'Cancelar',
  note,
  noteLabel = 'Nota',
  notePlaceholder,
  tone = 'default',
  busy,
  error,
  onConfirm,
  onClose,
  children,
}: ConfirmSheetProps) {
  const [text, setText] = useState('');
  const missing = note === 'required' && !text.trim();
  return (
    <Sheet label={title} onClose={busy ? () => {} : onClose} suspended={busy} testID="confirm-sheet">
      <T variant="subtitulo" accessibilityRole="header">
        {title}
      </T>
      {typeof children === 'string' ? <T soft>{children}</T> : children}
      {note ? (
        <Field
          label={noteLabel}
          optional={note === 'optional'}
          required={note === 'required'}
          placeholder={notePlaceholder}
          value={text}
          onChangeText={setText}
          multiline
          editable={!busy}
          testID="confirm-note"
        />
      ) : null}
      <ErrorRetry error={error} />
      <View style={styles.actions}>
        <Button block variant={tone === 'danger' ? 'danger' : 'primary'} disabled={missing} loading={busy} onPress={() => onConfirm(text.trim())}>
          {confirmLabel}
        </Button>
        <Button block onPress={onClose} disabled={busy}>
          {cancelLabel}
        </Button>
      </View>
    </Sheet>
  );
}

const styles = StyleSheet.create({ actions: { gap: space[2] } });
