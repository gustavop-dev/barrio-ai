"""The account's creator analytics, read from the answer of the export dialog (rutas.ANALYTICS_SCREEN). Sent by code
from the feed page on 2026-11-13, test account only: 7, 28 and 365 days read, but that account is nearly empty, so the
rows of posts and demographics have not been seen with data yet.

The dialog's component stream carries the whole workbook as JSON, `{"excelDoc": {documentTitle, sheets: [{name, rows:
[{index, cells: [{column, displayValue, style}]}]}]}}`. Seven sheets (six, see 7), always in this order. Their names,
headers and labels come in the language of the ACCOUNT, so everything is read by position, never by name:

1. discovery: a title row with the range, then the totals: impressions and members reached;
2. engagement: [date, impressions, engagements], one row per day;
3. latest posts: 15 columns of LIFETIME figures of the latest few posts (the range does not apply to them);
4. top posts: a note, then two tables side by side, [url, published, engagements] and [url, published, impressions],
   both with figures for the range (up to 50 posts, older ones included). Links name the post's urn (post_urn);
5. followers: a row with the total TODAY (whatever the range's end), then [date, new followers], one row per day;
6. audience demographics (followers), a snapshot that does not depend on the range: [group, label, percentage];
7. content demographics (who saw the posts in the range): the same columns. LinkedIn can leave this sheet out,
   probably when no post was seen in the range (2026-11-13, test account: six sheets, the sixth with only its
   header). Which of the two a lone sixth sheet is was not seen with data: it is read as the audience one, and the
   sheet names (LinkedIn's labels) go along in Workbook.sheets so an import can show which it was.

Every cell is a display string formatted for the account's locale: dates d/m/yyyy or m/d/yyyy (or ISO), thousands
with «.» or «,», percentages like «12 %» with a non-breaking space. Days are UTC. An empty cell or a dash is no data
(None), never 0. Anything else that does not read raises ParseError naming the sheet and row, never the value."""
import json
import re
from dataclasses import dataclass, field
from datetime import date, timedelta

from . import rutas
from .errores import LinkedInError

SHEETS = (6, 7)  # the content demographics sheet was left out for the nearly empty test account
POST_COLUMNS = 15
SPACES = re.compile(r'[\s    ]')
EMPTY = {'', '-', '–', '—', 'n/a', 'N/A'}
COUNT = re.compile(r'-?(?:\d{1,3}(?:([.,])\d{3})(?:\1\d{3})*|\d+)')
PERCENT = re.compile(r'(<)?(\d{1,3}(?:[.,]\d+)?)%')
SLASH = re.compile(r'(\d{1,2})/(\d{1,2})/(\d{4}|\d{2})')
ISO = re.compile(r'\d{4}-\d{2}-\d{2}')
# A post link: /feed/update/urn:li:<kind>:<n> or the readable /posts/<author>_<words>-<kind>-<n>-<hash> (the form the
# test account's export used on 2026-11-13, with a share urn).
URN = re.compile(r'urn(?::|%3A)li(?::|%3A)(activity|share|ugcPost)(?::|%3A)(\d{10,25})'
                 r'|[-_](activity|share|ugcPost)-(\d{10,25})(?=[-/?#]|$)')
DOC = re.compile(r'\{\s*"excelDoc"\s*:')
ORDERS = ('dmy', 'mdy')


class ParseError(LinkedInError):
    """The workbook changed shape. `sheet` and `row` say where (1-based, as LinkedIn numbers them); the message never
    carries a cell's value."""

    def __init__(self, sheet, row, what):
        where = ', '.join(p for p in (f'hoja {sheet}' if sheet else '', f'fila {row}' if row is not None else '') if p)
        super().__init__(f'Analítica de LinkedIn ilegible ({where or "libro"}): {what}.', kind='analytics_parse')
        self.sheet, self.row = sheet, row


@dataclass(frozen=True)
class Day:
    day: date
    impressions: int | None
    engagements: int | None
    new_followers: int | None = None


@dataclass(frozen=True)
class Post:
    """One of the latest posts, lifetime figures. `kind` is LinkedIn's own label (localized); percentages 0–100."""
    urn: str
    url: str
    published: date | None
    kind: str
    impressions: int | None
    network_pct: float | None
    outside_pct: float | None
    members_reached: int | None
    followers_gained: int | None
    profile_views: int | None
    reactions: int | None
    comments: int | None
    shares: int | None
    saves: int | None
    sends: int | None
    button_clicks: int | None


