"""The daily canary of a `directo` account (docs/plan-linkedin-directo.md, «Prueba diaria»).

LinkedIn renames fields without warning and an HTTP 200 with a field gone is a silent break. Once a day the connector's
14 reads (16 calls, inside the navegador service's budgets and stops like any other) are checked against the fields
Barrio's callers use; what to read and what each answer must carry stays with the rest of LinkedIn's knowledge in
linkedin_directo/canario.py, reached through DirectoConnector.canary(). Each run is a CanaryRun; the last KEEP stay.

- daily_due: cheap check for the autopilot (no reads): a directo account with its service configured, not paused,
  past LINKEDIN_CANARY_AFTER (UTC), without a run today that judged LinkedIn. A run that could not run (the service busy,
  unreachable or out of budget) is tried again after RETRY_AFTER, up to TRIES runs a day.
- run: the check_linkedin job. A stop (the service stopped the account or has no session, LinkedIn pushed back) pauses
  the account like any other read, with what the owner has to do in the reason; set_account_pause sends that notice.
- Notices (Notificaciones, kind linkedin_canary): once when the day's result turns broken or not run, and once when it
  is fine again. Days compare by their last run; a run that will be tried again says nothing yet. A run the service
  refused for another internet exit is also told at once, like any call (connectors_directo.egress_notice).
- latest: the last finished run, as GET /api/v1/operador/overview and /api/v1/operador/accounts show it (`canary`)."""
import os
from datetime import datetime, time, timedelta, timezone as dt_timezone
from django.utils import timezone
from . import operador
from .connectors import ConnectorError, get_connector
from .models import CanaryRun, ConnectorAccount

UTC=dt_timezone.utc
KEEP=30  # runs kept per account: about a month, retries included
TRIES=3  # runs a day at most while it cannot run
RETRY_AFTER=timedelta(hours=1)

def setting(name,default):
    return os.environ.get(name,default)

def enabled():
    return setting('LINKEDIN_CANARY_ENABLED','true').strip().lower()=='true'

def after():
    hour,_,minute=setting('LINKEDIN_CANARY_AFTER','12:00').partition(':')
    return time(int(hour),int(minute or 0))

def _midnight(now):
    return datetime.combine(now.astimezone(UTC).date(),time(0),tzinfo=UTC)

def _today(account,now):
    return CanaryRun.objects.filter(account=account,started_at__gte=_midnight(now))

def tries(account,now=None):
    """Runs started this UTC day."""
    return _today(account,now or timezone.now()).count()

def daily_due(account,now=None):
    from .analitica import service_ready
    now=now or timezone.now()
    if account.provider!='directo' or account.paused or not enabled() or not service_ready():return False
    if now.astimezone(UTC).time()<after():return False
    today=list(_today(account,now).values_list('state','started_at'))
    if any(state!=CanaryRun.State.NOT_RUN for state,_ in today) or len(today)>=TRIES:return False  # a running one too
    return not today or max(at for _,at in today)+RETRY_AFTER<=now

def failing(log):
    return [row.get('operacion') for row in log.operations or [] if row.get('estado')!='ok']

def latest(account):
    """The last finished run, or None (no run yet, or not a directo account)."""
    if account.provider!='directo':return None
    log=account.canary_runs.exclude(state=CanaryRun.State.RUNNING).first()
    if log is None:return None
    return {'state':log.state,'started_at':log.started_at,'finished_at':log.finished_at,'calls':log.calls,
            'failing':failing(log),'error_kind':log.error_kind,'error':log.error[:300]}

def _finish(log,state,**fields):
    for key,value in fields.items():setattr(log,key,value)
    log.state=state;log.finished_at=timezone.now()
    log.save()

def run(account,now=None,connector=None):
    """The check_linkedin job: one canary, stored, then what follows from it. Returns the CanaryRun, or None when the
    machine or the account is paused (nothing is read then)."""
    now=now or timezone.now()
    if account.provider!='directo':raise ValueError('La prueba diaria de LinkedIn es solo para una cuenta «directo».')
    if operador.globally_paused() or ConnectorAccount.objects.filter(pk=account.pk,paused=True).exists():return None
    log=CanaryRun.objects.create(account=account,started_at=now)
    try:
        report=(connector or get_connector(account)).canary()
    except ConnectorError as exc:  # the connector could not even be built: its configuration
        report={'resultado':CanaryRun.State.NOT_RUN,'operaciones':[],'llamadas':0,
                'error':{'kind':exc.kind,'pausa':exc.pause,'motivo':str(exc)}}
    except Exception as exc:
        _finish(log,CanaryRun.State.NOT_RUN,error_kind='internal',error=type(exc).__name__)
        raise
    error=report.get('error') or {}
    _finish(log,report['resultado'],operations=report['operaciones'],calls=report['llamadas'],
            error_kind=str(error.get('kind') or '')[:40],error=str(error.get('motivo') or '')[:1000])
    operador._audit(None,'linkedin.canary',account.id,state=log.state,calls=log.calls,failing=failing(log),
                    error_kind=log.error_kind)
    CanaryRun.objects.filter(id__in=list(account.canary_runs.values_list('id',flat=True)[KEEP:])).delete()
    if error.get('kind')=='egress':  # the canary reads through the transport, not the connector: tell it from here too
        from .connectors_directo import egress_notice
        egress_notice(account.external_account_id,error.get('desde'),log.error)
    if error.get('pausa') or log.state==CanaryRun.State.HALTED:
        # Its own notice would repeat the pause's: the reason says what happened and what to do.
        operador.set_account_pause(account,f'La prueba diaria de LinkedIn se detuvo: {log.error or "el servicio paró la cuenta."}')
    else:
        _notify(account,log,now)
    return log

def _notify(account,log,now):
    from .notificaciones import avisar
    today=tries(account,now)
    if log.state==CanaryRun.State.NOT_RUN and today<TRIES:return  # it will be tried again: nothing to say yet
    before=CanaryRun.objects.filter(account=account,started_at__lt=_midnight(now)).exclude(state=CanaryRun.State.RUNNING).first()
    previous=before.state if before else CanaryRun.State.OK
    if log.state==previous:return  # once per change
    ref=f'linkedin_canary:{log.id}'
    if log.state==CanaryRun.State.BROKEN:
        avisar('linkedin_canary','La prueba diaria de LinkedIn encontró lecturas rotas',
               f'{account.label}: {", ".join(failing(log))}. LinkedIn cambió algo; lo que dependa de esas lecturas puede '
               'fallar o quedarse sin datos hasta que se ajuste el conector directo.',ref=ref)
    elif log.state==CanaryRun.State.NOT_RUN:
        avisar('linkedin_canary','La prueba diaria de LinkedIn no pudo correr hoy',
               f'{account.label}: {log.error or "sin detalle"} Se intentó {today} veces; mañana vuelve a intentarlo.',ref=ref)
    elif log.state==CanaryRun.State.OK:
        avisar('linkedin_canary','La prueba diaria de LinkedIn vuelve a pasar',
               f'{account.label}: las {len(log.operations)} lecturas traen sus campos otra vez.',ref=ref)
