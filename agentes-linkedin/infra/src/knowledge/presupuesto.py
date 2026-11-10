"""The team's single AI budget (Gustavo, 10/11/2026: «los límites generales, mensuales, 100 USD»).

- AI_MONTHLY_LIMIT_USD (default 100): everything the team spends on AI in the calendar month (OPERATOR_TIMEZONE), every
  provider and every purpose together.
- AI_DAILY_FUSE_USD (default 15): a safety fuse, not a budget per area. It only stops a runaway from spending the month
  in one day; a normal day spends a few dollars.
Both count settled cost and pending reservations of the usage ledger. There are no per-area daily caps any more; a
<PROVIDER>_LIMIT_USD, when set, is an extra monthly ceiling for that provider only.
"""
import os
from datetime import datetime, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

MONTHLY_STOP = 'Presupuesto mensual de IA agotado'
FUSE_STOP = 'Tope de seguridad diario de IA alcanzado'
PROVIDER_STOP = 'Límite local de '  # an optional <PROVIDER>_LIMIT_USD (knowledge.providers.reserve)
STOPS = (MONTHLY_STOP, FUSE_STOP, PROVIDER_STOP)

SPENT = ("coalesce(sum(CASE WHEN status='complete' THEN actual_usd WHEN status IN ('reserved','uncertain') "
         "THEN reserved_usd ELSE 0 END),0)")


def _usd(name, default):
    try:
        value = Decimal(str(os.environ.get(name, '').strip() or default))
    except ArithmeticError:
        raise ValueError(f'{name} inválido') from None
    if not value.is_finite() or value < 0:
        raise ValueError(f'{name} inválido')
    return value


def monthly_limit():
    return _usd('AI_MONTHLY_LIMIT_USD', '100')


def daily_fuse():
    return _usd('AI_DAILY_FUSE_USD', '15')


def _local(now=None):
    return (now or datetime.now(timezone.utc)).astimezone(ZoneInfo(os.environ.get('OPERATOR_TIMEZONE', 'America/Bogota')))


def month_start(now=None):
    return _local(now).replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def day_start(now=None):
    return _local(now).replace(hour=0, minute=0, second=0, microsecond=0)


def spent_since(c, since, purpose_like='%', provider=None):
    query = f'SELECT {SPENT} AS spent FROM usage_ledger WHERE created_at>=%s AND purpose LIKE %s'
    args = [since, purpose_like]
    if provider:
        query += ' AND provider=%s'
        args.append(provider)
    return Decimal(c.execute(query, args).fetchone()['spent'])


def check(c, amount, now=None):
    """Inside providers.reserve, with its advisory lock held: refuse a reservation that would pass either limit."""
    month, day = spent_since(c, month_start(now)), spent_since(c, day_start(now))
    if month + amount > monthly_limit():
        raise ValueError(f'{MONTHLY_STOP} (AI_MONTHLY_LIMIT_USD={monthly_limit()}): este mes van '
                         f'{month} USD, incluidas reservas pendientes; la reserva pedía {amount} USD.')
    if day + amount > daily_fuse():
        raise ValueError(f'{FUSE_STOP} (AI_DAILY_FUSE_USD={daily_fuse()}): hoy van {day} USD, '
                         f'incluidas reservas pendientes; se reanuda mañana.')


def status(now=None):
    from .db import connect
    with connect() as c:
        month, day = spent_since(c, month_start(now)), spent_since(c, day_start(now))
    return {'month_usd': month, 'today_usd': day, 'monthly_limit_usd': monthly_limit(), 'daily_fuse_usd': daily_fuse(),
            'left_usd': max(Decimal(0), min(monthly_limit() - month, daily_fuse() - day))}


def left(now=None):
    """What the team can still spend now: the smaller of what is left this month and today under the fuse."""
    return status(now)['left_usd']
