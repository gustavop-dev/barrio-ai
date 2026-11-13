# Plan de outbound y red

Un solo lugar para todo lo de la red, los comentarios y el outbound: lo que Gustavo decidió, lo que ya funciona, lo que
falta y el orden propuesto. Abierto el 12/11/2026 a pedido suyo («reunir todo esto en un solo archivo para no tener todo
disperso»). Las fichas del catálogo (`docs/funcionalidades/`) siguen siendo la fuente de verdad de cada función; este plan
las enlaza y dice qué sigue. Cuando algo de aquí se construye, pasa a su ficha y aquí queda solo la referencia.

## Objetivo

Que LinkedIn posicione a Gustavo en EE. UU. y que su red se llene de personas que importan:

- **Compradores:** founders latinoamericanos con negocio en EE. UU., con ronda semilla o más, o con clientes que pagan
  (lo validan los agentes en la web, [BAR-17](funcionalidades/red.md#bar-17)). Fuera de EE. UU. no se invita a ningún
  comprador.
- **Comunidad:** no solo compradores. Mezcla del curso por semana: compradores 20 · recomendadores 15 · difusores 20 ·
  pares 25 (80 invitaciones) y líderes 10 solo con comentarios. Preferiblemente comunidad en EE. UU.; Latinoamérica
  sigue permitida, después.
- **Después de aceptar:** que la conexión se convierta en una conversación real y, si encaja, en una oportunidad.

## Decisiones de Gustavo (vigentes)

| Fecha | Decisión |
| --- | --- |
| 12/11/2026 | Los comentarios (INT-03) se abren a todos los roles del barrio, no solo a los 5 referentes. |
| 12/11/2026 | Calentar antes de invitar: seguir y comentar sus posts hasta invitar. Los compradores reciben el mayor calentamiento; los otros roles, menos. «Más caro y lento» no es razón para no hacerlo. |
| 12/11/2026 | Calentamiento: **2 comentarios en 7 a 14 días** antes de la invitación. |
| 12/11/2026 | Ronda semilla o más, validada por los agentes en la web. EE. UU. para todos («la idea es que LinkedIn nos mande a posicionarnos allá»). |
| 12/11/2026 | Umbral de seguidores: «lo veremos con la data». |
| 12/11/2026 | Rampa: al menos 15 invitaciones por día desde el inicio (quedó en 16/80 → 20/100). |
| 12/11/2026 | Notas en la invitación: sí; probarlas mientras se mejoran. |
| 12/11/2026 | Sus 5 referentes son muy locales de Colombia: llenar los cupos variables con voces orientadas a EE. UU. |
| 12/11/2026 | La clase 07 del curso (outbound) se puede consultar; el sistema completo de outbound viene después, con la información del curso que Gustavo trae. |
| 12/11/2026 | Café virtual semanal para reactivar contactos: pospuesto. |
| 12/11/2026 | **10 comentarios al día** (antes 5), y los comentarios son parte del outbound: calentar a los posibles compradores. |
| Vigente | La app nunca envía mensajes en nombre de Gustavo ([INB-08](funcionalidades/inbox.md#inb-08)). Un primer mensaje solo se redacta para que él lo copie y lo envíe ([RSP-07](funcionalidades/respuestas.md#rsp-07)). Catálogo CHAT-04: no escribir automáticamente por cada aceptación; interés real, sin pitch encubierto ni secuencias de campaña. |
| Vigente | En sus posts, el equipo responde solo, con el contexto del post, del hilo y del perfil; en el segundo turno puede proponer conectar y seguir por privado ([RSP-06](funcionalidades/respuestas.md#rsp-06)). |

## Lo que ya funciona

- **Red en EE. UU. ([BAR-17](funcionalidades/red.md#bar-17), PR #118, desplegado el 12/11/2026):** rampa 16/80 → 20/100,
  seguimientos 20/100, dos rondas de red al día, compradores solo en EE. UU. con la verificación de ronda semilla en la
  web, invitación a todos los roles salvo líderes (compradores de EE. UU. → comunidad de EE. UU. → Latinoamérica),
  descarte del líder con 30 días de descanso y «Sí, encaja» en la app, búsquedas en EE. UU. y en español, y la revisión
  extraordinaria de referentes (sus propuestas esperan la decisión de Gustavo en la Bandeja).
- **Comentarios ([comentarios-y-lider.md](funcionalidades/comentarios-y-lider.md)):** observar posts de referentes,
  prefiltro, borrador con la biblioteca (estante «comentar» activo), reglas fijas, idioma (español en un post en
  español) y revisión del líder antes de publicar.
- **Respuestas en sus posts ([respuestas.md](funcionalidades/respuestas.md)):** lectura, decisión, respuesta, segundo
  turno con invitación a conectar y «Mensaje sugerido» en la Bandeja.
- **Personas › Conexiones (PR #119):** la lista de quienes aceptaron, por etiqueta, como base de datos de personas.
- **Tope de comentarios en 10/día (12/11/2026):** en producción por `.env`: `OPERATOR_DAILY_LIMITS=INT-03=10` y
  `OPERATOR_WEEKLY_LIMITS=INT-03=50` (copia previa `.env.bak-20261112-comentarios-10`). Los fines de semana rige la
  mitad (5). El valor por defecto del código sigue en 5/25: se cambia en el PR de outbound.

## Diagnóstico (12/11/2026)

- **Los comentarios no llegan al tope por falta de posts donde comentar.** Últimos 7 días: 15 borradores, 6
  publicados, 9 descartados. Hoy solo se comenta en posts de referentes activos (4 publicaron esta semana), con una
  espera de 48 h por persona (`OPERATOR_AUTHOR_COOLDOWN_HOURS`): el máximo real ronda 2 comentarios al día. El tope de
  10 solo se alcanza comentando también en posts de compradores y de la comunidad, que es el calentamiento.
- **Hay un segundo tope:** `OPERATOR_DAILY_PROPOSALS=6` borradores pagados al día. Con 10 comentarios y un descarte
  cercano a la mitad hace falta subirlo (unos 14) cuando exista ese grupo de posts.
- **La decisión de abrir los comentarios a todos los roles no está construida:** el código pide `referent__active`.
- **Los 10 cupos variables de referentes están vacíos** hasta que Gustavo decida las propuestas de la revisión
  extraordinaria.
- **Después de aceptar no pasa nada:** el embudo termina en «conectado». El «Mensaje sugerido» existe solo para quien
  conversó con el equipo en un post de Gustavo.
- **No medimos el resultado:** sabemos cuánto se publica, comenta e invita, no si trae compradores, conversaciones o
  visitas al perfil.

## Diseño propuesto del outbound (por aprobar)

Un embudo por persona, con la red y los comentarios trabajando juntos:

1. **Detectar** (ya existe): búsqueda, clasificador, verificación de ronda semilla y revisión del líder.
2. **Seguir** (RED-01, ya existe).
3. **Calentar** (nuevo): leer sus posts recientes y comentar 2 veces en 7 a 14 días, con las mismas reglas de los
   comentarios (biblioteca, idioma, sin pitch, revisión del líder) y una persona a la vez cada 48 h.
4. **Invitar** (RED-02, ya existe) después del segundo comentario, o a los 14 días como máximo; con nota cuando lo
   permitan las notas reservadas ([BAR-16](funcionalidades/red.md#bar-16)).
5. **Al aceptar** (nuevo): aparece en Conexiones y, si es comprador o hay un motivo concreto, la Bandeja trae un primer
   mensaje redactado con el contexto (sus posts, los comentarios del equipo) para que Gustavo lo copie y lo envíe él,
   como RSP-07. Nada se envía solo.
6. **Conversación y oportunidad:** «Hecho, le escribí» registra el contacto; si avanza, pasa a Oportunidades
   ([PRS-07](funcionalidades/personas-oportunidades.md#prs-07)).

**Reparto de los 10 comentarios del día (propuesta):** 6 para calentar compradores, 2 para comunidad (pares,
recomendadores, difusores) y 2 para referentes y líderes, por visibilidad. Si un grupo no tiene posts ese día, sus
cupos pasan al siguiente.

**Costo:** pasar de 5 a 10 comentarios por día suma unos 15 USD al mes, más las lecturas de posts de compradores.
El gasto sin evaluaciones ronda 30 USD al mes: queda dentro del límite general de 100 USD.

**Medición semanal (nueva, en Resultados):**

- invitaciones enviadas y aceptadas, por rol y región;
- aceptación de los calentados frente a los no calentados;
- comprobaciones de ronda semilla: cuántos pasan;
- comentarios de calentamiento publicados y respuestas recibidas;
- conversaciones abiertas y oportunidades;
- gasto por comprador que aceptó.

## Decisiones abiertas (de Gustavo)

1. ¿El reparto 6 / 2 / 2 de los comentarios está bien?
2. Un comprador que no publica: ¿se invita sin calentar o se espera?
3. ¿Nota en la invitación a los calentados?
4. Primer mensaje: ¿solo a compradores o también a la comunidad? (siempre como borrador que él envía).
5. ¿Cuándo una conversación pasa a oportunidad?
6. La información de la clase 07 que falta.
7. Umbral de seguidores, cuando haya datos.

## Orden propuesto

1. **Hecho (12/11/2026):** 10 comentarios al día en producción.
2. **Hasta el 19/11/2026 aprox.:** observar los datos de BAR-17 (invitaciones, aceptación, cuántos pasan la
   verificación de semilla, dudas del líder) y decidir las propuestas de referentes en la Bandeja.
3. **PR chico, independiente:** infografías con más contenido.
4. **PR grande de outbound:** calentamiento, reparto de comentarios, primer mensaje en la Bandeja, medición semanal y
   los valores por defecto (INT-03 10/50, borradores por día).
5. **Después:** referentes por niveles (5 fijos, hasta 6 medianos rotativos, hasta 4 emergentes), umbral de
   seguidores, café virtual.

## Fichas relacionadas

[red.md](funcionalidades/red.md) (BAR-10 a BAR-17) · [comentarios-y-lider.md](funcionalidades/comentarios-y-lider.md) ·
[respuestas.md](funcionalidades/respuestas.md) · [inbox.md](funcionalidades/inbox.md) ·
[personas-oportunidades.md](funcionalidades/personas-oportunidades.md) · [backlog.md](backlog.md) ·
catálogo de acciones `agentes-linkedin/infra/docs/catalogo-acciones-linkedin.md` (CHAT-04 a CHAT-07).
