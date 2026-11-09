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
    # Which jobs it takes (jobs.LANES): 'acciones' runs LinkedIn executions, 'general' the rest, 'todas' everything.
    lane=models.CharField(max_length=20,default='todas')
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
    protected=models.BooleanField(default=False)
    position=models.PositiveIntegerField(default=0)
    revision=models.PositiveIntegerField(default=1)
    archived_at=models.DateTimeField(null=True,blank=True)
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True)
    created_at=models.DateTimeField(default=timezone.now)
    last_observed_at=models.DateTimeField(null=True,blank=True)
    class Meta:
        ordering=['display_name']
        constraints=[models.UniqueConstraint(fields=['account','public_identifier'],name='unique_referent_per_account')]
    def __str__(self):return self.display_name or self.public_identifier


class ReferentControl(models.Model):
    """Account row is the common lock for CRUD, monthly decisions and experiments."""
    account=models.OneToOneField(ConnectorAccount,on_delete=models.CASCADE,primary_key=True)
    initialized=models.BooleanField(default=False)
    initial_main=models.JSONField(default=list)
    revision=models.PositiveIntegerField(default=1)
    issue=models.TextField(blank=True)


class ReferentReview(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    account=models.ForeignKey(ConnectorAccount,on_delete=models.PROTECT)
    month=models.DateField()
    state=models.CharField(max_length=24,default='preparing')
    dossier=models.JSONField(default=dict)
    expected_revision=models.PositiveIntegerField(default=1)
    published_at=models.DateTimeField(null=True,blank=True)
    deadline=models.DateTimeField()
    closed_at=models.DateTimeField(null=True,blank=True)
    created_at=models.DateTimeField(default=timezone.now)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['account','month'],name='unique_referent_month')]


class ReferentChange(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    review=models.ForeignKey(ReferentReview,on_delete=models.CASCADE,related_name='changes')
    ordinal=models.PositiveIntegerField()
    version=models.PositiveIntegerField(default=1)
    # One immutable snapshot per version is retained in history before every decision/edit.
    proposal=models.JSONField(default=dict)
    history=models.JSONField(default=list)
    state=models.CharField(max_length=24,default='pending')
    responded_at=models.DateTimeField(null=True,blank=True)
    applied_at=models.DateTimeField(null=True,blank=True)
    conflict=models.TextField(blank=True)
    class Meta:
        ordering=['ordinal']
        constraints=[models.UniqueConstraint(fields=['review','ordinal'],name='unique_referent_change')]


class ReferentNotice(models.Model):
    review=models.ForeignKey(ReferentReview,on_delete=models.CASCADE,related_name='notices')
    event=models.CharField(max_length=24)
    payload=models.JSONField(default=dict)
    created_at=models.DateTimeField(default=timezone.now)
    pushed_at=models.DateTimeField(null=True,blank=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['review','event'],name='unique_referent_notice')]


class ReferentExperiment(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    account=models.ForeignKey(ConnectorAccount,on_delete=models.PROTECT)
    referent=models.ForeignKey(Referent,on_delete=models.PROTECT)
    review=models.ForeignKey(ReferentReview,on_delete=models.SET_NULL,null=True,blank=True)
    version=models.PositiveIntegerField(default=1)
    state=models.CharField(max_length=24,default='proposed')
    plan=models.JSONField(default=dict)
    history=models.JSONField(default=list)
    approved_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,blank=True)
    approved_at=models.DateTimeField(null=True,blank=True)
    starts_at=models.DateTimeField()
    focus_at=models.DateTimeField()
    followup_at=models.DateTimeField()
    ends_at=models.DateTimeField()
    results=models.JSONField(default=dict)
    created_at=models.DateTimeField(default=timezone.now)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['account'],condition=models.Q(state='approved'),name='one_referent_experiment')]

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
    # Gustavo's own notes about the person (Personas): [{id, at, text, by}].
    notes=models.JSONField(default=list,blank=True)
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
    research=models.JSONField(default=list,blank=True)
    variants=models.JSONField(default=dict,blank=True)
    panel=models.JSONField(default=dict,blank=True)
    selection=models.JSONField(default=dict,blank=True)
    verification=models.JSONField(default=dict,blank=True)
    image_kind=models.CharField(max_length=16,blank=True)
    image_reason=models.TextField(blank=True)
    image_spec=models.JSONField(default=dict,blank=True)
    image_review=models.JSONField(default=dict,blank=True)
    image_document=models.FileField(upload_to='piezas/documentos',max_length=200,blank=True)
    image_document_sha256=models.CharField(max_length=64,blank=True)
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
    referent_experiment=models.ForeignKey('ReferentExperiment',on_delete=models.PROTECT,null=True,blank=True)
    referent_experiment_version=models.PositiveIntegerField(null=True,blank=True)
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
    # Agente líder (lider.py): the typed judgments, thresholds and decision that replaced a human approval.
    review=models.JSONField(default=dict,blank=True)
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
    # False when the pre-check found nothing to write (already following, already connected, invitation gone,
    # account not running…): such an execution does not use the daily cap or the spacing between writes.
    wrote=models.BooleanField(default=True)
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


