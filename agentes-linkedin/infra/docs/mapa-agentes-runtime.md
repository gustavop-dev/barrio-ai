# Mapa de agentes: diseño y runtime

Qué corre de verdad por cada rol, comprobado en el código el 7 de noviembre de 2026, ya con las fases 2 y 3 de la auditoría (problema 1 de la [auditoría de IA](auditoria-arquitectura-ia.md), «Diseño y realidad divergen»).

Los 16 contratos de `agentes-linkedin/equipos/` son plantillas de diseño de 30–80 KB marcadas como no ejecutables. El runtime no los lee: usa prompts cortos escritos en Python. [`indice-agentes-v1.json`](../../arquitectura/indice-agentes-v1.json) lleva el estado real de cada rol y enlaza el código que lo implementa, y cada contrato tiene una línea `runtime` que apunta aquí.

**Cómo leerlo:**

- Las rutas de código son relativas a `agentes-linkedin/infra/src/`.
- Se nombran funciones y constantes, no números de línea, porque el código cambia a menudo.
- «Modelo» es el valor por defecto del código; la variable de entorno que lo cambia va entre paréntesis. En el circuito editorial, `EDITORIAL_MODEL_<ETAPA>` cambia el modelo de una etapa (C3).
- Opus 5.5 y Sonnet 5.5 siempre piensan, y el pensamiento cuenta contra `max_tokens`.

**Estados:**

- **Activo:** corre en el bucle autónomo.
- **Parcial:** corre solo una parte del rol, o corre a mano y su salida no llega al bucle.
- **No implementado:** no hay código.

## Resumen

| Rol | Estado | Código | Modelo · effort |
| --- | --- | --- | --- |
| posicionamiento | Parcial (a mano) | `knowledge/agents.py: run` | Opus 5.5 · sin fijar |
| perfil | Parcial (a mano) | `knowledge/agents.py: run` | Opus 5.5 · sin fijar |
| investigador_referentes | Parcial | `red.py: CLASSIFY_SYSTEM / classify`, `discover`, `operador.py: observe` | Sonnet 5.5 · medium |
| analista_barrio_resultados | Parcial | `metricas.py: collect`, `resultados.py`, `resumen_semanal.py: run` | Opus 5.5 · medium (resumen semanal) |
| director_editorial | Activo | `editorial.py: DIRECTOR_SYSTEM / _stage('director')`, `SELECTION_SYSTEM / _stage('seleccion')`, `REPAIR_SYSTEM / _stage('reparacion')` | Opus 5.5 · medium |
| copywriter_a y copywriter_b | Activo, en una llamada | `editorial.py: WRITER_SYSTEM / _stage('redactor')` | Opus 5.5 · medium |
| Cinco lectores | Activo, en una llamada | `editorial.py: PANEL_SYSTEM / _stage('lectores')` | Opus 5.5 · low |
| editor_verificador | Activo | `editorial.py: text_rules`, `VERIFIER_SYSTEM / _stage('verificador')`, `_check`, `_repair_round` | Opus 5.5 · high |
| relaciones_comunidad | Activo | `operador.py: COMMENT_SYSTEM / propose_comment`, `_draft_comment`, `red.py: plan`, `sync` | Opus 5.5 · medium |
| conversaciones_inbox | Parcial (solo lectura), si `INBOX_ENABLED` | `conversaciones.py: read_inbox`, `assess` | Jev 1.14 |
| operador_cuenta | Activo, determinista | `operador.py: execute`, `red.py: execute_action` | Ninguno |
| Agente líder (sin contrato) | Activo si `LEAD_ENABLED` | `lider.py: review`, `comment_worthy`, `autopiloto.py: policy_review` | Jev 1.14 |
| Ruteador de capturas (sin contrato) | Activo | `capturas.py: ROUTE_SYSTEM / classify` | Sonnet 5.5 · low |

## Roles

### posicionamiento y perfil

