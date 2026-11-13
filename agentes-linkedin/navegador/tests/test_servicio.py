"""The navegador service over HTTP, on a fake browser (tests/falsos.py): the contract's statuses
(docs/navegador-contrato.md), the bearer token, one call at a time per account, the pause and its floor, the budgets,
the backend's allowlist checked again here, request_id de-duplication across restarts, the hard stop and its clearing,
the session check (423), the live query ids, the headers of each kind and logs without LinkedIn's data."""
import asyncio
import io
import json
import os
import socket
import unittest
from contextlib import redirect_stdout
from dataclasses import replace
from unittest.mock import patch

from aiohttp.test_utils import TestClient, TestServer

from linkedin_directo import rutas

from navegador import __main__ as cli
from navegador import ajustes
from navegador.almacen import Store
from navegador.servidor import build
from tests.falsos import MESSAGING, POST, PROFILE, TOKEN, Browser, Request, Response, World, call, invitation, raw, \
    reaction

AUTH = {'Authorization': f'Bearer {TOKEN}'}
QUERIES = '/v1/cuentas/prueba/consultas?'


async def until(condition, seconds=3.0):
    for _ in range(int(seconds / 0.01)):
        if condition():
            return
        await asyncio.sleep(0.01)
    raise AssertionError('no pasó a tiempo')


class ServiceCase(unittest.IsolatedAsyncioTestCase):
    browser_options = {}

    async def asyncSetUp(self):
        self.world = World(Browser(**self.browser_options))
        self.addCleanup(self.world.tmp.cleanup)
        self.client = await self.start()

    async def start(self):
        """The service as a new process would be: a fresh app on the same data folder (and the same fake browser)."""
        client = TestClient(TestServer(build(self.world.settings, **self.world.deps())))
        await client.start_server()
        self.addAsyncCleanup(client.close)
        return client

    async def post(self, body, account='prueba', headers=AUTH, client=None):
        response = await (client or self.client).post(f'/v1/cuentas/{account}/llamadas', json=body, headers=headers)
        return response.status, await response.json()

    async def get(self, query, client=None):
        response = await (client or self.client).get(QUERIES + query, headers=AUTH)
        return response.status, await response.json()

    @property
    def browser(self):
        return self.world.browser

    def store(self):
        return Store(self.world.settings.account_dir('prueba'))


class AuthTests(ServiceCase):
    async def test_health_needs_no_token_and_says_nothing(self):
        response = await self.client.get('/health')
        self.assertEqual((response.status, await response.json()), (200, {'status': 'ok'}))

    async def test_the_token_is_required_and_compared(self):
        cases = (({}, 401), ({'Authorization': 'Basic x'}, 401), ({'Authorization': 'Bearer'}, 401),
                 ({'Authorization': 'Bearer otro-token-de-prueba-0123456789'}, 403),
                 ({'Authorization': f'Bearer {TOKEN}x'}, 403))
        for headers, status in cases:
            with self.subTest(headers=headers):
                self.assertEqual((await self.post(call(), headers=headers))[0], status)
                response = await self.client.get(QUERIES + 'prefixes=messengerConversations&variables=mailboxUrn',
                                                 headers=headers)
                self.assertEqual(response.status, status)
        self.assertEqual((self.browser.launches, self.browser.fetches), (0, []))
        self.assertEqual((await self.post(call()))[0], 200)

    def test_no_token_no_service(self):
        for env in ({}, {'NAVEGADOR_TOKEN': 'corto'}, {'NAVEGADOR_TOKEN': ' ' * 40}):
            with self.subTest(env=env), self.assertRaises(ajustes.ConfigError):
                ajustes.load(env)
        self.assertEqual(ajustes.load({'NAVEGADOR_TOKEN': TOKEN}).token, TOKEN)
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(SystemExit):
            cli.main(['servir'])


