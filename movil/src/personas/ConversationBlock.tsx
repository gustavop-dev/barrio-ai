// «Conversación» of the person card (DISENO-VISTAS, Personas, ficha 6): the team's read of the latest message,
// the last messages with author and date, and «Abrir en LinkedIn». Read-only: the app never sends messages.
import type { Conversation } from '@compartido/api/types';
import { teamRead } from '@compartido/logic/barrio';
import { messageText, messageWhen } from '@compartido/logic/personas';
import { StyleSheet, View } from 'react-native';
import { Badge, Card, LabelChip, T } from '@/components/ui';
import { ExternalLink } from '@/components/ui/ExternalLink';
import { colors, radius, space } from '@/theme/tokens';

function TeamRead({ conversation }: { conversation: Conversation }) {
  const read = teamRead(conversation.assessment);
  if (!read)
    return (
      <T variant="detalle" soft>
        El equipo aún no ha leído su último mensaje.
      </T>
    );
  return (
    <View style={styles.field}>
      <View style={styles.chips}>
        {read.chips.map((chip) =>
          chip.badge ? (
            <Badge key={chip.text} tone={chip.tone}>
              {chip.text}
            </Badge>
          ) : (
            <LabelChip key={chip.text} tone="muted">
              {chip.text}
            </LabelChip>
          ),
        )}
      </View>
      {read.numbers ? (
        <T variant="detalle" soft>
          {read.numbers}
        </T>
      ) : null}
    </View>
  );
}

function Messages({ conversation, name }: { conversation: Conversation; name: string }) {
  if (!conversation.messages.length) {
    return conversation.last_message_preview ? (
      <View style={styles.quote}>
        <T>“{conversation.last_message_preview}”</T>
      </View>
    ) : (
      <T variant="detalle" soft>
        Sin mensajes recientes.
      </T>
    );
  }
  return (
    <View accessibilityRole="list" accessibilityLabel="Últimos mensajes" style={styles.messages} testID="messages">
      {conversation.messages.map((message) => {
        const author = message.from_me ? 'Tú' : name;
        const when = message.at ? messageWhen(message.at) : '';
        return (
          <View key={message.id} style={[styles.message, message.from_me ? styles.mine : null]} testID={`message-${message.id}`}>
            <T variant="detalle" soft>
              {when ? `${author} · ${when}` : author}
            </T>
            <T>{messageText(message)}</T>
          </View>
        );
      })}
    </View>
  );
}

/** The person card block; `profileUrl` is the fallback link when there is no conversation yet. */
export function ConversationBlock({ conversation, name, profileUrl }: { conversation: Conversation | null | undefined; name: string; profileUrl?: string }) {
  if (!conversation) {
    return (
      <Card tone="dashed">
        <T>Aún no hay una conversación leída con esta persona</T>
        <T variant="detalle" soft>
          Cuando el equipo lea tu inbox de LinkedIn verás aquí sus últimos mensajes y su lectura. La app nunca envía mensajes.
        </T>
        <ExternalLink href={profileUrl} hint="Abre su perfil en LinkedIn">
          Abrir en LinkedIn
        </ExternalLink>
      </Card>
    );
  }
  return (
    <Card>
      <TeamRead conversation={conversation} />
      <Messages conversation={conversation} name={conversation.attendee_name || name} />
      <T variant="detalle" soft>
        La app nunca envía mensajes: respondes tú en LinkedIn.
      </T>
      <ExternalLink href={conversation.chat_url} hint="Abre la conversación en LinkedIn" testID="conversation-link">
        Abrir en LinkedIn
      </ExternalLink>
    </Card>
  );
}

const styles = StyleSheet.create({
  field: { gap: space[1] },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: space[1] },
  quote: { borderLeftWidth: 3, borderLeftColor: colors.line, paddingLeft: space[3] },
  messages: { gap: space[2] },
  message: { gap: 2, padding: space[3], borderRadius: radius.md, backgroundColor: colors.paper, marginRight: space[6] },
  mine: { backgroundColor: colors.brandLight, marginRight: 0, marginLeft: space[6] },
});