# ---------------------------------------------------------------------------
# Office redesign (oficina/PLAN-REDISENO.md): Gustavo steers from results; agents ask him only what nobody else knows.

class Orientation(models.Model):
    """Singleton: Gustavo's high-level direction for the team (audiences, topics, things to avoid or pause).
    Writers, the classifier and the agente líder read it; it never appears verbatim in public text."""
    id=models.PositiveSmallIntegerField(primary_key=True,default=1,editable=False)
    text=models.TextField(blank=True)
    updated_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,blank=True)
    updated_at=models.DateTimeField(null=True,blank=True)
    @classmethod
    def current(cls):
        return cls.objects.get_or_create(pk=1)[0]

class TeamQuestion(models.Model):
    """«Preguntas del equipo» (Tu turno): what an agent needs to know from Gustavo, delivered complete.
    The answer becomes confirmed user memory; «No quiero compartir esto» closes the key for good."""
    class Kind(models.TextChoices):
        ASK='ask','El equipo necesita un dato'
        CONFIRM='confirm','Confirmar un dato propuesto'
    class State(models.TextChoices):
        OPEN='open','Abierta'
        ANSWERED='answered','Respondida'
        DECLINED='declined','No quiere compartirlo'
        WITHDRAWN='withdrawn','Retirada por el equipo'
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    kind=models.CharField(max_length=10,choices=Kind.choices,default=Kind.ASK)
    agent=models.CharField(max_length=60)
    question=models.TextField()
    purpose=models.TextField(blank=True,help_text='Para qué lo necesita el equipo.')
    memory_key=models.CharField(max_length=120)
    proposed_value=models.JSONField(default=dict,blank=True)
    memory_id=models.UUIDField(null=True,blank=True,help_text='Fila de memoria propuesta que se confirma (kind=confirm).')
    class AnswerType(models.TextChoices):
        TEXT='text','Texto libre'
        YES_NO='yes_no','Sí o no, con detalle opcional'
        CHOICE='choice','Una opción de una lista'
        NUMBER='number','Número'
        DATE='date','Fecha'
    answer_type=models.CharField(max_length=10,choices=AnswerType.choices,default=AnswerType.TEXT)
    options=models.JSONField(default=list,blank=True,help_text='Opciones cuando answer_type=choice.')
    suggested_public=models.BooleanField(default=False)
    origin=models.CharField(max_length=120,blank=True)
    # Useful before this moment (e.g. the piece it was asked for); afterwards it stays useful but not urgent.
    deadline=models.DateTimeField(null=True,blank=True)
    postponed_until=models.DateTimeField(null=True,blank=True)
    memory_version=models.PositiveIntegerField(null=True,blank=True,help_text='Versión confirmada que creó la respuesta.')
    state=models.CharField(max_length=12,choices=State.choices,default=State.OPEN,db_index=True)
    answer=models.TextField(blank=True)
    public_use=models.BooleanField(null=True,blank=True)
    answered_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,blank=True,related_name='+')
    answered_at=models.DateTimeField(null=True,blank=True)
    created_at=models.DateTimeField(default=timezone.now)
    class Meta:
        ordering=['-created_at']
        constraints=[models.UniqueConstraint(fields=['memory_key'],condition=models.Q(state='open'),name='one_open_question_per_key')]
    def __str__(self):return self.question[:80]

