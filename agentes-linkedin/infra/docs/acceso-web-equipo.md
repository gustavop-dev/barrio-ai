# Acceso web del equipo · fase 1

Implementación de CAP-17/18 y ampliaciones de EDI-03, EDI-07, EDI-13 y EDI-17. El catálogo de `plan-equipos` prevalece: Capturas no consulta el curso; EDI-20 sigue reservado al futuro especialista visual; OBS-01–04 y ARQ-01–09 no se activan aquí. Solo backend, catálogo y contrato de interfaz. Tests escritos, **no ejecutados localmente**.

## Contrato reutilizable

`team_backend.research.research(request: ResearchRequest) -> ResearchResult` es el punto de entrada para el futuro orquestador. Las dataclasses `ResearchRequest`, `ResearchResult`, `Finding` y `Source` definen los tipos; `ResearchResult.to_dict/from_dict` serializa el contrato de versión 1.

- Entrada: `key` estable por ciclo/paso, `public_question`, `urls`, `search`, `purpose`. Los callers actuales usan `capture:<uuid>` y `piece:<uuid>`; la pieza tiene una sola solicitud, sin recursión. El caller debe extraer una pregunta pública: no pasar notas, memoria o inbox como pregunta. El servicio aplica filtros adicionales antes de cualquier herramienta.
- Salida: `schema_version`, `question`, `status`, `researched_at`, `findings[{text,source_ids}]`, `sources[{id,url,title,quoted_text,retrieved_at,kind,truncated}]`, `limitations`, `usage`. Estados: `complete`, `partial`, `unavailable`, `skipped`, `running` (en curso/interrumpida, nunca una invitación a repetir).
- `WebResearchRun` reclama cupo mediante transacción/lock PostgreSQL y guarda la respuesta. Misma clave y entrada devuelve la respuesta anterior; otra entrada con esa clave se rechaza. Un proceso interrumpido no vuelve a pagar. No es todavía el ledger completo de ciclos de ARQ-04.
- Capturas guarda `investigation`; piezas guardan `research`. Deshacer retira el contenido y marca el intento `withdrawn`, manteniendo cupo y uso monetario. La vista de la captura conserva el resumen de investigación incluso cuando su idea se usa o vuelve a la mesa.

## Prompts y herramientas

`capture_intent.GUIDE` incorpora `research_requested/research_evidence/research_question/research_public` a la llamada estructurada existente. Para destinos explícitos sin fotos se amplían las preguntas Noul de la misma llamada Jev. La evidencia de intención debe estar literalmente en nota/transcripción. No se añade consulta a biblioteca.

`research.SYSTEM` recibe únicamente una pregunta pública acotada y URLs validadas. Usa herramientas de servidor Claude `web_search` y `web_fetch`, con tipos versionados y límites configurables. Solicita citas nativas, fuentes primarias, fechas y omitir lo no verificable. Se conserva el cache de system y el conteo previo de tokens del adapter existente. No se mezcla JSON schema de salida con citas nativas; las URLs en prosa generada no se aceptan como evidencia. `pause_turn`, rechazo y truncamiento nunca provocan continuación automática.

El director puede pedir hechos actuales mediante `BRIEF_SCHEMA.research_request`. El workflow llama al servicio, persiste el resultado y vuelve una vez al director para cerrar el brief. `DIRECTION`, `VERIFIER_SYSTEM` y el prompt visual marcan todos los extractos como datos no confiables: ignoran órdenes dentro de páginas/README. La comprobación determinista exige refs web guardadas y contraste explícito del verificador; el modelo contrasta el significado de la afirmación con el extracto. Las citas de curso conservan su espacio separado.

GitHub REST lee solo raíces de repositorios públicos: descripción, topics, languages, README truncado y commits recientes. Primero comprueba acceso público **sin token**; el token opcional solo se usa después. Solo conecta a `api.github.com`, valida todas sus direcciones DNS, fija una IP pública y conserva Host/SNI para TLS. Desactiva proxies de entorno y redirecciones, limita bytes por respuesta y no sigue `download_url`, `html_url` ni URLs contenidas en README. Fallos REST permiten fallback a `web_fetch`. No hay fetch HTTP genérico local.

