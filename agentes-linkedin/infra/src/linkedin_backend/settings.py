import os
from pathlib import Path
from psycopg.conninfo import conninfo_to_dict
from knowledge.config import INFRA,dsn

BASE_DIR=INFRA
SECRET_KEY=os.environ['DJANGO_SECRET_KEY']
DEBUG=False
ALLOWED_HOSTS=os.environ.get('DJANGO_ALLOWED_HOSTS','localhost,127.0.0.1,[::1]').split(',')
INSTALLED_APPS=['django.contrib.admin','django.contrib.auth','django.contrib.contenttypes',
 'django.contrib.sessions','django.contrib.messages','django.contrib.staticfiles','rest_framework','team_backend']
MIDDLEWARE=['django.middleware.security.SecurityMiddleware','whitenoise.middleware.WhiteNoiseMiddleware',
 'django.contrib.sessions.middleware.SessionMiddleware','django.middleware.common.CommonMiddleware',
 'django.middleware.csrf.CsrfViewMiddleware','django.contrib.auth.middleware.AuthenticationMiddleware',
 'django.contrib.messages.middleware.MessageMiddleware','django.middleware.clickjacking.XFrameOptionsMiddleware',
 'team_backend.middleware.RequestIdMiddleware']
ROOT_URLCONF='linkedin_backend.urls'
WSGI_APPLICATION='linkedin_backend.wsgi.application'
TEMPLATES=[{'BACKEND':'django.template.backends.django.DjangoTemplates','DIRS':[],'APP_DIRS':True,
 'OPTIONS':{'context_processors':['django.template.context_processors.request','django.contrib.auth.context_processors.auth','django.contrib.messages.context_processors.messages']}}]
connection=conninfo_to_dict(dsn())
DATABASES={'default':{'ENGINE':'django.db.backends.postgresql','NAME':connection['dbname'],
 'USER':connection.get('user',''),'PASSWORD':connection.get('password',''),
 'HOST':connection.get('host',''),'PORT':connection.get('port','5432'),'CONN_MAX_AGE':60,
 'OPTIONS':{'connect_timeout':5},'TEST':{'NAME':os.environ.get('DJANGO_TEST_DATABASE','test_linkedin_knowledge')}}}
AUTH_PASSWORD_VALIDATORS=[{'NAME':'django.contrib.auth.password_validation.MinimumLengthValidator'},
 {'NAME':'django.contrib.auth.password_validation.CommonPasswordValidator'},
 {'NAME':'django.contrib.auth.password_validation.NumericPasswordValidator'}]
LANGUAGE_CODE='es'
TIME_ZONE='America/Bogota'
USE_TZ=True
STATIC_URL='/static/'
STATIC_ROOT=BASE_DIR/'staticfiles'
STORAGES={'default':{'BACKEND':'django.core.files.storage.FileSystemStorage'},
 'staticfiles':{'BACKEND':'whitenoise.storage.CompressedManifestStaticFilesStorage'}}
