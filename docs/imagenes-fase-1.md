# Imágenes y «publícalo lo antes posible»: entrega de backend

Implementación en `feat/imagenes-backend`. No se ejecutaron Django, pruebas, instalaciones ni builds; no hubo red, commit ni push. Claude debe actualizar `uv.lock`, ejecutar CI y devolver sus resultados. La revisión local se limita a lectura del código, análisis sintáctico sin importaciones y comprobación del diff. La UI y Maestro se hacen en fase 2.

## Comportamiento y decisiones

El director recibe candidatas de galería, vistas reducidas, notas/transcripciones, permisos y usos. Elige foto, infografía o carrusel con motivo. Las fotos de propuestas son preferentes. La preparación congela archivos, alt, permiso y revisión por SHA-256. La propuesta incluye ese manifiesto en su hash; tanto la política como la ejecución comprueban imágenes y verificador de texto. Una aprobación humana tampoco evita estas comprobaciones al ejecutar.

`no` prohíbe cualquier edición; `auto` obedece «tal cual», aplica instrucciones seguras o un retoque justificado; ante duda conserva el original. `si` pide un retoque, pero no permite alterar personas, textos ni marcas. Un error, presupuesto agotado, clave ausente o revisión desfavorable conserva el original. Los originales no se sobrescriben y los derivados se sirven autenticados. Borrar una foto borra sus derivados e invalida una propuesta que los referenciaba; no la convierte en un post sin imagen.

Las infografías usan una regla de agente versionada (copia completa del tablero, con SHA-256), datos estructurados, validación y Pillow/Ubuntu. Una corrección como máximo. Las imágenes dinámicas necesitan revisión visual; los errores del proveedor no se reintentan. El carrusel es un PDF etiquetado: cada página contiene `/Alt`, porque la API de documentos de LinkedIn no ofrece un alt por lámina. La API privada conserva también los alt individuales.

El fallback es una tarjeta de marca fija con «A question worth exploring / Ideas, tradeoffs and practical decisions.», sin cifras, experiencias o afirmaciones nuevas. Se identifica como `tarjeta` y `image_review.mode=fixed_brand_card`. Su aprobación es la de la plantilla fija; nunca se presenta como una revisión visual de un contenido dinámico. Si tampoco se puede renderizar o servir el archivo, se bloquea y avisa; jamás se publica solo texto.

La urgencia se interpreta junto con el destino en la llamada de clasificación existente. Los destinos explícitos con fotos usan esa comprensión para atribuir instrucciones; los destinos explícitos sin fotos usan una consulta Jev Noul con el texto completo y fragmentos literales para la evidencia. Una negación, cita ajena o urgencia de otro asunto no activa prioridad. Una indisponibilidad se registra y no inventa intención. No hay botón ni campo de escritura de prioridad.

Las urgencias se reservan por orden de llegada en huecos normales de publicación, con una por hueco y respetando topes, ventanas, presupuesto, autonomía y aprobación. **No se desplaza una pieza preparada ni un trabajo ya en cola:** conserva su hora, inversión y decisión anterior; la captura registra esa razón. El director usa la idea reservada o salta la pieza por calidad. Si preparar consume el periodo de veto, se mueve a otro hueco y avisa. Los avisos pasan por `notificaciones.avisar` y los eventos existentes de oficina.

## Valores elegidos

La sección «Pendiente de confirmar» de la especificación ya dice que no hay decisiones abiertas de producto. Se fijan estos valores técnicos:

