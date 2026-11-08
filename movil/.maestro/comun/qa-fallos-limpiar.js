// Clears every simulated backend failure (QA failure switch, team_backend.qa_fallos; see ../README.md).
//   - runScript: comun/qa-fallos-limpiar.js
var api = typeof QA_API !== 'undefined' && QA_API ? QA_API : 'http://127.0.0.1:8787';
var respuesta = http.delete(api + '/api/v1/qa/fallos', {});
if (respuesta.status !== 200) throw new Error('No se pudieron limpiar los fallos de QA (' + respuesta.status + '): ' + respuesta.body);
