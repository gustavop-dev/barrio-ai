// Pure rules of Resultados › Analítica de LinkedIn: the period of the URL, the custom range against the imported
// days, the period, freshness, error and coverage lines, the daily chart, followers, posts, top lists and demographics.
import { analiticaFixture, serieFixture, SIN_CUENTA } from '../fixtures/analitica';
import {
  audienceLine,
  checkCustomRange,
  contentLine,
  coverageNote,
  dayText,
  demographicBars,
  demographicPct,
  figure,
  followersView,
  freshnessLine,
  hasPayload,
  importErrorNote,
  nearestPoint,
  niceTop,
  periodLine,
  pointText,
  postAsOf,
  postAudienceSplit,
  postFigures,
  postTitle,
  rangeBounds,
  rangeText,
  readMetric,
  readSelection,
  selectionParams,
  selectionQuery,
  serieChart,
  topBars,
  topLine,
} from './analitica';

const NOW = Date.parse('2026-11-13T09:10:00Z');

describe('Analítica de LinkedIn rules', () => {
  it('reads the period of the URL: a preset, or a custom range of two days in order of at most 366 days', () => {
    expect(readSelection({})).toEqual({ kind: 'preset', periodo: '28d' });
    expect(readSelection({ periodo: '90d' })).toEqual({ kind: 'preset', periodo: '90d' });
    expect(readSelection({ periodo: '30d' })).toEqual({ kind: 'preset', periodo: '28d' });
    expect(readSelection({ periodo: '7d', desde: '2026-10-01', hasta: '2026-10-10' })).toEqual({ kind: 'custom', desde: '2026-10-01', hasta: '2026-10-10' });
    expect(readSelection({ desde: '2026-10-10', hasta: '2026-10-01' })).toEqual({ kind: 'preset', periodo: '28d' });
    expect(readSelection({ periodo: '7d', desde: '2025-01-01', hasta: '2026-11-12' })).toEqual({ kind: 'preset', periodo: '7d' });
    expect(readSelection({ desde: '2026-10-01' })).toEqual({ kind: 'preset', periodo: '28d' });
    expect(readSelection({ desde: '2026-02-30', hasta: '2026-03-02' })).toEqual({ kind: 'preset', periodo: '28d' });
  });

  it('turns a selection into the request and the route params (the default preset has no param)', () => {
    expect(selectionQuery({ kind: 'preset', periodo: '14d' })).toEqual({ periodo: '14d' });
    expect(selectionQuery({ kind: 'custom', desde: '2026-10-01', hasta: '2026-10-10' })).toEqual({ desde: '2026-10-01', hasta: '2026-10-10' });
    expect(selectionParams({ kind: 'preset', periodo: '28d' })).toEqual({ periodo: '', desde: '', hasta: '' });
    expect(selectionParams({ kind: 'preset', periodo: '365d' })).toEqual({ periodo: '365d', desde: '', hasta: '' });
    expect(selectionParams({ kind: 'custom', desde: '2026-10-01', hasta: '2026-10-10' })).toEqual({ periodo: '', desde: '2026-10-01', hasta: '2026-10-10' });
  });

  it('writes days and ranges in Spanish, with the year once when both share it', () => {
    expect(dayText('2026-11-12')).toBe('12 nov de 2026');
    expect(rangeText('2026-10-16', '2026-11-12')).toBe('del 16 oct al 12 nov de 2026');
    expect(rangeText('2025-11-13', '2026-11-12')).toBe('del 13 nov de 2025 al 12 nov de 2026');
    expect(rangeText('2026-11-12', '2026-11-12')).toBe('el 12 nov de 2026');
    expect([figure(1840), figure(0), figure(null)]).toEqual(['1.840', '0', '—']);
  });

  it('says the period, how fresh the data is and a failed import after the good one', () => {
    const data = analiticaFixture();
    expect(periodLine(data)).toBe('Del 6 nov al 12 nov de 2026 · 7 días (UTC). Se compara con los 7 días anteriores.');
    expect(freshnessLine(data, NOW)).toBe('Actualizado hace 3 h.');
    expect(freshnessLine(data, Date.parse('2026-11-25T09:00:00Z'))).toMatch(/^Actualizado el .+\.$/);
    expect(freshnessLine({ ...data, actualizado: null }, NOW)).toBeNull();
    expect(importErrorNote(data, NOW)).toBeNull();

    const failed = { at: '2026-11-13T07:10:00Z', tipo: 'diaria', kind: 'blocked', error: 'Analítica detenida por el proveedor: LinkedIn pidió verificar la cuenta' };
    expect(importErrorNote({ ...data, ultimo_error: failed }, NOW)).toEqual({
      title: 'La última importación de LinkedIn falló',
      text: 'Analítica detenida por el proveedor: LinkedIn pidió verificar la cuenta. Fue hace 2 h; las cifras son de la última importación que salió bien.',
    });
    expect(importErrorNote({ ...data, actualizado: null, ultimo_error: failed }, NOW)?.text).toBe('Analítica detenida por el proveedor: LinkedIn pidió verificar la cuenta. Fue hace 2 h.');
  });

  it('notes missing days in the period or in the one before, and a period with none', () => {
    const data = analiticaFixture();
    expect(coverageNote(data)).toBeNull();
    const partial = { ...data.totales, impressions: { ...data.totales.impressions, days_with_data: 5, comparable: false } };
    expect(coverageNote({ ...data, totales: partial })).toBe('Hay datos de 5 de 7 días: las cifras suman solo esos días y no se comparan con el periodo anterior.');
    const before = { ...data.totales, impressions: { ...data.totales.impressions, comparable: false, delta: null } };
    expect(coverageNote({ ...data, totales: before })).toBe('El periodo anterior (del 30 oct al 5 nov de 2026) no tiene todos sus días importados: las cifras no se comparan.');
    const none = { ...data.totales, impressions: { ...data.totales.impressions, value: null, days_with_data: 0, comparable: false } };
    expect(coverageNote({ ...data, totales: none })).toBe('Este periodo no tiene días importados de LinkedIn. Hay datos del 10 oct de 2025 al 12 nov de 2026.');
  });

  it('checks a custom range: AAAA-MM-DD, inside the imported days, in order and of at most 366 days', () => {
    const bounds = rangeBounds(analiticaFixture().limites, NOW);
    expect(bounds).toEqual({ min: '2025-10-10', max: '2026-11-12' });
    expect(checkCustomRange('2026-10-01', '2026-10-10', bounds)).toEqual({ desde: null, hasta: null, rango: null, ok: true });
    expect(checkCustomRange(' 2026-10-01 ', '2026-10-10', bounds).ok).toBe(true);
    const format = 'Escribe la fecha como AAAA-MM-DD.';
    expect(checkCustomRange('2026-1-01', '', bounds)).toEqual({ desde: format, hasta: format, rango: null, ok: false });
    expect(checkCustomRange('2026-02-30', '2026-03-02', bounds).desde).toBe(format);
    const outside = 'Elige un día entre el 10 oct de 2025 y el 12 nov de 2026.';
    expect(checkCustomRange('2025-10-09', '2026-11-13', bounds)).toEqual({ desde: outside, hasta: outside, rango: null, ok: false });
    expect(checkCustomRange('2026-10-10', '2026-10-01', bounds)).toEqual({ desde: null, hasta: null, rango: '«Desde» no puede ser posterior a «Hasta».', ok: false });
    expect(checkCustomRange('2025-10-10', '2026-11-12', bounds).rango).toBe('El periodo tiene como mucho 366 días.');
    expect(checkCustomRange('2025-11-12', '2026-11-12', bounds).ok).toBe(true); // 366 days
    // Before any import: LinkedIn's first day to yesterday (UTC).
    expect(rangeBounds({ primer_dia: null, ultimo_dia: null, linkedin_desde: '2025-10-10' }, NOW)).toEqual({ min: '2025-10-10', max: '2026-11-12' });
  });

  it('draws the days as a line that breaks on a missing day, with a round top and a spoken summary', () => {
    expect([niceTop(0), niceTop(7), niceTop(150), niceTop(2.4), niceTop(1840)]).toEqual([1, 10, 200, 2.5, 2000]);
    const chart = serieChart(serieFixture(), 'impressions');
    expect((({ top, topText, first, last, empty }) => ({ top, topText, first, last, empty }))(chart)).toEqual({ top: 200, topText: '200', first: '2026-11-06', last: '2026-11-12', empty: false });
    expect(chart.points[0]).toEqual({ date: '2026-11-06', value: 100, x: 0, y: 50 });
    expect(chart.points[6]!.x).toBe(100);
    expect(chart.segments).toHaveLength(1);
    expect(chart.summary).toBe('Impresiones por día del 6 nov al 12 nov de 2026: 840 impresiones en total; el día con más fue el 9 nov de 2026, con 150.');

    const gap = serieFixture().map((day) => (day.date === '2026-11-08' ? { ...day, impressions: null } : day));
    const broken = serieChart(gap, 'impressions');
    expect(broken.segments.map((segment) => segment.length)).toEqual([2, 4]);
    expect(broken.points[2]!.y).toBeNull();
    expect(broken.summary).toMatch(/ 1 día sin dato\.$/);

    const empty = serieChart(serieFixture().map((day) => ({ ...day, engagements: null })), 'engagements');
    expect(empty.empty).toBe(true);
    expect(empty.summary).toBe('Interacciones por día del 6 nov al 12 nov de 2026: sin datos.');

    expect(nearestPoint(chart, 0.5)?.date).toBe('2026-11-09');
    expect(nearestPoint(chart, 1.4)?.date).toBe('2026-11-12');
    expect(pointText(chart.points[3]!, 'impressions')).toBe('9 nov de 2026: 150 impresiones');
    const followers = serieChart(serieFixture(), 'new_followers');
    expect([pointText(followers.points[0]!, 'new_followers'), pointText(followers.points[1]!, 'new_followers')]).toEqual(['6 nov de 2026: 1 seguidor nuevo', '7 nov de 2026: 0 seguidores nuevos']);
    expect(pointText(broken.points[2]!, 'impressions')).toBe('8 nov de 2026: sin dato');
    expect([readMetric('engagements'), readMetric('otra')]).toEqual(['engagements', 'impressions']);
  });

  it('gives the followers total with its day and the growth between the first and last capture', () => {
    const view = followersView(analiticaFixture().seguidores);
    expect((({ total, at, growth, tone, spoken }) => ({ total, at, growth, tone, spoken }))(view)).toEqual({
      total: '1.480',
      at: 'según LinkedIn el 13 nov de 2026',
      growth: '+7 desde el 6 nov',
      tone: 'good',
      spoken: '1.480 seguidores, según LinkedIn el 13 nov de 2026, suben 7 desde el 6 nov',
    });
    const down = followersView({ ...analiticaFixture().seguidores, serie: [{ date: '2026-11-06', value: 1490 }, { date: '2026-11-13', value: 1480 }] });
    expect([down.growth, down.tone]).toEqual(['−10 desde el 6 nov', 'bad']);
    const missing = followersView({ total: null, at: null, serie: [], definition: '', unavailable_reason: 'Sin captura del total de seguidores en este periodo.' });
    expect([missing.total, missing.growth, missing.spoken]).toEqual([null, null, 'Seguidores: sin dato. Sin captura del total de seguidores en este periodo.']);
  });

  it('labels the posts with their lifetime figures as of the day LinkedIn gave them', () => {
    const [first, second] = analiticaFixture().posts.publicados;
    expect(postTitle(first!)).toBe('Publicada el 10 nov de 2026 · Imagen');
    expect(postTitle({ published: null, kind: '' })).toBe('Sin fecha de publicación');
    expect(postAsOf(first!)).toBe('Desde que se publicó, al 13 nov de 2026');
    expect(postFigures(first!).slice(0, 3)).toEqual([
      { key: 'impressions', label: 'Impresiones', text: '1.840' },
      { key: 'members_reached', label: 'Alcanzados', text: '1.210' },
      { key: 'reactions', label: 'Reacciones', text: '41' },
    ]);
    expect(postFigures(second!).find((item) => item.key === 'members_reached')?.text).toBe('—');
    expect(postAudienceSplit(first!)).toBe('De tu red 62,5 % · fuera 37,5 %');
    expect(postAudienceSplit(second!)).toBeNull();
  });

  it("lists LinkedIn's top posts and the demographics with «< 1 %» and their own range", () => {
    const data = analiticaFixture();
    const top = data.posts.top_linkedin!;
    expect(topBars(top.por_interacciones)).toEqual([
      { key: 'urn:li:activity:7000000000000000001-0', label: 'Post del 10 nov', value: 52 },
      { key: 'urn:li:activity:7000000000000000002-1', label: 'Post del 7 nov', value: 14 },
    ]);
    expect(topBars(top.por_interacciones, 1)).toHaveLength(1);
    expect(topLine(top)).toBe('Según LinkedIn, del 6 nov al 12 nov de 2026.');

    expect([demographicPct({ pct: 18.5, below: false }), demographicPct({ pct: 1, below: true }), demographicPct({ pct: null, below: false })]).toEqual(['18,5 %', '< 1 %', '—']);
    expect(demographicBars(data.demografia.audiencia!.groups[0]!).map((bar) => [bar.label, bar.display])).toEqual([
      ['Fundador', '18,5 %'],
      ['Ingeniero de software', '12 %'],
      ['Gerente de producto', '< 1 %'],
    ]);
    expect(audienceLine(data.demografia.audiencia!)).toBe('Tus seguidores, según LinkedIn el 13 nov de 2026.');
    const content = data.demografia.contenido!;
    expect(contentLine(content)).toBe('Quienes vieron tus publicaciones del 6 nov al 12 nov de 2026.');
    expect(contentLine({ ...content, desde: '2026-10-16', exacto: false })).toBe(
      'Quienes vieron tus publicaciones del 16 oct al 12 nov de 2026: el rango importado más cercano, no exactamente este periodo.',
    );
  });

  it('tells the answer without an account from the full one', () => {
    expect(hasPayload(SIN_CUENTA)).toBe(false);
    expect(hasPayload(analiticaFixture())).toBe(true);
    expect(hasPayload(undefined)).toBe(false);
  });
});
