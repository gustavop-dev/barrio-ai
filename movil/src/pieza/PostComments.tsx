// «Conversación en el post» of a published piece (INT-04): each comment by thread, what the team did with it
// (answered, reacted, asked Gustavo, nothing) and the team's replies as LinkedIn shows them. Read only: the team
// answers on its own after the leader's review; Gustavo can always reply himself on LinkedIn.
import type { PieceComment, PieceComments } from '@compartido/api/types';
import { timeAgo } from '@compartido/logic/format';
import { COMMENT_STATUS_TONE, commentsSummary, pendingReplyLabel } from '@compartido/logic/piece';
import { router } from 'expo-router';
import { Pressable, StyleSheet, View } from 'react-native';
import { Badge, Card, Section, T } from '@/components/ui';
import { colors, space } from '@/theme/tokens';

function Author({ comment }: { comment: PieceComment }) {
  const name = comment.own ? 'Tú' : comment.author.name || 'Alguien';
  const contactId = comment.author.contact_id;
  if (!contactId || comment.own) return <T>{name}</T>;
  return (
    <Pressable accessibilityRole="link" hitSlop={4} onPress={() => router.push({ pathname: '/personas/[id]', params: { id: contactId } })}>
      <T color={colors.brandDeep}>{name}</T>
    </Pressable>
  );
}

function CommentBlock({ comment, now, answer = false }: { comment: PieceComment; now: number; answer?: boolean }) {
  const pending = pendingReplyLabel(comment);
  return (
    <View style={[styles.comment, answer && styles.answer]} testID={`comentario-${comment.id}`}>
      <View style={styles.head}>
        <View style={styles.who}>
          <Author comment={comment} />
          {comment.author.headline && !comment.own ? (
            <T variant="detalle" soft numberOfLines={1}>
              {comment.author.headline}
            </T>
          ) : null}
        </View>
        <Badge tone={COMMENT_STATUS_TONE[comment.status] ?? 'muted'}>{comment.status_label}</Badge>
      </View>
      <T selectable>{comment.text}</T>
      {comment.at ? (
        <T variant="detalle" soft>
          {timeAgo(comment.at, now)}
        </T>
      ) : null}
      {pending && comment.reply?.text ? (
        <View style={styles.pending}>
          <T variant="etiqueta" soft>
            {pending}
          </T>
          <T selectable>{comment.reply.text}</T>
        </View>
      ) : pending ? (
        <T variant="detalle" soft>
          {pending}
        </T>
      ) : null}
    </View>
  );
}

export function PostComments({ comments, now }: { comments: PieceComments | null | undefined; now: number }) {
  if (!comments) return null;
  return (
    <Section label="Conversación en el post" intro="El equipo responde solo a quien comenta, con el contexto del post y del perfil.">
      <T variant="detalle" soft>
        {commentsSummary(comments)}
        {comments.read_at ? ` · leído ${timeAgo(comments.read_at, now)}` : ''}
      </T>
      {comments.threads.map((thread) => (
        <Card compact key={thread.id}>
          <CommentBlock comment={thread.comment} now={now} />
          {thread.answers.map((answer) => (
            <CommentBlock key={answer.id} comment={answer} now={now} answer />
          ))}
        </Card>
      ))}
    </Section>
  );
}

const styles = StyleSheet.create({
  comment: { gap: space[1] },
  answer: { marginTop: space[2], paddingLeft: space[3], borderLeftWidth: 3, borderLeftColor: colors.line },
  head: { flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between', gap: space[2] },
  who: { flex: 1, minWidth: 0 },
  pending: { gap: space[1], paddingLeft: space[3], borderLeftWidth: 3, borderLeftColor: colors.line },
});
