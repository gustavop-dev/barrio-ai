"""python -m navegador <orden>  (README.md tiene el detalle)

  servir                       el servicio HTTP (necesita NAVEGADOR_TOKEN)
  login <cuenta>               abre el navegador de esa cuenta para entrar A MANO en LinkedIn
  importar <carpeta> <cuenta>  copia un perfil de Chromium que ya tiene sesión como cuenta nueva (el original no se toca)
  reanudar <cuenta>            quita la parada de una cuenta detenida
  estado [<cuenta>]            perfil, sesión, parada, salida y consumo de cada cuenta
  salida <cuenta> [--aceptar]  la salida a internet de la cuenta; --aceptar la cambia a la configurada
  canario <cuenta>             la revisión diaria, solo lectura, a través del servicio en marcha
  rodaje <cuenta>              la prueba de resistencia de la fase 4: un día de producción, día tras día
  rodaje estado [<cuenta>]     los últimos días de rodaje en una tabla

Los datos van en NAVEGADOR_DATOS (por defecto ./datos): un perfil de navegador por cuenta y su estado."""
import argparse
import asyncio
import os
import shutil
import sys
import time

from . import ajustes, pagina, rodaje
from .almacen import IMPORTED, Store
from .cuenta import WORDS

LOCK_WAIT, LOCK_TRIES = 30, 5  # another browser on the profile: wait 30 s, up to 5 times
# Never copied from another profile: Chromium's locks of the browser that had it open, and caches it rebuilds.
SKIP = ('Singleton*', 'lockfile', 'Cache', 'Code Cache', 'GPUCache', 'DawnGraphiteCache', 'DawnWebGPUCache',
        'GrShaderCache', 'GraphiteDawnCache', 'ShaderCache', 'BrowserMetrics*')


def account_name(name):
    if not ajustes.ACCOUNT.fullmatch(name or ''):
        sys.exit('Nombre de cuenta inválido: minúsculas, números, - y _ (como external_account_id en Barrio).')
    return name


def wait_free(profile):
    for attempt in range(LOCK_TRIES + 1):
        if not pagina.profile_busy(profile):
            return
        if attempt == LOCK_TRIES:
            sys.exit('El perfil sigue abierto en otro navegador (¿el servicio?): no se hizo nada. Detén el servicio y '
                     'vuelve a intentarlo.')
        print(f'perfil en uso; espero {LOCK_WAIT} s ({attempt + 1}/{LOCK_TRIES})', flush=True)
        time.sleep(LOCK_WAIT)


def session_word(profile):
    return {True: 'sí', False: 'no', None: 'no se sabe'}[pagina.stored_session(profile)]


def same_egress(settings, store, name):
    """The profile opens only by the internet exit its session last used, as in the service (cuenta.Account._egress)."""
    egress, last = settings.egress(name), store.egress()
    if last is not None and last != egress.label:
        sys.exit(f'La salida a internet de «{name}» no es la de su última sesión ({last}; ahora {egress.label}): no se '
                 f'abrió nada. Si el cambio es a propósito: python -m navegador salida {name} --aceptar')
    return egress, last


async def login(settings, name):
    """A visible window on LinkedIn's login page. The person types the password and the verification there: nothing
    passes through this program. Closing the window ends it."""
    store = Store(settings.account_dir(name))
    store.profile.mkdir(parents=True, exist_ok=True, mode=0o700)
    egress, last = same_egress(settings, store, name)
    wait_free(store.profile)
    ctx = await pagina.launch(store.profile, headless=False, proxy=egress.option())
    if last is None:
        store.set_egress(egress.label)
    try:
        tab = ctx.pages[0] if ctx.pages else await ctx.new_page()
        await tab.goto(pagina.LOGIN)
        print('Entra en LinkedIn en la ventana (la clave y la verificación las escribes tú; no pasan por este '
              'programa). Cuando veas tu inicio, cierra la ventana.', flush=True)
        while ctx.pages:
            await asyncio.sleep(0.5)
    finally:
        try:
            await ctx.close()
        except Exception:  # already closed with the window
            pass
        await pagina.stop_driver()
    # Read from the profile on disk: closing the last window ends the browser, and Chromium writes its cookies then.
    has = pagina.stored_session(store.profile)
    print('Sesión guardada.' if has else 'No quedó sesión: vuelve a intentarlo.')
    if store.stopped():
        print('La cuenta sigue detenida. Cuando sepas por qué se detuvo: python -m navegador reanudar ' + name)
    return 0 if has else 1


def import_profile(settings, source, name):
    """Copy a Chromium profile (for instance the spike's, with its saved session) as a new account. Only reads the
    original; refuses while a browser has it open or when the account already has a profile."""
    source = os.path.realpath(source)
    if not os.path.isdir(os.path.join(source, 'Default')):
        sys.exit('Esa carpeta no parece un perfil de Chromium (no tiene Default/).')
    if pagina.profile_busy(source):
        sys.exit('Ese perfil está abierto en otro navegador: ciérralo y vuelve a intentarlo.')
    store = Store(settings.account_dir(name))
    if store.profile.exists():
        sys.exit('Esa cuenta ya tiene perfil: no se sobrescribe.')
    store.root.mkdir(parents=True, exist_ok=True, mode=0o700)
    partial = store.root / '.perfil-importando'
    shutil.rmtree(partial, ignore_errors=True)
    shutil.copytree(source, partial, symlinks=True, ignore=shutil.ignore_patterns(*SKIP))
    os.chmod(partial, 0o700)
    partial.rename(store.profile)
    store.set_egress(IMPORTED)  # its session went out from another machine: opening it here is a change of exit
    files = sum(len(f) for _, _, f in os.walk(store.profile))
    print(f'Perfil copiado como «{name}» ({files} archivos). Sesión guardada: {session_word(store.profile)}.')
    print(f'Su sesión salía a internet desde otro equipo. Antes de abrirla aquí: python -m navegador salida {name} '
          '--aceptar (mejor si sale por la misma conexión que aquel equipo).')
    return 0


