from datetime import timedelta
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.conf import settings
from team_backend.jobs import LANES
from team_backend.models import Worker

class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--lane', choices=LANES, help='Exige un worker vivo de ese carril (por defecto, cualquiera).')
    def handle(self, **options):
        alive = Worker.objects.filter(stopped_at=None, last_seen__gte=timezone.now()-timedelta(seconds=settings.WORKER_STALE_SECONDS))
        if options.get('lane'): alive = alive.filter(lane=options['lane'])
        if not alive.exists():
            raise CommandError('No hay un worker con latido vigente' + (f' en el carril {options["lane"]}' if options.get('lane') else ''))
