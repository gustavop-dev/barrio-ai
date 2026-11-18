# Organizaciones y miembros (`ORG`)

Una segunda persona de la empresa (el CTO) usa Barrio AI con su propio usuario y sus propias cuentas de LinkedIn. Estas
son las fases 1 y 2 del [plan de organizaciones](../plan-organizaciones.md): el modelo, «de quién es» cada cuenta, los
selectores por miembro, las pausas por miembro y la sesión del navegador solo para su dueño (fase 1); y un ritmo de
LinkedIn propio para cada miembro (fase 2: candado, espaciado, topes, lecturas de perfil, rampa, notas, tier, bloqueos
del proveedor y sus ajustes); y su identidad fuera del código (fase 3: perfiles de organización y de miembro en la
base, prompts por miembro, su voz y los textos que la nombran); y su contenido (fase 4: calendario y piezas, plan,
resumen, revisión, audiencia, memoria, orientación, preguntas, capturas y galería de cada miembro, con la hora de los posts
escalonada y los temas coordinados); y sus vistas y sus avisos (fase 5: cada ruta dice de quién son sus datos, el id de otro
miembro es un 404, el embudo de oportunidades es de la empresa y dice quién trajo cada una, cada aviso tiene dueño); y el
registro compartido de personas (fase 6: una ficha por persona en la organización, quien la toca primero se la queda, dos o
tres por empresa, un comentario por post de referente, el reparto de candidatos y los colegas). Con un solo miembro (la instalación de hoy) nada cambia. El alta real del CTO es la fase 7;
hasta entonces, un miembro nuevo entra **inactivo**.

- **Código:** backend `models.py` (`Organization`, `Member`, `ConnectorAccount.member`), migración `0055_organizaciones`,
  `miembros.py` (API interna), selectores en `editorial.py`, `respuestas.py`, `metricas.py`, `operador.py`,
  `alertas_slack.py`, `perfil.py`, `analitica.py`, `connectors_linkedin.py`; permisos en `conexion.py`,
  `referentes.py`, `experimentos.py`; comandos `operador miembro|miembros|ajustes`, `bootstrap_local`, `seed_qa --segundo-miembro`.
  Fase 2: `Member.settings` (migración `0056_ritmo_por_miembro`), `miembros.policy_key`/`setting`/`save_settings`, el ritmo
  por miembro en `operador.py` y `red.py`, `alertas_slack.por_miembro`.
- **Documentación:** [plan de organizaciones](../plan-organizaciones.md) (fases 1 y 2 y su API interna),
  «Organizaciones» y «Máquina autónoma» de [`CONTRATO-API.md`](../../oficina/CONTRATO-API.md).

## Resumen