class Opportunity(models.Model):
    """A business opportunity (Personas → Oportunidades; Resultados → «¿Genera negocio?»). Gustavo registers and
    moves them by hand for now; the analyst will propose them once the inbox is read."""
    class Stage(models.TextChoices):
        CONVERSATION='conversacion','Conversación'
        NEED='necesidad','Necesidad identificada'
        QUALIFIED='cualificada','Cualificada'
        MEETING='reunion','Reunión'
        PROPOSAL='propuesta','Propuesta'
        AGREEMENT='acuerdo','Acuerdo'
        NO_DEAL='sin_acuerdo','Cerrada sin acuerdo'
    class Modality(models.TextChoices):
        PERSONAL='personal_startups','Startups (personal)'
        PROJECTAPP='projectapp','ProjectApp'
        UNKNOWN='por_clasificar','Por clasificar'
    class Channel(models.TextChoices):
        LINKEDIN='linkedin','LinkedIn'
        EMAIL='email','Email'
        CALL='llamada','Llamada'
        EVENT='evento','Evento'
        OTHER='otro','Otro'
    class Attribution(models.TextChoices):
        CITED='cito_contenido','Citó un post o el perfil'
        SAID='lo_dijo','Lo dijo la persona'
        INFERRED='inferido','Se infiere'
        UNKNOWN='desconocido','Se desconoce'
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    contact=models.ForeignKey(Contact,on_delete=models.SET_NULL,null=True,blank=True,related_name='opportunities')
    # Someone outside the network: name and company instead of a contact.
    person_name=models.CharField(max_length=200,blank=True)
    company=models.CharField(max_length=200,blank=True)
    modality=models.CharField(max_length=20,choices=Modality.choices)
    channel=models.CharField(max_length=20,choices=Channel.choices,default=Channel.LINKEDIN)
    stage=models.CharField(max_length=20,choices=Stage.choices,default=Stage.CONVERSATION,db_index=True)
    attribution=models.CharField(max_length=20,choices=Attribution.choices,default=Attribution.UNKNOWN)
    need=models.TextField(blank=True)
    budget=models.CharField(max_length=200,blank=True)
    dedication=models.CharField(max_length=200,blank=True)
    next_action=models.CharField(max_length=300,blank=True)
    next_action_at=models.DateTimeField(null=True,blank=True)
    notes=models.TextField(blank=True)
    history=models.JSONField(default=list,blank=True)
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,related_name='+')
    created_at=models.DateTimeField(default=timezone.now)
    updated_at=models.DateTimeField(default=timezone.now)
    stage_changed_at=models.DateTimeField(default=timezone.now)
    closed_at=models.DateTimeField(null=True,blank=True)
    class Meta:
        ordering=['-updated_at']
        constraints=[models.CheckConstraint(condition=models.Q(contact__isnull=False)|~models.Q(person_name=''),name='opportunity_has_person')]
    def __str__(self):return self.person_name or str(self.contact or self.id)


# ---------------------------------------------------------------------------
# Captura y Galería (0ff1ce, FUNCIONES-NUEVAS.md): what Gustavo sends the team with one gesture, and his photos.
# Files live under MEDIA_ROOT and are only served through authenticated views (capturas_views.py), never as static.

def _media_name(folder,filename):
    """A random name under a dated folder; the client's filename is never trusted."""
    import os.path
    ext=os.path.splitext(filename or '')[1].lower()[:8]
    now=timezone.now()
    return f'{folder}/{now:%Y/%m}/{uuid.uuid4().hex}{ext}'

def capture_audio_path(instance,filename):return _media_name('capturas/audio',filename)
def gallery_image_path(instance,filename):return _media_name('galeria',filename)

class AIEdit(models.TextChoices):
    NO='no','No editar'
    AUTO='auto','Que decida el equipo'
    YES='si','Editar'

