"""URLs of the QA settings (settings_qa): the production ones plus the failure switch control (team_backend.qa_fallos)."""
from django.urls import path
from team_backend import qa_fallos
from .urls import urlpatterns as production

urlpatterns = [path('api/v1/qa/fallos', qa_fallos.control), *production]
