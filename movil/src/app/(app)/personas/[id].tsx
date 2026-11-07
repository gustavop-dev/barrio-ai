import { useLocalSearchParams } from 'expo-router';
import { DetailScreen } from '@/components/shell/DetailScreen';
import { Placeholder } from '@/components/shell/Placeholder';

/** Ficha de una persona (the PWA's /personas/:id). */
export default function PersonaScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  return (
    <DetailScreen back="Personas" fallback="/personas">
      <Placeholder testID="screen-persona" title="Ficha de la persona" subtitle={id ? `Persona ${id}` : undefined} />
    </DetailScreen>
  );
}
