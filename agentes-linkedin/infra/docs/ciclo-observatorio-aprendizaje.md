# Ciclos de Observatorio, barrio y aprendizaje

Versión 1.0 · 2026-11-06 · **Propuesta documental, no activa ni implementada.** No activa agentes, conectores, llamadas pagadas, scheduler, comentarios, mensajes, conexiones ni publicación. Clases 01–06; clase 07 y outbound excluidos. Diseño conectado con [plan maestro](plan-equipo-autonomo.md), [contexto de Gustavo](brief-gustavo-posicionamiento.md), [Estrategia/Perfil](ciclo-estrategia-perfil.md) y [observaciones](datos-y-resultados-del-equipo.md).

Este grupo contiene dos responsabilidades: [investigador_referentes](../../equipos/observatorio/investigador_referentes.json) descubre y contrasta comunidades, referentes y asuntos; [analista_barrio_resultados](../../equipos/observatorio/analista_barrio_resultados.json) escucha e interpreta respuestas, propone participación orgánica y cierra el aprendizaje. No son procesos permanentes: una pregunta sencilla puede resolverse con un rol y un artefacto, sin activar ambos.

## Contexto que gobierna las decisiones

Gustavo es founder de ProjectApp y busca ingeniería de producto con criterio de negocio e IA cuando aporte valor. Prioridad de esfuerzo: 60% oportunidades personales y 40% contratos ProjectApp; no cuota por post, ranking, ingresos ni número de perfiles. En personal ejecuta directamente; en ProjectApp ejecuta el equipo bajo su liderazgo. Mercado inicial USA, startups tempranas preferentemente presemilla financiadas y con presupuesto. Inglés público, afinidad hispanohablante/latinoamericana sin inferir etnia/idioma por nombre o imagen ni excluir a otros founders pertinentes.

No deducir presupuesto disponible de una ronda, disponibilidad de una banda salarial ni capacidad del equipo de la disponibilidad personal. La referencia interna personal de USD 5.000–7.999/mes para tiempo completo no es tarifa de ProjectApp ni regla automática para parcial. Casos del brief son declaraciones y documentación selectiva; no resultados validados ni permisos de publicación implícitos.

## Conocimiento leído y límite de cobertura

[Registro propio](../../equipos/observatorio/registro-lectura.json): 29 unidades completas seleccionadas, con ID, hash de base, origen, pointer, interpretación y límites. Distribución: 2 clase 01, 12 clase 03 y 15 clase 06. Se leyeron originales completos mediante `knowledge.db.connect`, `SET TRANSACTION READ ONLY` y consulta `SELECT id,session,title,original,sha256,source_path,pointer FROM units WHERE active ...`. Se repitieron lotes truncados en lotes menores. Índices/títulos no cuentan como lectura; referencias visuales dentro de una unidad no acreditan inspección de imágenes.

Esto fundamenta las reglas citadas aquí; **no acredita lectura integral del corpus, de clases completas ni de toda unidad potencialmente pertinente**. F1 sigue parcial. Nuevas decisiones sobre temas no leídos requieren ampliar evidencia; no reutilizar una referencia solo por su título.

| Criterio pedagógico | Unidades leídas | Excepción conservada |
| --- | --- | --- |
| Entender comprador y articular ofertas | LI-01-M006-K02; LI-01-V022-K02 | Motivo de compra requiere evidencia; dos ofertas no obligan una proporción de posts |
| Barrio diverso y filtro de pertinencia | LI-03-M001-K02; M003-K06/K07; M005-K05/K06 | Referencias completas en JSON; no cuota, exclusividad ni mínimo de seguidores |
| Referentes y descubrimiento en conversaciones | LI-03-V009-K04; V018-K02; V022-K01 | IA sugiere, no verifica; otras redes son vías candidatas, no importación garantizada |
| Escucha, comentarios y cuentas de distintos tamaños | LI-03-M004-K04; V020-K02/K04/K05 | Postura/fundamento/apertura; relato horario no regla algorítmica; todo queda propuesto |
| Escuchar tras publicar y reconocer público | LI-06-V006-K03/K04; V007-K01/K05; V008-K01 | Motivos de guardados/visitas son interpretación; audiencia no equivale a compradores |
| Ventanas, exposición y acciones | LI-06-V008-K02/K03; V009-K02/K03/K04; V010-K02 | No impresiones=lecturas; no sumar únicos ni inventar fórmula de engagement |
| Nicho y experimentación situada | LI-06-V026-K05; V029-K02; V033-K02/K03 | Nicho no garantiza originalidad; series sin mínimo universal; vídeos/horarios no recetas |

