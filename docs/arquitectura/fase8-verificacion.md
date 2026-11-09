# Fase 8: entrega y verificación por Claude

Implementación de EST-01–05, GAL-08 y TUR-18 en `feat/fase8-perfil`, sobre fases 3b y 7. Solo se editaron archivos: no hubo red, instalaciones, tests, builds, migraciones ejecutadas, commits, push, deploy ni generación de imágenes reales. El Mermaid se regeneró con el generador stdlib del repositorio. Las fichas del catálogo figuran como **funciona** por implementación; CI/QA y activación siguen pendientes.

El ciclo `perfil_periodico` pertenece a Perfil. Recupera biblioteca original, hechos confirmados y publicaciones propias con enlaces/métricas fechadas; usa posicionamiento, copy, revisión, web pública, lectura propia y visual como herramientas declaradas. Publica el paquete privado en Tu turno y emite `profile_task`. Ninguna ruta escribe el perfil de LinkedIn.

Corrección de la primera propuesta `partial`: el catálogo de evidencia incluye IDs exactos del snapshot, hechos públicos, publicaciones, referencias por rol y consentimiento, y fuentes web. La normalización ocurre antes del revisor. Una sección no legible admite una recomendación nueva; `needs_input` conserva copy con placeholders y preguntas separadas. Las omisiones justificadas de secciones opcionales no vuelven parcial todo el paquete: en modo completo se consideran esenciales foto A/B, banner, titular y Acerca de. El copy rechazado sí se oculta y se intenta corregir dentro de las dos rondas existentes, incluido un banner vacío.

La generación, render y revisión de A, B y banner fallan por separado. Visión comprueba los puntos aplicables a cada asset; los previews disponibles se revisan con el banner. El grafo permite seis revisiones visuales entre las dos versiones, manteniendo el cap agregado de **10 USD** y los checkpoints. La aceptación de foto exige A y B; la del banner exige su propio archivo revisado. Web sin fuentes es opcional: solo se conservan citas nativas o extractos literales de documentos devueltos por la herramienta, nunca URLs de prosa sin respaldo. No se ha ejecutado esta corrección en producción ni se han ejecutado tests/builds locales; las regresiones sintéticas de backend, web, PWA y app quedan para CI/QA.

## Migración y configuración

Migración **`team_backend/0026_profile_strategy.py`**, dependiente de `0025_referentes_monthly`: categoría, consentimiento/versiones/rol de GalleryPhoto; exclusión persistente en PieceImage; ProfileSchedule, ProfileProposal y ProfileAsset. No lleva datos privados ni modifica el SQL legado. Defaults conservan las fotos existentes como posts; autorizar Perfil no cambia el permiso de edición de posts.

Variables nuevas, nombres sin valores: `PROFILE_ENABLED`, `PROFILE_OWNER_USERNAME`. La primera habilita la cadencia periódica; la segunda identifica al usuario humano dueño de las referencias y propuestas. El propietario no es el robot de autopiloto. La captura explícita es una solicitud independiente del interruptor periódico.

Variables existentes utilizadas: `OPERATOR_TIMEZONE`, `LIVE_PROVIDERS`, `OPENAI_IMAGE_MODEL`, `OPENAI_API_KEY`, `OPENAI_LIMIT_USD`, `OPENAI_LIMIT_WINDOW`, `ANTHROPIC_MODEL`, `ANTHROPIC_VISION_MODEL`, `ANTHROPIC_API_KEY`, `ANTHROPIC_LIMIT_USD`, `ANTHROPIC_LIMIT_WINDOW`, y configuración `WEB_RESEARCH_ENABLED`, `WEB_RESEARCH_MAX_URLS`, `WEB_RESEARCH_MODEL`, `WEB_RESEARCH_DAILY_LIMIT`, `WEB_RESEARCH_DAILY_USD`, `WEB_RESEARCH_MAX_TOKENS`, `WEB_SEARCH_TOOL_TYPE`, `WEB_FETCH_TOOL_TYPE`, `WEB_SEARCH_MAX_USES`, `WEB_FETCH_MAX_USES`, `WEB_FETCH_MAX_CONTENT_TOKENS`, `WEB_SEARCH_RESERVED_TOKENS`, `WEB_SEARCH_USD_PER_REQUEST`. No hay una segunda variable de cap de Perfil: el grafo fija **10 USD por propuesta**, agregados entre texto, herramientas, tres ediciones y visión, incluidas reservas inciertas. Los topes globales del proveedor siguen aplicándose.

