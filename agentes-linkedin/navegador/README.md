# Servicio navegador

LinkedIn sin Unipile (fase 2 de `docs/plan-linkedin-directo.md`). Un Chromium por cuenta, con su perfil guardado,
que hace **cada** llamada a LinkedIn desde la página de LinkedIn con la sesión abierta, como la haría la propia
página. Nada sale hacia LinkedIn desde fuera de esa página. El servicio devuelve la respuesta de LinkedIn tal cual;
quien la juzga y la lee es el backend (`agentes-linkedin/infra/src/linkedin_directo`, conector `directo`).

El contrato entre los dos lados está en `agentes-linkedin/infra/docs/navegador-contrato.md`.

## Qué cuida el servicio

- **Una llamada a la vez por cuenta**, y antes de cada una una pausa al azar de 3 a 7 s (configurable, nunca
  menos de 3 s).
- **Topes por cuenta** por hora y por día, lecturas y escrituras por separado, y además un tope por día para cada
  tipo de escritura (comentarios y respuestas, reacciones, seguimientos, invitaciones, aceptaciones). Agotado uno, la
  llamada no sale y el backend recibe `422` con `code: budget` y los segundos que faltan para que haya cupo
  (`retry_after`). El backend no pausa la cuenta ni lo toma por un límite de LinkedIn: la acción queda aprobada y se
  reintenta después. Los números salen del ritmo real (ver [Topes frente al ritmo real](#topes-frente-al-ritmo-real)).
- **Lista permitida** revisada otra vez aquí: una escritura que no está en la lista no sale aunque el backend la
  pida.
- **Una escritura no se repite.** Cada una lleva un `request_id`; si llega otra vez con el mismo, se devuelve la
  respuesta guardada o, si no se sabe cómo terminó, `409` sin volver a enviarla.
- **Parada.** Si LinkedIn pide entrar de nuevo, verificar, resolver un CAPTCHA, responde 401/403/429/999, redirige,
  o desaparece la cookie de sesión, la cuenta queda **detenida** (se guarda en disco) y todo recibe `409` hasta
  que alguien la revise y la reanude. Nunca intenta saltarse nada.
- **Sin sesión**, `423`: alguien tiene que entrar a mano.
- **Memoria.** Con el navegador de una cuenta abierto, el contenedor ocupaba en el servidor cerca de **1 GiB** (medido
  el 13/11/2026 tras un canario de 16 llamadas). El navegador queda abierto. Opcional y apagado:
  `NAVEGADOR_CIERRE_INACTIVO_MIN` lo cierra tras esos minutos sin llamadas y la siguiente llamada lo abre otra vez. Solo
  compensa con varias cuentas en un servidor pequeño: el backend llama al menos cada hora (bandeja, comentarios de
  posts propios, referentes cada 3 h, acciones durante el día), así que casi siempre cerraría para volver a abrir, y
  cada reapertura es una carga más del inicio que LinkedIn ve. Nunca se cierra con una llamada en curso o esperando. No
  se usa ninguna bandera de Chromium ni bloqueo de imágenes para ahorrar memoria: cambiarían cómo LinkedIn ve el
  navegador.
- **Sin pantalla**, `503`: el navegador va con ventana sobre una pantalla virtual (Xvfb). Si no responde, no se abre
  nada, la llamada recibe `503` («sin pantalla») y `/health` contesta `503` con `sin_pantalla`. Al arrancar, el
  contenedor borra el candado y el socket que deja la pantalla de la vez anterior (un `restart` conserva `/tmp`), espera
  a que la nueva acepte conexiones y, si no lo hace, termina con error para que Docker lo vuelva a arrancar.
- **Una sola salida a internet por sesión.** Que una sesión aparezca desde otra IP es lo primero que hace que
  LinkedIn la cierre. El navegador de cada cuenta sale directo o por un proxy (`NAVEGADOR_PROXY`); la cuenta recuerda
  por cuál salió la última vez (solo una etiqueta: `directo` o un resumen del servidor y el puerto, nunca la dirección
  ni la clave). Si la salida configurada cambia, la cuenta no se abre (`503` con `code: egress` y desde cuándo,
  «no salió nada») hasta que alguien lo confirme con `python -m navegador salida <cuenta> --aceptar`. Un perfil
  importado de otro equipo también espera esa confirmación. El backend avisa de eso una vez en Notificaciones
  (`navegador_salida`), sin pausar la cuenta: lo pendiente espera y sale solo cuando la salida queda resuelta.
- **Registro sin datos**: solo método, ruta sin ids, estado y tiempos. Nunca cookies, tokens, cuerpos ni datos de
  otras personas.

## Dónde guarda las cosas

`NAVEGADOR_DATOS` (por defecto `./datos`, en el contenedor `/datos`):

```
cuentas/<cuenta>/perfil/          el perfil de Chromium (la sesión de LinkedIn vive aquí)
cuentas/<cuenta>/perfil-en-uso.lock  tomado (flock) mientras un navegador nuestro tiene abierto el perfil, también
                                  desde otro contenedor; el sistema lo suelta al terminar el proceso
cuentas/<cuenta>/detenida.json    existe solo si la cuenta está detenida: desde cuándo y por qué
cuentas/<cuenta>/consumo.json     las llamadas de las últimas 24 h (para los topes)
cuentas/<cuenta>/salida.json      la etiqueta de la última salida a internet de su sesión
cuentas/<cuenta>/salida-rechazada.json  desde cuándo rechaza otra salida (solo una hora; se borra al resolverse)
cuentas/<cuenta>/escrituras/      una ficha por request_id de escritura (7 días)
cuentas/<cuenta>/rodaje/          el rodaje de la fase 4: un resumen por día y lo ya hecho (solo resúmenes con sal)
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
uv run python -m navegador estado              # sesión, parada, salida y consumo de cada cuenta
uv run python -m navegador salida prueba       # su salida a internet; con --aceptar pasa a la configurada
uv run python -m navegador canario prueba      # la revisión diaria de solo lectura, con el servicio en marcha
uv run python -m navegador reanudar prueba     # quitar una parada, después de entender por qué ocurrió
```

En el backend: `LIVE_LINKEDIN_DIRECTO=true`, `NAVEGADOR_URL=http://127.0.0.1:8790` y el mismo `NAVEGADOR_TOKEN`.

`login` y `importar` no tocan un perfil que otro navegador tiene abierto (esperan 30 s hasta 5 veces); con el
servicio usando esa cuenta, hay que detenerlo antes.

El canario termina con 0 (todo bien), 2 (algo se rompió: LinkedIn cambió una respuesta), 3 (la cuenta se detuvo:
no reintentar, revisar a mano) o 4 (no corrió). Son las mismas 14 lecturas (16 llamadas) que el backend corre solo
una vez al día por cuenta `directo` (el trabajo `check_linkedin`, la «Prueba diaria» de
`docs/plan-linkedin-directo.md`); las dos pasan por `/llamadas`, así que gastan los mismos topes y respetan las
mismas paradas. Qué se lee y qué campos debe traer cada respuesta está en `linkedin_directo/canario.py`.

## Ajustes

| Variable | Por defecto | Qué es |
|---|---|---|
| `NAVEGADOR_TOKEN` | — | Obligatorio (24 caracteres o más) para `servir` y `canario`; sin él no arranca |
| `NAVEGADOR_DATOS` | `./datos` | Carpeta de datos |
| `NAVEGADOR_HOST`, `NAVEGADOR_PUERTO` | `127.0.0.1`, `8790` | Dónde escucha (`0.0.0.0` en el contenedor) |
| `NAVEGADOR_PAUSA_MIN`, `NAVEGADOR_PAUSA_MAX` | `3`, `7` | Pausa antes de cada llamada, en segundos (mínimo 3, máximo 15) |
| `NAVEGADOR_LECTURAS_HORA`, `NAVEGADOR_LECTURAS_DIA` | `150`, `1000` | Topes de lecturas por cuenta |
| `NAVEGADOR_ESCRITURAS_HORA`, `NAVEGADOR_ESCRITURAS_DIA` | `15`, `100` | Topes de escrituras por cuenta, todas juntas |
| `NAVEGADOR_COMENTARIOS_DIA` | `30` | Comentarios y respuestas por día (INT-03 e INT-04) |
| `NAVEGADOR_REACCIONES_DIA` | `30` | Reacciones por día (INT-02) |
| `NAVEGADOR_SEGUIMIENTOS_DIA` | `30` | Seguimientos por día (RED-01) |
| `NAVEGADOR_INVITACIONES_DIA` | `30` | Invitaciones por día (RED-02) |
| `NAVEGADOR_ACEPTACIONES_DIA` | `15` | Aceptaciones por día (RED-04) |
| `NAVEGADOR_RECARGA_HORAS` | `6` | Cada cuánto se recarga la página de inicio de una cuenta |
| `NAVEGADOR_CIERRE_INACTIVO_MIN` | vacío (`0`, nunca) | Cerrar el navegador de una cuenta tras estos minutos sin llamadas; ver «Memoria» arriba |
| `NAVEGADOR_PROXY` | vacío (`directo`) | Por dónde sale a internet el navegador de cada cuenta: `esquema://servidor:puerto` con `http`, `https` o `socks5`. Sin usuario ni clave en la dirección |
| `NAVEGADOR_PROXY_CUENTAS` | vacío | Una salida propia por cuenta: `cuenta=esquema://servidor:puerto` o `cuenta=directo`, separadas por comas |
| `NAVEGADOR_PROXY_USUARIO`, `NAVEGADOR_PROXY_CLAVE` | vacío | Credenciales del proxy, juntas. Solo con `http` o `https` (Chromium no las admite en `socks5`). Se leen del entorno y no se escriben en disco ni en el registro |
| `NAVEGADOR_HEADLESS` | `false` | Sin ventana. No se recomienda, y la imagen no trae ese Chromium: en el servidor la ventana va a una pantalla virtual |

Las horas y los días de los topes son ventanas móviles (las últimas 60 min, las últimas 24 h). `0` en un tope
cierra ese tipo de llamada.

## Salida a internet

Por qué: LinkedIn liga una sesión a la red desde la que se usa. Una sesión que salta de IP (la casa de alguien un
día, un centro de datos al siguiente) es la causa más probable de que la anule o pida verificarla. Por eso el
servicio no cambia de salida por su cuenta:

- La salida se aplica al abrir el navegador de la cuenta: en `servir`, en `login` y, como el canario va por el
  servicio, también en `canario`.
- La primera vez que una cuenta se abre, guarda su etiqueta en `salida.json`. `importar` guarda `otro-equipo`: esa
  sesión salía desde otra máquina.
- Si la salida configurada no coincide con la guardada, ni el servicio ni `login` la abren. `salida <cuenta>` muestra
  las dos; `salida <cuenta> --aceptar` guarda la configurada. Hacerlo solo cuando el cambio es a propósito (por
  ejemplo, al pasar al túnel de casa) y, si se puede, entrar a mano otra vez desde la nueva salida.
- El plan es salir por un equipo de la casa de Gustavo a través de un túnel (ver `docs/plan-linkedin-directo.md`):
  `NAVEGADOR_PROXY=socks5://<extremo del túnel en el servidor>:<puerto>`.

## Topes frente al ritmo real

Lo que cuesta en LinkedIn un día completo de producción de **una** cuenta, sacado del código el 13/11/2026 con los
ajustes de producción: hasta 10 comentarios al día (5 el fin de semana), respuestas y reacciones hasta sus topes,
20 seguimientos, 16 a 20 invitaciones (la rampa), 10 aceptaciones, 6 borradores de comentario
(`OPERATOR_DAILY_PROPOSALS`) y dos rondas de red (`NETWORK_BATCHES`). El post del día sale por la API oficial y no
pasa por este servicio. «Llamada» es una petición a LinkedIn; es lo que cuentan los topes.

**Escrituras.** Cada ejecución empieza leyendo `/me` (`operador.execute`) y confirma releyendo:

| Capacidad | Escrituras al día | Lecturas por escritura | Lecturas al día |
| --- | --- | --- | --- |
| INT-03 comentar | 10 | 4: `/me`, los comentarios del post (no repetir), la página del post (plantilla), la relectura | 40 |
| INT-04 responder en posts propios | 10 | 4: `/me`, el hilo, la página del post, la relectura del hilo | 40 |
| INT-02 reaccionar | 20 | 1 en un comentario (`/me`); 3 en un post (`/me`, el post antes y después) | hasta 60 |
| RED-01 seguir | 20 | 5: `/me`, el perfil antes (2) y después (2) | 100 |
| RED-02 invitar | 16 a 20 | 5, como seguir | hasta 100 |
| RED-04 aceptar | 10 | 4: `/me`, las invitaciones recibidas, el perfil después (2) | 40 |
| CONT-09 post del día | 0 aquí | 4: los posts propios antes y después (`/me` y la lista, dos veces) | 4 |
| **Total** | **hasta 90** | | **hasta 384** |

Fuentes: `operador.execute`, `red.execute_action`, `respuestas.execute_action`, `operador._publish` y el número de
llamadas de cada operación en `linkedin_directo/cliente.py`.

**Lecturas de los trabajos del autopiloto:**

| Trabajo | Cada cuánto | Llamadas por vez | Al día | Fuente |
| --- | --- | --- | --- | --- |
| Referentes (DESC-04) | cada 3 h | 1 por referente activo (hasta 15) | hasta 120 | `autopiloto._observe`, `operador.observe`, `referentes.py` |
| Borradores de comentario | 6 al día | 2: `/me` y los comentarios del post | 12 | `operador.propose_comment` |
| Bandeja | cada hora | 3: `/me` dos veces y la lista; más los hilos con mensajes nuevos | 72 + hasta 60 | `conversaciones.read_inbox` y sus topes |
| Descubrir (DESC-05) | cada 6 h | `/me`, hasta 5 posts de referentes y 2 búsquedas | 32 (+3 una vez: la ubicación) | `red.discover`, `red.search_location` |
| Sincronizar la red | cada 6 h | 2: invitaciones recibidas y enviadas | 8 | `red.sync` |
| Métricas (APRE-01) | cada 3 h, si toca | posts propios, post, comentarios, audiencia, visitas | ~15; tope 66 | `metricas.collect` y sus topes |
| Comentarios en posts propios | cada 2 h los 3 primeros días del post, luego cada 12 h hasta el día 7 | `/me`, comentarios e hilos | ~45; tope 112 | `respuestas.read` y sus topes |
| Analítica | una vez al día | 5 exportaciones: 14 días y 7, 28, 90 y 365 | 5 | `analitica.run` |
| Prueba diaria | una vez al día; si no pudo correr, otra vez a la hora (hasta 3) | 16 | 16 (hasta 48) | `team_backend/canario.py`, `linkedin_directo/canario.py` |
| Conciliación | solo escrituras sin confirmar | 1 o 2 | ~10 | `operador.reconcile` |

**Perfiles.** Leer un perfil son 2 llamadas (el perfil y su tarjeta). Las lecturas de perfil de seguir, invitar,
aceptar, clasificar (`red._enrich`, 10 personas cada 30 min), sincronizar y referentes comparten un tope de 80
perfiles al día (`OPERATOR_PROFILE_READ_DAILY_LIMIT`): como mucho 160 llamadas. Con 20 seguimientos y 20
invitaciones ese tope ya se llena solo con ellas (4 perfiles por persona).

**Total de un día:** hasta unas **880 lecturas** (204 de las ejecuciones fuera de perfiles, 513 de los trabajos y
160 de perfiles) y **90 escrituras**. Un día normal, con menos referentes y menos comentarios que leer, ronda las
650 lecturas. La hora más cargada es una de las rondas de red: unas 11 escrituras (espaciado de 3 a 8 min) con sus
55 lecturas, más una clasificación, referentes y bandeja: hasta unas 150 lecturas.

**Topes elegidos** (por cuenta; antes 60/300 lecturas y 6/30 escrituras, que frenaban una ronda de red):

| Tope | Valor | Frente al ritmo real |
| --- | --- | --- |
| Lecturas por hora | 150 | La hora más cargada estimada |
| Lecturas por día | 1000 | Unas 880 como mucho |
| Escrituras por hora | 15 | Una ronda hace unas 11 por hora; lo que pase de 15 espera |
| Escrituras por día, todas | 100 | 90 como mucho |
| Comentarios y respuestas, reacciones, seguimientos, invitaciones | 30 cada uno por día | 20 cada uno |
| Aceptaciones | 15 por día | 10 |

El operador cuenta por día local y aquí se cuentan 24 h móviles, que pueden juntar la tarde de un día con la mañana
del siguiente: por eso cada tipo tiene más o menos 1,5 veces el tope del operador. Siguen siendo una red de
seguridad detrás de los topes del operador, no el ritmo: si un error del backend repitiera llamadas, se cortan aquí.
Lo que más lee es la revisión de referentes (hasta 120 al día); pasarla a cada 6 h
(`OPERATOR_OBSERVE_EVERY_MINUTES=360`) la deja en la mitad.

## Rodaje

La fase 4 de `docs/plan-linkedin-directo.md`: antes de pasar la cuenta real, una cuenta **de prueba** hace en el
servidor, durante una o dos semanas, un día de producción tras otro, para saber si LinkedIn tolera la IP del servidor
y el ritmo. `python -m navegador rodaje <cuenta>` habla solo con el servicio en marcha, igual que el backend (mismo
cliente, mismas llamadas, mismos topes, paradas, lista permitida y `request_id`), y nada más: sin backend, sin base de
datos, sin propuestas y sin IA.

**Un día entre semana**, entre las 08:00 y las 20:00 de America/Bogota, al ritmo por hora de producción:

| Rutina | Veces | Qué lee (como en producción) |
| --- | --- | --- |
| Descubrir | 2 | `/me`, el typeahead de ubicación (una vez al día) y 2 búsquedas de personas con ese lugar (`red.discover`) |
| Referentes | 4 | Los posts de las 15 personas del día (`operador.observe`) |
| Perfiles | 8 | 5 perfiles con su tarjeta (`red._enrich`) |
| Borradores | 6 | `/me` y los comentarios de un post (`operador.propose_comment`) |
| Bandeja | 12 | `/me`, los chats y los mensajes de los no leídos (`conversaciones.read_inbox`) |
| Posts propios | 6 | `/me`, los posts propios y los comentarios e hilos de los de la semana (`respuestas.read`) |
| Métricas | 4 | Posts propios, el último y sus comentarios, audiencia y visitas (`metricas.collect`) |
| Red | 3 | Invitaciones recibidas y enviadas, y aceptar las recibidas (`red.sync`, RED-04) |
| Analítica | 1 | Una exportación, los últimos 28 días |
| Canario | 1 | La prueba diaria: 14 lecturas, 16 llamadas |

Y unas pocas escrituras inofensivas, cada una leída antes y después como en producción:

| Escritura | Por defecto al día | A quién |
| --- | --- | --- |
| Reacción «me gusta» | 6 | Posts públicos grandes (50 reacciones o más) de personas, nunca de páginas |
| Seguir | 4 | Autores de esos posts, si no se les sigue ni son contactos |
| Invitar, sin nota | 2 | Creadores (5000 seguidores o más) fuera de la red (3.er grado o más), sin invitación pendiente |
| Aceptar | 5 | Invitaciones reales recibidas de personas (la lista ya deja fuera boletines y páginas) |
| Comentar, responder | 0 | Solo con un número explícito y textos propios (`--textos`), cada uno una sola vez |

Comentar en posts ajenos desde una cuenta de prueba es spam para esas personas: por eso va en 0 y nunca se genera un
texto. Una respuesta solo va en un hilo de un post **propio** (INT-04). Nunca deja de seguir, retira, borra ni manda
un mensaje: el cliente no tiene esas llamadas y la lista permitida las rechaza.

En total, unas **290 a 330 lecturas y 12 escrituras** (más hasta 5 aceptaciones, si alguien invitó a la cuenta). El
fin de semana, la mitad: unas 150 lecturas, 3 reacciones, 2 seguimientos, 1 invitación y hasta 2 aceptaciones (la
analítica y el canario no bajan). `--escala` multiplica las lecturas (hasta 3, unas 880 al día: el día más cargado de
producción, por debajo del tope de 1000 del servicio).

**Cómo reparte el día.** Cada rutina se reparte en el horario con un desfase al azar (nunca una rejilla), alrededor
de una pausa larga de 60 a 120 min cerca del mediodía. Descubrir y referentes van en los primeros 25 min, para tener
de dónde escoger; la primera escritura, 45 min después de empezar, y entre dos escrituras al menos 20 min (las
aceptaciones de una misma ronda de red, de 3 a 8 min, como en producción). Un día se planea con una semilla de la
cuenta y la fecha: si el contenedor se reinicia, ese día sale igual, corre solo lo que queda por delante y lo que ya
salió cuenta en los topes del día.

**Nunca dos veces.** Ninguna publicación, persona, invitación o texto se toca dos veces, ni entre días ni tras un
reinicio: `rodaje/hecho.json` guarda un resumen con sal (SHA-256) y la fecha, nunca el id ni el nombre.

**Paradas.** Si el servicio tiene la cuenta detenida o sin sesión, o LinkedIn frena (401/403/429/999, redirección,
reto), el día termina en el acto y el comando sale con **3**. Si el servicio no abre la cuenta por otra salida a
internet o su configuración falla (token, cuenta desconocida), sale con **4**: eso lo arregla alguien en el servidor.
Un tope del servicio agotado, el servicio caído o una llamada sin respuesta cortan solo esa rutina; el día sigue.
Vuelto a arrancar el mismo día después de una parada, espera al día siguiente, y antes de cada paso lee la parada del
disco: con la cuenta detenida, no sale ni una llamada.

**El resumen de cada día**, `cuentas/<cuenta>/rodaje/rodaje-AAAA-MM-DD.json` (se reescribe tras cada paso): el plan
y la pausa larga, corridas y segundos por rutina, llamadas, rechazos y segundos por operación, las respuestas de
LinkedIn por estado HTTP, los rechazos del servicio por estado y tipo, los topes agotados, por tipo de escritura cuántas
salieron, se hicieron, se confirmaron releyendo, quedaron inciertas o rechazadas (y cuántas no tenían candidato, ya
estaban hechas o no encajaban), los errores por tipo, las paradas (hora, tipo, estado, motivo), el resultado del
canario y el código de salida. Nunca un nombre, un id o un texto.

```bash
uv run python -m navegador rodaje prueba          # con el servicio en marcha; hasta que se detenga (--dias N)
uv run python -m navegador rodaje estado          # los últimos 14 días (--dias N) de cada cuenta en una tabla
```

`estado` muestra por día: lecturas, escrituras hechas (reacciones/seguimientos/invitaciones/aceptaciones/
comentarios/respuestas), respuestas de LinkedIn que no fueron 200, topes agotados, rechazos del servicio, el canario,
la última parada y el código (0 bien, 3 parada, 4 no pudo, «en curso»).

| Variable | Por defecto | Qué es |
| --- | --- | --- |
| `RODAJE_CUENTA` | — | La cuenta de prueba (la de `login`); también como argumento |
| `RODAJE_HORARIO`, `RODAJE_ZONA` | `08:00-20:00`, `America/Bogota` | Horario de trabajo y su zona |
| `RODAJE_ESCALA` | `1` | Multiplica las lecturas (de 0 a 3) |
| `RODAJE_REACCIONES`, `_SEGUIMIENTOS`, `_INVITACIONES`, `_ACEPTACIONES` | `6`, `4`, `2`, `5` | Escrituras al día (de 0 a 30) |
| `RODAJE_COMENTARIOS`, `RODAJE_RESPUESTAS` | `0`, `0` | Con un número, hace falta `RODAJE_TEXTOS` |
| `RODAJE_TEXTOS` | vacío | Archivo con textos propios, uno por línea; cada uno sale una sola vez |
| `RODAJE_LUGAR`, `RODAJE_BUSQUEDAS` | `United States`, `founder,product manager,cto,software engineer` | El lugar del filtro y las búsquedas de personas |
| `NAVEGADOR_URL`, `NAVEGADOR_TOKEN` | `127.0.0.1:NAVEGADOR_PUERTO`, — | El servicio y su token |

En el servidor corre en el contenedor `rodaje` (perfil `rodaje` de `deploy/compose.prod.yaml`), con la misma imagen
y el mismo volumen que `navegador`; ver [En el servidor](#en-el-servidor).

## En el servidor

Montado y apagado hasta que se nombra su perfil:

- La imagen `ghcr.io/gustavop-dev/barrio-ai-navegador` se construye en cada push a `main`.
- En `deploy/compose.prod.yaml` el servicio `navegador` está bajo el perfil `navegador` y el rodaje bajo `rodaje`: un
  `up -d` normal no arranca ninguno. No publican puertos y Caddy no los expone; el backend alcanza el servicio en
  `http://navegador:8790` por la red interna. Los dos usan el volumen `navegador-datos`.
- Dentro del contenedor el navegador dibuja en una pantalla virtual (Xvfb) y corre con ventana, como en un
  escritorio. Un reinicio del contenedor (`restart`, `stop` + `up -d`, el servidor que se reinicia) la vuelve a
  levantar; si no arranca, el contenedor termina con error y Docker lo intenta otra vez.

Qué está comprobado y dónde: **[servidor]** probado en el servidor el 13/11/2026; **[local]** probado en Docker en la
laptop contra una página local, sin LinkedIn; **[pendiente]** solo se puede probar en el servidor y falta.

### Paso a paso

Todo en el servidor, salvo el túnel. Las órdenes repiten
`docker compose -f compose.prod.yaml --env-file .env --profile navegador`; abajo va como `dc`:

```bash
alias dc='docker compose -f compose.prod.yaml --env-file .env --profile navegador --profile rodaje'
```

1. **Preparar** [servidor]. `cd /opt/barrio-ai/deploy`. En `.env`: `NAVEGADOR_TOKEN` (`openssl rand -hex 32`, el
   mismo que usa el backend) y, para el rodaje, `RODAJE_CUENTA=<cuenta>`. Si cambió `deploy/`, el `rsync` de
   `deploy/README.md`. Luego `dc pull navegador`.
2. **Detener el servicio** si está corriendo [servidor]: `dc stop navegador`. Un perfil lo usa un solo navegador a
   la vez. Si no se detiene, `login` lo nota aunque corra en otro contenedor (el servicio tiene tomado
   `perfil-en-uso.lock` mientras su navegador está abierto), espera 30 s hasta 5 veces y se rinde sin abrir nada
   [local].
3. **Abrir el navegador de la cuenta con su pantalla** [servidor] [local]:
   ```bash
   dc run -d --name barrio-login -e NAVEGADOR_VNC=1 -p 127.0.0.1:6080:6080 navegador python -m navegador login <cuenta>
   docker logs barrio-login     # la dirección y la clave de un solo uso de la pantalla
   ```
   noVNC queda atado al `127.0.0.1` del servidor (`docker port barrio-login` dice `127.0.0.1:6080`), nunca a una
   dirección pública [local]. `docker ps` muestra ese contenedor como `unhealthy`: es normal, ahí no escucha el
   servicio (la prueba de salud es la de `servir`). La clave queda en el registro de ese contenedor hasta borrarlo
   (paso 6) y no sirve sin el túnel.
4. **El túnel, en la laptop** [servidor]: `ssh -N -L 6080:127.0.0.1:6080 barrio-ai`, y en el navegador de la laptop
   `http://127.0.0.1:6080/vnc.html` con esa clave.
5. **Entrar en LinkedIn** en esa ventana [servidor]. La clave y la verificación las escribe la persona en la página
   de LinkedIn; no pasan por ningún programa de Barrio. Al ver el inicio, cerrar la pestaña con Ctrl+W.
6. **Comprobar y limpiar** [servidor] [local]: `docker logs barrio-login` termina con «Sesión guardada.» y
   `docker wait barrio-login` dice `0` («No quedó sesión», `1`: repetir desde el paso 3). Luego
   `docker rm barrio-login` y cerrar el túnel (Ctrl+C).
7. **Encender el servicio** [servidor] [local]: `dc up -d navegador`. Abre el perfil que dejó `login` (mismo volumen,
   mismo usuario, mismo nombre de máquina `navegador`). Si la cuenta estaba detenida y ya se sabe por qué:
   `dc exec navegador python -m navegador reanudar <cuenta>`.
8. **Verificar** [servidor] [local]: `dc exec navegador python -m navegador estado` dice `pantalla :99: lista` y
   `<cuenta>: sesión guardada sí; … activa; salida directo`. Con `exec` (no `run`) se ve la pantalla del propio
   servicio. Opcional, la prueba diaria a mano: `dc exec navegador python -m navegador canario <cuenta>` (16 lecturas;
   sale con 0 si todo bien). Desde la IP del servidor pasó 14 de 14 [servidor].
9. **Arrancar el rodaje** [local; contra LinkedIn, pendiente]: `dc up -d rodaje` (con `navegador` ya arriba).
   `dc logs -f rodaje` muestra cada paso; `dc run --rm rodaje estado`, la tabla de los últimos días. Pararlo:
   `dc stop rodaje`. Si se detuvo (código 3 o 4 en la tabla), revisar con el paso 8 antes de nada; el contenedor
   vuelve a arrancar solo y espera al día siguiente.

Para volver a entrar (sesión caducada, `423`), los pasos 2 a 8. El rodaje no hace falta pararlo: con la cuenta sin
sesión o detenida, termina el día sin llamar a nada.

## Pruebas

`tests/` corre el servicio entero sobre un navegador falso (sin Chromium y sin LinkedIn): token, códigos de
respuesta, una llamada a la vez, la pausa mínima, los topes, la lista permitida, los `request_id`, la parada y su
reanudación, la falta de sesión, la salida a internet y su guarda, las cabeceras y que el registro no guarde secretos;
que un perfil abierto se note desde otro proceso, la pantalla y el cierre por inactividad;
y el rodaje con un reloj falso (el plan del día, los topes, nada dos veces, las paradas y el resumen sin datos). Corren en CI (job
`navegador` de `.github/workflows/barrio-ai.yml`):

```bash
PYTHONPATH=../infra/src uv run python -m unittest discover -s tests -t . -v
```
