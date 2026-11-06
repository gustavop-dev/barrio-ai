# QA del backend antes de conectar la oficina

Solicitado por Gustavo: dos subagentes independientes y la skill backend-test-coverage. Ejecución en worktree test/backend-qa, bases PostgreSQL temporales separadas, llamadas HTTP de proveedores simuladas y sin cambios de presupuesto. Los informes detallados están en qa-api.md y qa-worker.md.

## Resultado funcional

- QA API/admin: 59 pruebas nuevas aprobadas.
- QA worker/memoria/proveedores: 15 pruebas nuevas aprobadas.
- Suite Django combinada: 90 pruebas aprobadas (16 anteriores +74 nuevas).
- Motor de conocimiento: 24 pruebas aprobadas.
- Total: 114 casos de prueba verificados; incluye matrices parametrizadas de permisos y entradas.
- Django check sin incidencias; makemigrations --check sin cambios de esquema.

## Fallos reproducidos y corregidos

1. El admin permitía a staff leer trabajos ajenos e históricos aunque la API los restringía. Se aplica el mismo filtro por propietario; manage_jobs habilita supervisión global.
2. La lista administrativa de auditoría requería permiso nativo de Django pero omitía manage_jobs. Ahora exige ambos.
3. Texto Unicode inválido causaba error500 al guardar memoria anidada. Ahora se rechaza con400 y campo identificado; la protección cubre también query/task/key/evidence.
4. Ambos adaptadores aceptaban usage negativo y podían registrar costes negativos. Ahora solo admiten contadores enteros no negativos, rechazan bool/fracciones/cadenas y conservan reservas inciertas ante respuestas inválidas, sin cachear un vector inválidamente facturado.

Las regresiones se reprodujeron en rojo antes de corregir. Una colisión de nombre introducida al corregir el adaptador se detectó en la revisión cruzada y se resolvió antes del pase final. El caso de respuesta válida concurrente verifica que la protección nueva no rompe el uso normal.

## Evidencia adicional

Se verifican solicitudes simultáneas idempotentes, una sola liquidación de embeddings compartidos, atomicidad de memoria/auditoría, versiones concurrentes de memoria, permisos pagados revocados después de encolar, resultados tardíos tras interrupción y conservación de reservas inciertas sin repetir generación. Las pruebas de conocimiento original impiden modificación y borrado desde el admin, incluso con POST directo.

La medición final de team_backend es 96.6% de líneas y 72.8% de ramas (92.4% combinado), excluyendo tests y migraciones. No incluye una medición equivalente de toda la capa knowledge y no constituye certificación de seguridad. No se compara contra una lectura de cobertura anterior sobre archivos ya modificados. El porcentaje es un indicador secundario; el objetivo son los casos observables y sus regresiones.

## Reproducción

```bash
uv sync --frozen --extra test
DJANGO_ENV=production DJANGO_TEST_DATABASE=test_linkedin_qa_full LIVE_PROVIDERS=false uv run coverage run manage.py test team_backend.tests --noinput
uv run coverage report
LIVE_PROVIDERS=false uv run pytest -q
```

Los tests Django usan DB efímera real; los del núcleo usan esquema efímero y requieren el corpus privado local. CI incluye tests Django y reporte de coverage, sin umbral artificial. El repositorio no tiene origin: no hay ejecución CI remota que afirmar.

## Límites

OPS_ROOT y el quality gate externo del stack no están disponibles; se realizó revisión manual de comportamiento, asserts concretos, aislamiento, fronteras simuladas y duplicados. No se certifica ese gate formal. No hubo ensayo de carga, despliegue público, revisión del contenido por humanos ni llamadas reales nuevas a OpenAI/Anthropic. La oficina visual sigue sin conectarse. El comando worker_health se comprueba mediante Docker, sin cobertura unitaria específica de todos sus estados.

La misma suite Django de 90 casos pasó dentro de la imagen Docker Python3.12 (16.936s). Comparación de fingerprints de las 11 tablas históricas antes/después de QA: idénticos, incluido ledger y caché.

## Activación verificada

Correcciones instaladas en el backend local. API y trabajador saludables. Comprobación HTTP real: Unicode inválido 400, auditoría de servicio 403, 1,035 unidades y 11,554 vectores conservados. Fingerprints de las 11 tablas históricas idénticos también tras activar la versión; no hubo llamadas pagadas ni nuevas filas de consumo. Artefactos: artifacts/qa-runtime-check.json y post-qa-runtime-snapshot.json.