class Capture(models.Model):
    """«Botón de captura»: a voice note, photos and a note that the team transcribes and routes (capturas.py).
    `routed_to` records what processing created so «Deshacer» can revert it."""
    class Purpose(models.TextChoices):
        POST='post','Idea para un post'
        PROPOSAL='propuesta','Propuesta de post'
        FACT='dato','Dato sobre mí'
        ANSWER='respuesta','Responde una pregunta'
        GALLERY='galeria','Foto para la galería'
    class Context(models.TextChoices):
        QUESTION='pregunta','Pregunta de Tu turno'
        PERSON='persona','Persona'
        PIECE='pieza','Pieza'
    class State(models.TextChoices):
        RECEIVED='recibida','Recibida'
        TRANSCRIBING='transcribiendo','Transcribiendo'
        PROCESSING='procesando','Procesando'
        SAVED='dato_guardado','Dato guardado'
        NOTED='anotado','Anotado'
        IDEA='idea','En la mesa editorial'
        USED='usado','Usado'
        UNUSED='sin_usar','Sin usar'
        ERROR='error','No se pudo procesar'
        UNDONE='deshecha','Deshecha'
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,related_name='+')
    created_at=models.DateTimeField(default=timezone.now,db_index=True)
    note=models.TextField(blank=True)
    purpose=models.CharField(max_length=12,choices=Purpose.choices,blank=True)
    ai_edit=models.CharField(max_length=4,choices=AIEdit.choices,default=AIEdit.AUTO)
    publish_asap=models.BooleanField(default=False,db_index=True)
    publish_asap_evidence=models.TextField(blank=True)
    publish_asap_not_before=models.DateField(null=True,blank=True)
    publish_asap_expected_slot=models.DateTimeField(null=True,blank=True)
    publish_asap_reason=models.TextField(blank=True)
    understanding=models.JSONField(default=dict,blank=True)
    investigation=models.JSONField(default=dict,blank=True)
    context_type=models.CharField(max_length=10,choices=Context.choices,blank=True)
    context_id=models.CharField(max_length=64,blank=True)
    # Visibility chosen when the capture answers a question (null: the question's suggestion).
    public_use=models.BooleanField(null=True,blank=True)
    audio=models.FileField(upload_to=capture_audio_path,max_length=200,null=True,blank=True)
    audio_mime=models.CharField(max_length=60,blank=True)
    # Duration reported by the client at upload; replaced by AssemblyAI's audio_duration once transcribed.
    audio_duration_s=models.FloatField(null=True,blank=True)
    transcript=models.TextField(blank=True)
    transcript_language=models.CharField(max_length=20,blank=True)
    transcript_provider_id=models.CharField(max_length=80,blank=True)
    state=models.CharField(max_length=16,choices=State.choices,default=State.RECEIVED,db_index=True)
    # What the UI shows: {kind, text, link}.
    outcome=models.JSONField(default=dict,blank=True)
    routed_to=models.JSONField(default=dict,blank=True)
    error=models.TextField(blank=True)
    class Meta:ordering=['-created_at']
    def __str__(self):return f'{self.created_at:%Y-%m-%d %H:%M} · {self.get_state_display()}'
    @property
    def text(self):
        """The note plus the transcript: what the team routes."""
        return '\n\n'.join(part.strip() for part in (self.note,self.transcript) if part and part.strip())

class WebResearchRun(models.Model):
    """One durable research attempt per caller key, including failures and interrupted work.

    Generic ownership prepares the phase 3 tool adapter; a retry never resets the daily quota.
    Request bodies are not stored, only a hash and the bounded result. No private memory here.
    """
    key=models.CharField(max_length=160,primary_key=True)
    request_hash=models.CharField(max_length=64)
    created_at=models.DateTimeField(default=timezone.now,db_index=True)
    state=models.CharField(max_length=20,default='running')
    result=models.JSONField(default=dict,blank=True)