def resume(settings, name):
    store = Store(settings.account_dir(name))
    if not store.exists():
        sys.exit('Cuenta desconocida.')
    was = store.resume()
    print(f'Reanudada. Estaba detenida desde {was.get("desde") or "?"}: {was.get("motivo") or "?"}' if was
          else 'No estaba detenida.')
    return 0


def internet_exit(settings, name, accept=False):
    """Show the account's last internet exit and the configured one; --aceptar records the configured one."""
    store = Store(settings.account_dir(name))
    if not store.exists():
        sys.exit('Cuenta desconocida.')
    label, last = settings.egress(name).label, store.egress()
    if accept:
        store.set_egress(label)
        print(f'Salida de «{name}» aceptada: {label} (antes {last or "ninguna"}). La próxima vez se abre por ella.')
    else:
        print(f'{name}: última salida {last or "ninguna"}; configurada {label}'
              + ('' if last in (None, label) else '. DISTINTA: no se abre hasta aceptarla con --aceptar'))
    return 0


def status(settings, name=None):
    ready = None if settings.headless else pagina.display_ready()
    if ready is not None:  # run it with `docker compose exec` to see the service's own screen
        print(f'pantalla {pagina.display()}: ' + ('lista' if ready else
                                                  'NO RESPONDE: el navegador no puede abrir; reinicia el contenedor'))
    folder = settings.data / 'cuentas'
    names = [name] if name else sorted(p.name for p in folder.iterdir() if p.is_dir()) if folder.is_dir() else []
    if not names:
        print(f'No hay cuentas en {folder}.')
    now = time.time()
    for name in names:
        store = Store(settings.account_dir(name))
        if not store.exists():
            print(f'{name}: sin perfil')
            continue
        stopped = store.stopped()
        used = {k: store.usage(k, now) for k in ('read', 'write', *ajustes.WRITE_KINDS)}
        hour = {k: sum(1 for t in v if now - t < 3600) for k, v in used.items()}
        kinds = ', '.join(f'{WORDS[k]} {len(used[k])}' for k in ajustes.WRITE_KINDS if used[k])
        last, label = store.egress(), settings.egress(name).label
        print(f'{name}: sesión guardada {session_word(store.profile)}; '
              f'{"en uso por un navegador" if pagina.profile_busy(store.profile) else "sin navegador abierto"}; '
              + (f'DETENIDA desde {stopped.get("desde")}: {stopped.get("motivo")}' if stopped else 'activa')
              + f'; salida {last or "ninguna"}' + ('' if last in (None, label) else f' (DISTINTA de la configurada, {label})')
              + f'; lecturas {hour["read"]}/h {len(used["read"])}/día, escrituras {hour["write"]}/h '
              f'{len(used["write"])}/día' + (f' ({kinds})' if kinds else ''))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python -m navegador', description=__doc__.split('\n\n')[0])
    orders = parser.add_subparsers(dest='orden', required=True)
    orders.add_parser('servir', help='el servicio HTTP')
    orders.add_parser('login', help='entrar a mano en LinkedIn').add_argument('cuenta')
    imported = orders.add_parser('importar', help='copiar un perfil existente como cuenta')
    imported.add_argument('carpeta')
    imported.add_argument('cuenta')
    orders.add_parser('reanudar', help='quitar la parada de una cuenta').add_argument('cuenta')
    orders.add_parser('estado', help='estado de las cuentas').add_argument('cuenta', nargs='?')
    exit_order = orders.add_parser('salida', help='la salida a internet de una cuenta')
    exit_order.add_argument('cuenta')
    exit_order.add_argument('--aceptar', action='store_true', help='usar desde ahora la salida configurada')
    canary = orders.add_parser('canario', help='revisión diaria de solo lectura')
    canary.add_argument('cuenta')
    canary.add_argument('--url', help='dirección del servicio (por defecto NAVEGADOR_URL o 127.0.0.1:NAVEGADOR_PUERTO)')
    rodaje.options(orders.add_parser('rodaje', help='prueba de resistencia de la fase 4 (README «Rodaje»)'))
    args = parser.parse_args(argv)
    soak_status = args.orden == 'rodaje' and args.cuenta == 'estado'
    try:
        settings = ajustes.load(need_token=args.orden in ('servir', 'canario', 'rodaje') and not soak_status)
        if args.orden == 'rodaje':
            named = args.otra if soak_status else args.cuenta
            if named:  # none: RODAJE_CUENTA was empty too, and rodaje.main says so
                account_name(named)
            return rodaje.main(args, settings)
    except ajustes.ConfigError as exc:
        sys.exit(str(exc))
    name = account_name(args.cuenta) if getattr(args, 'cuenta', None) else None
    if args.orden == 'servir':
        from .servidor import serve
        serve(settings)
        return 0
    if args.orden == 'login':
        return asyncio.run(login(settings, name))
    if args.orden == 'importar':
        return import_profile(settings, args.carpeta, name)
    if args.orden == 'reanudar':
        return resume(settings, name)
    if args.orden == 'estado':
        return status(settings, name)
    if args.orden == 'salida':
        return internet_exit(settings, name, args.aceptar)
    from .canario import run
    url = args.url or os.environ.get('NAVEGADOR_URL') or f'http://127.0.0.1:{settings.port}'
    return run(url, settings.token, name, settings.data)


if __name__ == '__main__':
    sys.exit(main())
