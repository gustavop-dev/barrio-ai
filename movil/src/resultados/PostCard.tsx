// «Posts del periodo» at mobile size: one card per post (the PWA's table becomes cards), sorted with
// «Ordenar por». The card opens the piece.
import { commentersView, pillarLabel, POST_MOBILE_SORTS, type PostSortKey } from '@compartido/logic/resultados';
import { formatNumber, formatPct } from '@compartido/logic/format';
import { shortDate } from '@compartido/logic/personas';
import type { ResultadosPost } from '@compartido/api/types';
import { router } from 'expo-router';
import { Pressable, StyleSheet, View } from 'react-native';
import { LabelChip, T } from '@/components/ui';
import { Select } from '@/components/ui/Select';
import { colors, radius, space } from '@/theme/tokens';

function num(value: number | null | undefined): string {
  return value === null || value === undefined ? '—' : formatNumber(value);
}

function pct(value: number | null | undefined): string {
  return value === null || value === undefined ? '—' : formatPct(value);
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.stat} accessible accessibilityLabel={`${label}: ${value === '—' ? 'sin dato' : value}`}>
      <T variant="etiqueta" soft>
        {label}
      </T>
      <T>{value}</T>
    </View>
  );
}

function Commenters({ post }: { post: ResultadosPost }) {
  const view = commentersView(post);
  if (view.kind === 'nocut') return <LabelChip tone="info">Aún sin corte</LabelChip>;
  if (view.kind === 'unread')
    return (
      <T variant="detalle" soft>
        Sin leer
      </T>
    );
  if (view.kind === 'nobody')
    return (
      <T variant="detalle" soft>
        Nadie
      </T>
    );
  return (
    <>
      {view.chips.map((chip) => (
        <LabelChip key={chip} tone="info">
          {chip}
        </LabelChip>
      ))}
    </>
  );
}

/** The heading of the posts and «Ordenar por» (always descending, as in the PWA on mobile). */
export function PostsHeader({ count, sort, onSort }: { count: number; sort: PostSortKey; onSort: (key: PostSortKey) => void }) {
  return (
    <View style={styles.header}>
      <T variant="etiqueta" soft accessibilityRole="header">
        Posts del periodo
      </T>
      {count ? (
        <Select label="Ordenar por" value={sort} options={POST_MOBILE_SORTS} onChange={onSort} testID="posts-sort" />
      ) : (
        <T variant="detalle" soft>
          Sin posts publicados en el periodo.
        </T>
      )}
    </View>
  );
}

export function PostCard({ post }: { post: ResultadosPost }) {
  return (
    <View style={styles.card} testID={`post-${post.piece_id}`}>
      <View style={styles.head}>
        <T variant="detalle" soft style={styles.grow}>
          {shortDate(post.date)}
        </T>
        {post.pillar ? <LabelChip tone="muted">{pillarLabel(post.pillar)}</LabelChip> : null}
      </View>
      <Pressable
        accessibilityRole="link"
        onPress={() => router.push({ pathname: '/calendario/pieza/[id]', params: { id: post.piece_id } })}
        style={({ pressed }) => [styles.link, pressed ? styles.pressed : null]}
      >
        <T color={colors.brandDeep}>{post.first_line || 'Pieza sin texto'}</T>
      </Pressable>
      <View style={styles.stats}>
        <Stat label="24 h" value={num(post.impressions_24h)} />
        <Stat label="7 días" value={num(post.impressions_7d)} />
        <Stat label="Interacción" value={pct(post.engagement_pct)} />
        <Stat label="Reacciones" value={num(post.reactions)} />
        <Stat label="Comentarios" value={num(post.comments)} />
        <Stat label="Republic." value={num(post.reposts)} />
      </View>
      <View style={styles.chips}>
        <Commenters post={post} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  header: { gap: space[2] },
  card: { padding: space[4], gap: space[2], backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.line, borderRadius: radius.md },
  head: { flexDirection: 'row', alignItems: 'center', gap: space[2] },
  grow: { flex: 1 },
  link: { minHeight: 48, justifyContent: 'center', borderRadius: radius.sm },
  pressed: { backgroundColor: colors.paper },
  stats: { flexDirection: 'row', flexWrap: 'wrap', rowGap: space[2] },
  stat: { width: '33.33%', gap: 2, paddingRight: space[2] },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: space[1] },
});