| Aspecto | Valor |
| --- | --- |
| Edición nueva | `auto`; históricos false→no y true→auto |
| Compatibilidad | Alias booleanos de API temporales; nuevos campos `ai_edit` y `gallery_ai_edit` |
| Presupuesto de imágenes | 1 USD por día local; suma ambos proveedores, reservas e inciertos; separado de editorial/comentarios |
| Edición | `gpt-image-1`, una salida medium de 1024 cuadrada, escalada a 1080 antes de la comprobación; reserva conservadora de 1 USD |
| Diseño y visión | `claude-sonnet-4-6`; propósitos `image-design`, `image-design-repair`, `image-check` |
| Carrusel | 3–8 láminas 1080×1350; portada, interiores y pregunta final |
| Imagen única | 1080×1080; originales prohibidos de editar conservan dimensiones; un formato no decodificable usa fallback |
| Tipografía y firma | Ubuntu regular incluido en el paquete; autor «Gustavo» |
| Urgencia Jev | Probabilidad mínima 0,8 y evidencia literal; sin heurística de palabras clave como decisión |
| Planificación | Primer hueco libre hasta 14 días; no desplaza piezas; fecha mínima «mañana» si se pidió |
| Veto urgente | Mínimo 60 minutos; se conservan hora y cadencia configuradas |

## Dependencias y entorno

Dependencia nueva: `Pillow`. **`uv.lock` queda pendiente de Claude**; el Dockerfile usa instalación congelada, por lo que debe actualizarse antes del build. Ubuntu y su licencia van incluidos; no se necesita instalar una fuente del sistema ni descargarla en producción.

Variables nuevas: `IMAGE_DAILY_USD`, `EDITORIAL_VETO_MINUTES`.

Variables existentes utilizadas: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `TYPESAFE_API_KEY`, `LIVE_PROVIDERS`, `LIVE_LINKEDIN_OFFICIAL`, `OPERATOR_ALLOW_FAKE`, `OPENAI_LIMIT_USD`, `ANTHROPIC_LIMIT_USD`, `EDITORIAL_POST_TIME`, `EDITORIAL_LEAD_HOURS`, `EDITORIAL_DAILY_LLM_USD`, `OPERATOR_TIMEZONE`, `OPERATOR_WINDOW`, `OPERATOR_AUTONOMY`.

Gustavo solo necesita claves con acceso a los modelos si quiere edición/diseños dinámicos; la tarjeta fija no requiere ninguna clave de imagen. No hace falta reconfirmar cada edición permitida. Debe conservar una autorización LinkedIn vigente con `w_member_social`. Los valores de presupuesto/veto pueden cambiarse si prefiere otros; no son bloqueantes para esta entrega.

Los esquemas externos y la tarifa base de `gpt-image-1` se implementaron sin red. No se afirma que se hayan consultado las tarifas o permisos actuales: Claude debe contrastarlos antes de habilitar llamadas reales. Las pruebas usan `httpx.MockTransport`, el conector LinkedIn falso y un conector de imágenes falso explícito. La comparación visual de las cuatro plantillas con el tablero también queda para CI/revisión visual; hay pruebas escritas de geometría, fuentes, límites y PDF.

Las propuestas antiguas ya preparadas solo con texto carecen de manifiesto: la nueva compuerta las bloquea. Deben prepararse de nuevo como una nueva pieza/propuesta; no se cambia silenciosamente un hash aprobado. Las nuevas preparaciones funcionan sin claves opcionales.

## Archivos

Rutas de código relativas a `agentes-linkedin/infra/`:

