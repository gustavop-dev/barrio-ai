# Estado de los flujos (`FLU`)

Este documento es el mapa para auditar la máquina **flujo por flujo**. Cada flujo es algo que la máquina hace por ti de principio a fin, como publicar el post del día o hacer crecer tu red. Cada uno se parte en etapas ordenadas, y de cada etapa se cuenta lo mismo:

- qué entró
- qué avanzó
- qué se descartó a propósito
- qué falló, con su motivo
- qué está esperando ahora y desde cuándo

Todos los días llega a Slack un informe con ese estado. Está pensado para leerse en el celular en menos de un minuto. El mensaje y este documento salen del mismo registro de flujos, y una prueba comprueba que ninguno de los dos se quede atrás.

Hoy hay **13 flujos**: Post diario, Plan semanal y resúmenes, Tus ideas, Correcciones tuyas a un post, Comentarios en referentes, Respuestas en tus posts, Crecimiento de red, Comprador, Mensajes privados, Referentes, Investigación en internet, Perfil y posicionamiento y Salud de la máquina.

- **Código:**
  - `agentes-linkedin/infra/src/team_backend/flujos.py` tiene el registro `FLUJOS`, las medidas `medir_*`, las reglas (`juzgar`) y el texto (`texto`).
  - `alertas_slack.estado_de_flujos` hace el envío programado.
  - `manage.py operador estado-flujos` es el comando para pedirlo a mano.
- **Pruebas:** `agentes-linkedin/infra/src/team_backend/tests/test_estado_flujos.py`. Cubre:
  - los cinco incidentes de noviembre
  - un día sano
  - un flujo apagado
  - que el informe es solo de lectura
  - el horario
  - el comando
  - el formato para el celular

## Resumen

