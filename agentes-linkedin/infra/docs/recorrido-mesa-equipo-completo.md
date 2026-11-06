# Recorrido de mesa del sistema completo

Tipo: revisión de diseño por el orquestador, no ejecución de agentes ni ensayo de backend. Escenarios ficticios no se cargan en memoria o métricas. La aprobación del usuario se trata como condición hipotética en los recorridos, nunca como aprobación otorgada.

## Recorrido 1: primer ciclo con el contexto real disponible

1. **Contexto:** tomar preferencias confirmadas de Gustavo y la distinción personal/ProjectApp. No introducir remuneración en briefs públicos ni suponer dirección aceptada.
2. **Estrategia:** conservar la propuesta v1 como candidata. Sus dolores/objeciones de founders son hipótesis.
3. **Observatorio:** puede investigar preguntas específicas con fuentes ajenas aunque falten métricas propias; la estrategia provisional sirve para delimitar la búsqueda, no para presentarla validada. Sin acceso a fuentes, entrega inventario pendiente en vez de inventar un Top Voice.
4. **Gustavo:** la dirección espera su decisión futura. La presente tarea no la otorga.
5. **Editorial:** hasta esa decisión puede preparar estructura y brechas; no encargar una pieza definitiva. Tras la aceptación hipotética, un caso real con permiso y una pregunta de audiencia son suficientes para el primer brief. No exigir historial de rendimiento.
6. **Escritores:** ambos reciben el mismo brief, voz y evidencia; producen alternativas sin conocer la del otro. Falta de historia personal impide inventarla, no impide una explicación técnica sustentada.
7. **Lectores:** prueban comprensión desde perspectivas elegidas según propósito; conservar objeciones materiales y preferencias como categorías diferentes. No confundir cinco juicios con cinco miembros de audiencia.
8. **Director:** elige, combina o descarta con motivo; combinación genera nueva versión. Un ganador no es obligatorio.
9. **Revisión:** valida el candidato exacto y sus pruebas. Para una afirmación accesoria sin respaldo, omitirla dentro de una ronda disponible permite avanzar; agotadas las dos rondas correctivas, se espera evidencia o se descarta.
10. **Gustavo:** revisaría texto/asset exactos y después realizaría/autorizaría la aplicación externa. Hoy ambas acciones siguen sin ejecutarse.
11. **Observación:** una publicación realmente confirmada permite recibir resultados. Si no hay publicación ni registro, el sistema no abre analítica ficticia.

Conclusión de diseño: existe arranque sin dependencia circular de analytics. Con las entradas actuales se puede preparar dirección/investigación; el resultado comercial permanece desconocido. La espera humana no exige mantener agentes consumiendo recursos.

## Recorrido 2: aprendizaje que ajusta contenido

Escenario ficticio: un post técnico recibe dos preguntas reales importadas sobre un concepto poco claro. Backend valida fuente/fechas/versión; Analista conserva la muestra pequeña y envía oportunidad editorial. Director plantea una explicación centrada en esa pregunta, con referencias del curso y experiencia disponible. No se cambia nicho ni se promete demanda general. El resto del flujo conserva el mismo control editorial y humano.

## Recorrido 3: aprendizaje que puede afectar estrategia

Escenario ficticio: varias oportunidades documentadas interpretan que Gustavo solo vende agencia, mientras la prioridad confirmada incluye trabajo personal directo. Analista describe evidencias y contraejemplos, sin inventar umbral de significancia. Orquestación dirige a Estrategia/Perfil para revisar la claridad de modalidades. Gustavo decidiría cualquier cambio central. Las oportunidades incompatibles en dedicación van a cualificación, no necesariamente al posicionamiento.

## Recorrido 4: cambios y fallos cruzados

