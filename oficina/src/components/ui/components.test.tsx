import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../api/client';
import { AgentPortrait } from './AgentPortrait';
import { ErrorRetry } from './ErrorRetry';
import { ExternalLink } from './ExternalLink';
import { Funnel } from './Funnel';
import { Meter, meterTone } from './Meter';
import { StageTrack } from './StageTrack';
import { ToastProvider, useToast } from './Toast';

describe('Meter', () => {
  it('is green below 80 %, amber from 80 % and red at 100 %', () => {
    expect(meterTone(7, 10)).toBe('ok');
    expect(meterTone(8, 10)).toBe('warn');
    expect(meterTone(10, 10)).toBe('bad');
    expect(meterTone(1, 0)).toBe('ok');
    render(<Meter label="Invitaciones hoy" value={5} max={5} />);
    const meter = screen.getByRole('meter', { name: 'Invitaciones hoy' });
    expect(meter).toHaveAttribute('aria-valuetext', '5 de 5');
    expect(meter).toHaveClass('bad');
  });
});

describe('Funnel', () => {
  it('shows each count and the conversion from the previous step, with — for missing data', () => {
    render(
      <Funnel
        steps={[
          { label: 'Conversación', value: 4 },
          { label: 'Necesidad identificada', value: 3 },
          { label: 'Cualificada', value: null },
        ]}
        aside="Cerrada sin acuerdo: 1"
      />,
    );
    expect(screen.getByRole('img', { name: 'Conversación: 4' })).toBeInTheDocument();
    expect(screen.getByText('3 · 75 %')).toBeInTheDocument();
    expect(screen.getByRole('img', { name: 'Cualificada: sin dato' })).toBeInTheDocument();
    expect(screen.getByText('Cerrada sin acuerdo: 1')).toBeInTheDocument();
  });
});

describe('ErrorRetry', () => {
  it('offers a retry, and says «No se puede ahora» on a 409', async () => {
    const user = userEvent.setup();
    const retry = vi.fn();
    const { rerender } = render(<ErrorRetry error={new ApiError(500, 'El servidor no pudo completar la petición.')} onRetry={retry} />);
    expect(screen.getByRole('alert')).toHaveTextContent('No se pudo completar');
    await user.click(screen.getByRole('button', { name: 'Reintentar' }));
    expect(retry).toHaveBeenCalledOnce();
    rerender(<ErrorRetry error={new ApiError(409, 'OPERATOR_PAUSED=true está en el entorno')} />);
    expect(screen.getByRole('alert')).toHaveTextContent('No se puede ahora');
    expect(screen.getByRole('alert')).toHaveClass('warn');
  });
});

describe('ExternalLink', () => {
  it('only renders https links, in a new tab without opener', () => {
    const { rerender } = render(<ExternalLink href="https://www.linkedin.com/in/x">Abrir en LinkedIn</ExternalLink>);
    const link = screen.getByRole('link', { name: 'Abrir en LinkedIn' });
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', 'noopener noreferrer');
    rerender(<ExternalLink href="javascript:alert(1)">Malo</ExternalLink>);
    expect(screen.queryByRole('link')).not.toBeInTheDocument();
    rerender(<ExternalLink href="http://example.com">Sin TLS</ExternalLink>);
    expect(screen.queryByRole('link')).not.toBeInTheDocument();
  });
});

describe('AgentPortrait', () => {
  it('crops the role portrait from the atlas and falls back to the account operator', () => {
    const { container, rerender } = render(<AgentPortrait role="director_editorial" showName />);
    const portrait = container.querySelector('.portrait-px') as HTMLElement;
    // Sprite 4 at [357, 1320], ×2, 9 rows cropped above the head (as in the design).
    expect(portrait.style.backgroundPosition).toBe('-714px -2658px');
    expect(portrait.style.width).toBe('32px');
    expect(screen.getByText('Director editorial')).toBeInTheDocument();
    rerender(<AgentPortrait role="un_rol_nuevo" size="lg" showName name="Rol nuevo" />);
    const fallback = container.querySelector('.portrait-px') as HTMLElement;
    expect(fallback.style.width).toBe('48px');
    expect(screen.getByText('Rol nuevo')).toBeInTheDocument();
  });
});

describe('StageTrack', () => {
  it('marks the current step and says each state', () => {
    render(
      <StageTrack
        variant="numbered"
        label="Preparación"
        stages={[
          { key: 'director', label: 'Director: idea y brief', state: 'done' },
          { key: 'lectores', label: 'Panel de lectores', state: 'current' },
          { key: 'verificador', label: 'Verificador', state: 'pending' },
        ]}
      />,
    );
    const items = screen.getAllByRole('listitem');
    expect(items[1]).toHaveAttribute('aria-current', 'step');
    expect(items[0]).toHaveTextContent('Director: idea y brief, hecho');
    expect(items[2]).toHaveTextContent('3');
  });
});

function ToastDemo({ undo }: { undo: () => void }) {
  const toast = useToast();
  return (
    <button type="button" onClick={() => toast.show('Vetada', { undo })}>
      Vetar
    </button>
  );
}

describe('Toast', () => {
  it('shows the message with «Deshacer» for 5 seconds', async () => {
    const user = userEvent.setup();
    const undo = vi.fn();
    render(
      <MemoryRouter>
        <ToastProvider>
          <ToastDemo undo={undo} />
        </ToastProvider>
      </MemoryRouter>,
    );
    await user.click(screen.getByRole('button', { name: 'Vetar' }));
    expect(screen.getByRole('status')).toHaveTextContent('Vetada');
    await user.click(screen.getByRole('button', { name: 'Deshacer' }));
    expect(undo).toHaveBeenCalledOnce();
    expect(screen.queryByText('Vetada')).not.toBeInTheDocument();

    vi.useFakeTimers();
    try {
      act(() => screen.getByRole('button', { name: 'Vetar' }).click());
      expect(screen.getByText('Vetada')).toBeInTheDocument();
      act(() => vi.advanceTimersByTime(5100));
      expect(screen.queryByText('Vetada')).not.toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });
});
