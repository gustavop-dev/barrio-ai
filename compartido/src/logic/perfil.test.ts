import { PROFILE_HEADLINE, PROFILE_PROPOSAL } from '../fixtures/perfil';
import { applicationLabel, profileAvailability, profileQuestions, sectionActions } from './perfil';
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
  it('keeps ready copy available while facts pending are separate and cannot be applied', () => {
    const pending = { ...PROFILE_HEADLINE, id: 'experience', title: 'Experiencia', readiness: 'needs_input' as const,
      copy: '[exact title] — Built useful software.',
      missing: [{ key: 'perfil.experience.title', question: '¿Cuál fue el cargo exacto?', purpose: 'Completar el cargo.' }] };
    const proposal = { ...PROFILE_PROPOSAL, sections: [PROFILE_HEADLINE, pending] };
    expect(profileAvailability(proposal)).toBe('Secciones listas: 1 · Assets descargables: 0');
    expect(profileQuestions(proposal)[0]).toMatchObject({ section: 'experience', question: '¿Cuál fue el cargo exacto?' });
    expect(applicationLabel(pending)).toBe('Copy preparado; faltan tus datos');
    expect(sectionActions(pending, proposal)).not.toContain('accept');
    expect(sectionActions(pending, proposal)).not.toContain('applied');
    expect(sectionActions(PROFILE_HEADLINE, proposal)).toContain('accept');
  });
});
