import hashlib
import os
from django.contrib.auth.models import Group, Permission, User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from team_backend.models import ApiCredential

class Command(BaseCommand):
    help = 'Configura roles locales y adopta el token existente sin guardar el secreto en la base.'
    @transaction.atomic
    def handle(self, **options):
        roles = {
            'lectura': ['access_knowledge'],
            'operacion': ['access_knowledge', 'run_agents', 'use_paid_providers', 'propose_memory'],
            'revision': ['access_knowledge', 'run_agents', 'propose_memory', 'confirm_memory'],
        }
        for name, codes in roles.items():
            group, _ = Group.objects.get_or_create(name=name)
            group.permissions.set(Permission.objects.filter(content_type__app_label='team_backend', codename__in=codes))
        token = os.environ.get('KNOWLEDGE_API_TOKEN')
        if token:
            service, created = User.objects.get_or_create(username='linkedin-service')
            if created:
                service.set_unusable_password(); service.save()
                service.groups.add(Group.objects.get(name='operacion'))
            credential, created = ApiCredential.objects.get_or_create(
                digest=hashlib.sha256(token.encode()).hexdigest(),
                defaults={'user': service, 'name': 'Integración local original'})
            # Never reactivate a credential that an administrator revoked.
        username = os.environ.get('DJANGO_ADMIN_USERNAME')
        password = os.environ.get('DJANGO_ADMIN_PASSWORD')
        if username and password and not User.objects.filter(username=username).exists():
            User.objects.create_superuser(username=username, password=password)
        self.stdout.write('Roles y acceso local configurados; las cuentas existentes no fueron restablecidas.')