Los enlaces semilla solo admiten http(s), puertos estándar y DNS público. Se rechazan credenciales, IPs internas/metadata, hosts ambiguos y todos los parámetros de consulta en esta fase; fragmentos no viajan. Ambos lectores requieren `LIVE_PROVIDERS`, incluido GitHub gratuito. Las búsquedas nunca reciben la captura completa, memoria ni orientación; si no se separa un tema público se omiten.

## Coste y visibilidad

`providers.reserve` conserva los límites mensuales del proveedor y reserva el máximo de salida, entrada/cache, búsquedas y una estimación conservadora de tokens de resultados/relecturas. Serializa los caps de investigación y editorial con el mismo lock monetario. La liquidación registra tokens normales/cache, búsquedas, lecturas, coste de búsquedas, request ID y ledger ID. Timeouts o uso ilegible conservan la reserva y las operaciones reservadas; los errores HTTP definitivos se liquidan según el adapter existente.

El cap de investigaciones por día es independiente del monetario; cuenta intentos iniciados, incluso fallidos/interrumpidos/retirados, en el día de `OPERATOR_TIMEZONE`. No se libera por Deshacer. El cap editorial agrega `editorial-%` e `image-%`, incluidos los dos proveedores de imagen. El presupuesto de imágenes conserva su sublímite; la investigación iniciada en captura pertenece al cap web, y la solicitada por el director además al editorial. Las tarjetas de gasto son ámbitos solapados, no partidas sumables.

El outcome dice cuántas fuentes leyó o por qué no pudo investigar; la captura se enruta igualmente. Una investigación ejecutada emite `entrega` de `investigador_referentes` a `director_editorial` con un resumen sin consultas, URLs ni contenido privado. Fuentes y uso detallado quedan en las respuestas autenticadas de captura/pieza. Interfaz detallada pendiente, descrita en el contrato.

## Settings y variables de entorno (solo nombres)

| Nombres | Uso |
| --- | --- |
| `WEB_RESEARCH_ENABLED`, `LIVE_PROVIDERS` | Activación y cierre de toda salida de investigación |
| `WEB_RESEARCH_MODEL`, `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` | Modelo dedicado y proveedor existente |
| `WEB_SEARCH_TOOL_TYPE`, `WEB_FETCH_TOOL_TYPE` | Tipos versionados de herramientas |
| `WEB_SEARCH_MAX_USES`, `WEB_FETCH_MAX_USES`, `WEB_FETCH_MAX_CONTENT_TOKENS`, `WEB_RESEARCH_MAX_TOKENS`, `WEB_RESEARCH_MAX_URLS` | Límites por paso |
| `WEB_RESEARCH_DAILY_LIMIT`, `WEB_RESEARCH_DAILY_USD` | Cupo diario de intentos y dinero |
| `WEB_SEARCH_USD_PER_REQUEST`, `WEB_SEARCH_RESERVED_TOKENS` | Tarifa y reserva conservadora para resultados de búsqueda |
| `WEB_GITHUB_MAX_BYTES`, `WEB_GITHUB_README_CHARS`, `WEB_GITHUB_TIMEOUT_S`, `GITHUB_TOKEN` | Lector GitHub; token opcional |
| `ANTHROPIC_LIMIT_USD`, `ANTHROPIC_LIMIT_WINDOW`, `EDITORIAL_DAILY_LLM_USD`, `IMAGE_DAILY_USD`, `OPERATOR_TIMEZONE` | Límites existentes que también se aplican |

No se requieren credenciales de un buscador adicional. No se le pide a Gustavo otra decisión; `GITHUB_TOKEN` es opcional y permanece exclusivamente en el entorno privado.

## Archivos cambiados

Rutas relativas a la raíz del worktree:

