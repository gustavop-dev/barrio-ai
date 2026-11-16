// Pure rules of the monthly review shared by both apps: the partial line, the verdict and state chips, the pending
// sentence and the tab's name, what a decided change says, the toasts, «Generar ahora» and the automatic run.
import { monthlyGenerateFixture, monthlyReviewFixture, strategyChangeFixture } from '../fixtures/revision';
import {
  automaticSentence,
  baselineText,
  changeBadge,
  changeToast,
  decidedSentence,
  emptyText,
  evidenceLines,
  generateCost,
  generatingText,
  isChangeEndpoint,
  outcomeFigures,
  partialSentence,
  pendingSentence,
  reviewItems,
  reviewLines,
  reviewPhrase,
  revisionTabLabel,
  verdictBadge,
} from './revisionMensual';

describe('monthly review rules', () => {
  it('says why a review is partial, only when it is', () => {
    expect(partialSentence(monthlyReviewFixture())).toBeNull();
    expect(partialSentence({ partial: true, semanas_con_datos: 2, semanas_del_mes: 4 })).toBe(
      'Parcial: solo 2 de 4 semanas tienen posts medidos y hacen falta 4 para comparar el mes. Léela como pistas, no como conclusiones.',
    );
    expect(partialSentence({ partial: true, semanas_con_datos: 0, semanas_del_mes: 1 })).toContain('solo 0 de 1 semana tiene posts medidos');
    expect(partialSentence({ partial: true, semanas_con_datos: null, semanas_del_mes: null })).toContain('menos de cuatro semanas tienen posts medidos');
  });

  it('reads an unknown verdict as «Sin dato»', () => {
    expect(verdictBadge('se_conserva')).toEqual({ tone: 'ok', label: 'Se conserva' });
    expect(verdictBadge('empeoro')).toEqual({ tone: 'bad', label: 'Empeoró' });
    expect(verdictBadge('sin_dato')).toEqual({ tone: 'muted', label: 'Sin dato' });
    expect(verdictBadge('mejoro_mucho')).toEqual({ tone: 'muted', label: 'Sin dato' });
    expect(verdictBadge(undefined)).toEqual({ tone: 'muted', label: 'Sin dato' });
  });

  it('counts the changes that wait for him, in the review and in the tab', () => {
    expect(pendingSentence(monthlyReviewFixture())).toBe('1 cambio de estrategia espera tu decisión.');
    expect(pendingSentence(monthlyReviewFixture({ changes: [strategyChangeFixture(), strategyChangeFixture({ id: 'ch-2' })] }))).toBe('2 cambios de estrategia esperan tu decisión.');
    expect(pendingSentence(monthlyReviewFixture({ changes: [strategyChangeFixture({ state: 'aprobado', can_decide: false })] }))).toBe('Ningún cambio espera tu decisión.');
    expect(pendingSentence(monthlyReviewFixture({ changes: [] }))).toBe('Este mes no propone cambios de estrategia.');
    expect([revisionTabLabel(2), revisionTabLabel(0), revisionTabLabel(undefined)]).toEqual(['Revisión mensual · 2', 'Revisión mensual', 'Revisión mensual']);
  });

  it('keeps only the entries with text, and survives fields missing in an older review', () => {
    const review = monthlyReviewFixture({ lo_que_no: [{ texto: '', cifra: 'x: 1' }, { texto: 'Bajaron las respuestas.', cifra: 'y: 2' }] });
    expect(reviewItems(review, 'lo_que_no')).toEqual([{ texto: 'Bajaron las respuestas.', cifra: 'y: 2' }]);
    expect(reviewItems({ ...review, lo_que_paso: undefined } as unknown as typeof review, 'lo_que_paso')).toEqual([]);
    expect(reviewLines(['Uno', ' ', 2, 'Dos'])).toEqual(['Uno', 'Dos']);
    expect(reviewLines(null)).toEqual([]);
  });

  it('describes a change: its evidence, its baseline and its state', () => {
    expect(evidenceLines(strategyChangeFixture())).toEqual([{ cifra: 'por_tipo.caso.mediana_impresiones_72h: 1180', comparado: 'metricas.mediana_impresiones_72h.mes: 590' }]);
    expect(evidenceLines(strategyChangeFixture({ evidence: null as unknown as [] }))).toEqual([]);
    expect(baselineText(strategyChangeFixture())).toBe('Valor del mes revisado: 590');
    expect(baselineText(strategyChangeFixture({ baseline: null }))).toBeNull();
    expect(changeBadge(strategyChangeFixture())).toEqual({ tone: 'warn', label: 'Por decidir' });
    expect(changeBadge(strategyChangeFixture({ state: 'caducado' as never, state_label: 'Caducado' }))).toEqual({ tone: 'muted', label: 'Caducado' });
  });

  it('says when a change was decided and what it did', () => {
    expect(decidedSentence(strategyChangeFixture())).toBeNull();
    expect(decidedSentence(strategyChangeFixture({ state: 'aprobado', decided_at: '2026-11-03T15:00:00Z' }))).toMatch(/^Lo aprobaste el .+\. Entró en la orientación del equipo con este texto:$/);
    expect(decidedSentence(strategyChangeFixture({ state: 'rechazado', decided_at: null }))).toBe('Lo rechazaste. El analista no lo volverá a proponer igual en los próximos tres meses.');
    expect(decidedSentence(strategyChangeFixture({ state: 'revertido', decided_at: '2026-11-03T15:00:00Z', reverted_at: '2026-11-10T15:00:00Z' }))).toMatch(
      /^Lo aprobaste el .+ y lo revertiste el .+: ya no está en la orientación\.$/,
    );
    expect(outcomeFigures({ antes: 590, despues: 720 })).toBe('Antes: 590 · Después: 720');
    expect(outcomeFigures({ antes: 590, despues: null })).toBe('Antes: 590 · Después: —');
    expect(outcomeFigures({ antes: null, despues: null })).toBeNull();
  });

  it('confirms each decision; a revert that did not find its text says so', () => {
    expect(changeToast('aprobar')).toBe('Cambio aprobado. El equipo lo usa desde su próxima tarea.');
    expect(changeToast('rechazar')).toBe('Cambio rechazado');
    expect(changeToast('revertir', { found: true })).toBe('Cambio revertido: ya no está en la orientación.');
    expect(changeToast('revertir', { found: false, message: 'La orientación ya no tenía ese texto.' })).toBe('La orientación ya no tenía ese texto.');
    expect(changeToast('revertir', { found: false, message: null })).toMatch(/^La orientación ya no contenía este cambio/);
  });

  it('recognises the decision endpoints of a change', () => {
    const { endpoints } = strategyChangeFixture();
    expect(isChangeEndpoint(endpoints.approve)).toBe(true);
    expect(isChangeEndpoint(endpoints.approve, 'aprobar')).toBe(true);
    expect(isChangeEndpoint(endpoints.approve, 'rechazar')).toBe(false);
    expect(isChangeEndpoint(endpoints.reject, 'rechazar')).toBe(true);
    expect(isChangeEndpoint(endpoints.revert, 'revertir')).toBe(true);
    expect(isChangeEndpoint('/api/v1/operador/actions/a-1/approve')).toBe(false);
    expect(isChangeEndpoint(undefined)).toBe(false);
  });

  it('says when the next review arrives only while that run is ahead', () => {
    const offer = monthlyGenerateFixture({ automatic_at: '2026-12-07T13:30:00Z' });
    const before = Date.parse('2026-11-16T12:00:00Z');
    expect(automaticSentence(offer, before)).toMatch(/^ El analista la escribe el primer lunes de cada mes a las .+\. La próxima llega el lunes 7 de diciembre\.$/);
    expect(automaticSentence(offer, Date.parse('2026-12-08T12:00:00Z'))).not.toContain('La próxima');
    expect(automaticSentence({ automatic: false, automatic_at: '2026-12-07T13:30:00Z' }, before)).toBe('');
    expect(automaticSentence({ automatic: true, automatic_at: null }, before)).toBe('');
    expect(emptyText(offer, before)).toMatch(/^Una vez al mes el analista compara el mes con el anterior.*Necesita alrededor de un mes de datos\. El analista la escribe/);
  });

  it('words «Generar ahora» with the month and its cost', () => {
    const offer = monthlyGenerateFixture();
    expect(reviewPhrase(offer.label)).toBe('la revisión de octubre de 2026');
    expect(generateCost(offer)).toBe('Tiene coste: unos 0,19 USD (como mucho 0,47 USD), del presupuesto de la revisión mensual.');
    expect(generatingText(offer)).toBe('El analista está escribiendo la revisión de octubre de 2026. Tarda unos minutos y aparecerá aquí.');
  });
});
