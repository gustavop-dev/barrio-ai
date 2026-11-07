// Pure rules of Resultados shared by both apps: «datos hasta», the KPI «sin dato» and variation rules, bars and
// funnels, the 60/40 split, the impressions chart, the posts sorting, the team line and the summary texts.
import { kpi, negocioOn, resultadosFixture } from '../fixtures/resultados';
import {
  barRows,
  commentersView,
  dataUntil,
  funnelRows,
  impressionsChart,
  kpiDelta,
  kpiState,
  modalitySplit,
  newRequestId,
  periodNote,
  readDias,
  readModalidad,
  readNegocio,
  sortPosts,
  spendSummary,
  teamCount,
  weekPhrase,
  type NegocioOn,
} from './resultados';

describe('Resultados rules', () => {
  it('reads the controls of the URL with their defaults', () => {
    expect([readDias('7'), readDias('90'), readDias('x'), readDias(undefined)]).toEqual([7, 90, 28, 28]);
    expect([readModalidad('projectapp'), readModalidad('personal_startups'), readModalidad('otra')]).toEqual(['projectapp', 'personal_startups', 'todo']);
  });

  it('reads «datos hasta» as today or as a date in the machine time zone', () => {
    const now = new Date('2026-11-07T22:00:00Z');
    expect(dataUntil('2026-11-07T19:20:00Z', 'America/Bogota', now)).toBe('hoy 14:20');
    expect(dataUntil('2026-11-06T19:20:00Z', 'America/Bogota', now)).toBe('6 nov 14:20');
    expect(dataUntil('no-es-fecha')).toBe('—');
    expect(periodNote(undefined, true, 28)).toBe('Cargando el periodo…');
    expect(periodNote(undefined, false, 7)).toBe('Todo se compara con los 7 días anteriores.');
  });

  it('never turns «sin dato» into 0 and colours the variation', () => {
    expect(kpiState(kpi(null))).toEqual({ available: false, reason: 'Sin datos en este periodo.' });
    expect(kpiState(undefined, 'Disponible cuando conectemos el inbox.')).toEqual({ available: false, reason: 'Disponible cuando conectemos el inbox.' });
    expect(kpiState(kpi(0, { previous: 0 })).available).toBe(true);
    expect(kpiDelta(kpi(41, { previous: 45 }), 'percent')).toMatchObject({ text: '▼ −4 pts', tone: 'bad' });
    expect(kpiDelta(kpi(3, { previous: 4 }), 'number', 'down')).toMatchObject({ text: '▼ −1', tone: 'good' });
    expect(kpiDelta(kpi(1520, { previous: 1357 }), 'number', 'up', true)).toMatchObject({ text: '▲ 12 %', tone: 'good' });
    expect(kpiDelta(kpi(2, { comparable: false })).text).toBe('sin comparación');
  });

  it('draws funnels with conversion and bars with a dash for «sin dato»', () => {
    const rows = funnelRows([
      { label: 'Conversación', value: 4 },
      { label: 'Necesidad', value: 3 },
      { label: 'Cualificada', value: null },
    ]);
    expect(rows.map((row) => [row.valueText, row.conversion, Math.round(row.width)])).toEqual([
      ['4', null, 100],
      ['3', 75, 75],
      ['—', null, 0],
    ]);
    expect(rows[1]!.spoken).toBe('Necesidad: 3, 75 % del paso anterior');
    expect(barRows([{ key: 'a', value: null }, { key: 'b', value: 3.4, display: '3,4 %' }]).map((row) => [row.text, row.width])).toEqual([
      ['—', 0],
      ['3,4 %', 100],
    ]);
  });

  it('splits the opportunities against the 60/40 target, and says when there is no data', () => {
    const negocio = readNegocio(negocioOn()) as NegocioOn;
    expect(modalitySplit(negocio.modalidades)).toMatchObject({ startups: 50, projectapp: 50, target: 60, spoken: 'Startups 50 %, ProjectApp 50 %, objetivo 60/40' });
    expect(modalitySplit({ ...negocio.modalidades, pct: {}, counts: { por_clasificar: 2 } })).toMatchObject({
      startups: null,
      pendingNote: '2 oportunidades por clasificar no cuentan en el reparto.',
    });
  });

  it('draws the impressions per post against the median and labels each bar', () => {
    const chart = impressionsChart(resultadosFixture().contenido.chart, '7d');
    expect(chart.title).toBe('Impresiones por post a los 7 días');
    expect(chart.reference).toBe(1250);
    expect(chart.bars.map((bar) => [bar.pieceId, bar.above, bar.fallback, bar.empty])).toEqual([
      ['p-1', true, false, false],
      ['p-2', false, true, false],
      ['p-3', false, false, true],
    ]);
    expect(chart.bars[1]!.label).toBe('Post 2, 5 nov: 960 impresiones a las 24 h');
  });

  it('sorts posts with missing values last and reads who commented', () => {
    const posts = resultadosFixture().contenido.posts;
    expect(sortPosts(posts, 'impressions_7d', 'asc').map((p) => p.piece_id)).toEqual(['p-1', 'p-2', 'p-3']);
    expect(sortPosts(posts, 'commenters', 'desc').map((p) => p.piece_id)).toEqual(['p-1', 'p-2', 'p-3']);
    expect(sortPosts(posts, 'date', 'desc').map((p) => p.piece_id)).toEqual(['p-3', 'p-2', 'p-1']);
    expect(commentersView(posts[2]!)).toEqual({ kind: 'nocut' });
    expect(commentersView(posts[0]!)).toEqual({ kind: 'roles', chips: ['Comprador · 3', 'Par · 4'] });
    expect(commentersView({ ...posts[0]!, commenters_by_role: null })).toEqual({ kind: 'unread' });
    expect(commentersView({ ...posts[0]!, commenters_by_role: { par: 0 } })).toEqual({ kind: 'nobody' });
  });

  it('writes the team line and the AI spend', () => {
    expect(teamCount(kpi(1), 'bloqueada', 'bloqueadas')).toBe('1 bloqueada');
    expect(teamCount(kpi(null), 'publicado', 'publicados')).toBeNull();
    expect(spendSummary(resultadosFixture().equipo.spend)).toEqual({ today: '3,10 de 5,00 USD hoy', month: '61,20 USD este mes' });
    expect(spendSummary(undefined)).toBeNull();
  });

  it('phrases the summary week and makes one request id per intent', () => {
    expect(weekPhrase('Semana del 2 al 8 de noviembre')).toBe('la semana del 2 al 8 de noviembre');
    const first = newRequestId();
    expect(first).toMatch(/^[0-9a-f-]{36}$/);
    expect(newRequestId()).not.toBe(first);
  });
});
