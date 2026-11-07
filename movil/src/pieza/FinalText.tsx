// «Texto final» (Pieza.dc.html): the text as it goes out, its length, «Copiar» (expo-clipboard) and
// «Se publica tal cual, en inglés».
import type { PieceDetail } from '@compartido/api/types';
import { formatNumber } from '@compartido/logic/format';
import { charCount } from '@compartido/logic/piece';
import * as Clipboard from 'expo-clipboard';
import { useEffect, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { Button, Card, Section, T } from '@/components/ui';
import { copiedLabelMs, haptic } from '@/theme/motion';
import { space } from '@/theme/tokens';

function CopyButton({ text }: { text: string }) {
  const [state, setState] = useState<'idle' | 'copied' | 'failed'>('idle');
  useEffect(() => {
    if (state === 'idle') return;
    const timer = setTimeout(() => setState('idle'), copiedLabelMs);
    return () => clearTimeout(timer);
  }, [state]);
  const copy = async () => {
    try {
      await Clipboard.setStringAsync(text);
      haptic('copied');
      setState('copied');
    } catch {
      haptic('actionError');
      setState('failed');
    }
  };
  return (
    <Button size="small" onPress={() => void copy()} testID="copiar">
      {state === 'copied' ? 'Copiado' : state === 'failed' ? 'No se pudo copiar' : 'Copiar'}
    </Button>
  );
}

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
            <T key={index} selectable>
              {line}
            </T>
          ))}
        </View>
        <View style={styles.foot}>
          <T variant="detalle" soft>{`${formatNumber(charCount(text), 0)} caracteres`}</T>
          <CopyButton text={text} />
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
