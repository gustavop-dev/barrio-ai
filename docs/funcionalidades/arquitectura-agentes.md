# Arquitectura y grafo de agentes (`ARQ`)

Decisión acordada con Gustavo: **workflow determinista, un orquestador dueño de cada ciclo y especialistas llamados como herramientas**. El orquestador conserva el contexto y decide el siguiente paso; los especialistas devuelven resultados acotados. No hay traspaso de control entre agentes ni una red donde cualquiera llama a cualquiera. Una opinión o propuesta del especialista no es una aprobación de ejecución.

Antecedentes indicados por Gustavo: Anthropic, *Building effective agents* y su sistema de investigación multiagente; Cognition, *Don't build multi-agents* y *Multi-agents: what's actually working*; documentación multiagente de LangGraph; OpenAI Agents SDK, agents-as-tools frente a handoffs; Google ADK, coordinador con `sub_agents`/`AgentTool`; Microsoft Magentic-One, task/progress ledgers. Se recoge la decisión aportada, sin una nueva revisión web en esta tarea. No se elige ni se introduce uno de esos frameworks como dependencia.

**Fases 3a y 3b implementadas:** registro, mapa y control de runtime para pieza diaria y red. ARQ-02–06 funcionan en el alcance de la migración: dispatcher, contratos ejecutables, límites, ledgers, recuperación segura y actividad real. CI y QA quedan a cargo de Claude; no se ejecutaron suites locales.

Se conservan las llamadas agrupadas A/B y lectores, los prompts y la reparación histórica del director (máximo dos evaluaciones). Referentes mensuales, fan-out/gather, visual nuevo y Perfil periódico siguen `planned`; sus capacidades se implementan en las fases posteriores. Los caps futuros de 5 USD/mes y 10 USD/ciclo están declarados y no activan esos ciclos.


## Resumen

