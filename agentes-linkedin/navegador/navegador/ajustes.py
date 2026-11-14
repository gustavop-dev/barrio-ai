"""Settings, read once from the environment. Fail-closed: without a token the service does not start.

The pause before each LinkedIn call and the per-account budgets are the guards of the spike (2026-11-13). The pause
has a floor (PAUSE_FLOOR) whatever the environment says, and a ceiling so the backend's 75 s wait still covers the
queue, the pause and LinkedIn's 30 s (docs/navegador-contrato.md)."""
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

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


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Settings:
    token: str
    data: Path
    pause: tuple = (3.0, 7.0)
    budgets: dict = field(default_factory=lambda: dict(BUDGETS))
    deadline: float = DEADLINE
    reload_hours: float = 6.0  # the feed is loaded again after this long: fresh query ids, a page that looks used
    headless: bool = False
    host: str = '127.0.0.1'
    port: int = 8790

    def account_dir(self, account):
        return self.data / 'cuentas' / account


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


def load(env=None, need_token=True):
    env = os.environ if env is None else env
    token = (env.get('NAVEGADOR_TOKEN') or '').strip()
    if need_token and len(token) < TOKEN_MIN:
        raise ConfigError(f'Falta NAVEGADOR_TOKEN (al menos {TOKEN_MIN} caracteres): el servicio no arranca sin él.')
    budgets = {key: number(env, name, BUDGETS[key]) for key, name in BUDGET_ENV.items()}
    return Settings(
        token=token,
        data=Path(env.get('NAVEGADOR_DATOS') or 'datos').resolve(),
        pause=pause(number(env, 'NAVEGADOR_PAUSA_MIN', 3.0, float), number(env, 'NAVEGADOR_PAUSA_MAX', 7.0, float)),
        budgets=budgets,
        reload_hours=number(env, 'NAVEGADOR_RECARGA_HORAS', 6.0, float),
        headless=(env.get('NAVEGADOR_HEADLESS') or 'false').lower() == 'true',
        host=env.get('NAVEGADOR_HOST') or '127.0.0.1',
        port=number(env, 'NAVEGADOR_PUERTO', 8790),
    )
