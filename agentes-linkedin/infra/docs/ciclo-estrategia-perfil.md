# Contrato operativo: ciclo de Estrategia y Perfil

Versión 1. Estado: diseño revisable de F0, no implementado. Referencia: [plan maestro](plan-equipo-autonomo.md). Datos reales de entrada y resultados: [contrato de observaciones](datos-y-resultados-del-equipo.md). Evaluación propuesta: [casos](../../arquitectura/evaluacion-ciclo-estrategia-perfil.json).

## Propósito y límites

Mantener una dirección de posicionamiento y una propuesta de perfil coherentes con Gustavo, sus dos modalidades y la evidencia disponible. Medir el ciclo por la calidad y trazabilidad de sus decisiones; medir el objetivo de negocio por oportunidades reales, sin confundir ambos resultados.

Prioridad confirmada: 60% oportunidades personales en startups / 40% ProjectApp. Ejecución directa personal versus ejecución de equipo bajo su liderazgo. Inglés público, Estados Unidos y afinidad inicial hispanohablante/latinoamericana. No cambiar estas preferencias por una fluctuación de likes. El 60/40 no es una regla de distribución de publicaciones ni de ingresos.

Fuentes pedagógicas ya leídas: LI-01-M006-K02/K03 (comprador), LI-01-M007-K03/K04 (mensaje y comprobación), LI-01-V022-K02 (ofertas articuladas), LI-02-V016-K01/K05 (titular y misión), LI-02-V019-K01/K02 (experiencia), LI-06-V007-K05 (composición del público y revisión de perfil/contenido). Hashes y alcance en los registros existentes de arquitectura. El mecanismo de estados, versiones y eventos es diseño propio, no prescripción del curso.

## Entradas y contratos de entrega

| Entrada | Obligatoria | Si falta |
| --- | --- | --- |
| Versión del objetivo y contexto confirmado | Sí | Esperar información; consolidar preguntas concretas |
| Modalidades y preferencias | Sí para la decisión afectada | No inventar; continuar solo decisiones independientes |
| Referencias del curso con contexto y límites | Sí | Investigar unidades; no resolver mediante regla inventada |
| Evidencia de experiencia | Para afirmaciones de trayectoria/resultados | Omitir afirmación o mantenerla pendiente |
| Perfil actual con fecha y origen | Para diagnosticar diferencias reales | Se puede proponer estructura; no afirmar auditoría del perfil |
| Observaciones de audiencia/contenido/conversaciones | Para revisar resultados | Primer diseño permitido sin métricas; revisión de resultados queda pendiente |
| Política de permisos y presupuesto vigente | Para ejecución | Bloquear paso que no esté autorizado; no ampliar límites |

Cada entrada tiene ID, versión y procedencia. Un mensaje confirmado de Gustavo acredita sus preferencias y su testimonio; no convierte toda cifra de un caso en resultado independientemente verificado.

Entregables versionados:

1. `decision_packet`: disparador, pregunta a resolver, entradas, hechos, hipótesis, evidencia faltante y límites.
2. `positioning_proposal`: audiencias, problemas/transformaciones/objeciones, ofertas, asociación profesional y razones. Campos hipotéticos identificados.
3. `profile_proposal`: referencia exacta a positioning_proposal, textos/estructura propuestos, afirmaciones y evidencia, vacíos devueltos.
4. `review_record`: criterios, defectos materiales, preferencias menores, decisiones y responsable.
5. `decision_record`: aprobación/rechazo/pedido de ajuste de Gustavo sobre versiones concretas; motivo y alcance.
6. `measurement_plan`: hipótesis que se observará, señal, fuente, ventana, comparación válida y limitaciones; no contiene resultados ficticios.

Todos conservan `artifact_id`, versión, ciclo, autor, entradas versionadas, fecha, fuentes, estado y destinatario. `aprobado`, `aplicado` y `publicado` son estados distintos: aprobar una propuesta no prueba que LinkedIn haya cambiado.

## Disparadores y selección del siguiente paso

- Nuevo contexto confirmado o corrección de Gustavo: revisar solo decisiones afectadas.
- Primer diseño solicitado: crear propuesta aunque no exista historial de métricas.
- Nueva evidencia que respalda o contradice una afirmación: revisar la afirmación y sus dependientes.
- Informe de resultados con patrón relevante: evaluar si exige ajuste de mensaje, de contenido o de público.
- Solicitud explícita del usuario.

Un temporizador puede revisar si hay datos nuevos, una vez que exista cadencia autorizada. No genera por sí solo una llamada al modelo. Datos repetidos, ventanas incomparables o falta de evidencia nueva no disparan una nueva propuesta. No hay scheduler activado por este documento.

## Secuencia y autoridad

| Paso | Responsable | Tipo | Salida / ruta alternativa |
| --- | --- | --- | --- |
| 1. Recibir y deduplicar evento | Backend | Código | Evento nuevo o cierre sin trabajo por duplicado |
| 2. Comprobar versiones, permisos, coste y dependencias | Backend | Código | Entradas listas o bloqueo explícito |
| 3. Interpretar qué decisión necesita revisión | Orquestación | Modelo acotado | decision_packet o no cambiar con motivo |
| 4. Recuperar evidencia pertinente | Posicionamiento y recuperación | Modelo + código | Contexto trazable; ampliar búsqueda dentro de límites |
| 5. Proponer dirección o conservar la vigente | Posicionamiento | Modelo | positioning_proposal con hipótesis y alternativas |
| 6. Traducir a perfil y detectar vacíos | Perfil | Modelo | profile_proposal; devuelve dudas estratégicas sin redefinir audiencia |
| 7. Revisar coherencia y afirmaciones | Revisión del ciclo | Código + criterio de modelo | Defectos materiales, cambios concretos o listo para decisión |
| 8. Resolver correcciones | Dueño de la decisión | Modelo acotado | Máximo dos rondas propuestas; desacuerdo material se escala |
| 9. Aceptar o ajustar dirección/textos | Gustavo | Humano | decision_record ligado a versiones exactas |
| 10. Guardar y definir observación | Backend + orquestación | Código + modelo | Cierre de propuesta; medición pendiente si aún no se aplicó |

