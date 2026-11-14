# Plan: estrategia semanal de contenido (GASP)

Diseño aprobado por Gustavo el 14/11/2026, abierto ese día a pedido de Gustavo: «empezamos a publicar sin estrategia… hablando de
cosas que se me ocurren pero sin una estructura definida». Antes el director decidía cada día por separado. Este plan
añade una capa encima: la semana se decide entera, con un tipo de post por día, y Gustavo la ve antes de que empiece.

**Estado (14/11/2026):** construido en la rama `feat/estrategia-gasp` (backend, app y pruebas), pendiente de CI y de
revisión. Lo que falta está en [Pendiente](#pendiente).

## La regla general: la audiencia primero

Gustavo, 14/11/2026: «todo se enfoque en la audiencia… no se trata de mí, se trata de la audiencia». Vale para los
cuatro tipos y para todo lo demás:

- **Cada día planeado y cada brief nombran qué necesita el lector** (`reader_need`) y **la señal de la audiencia que
  lo respalda** (`audience_evidence`): un post de un referente que superó su mediana, una pregunta en los
  comentarios de sus posts, algo que Gustavo contó de un comprador o los resultados por tipo. Una idea con señal pasa
  por delante de una sin ella.
- **La señal tiene que ser real:** solo cuenta si apunta a una de las señales que se le dieron al director
  (`estrategia.valid_evidence`). Si no la hay, el día queda «sin señal de la audiencia todavía» y el director la busca
  ese día. Si había señales y la pieza no usa ninguna, sale con el riesgo `no_reader_need`.
- **Lo personal también es para el lector:** las historias de P son de founders que el lector reconoce, no de
  Gustavo, salvo cuando él manda su propio material.

## De dónde sale

- **El marco, GASP,** es de Diandra Escobar (Distinctiva): **G**rowth, que te descubran · **A**uthority, generar
  confianza · **S**ales, convertir la atención en clientes · **P**ersonal, que conecten contigo. En su blog lo llama
  «embudo de cuatro cubos» o «Content Stack», y al tercero «conversión». Se consultaron el texto del reel que pegó
  Gustavo, cuatro artículos suyos (enlaces al final) y la transcripción del reel, de 32 segundos. En el reel dice:
  cada semana el calendario debe tener posts de los cuatro tipos; **crecimiento** es tomar como modelo un post
  viral de alguien de tu sector; **autoridad**, compartir tus marcos y tus casos; **venta**, tener recursos
  descargables para conseguir correos o llamadas agendadas; **personal**, mostrar un poco más de tu personalidad.
- **Las reglas de cada tipo** salen de la biblioteca del curso, que no da un calendario («no se prescribe un
  calendario editorial», LI-01-V008-K04) pero sí todo lo demás: pocos pilares y rotarlos para combinar humanidad,
  crecimiento y autoridad técnica (LI-04-V010-K01, K02), mezclar posts accesibles con posts de especialidad
  (LI-04-V007-K02), la tríada cliente · hechos · oferta en cada pieza (LI-04-M007-K02), evitar la venta disfrazada
  (LI-04-V004-K04), la regla del 1: un concepto, un problema, una solución, una llamada a la acción
  (LI-06-V022-K01), los enfoques (LI-05-M001) y una frecuencia que se pueda sostener (LI-06-V004-K03).
- **Lo que ya existe** en el sistema no se reemplaza: tres pilares, cuatro propósitos (modalidades), los enfoques,
  la mezcla de propósitos a 30 días y el resumen de lo que funcionó.

## Los cuatro tipos

| Tipo | Para qué | Cómo es el post | Formato que más le va | Cómo se mide |
| --- | --- | --- | --- | --- |
| **G · Crecimiento** | Que te descubra gente nueva del barrio en EE. UU. | Idea amplia y fácil de entender sobre tu territorio; una postura clara o una observación que cualquiera del sector puede comentar. Toma como modelo la estructura y el ángulo de un post de referente que superó su mediana, nunca su texto. Enfoques: debate, observación, lista. Sin tecnicismos y sin oferta | Infografía de un dato o una frase; carrusel de lista | Impresiones, miembros alcanzados, % fuera de tu red, seguidores obtenidos |
| **A · Autoridad** | Que confíen en que sabes hacerlo | Profundidad de especialidad: cómo se resuelve algo, por qué funcionó un caso, una decisión de arquitectura o de producto con sus consecuencias. Enfoques: paso a paso, análisis, contraposición | Carrusel de pasos; foto tuya trabajando con el caso | Comentarios con sustancia, guardados, envíos, visitas al perfil |
| **S · Venta** | Convertir la atención en conversaciones | Un problema concreto del comprador, cómo lo resuelves y **una sola** invitación a conversar (comentario o mensaje). Sin enlace, sin calendario, sin urgencia. Nunca disfrazado de consejo: se nota que es una oferta | Foto o tarjeta; texto corto | Visitas al perfil desde el post, conversaciones abiertas, oportunidades |
| **P · Personal** | Que conecten contigo | Lo humano detrás de construir empresas. **Sin material tuyo:** la historia pública de un founder o cofounder (startups o big tech) sobre el dolor de la semana (miedo a fracasar, agotamiento, conflicto entre cofundadores, despedir, quedarse sin dinero, un producto que nadie quería, una mala contratación), sacada de entrevistas, podcasts, charlas o blogs donde la cuenta él mismo, **atribuida a su protagonista y con su fuente**. **Con material tuyo** (foto, nota de voz o una idea personal), ese material manda y es la única fuente sobre tu vida | Foto tuya cuando hay; si no, texto | Reacciones, comentarios, invitaciones aceptadas esa semana |

La tríada cliente · hechos · oferta sigue valiendo para los cuatro. En G y P la oferta no se nombra, pero el tema
tiene que tocar tu territorio; un post personal ajeno a tu sector no entra.

### Las historias de P, con reglas estrictas

- **Solo el dolor sale a la web.** La pregunta de la búsqueda (`estrategia.story_question`) dice el dolor de la semana y
  nada sobre Gustavo, sus clientes ni su semana. Es una investigación web por post P, dentro de los topes diarios de
  la investigación que ya existe.
- **La historia es de quien la vivió:** se nombra al protagonista y se le atribuye; nunca se cuenta como vivencia de
  Gustavo.
- **Citas literales o ninguna:** una frase entre comillas tiene que estar tal cual en el extracto guardado de la
  fuente. Si la fuente está en otro idioma, se parafrasea sin comillas.
- **Sin fuente no hay historia:** si la búsqueda no trae una historia con fuente, el director escribe sobre ese dolor
  para el lector, sin anécdotas: nunca inventa una.
- **Una historia no se repite** en 12 semanas (`STRATEGY_STORY_REPEAT_WEEKS`).

## Proporciones

Ella sí da proporciones, y son las que se adoptan. En dos artículos: «más o menos 40 % crecimiento, 30 % autoridad,
20 % conversión, 10 % personal»; en otro, 35 · 35 · 20 · 10. Aclara que no son reglas rígidas: lo que importa es que,
mirando un mes, estén los cuatro. Publica entre tres y cinco veces por semana como mínimo.

Llevado a tus 7 posts por semana (28 en cuatro semanas), tal como está construido:

| Tipo | Su proporción | Posts por semana | En cuatro semanas |
| --- | --- | --- | --- |
| G · Crecimiento | 40 % | 3, y 2 una semana de cada dos | 10 (35,7 %) |
| A · Autoridad | 30 % | 2 | 8 (28,6 %) |
| S · Venta | 20 % | 1, y 2 una semana de cada dos | 6 (21,4 %) |
| P · Personal | 10 % | 1, todas las semanas | 4 (14,3 %) |

Cada tipo queda a menos de cinco puntos de su proporción. P va todas las semanas desde que sus historias pueden ser
públicas y de terceros: ya no depende de que Gustavo mande material. Quedarse en 40 % de G exigiría quitar P una
semana al mes (G 11 · A 8 · S 5 · P 4 también es posible): es una de las [decisiones abiertas](#decisiones-abiertas).

Dos condiciones suyas que cambian cómo se aplica:

- **La venta solo funciona si los otros cubos hicieron su trabajo:** «publicar conversión sin los otros dos es por
  lo que la mayoría de llamadas a la acción parecen anuncios». Coincide con el curso (venta disfrazada,
  LI-04-V004-K04). Por eso la venta va después de días de crecimiento y autoridad, nunca abriendo la semana.
- **Lo personal funciona cuando ya hay comunidad.** Tu red en EE. UU. es pequeña: P se queda en un post por semana.

Se revisan a las 4 semanas con la analítica nueva: ella misma dice «tus datos son la verdad». Resultados y el resumen
semanal ya muestran la interacción por tipo.

### Qué pone ella en cada cubo

| Tipo | Contenido, en sus palabras | Llamada a la acción |
| --- | --- | --- |
| G | Observaciones del sector, comentario de tendencias, reconocer patrones, opiniones fuertes, ángulos a contracorriente. Para cuentas sin audiencia: subirse a una noticia, a una marca o a un nombre conocido | Una pregunta que abra discusión. «Aquí no intentas convertir a nadie» |
| A | Marcos, sistemas, casos, resultados de clientes, experiencia profunda. Atrae a menos gente que el de crecimiento | «Escríbeme para la plantilla» o «comenta X para el marco completo» |
| S | Recursos descargables, ofertas directas, plantillas. Es «el contenido que trae mensajes privados» | Enlace del perfil o «escríbeme para trabajar juntos». Debe sentirse como «el paso natural siguiente, no un discurso de venta» |
| P | Tu historia, tu punto de vista, lo que hay detrás de lo que estás construyendo. No «lo que mi perro me enseñó sobre ventas B2B» | Normalmente ninguna: solo conexión |

Otras ideas suyas que encajan con lo que ya tenemos:

- **Elegir la intención antes de escribir:** decidir el cubo es el primer paso de cada post. Es justo lo que añade
  este plan al director.
- **Los comentarios cuentan más que los posts los primeros 90 días:** media hora diaria comentando en
  conversaciones que ya tienen audiencia. Es lo que hace el equipo con los comentarios en posts de referentes.
- **De dónde salen los temas:** «cada objeción es un post, cada pregunta de un posible cliente es un gancho»;
  grabar llamadas y reuniones. Tus notas de voz y capturas son ese material, y por eso cuentan como señal de la
  audiencia.
- **Probar en texto y escalar lo que funciona:** un post de texto que funciona se vuelve carrusel. Coincide con
  dejar el carrusel para autoridad.
- **Qué mirar:** guardados y envíos pesan más que reacciones y comentarios; un post de 5.000 impresiones puede traer
  más clientes que uno de 100.000. No da una métrica por cubo; las de la tabla de arriba son propuesta nuestra.

No da un calendario por días ni un orden dentro de la semana: eso lo proponemos aquí.

## Semana tipo

| Día | Tipo | Nota |
| --- | --- | --- |
| Lunes | G · Crecimiento | Abrir la semana con la pieza más amplia |
| Martes | A · Autoridad | |
| Miércoles | G · Crecimiento | |
| Jueves | A · Autoridad | El carrusel de la semana suele ir aquí |
| Viernes | S · Venta | Con dos días de crecimiento y dos de autoridad detrás |
| Sábado | P · Personal | Todas las semanas |
| Domingo | G · Crecimiento | Pieza ligera; una semana de cada dos pasa a S |

Es `STRATEGY_WEEK_TEMPLATE=G,A,G,A,S,P,G` y `STRATEGY_SALES_DOUBLE_EVERY=2`. El orden de los días es una suposición
razonable, no un dato: qué día rinde más cada tipo lo dirá la analítica.

Reglas de mezcla dentro de la semana:

- Están los cuatro tipos; S nunca abre la semana y no van dos S seguidos. Lo comprueba el código
  (`estrategia.mix_warnings`) y lo avisa en «La semana».
- Cada pilar aparece al menos una vez; ninguno más de tres.
- Ningún enfoque se repite en la semana si hay alternativa.
- Al menos un carrusel y al menos una foto tuya.
- La venta de cada semana apunta a un propósito distinto (startups, ProjectApp, alianzas), en rotación; la mezcla
  de propósitos a 30 días sigue orientando el resto. El dolor de P también rota cada semana.

## Cómo funciona

1. **La estructura es gratis y siempre está:** el código decide el tipo de cada día (`estrategia.allocate`), sin
   modelo. Una semana sin planear usa la estructura tal cual y el director decide cada día dentro de su tipo.
2. **El domingo por la tarde** (`STRATEGY_PLAN_TIME`, 16:00 de Bogotá) el director planea la semana siguiente en una
   llamada (`plan_week`): para cada día, la idea, qué necesita el lector, la señal de la audiencia, pilar, propósito,
   enfoque y formato, con el motivo. El código, no el modelo, mantiene los tipos, comprueba la mezcla y conserva lo
   que Gustavo cambió. Solo cuando los posts pueden salir (cuenta conectada, sin pausa, CONT-09 no apagado y con
   presupuesto del día), una vez por semana y con su propio tope (`STRATEGY_PLAN_LLM_USD`). Gustavo recibe un aviso con
   el plan.
3. **La ves en el Calendario** (Semana › «La semana»), y cada día lleva su letra en la tira y «Post de …» en su panel.
   Puedes cambiar el tipo de un día, cambiar dos días entre sí o descartar una idea; «Volver a planear» repite la
   llamada del domingo después de decirte lo que cuesta. Si no tocas nada, se sigue tal cual. Un día pasado o con su
   post ya preparado no cambia.
4. **Tus capturas mandan.** Una idea que claramente es de un tipo ocupa el día de ese tipo más cercano y la idea
   planeada ahí queda apartada para otro día («Ideas apartadas»). Una idea sin tipo claro va al primer día libre y se
   escribe como post del tipo de ese día.
5. **Una fecha pedida es una orden.** «Publica esto el martes a las 12» sale ese día a esa hora como un post extra,
   junto al diario, fuera de la estructura y de los topes de CONT-09; sin hora, a las 12:00 (`EDITORIAL_EXTRA_TIME`).
   Solo si la fecha no se puede cumplir (ya pasó, cae dentro del plazo de veto o fuera de la ventana, está a más de 14
   días, no se entiende o ese día ya tiene dos posts) la Bandeja pregunta en el momento: «Al primer día libre» o
   «Descartarla». Antes, la idea se iba al primer día libre y días después se preguntaba si salía en su fecha.
6. **Cada día,** el director prepara la pieza con el tipo como restricción: G con los modelos de referentes, S con
   el propósito de la semana y P con la historia investigada o tu material. El verificador revisa lo propio de cada
   tipo y el código lo comprueba en el texto final (ver [Comprobaciones](#comprobaciones-por-tipo)).
7. **Resultados y el resumen semanal** muestran la interacción media y las impresiones medianas por tipo; el resumen
   dice además qué respondió más la audiencia en cada tipo y qué señales movieron el plan de la semana siguiente.

### Comprobaciones por tipo

Son hallazgos con un código que entran en la ronda de reparación que ya existe. Cómo frena cada código una pieza lo
decide `gate_policy(piece)`, en otra rama (`feat/compuertas-auditoria-reintento`); aquí se propone su gravedad
(`estrategia.SEVERITY`).

| Código | Cuándo | Gravedad propuesta |
| --- | --- | --- |
| `unsourced_third_party_story` | La historia de P no está en una fuente guardada | Dura |
| `fabricated_quote` | Una cita entre comillas no aparece en las fuentes | Dura |
| `first_person_appropriation` | La historia no se atribuye a su protagonista o se cuenta como de Gustavo | Dura |
| `cta_count` | Más de una llamada a la acción en S, o alguna en P | Blanda |
| `offer_in_growth`, `offer_in_personal` | Ofrece servicios en G o en P | Blanda |
| `no_reader_need` | La pieza no nombra una señal que respalde lo que necesita el lector | Blanda, va como riesgo |
| `repeated_story` | La historia ya salió en las últimas 12 semanas | Blanda, va como riesgo |

Mientras `gate_policy` no llegue, un hallazgo blando del texto que la reparación no arregla sigue bloqueando, y la
única llamada a la acción de S sigue chocando con la regla actual contra la venta agresiva (`POST_PITCH`,
`aggressive_pitch`): hay un `TODO(gate_policy)` en ambos sitios.

## Qué se construyó

| Parte | Qué |
| --- | --- |
| Backend | `estrategia.py` (estructura, señales de la audiencia, plan del domingo, cambios de Gustavo, historias de P, hallazgos por tipo); modelo `WeeklyPlan` (migración `0039_plan_semanal`); API `GET /api/v1/estrategia/semana`, `PATCH …/dias/<fecha>`, `POST …/mover`, `POST …/planear`; el tipo en el brief y en el calendario; capturas clasificadas por tipo; la fecha pedida como post extra (`urgente.py`, `capture_intent.py`); resultados y resumen semanal por tipo; ciclo `plan_semanal` en `agentes-linkedin/equipos/grafo.yaml` |
| App | Calendario › Semana: «La semana» y su hoja de día, la letra del tipo en la tira y «Post de …» en el panel; Resultados › Contenido: «Interacción media por tipo de post»; la tarjeta de fecha de Tu turno con las dos respuestas nuevas |
| Costo | El plan del domingo, en Opus: unos 0,20 USD típicos y 0,47 USD como mucho (lo que se reserva). Cada post P sin material tuyo hace una investigación web, unos 0,06–0,11 USD más las búsquedas. En total, unos 0,35–0,50 USD por semana |

## Pendiente

- **CI:** nada de esto se ejecutó en local; las pruebas de backend, Jest y Maestro corren en CI.
- **`gate_policy`:** que los hallazgos blandos pasen a riesgo y que S pueda llevar su única llamada a la acción. Las
  pruebas de venta esperan con `skipUnless` a que exista.
- **La migración** `0039_plan_semanal` depende de `0035`: hay que renumerarla si entran antes otras migraciones.
- **Referentes de la industria:** `estrategia.growth_models` es la única entrada de los modelos de G; cuando esté su
  revisión se cambia `observed_outliers` sin tocar el resto.

## Decisiones de Gustavo (14/11/2026)

| Decisión | Qué implica |
| --- | --- |
| Empezar con 40 · 30 · 20 · 10 y construirlo | G 3, A 2, S 1 (2 en semanas alternas), P 1 por semana |
| El post de venta, por ahora sin enlace ni calendario | La llamada a la acción invita a conversar (comentario o mensaje). La meta es una llamada agendada, pero el recurso descargable con página de aterrizaje y formulario se planea aparte, dentro del outbound (`docs/plan-outbound.md`) |
| Lo personal no tiene restricción de tema | Puede hablarle directamente a los dolores personales de sus clientes |
| Lo personal se nutre de historias públicas de founders | «No importa que no sean míos, lo importante es hablar de ellos»: miedos y fracasos de founders y cofounders de startups y big tech, buscados en internet (blogs, podcasts), atribuidos y con fuente. Su material, cuando lo hay, manda. Ya no hay tarjeta pidiendo material ni P que pase a Autoridad |
| Todo se enfoca en la audiencia | «No se trata de mí, se trata de la audiencia»: cada día y cada pieza dicen qué necesita el lector y qué señal lo respalda |
| El post diario de las 8 a. m. sigue siempre la estructura | La constancia del post diario no se rompe |
| Un post pedido con fecha y hora se obedece tal cual | «Publica esto el martes a las 12» sale ese día a esa hora, aunque ese día ya tenga el post diario: ese día lleva dos. No se manda a otra semana ni se pregunta después en la Bandeja |
| Una idea sin fecha se adapta | Va al primer día libre y se escribe según el tipo GASP que le toca a ese día |
| «Copiar» es el centro del crecimiento | Hacen falta referentes de verdad: grandes, de nuestra industria, que vendan los mismos servicios y tengan autoridad. Lo que les funciona se toma como modelo (estructura y ángulo, nunca el texto) |

## Decisiones abiertas

1. Qué recurso descargable se ofrecerá cuando llegue esa parte, y la página a la que lleva.
2. Quiénes son los referentes de la industria: el equipo los propone con el criterio de arriba y Gustavo decide.
3. P todas las semanas (G 10 · A 8 · S 6 · P 4) o 40 % exacto de G (G 11 · A 8 · S 5 · P 4).
4. Un post pedido a la misma hora que el diario: hoy salen los dos ese día; falta decidir si se separan las horas.

## Fuentes de GASP

Artículos de Diandra Escobar en el blog de Distinctiva: «The Entire LinkedIn System that made me $1M by 25», «The
best LinkedIn content strategy in 2026», «How to build a LinkedIn Content Engine that drives pipeline» y «Stole the
Best LinkedIn Content Strategy». El análisis de CaptureFlow sobre sus posts se leyó como referencia de terceros y no
se tomó ninguna cifra de ahí.

## Relacionado

`docs/plan-outbound.md` (el barrio y los compradores a los que apunta el contenido) ·
`docs/funcionalidades/` (calendario, resultados e imágenes) · `docs/plan-linkedin-directo.md` (la analítica con la
que se medirá).
