// «Tus comentarios para el equipo»: what Gustavo already told the team about the piece (the captures'
// `team_comments`), with its audio, and «Comentario para el equipo», which opens the capture sheet tied
// to the piece.
import type { TeamComment } from '@compartido/api/calendario';
import { sameOrigin } from '@compartido/api/capturas';
import { timeAgo } from '@compartido/logic/format';
import { useAudioPlayer, useAudioPlayerStatus } from 'expo-audio';
import { StyleSheet, View } from 'react-native';
import { apiUrl } from '@/api/config';
import { authHeaders } from '@/api/transport';
import { openCaptureSheet } from '@/capture/store';
import { Icon } from '@/components/icons';
import { Button, Card, Section, T } from '@/components/ui';
import { space } from '@/theme/tokens';

/** Plays an audio the API serves (`/media/…`), with the device token. */
function Listen({ path }: { path: string }) {
  const player = useAudioPlayer({ uri: apiUrl(path), headers: authHeaders() });
  const status = useAudioPlayerStatus(player);
  return (
    <Button size="small" icon={<Icon name={status.playing ? 'pausa' : 'play'} size={20} />} onPress={() => (status.playing ? player.pause() : player.play())}>
      {status.playing ? 'Pausar' : 'Escuchar'}
    </Button>
  );
}

function CommentCard({ comment, now }: { comment: TeamComment; now: number }) {
  const body = [comment.note, comment.transcript].filter(Boolean);
  const audio = comment.has_audio ? sameOrigin(comment.audio_url) : null;
  return (
    <Card compact>
      <T variant="detalle" soft>
        {timeAgo(comment.created_at, now)}
      </T>
      {(body.length ? body : [comment.text]).filter(Boolean).map((paragraph, index) => (
        <T key={index}>{paragraph}</T>
      ))}
      {audio ? (
        <View style={styles.audio}>
          <Listen path={audio} />
        </View>
      ) : null}
    </Card>
  );
}

export function TeamComments({ pieceId, label, comments, now }: { pieceId: string; label: string; comments: TeamComment[]; now: number }) {
  const button = (
    <Button block icon={<Icon name="microfono" size={20} />} onPress={() => openCaptureSheet({ tipo: 'pieza', id: pieceId, label })}>
      Comentario para el equipo
    </Button>
  );
  if (!comments.length) return button;
  return (
    <Section label="Tus comentarios para el equipo">
      {comments.map((comment) => (
        <CommentCard key={comment.id} comment={comment} now={now} />
      ))}
      {button}
    </Section>
  );
}

const styles = StyleSheet.create({ audio: { flexDirection: 'row', marginTop: space[1] } });
