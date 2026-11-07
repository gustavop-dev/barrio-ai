// Ajustes › Gasto de IA: today's line per budget, then the month and the total (GET /api/v1/ajustes).
import { useAjustes } from '../../api/hooks';
import { Card, ErrorRetry, Meter, Section, Skeleton } from '../../components/ui';
import { formatUsd } from '../../lib/format';
import { isUnavailable, Row, Unavailable } from './shared';

const known = (value: number | null | undefined): value is number => typeof value === 'number' && Number.isFinite(value);

export function GastoSection() {
  const ajustes = useAjustes();
  const spend = ajustes.data?.ai_spend;
  return (
    <Section label="Gasto de IA · hoy" id="gasto">
      {ajustes.isPending ? <Skeleton variant="card" label="Cargando el gasto…" /> : null}
      {isUnavailable(ajustes.error) ? <Unavailable>El gasto por presupuesto todavía no llega del servidor.</Unavailable> : <ErrorRetry error={ajustes.error} onRetry={() => void ajustes.refetch()} />}
      {spend ? (
        <Card className="aj-card">
          {spend.today.length ? (
            <div className="aj-meters">
              {spend.today.map((line) =>
                known(line.limit_usd) && line.limit_usd > 0 ? (
                  <Meter
                    key={line.budget}
                    label={line.label}
                    value={line.spent_usd}
                    max={line.limit_usd}
                    display={`${formatUsd(line.spent_usd)} de ${formatUsd(line.limit_usd)}`}
                  />
                ) : (
                  <Row key={line.budget} label={line.label}>
                    {known(line.spent_usd) ? formatUsd(line.spent_usd) : 'sin dato'}
                  </Row>
                ),
              )}
            </div>
          ) : (
            <p className="t-detalle text-suave">Hoy no hay presupuestos de IA configurados.</p>
          )}
          <div className="aj-rows">
            <Row label="Este mes">
              {known(spend.month_usd) ? (known(spend.limit_usd) ? `${formatUsd(spend.month_usd)} de ${formatUsd(spend.limit_usd)}` : formatUsd(spend.month_usd)) : 'sin dato'}
            </Row>
            <Row label="Desde el inicio">{known(spend.total_usd) ? formatUsd(spend.total_usd) : 'sin dato'}</Row>
            {known(spend.lead_month_usd) ? <Row label="Agente líder, este mes">{formatUsd(spend.lead_month_usd)}</Row> : null}
            {known(spend.transcription_month_usd) ? <Row label="Transcripción de audios, este mes">{formatUsd(spend.transcription_month_usd)}</Row> : null}
          </div>
        </Card>
      ) : null}
    </Section>
  );
}