class StatusTests(ServiceCase):
    async def test_200_is_linkedin_answer_as_it_came(self):
        self.browser.answers = [raw(200, '{"a":1}', 'application/json; charset=utf-8')]
        status, body = await self.post(call())
        self.assertEqual((status, body), (200, {'status': 200, 'text': '{"a":1}', 'redirected': False,
                                                'content_type': 'application/json; charset=utf-8',
                                                'url': 'https://www.linkedin.com/voyager/api/me'}))
        [fetch] = self.browser.fetches
        self.assertEqual((fetch['url'], fetch['method'], fetch['body']), ('/voyager/api/me', 'GET', None))

    async def test_400_for_a_malformed_call(self):
        bad = ['no es un objeto', call(request_id=None), call(request_id='corto'), call(method='PUT'),
               call(kind='graphql'), call(body=['x']), call(write='sí'), call(path=''), call(operation='Otra Cosa')]
        for body in bad:
            with self.subTest(body=str(body)[:60]):
                self.assertEqual((await self.post(body))[0], 400)
        response = await self.client.post('/v1/cuentas/prueba/llamadas', data='{no es json', headers=AUTH)
        self.assertEqual(response.status, 400)
        self.assertEqual((await self.get('prefixes=&variables=x'))[0], 400)
        self.assertEqual((await self.get('prefixes=a.b&variables=x'))[0], 400)
        self.assertEqual((self.browser.launches, self.browser.fetches), (0, []))

    async def test_404_for_an_unknown_account(self):
        for account in ('otra', 'MAYUS', 'a.b'):
            with self.subTest(account=account):
                self.assertEqual((await self.post(call(), account=account))[0], 404)
        response = await self.client.get('/v1/cuentas/otra/consultas?prefixes=a&variables=b', headers=AUTH)
        self.assertEqual(response.status, 404)

    async def test_422_outside_the_allowlist_nothing_leaves(self):
        unfollow = rutas.follow('3000003')
        unfollow['requestedArguments']['payload']['followStateType'] = 'FollowStateType_FOLLOW_INACTIVE'
        refused = {'lectura fuera de Voyager': call(path='/feed/'),
                   'dejar de seguir': call(method='POST', path=rutas.sdui(rutas.FOLLOW), kind='sdui', write=True,
                                           body=rutas.envelope(unfollow), operation='follow_user'),
                   'escritura marcada como lectura': reaction(write=False),
                   'un perfil como página': call(path='/in/una-persona/', kind='page'),
                   'otro host': call(path='//otro.example/voyager/api/me')}
        for why, body in refused.items():
            with self.subTest(why):
                status, answer = await self.post(body)
                self.assertEqual(status, 422)
                self.assertIn('no salió nada', answer['reason'])
        self.assertEqual((self.browser.launches, self.browser.fetches), (0, []))

    async def test_423_without_a_session_nothing_leaves_and_nothing_stops(self):
        self.browser.session = False
        status, body = await self.post(call())
        self.assertEqual(status, 423)
        self.assertIn('entrar a mano', body['reason'])
        self.assertEqual((self.browser.fetches, self.browser.gotos), ([], 0))
        self.assertIsNone(self.store().stopped())
        self.browser.session = True  # someone logged in by hand
        self.assertEqual((await self.post(call()))[0], 200)

    async def test_503_when_the_profile_is_open_elsewhere_or_the_browser_does_not_open(self):
        lock = self.world.data / 'cuentas' / 'prueba' / 'perfil' / 'SingletonLock'
        os.symlink(f'{socket.gethostname()}-{os.getpid()}', lock)
        with patch('navegador.pagina.is_browser', return_value=True):  # this live pid counts as a Chromium
            status, body = await self.post(call())
        self.assertEqual(status, 503)
        self.assertIn('otro navegador', body['reason'])
        self.assertEqual(self.browser.launches, 0)
        lock.unlink()
        self.browser.fail_launch = RuntimeError('sin pantalla')
        status, body = await self.post(call())
        self.assertEqual(status, 503)
        self.assertIn('no abrió', body['reason'])
        self.assertEqual(self.browser.fetches, [])

    async def test_504_when_the_page_fails_mid_call_and_that_write_is_never_repeated(self):
        self.browser.answers = [RuntimeError('la página navegó')]
        write = reaction()
        self.assertEqual((await self.post(write))[0], 504)
        self.assertEqual((await self.post(write))[0], 409)  # it may have left: never sent twice
        self.assertEqual(len(self.browser.fetches), 1)
        self.assertIsNone(self.store().stopped())
        self.assertEqual((await self.post(call()))[0], 200)  # the page is opened again for the next call
        self.assertEqual(self.browser.launches, 2)


