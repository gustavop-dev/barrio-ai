# Respuestas en los posts propios (`RSP`, capacidad `INT-04`)

Cuando alguien comenta un post de Gustavo, el equipo le responde solo en el hilo, con el contexto del post, de la conversación y del perfil de quien comenta, fundamentado en las unidades del curso. En el segundo turno puede cerrar invitando a conectar y seguir por privado; si la persona encaja, la invita. Nunca envía mensajes directos: deja a Gustavo un primer mensaje redactado para que lo envíe él.

- **Código:** `agentes-linkedin/infra/src/team_backend/respuestas.py` (lectura, reglas del hilo, redacción, ejecución, reglas del primer mensaje `dm_text_issues`, tarjeta «Mensaje sugerido»), `autopiloto._replies`, `operador` (`REPLY_UNITS`, `FIRST_MESSAGE_UNITS`, `execute`, `_run_job` `read_own_comments` y `propose_reply`), `lider.py` (`CHECKS['reply']`, `DM_CHECKS`), `red.py` (invitación sin calentamiento para `own_post`).
- **Vistas:** Tu turno (tarjeta `mensaje`), detalle de una pieza («Conversación en el post»), actividad del calendario y «Hoy el equipo…». App móvil (`movil/src/turno/TurnoCard.tsx`, `movil/src/pieza/PostComments.tsx`) y PWA (`oficina/src/pages/turno/TurnoCardView.tsx`, `oficina/src/pages/calendario/PostComments.tsx`).
- **API:** `GET /api/v1/editorial/pieces/<id>` (`comments`), `GET /api/v1/tu-turno` (`tasks.mensajes`), `POST /api/v1/respuestas/<id>/mensaje` `{how: enviado|no, note?}`.
- **Catálogo:** `INT-04` de [`catalogo-acciones-linkedin.md`](../../agentes-linkedin/infra/docs/catalogo-acciones-linkedin.md): fundamentos B06, B14 y B15; «leer contexto antes de responder; admitir un dato desconocido y conservar preguntas para futuros contenidos».
- **Entorno de prueba:** cuenta `fake` (LinkedIn simulado), Claude y TypeSafe parcheados, como en `tests/test_respuestas.py`.

## Resumen