| ID | Función | Dónde | Estado |
| --- | --- | --- | --- |
| [ARQ-01](#arq-01) | Registro declarativo único de agentes, llamadas y ciclos | backend | funciona |
| [ARQ-02](#arq-02) | Orquestador por ciclo sobre el workflow actual | backend | funciona |
| [ARQ-03](#arq-03) | Bucles acotados de revisión e investigación | backend | funciona |
| [ARQ-04](#arq-04) | Ledgers persistidos y reanudación desde checkpoint | backend | funciona |
| [ARQ-05](#arq-05) | Límites por ciclo, gasto y trazabilidad | PWA · app · backend | funciona |
| [ARQ-06](#arq-06) | Validación del grafo y rechazo de llamadas no declaradas | backend | funciona |
| [ARQ-07](#arq-07) | Diagramas Mermaid generados y comprobados en CI | documentación · backend | funciona |
| [ARQ-08](#arq-08) | Mapa del equipo en PWA y app | PWA · app · backend | funciona |
| [ARQ-09](#arq-09) | Añadir un agente con contrato y evaluación | documentación · backend | funciona |

## Lo que existe y la migración inicial <a id="migracion"></a>

Base local `1ba4e43`; no se inspeccionaron secretos ni configuración desplegada. [Mapa de runtime](../../agentes-linkedin/infra/docs/mapa-agentes-runtime.md), `autopiloto.py`, `jobs.py`, `editorial.py`, `operador.py`, `red.py`, `lider.py`, `evaluaciones.py` y `knowledge/retrieval.py` sustentan esta comparación.

| Hoy | Primer registro: describir y envolver lo existente | Después: capacidad nueva |
| --- | --- | --- |
| `autopiloto.tick` decide cadencias; jobs con ids deterministas y carriles `general`/`acciones`; `execute_action` y `reconcile_action` van al de acciones | Declarar triggers, bindings y políticas efectivas de esos trabajos. Mantener las colas y controles; no reemplazar el scheduler por un LLM | Un orquestador coordina cada instancia con llamadas limitadas y checkpoint. |
| `editorial._run`: director, una llamada que devuelve A/B, una llamada que reúne cinco lectores, selección, reglas, verificador y como máximo una reparación a cargo del director | Declarar llamadas agrupadas tal como existen y sus schemas; no afirmar dos copywriters independientes ni cinco llamadas separadas. Conservar la reparación actual | Adaptar la reparación a copywriters como herramientas del director dentro del bucle declarado ARQ-03, con evaluación de paridad antes de cambiar el binding. |
| Red: descubrimiento/clasificación y plan determinista; comentarios por `propose_comment`; inbox de lectura y evaluación tipada | Agrupar sus entradas bajo Relaciones como propietario de ciclo, manteniendo los subtriggers, topes y salidas actuales | Relaciones decide prioridades con el contexto reunido, sin reimplementar cálculos ni asumir envío de inbox. |
| Referentes definidos por Gustavo; `observe` lee su contenido | Declarar la lectura actual como servicio/herramienta de la red, con procedencia y sin alta/baja automática | Ciclo mensual a cargo de `investigador_lider`, con especialistas, gather y propuestas OBS. |
| `perfil` y `posicionamiento` son consultas manuales de `knowledge/agents.py`; resultados sin consumidor automático | Declarar el trigger manual y sus salidas reales, no una cadencia ya operativa | `perfil` coordina Estrategia y perfil, con posicionamiento/visual como herramientas, ciclos semestral/mensual y petición desde captura EST-05; entrega assets, previews, Markdown fundamentado y checklist. |
| Métricas deterministas y resumen semanal del analista; contratos JSON no leídos en runtime | Registrar servicios y entrada del analista, unidades curadas y entregas; el director es dueño del ciclo de aprendizaje de contenido | Estudio comunitario y evidencia por referente se añaden como contratos de salida nuevos del analista. |
| Captura enruta una nota y guarda medios; los eventos la atribuyen a Operación | Representar el binding actual con su etiqueta histórica, sin inventar una consulta al curso; su salida es un insumo para otro ciclo, no una llamada entre especialistas | Si se separa un nodo `ruteador_capturas`, declara especialidad, herramientas y `course_units: []` con motivo. No depende de BIB-06, retirada. |
| Hay uso/costes, auditoría y estados de jobs/piezas, pero no task/progress ledgers por ciclo; worker perdido queda interrumpido, no se repite ciegamente | Conservar esos registros y asociarlos a la instancia migrada; no afirmar reanudación que todavía falta | Checkpoints y conciliación ARQ-04 sin repetir gasto ni escrituras inciertas. |

La migración primero pasa pruebas de paridad con los adaptadores actuales. Nodos nuevos permanecen `planned`, dentro de ciclos declarados pero inactivos, hasta disponer de schemas, binding y evaluación. Un registro parcial no se anuncia como el grafo completo activo; la activación final no deja rutas de negocio fuera del control del grafo. Los contratos JSON pueden seguir dando detalle documental, pero identidad, herramientas, listas de unidades, modelo, límites y aristas efectivas salen del registro, sin configuraciones paralelas contradictorias.

## Ciclos y dueños <a id="ciclos"></a>

| Ciclo / trigger | Orquestador único | Herramientas/especialistas consultables | Decisión y salida |
| --- | --- | --- | --- |
| Contenido / hueco diario o preparación manual | `director_editorial` | Copywriters, lectores, investigador, analista y, cuando exista, `editor_visual` | Decide brief, texto y recurso visual. El visual propone; el director acepta, pide una corrección dentro del límite o bloquea. Después pasan las compuertas; no publica el director. |
| Red / subtriggers actuales de observar, descubrir, clasificar, planificar, sincronizar, comentar e inbox | `relaciones_comunidad` | `investigador_referentes`, `conversaciones_inbox`, `analista_barrio_resultados` y servicios de lectura | Decide prioridades/plan con todos los resultados pertinentes; el planificador aplica BIB-08 y Operación ejecuta. Cada subtrigger tiene clave de instancia; no arranca todo el ciclo cada vez ni duplica los barridos actuales. |
| Referentes / lote día 1, recordatorios 1/4 y cierre tras día 5 en America/Bogota | `investigador_lider` (nuevo coordinador, nombre de interfaz «Investigador líder») | Instancias acotadas de `investigador_referentes` y `analista_barrio_resultados` | Sintetiza evidencia y propone solo para diez plazas variables. Main intocables para agentes/jobs; solo Gustavo los gestiona según OBS-02. Altas/bajas/swaps variables pasan decisión humana o vencimiento autorizado. Experimentos requieren aprobación positiva. No es el líder/Jev. |
| Perfil / cada seis meses, revisión mensual y bajo demanda explícita desde captura [EST-05](estrategia-perfil.md#est-05) | `perfil` (coordinador de Estrategia y perfil, sin otro manager duplicado) | `posicionamiento`, investigador, analista y visual | Decide propuesta por sección; entrega assets/previews, Markdown con citas y checklist de la misma versión. Solo fotos de categoría Perfil. No existe salida ejecutable de modificación del perfil en LinkedIn. |
| Aprendizaje de contenido / métricas según edad y resumen semanal; estudio mensual al habilitarse | `director_editorial` | `analista_barrio_resultados` y servicios deterministas de métricas | Encarga y recibe los informes; conserva el informe original del analista, aplica solo recomendaciones dentro de su autoridad y entrega cambios de orientación a Gustavo. No dispara una publicación por cada medición. |

Un especialista compartido puede servir a varios ciclos, siempre con contexto y `cycle_id` separados. El orquestador es único por **instancia**, no un único proceso global; solo una escritura de progreso puede avanzar una instancia a la vez. El investigador líder no es un jefe de los demás ciclos. Intercambios entre ciclos se hacen con artefactos versionados y triggers declarados del workflow, no llamadas de un especialista a otro ni un orquestador subordinado oculto.

El trigger futuro de captura «hazme la propuesta del perfil» se declara con origen/id de captura, alcance completo y correlación/idempotencia; el workflow inicia o reúne la solicitud en la instancia de Perfil. No añade biblioteca al ruteador ni evita ledgers, límites o gates por ser manual. Los schemas de respuesta de Perfil incluyen Markdown, A/B sin elección automática, banner, origen/categoría/permiso y roles de referencias 01–03, previews por variante, citas, ocho puntos/visión contra 03, nota de composición estilizada y estado por sección. El registro enlaza schemas, no fotos; cada ejecución conserva referencias/medios en almacenamiento privado y la auditoría solo ids/metadatos. Ninguna imagen se incorpora al repo. Backend impide que originales/derivados de Perfil lleguen al ciclo de posts. La migración inicial declara solo salidas existentes antes de habilitar este contrato ampliado.

### ARQ-01 · Registro declarativo único de agentes, llamadas y ciclos <a id="arq-01"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Alcance 3a:** Inventario activo/planned, schemas reales (JSON o contrato Python indicado), presupuesto referenciado y listas curadas contrastadas en tests. No cambia bindings ni llamadas actuales.
- **Qué hace para Gustavo:** todas las relaciones y responsabilidades del equipo se pueden consultar en un solo lugar y una integración nueva debe declarar cómo encaja.
- **Responsable:** cada orquestador responde de su ciclo; el workflow determinista valida y hace cumplir el registro. Los agentes no editan su propia definición.
- **Cadencia:** validación al cambiar el registro y al arrancar; fijar versión/hash al crear una instancia.
- **Tu turno:** ninguna aprobación por cargar el registro. Cambios de autoridad, orientación, recursos o gasto que requieran a Gustavo siguen sus fichas; una descripción no concede permisos.
- **Datos necesarios y disponibilidad:** ids/grupos, prompts, schemas y configuración están hoy repartidos entre contratos, Python y escena. Falta registro canónico, resolutor de referencias y manifiesto efectivo versionado.
- **Código:** Registro descriptivo canónico en `agentes-linkedin/equipos/grafo.yaml`, cargado por `team_backend/grafo.py`. El dispatcher de `team_backend/orquestacion.py` autoriza las aristas con `runtime`; fija registro, código de contratos y overrides no secretos al abrir la instancia.
- **Contenido obligatorio del registro:**

  | Sección | Campos y significado |
  | --- | --- |
  | Cabecera | `schema_version`, `graph_version`, identificadores estables; hash calculado del registro y referencias resueltas. Sin credenciales ni prompts con datos privados. |
  | `agents` (nodos) | `id`, `group`, `role` (`orchestrator`, `specialist`, `gate`, `executor`), `description` de utilidad/alcance, `capabilities` o `skills`, nombres/versiones de schemas de entrada/salida, herramientas permitidas (`web_search`, `web_fetch`, biblioteca, Unipile de lectura...), lista curada `course_units` o referencia expandible, modelo y `effort`, presupuesto y binding al handler; estado `planned/enabled`. Servicios/gates humanos o deterministas llevan modelo/effort `null` y motivo. |
  | `edges` (solicitudes permitidas) | `id`, `from`, `to`, ciclos permitidos, `request_kind`, schemas versionados de petición/respuesta, `max_calls_per_cycle`, `response_required`. Una llamada agrupada declara sus participantes y handler real; no finge llamadas que hoy no existen. |
  | `cycles` | `id`, orquestador, cadencia, trigger y clave de deduplicación, participantes, bindings de pasos deterministas, aristas, bucles, gates, schemas del ledger/checkpoints y límites; estado activo/planificado. Los servicios de infraestructura no se disfrazan de agentes. |
  | `gates` | Tipos de salida ejecutable, controles obligatorios, orden/dependencias y condiciones deterministas de aplicación, revisión/versión/hash requerido, quién puede liberar y ruta al único ejecutor. El veto no equivale a una aprobación positiva de cada post. |
  | Referencias compartidas | Catálogo de schemas, listas de curso BIB, herramientas y políticas con versión; expansión única para runtime, validación y vistas. Una variable de entorno permitida se declara aquí y se muestra resuelta sin secretos, no constituye un segundo grafo oculto. |

- **Criterios de aceptación:**
  1. **Dado** un registro válido, **cuando** arranca el sistema, **entonces** resuelve nodos, schemas, políticas y bindings a un manifiesto efectivo con versión/hash, usado tanto para ejecutar como para generar diagramas y servir el Mapa del equipo.
  2. **Dado** campos ausentes, ids duplicados, schema inexistente, herramienta no permitida o presupuesto sin resolver, **cuando** se valida, **entonces** falla con nodo/arista y causa; no ejecuta con defaults ilimitados ni un grafo alternativo incrustado en código.
  3. **Dado** un nodo planificado sin binding, **cuando** se consulta, **entonces** aparece «En diseño» y no acepta invocaciones. Un nodo activo requiere binding, schemas, evaluación y alcance de herramientas comprobados.
  4. **Dado** cambio de registro con un ciclo abierto, **cuando** continúa, **entonces** usa su versión fijada o queda detenido para migración explícita del checkpoint; no cambia de modelo, autoridad o estructura a mitad del ciclo sin dejar registro.
  5. **Dado** listas/documentos de rol duplicados, **cuando** se construye el manifiesto, **entonces** la identidad, herramientas, unidades, modelo y presupuesto efectivos proceden del registro; una discrepancia de un contrato secundario falla validación o se genera desde él, no se decide por azar qué copia manda.
- **Brechas código/docs:** los JSON de equipos son contratos no ejecutables; actualmente el runtime usa prompts y llamadas Python, y la escena mantiene otro mapa. El registro gobierna las aristas marcadas con runtime de pieza/red; los demás ciclos siguen descriptivos.
- **Cobertura QA:** `test_grafo.py` y/o comprobación de diagrama en CI; ejecución de suites pendiente por Claude.


### ARQ-02 · Orquestador por ciclo sobre el workflow actual <a id="arq-02"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** cada ciclo tiene alguien que reúne el contexto, decide los pasos y responde de su resultado, manteniendo horarios y controles estables.
- **Responsable:** los cuatro dueños de la [tabla de ciclos](#ciclos); `operador_cuenta` es el único ejecutor de escrituras en LinkedIn.
- **Cadencia:** por trigger declarado, sobre `autopiloto` y carriles actuales; los intervalos vigentes se migran explícitamente antes de añadir cadencias nuevas.
- **Tu turno:** decisiones humanas existentes y escalados concretos por bloqueo ARQ-04. No se pide aprobar cada consulta, borrador o post autónomo; el cambio de arquitectura no amplía autonomía.
- **Datos necesarios y disponibilidad:** trabajos, propuestas, memoria y compuertas existentes se enlazan ahora a CycleLedger y al dispatcher de pieza/red. Los especialistas solo reciben el subconjunto necesario, no toda la memoria privada.
- **Código:** `orquestacion.py`, `editorial.py` y `operador.run_job` coordinan las dos rutas migradas. Referencias: `autopiloto.tick/policy_review`, `jobs.enqueue_operation/lane_jobs`, `editorial._run`, `red.plan`, `operador.execute`.
- **Matriz mínima de compuertas:**

  | Salida | Camino obligatorio declarado antes de su efecto |
  | --- | --- |
  | Post CONT-09 | Reglas deterministas → verificador sobre texto/paquete vigente → política/líder-Jev cuando la configuración aplicable lo exige → comprobación de veto, versión y programación → Operación con pausas, cuenta, ventana, espaciado, cupos e idempotencia. Con imágenes, incorporar gates IMG sin duplicarlos. |
  | Comentario INT-03 / reacción INT-02 ya habilitada | Reglas y política vigentes por capacidad; líder/Jev según alcance configurado; veto/hash y precontroles de Operación. No inventar que hoy el verificador editorial revisa comentarios ni que existen propuestas automáticas de reacciones. |
  | Red RED-01/02/04 | Encaje/evidencia y reglas deterministas de red; días, cupos y reparto BIB-08 para RED-02; líder sobre riesgo cuando corresponde; veto/hash y Operación con relectura previa. |
  | Altas/bajas/swaps de referentes variables | Revisión de evidencia/versión, conjunto main vigente protegido, máximo diez variables/15 totales y decisión humana **o mandato de vencimiento OBS-02**: lote día 1, sin respuesta al finalizar día 5 America/Bogota. Aplicación transaccional por backend, no escritura LinkedIn. Solo ese gate admite este vencimiento, nunca una rama especialista. |
  | Mover/reemplazar/proteger/desproteger main | Exclusivamente acción explícita de Gustavo autenticado desde Personas › Referentes o Tu turno; autoridad comprobada por backend, capacidad/versiones y auditoría de actor/antes/después OBS-02. Ninguna arista otorga a un agente proponer o ejecutar estos cambios; no hay mandato por plazo. |
  | Invitación con nota excepcional o fallback sin nota | Relaciones justifica encaje y curso; verificador/líder revisan texto inglés, y se conservan autonomía/veto y Operación. BAR-16 valida tier, reservas y rechazo inequívoco de cuota de notas antes del fallback; BAR-15 mantiene rampa/caps. El resultado ambiguo requiere conciliación, no otro envío. |
  | Experimento | Aprobación positiva de Gustavo en TUR-21; el silencio no lo inicia. Mantiene cupos, calidad, presupuesto y ritmo BAR-15. |
  | Cualquier texto público | Verificador/líder comprueban inglés, fundamento y honestidad antes de ejecutar. Incluye comentarios, posts, artículos, textos de imágenes/perfil y prueba social; no inventar charlas por un micrófono de estilo. Los textos internos pueden seguir en español. |
  | Orientación o perfil | Orientación solo se adopta tras decisión humana. Perfil termina en checklist TUR-18 y aplicación externa de Gustavo; no existe arista de escritura de perfil a Operación. |

La migración muestra las condiciones actuales (`LEAD_ENABLED`, capacidad, modo de autonomía) y cualquier gate no aplicable con motivo. No se anuncia que Jev ejecutó una revisión si estaba apagado. Una vez declaradas las condiciones, un orquestador no puede saltarlas ni modificar umbrales; cualquier cambio es política versionada, no una decisión del modelo.

- **Criterios de aceptación:**
  1. **Dado** un trigger, **cuando** se crea la instancia, **entonces** se asignan un solo orquestador y clave estable, se reúne contexto de tarea/hechos/artefactos y se conserva el plan; duplicar el trigger no duplica la instancia ni cambia su dueño.
  2. **Dado** una necesidad de investigación, análisis, imagen u opiniones, **cuando** el orquestador invoca una herramienta, **entonces** valida la arista y schemas, entrega un objetivo acotado y recibe un resultado sin ceder el control. Especialistas no invocan agentes, ni siquiera otro especialista u orquestador; las herramientas primitivas de lectura autorizadas no son delegación.
  3. **Dado** la propuesta de un visual, lector o investigador, **cuando** llega, **entonces** el dueño del ciclo decide usarla, pedir revisión dentro del presupuesto o descartarla y registra el motivo. El visual no cambia por sí solo el formato/medio final del post ni el lector selecciona el ganador.
  4. **Dado** una salida ejecutable, **cuando** se intenta aplicar, **entonces** atraviesa todos los gates declarados para su tipo/versionado. Ningún especialista, orquestador, prompt o llamada directa al conector puede escribir LinkedIn; una instrucción del modelo de omitir el verificador falla antes del envío.
  5. **Dado** la migración de un pipeline existente, **cuando** se prueba con simulaciones, **entonces** conserva triggers, carriles, handlers agrupados, guardas y decisiones efectivas de la base, mostrando cualquier cambio posterior por separado. Los nodos nuevos no se activan por cargar su descripción.
- **Brechas código/docs:** 3b migra pieza/red sin reescribir los servicios deterministas como LLM; los nuevos ciclos se activarán en sus fases.
- **Cobertura QA:** `test_orquestacion.py` más las regresiones existentes de editorial, red, imágenes, Jev, worker y grafo; ejecución por Claude.

### ARQ-03 · Bucles acotados de revisión e investigación <a id="arq-03"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Alcance 3b:** bucles existentes acotados y persistidos. El fan-out de referentes permanece planificado hasta la fase 5; no se habilita por esta entrega.
- **Qué hace para Gustavo:** el equipo puede corregir un borrador o investigar varios frentes sin encadenar agentes indefinidamente.
- **Responsable:** director para evaluación/corrección; investigador líder para exploración paralela. El workflow ejecuta el bucle y reúne las respuestas.
- **Cadencia:** solo dentro de ciclos/loops explícitos del registro; contadores persisten al reanudar.
- **Tu turno:** solo si el límite deja una decisión o dato que requiere a Gustavo; un borrador que sigue fallando puede cerrarse bloqueado sin pedirle aprobar un texto defectuoso.
- **Datos necesarios y disponibilidad:** verificador y una reparación editorial existen; no hay fan-out/gather ni bucles declarados. Web es dependencia de investigación; `feat/imagenes-backend` conserva sus verificaciones visuales, no crea una excepción a la profundidad.
- **Código:** `Runtime.call` aplica los contadores de las aristas y las llamadas agrupadas. Referencias: `editorial._check/_repair_round`, `evaluaciones.gate`, `jobs.py`.
- **Criterios de aceptación:**
  1. **Dado** un borrador con hallazgos corregibles, **cuando** entra al bucle evaluator-optimizer, **entonces** el director recibe los hallazgos, encarga corrección y vuelve a verificar el texto exacto. Se permiten **como máximo dos rondas de evaluación: inicial y una tras corrección**; no dos reparaciones además de la inicial. Esto conserva el máximo observable actual de una reparación.
  2. **Dado** la adaptación a copywriters ⇄ verificador, **cuando** se ejecuta, **entonces** las flechas representan pasos del bucle controlados por director/workflow, no llamadas directas entre ellos. En la primera migración se declara que la reparación la hace el director; el cambio a herramienta copywriter requiere binding y evaluación propios, sin alterar el límite.
  3. **Dado** mismo texto devuelto, fallo persistente o presupuesto agotado en la segunda ronda, **cuando** termina, **entonces** registra falta de progreso y cierra bloqueado/descartado con el motivo. No crea otra instancia para reiniciar el contador ni modifica criterios para lograr un aprobado.
  4. **Dado** una investigación mensual amplia, **cuando** el investigador líder divide el trabajo, **entonces** fija por subinvestigador objetivo/tema no duplicado, contexto mínimo, fuentes permitidas, schema de salida, citas, máximo de lecturas/llamadas, coste y deadline. Solo el líder lanza las ramas y recibe sus resultados; no hay subdelegación.
  5. **Dado** varias ramas, **cuando** termina el gather, **entonces** espera todas las requeridas hasta su timeout, valida schemas, deduplica candidatos/fuentes, preserva desacuerdos y distingue fallo de «sin hallazgos». Un resultado parcial se marca como tal; el líder sintetiza antes de proponer, y ninguna rama activa referentes.
  6. **Dado** una solicitud de un tercer ciclo de corrección, fan-out fuera de un loop o anidación de investigadores, **cuando** llega al dispatcher, **entonces** se rechaza y audita. Un loop declarado solo autoriza sus pasos acotados, no una excepción general de llamadas entre especialistas.
- **Brechas código/docs:** A/B y cinco lectores hoy son llamadas agrupadas; no se debe introducir fan-out para ellos solo porque la oficina dibuje varios personajes. El paralelo autorizado de esta decisión es para amplitud de investigación y gather explícito.
- **Cobertura QA:** `test_orquestacion.py` más las regresiones existentes de editorial, red, imágenes, Jev, worker y grafo; ejecución por Claude.

### ARQ-04 · Ledgers persistidos y reanudación desde checkpoint <a id="arq-04"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** un ciclo recuerda qué sabe, qué falta y qué ya hizo; tras una interrupción continúa desde un punto seguro y explica cuándo necesita su intervención.
- **Responsable:** orquestador de la instancia; el backend persiste/coordina cambios de estado. Operación concilia posibles escrituras.
- **Cadencia:** checkpoint antes de lanzar llamadas con efecto/coste y al registrar cada resultado; revisión de progreso después de cada paso o gather.
- **Tu turno:** tarjeta deduplicada por bloqueo con pregunta/decisión concreta, evidencia, progreso y opciones. No responder mantiene el ciclo esperando, sin gastar ni aprobar cambios. Los fallos operativos temporales usan reintentos limitados, no preguntas humanas sin utilidad.
- **Datos necesarios y disponibilidad:** `Job`, `EditorialPiece` por etapas, `ActionProposal/Execution`, `AuditEvent` y `usage_ledger` se conservan; CycleLedger añade identidad/checkpoints y detección de atasco para pieza/red.
- **Código:** `CycleLedger` (migración 0021), `Runtime` y `jobs.reconcile_interrupted`. Referencias: `jobs.reconcile_interrupted`, `editorial.recover_stuck`, `operador.reconcile/resolve_uncertain`, `models.py`.
- **Contrato persistido:** `task_ledger` guarda objetivo, hechos y sus fuentes, supuestos, incógnitas, restricciones, plan versionado, criterio de fin y dueño; nunca razonamiento privado del modelo. `progress_ledger` guarda paso/petición, destinatario/arista, ids de llamadas, estado pedido/respondido/pendiente/fallido, referencias a resultados, contadores, `stall_count`, siguiente paso, decisiones y checkpoints. Ambos incluyen `cycle_id`, versión/hash del grafo, de políticas/contexto, timestamps y control de concurrencia.
- **Criterios de aceptación:**
  1. **Dado** un paso completado y el siguiente pendiente, **cuando** el worker cae y vuelve, **entonces** recupera la misma instancia/checkpoint, reutiliza resultados validados ya persistidos y continúa el paso pendiente; no vuelve a pagar pasos completos ni reinicia el plan desde cero.
  2. **Dado** una llamada pagada en vuelo sin resultado confirmado, **cuando** reanuda, **entonces** conserva la reserva incierta y concilia el proveedor si es posible; si no puede saber el resultado, registra esa incertidumbre y aplica política acotada/escalado antes de otro intento. Una posible escritura LinkedIn siempre se concilia mediante Operación y nunca se repite ciegamente.
  3. **Dado** dos intentos consecutivos sin nueva evidencia, avance de estado ni resolución de hallazgos, **cuando** crece `stall_count`, **entonces** permite como máximo un replanteamiento dentro del presupuesto restante, con motivo y plan nuevo; si sigue atascado, bloquea y escala a Tu turno solo lo que Gustavo puede resolver. Son defaults de diseño, no instrucciones atribuidas a Magentic-One.
  4. **Dado** pausa humana, gate fallido o respuesta requerida pendiente, **cuando** evalúa avance, **entonces** distingue espera legítima de atasco y no consume reintentos ni inventa respuestas. El timeout técnico no implica aprobación; el cierre de negocio OBS-02 es un mandato distinto ya autorizado, con condiciones propias y marca `aplicada_por_plazo`, no una respuesta humana supuesta.
  5. **Dado** actualización concurrente, checkpoint incompatible o resultado de una rama vieja, **cuando** se intenta avanzar, **entonces** la versión/lease evita dos dueños, rechaza o aparta el resultado obsoleto y no salta gates. La reanudación conserva presupuestos, profundidad y número de rondas consumidos.
  6. **Dado** una respuesta de Gustavo al bloqueo, **cuando** se registra, **entonces** versiona la decisión y reanuda el mismo ciclo si sigue siendo válido; si requiere un ciclo nuevo, enlaza el anterior y mantiene sus gastos/decisiones sin borrarlos.
- **Brechas código/docs:** el ledger de 3b conserva checkpoints y contadores. Las llamadas sin respuesta confirmada requieren conciliación; no se ofrece replay ciego.
- **Cobertura QA:** `test_orquestacion.py` más las regresiones existentes de editorial, red, imágenes, Jev, worker y grafo; ejecución por Claude.

### ARQ-05 · Límites por ciclo, gasto y trazabilidad <a id="arq-05"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** sabe qué recursos consume cada ciclo y qué límite lo detuvo, sin que reintentos o investigadores paralelos multipliquen el gasto ocultamente.
- **Responsable:** cada orquestador distribuye su presupuesto; el backend y los proveedores aplican reservas, timeouts y auditoría; Operación conserva cupos de LinkedIn.
- **Cadencia:** validar antes de cada solicitud y liquidar al terminar; actualizar progreso visible con la actividad habitual de la Oficina.
- **Tu turno:** los importes del quinto addendum ya están fijados: al alcanzar el cap **parar y avisar**, sin pedir su aprobación otra vez ni elevarlo. El aviso enlaza avance, gasto y faltantes; cambios posteriores de importe sí requieren instrucción explícita.
- **Datos necesarios y disponibilidad:** el ledger de proveedores conserva gastos históricos; el runtime añade agregación por instancia/arista, profundidad y deadlines para las rutas migradas.
- **Código:** `Runtime`, `knowledge/cycle_context.py` y reservas serializadas de `knowledge/providers.py`. Referencias: `knowledge/providers.py`, `jobs.py`, `operador.py`, `oficina_views.py`, `oficina_eventos.py`.
- **Campos exigidos:** profundidad máxima `1` (orquestador → especialista, sin delegación de este), `max_calls` total, límites por arista, límites por herramienta/proveedor, `cost_cap_usd`, `call_timeout_s`, `cycle_timeout_s`, `max_replans`, `max_stalls` y, si aplica, `max_parallel_branches`. Toda configuración activa debe resolver a números finitos positivos o cero para desactivar; no se hereda un infinito implícito. Las unidades de tiempo distinguen trabajo activo de espera humana persistida.
- **Cómputo:** totalizar llamadas de orquestación a modelo, especialistas, Jev, herramientas y reintentos, con desglose; las invocaciones internas pagadas cuentan aunque el adapter agrupe A/B o lectores. Límites de arista cuentan solicitudes al destinatario y límites de proveedor cuentan llamadas reales. Reservar coste antes del fan-out y repartirlo entre ramas; el efectivo es el mínimo de ciclo, rol, proveedor y topes existentes. No sumar dos veces una reserva al liquidarla; mantener inciertos. Gate/servicio sin LLM registra coste de modelo cero y sus lecturas/ejecuciones como operaciones.
- **Importes vinculantes:** todo cabe en el presupuesto general de IA del equipo (`knowledge/presupuesto.py`, desde el 10/11/2026 por instrucción de Gustavo): `AI_MONTHLY_LIMIT_USD` (100 USD por mes calendario, todos los proveedores y áreas) y `AI_DAILY_FUSE_USD` (15 USD, tope de seguridad diario contra gastos desbocados). Dentro de él, pieza diaria **8 USD por ciclo** (antes 2 USD; tope por reservas contra desbocados que cabe en una pieza con imágenes), sin tope diario propio del circuito; referentes **5 USD por mes natural** America/Bogota, compartidos entre revisión, ramas, reintentos y solicitudes adicionales del mismo mes; Perfil **10 USD por ciclo**, incluida propuesta completa con A/B/banner y revisiones/reanudaciones del mismo encargo. El mensual de Perfil también tiene techo 10, sin obligación de gastarlo. Incluyen modelo, visión, imagen y herramientas facturables del ciclo; no son solo tokens de texto. El registro contiene estos caps y agregación; ya no hay topes diarios por área.
- **Defaults técnicos resueltos:** referentes 40 llamadas/20 min activos; perfil completo 60/30 min; perfil mensual y estudio comunitario 20/10 min; pieza conserva carril y dos rondas de evaluación. Timeout 120 s por llamada o 300 s para edición de imagen, siempre dentro del plazo del ciclo; máximo tres ramas de investigación y un replanteamiento tras dos intentos sin avance. Estudio comunitario conserva default 1 USD/ciclo dentro del presupuesto existente. Son configuración operativa del diseño, no nuevas preguntas de producto ni razones para aumentar los importes decididos.
- **Criterios de aceptación:**
  1. **Dado** un fixture con máximo 20 llamadas, 19 usadas y dos ramas listas, **cuando** ambas intentan reservar, **entonces** solo una obtiene la última llamada. Con tope de 1 USD, 0,80 USD consumidos/reservados y dos peticiones de 0,15 USD, solo cabe una; se rechaza la otra antes del proveedor y queda motivo en progreso/auditoría. Estos números son de prueba, no presupuestos desplegados.
  2. **Dado** especialista que intenta delegar o acceso directo a un proveedor no declarado, **cuando** se despacha, **entonces** se rechaza aunque quede presupuesto. Usar `web_fetch` autorizado es una lectura con cupo, no permiso para lanzar otro agente.
  3. **Dado** timeout de llamada/ciclo, **cuando** vence, **entonces** detiene nuevas solicitudes, cancela lecturas seguras si se puede y registra resultados parciales/posibles costes; un resultado tardío no se aplica a otro plan. Las escrituras inciertas van a conciliación, no a reenvío.
  4. **Dado** pausa/reanudación, **cuando** vuelve al checkpoint, **entonces** conserva saldo consumido/reservado, intentos y rondas; las esperas humanas no mantienen workers bloqueados ni permiten reiniciar gratis un ciclo.
  5. **Dado** cualquier solicitud, **cuando** se registra, **entonces** enlaza `cycle_id`, job, nodo, arista, versión, request/result, propósito, modelo/effort, duración, coste/reserva, citas y decisión del gate en usage ledger y auditoría; operaciones sin coste de modelo registran cero y su consumo de operaciones, sin duplicar cargos. No se exponen secretos ni mensajes privados en eventos públicos.
  6. **Dado** el panel de actividad, **cuando** Gustavo consulta un ciclo, **entonces** ve dueño, fase, llamadas usadas/máximo, gasto confirmado/reservado/tope, timeout o bloqueo y siguiente paso; sin datos muestra «Actividad no disponible», no trabajo simulado.
  7. **Dado** el cap de 8 USD por ciclo de pieza, 5 USD del mes de referentes o 10 USD del ciclo de Perfil, **cuando** liquida consumo que lo alcanza o intenta reservar una llamada que lo excedería, **entonces** detiene nuevas llamadas antes del proveedor y emite un aviso deduplicado con progreso/coste/motivo, aunque nadie intente otro paso. Reintentar, cambiar nodo o crear otra revisión del mismo encargo no reinicia el gasto; una entrega A/B incompleta se informa parcial, sin eliminar una opción para declararla completa.
- **Brechas código/docs:** las rutas migradas agregan reservas/gasto por ciclo y avisan al tope. Los ciclos futuros mantienen su activación pendiente; Claude debe comprobar las tarifas y reservas existentes sin aumentar caps automáticamente.
- **Cobertura QA:** `test_orquestacion.py` más las regresiones existentes de editorial, red, imágenes, Jev, worker y grafo; ejecución por Claude.

### ARQ-06 · Validación del grafo y rechazo de llamadas no declaradas <a id="arq-06"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Alcance 3b:** añade rechazo auditado de aristas/proveedores, profundidad, contratos y caps en las dos rutas migradas. Las rutas heredadas de otros ciclos siguen descriptivas.
- **Qué hace para Gustavo:** el mapa describe lo que el sistema puede hacer de verdad; un agente nuevo no adquiere accesos o rutas de ejecución por accidente.
- **Responsable:** workflow/dispatcher determinista; cada orquestador solo solicita operaciones que el registro autoriza.
- **Cadencia:** validación estática en CI y arranque; validación de petición/respuesta, permisos, gates y límites en cada llamada.
- **Tu turno:** ninguna aprobación de pruebas. Un rechazo no pide a Gustavo aprobar una llamada oculta; se corrige el contrato o se cierra el ciclo con la limitación.
- **Datos necesarios y disponibilidad:** validador del registro de 3a, contratos ejecutables y pruebas instrumentadas/negativas del dispatcher en 3b.
- **Código:** `team_backend/grafo.py` y `tests/test_grafo.py`: validación estructural, rutas de gates y deriva de listas/kinds/JOB_ROLES. El rechazo en runtime está en `orquestacion.py`, con pruebas negativas e instrumentación de reservas.
- **Criterios de aceptación:**
  1. **Dado** el registro, **cuando** se valida, **entonces** todo nodo es alcanzable desde al menos un ciclo declarado, todo ciclo tiene exactamente un orquestador y referencias existentes, y nodos/aristas/ciclos tienen ids únicos. Los planificados son alcanzables desde ciclos planificados inactivos; nunca quedan activos sin ruta real.
  2. **Dado** una arista entre especialistas, un especialista que llama a un orquestador o una cadena de delegación de profundidad mayor de uno, **cuando** pasa validación o runtime, **entonces** falla. Los bucles solo permiten los pasos enumerados de ARQ-03 bajo el dueño del ciclo; no habilitan una red de pares.
  3. **Dado** una arista, **cuando** se valida/invoca, **entonces** existen y se cumplen schemas de request/response versionados, tipo de solicitud, pertenencia al ciclo, máximos y respuesta requerida. Una respuesta opcional tiene schema de acuse/estado y política explícita; ningún gate o insumo obligatorio se trata como opcional.
  4. **Dado** cada salida con efecto, **cuando** se analizan sus rutas, **entonces** ninguna omite gates/hash/ejecutor. Tests negativos intentan publicar sin revisión, saltar veto, tocar main desde un agente/job, aplicar referente antes del plazo sin decisión, aplicar versión modificada y escribir perfil: fallan antes del efecto. Un caso positivo aplica solo un variable del lote vigente sin respuesta al cierre OBS-02; el mismo vencimiento nunca autoriza un experimento. Otro caso permite a Gustavo autenticado reemplazar un main y audita la transferencia de protección; el payload que suplanta su actor desde un agente falla. BAR-16 prueba el fallback tras rechazo de nota y bloquea el reenvío tras respuesta ambigua o límite general.
  5. **Dado** una llamada escrita directamente en código que no pasa por el dispatcher, **cuando** se ejecutan tests, **entonces** falla la regla de arquitectura que prohíbe accesos directos a agentes/proveedores/conectores fuera de adapters permitidos; pruebas instrumentadas del pipeline comparan cada llamada real con su arista. No basta contar nodos en YAML ni usar solo búsqueda textual de nombres.
  6. **Dado** una petición no declarada en el código o generada por un modelo, **cuando** llega a runtime, **entonces** falla cerrada con id del llamante/destinatario y motivo auditable; no hay fallback a invocación libre. Una respuesta inválida no avanza el ledger ni libera un gate.
  7. **Dado** un cambio de registro, **cuando** corre CI, **entonces** valida también unidades conocidas dentro de 01–06, tools/scopes, modelos/effort, budgets finitos, evaluación mínima por nodo y paridad de diagramas; un fallo impide dar el cambio por integrable.
- **Brechas código/docs:** ninguna prueba actual hace cumplir este grafo; la migración debe cubrir también rutas manuales y de reintento, no solo el camino feliz del autopiloto.
- **Cobertura QA:** `test_grafo.py` y/o comprobación de diagrama en CI; ejecución de suites pendiente por Claude.


### ARQ-07 · Diagramas Mermaid generados y comprobados en CI <a id="arq-07"></a>

- **Dónde:** documentación · backend
- **Estado:** funciona
- **Alcance 3a:** Diagrama completo y uno por ciclo, versión/hash estable, grupos, roles, límites, llamadas agrupadas y nodos planned. El generador documenta los contratos existentes sin simular invocaciones.
- **Qué hace para Gustavo:** puede entender rápidamente el equipo completo y seguir un ciclo sin reconstruir las relaciones leyendo prompts o código.
- **Responsable:** generador determinista del registro; los orquestadores son responsables de que sus ciclos estén declarados.
- **Cadencia:** regenerar cada cambio de grafo/schemas; CI comprueba que lo versionado coincide.
- **Tu turno:** ninguna aprobación por regenerar el dibujo; el diagrama no habilita decisiones o agentes.
- **Datos necesarios y disponibilidad:** registro ARQ-01 y schemas; hoy no existen generador ni diagrama derivado único.
- **Código:** `scripts/grafo/mermaid.py`, `docs/arquitectura/grafo.md` y paso de comprobación en `.github/workflows/barrio-ai.yml`.
- **Criterios de aceptación:**
  1. **Dado** un registro válido, **cuando** se genera, **entonces** produce un Mermaid completo y uno por ciclo, con grupos, roles, dirección/tipo de llamadas, leyenda, loops/gates, agentes planificados diferenciados, versión/hash y enlaces a contratos. Distingue solicitud, devolución de resultado y transición del workflow; una devolución no es permiso para llamar en sentido inverso.
  2. **Dado** el mismo registro y schemas, **cuando** se regenera dos veces, **entonces** el resultado es idéntico, sin timestamps volátiles ni orden aleatorio; el archivo señala «Generado, editar el registro».
  3. **Dado** un cambio de registro sin regenerar o una edición manual del diagrama, **cuando** corre el modo de comprobación en CI, **entonces** falla con diff y comando para regenerar. CI se dispara por registro, schemas, generador y documentos pertinentes; el filtro actual que omite `docs/` no deja pasar una deriva silenciosa.
  4. **Dado** registro inválido o vacío, **cuando** intenta generar, **entonces** explica el error y no reemplaza el documento válido previo por uno incompleto presentado como vigente.
- **Brechas código/docs:** los diagramas futuros serán derivados, no una segunda fuente de decisiones. Esta ficha especifica la generación, no afirma que `docs/arquitectura/grafo.md` ya exista.
- **Cobertura QA:** `test_grafo.py` y/o comprobación de diagrama en CI; ejecución de suites pendiente por Claude.


### ARQ-08 · Mapa del equipo en PWA y app <a id="arq-08"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Alcance 3a:** Lista por grupos/ciclos y ficha con misión, unidades, conexiones y actividad existente. Sin canvas gigante ni acciones de ejecución. No inventa actividad cuando no hay atribución; 3b agrega actividad procedente de los ledgers de pieza/red.
- **Qué hace para Gustavo:** abre «Mapa del equipo», ve las relaciones por grupo/ciclo y entiende qué hace cada agente, a quién consulta y qué hizo recientemente.
- **Responsable:** cada orquestador aporta su actividad; la Oficina presenta el mismo manifiesto y las ejecuciones registradas.
- **Cadencia:** configuración al abrir/cambiar versión; actividad con la cadencia de la Oficina, sin crear trabajo de agentes para dibujar el mapa.
- **Tu turno:** ninguna aprobación desde el mapa; enlaces a propuestas/bloqueos llevan a Tu turno para decidir allí con su versión vigente.
- **Datos necesarios y disponibilidad:** escena/paneles/eventos actuales existen; falta vista de grafo, endpoint de manifiesto saneado y enlace a ledgers/actividad persistida por ciclo.
- **Código:** `GET /api/v1/equipo/grafo`, `compartido/src/api/grafo.ts`, `oficina/src/pages/MapaEquipo.tsx` y `movil/src/equipo/MapaEquipoScreen.tsx`. Ruta `/equipo`, enlazada desde Oficina y Ajustes.
- **Criterios de aceptación:**
  1. **Dado** la PWA o app con sesión válida, **cuando** abre «Mapa del equipo», **entonces** ve agentes agrupados, roles distinguibles y conexiones permitidas; puede pasar del mapa completo a un ciclo, con leyenda y vista de lista accesible para pantallas pequeñas o lector de pantalla.
  2. **Dado** un agente seleccionado, **cuando** abre su ficha, **entonces** muestra para qué sirve, capacidades, inputs/outputs comprensibles, qué pide a quién y quién lo llama, unidades del curso, modelo/effort y límites efectivos, estado y actividad reciente con fecha/ciclo. La UI prioriza la explicación de trabajo; los nombres técnicos de schemas quedan en detalle ampliable.
  3. **Dado** un ciclo activo, **cuando** lo consulta, **entonces** muestra la ruta permitida y resalta solo pasos observados, con solicitudes pendientes, respuestas, gates, gasto y bloqueos ARQ-05. No dibuja una arista reciente como autorizada si no está en la versión de ese ciclo.
  4. **Dado** un nodo planificado, sin historial, registro nuevo frente a ciclo antiguo o fallo de conexión, **cuando** se muestra, **entonces** dice «En diseño», «Sin actividad registrada», distingue las versiones o muestra último dato con fecha/error respectivamente; no simula actividad ni mezcla ciclos.
  5. **Dado** el endpoint o panel, **cuando** se inspecciona, **entonces** no expone tokens, prompts con memoria privada, inbox ni detalles personales innecesarios; solo usuarios autorizados ven el mapa y los enlaces respetan permisos del artefacto de destino.
- **Brechas código/docs:** OFI-04 muestra equipos/roles, no sus conexiones. OFI-10 añadirá el visual a la oficina; ambos consumen el registro en lugar de mantener dos listas de agentes.
- **Cobertura QA:** `17-mapa-equipo.yaml` (ARQ-08), Jest y Vitest con fake backend; ejecución pendiente en CI/QA.


### ARQ-09 · Añadir un agente con contrato y evaluación <a id="arq-09"></a>

- **Dónde:** documentación · backend
- **Estado:** funciona
- **Alcance 3a:** La guía de integración está disponible. Activación por dispatcher y pruebas de rechazo runtime se completan en 3b.
- **Qué hace para Gustavo:** integrar un nuevo especialista tiene pasos claros y su lugar en el equipo se ve desde el primer cambio revisable.
- **Responsable:** orquestador receptor de la capacidad; quien implementa registra el contrato, adapter y evaluación, sin delegar ese cambio al propio agente.
- **Cadencia:** cada alta o cambio de responsabilidad/capacidad de un agente.
- **Tu turno:** solo decisiones de alcance, autoridad o presupuesto que no estén ya autorizadas; no se añade una aprobación humana rutinaria a toda definición técnica.
- **Datos necesarios y disponibilidad:** contratos, catálogo y harness de evaluaciones existen; faltan guía operativa ligada al registro y comprobaciones automáticas completas.
- **Código:** Guía `docs/arquitectura/anadir-agente.md`, enlazada al registro, sus tests, generador, API y evaluación con fakes.
- **Guía breve / checklist:**
  1. Elegir ciclo y dueño; explicar qué necesidad resuelve y por qué no basta un servicio/herramienta actual. Reservar id estable, grupo y rol; si es especialista, no delega.
  2. Añadir el nodo al registro con descripción de utilidad, capacidades, herramientas mínimas, schemas versionados, lista de unidades curadas o motivo de lista vacía, modelo/effort y presupuesto finito. Conservar el detalle de su definición documental enlazado, sin otra configuración efectiva.
  3. Declarar aristas desde el orquestador, tipos de petición/respuesta, obligatoriedad y topes; incluirlo en ciclos/loops pertinentes. Declarar gates para cualquier salida con efecto; un nuevo especialista no obtiene escrituras de LinkedIn.
  4. Implementar schemas y adapter que recibe contexto acotado y devuelve artefacto/citas. Registrar llamadas, resultados, errores, uso y checkpoints; no llamar otros agentes directamente.
  5. Añadir al menos un caso en el harness existente que demuestre su regla principal con una alternativa incorrecta, fuentes/unidades y salida esperada, más casos de schema inválido, timeout, presupuesto y llamada prohibida según su interfaz. Para el visual: proponer medio con motivo y devolverlo al director; nunca publicarlo por sí solo.
  6. Ejecutar validación estructural y de comportamiento sin efectos reales, regenerar Mermaid y comprobar CI. Revisar mapa completo y por ciclo en ambas interfaces; los estados deben corresponder a ejecuciones reales.
  7. Mantener `planned` hasta tener binding, schemas, evaluación y presupuesto válidos; activar de forma versionada y comprobar una instancia simulada con sus gates. No renumerar ni reutilizar un id retirado; conservar compatibilidad o migración de checkpoints viejos.
- **Criterios de aceptación:**
  1. **Dado** un nuevo nodo sin aristas, schema, evaluación o límites, **cuando** se intenta activar, **entonces** validación falla con la lista concreta de faltantes; añadir solo un JSON de definición o un personaje no lo activa.
  2. **Dado** un especialista completo, **cuando** supera la guía y se regenera, **entonces** aparece en el registro, Mermaid y Mapa del equipo con las mismas conexiones, y una llamada simulada produce el resultado esperado, citas y trazabilidad sin acceso extra.
  3. **Dado** un agente que intenta publicar o llamar a otro especialista, **cuando** se ejecuta su caso negativo, **entonces** falla antes de la operación y conserva evidencia; no se resuelve agregando una arista prohibida para hacer pasar el test.
- **Brechas código/docs:** hoy se puede describir un rol sin que exista runtime. Esta guía exige coherencia entre definición, llamadas autorizadas, evaluación y lo que se ve.
- **Cobertura QA:** `test_grafo.py` y/o comprobación de diagrama en CI; ejecución de suites pendiente por Claude.

## Retiradas

Ninguna.

## Entrega 3b y verificación pendiente

- Migración **0021_cycle_ledger**: identidad única por ciclo/clave, dueño/job, hash del registro, task/progress ledgers, lease, revisión y contadores. No modifica ni borra gastos históricos.
- Pieza: contexto privado congelado, resultados de etapa reutilizados, investigación fase 1, imágenes y Jev ligados al ciclo. Red: Relaciones coordina cada subtrigger existente; el investigador/descubrimiento/clasificador son herramientas. BAR-15, cadencias y Operación conservan su autoridad.
- Costes: reservas bajo el mismo lock global del usage ledger, incluyendo reservas inciertas; cap de pieza y día de 2 USD (desde el 10/11/2026: presupuesto general, ver `knowledge/presupuesto.py`; la pieza tiene 8 USD por ciclo, sin tope diario propio). Jev posterior usa la misma instancia. Referentes comparte bucket de mes natural America/Bogota cuando se active; Perfil tiene cap declarado de 10 USD. Los caps existentes de proveedor/propósito pueden detener antes.
- Recuperación: el reconciliador invalida el lease viejo y reencola el mismo job solo con checkpoints confirmados. Una llamada en vuelo queda incierta y avisa; no se repite ni se presume aprobada. Un cambio de registro/código/configuración exige migración explícita del checkpoint.
- Atasco: dos pasos sin avance permiten un replan explícito como máximo; sin plan nuevo, escalan. Esperas de negocio no incrementan el contador. Un gestor humano puede registrar un plan y reanudar un atasco conciliado en la misma instancia mediante `POST /equipo/ciclos/{id}/decision`; no aumenta presupuesto ni elimina intentos. Reconocer el aviso solo lo retira de Tu turno.
- Oficina: solicitudes y respuestas auténticas; el mapa lee contadores, gasto y motivos del ledger, filtrados por dueño. No entrega payloads, fuentes privadas ni resultados completos.

Claude debe ejecutar migraciones/checks y todas las regresiones con fakes, regenerar Mermaid en CI y comparar, y comprobar recuperación entre checkpoints, reservas concurrentes, ausencia de publicaciones duplicadas y veto/hash/BAR-15. Selección: **`[qa: 03 04 06 07 09 11 16 17-mapa-equipo]`**. Ver también [la entrega técnica](../arquitectura/orquestacion.md).