class GuardTests(ServiceCase):
    async def test_one_call_at_a_time_per_account(self):
        self.browser.gate = asyncio.Event()
        calls = asyncio.gather(*(self.post(call()) for _ in range(3)))
        await until(lambda: self.browser.fetches)
        await asyncio.sleep(0.1)
        self.assertEqual(len(self.browser.fetches), 1)  # the others wait their turn
        self.browser.gate.set()
        self.assertEqual([status for status, _ in await calls], [200, 200, 200])
        self.assertEqual((self.browser.most, len(self.browser.fetches), self.browser.launches), (1, 3, 1))

    async def test_a_call_that_cannot_reach_the_page_in_time_does_not_leave(self):
        self.world.settings = replace(self.world.settings, deadline=0.3)
        self.world.advance = False
        client = await self.start()
        self.browser.gate = asyncio.Event()
        first = asyncio.ensure_future(self.post(call(), client=client))
        await until(lambda: self.browser.fetches)
        status, body = await self.post(call(), client=client)  # queued behind it past the deadline
        self.assertEqual(status, 503)
        self.browser.gate.set()
        self.assertEqual((await first)[0], 200)
        self.world.advance = True  # a 7 s pause runs past a 0.3 s deadline: nothing leaves either
        self.assertEqual((await self.post(call(), client=client))[0], 503)
        self.assertEqual(len(self.browser.fetches), 1)

    async def test_a_random_pause_before_every_call_never_below_the_floor(self):
        self.world.settings = ajustes.load({'NAVEGADOR_TOKEN': TOKEN, 'NAVEGADOR_DATOS': str(self.world.data),
                                            'NAVEGADOR_PAUSA_MIN': '0', 'NAVEGADOR_PAUSA_MAX': '0.5'})
        client = await self.start()
        for _ in range(2):
            self.assertEqual((await self.post(call(), client=client))[0], 200)
        self.assertEqual(self.world.pauses, [ajustes.PAUSE_FLOOR] * 2)
        self.assertEqual(self.browser.events, ['pausa', 'fetch', 'pausa', 'fetch'])

    async def test_budgets_per_hour_and_day_reads_and_writes_apart_kept_across_restarts(self):
        budgets = {('read', 'hour'): 2, ('read', 'day'): 10, ('write', 'hour'): 1, ('write', 'day'): 2}
        self.world.settings = replace(self.world.settings, budgets=budgets)
        client = await self.start()
        self.assertEqual((await self.post(reaction(), client=client))[0], 200)
        status, body = await self.post(reaction(), client=client)
        self.assertEqual(status, 422)
        self.assertIn('escrituras por hora', body['reason'])
        reads = [(await self.post(call(), client=client))[0] for _ in range(3)]
        self.assertEqual(reads, [200, 200, 422])  # reads have their own
        self.world.clock.now += 3601
        self.assertEqual((await self.post(reaction(), client=client))[0], 200)
        self.world.clock.now += 3601
        status, body = await self.post(reaction(), client=client)
        self.assertEqual(status, 422)
        self.assertIn('escrituras por día', body['reason'])
        again = await self.start()  # a restart forgets nothing
        self.assertEqual((await self.post(reaction(), client=again))[0], 422)
        self.world.clock.now += 86400
        self.assertEqual((await self.post(reaction(), client=again))[0], 200)
        self.assertEqual(len(self.browser.fetches), 5)


class RequestIdTests(ServiceCase):
    async def test_a_repeated_write_gets_the_stored_answer_and_is_never_sent_twice(self):
        self.browser.answers = [raw(200, '0:{"errors":[]}', 'text/x-component', 'https://www.linkedin.com/x')]
        write = reaction()
        first = await self.post(write)
        self.assertEqual((first[0], first[1]['text']), (200, '0:{"errors":[]}'))
        self.assertEqual(await self.post(write), first)
        again = await self.start()  # after a restart too
        self.assertEqual(await self.post(write, client=again), first)
        self.assertEqual((len(self.browser.fetches), self.browser.launches), (1, 1))

    async def test_the_same_id_while_it_is_out_is_refused(self):
        self.browser.gate = asyncio.Event()
        write = reaction()
        first = asyncio.ensure_future(self.post(write))
        await until(lambda: self.browser.fetches)
        status, body = await self.post(write)
        self.assertEqual(status, 409)
        self.assertIn('request_id', body['reason'])
        self.browser.gate.set()
        self.assertEqual((await first)[0], 200)
        self.assertEqual(len(self.browser.fetches), 1)

    async def test_a_write_lost_in_a_crash_is_never_sent_again(self):
        write = reaction()
        self.store().sending(write['request_id'], 0)
        self.assertEqual((await self.post(write))[0], 409)
        self.assertEqual((self.browser.fetches, self.browser.launches), ([], 0))


