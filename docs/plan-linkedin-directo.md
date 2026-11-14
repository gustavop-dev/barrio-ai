# Plan: LinkedIn directo (sin Unipile) y analítica propia

Un solo lugar para lo que se investigó el 13/11/2026, lo que quedó demostrado, lo que falta y el orden de
construcción. La prueba exploratoria vive en `spikes/linkedin-directo/` (rama `spike/linkedin-directo`); su README
tiene el detalle técnico de cada operación. Aprobado por Gustavo el 13/11/2026; nada de aquí está todavía en producción.

## Objetivo

Que el equipo haga en LinkedIn todo lo que hoy hace a través de Unipile (leer, buscar, comentar, responder,
reaccionar, seguir, invitar, aceptar, leer mensajes) con un conector propio, pagando por usuario solo lo que cueste
su conexión, y que además traiga la analítica de la cuenta (impresiones, alcance, seguidores, público) a la app.

## Por qué

- Unipile cuesta 49 € al mes hasta 10 cuentas (después, 5 € por cuenta). La prueba gratuita vence alrededor del
  13/11/2026, 7:30 p. m. hora de Bogotá (la cuenta se conectó el 6/11 a esa hora).
- Gustavo prefiere un costo por usuario y no depender de un tercero, pensando en sumar a su CTO y, más adelante,
  en ofrecer la herramienta.
- La API oficial que cubriría parte (Community Management) exige organización legal, correo corporativo, Página,
  app nueva y revisión; limita el guardado a 48 horas y prohíbe el uso para ventas. Se descartó por ahora.

## Lo que quedó demostrado

| Hallazgo | Evidencia |
| --- | --- |
| Copiar las cookies a un script no sirve | En la cuenta principal, LinkedIn anuló la sesión en la segunda llamada |
| Llamar desde dentro de la página con sesión iniciada sí aguanta | Cuenta de prueba: 140 llamadas y 10 escrituras en una tarde, sin bloqueo ni verificación |
| Las 21 operaciones del conector funcionan | Cada escritura se confirmó con una lectura posterior |
| Iniciar sesión en el navegador automatizado no anula la sesión | Dos sesiones de solo lectura en la cuenta principal, sin incidentes |
| La analítica completa se obtiene con una petición | La respuesta al diálogo «Exportación» ya trae el libro entero; solo lleva fecha de inicio y de fin |
| Esa petición también funciona enviada por código | Cuenta de prueba, 13/11/2026: 7, 28 y 365 días desde la página de inicio, sin abrir la de analítica; respuesta en menos de un segundo |
| Entrar a mano en el servidor funciona | El paso a paso del README del servicio (contenedor de login, túnel SSH, noVNC): sesión guardada y abierta después por el servicio |
| Las lecturas salen bien desde la IP del servidor | La prueba diaria por el servicio en el servidor: 14 de 14 lecturas, 16 llamadas, 105 s |

Por dónde va cada cosa hoy:

- **API interna antigua:** perfil, seguidores y conexiones, visitas al perfil, posts de una persona, post suelto,
  comentarios y respuestas, invitaciones (leer, enviar, aceptar), conversaciones y mensajes.
- **Interfaz nueva de la web:** buscar personas, ubicaciones, reaccionar, seguir, comentar, responder y la analítica.
  Ningún proyecto open source la documenta; se sacó observando la propia web.

Analítica (libro de 7 hojas; la cuenta de prueba, casi vacía, recibió 6, sin la demografía del contenido): totales,
impresiones e interacciones por día, una fila por post con 15 columnas (impresiones, dentro y fuera de la red,
miembros alcanzados, seguidores obtenidos, visitas al perfil, reacciones, comentarios, compartidos, guardados, envíos),
hasta 50 posts principales del rango, nuevos seguidores por día y demografía de seguidores y de quienes vieron el
contenido. Intervalos: 7, 14, 28, 90, 365 días y personalizado, siempre con detalle diario; LinkedIn no da fechas
anteriores al 10/10/2025.

## Lo que no está demostrado

- **Aguante en el tiempo:** fue una tarde, en una cuenta de prueba casi vacía. No se sabe cómo reacciona LinkedIn a
  10 comentarios, 20 seguimientos y 16 invitaciones diarias durante semanas.
- **La cuenta real:** ahí solo se leyó la analítica con clics. Ninguna de las 21 operaciones se ha ejecutado en ella
  por esta vía.
