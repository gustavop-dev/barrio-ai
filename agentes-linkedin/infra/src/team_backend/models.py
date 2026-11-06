import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone

class ApiCredential(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    name=models.CharField(max_length=120)
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE)
    digest=models.CharField(max_length=64,unique=True,editable=False)
    created_at=models.DateTimeField(default=timezone.now,editable=False)
    expires_at=models.DateTimeField(null=True,blank=True)
    revoked=models.BooleanField(default=False)
    def __str__(self):return self.name

class Worker(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    started_at=models.DateTimeField(default=timezone.now)
    last_seen=models.DateTimeField(default=timezone.now,db_index=True)
    stopped_at=models.DateTimeField(null=True,blank=True)

class Job(models.Model):
    class State(models.TextChoices):
        QUEUED='queued','En cola'
        RUNNING='running','En ejecución'
        COMPLETE='complete','Completado'
        FAILED='failed','Fallido'
        INTERRUPTED='interrupted','Interrumpido; requiere revisión'
        CANCELLED='cancelled','Cancelado'
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    owner=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    request_hash=models.CharField(max_length=64)
    agent=models.CharField(max_length=40)
    task=models.TextField()
    execute=models.BooleanField(default=False)
    mode=models.CharField(max_length=12,default='lexical')
    state=models.CharField(max_length=20,choices=State.choices,default=State.QUEUED,db_index=True)
    worker=models.ForeignKey(Worker,on_delete=models.PROTECT,null=True,blank=True)
    created_at=models.DateTimeField(default=timezone.now)
    started_at=models.DateTimeField(null=True,blank=True)
    finished_at=models.DateTimeField(null=True,blank=True)
    result_status=models.CharField(max_length=30,blank=True)
    error=models.TextField(blank=True)
    class Meta:
        ordering=['-created_at']
        indexes=[models.Index(fields=['state','created_at'],name='job_queue_order')]
        permissions=[('access_knowledge','Consultar biblioteca del equipo'),('run_agents','Preparar ejecuciones de agentes'),
          ('use_paid_providers','Usar proveedores pagados'),('propose_memory','Proponer memoria'),
          ('confirm_memory','Confirmar hechos personales'),('manage_jobs','Administrar trabajos de todo el equipo')]

class AuditEvent(models.Model):
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True)
    action=models.CharField(max_length=80)
    target=models.CharField(max_length=120)
    request_id=models.CharField(max_length=40,blank=True)
    metadata=models.JSONField(default=dict)
    created_at=models.DateTimeField(default=timezone.now,db_index=True)
    class Meta:ordering=['-created_at']

class OriginalJSONField(models.JSONField):
    """Preserve PostgreSQL json, including escaped NUL in original evidence."""
    def db_type(self,connection):return 'json'
    def from_db_value(self,value,expression,connection):
        if isinstance(value,(dict,list)):return value
        return super().from_db_value(value,expression,connection)

class KnowledgeUnit(models.Model):
    id=models.TextField(primary_key=True)
    session=models.IntegerField()
    title=models.TextField()
    original=OriginalJSONField()
    sha256=models.TextField()
    source_path=models.TextField()
    pointer=models.TextField()
    metadata=models.JSONField()
    active=models.BooleanField()
    class Meta:managed=False;db_table='units';ordering=['id']

class SourceEvidence(models.Model):
    key=models.TextField(primary_key=True)
    session=models.IntegerField()
    original=OriginalJSONField()
    class Meta:managed=False;db_table='evidence';ordering=['key']

class KnowledgeRun(models.Model):
    id=models.UUIDField(primary_key=True)
    agent=models.TextField()
    task=models.TextField()
    status=models.TextField()
    payload=models.JSONField()
    created_at=models.DateTimeField()
    class Meta:managed=False;db_table='runs';ordering=['-created_at']

class MemoryEntry(models.Model):
    id=models.UUIDField(primary_key=True)
    namespace=models.TextField()
    key=models.TextField()
    version=models.IntegerField()
    value=models.JSONField()
    status=models.TextField()
    author=models.TextField()
    evidence=models.TextField()
    created_at=models.DateTimeField()
    class Meta:managed=False;db_table='memory';ordering=['-created_at']

class UsageEntry(models.Model):
    id=models.UUIDField(primary_key=True)
    provider=models.TextField()
    purpose=models.TextField()
    reserved_usd=models.DecimalField(max_digits=20,decimal_places=10)
    actual_usd=models.DecimalField(max_digits=20,decimal_places=10,null=True)
    status=models.TextField()
    usage=models.JSONField(null=True)
    request_hash=models.TextField(null=True)
    created_at=models.DateTimeField()
    class Meta:managed=False;db_table='usage_ledger';ordering=['-created_at']
