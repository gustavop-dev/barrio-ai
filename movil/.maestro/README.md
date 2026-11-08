# QA de la app en un emulador (Maestro + GitHub Actions)

Esta carpeta tiene los flujos de [Maestro](https://maestro.dev) que **usan la app como Gustavo**: tocan, escriben, deslizan, arrastran hojas y comprueban lo que tiene que aparecer en cada pantalla. Corren solo en GitHub Actions (`.github/workflows/qa-movil.yml`), en un emulador Android, contra una oficina de demostración sembrada en el propio runner. Nada se ejecuta en el portátil.

## Qué hace una ejecución

El workflow tiene cuatro jobs:

1. **`plan`** decide qué flujos corren y los reparte en hasta **4 emuladores en paralelo**, equilibrando su duración. En cada emulador los flujos van en orden numérico. `15-ajustes-sesion` cierra la sesión y vuelve a entrar al final, así que los flujos que vengan después en su emulador encuentran la sesión abierta.
2. **`apk`** compila la app una sola vez: `expo prebuild` y Gradle `assembleRelease -PreactNativeArchitectures=x86_64`. Es una build release, con el JS empaquetado y R8, igual que la de EAS, pero para el emulador x86_64. Usa `EXPO_PUBLIC_API_URL=http://10.0.2.2:8787`, que es el runner visto desde el emulador.
   - El APK queda en caché por el hash de lo que lo compone: `movil/` (sin esta carpeta ni los `.md`), `compartido/`, el `package-lock.json` y `app.config.js`.
   - Un push que solo cambia flujos, `seed_qa` o los scripts no vuelve a compilar: el job termina en segundos.
3. **`flujos (N)`** es un job por emulador, y cada uno es independiente:
   - **Backend propio:** PostgreSQL con pgvector, `migrate`, `bootstrap_local` y `seed_qa`. Gunicorn sirve la API en `0.0.0.0:8787` con `LIVE_LINKEDIN=false`, `LIVE_PROVIDERS=false` y `OPERATOR_ALLOW_FAKE=true`: conector simulado, sin LinkedIn real ni proveedores de pago.
   - **Emulador:** Android 15 x86_64 con KVM (`reactivecircus/android-emulator-runner`), 3 núcleos y 4 GB. El AVD se define ya con **390×844 dp** (780×1688 px a 320 dpi), el tamaño de los tableros de `diseno-movimiento/`. Las animaciones del sistema solo están activadas en `01-entrada`, `02-navegacion` y `03-oficina` (ver «Animaciones»). Redimensionar un pixel_6 después de arrancar colgaba el lanzador, y a 2× el render por software cuesta la mitad que a 3×. Cada flujo tiene un tope de 8 minutos (`QA_FLOW_TIMEOUT`): si se cuelga, falla con su captura y el emulador sigue con el siguiente.
   - **Flujos:** `scripts/qa/correr-maestro.sh` corre sus flujos uno a uno y **vuelve a sembrar el backend antes de cada uno**. Así un flujo nunca depende de lo que cambió otro, y un fallo apunta a una sola pantalla. La sesión de la app se conserva entre flujos.
4. **`qa`** junta los artefactos de todos los emuladores, compara las capturas con la referencia de `main` y cuenta la cobertura del catálogo. `scripts/qa/informe.py` escribe el resumen del job, el comentario del PR e `informe.html`. **Falla si falla un flujo o si la app se cae**: es el check que cuenta.

En un PR, una ejecución nueva cancela la anterior (`concurrency` con `cancel-in-progress`); en `main` cada ejecución termina, porque renueva la referencia visual.

### Por qué HTTP en claro solo en esta build

Android bloquea el HTTP sin cifrar en las builds release, y el backend del runner no tiene certificado. `app.config.js` añade `android:usesCleartextTraffic="true"` al manifiesto **solo cuando `OFFICE_QA_BUILD=1`**, y esa variable solo la pone este workflow. Los perfiles de EAS (`eas.json`) no la definen: el APK y el AAB de producción siguen aceptando solo HTTPS.

La misma condición apaga `updates.enabled`: el APK del emulador ejecuta el JS que lleva dentro y nunca consulta el servidor de actualizaciones de Expo al arrancar. Fuera de la QA la configuración nativa no cambia, así que la huella (`runtimeVersion: fingerprint`) de las builds de producción es la misma.

Se eligió una release con el JS empaquetado, en vez de una build debug, para probar lo mismo que se instala en el teléfono: Hermes, R8, sin Metro y sin el menú de desarrollo.

## Lanzar una QA

- **En un PR:** corre en todos los PR, para que `qa` pueda ser un check obligatorio. Si el PR no toca `movil/`, `compartido/`, `agentes-linkedin/`, `scripts/qa/` ni el workflow, `qa` pasa en segundos sin emulador.
- **En `main`:** después de cada push que toca la app y cada noche a las 03:00 de Bogotá, con todos los flujos. Esas ejecuciones guardan la referencia visual.
- **Solo algunos flujos:** pon `[qa: …]` en el mensaje del último commit del PR, con nombres o números separados por espacios o comas. Por ejemplo, `fix(movil): … [qa: 05-captura 09]` corre solo `05-captura` y `09-personas`. Sirve para arreglar un flujo sin volver a correr los once; antes de terminar, un push sin `[qa: …]` los corre todos.
- **A mano**, una vez que el workflow esté en `main`:

  ```bash
  gh workflow run qa-movil.yml                                  # todos, sobre main
  gh workflow run qa-movil.yml --ref mi-rama -f flujos="05 09"  # solo esos, sobre otra rama
  gh run watch $(gh run list --workflow qa-movil.yml --limit 1 --json databaseId --jq '.[0].databaseId')
  ```

Con el APK en caché, una ejecución completa tarda lo que el emulador más lento, unos 15 minutos. Si hay que compilar el APK, se suman unos 17.

## Revisar una ejecución (personas y agentes revisores)

```bash
scripts/qa/descargar.sh qa-descargas            # la última ejecución terminada
scripts/qa/descargar.sh qa-descargas --pr 42    # la última de un PR
scripts/qa/descargar.sh qa-descargas --run <id> # una concreta
```

Descarga el artefacto `qa-movil-<n>` en `qa-descargas/<run id>/`:

| Ruta | Qué es |
|---|---|
| `resumen.md` | flujos que pasan y fallan, si hubo crash, errores de JS, respuestas 5xx o 429 de la API |
| `informe.html` | el informe navegable: tabla de flujos con el motivo del fallo y, por flujo, sus capturas y su video |
| `capturas/NN-pantalla-SS-paso.png` | una captura por paso relevante, a 780×1688 (2× los tableros de 390×844) |
| `capturas/fallos/` | la captura que Maestro toma al fallar un paso, con el nombre del flujo delante |
| `videos/NN-flujo-parteK.mp4` | la grabación de la pantalla de cada flujo, en partes de menos de 3 minutos |
| `junit/NN-flujo.xml` | el informe JUnit de Maestro de cada flujo |
| `maestro/NN-flujo.log`, `maestro/NN-flujo/` | la salida de Maestro y su carpeta de depuración (comandos, jerarquía de la vista al fallar) |
| `logcat/logcat-errores.txt` | crashes, `FATAL EXCEPTION`, señales nativas, ANR y errores de `ReactNativeJS` |
| `logcat/logcat-app.txt` | todo lo que escribió el proceso de la app y React Native |
| `logcat/logcat-completo-N.txt.gz` | el logcat entero de cada emulador, comprimido |
| `seed-N.log`, `api-N.log`, `flujos-N.txt` | por emulador: la salida de `seed_qa`, el log de gunicorn y lo que tardó cada flujo |

Para comparar con el diseño, abre las capturas junto a los tableros `movil/diseno-movimiento/tableros/*.dc.html` (390×844) y `movil/MOTION.md`.

## El mundo de QA (`seed_qa`)

`agentes-linkedin/infra/src/team_backend/management/commands/seed_qa.py` crea un usuario `qa`, superusuario y solo de CI, con contraseña en `QA_PASSWORD`, y una oficina completa:

- las cuentas simuladas;
- una pieza en cada estado: programada para mañana y vetable, publicada con cortes de 72 h y de 7 días, bloqueada con ronda de reparación, saltada y fallida;
- comentarios y acciones de red pendientes, y acciones ya hechas para la Lista y el calendario;
- personas en cada etapa, oportunidades en varias etapas y referentes;
- todas las tarjetas de Tu turno: «¿Salió o no?», una conversación del inbox, preguntas de texto, de opción y de sí o no, una pospuesta, una caducada, la orientación del analista y dos aprobaciones de red (seguir a Laura, invitar a Julián: la red está en modo `approval` porque `OPERATOR_AUTONOMY` va vacío);
- notificaciones leídas y sin leer, y «Próximo»;
- una captura transcrita y una idea usada;
- cuatro fotos generadas en la Galería;
- unos 100 días de audiencia, trabajos y sincronizaciones de red para Resultados, el resumen semanal y filas de gasto.

Es idempotente: cada ejecución vacía el mundo de QA y lo vuelve a crear con los mismos ids y textos. Por eso **se niega a correr** si no está `QA_SEED=permitido`, si hay un interruptor `LIVE_*` activado o si la base tiene una cuenta real de LinkedIn. La prueba `team_backend/tests/test_seed_qa.py` lo cubre en el CI normal.

## Los flujos

| Flujo | Qué hace |
|---|---|
| `01-entrada` | la pantalla de entrada y «Entrar» desactivado; con el teclado abierto, la contraseña sigue a la vista; sin conexión, el aviso en español; contraseña equivocada; mostrar la contraseña; la correcta, la entrada animada y la Oficina; abrir otra vez sigue dentro; una sesión cerrada desde otro dispositivo vuelve a la entrada |
| `02-navegacion` | abrir la app sin conexión sigue dentro (la franja, y la red que vuelve); el contador y el punto de arriba; las cuatro pestañas de abajo, los cuatro accesos de arriba, el «atrás» de Android por el historial; una ficha cerrada con «‹», con atrás y arrastrando desde el borde; la firma; enlaces `oficina0ff1ce://` a una pestaña y a una pieza |
| `03-oficina` | tocar un personaje de la escena y ver su hoja con su estado real y lo último que hizo, arrastrarla a altura completa y cerrarla, la tira de equipos, «Ver en el Calendario» y la Biblioteca; arrastre y doble toque en la escena; tirar para recargar; la leyenda; la máquina en pausa (el aviso, la escena oscurecida y Ajustes) |
| `04-tu-turno` | la lista de arriba abajo una sola vez: «¿Salió o no?» con su nota, responder una pregunta, deslizar a la derecha y a la izquierda, «Más tarde», «Ya no es urgente», «Pospuestas», «Hecho recientemente» y «Lo que el equipo sabe de ti» |
| `04-tu-turno-aprobar` | aprobar una acción de red desde su tarjeta de Tu turno y otra desde «En cola» del calendario |
| `04-tu-turno-mas` | máquina detenida desde Ajustes y reanudada desde Tu turno, «Responder con audio», «Marcar como oportunidad», «No responder», descartar la orientación, responder con una opción y «Deshacer», «No quiero compartir esto» |
| `04-tu-turno-sabe` | «Lo que el equipo sabe de ti»: añadir, editar (v2) y retirar un dato |
| `05-captura` | desde Galería: abrir la hoja, «Para qué es», grabar desde la hoja, cerrar vacía y con algo («¿Cerrar sin enviar?»), mantener el botón, enviar, «Deshacer» en el aviso (vuelve el borrador), «Lo que enviaste» y «Deshacer» ahí |
| `05-captura-envios` | una foto del selector de Android y una nota de voz llegan al backend (aviso, Galería, «Lo que enviaste»); sin red (modo avión) y 413: el motivo, el borrador y «Reintentar» |
| `05-captura-contexto` | «Responder con audio» en Tu turno, «Nota de voz» en una persona y «Comentario para el equipo» con foto en una pieza, con su contexto en «Lo que enviaste» |
| `06-notificaciones` | «Próximo», filtros, tocar un aviso y llegar a la pieza o a la persona, «Marcar todo como leído» |
| `06-notificaciones-avisos` | Ajustes › Notificaciones: «Este dispositivo», «Probar notificación» y encender un tipo de push apagado por defecto, que sigue encendido tras reabrir la app |
| `06-notificaciones-destinos` | el resumen semanal, la captura procesada y la oportunidad sin contacto abren su destino |
| `07-calendario` | Semana, Mes y Lista; tocar días y su hoja; deslizar semanas y meses; la pieza de mañana, los pliegues de «Cómo se escribió», vetar y «Deshacer»; la pieza bloqueada y su ronda de reparación |
| `08-resultados` | el resumen semanal con «Usar como orientación» y «Descartar», cada uno con «Deshacer»; el «Periodo»; la definición de un gráfico; tocar una barra |
| `09-personas` | Barrio: pestañas, aviso de red apagada, filas, chips de etapa (con «En conversación» sin datos), búsqueda sin resultados y «Quitar filtros», «Más filtros» por rol; la ficha de Laura (recorrido, por qué encaja, de dónde salió, sin conversación, una nota nueva) y «Marcar como oportunidad» |
| `10-galeria` | la rejilla, los filtros (y uno vacío), la nota y el interruptor de edición con IA (y la foto abierta otra vez enseguida), el visor (zoom, deslizar, cerrar), «Quitar de la galería» y que las fotos son privadas |
| `10-galeria-subir` | «Subir fotos» con el selector de Android, un 413 con «Reintentar» y la Galería vacía |
| `11-ajustes` | de Máquina a Captura: parada total y reanudar, pausar la cuenta simulada, orientación (descartar y guardar), Autonomía, Gasto, «Conectar LinkedIn» abre la oficina web, micrófono y edición con IA |
| `12-oportunidades` | el tablero por etapas, mover con el selector y «Deshacer», que el cambio se guarde, «Cerradas sin acuerdo»; nueva oportunidad (obligatorios, «De Personas», fuera de la red, fecha inválida), editar y eliminar |
| `13-referentes` | la lista, «Observar ahora», desactivar con «Deshacer» y reactivar, la validación al añadir, un perfil que LinkedIn no conoce, «Referente añadido», quitar con confirmación y una cuenta sin referentes |
| `14-fichas` | la conversación de Sofía, la oportunidad y la nota de Andrés, descartar a Pedro con motivo y el enlace a una persona que no existe |
| `15-ajustes-sesion` | un tipo de aviso apagado y encendido, cerrar la sesión del Pixel 7, «Lo que el equipo sabe de ti», `?ancla=autonomia` y cerrar sesión (vuelve a entrar al final) |

## Escribir o cambiar un flujo

- Un archivo por área (`NN-area.yaml`), que empieza con `- runFlow: comun/entrar.yaml`.
- Captura en cada paso relevante con `takeScreenshot: NN-area-SS-paso`, en minúsculas ASCII y con guiones.
- Selectores, por orden de preferencia: `id:` (el `testID` de React Native) y después el texto o la etiqueta de accesibilidad. Si falta un selector estable, añade un `testID` mínimo en la app.
- Cada interacción va seguida de lo que tiene que aparecer (`assertVisible`, `extendedWaitUntil`). Un flujo que solo hace capturas no detecta nada.
- El emulador usa render por software y es lento. Espera con `extendedWaitUntil` y timeouts de 20 a 30 s. La escena de la Oficina se anima sin parar: no uses `waitForAnimationToEnd` sin `timeout`.
- Los flujos no se prueban en el portátil: haz push y mira el PR, o lanza `gh workflow run qa-movil.yml --ref tu-rama`.
- **Sin conexión:** `setAirplaneMode: enabled` corta la red del emulador (el backend del runner deja de verse). Un flujo que lo usa pone `onFlowComplete: [setAirplaneMode: disabled]`, para no dejar al siguiente sin red aunque falle un paso.
- **Lo que haría otro dispositivo o la máquina:** `comun/qa-api.js` llama a la API del backend del runner como otro teléfono del usuario `qa`. `ACCION: cerrar-este-telefono` cierra la sesión del emulador desde «Dispositivos con la app» (la siguiente petición de la app recibe un 401); `pausar` y `reanudar` paran y reanudan la máquina.

## Lo que no se automatiza

- **La voz.** El emulador del runner arranca con `-noaudio`: el micrófono abre y graba silencio. Las capturas con audio viajan como un m4a real y llegan al backend, pero la transcripción (que en CI no corre) y la voz de verdad se prueban en el teléfono.
- **Los avisos push reales.** Necesitan las credenciales de FCM y el servicio de Expo, y la QA no usa secretos ni servicios externos. Se prueba la pantalla de Ajustes › Notificaciones, no la entrega.
- **La cámara** (`-camera-back none`). El selector de fotos sí: `correr-maestro.sh` deja una de las fotos sembradas en `Pictures` y `comun/elegir-foto.yaml` la elige.
- **Abrir LinkedIn**: los enlaces del mundo de QA apuntan a `linkedin.example`, nunca a linkedin.com.

## Cobertura del catálogo

El resumen de cada ejecución dice **«X de Y funcionalidades de la app cubiertas por E2E»**, con la lista de las que faltan agrupadas por área (`scripts/qa/cobertura.py`):

- **Y** son las fichas de `docs/funcionalidades/*.md` cuyo «Dónde» incluye `app` y cuyo «Estado» es `funciona` o `parcial`.
- **X** son las de Y que aparecen en la cabecera `# cubre: ID, ID` de algún flujo, antes de su `---`. Un `# cubre:` en mitad del flujo documenta un paso, pero no suma.
- También dice cuántas de ellas cubren flujos que pasaron en esa ejecución, y avisa de IDs en `# cubre:` que no existen en el catálogo.

`python3 scripts/qa/cobertura.py` da el mismo recuento sin correr nada (`--json` para máquinas).

## Regresión visual

Cada ejecución compara sus capturas con la **referencia de `main`** (`scripts/qa/visual.py`):

- **La referencia es un artefacto, no está en el repo.** Las ejecuciones en `main` suben `qa-movil-referencias`: sus capturas a 390×844, encima de la referencia anterior para los flujos que no corrieron, guardadas 90 días. Así no se versionan cientos de PNG en git, y la referencia es siempre lo último que se fusionó. Un PR compara contra la última ejecución de `main` que guardó una.
- **Cómo compara:** lleva las dos imágenes a 390×844, deja fuera la barra de estado y las máscaras configuradas, y cuenta un píxel como cambiado cuando un canal se mueve más de `umbral_pixel`. Una captura cambia cuando la parte cambiada supera su `tolerancia`, por defecto 1,5 %.
- **Lo que deja:** para cada captura que cambia, `visual/<captura>.png` en el artefacto, con antes, después y los píxeles cambiados en rojo. El resumen y el comentario del PR las listan, la ejecución lleva un aviso y aparece el check **«QA visual»**: neutro si algo cambió, verde si no.
- **No hace fallar la ejecución:** un cambio visual puede ser buscado. Quien revisa mira `visual/` y decide; al fusionar, la siguiente ejecución en `main` lo convierte en referencia.
- **Ajustes** en `scripts/qa/visual.json`: tolerancia, máscaras `[x, y, ancho, alto]` en dp e `ignorar`, por patrón de nombre. Por ejemplo, las capturas del calendario toleran más porque sus fechas cambian cada día.

## Fallos simulados (interruptor de QA)

Para probar los estados de error y los vacíos, el backend de la QA puede hacer que un endpoint responda 5xx, 413 o 429, que tarde, que se agote el tiempo o que devuelva sus listas vacías.

- **Solo existe en la QA.** Vive en `linkedin_backend/settings_qa.py`, que el workflow usa para gunicorn y que se niega a cargar sin `QA_MODE=true`. Los settings de producción no tienen el middleware ni la ruta de control. `team_backend/tests/test_qa_fallos.py` prueba que en producción no hace nada, aunque haya reglas o cabeceras.
- **Desde un flujo** se arma con un script que corre en el runner, junto a la API:

  ```yaml
  - runScript:
      file: comun/qa-fallo.js
      env:
        RUTA: '^/api/v1/capturas$'   # regex sobre el path (obligatoria)
        EFECTO: '500'                 # 500 | 502 | 503 | 504 | 413 | 429 | timeout | lento | vacio
        METODO: POST                  # opcional; por defecto, cualquiera
        VECES: '1'                    # opcional; cuántas peticiones afecta, -1 hasta limpiar (por defecto 1)
        SEGUNDOS: '30'                # opcional; para timeout (después responde 504) y lento
  - tapOn: …                          # la acción que debe fallar
  - assertVisible: …                  # el mensaje de error que debe ver Gustavo
  - runScript: comun/qa-fallos-limpiar.js   # opcional: el script de la QA limpia todo antes de cada flujo
  ```

- **`vacio`** devuelve la respuesta real con sus listas vacías, los contadores (`count`, `unread`, `urgent_count`, `total`) a 0 y `top` en `null`. Sirve para los estados vacíos sin otra siembra.
- **Por HTTP** (curl o pruebas del backend): `POST /api/v1/qa/fallos` con una regla o una lista, `GET` para verlas, `DELETE` para limpiarlas. También vale la cabecera `X-QA-Fallo: 503` en una petición.

## Animaciones

`scripts/qa/correr-maestro.sh` pone las escalas de animación del sistema a 1 solo para los flujos de `QA_FLUJOS_ANIMADOS` (en el workflow, `01-entrada 02-navegacion 03-oficina`; sin la variable, `01-entrada 03-oficina`) y a 0 para el resto. `02-navegacion` la necesita: con movimiento reducido las pestañas cambian sin su push, y la pantalla en blanco al volver con atrás entre dos pantallas de la barra superior (ejecución 42451843664) solo ocurría con él.

- Con 0, la app usa movimiento reducido y la escena de la Oficina queda quieta. Maestro ve cada pantalla asentarse al momento, en vez de esperar 20 a 100 s por paso sobre la escena animada con el render por software del emulador.
- Un flujo que necesite el movimiento se añade a la lista, en el workflow (`QA_FLUJOS_ANIMADOS`), no en el flujo.

## Check obligatorio para los PR (lo aplica Gustavo)

`qa` corre en todos los PR y pasa en segundos cuando el PR no toca la app, así que puede exigirse sin bloquear los PR de documentación. Cambiar la protección de `main` necesita permisos de administrador.

1. Comprueba que `qa` ya pasó en algún PR. El nombre del check es exactamente `qa`, el último job de «QA móvil».
2. Crea una regla del repositorio que exija `qa` en `main`, dejando que los administradores la salten en una urgencia:

   ```bash
   gh api -X POST repos/gustavop-dev/barrio-ai/rulesets --input - <<'EOF'
   {
     "name": "main · QA móvil obligatoria",
     "target": "branch",
     "enforcement": "active",
     "conditions": { "ref_name": { "include": ["~DEFAULT_BRANCH"], "exclude": [] } },
     "rules": [
       { "type": "required_status_checks",
         "parameters": {
           "strict_required_status_checks_policy": false,
           "required_status_checks": [ { "context": "qa", "integration_id": 15368 } ] } }
     ],
     "bypass_actors": [ { "actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always" } ]
   }
   EOF
   ```

   - `15368` es la app de GitHub Actions.
   - `actor_id: 5` es el rol de administrador del repositorio.
   - Lo mismo se hace en la web: Settings › Rules › Rulesets › New branch ruleset › «Require status checks to pass» › `qa`.

3. Verifica con `gh api repos/gustavop-dev/barrio-ai/rulesets`. Para quitarla: `gh api -X DELETE repos/gustavop-dev/barrio-ai/rulesets/<id>`.

No conviene exigir los jobs de «Barrio AI» (`backend`, `movil`, `oficina`) de la misma forma: ese workflow solo corre cuando cambian ciertas rutas, y un check exigido que nunca aparece deja el PR esperando para siempre.