La primera activación fija el ancla semestral; seis meses son meses calendario, con ajuste al último día cuando sea necesario. Mensualmente solo se revisan destacados/artículos/actividad. Sin cambios, se registra información en Notificaciones (`profile_reviewed`) sin crear una tarea vacía. La actividad aceptada llega como artefacto al siguiente brief editorial, sin programar posts. Una captura explícita no mueve el ancla. Se deduplican solicitudes activas compatibles y periodos; deshacer una captura retira su trigger y no cancela un periodo que también atendía esa propuesta.

## CI y QA pendientes

Selección: **`[qa: 03 04 05 07 10 11 16-imagenes 17-mapa-equipo 18-perfil]`**.

1. Integrar los resultados finales de 3b y 7, conservando sus ledgers, IDs y gates. Revisar dependencias de migración y ejecutar en CI el chequeo de migraciones, `manage.py check`, `test_grafo` y `scripts/grafo/mermaid.py --check`. Verificar que Docker empaquete el registro único y `recursos/fonts/Ubuntu.ttf`.
2. Ejecutar backend `test_perfil`, `test_seed_qa` y regresiones de `test_orquestacion`, `test_editor_visual`, `test_imagenes`, capturas, publicación, preguntas, autopiloto y notificaciones. Modelos, conectores y reloj son fakes; `test_perfil` prohíbe llamadas reales y usa PNG generados. El caso de contrato HTTP usa exclusivamente MockTransport. Casos y alternativa incorrecta: [casos-fase8.json](../../agentes-linkedin/equipos/estrategia-perfil/casos-fase8.json). El harness de evaluación editorial histórica no se ejecutó ni se presenta como evaluación de Perfil.
3. Ejecutar typecheck/lint, Vitest PWA y Jest app/compartido en CI; revisar Galería, el contrato compartido y `ProfileProposal`. Confirmar que cambios de categoría en reintentos no alteren el lote anterior y que fallos/409 conserven las notas escritas.
4. Correr Maestro `18-perfil.yaml` con seed aislado. Etiqueta una foto como Perfil, abre la propuesta sembrada, muestra citas y checklist, acepta/aplica el titular y conserva «Aplicado por Gustavo». Seed suma una foto PNG de bloques y siete assets sintéticos: nunca una persona real. Revisar también los contadores actualizados de `04-*` y el visor de cinco fotos de `10-galeria`.
5. QA en vivo PWA y app a 390×844 y escritorio: asignar categoría al subir y después; notas/roles/consentimiento; filtro Perfil; exclusión por catálogo e ID directo de posts, incluso un derivado previamente seleccionado. Ver ambas opciones, banner, cuatro previews, referencias privadas, ocho puntos/identidad, copy/citas/pasos, Markdown, descargas y elección A/B sin preselección. Aceptación del banner independiente. Confirmar continuidad de scroll y accesibilidad de controles de la hoja.
6. Probar «Hecho, lo apliqué», texto alternativo, rechazo con motivo, ajuste por sección, más tarde y versión antigua. La lectura actual solo expone titular; «Comprobado» exige coincidencia exacta en una relectura propia autorizada. Las otras secciones quedan aplicadas sin comprobación automática. Un fallo de lectura conserva cuotas/checkpoint y no declara éxito.
7. Probar ausencia de biblioteca/fotos/Ubuntu/alfa, notas conflictivas, cita ausente o irrelevante, hecho no acreditado, identidad/gafas/sonrisa rechazadas, web caída, límite no verificado, agotamiento de cap y llamada incierta. Entregar solo las secciones independientes válidas; no inventar información ni sustituir originales ni quitar B para declarar completo el paquete.
8. Probar respuesta de un único hecho faltante: deduplicación entre secciones, memoria con procedencia, ajuste solo de las secciones afectadas y mismo ledger. Probar reintento de upload por hash y reutilización de ediciones ya completadas; cambio/revocación de referencia invalida assets/descargas/decisiones anteriores.

El `seed_qa` conserva sus guardas destructivas existentes: **solo en la base efímera de QA**, nunca en producción. No se ejecutó en este worktree. Se añadieron modelos a su limpieza aislada y a sus aserciones de idempotencia, sin borrar estado de producción.

## Después del deploy, en el servidor