@dataclass(frozen=True)
class TopPost:
    urn: str
    url: str
    published: date | None
    value: int | None  # engagements or impressions in the range, by the list it is in


@dataclass(frozen=True)
class Demographic:
    """`group` is the label LinkedIn gives the row's group (location, seniority...), as written: no taxonomy of our
    own. `below` means LinkedIn wrote «< pct %»."""
    group: str
    label: str
    pct: float | None
    below: bool = False
    value: int | None = None


@dataclass(frozen=True)
class Workbook:
    start: date
    end: date
    impressions: int | None
    members_reached: int | None
    daily: list = field(default_factory=list)  # [Day], new_followers merged from sheet 5
    recent_posts: list = field(default_factory=list)  # [Post]
    top_by_engagements: list = field(default_factory=list)  # [TopPost]
    top_by_impressions: list = field(default_factory=list)  # [TopPost]
    followers_total: int | None = None
    audience: list = field(default_factory=list)  # [Demographic]
    content: list | None = None  # [Demographic]; None when the workbook has no content demographics sheet
    sheets: tuple = ()  # the sheet names, LinkedIn's labels in the account's language: for diagnosis only


# --- the stream ------------------------------------------------------------------------------------------------------
def excel_doc(stream):
    """The `excelDoc` object of the dialog's answer, wherever it sits in the stream (raw, or escaped in a string)."""
    for text in (stream or '', rutas.unescape(stream or '')):
        for match in DOC.finditer(text):
            try:
                found = json.JSONDecoder().raw_decode(text, match.start())[0]
            except ValueError:
                continue
            doc = found.get('excelDoc')
            if isinstance(doc, dict) and isinstance(doc.get('sheets'), list):
                return doc
    raise ParseError(None, None, 'la respuesta no trae el libro')


def read(stream, start, end, order=None):
    return parse(excel_doc(stream), start, end, order)


# --- cells -----------------------------------------------------------------------------------------------------------
def column(value, position):
    """A cell's column: an int, a digit string or a letter (A, B, ... AA); its position when it has none."""
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    if isinstance(value, str) and re.fullmatch(r'[A-Za-z]{1,3}', value):
        n = 0
        for ch in value.upper():
            n = n * 26 + ord(ch) - 64
        return n - 1
    return position


def rows(sheet):
    """[(row number, [(column, text)])] in order, empty cells and empty rows left out. The row number is the row's
    1-based position in the sheet's list, the one error messages give."""
    listed = sheet.get('rows') if isinstance(sheet, dict) else None
    out = []
    for i, row in enumerate(listed if isinstance(listed, list) else []):
        found = row.get('cells') if isinstance(row, dict) else None
        cells = []
        for j, item in enumerate(found if isinstance(found, list) else []):
            text = item.get('displayValue') if isinstance(item, dict) else None
            text = SPACES.sub(' ', text).strip() if isinstance(text, str) else ''
            if text:
                cells.append((column(item.get('column'), j), text))
        if cells:
            out.append((i + 1, sorted(cells)))
    return out


def count(text):
    """An integer as LinkedIn writes it in any locale: «1.234», «1,234», «1 234» or «1234»; None for no data."""
    raw = SPACES.sub('', text or '')
    if raw in EMPTY:
        return None
    if not COUNT.fullmatch(raw):
        raise ValueError
    return int(re.sub(r'[.,]', '', raw))


def percent(text):
    """(value 0–100, below) of «12 %», «12,5%» or «< 1 %»; (None, False) for no data. The sign is required: a bare
    number is not taken as a percentage."""
    raw = SPACES.sub('', text or '')
    if raw in EMPTY:
        return None, False
    found = PERCENT.fullmatch(raw)
    if not found:
        raise ValueError
    return float(found.group(2).replace(',', '.')), bool(found.group(1))


def day(text, order):
    text = SPACES.sub('', text or '')
    if ISO.fullmatch(text):
        return date.fromisoformat(text)
    found = SLASH.fullmatch(text)
    if not found:
        raise ValueError
    a, b, year = (int(x) for x in found.groups())
    year += 2000 if year < 100 else 0
    return date(year, b, a) if order == 'dmy' else date(year, a, b)


def is_date(text):
    text = SPACES.sub('', text or '')
    return bool(ISO.fullmatch(text) or SLASH.fullmatch(text))


