# Despliegue de Barrio AI en un servidor 24/7

Este stack levanta en un solo servidor la oficina PWA, Django, el worker, el piloto automático y PostgreSQL con pgvector. Caddy es el único servicio expuesto: obtiene el certificado HTTPS automáticamente, sirve la PWA y hace de proxy de `/api`, `/admin`, `/static` y `/health` hacia Django. Así PWA y API comparten origen, y la sesión de Django funciona con CSRF sin configurar CORS.

## 1. Servidor y dominio

- **Servidor:** Hostinger KVM 1 (1 vCPU, 4 GB, 50 GB NVMe), centro de datos en EE. UU. o Brasil, con Ubuntu 24.04 LTS. Si Hostinger ofrece la plantilla «Ubuntu 24.04 with Docker», úsala y salta la instalación de Docker. Al servidor no le toca compilar nada: GitHub Actions construye las imágenes y él solo las descarga.
- **DNS:** un registro A (y AAAA si hay IPv6) de `barrio.tudominio.com` a la IP del servidor.
- **Firewall:** abrir solo 22, 80 y 443. PostgreSQL y Django no publican puertos.
- **Docker:** instalar Docker Engine y el plugin Compose (guía oficial de Docker para Ubuntu).

## 2. Código, imágenes y configuración

Las imágenes se publican en GitHub Container Registry (privado) en cada push a `main`: `ghcr.io/gustavop-dev/barrio-ai-api` y `-web`. El servidor necesita un token de solo lectura. Créalo en https://github.com/settings/tokens/new?scopes=read:packages (classic, únicamente `read:packages`).

```bash
# En la laptop (el repo es privado: el servidor no clona, recibe solo deploy/):
rsync -a --exclude .env --exclude backups/ --exclude conocimiento/ deploy/ barrio-ai:/opt/barrio-ai/deploy/
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
- restaura la base completa (biblioteca de 1.035 unidades, embeddings, memoria, ledger, trabajos y usuarios) en una base vacía;
- copia el archivo de política que usan los agentes;
- aplica las migraciones nuevas;
- levanta todo.

Si la base ya tiene tablas, se niega a restaurar encima. Después borra el paquete del servidor y de la laptop.

Los originales del curso no viajan al servidor. Por eso `/api/v1/integrity` informa de fuentes ausentes allí: la verificación de integridad del corpus se hace en la laptop.

## 4. Comprobar

```bash
docker compose -f compose.prod.yaml ps            # api, worker, autopilot y web deben estar "healthy"
curl -fsS https://barrio.tudominio.com/health
```

Abre `https://barrio.tudominio.com`, inicia sesión e instala la PWA:
- **Android/Chrome:** desde el menú.
- **iPhone:** Compartir → «Añadir a pantalla de inicio». Es imprescindible para recibir notificaciones push.

Después, en Ajustes → activar notificaciones → «Probar».

## 5. Encender la máquina

En `.env`:
- `UNIPILE_API_KEY` y `LIVE_LINKEDIN=true`;
- `ANTHROPIC_LIMIT_USD`, que es un techo acumulado: súbelo al presupuesto acordado;
- `OPERATOR_AUTOPILOT=true`.

Luego aplica los cambios y da de alta la cuenta y los referentes:

```bash
docker compose -f compose.prod.yaml --env-file .env up -d
docker compose -f compose.prod.yaml exec api python manage.py operador --usuario gustavo cuenta --account-id acc_… --etiqueta "LinkedIn Gustavo"
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
| Copias de seguridad | `crontab -e` → `0 4 * * * /ruta/barrio-ai/deploy/backup.sh` (conserva 14 días). Guarda la base (`knowledge-*.dump`) y los audios y fotos del volumen `media` (`media-*.tar.gz`). Copia periódicamente `deploy/backups/` fuera del servidor. Restaurar los archivos: [capturas-galeria.md](../agentes-linkedin/infra/docs/capturas-galeria.md#servidor). |
| Actualizar | Tras el merge a `main` y el workflow en verde: `rsync` de `deploy/` si cambió, y `docker compose -f compose.prod.yaml --env-file .env pull && docker compose -f compose.prod.yaml --env-file .env up -d`. Las migraciones se aplican solas. |
| Volver atrás | `BARRIO_TAG=<sha de un commit anterior>` en `.env`, luego `pull` y `up -d`. Las migraciones no se deshacen solas. |
| Logs | `docker compose -f compose.prod.yaml logs -f autopilot worker`. |
| Admin | `https://barrio.tudominio.com/admin/`. |

## Seguridad

- `.env`, `backups/` y `conocimiento/` no se versionan.
- Las claves nunca llegan a la PWA.
- Las decisiones humanas (parada, veto, resolución, confirmar memoria, suscribir push) exigen sesión con CSRF.
- El login limita intentos por IP y usuario.
- HSTS se envía solo para el dominio exacto. `DJANGO_HSTS_SUBDOMAINS=true` lo extiende a los subdominios, solo si todos usan HTTPS.
