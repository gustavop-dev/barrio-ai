"""A fake Chromium for the unit tests. The real Page (navegador/pagina.py) runs on it, so everything but patchright is
exercised: the HTTP API, the guards, the page checks and the live query capture. Every LinkedIn answer is invented."""
import asyncio
import tempfile
import uuid
from dataclasses import replace
from pathlib import Path

from linkedin_directo import rutas

from navegador.ajustes import Settings
from navegador.pagina import FEED, Page

TOKEN = 'token-de-prueba-0123456789abcdef'
POST = '7100000000000000001'
PROFILE = 'ACoPersonaFicticia0001'
MESSAGING = ('https://www.linkedin.com/voyager/api/voyagerMessagingGraphQL/graphql?queryId=messengerConversations.'
             '0123456789abcdef0123456789abcdef&variables=(mailboxUrn:urn%3Ali%3Afsd_profile%3AACoCuentaFicticia01)')


def raw(status=200, text='{"data":{}}', ctype='application/json', url='https://www.linkedin.com/voyager/api/me',
        kind='basic'):
    """What the in-page fetch returns."""
    return {'status': status, 'type': kind, 'url': url, 'ctype': ctype, 'text': text}


def call(**fields):
    """A read call as the backend sends it (ServiceTransport), with a fresh request_id."""
    return {'method': 'GET', 'path': '/voyager/api/me', 'kind': 'voyager', 'body': None, 'write': False,
            'operation': 'account_status', 'request_id': str(uuid.uuid4()), **fields}


def reaction(**fields):
    return call(**{'method': 'POST', 'path': rutas.sdui(rutas.REACT), 'kind': 'sdui', 'write': True,
                   'operation': 'add_reaction', 'body': rutas.envelope(rutas.reaction(POST, 'LIKE')), **fields})


def invitation(note, **fields):
    return call(**{'method': 'POST', 'path': rutas.voyager(rutas.INVITE), 'kind': 'voyager', 'write': True,
                   'operation': 'send_invitation', 'body': rutas.invitation(PROFILE, note), **fields})


class Request:
    """A request of the page's own, as the context's `request` event shows it."""

    def __init__(self, url, method='GET', headers=None):
        self.url, self.method, self.headers = url, method, headers or {}


class Response:
    def __init__(self, url, status):
        self.url, self.status = url, status


class Browser:
    """One fake world: whether the profile has a session, where the feed lands, what the page asks for by itself
    while loading, and LinkedIn's answers to our fetches (in order: a dict, a callable of the fetch arguments, or an
    exception to raise). `after(tab)` runs after each fetch: LinkedIn moving the page, the cookie going away."""

    def __init__(self, answers=(), session=True, landing=FEED, own_calls=()):
        self.answers, self.session, self.landing, self.own_calls = list(answers), session, landing, list(own_calls)
        self.fetches, self.contexts, self.gotos, self.events, self.proxies = [], [], 0, [], []
        self.active = self.most = 0
        self.gate = None  # an asyncio.Event every fetch waits on
        self.after = None
        self.fail_launch = None

    async def launch(self, profile, headless=False, proxy=None):
        if self.fail_launch:
            raise self.fail_launch
        self.proxies.append(proxy)
        ctx = Context(self)
        self.contexts.append(ctx)
        return ctx

    @property
    def launches(self):
        return len(self.contexts)


class Context:
    def __init__(self, browser):
        self.browser, self.handlers, self.closed = browser, {}, False
        self.pages = [Tab(self)]

    def on(self, event, handler):
        self.handlers.setdefault(event, []).append(handler)

    def emit(self, event, value):
        for handler in self.handlers.get(event, []):
            handler(value)

    async def cookies(self, url=None):
        if self.closed:
            raise RuntimeError('contexto cerrado')
        return [{'name': 'li_at', 'value': 'valor-ficticio'}] if self.browser.session else []

    async def new_page(self):
        tab = Tab(self)
        self.pages.append(tab)
        return tab

    async def close(self):
        self.closed, self.pages = True, []


class Tab:
    def __init__(self, ctx):
        self.ctx, self.url, self.closed = ctx, 'about:blank', False

    def is_closed(self):
        return self.closed or self.ctx.closed

    async def goto(self, url, **options):
        browser = self.ctx.browser
        browser.gotos += 1
        for request in browser.own_calls:
            self.ctx.emit('request', request)
        self.url = browser.landing

    async def wait_for_timeout(self, ms):
        pass

    async def evaluate(self, script, arg):
        browser = self.ctx.browser
        browser.fetches.append(arg)
        browser.events.append('fetch')
        browser.active += 1
        browser.most = max(browser.most, browser.active)
        try:
            if browser.gate:
                await browser.gate.wait()
            answer = browser.answers.pop(0) if browser.answers else raw()
            if isinstance(answer, BaseException):
                raise answer
            answer = answer(arg) if callable(answer) else answer
        finally:
            browser.active -= 1
        if browser.after:
            browser.after(self)
        return answer


class Clock:
    def __init__(self, now=1_900_000_000.0):
        self.now = now

    def __call__(self):
        return self.now


def settings(data, **changes):
    return replace(Settings(token=TOKEN, data=Path(data)), **changes)


def account_dir(data, name='prueba'):
    profile = Path(data) / 'cuentas' / name / 'perfil'
    profile.mkdir(parents=True, exist_ok=True)
    return profile.parent


class World:
    """A temporary data folder with one account, a fake browser, a clock the pauses move and the pauses taken."""

    def __init__(self, browser=None, **changes):
        self.tmp = tempfile.TemporaryDirectory()
        self.data = Path(self.tmp.name)
        account_dir(self.data)
        self.browser = browser or Browser()
        self.clock, self.pauses, self.advance, self.screen = Clock(), [], True, True
        self.settings = settings(self.data, **changes)

    def opener(self, profile, settings):
        return Page.open(profile, settings, launcher=self.browser.launch, clock=self.clock)

    async def sleep(self, seconds):
        self.pauses.append(seconds)
        self.browser.events.append('pausa')
        if self.advance:
            self.clock.now += seconds
        await asyncio.sleep(0)

    def deps(self):
        return {'opener': self.opener, 'clock': self.clock, 'sleep': self.sleep, 'rand': lambda low, high: high,
                'display': lambda: self.screen}
