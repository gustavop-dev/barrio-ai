# Plan de organizaciones: una segunda persona con su propia cuenta

Abierto el 17/11/2026 a pedido de Gustavo: que su CTO use Barrio AI con su propia cuenta de LinkedIn, «pero bien».
Mismos objetivos, criterios, servicios, biblioteca y estrategia; cambian su nombre, su identidad y su cuenta.
Nada de esto está construido. Las fichas del catálogo siguen siendo la fuente de verdad de cada función.

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
| 1 | Organización y miembro | Modelos `Organizacion` y `Miembro`; migración que crea ProjectApp y a Gustavo y le asigna sus dos cuentas; `ConnectorAccount.miembro`; los selectores de «la» cuenta pasan a ser por miembro (`publishing_account`, `reader_account`, `_own_posts_reader`, `analitica.account_for`, `perfil.read_profile`, `publications`); `require_gustavo` → dueño de la cuenta; **la vista remota del navegador solo para el dueño** |
| 2 | Un miembro de LinkedIn por persona | Candado, espaciado, agenda del día, topes de escritura, lecturas de perfil, rampa, notas, tier, pausas, 429 y bloqueos: de globales a por miembro. Reescribir las pruebas que fijan «un solo miembro» |
| 3 | Identidad fuera del código | `posicionamiento` repartido en perfil de organización y perfil de miembro; los prompts de sistema pasan a funciones que reciben al miembro; voz, autor de infografías y textos con «Gustavo» que llegan al usuario; formulario mínimo de identidad |
| 4 | Contenido por miembro | Piezas, calendario y sus restricciones por día; plan semanal, resumen, revisión mensual y audiencia; memoria y hechos, preguntas, capturas y galería; orientación |
| 5 | Vistas y avisos por miembro | Las rutas filtran por el miembro del usuario, con permiso por objeto; avisos y push solo a su dueño; preferencias y «visto» por usuario; Ajustes › LinkedIn y Máquina para varias cuentas |
| 6 | Registro compartido de personas | Una ficha por persona en la organización; quien la atiende se la queda; no seguir, comentar ni invitar a quien atiende otro miembro; no comentar los dos el mismo post; excluir los perfiles de los colegas; referentes observados una vez |
| 7 | Alta del CTO | Su usuario, su OAuth y su sesión del navegador; su identidad; rampa de cuenta dormida (5 a 10 invitaciones al día e ir subiendo, LI-09-V006-K01); autonomía en «aprobación» al empezar; hora de publicación escalonada; guardas de memoria del servidor |

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

Esto vive en la fase 3 (documento de voz por miembro) y en la fase 7 (arranque en voz provisional).

## Orden respecto del outbound

Decidido el 17/11/2026: el outbound del comprador (PR #135) se mezcló primero, apagado, y las organizaciones se
construyen encima; así el recorrido del comprador nace ya por miembro. Los dos trabajos tocan los mismos archivos
centrales (`operador.py`, `red.py`, `autopiloto.py`, `lider.py`, `respuestas.py`).

## Lo que falta de Gustavo

1. Del CTO, antes de la fase 7: su trayectoria en pocas líneas, fotos y sus temas. La voz se aprende de su uso.
2. ¿El CTO publica desde el principio con voz provisional y aprobación, o empieza con red y comentarios?
