// Organizaciones, phase 7: GET /api/v1/yo, /yo/perfil, /yo/voz and /organizacion as the backend answers them. Invented
// data only: no real person or company text.
import type { MiPerfil, MiVoz, Organizacion, Yo } from '../api/types';

/** The installation's first member, admin and active (seed_qa's «qa»). */
export function yoFixture(extra: Partial<Yo> = {}, member: Partial<NonNullable<Yo['member']>> = {}): Yo {
  return {
    username: 'gustavo',
    member: { id: 'm-1', display_name: 'Gustavo', role: 'Fundador', active: true, is_admin: true, first: true, ...member },
    organization: { id: 'o-1', name: 'ProjectApp', slug: 'projectapp' },
    is_admin: true,
    provisional_voice: false,
    members: 1,
    ...extra,
  };
}

/** A new member in onboarding: inactive, not admin, provisional voice. */
export function yoAltaFixture(): Yo {
  return yoFixture(
    { username: 'ana', is_admin: false, provisional_voice: true, members: 1 },
    { id: 'm-2', display_name: 'Ana Pérez', role: 'CTO', active: false, is_admin: false, first: false },
  );
}

export function perfilFixture(extra: Partial<MiPerfil> = {}): MiPerfil {
  return {
    member: { id: 'm-2', display_name: 'Ana Pérez', role: 'CTO', active: true },
    profile: {
      name: 'Ana Pérez',
      role: 'CTO',
      identity: 'Construyo producto con equipos pequeños.',
      company_relation: 'Es CTO de ProjectApp.',
      limits: 'Temas que no domina; nada inventado.',
      personal_startups: false,
    },
    own: true,
    help: {
      name: 'Cómo la nombra el equipo en sus textos.',
      identity: 'Cómo se presenta: una o dos frases.',
      limits: 'Límites de lo que se escribe en su nombre.',
    },
    history: [
      { number: 2, created_at: '2026-11-18T15:30:00Z', by: 'ana', source: 'app', changed: ['identity'] },
      { number: 1, created_at: '2026-11-18T10:00:00Z', by: 'gustavo', source: 'alta', changed: ['company_relation', 'name'] },
    ],
    ...extra,
  };
}

export function vozFixture(extra: Partial<MiVoz> = {}): MiVoz {
  return {
    state: 'provisional',
    version: null,
    label: 'Provisional',
    learning_enabled: true,
    signals: { texts: 7, minimum: 12, by_kind: { aprobado: 5, editado: 2, captura: 3 } },
    can_propose: false,
    proposal: null,
    versions: [],
    ...extra,
  };
}

/** Her voice with a proposal waiting for her decision. */
export function vozConPropuestaFixture(): MiVoz {
  return vozFixture({
    signals: { texts: 13, minimum: 12, by_kind: { aprobado: 9, editado: 4, respuesta: 2 } },
    proposal: { number: 1, created_at: '2026-11-18T16:00:00Z', note: 'Muestra sólida.', text: '# Tono de voz de Ana Pérez\n\nFrases cortas.' },
    versions: [{ number: 1, state: 'propuesta', source: 'aprendida', created_at: '2026-11-18T16:00:00Z', decided_at: null }],
  });
}

export function vozConfirmadaFixture(): MiVoz {
  return vozFixture({
    state: 'confirmada',
    version: 2,
    label: 'Confirmada v2',
    signals: { texts: 14, minimum: 12, by_kind: { aprobado: 10, editado: 4 } },
    can_propose: true,
    versions: [
      { number: 1, state: 'descartada', source: 'aprendida', created_at: '2026-11-10T10:00:00Z', decided_at: '2026-11-11T10:00:00Z' },
      { number: 2, state: 'confirmada', source: 'aprendida', created_at: '2026-11-17T10:00:00Z', decided_at: '2026-11-18T10:00:00Z' },
    ],
  });
}

export function organizacionFixture(): Organizacion {
  return {
    organization: { id: 'o-1', name: 'ProjectApp', slug: 'projectapp' },
    profile: {
      version: 'posicionamiento-v3',
      date: '2026-11-01',
      status: 'Vigente.',
      language: 'Español, Latinoamérica.',
      location: 'Medellín.',
      not_wanted: 'Corporativos grandes.',
      pillars: { producto: 'Producto con IA.', equipo: 'Equipos pequeños.' },
      services: { producto: { label: 'Desarrollo de producto', source: 'catalogo', terms: ['product'] } },
      offer: { proyecto: 'Proyecto cerrado.' },
      cases: { retail: 'Un caso de retail.' },
      modalities: { projectapp: { purpose: 'Conseguir clientes.', neighborhood: 'Fundadores.' } },
    },
    members: [
      { id: 'm-1', display_name: 'Gustavo', role: 'Fundador', active: true, is_admin: true, first: true, voice: 'inicial', accounts: { official: true, reader: true }, since: '2026-11-17' },
      { id: 'm-2', display_name: 'Ana Pérez', role: 'CTO', active: false, is_admin: false, first: false, voice: 'provisional', accounts: { official: true, reader: false }, since: '2026-11-18' },
    ],
  };
}
