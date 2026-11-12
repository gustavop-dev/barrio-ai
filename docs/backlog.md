# Backlog

Pendientes que quedan fuera de lo esencial. La fuente de verdad sigue siendo el catálogo (`docs/funcionalidades/`): cuando
algo de aquí se resuelve, se actualiza su ID allí y se borra de esta lista.

Los números son fijos: un punto resuelto se borra y los demás conservan el suyo.

Prioridad: **A** (afecta seguridad o al uso diario), **B** (funciona, pero mal o incompleto) y **C** (detalle visual o
comodidad).

Leyenda de la columna «Quién»:

- **Gustavo**: necesita una acción o decisión suya.
- **Equipo**: lo resuelve el equipo de agentes; los cambios los hace Codex y Claude los sube y verifica en CI y QA.

## Dependen de Gustavo

| # | Prioridad | Qué | Por qué importa | Quién |
|---|---|---|---|---|
| 1 | A | Notificaciones push en el teléfono (Firebase) | Sin Firebase las push no llegan al celular; solo se ven dentro de la app (PUS-07, PUS-08, PUS-10). La app ya está preparada: una build de EAS con la variable secreta `GOOGLE_SERVICES_JSON` incluye Firebase sin cambiar la huella de las OTA (`movil/app.config.js`). Falta: crear el proyecto de Firebase con la app Android `co.projectapp.office`, subir la llave FCM V1 (cuenta de servicio) a las credenciales de EAS, crear la variable `GOOGLE_SERVICES_JSON` (tipo archivo, preview y production, secreta) con `google-services.json` y compilar un APK nuevo. | Gustavo + Equipo |
| 3 | B | Hacer `qa` obligatorio antes de fusionar | Hoy un PR se puede fusionar con QA en rojo. El comando exacto (`gh api … /rulesets`) está en `movil/.maestro/README.md`, sección «Check obligatorio para los PR». | Gustavo |
| 4 | B | Compilar el APK en GitHub en vez de EAS | **Aplazado** (Gustavo, 11/11). Las máquinas de GitHub no tienen cola ni límite de 15 builds al mes; el CI ya compila un APK en GitHub para QA. Falta exportar la llave de firma desde EAS (`eas credentials`) para que el teléfono acepte el APK como actualización. | Gustavo + Equipo |

## Bugs

| # | Prioridad | Qué | Detalle |
|---|---|---|---|
| 9 | C | El tablero de oportunidades muestra como mucho 100 (PRS-07) | Pide una sola página de 100 y no avisa si hay más. Hoy no hay tantas oportunidades. |
| 10 | B | Falta el botón «Desactivar notificaciones en este dispositivo» (PUS-03) | Está en el catálogo como parcial. Tiene sentido cuando las push lleguen al teléfono (#1). |

## Detalles visuales

| # | Prioridad | Dónde | Qué |
|---|---|---|---|
| 22 | C | Tu turno | La tarjeta de conversación no sigue TuTurno.dc.html: faltan «Resumen del hilo», «Borrador sugerido» y «Copiar borrador», y «Por qué importa» muestra porcentajes crudos. |

Revisado el 11/11: se resolvieron los puntos 5, 6, 7, 8, 11-21 y 23-28. Se descartaron el 2 (decisión de Gustavo) y la cobertura
E2E que faltaba (29-31): CAL-10, SEM-07 y TUR-05 los cubren las pruebas del backend o de la app, y un flujo más alarga el CI.