class StopTests(ServiceCase):
    async def send(self, answer=None, after=None, write=False):
        if answer:
            self.browser.answers = [answer]
        self.browser.after = after
        try:
            return await self.post(reaction() if write else call())
        finally:
            self.browser.after = None

    async def assert_stopped(self, word):
        stopped = self.store().stopped()
        self.assertIsNotNone(stopped)
        self.assertIn(word, stopped['motivo'])
        self.assertTrue(self.browser.contexts[-1].closed)  # the browser is closed at once
        before = (len(self.browser.fetches), self.browser.launches)
        status, body = await self.post(call())
        self.assertEqual(status, 409)
        self.assertIn('detenida', body['reason'])
        self.assertEqual((len(self.browser.fetches), self.browser.launches), before)

    async def test_pushback_goes_back_to_the_backend_and_stops_the_account(self):
        cases = ((raw(429, '{}'), '429'), (raw(999, ''), '999'), (raw(401, ''), '401'), (raw(403, '{}'), '403'),
                 (raw(0, '', '', kind='opaqueredirect'), 'redirección'),
                 (raw(200, '<html><title>Security Verification</title></html>', 'text/html'), 'HTML'),
                 (raw(200, '{}', url='https://www.linkedin.com/checkpoint/challenge/x'), '/checkpoint'))
        for answer, word in cases:
            with self.subTest(word=word):
                status, body = await self.send(answer)
                self.assertEqual((status, body['status']), (200, answer['status']))  # it left: its answer goes back
                await self.assert_stopped(word)
                self.store().resume()

    async def test_the_page_leaving_or_losing_its_session_stops_the_account(self):
        def checkpoint(tab):
            tab.url = 'https://www.linkedin.com/checkpoint/challenge/x'

        def logout(tab):
            self.browser.session = False

        def alarm(tab):
            tab.ctx.emit('response', Response('https://www.linkedin.com/li/track', 429))

        for after, word in ((checkpoint, '/checkpoint'), (logout, 'li_at'), (alarm, '429')):
            with self.subTest(word=word):
                status, body = await self.send(after=after, write=True)
                self.assertEqual((status, body['status']), (200, 200))
                await self.assert_stopped(word)
                self.store().resume()
                self.browser.session = True

    async def test_a_feed_that_lands_on_the_login_stops_before_anything_leaves(self):
        self.browser.landing = 'https://www.linkedin.com/login?session_redirect=x'
        status, _ = await self.post(reaction())
        self.assertEqual(status, 409)
        self.assertEqual(self.browser.fetches, [])
        await self.assert_stopped('/login')

    async def test_an_operator_clears_the_stop(self):
        self.browser.answers = [raw(429, '{}')]
        await self.post(call())
        self.assertEqual((await self.post(call()))[0], 409)
        with redirect_stdout(io.StringIO()) as out:
            cli.resume(self.world.settings, 'prueba')
        self.assertIn('429', out.getvalue())
        self.assertIsNone(self.store().stopped())
        self.assertEqual((await self.post(call()))[0], 200)
        self.assertEqual((len(self.browser.fetches), self.browser.launches), (2, 2))


