// Ajustes › Mi perfil, Mi voz and Organización (organizaciones, phase 7): what each member edits of herself, how far her
// voice is, and what the admin sees of the organization. Pure: shared by the PWA and the native app, each draws it with
// its own components. The limits mirror the backend's validation (identidad.validate_member) so a mistake is said before
// sending; the backend checks again and its 400 `detail` is shown as it comes.
import type {
  MemberProfile,
  MemberProfileField,
  MemberProfilePatch,
  MiPerfil,
  MiVoz,
  OrganizationMember,
  ProfileRevision,
  VoiceSignalKind,
  VoiceState,
  VoiceVersionState,
  Yo,
} from '../api/types';
import { formatDateTime } from './format';
import type { Tone } from './tone';

/** Shown on top of Ajustes while her member is inactive (in onboarding). */
export const ALTA_NOTICE =
  'Tu cuenta está en alta: conecta tu LinkedIn (API oficial y sesión del navegador) y completa tu perfil; el administrador la activa cuando todo esté listo.';

/** Whether the signed-in person is a member in onboarding (inactive): she only uses Ajustes until the admin activates her. */
export function inOnboarding(yo: Yo | null | undefined): boolean {
  return yo?.member?.active === false;
}

// ---------------------------------------------------------------- Mi perfil

export interface ProfileFieldSpec {
  key: MemberProfileField;
  label: string;
  /** Characters at most (texts). */
  max?: number;
  required?: boolean;
  multiline?: boolean;
  /** Said under the field when the backend sends no help of its own. */
  hint: string;
}

/** The fields in the order they are shown. `personal_startups` is a switch; the rest are texts. */
export const PROFILE_FIELDS: readonly ProfileFieldSpec[] = [
  { key: 'name', label: 'Nombre', max: 60, required: true, hint: 'Cómo te nombra el equipo en sus textos y en lo que dibuja.' },
  { key: 'role', label: 'Rol', max: 120, hint: 'Tu papel en la organización (p. ej. «CTO»).' },
  { key: 'identity', label: 'Cómo te presentas', max: 600, multiline: true, hint: 'Una o dos frases.' },
  { key: 'company_relation', label: 'Relación con la empresa', max: 300, multiline: true, hint: 'P. ej. «Es CTO de ProjectApp…».' },
  {
    key: 'limits',
    label: 'Temas que no dominas',
    max: 600,
    required: true,
    multiline: true,
    hint: 'Lo que el equipo nunca escribe en tu nombre: temas que no dominas y lo que nunca se inventa.',
  },
  { key: 'personal_startups', label: 'Te aplica el trabajo personal en startups', hint: 'Si la modalidad de trabajo personal en startups es tuya.' },
];

export const PROFILE_LABEL: Record<string, string> = Object.fromEntries(PROFILE_FIELDS.map((field) => [field.key, field.label]));

