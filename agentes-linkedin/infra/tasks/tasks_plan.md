# Plan completado
- [x] Incorporar presets y baseline versionada.
- [x] Django/settings/migraciones y modelos de control, sin recrear datos existentes.
- [x] DRF con permisos y autenticación por sesión o credencial hash.
- [x] Cola persistente y trabajador con latidos, cancelación e interrupción explícita.
- [x] Admin de lectura del conocimiento y administración de usuarios/credenciales.
- [x] 24 pruebas del núcleo + 16 Django; ensayo PostgreSQL, revisión delegada y CI adaptada.
- [x] Docker Python 3.12: 16 pruebas Django aprobadas.
- [x] Copia de seguridad, cambio local a Django y 11 fingerprints históricos idénticos.
- [x] Prueba HTTP real de sesión/admin/CSRF, cola, worker e idempotencia; cero solicitudes pagadas.

Siguiente etapa de producto, fuera de esta migración: conectar la oficina visual a esta API y definir los demás agentes y la memoria personal de Gustavo.

- [x] QA solicitado: dos subagentes, 74 regresiones/casos nuevos, cuatro grupos de fallos corregidos y 114 tests verdes.

- [x] Oficina publicada conectada con puente privado, pruebas de interfaz y estado remoto. Prueba Claude fallida por timeout documentada, sin repetir llamada incierta.

## Próxima etapa: equipo autónomo

Referencia de dirección: [plan maestro](../docs/plan-equipo-autonomo.md).
La migración anterior permanece completada; las fases F0–F7 del plan nuevo tienen
su propio seguimiento. Siguiente incremento: contrato operativo de Estrategia y
Perfil y lectura de sus unidades. No activar los trece roles ni nuevas llamadas
pagadas como parte de la documentación.

- Diseño documental integral de equipos: ver [circuitos](../docs/circuitos-equipo.md), catálogo externo e índice de contratos. Recorrido conceptual y QA documentales separados de futuros tests runtime. Software y conexiones no implementados por instrucción del usuario.

- [x] Corregir assets de Perfil tras #90: capacidades de transparencia, recorte croma validado, diagnóstico 400 y recuperación del banner desde la sección; tests con fakes escritos.
- [ ] QA de `test_perfil_chroma`, `test_perfil_assets`, `test_perfil` y `test_imagenes` en el entorno autorizado. No ejecutados localmente; sin llamadas pagadas, builds ni despliegue en esta sesión.
- [x] Tras #91: encuadre por alfa, métricas deterministas para visión, despill cian, normalización del highlight y reutilización entre ciclos `perfil_assets`; regresiones con fakes escritas.
- [ ] Ejecutar esas regresiones en entorno autorizado y comprobar el relanzamiento productivo de `perfil_assets 8aa8c51c` con sus blobs confirmados. No se accedió a producción en esta sesión.
- [x] Tras #92: revisión separada de asset/explicación, reparación de una sección con segunda revisión única, fallback `needs_input`, evidencia de previews y conservación de A/B/topes/checkpoints. Tests con fakes escritos.
- [ ] Ejecutar `test_perfil_assets_explanation`, `test_perfil_assets`, `test_perfil`, `test_perfil_chroma` y `test_grafo` en entorno autorizado. Sin tests/builds locales ni proveedores pagados en esta sesión.
- [x] Biblioteca 01–12, fases 0–1: constantes de clases, migración 0045, ingesta 07–12 con fuentes y políticas, alcance de agentes en 01–06 y pruebas sintéticas y con corpus.
- [ ] Fase 2, con aprobación de Gustavo: `migrate` y `knowledge ingest` en la base desplegada (montar «Procesamiento clases 08-12» en el compose del runtime) y verificar 1.656 unidades; embeddings de 07–12 aparte.
- [x] Primera metodología outbound, «primer mensaje» (clase 09, BIB-10): caso `BIB-09-primer-mensaje` con línea base medida, reglas fijas de `dm_opener` con un solo redraft, seis preguntas `dm_*` en la misma revisión del líder (`review.dm_approved`), tarjeta «Mensaje sugerido» solo con `dm_approved`, siete unidades LI-09 activadas por `METODOLOGIAS_ACTIVAS` (sin ampliar `CLASES_AGENTES`), `COURSE_VERSION` `bib-v2`, registro de lectura y huella del corpus por caso. Proveedores simulados, sin envío ni topes tocados.
- [ ] Desplegar el primer mensaje solo después de la fase 2: sin las unidades 09 en la base desplegada, Relaciones no guarda primeros mensajes y la tarjeta «Mensaje sugerido» desaparece. Revisar el costo del líder con las unidades 09 en el estado.
- [ ] Siguiente metodología: «nota de invitación» (clase 09, nota de hasta 300 caracteres). Por defecto sin nota; hasta 3 al mes con `LINKEDIN_INVITE_NOTE_MONTHLY_LIMIT`. Mismo orden: caso y línea base, procedimiento, lectura, compuertas.
- [x] Sistema del comprador, fase 1: `BuyerJourney`/`BuyerTouch` (migración 0046), registro pasivo desde los puntos existentes con fallos aislados y auditados, señales entrantes y `temperature`, descanso/reintento/salida definitiva como forma y transiciones probadas, reconstrucción idempotente (`manage.py comprador reconstruir`), embudo `GET /api/v1/resultados/embudo-comprador` y arnés e2e `test_comprador_e2e.BuyerPathBase` para las fases 2–6. Sin cambio de comportamiento.
- [ ] Desplegar la fase 1: `migrate` (0046) y `manage.py comprador reconstruir --seco`, revisar cifras y tiempo, luego sin `--seco`. Comprobar `buyer.record_failed` en la auditoría la primera semana.
- [x] Fase 2 del comprador (BAR-19, COM-13, BIB-11), detrás de `BUYER_WARMUP_ENABLED` (apagado por defecto): lectura de posts de compradores con su propio tope, comentarios por grupos 6/2/2 con espera por autor, metodología `comentario_calentamiento` (clases 07 y 10) con caso, línea base y registro de lectura, invitación tras el segundo comentario, una señal o 14 días, ruta `sin_posts`, descanso a los 21 días con despertar por señal, temperatura con pesos y señales de compra de la verificación web, `GET /api/v1/red/invitaciones-pendientes`. Proveedores simulados, sin topes ni rampa tocados.
- [ ] Desplegar la fase 2 apagada (sin migraciones), cargar las clases 07 y 10 (`knowledge ingest`), y encender `BUYER_WARMUP_ENABLED` siguiendo el orden de BAR-19. Revisar a la semana `buyer.read`, `calentados_2` y los descartes `cal_*` del líder.
- [ ] Pendientes de la fase 2: acción permitida para responder en el hilo del comprador, fuente de posts para el grupo «comunidad», despertar un descanso por una señal de compra nueva.
