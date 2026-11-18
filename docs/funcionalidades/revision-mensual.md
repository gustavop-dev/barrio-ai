# Revisión mensual (`MEN`)

El primer lunes de cada mes, el analista de resultados revisa el mes que terminó contra el anterior y, solo si los datos lo respaldan, propone a Gustavo como mucho tres cambios de estrategia. Cada cambio cita la cifra que lo sostiene y frente a qué se compara, dice qué debería mejorar y con qué métrica se medirá. Gustavo aprueba, edita o rechaza cada uno por separado; solo lo aprobado entra en la orientación del equipo y se puede revertir. El resumen semanal solo observa: este es el único sitio donde se propone cambiar la estrategia.

- **Código:** `agentes-linkedin/infra/src/team_backend/revision_mensual.py` (`stats`, `validate`, `run`, `queue`, `generate`, `approve`, `reject`, `revert`, `mark_seen`, `cards`, `overview`, `history`), `revision_views.py`, `rediseno_views.TuTurno` (tarea `estrategia`), `autopiloto._monthly_review`, modelos `MonthlyReview` y `StrategyChange` (migración `0043_revision_mensual`). Interfaz en la app móvil: `movil/src/resultados/RevisionMensual.tsx` y `movil/src/turno/` (la PWA aún no la muestra).
- **Documentación:** este documento; ciclo `revision_mensual` y arista `cambio_de_estrategia` en [`grafo.yaml`](../../agentes-linkedin/equipos/grafo.yaml).
- **Entorno de prueba:** Claude parcheado, como en `tests/test_revision_mensual.py`.
- **Por miembro (organizaciones, fase 4):** una revisión por miembro y mes, con sus posts y su audiencia; los cambios que aprueba van a su orientación. El embudo de oportunidades y la cobertura de la analítica siguen siendo de la organización. Ver [ORG-18](organizaciones.md#org-18).

## Resumen

| ID | Función | Dónde | Estado |
| --- | --- | --- | --- |
| [MEN-01](#men-01) | Revisión automática el primer lunes del mes | backend | funciona |
| [MEN-02](#men-02) | Cifras del mes y del anterior, solo de la base | backend | funciona |
| [MEN-03](#men-03) | De cero a tres cambios, cada uno con su evidencia | backend | funciona |
| [MEN-04](#men-04) | Validador: cifras, métricas, rechazados y compuertas | backend | funciona |
| [MEN-05](#men-05) | Cada cambio en Tu turno: aprobar, editar o rechazar | backend · app móvil | implementado |
| [MEN-06](#men-06) | La orientación cambia por el camino de siempre y se revierte | backend | funciona |
| [MEN-07](#men-07) | Qué pasó con los cambios del mes anterior | backend | funciona |
| [MEN-08](#men-08) | Informe en Resultados, «Generar ahora» y aviso | backend · app móvil | implementado |
| [MEN-09](#men-09) | Presupuesto mensual propio | backend | funciona |

---

### MEN-01 · Revisión automática el primer lunes del mes <a id="men-01"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** el primer lunes de cada mes tiene la revisión del mes anterior sin pedirla, después del resumen de la última semana.
- **Código:** `autopiloto._monthly_review`, `revision_mensual.queue`, `due_at`, `last_month`, `weeks`; trabajo `monthly_review` con id determinista por mes.
- **Criterios de aceptación:**
  1. **Dado** `MONTHLY_REVIEW_ENABLED=true` y `WEEKLY_SUMMARY_TIME=07:30`, **cuando** el autopiloto corre el primer lunes del mes a las 08:31 hora local y ya existe el resumen semanal de la última semana del mes anterior, **entonces** encola un `monthly_review` con `{month: "AAAA-MM-01"}` del mes que terminó.
  2. **Dado** que falta ese resumen semanal, **cuando** pasa un día desde la hora prevista, **entonces** encola la revisión igualmente.
  3. **Dado** que el mes ya tiene revisión, hay otro `monthly_review` en curso, se agotó el presupuesto del mes, la máquina no funcionó ese mes o `MONTHLY_REVIEW_ENABLED=false`, **cuando** corre el autopiloto, **entonces** no encola nada.
  4. **Dado** un intento automático fallido, **cuando** corre otra vez el autopiloto ese mes, **entonces** no lo repite (mismo id); «Generar ahora» sigue disponible.
  5. **Dado** el informe del tick, **cuando** se encola, **entonces** `report.monthly_review` vale 1 (y `monthly_review_error` si algo falló, sin parar el resto del tick).
- **Brechas código/docs:** —
- **Cobertura QA:** `tests/test_revision_mensual.py::SchedulingTests` (pendiente de CI)

### MEN-02 · Cifras del mes y del anterior, solo de la base <a id="men-02"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** los números de la revisión salen de lo guardado, no del modelo; un dato que falta nunca aparece como cero.
- **Código:** `revision_mensual.stats`, `month_stats`, `metrics`, `week_rows`, `previous_changes`, `rejected`, `data_warnings`.
- **Criterios de aceptación:**
  1. **Dado** un mes, **cuando** se calculan las cifras, **entonces** `mes` y `mes_anterior` traen `publicaciones` (cortes de 72 h y 7 días, posts con `pieza_id` y `accion_id`), `por_tipo` (GASP), `comentarios` (con lo que pasó después, de `desenlaces.comment_rates`), `red` (con la aceptación y los seguidos con respuesta, de `desenlaces.network_engaged`), `audiencia` (primera y última captura del mes), `oportunidades` y `analitica_linkedin` (`analitica.coverage`), cada sección `{disponible: true, …}` o `{disponible: false, motivo}`.
  2. **Dado** las métricas permitidas, **cuando** se calculan, **entonces** `metricas` trae cada una con su valor del mes, del mes anterior, la diferencia y la variación ya calculadas; si falta uno de los dos valores, la diferencia es `null`.
  3. **Dado** los resúmenes semanales del mes (las semanas que empiezan en el mes), **cuando** se calculan, **entonces** `semanas` trae sus cifras principales y lo que escribió el analista, y `semanas_con_datos` cuenta las que tienen posts medidos a 72 h.
  4. **Dado** menos de 4 semanas con datos, **cuando** se calculan, **entonces** `parcial` es `true`, el primer aviso lo dice y la revisión se guarda como parcial.
- **Brechas código/docs:** la revisión no lee la evidencia compartida ni el gasto de IA por bolsillo (el resumen semanal sí).
- **Cobertura QA:** `StatsTests` (pendiente de CI)

### MEN-03 · De cero a tres cambios, cada uno con su evidencia <a id="men-03"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** recibe pocos cambios y bien justificados, o ninguno si los datos no dan para más.
- **Código:** `revision_mensual.SYSTEM`, `SCHEMA`, `message`, `run`, `baseline`; una llamada a Claude (`purpose='monthly-review'`, `effort='high'`, `max_tokens=16000`).
- **Criterios de aceptación:**
  1. **Dado** una revisión, **cuando** el analista escribe, **entonces** devuelve `titular`, `lo_que_paso`, `lo_que_funciono`, `lo_que_no`, `no_concluyente`, `cambios_previos` y `cambios`.
  2. **Dado** un cambio, **cuando** se guarda, **entonces** es un `StrategyChange` con `title`, `proposal` (la frase que entraría en la orientación), `reason`, `evidence` (`cifra`, `comparado_con`, `refs` de piezas o acciones), `expected`, `metric` y `baseline` (el valor de la métrica en el mes revisado).
  3. **Dado** que los datos no apuntan a nada claro, **cuando** el analista devuelve una lista vacía, **entonces** la revisión se guarda sin cambios y el aviso dice «Este mes no propone cambios de estrategia».
  4. **Dado** cualquier revisión, **cuando** se lee, **entonces** `metodo` dice que es una comparación de un mes con el anterior, no una prueba estadística, y si es parcial cuántas semanas tenían datos.
  5. **Dado** que el mes ya tiene revisión o aún no terminó, **cuando** corre el trabajo, **entonces** falla con 409 y no paga.
- **Brechas código/docs:** —
- **Cobertura QA:** `RunTests` (pendiente de CI)

### MEN-04 · Validador: cifras, métricas, rechazados y compuertas <a id="men-04"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** un cambio con un número inventado, sobre algo que no se mide o que toca las compuertas del equipo no le llega.
- **Código:** `revision_mensual.validate` con `resumen_semanal.allowed_numbers`, `unknown_numbers` y `operador.validate_course_citations`.
- **Criterios de aceptación:**
  1. **Dado** un cambio con una cifra que no está en `stats`, **cuando** se valida, **entonces** se descarta con `cifras_no_encontradas`; sin cifra o sin `comparado_con` con número, también (`sin_cifra`, `sin_comparacion`).
  2. **Dado** una métrica fuera de la lista (`publicaciones`, `mediana_impresiones_72h`, `mediana_interaccion_pct_72h`, `tasa_respuesta_comentarios`, `aceptacion_invitaciones`, `conectados_que_encajan`, `seguidores_ganados`, `oportunidades_creadas`), **cuando** se valida, **entonces** se descarta (`metrica_desconocida`).
  3. **Dado** un cambio cuyo título o propuesta, sin tildes ni mayúsculas, repite uno rechazado en los tres meses anteriores, **cuando** se valida, **entonces** se descarta (`repite_rechazado`).
  4. **Dado** un cambio que nombra umbrales, compuertas, filtros, prompts, límites o topes, **cuando** se valida, **entonces** se descarta (`toca_compuertas`): los agentes nunca reescriben compuertas ni prompts.
  5. **Dado** más de tres cambios válidos, **cuando** se valida, **entonces** se quedan los tres primeros y el resto queda como `mas_de_tres`; un `refs` que no es una pieza o acción de `stats` se quita.
  6. **Dado** una entrada del informe sin cifra de `stats` o sin una cita del curso recuperada, **cuando** se valida, **entonces** se quita esa frase y la revisión sigue; todo lo quitado queda en `analysis.validacion.descartado`.
- **Brechas código/docs:** la repetición de un rechazado se detecta por texto igual, no por sentido.
- **Cobertura QA:** `ValidationTests` (pendiente de CI)

### MEN-05 · Cada cambio en Tu turno: aprobar, editar o rechazar <a id="men-05"></a>

- **Dónde:** backend; interfaz pendiente
- **Estado:** parcial
- **Qué hace para Gustavo:** decide cada cambio en su bandeja de siempre, sin una bandeja aparte.
- **Código:** `revision_mensual.cards`, `rediseno_views.TuTurno` (`tasks.estrategia`), `revision_views.StrategyChangeApprove`, `StrategyChangeReject`.
- **Criterios de aceptación:**
  1. **Dado** la última revisión con cambios `propuesto`, **cuando** se abre Tu turno, **entonces** hay una tarjeta «cuando puedas» por cambio, tipo `cambio_estrategia`, id `strategy_change:<id>`, del analista, con «Aprobar», «Editar y aprobar» (`editable: {field: "text", value}`), «Rechazar» (nota opcional) y «Ver la revisión».
  2. **Dado** un cambio aprobado o rechazado, **cuando** se vuelve a abrir Tu turno, **entonces** su tarjeta ya no está.
  3. **Dado** una revisión nueva, **cuando** quedan cambios sin decidir de la anterior, **entonces** salen de Tu turno y se siguen pudiendo decidir desde Resultados.
  4. **Dado** «Rechazar» con nota, **cuando** se decide, **entonces** el cambio queda `rechazado` con su nota y las tres revisiones siguientes lo reciben en `stats.rechazados`.
  5. **Dado** una credencial de servicio, **cuando** intenta decidir, **entonces** recibe 403: solo una sesión humana con `approve_actions`.
- **Brechas código/docs:** la oficina y la app no pintan aún la acción `editable` ni la tarjeta `cambio_estrategia`.
- **Cobertura QA:** `DecisionTests` (pendiente de CI)

### MEN-06 · La orientación cambia por el camino de siempre y se revierte <a id="men-06"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** lo que aprueba llega a todos los agentes como la orientación que ya edita en Ajustes, con fecha, y puede quitarlo sin tocar lo demás.
- **Código:** `revision_mensual.approve`, `revert`, `marker`, `block`; `orientacion.update`.
- **Criterios de aceptación:**
  1. **Dado** un cambio `propuesto`, **cuando** Gustavo lo aprueba (con su texto o editado), **entonces** se añade al final de la orientación por `orientacion.update` (auditoría `orientation.updated`) como `[Revisión mensual de <mes> de <año> · cambio aprobado el AAAA-MM-DD · <id>]` y la frase en la línea siguiente; se guardan `final_text`, `orientation_before`, quién y cuándo.
  2. **Dado** un cambio aprobado, **cuando** Gustavo lo revierte, **entonces** se quita exactamente ese bloque aunque la orientación se haya editado alrededor, y el cambio queda `revertido`.
  3. **Dado** que Gustavo ya quitó ese bloque a mano, **cuando** revierte, **entonces** la orientación no se toca, el cambio queda `revertido` y la respuesta trae `found: false` con el motivo.
  4. **Dado** un cambio ya decidido, **cuando** se intenta decidir otra vez, **entonces** 409.
- **Brechas código/docs:** —
- **Cobertura QA:** `DecisionTests` (pendiente de CI)

### MEN-07 · Qué pasó con los cambios del mes anterior <a id="men-07"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** cada mes ve si lo que aprobó el mes anterior se sostuvo, empeoró o aún no se puede saber.
- **Código:** `revision_mensual.previous_changes`, `validate` (`cambios_previos`), `_write_outcomes`.
- **Criterios de aceptación:**
  1. **Dado** cambios aprobados (o luego revertidos) en la revisión anterior, **cuando** se calculan las cifras, **entonces** `cambios_previos` trae su línea base, la misma métrica ahora y la diferencia.
  2. **Dado** el veredicto del analista (`se_conserva`, `empeoro`, `sin_dato`) con su cifra, **cuando** se guarda la revisión, **entonces** se escribe en `StrategyChange.outcome` del cambio anterior con `antes`, `despues`, `diferencia`, la revisión y el mes.
  3. **Dado** un cambio sin veredicto válido, **cuando** se guarda, **entonces** su resultado es `sin_dato`.
- **Brechas código/docs:** —
- **Cobertura QA:** `RunTests` (pendiente de CI)

### MEN-08 · Informe en Resultados, «Generar ahora» y aviso <a id="men-08"></a>

- **Dónde:** backend; interfaz pendiente
- **Estado:** parcial
- **Qué hace para Gustavo:** lee el informe en Resultados, puede pedirlo antes con el coste a la vista y recibe un aviso cuando está listo.
- **Código:** `revision_views.py`; `revision_mensual.overview`, `payload`, `generation`, `estimate`; aviso `monthly_review` (`notificaciones.FEED_KINDS`).
- **Criterios de aceptación:**
  1. **Dado** `GET /api/v1/resultados/revision-mensual`, **cuando** se lee, **entonces** trae `latest` (con sus cambios y sus endpoints), `pending`, `previous` y `generate` (`available`, `reason`, `estimated_usd`, `max_usd`, `last_error`, `automatic_at`).
  2. **Dado** `POST …/generar` desde una sesión humana, **cuando** el mes pasado no tiene revisión y no hay otra en curso, **entonces** 202 con el trabajo; con el mismo `request_id`, 200 y el mismo trabajo; si no, 409.
  3. **Dado** la revisión guardada, **cuando** termina, **entonces** hay un aviso «Revisión de <mes> de <año>» en la capa «tuyo» con enlace a `/resultados#revision-mensual`, el titular y cuántos cambios esperan decisión.
- **Brechas código/docs:** la oficina y la app no muestran aún el bloque de la revisión.
- **Cobertura QA:** `ApiTests`, `RunTests` (pendiente de CI)

### MEN-09 · Presupuesto mensual propio <a id="men-09"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** la revisión no puede gastar más de lo fijado al mes.
- **Código:** `revision_mensual.budget`, `spent_this_month`, `_guard`; presupuesto `mensual` del grafo.
- **Criterios de aceptación:**
  1. **Dado** `MONTHLY_REVIEW_MAX_USD=2.00` ya gastado en el mes local con `purpose='monthly-review'`, **cuando** corre el trabajo, **entonces** falla sin llamar a Claude y el autopiloto no encola.
  2. **Dado** una revisión típica (unos 14 000 tokens de entrada y 6 000 de salida en Opus 5.5), **cuando** se estima, **entonces** «Generar ahora» muestra unos 0,19 USD y una reserva máxima de 0,47 USD.
- **Brechas código/docs:** —
- **Cobertura QA:** `RunTests`, `ApiTests` (pendiente de CI)

## Variables

| Variable | Por defecto | Qué hace |
| --- | --- | --- |
| `MONTHLY_REVIEW_ENABLED` | `true` | `false` apaga la revisión automática; «Generar ahora» sigue disponible. |
| `MONTHLY_REVIEW_MAX_USD` | `2.00` | Gasto máximo de la revisión por mes local. |
| `WEEKLY_SUMMARY_TIME` | `07:30` | La revisión corre una hora después, el primer lunes del mes. |
