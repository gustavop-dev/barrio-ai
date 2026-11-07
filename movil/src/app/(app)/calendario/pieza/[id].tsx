import { useLocalSearchParams } from 'expo-router';
import { DetailScreen } from '@/components/shell/DetailScreen';
import { Placeholder } from '@/components/shell/Placeholder';

/** Detalle de una pieza (the PWA's /calendario/pieza/:id). */
export default function PiezaScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  return (
    <DetailScreen back="Calendario" fallback="/calendario">
      <Placeholder testID="screen-pieza" title="Detalle de la pieza" subtitle={id ? `Pieza ${id}` : undefined} />
    </DetailScreen>
  );
}
