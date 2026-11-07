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
        # Official API (Share on LinkedIn): own publications only; external_account_id is the member URN.
        LINKEDIN='linkedin','API oficial de LinkedIn'
        LINKEDIN_FAKE='linkedin_fake','API oficial simulada (pruebas)'
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
    # DESC-05: when its commenters were last read to discover people (each post is scanned once).
    commenters_scanned_at=models.DateTimeField(null=True,blank=True)
    class Meta:
        ordering=['-posted_at','-observed_at']
        constraints=[models.UniqueConstraint(fields=['account','provider_post_id'],name='unique_observed_post')]
    def __str__(self):return f'{self.author_name}: {self.text[:60]}'

class Contact(models.Model):
    """A person of Gustavo's neighborhood (RED-09 relationship memory): discovered, classified and moved
    through follow -> invitation without note -> connection. Only the operator writes to LinkedIn."""
    class Stage(models.TextChoices):
        CANDIDATE='candidate','Descubierto; pendiente de clasificar'
        FIT='fit','Encaja; pendiente de seguir'
        DISCARDED='discarded','Descartado'
        FOLLOWED='followed','Seguido; calentando antes de invitar'
        INVITED='invited','Invitación enviada'
        CONNECTED='connected','Conectado'
        CLOSED='closed','Invitación ignorada o retirada; no se reinvita'
        INCOMING='incoming','Invitación recibida pendiente'
    class Source(models.TextChoices):
        COMMENTER='commenter','Comentó en un post de un referente'
        SEARCH='search','Búsqueda'
        INCOMING='incoming','Invitación recibida'
        MANUAL='manual','Añadido a mano'
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    account=models.ForeignKey(ConnectorAccount,on_delete=models.PROTECT,related_name='contacts')
    provider_user_id=models.CharField(max_length=200)
    public_identifier=models.CharField(max_length=100,blank=True)
    display_name=models.CharField(max_length=200,blank=True)
    headline=models.TextField(blank=True)
    profile_url=models.TextField(blank=True)
    location=models.CharField(max_length=200,blank=True)
    source=models.CharField(max_length=20,choices=Source.choices)
    evidence=models.JSONField(default=dict,blank=True)
    network_distance=models.CharField(max_length=20,blank=True)
    is_following=models.BooleanField(default=False)
    # Provider id of the pending invitation (sent by us or received), used to accept or to track it.
    invitation_id=models.CharField(max_length=200,blank=True)
    classification=models.JSONField(default=dict,blank=True)
    stage=models.CharField(max_length=20,choices=Stage.choices,default=Stage.CANDIDATE,db_index=True)
    history=models.JSONField(default=list,blank=True)
    profile_checked_at=models.DateTimeField(null=True,blank=True)
    followed_at=models.DateTimeField(null=True,blank=True)
    invited_at=models.DateTimeField(null=True,blank=True)
    connected_at=models.DateTimeField(null=True,blank=True)
    discovered_at=models.DateTimeField(default=timezone.now)
    updated_at=models.DateTimeField(default=timezone.now)
    class Meta:
        ordering=['-updated_at']
        constraints=[models.UniqueConstraint(fields=['account','provider_user_id'],name='unique_contact_per_account')]
    def __str__(self):return self.display_name or self.provider_user_id

OPEN_ACTION_STATES=['proposed','approved','executing','sent','uncertain']
OPEN_PIECE_STATES=['preparing','ready']

class EditorialPiece(models.Model):
    """CONT-01..07: one own publication prepared by the editorial circuit for a local calendar day.
    Its CONT-09 ActionProposal carries the exact text through policy approval and execution."""
    class State(models.TextChoices):
        PREPARING='preparing','Preparándose'
        SKIPPED='skipped','Día sin pieza por decisión editorial'
        BLOCKED='blocked','Bloqueada por la verificación'
        FAILED='failed','Preparación fallida'
        READY='ready','Lista; publicación propuesta'
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    account=models.ForeignKey(ConnectorAccount,on_delete=models.PROTECT,related_name='pieces')
    slot_date=models.DateField(db_index=True)
    scheduled_for=models.DateTimeField()
    state=models.CharField(max_length=20,choices=State.choices,default=State.PREPARING,db_index=True)
    stage=models.CharField(max_length=20,blank=True)
    brief=models.JSONField(default=dict,blank=True)
    variants=models.JSONField(default=dict,blank=True)
    panel=models.JSONField(default=dict,blank=True)
    selection=models.JSONField(default=dict,blank=True)
    verification=models.JSONField(default=dict,blank=True)
    final_text=models.TextField(blank=True)
    citations=models.JSONField(default=list,blank=True)
    signals=models.JSONField(default=list,blank=True)
    usage=models.JSONField(default=list,blank=True)
    # APRE-01, first metric: impressions read through Unipile when the publication is reconciled (null ≠ 0).
    metrics=models.JSONField(default=dict,blank=True)
    note=models.TextField(blank=True)
    origin_job=models.CharField(max_length=40,blank=True)
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,related_name='+')
    created_at=models.DateTimeField(default=timezone.now)
    updated_at=models.DateTimeField(auto_now=True)
    class Meta:
        ordering=['-slot_date','-created_at']
        constraints=[models.UniqueConstraint(fields=['slot_date'],condition=models.Q(state__in=OPEN_PIECE_STATES),
                                             name='one_open_piece_per_day')]
    def __str__(self):return f'{self.slot_date} · {self.get_state_display()}'

