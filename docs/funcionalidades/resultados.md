# Resultados (`RES`)

Cuatro preguntas con cifras: ¿genera negocio?, ¿llegamos a la gente correcta?, ¿el contenido aporta? y ¿el equipo trabaja bien? Todo comparado con el periodo anterior y sin presentar nunca un dato que falta como cero. El resumen semanal, que va arriba de Resultados, está en [resumen-semanal.md](resumen-semanal.md).

- **Código:** backend `resultados.py` (`build`, `negocio`, `audiencia`, `contenido`, `equipo`, `spend`), `resultados_views.Resultados`, `metricas.py` (`collect`, trabajo `collect_metrics`), `analitica.py` (analítica de LinkedIn, trabajo `import_analytics`, `resultados_views.Analitica`); PWA `oficina/src/pages/Resultados.tsx`, `pages/resultados/*`; app `movil/src/resultados/*`; común `compartido/src/logic/resultados.ts`, `logic/analitica.ts`.
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
| [RES-10](#res-10) | Traer la analítica de LinkedIn | backend | funciona |
| [RES-11](#res-11) | Consultar la analítica por periodo | backend | funciona |
| [RES-12](#res-12) | Ver la analítica de LinkedIn en la app | app · backend | funciona |

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
- **Cobertura QA:** RES-01.1, 2, 3 y 5 en `movil/.maestro/08-resultados.yaml` (periodo 7/28/90, modalidad «Startups», accesos) · RES-01.4 sin prueba E2E · 2026-11-08 · pasa

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
- **Cobertura QA:** RES-02.1 y 5 en `08-resultados.yaml` («—» con su motivo en «Conversaciones pertinentes» y «Personas recurrentes», definición) · RES-02.2–4 sin prueba E2E · 2026-11-08 · pasa

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
- **Cobertura QA:** RES-03.2 y 3 en `08-resultados.yaml` y `08-resultados-errores.yaml` (embudo, reparto, oportunidad activa que abre la ficha; sin oportunidades activas) · RES-03.1 sin prueba E2E · 2026-11-08 · pasa

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
- **Cobertura QA:** RES-04.1 en `08-resultados.yaml` · RES-04.2–4 sin prueba E2E · 2026-11-08 · pasa

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
- **Cobertura QA:** RES-05.2–4 en `08-resultados.yaml` y `08-resultados-errores.yaml` (barra que abre la pieza, mejor post, periodo sin posts) · RES-05.1 y 5 sin prueba E2E · 2026-11-08 · pasa

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
- **Cobertura QA:** RES-06.1, 2 y 4 en `08-resultados.yaml` y `08-resultados-errores.yaml` («7 días: sin dato», «Republic.: sin dato») · RES-06.3 sin prueba E2E · 2026-11-08 · pasa

### RES-07 · 4 · ¿El equipo trabaja bien? <a id="res-07"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** ve cuántos comentarios publicó y respondieron, cuánta gente siguió, invitó y aceptó, cuántas piezas salieron, se bloquearon o vetó, y lo gastado en IA.
- **Código:** `resultados.equipo`, `resultados.spend`.
- **Criterios de aceptación:**
  1. **Dado** actividad del periodo, **cuando** abre la sección, **entonces** ve Comentarios (publicados · con respuesta), Red (seguidos · invitados · aceptados) y Piezas (publicadas · bloqueadas · vetadas).
  2. **Dado** el gasto, **cuando** se pinta «Gasto de IA», **entonces** ve «$X hoy» (Anthropic por áreas; desde el 10/11/2026 las áreas no tienen tope propio, así que `today.*.budget` llega `null` y no hay «de $Y») y «$Z este mes» (`month.total`: todos los proveedores, frente a `AI_MONTHLY_LIMIT_USD`); un dato que falta es «—».
- **Brechas código/docs:** la interfaz no muestra `spend.daily_fuse` (el tope de seguridad diario `AI_DAILY_FUSE_USD`) ni el presupuesto del mes de `month.total.budget`; están en Ajustes ([AJU-05](ajustes.md#aju-05)).
- **Cobertura QA:** RES-07.1 y 2 en `08-resultados.yaml` («— con respuesta», gasto de hoy) · 2026-11-08 · pasa

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
- **Cobertura QA:** RES-08.2 en `08-resultados-errores.yaml` («No se pudieron cargar los resultados» con «Reintentar») · RES-08.1, 3 y 4 sin prueba E2E · 2026-11-08 · pasa

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
- **Brechas código/docs:** estos cortes salen de Unipile. Con una cuenta `directo`, la analítica de LinkedIn llega por [RES-10](#res-10); la analítica oficial de la API de LinkedIn sigue sin conectar (`publicacion-diaria.md`).
- **Cobertura QA:** pendiente

### RES-10 · Traer la analítica de LinkedIn <a id="res-10"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** cada día el equipo trae de LinkedIn la analítica de su cuenta, la misma de «Exportar»: impresiones e interacciones por día, publicaciones recientes, publicaciones principales, seguidores y demografía. Solo lee.
- **Código:** `linkedin_directo/analitica.py` (lee el libro), `analitica.import_range`, `run` (trabajo `import_analytics`), `backfill`; `autopiloto._analytics`; comando `manage.py analitica importar|carga-inicial|estado`; modelos `AnalyticsDay`, `AnalyticsPost`, `AnalyticsSnapshot`, `AnalyticsRange`, `AnalyticsImport`. Ver [`metricas-resultados.md`](../../agentes-linkedin/infra/docs/metricas-resultados.md#analítica-de-linkedin-cuenta-directo).
- **Criterios de aceptación:**
  1. **Dado** una cuenta `directo` sin pausa y con el servicio navegador configurado, **cuando** el autopiloto corre después de las 01:30 UTC, **entonces** pone en cola un solo `import_analytics` ese día, que trae los 14 días completos que terminan ayer y después, uno tras otro, los rangos exactos de 7, 28, 90 y 365 días que terminan ayer (`ANALYTICS_DAILY_RANGES`), cada uno con su propia fila de importación.
  2. **Dado** que ese día ya hubo un intento diario, aunque fallara, **cuando** el autopiloto vuelve a correr, **entonces** no pone otro hasta el día siguiente.
  3. **Dado** un día ya importado, **cuando** otra importación lo cubre, **entonces** se actualiza en su sitio; un guion o un día que falta no borra un valor ya visto.
  4. **Dado** que LinkedIn pide entrar, verificar o responde 401/403/429/999, **cuando** se importa, **entonces** la importación queda con error y la cuenta se pausa con «Analítica detenida por el proveedor: …».
  5. **Dado** un libro con otra forma, **cuando** se importa, **entonces** la importación queda con error `analytics_parse` y un mensaje con la hoja y la fila, sin el valor de ninguna celda; la cuenta no se pausa.
  6. **Dado** la máquina o la cuenta en pausa, o una cuenta que no es `directo`, **cuando** se pide una importación, **entonces** no se lee nada.
  7. **Dado** `manage.py analitica carga-inicial`, **cuando** corre, **entonces** va de ayer hacia atrás en trozos (365 días por defecto) hasta el 10/10/2025, y para en el primer fallo.
  8. **Dado** una petición de exportación con otra pantalla, otro cuerpo, fechas que no son ISO, un rango invertido o de más de 366 días, **cuando** se va a enviar, **entonces** la lista permitida la bloquea y no sale nada.
  9. **Dado** que una exportación del lote diario falla, **cuando** se importa, **entonces** no se pide ningún rango más; y si el trabajo vuelve a correr ese mismo día, trae otra vez los 14 días, pero no repite los rangos ya intentados ni pide ninguno después de un fallo del día.
  10. **Dado** `ANALYTICS_DAILY_RANGES` vacío o `0`, **cuando** corre la importación diaria, **entonces** solo trae los 14 días.
- **Brechas código/docs:** la cuenta de prueba no tiene impresiones: aún no se vio un libro con datos de publicaciones ni de demografía, solo su forma.
- **Cobertura QA:** pruebas de backend en `test_analitica.py` (libros inventados en español e inglés) · sin prueba E2E

### RES-11 · Consultar la analítica por periodo <a id="res-11"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** ve la analítica de LinkedIn de 7, 14, 28, 90 o 365 días, o de un rango suyo, comparada con el periodo anterior, sin esperar a LinkedIn.
- **Código:** `GET /api/v1/resultados/analitica?periodo=7d|14d|28d|90d|365d` o `?desde&hasta`, `cuenta` opcional; `analitica.overview`.
- **Criterios de aceptación:**
  1. **Dado** la consulta sin parámetros, **cuando** se pide, **entonces** responde los 28 días que terminan ayer (UTC), o el último día guardado si las importaciones van atrasadas, y el periodo anterior de la misma duración.
  2. **Dado** un periodo con todos sus días y un anterior también completo, **cuando** se pide, **entonces** impresiones, interacciones y seguidores nuevos traen valor, anterior y variación; si a alguno le faltan días, el valor se da con `days_with_data` y sin comparación.
  3. **Dado** un periodo que no coincide con un rango importado, **cuando** se pide, **entonces** los miembros alcanzados y las publicaciones principales de LinkedIn van en `null` con su motivo; nunca se suman por días ni se toman de otro rango.
  4. **Dado** la demografía del contenido, **cuando** se pide, **entonces** viene la del rango importado más cercano, con su propio rango y si es exacto.
  5. **Dado** una importación fallida después de la última correcta, **cuando** se pide, **entonces** la respuesta trae `ultimo_error` además de `actualizado`.
  6. **Dado** `periodo=30d`, `desde` sin `hasta`, una fecha que no es AAAA-MM-DD, más de 366 días o una `cuenta` que no es `directo`, **cuando** se pide, **entonces** responde 400.
  7. **Dado** un usuario sin `operate_linkedin`, **cuando** pide la analítica, **entonces** recibe 403.
  8. **Dado** cualquier consulta, **cuando** se responde, **entonces** no se llama a LinkedIn.
- **Brechas código/docs:** la app la muestra ([RES-12](#res-12)); la PWA aún no.
- **Cobertura QA:** pruebas de backend en `test_analitica.py` · la app la consulta en `movil/.maestro/08-resultados-linkedin.yaml` (RES-12)

### RES-12 · Ver la analítica de LinkedIn en la app <a id="res-12"></a>

- **Dónde:** app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** en Resultados, la pestaña «Analítica de LinkedIn» le muestra la analítica de su cuenta como la elige en LinkedIn: 7, 14, 28, 90 o 365 días, o un periodo suyo, con las cifras del periodo comparadas con el anterior, el día a día, los seguidores, sus publicaciones, las principales según LinkedIn y su público.
- **Código:** app `movil/src/resultados/AnaliticaLinkedin.tsx` (pestaña de `ResultadosScreen.tsx`, `?pestana=linkedin`); común `compartido/src/logic/analitica.ts`, `useAnalitica`; backend [RES-11](#res-11). La PWA aún no tiene esta vista.
- **Criterios de aceptación:**
  1. **Dado** Resultados, **cuando** toca «Analítica de LinkedIn», **entonces** la pestaña queda en la URL (`?pestana=linkedin`) y ve 28 días, «Del … al … · 28 días (UTC). Se compara con los 28 días anteriores.» y «Actualizado hace …».
  2. **Dado** «Periodo», **cuando** elige 7, 14, 90 o 365 días, **entonces** se pide ese periodo (`?periodo=7d…`), queda en la URL y las cifras anteriores se ven atenuadas mientras carga.
  3. **Dado** «Personalizado», **cuando** escribe «Desde» y «Hasta» (AAAA-MM-DD), **entonces** solo acepta días entre el primero y el último importados, «Desde» no posterior a «Hasta» y como mucho 366 días; si no, dice qué corregir y no pide nada. Si vale, pide `?desde&hasta` y ningún periodo fijo queda elegido.
  4. **Dado** un periodo con datos, **cuando** se muestra, **entonces** ve impresiones, interacciones, seguidores nuevos y tasa de interacción con su variación, o «sin comparación»; un dato que falta es «—» con su motivo, nunca 0.
  5. **Dado** un periodo que no es un rango exacto importado, **cuando** se muestra, **entonces** «Miembros alcanzados» y «Principales según LinkedIn» dicen por qué no hay dato, en vez de sumar días o tomar otro rango.
  6. **Dado** días sin importar en el periodo o en el anterior, **cuando** se muestra, **entonces** una nota dice cuántos días tienen datos y que no se compara.
  7. **Dado** el gráfico «Por día», **cuando** cambia de cifra o toca un día, **entonces** dibuja esa cifra (un día sin dato corta la línea) y dice el valor del día tocado; un lector de pantalla oye el total y el día con más.
  8. **Dado** sus publicaciones del periodo, **cuando** se muestran, **entonces** cada una lleva sus cifras «Desde que se publicó, al …», «—» en lo que LinkedIn no dio, «Ver en LinkedIn» y, si es una pieza del equipo, «Abrir la pieza».
  9. **Dado** «Público», **cuando** se muestra, **entonces** ve a sus seguidores con el día de la captura y a quienes vieron sus publicaciones con su propio rango, avisando si es el rango importado más cercano; «< 1 %» se muestra tal cual.
  10. **Dado** una importación fallida después de la última correcta, **cuando** abre la pestaña, **entonces** un aviso dice qué falló y cuándo, y que las cifras son de la última importación correcta.
  11. **Dado** que no hay cuenta «directo» o aún no se importó nada, **cuando** abre la pestaña, **entonces** ve solo «Aún no hay analítica de LinkedIn» con el motivo, sin controles ni cifras vacías.
  12. **Dado** que la consulta falla, **cuando** abre la pestaña, **entonces** ve «No se pudo cargar la analítica de LinkedIn» con «Reintentar».
- **Brechas código/docs:** la PWA no tiene esta vista. Las cifras son las que la importación guardó: la app nunca llama a LinkedIn.
- **Cobertura QA:** RES-12.1–9 en `movil/.maestro/08-resultados-linkedin.yaml` (`seed_qa --analitica`: 28, 7 y 90 días, personalizado rechazado y válido, gráfico, publicaciones, principales y público) · RES-12.11 en `08-resultados-errores.yaml` (sin cuenta «directo») · RES-12.10 y 12 sin prueba E2E (sí en `AnaliticaLinkedin.test.tsx`) · 2026-11-13 · pendiente del CI

## Retiradas

Ninguna.
