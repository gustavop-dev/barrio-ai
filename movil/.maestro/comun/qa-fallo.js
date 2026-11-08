// Arms a simulated backend failure from a flow (QA failure switch, team_backend.qa_fallos; see ../README.md).
// The script runs on the CI runner, next to the API. Use it in a flow like this:
//   - runScript:
//       file: comun/qa-fallo.js
//       env:
//         RUTA: '^/api/v1/capturas$'   # regex on the request path (required)
//         EFECTO: '500'                 # 500 | 502 | 503 | 504 | 413 | 429 | timeout | lento | vacio (required)
//         METODO: POST                  # optional, default any method
//         VECES: '1'                    # optional, how many requests it hits; -1 until cleared (default 1)
//         SEGUNDOS: '30'                # optional, for timeout (then 504) and lento
// The run script clears every rule before each flow; comun/qa-fallos-limpiar.js clears them inside a flow.
var api = typeof QA_API !== 'undefined' && QA_API ? QA_API : 'http://127.0.0.1:8787';
var regla = { ruta: RUTA, efecto: EFECTO };
if (typeof METODO !== 'undefined' && METODO) regla.metodo = METODO;
if (typeof VECES !== 'undefined' && VECES) regla.veces = parseInt(VECES, 10);
if (typeof SEGUNDOS !== 'undefined' && SEGUNDOS) regla.segundos = parseFloat(SEGUNDOS);
var respuesta = http.post(api + '/api/v1/qa/fallos', { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(regla) });
if (respuesta.status !== 201) throw new Error('No se pudo armar el fallo de QA (' + respuesta.status + '): ' + respuesta.body);
output.qaFallo = JSON.parse(respuesta.body).reglas[0];
