import hashlib
import json
import logging
import uuid
from datetime import timedelta
from django.conf import settings
from django.db import transaction,connection
from django.utils import timezone
from rest_framework.exceptions import NotFound
from knowledge import agents
from .exceptions import Conflict
from .models import Job,Worker,AuditEvent,KnowledgeRun
from .permissions import require

logger=logging.getLogger('team_backend.worker')

def audit(actor,action,target,request_id='',connection=None,**metadata):
    if connection is not None:
        from psycopg.types.json import Jsonb
        connection.execute('''INSERT INTO team_backend_auditevent
            (actor_id,action,target,request_id,metadata,created_at) VALUES(%s,%s,%s,%s,%s,%s)''',
            (actor.pk if actor else None,action,str(target),request_id,Jsonb(metadata),timezone.now()))
    else:
        AuditEvent.objects.create(actor=actor,action=action,target=str(target),request_id=request_id,metadata=metadata)

def visible_jobs(user):
    qs=Job.objects.all()
    return qs if user.has_perm('team_backend.manage_jobs') else qs.filter(owner=user)

def enqueue(user,data,request_id=''):
    require(user,'run_agents')
    if data.get('execute') or data.get('mode')=='hybrid':require(user,'use_paid_providers')
    attrs={k:data[k] for k in ['agent','task','execute','mode']}
    fingerprint=hashlib.sha256(json.dumps(attrs,sort_keys=True).encode()).hexdigest()
    jid=data.get('request_id') or uuid.uuid4()
    with transaction.atomic():
        with connection.cursor() as c:c.execute('SELECT pg_advisory_xact_lock(103506)')
        old=Job.objects.filter(id=jid).first()
        if old:
            if old.owner_id!=user.pk:raise NotFound()
            if old.request_hash!=fingerprint:raise Conflict('request_id ya corresponde a otra tarea')
            return old,False
        if KnowledgeRun.objects.filter(id=jid).exists():raise Conflict('Identificador ya utilizado por una ejecución histórica')
        if Job.objects.filter(state=Job.State.QUEUED).count()>=settings.JOB_QUEUE_LIMIT:raise Conflict('La cola está llena; espera a que terminen trabajos')
        job=Job.objects.create(id=jid,owner=user,request_hash=fingerprint,**attrs)
        audit(user,'job.enqueued',job.id,request_id,execute=job.execute,mode=job.mode)
        return job,True

OPERATION_PERMISSIONS={
    'observe':['operate_linkedin'],
    'propose_comment':['operate_linkedin','run_agents','use_paid_providers'],
    'execute_action':['execute_actions'],
    'reconcile_action':['operate_linkedin'],
    'prepare_piece':['operate_linkedin','run_agents','use_paid_providers'],
    'discover_network':['operate_linkedin'],
    'classify_contacts':['operate_linkedin','run_agents','use_paid_providers'],
    'plan_network':['operate_linkedin'],
    'sync_network':['operate_linkedin'],
    'collect_metrics':['operate_linkedin'],
    'process_capture':['operate_linkedin','run_agents','use_paid_providers'],
    'read_inbox':['operate_linkedin','run_agents','use_paid_providers'],
}
PAID_OPERATIONS=('propose_comment','prepare_piece','classify_contacts','process_capture','read_inbox')

def enqueue_operation(user,kind,params,request_id=None,audit_request_id=''):
    """Queue an account-operator step with the same idempotency rules as agent runs."""
    if kind not in OPERATION_PERMISSIONS:raise ValueError('Operación desconocida')
    for codename in OPERATION_PERMISSIONS[kind]:require(user,codename)
    params=json.loads(json.dumps(params,default=str))
    fingerprint=hashlib.sha256(json.dumps({'kind':kind,'params':params},sort_keys=True).encode()).hexdigest()
    jid=request_id or uuid.uuid4()
    with transaction.atomic():
        with connection.cursor() as c:c.execute('SELECT pg_advisory_xact_lock(103506)')
        old=Job.objects.filter(id=jid).first()
        if old:
            if old.owner_id!=user.pk:raise NotFound()
            if old.request_hash!=fingerprint:raise Conflict('request_id ya corresponde a otra tarea')
            return old,False
        if Job.objects.filter(state=Job.State.QUEUED).count()>=settings.JOB_QUEUE_LIMIT:raise Conflict('La cola está llena; espera a que terminen trabajos')
        job=Job.objects.create(id=jid,owner=user,request_hash=fingerprint,agent='operador',task=kind,
                               execute=kind in PAID_OPERATIONS,kind=kind,params=params)
        audit(user,'job.enqueued',job.id,audit_request_id,kind=kind)
        return job,True