class GalleryPhoto(models.Model):
    """«Galería»: photos for Gustavo's posts. The team decides when to use them and whether to edit them with AI."""
    class State(models.TextChoices):
        UNUSED='sin_usar','Sin usar'
        CHOSEN='elegida','Elegida'
        EDITED='editada','Editada con IA'
        PUBLISHED='publicada','Publicada'
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    image=models.FileField(upload_to=gallery_image_path,max_length=200)
    mime=models.CharField(max_length=40)
    size_bytes=models.PositiveIntegerField()
    width=models.PositiveIntegerField(null=True,blank=True)
    height=models.PositiveIntegerField(null=True,blank=True)
    note=models.TextField(blank=True)
    ai_edit=models.CharField(max_length=4,choices=AIEdit.choices,default=AIEdit.AUTO)
    instruction=models.TextField(blank=True)
    instruction_kind=models.CharField(max_length=12,blank=True)
    state=models.CharField(max_length=12,choices=State.choices,default=State.UNUSED,db_index=True)
    chosen_piece=models.ForeignKey(EditorialPiece,on_delete=models.SET_NULL,null=True,blank=True,related_name='gallery_photos')
    chosen_for=models.DateField(null=True,blank=True)
    published_at=models.DateTimeField(null=True,blank=True)
    capture=models.ForeignKey(Capture,on_delete=models.SET_NULL,null=True,blank=True,related_name='photos')
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,related_name='+')
    created_at=models.DateTimeField(default=timezone.now,db_index=True)
    class Meta:ordering=['-created_at']
    def __str__(self):return f'{self.id} · {self.get_state_display()}'

    @property
    def allow_ai_edit(self):return self.ai_edit!=AIEdit.NO
    @allow_ai_edit.setter
    def allow_ai_edit(self,value):self.ai_edit=AIEdit.AUTO if value else AIEdit.NO


class PieceImage(models.Model):
    """Frozen image and permission snapshot. Original files stay owned by GalleryPhoto."""
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    piece=models.ForeignKey(EditorialPiece,on_delete=models.CASCADE,related_name='images')
    source_photo=models.ForeignKey(GalleryPhoto,on_delete=models.CASCADE,null=True,blank=True,related_name='uses')
    position=models.PositiveSmallIntegerField(default=1)
    kind=models.CharField(max_length=16)
    image=models.FileField(upload_to='piezas/imagenes',max_length=200)
    mime=models.CharField(max_length=40,default='image/png')
    width=models.PositiveIntegerField()
    height=models.PositiveIntegerField()
    sha256=models.CharField(max_length=64)
    alt=models.TextField()
    edited=models.BooleanField(default=False)
    ai_edit=models.CharField(max_length=4,choices=AIEdit.choices,default=AIEdit.NO)
    reason=models.TextField(blank=True)
    template=models.CharField(max_length=20,blank=True)
    data=models.JSONField(default=dict,blank=True)
    review=models.JSONField(default=dict,blank=True)
    created_at=models.DateTimeField(default=timezone.now)
    class Meta:
        ordering=['position']
        constraints=[models.UniqueConstraint(fields=['piece','position'],name='one_image_per_piece_position')]

class OfficePreference(models.Model):
    """Singleton of Gustavo's office preferences (Ajustes)."""
    id=models.PositiveSmallIntegerField(primary_key=True,default=1,editable=False)
    gallery_ai_edit=models.CharField(max_length=4,choices=AIEdit.choices,default=AIEdit.AUTO)
    # Ajustes › Notificaciones: event kinds whose push Gustavo turned off, and those he turned on although their default
    # is off (notificaciones.INBOX_KINDS and FEED_KINDS hold the defaults; off wins if a kind is in both).
    push_disabled=models.JSONField(default=list,blank=True)
    push_enabled=models.JSONField(default=list,blank=True)
    updated_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,blank=True,related_name='+')
    updated_at=models.DateTimeField(null=True,blank=True)
    @classmethod
    def current(cls):
        return cls.objects.get_or_create(pk=1)[0]

    @property
    def gallery_ai_edit_default(self):return self.gallery_ai_edit!=AIEdit.NO
    @gallery_ai_edit_default.setter
    def gallery_ai_edit_default(self,value):self.gallery_ai_edit=AIEdit.AUTO if value else AIEdit.NO


