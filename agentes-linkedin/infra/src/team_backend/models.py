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
    # agent_run keeps the original behaviour; other kinds are account-operator steps.
    kind=models.CharField(max_length=30,default='agent_run')
    params=models.JSONField(default=dict,blank=True)
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
          ('confirm_memory','Confirmar hechos personales'),('manage_jobs','Administrar trabajos de todo el equipo'),
          ('operate_linkedin','Leer la cuenta de LinkedIn conectada y preparar acciones'),
          ('approve_actions','Aprobar acciones externas en LinkedIn'),
          ('execute_actions','Ejecutar acciones externas aprobadas')]

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


# ---------------------------------------------------------------------------
# Account operator: the single executor of external LinkedIn actions.
# Proposal -> approval of an exact payload hash -> one execution -> confirmation.

class ConnectorAccount(models.Model):
    class Provider(models.TextChoices):
        UNIPILE='unipile','Unipile v2'
        FAKE='fake','Simulado (pruebas)'
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    provider=models.CharField(max_length=20,choices=Provider.choices)
    external_account_id=models.CharField(max_length=120)
    label=models.CharField(max_length=120)
    status=models.CharField(max_length=20,default='unknown')
    is_locked=models.BooleanField(default=False)
    # Per-account kill switch: no external write runs while paused.
    paused=models.BooleanField(default=False)
    paused_reason=models.TextField(blank=True)
    last_checked_at=models.DateTimeField(null=True,blank=True)
    created_at=models.DateTimeField(default=timezone.now)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['provider','external_account_id'],name='unique_connector_account')]
    def __str__(self):return f'{self.label} ({self.provider})'

class Referent(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    account=models.ForeignKey(ConnectorAccount,on_delete=models.PROTECT,related_name='referents')
    public_identifier=models.CharField(max_length=100)
    provider_user_id=models.CharField(max_length=200,blank=True)
    display_name=models.CharField(max_length=200,blank=True)
    profile_url=models.TextField(blank=True)
    reason=models.TextField(help_text='Por qué conviene observar a esta persona (pertinencia, no popularidad).')
    active=models.BooleanField(default=True)
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True)
    created_at=models.DateTimeField(default=timezone.now)
    last_observed_at=models.DateTimeField(null=True,blank=True)
    class Meta:
        ordering=['display_name']
        constraints=[models.UniqueConstraint(fields=['account','public_identifier'],name='unique_referent_per_account')]
    def __str__(self):return self.display_name or self.public_identifier