| ID | Función | Dónde | Estado |
| --- | --- | --- | --- |
| [FLU-01](#flu-01) | Informe por flujo y etapa, hoy y ayer | backend · Slack | funciona |
| [FLU-02](#flu-02) | Reglas del color de cada flujo | backend | funciona |
| [FLU-03](#flu-03) | Envío a Slack por la tarde y por la mañana | backend · Slack | funciona |
| [FLU-04](#flu-04) | Comando `operador estado-flujos` | backend | funciona |
| [FLU-05](#flu-05) | Un informe por miembro | backend · Slack | funciona |
| [FLU-06](#flu-06) | Solo lectura | backend | funciona |

---

## Cómo se lee el informe

### FLU-01 · Informe por flujo y etapa <a id="flu-01"></a>

**El informe de la tarde** (18:00) tiene tres partes:

1. **Arriba:**
   - la fecha
   - un veredicto de una línea, por ejemplo «🟢 Todo funciona: 13 flujos al día.» o «🔴 1 detenido · 🟡 2 con atención · 🟢 10 funcionando»
   - una línea por flujo con su color
2. **Los flujos en 🔴 y 🟡, abiertos.** Primero los rojos. Cada uno trae:
   - lo que pasó, con el motivo en palabras simples
   - sus etapas, una línea cada una: cuántos avanzaron hoy, de cuántos, cuántos fallaron y por qué, y qué espera
   - una línea «👉 Qué hacer:»
3. **Los flujos en 🟢, cerrados.** Una sola línea con su cifra clave, por ejemplo «publicado hoy a las 08:30».

**El informe de la mañana** (08:45) es más corto. Tiene la misma cabecera y estas tres partes:

- **«Desde medianoche»:** lo que se movió en la noche.
- **«Pendiente para hoy»:** lo que espera por ti.
- **«Lo que pide atención»:** la primera razón de cada flujo en 🔴 o 🟡 y qué hacer.

En ningún caso el informe trae identificadores internos, enlaces, tablas anchas ni el texto de mensajes privados. A las personas se las nombra igual que en los avisos que ya existen.

Si un día el mensaje pasa del tamaño que acepta Slack, se parte en varios. Cada parte siguiente lleva la cabecera y la marca «(sigue 2/3)».

**Criterios de aceptación:**

1. **Dado** un día en que todo funciona, **cuando** sale el informe de la tarde, **entonces** los 13 flujos aparecen en 🟢, con su cifra clave, y todo cabe en un solo mensaje.
2. **Dado** un informe más largo que el tope de un mensaje, **cuando** se envía, **entonces** sale en varias partes, cada una por debajo del tope y con «(sigue n/m)».
3. **Dado** que medir un flujo da error, **cuando** se arma el informe, **entonces** ese flujo sale en 🟡 con «No se pudo medir este flujo» y los demás salen normales.

### FLU-02 · Reglas del color de cada flujo <a id="flu-02"></a>

Cada etapa se mide en tres ventanas:

- hoy (desde la medianoche local)
- ayer
- las últimas 24 horas

Las reglas miran **las últimas 24 horas**, así un problema de anoche no desaparece al dar la medianoche.

| Color | Cuándo |
| --- | --- |
| ⚪ apagado | Su interruptor está apagado, y el informe dice cuál. Una etapa sola también puede estar apagada; se marca con ⚪ y su interruptor. |
| 🔴 detenido | No pasó algo que debía pasar hoy (cada flujo dice qué espera; ver su sección). O una etapa falló todos sus intentos de las últimas 24 horas, con al menos `ESTADO_FLUJOS_FALLOS_MIN` (3) fallos. O algo lleva esperando a la máquina más de `ESTADO_FLUJOS_DETENIDO_HORAS` (24). |
| 🟡 con atención | Una etapa falló al menos 3 veces en 24 horas y más del `ESTADO_FLUJOS_FALLOS_PCT` (20 %) de sus intentos. O algo espera a la máquina más que el límite de su etapa. O salió algo con un respaldo, como una imagen de respaldo en vez de la propia. O hay un hallazgo propio del flujo (ver su sección). |
| 🟢 funcionando | Nada de lo anterior. |

**Lo que no pone un flujo en amarillo:**

- **Lo que espera por ti:** tu aprobación, un mensaje que envías tú, un día que tienes que confirmar. Se muestra en «Pendiente para hoy», pero la máquina está bien.
- **Las paradas normales del ritmo de LinkedIn:**
  - fuera del horario de lectura
  - el tope de escrituras del día lleno
  - el espaciado entre escrituras
  - la tanda de red que terminó
- **Un cupo diario de lecturas agotado.** Es un límite, no un fallo. Sale como una línea de «Salud de la máquina». Lo que deja de pasar por ese cupo se ve en el flujo afectado. Por ejemplo, «Seguir e invitar se quedaron sin lecturas de perfil» aparece en Crecimiento de red.

**Los motivos.** Cada motivo de fallo se traduce a una frase simple con su «qué hacer». Por ejemplo, `cost_cap` se muestra como «se acabó el presupuesto de su ciclo». Un motivo que no está en la lista sale con su primera frase, sin identificadores, enlaces, correos ni números.

**Criterios de aceptación:** cada incidente de noviembre pone su flujo en el color correcto, con su motivo, y deja todos los demás en 🟢:

1. El post de hoy sin preparar porque el autopiloto no encargó su preparación pone **Post diario** en 🔴.
2. Seguir e invitar sin lecturas de perfil, porque la investigación gastó el cupo, pone **Crecimiento de red** en 🟡 con las cifras de cada parte del cupo.
3. Las investigaciones que quedan «en curso» para siempre, y las verificaciones que fallan por presupuesto, ponen **Investigación en internet** en 🟡 y **Crecimiento de red** en 🔴.
4. Compradores descartados con un nivel que los mantiene ponen **Crecimiento de red** en 🟡 y nombran el comando para recuperarlos.
5. Piezas con una imagen de respaldo (la tarjeta genérica, la tarjeta con la frase del post o una foto de la galería) ponen **Post diario** en 🟡, con cuál fue, el motivo y la cuenta de la semana.
6. La caja de comentarios que LinkedIn cambió el 19/11/2026 pone **Comentarios en referentes** y **Respuestas en tus posts** en 🔴: «LinkedIn cambió la página: no se puede comentar en un post (create_comment) desde las 16:00 (en la prueba de LinkedIn): no salen comentarios en posts de otros.». Su «qué hacer»: lo aprobado espera sin perderse; prueba ahora con `manage.py operador --usuario <tu usuario> prueba-linkedin`.

**LinkedIn cambió la página.** Un cambio de LinkedIn en una página o una respuesta que usa un flujo lo pone en 🔴 mientras dure ese día, aunque nada haya fallado tres veces. Lo encuentra la prueba de LinkedIn o una acción en uso (`cambios_linkedin.py`; detalle en [operador-linkedin.md](../../agentes-linkedin/infra/docs/operador-linkedin.md)). El hallazgo dice qué no se puede hacer, la operación, desde qué hora, quién lo vio («en uso» o «en la prueba de LinkedIn») y qué se detiene. Cada operación va a su flujo:

- comentar, a Comentarios en referentes;
- leer los comentarios de un post, a ese flujo y a Respuestas en tus posts;
- responder, leer hilos y reaccionar a un comentario, a Respuestas en tus posts;
- perfiles, búsqueda, seguir, invitar y aceptar, a Crecimiento de red;
- chats, a Mensajes privados;
- posts propios y analítica, a Post diario;
- lo demás, como reaccionar a un post o leer `/me`, a Salud de la máquina.

Se quita solo cuando la prueba vuelve a pasar o una operación igual sale bien.

### FLU-03 · Envío a Slack <a id="flu-03"></a>

- **Cuándo sale:**
  - el informe completo a las `SLACK_ESTADO_FLUJOS_HORA` (18:00)
  - la versión de la mañana a las `SLACK_ESTADO_FLUJOS_MANANA` (08:45)
  - Las dos horas son locales (`OPERATOR_TIMEZONE`).
  - Si la hora de la mañana está vacía, o es más tarde que la de la tarde, no hay versión de la mañana.
- **Adónde va:** al canal de resúmenes, `SLACK_WEBHOOK_RESUMEN` (o el de alertas si ese está vacío).
- **Cuántas veces:** cada informe sale **una sola vez** por día y horario, aunque el vigilante corra muchas veces.
- **Interruptor:** `SLACK_ESTADO_FLUJOS`, encendido por defecto. Con `false` no sale ninguno de los dos.
- **El resumen diario de antes:** mientras este informe está encendido, el resumen de `SLACK_DAILY_SUMMARY` no se envía. Este informe cuenta lo mismo, ordenado por flujo. Los cupos usados y sus topes siguen en la app y en `operador estado-flujos`. Si apagas `SLACK_ESTADO_FLUJOS`, el resumen de antes vuelve solo. Así no llegan dos resúmenes al mismo canal.

### FLU-04 · Comando `operador estado-flujos` <a id="flu-04"></a>

`python manage.py operador estado-flujos` **imprime** el informe de la tarde y no envía nada. Opciones:

- `--manana`: imprime la versión de la mañana.
- `--miembro USUARIO`: solo el de ese miembro.
- `--enviar`: además lo manda al canal de resúmenes. Como mucho una vez por minuto, y queda en la auditoría.

Si Slack no está configurado, el comando lo dice y no falla.

### FLU-05 · Un informe por miembro <a id="flu-05"></a>

Cuando hay más de un miembro activo, cada uno recibe su propio informe con sus cuentas, sus piezas y su red. La cabecera lleva su nombre («Barrio · Ana · *Estado de los flujos* …»).

Lo que es de toda la instalación solo va en el informe del primer miembro:

- el flujo Investigación en internet
- el presupuesto de IA
- la cola de trabajos
- las escrituras sin confirmar

### FLU-06 · Solo lectura <a id="flu-06"></a>

El informe solo **lee**:

- la base de datos: trabajos, propuestas, escrituras, piezas, capturas, personas, investigaciones y eventos de auditoría
- el registro de gasto de IA

Nunca lee LinkedIn, nunca llama a un proveedor de IA ni de búsqueda, y no escribe nada. La única excepción es la fila de auditoría de su propio envío. Una prueba lo comprueba: cualquier llamada a LinkedIn, a un proveedor o a la investigación web la hace fallar, y también cualquier escritura en la base.

---

## Los ciclos del equipo y sus flujos

El [registro del equipo](arquitectura-agentes.md) (`agentes-linkedin/equipos/grafo.yaml`) tiene 17 ciclos. Varios de ellos son, para ti, partes de un mismo flujo:

| Ciclo del equipo | Flujo del informe |
| --- | --- |
| `pieza_diaria` · Pieza diaria | Post diario |
| `metricas` · Métricas | Post diario (etapa Métricas) |
| `retoque_pieza` · Retoque por comentario | Correcciones tuyas a un post |
| `plan_semanal` · Plan de la semana | Plan semanal y resúmenes |
| `resumen_semanal` · Resumen semanal | Plan semanal y resúmenes |
| `consulta_evidencia` · Consulta de evidencia compartida | Plan semanal y resúmenes (la usa el resumen semanal) |
| `revision_mensual` · Revisión mensual | Plan semanal y resúmenes |
| `capturas` · Capturas | Tus ideas |
| `red` · Red y comentarios | Comentarios en referentes, Respuestas en tus posts, Crecimiento de red y Comprador |
| `inbox` · Inbox | Mensajes privados (y la secuencia del Comprador, que depende de leer la bandeja) |
| `referentes_mensuales` · Referentes mensuales | Referentes |
| `experimentos_referentes` · Experimentos de referentes | Referentes (etapa Experimentos) |
| `perfil_periodico` · Estrategia y perfil | Perfil y posicionamiento |
| `perfil_assets` · Solo fotos y banner de Perfil | Perfil y posicionamiento (etapa Propuesta de perfil) |
| `comunidad_mensual` · Estudio mensual de comunidad | Perfil y posicionamiento (etapa Estudio de la comunidad) |
| `manual_posicionamiento` · Consulta manual · posicionamiento | No es un flujo: corre solo cuando lo pides, no tiene ritmo que vigilar |
| `manual_perfil` · Consulta manual · perfil | No es un flujo: corre solo cuando lo pides, no tiene ritmo que vigilar |

Dos flujos no tienen ciclo propio en ese registro:

- **Investigación en internet** es un servicio que comparten los posts, tus ideas, los compradores, los referentes y tu perfil.
- **Salud de la máquina** es lo que todos necesitan.

---

## Post diario

**Qué hace:** prepara, revisa, ilustra y publica tu post de cada día a su hora. Después lee cómo le fue.

**Etapas:**

1. **Plan del día:** el autopiloto encarga la preparación del hueco del día (trabajos `prepare_piece`). Si un encargo espera más de 3 horas, la etapa se pone en amarillo.
2. **Preparación:** cuenta las piezas creadas, las listas, las saltadas a propósito por el director y las fallidas o bloqueadas con su nota. El trabajo pasa por:
   - el director
   - la investigación
   - la redacción
   - los lectores
   - la verificación
   - la reparación
3. **Imagen propia:** las piezas listas con su propia imagen. Los respaldos cuentan aparte. Cuando la imagen propia no sale, el código pone primero una tarjeta con la frase del post, si no puede una foto de la galería y, como último recurso, la tarjeta genérica de marca.
4. **Programado:** la propuesta de publicación (CONT-09). La aprueba el líder o la apruebas tú, o se descarta o se veta.
5. **Publicado:** el post escrito en LinkedIn, y los intentos fallidos con su motivo.
6. **Métricas:**
   - los cortes de 24 horas, 72 horas y 7 días leídos de cada post publicado
   - los cortes que ya tocaban y siguen sin leer

**Interruptores y límites:**

- `OPERATOR_AUTONOMY` de `CONT-09`: en `off` el flujo está apagado. En `approval` cada post espera tu aprobación.
- `LIVE_LINKEDIN_OFFICIAL` y la cuenta oficial: sin una cuenta que pueda publicar, el flujo está apagado.
- `OPERATOR_PAUSED` o el interruptor de la Oficina: la máquina detenida apaga el flujo.
- `EDITORIAL_POST_TIME` es la hora del post, y `EDITORIAL_LEAD_HOURS` cuántas horas antes empieza su preparación.
- `OPERATOR_WEEKLY_LIMITS` de `CONT-09`: con la semana llena no se espera otro post.
- `ALERT_POST_LATE_MINUTES` (60) es cuánto puede atrasarse el post.

**Está sano cuando:**

- el post de hoy salió a su hora
- el de mañana está preparado o en preparación
- las piezas llevan su propia imagen
- no hay cortes de métricas atrasados

**Se pone en 🔴 cuando:**

- **El post de hoy no salió a su hora:** pasó su hora más `ALERT_POST_LATE_MINUTES` y no está publicado. El informe dice en qué etapa quedó.
- **El post de hoy o el de mañana no está preparado:** pasaron 2 horas desde que debía empezar su preparación y no hay pieza ni encargo en curso. El informe dice por qué:
  - el autopiloto no lo encargó
  - el encargo falló, con su motivo
  - el presupuesto de IA se acabó
- **La hora del post está mal configurada.**
- Si el director **saltó el día a propósito**, o la semana ya publicó todo lo permitido, no se espera nada.

**Se pone en 🟡 cuando:**

- **Una pieza lista lleva un respaldo** en vez de su propia imagen en las últimas 24 horas, o **2 o más** de las piezas de la semana llevan uno. El informe dice cuál respaldo fue, el motivo y la cuenta de la semana, por ejemplo «4 de 14».
- Una etapa falla a menudo, o algo espera más de lo normal (las reglas de [FLU-02](#flu-02)).

**Cifra clave:** «publicado hoy a las 08:30; el de mañana, listo».

## Plan semanal y resúmenes

**Qué hace:**

- el domingo planea la semana siguiente
- el lunes resume la semana pasada
- el primer lunes del mes revisa el mes

**Etapas:**

1. **Plan de la semana:** los encargos `plan_week` y los planes guardados.
2. **Resumen semanal:** los encargos `weekly_summary` y los resúmenes guardados. Este paso usa la consulta de evidencia compartida.
3. **Revisión mensual:** los encargos `monthly_review` y las revisiones guardadas.

**Interruptores y límites:**

- **El plan:** `STRATEGY_ENABLED` lo enciende y `STRATEGY_PLAN_TIME` fija su hora del domingo.
- **El resumen:** `WEEKLY_SUMMARY_ENABLED` lo enciende y `WEEKLY_SUMMARY_TIME` fija su hora del lunes.
- **La revisión:** `MONTHLY_REVIEW_ENABLED` la enciende.

Con los tres apagados, el flujo está ⚪. Con alguno apagado, solo su etapa sale con ⚪ y su interruptor.

**Está sano cuando:**

- la semana que viene tiene plan desde el domingo
- el lunes está el resumen de la semana pasada
- el primer lunes del mes está la revisión del mes pasado

**Se pone en 🟡 cuando:**

- **La semana que viene aún no tiene plan** 2 horas después de su hora del domingo. Mientras tanto, el director planea cada día sin él. Solo se mira si el Post diario está encendido.
- **No se generó el resumen de la semana pasada** 2 horas después de su hora del lunes. Solo se pide si la máquina funcionó esa semana, porque sin datos el autopiloto no lo paga.
- **No se generó la revisión del mes pasado** durante la semana en que tocaba. Solo se pide si la máquina funcionó ese mes.

**Cifra clave:** «plan de esta semana listo; resumen de la semana pasada listo».

## Tus ideas

**Qué hace:** lo que mandas con el botón de captura (audio, nota o fotos) se transcribe, se entiende y llega a la mesa editorial. Ahí el director lo usa en un post.

**Etapas:**

1. **Recibidas:** las capturas nuevas, cuántas se procesaron, cuántas terminaron con error (con su motivo) y cuántas siguen procesándose.
2. **En la mesa editorial:** las ideas para un post que esperan un brief.
3. **Con fecha:** las ideas con un día pedido, y las que esperan que confirmes el día.
4. **Preparadas en un post:** las ideas que el director usó en una pieza creada ese día.
5. **Publicadas:** las ideas cuya pieza salió en LinkedIn ese día.
6. **Descartadas:** las ideas que no se usaron, porque estaban vacías o porque pasaron 14 días sin encajar.

**Interruptores y límites:** ninguno. El flujo siempre está encendido.

**Está sano cuando:** cada captura termina de procesarse en menos de una hora, y sin errores repetidos.

**Se pone en 🟡 o 🔴 cuando:**

- **Una captura lleva más de una hora procesándose.** Pasa a rojo si lleva más de 24 horas.
- **Las capturas fallan a menudo** (las reglas de [FLU-02](#flu-02)).
- Las ideas que esperan que confirmes el día **no** lo ponen en amarillo. Salen en «Pendiente para hoy».

**Cifra clave:** «hoy 2 capturas recibidas; 3 ideas esperan en la mesa editorial».

## Correcciones tuyas a un post

**Qué hace:** cuando dejas un comentario sobre una pieza ya lista, el director decide qué hacer. Puede rehacer el texto, la imagen o ambos, antes de que salga.

**Etapas:**

1. **Correcciones aplicadas:** tus comentarios sobre una pieza. Cada uno termina de una de estas formas:
   - **Rehecha.**
   - **Sin cambios:** el director decidió que no hacía falta cambiar nada.
   - **No aplicada, con su motivo:** sin revisiones del líder, sin presupuesto, o la pieza no puede salir así.
   - **Como nota para el equipo:** cuando la pieza ya no puede cambiar.

**Interruptores y límites:** `EDITORIAL_REWORK_MIN_USD` es el presupuesto mínimo que debe quedar para rehacer una pieza.

**Está sano cuando:** cada corrección se aplica, o se decide no cambiar nada, en menos de una hora.

**Se pone en 🟡 o 🔴 cuando:**

- **Una corrección lleva más de una hora aplicándose.** Pasa a rojo si lleva más de 24 horas.
- **Varias correcciones no se pudieron aplicar** (las reglas de [FLU-02](#flu-02)).

**Cifra clave:** «hoy 1 corrección aplicada» o «hoy no mandaste correcciones».

## Comentarios en referentes

**Qué hace:** lee los posts de tus referentes (y de los compradores que se están calentando) y propone un comentario. El líder lo revisa y, si lo aprueba, se publica en LinkedIn.

**Etapas:**

1. **Posts observados:** los posts nuevos leídos y las lecturas fallidas.
2. **Comentario propuesto:** los borradores encargados y las propuestas de comentario (INT-03) creadas.
3. **Revisado por el líder:** las propuestas aprobadas o descartadas por las reglas y el líder.
4. **Publicado:** los comentarios escritos en LinkedIn y los intentos fallidos con su motivo.
5. **Confirmado en LinkedIn:** los comentarios que LinkedIn mostró. Los que LinkedIn no confirmó cuentan como fallos.

**Interruptores y límites:**

- `OPERATOR_AUTONOMY` de `INT-03`: en `off` el flujo está apagado. En `approval` cada comentario espera tu aprobación.
- Sin referentes activos el flujo está apagado. También lo apaga la máquina detenida.
- `OPERATOR_DAILY_PROPOSALS` y `OPERATOR_DAILY_LIMITS` de `INT-03` son los topes de propuestas y comentarios por día.
- `LEAD_ENABLED` enciende al líder que revisa.
- `ALERT_NO_COMMENTS_HOURS` (24) son las horas de ventana sin ningún comentario publicado antes de avisar.

**Está sano cuando:** sale al menos un comentario dentro de su ventana y el líder no descarta casi todo.

**Se pone en 🔴 cuando:** **ningún comentario se publicó** en `ALERT_NO_COMMENTS_HOURS` horas de ventana. Si en ese tiempo hay comentarios esperando **tu** aprobación, queda en 🟡 y te pide aprobarlos.

**Se pone en 🟡 cuando:**

- **El líder descartó casi todo:** el 80 % o más de al menos 5 revisiones en 24 horas. Se ajusta con `ALERT_LEAD_DISCARD_RATIO` y `ALERT_LEAD_DISCARD_MIN`.
- Las lecturas, los borradores o las escrituras fallan a menudo (las reglas de [FLU-02](#flu-02)).
- Algo espera más de `ESTADO_FLUJOS_ESPERA_HORAS` (6) en la cola de la máquina.

**Cifra clave:** «hoy 3 comentarios publicados de 4 propuestos».

## Respuestas en tus posts

**Qué hace:** lee los comentarios de tus posts y propone una respuesta a los que la merecen. El líder la revisa y, si la aprueba, se publica.

**Etapas:**

1. **Comentarios leídos:** los comentarios nuevos y las lecturas fallidas.
2. **Respuesta propuesta:** las propuestas de respuesta (INT-04) aprobadas o descartadas, y los comentarios que siguen esperando una respuesta de la máquina.
3. **Publicada:** las respuestas escritas en LinkedIn y los intentos fallidos con su motivo.

**Interruptores y límites:**

- `REPLIES_ENABLED` y `OPERATOR_AUTONOMY` de `INT-04`: si cualquiera está apagado, el flujo está apagado.
- `REPLIES_READ_CAPS` son los cupos de lectura de comentarios.
- `READ_WINDOW` es el horario de lectura.
- `ALERT_REPLY_PENDING_HOURS` (4) son las horas de ventana que un comentario puede esperar respuesta.

**Está sano cuando:** los comentarios se leen durante el día y ninguno que merece respuesta espera más de 4 horas de ventana.

**Se pone en 🔴 cuando:** **no se están leyendo los comentarios de tus posts**, con alguno esperando su lectura. El informe da el motivo, por ejemplo una lectura que falla, el cupo agotado o la cuenta en pausa.

**Se pone en 🟡 cuando:**

- **Un comentario espera respuesta** más de `ALERT_REPLY_PENDING_HOURS` horas. Pasa a rojo si lleva más de 24 horas.
- **El líder descartó casi todo** (la misma regla que en Comentarios en referentes).
- Las lecturas o las escrituras fallan a menudo.

No cuentan los comentarios que esperan **tu** respuesta a una pregunta del equipo o a un «¿Salió o no?».

**Cifra clave:** «hoy 2 respuestas publicadas; 0 comentarios esperan respuesta».

## Crecimiento de red

**Qué hace:**

- encuentra personas
- las clasifica por rol y por nivel de comprador
- verifica en la web a los compradores
- las sigue y las invita
- acepta las invitaciones que te llegan

**Etapas:**

1. **Perfiles encontrados:** las personas descubiertas y las búsquedas fallidas.
2. **Clasificados:** las personas clasificadas, las descartadas y las que esperan clasificación.
3. **Verificados en la web:** las verificaciones de la etapa de compra de cada comprador, y los compradores que faltan por verificar.
4. **Seguidos (RED-01):** las propuestas, los seguimientos escritos y los intentos fallidos con su motivo.
5. **Invitados (RED-02):** las propuestas, las invitaciones enviadas y los intentos fallidos con su motivo.
6. **Aceptaron tu invitación:** las personas que pasaron a ser conexión, y las invitaciones sin respuesta.
7. **Invitaciones recibidas aceptadas (RED-04):** las invitaciones de otros que aceptaste.

**Interruptores y límites:**

- `NETWORK_ENABLED` enciende el flujo.
- `NETWORK_STAGE_CHECK` enciende la etapa Verificados en la web.
- `OPERATOR_AUTONOMY` de `RED-01`, `RED-02` y `RED-04`: en `off`, esa etapa sale con ⚪.
- **Las lecturas de perfil:** `OPERATOR_PROFILE_READ_DAILY_LIMIT` (80 por día) es el cupo diario. `OPERATOR_PROFILE_READ_RESEARCH_SHARE` es la parte de ese cupo que puede usar la investigación; el resto queda para seguir e invitar. Las dos partes se juntan a partir de `OPERATOR_PROFILE_READ_POOL_CUTOFF` (17:00).
- La rampa de invitaciones (BAR-15) puede pausar las invitaciones.

**Está sano cuando:**

- hay personas nuevas, clasificadas en menos de un día
- sigue e invita dentro de sus topes
- ningún comprador sale del barrio por una regla equivocada

**Se pone en 🔴 cuando:**

- Una acción (seguir, invitar o verificar) **falló todos sus intentos** de las últimas 24 horas, con al menos 3 fallos. El informe dice el motivo, por ejemplo «sin lecturas de perfil» o «se acabó el presupuesto de su ciclo».
- Algo espera en la cola de la máquina más de 24 horas.

**Se pone en 🟡 cuando:**

- **Seguir e invitar se quedaron sin lecturas de perfil.** El informe dice a qué hora pasó y cuánto usó cada parte, por ejemplo «acciones 4/4, investigación 5/2».
- **Compradores salieron del barrio** en 24 horas con un nivel que debería mantenerlos. Es una regla de clasificación, no su nivel. Se recuperan sin pagar otra clasificación con `operador reevaluar-compradores`; sin `--confirmar`, el comando no cambia nada.
- **La investigación web no devuelve hallazgos** y se pausaron las verificaciones de compradores.
- **Las invitaciones están en pausa** por baja aceptación o por un límite de LinkedIn.
- Una etapa falla a menudo, o algo espera más de lo normal.

Las propuestas que esperan **tu** aprobación salen en «Pendiente para hoy» y no ponen el flujo en amarillo.

**Cifra clave:** «hoy 12 seguidos, 8 invitados y 3 aceptaron tu invitación».

## Comprador

**Qué hace:** acompaña el recorrido de un comprador:

1. lo calienta con comentarios
2. lo invita
3. prepara el primer mensaje
4. prepara los seguimientos
5. prepara la respuesta a lo que te contestó
6. llega a la reunión

Los mensajes los envías **tú**: la máquina solo deja listos los borradores.

**Etapas:**

1. **Calentamiento:** los compradores elegidos, los invitados tras calentarse y los que siguen calentándose.
2. **Primer mensaje:** los borradores del mensaje 1 preparados, descartados o fallidos, y los listos para que los envíes.
3. **Secuencia (mensajes 2 a 4):** los borradores de seguimiento, y los listos para que los envíes.
4. **Respuesta a quien respondió:** los borradores de respuesta, y los listos para que los envíes.
5. **Reunión:** los compradores que respondieron, las reuniones agendadas y las reservas que no se pudieron emparejar con un comprador.

**Interruptores y límites:**

- **Cada etapa tiene su interruptor:**
  - `BUYER_WARMUP_ENABLED`
  - `BUYER_FIRST_MESSAGE_ENABLED`
  - `BUYER_SEQUENCE_ENABLED`
  - `BUYER_REPLY_ENABLED`
- Con los cuatro apagados, el flujo está ⚪. Con alguno apagado, solo su etapa sale con ⚪.
- **Lo que necesitan los borradores:**
  - el primer mensaje y la secuencia necesitan al líder (`LEAD_ENABLED`)
  - la secuencia necesita leer la bandeja (`INBOX_ENABLED`)
  - la respuesta necesita tu enlace de agenda (`CALCOM_BOOKING_URL`)

**Está sano cuando:** los borradores se preparan sin fallos y la secuencia sabe, por la bandeja, quién respondió.

**Se pone en 🟡 cuando:**

- **La secuencia está detenida** porque no se leyó la bandeja y no se sabe si respondieron.
- **Hay respuestas de compradores sin borrador** porque falta tu enlace de agenda.
- Los borradores fallan a menudo.

Los mensajes listos para que los envíes salen en «Pendiente para hoy» y no ponen el flujo en amarillo.

**Cifra clave:** «4 compradores calentándose; 2 mensajes listos para que los envíes».

## Mensajes privados

**Qué hace:** lee tu bandeja de LinkedIn y te avisa de las conversaciones que te tocan a ti. El equipo **no** responde mensajes privados.

**Etapas:**

1. **Bandeja leída:** las lecturas de la bandeja completas o fallidas.
2. **Te tocan a ti:** las conversaciones que esperan tu respuesta.

**Interruptores y límites:**

- `INBOX_ENABLED` enciende el flujo; la máquina detenida también lo apaga.
- `INBOX_EVERY_MINUTES` es cada cuánto se lee la bandeja.
- `INBOX_READ_CAPS` son los cupos de lectura de la bandeja.

**Está sano cuando:** la bandeja se lee varias veces al día dentro del horario de lectura.

**Se pone en 🟡 cuando:**

- **No se lee la bandeja** desde hace más de tres veces `INBOX_EVERY_MINUTES`, dentro del horario de lectura.
- Las lecturas fallan a menudo.

Las conversaciones que te esperan salen en «Pendiente para hoy» y no ponen el flujo en amarillo.

**Cifra clave:** «bandeja leída 6 veces hoy; 1 conversación te espera».

## Referentes

**Qué hace:**

- revisa cada mes a quién observas
- busca referentes grandes de tu industria
- analiza sus posts
- corre experimentos con lo que aprende

**Etapas:**

1. **Revisión mensual:** las revisiones preparadas y publicadas, y los cambios que esperan tu respuesta.
2. **Búsqueda de referentes de industria:** las búsquedas que pediste (con `operador referentes-industria`) y las publicadas.
3. **Análisis de posts:** los posts de los referentes de industria leídos para el análisis.
4. **Experimentos:** los avances de los experimentos, y los experimentos en curso.

**Interruptores y límites:**

- `REFERENTES_ANALISIS` enciende la etapa Análisis de posts.
- `REFERENTES_INDUSTRIA_TOPE_USD` es el tope de gasto de la búsqueda de industria.
- La revisión mensual tiene su ventana del día 1 al día 5 (OBS-01/02).

**Está sano cuando:** la revisión del mes se prepara y se publica sin quedarse a medias, y los experimentos avanzan sin fallos.

**Se pone en 🟡 cuando:**

- **Una revisión de referentes lleva más de un día preparándose.**
- Una búsqueda o un avance de experimentos falla a menudo.

Los cambios que esperan tu respuesta salen en «Pendiente para hoy».

**Cifra clave:** «5 referentes activos; 0 cambios esperan tu respuesta».

## Investigación en internet

**Qué hace:** busca y lee fuentes públicas, con citas, para:

- los posts
- tus ideas
- los compradores
- los referentes
- tu perfil

Es de toda la instalación, por eso solo sale en el informe del primer miembro.

**Etapas:** en cada una cuenta las investigaciones pedidas, las hechas, las omitidas, las que no trajeron hallazgos y las que quedaron a medias.

1. **Para los posts:** investigaciones con clave `piece:`.
2. **Para tus ideas:** clave `capture:`.
3. **Para verificar compradores:** clave `etapa:`.
4. **Para referentes:** clave `referents:`.
5. **Para tu perfil:** clave `profile:`.

**Interruptores y límites:**

- Tienen que estar encendidos `WEB_RESEARCH_ENABLED` y `LIVE_PROVIDERS`. Si falta cualquiera de los dos, el flujo está apagado.
- `WEB_RESEARCH_DAILY_LIMIT` (6) es el tope de investigaciones por día.
- `NETWORK_STAGE_CHECKS_PER_DAY` (6) es el tope de verificaciones de compradores por día.

**Está sano cuando:** cada investigación termina, con o sin hallazgos, en menos de 30 minutos, y las últimas traen hallazgos con citas.

**Se pone en 🟡 cuando:**

- **Una investigación quedó a medias:** sigue «en curso» después de 30 minutos. Su gasto no se repite y su resultado no llegó.
- **Las últimas investigaciones no trajeron ningún hallazgo con citas.**
- Muchas investigaciones terminan sin hallazgos.

**Se pone en 🔴 cuando:** una investigación lleva más de 24 horas «en curso», o todas las de un tipo fallaron en 24 horas (al menos 3).

**Cifra clave:** «hoy 4 investigaciones hechas de 5 pedidas» o «hoy no se pidió ninguna».

## Perfil y posicionamiento

**Qué hace:**

- cada seis meses te propone cambios a tu perfil de LinkedIn
- cada mes te propone los destacados y la actividad
- te propone fotos y banner para tu perfil
- cada mes estudia tu comunidad

**Etapas:**

1. **Propuesta de perfil:** las propuestas de perfil y las de fotos y banner. Cuenta las listas, las detenidas y las fallidas, y las que esperan tu revisión.
2. **Estudio de la comunidad:** los estudios mensuales empezados, terminados o con errores.

**Interruptores y límites:**

- `PROFILE_ENABLED` enciende la propuesta de perfil. Apagado, esa etapa sale con ⚪.
- El estudio de la comunidad tiene un tope de 50 personas y 90 días.

**Está sano cuando:** las propuestas terminan sin detenerse y el estudio del mes se construye en menos de un día.

**Se pone en 🔴 cuando:** **un estudio de la comunidad lleva más de 24 horas construyéndose**, o las propuestas o los estudios fallaron todos sus intentos de 24 horas (al menos 3).

**Se pone en 🟡 cuando:** las propuestas o los estudios fallan a menudo (las reglas de [FLU-02](#flu-02)).

**Cifra clave:** «al día» o «1 propuesta espera tu revisión».

## Salud de la máquina

**Qué hace:** vigila lo que todo lo demás necesita:

- el autopiloto
- el presupuesto de IA
- los cupos de lectura y de escritura
- la cola de trabajos
- las cuentas
- el navegador
- la prueba diaria de LinkedIn

**Etapas:**

1. **Cola de trabajos:** los trabajos encolados, los terminados y la cola actual. Solo sale en el informe del primer miembro. Los fallos de cada trabajo los juzga su propio flujo, no esta etapa.

**Interruptores y límites:**

- `OPERATOR_AUTOPILOT` enciende el autopiloto.
- `OPERATOR_PAUSED` (o el interruptor de la Oficina) detiene la máquina.
- `AI_MONTHLY_LIMIT_USD` (100) es el tope de gasto de IA del mes, y `AI_DAILY_FUSE_USD` (15) el del día.
- `ALERT_CAP_THRESHOLD` (0,8) es la fracción del mes a la que avisa.
- `ALERT_QUEUE_STUCK_MINUTES` (20) es cuánto puede estar quieta la cola de un worker.

Este flujo nunca está ⚪: si algo de lo que vigila está apagado, sale en rojo.

**Está sano cuando:**

- el autopiloto está encendido y la máquina corriendo
- queda presupuesto de IA
- ninguna cuenta está en pausa
- los workers procesan su cola
- no hay escrituras sin confirmar

**Se pone en 🔴 cuando:**

- **El autopiloto está apagado:** nada se encola solo.
- **La máquina está detenida.**
- **Se acabó el presupuesto de IA del mes o el de hoy:** nada pagado avanza.
- **Una cuenta de LinkedIn está en pausa:** no lee ni escribe.
- **El worker de un carril no procesa su cola.**

**Se pone en 🟡 cuando:**

- **El gasto de IA del mes pasó el 80 %** de su tope.
- **El navegador de LinkedIn no responde** y aplazó escrituras en la última hora.
- **Hay escrituras sin confirmar en LinkedIn.** También salen en «Pendiente para hoy» como «¿Salió o no?».

**Cifra clave:** «IA: 1,20 USD hoy, 38,40 de 100,00 en el mes» y la línea de la prueba de LinkedIn de las últimas 24 horas. Por ejemplo, «Prueba de LinkedIn: ok a las 07:05 (21 comprobaciones, 17 llamadas, ninguna escritura enviada; 3 escrituras solo se saben al escribir)». Si no, «rota a las … (create_comment)», «no pudo correr a las … (motivo)» o «sin correr en 24 h». El «todo bien» diario de la prueba solo vive aquí: no hay un mensaje de Slack aparte. Lo que encontró roto pone en 🔴 su flujo (ver «LinkedIn cambió la página»). Debajo del flujo, cuando está abierto, salen los cupos de lectura agotados hoy y las escrituras del día con su tope, por ejemplo «posts 1/1, comentarios 8/15».

---

## Variables de entorno

Todas son opcionales. Sus valores por defecto son los de esta tabla.

| Variable | Por defecto | Qué hace |
| --- | --- | --- |
| `SLACK_ESTADO_FLUJOS` | `true` | Enciende el informe. Mientras está encendido, el resumen diario de `SLACK_DAILY_SUMMARY` no se envía. |
| `SLACK_ESTADO_FLUJOS_HORA` | `18:00` | Hora local del informe completo. |
| `SLACK_ESTADO_FLUJOS_MANANA` | `08:45` | Hora local de la versión de la mañana. Vacía, o más tarde que la de la tarde, la apaga. |
| `ESTADO_FLUJOS_FALLOS_MIN` | `3` | Fallos mínimos en 24 horas para que una etapa cambie de color. |
| `ESTADO_FLUJOS_FALLOS_PCT` | `0.2` | Fracción de intentos fallidos que pone una etapa en amarillo. |
| `ESTADO_FLUJOS_ESPERA_HORAS` | `6` | Horas que algo puede esperar en la cola de lecturas y comentarios antes del amarillo. |
| `ESTADO_FLUJOS_DETENIDO_HORAS` | `24` | Horas de espera en una cola de la máquina que la ponen en rojo. |

El informe usa los mismos webhooks que los avisos: `SLACK_WEBHOOK_RESUMEN` y, si está vacío, `SLACK_WEBHOOK_URL`. Las variables están en `agentes-linkedin/infra/.env.example`. En el servidor hay que añadirlas también a `deploy/.env.example` y al `.env` de producción. Con sus valores por defecto no hace falta tocar nada.
