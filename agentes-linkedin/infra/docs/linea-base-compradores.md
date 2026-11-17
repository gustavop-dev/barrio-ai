# Línea base de los compradores (BAR-24-compradores)

Medición del estado actual **antes** de cambiar el clasificador, la verificación web y el plan, a pedido de Gustavo
(17/11/2026: «Siento que puede ser demasiado estricto, o que el verificador hace una pregunta demasiado rígida y no deja
pasar a nadie»).

- **Fecha:** 17/11/2026. Rama `fix/compradores-menos-rigido`, código en `d8f7a6c` (`origin/main`).
- **Entorno:** PostgreSQL desechable propia con pgvector (puerto 55491; no el runtime ni producción), Python 3.12,
  `LIVE_PROVIDERS=false`. Claude simulado (clasificador y juez de etapa), investigación web simulada, conector de LinkedIn
  simulado, unidades del curso sintéticas.
- **Caso:** `evaluaciones.BUYERS_CASE`, siete personas sintéticas construidas con los veredictos medidos en producción el
  17/11/2026 (anonimizados: ni nombres, ni empresas, ni perfiles reales). **Prueba:**
  `src/team_backend/tests/test_compradores_niveles.py`, con las funciones de producción: clasificación (`red.classify`),
  verificación web de la etapa durante tres días (`red.check_stages`) y plan de invitaciones (`red.plan`).
- **Qué responde el modelo simulado:** con el prompt de producción del 12/11/2026, lo que el modelo real respondió para ese
  tipo de perfil (`antes`); con el prompt nuevo, lo que el prompt nuevo pide (`despues`). La prueba mide qué hace el código
  con cada respuesta; cómo responde el modelo real solo se mide con una corrida pagada.
- **Cómo se midió:** `manage.py test team_backend.tests.test_compradores_niveles` sin el marcador de fallo esperado.

## Medido en producción (solo lectura, 14 días al 17/11/2026)

- 53 personas clasificadas `comprador`: 45 con `fit=false` (85 %), 8 con `fit=true`. Los motivos son casi siempre ausencia
  de evidencia («sin evidencia de ronda semilla ni clientes que pagan»), no evidencia en contra.
- La verificación web completó **un** veredicto en 8 días (`semilla_o_mas`). Cuatro compradores de EE. UU. que encajan
  seguían en `pending` desde el 13–14/11 con «Sin hallazgos de la web todavía; se reintenta mañana», un intento al día
  justo después de medianoche; al tercero sin hallazgos el veredicto pasa a `sin_evidencia` y la persona sale del barrio.
- Cuatro compradores de Latinoamérica seguidos nunca se invitan, y el clasificador descarta a otros con la regla
  «Comprador fuera de EE. UU.».
- Reparto de las invitaciones: par 53 %, aliado 26 %, comprador 9 %, divulgador 6 %, recomendador 6 %.

## Resultado por variante (código de `d8f7a6c`)

| Variante | Perfil | Esperado | Observado | Dónde se pierde |
| --- | --- | --- | --- | --- |
| C1 | Co-founder y CTO en Nueva York, stealth, una salida previa | Sigue (`probable` o `por_confirmar`) | **Sale** | El clasificador da `fit=false` («la tracción actual es una hipótesis»), porque el prompt exige ronda o clientes visibles. |
| C2 | «Founder @Lumora» en San Francisco | Sigue (`por_confirmar`), aviso de perfil escueto | **Sale** | Igual que C1: «sin evidencia de ronda semilla ni clientes que pagan». |
| C3 | Founder de un SaaS bootstrapped con clínicas que pagan | Sigue (`confirmado` o `probable`) | **Sigue**, sin nivel ni puntaje | La web cita clientes que pagan: `semilla_o_mas`. |
| C4 | Cofundadora y CEO de una fintech en Bogotá | Sigue, con prioridad baja | **Sale** | `_classify_batch` la descarta con «Comprador fuera de EE. UU.». |
| C5 | Director de ventas enterprise de una empresa grande | Sale | Sale | Correcto. |
| C6 | Pide que no lo contacten | Sale | Sale | Correcto. |
| C7 | Presemilla declarada, sin ingresos | Sale | Sale | Correcto. |