1. Aplicar la migración 0023 con el proceso habitual y desplegar backend/PWA. La app solo cambia JS/TS compartido: OTA, sin dependencias ni fingerprint nativo nuevos. Verificar almacenamiento privado y rutas autenticadas antes de producir assets. No reiniciar saldos, ledgers ni memoria para desbloquear errores. Una instancia 3b cuyo grafo/contexto cambie requiere conciliación explícita; no forzar reintentos de llamadas inciertas.
2. Configurar el dueño humano y mantener la cadencia deshabilitada hasta preparar sus referencias. Comprobar el contrato/precio y compatibilidad real del modelo configurado por `OPENAI_IMAGE_MODEL` con múltiples entradas, fondo transparente, salida PNG y usage. El adaptador existente estima costes y reserva conservadoramente; esta tarea offline no verificó precios ni el contrato remoto del modelo. Si no devuelve alfa fiable, Perfil queda pendiente. Confirmar también disponibilidad de Ubuntu y visión.
3. **Cargar las tres fotos privadas de Gustavo a «Perfil», con su sesión, edición para Perfil autorizada, roles 01/02/03 y notas exactas de la tabla siguiente.** Origen externo al repo: `/home/cerrotico/personal/linkedin/Recursos visuales/perfil-referencias/`. Usar esta lista explícita, no un glob de todo el directorio. Verificar por ID/hash las ya cargadas; el endpoint deduplica uploads de Perfil del mismo dueño por bytes y conserva versiones si no cambia la metadata. No crear segundos originales activos con el mismo rol.

| Archivo privado | Rol | Nota exacta |
| --- | --- | --- |
| `01-pose-foto-perfil-sonriendo-de-lado.png` | `01` | Pose para B y sonrisa para A, B y banner: conservar cabeza girada en B y sonrisa natural de esta referencia en todos los assets. Sustituir jersey por camiseta blanca oversized de algodón grueso, cuello crew neck, sin logos; gafas claras de 03. |
| `02-cuerpo-completo-referencia-portada.png` | `02` | Cuerpo y postura para el banner: recortar de cintura arriba, presentando con micrófono de mano, camiseta blanca oversized y gafas claras; expresión natural hablando con la sonrisa de 01. |
| `03-rostro-angulos-identidad.png` | `03` | Identidad para A, B y banner: vistas frontal, lateral y posterior de rostro y pelo; preservar facciones/cabello y mostrar sus gafas fotocromáticas (transitions) claras, como aquí. Comparar por visión cada resultado con esta referencia. |

No cargar `ref-externa-diandra-portada-microfono.png`: solo se usa su descripción verbal. Ninguna referencia, resultado o comparación real va al repo público, fixtures, capturas de QA públicas ni documentación; tampoco se incrustan como base64. Los originales y checkpoints se guardan en storage privado del servidor.

4. Verificar que las referencias pertenecen al dueño configurado, tienen las notas/roles correctos y consentimiento vigente. Comprobar aptitud/foco y conservar sus originales. Activar la cadencia o enviar «hazme la propuesta del perfil»; comprobar el trigger y `cycle_id`, el cap, notificación/push, documento y siete archivos de la misma versión. El ciclo mensual no debe llamar al editor de personas.
5. Revisar A y B 800×800, banner 1584×396, sRGB y tamaño, fondo plano exacto, A neutra, B natural, ambas sonriendo con identidad de 03 y gafas claras; banner con cuerpo 02, sonrisa 01, micrófono, camiseta correcta, figura fuera del círculo y texto sin colisiones. Revisar la frase inglesa propuesta, fallback solo si la oferta está acreditada, y ausencia de «speaker»/prueba social sin evidencia. Revisar los ocho puntos por opción y sus hashes. Los previews son aproximaciones conservadoras; Gustavo comprueba el resultado en LinkedIn real al aplicarlo.
6. Verificar descargas privadas en navegador y app. La app obtiene una capacidad aleatoria de un solo recurso, un solo uso y 60 segundos, ligada a la revisión; no envía el bearer de dispositivo al navegador. Su canje revalida dueño, permiso, versión, revocación y hash. Confirmar que el proxy no cachee ni publique esos enlaces y oculte el segmento del token en logs de acceso. Nadie debe convertirlos en URLs públicas persistentes.

## Archivos cambiados

El inventario de esta entrega se mantiene al final de este documento. Incluye el pipeline nuevo, extensiones acotadas a 3b/7, migración, UI compartida/PWA/app, fakes, seed, Maestro, registro y catálogo.

<!-- inventario-fase8 -->

70 archivos modificados o nuevos:

