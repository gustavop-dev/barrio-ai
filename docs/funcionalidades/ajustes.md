# Ajustes (`AJU`)

Los controles que Gustavo toca poco: la parada total, la orientación para el equipo, los modos y topes (solo lectura), el gasto de IA, LinkedIn, la captura, las notificaciones y la sesión. Las notificaciones de este dispositivo están en [notificaciones-push.md](notificaciones-push.md); la sesión y los dispositivos, en [acceso.md](acceso.md).

- **Código:** backend `rediseno_views.Settings` (`GET /api/v1/ajustes`), `oficina_views.Overview`, `Control`, `operador.set_global_pause`, `set_paused`, `orientacion.py`, `capturas_views.Preferences`, `linkedin_views.py`, `connectors_linkedin.status_payload`; PWA `oficina/src/pages/Ajustes.tsx`, `pages/ajustes/*`; app `movil/src/ajustes/*`; común `compartido/src/logic/ajustes.ts`, `linkedin.ts`.
- **Documentación:** secciones «Máquina autónoma», «LinkedIn oficial», «Ajustes» y «Preferencias» de [`CONTRATO-API.md`](../../oficina/CONTRATO-API.md).

## Resumen

| ID | Función | Dónde | Estado |
| --- | --- | --- | --- |
| [AJU-01](#aju-01) | Parada total y reanudar la máquina | PWA · app · backend | funciona |
| [AJU-02](#aju-02) | Pausar o reanudar una cuenta de Unipile | PWA · app · backend | funciona |
| [AJU-03](#aju-03) | Orientación para el equipo | PWA · app · backend | funciona |
| [AJU-04](#aju-04) | Autonomía y límites | PWA · app · backend | funciona |
| [AJU-05](#aju-05) | Gasto de IA | PWA · app · backend | funciona |
| [AJU-06](#aju-06) | Estado de LinkedIn oficial | PWA · app · backend | funciona |
| [AJU-07](#aju-07) | Conectar o reconectar LinkedIn | PWA · app · backend | parcial |
| [AJU-08](#aju-08) | Permiso del micrófono | PWA · app | funciona |
| [AJU-09](#aju-09) | Edición con IA por defecto en las fotos nuevas | PWA · app · backend | funciona |
| [AJU-10](#aju-10) | Acceso a «Lo que el equipo sabe de ti» | PWA · app · backend | funciona |
| [AJU-11](#aju-11) | Orden y anclas de Ajustes | PWA · app | funciona |

---

### AJU-01 · Parada total y reanudar la máquina <a id="aju-01"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** detiene todo el trabajo del equipo con un motivo, y lo reanuda cuando quiere; si la parada viene del servidor, lo ve y sabe que no puede levantarla desde la app.
- **Código:** `POST /api/v1/operador/control {paused, reason}` (`operador.set_global_pause`), `overview.control`; PWA `ajustes/Maquina.tsx`; app `ajustes/Maquina.tsx`.
- **Criterios de aceptación:**
  1. **Dado** la máquina en marcha, **cuando** abre Ajustes › Máquina, **entonces** ve «En marcha», «La máquina está en marcha. Observa, redacta y actúa dentro de los topes.» y «Parada total».
  2. **Dado** «Parada total», **cuando** lo pulsa, **entonces** se abre «Parada total» con el motivo obligatorio (ejemplo «Por ejemplo: reviso los topes de la semana») y «Detener la máquina»; al confirmar aparece «Máquina detenida.».
  3. **Dado** la API sin motivo, **cuando** recibe `{paused: true}`, **entonces** responde 400 «Indica el motivo de la parada».
  4. **Dado** la máquina detenida desde la app, **cuando** abre Ajustes, **entonces** ve «Detenida», el motivo, «Origen: Desde la app», quién y cuándo, y «Reanudar» con nota opcional; al confirmar aparece «Máquina en marcha.».
  5. **Dado** `OPERATOR_PAUSED=true`, **cuando** abre Ajustes, **entonces** ve «Origen: Desde el servidor» y «Reanudar» desactivado con «La parada viene del servidor (`OPERATOR_PAUSED=true`). No se puede levantar desde la app.»; la API responde 409 si se intenta.
  6. **Dado** la máquina detenida, **cuando** corre el autopiloto, **entonces** no hace nada salvo los avisos de caducidad de LinkedIn ([EDI-15](motor-editorial.md#edi-15)), y ninguna acción se ejecuta.
  7. **Dado** la máquina detenida, **cuando** navega por cualquier vista, **entonces** ve el banner «Máquina en pausa · <motivo>» ([OFI-07](oficina.md#ofi-07)).
  8. **Dado** un token de servicio, **cuando** intenta parar o reanudar, **entonces** recibe 403.
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### AJU-02 · Pausar o reanudar una cuenta de Unipile <a id="aju-02"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** pausa solo la cuenta de LinkedIn conectada por Unipile, sin parar el resto de la máquina.
- **Código:** `POST /api/v1/operador/accounts/<id>/pause {paused, reason}`.
- **Criterios de aceptación:**
  1. **Dado** una cuenta de Unipile, **cuando** abre Ajustes › Máquina, **entonces** ve su nombre, el proveedor («Unipile» o «simulada»), «Conectada», «Sin comprobar» o «Token caducado», «En pausa» o «Bloqueada» si aplica, y «Comprobada hace X».
  2. **Dado** «Pausar solo esta cuenta», **cuando** confirma con un motivo obligatorio, **entonces** aparece «Cuenta en pausa.» y el equipo deja de actuar con ella.
  3. **Dado** una cuenta en pausa, **cuando** pulsa «Reanudar la cuenta», **entonces** se reanuda sin confirmación y aparece «Cuenta reanudada.».
  4. **Dado** que no hay cuentas de Unipile, **cuando** abre la sección, **entonces** ve «No hay ninguna cuenta de Unipile configurada.».
- **Brechas código/docs:** la cuenta de la API oficial de LinkedIn no aparece aquí (se gestiona en [AJU-06](#aju-06)).
- **Cobertura QA:** pendiente

### AJU-03 · Orientación para el equipo <a id="aju-03"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** escribe su dirección de alto nivel (temas, tono, prioridades, qué evitar) y la leen quien redacta los comentarios, el circuito editorial, el clasificador de la red y el agente líder.
- **Código:** `GET|PUT /api/v1/orientacion` (`orientacion.update`, `MAX_CHARS` 4.000); PWA y app `ajustes/Orientacion.tsx`.
- **Criterios de aceptación:**
  1. **Dado** la sección, **cuando** la abre, **entonces** ve el campo «Qué quieres que el equipo tenga en cuenta ahora» y el contador «N de 4000 caracteres. Es privada: orienta las decisiones y nunca aparece en un texto público.».
  2. **Dado** un texto, **cuando** pulsa «Guardar orientación», **entonces** aparece «Orientación guardada. El equipo la usa desde su próxima tarea.» y abajo «Actualizada hace X por <usuario>.».
  3. **Dado** más de 4.000 caracteres, **cuando** escribe, **entonces** el contador se pone en rojo; la API respondería 400.
  4. **Dado** cambios sin guardar, **cuando** pulsa «Descartar cambios», **entonces** vuelve el texto guardado.
  5. **Dado** que nunca escribió una orientación, **cuando** abre la sección, **entonces** ve «Todavía no has escrito ninguna orientación.».
  6. **Dado** una orientación guardada, **cuando** el equipo redacta un texto público, **entonces** nunca la cita ni la parafrasea (las comprobaciones de filtración la tratan como orientación privada).
  7. **Dado** que el resumen semanal aplica una orientación ([SEM-06](resumen-semanal.md#sem-06)), **cuando** abre Ajustes, **entonces** ve el texto nuevo.
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### AJU-04 · Autonomía y límites <a id="aju-04"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** ve, sin poder cambiarlos, el modo de cada capacidad, si el agente líder decide por él, la ventana horaria, los topes de hoy y de la semana, y las lecturas de la red.
- **Código:** `GET /api/v1/ajustes` (`autonomy`, `lead`, `limits`, `window`), `overview.accounts[].capacity`, `red/summary`; PWA y app `ajustes/Autonomia.tsx` (pliegue).
- **Criterios de aceptación:**
  1. **Dado** el pliegue «Autonomía y límites», **cuando** lo abre, **entonces** ve «Modo por capacidad · solo lectura» con Comentarios, Reacciones, Publicación diaria, Seguir, Invitar sin nota y Aceptar invitaciones, cada una «Auto», «Aprobación» o «Apagado», y «El equipo actúa solo en modo Auto. Puedes vetar lo programado desde el Calendario.».
  2. **Dado** el agente líder, **cuando** se pinta, **entonces** ve «Activo» o «Apagado», sus capacidades, el modelo y «Aprueba solo lo que pasa sus comprobaciones con claridad; lo dudoso no se hace y nunca te llega para aprobar.».
  3. **Dado** la ventana horaria, **cuando** se pinta, **entonces** ve el horario, si está «Abierta» o «Cerrada» ahora y el espaciado mínimo («N min entre acciones»).
  4. **Dado** los topes, **cuando** se pintan, **entonces** ve un medidor por capacidad con lo usado y el tope de hoy y de la semana; sin dato de uso, «Tope N · sin dato de uso».
  5. **Dado** las lecturas de la red, **cuando** se pintan, **entonces** ve sus medidores y «Comprobaciones antes y después de escribir: N hoy · sin tope: ninguna escritura sale sin ellas».
  6. **Dado** la sección, **cuando** la abre, **entonces** nada es editable: los modos se configuran en el servidor (`OPERATOR_AUTONOMY`).
- **Brechas código/docs:** en la app, un fallo de `/ajustes` puede mostrar hasta tres errores en la misma pantalla.
- **Cobertura QA:** pendiente

### AJU-05 · Gasto de IA <a id="aju-05"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** ve lo gastado hoy por todo el equipo frente al tope de seguridad diario, lo gastado hoy por cada área (sin tope propio), lo del mes frente al presupuesto general de IA, el total, lo del agente líder y lo de la transcripción.
- **Código:** `ai_spend` de `GET /api/v1/ajustes` (`rediseno_views._spend`, `knowledge/presupuesto.status`); PWA y app `ajustes/Gasto.tsx`; `compartido/src/logic/ajustes.ts`.
- **Criterios de aceptación:**
  1. **Dado** gasto de hoy, **cuando** abre «Gasto de IA · hoy», **entonces** ve primero un medidor «$gastado de $tope» para «Todo el equipo hoy (tope de seguridad)» (`AI_DAILY_FUSE_USD`, 15 USD por defecto: todos los proveedores y áreas, con reservas pendientes) y debajo solo lo gastado en «General (comentarios)», «Editorial (incluye imágenes e investigación de piezas)», «Imágenes» (ambos proveedores) y «Red», que no tienen tope propio (`limit_usd: 0`).
  2. **Dado** el gasto del mes, **cuando** se pinta, **entonces** ve «Este mes: X de 100,00 USD» (todos los proveedores frente a `AI_MONTHLY_LIMIT_USD`), «Desde el inicio: $Y», «Agente líder, este mes» (TypeSafe) y «Transcripción de audios, este mes» (AssemblyAI).
  3. **Dado** una línea con tope 0 o sin dato, **cuando** se pinta, **entonces** ve solo lo gastado o «sin dato».
  4. **Dado** `ai_spend.today` vacío, **cuando** se pinta, **entonces** ve «Hoy no hay presupuestos de IA configurados.». El backend siempre manda al menos la línea del equipo.
  5. **Dado** la carga, un 404 o un error, **cuando** abre la sección, **entonces** ve «Cargando el gasto…», «Aún no disponible» o el error con «Reintentar».
- **Brechas código/docs:**
  - No hay línea propia para el resumen semanal (`WEEKLY_SUMMARY_LLM_USD`, [SEM-04](resumen-semanal.md#sem-04)) ni para el clasificador de capturas (`capture-route`); ambos cuentan solo en «Todo el equipo hoy» y en el mes.
- **Cobertura QA:** pendiente

### AJU-06 · Estado de LinkedIn oficial <a id="aju-06"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** ve si la cuenta oficial de LinkedIn (la que publica) está conectada, cuándo caduca, con qué permisos y si la publicación real está encendida.
- **Código:** `GET /api/v1/linkedin/status` (cada 5 minutos); PWA y app `ajustes/LinkedIn.tsx`.
- **Criterios de aceptación:**
  1. **Dado** una cuenta conectada, **cuando** abre la sección, **entonces** ve «Conectado», Miembro (nombre · URN), Caduca, Permisos y Versión de la API; nunca el token.
  2. **Dado** un token que caduca en 7 días o menos, **cuando** abre la sección, **entonces** ve «Caduca pronto» y «El permiso caduca el <fecha> (quedan N días). LinkedIn no deja renovarlo solo: reconecta antes para que la publicación diaria no se pause.».
  3. **Dado** un token caducado, **cuando** abre la sección, **entonces** ve «Caducado» y «El permiso caducó y la publicación diaria está en pausa. Reconecta LinkedIn para reanudarla.».
  4. **Dado** `live: false`, **cuando** abre la sección, **entonces** ve «La publicación real está desactivada en el servidor (`LIVE_LINKEDIN_OFFICIAL=false`): no sale nada a LinkedIn aunque la cuenta esté conectada.».
  5. **Dado** la app de LinkedIn sin configurar en el servidor, **cuando** abre la sección, **entonces** ve «Falta configurar la app de LinkedIn en el servidor (`LINKEDIN_CLIENT_ID`, …)» y no hay botón de conectar.
  6. **Dado** un usuario sin `approve_actions`, **cuando** abre la sección, **entonces** ve «Tu usuario no tiene el permiso «approve_actions», necesario para conectar LinkedIn.».
  7. **Dado** la cuenta oficial en pausa, **cuando** abre la sección, **entonces** ve «La cuenta oficial está en pausa: …».
  8. **Dado** la carga o un error, **cuando** abre la sección, **entonces** ve «Consultando LinkedIn…» o el error con «Reintentar».
- **Brechas código/docs:** en la app, si la sesión se restauró sin usuario ([ACC-06](acceso.md#acc-06)), la sección dice por error que no tiene el permiso `approve_actions`.
- **Cobertura QA:** pendiente

### AJU-07 · Conectar o reconectar LinkedIn <a id="aju-07"></a>

- **Dónde:** PWA · app · backend
- **Estado:** parcial
- **Qué hace para Gustavo:** autoriza a 0ff1ce a publicar en su perfil con la API oficial y, cada unos 60 días, reconecta.
- **Código:** `GET /api/v1/linkedin/oauth/start` y `…/callback` (`linkedin_views.py`, `connectors_linkedin.connect_member`); PWA `ajustes/LinkedIn.tsx`, `ajustes/linkedin.ts`; app `ajustes/LinkedIn.tsx`, `navigation.ts` (abre la PWA en una pestaña del navegador del sistema).
- **Criterios de aceptación:**
  1. **Dado** la PWA, **cuando** pulsa «Conectar LinkedIn» (o «Reconectar LinkedIn»), **entonces** el navegador navega a `/api/v1/linkedin/oauth/start`, que responde 302 a LinkedIn con `scope=openid profile w_member_social` y un `state` de un solo uso válido 10 minutos.
  2. **Dado** que autoriza en LinkedIn, **cuando** vuelve, **entonces** llega a `/ajustes?linkedin=ok`, ve «LinkedIn conectado» con «La publicación diaria ya puede usar la API oficial con tu cuenta.» y los parámetros desaparecen de la URL.
  3. **Dado** un fallo, **cuando** vuelve a `/ajustes?linkedin=error&motivo=…`, **entonces** ve «No se pudo conectar LinkedIn» con el mensaje de su motivo (`sesion`, `permiso`, `state`, `denegado`, `code`, `scope`, `canje`) y «Entendido».
  4. **Dado** que LinkedIn no concede `w_member_social`, **cuando** vuelve, **entonces** el motivo es `scope` y no se guarda nada.
  5. **Dado** una cuenta pausada por token caducado, **cuando** reconecta, **entonces** se guarda el token nuevo (cifrado) y se levanta esa pausa.
  6. **Dado** la app, **cuando** pulsa «Conectar LinkedIn», **entonces** completa la conexión y vuelve a la app con el resultado visible. **Hoy es parcial:** la app abre la página `/ajustes#linkedin` de la PWA en una pestaña del navegador del sistema; Gustavo necesita tener sesión de la PWA en ese navegador, el retorno de LinkedIn se queda en esa pestaña (la cierra él) y los errores solo se ven allí. Al volver, la app compara el estado y muestra «LinkedIn conectado» si cambió.
  7. **Dado** un token de dispositivo (la app) en `oauth/start`, **cuando** se llama, **entonces** responde 403: el OAuth exige la sesión con cookie.
  8. **Dado** la app de LinkedIn sin configurar, **cuando** se llama a `oauth/start`, **entonces** responde 503 con su `detail`.
- **Brechas código/docs:** `app-movil-backend.md` lo reconoce («Conectar LinkedIn (OAuth) necesita la PWA»). En Tu turno de la app, «Reconectar LinkedIn» abre la PWA en el navegador externo y no refresca el estado al volver.
- **Cobertura QA:** pendiente

### AJU-08 · Permiso del micrófono <a id="aju-08"></a>

- **Dónde:** PWA · app
- **Estado:** funciona
- **Qué hace para Gustavo:** ve si 0ff1ce puede usar el micrófono y, si lo bloqueó, cómo volver a permitirlo.
- **Código:** PWA `ajustes/Captura.tsx`; app `ajustes/Captura.tsx`.
- **Criterios de aceptación:**
  1. **Dado** la sección «Captura y galería», **cuando** la abre, **entonces** ve el estado del micrófono («Permitido», «Bloqueado», «Sin pedir», «Comprobando…» o «No disponible») y «Se usa solo mientras mantienes el botón aguamarina o grabas desde la hoja de captura.».
  2. **Dado** «Sin pedir», **cuando** pulsa «Permitir el micrófono», **entonces** aparece el aviso del sistema.
  3. **Dado** «Bloqueado», **cuando** abre la sección, **entonces** ve «Para volver a permitirlo» con los pasos (navegador e iPhone en la PWA; «Apps › 0ff1ce › Permisos › Micrófono» y «Abrir los ajustes del teléfono» en la app).
  4. **Dado** un navegador sin grabación, **cuando** abre la sección en la PWA, **entonces** ve «Este navegador no permite grabar audio. Puedes seguir enviando fotos y notas.».
- **Brechas código/docs:** en la app, un error al comprobar el permiso se ignora y la etiqueta puede quedarse en «Comprobando…». Ninguna interfaz muestra el estado del permiso de cámara o de fotos.
- **Cobertura QA:** pendiente

### AJU-09 · Edición con IA por defecto en las fotos nuevas <a id="aju-09"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** elige «No editar», «Que decida el equipo» (inicial) o «Editar» para las fotos nuevas.
- **Código:** `GET|PATCH /api/v1/ajustes/preferencias {gallery_ai_edit}`; `ajustes/Captura.tsx` y `AIEditControl.tsx` de ambas interfaces.
- **Criterios de aceptación:**
  1. **Dado** el selector «Edición con IA», **cuando** cambia la opción, **entonces** envía `gallery_ai_edit` (no/auto/si) y muestra «Edición con IA guardada para las fotos nuevas.».
  2. **Dado** ese valor guardado, **cuando** adjunta fotos en captura o sube a Galería, **entonces** lo toman las fotos nuevas; las existentes no cambian.
  3. **Dado** un error al guardar, **cuando** termina, **entonces** vuelve la selección anterior y aparece el aviso de error.
  4. **Dado** que las preferencias no han cargado o se están guardando, **cuando** mira el selector, **entonces** está desactivado.
- **Brechas código/docs:** implementación terminada; validación de fase 2 en CI pendiente.
- **Cobertura QA:** `11-ajustes` (guardar y revertir tras error), `05-captura-envios`; Jest y Vitest de Ajustes y captura. Escritos; ejecución pendiente de Claude.

### AJU-10 · Acceso a «Lo que el equipo sabe de ti» <a id="aju-10"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** desde Ajustes salta a la lista de datos que el equipo puede usar.
- **Código:** `facts_count` de `GET /api/v1/ajustes`; PWA `ajustes/Sesion.tsx` (enlace a `/tu-turno/sabe`); app `ajustes/Sesion.tsx` (enlace a `/tu-turno?tab=sabe`).
- **Criterios de aceptación:**
  1. **Dado** 12 datos confirmados, **cuando** abre Ajustes, **entonces** la tarjeta dice «12 datos confirmados» y lleva a «Lo que el equipo sabe de ti» ([TUR-15](tu-turno.md#tur-15)).
  2. **Dado** que `facts_count` no llega, **cuando** se pinta, **entonces** dice «Los datos que confirmaste y su visibilidad».
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### AJU-11 · Orden y anclas de Ajustes <a id="aju-11"></a>

- **Dónde:** PWA · app
- **Estado:** funciona
- **Qué hace para Gustavo:** encuentra cada sección en el mismo orden, y los enlaces le llevan directo a la sección.
- **Código:** PWA `Ajustes.tsx`, `compartido/src/logic/ajustes.ts` (anclas); app `ajustes/AjustesScreen.tsx` (`?ancla=`).
- **Criterios de aceptación:**
  1. **Dado** Ajustes, **cuando** lo abre, **entonces** las secciones van en este orden: Máquina, Orientación para el equipo, Autonomía y límites, Gasto de IA, LinkedIn oficial, Captura y galería, Notificaciones, Lo que el equipo sabe de ti, Sesión y Acerca de.
  2. **Dado** el enlace `/ajustes#maquina` en la PWA (o `?ancla=maquina` en la app), **cuando** lo abre, **entonces** baja a esa sección; `ancla=autonomia` abre además el pliegue.
  3. **Dado** la PWA en escritorio, **cuando** abre Ajustes, **entonces** ve un índice a la izquierda que salta a cada sección.
  4. **Dado** la app, **cuando** abre Ajustes, **entonces** llega desde el icono de la barra superior.
- **Brechas código/docs:** la app no tiene «tirar para recargar» en Ajustes.
- **Cobertura QA:** pendiente

---

## Imágenes

El backend devuelve la línea Imágenes con el gasto de ambos proveedores, sin tope propio (desde el 10/11/2026 cuenta en el presupuesto general de IA); la presentación queda para fase 2: ver [IMG-13](imagenes-en-publicaciones.md#img-13) ([imagenes-en-publicaciones.md](imagenes-en-publicaciones.md)).

## Retiradas

Ninguna.
