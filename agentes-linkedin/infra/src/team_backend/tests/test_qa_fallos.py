"""QA failure switch (team_backend.qa_fallos, linkedin_backend.settings_qa): inert under the production settings, and under
the QA settings it answers the armed faults (5xx, 413, timeout, slow, empty) and then spends them."""
import importlib
import json
import os
import shutil
import sys
import tempfile
from unittest.mock import patch
from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ImproperlyConfigured, MiddlewareNotUsed
from django.test import TestCase, override_settings
from team_backend import qa_fallos
from team_backend.models import Notification

MIDDLEWARE = 'team_backend.qa_fallos.QaFaultMiddleware'
ALWAYS_500 = [{'id': 'x', 'ruta': '.*', 'metodo': '*', 'efecto': '500', 'veces': -1, 'segundos': 0}]


class TempRules:
    def use_rules_file(self, rules=None):
        folder = tempfile.mkdtemp(prefix='qa-fallos-')
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        path = os.path.join(folder, 'fallos.json')
        if rules is not None:
            with open(path, 'w') as fh:
                json.dump(rules, fh)
        override = override_settings(QA_FAULTS_FILE=path)
        override.enable()
        self.addCleanup(override.disable)
        return path


class InertInProductionTests(TempRules, TestCase):
    def test_production_settings_have_no_switch(self):
        """Catch the switch leaking into production: no middleware, no QA mode, no control route."""
        self.assertNotIn(MIDDLEWARE, settings.MIDDLEWARE)
        self.assertFalse(getattr(settings, 'QA_MODE', False))
        self.assertEqual(settings.ROOT_URLCONF, 'linkedin_backend.urls')

    def test_armed_rules_and_header_do_nothing(self):
        """Catch a production request being failed on purpose: rules on disk and the header are ignored."""
        self.use_rules_file(ALWAYS_500)
        self.assertEqual(self.client.get('/health', HTTP_X_QA_FALLO='500').status_code, 200)
        self.assertEqual(self.client.post('/api/v1/qa/fallos', '{}', content_type='application/json').status_code, 404)
        self.assertEqual(self.client.get('/api/v1/qa/fallos').status_code, 404)

    def test_middleware_and_control_refuse_without_qa_mode(self):
        """Catch the middleware being listed by mistake: it unloads itself and the control answers 404."""
        with self.assertRaises(MiddlewareNotUsed):
            qa_fallos.QaFaultMiddleware(lambda request: None)
        self.assertFalse(qa_fallos.active())

    def test_qa_settings_refuse_without_qa_mode(self):
        """Catch settings_qa being imported in a deployment without QA_MODE."""
        sys.modules.pop('linkedin_backend.settings_qa', None)
        with patch.dict(os.environ, {'QA_MODE': ''}):
            with self.assertRaises(ImproperlyConfigured):
                importlib.import_module('linkedin_backend.settings_qa')
        sys.modules.pop('linkedin_backend.settings_qa', None)


@override_settings(QA_MODE=True, ROOT_URLCONF='linkedin_backend.urls_qa', MIDDLEWARE=[*settings.MIDDLEWARE, MIDDLEWARE])
class ArmedFaultsTests(TempRules, TestCase):
    def setUp(self):
        self.use_rules_file()

    def arm(self, *rules):
        response = self.client.post('/api/v1/qa/fallos', json.dumps(list(rules)), content_type='application/json')
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()['reglas']

    def test_a_fault_hits_as_many_times_as_asked_then_clears(self):
        """Catch a fault that never ends (it would break every later flow) or never starts."""
        self.arm({'ruta': '^/health$', 'efecto': '503', 'veces': 2})
        self.assertEqual(self.client.get('/health').status_code, 503)
        self.assertEqual(self.client.get('/health').json()['detail'], 'Fallo simulado por QA (503).')
        self.assertEqual(self.client.get('/health').status_code, 200)
        self.arm({'ruta': '^/health$', 'efecto': '413', 'veces': -1, 'metodo': 'GET'})
        self.assertEqual(self.client.get('/health').status_code, 413)
        self.assertEqual(self.client.get('/health').status_code, 413)
        self.assertEqual(len(self.client.get('/api/v1/qa/fallos').json()['reglas']), 1)
        self.assertEqual(self.client.delete('/api/v1/qa/fallos').json()['reglas'], [])
        self.assertEqual(self.client.get('/health').status_code, 200)

    def test_method_route_header_timeout_and_slow(self):
        """Catch rules hitting the wrong requests, and the timeout and slow effects."""
        self.arm({'ruta': '^/health$', 'metodo': 'POST', 'efecto': '500'})
        self.assertEqual(self.client.get('/health').status_code, 200)
        self.assertEqual(self.client.get('/health', HTTP_X_QA_FALLO='429').status_code, 429)
        self.arm({'ruta': '^/health$', 'efecto': 'timeout', 'segundos': 0})
        self.assertEqual(self.client.get('/health').status_code, 504)
        self.arm({'ruta': '^/health$', 'efecto': 'lento', 'segundos': 0})
        self.assertEqual(self.client.get('/health').status_code, 200)

    def test_empty_dataset_keeps_the_shape(self):
        """Catch an empty-state fault that breaks the JSON the app parses."""
        user = User.objects.create_superuser('qa-fallos', password='x')
        self.client.force_login(user)
        Notification.objects.create(kind='piece_published', layer='publicaciones', title='Se publicó')
        full = self.client.get('/api/v1/notificaciones').json()
        self.assertEqual(full['unread'], 1)
        self.arm({'ruta': '^/api/v1/notificaciones$', 'efecto': 'vacio'})
        empty = self.client.get('/api/v1/notificaciones').json()
        self.assertEqual(set(empty), set(full))
        self.assertEqual((empty['items'], empty['upcoming'], empty['unread']), ([], [], 0))

    def test_invalid_rules_are_refused(self):
        """Catch a typo arming nothing silently."""
        for rule in ({'ruta': '^/x$', 'efecto': '418'}, {'efecto': '500'}, {'ruta': '(', 'efecto': '500'}):
            response = self.client.post('/api/v1/qa/fallos', json.dumps(rule), content_type='application/json')
            self.assertEqual(response.status_code, 400, rule)
