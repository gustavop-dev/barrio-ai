# Oficina (`OFI`)

La pantalla de inicio: la oficina en pixel art con los 16 roles del equipo, que se mueven solo cuando el backend registra trabajo real. Incluye lo común a todas las vistas: la navegación, el banner de pausa y la franja sin conexión.

- **Código:** backend `oficina_views.Actividad` (`ROLES`, `JOB_ROLES`, `DESCRIPTIONS`), `oficina_views.Eventos`, `oficina_eventos.py`, `Overview`; PWA `oficina/src/pages/Oficina.tsx`, `oficina/src/scene/*`, `components/Layout.tsx`; app `movil/src/scene/*`, `movil/src/components/shell/*`; común `compartido/src/scene/*` (motor, plan, roles, actividad, narración, paneles).
- **Documentación:** secciones «Oficina (escena)» y «Escena de la Oficina: feed de eventos» de [`CONTRATO-API.md`](../../oficina/CONTRATO-API.md), notas `comportamiento` y `backend` de `movil/diseno-movimiento/canvas.json`, [`movil/MOTION.md`](../../movil/MOTION.md).

## Resumen

| ID | Función | Dónde | Estado |
| --- | --- | --- | --- |
| [OFI-01](#ofi-01) | La escena refleja la actividad real | PWA · app · backend | con fallo conocido |
| [OFI-02](#ofi-02) | Estado de cada personaje | PWA · app · backend | funciona |
| [OFI-03](#ofi-03) | Línea de lo que pasa ahora y eventos del equipo | PWA · app · backend | funciona |
| [OFI-04](#ofi-04) | Paneles de equipo y de rol | PWA · app | funciona |
| [OFI-05](#ofi-05) | La captura llega a la oficina | PWA · app | parcial |
| [OFI-06](#ofi-06) | Gestos en la escena | app | funciona |
| [OFI-07](#ofi-07) | Banner de máquina o cuenta en pausa | PWA · app · backend | funciona |
| [OFI-08](#ofi-08) | Franja sin conexión | PWA · app | funciona |
| [OFI-09](#ofi-09) | Navegación | PWA · app | funciona |

---

### OFI-01 · La escena refleja la actividad real <a id="ofi-01"></a>

- **Dónde:** PWA · app · backend
- **Estado:** con fallo conocido
- **Qué hace para Gustavo:** abre 0ff1ce y ve a su equipo trabajando, sin simulaciones: si nadie trabaja, nadie se mueve.
- **Código:** `GET /api/v1/oficina/actividad` (cada 15 s), `GET /api/v1/operador/overview` (cada 30 s); PWA `OfficeCanvas.tsx` (canvas); app `OfficeCanvas.tsx` (Skia), `useOfficeScene.ts`, `useOfficeLifecycle.ts`.
- **Criterios de aceptación:**
  1. **Dado** un trabajo `prepare_piece` corriendo en la etapa `redactor`, **cuando** se consulta la actividad, **entonces** `copywriter_a` y `copywriter_b` están `trabajando` con «Redactando dos variantes en inglés» y su hora de inicio, y en la escena trabajan en su puesto.
  2. **Dado** un trabajo en cola, **cuando** se consulta, **entonces** el rol muestra «Trabajo en cola».
  3. **Dado** un rol implementado sin trabajo, **cuando** se consulta, **entonces** está `en_espera` con «Último: <tarea> (<resultado>)» si hubo uno.
  4. **Dado** un rol que no tiene ningún trabajo implementado, **cuando** se consulta, **entonces** está `diseno` con «Contrato diseñado; aún sin implementar»; ningún rol con código aparece en diseño.
  5. **Dado** `INBOX_ENABLED=true` y un trabajo `read_inbox` corriendo, **cuando** se consulta, **entonces** `conversaciones_inbox` está `trabajando`. **Hoy falla:** `JOB_ROLES` no incluye `read_inbox`, así que el agente de inbox sale siempre «en diseño» aunque esté leyendo el inbox.
  6. **Dado** que la actividad no se puede leer, **cuando** falla, **entonces** ve «No se pudo leer la actividad.» con «Mientras tanto los personajes quedan quietos: la oficina no simula trabajo.» y «Reintentar», y los personajes quedan quietos.
  7. **Dado** que el dibujo de la oficina no carga, **cuando** falla, **entonces** ve «No se pudo cargar el dibujo de la oficina.» (en la PWA, «… Recarga la página.»; en la app, con «Reintentar»).
  8. **Dado** la leyenda, **cuando** se pinta, **entonces** muestra Trabajando, En espera y En diseño, y «Actividad real · hace X», «Leyendo actividad…» o «Actividad no disponible».
  9. **Dado** la app en segundo plano o en otra pestaña, **cuando** pasa el tiempo, **entonces** la escena deja de consultar y de animar hasta volver.
  10. **Dado** «reducir movimiento» en el sistema, **cuando** abre la oficina, **entonces** la escena queda quieta.
- **El fallo:** el agente de inbox (`conversaciones_inbox`) aparece siempre «en diseño» porque `oficina_views.JOB_ROLES` no asigna el trabajo `read_inbox` a ningún rol. El contrato dice que `diseno` significa «tiene contrato pero aún no está implementado», y el inbox está implementado y encendido en producción.
- **Brechas código/docs:** `oficina/README.md` describe los botones «Activar ambiente» y «Luz de tarde», que no existen en el código actual.
- **Cobertura QA:** pendiente

### OFI-02 · Estado de cada personaje <a id="ofi-02"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** cada personaje muestra si trabaja, espera, está en diseño o no hay datos.
- **Código:** `compartido/src/scene/activity.ts`, `engine.ts`, `runtime.ts`.
- **Criterios de aceptación:**
  1. **Dado** un rol `trabajando`, **cuando** se pinta, **entonces** está en su puesto con el monitor encendido.
  2. **Dado** un rol `en_espera`, **cuando** pasa el tiempo, **entonces** puede dar paseos ambientales («Por un café»); solo estos se mueven sin trabajo.
  3. **Dado** un rol `diseno`, **cuando** se pinta, **entonces** está atenuado, quieto y con la etiqueta «EN DISEÑO».
  4. **Dado** un rol sin dato, **cuando** se pinta, **entonces** está quieto y sin luz.
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

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
- **Brechas código/docs:** en la app la línea se retira sola a los 3,5 s; en la PWA no. La PWA no muestra ningún aviso si fallan los eventos por otro motivo.
- **Cobertura QA:** pendiente

### OFI-04 · Paneles de equipo y de rol <a id="ofi-04"></a>

- **Dónde:** PWA · app
- **Estado:** funciona
- **Qué hace para Gustavo:** toca un personaje o una zona y ve qué hace ese rol o ese equipo, su misión y su estado real.
- **Código:** PWA `scene/OfficePanels.tsx`, `BottomSheet.tsx` (teléfono) o panel lateral (≥ 1.100 px); app `OfficePanels.tsx` en una hoja; `compartido/src/scene/panels.ts`.
- **Criterios de aceptación:**
  1. **Dado** la tira «Equipos» (siete equipos más «Biblioteca»), **cuando** toca uno, **entonces** se abre su panel con «ESPACIO DEL EQUIPO», el número, «Nuevo» en Relaciones y Operación, el propósito, «N INTEGRANTES · <lugar>», el recuento («2 trabajando · 1 en espera · 0 en diseño») y sus miembros.
  2. **Dado** un personaje, **cuando** lo toca, **entonces** ve «AGENTE» o «SERVICIO» con la zona, la misión, «ESTADO REAL» con el detalle y desde cuándo (o «Sin datos de actividad.»), y para Operación la nota de que es un servicio, no un agente de IA.
  3. **Dado** un rol en diseño, **cuando** abre su panel, **entonces** ve «Este rol está en diseño. Aparece en la oficina, pero todavía no trabaja.».
  4. **Dado** «LO ÚLTIMO QUE HIZO», **cuando** se pinta, **entonces** muestra hasta 3 eventos de esta sesión o «Nada todavía en esta sesión.» (no es historial del servidor).
  5. **Dado** «Ver en el Calendario», **cuando** lo pulsa, **entonces** abre `/calendario` (sin filtrar por rol).
  6. **Dado** la PWA en escritorio, **cuando** abre la oficina, **entonces** el panel lateral muestra Operación por defecto.
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

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
- **Cobertura QA:** pendiente

### OFI-06 · Gestos en la escena <a id="ofi-06"></a>

- **Dónde:** app
- **Estado:** funciona
- **Qué hace para Gustavo:** en el teléfono mueve la oficina, hace zoom y recarga tirando hacia abajo.
- **Código:** `movil/src/scene/OfficeCanvas.tsx:61-99`, `viewport.ts`, tokens de `theme/motion.ts`.
- **Criterios de aceptación:**
  1. **Dado** la escena, **cuando** arrastra (8 pt como mínimo), **entonces** la oficina se desplaza.
  2. **Dado** la escena, **cuando** pellizca, **entonces** hace zoom entre 1× y 3×; un doble toque vuelve al inicio.
  3. **Dado** la pantalla, **cuando** tira hacia abajo, **entonces** se vuelven a pedir la actividad y los eventos.
  4. **Dado** un toque en un personaje, **cuando** lo hace, **entonces** vibra levemente y se abre su panel.
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

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
- **Cobertura QA:** pendiente

### OFI-08 · Franja sin conexión <a id="ofi-08"></a>

- **Dónde:** PWA · app
- **Estado:** funciona
- **Qué hace para Gustavo:** si pierde la conexión, lo sabe y sigue viendo lo último que cargó.
- **Código:** PWA `Layout.tsx` (`OfflineStrip`, `navigator.onLine`); app `TopBar.tsx` (NetInfo).
- **Criterios de aceptación:**
  1. **Dado** que el dispositivo se queda sin red, **cuando** pasa, **entonces** aparece «Sin conexión. Mostrando lo último que cargó.» y los datos ya cargados siguen visibles.
  2. **Dado** que vuelve la red, **cuando** pasa, **entonces** la franja desaparece y las consultas se reanudan.
  3. **Dado** que recarga la PWA sin red, **cuando** abre una vista, **entonces** la aplicación abre (el service worker sirve la página), pero las vistas muestran error: no se guardan datos entre sesiones.
- **Brechas código/docs:** en la app, abrirla sin conexión cierra la sesión ([ACC-06](acceso.md#acc-06)), y los errores de red salen en inglés ([APP-08](app-movil-instalacion.md#app-08)).
- **Cobertura QA:** pendiente

### OFI-09 · Navegación <a id="ofi-09"></a>

- **Dónde:** PWA · app
- **Estado:** funciona
- **Qué hace para Gustavo:** llega a cada vista desde las barras, con el contador de Tu turno y el punto de Notificaciones siempre a la vista.
- **Código:** PWA `components/Layout.tsx`; app `components/shell/BottomBar.tsx`, `TopBar.tsx`, `movil/src/app/(app)/(tabs)/_layout.tsx`.
- **Criterios de aceptación:**
  1. **Dado** la PWA en escritorio, **cuando** la abre, **entonces** la barra lateral tiene «Capturar», Oficina, Tu turno, Notificaciones, Calendario, Resultados, Personas, Galería y Ajustes, y el crédito «Arte: LimeZu · Modern Interiors».
  2. **Dado** la PWA en el teléfono o la app, **cuando** la abre, **entonces** la barra inferior tiene Oficina, Resultados, el botón de captura, Personas y Galería, y la superior los iconos de Tu turno (con contador), Notificaciones (con punto), Calendario y Ajustes.
  3. **Dado** una vista de detalle (pieza o persona), **cuando** la abre en el teléfono, **entonces** la barra superior muestra «‹ Calendario» o «‹ Personas»; en la app, además, se vuelve deslizando desde el borde o con el botón atrás de Android.
  4. **Dado** «Saltar al contenido», **cuando** navega con teclado en la PWA, **entonces** es lo primero que recibe el foco.
  5. **Dado** cada vista de la PWA, **cuando** se abre, **entonces** el título de la pestaña es «<Vista> · 0ff1ce».
- **Brechas código/docs:** el diseño original (`DISENO-VISTAS.md`, rama `feat/rediseno-oficina`) tenía cinco entradas en la barra inferior (Oficina, Tu turno, Calendario, Resultados, Personas); el código actual pone Galería en la barra inferior y Tu turno y Calendario arriba, como el diseño móvil de `movil/diseno-movimiento`.
- **Cobertura QA:** pendiente

## Retiradas

Ninguna.
