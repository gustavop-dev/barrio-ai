# QA independiente de contratos y coordinación

Fecha: 2026-11-06. Alcance: revisión documental de F0 y consistencia de fichas de los 13 roles. No se ejecutaron agentes, proveedores, publicación, integraciones ni pruebas de backend. Esta revisión no acredita rendimiento editorial ni comportamiento del runtime. Los hallazgos describen ambigüedades que conviene resolver antes de traducir el diseño a F3.

Resultado de la revalidación: cinco hallazgos P2 corregidos documentalmente; ningún P1 identificado ni P2 abierto en el alcance revisado. Las correcciones se comprobaron por relectura de contratos y parseo local de las 13 fichas JSON, sin ejecutar su comportamiento.

## Hallazgos iniciales

### QA-C01 — P2: Editorial obliga a despachar cinco lectores aunque el contrato global permite seleccionar perspectivas

- **Archivos/secciones:** `ciclo-editorial.md`, tablas «Entradas y salida de los grupos vecinos» y «Flujo y decisiones»; `equipos/editorial/director_editorial.json`, `funcionamiento.pasos`, `coordinacion` y esquema `editorial_brief`. Contraste: `ciclo-lectores.md`, «Entrada y activación», y `circuitos-equipo.md`, «Función de orquestación».
- **Problema:** el ciclo y la ficha del Director ordenan enviar borradores a cinco lectores. El contrato de Lectores dispone seleccionar perspectivas pertinentes en el brief y no ejecutar los cinco por defecto. El esquema del brief no declara esa selección.
- **Ejemplo:** una pieza técnica requiere par y comprador. El orquestador crea dos lecturas, mientras el Director espera cinco entregas, o crea tres llamadas adicionales sin justificación.
- **Corrección propuesta:** guardar en el brief los IDs de lectores seleccionados, perspectiva prioritaria y motivo; despachar y esperar solo ese conjunto. Los cinco roles permanecen disponibles. Declarar qué hacer si un lector seleccionado falla, sin inventar su evaluación ni repetir un resultado pagado incierto.
- **Estado:** detectado abierto; corregido y revalidado documentalmente. Evidencia en la tabla de cierre.

### QA-C02 — P2: omitir una afirmación después de agotar las rondas no tiene una ruta de revisión coherente

- **Archivos/secciones:** `circuitos-equipo.md`, «Control de bucles, coste y estados»; `ciclo-revision.md`, «Devoluciones y publicación»; `ciclo-editorial.md`, «Estados, rondas y recuperación»; controles de las fichas.
- **Problema:** los contratos permiten omitir una afirmación tras agotar las dos rondas. A la vez, cualquier edición exige revisar el nuevo hash y el límite impide más correcciones. No se delimita si la omisión consume otra ronda, si solo se permite una comprobación sin nueva edición o si necesariamente termina en espera/descarte.
- **Ejemplo:** Revisión encuentra una cifra accesoria falsa en la segunda entrega corregida. El Director la quita y crea otra versión: podría enviarse sin revisión o generar una tercera corrección encubierta.
- **Corrección propuesta:** definir una regla única. Una opción conservadora es permitir omisiones dentro de rondas disponibles y, tras agotarlas, esperar/descartar; la comprobación final de la última entrega puede aceptar o detener, pero no iniciar una tercera edición. Una reanudación con evidencia material nueva conserva historial, límites y autorización explícita del nuevo alcance.
- **Estado:** detectado abierto; corregido y revalidado documentalmente. Evidencia en la tabla de cierre.

### QA-C03 — P2: la ficha del Director usa ACK como transición a presentación humana

- **Archivos/secciones:** `equipos/editorial/director_editorial.json`, `funcionamiento.pasos` («Recibir ACK de verificación; remitir paquete listo al humano»). Contraste: `circuitos-equipo.md`, «Handoffs», y `ciclo-revision.md`, «Decisiones y entregables».
- **Problema:** ACK admite estructura y versiones; no implica que el revisor haya terminado ni que haya resuelto hallazgos. La transición de la ficha no exige explícitamente el resultado sustantivo previsto por Revisión.
- **Ejemplo:** el revisor admite el candidato y luego emite `needs_evidence`. Si el Director usa el ACK inicial para avanzar, presenta como listo un texto aún no verificado.
- **Corrección propuesta:** exigir `review_record.status=ready_for_human` y `approval_package` referidos al mismo hash vigente antes de presentar como listo. Un ACK positivo solo habilita la revisión; otras respuestas conservan el bloqueo correspondiente.
- **Estado:** detectado abierto; corregido y revalidado documentalmente. Evidencia en la tabla de cierre.

### QA-C04 — P2: la clave editorial mezcla identidad del evento con identidad semántica del trabajo

