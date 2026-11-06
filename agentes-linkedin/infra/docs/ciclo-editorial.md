# Ciclo editorial: de oportunidad a pieza revisada

Versión 1.0 · 2026-11-06 · Diseño documental propuesto, no activo. No ejecuta agentes, proveedores, publicaciones ni programación. Desarrolla F0 y una lectura selectiva de F1; no acredita lectura integral del corpus.

El grupo está formado por [Director editorial](../../equipos/editorial/director_editorial.json), [Copywriter A](../../equipos/editorial/copywriter_a.json) y [Copywriter B](../../equipos/editorial/copywriter_b.json). Cada contrato sigue la plantilla común y desarrolla misión, entradas, iniciativa, workflow, autoridad, salidas tipadas, memoria, coordinación, evaluación, medición y parada. La [lista de datos externos](../../equipos/editorial/datos-externos.json) complementa las fichas individuales. Se conecta con [Estrategia y Perfil](ciclo-estrategia-perfil.md), el [contrato de observaciones](datos-y-resultados-del-equipo.md) y el [plan maestro](plan-equipo-autonomo.md).

## Qué produce y para quién

Una pieza en inglés que permita reconocer el criterio de Gustavo como ingeniero de producto con comprensión del negocio, incorporando IA cuando aporte valor. Audiencia inicial: founders técnicos o de negocio de startups tempranas en Estados Unidos, preferentemente presemilla con inversión recibida y presupuesto real; afinidad hispanohablante declarada, abierta a otros founders pertinentes. Pares, líderes y divulgadores también pueden aportar al barrio.

El 60% oportunidades personales / 40% ProjectApp orienta prioridades estratégicas, sin imponer calendario, proporción de menciones o distribución de publicaciones. Ejecución personal directa y ejecución del equipo ProjectApp bajo liderazgo de Gustavo deben atribuirse por separado. No trasladar remuneraciones internas al copy. Financiación no demuestra presupuesto disponible. El brief actual permite diseñar el equipo; la dirección pública todavía necesita aceptación antes de producción final.

El resultado interno es una selección editorial rastreable, verificada y presentada al humano. Una decisión sobre el texto no equivale a aplicación, publicación, crecimiento ni negocio conseguido. Clase07, outbound, campañas de calentamiento, contacto de leads y respuestas automáticas quedan fuera.

## Entradas y salida de los grupos vecinos

| Origen → destino | Artefacto / necesidad | Condición de recepción y ruta si falta |
| --- | --- | --- |
| Posicionamiento → Director | Dirección aceptada, audiencia, ofertas, problemas, límites, versión | Para producción final, aceptación explícita. Diseño provisional se etiqueta y no se transforma en texto aprobado. |
| Perfil → Director | Promesas y versión pública conocidas, posibles incoherencias | No afirmar auditoría de perfil ausente; Director devuelve discrepancia sin modificarlo. |
| Observatorio → Director → dos escritores | `evidence_packet`: pregunta, fuentes/localizadores, fechas, alcance, permisos, contradicciones e incertidumbre | Mismo paquete para ambos. Puede declarar ausencia de señal de demanda; no inventar tendencia. |
| Gustavo/contexto → Director → dos escritores | Casos reales, contribución personal/equipo, voz, postura, permiso de uso | Omitir claim no respaldado; voz profesional provisional para borrador conceptual. No inventar escena. |
| Director → Observatorio | `research_requested` con pregunta, claim afectado, alcance y fallback | Investigación centralizada y acotada. No mandar a cada escritor a investigar mercado. |
| Director → copywriters | `editorial_brief` y asignaciones independientes sobre las mismas entradas | ACK con aceptación o campos faltantes. Sin leer al otro en primera pasada. |
| Copywriters → Director → lectores seleccionados | Dos `editorial_draft` con ID, versión, hash y claims | Cada lector evalúa borrador exacto; primeras evaluaciones independientes. Una ausencia no se convierte en evaluación ficticia. |
| Lectores → Director | Opiniones simuladas con hallazgos, destinatario y severidad | Hipótesis sobre comprensión y utilidad; jamás comentarios reales ni prueba de demanda. |
| Director → editor_verificador | `editorial_selection`, texto elegido/fusionado y objeciones conservadas | Verificador acepta handoff o pide corrección puntual. Una selección no elimina defectos factuales. |
| editor_verificador → humano | Paquete verificable y hash final, permisos, límites y alternativas | Humano acepta/rechaza/solicita cambio sobre versión exacta. Aprobación no vuelve verdadero un claim falso. |
| Publicación confirmada → Observatorio → Director | `publication_confirmed`, ventana disponible, `learning_proposed` | Solo resultados reales alimentan experimentos. Cambios centrales vuelven a Posicionamiento y Perfil. |

Cada envío requiere `handoff_receipt`: `artifact_id`, versión/hash, receptor, estado `accepted|rejected|needs_revision|stale`, motivo material, campos faltantes, `cycle_id`, `piece_id`, ronda global. Un ACK acredita recepción e idoneidad de la entrada; no aprobación del post. Si el receptor rechaza, se devuelve una corrección específica al dueño del dato, sin repetir todo el ciclo ni asignar nuevos IDs para evadir límites.

