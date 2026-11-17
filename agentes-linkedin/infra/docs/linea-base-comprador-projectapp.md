# Línea base del comprador de ProjectApp (BAR-25-comprador-projectapp)

Medición del estado actual **antes** de añadir el comprador de ProjectApp, el segmento y el papel `partner`, por la
estrategia que Gustavo aprobó el 17/11/2026: «se verticaliza a quién se le escribe y con qué prueba, no el feed».

- **Fecha:** 17/11/2026. Rama `feat/comprador-projectapp`, código en `6508245` (`origin/main`, con BAR-24 y el outbound).
- **Entorno:** PostgreSQL desechable propia con pgvector (puerto 55492; no el runtime ni producción), Python 3.12,
  `LIVE_PROVIDERS=false`. Claude simulado (clasificador y juez de etapa), investigación web simulada, conector de LinkedIn
  simulado, unidades del curso sintéticas.
- **Caso:** `evaluaciones.PROJECTAPP_CASE`, ocho personas sintéticas (ninguna real). **Prueba:**
  `src/team_backend/tests/test_comprador_projectapp.py`, con las funciones de producción: clasificación (`red.classify`),
  verificación web durante tres días (`red.check_stages`) y dos ciclos del plan de invitaciones (`red.plan`, cinco
  invitaciones por ciclo como fija `politica_red`).
- **Qué responde el modelo simulado:** con el prompt de BAR-24 (el vigente), lo que ese prompt pide para cada perfil,
  leído regla por regla (`antes`): un founder o ejecutivo que decide es un comprador de tipo startup; quien vende
  servicios a otro público que no son founders queda `fit=false`; una directora de una empresa grande es «ejecutivo». No
  se midió con el modelo real (sería una corrida pagada). Con el prompt nuevo, lo que el prompt nuevo pide (`despues`).
- **Cómo se midió:** `manage.py test team_backend.tests.test_comprador_projectapp` sobre el código de `6508245`.

## Lo que se sabe de producción (sin leer producción)

Lo dice el pedido del 17/11/2026: las cinco búsquedas de producción son `founder seed startup;cofounder startup AI;CTO
startup;fundador startup [es];cofundador SaaS [es]` (`red.NETWORK_SEARCH_QUERIES`), el vecindario de `projectapp` es
vago («founders u operadores que necesitan una entrega externa, un proyecto definido o un equipo continuo») y de 39
compradores recuperables casi todos son founders de startups de IA. Esta línea base no consultó producción.

## Resultado por variante (código de `6508245`)

| Variante | Perfil | Esperado | Observado | Dónde se pierde |
| --- | --- | --- | --- | --- |
| P1 | CTO de una cadena de retail de 80 personas en Texas que publica vacantes de ingeniería | Comprador ProjectApp, líder de tecnología, retail, `probable`/`confirmado`, puntaje alto | Comprador `probable` (82), sin línea, sin segmento, sin papel | El clasificador solo conoce compradores de startup (`ejecutivo`); no hay línea ni segmento. |
| P2 | Dueña de una academia en línea de 30 personas en Miami, titular en español | ProjectApp, educación en línea (coincide con dueños latinos), `por_confirmar` | Comprador `por_confirmar` (59) | Sin línea, segmento ni papel; la coincidencia con «dueños latinos» no existe. |
| P3 | Dueño de un negocio de plomería de 5 personas | ProjectApp, puntaje bajo, no expulsado | Comprador `por_confirmar` (59), **empata** con P2 | El puntaje v1 no mira el tamaño de la empresa. |
| P4 | Directora de TI de una multinacional de 20.000 empleados | Fuera (caso claro) | **Sigue**, `probable` (70), se invita antes que P2 y P3 | Nada mira el tamaño: un «ejecutivo» de una empresa grande sube. |
| P5 | Fundador de una agencia de marketing que subcontrata desarrollo | `partner`, se sigue, se comenta y se invita como comunidad | **Sale** (`aliado`, `fit=false`) | El prompt descarta a quien vende servicios a otro público que no son founders; no existe el papel `partner`. |
| P6 | Agencia de desarrollo de software | `par` (competidor), nunca partner ni comprador | `par` | Correcto. |
| P7 | Cofundadora de una startup con ronda semilla | Comprador línea startup, `confirmado` | Comprador `confirmado` (99), sin línea | No hay línea: el comprador de startup no se distingue del de ProjectApp. |
| P8 | CFO fraccional para startups semilla | `aliado` | `aliado` | Correcto. |

Invitaciones a compradores de ProjectApp, en orden: esperado P1, P2, P3; observado **P1, P4, P2, P3** (la multinacional
se cuela en segundo lugar).

## Calificación del caso

```
grade_projectapp_case: passed False
errors: P1:line, P1:segment, P1:papel, P2:line, P2:segment, P2:papel, P2:also, P3:line, P3:segment, P3:papel,
        P3:score_bajo, P4:kept, P5:kept, P7:line, order
right: 2/8
```

## Cómo queda marcada la prueba

La prueba `test_antes_the_case_shows_where_the_buyer_of_today_is_only_a_startup_buyer` fija estos errores exactos. Después
del cambio sigue corriendo con `NETWORK_PROJECTAPP_BUYER_ENABLED=false`: si el interruptor apagado da otra cosa que esta
línea base, el apagado ya no es el comportamiento de hoy y la prueba falla.
