# Despliegue de Barrio AI en un servidor 24/7

Este stack levanta en un solo servidor la oficina PWA, Django, dos workers (`worker` para el trabajo general y `worker-acciones` solo para escribir y conciliar en LinkedIn), el piloto automático y PostgreSQL con pgvector. Caddy es el único servicio expuesto: obtiene el certificado HTTPS automáticamente, sirve la PWA y hace de proxy de `/api`, `/admin`, `/static` y `/health` hacia Django. Así PWA y API comparten origen, y la sesión de Django funciona con CSRF sin configurar CORS.

## 1. Servidor y dominio

- **Servidor:** Hostinger KVM 1 (1 vCPU, 4 GB, 50 GB NVMe), centro de datos en EE. UU. o Brasil, con Ubuntu 24.04 LTS. Si Hostinger ofrece la plantilla «Ubuntu 24.04 with Docker», úsala y salta la instalación de Docker. Al servidor no le toca compilar nada: GitHub Actions construye las imágenes y él solo las descarga.
- **DNS:** un registro A (y AAAA si hay IPv6) de `barrio.tudominio.com` a la IP del servidor.
- **Firewall:** abrir solo 22, 80 y 443. PostgreSQL y Django no publican puertos.
- **Docker:** instalar Docker Engine y el plugin Compose (guía oficial de Docker para Ubuntu).

## 2. Código, imágenes y configuración

Las imágenes se publican en GitHub Container Registry (privado) en cada push a `main`: `ghcr.io/gustavop-dev/barrio-ai-api` y `-web`. El servidor necesita un token de solo lectura. Créalo en https://github.com/settings/tokens/new?scopes=read:packages (classic, únicamente `read:packages`).

```bash
# En la laptop (el repo es privado: el servidor no clona, recibe solo deploy/):
rsync -a --exclude .env --exclude backups/ --exclude conocimiento/ --exclude estado/ deploy/ barrio-ai:/opt/barrio-ai/deploy/
# En el servidor (ssh barrio-ai):
cat ~/.barrio-ghcr.token | docker login ghcr.io -u gustavop-dev --password-stdin   # token copiado con scp, luego borrarlo
cd /opt/barrio-ai/deploy && cp .env.example .env && chmod 600 .env   # completar todos los valores
docker compose -f compose.prod.yaml --env-file .env pull
docker compose -f compose.prod.yaml --env-file .env run --rm --no-deps api python manage.py vapid_claves
```

Las contraseñas se generan con `openssl rand -base64 36`. `DJANGO_ADMIN_*` crea el usuario humano inicial solo si la base está vacía; con una base migrada se conserva el usuario existente.

## 3. Traer los datos desde la laptop

En la laptop, con el runtime actual encendido:

```bash
./deploy/exportar-desde-laptop.sh          # genera barrio-ai-migracion-*.tar.gz (datos privados)
scp barrio-ai-migracion-*.tar.gz usuario@servidor:~/
```

En el servidor, desde `deploy/`:

```bash
./importar-en-servidor.sh ~/barrio-ai-migracion-*.tar.gz
```

El script de importación hace cuatro cosas:
- restaura la base completa (la biblioteca tal como esté en la laptop: 1.035 unidades de 01–06, o 1.656 de 01–12 si ya se aprobó y ejecutó su ingesta; embeddings, memoria, ledger, trabajos y usuarios) en una base vacía;
- copia los archivos de política de uso: el que usan los agentes y el de las clases 08–12, que ningún agente lee todavía;
- aplica las migraciones nuevas;
- levanta todo.

Si la base ya tiene tablas, se niega a restaurar encima. Después borra el paquete del servidor y de la laptop.

Los originales del curso no viajan al servidor. Por eso `/api/v1/integrity` informa de fuentes ausentes allí: la verificación de integridad del corpus se hace en la laptop.

## 4. Comprobar

