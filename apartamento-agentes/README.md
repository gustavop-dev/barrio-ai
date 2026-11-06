# LinkedIn Team · Oficina conectada

Oficina pixel art existente, conservando el proyecto y su acceso privado en Sites.
Django/PostgreSQL siguen en el equipo del propietario. Un puente saliente autenticado
lee comandos de una cola temporal D1; no se abren puertos de Django ni PostgreSQL.
Las claves de proveedores nunca llegan a Sites ni al navegador.

## Flujo

1. El propietario entra con su cuenta de ChatGPT.
2. La API verifica su identidad y el origen antes de aceptar un comando acotado.
3. `officebridge` reclama el comando una sola vez y llama a Django con una sesión
   del propietario y CSRF. Solo se permiten rutas definidas en el adaptador.
4. El puente entrega la respuesta. Si falla esa entrega, reenvía el resultado,
   nunca el comando. Solicitudes ambiguas expiran sin repetirse.
5. Django conserva el trabajo, las fuentes, los hechos confirmados y el ledger.

Los mensajes del puente se eliminan una hora después de expirar. El historial
durable vive en Django. No hay publicación automática a LinkedIn.
Posicionamiento y Perfil son los dos agentes activos; los demás son planificación.

## Secretos y dependencias operativas

Sites: OFFICE_OWNER_EMAIL (cuenta propietaria) y OFFICE_BRIDGE_TOKEN.
Django .env privado: OFFICE_SITE_URL, OFFICE_BRIDGE_TOKEN, OFFICE_SITE_ACCESS_TOKEN,
DJANGO_ADMIN_USERNAME y DJANGO_ADMIN_PASSWORD. El puente usa las credenciales
humanas locales solo para establecer una sesión; si se cambia la contraseña de
Django, actualizar también el .env privado. El token de acceso de Sites es exclusivo
de ese sitio, y se envía únicamente a OFFICE_SITE_URL.
La API de oficina no admite visitantes adicionales aunque se comparta posteriormente
el sitio: hay que definir membresía y mapeo de usuarios antes de ampliar el equipo.

El equipo local necesita estar encendido. La oficina indica conexión según el
latido real del puente; una caída no genera simulaciones ni trabajo automático.
Las vistas previas y búsqueda textual no usan IA pagada; el checkbox de Claude
activa ejecución y búsqueda híbrida bajo los límites existentes.

## Desarrollo y validación

Frontend en public/office.html, app.js, connection.js, style.css y assets/.
app/page.tsx redirige a la oficina; app/api/office/[...path]/route.ts usa el relay.
Conservar la integración Sites/Vinext y las migraciones Drizzle ya generadas.

- `node --test tests/relay.test.mjs`: auth, origen, idempotencia, reclamo, entrega,
  expiración, rutas y disponibilidad; SQLite real compatible con las operaciones D1.
- Build mediante helper de Sites, luego aplicar migraciones locales siguiendo el
  README del starter y ejecutar `npm run dev`.
- `.dev.vars` solo contiene configuración local; no se versiona ni publica.
- Pruebas de navegador y capturas quedan en outputs/ ignorado. Se comprobó búsqueda,
  fuente original, encargo, resultado, memoria y viewport móvil.

No se modificó el arte ni se reescribió conocimiento del curso.
