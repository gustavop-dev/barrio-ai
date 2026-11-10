# Runtime de ciclos · fase 3b

Pieza diaria y red usan el registro para autorizar herramientas. El director conserva el contenido y Relaciones es dueño de cada subtrigger de red. El dispatcher no publica: las propuestas conservan las reglas, el verificador, Jev cuando aplica, veto/hash y Operación como único escritor LinkedIn. BAR-15 y las cadencias no cambian.

## Persistencia y recuperación

La migración **0021_cycle_ledger**, dependiente de 0020, crea `CycleLedger`. Una restricción única `(cycle, key)` conserva la identidad. Task ledger: hechos, plan/versiones, hash de código/configuración y decisiones humanas. Progress ledger: solicitudes/resultados privados, estados, duración, contadores, siguiente paso y snapshots. Un lease exclusivo y su token impiden dos trabajadores o respuestas obsoletas.

La migración **0022_cycleledger_job_set_null** permite borrar jobs como antes de 3b. Su ledger permanece con `job=NULL`: no se eliminan checkpoints, contadores ni gasto. La migración 0021 se conserva para instalaciones que ya la aplicaron.

El worker reencola el mismo job tras perder el latido únicamente si no hay llamadas en vuelo. Las etapas respondidas se reutilizan sin proveedor. Un error conocido se conserva y se vuelve a entregar al workflow; una llamada en vuelo no se vuelve a pagar. Una posible escritura LinkedIn continúa por la conciliación existente de Operación. El presupuesto y los contadores no se borran. Cambiar registro, contratos/código u overrides de modelo/política detiene la instancia hasta una migración explícita.

La recuperación automática requiere el job persistido de los triggers normales. No adopta los intentos heredados previos a 0021 que carecen de ledger. Los ciclos sin migrar mantienen su política previa de interrupción.

## Contratos, límites y coste

Las aristas ejecutables llevan `runtime` y propósitos de proveedor permitidos. El dispatcher valida petición y respuesta por el nombre de schema del registro. Las llamadas agrupadas de copywriters y lectores consumen una llamada y autorizan/auditan a todos sus participantes. Un especialista no puede llamar a otro agente, ni usar un proveedor fuera de los propósitos de su arista.

Se mantienen prompts y resultado de la única reparación histórica del director. El bucle declara copywriters, verificador y reparación, con dos evaluaciones como máximo. Cambiar el autor/prompt de la reparación es una capacidad posterior con evaluación propia, como exige ARQ-03. El fan-out mensual permanece planificado.

Un presupuesto ya agotado antes de preparar conserva el fallo del job sin crear una pieza. Si se agota durante la reparación, se conserva `verification.repair.outcome=sin_presupuesto`, el texto/hash original y los motivos editoriales. Ese resultado bloqueado queda en el checkpoint sin convertir el ciclo detenido en completo ni autorizar más herramientas. Una solicitud de imagen pendiente o incierta sigue exigiendo conciliación antes de comprobar si cabe otra reserva.

`knowledge/cycle_context.py` evita acoplar los usos independientes de `knowledge.providers` a Django. Cuando hay ciclo, cada reserva se etiqueta con instancia/job/nodo/arista/bucket y comparte el lock del usage ledger existente. Gasto confirmado sustituye a reserva; reservado e incierto permanecen contabilizados. La liquidación al cap detiene y avisa aunque no haya otro paso. Jev posterior comparte el presupuesto de la propuesta original. La política y el último control de Operación impiden ejecutar propuestas de una instancia detenida.

Pieza: **8 USD por ciclo**, tope por reservas contra gastos desbocados que cabe en una pieza con imágenes (hasta el 10/11/2026 eran 2 USD por instancia y día; ya no hay tope diario propio). Red: techo técnico de **1 USD por subtrigger**. Todo ciclo queda además dentro del presupuesto general de IA (`knowledge/presupuesto.py`: `AI_MONTHLY_LIMIT_USD` y el tope de seguridad diario `AI_DAILY_FUSE_USD`) y de los techos opcionales por proveedor, que pueden detener antes. Referentes: **5 USD por mes natural**, compartido entre instancias cuando se active. Perfil: **10 USD por ciclo**, declarado para su futura activación. No se amplían estos valores desde un reintento o una respuesta humana.

