// «Texto final» (Pieza.dc.html): the text as it goes out, its length, «Copiar» (the shared CopyButton) and
// «Se publica tal cual, en inglés».
import type { PieceDetail } from '@compartido/api/types';
import { formatNumber } from '@compartido/logic/format';
import { charCount } from '@compartido/logic/piece';
import { StyleSheet, View } from 'react-native';
import { Card, CopyButton, Section, T } from '@/components/ui';
import { space } from '@/theme/tokens';

export function FinalText({ piece }: { piece: PieceDetail }) {
  const text = piece.final_text || piece.selection?.final_text || '';
  if (!text) {
    if (piece.status === 'skipped') return null;
    return (
      <Section label="Texto final">
        <T soft>El texto final aparece cuando termine la selección.</T>
      </Section>
    );
  }
  const lines = text.split('\n').filter((line) => line.trim());
  return (
    <Section label="Texto final">
      <Card>
        <View style={styles.text}>
          {lines.map((line, index) => (
            <T key={index} testID={`piece-final-paragraph-${index + 1}`} selectable>
              {line}
            </T>
          ))}
        </View>
        <View style={styles.foot}>
          <T variant="detalle" soft>{`${formatNumber(charCount(text), 0)} caracteres`}</T>
          <CopyButton text={text} testID="copiar" />
        </View>
        <T variant="detalle" soft>
          Se publica tal cual, en inglés.
        </T>
      </Card>
    </Section>
  );
}

const styles = StyleSheet.create({
  text: { gap: space[2] },
  foot: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: space[2] },
});
