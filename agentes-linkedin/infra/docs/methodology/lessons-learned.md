# Convenciones
La aprobación del asset y la de su explicación son resultados distintos: no inferir esa distinción de una cadena de error antigua. Reparar solo campos autorizados, revisar una vez y reservar margen de llamadas para el trabajo esencial. Un layout aproximado no demuestra que exista un preview; los previews requieren hashes y revisión visual antes de acreditar comprobaciones.

En assets, separar la identidad de la petición pagada de la versión del render local. Conservar blobs confirmados entre continuaciones y fallar sin regenerar si falta storage. Las medidas exactas de color/encuadre pertenecen al render y deben viajar a visión ligadas a sus bytes; distinguir estimaciones de máscara de landmarks faciales.

No confundir integridad técnica con revisión humana. Referencias de evidencia llevan sesión. RRF calibrado se documenta como evaluación de desarrollo. Las claves solo en .env. Presets upstream son metodología, no una dependencia Python ni licencia para reescribir conocimiento.

Adoptar el stack de presets no implica instalar automáticamente sus dependencias fleet ni copiar workflows de MySQL a un proyecto PostgreSQL. Se fijó el commit de origen y se adaptó CI. No hay toolkit OPS_ROOT local, por lo que se midieron rutas localmente sin afirmar cumplimiento formal del protocolo perf-pass. La revisión delegada detectó fallos de atomicidad y latidos que las pruebas iniciales no cubrían.

Un registro que solo se añade y que se reconstruye desde varias fuentes necesita saber qué fuente manda: la fecha de un contacto (`followed_at`, `invited_at`, `connected_at`) o su historial pueden llegar al registro antes que la fila propia del hecho (la ejecución, la evidencia). Se guardan los dos y la lectura (`comprador.current`) usa la mejor fuente, en vez de editar el registro. Un gancho pasivo debe probarse también con un error de base de datos, no solo con una excepción de Python: el savepoint propio es lo que deja seguir a la transacción de la acción.