| Archivo | Cambio |
| --- | --- |
| `pyproject.toml` | Pillow y empaquetado de recursos/fuentes/reglas. |
| `src/knowledge/providers.py` | Reserva atómica del presupuesto diario de imágenes, además del techo del proveedor. |
| `src/team_backend/models.py` | AIEdit, intención/evidencia/fecha de captura, campos de imagen de pieza y PieceImage. |
| `src/team_backend/migrations/0019_imagenes_y_urgencia.py` | Esquema y conversión reversible de booleanos; no modifica los archivos. |
| `src/team_backend/capture_intent.py` | Comprensión estructurada, Noul, citas literales e instrucciones por foto. |
| `src/team_backend/capturas.py` | Propuestas, notas en todas las fotos, intención, API y ciclo de usos/liberación/borrado. |
| `src/team_backend/capturas_views.py` | Campos de tres estados, compatibilidad, validación y prioridad de solo lectura. |
| `src/team_backend/urgente.py` | Asignación serializada de huecos, topes, avisos y periodo de veto. |
| `src/team_backend/editorial.py` | Elección visual en brief, prioridad obligatoria, preparación de imágenes y manifiesto. |
| `src/team_backend/imagenes.py` | Galería, permisos, edición/check, rendering, fallback, hashes, uso y subida. |
| `src/team_backend/infografias.py` | Regla completa, esquema, validadores, cuatro plantillas/cierre, PNG y PDF etiquetado. |
| `src/team_backend/connectors_images.py` | OpenAI multipart con ledger, Claude multimodal y fake de pruebas. |
| `src/team_backend/connectors_linkedin.py` | Subidas de imagen/documento, espera de AVAILABLE, content.media/multiImage y memoria del fake. |
| `src/team_backend/autopiloto.py` | Compuerta de imágenes, prioridad y liberación al caducar. |
| `src/team_backend/operador.py` | Manifiesto bajo hash, validación antes de publicar, subida, estados, avisos y marcas publicadas. |
| `src/team_backend/editorial_views.py` | Imágenes/revisiones de pieza y streaming privado PNG/PDF. |
| `src/team_backend/urls.py` | Dos nuevas rutas de archivos privados. |
| `src/team_backend/notificaciones.py` | Evento `capture_scheduled`. |
| `src/team_backend/rediseno_views.py` | Línea de gasto de imágenes con ambos proveedores. |
| `src/team_backend/resumen_semanal.py` | Gasto de imágenes incluido en cifras semanales y presupuesto. |
| `src/team_backend/management/commands/seed_qa.py` | Foto, infografía y captura urgente; limpieza de archivos nuevos y manifiestos de fixtures. |
| `src/team_backend/recursos/infografias.html` | Copia íntegra del tablero fuente; solo backend. |
| `src/team_backend/recursos/fonts/Ubuntu.ttf` | Fuente local redistribuida, sin descarga de runtime. |
| `src/team_backend/recursos/fonts/LICENSE.txt` | Licencia y atribución de la distribución de Ubuntu. |
| `src/team_backend/tests/test_imagenes.py` | Permisos, integridad, fallback, plantillas, alt/PDF, ledger, contratos de proveedores y publicación. |
| `src/team_backend/tests/test_publish_asap.py` | Interpretación, reservas, presupuesto/aprobación/verificación/veto y migración histórica. |
| `src/team_backend/tests/test_publicacion.py` | Fixtures de piezas con imagen y almacenamiento temporal. |
| `src/team_backend/tests/test_capturas.py` | Nuevo destino y marca de uso. |
| `src/team_backend/tests/test_rediseno.py` | Línea nueva de presupuesto. |
| `src/team_backend/tests/test_resumen_semanal.py` | Categoría nueva de gasto. |
| `src/team_backend/tests/test_seed_qa.py` | Comprueba ejemplos visuales y captura urgente. |
| `docs/capturas-galeria.md` | Describe tres estados y circuito de imagen implementado. |
| `docs/publicacion-diaria.md` | Actualiza el límite anterior de texto, manifiestos y subida. |

Documentos del repositorio:

| Archivo | Cambio |
| --- | --- |
| `docs/funcionalidades/imagenes-en-publicaciones.md` | Estados backend/mixtos, implementación por ID, defaults y QA vacía. |
| `docs/funcionalidades/captura.md` | CAP-16 e intención sin botón; propuestas y contexto de fotos. |
| `docs/funcionalidades/motor-editorial.md` | EDI-20, hueco urgente, decisión de no desplazar y compuertas. |
| `docs/funcionalidades/calendario-piezas.md` | CAL-17, fecha prevista y aviso. |
| `docs/funcionalidades/galeria.md` | Uso real, permiso dominante y compatibilidad de fase 2. |
| `docs/funcionalidades/ajustes.md` | Tres estados y presupuesto de imágenes. |
| `oficina/CONTRATO-API.md` | Contrato exacto de endpoints/campos/tipos para fase 2, compatibilidad y fixtures. |
| `docs/imagenes-fase-1.md` | Este inventario, defaults, dependencias y límites de validación. |

El contrato completo de la siguiente fase está en [CONTRATO-API.md, «Fase 2: imágenes y publicación prioritaria»](../oficina/CONTRATO-API.md#fase-2-imágenes-y-publicación-prioritaria).