class Notification(models.Model):
    """Notificaciones: what is coming or already happened and asks nothing of Gustavo (kept 7 days).
    Anything only he can solve lives in Tu turno instead (notificaciones.INBOX_KINDS)."""
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    kind=models.CharField(max_length=40)
    layer=models.CharField(max_length=20)
    title=models.CharField(max_length=300)
    detail=models.TextField(blank=True)
    link=models.CharField(max_length=300,blank=True)
    ref=models.CharField(max_length=160,null=True,blank=True,unique=True,help_text='Deduplica el mismo evento.')
    created_at=models.DateTimeField(default=timezone.now,db_index=True)
    read_at=models.DateTimeField(null=True,blank=True)
    class Meta:ordering=['-created_at']

class InboxSeen(models.Model):
    """Tu turno: an item Gustavo already opened («Vista»), keyed by the card id the API returns."""
    item_id=models.CharField(max_length=120,primary_key=True)
    seen_at=models.DateTimeField(default=timezone.now)


class Conversation(models.Model):
    """conversaciones_inbox (conversaciones.py): one LinkedIn 1to1 chat read through Unipile, read-only. The team
    proposes it to Gustavo (Tu turno) when it looks like business or needs his reply; it never answers. Messages are
    third-party data: shown and judged as data, never followed as instructions."""
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    account=models.ForeignKey(ConnectorAccount,on_delete=models.PROTECT,related_name='conversations')
    provider_chat_id=models.CharField(max_length=200)
    contact=models.ForeignKey(Contact,on_delete=models.SET_NULL,null=True,blank=True,related_name='conversations')
    attendee_name=models.CharField(max_length=200,blank=True)
    attendee_provider_id=models.CharField(max_length=200,blank=True)
    last_message_at=models.DateTimeField(null=True,blank=True,db_index=True)
    last_message_preview=models.CharField(max_length=300,blank=True)
    # Who sent the last message: True when it was Gustavo (is_sender), so nothing is waiting for him.
    last_from_me=models.BooleanField(default=False)
    # The latest messages, oldest first and bounded (INBOX_SNAPSHOT_MESSAGES): [{id, at, from_me, text}].
    messages=models.JSONField(default=list,blank=True)
    # Jev's read of the latest inbound message: {message_id, answers, opportunity, awaiting_reply, pitch, modality, model, at}.
    assessment=models.JSONField(default=dict,blank=True)
    # Inbound message id at which Gustavo closed the card («Hecho, respondí» / «No responder»); a newer one reopens it.
    closed_message_id=models.CharField(max_length=200,blank=True)
    created_at=models.DateTimeField(default=timezone.now)
    updated_at=models.DateTimeField(default=timezone.now)
    class Meta:
        ordering=['-last_message_at']
        constraints=[models.UniqueConstraint(fields=['account','provider_chat_id'],name='unique_conversation_per_account')]
    def __str__(self):return self.attendee_name or self.provider_chat_id


class WeeklySummary(models.Model):
    """analista_barrio_resultados (resumen_semanal.py): the results of one local ISO week (Monday to Sunday) and the
    analysis written from them. One per week. Only Gustavo's decision turns its proposed orientation into the team's."""
    class State(models.TextChoices):
        NEW='nuevo','Nuevo'
        SEEN='visto','Visto'
        APPLIED='aplicado','Usado como orientación'
        DISCARDED='descartado','Descartado'
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    week_start=models.DateField(unique=True)
    # Deterministic figures of the week and the one before; null means no data, never zero.
    stats=models.JSONField(default=dict,blank=True)
    # {titular, lo_que_funciono, lo_que_no, recomendaciones, orientacion_propuesta, advertencias, validacion}.
    analysis=models.JSONField(default=dict,blank=True)
    state=models.CharField(max_length=12,choices=State.choices,default=State.NEW,db_index=True)
    usage=models.JSONField(default=dict,blank=True)
    cost_usd=models.DecimalField(max_digits=12,decimal_places=6,null=True,blank=True)
    # «Usar como orientación»: the orientation it replaced, so «Deshacer» can put it back.
    previous_orientation=models.TextField(blank=True)
    decided_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,blank=True,related_name='+')
    decided_at=models.DateTimeField(null=True,blank=True)
    origin_job=models.CharField(max_length=40,blank=True)
    created_at=models.DateTimeField(default=timezone.now)
    updated_at=models.DateTimeField(auto_now=True)
    class Meta:ordering=['-week_start']
    def __str__(self):return f'{self.week_start} · {self.get_state_display()}'


