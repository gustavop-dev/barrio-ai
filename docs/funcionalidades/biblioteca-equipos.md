# Uso de la biblioteca por los equipos (`BIB`)

La biblioteca es el curso de las clases 01–06: aporta criterios con sus excepciones y fuentes, no hechos sobre personas ni permisos para actuar. No se modifican las unidades originales ni se incorpora clase 07. La fase web prevista (`web_search`, `web_fetch`, enlaces en capturas) aporta fuentes externas separadas; este archivo no vuelve a definirla.

## Punto de partida y reparto

| Consumidor | Uso comprobado hoy | Uso propuesto |
| --- | --- | --- |
| Editorial y cinco lectores | `editorial.STAGES` y `operador.course_context` cargan unidades fijas por etapa | Conservarlo; añadir estudio comunitario LEC-03 y contexto visual EDI-20 sin sustituir las unidades pertinentes. |
| Comentarios de Relaciones | `operador.COMMENT_UNITS`, `course_context`, `propose_comment` | Conservarlo; enlazar evidencia de referentes y experimentos COM-11. |
| Estrategia y perfil | `knowledge/agents.py` busca y lee unidades; `retrieval.AGENTS` solo reconoce `posicionamiento` y `perfil` | Biblioteca como insumo principal en EST-01–05; [listas curadas de posicionamiento, copy, revisión mensual y visual](estrategia-perfil.md#unidades-perfil). Cada recomendación del Markdown cita IDs pertinentes y evidencia; marca y geometría se atribuyen a Gustavo/tablero. |
| Observatorio | Sin recuperación del curso en `observe`, `red.discover/classify` o métricas; sus contratos sí enumeran unidades | BIB-02: selección de referentes, estudio comunitario y experimentos. |
| Red | Criterios de posicionamiento escritos en código; `classify` no recupera unidades y `plan` es determinista | BIB-03: fundamentar criterios de encaje y decisiones de clasificación; el plan consume resultados, no busca por persona a seguir. |
| Inbox | `conversaciones.assess` usa preguntas tipadas; sin biblioteca | BIB-04: guía para interpretar necesidades y distinguir conversación, venta y compromisos. |
| Líder | `lider.review/comment_worthy` usa reglas, orientación y juicios tipados; sin biblioteca | BIB-05: guía versionada de aporte, respeto y riesgo; no un segundo juez del encaje. |
| Capturas | `capturas.classify` decide destino; sin biblioteca | Sin consumo propio del curso, por decisión de Gustavo. BIB-06 se retira; Editorial o Perfil consultan su contexto habitual tras el ruteo, incluida la petición explícita EST-05. |
| Resumen semanal | `resumen_semanal` usa estadísticas, posicionamiento y orientación; sin biblioteca | BIB-07: interpretar aprendizajes y proponer próximos experimentos con evidencia. |
| Revisión y Operación | Revisión usa unidades fijas en Editorial; Operación ejecuta controles deterministas | Conservar el reparto. No dar al ejecutor discreción para cambiar texto, lista de referentes o perfil. |

Los contratos de [equipos](../../agentes-linkedin/equipos/) son diseño; enumerar unidades allí no significa que el runtime las consulte. El cambio de acceso para otros roles requerirá integración explícita: `retrieval.search(agent=...)` rechaza hoy identificadores distintos de los dos agentes de biblioteca.

## Listas curadas por rol y origen comprobado <a id="unidades-por-rol"></a>

Addendum de Gustavo leído en `codex-spec-biblioteca.md` del scratchpad, junto con `LEEME.txt`, `politica-de-uso.json` y los registros correspondientes de `/home/cerrotico/personal/linkedin/LinkedIn Sales - Procesamiento completo/conocimiento-para-agentes/conocimiento.jsonl`. SHA-256 del JSONL: `53e839548e0ea27750a82bdcf2d572573969c263ed47d58f0da6d02c35636853`. La exportación contiene 1.032 unidades de clases **02–07**, no clase 01; las listas siguientes usan solo 03 y 06. El alcance global del proyecto sigue siendo 01–06; clase 07 queda excluida. La lectura local no es una nueva revisión humana ni una verificación de LinkedIn.

Las listas son estables, siguiendo `APPROACH_UNITS`, `READER_UNITS` y `course_context/course_block`: cargar originales completos, límites y procedencia mediante `retrieval.unit`, como bloques de sistema cacheables. `retrieval.search` queda para un tema variable del caso, no para volver a descubrir las reglas del rol en cada ejecución. Al migrar a [ARQ-01](arquitectura-agentes.md#arq-01), las listas viven en el único registro, con referencias reutilizables y expansión visible por nodo; no habrá otra lista divergente en Python. Una clave de fuente de esta exportación, por ejemplo `03:qt00458`, debe resolverse con su sesión, nunca como `qt00458` sin clase.

| Lista / consumidores | IDs exactos y regla que sostiene cada uno | Traducción a comportamiento |
| --- | --- | --- |
| `REFERENTS_UNITS`: investigador de referentes e investigador líder del ciclo mensual | `LI-03-V009-K04`: elegir líderes que lee el cliente; `LI-03-V018-K02`: descubrir en líderes, comentarios y otras redes; `LI-03-M005-K05`: cinco papeles; `LI-03-M005-K06`: pertinencia más allá de ser comprador; `LI-03-V020-K05`: registrar señales sin afirmar causalidad | Juicio contextual con citas. Código: cinco main protegidos, diez variables, máximo 15 y gate de decisión humana o plazo OBS-02 vienen de Gustavo, no se atribuyen al curso. |
| `ANALYSIS_UNITS`: analista de barrio y resultados, estudio de comunidad y resumen semanal | `LI-03-M004-K04`: escuchar necesidades, objeciones y lenguaje; `LI-03-V020-K05`: registrar lo observado; `LI-06-V006-K03`: escuchar después de publicar; `LI-06-V006-K04`: distinguir señales, DM no es venta; `LI-06-V007-K05`: audiencia pertinente no equivale solo a compradores; `LI-06-V008-K01`: separar contenido y composición de público; `LI-06-V008-K02`: elegir y conservar ventanas comparables | Juicio en el contexto del analista. Código calcula cifras, ventanas, cobertura y deduplicación; no convierte interpretaciones cualitativas en puntuaciones numéricas inventadas. `WEEKLY_UNITS` referencia esta misma lista, sin copia independiente. |
| `NETWORK_UNITS`: investigador al descubrir/clasificar y Relaciones al planificar | `LI-03-M005-K05`: papeles; `LI-03-M005-K06`: cinco preguntas sin exigir cinco sí; `LI-03-V018-K02`: lugares de descubrimiento; `LI-03-V018-K03`: diversidad y etapa de crecimiento; `LI-03-V015-K01`: ritmo orientativo, dependiente de la cuenta; `LI-03-V021-K02`: pauta diaria/semanal con cautelas; `LI-03-V021-K03`: reparto adaptable por papeles y acciones; `LI-03-M006-K01`: conexión sin pitch; `LI-03-M006-K04`: prioridad comercial sin exclusividad, participación y registro | Código para lunes–viernes, techo de 20/día y distribución auditable (BIB-08); juicio contextual para encaje, pertinencia y acción adecuada. Las cifras de la tabla del curso no se convierten en cuotas obligatorias ni todas sus acciones en invitaciones. |
| `INBOX_UNITS`: conversaciones e inbox | `LI-03-V019-K03`: interés por el trabajo del interlocutor; `LI-03-V019-K04`: propuesta solo cuando la conversación y el interés lo permitan; `LI-03-V020-K01`: necesidad expresada antes de ofrecer reunión; `LI-06-V006-K04`: distinguir conversación de venta | Contexto/criterios de las preguntas tipadas de `assess`; código mantiene solo lectura, privacidad y paso a Gustavo. No convertir ejemplos de conversaciones del curso en mensajes realmente enviados. |
| `LEAD_UNITS`: líder/Jev | `LI-03-V020-K02`: aporte con postura y fundamento; `LI-03-M006-K01`: sin pitch al abrir relación; `LI-03-M005-K06`: pertinencia sin exigir cinco sí; `LI-06-M001-K04`: cumplir la promesa; `LI-06-M001-K07`: no inventar evidencia | Reglas explícitas en código y juicios estrechos en `state`/criterios `true`/`false` de Jev. El encaje sigue siendo del clasificador; el líder comprueba riesgo, aporte y coherencia según capacidad. |

**Curso y decisiones de Gustavo:** `LI-03-V015-K01` advierte que 15–20 no es límite universal; `LI-03-V021-K02` menciona una tarea de 80 semanales y cautela de 30; `LI-03-V021-K03` conserva la flexibilidad de la tabla. Gustavo fija lunes–viernes, máximo **20/día y 100/semana**, rampa y reparto tal como lo enseña el curso. BIB-08 reproduce sus cinco filas/acciones y condiciones; BAR-15 concreta caps/salud/agenda. No se atribuyen al curso porcentajes de invitaciones que no contiene ni se presentan cifras observadas de proveedores como límites oficiales.

El sexto addendum confirma **cuenta gratuita**: invitaciones sin nota por defecto, notas escasas reservadas para mayor encaje con explicación y citas de NETWORK_UNITS (en particular conexión sin pitch `LI-03-M006-K01`). [BAR-16](red.md#bar-16) especifica tier/cupos y fallback tras rechazo inequívoco de cuota de notas. El tipo de cuenta, el cap local de notas y la exclusión de outreach externo son decisiones de producto, no reglas atribuidas al curso. Solo Gustavo puede cambiar los main protegidos; el agente nunca propone su baja, swap o desprotección.

## Resumen

| ID | Función | Dónde | Estado |
| --- | --- | --- | --- |
| [BIB-01](#bib-01) | Consulta compartida con evidencia y versión | backend | no implementado |
| [BIB-02](#bib-02) | Criterios del curso para Observatorio | backend | no implementado |
| [BIB-03](#bib-03) | Criterios del curso para la red | backend | no implementado |
| [BIB-04](#bib-04) | Guía de conversación para inbox de solo lectura | backend | no implementado |
| [BIB-05](#bib-05) | Fundamentos para el juicio acotado del líder | backend | no implementado |
| [BIB-07](#bib-07) | Aprendizaje semanal con curso y resultados separados | backend | no implementado |
| [BIB-08](#bib-08) | Política de invitaciones: días, techo y diversidad | backend | no implementado |
| [BIB-09](#bib-09) | Evaluar el uso efectivo del curso por cada rol | backend | no implementado |

### BIB-01 · Consulta compartida con evidencia y versión <a id="bib-01"></a>

- **Dónde:** backend
- **Estado:** no implementado
- **Qué hace para Gustavo:** cada equipo puede explicar qué criterio del curso utilizó y cómo lo adaptó a su contexto, sin atribuir al curso reglas inventadas.
- **Responsable:** cada rol consumidor responde de su consulta; `posicionamiento` mantiene la coherencia con la dirección aprobada de Gustavo.
- **Cadencia:** por decisión o cambio de versión; paquetes comunes reutilizables por rol y versión de curso/criterios, no una búsqueda pagada en cada tick.
- **Tu turno:** solo conflictos estratégicos o información imprescindible de Gustavo. La recuperación de conocimiento no requiere aprobación; no confirma memoria ni cambia orientación por sí misma.
- **Datos necesarios y disponibilidad:** `retrieval.search/unit`, unidades con original, hash, fuentes y relaciones, y contexto de `knowledge/agents.py` existen; se han leído las unidades del JSONL local indicadas arriba, sin consultar la base de datos. Faltan integración con consumidores nuevos, artefactos y trazabilidad común; se validará que esos IDs estén disponibles en `retrieval.unit` al implementar.
- **Código:** no existe la integración transversal. Referencias: `knowledge/retrieval.py`, `knowledge/agents.py: context`, `team_backend/operador.py: course_context`.
- **Criterios de aceptación:**
  1. **Dado** un rol consumidor nuevo, **cuando** consulta, **entonces** dispone de una identidad y política de recuperación explícita sin hacerse pasar por `perfil`; registra tarea, consulta, modo real (léxico/híbrido), unidades utilizadas, hash, fuentes, omisiones y versiones del contexto.
  2. **Dado** una recomendación, **cuando** cita el curso, **entonces** solo cita unidades recuperadas completas con condiciones y excepciones, y distingue pauta del curso, dato confirmado de Gustavo, evidencia externa e hipótesis. Un id válido por sí solo no prueba que respalde la afirmación.
  3. **Dado** presupuesto de contexto o dinero agotado, **cuando** recupera, **entonces** reutiliza un paquete vigente si existe, registra unidades omitidas sin mutilar sus límites y muestra «Biblioteca no disponible» si no puede fundamentar. No fabrica citas ni convierte una preferencia del curso en un permiso de escritura.
  4. **Dado** falta de embeddings, cero coincidencias o una unidad retirada, **cuando** consulta, **entonces** diferencia búsqueda léxica disponible de fallo total, deja constancia y sigue la alternativa de cada ficha; no presenta una recomendación nueva como sustentada si faltó la evidencia necesaria.
  5. **Dado** un cambio de dirección o de fuentes, **cuando** reutiliza un paquete, **entonces** invalida el contexto incompatible, conserva la versión usada en decisiones previas y no aplica retroactivamente nuevas reglas a una aprobación anterior.
  6. **Dado** contenido de una unidad, captura o web que pida actuar, **cuando** lo interpreta, **entonces** lo trata como fuente y mantiene reglas de Gustavo, privacidad y reparto de acciones. La consulta no reescribe unidades, confirma hechos personales ni habilita clase 07.
  7. **Dado** un rol de la tabla curada, **cuando** prepara contexto, **entonces** carga su lista por ID en un bloque estable/cacheable y limita la búsqueda adicional al tema variable; registra por separado la lista base y las unidades adicionales. No resume una regla perdiendo sus excepciones.
  8. **Dado** cualquier salida del rol, incluida abstención, juicio tipado o plan determinista, **cuando** se persiste, **entonces** su envoltorio incluye `course_citations` (IDs efectivamente utilizados) y `criterion_sources` (criterio → IDs), versiones y evidencia del caso. Las citas son metadatos internos, no texto a publicar. Una salida técnica sin conocimiento disponible lleva lista vacía y motivo explícito; no puede pasar por decisión fundamentada. En Jev el backend adjunta el mapa de criterios cargado, sin pedir al modelo generar citas ni atribuirle lectura de unidades ausentes.
- **Brechas código/docs:** existen dos mecanismos de lectura (búsqueda manual y unidades fijas), pero no un consumo trazable para todos estos roles; las fichas nuevas no reclasifican como ausente el uso editorial ya implementado.
- **Cobertura QA:** pendiente

### BIB-02 · Criterios del curso para Observatorio <a id="bib-02"></a>

- **Dónde:** backend
- **Estado:** no implementado
- **Qué hace para Gustavo:** la búsqueda de referentes y la lectura de su comunidad responden a sus objetivos y al concepto de barrio del curso, no solo al alcance.
- **Responsable:** `investigador_referentes` para selección; `analista_barrio_resultados` para comunidad y experimentos.
- **Cadencia:** revisión mensual, diseño de experimento y actualización del estudio comunitario; reutilizar criterios vigentes durante la observación diaria.
- **Tu turno:** las propuestas OBS-01/02/04 y las decisiones de orientación; ninguna aprobación extra por consultar el curso.
- **Datos necesarios y disponibilidad:** listas `REFERENTS_UNITS` y `ANALYSIS_UNITS` verificadas en el JSONL local, posicionamiento y observaciones parciales; falta su recuperación efectiva en el ciclo de Observatorio. El investigador líder recibe las fuentes del especialista y conserva la decisión de ciclo según ARQ-02.
- **Código:** no existe este consumo. Referencias: `operador.observe`, `red.discover/classify`, contratos de Observatorio y `knowledge/retrieval.py`.
- **Criterios de aceptación:**
  1. **Dado** una selección de referentes, **cuando** usa el curso, **entonces** traduce las unidades recuperadas a criterios sobre audiencia, problemas y aportación, y cada recomendación los relaciona con evidencia del candidato y objetivos vigentes, sin convertir insignias o popularidad en encaje.
  2. **Dado** un estudio o experimento, **cuando** define aprendizaje, **entonces** distingue compradores, pares, recomendadores, líderes y divulgadores, admite incertidumbre y conserva los límites de las unidades sobre inferencias y causalidad.
  3. **Dado** falta de unidad o evidencia, **cuando** prepara el dossier, **entonces** muestra la brecha y conserva los criterios previamente fundamentados si siguen vigentes; no presenta un criterio nuevo como instrucción de Daniela ni inventa resultados para rellenar la recomendación.
  4. **Dado** un dossier del investigador o informe del analista, **cuando** lo entrega al orquestador, **entonces** cada propuesta/hallazgo lleva citas de su lista y evidencia del caso, y supera su caso de evaluación BIB-09. No se cambia la lista de referentes desde un especialista.
- **Brechas código/docs:** estos conocimientos figuran en contratos no ejecutables, no en `observe` ni en el análisis mensual que aún falta.
- **Cobertura QA:** pendiente

### BIB-03 · Criterios del curso para la red <a id="bib-03"></a>

- **Dónde:** backend
- **Estado:** no implementado
- **Qué hace para Gustavo:** el encaje de cada persona tiene fundamento y evidencia, y la red conserva la diferencia entre comunidad, posible comprador y oportunidad confirmada.
- **Responsable:** `investigador_referentes` clasifica; `relaciones_comunidad` usa esa clasificación para su plan.
- **Cadencia:** al preparar/actualizar el paquete de criterios y en cada lote de clasificación; `red.plan` reutiliza la decisión y mantiene su funcionamiento determinista.
- **Tu turno:** solo propuestas de cambio de público/criterios estratégicos y las acciones que ya requieran aprobación por configuración. No se añade aprobación individual a toda clasificación.
- **Datos necesarios y disponibilidad:** `Contact.classification`, evidencia y `posicionamiento.network_criteria` existen; `NETWORK_UNITS` se comprobó en el corpus local. Faltan recuperación, citas y versión del fundamento en clasificación/plan; las brechas de días, límites y reparto están en BIB-08.
- **Código:** no existe la consulta. Referencias: `red.CLASSIFY_SYSTEM/classify/plan`, `posicionamiento.py`.
- **Criterios de aceptación:**
  1. **Dado** un lote de contactos, **cuando** clasifica, **entonces** guarda criterio/versionado, unidades, motivo basado en perfil o interacción, confianza y datos faltantes; ser «comprador» sigue siendo hipótesis y una persona de la audiencia de un referente no hereda automáticamente su encaje.
  2. **Dado** una pauta general del curso sobre conexión, **cuando** el plan la consume, **entonces** aplica la política explícita BIB-08 y conserva pausas, cupos menores, esperas y veto; ninguna cifra de aula aumenta automáticamente límites ni habilita mensajes outbound.
  3. **Dado** biblioteca fallida, **cuando** hay criterios previamente válidos, **entonces** puede clasificar con ese paquete y registra la versión; sin criterios fundamentados deja el lote pendiente y explica la falta, sin descartar personas por el fallo de infraestructura.
  4. **Dado** un lote clasificado y un plan, **cuando** se entregan a Relaciones como orquestador, **entonces** incluyen `course_citations` y el mapa de criterios de BIB-01; se conservan los resultados de las evaluaciones de clasificador y plan de BIB-09.
- **Brechas código/docs:** el prompt usa criterios escritos en código; el plan no necesita convertirse en otro agente de recuperación ni el líder repetir el juicio de encaje.
- **Cobertura QA:** pendiente

### BIB-04 · Guía de conversación para inbox de solo lectura <a id="bib-04"></a>

- **Dónde:** backend
- **Estado:** no implementado
- **Qué hace para Gustavo:** las conversaciones que le llegan a Tu turno se interpretan con criterios sobre escucha, necesidades expresadas y límites de una propuesta comercial.
- **Responsable:** `conversaciones_inbox`.
- **Cadencia:** preparar guía al activarse o cambiar sus fuentes; reutilizarla en cada evaluación horaria de mensajes nuevos.
- **Tu turno:** las tarjetas de conversación actuales; responder, negociar y marcar oportunidades continúa en manos de Gustavo.
- **Datos necesarios y disponibilidad:** hilo limitado, remitente/contacto y probabilidades de `conversaciones.assess` existen; `INBOX_UNITS` está verificada localmente. Falta incorporarla a las preguntas/estado de evaluación y a las citas de su salida.
- **Código:** no existe este consumo. Referencias: `conversaciones.py: assess/_questions`, [INB-08](inbox.md#inb-08).
- **Criterios de aceptación:**
  1. **Dado** un mensaje nuevo, **cuando** lo evalúa con la guía, **entonces** distingue interés expresado, pregunta pendiente y venta entrante, sin interpretar cortesía o interacción como intención de compra; registra unidades/versionado sin copiar el mensaje privado a consultas web o a otros equipos.
  2. **Dado** una unidad que hable de conversar o proponer una reunión, **cuando** se usa, **entonces** solo orienta la lectura y la prioridad. No se envían respuestas, se marca leído, se crean oportunidades ni se comprometen condiciones por esa recomendación.
  3. **Dado** fallo de biblioteca, **cuando** llega un mensaje, **entonces** usa el último paquete vigente si existe y cita su versión; sin paquete válido conserva la lectura y deja la evaluación pendiente, sin inventar un juicio fundamentado ni borrar tarjetas ya justificadas. El fallo queda visible para reintentar dentro de los límites.
  4. **Dado** una evaluación con guía vigente, **cuando** se guarda, **entonces** el envoltorio lleva citas por criterio y la versión de `INBOX_UNITS`; la salida estrecha de TypeSafe no se convierte en una redacción libre ni una instrucción de envío. El caso de BIB-09 distingue agradecimiento de necesidad expresada.
- **Brechas código/docs:** el contrato describe más conversación que el código; esta ficha preserva el inbox de solo lectura y no implementa envío ni borradores de respuesta.
- **Cobertura QA:** pendiente

### BIB-05 · Fundamentos para el juicio acotado del líder <a id="bib-05"></a>

- **Dónde:** backend
- **Estado:** no implementado
- **Qué hace para Gustavo:** el líder entiende las razones de las reglas de aporte y respeto y puede dejar una trazabilidad de sus juicios sin asumir nuevas decisiones.
- **Responsable:** agente líder (`lider.py`); no se añade otro cargo ni se amplía su autoridad.
- **Cadencia:** paquete de guía por versión; se usa al prefiltrar/revisar propuestas dentro de la cadencia actual.
- **Tu turno:** ninguna aprobación nueva; los avisos actuales por inactividad permanecen y solo Gustavo cambia orientación o configuración.
- **Datos necesarios y disponibilidad:** preguntas `noul`, `state`, criterios `true`/`false` y umbrales existen; `LEAD_UNITS` se comprobó en el JSONL. Falta recuperar el paquete y registrar qué unidades fundamentan cada pregunta.
- **Código:** no existe esta consulta. Referencias: `lider.review/comment_worthy`, `autopiloto.policy_review`, [COM-05](comentarios-y-lider.md#com-05).
- **Criterios de aceptación:**
  1. **Dado** una propuesta de comentario, **cuando** revisa con su guía, **entonces** las preguntas sobre aporte, pitch, invención y respeto usan criterios documentados y conservan respuestas tipadas, umbrales y fundamentos; no reescribe el comentario ni cambia sus comprobaciones deterministas.
  2. **Dado** una acción de red ya clasificada, **cuando** el líder la juzga, **entonces** solo evalúa el riesgo que le corresponde; no vuelve a clasificar `fit`, elige referentes ni aprueba cambios de perfil.
  3. **Dado** un fallo de biblioteca o una contradicción con la política vigente, **cuando** revisa, **entonces** usa la guía válida anterior si existe; sin paquete válido mantiene pendiente el juicio Jev. Las reglas deterministas siguen pudiendo bloquear, pero no se sustituye una revisión requerida por una aprobación sin fundamento; un fallo del modelo mantiene el reintento acotado.
  4. **Dado** una revisión Jev, **cuando** se construye la petición, **entonces** `state.course_criteria` o los criterios de cada pregunta contienen la pauta pertinente con sus límites, manteniendo preguntas `noul` separadas sobre aporte, pitch, evidencia, respeto, idioma, riesgo u orientación según la capacidad. El código aplica los umbrales; Jev no decide nuevas reglas ni genera un plan.
  5. **Dado** `review` o `comment_worthy`, **cuando** devuelven resultado, **entonces** el backend añade `course_citations` y `criterion_sources` de las preguntas realmente enviadas, respuestas, umbrales y versión; pasan el caso del líder en BIB-09. Sin paquete válido se registra modo degradado explícito, no «fundamentado en el curso».
- **Brechas código/docs:** no existe recuperación en el líder; aprender del curso no lo convierte en director ni en autoridad estratégica.
- **Cobertura QA:** pendiente

### BIB-07 · Aprendizaje semanal con curso y resultados separados <a id="bib-07"></a>

- **Dónde:** backend
- **Estado:** no implementado
- **Qué hace para Gustavo:** el resumen conecta resultados con aprendizajes del curso y propone qué comprobar después, explicando los límites de lo observado.
- **Responsable:** `analista_barrio_resultados`.
- **Cadencia:** en cada resumen semanal del lunes, reutilizando el corte determinista y un paquete de unidades pertinente al resultado.
- **Tu turno:** orientación propuesta por [SEM-06](resumen-semanal.md#sem-06); experimentos por TUR-21 y cambios de referentes por TUR-20, cada decisión separada. Las recomendaciones de aprendizaje son informativas.
- **Datos necesarios y disponibilidad:** `resumen_semanal.stats/validate`, estadísticas, orientación y comentarios de Gustavo existen. Faltan consulta y relación con estudios/experimentos; se usará `WEEKLY_UNITS`, referencia de `ANALYSIS_UNITS`, comprobada en el corpus.
- **Código:** no existe esta integración. Referencias: `resumen_semanal.SYSTEM/message/run/validate`, [SEM-02](resumen-semanal.md#sem-02).
- **Criterios de aceptación:**
  1. **Dado** el corte semanal y unidades pertinentes, **cuando** escribe, **entonces** cada aprendizaje separa cifra observada (clave, ventana y cobertura), criterio del curso (unidad) e interpretación/experimento propuesto; las fórmulas siguen calculadas por backend.
  2. **Dado** citas y ejemplos numéricos del curso, **cuando** valida, **entonces** no los admite como métricas de Gustavo ni confunde números de IDs con resultados. Conserva el validador de cifras y descarta afirmaciones numéricas sin respaldo en estadísticas.
  3. **Dado** resultados de OBS-03/04 o LEC-01, **cuando** los incorpora, **entonces** cita su versión, muestra y límites; no adjudica nuevos seguidores a un referente con solo un delta agregado ni generaliza a toda la comunidad una muestra de comentaristas.
  4. **Dado** poca evidencia o biblioteca fallida sin paquete vigente, **cuando** genera el resumen, **entonces** muestra los datos deterministas disponibles con sus advertencias y «Aprendizaje del curso pendiente»; no emite una interpretación nueva sin fundamento, inventa citas ni propone cambiar la dirección a partir de una semana insuficiente.
  5. **Dado** una orientación, alta/baja o prueba sugerida, **cuando** entrega el resumen, **entonces** mantiene su carácter de propuesta y el director solo recibe recomendaciones; no cambia memoria confirmada, referentes ni planes aprobados.
  6. **Dado** el resumen, **cuando** se guarda, **entonces** cada aprendizaje lleva los IDs usados y su evidencia estadística; el caso del analista/resumen de BIB-09 verifica que una caída de likes no se transforma por sí sola en un cambio de público.
- **Brechas código/docs:** hoy el resumen ya propone orientación con aprobación humana, pero no consulta la biblioteca ni recibe experimentos o estudios comunitarios versionados.
- **Cobertura QA:** pendiente

### BIB-08 · Política de invitaciones: días, techo y diversidad <a id="bib-08"></a>

- **Dónde:** backend
- **Estado:** no implementado
- **Qué hace para Gustavo:** las invitaciones salen de lunes a viernes, nunca más de 20 por día, y se distribuyen entre papeles pertinentes del barrio.
- **Responsable:** `relaciones_comunidad` decide el plan del ciclo; el planificador y `operador_cuenta` aplican los límites en código, no Jev ni un prompt.
- **Cadencia:** plan de red dentro de su frecuencia actual; asignación por día local y control de cada envío. Registro semanal de distribución y huecos.
- **Tu turno:** reparto del curso, días, techo y rampa ya decididos; no se pide otra aprobación de esa política ni de cada invitación en auto. Gustavo conserva veto y recibe avisos de salud/límite. Cambiar posteriormente el mandato requiere una decisión explícita.
- **Datos necesarios y disponibilidad:** `Contact.classification.role/fit/confidence`, propuestas, ejecuciones y zona horaria existen. Faltan política de días, reparto persistido por papel, reservas de cupos por papel y procedencia del criterio; `NETWORK_UNITS` da el fundamento.
- **Código:** no existe esta política completa. Hoy `operador.DEFAULT_LIMITS['RED-02']=(5,20)` y `deploy/.env.example` reflejan 5/día y 20/semana; `OPERATOR_DAILY_LIMITS`/`OPERATOR_WEEKLY_LIMITS` pueden sobrescribirlos sin techo fijo de 20. `within_window` comprueba hora pero no día laboral. `red.plan` ordena por `followed_at`, espera 48 h por defecto, descuenta propuestas abiertas y cupos, pero no reparte por papel. `execute` vuelve a comprobar límites; no se inspeccionó la configuración privada desplegada.
- **Política vinculante:** `D = min(20, límite diario configurado, etapa de rampa)`; límite semanal mínimo entre **100**, configuración y etapa. Restar ejecuciones/reservas/posibles envíos por día local y semana ISO, en America/Bogota. La subida **5/20 → 10/50 → 20/100** está ahora autorizada bajo salud/plazos de [BAR-15](red.md#bar-15); no es un salto automático. Espaciado, enfriamiento, restricciones, autonomía/veto y caps menores efectivos prevalecen.
- **Reparto del curso confirmado, sin una distribución inventada:** se aplica literalmente `LI-03-V021-K03`, fuente `03:c7f1f10c349724396998:p040`, con sus condiciones orales `03:qt00456–qt00459`, y `LI-03-M006-K04`. Sustituye la rotación uniforme propuesta antes. La tabla es de **perfiles semanales y acciones**, suma 90 perfiles de referencia; no define porcentajes de invitaciones ni obliga a invitar a 90/100 personas.

  | Papel | Meta semanal de referencia | Dónde buscar | Acción del curso |
  | --- | --- | --- | --- |
  | Comprador | 20 perfiles | Cargo o industria | Conectar; prioridad comercial. |
  | Recomendador | 15 perfiles | Clientes, aliados y socios | Conectar o conversar. |
  | Divulgador (difusor en la tabla) | 20 perfiles | Comentarios y posts activos | Comentar o conectar. |
  | Líder | 10 perfiles | Referentes de industria | Comentar con criterio. |
  | Par | 25 perfiles | Creadores o emergentes | Relación y reciprocidad. |

  El plan mantiene este reparto de atención y sus acciones, registra desviaciones justificadas por nicho/elegibilidad y evita llenar vacantes solo con compradores. Invitaciones diarias incluyen distintos actores elegibles con prioridad del buyer persona; no transforma «comentar» o «relación» en invitación obligatoria ni habilita mensajes de inbox. El backend comprueba papeles/acciones/contadores y conserva razones de adaptación; el juicio decide pertinencia. Una persona con varios roles se cuenta una vez en el reparto de perfiles; desconocidos no llenan cuotas y `aliado` requiere asignación sustentada. Si faltan otros actores, descubre más y deja huecos, sin reclasificar para cumplir números. Esta flexibilidad es parte explícita del curso, no una pregunta abierta a Gustavo.
- **Criterios de aceptación:**
  1. **Dado** sábado o domingo local, incluso con propuesta aprobada el viernes, **cuando** planifica o ejecuta RED-02, **entonces** no envía, conserva el pendiente y señala el próximo día permitido. Leer, clasificar o conciliar no equivale a enviar y puede continuar.
  2. **Dado** configuración 30/día o 200/semana, **cuando** agota 20/100 o el límite menor de rampa/configuración, **entonces** bloquea el siguiente envío; etapa inicial 5/20 bloquea sexta diaria o 21.ª semanal. Reservas transaccionales evitan que dos workers excedan el mismo cupo.
  3. **Dado** un fixture con suficientes perfiles de los cinco papeles, **cuando** arma la referencia semanal, **entonces** conserva la tabla **20/15/20/10/25** y sus acciones/fuentes, distingue perfiles de interacciones y mantiene diversidad real en invitaciones pertinentes. No usa un reparto uniforme, convierte esos 90 perfiles en 90 invitaciones ni invita automáticamente a los diez líderes.
  4. **Dado** falta de actores o de encaje, **cuando** adapta, **entonces** justifica el hueco frente a la tabla y activa descubrimiento sin rellenarlo con compradores o invitaciones indebidas. Registra por separado planeado/ejecutado y no proclama diversidad con acciones fallidas; comentarios a líderes y relación con pares conservan su valor aunque no haya invitación.
  5. **Dado** invitación incierta, cancelada o definitivamente no enviada, **cuando** concilia/recalcula, **entonces** la incierta conserva su cupo hasta resolverla, y la no enviada libera solo su reserva una vez. La política se vuelve a validar inmediatamente antes de escribir, también en rutas manuales de la app.
  6. **Dado** una pauta del curso con metas de aula, **cuando** explica el plan, **entonces** cita unidades y registra reglas ejecutadas, papel, huecos y límites efectivos; no promete aceptación/ventas ni sustituye el techo de Gustavo por el 30 o el mínimo de 80 del ejemplo didáctico.
- **Brechas código/docs:** hay topes y control antes de escribir; faltan calendario laboral, techo 20/100, rampa/salud y aplicación trazable de la tabla. Ya no queda pendiente decidir reparto: rige el curso con su flexibilidad, por instrucción del quinto addendum.
- **Cobertura QA:** pendiente

### BIB-09 · Evaluar el uso efectivo del curso por cada rol <a id="bib-09"></a>

- **Dónde:** backend
- **Estado:** no implementado
- **Qué hace para Gustavo:** permite comprobar que el curso cambia decisiones concretas y que las citas no son un adorno.
- **Responsable:** cada rol responde de su caso; su orquestador conserva el resultado y la versión evaluada. El líder sigue siendo una compuerta del producto, no juez libre de estas pruebas.
- **Cadencia:** al integrar un rol y al cambiar lista de unidades, contexto, criterios Jev, modelo, schemas o política; antes de activar el cambio.
- **Tu turno:** ninguna aprobación de fixtures o pruebas simuladas; cambios de público, reparto o gasto se proponen por sus fichas. Las evaluaciones pagadas conservan opt-in y tope, no se ejecutan en esta tarea documental.
- **Datos necesarios y disponibilidad:** `evaluaciones.py`, constructores que reflejan peticiones de producción, validadores y `tests/test_evaluaciones.py` existen. El harness hoy enumera verificador, comentarios, clasificador, lectores y director; faltan casos/entradas para investigador, analista, plan de red, inbox y líder por separado.
- **Código:** no existe esta cobertura. Referencias: `team_backend/evaluaciones.py: AGENTS/Run/gate`, `tests/test_evaluaciones.py`; adaptar el harness existente, sin otro sistema paralelo.
- **Casos mínimos de aceptación por rol:**

  | Caso / rol | Unidad que debe influir | Entrada y resultado observable |
  | --- | --- | --- |
  | `BIB-09-investigador` / investigador de referentes y síntesis del investigador líder | `LI-03-V009-K04`, `LI-03-M005-K06` | Candidato famoso ajeno al público y otro de nicho pertinente: prioriza el segundo, cita evidencia y no inventa insignia. Un main con pocas interacciones permanece protegido; un swap solo puede retirar un variable y se entrega como pareja al lote OBS-02. |
  | `BIB-09-analista` / analista de barrio y resultados | `LI-06-V006-K04`, `LI-06-V007-K05` | Aumentan seguidores agregados y aparecen dos DM sin necesidad comercial: no inventa identidades, motivos ni ventas; conserva valor de divulgadores y cita las unidades. |
  | `BIB-09-clasificador` / investigador en red | `LI-03-M005-K06`, `LI-03-V018-K03` | Par relevante que habla del tema pero no compra: puede encajar con evidencia; no exige cinco respuestas afirmativas ni inventa una puntuación del curso. |
  | `BIB-09-relaciones` / Relaciones, orquestador del plan | `LI-03-V021-K03`, `LI-03-M005-K05`, `LI-03-M006-K01` | Plan usa 20/15/20/10/25 perfiles de referencia con sus acciones, no porcentaje uniforme ni 90 invitaciones; registra adaptación al nicho. Fixtures sábado, cupo 21 y semana 101 verifican bloqueos; caída de aceptación y 422 cannot_resend_yet frenan rampa por BAR-15. Cuenta free: sin nota por defecto; para candidato de mayor encaje justifica/cita la excepción sin pitch. Simular cuota de notas agotada permite solo fallback confirmado BAR-16; límite general o escritura ambigua nunca produce doble invitación. |
  | `BIB-09-inbox` / conversaciones e inbox | `LI-03-V019-K04`, `LI-03-V020-K01` | Comparar «gracias por conectar» con una necesidad y pregunta concreta: no tratar el saludo como permiso para vender; el segundo puede escalar a Gustavo, sin enviar mensajes. |
  | `BIB-09-lider` / líder Jev | `LI-03-V020-K02`, `LI-03-M006-K01` | Comentario con fundamento frente a elogio genérico seguido de pitch: preguntas `noul` y umbrales descartan el segundo; `criterion_sources` contiene solo unidades cargadas. |
  | `BIB-09-semanal` / analista al resumir | `LI-06-V008-K01`, `LI-06-V008-K02` | Caen likes de 7 días frente a público medido a 90: no compara ventanas incompatibles ni cambia la dirección solo por likes; cita curso y separa cifras. |
  | `BIB-09-posicionamiento` / posicionamiento para perfil | `LI-01-M006-K02`, `LI-02-V021-K01` | Trayectoria extensa y público con problema concreto: explica ayuda/transformación con evidencia, señala datos faltantes y no convierte años de experiencia en una promesa de resultados. |
  | `BIB-09-perfil` / Perfil, completo y mensual | `LI-02-V015-K03`, `LI-02-V019-K01`, `LI-02-M011-K01`, `LI-02-M015-K03` | Perfil centrado en cargos y destacados obsoletos: Markdown propone utilidad primero, experiencias reales, destacados pertinentes y URL sin cargo; cada recomendación cita sus unidades. Reutiliza el cargo acreditado, pregunta una vez por una fecha imprescindible ausente y omite prueba social no verificable. Propone frase inglesa del banner desde posicionamiento/curso, con texto del tablero solo como fallback válido; no escribe LinkedIn. |
  | `BIB-09-visual-perfil` / visual como herramienta de Perfil | `LI-02-V011-K02`, `LI-02-V014-K06`, `LI-02-V015-K02`, `LI-02-V021-K01` | Fixtures sintéticos de 01–03 y ninguna charla en memoria: entrega A en grises y B en color con pose/sonrisa de 01, camiseta/gafas acordadas e identidad de 03; banner usa cuerpo de 02 e identidad de 03. Evalúa ojos/móvil/rostro por variante, sonrisa de 01 en A/B/banner y transitions claras de 03, y deja elegir a Gustavo. Micrófono etiquetado como estilo en Markdown, sin «speaker» ni pruebas inventadas. No usa imagen externa de Diandra ni incorpora fotos reales a fixtures del repo; Perfil y derivados quedan fuera de posts. Las decisiones de estilo son de Gustavo, no citas atribuidas al curso. |

- **Criterios de aceptación:**
  1. **Dado** cada caso de la tabla, **cuando** se evalúa con fixtures locales, **entonces** se construye el mismo contexto/esquema que producción y se comprueban decisión, regla concreta, evidencia y citas conocidas; una salida con citas correctas y conducta contraria falla.
  2. **Dado** la migración del harness, **cuando** se ejecuta sin opt-in pagado, **entonces** produce previsualización/estimación o usa proveedores simulados; no publica, envía invitaciones ni crea tareas de negocio. Una evaluación real requiere `execute`, `max_usd` y `EVAL_LIMIT_USD`, y se contabiliza.
  3. **Dado** unidades ausentes, una cita inventada, lista de clase 07 o criterio Jev desconectado de su petición, **cuando** se valida, **entonces** el caso falla e identifica el rol/versión; no se activa como fundamentado hasta corregirlo.
- **Brechas código/docs:** el harness existente comprueba cinco entradas y espejos de peticiones; los casos nuevos y sus umbrales de evaluación aún no están implementados. No se afirma haber ejecutado estas evaluaciones en esta tarea.
- **Cobertura QA:** pendiente

## Retiradas

### BIB-06 · Enriquecer capturas cuando lo requiere su destino <a id="bib-06"></a>

- **Dónde:** backend
- **Estado:** no implementado
- **Retirada:** 8 de noviembre de 2026, por el addendum explícito de Gustavo: procesar capturas no necesita biblioteca. ID reservado, no reutilizar. La ficha nunca se implementó.
- **Alcance retirado:** añadir un enriquecimiento propio posterior a la captura. Editorial/Perfil pueden usar el curso al realizar su trabajo habitual sobre una idea recibida, sin otro agente, consulta o presupuesto específico de Capturas.
- **Qué hace para Gustavo (diseño retirado):** una idea capturada llegaría al equipo acompañada de criterios útiles del curso, manteniendo intactas su nota y su intención.
- **Responsable:** rol destinatario, `director_editorial` para ideas y `perfil`/`posicionamiento` para sus preguntas; el ruteador resolvía el envío.
- **Cadencia:** se proponía una vez por versión tras guardar/enrutar; no se implementará esta cadencia adicional.
- **Tu turno:** se contemplaban preguntas por información o destino ambiguo; el retiro no añade tareas ni cambia el flujo actual de Capturas.
- **Datos necesarios y disponibilidad:** texto, transcripción, fotos, propósito y contexto existen; el enriquecimiento propio no se implementó. Enlaces siguen dependiendo de la fase web, independiente de esta retirada.
- **Código:** no existe; referencias históricas `capturas.classify/process`, `ideas_for_director` y `knowledge/retrieval.py`.
- **Criterios de aceptación históricos, retirados:**
  1. **Dado** una nota «Idea para un post», **cuando** el director la preparase como insumo, **entonces** podría consultar unidades y adjuntar sugerencias con citas en un artefacto separado, conservando el original.
  2. **Dado** subida de foto, transcripción o destino conocido, **cuando** se guardase/enrutase, **entonces** no necesitaría consultar el curso para completar esa operación.
  3. **Dado** una captura con enlace, **cuando** necesitase su contenido, **entonces** usaría la salida trazable de la fase web, separada de las unidades del curso.
  4. **Dado** biblioteca caída o sin resultados, **cuando** terminase el envío, **entonces** la captura seguiría guardada, con enriquecimiento pendiente/vacío y sin duplicar ideas al reintentar.
- **Brechas código/docs:** estos criterios se conservan como historia de la ficha retirada, no como trabajo pendiente ni exigencia de QA. La conducta vigente es no añadir consumo propio de biblioteca a Capturas.
- **Cobertura QA:** no aplica a una función retirada.