| | |
| --- | --- |
| Contrato | `equipos/estrategia-perfil/contratos-v1/posicionamiento.json` y `perfil.json` |
| Código | `knowledge/agents.py: run`, lanzado como trabajo `agent_run` con `POST /api/v1/runs` |
| Prompt | `knowledge/agents.py: SYSTEM`, la misión de `knowledge/retrieval.py: AGENTS` y la política de uso del curso |
| Modelo · effort | `ANTHROPIC_MODEL` (Opus 5.5) · sin fijar; `max_tokens` = `ANTHROPIC_MAX_TOKENS` (8.000); ledger `agent-run` |
| Entradas | La tarea escrita a mano, unidades del curso halladas por búsqueda léxica o híbrida y la memoria confirmada |
| Salidas | Una fila en `runs` con estado `needs_review` o `validation_failed` |
| Compuertas | Ninguna en el bucle: nada consume la salida |
| Frente al contrato | No hay `positioning_proposal`, `neighborhood_criteria` ni cambios de perfil (PERF-*). La dirección que usan los demás está escrita a mano en `posicionamiento.py` (`posicionamiento-v1`, con la tabla de vocabularios de modalidad), y de ahí salen `editorial.DIRECTION`, `red.CLASSIFY_SYSTEM` y `lider.CRITERIA_DEL_BARRIO`. El agente no la propone ni la actualiza. |

### investigador_referentes

| | |
| --- | --- |
| Contrato | `equipos/observatorio/investigador_referentes.json` |
| Código | `red.py: classify` (DESC-07). Deterministas: `red.py: discover` (DESC-05, DESC-02), `_enrich` (DESC-03) y `operador.py: observe` (DESC-04) |
| Prompt | `red.py: CLASSIFY_SYSTEM`, con `CLASSIFY_SCHEMA` |
| Modelo · effort | `NETWORK_CLASSIFIER_MODEL` (Sonnet 5.5) · medium; `max_tokens` 16.000; ledger `network-classify` |
| Entradas | Lotes de hasta 10 personas: nombre, titular, ubicación, grado, origen y evidencia (comentario, búsqueda o mensaje de invitación). Además, la orientación privada (`guardas.blocks`) y la orientación de Gustavo |
| Salidas | `Contact.classification` (encaja, papel, modalidad, afinidad, motivo y confianza). Encaja si el modelo dice que sí y la confianza llega a `NETWORK_MIN_CONFIDENCE` (0,6); si no, la persona pasa a `discarded` |
| Compuertas | `NETWORK_DAILY_LLM_USD` y los topes de lectura de perfil. Después, `red.network_issues`, que exige su `fit`, y el líder, que solo mira el riesgo |
| Frente al contrato | Solo clasifica personas descubiertas: los referentes los añade Gustavo (`operador.add_referent`). No hay `search_plan`, `research_packet`, `signal_card` ni INT-07. Desde R2 es el único juez del encaje; sus criterios salen de `posicionamiento.network_criteria`. |

### analista_barrio_resultados

| | |
| --- | --- |
| Contrato | `equipos/observatorio/analista_barrio_resultados.json` |
| Código | `metricas.py: collect` (APRE-01) y `resultados.py` (indicadores de la oficina), deterministas; `resumen_semanal.py: stats` (determinista), `run` y `validate` (resumen semanal, trabajo `weekly_summary`) |
| Prompt · modelo | Métricas: ninguno. Resumen semanal: `resumen_semanal.SYSTEM` con `SCHEMA`; `ANTHROPIC_MODEL` (Opus 5.5) · medium; `max_tokens` 12.000; ledger `weekly-summary` |
| Entradas | Métricas: lecturas por Unipile de las publicaciones propias a 24 h, 72 h y 7 días, de quién comentó y de la audiencia diaria. Resumen: las cifras de la semana y de la anterior (publicaciones y cortes, comentarios y su destino, red, oportunidades, inbox, capturas, gasto, decisiones del líder, paradas), el posicionamiento, la orientación vigente y los comentarios de Gustavo sobre las piezas de la semana |
| Salidas | `PostMetric`, `AudienceSnapshot` y `EditorialPiece.metrics`; los indicadores de `/resultados`; un `WeeklySummary` por semana (titular, lo que funcionó, lo que no, recomendaciones, orientación propuesta y advertencias), la Notificación `weekly_summary`, la tarjeta de Tu turno si propone orientación y `weekly_recommendations` en el brief del director |
| Compuertas | Topes diarios de lectura y `METRICS_EVERY_MINUTES`. El resumen: los lunes tras `WEEKLY_SUMMARY_TIME`, uno por semana (`week_start` único, id de trabajo determinista), solo si `WEEKLY_SUMMARY_ENABLED` y la máquina funcionó esa semana, dentro de `WEEKLY_SUMMARY_LLM_USD` por semana. Un validador quita las frases con cifras que no están en los datos |
| Frente al contrato | El resumen semanal ([resumen-semanal.md](resumen-semanal.md)) es un `learning_proposal` simplificado. La orientación que propone solo la adopta Gustavo, y el director recibe sus recomendaciones como pista, no como orientación. No hay experimentos ni `participation_signal`, y el resumen de 30 días del director sigue en `editorial.py` (`_performance` y `_history`). |