def post_urn(url):
    """`urn:li:<activity|share|ugcPost>:<n>` of a post link; '' when it names none (an article, a newsletter)."""
    found = URN.search(url or '')
    if not found:
        return ''
    kind, number = (found.group(1), found.group(2)) if found.group(1) else (found.group(3), found.group(4))
    return f'urn:li:{kind}:{number}'


# --- the workbook ----------------------------------------------------------------------------------------------------
def date_order(sheets, start, end, hint):
    """d/m or m/d for the whole workbook: the one under which every slash date exists and every daily row falls in the
    range asked; the hint only decides between two that both fit and disagree. Raises ParseError when none fits or
    two fit with different dates and no hint."""
    every, daily = [], []
    for position in (1, 2, 3, 4):
        for _, cells in rows(sheets[position]):
            slashes = [t for _, t in cells if SLASH.fullmatch(SPACES.sub('', t))]
            every += slashes
            if position in (1, 4) and cells and SLASH.fullmatch(SPACES.sub('', cells[0][1])):
                daily.append(cells[0][1])
    if not every:
        return hint or 'dmy'
    fits = {}
    for order in ORDERS:
        try:
            dates = [day(t, order) for t in every]
        except ValueError:
            continue
        if all(start - timedelta(days=1) <= day(t, order) <= end + timedelta(days=1) for t in daily):
            fits[order] = dates
    if not fits:
        raise ParseError(None, None, 'fechas que no se leen como d/m ni como m/d dentro del rango')
    if len(fits) == 1 or fits['dmy'] == fits['mdy']:
        return next(iter(fits))
    if hint in fits:
        return hint
    raise ParseError(None, None, 'fechas ambiguas (d/m o m/d) y sin el idioma de la cuenta')


def parse(doc, start, end, order=None):
    """The Workbook of an excelDoc for [start, end]. `order` ('dmy' or 'mdy') is the account's date order when known."""
    sheets = doc.get('sheets') if isinstance(doc, dict) else None
    if not isinstance(sheets, list) or len(sheets) not in SHEETS:
        raise ParseError(None, None, f'el libro trae {len(sheets) if isinstance(sheets, list) else 0} hojas, '
                                     f'se esperaban {" o ".join(map(str, SHEETS))}')
    order = date_order(sheets, start, end, order)
    impressions, reached = discovery(sheets[0])
    engagement = daily(sheets[1], 2, order)
    total, followers = follower_rows(sheets[4], order)
    days = sorted(set(engagement) | set(followers))
    merged = [Day(d, *(engagement.get(d) or (None, None)), followers.get(d)) for d in days]
    by_engagements, by_impressions = top_posts(sheets[3], order)
    names = tuple(str(s.get('name') or '')[:80] if isinstance(s, dict) else '' for s in sheets)
    return Workbook(start, end, impressions, reached, merged, recent_posts(sheets[2], order), by_engagements,
                    by_impressions, total, demographics(sheets[5], 6),
                    demographics(sheets[6], 7) if len(sheets) > 6 else None, names)


def cell(sheet, row, text, read, what):
    try:
        return read(text)
    except ValueError:
        raise ParseError(sheet, row, what) from None


def discovery(sheet):
    """The first two rows with a label and a number: impressions, then members reached. The title row before them
    ends with the range, which is not a number."""
    totals = []
    for n, cells in rows(sheet):
        try:
            if len(cells) >= 2:
                totals.append(count(cells[-1][1]))
        except ValueError:
            if totals:
                raise ParseError(1, n, 'total ilegible') from None
    if len(totals) < 2:
        raise ParseError(1, None, 'faltan los totales de impresiones y miembros alcanzados')
    return tuple(totals[:2])


def daily(sheet, number, order):
    """{day: (first value, second value)} of the rows that start with a date; a header before them is skipped."""
    out = {}
    for n, cells in rows(sheet):
        if not is_date(cells[0][1]):
            if out:
                raise ParseError(number, n, 'fila sin fecha entre las filas diarias')
            continue
        values = dict(cells)
        first = cells[0][0]
        when = cell(number, n, cells[0][1], lambda t: day(t, order), 'fecha ilegible')
        out[when] = tuple(cell(number, n, values.get(first + k, ''), count, 'número ilegible') for k in (1, 2))
    return out


