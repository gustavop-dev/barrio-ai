// Days of the LinkedIn analytics of the QA world (seed_qa --analitica) for 08-resultados-linkedin.yaml. The backend
// stores UTC days and the runner runs in UTC: «yesterday» here is the last day the seed imported. The custom range is
// days 20 to 11 before it: ten complete days, clear of the seed's three-day gap (57 to 59 days back).
var DAY = 86400000;
var now = new Date();
var today = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate());

function iso(offset) {
  return new Date(today + offset * DAY).toISOString().slice(0, 10);
}

output.anaDesde = iso(-21);
output.anaHasta = iso(-12);