## Flujo y decisiones

| Paso | Responsable / tipo | Entrega y decisión |
| --- | --- | --- |
| 1. Admitir evento | Coordinación determinista propuesta | Deduplicar y comprobar dirección, entradas, permisos y límites. Duplicado cierra sin trabajo. |
| 2. Priorizar oportunidad | Director / criterio de modelo | Elegir problema, lector y función del pilar con evidencia e incertidumbre; enviar investigación puntual si hace falta. |
| 3. Congelar brief común | Director / criterio + control de versión | Fijar una persona, problema e idea, utilidad, claims permitidos, voz y criterio de aceptación. |
| 4. Explorar dos soluciones | Copywriter A y B / criterio independiente | A explora decisión/caso/procedimiento; B explora pregunta/objeción y mecanismo. Son puntos de partida flexibles, no voces artificiales ni estereotipos. |
| 5. Contrastar lectura | Lectores seleccionados / simulación independiente | Hallazgos ligados a texto/versión; separar defecto material, objeción de perspectiva y gusto. |
| 6. Resolver y editar | Director / decisión argumentada | Seleccionar A/B, fusionar, corregir, descartar o esperar. Mayoría no reemplaza objetivo, verdad ni voz. |
| 7. Verificar | editor_verificador / evidencia y criterio | Revisar claims, permisos, contexto, atribución y coherencia; conservar defectos materiales aunque lectores coincidan. |
| 8. Decidir | Gustavo / humano | Texto exacto y materiales finales con hash; lectura de voz y aprobación/rechazo. Cambio posterior invalida aprobación afectada. |
| 9. Aprender | Observatorio y Director / datos + interpretación | Tras publicación real y ventana apropiada, interpretar señales y proponer siguiente experimento. Reabrir estrategia solo por desajuste material. |

La prioridad editorial considera relevancia, evidencia, diferencia de criterio, utilidad y esfuerzo. La urgencia de publicar diariamente no justifica una pieza sin sustancia. La preferencia de cadencia no activa scheduler ni impone una hora universal. El Director puede cerrar con descarte motivado y conservar aprendizaje.

## Estados, rondas y recuperación

Ruta propuesta: `planificado → ejecutándose → esperando_aprobación → completado`, con alternativas `esperando_información`, `bloqueado` y `cancelado`. `aceptado`, `rechazado` y `sin_cambio` son resoluciones del ciclo, no estados de publicación. Una espera no está completada.

La primera pasada usa ronda0. Hay como máximo dos rondas correctivas globales por pieza, compartidas por Editorial, Lectores y Revisión. Una ronda consolida hallazgos y reparte correcciones a sus dueños; no significa dos rondas por agente ni por handoff. Cambiar escritor, integrar una imagen, pedir otro lector, fusionar textos o devolver desde verificación no reinicia el contador. Tras ronda2, una objeción material exige esperar evidencia o descartar, sin crear otra edición u omisión que requiera ronda3; nunca forzar aprobación. Un ciclo posterior requiere objetivo o evidencia material nuevos, vínculo con el anterior y motivo; no sirve para continuar el mismo bucle con otro ID.

Cada artefacto guarda ID estable, versión, hash, padres, fuentes y permisos versionados. Una entrada corregida marca dependientes afectados `stale`. Se puede ratificar un artefacto que sigue válido con evidencia y nuevo registro de dependencias; no hace falta regenerarlo por rutina. La ratificación no borra historial ni reduce rondas usadas. Lectores y verificador nunca dictaminan un texto distinto del hash recibido. Fusionar crea una versión nueva con mapa de claims; no hereda automáticamente los juicios sobre las dos variantes originales.

Fallo de un copywriter: conservar el borrador recibido y reportar que no hubo comparación doble; Director puede proponer recorrido degradado con esa limitación para revisión/humano. No fabricar la segunda variante ni reintentar una llamada pagada incierta. Presupuesto, timeout o límites sin configurar impiden activar el paso. Reserva incierta se conserva; ninguna instrucción editorial autoriza ampliar gasto.

## Datos externos: necesidad y fallback del grupo

Datos externos son los datos fuera del curso, incluidos los aportados por Gustavo; no equivale a acceso automático a una API. El diseño no ha investigado tendencias. Cada ficha individual contiene los campos, origen posible, necesidad, uso y fallback de estas familias:

