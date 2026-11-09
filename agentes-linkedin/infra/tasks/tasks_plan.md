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