class LiveQueryTests(ServiceCase):
    browser_options = {'own_calls': [Request(MESSAGING), Request('https://www.linkedin.com/voyager/api/me')]}
    ASKED = 'prefixes=messengerConversations,voyagerMessagingDashMessengerConversations&variables=mailboxUrn'
    FOUND = {'path': '/voyagerMessagingGraphQL/graphql', 'query_id': 'messengerConversations.' + '0123456789abcdef' * 2,
             'variables': ['mailboxUrn'], 'source': 'page'}

    async def test_the_page_own_query_id_shaped_like_ours(self):
        self.assertEqual(await self.get(self.ASKED), (200, self.FOUND))
        self.assertEqual(self.browser.fetches, [])  # nothing sent: it is what the page asked for while loading
        self.assertEqual((await self.get('prefixes=messengerConversations&variables=conversationUrn'))[0], 404)
        self.assertEqual((await self.get('prefixes=messengerMessages&variables=mailboxUrn'))[0], 404)
        # Later requests include ours: they are not recorded.
        self.browser.contexts[0].emit('request', Request(MESSAGING.replace('0123456789abcdef' * 2, 'f' * 32)))
        self.assertEqual(await self.get(self.ASKED), (200, self.FOUND))

    async def test_the_feed_is_loaded_again_after_some_hours(self):
        await self.post(call())
        self.world.clock.now += self.world.settings.reload_hours * 3600 + 1
        await self.post(call())
        self.assertEqual((self.browser.gotos, self.browser.launches), (2, 1))

    async def test_a_stopped_account_gives_no_query(self):
        self.store().stop('prueba', 0)
        self.assertEqual((await self.get(self.ASKED))[0], 409)
        self.assertEqual(self.browser.launches, 0)


class HeaderTests(ServiceCase):
    browser_options = {'own_calls': [
        Request(MESSAGING, headers={'x-li-lang': 'es_ES', 'x-li-track': 'pista', 'cookie': 'no', 'csrf-token': 'no'}),
        Request('https://www.linkedin.com/flagship-web/rsc-action/actions/component?componentId=x&parentSpanId=y', 'POST',
                {'x-li-page-instance': 'instancia', 'accept': '*/*', 'csrf-token': 'no', 'content-type': 'text/plain'})]}

    async def test_each_kind_carries_its_headers_and_python_never_holds_the_csrf_token(self):
        for body in (call(), invitation('Hola'), reaction(), call(path=rutas.post_page(POST), kind='page',
                                                                    operation='create_comment')):
            self.assertEqual((await self.post(body))[0], 200)
        get, post, sdui, page = [fetch['headers'] for fetch in self.browser.fetches]
        self.assertEqual(get, {'accept': 'application/vnd.linkedin.normalized+json+2.1',
                               'x-restli-protocol-version': '2.0.0', 'x-li-lang': 'es_ES', 'x-li-track': 'pista'})
        self.assertEqual(post, {**get, 'content-type': 'application/json; charset=UTF-8'})
        self.assertEqual(sdui, {'x-li-page-instance': 'instancia', 'accept': '*/*', 'content-type': 'application/json'})
        self.assertEqual(page, {'accept': 'text/html'})
        self.assertEqual(json.loads(self.browser.fetches[1]['body']), rutas.invitation(PROFILE, 'Hola'))
        self.assertEqual(json.loads(self.browser.fetches[2]['body']), rutas.envelope(rutas.reaction(POST, 'LIKE')))


class LogTests(ServiceCase):
    async def test_logs_say_what_and_how_long_but_nothing_linkedin_answered(self):
        self.browser.answers = [raw(200, '{"secreto":"RESPUESTA-PRIVADA"}'), raw(429, 'RESPUESTA-PRIVADA')]
        with self.assertLogs('navegador', 'INFO') as logs:
            await self.post(invitation('NOTA-PRIVADA'))
            await self.post(call(path=rutas.post_page('7123456789012345678'), kind='page', operation='create_comment'))
            await self.post(call())
        text = '\n'.join(logs.output)
        for secret in ('NOTA-PRIVADA', 'RESPUESTA-PRIVADA', '7123456789012345678', PROFILE, TOKEN, 'valor-ficticio'):
            self.assertNotIn(secret, text)
        self.assertIn('op=send_invitation POST voyager /voyager/api/voyagerRelationshipsDashMemberRelationships -> 200',
                      text)
        self.assertIn('/feed/update/{id}/', text)
        self.assertIn('DETENIDA', text)
        self.assertIn('op=account_status -> 409', text)


if __name__ == '__main__':
    unittest.main()
