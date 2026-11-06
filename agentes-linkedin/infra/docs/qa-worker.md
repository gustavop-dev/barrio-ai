# QA 2 — cola, memoria y contabilidad de proveedores

Aplicada `.agents/skills/backend-test-coverage/SKILL.md` sobre el worktree `test/backend-qa`. Se revisaron primero `jobs.py`, el trabajador, memoria, adaptadores y las pruebas ya existentes; se añadieron únicamente comportamientos que faltaban o integración entre capas. No se modificó código de producción desde este subagente.

## Hallazgo corregido por el conductor

Los adaptadores aceptaban cantidades negativas en `usage`: Claude y embeddings podían registrar un coste negativo, reduciendo artificialmente el consumo acumulado. Embeddings además persistía el vector como si la respuesta fuera válida. Dos pruebas inicialmente rojas reprodujeron ambas rutas usando HTTP simulado. El conductor incorporó validación estricta de enteros no negativos antes de calcular el coste o guardar caché y protección de costes al liquidar. Las reservas se conservan como inciertas ante una respuesta inválida.

Durante la revisión de ese cambio se detectó una colisión entre la nueva función `token_count` y una variable local del adaptador de embeddings, que rechazaba respuestas válidas. Se notificó y el conductor renombró el validador a `validate_token_count`. La prueba concurrente de respuesta válida pasó después del arreglo.

## Cobertura nueva por comportamiento

15 casos en `src/team_backend/tests/test_qa_worker.py`:

1. Dos solicitudes simultáneas idénticas dejan un trabajo y una auditoría.
2. Un error de almacenamiento de auditoría revierte la creación del trabajo.
3. Revocar el permiso de gasto después de encolar bloquea la ejecución pagada.
4. Una respuesta HTTP ambigua conserva la reserva y no reencola el trabajo.
5. Una cita desconocida deja resultado `validation_failed`, sin aprobación humana.
6. Una respuesta tardía no revive un trabajo ya reconciliado como interrumpido.
7. Dos escritores con la misma versión esperada de memoria producen un ganador y un conflicto.
8. No se puede reutilizar como trabajo nuevo el UUID de una ejecución histórica.
9. Uso negativo de Claude: error y reserva incierta, sin crédito artificial.
10. Uso negativo de embeddings: error, reserva incierta y caché vacío.
11. Dos fallos de caché simultáneos para el mismo texto producen un vector y una sola liquidación.
12. Una ejecución guardada en `running` se conserva interrumpida sin repetir ni liberar la reserva previa.
13. Un conteo previo booleano no se transforma en un token ni inicia generación/reserva.
14. Uso fraccionario de Claude se rechaza.
15. Uso de embeddings expresado como cadena numérica se rechaza sin guardar vector.

Los tests ejercitan servicios, SQL, transacciones y concurrencia reales. Se simulan únicamente HTTP, fallo del almacenamiento de auditoría y reloj de la reconciliación. Las respuestas esperadas incluyen estados, versiones, conteos de filas y cantidades monetarias concretas. Cada test identifica en su docstring el bug que detectaría. Los tres formatos inválidos adicionales se separan por frontera del proveedor; se usa el runner unittest de Django, no parametrización pytest incompatible con su descubrimiento.

## Resultado reproducible

Comando:

```bash
DJANGO_ENV=production DJANGO_TEST_DATABASE=test_linkedin_qa_worker LIVE_PROVIDERS=false uv run python manage.py test team_backend.tests.test_qa_worker --noinput
```

Resultado final: **15 tests, 3.020 s, OK**, sin problemas en `manage.py check`. PostgreSQL real efímero; la base de pruebas se destruyó al finalizar. La prueba concurrente cierra explícitamente las conexiones ORM de sus hilos para no dejar conexiones que bloqueen esa limpieza. No se hicieron llamadas reales a proveedores ni escrituras en las tablas operativas.

## Límites de esta revisión

No se asigna objetivo porcentual ni se afirma cobertura exhaustiva. El conductor puede agregar la medición de líneas del lote integrado. No se ejecutó el gate formal de fleet: `OPS_ROOT` y su herramienta no están disponibles. Se revisó manualmente el contrato behavior-first de los nuevos casos.

Se abstuvo de añadir tests de constantes, representaciones de modelos o migraciones generadas sin comportamiento propio. Autenticación/API/admin pertenecen a QA 1. No se probó una caída real del proceso con SIGKILL mientras un proveedor remoto responde; se verificó su estado equivalente mediante reconciliación PostgreSQL y respuesta tardía simulada. No se verifican tarifas externas, facturas, crédito promocional ni calidad semántica de respuestas de IA.
