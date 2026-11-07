// Ajustes › Autonomía y límites (folded; `/ajustes#autonomia` opens it): mode per capability, the
// lead agent, the time window, today's and this week's caps, and the network reads against their caps,
// with «Comprobaciones antes y después de escribir».
import { useAjustes, useOverview, useRedSummary } from '@compartido/api/hooks';
import { CAPABILITY_ORDER, capLines, EXECUTION_CHECKS_LABEL, isUnavailable, MODE_NAME, modeOf, readLines, spacingLabel } from '@compartido/logic/ajustes';
import type { ReactNode } from 'react';
import { StyleSheet, View } from 'react-native';
import { Badge, ErrorRetry, Fold, KeyValue, Skeleton, T } from '@/components/ui';
import { colors, space } from '@/theme/tokens';
import { Block, LimitRow, Unavailable } from './parts';

function ModeRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <View style={styles.mode}>
      <T style={styles.modeLabel}>{label}</T>
      {children}
    </View>
  );
}

function Body() {
  const ajustes = useAjustes();
  const overview = useOverview();
  const red = useRedSummary();
  const data = ajustes.data;
  const timeWindow = data?.window ?? overview.data?.window;
  const lead = data?.lead;
  const leadNames = (lead?.capabilities ?? []).map((code) => MODE_NAME[code] ?? code);
  const daily = capLines(data, overview.data, red.data, 'daily');
  const weekly = capLines(data, overview.data, red.data, 'weekly');
  const reads = red.data ? readLines(red.data) : null;

  return (
    <View style={styles.body}>
      {ajustes.isPending ? <Skeleton variant="row" count={3} label="Cargando la autonomía…" /> : null}
      {isUnavailable(ajustes.error) ? (
        <Unavailable>El modo por capacidad todavía no llega del servidor.</Unavailable>
      ) : (
        <ErrorRetry error={ajustes.error} onRetry={() => void ajustes.refetch()} />
      )}

      {data?.autonomy ? (
        <Block label="Modo por capacidad · solo lectura">
          <View>
            {CAPABILITY_ORDER.filter((code) => data.autonomy[code]).map((code) => {
              const mode = modeOf(data.autonomy[code]!);
              return (
                <ModeRow key={code} label={MODE_NAME[code]!}>
                  <Badge tone={mode.tone}>{mode.label}</Badge>
                </ModeRow>
              );
            })}
          </View>
          <T variant="detalle" soft>
            El equipo actúa solo en modo Auto. Puedes vetar lo programado desde el Calendario.
          </T>
        </Block>
      ) : null}

      {lead ? (
        <Block label="Agente líder">
          <ModeRow label="Decide en lugar de pedirte aprobación">
            <Badge tone={lead.enabled ? 'ok' : 'muted'}>{lead.enabled ? 'Activo' : 'Apagado'}</Badge>
          </ModeRow>
          {leadNames.length ? <KeyValue label="Capacidades">{leadNames.join(', ')}</KeyValue> : null}
          {lead.model ? <KeyValue label="Modelo">{lead.model}</KeyValue> : null}
          <T variant="detalle" soft>
            Aprueba solo lo que pasa sus comprobaciones con claridad; lo dudoso no se hace y nunca te llega para aprobar.
          </T>
        </Block>
      ) : null}

      {timeWindow ? (
        <Block label="Ventana horaria">
          <KeyValue label="Horario">{`${timeWindow.start}–${timeWindow.end} · ${timeWindow.timezone}`}</KeyValue>
          <KeyValue label="Ahora">{timeWindow.open_now ? 'Abierta' : 'Cerrada'}</KeyValue>
          <KeyValue label="Espaciado mínimo">{spacingLabel(timeWindow.min_spacing_seconds)}</KeyValue>
        </Block>
      ) : null}

      {daily.length ? (
        <Block label="Topes de hoy">
          <View style={styles.meters}>
            {daily.map((line) => (
              <LimitRow key={line.key} line={line} />
            ))}
          </View>
        </Block>
      ) : null}
      {weekly.length ? (
        <Block label="Topes de la semana">
          <View style={styles.meters}>
            {weekly.map((line) => (
              <LimitRow key={line.key} line={line} />
            ))}
          </View>
        </Block>
      ) : null}
      {reads && (reads.lines.length || reads.execution) ? (
        <Block label="Lecturas de la red">
          <View style={styles.meters}>
            {reads.lines.map((line) => (
              <LimitRow key={line.key} line={line} />
            ))}
            {reads.execution ? <KeyValue label={EXECUTION_CHECKS_LABEL}>{reads.execution}</KeyValue> : null}
          </View>
        </Block>
      ) : null}
    </View>
  );
}

/** Folded by default; a link to #autonomia opens it (a new link remounts the fold open). */
export function AutonomiaSection({ open }: { open: boolean }) {
  return (
    <View style={styles.fold} testID="autonomia">
      <Fold key={open ? 'abierta' : 'plegada'} summary="Autonomía y límites" initiallyOpen={open}>
        <Body />
      </Fold>
    </View>
  );
}

const styles = StyleSheet.create({
  fold: { borderBottomWidth: 1, borderBottomColor: colors.line },
  body: { gap: space[4] },
  mode: { minHeight: 40, flexDirection: 'row', alignItems: 'center', gap: space[2], borderTopWidth: 1, borderTopColor: colors.line },
  modeLabel: { flex: 1 },
  meters: { gap: space[3] },
});
