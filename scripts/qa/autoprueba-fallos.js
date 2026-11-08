// Part of autoprueba-fallos.yaml: GET /health must answer ESPERADO.
var api = typeof QA_API !== 'undefined' && QA_API ? QA_API : 'http://127.0.0.1:8787';
var r = http.get(api + '/health');
if (String(r.status) !== ESPERADO) throw new Error('GET /health respondió ' + r.status + ', se esperaba ' + ESPERADO);