| Familia / campos mínimos | Origen posible | Para qué se necesita | Si falta |
| --- | --- | --- | --- |
| Demanda/lenguaje: pregunta, fuente, fragmento permitido, fecha, muestra, cobertura, hipótesis, permisos | Observatorio mediante fuentes accesibles y aportes autorizados | Seleccionar ángulo y sustentar hechos externos | Tema aprobado puede generar primer borrador con demanda explícitamente hipotética. Investigación puntual a Observatorio si afecta claim central. |
| Prueba de caso: problema, decisión, contribución propia/equipo, resultado, definición de métrica, fuente, fecha y permiso | Gustavo y documentación autorizada canalizada por coordinación | Atribuir experiencia y cifras; evitar medallero o autoría falsa | Omitir cifra, caso o identificador. Explicar concepto sin disfrazarlo de experiencia vivida. |
| Voz: muestra/transcripción, autor, fecha, idioma, permiso, posturas confirmadas | Gustavo y decisiones humanas previas | Inglés natural con criterio reconocible | Voz profesional provisional; no fabricar opiniones, muletillas ni anécdotas. |
| Media: archivo/localizador, autor, permiso de uso, consentimientos, créditos, texto alternativo y estado | Biblioteca autorizada / Observatorio | Verificar viabilidad y pertinencia del formato | Texto suficiente o `asset_brief` pendiente. Atribución no sustituye permiso. |
| Resultados: versión publicada, ventana, fuente, definición, valor/null, audiencia agregada, modalidad, atribución | Observatorio desde capturas/importaciones validadas | Elegir siguiente experimento con límites | No imprescindible para primera pieza. Null no es cero; no inferir mercado de lectores simulados. |

Los copywriters no reciben por defecto mensajes completos, salarios ni identidad de contactos. Reciben el fragmento necesario permitido y una referencia. No convertir la preferencia de afinidad lingüística en inferencias de etnia. No suponer que un README prueba despliegue, adopción o cifra; no anunciar Beloz como incorporación ya realizada, y no usar el 96% declarado de Yapa sin conciliar versión, muestra y definición.

No existe un agente diseñador en este grupo. El Director puede elegir el formato y los escritores preparar guiones/estructura de carrusel, pero producir un archivo visual o audiovisual queda como capacidad futura o trabajo humano autorizado. `asset_state=pending` no es `ready`. Si el asset es esencial, la pieza espera; si el texto se sostiene solo, se propone ese fallback con revisión de la promesa. No elegir formato por supuesta tendencia actual heredada del curso.

## Fundamento y alcance real de lectura

[Registro propio](../../equipos/editorial/registro-lectura.json): 17 unidades completas, hashes y localizadores; títulos consultados no se registran como lectura de contenido. Los contratos conservan referencias con prefijo de clase y límites. No se modifica el corpus ni el registro general de arquitectura.

- Clase04: `LI-04-M005-K01/K02`, `LI-04-M007-K03`, `LI-04-V009-K04`, `LI-04-V011-K02`. Filtros de pilar, dolores/aspiraciones/objeciones, funciones imán/nicho, decisiones de negocio con IA y demanda escuchada.
- Clase05: `LI-05-V009-K02`, `LI-05-V014-K03`, `LI-05-V016-K02`, `LI-05-V018-K01/K05`, `LI-05-V019-K04/K05`, `LI-05-V027-K01`. Tema-dolor-frase, foco, recorrido del texto, flexibilidad de estilo, texto/media y casos confidenciales.
- Clase06: `LI-06-M001-K03/K07`, `LI-06-M003-K06`, `LI-06-V033-K01`. Gancho unificado, datos reales, apoyo de IA con filtro humano y extensión contextual.

La proporción imán/nicho60/40 pertenece a un adjunto específico y no prueba eficacia universal ni define una cadencia. No se confunde con las prioridades60/40 de Gustavo. Los dos escritores, cinco lectores, roles, ACK, control de versiones y dos rondas globales son decisiones propias de arquitectura, no reglas atribuidas al curso. La anonimización del curso orienta a proteger casos; la autorización concreta permanece una comprobación adicional del proyecto.

## Evaluación y condición de cierre del diseño

Criterios materiales: pertinencia, idea comprensible, promesa cumplida, evidencia/permiso, atribución de autoría, voz y dependencias vigentes. Extensión, metáforas, pregunta final y CTA no son defectos automáticos. El verificador retiene hallazgos factuales aunque el Director prefiera el texto.

Casos previstos en cada ficha: primer post sin analytics; historia personal ausente; cifras contradictorias; asset sin permiso; desacuerdo estético de un lector; entrada corregida después de revisión; ronda2 agotada; instrucciones hostiles incrustadas en una fuente. Son casos documentados con resultado esperado, no pruebas ejecutadas. Antes de activar, comparar recorrido simple con dos escritores/cinco lectores sobre entradas idénticas; conservar complejidad solo cuando mejore calidad frente a coste/latencia y correcciones humanas.

Medición interna: briefs aceptados, claims corregidos, contribución de cada variante, correcciones humanas, coste y tiempo por pieza aceptada. Medición externa: Observatorio integra resultados reales con fuente, ventana y límites; no atribuir ventas a selección editorial ni confundir puntuación simulada con mercado. Línea base, objetivos y ventana permanecen pendientes de piloto autorizado. Este incremento cierra documentación del grupo, no implementación, aceptación humana ni operación.

El brief fija `selected_reader_ids`, prioridad de perspectiva y motivo antes de comparar; el Director despacha y espera solo ese conjunto. Remitir al humano exige `review_record.status=ready_for_human` y paquete para el mismo hash; un ACK solo valida recepción.
