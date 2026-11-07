// Detalle de una pieza (DISENO-VISTAS «Detalle de una pieza», Pieza.dc.html): the result by cut, the
// veto before it goes out, the preparation steps, the final text, Gustavo's comments for the team and
// how it was written. Opened from the calendar, the notifications and Tu turno.
import type { PieceDetailFull } from '@compartido/api/calendario';
import { usePiece } from '@compartido/api/hooks';
import { CALENDAR_TZ, longDay, todayIn } from '@compartido/logic/dates';
import { pieceStatus, vetoable } from '@compartido/logic/editorial';
import { formatTime } from '@compartido/logic/format';
import { isOnItsWay, pieceLeaves, pieceWhen, preparationStages, publishedAt, stageShort } from '@compartido/logic/piece';
import { turnoAnchor } from '@compartido/logic/turno';
import { useState } from 'react';
import { RefreshControl, ScrollView, StyleSheet, View } from 'react-native';
import { useNow } from '@/calendario/useNow';
import { VetoButton } from '@/calendario/Veto';
import { useContentInsets } from '@/components/shell/useContentInsets';
import { Badge, Button, Card, ErrorRetry, Note, PageHeader, Section, Skeleton, T, pageContent } from '@/components/ui';
import { openLink } from '@/navigation';
import { colors, space } from '@/theme/tokens';
import { ComoSeEscribio } from './ComoSeEscribio';
import { FinalText } from './FinalText';
import { PreparationTrack } from './PreparationTrack';
import { Resultado } from './Resultado';
import { TeamComments } from './TeamComments';

/** Blocked, skipped, vetoed, discarded, failed or uncertain: what happened, in the state's tone. */
function StatusNote({ piece }: { piece: PieceDetailFull }) {
  const action = piece.action_detail;
  switch (piece.status) {
    case 'blocked': {
      const reasons = piece.verification?.blocking_reasons?.length ? piece.verification.blocking_reasons : piece.note ? [piece.note] : [];
      return (
        <Note tone="error" title="El verificador bloqueó la pieza">
          {reasons.map((reason, index) => (
            <T key={index} variant="detalle">
              {reason}
            </T>
          ))}
        </Note>
      );
    }
    case 'skipped':
      return (
        <Note tone="info" title="Ese día no hubo publicación">
          {piece.brief?.skip_reason || piece.note || 'El director decidió no publicar: no había material genuino.'}
        </Note>
      );
    case 'vetoed':
      return (
        <Note tone="info" title="La vetaste">
          {action?.decision_note ? `Tu nota: ${action.decision_note}` : 'Ese día quedó sin publicación.'}
        </Note>
      );
    case 'discarded':
      return (
        <Note tone="info" title="La política no aprobó la pieza">
          {action?.decision_note || piece.note || undefined}
        </Note>
      );
    case 'failed':
      return (
        <Note tone="error" title="La publicación falló">
          {action?.execution?.note || piece.note || undefined}
        </Note>
      );
    case 'uncertain':
      return (
        <Note
          tone="error"
          title="No se sabe si salió"
          actions={
            action ? (
              <Button variant="ghost" onPress={() => openLink(`/tu-turno#${turnoAnchor(`uncertain:${action.id}`)}`)}>
                Resuélvela en Tu turno
              </Button>
            ) : undefined
          }
        >
          Comprueba en LinkedIn si el post está publicado y dilo en Tu turno.
        </Note>
      );
    default:
      return null;
  }
}

export function PiezaScreen({ pieceId }: { pieceId: string }) {
  const query = usePiece(pieceId);
  const piece = query.data as PieceDetailFull | undefined;
  const now = useNow();
  const { bottom } = useContentInsets();
  const [refreshing, setRefreshing] = useState(false);
  const timeZone = CALENDAR_TZ;
  const today = todayIn(timeZone, now);

  const refresh = async () => {
    setRefreshing(true);
    try {
      await query.refetch();
    } finally {
      setRefreshing(false);
    }
  };

  const content = [pageContent, { paddingBottom: bottom }];
  const refreshControl = <RefreshControl refreshing={refreshing} onRefresh={() => void refresh()} tintColor={colors.brandDeep} colors={[colors.brandDeep]} />;

  if (!piece) {
    return (
      <ScrollView testID="pieza" style={styles.screen} contentContainerStyle={content} refreshControl={refreshControl}>
        <PageHeader title="Detalle de la pieza" />
        {query.isPending ? <Skeleton variant="card" count={2} label="Cargando la pieza…" /> : null}
        <ErrorRetry error={query.isError ? query.error : null} onRetry={() => void query.refetch()} title="No se pudo cargar la pieza" />
      </ScrollView>
    );
  }

  const status = pieceStatus(piece.status);
  const day = longDay(piece.slot_date);
  const when =
    piece.status === 'preparing'
      ? `Etapa: ${stageShort(piece.stage)}`
      : isOnItsWay(piece.status)
        ? pieceLeaves(piece.scheduled_for, { today, timeZone })
        : pieceWhen(piece.status, piece.scheduled_for, { today, timeZone, now, published: publishedAt(piece) });
  const canVeto = Boolean(piece.action && vetoable(piece.action));
  const hour = formatTime(piece.scheduled_for, timeZone);

  return (
    <ScrollView testID="pieza" style={styles.screen} contentContainerStyle={content} refreshControl={refreshControl}>
      <View style={styles.head}>
        <PageHeader title={`Pieza del ${day}`} />
        <View style={styles.status}>
          <Badge tone={status.tone}>{status.label}</Badge>
          {when && when !== 'Día sin pieza' ? (
            <T variant="detalle" soft>
              {when}
            </T>
          ) : null}
        </View>
      </View>
      <ErrorRetry error={query.isError ? query.error : null} onRetry={() => void query.refetch()} title="No se pudo actualizar la pieza" />
      <StatusNote piece={piece} />

      {piece.status === 'published' || piece.snapshots?.length ? <Resultado piece={piece} timeZone={timeZone} now={now} /> : null}

      {canVeto && piece.action ? (
        <Section label="Veto">
          <Card>
            <T>{`El equipo publica solo. Si no quieres que salga, vétala antes de las ${hour}: ese día quedará sin publicación.`}</T>
            <VetoButton block target={{ actionId: piece.action.id, kind: 'pieza', when: `a las ${hour}` }} />
          </Card>
        </Section>
      ) : null}

      {piece.status === 'preparing' ? (
        <Section label="Preparándose">
          <Card>
            <PreparationTrack stages={preparationStages(piece.stage)} label="Etapas de la preparación" />
            <T variant="detalle" soft>{`${pieceLeaves(piece.scheduled_for, { today, timeZone })}. Puedes vetarla cuando esté lista.`}</T>
          </Card>
        </Section>
      ) : null}

      <FinalText piece={piece} />
      <TeamComments pieceId={piece.id} label={`Pieza del ${day}`} comments={piece.team_comments ?? []} now={now} />
      <ComoSeEscribio piece={piece} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.paper },
  head: { gap: space[2] },
  status: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: space[2] },
});