### director_editorial

| | |
| --- | --- |
| Contrato | `equipos/editorial/director_editorial.json` |
| Código | `editorial.py: _stage('director')`, `_stage('seleccion')` y, en `_repair_round`, `_stage('reparacion')`, dentro de `prepare` / `_run` (trabajo `prepare_piece`) |
| Prompt | `DIRECTOR_SYSTEM` con `BRIEF_SCHEMA`; `SELECTION_SYSTEM` con `SELECTION_SCHEMA`; `REPAIR_SYSTEM` con `REPAIR_SCHEMA`. Selección y reparación llevan la voz de Gustavo (`voz.with_voice`); las tres incluyen `DIRECTION` |
| Modelo · effort | `ANTHROPIC_MODEL` (Opus 5.5) o `EDITORIAL_MODEL_<ETAPA>` · medium en las tres (la reparación sigue el modelo de la selección); `max_tokens` 16.000; ledger `editorial-director`, `editorial-seleccion` y `editorial-reparacion` |
| Entradas del brief | Hechos públicos, orientación privada y orientación de Gustavo; el día; hasta 12 publicaciones de referentes de los últimos 7 días; las 20 últimas piezas listas, con los resultados de las publicadas; el resumen de resultados de 30 días por pilar y modalidad (`performance_30d`); la mezcla de modalidades de 30 días; las preguntas abiertas y cerradas; las ideas y los comentarios de Gustavo de la captura; las recomendaciones del último resumen semanal (`weekly_recommendations`, una pista, no orientación); unidades del curso de pilares, cadencia, los 9 enfoques y formato |
| Entradas de la selección | El brief congelado, las dos variantes, el panel de lectores y las fuentes |
| Entradas de la reparación | El brief congelado, el texto, sus afirmaciones, los hallazgos concretos (de las reglas o del verificador) y las fuentes |
| Salidas | Brief o «skip»; hasta 2 preguntas a Gustavo (`preguntas.ask`); las ideas usadas (`capturas.mark_used`). La selección devuelve A, B, fusión o descarte, el texto final y sus afirmaciones. La reparación devuelve el texto corregido y un cambio por hallazgo, o un descarte |
| Compuertas | `EDITORIAL_DAILY_LLM_USD` antes de cada etapa. Un «skip» o un descarte cierran la pieza como `skipped`. El autopiloto prepara la pieza `EDITORIAL_LEAD_HOURS` antes de `EDITORIAL_POST_TIME`, un intento por día, si queda cupo de CONT-09 |
| Frente al contrato | Sin ACK ni eventos. Hace una sola ronda de reparación (el contrato prevé hasta 2 correctivas), que `EDITORIAL_REPAIR=false` apaga. Pide siempre los cinco lectores, aunque el contrato los elige en el brief. Solo `text_only` y sin calendario ni experimentos. |

### copywriter_a y copywriter_b

| | |
| --- | --- |
| Contrato | `equipos/editorial/copywriter_a.json` y `copywriter_b.json` |
| Código | `editorial.py: _stage('redactor')`: una sola llamada devuelve `variant_a` y `variant_b` |
| Prompt | `WRITER_SYSTEM` con `WRITER_SCHEMA`, `DIRECTION` y la voz de Gustavo |
| Modelo · effort | `ANTHROPIC_MODEL` (Opus 5.5) o `EDITORIAL_MODEL_REDACTOR` · medium; `max_tokens` 16.000; ledger `editorial-redactor` |
| Entradas | Hechos públicos, orientación privada, orientación, el brief congelado, las fuentes y unidades del curso (primero el enfoque elegido, luego formato, edición y la guía de la sesión 6) |
| Salidas | Dos variantes en inglés, cada una con ángulo, texto, afirmaciones e incertidumbres |
| Compuertas | Las del circuito: presupuesto diario y las etapas siguientes |
| Frente al contrato | B se escribe viendo A en la misma llamada, así que no son borradores independientes. Sin rondas de revisión, `asset_brief` ni `research_request`. |

