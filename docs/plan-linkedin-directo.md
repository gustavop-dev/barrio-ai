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
   comandos y `GET /api/v1/resultados/analitica`; detalle en
   [`metricas-resultados.md`](../agentes-linkedin/infra/docs/metricas-resultados.md#analítica-de-linkedin-cuenta-directo).
   Lo que solo vale para un rango exacto (miembros alcanzados, publicaciones principales, demografía del contenido)
   se muestra solo para ese rango, o con su propio rango.
6. **Prueba diaria.** La del spike, llevada al servicio: lecturas de comprobación sobre la cuenta de prueba y aviso
   en la Bandeja cuando algo se rompe.

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
| 3 | Analítica: importación diaria, carga inicial, modelos y pantalla de Resultados con intervalos. 3a, el backend, está hecho; falta la pantalla (3b) | Cuenta de prueba (3a); datos de la cuenta de Gustavo, solo lectura |
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
