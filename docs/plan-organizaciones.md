# Plan de organizaciones: una segunda persona con su propia cuenta

Abierto el 17/11/2026 a pedido de Gustavo: que su CTO use Barrio AI con su propia cuenta de LinkedIn, «pero bien».
Mismos objetivos, criterios, servicios, biblioteca y estrategia; cambian su nombre, su identidad y su cuenta.
**Fases 1 a 7 construidas** (17 y 18/11/2026, rama `feat/organizaciones`, sin desplegar): ver «Fase N: lo construido».
El CTO no está dado de alta: lo que falta lo hacen personas (al final, «Para dar de alta al CTO»). Las fichas del catálogo siguen siendo la fuente de verdad de cada función
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
| 4 | Contenido por miembro (**hecha**) | Piezas, calendario y sus restricciones por día; plan semanal, resumen, revisión mensual y audiencia; memoria y hechos, preguntas, capturas y galería; orientación |
| 5 | Vistas y avisos por miembro (**hecha**) | Las rutas filtran por el miembro del usuario, con permiso por objeto; avisos y push solo a su dueño; preferencias y «visto» por usuario; Ajustes › LinkedIn y Máquina para varias cuentas |
| 6 | Registro compartido de personas (**hecha**) | Una ficha por persona en la organización; quien la atiende se la queda; no seguir, comentar ni invitar a quien atiende otro miembro; no comentar los dos el mismo post; excluir los perfiles de los colegas; referentes observados una vez |
| 7 | Alta del CTO (**hecha**: el camino; el alta real la hacen Gustavo y el CTO) | Su usuario, su OAuth y su sesión del navegador; su identidad; rampa de cuenta dormida (5 a 10 invitaciones al día e ir subiendo, LI-09-V006-K01); autonomía en «aprobación» al empezar; hora de publicación escalonada; guardas de memoria del servidor |

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

## Fase 4: lo construido

Hecho el 18/11/2026 en `feat/organizaciones` (fichas [ORG-18 a ORG-22](funcionalidades/organizaciones.md)). Cada miembro
tiene su contenido: su calendario y sus piezas, su plan semanal, su resumen, su revisión mensual, su audiencia, su memoria,
su orientación, sus preguntas, sus capturas y su galería. Con un solo miembro la API responde lo mismo que antes: 32 rutas
(calendario, piezas, plan, resumen, revisión, memoria y hechos, preguntas, orientación, galería, capturas, Tu turno,
Resultados, Actividad y Ajustes) comparadas byte a byte contra el código anterior, con el mismo reloj congelado y el mismo
`seed_qa`; la única diferencia es el id aleatorio de una imagen de la semilla, que también cambia entre dos corridas del
mismo código.

**De quién es cada cosa.**

| Qué | Dónde | Regla |
| --- | --- | --- |
| Piezas y calendario | `EditorialPiece.member`; restricciones `one_open_piece_per_member_day` y `one_second_piece_per_member_day` | una pieza del día y una segunda por miembro y día; `models._her_content` le pone el miembro de su cuenta |
| Hora del post | `editorial.post_time(member)`, `staggered_times`, `post_stagger` | la suya, escalonada (ver «Coordinación») |
| Huecos y pedidos de fecha | `urgente.assign_slots(now, member)`, `next_slot`, `next_extra`, `reserved_at`, `extra_at`, `free_slot`, `confirm_day`, `editorial.next_slot` | su calendario; el recálculo sin miembro recorre a cada uno (`each_member`) |
| Plan semanal | `WeeklyPlan.member` (`one_plan_per_member_week`); `estrategia.run`, `queue`, `regenerate`, `week`, `payload`, `calendar_days`; `estrategia_views.Week` | su plan, con la plantilla y los pilares de la organización |
| Resumen semanal | `WeeklySummary.member` (`one_summary_per_member_week`); `resumen_semanal.stats`, `queue`, `generate`, `for_director` | sus posts, su red, su audiencia y sus capturas |
| Revisión mensual y cambios de estrategia | `MonthlyReview.member` (`one_review_per_member_month`); `revision_mensual.stats`, `queue`, `generate`, `approve`, `revert` | lo aprobado va a su orientación |
| Audiencia | `AudienceSnapshot.member` (`one_audience_per_member_day`); `metricas.collect_audience`, `due` | la del lector de su cuenta, una por miembro y día |
| Memoria y hechos | `hechos.py`; `knowledge.memory.latest`/`confirmed_blocks(scope)`; `guardas.blocks(member)`, `guardas.text_checks(text, member)`; `identidad.facts`/`blocks(member)`; `knowledge.agents.context(memory_scope)` | ver «Hechos personales y de la empresa» |
| Orientación | `Orientation.member`; `orientacion.row`, `text`, `update(member)` | la fila 1 es la del primer miembro; otro miembro recibe la suya, vacía |
| Preguntas del equipo | `TeamQuestion.member` (`one_open_question_per_member_key`); `preguntas.ask`, `answer`, `undo`, `postpone`, `decline`, `facts`, `add_fact`, `correct`, `retire`, `sync_memory_proposals`; `projectapp.ask_case_questions`/`case_facts` | se pregunta al dueño de la pieza; solo ella responde (403 a otro miembro) y su respuesta es su memoria |
| Capturas e ideas | `Capture.member` (de quien la grabó); `capturas.ideas_for_director`, `feedback_for_director`, `answer_research_for_director`, `expire_ideas`; `capture_intent.jev` | su audio y sus notas alimentan solo sus piezas |
| Galería | `GalleryPhoto.member` (el de su captura, o quien la subió); `imagenes.candidates(ideas, member)`, `editor_visual.gallery(piece)`, `imagenes.prepare` | una foto suya nunca va en la pieza de otro |
| Perfil | `perfil.schedule` por miembro (`each_member`) | |
| Vistas que ya filtran | `rediseno_views.Questions`, `Facts`, `FactCorrect`, `FactRetire`, `OrientationView`, `Settings`, `Calendar` y, en `TuTurno`, sus preguntas, su memoria pendiente y su resumen; `capturas_views.Captures`, `Gallery`; `estrategia_views.Week`; `resumen_semanal.overview`/`revision_mensual.overview(member)`; la orientación de un resumen o una revisión es la de `summary.member`/`review.member` | las demás, en la fase 5 |
| Diagnóstico | `bucle_resultados.report(member)` y `manage.py bucle_resultados --miembro U` | sus resúmenes, audiencia, recomendaciones y plan |

**Trabajos periódicos.** Cada uno corre para cada miembro activo con `miembros.each_member(work, label)`: el fallo de uno se
registra (`<label>_failed member=<id>` en `team_backend.autopilot`) y no frena al siguiente; si fallan todos, el error llega
al informe del autopiloto como antes. El trabajo de un miembro lleva su id en el id determinista (`miembros.job_parts`) y
en sus parámetros (`job_params`); los del primer miembro conservan el id y los parámetros de antes, así que un trabajo
encolado antes del despliegue sigue siendo suyo (`miembros.of_job`). Lo hacen `autopiloto._editorial`,
`urgente.assign_slots`, `estrategia.queue`, `resumen_semanal.queue`, `revision_mensual.queue` y `perfil.schedule`.

