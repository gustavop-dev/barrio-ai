"""The real page: one persistent Chromium profile per account (patchright, headed by default, as in the spike of
2026-11-13) left on LinkedIn's feed. Every call is a same-origin `fetch` run by the page itself: it leaves with the
browser's own cookies, TLS and fingerprint, and the csrf-token is read from the JSESSIONID cookie inside the page, so it
never reaches Python. Replaying the cookies from a script got a session revoked on the second call; this did not.

While the feed loads, the Voyager GETs the page makes by itself are recorded (path, query id and variable names, never
values): GraphQL query ids rotate with LinkedIn deploys and these are fresh. Only during the load: later on, the
page's requests include ours. The x-li-* headers the web app adds are kept to send the same ones (in memory only).

patchright is imported only when a browser opens: the unit tests replace the browser with a fake one (`launcher`)."""
import os
import socket
import sqlite3
import time
from pathlib import Path
from urllib.parse import unquote, urlsplit

from linkedin_directo.transporte import bad_path

from .ajustes import LINKEDIN_TIMEOUT_MS

ORIGIN = 'https://www.linkedin.com'
HOST = 'www.linkedin.com'
FEED = ORIGIN + '/feed/'
LOGIN = ORIGIN + '/login'
VOYAGER = '/voyager/api'
SDUI = '/flagship-web/rsc-action/actions/'
SETTLE_MS = 8000  # the messaging overlay asks for its conversations a few seconds after the feed
GOTO_TIMEOUT_MS = 45000
VOYAGER_COPY = ('x-li-lang', 'x-li-track', 'x-li-page-instance')  # what the web app adds; never its csrf-token
PAGING = {'start', 'count', 'paginationToken'}
ALARMS = (429, 999)

# Runs in the page. A redirect is not followed (`manual` turns it into an opaqueredirect) and a call gives up after
# `timeout` ms. The csrf-token is the JSESSIONID cookie, read here.
FETCH = """async ({url, method, headers, body, timeout}) => {
  const m = document.cookie.match(/JSESSIONID="?([^";]+)"?/);
  if (m) headers['csrf-token'] = m[1];
  const abort = new AbortController();
  const timer = setTimeout(() => abort.abort(), timeout);
  try {
    const res = await fetch(url, {method, headers, body: body ?? undefined, credentials: 'include',
                                  redirect: 'manual', signal: abort.signal});
    let text = '';
    try { text = await res.text(); } catch (e) {}
    return {status: res.status, type: res.type, url: res.url, ctype: res.headers.get('content-type') || '', text};
  } catch (e) {
    return {status: 0, type: abort.signal.aborted ? 'timeout' : 'error', url: '', ctype: '', text: ''};
  } finally {
    clearTimeout(timer);
  }
}"""


class NoSession(Exception):
    """The profile has no LinkedIn session: someone has to log in by hand."""


class Stop(Exception):
    """LinkedIn pushed back or the session went away while opening: the account stops."""


class Busy(Exception):
    """The profile is open in another browser (a login, another process)."""


# --- live GraphQL query ids ------------------------------------------------------------------------------------------
def variable_names(literal):
    """Top-level keys of a Rest.li literal: `(count:5,query:(keywords:x))` -> {'count', 'query'}. Values come
    percent-encoded, so a raw `(`, `,` or `:` is structure."""
    names, depth, key = set(), 0, ''
    for ch in literal:
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        elif depth == 1 and ch == ',':
            key = ''
        elif depth == 1 and ch == ':' and key is not None:
            names.add(key)
            key = None
        elif depth == 1 and key is not None:
            key += ch
    return names


def record(url):
    """A Voyager GET seen from outside: path after /voyager/api, query id and variable names, no values."""
    parts = urlsplit(url)
    query = dict(p.split('=', 1) for p in parts.query.split('&') if '=' in p)
    return {'path': parts.path.split(VOYAGER, 1)[-1], 'query_id': unquote(query.get('queryId', '')),
            'variables': sorted(variable_names(query.get('variables', '')))}


