# Captura (`CAP`)

Con un gesto, Gustavo le manda al equipo una nota de voz, fotos y una nota escrita. El equipo transcribe el audio, decide a dónde va (una idea para un post, un dato sobre él, una respuesta, una nota sobre una persona o una pieza, la Galería) y le cuenta qué hizo en «Lo que enviaste».

- **Código:** backend `capturas.py` (`create`, `process`, `classify`, `undo`, `capture_payload`), `capturas_views.py`, `knowledge/providers.assemblyai_transcribe`; PWA `oficina/src/capture/*`; app `movil/src/capture/*`, `movil/src/api/transport.ts`; común `compartido/src/api/capturas.ts` (`captureForm`, `appendFile`, `useCreateCaptura`), `compartido/src/logic/capturas.ts`, `compartido/src/logic/audio.ts`.
- **Documentación:** [`capturas-galeria.md`](../../agentes-linkedin/infra/docs/capturas-galeria.md), sección «Captura y Galería» de [`CONTRATO-API.md`](../../oficina/CONTRATO-API.md).
- **Entorno de prueba:** AssemblyAI y Claude parcheados, como en `tests/test_capturas.py`. En la app, las pruebas de Jest sustituyen `fetch` por un simulacro (`movil/src/test/server.ts`), así que no pueden detectar un fallo del transporte como el de [CAP-04](#cap-04) y [CAP-05](#cap-05): eso lo prueban los flujos de Maestro sobre la build release en el emulador (`movil/.maestro/05-captura*.yaml`), contra el backend de QA.

## Resumen

| ID | Función | Dónde | Estado |
| --- | --- | --- | --- |
| [CAP-01](#cap-01) | Abrir la hoja de captura con un toque | PWA · app | funciona |
| [CAP-02](#cap-02) | Grabar manteniendo el botón: bloquear, descartar, recuperar | PWA · app | funciona |
| [CAP-03](#cap-03) | Enviar una captura solo con nota | PWA · app · backend | funciona |
| [CAP-04](#cap-04) | Enviar una captura con nota de voz | PWA · app · backend | funciona |
| [CAP-05](#cap-05) | Enviar una captura con fotos | PWA · app · backend | funciona |
| [CAP-06](#cap-06) | Mensaje claro cuando un envío falla | PWA · app | parcial |
| [CAP-07](#cap-07) | Captura ligada a una pregunta, una persona o una pieza | PWA · app · backend | funciona |
| [CAP-08](#cap-08) | «Para qué es», o lo decide el equipo | PWA · app · backend | funciona |
| [CAP-09](#cap-09) | Transcripción del audio | backend | funciona |
| [CAP-10](#cap-10) | Deshacer un envío en los 2 minutos siguientes | PWA · app · backend | funciona |
| [CAP-11](#cap-11) | «Lo que enviaste» | PWA · app · backend | funciona |
| [CAP-12](#cap-12) | Qué hizo el equipo con cada envío | backend | funciona |
| [CAP-13](#cap-13) | Permiso del micrófono | PWA · app | funciona |
| [CAP-14](#cap-14) | Cerrar la hoja sin enviar | PWA · app | funciona |
| [CAP-15](#cap-15) | Límites de tamaño, tipo y duración | PWA · app · backend | parcial |
| [CAP-16](#cap-16) | Interpretar «publícalo lo antes posible» | PWA · app · backend | funciona |
| [CAP-17](#cap-17) | Enlaces que el equipo lee | backend | funciona |
| [CAP-18](#cap-18) | Pídele al equipo que investigue | backend | funciona |

---

### CAP-01 · Abrir la hoja de captura con un toque <a id="cap-01"></a>

- **Dónde:** PWA · app
- **Estado:** funciona
- **Qué hace para Gustavo:** toca el botón aguamarina y se abre la hoja para añadir foto o nota, sin grabar.
- **Código:** PWA `capture/CaptureButton.tsx` (móvil) y el botón «Capturar» de la barra lateral (escritorio); app `movil/src/capture/CaptureButton.tsx`.
- **Criterios de aceptación:**
  1. **Dado** el botón aguamarina en el centro de la barra inferior, **cuando** lo toca (menos de 220 ms), **entonces** se abre la hoja «Para el equipo» con «Grabar un audio», «Añadir una imagen» («Tomar foto», «Galería»), «Nota para el equipo (opcional)», «Para qué es (opcional)» y «Guardar y enviar al equipo».
  2. **Dado** que nunca usó el botón, **cuando** ve la barra, **entonces** aparece la pista «Mantén oprimido para grabar. Toca para foto o nota.»; tras el primer uso no vuelve a salir. En la app la pista se va sola a los 4 s y se quita deslizándola de lado; si la desliza, no vuelve (`movil/src/components/Hint.tsx`).
  3. **Dado** la PWA en escritorio, **cuando** pulsa «Capturar» en la barra lateral, **entonces** se abre la misma hoja (en escritorio no hay mantener para grabar).
  4. **Dado** una vista de detalle en la app (pieza o persona), **cuando** se muestra, **entonces** la barra inferior y el botón de captura no aparecen.
- **Brechas código/docs:** —
- **Cobertura QA:** E2E `05-captura` (criterios 1 y 2: el toque y la pista del primer uso). El 4 (sin barra en una ficha) se ve en la captura `05-contexto-04a-ficha-sin-barra`: las pestañas siguen montadas debajo de la ficha y Maestro encuentra el botón aunque no esté en pantalla. El 3 es de la PWA.

### CAP-02 · Grabar manteniendo el botón: bloquear, descartar, recuperar <a id="cap-02"></a>

- **Dónde:** PWA · app
- **Estado:** funciona
- **Qué hace para Gustavo:** mantiene el botón para grabar; desliza hacia arriba para seguir grabando sin el dedo, a la izquierda para descartar, o suelta para revisar el audio antes de enviarlo.
- **Código:** PWA `CaptureButton.tsx` (umbrales en `:19-24`); app `CaptureButton.tsx`, `hold.ts`, tokens `theme/motion.ts` (`holdDelayMs 220`, `minHoldMs 600`, `lockDistance 64`, `discardDistance 110`).
- **Criterios de aceptación:**
  1. **Dado** el micrófono permitido, **cuando** mantiene el botón 220 ms o más, **entonces** empieza a grabar y ve el tiempo, la onda, «Desliza hacia arriba para bloquear» y «‹ Desliza para cancelar».
  2. **Dado** que graba, **cuando** desliza 64 px hacia arriba, **entonces** la grabación sigue dentro de la hoja con «Grabando · bloqueado» y los botones «Descartar», «Pausar»/«Seguir» y «Terminar».
  3. **Dado** que graba, **cuando** desliza 110 px a la izquierda, **entonces** se descarta y aparece «Grabación descartada.» con «Recuperar» durante 5 s; «Recuperar» devuelve el audio.
  4. **Dado** que graba, **cuando** suelta sin bloquear, **entonces** la hoja se abre con el audio terminado; nunca se envía solo.
  5. **Dado** que suelta antes de 600 ms desde que pulsó, **cuando** termina el gesto, **entonces** cuenta como un toque y no se graba nada.
  6. **Dado** 30 minutos de grabación, **cuando** se alcanzan, **entonces** la grabación se detiene sola y queda en la hoja.
- **Brechas código/docs:** —
- **Cobertura QA:** E2E `05-captura` (criterio 4: mantener el botón abre la hoja con el audio listo; grabar, descartar y terminar desde la hoja). Bloquear, deslizar para descartar y «Recuperar» necesitan el dedo quieto en pantalla mientras se mueve, que Maestro no hace: pruebas de Jest (`capture.test.tsx`) y el video del flujo.

### CAP-03 · Enviar una captura solo con nota <a id="cap-03"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** escribe una nota y la manda al equipo; ve que llegó y puede deshacerlo.
- **Código:** `POST /api/v1/capturas` (multipart, `api.postForm`, sin `Content-Type` propio); `capturas.create`; hoja `CaptureSheet.tsx` en las dos interfaces.
- **Criterios de aceptación:**
  1. **Dado** una nota «Idea para el post del jueves», **cuando** pulsa «Guardar y enviar al equipo», **entonces** se envía `POST /api/v1/capturas` con la parte `nota`, la API responde 201 con la captura en `recibida`, la hoja se cierra y aparece «Enviado al equipo.» con «Deshacer».
  2. **Dado** la captura enviada, **cuando** abre «Lo que enviaste», **entonces** la ve arriba con el chip «Nota» y su estado, que avanza solo (la interfaz consulta cada 2,5 s mientras está `recibida`, `transcribiendo` o `procesando`).
  3. **Dado** una hoja vacía (sin nota, audio ni fotos), **cuando** mira el botón, **entonces** «Guardar y enviar al equipo» está desactivado; si la API recibe una captura vacía, responde 400 «La captura está vacía: graba un audio, añade una foto o escribe una nota.».
  4. **Dado** una nota de más de 4.000 caracteres, **cuando** la escribe, **entonces** ve «La nota tiene N caracteres; el máximo es 4000.» y no puede enviar.
  5. **Dado** el envío desde la app, **cuando** sale la petición, **entonces** lleva `Authorization: Bearer <token>` y ninguna cookie ni `X-CSRFToken`; desde la PWA lleva la cookie y `X-CSRFToken`.
  6. **Dado** un token de servicio, **cuando** intenta enviar, **entonces** recibe 403.
- **Brechas código/docs:** —
- **Cobertura QA:** E2E `05-captura` (criterios 1 a 3). El 4 (4.000 caracteres) y el 5 y 6 (cabeceras, token de servicio) son de Jest y del backend.

### CAP-04 · Enviar una captura con nota de voz <a id="cap-04"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** graba lo que piensa y lo manda; el equipo lo transcribe y decide qué hacer.
- **Código:** app `CaptureSheet.tsx` (`send`: `create.mutate` con `audio: {blob: {uri, name, type}}`), `recorder.tsx` (`RecordingPresets.HIGH_QUALITY`, `.m4a`, `MIME = 'audio/mp4'`), `movil/src/api/multipart.ts` (las subidas `multipart/form-data` van por `XMLHttpRequest`); común `compartido/src/api/capturas.ts` (`appendFile`, `nativePart`, `captureForm`); backend `capturas.check_audio`.
- **Arreglado:** con `expo/fetch` como `fetch` global, la parte `{uri, name, type}` lanzaba `Unsupported FormDataPart implementation` y la captura con audio no salía del teléfono. El PR #43 manda las subidas por `XMLHttpRequest` (`multipart.ts`); el flujo `05-captura-envios` lo comprueba en el emulador.
- **Criterios de aceptación:**
  1. **Dado** la app con una grabación de 20 s, **cuando** pulsa «Guardar y enviar al equipo», **entonces** sale `POST /api/v1/capturas` multipart con la parte `audio` (nombre `captura.m4a`, tipo `audio/mp4`) y `audio_duration_s` = 20, la API responde 201 y aparece «Enviado al equipo.» con «Deshacer».
  2. **Dado** esa captura, **cuando** abre «Lo que enviaste», **entonces** ve «Audio 0:20» y el estado pasa por «Transcribiendo» y «Procesando» hasta su destino, con la transcripción visible y «Escuchar».
  3. **Dado** audio, nota y dos fotos en la misma captura, **cuando** la envía, **entonces** llega una sola captura con las tres cosas.
  4. **Dado** «Responder con audio» en Tu turno, «Nota de voz» en una persona o «Comentario para el equipo» en una pieza, **cuando** envía con audio, **entonces** llega igual que desde el botón aguamarina, ligada a su contexto.
  5. **Dado** la PWA en Chrome (webm/opus) o en Safari (mp4), **cuando** envía con audio, **entonces** llega con el tipo correcto y la API la acepta.
  6. **Dado** un audio cuyo tipo declarado no coincide con su contenido, **cuando** llega, **entonces** la API responde 400 «El archivo de audio no corresponde a su tipo.».
  7. **Dado** que un envío con audio falla por cualquier motivo, **cuando** termina, **entonces** se cumple [CAP-06](#cap-06).
- **Brechas código/docs:** —
- **Cobertura QA:** E2E `05-captura-envios` (criterios 1 y 2: una nota de voz grabada manteniendo el botón llega al backend, «Enviado al equipo.» y «Audio 0:0N» con «Escuchar» en «Lo que enviaste»; sin trabajador en CI se queda «Recibida») y `05-captura-contexto` (criterio 4: respuesta por voz a una pregunta y nota de voz en una persona). El emulador graba silencio (`-noaudio`): la voz real y la transcripción (CAP-09) se prueban en el teléfono. Los criterios 5 y 6 son de la PWA y del backend.

### CAP-05 · Enviar una captura con fotos <a id="cap-05"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** hace una foto o elige varias y las manda; quedan en su Galería y, si hay texto, el equipo decide qué hacer con él.
- **Código:** app `movil/src/capture/photos.ts` (`launchCameraAsync`, `launchImageLibraryAsync`, partes `{uri, name, type}`); común `appendFile`; backend `capturas.check_photos`, `_save_photos`.
- **Arreglado:** el mismo fallo de transporte de [CAP-04](#cap-04), corregido en el PR #43; `05-captura-envios` y `18-perfil` (la subida de Ajustes › Fotos de perfil) lo comprueban en el emulador.
- **Criterios de aceptación:**
  1. **Dado** la app, **cuando** pulsa «Tomar foto», hace la foto y envía, **entonces** sale `POST /api/v1/capturas` con una parte `fotos` (JPEG), la API responde 201 y la foto aparece en la Galería con la etiqueta «Nueva».
  2. **Dado** «Galería» en la hoja, **cuando** elige 3 fotos y envía, **entonces** llegan las 3 como partes `fotos` de la misma captura y «Lo que enviaste» muestra «3 fotos».
  3. **Dado** «Para qué es: Foto para la galería» con una nota, **cuando** envía, **entonces** las fotos quedan en la Galería con esa nota como nota de la foto y la captura termina con «Está en tu Galería».
  4. **Dado** «Foto para la galería» sin fotos, **cuando** intenta enviar desde la PWA, **entonces** ve «Para «Foto para la galería» adjunta al menos una foto.» y no puede enviar. La app ya no ofrece ese propósito (12/11/2026): una foto va con «Idea para un post» o sin propósito, y un borrador viejo con `para=galeria` vuelve como idea.
  5. **Dado** una foto HEIC del iPhone o una PNG, **cuando** la envía, **entonces** la API la acepta y la sirve con su tipo real.
  6. **Dado** un archivo que dice ser imagen pero no lo es, **cuando** llega, **entonces** la API responde 400 «Uno de los archivos no es una imagen JPEG, PNG, WebP o HEIC.».
  7. **Dado** que el permiso de cámara está denegado, **cuando** pulsa «Tomar foto», **entonces** ve «La cámara está bloqueada para 0ff1ce: permítela en los ajustes del teléfono, o elige una foto de la galería.».
- **Brechas código/docs:** en la app, a diferencia del micrófono, no hay botón para abrir los ajustes cuando la cámara está bloqueada.
- **Cobertura QA:** E2E `05-captura-envios` (criterios 2 y 4: una foto elegida en el selector de Android llega al backend, y aparece en «Lo que enviaste» con «1 foto»; `05-captura` comprueba que la app ya no ofrece «Foto para la galería») y `05-captura-contexto` (comentario con foto en una pieza). El criterio 1 (cámara) no: el emulador arranca sin cámara (`-camera-back none`). 3, 5 y 6 son del backend; 7, de Jest.

### CAP-06 · Mensaje claro cuando un envío falla <a id="cap-06"></a>

- **Dónde:** PWA · app
- **Estado:** parcial
- **Qué hace para Gustavo:** si algo sale mal al enviar, lo ve al momento, en español, sabe qué hacer y no pierde lo que grabó o escribió.
- **Código:** app `CaptureSheet.tsx` (`SendError`: el motivo, «Tu audio, tus fotos y tu nota siguen aquí. Puedes reintentar.» y «Reintentar», justo encima del botón de enviar), `sendError.ts` (`describeSendError`), `movil/src/api/multipart.ts` (`UploadNetworkError`); PWA `oficina/src/capture/CaptureSheet.tsx`; común `compartido/src/api/errors.ts` (`errorMessage`).
- **Lo que falta:** la app cumple los criterios desde el PR #43 (con sus propios títulos: sin conexión, «No hay conexión con el servidor» y «El envío no salió del teléfono. Comprueba tu red y vuelve a intentarlo.»; el 409, «No se puede enviar así ahora»). En la PWA falta el 7: no hay «Reintentar», se vuelve a pulsar «Guardar y enviar al equipo».
- **Criterios de aceptación:**
  1. **Dado** un envío que falla por cualquier motivo, **cuando** vuelve el error, **entonces** la hoja sigue abierta con el audio, las fotos, la nota, «Para qué es», la visibilidad y el contexto intactos.
  2. **Dado** el mismo fallo, **cuando** vuelve el error, **entonces** Gustavo ve un mensaje en español sin tener que desplazarse (un aviso fijo junto al botón de enviar o un toast), además de la vibración en la app.
  3. **Dado** que el teléfono no tiene conexión, **cuando** envía, **entonces** el mensaje es «No hay conexión con el servidor. Comprueba tu red.».
  4. **Dado** una respuesta 413, **cuando** vuelve, **entonces** ve «El envío es demasiado grande» con «El audio puede pesar hasta 25 MB y cada foto hasta 10 MB. Quita alguna foto o graba un audio más corto.».
  5. **Dado** una respuesta 409 (por ejemplo, el contexto ya no admite el envío), **cuando** vuelve, **entonces** ve «No se puede ahora» con su `detail`. Una respuesta a una pregunta ya cerrada no da 409: se guarda como dato privado ([TUR-10](tu-turno.md#tur-10)).
  6. **Dado** cualquier otro error de la API, **cuando** vuelve, **entonces** ve su `detail` en español.
  7. **Dado** el mensaje de error, **cuando** se muestra, **entonces** ofrece reintentar el mismo envío con un toque, sin rehacer nada.
  8. **Dado** cualquier fallo, **cuando** se muestra, **entonces** nunca aparece texto técnico en inglés (`Unsupported FormDataPart implementation`, `fetch failed: …`).
- **Brechas código/docs:** el problema de los mensajes sin conexión en inglés fuera de la captura se sigue en [APP-08](app-movil-instalacion.md#app-08).
- **Cobertura QA:** E2E `05-captura-envios` (criterios 1, 2, 3, 7 y 8: sin red, con el modo avión del emulador; y 4, el 413 con el interruptor de fallos de la QA). 5 y 6, Jest (`capture.test.tsx`).

### CAP-07 · Captura ligada a una pregunta, una persona o una pieza <a id="cap-07"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** desde una pregunta, la ficha de una persona o una pieza, abre la captura ya ligada a eso, y el equipo sabe a qué se refiere.
- **Código:** `contexto_tipo` y `contexto_id`; backend `capturas._route_question`, `_route_person`, `_route_piece` (y `retoque.run` para una pieza lista, en el mismo trabajo `process_capture`).
- **Criterios de aceptación:**
  1. **Dado** «Responder con audio» en una pregunta, **cuando** se abre la hoja, **entonces** muestra el chip «Responde a <agente>» con la pregunta. En la PWA trae además el selector «Visibilidad de tu respuesta» con «Si no eliges, se usa la que sugiere la pregunta.». En la app la hoja con contexto (pregunta, persona o pieza) es la sencilla: el chip, «Grabar un audio», «Añadir una imagen» y la nota; sin «Para qué es», visibilidad, «Edición con IA» ni «Lo que enviaste». La respuesta toma la visibilidad que sugiere la pregunta y la foto, el valor de Ajustes.
  2. **Dado** esa captura enviada, **cuando** se procesa, **entonces** la pregunta queda respondida como Gustavo (las preguntas tipadas guardan «{pregunta} {texto}») y la captura termina en «Está en Lo que el equipo sabe de ti · Público» o «· Privado», con enlace a `/tu-turno/sabe`.
  3. **Dado** «Nota de voz» en una persona, **cuando** se procesa, **entonces** se añade una nota a la persona con `source: "captura"` y la captura dice «Quedó en las notas de <nombre>», con enlace a su ficha.
  4. **Dado** «Comentario para el equipo» en una pieza ya publicada, descartada o sin publicación pendiente, **cuando** se procesa, **entonces** aparece en «Tus comentarios para el equipo» de esa pieza y la captura dice «Quedó como comentario para el equipo en la pieza del <día>».
  7. **Dado** «Comentario para el equipo» en una pieza lista que aún no salió (también si el líder descartó su última versión), **cuando** se procesa, **entonces** esa versión ya no se publica y el equipo la rehace según [EDI-22](motor-editorial.md#edi-22); la captura dice primero «El director está aplicando tu comentario…» y después qué cambió y cuándo sale, o por qué se aplazó.
  5. **Dado** el chip de contexto, **cuando** pulsa «Quitar el contexto», **entonces** la captura se envía sin contexto.
  6. **Dado** un contexto que ya no existe, **cuando** se envía, **entonces** la API responde 400 «El elemento ligado a la captura no existe.».
- **Brechas código/docs:** en la app, el contexto funciona con texto; con audio o fotos falla ([CAP-04](#cap-04)).
- **Cobertura QA:** E2E `05-captura-contexto` (criterios 1 y 4 a la vista: el chip de cada contexto, la hoja sencilla sin visibilidad ni «Para qué es», y las tres capturas en «Lo que enviaste» con su contexto, abierto tras quitar el contexto). Lo que hace el equipo con ellas (2, 3, 4) necesita el trabajador, que no corre en CI: pruebas del backend.

### CAP-08 · «Para qué es», o lo decide el equipo <a id="cap-08"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** puede decir para qué es lo que manda; si no lo dice, el equipo lo clasifica y le explica por qué.
- **Código:** campo `para`; backend `capturas._destination`, `classify` (Sonnet, propósito `capture-route`), `ROUTES`. La app ofrece «Idea para un post» y «Dato sobre mí» (la Galería y su «Foto para la galería» salieron de la app el 12/11/2026). «Propuesta de post» es lo mismo que una idea, y una pregunta se responde desde Tu turno. La PWA y la API conservan los cinco valores.
- **Criterios de aceptación:**
  1. **Dado** «Idea para un post», **cuando** se procesa, **entonces** la captura queda «En la mesa editorial» con «Mesa editorial lo tendrá en cuenta» y llega al director ([EDI-17](motor-editorial.md#edi-17)).
  2. **Dado** «Dato sobre mí» o «Responde una pregunta» sin pregunta ligada, **cuando** se procesa, **entonces** se guarda un dato privado `nota.captura-<id>` y la captura dice «Está en Lo que el equipo sabe de ti · Privado».
  3. **Dado** que no eligió nada y hay texto, **cuando** se procesa, **entonces** una clasificación decide entre post, propuesta, dato y galería (esta solo con fotos), y la tarjeta muestra «… · lo decidió el equipo» con el motivo; ante la duda gana «dato».
  4. **Dado** que no eligió nada y solo hay fotos, **cuando** se procesa, **entonces** las fotos quedan en la Galería sin pasar por el clasificador.
  5. **Dado** un audio sin voz y sin nota ni fotos, **cuando** se procesa, **entonces** la captura queda «Sin usar».
  6. **Dado** que la clasificación falla o devuelve algo inválido, **cuando** se procesa, **entonces** la captura queda en error con «No se pudo decidir a dónde va (…). El texto queda aquí: elige «Para qué es» y envíalo de nuevo.».
- **Brechas código/docs:** —
- **Cobertura QA:** E2E `05-captura` (los chips de «Para qué es» y «Idea para un post» en «Lo que enviaste»). La clasificación (1 a 6) es del backend.

### CAP-09 · Transcripción del audio <a id="cap-09"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** su nota de voz se convierte en texto que el equipo puede leer y usar.
- **Código:** `capturas.process`, `providers.assemblyai_transcribe`, propósito `capture-transcribe`, dentro de `AI_MONTHLY_LIMIT_USD` y del techo opcional `ASSEMBLYAI_LIMIT_USD`.
- **Criterios de aceptación:**
  1. **Dado** una captura con audio, **cuando** corre `process_capture`, **entonces** pasa a `transcribiendo` («Transcribiendo el audio»), guarda `transcript`, `transcript_language` y la duración real, y pasa a `procesando`.
  2. **Dado** la transcripción, **cuando** se calcula el coste, **entonces** se reserva antes el peor caso según la duración declarada (hasta 30 min) y se liquida con la duración real.
  3. **Dado** que AssemblyAI devuelve error, **cuando** termina, **entonces** la captura queda «No se pudo procesar» con el motivo, el texto intacto, y no se cobra (reserva `rejected`).
  4. **Dado** un corte de red o un tiempo agotado al crear la transcripción, **cuando** termina, **entonces** la reserva queda `uncertain` y no se reintenta sola.
  5. **Dado** un trabajo que muere a medias, **cuando** se listan las capturas, **entonces** esa captura aparece en error con «El procesamiento se interrumpió y no se repite: la transcripción pudo haberse cobrado ya.» o «El trabajo que la procesaba se detuvo y no se repite (no se paga dos veces). Envíala de nuevo si hace falta.».
  6. **Dado** `LIVE_PROVIDERS=false` o sin `ASSEMBLYAI_API_KEY`, **cuando** llega un audio, **entonces** la captura queda en error con un mensaje claro y no se llama a nadie.
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### CAP-10 · Deshacer un envío en los 2 minutos siguientes <a id="cap-10"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** si mandó algo por error, lo deshace y el equipo revierte lo que hizo con ello.
- **Código:** `DELETE /api/v1/capturas/<id>` (`capturas.undo`, `UNDO_WINDOW` 2 min); el aviso «Enviado al equipo.» y `History.tsx` en las dos interfaces.
- **Arreglado:** «Deshacer» de «Lo que enviaste» calculaba el plazo con la hora en que se pintó la tarjeta y seguía visible pasados los 2 minutos. Ahora la tarjeta vuelve a pintarse cuando vence el plazo (`useUndoClock`, en las dos interfaces), y una captura deshecha sale de la lista al momento (`removeCapturaFromHistory`), sin esperar a que vuelva la lista.
- **Criterios de aceptación:**
  1. **Dado** una captura recién enviada, **cuando** pulsa «Deshacer» en el aviso (5 s), **entonces** la API la deja en `deshecha`, aparece «Envío deshecho. Lo tienes otra vez en la hoja.» y la hoja se reabre con el mismo borrador.
  2. **Dado** una captura de hace 1 minuto, **cuando** pulsa «Deshacer» en «Lo que enviaste», **entonces** se deshace, aparece «Envío deshecho.» y desaparece de la lista.
  3. **Dado** que se deshace, **cuando** termina, **entonces** se cancela el trabajo si no había empezado, se reabre la pregunta, se retira el dato o se quita la nota de la persona, y se borran el audio y las fotos (también de la Galería).
  4. **Dado** una captura de hace más de 2 minutos, **cuando** abre «Lo que enviaste», **entonces** no hay botón «Deshacer».
  5. **Dado** que se pide deshacer pasados los 2 minutos, **cuando** responde la API, **entonces** es 409 «Ya no se puede deshacer: pasaron más de 2 minutos. Corrige o quita lo que creó desde su sitio.» y la interfaz muestra «Ya no se puede deshacer: pasaron los 2 minutos.».
  6. **Dado** otra persona, **cuando** intenta deshacer una captura que no envió, **entonces** la API responde 409 «Solo quien la envió puede deshacerla.».
- **Brechas código/docs:** deshacer desde «Lo que enviaste» no reabre el borrador, a diferencia del aviso.
- **Cobertura QA:** E2E `05-captura` (criterios 1 y 2: «Deshacer» en el aviso devuelve el borrador; en «Lo que enviaste», «Envío deshecho.» encima de la hoja y la captura sale de la lista). 3, 5 y 6, backend; 4, Jest y Vitest (el plazo de 2 minutos).

### CAP-11 · «Lo que enviaste» <a id="cap-11"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** dentro de la hoja ve todo lo que mandó, en qué estado está y qué hizo el equipo con ello.
- **Código:** `GET /api/v1/capturas`, `GET /api/v1/capturas/<id>`, `GET /api/v1/capturas/<id>/audio`; `History.tsx` en las dos interfaces.
- **Criterios de aceptación:**
  1. **Dado** capturas enviadas, **cuando** pulsa «Lo que enviaste · N», **entonces** ve la lista de la más reciente a la más antigua, sin las deshechas, cada una con los chips («Audio 0:42», «N fotos», «Nota»), la hora («Hoy, 10:40»), para qué es, el contexto, la transcripción o la nota, el estado y el resultado (enlazado si tiene enlace dentro de la app).
  2. **Dado** una captura en error, **cuando** se pinta, **entonces** muestra el motivo en rojo.
  3. **Dado** una captura con audio, **cuando** pulsa «Escuchar», **entonces** suena el audio, servido por `…/audio` con la sesión o el token (admite `Range`).
  4. **Dado** más de una página, **cuando** pulsa «Ver envíos anteriores», **entonces** carga la siguiente.
  5. **Dado** ninguna captura, **cuando** abre la lista, **entonces** ve «Todavía no has enviado nada» y «Lo que mandes aparecerá aquí, con lo que hizo el equipo.».
  6. **Dado** un error al cargar, **cuando** falla, **entonces** ve el error con «Reintentar».
  7. **Dado** el enlace `/?enviado=1` (notificación «captura procesada»), **cuando** lo abre, **entonces** se abre la hoja en «Lo que enviaste».
- **Brechas código/docs:** un envío que falló en el teléfono antes de llegar al servidor no aparece aquí. En la app no se comprobó si el reproductor de audio envía la cabecera `Authorization` en Android.
- **Cobertura QA:** E2E `05-captura` (criterio 1: la lista con las dos capturas sembradas y la nueva, chips, hora, estado y resultado; 3: «Escuchar» de la nota de voz sembrada) y `05-captura-envios` («1 foto», «Audio 0:0N»). 2, 4 a 7: Jest.

### CAP-12 · Qué hizo el equipo con cada envío <a id="cap-12"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** cada envío dice en una frase dónde acabó.
- **Código:** `capturas.capture_payload`, `STATE_LABELS`, `_outcome`; aviso `capture_processed`.
- **Criterios de aceptación:**
  1. **Dado** cada estado, **cuando** se consulta la captura, **entonces** `state_label` y `outcome.text` son: Recibida / «El equipo lo recibió»; Transcribiendo / «Transcribiendo el audio»; Procesando / «Mesa editorial lo está leyendo»; Dato guardado / «Está en Lo que el equipo sabe de ti · …» o «Está en tu Galería»; Anotado / «Quedó en las notas de …» o «Quedó como comentario…»; En la mesa editorial / «Mesa editorial lo tendrá en cuenta»; Usado / «El Director editorial lo usó en el brief del …»; Sin usar; No se pudo procesar; Deshecha / «Deshiciste este envío».
  2. **Dado** que una captura termina su procesamiento, **cuando** se rutea, **entonces** se guarda la Notificación `capture_processed` con el resultado y «Míralo en «Lo que enviaste».» (sin push por defecto), y la escena registra una `entrega` de Operación al agente que la recibe.
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### CAP-13 · Permiso del micrófono <a id="cap-13"></a>

- **Dónde:** PWA · app
- **Estado:** funciona
- **Qué hace para Gustavo:** antes de que el sistema pida el micrófono, la app le explica para qué; si lo bloqueó, le dice cómo volver a permitirlo.
- **Código:** PWA `CaptureSheet.tsx:67-123`, `capture/recorder.ts`; app `CaptureSheet.tsx`, `recorder.tsx`, `CaptureButton.tsx:156-169, 211-216`.
- **Criterios de aceptación:**
  1. **Dado** el micrófono sin pedir, **cuando** mantiene el botón o pulsa «Grabar un audio», **entonces** ve primero «Para grabar, 0ff1ce necesita el micrófono» con «Permitir el micrófono» y «Ahora no», y solo después el aviso del sistema.
  2. **Dado** el micrófono bloqueado, **cuando** quiere grabar, **entonces** ve «El micrófono está bloqueado» con una salida: en la app «Abrir los ajustes del teléfono»; en la PWA «Ir a Ajustes › Captura y galería».
  3. **Dado** que otra app usa el micrófono, **cuando** falla al grabar, **entonces** ve «No se pudo usar el micrófono» con «Volver a intentarlo», y puede seguir enviando fotos o una nota.
  4. **Dado** un navegador sin grabación, **cuando** abre la hoja en la PWA, **entonces** ve «Aquí no se puede grabar audio».
  5. **Dado** que vuelve a la app tras cambiar el permiso en el sistema, **cuando** la app pasa a primer plano, **entonces** relee el permiso.
- **Brechas código/docs:** —
- **Cobertura QA:** E2E `05-captura` (lo que muestra la hoja según abra o no el micrófono del emulador; el flujo concede el permiso al instalar, así que «Para grabar, 0ff1ce necesita el micrófono» y «bloqueado» son de Jest).

### CAP-14 · Cerrar la hoja sin enviar <a id="cap-14"></a>

- **Dónde:** PWA · app
- **Estado:** funciona
- **Qué hace para Gustavo:** si cierra la hoja con algo dentro, se le pregunta antes de perderlo.
- **Código:** `CaptureSheet.tsx` en las dos interfaces (confirmación «¿Cerrar sin enviar?»).
- **Arreglado:** mientras el envío estaba en curso, cerrar con Esc, el fondo, «atrás» o la X cerraba la hoja sin preguntar (en la PWA y en la app) y el resultado del envío se perdía. Ahora la hoja no se cierra hasta que el envío termina (`close()` en la PWA, `canClose` y `suspended` en la app). La X dice «Cerrar sin enviar», como su diálogo (decía «Cerrar sin guardar»).
- **Criterios de aceptación:**
  1. **Dado** una hoja con audio, fotos o nota, **cuando** la cierra, **entonces** ve «¿Cerrar sin enviar?» con «Se pierden el audio, las fotos y la nota de esta captura.», «Seguir aquí» y «Cerrar sin enviar».
  2. **Dado** una hoja vacía, **cuando** la cierra, **entonces** se cierra sin preguntar.
  3. **Dado** un envío en curso, **cuando** intenta cerrar la hoja, **entonces** no se cierra hasta que termine, o el resultado (éxito o error) se le muestra igualmente.
- **Brechas código/docs:** —
- **Cobertura QA:** E2E `05-captura` (criterios 1 y 2, con «Seguir aquí»). El 3, Jest y Vitest (`capture.test.tsx`, `CaptureSheet.test.tsx`).

### CAP-15 · Límites de tamaño, tipo y duración <a id="cap-15"></a>

- **Dónde:** PWA · app · backend
- **Estado:** parcial
- **Qué hace para Gustavo:** la interfaz le avisa antes de enviar algo que el servidor no aceptaría.
- **Código:** backend `CAPTURE_AUDIO_MAX_BYTES` (25 MB), `GALLERY_PHOTO_MAX_BYTES` (10 MB), `GALLERY_MAX_PHOTOS_PER_REQUEST` (10), `audio_duration_s` ≤ 1800, nota ≤ 4.000; Caddy 130 MB; PWA `CaptureSheet.tsx:271-275, 313-328`; app `photos.ts` (`checkPhotos`), `recorder.tsx`.
- **Criterios de aceptación:**
  1. **Dado** una foto de 12 MB o un GIF, **cuando** la añade, **entonces** ve «No se añadió <nombre>: solo JPEG, PNG, WebP o HEIC de hasta 10 MB.» y no se adjunta.
  2. **Dado** 10 fotos adjuntas, **cuando** intenta añadir otra, **entonces** ve «Puedes adjuntar hasta 10 fotos por envío.».
  3. **Dado** un audio de más de 25 MB en la PWA, **cuando** termina de grabar, **entonces** ve «El audio pasa de 25 MB: grábalo más corto.» y no puede enviar.
  4. **Dado** una grabación de 28 minutos en la app, **cuando** termina, **entonces** la interfaz avisa de que pasa de 25 MB antes de enviar. **Hoy falla:** la app graba a 128 kbps (unos 28,8 MB en 30 minutos) y no comprueba el tamaño del audio, así que la API respondería 413 al enviar.
  5. **Dado** una duración declarada de más de 1.800 s, **cuando** llega, **entonces** la API responde 400 «El audio puede durar como mucho 30 minutos.».
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### CAP-16 · Interpretar «publícalo lo antes posible» <a id="cap-16"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Código:** `capture_intent.py`, `capturas.classify` y `process`; `compartido/src/logic/capturas.ts` y `capture/History.tsx` de ambas interfaces.
- **Criterios de aceptación:**
  1. **Dado** una nota o transcripción que pide publicar pronto, **cuando** se procesa, **entonces** la clasificación estructurada guarda `publish_asap` y una cita literal sin añadir otra llamada; en destinos explícitos sin clasificación usa una consulta Jev Noul.
  2. **Dado** una negación, una cita ajena o una urgencia de otro asunto, **cuando** se interpreta, **entonces** no se activa prioridad.
  3. **Dado** «sácalo mañana», **cuando** se interpreta, **entonces** no se reserva antes de mañana ni se saltan verificaciones.
  4. **Dado** que falla la interpretación, **cuando** se guarda la captura, **entonces** conserva el texto y registra el error; no inventa una urgencia ni repite el paso pagado.
  5. **Dado** una idea urgente, **cuando** se consulta, **entonces** muestra evidencia, fecha prevista y condiciones, sin botón ni campo editable de urgencia.
  6. **Dado** un día y una hora pedidos («publica esto el martes a las 12»), **cuando** se interpretan del fragmento literal, **entonces** son una orden: el post sale ese día a esa hora como post extra ([EDI-24](motor-editorial.md#edi-24)); sin hora, a `EDITORIAL_EXTRA_TIME`. Una fecha pasada, a más de 14 días o que no se entiende queda como problema (`pasada`, `lejana`, `ambigua`) y la Bandeja pregunta en el momento; nunca se cambia por otro día sin preguntar.
  7. **Dado** la misma clasificación, **cuando** la idea pide claramente un tipo de post, **entonces** guarda `gasp_type` (G, A, S o P; «ninguno» si no está claro) y la idea toma el día de ese tipo más cercano ([EDI-25](motor-editorial.md#edi-25)); el director recibe la idea con su tipo y si es un post extra. Su motivo («El día de … más cercano» o «Se escribe como post de …») es el que ve en «Lo que enviaste».
- **Validación:** pruebas escritas; CI pendiente. Sin ejecución local.
- **Cobertura QA:** `16-imagenes` (línea, fecha prevista, evidencia y condiciones); Jest/Vitest de captura (zona de Bogotá) y lógica compartida (sin fecha y sin urgencia). Escritos; ejecución pendiente de Claude.

### CAP-17 · Enlaces que el equipo lee <a id="cap-17"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** el equipo lee los enlaces públicos de una nota o transcripción y conserva evidencia para Editorial.
- **Código:** `web_sources.detect_urls/read_github`, `research.research`, `capturas.process/ideas_for_director`.
- **Criterios de aceptación:**
  1. **Dado** enlaces en nota y audio, **cuando** procesa la captura, **entonces** deduplica los enlaces y guarda `investigation` con pregunta, hallazgos, fuentes (URL, título, extracto y fecha), estado y limitaciones.
  2. **Dado** la raíz de un repositorio público de GitHub, **cuando** lo lee, **entonces** obtiene descripción, temas, lenguajes, README acotado y commits recientes por REST. Si falla, puede usar `web_fetch`; nunca deduce contenido del nombre. Un enlace a un archivo o issue sigue siendo ese enlace.
  3. **Dado** credenciales, parámetros de consulta, direcciones privadas, DNS mixto, redirecciones o exceso de tamaño, **cuando** intenta leer, **entonces** omite el enlace inseguro o detiene esa lectura, conserva la captura y muestra la limitación. El cliente directo solo contacta GitHub, con IP pública fijada y TLS para el host original.
  4. **Dado** fuentes leídas, **cuando** termina, **entonces** el resultado de la captura lo dice y la Oficina recibe una entrega de `investigador_referentes` a `director_editorial`, sin texto privado ni URLs en el evento.
  5. **Dado** `LIVE_PROVIDERS` desactivado, **cuando** recibe enlaces, **entonces** no hace DNS, HTTP ni llamadas al modelo de investigación, tampoco al GitHub gratuito.
- **Brechas código/docs:** esta fase entrega backend y contrato; la vista detallada de fuentes en PWA/app queda para la fase de interfaz. URLs con parámetros se omiten de forma conservadora. «funciona» identifica la implementación; validación de CI pendiente.
- **Cobertura QA:** `test_web_research.py`, escrito con DNS/HTTP/SDK falsos; ejecución a cargo de Claude.

### CAP-18 · Pídele al equipo que investigue <a id="cap-18"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** puede pedir en texto o voz que el equipo investigue un tema público y lo lleve con fuentes a la mesa editorial.
- **Código:** `capture_intent`, `research.ResearchRequest/ResearchResult`, `WebResearchRun`, `knowledge.providers.WebTools`.
- **Criterios de aceptación:**
  1. **Dado** «investiga la nueva versión de Python», **cuando** interpreta la captura, **entonces** usa la llamada de clasificación existente o las preguntas de Jev de la ruta explícita, exige evidencia literal y separa una pregunta pública. Negaciones, citas ajenas y evidencia inventada no activan la investigación.
  2. **Dado** información privada mezclada con la petición, **cuando** prepara la consulta, **entonces** solo envía el tema público separado; si no puede separarlo con seguridad, informa la limitación. No envía la nota, transcript, memoria, orientación ni inbox al contexto de herramientas web.
  3. **Dado** búsquedas con respuesta, **cuando** guarda hallazgos, **entonces** usa citas nativas enlazadas a resultados reales de herramientas. Una URL escrita por el modelo sin cita no es evidencia.
  4. **Dado** cap diario, presupuesto agotado, timeout, herramienta fallida o respuesta parcial, **cuando** termina, **entonces** conserva el destino de la captura y hace visible el límite. No vuelve a pagar al repetir la misma clave, ni continúa automáticamente un `pause_turn`.
  5. **Dado** una idea con investigación, **cuando** el director la recibe, **entonces** conserva fuentes y fechas como datos no confiables; nunca trata instrucciones dentro de páginas o README como órdenes.
  6. **Dado** Deshacer durante o después de una investigación, **cuando** se aplica, **entonces** retira el contenido de captura y resultado persistido sin borrar el gasto ni liberar el cupo consumido.
- **Brechas código/docs:** el catálogo de `plan-equipos` remite a esta fase sin reservar IDs web nuevos; CAP-17/18 proceden del brief. No se implementa aquí el observatorio mensual ni el dispatcher de fase 3.
- **Cobertura QA:** `test_web_research.py`, pendiente de ejecución en CI.

## Imágenes

Las fotos que Gustavo manda con la captura son la materia prima del flujo de imagen, implementado en el backend; el selector y el detalle visual están implementados en fase 2, con CI pendiente ([imagenes-en-publicaciones.md](imagenes-en-publicaciones.md)). Comportamiento de la captura:
- [IMG-01](imagenes-en-publicaciones.md#img-01): la nota de voz o escrita es contexto de las fotos y, si la trae, una instrucción («úsala tal cual», «recórtala», «quita el fondo», «más luz»);
- [IMG-02](imagenes-en-publicaciones.md#img-02): «Para qué es» gana la opción «Propuesta de post», y el clasificador puede elegirla cuando Gustavo no elige nada;
- [IMG-03](imagenes-en-publicaciones.md#img-03): las fotos llegan siempre a la Galería con su nota, sea cual sea el destino de la captura (implementado para todos los destinos).

## Biblioteca y fase web prevista

Por el addendum de Gustavo, Capturas **no necesita consultar el curso**; [BIB-06](biblioteca-equipos.md#bib-06) se retira sin reutilizar su ID. Editorial o Perfil emplean su biblioteca habitual cuando trabajan con una idea recibida. La fase web ya prevista aporta `web_search`, `web_fetch` y enlaces en capturas; no se duplica aquí ni habilita llamadas entre especialistas fuera del [grafo](arquitectura-agentes.md).

[EST-05](estrategia-perfil.md#est-05), **no implementado**, define el ruteo de «hazme la propuesta del perfil» en texto o voz al ciclo completo de Perfil, con deduplicación, progreso y paquete final enlazado. Una foto adjunta solo se vuelve elegible para foto/banner cuando Gustavo la asigna a la categoría «Perfil» de [GAL-08](galeria.md#gal-08), al subir o después. El ruteador no consulta biblioteca ni elige fotos fuera de esa categoría.

## Retiradas

Ninguna.