**Lo que sigue siendo de la organización**, y por qué:
- la plantilla de la estrategia y sus pilares (`Organization.profile`): la empresa decide de qué habla; cada plan los usa;
- la biblioteca y el catálogo del curso: es conocimiento, se ingiere una vez y sirve a todos;
- el presupuesto de IA: un solo tope de la instalación (decisión del 13/11/2026: sin límite por usuario);
- los referentes y lo que aprende su análisis: se observan una vez para la organización (la fase 6 reparte a las personas);
- el embudo de oportunidades: uno solo, visible para los dos (decisión del 17/11/2026).

**Hechos personales y de la empresa.** La tabla `memory` no cambia de esquema: de quién es un hecho va en su clave. Las
claves de antes (sin prefijo) son del primer miembro, así que la memoria de Gustavo no se mueve; las de otro miembro
empiezan por `m:<uuid del miembro>:` y las de la empresa por `o:<uuid de la organización>:` (`knowledge.memory.in_scope`).
Todo lo que un miembro confirma (una respuesta, un dato de su captura, una nota, una corrección) es suyo. Que un hecho sea
de la empresa es un acto explícito del administrador activo: `manage.py operador --usuario <admin> hecho-empresa
--compartir CLAVE --miembro U` copia su valor vigente a la clave de la organización (auditado,
`memory.shared_with_organization`; idempotente) y `--retirar CLAVE [--motivo …]` lo retira con una lápida confirmada
(`memory.unshared_from_organization`); sin opciones lista los hechos de la empresa. Un hecho de la empresa llega a todos
los miembros y en el prompt se lee `empresa.<clave>`; si ella tiene la misma clave, gana la suya. Las guardas de fuga y de
experiencia inventada de un texto comparan con los hechos de su autora (`guardas.text_checks`) y sus razones dicen su
nombre.

**Migraciones.** `0059_contenido_por_miembro` (esquema): la columna `member` (nula) en piezas, planes, resúmenes,
revisiones, audiencia, preguntas, capturas y fotos, y `Orientation.member`; las restricciones únicas por día, semana, mes o
clave pasan a ser por miembro y día, semana, mes o clave, con `NULLS NOT DISTINCT` (sin miembros, una por día como antes).
`0060_contenido_del_primer_miembro` (datos): todo lo que no tiene miembro pasa a ser del primer miembro (el más antiguo); una
captura o una foto de alguien que es miembro pasa a ser suya, y una foto de una captura es del miembro de la captura; la
orientación de antes (fila 1) se marca suya. Sin miembros no hace nada; `miembros.ensure_first_member` aplica la misma regla
(`adopt_content`) cuando la base recibe su primer miembro después.
- *Efecto en producción:* unos `UPDATE` sobre las filas sin miembro de ocho tablas pequeñas (decenas a cientos de filas) y
  la fila 1 de la orientación, dentro de la transacción de la migración. La memoria, las cuentas y los trabajos no se tocan.
  Idempotente: corrida otra vez no encuentra nada que mover.
- *Revertir:* `manage.py migrate team_backend 0058`. El paso inverso de 0060 vacía `member` en las filas del primer miembro;
  el de 0059 quita las columnas y devuelve las restricciones de una por día o por semana, que solo caben mientras un único
  miembro tenga contenido: si el CTO ya tiene piezas, planes o resúmenes, hay que archivarlos antes de revertir.

**Coordinación sin llamadas de pago.**
- *Temas:* `estrategia.team_topics(monday, member)` lee lo que los otros miembros de su organización ya planearon esa semana
  y el pedido del plan lo lleva en `team_planned` (`{rule, topics}`) solo cuando no está vacío: el de Gustavo solo es el de
  antes. `estrategia._pick` descarta la opción que repite un tema de otro miembro (`same_topic`: la mitad o más de sus
  palabras con sentido en común, por código); si un día no queda otra, queda sin idea y el plan lo advierte.
- *Horas:* `editorial.staggered_times` recorre a los miembros activos de la organización del más antiguo al más nuevo; cada
  uno conserva su `EDITORIAL_POST_TIME` salvo que caiga a menos de `EDITORIAL_POST_STAGGER_MINUTES` (15 por defecto) de la
  de uno más antiguo, y entonces se corre en pasos de ese tamaño. El primer miembro nunca se mueve; una hora suya mal escrita
  falla solo su pasada.

**Voz provisional.** Mientras su voz es provisional (`voz.current(member).provisional`), `autopiloto.autonomy('CONT-09',
member)` devuelve «approval» aunque su ajuste diga «auto». Un post escrito con la voz provisional (la marca `voice` de su
propuesta o de su pieza; `operador.create_proposal` copia la de la pieza) nunca sale solo, ni siquiera después de que ella
confirme su voz: `autopiloto.provisional_draft` hace que `policy_review` lo deje esperando a una persona.

**`MiembroRequerido` que quedan.** Con dos miembros activos, el autopiloto (sus pasadas del domingo, del lunes y de la hora
del post) y los trabajos de contenido nunca piden «el» miembro: lo prueba
`ContenidoTests.test_the_autopilot_never_asks_whose_content_it_is_with_two_active_members`. Las vistas de contenido de esta
fase piden el miembro del usuario (`miembros.member_for`): preguntas, hechos, orientación, ajustes, calendario, capturas,
galería, semana del plan, resumen y revisión (con su «Generar ahora») y, en Tu turno, sus preguntas, su memoria pendiente,
su tarjeta de resumen y el aviso «Reconecta LinkedIn» de su conexión. Lo que queda sin decir de quién es de la fase 5 y no se detiene: lo lee entero, como antes. Son el
tablero de Resultados (`resultados.build`: posts, comentarios, red y audiencia de todos los miembros), las demás tarjetas
de Tu turno (aprobaciones, mensajes, fechas, cambios de estrategia, cuentas pausadas), los detalles por id (pieza, captura, foto, resumen),
que no comprueban dueño, y `GET /api/v1/memory` (la memoria cruda de la Oficina, con todas las claves tal como están
guardadas).

**Pruebas** (`test_organizaciones_e2e.py`): `ContenidoTests` con dos miembros activos (el post de cada uno el mismo día a su
hora, la voz provisional que no sale sola, hechos que no se cruzan y el de la empresa que llega a los dos, audio y fotos
solo para sus piezas, la pregunta a su dueña, planes con temas coordinados, resumen y revisión con su audiencia, el fallo
aislado, el plan por la API, el autopiloto sin `MiembroRequerido` y el diagnóstico por miembro); `ContenidoMigracionTests`
(datos como los de producción: sin duplicados, idempotente y reversible) y las clases `UnMiembro…` que vuelven a correr con
Gustavo las pruebas de siempre del plan, las preguntas, el calendario, las capturas, la galería, las ideas del director, el
resumen y la revisión.

### Lo que queda para las fases 5 a 7

- Fase 5 (**hecha**, ver «Fase 5: lo construido»): las vistas listadas arriba, los detalles por id con permiso por objeto,
  `GET /api/v1/memory` por miembro, los avisos y el push solo a su dueño.
