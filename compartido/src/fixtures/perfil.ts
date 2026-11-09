import type { ProfileProposal, ProfileSection } from '../api/perfil';
import type { TurnoCard } from '../api/types';
export const PROFILE_CARD: TurnoCard = {
  id: 'perfil:profile-qa', type: 'perfil', profile_id: 'profile-qa', priority: 'cuando_puedas', state: 'nueva',
  critical: false, tone: 'info', agent: 'perfil', agent_label: 'Perfil', title: 'Propuesta de perfil',
  body: 'Cambios por sección. Tú decides y los aplicas en LinkedIn.', deadline: null, created_at: null, actions: [],
};
export const PROFILE_HEADLINE: ProfileSection = {
  id: 'headline', title: 'Titular', action: 'change', copy: 'Helping product teams build useful software',
  audience: 'Product teams', benefit: 'Useful product decisions', reason: 'Lead with usefulness for the visitor.',
  citations: [{ unit_id: 'LI-02-V015-K03', reason: 'Start with how you help.' }], evidence: ['qa:offer'], steps: ['Open your introduction and paste the headline.'],
  missing: [], readiness: 'ready', decision: 'pending', application: 'pending', current: null, limit: 0, limit_source: '',
};
export const PROFILE_PROPOSAL: ProfileProposal = {
  id: 'profile-qa', version: 1, revision: 1, mode: 'full', state: 'partial', sections: [PROFILE_HEADLINE],
  photo_choice: '', findings: [], microphone_note: 'Composición estilizada con micrófono; no documenta una charla o evento real.',
  markdown: '# Propuesta de perfil\n\n[LI-02-V015-K03] Start with how you help.\n', document_url: '/api/v1/perfil/profile-qa/documento',
  references_valid: true, references: [], assets: [],
};