- [agentes-linkedin/arquitectura/indice-agentes-v1.json](../../agentes-linkedin/arquitectura/indice-agentes-v1.json)
- [agentes-linkedin/equipos/estrategia-perfil/casos-fase8.json](../../agentes-linkedin/equipos/estrategia-perfil/casos-fase8.json) — nuevo
- [agentes-linkedin/equipos/estrategia-perfil/perfil.json](../../agentes-linkedin/equipos/estrategia-perfil/perfil.json)
- [agentes-linkedin/equipos/estrategia-perfil/posicionamiento.json](../../agentes-linkedin/equipos/estrategia-perfil/posicionamiento.json)
- [agentes-linkedin/equipos/grafo.yaml](../../agentes-linkedin/equipos/grafo.yaml)
- [agentes-linkedin/infra/.env.example](../../agentes-linkedin/infra/.env.example)
- [agentes-linkedin/infra/docs/mapa-agentes-runtime.md](../../agentes-linkedin/infra/docs/mapa-agentes-runtime.md)
- [agentes-linkedin/infra/src/team_backend/autopiloto.py](../../agentes-linkedin/infra/src/team_backend/autopiloto.py)
- [agentes-linkedin/infra/src/team_backend/capturas.py](../../agentes-linkedin/infra/src/team_backend/capturas.py)
- [agentes-linkedin/infra/src/team_backend/capturas_views.py](../../agentes-linkedin/infra/src/team_backend/capturas_views.py)
- [agentes-linkedin/infra/src/team_backend/connectors_images.py](../../agentes-linkedin/infra/src/team_backend/connectors_images.py)
- [agentes-linkedin/infra/src/team_backend/editor_visual.py](../../agentes-linkedin/infra/src/team_backend/editor_visual.py)
- [agentes-linkedin/infra/src/team_backend/editorial.py](../../agentes-linkedin/infra/src/team_backend/editorial.py)
- [agentes-linkedin/infra/src/team_backend/imagenes.py](../../agentes-linkedin/infra/src/team_backend/imagenes.py)
- [agentes-linkedin/infra/src/team_backend/jobs.py](../../agentes-linkedin/infra/src/team_backend/jobs.py)
- [agentes-linkedin/infra/src/team_backend/management/commands/seed_qa.py](../../agentes-linkedin/infra/src/team_backend/management/commands/seed_qa.py)
- [agentes-linkedin/infra/src/team_backend/migrations/0026_profile_strategy.py](../../agentes-linkedin/infra/src/team_backend/migrations/0026_profile_strategy.py) — nuevo
- [agentes-linkedin/infra/src/team_backend/models.py](../../agentes-linkedin/infra/src/team_backend/models.py)
- [agentes-linkedin/infra/src/team_backend/notificaciones.py](../../agentes-linkedin/infra/src/team_backend/notificaciones.py)
- [agentes-linkedin/infra/src/team_backend/oficina_views.py](../../agentes-linkedin/infra/src/team_backend/oficina_views.py)
- [agentes-linkedin/infra/src/team_backend/operador.py](../../agentes-linkedin/infra/src/team_backend/operador.py)
- [agentes-linkedin/infra/src/team_backend/perfil.py](../../agentes-linkedin/infra/src/team_backend/perfil.py) — nuevo
- [agentes-linkedin/infra/src/team_backend/perfil_contenido.py](../../agentes-linkedin/infra/src/team_backend/perfil_contenido.py) — nuevo
- [agentes-linkedin/infra/src/team_backend/perfil_galeria.py](../../agentes-linkedin/infra/src/team_backend/perfil_galeria.py) — nuevo
- [agentes-linkedin/infra/src/team_backend/perfil_views.py](../../agentes-linkedin/infra/src/team_backend/perfil_views.py) — nuevo
- [agentes-linkedin/infra/src/team_backend/perfil_visual.py](../../agentes-linkedin/infra/src/team_backend/perfil_visual.py) — nuevo
- [agentes-linkedin/infra/src/team_backend/preguntas.py](../../agentes-linkedin/infra/src/team_backend/preguntas.py)
- [agentes-linkedin/infra/src/team_backend/rediseno_views.py](../../agentes-linkedin/infra/src/team_backend/rediseno_views.py)
- [agentes-linkedin/infra/src/team_backend/tests/test_grafo.py](../../agentes-linkedin/infra/src/team_backend/tests/test_grafo.py)
- [agentes-linkedin/infra/src/team_backend/tests/test_notificaciones.py](../../agentes-linkedin/infra/src/team_backend/tests/test_notificaciones.py)
- [agentes-linkedin/infra/src/team_backend/tests/test_perfil.py](../../agentes-linkedin/infra/src/team_backend/tests/test_perfil.py) — nuevo
- [agentes-linkedin/infra/src/team_backend/tests/test_seed_qa.py](../../agentes-linkedin/infra/src/team_backend/tests/test_seed_qa.py)
- [agentes-linkedin/infra/src/team_backend/urls.py](../../agentes-linkedin/infra/src/team_backend/urls.py)
- [compartido/src/api/capturas.ts](../../compartido/src/api/capturas.ts)
- [compartido/src/api/perfil.ts](../../compartido/src/api/perfil.ts) — nuevo
- [compartido/src/api/types.ts](../../compartido/src/api/types.ts)
- [compartido/src/fixtures/perfil.ts](../../compartido/src/fixtures/perfil.ts) — nuevo
- [compartido/src/logic/galeria.ts](../../compartido/src/logic/galeria.ts)
- [compartido/src/logic/perfil.test.ts](../../compartido/src/logic/perfil.test.ts) — nuevo
- [compartido/src/logic/perfil.ts](../../compartido/src/logic/perfil.ts) — nuevo
- [docs/arquitectura/anadir-agente.md](../../docs/arquitectura/anadir-agente.md)
- [docs/arquitectura/fase8-verificacion.md](../../docs/arquitectura/fase8-verificacion.md) — nuevo
- [docs/arquitectura/grafo.md](../../docs/arquitectura/grafo.md)
- [docs/funcionalidades/README.md](../../docs/funcionalidades/README.md)
- [docs/funcionalidades/estrategia-perfil.md](../../docs/funcionalidades/estrategia-perfil.md)
- [docs/funcionalidades/galeria.md](../../docs/funcionalidades/galeria.md)
- [docs/funcionalidades/tu-turno.md](../../docs/funcionalidades/tu-turno.md)
- [docs/plan-equipos.md](../../docs/plan-equipos.md)
- [movil/.maestro/04-tu-turno-aprobar.yaml](../../movil/.maestro/04-tu-turno-aprobar.yaml)
- [movil/.maestro/04-tu-turno-mas.yaml](../../movil/.maestro/04-tu-turno-mas.yaml)
- [movil/.maestro/04-tu-turno.yaml](../../movil/.maestro/04-tu-turno.yaml)
- [movil/.maestro/10-galeria.yaml](../../movil/.maestro/10-galeria.yaml)
- [movil/.maestro/18-perfil.yaml](../../movil/.maestro/18-perfil.yaml) — nuevo
- [movil/.maestro/README.md](../../movil/.maestro/README.md)
- [movil/src/galeria/GaleriaScreen.test.tsx](../../movil/src/galeria/GaleriaScreen.test.tsx)
- [movil/src/galeria/GaleriaScreen.tsx](../../movil/src/galeria/GaleriaScreen.tsx)
- [movil/src/galeria/PhotoSheet.tsx](../../movil/src/galeria/PhotoSheet.tsx)
- [movil/src/galeria/upload.ts](../../movil/src/galeria/upload.ts)
- [movil/src/turno/ProfileProposal.test.tsx](../../movil/src/turno/ProfileProposal.test.tsx) — nuevo
- [movil/src/turno/ProfileProposal.tsx](../../movil/src/turno/ProfileProposal.tsx) — nuevo
- [movil/src/turno/TurnoCard.tsx](../../movil/src/turno/TurnoCard.tsx)
- [oficina/src/api/perfil.ts](../../oficina/src/api/perfil.ts) — nuevo
- [oficina/src/pages/Galeria.test.tsx](../../oficina/src/pages/Galeria.test.tsx)
- [oficina/src/pages/Galeria.tsx](../../oficina/src/pages/Galeria.tsx)
- [oficina/src/pages/galeria/PhotoSheet.tsx](../../oficina/src/pages/galeria/PhotoSheet.tsx)
- [oficina/src/pages/turno/ProfileProposal.test.tsx](../../oficina/src/pages/turno/ProfileProposal.test.tsx) — nuevo
- [oficina/src/pages/turno/ProfileProposal.tsx](../../oficina/src/pages/turno/ProfileProposal.tsx) — nuevo
- [oficina/src/pages/turno/TurnoCardView.tsx](../../oficina/src/pages/turno/TurnoCardView.tsx)
- [scripts/grafo/mermaid.py](../../scripts/grafo/mermaid.py)
- [scripts/qa/seleccion.json](../../scripts/qa/seleccion.json)
