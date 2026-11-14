# Compuertas: qué frena el trabajo del equipo, cuánto, y cómo se reintenta

Gustavo, 14/11/2026: «el verificador es demasiado rígido… busca una manera de auditarlo… que no nos bloquee tanto, y si
nos bloquea buscar una manera de reintentar… no digo que lo quitemos… tampoco iteraciones infinitas: al menos que en la
segunda revisión ya pase, de haber corregido lo que bloqueó… que esto sea sostenible».

Este documento reúne las compuertas que pueden parar una pieza, un comentario o una acción de red; cuáles bloquean siempre
y cuáles dejan pasar con una observación; la escalera de reintentos con sus topes y su coste; y cómo se audita todo sin
llamar a modelos. Código: `team_backend/compuertas.py` (severidad, segunda revisión y segundo intento) y
`team_backend/auditoria_compuertas.py` (auditoría y aviso).

## Qué cambia y qué no

- **Cambia.** El verificador del post ya no bloquea por calidad: un gancho que no cumple, una pieza fuera del brief u
  `other` pasan por la ronda de reparación y, si siguen, la pieza sale con esos hallazgos «conservados como
  observación». La segunda revisión, tras la reparación, comprueba lo que se corrigió y solo marca problemas graves
  nuevos. Un día que una compuerta de contenido bloqueó tiene un segundo intento. Un comentario que el líder descartó se
  reescribe una vez con sus razones.