| ID | Función | Dónde | Estado |
| --- | --- | --- | --- |
| [RSP-01](#rsp-01) | Leer los comentarios de los posts propios | backend | funciona |
| [RSP-02](#rsp-02) | Decidir qué merece respuesta, reacción o nada | backend | funciona |
| [RSP-03](#rsp-03) | Redactar la respuesta fundamentada en la biblioteca | backend | funciona |
| [RSP-04](#rsp-04) | Reglas fijas, agente líder y publicación sin duplicar | backend | funciona |
| [RSP-05](#rsp-05) | Preguntar a Gustavo un dato que el equipo no sabe | backend · Tu turno | funciona |
| [RSP-06](#rsp-06) | Segundo turno: conectar y seguir por privado | backend | funciona |
| [RSP-07](#rsp-07) | «Mensaje sugerido» en Tu turno | app · PWA · backend | funciona |
| [RSP-08](#rsp-08) | La conversación del post en el detalle de la pieza | app · PWA | funciona |

---

### RSP-01 · Leer los comentarios de los posts propios <a id="rsp-01"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** el equipo sabe quién comentó cada post y qué dijo, sin que él tenga que avisar.
- **Código:** `autopiloto._replies` → `respuestas.reading_due` (`plan`, `cadence`, `reading_room`, `to_read`) → trabajo `read_own_comments` → `respuestas.read`. Ventana: `operador.within_read_window`.
- **Criterios de aceptación:**
  1. **Dado** un post publicado hace menos de 72 h, **cuando** corre el autopiloto dentro de `READ_WINDOW` (07:00-21:00), **entonces** se leen sus comentarios: el post más nuevo cada `REPLIES_FRESH_EVERY_MINUTES` (120) durante sus primeras `REPLIES_NEWEST_HOURS` (48); otro post cada 120 mientras sus lecturas traigan comentarios y el doble por cada lectura seguida sin nada nuevo, hasta `REPLIES_IDLE_MAX_MINUTES` (240); un comentario nuevo lo devuelve a 120. De 72 h al día 7, cada `REPLIES_LATE_EVERY_MINUTES` (720).
  2. **Dado** varios posts que tocan a la vez, **entonces** se leen primero el más nuevo, después los que trajeron comentarios en su última lectura y luego el resto, del más reciente al más viejo (`REPLIES_PIECES_PER_RUN`, 4 por vez).
  3. **Dado** un comentario nuevo de una persona, **cuando** se lee, **entonces** queda como `PostComment` y la persona entra en Personas con la fuente «Comentó en tu post».
  4. **Dado** el tope diario de lecturas (`REPLIES_READ_CAPS`, `comments=100`), **entonces** se reparte a lo largo de `READ_WINDOW` (los demás posts no pasan de tope × (tiempo transcurrido + 1 h) / ventana) y siempre deja al post más nuevo sus lecturas hasta el cierre. **Cuando** se agota, la lectura para, queda un solo `replies.read_cap_reached` ese día y el autopiloto no encola más lecturas hasta el día siguiente; el hilo pendiente se relee la próxima vez.
  5. **Dado** que es de noche (fuera de `READ_WINDOW`), **entonces** el autopiloto no encola lecturas ni borradores (un borrador lee el perfil de quien comenta); lo que Gustavo pide desde la app, las respuestas ya aprobadas y su conciliación no esperan. `READ_WINDOW` vacío = a cualquier hora, como antes.
  6. La lectura nunca escribe en `piece.metrics` (es de métricas): el id del post queda en la auditoría `replies.scanned`, con `new` (comentarios nuevos que trajo, lo que usa la cadencia).
- **Un día con 8 posts** (4 de menos de 72 h; simulación de `tests/test_ventana_lectura.py`, reloj simulado): unas 28 lecturas, ninguna fuera de la ventana; el comentario de las 16:00 en el post más nuevo se lee en 30 min. Antes (cada 2 h a toda hora y tope 30) se agotaba a las 12:00 tras 20 lecturas nocturnas.

### RSP-02 · Decidir qué merece respuesta, reacción o nada <a id="rsp-02"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Código:** `respuestas.triage`, `closed_reason`, `congratulation`, `substantive`.
- **Criterios de aceptación:**
  1. Una felicitación corta recibe una reacción (`INT-02` sobre el comentario), no una respuesta.
  2. No se responde: un comentario de más de `REPLIES_WINDOW_HOURS` (72 h desde el comentario), uno que Gustavo ya respondió él mismo, uno ya respondido, uno superado por otro más nuevo de la misma persona, ni un tercer turno.
  3. Como máximo dos respuestas públicas por persona e hilo.

### RSP-03 · Redactar la respuesta fundamentada en la biblioteca <a id="rsp-03"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Código:** `respuestas.propose`, `context`, `operador.REPLY_UNITS`.
- **Criterios de aceptación:**
  1. Cada borrador carga completas las unidades de `REPLY_UNITS` (B06, B14, B15) desde la biblioteca; si falta alguna, no hay borrador («Biblioteca no disponible para fundamentar la respuesta.»).
  2. El contexto incluye la tesis y el texto del post, el hilo, el comentario, el titular y el rol de la persona, sus posts recientes si encaja y lo que Gustavo ya contestó a una pregunta.
  3. Como máximo `MAX_DRAFTS` (3) intentos por comentario; un borrador a la vez.

### RSP-04 · Reglas fijas, agente líder y publicación sin duplicar <a id="rsp-04"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Código:** `respuestas.reply_text_issues`, `content_issues`, `lider.CHECKS['reply']`, `respuestas.execute_action`.
- **Criterios de aceptación:**
  1. Sin venta, enlaces, correos, teléfonos ni hashtags; sin invitar a conectar en el primer turno; sin datos inventados.
  2. El agente líder aprueba o descarta (`responde`, `hilo`, `pitch`, `inventa`, `respeto`, `idioma`).
  3. La respuesta sale en el hilo del comentario raíz; si ya hay una respuesta propia idéntica, no se escribe otra. Se confirma releyendo el hilo.
  4. Topes `INT-04`: 10 al día y 40 a la semana (`OPERATOR_DAILY_LIMITS`, `OPERATOR_WEEKLY_LIMITS`).

### RSP-05 · Preguntar a Gustavo un dato que el equipo no sabe <a id="rsp-05"></a>

- **Dónde:** backend · Tu turno
- **Estado:** funciona
- **Criterios de aceptación:**
  1. **Dado** un comentario que pide un dato que el equipo no conoce, **cuando** se redacta, **entonces** la pregunta llega a Tu turno con plazo hasta que vence la ventana del comentario.
  2. **Dado** que Gustavo responde o declina, **entonces** se redacta otra vez con su respuesta (sin volver a preguntar); si caduca, el comentario se cierra sin respuesta.

### RSP-06 · Segundo turno: conectar y seguir por privado <a id="rsp-06"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Criterios de aceptación:**
  1. En el segundo turno, si la persona encaja o ya es conexión, la respuesta puede cerrar proponiendo conectar y seguir por privado.
  2. Una persona `own_post` que encaja recibe la invitación sin nota (`RED-02`) sin esperar las 48 h tras seguirla.

### RSP-07 · «Mensaje sugerido» en Tu turno <a id="rsp-07"></a>

- **Dónde:** app · PWA · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** cuando alguien con quien el equipo conversó en su post ya es su conexión, Tu turno le deja un primer mensaje redactado para copiar y enviar él desde LinkedIn.
- **Metodología:** la clase 09, primera metodología de outbound activada ([BIB-10](biblioteca-equipos.md#bib-10), caso `BIB-09-primer-mensaje`). Al cerrar el segundo turno, Relaciones carga además `FIRST_MESSAGE_UNITS` y redacta un toque concreto de lo que dijo la persona, el puente honesto (la conversación que quedó abierta, nunca los servicios) y una pregunta fácil.
- **Criterios de aceptación:**
  1. La tarjeta muestra a la persona, su comentario, la respuesta del equipo y el mensaje con «Copiar».
  2. «Hecho, le escribí» y «No escribirle» (nota opcional) la cierran con `POST /api/v1/respuestas/<id>/mensaje`.
  3. La push `dm_ready` sale una sola vez por comentario.
  4. La app nunca envía mensajes en nombre de Gustavo (INB-08).
  5. Reglas fijas (`respuestas.dm_text_issues`): como mucho 3 líneas y 500 caracteres; sin enlaces, correos, teléfonos ni hashtags; sin pedir minutos, una llamada o una reunión; sin las fórmulas que matan un mensaje («quedo atento», «gracias por conectar», «espero que estés bien», «ser parte de mi red», «somos líderes»…); en el idioma de la persona. Una violación va a la única reescritura (la respuesta pública se queda como estaba); si persiste, el mensaje se descarta entero, sin recortarlo, y su texto solo queda en la auditoría (`replies.drafted` `dm_rejected`).
  6. El líder lo juzga en la misma revisión de la respuesta de cierre (toque, puente, pregunta fácil, un tema, en persona y venta). Un fallo deja `dm_approved=False` y no descarta la respuesta pública.
  7. La tarjeta solo aparece con `dm_approved=True` en la revisión de esa respuesta confirmada; sin revisión del líder no hay tarjeta. Una aceptación sin conversación previa no redacta nada.

### RSP-08 · La conversación del post en el detalle de la pieza <a id="rsp-08"></a>

- **Dónde:** app · PWA
- **Estado:** funciona
- **Criterios de aceptación:**
  1. Cada hilo muestra el comentario, su estado (respondido, reacción, pregunta, en camino, sin respuesta) y las respuestas como las muestra LinkedIn.
  2. La respuesta del equipo que LinkedIn aún no muestra aparece bajo el comentario.
  3. Si los comentarios nunca se leyeron, la sección no aparece.
