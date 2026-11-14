# Evaluaciones de los agentes

`manage.py evaluar` mide la calidad de los agentes con casos sacados del historial de producción. Es el punto «20–30 casos de evaluación por agente» de la fase 3 de la [auditoría de IA](auditoria-arquitectura-ia.md). Sin estas evaluaciones no se puede cambiar de modelo, mover umbrales ni quitar el panel de lectores con seguridad. Código: `team_backend/evaluaciones.py`.

## Ningún dato sale del servidor

- Los casos se arman al correr el comando, leyendo la base donde corre.
- No se exporta nada al repositorio ni se guardan conjuntos de datos.
- El informe sale por pantalla o, con `--salida`, a una ruta dentro del servidor.
- El informe lista identificadores, etiquetas, veredictos y motivos de las reglas, no textos de publicaciones ni nombres de personas.
- La corrida solo lee la base. Lo único que escribe son las filas del ledger de uso de las llamadas pagadas: no crea propuestas, trabajos ni piezas.

## Casos y calificación

El historial empieza el 6 de noviembre de 2026, cuando la máquina entró en producción; `--desde` lo cambia. Se usan como mucho `--limite` casos por agente (30), los más recientes primero.

| Agente | Caso | Contra qué se califica | Calificación |
| --- | --- | --- | --- |
| verificador | Piezas que llegaron a la compuerta con un destino conocido: publicada y no vetada, bloqueada, vetada por Gustavo o descartada por la política (no cuentan los descartes por hash o por capacidad apagada) | El texto de la selección (antes de cualquier reparación) vuelve a pasar la compuerta de producción: reglas deterministas (`editorial.text_rules`), verificador solo si pasan, una ronda de reparación con los hallazgos concretos y otra vez reglas y verificador. Su veredicto se compara con el destino: publicada → `ready_for_execution`; el resto → `blocked`. `--modelo` cambia el modelo del verificador; la reparación conserva el de producción | Acuerdo de la compuerta, acuerdo del verificador solo (su primer veredicto, cuando las reglas lo dejaron llegar), matriz de confusión, paradas por reglas, resultado de las reparaciones y esquema válido |
| comentarios | Publicaciones con un borrador del agente, con su destino: confirmado, aprobado, descartado por el líder (con motivos), descartado por las reglas, vetado o saltado | Se redacta un borrador nuevo. Si rompe una regla fija de texto, se reescribe una vez, como en producción. Al final se le aplican las reglas (`autopiloto.comment_text_issues`, sin el enfriamiento por autor) y las preguntas del líder (Jev) con sus umbrales | Pasa la compuerta, saltados, reescritos, viola reglas, el líder aprueba, mejoras y regresiones frente al destino original |
| clasificador | Personas clasificadas con una señal posterior. No encajan: Gustavo las descartó o vetó una acción, o el líder la descartó por `riesgo`. Encajan: aceptaron la invitación o comentaron con sustancia una publicación propia | Se reclasifica en lotes de 10, con el mismo corte de confianza que `red.classify` | Acuerdo de encaje frente a la línea base (lo que se decidió en su día) |
| lectores | Piezas con variantes, panel y selección guardados | Ablación: la selección se repite con el panel guardado y sin panel. La diferencia se compara con el ruido entre corridas (con panel frente a la selección guardada) | Cambio de decisión, ruido, similitud de textos y reglas violadas. El veredicto dice si el panel cambia la selección más que el ruido; con menos de 20 casos es solo orientativo |
| director | Días con pieza escrita o saltada | Descriptivo: no hay un desenlace correcto conocido, así que no se llama al modelo ni hay juez | Días, saltos, mezcla de pilares y modalidades, destino de lo escrito y métricas (24 h, 72 h, 7 días) por pilar y modalidad cuando existen |

En comentarios, `--catalogo` elige las unidades del curso que recibe el borrador: por defecto, las que carga producción (el núcleo del catálogo activo para «comentar» o, si no hay, la lista fija); `--catalogo fijas` fuerza la lista fija, y `--catalogo <versión>` mide una versión cargada en sombra, sin activarla. El informe dice qué unidades usó. Ver [catálogo de la biblioteca](catalogo-biblioteca.md).

Las calificaciones son deterministas: tasas de acuerdo, validez del esquema y violaciones de las guardas. Las preguntas del líder en los comentarios son la compuerta de producción, no un juez externo. `--sin-lider` las quita. No hay un juez de modelo; si se añade, irá detrás de su propia bandera.

Las respuestas inválidas no se ocultan: el esquema se valida aparte, y un caso que falla queda como error con su motivo.

**Límites:**

- Las respuestas del inbox no se observan hasta que exista el agente de inbox.
- El borrador nuevo de un comentario no ve los comentarios existentes, porque no se lee LinkedIn. Tampoco pasa por el prefiltro de Jev (R5): el caso ya es una publicación que lo pasó.
- La memoria y la orientación son las de hoy, no las del día del caso.

