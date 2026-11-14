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

## Qué es un referente de industria

`Referent.kind = industria` (los de siempre son `nicho`). Ocupa una plaza variable como cualquier referente: el equipo
observa sus posts, descubre personas en sus comentarios y el autopiloto puede comentar en ellos. Lo distinto:

- Entra solo con la decisión explícita de Gustavo (tarjeta «Alta de industria: …», 14 días para decidir). No se aplica
  al cierre del día 5 ni por ningún vencimiento; los recordatorios del día 4 son solo del lote mensual.
- Sus posts atípicos se convierten en **modelos de crecimiento** para la estrategia semanal ([OBS-06](funcionalidades/observatorio-referentes.md#obs-06)).

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

## De dónde salen los candidatos

Solo de lecturas de LinkedIn de la cuenta conectada (conector directo), nunca de la web:

1. Contactos ya conocidos del barrio con ≥ 10.000 seguidores registrados.
2. Búsquedas de personas en EE. UU. con las palabras de cada servicio (round robin entre los cuatro servicios).

Para cada candidato, los más grandes primero: una lectura de perfil, una de sus últimos 20 posts (solo contadores y
fechas; los posts no se guardan) y una de los comentarios de su mejor post (para medir la audiencia). Leer un perfil
con el conector directo registra una visita en ese perfil. Del perfil se conserva, como fuente fechada del dossier, la
línea pública: nombre, titular, ubicación y extracto de hasta 1.500 caracteres. No se guardan nombres de quienes comentan.

Solo los que pasan los criterios medibles (tamaño, actividad y audiencia no medida como ajena) van a la investigación
web, que busca pruebas de servicios, autoridad y mercado EE. UU. La pregunta web lleva el nombre público del candidato,
sin URLs. La selección final solo puede proponer candidatos de la lista, y el código verifica cada afirmación contra la
fuente citada antes de publicar la tarjeta.

## Cómo se lanza y cuánto cuesta

Solo a mano, nunca automático:

```
python manage.py operador referentes-industria --cuenta <id> [--candidatos 6] [--busquedas 4] [--tope-usd 3] [--confirmar]
```

Sin `--confirmar` imprime el peor caso y no encola nada. Con los valores por defecto:

| Concepto | Peor caso |
| --- | --- |
| Lecturas de LinkedIn | 5 búsquedas, 6 perfiles, 12 de contenido (gratis; cuentan en los topes diarios de `red.READ_CAPS`) |
| Investigaciones web | 2 llamadas × 0,82 USD de reserva |
| Selección | 0,27 USD de reserva |
| **Total reservado** | **1,91 USD** (2,73 USD con 9 candidatos y 3 llamadas) |

Lo real suele ser menos: la reserva cuenta cada vuelta de herramienta como si repitiera toda la entrada. El tope duro
(`--tope-usd`, por defecto `REFERENTES_INDUSTRIA_TOPE_USD` = 3) se revisa antes de cada llamada web, guardando la
reserva de la selección.

La guarda bloquea si: los números están fuera de rango (1–9 candidatos, 0–8 búsquedas), la cuenta es la de publicación
oficial (no lee perfiles ajenos), los main no están identificados, ya hubo una búsqueda de industria este mes, no queda
plaza variable libre, el tope no alcanza para una investigación más la selección, o no queda saldo en el ciclo
`referentes_mensuales` (5 USD al mes, compartido con la revisión mensual) o en el presupuesto diario del equipo. Avisa
sin bloquear si quedan menos investigaciones web hoy (`WEB_RESEARCH_DAILY_LIMIT`, compartido) o si el tope es menor que
el peor caso.

Corre dentro del ciclo `referentes_mensuales` (mismas aristas y presupuesto; sin nodo nuevo en el grafo): como máximo 3
llamadas web y 1 de selección, dentro de sus 4 llamadas a proveedor por instancia.

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
   las primeras búsquedas.
2. ¿El criterio de audiencia debe ser obligatorio (`REFERENTES_INDUSTRIA_AUDIENCIA_OBLIGATORIA=true`) cuando haya más
   comentaristas clasificados?
3. Agrupar preguntas libres con un modelo (≈ 0,0005 USD por post con Haiku) en vez de la taxonomía fija: requiere su visto bueno.
4. Oficina (escritorio) aún no muestra los criterios; la app móvil sí.
5. Integración con la estrategia semanal (GASP), hecha el 14/11/2026: `estrategia.growth_models` usa estos atípicos
   antes que los de los referentes observados, y `audience_questions` es la señal `audience_question` del plan y del
   director (ids `tema:<pregunta|objecion>:<tema>`). Solo etiquetas y cifras; sin llamadas pagadas nuevas.
