# Recorrido de mesa — Estrategia y Perfil

Estado: revisión de diseño realizada por el asistente; no ejecución de agentes, prueba de Django ni evaluación humana independiente. Sin solicitudes a proveedores, métricas importadas o cambios en LinkedIn. Los escenarios ficticios se mantienen en artefactos de evaluación.

## 1. Recorrido con el contexto real de Gustavo

Entrada fijada: brief personal vigente, propuesta de posicionamiento v1 y unidades de conocimiento referenciadas. Preferencias confirmadas: 60/40; ingeniería de producto e IA; startups tempranas con presupuesto; inglés; ejecución personal directa; ProjectApp como oferta separada; sumar colaboraciones compatibles. Disponibilidad exacta, línea base, perfil actual capturado y validación de los casos permanecen incompletos.

| Paso | Decisión tomada en esta revisión de mesa | Entrega / estado |
| --- | --- | --- |
| Contexto | Las preferencias bastan para diseñar una dirección. La falta de métricas no impide esa propuesta. | Entrada suficiente para diseño; resultados de mercado desconocidos |
| Selección de objetivo | La petición vigente es probar el ciclo, no aprobar el titular de la propuesta anterior. | No registrar aprobación implícita |
| Posicionamiento | Reutilizar v1 como borrador, con problemas y objeciones de founders etiquetados como hipótesis. | No volver a generar por generar; pendiente decisión de dirección |
| Entrega a Perfil | Perfil puede examinar coherencia provisional, pero no cerrar una versión definitiva sobre estrategia sin aprobar. | Se permite análisis preparatorio; publicación y cierre definitivos bloqueados por dependencia |
| Pruebas de trayectoria | No introducir “96%” global, RFID desplegado o relación directa con cadenas sin aclarar la evidencia correspondiente. | Bloquear esas afirmaciones concretas, no todo el documento |
| Revisión | La distinción entre trabajo personal y equipo debe preservar la aclaración más reciente. “Product Engineer” es una propuesta de presentación, no un cargo histórico acreditado. | Mantener modalidad real; no inventar experiencia |
| Decisión humana | No existe aceptación del eje o textos concretos en esta tarea. | Estado simulado: esperando aprobación de dirección, sin formularla como permiso para esta revisión |
| Observación posterior | Sin evidencia de aplicación del perfil no hay fecha de inicio del supuesto cambio. | Measurement plan pendiente de línea base/aplicación; no registrar cero conversaciones |

El recorrido llega a una espera válida, no a un resultado comercial ni a un perfil publicado. La prueba de mesa puede completarse aunque el ciclo de producto siga esperando una decisión futura. No se necesita una API de LinkedIn para descubrir estos problemas de coordinación.

## 2. Vacíos encontrados y corregidos en los contratos

### D1. Aprobación estratégica demasiado tardía

La secuencia original llevaba a Perfil hasta una propuesta completa antes de distinguir aprobación de dirección y aprobación de textos. Eso podía producir retrabajo y tratar una hipótesis como posicionamiento definitivo.

Corrección: dos decisiones distintas. Gustavo acepta la dirección; Perfil desarrolla la versión final sobre esa referencia. Puede hacer una revisión preliminar antes, claramente provisional. Aprobar el texto no implica aprobar su publicación, y una edición no hereda aprobación de otra versión.

### D2. Resultado del ciclo mezclado con su estado

Se usaba `sin_cambio` como cierre sin precisar si era estado adicional. También había ambigüedad sobre si el rechazo obligaba a reabrir indefinidamente.

Corrección: separar estado operativo de resolución. `completado` con resolución `sin_cambio`, `aceptado` o `rechazado`; cancelación es estado propio. Esperando aprobación/información no cuenta como completado. La aplicación externa y los resultados de negocio se registran por separado.

### D3. Evidencia insuficiente podía bloquear demasiado o terminar aprobándose por cansancio

El límite de dos rondas no decía con suficiente precisión qué ocurría si el usuario prefería continuar sin respaldar una cifra, ni cómo permitir avances independientes.

Corrección: bloquear la afirmación afectada; proponer omitirla o redactar solo lo que puede sostenerse. La aprobación humana no convierte una afirmación no respaldada en evidencia verificada. No se bloquea una propuesta completa por un caso accesorio prescindible. Tras dos rondas se espera información o decisión sobre alternativas, sin inventar consenso.

### D4. Una corrección de importación podía confundirse con duplicado

El contrato exigía deduplicación pero dejaba sin concretar su diferencia con corregir el mismo registro y cómo propagar ese cambio.

Corrección: mismo registro y payload idéntico es duplicado; mismo registro con contenido distinto es revisión candidata, no suma ni sustitución silenciosa. Tras validación sustituye la versión previa, conserva historial y marca informes dependientes para revisión. Una captura posterior de un contador es otro snapshot, no otro evento de negocio.

## 3. Resultado de los 15 escenarios

La matriz detallada en `arquitectura/evaluacion-ciclo-estrategia-perfil.json` registra para cada caso la decisión de mesa y su fundamento. Resultado: 11 casos tenían una ruta especificada y 4 necesitaron precisión del contrato (duplicados, versiones, dos rondas y aprobación/publicación). Tras las correcciones, los 15 tienen una resolución de diseño explícita.

Esto no significa “15 tests pasaron”: no se ejecutó código de coordinación ni se midieron respuestas de modelos. La implementación todavía podría incumplir cualquiera de estas reglas; estos casos deberán transformarse en pruebas de comportamiento cuando exista.

## 4. Qué continúa pendiente

- Pruebas técnicas de transiciones, permisos, concurrencia, deduplicación, reserva incierta e invalidación por versión.
- Evaluación real de agentes: recuperación de fuentes, respeto a hipótesis, calidad de decisiones y resistencia a instrucciones en fuentes externas.
- Decidir parámetros operativos antes de activar: pasos, duración, tokens, límites vigentes y cadencia; el contrato no autoriza valores ilimitados por omisión.
- Línea base de LinkedIn y captura de oportunidades, para aprendizaje real.
- Aprobar dirección y textos cuando corresponda; esta sesión no solicita ni simula aprobación del usuario.
- Completar F0 de los otros ciclos y continuar la lectura F1. No dar por cerradas todas las fases por esta revisión.

## 5. Próximo incremento del plan

Definir el contrato del Observatorio y aprendizaje: cómo recibe observaciones normalizadas, evalúa su suficiencia y decide si debe informar a Editorial, a Estrategia o simplemente esperar datos. Es la dependencia inmediata que este recorrido dejó visible. Después cerrar el contrato editorial/revisión antes de implementar coordinación F3. No continuar generando copy como sustituto del trabajo de arquitectura.
