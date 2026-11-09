import type { ProfileAction, ProfileProposal, ProfileSection } from '../api/perfil';
export const PROFILE_ACTION_LABELS: Record<ProfileAction, string> = {
  prepare_assets: 'Generar fotos y banner', accept: 'Aceptar propuesta', adjust: 'Pedir ajuste', later: 'Más tarde', decline: 'No lo haré',
  applied: 'Hecho, lo apliqué', changed: 'Lo cambié con otro texto', choose_A: 'Elegir A', choose_B: 'Elegir B', verify: 'Comprobar por relectura',
};
export const PROFILE_ASSET_LABELS: Record<string, string> = {
  A: 'Foto A · grises', B: 'Foto B · color', banner: 'Banner', mobile_A: 'Preview móvil · A', mobile_B: 'Preview móvil · B',
  desktop_A: 'Preview escritorio · A', desktop_B: 'Preview escritorio · B',
};
export const PROFILE_UNREADABLE = 'No pude leer tu versión actual; compárala tú con esta recomendación nueva.';
export const profileQuestions = (proposal: ProfileProposal) => proposal.sections.flatMap((row) =>
  row.missing.map((question) => ({ ...question, section: row.id, title: row.title })));
export const profileAvailability = (proposal: ProfileProposal) =>
  `Secciones listas: ${proposal.sections.filter((row) => row.readiness === 'ready').length} · Assets descargables: ${proposal.assets.filter((asset) => ['A', 'B', 'banner'].includes(asset.kind)).length}`;
export function applicationLabel(section: ProfileSection): string {
  if (section.application === 'checked') return 'Comprobado';
  if (section.application === 'applied') return section.id === 'headline'
    ? 'Aplicado por Gustavo, pendiente de comprobar'
    : 'Aplicado por Gustavo; comprobación automática no disponible';
  if (section.decision === 'declined') return 'No lo haré';
  if (section.readiness === 'blocked') return 'Pendiente de información o fundamento';
  if (section.readiness === 'needs_input') return section.copy ? 'Copy preparado; faltan tus datos' : 'Faltan tus datos';
  if (section.decision === 'accepted') return 'Aceptado; pendiente de aplicar';
  return 'Pendiente de revisar';
}
export const needsProfileNote = (action: ProfileAction) => ['adjust', 'decline', 'changed'].includes(action);
export function sectionActions(section: ProfileSection, proposal: ProfileProposal): ProfileAction[] {
  if (proposal.assets_pending) return [];
  if (['queued', 'running', 'cancelled', 'superseded'].includes(proposal.state)) return [];
  const result: ProfileAction[] = ['adjust', 'decline'];
  if (section.id === 'photo' && section.readiness === 'ready' && proposal.photo_choice) result.unshift(proposal.photo_choice === 'A' ? 'choose_B' : 'choose_A');
  if (section.readiness !== 'ready') return result;
  if (section.id === 'photo' && !proposal.photo_choice) {
    return ['choose_A', 'choose_B', ...result];
  }
  if (section.decision !== 'accepted') return ['accept', ...result];
  if (section.action === 'keep' || section.action === 'not_applicable') return result;
  if (section.application === 'pending') return ['applied', ...(section.copy ? ['changed' as const] : []), ...result];
  if (section.application === 'applied' && section.id === 'headline') return ['verify', ...result];
  return result;
}
