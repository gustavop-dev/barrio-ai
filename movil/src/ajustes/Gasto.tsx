// Ajustes › Gasto de IA: today's line per budget, then the month against its limit, the total, the
// lead agent and transcription (GET /api/v1/ajustes `ai_spend`). Never «sin dato» as 0.
import { useAjustes } from '@compartido/api/hooks';
import { isUnavailable, monthAlert, spendLine, spendRows } from '@compartido/logic/ajustes';
import { StyleSheet, View } from 'react-native';
import { Badge, Card, ErrorRetry, KeyValue, Meter, Section, Skeleton, T } from '@/components/ui';
import { space } from '@/theme/tokens';
import { Unavailable } from './parts';

export function GastoSection() {
  const ajustes = useAjustes();
  const spend = ajustes.data?.ai_spend;
  const alert = spend ? monthAlert(spend) : null;
  return (
    <Section label="Gasto de IA · hoy">
      {ajustes.isPending ? <Skeleton variant="card" label="Cargando el gasto…" /> : null}
      {isUnavailable(ajustes.error) ? (
        <Unavailable>El gasto por presupuesto todavía no llega del servidor.</Unavailable>
      ) : (
        <ErrorRetry error={ajustes.error} onRetry={() => void ajustes.refetch()} />
      )}
      {spend ? (
        <Card>
          {spend.today.length ? (
            <View style={styles.meters}>
              {spend.today.map((budget) => {
                const line = spendLine(budget);
                return 'text' in line ? (
                  <KeyValue key={budget.budget} label={line.label}>
                    {line.text}
                  </KeyValue>
                ) : (
                  <Meter key={budget.budget} label={line.label} value={line.used} max={line.max} display={line.display} />
                );
              })}
            </View>
          ) : (
            <T variant="detalle" soft>
              Hoy no hay presupuestos de IA configurados.
            </T>
          )}
          <View style={styles.rows}>
            {spendRows(spend).map((row) => (
              <KeyValue key={row.label} label={row.label}>
                {row.text}
              </KeyValue>
            ))}
            {/* Near or over the monthly limit, in the Meter's tones (backlog #19). */}
            {alert ? (
              <View style={styles.alert} testID="gasto-mes-alerta">
                <Badge tone={alert.tone}>{alert.text}</Badge>
              </View>
            ) : null}
          </View>
        </Card>
      ) : null}
    </Section>
  );
}

const styles = StyleSheet.create({ meters: { gap: space[3] }, rows: { gap: 6 }, alert: { alignItems: 'flex-end' } });
