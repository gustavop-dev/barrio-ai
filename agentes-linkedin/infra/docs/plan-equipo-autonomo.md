# Plan maestro del equipo autónomo de LinkedIn

Fecha: 2026-11-06. Versión: 1.0. Estado: planificación; autonomía aún no implementada.

Este documento guía el diseño y la implementación. Antes de trabajar en un grupo, consultar su fase, dependencias y criterio de salida. Registrar aquí cambios de rumbo; los documentos de cada agente desarrollan este plan, no lo sustituyen.

## 1. Objetivo y alcance

Construir para Gustavo un posicionamiento reconocible, autoridad profesional y una audiencia grande y pertinente en LinkedIn. El barrio incluye compradores, pares, recomendadores, líderes y divulgadores. Seguidores y publicaciones son indicadores parciales; interesa también quién llega, qué conversaciones se generan y qué utilidad percibe la audiencia.

Trabajamos con las clases 01–06, conservando originales y evidencias. Las metas numéricas, oferta, nicho, línea base, voz y cadencia requieren contexto personal; permanecen sin fijar hasta trabajarlo con Gustavo. No interpretar ejemplos del curso como resultados garantizados ni tareas de alumnos como obligaciones del sistema.

Outbound, campañas de calentamiento y contacto de leads quedan pendientes de las clases 07 y posteriores. Diseñar un punto de integración inactivo, sin inventar sus procedimientos. La escucha y comunidad orgánica sí pertenecen a esta primera mitad.

## 2. Fundamento y decisiones de arquitectura