### Cinco lectores (comprador, recomendador, divulgador, líder, par)

| | |
| --- | --- |
| Contrato | `equipos/lectores/lector_*.json` |
| Código | `editorial.py: _stage('lectores')`: una llamada para los cinco |
| Prompt | `PANEL_SYSTEM` con `PANEL_SCHEMA` |
| Modelo · effort | `ANTHROPIC_MODEL` (Opus 5.5) o `EDITORIAL_MODEL_LECTORES` · low; `max_tokens` 12.000; ledger `editorial-lectores` |
| Entradas | El lector principal, la modalidad y la tesis del brief, el texto de A y B y dos unidades del curso. No recibe memoria ni autoría |
| Salidas | Fortalezas y objeciones por lector y variante, cada objeción como `material`, `preference` o `missing_data`, y un resumen |
| Compuertas | Ninguna propia: la selección decide |
| Frente al contrato | Siempre los cinco y en una sola llamada. Es el rol con menor valor por costo según la auditoría; `manage.py evaluar --agentes lectores` mide si cambia la selección ([evaluaciones](evaluaciones-agentes.md)). |

### editor_verificador

| | |
| --- | --- |
| Contrato | `equipos/revision/editor_verificador.json` |
| Código | `editorial.py: _check`: primero `text_rules` (las reglas deterministas de la política y las guardas), y solo si pasan `_stage('verificador')` y `_blocking`. Luego `_repair_round`, y en la política `autopiloto.py: post_issues` |
| Prompt | `VERIFIER_SYSTEM` con `VERIFIER_SCHEMA` |
| Modelo · effort | `ANTHROPIC_MODEL` (Opus 5.5) o `EDITORIAL_MODEL_VERIFICADOR` · high; `max_tokens` 16.000; ledger `editorial-verificador` |
| Entradas | Hechos públicos, orientación privada y orientación, el texto final exacto, el brief congelado, las afirmaciones de la selección y las fuentes |
| Salidas | Veredicto, hallazgos con su gravedad, afirmaciones comprobadas, las reglas que saltaron, la reparación si la hubo y el hash del texto (`EditorialPiece.verification`, con `rules` y `repair`) |
| Compuertas | Las reglas paran el texto antes de pagar al verificador. El verificador bloquea con `blocked`, un hallazgo `material` o una afirmación sin respaldo. Los hallazgos concretos de cualquiera de los dos reciben una ronda de reparación, y el texto reparado vuelve a pasar reglas y verificador; si sigue con problemas, la pieza queda bloqueada y avisa (`piece_blocked`). Si pasa, crea la propuesta CONT-09, y `post_issues` vuelve a aplicar las reglas y exige el veredicto sobre ese texto exacto |
| Frente al contrato | Solo revisa la pieza propia. Comentarios, notas de invitación, mensajes y perfil, que el contrato también cubre, pasan por reglas deterministas y por el líder. No hay `evidence_request`: la reparación la hace el director. |

### relaciones_comunidad

| | |
| --- | --- |
| Contrato | `equipos/relaciones/relaciones_comunidad.json` |
| Código | `operador.py: propose_comment` y `_draft_comment` (INT-03, trabajo `propose_comment`). Deterministas: `red.py: plan` (RED-01, RED-02 y RED-04) y `red.py: sync` (RED-03) |
| Prompt | `operador.py: COMMENT_SYSTEM` con `COMMENT_SCHEMA` y la voz de Gustavo; las unidades del curso van detrás, en un bloque de sistema cacheado (`course_block`, C1) |
| Modelo · effort | `ANTHROPIC_MODEL` (Opus 5.5) · medium; `max_tokens` = `ANTHROPIC_MAX_TOKENS` (8.000); ledger `propose-comment` |
| Entradas | La publicación (autor, texto y URL), hasta 10 comentarios existentes leídos por Unipile, los hechos públicos y la orientación privada de la memoria confirmada (sin la orientación base del brief), la orientación y seis unidades del curso. En la reescritura, además, el borrador anterior y las reglas que incumplió (`revision`) |
| Salidas | Una propuesta INT-03 con texto, motivo, citas y riesgos, o una propuesta descartada si decide no comentar. El plan de red propone seguir, invitar sin nota tras `NETWORK_INVITE_AFTER_HOURS` o aceptar |
| Compuertas | Antes de pagar el borrador, Jev decide si la publicación merece comentario (`lider.comment_worthy`, R5). El autopiloto redacta un borrador cada vez, solo si queda cupo tras los comentarios pendientes, dentro de `OPERATOR_DAILY_PROPOSALS` y `OPERATOR_DAILY_LLM_USD` y con enfriamiento por autor. Un borrador que rompe una regla fija de texto (`autopiloto.comment_text_issues`) se reescribe una vez (R4). Luego `autopiloto.content_issues`: 40–900 caracteres, sin pitch, enlaces, correo, teléfono ni hashtags, con citas, sin afirmaciones por verificar, con las guardas y el enfriamiento por autor. Después, el líder. En red, `red.network_issues` y el líder |
| Frente al contrato | No propone reacciones (INT-02 solo se crea a mano), mensajes ni notas (RED-05 a RED-08). No lleva `relationship_record` con seguimiento ni recibe `participation_signal` del analista. |