def pick_live(records, prefixes, variables):
    """The newest recorded call whose operation name starts with one of `prefixes` and used the same variable names,
    paging aside: one name can hide several finders, and only a call shaped like ours says which hash is ours."""
    want = set(variables) - PAGING
    for rec in reversed(records):
        if rec['query_id'] and rec['query_id'].split('.')[0].startswith(tuple(prefixes)) \
                and set(rec['variables']) - PAGING == want:
            return rec
    return None


# --- the profile on disk ---------------------------------------------------------------------------------------------
def is_browser(pid):
    """Whether a live pid is a Chromium. After a container restart the old lock's pid may belong to anything."""
    try:
        return 'chrom' in os.readlink(f'/proc/{pid}/exe').lower()
    except OSError:
        return True  # cannot tell: count it as a browser


def profile_busy(profile):
    """Chromium holds a SingletonLock symlink (`<host>-<pid>`) while a browser uses the profile. A lock left by a dead
    browser on this machine is not a lock: Chromium takes it over, and so do we (same rule as Chromium's: the pid must
    be alive and be a browser). The compose service has a fixed hostname so a restarted container is this machine."""
    lock = Path(profile) / 'SingletonLock'
    if not lock.is_symlink():
        return False
    host, _, pid = os.readlink(lock).rpartition('-')
    if host != socket.gethostname():
        return True
    try:
        os.kill(int(pid), 0)
    except (ValueError, ProcessLookupError):
        return False
    except PermissionError:
        return True
    return is_browser(pid)


def stored_session(profile):
    """Whether the profile's cookie store holds an unexpired li_at, without opening a browser or reading any value:
    True, False, or None when it cannot tell (no store yet, or one this code cannot read)."""
    path = Path(profile) / 'Default' / 'Cookies'
    if not path.is_file():
        return None
    now = int((time.time() + 11644473600) * 1_000_000)  # Chromium counts microseconds since 1601
    try:
        with sqlite3.connect(path.as_uri() + '?mode=ro&immutable=1', uri=True) as db:
            rows = db.execute("SELECT expires_utc FROM cookies WHERE name = 'li_at' AND host_key LIKE '%linkedin.com'"
                              ).fetchall()
    except sqlite3.Error:
        return None
    return any(not expires or expires > now for (expires,) in rows)


# --- the browser -----------------------------------------------------------------------------------------------------
_driver = None


async def driver():
    global _driver
    if _driver is None:
        from patchright.async_api import async_playwright
        _driver = await async_playwright().start()
    return _driver


async def stop_driver():
    global _driver
    if _driver is not None:
        try:
            await _driver.stop()
        finally:
            _driver = None


async def launch(profile, headless=False, proxy=None):
    """A persistent context on `profile`, as the spike opened it, going out through `proxy` (ajustes.Egress.option)
    when given. Headed needs a screen: WSL shells often export DISPLAY empty while WSLg listens on :0; the image runs a
    virtual one (entrada.sh)."""
    pw = await driver()
    env = {**os.environ, 'DISPLAY': os.environ.get('DISPLAY') or ':0'}
    options = {'proxy': proxy} if proxy else {}
    return await pw.chromium.launch_persistent_context(str(profile), headless=headless, no_viewport=not headless,
                                                       env=env, **options)


async def has_session(ctx):
    return any(c.get('name') == 'li_at' and c.get('value') for c in await ctx.cookies(ORIGIN))


