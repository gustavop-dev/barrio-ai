"""OpenAI answers a Claude call that Anthropic refused for its account or availability (providers.claude → openai_text).
No network: the Anthropic SDK is faked and httpx.post is patched."""
import json
import os
import uuid
from copy import deepcopy
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import anthropic
import httpx
import httpx2
from django.contrib.auth import get_user_model
from django.test import TransactionTestCase

from knowledge import providers
from team_backend import orquestacion as runtime
from team_backend.grafo import load_graph
from team_backend.models import Job, UsageEntry
from team_backend.tests.fakes import FakeAnthropic, message, status_error
from team_backend.tests.test_orquestacion import REQUEST, RESULT

ENV = {'LIVE_PROVIDERS': 'true', 'ANTHROPIC_API_KEY': 'test-only', 'OPENAI_API_KEY': 'test-only',
       'ANTHROPIC_MODEL': 'claude-opus-5-5', 'ANTHROPIC_LIMIT_USD': '', 'OPENAI_LIMIT_USD': '', 'LLM_FALLBACK': 'openai'}
SCHEMA = {'type': 'object', 'additionalProperties': False, 'required': ['decision', 'items'],
          'properties': {'decision': {'type': 'string', 'enum': ['si', 'no']}, 'note': {'type': 'string'},
                         'items': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': False,
                                   'required': ['id'], 'properties': {'id': {'type': 'string'},
                                                                      'why': {'type': 'string', 'default': ''}}}}}}


def anthropic_error(status, kind, text):
    request = httpx2.Request('POST', 'https://api.anthropic.com/v1/messages')
    return anthropic.APIStatusError('simulated', response=httpx2.Response(status, request=request),
                                    body={'type': 'error', 'error': {'type': kind, 'message': text}})


CREDIT = lambda: anthropic_error(400, 'invalid_request_error', 'Your credit balance is too low to access the Anthropic API.')


def response(text, input_tokens=120, cached=20, output_tokens=30, status='completed', incomplete=None, parts=None):
    return {'id': 'resp_test', 'status': status, 'incomplete_details': incomplete,
            'output': [{'type': 'reasoning', 'summary': []},
                       {'type': 'message', 'content': parts or [{'type': 'output_text', 'text': text}]}],
            'usage': {'input_tokens': input_tokens, 'input_tokens_details': {'cached_tokens': cached},
                      'output_tokens': output_tokens}}


class CountFails(FakeAnthropic):
    def __init__(self, error):
        super().__init__()
        def count_tokens(**params):raise error
        self.messages.count_tokens = count_tokens


