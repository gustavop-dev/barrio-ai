# Organizaciones y miembros (`ORG`)

Una segunda persona de la empresa (el CTO) usa Barrio AI con su propio usuario y sus propias cuentas de LinkedIn. Estas
son las fases 1 y 2 del [plan de organizaciones](../plan-organizaciones.md): el modelo, «de quién es» cada cuenta, los
selectores por miembro, las pausas por miembro y la sesión del navegador solo para su dueño (fase 1); y un ritmo de
LinkedIn propio para cada miembro (fase 2: candado, espaciado, topes, lecturas de perfil, rampa, notas, tier, bloqueos
del proveedor y sus ajustes). Con un solo miembro (la instalación de hoy) nada cambia. El alta real del CTO es la fase 7;
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
