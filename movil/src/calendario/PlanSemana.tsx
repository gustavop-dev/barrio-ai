// «La semana» (Calendario › Semana; docs/plan-estrategia-semanal.md): the GASP type of each day of the week on screen,
// the idea the director planned for it, what the reader needs and the audience signal behind it. Gustavo changes a
// day's type, swaps two days or discards an idea in a sheet; «Volver a planear» is one paid call of the director, asked
// with its cost first. A week that already passed is not shown: the calendar tells what went out.
import {
  GASP_LABEL,
  GASP_PURPOSE,
  GASP_TYPES,
  SIGNAL_LABEL,
  useCambiarDia,
  useMoverDias,
  usePlanearSemana,
  useSemana,
  type AudienceSignalKind,
  type GaspType,
  type PlanDay,
  type WeekPlan,
} from '@compartido/api/estrategia';
import { longDayTitle, shortDay, weekDays } from '@compartido/logic/dates';
import { formatUsd } from '@compartido/logic/format';
import { newRequestId } from '@compartido/logic/resultados';
import { useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { Badge, Button, Card, ConfirmSheet, errorMessage, Fold, Note, Options, Sheet, Skeleton, T, useToast } from '@/components/ui';
import { haptic } from '@/theme/motion';
import { colors, radius, space } from '@/theme/tokens';

const STATE_NOTE: Record<string, string> = {
  discarded: 'Idea descartada: el director decide ese día.',
  capture: 'Una idea tuya ocupa este día.',
  used: 'Ya se preparó el post de este día.',
};

/** «Algo que contaste de un comprador: …», or why the idea has no audience signal. */
export function evidenceLine(day: PlanDay): string | null {
  if (!day.idea) return null;
  if (!day.evidence_ok || !day.audience_evidence) return 'Sin señal de la audiencia todavía: el director la busca ese día.';
  const label = SIGNAL_LABEL[day.audience_evidence.kind as AudienceSignalKind] ?? 'Señal de la audiencia';
  return day.audience_evidence.note ? `${label}: ${day.audience_evidence.note}` : label;
}

/** «Crecimiento 36 % · Autoridad 29 % · Venta 21 % · Personal 14 %» over the four weeks from this one. */
export function monthLine(plan: WeekPlan): string {
  return GASP_TYPES.map((type) => `${GASP_LABEL[type]} ${Math.round(plan.month_share[type]?.pct ?? 0)} %`).join(' · ');
}

function DayRow({ day, onPress }: { day: PlanDay; onPress: (day: PlanDay) => void }) {
  const evidence = evidenceLine(day);
  return (
    <Pressable
      testID={`plan-dia-${day.date}`}
      accessibilityRole="button"
      accessibilityLabel={`${longDayTitle(day.date)}, post de ${day.label.toLowerCase()}${day.idea ? `: ${day.idea}` : ''}`}
      accessibilityHint={day.editable ? 'Cambia el tipo, muévelo o descarta la idea' : undefined}
      accessibilityState={{ disabled: !day.editable }}
      onPress={() => onPress(day)}
      style={styles.row}
    >
      <View style={styles.letter}>
        <T variant="subtitulo" color={colors.brandDeep}>
          {day.type}
        </T>
      </View>
      <View style={styles.grow}>
        <T variant="detalle" soft>
          {`${shortDay(day.date)} · ${day.label}${day.owner_edited ? ' · lo cambiaste tú' : ''}`}
        </T>
        <T numberOfLines={2}>{day.idea ?? GASP_PURPOSE[day.type]}</T>
        {day.reader_need ? (
          <T variant="detalle" soft numberOfLines={2}>
            {`Para el lector: ${day.reader_need}`}
          </T>
        ) : null}
        {evidence ? (
          <T variant="detalle" soft numberOfLines={2} testID={`plan-senal-${day.date}`}>
            {evidence}
          </T>
        ) : null}
        {STATE_NOTE[day.state] ? (
          <T variant="detalle" soft>
            {STATE_NOTE[day.state]}
          </T>
        ) : null}
      </View>
    </Pressable>
  );
}

/** The sheet of one day: its type, a swap with another day of the week and «Descartar la idea». */
function DaySheet({ plan, day, onClose }: { plan: WeekPlan; day: PlanDay; onClose: () => void }) {
  const cambiar = useCambiarDia();
  const mover = useMoverDias();
  const toast = useToast();
  const busy = cambiar.isPending || mover.isPending;
  const error = cambiar.error ?? mover.error;
  const others = plan.days.filter((other) => other.date !== day.date && other.editable);
  const done = (message: string) => {
    haptic('actionSuccess');
    toast.show(message);
    onClose();
  };
  return (
    <Sheet label={`Cambiar el ${longDayTitle(day.date).toLowerCase()}`} onClose={busy ? () => {} : onClose} suspended={busy} testID="plan-dia-hoja">
      <View style={styles.sheet}>
        <T variant="subtitulo">{longDayTitle(day.date)}</T>
        {day.editable ? (
          <>
            <Options<GaspType>
              legend="Tipo del día"
              testID="plan-tipo"
              disabled={busy}
              value={day.type}
              options={GASP_TYPES.map((type) => ({ value: type, label: GASP_LABEL[type], hint: GASP_PURPOSE[type] }))}
              onChange={(tipo) => {
                if (tipo === day.type) return;
                cambiar.mutate({ dia: day.date, tipo }, { onSuccess: () => done(`El ${shortDay(day.date)} es de ${GASP_LABEL[tipo].toLowerCase()}`) });
              }}
            />
            {day.idea ? (
              <T variant="detalle" soft>
                Si cambias el tipo, su idea queda apartada para otro día.
              </T>
            ) : null}
            {others.length ? (
              <Options<string>
                legend="Cambiar con otro día"
                testID="plan-mover"
                disabled={busy}
                value={null}
                options={others.map((other) => ({ value: other.date, label: `${shortDay(other.date)} · ${other.label}`, hint: other.idea ?? undefined }))}
                onChange={(hasta) => mover.mutate({ desde: day.date, hasta }, { onSuccess: () => done('Días cambiados') })}
              />
            ) : null}
            {day.idea && day.state === 'planned' ? (
              <Button
                variant="ghost"
                disabled={busy}
                testID="plan-descartar"
                onPress={() => cambiar.mutate({ dia: day.date, descartar_idea: true }, { onSuccess: () => done('Idea descartada') })}
              >
                Descartar la idea
              </Button>
            ) : null}
          </>
        ) : (
          <T soft>Ese día ya pasó o su post ya está preparado: su tipo no cambia.</T>
        )}
        {error ? <Note tone="error">{errorMessage(error)}</Note> : null}
      </View>
    </Sheet>
  );
}

/** «Volver a planear» behind the cost confirmation (POST /estrategia/planear). */
function Regenerate({ plan }: { plan: WeekPlan }) {
  const planear = usePlanearSemana();
  const [asking, setAsking] = useState(false);
  // One id per intent: a retry after a network error never queues a second plan.
  const [requestId, setRequestId] = useState<string | undefined>(undefined);
  if (plan.regenerate.pending || planear.isSuccess) {
    return <Note tone="info">El director está planeando la semana. Tarda uno o dos minutos y aparecerá aquí.</Note>;
  }
  if (!plan.regenerate.available) return null;
  return (
    <>
      <Button
        variant="secondary"
        block
        testID="plan-volver-a-planear"
        onPress={() => {
          planear.reset();
          setRequestId(newRequestId());
          setAsking(true);
        }}
      >
        {plan.state === 'planeada' ? 'Volver a planear' : 'Planear la semana'}
      </Button>
      {asking ? (
        <ConfirmSheet
          title="Planear la semana"
          confirmLabel="Planear"
          busy={planear.isPending}
          error={planear.error}
          onClose={() => setAsking(false)}
          onConfirm={() =>
            planear.mutate(
              { semana: plan.week_start, requestId },
              {
                onSuccess: () => {
                  haptic('actionSuccess');
                  setAsking(false);
                },
                onError: () => haptic('actionError'),
              },
            )
          }
        >
          <T>El director planea la idea de cada día dentro de su tipo, con lo que pide la audiencia. Lo que cambiaste se queda.</T>
          <Note tone="warn">{`Tiene coste: unos ${formatUsd(plan.regenerate.estimated_usd)} (como mucho ${formatUsd(plan.regenerate.max_usd)}).`}</Note>
        </ConfirmSheet>
      ) : null}
    </>
  );
}

/** «La semana» of the week holding `fecha`; nothing for a week that already passed or with the strategy off. */
export function PlanSemana({ fecha, today }: { fecha: string; today: string }) {
  const days = weekDays(fecha);
  const past = days[days.length - 1]! < today;
  const query = useSemana(past ? today : fecha);
  const [editing, setEditing] = useState<string | null>(null);
  if (past) return null;
  const plan = query.data;
  if (query.isPending) return <Skeleton variant="card" label="Cargando la semana…" />;
  if (!plan || !plan.enabled) return null;
  const day = editing ? plan.days.find((item) => item.date === editing) : undefined;
  return (
    <Card>
      <View style={styles.card} testID="plan-semana" collapsable={false}>
        <View style={styles.head}>
          <T variant="subtitulo" accessibilityRole="header" style={styles.grow}>
            La semana
          </T>
          <Badge tone={plan.state === 'planeada' ? 'info' : 'muted'}>{plan.state_label}</Badge>
        </View>
        <T variant="detalle" soft>
          {plan.summary ?? 'Cada día tiene un tipo. El director planea las ideas el domingo; mientras tanto decide cada día.'}
        </T>
        <View>
          {plan.days.map((item) => (
            <DayRow key={item.date} day={item} onPress={(picked) => setEditing(picked.date)} />
          ))}
        </View>
        {plan.warnings.slice(0, 3).map((warning) => (
          <Note key={warning} tone="warn">
            {warning}
          </Note>
        ))}
        <T variant="detalle" soft testID="plan-mes">
          {`En cuatro semanas: ${monthLine(plan)}`}
        </T>
        {plan.kept_ideas.length ? (
          <Fold summary={`Ideas apartadas · ${plan.kept_ideas.length}`}>
            {plan.kept_ideas.map((idea) => (
              <T key={`${idea.date}-${idea.idea}`} soft>
                {`${GASP_LABEL[idea.type] ?? idea.type}: ${idea.idea}`}
              </T>
            ))}
          </Fold>
        ) : null}
        <Regenerate plan={plan} />
      </View>
      {day ? <DaySheet plan={plan} day={day} onClose={() => setEditing(null)} /> : null}
    </Card>
  );
}

const styles = StyleSheet.create({
  card: { gap: space[3] },
  head: { flexDirection: 'row', alignItems: 'center', gap: space[2] },
  grow: { flex: 1 },
  row: { flexDirection: 'row', gap: space[3], paddingVertical: space[2], borderTopWidth: 1, borderTopColor: colors.line },
  letter: {
    width: 32,
    height: 32,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.line,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.surface,
  },
  sheet: { gap: space[3] },
});