Eventos, esquemas, verificación de fuentes, sesgos, privacidad, estados y límites son diseño propio. No se atribuyen al curso. El contenido del curso describe interfaces y observaciones de su momento: no confirma APIs, disponibilidad de exportaciones ni funcionamiento actual del algoritmo.

## Datos externos que necesita el grupo

Los campos exactos, metadatos comunes y políticas están en `datos_externos` de cada contrato. Todas las fuentes son **candidatas no verificadas**; esta tarea no consultó fuentes externas. Inicio viable: material seleccionado por Gustavo, capturas/manual e importaciones disponibles. API/conector se considerará únicamente después de comprobar capacidad, permisos, alcance y definición de datos; no promesa de scraping ni acceso a inbox/analytics completos.

| ID | Agente | Datos y decisión | Necesidad/fallback |
| --- | --- | --- | --- |
| OBS-EXT-01 | Investigador | Perfiles, cargo/contexto, temas, actividad fechada, URL verificada, papel propuesto, evidencia de audiencia y ruta de descubrimiento | Para recomendar personas reales se exige identidad/localizador y evidencia; tamaño/idioma/distintivo opcionales. Sin acceso: plan de búsqueda, no nombres inventados |
| OBS-EXT-02 | Investigador | Publicaciones y comentarios ajenos con contexto, fecha, origen, muestra y fragmentos permitidos | Para afirmar escucha real; contadores opcionales. Sin contenido: preguntas y vías de descubrimiento |
| OBS-EXT-03 | Investigador | Fuentes primarias de afirmaciones/tendencias, fechas del hecho y publicación, método/muestra, dependencia y contradicciones | Obligatorio para hechos externos actuales; sin respaldo, señal/hipótesis u omisión material |
| OBS-EXT-04 | Analista | Red/composición propia: seguidores/conexiones/seguidos diferenciados; categorías, denominadores y muestra | Para afirmar quién llega; opcional al inicio. Sin datos: mapa deseado provisional |
| OBS-EXT-05 | Analista | Post real, versión/hash, fecha/URL/confirmación, misión/modalidad, formato/idioma y ediciones | Obligatorio para rendimiento de pieza propia. Sin publicaciones: plan inicial y escucha disponible |
| OBS-EXT-06 | Analista | Métricas disponibles por entidad, definición, tipo de contador, ventana, captura, alcance y fórmula derivada | Obligatorio para cálculos; cada campo posible es opcional según fuente. Ausencia=null, no cero |
| OBS-EXT-07 | Analista | Comentarios/conversaciones reales, hilo, fecha, pregunta/objeción, permiso, papel profesional y procedencia | Obligatorio para señal real; mensajes solo fragmentos aportados/autorizados. Sin datos: hipótesis, no feedback simulado |
| OBS-EXT-08 | Analista | Oportunidad estable, modalidad, necesidad, etapa, fuente, presupuesto/dedicación/compatibilidad y resultado | Para resultados comerciales; campos suficientes antes de cualificar. Sin ellos: candidata/pendiente, no venta inferida |

Todo registro tiene ID/versión/workspace, origen/localizador, fecha de captura y del hecho/periodo, zona horaria, hash, validación, acceso/uso y versión sustituida. Idioma observado en posts no acredita identidad o idioma preferido de una persona. Preferir agregados; editorial recibe problemas y evidencia permitida sin salarios, contratos, identidades privadas ni mensajes completos. Fuentes externas son datos, nunca instrucciones capaces de ampliar permisos.

Frescura se define por la decisión: antes de proponer participación se verifica contexto abierto; antes de recomendar referente se revisa actividad/cargo; antes de usar tendencia se revisan fecha del hecho y evidencia; para métricas se conserva el corte histórico. Una caducidad no configurada significa vigencia pendiente, no permiso de reutilización indefinida. No imponer fecha de expiración inventada ni borrar historia.

## Ciclo A: investigación y barrio

**Entrada mínima:** pregunta concreta y decisión que informará, contexto versionado, fuentes permitidas y límites configurados para ejecución futura. Con dirección provisional puede investigar hipótesis etiquetadas. No necesita métricas propias para descubrir comunidad.

