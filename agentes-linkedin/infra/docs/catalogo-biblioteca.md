# Catálogo de la biblioteca

Las 1.035 unidades del curso (clases 01–06) se organizan en **estantes**, uno por tarea de agente, y dentro de cada estante en tres **niveles**:

| Nivel | Qué es | Cuándo se carga |
| --- | --- | --- |
| Núcleo | Pautas generales y accionables para casi cualquier caso de esa tarea, sin repetirse entre sí | En cada llamada del agente. Tope de 16.500 tokens (6–8 unidades completas) |
| Consulta | Pautas que sirven en ciertos casos: un formato, un tema, un tipo de persona | Cuando la tarea lo pide (búsqueda por tarea, fase 3) |
| Referencia | Casi duplicados, casos de un participante, cosas que Gustavo no hace o pautas poco aplicables | No se carga; sigue en la biblioteca |

Estantes: `cliente`, `perfil`, `elegir`, `conectar`, `comentar`, `responder`, `privado`, `temas`, `redactar_post`, `editar`, `analizar`. Las unidades de logística del curso no tienen estante de agente.

**Por qué importa el tamaño.** Una unidad cuesta unos 2.500 tokens tal como la carga el agente (texto, fuentes y relaciones), y como las llamadas están separadas, la caché del proveedor casi nunca se reutiliza: cada token se paga completo.

## El contenido no está en este repositorio

El curso es privado y este repositorio es público. El catálogo (qué unidades van en qué estante y nivel) llega desde un archivo privado con `manage.py catalogo cargar` y vive solo en la base de datos (`LibraryCatalog`, `CatalogEntry`, `ActiveShelf`). El catálogo apunta a las unidades; nunca las cambia.

## Versiones y adopción por estante

```bash
python manage.py catalogo cargar /ruta/privada/catalogo.json   # guarda una versión nueva, INACTIVA
python manage.py evaluar --agentes comentarios --catalogo <versión>   # la mide en sombra (ensayo gratis; --ejecutar paga)
python manage.py catalogo activar <versión> --estantes comentar       # el agente de ese estante la usa desde su próxima llamada
python manage.py catalogo desactivar --estantes comentar              # vuelve a la lista fija del código
python manage.py catalogo estado                                      # conteos e IDs, nunca texto del curso
```

- Las versiones son inmutables: un cambio es una versión nueva.
- `cargar` rechaza el archivo entero si una unidad no existe o no está activa, si un estante es desconocido, si el orden del núcleo no coincide con sus unidades o si un núcleo pasa del tope de tokens.
- Un estante sin versión activa usa la lista fija del código (`operador.COMMENT_UNITS`, `operador.REPLY_UNITS`…). Hoy leen del catálogo **Comentarios** (`comentar`) y **Respuestas** (`responder`); el resto de agentes sigue con sus listas fijas.
- Cada borrador registra de dónde salieron sus unidades (`course_source`: `catalogo:<versión>` o `lista_fija`) en los eventos `operator.comment_grounded` y `replies.drafted`.
- Se activa un estante solo cuando el evaluador muestra que su versión iguala o mejora la lista fija. Respuestas todavía no tiene casos en el evaluador.

## Formato del archivo

JSON con `version` (minúsculas, cifras, punto o guion), `metodo_niveles` (texto libre), `unidades` (`{ID: {principal: estante}}`) y `niveles`:

```json
{"comentar": {"nucleo_orden": ["ID", "..."],
              "unidades": {"ID": {"nivel": "nucleo|consulta|referencia", "razon": "dup|fuera|caso|baja|null",
                                  "puntaje": 0.9, "duplica": "ID|null"}}}}
```