- **El servidor en el tiempo:** desde la IP del servidor (centro de datos) solo corrió la prueba diaria, una vez y
  sin escrituras. Si LinkedIn tolera esa IP días seguidos y con escrituras es lo que mide la
  [fase 4](#fase-4-rodaje-de-la-cuenta-de-prueba).
- **La analítica de una cuenta con actividad por código:** la cuenta de prueba no tiene impresiones, así que no se
  vieron hojas con datos de publicaciones ni de demografía. Tampoco los rangos anteriores al límite.
- **Si leer la tarjeta de un perfil cuenta como visita** a ese perfil. Las librerías públicas dicen que sí: hay que
  contar con que esas personas ven la visita.

## Riesgos

- **Términos de LinkedIn:** automatizar así los incumple, igual que hace Unipile por debajo. La diferencia es que la
  detección y los bloqueos pasan a ser asunto nuestro.
- **Mantenimiento continuo:** dos rutas ya estaban retiradas el día de la prueba; los identificadores rotan y la
  interfaz nueva cambia con cada despliegue de LinkedIn. Hace falta la prueba diaria y alguien que arregle.
- **Repositorio público:** `gustavop-dev/barrio-ai` es público. Publicar ahí el conector deja a la vista cómo se
  automatiza la cuenta. Antes del primer PR hay que decidir: repo privado, o el conector en un repo privado aparte.

## Arquitectura propuesta

1. **Conector `directo` en el backend.** Un proveedor más junto a `unipile` y `fake`, con la misma interfaz y las
   mismas formas de respuesta, de modo que operador, autopiloto, respuestas y métricas no cambian. La cuenta decide
   su proveedor: se puede pasar una cuenta sin tocar las demás y volver atrás cambiando un campo.
2. **Servicio «navegador».** Un proceso aparte con un Chromium por cuenta y su perfil persistente. Recibe las
   operaciones del backend por una API interna con token y las ejecuta dentro de la página. Lleva las protecciones
   de la prueba: pausas aleatorias, tope por sesión y por día, escrituras por lista permitida, y parada dura ante
   login, verificación, CAPTCHA o bloqueo, que además pausa la cuenta y avisa en la Bandeja.
3. **Inicio de sesión a mano.** El usuario entra una vez con su clave y su 2FA en ese navegador; la clave nunca
   pasa por nuestro código ni se guarda.
4. **Dónde corre el navegador** (por decidir, ver abajo): en el servidor con una IP residencial fija por cuenta, o
   en un equipo del usuario.
5. **Analítica.** Una importación diaria de los últimos 14 días (los días recientes aún cambian), seguida de los
   rangos exactos de 7, 28, 90 y 365 días que terminan ayer, y una carga inicial de 365 días. Se guarda por día y por post; la app muestra 7, 14, 28, 90, 365 días y rango personalizado
   desde nuestros datos, sin volver a pedirle nada a LinkedIn. El backend está hecho (fase 3a): modelos, importación,
   comandos y `GET /api/v1/resultados/analitica`; la app la muestra en Resultados › «Analítica de LinkedIn» (fase 3b,
   [RES-12](funcionalidades/resultados.md#res-12)); falta la vista en la PWA. Detalle en
   [`metricas-resultados.md`](../agentes-linkedin/infra/docs/metricas-resultados.md#analítica-de-linkedin-cuenta-directo).
   Lo que solo vale para un rango exacto (miembros alcanzados, publicaciones principales, demografía del contenido)
   se muestra solo para ese rango, o con su propio rango.
6. **Prueba diaria.** La del spike, llevada al backend (trabajo `check_linkedin`, `team_backend/canario.py`). Una vez
   al día por cuenta `directo`, desde las 12:00 UTC (`LINKEDIN_CANARY_AFTER`), hace las 14 lecturas del conector (16
   llamadas) y comprueba que cada respuesta trae los campos que usa Barrio. Va por el servicio como cualquier
   lectura: gasta sus topes y respeta sus paradas. Guarda por lectura el estado, las filas y los campos que faltan,
   nunca un valor; quedan las 30 últimas. Si no pudo correr (servicio ocupado, caído o sin cupo), lo intenta otra vez
   a la hora, hasta 3 veces al día. Avisa en Notificaciones (`linkedin_canary`) una vez cuando algo se rompe o no pudo
   correr en todo el día, y otra cuando vuelve a pasar. Si el servicio paró la cuenta o no tiene sesión, la pausa en
   Barrio como una restricción de Unipile, con qué hacer en el motivo, y avisa una sola vez. La última prueba de cada
   cuenta llega en `canary` de `GET /api/v1/operador/overview` y `/operador/accounts`. A mano:
   `python -m navegador canario <cuenta>`.

### Topes frente al ritmo real

Un día completo de producción de una cuenta, sacado del código (13/11/2026; detalle por trabajo y fuentes en
[`agentes-linkedin/navegador/README.md`](../agentes-linkedin/navegador/README.md#topes-frente-al-ritmo-real)):

| Qué | Escrituras | Lecturas al día |
| --- | --- | --- |
| Comentar (10), responder (10), reaccionar (20) | 40 | hasta 140 |
| Seguir (20), invitar (16 a 20), aceptar (10) | 50 | hasta 240, 180 de ellas de perfiles |
| Post del día (API oficial) | 0 aquí | 4 |
| Referentes cada 3 h (hasta 15) | — | hasta 120 |
| Bandeja cada hora | — | hasta 132 |
| Comentarios de los posts propios, métricas, descubrir, sincronizar, borradores y conciliación | — | hasta 245 |
| Analítica (5 exportaciones) y prueba diaria (16) | — | 21 |
| **Total**: los perfiles de todo (también clasificar) comparten un tope de 80 al día, 160 llamadas | **90** | **hasta unas 880**; un día normal, unas 650 |

Topes del servicio por cuenta, en ventanas móviles: 150 lecturas por hora y 1000 por día; 15 escrituras por hora y
100 por día; por día, 30 comentarios y respuestas, 30 reacciones, 30 seguimientos, 30 invitaciones y 15
aceptaciones. Son una red de seguridad detrás de los topes del operador. Un tope agotado contesta 422 con
`code: budget`: no pausa la cuenta, no cuenta como límite de LinkedIn y la acción se reintenta cuando hay cupo.

### Hecho y lo que falta (14/11/2026)

Hecho y probado con respuestas inventadas y el navegador falso de las pruebas; nada de esto salió a LinkedIn:

- **Topes por tipo de escritura** en el servicio, con el 422 `budget` de arriba. Una acción que el servicio no dejó salir
  (su tope, o no enviada: ocupado, sin abrir, otra salida o el servicio caído) vuelve a aprobada sin contar en los
  topes del día ni pausar, y se reintenta pasado el `retry_after` (30 min si no llega). Las lecturas cortadas así se
  retoman en la siguiente vuelta. Cualquier otro error, de este proveedor o de otro, sigue como antes.
- **Salida a internet.** Proxy opcional para todas las cuentas (`NAVEGADOR_PROXY`) o por cuenta
  (`NAVEGADOR_PROXY_CUENTAS`), con usuario y clave solo desde el entorno, nunca en disco ni en el log. El servicio
  guarda por cuenta una etiqueta sin secretos de la salida de su sesión y no la abre por otra hasta que alguien lo
  acepta (`python -m navegador salida <cuenta> --aceptar`): una sesión que salta de IP es lo que más verificaciones
  provoca. Un perfil importado de otro equipo también espera esa aceptación. Mientras tanto el backend avisa una vez,
  en el acto (`navegador_salida`, con qué hacer), sin pausar la cuenta: lo pendiente espera y nada se pierde.
- **Prueba diaria** en el backend, con sus avisos y la pausa (punto 6). La app la muestra en la tarjeta de la cuenta
  (Ajustes › Máquina, [AJU-02](funcionalidades/ajustes.md#aju-02)); la PWA, todavía no.
- **Rodaje de la fase 4** (abajo), con sus paradas, y el servicio más firme para el servidor: la pantalla virtual vuelve
  tras reiniciar el contenedor, y un login en otro contenedor espera a que el servicio suelte el perfil.
- **Filtro de grado de red** en la búsqueda (`rutas.search_page(network=...)`): escrito, apagado y sin verificar.
- **Conectar LinkedIn desde la app** ([AJU-13](funcionalidades/ajustes.md#aju-13)), apagado (`LINKEDIN_CONEXION_APP`):
  el servicio abre el navegador de la cuenta en una pantalla propia y la persona entra desde el teléfono por una vista
  remota que solo existe mientras dura la conexión, detrás de Caddy y de un enlace de un solo uso. Probado en local con
  Docker y Caddy, con una página de entrada local en lugar de la de LinkedIn. Diseño de seguridad en el README del
  servicio ([Conectar desde la app](../agentes-linkedin/navegador/README.md#conectar-desde-la-app)).

Hecho en el servidor: entrar a mano por el túnel y noVNC, y una prueba diaria de 14 de 14 desde su IP (arriba).

Falta:

- El rodaje de la fase 4 en el servidor y, si su IP no aguanta, el túnel de casa.
- La prueba diaria en la PWA.
- Conectar desde la app en el servidor: entrar de verdad en LinkedIn desde el teléfono y que la sesión quede.

Servidor actual: 1 CPU, 4 GB de memoria, unos 2,4 GB disponibles. Medido el 13/11/2026: con el navegador de una
cuenta abierto tras un canario de 16 llamadas, el contenedor del servicio ocupaba cerca de 1 GiB y quedaron unos 1,5 GB
disponibles. Dos cuentas a la vez caben justas; más cuentas piden más máquina o el equipo del usuario. El navegador
queda abierto: cerrarlo sin uso (`NAVEGADOR_CIERRE_INACTIVO_MIN`, apagado) solo compensa con varias cuentas en un
servidor pequeño, porque el backend llama al menos cada hora y cada reapertura es una carga más del inicio que LinkedIn
ve. Ninguna bandera de Chromium ni bloqueo de imágenes para ahorrar memoria: cambiarían cómo LinkedIn ve el navegador.

## Fase 4: rodaje de la cuenta de prueba

Antes de pasar la cuenta de Gustavo, una cuenta **de prueba** trabaja en el servidor una o dos semanas a ritmo de
producción, para saber si LinkedIn tolera la IP del servidor y nuestro ritmo. Detalle en el README del servicio
([Rodaje](../agentes-linkedin/navegador/README.md#rodaje)) y paso a paso en el servidor
([En el servidor](../agentes-linkedin/navegador/README.md#en-el-servidor)).

**Qué hace.** `python -m navegador rodaje <cuenta>`, en el contenedor `rodaje` (perfil `rodaje` de Compose, apagado
por defecto), hace un día de producción tras otro por el servicio en marcha: el mismo cliente, las mismas llamadas,
topes, paradas y lista permitida que usa el backend, pero sin backend (no crea propuestas, no gasta IA ni toca la
base). Entre semana, de 08:00 a 20:00 de Bogotá con una pausa larga cerca del mediodía y desfases al azar: unas 290 a
330 lecturas con la mezcla de producción (referentes, perfiles con su tarjeta, búsquedas con el filtro de lugar,
bandeja, posts propios, métricas, red, una exportación de analítica y la prueba diaria) y 12 escrituras inofensivas:
6 «me gusta», 4 seguimientos y 2 invitaciones sin nota a creadores fuera de la red, más hasta 5 aceptaciones de
invitaciones reales. El fin de semana, la mitad. Nunca toca dos veces la misma publicación o persona, no comenta ni
responde (solo con un número explícito y textos propios), y nunca deja de seguir, retira, borra ni manda mensajes.

**Qué no prueba.**

- La cuenta real: una cuenta casi vacía y nueva puede recibir otro trato que una con años de historia.
- El volumen de escritura de producción: 12 al día frente a hasta 90, sin comentarios ni respuestas. Las escrituras
  crecen en la fase 5, una capacidad cada vez.
- Un día cargado de lecturas, salvo con `RODAJE_ESCALA` (2 o 3: unas 600 a 880 al día).
- El backend: autopiloto, workers, conciliación y avisos. La prueba diaria del backend corre solo para cuentas
  `directo` dadas de alta en Barrio; la de prueba no lo está (el autopiloto actuaría con ella), así que no sale en la
  app: el rodaje corre su propia prueba diaria y la guarda en su resumen.
- El túnel de casa: solo se monta si la IP del servidor no aguanta.

Efecto en terceros, igual que en producción: unas 40 tarjetas de perfil al día, que probablemente cuentan como visitas,
y las reacciones, seguimientos e invitaciones de la tabla.

**Cómo se lee.** `rodaje estado` (los últimos 14 días en una tabla): por día lecturas, escrituras hechas por tipo,
respuestas de LinkedIn que no fueron 200, topes agotados, rechazos del servicio, la prueba diaria, la última parada y el
código de salida (0 bien, 3 parada, 4 no pudo). El detalle de cada día queda en
`cuentas/<cuenta>/rodaje/rodaje-AAAA-MM-DD.json`; `navegador estado` dice si la cuenta tiene una parada y su motivo.

| Señal | Qué es |
| --- | --- |
| Bien | Código 0, prueba diaria `ok`, ninguna respuesta de LinkedIn que no sea 200 salvo algún 404 suelto (contenido borrado), escrituras confirmadas al releer |
| Alarma | Código 3 por LinkedIn: reto, verificación, redirección al login, 401, 403, 429 o 999, o la sesión cerrada. El día termina solo |
| No habla del aguante | Código 4 (otra salida a internet, configuración), un tope del servicio agotado, el servicio caído, o una prueba diaria `roto`: LinkedIn cambió un campo y se arregla el conector |

**Criterio para pasar la cuenta real** (propuesta; decide Gustavo):

1. 10 días seguidos a ritmo normal, al menos 7 entre semana, sin ninguna alarma y sin volver a entrar a mano.
2. La prueba diaria `ok` todos esos días; un `roto` arreglado no reinicia la cuenta de días, una alarma sí.
3. Todas las escrituras confirmadas releyendo; ninguna incierta sin explicar.
4. Después, 3 días con `RODAJE_ESCALA=2` (unas 600 lecturas, un día normal de producción) con el mismo resultado.

Si LinkedIn frena, el rodaje se detiene solo y no vuelve a llamar ese día. Se mira el motivo, se resuelve (entrar a mano
si pidió verificación) y la cuenta de días empieza de cero. Si frena otra vez desde la IP del servidor, se monta el
túnel de casa (decisión abierta 3) y la fase 4 se repite por ahí.

## Orden de construcción

Cada fase es un PR grande, hecho por subagentes y revisado antes de fusionar. Las fases 1 a 3 no envían nada a
LinkedIn desde producción.

| Fase | Qué se construye | Cómo se comprueba |
| --- | --- | --- |
| 0 | Decisiones abiertas y el puente con Unipile | — |
| 1 | Conector `directo` en el backend: las 21 operaciones con la interfaz actual, traducción de respuestas, pruebas con respuestas grabadas sin datos personales | CI; cuenta de prueba desde el computador de Gustavo |
| 2 | Servicio «navegador»: contenedor, perfiles por cuenta, API interna, protecciones, inicio de sesión, pausa y aviso | Cuenta de prueba en el entorno elegido |
| 3 | Analítica: importación diaria, carga inicial, modelos y pantalla de Resultados con intervalos. 3a (el backend) y 3b en la app están hechas; falta la vista en la PWA | Cuenta de prueba (3a); datos de la cuenta de Gustavo, solo lectura |
| 4 | Prueba de resistencia: la cuenta de prueba trabajando 1 a 2 semanas a ritmo real, con la prueba diaria ([rodaje](#fase-4-rodaje-de-la-cuenta-de-prueba)) | El criterio de esa sección: 10 días seguidos sin alarmas y la prueba diaria bien |
| 5 | Paso de la cuenta de Gustavo: primero lecturas, luego una capacidad de escritura cada vez; Unipile queda de respaldo hasta el final | Una semana estable por capacidad |
| 6 | Segundo usuario (CTO) y multitenant: alta con inicio de sesión propio, identidad fuera del código | Ver `barrio-multitenant` en la memoria del proyecto |

Estimación, sin diseño detallado: fases 1 a 3, alrededor de una semana de trabajo; la fase 4 es tiempo de espera;
la 5, una a dos semanas según cómo responda LinkedIn.

## Decisiones de Gustavo (13/11/2026)

| Decisión | Qué implica |
| --- | --- |
| No se paga Unipile; nos desligamos | Cuando venza la prueba, el backend pausa sola la cuenta de Unipile ante el rechazo (401/403) y avisa. Comentarios, red, lectura de referentes y métricas quedan detenidos hasta la fase 5. Publicar los posts sigue: va por la API oficial. |
| El navegador corre en el servidor y sale a internet por la conexión de su casa | Un túnel desde el servidor a un equipo de su casa que haga de salida. Ese equipo tiene que estar encendido a toda hora (su computador se apaga: hará falta uno pequeño siempre encendido). Se monta hacia el final, en la fase 4. |
| El repositorio sigue público por ahora | Se hará privado más adelante. Los PR no llevan datos personales, capturas ni identificadores de cuentas. |

## Decisiones abiertas

1. **Cuenta de prueba:** usarla para la prueba de resistencia implica darle vida (conexiones, posts).
2. **API oficial más adelante:** solicitar Community Management con la empresa cuando haya tiempo, como vía sin
   riesgo para publicar, comentar y estadísticas.
3. **Por dónde sale el navegador:** primero se prueba la cuenta de prueba desde la IP del servidor (fase 4). Si
   LinkedIn pide verificación, se monta el túnel a un equipo siempre encendido en casa de Gustavo. No se compra
   ningún equipo aparte para esto.

## Relacionado

`docs/plan-outbound.md` (el embudo que este conector tiene que servir) · `spikes/linkedin-directo/README.md`
(estado por operación, cómo correr la prueba y la prueba diaria). · `agentes-linkedin/infra/docs/navegador-contrato.md`
(contrato entre el backend y el servicio navegador, ids y lista permitida). · `agentes-linkedin/navegador/README.md`
(el servicio navegador: cómo correrlo, entrar a mano y encenderlo en el servidor).
