import type { CommunityReport } from '../api/comunidad';

export function communityFixture(): CommunityReport {
  return {
    status: 'Estudio parcial', pending: false,
    study: { id: 'study-synthetic', version: 1, period: '2026-10-01', state: 'partial',
      window_start: '2026-08-03T05:00:00Z', window_end: '2026-11-01T05:00:00Z',
      created_at: '2026-11-09T12:00:00Z', expires_at: '2027-05-08T12:00:00Z', positioning_version: 'synthetic-v1',
      coverage: { sample_size: 6, potential: 9, since: '2026-10-01T12:00:00Z', limitations: ['Muestra no representativa.'] },
      summary: { findings: [{ id: 'h1', pattern: 'medición del resultado', basis: 'observed', people: 6,
        counterexamples: null, interpretation: 'Puede orientar preguntas del panel.', uncertainty: 'Cobertura parcial.' }],
        unknown_follow_reason: 6, units: ['LI-06-V006-K04'] } },
    sources: [{ id: 'source-synthetic', person: 'person-synthetic', kind: 'public_comment',
      text: 'How do you measure delivery cost?', url: '', event_at: '2026-10-01T12:00:00Z',
      observed_at: '2026-11-09T12:00:00Z', analysis: { follow_status: 'unknown' } }],
  };
}

export const emptyCommunity: CommunityReport = { status: 'Sin estudio vigente', pending: false, study: null, sources: [] };
