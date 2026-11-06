# Convenciones
No confundir integridad técnica con revisión humana. Referencias de evidencia llevan sesión. RRF calibrado se documenta como evaluación de desarrollo. Las claves solo en .env. Presets upstream son metodología, no una dependencia Python ni licencia para reescribir conocimiento.

Adoptar el stack de presets no implica instalar automáticamente sus dependencias fleet ni copiar workflows de MySQL a un proyecto PostgreSQL. Se fijó el commit de origen y se adaptó CI. No hay toolkit OPS_ROOT local, por lo que se midieron rutas localmente sin afirmar cumplimiento formal del protocolo perf-pass. La revisión delegada detectó fallos de atomicidad y latidos que las pruebas iniciales no cubrían.