- **Archivos/secciones:** fichas `equipos/editorial/{director_editorial,copywriter_a,copywriter_b}.json`, `iniciativa.clave_de_deduplicacion`. Contraste: `circuitos-equipo.md`, «Control de bucles, coste y estados».
- **Problema:** la clave editorial incluye `event_id`. La regla transversal exige deduplicar misma tarea, mismas entradas y mismo alcance, aunque lleguen por eventos diferentes. El texto general prohíbe duplicados, pero la clave concreta por sí sola no implementa esa regla.
- **Ejemplo:** una entrega provoca dos eventos distintos con IDs nuevos y las mismas entradas vigentes. Las claves editoriales difieren y se podría despachar dos veces el mismo encargo pagado.
- **Corrección propuesta:** separar deduplicación de transporte por `event_id` de deduplicación semántica por propietario, pieza/ciclo, rol, tarea, alcance y versiones pertinentes; un nuevo evento no basta para crear un nuevo trabajo. Mantener `event_id` como trazabilidad y exigir novedad material documentada para trabajo adicional.
- **Estado:** detectado abierto; corregido y revalidado documentalmente. Evidencia en la tabla de cierre.

### QA-C05 — P2: la propuesta orgánica no figura entre las entradas de Revisión

- **Archivos/secciones:** `ciclo-observatorio-aprendizaje.md`, «Ciclo A» y «Plan de experimento y retorno al equipo»; `ciclo-revision.md`, «Entradas y activación»; ficha `equipos/revision/editor_verificador.json`, entradas/eventos.
- **Problema:** Observatorio entrega `organic_participation_proposal` al verificador antes de Gustavo, pero Revisión declara activación solo para candidato editorial, perfil y corrección de evidencia. No explicita la admisión de esa propuesta ni el contexto de hilo que debe verificar.
- **Ejemplo:** el analista entrega un borrador de comentario contextual. Ningún evento admitido inicia la revisión, o se lo adapta como post perdiendo vínculo con el texto exacto al que responde.
- **Corrección propuesta:** declarar evento/entrada explícitos para la propuesta orgánica, contexto del hilo versionado, aporte, afirmaciones y permisos. Aplicar revisión y decisión humana sobre hash exacto; mantener el resultado como propuesta y la ejecución externa deshabilitada.
- **Estado:** detectado abierto; corregido y revalidado documentalmente. Evidencia en la tabla de cierre.

## Revalidación y cierre

| Hallazgo | Evidencia de corrección revisada | Resolución documental |
| --- | --- | --- |
| QA-C01 | `editorial_brief` incluye `selected_reader_ids`, `reader_priority` y `reader_selection_reason`; pasos del Director y ciclo editorial despachan y esperan solo el conjunto seleccionado | Corregido |
| QA-C02 | Contrato transversal de las 13 fichas y sección final del circuito global permiten verificar el candidato de ronda2, pero no otra edición tras fallo; ciclo de Revisión elimina la omisión posterior al agotamiento | Corregido |
| QA-C03 | Paso del Director y ciclo editorial exigen `review_record.status=ready_for_human` y `approval_package` sobre el mismo hash; ACK queda como admisión | Corregido |
| QA-C04 | Las 13 claves semánticas excluyen `event_id` como habilitador de trabajo; Observatorio conserva pregunta/entidad, alcance y ventana entre entradas pertinentes | Corregido |
| QA-C05 | Analista declara `organic_participation_proposed` con receptor verificador; ficha y ciclo de Revisión admiten propuesta, hilo versionado, fuentes y permisos; devolución al analista o paquete para Gustavo sin envío externo | Corregido |

La comprobación local acreditó que las 13 fichas revisadas son JSON parseables y contienen la directiva transversal. No se comprobó un esquema ejecutable, entrega de eventos, llamadas de modelos ni efectos reales. Los casos que originaron estos hallazgos deben conservarse en la evaluación de F3.

## Cobertura y límites

Se revisaron el contrato global, catálogo externo, contrato de observaciones, plan maestro, recorrido de mesa completo, los cinco ciclos y las fichas de los 13 roles. Se releyeron las correcciones finales del integrador y los handoffs afectados.

El diseño separa propuestas de aplicación real, observaciones de simulaciones y cálculos de interpretación. La alternativa textual o espera de un asset evita atribuir producción multimedia a un agente inexistente. Presupuesto sin configurar bloquea ejecución y una reserva incierta no habilita reintento automático. Estas son propiedades documentadas, aún sin verificación operativa.

Normalizar nombres de eventos, artefactos y campos, definir las políticas cuantitativas y comprobar transiciones, concurrencia y recuperación corresponde a F3 antes de activar. La lectura selectiva de unidades no acredita lectura integral de las clases01–06. No se considera defecto de este incremento que esas tareas técnicas sigan pendientes, siempre que no se declare autonomía implementada.