- Fase 6: el registro compartido de personas.
- Fase 7: el alta del CTO (con su voz provisional y su CONT-09 en «aprobación»).

## Fase 5: lo construido

Hecho el 18/11/2026 en `feat/organizaciones` (fichas [ORG-23 a ORG-27](funcionalidades/organizaciones.md#org-23)).
Decisión de Gustavo del 17/11/2026: **cada miembro ve y maneja solo lo suyo**; ni el administrador ve las conversaciones,
los borradores ni las notas privadas de otro miembro. Con un solo miembro la API responde lo mismo que antes: **todas las
rutas de lectura** (249 lecturas: cada ruta GET sin id y cada ruta con id una vez por fila de la semilla) comparadas byte a
byte contra el código de la fase 4 (`350e01b`), con el reloj congelado y el mismo `seed_qa`. Las únicas diferencias son
cinco valores que también cambian entre dos corridas del mismo código (los `payload_hash`/`approved_hash` de las propuestas
y el sha del documento de una propuesta de perfil) y los ids aleatorios de la semilla.

**El mecanismo, en un solo lugar: `team_backend/alcance.py`.**
- `RUTAS` clasifica **cada** ruta de `team_backend.urls` y `RAIZ` las del proyecto: *del miembro*, *de la organización*,
  *solo del administrador* o *servicio* (con su porqué al lado). `RutaClasificada` (en `DEFAULT_PERMISSION_CLASSES`, después
  de `KnowledgeAccess`) rechaza con 403 una ruta que no esté en la tabla, pide el administrador activo en las de
  administrador y, en una ruta *del miembro* con id, comprueba **antes de la vista** que la fila que nombra el id sea suya
  (`OBJETOS`, armado de la tabla de prefijos `_IDS`): la de otro miembro responde **404, nunca 403**, diga lo que diga el
  cuerpo, y no cambia nada. `tests/test_alcance.py` falla si una ruta nueva no está clasificada, si una clasificada ya no
  existe o si una ruta del miembro con id no dice qué fila nombra.
- `DUENO` dice, para cada modelo de un miembro, el camino de una fila a su dueño: un miembro (`member`, `piece__member`…),
  una cuenta de LinkedIn (`account`, `contact__account`…) o un usuario (`owner`, `user`). Una fila sin dueño en ese camino
  (escrita antes de las organizaciones) es del primer miembro.
- Las vistas usan solo `alcance.de(filas, miembro)` (las suyas), `alcance.obtener(request, Modelo, **lookup)` (una suya o 404,
  también para un id mal formado) y `alcance.miembro(request)` (el miembro del usuario autenticado, explícito). Ningún
  ayudante convierte «sin miembro» en «el» miembro: `de(filas, None)` con miembros en la instalación es `MiembroRequerido`
  (400). `alcance.TODOS` lee a todos a propósito y solo lo usan lectores de la máquina (el autopiloto, Slack), nunca una
  pantalla. `alcance.trabajos(request)` son los trabajos que puede ver (los de su usuario, los de contenido de su miembro y los
  de sus cuentas; los de la máquina, sin miembro, siguen para quien tiene `manage_jobs`).
- Un usuario que no es miembro (una credencial de servicio, el robot del autopiloto) actúa por el único miembro activo,
  como antes; con varios activos recibe 400 en las rutas del miembro. Un token de dispositivo actúa como su usuario.

**Las rutas** (144 de la API y 3 del proyecto; la fase 6 suma tres: 147, con 117 del miembro y 4 + 1 del administrador):

| Clase | Rutas | Cuáles |
| --- | ---: | --- |
| Del miembro | 115 (117 desde la fase 6: liberar y pasar a una persona) | Las suyas: piezas, calendario, plan, resumen, revisión, memoria y hechos, preguntas, orientación, capturas, galería (fase 4) y, en esta fase, Tu turno entero, Notificaciones, Actividad, Resultados (su audiencia, su contenido, sus acciones, su analítica y su embudo del comprador), Personas (sus contactos y sus notas), sus conversaciones, respuestas y mensajes sugeridos, sus propuestas de acción, sus cuentas y sesiones de LinkedIn, su estudio de comunidad, sus propuestas de perfil, sus leads, reservas y respuestas del comprador, sus trabajos, su sesión, sus dispositivos y sus suscripciones push, `GET /api/v1/memory` y «quién soy» |
| De la organización | 18 | El embudo de oportunidades (2), los referentes y sus revisiones, análisis, cambios y experimentos (7), la biblioteca (`status`, `search`, `units`, `units/<id>`, `sources/<key>`), la parada total (`operador/control`), la escena de la oficina (`oficina/eventos`), el mapa del equipo (`equipo/grafo`) y la clave pública VAPID |
| Solo del administrador | 3 + 1 (4 + 1 desde la fase 6) | `integrity`, `audit`, `equipo/ciclos/<id>/decision`, la lectura de `app/errores` (informar un error, `POST`, es de cada uno) y, desde la fase 6, `red/contacts/<id>/reasignar` |
| Servicio | 7 | `auth/login`, `auth/token`, `linkedin/oauth/callback`, el webhook de Cal.com, la descarga con ticket de un perfil y las dos de la vista remota (`linkedin/pantalla/entrar`, `…/permitir`) |
| Proyecto (`RAIZ`) | 3 | `admin/` (administrador: el admin de Django es del superusuario del servidor y ve todo), `health` (servicio), la consola de la biblioteca (organización) |

**Lo que es de la organización, y por qué:** el embudo de oportunidades (decisión del 17/11/2026: uno solo, visible para
los dos; cada oportunidad dice quién la registró y de qué miembro vino), los referentes (se observan una vez para todos;
decide el dueño de la cuenta o el administrador, ORG-07), la biblioteca y el catálogo (conocimiento que se ingiere una vez),
el gasto de IA (un solo tope, sin límite por miembro, decisión del 13/11/2026) y la parada total (es de toda la máquina). La
escena de la oficina y el mapa del equipo son de todos porque solo llevan rol, destino y conteos, sin contenido ni ids.

**Oportunidades.** `Opportunity.member` (quien la registró) y `Opportunity.origin_member` (el dueño de la cuenta de su
persona; sin persona, quien la registró). Todos ven y mueven todas. Con varios miembros cada una trae `registered_by` y
`brought_by` (`{id, display_name}`); con uno, nada cambia. El nombre de la persona se ve en el embudo de todos (es de la
organización); su ficha (`contact`) solo la ve su dueña: para otro miembro llega `contact: null` hasta que la fase 6
comparta el registro. Un miembro solo puede vincular una persona suya («Persona inexistente» para la de otro) y, al editar
una oportunidad cuya persona es de otro miembro, lo que mande para la persona se ignora: mueve la etapa y el siguiente paso,
nunca la persona. El aviso de una oportunidad que avanza va a quien la trajo.

**Avisos por dueño.**
- `Notification.member`; `notificaciones.avisar(…, member=)` es obligatorio (sin valor por defecto). `member=ORGANIZACION`
  es el aviso de toda la organización (la parada total, el silencio del líder, las compuertas, un ciclo de la máquina): una
  fila por miembro activo, cada una con su estado de leído y sus preferencias. Con miembros, un aviso que no nombra a nadie se
  descarta con un `warning` (`notice_without_member`), nunca se adivina. Lo usan todos los avisos del backend, con
  `de_cuenta(account)`, `de_contenido(fila)`, `de_usuario(user)` o el miembro que ya tienen.
- El push web y el de Expo van solo a los dispositivos del usuario de su miembro (`alerts.notify(users=[…])`); un miembro
  inactivo guarda la fila y no recibe push. `OPERATOR_ALERT_WEBHOOK` es el canal del primer miembro (el de Gustavo): recibe
  los avisos suyos y los de la organización, nunca los de otro miembro.
- Preferencias por usuario (`OfficePreference.user`, `OfficePreference.of(user)`): la fila 1 (lo que Gustavo apagó o prendió y
  el retoque de su galería) es de su usuario, intacta; cualquier otra persona recibe la suya con los valores por defecto. El
  «Vista» de Tu turno (`InboxSeen`) es de cada uno: las del primer miembro conservan su id; las de otro llevan
  `u:<id de usuario>:` delante (`alcance.vista`).
- El `ref` de deduplicación del primer miembro es el de antes; el de otro lleva `@<id del miembro>` (salvo que ya lo nombre).
- **Slack: un solo canal.** Con más de un miembro activo, los avisos que nombran lo privado de un miembro (comentario sin
  responder, mensaje sugerido, conversación que espera, seguimiento que vence, comprador que respondió o se interesó, reunión
  agendada) llegan genéricos: «Barrio · {tipo}. El detalle está en Tu turno de quien corresponde; Slack no lo nombra.»
  (`alertas_slack.privado`). Con uno, el texto de siempre.
- **Con un solo miembro, Gustavo recibe exactamente lo que recibe hoy:** los mismos avisos, el mismo push (su usuario es el
  dueño de todos los dispositivos de hoy), sus preferencias (fila 1), sus «Vista», el mismo canal de Slack con el mismo texto.

**Las apps.** Ajustes › Sesión dice «Has entrado como Gustavo (Fundador) · ProjectApp.» con `GET /api/v1/yo` (sin miembro,
el usuario como antes); Ajustes › LinkedIn ya muestra solo sus cuentas (`operador/overview` es del miembro); Tu turno marca
«Voz provisional» en un borrador escrito con su voz provisional (`approval.provisional_voice`, `message.provisional_voice`);
el tablero de oportunidades dice «Trajo: …» con varios miembros y el formulario deja fija la persona de otro miembro. Las apps
no tenían textos con un nombre fijo (los que nombraban a Gustavo venían del backend: fase 3 y `comprador.signal_name`).

**`'gustavo'` en el cable: se queda.** `next_step.owner: "gustavo"`, `decided_by: "gustavo"` y los valores internos
(`confirmed_by_gustavo`, las opciones de `models.py`) siguen igual: los leen las apps instaladas (APK y PWA en caché) y cambiar el valor rompe a quien
no se actualizó. Como cada miembro solo ve sus contactos, sus propuestas y su Tu turno, `'gustavo'` significa siempre «tú»
y las apps nunca lo muestran como nombre (lo dicen los tipos de `compartido/src/api/types.ts`). Las etiquetas internas de
`models.py` no llegan a la pantalla de otro miembro; las que sí (las señales de un comprador) se dicen con su nombre
(`comprador.signal_name`). Renombrarlo, si se quiere, va con una versión nueva del contrato y de las apps.

**El inicio de sesión de otro miembro.** El administrador lo da de alta (`manage.py operador --usuario <admin> miembro
--nombre «Ana Pérez» --usuario-nuevo ana --rol CTO --grupo operacion --grupo revision`, inactivo hasta la fase 7) y le fija
la contraseña en el servidor (`manage.py changepassword ana`), que le entrega en persona o por un canal privado, nunca por
Slack ni en un archivo del repositorio. Los grupos `operacion` y `revision` bastan para trabajar su cuenta (operar LinkedIn,
aprobar y ejecutar sus acciones, confirmar su memoria, planear con proveedores de pago); no le dan `manage_jobs` ni la
administración. En la PWA entra con `POST /api/v1/auth/login` (sesión) y en la app con `POST /api/v1/auth/token` (un
`DeviceToken` de su usuario); los dos leen solo lo suyo. Activarla es de la fase 7 (`--activo`): mientras está inactiva, las
rutas del miembro le responden 400 «Tu miembro está inactivo en la organización.».

**Migración `0061_avisos_y_preferencias_por_miembro`.** `Notification.member`, `OfficePreference.user`, `InboxSeen.item_id`
hasta 200 caracteres, `Opportunity.member` y `Opportunity.origin_member`; los avisos de antes (7 días) pasan al primer
miembro, la fila 1 de preferencias a su usuario y cada oportunidad recibe el miembro de quien la creó (si no, el primero) y su
origen (el dueño de la cuenta de su persona). Sin miembros no hace nada.
- *Efecto en producción:* unas columnas en tablas pequeñas y unos `UPDATE` de decenas de filas, en la transacción de la
  migración. Idempotente.
- *Revertir:* `manage.py migrate team_backend 0060`: el paso inverso vacía lo que llenó, borra las preferencias que no son la
  fila 1 y quita las columnas.

**Pruebas.** `tests/test_alcance.py`: `RutasTests` (toda ruta clasificada, ninguna sobrante, los totales de esta tabla, toda
ruta del miembro con id dice qué fila nombra); con dos miembros activos y una fila de cada cosa por miembro (contacto,
conversación, pieza, imagen, comentario, post observado, propuesta, pregunta, captura, foto, resumen, revisión y su cambio,
recorrido y borrador del comprador, reserva, lead, propuesta de perfil y su archivo, sesión del navegador, fuente de
comunidad, trabajo, dispositivo, aviso y memoria), `DelMiembroTests` recorre **todas** las rutas del miembro: ninguna lista
trae el texto ni los ids del otro, el id del otro responde 404 en cada ruta y método sin cambiar nada, los suyos responden y
un id inexistente se ve igual; `FactsKeysTests`, `OrganizacionYAdministradorTests` (las de la organización responden igual a
los dos, el embudo y quién trajo cada oportunidad, editar la de otro sin tocar su persona, el 403 de administrador, la ruta
sin clasificar), `QuienSoyTests` y `AvisosTests` (su aviso solo a sus dispositivos y nunca al canal de Gustavo, el de la
organización a los dos con su estado de leído, preferencias y «Vista» de cada uno, el aviso sin dueño descartado, Slack
genérico con dos y el de siempre con uno). `test_organizaciones_e2e.RecorridoDelCtoTests`: el CTO entra con contraseña a la
PWA y con token a la app, ve quién es, conecta su LinkedIn, aprueba y publica su post con la marca de voz provisional, recibe
solo su aviso, no abre nada de Gustavo (404 en la oficina y en el teléfono) y el embudo dice quién trajo cada oportunidad.

**Revisión de seguridad de la fase** (lectura del código con un revisor independiente; arreglado con su prueba en
`CruzadosTests`): un id que llega en el cuerpo y no en la ruta no pasa por `OBJETOS`, así que cada uno se comprueba donde se
usa: la captura ligada a una persona, una pieza o una pregunta (`capturas.context_object(…, member)`: la de otro miembro
es «no existe», ni su nombre ni su nota llegan a él); el «Mensaje sugerido» de un comprador (`respuestas/<id>/mensaje`
acepta un comentario o un borrador del comprador: `OBJETOS` admite varios modelos por id); las notas de la oportunidad que
crea un lead con varios miembros dicen dónde está la conversación, no lo que dice (`entrega_lead.confirm`); `GET
/api/v1/audit` no muestra al administrador las acciones propias de otro miembro, y un id «u:…» en `tu-turno/vistos` nunca
marca la tarjeta de otra persona.

### Lo que queda para las fases 6 y 7

- Fase 6: el registro compartido de personas (hasta entonces, cada miembro ve solo sus contactos, y en el embudo solo el
  nombre de la persona de otro).
- Fase 7: el alta real del CTO (activarlo, su OAuth y su sesión del navegador).
- Riesgos conocidos:
  - El administrador (`manage_jobs`) ve metadatos de los trabajos y ciclos de la máquina de todos en el mapa del equipo y
    en las tarjetas de ciclo de Tu turno (ids, tipo, estado, motivo de parada; no el contenido); un administrador que no
    sea el primer miembro vería además los trabajos de contenido sin miembro en sus parámetros. Hoy el administrador es
    Gustavo, el primer miembro.
  - Los avisos de experimentos de referentes se guardan sin miembro: con varios, solo los ve el primero (son datos de la
    organización; decide el dueño de la cuenta o el administrador, ORG-07).
  - `OPERATOR_ALERT_WEBHOOK` debe ser un canal que solo lea Gustavo (un tema de ntfy suyo); si es un canal de Slack que
    lee el CTO, recibiría los avisos de Gustavo. Verificarlo en el `.env` del servidor antes de activar al CTO.
  - El admin de Django (`/admin/`) es del superusuario del servidor y ve todo: no se da a otro miembro.

## Fase 6: lo construido

Hecho el 18/11/2026 en `feat/organizaciones` (fichas [ORG-28 a ORG-33](funcionalidades/organizaciones.md#org-28)). Decisión
de Gustavo del 17/11/2026: «un modelo basado en organizaciones donde se comparta la base de datos, porque tenemos un mismo
objetivo», «cada una con su cuenta, y ya él maneje de su lado sus cosas»; un solo embudo; **quien toca primero a una persona
se la queda** y **nunca dos comentarios en el mismo post**. Todo vive en un módulo, `team_backend/registro.py`.

**Con un solo miembro activo nada cambia** (la instalación de hoy): el reparto, la regla por empresa, la lectura repartida de
referentes, la reutilización de clasificaciones, la regla de empleados y la liberación por plazo solo actúan con dos o más
miembros activos; una exclusión nunca frena al miembro cuya propia historia la causó (decide la regla de hoy), y Personas no
trae la clave `registro`. Comprobado contra el código del merge anterior a la fase (`feda285`) con el reloj congelado y el
mismo `seed_qa`: **todas las rutas de lectura** y las colas de los planificadores (ver «Pruebas»).

**Qué se comparte y qué no.** `Person` (migración `0062_registro_de_personas`): una ficha por persona de LinkedIn en la
organización, única por (`organization`, `provider_user_id`; el id del perfil de `directo`, igual para las cuentas de todos
desde el 14/11/2026). Guarda lo de la organización: nombre, titular, empresa (`sin_posts.company_of`), la parte de la
clasificación que es su criterio (encaje, papel, nivel y puntaje del comprador, confianza, motivo, `stage_check`), la etapa
general (candidata, seguida, invitada, conectada, descanso, descartada), una **exclusión para todos** (`rechazo_linkedin`,
`no_contactar`, `descarte`) con quién la causó, y **quién la atiende** desde cuándo y con qué toque. Cada `Contact` apunta a su
ficha (`Contact.person`) y guarda lo privado de su miembro: notas, historial, conversación, borradores, la nota de invitación y
la evidencia de la clasificación. Un receptor `post_save` de `Contact` mantiene la ficha (`registro.sync`, en un savepoint: un
fallo del espejo se registra y no frena el guardado). `PostClaim`: el único miembro que comenta un post de referente (único
por organización y post).

**«Quien la toca primero se la queda».** Toques: seguir (RED-01), invitar (RED-02), aceptar su invitación (RED-04), comentar
su post (INT-03 en un post que no es de referente) y responderle (INT-04). Clasificar no es tocar. `operador.execute`, dentro
del candado del miembro y antes de escribir, llama a `registro.claim`: toma la fila de la ficha `FOR UPDATE`; si nadie la
atiende, el miembro queda como dueño y las propuestas abiertas y borradores pendientes del otro para esa persona salen de sus
colas (descartadas, «La atiende <nombre>»; una fila que otra ejecución tiene tomada en ese momento se salta, sin esperar, y
esa ejecución ve al dueño en su propio `claim`). Si la atiende otro, la propuesta se descarta sin escribir nada
(`OperatorBlocked «La atiende <nombre>.»`, auditado `people.touch_refused`). Una ejecución que no escribió devuelve la ficha
(`registro.unclaim` en `_finish`). La misma comprobación (`registro.issue`) está en `operador.create_proposal` (409 por la
API), en `final_write_gate` y `red.execution_issues`, en los planificadores (`red.plan`, la verificación web de etapa, los
comentarios, los borradores del comprador) y antes de cada borrador pagado (`propose_comment`, la respuesta en su post, el
primer mensaje, los seguimientos y la respuesta del comprador).

**Por empresa** (`registro.company_issue`, LI-08-V006-K02 y LI-08-M004-K04), al abrir a alguien nuevo (seguir o invitar) entre
dos o más miembros: como mucho `PEOPLE_PER_COMPANY_MAX` (3) personas atendidas de una empresa entre todos, nunca dos del mismo
cargo (`sin_posts.cargo_of`), y donde otro miembro ya atiende a alguien de esa empresa no se abre a nadie nuevo sin un motivo
propio (la persona comentó su post, la invitó, le escribió, se la refirieron o es su puente). Un referido y un puente siguen
sus propias reglas (`sin_posts`, `COMPANY_MAX`).

**Liberar, pasar y reasignar** (`POST /api/v1/red/contacts/<id>/liberar|pasar|reasignar`): quien la atiende la libera o la
pasa a otro miembro activo, siempre con motivo y auditado (`people.released`, `people.passed`); el que la recibe empieza con la
ficha básica (`registro.card_for`: nombre, titular, perfil y la clasificación de la organización); notas, mensajes y
borradores se quedan con quien los tenía. El administrador reasigna solo a quien nadie ha tocado (`people.reassigned`; la
respuesta es la ficha de la organización, nunca el contacto de otro miembro). Una
persona en descanso o descartada sin exclusión para todos y sin actividad de su dueño durante `PEOPLE_RELEASE_AFTER_DAYS`
(180) queda libre (`registro.release_stale`, en `red.plan`). Descartar con `for_everyone: true` excluye para toda la
organización; solo quien la atiende, o cualquiera mientras nadie la atiende (si la atiende otro, 409:
`registro.exclusion_issue`, hallazgo de la pasada de seguridad de la fase).

**Colegas.** `ConnectorAccount.linkedin_ids` guarda el perfil propio de cada cuenta (lo lee `check_account` de `/me`); esos
perfiles nunca se clasifican (salen como no encaja sin llamada pagada, `red.COLLEAGUE_RULE`), nunca se proponen ni se
descubren. Con dos o más miembros, alguien cuyo titular nombra a la organización (`Organization.name`) nunca es comprador
(`red.EMPLOYEE_RULE`).

**Referentes de la organización.** La lista sigue en las cuentas de los miembros (la de Gustavo); con dos o más miembros
`referentes.to_read` reparte cada referente a **una** cuenta lectora de la organización (hash estable del referente) y
`referentes.share_posts` copia lo leído a las cuentas lectoras de los demás: cada post se lee una vez y cada miembro tiene su
fila para proponer. El primer miembro con una propuesta viva en un post de referente se lo queda (`registro.claim_post`); los
demás no lo proponen, no pagan su borrador y la API responde 409 «Este post ya lo comenta <nombre>.». La espera por autor
(`OPERATOR_AUTHOR_COOLDOWN_HOURS`) cuenta los comentarios de todos los miembros (`registro.peers`). Los comentaristas de un
post se leen una vez (`referentes.scanned_everywhere`) y entran al registro sin dueño. El análisis de la organización
(`analisis_referentes.report` sin cuenta) cuenta cada post una vez. Decide los cambios de referentes el dueño de la cuenta o
el administrador (ORG-07, sin cambio); los protegidos son de Gustavo.

**El reparto de candidatos sin dueño** (`registro.taker`, para que Gustavo lo confirme): (1) a quien el administrador se la
asignó; (2) afinidad: el miembro cuyo contacto llegó de su propio post, de una invitación, de una referencia o de una
conversación; (3) `PEOPLE_ROLE_PREFERENCE` (apagado; propuesta: `lider_tecnologia=CTO`, los líderes de tecnología de
ProjectApp al CTO y el resto por hash); (4) un hash estable de la persona entre los miembros que tienen cuenta lectora:
determinista y parejo (200 personas: cerca de mitad y mitad, igual en cada corrida). La clasificación se paga una vez: otro
miembro reutiliza la de la organización hecha con el mismo criterio (`red.shared_criterion`: instrucciones, umbral, curso y
ProjectApp, sin el nombre ni la orientación privada de nadie). Los cupos semanales por papel (`NETWORK_ROLE_SHARE`) y todos
los topes siguen siendo de cada miembro (fase 2). `red.plan` da a cada miembro la ficha básica de los candidatos que el reparto
le asigna (`registro.share_assigned`, hasta 20 por corrida).

**Pantallas.** Personas sigue mostrando solo los contactos del miembro (fase 5). Con dos o más miembros, `ContactOutput` trae
`registro` (`attended_by`, `mine`, `pass_to`, `excluded`) y, si la atiende otro, el siguiente paso dice «La atiende
<nombre>», sin nada privado del otro. La PWA y la app muestran esa línea, ocultan «Descartar» para la persona de otro y dan
«Liberar» y «Pasar a <nombre>» (con motivo obligatorio) a quien la atiende.

**Migración `0063_registro_inicial`** (datos, reversible e idempotente): todo lo de hoy es de Gustavo (el primer miembro). Cada
contacto recibe su ficha; Gustavo queda como dueño de quien ya tocó (el contacto pasó de «encaja»: seguido, invitado,
conectado o cerrado; o una escritura le llegó: seguir, invitar, aceptar, comentar su post o responderle), con toque «antes»;
los candidatos que nadie tocó quedan libres. Los rechazos `cannot_resend_yet` (`network.recipient_blocked`) y las salidas
«pidió no contacto» y «no le interesa» quedan como exclusión para todos, causada por Gustavo (para él sigue la regla de
hoy). Cada propuesta de comentario en un post de referente reclama su post. En producción son inserciones en tablas nuevas
(cientos de filas) y un `UPDATE` de `Contact.person`, en la transacción de la migración; nada de antes cambia. Sin miembros
no hace nada (`bootstrap_local` lo hace después con `registro.adopt`). La vuelta vacía `Contact.person` y borra fichas y
reclamos.

**Pruebas.** `test_organizaciones_e2e`: `RegistroTests` (clasificada una vez y no se descubre otra vez; el primer seguimiento
se la queda, la otra pierde su cola y no la toca ni por la API ni con un borrador; la regla por empresa; liberar, pasar y
reasignar sin mover nada privado; colegas y empleados; excluida para todos), `RegistroConcurrenciaTests` (dos ejecuciones a
la vez: una escribe, la otra no), `ReferentesDeLaOrganizacionTests` (cada referente leído por una cuenta, un comentario por
post, comentaristas una vez, la espera por autor de los dos), `RepartoTests` (estable, parejo, afinidad, preferencia de rol y
los planificadores), `RegistroMigracionTests` (0063 ida, otra vez y vuelta), `UnMiembroRegistroTests` y las suites de red y del
comprador corridas con un solo miembro (`UnMiembroDiscoveryAndFollowTests`, `UnMiembroInvitationTests`,
`UnMiembroVetoAndSafetyTests`, `UnMiembroTodayBuyerPathTests`). Identidad con un miembro: las lecturas de todas las rutas GET
y las colas de `red.plan`, `autopiloto._propose` y `autopiloto._observe` comparadas contra `feda285`.

En local (18/11/2026, en serie, PostgreSQL desechable; las pruebas de la fase con el reloj congelado):
`test_organizaciones_e2e`, `test_alcance` y `test_red`, 248 OK con el código final; otros 40 archivos que importan los
módulos tocados (en cinco lotes, el primero con `test_red` antes de los arreglos de seguridad), 824 OK (145, 155, 226, 189 y
109 por lote); vitest `Persona.test.tsx` 11 OK; jest `PersonaScreen.test.tsx` y `barrio.test.ts` 38 OK; `tsc` y `eslint` de
la PWA y la app; `check`, `makemigrations --check` y `mermaid.py --check`. Identidad con un miembro: 254 lecturas y colas
contra `feda285`; las únicas diferencias (el orden de dos eventos de auditoría con la misma hora, el `payload_hash` de una
pieza y el sha del documento del perfil) cambian igual entre dos corridas del mismo código. Doce mutaciones, todas detectadas
(una, pasar copiando la clasificación privada, después de reforzar la prueba). Sin correr en local: los otros 40 archivos de
`team_backend/tests`, el pytest de infraestructura y Maestro; la regresión completa queda para el CI.

### Lo que queda para la fase 7

Cerrado en la fase 7 (ver «Fase 7: lo construido»): el reclamo de un post de referente ya se libera cuando su propuesta muere,
y la reutilización de una clasificación ya no lleva la orientación privada de quien la pagó. Siguen abiertos:

- El alta real del CTO (activarlo, su OAuth y su sesión del navegador).
- Que Gustavo confirme el reparto (afinidad, luego hash) y si activa `PEOPLE_ROLE_PREFERENCE=lider_tecnologia=<usuario del CTO>`.
- Un flujo de Maestro con dos miembros («La atiende <nombre>», «Liberar», «Pasar a…»).
- Riesgos conocidos:
  - El reasignar del administrador nombra a la persona por un contacto de la organización; la API no lista aún las fichas
    sin contacto suyo.
  - Una persona cuya ficha se creó sin contacto (un comentarista de un post propio a quien se respondió) no entra al reparto
    hasta que alguien la descubre.
  - Entre miembros, un post de referente lo reclama quien primero tiene una propuesta (también una del agente que nadie
    aprobó todavía): con dos autopilotos, el de Gustavo suele llegar primero a los posts de sus referentes.

## Fase 7: lo construido

Hecho el 18/11/2026 en `feat/organizaciones` (fichas [ORG-34 a ORG-40](funcionalidades/organizaciones.md#org-34)). Deja listo
el camino para dar de alta al segundo miembro con seguridad; **no da de alta a nadie**: el CTO entra cuando Gustavo corre los
comandos y el CTO conecta lo suyo (guía para Gustavo: [alta de un miembro](alta-de-un-miembro.md); para el CTO:
[tu primera semana](tu-primera-semana.md)).

**Con un solo miembro activo nada cambia.** Gustavo nunca tiene voz provisional (es el primer miembro), así que la regla de la
voz provisional no le toca; las retenciones por miembro inactivo solo actúan sobre cuentas de un miembro inactivo; la marca
`provisional_voice` y la nota de Tu turno solo aparecen en borradores provisionales. Las 109 huellas de
`test_identidad_prompts.py` siguen iguales.

**Tres comandos, cada uno con ensayo** (`team_backend/alta.py`; nada cambia sin `--confirmar`):

```
operador --usuario gustavo alta-miembro --usuario-nuevo <usuario> --nombre "<Nombre>" --rol CTO \
    [--relacion "Es CTO de ProjectApp."] [--presentacion "…"] [--cuenta-directo <id>] [--confirmar]
operador --usuario gustavo activar-miembro --miembro <usuario> [--confirmar]
operador --usuario gustavo desactivar-miembro --miembro <usuario> --motivo "…" [--sin-acceso] [--confirmar]
```

1. `alta-miembro` crea su usuario (sin contraseña) y su miembro **inactivo**, con los grupos `operacion` y `revision`; le fija
   los ajustes prudentes (abajo) que no tenga ya (lo que el administrador fijó antes se deja); escribe su perfil mínimo (nombre
   y relación con la empresa) **mientras ella nunca haya guardado el suyo**; deja su voz provisional; opcionalmente registra su
   cuenta `directo` (nunca reasigna una de otro); y **propone** sin aplicar `PEOPLE_ROLE_PREFERENCE=lider_tecnologia=<usuario>`.
   Termina con la lista de lo que queda a mano ([x] hecho, [ ] pendiente, [?] verificar). Es idempotente y rechaza a un miembro
   activo. Nunca pone una contraseña, nunca conecta una credencial ni una sesión de LinkedIn y nunca la activa.
2. `activar-miembro` activa **solo si pasan todas** las comprobaciones, y dice cuáles fallan: `acceso` (usuario activo con
   contraseña), `cuenta_oficial` (su LinkedIn oficial con credencial vigente y sin pausa), `cuenta_directo` (su cuenta del
   navegador con sesión sana: se pregunta al servicio en el acto), `hora_post` (su hora a más de
   `EDITORIAL_POST_STAGGER_MINUTES` de la de los demás), `autonomia` (todo lo que escribe en «aprobación» mientras su voz es
   provisional), `rampa` (etapa 0, como mucho 10 invitaciones al día), `sin_miembro_requerido` (una pasada en seco con ella
   activa, deshecha al final: un tick del autopiloto, sus trabajos y cada ruta de miembro como cada miembro activo, con toda
   salida bloqueada; ninguna pide «el» miembro) y `memoria` (`MemAvailable` del servidor por encima de
   `MEMBER_ACTIVATION_MIN_FREE_MB`, 400 MB; se mira después de abrir su navegador).
3. `desactivar-miembro` la detiene: el autopiloto salta sus cuentas, `execute` y la última compuerta retienen lo suyo aprobado
   («El miembro dueño de esta cuenta está inactivo…»), su cola se cancela (`inactive_member`) y un trabajo suyo que llegue a
   correr se cancela solo. Sus datos quedan; nada de los demás cambia. `--sin-acceso` además apaga su usuario. Para volver:
   `alta-miembro` (devuelve el acceso) y `activar-miembro` con todas sus comprobaciones.

Mientras está en alta (inactiva) solo le responden su «quién soy», su perfil, su voz, Ajustes, su LinkedIn oficial (OAuth y
estado) y la conexión de su navegador (`alcance.DE_ALTA`); todo lo demás contesta «Tu miembro está inactivo».

**Ajustes prudentes de una cuenta gratuita dormida** (`alta.prudent`; curso LI-09-V006-K01 «arrancar con 5–10 invitaciones al
día e ir subiendo en 3–4 semanas» y LI-10-M001-K03 «la cuenta se calienta antes de la campaña, no durante»):

| Ajuste | Valor | Por qué |
| --- | --- | --- |
| `LINKEDIN_ACCOUNT_TIER` | `free` | Su cuenta es gratuita: límites de notas y búsquedas de una cuenta free |
| `OPERATOR_INVITE_RAMP_STAGES` | `5/25,8/40,10/50` | Rampa de cuenta dormida: 5 al día (25 a la semana), luego 8/40 y 10/50 |
| `OPERATOR_INVITE_RAMP_START` | `0` | Empieza en la etapa más baja; sube sola con aceptación sana |
| `OPERATOR_DAILY_LIMITS` | `INT-03=7,INT-04=5,RED-01=10` | Comentarios, respuestas y seguimientos a la mitad de los generales mientras la cuenta se calienta |
| `OPERATOR_PROFILE_READ_DAILY_LIMIT` | `40` | Las lecturas de perfil también se notan: la mitad |
| `OPERATOR_AUTONOMY` | todo en `approval` | Todo lo que escribe espera su aprobación mientras su voz es provisional |
| `EDITORIAL_POST_TIME` | la del primer miembro + 1 h (09:30) | Dos posts de la empresa nunca salen a la vez |

**La voz provisional nunca sale sola, en ninguna capacidad** (`autopiloto.PROVISIONAL_HOLDS`, `provisional_draft`,
`voice_hold`). Un texto escrito con su voz provisional (publicación CONT-09, comentario INT-03, respuesta INT-04, nota de una
invitación RED-02, también la que viene de un borrador del comprador) queda en «aprobación» aunque su capacidad esté en «auto»;
`operador.execute` y la última compuerta antes de escribir lo rechazan si no lo aprobó **ella** (la aprobación de la política o
la del administrador no cuentan). Tu turno lo muestra con «Voz provisional» (y la nota de la invitación); el detalle de la pieza
también. Los mensajes del comprador nunca los envía el sistema: no existe una capacidad que envíe mensajes. **Confirmar su voz
no cambia su autonomía** (decisión por defecto: no; la decide el administrador con `operador ajustes`), y lo que se escribió con
la voz provisional antes de confirmarla sigue esperando su aprobación.

**Pantallas** (PWA y app, Ajustes): «Mi perfil» (ver y editar nombre, rol, presentación, relación con la empresa, temas que no
domina y startups personales; validado, auditado, con historial), «Mi voz» (provisional, propuesta lista o confirmada vN; sus
señales contra `VOICE_LEARNING_MIN_TEXTS`; ver la propuesta y confirmarla o descartarla, solo ella) y, para el administrador,
«Organización» (el perfil de la empresa y sus miembros con su estado: activo, administrador, voz, cuentas; nada privado).
Rutas: `GET/PATCH yo/perfil`, `GET yo/voz`, `POST yo/voz/proponer`, `POST yo/voz/decidir`, `GET organizacion`
(clasificadas en `alcance.py`). Flujo Maestro `20-ajustes-perfil-voz.yaml`.

**Memoria del servidor** (`deploy/README.md` «Memoria del servidor»): topes por servicio en `compose.prod.yaml` (la base sin
tope, con 512 MB reservados y `oom_score_adj -500`; el navegador 2,25 GiB para dos cuentas y `oom_score_adj 300`); el
navegador no abre otro Chromium con menos de `NAVEGADOR_MEMORIA_MINIMA_MB` (1100) libres (503 `code: memoria`, «no salió»,
sin pausar la cuenta) y abre uno a la vez; `deploy/memoria.sh` por cron avisa en Slack de memoria baja, de un contenedor que el
kernel mató por memoria y de uno que Docker reinició solo; el cierre del navegador inactivo sigue apagado (no baja el pico y
cada reapertura es una carga que LinkedIn ve). Criterio de crecer: la tabla del README (OOM en la base, memoria baja tres días
de una semana, el navegador que no abre por memoria…); objetivo 8 GB y 2 vCPU. Los topes por servicio son estimaciones del
total medido el 13/11: hay que medir en el servidor.

**Cierres de las fases 5 y 6:**
- El reclamo de un post de referente se sostiene mientras su comentario salió (o pudo salir), o su miembro está activo y tiene
  una propuesta viva en él, o aún no tiene ninguna y no pasó `PEOPLE_POST_CLAIM_GRACE_MINUTES` (10). Muerta su propuesta
  (rechazada, descartada, caducada, fallida, sustituida sin otra) o inactivo su miembro, el post queda libre y el reclamo pasa,
  auditado (`people.post_claim_passed`), a quien lo comenta.
- La clasificación compartida solo se reutiliza entre miembros con el mismo contexto privado (su guía privada y su orientación,
  como huella): el criterio del clasificador lee la de quien paga. Con Gustavo (que tiene la guía de su brief) y el CTO, cada
  uno paga la suya. Los prompts no cambian.
- Los avisos de experimentos de referentes son del miembro de la cuenta; las notas del equipo en una pieza son solo las de su
  miembro; un administrador que no es el primer miembro no ve los trabajos de contenido del primero.
- `PEOPLE_ROLE_PREFERENCE` acepta el usuario del miembro (`lider_tecnologia=<usuario del CTO>`); sigue apagada.
- La lista de alta recuerda verificar que `OPERATOR_ALERT_WEBHOOK` sea un canal privado del primer miembro.

### Pruebas

`tests/test_organizaciones_e2e.py`: `AltaGuiadaTests`, `ActivacionTests`, `DesactivacionTests`, `PrimeraSemanaTests` (el
recorrido entero con funciones de producción, reloj congelado y conectores falsos, y el estado de Gustavo igual antes y
después), `VozProvisionalTests` (una prueba por capacidad), `AjustesDelMiembroTests`, `PendientesDeFase6Tests`;
`tests/test_memoria_servidor.py` (el script sin red). Números y lo que no se corrió: `tasks/active_context.md`.

## Servidor

Cada navegador abierto ocupa cerca de 1 GB; la máquina tiene 4 GB y 1 vCPU, y la documentación del conector dice que
dos cuentas «caben justas». Se intenta con el actual (decisión de Gustavo), con las guardas de la fase 7: límite de
memoria por servicio, el navegador que no abre sin memoria, alerta a Slack por memoria baja y por contenedores muertos y un
criterio escrito para ampliar ([deploy/README.md](../deploy/README.md#memoria-del-servidor)). El cierre del navegador
inactivo se revisó y queda apagado.
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

## Para dar de alta al CTO: lo que falta de personas

Nada de esto lo puede hacer el código. En orden ([guía paso a paso](alta-de-un-miembro.md)):

1. **Gustavo:** desplegar la rama (con un solo miembro no cambia nada) y poner el cron de `deploy/memoria.sh`.
2. **Gustavo:** verificar que `OPERATOR_ALERT_WEBHOOK` del `.env` del servidor es un canal privado suyo (recibe sus avisos y
   los de la organización, nunca los del CTO).
3. **Gustavo:** correr `alta-miembro` (ensayo y luego `--confirmar`), con `--cuenta-directo <id>` (el nombre de la carpeta de
   la cuenta en el servicio navegador).
4. **Gustavo:** `manage.py changepassword <usuario>` en el servidor y entregar la contraseña en persona o por un canal privado.
5. **El CTO:** entrar en la PWA o la app, conectar su LinkedIn oficial (Ajustes › LinkedIn) y abrir la sesión de su navegador
   (Ajustes › Máquina › «Conectar LinkedIn», con `LINKEDIN_CONEXION_APP=true`, o por SSH con él escribiendo su clave). Nadie
   más escribe su clave.
6. **El CTO:** completar «Mi perfil» (cómo se presenta y los temas que no domina); de él, su trayectoria en pocas líneas y fotos.
7. **Gustavo:** decidir el reparto de candidatos (`PEOPLE_ROLE_PREFERENCE=lider_tecnologia=<usuario>` o nada) y si el CTO
   publica desde el primer día (con voz provisional y aprobación) o empieza con red y comentarios.
8. **Gustavo:** `activar-miembro` (ensayo; si algo falla, lo dice) y luego `--confirmar`.
9. **El CTO, su primera semana:** aprobar o corregir lo que el equipo le propone, grabar audios y contestar preguntas; cuando
   haya muestra, pedir y confirmar su voz en «Mi voz».
10. **Gustavo, cuando quiera:** levantar la aprobación de alguna capacidad del CTO (`operador ajustes`); no es automático.
11. **Gustavo, la primera semana con dos navegadores:** medir `docker stats --no-stream` y `free -m` en el servidor y ajustar los
    topes si hace falta.
