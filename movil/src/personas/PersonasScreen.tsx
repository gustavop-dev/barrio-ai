// Personas: Barrio (the people of the network), Oportunidades and Referentes, as tabs. The tab and the Barrio
// filters live in the route params (?pestana=, ?etapa=&q=&rol=&modalidad=&origen=), as in the PWA, so the
// links of the old /red and /referentes land on the right place. The person card is its own screen.
import { StyleSheet, View } from 'react-native';
import { useParamState } from '@/components/shell/useParamState';
import { PageHeader, TabBar } from '@/components/ui';
import { space } from '@/theme/tokens';
import { Barrio } from './Barrio';
import { Oportunidades } from './Oportunidades';
import { Referentes } from './Referentes';

type Tab = 'barrio' | 'oportunidades' | 'referentes';

const TABS: readonly { value: Tab; label: string }[] = [
  { value: 'barrio', label: 'Barrio' },
  { value: 'oportunidades', label: 'Oportunidades' },
  { value: 'referentes', label: 'Referentes' },
];

export const PERSONAS_PARAMS = ['pestana', 'etapa', 'q', 'rol', 'modalidad', 'origen'] as const;

function readTab(value: string): Tab {
  return value === 'oportunidades' || value === 'referentes' ? value : 'barrio';
}

export function PersonasScreen() {
  const [params, setParams] = useParamState(PERSONAS_PARAMS);
  const tab = readTab(params.pestana);

  // Each tab starts clean: the Barrio filters do not apply to the other two.
  const choose = (next: Tab) => setParams({ pestana: next === 'barrio' ? '' : next, etapa: '', q: '', rol: '', modalidad: '', origen: '' });

  const header = (
    <View style={styles.header}>
      <PageHeader title="Personas" />
      <TabBar<Tab> label="Personas" tabs={TABS} value={tab} onChange={choose} />
    </View>
  );

  if (tab === 'oportunidades') return <Oportunidades header={header} />;
  if (tab === 'referentes') return <Referentes header={header} />;
  return (
    <Barrio
      header={header}
      filters={{ stage: params.etapa, q: params.q, role: params.rol, modality: params.modalidad, source: params.origen }}
      onFilters={(changes) =>
        setParams({
          pestana: '',
          ...(changes.stage !== undefined ? { etapa: changes.stage } : {}),
          ...(changes.q !== undefined ? { q: changes.q } : {}),
          ...(changes.role !== undefined ? { rol: changes.role } : {}),
          ...(changes.modality !== undefined ? { modalidad: changes.modality } : {}),
          ...(changes.source !== undefined ? { origen: changes.source } : {}),
        })
      }
    />
  );
}

const styles = StyleSheet.create({ header: { gap: space[4] } });