class DeviceToken(models.Model):
    """Login of the 0ff1ce mobile app on one device (docs/app-movil-backend.md): a human session without cookies or
    CSRF. Separate from ApiCredential on purpose: a service credential never decides, a device token is Gustavo himself.
    Only the SHA-256 digest is stored; the plain token (authentication.DEVICE_PREFIX…) is shown once, when issued."""
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name='device_tokens')
    name=models.CharField(max_length=120)
    digest=models.CharField(max_length=64,unique=True,editable=False)
    created_at=models.DateTimeField(default=timezone.now,editable=False)
    last_used_at=models.DateTimeField(null=True,blank=True)
    revoked_at=models.DateTimeField(null=True,blank=True,db_index=True)
    class Meta:ordering=['-created_at']
    def __str__(self):return self.name


class ExpoPushToken(models.Model):
    """Native push of the mobile app through Expo (expo.py). Registering the same token again updates it; revoking
    its device login or Expo's DeviceNotRegistered deactivates it."""
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name='expo_push_tokens')
    device=models.ForeignKey(DeviceToken,on_delete=models.CASCADE,null=True,blank=True,related_name='expo_push_tokens')
    token=models.CharField(max_length=200,unique=True)
    device_name=models.CharField(max_length=120,blank=True)
    active=models.BooleanField(default=True,db_index=True)
    created_at=models.DateTimeField(default=timezone.now)
    updated_at=models.DateTimeField(default=timezone.now)
    last_success_at=models.DateTimeField(null=True,blank=True)
    # Last per-message error from Expo, or why the token was deactivated (DeviceNotRegistered, device_revoked).
    last_error=models.CharField(max_length=80,blank=True)
    # Push tickets waiting for their receipt: [[ticket_id, iso]], newest last, at most expo.MAX_TICKETS.
    tickets=models.JSONField(default=list,blank=True)
    def __str__(self):return self.device_name or str(self.id)


class AppClientError(models.Model):
    """A failure the mobile app reported (POST /api/v1/app/errores, movil_views.ClientErrors): what failed and on which
    build, so the team can diagnose it without the phone. Never what was being sent: no audio, photos, note text, file
    names or tokens. Only the newest movil_views.CLIENT_ERRORS_KEPT are kept."""
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    created_at=models.DateTimeField(default=timezone.now,editable=False,db_index=True)
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name='app_client_errors')
    device=models.ForeignKey(DeviceToken,on_delete=models.SET_NULL,null=True,blank=True,related_name='client_errors')
    # What failed (captura_envio, galeria_subida…), the error class and message, and the HTTP answer if there was one.
    kind=models.CharField(max_length=40)
    name=models.CharField(max_length=80,blank=True)
    message=models.CharField(max_length=500,blank=True)
    status=models.PositiveSmallIntegerField(null=True,blank=True)
    detail=models.CharField(max_length=500,blank=True)
    # [{field, type, scheme, size}] of the upload's file parts.
    parts=models.JSONField(default=list,blank=True)
    platform=models.CharField(max_length=20,blank=True)
    os_version=models.CharField(max_length=40,blank=True)
    app_version=models.CharField(max_length=40,blank=True)
    class Meta:ordering=['-created_at']
    def __str__(self):return f'{self.kind} · {self.name}'


class EvidencePerson(models.Model):
    """Identity in one connector account. Never merged by name, slug or URN prefix."""
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    account=models.ForeignKey(ConnectorAccount,on_delete=models.PROTECT,related_name='evidence_people')
    provider_user_id=models.CharField(max_length=200)
    display_name=models.CharField(max_length=200,blank=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['account','provider_user_id'],name='unique_evidence_person')]