Revisión es una función necesaria; no exige implementar otro agente permanente ahora. En la primera prueba puede realizarse mediante rúbrica y revisión humana. Posicionamiento resuelve audiencia/oferta; Perfil resuelve claridad de presentación. Revisor no impone gustos estéticos como defectos bloqueantes.

Correcciones del usuario prevalecen sobre hipótesis previas. Si cambia una entrada durante la revisión, conservar el trabajo pero marcar dependientes como desactualizados. No ejecutar con una mezcla silenciosa de versiones.

## Estados y condiciones de parada

`planificado → ejecutándose → esperando_aprobación → completado` es la ruta de una propuesta suficiente y aceptada. Rutas alternativas: `esperando_información`, `bloqueado`, `cancelado`.

- Completado: propuesta decidida y registro conservado; no significa autoridad o crecimiento alcanzados.
- Esperando información: pregunta concreta que afecta una decisión; no reiniciar todo ni repetirla automáticamente.
- Bloqueado: límite económico, fallo técnico, permiso ausente o dependencia inaccesible; registrar acción necesaria.
- Rechazo de Gustavo: conservar propuesta rechazada; nueva versión si aporta dirección, o cierre con rechazo si no desea continuar.
- Dos rondas sin resolver una objeción material: esperar decisión de Gustavo con alternativas y consecuencias.
- Timeout de proveedor: conservar estado/reserva incierta y no repetir automáticamente.
- No hay nueva evidencia o cambio necesario: cerrar la evaluación como `sin_cambio`, sin alterar el posicionamiento vigente.

La implementación fijará también límites por pasos, tokens y duración dentro del presupuesto vigente. No se asignan cifras de gasto nuevas aquí.

## Cómo vuelve la información del mundo real

Observatorio prepara un paquete de resultados a partir de registros verificables, separando hechos de interpretación. El orquestador clasifica la respuesta:

- Una pieza poco clara: devolver a Editorial; no cambiar de nicho automáticamente.
- Audiencia amplia con recomendadores y pares: puede ser coherente con el barrio, aunque no todos compren.
- Confusión repetida entre contratación personal y agencia: candidato a revisión del perfil y diferenciación de modalidades.
- Ofertas pertinentes pero incompatibles en dedicación: revisar cualificación/disponibilidad, no concluir que falta alcance.
- Sin conversaciones u ofertas registradas: distinguir cero confirmado de falta de registro; no concluir fracaso del posicionamiento.

No hay umbral de conversión o tamaño de muestra inventado. El primer plan de observación deberá acordar una ventana y registrar las limitaciones de cualquier conclusión con pocos casos. No cambiar estrategia solo por mayoría entre agentes.

## Criterios para cerrar este incremento de diseño

Contrato y responsabilidades definidos; entradas/salidas trazables; reglas de espera y parada; interfaz de observaciones; casos de evaluación preparados. Su aceptación y ejecución de pruebas aún están pendientes. F0 global sigue parcial: faltan contratos detallados de los otros ciclos. La lectura F1 de las especialidades tampoco se considera terminada.

Siguiente incremento: recorrido de mesa del caso de Gustavo con datos ficticios claramente separados para los escenarios de fallo, sin proveedores ni publicación. Luego preparar contratos faltantes y el cambio técnico de F3. No adelantar la generación de nuevos titulares como sustituto de estas verificaciones.

## Correcciones tras el recorrido de mesa — versión 1.1

Estas precisiones sustituyen cualquier ambigüedad de la secuencia anterior:

1. **Dos puntos de decisión:** entre Posicionamiento y el desarrollo final de Perfil se requiere aceptación de la dirección por Gustavo. Perfil puede hacer revisión de coherencia preliminar con estado provisional. Después se revisa y aprueba el texto exacto; aplicar/publicar requiere una acción autorizada separada. La instrucción de probar este ciclo no es aprobación del contenido.
2. **Estado y resolución:** `sin_cambio` es una resolución, no un estado operativo. Un ciclo `completado` registra `aceptado`, `rechazado` o `sin_cambio`. Una espera de información/aprobación no está completada. Cancelar no equivale a rechazar una propuesta. Guardar aplicación y resultados externos por separado.
3. **Dependencias y bloqueos acotados:** una afirmación material sin evidencia se omite o permanece pendiente; no bloquea los componentes independientes. Tras dos rondas se escalan alternativas, sin aceptar como verificada una afirmación por el solo hecho de aprobación humana. Un presupuesto, permiso o límite sin configurar impide activar el paso pagado; no significa ilimitado.
4. **Cambio de versión:** una aprobación identifica el hash/versión exactos del artefacto y de la dirección aceptada. Una corrección de datos o del contexto marca solo dependientes afectados para revisión. La revisión permite confirmar que un artefacto sigue válido, con registro; no exige regenerarlo siempre.

Resultado de diseño: [recorrido de mesa](recorrido-mesa-estrategia-perfil.md). Realizado por el asistente; pruebas de backend y agentes pendientes. Siguiente incremento: contrato de Observatorio/aprendizaje, continuando F0 global.

Regla global de rondas: una omisión o cambio de texto requiere ronda disponible; tras la verificación final de ronda2 fallida solo esperar evidencia o descartar, sin ronda3 implícita. El documento circuitos-equipo.md precisa el contador compartido y la diferencia entre ACK y aprobación de contenido.
