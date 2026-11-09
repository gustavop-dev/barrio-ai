# Runtime de ciclos · fase 3b

Pieza diaria y red usan el registro para autorizar herramientas. El director conserva el contenido y Relaciones es dueño de cada subtrigger de red. El dispatcher no publica: las propuestas conservan las reglas, el verificador, Jev cuando aplica, veto/hash y Operación como único escritor LinkedIn. BAR-15 y las cadencias no cambian.

## Persistencia y recuperación

La migración **0021_cycle_ledger**, dependiente de 0020, crea `CycleLedger`. Una restricción única `(cycle, key)` conserva la identidad. Task ledger: hechos, plan/versiones, hash de código/configuración y decisiones humanas. Progress ledger: solicitudes/resultados privados, estados, duración, contadores, siguiente paso y snapshots. Un lease exclusivo y su token impiden dos trabajadores o respuestas obsoletas.

El worker reencola el mismo job tras perder el latido únicamente si no hay llamadas en vuelo. Las etapas respondidas se reutilizan sin proveedor. Un error conocido se conserva y se vuelve a entregar al workflow; una llamada en vuelo no se vuelve a pagar. Una posible escritura LinkedIn continúa por la conciliación existente de Operación. El presupuesto y los contadores no se borran. Cambiar registro, contratos/código u overrides de modelo/política detiene la instancia hasta una migración explícita.

La recuperación automática requiere el job persistido de los triggers normales. No adopta los intentos heredados previos a 0021 que carecen de ledger. Los ciclos sin migrar mantienen su política previa de interrupción.

## Contratos, límites y coste

Las aristas ejecutables llevan `runtime` y propósitos de proveedor permitidos. El dispatcher valida petición y respuesta por el nombre de schema del registro. Las llamadas agrupadas de copywriters y lectores consumen una llamada y autorizan/auditan a todos sus participantes. Un especialista no puede llamar a otro agente, ni usar un proveedor fuera de los propósitos de su arista.

Se mantienen prompts y resultado de la única reparación histórica del director. El bucle declara copywriters, verificador y reparación, con dos evaluaciones como máximo. Cambiar el autor/prompt de la reparación es una capacidad posterior con evaluación propia, como exige ARQ-03. El fan-out mensual permanece planificado.

`knowledge/cycle_context.py` evita acoplar los usos independientes de `knowledge.providers` a Django. Cuando hay ciclo, cada reserva se etiqueta con instancia/job/nodo/arista/bucket y comparte el lock del usage ledger existente. Gasto confirmado sustituye a reserva; reservado e incierto permanecen contabilizados. La liquidación al cap detiene y avisa aunque no haya otro paso. Jev posterior comparte el presupuesto de la propuesta original. La política y el último control de Operación impiden ejecutar propuestas de una instancia detenida.

Pieza: **2 USD por instancia y día** America/Bogota. Red: techo técnico de **1 USD por subtrigger**, además de los caps diarios/por proveedor existentes que pueden detener antes. Referentes: **5 USD por mes natural**, compartido entre instancias cuando se active. Perfil: **10 USD por ciclo**, declarado para su futura activación. No se amplían estos valores desde un reintento o una respuesta humana.

El tiempo activo se conserva entre sesiones; no incluye la espera con el worker liberado. Timeout de llamada 120 s y edición de foto hasta 300 s, subordinados al ciclo y a los timeouts más cortos de los adaptadores actuales. Los transportes reciben el tiempo restante; un resultado tardío no se aplica. Los límites detienen nuevas solicitudes; no se presume que un proveedor haya cancelado una petición ya enviada.

## Oficina, mapa y Tu turno

La Oficina recibe la solicitud y respuesta de cada herramienta. El Mapa agrega estados, fase, contadores y costes confirmados/reservados de los ledgers visibles para el usuario. No devuelve hechos privados, prompts, fuentes privadas ni respuestas completas.

Un límite de gasto, atasco o resultado incierto genera un aviso deduplicado. Un gestor puede reconocerlo desde Tu turno. `POST /api/v1/equipo/ciclos/{id}/decision` exige sesión humana y `manage_jobs`: `acknowledge` retira el aviso; `resume` con `plan` solo permite reanudar un atasco sin llamadas pendientes ni límites agotados. No autoriza repetir llamadas inciertas ni aumenta el gasto. La conciliación de proveedores inciertos sigue siendo una tarea operativa explícita.

## Archivos de esta entrega

Rutas relativas a `agentes-linkedin/infra/src/` salvo indicación:

- Runtime: `team_backend/orquestacion.py`, `orquestacion_schemas.py`, `orquestacion_views.py`; `knowledge/cycle_context.py` y `knowledge/providers.py`.
- Modelo/migración: `team_backend/models.py`, `team_backend/migrations/0021_cycle_ledger.py`.
- Integración: `team_backend/editorial.py`, `imagenes.py`, `connectors_images.py`, `operador.py`, `red.py`, `research.py`, `lider.py`, `autopiloto.py`, `jobs.py`.
- API/avisos: `team_backend/grafo.py`, `grafo_views.py`, `notificaciones.py`, `rediseno_views.py`, `urls.py`.
- Pruebas: `team_backend/tests/test_orquestacion.py`, `test_publicacion.py` (contratos completos del fake compartido).
- Registro y cliente: `agentes-linkedin/equipos/grafo.yaml`, `compartido/src/api/grafo.ts`.
- Documentación/generador: `scripts/grafo/mermaid.py`, `docs/arquitectura/grafo.md`, este documento, `docs/funcionalidades/arquitectura-agentes.md`, `docs/plan-equipos.md`.

## Verificación para Claude

No se ejecutaron tests, builds, uv, pip, npm, migraciones ni generadores. No hubo red, commit o push. El Markdown de Mermaid se sincronizó mediante edición, incluido su hash; CI debe regenerarlo y comparar.

1. Ejecutar 0021 sobre PostgreSQL de QA y comprobar `makemigrations --check --dry-run` y `manage.py check`.
2. Ejecutar `test_orquestacion` y la suite backend con fakes, especialmente editorial/publicación, auditorías, imágenes, investigación web, red/BAR-15, Jev, worker, grafo y eventos. Ejecutar también la suite independiente de knowledge: fuera de un ciclo no debe necesitar Django.
3. Confirmar paridad de decisión/texto/hash/citas/manifest con los fixtures de referencia, máximo dos evaluaciones y una reparación. La actualización del fake elimina campos históricos incompatibles (`text_only`, `kind` en checked_claims) sin cambiar la decisión esperada.
4. Cortar un worker entre checkpoints y dentro de una llamada: el primero reutiliza respuestas; el segundo conserva incertidumbre y no llama de nuevo. Repetir con dos workers, y con caída después de crear la propuesta pero antes de cerrar el job. Comprobar no duplicar propuestas/imagen/gasto/publicaciones.
5. Comprobar reservas concurrentes, cap exacto, reservas inciertas, Jev posterior, día/mes Colombia, límite por arista/global y tiempos. Confirmar no ejecutar una propuesta detenida con Jev apagado, aprobación manual o una pausa durante preflight.
6. Comprobar Oficina → Mapa y Tu turno: eventos reales, costes/estado, lectura por dueño, ausencia de datos privados, aviso único, reconocimiento sin reanudación ni aumento del cap.
7. Revisar la integración con el resultado final de CI/QA de 3a antes de fusionar; no se han importado cambios de su otro worktree. Referentes, Perfil y fan-out no deben activarse por esta migración.

Selección: **`[qa: 03 04 06 07 09 11 16 17-mapa-equipo]`**.
