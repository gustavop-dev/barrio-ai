# Calendario y piezas (`CAL`)

Lo que el equipo hizo y va a hacer, día a día y por capas, y el detalle de cada pieza diaria: su resultado, su texto, cómo se escribió y el veto. El circuito que prepara y publica las piezas está en [motor-editorial.md](motor-editorial.md).

- **Código:** backend `rediseno_views.Calendar`, `Activity`, `upcoming`, `item`, `editorial_views.PieceDetail`, `Plan`, `operador.reject`; PWA `oficina/src/pages/Calendario.tsx`, `pages/calendario/*`, `pages/PiezaDetalle.tsx`; app `movil/src/calendario/*`, `movil/src/pieza/*`, `movil/src/app/(app)/calendario/pieza/[id].tsx`; común `compartido/src/logic/events.ts`, `editorial.ts`, `piece.ts`, `dates.ts`.
- **Documentación:** secciones «Calendario» y «Publicación diaria (editorial)» de [`CONTRATO-API.md`](../../oficina/CONTRATO-API.md), [`rediseno-backend.md`](../../agentes-linkedin/infra/docs/rediseno-backend.md).

## Resumen

| ID | Función | Dónde | Estado |
| --- | --- | --- | --- |
| [CAL-01](#cal-01) | Vistas Mes, Semana y Lista | PWA · app · backend | funciona |
| [CAL-02](#cal-02) | Capas del calendario | PWA · app · backend | funciona |
| [CAL-03](#cal-03) | Panel del día | PWA · app · backend | parcial |
| [CAL-04](#cal-04) | «Próximo» y lo que está en cola | PWA · app · backend | funciona |
| [CAL-05](#cal-05) | «Lo que pasó» y «Ver todo lo del día» | PWA · app · backend | funciona |
| [CAL-06](#cal-06) | Detalle de una pieza: cabecera y estado | PWA · app · backend | funciona |
| [CAL-07](#cal-07) | Resultado de una pieza publicada | PWA · app · backend | funciona |
| [CAL-08](#cal-08) | Texto final y «Copiar» | PWA · app · backend | funciona |
| [CAL-09](#cal-09) | «Cómo se escribió» | PWA · app · backend | funciona |
| [CAL-10](#cal-10) | Pieza en preparación | PWA · app · backend | funciona |
| [CAL-11](#cal-11) | Comentario para el equipo sobre una pieza | PWA · app · backend | funciona |
| [CAL-12](#cal-12) | Vetar una pieza | PWA · app · backend | funciona |
| [CAL-13](#cal-13) | Vetar una acción en cola | PWA · app · backend | funciona |
| [CAL-14](#cal-14) | «Preparar la siguiente pieza» | PWA · app · backend | funciona |
| [CAL-15](#cal-15) | Aprobar una pieza en modo aprobación | PWA · app · backend | parcial |
| [CAL-16](#cal-16) | Enlaces antiguos llevan al Calendario o a la pieza | PWA · app | funciona |
| [CAL-17](#cal-17) | Fecha prevista y aviso de una captura urgente | backend | funciona |

---

### CAL-01 · Vistas Mes, Semana y Lista <a id="cal-01"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** ve el mes, la semana o una línea de tiempo de lo que pasó y lo que viene, y se mueve entre periodos.
- **Código:** `GET /api/v1/calendario?desde=&hasta=` (por día local de `America/Bogota`, como mucho 93 días); PWA `Calendario.tsx`, `calendario/Grids.tsx`; app `CalendarioScreen.tsx`, `Grids.tsx`, `Pager.tsx`.
- **Criterios de aceptación:**
  1. **Dado** el Calendario, **cuando** lo abre, **entonces** ve la vista Semana por defecto, con el control «Mes» | «Semana» | «Lista», «Hoy» y las flechas de periodo anterior y siguiente; el estado queda en la URL (`?vista=&fecha=&capas=&tipo=&no_salio=`).
  2. **Dado** un teléfono o navegador en otra zona horaria, **cuando** lo abre, **entonces** el subtítulo añade «· Horas de Bogotá».
  3. **Dado** la vista Mes, **cuando** cambia de mes, **entonces** cada día muestra los puntos de las capas con eventos y hoy va marcado; en la app se puede deslizar entre meses y semanas.
  4. **Dado** un mes sin nada, **cuando** lo abre, **entonces** ve «No hay nada registrado en este mes.».
  5. **Dado** un error al cargar, **cuando** falla, **entonces** ve «No se pudo cargar el calendario» con «Reintentar».
  6. **Dado** un rango de más de 93 días o fechas inválidas, **cuando** se pide a la API, **entonces** responde 400.
  7. **Dado** la app, **cuando** abre el Calendario, **entonces** llega desde el icono de la barra superior (no es una pestaña de la barra inferior).
  8. **Dado** un día con varias piezas (intentos que no salieron y la que sí va), **cuando** se muestra el día (`/calendario` y `/editorial/calendar`), **entonces** solo aparece su pieza viva (en preparación, lista, programada, publicándose, publicada, incierta o rehaciéndose); sin ninguna viva, solo su último intento; y un día próximo que solo se frenó por el presupuesto diario queda vacío porque el piloto lo prepara el día anterior (`editorial.calendar_rows`). Los intentos viejos siguen abriéndose desde su enlace.
  9. **Dado** la hoja del día (y el panel de la Oficina), **cuando** está abierta, **entonces** no hay botón «Cerrar»: se cierra deslizándola hacia abajo o con atrás de Android; el lector de pantalla tiene la acción «Cerrar» en la manija.
- **Brechas código/docs:** —
- **Cobertura QA:** CAL-01.1, 3, 4, 5 y 7 en `movil/.maestro/07-calendario.yaml` y `07-calendario-errores.yaml` (Semana, Mes y Lista, deslizar semanas y meses, mes vacío, error con «Reintentar») · CAL-01.2 y 6 sin prueba E2E · 2026-11-08 · pasa

### CAL-02 · Capas del calendario <a id="cal-02"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** enciende o apaga las capas Tuyo, Publicaciones, Red, Conversaciones y Sistema.
- **Código:** `layers` y `events[].layer` de `GET /api/v1/calendario`; PWA y app `LayerChips`.
- **Criterios de aceptación:**
  1. **Dado** los chips de capa, **cuando** apaga «Red», **entonces** desaparecen los eventos de red y el filtro queda en `?capas=`.
  2. **Dado** la capa Conversaciones, que llega como `parcial`, **cuando** se pinta, **entonces** dice «Conversaciones · parcial» con «Por ahora solo las oportunidades: las conversaciones llegan con el inbox».
  3. **Dado** una capa que llega como `false`, **cuando** se pinta, **entonces** aparece desactivada con «· aún no disponible».
  4. **Dado** los eventos de un día, **cuando** se ordenan, **entonces** van por capa (Tuyo, Sistema, Publicaciones, Conversaciones, Red) y después por hora.
  5. **Dado** cada capa, **cuando** hay datos, **entonces** muestra: Tuyo (plazos de preguntas, siguientes acciones y reuniones de oportunidades, caducidad de LinkedIn, lo resuelto), Publicaciones (cada pieza con su estado), Red (conexiones que encajan agrupadas, invitaciones recibidas y aceptadas, invitaciones previstas como estimación), Conversaciones (oportunidades nuevas o que cambian de etapa) y Sistema (paradas, reanudaciones, pausas de cuenta, acciones inciertas o fallidas).
- **Brechas código/docs:** la capa Conversaciones sigue marcada `parcial` y sin conversaciones del inbox, aunque el inbox ya está implementado ([INB-01](inbox.md#inb-01)).
- **Cobertura QA:** CAL-02.1 y 2 en `07-calendario.yaml` y `07-pieza-estados.yaml` («Conversaciones · parcial», apagar «Red» y volver a encenderla) · CAL-02.3–5 sin prueba E2E · 2026-11-08 · pasa

### CAL-03 · Panel del día <a id="cal-03"></a>

- **Dónde:** PWA · app · backend
- **Estado:** parcial
- **Qué hace para Gustavo:** al elegir un día ve su resumen (qué publicó y cuántas interacciones hubo), lo que le tocaba a él, la publicación del día, lo programado y lo importante.
- **Código:** PWA `calendario/DayPanel.tsx`; app `DayPanel.tsx` (en línea y en una hoja).
- **Lo que falta:** en la PWA, si falla la carga del calendario, el panel del día se pinta como un día vacío («Sin actividad registrada.», «Hueco libre…», «Nada importante en las capas visibles.») junto al error (`Calendario.tsx:65`). La app ya dice «No se pudo cargar este día.» y, si falla la pieza del día, muestra el error con «Reintentar».
- **Criterios de aceptación:**
  1. **Dado** hoy o un día pasado, **cuando** lo elige, **entonces** ve el encabezado con «Hoy» o «Pasado» y el resumen («1 post · 6 comentarios · …»); cada cifra abre «Ver todo lo del día» filtrado.
  2. **Dado** un día sin actividad, **cuando** lo elige, **entonces** ve «Sin actividad registrada.».
  3. **Dado** un plazo de pregunta ese día, **cuando** lo elige, **entonces** «Tu parte» muestra «Plazo: HH:MM» (o «Hecho ✓» si ya respondió) e «Ir a Tu turno».
  4. **Dado** un día futuro sin pieza, **cuando** lo elige, **entonces** ve «Hueco libre. El equipo prepara cada pieza N h antes de su hora.»; uno pasado sin pieza dice «Sin publicación.».
  5. **Dado** un día a más de 15 días, **cuando** lo elige, **entonces** ve «Todavía no hay nada programado tan lejos.».
  6. **Dado** acciones en cola o invitaciones previstas, **cuando** lo elige, **entonces** «Programado» las muestra, cada acción con «Vetar», y «Invitaciones previstas: N personas».
  7. **Dado** que falla la carga del calendario, **cuando** se muestra el error, **entonces** el panel del día no dice que el día está vacío: muestra que no se pudo cargar. **Hoy falla en la PWA.**
  8. **Dado** que falla la carga de la pieza del día, **cuando** se pinta la tarjeta, **entonces** se ve un error con «Reintentar».
- **Brechas código/docs:** —
- **Cobertura QA:** CAL-03.1–5 y 7–8 en `07-calendario.yaml`, `07-pieza-estados.yaml` y `07-calendario-errores.yaml` (hoja media y completa sin tapar la tira, «Ver todo lo del día» filtrado, «Tu parte», hueco libre, sin publicación, día lejano, panel y pieza del día que fallan) · CAL-03.6 visto en las capturas («Programado» con «Vetar») · 2026-11-08 · pasa

### CAL-04 · «Próximo» y lo que está en cola <a id="cal-04"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** en la Lista ve la próxima pieza (con su etapa, tesis y primeras líneas) y las acciones que esperan su turno, con la hora estimada, y puede vetarlas.
- **Código:** `upcoming` de `GET /api/v1/actividad` (`rediseno_views.upcoming`, `next_execution_time`); PWA `calendario/ListView.tsx`; app `ListView.tsx`.
- **Criterios de aceptación:**
  1. **Dado** una pieza en preparación o lista en los próximos días, **cuando** abre la Lista, **entonces** «Próximo» muestra la primera con su estado, la hora, la tesis (o «El equipo prepara la pieza»), las tres primeras líneas, «Etapa: …», «Vetar» si se puede y «Ver cómo se escribió». En la app la tarjeta entera abre la pieza (sin ese enlace) y la tesis y las primeras líneas se recortan a dos líneas con «…».
  2. **Dado** acciones aprobadas sin ejecutar (comentarios, acciones de red), **cuando** abre la Lista, **entonces** aparecen en «En cola» con su hora estimada de salida (según la ventana y el espaciado) y «Vetar».
  3. **Dado** que no hay pieza programada, **cuando** abre la Lista, **entonces** ve «No hay pieza programada para los próximos días.» y «Preparar la siguiente pieza» ([CAL-14](#cal-14)).
  4. **Dado** una pieza ya publicada, fallida o incierta, **cuando** se calcula «Próximo», **entonces** no aparece.
  5. **Dado** la carga en curso o un error, **cuando** abre la Lista, **entonces** ve «Cargando lo próximo…» o el error con «Reintentar».
- **Brechas código/docs:** —
- **Cobertura QA:** CAL-04.1–3 y 5 en `07-calendario.yaml`, `07-pieza-veto.yaml` y `07-calendario-errores.yaml` («Próximo», «En cola», sin pieza en camino, error y vacío) · CAL-04.4 sin prueba E2E · 2026-11-08 · pasa

### CAL-05 · «Lo que pasó» y «Ver todo lo del día» <a id="cal-05"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** repasa todo lo que hizo el equipo (comentarios, reacciones, seguimientos, invitaciones, publicaciones), con el texto, el destino y el porqué, y puede ver también lo que no salió.
- **Código:** `GET /api/v1/actividad?tipo=&desde=&hasta=&no_salio=&limit=&offset=` (`rediseno_views.Activity`, `item`); PWA y app `ActivityList.tsx`.
- **Criterios de aceptación:**
  1. **Dado** acciones de varios tipos, **cuando** abre «Lo que pasó», **entonces** las ve agrupadas por día, de la más reciente a la más antigua, con frases como «Comentaste en el post de X», «Seguiste a X», «Invitaste a X (sin nota)», «Aceptaste la invitación de X» o «Publicaste: …», su estado, el enlace a LinkedIn, «Ver el comentario» o «Ver el post» y «Por qué».
  2. **Dado** los chips «Todo», «Publicaciones», «Comentarios», «Reacciones» y «Red», **cuando** elige uno, **entonces** se filtra; un tipo desconocido en la API responde 404.
  3. **Dado** «Mostrar lo que no salió», **cuando** lo activa, **entonces** aparecen también las vetadas, descartadas, caducadas y sustituidas («Vetada por ti», «Descartada por la política», «Caducada», «Sustituida»); las fallidas y las inciertas se ven siempre.
  4. **Dado** una acción decidida por el líder, **cuando** se pinta, **entonces** se puede ver quién decidió (`decided_by` = `lider`) y sus respuestas.
  5. **Dado** más de 50 elementos, **cuando** pulsa «Cargar más», **entonces** carga los siguientes.
  6. **Dado** un filtro sin resultados, **cuando** lo aplica, **entonces** ve «No hay nada registrado con este filtro.» (o «Nada registrado ese día con este filtro.» en un día).
  7. **Dado** el enlace de `lead_silent` (`/calendario?vista=lista&tipo=comentarios&no_salio=1`), **cuando** lo abre, **entonces** llega a la Lista con ese filtro.
- **Brechas código/docs:** en la app, «tirar para recargar» en la Lista solo recarga la actividad sin filtro; con filtro hay que esperar a la consulta de cada 30 s.
- **Cobertura QA:** CAL-05.1–3 y 6 en `07-calendario.yaml` y `07-calendario-errores.yaml` (filtro «Red», «Mostrar lo que no salió» con «Vetada por ti», día y lista sin resultados) · CAL-05.4, 5 y 7 sin prueba E2E · 2026-11-08 · pasa

### CAL-06 · Detalle de una pieza: cabecera y estado <a id="cal-06"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** abre una pieza y ve de qué día es, en qué estado está y, si algo fue mal, por qué.
- **Código:** `GET /api/v1/editorial/pieces/<id>`; PWA `PiezaDetalle.tsx` (`/calendario/pieza/:id`); app `pieza/PiezaScreen.tsx`.
- **Criterios de aceptación:**
  1. **Dado** una pieza, **cuando** abre su detalle, **entonces** ve «Pieza del <día>», la etiqueta de estado («Preparándose», «Día sin pieza», «Bloqueada por el verificador», «Pendiente de aprobación», «Programada», «Publicándose», «Publicada», «Incierta», «Vetada», «Descartada por la política», «Caducada», «Sustituida», «Fallida») y la hora («Sale <día> a las HH:MM», «Salió a las …», «Etapa: …»).
  2. **Dado** una pieza bloqueada, **cuando** abre el detalle, **entonces** ve «El verificador bloqueó la pieza» con los motivos.
  3. **Dado** una pieza saltada, vetada, descartada, fallida o incierta, **cuando** abre el detalle, **entonces** ve «Ese día no hubo publicación» (con el motivo del director), «La vetaste» con «Tu nota: …», «La política no aprobó la pieza», «La publicación falló» o «No se sabe si salió» con «Resuélvela en Tu turno».
  4. **Dado** «Calendario» (volver), **cuando** lo pulsa en la PWA, **entonces** vuelve al día de la pieza (`/calendario?fecha=<día>`); en la app vuelve atrás, o a hoy si llegó desde una notificación.
  5. **Dado** la carga, **cuando** abre el detalle, **entonces** ve «Cargando la pieza…»; con error y sin datos, «No se pudo cargar la pieza» con «Reintentar»; con datos, «No se pudo actualizar la pieza».
  6. **Dado** un id que no existe, **cuando** abre el detalle, **entonces** ve un mensaje de pieza no encontrada. **Hoy:** la PWA muestra el genérico «No encontrado.».
- **Brechas código/docs:** —
- **Cobertura QA:** CAL-06.1–3 y 5 en `07-pieza-veto.yaml`, `07-pieza-estados.yaml` y `07-calendario-errores.yaml` (programada, bloqueada, saltada, fallida, vetada, error con «Reintentar») · CAL-06.4 y 6 sin prueba E2E · 2026-11-08 · pasa

### CAL-07 · Resultado de una pieza publicada <a id="cal-07"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** ve cómo le fue al post a las 24 h, a las 72 h y a los 7 días, y quién comentó.
- **Código:** `snapshots`, `metrics`, `commenters` del detalle (`resultados.piece_snapshots`, `piece_commenters`); PWA `calendario/Resultado.tsx`; app `pieza/Resultado.tsx`.
- **Criterios de aceptación:**
  1. **Dado** una pieza publicada con cortes, **cuando** abre el detalle, **entonces** ve «Interacción = (reacciones + comentarios + republicaciones) / impresiones.» y, para «A 24 h», «A 72 h» y «A 7 días», impresiones, reacciones, comentarios, republicaciones e interacción.
  2. **Dado** un dato que falta, **cuando** se pinta, **entonces** se ve «—», nunca 0.
  3. **Dado** un corte que aún no llega, **cuando** se pinta, **entonces** ve «Aún no» con «Llega el <día> a las HH:MM.»; si pasó su hora sin leerse, «Sin dato» con «El corte no se pudo leer a tiempo.».
  4. **Dado** solo la última lectura, **cuando** se pinta, **entonces** ve «Última lectura: N impresiones, hace X.».
  5. **Dado** comentaristas leídos, **cuando** se pinta «Quién comentó», **entonces** ve chips por rol («Comprador · 2», «Sin clasificar · N»); si no se leyeron, «Los comentarios aún no se han leído.»; si nadie comentó, «Nadie ha comentado todavía.».
  6. **Dado** la URL del post, **cuando** pulsa «Ver el post en LinkedIn», **entonces** se abre fuera de la app (solo si es https).
- **Brechas código/docs:** —
- **Cobertura QA:** CAL-07.1–3, 5 y 6 en `07-pieza-estados.yaml` y `08-resultados.yaml` (cortes, «—» sin republicaciones, «Aún no», quién comentó; el enlace a LinkedIn se ve, no se abre) · CAL-07.4 sin prueba E2E · 2026-11-08 · pasa

### CAL-08 · Texto final y «Copiar» <a id="cal-08"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** lee el texto exacto que se publica (en inglés) y lo copia.
- **Código:** `final_text`; PWA `PiezaDetalle.tsx:72-99`; app `pieza/FinalText.tsx`.
- **Criterios de aceptación:**
  1. **Dado** una pieza con texto final, **cuando** abre el detalle, **entonces** ve el texto por párrafos, «N caracteres», «Copiar» y «Se publica tal cual, en inglés.».
  2. **Dado** «Copiar», **cuando** lo pulsa, **entonces** el texto queda en el portapapeles y el botón dice «Copiado»; si falla, la PWA dice «No se pudo copiar».
  3. **Dado** una pieza sin selección todavía, **cuando** abre el detalle, **entonces** ve «El texto final aparece cuando termine la selección.».
- **Brechas código/docs:** en la app no se comprobó qué pasa si falla el portapapeles.
- **Cobertura QA:** CAL-08.1 y 3 en `07-pieza-veto.yaml` y `07-pieza-estados.yaml` · CAL-08.2: se toca «Copiar» sin «No se pudo copiar»; «Copiado» dura menos que un toque de Maestro · 2026-11-08 · pasa

### CAL-09 · «Cómo se escribió» <a id="cal-09"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** abre, plegado por secciones, el brief, las dos variantes, el panel de lectores, la selección, el verificador, la reparación y lo que costó.
- **Código:** `brief`, `variants`, `panel`, `selection`, `verification` (con `rules` y `repair`), `citations`, `signals`, `usage`; PWA `calendario/ComoSeEscribio.tsx`; app `pieza/ComoSeEscribio.tsx`.
- **Criterios de aceptación:**
  1. **Dado** una pieza lista, **cuando** abre «Cómo se escribió», **entonces** ve las secciones cerradas: Brief (lector, modalidad, pilar, tesis, enfoque, formato, valor para el lector, criterio de éxito, qué evitar, evidencia, por qué), Variantes A y B (con «Elegida»), Panel de lectores («Cinco perspectivas simuladas: son hipótesis…»), Selección, Verificador («Afirmaciones comprobadas N de M») y Fuentes y coste (coste por etapa y total).
  2. **Dado** una ronda de reparación, **cuando** abre el detalle, **entonces** aparece «Ronda de reparación» con qué había que corregir, qué cambió y el texto antes de reparar; sin ronda, la sección no aparece.
  3. **Dado** una etapa que no corrió, **cuando** abre su sección, **entonces** ve «Esta etapa aún no ha corrido.» o «Esta etapa no llegó a correr.».
  4. **Dado** que no hay coste registrado, **cuando** abre Fuentes y coste, **entonces** ve «Sin dato de coste.».
  5. **Dado** las variantes, **cuando** las mira en el teléfono, **entonces** van en pestañas (o deslizables en la app); en escritorio, lado a lado.
- **Brechas código/docs:** —
- **Cobertura QA:** CAL-09.1–3 y 5 en `07-pieza-veto.yaml` y `07-pieza-estados.yaml` (cada pliegue, variantes deslizadas, ronda de reparación, etapa que no corrió) · CAL-09.4 sin prueba E2E · 2026-11-08 · pasa

### CAL-10 · Pieza en preparación <a id="cal-10"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** mientras el equipo prepara la pieza, ve en qué etapa va.
- **Código:** `stage` de la pieza; PWA `PiezaDetalle.tsx`; app `pieza/PreparationTrack.tsx`.
- **Criterios de aceptación:**
  1. **Dado** una pieza en `preparing` con `stage: "lectores"`, **cuando** abre el detalle, **entonces** ve los cinco pasos (Director, Redactores, Panel de lectores, Selección, Verificador) con los dos primeros «Hecho» y el tercero «Ahora», y «Sale … a las HH:MM. Puedes vetarla cuando esté lista.».
  2. **Dado** la etapa `reparacion`, **cuando** se pinta, **entonces** la etiqueta de etapa lo refleja.
  3. **Dado** que la pieza avanza, **cuando** pasan 30 s, **entonces** el detalle se actualiza solo.
- **Brechas código/docs:** —
- **Cobertura QA:** sin prueba E2E: una pieza en preparación en el mundo de QA dejaría siempre algo «en camino» y CAL-04.3 y CAL-14 no se podrían probar · 2026-11-08 · pasa

### CAL-11 · Comentario para el equipo sobre una pieza <a id="cal-11"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** desde la pieza le dice algo al equipo, por escrito o con la voz, y lo ve en «Tus comentarios para el equipo»; el director lo tiene en cuenta en las piezas siguientes.
- **Código:** «Comentario para el equipo» abre la captura con contexto `pieza` ([CAP-07](captura.md#cap-07)); `team_comments` del detalle (`capturas.piece_comments`); PWA `PiezaDetalle.tsx`; app `pieza/TeamComments.tsx`.
- **Criterios de aceptación:**
  1. **Dado** una pieza, **cuando** pulsa «Comentario para el equipo», **entonces** se abre la captura con el chip «Comentario sobre la pieza» y su tesis.
  2. **Dado** el comentario enviado y procesado, **cuando** abre el detalle, **entonces** aparece en «Tus comentarios para el equipo» con la nota o la transcripción, «hace X» y «Escuchar» si tiene audio.
  3. **Dado** un comentario de voz en la app, **cuando** lo envía, **entonces** llega igual que uno escrito.
  4. **Dado** comentarios de los últimos 30 días, **cuando** corre el director, **entonces** los recibe en `feedback_from_gustavo` ([EDI-17](motor-editorial.md#edi-17)).
- **Brechas código/docs:** un comentario solo aparece cuando el backend lo marca `anotado`; mientras se procesa, el detalle no lo muestra como pendiente.
- **Cobertura QA:** CAL-11.1 en `07-pieza-veto.yaml` (abre la captura con «Comentario sobre la pieza») y `05-captura-contexto.yaml` (el chip con la tesis) · el envío es de `05-captura-*.yaml` · 2026-11-11

### CAL-12 · Vetar una pieza <a id="cal-12"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** si no quiere que salga una pieza, la veta antes de su hora con una nota; ese día queda sin publicación.
- **Código:** `POST /api/v1/operador/actions/<action.id>/reject {note}` (`operador.reject`); PWA `calendario/Veto.tsx` (inmediato); app `movil/src/calendario/Veto.tsx`, `pendingVeto.ts` (espera 5 s para poder deshacer).
- **Criterios de aceptación:**
  1. **Dado** una pieza cuya acción está en `proposed` o `approved`, **cuando** abre su detalle o su tarjeta, **entonces** ve «El equipo publica solo. Si no quieres que salga, vétala antes de las HH:MM: ese día quedará sin publicación.» y «Vetar».
  2. **Dado** «Vetar», **cuando** lo pulsa, **entonces** se abre «Vetar la pieza» con la nota obligatoria «Por qué no debe salir» y «La pieza no saldrá a las HH:MM y ese día quedará sin publicación. Queda registrada con tu nota.».
  3. **Dado** que confirma en la PWA, **cuando** termina, **entonces** la acción pasa a `rejected`, la pieza a «Vetada», aparece «Vetada» y las ideas de Gustavo que usaba vuelven a la mesa editorial.
  4. **Dado** que confirma en la app, **cuando** termina, **entonces** aparece «Vetada» con «Deshacer» durante 5 s: si lo pulsa, no se envía nada («Veto deshecho»); si no, se envía al pasar los 5 s, o al momento si la app pasa a segundo plano.
  5. **Dado** que la pieza ya se está publicando, **cuando** veta, **entonces** la API responde 409 «Solo se rechazan propuestas aún no ejecutadas.» y se ve «No se puede ahora» (en la app, «No se pudo vetar. …»).
  6. **Dado** una pieza ya publicada, saltada o bloqueada, **cuando** abre el detalle, **entonces** no hay botón «Vetar».
  7. **Dado** un token de servicio, **cuando** intenta vetar, **entonces** recibe 403.
- **Brechas código/docs:** la API acepta el veto sin nota (`note` opcional en `DecisionInput`); la nota obligatoria la pone la interfaz. En la app, cerrar la app a la fuerza durante los 5 s pierde el veto (lo dice un comentario en `pendingVeto.ts`), y un error del envío en segundo plano probablemente no se ve.
- **Cobertura QA:** CAL-12.1, 2, 4 y 6 en `07-pieza-veto.yaml` (nota obligatoria, «Deshacer», veto enviado a los 5 s) · CAL-12.5 en `07-calendario-errores.yaml` (veto rechazado: «No se pudo vetar») · CAL-12.3 y 7 sin prueba E2E · 2026-11-08 · pasa

### CAL-13 · Vetar una acción en cola <a id="cal-13"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** veta un comentario o una acción de red que está esperando su turno; si es de red, esa persona queda descartada para siempre.
- **Código:** el mismo `reject`; para RED-* llama a `red.on_rejected` ([BAR-10](red.md#bar-10)).
- **Criterios de aceptación:**
  1. **Dado** un comentario en cola, **cuando** lo veta con nota, **entonces** se ve «La acción no saldrá. Queda registrada con tu nota.», la acción pasa a `rejected` y desaparece de «En cola».
  2. **Dado** una acción de red, **cuando** abre el veto, **entonces** el texto avisa «No saldrá, y vetar una acción de red descarta a <persona> para siempre: el equipo no la volverá a proponer.».
  3. **Dado** que confirma el veto de red, **cuando** termina, **entonces** la persona pasa a `discarded`.
- **Brechas código/docs:** —
- **Cobertura QA:** CAL-13.1 y 2 en `07-calendario.yaml` (veto de una invitación en cola, que sale a los 5 s, y de una reacción con «Deshacer») · CAL-13.3 sin prueba E2E · 2026-11-08 · pasa

### CAL-14 · «Preparar la siguiente pieza» <a id="cal-14"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** cuando no hay ninguna pieza en camino, pide al equipo que prepare la próxima, sabiendo que cuesta dinero.
- **Código:** PWA `calendario/Veto.tsx` (`PlanNextButton`); app `movil/src/calendario/Veto.tsx`; `POST /api/v1/editorial/plan` ([EDI-02](motor-editorial.md#edi-02)).
- **Criterios de aceptación:**
  1. **Dado** que no hay pieza programada, **cuando** mira la publicación del día o «Próximo», **entonces** ve «Preparar la siguiente pieza».
  2. **Dado** el botón, **cuando** lo pulsa, **entonces** ve «Pone en cola el circuito editorial para el próximo día libre (como mucho a siete días): director, dos redactores, panel de lectores, selección y verificador.» y «Tiene coste: cada etapa llama a Claude y gasta del presupuesto editorial. Si la pieza pasa el verificador, saldrá sola a su hora salvo que la vetes.», con «Preparar» y «Cancelar».
  3. **Dado** que confirma, **cuando** la API responde 202, **entonces** ve «Preparación en cola para el <día>. El circuito tarda unos minutos y la pieza aparecerá en el calendario.».
  4. **Dado** un 409 (sin LinkedIn, en pausa o sin hueco), **cuando** vuelve, **entonces** el motivo se ve dentro de la confirmación.
  5. **Dado** dos pulsaciones del mismo intento, **cuando** se envían, **entonces** llevan el mismo `request_id` y solo se encola una preparación.
- **Brechas código/docs:** la confirmación no da una cifra de coste y sigue diciendo «presupuesto editorial», que desde el 10/11/2026 es el presupuesto general de IA del equipo ([EDI-13](motor-editorial.md#edi-13)).
- **Cobertura QA:** CAL-14.1–3 en `07-pieza-veto.yaml` (con la API del mundo de QA responde 202 y la preparación queda en cola) · CAL-14.4 y 5 sin prueba E2E · 2026-11-08 · pasa

### CAL-15 · Aprobar una pieza en modo aprobación <a id="cal-15"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** si la publicación diaria está en modo aprobación (por ejemplo para la primera pieza, como recomienda `publicacion-diaria.md`), aprueba la pieza antes de que salga.
- **Código:** `POST /api/v1/operador/actions/<id>/approve {expected_hash, note}`; `useApproveAction` (`compartido/src/api/hooks.ts`); app `movil/src/pieza/PiezaScreen.tsx` y PWA `pages/PiezaDetalle.tsx` (sección «Aprobación» con `ApproveButton` y `VetoButton`); la tarjeta `approval:<id>` de Tu turno y «En cola» ([BAR-13](red.md#bar-13)).
- **Criterios de aceptación:**
  1. **Dado** `OPERATOR_AUTONOMY=…,CONT-09=approval`, **cuando** una pieza pasa el verificador, **entonces** su acción queda en `proposed` y el detalle dice «Pendiente de aprobación».
  2. **Dado** esa pieza, **cuando** se envía `approve` con su `payload_hash` desde una sesión humana con `approve_actions`, **entonces** pasa a `approved` y sale a su hora.
  3. **Dado** esa pieza en la PWA o la app, **cuando** abre el detalle, **entonces** ve la sección «Aprobación» con «Aprobar» junto a «Vetar»; en Tu turno, la tarjeta «¿Apruebas la pieza del <d/m>?» con «Ver la pieza».
  4. **Dado** un `expected_hash` que no coincide con el texto actual, **cuando** aprueba, **entonces** la API lo rechaza.
- **Brechas código/docs:** `publicacion-diaria.md` («Para la primera pieza conviene `CONT-09=approval`: Gustavo la aprueba con su hash») presupone una interfaz que ya no existe. Ver también [BAR-13](red.md#bar-13).
- **Cobertura QA:** E2E `04-tu-turno-aprobar` (criterio 3: «Aprobar» en el detalle de una pieza pendiente, que pasa a «Programada»). Backend `ApprovalTests`.

### CAL-16 · Enlaces antiguos llevan al Calendario o a la pieza <a id="cal-16"></a>

- **Dónde:** PWA · app
- **Estado:** funciona
- **Qué hace para Gustavo:** los enlaces de notificaciones viejas siguen llevando a un sitio que existe.
- **Código:** PWA `App.tsx` (redirecciones); app `push/routes.ts` (`routeForUrl`).
- **Criterios de aceptación:**
  1. **Dado** `/editorial/<id>` o `/contenido/<id>`, **cuando** lo abre, **entonces** llega a `/calendario/pieza/<id>`.
  2. **Dado** `/editorial`, `/contenido` o `/maquina`, **cuando** lo abre, **entonces** llega a `/calendario`.
  3. **Dado** `/acciones?state=uncertain`, **cuando** lo abre, **entonces** llega a `/tu-turno`; cualquier otro `/acciones`, a `/calendario`.
  4. **Dado** una ruta desconocida en la app, **cuando** la abre, **entonces** ve «Esta vista no existe» con «Ir a la Oficina»; en la PWA vuelve a `/`.
- **Brechas código/docs:** `CONTRATO-API.md` sigue describiendo `/acciones`, `/red` y `/maquina` como pantallas vivas.
- **Cobertura QA:** CAL-16.4 en `07-pieza-estados.yaml` (una vista que no existe y «Ir a la Oficina») · CAL-16.1–3 en `push/routes.ts` y sus pruebas · 2026-11-08 · pasa

---

### CAL-17 · Fecha prevista y aviso de una captura urgente <a id="cal-17"></a>

- **Dónde:** backend (campos y avisos; presentación de fase 2 pendiente)
- **Estado:** funciona
- **Código:** `urgente.assign_slots`, `notificaciones.avisar(capture_scheduled)`, eventos de oficina y API de capturas.
- **Criterios de aceptación:**
  1. **Dado** que se asigna una fecha a una idea urgente, **cuando** termina la planificación, **entonces** se guarda `publish_asap_expected_slot`, se envía una notificación con fecha, hora y condiciones y se emite un evento de oficina.
  2. **Dado** una cuenta en pausa o sin hueco, **cuando** se consulta, **entonces** la fecha es null y el motivo explica por qué; no se promete una publicación.
  3. **Dado** el mismo hueco sin cambios, **cuando** vuelve el planificador, **entonces** no duplica avisos.
  4. **Dado** una pieza vetada, fallida o caducada, **cuando** se cierra, **entonces** libera la idea y las fotos para reconsiderarlas; jamás reintenta una publicación incierta.
- **Validación:** pruebas escritas; CI pendiente. Sin ejecución local.
- **Cobertura QA:**

## Imágenes

El detalle de la API devuelve imágenes y revisiones; los tipos y las pantallas se actualizan en fase 2. Lo que Gustavo quiere ver (la foto original y la editada con el motivo, o la infografía o las láminas del carrusel con su texto alternativo, y el veto hasta la hora de salida) está en [IMG-11](imagenes-en-publicaciones.md#img-11) ([imagenes-en-publicaciones.md](imagenes-en-publicaciones.md)).

## Retiradas

Ninguna.