```bash
docker compose -f compose.prod.yaml ps            # api, worker, worker-acciones, autopilot y web deben estar "healthy"
curl -fsS https://barrio.tudominio.com/health
```

Abre `https://barrio.tudominio.com`, inicia sesión e instala la PWA:
- **Android/Chrome:** desde el menú.
- **iPhone:** Compartir → «Añadir a pantalla de inicio». Es imprescindible para recibir notificaciones push.

Después, en Ajustes → activar notificaciones → «Probar».

## 5. Encender la máquina

Antes, el servicio `navegador` arriba y la sesión de LinkedIn abierta en él: [En el servidor](../agentes-linkedin/navegador/README.md#en-el-servidor) (o «Conectar LinkedIn» desde la app, abajo). La clave y el 2FA los escribe Gustavo en la propia página de LinkedIn; Barrio no los guarda.

En `.env`:
- `LIVE_LINKEDIN_DIRECTO=true`, `NAVEGADOR_URL=http://navegador:8790` y `NAVEGADOR_TOKEN`, el mismo que usa el servicio;
- `AI_MONTHLY_LIMIT_USD`, el presupuesto de IA de todo el equipo por mes (100 USD acordados), y `AI_DAILY_FUSE_USD`, su tope de seguridad diario;
- `OPERATOR_AUTOPILOT=true`.

Luego aplica los cambios y da de alta la cuenta y los referentes:

```bash
docker compose -f compose.prod.yaml --env-file .env up -d
docker compose -f compose.prod.yaml exec api python manage.py operador --usuario gustavo cuenta --account-id <cuenta> --etiqueta "LinkedIn Gustavo"   # <cuenta>: su nombre en el servicio navegador
docker compose -f compose.prod.yaml exec api python manage.py operador --usuario gustavo comprobar --cuenta <uuid>
docker compose -f compose.prod.yaml exec api python manage.py operador --usuario gustavo referente --cuenta <uuid> --perfil https://www.linkedin.com/in/… --motivo "…"
```

Desde ese momento el ciclo autónomo observa, redacta, aprueba por política, ejecuta y concilia. La PWA muestra todo y permite la parada total.

### Publicación diaria con la API oficial

1. En LinkedIn Developers, crea la app con los productos **Share on LinkedIn** y **Sign In with LinkedIn using OpenID Connect**. Añade la URL de retorno `https://barrio.tudominio.com/api/v1/linkedin/oauth/callback`.
2. En `.env`, completa `LINKEDIN_CLIENT_ID`, `LINKEDIN_CLIENT_SECRET`, `LINKEDIN_REDIRECT_URI` y `FIELD_ENCRYPTION_KEY`, y revisa `EDITORIAL_*`. Después, `up -d`.
3. Con la sesión iniciada en la PWA, abre `https://barrio.tudominio.com/api/v1/linkedin/oauth/start` y autoriza.
4. Cuando quieras que salgan las piezas, pon `LIVE_LINKEDIN_OFFICIAL=true` y haz `up -d`. El token dura unos 60 días: una push avisa 7 días antes de que caduque.

Detalle completo en [publicación diaria](../agentes-linkedin/infra/docs/publicacion-diaria.md).

## 6. Operación

| Tarea | Cómo |
| --- | --- |
| Parada total | Botón en la PWA (Máquina). Como emergencia sin PWA: `OPERATOR_PAUSED=true` en `.env` y `up -d`. |
| Copias de seguridad | `crontab -e` → `0 4 * * * /ruta/barrio-ai/deploy/backup.sh` (conserva 14 días). Guarda la base (`knowledge-*.dump`) y los audios y fotos del volumen `media` (`media-*.tar.gz`). Copia periódicamente `deploy/backups/` fuera del servidor. Si la copia falla, avisa en el canal de alertas de Slack (`SLACK_WEBHOOK_URL` del `.env`; vacío = sin aviso). Restaurar los archivos: [capturas-galeria.md](../agentes-linkedin/infra/docs/capturas-galeria.md#servidor). |
| Memoria | `crontab -e` → `*/5 * * * * /ruta/barrio-ai/deploy/memoria.sh`, junto a la de `backup.sh`. Avisa en el canal de alertas de Slack de memoria baja, de un contenedor que el kernel mató por memoria y de uno que Docker reinició solo. Ver [Memoria del servidor](#memoria-del-servidor). |
| Alta de un miembro | Tres comandos con ensayo (`operador alta-miembro`, `activar-miembro`, `desactivar-miembro`); paso a paso para Gustavo en [docs/alta-de-un-miembro.md](../docs/alta-de-un-miembro.md). Antes: `OPERATOR_ALERT_WEBHOOK` debe ser un canal privado del primer miembro y el cron de `memoria.sh` debe estar puesto. Activar comprueba que el servidor tenga `MEMBER_ACTIVATION_MIN_FREE_MB` (400) libres con su navegador abierto. |
| Actualizar | Tras el merge a `main` y el workflow en verde: `rsync` de `deploy/` si cambió, y `docker compose -f compose.prod.yaml --env-file .env pull && docker compose -f compose.prod.yaml --env-file .env up -d`. Las migraciones se aplican solas. |
| Volver atrás | `BARRIO_TAG=<sha de un commit anterior>` en `.env`, luego `pull` y `up -d`. Las migraciones no se deshacen solas. |
| LinkedIn directo | El servicio `navegador` y el rodaje de la fase 4 van bajo los perfiles `navegador` y `rodaje`: un `pull` o `up -d` normal no los toca. Para actualizarlos, añadir `--profile navegador --profile rodaje` a los dos. Encenderlos, entrar a mano en LinkedIn y el rodaje: [En el servidor](../agentes-linkedin/navegador/README.md#en-el-servidor). Entrar desde la app (Ajustes › Máquina) está apagado: `LINKEDIN_CONEXION_APP=true` en `.env` y `up -d web` más `--profile navegador up -d navegador` ([Conectar desde la app](../agentes-linkedin/navegador/README.md#conectar-desde-la-app)). |
| Logs | `docker compose -f compose.prod.yaml logs -f autopilot worker worker-acciones`. |
| Admin | `https://barrio.tudominio.com/admin/`. |

## Memoria del servidor

El servidor tiene 4 GB (unos 3,8 GiB para procesos) y 1 vCPU. Medido el 13/11/2026 (`docs/plan-linkedin-directo.md`, «Servidor actual»): con todo el stack arriba y ningún navegador quedaban **~2,4 GB disponibles**; con el navegador de una cuenta abierto, su contenedor ocupaba **~1 GiB** y quedaban **~1,5 GB**. El de una segunda cuenta debería dejar **~0,5 GB**: dos cuentas caben, justas. Una tercera no cabe.

**Topes por servicio** (`compose.prod.yaml`, con su porqué al lado). Son techos, no reservas: suman más que la RAM y solo impiden que un servicio se desboque. Lo que compran: un proceso desbocado (un Chromium, un tercer navegador, una fuga en un worker) muere dentro de su contenedor, que Docker reinicia, antes de que el OOM killer del kernel elija una víctima en todo el servidor.

| Servicio | Memoria | Por qué |
| --- | --- | --- |
| `db` | **sin tope**; reserva 512 MB, `oom_score_adj -500` | La base nunca debe ser la que muere: un tope la volvería víctima dentro de su propio cgroup. La reserva (memory.low) hace que el kernel recupere memoria de los demás primero: `shared_buffers` 128 MB + un backend por proceso Django (~10–20 MB cada uno) + `maintenance_work_mem` de pgvector. `-500` la pone muy por debajo de todo para el OOM killer (no `-1000`: una consulta desbocada aún se puede parar). |
| `api` | 768 MB | Maestro de gunicorn + 2 workers (cada uno un Django entero con la biblioteca, ~150–250 MB) + una subida o exportación en curso. Si se pasa, muere un worker y gunicorn levanta otro: falla una petición, el servicio sigue. |
| `worker` | 768 MB | El proceso más pesado: respuestas de IA, imágenes e infografías, transcripciones, importaciones de analítica. |
| `worker-acciones` | 512 MB | Una escritura a la vez y su relectura; lo más grande que sostiene es la imagen de un post. |
| `autopilot` | 512 MB | Un Django que solo lee la base y encola trabajos. |
| `migrate` | 512 MB | Un Django, una vez por despliegue. |
| `web` | 256 MB | Caddy: TLS, estáticos y proxy (decenas de MB). |
| `navegador` | 2304 MB (2,25 GiB), `oom_score_adj 300` | Dos navegadores: ~1 GiB medido con uno (servicio, Xvfb y Chromium) + ~0,9 GiB el segundo ≈ 1,9–2,0 GiB, más ~10 % para un feed pesado. La memoria compartida (`shm_size: 1gb`) cuenta dentro. Un tercer navegador o un renderer desbocado muere aquí (la llamada recibe 503/504 y se reintenta), y el OOM killer global lo prefiere a él antes que a la base. |
| `rodaje` | 256 MB | Un cliente HTTP del servicio navegador; no abre navegador. |

Los números por servicio son **estimaciones** sacadas del total medido: no hay todavía una medición por servicio. Hay que medirlos en el servidor (`docker stats --no-stream`, en ventana de trabajo y con los dos navegadores abiertos) y ajustar.

**Guarda del navegador.** Antes de lanzar el Chromium de una cuenta, el servicio mira la memoria libre (la menor entre `MemAvailable` y lo que queda bajo su tope). Por debajo de `NAVEGADOR_MEMORIA_MINIMA_MB` (1100 aquí: ~900 MiB de un navegador + ~200 que deben quedar para la base y los workers) contesta `503` con `code: memoria` y no sale nada; el backend la trata como un «no salió» y reintenta más tarde, sin pausar la cuenta. Un navegador se abre a la vez, para que el siguiente vea lo que tomó el anterior. Con 0 navegadores (~2,2 GiB libres) y con 1 (~1,3 GiB bajo el tope, ~1,5 GB en el servidor) abre; con 2 (~0,35–0,5) un tercero no abre. Detalle: [navegador, «Memoria»](../agentes-linkedin/navegador/README.md).

**Cierre por inactividad (`NAVEGADOR_CIERRE_INACTIVO_MIN`): apagado a propósito.** No baja el pico (con las dos cuentas trabajando a la vez hacen falta los dos navegadores), el backend llama a cada cuenta al menos cada hora, cada reapertura es una carga más del inicio que LinkedIn ve y, en 1 vCPU, le quita segundos a la llamada que la provoca. Que la sesión sobreviva al cierre depende de que Chromium escriba sus cookies al cerrarse, y eso las pruebas con el navegador falso no lo pueden mostrar. Razones completas y cuándo encenderlo: [navegador, «Memoria»](../agentes-linkedin/navegador/README.md).

**Avisos (`memoria.sh`, cron cada 5 min).** Al canal de alertas de Slack (`SLACK_WEBHOOK_URL`; vacío = solo lo escribe en la salida del cron):
- memoria disponible por debajo de `MEMORIA_ALERTA_MB` (300) dos lecturas seguidas: un aviso por episodio, y otro al volver a `MEMORIA_RECUPERADA_MB` (500) o más. 300 está por debajo de lo que dejan dos navegadores (~500): si se llega ahí, algo creció;
- un contenedor en el que el kernel mató un proceso por falta de memoria (evento `oom` de Docker), una vez por contenedor y hora;
- un contenedor que Docker reinició solo (sube su `RestartCount`). Un despliegue no cuenta: recrea los contenedores.

La URL del webhook se lee del `.env`, nunca se imprime ni pasa por la línea de órdenes. Un aviso que no sale se reintenta en la pasada siguiente. Lo ya avisado vive en `deploy/estado/` (fuera de git). Salida: 0 bien, 1 no pudo leer la memoria, 2 docker falló, 3 no salió el aviso (manda el primero). Si se quiere conservar lo que escribe (solo escribe cuando avisa o falla): `*/5 * * * * /ruta/barrio-ai/deploy/memoria.sh >> /ruta/barrio-ai/deploy/estado/memoria.log 2>&1`.

**Cuándo crecer el servidor.** Cualquiera de estas señales, medidas, basta:

| Señal | Dónde se ve | Umbral |
| --- | --- | --- |
| El kernel mató un proceso de `db`, `api`, `worker` o `worker-acciones` | Aviso de `memoria.sh` | 2 en una semana (1 en `db`: ya) |
| Memoria baja | Avisos de `memoria.sh` | Episodios en 3 o más días de una semana |
| El navegador no abre por memoria | `docker compose logs navegador \| grep "sin memoria para abrir"`; aviso «el navegador no responde» del backend (`ALERT_NAVEGADOR_DEFERRALS`) | Más de un día a la semana |
| Contenedores que se reinician solos | Aviso de `memoria.sh` | Más de uno a la semana sin causa en el código |
| Swap en uso | `free -m` (si el servidor tiene swap) | Más de 256 MB usados de forma sostenida |
| Presión de memoria | `cat /proc/pressure/memory` | `some avg300` por encima de 10 en ventana de trabajo |
| Una tercera cuenta de LinkedIn | — | Antes de darla de alta: con 4 GB no cabe (la guarda la rechaza) |

**Tamaño objetivo:** 8 GB y 2 vCPU (en Hostinger, el siguiente plan KVM). Con la misma cuenta (~1,6 GB el stack y el sistema, ~1 GiB por navegador) caben 4 navegadores con margen; al crecer, subir el tope de `navegador` a ~1 GiB por cuenta + 0,3 GiB y medir otra vez. La segunda vCPU acorta el arranque de Chromium y las pausas de los workers.

**Lo que no se puede garantizar sin medir en el servidor:**
- cuánto usa de verdad cada servicio (los topes son estimaciones) y si el segundo navegador cabe con el margen esperado;
- que la memoria compartida de Chromium (`shm_size`) y su caché no lleven el contenedor al tope en un feed pesado;
- que el evento `oom` de Docker salga también cuando quien mata es el OOM killer global (y no el tope del contenedor): depende de la versión de Docker/containerd del servidor; por eso `memoria.sh` mira además los reinicios;
- si el servidor tiene swap (con swap, la memoria baja se nota antes como lentitud que como procesos muertos);
- que el navegador conserve la sesión tras cerrarse por inactividad (por eso sigue apagado).

## Seguridad

- `.env`, `backups/`, `conocimiento/` y `estado/` no se versionan.
- Las claves nunca llegan a la PWA.
- Las decisiones humanas (parada, veto, resolución, confirmar memoria, suscribir push) exigen sesión humana: la de la PWA con CSRF o el token de dispositivo de la app móvil ([app-movil-backend.md](../agentes-linkedin/infra/docs/app-movil-backend.md)). Un token de servicio nunca decide.
- El login limita intentos por IP y usuario, y el de la app móvil comparte ese contador.
- La vista remota del navegador de LinkedIn (`/conectar/`) solo existe con `LINKEDIN_CONEXION_APP=true` y mientras dura una conexión iniciada desde la app; Caddy pregunta al backend en cada petición y solo deja pasar al navegador que canjeó el enlace de un solo uso. El servicio `navegador` no publica ningún puerto.
- HSTS se envía solo para el dominio exacto. `DJANGO_HSTS_SUBDOMAINS=true` lo extiende a los subdominios, solo si todos usan HTTPS.
