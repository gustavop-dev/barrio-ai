# Servicio navegador

LinkedIn sin Unipile (fase 2 de `docs/plan-linkedin-directo.md`). Un Chromium por cuenta, con su perfil guardado,
que hace **cada** llamada a LinkedIn desde la página de LinkedIn con la sesión abierta, como la haría la propia
página. Nada sale hacia LinkedIn desde fuera de esa página. El servicio devuelve la respuesta de LinkedIn tal cual;
quien la juzga y la lee es el backend (`agentes-linkedin/infra/src/linkedin_directo`, conector `directo`).

El contrato entre los dos lados está en `agentes-linkedin/infra/docs/navegador-contrato.md`.

## Qué cuida el servicio

- **Una llamada a la vez por cuenta**, y antes de cada una una pausa al azar de 3 a 7 s (configurable, nunca
  menos de 3 s).
- **Topes por cuenta** por hora y por día, lecturas y escrituras por separado. Agotado un tope, la llamada no sale y
  el backend recibe `422` («no salió nada»).
- **Lista permitida** revisada otra vez aquí: una escritura que no está en la lista no sale aunque el backend la
  pida.
- **Una escritura no se repite.** Cada una lleva un `request_id`; si llega otra vez con el mismo, se devuelve la
  respuesta guardada o, si no se sabe cómo terminó, `409` sin volver a enviarla.
- **Parada.** Si LinkedIn pide entrar de nuevo, verificar, resolver un CAPTCHA, responde 401/403/429/999, redirige,
  o desaparece la cookie de sesión, la cuenta queda **detenida** (se guarda en disco) y todo recibe `409` hasta
  que alguien la revise y la reanude. Nunca intenta saltarse nada.
- **Sin sesión**, `423`: alguien tiene que entrar a mano.
- **Registro sin datos**: solo método, ruta sin ids, estado y tiempos. Nunca cookies, tokens, cuerpos ni datos de
  otras personas.

## Dónde guarda las cosas

`NAVEGADOR_DATOS` (por defecto `./datos`, en el contenedor `/datos`):

```
cuentas/<cuenta>/perfil/          el perfil de Chromium (la sesión de LinkedIn vive aquí)
cuentas/<cuenta>/detenida.json    existe solo si la cuenta está detenida: desde cuándo y por qué
cuentas/<cuenta>/consumo.json     las llamadas de las últimas 24 h (para los topes)
cuentas/<cuenta>/escrituras/      una ficha por request_id de escritura (7 días)
canario/                          los informes del canario
```

El nombre de la cuenta es el `external_account_id` de la cuenta en Barrio. Esa carpeta tiene sesiones abiertas de
LinkedIn: tratarla como una contraseña.

## Correrlo en la laptop

