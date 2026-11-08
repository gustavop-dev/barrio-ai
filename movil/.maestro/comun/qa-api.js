// Does, through the QA backend's API, what another device or the machine would do while a flow runs. The script runs on
// the CI runner, next to the API (never production: QA_API defaults to the runner's own backend). Use it in a flow:
//   - runScript:
//       file: comun/qa-api.js
//       env:
//         ACCION: cerrar-este-telefono   # cerrar-este-telefono | pausar | reanudar
//         QA_USER: ${QA_USER}            # the QA user and its password (correr-maestro.sh passes them with -e)
//         QA_PASSWORD: ${QA_PASSWORD}
// - cerrar-este-telefono (ACC-05, ACC-09): another phone of the QA user logs in and closes every other device login,
//   this emulator's included, as «Dispositivos con la app» does; then it logs itself out. seed_qa recreates the seeded
//   second phone before the next flow.
// - pausar / reanudar (OFI-07): stops or resumes the whole machine (POST /api/v1/operador/control), as Ajustes does.
var api = typeof QA_API !== 'undefined' && QA_API ? QA_API : 'http://127.0.0.1:8787';
var json = { 'Content-Type': 'application/json' };

function call(method, path, token, body) {
  var options = { headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + token } };
  if (body !== undefined) options.body = JSON.stringify(body);
  var response = method === 'GET' ? http.get(api + path, options) : method === 'DELETE' ? http.delete(api + path, options) : http.post(api + path, options);
  if (response.status >= 400) throw new Error(method + ' ' + path + ' respondió ' + response.status + ': ' + response.body);
  return response.body ? JSON.parse(response.body) : null;
}

var login = http.post(api + '/api/v1/auth/token', {
  headers: json,
  body: JSON.stringify({ username: QA_USER, password: QA_PASSWORD, device_name: 'Otro teléfono (QA)' }),
});
if (login.status !== 201) throw new Error('No se pudo entrar como ' + QA_USER + ' (' + login.status + '): ' + login.body);
var token = JSON.parse(login.body).token;

if (ACCION === 'cerrar-este-telefono') {
  var closed = 0;
  var devices = call('GET', '/api/v1/auth/dispositivos', token);
  for (var i = 0; i < devices.length; i++) {
    if (devices[i].current) continue;
    call('DELETE', '/api/v1/auth/dispositivos/' + devices[i].id, token);
    closed++;
  }
  output.qaApi = { cerrados: closed };
} else if (ACCION === 'pausar' || ACCION === 'reanudar') {
  output.qaApi = call('POST', '/api/v1/operador/control', token, { paused: ACCION === 'pausar', reason: ACCION === 'pausar' ? 'Pausa de la QA' : '' });
} else {
  throw new Error('ACCION desconocida: ' + ACCION);
}
call('POST', '/api/v1/auth/token/revocar', token, {});
