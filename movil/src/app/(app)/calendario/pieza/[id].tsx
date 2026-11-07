import { useLocalSearchParams } from 'expo-router';
import { DetailScreen } from '@/components/shell/DetailScreen';
import { PiezaScreen } from '@/pieza/PiezaScreen';

/** Detalle de una pieza (the PWA's /calendario/pieza/:pieceId). */
export default function PiezaRoute() {
  const { id } = useLocalSearchParams<{ id: string }>();
  return (
    <DetailScreen back="Calendario" fallback="/calendario">
      <PiezaScreen pieceId={id ?? ''} />
    </DetailScreen>
  );
}