DEFAULT_AUTO_FIELD='django.db.models.BigAutoField'
# Captures and the Galería (docs/capturas-galeria.md): private files, served only by authenticated views.
# There is deliberately no MEDIA_URL route: nothing under MEDIA_ROOT is ever public.
MEDIA_ROOT=Path(os.environ.get('MEDIA_ROOT') or BASE_DIR/'media')
FILE_UPLOAD_PERMISSIONS=0o640
FILE_UPLOAD_DIRECTORY_PERMISSIONS=0o750
CAPTURE_AUDIO_MAX_BYTES=25*1024*1024
GALLERY_PHOTO_MAX_BYTES=10*1024*1024
GALLERY_MAX_PHOTOS_PER_REQUEST=10
# Phase 1 web research. LIVE_PROVIDERS also gates the free GitHub reader.
WEB_RESEARCH_ENABLED=os.environ.get('WEB_RESEARCH_ENABLED','true').lower()=='true'
WEB_RESEARCH_MODEL=os.environ.get('WEB_RESEARCH_MODEL','claude-sonnet-5-5')
WEB_SEARCH_TOOL_TYPE=os.environ.get('WEB_SEARCH_TOOL_TYPE','web_search_20260209')
WEB_FETCH_TOOL_TYPE=os.environ.get('WEB_FETCH_TOOL_TYPE','web_fetch_20260209')
WEB_SEARCH_MAX_USES=int(os.environ.get('WEB_SEARCH_MAX_USES','2'))
WEB_FETCH_MAX_USES=int(os.environ.get('WEB_FETCH_MAX_USES','2'))
WEB_FETCH_MAX_CONTENT_TOKENS=int(os.environ.get('WEB_FETCH_MAX_CONTENT_TOKENS','4000'))
WEB_RESEARCH_MAX_TOKENS=int(os.environ.get('WEB_RESEARCH_MAX_TOKENS','4000'))
WEB_RESEARCH_DAILY_LIMIT=int(os.environ.get('WEB_RESEARCH_DAILY_LIMIT','6'))
WEB_RESEARCH_DAILY_USD=os.environ.get('WEB_RESEARCH_DAILY_USD','2')
WEB_SEARCH_USD_PER_REQUEST=os.environ.get('WEB_SEARCH_USD_PER_REQUEST','0.01')
# Conservative reservation for search results and repeated tool-turn input; verify pricing on deploy.
WEB_SEARCH_RESERVED_TOKENS=int(os.environ.get('WEB_SEARCH_RESERVED_TOKENS','25000'))
WEB_RESEARCH_MAX_URLS=int(os.environ.get('WEB_RESEARCH_MAX_URLS','3'))
WEB_GITHUB_MAX_BYTES=int(os.environ.get('WEB_GITHUB_MAX_BYTES','131072'))
WEB_GITHUB_README_CHARS=int(os.environ.get('WEB_GITHUB_README_CHARS','8000'))
WEB_GITHUB_TIMEOUT_S=float(os.environ.get('WEB_GITHUB_TIMEOUT_S','10'))
SESSION_COOKIE_HTTPONLY=True
SESSION_COOKIE_SAMESITE='Strict'
CSRF_COOKIE_SAMESITE='Strict'
SESSION_COOKIE_SECURE=os.environ.get('DJANGO_HTTPS','false')=='true'
CSRF_COOKIE_SECURE=SESSION_COOKIE_SECURE
SECURE_SSL_REDIRECT=SESSION_COOKIE_SECURE
# Behind the Caddy reverse proxy in production; Django is never exposed directly.
if SESSION_COOKIE_SECURE:SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO','https')
# Container healthchecks call /health over plain HTTP on the internal network.
SECURE_REDIRECT_EXEMPT=[r'^health$']
SECURE_HSTS_SECONDS=31536000 if SESSION_COOKIE_SECURE else 0
# Subdomain/preload HSTS commits every subdomain of the owner's domain: opt-in only.
SECURE_HSTS_INCLUDE_SUBDOMAINS=SESSION_COOKIE_SECURE and os.environ.get('DJANGO_HSTS_SUBDOMAINS','false')=='true'
SECURE_HSTS_PRELOAD=SECURE_HSTS_INCLUDE_SUBDOMAINS
DATA_UPLOAD_MAX_MEMORY_SIZE=128*1024
CSRF_TRUSTED_ORIGINS=[v for v in os.environ.get('DJANGO_CSRF_TRUSTED_ORIGINS','').split(',') if v]
LOGIN_URL='/admin/login/'
JOB_QUEUE_LIMIT=100
WORKER_STALE_SECONDS=180
REST_FRAMEWORK={
 # Device tokens of the mobile app first: they only claim `Bearer 0ff1ce_dt_…`, so service credentials are never shadowed.
 'DEFAULT_AUTHENTICATION_CLASSES':['team_backend.authentication.DeviceTokenAuthentication','team_backend.authentication.CredentialAuthentication',
                                   'rest_framework.authentication.SessionAuthentication'],
 'DEFAULT_PERMISSION_CLASSES':['team_backend.permissions.KnowledgeAccess'],
 'DEFAULT_RENDERER_CLASSES':['rest_framework.renderers.JSONRenderer'],
 'DEFAULT_PARSER_CLASSES':['rest_framework.parsers.JSONParser'],
 'DEFAULT_PAGINATION_CLASS':'team_backend.pagination.BoundedPagination','PAGE_SIZE':25,
 'DEFAULT_THROTTLE_CLASSES':['rest_framework.throttling.UserRateThrottle'],
 'DEFAULT_THROTTLE_RATES':{'user':'120/min'},
 'EXCEPTION_HANDLER':'team_backend.exceptions.handle_exception'}
LOGGING={'version':1,'disable_existing_loggers':False,
 'handlers':{'console':{'class':'logging.StreamHandler'}},
 'loggers':{'team_backend':{'handlers':['console'],'level':'INFO'}}}
