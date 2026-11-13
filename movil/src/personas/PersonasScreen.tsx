// Personas: Conexiones (the people who accepted, Gustavo's people database), Oportunidades, Referentes and Comunidad,
// as tabs. The tab and the Conexiones filters live in the route params (?pestana=, ?q=&rol=), as in the PWA, so the
// links of the old /red and /referentes land on the right place. The old funnel filters (?etapa=, ?modalidad=,
// ?origen=) of earlier links are ignored: they open Conexiones. The person card is its own screen.
import { StyleSheet, View } from 'react-native';
import { useParamState } from '@/components/shell/useParamState';
import { PageHeader, TabBar } from '@/components/ui';
import { space } from '@/theme/tokens';
import { Conexiones } from './Conexiones';
import { Oportunidades } from './Oportunidades';
import { Referentes } from './Referentes';
import { Comunidad } from './Comunidad';

type Tab = 'conexiones' | 'oportunidades' | 'referentes' | 'comunidad';

const TABS: readonly { value: Tab; label: string }[] = [
  { value: 'conexiones', label: 'Conexiones' },
  { value: 'oportunidades', label: 'Oportunidades' },
  { value: 'referentes', label: 'Referentes' },
  { value: 'comunidad', label: 'Comunidad' },
];

export const PERSONAS_PARAMS = ['pestana', 'q', 'rol'] as const;

function readTab(value: string): Tab {
  return value === 'oportunidades' || value === 'referentes' || value === 'comunidad' ? value : 'conexiones';
}

export function PersonasScreen() {
  const [params, setParams] = useParamState(PERSONAS_PARAMS);
  const tab = readTab(params.pestana);

  // Each tab starts clean: the Conexiones filters do not apply to the others.
  const choose = (next: Tab) => setParams({ pestana: next === 'conexiones' ? '' : next, q: '', rol: '' });

  const header = (
    <View style={styles.header}>
      <PageHeader title="Personas" />
      <TabBar<Tab> label="Personas" tabs={TABS} value={tab} onChange={choose} testIDPrefix="personas" />
    </View>
  );

  if (tab === 'oportunidades') return <Oportunidades header={header} />;
  if (tab === 'referentes') return <Referentes header={header} />;
  if (tab === 'comunidad') return <Comunidad header={header} />;
  return (
    <Conexiones
      header={header}
      filters={{ q: params.q, role: params.rol }}
      onFilters={(changes) =>
        setParams({
          pestana: '',
          ...(changes.q !== undefined ? { q: changes.q } : {}),
          ...(changes.role !== undefined ? { rol: changes.role } : {}),
        })
      }
    />
  );
}

const styles = StyleSheet.create({ header: { gap: space[4] } });
