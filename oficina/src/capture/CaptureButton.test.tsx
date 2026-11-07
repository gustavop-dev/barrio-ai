import { act, fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ToastProvider } from '../components/ui/Toast';
import { CaptureButton } from './CaptureButton';
import { CAPTURE_LABEL, CaptureProvider, type CaptureSeed } from './CaptureContext';
import { installFakeMedia, removeFakeMedia } from './fakeMedia';
import { resetMicStateForTests } from './recorder';
import { resetCaptureStoreForTests } from './store';

function renderButton() {
  const onCapture = vi.fn();
  render(
    <ToastProvider>
      <CaptureProvider onCapture={onCapture}>
        <CaptureButton />
      </CaptureProvider>
    </ToastProvider>,
  );
  return { onCapture, button: screen.getByRole('button', { name: CAPTURE_LABEL }) };
}

const at = (x: number, y: number) => ({ pointerId: 1, button: 0, isPrimary: true, clientX: x, clientY: y });

/** Presses, waits for the hold to start and lets the microphone open. */
async function startHold(button: HTMLElement) {
  fireEvent.pointerDown(button, at(200, 800));
  await act(async () => {
    await vi.advanceTimersByTimeAsync(250);
  });
}

beforeEach(() => {
  resetCaptureStoreForTests();
  vi.useFakeTimers({ shouldAdvanceTime: true });
});
afterEach(() => {
  vi.useRealTimers();
  removeFakeMedia();
});

describe('Botón de captura', () => {
  it('opens the sheet without recording on a short tap or Enter', async () => {
    resetMicStateForTests('granted');
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    const { onCapture, button } = renderButton();
    await user.click(button);
    expect(onCapture).toHaveBeenCalledTimes(1);
    expect(onCapture).toHaveBeenCalledWith(undefined);
    button.focus();
    await user.keyboard('{Enter}');
    expect(onCapture).toHaveBeenCalledTimes(2);
  });

  it('records while held and opens the sheet with the audio ready on release', async () => {
    installFakeMedia();
    resetMicStateForTests('granted');
    const { onCapture, button } = renderButton();
    await startHold(button);
    expect(button).toHaveClass('holding');
    expect(screen.getByText('Desliza hacia arriba para bloquear')).toBeInTheDocument();
    expect(screen.getByText('‹ Desliza para cancelar')).toBeInTheDocument();
    expect(screen.getByText(/^Grabando audio\. Suelta para terminar/)).toHaveAttribute('role', 'status');

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1500);
    });
    fireEvent.pointerUp(button, at(200, 800));
    fireEvent.click(button);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10);
    });
    expect(onCapture).toHaveBeenCalledTimes(1);
    const seed = onCapture.mock.calls[0]![1] as CaptureSeed;
    expect(seed.audio?.blob.size).toBeGreaterThan(0);
    expect(seed.audio?.duration).toBeGreaterThan(1);
    expect(button).not.toHaveClass('holding');
  });

  it('locks the recording when sliding up: it carries on in the sheet', async () => {
    installFakeMedia();
    resetMicStateForTests('granted');
    const { onCapture, button } = renderButton();
    await startHold(button);
    fireEvent.pointerMove(button, at(200, 760));
    expect(onCapture).not.toHaveBeenCalled();
    fireEvent.pointerMove(button, at(200, 720));
    expect(onCapture).toHaveBeenCalledTimes(1);
    const seed = onCapture.mock.calls[0]![1] as CaptureSeed;
    expect(seed.recorder?.active).toBe(true);
    // Lifting the finger afterwards neither stops it nor opens the sheet again.
    fireEvent.pointerUp(button, at(200, 720));
    fireEvent.click(button);
    expect(onCapture).toHaveBeenCalledTimes(1);
    await seed.recorder?.discard();
  });

  it('discards when sliding left, with «Recuperar» in the toast', async () => {
    installFakeMedia();
    resetMicStateForTests('granted');
    const { onCapture, button } = renderButton();
    await startHold(button);
    fireEvent.pointerMove(button, at(60, 800));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10);
    });
    expect(screen.getByText('Grabación descartada.')).toBeInTheDocument();
    expect(onCapture).not.toHaveBeenCalled();
    fireEvent.pointerUp(button, at(60, 800));
    fireEvent.click(screen.getByRole('button', { name: 'Recuperar' }));
    expect(onCapture).toHaveBeenCalledTimes(1);
    expect((onCapture.mock.calls[0]![1] as CaptureSeed).audio).toBeDefined();
  });

  it('counts a very short hold as a tap, without audio', async () => {
    installFakeMedia();
    resetMicStateForTests('granted');
    const { onCapture, button } = renderButton();
    await startHold(button);
    fireEvent.pointerUp(button, at(200, 800));
    fireEvent.click(button);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10);
    });
    expect(onCapture).toHaveBeenCalledTimes(1);
    expect(onCapture).toHaveBeenCalledWith(undefined);
  });

  it('explains the microphone before asking for it', async () => {
    installFakeMedia();
    resetMicStateForTests('prompt');
    const { onCapture, button } = renderButton();
    await startHold(button);
    expect(onCapture).toHaveBeenCalledWith(undefined, { mic: 'explain' });
    expect(button).not.toHaveClass('holding');
    fireEvent.pointerUp(button, at(200, 800));
    fireEvent.click(button);
    expect(onCapture).toHaveBeenCalledTimes(1);
  });

  it('opens without audio when the microphone is blocked', async () => {
    installFakeMedia();
    resetMicStateForTests('denied');
    const { onCapture, button } = renderButton();
    await startHold(button);
    expect(onCapture).toHaveBeenCalledWith(undefined, { mic: 'denied' });
  });
});
