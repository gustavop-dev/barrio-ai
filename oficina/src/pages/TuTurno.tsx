import { useMatch, useNavigate } from 'react-router-dom';
import { useTuTurno } from '../api/hooks';
import { Page, TabBar } from '../components/ui';
import { prioritySummary } from './turno/model';
import { Pendiente, pendingView } from './turno/Pendiente';
import { Sabe } from './turno/Sabe';
import './turno/turno.css';

type Tab = 'pendiente' | 'sabe';

const TABS = [
  { value: 'pendiente', label: 'Pendiente' },
  { value: 'sabe', label: 'Lo que el equipo sabe de ti' },
] as const;

/**
 * Tu turno (/tu-turno): only what Gustavo alone can resolve, grouped Urgente → Importante → Cuando puedas,
 * with the «Lo que el equipo sabe de ti» tab at /tu-turno/sabe.
 */
export function TuTurno() {
  const navigate = useNavigate();
  const tab: Tab = useMatch('/tu-turno/sabe') ? 'sabe' : 'pendiente';
  const turno = useTuTurno();
  const { groups } = pendingView(turno.data);

  return (
    <Page title="Bandeja de entrada" subtitle={groups.length ? prioritySummary(groups) : undefined} width="narrow">
      <div className="turno-view">
        <TabBar<Tab>
          label="Bandeja de entrada"
          idPrefix="turno-tab"
          tabs={TABS}
          value={tab}
          onChange={(next) => navigate(next === 'sabe' ? '/tu-turno/sabe' : '/tu-turno')}
        />
        <div role="tabpanel" id={`turno-tab-${tab}-panel`} aria-labelledby={`turno-tab-${tab}`}>
          {tab === 'pendiente' ? <Pendiente query={turno} /> : <Sabe />}
        </div>
      </div>
    </Page>
  );
}
