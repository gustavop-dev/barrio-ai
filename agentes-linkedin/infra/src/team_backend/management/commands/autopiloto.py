import logging
import signal
import threading
import time
from pathlib import Path
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections
from team_backend import autopiloto

HEARTBEAT=Path('/tmp/barrio-autopilot-heartbeat')
logger=logging.getLogger('team_backend.autopilot')

class Command(BaseCommand):
    help='Ejecuta el ciclo autónomo del operador (OPERATOR_AUTOPILOT=true). Solo encola trabajo; el worker lo ejecuta.'

    def add_arguments(self,parser):
        parser.add_argument('--once',action='store_true')
        parser.add_argument('--usuario',default='barrio-autopiloto')
        parser.add_argument('--intervalo',type=int,default=60)

    def handle(self,**options):
        user=User.objects.filter(username=options['usuario'],is_active=True).first()
        if not user:raise CommandError('Usuario del piloto automático inexistente: ejecutar bootstrap_local.')
        stopping=threading.Event()
        if threading.current_thread() is threading.main_thread():
            for sig in (signal.SIGTERM,signal.SIGINT):signal.signal(sig,lambda *a:stopping.set())
        while not stopping.is_set():
            close_old_connections()
            HEARTBEAT.write_text(str(time.time()))
            if autopiloto.enabled():
                try:
                    report=autopiloto.tick(user)
                    if any(v for k,v in report.items() if k!='stopped') or report.get('stopped'):
                        logger.info('autopilot_tick %s',' '.join(f'{k}={v}' for k,v in report.items()))
                except Exception:
                    # Never crash-loop into duplicate work; the next tick re-reads state.
                    logger.exception('autopilot_tick_failed')
            if options['once']:break
            stopping.wait(options['intervalo'])
        close_old_connections()