Invitaciones planeadas, en orden: esperado C3, C1, C2, C4; observado **solo C3**.

Segunda medición, con el modelo simulado respondiendo ya `fit=true` a C1 y C2 (como pediría el prompt nuevo) sobre el
código viejo: igual salen los dos, al tercer día, con «Sin ronda semilla o clientes visibles en la web: no es comprador»
(`check_stages` convierte «sin hallazgos» en `sin_evidencia` → `failed`). Es decir, cambiar solo el prompt no basta: la
verificación web también descarta por ausencia de evidencia.

## Calificación del caso

```
grade_buyers_case: passed False
errors: C1:kept, C2:kept, C3:level, C3:score, C4:kept, order
kept_right: 4/7
```

## Cómo queda marcada la prueba

En el commit de la línea base la prueba lleva `@expectedFailure`. El marcador se quita con el cambio de los niveles, la
región y el puntaje (sección «Después», abajo).

## Después (17/11/2026, rama `fix/compradores-menos-rigido` con `origin/main` mezclado)

El caso es el mismo y corre con las mismas funciones de producción y los mismos modelos simulados. Lo que cambia es el
código: el prompt del clasificador con perfil, nivel y `us_market`, la pregunta a la web según el perfil, los cuatro
niveles, el puntaje `buyer_score_v1` y la región que ordena sin sacar. El identificador pasó de BAR-18 a **BAR-24**
porque `main` usa BAR-18 para el recorrido del comprador (outbound, fase 1).

```
grade_buyers_case: passed True
errors: (ninguno)
kept_right: 7/7
```

| Variante | Antes | Después | Nivel | Puntaje | Desglose (evidencia + mercado + papel + servicios + confianza) |
| --- | --- | --- | --- | --- | --- |
| C1 stealth con salida previa | Sale | **Sigue** | probable | 82 | 33 + 20 + 12 + 12 + 5. La web no encontró nada en tres días: el nivel del perfil se mantiene. |
| C2 «Founder @Lumora» | Sale | **Sigue** | por_confirmar | 62 | 16 + 20 + 12 + **9 (sin dato)** + 5, con el aviso «perfil con poca información»; no pierde puntos. |
| C3 bootstrapped con clientes | Sigue, sin nivel | Sigue | confirmado | 99 | 50 + 20 + 12 + 12 + 5. La web cita clientes que pagan. |
| C4 founder en Bogotá | Sale | **Sigue**, después | por_confirmar | 53 | 16 + **8 (Latinoamérica)** + 12 + 12 + 5. |
| C5 director de ventas | Sale | Sale | no_encaja | — | Evidencia en contra: vende, no decide. |
| C6 pide no ser contactado | Sale | Sale | no_encaja | — | Evidencia en contra. |
| C7 presemilla declarada | Sale | Sale | no_encaja | — | Evidencia en contra. |

- **Invitaciones planeadas, en orden:** C3, C1, C2, C4, las cuatro esperadas. Antes solo se invitaba a C3.
- **Con todos los `BUYER_*_ENABLED` apagados:** el resultado es el mismo y no se escribe ningún recorrido
  (`test_with_every_buyer_switch_off_the_case_is_the_same_and_nothing_is_recorded`).
- **Con `BUYER_RECORD_ENABLED`** (encendido por defecto): cada uno de los cuatro que siguen tiene su recorrido.
- **Cómo se midió:** `manage.py test team_backend.tests.test_compradores_niveles`, sin marcador de fallo esperado.
- **Lo que esto no mide:** cómo responde el modelo real con el prompt nuevo (haría falta una corrida pagada) ni cuántos
  compradores reales cambian de nivel. Eso lo dice `manage.py operador reevaluar-compradores` en seco, en producción.
