// Agreement of the person card's labels with the person (Persona.dc.html: «Descubierta», «Seguida», «Conectada»).
// LinkedIn gives no gender, so it is read from the first name: a name we take as a woman's gets the feminine forms;
// an unknown or ambiguous one keeps the masculine ones, as before. Only for agreement, never shown or stored.

/** Common women's names that do not end in «a» (accents removed, lower case). */
const FEMININE = new Set([
  'abigail', 'abril', 'adriana', 'alison', 'allison', 'amy', 'araceli', 'ashley', 'beatriz', 'belen', 'camille', 'carmen',
  'caroline', 'catherine', 'chloe', 'cindy', 'consuelo', 'danielle', 'dolores', 'dulce', 'elizabeth', 'ellen', 'emily',
  'esther', 'evelyn', 'flor', 'gabrielle', 'grace', 'helen', 'ines', 'ingrid', 'iris', 'isabel', 'isabelle', 'ivonne',
  'jacqueline', 'jennifer', 'jenny', 'joy', 'karen', 'karin', 'katherine', 'kimberly', 'lady', 'leidy', 'lisbeth', 'lizeth',
  'lourdes', 'lucy', 'luz', 'madison', 'margaret', 'maribel', 'marisol', 'mary', 'mercedes', 'michelle', 'miriam', 'nancy',
  'natalie', 'nathalie', 'nicole', 'noemi', 'paz', 'pilar', 'rachel', 'raquel', 'rocio', 'ruth', 'sarah', 'sharon',
  'sol', 'soledad', 'sophie', 'stefany', 'susan', 'tiffany', 'wendy', 'yvonne', 'zoe',
]);

/** Men's names that end in «a». */
const MASCULINE_IN_A = new Set(['bautista', 'borja', 'elisha', 'ilya', 'joshua', 'luca', 'mika', 'nikita', 'kosta']);

/** Titles that say it outright; any other abbreviation («Dr.», «Ing.») is skipped. */
const FEMININE_TITLES = new Set(['dra.', 'sra.', 'srta.']);

function plain(word: string): string {
  return word.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
}

/** True when the first name reads as a woman's («Lucía Ficticia», «Dra. Pérez», «Isabel Díaz»). */
export function isFeminineName(displayName: string | null | undefined): boolean {
  for (const raw of (displayName ?? '').trim().split(/\s+/)) {
    const word = plain(raw).replace(/[^a-z.]/g, '');
    if (!word || word === '.') continue;
    if (FEMININE_TITLES.has(word)) return true;
    if (word.endsWith('.')) continue;
    if (FEMININE.has(word)) return true;
    if (MASCULINE_IN_A.has(word)) return false;
    return word.length > 2 && word.endsWith('a');
  }
  return false;
}

/** The participles of the card that agree with the person. */
const AGREEING = new Set(['Clasificado', 'Descubierto', 'Seguido', 'Invitado', 'Conectado', 'Cerrado', 'Descartado']);

/** «Seguido» → «Seguida» for a woman; any other label stays as it is. */
export function agree(label: string, feminine: boolean): string {
  return feminine && AGREEING.has(label) ? `${label.slice(0, -1)}a` : label;
}
