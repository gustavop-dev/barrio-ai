# Pruebas
Tests nuevos verifican comportamiento observable y documentan el fallo que detectarían. Permisos: anónimo 401, usuario sin permiso 403, usuario autorizado 200/202 y trabajo ajeno 404. PostgreSQL real y datos de prueba aislados, nunca SQLite ni proveedores pagados. Cubrir idempotencia, concurrencia, permisos, caída de worker, migración no destructiva y contrato de API.
