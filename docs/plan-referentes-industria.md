# Plan: referentes de industria y modelos de crecimiento

Abierto el 14/11/2026 a pedido de Gustavo: «necesito que en verdad tengamos referentes de nuestra industria que vendan
los mismos servicios que nosotros pero grandes… para que lo que les funcione a ellos lo copiemos». Las fichas
[OBS-05](funcionalidades/observatorio-referentes.md#obs-05) y [OBS-06](funcionalidades/observatorio-referentes.md#obs-06)
son la fuente de verdad de cada función; este plan explica los criterios, sus umbrales y lo que queda abierto.

## Decisiones de Gustavo (vigentes)

| Fecha | Decisión |
| --- | --- |
| 14/11/2026 | Los cinco referentes main son demasiado locales de Colombia; las diez plazas variables se orientan a voces de EE. UU. |
| 14/11/2026 | Referentes **de industria**: grandes, que venden lo mismo que él (software a la medida, producto/MVP, IA aplicada, liderazgo técnico). |
| 14/11/2026 | El equipo **propone** con criterios verificables y **él decide**. Nada entra por silencio. |
| 14/11/2026 | «Copiar» es copiar estructura y ángulo de lo que les funciona. **Nunca su texto.** |
| 14/11/2026 | «Todo se enfoca en la audiencia… no se trata de mí, se trata de la audiencia»: se mide si su audiencia es la de Gustavo y qué pregunta esa audiencia. |
| 17/11/2026 | La primera búsqueda no propuso a nadie (ver [primera corrida](#primera-corrida)). Gustavo puede dar empresas o perfiles semilla, y si la búsqueda del mes terminó sin propuestas se puede repetir. |
| 17/11/2026 | «Analizar sus posts, qué les funciona y qué no, cómo lo hacen, qué estructura usan; descomponer sus temas y su estructura». Con cifras (el post, la mediana del autor, cuántas veces), por partes, y separando lo **duradero** de lo **pasajero** (ver [qué les funciona y qué no](#analisis)). |
| 17/11/2026 | Los referentes de industria que añadió a mano entraron como «nicho»: `operador referente --industria` y `operador referente-tipo` (ver [tipo](#tipo)). |
| 18/11/2026 | Del análisis al post: el **molde** de un post de referente que superó con claridad la mediana de su autor (etiquetas, rango de longitud, ángulo, fuente con enlace y estado). La variante A se escribe sobre él y la B queda libre; se usa ya como hipótesis, cada autor aporta sus mejores posts frente a su propia norma, con tope por autor, y se mide con molde frente a sin molde. Detrás de `REFERENTES_MOLDE`, apagado por defecto (ver [el molde](#molde)). |

## Qué es un referente de industria

`Referent.kind = industria` (los de siempre son `nicho`). Ocupa una plaza variable como cualquier referente: el equipo
observa sus posts, descubre personas en sus comentarios y el autopiloto puede comentar en ellos. Lo distinto:

- Entra solo con la decisión explícita de Gustavo (tarjeta «Alta de industria: …», 14 días para decidir). No se aplica
  al cierre del día 5 ni por ningún vencimiento; los recordatorios del día 4 son solo del lote mensual.
- Sus posts atípicos se convierten en **modelos de crecimiento** para la estrategia semanal ([OBS-06](funcionalidades/observatorio-referentes.md#obs-06)).

### El tipo importa <a id="tipo"></a>

`kind` decide tres cosas: los atípicos de un referente de industria son modelos de crecimiento para la estrategia y el
editorial (`modelos_crecimiento.growth_models` y `audience_questions`, con `kinds=('industria',)`); de sus atípicos nuevos
se leen los comentarios (`after_observe`); y su primera observación lee 20 posts para tener base (`read_limit`). Uno de
«nicho» solo alimenta el respaldo `estrategia.observed_outliers` mientras no haya modelos de industria.

- Alta: `python manage.py operador --usuario <u> referente --cuenta <id> --perfil <url> --motivo "…" --industria`. Sin la
  opción sigue entrando como nicho; si ya existía, conserva su tipo y el comando lo dice.
- Corrección: `python manage.py operador --usuario <u> referente-tipo --cuenta <id> --perfil <url> --tipo industria --motivo "…"`
  solo muestra el cambio; con `--confirmar` lo aplica. Sube la revisión del referente, deja `referents.changed` con
  antes y después (visible en su historial) y **no** toca la revisión de la lista: las revisiones mensuales pendientes
  no entran en conflicto. Un main sigue necesitando a Gustavo.

## Criterios (regla `industria-v1`)

Cada candidato llega con los seis criterios, su estado (Cumple · No cumple · Sin medir) y el dato que lo sustenta.
**«Sin medir» nunca cuenta como cumplido.** Los umbrales son variables de entorno para recalibrarlos sin desplegar código.

| Criterio | Regla por defecto | Variable | Por qué |
| --- | --- | --- | --- |
| Vende lo mismo que Gustavo | Vende al menos uno de los cuatro servicios de `posicionamiento.SERVICES`; lo dice una fuente citada que lo nombra (o su propio perfil) con las palabras del servicio | — | Una afirmación del modelo no basta: el código busca el término en la cita. |
| Es grande | ≥ 10.000 seguidores **y** mediana ≥ 50 interacciones en ≥ 5 posts propios ya asentados (48 h) | `REFERENTES_INDUSTRIA_MIN_SEGUIDORES`, `…_MIN_MEDIANA`, `…_MIN_MUESTRA` | 10k es donde una voz deja de ser un par; la mediana prueba una audiencia que responde hoy, no seguidores heredados. |
| Autoridad verificable | ≥ 2 pruebas verificadas de ≥ 2 tipos: clientes, casos, equipo, trayectoria, charlas | `…_MIN_AUTORIDAD` | Separa a quien tiene una práctica real de quien solo comenta. Cada prueba se verifica contra su fuente. |
| Publica seguido | ≥ 4 posts propios en 30 días y el último hace ≤ 14 días | `…_MIN_POSTS_30D`, `…_MAX_DIAS_SIN_POST` | Una voz de la que se aprende cada semana. |
| Vende en EE. UU. | Perfil ubicado en EE. UU. o una fuente citada que lo nombra dice que vende allí | — | La red de Gustavo crece en EE. UU. |
| Su audiencia es el barrio | De los comentaristas de su mejor post, ≥ 5 ya clasificados por el equipo y ≥ 30 % con encaje | `…_MIN_CLASIFICADOS`, `…_MIN_ENCAJE`, `…_AUDIENCIA_OBLIGATORIA` | El principio de Gustavo. Un «no cumple» medido descarta; «sin medir» se muestra tal cual y, por defecto, no bloquea (si fuera obligatorio, casi nadie nuevo pasaría al inicio porque pocos comentaristas están clasificados). |

El 30 % es un punto de partida prudente, no una medida: en esta tarea no se midió la proporción real de encaje entre
los comentaristas de sus referentes actuales. Recalibrar cuando exista ([preguntas abiertas](#preguntas-abiertas)).

Otros límites: como máximo 3 altas por búsqueda (`REFERENTES_INDUSTRIA_MAX_ALTAS`). Nunca se propone a quien ya es o
fue referente, a quien Gustavo rechazó (se guarda su nota) ni, durante 90 días (`REFERENTES_INDUSTRIA_RECORDAR_DIAS`), a
quien falló un criterio **medido**. Quien quedó «sin medir» vuelve a medirse la próxima vez.

## Primera corrida (17/11/2026) <a id="primera-corrida"></a>

Pool de 24 personas, 6 perfiles medidos, 4 pasaron tamaño y actividad y los 4 cayeron en «vende lo mismo que Gustavo»
(consultora de go-to-market, captación de clientes en LinkedIn, coach ejecutivo, líder de una startup de IA para
compras). El descarte fue correcto; el origen no:

- Las búsquedas eran las palabras sueltas de cada servicio (`custom software development`, `product development`,
  `applied ai`, `fractional cto`), en EE. UU., una por servicio. LinkedIn trae a quien escribe sobre eso, no a quien lo vende.
- La página de búsqueda del conector directo no trae nombre, titular, lugar ni seguidores, y solo trae el identificador
  público de los primeros ~3 de 10 (`linkedin_directo.lectura.search_results`). El código descartaba las filas sin
  identificador y ordenaba el resto por seguidores = 0: quedaban **detrás de todos los contactos conocidos con ≥ 10.000
  seguidores**, y los 6 perfiles leídos fueron, casi seguro, esos contactos grandes del barrio (ventas, crecimiento,
  coaching). El conector simulado sí devolvía titular y seguidores, por eso las pruebas no lo vieron.
- «Una búsqueda no devolvió resultados utilizables» venía de la **investigación web** (`research.native_findings`), no
  de LinkedIn. El dossier ahora lo marca como «Investigación web: …».
- La guarda permitía una búsqueda al mes: el intento vacío quemó el mes.

## De dónde salen los candidatos

Solo de lecturas de LinkedIn de la cuenta conectada (conector directo), nunca de la web. En este orden:

0. **Perfiles semilla** (`--perfiles`, hasta 5): se miden primero y con los mismos criterios; el prefiltro no los
   descarta (los pidió Gustavo), pero tamaño, actividad, servicios, autoridad y EE. UU. sí. Uno que ya es o fue
   referente se omite; un rechazo o descarte anterior no lo bloquea (su pedido explícito es posterior).
1. **Empresas semilla** (`--empresas`, hasta 5): una búsqueda `"<empresa>" founder` sin filtro de lugar por empresa.
2. **Búsquedas de quien vende el servicio** (`referentes_industria.QUERIES`, en orden fijo; `--busquedas` toma las
   primeras N, 5 por defecto): cargo + servicio entre comillas, con `OR` y paréntesis como en el buscador de LinkedIn.
   Las de EE. UU. usan `NETWORK_SEARCH_LOCATION`; las de nearshore buscan sin filtro de lugar.
3. **Contactos ya conocidos** con ≥ 10.000 seguidores.

**Prefiltro gratis** (`prefilter`, reglas, sin llamadas pagadas) sobre el texto que ya se tiene (titular de un contacto
o de un resultado): fuera quien vende otra cosa (coach, go-to-market, marca personal, ventas/captación, reclutamiento y
staffing, marketing, LinkedIn como servicio, inversión, ya no dirige la empresa, formación o medios, liderazgo
genérico, ejecutivo de gran empresa) si nada nombra uno de los servicios; y fuera quien está fuera de EE. UU. si su
titular no dice que vende allí (no aplica a una empresa semilla). Primero quien nombra un servicio y lo dirige
(founder, CEO, CTO, partner…). Una palabra de servicio pesa más que una de ventas.

Luego, por persona y en ese orden: una lectura de perfil; **el prefiltro otra vez** con el titular, el extracto y el
lugar del perfil; si tiene menos de 10.000 seguidores, cae en «tamaño» **sin leer sus posts**; solo quien pasa lee sus
últimos 20 posts (contadores y fechas) y los comentarios de su mejor post. Se detiene al medir `--candidatos` personas o
al gastar `2 × candidatos + perfiles semilla` lecturas de perfil. Una fila sin identificador público ya no se pierde: se
lee por su id y se excluye también por id. Leer un perfil registra una visita.

Del perfil se conserva, como fuente fechada del dossier, la línea pública: nombre, titular, ubicación y extracto de hasta
1.500 caracteres. No se guardan nombres de quienes comentan.

Solo los que pasan los criterios medibles (tamaño, actividad y audiencia no medida como ajena) van a la investigación
web, que busca pruebas de servicios, autoridad y mercado EE. UU. La pregunta web lleva el nombre público del candidato,
sin URLs. La selección final solo puede proponer candidatos de la lista, y el código verifica cada afirmación contra la
fuente citada antes de publicar la tarjeta.

**Dossier por candidato** (`dossier.industria`): `descartados` dice para cada uno el paso en que cayó (`prefiltro`,
`tamano`, `actividad`, `servicios`, `autoridad`, `mercado_eeuu`, `audiencia`), por qué, cómo se encontró y qué lecturas
costó (ninguna · perfil · perfil y posts); `evaluated` lleva `step` (o `propuesto` / `no_elegido`); `sin_medir` quién
quedó fuera por cupo; `busquedas` cada búsqueda con resultados, cuántos con identificador y cuántos nuevos; `embudo` y
`diagnostico` el resumen en una línea. `operador referentes-industria --cuenta <id> --informe` lo imprime sin leer nada.
«Sin medir» en audiencia nunca es el paso de un descarte.

## Cómo se lanza y cuánto cuesta

Solo a mano, nunca automático:

```
python manage.py operador --usuario <u> referentes-industria --cuenta <id> [--candidatos 6] [--busquedas 5] [--tope-usd 3] \
    [--empresas "Imagine Apps,Northwind Labs"] [--perfiles https://www.linkedin.com/in/<slug>/,<slug>] [--confirmar]
python manage.py operador --usuario <u> referentes-industria --cuenta <id> --informe   # embudo del mes, sin encolar
```

Sin `--confirmar` imprime el peor caso, las búsquedas que hará y las semillas, y no encola nada. Con los valores por
defecto:

| Concepto | Peor caso |
| --- | --- |
| Lecturas de LinkedIn | 6 búsquedas (5 + 1 de ubicación, una vez) + 1 por empresa semilla; 12 perfiles + 1 por perfil semilla; 12 de contenido (gratis; cuentan en los topes diarios de `red.READ_CAPS`) |
| Investigaciones web | 2 llamadas × 0,82 USD de reserva |
| Selección | 0,27 USD de reserva |
| **Total reservado** | **1,91 USD** (2,73 USD con 9 candidatos y 3 llamadas). Las semillas y el prefiltro no cambian el USD. |

Lo real suele ser menos: la reserva cuenta cada vuelta de herramienta como si repitiera toda la entrada. El tope duro
(`--tope-usd`, por defecto `REFERENTES_INDUSTRIA_TOPE_USD` = 3) se revisa antes de cada llamada web, guardando la
reserva de la selección.

La guarda bloquea si: los números están fuera de rango (1–9 candidatos, 0–8 búsquedas, hasta 5 empresas y 5 perfiles
válidos), la cuenta es la de publicación oficial (no lee perfiles ajenos), los main no están identificados, este mes
ya hubo una búsqueda de industria **con propuestas** (por decidir o ya decididas) o hay una **en curso**, ya hubo
`REFERENTES_INDUSTRIA_MAX_INTENTOS` (3) búsquedas este mes, no queda
plaza variable libre, el tope no alcanza para una investigación más la selección, o no queda saldo en el ciclo
`referentes_mensuales` (5 USD al mes, compartido con la revisión mensual) o en el presupuesto diario del equipo. Avisa
sin bloquear si quedan menos investigaciones web hoy (`WEB_RESEARCH_DAILY_LIMIT`, compartido) o si el tope es menor que
el peor caso.

Corre dentro del ciclo `referentes_mensuales` (mismas aristas y presupuesto; sin nodo nuevo en el grafo): como máximo 3
llamadas web y 1 de selección, dentro de sus 4 llamadas a proveedor por instancia.

**Otro intento en el mes.** Si todas las búsquedas de industria del mes terminaron sin una sola propuesta (0 cambios),
se puede lanzar otra con el mismo comando: el informe dice «Intento N de este mes». Cada intento es su propia
`ReferentReview` (`attempt`, migración `0046`): su dossier, su aviso «Referentes de industria por decidir», su ledger
(clave = id de la revisión) y sus claves de investigación web. El `request_id` del trabajo sigue siendo determinista:
el del primer intento no cambia (`referents:<cuenta>:<mes>:industria`) y los siguientes añaden `:<N>`. Al empezar, el
intento nuevo cierra los anteriores (`closed_at`, `dossier.reemplazada` con fecha y motivo; su dossier no se toca) y
deja la auditoría `referents.industry_retry`; sin aviso de cierre, porque no tenían nada por decidir. El tope mensual
del ciclo es el mismo (el gasto del primer intento cuenta) y el costo se imprime antes de confirmar igual que siempre.
Si el trabajo corre cuando ya hay una propuesta en algún intento del mes, se niega y no cierra nada.

## Modelos de crecimiento (regla `atipico-v1`)

Un post es **atípico** cuando le fue claramente mejor que al post habitual **de su mismo autor**:

- Interacciones = reacciones + comentarios. Un contador oculto no es cero: sin contadores no se juzga.
- Base: los otros posts propios asentados (≥ 48 h) del autor en los últimos 120 días, **sin incluir el propio post**,
  para que un post enorme no suba su propia vara. Mínimo 6.
- Atípico si supera a la vez: ≥ 2 × la mediana, z robusto ≥ 3 (mediana y MAD, para que un viral no mueva la norma) y
  ≥ 20 interacciones. Con MAD 0 decide solo la razón; con mediana 0, solo el mínimo absoluto.
- Variables: `MODELOS_MIN_MUESTRA`, `MODELOS_MIN_VECES_MEDIANA`, `MODELOS_MIN_Z`, `MODELOS_MIN_INTERACCIONES`,
  `MODELOS_DIAS_BASE`, `MODELOS_DIAS_RECIENTES` (45), `MODELOS_HORAS_MADURO`.

**Qué se guarda de cada post observado** (`ObservedPost.outlier/structure/audience`), solo etiquetas y números:

- `outlier`: interacciones, mediana, MAD, veces la mediana, z, muestra, si está asentado y el motivo cuando no es atípico.
- `structure` (`estructura-v1`): idioma, longitud y banda, líneas, párrafos, gancho (tipo, palabras, si va solo),
  forma, ítems de lista, esquema, cierre, ángulo, pilar, conteos de hashtags/menciones/enlaces/emojis, si es anuncio de
  vacantes o promoción. El formato (imagen, video) es «desconocido»: el conector no lo da.
- `audience` (`audiencia-v1`): comentarios leídos, sustantivos, preguntas, aplausos, objeciones y temas de una
  taxonomía fija de 10 temas. Ni nombres ni frases.

Ninguna frase del post ni de sus comentarios sale en un modelo: el texto sigue solo en `ObservedPost.text`, como ya
ocurría para comentar, y cada modelo lleva un enlace al post para verlo y la advertencia «Nunca copiar frases, cifras,
historias ni ejemplos».

**Audiencia de cada modelo:** de quienes comentaron ese post, cuántos ya están clasificados en el barrio, cuántos
encajan, cuántos están en EE. UU. y con qué papel (`PersonEvidence` de tipo `referent_comment` cruzado con `Contact`).
Para atípicos nuevos de referentes de industria se leen como mucho 4 hilos de comentarios al día
(`MODELOS_LECTURAS_DIA`), dentro del tope diario compartido de lecturas de contenido.

## Qué les funciona y qué no (regla `analisis-v1`) <a id="analisis"></a>

`analisis_referentes.py`, sin llamadas pagadas ni lecturas nuevas de LinkedIn: trabaja sobre lo que `operador.observe`
ya guardó (su ventana y sus topes). Costo: 0 USD al día con 11 o 15 referentes. Lo ve Gustavo (o quien opere) en
`GET /api/v1/referentes/analisis` ([contrato](../oficina/CONTRATO-API.md#referentes-analisis)); la app aún no lo muestra.

**Cada post, por partes** (`ObservedPost.analysis`, guardado una vez por texto y medio, solo etiquetas):

| Parte | Qué se guarda |
| --- | --- |
| Recurso visual | Tipo cuando el conector lo reconoce (`imagen`, `imagenes`, `video`, `documento` = carrusel PDF, `encuesta`, `enlace`…; `desconocido` si no). Si es foto, gráfico, captura o infografía exigiría leer la imagen: no se hace. |
| Gancho | Tipo (pregunta, lista anunciada, historia, cifra, contraste, primera persona, afirmación), palabras, si va solo. |
| Cuerpo | Tema de la taxonomía fija (los 10 temas de la audiencia, cada uno bajo un pilar de Gustavo: negocio→producto, IA aplicada, arquitectura y entrega), formato (lista, historia, opinión contraria, caso, tutorial, datos, pregunta abierta, opinión), ángulo y esquema. |
| Cierre | Tipo (pregunta, llamado, enlace, resumen, afirmación) y si es llamado a la acción. |
| Longitud | Banda (corto < 600 caracteres, medio, largo > 1300), palabras, líneas, % de líneas cortas. |

La **firma** de su estructura es `gancho·formato·cierre` (p. ej. `lista_anunciada·lista·pregunta`).

**Contra su propio autor**, contador por contador (reacciones, comentarios, compartidos; las vistas de posts ajenos no
las da LinkedIn): el valor del post, la mediana de los otros posts originales del mismo autor con ≥ 48 h de los últimos
120 días (sin contar el propio) y cuántas veces es. Veredicto sobre las interacciones (reacciones + comentarios):

- **Funcionó**: la regla de los modelos (`atipico-v1`: ≥ 2 × su mediana, z robusto ≥ 3, ≥ 20 interacciones).
- **No funcionó**: ≤ 0,5 × su mediana (`REFERENTES_ANALISIS_VECES_BAJO`).
- **Normal** entre medias. **Sin juicio** con menos de 6 posts de base, < 48 h o sin contadores.

**Duradero o pasajero.** Un post que funcionó es **de coyuntura** si habla de una noticia (anunció, lanzó, adquirió…),
nombra una fecha («esta semana», «March 12», «Q3 2026») o un lanzamiento (GPT-5, DevDay…), o si nombra lo mismo que
otro referente la misma semana (nombres propios compartidos; una línea en Title Case no cuenta como nombres).

- **Estructuras sostenidas**: firmas con ≥ 3 posts que funcionaron **sin coyuntura**, de ≥ 2 autores, en ≥ 2 semanas
  distintas (`REFERENTES_ANALISIS_MIN_POSTS`, `_MIN_AUTORES`, `_MIN_SEMANAS`). Por debajo es **hipótesis** y dice qué
  falta. También salen las que rinden por debajo (≥ 2 posts con juicio, la mitad o más «no funcionó»).
- **Temas en tendencia**: un nombre que usan ≥ 2 referentes la misma semana, o el tema de un post de coyuntura que
  funcionó, en los últimos 14 días; cada uno con su fecha de caducidad (`REFERENTES_ANALISIS_DIAS_TENDENCIA`,
  `_AUTORES_TENDENCIA`).
- Por referente y en total, cada parte (tema, recurso visual, gancho, formato, cierre, longitud) con sus posts, cuántos
  funcionaron o no, la mediana de «veces» y `muestra_pequena` cuando hay menos de 3 con juicio.

**Al editorial**, solo con `REFERENTES_ANALISIS=true` (apagado por defecto: lee exactamente lo de antes), dos señales
aparte en `estrategia.audience_signals`, no citables como evidencia: `estructura_sostenida` (hasta 5 estructuras, las
sostenidas primero y las hipótesis marcadas, con la advertencia de reutilizar la estructura y nunca el texto) y
`tema_en_tendencia` (hasta 5 temas con su caducidad). Ninguna frase de un referente: etiquetas, cifras, fechas y los
nombres compartidos.

**No se hizo:** una sección en el resumen semanal (es una llamada pagada con validación de cifras y su validador corta
toda frase causal sobre «referentes»: añadirla exige cambiar su prompt y su validador); un modelo para el tipo de imagen
(habría que descargar cada imagen: lecturas nuevas y ≈ 0,001–0,002 USD por imagen con un modelo pequeño de visión,
menos de 0,05 USD al día con 15 referentes, pero requiere su visto bueno) ni para temas libres.

## Del post viral al post propio: el molde (regla `molde-v1`) <a id="molde"></a>

`moldes.py`, decidido por Gustavo el 18/11/2026. El análisis decía qué les funciona a los referentes, pero el post del
día no tomaba esa forma: el plan citaba un atípico como evidencia y el director escribía libre. Además la regla estricta
(`atipico-v1`) solo deja pasar cuentas grandes, así que un competidor con números pequeños nunca aportaba nada. El molde
lleva la forma de un post que funcionó hasta la variante A del redactor y mide si sirvió. Sin llamadas pagadas nuevas ni
lecturas de LinkedIn: trabaja sobre lo que `operador.observe` y el análisis ya guardaron.

**Qué es un molde** (solo etiquetas de un vocabulario fijo y números, nunca una frase del post):

| Campo | Qué lleva |
| --- | --- |
| `gancho` | Tipo (pregunta, lista anunciada, historia, cifra…), palabras y si va en su propia línea. |
| `cuerpo` | Formato (lista, historia, opinión contraria, caso, tutorial, datos, pregunta abierta, opinión), esquema por bloques e ítems de lista. |
| `cierre` | Tipo (pregunta, llamado, enlace, resumen, afirmación). |
| `longitud` | Banda del post y el rango que pueden cumplir los redactores (corto 600–800, medio 600–1.300, largo 1.300–1.800 caracteres; su propia regla es 600–1.800). |
| `angulo` | Experiencia propia, caso de cliente, a contracorriente, tutorial, datos, tendencia o general. |
| `fuente` | Id del post, referente, autor, enlace, fecha, cuántas veces su mediana, interacciones, mediana del autor y muestra. |
| `estado` | `sostenida` si su estructura (`gancho·formato·cierre`) es una estructura sostenida del [análisis](#analisis) (≥ 3 posts, ≥ 2 autores, ≥ 2 semanas); si no, `hipotesis`, con `faltan` (qué le falta para la regla estricta: «menos de 6 posts propios de base», «menos de 20 interacciones», «post de coyuntura»…). |

**Cada autor frente a su propia norma.** Cada post original de un referente, de los últimos 120 días y con ≥ 48 h, se
compara con la mediana de los **otros** posts del mismo autor (como `atipico-v1`) con una regla más suave, solo para
ofrecer moldes: ≥ 3 posts de base (`MOLDES_MIN_MUESTRA`) y ≥ 1,5 × su mediana (`MOLDES_MIN_VECES_MEDIANA`), sin mínimo
absoluto de interacciones ni z. Así un competidor con 4 interacciones de norma y un post de 12 aporta ese post. Se
descartan los anuncios de vacantes, las promociones, los que el prefiltro del líder descartó y los de coyuntura (noticia,
fecha o lanzamiento en el propio post). La marca estricta (`ObservedPost.outlier`, `atipico-v1`) no cambia: el molde
solo la usa para decir `atipico_estricto` y qué le falta a una hipótesis. Un post leído por dos miembros cuenta una vez.

**La oferta** (`Catalog.offer`): primero un ejemplo de cada estructura sostenida; después los mejores de cada autor por
turnos (el mejor de cada uno antes que el segundo de nadie), como mucho `MOLDES_POR_AUTOR` (2) por autor y
`MOLDES_OFERTA` (8) en total. Referentes de industria primero; sin ninguno con molde, todos los observados (como
`estrategia.growth_models`).

**La semana.** El plan del domingo recibe `moldes.ofrecidos` y cada opción dice sobre qué molde se escribe (`molde`: un
id ofrecido, el id de una estructura sostenida `estructura:…` o vacío si ninguno encaja con el tema: un molde nunca
fuerza un tema). Un día basado en un atípico (`audience_evidence` `referent_outlier`) toma el molde de ese post. El día
guarda el molde entero, con su enlace; `plan.signals.used` lo registra como una señal más (`kind: molde`, etiqueta,
estado, autor, enlace) y el resumen semanal lo lee en `plan_siguiente`. Como mucho `MOLDES_MAX_AUTOR_SEMANA` (2) días de
una semana sobre moldes del mismo autor: los días que Gustavo fijó o que ya se prepararon cuentan primero y el resto por
fecha; un día que se pasa del tope conserva su idea, pierde el molde y la semana lo avisa. Cambiar el tipo de un día o
descartar su idea le quita el molde, mover dos días lo lleva con su idea y un día que se vuelve a planear con otra idea
no conserva el de antes. La vista de la semana (`GET /api/v1/estrategia/semana`) trae el molde de cada día mientras el
interruptor está encendido.

**El día.** El director recibe `strategy.planned.molde` (el del plan) y `strategy.moldes` (los ofrecidos, sin los
autores que ya llenan su tope de la semana). El brief lleva `molde` solo si es el planeado o uno ofrecido: sin decir
nada se queda el planeado, vacío es ninguno y un id inventado no cuenta. Un día sin molde en el plan puede tomar uno
ofrecido. Sin molde, nada cambia.

**Los redactores.** A y B siguen saliendo de la misma llamada `redactor` (el grafo la cuenta una vez por pieza). Esa
llamada recibe aparte `molde_variante_a`: gancho, cuerpo, cierre, rango de longitud, ángulo, estado y la regla de uso;
sin autor, enlace, id ni texto. La variante A se escribe sobre él con el material y la voz de Gustavo; la B queda libre.
El brief compartido no lleva el molde, y los lectores, la selección y el verificador no saben cuál variante lo sigue:
juzgan las dos a ciegas.

**La medición.** Al elegir, la pieza guarda `selection.molde` = `{id, estado, variante: "A", decision, ganadora}` con
`ganadora` `molde` (ganó A), `libre` (ganó B), `fusion` o `descartada`. El resumen semanal añade a sus cifras `moldes`
sobre los posts publicados en las cuatro semanas que terminan con la del resumen: con molde (el texto publicado es la
variante A), libre le ganó al molde, fusión y sin molde, cada grupo con la mediana de impresiones y de interacción a las
72 h y `muestra_pequena` con menos de tres medidos; cuántas veces ganó cada variante; y por molde (etiqueta, estado,
autor, enlace) sus duelos y los resultados de los posts que salieron con su texto. Son datos: el analista los lee como
otra sección de `estadisticas`, sin llamada nueva.

**Interruptor y variables.** `REFERENTES_MOLDE=false` por defecto. Apagado, el plan, el director y los redactores leen
exactamente lo de antes: sus instrucciones, esquemas y pedidos son los mismos byte a byte (las huellas de
`tests/test_identidad_prompts.py` no cambian) y un molde guardado en un plan no se usa. Encendido, el plan y el director
reciben como mucho 8 moldes (unos 450 tokens cada uno, menos de 4.000 en total) y el redactor unos 250 tokens más.

| Variable | Defecto | Para qué |
| --- | --- | --- |
| `REFERENTES_MOLDE` | `false` | Enciende todo lo de esta sección. |
| `MOLDES_POR_AUTOR` | 2 | Moldes de un mismo autor en la oferta. |
| `MOLDES_MAX_AUTOR_SEMANA` | 2 | Días de una semana sobre moldes de un mismo autor. |
| `MOLDES_MIN_MUESTRA` | 3 | Otros posts del autor que hacen su norma. |
| `MOLDES_MIN_VECES_MEDIANA` | 1,5 | Cuántas veces su mediana debe superar un post. |
| `MOLDES_OFERTA` | 8 | Moldes ofrecidos al plan y al director. |

**Límites conocidos.**

- A y B salen de una sola llamada: B no es una ejecución independiente (como antes), aunque la instrucción dice que no
  use el molde. Separarlas costaría una llamada pagada más por pieza y cambiar el grafo (`call_group redactor`).
- El molde no lleva texto del referente, pero los redactores ya recibían antes `sources`: el texto (hasta 700
  caracteres) de los posts observados que el director cita en `signals_used`, entre ellos posts de referentes. No es
  parte del molde y no se cambió; queda como [pregunta abierta](#preguntas-abiertas).
- La coyuntura del molde mira el propio post (noticia, fecha, lanzamiento); no la de «varios referentes nombran lo
  mismo la misma semana», que el análisis sí usa para sus estructuras.
- Con pocos posts publicados, la comparación es una pista (`muestra_pequena`), no una conclusión.

## Interfaz para la estrategia semanal

La rama de estrategia semanal consume dos funciones de `modelos_crecimiento` (sin llamadas pagadas):

- `growth_models(account=None, *, limit=8, now=None, kinds=('industria',), days=None)`: atípicos recientes ordenados por
  relevancia = min(veces la mediana, 20) × (0,5 + proporción de comentaristas con encaje, o 1 si no se midió). Un post
  que llegó al barrio supera a uno más grande que no. Excluye anuncios de vacantes, promociones y los que el prefiltro
  del líder descartó.
- `audience_questions(account=None, *, days=60, kinds=('industria',), limit=10, top_only=True, now=None)`: qué pregunta
  y qué objeta la audiencia de esos referentes, por tema, con número de posts y referentes. El contenido futuro debería
  responderlo.

## Costes de lectura continuos

- Observar: cada referente de industria nuevo lee 20 posts la primera vez (para tener base) y luego los mismos que
  cualquier referente, unas 8 lecturas al día con la observación cada 180 minutos.
- Hasta 4 lecturas de comentarios al día para la audiencia de atípicos nuevos.

## Preguntas abiertas

1. Umbrales: ¿10.000 seguidores y mediana 50 son «grandes» para él? ¿30 % de encaje es el corte justo? Recalibrar con
   las primeras búsquedas. El embudo (`--informe`) mostrará cuántos dueños de agencia caen en «tamaño» y con qué cifras:
   si casi todos los que venden lo mismo tienen menos de 10.000 seguidores, la decisión es de Gustavo (bajar el umbral
   o aceptar menos propuestas); el código no lo relaja solo.
2. Las búsquedas con `OR`, paréntesis y comillas siguen la sintaxis del buscador de LinkedIn, pero no se probaron con el
   conector directo. Si una devuelve 0 resultados, el dossier (`busquedas`) lo dice; cambiar `QUERIES` es un cambio de código.
3. ¿El criterio de audiencia debe ser obligatorio (`REFERENTES_INDUSTRIA_AUDIENCIA_OBLIGATORIA=true`) cuando haya más
   comentaristas clasificados?
4. Agrupar preguntas libres con un modelo (≈ 0,0005 USD por post con Haiku) en vez de la taxonomía fija: requiere su visto bueno.
5. Oficina (escritorio) aún no muestra los criterios; la app móvil sí.
6. Integración con la estrategia semanal (GASP), hecha el 14/11/2026: `estrategia.growth_models` usa estos atípicos
   antes que los de los referentes observados, y `audience_questions` es la señal `audience_question` del plan y del
   director (ids `tema:<pregunta|objecion>:<tema>`). Solo etiquetas y cifras; sin llamadas pagadas nuevas.
7. Los redactores reciben en `sources` el texto de los posts observados que cita el director (hasta 700 caracteres),
   también de referentes: «estructura y ángulo, nunca su texto» lo cumple el molde, pero esa entrada es anterior y
   sigue igual. ¿Se le quita el texto a los posts de referentes en `sources`?
