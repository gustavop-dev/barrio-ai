"""Optional workflow hooks. Standalone knowledge providers do not import Django."""
from contextvars import ContextVar

class CycleStopped(Exception):
    """A workflow limit; fallbacks catching ValueError must not swallow it."""


_current = ContextVar('orchestration_cycle', default=None)
_active_call = ContextVar('orchestration_call', default=None)


def current():
    return _current.get()


def provider_metadata(provider, purpose, amount, connection):
    if current() is None:return {}
    from team_backend.orquestacion import provider_metadata as reserve
    return reserve(provider, purpose, amount, connection)


def timeout(default):
    if current() is None:return default
    from team_backend.orquestacion import timeout as remaining
    return remaining(default)


def after_settle():
    if current() is None:return
    from team_backend.orquestacion import after_settle as settled
    settled()
