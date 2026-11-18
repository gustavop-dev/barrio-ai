# Cómo dar de alta a un miembro

Para Gustavo. Así entra una persona nueva de ProjectApp (por ejemplo, tu CTO) a Barrio AI con su propio usuario y su propio
LinkedIn, sin tocar nada de lo tuyo. Son unos 30 minutos tuyos y unos 15 suyos, en dos momentos.

**Qué cambia para ti:** nada hasta el último paso. Mientras la persona está «en alta» (inactiva), el sistema no trabaja su
cuenta y tu día sigue igual. Cuando la activas, cada uno tiene su calendario, su ritmo y su cola; las oportunidades siguen
siendo un solo embudo de la empresa.

**Lo que nunca pasa:** el sistema no escribe ni guarda su clave de LinkedIn, no le pone contraseña sin ti, no la activa solo
y no manda mensajes en su nombre. Mientras su voz es «provisional», nada de lo que el equipo escriba por ella sale sin que
ella lo apruebe.

## Antes de empezar

- Ten a mano: su nombre como quiere que aparezca, su rol («CTO»), una frase de cómo se presenta y el nombre corto que
  usarás para su usuario (por ejemplo `laura`).
- Elige el nombre de su cuenta en el servicio navegador (por ejemplo `laura`): es el nombre de la carpeta de su sesión.
- En el servidor, todo se corre desde `/opt/barrio-ai/deploy`. Para no repetir, define el atajo:

  ```bash
  ssh barrio-ai
  cd /opt/barrio-ai/deploy
  alias dc='docker compose -f compose.prod.yaml --env-file .env'
  ```

- Comprueba que `OPERATOR_ALERT_WEBHOOK` del `.env` es un canal **privado tuyo** de Slack (ahí llegan tus avisos y los de la
  empresa; nunca los de ella). Si no lo es, cámbialo antes de seguir.
