import { publishAsapLines } from './capturas';
import { photoPatch } from './galeria';
import { pieceVetoable } from './piece';
import { reviewLines } from './imagenes';

describe('image workflow contract', () => {
  it.each(['no', 'auto', 'si'] as const)('patches only the changed choice (%s)', (ai_edit) => {
    expect(photoPatch({ note: 'Demo', ai_edit }, ' Demo ', ai_edit)).toEqual({});
    expect(photoPatch({ note: 'Demo', ai_edit: ai_edit === 'no' ? 'si' : 'no' }, 'Demo', ai_edit)).toEqual({ ai_edit });
  });

  it('keeps urgency evidence and conditions, without inventing a date or an intention', () => {
    expect(publishAsapLines({ publish_asap: false, publish_asap_evidence: 'Pronto' })).toEqual([]);
    expect(publishAsapLines({ publish_asap: true, publish_asap_expected_slot: null, publish_asap_reason: 'Máquina pausada', publish_asap_evidence: 'Publícalo pronto' }))
      .toEqual(['Saldrá lo antes posible · fecha por confirmar', 'Máquina pausada', '«Publícalo pronto»']);
    expect(publishAsapLines({ publish_asap: true, publish_asap_expected_slot: 'bad date' })[0]).toContain('fecha por confirmar');
  });

  it('never labels a fixed card or an unfinished check as a passed dynamic review', () => {
    expect(reviewLines({ ok: true, mode: 'fixed_brand_card' })).toEqual(['Plantilla fija de marca; sin revisión visual dinámica.']);
    expect(reviewLines({ started: true })).toEqual(['Comprobación en curso']);
    expect(reviewLines({ ok: false, reasons: ['Se alteró un nombre'] })).toEqual(['Comprobación no aprobada', 'Se alteró un nombre']);
  });
});


it('ends the whole-piece veto at the scheduled time and while executing', () => {
  const scheduled_for = '2026-11-10T13:30:00Z';
  const piece = { scheduled_for, action: { id: 'a', state: 'approved' as const, payload_hash: 'text-and-media' } };
  const deadline = Date.parse(scheduled_for);
  expect(pieceVetoable(piece, deadline - 1)).toBe(true);
  expect(pieceVetoable(piece, deadline)).toBe(false);
  expect(pieceVetoable({ ...piece, action: { ...piece.action, state: 'executing' } }, deadline - 1)).toBe(false);
});