| ID | Función | Dónde | Estado |
| --- | --- | --- | --- |
| [ORG-01](#org-01) | ProjectApp y su primer miembro | backend | funciona |
| [ORG-02](#org-02) | De quién es cada cuenta | backend | funciona |
| [ORG-03](#org-03) | Cada miembro publica en su propia cuenta | backend | funciona |
| [ORG-04](#org-04) | Cada miembro lee con su propia cuenta | backend | funciona |
| [ORG-05](#org-05) | Sesión del navegador y credencial oficial: solo su dueño | backend | funciona |
| [ORG-06](#org-06) | Pausas por miembro; parada total de la máquina | backend | funciona |
| [ORG-07](#org-07) | Quién decide referentes y experimentos | backend | funciona |
| [ORG-08](#org-08) | Alta de miembros por comando | backend | funciona |
| [ORG-09](#org-09) | Mundo de QA con un segundo miembro | backend · QA | funciona |
| [ORG-10](#org-10) | Un ritmo de LinkedIn por miembro | backend | funciona |
| [ORG-11](#org-11) | Rampa, notas y bloqueos del proveedor por miembro | backend | funciona |
| [ORG-12](#org-12) | El ritmo de cada miembro se ajusta aparte | backend (servidor) | funciona |
| [ORG-13](#org-13) | Avisos de Slack del ritmo de cada miembro | backend | funciona |
| [ORG-14](#org-14) | La identidad de la organización y de cada miembro, en la base | backend | funciona |
| [ORG-15](#org-15) | Cada texto del equipo se escribe como su miembro | backend | funciona |
| [ORG-16](#org-16) | La voz de cada miembro: provisional y aprendida | backend (servidor) | funciona (apagada) |
| [ORG-17](#org-17) | Los textos que ven las personas nombran al dueño | backend, PWA, app | funciona |
| [ORG-18](#org-18) | Cada miembro tiene su calendario, su plan, su resumen y su revisión | backend | funciona |
| [ORG-19](#org-19) | Su memoria y sus hechos; los de la empresa los comparte el administrador | backend (servidor) | funciona |
| [ORG-20](#org-20) | Sus capturas, su galería, sus preguntas y su orientación | backend | funciona |
| [ORG-21](#org-21) | Posts escalonados y temas coordinados entre miembros | backend | funciona |
| [ORG-22](#org-22) | Un post en voz provisional nunca sale solo | backend, PWA, app | funciona |
| [ORG-23](#org-23) | Cada ruta dice de quién son sus datos; lo de otro miembro no existe | backend | funciona |
| [ORG-24](#org-24) | Un solo embudo de oportunidades que dice quién trajo cada una | backend, PWA, app | funciona |
| [ORG-25](#org-25) | Cada aviso tiene dueño: push, preferencias y «Vista» por persona | backend | funciona |
| [ORG-26](#org-26) | «Quién soy» y la marca de voz provisional en las apps | backend, PWA, app | funciona |
| [ORG-27](#org-27) | Cada miembro entra con su usuario y solo lee lo suyo | backend (servidor), PWA, app | funciona |
| [ORG-28](#org-28) | Una ficha por persona en la organización | backend | funciona (actúa desde dos miembros) |
| [ORG-29](#org-29) | Quien toca primero a una persona se la queda | backend, PWA, app | funciona (actúa desde dos miembros) |
| [ORG-30](#org-30) | Dos o tres personas por empresa, nunca dos del mismo cargo | backend | funciona (actúa desde dos miembros) |
| [ORG-31](#org-31) | Liberar, pasar y reasignar una persona | backend, PWA, app | funciona (actúa desde dos miembros) |
| [ORG-32](#org-32) | Referentes de la organización: una lectura y un comentario por post | backend | funciona (actúa desde dos miembros) |
| [ORG-33](#org-33) | El reparto de candidatos y los colegas | backend | funciona (actúa desde dos miembros) |

---

### ORG-01 · ProjectApp y su primer miembro <a id="org-01"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** al desplegar, la instalación pasa a tener la organización ProjectApp y a Gustavo como su
  primer miembro (administrador, rol «Fundador»), dueño de las dos cuentas que ya existen (API oficial y navegador). Él no
  nota nada.
- **Código:** migración `0055_organizaciones` (`first_member`), `miembros.first_owner`, `miembros.ensure_first_member`
  (también en `bootstrap_local`, que corre en cada arranque).
- **Criterios de aceptación:**
  1. **Dado** una base con el usuario de `REFERENTS_GUSTAVO_USERNAME` (por defecto `gustavo`) activo, **cuando** migra,
     **entonces** se crea ProjectApp (`projectapp`) con ese usuario como miembro activo y administrador, con nombre su
     nombre y apellido (o «Gustavo»), y todas las cuentas sin miembro pasan a ser suyas.
  2. **Dado** que ese usuario no existe, **cuando** migra, **entonces** el miembro es el primer superusuario activo por fecha
     de alta con contraseña usable que no sea `barrio-autopiloto` ni `linkedin-service`.
  3. **Dado** una base sin nadie así (la del CI, la de QA antes de `seed_qa`), **cuando** migra, **entonces** no se crea
     nada y todo funciona como antes de las organizaciones; `bootstrap_local` crea el miembro después con la misma regla.
  4. **Dado** la migración aplicada, **cuando** se revierte, **entonces** desaparecen las dos tablas y la columna, y las
     cuentas quedan intactas; volver a aplicarla da el mismo resultado.
- **Brechas código/docs:** —
- **Cobertura QA:** `test_organizaciones_e2e.MigracionTests` (1–4) y `AltaDeMiembrosTests.test_bootstrap_local_makes_the_first_member_once` (3) · 2026-11-17 · pasa en local

### ORG-02 · De quién es cada cuenta <a id="org-02"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** el equipo sabe de quién es cada cuenta y para quién trabaja cada pedido, en lugar de tomar «la
  cuenta más nueva» o «la primera» de toda la base.
- **Código:** `miembros.py` (`member_for`, `member_of_account`, `default_member`, `accounts`, `same_member`,
  `MiembroRequerido`).
- **Criterios de aceptación:**
  1. **Dado** un solo miembro activo, **cuando** una tarea no dice de quién es, **entonces** es suya, y también son suyas las
     cuentas sin miembro (como antes).
  2. **Dado** varios miembros activos, **cuando** una tarea o una ruta no dice de quién es, **entonces** se detiene con
     `MiembroRequerido` («Hay varios miembros activos y esta operación no dice de cuál: hay que indicarlo.»; 400 en una
     vista) y nunca elige una cuenta por su cuenta.
  3. **Dado** varios miembros activos, **cuando** hay una cuenta sin miembro, **entonces** no es de nadie: ningún selector la
     elige y nadie es su dueño.
  4. **Dado** una instalación sin miembros, **cuando** se pregunta de quién es algo, **entonces** todo cuenta como antes.
- **Brechas código/docs:** con varios miembros activos, las tareas que aún no dicen de quién son (plan semanal,
  preparación automática de piezas, asignación de ideas, vigilantes de Slack, ciclo de perfil) se detienen; por eso un
  miembro nuevo entra inactivo hasta la fase 7.
- **Cobertura QA:** `test_organizaciones_e2e.PublicarTests.test_without_saying_whose_nothing_is_guessed` (2–3), `UnMiembroTests` (1), los `UnMiembro*` (1) y las suites existentes sin miembros (4) · 2026-11-17 · pasa en local

### ORG-03 · Cada miembro publica en su propia cuenta <a id="org-03"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** sus posts salen en su perfil y los del CTO en el del CTO; nunca uno en el perfil del otro.
- **Código:** `editorial.publishing_account(member)` (desde `plan` y `prepare` con el miembro de quien la pide),
  `operador.execute` (publica por la cuenta de la pieza).
- **Criterios de aceptación:**
  1. **Dado** dos miembros con su cuenta oficial, **cuando** cada uno publica su pieza, **entonces** cada post sale por su
     propia cuenta.
  2. **Dado** que la cuenta oficial más nueva de la instalación, con la credencial más nueva, es del CTO, **cuando** se
     prepara o publica una pieza de Gustavo, **entonces** sale por la cuenta de Gustavo y no se escribe nada en la del CTO.
  3. **Dado** dos miembros activos, **cuando** Gustavo pide la próxima pieza, **entonces** recibe 400 (el calendario aún es
     de toda la instalación, fase 4); con el CTO inactivo la pieza se prepara y publica en la cuenta de Gustavo.
- **Brechas código/docs:** el calendario, el hueco del día y los topes de CONT-09 siguen siendo de toda la instalación
  (fases 2 y 4).
- **Cobertura QA:** `test_organizaciones_e2e.PublicarTests` · 2026-11-17 · pasa en local

### ORG-04 · Cada miembro lee con su propia cuenta <a id="org-04"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** las respuestas a sus comentarios, la relectura de sus posts, su perfil y su analítica salen de
  su propia cuenta `directo`, nunca de la del CTO.
- **Código:** `respuestas.reader_account`, `respuestas.publications`, `metricas.publications`/`due`,
  `operador._own_posts_reader`/`_find_own_post`, `alertas_slack._reader`, `perfil.read_profile`,
  `analitica.account_for`, `connectors_linkedin.status_payload`.
- **Criterios de aceptación:**
  1. **Dado** dos miembros, **cuando** el equipo lee para uno, **entonces** usa la primera cuenta lectora de ese miembro.
  2. **Dado** que la cuenta lectora del CTO es la más antigua y muestra un post idéntico al de Gustavo, **cuando** se
     publica el de Gustavo, **entonces** no se toma el del CTO por suyo: sale y se confirma releyendo el perfil de Gustavo.
  3. **Dado** dos miembros con posts publicados, **cuando** se leen comentarios o métricas, **entonces** cada uno ve solo
     los posts de sus cuentas.
  4. **Dado** la analítica, **cuando** el CTO pide una cuenta de Gustavo, **entonces** recibe 400, igual que con una cuenta
     desconocida.
  5. **Dado** Ajustes › LinkedIn, **cuando** cada uno lo abre, **entonces** ve su propia credencial.
- **Brechas código/docs:** —
- **Cobertura QA:** `test_organizaciones_e2e.LectoresTests`, `SesionesTests.test_the_cto_cannot_connect_or_replace_gustavos_credential` (5) · 2026-11-17 · pasa en local

### ORG-05 · Sesión del navegador y credencial oficial: solo su dueño <a id="org-05"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** nadie más, ni siquiera el administrador, puede abrir la vista remota de su sesión de LinkedIn
  ni conectar o reemplazar su credencial oficial.
- **Código:** `conexion.require_owner` en `start`, `poll`, `new_link` y `cancel`; `conexion._usable` (canje del enlace y
  `forward_auth`); `connectors_linkedin.connect_member` (motivo `dueno`).
- **Criterios de aceptación:**
  1. **Dado** la cuenta `directo` de Gustavo, **cuando** el CTO (u otro usuario) intenta abrirla, consultarla, pedir otro
     enlace o cancelarla, **entonces** recibe 403 y no se llama al servicio del navegador.
  2. **Dado** la cuenta del CTO, **cuando** Gustavo, administrador, intenta abrirla, **entonces** recibe 403.
  3. **Dado** una vista abierta por su dueño, **cuando** la cuenta deja de ser suya, **entonces** el enlace y la cookie dejan
     de valer al instante.
  4. **Dado** que LinkedIn responde con el miembro de Gustavo en el OAuth del CTO, **cuando** vuelve, **entonces** va a
     `/ajustes?linkedin=error&motivo=dueno`, la credencial de Gustavo no cambia y queda `linkedin.oauth_failed`
     (`kind: owner`).
  5. **Dado** una instalación sin miembros, **cuando** alguien abre la sesión, **entonces** solo puede el usuario de
     `REFERENTS_GUSTAVO_USERNAME`.
- **Brechas código/docs:** no hay ruta para desconectar una credencial. La PWA y la app no tienen texto propio para
  `motivo=dueno` (muestran el genérico).
- **Cobertura QA:** `test_organizaciones_e2e.SesionesTests` (1–4), `UnMiembroStartTests`/`TicketTests`/`EndTests` · 2026-11-17 · pasa en local

### ORG-06 · Pausas por miembro; parada total de la máquina <a id="org-06"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** una pausa de una cuenta del CTO no frena sus escrituras, y al revés. La parada total sigue
  deteniendo todo.
- **Código:** `operador.execute` y `operador.final_write_gate` con `miembros.same_member`; `globally_paused`
  (`OPERATOR_PAUSED`, `OperatorControl`).
- **Criterios de aceptación:**
  1. **Dado** una cuenta del CTO en pausa, **cuando** sale el post de Gustavo, **entonces** se publica; el del CTO queda
     aprobado con «Otro conector de la misma cuenta está en pausa.». Y al revés.
  2. **Dado** una pausa que llega durante la subida de la imagen, **cuando** es de otro miembro, **entonces** el post sale;
     **cuando** es de su propia cuenta, **entonces** no se escribe (`policy_changed`, «Cuenta o máquina en pausa»).
  3. **Dado** la parada total (desde la app o `OPERATOR_PAUSED`), **cuando** sale cualquier post, **entonces** no sale
     ninguno, tampoco si llega durante la subida.
- **Brechas código/docs:** — (los 429, los bloqueos y los topes son por miembro desde la fase 2: [ORG-10](#org-10) y
  [ORG-11](#org-11)).
- **Cobertura QA:** `test_organizaciones_e2e.PausasTests` · 2026-11-17 · pasa en local

### ORG-07 · Quién decide referentes y experimentos <a id="org-07"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** decide los referentes protegidos y los experimentos el dueño de la cuenta o el administrador de
  la organización; el CTO decide los de sus cuentas, no los de Gustavo.
- **Código:** `referentes.is_gustavo(user, account)` y `require_gustavo(user, account)` (`miembros.can_decide`), usados
  por `referentes.manage`/`initialize`/`decide`, `experimentos.decide`, `operador.add_referent`/`set_referent_kind` y
  `ReferentOutput.can_manage_protected`.
- **Criterios de aceptación:**
  1. **Dado** un referente de una cuenta de Gustavo, **cuando** el CTO intenta protegerlo, **entonces** recibe 403 y
     `can_manage_protected` es falso para él; Gustavo puede.
  2. **Dado** una cuenta del CTO, **cuando** decide el CTO o el administrador, **entonces** se acepta.
  3. **Dado** que hay miembros, **cuando** decide un usuario que se llama como `REFERENTS_GUSTAVO_USERNAME` pero no es
     miembro, **entonces** no puede.
- **Brechas código/docs:** el mensaje sigue diciendo «Solo Gustavo puede decidir…» (fase 3).
- **Cobertura QA:** `test_organizaciones_e2e.DecidirTests` · 2026-11-17 · pasa en local

### ORG-08 · Alta de miembros por comando <a id="org-08"></a>

- **Dónde:** backend (servidor)
- **Estado:** funciona
- **Qué hace para Gustavo:** da de alta a otra persona de su organización con su propio usuario; ella conecta después sus
  propias cuentas.
- **Código:** `manage.py operador --usuario <admin> miembro --nombre … --usuario-nuevo … [--rol …] [--activo|--no-activo]
  [--admin|--no-admin] [--grupo lectura|operacion|revision]`, `manage.py operador --usuario <admin> miembros` (listado);
  `miembros.save_member`.
- **Criterios de aceptación:**
  1. **Dado** el administrador, **cuando** da de alta a alguien nuevo, **entonces** se crea su usuario sin contraseña
     (se fija con `manage.py changepassword`) y su miembro, **inactivo** salvo `--activo`, sin ninguna cuenta de LinkedIn.
  2. **Dado** el mismo alta otra vez, **cuando** se repite, **entonces** solo actualiza nombre, rol y lo que se indique;
     no duplica nada.
  3. **Dado** alguien que no es administrador activo, un usuario técnico, un usuario inválido, un grupo inexistente,
     quitarse a sí mismo la actividad o el rol de administrador, o un miembro de otra organización, **cuando** se intenta,
     **entonces** falla con el motivo y no cambia nada.
- **Brechas código/docs:** no hay pantalla de alta (fase 7).
- **Cobertura QA:** `test_organizaciones_e2e.AltaDeMiembrosTests` · 2026-11-17 · pasa en local

### ORG-09 · Mundo de QA con un segundo miembro <a id="org-09"></a>

- **Dónde:** backend · QA
- **Estado:** funciona
- **Qué hace para Gustavo:** el mundo de QA sigue teniendo a `qa` como único miembro; con `--segundo-miembro`, también a
  `qa-cto` («CTO de prueba») con sus propias cuentas simuladas, para las fases siguientes.
- **Código:** `seed_qa` (`members`, `accounts`, `--segundo-miembro`).
- **Criterios de aceptación:**
  1. **Dado** `seed_qa` sin opciones, **cuando** termina, **entonces** `qa` es el único miembro, administrador, y dueño de
     todas las cuentas.
  2. **Dado** `--segundo-miembro`, **cuando** termina, **entonces** existe `qa-cto`, activo, con su cuenta simulada y su API
     oficial simulada, y entra con la contraseña de QA.
  3. **Dado** una nueva siembra sin la opción, **cuando** termina, **entonces** vuelve a haber un solo miembro.
- **Brechas código/docs:** ningún flujo de Maestro usa todavía el segundo miembro.
- **Cobertura QA:** `test_seed_qa.test_one_member_owns_the_world_and_a_second_one_only_on_request` · 2026-11-17 · pasa en local

### ORG-10 · Un ritmo de LinkedIn por miembro <a id="org-10"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** su ritmo en LinkedIn (cuándo escribe, cuánto al día y a la semana, cuántos perfiles lee) es
  suyo y el del CTO es del CTO: lo que hace uno no gasta los cupos del otro ni lo hace esperar. Sus dos cuentas (API
  oficial y navegador) siguen compartiendo el suyo, porque son la misma persona para LinkedIn.
- **Código:** `operador.policy_lock(member)`, `reserve_spacing`/`release_spacing`/`spacing_ok`/`prepare_day_schedule`/
  `post_due`, `limits(now, member)`, `writes(account, capability, member)`, `capacity_left`, `profile_read_cap`/
  `profile_reads_used`/`reserve_profile_read`; `miembros.policy_key` (`'member'` para el primer miembro, `'member:<id>'`
  para los demás); `autopiloto.tick` salta las cuentas de nadie (`unowned`).
- **Criterios de aceptación:**
  1. **Dado** dos miembros activos con el tope de CONT-09 del `.env` (1 al día), **cuando** cada uno publica su post del
     día, **entonces** salen los dos; un segundo post de Gustavo ese día queda aprobado con «Tope diario o semanal de
     CONT-09 alcanzado».
  2. **Dado** el hueco que reservó una escritura de Gustavo y su última escritura, **cuando** escribe otra cuenta suya,
     **entonces** espera; **cuando** escribe una del CTO, **entonces** no. Cada uno sortea su propia apertura del día, una
     sola vez.
  3. **Dado** `OPERATOR_DAILY_LIMITS=RED-01=2` y dos seguimientos de Gustavo (uno por cada cuenta suya), **cuando** el CTO
     sigue a alguien, **entonces** le quedan sus 2; si su ajuste baja a 1, el de Gustavo sigue en 2.
  4. **Dado** `OPERATOR_PROFILE_READ_DAILY_LIMIT=2`, **cuando** Gustavo lee dos perfiles (una por cada cuenta), **entonces**
     la tercera espera y el CTO sigue leyendo con su propio tope.
  5. **Dado** dos reservas a la vez en las dos cuentas de Gustavo con una lectura disponible, **cuando** corren,
     **entonces** solo una la obtiene; mientras el candado de Gustavo está tomado, el CTO reserva sin esperar.
  6. **Dado** la base de producción antes de esta fase (rampa en etapa 1, notas del mes, agenda de hoy, lecturas de perfil
     de hoy, todo con `target='member'`), **cuando** existe el primer miembro, **entonces** ve exactamente lo mismo (sin
     reinicio, sin eventos nuevos); un segundo miembro empieza de cero con su clave.
  7. **Dado** una cuenta sin miembro con varios miembros activos, **cuando** corre el autopiloto, **entonces** la salta y
     sigue con las demás.
- **Brechas código/docs:** el calendario (`urgente.assign_slots`, `confirm_day`), el plan semanal y el resumen semanal aún
  no dicen de quién son: con varios miembros activos se detienen con `MiembroRequerido` (fase 4).
- **Cobertura QA:** `test_organizaciones_e2e.RitmoPorMiembroTests` (1–4, 7), `ConcurrenciaTests` (5),
  `EstadoDeGustavoTests` (6), `test_fase2_curso` (un miembro: el hueco y las lecturas los comparten sus cuentas) · 2026-11-17 · pasa en local

### ORG-11 · Rampa, notas y bloqueos del proveedor por miembro <a id="org-11"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** la rampa de invitaciones, su salud (la aceptación), las notas del mes, el tier y los
  bloqueos de LinkedIn son de cada uno: si LinkedIn frena al CTO, Gustavo sigue invitando. Lo que es de la empresa sigue
  siendo de la empresa: a una persona la invita uno solo, y a quien LinkedIn rechazó no la vuelve a invitar nadie.
- **Código:** `red.ramp_start`/`ramp_state`/`invitation_health`/`review_health`/`ramp_limits`/`health_snapshot`/
  `invites_blocked`, `note_policy`/`note_blocked`/`note_room`/`reserve_note`/`send_invitation`, `provider_failure`;
  `mensajes_comprador._notes`/`note_hold`; `red.invitation_reserved` y `recipient_blocked` (de la organización).
- **Criterios de aceptación:**
  1. **Dado** la rampa de Gustavo en su etapa y el CTO con `5/25,8/40,10/50` desde la etapa 0, **cuando** se calcula,
     **entonces** Gustavo invita lo de su etapa y el CTO 5 al día.
  2. **Dado** 20 invitaciones maduras del CTO sin aceptar, **cuando** se revisa la salud, **entonces** se pausan solo las
     suyas (y su cuenta); las de Gustavo siguen.
  3. **Dado** Gustavo en `free` con 3 notas al mes y el CTO en `premium` con 5, **cuando** cada uno reserva, **entonces** se
     descuentan aparte; un rechazo de notas de LinkedIn al CTO bloquea solo las suyas.
  4. **Dado** un `cannot_resend_yet` a cada uno, **cuando** llega el segundo destinatario rechazado al CTO, **entonces** se
     pausan solo sus invitaciones; un 429 al CTO tampoco frena a Gustavo. La persona rechazada queda bloqueada para todos.
  5. **Dado** una persona que Gustavo ya invitó, **cuando** el CTO quiere invitarla, **entonces** espera («Ya existe otra
     intención o envío para el destinatario»).
- **Brechas código/docs:** el registro compartido de personas (quién atiende a quién) es la fase 6.
- **Cobertura QA:** `test_organizaciones_e2e.RitmoPorMiembroTests` · 2026-11-17 · pasa en local

### ORG-12 · El ritmo de cada miembro se ajusta aparte <a id="org-12"></a>

- **Dónde:** backend (servidor)
- **Estado:** funciona
- **Qué hace para Gustavo:** el CTO puede empezar con una cuenta gratuita y dormida, con pocas invitaciones al día y todo
  en «aprobación», sin tocar el ritmo de Gustavo.
- **Código:** `Member.settings`; `miembros.MEMBER_SETTINGS`, `setting`, `validate_setting`, `effective_settings`,
  `save_settings`; `manage.py operador --usuario <admin> ajustes --miembro <usuario> [--fijar VARIABLE=VALOR …]
  [--quitar VARIABLE …]`.
- **Criterios de aceptación:**
  1. **Dado** el administrador, **cuando** fija variables del ritmo de un miembro (`LINKEDIN_ACCOUNT_TIER`,
     `LINKEDIN_INVITE_NOTE_MONTHLY_LIMIT`, `OPERATOR_DAILY_LIMITS`, `OPERATOR_WEEKLY_LIMITS`, `OPERATOR_INVITE_RAMP_STAGES`,
     `OPERATOR_INVITE_RAMP_START`, `OPERATOR_PROFILE_READ_DAILY_LIMIT`, `OPERATOR_AUTONOMY`, `EDITORIAL_POST_TIME`),
     **entonces** valen solo para ese miembro; las demás siguen las del `.env`. El comando muestra cada valor con su origen
     (miembro, entorno o por defecto).
  2. **Dado** un valor inválido (una etapa por encima del máximo, una variable o capacidad desconocida, una hora fuera de
     `OPERATOR_WINDOW`, un tier inexistente, fijar y quitar la misma) o alguien que no es el administrador activo de su
     organización, **cuando** se intenta, **entonces** falla con el motivo y no cambia nada.
  3. **Dado** un cambio, **cuando** se guarda, **entonces** queda auditado (`organization.member_settings`, antes y después);
     repetirlo no cambia nada ni audita otra vez; `--quitar` vuelve a la del `.env`.
- **Brechas código/docs:** no hay pantalla (fase 5).
- **Cobertura QA:** `test_organizaciones_e2e.AjustesTests` · 2026-11-17 · pasa en local

### ORG-13 · Avisos de Slack del ritmo de cada miembro <a id="org-13"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** con un solo miembro, los avisos son los de siempre. Con dos, cada aviso de cupos, rampa,
  aceptación, lecturas, propuestas por caducar, post del día, comentarios e invitaciones sale para cada uno y dice de
  quién es; lo de la empresa (gasto de IA, cola, navegador, compradores) sale una vez.
- **Código:** `alertas_slack.por_miembro`, `hers`, `named`; `read_caps`/`write_caps`/`profile_reads_today` por miembro;
  `cuenta_en_pausa` nombra al dueño; `summary_lines` por miembro; `unreported` (el aviso de antes de medianoche).
- **Criterios de aceptación:**
  1. **Dado** el mismo estado sin miembros y con un miembro, **cuando** corren todos los vigilantes, **entonces** emiten
     exactamente las mismas claves y textos.
  2. **Dado** dos miembros activos, **cuando** corren, **entonces** ninguno falla; los avisos de Gustavo conservan su
     clave y dicen «Barrio · Gustavo · …»; los del CTO llevan su id en la clave y su nombre; el gasto de IA y la falta de
     enlace de agenda salen una vez. El fallo de un miembro no silencia al otro.
  3. **Dado** un evento de una vez al día a las 23:58 que ningún vistazo vio ese día, **cuando** mira el primero del día
     siguiente, **entonces** avisa una vez y no lo repite.
- **Brechas código/docs:** los avisos van al mismo canal de Slack; avisos y push solo a su dueño son la fase 5.
- **Cobertura QA:** `test_organizaciones_e2e.VigilantesTests` (1–2), `test_alertas_slack.BuyerSequenceAlertTests`/
  `BuyerReplyAlertTests` (3) · 2026-11-17 · pasa en local

### ORG-14 · La identidad de la organización y de cada miembro, en la base <a id="org-14"></a>

- **Dónde:** backend (servidor)
- **Estado:** funciona
- **Qué hace para Gustavo:** lo que el equipo sabe de ProjectApp (posicionamiento, pilares, servicios, oferta, casos,
  modalidades) y de cada miembro (nombre, identidad, relación con la empresa, límites, modalidades, marca) se cambia sin
  desplegar, con validación e historial. Al desplegar, su perfil y el de ProjectApp quedan con los textos de siempre.
- **Código:** `Organization.profile`, `Member.profile`, `IdentityRevision`, `identidad.py` (`of`, `save_profile`,
  `seed_first`, `validate_*`), migraciones `0057_identidad` y `0058_identidad_inicial`, `recursos/identidad-inicial.json`;
  comandos `operador perfil` y `operador perfil-organizacion`.
- **Criterios de aceptación:**
  1. **Dado** la base de hoy, **cuando** migra, **entonces** ProjectApp y Gustavo tienen los textos exactos de antes (revisión
     1 de cada perfil) y su voz es su documento «Tono de voz» (versión 1 confirmada); revertir lo deja como estaba.
  2. **Dado** un miembro, **cuando** fija un campo de su perfil, **entonces** se valida el perfil entero (nombre solo letras,
     sin llaves, modalidades existentes, longitudes) y queda una revisión con quién, cuándo, antes y después; repetirlo no
     crea otra.
  3. **Dado** otro usuario (también el administrador), **cuando** intenta cambiar el perfil de ella, **entonces** se rechaza;
     el de la organización solo lo cambia su administrador activo.
  4. **Dado** varios miembros activos, **cuando** algo lee una identidad sin decir de quién, **entonces** `MiembroRequerido`.
- **Brechas código/docs:** el formulario en la app es de la fase 7; hoy es por comando.
- **Cobertura QA:** `test_identidad_prompts` (1), `test_organizaciones_e2e.PerfilComandoTests` (2–3),
  `IdentidadPorMiembroTests.test_without_saying_whose_identity_several_active_members_raise` (4) · 2026-11-17 · pasa en local

### ORG-15 · Cada texto del equipo se escribe como su miembro <a id="org-15"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** comentarios, respuestas, primeros mensajes, clasificaciones, piezas editoriales, el líder, los
  referentes y las infografías se arman con el nombre, la identidad, los límites y la voz del dueño de la cuenta. Los
  suyos son byte a byte los de antes, así que la caché de prompts del proveedor sigue valiendo.
- **Código:** las plantillas `{nombre}`/`{alias}`/`{decisor}` de cada módulo y sus funciones por miembro (lista en el
  [plan](../plan-organizaciones.md#fase-3-lo-construido)); `identidad.keyed`/`unkeyed` para las claves guardadas.
- **Criterios de aceptación:**
  1. **Dado** Gustavo, **cuando** se arma cualquiera de los 109 textos fijados, **entonces** su sha256 es el de `origin/main`.
  2. **Dado** el CTO con su perfil, **cuando** el equipo redacta un comentario, una respuesta, un primer mensaje, una
     clasificación o una pieza editorial en su cuenta, **entonces** el prompt, el mensaje y el esquema no llevan el nombre,
     la identidad, los límites ni la voz de Gustavo y sí los de ella; las claves guardadas vuelven a su nombre de siempre.
  3. **Dado** su cuenta, **cuando** se dibuja una infografía o se titula un carrusel, **entonces** dice su nombre; la regla
     de infografías que lee el diseñador firma sus ejemplos con su nombre (misma versión de regla que la de Gustavo).
  4. **Dado** cualquier miembro, **cuando** una pregunta web lleva su nombre, **entonces** no sale a la web.
- **Brechas código/docs:** — (desde la fase 4 cada miembro tiene su memoria, su orientación, su plan, su resumen y su
  revisión: [ORG-18](#org-18) a [ORG-20](#org-20)).
- **Cobertura QA:** `test_identidad_prompts.GustavoSinCambiosTests` (1), `test_organizaciones_e2e.IdentidadPorMiembroTests`
  (2–4) · 2026-11-17 · pasa en local

### ORG-16 · La voz de cada miembro: provisional y aprendida <a id="org-16"></a>

- **Dónde:** backend (servidor)
- **Estado:** funciona; el aprendizaje está apagado (`VOICE_LEARNING_ENABLED=false`)
- **Qué hace para Gustavo:** su voz sigue siendo su documento. Un miembro sin documento escribe con una voz neutra y sus
  borradores quedan marcados «voz provisional» (`voice`); con muestra suficiente, una llamada de pago propone su documento
  desde sus propias señales, que ella revisa y confirma antes de que se use.
- **Código:** `voz.py` (`current`, `collect_signals`, `sample`, `propose`, `confirm`, `discard`), `VoiceDocument`,
  `VoiceSignal`, `recursos/voz-provisional.md`, `recursos/voz-guia.md`; comando `operador voz`.
- **Criterios de aceptación:**
  1. **Dado** un miembro sin documento confirmado que no es el primero, **cuando** el equipo escribe en su nombre,
     **entonces** usa la voz provisional con su nombre y el borrador guarda `{"tipo": "provisional"}`.
  2. **Dado** menos de `VOICE_LEARNING_MIN_TEXTS` textos suyos aprobados o editados (o el aprendizaje apagado),
     **cuando** se pide una propuesta, **entonces** no se propone nada ni se paga.
  3. **Dado** la muestra, **cuando** se propone, **entonces** la llamada lee solo sus señales, la propuesta no se usa hasta
     que ella la confirma, y confirmada pasa a ser su voz con número de versión; nadie más la confirma.
- **Brechas código/docs:** exponer la marca «voz provisional» en la PWA y la app es de la fase 7.
- **Cobertura QA:** `test_organizaciones_e2e.VozTests`, `IdentidadPorMiembroTests` (1) · 2026-11-17 · pasa en local

### ORG-17 · Los textos que ven las personas nombran al dueño <a id="org-17"></a>

- **Dónde:** backend, PWA, app
- **Estado:** funciona
- **Qué hace para Gustavo:** los avisos y notas que decían «Gustavo» dicen el nombre del dueño de la cuenta (o «el dueño
  de la cuenta»); para él siguen igual. En la PWA y la app: «Solo el dueño de la cuenta o el administrador.», «Tu aporte» y
  «Aplicado por ti».
- **Código:** `identidad.owner_name`; `operador`, `red`, `respuestas`, `referentes`, `rescate`, `retoque`, `entrega_lead`,
  `calentamiento`, `sin_posts`, `connectors_linkedin`, `perfil_views`; `ProtectedReferent`, `ReferentDecision`,
  `compartido/src/logic/perfil.ts`.
- **Criterios de aceptación:**
  1. **Dado** una cuenta del CTO, **cuando** un texto del servidor nombra a quien decide, **entonces** dice su nombre.
  2. **Dado** una cuenta de nadie con varios miembros, **cuando** se nombra al dueño, **entonces** «el dueño de la cuenta».
- **Brechas código/docs:** `next_step.owner = 'gustavo'` en la API se queda como sinónimo de «tú» hasta la fase 5; las
  etiquetas de las opciones de los modelos (`models.py`) aún dicen «Gustavo». Las razones de las guardas nombran a la
  autora en la revisión final (`guardas.text_checks`, fase 4); las de los chequeos previos del editorial, el editor visual
  y las imágenes, que reciben solo los hechos, todavía dicen «Gustavo» en la nota de la pieza.
- **Cobertura QA:** `IdentidadPorMiembroTests.test_without_saying_whose_identity_several_active_members_raise` (1–2); los
  textos de Gustavo, sus pruebas de siempre · 2026-11-17 · pasa en local

### ORG-18 · Cada miembro tiene su calendario, su plan, su resumen y su revisión <a id="org-18"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** él sigue viendo su calendario, su plan, su resumen y su revisión como siempre. Cuando el CTO
  esté activo, cada uno tiene su post del día (y su segundo post), su plan de la semana con los pilares de ProjectApp, su
  resumen del lunes y su revisión del mes, con sus posts y su audiencia; los cambios de estrategia que apruebe van a su
  orientación.
- **Código:** `member` en `EditorialPiece`, `WeeklyPlan`, `WeeklySummary`, `MonthlyReview` y `AudienceSnapshot` (migraciones
  `0059_contenido_por_miembro` y `0060_contenido_del_primer_miembro`); `miembros.own`, `each_member`, `job_parts`,
  `job_params`, `of_job`; `editorial`, `urgente`, `estrategia`, `resumen_semanal`, `revision_mensual`, `metricas`,
  `autopiloto._editorial`, `bucle_resultados` (`--miembro`).
- **Criterios de aceptación:**
  1. **Dado** dos miembros activos, **cuando** pasa el autopiloto, **entonces** cada uno tiene su pieza del día en su cuenta,
     a su hora y con su trabajo (el de Gustavo con el id y los parámetros de antes).
  2. **Dado** el domingo por la tarde, el lunes por la mañana o el primer lunes del mes, **cuando** pasa el autopiloto,
     **entonces** el plan, el resumen y la revisión se encolan para cada uno y ninguno se detiene con `MiembroRequerido`.
  3. **Dado** que el trabajo de un miembro falla, **cuando** pasa el autopiloto, **entonces** el del otro sale igual y el
     fallo queda registrado con de quién era; si fallan todos, llega al informe.
  4. **Dado** los posts y la audiencia de cada uno, **cuando** se escribe el resumen o la revisión, **entonces** cada uno
     lleva solo los suyos y su aviso es suyo; las rutas del resumen y de la revisión le muestran a cada uno los suyos.
  5. **Dado** la base de hoy, **cuando** migra, **entonces** todo pasa a ser de Gustavo sin duplicados; corrida otra vez no
     cambia nada; revertida queda como estaba; y con un solo miembro la API responde lo mismo que antes.
- **Brechas código/docs:** el tablero de Resultados (`resultados.build`) y los detalles por id aún leen a todos los
  miembros (fase 5).
- **Cobertura QA:** `test_organizaciones_e2e.ContenidoTests` (1–4), `ContenidoMigracionTests` (5), clases `UnMiembro…` del
  plan, el calendario, el resumen y la revisión (5) · 2026-11-18 · pasa en local

### ORG-19 · Su memoria y sus hechos; los de la empresa los comparte el administrador <a id="org-19"></a>

- **Dónde:** backend (servidor)
- **Estado:** funciona
- **Qué hace para Gustavo:** su memoria queda como está. Lo que confirma un miembro (respuestas, datos de sus capturas,
  notas, correcciones) es solo suyo: nunca llega a los textos, las imágenes ni las decisiones de otro. Un hecho de la empresa
  (un caso, una cifra de ProjectApp) llega a todos cuando el administrador lo comparte.
- **Código:** `hechos.py` (`scope`, `latest`, `set_fact`, `confirmed_blocks`, `with_company`, `share`, `unshare`),
  `knowledge/memory.py` (`in_scope`, `latest`/`confirmed_blocks(scope)`), `guardas.blocks(member)`/`text_checks`,
  `identidad.facts`/`blocks`, `projectapp.case_facts`; comando `operador hecho-empresa`.
- **Criterios de aceptación:**
  1. **Dado** un hecho confirmado del CTO, **cuando** el director escribe la pieza de Gustavo, **entonces** no lo lee; y al
     revés.
  2. **Dado** una afirmación de experiencia, **cuando** se revisa el texto de un miembro, **entonces** solo la respaldan
     sus hechos y la razón dice su nombre.
  3. **Dado** el administrador activo, **cuando** comparte un hecho de un miembro (`hecho-empresa --compartir CLAVE
     --miembro U`), **entonces** llega a todos como `empresa.<clave>` y queda auditado; otro miembro no puede compartirlo;
     `--retirar` lo quita a todos y la dueña lo conserva.
- **Brechas código/docs:** compartir es por comando; en la app, fase 5 o 7.
- **Cobertura QA:** `test_organizaciones_e2e.ContenidoTests.test_her_facts_never_reach_his_post_and_his_never_hers_but_the_companys_reach_both`
  (1–3) · 2026-11-18 · pasa en local

### ORG-20 · Sus capturas, su galería, sus preguntas y su orientación <a id="org-20"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** lo que graba, sube y responde sigue llegando a sus piezas. El audio o la foto de un miembro solo
  alimentan las piezas de ese miembro; cada uno ve sus capturas y su galería; la pregunta del equipo va a quien es dueño de
  la pieza y solo ella la responde; cada uno tiene su orientación.
- **Código:** `member` en `Capture`, `GalleryPhoto`, `TeamQuestion` y `Orientation`; `capturas.ideas_for_director`/
  `feedback_for_director`, `imagenes.candidates`, `editor_visual.gallery`, `preguntas.py` (`_hers`), `orientacion.row`;
  vistas `capturas_views.Captures`/`Gallery`, `rediseno_views.Questions`/`Facts`/`OrientationView`/`TuTurno`.
- **Criterios de aceptación:**
  1. **Dado** un audio del CTO, **cuando** se procesa, **entonces** es una idea suya y solo su director la lee.
  2. **Dado** una foto de cada uno, **cuando** se arma la galería de una pieza, **entonces** solo se ofrece la de su dueño,
     aunque el brief nombre la del otro.
  3. **Dado** una pregunta del director de la pieza del CTO, **cuando** Gustavo intenta responderla, **entonces** 403; su
     respuesta es memoria del CTO y Tu turno le muestra a cada uno solo las suyas.
- **Brechas código/docs:** — (los detalles por id comprueban dueño desde la fase 5, [ORG-23](#org-23)).
- **Cobertura QA:** `ContenidoTests.test_her_audio_and_her_photos_feed_only_her_pieces` (1–2),
  `test_a_team_question_goes_to_the_member_who_owns_the_piece` (3) · 2026-11-18 · pasa en local

### ORG-21 · Posts escalonados y temas coordinados entre miembros <a id="org-21"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** su hora no cambia. El post del CTO sale al menos `EDITORIAL_POST_STAGGER_MINUTES` (15) después;
  su plan semanal sabe lo que Gustavo ya planeó esa semana y no repite sus temas, sin pagar una llamada más.
- **Código:** `editorial.staggered_times`, `post_stagger`, `post_time(member)`; `estrategia.team_topics`, `same_topic`,
  `_pick` (`team_planned` en el pedido del plan).
- **Criterios de aceptación:**
  1. **Dado** las dos horas a las 08:30, **cuando** se calcula la del CTO, **entonces** 08:45 (con 40 minutos, 09:10); la del
     primer miembro nunca se mueve.
  2. **Dado** el plan de Gustavo hecho, **cuando** se planea la semana del CTO, **entonces** el pedido lleva sus temas, una
     opción que repite uno nunca se elige (el día queda sin idea y el plan lo advierte) y se pagan dos llamadas, no tres; el
     pedido de Gustavo solo es el de antes.
- **Brechas código/docs:** —
- **Cobertura QA:** `ContenidoTests.test_each_member_has_her_post_of_the_day_on_the_same_day_at_her_own_hour` (1),
  `test_each_member_plans_her_week_and_the_second_plan_avoids_the_first_ones_topics` (2) · 2026-11-18 · pasa en local

### ORG-22 · Un post en voz provisional nunca sale solo <a id="org-22"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** nada cambia para él. Mientras la voz de un miembro es provisional, su CONT-09 está en
  «aprobación» aunque su ajuste diga «auto»; un post escrito con la voz provisional espera a una persona incluso después de
  que ella confirme su voz.
- **Código:** `autopiloto.autonomy`, `provisional_voice`, `provisional_draft`, `policy_review`; `operador.create_proposal`
  (copia la marca `voice` de la pieza).
- **Criterios de aceptación:**
  1. **Dado** el CTO con `CONT-09=auto` y voz provisional, **cuando** llega su hora, **entonces** el post de Gustavo sale y
     el suyo queda propuesto, con la marca `{"tipo": "provisional"}`.
  2. **Dado** que confirma su voz, **cuando** pasa el autopiloto, **entonces** ese post sigue esperando; sale cuando una
     persona lo aprueba.
- **Brechas código/docs:** — (la marca «Voz provisional» se ve en Tu turno desde la fase 5, [ORG-26](#org-26)).
- **Cobertura QA:** `ContenidoTests.test_a_post_in_a_provisional_voice_never_goes_out_on_its_own` (1–2) · 2026-11-18 · pasa
  en local

### ORG-23 · Cada ruta dice de quién son sus datos; lo de otro miembro no existe <a id="org-23"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** nada cambia para él. Con el CTO activo, cada uno ve y maneja solo lo suyo: sus contactos, sus
  conversaciones, sus borradores, sus notas, su Tu turno, sus Resultados, sus cuentas y sus sesiones. Ni el administrador ve
  lo privado de otro miembro (decisión del 17/11/2026). Pedir algo del otro por su id responde 404, como si no existiera.
- **Código:** `alcance.py` (`RUTAS`, `RAIZ`, `RutaClasificada` en `DEFAULT_PERMISSION_CLASSES`, `OBJETOS`, `DUENO`, `de`,
  `obtener`, `miembro`, `trabajos`, `TODOS`); las vistas de `rediseno_views.py`, `operador_views.py`, `red_views.py`,
  `comprador_views.py`, `editorial_views.py`, `capturas_views.py`, `resultados_views.py`, `revision_views.py`,
  `comunidad_views.py`, `conexion_views.py`, `linkedin_views.py`, `oficina_views.py` y `views.py`.
- **Criterios de aceptación:**
  1. **Dado** una ruta nueva en `team_backend/urls.py` que no está en `alcance.RUTAS`, **cuando** corre la prueba, **entonces**
     falla; y en ejecución la ruta responde 403 («Esta ruta no dice de quién son sus datos…»).
  2. **Dado** dos miembros activos con una fila de cada cosa, **cuando** cada uno pide cualquier ruta del miembro, **entonces**
     ninguna lista trae el texto ni los ids del otro.
  3. **Dado** el id de una fila del otro, **cuando** lo pide por cualquier ruta y método, **entonces** 404 (aunque el cuerpo
     sea inválido) y nada cambia; con un id suyo responde.
  4. **Dado** el CTO sin ser administrador, **cuando** pide `integrity`, `audit`, la lectura de `app/errores` o decide un
     ciclo, **entonces** 403.
  5. **Dado** un solo miembro, **cuando** se leen todas las rutas GET con la semilla de QA y el reloj congelado, **entonces**
     la respuesta es byte a byte la de antes.
  6. **Dado** un id del otro en el cuerpo (la persona, la pieza o la pregunta de una captura; el borrador de un comprador en
     «Mensaje sugerido»), **cuando** lo usa, **entonces** responde como un id inexistente y nada suyo cambia; el
     administrador no ve en la auditoría las acciones propias del otro.
- **Brechas código/docs:** el registro compartido de personas es de la fase 6; el admin de Django ve todo (es del
  superusuario del servidor); el administrador ve metadatos (no contenido) de los trabajos y ciclos de todos.
- **Cobertura QA:** `test_alcance.RutasTests` (1), `DelMiembroTests` (2–3), `OrganizacionYAdministradorTests.
  test_administrator_routes_refuse_the_cto`/`test_an_unclassified_route_is_refused` (4, 1), comparación de 249 lecturas
  contra `350e01b` (5), `CruzadosTests` (6) · 2026-11-18 · pasa en local

### ORG-24 · Un solo embudo de oportunidades que dice quién trajo cada una <a id="org-24"></a>

- **Dónde:** backend, PWA, app
- **Estado:** funciona
- **Qué hace para Gustavo:** ve todas las oportunidades de la empresa, también las que trae el CTO, con «Trajo: …» en cada
  tarjeta cuando hay más de un miembro. La ficha de la persona solo la abre su dueño.
- **Código:** `Opportunity.member`/`origin_member` (migración `0061`), `oportunidades.py` (`create`, `update`, `_origin`, `hers`,
  `_notify`), `rediseno_views.OpportunityOutput` (`registered_by`, `brought_by`, `contact` solo para su dueña);
  `compartido/src/logic/barrio.ts` (`broughtByText`, `personModeOf`, `othersPersonText`), `Oportunidades.tsx` y
  `OportunidadForm.tsx` de las dos apps.
- **Criterios de aceptación:**
  1. **Dado** una oportunidad de un contacto de Gustavo, **cuando** el CTO abre el embudo, **entonces** la ve con el nombre de
     la persona, `brought_by` Gustavo y `contact: null`.
  2. **Dado** que el CTO la edita, **cuando** guarda, **entonces** cambian la etapa y el siguiente paso, y la persona sigue
     siendo la de Gustavo (lo que mande para la persona se ignora); Gustavo sí puede cambiarla.
  3. **Dado** que el CTO intenta vincular un contacto de Gustavo, **cuando** guarda, **entonces** 400 «Persona inexistente».
  4. **Dado** un solo miembro, **cuando** lee el embudo, **entonces** no llegan `registered_by` ni `brought_by`.
- **Brechas código/docs:** —
- **Cobertura QA:** `OrganizacionYAdministradorTests.test_organization_routes_answer_the_same_to_both` (1),
  `test_she_moves_his_opportunity_but_never_its_person` (2), `RecorridoDelCtoTests` (1), comparación de un miembro (4);
  `barrio.test.ts` «Who brought the opportunity» · 2026-11-18 · backend pasa en local; front sin correr en local (CI)

### ORG-25 · Cada aviso tiene dueño: push, preferencias y «Vista» por persona <a id="org-25"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** recibe exactamente lo de hoy: los mismos avisos, el mismo push, sus preferencias y el mismo
  Slack. Con el CTO activo, el aviso de uno no llega al teléfono del otro, y Slack no nombra lo privado de nadie.
- **Código:** `Notification.member`, `OfficePreference.user`, `InboxSeen` (migración `0061`); `notificaciones.avisar(…,
  member=)` (obligatorio), `ORGANIZACION`, `empujar`, `de_cuenta`, `de_contenido`, `de_usuario`, `push_enabled(kind, user)`;
  `alerts.notify(users=, webhook=)`; `alcance.vista`; `alertas_slack.privado`.
- **Criterios de aceptación:**
  1. **Dado** un aviso del CTO, **cuando** se envía, **entonces** se guarda para él y el push va solo a sus dispositivos, nunca
     al canal de Gustavo (`OPERATOR_ALERT_WEBHOOK`).
  2. **Dado** la parada total (aviso de la organización), **cuando** se envía, **entonces** llega a los dos, cada uno con su
     estado de leído y sus preferencias.
  3. **Dado** que el CTO apaga un tipo de push, **cuando** llega un aviso de ese tipo, **entonces** no le llega a él y a
     Gustavo sí; las preferencias de antes son las de Gustavo.
  4. **Dado** un aviso que no dice de quién es con miembros, **cuando** se envía, **entonces** se descarta con un warning.
  5. **Dado** dos miembros activos, **cuando** sale un aviso de Slack de un comentario o una conversación, **entonces** el
     texto es genérico; con uno, el de siempre.
- **Brechas código/docs:** —
- **Cobertura QA:** `test_alcance.AvisosTests` (1–5) · 2026-11-18 · pasa en local

### ORG-26 · «Quién soy» y la marca de voz provisional en las apps <a id="org-26"></a>

- **Dónde:** backend, PWA, app
- **Estado:** funciona
- **Qué hace para Gustavo:** Ajustes › Sesión dice «Has entrado como Gustavo (Fundador) · ProjectApp.». Los borradores del
  CTO escritos con su voz provisional llevan la marca «Voz provisional» en Tu turno.
- **Código:** `oficina_views.Yo` (`GET /api/v1/yo`), `provisional_voice` en las tarjetas de aprobación y de mensaje de Tu
  turno; `compartido` (`getYo`, `useYo`, `sessionLabel`, `provisionalVoice`), `Sesion.tsx`, `TurnoCardView.tsx` y
  `TurnoCard.tsx`; Maestro `15-ajustes-sesion.yaml`.
- **Criterios de aceptación:**
  1. **Dado** un miembro, **cuando** abre Ajustes › Sesión, **entonces** lee su nombre, su rol y su organización; sin miembro,
     su usuario como antes.
  2. **Dado** un borrador con `provisional_voice`, **cuando** se ve en Tu turno, **entonces** lleva la marca; sin ella, no.
- **Brechas código/docs:** —
- **Cobertura QA:** `QuienSoyTests.test_yo_says_who_she_is`, `RecorridoDelCtoTests` (backend); `ajustes.test.ts`,
  `Ajustes.test.tsx`, `AjustesScreen.test.tsx`, `TuTurno.test.tsx`, `TuTurnoScreen.test.tsx` · 2026-11-18 · backend pasa en
  local; front y Maestro sin correr en local (CI)

### ORG-27 · Cada miembro entra con su usuario y solo lee lo suyo <a id="org-27"></a>

- **Dónde:** backend (servidor), PWA, app
- **Estado:** funciona
- **Qué hace para Gustavo:** nada cambia para él. Al CTO se le da un usuario con los grupos `operacion` y `revision` y una
  contraseña que se le entrega en privado; entra a la PWA con su sesión y a la app con su token, y los dos leen solo lo suyo.
- **Código:** `manage.py operador --usuario <admin> miembro … --grupo operacion --grupo revision`, `manage.py changepassword`;
  `auth/login` (sesión), `auth/token` (`DeviceToken`); `alcance.miembro`.
- **Criterios de aceptación:**
  1. **Dado** el CTO con los dos grupos y sin otros permisos, **cuando** entra con contraseña, **entonces** trabaja su cuenta
     (conectar, aprobar, publicar) y una contraseña mala responde 400.
  2. **Dado** su token de la app, **cuando** pide una pieza o una acción de Gustavo, **entonces** 404.
  3. **Dado** una credencial de servicio (sin miembro) con dos miembros activos, **cuando** pide Tu turno o Notificaciones,
     **entonces** 400, nunca los datos de uno.
- **Brechas código/docs:** activarlo es de la fase 7.
- **Cobertura QA:** `RecorridoDelCtoTests.test_the_cto_logs_in_works_her_account_and_never_sees_gustavos` (1–3) · 2026-11-18 ·
  pasa en local

### ORG-28 · Una ficha por persona en la organización <a id="org-28"></a>

- **Dónde:** backend
- **Estado:** funciona; actúa con dos o más miembros activos (con uno, solo registra)
- **Qué hace para Gustavo:** nada cambia para él. Con el CTO activo, una persona de LinkedIn es una sola ficha de ProjectApp:
  se descubre y se clasifica una vez, y cada uno ve en la suya quién la atiende, sin nada privado del otro.
- **Código:** `Person`, `Contact.person` (migración `0062_registro_de_personas`), `registro.py` (`sync`, `card_of`, `view`,
  `known_uids`, `reusable`, `classified`), `red.shared_criterion`, `red._shared_classifications`, `red.discover`,
  `serializers.ContactOutput` (`registro`), migración `0063_registro_inicial`, `miembros.ensure_first_member` → `registro.adopt`.
- **Criterios de aceptación:**
  1. **Dado** la misma persona descubierta por los dos, **cuando** clasifican, **entonces** se paga una sola llamada y el otro
     contacto toma la clasificación de la organización sin la nota ni la evidencia privada; la ficha es una.
  2. **Dado** una persona que la organización ya tiene, **cuando** la búsqueda del otro miembro la encuentra, **entonces** no se
     vuelve a descubrir; una nueva sí.
  3. **Dado** los datos de hoy, **cuando** corre la migración, **entonces** Gustavo atiende a quien ya tocó, los no tocados quedan
     libres, rechazos y salidas definitivas excluyen para todos, y otra corrida no cambia nada; la vuelta deja el registro vacío.
  4. **Dado** un solo miembro, **cuando** lee cualquier ruta o corre un planificador, **entonces** responde lo de antes.
- **Brechas código/docs:** la clasificación reutilizada lleva la orientación privada de quien la pagó (el criterio compartido
  no la incluye).
- **Cobertura QA:** `RegistroTests.test_the_same_person_found_by_both_is_classified_once_and_not_discovered_again` (1–2),
  `RegistroMigracionTests` (3), `UnMiembroRegistroTests`, las suites `UnMiembro*` de red y del comprador y la comparación de
  lecturas y colas contra `feda285` (4) · 2026-11-18 · pasa en local

### ORG-29 · Quien toca primero a una persona se la queda <a id="org-29"></a>

- **Dónde:** backend, PWA, app
- **Estado:** funciona; actúa con dos o más miembros activos
- **Qué hace para Gustavo:** si él sigue, invita, acepta, comenta el post o le responde a alguien primero, esa persona es suya:
  el CTO no la sigue, no la invita, no comenta sus posts, no le responde y no recibe borradores para ella; su ficha dice «La
  atiende Gustavo». Clasificar no cuenta como tocar.
- **Código:** `registro.claim` (en `operador.execute`, fila `FOR UPDATE`), `registro.issue`/`issue_for`/`execution_issue`,
  `check_proposal` (en `operador.create_proposal`), `precheck` (antes de cada borrador pagado), `gate` (planificadores),
  `foreign_uids`, `_leave_queues`, `unclaim`; `red.plan`, `red.check_stages`, `autopiloto._propose_groups`/`_lead_redraft`,
  `mensajes_comprador.prepare`/`_notes`/`_messages`, `respuesta_comprador.prepare`, `respuestas.propose`; `Persona.tsx` y
  `PersonaScreen.tsx` («La atiende <nombre>»).
- **Criterios de aceptación:**
  1. **Dado** que Gustavo sigue a una persona que el CTO también tiene, **cuando** se ejecuta, **entonces** Gustavo la atiende y la
     propuesta abierta y el borrador del CTO para ella salen de sus colas.
  2. **Dado** eso, **cuando** el CTO propone, aprueba o ejecuta algo para ella (también por la API, con sus propios ids) o pide su
     borrador, **entonces** 409 o «La atiende Gustavo.» y no se escribe nada.
  3. **Dado** dos ejecuciones a la vez sobre la misma persona, **cuando** corren, **entonces** una escribe y la otra no.
  4. **Dado** una persona excluida para todos, **cuando** cualquiera la propone o ejecuta, **entonces** se rechaza.
- **Brechas código/docs:** —
- **Cobertura QA:** `RegistroTests.test_the_first_follow_keeps_her_…` (1–2), `RegistroConcurrenciaTests` (3),
  `RegistroTests.test_excluded_for_everyone_nobody_touches_her` (4); `Persona.test.tsx`, `PersonaScreen.test.tsx`,
  `barrio.test.ts` · 2026-11-18 · pasa en local

### ORG-30 · Dos o tres personas por empresa, nunca dos del mismo cargo <a id="org-30"></a>

- **Dónde:** backend
- **Estado:** funciona; actúa con dos o más miembros activos
- **Qué hace para Gustavo:** donde él ya atiende a alguien de una empresa, el CTO no abre a nadie nuevo de esa empresa sin un
  motivo propio; entre los dos, como mucho tres personas por empresa y nunca dos del mismo cargo (LI-08-V006-K02).
- **Código:** `registro.company_issue`, `PEOPLE_PER_COMPANY_MAX`; `sin_posts.company_of`, `same_company`, `cargo_of`.
- **Criterios de aceptación:**
  1. **Dado** que Gustavo atiende a dos personas de Acme, **cuando** el CTO va a seguir a una tercera sin motivo propio,
     **entonces** se rechaza; con motivo (la invitó) y el mismo cargo, también; con otro cargo, sale.
  2. **Dado** tres atendidas de Acme, **cuando** el CTO va por una cuarta, **entonces** se rechaza.
  3. **Dado** un referido o un puente, **cuando** se propone, **entonces** siguen sus propias reglas.
- **Brechas código/docs:** —
- **Cobertura QA:** `RegistroTests.test_one_company_two_or_three_people_…` (1–3) · 2026-11-18 · pasa en local

### ORG-31 · Liberar, pasar y reasignar una persona <a id="org-31"></a>

- **Dónde:** backend, PWA, app
- **Estado:** funciona; actúa con dos o más miembros activos
- **Qué hace para Gustavo:** desde la ficha de una persona que atiende, «Liberar» o «Pasar a <nombre>», siempre con un motivo;
  quien la recibe empieza con la ficha básica y sus notas y mensajes se quedan con él. Como administrador, reasigna a quien
  nadie ha tocado. Una persona en descanso o descartada sin actividad por 180 días queda libre.
- **Código:** `registro.release`, `pass_to`, `card_for`, `reassign`, `release_stale`; `red_views.ContactRelease`, `ContactPass`,
  `ContactReassign`; `red.discard(…, for_everyone)`, `registro.exclusion_issue`; `compartido` (`releaseContact`, `passContact`, `useReleaseContact`,
  `usePassContact`, `attendedBy`, `passTargets`).
- **Criterios de aceptación:**
  1. **Dado** una persona suya, **cuando** la pasa al CTO con motivo, **entonces** el CTO la atiende con una ficha sin sus notas
     y queda auditado con el motivo; sin motivo, 400.
  2. **Dado** que ya no la atiende, **cuando** intenta liberarla, **entonces** 403; quien la atiende la libera con motivo.
  3. **Dado** el administrador, **cuando** reasigna a alguien sin tocar, **entonces** queda asignada; si alguien la atiende, 400;
     el CTO (no administrador) recibe 403. Nombrándola por el contacto del CTO, la respuesta es la ficha, nada de su contacto.
  4. **Dado** que Gustavo la atiende, **cuando** el CTO la descarta «para todos», **entonces** 409 y nada cambia; su descarte de
     su propio contacto sí se hace.
- **Brechas código/docs:** falta un flujo de Maestro con dos miembros (fase 7).
- **Cobertura QA:** `RegistroTests.test_release_and_pass_…` (1–3), `RegistroTests.test_only_who_attends_her_excludes_…` (3–4);
  `Persona.test.tsx`, `PersonaScreen.test.tsx` · 2026-11-18 · pasa en local

### ORG-32 · Referentes de la organización: una lectura y un comentario por post <a id="org-32"></a>

- **Dónde:** backend
- **Estado:** funciona; actúa con dos o más miembros activos
- **Qué hace para Gustavo:** sus referentes son los de ProjectApp: cada post se lee una vez (las lecturas se reparten entre
  las cuentas) y lo comenta un solo miembro, el primero que lo propone. La espera de 48 h por autor cuenta los comentarios de
  los dos. Los cambios de referentes los sigue decidiendo él (o el administrador).
- **Código:** `referentes.to_read`, `share_posts`, `scanned_everywhere`; `PostClaim`, `registro.claim_post`, `post_issue`,
  `claimed_by_others`, `peers`; `operador.observe`, `autopiloto._observe`/`_propose`/`_propose_groups`/`_lead_redraft`/
  `recent_comment_authors`, `operador.propose_comment`, `analisis_referentes.report`.
- **Criterios de aceptación:**
  1. **Dado** cuatro referentes y dos cuentas lectoras, **cuando** observan, **entonces** cada referente lo lee una sola cuenta
     (la del hash) y sus posts llegan a las dos.
  2. **Dado** que Gustavo propone un comentario en un post, **cuando** el CTO lo propone (también por la API o el borrador
     pagado), **entonces** «Este post ya lo comenta Gustavo.».
  3. **Dado** un comentario de Gustavo a un referente, **cuando** el CTO va por otro post del mismo autor, **entonces** espera.
  4. **Dado** que una cuenta leyó los comentaristas de un post, **cuando** la otra descubre, **entonces** no lo vuelve a leer; los
     descubiertos entran sin dueño.
- **Brechas código/docs:** —
- **Cobertura QA:** `ReferentesDeLaOrganizacionTests` (1–4) · 2026-11-18 · pasa en local

### ORG-33 · El reparto de candidatos y los colegas <a id="org-33"></a>

- **Dónde:** backend
- **Estado:** funciona; actúa con dos o más miembros activos
- **Qué hace para Gustavo:** los candidatos que nadie ha tocado se reparten solos: primero por afinidad (quien comentó su post,
  lo invitó, le escribió o se lo refirieron), luego por la preferencia de rol si la activa (`PEOPLE_ROLE_PREFERENCE`, por
  ejemplo `lider_tecnologia=CTO`) y el resto por un hash estable y parejo. Los perfiles del CTO y de Gustavo nunca son
  prospectos, y alguien que trabaja en ProjectApp nunca es comprador.
- **Código:** `registro.taker`, `may_take`, `gate`, `share_assigned`, `colleague_ids`, `remember_own`, `employee`;
  `ConnectorAccount.linkedin_ids`; `red.COLLEAGUE_RULE`, `red.EMPLOYEE_RULE`, `operador.check_account`.
- **Criterios de aceptación:**
  1. **Dado** 200 personas sin tocar, **cuando** se reparten, **entonces** quedan cerca de mitad y mitad y igual en cada corrida;
     la que invitó al CTO es suya; con la preferencia, un líder de tecnología va al CTO.
  2. **Dado** los planificadores de los dos, **cuando** corren, **entonces** cada uno va solo por las suyas y el CTO recibe la ficha
     básica de las que Gustavo descubrió para ella.
  3. **Dado** el perfil propio del CTO como contacto de Gustavo, **cuando** se clasifica o se propone, **entonces** no se paga ni
     se propone; un empleado de ProjectApp sale como no comprador.
- **Brechas código/docs:** la preferencia de rol está apagada hasta que Gustavo la confirme.
- **Cobertura QA:** `RepartoTests` (1–2), `RegistroTests.test_a_colleague_is_never_a_prospect_…` (3) · 2026-11-18 · pasa en local

