from datetime import timedelta
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.conf import settings
from team_backend.models import Worker

class Command(BaseCommand):
    def handle(self, **options):
        if not Worker.objects.filter(stopped_at=None, last_seen__gte=timezone.now()-timedelta(seconds=settings.WORKER_STALE_SECONDS)).exists():
            raise CommandError('No hay un worker con latido vigente')