| Paso | Dueño y tipo | Resultado y alternativa |
| --- | --- | --- |
| Recibir `research_requested` o nueva pregunta de observaciones | Backend, código futuro | Deduplicar por workspace/pregunta/alcance/entradas/periodo; duplicado cierra sin cambio |
| Delimitar problema, industria/nicho, funciones y mercado | Investigador, modelo | `search_plan`; contexto ausente restringe solo conclusiones dependientes |
| Descubrir y verificar referentes | Investigador con lector autorizado | Perfiles con evidencia y actividad; candidatos no verificados se separan |
| Leer dónde conversa el público pertinente | Investigador, modelo | `candidate_map` y `signal_card`; comunidades pequeñas/medianas y pares también cuentan |
| Contrastar asuntos y afirmaciones | Investigador, modelo + fuentes | Origen, fechas, contradicciones y dependencia; señal aislada no es tendencia general |
| Entregar evidencia y pregunta siguiente | Investigador → analista/editorial | `research_packet` con límites o respuesta parcial; ninguna interacción externa |
| Proponer aporte orgánico, si el material lo permite | Analista, modelo | `organic_participation_proposal` como borrador para verificador y después Gustavo; ejecución separada, sin enviar |

La selección valora relación con problema/cliente, conversación que reúne, actividad y aporte posible. Tamaño es contexto, no filtro decisivo. Una etiqueta oficial Top Voice solo se conserva si se verificó a fecha; «referente de nicho» es juicio del equipo con razones. La fama no prueba que el público buscado lea sus publicaciones.

Diseño de muestra: registrar consulta/semilla, vías de descubrimiento, ventana, criterio de inclusión/exclusión, piezas/autores observados y faltantes. Buscar contraste de papeles, tamaños y ámbitos cuando la muestra esté concentrada; no fabricar una cuota. Examinar también contradicciones y participantes menos visibles. Varias copias de un anuncio no son fuentes independientes. El feed y una selección manual sesgan la muestra; no estimar mercado total ni prevalencia sin un diseño que lo permita.

Cierre: pregunta respondida dentro del alcance, límite alcanzado con hallazgos parciales o falta de fuente explicitada. No exige cierto número de referentes. La ruta sin acceso externo termina con `search_plan`, no con una lista pretendidamente investigada.

## Ciclo B: aprendizaje tras actividad real

**Entrada mínima para rendimiento:** publicación confirmada, versión exacta y observaciones validadas con ventana/definiciones. `publication_confirmed` puede crear un plan pendiente, pero no resultados. El cierre de una ventana sin observaciones nuevas no provoca una llamada pagada.

| Paso | Dueño y tipo | Resultado y alternativa |
| --- | --- | --- |
| Recibir lote/corrección | Captura + backend, código futuro | Validar, deduplicar, preservar conflictos y revisiones; no sobrescribir evidencia |
| Calcular solo métricas compatibles | Backend, código | Conteos/deltas/ratios trazables; datos faltantes y denominadores cero producen null |
| Delimitar alcance de la lectura | Analista, modelo | `observation_packet`: periodo, cobertura, faltantes y confusores |
| Escuchar y separar dimensiones | Analista, modelo | Exposición, acciones, audiencia, preguntas y negocio por modalidad |
| Interpretar según propósito y contexto | Analista, modelo | Hechos frente a hipótesis; comparación compatible o descripciones separadas |
| Proponer siguiente decisión | Analista → responsable | `learning_proposal`: mantener, ajuste acotado, experimento, investigación o evidencia insuficiente |
| Elegir siguiente pieza/experimento | Dirección editorial, modelo; humano donde corresponda | Brief/plan versionados; no ejecución automática ni resultado validado |
| Escalar cambio central | Posicionamiento → Gustavo | Decisión sobre dirección; no sustituir identidad por ruido de un post |

La interpretación diferencia para qué sirve cada señal. Una objeción puede ser más útil para la próxima pieza que muchos likes. Un guardado sugiere utilidad pero no prueba su motivo. La audiencia incluye pares, recomendadores y divulgadores; no se marca incorrecta solo por no comprar. Una pieza de nicho se evalúa por propósito y destinatario, no por alcance de una reflexión general.

Oportunidades personales y ProjectApp tienen registros separados, etapas con historial y compatibilidad explícita. Conversación, entrevista, oferta, contrato firmado, trabajo iniciado e ingreso recibido son eventos distintos. No contar mensajes como oportunidades nuevas. Referencia explícita a una publicación o declaración del interesado apoya una asociación, no causalidad exclusiva. Un resultado posterior a publicar puede tener otros orígenes.