class PersonEvidence(models.Model):
    """Minimized observations; unknown event time stays null. No inbox text or invitation message."""
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    person=models.ForeignKey(EvidencePerson,on_delete=models.PROTECT,related_name='observations')
    key=models.CharField(max_length=64)
    kind=models.CharField(max_length=32)
    source=models.CharField(max_length=40)
    source_id=models.CharField(max_length=200)
    referent=models.ForeignKey(Referent,on_delete=models.PROTECT,null=True,blank=True,related_name='person_evidence')
    post_id=models.CharField(max_length=200,blank=True)
    interaction_id=models.CharField(max_length=200,blank=True)
    source_url=models.TextField(blank=True)
    event_at=models.DateTimeField(null=True,blank=True)
    observed_at=models.DateTimeField(db_index=True)
    recorded_at=models.DateTimeField(default=timezone.now)
    coverage=models.JSONField(default=dict)
    details=models.JSONField(default=dict)
    experiment_id=models.CharField(max_length=200,blank=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['person','key'],name='unique_person_evidence')]


class EvidenceCoverage(models.Model):
    """A read/cut even when no identifiable people were returned. Counts may be unknown."""
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    account=models.ForeignKey(ConnectorAccount,on_delete=models.PROTECT,related_name='evidence_coverage')
    source=models.CharField(max_length=40)
    source_id=models.CharField(max_length=200)
    referent=models.ForeignKey(Referent,on_delete=models.PROTECT,null=True,blank=True)
    observed_at=models.DateTimeField(db_index=True)
    status=models.CharField(max_length=20)
    details=models.JSONField(default=dict)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['account','source','source_id'],name='unique_evidence_coverage')]


class FitClassification(models.Model):
    """Append-only fit history; operational Contact.classification remains compatible."""
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    person=models.ForeignKey(EvidencePerson,on_delete=models.PROTECT,related_name='fit_versions')
    key=models.CharField(max_length=64)
    criterion_version=models.CharField(max_length=100)
    classified_at=models.DateTimeField(null=True,blank=True)
    recorded_at=models.DateTimeField(default=timezone.now)
    sufficient=models.BooleanField(default=False)
    fit=models.BooleanField(null=True,blank=True)
    details=models.JSONField(default=dict)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['person','key'],name='unique_fit_version')]


class ReferentAttribution(models.Model):
    """Versioned observational report, including its baseline and exposure evidence."""
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    referent=models.ForeignKey(Referent,on_delete=models.PROTECT,related_name='attribution_reports')
    key=models.CharField(max_length=64)
    window_start=models.DateTimeField()
    window_end=models.DateTimeField()
    as_of=models.DateTimeField()
    created_at=models.DateTimeField(default=timezone.now)
    report=models.JSONField(default=dict)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['referent','key'],name='unique_referent_attribution')]


class CycleLedger(models.Model):
    """One durable orchestrator instance; JSON payloads are private workspace data."""
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    cycle=models.CharField(max_length=60)
    key=models.CharField(max_length=160)
    owner=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    job=models.ForeignKey(Job,on_delete=models.SET_NULL,null=True,blank=True)
    orchestrator=models.CharField(max_length=60)
    graph_version=models.CharField(max_length=40)
    graph_hash=models.CharField(max_length=64)
    limits=models.JSONField(default=dict)
    budget_bucket=models.CharField(max_length=220,db_index=True)
    task_ledger=models.JSONField(default=dict)
    progress_ledger=models.JSONField(default=dict)
    state=models.CharField(max_length=20,default='running',db_index=True)
    stop_reason=models.CharField(max_length=80,blank=True)
    needs_attention=models.BooleanField(default=False)
    lease_token=models.CharField(max_length=32,blank=True)
    revision=models.PositiveIntegerField(default=0)
    calls=models.PositiveIntegerField(default=0)
    active_seconds=models.FloatField(default=0)
    created_at=models.DateTimeField(default=timezone.now)
    updated_at=models.DateTimeField(auto_now=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['cycle','key'],name='unique_cycle_instance')]
        ordering=['-updated_at']
