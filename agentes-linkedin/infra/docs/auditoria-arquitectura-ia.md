# Auditoría de la arquitectura de IA

Revisión del 7 de noviembre de 2026 sobre `main` en `1a09154` (PR #13). La versión editable, con el mapa de roles dibujado, está en [Claude Docs](https://claude.ai/artifact/5F9iikijgKKXGeNkuu3BxU).

La arquitectura es sólida en lo que más importa: ningún modelo escribe en LinkedIn, cada acción se ejecuta una sola vez y todo gasto pasa por un ledger con reservas. Los problemas están en cómo encajan las piezas:

- trabajo pagado que se pierde sin aviso;
- una cola única que frena la ejecución;
- decisiones que se toman dos o tres veces;
- un diseño de agentes que ya no describe lo que corre.

**Alcance.** El código de IA en `agentes-linkedin/infra/src/` (proveedores, operador, autopiloto, editorial, red, líder, guardas, captura, worker) y los contratos y ciclos de `agentes-linkedin/`.

**Qué cambió desde la primera revisión.** #12 añadió el enfriamiento por autor y el reintento por presupuesto; #13, la captura, las notificaciones y el feed de la oficina. Ningún hallazgo anterior quedó resuelto, aparecen E5 y E6, y B1 empeora.

**Limitación.** La base local solo tiene las corridas piloto del 6 de noviembre y esta revisión no tuvo lectura en producción. Los costos son estimaciones con tamaños de unidades medidos; al final hay consultas para confirmar los hallazgos con datos reales.

Rutas relativas a `agentes-linkedin/infra/src/`.

## Errores

| # | Problema | Dónde | Efecto | Arreglo |
| --- | --- | --- | --- | --- |
| E1 | `max_tokens` demasiado bajo para modelos con pensamiento siempre activo. Director, lectores, selección y verificador tienen 4.000; el verificador va con effort `high`. El clasificador de red tiene 4.000 y no fija `effort`, así que Sonnet 5.5 usa `high`. | `team_backend/editorial.py:193-197`, `team_backend/red.py:233` | Si el pensamiento agota el tope, el JSON llega cortado y `_stage` solo dice «no devolvió JSON válido». La pieza del día se pierde sin reintento, con el gasto ya hecho. | Subir a ~16k (ya hay streaming), comprobar `stop_reason == 'max_tokens'` con un error explícito y fijar `effort='low'` en el clasificador. |
| E2 | Sobre-redacción de comentarios: `_propose` solo descuenta ejecuciones, no las propuestas aprobadas que esperan turno. | `team_backend/autopiloto.py:212-219` | Con 20 min entre escrituras se redactan hasta 6 borradores para 3 cupos. Los sobrantes salen al día siguiente sobre posts viejos o caducan a las 48 h. En producción llegó a haber 11 pendientes (mensaje de #12); el enfriamiento por autor reparte mejor, pero no corrige la cuenta. | Restar las INT-03 abiertas, como ya hace `room()` en `red.py:301`. |
| E3 | Las ejecuciones que no escribieron nada consumen cupo y espaciado: «ya lo seguías», `already_connected`, `invitation_gone`, `account_not_running`. | `team_backend/operador.py:81-90` | Gastan el tope diario y bloquean 20 min sin tocar LinkedIn. | Contar solo las ejecuciones que escribieron (un booleano `wrote` o un filtro por `error_kind`). |
| E4 | El precio de lectura de caché está fijo en 0,1× para todos los modelos. | `knowledge/providers.py:19` | Opus 5.5 lee a 0,05× ($0,20/M): el ledger sobreestima el gasto. | Multiplicador por modelo. |
| E5 | El ruteo de capturas (#13) usa Sonnet 5.5 con `max_tokens=400` y sin `effort`, así que va en `high`. Es el patrón de E1, más apretado. | `team_backend/capturas.py:247` | Si el pensamiento agota los 400 tokens, la captura queda en error y Gustavo tiene que elegir «Para qué es» y reenviarla. | `effort='low'` y ~2.000 tokens, o una pregunta a Jev (post o dato) con umbral. |
| E6 | Las ideas de la captura se marcan «usado» justo después del brief, antes de redactar, verificar y publicar. | `team_backend/editorial.py:373` | Si la pieza se salta, se descarta o se bloquea, la idea de Gustavo queda gastada en una pieza que no salió y no vuelve al director. | Marcarla cuando la pieza quede lista, o devolverla a «idea» si termina en skipped, blocked o failed. |

## Cuellos de botella

| # | Problema | Dónde | Efecto | Arreglo |
| --- | --- | --- | --- | --- |
| B1 | Un solo worker con una cola FIFO. `prepare_piece` son 5 llamadas a Opus en serie; `classify` y `plan_network` hacen decenas de lecturas HTTP en serie. Desde #13, `process_capture` espera a AssemblyAI hasta 300 s en el mismo worker. | `team_backend/jobs.py:94`, servicio `worker` | `execute_action` y `reconcile` esperan detrás del trabajo de LLM y de transcripción. | Dos carriles: filtro por tipo en `claim` (`runworker --kinds`) y un segundo contenedor. |
| B2 | Espaciado global de 20 min entre cualquier escritura. | `team_backend/operador.py:78-84` | 14 h de ventana dan como máximo 42 escrituras y la suma de topes es 44: los topes nunca se alcanzan. Un follow a las 08:25 retrasa la pieza de las 08:30 hasta las 08:45. | Espaciado por tipo de acción y reservar el hueco previo a la pieza. |
| B3 | El líder (Jev) se llama dentro del tick del autopiloto, propuesta por propuesta, con timeout de 60 s. | `team_backend/autopiloto.py:163` → `team_backend/lider.py:117` | Tras un `plan_network` puede haber ~25 propuestas: el tick se bloquea minutos. | Tope de revisiones por tick o mover la revisión al worker. |
| B4 | Tope de 30 lecturas de perfil al día, compartido entre enriquecer y refrescar. | `team_backend/red.py:28` | La clasificación se queda sin cupo mientras `discover` agrega hasta 60 candidatos al día que nunca se clasifican. | Frenar `discover` con backlog alto; ver R1. |
| B5 | Límite de gasto de por vida: suma todo el ledger del proveedor desde el inicio, bajo un lock compartido. Las reservas `uncertain` cuentan para siempre. | `knowledge/providers.py:28-39` | En una máquina 24/7 es un precipicio que solo se levanta editando `.env`. Desde #13 también aplica a AssemblyAI. | Ventana mensual e índice en `(provider, created_at)`. |

## Reprocesos

| # | Problema | Dónde | Arreglo |
| --- | --- | --- | --- |
| R1 | El perfil se lee hasta 4 veces por follow: `_enrich`, `_refresh` en el plan y la comprobación antes y después en la ejecución. Las lecturas de ejecución no cuentan para el tope. | `team_backend/red.py:211`, `:306`, `:381-388` | Quitar el refresh del plan (la ejecución ya cubre todos los estados) y contar las lecturas de ejecución. |
| R2 | «¿Encaja?» se juzga dos o tres veces con los mismos datos: Sonnet (fit ≥ 0,6), Jev para el follow (≥ 0,6) y otra vez para la invitación (≥ 0,7). | `team_backend/red.py:244`, `team_backend/lider.py:39-41` | Un solo juez: que clasifique Jev y el líder solo mire `riesgo` en RED-*. |
| R3 | El verificador (Opus, `high`) corre antes que las reglas deterministas de longitud, URL, correo, pitch y hashtags, que solo se aplican después en la política. Las guardas corren dos veces. | `team_backend/editorial.py:416-422`, `team_backend/autopiloto.py:56-73` | Reglas deterministas justo tras la selección. |
| R4 | Cualquier hallazgo bloquea la pieza y se pierde el día con ~$0,6–0,75 gastados (desde #12 solo se reintenta un corte por presupuesto). Un comentario descartado por un hashtag tampoco se corrige. | `team_backend/editorial.py:404-408`, `team_backend/autopiloto.py:108-118` | Una pasada de reparación con los hallazgos concretos y verificar de nuevo. |
| R5 | Se paga Opus antes de saber si el post merece comentario. | `team_backend/autopiloto.py:212-227` | Prefiltro con Jev antes de encolar `propose_comment`. |
| R6 | El contexto del curso se relee en cada etapa: una conexión nueva a Postgres por unidad y 3 consultas, de las que se descartan 2. `knowledge/db.py` no usa pool. | `team_backend/operador.py:509-519`, `knowledge/retrieval.py:15-21` | `lru_cache` sobre las unidades, que son inmutables, y un pool de conexiones. |

## Costos

Estimado: unos $0,10–0,15 por borrador de comentario y $0,6–0,75 por pieza editorial, todo en Opus 5.5. Las unidades del curso se midieron en la base local con el tokenizer del código; el de Claude cuenta ~15–20% más.

| Llamada | Entrada aprox. (tokens) | Unidades del curso |
| --- | --- | --- |
| Comentario | ~20k | 6 unidades, 9,3k |
| Director | ~26k | 13 unidades, 20,2k |
| Redactor A/B | ~32k | 21 unidades, 24,5k |
| Lectores | ~6k | 2 unidades, 3,4k |
| Selección | ~17k | 5 unidades, 7,9k |
| Verificador | ~10k | 5 unidades, 6,5k |

- **C1. La caché de comentarios está mal ubicada** (`team_backend/operador.py:532`). Las unidades van en el mensaje de usuario, después del post, y no se cachean. Pasarlas a un bloque de `system` con `cache_control` las lee a 0,05×.
- **C2. La caché del circuito editorial no sirve.** Cada system se usa una vez al día, así que la caché de 5 min solo suma 25% por escritura (`knowledge/providers.py:164`). Unir un prefijo común entre etapas no compensa: comparten ~7k de 62k tokens.
- **C3. Modelo por etapa.** Tras una evaluación pequeña: panel de lectores a Sonnet 5.5; clasificadores a Haiku 5.5 o a Jev.
- **C4. API de lotes (50% menos)** para la pieza, que se prepara 12 h antes, y la clasificación. Exige polling.
- **C5. Detalles.** Un cliente Anthropic nuevo por llamada y una ida extra a `count_tokens` antes de cada generación.

## Auditoría del diseño de los agentes

El reparto de roles es apropiado y la frontera más importante está bien puesta: solo el operador determinista escribe en LinkedIn. Lo que falla es la relación entre diseño y realidad, y faltan las dos piezas que cierran el ciclo: aprender de los resultados y convertir conversaciones en oportunidades.

Los 16 contratos de `agentes-linkedin/equipos/` son plantillas de 30–80 KB marcadas como no ejecutables; el runtime no las lee y usa prompts cortos escritos en Python. `indice-agentes-v1.json` sigue marcando los 16 como `diseno_no_activo` mientras el circuito publica solo en producción.

| Rol | Qué corre hoy | Veredicto | Recomendación |
| --- | --- | --- | --- |
| posicionamiento, perfil | `knowledge.agents.run`, a mano; su salida no llega al bucle | Desconectados | La dirección de Gustavo está copiada en tres sitios: `DIRECTION` (`editorial.py:79`), `CLASSIFY_SYSTEM` (`red.py:171`) y `CRITERIA_DEL_BARRIO` (`lider.py:21`), con modalidades distintas (`comunidad` frente a `comunidad_autoridad`; Oportunidades tiene 3). Un solo artefacto de posicionamiento, versionado y confirmado. |
| investigador_referentes | Solo clasifica personas (Sonnet); los referentes los añade Gustavo | Apropiado, pero duplica al líder | Un solo juez de encaje (R2). |
| analista_barrio_resultados | Solo recoge métricas (`metricas.py`) | Le falta su núcleo | `_history` (`editorial.py:333`) no pasa resultados al director. Desde #13 recibe las ideas y los comentarios de Gustavo, pero no los datos. Pasar métricas de 72 h y 7 d y un resumen semanal que proponga orientación. |
| director_editorial | Dos llamadas: brief y selección | Apropiado | Le falta la ronda correctiva que su contrato prevé (máximo 2, `circuitos-equipo.md`). |
| copywriter_a y _b | Una llamada escribe las dos variantes | Aceptable | B se escribe viendo A, así que no son independientes. Si las variantes salen parecidas, dos llamadas en paralelo. |
| 5 lectores | Una llamada, siempre los cinco, en Opus | El de menor valor por costo | El diseño pide elegir el subconjunto en el brief. Medir la selección con y sin panel; si no cambia, plegarlo como rúbrica. |
| editor_verificador | Opus con effort `high` | Apropiado; es la compuerta clave | Ver E1 y R3. |
| relaciones_comunidad | Comentarios (Opus) y plan de red (determinista) | Apropiado | Ver E2 y R5. |
| conversaciones_inbox | No existe | El mayor hueco frente al objetivo 60/40 | Siguiente agente a construir, primero de solo lectura: leer el inbox y proponer oportunidades. Comprometer términos sigue siendo nivel C de Gustavo. |
| operador_cuenta | Determinista, exactamente una vez | Lo mejor del sistema | Ver E3 y B2. |
| Agente líder (fuera del diseño) | Jev juzga cada propuesta y solo puede descartar | Útil como segunda opinión barata; el nombre engaña | No lidera ni prioriza. Su modo de fallo es la inacción silenciosa: alertar si la aprobación de una capacidad cae a cero en 7 días y calibrar umbrales con vetos y resultados. |
| Ruteador de capturas (nuevo en #13) | Sonnet decide si una captura sin destino es idea, dato o galería | Apropiado como función; frágil y mal nombrado | Se presenta como «operador de cuenta», el rol sin modelo. Ver E5; es un buen caso para Jev. |
| Orquestación | Tick del autopiloto cada 60 s, sin eventos, ACK ni rondas | Más simple que el diseño y correcto a esta escala | Actualizar el diseño para que describa lo que corre. |

Tres problemas transversales:

1. **Diseño y realidad divergen.** Quien lea los contratos no sabe qué hace la máquina, y aparecen roles sin contrato (el líder, el ruteador de capturas). Marcar en el índice el estado real de cada rol y enlazar cada contrato con la función y el prompt que lo implementan.
2. **La regla contra experiencias inventadas se apaga con un solo hecho público.** `guardas.invented_experience` devuelve vacío en cuanto existe cualquier hecho público (`guardas.py:63`); desde ese momento un «I built…» solo lo frenan los dos modelos. La regla debería comparar la afirmación con los hechos.
   - **Arreglado en la fase 2.** Ahora compara cada afirmación en primera persona (la frase de «I built», «my clients», «construí», «en mi empresa»…) con los hechos públicos confirmados. La marca si trae una cifra que ningún hecho contiene, o si no comparte ninguna palabra de contenido ni ninguna cifra con ellos. Es conservadora: basta una palabra en común, y tener equipo, empresa o clientes cuenta como una sola familia en inglés y en español. El verificador sigue siendo el juez principal.
3. **No hay evaluaciones de calidad.** Las pruebas usan proveedores simulados y solo comprueban la mecánica. Sin evaluación no se puede cambiar de modelo, mover umbrales ni quitar el panel con seguridad. Para empezar bastan 20–30 casos por agente sacados del historial: piezas, descartes y vetos.

Conviene conservar: salidas estructuradas con esquema, texto de terceros tratado como datos, vigilancia de filtraciones de la orientación privada, ejecución exactamente una vez y preguntas a Gustavo solo por hechos que nadie más conoce.

## Plan sugerido

**Fase 1: errores y cuello del worker**

Hecha en el PR #15. E4 (precio de lectura de caché por modelo) va en el mismo PR.

- [x] E1 y E5: `max_tokens` suficiente, comprobar `stop_reason` y `effort` en los clasificadores (`low` en captura; `medium` en red, para no perder juicio)
- [x] E2: contar comentarios aprobados pendientes antes de redactar otro
- [x] E3: que solo cuenten como cupo las ejecuciones que escribieron (`ActionExecution.wrote`)
- [x] E6: la idea vuelve a la mesa si su pieza se salta, se bloquea, falla, se descarta, se veta o LinkedIn no la publica
- [x] B1: separar la cola en dos carriles (`worker` general y `worker-acciones`)

**Fase 2: reprocesos**

- [ ] R1: quitar el refresh de perfil del plan y contar las lecturas de ejecución
- [ ] R2: un solo juez de encaje para la red
- [x] R3 y R4: reglas deterministas antes del verificador y una ronda de reparación (pieza editorial; `EDITORIAL_REPAIR=false` la apaga). La reparación del comentario descartado por un hashtag queda fuera de este corte
- [ ] R5: prefiltro con Jev antes de redactar un comentario
- [ ] B3: tope de revisiones del líder por tick

**Fase 3: diseño y costo**

- [ ] 20–30 casos de evaluación por agente, sacados del historial
- [x] Un solo artefacto de posicionamiento para director, clasificador y líder (`team_backend/posicionamiento.py`, `posicionamiento-v1`; sigue siendo una propuesta interna, Gustavo no la ha confirmado)
- [x] Resultados de las piezas en el historial del director (cortes de 72 h y 7 d y resumen de 30 días por pilar y modalidad; el resumen semanal que propone orientación sigue pendiente)
- [ ] Alerta si la aprobación del líder cae a cero en una capacidad
- [ ] Agente de inbox de solo lectura que proponga oportunidades
- [ ] C1 a C3, validados con las evaluaciones
  - [x] C3 configurable, sin cambiar: `EDITORIAL_MODEL_<ETAPA>` por etapa editorial; por defecto sigue el modelo actual hasta que la evaluación respalde el cambio

## Cómo confirmarlo en producción

Consultas de solo lectura sobre la base del servidor:

```sql
-- E1 y E5: respuestas cortadas por max_tokens, por propósito
SELECT purpose, usage->>'stop_reason' AS stop, count(*)
FROM usage_ledger WHERE provider = 'anthropic' GROUP BY 1, 2 ORDER BY 1;

-- E2: comentarios por estado
SELECT state, count(*) FROM team_backend_actionproposal
WHERE capability = 'INT-03' GROUP BY 1;

-- E3: ejecuciones que no escribieron
SELECT state, error_kind, count(*) FROM team_backend_actionexecution GROUP BY 1, 2;

-- E6: ideas usadas en piezas que no salieron
SELECT p.state, count(*) FROM team_backend_capture c
JOIN team_backend_editorialpiece p ON p.id::text = c.routed_to->>'used_in'
WHERE c.state = 'usado' GROUP BY 1;

-- Líder: decisiones por capacidad
SELECT capability, review->>'decision' AS decision, count(*)
FROM team_backend_actionproposal WHERE review <> '{}' GROUP BY 1, 2;
```
