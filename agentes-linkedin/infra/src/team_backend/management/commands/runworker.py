import logging
import signal
import threading
from django.core.management.base import BaseCommand
from django.db import close_old_connections
from django.utils import timezone
from team_backend.jobs import process_one, reconcile_interrupted
from team_backend.models import Worker

HEARTBEAT_SECONDS = 5

def refresh_heartbeat(worker_id):
    Worker.objects.filter(pk=worker_id).update(last_seen=timezone.now())

class Command(BaseCommand):
    help = 'Procesa la cola PostgreSQL sin reintentar automáticamente trabajos interrumpidos.'
    def add_arguments(self, parser):
        parser.add_argument('--once', action='store_true')
    def handle(self, **options):
        stopping = threading.Event()
        heartbeat_stop = threading.Event()
        worker = Worker.objects.create()
        def stop(signum, frame): stopping.set()
        previous = {}
        if threading.current_thread() is threading.main_thread():
            for sig in (signal.SIGTERM, signal.SIGINT):
                previous[sig] = signal.signal(sig, stop)
        def heartbeat():
            try:
                while not heartbeat_stop.wait(HEARTBEAT_SECONDS):
                    close_old_connections()
                    refresh_heartbeat(worker.pk)
            except Exception:
                logging.getLogger('team_backend.worker').error('worker_heartbeat_failed id=%s; stopping after current job',worker.pk)
                stopping.set()
            finally: close_old_connections()
        thread = threading.Thread(target=heartbeat, daemon=True)
        thread.start()
        self.stdout.write('Worker iniciado: ' + str(worker.pk))
        try:
            while not stopping.is_set():
                close_old_connections()
                reconcile_interrupted()
                result = process_one(worker)
                if options['once']: break
                if result is None: stopping.wait(1)
        finally:
            heartbeat_stop.set(); thread.join(timeout=10)
            try:
                Worker.objects.filter(pk=worker.pk).update(last_seen=timezone.now(), stopped_at=timezone.now())
            finally:
                close_old_connections()
            for sig, handler in previous.items(): signal.signal(sig, handler)
