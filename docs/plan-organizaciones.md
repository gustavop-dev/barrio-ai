# Plan de organizaciones: una segunda persona con su propia cuenta

Abierto el 17/11/2026 a pedido de Gustavo: que su CTO use Barrio AI con su propia cuenta de LinkedIn, «pero bien».
Mismos objetivos, criterios, servicios, biblioteca y estrategia; cambian su nombre, su identidad y su cuenta.
**Fase 1 construida** (17/11/2026, rama `feat/organizaciones`, sin desplegar): ver «Fase 1: lo construido». Las fases
2 a 7 no están construidas. Las fichas del catálogo siguen siendo la fuente de verdad de cada función
([ORG](funcionalidades/organizaciones.md) para esta).

## Decisiones de Gustavo

| Fecha | Decisión |
| --- | --- |
| 13/11/2026 | El CTO conecta su propio LinkedIn (API oficial y navegador). Mismo comprador y misma información. La identidad debe salir del código y vivir en un modelo. Sin límite de IA por usuario. Los usuarios por ahora son de su empresa; venderlo después «sería interesante». |
| 17/11/2026 | **Versión completa**, no la básica: el CTO también publica sus posts, con su calendario y su estrategia. |
| 17/11/2026 | **Modelo basado en organizaciones**: la base de datos se comparte porque el objetivo es el mismo. |
| 17/11/2026 | **Cada uno con su cuenta y su inicio de sesión**; cada uno maneja lo suyo. |
| 17/11/2026 | Se intenta con el servidor actual (1 vCPU, 4 GB). |
| 17/11/2026 | El CTO: rol «CTO», cuenta de LinkedIn gratuita. |
| 17/11/2026 | **Su voz se aprende de su uso**, no de textos previos: de los audios que grabe y de cómo responda y corrija lo que el equipo le propone. |
| 17/11/2026 | **Oportunidades: un solo embudo de la empresa**, visible para los dos. |
| 17/11/2026 | El outbound del comprador se mezcla primero (PR #135, apagado) y las organizaciones se construyen encima. |

## Diagnóstico (exploración del 17/11/2026, sobre `main`)

La base de datos ya admite varias cuentas y el servicio navegador ya maneja varias sesiones, pero la lógica trata
todas las cuentas como **un solo miembro de LinkedIn**: las dos que existen hoy son los dos conectores de Gustavo
(API oficial para publicar; navegador para todo lo demás). No existe el concepto de persona por encima de la cuenta.

Lo que se rompería al conectar hoy una segunda persona:

- Los posts de Gustavo podrían salir en el perfil del CTO (`editorial.publishing_account()` elige la cuenta oficial
  más nueva).
- Un solo post al día entre los dos y la mitad de ritmo para cada uno: topes, espaciado, rampa, notas y lecturas de
  perfil son globales (`operador.writes`, `spacing_ok`, `policy_lock`, `red.ramp_state`, eventos con `target='member'`).
- Una pausa o un 429 de una cuenta frena a la otra (`final_write_gate`, `execute`, `invites_blocked`).
- Cada uno vería la bandeja, las notas, las oportunidades y los avisos del otro: las vistas no filtran por usuario.
- **Seguridad:** cualquier usuario con `operate_linkedin` puede abrir la vista remota del navegador de cualquier cuenta
  (`conexion.start`), es decir, la sesión viva de LinkedIn de otra persona.
- Los textos del CTO sonarían a Gustavo: su identidad está en `posicionamiento.py`, en los prompts de sistema
  (constantes de módulo), en `voz.py`, en la memoria (`guardas.blocks`) y en unas 590 líneas de 68 archivos.
- Los dos irían sobre las mismas personas: solo la invitación está protegida entre cuentas (`red.invitation_reserved`).

## Modelo

**Organización** (ProjectApp): lo que se comparte porque el objetivo es el mismo.

- Biblioteca del curso, catálogo y metodologías.
- Servicios, comprador objetivo, criterios del barrio, pilares y plantilla de estrategia.
- Lista de referentes (se observan una sola vez para todos).
- **Registro de personas**: una sola ficha por persona de LinkedIn en toda la organización, con el miembro que la
  atiende. Evita que dos socios contacten a la misma persona o empresa (LI-08-V006-K02).
- Embudo de oportunidades de la empresa (uno solo, visible para todos los miembros).
- Presupuesto de IA (sin límite por miembro) y canales de Slack (cada aviso nombra al miembro).

**Miembro** (Gustavo, el CTO): lo que es de cada uno.

- Su usuario e inicio de sesión; sus dispositivos y avisos.
- Sus cuentas de LinkedIn (oficial y navegador) y su sesión; solo él puede abrirla.
- Su identidad: nombre, rol, trayectoria, límites («temas que no domina»), documento de voz, hechos confirmados
  (memoria), fotos y marca de perfil.
- Su contenido: posts, calendario, plan semanal, resumen, revisión mensual, audiencia y analítica.
- Sus acciones y su ritmo: comentarios, respuestas, seguir, invitar, borradores, Tu turno; topes, espaciado, rampa,
  notas, lecturas de perfil, tier de cuenta, autonomía, pausas.
- Sus conversaciones (mensajes privados): no las ve nadie más.

**Qué ve cada uno:** cada miembro ve y maneja lo suyo. Del registro compartido de personas ve la ficha básica y quién
la atiende; no ve las conversaciones ni los borradores de otro miembro. La parada total sigue siendo de toda la máquina.

Las oportunidades son un solo embudo de la empresa, visible para los dos; cada oportunidad dice qué miembro la trajo.

## Fases

Cada fase conserva el comportamiento actual para una organización con un solo miembro, entra con pruebas dirigidas en
local y la regresión completa en el CI de GitHub, y se despliega sin efecto hasta la fase 7.

| # | Fase | Qué incluye |
| --- | --- | --- |
| 1 | Organización y miembro (**hecha**) | Modelos `Organizacion` y `Miembro`; migración que crea ProjectApp y a Gustavo y le asigna sus dos cuentas; `ConnectorAccount.miembro`; los selectores de «la» cuenta pasan a ser por miembro (`publishing_account`, `reader_account`, `_own_posts_reader`, `analitica.account_for`, `perfil.read_profile`, `publications`); `require_gustavo` → dueño de la cuenta; **la vista remota del navegador solo para el dueño** |
| 2 | Un miembro de LinkedIn por persona (**hecha**) | Candado, espaciado, agenda del día, topes de escritura, lecturas de perfil, rampa, notas, tier, pausas, 429 y bloqueos: de globales a por miembro. Reescribir las pruebas que fijan «un solo miembro» |
| 3 | Identidad fuera del código (**hecha**) | `posicionamiento` repartido en perfil de organización y perfil de miembro; los prompts de sistema pasan a funciones que reciben al miembro; voz, autor de infografías y textos con «Gustavo» que llegan al usuario; formulario mínimo de identidad |
| 4 | Contenido por miembro | Piezas, calendario y sus restricciones por día; plan semanal, resumen, revisión mensual y audiencia; memoria y hechos, preguntas, capturas y galería; orientación |
| 5 | Vistas y avisos por miembro | Las rutas filtran por el miembro del usuario, con permiso por objeto; avisos y push solo a su dueño; preferencias y «visto» por usuario; Ajustes › LinkedIn y Máquina para varias cuentas |
| 6 | Registro compartido de personas | Una ficha por persona en la organización; quien la atiende se la queda; no seguir, comentar ni invitar a quien atiende otro miembro; no comentar los dos el mismo post; excluir los perfiles de los colegas; referentes observados una vez |
| 7 | Alta del CTO | Su usuario, su OAuth y su sesión del navegador; su identidad; rampa de cuenta dormida (5 a 10 invitaciones al día e ir subiendo, LI-09-V006-K01); autonomía en «aprobación» al empezar; hora de publicación escalonada; guardas de memoria del servidor |

## Fase 1: lo construido

Hecho el 17/11/2026 en `feat/organizaciones` (fichas [ORG-01 a ORG-09](funcionalidades/organizaciones.md)). Con un solo
miembro nada cambia; con ninguno (una base nueva o una prueba que no lo crea), todo funciona como antes.

**Modelos** (`models.py`, migración `0055_organizaciones`). Los nombres van en inglés, como el resto de los modelos:
- `Organization`: `name`, `slug` (único), `created_at`. Sin filas fijas: admite más de una organización.
- `Member`: `organization` (FK), `user` (OneToOne con el usuario de Django: una persona, un inicio de sesión),
  `display_name`, `role` (texto libre: «Fundador», «CTO»), `active`, `is_admin`, `created_at`.
- `ConnectorAccount.member` (FK opcional, `PROTECT`): de quién es cada cuenta.

**Migración.** Crea ProjectApp y su primer miembro, administrador y activo, con rol «Fundador». Su usuario es el de
`REFERENTS_GUSTAVO_USERNAME` (settings, si no el entorno, por defecto `gustavo`) si existe y está activo. Si no, es el
primer superusuario activo por fecha de alta, con contraseña usable y que no sea `barrio-autopiloto` ni `linkedin-service`.
Ese miembro adopta todas las cuentas sin miembro. Sin nadie así (la base del CI, la de QA antes de `seed_qa`) no crea
nada. Se revierte sin tocar las cuentas. `bootstrap_local`, que corre en cada arranque, aplica la misma regla
(`miembros.ensure_first_member`) si todavía no hay miembros. En producción, con `DJANGO_ADMIN_USERNAME=gustavo`, el
miembro será `gustavo` y sus dos cuentas (API oficial y `directo`) pasarán a ser suyas. Se verifica con
`manage.py operador --usuario gustavo miembros`.

**API interna** (`team_backend/miembros.py`):

| Función | Qué responde |
| --- | --- |
| `member_of_user(user)` | El miembro que es ese usuario (activo o no); `None` para robots, servicios y usuarios sin miembro. |
| `default_member()` | El único miembro activo. `None` si no hay miembros. `MiembroRequerido` si hay varios activos, o miembros pero ninguno activo. |
| `resolve(member=None)` | El miembro dado o `default_member()`. |
| `member_for(user)` | Para quién actúa un pedido: su propio miembro (inactivo: `MiembroRequerido`), si no `default_member()`. |
| `member_of_account(account)` | De quién es la cuenta: su miembro, o el único activo para una cuenta sin miembro; `None` si no se puede nombrar. |
| `member_for_account(account)` | Para el trabajo de una cuenta: `member_of_account`, si no `resolve()`. |
| `accounts(member=None, providers=None)` | Las cuentas del miembro (con las sin miembro mientras sea el único activo). `None`: todas. |
| `same_member(account)` | Todas las cuentas del dueño de esa cuenta (para las pausas). |
| `is_owner(user, account)` | Si es el miembro activo dueño de la cuenta. Sin miembros, el usuario de `REFERENTS_GUSTAVO_USERNAME`. |
| `is_admin(user, organization=None)`, `can_decide(user, account)` | Administrador activo; dueño o administrador de la organización de la cuenta. |
| `first_owner()`, `ensure_first_member(actor=None)` | La regla del primer miembro y su creación idempotente. |
| `save_member(admin, username, display_name, role='', *, make_admin=None, active=None, groups=())` | Alta o actualización idempotente; nunca crea cuentas de LinkedIn. |

`MiembroRequerido` es un `ValueError`: una vista responde 400 con el motivo y las guardas del autopiloto siguen con el
resto del ciclo.

**Comportamiento seguro con varios miembros.** Una cuenta sin miembro es del único miembro activo; con varios activos no
es de nadie. Una tarea o una ruta que no dice de quién es se detiene con `MiembroRequerido` en lugar de adivinar. Por eso
`operador miembro` da de alta a los miembros **inactivos** por defecto: hasta la fase 7, Gustavo sigue siendo el miembro
por defecto y nada se detiene.

**Selectores por miembro:** `editorial.publishing_account`, `respuestas.reader_account`/`publications`/`plan`/`due_pieces`,
`metricas.publications`/`due`, `operador._own_posts_reader`/`_find_own_post` (en `_publish` y `reconcile`),
`alertas_slack._reader`, `perfil.read_profile` (y `perfil.owner()` en lugar de exigir `PROFILE_OWNER_USERNAME`),
`analitica.account_for`/`overview` y `connectors_linkedin.status_payload`. Una cuenta nueva es de quien la registra
(`operador.register_account`, `connectors_linkedin.connect_member`).

**Permisos.** `referentes.require_gustavo(user, account)`/`is_gustavo`: el dueño de la cuenta o el administrador de su
organización. La sesión del navegador (`conexion.start`, `poll`, `new_link`, `cancel`, el canje del enlace y
`forward_auth`) y la credencial oficial (`connect_member`, motivo `dueno`) son **solo del dueño**, también frente al
administrador. `REFERENTS_GUSTAVO_USERNAME` y `PROFILE_OWNER_USERNAME` siguen valiendo, pero ya no hacen falta.

**Pausas.** `operador.execute` y `final_write_gate` miran solo las cuentas del mismo miembro (`same_member`). La parada
total (`OPERATOR_PAUSED`, `OperatorControl`) sigue siendo de toda la máquina.

**Comandos.** `manage.py operador --usuario <admin> miembro --nombre … --usuario-nuevo … [--rol …] [--activo] [--admin]
[--grupo …]` y `… miembros` (listado). `seed_qa --segundo-miembro` añade `qa-cto` con sus dos cuentas simuladas (apagado
por defecto).

**Pruebas.** `team_backend/tests/test_organizaciones_e2e.py` es el arnés de dos miembros que amplían las fases 2 a 7
(`DosMiembrosBase`, `Persona`, pasos `piece`, `publish`, `pause`, `oauth`, `plan_as`). Las clases `UnMiembro*` vuelven a
correr suites existentes con un solo miembro, sin tocar sus expectativas.

## Fase 2: lo construido

Hecho el 17/11/2026 en `feat/organizaciones` (fichas [ORG-10 a ORG-13](funcionalidades/organizaciones.md)). Cada miembro
es un miembro de LinkedIn con su propio ritmo; dos miembros no comparten ritmo y las cuentas de un mismo miembro sí.
Con un solo miembro (o ninguno) los números, los eventos y los avisos son los de antes.

**Su ritmo, por miembro** (`operador.py` y `red.py` salvo que se diga):

| Qué | Dónde |
| --- | --- |
| Candado | `operador.policy_lock(member)`: el primer miembro (y una instalación sin miembros) toma la fila de siempre, `OperatorControl` pk=1; cualquier otro, su fila `Member` (`FOR NO KEY UPDATE`). Lo toman `execute`, `final_write_gate`, `release_spacing`, `prepare_day_schedule`, `reserve_profile_read`, `red.review_health`/`provider_failure`/`reserve_note`/`send_invitation`/`_read`/`_signals_read`/`plan`, `calentamiento._reserve`, `experimentos.decide`/`tick`. |
| Espaciado y agenda del día | `reserve_spacing`, `release_spacing`, `spacing_ok` (su última escritura, no la de cualquiera), `prepare_day_schedule`, `post_due` (sus posts). |
| Topes diarios y semanales | `limits(now, member)`, `writes(account, capability, member)` (lo que escribieron todas sus cuentas), `capacity_left`; también `urgente.free_slot`, `calentamiento.rooms`, `reparto.weekly_invitations`, `oficina_views._capacity`, `alertas_slack.write_caps`, `red.summary`/`weekly_rhythm`. |
| Lecturas de perfil | `profile_read_cap(member)`, `profile_reads_used(member, now)`, `reserve_profile_read` (atómico bajo su candado; la línea base del día también es suya). |
| Rampa y su salud | `red.ramp_start`, `ramp_state`, `invitation_health` (sus invitaciones), `review_health`, `ramp_limits`, `health_snapshot`, `invites_blocked`. |
| Notas y tier | `red.note_policy(member)`, `note_blocked`, `note_room` (sus propuestas), `reserve_note`, `send_invitation`; `mensajes_comprador._notes`/`note_hold(contacts, now, member)`. |
| 429 y bloqueos del proveedor | `red.provider_failure`: baja y congela (o pausa) su rampa y pausa su cuenta; el `cannot_resend_yet` repetido cuenta destinatarios distintos rechazados **a ella** en 24 h. |
| Autonomía | `autopiloto.autonomy(capability, member)`, `autonomy_of(proposal)`; `respuestas.enabled(member)`. |
| Hora del post | `editorial.post_time(member)`, `scheduled_for(day, member)`. |

**Claves de auditoría.** El ritmo sigue viviendo en `AuditEvent` (`operator.schedule`, `operator.day_schedule`,
`operator.profile_baseline`/`profile_read`, `network.ramp`, `network.account_tier`, `network.note_capability`,
`network.notes_blocked`, `network.notes_reset_verified`, `network.provider_limit`). `miembros.policy_key(member)` da su
`target`: `'member'` para el **primer miembro** (el más antiguo por `created_at`, `pk`; Gustavo en producción) y para una
instalación sin miembros; `'member:<id>'` para cualquier otro.

**El estado de Gustavo se conserva sin migrar datos.** La migración `0056_ritmo_por_miembro` solo añade `Member.settings`
(vacío para todos). Sus eventos con `target='member'` siguen siendo suyos: su rampa, las notas del mes, la agenda de hoy y
las lecturas de perfil de hoy continúan donde estaban (lo fija `EstadoDeGustavoTests`). Si se revierte la migración o se
vuelve a desplegar el código anterior, todo lee las mismas filas. Mientras un despliegue convive con un worker viejo, los
dos toman el mismo candado (pk=1) para el ritmo de Gustavo.

**Ajustes por miembro** (`Member.settings`, con el nombre y el formato del `.env`; sin ajuste propio vale el del `.env` y,
sin él, el de siempre): `LINKEDIN_ACCOUNT_TIER` (free), `LINKEDIN_INVITE_NOTE_MONTHLY_LIMIT` (3), `OPERATOR_DAILY_LIMITS` y
`OPERATOR_WEEKLY_LIMITS` (por capacidad, encima de los del `.env`), `OPERATOR_INVITE_RAMP_STAGES` (8/40,16/80,20/100; solo
puede bajar cada etapa), `OPERATOR_INVITE_RAMP_START` (1; variable nueva, también en el `.env`), `OPERATOR_PROFILE_READ_DAILY_LIMIT`
(80), `OPERATOR_AUTONOMY` (por capacidad, encima de la del `.env`) y `EDITORIAL_POST_TIME` (08:30, dentro de
`OPERATOR_WINDOW`). Se ven y se cambian con `manage.py operador --usuario <admin> ajustes --miembro <usuario>
[--fijar VARIABLE=VALOR …] [--quitar VARIABLE …]` (solo el administrador activo de su organización; validado entero antes
de cambiar nada; auditado como `organization.member_settings` con el antes y el después; idempotente). Para la fase 7, el
CTO: `--fijar OPERATOR_INVITE_RAMP_STAGES=5/25,8/40,10/50 --fijar OPERATOR_INVITE_RAMP_START=0 --fijar
OPERATOR_AUTONOMY=INT-03=approval,INT-04=approval,RED-01=approval,RED-02=approval,RED-04=approval,CONT-09=approval`.

**Lo que sigue siendo de toda la organización, a propósito:** la parada total (`OPERATOR_PAUSED`, `OperatorControl`); el
presupuesto de IA (`AI_MONTHLY_LIMIT_USD`, fusible diario, `red.budget_left`/`spent_today`: Gustavo no quiere un tope por
miembro); los topes propios del servicio navegador (ya son por cuenta); «una persona, una invitación»
(`red.invitation_reserved`, `recipient_blocked`: nadie vuelve a invitar a quien LinkedIn rechazó). Los topes de lectura
de cada módulo (`REPLIES_READ_CAPS`, `NETWORK_READ_CAPS`…) ya eran por cuenta.

**Avisos de Slack.** Los vigilantes del ritmo de un miembro (`cupos_de_lectura`, `cupos_de_escritura`, `rampa_en_pausa`,
`aceptacion_baja`, `lecturas_detenidas`, `propuestas_por_caducar`, `post_del_dia`, `sin_comentarios`, `sin_invitaciones`)
son `@por_miembro`: corren para cada miembro activo; con uno solo emiten exactamente lo de antes; con varios, el texto
dice «Barrio · <nombre> · …» y la clave de un miembro que no es el primero lleva `:<id>`. `cuenta_en_pausa` nombra al
dueño con varios miembros. El resumen diario cuenta lo de toda la organización y los cupos de cada miembro. El fallo de
un miembro no silencia al otro.

**Autopiloto con varios miembros.** Cada cuenta trabaja con el ritmo de su dueño. Una cuenta sin miembro con varios
activos no es de nadie: el ciclo la salta (y sus propuestas), y lo cuenta en `report['unowned']`.

**Cambios de la API** (con un solo miembro, ninguno): `GET /api/v1/operador/overview` devuelve `capacity: null` para una
cuenta de nadie; `GET /api/v1/ajustes`, `GET /api/v1/notificaciones` y `GET /api/v1/red/summary` sin `account` responden
con el ritmo del miembro del usuario (y 400 `MiembroRequerido` si no se puede nombrar). Detalle en
[CONTRATO-API](../oficina/CONTRATO-API.md).

**Pruebas.** En `test_organizaciones_e2e.py`: `RitmoPorMiembroTests` (post del día con su tope, espaciado y agenda,
topes, lecturas de perfil, rampa del CTO baja y la de Gustavo la suya, salud, notas y tier, `cannot_resend_yet` repetido
y 429 solo de ella, una persona nunca invitada por los dos, el ciclo con una cuenta de nadie), `ConcurrenciaTests`
(dos reservas a la vez de un miembro no pasan el tope; el candado de uno no frena al otro), `AjustesTests`,
`EstadoDeGustavoTests` y `VigilantesTests` (todos los vigilantes sin miembros, con uno y con dos).

### Lo que sigue siendo de toda la instalación (para las fases 3 a 5)

Tareas que aún no dicen de quién son y que con varios miembros activos se detienen con `MiembroRequerido` (con un
miembro, o con el CTO inactivo, nada se detiene):
- Fase 4, contenido: `urgente.assign_slots` (y con él `editorial.plan`, `next_slot`, `next_extra`), `urgente._honor_legacy`
  y `confirm_day` (su `policy_lock()` sin miembro), `urgente.tick_day_requests`, `autopiloto._editorial` (su autonomía y
  `publishing_account()`), el plan semanal (`estrategia.queue`, línea 630), `editorial.next_slot` (`scheduled_for(day)`),
  el resumen semanal (`resumen_semanal.network`: `health_snapshot` y `weekly_rhythm` sin miembro).
- Fase 5, vistas: `perfil.schedule`/`owner()`; `rediseno_views.next_execution_time` estima con la última escritura de
  todos; las vistas aún no filtran por usuario (Tu turno lista las propuestas de todos los miembros, cada una con la
  autonomía de su dueño).
- Siguen globales también el hueco del día (`EditorialPiece.slot_date` único), la audiencia diaria de `metricas`,
  `perfil.facts` (piezas recientes) y la memoria (`guardas.blocks`).

## Fase 3: lo construido

Hecho el 17/11/2026 en `feat/organizaciones` (fichas [ORG-14 a ORG-17](funcionalidades/organizaciones.md)). La identidad
ya no está en el código: vive en la base, por organización y por miembro, y cada prompt se arma para el miembro dueño de
la cuenta. Para Gustavo todo es byte a byte lo de antes (lo prueban 109 hashes).

**Dónde vive la identidad.**

| Qué | Dónde | Qué guarda |
| --- | --- | --- |
| Perfil de la organización | `Organization.profile` (JSON) | versión, fecha y estado del posicionamiento, idioma, pilares, a quién no se busca, ubicación, servicios, oferta, casos, modalidades (propósito y barrio) y el barrio de antes del comprador de ProjectApp |
| Perfil del miembro | `Member.profile` (JSON) | nombre, identidad, relación con la empresa, límites, si le aplica la modalidad de startups personales, sus propósitos propios, versión de la marca de su perfil |
| Historial | `IdentityRevision` | cada cambio: quién, cuándo, antes, después, qué campos, origen (`migracion`, `semilla`, `comando`); más un `AuditEvent` `organization.identity_saved` |
| Su voz | `VoiceDocument` | versiones numeradas: `confirmada`, `propuesta` o `descartada`; texto propio o puntero a `recursos/` con su sha256; las señales que la originaron |
| Señales de estilo | `VoiceSignal` | referencias (modelo e id, nunca copias) a lo que aprobó, editó, rechazó, respondió o capturó |
| Semilla | `recursos/identidad-inicial.json` | los textos exactos de antes (ProjectApp, Gustavo y su voz); la migración `0058_identidad_inicial` lleva una copia congelada (una prueba fija que son iguales) |

Migraciones: `0057_identidad` (esquema: los dos JSON, los tres modelos y `voice` en `EditorialPiece`, `ActionProposal` y
`BuyerDraft`) y `0058_identidad_inicial` (datos: al primer miembro y a su organización les pone la semilla si están vacíos,
con la revisión 1 de cada uno, y su `VoiceDocument` 1 confirmado apuntando a `tono-de-voz.md`; reversible).
`miembros.ensure_first_member` hace lo mismo (`identidad.seed_first`) para una base que recibe su primer miembro después.

**Reglas de `identidad.of(member)`** (`identidad.py`): el primer miembro de la instalación (o ninguno) con perfil vacío
lee la semilla; cualquier otro, valores neutros más su `display_name` hasta que llene su perfil. `{nombre}` es su nombre,
`{alias}` su ficha de claves (`laura_gomez`) y `{decisor}` su nombre si es el primer miembro o «la organización» si no.
Con varios miembros activos y ninguno dado, `MiembroRequerido`: nunca se elige uno. Al leer un perfil guardado se
respeta el orden de claves de la semilla (jsonb no lo guarda y los criterios listan pilares y modalidades en ese orden).

**Prompts convertidos** (plantillas con `{nombre}`, `{alias}`, `{decisor}`; se renderizan con el miembro de la cuenta):
`posicionamiento` (todas sus funciones reciben al miembro), `editorial.stage_system`/`stage_schema`/`direction`,
`operador.comment_system`, `respuestas.reply_system`, `red.classify_system`/`stage_system`/`no_fit_rule`/`criterion_version`,
`lider` (criterios, comprobaciones, preguntas y estados del líder), `mensajes_comprador.system_for`,
`secuencia_comprador.system`, `respuesta_comprador.system_for`/`_question`, `projectapp.size_rule`/`case_issues`,
`estrategia.plan_system`/`type_rules`, `capturas.route_system`/`event_details`, `resumen_semanal.system`,
`revision_mensual.system`, `referentes_industria` (`for_account`), `referentes_research.system`, `editor_visual.system`,
`imagenes.design_system`, `connectors_images.photo_check`, `perfil_contenido`, `perfil_marca.brand_version`,
`comunidad` (analista), `research`/`capture_intent` (guías), `conversaciones.lines`, `infografias.author`/`render` y
`infografias.rule`/`with_rule` (los ejemplos de la regla de infografías firman con su nombre; la versión de la regla es
la del documento, igual para todos). `research.safe_question` descarta una pregunta web que nombre a cualquier miembro.
Las claves guardadas que llevan `gustavo` (`questions_for_gustavo`, `ideas_from_gustavo`, `ask_gustavo`…) no cambian en
la base: `identidad.keyed` se las muestra al modelo con la ficha del miembro y `unkeyed` devuelve su respuesta a los
nombres guardados.

**La voz** (`voz.py`): su `VoiceDocument` confirmado más reciente; sin él, la inicial si es el primer miembro; sin él, la
**provisional** (`recursos/voz-provisional.md` con la guía genérica `voz-guia.md`): neutra, sobria, sin rasgos de nadie. Cada
borrador guarda la voz con que se escribió (`voice`: `{"tipo": "provisional"}` o `{"tipo": "confirmada", "version": N}`).
Aprendizaje: `collect_signals` registra referencias; `propose` (apagado por defecto, `VOICE_LEARNING_ENABLED`; muestra
mínima `VOICE_LEARNING_MIN_TEXTS`=12 textos suyos aprobados o editados) hace una sola llamada de pago con su reserva
(Opus 5.5, `max_tokens` 6000: unos 13 000 tokens de entrada y hasta 6 000 de salida, cerca de 0,17 USD; el peor caso con 60
señales largas, unos 0,28 USD) y deja una **propuesta** que no se usa hasta que ella la confirma; confirmar crea la
versión vigente. Solo ella confirma o descarta; ella o el administrador piden la propuesta.

**Comandos** (`manage.py operador --usuario <usuario> …`): `perfil [--miembro U] [--fijar CAMPO=VALOR] [--quitar CAMPO]
[--historial]` (cambiarlo es solo de ella; verlo, de cualquiera), `perfil-organizacion [--fijar …] [--quitar …]
[--historial]` (solo el administrador), `voz [--miembro U] [--senales | --proponer | --confirmar N | --descartar N | --ver N]`.

**Textos que ve la persona.** Los mensajes del servidor que nombraban a Gustavo nombran al dueño de la cuenta
(`identidad.owner_name`: su nombre, o «el dueño de la cuenta» si no se puede nombrar): «Solo {nombre} puede reanudarla»,
«Decide {nombre}», «no se reinvita sin {nombre}», los retoques y el rescate de piezas, la entrega del lead, «{nombre}
conversa en este hilo». Para Gustavo dicen lo mismo que antes, salvo «Solo el dueño de la cuenta o el administrador decide
cambios de referentes y experimentos». En la PWA y la app: «Solo el dueño de la cuenta o el administrador.» (protección de
referentes), «Tu aporte» (decisión de referente) y «Aplicado por ti» (perfil). El dueño de un paso de la API
(`next_step.owner = 'gustavo'`) se queda como sinónimo de «tú»: lo leen la PWA y la app y cambiarlo rompería clientes
instalados; se renombra cuando la fase 5 filtre las vistas por miembro.

**Lo que no cambia para Gustavo** (`tests/test_identidad_prompts.py`): los 109 textos (prompts, esquemas, criterios,
preguntas del líder, voz, `posicionamiento` version/status, `criterion_version` y el PNG de la infografía) tienen el mismo
sha256 que en `origin/main`, después de la migración, con perfiles vacíos y sin miembros.

**Pruebas de dos miembros** (`test_organizaciones_e2e.py`): `IdentidadPorMiembroTests` (comentario, respuesta, primer
mensaje, clasificación y pieza editorial del CTO sin nada de Gustavo y con lo suyo; nombres dibujados;
`MiembroRequerido`), `VozTests` (provisional y su marca; muestra insuficiente; solo sus señales; la propuesta no se usa sin
confirmar; confirmada y versionada) y `PerfilComandoTests` (validación, auditoría, permisos).

### Lo que queda para las fases 4 a 7

- Fase 4: la memoria y los hechos (`identidad.facts`/`blocks`/`orientation` son el punto de enganche: hoy un miembro que
  no es el primero no tiene memoria ni orientación propias) y las guardas de `guardas.py`, que aún dicen «Gustavo» en sus
  razones.
- Siguen leyendo `identidad.of()` sin miembro (con varios activos se detienen con `MiembroRequerido`): el plan semanal
  (`estrategia.run`), el resumen y la revisión mensual, el pipeline de perfil (`perfil_*`), el enrutado de una captura sin
  autor y `evaluaciones` (el arnés de evaluación es el de Gustavo).
- Fase 7: el formulario del perfil en la app (hoy, por comando), exponer la marca «voz provisional» en la API y su CTO.

## Servidor

Cada navegador abierto ocupa cerca de 1 GB; la máquina tiene 4 GB y 1 vCPU, y la documentación del conector dice que
dos cuentas «caben justas». Se intenta con el actual (decisión de Gustavo), con estas guardas en la fase 7: límite de
memoria por servicio, cierre del navegador inactivo, alerta a Slack por memoria baja y un criterio escrito para
ampliar (si la base de datos o los workers se reinician por memoria, o si los chequeos de salud fallan a diario).
Las dos cuentas saldrían por la misma IP del servidor; el conector admite una salida propia por cuenta si hiciera falta.

## La voz de un miembro nuevo

El CTO no trae textos propios. Su voz se construye con lo que haga en la app (decisión del 17/11/2026):

- **Audios y notas** que grabe con el botón de captura: de ahí salen sus temas, sus expresiones y sus hechos
  (que él confirma antes de que cuenten como memoria).
- **Sus respuestas y correcciones:** cada vez que edita, aprueba, rechaza o reescribe un borrador, y lo que contesta a
  las preguntas del equipo, es una señal de estilo.
- **Arranque:** mientras no haya muestra suficiente, el equipo escribe con una voz neutra y sobria, marca cada
  borrador como «voz provisional» y le pide revisión (autonomía en «aprobación»). Con muestra suficiente (mínimos
  explícitos de textos suyos aceptados), se genera su documento de voz, que él revisa y confirma; después se
  actualiza con sus correcciones.
- Lo que nunca se hace: usar la voz, los hechos o las fotos de otro miembro.

Esto vive en la fase 3 (documento de voz por miembro, voz provisional y aprendizaje: ver «Fase 3: lo construido») y en la
fase 7 (su arranque con autonomía en «aprobación»).

## Orden respecto del outbound

Decidido el 17/11/2026: el outbound del comprador (PR #135) se mezcló primero, apagado, y las organizaciones se
construyen encima; así el recorrido del comprador nace ya por miembro. Los dos trabajos tocan los mismos archivos
centrales (`operador.py`, `red.py`, `autopiloto.py`, `lider.py`, `respuestas.py`).

## Lo que falta de Gustavo

1. Del CTO, antes de la fase 7: su trayectoria en pocas líneas, fotos y sus temas. La voz se aprende de su uso.
2. ¿El CTO publica desde el principio con voz provisional y aprobación, o empieza con red y comentarios?
