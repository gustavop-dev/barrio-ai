# Oficina (`OFI`)

La pantalla de inicio: la oficina en pixel art con los 17 roles del equipo. Van a su puesto solo cuando el backend registra trabajo real; mientras esperan, descansan en la sala de juegos, la cocina o la biblioteca, con la oficina a oscuras. Incluye lo común a todas las vistas: la navegación, el banner de pausa y la franja sin conexión.

- **Código:** backend `oficina_views.Actividad` (`ROLES`, `JOB_ROLES`, `DESCRIPTIONS`), `oficina_views.Eventos`, `oficina_eventos.py`, `Overview`; PWA `oficina/src/pages/Oficina.tsx`, `oficina/src/scene/*`, `components/Layout.tsx`; app `movil/src/scene/*`, `movil/src/components/shell/*`; común `compartido/src/scene/*` (motor, plan, roles, actividad, narración, paneles).
- **Documentación:** secciones «Oficina (escena)» y «Escena de la Oficina: feed de eventos» de [`CONTRATO-API.md`](../../oficina/CONTRATO-API.md), notas `comportamiento` y `backend` de `movil/diseno-movimiento/canvas.json`, [`movil/MOTION.md`](../../movil/MOTION.md).

## Resumen

| ID | Función | Dónde | Estado |
| --- | --- | --- | --- |
| [OFI-01](#ofi-01) | La escena refleja la actividad real | PWA · app · backend | funciona |
| [OFI-02](#ofi-02) | Estado de cada personaje | PWA · app · backend | funciona |
| [OFI-03](#ofi-03) | Línea de lo que pasa ahora y eventos del equipo | PWA · app · backend | funciona |
| [OFI-04](#ofi-04) | Paneles de equipo y de rol | PWA · app | funciona |
| [OFI-05](#ofi-05) | La captura llega a la oficina | PWA · app | parcial |
| [OFI-06](#ofi-06) | Gestos en la escena | app | funciona |
| [OFI-07](#ofi-07) | Banner de máquina o cuenta en pausa | PWA · app · backend | funciona |
| [OFI-08](#ofi-08) | Franja sin conexión | PWA · app | funciona |
| [OFI-09](#ofi-09) | Navegación | PWA · app | funciona |
| [OFI-10](#ofi-10) | Editor visual como integrante de Editorial | PWA · app · backend | implementado; CI/QA pendiente |

---

### OFI-01 · La escena refleja la actividad real <a id="ofi-01"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** abre 0ff1ce y ve a su equipo. Los que trabajan están en su puesto, con su zona iluminada y la pantalla encendida. Los que esperan descansan en la sala de juegos, bajo El Barrio. El trabajo que se ve es real; el descanso es decorativo (pedido de Gustavo, 11/11/2026: «solo por placer visual»).
- **Código:** `GET /api/v1/oficina/actividad` (cada 15 s), `GET /api/v1/operador/overview` (cada 30 s); PWA `OfficeCanvas.tsx` (canvas); app `OfficeCanvas.tsx` (Skia), `useOfficeScene.ts`, `useOfficeLifecycle.ts`.
- **Criterios de aceptación:**
  1. **Dado** un trabajo `prepare_piece` corriendo en la etapa `redactor`, **cuando** se consulta la actividad, **entonces** `copywriter_a` y `copywriter_b` están `trabajando` con «Redactando dos variantes en inglés» y su hora de inicio, y en la escena trabajan en su puesto.
  2. **Dado** un trabajo en cola, **cuando** se consulta, **entonces** el rol muestra «Trabajo en cola».
  3. **Dado** un rol implementado sin trabajo, **cuando** se consulta, **entonces** está `en_espera` con «Último: <tarea> (<resultado>)» si hubo uno.
  4. **Dado** un rol que no tiene ningún trabajo implementado, **cuando** se consulta, **entonces** está `diseno` con «Contrato diseñado; aún sin implementar»; ningún rol con código aparece en diseño.
  5. **Dado** `INBOX_ENABLED=true` y un trabajo `read_inbox` corriendo, **cuando** se consulta, **entonces** `conversaciones_inbox` está `trabajando`.
  6. **Dado** que la actividad no se puede leer, **cuando** falla, **entonces** ve «No se pudo leer la actividad.» con «Mientras tanto los personajes quedan quietos: la oficina no simula trabajo.» y «Reintentar», y los personajes quedan quietos.
  7. **Dado** que el dibujo de la oficina no carga, **cuando** falla, **entonces** ve «No se pudo cargar el dibujo de la oficina.» (en la PWA, «… Recarga la página.»; en la app, con «Reintentar»).
  8. **Dado** la leyenda, **cuando** se pinta, **entonces** muestra Trabajando, En espera y En diseño, y «Actividad real · hace X», «Leyendo actividad…» o «Actividad no disponible». En la app (11/11/2026, a pedido de Gustavo) no hay leyenda, edad de la actividad, tira de equipos, enlace al mapa ni crédito del arte: la escena ocupa todo el ancho y llena la pantalla hasta la barra de abajo (solo se desplaza hacia arriba y abajo), y encima solo aparecen los avisos de error; el estado de cada rol sigue en su panel.
  9. **Dado** la app en segundo plano o en otra pestaña, **cuando** pasa el tiempo, **entonces** la escena deja de consultar y de animar hasta volver.
  10. **Dado** «reducir movimiento» en el sistema, **cuando** abre la oficina, **entonces** la escena queda quieta: cada rol en su puesto o en un lugar de descanso fijo, con las luces ya puestas.
  11. **Dado** los roles en espera, **cuando** abre la oficina, **entonces** los agentes libres ya están descansando. Juegan consola, arcade o billar, tocan la batería, cantan, bailan o conversan en la sala de juegos; toman café o comen en la cocina; o leen en la biblioteca. Las zonas sin nadie quedan a oscuras con las pantallas apagadas. Si nadie trabaja, la app abre la cámara en la sala de juegos. Bibliotecario y Operación son servicios y no dejan su puesto.
  12. **Dado** un rol que pasa a `trabajando`, una captura (llaman al director) o una entrega (va quien entrega y llaman a quien recibe), **cuando** ocurre, **entonces** caminan rápido a su puesto, su zona se ilumina y su pantalla se enciende. Al terminar se quedan 15 s (30 s si los llamaron) y vuelven a descansar.
  13. **Dado** agentes descansando, **cuando** pasa el tiempo, **entonces** cambian de juego cada 16 a 42 s (hay más lugares que agentes), se hablan con emojis y su pareja les contesta. De vez en cuando arman una fiesta con la pista encendida, y entre las 22:00 y las 6:00 del teléfono se quedan dormidos («zzz»).
  14. **Dado** que la actividad aún no se conoce, **cuando** abre la oficina, **entonces** todos siguen en su puesto con las luces encendidas.
- **Brechas código/docs:** `oficina/README.md` describe los botones «Activar ambiente» y «Luz de tarde», que no existen en el código actual.
- **Cobertura QA:** OFI-01.4, OFI-01.5 (el agente de inbox en espera, con su último read_inbox, abierto desde su equipo), OFI-01.8 y la sala de juegos de OFI-01.11 (captura) en `movil/.maestro/03-oficina.yaml` · OFI-01.1–3 y 5 en `team_backend/tests/test_oficina.py` · OFI-01.10–14 en `compartido/src/scene/engine.suite.ts` y `plan.suite.ts`; el dibujo compilado para el hilo de la interfaz en `movil/src/scene/runtime.worklet.test.ts` · OFI-01.6, 7 y 9 sin prueba E2E · 2026-11-11 · pendiente de CI

### OFI-02 · Estado de cada personaje <a id="ofi-02"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** cada personaje muestra si trabaja, espera, está en diseño o no hay datos.
- **Código:** `compartido/src/scene/activity.ts`, `engine.ts`, `runtime.ts`.
- **Criterios de aceptación:**
  1. **Dado** un rol `trabajando`, **cuando** se pinta, **entonces** está en su puesto, con la zona iluminada y el monitor encendido.
  2. **Dado** un rol `en_espera`, **cuando** pasa el tiempo, **entonces** descansa ([OFI-01.11](#ofi-01)) y, al tocarlo, la línea dice «<rol> · Descansa · <lo que hace>» («Juega en la consola», «Baila en la pista»…); los servicios se quedan en su puesto.
  3. **Dado** un rol `diseno`, **cuando** se pinta, **entonces** está atenuado, quieto y con la etiqueta «EN DISEÑO».
  4. **Dado** un rol sin dato, **cuando** se pinta, **entonces** está quieto y sin luz.
- **Brechas código/docs:** —
- **Cobertura QA:** OFI-02 en `movil/.maestro/03-oficina.yaml` (estado de un personaje en su panel) · 2026-11-08 · pasa

### OFI-03 · Línea de lo que pasa ahora y eventos del equipo <a id="ofi-03"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** una línea flotante le cuenta lo que acaba de pasar («Copywriter A va a la biblioteca», «Director entrega a …», «Operación publica en LinkedIn»), y los personajes caminan en consecuencia.
- **Código:** `GET /api/v1/oficina/eventos?desde=` (cada 15 s, como mucho 50, sin `desde` los últimos 10 minutos), `oficina_eventos.emit`; `compartido/src/scene/events.ts`, `presentation.ts`; PWA `Oficina.tsx`; app `OfficeNarration.tsx`.
- **Criterios de aceptación:**
  1. **Dado** que una etapa editorial lee unidades del curso, **cuando** llega el evento `consulta_biblioteca`, **entonces** el personaje va a la biblioteca y la línea dice «<rol> va a la biblioteca: “<detalle>”».
  2. **Dado** que una etapa termina, **cuando** llega una `entrega`, **entonces** el personaje lleva una hoja al que recibe y la línea dice «<rol> entrega a <rol>».
  3. **Dado** que LinkedIn confirma un post propio o un comentario, **cuando** llega `publicacion`, **entonces** la línea dice «<rol> publica en LinkedIn».
  4. **Dado** muchos eventos juntos, **cuando** llegan, **entonces** se resumen («Mientras tanto: 3 consultas a la biblioteca, 2 entregas y 1 publicación.»).
  5. **Dado** la máquina en pausa, **cuando** se pinta la línea, **entonces** dice «La máquina está en pausa. Nadie toca tu LinkedIn.»; sin nadie trabajando, «Nadie camina: el equipo está en espera.».
  6. **Dado** un `desde` inválido, **cuando** se pide a la API, **entonces** responde 400 «desde debe ser una fecha ISO».
  7. **Dado** que la API de eventos responde 403 o 404, **cuando** pasa, **entonces** se deja de consultar; la app dice «El registro de eventos no está disponible. Se muestra la actividad real de cada rol.».
- **Brechas código/docs:** en la app la línea se retira sola a los 3,5 s; en la PWA no. La PWA no muestra ningún aviso si fallan los eventos por otro motivo. Además de las etapas editoriales y los comentarios, el trabajo de fondo emite entregas (`oficina_eventos.job_done` y `lead_reviewed`): observar referentes, descubrir y clasificar personas, leer el inbox, medir y la revisión del líder.
- **Cobertura QA:** OFI-03.2 y 4 en `movil/.maestro/03-oficina.yaml` (entregas de fondo sembradas, resumidas en «Lo último que hizo») · OFI-03.1–3 y 6 en `team_backend/tests/test_eventos.py` · 2026-11-08 · pasa

### OFI-04 · Paneles de equipo y de rol <a id="ofi-04"></a>

- **Dónde:** PWA · app
- **Estado:** funciona
- **Qué hace para Gustavo:** toca un personaje o una zona y ve qué hace ese rol o ese equipo, su misión y su estado real.
- **Código:** PWA `scene/OfficePanels.tsx`, `BottomSheet.tsx` (teléfono) o panel lateral (≥ 1.100 px); app `OfficePanels.tsx` en una hoja; `compartido/src/scene/panels.ts`.
- **Criterios de aceptación:**
  1. **Dado** la tira «Equipos» de la PWA (siete equipos más «Biblioteca») o, en la app, el nombre de una zona sobre la escena (botón para el lector de pantalla), **cuando** toca uno, **entonces** se abre su panel con «ESPACIO DEL EQUIPO», el número, «Nuevo» en Relaciones y Operación, el propósito, «N INTEGRANTES · <lugar>», el recuento («2 trabajando · 1 en espera · 0 en diseño») y sus miembros.
  2. **Dado** un personaje, **cuando** lo toca, **entonces** ve «AGENTE» o «SERVICIO» con la zona, la misión, «ESTADO REAL» con el detalle y desde cuándo (o «Sin datos de actividad.»), y para Operación la nota de que es un servicio, no un agente de IA.
  3. **Dado** un rol en diseño, **cuando** abre su panel, **entonces** ve «Este rol está en diseño. Aparece en la oficina, pero todavía no trabaja.».
  4. **Dado** «LO ÚLTIMO QUE HIZO», **cuando** se pinta, **entonces** muestra hasta 3 eventos de esta sesión o «Nada todavía en esta sesión.» (no es historial del servidor).
  5. **Dado** «Ver en el Calendario», **cuando** lo pulsa, **entonces** abre `/calendario` (sin filtrar por rol).
  6. **Dado** la PWA en escritorio, **cuando** abre la oficina, **entonces** el panel lateral muestra Operación por defecto.
- **Brechas código/docs:** —
- **Cobertura QA:** OFI-04.1, 2 y 5 en `movil/.maestro/03-oficina.yaml` · OFI-04.6 es de la PWA · 2026-11-08 · pasa

### OFI-05 · La captura llega a la oficina <a id="ofi-05"></a>

- **Dónde:** PWA · app
- **Estado:** parcial
- **Qué hace para Gustavo:** después de mandar una captura, ve cómo cae un sobre en Operación y cómo lo lleva a Mesa editorial.
- **Código:** `compartido/src/scene/runtime.ts` (`receiveCapture`); app `movil/src/scene/captureReceipts.ts` (escucha el éxito de `createCaptura`). La PWA no lo llama.
- **Criterios de aceptación:**
  1. **Dado** una captura enviada con éxito, **cuando** vuelve a la oficina, **entonces** cae un sobre en Operación con «Llegó tu captura a la oficina.», Operación lo recoge y lo lleva a Mesa editorial («Operación lleva tu captura a Mesa editorial.», «Director editorial recibe tu captura.»).
  2. **Dado** la PWA, **cuando** envía una captura, **entonces** ve la misma animación. **Hoy falla:** la PWA nunca llama a `receiveCapture`.
  3. **Dado** una captura con audio o fotos en la app, **cuando** la envía, **entonces** ve la animación. **Hoy falla** porque el envío falla ([CAP-04](captura.md#cap-04)).
  4. **Dado** una captura que se deshace, **cuando** se deshace, **entonces** no debería quedar la animación de entrega. **Hoy:** la app la reproduce igual.
- **Brechas código/docs:** —
- **Cobertura QA:** sin prueba E2E: la línea «Llegó tu captura a la oficina.» se retira a los 3,5 s y el sobre es dibujo de Skia sin vistas; en el emulador con render por software Maestro no la ve de forma fiable. Lo cubren `movil/src/scene/OficinaScreen.test.tsx` y `compartido/src/scene/engine.suite.ts` · 2026-11-08

### OFI-06 · Gestos en la escena <a id="ofi-06"></a>

- **Dónde:** app
- **Estado:** funciona
- **Qué hace para Gustavo:** en el teléfono mueve la oficina, hace zoom y recarga tirando hacia abajo desde arriba de la escena.
- **Código:** `movil/src/scene/OfficeCanvas.tsx` (`usePanGesture`, `usePinchGesture`, `useTapGesture`), `viewport.ts`, tokens de `theme/motion.ts`.
- **Criterios de aceptación:**
  1. **Dado** la escena, **cuando** arrastra (8 pt como mínimo), **entonces** la oficina se desplaza.
  2. **Dado** la escena, **cuando** pellizca, **entonces** hace zoom entre 1× y 3×; un doble toque vuelve al inicio, arriba de la oficina.
  3. **Dado** la escena en su parte de arriba, **cuando** tira hacia abajo más de 64 pt y suelta, **entonces** la escena cede un poco bajo el dedo y se vuelven a pedir la actividad y los eventos.
  4. **Dado** un toque en un personaje, **cuando** lo hace, **entonces** vibra levemente y se abre su panel.
- **Brechas código/docs:** —
- **Cobertura QA:** OFI-06.1, 3 y 4 y el doble toque de OFI-06.2 en `movil/.maestro/03-oficina.yaml` (arrastre, doble toque y tirar para recargar desde arriba de la escena, sin cierres) · el pellizco de OFI-06.2 no se puede hacer en Maestro (un solo dedo) · 2026-11-11 · pendiente de CI

### OFI-07 · Banner de máquina o cuenta en pausa <a id="ofi-07"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** en cualquier vista, una franja le recuerda que la máquina o la cuenta de LinkedIn está en pausa.
- **Código:** `overview.control` y `overview.accounts[].paused`; PWA `components/Layout.tsx:125-165`; app `components/shell/TopBar.tsx` (`PauseBanner`).
- **Criterios de aceptación:**
  1. **Dado** la máquina detenida, **cuando** abre cualquier vista, **entonces** ve «Máquina en pausa · <motivo>», con «· fijada en el entorno» si viene de `OPERATOR_PAUSED`, y al tocarla va a Ajustes › Máquina.
  2. **Dado** la máquina en marcha y la cuenta en pausa, **cuando** abre cualquier vista, **entonces** ve «La cuenta de LinkedIn está en pausa · <motivo>», que lleva a su tarjeta de Tu turno.
  3. **Dado** todo en marcha, **cuando** abre una vista, **entonces** no hay franja.
  4. **Dado** que la consulta del estado falla, **cuando** pasa, **entonces** la franja no aparece y no hay aviso (comportamiento actual en las dos interfaces).
  5. **Dado** la máquina detenida, **cuando** abre la oficina, **entonces** la escena se oscurece y se detiene.
- **Brechas código/docs:** —
- **Cobertura QA:** OFI-07.1, 3 y 5 en `movil/.maestro/03-oficina.yaml` (máquina parada con `comun/qa-api.js`) · OFI-07.2 sin prueba E2E · 2026-11-08 · pasa

### OFI-08 · Franja sin conexión <a id="ofi-08"></a>

- **Dónde:** PWA · app
- **Estado:** funciona
- **Qué hace para Gustavo:** si pierde la conexión, lo sabe y sigue viendo lo último que cargó.
- **Código:** PWA `Layout.tsx` (`OfflineStrip`, `navigator.onLine`); app `TopBar.tsx` (NetInfo).
- **Criterios de aceptación:**
  1. **Dado** que el dispositivo se queda sin red, **cuando** pasa, **entonces** aparece «Sin conexión. Mostrando lo último que cargó.» y los datos ya cargados siguen visibles.
  2. **Dado** que vuelve la red, **cuando** pasa, **entonces** la franja desaparece y las consultas se reanudan.
  3. **Dado** que recarga la PWA sin red, **cuando** abre una vista, **entonces** la aplicación abre (el service worker sirve la página), pero las vistas muestran error: no se guardan datos entre sesiones.
- **Brechas código/docs:** —
- **Cobertura QA:** OFI-08.1–2 en `movil/.maestro/02-navegacion.yaml` (modo avión) · OFI-08.3 es de la PWA · 2026-11-08 · pasa

### OFI-09 · Navegación <a id="ofi-09"></a>

- **Dónde:** PWA · app
- **Estado:** funciona
- **Qué hace para Gustavo:** llega a cada vista desde las barras, con el contador de la Bandeja de entrada (antes «Tu turno», renombrada el 12/11/2026) y el punto de Notificaciones siempre a la vista.
- **Código:** PWA `components/Layout.tsx`; app `components/shell/BottomBar.tsx`, `TopBar.tsx`, `TurnBadge.tsx` (el contador), `tabTransitions.ts`, `movil/src/app/(app)/(tabs)/_layout.tsx`.
- **Criterios de aceptación:**
  1. **Dado** la PWA en escritorio, **cuando** la abre, **entonces** la barra lateral tiene «Capturar», Oficina, Bandeja de entrada, Notificaciones, Calendario, Resultados, Personas, Galería y Ajustes, y el crédito «Arte: LimeZu · Modern Interiors».
  2. **Dado** la app, **cuando** la abre, **entonces** la barra inferior tiene Oficina, Resultados, el botón de captura, Personas y Bandeja (con su contador, en alerta si hay algo crítico; la Galería salió el 12/11/2026), y la superior los iconos de Notificaciones (con punto), Calendario y Ajustes. En la PWA en el teléfono la barra inferior sigue con Galería y la superior con la Bandeja de entrada (con contador), Notificaciones, Calendario y Ajustes.
  3. **Dado** una vista de detalle (pieza o persona), **cuando** la abre en el teléfono, **entonces** la barra superior muestra «‹» con el nombre de la vista a la que vuelve («‹ Calendario», «‹ Personas»; en la app, «‹ Bandeja» si la pieza se abrió desde la Bandeja); en la app, además, se vuelve deslizando desde el borde o con el botón atrás de Android.
  4. **Dado** «Saltar al contenido», **cuando** navega con teclado en la PWA, **entonces** es lo primero que recibe el foco.
  5. **Dado** cada vista de la PWA, **cuando** se abre, **entonces** el título de la pestaña es «<Vista> · 0ff1ce».
- **Brechas código/docs:** el diseño original (`DISENO-VISTAS.md`, rama `feat/rediseno-oficina`) tenía cinco entradas en la barra inferior (Oficina, Tu turno, Calendario, Resultados, Personas); la app pone desde el 12/11/2026 la Bandeja en la barra inferior (en el sitio de la Galería) y Notificaciones, Calendario y Ajustes arriba; la PWA en el teléfono sigue con Galería abajo y la Bandeja arriba.
- **Cobertura QA:** OFI-09.2–3 en `movil/.maestro/02-navegacion.yaml` (barras con la Bandeja abajo, contador y punto, atrás de Android por el historial, una ficha con «‹», atrás y arrastre del borde, «‹ Bandeja» en una pieza abierta por enlace) y Jest (`navegacion.test.tsx`, `barraSuperior.test.tsx`) · OFI-09.1, 4 y 5 son de la PWA.

### OFI-10 · Editor visual como integrante de Editorial <a id="ofi-10"></a>

- **Dónde:** PWA · app · backend
- **Estado:** implementado; CI y QA en vivo pendientes por Claude.
- **Qué hace para Gustavo:** ve quién está preparando los medios de cada pieza y puede abrir la misión y actividad de ese agente.
- **Responsable:** `editor_visual`, coordinado por `director_editorial`.
- **Cadencia:** con cada cambio de estado/evento del trabajo visual; reutiliza la actualización de actividad de la Oficina.
- **Tu turno:** ninguna aprobación por mostrar al rol. Sus entregables siguen EDI-21 y, para perfil, TUR-18.
- **Datos necesarios y disponibilidad:** el rol ocupa el cuarto asiento de Editorial y aparece en su tira/panel. La etapa `visual` y el ledger atribuyen actividad real; los eventos del dispatcher muestran solicitudes y respuestas director ⇄ Editor visual. Sin actividad recibida permanece quieto y muestra Sin datos.
- **Código:** `team_backend/oficina_views.py`, eventos existentes del dispatcher, `compartido/src/logic/roles.ts` y `scene`, paneles PWA/app. «Ver definición y conexiones» abre la ficha del registro en la PWA (la app retiró el mapa el 11/11/2026). Sprite existente reutilizado; cambios app solo TS/TSX, sin dependencias nativas.
- **Criterios de aceptación:**
  1. **Dado** el rol registrado, **cuando** abre Editorial en la PWA o app, **entonces** aparece «Editor visual», su misión y definición accesible desde el panel, y se actualiza el número de integrantes sin sustituir a director o copywriters.
  2. **Dado** un trabajo visual real, **cuando** se consulta, **entonces** muestra en cola, trabajando, en espera o bloqueo, con el detalle de la tarea y la pieza/propuesta de perfil asociada; si aún no hay runtime, muestra «En diseño».
  3. **Dado** una decisión/entrega visual, **cuando** llega su evento, **entonces** se atribuye a `editor_visual` y al destinatario real. Sin datos de actividad o con fallo de consulta queda quieto y muestra el aviso existente, sin simular trabajo.
- **Brechas código/docs:** falta ejecutar CI/QA; los encargos de Perfil siguen en fase 8.
- **Cobertura QA:** escritos casos backend de etapa/actividad y entregas, suites compartidas de estado/animación, Jest y Vitest de ficha/tira/mapa, Maestro 03-oficina y 17-mapa-equipo. Selección **`[qa: 03 07 11 16-imagenes 17-mapa-equipo]`**; Claude comprueba la escena a 390 × 844 y los handoffs reales.

## Mapa declarativo del equipo

[ARQ-08](arquitectura-agentes.md#arq-08), **no implementado**, añade «Mapa del equipo» en PWA y app, con grupos, conexiones, fichas de agentes, unidades y actividad. Consume el mismo registro que gobierna las llamadas y genera Mermaid (ARQ-01/07), sin mantener otro grafo en la escena.

## Retiradas

Ninguna.