def follower_rows(sheet, order):
    """(total today, {day: new followers}). The total is the number on the first row before the daily header."""
    total, seen, per_day = None, False, {}
    for n, cells in rows(sheet):
        if is_date(cells[0][1]):
            seen = True
            when = cell(5, n, cells[0][1], lambda t: day(t, order), 'fecha ilegible')
            values = dict(cells)
            per_day[when] = cell(5, n, values.get(cells[0][0] + 1, ''), count, 'número ilegible')
        elif seen:
            raise ParseError(5, n, 'fila sin fecha entre las filas diarias')
        elif total is None:
            # «Total followers on <date>» and the number, in its own cell or after a colon in the same one.
            last = cells[-1][1] if len(cells) >= 2 else cells[0][1].rpartition(':')[2]
            try:
                total = count(last) if last != cells[0][1] else None
            except ValueError:
                continue  # the daily header: two labels
    if total is None:
        raise ParseError(5, None, 'falta el total de seguidores')
    return total, per_day


def header_before(table, first_data):
    """The last row before the first data row: the table's column headers."""
    before = [cells for n, cells in table if n < first_data]
    return before[-1] if before else []


def is_url(text):
    return text.startswith(('http://', 'https://'))


def recent_posts(sheet, order):
    table = rows(sheet)
    data = [(n, cells) for n, cells in table if is_url(cells[0][1])]
    if not data:
        return []
    header = header_before(table, data[0][0])
    if len(header) != POST_COLUMNS:
        raise ParseError(3, data[0][0] - 1, f'encabezado de {len(header)} columnas, se esperaban {POST_COLUMNS}')
    columns = [c for c, _ in header]
    out = []
    for n, cells in data:
        values = dict(cells)
        text = [values.get(c, '') for c in columns]
        counts = {i: cell(3, n, text[i], count, 'número ilegible') for i in (3, 6, 7, 8, 9, 10, 11, 12, 13, 14)}
        pcts = [cell(3, n, text[i], percent, 'porcentaje ilegible') for i in (4, 5)]
        out.append(Post(post_urn(text[0]), text[0], cell(3, n, text[1], lambda t: day(t, order) if t else None,
                                                        'fecha ilegible'),
                        text[2], counts[3], *(None if below else value for value, below in pcts), counts[6],
                        counts[7], counts[8], counts[9], counts[10], counts[11], counts[12], counts[13], counts[14]))
    return out


def top_posts(sheet, order):
    """Two tables side by side, by position: the left one ranks by engagements, the right one by impressions."""
    table = rows(sheet)
    data = [n for n, cells in table if any(is_url(t) for _, t in cells)]
    if not data:
        return [], []
    header = header_before(table, data[0])
    if len(header) != 6:
        raise ParseError(4, data[0] - 1, f'encabezado de {len(header)} columnas, se esperaban 6 (dos tablas)')
    starts = (header[0][0], header[3][0])
    lists = ([], [])
    for n, cells in table:
        if n < data[0]:
            continue
        values = dict(cells)
        for k, at in enumerate(starts):
            url = values.get(at, '')
            if not url:
                continue
            if not is_url(url):
                raise ParseError(4, n, 'fila sin enlace al post')
            published = values.get(at + 1, '')
            lists[k].append(TopPost(post_urn(url), url,
                                    cell(4, n, published, lambda t: day(t, order) if t else None, 'fecha ilegible'),
                                    cell(4, n, values.get(at + 2, ''), count, 'número ilegible')))
    return lists


def demographics(sheet, number):
    """[group, label, percentage] rows. The group is taken as written on each row. A row with a single text and no
    percentage after the first row is read as a group title for the rows under it (in case a layout puts it there);
    rows of several labels before the first percentage are headers."""
    out, group = [], ''
    for k, (n, cells) in enumerate(rows(sheet)):
        try:
            pct, below = percent(cells[-1][1]) if len(cells) >= 2 else (None, None)
        except ValueError:
            pct, below = None, None
        if below is None:
            if len(cells) == 1 and k:
                group = cells[0][1]
            elif out:
                raise ParseError(number, n, 'fila sin porcentaje')
            continue
        texts, value = [], None
        for _, text in cells[:-1]:
            try:
                number_found = count(text)
            except ValueError:
                texts.append(text)
                continue
            if number_found is not None:
                value = number_found
        if not texts:
            raise ParseError(number, n, 'fila sin etiqueta')
        out.append(Demographic(texts[0] if len(texts) > 1 else group, texts[-1] if len(texts) > 1 else texts[0], pct,
                               below, value))
    return out