class Page:
    """One account's open LinkedIn page. Account (cuenta.py) drives it; nothing here decides what may leave."""

    def __init__(self, ctx, tab, clock=time.time):
        self.ctx, self.tab, self.clock = ctx, tab, clock
        self.live = []  # GraphQL GETs the page made by itself while loading the feed
        self.voyager_headers = {}
        self.sdui_headers = {}  # x-li-* and accept of the page's own latest server-driven UI request
        self.alarms = []  # 429/999 on the page's own calls
        self.loaded_at = 0.0
        self._listening = False
        ctx.on('request', self._seen)
        ctx.on('response', self._answered)

    @classmethod
    async def open(cls, profile, settings, launcher=None, clock=time.time):
        """Open the profile and load the feed. NoSession: the profile has no session cookie (nothing was loaded).
        Stop: LinkedIn sent the feed elsewhere (login, checkpoint...). Busy: another browser holds the profile."""
        if profile_busy(profile):
            raise Busy()
        ctx = await (launcher or launch)(profile, headless=settings.headless,
                                         proxy=settings.egress(profile.parent.name).option())
        try:
            if not await has_session(ctx):
                raise NoSession()
            page = cls(ctx, ctx.pages[0] if ctx.pages else await ctx.new_page(), clock)
            await page.reload()
            return page
        except BaseException:
            try:
                await ctx.close()
            except Exception:  # the window may already be gone
                pass
            raise

    async def reload(self):
        """Load the feed, recording what the page asks for by itself. Raises Stop when it does not land on it."""
        self.live = []
        self._listening = True
        try:
            await self.tab.goto(FEED, wait_until='domcontentloaded', timeout=GOTO_TIMEOUT_MS)
            await self.tab.wait_for_timeout(SETTLE_MS)
        finally:
            self._listening = False
        self.loaded_at = self.clock()
        parts = urlsplit(self.tab.url)
        if bad_path(self.tab.url) or parts.netloc != HOST or not parts.path.startswith('/feed'):
            raise Stop(f'al cargar el inicio, LinkedIn llevó a /{parts.path.strip("/").split("/")[0]}')
        reason = await self.trouble()
        if reason:
            raise Stop(reason)

    def alive(self):
        try:
            return not self.tab.is_closed()
        except Exception:
            return False

    async def trouble(self):
        """Why the account must stop now ('' when nothing): the page on a login or checkpoint path, the session cookie
        gone, or 429/999 on the page's own calls. Raises when the page is no longer on LinkedIn at all (closed,
        crashed, an error page): that is the browser failing, not LinkedIn pushing back."""
        url = self.tab.url
        where = bad_path(url)
        if where:
            return f'la página está en {where}'
        if urlsplit(url).netloc != HOST:
            raise RuntimeError('la página no está en LinkedIn')
        if not await has_session(self.ctx):
            return 'se fue la cookie de sesión (li_at)'
        return self.alarms[0] if self.alarms else ''

    async def fetch(self, path, method, headers, body):
        """ONE call from inside the page: {status, type, url, ctype, text} as the page saw it."""
        return await self.tab.evaluate(FETCH, {'url': path, 'method': method, 'headers': dict(headers), 'body': body,
                                               'timeout': LINKEDIN_TIMEOUT_MS})

    async def close(self):
        try:
            await self.ctx.close()
        except Exception:  # the window may already be gone
            pass

    # --- what the page does by itself (recording must never break it) --------------------------------------------
    def _seen(self, request):
        try:
            url, method = request.url, request.method
            parts = urlsplit(url)
            if parts.netloc != HOST:
                return
            if self._listening and method == 'GET' and parts.path.startswith(VOYAGER + '/'):
                self.live.append(record(url))
                for key in VOYAGER_COPY:
                    if request.headers.get(key):
                        self.voyager_headers.setdefault(key, request.headers[key])
            # The app's own server-driven UI calls carry parentSpanId; ours do not, so only the page's are copied.
            if method == 'POST' and parts.path.startswith(SDUI) and 'parentSpanId=' in parts.query:
                self.sdui_headers = {k: v for k, v in request.headers.items() if k.startswith('x-li-') or k == 'accept'}
        except Exception:
            pass

    def _answered(self, response):
        try:
            if response.status in ALARMS and urlsplit(response.url).netloc.endswith('linkedin.com'):
                self.alarms.append(f'HTTP {response.status} en una llamada de la propia página')
        except Exception:
            pass
