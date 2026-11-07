import { useLocalSearchParams } from 'expo-router';
import { DetailScreen } from '@/components/shell/DetailScreen';
import { PersonaScreen } from '@/personas/PersonaScreen';

/** Ficha de una persona (the PWA's /personas/:id). */
export default function PersonaRoute() {
  const { id } = useLocalSearchParams<{ id: string }>();
  return (
    <DetailScreen back="Personas" fallback="/personas">
      <PersonaScreen contactId={id ?? ''} />
    </DetailScreen>
  );
}
