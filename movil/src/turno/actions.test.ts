import { APPROVAL_CARD, CONVERSATION_CARD, DAY_REQUEST_CARD, EXPIRING_CARD, questionCard, UNCERTAIN_CARD, cardFixture } from '@compartido/fixtures/turno';
import type { TurnoCard } from '@compartido/api/types';
import { APPROVED_MESSAGE } from '@compartido/logic/events';
import { cardSummary, cardTitle, hasDetails, modalFor, orderedActions, successMessage, SUMMARY_FITS, swipeIntents, withNote } from './actions';
import { commitSide, dragOffset, pastCommit, revealProgress } from './swipe';

describe('card actions', () => {
  it('asks for a note before resolving an uncertain action, and says what happened', () => {
    const [applied, failed] = UNCERTAIN_CARD.actions;
    expect(modalFor(applied!)).toMatchObject({ title: 'Confirmar que se aplicó', note: 'required', noteLabel: 'Qué comprobaste' });
    expect(modalFor(failed!)).toMatchObject({ title: 'Confirmar que no se aplicó' });
    expect(successMessage(applied!)).toBe('Anotado: se aplicó');
    expect(successMessage(failed!)).toBe('Anotado: no se aplicó');
    expect(cardTitle(UNCERTAIN_CARD)).toBe('Comprueba si salió tu comentario');
  });

  it('closes a conversation without asking, and «No responder» asks for an optional reason', () => {
    const done = CONVERSATION_CARD.actions.find((a) => a.label === 'Hecho, respondí')!;
    const noReply = CONVERSATION_CARD.actions.find((a) => a.label === 'No responder')!;
    expect(modalFor(done)).toBeNull();
    expect(successMessage(done)).toBe('Anotado: respondiste');
    expect(modalFor(noReply)).toMatchObject({ note: 'optional', noteLabel: 'Motivo' });
    expect(successMessage(noReply)).toBe('Anotado: no responderás');
  });

  it('approves at once with the exact version; «Vetar» asks for a note and warns that the person is discarded', () => {
    const [approve, reject] = APPROVAL_CARD.actions;
    expect(modalFor(approve!, APPROVAL_CARD)).toBeNull();
    expect(successMessage(approve!)).toBe(APPROVED_MESSAGE);
    expect(modalFor(reject!, APPROVAL_CARD)).toMatchObject({ title: 'Vetar la acción', note: 'required', noteLabel: 'Nota' });
    expect(modalFor(reject!, APPROVAL_CARD)?.text).toContain('descarta a Laura Prueba para siempre');
    expect(successMessage(reject!)).toBe('Vetada');
    expect(swipeIntents(APPROVAL_CARD).right).toMatchObject({ kind: 'run', label: 'Aprobar' });
    expect(swipeIntents(APPROVAL_CARD).left).toBeNull();
  });

  it('sends the machine its reason as `reason`, everything else as `note`', () => {
    const resume = { label: 'Reanudar', endpoint: '/api/v1/operador/control', body: { paused: false } };
    expect(withNote(resume, 'listo')).toEqual({ action: { ...resume, body: { paused: false, reason: 'listo' } } });
    expect(withNote(UNCERTAIN_CARD.actions[0]!, 'aparece')).toEqual({ action: UNCERTAIN_CARD.actions[0], note: 'aparece' });
    expect(withNote(UNCERTAIN_CARD.actions[0]!, '')).toEqual({ action: UNCERTAIN_CARD.actions[0] });
  });

  it('puts the primary action first', () => {
    expect(orderedActions(CONVERSATION_CARD.actions).map((a) => a.label)[0]).toBe('Abrir en LinkedIn');
    expect(orderedActions([{ label: 'A' }, { label: 'B', primary: true }]).map((a) => a.label)).toEqual(['B', 'A']);
  });
});