class FallbackTests(TransactionTestCase):
    def setUp(self):
        UsageEntry.objects.all().delete()
        env = patch.dict(os.environ, ENV);env.start();self.addCleanup(env.stop)

    def call(self, claude, openai=None, **kwargs):
        sent = []
        def post(url, **request):
            sent.append((url, request['json'], request['headers']))
            return httpx.Response(200, json=openai if openai is not None else response('{"decision":"si","items":[]}'))
        with patch('knowledge.providers.anthropic_client', return_value=claude), patch('knowledge.providers.post', side_effect=post):
            result = providers.claude('Instrucciones', kwargs.pop('message', 'Tarea'), purpose='prueba', **kwargs)
        return result, sent

    def rows(self):
        return {(r.provider, r.status): r for r in UsageEntry.objects.all()}

    def test_a_claude_credit_error_is_answered_by_openai_in_the_same_budget_and_ledger(self):
        result, sent = self.call(FakeAnthropic(outcome=CREDIT()), output_schema=SCHEMA, effort='medium', context='Unidades',
                                 openai=response('{"decision":"si","note":null,"items":[{"id":"a","why":null}]}'))
        self.assertEqual((result['provider'], result['model'], result['fallback_from'], result['fallback_reason']),
                         ('openai', 'gpt-5.5', 'claude-opus-5-5', 'cuenta'))
        self.assertEqual(json.loads(result['text']), {'decision': 'si', 'items': [{'id': 'a'}]})  # nulls of optionals dropped
        (url, payload, headers), = sent
        self.assertEqual((url, payload['model'], payload['store'], payload['reasoning']),
                         (providers.OPENAI_RESPONSES_URL, 'gpt-5.5', False, {'effort': 'low'}))
        self.assertEqual(payload['instructions'], 'Instrucciones\n\nUnidades')
        self.assertEqual(payload['input'], [{'role': 'user', 'content': [{'type': 'input_text', 'text': 'Tarea'}]}])
        fmt = payload['text']['format']
        self.assertTrue(fmt['strict'])
        self.assertEqual(fmt['schema']['required'], ['decision', 'note', 'items'])
        self.assertEqual(fmt['schema']['properties']['note']['type'], ['string', 'null'])
        self.assertEqual(fmt['schema']['properties']['items']['items']['properties']['why'], {'type': ['string', 'null']})
        rows = self.rows()
        self.assertEqual(set(rows), {('anthropic', 'rejected'), ('openai', 'complete')})
        self.assertEqual(rows[('anthropic', 'rejected')].usage['fallback'], 'openai')
        openai = rows[('openai', 'complete')]
        self.assertEqual(openai.purpose, 'prueba')
        self.assertEqual(openai.actual_usd, (Decimal(100) * 5 + Decimal(20) * Decimal('0.5') + Decimal(30) * 30) / 1000000)
        self.assertEqual((openai.usage['fallback_from'], openai.usage['cache_read_input_tokens']), ('claude-opus-5-5', 20))
        self.assertGreaterEqual(openai.reserved_usd, openai.actual_usd)

    def test_each_claude_tier_falls_back_to_the_openai_model_of_its_tier_and_images_travel(self):
        image = {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/png', 'data': 'QUJD'}}
        result, sent = self.call(FakeAnthropic(outcome=status_error(529)), model='claude-haiku-5-5',
                                 message=[{'type': 'text', 'text': 'Contexto'}, image], openai=response('Listo'))
        self.assertEqual((result['model'], result['fallback_reason'], result['text']), ('gpt-5.4-mini', 'disponibilidad', 'Listo'))
        self.assertEqual(sent[0][1]['input'][0]['content'],
                         [{'type': 'input_text', 'text': 'Contexto'}, {'type': 'input_image', 'image_url': 'data:image/png;base64,QUJD'}])
        self.assertEqual(self.rows()[('anthropic', 'uncertain')].usage.get('fallback'), None)  # a 5xx may have been processed

    def test_an_expired_key_goes_to_openai_without_reserving_claude(self):
        result, _ = self.call(CountFails(anthropic_error(401, 'authentication_error', 'invalid x-api-key')), openai=response('Hola'))
        self.assertEqual((result['provider'], result['text']), ('openai', 'Hola'))
        self.assertEqual(set(self.rows()), {('openai', 'complete')})

    def test_a_request_error_is_not_hidden_by_the_fallback(self):
        with self.assertRaisesRegex(ValueError, 'anthropic: HTTP 400'):
            self.call(FakeAnthropic(outcome=anthropic_error(400, 'invalid_request_error', 'messages: field required')))
        self.assertEqual(set(self.rows()), {('anthropic', 'rejected')})

    def test_evaluations_disabled_fallback_and_a_missing_openai_key_keep_the_claude_error(self):
        with self.assertRaisesRegex(ValueError, 'anthropic: HTTP 400'):
            self.call(FakeAnthropic(outcome=CREDIT()), fallback=False)
        with patch.dict(os.environ, {'LLM_FALLBACK': 'off'}), self.assertRaisesRegex(ValueError, 'anthropic: HTTP 400'):
            self.call(FakeAnthropic(outcome=CREDIT()))
        with patch.dict(os.environ, {'OPENAI_API_KEY': ''}), self.assertRaisesRegex(ValueError, 'anthropic: HTTP 400'):
            self.call(FakeAnthropic(outcome=CREDIT()))
        self.assertFalse(UsageEntry.objects.filter(provider='openai').exists())

    def test_claude_answers_when_it_can(self):
        result, sent = self.call(FakeAnthropic(outcome=message('Claude')))
        self.assertEqual((result['text'], result['model'], sent), ('Claude', 'claude-opus-5-5', []))

    def test_an_incomplete_or_refused_openai_answer_is_settled_and_reported(self):
        with self.assertRaisesRegex(ValueError, 'OpenAI agotó max_tokens'):
            self.call(FakeAnthropic(outcome=CREDIT()), output_schema=SCHEMA,
                      openai=response('{"deci', status='incomplete', incomplete={'reason': 'max_output_tokens'}))
        with self.assertRaisesRegex(ValueError, 'OpenAI declinó'):
            self.call(FakeAnthropic(outcome=CREDIT()), openai=response('', parts=[{'type': 'refusal', 'refusal': 'No'}]))
        self.assertEqual(UsageEntry.objects.filter(provider='openai', status='complete').count(), 2)

    def test_a_free_form_schema_goes_non_strict(self):
        loose = {'type': 'object', 'properties': {'data': {'type': 'object'}}, 'required': ['data'], 'additionalProperties': False}
        self.assertEqual(providers.openai_schema(loose), (loose, False))
        self.assertTrue(providers.openai_schema(SCHEMA)[1])


class CycleFallbackTests(TransactionTestCase):
    """Inside a cycle, OpenAI may serve a purpose declared for anthropic, and the refused Claude call is not counted."""

    def setUp(self):
        self.user = get_user_model().objects.create_user('fallback-owner')
        self.job = Job.objects.create(owner=self.user, kind='prepare_piece', agent='operador', task='synthetic')
        self.graph = load_graph()
        loader = patch('team_backend.orquestacion.load_graph', side_effect=lambda: deepcopy(self.graph))
        loader.start();self.addCleanup(loader.stop)
        notice = patch('team_backend.notificaciones.avisar');notice.start();self.addCleanup(notice.stop)
        UsageEntry.objects.all().delete()

    def test_openai_serves_a_claude_purpose_and_the_fallback_counts_once(self):
        next(c for c in self.graph['cycles'] if c['id'] == 'pieza_diaria')['limits']['max_provider_calls'] = 1
        run = runtime.Runtime.open('pieza_diaria', str(uuid.uuid4()), self.user, self.job, facts={}, plan=['selection'])
        def both():
            refused = providers.reserve('anthropic', 'editorial-seleccion', Decimal('.01'))
            providers.settle(refused, 'rejected', {'http_status': 400, 'fallback': 'openai'})
            providers.reserve('openai', 'editorial-seleccion', Decimal('.01'))
            return RESULT
        with run.session():
            self.assertEqual(run.call('seleccionar', REQUEST, both), RESULT)
        self.assertEqual(UsageEntry.objects.filter(usage__cycle_id=str(run.id)).count(), 2)
        run = runtime.Runtime.open('pieza_diaria', str(uuid.uuid4()), self.user, self.job, facts={}, plan=['selection'])
        with run.session(), self.assertRaises(runtime.UndeclaredCall):
            run.call('seleccionar', REQUEST, lambda: providers.reserve('openai', 'image-edit', Decimal('.01')))
