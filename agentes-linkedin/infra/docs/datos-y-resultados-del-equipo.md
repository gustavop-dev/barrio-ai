# Cómo recibe datos y resultados el equipo

Estado: contrato de diseño, sin integración automática activada.

## Flujo

Fuentes reales → captura/importación → validación y almacenamiento estructurado → paquete de observaciones → interpretación del Observatorio → decisión del ciclo pertinente → propuesta/aprobación → cambio aplicado → nuevas observaciones.

Los modelos no deben sumar contadores ni inventar métricas a partir de impresiones subjetivas. El backend calcula números; los agentes interpretan con contexto. Los números viven en registros estructurados, no exclusivamente como embeddings. Comentarios y evidencias textuales pueden indexarse para recuperación, conservando el original y sus permisos.

## Cuatro familias de información

| Familia | Ejemplos | Fuente inicial prevista | Para qué sirve |
| --- | --- | --- | --- |
| Contexto y decisiones | Objetivos, ofertas, disponibilidad, posicionamiento aceptado | Respuestas de Gustavo y decisiones versionadas | Define qué es una oportunidad pertinente |
| Actividad y exposición | Publicación real, fecha, impresiones, alcance, seguidores, visitas cuando estén disponibles | Registro manual, captura o exportación disponible en la cuenta | Conocer actividad y distribución |
| Respuesta y audiencia | Comentarios, preguntas, objeciones, datos de composición disponibles | Texto/enlaces aportados e importaciones habilitadas | Entender quién responde y qué entiende |
| Resultado de negocio | Conversación pertinente, entrevista, propuesta, oferta, contrato | Registro de Gustavo o conector autorizado y verificado | Evaluar oportunidades personales y ProjectApp por separado |

No todos los campos estarán disponibles en LinkedIn o en un conector. Esta tabla expresa necesidades de datos, no capacidades confirmadas de una API. No existe aquí acceso automático a mensajes, analytics o historial completo. Una conversación puede ocurrir fuera de LinkedIn; se conserva su canal.

## Primera captura: sencilla y controlable

Diseñar una bandeja en la oficina con dos acciones principales:

1. **Añadir resultados de LinkedIn:** seleccionar perfil/publicación y pegar valores, adjuntar captura o importar archivo cuando exista. Ver un resumen antes de aceptar extracción de datos. OCR/IA propone; no convierte una lectura dudosa en cifra confirmada.
2. **Registrar una oportunidad:** seleccionar personal / ProjectApp / por clasificar; canal; fecha; etapa; motivo de interés; compatibilidad; origen conocido o desconocido. Añadir solo el fragmento necesario para entender una objeción o intención, no una copia indiscriminada de mensajes.

Esas pantallas están por implementar. Hasta entonces, una tabla/importación de prueba puede usar el mismo contrato. Conectores posteriores producirán los mismos registros normalizados, después de comprobar acceso, permisos y alcance; no cambiarán el significado de las métricas.

No pedir una carga manual por cada like. Agrupar actividad y resultados por la ventana acordada, conservando eventos importantes. La periodicidad se definirá con Gustavo; publicar diariamente no obliga a revisar el posicionamiento diariamente.

## Registro de observación

Campos mínimos: `observation_id`, propietario/workspace, `source`, localizador de evidencia, fecha de captura, intervalo observado y zona horaria, entidad (perfil/post/conversación/oportunidad), métrica/evento, valor/unidad, alcance de medición y estado de validación. Metadatos: importación, hash, clave de deduplicación, versión sustituida y explicación de corrección.

Para contadores: indicar `snapshot_acumulado`, `total_del_periodo` o `evento`. Dos capturas acumuladas de la misma publicación no se suman. Una diferencia entre snapshots solo se calcula si entidad, definición y alcance son compatibles. Conservar ajustes del proveedor sin convertir valores negativos inesperados en crecimiento positivo.

`null` significa desconocido/no disponible; `0` solo representa cero observado explícitamente. Un archivo sin comentarios no demuestra cero comentarios. Fechas de captura y de publicación son distintas. Comparar posts a una edad equivalente o declarar que la comparación tiene distinta exposición.

No sumar miembros alcanzados de publicaciones distintas como personas únicas del perfil. No confundir impresiones con lecturas. El crecimiento neto entre dos snapshots no prueba quién llegó ni cuántas altas y bajas hubo. Cualquier ratio debe guardar fórmula, numerador, denominador y ventana; si el denominador es cero o falta, el resultado es no disponible.

