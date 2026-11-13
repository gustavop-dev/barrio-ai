// Pure rules of the Personas screens shared by both apps: funnel counts, the person card texts, the team's read
// of a conversation, the opportunity form and the referents.
import { contactFixture, conversationFixture, opportunityFixture, redSummaryFixture, referentFixture } from '../fixtures/personas';
import {
  leadDoubtText,
  nextActionText,
  nextStepView,
  opportunityErrors,
  opportunityInput,
  personMeta,
  referentMeta,
  stageCount,
  stageGroups,
  suggestedModality,
  teamRead,
  totalCount,
  type OpportunityDraft,
} from './barrio';

const draft = (extra: Partial<OpportunityDraft> = {}): OpportunityDraft => ({
  mode: 'red',
  picked: null,
  personName: '',
  company: '',
  modality: '',
  channel: 'linkedin',
  stage: 'conversacion',
  attribution: '',
  need: '',
  budget: '',
  dedication: '',
  nextAction: '',
  nextAt: '',
  notes: '',
  ...extra,
});

describe('Opportunity dates in Bogotá', () => {
  beforeEach(() => { jest.useFakeTimers(); });
  afterEach(() => { jest.useRealTimers(); });

  it.each([
    ['2026-11-11T23:59:59Z', '2026-11-12T20:00:00Z', 'mañana'],
    ['2026-11-12T00:00:00Z', '2026-11-12T20:00:00Z', 'mañana'],
    ['2026-11-12T02:00:00Z', '2026-11-12T15:00:00-05:00', 'mañana'],
    ['2026-11-12T03:00:00Z', '2026-11-12T20:00:00Z', 'mañana'],
    ['2026-11-12T04:59:59Z', '2026-11-12T20:00:00Z', 'mañana'],
    ['2026-11-12T05:00:00Z', '2026-11-12T20:00:00Z', 'hoy'],
    ['2026-11-13T05:00:00Z', '2026-11-12T20:00:00Z', 'ayer'],
    ['2026-11-11T15:00:00Z', '2026-11-12T02:00:00Z', 'hoy'],
    ['2026-11-12T02:00:00Z', '2026-11-12', 'mañana'],
    ['2026-11-12T02:00:00Z', '2026-12-01T02:00:00Z', '30 nov'],
  ])('at %s, the action for %s says %s', (now, nextAt, label) => {
    jest.setSystemTime(new Date(now));
    expect(nextActionText({ next_action: 'Enviar la propuesta revisada', next_action_at: nextAt }))
      .toBe(`Enviar la propuesta revisada · ${label}`);
  });

  it.each([null, '', 'not-a-date'])('omits an absent or invalid action date (%s)', (nextAt) => {
    jest.setSystemTime(new Date('2026-11-12T02:00:00Z'));
    expect(nextActionText({ next_action: 'Enviar la propuesta revisada', next_action_at: nextAt }))
      .toBe('Enviar la propuesta revisada');
  });
});