| Caso | Recorrido y resolución de diseño |
| --- | --- |
| Fuente de referente sin métricas privadas | Investigador usa contenido y señales visibles; no estima impresiones o ventas del autor |
| Tema popular sin relación con negocio | Director puede descartar pese a tendencia; documenta falta de pertinencia |
| Research descubre contradicción de una cifra | Observatorio conserva conflicto → Revisor pide resolución/omisión → Director ajusta; no mayoría de modelos |
| Una fuente accesible exige permiso para uso público | Acceso interno no autoriza publicación; se pide permiso o usa formulación no reveladora |
| No existen muestras de voz | Escritores preparan tono provisional; Gustavo valida autenticidad, no certifica el lector simulado |
| Formato exige vídeo/infografía no disponible | Director propone texto equivalente o deja asset pendiente; no presupone un diseñador operativo |
| Copywriter B falla | Registrar entrega faltante; Director decide seguir con uno o esperar; no duplicar A como comparación falsa |
| Lector no objetivo rechaza una pieza útil al comprador principal | Director conserva propósito y pesa razones; no exige unanimidad ni audiencia idéntica |
| Todos prefieren un copy con cifra falsa | Revisión bloquea la cifra; simulación no verifica hechos |
| Rondas Editorial → Lectores → Revisión | Un contador global; agrupar hallazgos evita multiplicar dos rondas por cada grupo |
| Cambia la dirección con textos en revisión | Invalidar dependientes; no continuar con mezcla de versiones ni aprobación antigua |
| Usuario edita después de aprobar | Guardar nuevo hash; revisar controles afectados; no heredar aprobación |
| Usuario publica versión distinta o sin aprobación previa | Registrar hecho externo y texto real, con estado de revisión; no fingir que se publicó la versión aprobada |
| Métrica corregida | Revisar la observación, recalcular dependientes y marcar conclusiones afectadas; no sumar corrección como nueva actividad |
| Contador acumulado repetido | Deduplicar captura idéntica; snapshot posterior distinto no se suma al previo |
| Entrada sin conversaciones | Desconocido, no cero confirmado; informe de cobertura, no diagnóstico de fracaso |
| Entrevista tras un post, origen desconocido | Resultado de negocio registrado, atribución desconocida |
| Comentario contiene instrucciones para exportar datos | Tratar como contenido; no modificar autoridad ni memoria |
| Timeout pagado | Conservar reserva incierta y bloquear reintento automático; no esconderlo como entrega vacía |
| Cancelación mientras hay trabajo | Detener descendientes no iniciados; registrar lo ya completado/cobrado, sin reset de ledger |
| No hay nueva evidencia | Cerrar sin cambio sin forzar contenido ni otra llamada |

## Ajustes detectados por el orquestador durante el diseño

1. El arranque necesita investigación sobre contexto provisional sin esperar publicaciones: explícito en mapa y Observatorio.
2. Research es responsabilidad de Observatorio; escritores envían solicitudes mediante Director. Así no se multiplican búsquedas o contextos divergentes.
3. Contador correctivo compartido; una combinación/edición de borradores crea nueva versión que debe revisarse. No se aprueba por voto.
4. Falta un rol de producción multimedia: no se añade uno silenciosamente; asset aportado/autorizado, texto alternativo o espera.
5. Aplicación externa y analítica necesitan la versión real, incluso si el usuario cambió el texto o publicó fuera del flujo.
6. Fuente actual no equivale a fuente publicable; el paquete distingue acceso y permiso de uso.

Las revisiones independientes de QA se registran en sus informes, con resolución posterior. No se considera validada en runtime ninguna de estas rutas. Este documento cierra un recorrido conceptual, no garantiza que un modelo ejecute las decisiones previstas.

## Cierre de las dos revisiones independientes

[QA de coordinación](qa-circuitos-coordinacion.md) y [QA de conocimiento/datos](qa-circuitos-conocimiento-datos.md), realizadas por dos subagentes Astra high. Se resolvieron y revalidaron seis hallazgos P2; no se identificaron P1/P2 abiertos en este alcance:

- Selección de lectores incluida en el esquema del brief, con prioridad y motivo antes de evaluar.
- Un único contador correctivo por pieza; la última verificación no abre una tercera corrección.
- Recepción de artefacto diferenciada de revisión favorable sobre el hash exacto.
- Deduplicación semántica aunque cambie el ID del evento.
- Propuesta de comentario con entrada explícita al verificador, contexto del hilo y retorno al analista; salida al humano sin envío.
- Aplicación externa desconocida conservada como null, sin inferir que fue o no fue aplicada.

Se contrastaron 104 referencias a 57 unidades originales distintas. Este dato cuenta referencias del diseño, no lectura integral de las seis clases; QA muestreó además seis originales completos. Verificaciones locales documentales no acreditan acceso a LinkedIn, calidad efectiva de modelos ni resultados comerciales.