class PostMetric(models.Model):
    """APRE-01: cumulative counters of an own published post at a fixed age, read through Unipile (metricas.py).
    Each age is captured once, late if need be (captured_at - published_at tells how late). Null means no data
    (hidden by LinkedIn, absent or unread), never zero."""
    class Kind(models.TextChoices):
        H24='24h','24 horas'
        H72='72h','72 horas'
        D7='7d','7 días'
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    piece=models.ForeignKey(EditorialPiece,on_delete=models.CASCADE,related_name='post_metrics')
    provider_post_id=models.CharField(max_length=200,blank=True)  # opaque Unipile id, not the official URN
    share_url=models.TextField(blank=True)
    kind=models.CharField(max_length=4,choices=Kind.choices)
    impressions=models.IntegerField(null=True,blank=True)
    reactions=models.IntegerField(null=True,blank=True)
    comments=models.IntegerField(null=True,blank=True)
    reposts=models.IntegerField(null=True,blank=True)
    # Who commented, read once per capture: [{provider_user_id, name, substantive, role, fit}]; null = not read.
    commenters=models.JSONField(null=True,blank=True)
    published_at=models.DateTimeField(null=True,blank=True)
    captured_at=models.DateTimeField(default=timezone.now)
    class Meta:
        ordering=['piece','captured_at']
        constraints=[models.UniqueConstraint(fields=['piece','kind'],name='one_post_metric_per_age')]
    def __str__(self):return f'{self.piece_id} · {self.kind}'

class AudienceSnapshot(models.Model):
    """APRE-01: Gustavo's own audience once per local day (OPERATOR_TIMEZONE), read through Unipile.
    Cumulative counters: net growth is the difference between two snapshots. Null means no data, never zero."""
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    day=models.DateField(unique=True)
    followers=models.IntegerField(null=True,blank=True)
    connections=models.IntegerField(null=True,blank=True)
    # LinkedIn reports profile views over a trailing window (List Profile Views, date_range in days).
    profile_views=models.IntegerField(null=True,blank=True)
    profile_views_days=models.PositiveSmallIntegerField(null=True,blank=True)
    captured_at=models.DateTimeField(default=timezone.now)
    class Meta:ordering=['-day']
    def __str__(self):return str(self.day)

class ActionProposal(models.Model):
    class Capability(models.TextChoices):
        COMMENT='INT-03','Comentar en una publicación ajena'
        REACT='INT-02','Reaccionar a una publicación'
        PUBLISH='CONT-09','Publicar una pieza propia'
        FOLLOW='RED-01','Seguir a una persona'
        INVITE='RED-02','Invitar a conectar sin nota'
        ACCEPT='RED-04','Aceptar una invitación recibida'
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
    # Target: someone else's post (INT-*) or an own editorial piece (CONT-09, post is null).
    post=models.ForeignKey(ObservedPost,on_delete=models.PROTECT,related_name='proposals',null=True,blank=True)
    piece=models.ForeignKey(EditorialPiece,on_delete=models.PROTECT,related_name='proposals',null=True,blank=True)
    # Network actions (RED-*) target a person instead of a post or a piece.
    contact=models.ForeignKey(Contact,on_delete=models.PROTECT,related_name='proposals',null=True,blank=True)
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
        # One executor per action: a single open proposal per target (post, piece or contact) and capability.
        constraints=[models.UniqueConstraint(fields=['post','capability'],condition=models.Q(state__in=OPEN_ACTION_STATES),
                                             name='one_open_action_per_target'),
                     models.UniqueConstraint(fields=['piece','capability'],condition=models.Q(state__in=OPEN_ACTION_STATES),
                                             name='one_open_action_per_piece'),
                     models.UniqueConstraint(fields=['contact','capability'],condition=models.Q(state__in=OPEN_ACTION_STATES),
                                             name='one_open_action_per_contact'),
                     models.CheckConstraint(condition=models.Q(post__isnull=False)|models.Q(piece__isnull=False)|models.Q(contact__isnull=False),
                                            name='action_has_target')]
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

class LinkedInCredential(models.Model):
    """OAuth token of the official API for one member, encrypted at rest (Fernet, FIELD_ENCRYPTION_KEY).
    Share on LinkedIn tokens last about 60 days and are not refreshed programmatically."""
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    account=models.OneToOneField(ConnectorAccount,on_delete=models.PROTECT,related_name='linkedin_credential')
    member_urn=models.CharField(max_length=120,unique=True)
    member_name=models.CharField(max_length=200,blank=True)
    scopes=models.CharField(max_length=300,blank=True)
    token_encrypted=models.TextField(editable=False)
    expires_at=models.DateTimeField()
    connected_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,related_name='+')
    connected_at=models.DateTimeField(default=timezone.now)
    expiry_alerted_at=models.DateTimeField(null=True,blank=True)
    def __str__(self):return self.member_urn
