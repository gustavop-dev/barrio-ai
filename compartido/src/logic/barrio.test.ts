// Pure rules of the Personas screens shared by both apps: funnel counts, the person card texts, the team's read
// of a conversation, the opportunity form and the referents.
import { contactFixture, conversationFixture, opportunityFixture, redSummaryFixture, referentFixture } from '../fixtures/personas';
import {
  nextStepView,
  noResultsTitle,
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

describe('Personas rules', () => {
  it('counts the funnel chips; «En conversación» stays null until the inbox arrives', () => {
    const summary = redSummaryFixture();
    expect(totalCount(summary)).toBe(51);
    expect(stageCount(summary, 'conversation')).toBeNull();
    expect(stageCount(summary, 'opportunity')).toBe(1);
    expect(stageCount(summary, 'fit')).toBe(9);
    expect(stageCount(undefined, 'fit')).toBeUndefined();
    expect(noResultsTitle({ stage: 'fit', q: '', role: '', modality: '', source: '' })).toBe('Nadie en «Encaja» ahora mismo');
    expect(noResultsTitle({ stage: 'fit', q: 'luc', role: '', modality: '', source: '' })).toBe('Nadie coincide con estos filtros');
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
