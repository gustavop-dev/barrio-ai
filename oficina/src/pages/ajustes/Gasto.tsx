// Ajustes › Gasto de IA: today's line per budget, then the month and the total (GET /api/v1/ajustes).
import { monthAlert, spendLine, spendRows } from '../../../../compartido/src/logic/ajustes';
import { useAjustes } from '../../api/hooks';
import { Badge, Card, ErrorRetry, Meter, Section, Skeleton } from '../../components/ui';
import { isUnavailable, Row, Unavailable } from './shared';

export function GastoSection() {
  const ajustes = useAjustes();
  const spend = ajustes.data?.ai_spend;
  const alert = spend ? monthAlert(spend) : null;
  return (
    <Section label="Gasto de IA · hoy" id="gasto">
      {ajustes.isPending ? <Skeleton variant="card" label="Cargando el gasto…" /> : null}
      {isUnavailable(ajustes.error) ? <Unavailable>El gasto por presupuesto todavía no llega del servidor.</Unavailable> : <ErrorRetry error={ajustes.error} onRetry={() => void ajustes.refetch()} />}
      {spend ? (
        <Card className="aj-card">
          {spend.today.length ? (
            <div className="aj-meters">
              {spend.today.map((budget) => {
                const line = spendLine(budget);
                return 'text' in line ? (
                  <Row key={budget.budget} label={line.label}>
                    {line.text}
                  </Row>
                ) : (
                  <Meter key={budget.budget} label={line.label} value={line.used} max={line.max} display={line.display} />
                );
              })}
            </div>
          ) : (
            <p className="t-detalle text-suave">Hoy no hay presupuestos de IA configurados.</p>
          )}
          <div className="aj-rows">
            {spendRows(spend).map((row) => (
              <Row key={row.label} label={row.label}>
                {row.text}
              </Row>
            ))}
            {alert ? <Badge tone={alert.tone}>{alert.text}</Badge> : null}
          </div>
        </Card>
      ) : null}
    </Section>
  );
}
