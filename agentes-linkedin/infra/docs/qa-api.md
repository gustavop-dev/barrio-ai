# QA independiente: API, permisos y administración

Skill aplicada: `.agents/skills/backend-test-coverage/SKILL.md`. Revisión por comportamiento y riesgo, sin perseguir un porcentaje. Se revisó la suite existente antes de añadir casos; no se heredó su clase TestCase, evitando repetir sus pruebas.

## Alcance

59 casos nuevos: matriz anónimo/sin permiso en 13 rutas que no tenían matriz propia, validación de entradas, acceso a ejecuciones históricas, unidades inactivas, autor de memoria no falsificable, errores JSON/Unicode, acceso administrativo a trabajos/resultados/auditoría, inmutabilidad del conocimiento y revocación de credenciales sin reasignación de identidad. Las pruebas del dueño y gestor acompañan a los casos negativos para evitar endurecimiento que bloquee usos autorizados.

El harness usa casos nombrados generados desde tablas porque el runner es Django/unittest, no pytest. No hay bucles ni condicionales dentro de los casos de prueba. Se usa PostgreSQL real efímero y bloqueo de red HTTP de proveedores. Los datos son sintéticos y no se ejecutan tareas pagadas.

## Hallazgos reproducidos

1. **Acceso administrativo más amplio que API.** Staff con `view_job`, sin `manage_jobs`, veía trabajos ajenos tanto en detalle como en listado. `view_knowledgerun` permitía ver históricos sin propietario, que la API restringe. Se entregaron regresiones rojas al conductor; este filtró JobAdmin por dueño y RunAdmin por los trabajos del dueño, salvo permiso explícito `manage_jobs`.
2. **Auditoría administrativa sin permiso funcional.** Staff con `view_auditevent` podía consultar auditoría sin `manage_jobs`; la API exigía ese permiso. Regresión entregada al conductor para exigir ambos permisos.
3. **Unicode inválido en memoria anidada causaba HTTP 500.** JSON con surrogate aislado (`\\ud800`) pasaba la validación del valor y fallaba al guardarse. El conductor añadió validación UTF-8 y extendió la protección a query/task/key/evidence. Los tests verifican HTTP 400 y el campo concreto en el cuerpo.

El número JSON `1e999` ya es rechazado por el JSONField; no se recomendó cambio. NUL anidado ya estaba protegido. El panel no permite editar ni borrar unidades originales, incluso mediante POST directo de superusuario. Los campos readonly de credenciales no permiten reasignar el token a otra identidad.

## Ejecución y límites

Comando: `DJANGO_ENV=production DJANGO_TEST_DATABASE=test_linkedin_qa_api LIVE_PROVIDERS=false uv run python manage.py test team_backend.tests.test_qa_api --noinput`.

Resultado final: **59/59 casos aprobados en 11.828 s**, PostgreSQL efímero destruido al terminar. Sin incidencias de Django check. Los fallos reproducidos quedaron corregidos por el conductor y las regresiones pasaron. Log de esta ejecución: `/tmp/linkedin-qa-api.log`.

No están disponibles OPS_ROOT ni el quality gate externo; no se declara certificación formal de ese gate. Se comprobó manualmente la definición de terminado de cada caso. No se añaden pruebas para constantes, métodos de representación ni migraciones generadas: no aportan comportamiento de negocio nuevo. No es prueba de carga, seguridad perimetral de un despliegue público ni validación humana de la verdad del conocimiento. Cola, proveedor, límites monetarios y transacciones de memoria corresponden al segundo QA y a la suite existente.