### conversaciones_inbox

| | |
| --- | --- |
| Contrato | `equipos/relaciones/conversaciones_inbox.json` |
| Código | `conversaciones.py: read_inbox` (trabajo `read_inbox`) y `assess` |
| Prompt | Preguntas `noul` de `conversaciones._questions` (oportunidad, espera respuesta, venta, startups, ProjectApp), con las líneas de negocio de Gustavo en `LINES` |
| Modelo | `TYPESAFE_MODEL` (Jev 1.14) por `providers.typesafe`; ledger `inbox-assess` |
| Activación | `INBOX_ENABLED=true` (false por defecto); `autopiloto._inbox` encola `read_inbox` cada `INBOX_EVERY_MINUTES` |
| Entradas | Los chats 1 a 1 y los últimos mensajes de los que tienen algo nuevo, leídos por Unipile con topes diarios; la persona y su clasificación si es un contacto conocido |
| Salidas | `Conversation.assessment` con probabilidades y umbrales. Si parece negocio o espera respuesta, una tarjeta en Tu turno y un aviso por mensaje nuevo |
| Compuertas | Topes de lectura y de juicios por corrida; umbrales `INBOX_OPPORTUNITY_MIN`, `INBOX_REPLY_MIN` y `INBOX_PITCH_MAX`. Sin respuesta de Jev no propone nada |
| Frente al contrato | Solo lee y propone atención. No responde, no marca como leído ni crea oportunidades: la tarjeta ofrece «Marcar como oportunidad», y CHAT-* y comprometer términos siguen en Gustavo. |

### operador_cuenta

| | |
| --- | --- |
| Contrato | `equipos/operacion/operador_cuenta.json` |
| Código | `operador.py: execute`, `_publish`, `reconcile`, `resolve_uncertain` y `check_account`; `red.py: execute_action` y `reconcile_action` |
| Prompt · modelo | Ninguno: servicio determinista |
| Entradas | Una propuesta aprobada cuyo `approved_hash` coincide con el contenido |
| Salidas | Una sola `ActionExecution` por propuesta (`wrote`, identificadores externos y estado) y los avisos |
| Compuertas | Parada global (`OPERATOR_PAUSED` o la oficina), pausa de la cuenta, hora programada de la pieza, `OPERATOR_WINDOW`, espaciado entre escrituras (solo cuentan las que escribieron), topes diarios y semanales, y cuenta operativa. Antes de escribir comprueba el estado, y después lo relee; si no puede confirmar, la acción queda incierta para Gustavo |
| Frente al contrato | Sin webhooks: el autopiloto consulta cada 60 s. Ejecuta solo INT-02, INT-03, CONT-09, RED-01, RED-02 y RED-04, con un espaciado global (B2). Su nombre lo usa también el ruteador de capturas en la escena. |

### Agente líder (sin contrato)