describe('Personas rules', () => {
  it('counts the funnel chips; «En conversación» stays null until the inbox arrives', () => {
    const summary = redSummaryFixture();
    expect(totalCount(summary)).toBe(51);
    expect(stageCount(summary, 'conversation')).toBeNull();
    expect(stageCount(summary, 'opportunity')).toBe(1);
    expect(stageCount(summary, 'fit')).toBe(9);
    expect(stageCount(undefined, 'fit')).toBeUndefined();
  });

  it('adds the followers to the header line and explains a doubt of the lead', () => {
    expect(personMeta(contactFixture('c-1', { network_distance: '', signals: { followers: 980 } }))).toBe('Medellín, Colombia · 980 seguidores');
    expect(personMeta(contactFixture('c-1', { network_distance: '', signals: {} }))).toBe('Medellín, Colombia');
    expect(leadDoubtText(contactFixture('c-1'))).toBeNull();
    const doubt = { capability: 'RED-01', reasons: [], decided_at: '2026-11-12T15:00:00Z', until: '2026-12-12T15:00:00Z' };
    expect(leadDoubtText(contactFixture('c-1', { lead_doubt: doubt }))).toBe(
      'El clasificador dice que encaja, pero el líder frenó el follow. Descansa hasta el 12 dic salvo que confirmes que encaja.',
    );
    expect(leadDoubtText(contactFixture('c-1', { lead_doubt: { ...doubt, capability: 'RED-02', reasons: ['Riesgo alto'] } }))).toContain('frenó la invitación (Riesgo alto)');
  });

  it('writes the header line and the next step with its owner', () => {
    expect(personMeta(contactFixture('c-1', { is_following: true, network_distance: 'FIRST_DEGREE' }))).toBe('Medellín, Colombia · 1.er grado · Lo sigues');
    const step = nextStepView(contactFixture('c-1', { your_turn: true, next_step: { owner: 'equipo', text: 'Invitar', at: '2026-11-07T15:00:00Z', action: { id: 'a', capability: 'RED-02', state: 'approved' } } }));
    expect(step).toEqual({ mine: true, label: 'Siguiente paso · Te toca', text: 'Invitar', at: 'Para el 7 nov', action: 'Invitación sin nota · Aprobada' });
    expect(nextStepView(contactFixture('c-1', { next_step: { owner: 'equipo', text: 'Seguir', at: null } }))?.label).toBe('Siguiente paso · Equipo');
  });

  it('reads the conversation: chips, probabilities and the modality to prefill', () => {
    const conversation = conversationFixture();
    expect(teamRead(conversation.assessment)).toEqual({
      chips: [
        { text: 'Posible oportunidad · ProjectApp', tone: 'ok', badge: true },
        { text: 'Espera tu respuesta', tone: 'warn', badge: true },
      ],
      numbers: 'Oportunidad 86 % · Espera respuesta 81 % · Venta o spam 4 %',
    });
    expect(teamRead(null)).toBeNull();
    const contact = contactFixture('c-1', { classification: { modality: 'alianzas' }, conversation });
    expect(suggestedModality(contact)).toBe('projectapp');
  });

  it('checks the required fields of the opportunity form and builds its body', () => {
    expect(opportunityErrors(draft())).toEqual({ person: 'Elige a alguien de Personas.', modality: 'Elige la modalidad.', attribution: 'Elige cómo llegó.' });
    expect(opportunityErrors(draft({ mode: 'fuera' })).person).toBe('Escribe el nombre de la persona.');
    const body = opportunityInput(draft({ mode: 'fuera', personName: ' Mario ', modality: 'projectapp', attribution: 'lo_dijo', nextAt: '2026-11-12' }));
    expect(body).toMatchObject({ contact: null, person_name: 'Mario', modality: 'projectapp', attribution: 'lo_dijo' });
    expect(String(body.next_action_at)).toMatch(/^2026-11-1[12]T/);
  });

  it('groups the opportunities most advanced first and keeps the empty stages while dragging', () => {
    const items = [opportunityFixture('o-1'), opportunityFixture('o-2', { stage: 'conversacion' }), opportunityFixture('o-3', { stage: 'sin_acuerdo' })];
    expect(stageGroups(items).map((group) => group.stage)).toEqual(['necesidad', 'conversacion']);
    expect(stageGroups(items, true).map((group) => group.stage)).toEqual(['acuerdo', 'propuesta', 'reunion', 'cualificada', 'necesidad', 'conversacion']);
  });

  it('says when a referent was observed and how many people came from it', () => {
    const now = Date.parse('2026-11-07T15:00:00Z');
    expect(referentMeta(referentFixture('r-1', { last_observed_at: '2026-10-26T10:00:00Z', contacts_count: 1 }), now)).toBe('Observado hace 12 días · 1 persona del barrio salió de sus posts');
    expect(referentMeta(referentFixture('r-1', { contacts_count: 0 }), now)).toBe('Aún sin observar · 0 personas del barrio salieron de sus posts');
  });
});