## Registro de conversación y oportunidad

Identificador estable propio; canal, fecha, referente mínimo de persona/organización; modalidad; etapa; evidencia; quién registró; presupuesto/compensación y dedicación si se conocen; motivo de pertinencia; compatibilidad confirmada o pendiente; siguiente acción y estado.

Etapas propuestas: conversación → necesidad identificada → oportunidad cualificada → entrevista/reunión → propuesta/oferta → acuerdo confirmado → cerrada sin acuerdo. Permitir saltos respaldados por evidencia, historial y reapertura. No contar cada mensaje como una conversación nueva ni sumar snapshots de etapas como oportunidades distintas.

Cualificada significa que hay una necesidad expresa, una modalidad pertinente y datos suficientes de presupuesto y dedicación/compatibilidad; si faltan, queda candidata o pendiente. Para contratación personal, una banda atractiva no demuestra compatibilidad. Para ProjectApp, presupuesto y capacidad se evalúan como equipo.

Procedencia de oportunidad: referencia explícita a post/perfil, declaración de la persona, inferencia o desconocida. Solo las dos primeras respaldan una asociación documentada, y aun así no prueban causalidad exclusiva. Una oferta posterior a publicar no es automáticamente una conversión de ese post.

No inferir origen étnico ni idioma por nombre/foto. Afinidad lingüística solo con información declarada; una persona puede desempeñar varios papeles del barrio. Recibir una conversación no autoriza campañas ni respuestas automáticas; outbound sigue fuera del alcance.

## Qué recibe cada agente

- Posicionamiento: composición agregada, oportunidades por modalidad y compatibilidad, objeciones documentadas, límites y contexto confirmado.
- Perfil: dudas de comprensión y desajustes entre mensaje prometido y consultas reales, versiones de perfil y fechas de cambios.
- Editorial/copywriters: preguntas y temas pertinentes, resultados comparables de contenido y pruebas autorizadas. No reciben por defecto salarios, identidad privada de contactos ni mensajes completos.
- Lectores simulados: brief y borrador; sus valoraciones permanecen simulaciones, nunca se almacenan como comentarios reales.
- Revisión: afirmaciones y fuentes necesarias, con acceso autorizado; no amplía permisos por ser revisor.

El paquete de resultados incluye periodo, cobertura, datos faltantes, conteos calculados, ejemplos permitidos, hipótesis y conflictos. Las cifras y sus fuentes se enlazan; un resumen generado no sustituye el registro original.

## Medición del propósito

Principal: oportunidades pertinentes por modalidad, entrevistas/propuestas/ofertas y acuerdos confirmados, compatibilidad y valor cuando se conozca. Separar trabajo conseguido, contrato firmado e ingreso recibido: no son el mismo evento.

Apoyo: audiencia relevante, crecimiento, exposición, participación y conversaciones. La relevancia no se reduce a compradores: pares y divulgadores pueden contribuir al objetivo. Interacción abundante sin oportunidades exige investigar, no concluir automáticamente que es inútil.

Operación del equipo: coste por ciclo, tiempo, intervención humana, afirmaciones corregidas y entregables aceptados. No mezclar la calidad técnica del workflow con crecimiento de LinkedIn.

Primera tarea de medición: establecer línea base real y disponibilidad de campos. Objetivos cuantitativos y ventanas se fijarán con esa información; no inventar resultados para completar un dashboard.

## Correcciones tras el recorrido de mesa — versión 1.1

Identidad y revisión se separan. La identidad de origen/localizador, entidad, métrica, intervalo y tipo permite reconocer el registro; el hash del payload reconoce repetición exacta. Identidad y payload idénticos se ignoran como duplicado. Identidad igual con payload distinto se presenta como revisión candidata con origen y explicación: no sumar ni sobrescribir silenciosamente. Al validarla se conserva la versión anterior y se invalidan para revisión los cálculos/decisiones dependientes. Conflictos entre fuentes se conservan separados hasta resolverlos.

Los snapshots posteriores conservan su fecha de captura; no se confunden con una corrección del snapshot anterior. Métricas, oportunidades y opiniones simuladas usan tipos separados; un importador no puede convertir una evaluación de lector simulado en comentario real.
