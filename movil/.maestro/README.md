# QA de la app en un emulador (Maestro + GitHub Actions)

Esta carpeta tiene los flujos de [Maestro](https://maestro.dev) que **usan la app como Gustavo**: tocan, escriben, deslizan, arrastran hojas y comprueban lo que tiene que aparecer en cada pantalla. Corren solo en GitHub Actions (`.github/workflows/qa-movil.yml`), en un emulador Android, contra una oficina de demostración sembrada en el propio runner. Nada se ejecuta en el portátil.

## Qué hace una ejecución

El workflow tiene cuatro jobs:

1. **`plan`** decide qué flujos corren y los reparte en hasta **8 emuladores en paralelo**, equilibrando el número de líneas como aproximación de la duración. Usa `min(8, flujos seleccionados)` emuladores; `QA_MAX_SHARDS` permite otro límite al invocar el script. En cada emulador los flujos van en orden numérico. `15-ajustes-sesion` cierra la sesión y vuelve a entrar al final, así que los flujos que vengan después en su emulador encuentran la sesión abierta.
2. **`apk`** combina un shell nativo release x86_64 con el JS actual. Todos los pasos usan `OFFICE_QA_BUILD=1`, `EXPO_PUBLIC_API_URL=http://10.0.2.2:8787`, `NODE_ENV=production` y `EXPO_NO_DOTENV=1` (sin cargar `.env` implícitos).
   - **Caché nativa:** después de `npm ci`, exporta con `expo export:embed` y compila el bundle con el Hermes del lockfile. Calcula `@expo/fingerprint` para Android, antes de generar `android/`, con preset estricto, configuración, plugins, lockfile, entorno de QA y los recursos que Metro referencia. Si falta esa huella, hace `expo prebuild` y Gradle `assembleRelease -PreactNativeArchitectures=x86_64`, y guarda el APK nativo con su keystore debug y el inventario de assets.
   - **Cambios de JS/TS:** con la misma huella no hay prebuild ni Gradle. Sustituye `assets/index.android.bundle` y los assets acompañantes de Metro; elimina los que ya no existen. Conserva los recursos Android compilados, elimina las firmas anteriores, hace `zipalign -P 16` y firma con `apksigner` y el keystore debug del shell. La ruta fría usa también este reempaquetado, para comprobarlo desde la primera ejecución.
   - **Imágenes, fuentes y otros recursos:** un cambio en los nombres o contenidos exportados a `res/` cambia la huella, incluso si viene de un nuevo `require()` en JS. Necesita build nativa porque Android registra esos recursos en `resources.arsc`; copiar archivos nuevos al ZIP no los registra. No se sobrescribe XML compilado con XML de texto.
   - **Caché del APK final:** evita incluso npm/Metro cuando solo cambian flujos, documentación, backend o los scripts de selección/informe. Los emuladores restauran esta caché, que contiene el JS de esta revisión.
3. **`flujos (N)`** es un job por emulador, y cada uno es independiente:
   - **Backend propio:** PostgreSQL con pgvector, `migrate`, `bootstrap_local` y `seed_qa`. Gunicorn sirve la API en `0.0.0.0:8787` con `LIVE_LINKEDIN=false`, `LIVE_PROVIDERS=false` y `OPERATOR_ALLOW_FAKE=true`: conector simulado, sin LinkedIn real ni proveedores de pago.
   - **Emulador:** Android 15 x86_64 con KVM (`reactivecircus/android-emulator-runner`), 3 núcleos y 4 GB. El AVD se define ya con **390×844 dp** (780×1688 px a 320 dpi), el tamaño de los tableros de `diseno-movimiento/`. Las animaciones del sistema solo están activadas en `01-entrada`, `02-navegacion` y `03-oficina` (ver «Animaciones»). Redimensionar un pixel_6 después de arrancar colgaba el lanzador, y a 2× el render por software cuesta la mitad que a 3×. Cada flujo tiene un tope de 8 minutos (`QA_FLOW_TIMEOUT`): si se cuelga, falla con su captura y el emulador sigue con el siguiente.
   - **Flujos:** `scripts/qa/correr-maestro.sh` corre sus flujos uno a uno y **vuelve a sembrar el backend antes de cada uno**. Así un flujo nunca depende de lo que cambió otro, y un fallo apunta a una sola pantalla. La sesión de la app se conserva entre flujos.
4. **`qa`** junta los artefactos de todos los emuladores, compara las capturas con la referencia de `main` y cuenta la cobertura del catálogo. `scripts/qa/informe.py` escribe el resumen del job, el comentario del PR e `informe.html`. **Falla si falla un flujo o si la app se cae**: es el check que cuenta.

En un PR, una ejecución nueva cancela la anterior (`concurrency` con `cancel-in-progress`); en `main` cada ejecución termina, porque renueva la referencia visual.

Las claves son `apk-native-v2-Linux-x86_64-<huella>` y `apk-qa-v2-Linux-x86_64-<hashFiles>`. La segunda usa `hashFiles('movil/**', '!movil/.maestro/**', '!movil/**/*.md', 'compartido/**', 'scripts/qa/apk-*', '.github/workflows/qa-movil.yml')`. El resumen del job muestra las claves y los aciertos; el artefacto `qa-apk-fingerprint` conserva las fuentes de la huella para diagnosticar un miss inesperado. Las cachés de GitHub respetan el ámbito de rama/PR: `main` sirve de base para los PR; un shell creado en un PR no calienta otro PR.

**Forzar una build nativa completa:** sube `APK_CACHE_VERSION` en `.github/workflows/qa-movil.yml` (actualmente `v2`). Invalida ambas cachés. Hazlo también si cambias los pasos de compilación o el empaquetado. `[qa: todos]` fuerza todos los flujos, pero no invalida el APK.

### Por qué HTTP en claro solo en esta build

Android bloquea el HTTP sin cifrar en las builds release, y el backend del runner no tiene certificado. `app.config.js` añade `android:usesCleartextTraffic="true"` al manifiesto **solo cuando `OFFICE_QA_BUILD=1`**, y esa variable solo la pone este workflow. Los perfiles de EAS (`eas.json`) no la definen: el APK y el AAB de producción siguen aceptando solo HTTPS.

La misma condición apaga `updates.enabled`: el APK del emulador ejecuta el JS que lleva dentro y nunca consulta el servidor de actualizaciones de Expo al arrancar. Fuera de la QA la configuración nativa no cambia, así que la huella (`runtimeVersion: fingerprint`) de las builds de producción es la misma.

Se eligió una release con el JS empaquetado, en vez de una build debug, para probar lo mismo que se instala en el teléfono: Hermes, R8, sin Metro y sin el menú de desarrollo.

## Lanzar una QA

- **En un PR sin etiqueta:** `scripts/qa/seleccion.json` cruza las rutas cambiadas con carpetas de área, prefijos de flujo y las cabeceras `# cubre:`. Une la selección de todos los archivos, incluidos los nombres anteriores de archivos renombrados. Por ejemplo, `capture/**` selecciona `05-*` y `10-*`; `login.tsx`, `01-*`; Calendario, `07-*` y otros flujos que declaran `CAL-*`. Cambiar un flujo selecciona ese flujo. Los helpers comunes, UI, tema, autenticación, API, `compartido/`, `agentes-linkedin/`, `seed_qa`, scripts de QA, workflow o **cualquier ruta sin mapa** seleccionan todos. Si la lista de GitHub falla o puede estar truncada, también van todos. Solo las rutas documentales explícitas de `ignorar` permiten pasar sin emulador.
- **En `main`:** después de cada push que toca la app y cada noche a las 03:00 de Bogotá, con todos los flujos. Esas ejecuciones guardan la referencia visual.
- **Solo algunos flujos:** pon `[qa: …]` en el mensaje del último commit del PR, con nombres o números separados por espacios o comas. Conserva la selección por nombre, prefijo o fragmento: `[qa: 05-captura 09]` corre todos los `05-captura*` y `09-personas`. La etiqueta tiene prioridad sobre el mapa automático; `[qa: todos]` corre la suite completa. Quitar la etiqueta vuelve a la selección automática. Los pushes a `main` y las ejecuciones nocturnas siempre corren todos los flujos.
- **A mano**, una vez que el workflow esté en `main`:

  ```bash
  gh workflow run qa-movil.yml                                  # todos, sobre main
  gh workflow run qa-movil.yml --ref mi-rama -f flujos="05 09"  # solo esos, sobre otra rama
  gh run watch $(gh run list --workflow qa-movil.yml --limit 1 --json databaseId --jq '.[0].databaseId')
  ```

El objetivo del job `apk` para cambios solo de JS/TS es **2–4 minutos** con el shell nativo en caché; una build nativa sigue costando unos 13–17 minutos. El tiempo total depende además del emulador más lento y de la cola de GitHub; hay que medirlo en CI.

En las primeras ejecuciones, comprobar una ruta fría y después un cambio de JS con la misma huella: prebuild/Gradle deben quedar omitidos en la segunda, la firma y alineación deben pasar, y el emulador debe mostrar el cambio nuevo, las imágenes y las fuentes, iniciar sesión contra `10.0.2.2` y arrancar sin OTA. Verificar también una selección pequeña, `[qa: todos]` con 8 shards y un cambio nativo que invalide la huella. Al actualizar Expo/RN, revisar `assets/index.android.bundle`, las rutas `generated/{assets,res}/react/release`, Hermes y los recursos: el script falla si deja de coincidir el contrato del shell. La implementación se preparó mediante lectura de código; la validación de ejecución se hace únicamente en CI.

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
- una captura transcrita, una idea usada y una captura urgente con evidencia y fecha prevista;
- foto en `manana`, infografía en `aprobacion` y carrusel de cuatro láminas con PDF y alt en `publicada8`;
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
| `16-imagenes` | detalle con foto y veto, infografía con revisión, carrusel de cuatro láminas por swipe y botones; «Lo antes posible» con previsión, evidencia y condiciones en Lo que enviaste |
| `17-mapa-equipo` | mapa desde Oficina y Ajustes, grupos, unidades del curso, conexiones de ida/vuelta, nodos en diseño y actividad real |
| `05-captura` | desde Galería: abrir la hoja, «Para qué es», grabar desde la hoja, cerrar vacía y con algo («¿Cerrar sin enviar?»), mantener el botón, enviar, «Deshacer» en el aviso (vuelve el borrador), «Lo que enviaste» y «Deshacer» ahí |
| `05-captura-envios` | una foto del selector de Android y una nota de voz llegan al backend (aviso, Galería, «Lo que enviaste»); sin red (modo avión) y 413: el motivo, el borrador y «Reintentar» |
| `05-captura-contexto` | «Responder con audio» en Tu turno, «Nota de voz» en una persona y «Comentario para el equipo» con foto en una pieza, con su contexto en «Lo que enviaste» |
| `06-notificaciones` | «Próximo», filtros, tocar un aviso y llegar a la pieza o a la persona, «Marcar todo como leído» |
| `06-notificaciones-avisos` | Ajustes › Notificaciones: «Este dispositivo», «Probar notificación» y encender un tipo de push apagado por defecto, que sigue encendido tras reabrir la app |
| `06-notificaciones-destinos` | el resumen semanal, la captura procesada y la oportunidad sin contacto abren su destino |
| `07-calendario` | Semana, Mes y Lista; deslizar semanas y meses; un mes sin nada y un día a más de 15 días; la hoja del día y el panel de un día con reunión, uno sin pieza y el de ayer con «Ver todo lo del día» filtrado; «En cola»: vetar una acción de red (se envía a los 5 s) y una reacción con «Deshacer»; «Lo que pasó» por tipo y con «Mostrar lo que no salió» |
| `07-pieza-veto` | la pieza de mañana: cabecera, «Copiar», «Comentario para el equipo», vetar y «Deshacer», los pliegues de «Cómo se escribió», el veto que se envía a los 5 s («La vetaste») y «Preparar la siguiente pieza» |
| `07-pieza-estados` | las piezas pasadas desde su día: bloqueada (y la capa «Red» apagada), publicada con sus cortes y «—», saltada y fallida; la hoja a altura completa deja tocar otro día |
| `07-calendario-errores` | con el interruptor de fallos: el calendario, la actividad, la pieza y la pieza del día fallan («Reintentar»); un veto rechazado; «Próximo» y «Lo que pasó» vacíos |
| `08-resultados` | el resumen semanal con «Usar como orientación» y «Descartar», cada uno con «Deshacer»; el «Periodo» y la «Modalidad»; los accesos a cada sección; un dato que falta como «—» con su motivo; la definición de un gráfico; tocar una barra, una oportunidad activa y el mejor post |
| `08-resultados-errores` | con el interruptor de fallos: las cifras y el resumen semanal fallan, «Reintentar»; un periodo sin posts ni oportunidades activas |
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

`qa` corre en todos los PR y pasa en segundos cuando solo cambian las rutas documentales ignoradas por el mapa, así que puede exigirse sin bloquear esos PR. Cambiar la protección de `main` necesita permisos de administrador.

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


## Sesión viva de QA: iterar sobre un arreglo

`qa-sesion.yml` mantiene un runner, el backend de QA, un emulador y Metro durante el ciclo de arreglar, hacer push y volver a probar. Úsalo para unos pocos flujos afectados por un bug de JS o de UI. Tras el arranque, el objetivo es recibir resultados en 1–5 minutos por push; depende de los flujos elegidos, no es un plazo garantizado. Un flujo puede llegar al límite de 8 minutos. La primera sesión con cachés frías todavía debe compilar el dev client y preparar el AVD.

`qa-movil` sigue siendo la comprobación final del PR, de los cambios nativos y de las fusiones: prueba el APK release y conserva cobertura y regresión visual. La sesión usa un APK debug con `expo-dev-client` y bundles de producción servidos por Metro; no sustituye ese check ni cambia sus triggers. Los pushes pueden seguir disparando también `qa-movil`.

### Abrir la sesión y leer los resultados

La rama vigilada debe pertenecer al mismo repositorio y contener los archivos de la sesión. Cuando el workflow ya esté en la rama por defecto:

```bash
gh workflow run qa-sesion.yml -f rama=mi-rama
# Con selección inicial y duración distinta (la preparación cuenta dentro del plazo):
gh workflow run qa-sesion.yml -f rama=mi-rama -f minutos=120 -f flujos="05-captura 09"
# Para elegir la versión del workflow, cuando GitHub ya lo tenga registrado:
gh workflow run qa-sesion.yml --ref mi-rama -f rama=mi-rama -f flujos="01"
```

`rama` es el código que el runner vigila; `--ref` elige la versión del workflow. `flujos` solo se aplica al primer head observado. Después, el **último** tag `[qa: ...]` del mensaje del commit head decide qué correr, con la misma selección que `plan.py`: nombres, números o fragmentos separados por espacios o comas; `todo`, `todos` y `all` seleccionan todos.

```bash
git commit -am 'fix(movil): corregir el teclado [qa: 01-entrada]'
git push
scripts/qa/sesion-resultado.sh mi-rama
# SHA explícito y carpeta base de descarga:
scripts/qa/sesion-resultado.sh mi-rama <sha> --carpeta /tmp/qa-revision --espera 1800
```

El lector usa `gh` autenticado, Git, Python 3, `jq` y `tar`; no instala dependencias ni ejecuta la app. Por defecto espera el SHA de `HEAD`, consulta cada 15 segundos y termina a los 1800 segundos. Guarda los archivos en `<carpeta>/<sha>/` (por defecto `qa-sesion-resultados/<sha>/`), sin sobrescribir una carpeta existente, e imprime `resumen.md`. Sale con 0 para `ok` o `idle`, con 1 si hay un fallo o la sesión se detuvo, y con 124 si agotó la espera. `QA_REPO=owner/repo` permite elegir el repositorio; sin esa variable se infiere con `gh repo view`.

**Sin tag no se ejecuta ningún flujo:** se publica `idle`. Esto difiere deliberadamente de `qa-movil`, donde un push sin tag pide todos. Para pedir todos en la sesión usa `[qa: todos]`; un tag vacío también selecciona todos, igual que `plan.py`. Si llega otro push mientras corre Maestro, se cancela esa iteración y se pasa al nuevo head; no se garantiza un resultado para los heads intermedios.

### Qué conserva la sesión

- El backend usa PostgreSQL/pgvector, `bootstrap_local`, `seed_qa`, `settings_qa`, `QA_MODE=true` y el interruptor de fallos de `qa-movil`. Antes de cada flujo vuelve a sembrar y limpia los fallos; si alguna operación falla, el flujo falla. Solo `01-entrada`, `02-navegacion` y `03-oficina` mantienen las animaciones del sistema. No se usan secretos del repositorio ni proveedores reales.
- El APK debug x86_64 se guarda bajo `qa-devclient-<huella>`. La huella usa objetos Git de los manifiestos y lockfiles, app config, plugins, módulos, parches, assets nativos, scripts de generación y receta del workflow. El JS de la app y de `compartido/`, los flujos y sus docs quedan fuera. Es una huella conservadora: cambiar una dependencia JS o la receta también puede pedir APK nuevo. Los plugins locales deben vivir en `movil/plugins/`, `movil/modules/` o las rutas declaradas en `sesion-util.py`; añade a esa lista cualquier otra entrada nativa local. Un acierto de caché omite prebuild y Gradle.
- El AVD y su snapshot son los mismos de `qa-movil`: Android 35, x86_64, 390×844 dp a 320 dpi. Se instala el APK una vez. `OFFICE_QA_BUILD=1` mantiene HTTP habilitado y `updates.enabled=false`.
- El comando exacto es `npx expo start --dev-client --no-dev --minify --port 8081`, con `EXPO_PUBLIC_API_URL=http://10.0.2.2:8787`, `EXPO_NO_DOTENV=1`, `EXPO_OFFLINE=1` y el host anunciado de Metro en `localhost`. La API se alcanza por `10.0.2.2:8787`; solo Metro lleva `adb reverse tcp:8081 tcp:8081`.
- El enlace es `oficina0ff1ce://expo-development-client/?url=http%3A%2F%2Flocalhost%3A8081&disableOnboarding=1`. Antes de correr flujos se pide con curl la URL del bundle anunciada por Expo y se comprueba que contiene el SHA nuevo. La sonda se añade solo a archivos generados del runner. La app vuelve a abrir el proyecto de Metro al comenzar cada iteración; con `--no-dev` se fuerza esa recarga en vez de depender de Fast Refresh.
- `sesion-abrir.yaml` abre ese enlace y atiende la introducción/menú del dev client. Se inserta después de `launchApp` en **copias temporales** de los flujos, también después de `clearState` de `01-entrada`. Los flujos originales siguen intactos. El runner conserva Metro, APK y emulador entre pushes. Si cambia el backend, sincroniza sus dependencias y migraciones y reinicia solo gunicorn antes de probar, para evitar ejecutar Python del head anterior.

Después de cada iteración se fuerza la rama `qa-sesion/<rama>` a un **commit sin padre** que contiene únicamente el último resultado: `resultado.json`, `head-sha.txt`, `resumen.md`, un JUnit por flujo y logs de Maestro. Solo se copian capturas de flujos fallidos (hasta tres por flujo y 20 MiB en total); los logs publicados se limitan a 256 KiB cada uno y no se guardan videos. El resumen incluye PASS/FAIL, paso o motivo del fallo, SHA y tiempos. Se crea o actualiza un único comentario del bot marcado `<!-- qa-sesion -->` en el PR; si la rama aún no tiene PR, los resultados siguen disponibles en la rama de resultados. El lector fija el commit de resultados antes de descargar, para evitar mezclar dos publicaciones.

### Límites y primer arranque en GitHub

Una sesión por rama: iniciar otra cancela la anterior. El job tiene un límite de 6 horas; `minutos` acepta de 1 a 345, por defecto 330, contados desde el comienzo de la preparación y dejando margen para publicar/cerrar. La sesión también termina cuando el PR se fusiona o se cierra. No hay historial de resultados en la rama: una nueva iteración reemplaza la anterior. Cambiar el controlador requiere iniciar otra sesión, porque el proceso conserva una copia fuera del checkout.

Si cambia la huella antes de un reset, la sesión publica **«Cambió lo nativo: corre qa-movil (APK nuevo)»** y termina. Corre `qa-movil` y abre una sesión nueva para obtener el nuevo dev client. Esta sesión es para ramas del mismo repositorio; no para PRs de forks.

En la primera ejecución hay que comprobar en GitHub:

1. Que el dev-client launcher y el menú se cierran, incluso después de `clearState`; sus textos pueden cambiar entre versiones.
2. Que `adb reverse` lleva Metro a `localhost:8081`, mientras `10.0.2.2:8787` sigue siendo la API. Prueba los pasos de modo avión: Metro debe seguir disponible por el transporte de adb y la API debe quedar sin conexión. Estas reaperturas con Metro no prueban el arranque offline de un APK release.
3. Que Expo 58/dev client acepta el manifiesto y los bundles de `--no-dev --minify`, y que la comprobación del SHA reconoce el bundle nuevo. El APK sigue siendo debug aunque el JS use esas opciones.
4. Que el token efímero de Actions tiene `contents: write` y `pull-requests: write`, y que las reglas del repositorio permiten crear y hacer force-push a `qa-sesion/**`. El controlador solo empuja ese prefijo. Las reglas de ramas protegidas pueden rechazarlo aunque el workflow declare los permisos.

La implementación se preparó sin ejecutar instalaciones, builds ni pruebas locales. La primera ejecución y su revisión se hacen en GitHub.

Fase 2 de imágenes: flujos y pruebas escritos, sin ejecución local. Selección inicial para Claude: `[qa: 05 07 10 11 16]`. `05-captura-envios`, `10-galeria` y `11-ajustes` cubren el selector de tres estados (IMG-16); `16-imagenes` cubre IMG-11 y CAP-16.
