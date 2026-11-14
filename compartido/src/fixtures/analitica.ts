// GET /api/v1/resultados/analitica shaped like analitica.overview (a 7-day preset ending 12 nov 2026, every day
// imported). Invented data only: no real account, post or figure.
import type { AnaliticaData, AnaliticaDay, AnaliticaKpi, AnaliticaSinCuenta } from '../api/types';
import { kpi } from './resultados';

export const SIN_CUENTA: AnaliticaSinCuenta = {
  disponible: false,
  motivo: 'Aún no hay una cuenta de LinkedIn conectada por el navegador (proveedor «directo»).',
};

const DAYS = ['2026-11-06', '2026-11-07', '2026-11-08', '2026-11-09', '2026-11-10', '2026-11-11', '2026-11-12'];
const IMPRESSIONS = [100, 120, 90, 150, 130, 110, 140];
const ENGAGEMENTS = [5, 6, 4, 8, 7, 5, 7];
const NEW_FOLLOWERS = [1, 0, 2, 1, 0, 1, 2];

export function serieFixture(): AnaliticaDay[] {
  return DAYS.map((date, index) => ({ date, impressions: IMPRESSIONS[index]!, engagements: ENGAGEMENTS[index]!, new_followers: NEW_FOLLOWERS[index]! }));
}

function daily(value: number | null, previous: number | null, definition: string, extra: Partial<AnaliticaKpi> = {}): AnaliticaKpi {
  return {
    ...kpi(value, { previous, definition, unavailable_reason: value === null ? 'Sin datos importados de LinkedIn en este periodo.' : null }),
    days: 7,
    days_with_data: value === null ? 0 : 7,
    ...extra,
  };
}

const POST_URL = 'https://www.linkedin.example/feed/update/urn:li:activity:7000000000000000001/';

export function analiticaFixture(overrides: Partial<AnaliticaData> = {}): AnaliticaData {
  return {
    disponible: true,
    motivo: null,
    cuenta: { id: '5d1c9a2e-0000-4000-8000-00000000d1ec', label: 'Cuenta directa de prueba' },
    periodo: { desde: '2026-11-06', hasta: '2026-11-12', dias: 7, preset: '7d', zona_horaria: 'UTC', anterior: { desde: '2026-10-30', hasta: '2026-11-05' } },
    limites: { primer_dia: '2025-10-10', ultimo_dia: '2026-11-12', linkedin_desde: '2025-10-10' },
    actualizado: { at: '2026-11-13T06:10:00Z', desde: '2026-10-30', hasta: '2026-11-12', tipo: 'diaria' },
    ultimo_error: null,
    totales: {
      impressions: daily(840, 700, 'Impresiones de tus publicaciones por día, sumadas en el periodo (LinkedIn).'),
      engagements: daily(42, 35, 'Interacciones con tus publicaciones por día, sumadas en el periodo (LinkedIn).'),
      new_followers: daily(7, 9, 'Seguidores nuevos que LinkedIn cuenta por día, sumados en el periodo.'),
      engagement_rate: {
        ...kpi(5, { previous: 5, definition: 'Interacciones frente a impresiones en el periodo (LinkedIn).', formula: 'interacciones / impresiones × 100' }),
        numerator: 42,
        denominator: 840,
      },
      members_reached: {
        ...kpi(612, { previous: null, comparable: false, definition: 'Personas distintas que vieron tus publicaciones en el periodo, según LinkedIn para ese rango exacto.' }),
        captured_at: '2026-11-13T06:12:00Z',
      },
    },
    serie: serieFixture(),
    seguidores: {
      total: 1480,
      at: '2026-11-13',
      serie: [
        { date: '2026-11-06', value: 1473 },
        { date: '2026-11-09', value: 1476 },
        { date: '2026-11-13', value: 1480 },
      ],
      definition: 'Total de seguidores que LinkedIn da el día en que se importa (no el de una fecha pasada); la última captura del periodo o del día siguiente.',
      unavailable_reason: null,
    },
    posts: {
      publicados: [
        {
          post_urn: 'urn:li:activity:7000000000000000001',
          url: POST_URL,
          piece_id: 'pieza-analitica-1',
          published: '2026-11-10',
          kind: 'Imagen',
          impressions: 1840,
          network_pct: 62.5,
          outside_pct: 37.5,
          members_reached: 1210,
          followers_gained: 3,
          profile_views: 14,
          reactions: 41,
          comments: 9,
          shares: 2,
          saves: 5,
          sends: 1,
          button_clicks: null,
          as_of: '2026-11-13T06:10:00Z',
        },
        {
          post_urn: 'urn:li:activity:7000000000000000002',
          url: 'https://www.linkedin.example/feed/update/urn:li:activity:7000000000000000002/',
          piece_id: null,
          published: '2026-11-07',
          kind: 'Texto',
          impressions: 620,
          network_pct: null,
          outside_pct: null,
          members_reached: null,
          followers_gained: null,
          profile_views: null,
          reactions: 12,
          comments: 2,
          shares: null,
          saves: null,
          sends: null,
          button_clicks: null,
          as_of: '2026-11-12T06:10:00Z',
        },
      ],
      definition: 'Publicaciones del periodo con sus cifras de toda la vida, tal como LinkedIn las dio la última vez que estaban entre las más recientes (as_of).',
      top_linkedin: {
        desde: '2026-11-06',
        hasta: '2026-11-12',
        captured_at: '2026-11-13T06:12:00Z',
        por_interacciones: [
          { post_urn: 'urn:li:activity:7000000000000000001', url: POST_URL, piece_id: 'pieza-analitica-1', published: '2026-11-10', value: 52 },
          { post_urn: 'urn:li:activity:7000000000000000002', url: POST_URL, piece_id: null, published: '2026-11-07', value: 14 },
        ],
        por_impresiones: [
          { post_urn: 'urn:li:activity:7000000000000000001', url: POST_URL, piece_id: 'pieza-analitica-1', published: '2026-11-10', value: 1840 },
          { post_urn: 'urn:li:activity:7000000000000000002', url: POST_URL, piece_id: null, published: '2026-11-07', value: 620 },
        ],
      },
      top_unavailable_reason: null,
    },
    demografia: {
      audiencia: {
        at: '2026-11-13',
        groups: [
          {
            group: 'Cargo',
            rows: [
              { label: 'Fundador', pct: 18.5, below: false, value: null },
              { label: 'Ingeniero de software', pct: 12, below: false, value: null },
              { label: 'Gerente de producto', pct: 1, below: true, value: null },
            ],
          },
          {
            group: 'Ubicación',
            rows: [
              { label: 'Área de Bogotá', pct: 41, below: false, value: null },
              { label: 'Área de Medellín', pct: 9.5, below: false, value: null },
            ],
          },
        ],
      },
      contenido: {
        desde: '2026-11-06',
        hasta: '2026-11-12',
        exacto: true,
        captured_at: '2026-11-13T06:12:00Z',
        groups: [
          {
            group: 'Sector',
            rows: [
              { label: 'Desarrollo de software', pct: 33, below: false, value: null },
              { label: 'Servicios financieros', pct: 8, below: false, value: null },
            ],
          },
        ],
      },
    },
    ...overrides,
  };
}
