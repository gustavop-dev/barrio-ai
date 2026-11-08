"""QA world for the mobile app's UI tests (.github/workflows/qa-movil.yml). Placeholder: user only."""
import os
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction

QA_USERNAME='qa'
QA_PASSWORD_DEFAULT='qa-0ff1ce-solo-ci'

class Command(BaseCommand):
    help='Crea el mundo de QA de la app móvil (solo CI).'
    @transaction.atomic
    def handle(self,**options):
        user,_=User.objects.get_or_create(username=QA_USERNAME)
        user.is_superuser=True;user.is_staff=True;user.is_active=True
        user.set_password(os.environ.get('QA_PASSWORD') or QA_PASSWORD_DEFAULT);user.save()
        self.stdout.write('Mundo de QA listo.')