Anthropic distingue recorridos definidos por código de agentes que deciden dinámicamente cómo actuar. También recomienda empezar con la solución más sencilla y añadir complejidad cuando aporte valor. Aplicaremos un modelo híbrido: estados y controles programados, con decisiones abiertas dentro de cada especialidad. [Building Effective Agents](https://www.anthropic.com/research/building-effective-agents).

Su experiencia con investigación multiagente destaca delegación delimitada, herramientas claras, evaluación y recuperación de fallos. La trasladamos como principios de ingeniería; sus resultados en investigación no demuestran que trece roles mejoren nuestro contenido. [How we built our multi-agent research system](https://www.anthropic.com/research/multi-agent-research-system).

Estas fuentes sustentan patrones, no una obligación de usar un SDK o servicio particular. El propio primer artículo advierte que su panorama de herramientas ha cambiado. Este plan conserva Django, PostgreSQL/pgvector y los adaptadores existentes; cualquier nueva dependencia deberá justificar una carencia concreta y comprobarse contra documentación vigente.

Decisiones propias del proyecto:

- Propósito común y ciclos que se activan por eventos, sin exigir una orden manual para cada paso.
- El planificador propone acciones; el backend valida permisos, dependencias, límites y transiciones antes de ejecutarlas.
- Trece roles son una hipótesis organizativa, no trece procesos permanentes. Activar solo los necesarios para cada ciclo.
- Conocimiento compartido con recuperación contextual. Afinidades y etiquetas no restringen la propiedad de una unidad a un agente.
- Dos borradores y lectores independientes cuando la comparación aporte valor; decisión editorial razonada, sin exigir unanimidad.
- Dos rondas de revisión como límite inicial propuesto, configurable después de evaluar; nunca atribuirlo al curso.
- Los lectores simulados generan hipótesis y objeciones, no métricas de mercado.
- Revisión humana final antes de publicación. Este plan no activa publicación, comentarios, cambios de perfil ni mensajes externos.

## 3. Punto de partida y brechas

La base existente incluye backend Django, cola persistente, proveedores con caché y reservas, biblioteca de 1.035 unidades de clases 01–06, memoria y oficina visual conectada. Existen diseños previos de posicionamiento y perfil. Hay que verificar estos componentes al comenzar cada fase técnica; no asumir que un resultado histórico acredita su salud actual.

Falta implementar coordinación autónoma entre roles, objetivos operativos, dependencias versionadas, ciclos y evaluación del conjunto. Una misión en un prompt o un personaje animado no acredita un agente operativo. La lectura integral del corpus tampoco está completada.

La prueba anterior de generación con Claude terminó con timeout y reserva incierta: no cuenta como generación exitosa y no se repetirá automáticamente. Antes de un piloto pagado, comprobar permisos, disponibilidad y presupuesto vigente. El presupuesto histórico del procesamiento del curso es distinto del de esta infraestructura.

## 4. Ciclos operativos que debemos diseñar

| Ciclo | Activación | Decisión y entrega | Condición de cierre |
| --- | --- | --- | --- |
| Posicionamiento | Contexto personal confirmado o cambio material | Posicionamiento propone; perfil deriva una propuesta coherente | Referencia aprobada o preguntas concretas pendientes |
| Investigación y barrio | Pregunta editorial, evidencia nueva o revisión acordada | Observatorio entrega hallazgos fechados, fuentes, incertidumbre y oportunidades | Pregunta suficientemente respondida o límites de investigación alcanzados |
| Producción editorial | Oportunidad priorizada y entradas vigentes | Director prepara brief; escritura propone; lectores contrastan; revisión verifica | Pieza lista para aprobación o descarte justificado |
| Aprendizaje | Publicación confirmada y ventana de datos disponible | Observatorio interpreta; dirección propone ajustes; estrategia interviene si cambia el enfoque | Aprendizaje registrado y siguiente experimento definido, o evidencia insuficiente |

El disparador no ejecuta trabajo ilimitado. Se comprobarán novedad, relevancia, presupuesto y dependencias. Una revisión periódica sin evidencia nueva puede terminar sin llamar al modelo.

## 5. Plan por fases y criterios para avanzar

### F0 — Acordar el contrato operativo del equipo

Entregables: especificar los cuatro ciclos anteriores, decisiones, entradas mínimas, artefactos de salida, métricas y autoridad. Adaptar la plantilla de agente a esos ciclos. Clasificar cada función como código determinista, decisión de modelo o decisión humana.

Salida: cada ciclo tiene responsable, disparador, resultado verificable, condición de parada y manejo de información faltante. No exige todavía elegir nicho ni activar agentes.

### F1 — Fundamentar los grupos en el conocimiento

El orquestador leerá las unidades completas y registrará identificador, hash, interpretación, límites y relaciones. Distinguir lectura de títulos, lectura completa y evaluación de aplicabilidad. Leer todo el corpus antes de declarar fundamentado el equipo completo; para diseñar un grupo se exige completar sus unidades pertinentes y revisar conexiones transversales.

Orden: estrategia/perfil → observatorio/barrio → dirección editorial/escritura → lectores → revisión y aprendizaje. Clases 01–02 aportan las bases del primer grupo; clases posteriores pueden complementarlo. No asignar exclusividad por clase.

Entregables por grupo: contrato, fuentes, reglas con excepciones, salidas, conflictos que escala y casos de evaluación. Mantener pendientes explícitos sobre Gustavo. No reescribir las unidades originales.

Salida: cada regla atribuida al curso tiene respaldo revisado; las decisiones de arquitectura se etiquetan como propias. Logística y ejercicios sin utilidad operativa quedan fuera de las instrucciones.

### F2 — Incorporar contexto personal y construir la evaluación inicial

Trabajar con Gustavo oferta, pruebas reales, experiencias, preferencias, límites, voz, audiencia y métricas disponibles. Separar confirmado, provisional y desconocido. Definir objetivos medibles y una cadencia sostenible sin prometer crecimiento.

Crear casos de evaluación a partir de situaciones representativas: brief completo/incompleto, prueba ausente, fuentes contradictorias, lector no comprador, contenido atractivo pero ajeno al posicionamiento, pieza técnicamente correcta sin voz propia y métricas insuficientes.

Salida: contexto suficiente para un primer ciclo y rúbrica versionada. Comparar calidad con un recorrido sencillo de un solo agente antes de añadir colaboración. Definir umbrales de aceptación antes de medir, no después de ver los resultados.

### F3 — Implementar la coordinación persistente en Django

Reutilizar cola, identidad, permisos, caché, memoria y ledger. Añadir con migraciones los conceptos que falten: objetivo, versión de contrato, ciclo, paso/dependencia, evento, artefacto versionado, decisión/aprobación y observación de resultado. Los nombres definitivos se ajustan al código existente para evitar tablas duplicadas.

Separar servicios de planificación, validación y ejecución. Cada paso referencia un trabajo existente y conserva entradas, versión del prompt/modelo, fuentes, salida y coste. Una aprobación corresponde a una versión específica; editar la pieza obliga a revisar su aprobación.

Estado de ciclo propuesto: planificado, ejecutándose, esperando información, esperando aprobación, bloqueado, completado o cancelado. Los trabajos mantienen sus estados técnicos existentes; no confundir trabajo completado con objetivo alcanzado o publicación realizada.

Eventos deduplicados, adquisición transaccional de trabajo y transiciones válidas impiden carreras. Una interrupción recupera el trabajo local seguro; una llamada pagada de resultado incierto conserva su reserva y no se repite automáticamente. Límites de pasos, rondas, duración y gasto se comprueban antes de cada ejecución.

Salida: pruebas sin proveedores reales demuestran reanudación, aislamiento por propietario, deduplicación, rechazo de transiciones inválidas y detención correcta por límites. Una entrada modificada marca sus dependientes para revisión sin borrar históricos.

### F4 — Completar un recorrido mínimo de punta a punta

Usar estrategia y perfil como primer grupo de implementación. Confirmar contexto → recuperar unidades → generar propuesta de posicionamiento → preparar perfil → revisión/aprobación → guardar versiones y trazabilidad. Añadir luego una única pieza editorial con el mínimo de roles necesario para comprobar el ciclo.

Primero ejecutar con respuestas simuladas y datos de prueba; después una prueba real acotada solo dentro de autorización y saldo vigentes. No modificar límites para hacer pasar el piloto. Si la ejecución real falla, conservar diagnóstico y no declararla validada.

Salida: un cambio de contexto inicia el trabajo pertinente, entrega un resultado verificable, solicita solo la información faltante y termina sin duplicar gasto. Comparación inicial de calidad, latencia y coste contra el recorrido sencillo.

### F5 — Incorporar grupos y colaboración evaluada

Añadir observatorio con fuentes accesibles, fecha, muestra y límites. Si LinkedIn no proporciona acceso a un dato, aceptar material aportado por el usuario o declarar el vacío; no suponer capacidades de una integración inexistente.

Incorporar dirección editorial, dos escritores y revisión. Probar lectores por perspectiva con evaluaciones inicialmente independientes para reducir conformidad. El director resuelve desacuerdos según el propósito de la pieza; el verificador conserva objeciones materiales. Comparar el recorrido simple, dos escritores y el debate de lectores sobre los mismos casos.

Salida: conservar cada participación adicional solo si aporta una mejora verificable respecto de su coste. Una preferencia estética no bloquea una pieza; una experiencia inventada o afirmación material sin respaldo sí requiere resolución.

### F6 — Conectar resultados reales y autonomía gradual

Registrar publicación únicamente con confirmación real. Incorporar métricas disponibles mediante fuente habilitada o importación, con fecha y ventana. Distinguir impresiones, personas, acciones y composición de audiencia; no inferir ventas de likes ni causalidad de una sola observación.

El ciclo propone cambios basados en evidencia. Sin suficiente evidencia, pide datos o mantiene la hipótesis abierta. Cambios centrales de posicionamiento se presentan para confirmación; no se sobrescribe la identidad profesional por fluctuaciones de un post.

Activación gradual: ejecución manual verificable → propuesta automática por evento → ejecución interna acotada → cadencia acordada. En cada nivel, presupuestos, permisos y parada siguen vigentes. No activar un scheduler nuevo durante esta planificación.

Salida: el equipo puede justificar qué hará después, con qué evidencia y qué espera aprender; puede pausar trabajo improductivo y recuperar un ciclo interrumpido de manera segura.

### F7 — Reflejar el funcionamiento en la oficina y operar

Mostrar por grupo el estado real, objetivo, siguiente acción, bloqueo, artefactos y decisiones. Mantener la tarea manual como intervención opcional. Diferenciar simulación visual, trabajo real y resultados pendientes de aprobación.

Documentar operación: detener/reactivar ciclos, revisar reservas inciertas, corregir entradas, invalidar versiones, inspeccionar trazas y recuperar tras fallo. Ejecutar una prueba representativa de punta a punta y registrar sus límites.

Salida: lo que muestra la oficina coincide con el backend; un reinicio no pierde trabajo ni duplica acciones. El usuario puede comprender y controlar el sistema sin leer logs.

## 6. Memoria y recuperación

Cuatro capas: curso inmutable; contexto personal confirmado; artefactos/decisiones del equipo; observaciones externas y métricas. Las simulaciones se etiquetan y nunca ingresan como evidencia real.

Sobre el corpus, añadir metadatos derivados y versionados: tema, habilidad, aplicabilidad, relación, excepción y afinidad con roles. Usar embeddings del proveedor y recuperación existente antes de construir infraestructura nueva. Evaluar si recupera las unidades necesarias, incluidas excepciones y conexiones entre clases. Registrar qué contexto recibió cada ejecución.

No cargar las 1.035 unidades en cada llamada. La lectura transversal durante el diseño sirve para construir criterios y relaciones; la ejecución recupera contexto pertinente y puede ampliar su búsqueda de manera acotada.

## 7. Verificación transversal

- Ingeniería: trabajos concurrentes, deduplicación, reinicio, cancelación, permisos, reservas inciertas y memoria versionada.
- Conocimiento: fuentes correctas con prefijo de clase, originales intactos, excepciones conservadas y distinción entre curso e investigación actual.
- Comportamiento: hechos faltantes, instrucciones hostiles dentro de fuentes, resultados contradictorios y presión para publicar sin aprobar.
- Calidad editorial: relevancia, voz, prueba, claridad, promesa cumplida y utilidad para el destinatario de la pieza.
- Operación: coste por resultado aceptado, tiempo, correcciones humanas y contribución de cada rol. El acuerdo entre modelos no equivale a verificación factual.

Ejecutar pruebas focalizadas al modificar código y las comprobaciones exigidas por AGENTS.md antes de cerrar cada fase técnica. Registrar evidencia; no marcar una fase completa solo por haber escrito sus documentos.

## 8. Seguimiento y regla para no perder el rumbo

| Fase | Estado actual | Evidencia necesaria para cerrarla |
| --- | --- | --- |
| F0 | Diseño de los cinco grupos y 13 roles disponible; recorrido global realizado; QA independiente y aceptación se registran abajo | Contratos conectados, datos externos y hallazgos resueltos; ejecución corresponde a F3/F4 |
| F1 | En curso parcial | Lecturas completas y diseños fundamentados |
| F2 | Iniciada con contexto y propuesta provisional; línea base y contraste pendientes | Dirección aceptada, evidencia y criterios anteriores |
| F3–F7 | Pendientes | Entregables y criterios anteriores |

Antes de cada sesión: identificar fase y criterio pendiente, consultar fuentes del grupo, elegir un incremento que pueda verificarse. Al terminar: registrar lo cambiado, evidencia, decisiones nuevas, pendientes y siguiente acción. Si aparece una mejora fuera del incremento, anotarla sin desplazar silenciosamente el objetivo.

Siguiente incremento vigente: revisar las dependencias de datos del diseño integral, completar lectura pertinente de F1 y línea base de F2; preparar F3 sin desarrollar los trece agentes simultáneamente. Los incrementos anteriores se conservan abajo como historial.

Documentos relacionados: [arquitectura implementada](methodology/architecture.md), [integración de oficina](office-integration.md), [estructura inicial del equipo](../../arquitectura/ESTRUCTURA.txt), [plantilla de agente](../../arquitectura/plantilla-agente.json), [mapa de roles](../../arquitectura/equipo-autonomo.json) y [registro de lectura](../../arquitectura/registro-lectura.json).

## 9. Registro de decisiones

- 2026-11-06: plan inicial basado en investigación y estado documentado del proyecto. Arquitectura híbrida, expansión gradual y evaluación comparativa. No cambia código de ejecución, presupuesto, permisos ni programación. Los umbrales cuantitativos y cronograma quedan pendientes de datos y mediciones; no se inventan fechas de entrega.

### Contexto personal recibido — 2026-11-06

[Brief inicial de Gustavo y contraste de casos](brief-gustavo-posicionamiento.md).
F2 iniciada parcialmente por instrucción del usuario: objetivos y experiencia recibidos,
primera revisión documental y tres decisiones pendientes. No supone completar F0/F1
ni aprobar el posicionamiento. Prioridades: oportunidades en startups y servicios
ProjectApp; contenido inglés, foco inicial hispanohablante/latinoamericano en USA.

- Actualización de prioridades: 60% oportunidades en startups / 40% contratos
  ProjectApp. Identidad técnica con comprensión de negocio. Aclaración vigente: ejecución directa de Gustavo en contratos personales;
  ejecución del equipo bajo su liderazgo en contratos ProjectApp. Próximo paso:
  precisar etapa de startup, problema prioritario y perfil de founder.

- Segmento inicial confirmado: startups tempranas, preferentemente presemilla
  con inversión recibida y presupuesto de contratación. Ingeniería de producto
  e incorporación pertinente de IA; founders técnicos o de negocio. Otras etapas
  no quedan excluidas. Pendientes modalidad, remuneración y disponibilidad.

- Condiciones iniciales recibidas: tiempo completo o parcial; referencia interna
  USD 5.000–7.999 mensuales antes de impuestos para tiempo completo; sumar
  colaboraciones compatibles sin reemplazo por defecto. Capacidad horaria concreta
  pendiente. Siguiente entregable de posicionamiento: perfil de oportunidad,
  propuesta de valor y criterios de audiencia, diferenciando oferta personal/equipo.

- Primera síntesis curso/contexto preparada: [posicionamiento v1](propuesta-posicionamiento-gustavo-v1.md). Buyer personas hipotéticos, dos ofertas, mensaje y brief para Perfil. Pendiente revisión de Gustavo y contraste de mercado; F0/F1/F2 no se dan por cerradas.

### Incremento F0: primer contrato operativo y datos

- [Ciclo de Estrategia y Perfil](ciclo-estrategia-perfil.md): disparadores, estados, autoridad, entregables, revisión y parada.
- [Datos y resultados](datos-y-resultados-del-equipo.md): captura inicial, observaciones, oportunidades, procedencia y distribución por rol.
- [15 casos de evaluación](../../arquitectura/evaluacion-ciclo-estrategia-perfil.json), diseñados y todavía no ejecutados.
- Siguiente acción vigente: recorrido de mesa del primer ciclo con el contexto confirmado de Gustavo, luego completar contratos restantes y preparar F3. La propuesta de titulares anterior es material de prueba, no cierre del ciclo.
- No se activó captura automática, scheduler, llamadas pagadas ni cambios de LinkedIn. F0 global y F1 siguen parciales.

### Recorrido de mesa completado — primer ciclo

[Informe](recorrido-mesa-estrategia-perfil.md): caso real de Gustavo y 15 escenarios revisados por el asistente. Cuatro vacíos corregidos en contratos v1.1. No son tests de backend ni ejecución de agentes; resultados runtime siguen pendientes.

Siguiente acción vigente: definir contrato de Observatorio/aprendizaje y sus decisiones de suficiencia y distribución de evidencia; luego completar contratos restantes de F0 y preparar F3. La primera propuesta de perfil permanece provisional.

### Diseño integral solicitado: todos los equipos y datos externos

Referencia vigente para continuar: [circuitos conectados](circuitos-equipo.md). Incluye cinco grupos, arranque sin métricas, producción, aprendizaje y cambios de contexto. [Catálogo de datos externos](datos-externos-por-equipo.md) y [índice de 13 contratos](../../arquitectura/indice-agentes-v1.json).

[Recorrido global de mesa](recorrido-mesa-equipo-completo.md), [QA coordinación](qa-circuitos-coordinacion.md) y [QA conocimiento/datos](qa-circuitos-conocimiento-datos.md) distinguen diseño de pruebas de ejecución. Este incremento sustituye las notas históricas de “diseñar a continuación Observatorio/otros ciclos”.

Estado: diseño integral de F0 documentado y revisado por dos subagentes QA Astra high, con seis hallazgos P2 corregidos y ninguno P1/P2 abierto identificado; aceptación humana del diseño pendiente; F1 sigue selectivo, no se declara lectura integral de 1.035 unidades. F2 conserva pendiente línea base, validación de comprador y permiso de uso público de casos. No se implementó F3 ni se activaron llamadas, cuentas o publicación. Próximo trabajo: revisar dependencias externas del catálogo, completar conocimiento pertinente y preparar especificación de implementación sobre estos contratos cuando corresponda; no generar copy como sustituto del circuito.

Cierre documental: coordinación verificó cinco correcciones (selección de lectores, rondas globales, ACK frente a aprobación, deduplicación y recepción de comentarios); conocimiento/datos verificó una (aplicación desconocida frente a false). Validación local de estructura, referencias y enlaces: [registro](../../arquitectura/validacion-diseno-equipo-v1.json). No equivale a pruebas de comportamiento de agentes.