def cancel(user,jid,request_id=''):
    require(user,'run_agents')
    with transaction.atomic():
        job=visible_jobs(user).select_for_update().filter(id=jid).first()
        if not job:raise NotFound()
        if job.state!=Job.State.QUEUED:raise Conflict('Solo se puede cancelar un trabajo que aún no ha comenzado')
        job.state=Job.State.CANCELLED;job.finished_at=timezone.now();job.save(update_fields=['state','finished_at'])
        audit(user,'job.cancelled',job.id,request_id)
    return job

# Lanes: LinkedIn executions and their reconciliation run on their own worker, so a write never waits behind
# minutes of LLM calls, profile reads or a transcription. 'todas' (one worker for everything) is the default.
ACTION_KINDS=('execute_action','reconcile_action')
LANES=('todas','acciones','general')

def lane_jobs(lane):
    queued=Job.objects.filter(state=Job.State.QUEUED)
    if lane=='acciones':return queued.filter(kind__in=ACTION_KINDS)
    if lane=='general':return queued.exclude(kind__in=ACTION_KINDS)
    if lane=='todas':return queued
    raise ValueError(f'Carril desconocido: {lane}')

def claim(worker):
    with transaction.atomic():
        job=lane_jobs(worker.lane).select_for_update(skip_locked=True).order_by('created_at','id').first()
        if not job:return None
        job.state=Job.State.RUNNING;job.worker=worker;job.started_at=timezone.now()
        job.save(update_fields=['state','worker','started_at'])
        return job

def reconcile_interrupted():
    """Never replay a paid task after losing its worker; preserve its run/ledger."""
    cutoff=timezone.now()-timedelta(seconds=settings.WORKER_STALE_SECONDS)
    with transaction.atomic():
        stale=list(Job.objects.select_for_update(skip_locked=True).filter(state=Job.State.RUNNING,worker__last_seen__lt=cutoff))
        for job in stale:
            job.state=Job.State.INTERRUPTED;job.finished_at=timezone.now()
            job.error='El trabajador perdió su latido. Revisar la ejecución y el ledger antes de crear otro trabajo.'
            job.save(update_fields=['state','finished_at','error'])
            audit(None,'job.interrupted',job.id,worker=str(job.worker_id))
    return len(stale)

def process_one(worker):
    job=claim(worker)
    if not job:return None
    try:
        user=job.owner
        if not user.is_active:raise ValueError('Usuario desactivado antes de ejecutar')
        if job.kind!='agent_run':
            from . import operador
            for codename in OPERATION_PERMISSIONS.get(job.kind,['manage_jobs']):require(user,codename)
            state,result_status,error=operador.run_job(job)
        else:
            require(user,'run_agents')
            if job.execute or job.mode=='hybrid':require(user,'use_paid_providers')
            result=agents.run(job.agent,job.task,execute=job.execute,mode=job.mode,request_id=str(job.id))
            result_status=result['status']
            state=Job.State.COMPLETE if result_status in ['preview','needs_review','validation_failed'] else Job.State.INTERRUPTED
            error='' if state==Job.State.COMPLETE else 'La ejecución ya existe sin resultado terminal; no se repitió.'
    except Exception:
        # Provider errors and user task content are not leaked through public job logs.
        state=Job.State.FAILED;result_status='failed'
        error='No se completó el trabajo. Revisa la ejecución y el ledger; no hubo reintento automático.'
        logger.warning('job_failed id=%s',job.id)
    with transaction.atomic():
        # A reconciled job must never be silently resurrected by a late worker.
        changed=Job.objects.filter(id=job.id,state=Job.State.RUNNING,worker=worker).update(
            state=state,result_status=result_status,error=error,finished_at=timezone.now())
        if changed:audit(job.owner,'job.'+state,job.id,result_status=result_status)
    return job.id
