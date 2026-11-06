# Conexión de la oficina con Django

La oficina privada de Sites conserva su proyecto y su arte. Ahora tiene una API
propia y una cola temporal D1. El servicio Docker office inicia un enlace saliente
para recibir comandos permitidos y devolver resultados; no se exponen puertos de
Django ni PostgreSQL fuera del equipo. Las claves de proveedores siguen locales.

Sites exige identidad del propietario y origen de la misma página. El puente usa
una clave exclusiva y el acceso privado de ese Site; no puede crear solicitudes
en nombre del usuario a través del endpoint de puente. Reclamo atómico, IDs estables,
cola acotada y expiración sin reencolar. Solo se reintenta entregar respuestas ya
obtenidas, nunca repetir un comando ambiguo. Los tickets temporales se limpian una
hora tras expirar; Django conserva el historial y los costes.

El puente establece una sesión humana en Django con las credenciales privadas del
propietario, y usa CSRF en cada POST. Esto permite confirmar memoria únicamente
tras el botón explícito del propietario en su oficina autenticada. Si cambia la
contraseña de Django, actualizar DJANGO_ADMIN_PASSWORD en .env y recrear office.
No existe un proxy abierto: office_bridge.py define exactamente las operaciones.

Activos: Posicionamiento y Perfil. Otros equipos conservan planificación local.
Las fuentes se consultan sin reescribirlas. Los datos personales se proponen antes
de confirmar; notas antiguas del navegador no se convierten solas en hechos.
Vista previa por defecto sin IA pagada. La opción Claude activa generación y
búsqueda híbrida bajo los límites existentes.

## Pruebas

7 casos del adaptador: rutas permitidas, UUID obligatorio, identidad no inyectable,
entrega sin reejecución, timeout ambiguo, CSRF de confirmación y fallo de login.
Suite Django completa: 97 aprobados. Relay del Site: 10 casos con SQLite real,
autenticación, origen, cola, reclamo, respuesta, expiración y estado offline.
Navegador Chromium: búsqueda, 8 fuentes, lectura original, vista previa real,
memoria, viewport móvil sin overflow y sin errores JS. Se conservaron las capturas
en outputs/ del frontend, fuera del control de versiones.

Una prueba real con Claude falló por ReadTimeout. Job:
b17514f0-7597-40fb-80e5-6ab75178d19e. No se repitió. Reserva incierta Anthropic:
USD 0.085902; no es gasto confirmado. La consulta nueva de embeddings OpenAI costó
USD 0.00000134. La interfaz muestra No completado y Reserva retenida. Este resultado
no acredita generación exitosa en esta ronda; sí la conexión, el encargo persistido,
la protección monetaria y la presentación del error. La vista previa real anterior
sí terminó correctamente. Revisar consumo del proveedor antes de repetir esa tarea.

## Operación

`docker compose up -d` inicia api/db/worker/office. La oficina debe mostrar backend
desconectado cuando el equipo se apaga o falta su latido. Salud del bridge cada 20s,
latido máximo 60s. No cambia el presupuesto ni publica contenido en LinkedIn.
El Site conserva acceso solo para su propietario. Compartir la oficina con más
personas requeriría un mapeo explícito de identidades y permisos por usuario.

Publicación verificada: https://apartamento-agentes.elcerrotico.chatgpt.site
El latido remoto en D1 informa 1,035 unidades; los cuatro servicios Docker están
saludables. Un token de servicio no puede crear comandos humanos (HTTP 401 probado
en el Site publicado). La prueba de navegador completa se hizo en preview local
con Django real; no se automatizó la sesión humana de ChatGPT en producción.
Las fuentes originales mantienen passed=true; el caché tiene 11,555 vectores
tras añadir la consulta semántica real. La memoria personal permanece vacía.