El tiempo activo se conserva entre sesiones; no incluye la espera con el worker liberado. Timeout de llamada 120 s y edición de foto hasta 300 s, subordinados al ciclo y a los timeouts más cortos de los adaptadores actuales. Los transportes reciben el tiempo restante; un resultado tardío no se aplica. Los límites detienen nuevas solicitudes; no se presume que un proveedor haya cancelado una petición ya enviada.

## Oficina, mapa y Tu turno

La Oficina conserva las secuencias de etapas, comentarios y publicaciones en `office.event`. Las solicitudes/respuestas del dispatcher se añaden como `office.orchestration`, con instancia, arista y fase en auditoría. El endpoint de eventos devuelve ambas fuentes en orden `(created_at, id)`; únicamente las nuevas llevan `source: "orchestration"`. Así se distinguen la llamada a una herramienta y la entrega posterior del trabajo, sin sustituir ni duplicar las entregas históricas dentro de `office.event`. El Mapa agrega ambas fuentes de handoffs y los estados, fase, contadores y costes confirmados/reservados de los ledgers visibles para el usuario. No devuelve hechos privados, prompts, fuentes privadas ni respuestas completas.

Un límite de gasto, atasco o resultado incierto genera un aviso deduplicado. Un gestor puede reconocerlo desde Tu turno. `POST /api/v1/equipo/ciclos/{id}/decision` exige sesión humana y `manage_jobs`: `acknowledge` retira el aviso; `resume` con `plan` solo permite reanudar un atasco sin llamadas pendientes ni límites agotados. No autoriza repetir llamadas inciertas ni aumenta el gasto. La conciliación de proveedores inciertos sigue siendo una tarea operativa explícita.

## Archivos de esta entrega

Rutas relativas a `agentes-linkedin/infra/src/` salvo indicación:

- Runtime: `team_backend/orquestacion.py`, `orquestacion_schemas.py`, `orquestacion_views.py`; `knowledge/cycle_context.py` y `knowledge/providers.py`.
- Modelo/migraciones: `team_backend/models.py`, `team_backend/migrations/0021_cycle_ledger.py`, `0022_cycleledger_job_set_null.py`.
- Integración: `team_backend/editorial.py`, `imagenes.py`, `connectors_images.py`, `operador.py`, `red.py`, `research.py`, `lider.py`, `autopiloto.py`, `jobs.py`.
- API/avisos: `team_backend/grafo.py`, `grafo_views.py`, `oficina_eventos.py`, `notificaciones.py`, `rediseno_views.py`, `urls.py`.
- Pruebas: `team_backend/tests/test_orquestacion.py`, `test_publicacion.py` (contratos completos del fake compartido), `test_auditoria_editorial.py`, `test_eventos.py`, `test_evaluaciones.py`, `test_grafo.py`.
- Registro y cliente: `agentes-linkedin/equipos/grafo.yaml`, `compartido/src/api/grafo.ts`, `compartido/src/api/oficina.ts`.
- Documentación/generador: `scripts/grafo/mermaid.py`, `docs/arquitectura/grafo.md`, este documento, `docs/funcionalidades/arquitectura-agentes.md`, `docs/plan-equipos.md`.

## Verificación para Claude

No se ejecutaron tests, builds, uv, pip, npm, migraciones ni generadores. No hubo red, commit o push. El Markdown de Mermaid se sincronizó mediante edición, incluido su hash; CI debe regenerarlo y comparar.

