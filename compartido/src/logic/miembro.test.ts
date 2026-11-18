// The pure logic of Mi perfil, Mi voz and Organización (organizaciones, phase 7), shared by the PWA and the app.
import { organizacionFixture, perfilFixture, vozConfirmadaFixture, vozConPropuestaFixture, vozFixture, yoAltaFixture, yoFixture } from '../fixtures/miembro';
import { ajustesSections, isAjustesSection } from './ajustes';
import {
  fieldCounter,
  hasChanges,
  inOnboarding,
  memberAccounts,
  memberBadges,
  profileIssues,
  profileOrigin,
  profilePatch,
  proposeBlocked,
  revisionLine,
  savedMessage,
  signalRows,
  voiceProgress,
  voiceSentence,
} from './miembro';
import { approvalNoteLabel } from './turno';

describe('Mi perfil', () => {
  const saved = perfilFixture().profile;

  it('checks the limits the server checks', () => {
    expect(profileIssues(saved)).toEqual({});
    expect(profileIssues({ ...saved, name: '' }).name).toBe('No puede quedar vacío.');
    expect(profileIssues({ ...saved, name: 'Ana 2' }).name).toBe('Solo letras, espacios, apóstrofo o guion.');
    expect(profileIssues({ ...saved, name: "María-José O'Neil" })).toEqual({});
    expect(profileIssues({ ...saved, name: 'a'.repeat(61) }).name).toBe('Como mucho 60 caracteres (van 61).');
    expect(profileIssues({ ...saved, role: 'r'.repeat(121) }).role).toBe('Como mucho 120 caracteres (van 121).');
    expect(profileIssues({ ...saved, identity: 'i'.repeat(601) }).identity).toBe('Como mucho 600 caracteres (van 601).');
    expect(profileIssues({ ...saved, company_relation: 'c'.repeat(301) }).company_relation).toBe('Como mucho 300 caracteres (van 301).');
    expect(profileIssues({ ...saved, limits: '   ' }).limits).toBe('No puede quedar vacío.');
    // Optional texts may be empty.
    expect(profileIssues({ ...saved, role: '', identity: '', company_relation: '' })).toEqual({});
  });

  it('sends only what changed, trimmed', () => {
    expect(profilePatch(saved, saved)).toEqual({});
    expect(hasChanges(profilePatch(saved, saved))).toBe(false);
    // Only spaces around the same text is not a change.
    expect(profilePatch(saved, { ...saved, identity: ` ${saved.identity} ` })).toEqual({});
    const patch = profilePatch(saved, { ...saved, role: ' CTO y cofundadora ', personal_startups: true });
    expect(patch).toEqual({ role: 'CTO y cofundadora', personal_startups: true });
    expect(hasChanges(patch)).toBe(true);
  });

  it('says what saving did, counts and reads the history', () => {
    expect(savedMessage(true)).toBe('Guardado.');
    expect(savedMessage(false)).toBe('Sin cambios: ya tenías esos valores.');
    expect(fieldCounter('hola', 600)).toBe('4 / 600');
    const [newest, oldest] = perfilFixture().history;
    expect(revisionLine(newest!)).toMatch(/^#2 · .+ · ana · desde la app · cambió: Cómo te presentas$/);
    expect(revisionLine(oldest!)).toMatch(/^#1 · .+ · gustavo · en el alta · cambió: Relación con la empresa, Nombre$/);
    expect(revisionLine({ ...newest!, by: null, source: 'otra', changed: [] })).toMatch(/ · sistema · otra · cambió: —$/);
    expect(profileOrigin({ own: false })).toBe('Aún no guardaste tu perfil: lo que ves son los valores iniciales.');
    expect(profileOrigin({ own: true })).toBeNull();
  });
});

describe('Mi voz', () => {
  it('says what each state means and how far the sample is', () => {
    expect(voiceSentence(vozFixture())).toContain('marca tus borradores «Voz provisional»');
    expect(voiceSentence(vozConfirmadaFixture())).toBe('El equipo escribe con tu voz confirmada (versión 2).');
    expect(voiceSentence({ state: 'inicial', version: null })).toBe('El equipo escribe con la voz inicial de la instalación.');
    expect(voiceProgress(vozFixture().signals)).toBe('7 de 12 textos aprobados o editados');
    expect(signalRows(vozFixture().signals).map((row) => [row.kind, row.count])).toEqual([
      ['aprobado', 5],
      ['editado', 2],
      ['rechazado', 0],
      ['respuesta', 0],
      ['captura', 3],
    ]);
  });

  it('explains why a proposal cannot be asked for yet', () => {
    expect(proposeBlocked(vozConfirmadaFixture())).toBeNull();
    expect(proposeBlocked(vozFixture())).toBe('Faltan 5 textos tuyos aprobados o editados para pedir una propuesta.');
    expect(proposeBlocked(vozConPropuestaFixture())).toBe('Hay una propuesta esperando tu decisión.');
    expect(proposeBlocked(vozFixture({ learning_enabled: false }))).toBe('El aprendizaje de la voz está apagado en el servidor.');
  });
});

describe('Organización y alta', () => {
  it('adds Mi perfil and Mi voz for a member and Organización for the admin, before «Lo que el equipo sabe»', () => {
    const ids = (yo: Parameters<typeof ajustesSections>[0]) => ajustesSections(yo).map((section) => section.id);
    expect(ids(null)).not.toContain('perfil');
    expect(ids({ member: null, is_admin: false })).not.toContain('voz');
    const member = ids(yoAltaFixture());
    expect(member).toContain('perfil');
    expect(member).toContain('voz');
    expect(member).not.toContain('organizacion');
    const admin = ids(yoFixture());
    expect(admin.indexOf('organizacion')).toBe(admin.indexOf('sabe') - 1);
    expect(['perfil', 'voz', 'organizacion'].every(isAjustesSection)).toBe(true);
  });

  it('knows a member in onboarding', () => {
    expect(inOnboarding(yoAltaFixture())).toBe(true);
    expect(inOnboarding(yoFixture())).toBe(false);
    expect(inOnboarding(null)).toBe(false);
  });

  it('shows each member’s state and accounts, nothing else', () => {
    const [gustavo, ana] = organizacionFixture().members;
    expect(memberBadges(gustavo!).map((badge) => badge.text)).toEqual(['Activo', 'Administrador', 'Voz inicial']);
    expect(memberBadges(ana!).map((badge) => badge.text)).toEqual(['Inactivo', 'Voz provisional']);
    expect(memberAccounts(ana!)).toBe('API oficial: conectada · Navegador: sin conectar');
  });

  it('names the note of an approval by what it sends', () => {
    expect(approvalNoteLabel({ capability: 'RED-02' })).toBe('Nota de la invitación');
    expect(approvalNoteLabel({ capability: 'RED-01' })).toBe('Nota');
  });
});
