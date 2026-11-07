import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import type { Kpi } from '../../api/types';
import { KpiCard, kpiDelta, sparklinePoints } from './KpiCard';

function kpi(overrides: Partial<Kpi> = {}): Kpi {
  return {
    value: 4,
    previous: 2,
    delta: 2,
    delta_pct: 100,
    comparable: true,
    series: null,
    definition: 'Conversaciones abiertas en el periodo con personas que encajan.',
    formula: null,
    unavailable_reason: null,
    ...overrides,
  };
}

describe('KpiCard', () => {
  it('shows «sin dato» with the reason instead of 0 when the value is null', () => {
    const { container } = render(
      <KpiCard label="Seguidores" kpi={kpi({ value: null, delta: null, delta_pct: null, comparable: false, unavailable_reason: 'Disponible cuando capturemos la audiencia a diario.' })} />,
    );
    expect(screen.getByText('—')).toBeInTheDocument();
    expect(screen.getByText('Sin dato')).toBeInTheDocument();
    expect(screen.getByText('Disponible cuando capturemos la audiencia a diario.')).toBeInTheDocument();
    expect(container).not.toHaveTextContent(/\b0\b/);
    expect(container.querySelector('.kpi-delta')).toBeNull();
  });

  it('reads a KPI that did not arrive as not available yet', () => {
    render(<KpiCard label="Visitas al perfil" kpi={undefined} />);
    expect(screen.getByText('—')).toBeInTheDocument();
    expect(screen.getByText('Aún no disponible')).toBeInTheDocument();
  });

  it('shows the value and a green rise', () => {
    const { container } = render(<KpiCard label="Seguidores" kpi={kpi({ value: 1284, delta: 46 })} />);
    expect(screen.getByText('1.284')).toBeInTheDocument();
    const delta = container.querySelector('.kpi-delta');
    expect(delta).toHaveClass('good');
    expect(delta).toHaveTextContent('▲ 46');
    expect(screen.getByText('Sube 46 frente al periodo anterior')).toBeInTheDocument();
  });

  it('paints a fall red, in points for percentages', () => {
    const { container } = render(<KpiCard label="Tasa de aceptación" unit="percent" kpi={kpi({ value: 41, delta: -4, delta_pct: -8.9 })} />);
    expect(screen.getByText('41 %')).toBeInTheDocument();
    const delta = container.querySelector('.kpi-delta');
    expect(delta).toHaveClass('bad');
    expect(delta).toHaveTextContent('▼ −4 pts');
  });

  it('greys the variation when the periods are not comparable', () => {
    const { container } = render(<KpiCard label="Reuniones" kpi={kpi({ value: 1, delta: null, delta_pct: null, comparable: false })} />);
    expect(screen.getByText('1')).toBeInTheDocument();
    const delta = container.querySelector('.kpi-delta');
    expect(delta).toHaveClass('flat');
    expect(delta).toHaveTextContent('sin comparación');
  });

  it('shows the definition and formula behind ⓘ', async () => {
    const user = userEvent.setup();
    render(<KpiCard label="Interacción" unit="percent" kpi={kpi({ value: 3.5, formula: '(reacciones + comentarios + republicaciones) / impresiones' })} />);
    const info = screen.getByRole('button', { name: 'Definición de Interacción' });
    expect(info).toHaveAttribute('aria-expanded', 'false');
    await user.click(info);
    expect(info).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByText('Fórmula: (reacciones + comentarios + republicaciones) / impresiones')).toBeInTheDocument();
    expect(screen.getByText('3,5 %')).toBeInTheDocument();
  });

  it('draws the series as a minichart', () => {
    const { container } = render(
      <KpiCard
        label="Seguidores"
        kpi={kpi({
          series: [
            { date: '2026-11-01', value: 10 },
            { date: '2026-11-02', value: null },
            { date: '2026-11-03', value: 20 },
          ],
        })}
      />,
    );
    expect(container.querySelector('.kpi-spark polyline')).toHaveAttribute('points', '0.0,28.0 100.0,4.0');
  });
});

describe('kpiDelta and sparklinePoints', () => {
  it('handles equal periods, falls that are good and relative changes', () => {
    expect(kpiDelta(kpi({ delta: 0 }))).toMatchObject({ text: '= igual que antes', tone: 'flat' });
    expect(kpiDelta(kpi({ delta: -3 }), 'number', 'down')).toMatchObject({ text: '▼ −3', tone: 'good' });
    expect(kpiDelta(kpi({ delta: 120, delta_pct: 12 }), 'number', 'up', true)).toMatchObject({ text: '▲ 12 %', tone: 'good' });
  });

  it('needs two points', () => {
    expect(sparklinePoints([{ date: 'a', value: 1 }])).toBeNull();
    expect(sparklinePoints(null)).toBeNull();
  });
});