```text
agentes-linkedin/infra/src/knowledge/providers.py
agentes-linkedin/infra/src/linkedin_backend/settings.py
agentes-linkedin/infra/src/team_backend/research.py                         (nuevo)
agentes-linkedin/infra/src/team_backend/web_sources.py                      (nuevo)
agentes-linkedin/infra/src/team_backend/capture_intent.py
agentes-linkedin/infra/src/team_backend/capturas.py
agentes-linkedin/infra/src/team_backend/editorial.py
agentes-linkedin/infra/src/team_backend/editorial_views.py
agentes-linkedin/infra/src/team_backend/imagenes.py
agentes-linkedin/infra/src/team_backend/models.py
agentes-linkedin/infra/src/team_backend/rediseno_views.py
agentes-linkedin/infra/src/team_backend/migrations/0020_web_research.py      (nuevo)
agentes-linkedin/infra/src/team_backend/tests/test_web_research.py          (nuevo)
agentes-linkedin/infra/src/team_backend/tests/test_imagenes.py
agentes-linkedin/infra/src/team_backend/tests/test_publish_asap.py
agentes-linkedin/infra/docs/acceso-web-equipo.md                            (nuevo)
docs/funcionalidades/captura.md
docs/funcionalidades/motor-editorial.md
docs/funcionalidades/observatorio-referentes.md                            (nuevo)
docs/funcionalidades/README.md
oficina/CONTRATO-API.md
```

## Claude: CI y despliegue

En CI, con PostgreSQL temporal y proveedores falsos:

1. Ejecutar `python manage.py check`, `python manage.py makemigrations --check --dry-run`, la suite Django completa y la suite de infraestructura habitual. No conectar a la web ni habilitar credenciales reales; los tests nuevos que ejercitan el gate live usan claves ficticias y SDK/HTTP/DNS falsos.
2. Revisar `test_web_research`: detección en nota/transcript; intención y privacidad; lectura GitHub, DNS mixto, redirects y tamaño; citas search/fetch; pausa/truncamiento; reserva/liquidación/cache y conteo de búsquedas; fallo de presupuesto, deduplicación/interrupción y competencia por el último cupo; captura/outcome/undo; entrega a director y rechazo de fuentes inexistentes.
3. Revisar regresiones de `test_capturas`, `test_publish_asap`, `test_publicacion`, `test_auditoria_editorial`, `test_imagenes`, `test_limite_mensual` y API de Ajustes. La prueba de migración de imágenes restaura ahora todas las hojas del grafo tras su comprobación histórica.
4. Aplicar y revertir `0020_web_research` sobre datos de prueba, comprobando defaults sin alterar capturas/piezas anteriores. No se toca el SQL legado ni se reinicia ningún ledger.

Al desplegar:

1. Aplicar la migración antes de reiniciar API/workers. Reconciliar el override editorial con el tope del plan de equipos y revisar los límites web/proveedor; no elevarlos automáticamente para hacer pasar una llamada. Comparar presupuestos solapados sin sumar imágenes dos veces.
2. Verificar en documentación oficial y configuración del proveedor la compatibilidad del modelo con ambos tipos de herramientas, el soporte de conteo/streaming, la tarifa por búsqueda y la forma de usage/citas. Esta tarea no tuvo red; la reserva de resultados es conservadora y debe revisarse frente al uso real.
3. Comprobar TLS/Host/SNI y salida directa al GitHub público en el entorno desplegado. Si requiere proxy, el cliente directo falla cerrado y usa el fallback; nunca habilitar un proxy no controlado ni omitir validación TLS.
4. En QA, comprobar primero con fakes que una captura y una pieza exponen fuentes/fecha/limitaciones y el evento de Oficina. Comprobar ausencia de gasto/HTTP con proveedores desactivados, límite agotado, Deshacer concurrente y rechazo de afirmación sin respaldo. Cualquier validación real de herramientas usa el procedimiento de despliegue y presupuesto autorizado; no forma parte de los tests.

No se ejecutaron instalaciones, tests, builds, migraciones ni llamadas reales en el worktree; no hubo commit ni push. La aceptación final queda pendiente de los resultados que Claude traiga de CI/despliegue.
