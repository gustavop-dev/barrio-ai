// Dates of the QA world as the Calendario shows them (compartido/src/logic/dates.ts), for 07-calendario.yaml.
// The script runs on the runner (UTC), not on the emulator: America/Bogota is UTC-5 all year (no DST), so
// "now" minus 5 hours read in UTC fields is Bogotá's wall clock, the same day the app and the backend use.
var DAY = 86400000;
var DIAS = ['domingo', 'lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado'];
var MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];
var MESES_CORTOS = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];

var bogota = new Date(Date.now() - 5 * 3600000);
var today = Date.UTC(bogota.getUTCFullYear(), bogota.getUTCMonth(), bogota.getUTCDate());

function day(offset) {
  return new Date(today + offset * DAY);
}

/** AAAA-MM-DD, the day testIDs (dia-AAAA-MM-DD). */
function iso(date) {
  return date.toISOString().slice(0, 10);
}

/** «domingo 8 de noviembre» (longDay). */
function longDay(date) {
  return DIAS[date.getUTCDay()] + ' ' + date.getUTCDate() + ' de ' + MESES[date.getUTCMonth()];
}

function capitalize(text) {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/** «2–8 nov 2026», «30 nov – 6 dic 2026», «29 dic 2025 – 4 ene 2026» (weekRangeLabel, Monday first). */
function weekRange(date) {
  var start = new Date(date.getTime() - ((date.getUTCDay() + 6) % 7) * DAY);
  var end = new Date(start.getTime() + 6 * DAY);
  var sd = start.getUTCDate(), sm = start.getUTCMonth(), sy = start.getUTCFullYear();
  var ed = end.getUTCDate(), em = end.getUTCMonth(), ey = end.getUTCFullYear();
  if (sy !== ey) return sd + ' ' + MESES_CORTOS[sm] + ' ' + sy + ' – ' + ed + ' ' + MESES_CORTOS[em] + ' ' + ey;
  if (sm !== em) return sd + ' ' + MESES_CORTOS[sm] + ' – ' + ed + ' ' + MESES_CORTOS[em] + ' ' + ey;
  return sd + '–' + ed + ' ' + MESES_CORTOS[em] + ' ' + ey;
}

/** «Noviembre 2026» (monthTitle). */
function monthTitle(date) {
  return capitalize(MESES[date.getUTCMonth()]) + ' ' + date.getUTCFullYear();
}

/** The 15th of the month `n` months away: always in that month's grid, never in a neighbour's. */
function midMonth(date, n) {
  return new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth() + n, 15));
}

var hoy = day(0);
var manana = day(1);
var anteayer = day(-2);

output.hoy = iso(hoy);
output.hoyTitulo = capitalize(longDay(hoy));
output.manana = iso(manana);
output.mananaTitulo = capitalize(longDay(manana));
output.mananaLargo = longDay(manana);
output.anteayer = iso(anteayer);
output.anteayerTitulo = capitalize(longDay(anteayer));
output.anteayerLargo = longDay(anteayer);
output.semanaHoy = weekRange(hoy);
output.semanaSiguiente = weekRange(day(7));
output.semanaAnterior = weekRange(day(-7));
output.diaSemanaSiguiente = iso(day(7));
output.diaSemanaAnterior = iso(day(-7));
output.mesHoy = monthTitle(hoy);
output.mesSiguiente = monthTitle(midMonth(hoy, 1));
output.mitadMes = iso(midMonth(hoy, 0));
output.mitadMesSiguiente = iso(midMonth(hoy, 1));

// 07-pieza-veto and 07-pieza-estados: the other days of the QA world (seed_qa: pieces at T-1 skipped, T-2 blocked,
// T-3 and T-8 published, T-5 failed; T+2 has a meeting and no piece; T-4 has no piece).
var ayer = day(-1);
var hace3 = day(-3);
var hace4 = day(-4);
var hace5 = day(-5);
var pasadoManana = day(2);
output.ayer = iso(ayer);
output.ayerTitulo = capitalize(longDay(ayer));
output.ayerLargo = longDay(ayer);
output.hace3 = iso(hace3);
output.hace3Largo = longDay(hace3);
output.hace4 = iso(hace4);
output.hace4Titulo = capitalize(longDay(hace4));
output.hace5 = iso(hace5);
output.hace5Largo = longDay(hace5);
output.pasadoManana = iso(pasadoManana);
output.pasadoMananaTitulo = capitalize(longDay(pasadoManana));
// The 7-day cut of the T-3 post arrives at T+4 («Aún no · Llega el …»).
output.corte7dHace3 = longDay(day(4));
// Two months away: nothing registered there, and every day is more than 15 days out.
output.mesMas2 = monthTitle(midMonth(hoy, 2));
output.mitadMesMas2 = iso(midMonth(hoy, 2));
output.mitadMesMas2Titulo = capitalize(longDay(midMonth(hoy, 2)));
// Another day of today's week (Monday first): the day before, or the day after on Mondays.
var otroDia = day(hoy.getUTCDay() === 1 ? 1 : -1);
output.otroDia = iso(otroDia);
output.otroDiaTitulo = capitalize(longDay(otroDia));