## Decisiones según fuerza de evidencia

| Decisión | Evidencia necesaria | Salida cuando falta |
| --- | --- | --- |
| Describir una observación | Registro real con fuente, contexto, fecha y permiso | No observado / dato pendiente |
| Proponer tema o comentario | Señal contextual pertinente y aporte fundamentado | Pregunta de investigación, sin simular necesidad real |
| Comparar piezas | Misión, edad/ventana, definiciones, alcance y confusores visibles | Descripciones separadas; no ganador |
| Formular patrón o tendencia | Recurrencia en muestra descrita, fuentes diferenciadas, contexto temporal y contradicciones examinadas | Señal aislada o hipótesis; no extrapolación a mercado |
| Recomendar un ajuste editorial persistente | Patrón pertinente, alternativas consideradas y criterio de observación previo | Experimento acotado o mantener hipótesis abierta |
| Cambiar posicionamiento | Evidencia contextual relevante para objetivo + propuesta de estrategia + decisión de Gustavo | Conservar dirección y devolver duda concreta |
| Cualificar oportunidad | Necesidad expresa, modalidad, presupuesto/dedicación y compatibilidad suficientes | Candidata/pendiente, no cualificada |

No hay tamaño de muestra mágico. Una observación puede justificar explorar una pregunta; no demuestra causalidad ni frecuencia. La suficiencia depende del alcance de la decisión y del tipo/calidad de evidencia. No elegir el umbral después de ver el resultado ni reemplazar evidencia con unanimidad entre agentes.

## Ruta inicial sin métricas

1. Inventariar qué material existe y qué no: posts, comentarios, red, oportunidades y capacidad de captura. No pedir trabajo manual por cada like.
2. Usar conversaciones reales permitidas para hipótesis y preguntas; si tampoco existen, elaborar plan de búsqueda/captura con contexto confirmado.
3. Proponer línea base y ventana según objetivo y disponibilidad; ambas pendientes hasta datos reales. No rellenar dashboard ni declarar cero resultados.
4. Entregar tema/brief provisional con sustento, límites y prueba que se querría observar. Lectores simulados solo generan objeciones hipotéticas.
5. Al llegar publicación confirmada y datos nuevos, activar únicamente la rama pertinente del aprendizaje.

## Plan de experimento y retorno al equipo

`experiment_plan` contiene hipótesis, decisión que informa, cambio acotado, misión/modalidad/lector, variable y comparador, métricas con definiciones, fuentes, periodo y edad de comparación, confusores, criterio de decisión fijado antes del resultado, límites y parada. Elegir una serie viable puede ayudar a aprender; el curso no fija cuántas piezas ni garantiza control experimental. Si varían tema, formato y horario simultáneamente, declarar que no se puede aislar un efecto. Un cambio rechazado o sin datos suficientes también se registra; no insistir indefinidamente hasta obtener un resultado favorable.

| Hallazgo | Handoff | Autoridad final |
| --- | --- | --- |
| Pregunta/objeción real aprovechable | Editorial con fragmento permitido, contexto y misión | Dirección editorial elige pieza; publicación requiere revisión humana |
| Necesidad de verificar referente o tendencia | Investigador con pregunta concreta y límite | Investigador devuelve evidencia, no campaña |
| Confusión entre ejecución personal y equipo | Perfil y Posicionamiento con evidencia | Gustavo decide dirección y texto exactos |
| Oportunidad relevante incompatible en horas | Contexto/cualificación, no automáticamente alcance | Gustavo evalúa disponibilidad/condiciones |
| Comentario orgánico pertinente | Borrador contextual al verificador y después Gustavo | Autorizar/aplicar es paso separado; aquí no se ejecuta |
| Mucha exposición y poco registro comercial | Examinar cobertura, misión y pertinencia | No se deduce fracaso ni cambio automático |

## Artefactos, eventos y versiones

Todos los artefactos incluyen ID, versión, hash, workspace, ciclo/correlación, autor/versión de contrato, fecha, tipo/estado, entradas ID/versión/hash, fuentes/localizador/fechas/permisos, hechos, hipótesis, faltantes, límites, decisión/motivo, destinatario, referencia de aprobación y de aplicación separadas, y versión sustituida. Los JSON detallan campos por tipo. Una aprobación no convierte una afirmación falsa en verdadera ni demuestra que una acción se ejecutó.