Necesita [uv](https://docs.astral.sh/uv/) y una pantalla (el navegador se ve; en WSL, `DISPLAY=:0`).
`linkedin_directo` no es una dependencia del proyecto: se toma del código del backend con `PYTHONPATH`.

```bash
cd agentes-linkedin/navegador
uv sync --frozen
uv run patchright install chromium            # una vez
export PYTHONPATH=../infra/src NAVEGADOR_DATOS=~/barrio-navegador
export NAVEGADOR_TOKEN=$(openssl rand -hex 32)  # el mismo valor va al backend

uv run python -m navegador login prueba        # abre LinkedIn; entras tú y cierras la ventana
# o, si ya hay un perfil con sesión (por ejemplo el del spike), se COPIA; el original no se toca:
uv run python -m navegador importar ../../spikes/linkedin-directo/.perfil-prueba prueba

uv run python -m navegador servir              # http://127.0.0.1:8790
uv run python -m navegador estado              # sesión, parada y consumo de cada cuenta
uv run python -m navegador canario prueba      # la revisión diaria de solo lectura, con el servicio en marcha
uv run python -m navegador reanudar prueba     # quitar una parada, después de entender por qué ocurrió
```

En el backend: `LIVE_LINKEDIN_DIRECTO=true`, `NAVEGADOR_URL=http://127.0.0.1:8790` y el mismo `NAVEGADOR_TOKEN`.

`login` y `importar` no tocan un perfil que otro navegador tiene abierto (esperan 30 s hasta 5 veces); con el
servicio usando esa cuenta, hay que detenerlo antes.

El canario termina con 0 (todo bien), 2 (algo se rompió: LinkedIn cambió una respuesta), 3 (la cuenta se detuvo:
no reintentar, revisar a mano) o 4 (no corrió).

## Ajustes

| Variable | Por defecto | Qué es |
|---|---|---|
| `NAVEGADOR_TOKEN` | — | Obligatorio (24 caracteres o más) para `servir` y `canario`; sin él no arranca |
| `NAVEGADOR_DATOS` | `./datos` | Carpeta de datos |
| `NAVEGADOR_HOST`, `NAVEGADOR_PUERTO` | `127.0.0.1`, `8790` | Dónde escucha (`0.0.0.0` en el contenedor) |
| `NAVEGADOR_PAUSA_MIN`, `NAVEGADOR_PAUSA_MAX` | `3`, `7` | Pausa antes de cada llamada, en segundos (mínimo 3, máximo 15) |
| `NAVEGADOR_LECTURAS_HORA`, `NAVEGADOR_LECTURAS_DIA` | `60`, `300` | Topes de lecturas por cuenta |
| `NAVEGADOR_ESCRITURAS_HORA`, `NAVEGADOR_ESCRITURAS_DIA` | `6`, `30` | Topes de escrituras por cuenta |
| `NAVEGADOR_RECARGA_HORAS` | `6` | Cada cuánto se recarga la página de inicio de una cuenta |
| `NAVEGADOR_HEADLESS` | `false` | Sin ventana. No se recomienda, y la imagen no trae ese Chromium: en el servidor la ventana va a una pantalla virtual |

## En el servidor

**Pendiente de probar en el servidor.** Está montado pero apagado:

- La imagen `ghcr.io/gustavop-dev/barrio-ai-navegador` se construye en cada push a `main`.
- En `deploy/compose.prod.yaml` el servicio `navegador` está bajo el perfil `navegador`: un `up -d` normal no lo
  arranca. No publica puertos y Caddy no lo expone; el backend lo alcanza en `http://navegador:8790` por la red
  interna. Sus datos van en el volumen `navegador-datos`.
- Dentro del contenedor el navegador dibuja en una pantalla virtual (Xvfb) y corre con ventana, como en un
  escritorio.

Encenderlo, cuando toque (fase 4):

```bash
cd /opt/barrio-ai/deploy   # con NAVEGADOR_TOKEN en .env
docker compose -f compose.prod.yaml --env-file .env --profile navegador pull navegador
docker compose -f compose.prod.yaml --env-file .env --profile navegador up -d navegador
```

### Entrar a mano en LinkedIn desde el servidor

La clave y la verificación las escribe la persona en la ventana del navegador; nunca pasan por un programa. El
servidor no tiene pantalla, así que esa ventana se ve por noVNC, atado al `127.0.0.1` del servidor y alcanzado por
un túnel SSH, y solo mientras dura el inicio de sesión.

1. Detener el servicio si está corriendo (el perfil de una cuenta lo usa un solo navegador a la vez):
   `docker compose -f compose.prod.yaml --env-file .env --profile navegador stop navegador`
2. En el servidor, abrir el navegador de la cuenta con la pantalla visible por noVNC:
   ```bash
   docker compose -f compose.prod.yaml --env-file .env --profile navegador run --rm \
     -e NAVEGADOR_VNC=1 -p 127.0.0.1:6080:6080 navegador python -m navegador login <cuenta>
   ```
   Imprime una clave de un solo uso para la pantalla.
3. En la laptop, el túnel: `ssh -N -L 6080:127.0.0.1:6080 barrio-ai` y abrir
   `http://127.0.0.1:6080/vnc.html` con esa clave.
4. Entrar en LinkedIn en esa ventana. Al ver el inicio, cerrar la pestaña (Ctrl+W). El comando dice si la sesión
   quedó guardada y el contenedor desaparece con la pantalla.
5. Volver a encender el servicio (`up -d navegador`) y, si la cuenta estaba detenida y ya se sabe por qué,
   `docker compose ... run --rm navegador python -m navegador reanudar <cuenta>`.

`estado` y `canario` se corren igual: `docker compose ... exec navegador python -m navegador estado`.

## Pruebas

`tests/` corre el servicio entero sobre un navegador falso (sin Chromium y sin LinkedIn): token, códigos de
respuesta, una llamada a la vez, la pausa mínima, los topes, la lista permitida, los `request_id`, la parada y su
reanudación, la falta de sesión, las cabeceras y que el registro no guarde secretos. Corren en CI (job
`navegador` de `.github/workflows/barrio-ai.yml`):

```bash
PYTHONPATH=../infra/src uv run python -m unittest discover -s tests -t . -v
```