const NAME = /^\p{L}+(?:[ '-]\p{L}+)*$/u;

/** What is wrong with each field of `profile` (nothing when it can be sent). Same limits as the backend. */
export function profileIssues(profile: MemberProfile): Partial<Record<MemberProfileField, string>> {
  const issues: Partial<Record<MemberProfileField, string>> = {};
  for (const field of PROFILE_FIELDS) {
    if (field.key === 'personal_startups') continue;
    const value = String(profile[field.key] ?? '').trim();
    if (field.required && !value) issues[field.key] = 'No puede quedar vacío.';
    else if (field.max !== undefined && value.length > field.max) issues[field.key] = `Como mucho ${field.max} caracteres (van ${value.length}).`;
  }
  const name = profile.name.trim();
  if (!issues.name && !NAME.test(name)) issues.name = 'Solo letras, espacios, apóstrofo o guion.';
  return issues;
}

/** «12 / 600». */
export function fieldCounter(value: string, max: number | undefined): string {
  return max === undefined ? '' : `${value.length} / ${max}`;
}

/** Only the fields that changed (texts trimmed): what PATCH /api/v1/yo/perfil receives. */
export function profilePatch(saved: MemberProfile, draft: MemberProfile): MemberProfilePatch {
  const patch: MemberProfilePatch = {};
  for (const field of PROFILE_FIELDS) {
    const key = field.key;
    if (key === 'personal_startups') {
      if (draft.personal_startups !== saved.personal_startups) patch.personal_startups = draft.personal_startups;
      continue;
    }
    const value = String(draft[key] ?? '').trim();
    if (value !== String(saved[key] ?? '').trim()) patch[key] = value;
  }
  return patch;
}

export function hasChanges(patch: MemberProfilePatch): boolean {
  return Object.keys(patch).length > 0;
}

/** What the screen says after saving: «Guardado.» or «Sin cambios: ya tenías esos valores.». */
export function savedMessage(saved: boolean): string {
  return saved ? 'Guardado.' : 'Sin cambios: ya tenías esos valores.';
}

/** Where a change came from, in words. */
const SOURCE_LABEL: Record<string, string> = {
  app: 'desde la app',
  comando: 'por comando',
  alta: 'en el alta',
  semilla: 'identidad inicial',
  migracion: 'migración',
};

/** «#3 · 18 nov 2026, 10:30 · gustavo · desde la app · cambió: Cómo te presentas, Rol». */
export function revisionLine(revision: ProfileRevision): string {
  const changed = revision.changed.map((key) => PROFILE_LABEL[key] ?? key).join(', ') || '—';
  return [
    `#${revision.number}`,
    formatDateTime(revision.created_at),
    revision.by ?? 'sistema',
    SOURCE_LABEL[revision.source] ?? revision.source,
    `cambió: ${changed}`,
  ].join(' · ');
}

/** «Aún no guardaste tu perfil: son los valores iniciales.» when `own` is false; null otherwise. */
export function profileOrigin(perfil: Pick<MiPerfil, 'own'>): string | null {
  return perfil.own ? null : 'Aún no guardaste tu perfil: lo que ves son los valores iniciales.';
}

// ---------------------------------------------------------------- Mi voz

export const VOICE_TONE: Record<VoiceState, Tone> = { provisional: 'warn', confirmada: 'ok', inicial: 'info' };

/** What her voice means for what the team writes. */
export function voiceSentence(voz: Pick<MiVoz, 'state' | 'version'>): string {
  switch (voz.state) {
    case 'provisional':
      return 'El equipo escribe con una voz neutra y sobria y marca tus borradores «Voz provisional». Nada de lo que escribe en tu nombre sale sin que lo apruebes.';
    case 'confirmada':
      return `El equipo escribe con tu voz confirmada${voz.version ? ` (versión ${voz.version})` : ''}.`;
    default:
      return 'El equipo escribe con la voz inicial de la instalación.';
  }
}

/** «7 de 12 textos aprobados o editados»: what a proposal needs (VOICE_LEARNING_MIN_TEXTS). */
export function voiceProgress(signals: MiVoz['signals']): string {
  return `${signals.texts} de ${signals.minimum} textos aprobados o editados`;
}

export const SIGNAL_LABEL: Record<VoiceSignalKind, string> = {
  aprobado: 'Aprobados sin cambios',
  editado: 'Editados por ti',
  rechazado: 'Rechazados con motivo',
  respuesta: 'Respuestas a preguntas',
  captura: 'Audios y notas',
};

/** Every kind with its count, in a fixed order (zero when there is none). */
export function signalRows(signals: MiVoz['signals']): { kind: VoiceSignalKind; label: string; count: number }[] {
  return (Object.keys(SIGNAL_LABEL) as VoiceSignalKind[]).map((kind) => ({ kind, label: SIGNAL_LABEL[kind], count: signals.by_kind[kind] ?? 0 }));
}

/** Why «Pedir propuesta» is not there, or null when it is. */
export function proposeBlocked(voz: Pick<MiVoz, 'can_propose' | 'learning_enabled' | 'proposal' | 'signals'>): string | null {
  if (voz.can_propose) return null;
  if (voz.proposal) return 'Hay una propuesta esperando tu decisión.';
  if (!voz.learning_enabled) return 'El aprendizaje de la voz está apagado en el servidor.';
  if (voz.signals.texts < voz.signals.minimum) return `Faltan ${voz.signals.minimum - voz.signals.texts} textos tuyos aprobados o editados para pedir una propuesta.`;
  return 'Ahora no se puede pedir una propuesta.';
}

/** Said before asking: it is paid and is not used until she confirms it. */
export const PROPOSE_COST =
  'Pedir una propuesta hace una llamada de pago (unos 0,17 USD) con tus señales. No se usa hasta que tú la confirmes.';

export const VERSION_STATE_LABEL: Record<VoiceVersionState, string> = { confirmada: 'Confirmada', propuesta: 'Propuesta', descartada: 'Descartada' };
export const VERSION_STATE_TONE: Record<VoiceVersionState, Tone> = { confirmada: 'ok', propuesta: 'info', descartada: 'muted' };

// ---------------------------------------------------------------- Organización

export const VOICE_LABEL: Record<VoiceState, string> = { provisional: 'Voz provisional', confirmada: 'Voz confirmada', inicial: 'Voz inicial' };

/** The badges of a member in the admin's list: active or not, admin, her voice. */
export function memberBadges(member: OrganizationMember): { text: string; tone: Tone | 'ink' }[] {
  const badges: { text: string; tone: Tone | 'ink' }[] = [member.active ? { text: 'Activo', tone: 'ok' } : { text: 'Inactivo', tone: 'warn' }];
  if (member.is_admin) badges.push({ text: 'Administrador', tone: 'ink' });
  badges.push({ text: VOICE_LABEL[member.voice] ?? member.voice, tone: VOICE_TONE[member.voice] ?? 'muted' });
  return badges;
}

/** «API oficial: conectada · Navegador: sin conectar». */
export function memberAccounts(member: OrganizationMember): string {
  const state = (value: boolean) => (value ? 'conectada' : 'sin conectar');
  return `API oficial: ${state(member.accounts.official)} · Navegador: ${state(member.accounts.reader)}`;
}

/** «Fundador · desde 2026-11-17». */
export function memberSubtitle(member: OrganizationMember): string {
  return [member.role || 'sin rol', member.since ? `desde ${member.since}` : ''].filter(Boolean).join(' · ');
}
