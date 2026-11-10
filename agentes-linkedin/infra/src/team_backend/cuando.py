"""The day and hour Gustavo asks for a post («publícalo mañana a las 10», «el jueves a las 3 de la tarde»).

Deterministic on purpose: the model (Jev or the structured route) only says WHICH literal fragment asks for a
date; this module turns that fragment into a day and an hour, so the same words always give the same slot.
"""
import re
import unicodedata
from datetime import date, time, timedelta

WEEKDAYS = ['lunes', 'martes', 'miercoles', 'jueves', 'viernes', 'sabado', 'domingo']
MONTHS = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre',
          'noviembre', 'diciembre']
NUMBERS = {'una': 1, 'uno': 1, 'dos': 2, 'tres': 3, 'cuatro': 4, 'cinco': 5, 'seis': 6, 'siete': 7, 'ocho': 8,
           'nueve': 9, 'diez': 10, 'once': 11, 'doce': 12}
HOUR = r'(\d{1,2}|' + '|'.join(NUMBERS) + r')'
MINUTES = r'(?::(\d{2})|\s+y\s+(media|cuarto))?'
PERIOD = r'(?:\s*(am|a\.?\s?m\.?|pm|p\.?\s?m\.?|de la manana|de la tarde|de la noche))?'
AT = re.compile(r'\ba\s+las?\s+' + HOUR + MINUTES + PERIOD + r'\b')
BARE = re.compile(r'\b(\d{1,2})' + MINUTES + r'\s*(am|a\.?\s?m\.?|pm|p\.?\s?m\.?)(?![a-z])')  # not «5 a mis»


def _plain(text):
    text = unicodedata.normalize('NFKD', text.lower())
    return ''.join(c for c in text if not unicodedata.combining(c))


def _hour(raw, minutes, extra, period):
    hour = int(raw) if raw.isdigit() else NUMBERS[raw]
    minute = int(minutes) if minutes else {'media': 30, 'cuarto': 15}.get(extra or '', 0)
    period = (period or '').replace('.', '').replace(' ', '')
    if period in ('pm', 'delatarde', 'delanoche') and hour < 12:
        hour += 12
    elif period in ('am', 'delamanana') and hour == 12:
        hour = 0
    elif not period and 1 <= hour <= 6:
        hour += 12  # «a las 3» in a day of posts (07:00–21:00) is the afternoon
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return time(hour, minute)


def parse_time(text):
    plain = _plain(text)
    if re.search(r'\b(al\s+)?mediodia\b', plain):
        return time(12, 0)
    match = AT.search(plain)
    if match:
        return _hour(*match.groups())
    match = BARE.search(plain)
    if match:
        raw, minutes, extra, period = match.groups()
        return _hour(raw, minutes, extra, period)
    return None


def parse_day(text, today):
    plain = _plain(text)
    if re.search(r'\bpasado\s+manana\b', plain):
        return today + timedelta(days=2)
    # «hoy», «esta mañana/tarde/noche» are today; «mañana» is tomorrow; «de/por/en la mañana» is the morning.
    if re.search(r'\bhoy\b|\besta\s+(manana|tarde|noche)\b', plain):
        return today
    if re.search(r'(?<!la )\bmanana\b', plain.replace('pasado manana', '')):
        return today + timedelta(days=1)
    match = re.search(r'\b(\d{1,2})\s+de\s+(' + '|'.join(MONTHS) + r')\b', plain)
    if match:
        day, month = int(match.group(1)), MONTHS.index(match.group(2)) + 1
        for year in (today.year, today.year + 1):
            try:
                found = date(year, month, day)
            except ValueError:
                return None
            if found >= today:
                return found
    match = re.search(r'\b(\d{1,2})/(\d{1,2})\b', plain)
    if match:
        for year in (today.year, today.year + 1):
            try:
                found = date(year, int(match.group(2)), int(match.group(1)))
            except ValueError:
                return None
            if found >= today:
                return found
    match = re.search(r'\b(' + '|'.join(WEEKDAYS) + r')\b', plain)
    if match:
        ahead = (WEEKDAYS.index(match.group(1)) - today.weekday()) % 7 or 7  # «el jueves» said on Thursday: next week
        return today + timedelta(days=ahead)
    return None


def parse(text, today):
    """(day or None, hour or None) asked in `text`."""
    return parse_day(text, today), parse_time(text)