class ObservedPost(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    account=models.ForeignKey(ConnectorAccount,on_delete=models.PROTECT,related_name='posts')
    referent=models.ForeignKey(Referent,on_delete=models.SET_NULL,null=True,blank=True,related_name='posts')
    provider_post_id=models.CharField(max_length=200)
    share_url=models.TextField(blank=True)
    author_name=models.CharField(max_length=200,blank=True)
    author_public_identifier=models.CharField(max_length=100,blank=True)
    author_provider_id=models.CharField(max_length=200,blank=True)
    text=models.TextField(blank=True)
    posted_at=models.DateTimeField(null=True,blank=True)
    comments_count=models.IntegerField(null=True,blank=True)
    reactions_count=models.IntegerField(null=True,blank=True)
    is_repost=models.BooleanField(default=False)
    observed_at=models.DateTimeField(default=timezone.now)
    class Meta:
        ordering=['-posted_at','-observed_at']
        constraints=[models.UniqueConstraint(fields=['account','provider_post_id'],name='unique_observed_post')]
    def __str__(self):return f'{self.author_name}: {self.text[:60]}'

OPEN_ACTION_STATES=['proposed','approved','executing','sent','uncertain']

class ActionProposal(models.Model):
    class Capability(models.TextChoices):
        COMMENT='INT-03','Comentar en una publicación ajena'
        REACT='INT-02','Reaccionar a una publicación'
    class State(models.TextChoices):
        PROPOSED='proposed','Propuesta; espera aprobación'
        APPROVED='approved','Aprobada; pendiente de ejecución'
        REJECTED='rejected','Rechazada'
        SUPERSEDED='superseded','Sustituida por otra versión'
        DISCARDED='discarded','Descartada por el agente'
        EXECUTING='executing','Ejecutándose'
        SENT='sent','Enviada; confirmación pendiente'
        CONFIRMED='confirmed','Confirmada en LinkedIn'
        UNCERTAIN='uncertain','Resultado incierto; conciliar sin repetir'
        FAILED='failed','Fallida; no aplicada'
        EXPIRED='expired','Caducada sin ejecutar'
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    account=models.ForeignKey(ConnectorAccount,on_delete=models.PROTECT,related_name='proposals')
    post=models.ForeignKey(ObservedPost,on_delete=models.PROTECT,related_name='proposals')
    capability=models.CharField(max_length=10,choices=Capability.choices)
    payload=models.JSONField()
    payload_hash=models.CharField(max_length=64)
    version=models.PositiveIntegerField(default=1)
    previous=models.ForeignKey('self',on_delete=models.PROTECT,null=True,blank=True,related_name='revisions')
    rationale=models.TextField(blank=True)
    citations=models.JSONField(default=list,blank=True)
    risks=models.JSONField(default=list,blank=True)
    source=models.CharField(max_length=10,default='human')
    origin_job=models.CharField(max_length=40,blank=True)
    model=models.CharField(max_length=40,blank=True)
    state=models.CharField(max_length=20,choices=State.choices,default=State.PROPOSED,db_index=True)
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,related_name='+')
    created_at=models.DateTimeField(default=timezone.now)
    approved_hash=models.CharField(max_length=64,blank=True)
    decided_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,blank=True,related_name='+')
    decided_at=models.DateTimeField(null=True,blank=True)
    decision_note=models.TextField(blank=True)
    class Meta:
        ordering=['-created_at']
        # One executor per action: a single open proposal per post and capability.
        constraints=[models.UniqueConstraint(fields=['post','capability'],condition=models.Q(state__in=OPEN_ACTION_STATES),
                                             name='one_open_action_per_target')]
    def __str__(self):return f'{self.capability} v{self.version} · {self.get_state_display()}'

class ActionExecution(models.Model):
    class State(models.TextChoices):
        EXECUTING='executing','Ejecutándose'
        SENT='sent','Enviada; confirmación pendiente'
        CONFIRMED='confirmed','Confirmada'
        UNCERTAIN='uncertain','Incierta'
        FAILED='failed','Fallida'
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    # OneToOne: an approved proposal can only ever be executed once.
    proposal=models.OneToOneField(ActionProposal,on_delete=models.PROTECT,related_name='execution')
    idempotency_key=models.CharField(max_length=64,unique=True)
    provider=models.CharField(max_length=20)
    state=models.CharField(max_length=20,choices=State.choices,default=State.EXECUTING)
    executed_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    started_at=models.DateTimeField(default=timezone.now)
    finished_at=models.DateTimeField(null=True,blank=True)
    external_id=models.CharField(max_length=200,blank=True)
    external_url=models.TextField(blank=True)
    error_kind=models.CharField(max_length=80,blank=True)
    http_status=models.IntegerField(null=True,blank=True)
    note=models.TextField(blank=True)
    reconciled_at=models.DateTimeField(null=True,blank=True)
    class Meta:ordering=['-started_at']


class OperatorControl(models.Model):
    """Singleton total stop of the autonomous machine, switched by a human from the office."""
    id=models.PositiveSmallIntegerField(primary_key=True,default=1,editable=False)
    paused=models.BooleanField(default=False)
    reason=models.TextField(blank=True)
    updated_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,blank=True)
    updated_at=models.DateTimeField(null=True,blank=True)
    @classmethod
    def current(cls):
        return cls.objects.get_or_create(pk=1)[0]

class PushSubscription(models.Model):
    """Web Push endpoint of an installed office PWA (VAPID)."""
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name='push_subscriptions')
    endpoint=models.CharField(max_length=1000,unique=True)
    p256dh=models.CharField(max_length=200)
    auth=models.CharField(max_length=100)
    user_agent=models.CharField(max_length=300,blank=True)
    created_at=models.DateTimeField(default=timezone.now)
    last_success_at=models.DateTimeField(null=True,blank=True)
    failures=models.PositiveIntegerField(default=0)
