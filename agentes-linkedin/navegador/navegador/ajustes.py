"""Settings, read once from the environment. Fail-closed: without a token the service does not start.

The pause before each LinkedIn call and the per-account budgets are the guards of the spike (2026-11-13). The pause
has a floor (PAUSE_FLOOR) whatever the environment says, and a ceiling so the backend's 75 s wait still covers the
queue, the pause and LinkedIn's 30 s (docs/navegador-contrato.md)."""
import hashlib
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

PAUSE_FLOOR, PAUSE_CEILING = 3.0, 15.0
TOKEN_MIN = 24
# A call must reach the page within this many seconds of arriving, or it does not leave (503): with the pause and
# LinkedIn's 30 s it stays under the backend's 75 s, so the backend never gives up on a call that still goes out.
DEADLINE = 35.0
LINKEDIN_TIMEOUT_MS = 30000
# Per account, a backstop behind the operator's own daily caps (README, «Topes frente al ritmo real»): a production
# day of one account is at most about 880 reads and 90 writes (20 comments and replies, 20 reactions, 20 follows,
# 20 invitations, 10 accepts). Windows are rolling, while the operator counts local days: two halves of two days can
# fall in one window, hence about 1.5 times its caps per kind. The hourly ones smooth the network rounds.
WRITE_KINDS = ('comment', 'reaction', 'follow', 'invitation', 'accept')
BUDGETS = {('read', 'hour'): 150, ('read', 'day'): 1000, ('write', 'hour'): 15, ('write', 'day'): 100,
           ('comment', 'day'): 30, ('reaction', 'day'): 30, ('follow', 'day'): 30, ('invitation', 'day'): 30,
           ('accept', 'day'): 15}
BUDGET_ENV = {('read', 'hour'): 'NAVEGADOR_LECTURAS_HORA', ('read', 'day'): 'NAVEGADOR_LECTURAS_DIA',
              ('write', 'hour'): 'NAVEGADOR_ESCRITURAS_HORA', ('write', 'day'): 'NAVEGADOR_ESCRITURAS_DIA',
              ('comment', 'day'): 'NAVEGADOR_COMENTARIOS_DIA', ('reaction', 'day'): 'NAVEGADOR_REACCIONES_DIA',
              ('follow', 'day'): 'NAVEGADOR_SEGUIMIENTOS_DIA', ('invitation', 'day'): 'NAVEGADOR_INVITACIONES_DIA',
              ('accept', 'day'): 'NAVEGADOR_ACEPTACIONES_DIA'}
ACCOUNT = re.compile(r'[a-z0-9][a-z0-9_\-]{0,62}')  # the backend's ConnectorAccount.external_account_id
# Where a browser goes out to the internet: straight (DIRECT) or through a proxy given as scheme://host:port, never with
# a user or password in it (those come apart, from NAVEGADOR_PROXY_USUARIO and _CLAVE, and are never logged or stored).
DIRECT = 'directo'
# A login from the app (conexion.py): how long the remote view may stay open, within these bounds.
CONNECT_MINUTES, CONNECT_FLOOR, CONNECT_CEILING = 10.0, 2.0, 30.0
PROXY = re.compile(r'(http|https|socks5)://([A-Za-z0-9.\-]{1,253}|\[[0-9A-Fa-f:.]{2,45}\]):(\d{1,5})')


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Egress:
    """One account's way out to the internet: '' straight out, or a proxy server. The credentials stay out of repr."""
    server: str = ''
    username: str = field(default='', repr=False)
    password: str = field(default='', repr=False)

    @property
    def label(self):
        """What the account remembers of it (almacen.Store.egress): 'directo', or a hash of the proxy's host and port.
        Neither the address nor any credential."""
        if not self.server:
            return DIRECT
        return 'proxy-' + hashlib.sha256(urlsplit(self.server).netloc.lower().encode()).hexdigest()[:12]

    def option(self):
        """Playwright's `proxy` launch option, or None to go straight out."""
        if not self.server:
            return None
        return {'server': self.server, **({'username': self.username, 'password': self.password} if self.username else {})}


@dataclass(frozen=True)
class Settings:
    token: str
    data: Path
    pause: tuple = (3.0, 7.0)
    budgets: dict = field(default_factory=lambda: dict(BUDGETS))
    deadline: float = DEADLINE
    reload_hours: float = 6.0  # the feed is loaded again after this long: fresh query ids, a page that looks used
    idle_minutes: float = 0.0  # close an account's browser after this long without calls (0 = never): ~1 GiB each
    headless: bool = False
    host: str = '127.0.0.1'
    port: int = 8790
    proxy: str = ''  # every account's egress unless `proxies` names its own ('' = straight out)
    proxies: dict = field(default_factory=dict)  # account -> its own proxy server, or '' to go straight out
    proxy_user: str = field(default='', repr=False)
    proxy_password: str = field(default='', repr=False)
    # Logging in from the app (conexion.py, README «Conectar desde la app»): off unless NAVEGADOR_CONEXION=true.
    connect: bool = False
    connect_minutes: float = CONNECT_MINUTES
    connect_screen: str = ':98'  # the login's own virtual screen, never the service's (:99)
    view_port: int = 8791  # noVNC and its WebSocket, only while a login lasts
    novnc: Path = Path('/usr/share/novnc')

    def account_dir(self, account):
        return self.data / 'cuentas' / account

    def egress(self, account):
        server = self.proxies.get(account, self.proxy)
        return Egress(server, self.proxy_user, self.proxy_password) if server else Egress()