describe('swipe intents', () => {
  it('right runs the first request action; links and the opportunity form are left alone', () => {
    expect(swipeIntents(CONVERSATION_CARD).right).toMatchObject({ kind: 'run', label: 'Hecho, respondí' });
    expect(swipeIntents(UNCERTAIN_CARD).right).toMatchObject({ kind: 'run', label: 'Sí, se aplicó' });
    expect(swipeIntents(EXPIRING_CARD).right).toBeNull();
    expect(swipeIntents(cardFixture({ actions: [] }))).toEqual({ right: null, left: null });
  });

  it('a date that cannot be kept is a tap on its button, never a swipe', () => {
    expect(swipeIntents(DAY_REQUEST_CARD)).toEqual({ right: null, left: null });
    const [next, discard] = DAY_REQUEST_CARD.actions;
    expect(successMessage(next!)).toBe('Va al primer día libre');
    expect(successMessage(discard!)).toBe('Idea descartada');
    expect(hasDetails(DAY_REQUEST_CARD)).toBe(true);
  });

  it('left postpones a question («Más tarde»); a question has no «done» swipe', () => {
    expect(swipeIntents(questionCard())).toEqual({ right: null, left: { kind: 'postpone', questionId: 'q1', label: 'Más tarde' } });
    expect(swipeIntents(CONVERSATION_CARD).left).toBeNull();
  });

  it('expired cards cannot be swiped', () => {
    expect(swipeIntents(UNCERTAIN_CARD, true)).toEqual({ right: null, left: null });
  });
});

describe('swipe rules (motion.ts gestures.swipe)', () => {
  const both = { right: true, left: true };
  const width = 300; // commit point at 99 px

  it('commits past a third of the card, or on a fast flick that way', () => {
    expect(commitSide(120, 0, width, both)).toBe('right');
    expect(commitSide(-120, 0, width, both)).toBe('left');
    expect(commitSide(60, 0, width, both)).toBeNull();
    expect(commitSide(40, 1200, width, both)).toBe('right');
    expect(commitSide(-40, -1200, width, both)).toBe('left');
    expect(commitSide(8, 1200, width, both)).toBeNull();
  });

  it('never commits towards a side without an action, and barely moves there', () => {
    expect(commitSide(200, 2000, width, { right: false, left: true })).toBeNull();
    expect(Math.abs(dragOffset(200, width, { right: false, left: true }))).toBeLessThanOrEqual(24);
  });

  it('follows the finger up to the commit point, then resists', () => {
    expect(dragOffset(80, width, both)).toBe(80);
    expect(dragOffset(199, width, both)).toBeCloseTo(99 + 100 * 0.35);
    expect(pastCommit(99, width)).toBe(true);
    expect(revealProgress(0, width)).toBe(0);
    expect(revealProgress(99, width)).toBe(1);
  });
});

describe('collapsed cards (title and a two-line summary; the rest under «Ver más»)', () => {
  it('sums a card up by what it is about: the message, the comment to check, or its body', () => {
    expect(cardSummary(CONVERSATION_CARD)).toBe('“Hola Gustavo, ¿tienes disponibilidad para un proyecto corto de IA en enero?”');
    expect(cardSummary(UNCERTAIN_CARD)).toBe('“Scoping from the decision a feature supports is what keeps the first version small.”');
    expect(cardSummary(APPROVAL_CARD)).toBe('Lidera producto en un marketplace B2B.');
    expect(cardSummary(questionCard())).toBe('Para el post del jueves sobre arquitectura. Sin un caso real, el post se queda en opinión.');
    expect(cardSummary(EXPIRING_CARD)).toBe('El permiso para publicar caduca pronto.');
    expect(cardSummary(cardFixture({ expires_at: '2026-11-20T15:00:00Z', days_left: 1 } as Partial<TurnoCard>))).toMatch(/^El permiso para publicar caduca el .* \(queda 1 día\)\. LinkedIn no deja renovarlo solo\.$/);
  });

  it('offers «Ver más» only when it shows something new', () => {
    expect(hasDetails(CONVERSATION_CARD)).toBe(true);
    expect(hasDetails(UNCERTAIN_CARD)).toBe(true);
    expect(hasDetails(APPROVAL_CARD)).toBe(true);
    expect(hasDetails(cardFixture({ id: 'aviso:corto', type: 'aviso', body: 'Corto.' }))).toBe(false);
    expect(hasDetails(cardFixture({ id: 'aviso:largo', type: 'aviso', body: 'x'.repeat(SUMMARY_FITS + 1) }))).toBe(true);
  });
});