| | |
| --- | --- |
| Contrato | No tiene |
| Código | `lider.py: review` y `_questions`, llamados desde `autopiloto.py: policy_review`; `lider.py: comment_worthy` (prefiltro de comentarios, R5); `autopiloto.py: lead_silence` |
| Prompt | Preguntas `noul` de `lider._questions` y del prefiltro; umbrales en `CHECKS`, `ORIENTATION_CHECK` y `PREFILTER_CHECKS`; criterios del barrio en `CRITERIA_DEL_BARRIO` (de `posicionamiento.lead_criteria`) |
| Modelo | `TYPESAFE_MODEL` (Jev 1.14) por `providers.typesafe`; ledger `lead-review` y `comment-prefilter`. Devuelve juicios tipados con probabilidad y no genera texto |
| Activación | `LEAD_ENABLED=true` y `LEAD_CAPABILITIES` (INT-03, CONT-09, RED-01, RED-02 y RED-04), como mucho `LEAD_MAX_REVIEWS_PER_TICK` (5) revisiones por tick (B3). En el código y en `deploy/.env.example` está en `false` por defecto |
| Entradas | Comentario: autor y texto de la publicación, el comentario y los hechos públicos. Pieza: el texto y los hechos públicos. Red: nombre, titular, ubicación, grado, origen y evidencia de la persona, con los criterios del barrio; desde R2 solo se le pregunta el riesgo. En todos, la orientación de Gustavo si existe |
| Salidas | `ActionProposal.review`: aprobar, descartar o reintentar, con respuestas, umbrales y coste |
| Compuertas | Corre después de las reglas deterministas. Un solo umbral fallido descarta, y si Jev no responde se reintenta tras `LEAD_RETRY_MINUTES` |
| Frente al diseño | No lidera ni prioriza: solo puede descartar. Su modo de fallo es la inacción silenciosa, y `lead_silence` avisa si en 7 días no aprueba nada en una capacidad. |

### Ruteador de capturas (sin contrato)

| | |
| --- | --- |
| Contrato | No tiene |
| Código | `capturas.py: classify`, llamado por `_destination` en `process` (trabajo `process_capture`) |
| Prompt | `capturas.py: ROUTE_SYSTEM` |
| Modelo · effort | `ROUTE_MODEL` (Sonnet 5.5) · low; `max_tokens` 2.000; ledger `capture-route` |
| Entradas | El texto de la captura (nota y transcripción de AssemblyAI, hasta 6.000 caracteres) y el número de fotos |
| Salidas | Destino `post` (idea para el director), `dato` (hecho privado `nota.captura-<id>`) o `galeria` (solo con fotos), y una frase de motivo |
| Compuertas | Solo corre si la captura trae texto y no indica contexto ni «Para qué es». Una respuesta inválida deja la captura en error para que Gustavo elija el destino |
| Frente al diseño | Se presenta como «operador de cuenta», el rol sin modelo (ver abajo). |

## Dónde vive la etiqueta «operador de cuenta» del ruteador

No se renombró. La parte guardada forma parte del contrato de la API de la oficina, y el prompt es una decisión de comportamiento que queda para quien rehaga el ruteador (E5 propone pasarlo a Jev).

| Dónde | Qué es | ¿Valor guardado? |
| --- | --- | --- |
| `capturas.py: ROUTE_SYSTEM` | El prompt empieza «Eres el operador de cuenta de 0ff1ce» | No: es texto del prompt. Renombrarlo cambia la entrada del modelo |
| `capturas.py: process` → `oficina_eventos.emit('entrega', 'operador_cuenta', …)` | Cada ruteo guarda un `AuditEvent` `office.event` con `target` y `metadata.rol` = `operador_cuenta` | Sí |
| `oficina_views.py: JOB_ROLES['process_capture']` | `/api/v1/oficina/actividad` muestra el trabajo de captura como `operador_cuenta` | Lo consume la PWA |
| `oficina/CONTRATO-API.md` (sección de la escena) y `docs/capturas-galeria.md` | Documentan que el ruteo sale de `operador_cuenta` | Contrato de la API |
| `tests/test_capturas.py` | Comprueban las entregas `('operador_cuenta', …)` | — |

## Orquestación

`autopiloto.py: tick` corre cada 60 s (`manage.py autopiloto`). Solo encola trabajos con identificadores deterministas, y los ejecutan dos workers: `worker`, para el trabajo general, y `worker-acciones`, para escribir y conciliar en LinkedIn. No hay eventos, ACK ni rondas como en `circuitos-equipo.md`. Es más simple que el diseño y correcto a esta escala.

## Cómo mantenerlo al día

- Si cambia un prompt, un modelo, un effort o una compuerta, actualiza este mapa y el bloque `runtime` del rol en el índice.
- `manage.py evaluar` reproduce las llamadas del verificador con su reparación, la selección, los comentarios con su reescritura y el clasificador. `tests/test_evaluaciones.py` compara esas peticiones con las de producción y falla si divergen.
