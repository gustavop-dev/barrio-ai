import { Outlet, useMatch, useSearchParams } from 'react-router-dom';
import { EmptyState, Page, TabBar } from '../components/ui';
import { Barrio } from './personas/Barrio';
import { Oportunidades } from './personas/Oportunidades';
import { Referentes } from './personas/Referentes';
import { Comunidad } from './personas/Comunidad';
import './personas/personas.css';

type Tab = 'barrio' | 'oportunidades' | 'referentes' | 'comunidad';

const TABS: readonly { value: Tab; label: string }[] = [
  { value: 'barrio', label: 'Barrio' },
  { value: 'oportunidades', label: 'Oportunidades' },
  { value: 'referentes', label: 'Referentes' },
  { value: 'comunidad', label: 'Comunidad' },
];

function readTab(value: string | null): Tab {
  return value === 'oportunidades' || value === 'referentes' || value === 'comunidad' ? value : 'barrio';
}

/**
 * /personas: Barrio (the people of the network), Oportunidades and Referentes. The person card
 * (/personas/:contactId) is the nested route: next to the list from 1100px, its own screen below.
 */
export function Personas() {
  const [params, setParams] = useSearchParams();
  const match = useMatch('/personas/:contactId');
  const contactId = match?.params.contactId ?? '';
  const tab = contactId ? 'barrio' : readTab(params.get('pestana'));

  // Each tab starts clean: the Barrio filters do not apply to the other two.
  const choose = (next: Tab) => setParams(next === 'barrio' ? {} : { pestana: next });

  return (
    <div className={contactId ? 'personas has-detail' : 'personas'}>
      <Page title="Personas">
        <div className="personas-tabs">
          <TabBar label="Personas" tabs={TABS} value={tab} onChange={choose} idPrefix="personas" />
        </div>
        <div id={`personas-${tab}-panel`} role="tabpanel" aria-labelledby={`personas-${tab}`} className="personas-panel">
          {tab === 'barrio' ? (
            <div className="split list-detail personas-split">
              <div className="personas-list">
                <Barrio selectedId={contactId} />
              </div>
              <div className="personas-detail">
                {contactId ? (
                  <Outlet />
                ) : (
                  <div className="personas-placeholder">
                    <EmptyState title="Elige a alguien de la lista">Verás su recorrido, el siguiente paso, por qué encaja y tus notas.</EmptyState>
                  </div>
                )}
              </div>
            </div>
          ) : null}
          {tab === 'oportunidades' ? <Oportunidades /> : null}
          {tab === 'referentes' ? <Referentes /> : null}
          {tab === 'comunidad' ? <Comunidad /> : null}
        </div>
      </Page>
    </div>
  );
}