1. Ejecutar 0021 y 0022 sobre PostgreSQL de QA y comprobar `makemigrations --check --dry-run` y `manage.py check`. Verificar también 0022 sobre una base que ya tenga 0021, y borrar un job conservando ledger y gasto.
2. Ejecutar `test_orquestacion` y la suite backend con fakes, especialmente editorial/publicación, auditorías, imágenes, investigación web, red/BAR-15, Jev, worker, grafo y eventos. Ejecutar también la suite independiente de knowledge: fuera de un ciclo no debe necesitar Django.
3. Confirmar paridad de decisión/texto/hash/citas/manifest con los fixtures de referencia, máximo dos evaluaciones y una reparación. La actualización del fake elimina campos históricos incompatibles (`text_only`, `kind` en checked_claims) sin cambiar la decisión esperada.
4. Cortar un worker entre checkpoints y dentro de una llamada: el primero reutiliza respuestas; el segundo conserva incertidumbre y no llama de nuevo. Repetir con dos workers, y con caída después de crear la propuesta pero antes de cerrar el job. Comprobar no duplicar propuestas/imagen/gasto/publicaciones.
5. Comprobar reservas concurrentes, cap exacto, reservas inciertas, Jev posterior, día/mes Colombia, límite por arista/global y tiempos. Confirmar no ejecutar una propuesta detenida con Jev apagado, aprobación manual o una pausa durante preflight.
6. Comprobar Oficina → Mapa y Tu turno: eventos reales, costes/estado, lectura por dueño, ausencia de datos privados, aviso único, reconocimiento sin reanudación ni aumento del cap. Las secuencias históricas deben permanecer idénticas al excluir los eventos añadidos con `source: "orchestration"`; comprobar también el orden de ambas fuentes intercaladas.
7. Revisar la integración con el resultado final de CI/QA de 3a antes de fusionar; no se han importado cambios de su otro worktree. Referentes, Perfil y fan-out no deben activarse por esta migración.

Selección: **`[qa: 03 04 06 07 09 11 16 17-mapa-equipo]`**.

## Corrección del primer CI backend de 3b

El log `f3b-ci-1.log` termina con **9 FAIL y 7 ERROR** (553 tests). Se leyeron todos sus tracebacks. Cambios de esta corrección:

- `knowledge/cycle_context.py`, `knowledge/providers.py`, `team_backend/orquestacion.py`: usar `connection.execute(...).fetchone()` en las tres consultas de reserva, conservando el lock global; priorizar la conciliación de solicitudes inciertas; permitir guardar un resultado bloqueado sin levantar el stop.
- `team_backend/editorial.py`, `models.py`, `migrations/0022_cycleledger_job_set_null.py`: restaurar preflight, resultado de reparación, entregas de etapas y borrado de jobs con conservación del ledger.
- `team_backend/oficina_eventos.py`, `grafo_views.py`, `compartido/src/api/oficina.ts`: identificar y mostrar los nuevos handoffs sin reemplazar los eventos históricos.
- `team_backend/grafo.py`: validar profundidad y rutas de gates antes de la autoridad runtime; la excepción de Jev exige además una arista declarada en `runtime_edges`. Se conservan los tests negativos y el registro/Mermaid no cambia.
- `team_backend/tests/test_auditoria_editorial.py`, `test_orquestacion.py`, `test_eventos.py`, `test_evaluaciones.py`, `test_grafo.py`: reforzar checkpoints bloqueados, borrado de jobs, cap diario compartido y rechazo de gates runtime no declarados; ordenar handoffs explícitamente; verificar la secuencia histórica y las adiciones por separado; inyectar el campo prohibido en el caso negativo del evaluador. Los schemas de producción y sus errores esperados no cambian.
- Este documento describe el cambio aditivo del feed y la migración.

Claude debe repetir la suite backend completa con fakes y comprobar los 16 casos originales, además de los casos nuevos. Especial atención a presupuesto agotado antes/durante la reparación, reservas concurrentes/mensuales, imagen incierta y secuencias de Oficina. Esta corrección solo editó archivos y revisó el diff; no se ejecutaron tests, builds, migraciones ni generadores localmente.

## Corrección del CI de PR #79

El log `f3b-ci-79.log` termina con **1 FAIL y 0 ERROR** (557 tests). El único traceback corresponde a `GraphTests.test_specialists_depth_contracts_and_units`: al cambiar el origen de `redactar_a` al verificador, su pertenencia al bucle omitía el control de profundidad y el rechazo llegaba después como `runtime fuera del orquestador`.

`team_backend/grafo.py` limita la excepción de profundidad por bucle a las aristas sin runtime. Las llamadas ejecutables del bucle deben salir del orquestador, igual que exige el dispatcher. Se conserva el test existente, las dos evaluaciones máximas, la excepción explícita de Jev y la validación de rutas sin bypass. No cambia el registro ni sus diagramas, los workflows, los contratos o las unidades.

Revisión estática solamente, sin ejecutar pruebas, builds, gestores de paquetes ni usar la red, commit o push. Pendiente en CI: repetir `team_backend.tests.test_grafo` y la suite backend para confirmar el resultado.