Eventos internos propuestos a normalizar con el circuito transversal: `research_requested`, `research_completed`, `observation_batch_validated`, `publication_confirmed`, `observation_window_ready`, `learning_proposed`, `editorial_opportunity_proposed` y `organic_participation_proposed` (artefacto `organic_participation_proposal` al verificador, con contexto del hilo versionado). `context_confirmed` notifica cambio de contexto pertinente. Son especificación documental, no eventos emitidos por el backend actual.

Envelope propuesto: `event_id`, `event_type`, `schema_version`, `workspace_id`, `cycle_id`, `correlation_id`, `causation_id`, `occurred_at`, `actor`, `input_refs`, `payload_hash`, `deduplication_key`. Dedupe se aplica antes de invocar modelos. Revisión candidata de observación exige validación; solo entonces se notifica nuevo lote y se revisan dependientes. Cambiar una entrada marca artefactos afectados como desactualizados, conservando historia y permitiendo ratificar lo que siga válido.

## Autonomía, límites y estados

Autonomía futura propuesta: seleccionar evidencia dentro del alcance autorizado, formular hipótesis, elegir siguiente paso interno y cerrar sin cambio. El backend valida permisos, versiones y límites antes de ejecutar. Nada de ello se activa al guardar estos contratos. Los agentes no envían mensajes, comentarios, invitaciones o campañas. El punto de integración outbound permanece inactivo y sin procedimientos derivados de clases 07+.

Estados compatibles con Estrategia/Perfil: `planificado`, `ejecutándose`, `esperando_información`, `esperando_aprobación`, `bloqueado`, `completado`, `cancelado`. `sin_cambio`, `aceptado`, `rechazado` y `evidencia_insuficiente` describen resolución, no estado operativo. Entregar un informe descriptivo suficiente puede completar su pregunta; una propuesta esperando decisión humana no está completada. Objetivo comercial alcanzado y ejecución externa son registros distintos.

Dos rondas es límite **global propuesto por ciclo/pieza**, incluyendo revisiones/handoffs/subciclos; no se reinicia al cambiar agente. Fuentes, pasos, duración, tokens y presupuesto se configuran antes de ejecutar. Límite sin configurar no significa ilimitado. Falta de permiso o dato bloquea solo el paso dependiente. Un fallo pagado incierto conserva reserva/estado y no se reintenta automáticamente.

Parar al responder la pregunta, agotar alcance/límite, encontrar duplicado/sin novedad, perder acceso, recibir cancelación o requerir dato/decisión indispensable. Escalar desacuerdo material con alternativas y consecuencias; no declararlo resuelto por promedio, acuerdo de lectores o preferencia estética.

## Evaluación propuesta y estado del incremento

Los contratos incluyen casos adversos con resultado esperado: referente inventado, cuenta grande irrelevante, cinco copias de una noticia, idioma inferido, datos ausentes, snapshots duplicados, ratio sin denominador, muestras incomparables, publicación no confirmada, comentario negativo, startup financiada sin compatibilidad, corrección de observaciones, simulación confundida con audiencia real y límite de rondas trasladado entre agentes.

Rúbrica material: procedencia completa, incertidumbre visible, respeto de modalidades y privacidad, cálculo correcto y separado, ausencia de acciones externas y handoff accionable. Una invención o violación de permisos bloquea aceptación de la salida afectada; no se compensa con estilo. Preferencias de orden/estética no bloquean. Comparar utilidad y coste contra una respuesta sencilla de un solo rol antes de multiplicar colaboración.

En esta tarea: contratos y registro revisados como documentos; JSON parseables y referencias de lectura verificadas localmente. No se ejecutaron agentes, escenarios de proveedor, pruebas de backend ni experimento de mercado. Los casos de evaluación permanecen propuestos, no aprobados ni superados por un sistema operativo. Pendientes: aceptación de diseño, ampliar lectura según decisiones, verificar fuentes, fijar captura/cadencia/límites e implementar/evaluar.

Reglas transversales: [circuito común](circuitos-equipo.md). El hash de entradas para deduplicación incluye pregunta/entidad, alcance y ventana; un nuevo ID de evento no habilita repetir trabajo. Ronda0 es la elaboración inicial; ronda1/2 son correctivas compartidas. La verificación final de ronda2 ocurre, pero si falla no permite otra edición u omisión; esperar evidencia o descartar.
