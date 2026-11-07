import { fireEvent, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../api/client';
import { ConfirmModal } from './ConfirmModal';

function veto(props: Partial<Parameters<typeof ConfirmModal>[0]> = {}) {
  const onConfirm = vi.fn();
  const onClose = vi.fn();
  render(
    <>
      <button type="button">Vetar</button>
      <ConfirmModal title="Vetar la pieza" confirmLabel="Vetar" tone="danger" note="required" noteLabel="Por qué la vetas" onConfirm={onConfirm} onClose={onClose} {...props}>
        La pieza no saldrá y ese día quedará sin publicación.
      </ConfirmModal>
    </>,
  );
  return { onConfirm, onClose, dialog: screen.getByRole('dialog', { name: props.title ?? 'Vetar la pieza' }) };
}

describe('ConfirmModal', () => {
  it('keeps Confirm disabled until the required note has text, then sends it trimmed', async () => {
    const user = userEvent.setup();
    const { onConfirm, dialog } = veto();
    expect(dialog).toHaveAccessibleDescription('La pieza no saldrá y ese día quedará sin publicación.');
    const note = within(dialog).getByLabelText(/Por qué la vetas/);
    expect(note).toHaveFocus();
    expect(note).toBeRequired();
    const confirm = within(dialog).getByRole('button', { name: 'Vetar' });
    expect(confirm).toBeDisabled();

    await user.type(note, '   ');
    expect(confirm).toBeDisabled();
    await user.type(note, 'No es el momento  ');
    expect(confirm).toBeEnabled();
    await user.click(confirm);
    expect(onConfirm).toHaveBeenCalledWith('No es el momento');
  });

  it('allows an empty optional note', async () => {
    const user = userEvent.setup();
    const { onConfirm, dialog } = veto({ title: 'Reanudar', confirmLabel: 'Reanudar', tone: 'primary', note: 'optional', noteLabel: 'Nota' });
    await user.click(within(dialog).getByRole('button', { name: 'Reanudar' }));
    expect(onConfirm).toHaveBeenCalledWith('');
  });

  it('closes with Esc, with a click outside and with Cancelar', async () => {
    const user = userEvent.setup();
    const { onClose, dialog } = veto();
    await user.keyboard('{Escape}');
    expect(onClose).toHaveBeenCalledTimes(1);
    fireEvent.mouseDown(dialog.parentElement!);
    expect(onClose).toHaveBeenCalledTimes(2);
    fireEvent.mouseDown(dialog);
    expect(onClose).toHaveBeenCalledTimes(2);
    await user.click(within(dialog).getByRole('button', { name: 'Cancelar' }));
    expect(onClose).toHaveBeenCalledTimes(3);
  });

  it('stays open while busy and shows the error of the last attempt', async () => {
    const user = userEvent.setup();
    const { onClose, dialog } = veto({ busy: true, busyLabel: 'Vetando…', error: new ApiError(409, 'La acción ya se está ejecutando.') });
    expect(within(dialog).getByRole('button', { name: 'Vetando…' })).toBeDisabled();
    await user.keyboard('{Escape}');
    fireEvent.mouseDown(dialog.parentElement!);
    expect(onClose).not.toHaveBeenCalled();
    expect(within(dialog).getByRole('alert')).toHaveTextContent('No se puede ahora');
    expect(within(dialog).getByRole('alert')).toHaveTextContent('La acción ya se está ejecutando.');
  });
});
