# Resultados (`RES`)

Cuatro preguntas con cifras: ¿genera negocio?, ¿llegamos a la gente correcta?, ¿el contenido aporta? y ¿el equipo trabaja bien? Todo comparado con el periodo anterior y sin presentar nunca un dato que falta como cero. El resumen semanal, que va arriba de Resultados, está en [resumen-semanal.md](resumen-semanal.md).

- **Código:** backend `resultados.py` (`build`, `negocio`, `audiencia`, `contenido`, `equipo`, `spend`), `resultados_views.Resultados`, `metricas.py` (`collect`, trabajo `collect_metrics`); PWA `oficina/src/pages/Resultados.tsx`, `pages/resultados/*`; app `movil/src/resultados/*`; común `compartido/src/logic/resultados.ts`.
- **Documentación:** sección «Resultados» de [`CONTRATO-API.md`](../../oficina/CONTRATO-API.md), [`metricas-resultados.md`](../../agentes-linkedin/infra/docs/metricas-resultados.md).

## Resumen

| ID | Función | Dónde | Estado |
| --- | --- | --- | --- |
| [RES-01](#res-01) | Elegir periodo y modalidad | PWA · app · backend | funciona |
| [RES-02](#res-02) | Fichas de indicadores: sin dato no es cero | PWA · app · backend | funciona |
| [RES-03](#res-03) | 1 · ¿Genera negocio? | PWA · app · backend | funciona |
| [RES-04](#res-04) | 2 · ¿Llegamos a la gente correcta? | PWA · app · backend | funciona |
| [RES-05](#res-05) | 3 · ¿El contenido aporta? | PWA · app · backend | funciona |
| [RES-06](#res-06) | Posts del periodo | PWA · app · backend | funciona |
| [RES-07](#res-07) | 4 · ¿El equipo trabaja bien? | PWA · app · backend | funciona |
| [RES-08](#res-08) | Errores por sección | PWA · app | funciona |
| [RES-09](#res-09) | Medir los posts y la audiencia | backend | funciona |

---

### RES-01 · Elegir periodo y modalidad <a id="res-01"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** mira los últimos 7, 28 o 90 días, todo o solo una modalidad (Startups o ProjectApp), comparado con el periodo anterior de la misma duración.
- **Código:** `GET /api/v1/resultados?dias=7|28|90&modalidad=todo|personal_startups|projectapp`.
- **Criterios de aceptación:**
  1. **Dado** Resultados sin parámetros, **cuando** lo abre, **entonces** ve 28 días y «Todo», y «Periodo en curso: datos hasta <…>. Todo se compara con los 28 días anteriores.».
  2. **Dado** «Periodo» = 7 días, **cuando** lo elige, **entonces** las cifras se recalculan, el valor queda en la URL (`?dias=7`) y los datos anteriores se ven atenuados mientras carga.
  3. **Dado** una modalidad elegida, **cuando** se recalcula, **entonces** solo cambian las secciones 1 y 2; las secciones 3 y 4 dicen «No se separa por modalidad: muestra toda la cuenta.».
  4. **Dado** `dias=10` o una modalidad desconocida, **cuando** se pide a la API, **entonces** responde 400 «dias debe ser 7, 28 o 90.» o «modalidad debe ser todo, personal_startups o projectapp.».
  5. **Dado** los accesos «1 · Negocio» a «4 · Equipo», **cuando** pulsa uno, **entonces** salta a esa sección.
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### RES-02 · Fichas de indicadores: sin dato no es cero <a id="res-02"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** cada cifra dice qué mide, cómo se calcula y cuánto cambió; si falta el dato, lo dice en vez de mostrar un cero.
- **Código:** forma `KPI` (`value`, `previous`, `delta`, `delta_pct`, `comparable`, `series`, `definition`, `formula`, `unavailable_reason`); PWA `components/ui/KpiCard.tsx`; app `resultados/charts.tsx`, `CountUp.tsx`.
- **Criterios de aceptación:**
  1. **Dado** un indicador con `value: null`, **cuando** se pinta, **entonces** muestra «—» y `unavailable_reason` (o «Sin dato en este periodo.»), nunca 0.
  2. **Dado** `comparable: false`, **cuando** se pinta, **entonces** la variación va en gris: «sin comparación».
  3. **Dado** un indicador en %, **cuando** se pinta la variación, **entonces** va en puntos («N pts»).
  4. **Dado** el valor anterior igual a 0, **cuando** se calcula, **entonces** `delta_pct` es `null`.
  5. **Dado** «ⓘ», **cuando** lo pulsa, **entonces** ve la definición y la fórmula.
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### RES-03 · 1 · ¿Genera negocio? <a id="res-03"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** ve sus oportunidades abiertas, reuniones, propuestas y acuerdos, el embudo y el reparto entre Startups y ProjectApp.
- **Código:** `resultados.negocio`; PWA y app `resultados/sections.tsx`.
- **Criterios de aceptación:**
  1. **Dado** que no hay ninguna oportunidad registrada (`negocio.disponible: false`), **cuando** abre Resultados, **entonces** la sección muestra solo el motivo («Mediremos oportunidades cuando registres la primera o conectemos el inbox»), «Registrar una oportunidad» (abre el formulario, [PRS-08](personas-oportunidades.md#prs-08)) y la ficha «Inbound».
  2. **Dado** oportunidades, **cuando** abre Resultados, **entonces** ve Conversaciones pertinentes, Oportunidades abiertas, Reuniones, Propuestas enviadas, Acuerdos e Inbound, el «Embudo de oportunidades» con «Cerrada sin acuerdo: N», el «Reparto por modalidad» y «Oportunidades activas» (las 5 más recientes, enlazadas a la persona).
  3. **Dado** que no hay oportunidades activas, **cuando** se pinta, **entonces** ve «No hay oportunidades activas ahora mismo.».
- **Brechas código/docs:** los campos de `negocio` con `disponible: true` (conversaciones, abiertas, reuniones, propuestas, acuerdos, embudo, modalidades, activas) existen en `resultados.py` y en las interfaces, pero `CONTRATO-API.md` solo documenta el caso `disponible: false`.
- **Cobertura QA:** pendiente

### RES-04 · 2 · ¿Llegamos a la gente correcta? <a id="res-04"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** ve seguidores, conexiones, visitas al perfil, conexiones nuevas que encajan (por rol), tasa de aceptación, el embudo de la red y las personas que vuelven a interactuar.
- **Código:** `resultados.audiencia`.
- **Criterios de aceptación:**
  1. **Dado** lecturas de audiencia, **cuando** abre la sección, **entonces** ve Seguidores, Conexiones, Visitas al perfil, Conexiones nuevas que encajan, Tasa de aceptación (%) y Personas recurrentes (enlazadas a su ficha).
  2. **Dado** una modalidad elegida, **cuando** se recalcula, **entonces** seguidores, conexiones y visitas siguen siendo de toda la cuenta.
  3. **Dado** que falta el reparto por rol, **cuando** se pinta, **entonces** dice «— <motivo>» o «— Sin dato en este periodo.».
  4. **Dado** el embudo de la red, **cuando** se pinta, **entonces** sigue el orden de etapas de la red y muestra aparte las que no forman parte del embudo.
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### RES-05 · 3 · ¿El contenido aporta? <a id="res-05"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** ve las impresiones medianas, la interacción, los comentarios con sustancia, la constancia, un gráfico por post, su mejor post y la interacción por pilar, comparando posts de la misma edad.
- **Código:** `resultados.contenido`; PWA `resultados/charts.tsx`; app `resultados/charts.tsx`.
- **Criterios de aceptación:**
  1. **Dado** posts del periodo con corte de 7 días, **cuando** abre la sección, **entonces** las fichas comparan a 7 días; si ningún post cumple 7 días, comparan a 24 h (`cut`).
  2. **Dado** el gráfico, **cuando** un post aún no cumple 7 días, **entonces** su barra usa las impresiones a 24 h y se distingue (`fallback: true`); tocar una barra abre la pieza.
  3. **Dado** que no hay posts en el periodo, **cuando** se pinta, **entonces** ve «Sin posts publicados en el periodo.».
  4. **Dado** un mejor post, **cuando** se pinta, **entonces** ve su primera línea, fecha, pilar, impresiones e interacción con «Ver la pieza»; si ninguno tiene corte, «Aún ningún post del periodo tiene su corte de impresiones.».
  5. **Dado** posts sin corte, **cuando** se pinta «Interacción media por pilar», **entonces** ve «Sin posts con corte en el periodo.».
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### RES-06 · Posts del periodo <a id="res-06"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** repasa cada post del periodo con sus cifras y lo ordena.
- **Código:** `contenido.posts`; PWA `resultados/PostsTable.tsx` (tabla en escritorio, tarjetas en el teléfono); app `resultados/PostCard.tsx`.
- **Criterios de aceptación:**
  1. **Dado** posts publicados, **cuando** abre la lista, **entonces** cada uno muestra fecha, primera línea (enlazada a la pieza), pilar, impresiones a 24 h y a 7 días, reacciones, comentarios, republicaciones, interacción y quién comentó por rol.
  2. **Dado** un corte que falta, **cuando** se pinta, **entonces** dice «Aún sin corte», «Sin leer» o «Nadie», nunca 0.
  3. **Dado** «Ordenar por», **cuando** elige una columna, **entonces** se reordena (en la PWA de escritorio en los dos sentidos; en la app solo de mayor a menor).
  4. **Dado** que no hay posts, **cuando** se pinta, **entonces** ve «Sin posts publicados en el periodo.».
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### RES-07 · 4 · ¿El equipo trabaja bien? <a id="res-07"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** ve cuántos comentarios publicó y respondieron, cuánta gente siguió, invitó y aceptó, cuántas piezas salieron, se bloquearon o vetó, y lo gastado en IA.
- **Código:** `resultados.equipo`, `resultados.spend`.
- **Criterios de aceptación:**
  1. **Dado** actividad del periodo, **cuando** abre la sección, **entonces** ve Comentarios (publicados · con respuesta), Red (seguidos · invitados · aceptados) y Piezas (publicadas · bloqueadas · vetadas).
  2. **Dado** el gasto, **cuando** se pinta «Gasto de IA», **entonces** ve «$X de $Y hoy» (la suma de los presupuestos diarios) y «$Z este mes»; un dato que falta es «—».
- **Brechas código/docs:** el texto `definition` de `spend` (en `resultados.py`) y `CONTRATO-API.md` dicen que `ANTHROPIC_LIMIT_USD` es un techo acumulado; desde B5 (`knowledge/providers.limit_window_start`) es mensual por defecto (`ANTHROPIC_LIMIT_WINDOW=total` vuelve al acumulado). Ver [AJU-05](ajustes.md#aju-05).
- **Cobertura QA:** pendiente

### RES-08 · Errores por sección <a id="res-08"></a>

- **Dónde:** PWA · app
- **Estado:** funciona
- **Qué hace para Gustavo:** si una parte de Resultados falla, el resto sigue visible.
- **Código:** PWA `resultados/sections.tsx` (`SectionBoundary`); app `resultados/sections.tsx`.
- **Criterios de aceptación:**
  1. **Dado** la carga, **cuando** abre Resultados, **entonces** ve las fichas en esqueleto («Cargando…»).
  2. **Dado** un error sin datos previos, **cuando** falla, **entonces** ve «No se pudieron cargar los resultados» con «Reintentar»; con datos previos, «No se pudo actualizar».
  3. **Dado** una sección que llega sin datos, **cuando** se pinta, **entonces** dice «No se pudo cargar esta sección.».
  4. **Dado** una sección con una forma inesperada, **cuando** se pinta, **entonces** dice «No se pudo mostrar esta sección» con «Los datos de esta sección llegaron con una forma inesperada.» y «Reintentar», y las demás secciones siguen.
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### RES-09 · Medir los posts y la audiencia <a id="res-09"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** el equipo lee solo cómo van sus posts a las 24 h, 72 h y 7 días, quién comentó y su audiencia diaria.
- **Código:** `metricas.collect` (trabajo `collect_metrics`, cada `METRICS_EVERY_MINUTES`), `PostMetric`, `AudienceSnapshot`, topes `metrics.read`.
- **Criterios de aceptación:**
  1. **Dado** un post publicado hace 25 h sin corte de 24 h, **cuando** corre `collect_metrics`, **entonces** se guarda un `PostMetric` `24h` con impresiones, reacciones, comentarios y republicaciones; nunca dos del mismo corte para la misma pieza.
  2. **Dado** que una lectura no devuelve un dato, **cuando** se guarda, **entonces** queda `null`, no 0.
  3. **Dado** el tope diario de lecturas de métricas agotado, **cuando** toca leer, **entonces** no se lee y se registra «Tope diario de lecturas de métricas «…» alcanzado (N).».
  4. **Dado** comentarios leídos, **cuando** se guardan, **entonces** cada comentarista lleva si su comentario tiene sustancia, su rol y si encaja.
  5. **Dado** un fallo de las métricas, **cuando** corre el autopiloto, **entonces** el resto del ciclo sigue.
- **Brechas código/docs:** la única fuente de métricas es Unipile; la analítica oficial de LinkedIn no está conectada (`publicacion-diaria.md`).
- **Cobertura QA:** pendiente

## Retiradas

Ninguna.