- Si no lo hiciste: pon el aviso de memoria del servidor (`crontab -e` y la línea de `deploy/memoria.sh` de
  [deploy/README.md](../deploy/README.md#memoria-del-servidor)).

## Paso 1 · Ensayar el alta (no cambia nada)

```bash
dc exec api python manage.py operador --usuario gustavo alta-miembro \
  --usuario-nuevo laura --nombre "Laura Gómez" --rol CTO \
  --relacion "Es la CTO de ProjectApp." --cuenta-directo laura
```

**Qué ves:** «ENSAYO (nada cambió; repite con --confirmar)» y la lista de lo que haría: su usuario, sus grupos, sus ajustes
prudentes (rampa baja, topes a la mitad, todo en aprobación, su post una hora después del tuyo), su perfil mínimo, su voz
provisional, su cuenta del navegador y una propuesta de reparto.

**Cómo verificas:** lee que los valores son los que esperas. Si algo no te gusta, corrige el comando y vuelve a ensayar.

## Paso 2 · Hacer el alta

El mismo comando con `--confirmar` al final.

**Qué ves:** «Alta aplicada: Laura Gómez (laura), inactivo hasta activar-miembro.» y, debajo, «Lo que falta a mano:» con
casillas: `[x]` hecho, `[ ]` pendiente, `[?]` algo que debes verificar tú.

**Cómo verificas:** `dc exec api python manage.py operador --usuario gustavo miembros` la lista como «inactivo». Puedes repetir
el alta: no duplica nada y respeta lo que hayas cambiado a mano.

## Paso 3 · Darle su contraseña

```bash
dc exec api python manage.py changepassword laura
```

Escribe una contraseña y entrégasela **en persona o por un canal privado** (nunca por Slack ni en un archivo).

## Paso 4 · Lo que hace ella (en su teléfono o su computador)

Mándale la guía [Tu primera semana en Barrio AI](tu-primera-semana.md). En resumen, ella:

1. Entra en la app o en la PWA con su usuario y su contraseña. Verá un aviso «Tu cuenta está en alta»: es normal.
2. Conecta su LinkedIn oficial: **Ajustes › LinkedIn › Conectar** (LinkedIn le pide permiso; ella acepta).
3. Abre la sesión de su navegador: **Ajustes › Máquina**, en su cuenta, **«Conectar LinkedIn»**. Se abre una pantalla con
   la página de LinkedIn; ella escribe su clave y su código. Nadie más los ve ni los guarda.
   - Esto necesita `LINKEDIN_CONEXION_APP=true` en el `.env`. Si está apagado, hazlo con ella por SSH (los pasos de
     «Paso a paso» del [README del navegador](../agentes-linkedin/navegador/README.md#conectar-desde-la-app)), con ella
     escribiendo su clave.
4. Completa **Ajustes › Mi perfil**: cómo se presenta y los temas que no domina.

**Cómo verificas:** vuelve a correr el paso 5 en ensayo; las comprobaciones de su LinkedIn y de su navegador pasan a «ok».

## Paso 5 · Ensayar la activación

```bash
dc exec api python manage.py operador --usuario gustavo activar-miembro --miembro laura
```

**Qué ves:** ocho líneas, cada una `[ok]` o `[FALLA]` con el motivo:

| Comprobación | Si falla, qué hacer |
| --- | --- |
| Puede entrar | Paso 3 (contraseña) |
| Cuenta oficial conectada | Ella repite Ajustes › LinkedIn › Conectar |
| Cuenta directo con sesión sana | Ella repite «Conectar LinkedIn» en Ajustes › Máquina |
| Hora de publicación propia | `operador --usuario gustavo ajustes --miembro laura --fijar EDITORIAL_POST_TIME=09:30` (otra hora) |
| Autonomía en aprobación | `ajustes --miembro laura --fijar OPERATOR_AUTONOMY=…` todo en `approval` (lo deja el alta) |
| Rampa en la etapa baja | `ajustes --miembro laura --fijar OPERATOR_INVITE_RAMP_START=0` |
| Ninguna ruta pide «el» miembro | Un fallo del sistema: no la actives y avísale a quien mantiene el código |
| Memoria libre del servidor | El servidor no tiene memoria para su navegador: ver «Cuándo crecer» en [deploy/README.md](../deploy/README.md#memoria-del-servidor) |

Si todo está `[ok]`: «Todo pasa. Repite con --confirmar para activarla.»

## Paso 6 · Activarla

El mismo comando con `--confirmar`. **Qué ves:** «Laura Gómez está activa: el autopiloto trabaja sus cuentas con su ritmo.»
Si algo falló, no la activa y te dice qué.

**Cómo verificas:** en la app, **Ajustes › Organización** te muestra a los dos como «Activo»; ella ya no ve el aviso de alta.

## Paso 7 · Decisiones tuyas (cuando quieras)

- **Reparto de candidatos:** el alta propone `PEOPLE_ROLE_PREFERENCE=lider_tecnologia=laura` (los líderes de tecnología que
  nadie ha tocado irían a ella). Está apagado. Si lo quieres, ponlo en el `.env` y `dc up -d`.
- **Cuándo deja de necesitar su aprobación:** confirmar su voz **no** cambia nada solo. Si un día quieres que sus comentarios
  salgan sin su aprobación: `operador --usuario gustavo ajustes --miembro laura --fijar OPERATOR_AUTONOMY=INT-03=auto,…`.
- **La primera semana con dos navegadores:** mira `docker stats --no-stream` y `free -m` en el servidor un par de veces.

## Desactivarla (si hace falta)

```bash
dc exec api python manage.py operador --usuario gustavo desactivar-miembro --miembro laura --motivo "Vacaciones"            # ensayo
dc exec api python manage.py operador --usuario gustavo desactivar-miembro --miembro laura --motivo "Vacaciones" --confirmar
```

**Qué pasa:** su cuenta deja de leer y escribir, su cola se cancela, lo que tenía aprobado espera, y todo lo suyo se queda
guardado. Nada tuyo cambia. Sin `--sin-acceso` ella aún entra a sus ajustes y puede volver a conectar su LinkedIn (lo
necesita para volver); con `--sin-acceso` no puede entrar.

**Para volver:** el alta otra vez (paso 2, le devuelve el acceso) y la activación (pasos 5 y 6), con todas sus comprobaciones.
