"""Settings of the mobile app's UI QA (.github/workflows/qa-movil.yml): production settings plus the QA failure switch
(team_backend.qa_fallos). Production never uses this module; it refuses to load without QA_MODE=true."""
import os
from django.core.exceptions import ImproperlyConfigured
from .settings import *  # noqa: F401,F403
from .settings import MIDDLEWARE

if os.environ.get('QA_MODE', '').strip().lower() != 'true':
    raise ImproperlyConfigured('linkedin_backend.settings_qa solo se usa en la QA de CI (QA_MODE=true).')

QA_MODE = True
QA_FAULTS_FILE = os.environ.get('QA_FAULTS_FILE', '/tmp/qa-fallos.json')
MIDDLEWARE = [*MIDDLEWARE, 'team_backend.qa_fallos.QaFaultMiddleware']
ROOT_URLCONF = 'linkedin_backend.urls_qa'

# Explicit human identity for synthetic monthly referent decisions; never used in production.
REFERENTS_GUSTAVO_USERNAME = 'qa'