## Ensayo (por defecto): gratis

```bash
docker compose -f compose.prod.yaml --env-file .env exec api python manage.py evaluar
```

Imprime, por agente:

- los casos encontrados por etiqueta;
- lo que falta para 20 y para 30;
- la línea base, cuando la hay;
- el coste estimado de una corrida con cada modelo de `knowledge/providers.py` (y Jev para el clasificador);
- para el verificador, «Repetición de la compuerta del post»: las reglas y la severidad actuales
  ([`compuertas.md`](compuertas.md)) aplicadas a los veredictos ya guardados, sin pagar. Dice cuántos casos coinciden
  con lo que pasó, qué bloqueadas pasarían ahora (con sus observaciones), qué duras siguen bloqueando, las etiquetas de
  Gustavo y en cuántos cambió el contexto desde entonces. Un caso sin veredicto guardado no se repite. La corrida
  pagada (`--ejecutar`) hace además la segunda revisión acotada tras la reparación, como producción.

Todo sin llamar a la API. Es una **estimación**:

- La entrada se cuenta con tiktoken (cl100k) ×1,2, porque el tokenizer de Claude cuenta un 15–20% más.
- La entrada se cobra como escritura de caché (1,25×), igual que la reserva de `providers.claude`.
- La salida es la media del ledger para el propósito de producción (`editorial-verificador`, `editorial-seleccion`, `propose-comment`, `network-classify`) o, sin historial, un valor por defecto.

Opciones: `--agentes verificador,lectores`, `--desde 2026-11-06`, `--limite 30`, `--json` y `--salida /tmp/evaluacion.json`. La ruta de `--salida` es la del contenedor.

## Ejecución: pagada

```bash
docker compose -f compose.prod.yaml --env-file .env exec -e EVAL_LIMIT_USD=25 api \
  python manage.py evaluar --ejecutar --max-usd 20 [--modelo claude-sonnet-5-5 --modelo claude-opus-5-5]
```

- `--ejecutar` exige `--max-usd`. La corrida se detiene antes de cualquier llamada que, en el peor caso (todo `max_tokens`, como la reserva del proveedor), pudiera superar ese tope, y el informe dice dónde paró.
- `EVAL_LIMIT_USD` es el presupuesto mensual de las evaluaciones: suma lo gastado en el mes con propósito `eval-*`. Vale 0 por defecto, así que nada se paga hasta fijarlo.
- Todas las llamadas pasan por `providers.claude` y `providers.typesafe`, con propósito `eval-verificador`, `eval-comentarios`, `eval-clasificador` o `eval-lectores`. Quedan en el ledger y cuentan en el presupuesto de IA de todo el equipo (`AI_MONTHLY_LIMIT_USD` y el tope de seguridad diario `AI_DAILY_FUSE_USD`, 15 USD por defecto, que también las frena), y en `ANTHROPIC_LIMIT_USD` y `TYPESAFE_LIMIT_USD` si están fijados. Lo que gasta una evaluación ya no queda para producción ese mes.
- `--modelo` (repetible) compara modelos, la palanca C3 de la auditoría. Sin `--modelo` se usa el de producción de cada agente. `--modelo jev` evalúa el clasificador con Jev: la pregunta de riesgo del líder más una de encaje propia (desde R2 el líder ya no pregunta el encaje).

## Coste esperado

Calculado con los tamaños reales de las unidades del curso y los prompts:

| Agente | Por caso (Opus 5.5, salvo el clasificador) | 30 casos |
| --- | --- | --- |
| verificador | ~$0,13 (≈10k de entrada, 4k de salida), más una reparación y otra verificación cuando hacen falta | ~$4 |
| comentarios | ~$0,13 más ~$0,0002 de Jev, y otro tanto si el borrador se reescribe | ~$4 |
| clasificador (Sonnet 5.5) | ~$0,05 por lote de 10 | ~$0,15 |
| lectores (dos selecciones por caso) | ~$0,40 | ~$12 |
| director | $0 | $0 |

Una corrida completa con los modelos de producción ronda los **$20** (estimación conservadora). Con Sonnet 5.5 cuesta la mitad, y con Haiku 5.5 unas 40 veces menos.

Con el historial corto de hoy hay muchos menos casos y cuesta unos pocos dólares; el ensayo da la cifra exacta para la base del servidor. Para que una corrida completa no se corte, `--max-usd` necesita margen sobre el gasto real (el peor caso de una llamada a Opus con 16k de `max_tokens` es ~$0,40).

## Mantenimiento

Las peticiones reproducen las llamadas de producción: `editorial._stage`, `_check` y `_repair_round`, `operador.propose_comment` y `_draft_comment`, `red.classify` y `lider.review`. `tests/test_evaluaciones.py` compara el sistema, el mensaje, el esquema, `max_tokens` y `effort` con las llamadas reales, y falla si un cambio de producción no llega aquí. El [mapa de agentes](mapa-agentes-runtime.md) describe qué corre por rol.
