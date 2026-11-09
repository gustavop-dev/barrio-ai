import { PROFILE_HEADLINE, PROFILE_PROPOSAL } from '../fixtures/perfil';
import { applicationLabel, sectionActions } from './perfil';
import { profilePhotoPatch } from './galeria';
import type { PhotoOutput } from '../api/capturas';

describe('Perfil manual and scoped gallery consent', () => {
  it('does not equate acceptance, manual application and a verified reread', () => {
    expect(applicationLabel(PROFILE_HEADLINE)).toBe('Pendiente de revisar');
    expect(applicationLabel({ ...PROFILE_HEADLINE, decision: 'accepted' })).toBe('Aceptado; pendiente de aplicar');
    expect(applicationLabel({ ...PROFILE_HEADLINE, application: 'applied' })).toBe('Aplicado por Gustavo, pendiente de comprobar');
    expect(applicationLabel({ ...PROFILE_HEADLINE, id: 'about', application: 'applied' })).toContain('comprobación automática no disponible');
    expect(applicationLabel({ ...PROFILE_HEADLINE, application: 'checked' })).toBe('Comprobado');
  });
  it('requires a choice of portrait and preserves separate banner approval', () => {
    expect(sectionActions({ ...PROFILE_HEADLINE, id: 'photo' }, PROFILE_PROPOSAL)).toContain('choose_A');
    expect(sectionActions({ ...PROFILE_HEADLINE, id: 'photo' }, PROFILE_PROPOSAL)).toContain('choose_B');
    expect(sectionActions({ ...PROFILE_HEADLINE, id: 'banner' }, { ...PROFILE_PROPOSAL, photo_choice: 'B' })).toContain('accept');
    expect(sectionActions({ ...PROFILE_HEADLINE, readiness: 'blocked' }, PROFILE_PROPOSAL)).not.toContain('accept');
  });
  it('category consent does not enable AI editing for posts', () => {
    const photo = { category: 'posts', profile_edit: false, profile_role: '', ai_edit: 'no' } as PhotoOutput;
    expect(profilePhotoPatch(photo, 'perfil', true, '03')).toEqual({ category: 'perfil', profile_edit: true, profile_role: '03' });
    expect(profilePhotoPatch({ ...photo, category: 'perfil', profile_edit: true }, 'perfil', false, '')).toEqual({ profile_edit: false });
  });
});
