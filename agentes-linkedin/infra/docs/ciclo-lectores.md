# Ciclo de la mesa de lectores

Estado: contrato propuesto, no activo. Cinco roles: par, recomendador, líder, comprador y divulgador. Las fichas están en `equipos/lectores/`. Basado en LI-03-M005-K05 (papeles no excluyentes), LI-05-V005-K05 (perspectiva ajena) y LI-06-V020-K01 (no sustituir consumidor por gusto propio). Convertir esas perspectivas en agentes es decisión de arquitectura; no lo prescribe el curso.

## Entrada y activación

`draft_pair_ready`: Director entrega dos borradores independientes del mismo brief vigente, audiencia principal, propósito, fuentes permitidas, restricciones y versión. Si solo hay un borrador por fallo, no se inventa el segundo: el Director registra degradación y puede solicitar lectura individual con su motivo. Cinco roles disponibles, sin obligación de ejecutar los cinco en cada pieza; el subset y perspectiva prioritaria se fijan en el brief antes de comparar.

Datos externos: no necesitan iniciar sesión en LinkedIn. Usan extractos autorizados del lenguaje de audiencia (D06), pruebas (D03) y voz (D09) que reciban. Si no existen datos de audiencia, la simulación se etiqueta provisional. No inventar demografía ni opiniones de referentes reales.

## Flujo y salida

1. Validar hash del brief y de cada borrador; si falta contexto de propósito, devolver defecto de entrada.
2. Cada lector evalúa sin conocer autor A/B ni juicios ajenos cuando se pueda neutralizar ese sesgo. Identificadores opacos conservan trazabilidad interna.
3. Entregar `reader_assessment`: perspectiva, fragmento, criterio, objeción, tipo (material/preferencia/falta de dato), sugerencia y límites. Puede declarar ambos adecuados, ambos insuficientes o sin evidencia para preferir.
4. Director recibe evaluaciones, distingue objetivos del post y objeciones. Puede pedir contraste sobre una discrepancia concreta; no conversación abierta sin propósito.
5. Contraste conserva primera evaluación y revisión posterior. Ningún voto obliga a cambiar de audiencia o a publicar. Director selecciona/combina/descarta y pasa candidato a Revisión.

El lector comprador utiliza una modalidad primaria (personal o ProjectApp); el par revisa utilidad técnica; el recomendador, claridad para recomendar; el líder, criterio propio; el divulgador, valor compartible y claridad. No exigir que un solo post satisfaga por igual todas las perspectivas.

## Conexiones y control

Receptor único de decisiones: Director. Los lectores no envían órdenes directamente a escritores ni abren una segunda investigación paralela. Datos faltantes vuelven al Director, que agrupa solicitud para Observatorio o Gustavo. Revisor puede consultar objeciones sin convertirlas en evidencia externa.

Se usa contador global de dos rondas correctivas por pieza; evaluación inicial no es una ronda correctiva. Una ronda agrupa hallazgos de todos los grupos y un nuevo candidato. Lectores no reinician el contador cambiando nombre de tarea. Al cambiar una premisa sustantiva se cierra el intento y se solicita al orquestador una nueva pieza con parentesco y justificación; no se usa para eludir límites de coste ni provocar reintentos automáticos.

Entrada desactualizada → detener y devolver `stale_input`. Sin objeción material → entregar y detener, no buscar fallos cosméticos. Con discrepancia material tras límite → Director propone descarte/espera de evidencia; la resolución humana no certifica hechos no probados.

## Evaluación prevista

Casos: unanimidad con cifra inventada (no aprobable); comprador no objetivo reclama otro producto (no manda); voces privadas innecesarias (no compartir); ambos textos insuficientes (ningún ganador obligatorio); cambio de brief durante debate (invalidar); cinco juicios simulados (cero observaciones reales creadas). Resultado esperado es razonamiento útil, no predicción de engagement. El recorrido global y QA registran evaluación de diseño aparte de futura ejecución.

Regla global de rondas: una omisión o cambio de texto requiere ronda disponible; tras la verificación final de ronda2 fallida solo esperar evidencia o descartar, sin ronda3 implícita. El documento circuitos-equipo.md precisa el contador compartido y la diferencia entre ACK y aprobación de contenido.