def pause(low, high):
    """(low, high) seconds, raised to the floor and capped; high never below low."""
    low = min(max(float(low), PAUSE_FLOOR), PAUSE_CEILING)
    return low, min(max(float(high), low), PAUSE_CEILING)


def number(env, name, default, cast=int):
    raw = (env.get(name) or '').strip()
    if not raw:
        return default
    try:
        value = cast(raw)
    except ValueError:
        raise ConfigError(f'{name} debe ser un número.') from None
    if value < 0:
        raise ConfigError(f'{name} no puede ser negativo.')
    return value


def proxy(name, raw):
    """A proxy server checked and kept as given; '' for none or 'directo'. The message never repeats the value."""
    raw = (raw or '').strip()
    if not raw or raw.lower() == DIRECT:
        return ''
    found = PROXY.fullmatch(raw)
    if not found or not 0 < int(found.group(3)) < 65536:
        raise ConfigError(f'{name}: se esperaba esquema://servidor:puerto (http, https o socks5) o «{DIRECT}», sin usuario '
                          'ni clave (van en NAVEGADOR_PROXY_USUARIO y NAVEGADOR_PROXY_CLAVE).')
    return raw


def proxies(env):
    """NAVEGADOR_PROXY_CUENTAS: «cuenta=esquema://servidor:puerto» or «cuenta=directo», separated by commas."""
    out = {}
    for item in filter(None, (x.strip() for x in (env.get('NAVEGADOR_PROXY_CUENTAS') or '').split(','))):
        account, _, server = item.partition('=')
        if not ACCOUNT.fullmatch(account.strip()):
            raise ConfigError('NAVEGADOR_PROXY_CUENTAS: cada elemento es cuenta=esquema://servidor:puerto o cuenta=directo.')
        out[account.strip()] = proxy('NAVEGADOR_PROXY_CUENTAS', server)
    return out


def load(env=None, need_token=True):
    env = os.environ if env is None else env
    token = (env.get('NAVEGADOR_TOKEN') or '').strip()
    if need_token and len(token) < TOKEN_MIN:
        raise ConfigError(f'Falta NAVEGADOR_TOKEN (al menos {TOKEN_MIN} caracteres): el servicio no arranca sin él.')
    budgets = {key: number(env, name, BUDGETS[key]) for key, name in BUDGET_ENV.items()}
    default, own = proxy('NAVEGADOR_PROXY', env.get('NAVEGADOR_PROXY')), proxies(env)
    user, password = env.get('NAVEGADOR_PROXY_USUARIO') or '', env.get('NAVEGADOR_PROXY_CLAVE') or ''
    if bool(user) != bool(password):
        raise ConfigError('NAVEGADOR_PROXY_USUARIO y NAVEGADOR_PROXY_CLAVE van juntos.')
    if user and any(s.startswith('socks5:') for s in (default, *own.values())):
        raise ConfigError('Chromium no admite usuario y clave en un proxy socks5: usa http o https, o uno sin clave.')
    return Settings(
        token=token,
        data=Path(env.get('NAVEGADOR_DATOS') or 'datos').resolve(),
        pause=pause(number(env, 'NAVEGADOR_PAUSA_MIN', 3.0, float), number(env, 'NAVEGADOR_PAUSA_MAX', 7.0, float)),
        budgets=budgets,
        reload_hours=number(env, 'NAVEGADOR_RECARGA_HORAS', 6.0, float),
        idle_minutes=number(env, 'NAVEGADOR_CIERRE_INACTIVO_MIN', 0.0, float),
        headless=(env.get('NAVEGADOR_HEADLESS') or 'false').lower() == 'true',
        host=env.get('NAVEGADOR_HOST') or '127.0.0.1',
        port=number(env, 'NAVEGADOR_PUERTO', 8790),
        proxy=default,
        proxies=own,
        proxy_user=user,
        proxy_password=password,
        connect=(env.get('NAVEGADOR_CONEXION') or 'false').strip().lower() == 'true',
        connect_minutes=min(max(number(env, 'NAVEGADOR_CONEXION_MIN', CONNECT_MINUTES, float), CONNECT_FLOOR),
                            CONNECT_CEILING),
        connect_screen=(env.get('NAVEGADOR_PANTALLA_CONEXION') or ':98').strip(),
        view_port=number(env, 'NAVEGADOR_PUERTO_PANTALLA', 8791),
        novnc=Path(env.get('NAVEGADOR_NOVNC') or '/usr/share/novnc'),
    )
