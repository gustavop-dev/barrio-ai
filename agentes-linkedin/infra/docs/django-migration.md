# Migración local a Django

Backend en Django 5.2 LTS, DRF y Gunicorn; mantiene PostgreSQL 17/pgvector y los adaptadores de IA existentes. El repositorio ai_skills_project contiene presets de desarrollo, no un runtime de agentes: se incorporaron .agents/.claude/.codex y se adaptó su metodología y CI. Origen fijado en docs/stack/source.json.

## Controles y operación

- Autenticación por sesión humana con CSRF o credencial API almacenada solo como SHA-256. Cuenta de servicio sin contraseña; roles lectura, operacion y revision. El bootstrap no reactiva tokens revocados ni cambia contraseñas existentes.
- Trabajos con propietario, UUID idempotente, límite de cola, cancelación antes de comenzar y auditoría. Los permisos se comprueban al encolar y otra vez al ejecutar.
- Worker independiente con reclamación SKIP LOCKED y latido cada 5 s. Un fallo del latido detiene nuevas reclamaciones. Sin latido durante 180 s: interrupted, sin reintento automático. Reiniciar un contenedor no repite trabajos en ejecución.
- Propuestas/confirmaciones de memoria y su auditoría se guardan atómicamente. Solo una sesión humana autorizada confirma hechos. El admin permite inspeccionar fuentes, memoria, consumo y trabajos sin editar conocimientos originales.
- API canónica /api/v1; alias previos conservados. POST /runs ahora devuelve 202, seguido de consulta GET /runs/{id}. La consola se adaptó a ese contrato.
- LIVE_PROVIDERS y los límites monetarios existentes se conservan. No hay publicación automática ni nuevas llamadas pagadas durante la migración.

## Verificación

Ensayo mediante pg_dump/pg_restore en una base separada. SHA-256 de cada fila en orden estable, por tabla: las 11 tablas históricas idénticas después de migrate/bootstrap, incluidos embeddings, revisiones, memoria, ejecuciones y ledger. Copia previa: knowledge-20261106T040852Z.dump (directorio privado backups).

Pruebas de núcleo con corpus privado: 24. Pruebas Django independientes del corpus: 16, sobre PostgreSQL real efímero, red de proveedores bloqueada. Incluyen autenticación/roles, revocación, caducidad, aislamiento de propietarios, concurrencia al reclamar, cola llena, idempotencia, interrupción sin repetición, JSON con NUL, CSRF, atomicidad de auditoría y fallo de latidos. Django check y migraciones sin drift. CI GitHub preparado; sin remoto del producto, no hay ejecución remota ni PR que reportar.

Medición local de ensayo, 10 iteraciones por ruta con Django Client: mediana /health 2.3 ms; lista de 100 unidades 10.1 ms; lista de trabajos 8.6 ms; status 76.1 ms; encolar 16.6 ms. No es prueba de carga ni SLA. Cuenta de consultas Django no incluye las conexiones psycopg del motor. Revisión adicional de código confirmó que no se retienen locks de trabajos durante solicitudes de IA.

## Límites pendientes

La oficina publicada aún no está conectada; backend disponible solo en loopback. Configurar dominio, TLS y acceso humano antes de exponerlo. El throttling local no es distribuido. Biblioteca compartida para un único equipo, no aislamiento multiempresa. Estados complete indican fin técnico; result_status y citas pueden requerir revisión. La verdad del conocimiento y los contenidos generados siguen sujetos a revisión humana. No se ejecutó un benchmark ciego nuevo ni se amplió el grafo semántico.

## Reversión

Conservar .env y volumen. Detener worker/api y comprobar trabajos activos antes de retroceder. La base conserva tablas originales compatibles con el baseline 5ed0826; las nuevas tablas Django no afectan al runtime anterior. Usar un checkout separado de ese commit, con copia privada del .env, reconstruir la API anterior y mantener el mismo proyecto/volumen Docker. No ejecutar down -v. Un restore del dump completo solo es necesario ante pérdida de datos; no hacerlo encima de actividad nueva sin conciliación. Las migraciones no eliminan las tablas históricas al revertir.

La imagen incluye el tokenizador cl100k_base con checksum verificado; el arranque y las vistas previas no requieren descargarlo.

## Resultado de activación local

API, PostgreSQL y worker saludables en Docker. Las 16 pruebas Django también pasaron en la imagen Python3.12. Se verificaron por HTTP real el login de admin, sus estilos, navegación, autorización, CSRF y el flujo POST202 → worker → complete/preview → reenvío idempotente200. La prueba añadió una sola ejecución local sin generación. Ledger y caché no cambiaron. Integridad de fuentes: passed=true, 1,035 unidades, sin errores; human_review=false.

Artefactos privados de operación: artifacts/pre-django-snapshot.json, post-django-snapshot.json, post-django-integrity.json, django-live-check.json, core-tests.log y docker-tests.log. El backend se instaló en la carpeta infra original; el worktree conserva el desarrollo. La contraseña inicial del admin se consulta en DJANGO_ADMIN_PASSWORD del .env privado, no en este documento.