- **No cambia.** Experiencias inventadas, cifras o afirmaciones sin respaldo, datos privados, fugas de la guía privada,
  pitch agresivo, las reglas fijas y las fuentes web siguen bloqueando siempre, en cualquier revisión. Los criterios de
  la red (el clasificador y el riesgo que juzga el líder) no se tocan. La versión de una pieza que Gustavo comentó nunca
  sale sin él ([EDI-22](../../../docs/funcionalidades/motor-editorial.md#edi-22)). Sin `gate_policy` en el brief, la
  publicación se comporta como antes respecto al contacto: ninguna petición de contacto pasa.

## Inventario de compuertas

| Compuerta | Código | Qué para | Qué pasa después |
| --- | --- | --- | --- |
| Reglas fijas del post | `compuertas.form_rules` (`editorial.text_rules` antes del verificador; `autopiloto.post_issues` como compuerta final) | longitud, correo, teléfono, enlaces, pitch, hashtags; más `guardas.private_leaks` e `invented_experience` | ronda de reparación; si sigue, `blocked` (dura) |
| Fuentes web | `research.source_issues` | afirmación web sin fuente guardada o con ref inventada | dura |
| Verificador del post | `editorial._check`, `VERIFIER_SYSTEM` | hallazgos `material` y afirmaciones `unsupported` | según severidad (abajo) |
| Ronda de reparación | `editorial._repair_round` | una por pieza | segunda revisión acotada |
| Revisión visual | `editorial._visual`, `editor_visual` | imagen que no pasa | `blocked` («Pieza bloqueada: imagen»); cuenta como compuerta para el segundo intento |
| Política CONT-09 | `autopiloto.policy_review` | reglas otra vez, veredicto sobre el hash exacto, citas | `discarded` |
| Líder CONT-09 (Jev) | `lider.review` | `clara`, `pitch`, `inventa`, `idioma`, `orientacion` | `discarded`; Gustavo puede desestimarlo ([EDI-23](../../../docs/funcionalidades/motor-editorial.md#edi-23)) |
| Retoque | `retoque.py` | texto o foto rehechos que no pasan | `blocked`; no se reintenta solo |
| Prefiltro de comentarios | `autopiloto._prefilter`, `lider.comment_worthy` | posts donde comentar es ruido | se salta el post |
| Reglas del comentario | `autopiloto.comment_text_issues` | longitud, pitch, enlaces, hashtags, afirmaciones sin evidencia, idioma, privacidad | una reescritura (R4) |
| Líder INT-03 (Jev) | `lider.review` | `aporta`, `pitch`, `inventa`, `respeto`, `orientacion` | una reescritura con sus razones |
| Red RED-01/02/04 | `red.classify`, `red.network_issues`, líder (`riesgo`) | quién encaja y el riesgo | sin cambios: criterio estricto de Gustavo; su «Sí, encaja» levanta la duda del líder |
| Dinero | `knowledge/presupuesto.py`, `cost_cap` del ciclo | presupuesto agotado | espera; se reintenta al haber presupuesto, no cuenta como intento |

## Severidad del verificador

`compuertas.split` decide sobre lo que devuelve el verificador. Una afirmación `unsupported` y un `blocked` sin hallazgos
concretos son duros siempre.

| `issue` | Severidad | Por qué |
| --- | --- | --- |
| `invented_experience` | dura | atribuye a Gustavo algo que no vivió |
| `unsourced_figure` | dura | una cifra sin fuente es un hecho falso posible |
| `unsupported_claim` | dura | un hecho sin respaldo |
| `private_data` | dura | expone a personas |
| `private_guidance_leak` | dura | expone sus prioridades privadas |
| `aggressive_pitch` | dura; blanda solo con `gate_policy.cta_max=1` | venta y petición de contacto; la regla fija sigue parando la venta dura |
| `hook_not_delivered` | blanda | calidad: la ronda la intenta arreglar; si no, sale como observación |
| `off_brief` | blanda | calidad |
| `other` | blanda | solo calidad; el prompt manda los problemas graves a su categoría |
| `unsourced_third_party_story` | dura | estrategia (P): la historia de un founder no está en una fuente guardada |
| `fabricated_quote` | dura | estrategia (P): una cita entre comillas que no está literal en la fuente |
| `first_person_appropriation` | dura | estrategia (P): la historia ajena contada como de Gustavo o sin atribuir |
| `cta_count` | blanda | estrategia: más de una llamada a la acción en S, o alguna en P |
| `offer_in_growth`, `offer_in_personal` | blanda | estrategia: ofrece servicios en un post G o P |
| `no_reader_need`, `repeated_story` | blanda | estrategia: lo decidió el brief; viajan solo como riesgo «Estrategia: …», sin ronda |

Los códigos de la estrategia semanal (`compuertas.STRATEGY_CODES`, `estrategia.findings` y `notes`) están en esta misma
tabla (`compuertas.HARD`/`SOFT`): no hay otra. El código los busca en el texto exacto antes del verificador
(`editorial.strategy_issues`): los duros paran el texto como una regla fija y no se paga el verificador; los blandos se
suman a la revisión del verificador como hallazgos `material` marcados `by: "codigo"` (`compuertas.with_code_findings`),
pasan por la ronda de reparación (`source: "estrategia"`) y, si siguen, salen como observación. Un `blocked` del modelo
sin hallazgos propios sigue siendo duro aunque el código haya añadido los suyos.

`COMPUERTAS_DURAS=other,off_brief` vuelve duras más categorías si la auditoría muestra que salen piezas que no deberían.
Un hallazgo `minor` nunca bloquea (como antes). El prompt del verificador dice ahora que solo un **hecho** sin respaldo es
material; las opiniones, el criterio, los razonamientos, las preguntas y la voz de Gustavo no lo son, y «I think…» no es
una anécdota («last week I…» sí). Ante la duda en un hallazgo de calidad, `minor`.

Lo blando queda en `verification.observations` y en los riesgos de la propuesta («Conservada como observación (issue):
…»); el detalle de la pieza lo muestra en «Cómo se escribió».

## Escalera de reintentos

| Peldaño | Tope | Coste en llamadas |
| --- | --- | --- |
| Ronda de reparación (post) | 1 por pieza (`EDITORIAL_REPAIR`) | 1 reparación + 1 verificador (ya existía; ≈ 0,2–0,3 USD con opus) |
| Segunda revisión acotada | es ese segundo verificador | 0 llamadas más: solo añade los hallazgos y los cambios a su entrada (`second_review`), unos cientos de tokens |
| Segundo intento del día | `EDITORIAL_DAY_ATTEMPTS=2` piezas por día; solo si quedan `EDITORIAL_RETRY_MIN_MINUTES` (90) antes de su hora | una preparación completa (≈ 0,4–0,5 USD de texto con opus, más la imagen); no empieza con menos de `EDITORIAL_PREPARE_MIN_USD` (3 USD) |
| Reescritura por reglas (comentario, R4) | 1 por borrador | 1 borrador de Claude |
| Reescritura con las razones del líder (comentario) | 1 por post: un post con dos borradores no se reescribe más | 1 borrador de Claude + 1 revisión de Jev; cuenta en `OPERATOR_DAILY_PROPOSALS` |
| Dinero | sin tope: espera al presupuesto | no cuenta como intento |

Nunca hay más de dos verificaciones por pieza (la arista `verificar` de `grafo.yaml` admite dos por ciclo), dos piezas de
contenido por día ni dos borradores por post comentado (tres si el primero tuvo además la reescritura por reglas). El peor caso diario del post pasa de una preparación a dos (≈ +0,5 USD de texto); con los ≈ 13–15 USD al
mes de una pieza diaria, un segundo intento cada día sumaría como mucho otros tantos, y el tope de seguridad diario
(`AI_DAILY_FUSE_USD`) sigue mandando.

### Segunda revisión acotada

Tras la reparación, el verificador recibe `second_review: {previous_findings, changes}`. Comprueba primero si cada
hallazgo anterior quedó resuelto y solo marca como material lo que sigue en el texto o un problema grave nuevo. El código
decide igual que en la primera: bloquean solo los duros. `verification.repair.resolution` guarda, por hallazgo, si quedó
resuelto (por regla exacta, por `issue` o por afirmación), sin llamar a nadie más. Si la reparación descarta la pieza o
no cambia nada, se queda el texto original y sus hallazgos blandos salen como observación.

### Segundo intento del día

`compuertas.gate_blocked(pieza)`: `blocked` por las reglas, el verificador o la revisión visual mientras se preparaba.
No cuentan el dinero, un ciclo detenido, una preparación interrumpida ni un retoque fallido (el comentario de Gustavo
manda). Si la última pieza del día es así, quedan intentos y tiempo, `editorial.next_slot` vuelve a dar ese día y el
director recibe `previous_attempts` (tesis, pilar, enfoque, categorías y motivos del intento bloqueado) para no repetir lo
que lo paró, o saltar el día. El aviso `piece_blocked` añade «Habrá un segundo intento para ese día.» cuando lo habrá.
`verification.day_attempt` dice qué intento fue. Solo el autopiloto reintenta; una pieza con `second_of_day` no.

## `gate_policy`: lo que un tipo de post puede permitir

`compuertas.gate_policy(pieza)` lee `brief['gate_policy']`, que pone el tipo de post (nunca el modelo):
`estrategia.finalize_brief` lo fija con el tipo GASP del día, `{"cta_max": 1}` en venta (S) y `{"cta_max": 0}` en los
demás; en un post extra que Gustavo pidió con fecha, solo si su propia idea se clasificó como venta. Lo leen las reglas
fijas, el verificador, la compuerta final (`autopiloto.post_issues`) y la pregunta `pitch` del líder para CONT-09, que en
un post de venta no cuenta una sola invitación a conversar. Hoy solo admite
`{"cta_max": 0|1}`: con 1, una sola invitación conversacional («DM me», «escríbeme», `autopiloto.POST_CTA`) pasa en las
reglas fijas y en el verificador; la venta dura («hire me», «book a call», «buy now», `autopiloto.POST_SELL`) sigue
parando, y dos invitaciones también. Sin política, `{"cta_max": 0}` y todo
como antes. El verificador recibe `gate_policy` solo cuando difiere del valor por defecto, así que la entrada por
defecto no cambia.

## Auditoría

`python manage.py compuertas auditar --dias 7 [--json]` lee lo guardado (piezas, propuestas y eventos de auditoría) y
no llama a modelos ni escribe. Solo saca ids y categorías: nunca un texto, una cita ni un nombre.

```
Auditoría de compuertas · 7 días (2026-11-07 → 2026-11-13). Solo ids y categorías.

Verificador del post: 6 entraron · 3 a la primera · 2 tras reparar o reintentar · 1 paradas (17 %) · 0 en espera
  Salieron con observaciones: 2
  Motivos: unsourced_figure 1
  Ejemplos: <id> (unsourced_figure)
  Gustavo: paradas 1, no estuvo de acuerdo en 1 · vetó 0 de las que pasaron
Líder (Jev) · INT-03: 9 entraron · 5 a la primera · 1 tras reparar o reintentar · 3 paradas (33 %) · 0 en espera
  Motivos: aporta 2 · orientacion 1
  Descartes sin reescritura: 0

Días sin post: 1 (compuerta:verificador 1)
  2026-11-10 · compuerta:verificador · pieza <id> · 2 intento(s)
Callejones sin salida (una compuerta paró el día y nadie lo reintentó ni desestimó): 1
Segundo intento: 2 día(s), con post al final en 1.
Red: «Sí, encaja» tras una duda del líder 0 · personas que descartaste 0.
```

- **Por compuerta:** entraron, pasaron a la primera, pasaron tras reparar o reintentar, paradas, en espera, tasa de
  parada, con observaciones, motivos (categorías) y hasta 5 ejemplos (id y categoría).
- **La palabra de Gustavo como etiqueta:** «Desestimar el bloqueo» (`editorial.block_overridden`) cuenta como «no estuvo
  de acuerdo» con la compuerta que paró; «Sí, encaja» tras una duda del líder, igual para la red; un veto de algo que
  pasó cuenta como «vetada tras pasar».
- **Días sin post** con su causa (`sin_pieza`, `saltada_por_el_director`, `dinero`, `fallo`, `compuerta:<nombre>`,
  `vetada_por_ti`, `caducada`, `incierta`, `sin_publicar`) y los **callejones sin salida**: días que paró una compuerta
  sin reintento ni desestimación.
- **Resumen semanal:** `resumen_semanal` guarda la vista de la semana sin ids en `compuertas`.
- **Aviso `gate_alert`** (capa sistema): uno por compuerta y semana si su tasa de parada a 7 días llega a
  `COMPUERTAS_ALERTA_TASA` (0,5) con al menos `COMPUERTAS_ALERTA_MIN` (4) decisiones, y uno por cada día de ayer que una
  compuerta dejó sin post. No se avisa de la reparación, el prefiltro, el dinero ni los fallos (tienen sus propios
  avisos o no miden rigidez). `COMPUERTAS_ALERTAS=false` los apaga. Corre con la comprobación del silencio del líder.

### Repetir la compuerta sin pagar

`python manage.py evaluar --agentes verificador` añade «Repetición de la compuerta del post»: aplica las reglas y la
severidad actuales a los veredictos guardados, sin llamar a modelos. Dice cuántos casos coinciden con lo que pasó, cuántos
bloqueados pasarían ahora (con sus observaciones), qué duros siguen bloqueando, las etiquetas de Gustavo y en cuántos el
contexto (hechos, guía, orientación) cambió desde entonces (`verification.context`). Para volver a preguntar al
verificador con el prompt nuevo hace falta la corrida pagada de siempre (`--ejecutar --max-usd N`), que ahora incluye la
segunda revisión.

## Variables de entorno

| Variable | Por defecto | Qué hace |
| --- | --- | --- |
| `EDITORIAL_DAY_ATTEMPTS` | 2 | piezas de contenido por día como máximo (1 apaga el segundo intento) |
| `EDITORIAL_RETRY_MIN_MINUTES` | 90 | margen mínimo antes de la hora para el segundo intento |
| `COMPUERTAS_DURAS` | vacío | categorías del verificador que también bloquean siempre |
| `COMMENT_LEAD_REDRAFT` | true | reescritura de un comentario con las razones del líder |
| `COMPUERTAS_ALERTA_TASA` | 0.5 | tasa de parada a 7 días que dispara `gate_alert` |
| `COMPUERTAS_ALERTA_MIN` | 4 | decisiones mínimas para ese aviso |
| `COMPUERTAS_ALERTAS` | true | false apaga los avisos `gate_alert` |

`EDITORIAL_REPAIR`, `EDITORIAL_PREPARE_MIN_USD` y los del líder siguen como en
[`publicacion-diaria.md`](publicacion-diaria.md) y [`operador-linkedin.md`](operador-linkedin.md).

## Pendiente

- Un post que descarta el líder (CONT-09) no se reintenta solo: Gustavo lo rescata con «Pedir un cambio» o «Desestimar el
  bloqueo». Las respuestas INT-04 tampoco tienen reescritura por el líder.
- Una pieza detenida por dinero a mitad del circuito vuelve a empezar desde el director, no desde la etapa en que paró.
- Una pieza detenida por el techo opcional de un proveedor (`<PROVEEDOR>_LIMIT_USD`), que el presupuesto general no ve,
  cuenta como parada por dinero: el hueco de una idea con fecha (`urgente.next_slot`) puede volver a prepararse en
  ciclos sucesivos del mismo día. No se cambió porque ese reintento el mismo día está probado y es intencionado para el
  presupuesto general.
