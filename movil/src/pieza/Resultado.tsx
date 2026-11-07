// «Resultado» of a published piece (Pieza.dc.html): the 24 h / 72 h / 7 d cuts as cards, who commented
// by role and the post on LinkedIn. A missing value is «—», never 0; a cut not read yet says when it
// arrives («Aún no»), and «Sin dato» once its hour passed.
import type { PieceCommenter, PieceDetail, PieceSnapshot } from '@compartido/api/types';
import { timeAgo } from '@compartido/logic/format';
import { commenterRoles, CUT_LABEL, cutPending, engagementValue, metricValue, pieceUrl, publishedAt, RESULT_CUTS, RESULT_METRICS } from '@compartido/logic/piece';
import { Pressable, StyleSheet, View } from 'react-native';
import { Icon } from '@/components/icons';
import { Badge, Card, LabelChip, Section, T } from '@/components/ui';
import { isHttps, openLink } from '@/navigation';
import { colors, shell, space } from '@/theme/tokens';

function CutCard({ kind, snapshot, published, timeZone, now }: { kind: PieceSnapshot['kind']; snapshot?: PieceSnapshot; published: string; timeZone: string; now: number }) {
  const title = `A ${CUT_LABEL[kind]}`;
  if (!snapshot) {
    const missing = cutPending(kind, published, timeZone, now);
    return (
      <Card compact>
        <View style={styles.head} testID={`corte-${kind}`}>
          <T variant="etiqueta" soft>
            {title}
          </T>
          <Badge tone="muted">{missing.badge}</Badge>
        </View>
        <T variant="detalle" soft>
          {missing.text}
        </T>
      </Card>
    );
  }
  return (
    <Card compact>
      <View style={styles.head} testID={`corte-${kind}`}>
        <T variant="etiqueta" soft>
          {title}
        </T>
        <T variant="detalle">{`Interacción ${engagementValue(snapshot.engagement_pct)}`}</T>
      </View>
      <View style={styles.grid}>
        {RESULT_METRICS.map((metric) => (
          <View key={metric.key} style={styles.metric} accessible accessibilityLabel={`${metric.label}: ${metricValue(snapshot[metric.key])}`}>
            <T>{metricValue(snapshot[metric.key])}</T>
            <T variant="detalle" soft>
              {metric.label}
            </T>
          </View>
        ))}
      </View>
    </Card>
  );
}

function Commenters({ commenters }: { commenters: PieceCommenter[] | null | undefined }) {
  if (commenters === null || commenters === undefined) {
    return (
      <T variant="detalle" soft>
        Los comentarios aún no se han leído.
      </T>
    );
  }
  if (!commenters.length) {
    return (
      <T variant="detalle" soft>
        Nadie ha comentado todavía.
      </T>
    );
  }
  const { roles, unclassified } = commenterRoles(commenters);
  return (
    <View style={styles.chips} accessibilityLabel="Quién comentó, por rol">
      {roles.map(({ role, label, count }) => (
        <LabelChip key={role} tone="info">
          {`${label} · ${count}`}
        </LabelChip>
      ))}
      {unclassified ? <LabelChip tone="muted">{`Sin clasificar · ${unclassified}`}</LabelChip> : null}
    </View>
  );
}

export function Resultado({ piece, timeZone, now }: { piece: PieceDetail; timeZone: string; now: number }) {
  const byKind = new Map((piece.snapshots ?? []).map((snapshot) => [snapshot.kind, snapshot]));
  const published = publishedAt(piece);
  const url = pieceUrl(piece);
  const lastRead = typeof piece.metrics?.impressions === 'number' && !byKind.size ? piece.metrics : null;
  return (
    <Section label="Resultado" intro="Interacción = (reacciones + comentarios + republicaciones) / impresiones.">
      {RESULT_CUTS.map((kind) => (
        <CutCard key={kind} kind={kind} snapshot={byKind.get(kind)} published={published} timeZone={timeZone} now={now} />
      ))}
      {lastRead ? (
        <T variant="detalle" soft>
          {`Última lectura: ${metricValue(lastRead.impressions)} impresiones${lastRead.observed_at ? `, ${timeAgo(lastRead.observed_at, now)}` : ''}.`}
        </T>
      ) : null}
      <View style={styles.commenters}>
        <T variant="etiqueta" soft>
          Quién comentó
        </T>
        <Commenters commenters={piece.commenters} />
      </View>
      {isHttps(url) ? (
        <Pressable accessibilityRole="link" accessibilityHint="Se abre fuera de la app" onPress={() => openLink(url)} style={styles.external}>
          <T color={colors.brandDeep}>Ver el post en LinkedIn</T>
          <Icon name="external" size={18} color={colors.brandDeep} />
        </Pressable>
      ) : null}
    </Section>
  );
}

const styles = StyleSheet.create({
  head: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: space[2] },
  grid: { flexDirection: 'row', flexWrap: 'wrap', rowGap: space[2] },
  metric: { width: '50%', paddingRight: space[3] },
  commenters: { gap: space[2] },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: space[2] },
  external: { flexDirection: 'row', alignItems: 'center', gap: space[1], minHeight: shell.touch, alignSelf: 'flex-start' },
});
