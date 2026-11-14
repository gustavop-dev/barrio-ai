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
- **El servidor:** todo corrió desde el computador de Gustavo, con su conexión de casa. Desde el servidor (IP de
  centro de datos) no se ha probado nada.
- **La analítica de una cuenta con actividad por código:** la cuenta de prueba no tiene impresiones, así que no se
  vieron hojas con datos de publicaciones ni de demografía. Tampoco los rangos anteriores al límite.
- **Si leer la tarjeta de un perfil cuenta como visita** a ese perfil.

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

### Hecho y lo que falta (13/11/2026)

Hecho y probado con respuestas inventadas y el navegador falso de las pruebas; nada de esto salió a LinkedIn:

- **Topes por tipo de escritura** en el servicio, con el 422 `budget` de arriba. Una acción que no salió por tope, por
  servicio ocupado o por la red vuelve a aprobada sin contar en los topes del día ni pausar, y se reintenta pasado
  el `retry_after` (30 min si no llega). Las lecturas cortadas así se retoman en la siguiente vuelta.
- **Salida a internet.** Proxy opcional para todas las cuentas (`NAVEGADOR_PROXY`) o por cuenta
  (`NAVEGADOR_PROXY_CUENTAS`), con usuario y clave solo desde el entorno, nunca en disco ni en el log. El servicio
  guarda por cuenta una etiqueta sin secretos de la salida de su sesión y no la abre por otra hasta que alguien lo
  acepta (`python -m navegador salida <cuenta> --aceptar`): una sesión que salta de IP es lo que más verificaciones
  provoca. Un perfil importado de otro equipo también espera esa aceptación.
- **Prueba diaria** en el backend, con sus avisos y la pausa (punto 6).
- **Filtro de grado de red** en la búsqueda (`rutas.search_page(network=...)`): escrito, apagado y sin verificar.

Falta:

- Correrlo contra LinkedIn con la cuenta de prueba (fase 4): los topes frente a lo que LinkedIn tolera, la salida por
  el túnel de casa y la prueba diaria real.
- Mostrar la última prueba diaria en Ajustes › Máquina, junto al estado de la cuenta: el backend ya la sirve.

Servidor actual: 1 CPU, 4 GB de memoria, unos 2,4 GB disponibles. Un Chromium por cuenta ocupa del orden de medio
giga (estimación, sin medir): caben una o dos cuentas; más cuentas piden más máquina o el equipo del usuario.

## Orden de construcción

Cada fase es un PR grande, hecho por subagentes y revisado antes de fusionar. Las fases 1 a 3 no envían nada a
LinkedIn desde producción.

| Fase | Qué se construye | Cómo se comprueba |
| --- | --- | --- |
| 0 | Decisiones abiertas y el puente con Unipile | — |
| 1 | Conector `directo` en el backend: las 21 operaciones con la interfaz actual, traducción de respuestas, pruebas con respuestas grabadas sin datos personales | CI; cuenta de prueba desde el computador de Gustavo |
| 2 | Servicio «navegador»: contenedor, perfiles por cuenta, API interna, protecciones, inicio de sesión, pausa y aviso | Cuenta de prueba en el entorno elegido |
| 3 | Analítica: importación diaria, carga inicial, modelos y pantalla de Resultados con intervalos. 3a (el backend) y 3b en la app están hechas; falta la vista en la PWA | Cuenta de prueba (3a); datos de la cuenta de Gustavo, solo lectura |
| 4 | Prueba de resistencia: la cuenta de prueba trabajando 1 a 2 semanas a ritmo real, con la prueba diaria | Sin bloqueos ni verificaciones en ese periodo |
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
