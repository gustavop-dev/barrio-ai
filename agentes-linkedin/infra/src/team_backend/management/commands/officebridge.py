import logging
import signal
import threading
from django.core.management.base import BaseCommand
from team_backend.office_bridge import OfficeBridge

class Command(BaseCommand):
    help='Conecta la oficina privada con Django mediante un enlace saliente autenticado.'
    def add_arguments(self,parser):parser.add_argument('--once',action='store_true')
    def handle(self,**options):
        stop=threading.Event();previous={}
        if threading.current_thread() is threading.main_thread():
            for sig in (signal.SIGINT,signal.SIGTERM):previous[sig]=signal.signal(sig,lambda *_:stop.set())
        bridge=OfficeBridge()
        try:
            while not stop.is_set():
                try:delay=bridge.tick()
                except Exception as exc:
                    logging.getLogger('team_backend.office').warning('office_bridge_unavailable type=%s',type(exc).__name__)
                    if options['once']:raise
                    delay=5
                if options['once']:break
                stop.wait(delay)
        finally:
            bridge.close()
            for sig,handler in previous.items():signal.signal(sig,handler)
