# Resumen semanal (`SEM`)

Cada lunes, el analista de resultados escribe para Gustavo el resumen de la semana que terminó: qué funcionó, qué no y qué cambiar, cada frase atada a una cifra de la base. Si los datos lo respaldan, propone una orientación que solo Gustavo puede adoptar.

- **Código:** `agentes-linkedin/infra/src/team_backend/resumen_semanal.py` (`stats`, `run`, `validate`, `generate`, `apply`, `discard`, `undo`, `mark_seen`, `overview`, `for_director`), `resultados_views.py`, `rediseno_views._summary_card`, `autopiloto._weekly_summary`. Interfaz: `oficina/src/pages/resultados/ResumenSemanal.tsx` y `movil/src/resultados/ResumenSemanal.tsx`.
- **Documentación:** [`resumen-semanal.md`](../../agentes-linkedin/infra/docs/resumen-semanal.md), sección «Resumen semanal» de [`CONTRATO-API.md`](../../oficina/CONTRATO-API.md).
- **Entorno de prueba:** Claude parcheado, como en `tests/test_resumen_semanal.py`.

## Resumen

| ID | Función | Dónde | Estado |
| --- | --- | --- | --- |
| [SEM-01](#sem-01) | Resumen automático cada lunes | backend | funciona |
| [SEM-02](#sem-02) | Cifras deterministas de la semana y de la anterior | backend | funciona |
| [SEM-03](#sem-03) | Validador de cifras | backend | funciona |
| [SEM-04](#sem-04) | Presupuesto semanal propio | backend | funciona |
| [SEM-05](#sem-05) | Bloque «Resumen de la semana» en Resultados | PWA · app · backend | parcial |
| [SEM-06](#sem-06) | «Usar como orientación», «Descartar» y «Deshacer» | PWA · app · backend | funciona |
| [SEM-07](#sem-07) | «Generar ahora» con el coste a la vista | PWA · app · backend | funciona |
| [SEM-08](#sem-08) | Tarjeta en Tu turno y aviso | PWA · app · backend | funciona |
| [SEM-09](#sem-09) | Recomendaciones para el director | backend | funciona |

---

### SEM-01 · Resumen automático cada lunes <a id="sem-01"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** el lunes por la mañana tiene el resumen de la semana anterior sin pedirlo.
- **Código:** `autopiloto._weekly_summary`, `resumen_semanal.queue`, trabajo `weekly_summary` con id determinista por semana.
- **Criterios de aceptación:**
  1. **Dado** `WEEKLY_SUMMARY_ENABLED=true` y `WEEKLY_SUMMARY_TIME=07:30`, **cuando** el autopiloto corre el lunes a las 07:31 hora local, **entonces** encola un `weekly_summary` para la semana ISO anterior (lunes a domingo) en el carril general.
  2. **Dado** que esa semana ya tiene resumen, o hay otro trabajo en curso, o se agotó el presupuesto semanal, o la máquina no funcionó esa semana, **cuando** corre el autopiloto, **entonces** no encola nada.
  3. **Dado** que la máquina estuvo parada el lunes, **cuando** vuelve a correr el martes, **entonces** encola el resumen de esa misma semana.
  4. **Dado** un intento automático fallido, **cuando** corre otra vez el autopiloto, **entonces** no lo repite; `generate.last_error` lo muestra.
  5. **Dado** el resumen guardado, **cuando** termina, **entonces** queda en estado `nuevo`, se registra `weekly_summary.created` y la escena muestra una `entrega` del analista al director.
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### SEM-02 · Cifras deterministas de la semana y de la anterior <a id="sem-02"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** los números del resumen salen de la base, no del modelo, y un dato que falta nunca se presenta como cero.
- **Código:** `resumen_semanal.stats`, `week_stats`, `compare`, `data_warnings`.
- **Criterios de aceptación:**
  1. **Dado** una semana, **cuando** se calculan las cifras, **entonces** traen las secciones `publicaciones`, `comentarios`, `red`, `oportunidades`, `conversaciones`, `capturas`, `gasto_ia`, `lider` y `pausas_y_bloqueos`, cada una `{disponible: true, …}` o `{disponible: false, motivo}`.
  2. **Dado** `INBOX_ENABLED=false`, **cuando** se calculan, **entonces** `conversaciones` es `{disponible: false, motivo}`, no ceros.
  3. **Dado** que Gustavo no envió capturas, **cuando** se calculan, **entonces** `capturas` está disponible con 0 (un cero real).
  4. **Dado** dos de tres posts con corte de 72 h, **cuando** se calculan los avisos, **entonces** `avisos_de_datos` incluye «Pocos datos: 2 de 3 posts con corte de 72 h».
  5. **Dado** `comparacion`, **cuando** el valor anterior es 0 o falta, **entonces** `variacion_pct` es `null`.
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### SEM-03 · Validador de cifras <a id="sem-03"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** si el modelo se inventa un número, esa frase se quita y se le avisa.
- **Código:** `resumen_semanal.validate`, `allowed_numbers`, `unknown_numbers`.
- **Criterios de aceptación:**
  1. **Dado** una recomendación que cita «37» y ese número no está en las cifras, **cuando** se valida, **entonces** se quita, queda en `analysis.validacion.descartado` con `cifras_no_encontradas: ["37"]` y `advertencias` termina con «Se quitaron N frases del análisis con cifras que no están en los datos de la semana».
  2. **Dado** una entrada de lista sin ningún número, **cuando** se valida, **entonces** se quita (`sin_cifra: true`).
  3. **Dado** un titular con un número inventado, **cuando** se valida, **entonces** se sustituye por «Semana del … al …».
  4. **Dado** «1.840» en el texto y 1840 en las cifras, **cuando** se valida, **entonces** se acepta (lectura española o inglesa).
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### SEM-04 · Presupuesto semanal propio <a id="sem-04"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** el resumen tiene su propio tope de gasto por semana y nunca le quita presupuesto a los comentarios ni a la publicación.
- **Código:** `resumen_semanal.budget`, `spent_this_week`, `_guard`, `WEEKLY_SUMMARY_LLM_USD` (1 USD).
- **Criterios de aceptación:**
  1. **Dado** que lo gastado con propósito `weekly-summary` esta semana ISO local llega al tope, **cuando** corre un trabajo, **entonces** falla con «Presupuesto del resumen semanal agotado esta semana (WEEKLY_SUMMARY_LLM_USD); no se gasta más.» sin llamar a Claude.
  2. **Dado** el gasto del resumen, **cuando** se calculan los presupuestos de comentarios y editorial, **entonces** no cuenta en ellos.
- **Brechas código/docs:** Ajustes › Gasto no muestra el presupuesto del resumen semanal como línea propia (ver [AJU-05](ajustes.md#aju-05)).
- **Cobertura QA:** pendiente

### SEM-05 · Bloque «Resumen de la semana» en Resultados <a id="sem-05"></a>

- **Dónde:** PWA · app · backend
- **Estado:** parcial
- **Qué hace para Gustavo:** arriba de Resultados lee el último resumen: titular, lo que funcionó, lo que no, recomendaciones, advertencias, coste y semanas anteriores.
- **Código:** `GET /api/v1/resultados/resumen-semanal`, `POST …/<id>/visto`; `ResumenSemanal.tsx` en la PWA y en la app.
- **Criterios de aceptación:**
  1. **Dado** un resumen, **cuando** Gustavo abre Resultados, **entonces** ve arriba, con el ancla `#resumen`, la semana, el titular, el retrato del analista, «Lo que funcionó», «Lo que no» y «Recomendaciones» (cada entrada con «Dato: <cifra>»), las advertencias y «Escrito el <fecha> · <coste>».
  2. **Dado** una lista vacía, **cuando** se pinta, **entonces** dice «Nada destacable con los datos de la semana.», «Nada que señalar con los datos de la semana.» o «Sin recomendaciones: los datos no dan para tanto.».
  3. **Dado** un resumen en estado `nuevo`, **cuando** se muestra, **entonces** la interfaz llama a `…/visto` y pasa a `visto`.
  4. **Dado** semanas anteriores, **cuando** abre «Ver semanas anteriores · N», **entonces** ve hasta 12, de la más reciente a la más antigua.
  5. **Dado** que nunca hubo un resumen, **cuando** abre Resultados, **entonces** ve «Todavía no hay resúmenes semanales» y «Cada semana el analista resume qué funcionó, qué no y qué cambiar, con las cifras de la semana.».
  6. **Dado** que la semana pasada no tiene resumen y no se puede generar, **cuando** abre Resultados, **entonces** ve el motivo (`generate.reason`, por ejemplo «Presupuesto del resumen semanal agotado esta semana.»). **Hoy falla en la PWA:** el botón «Generar ahora» desaparece sin explicar por qué.
  7. **Dado** un error al cargar el bloque, **cuando** falla, **entonces** solo ese bloque muestra el error con «Reintentar»; el resto de Resultados sigue. **Hoy es parcial:** las dos interfaces muestran «No se pudo cargar el resumen de la semana.» sin botón «Reintentar».
- **Brechas código/docs:** si falla la llamada automática a `…/visto`, no se avisa y la etiqueta «Nuevo» se queda (las dos interfaces).
- **Cobertura QA:** SEM-05.1, 4 y 7 en `08-resultados.yaml` y `08-resultados-errores.yaml` (listas, advertencias, semanas anteriores; el error del bloque, aún sin «Reintentar») · 2026-11-08 · pasa

### SEM-06 · «Usar como orientación», «Descartar» y «Deshacer» <a id="sem-06"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** si el analista propone una orientación, la adopta o la descarta con un toque, y tiene 5 segundos para deshacerlo.
- **Código:** `POST …/<id>/aplicar`, `…/descartar`, `…/deshacer` (`resumen_semanal.apply`, `discard`, `undo`).
- **Criterios de aceptación:**
  1. **Dado** un resumen `nuevo` o `visto` con `orientacion_propuesta`, **cuando** pulsa «Usar como orientación», **entonces** la orientación del equipo pasa a ser ese texto (como `PUT /api/v1/orientacion`), el resumen queda `aplicado` y la respuesta trae `orientation` y `previous_orientation`.
  2. **Dado** el aviso con «Deshacer», **cuando** lo pulsa antes de 5 s, **entonces** vuelve la orientación anterior y el resumen queda `visto`.
  3. **Dado** que la orientación cambió después de aplicarla, **cuando** intenta deshacer, **entonces** recibe 409 «La orientación cambió después; edítala en Ajustes.».
  4. **Dado** «Descartar», **cuando** lo pulsa, **entonces** el resumen queda `descartado`, desaparece la tarjeta de Tu turno y el director deja de leer sus recomendaciones.
  5. **Dado** un resumen ya decidido, **cuando** se intenta aplicar o descartar otra vez, **entonces** responde 409 «Este resumen ya está decidido.».
  6. **Dado** un resumen sin orientación propuesta, **cuando** se intenta aplicar, **entonces** responde 409 «Este resumen no propone una orientación.».
  7. **Dado** un token de servicio, **cuando** intenta decidir, **entonces** recibe 403.
- **Brechas código/docs:** el límite de 5 s lo pone la interfaz; la API acepta `deshacer` en cualquier momento mientras el resumen esté `aplicado` o `descartado` (`can_undo`).
- **Cobertura QA:** SEM-06.1 y 2, y «Descartar» con «Deshacer», en `08-resultados.yaml` · 2026-11-08 · pasa

### SEM-07 · «Generar ahora» con el coste a la vista <a id="sem-07"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** si la semana pasada no tiene resumen, puede pedirlo ya, viendo antes cuánto costará.
- **Código:** `POST /api/v1/resultados/resumen-semanal/generar` (`resumen_semanal.generate`), `generate.estimated_usd` y `max_usd`.
- **Criterios de aceptación:**
  1. **Dado** `generate.available: true`, **cuando** pulsa «Generar ahora», **entonces** ve una confirmación con el coste estimado y el máximo antes de encolar nada.
  2. **Dado** que confirma, **cuando** se envía, **entonces** recibe 202 con `week_start` y `job`, y el bloque muestra que se está preparando.
  3. **Dado** que la semana ya tiene resumen, otro se está preparando o se agotó el presupuesto, **cuando** se pide, **entonces** responde 409 con «La semana pasada ya tiene su resumen.», «El resumen ya se está preparando.» o el motivo de presupuesto.
  4. **Dado** el mismo `request_id`, **cuando** se reintenta, **entonces** recibe 200 con el mismo trabajo.
  5. **Dado** un usuario sin `use_paid_providers`, **cuando** lo pide, **entonces** recibe 403.
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### SEM-08 · Tarjeta en Tu turno y aviso <a id="sem-08"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** le llega «Resumen de la semana listo» y, si hay una orientación propuesta sin decidir, una tarjeta en Tu turno.
- **Código:** `rediseno_views._summary_card`, `resumen_semanal.pending_proposal`, `avisar('weekly_summary', …)`.
- **Criterios de aceptación:**
  1. **Dado** un resumen nuevo, **cuando** se guarda, **entonces** se registra la Notificación `weekly_summary` (capa `tuyo`) con el titular como detalle, enlace `/resultados#resumen` y push por defecto.
  2. **Dado** que el último resumen propone orientación y está `nuevo` o `visto`, **cuando** Gustavo abre Tu turno, **entonces** ve la tarjeta «El analista propone una orientación», prioridad Cuando puedas, con el texto propuesto, «Ver el resumen» (navega a `/resultados#resumen` dentro de la app) y «Descartar».
  3. **Dado** que lo aplica o lo descarta, **cuando** vuelve a Tu turno, **entonces** la tarjeta ya no está.
  4. **Dado** `tasks`, **cuando** no hay tarjeta de resumen, **entonces** `tasks.resumen` llega vacío.
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### SEM-09 · Recomendaciones para el director <a id="sem-09"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** el director tiene en cuenta las recomendaciones del último resumen como pista, nunca como orientación.
- **Código:** `resumen_semanal.for_director`, `editorial._run` (`weekly_recommendations`).
- **Criterios de aceptación:**
  1. **Dado** un resumen no descartado cuya semana empezó hace 3 semanas o menos, **cuando** corre el director, **entonces** recibe `weekly_recommendations` con la semana y las recomendaciones.
  2. **Dado** que el último resumen está descartado o es más antiguo, **cuando** corre el director, **entonces** recibe `null`.
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

## Ampliación prevista de aprendizaje

[BIB-07](biblioteca-equipos.md#bib-07), **no implementado**, añade criterios del curso a la interpretación semanal y referencias a los estudios de comunidad y experimentos de [OBS-03/04](observatorio-referentes.md#obs-03). Conserva los cálculos deterministas, el validador de cifras y la aprobación de orientación de SEM-06; no cambia referentes por sí mismo.

## Retiradas

Ninguna.
