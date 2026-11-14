"""The daily canary by hand, through the running service exactly as the backend calls it: the checks themselves live
in linkedin_directo/canario.py (the backend runs the same ones once a day, team_backend/canario.py).

    python -m navegador canario <cuenta> [--url http://127.0.0.1:8790]

One line per operation (ok / roto / sin_probar, and why) and <datos>/canario/canario-<cuenta>-<fecha>.json with states,
counts and field names, never values (no names, texts or ids). Exit code: 0 all ok; 2 something broke; 3 hard stop
(the account is stopped, has no session, or LinkedIn pushed back: do not retry, look at it by hand); 4 it did not run
(the service is not reachable or busy, the token is wrong, the account is unknown or out of budget)."""
import json
import sys
import time

from linkedin_directo import canario

OK, BROKEN, HALTED, NOT_RUN = 0, 2, 3, 4
CODES = {canario.OK: OK, canario.BROKEN: BROKEN, canario.HALTED: HALTED, canario.NOT_RUN: NOT_RUN}


def run(url, token, account, data_dir, out=print, transport=None):
    if transport is None:
        from linkedin_directo.servicio import ServiceTransport
        transport = ServiceTransport(url, token, account)
    report = {'fecha': time.strftime('%Y-%m-%d'), 'hora': time.strftime('%H:%M:%S'), 'cuenta': account}
    report.update(canario.run(transport, out=out))
    code = report['codigo'] = CODES[report['resultado']]
    folder = data_dir / 'canario'
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = folder / f'canario-{account}-{report["fecha"]}.json'
    path.write_text(json.dumps(report, ensure_ascii=False, indent=1))
    out(f'canario: {report["resultado"]} ({report["llamadas"]} llamadas, {report["segundos"]} s) -> {path}')
    if code == HALTED:
        out('DETENIDO: no reintentar; revisar a mano (python -m navegador estado).')
    return code


if __name__ == '__main__':
    sys.exit('Uso: python -m navegador canario <cuenta>')
