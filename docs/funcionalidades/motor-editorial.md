# Motor editorial (`EDI`)

El circuito que prepara, verifica y publica la pieza diaria de Gustavo en LinkedIn, sin aprobación humana pieza a pieza. Gustavo supervisa: puede vetar (ver [CAL-12](calendario-piezas.md#cal-12)), pausar la máquina y recibe avisos.

- **Código:** `agentes-linkedin/infra/src/team_backend/editorial.py`, `autopiloto.py` (`_editorial`, `policy_review`, `post_issues`), `operador.py` (`execute`, `_publish`, `reconcile`, `resolve_uncertain`), `connectors_linkedin.py`, `guardas.py`, `voz.py`, `posicionamiento.py`.
- **Documentación:** [`publicacion-diaria.md`](../../agentes-linkedin/infra/docs/publicacion-diaria.md), [`mapa-agentes-runtime.md`](../../agentes-linkedin/infra/docs/mapa-agentes-runtime.md).
- **Entorno de prueba:** cuenta `linkedin_fake` con `OPERATOR_ALLOW_FAKE=true` y Claude parcheado, como en `tests/test_publicacion.py`. En producción la publicación real exige `LIVE_LINKEDIN_OFFICIAL=true` y el OAuth de Gustavo; hoy está en `false`.

## Resumen

| ID | Función | Dónde | Estado |
| --- | --- | --- | --- |
| [EDI-01](#edi-01) | Preparación automática de la pieza del día | backend | funciona |
| [EDI-02](#edi-02) | Preparar la siguiente pieza a mano | PWA · app · backend | funciona |
| [EDI-03](#edi-03) | El director escribe el brief o salta el día | backend | funciona |
| [EDI-04](#edi-04) | Dos variantes y panel de cinco lectores | backend | funciona |
| [EDI-05](#edi-05) | Selección del texto final | backend | funciona |
| [EDI-06](#edi-06) | Reglas deterministas antes del verificador | backend | funciona |
| [EDI-07](#edi-07) | Verificador sobre el texto exacto | backend | funciona |
| [EDI-08](#edi-08) | Una ronda de reparación | backend | funciona |
| [EDI-09](#edi-09) | Pieza bloqueada y su aviso | backend | funciona |
| [EDI-10](#edi-10) | Compuerta autónoma de la publicación | backend | funciona |
| [EDI-11](#edi-11) | Publicar a la hora programada | backend | funciona |
| [EDI-12](#edi-12) | Resultado incierto y conciliación | backend | funciona |
| [EDI-13](#edi-13) | Presupuesto de IA de la publicación diaria | backend | funciona |
| [EDI-14](#edi-14) | Caducidad de una pieza aprobada que no salió | backend | funciona |
| [EDI-15](#edi-15) | Caducidad del permiso de LinkedIn | backend | funciona |
| [EDI-16](#edi-16) | Voz de Gustavo y hechos públicos frente a orientación privada | backend | funciona |
| [EDI-17](#edi-17) | Ideas y comentarios de Gustavo en el brief | backend | funciona |
| [EDI-18](#edi-18) | Preparación interrumpida | backend | funciona |
| [EDI-19](#edi-19) | Modelo configurable por etapa | backend | funciona |
| [EDI-20](#edi-20) | Dar el siguiente hueco libre a una idea urgente | backend | funciona |
| [EDI-21](#edi-21) | Agente visual dedicado al post ganador | PWA · app · backend | parcial |

---

### EDI-01 · Preparación automática de la pieza del día <a id="edi-01"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** cada día, unas horas antes de la hora de publicación, el equipo empieza solo a preparar el post del día siguiente (o de hoy), una sola vez por día.
- **Código:** `autopiloto._editorial`, `editorial.next_slot`, `editorial.can_publish`, `editorial.scheduled_for`; trabajo `prepare_piece` con id determinista por hueco.
- **Criterios de aceptación:**
  1. **Dado** `EDITORIAL_POST_TIME=08:30`, `EDITORIAL_LEAD_HOURS=12`, una cuenta oficial conectada sin pausa, `LIVE_LINKEDIN_OFFICIAL=true` (o la cuenta `linkedin_fake`), CONT-09 distinto de `off`, cupo semanal libre y al menos `EDITORIAL_PREPARE_MIN_USD` de presupuesto de IA disponible, **cuando** el autopiloto corre a las 20:31 hora de `OPERATOR_TIMEZONE` del día anterior, **entonces** encola un trabajo `prepare_piece` para el hueco del día siguiente.
  2. **Dado** que ese día ya tiene una pieza en cualquier estado (incluida `skipped`, `blocked` o `failed` por otro motivo que el dinero), **cuando** el autopiloto vuelve a correr, **entonces** no encola otra preparación para ese día.
  3. **Dado** que no hay cuenta oficial conectada, o está en pausa, o `LIVE_LINKEDIN_OFFICIAL=false` con cuenta real, **cuando** el autopiloto corre, **entonces** no encola nada y no se gasta nada.
  4. **Dado** `OPERATOR_AUTONOMY=…,CONT-09=off`, **cuando** el autopiloto corre, **entonces** no encola nada.
  5. **Dado** que ya hay un `prepare_piece` en cola o corriendo, **cuando** el autopiloto corre, **entonces** no encola un segundo trabajo.
  6. **Dado** que la máquina está en parada total (`OPERATOR_PAUSED=true` o la parada de Ajustes), **cuando** el autopiloto corre, **entonces** no encola ninguna preparación.
  7. **Dado** que la base de datos ya tiene una pieza abierta para el día, **cuando** se intenta crear otra, **entonces** la restricción única la rechaza (una sola pieza abierta por día).
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### EDI-02 · Preparar la siguiente pieza a mano <a id="edi-02"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** desde el Calendario puede pedir que el equipo prepare ya la próxima pieza libre, sabiendo que cuesta dinero.
- **Código:** `POST /api/v1/editorial/plan` (`editorial_views.Plan`, `editorial.plan`). La interfaz se describe en [CAL-14](calendario-piezas.md#cal-14).
- **Criterios de aceptación:**
  1. **Dado** un usuario con `use_paid_providers`, una cuenta oficial conectada y un día sin pieza abierta en los próximos siete, **cuando** envía `POST /api/v1/editorial/plan {}`, **entonces** recibe 202 con `slot_date` (el primer día libre) y `job`.
  2. **Dado** el mismo `request_id` de una petición anterior, **cuando** lo reenvía, **entonces** recibe 200 con el mismo trabajo y no se encola otro.
  3. **Dado** que no hay cuenta oficial, **cuando** lo pide, **entonces** recibe 409 «Conecta LinkedIn (API oficial) antes de planificar piezas.».
  4. **Dado** que la cuenta está en pausa o `LIVE_LINKEDIN_OFFICIAL=false`, **cuando** lo pide, **entonces** recibe 409 «La publicación está en pausa o desactivada (LIVE_LINKEDIN_OFFICIAL); no se prepara una pieza que no saldría.».
  5. **Dado** que los siete días siguientes ya tienen pieza abierta, **cuando** lo pide, **entonces** recibe 409 «No hay un hueco libre en los próximos siete días.».
  6. **Dado** un usuario sin `use_paid_providers`, **cuando** lo pide, **entonces** recibe 403.
  7. **Dado** que Gustavo pulsa «Preparar la siguiente pieza» en la interfaz, **cuando** aparece la confirmación, **entonces** dice «Tiene coste: cada etapa llama a Claude y gasta del presupuesto editorial…» antes de encolar nada; si cancela, no se envía la petición.
- **Brechas código/docs:** la confirmación no muestra una cifra de coste, a diferencia de «Generar ahora» del resumen semanal, y sigue diciendo «presupuesto editorial», que desde el 10/11/2026 es el presupuesto general de IA del equipo ([EDI-13](#edi-13)). La interfaz se describe en [CAL-14](calendario-piezas.md#cal-14).
- **Cobertura QA:** desde la app en `movil/.maestro/07-pieza-veto.yaml` («Preparar la siguiente pieza»: la confirmación con su coste y la preparación en cola, 202) · 2026-11-08 · pasa

### EDI-03 · El director escribe el brief o salta el día <a id="edi-03"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** el director editorial decide de qué va el post (lector, modalidad, pilar, tesis, enfoque) o decide no publicar ese día si no hay material genuino. Puede hacerle hasta dos preguntas.
- **Código:** `editorial._run` (etapa `director`), `DIRECTOR_SYSTEM`, `BRIEF_SCHEMA`, `preguntas.ask`.
- **Criterios de aceptación:**
  1. **Dado** un hueco en preparación, **cuando** corre la etapa del director, **entonces** la pieza guarda `brief` con `decision`, `primary_reader`, `modality` (`personal_startups|projectapp|alianzas|comunidad`), `pillar`, `thesis`, `approach` (uno de los nueve enfoques), `format: "foto|infografia|carrusel"` e `image` con la elección y su motivo, `positioning_version` y `stage: "director"`.
  2. **Dado** que el director responde `decision: "skip"`, **cuando** termina la etapa, **entonces** la pieza queda `skipped` con `skip_reason` como nota, no se paga ninguna etapa más y ese día no se reintenta solo.
  3. **Dado** que el brief trae `questions_for_gustavo` con tres preguntas, **cuando** se guarda, **entonces** se crean como mucho dos `TeamQuestion` del `director_editorial`, con plazo igual a `scheduled_for` de la pieza y origen `piece:<id>`, y cada una dispara la push «Director editorial te pregunta».
  4. **Dado** una clave de memoria ya abierta, rechazada, retirada o conocida, **cuando** el director la vuelve a preguntar, **entonces** no se crea una pregunta duplicada.
  5. **Dado** posts de referentes observados en los últimos 7 días, **cuando** el director los usa, **entonces** `signals` de la pieza guarda solo los que el brief lista en `signals_used`.
  6. **Dado** hechos actuales esenciales ausentes, **cuando** el director pide `research_request`, **entonces** el workflow llama una vez a `research(ResearchRequest)` por pieza, persiste el resultado y lo devuelve al director para cerrar el brief. No envía memoria privada a las herramientas web ni permite una segunda investigación en esa pieza.
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### EDI-04 · Dos variantes y panel de cinco lectores <a id="edi-04"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** dos redactores escriben dos versiones en inglés y cinco lectores simulados (comprador, recomendador, divulgador, líder y par) las comentan.
- **Código:** `editorial._run` (etapas `redactor` y `lectores`), `WRITER_SYSTEM`, `PANEL_SYSTEM`.
- **Criterios de aceptación:**
  1. **Dado** un brief con `decision: "write"`, **cuando** corre la etapa `redactor`, **entonces** la pieza guarda `variants.variant_a` y `variants.variant_b`, cada una con `angle`, `text`, `claims` e `uncertainties`.
  2. **Dado** las dos variantes, **cuando** corre la etapa `lectores`, **entonces** `panel.readers` trae los cinco lectores, cada uno con fortalezas y objeciones por variante, y cada objeción con `severity` `material`, `preference` o `missing_data`.
  3. **Dado** la etapa de lectores, **cuando** se arma su entrada, **entonces** no incluye la memoria de Gustavo ni quién escribió cada variante.
- **Brechas código/docs:** el contrato de diseño prevé redactores independientes y lectores elegidos por brief; el código hace una sola llamada para A y B y pide siempre los cinco lectores (anotado en `mapa-agentes-runtime.md`).
- **Cobertura QA:** pendiente

### EDI-05 · Selección del texto final <a id="edi-05"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** el director elige una versión, las fusiona o descarta la pieza, y fija el texto final.
- **Código:** `editorial._run` (etapa `seleccion`), `SELECTION_SYSTEM`.
- **Criterios de aceptación:**
  1. **Dado** variantes y panel, **cuando** corre la selección, **entonces** `selection.decision` vale `A`, `B`, `merge` o `discard` y `final_text` guarda el texto elegido.
  2. **Dado** `decision: "discard"` o un texto final vacío, **cuando** termina la etapa, **entonces** la pieza queda `skipped` con la nota «Descartada por el director: …» y no se paga el verificador.
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### EDI-06 · Reglas deterministas antes del verificador <a id="edi-06"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** un texto que rompe las reglas fijas (largo, enlaces, contacto, pitch, hashtags, datos privados, experiencias inventadas) se frena antes de pagar al verificador.
- **Código:** `editorial.text_rules`, `editorial._check`, `autopiloto.post_issues`, `guardas.private_leaks`, `guardas.invented_experience`.
- **Criterios de aceptación:**
  1. **Dado** un texto final de 150 caracteres, **cuando** pasan las reglas, **entonces** `verification.rules` incluye «Longitud fuera de 200–2200 caracteres» y el verificador no corre (faltan `model_verdict`, `findings` y `checked_claims`).
  2. **Dado** un texto con un correo, un teléfono o un enlace, **cuando** pasan las reglas, **entonces** `verification.rules` lo nombra («Contiene un correo», «Contiene un número de teléfono», «Contiene enlaces»).
  3. **Dado** un texto con cuatro hashtags, **cuando** pasan las reglas, **entonces** aparece «Más de 3 hashtags».
  4. **Dado** un texto que menciona «60/40» o «Spanish-speaking founders», **cuando** pasan las reglas, **entonces** se marca como filtración privada sin citar el fragmento.
  5. **Dado** que la memoria no tiene hechos públicos, **cuando** el texto dice «I built…» en primera persona, **entonces** se marca como experiencia inventada.
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### EDI-07 · Verificador sobre el texto exacto <a id="edi-07"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** un editor verificador contrasta cada afirmación con los hechos públicos y las fuentes, y su veredicto vale solo para ese texto exacto.
- **Código:** `editorial._check`, `editorial._blocking`, `VERIFIER_SYSTEM`.
- **Criterios de aceptación:**
  1. **Dado** un texto que pasó las reglas, **cuando** corre el verificador, **entonces** `verification` guarda `verdict`, `model_verdict`, `findings`, `checked_claims`, `blocking_reasons` y `text_sha256` igual al SHA-256 del texto final.
  2. **Dado** un hallazgo de gravedad `material` o una afirmación `unsupported`, **cuando** se calcula el veredicto, **entonces** es `blocked` aunque el modelo diga `ready_for_execution`.
  3. **Dado** que el texto cambia después del veredicto, **cuando** la política lo revisa, **entonces** lo descarta con «El veredicto del verificador no corresponde a este texto exacto».
  4. **Dado** una afirmación `web_source`, **cuando** se verifica, **entonces** exige una fuente guardada con URL, fecha y extracto, y una entrada `supported_source` con texto y ref coincidentes. Una ref inventada bloquea aunque el modelo quiera aprobar. El verificador contrasta también hechos actuales que el redactor omitió o etiquetó como conocimiento general.
  5. **Dado** fuentes web con instrucciones maliciosas, **cuando** se usan en texto o infografía, **entonces** llegan como datos no confiables; redactor, selección, reparación y verificadores reciben la regla explícita de ignorarlas.
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### EDI-08 · Una ronda de reparación <a id="edi-08"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** si las reglas o el verificador encuentran problemas concretos, el director corrige el texto una vez con el cambio mínimo, en su voz, y se vuelve a comprobar.
- **Código:** `editorial._repair_round`, `REPAIR_SYSTEM`, `EDITORIAL_REPAIR`.
- **Criterios de aceptación:**
  1. **Dado** un hallazgo `material` concreto y `EDITORIAL_REPAIR=true`, **cuando** termina el verificador, **entonces** corre la etapa `reparacion` y después se repiten una vez las reglas y el verificador; `verification.repair` guarda `trigger`, `findings`, `original_text`, `first_review`, `changes` y `outcome`.
  2. **Dado** que el texto reparado pasa, **cuando** se crea la propuesta CONT-09, **entonces** lleva el riesgo «Reparada en una ronda: N hallazgo(s) de … corregido(s)».
  3. **Dado** que el texto reparado sigue bloqueado, o la reparación lo descarta o no cambia nada, **cuando** termina, **entonces** la pieza queda `blocked` con los motivos y no hay una segunda ronda.
  4. **Dado** un `blocked` del verificador sin hallazgos concretos, **cuando** termina, **entonces** no hay ronda y la pieza queda `blocked`.
  5. **Dado** `EDITORIAL_REPAIR=false`, **cuando** hay hallazgos, **entonces** la pieza queda `blocked` sin ronda.
  6. **Dado** que el presupuesto de IA se agota durante la ronda, **cuando** termina, **entonces** la pieza queda `blocked` con los motivos originales (no `failed`).
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### EDI-09 · Pieza bloqueada y su aviso <a id="edi-09"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** si el texto no pasa la verificación, ese día no se publica y le llega un aviso con el motivo.
- **Código:** `editorial._run` (`avisar('piece_blocked', …)`), `capturas.release_ideas`.
- **Criterios de aceptación:**
  1. **Dado** una pieza con veredicto final `blocked`, **cuando** termina el circuito, **entonces** queda en estado `blocked` con los motivos en `note`, no se crea propuesta CONT-09 y se guarda una Notificación `piece_blocked` con el título «El verificador bloqueó la pieza del DD/MM» (o «Las reglas de publicación bloquearon…» si no corrió el verificador), el primer motivo como detalle y el enlace `/calendario/pieza/<id>`.
  2. **Dado** la push de `piece_blocked` activada (por defecto), **cuando** se bloquea, **entonces** llega una push que abre `/calendario/pieza/<id>`.
  3. **Dado** que la pieza usaba ideas de Gustavo, **cuando** se bloquea, **entonces** esas capturas vuelven a `idea` con «Vuelve a la mesa editorial: la pieza del … no salió (el verificador la bloqueó)».
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### EDI-10 · Compuerta autónoma de la publicación <a id="edi-10"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** una política automática (y el agente líder si está encendido) aprueba la pieza sin que él tenga que hacerlo; si la aprueba, le avisa de que puede vetarla hasta la hora de salida.
- **Código:** `autopiloto.policy_review`, `autopiloto.post_issues`, `lider.review`, `POLICY_VERSION=autonomia-v1`.
- **Criterios de aceptación:**
  1. **Dado** una propuesta CONT-09 en `proposed` con CONT-09 en `auto`, texto válido, veredicto `ready_for_execution` sobre su `text_sha256` y al menos una cita, **cuando** corre el autopiloto, **entonces** pasa a `approved` con la nota «Aprobada por política autonomia-v1» (o «Aprobada por el líder (jev-…) · política autonomia-v1») y se guarda la Notificación `piece_scheduled` «La pieza del DD/MM está lista» con «Sale a las HH:MM. Puedes vetarla en el detalle hasta esa hora.».
  2. **Dado** CONT-09 en `approval`, **cuando** corre el autopiloto, **entonces** la propuesta se queda en `proposed` esperando a Gustavo.
  3. **Dado** una propuesta que incumple una regla, **cuando** corre el autopiloto, **entonces** pasa a `discarded` con «Descartada por política autonomia-v1», las ideas usadas vuelven a la mesa y se guarda la Notificación `piece_discarded` «La política no aprobó la pieza del DD/MM» (sin push por defecto).
  4. **Dado** `LEAD_ENABLED=true` y que Jev responde `clara` < 0,6, **cuando** se revisa, **entonces** se descarta con «Descartada por el líder (…)».
  5. **Dado** que Jev no responde, **cuando** se revisa, **entonces** la propuesta queda en `proposed` y se reintenta tras `LEAD_RETRY_MINUTES`; nunca se aprueba sin juicio.
  6. **Dado** que el `payload_hash` no coincide con el contenido, **cuando** se revisa, **entonces** se descarta con «Hash inconsistente; descartada».
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### EDI-11 · Publicar a la hora programada <a id="edi-11"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** la pieza aprobada sale sola a su hora en su perfil de LinkedIn, una sola vez, y le llega «Publicaste…».
- **Código:** `operador.execute`, `operador._publish`, `operador._find_own_post`, `connectors_linkedin.LinkedInOfficialConnector.create_post`, `post_body`.
- **Criterios de aceptación:**
  1. **Dado** una pieza `approved` con `scheduled_for` a las 08:30, **cuando** el worker intenta ejecutarla a las 08:29, **entonces** no publica (compuerta de la hora programada).
  2. **Dado** la misma pieza a las 08:30, dentro de `OPERATOR_WINDOW`, sin parada ni pausa, respetando el espaciado y los topes (1 al día, 7 a la semana), **cuando** se ejecuta, **entonces** se hace un solo `POST /rest/posts` con `LinkedIn-Version`, `commentary` escapado en formato `little`, `visibility: PUBLIC`, y con un 201 y `x-restli-id` la acción queda `confirmed` con `external_url` `https://www.linkedin.com/feed/update/<urn>/`.
  3. **Dado** que se publicó, **cuando** termina, **entonces** se guarda la Notificación `piece_published` «Publicaste «<tesis>»» con «Las impresiones a las 24 h llegan mañana.» y push.
  4. **Dado** que ya existe en el perfil un post propio con el mismo texto (leído por Unipile), **cuando** se va a ejecutar, **entonces** se confirma sin publicar otro.
  5. **Dado** un 401, 403 o 429, **cuando** se publica, **entonces** la acción queda `failed`, la cuenta pasa a pausa con push «LinkedIn: cuenta en pausa» y no se reintenta.
  6. **Dado** un fallo de conexión antes de enviar, **cuando** se publica, **entonces** queda `failed` con `not_sent`.
  7. **Dado** `LIVE_LINKEDIN_OFFICIAL=false` y una cuenta real, **cuando** se intenta ejecutar, **entonces** no se publica nada («API oficial de LinkedIn desactivada…»).
- **Brechas código/docs:** contrato de archivos añadido; ver [IMG-14](imagenes-en-publicaciones.md#img-14).
- **Cobertura QA:** pendiente

### EDI-12 · Resultado incierto y conciliación <a id="edi-12"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** si LinkedIn no confirma si salió, el equipo nunca lo repite: intenta comprobarlo leyendo su perfil y, si no puede, se lo pregunta en Tu turno.
- **Código:** `operador.execute` (`ConnectorUncertain`), `operador.reconcile`, `operador.resolve_uncertain`, `rediseno_views.alerts` (tarjeta `uncertain:<id>`).
- **Criterios de aceptación:**
  1. **Dado** un 5xx, un timeout tras enviar o un 201 sin URN, **cuando** se publica, **entonces** la acción queda `uncertain`, no se reintenta y llega la push «¿Salió o no?» (prioridad alta).
  2. **Dado** una cuenta Unipile conectada, **cuando** corre la conciliación, **entonces** busca el post propio por texto y, si lo encuentra, la acción pasa a `confirmed`.
  3. **Dado** que no se puede conciliar, **cuando** Gustavo abre Tu turno, **entonces** ve la tarjeta urgente «¿Salió o no?» con «Sí, se aplicó» y «No se aplicó», que piden nota y llaman a `POST /api/v1/operador/actions/<id>/resolve` (ver [TUR-04](tu-turno.md#tur-04)).
  4. **Dado** una acción que no está en `sent` ni `uncertain`, **cuando** se intenta resolver, **entonces** responde 409 «Solo se resuelven acciones enviadas o inciertas.».
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### EDI-13 · Presupuesto de IA de la publicación diaria <a id="edi-13"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** la publicación diaria no tiene tope propio: gasta del presupuesto general de IA del equipo (`AI_MONTHLY_LIMIT_USD`, 100 USD al mes, y el tope de seguridad diario `AI_DAILY_FUSE_USD`, 15 USD; ver `knowledge/presupuesto.py`, desde el 10/11/2026). Una preparación no empieza si no queda para terminarla; si el dinero se acaba a medias, la pieza se detiene y el día se reintenta cuando vuelve a haber presupuesto.
- **Código:** `editorial.budget_left`, `editorial.can_afford_preparation`, `editorial.prepare_min`, `editorial._guard`, `editorial.budget_stopped`, `editorial.budget_retry`, `knowledge/presupuesto.check`, `providers.reserve`, `EDITORIAL_PREPARE_MIN_USD` (3 USD por defecto). El ciclo `pieza_diaria` de `grafo.yaml` tiene además un tope por reservas de 8 USD por ciclo, contra gastos desbocados.
- **Criterios de aceptación:**
  1. **Dado** que queda menos de `EDITORIAL_PREPARE_MIN_USD` (lo menor entre lo que falta del mes y lo que falta hoy bajo el tope de seguridad), **cuando** el autopiloto corre, **entonces** no encola preparación, tampoco la de una idea reservada. Cuenta lo gastado o reservado por todo el equipo: todos los proveedores y áreas, incluidas investigación, búsquedas, visión e imágenes.
  2. **Dado** que el presupuesto se agota entre dos etapas, **cuando** va a empezar la siguiente, **entonces** la pieza se detiene con una nota que empieza por «Presupuesto de IA agotado» o «Ciclo detenido: cost_cap».
  3. **Dado** un hueco cuyas piezas se detuvieron todas solo por dinero (`failed` o `blocked` con «Presupuesto de IA agotado», la nota antigua «Presupuesto editorial diario agotado» o «Ciclo detenido: cost_cap»), **cuando** llega el día local siguiente y hay presupuesto, **entonces** el autopiloto lo vuelve a intentar con un trabajo nuevo.
  4. **Dado** gasto de comentarios, red u otras áreas, **cuando** se calcula lo que queda, **entonces** cuenta: el presupuesto es uno para todo el equipo.
  5. **Dado** dos solicitudes que compiten por el saldo restante, **cuando** reservan, **entonces** el ledger serializa la comprobación antes de generar. Una reserva incierta sigue contando. La investigación de captura y la de pieza consumen el presupuesto general y, si está fijado, el techo opcional del proveedor (`<PROVEEDOR>_LIMIT_USD`).
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### EDI-14 · Caducidad de una pieza aprobada que no salió <a id="edi-14"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** una pieza aprobada que no llega a salir no se publica días después: caduca.
- **Código:** `autopiloto.tick` (propuestas con `piece` y `piece__scheduled_for` < ahora − `OPERATOR_PROPOSAL_TTL_HOURS`).
- **Criterios de aceptación:**
  1. **Dado** `OPERATOR_PROPOSAL_TTL_HOURS=48` y una pieza `approved` programada hace 49 h sin ejecución, **cuando** corre el autopiloto, **entonces** la acción pasa a `expired` con «Caducada sin ejecutar» y el calendario la muestra como `expired`.
  2. **Dado** una pieza creada hace 3 días pero programada para dentro de 1 hora, **cuando** corre el autopiloto, **entonces** no caduca (el TTL cuenta desde la hora programada).
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### EDI-15 · Caducidad del permiso de LinkedIn <a id="edi-15"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** siete días antes de que caduque el permiso de publicar le avisa una vez; al caducar, la publicación se pausa hasta que reconecte.
- **Código:** `connectors_linkedin.check_tokens` (corre en cada tick, también con la máquina parada), `operador.set_account_pause`.
- **Criterios de aceptación:**
  1. **Dado** un token que caduca en 6 días y sin aviso previo, **cuando** corre el autopiloto, **entonces** llega una sola push «LinkedIn caduca pronto» y `expiry_alerted_at` queda fijado; el tick siguiente no la repite.
  2. **Dado** un token caducado y la cuenta sin pausa, **cuando** corre el autopiloto, **entonces** la cuenta pasa a pausa con un motivo que empieza por el texto de token caducado y llega la push «LinkedIn: cuenta en pausa».
  3. **Dado** la cuenta pausada por token caducado, **cuando** Gustavo reconecta LinkedIn ([AJU-07](ajustes.md#aju-07)), **entonces** se guarda el token nuevo y se levanta esa pausa.
- **Brechas código/docs:** el tipo de push `linkedin_expired` existe en Ajustes, pero nada lo emite: al caducar llega `account_paused` (ver [PUS-05](notificaciones-push.md#pus-05)).
- **Cobertura QA:** pendiente

### EDI-16 · Voz de Gustavo y hechos públicos frente a orientación privada <a id="edi-16"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** los posts suenan a él (su documento de tono) y solo le atribuyen lo que él confirmó como público; sus prioridades privadas nunca aparecen.
- **Código:** `voz.with_voice`, `voz.VOICE_GUIDE`, `recursos/tono-de-voz.md`, `knowledge.memory.confirmed_blocks`, `guardas.blocks`.
- **Criterios de aceptación:**
  1. **Dado** las etapas `redactor`, `seleccion` y `reparacion`, **cuando** se arma su system, **entonces** termina con la guía de voz y el documento de tono; el director, los lectores y el verificador no lo reciben.
  2. **Dado** un hecho confirmado `{texto, uso_publico: true}`, **cuando** se arma la memoria, **entonces** va en `public_facts`; cualquier otro valor va en `private_guidance`.
  3. **Dado** el panel de lectores, **cuando** se arma su entrada, **entonces** no recibe ni `public_facts` ni `private_guidance`.
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### EDI-17 · Ideas y comentarios de Gustavo en el brief <a id="edi-17"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** lo que manda con el botón de captura como «Idea para un post» y sus comentarios sobre piezas llegan al director, que da prioridad a las ideas cuando encajan.
- **Código:** `capturas.ideas_for_director`, `capturas.feedback_for_director`, `capturas.mark_used`, `capturas.release_ideas`, `capturas.expire_ideas`.
- **Criterios de aceptación:**
  1. **Dado** seis capturas en estado `idea` de los últimos 14 días, **cuando** corre el director, **entonces** recibe hasta 5 en `ideas_from_gustavo`, priorizando urgencias reservadas para el hueco; con texto (hasta 6.000 caracteres), fotos, fecha y evidencia.
  2. **Dado** que el brief devuelve `ideas_used` con el id de una idea ofrecida, **cuando** se guarda, **entonces** esa captura pasa a `usado` con «El Director editorial lo usó en el brief del <día>» y enlace a la pieza. Un id que no se le ofreció se ignora.
  3. **Dado** que esa pieza termina `skipped`, `blocked`, `failed`, descartada o vetada, **cuando** se cierra, **entonces** la idea vuelve a `idea` con «Vuelve a la mesa editorial: la pieza del … no salió (…)».
  4. **Dado** una idea con más de 14 días sin usar, **cuando** se listan las capturas o corre el director, **entonces** pasa a `sin_usar` con «Pasaron 14 días sin que encajara en un brief».
  5. **Dado** comentarios de pieza (capturas con contexto `pieza`) de los últimos 30 días, **cuando** corre el director, **entonces** recibe hasta 10 en `feedback_from_gustavo` con la fecha y la tesis de la pieza.
  6. **Dado** investigación de una captura, **cuando** se prepara una pieza, **entonces** `research` conserva los resultados ofrecidos al director y `untrusted_web_evidence` los entrega a redacción, selección, reparación y verificador. El detalle de pieza expone esos resultados con sus fuentes; las citas de curso siguen separadas.
- **Brechas código/docs:** el director recibe fotos, notas y prioridad; ver [IMG-06](imagenes-en-publicaciones.md#img-06).
- **Cobertura QA:** pendiente

### EDI-18 · Preparación interrumpida <a id="edi-18"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** si la preparación muere a medias, la pieza se ve como fallida y no se vuelve a pagar sola.
- **Código:** `editorial.recover_stuck`, `editorial.prepare` (excepciones).
- **Criterios de aceptación:**
  1. **Dado** una pieza en `preparing` cuyo trabajo ya no está en cola ni corriendo, **cuando** corre el autopiloto, **entonces** pasa a `failed` con «Preparación interrumpida; no se repite el gasto. Planifica otra si procede.».
  2. **Dado** un error interno durante una etapa, **cuando** se captura, **entonces** la pieza queda `failed` con «Error interno en la preparación; no se repite el gasto.».
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### EDI-19 · Modelo configurable por etapa <a id="edi-19"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** se puede abaratar una etapa concreta cambiando su modelo, sin tocar las demás.
- **Código:** `editorial.stage_model`, `editorial.check_models`, `providers.MODEL_PRICES`.
- **Criterios de aceptación:**
  1. **Dado** `EDITORIAL_MODEL_LECTORES=claude-sonnet-5-5`, **cuando** corre la pieza, **entonces** solo la etapa de lectores usa ese modelo y `usage` lo registra.
  2. **Dado** un modelo sin tarifa en `MODEL_PRICES`, **cuando** empieza la pieza, **entonces** falla antes de pagar ninguna etapa.
  3. **Dado** que no hay `EDITORIAL_MODEL_REPARACION`, **cuando** corre la reparación, **entonces** usa el modelo de la selección.
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

---

### EDI-20 · Dar el siguiente hueco libre a una idea urgente <a id="edi-20"></a>

- **Dónde:** backend (campos y avisos; presentación de fase 2 pendiente)
- **Estado:** funciona
- **Código:** `urgente.py`, `editorial.plan`, `_run`, `autopiloto._editorial`.
- **Criterios de aceptación:**
  1. **Dado** una idea urgente, **cuando** se planifica, **entonces** obtiene el primer hueco de publicación libre compatible con cadencia, topes y un mínimo de 60 minutos de veto.
  2. **Dado** una pieza ya preparada o un trabajo en cola en ese hueco, **cuando** llega la urgencia, **entonces** conserva la pieza y registra por qué la idea va al siguiente hueco; no se pierde trabajo pagado ni una decisión anterior.
  3. **Dado** varias urgencias, **cuando** se asignan, **entonces** se atienden por orden de llegada, una por hueco.
  4. **Dado** el hueco de una urgencia, **cuando** decide el director, **entonces** usa esa idea o salta el día con motivo; nunca publica otra idea pasando por encima de la prioridad.
  5. **Dado** pausa, modo off/aprobación, falta de presupuesto o bloqueo de calidad, **cuando** corre el circuito, **entonces** se conservan todas las compuertas, y la urgencia no autoriza publicar.
  6. **Dado** una preparación que consume el plazo de veto, **cuando** termina, **entonces** mueve la pieza a otro hueco y avisa; no publica inmediatamente.
  7. **Dado** que la pieza del hueco reservado de una idea termina `blocked` o `failed` por algo que no es dinero, **cuando** se reasignan los huecos, **entonces** cuenta un intento (una vez por pieza); con 2 intentos la idea pierde su fecha y sigue en la mesa del director con «Se intentó preparar dos veces y no salió; sigue en la mesa del director para un día normal.».
  8. **Dado** un día cuyas únicas piezas eran para una idea reservada y no salieron (`skipped`, `blocked` o `failed`), **cuando** el autopiloto busca hueco, **entonces** ese día queda libre para su publicación propia.
  9. **Dado** un día cuya pieza se detuvo solo por dinero ([EDI-13](#edi-13)), **cuando** se busca hueco para una idea, **entonces** ese día cuenta como libre; la preparación espera a que queden `EDITORIAL_PREPARE_MIN_USD`.
- **Validación:** pruebas escritas; CI pendiente. Sin ejecución local.
- **Cobertura QA:**

## Imágenes

El flujo de imagen está implementado en el backend; la interfaz queda para fase 2. Está descrito en [imagenes-en-publicaciones.md](imagenes-en-publicaciones.md). Las fichas que tocan este circuito:
- [IMG-15](imagenes-en-publicaciones.md#img-15): el equipo de redacción elige por contexto una foto de la Galería, una infografía o un carrusel, y nunca publica sin imagen ([IMG-05](imagenes-en-publicaciones.md#img-05));
- [IMG-04](imagenes-en-publicaciones.md#img-04) e [IMG-06](imagenes-en-publicaciones.md#img-06): el director ve la Galería y las propuestas de post de Gustavo;
- [IMG-07](imagenes-en-publicaciones.md#img-07) a [IMG-10](imagenes-en-publicaciones.md#img-10): decidir, editar con OpenAI y comprobar las fotos;
- [IMG-INF-01](imagenes-en-publicaciones.md#img-inf-01) a [IMG-INF-08](imagenes-en-publicaciones.md#img-inf-08): las infografías y los carruseles, con el manual de Gustavo como regla de agente (como la voz, [EDI-16](#edi-16)) y la lista de 10 puntos en el verificador;
- [IMG-14](imagenes-en-publicaciones.md#img-14): publicar con imagen o carrusel.

### EDI-21 · Agente visual dedicado al post ganador <a id="edi-21"></a>

- **Dónde:** PWA · app · backend
- **Estado:** parcial: pieza diaria implementada; CI/QA por Claude pendientes. Perfil/GAL-08 pertenecen a fase 8.
- **Qué hace para Gustavo:** un integrante de Editorial se encarga de elegir y preparar la foto, infografía o carrusel de la pieza ganadora, con decisiones visibles y un responsable propio.
- **Responsable:** nuevo rol especialista `editor_visual` («Editor visual»), dentro de Editorial; `director_editorial` es orquestador y conserva la decisión del ciclo, incluido el medio final. Revisión conserva sus guardas y Operación ejecuta la publicación.
- **Cadencia:** una preparación por versión ganadora del post, después de seleccionar el texto; si se repara el texto, revisar compatibilidad del visual antes de publicar. También presta preparación visual a EST-03/04 cuando Perfil la solicita.
- **Tu turno:** los posts conservan autonomía y veto de [IMG-11](imagenes-en-publicaciones.md#img-11); no se añade aprobación por cada imagen. Solo preguntas sobre datos/recursos faltantes que requieran a Gustavo. Foto y mural de perfil sí pasan por la checklist TUR-18.
- **Datos necesarios y disponibilidad:** texto final (después de reparación), brief, fuentes, Galería ofrecida/disponible y opciones IMG. El selector devuelve la propuesta al director antes de preparar medios. Se conserva la revisión por bytes, original/tarjeta de fallback y bloqueo IMG-05.
- **Código:** `editor_visual.py` contiene las herramientas y contratos; `editorial._visual` coordina llamadas secuenciales sin delegación anidada. `imagenes`, `infografias` y `connectors_images` conservan producción y revisión. Definición: `agentes-linkedin/equipos/editorial/editor_visual.json`; configuración efectiva: `equipos/grafo.yaml`. `selection.visual` guarda propuesta, decisión del director y manifest realmente entregado; `image_review.visual_binding` liga texto, fuentes y permisos usados. La elección usa `editorial-visual`; producción conserva `image-*`, ambos dentro del cap agregado existente.
- **Contrato de definición requerido:** id y nombre estables, grupo Editorial, misión, entradas (versión/hash del post, brief, evidencia, fotos y opciones), entregable (propuesta de formato, motivos, ids de originales/variantes, instrucciones de edición, plantilla/datos, texto alternativo y verificaciones), unidades/reglas visuales, límites de gasto, permisos, errores y binding al runtime. Configuración efectiva y aristas viven en [ARQ-01](arquitectura-agentes.md#arq-01); el JSON de rol es detalle enlazado, no otra fuente de configuración. El visual devuelve su propuesta al director; no llama lectores, verificador ni otros agentes por sí mismo.
- **Criterios de aceptación:**
  1. **Dado** un post ganador, **cuando** trabaja el agente visual, **entonces** recibe su versión exacta y propone foto, infografía o carrusel según [IMG-15](imagenes-en-publicaciones.md#img-15), dejando motivo y vínculo al texto; devuelve el resultado al director, quien acepta el medio, pide revisión dentro de sus límites o bloquea antes de encargar su preparación definitiva.
  2. **Dado** una decisión de usar fotografía para el post, **cuando** selecciona y edita, **entonces** consulta fotos/notas según IMG-04 **excluyendo Perfil y sus derivados** por GAL-08; backend filtra antes del contexto del director/visual y rechaza selección por id, incluida selección manual. Aplica IMG-07/08/16 a las elegibles: «No editar» impide llamar al modelo aunque la nota pida retoques. Conserva original y trazabilidad IMG-09/10.
  3. **Dado** infografía o carrusel, **cuando** prepara el entregable, **entonces** entrega plantilla y contenido estructurado al renderizador de IMG-INF, con fuentes y texto alternativo; ningún modelo de imagen dibuja las letras o el gráfico completo.
  4. **Dado** un texto reparado o fuente/permiso cambiado, **cuando** se va a publicar, **entonces** vuelve a comprobar compatibilidad y vigencia del paquete visual; no usa una imagen cuya verificación corresponde a otro contenido. Si no hay una imagen válida, se aplica el bloqueo ya definido por IMG-05.
  5. **Dado** un trabajo de imagen, **cuando** se consulta su actividad, **entonces** aparece como `editor_visual` dentro de Editorial según [OFI-10](oficina.md#ofi-10), con su definición, estado y entrega. No se atribuye a los copywriters ni se presenta activo por existir solamente el JSON.
  6. **Dado** Galería vacía, render fallido o presupuesto agotado, **cuando** el rol no puede completar el medio, **entonces** registra el motivo y usa las alternativas/bloqueos del flujo IMG, sin un segundo pipeline ni publicar una pieza sin imagen.
  7. **Dado** un encargo del orquestador Perfil, **cuando** propone foto/banner, **entonces** usa exclusivamente esa categoría y las notas como instrucciones por función de [GAL-08](galeria.md#gal-08); entrega A/B, banner con micrófono, previews, citas y visión contra 03 según [EST-03/04](estrategia-perfil.md#est-03). Devuelve el resultado a Perfil sin elegir por Gustavo. Ni esos originales ni derivados/notas entran al contexto o selección de posts; ninguna alternativa editorial sustituye una referencia faltante.
- **Brechas código/docs:** fase 7 implementa el circuito de posts. Los criterios de Perfil y su separación GAL-08 dependen de fase 8 y no se activan aquí. No se cargaron referencias privadas. La producción reutiliza IMG/IMG-INF; Revisión y Operación conservan su reparto.
- **Cobertura QA:** escritos `test_editor_visual.py`, regresiones de IMG, grafo, publicación y Oficina; Jest/Vitest compartidos y flujos Maestro 03/17. Sin suites locales. Claude ejecuta CI y sesión QA en vivo con **`[qa: 03 07 11 16-imagenes 17-mapa-equipo]`**, incluyendo imágenes/veto del detalle de pieza.

## Retiradas

Ninguna.
