import uuid
from django.conf import settings
from django.db import models, transaction
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
# Organizations (docs/plan-organizaciones.md, phase 1): who each LinkedIn account belongs to. The organization holds what
# is shared because the goal is the same (ProjectApp); a member is one person with her own login and her own accounts.
# team_backend/miembros.py is the one way to ask «whose is this»; no code reads these tables directly for that.

class Organization(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    name=models.CharField(max_length=120)
    slug=models.SlugField(max_length=60,unique=True)
    created_at=models.DateTimeField(default=timezone.now)
    # What the organization is and sells (phase 3, identidad.ORGANIZATION_FIELDS): positioning version and status,
    # language, pillars, services, offer, cases, modalities and the neighborhood. Validated and audited by
    # identidad.save_profile (each change leaves an IdentityRevision); empty: the installation's initial identity.
    profile=models.JSONField(default=dict,blank=True)
    def __str__(self):return self.name

class Member(models.Model):
    """One person of an organization: her Django user (her login), the name the team uses for her and her role. `active`
    off: she keeps her accounts but nothing resolves to her and she owns nothing (miembros.py). `is_admin`: may add
    members and decide on the organization's referents; never opens another member's LinkedIn session."""
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    organization=models.ForeignKey(Organization,on_delete=models.PROTECT,related_name='members')
    # One login, one member (one organization per user for now; a FK unique per organization if that ever changes).
    user=models.OneToOneField(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='member')
    display_name=models.CharField(max_length=120)
    role=models.CharField(max_length=120,blank=True)  # free text: «Fundador», «CTO»
    active=models.BooleanField(default=True)
    is_admin=models.BooleanField(default=False)
    created_at=models.DateTimeField(default=timezone.now)
    # Her LinkedIn rhythm when it differs from the .env (phase 2): {VARIABLE: value} with the same names and formats as
    # the environment (LINKEDIN_ACCOUNT_TIER, OPERATOR_DAILY_LIMITS…). Only miembros.MEMBER_SETTINGS, validated by
    # miembros.save_settings; a variable she does not set takes the .env's value (miembros.setting).
    settings=models.JSONField(default=dict,blank=True)
    # Who she is for the agents (phase 3, identidad.MEMBER_FIELDS): the name the team writes, how she presents herself,
    # her relation to the organization, her limits, whether the personal startup modality is hers. Only she changes it
    # (identidad.save_profile, audited with an IdentityRevision). Her voice is VoiceDocument.
    profile=models.JSONField(default=dict,blank=True)
    class Meta:ordering=['created_at']
    def __str__(self):return f'{self.display_name} ({self.organization.slug})'


class IdentityRevision(models.Model):
    """One change of an identity profile, the organization's (`subject`='organization') or a member's ('member:<id>'):
    who, when, which fields, the whole profile before and after. Only added, never edited (identidad.save_profile)."""
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    organization=models.ForeignKey(Organization,on_delete=models.PROTECT,related_name='identity_revisions')
    member=models.ForeignKey(Member,on_delete=models.PROTECT,null=True,blank=True,related_name='identity_revisions')
    subject=models.CharField(max_length=60)
    number=models.PositiveIntegerField()
    changed=models.JSONField(default=list,blank=True)
    before=models.JSONField(default=dict,blank=True)
    after=models.JSONField(default=dict,blank=True)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,blank=True,related_name='+')
    source=models.CharField(max_length=20)  # migracion, semilla, comando
    created_at=models.DateTimeField(default=timezone.now)
    class Meta:
        ordering=['created_at']
        constraints=[models.UniqueConstraint(fields=['organization','subject','number'],name='one_identity_revision_number')]


class VoiceDocument(models.Model):
    """A member's voice document (voz.py), versioned. Used only once she confirms it; the latest confirmed one is her
    voice. Gustavo's points to recursos/tono-de-voz.md (`resource`); a learned one keeps its text and the references to
    the signals it came from (`signals`, never copies of them)."""
    class State(models.TextChoices):
        PROPOSED='propuesta','Propuesta; espera su confirmación'
        CONFIRMED='confirmada','Confirmada por ella'
        DISCARDED='descartada','Descartada'
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    member=models.ForeignKey(Member,on_delete=models.PROTECT,related_name='voice_documents')
    number=models.PositiveIntegerField()
    state=models.CharField(max_length=12,choices=State.choices,default=State.PROPOSED,db_index=True)
    source=models.CharField(max_length=20)  # recurso (a file of recursos/), aprendida (proposed from her signals)
    guide=models.TextField(blank=True)  # how the team applies it on LinkedIn; empty: voz.GENERIC_GUIDE
    text=models.TextField(blank=True)
    resource=models.CharField(max_length=120,blank=True)
    sha256=models.CharField(max_length=64,blank=True)
    signals=models.JSONField(default=list,blank=True)
    usage=models.JSONField(default=dict,blank=True)
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,blank=True,related_name='+')
    created_at=models.DateTimeField(default=timezone.now)
    decided_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,blank=True,related_name='+')
    decided_at=models.DateTimeField(null=True,blank=True)
    note=models.TextField(blank=True)
    class Meta:
        ordering=['-number']
        constraints=[models.UniqueConstraint(fields=['member','number'],name='one_voice_document_number')]


class VoiceSignal(models.Model):
    """A trace of her style that already lives in the system (voz.collect_signals): a reference to the row, never a copy
    of its text. One per member, kind and row."""
    class Kind(models.TextChoices):
        APPROVED='aprobado','Aprobó un borrador sin cambios'
        EDITED='editado','Editó un borrador (antes y después)'
        REJECTED='rechazado','Rechazó un borrador con su motivo'
        ANSWER='respuesta','Respondió una pregunta del equipo'
        CAPTURE='captura','Grabó un audio o escribió una nota'
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    member=models.ForeignKey(Member,on_delete=models.PROTECT,related_name='voice_signals')
    kind=models.CharField(max_length=12,choices=Kind.choices)
    source_model=models.CharField(max_length=40)
    source_id=models.CharField(max_length=64)
    occurred_at=models.DateTimeField()
    created_at=models.DateTimeField(default=timezone.now)
    class Meta:
        ordering=['-occurred_at']
        constraints=[models.UniqueConstraint(fields=['member','kind','source_model','source_id'],name='one_voice_signal_per_row')]


# ---------------------------------------------------------------------------
# Account operator: the single executor of external LinkedIn actions.
# Proposal -> approval of an exact payload hash -> one execution -> confirmation.

class ConnectorAccount(models.Model):
    class Provider(models.TextChoices):
        FAKE='fake','Simulado (pruebas)'
        # The real account, through the navegador service; external_account_id is the account's name there.
        DIRECTO='directo','LinkedIn directo (navegador)'
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
    # When the LinkedIn ids kept for the account changed scheme (2026-11-14 on the first account, when it moved to
    # directo), or null. Ids an audit event kept before then are of the scheme before and are never reused
    # (metricas._known_id, red.search_location).
    ids_since=models.DateTimeField(null=True,blank=True)
    # Whose LinkedIn this is (organizaciones, phase 1). Null only for an account created before any member existed or by a
    # test: it belongs to the only active member, and to nobody once there are several (miembros.member_of_account).
    member=models.ForeignKey(Member,on_delete=models.PROTECT,null=True,blank=True,related_name='accounts')
    class Meta:
        constraints=[models.UniqueConstraint(fields=['provider','external_account_id'],name='unique_connector_account')]
    def __str__(self):return f'{self.label} ({self.provider})'

class Referent(models.Model):
    class Kind(models.TextChoices):
        # Main or variable (protected) is the slot; the kind is why the team reads them. Gustavo, 14/11/2026: big voices of
        # his own industry that sell what he sells, so that what works for them becomes a model (referentes_industria.py).
        NICHO='nicho','Voz del nicho'
        INDUSTRIA='industria','Referente de industria'
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    kind=models.CharField(max_length=16,choices=Kind.choices,default=Kind.NICHO)
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
    # mensual: the monthly batch (and the extraordinary one, which takes its place); industria: the search Gustavo starts
    # by hand (operador referentes-industria), never applied by silence: one a month, plus another attempt when every
    # earlier one ended without proposals (attempt 2, 3…; the earlier one is closed, referentes_industria.supersede).
    kind=models.CharField(max_length=16,default='mensual')
    attempt=models.PositiveSmallIntegerField(default=1)
    state=models.CharField(max_length=24,default='preparing')
    dossier=models.JSONField(default=dict)
    expected_revision=models.PositiveIntegerField(default=1)
    published_at=models.DateTimeField(null=True,blank=True)
    deadline=models.DateTimeField()
    closed_at=models.DateTimeField(null=True,blank=True)
    created_at=models.DateTimeField(default=timezone.now)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['account','month','kind','attempt'],name='unique_referent_month_kind_attempt')]


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
    # «What worked for them» (modelos_crecimiento.py). outlier: how the post did against its author's own norm. structure:
    # its shape (hook, length band, outline, closing…) as labels and numbers, never a sentence of it. audience: what its
    # comments were like (counts and de-identified themes), computed when a step already read them; no names, no text.
    outlier=models.JSONField(default=dict,blank=True)
    structure=models.JSONField(default=dict,blank=True)
    audience=models.JSONField(default=dict,blank=True)
    # «Qué les funciona y qué no» (analisis_referentes.py): shares as LinkedIn counts them (null: hidden or read before
    # this field), the media the connector recognized ('' = not known, never «text only») and the post's decomposition
    # (topic, hook, body, closing, length, topical signals) as labels, cached by a hash of its text and media.
    reposts_count=models.IntegerField(null=True,blank=True)
    media=models.CharField(max_length=20,blank=True,default='')
    analysis=models.JSONField(default=dict,blank=True)
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
        OWN_POST='own_post','Comentó en tu post'
        SEARCH='search','Búsqueda'
        INCOMING='incoming','Invitación recibida'
        MANUAL='manual','Añadido a mano'
        REFERRAL='referido','Referido por un comprador que respondió (fase 6)'
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
    # What the last profile read or search result said about reach and moment (connectors._signals): followers,
    # connections, bio, is_creator, is_hiring, is_open_to_work… Kept to set thresholds with data, never guessed.
    signals=models.JSONField(default=dict,blank=True)
    followed_at=models.DateTimeField(null=True,blank=True)
    invited_at=models.DateTimeField(null=True,blank=True)
    connected_at=models.DateTimeField(null=True,blank=True)
    discovered_at=models.DateTimeField(default=timezone.now)
    updated_at=models.DateTimeField(default=timezone.now)
    # Phase 5 (sin_posts.py): this person is the bridge («puente») to the buyer of that journey, a colleague at the
    # same company who does post. Its own contact with its own role, never a second buyer. Null for everyone else.
    bridge_for=models.ForeignKey('BuyerJourney',on_delete=models.SET_NULL,null=True,blank=True,related_name='bridges')
    class Meta:
        ordering=['-updated_at']
        constraints=[models.UniqueConstraint(fields=['account','provider_user_id'],name='unique_contact_per_account')]
    def __str__(self):return self.display_name or self.provider_user_id

OPEN_ACTION_STATES=['proposed','approved','executing','sent','uncertain']
OPEN_PIECE_STATES=['preparing','ready']


def _her_content(row,account=None):
    """Phase 4 of organizations: a content row created without saying whose is the member of its account (a piece), else
    the default member (miembros.content_member: MiembroRequerido among several active members, never a guess). Without
    members it stays without one, as before organizations."""
    if row.member_id is None and row._state.adding:
        from .miembros import content_member
        member=content_member(account=account)
        if member is not None:row.member=member


def _whose_upload(row):
    """A capture or a photo is of the member who recorded or uploaded it (created_by); a robot, a service or nobody: the
    default member (_her_content)."""
    if row.member_id is None and row._state.adding and row.created_by_id:
        from .miembros import member_of_user
        own=member_of_user(row.created_by)
        if own is not None:row.member=own
    _her_content(row)

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
    # Whose piece (organizaciones, phase 4): her calendar, her day's post and her second one. Set from the account's member.
    member=models.ForeignKey(Member,on_delete=models.PROTECT,null=True,blank=True,related_name='pieces')
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
    # Which voice wrote it (phase 3, voz.meta): {'tipo': 'provisional'|'confirmada'|'inicial', 'version': n}. A draft in the
    # provisional voice of a member who has none yet is marked so (phase 5 shows it, phase 7 keeps her in approval).
    voice=models.JSONField(default=dict,blank=True)
    # APRE-01, first metric: impressions read back when the publication is reconciled (null ≠ 0).
    metrics=models.JSONField(default=dict,blank=True)
    note=models.TextField(blank=True)
    origin_job=models.CharField(max_length=40,blank=True)
    # One post a day, except the extra one Gustavo asked for at a day and hour (urgente.py: an order, 14/11/2026). It does
    # not count for the CONT-09 caps nor for the GASP structure.
    second_of_day=models.BooleanField(default=False)
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,related_name='+')
    created_at=models.DateTimeField(default=timezone.now)
    updated_at=models.DateTimeField(auto_now=True)
    class Meta:
        ordering=['-slot_date','-created_at']
        # One open post of the day and one second post per member and day (phase 4); without members (member null) one per
        # day for the whole installation, as before (NULLS NOT DISTINCT).
        constraints=[models.UniqueConstraint(fields=['member','slot_date'],condition=models.Q(state__in=OPEN_PIECE_STATES,second_of_day=False),
                                             name='one_open_piece_per_member_day',nulls_distinct=False),
                     models.UniqueConstraint(fields=['member','slot_date'],condition=models.Q(state__in=OPEN_PIECE_STATES,second_of_day=True),
                                             name='one_second_piece_per_member_day',nulls_distinct=False)]
    def __str__(self):return f'{self.slot_date} · {self.get_state_display()}'
    def save(self,*args,**kwargs):
        _her_content(self,self.account if self.account_id else None)
        super().save(*args,**kwargs)

class PostMetric(models.Model):
    """APRE-01: cumulative counters of an own published post at a fixed age, read through the directo account (metricas.py).
    Each age is captured once, late if need be (captured_at - published_at tells how late). Null means no data
    (hidden by LinkedIn, absent or unread), never zero."""
    class Kind(models.TextChoices):
        H24='24h','24 horas'
        H72='72h','72 horas'
        D7='7d','7 días'
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    piece=models.ForeignKey(EditorialPiece,on_delete=models.CASCADE,related_name='post_metrics')
    provider_post_id=models.CharField(max_length=200,blank=True)  # the connector's id (activity number), not the official URN
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

class PostComment(models.Model):
    """INT-04 (respuestas.py): a comment on one of Gustavo's own posts (a published piece), read through the directo account. His own
    replies are kept too (own=True), so the team sees the whole thread before answering and never answers twice. The
    text of other people is third-party data: shown and judged as data, never followed as instructions."""
    class State(models.TextChoices):
        NEW='new','Leído; el equipo decide qué hacer'
        REPLY='reply','El equipo responde en el hilo'
        REACT='react','Basta una reacción'
        ASKED='asked','El equipo le preguntó un dato a Gustavo'
        IGNORED='ignored','Sin respuesta: spam, autopromoción, ofensivo o sin relación'
        CLOSED='closed','Sin respuesta: ya respondida, plazo vencido o hilo cerrado'
        OWN='own','Respuesta de Gustavo'
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    account=models.ForeignKey(ConnectorAccount,on_delete=models.PROTECT,related_name='post_comments')
    piece=models.ForeignKey(EditorialPiece,on_delete=models.CASCADE,related_name='post_comments')
    provider_post_id=models.CharField(max_length=200)  # the connector's id of the own post
    provider_comment_id=models.CharField(max_length=200)
    # The top-level comment this one replies to ('' for a top-level comment): LinkedIn threads have one level.
    thread_id=models.CharField(max_length=200,blank=True,db_index=True)
    author_provider_id=models.CharField(max_length=200,blank=True)
    author_name=models.CharField(max_length=200,blank=True)
    author_public_identifier=models.CharField(max_length=100,blank=True)
    author_profile_url=models.TextField(blank=True)
    author_kind=models.CharField(max_length=20,blank=True)  # individual | organization
    text=models.TextField(blank=True)
    commented_at=models.DateTimeField(null=True,blank=True)
    own=models.BooleanField(default=False)
    reply_count=models.IntegerField(null=True,blank=True)
    contact=models.ForeignKey(Contact,on_delete=models.SET_NULL,null=True,blank=True,related_name='post_comments')
    state=models.CharField(max_length=12,choices=State.choices,default=State.NEW,db_index=True)
    # What the team decided and why: {reason, turn, closing, by, model, at, question, dm_opener, dm_closed, ...}.
    decision=models.JSONField(default=dict,blank=True)
    observed_at=models.DateTimeField(default=timezone.now)
    updated_at=models.DateTimeField(default=timezone.now)
    class Meta:
        ordering=['commented_at','observed_at']
        constraints=[models.UniqueConstraint(fields=['account','provider_comment_id'],name='unique_post_comment')]
    @property
    def thread_key(self):
        return self.thread_id or self.provider_comment_id
    def __str__(self):return f'{self.author_name}: {self.text[:60]}'

class AudienceSnapshot(models.Model):
    """APRE-01: Gustavo's own audience once per local day (OPERATOR_TIMEZONE), read through the directo account.
    Cumulative counters: net growth is the difference between two snapshots. Null means no data, never zero."""
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    # One per member and day (organizaciones, phase 4); without members, one per day.
    member=models.ForeignKey(Member,on_delete=models.PROTECT,null=True,blank=True,related_name='audience')
    day=models.DateField()
    followers=models.IntegerField(null=True,blank=True)
    connections=models.IntegerField(null=True,blank=True)
    # LinkedIn reports profile views over a trailing window (List Profile Views, date_range in days).
    profile_views=models.IntegerField(null=True,blank=True)
    profile_views_days=models.PositiveSmallIntegerField(null=True,blank=True)
    captured_at=models.DateTimeField(default=timezone.now)
    class Meta:
        ordering=['-day']
        constraints=[models.UniqueConstraint(fields=['member','day'],name='one_audience_per_member_day',nulls_distinct=False)]
    def __str__(self):return str(self.day)
    def save(self,*args,**kwargs):
        _her_content(self);super().save(*args,**kwargs)

# ---------------------------------------------------------------------------
# Creator analytics of a `directo` account (analitica.py): LinkedIn's own export of the account, imported by day, per
# post, per capture and per range. Only the account's own figures and aggregate demographics: no third-party person.
# Null means no data, never zero. Days are UTC, as LinkedIn counts them.

class AnalyticsDay(models.Model):
    """One UTC day: impressions, engagements and new followers. Every import that covers the day updates it (recent
    days still move); a value already seen is never replaced by a missing one."""
    account=models.ForeignKey(ConnectorAccount,on_delete=models.CASCADE,related_name='analytics_days')
    day=models.DateField()
    impressions=models.IntegerField(null=True,blank=True)
    engagements=models.IntegerField(null=True,blank=True)
    new_followers=models.IntegerField(null=True,blank=True)
    updated_at=models.DateTimeField(default=timezone.now)
    class Meta:
        ordering=['account','day']
        constraints=[models.UniqueConstraint(fields=['account','day'],name='one_analytics_day')]

class AnalyticsPost(models.Model):
    """Lifetime figures of one own post as the export last showed them (its «latest posts» sheet ignores the range and
    lists only the latest few). Keyed by the post's urn as LinkedIn links it (activity, share or ugcPost)."""
    account=models.ForeignKey(ConnectorAccount,on_delete=models.CASCADE,related_name='analytics_posts')
    post_urn=models.CharField(max_length=60)
    url=models.TextField(blank=True)
    # The editorial piece, when the urn is one we keep for a CONT-09 publication.
    piece=models.ForeignKey(EditorialPiece,on_delete=models.SET_NULL,null=True,blank=True,related_name='analytics_posts')
    published=models.DateField(null=True,blank=True)
    kind=models.CharField(max_length=60,blank=True)  # LinkedIn's own label, in the account's language
    impressions=models.IntegerField(null=True,blank=True)
    network_pct=models.FloatField(null=True,blank=True)
    outside_pct=models.FloatField(null=True,blank=True)
    members_reached=models.IntegerField(null=True,blank=True)
    followers_gained=models.IntegerField(null=True,blank=True)
    profile_views=models.IntegerField(null=True,blank=True)
    reactions=models.IntegerField(null=True,blank=True)
    comments=models.IntegerField(null=True,blank=True)
    shares=models.IntegerField(null=True,blank=True)
    saves=models.IntegerField(null=True,blank=True)
    sends=models.IntegerField(null=True,blank=True)
    button_clicks=models.IntegerField(null=True,blank=True)
    first_seen_at=models.DateTimeField(default=timezone.now)
    last_seen_at=models.DateTimeField(default=timezone.now)
    class Meta:
        ordering=['account','-published']
        constraints=[models.UniqueConstraint(fields=['account','post_urn'],name='one_analytics_post')]

class AnalyticsSnapshot(models.Model):
    """What the export says about the account TODAY whatever the range asked: the follower total and the audience
    demographics, once per account and UTC day of capture (the last import of the day wins)."""
    account=models.ForeignKey(ConnectorAccount,on_delete=models.CASCADE,related_name='analytics_snapshots')
    day=models.DateField()
    followers=models.IntegerField(null=True,blank=True)
    # [{group, label, pct, below, value}] as LinkedIn labels them; [] when the sheet came with no rows.
    audience=models.JSONField(default=list,blank=True)
    captured_at=models.DateTimeField(default=timezone.now)
    class Meta:
        ordering=['account','-day']
        constraints=[models.UniqueConstraint(fields=['account','day'],name='one_analytics_snapshot')]

class AnalyticsRange(models.Model):
    """What only holds for the exact range imported: the totals (members reached cannot be added across days), LinkedIn's
    two top-post lists and the content demographics. The last import of the same range wins."""
    account=models.ForeignKey(ConnectorAccount,on_delete=models.CASCADE,related_name='analytics_ranges')
    start=models.DateField()
    end=models.DateField()
    impressions=models.IntegerField(null=True,blank=True)
    members_reached=models.IntegerField(null=True,blank=True)
    # [{post_urn, url, published, value}] in LinkedIn's order.
    top_by_engagements=models.JSONField(default=list,blank=True)
    top_by_impressions=models.JSONField(default=list,blank=True)
    # [{group, label, pct, below, value}]; null when the workbook had no content demographics sheet.
    content=models.JSONField(null=True,blank=True)
    captured_at=models.DateTimeField(default=timezone.now)
    class Meta:
        ordering=['account','-captured_at']
        constraints=[models.UniqueConstraint(fields=['account','start','end'],name='one_analytics_range')]

class AnalyticsImport(models.Model):
    """One export asked of LinkedIn and what came of it. Errors keep the kind and a message that names the sheet and
    row when the workbook could not be read, never a cell's value."""
    class State(models.TextChoices):
        RUNNING='running','En curso'
        OK='ok','Importada'
        ERROR='error','Fallida'
    class Trigger(models.TextChoices):
        DAILY='diaria','Importación diaria'
        MANUAL='manual','A mano'
        BACKFILL='carga_inicial','Carga inicial'
    account=models.ForeignKey(ConnectorAccount,on_delete=models.CASCADE,related_name='analytics_imports')
    start=models.DateField()
    end=models.DateField()
    trigger=models.CharField(max_length=16,choices=Trigger.choices,default=Trigger.MANUAL)
    state=models.CharField(max_length=10,choices=State.choices,default=State.RUNNING,db_index=True)
    error_kind=models.CharField(max_length=40,blank=True)
    error=models.TextField(blank=True)
    # {days, posts, posts_without_urn, top_by_engagements, top_by_impressions, audience, content}
    rows=models.JSONField(default=dict,blank=True)
    # The workbook's sheet names (LinkedIn's labels): a six-sheet workbook says which demographics came.
    sheets=models.JSONField(default=list,blank=True)
    started_at=models.DateTimeField(default=timezone.now)
    finished_at=models.DateTimeField(null=True,blank=True)
    class Meta:
        ordering=['-started_at']
        indexes=[models.Index(fields=['account','state','started_at'],name='analytics_import_last')]

class CanaryRun(models.Model):
    """One daily canary of a `directo` account (team_backend/canario.py): the connector's reads checked against the
    fields Barrio uses. `operations` keeps per read its state, row count and a reason; never a LinkedIn value."""
    class State(models.TextChoices):
        RUNNING='running','En curso'
        OK='ok','Todo bien'
        BROKEN='roto','Algo cambió en LinkedIn'
        HALTED='alto','Cuenta detenida'
        NOT_RUN='no_corrio','No pudo correr'
    account=models.ForeignKey(ConnectorAccount,on_delete=models.CASCADE,related_name='canary_runs')
    state=models.CharField(max_length=10,choices=State.choices,default=State.RUNNING)
    operations=models.JSONField(default=list,blank=True)  # [{operacion, estado, motivo, filas}]
    calls=models.PositiveIntegerField(default=0)
    error_kind=models.CharField(max_length=40,blank=True)
    error=models.TextField(blank=True)
    started_at=models.DateTimeField(default=timezone.now)
    finished_at=models.DateTimeField(null=True,blank=True)
    class Meta:
        ordering=['-started_at']
        indexes=[models.Index(fields=['account','started_at'],name='canary_run_last')]

class BrowserLogin(models.Model):
    """A login from the app into the navegador browser of a `directo` account (team_backend/conexion.py). The single-use
    ticket and the remote view's cookie are kept only as SHA-256 hashes; the view's key is never stored (an HMAC of the
    service token and `session`, which alone opens nothing)."""
    class State(models.TextChoices):
        STARTING='abriendo','Abriendo'
        WAITING='esperando','Esperando'
        CONNECTED='conectada','Conectada'
        EXPIRED='vencida','Vencida'
        CANCELLED='cancelada','Cancelada'
        FAILED='fallida','Fallida'
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    account=models.ForeignKey(ConnectorAccount,on_delete=models.CASCADE,related_name='browser_logins')
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True)
    session=models.CharField(max_length=64)
    state=models.CharField(max_length=12,choices=State.choices,default=State.STARTING)
    reason=models.TextField(blank=True)
    still_stopped=models.BooleanField(default=False)  # the service kept a stop that a login does not mend
    started_at=models.DateTimeField(default=timezone.now)
    expires_at=models.DateTimeField()
    finished_at=models.DateTimeField(null=True,blank=True)
    ticket_hash=models.CharField(max_length=64,blank=True,db_index=True)
    ticket_expires_at=models.DateTimeField(null=True,blank=True)
    cookie_hash=models.CharField(max_length=64,blank=True,db_index=True)
    class Meta:
        ordering=['-started_at']
        indexes=[models.Index(fields=['account','started_at'],name='browser_login_last')]

class ActionProposal(models.Model):
    referent_experiment=models.ForeignKey('ReferentExperiment',on_delete=models.PROTECT,null=True,blank=True)
    referent_experiment_version=models.PositiveIntegerField(null=True,blank=True)
    class Capability(models.TextChoices):
        COMMENT='INT-03','Comentar en una publicación ajena'
        REPLY='INT-04','Responder un comentario en una publicación propia'
        REACT='INT-02','Reaccionar a una publicación o a un comentario'
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
    # INT-04 replies (and INT-02 reactions to a comment) target a comment on an own post.
    comment=models.ForeignKey(PostComment,on_delete=models.PROTECT,related_name='proposals',null=True,blank=True)
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
    # Which voice wrote it (phase 3, voz.meta): {'tipo': 'provisional'|'confirmada'|'inicial', 'version': n}. A draft in the
    # provisional voice of a member who has none yet is marked so (phase 5 shows it, phase 7 keeps her in approval).
    voice=models.JSONField(default=dict,blank=True)
    class Meta:
        ordering=['-created_at']
        # One executor per action: a single open proposal per target (post, piece or contact) and capability.
        constraints=[models.UniqueConstraint(fields=['post','capability'],condition=models.Q(state__in=OPEN_ACTION_STATES),
                                             name='one_open_action_per_target'),
                     models.UniqueConstraint(fields=['piece','capability'],condition=models.Q(state__in=OPEN_ACTION_STATES),
                                             name='one_open_action_per_piece'),
                     models.UniqueConstraint(fields=['contact','capability'],condition=models.Q(state__in=OPEN_ACTION_STATES),
                                             name='one_open_action_per_contact'),
                     models.UniqueConstraint(fields=['comment','capability'],condition=models.Q(state__in=OPEN_ACTION_STATES),
                                             name='one_open_action_per_comment'),
                     models.CheckConstraint(condition=models.Q(post__isnull=False)|models.Q(piece__isnull=False)|models.Q(contact__isnull=False)
                                            |models.Q(comment__isnull=False),name='action_has_target')]
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

class ActionOutcome(models.Model):
    """What came after an executed action (desenlaces.py): an own comment on someone else's post (INT-03) at 72 h,
    read on LinkedIn, and a follow, invitation or acceptance (RED-01/02/04) at 7 d, derived from own data. Each age
    is captured once; null means not read or hidden by LinkedIn, never zero."""
    class Kind(models.TextChoices):
        H72='72h','72 horas'
        D7='7d','7 días'
    class Source(models.TextChoices):
        READ='read','Leído en LinkedIn'
        DERIVED='derived','Derivado de datos propios'
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    execution=models.ForeignKey(ActionExecution,on_delete=models.CASCADE,related_name='outcomes')
    kind=models.CharField(max_length=4,choices=Kind.choices)
    captured_at=models.DateTimeField(default=timezone.now)
    source=models.CharField(max_length=10,choices=Source.choices)
    provider_comment_id=models.CharField(max_length=255,blank=True)
    reactions=models.PositiveIntegerField(null=True,blank=True)
    replies=models.PositiveIntegerField(null=True,blank=True)
    author_replied=models.BooleanField(null=True,blank=True)
    # Public ids of the people who replied to the comment; never of those who only reacted.
    repliers=models.JSONField(default=list,blank=True)
    # Network signals derived from own data: {accepted, commented_own_post, replied_to_comment, invited_us}.
    signals=models.JSONField(default=dict,blank=True)
    class Meta:
        ordering=['captured_at']
        constraints=[models.UniqueConstraint(fields=['execution','kind'],name='one_outcome_per_age')]
    def __str__(self):return f'{self.execution_id} · {self.kind}'


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
    # Whose orientation (organizaciones, phase 4): row 1 is the first member's (and an installation's without members),
    # the one of before; any other member gets her own row (orientacion.row).
    member=models.OneToOneField(Member,on_delete=models.PROTECT,null=True,blank=True,related_name='orientation')
    @classmethod
    def current(cls,member=None):
        from .orientacion import row
        return row(member)

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
    # Whom the team asks (organizaciones, phase 4): her answer is her memory, never another member's.
    member=models.ForeignKey(Member,on_delete=models.PROTECT,null=True,blank=True,related_name='questions')
    class Meta:
        ordering=['-created_at']
        constraints=[models.UniqueConstraint(fields=['member','memory_key'],condition=models.Q(state='open'),
                                             name='one_open_question_per_member_key',nulls_distinct=False)]
    def __str__(self):return self.question[:80]
    def save(self,*args,**kwargs):
        _her_content(self);super().save(*args,**kwargs)

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
    # Whose capture (organizaciones, phase 4): her ideas, facts and photos feed only her pieces. The member of whoever
    # recorded it, else the default member.
    member=models.ForeignKey(Member,on_delete=models.PROTECT,null=True,blank=True,related_name='captures')
    created_at=models.DateTimeField(default=timezone.now,db_index=True)
    note=models.TextField(blank=True)
    purpose=models.CharField(max_length=12,choices=Purpose.choices,blank=True)
    ai_edit=models.CharField(max_length=4,choices=AIEdit.choices,default=AIEdit.AUTO)
    publish_asap=models.BooleanField(default=False,db_index=True)
    publish_asap_evidence=models.TextField(blank=True)
    publish_asap_not_before=models.DateField(null=True,blank=True)
    publish_asap_expected_slot=models.DateTimeField(null=True,blank=True)
    publish_asap_reason=models.TextField(blank=True)
    # The day and hour Gustavo asked for («publícalo mañana a las 10»), from the literal fragment in publish_at_evidence.
    publish_at=models.DateTimeField(null=True,blank=True)
    publish_at_evidence=models.TextField(blank=True)
    # The date he asked for cannot be kept (past, inside the veto notice, outside the window, beyond 14 days, unclear or
    # a day that already has two posts): {state: problem|next_free|discarded|expired, problem, asked, at, answered_at,
    # notified}. A problem is a Bandeja card at once (urgente.py). Older rows may say pending|same_day (flow before 14/11).
    day_request=models.JSONField(default=dict,blank=True)
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
    def save(self,*args,**kwargs):
        _whose_upload(self);super().save(*args,**kwargs)
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
    category=models.CharField(max_length=12,default='posts',choices=[('posts','Posts'),('perfil','Perfil')],db_index=True)
    profile_edit=models.BooleanField(default=False)
    profile_role=models.CharField(max_length=2,blank=True,choices=[('','Sin asignar'),('01','Pose y sonrisa'),('02','Cuerpo'),('03','Identidad')])
    profile_version=models.PositiveIntegerField(default=1)
    profile_consent=models.JSONField(default=dict,blank=True)
    ai_edit=models.CharField(max_length=4,choices=AIEdit.choices,default=AIEdit.AUTO)
    instruction=models.TextField(blank=True)
    instruction_kind=models.CharField(max_length=12,blank=True)
    state=models.CharField(max_length=12,choices=State.choices,default=State.UNUSED,db_index=True)
    chosen_piece=models.ForeignKey(EditorialPiece,on_delete=models.SET_NULL,null=True,blank=True,related_name='gallery_photos')
    chosen_for=models.DateField(null=True,blank=True)
    published_at=models.DateTimeField(null=True,blank=True)
    capture=models.ForeignKey(Capture,on_delete=models.SET_NULL,null=True,blank=True,related_name='photos')
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,related_name='+')
    # Whose photo (organizaciones, phase 4): only her pieces may use it. Her capture's member, else whoever uploaded it.
    member=models.ForeignKey(Member,on_delete=models.PROTECT,null=True,blank=True,related_name='photos')
    created_at=models.DateTimeField(default=timezone.now,db_index=True)
    class Meta:ordering=['-created_at']
    def __str__(self):return f'{self.id} · {self.get_state_display()}'
    def save(self,*args,**kwargs):
        if self.member_id is None and self._state.adding and self.capture_id and self.capture.member_id:self.member_id=self.capture.member_id
        _whose_upload(self);super().save(*args,**kwargs)

    @property
    def allow_ai_edit(self):return self.ai_edit!=AIEdit.NO
    @allow_ai_edit.setter
    def allow_ai_edit(self,value):self.ai_edit=AIEdit.AUTO if value else AIEdit.NO


class PieceImage(models.Model):
    """Frozen image and permission snapshot. Original files stay owned by GalleryPhoto."""
    profile_exclusive=models.BooleanField(default=False)
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    piece=models.ForeignKey(EditorialPiece,on_delete=models.CASCADE,related_name='images')
    source_photo=models.ForeignKey(GalleryPhoto,on_delete=models.SET_NULL,null=True,blank=True,related_name='uses')
    position=models.PositiveSmallIntegerField(default=1)
    kind=models.CharField(max_length=16)
    image=models.FileField(upload_to='piezas/imagenes',max_length=200)
    mime=models.CharField(max_length=40,default='image/png')
    width=models.PositiveIntegerField()
    height=models.PositiveIntegerField()
    sha256=models.CharField(max_length=64)
    alt=models.TextField()
    edited=models.BooleanField(default=False)  # pixels made by the image model (checked by vision, IMG-10)
    cropped=models.BooleanField(default=False)  # his photo cut to LinkedIn's size by code, no model (IMG-14); data.crop
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
    """conversaciones_inbox (conversaciones.py): one LinkedIn 1to1 chat read through the directo account, read-only. The team
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
    # Whose week (organizaciones, phase 4): one per member and week; without members, one per week.
    member=models.ForeignKey(Member,on_delete=models.PROTECT,null=True,blank=True,related_name='weekly_summaries')
    week_start=models.DateField()
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
    class Meta:
        ordering=['-week_start']
        constraints=[models.UniqueConstraint(fields=['member','week_start'],name='one_summary_per_member_week',nulls_distinct=False)]
    def __str__(self):return f'{self.week_start} · {self.get_state_display()}'
    def save(self,*args,**kwargs):
        _her_content(self);super().save(*args,**kwargs)


class WeeklyPlan(models.Model):
    """director_editorial (estrategia.py): the GASP type of each day of one local ISO week and, once planned, its idea
    with the reader's need and the audience signal behind it. One per week; Gustavo's changes are kept in `history`."""
    class State(models.TextChoices):
        TEMPLATE='estructura','Solo la estructura'
        PLANNED='planeada','Planeada'
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    # Whose week (organizaciones, phase 4): her own plan from the organization's template and pillars.
    member=models.ForeignKey(Member,on_delete=models.PROTECT,null=True,blank=True,related_name='weekly_plans')
    week_start=models.DateField()
    state=models.CharField(max_length=12,choices=State.choices,default=State.TEMPLATE)
    # One per day, Monday first: {date, type, type_reason, idea, reason, pillar, modality, approach, format, reader,
    # reader_need, audience_evidence, evidence_ok, pain, state, owner_edited, piece_id}.
    slots=models.JSONField(default=list,blank=True)
    summary=models.TextField(blank=True)
    warnings=models.JSONField(default=list,blank=True)
    # The audience signals the plan read and used: what the weekly summary reports as what moved the week.
    signals=models.JSONField(default=dict,blank=True)
    # Planned ideas displaced by a type change or by an idea of Gustavo: kept for later weeks.
    kept_ideas=models.JSONField(default=list,blank=True)
    history=models.JSONField(default=list,blank=True)
    usage=models.JSONField(default=list,blank=True)
    cost_usd=models.DecimalField(max_digits=12,decimal_places=6,null=True,blank=True)
    origin_job=models.CharField(max_length=40,blank=True)
    created_at=models.DateTimeField(default=timezone.now)
    updated_at=models.DateTimeField(auto_now=True)
    class Meta:
        ordering=['-week_start']
        constraints=[models.UniqueConstraint(fields=['member','week_start'],name='one_plan_per_member_week',nulls_distinct=False)]
    def __str__(self):return f'{self.week_start} · {self.get_state_display()}'
    def save(self,*args,**kwargs):
        _her_content(self);super().save(*args,**kwargs)


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


class CommunityStudy(models.Model):
    """Monthly community artifact. Identifiable sources never enter the reader packet."""
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    account=models.ForeignKey(ConnectorAccount,on_delete=models.PROTECT)
    period=models.DateField()
    version=models.PositiveIntegerField(default=1)
    window_start=models.DateTimeField()
    window_end=models.DateTimeField()
    created_at=models.DateTimeField(default=timezone.now)
    completed_at=models.DateTimeField(null=True,blank=True)
    expires_at=models.DateTimeField()
    state=models.CharField(max_length=24,default='building')
    positioning_version=models.CharField(max_length=100)
    selection=models.JSONField(default=list)
    coverage=models.JSONField(default=dict)
    summary=models.JSONField(default=dict)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['account','period','version'],name='unique_community_version')]


class CommunitySource(models.Model):
    """Public-only derived layer; retired rows retain just ids, hashes and dates."""
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    study=models.ForeignKey(CommunityStudy,on_delete=models.CASCADE,related_name='sources')
    person=models.ForeignKey(EvidencePerson,on_delete=models.PROTECT)
    key=models.CharField(max_length=64)
    target=models.CharField(max_length=64)
    kind=models.CharField(max_length=24)
    url=models.TextField(blank=True)
    text=models.TextField(blank=True)
    event_at=models.DateTimeField(null=True,blank=True)
    observed_at=models.DateTimeField(default=timezone.now)
    expires_at=models.DateTimeField()
    retired_at=models.DateTimeField(null=True,blank=True)
    analysis=models.JSONField(default=dict)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['study','person','key'],name='unique_community_source')]


class CommunityWithdrawal(models.Model):
    """Non-content tombstone: prevents recollection without touching operational data."""
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    account=models.ForeignKey(ConnectorAccount,on_delete=models.PROTECT)
    key=models.CharField(max_length=64)
    created_at=models.DateTimeField(default=timezone.now)
    reason=models.CharField(max_length=24)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['account','key'],name='unique_community_withdrawal')]


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


class ProfileSchedule(models.Model):
    """Calendar anchor is independent of on-demand requests and human application."""
    owner=models.OneToOneField(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    anchor=models.DateField()
    full_period=models.CharField(max_length=10,blank=True)
    monthly_period=models.CharField(max_length=7,blank=True)


class ProfileProposal(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    owner=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    key=models.CharField(max_length=160,unique=True)
    mode=models.CharField(max_length=12,default='full')
    triggers=models.JSONField(default=list,blank=True)
    version=models.PositiveIntegerField(default=1)
    revision=models.PositiveIntegerField(default=1)
    state=models.CharField(max_length=16,default='queued',db_index=True)
    sections=models.JSONField(default=list,blank=True)
    context=models.JSONField(default=dict,blank=True)
    references=models.JSONField(default=list,blank=True)
    history=models.JSONField(default=list,blank=True)
    findings=models.JSONField(default=list,blank=True)
    download_tickets=models.JSONField(default=dict,blank=True)
    photo_choice=models.CharField(max_length=1,blank=True)
    cycle=models.ForeignKey(CycleLedger,on_delete=models.PROTECT,null=True,blank=True)
    postponed_until=models.DateTimeField(null=True,blank=True)
    created_at=models.DateTimeField(default=timezone.now)
    updated_at=models.DateTimeField(auto_now=True)
    class Meta:ordering=['-created_at']

    @transaction.atomic
    def save(self,*args,**kwargs):
        super().save(*args,**kwargs)
        if self.state in ('superseded','cancelled'):
            from .preguntas import withdraw_origin
            withdraw_origin(f'perfil:{self.id}',reason='Propuesta '+self.state)


def profile_asset_path(instance,filename):return _media_name('perfil',filename)


class ProfileAsset(models.Model):
    """Always private, never a GalleryPhoto/PieceImage or a publication candidate."""
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    proposal=models.ForeignKey(ProfileProposal,on_delete=models.CASCADE,related_name='assets')
    version=models.PositiveIntegerField()
    kind=models.CharField(max_length=24)
    image=models.FileField(upload_to=profile_asset_path,max_length=200)
    sha256=models.CharField(max_length=64)
    width=models.PositiveIntegerField()
    height=models.PositiveIntegerField()
    review=models.JSONField(default=dict,blank=True)
    provenance=models.JSONField(default=dict,blank=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['proposal','version','kind'],name='profile_asset_version_kind')]


# ---------------------------------------------------------------------------
# Library catalog (catalogo.py): course units by shelf and tier, versioned. The content is private course structure:
# it arrives through `manage.py catalogo cargar` from a private file, never from this public repository.

class LibraryCatalog(models.Model):
    version=models.CharField(max_length=40,primary_key=True)
    method=models.TextField(blank=True)
    sha256=models.CharField(max_length=64)
    loaded_at=models.DateTimeField(default=timezone.now)
    class Meta:ordering=['-loaded_at']


class CatalogEntry(models.Model):
    """One unit in one shelf of a catalog version. It points at the unit and never changes it."""
    class Tier(models.TextChoices):
        CORE='nucleo','Núcleo: se carga en cada llamada'
        CONSULT='consulta','Consulta: se busca cuando la tarea lo pide'
        REFERENCE='referencia','Referencia: se guarda, no se carga'
    catalog=models.ForeignKey(LibraryCatalog,on_delete=models.CASCADE,related_name='entries')
    unit_id=models.CharField(max_length=40)
    shelf=models.CharField(max_length=20)
    home=models.BooleanField(default=False)
    tier=models.CharField(max_length=10,choices=Tier.choices)
    core_rank=models.PositiveSmallIntegerField(null=True,blank=True)
    score=models.FloatField(null=True,blank=True)
    reason=models.CharField(max_length=10,blank=True)
    duplicate_of=models.CharField(max_length=40,blank=True)
    class Meta:
        ordering=['catalog','shelf','core_rank','unit_id']
        constraints=[models.UniqueConstraint(fields=['catalog','unit_id','shelf'],name='catalog_entry_unit_shelf')]
        indexes=[models.Index(fields=['catalog','shelf','tier'],name='catalog_entry_shelf_tier')]


class ActiveShelf(models.Model):
    """The catalog version an agent's shelf loads its core from. No row: the agent keeps its fixed list in code."""
    shelf=models.CharField(max_length=20,primary_key=True)
    catalog=models.ForeignKey(LibraryCatalog,on_delete=models.PROTECT,related_name='active_shelves')
    activated_at=models.DateTimeField(default=timezone.now)
    class Meta:ordering=['shelf']


# ---------------------------------------------------------------------------
# Monthly review (revision_mensual.py): once a month analista_barrio_resultados proposes at most three strategy changes
# from the month's data. Gustavo approves, edits or rejects each one; only an approved change enters the orientation.

class MonthlyReview(models.Model):
    """One per month (month_start is its first day): the figures the analyst read and the validated report."""
    class State(models.TextChoices):
        NEW='nuevo','Nueva'
        SEEN='visto','Vista'
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    # Whose month (organizaciones, phase 4): one per member and month; its changes go to her orientation.
    member=models.ForeignKey(Member,on_delete=models.PROTECT,null=True,blank=True,related_name='monthly_reviews')
    month_start=models.DateField()
    # The inputs, as the analyst read them: proof of where each figure of the report came from.
    stats=models.JSONField(default=dict,blank=True)
    # {titular, metodo, lo_que_paso, lo_que_funciono, lo_que_no, no_concluyente, cambios_previos, cambios, validacion, …}.
    analysis=models.JSONField(default=dict,blank=True)
    state=models.CharField(max_length=12,choices=State.choices,default=State.NEW,db_index=True)
    # Fewer than four weeks of the month had measured posts: a hint, not a conclusion.
    partial=models.BooleanField(default=False)
    usage=models.JSONField(default=dict,blank=True)
    cost_usd=models.DecimalField(max_digits=12,decimal_places=6,null=True,blank=True)
    origin_job=models.CharField(max_length=40,blank=True)
    created_at=models.DateTimeField(default=timezone.now)
    updated_at=models.DateTimeField(auto_now=True)
    class Meta:
        ordering=['-month_start']
        constraints=[models.UniqueConstraint(fields=['member','month_start'],name='one_review_per_member_month',nulls_distinct=False)]
    def __str__(self):return f'{self.month_start} · {self.get_state_display()}'
    def save(self,*args,**kwargs):
        _her_content(self);super().save(*args,**kwargs)


class StrategyChange(models.Model):
    """One proposed change of a monthly review: a sentence for the orientation, the figure behind it and how it will be
    measured. Approving appends it to the orientation under a marker line that «Revertir» finds again."""
    class State(models.TextChoices):
        PROPOSED='propuesto','Propuesto'
        APPROVED='aprobado','Aprobado'
        REJECTED='rechazado','Rechazado'
        REVERTED='revertido','Revertido'
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    review=models.ForeignKey(MonthlyReview,on_delete=models.CASCADE,related_name='changes')
    position=models.PositiveSmallIntegerField(default=0)
    title=models.CharField(max_length=120)
    # The sentence that would enter the orientation, written as an instruction to the team.
    proposal=models.TextField()
    reason=models.TextField(blank=True)
    # [{cifra, comparado_con, refs: [piece or action ids]}].
    evidence=models.JSONField(default=list,blank=True)
    # What should improve and how it will be measured next month.
    expected=models.TextField(blank=True)
    metric=models.CharField(max_length=40)
    # {metrica, valor, mes, desde, hasta}: the metric when it was proposed.
    baseline=models.JSONField(default=dict,blank=True)
    state=models.CharField(max_length=12,choices=State.choices,default=State.PROPOSED,db_index=True)
    # What was applied: the proposal, or Gustavo's edit of it.
    final_text=models.TextField(blank=True)
    decided_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,blank=True,related_name='+')
    decided_at=models.DateTimeField(null=True,blank=True)
    decision_note=models.TextField(blank=True)
    # The orientation right before the approval (the record of what it was; «Revertir» removes only the addition).
    orientation_before=models.TextField(blank=True)
    reverted_at=models.DateTimeField(null=True,blank=True)
    # Written by the next review: {veredicto: se_conserva|sin_dato|empeoro, texto, cifra, metrica, antes, despues, …}.
    outcome=models.JSONField(default=dict,blank=True)
    created_at=models.DateTimeField(default=timezone.now)
    updated_at=models.DateTimeField(auto_now=True)
    class Meta:
        ordering=['review','position']
        constraints=[models.UniqueConstraint(fields=['review','position'],name='one_strategy_change_per_position')]
    def __str__(self):return f'{self.title} · {self.get_state_display()}'


# ---------------------------------------------------------------------------
# The buyer's journey (comprador.py; docs/plan-outbound.md «El sistema del comprador»). One record per buyer beside
# Contact, whose Stage stays as it is, and the append-only log of what happened to that person: touches the team made,
# signals the person gave and changes of state. BuyerJourney is a projection: comprador.update() rebuilds it from the
# person's BuyerTouch rows in time order, so the same facts always give the same journey (live or rebuilt).

class BuyerJourney(models.Model):
    class Step(models.TextChoices):
        CHOSEN='elegido','Elegido'
        WARMING='calentando','Calentando'
        INVITED='invitado','Invitado'
        ACCEPTED='acepto','Aceptó'
        MESSAGE_1='mensaje_1','Mensaje 1'
        MESSAGE_2='mensaje_2','Mensaje 2'
        MESSAGE_3='mensaje_3','Mensaje 3'
        MESSAGE_4='mensaje_4','Mensaje 4'
        REPLIED='respondio','Respondió'
        INTERESTED='interesado','Interesado'
        MEETING='reunion','Reunión agendada'
        RESTING='descanso','En descanso; puede volver'
        LEFT='salio','Salió del recorrido'
    class Route(models.TextChoices):
        UNKNOWN='sin_definir','Sin definir'
        COMMENTS='comentarios','Publica: se calienta con comentarios'
        NO_POSTS='sin_posts','No publica'
    class Entry(models.TextChoices):
        OUTBOUND='saliente','El equipo lo eligió'
        INBOUND='entrante','Llegó con su invitación'
    class RestReason(models.TextChoices):
        NO_WARM_REPLY='sin_respuesta_calentamiento','Sin respuesta al calentamiento'
        INVITE_NOT_ACCEPTED='invitacion_no_aceptada','Invitación no aceptada'
        SEQUENCE_NO_REPLY='secuencia_sin_respuesta','Secuencia terminada sin respuesta'
        NOT_NOW='no_es_el_momento','No es el momento'
    class ExitReason(models.TextChoices):
        # Definitive (Gustavo, 17/11/2026): the buyer machine never contacts the person again.
        DO_NOT_CONTACT='pidio_no_contacto','Pidió no ser contactado'
        NOT_INTERESTED='no_le_interesa','No le interesa'
        DISCARDED_BY_GUSTAVO='descartado_por_gustavo','Descartado por Gustavo'
        # Closed by a rule in force today (red.py); something the person does (accepting, writing) reopens it.
        OUT_OF_CRITERIA='fuera_de_criterio','Dejó de cumplir el criterio de comprador'
        INVITATION_CLOSED='invitacion_cerrada','Invitación ignorada o retirada'
        RESTRICTED='perfil_restringido','Perfil restringido'
    class Origin(models.TextChoices):
        LIVE='en_vivo','Registrado al ocurrir'
        REBUILT='reconstruido','Reconstruido desde el historial'
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    contact=models.OneToOneField(Contact,on_delete=models.CASCADE,related_name='buyer_journey')
    entry=models.CharField(max_length=10,choices=Entry.choices,default=Entry.OUTBOUND)
    # BAR-24 (17/11/2026): the level and score (nivel_comprador) the team went after the buyer with, fixed by its first
    # follow or invitation and never overwritten after, so the funnel can compare whether the «por confirmar» accept and
    # answer like the confirmed ones.
    entry_level=models.CharField(max_length=14,blank=True)
    entry_score=models.PositiveSmallIntegerField(null=True,blank=True)
    entry_score_version=models.CharField(max_length=20,blank=True)
    # BAR-25 (NETWORK_PROJECTAPP_BUYER_ENABLED): the buyer's line (projectapp, startup) and, for a ProjectApp buyer, her
    # segment of the three-month test, measured apart in the funnel. They follow the classification until the first
    # follow or invitation, are fixed then, and are set once more only if still empty (a reevaluation that gives a line
    # to a buyer the team already followed before the switch). '' with the switch off.
    line=models.CharField(max_length=12,blank=True,db_index=True)
    segment=models.CharField(max_length=24,blank=True,db_index=True)
    route=models.CharField(max_length=12,choices=Route.choices,default=Route.UNKNOWN)
    step=models.CharField(max_length=12,choices=Step.choices,default=Step.CHOSEN,db_index=True)
    # When something is due for this person (comprador.next_at); null when nothing is scheduled.
    next_at=models.DateTimeField(null=True,blank=True,db_index=True)
    # Retries: the current attempt and every attempt so far, [{numero, desde, angulo, hasta, motivo}].
    attempt=models.PositiveSmallIntegerField(default=1)
    attempts=models.JSONField(default=list,blank=True)
    rest_reason=models.CharField(max_length=30,choices=RestReason.choices,blank=True)
    rest_until=models.DateTimeField(null=True,blank=True)
    exit_reason=models.CharField(max_length=30,choices=ExitReason.choices,blank=True)
    exited_at=models.DateTimeField(null=True,blank=True)
    exit_step=models.CharField(max_length=12,blank=True)  # the step it was in when it left
    # Milestones: the first time each one happened, across attempts (the funnel counts them).
    chosen_at=models.DateTimeField(db_index=True)
    warming_at=models.DateTimeField(null=True,blank=True)
    invited_at=models.DateTimeField(null=True,blank=True)
    invite_note=models.BooleanField(null=True,blank=True)  # the first invitation went with a note; null: no invitation or unknown
    accepted_at=models.DateTimeField(null=True,blank=True)
    first_message_at=models.DateTimeField(null=True,blank=True)
    last_message_at=models.DateTimeField(null=True,blank=True)
    replied_at=models.DateTimeField(null=True,blank=True)
    interested_at=models.DateTimeField(null=True,blank=True)
    meeting_at=models.DateTimeField(null=True,blank=True)
    # Counters. messages_sent and warm_comments belong to the current attempt; comments_before_invite to the first invitation.
    messages_sent=models.PositiveSmallIntegerField(default=0)
    warm_comments=models.PositiveSmallIntegerField(default=0)
    comments_before_invite=models.PositiveSmallIntegerField(default=0)
    visits=models.PositiveSmallIntegerField(default=0)
    # Signals the person gave (direction «entrante»): how many, the latest, and whether one came before the first invitation.
    inbound_signals=models.PositiveIntegerField(default=0)
    last_inbound_at=models.DateTimeField(null=True,blank=True)
    signal_before_invite=models.BooleanField(default=False)
    # Phase 6: the person who pointed to this one after her message 3 («¿no eres la persona indicada?»;
    # secuencia_comprador.link_referral). Null when nobody referred her.
    referred_by=models.ForeignKey('self',on_delete=models.SET_NULL,null=True,blank=True,related_name='referrals')
    # Phase 6 (respuesta_comprador.py): the type of her latest classified reply (interesado, pide_informacion,
    # no_es_el_momento, no_le_interesa, otra_persona, otro); the identifier that travels in her booking link
    # (?metadata[barrio]=…, agenda_calcom matches the Cal.com booking with it); and the date of the booked meeting.
    reply_type=models.CharField(max_length=20,blank=True)
    booking_ref=models.CharField(max_length=24,null=True,blank=True,unique=True)
    meeting_date=models.DateTimeField(null=True,blank=True)
    origin=models.CharField(max_length=12,choices=Origin.choices,default=Origin.LIVE)
    created_at=models.DateTimeField(default=timezone.now)
    updated_at=models.DateTimeField(default=timezone.now)
    class Meta:
        ordering=['-chosen_at']
    def __str__(self):return f'{self.contact} · {self.get_step_display()}'

class BuyerTouch(models.Model):
    """One entry of a buyer's log; never edited nor deleted. `key` names its source (an execution, a comment, a message…)
    so the same fact is recorded once, whether a live hook or the rebuild sees it first."""
    class Direction(models.TextChoices):
        OUT='saliente','Lo hizo el equipo o Gustavo'
        IN='entrante','Lo hizo la persona'
        STATE='estado','Cambio de estado del recorrido'
    class Kind(models.TextChoices):
        # estado
        CHOSEN='elegido','Elegido como comprador'
        ROUTE='ruta','Ruta decidida'
        ANGLE='angulo','Ángulo del intento'
        REST='descanso','Pasa a descanso'
        RETRY='reintento','Nuevo intento'
        EXIT='salida','Sale del recorrido'
        REOPENED='reabierto','Vuelve al recorrido'
        ALREADY_CONNECTED='ya_conectados','Ya eran conexión'
        NO_MESSAGE='no_escribirle','Gustavo decidió no escribirle'
        DRAFT='borrador','Borrador preparado o descartado (fase 3)'
        OPPORTUNITY='oportunidad','Oportunidad registrada'
        INTERESTED='interesado','Respuesta con interés'
        REFERRED='referido','Llegó referido por otra persona (su mensaje 3)'
        BRIDGE='puente','Puente por otra persona de su empresa (fase 5)'
        RECHECK='reverificacion','Reverificación de sus señales de compra al terminar un descanso (fase 5)'
        REPLY_CLASSIFIED='respuesta_clasificada','Su respuesta clasificada (fase 6)'
        MEETING_CANCELLED='reunion_cancelada','Reunión cancelada (fase 6)'
        # saliente
        FOLLOW='seguir','Seguir (RED-01)'
        COMMENT='comentario','Comentario en un post suyo (INT-03)'
        REACTION='reaccion','Reacción a un post o comentario suyo (INT-02)'
        THREAD_REPLY='respuesta_hilo','Respuesta a su comentario en un post de Gustavo (INT-04)'
        VISIT='visita','Visita a su perfil'
        INVITATION='invitacion','Invitación (RED-02)'
        ACCEPTED_THEIRS='aceptaste_invitacion','Gustavo aceptó su invitación (RED-04)'
        MESSAGE='mensaje','Mensaje enviado por Gustavo («Hecho, le escribí»)'
        MESSAGE_SEEN='mensaje_visto','Mensaje de Gustavo leído en el inbox'
        REPLY_SENT='respuesta_enviada','Respuesta enviada por Gustavo a lo que ella escribió (fase 6)'
        # entrante
        REPLIED_COMMENT='respondio_comentario','Respondió a un comentario del equipo'
        COMMENTED_POST='comento_post','Comentó en un post de Gustavo'
        REACTED_POST='reacciono_post','Reaccionó a un post de Gustavo'
        FOLLOWED_US='nos_siguio','Siguió a Gustavo'
        INVITED_US='nos_invito','Invitó a Gustavo'
        ACCEPTED_OURS='acepto_invitacion','Aceptó la invitación'
        OPENED_CONVERSATION='abrio_conversacion','Le escribió primero'
        REPLIED_MESSAGE='respondio_mensaje','Respondió un mensaje'
        MEETING='reunion','Agendó una reunión'
        BRIDGE_SIGNAL='senal_puente','Su colega (el puente) aceptó o interactuó'
    class Source(models.TextChoices):
        LIVE='en_vivo','Registrado al ocurrir'
        REBUILT='reconstruido','Reconstruido desde el historial'
        PHASE='fase','Registrado por una fase del recorrido'
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    journey=models.ForeignKey(BuyerJourney,on_delete=models.CASCADE,related_name='touches')
    kind=models.CharField(max_length=24,choices=Kind.choices)
    direction=models.CharField(max_length=10,choices=Direction.choices)
    at=models.DateTimeField(db_index=True)
    key=models.CharField(max_length=200)
    detail=models.JSONField(default=dict,blank=True)
    source=models.CharField(max_length=12,choices=Source.choices,default=Source.LIVE)
    proposal=models.ForeignKey(ActionProposal,on_delete=models.SET_NULL,null=True,blank=True,related_name='+')
    execution=models.ForeignKey(ActionExecution,on_delete=models.SET_NULL,null=True,blank=True,related_name='+')
    post=models.ForeignKey(ObservedPost,on_delete=models.SET_NULL,null=True,blank=True,related_name='+')
    comment=models.ForeignKey(PostComment,on_delete=models.SET_NULL,null=True,blank=True,related_name='+')
    conversation=models.ForeignKey(Conversation,on_delete=models.SET_NULL,null=True,blank=True,related_name='+')
    opportunity=models.ForeignKey(Opportunity,on_delete=models.SET_NULL,null=True,blank=True,related_name='+')
    outcome=models.ForeignKey(ActionOutcome,on_delete=models.SET_NULL,null=True,blank=True,related_name='+')
    created_at=models.DateTimeField(default=timezone.now)
    class Meta:
        ordering=['at','created_at']
        constraints=[models.UniqueConstraint(fields=['journey','key'],name='one_buyer_touch_per_key')]
    def save(self,*args,**kwargs):
        if not self._state.adding:raise ValueError('El registro del comprador solo se añade; no se edita.')
        super().save(*args,**kwargs)
    def delete(self,*args,**kwargs):raise ValueError('El registro del comprador solo se añade; no se borra.')
    def __str__(self):return f'{self.kind} · {self.at:%Y-%m-%d}'

class BuyerDraft(models.Model):
    """A text the team prepared for a buyer (phase 3, mensajes_comprador.py): the first message after the acceptance, which
    Gustavo sends himself from LinkedIn (INB-08: the app never sends one), or the note of an invitation. One decision per
    person, kind, number and attempt, including the decision not to write (sin_borrador) and the reason. Phase 4
    (secuencia_comprador.py) adds messages 2–4 with `number`, cancelled when she replies. It hangs from the Contact, so it
    outlives a rebuilt journey."""
    class Kind(models.TextChoices):
        MESSAGE='mensaje','Mensaje privado (el primero después de aceptar; fase 4: los seguimientos 2 a 4)'
        NOTE='nota','Nota de la invitación'
        REPLY='respuesta','Respuesta a lo que ella escribió (fase 6; `number`: su n-ésima respuesta del intento)'
    class State(models.TextChoices):
        REVIEWING='en_revision','Esperando la revisión del líder'
        READY='listo','Listo: en Tu turno (mensaje) o esperando la invitación (nota)'
        USED='usada','Nota puesta en una invitación'
        SENT='enviado','Enviado (Gustavo le escribió o la nota salió con la invitación)'
        NOT_SENT='no_enviado','No enviado (Gustavo decidió no escribirle o la invitación salió sin la nota)'
        DISCARDED='descartado','Descartado por las reglas fijas o el líder'
        NONE='sin_borrador','Sin borrador: nada real que citar, sin cupo de notas o ya hay conversación'
        EXPIRED='caducado','Caducado sin usar'
        REPLACED='reemplazado','Reemplazado: ya hubo otro primer mensaje o la persona ya no está en ese paso'
        CANCELLED='cancelado','Cancelado: la persona respondió y la secuencia se detuvo'
    class StoppedBy(models.TextChoices):
        RULES='reglas','Reglas fijas'
        JUDGE='juez','Líder (Jev)'
        FACT='hecho','Nada real que citar'
        QUOTA='cupo','Sin cupo de notas este mes'
        CONVERSATION='conversacion','Ya hay una conversación'
        LINK='agenda','Sin enlace de agenda (CALCOM_BOOKING_URL vacío)'
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    contact=models.ForeignKey(Contact,on_delete=models.CASCADE,related_name='buyer_drafts')
    kind=models.CharField(max_length=12,choices=Kind.choices)
    number=models.PositiveSmallIntegerField(default=1)  # 1: the first message; phase 4: the follow-ups 2–4
    attempt=models.PositiveSmallIntegerField(default=1)  # the journey's attempt it belongs to
    state=models.CharField(max_length=12,choices=State.choices,db_index=True)
    stopped_by=models.CharField(max_length=12,choices=StoppedBy.choices,blank=True)
    reason=models.TextField(blank=True)  # why it was written (its fact) or why it stopped
    text=models.TextField(blank=True)
    language=models.CharField(max_length=10,blank=True)
    # The fact the first line (or the note) cites: {id, tipo, texto, fecha, fuente…}; every fact it was given in `inputs`.
    anchor=models.JSONField(default=dict,blank=True)
    inputs=models.JSONField(default=dict,blank=True)
    citations=models.JSONField(default=list,blank=True)
    issues=models.JSONField(default=list,blank=True)  # the fixed rules it broke (after the single redraft)
    review=models.JSONField(default=dict,blank=True)  # the lead's verdict, with the course grounding it read
    # Which voice wrote it (phase 3, voz.meta): {'tipo': 'provisional'|'confirmada'|'inicial', 'version': n}. A draft in the
    # provisional voice of a member who has none yet is marked so (phase 5 shows it, phase 7 keeps her in approval).
    voice=models.JSONField(default=dict,blank=True)
    model=models.CharField(max_length=100,blank=True)
    show_at=models.DateTimeField(null=True,blank=True)  # a message's card never shows the minute she accepted
    proposal=models.ForeignKey(ActionProposal,on_delete=models.SET_NULL,null=True,blank=True,related_name='buyer_drafts')
    created_at=models.DateTimeField(default=timezone.now)
    decided_at=models.DateTimeField(null=True,blank=True)  # ready, discarded or not written
    closed_at=models.DateTimeField(null=True,blank=True)  # sent, not sent, expired or replaced
    closed_note=models.TextField(blank=True)
    class Meta:
        ordering=['-created_at']
        constraints=[models.UniqueConstraint(fields=['contact','kind','number','attempt'],name='one_buyer_draft_per_step')]
    def __str__(self):return f'{self.contact} · {self.kind} {self.number} · {self.state}'

class MeetingBooking(models.Model):
    """Phase 6 (agenda_calcom.py): a meeting a buyer booked through Gustavo's Cal.com link, as its signed webhook told it
    (BOOKING_CREATED, BOOKING_RESCHEDULED, BOOKING_CANCELLED), or that Gustavo marked by hand («Agendó»). The body is only
    trusted to match it with a journey: the identifier the link carries (metadata[barrio] → `ref`), else the attendee's
    email or name against what Barrio knows; nothing matched stays «sin_emparejar» for Gustavo to associate."""
    class State(models.TextChoices):
        BOOKED='agendada','Agendada'
        RESCHEDULED='reprogramada','Reprogramada: la reemplaza otra reserva'
        CANCELLED='cancelada','Cancelada'
        DISCARDED='descartada','Descartada por Gustavo (no era de un comprador)'
    class MatchedBy(models.TextChoices):
        LINK='enlace','Identificador del enlace'
        EMAIL='correo','Correo que ella escribió en la conversación'
        NAME='nombre','Nombre exacto, una sola candidata'
        PREVIOUS='reserva_anterior','La reserva que reprograma'
        GUSTAVO='gustavo','Gustavo la asoció'
        MANUAL='manual','«Agendó» a mano'
        NONE='sin_emparejar','Sin emparejar'
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    provider=models.CharField(max_length=20,default='calcom')
    uid=models.CharField(max_length=200,unique=True)  # Cal.com's booking uid; «manual:<draft>» for «Agendó»
    previous_uid=models.CharField(max_length=200,blank=True)  # the booking it reschedules (payload.rescheduleUid)
    state=models.CharField(max_length=14,choices=State.choices,default=State.BOOKED,db_index=True)
    start_at=models.DateTimeField(null=True,blank=True)
    end_at=models.DateTimeField(null=True,blank=True)
    attendee_name=models.CharField(max_length=200,blank=True)
    attendee_email=models.CharField(max_length=254,blank=True)
    ref=models.CharField(max_length=40,blank=True)  # what travelled in the link (metadata[barrio])
    journey=models.ForeignKey(BuyerJourney,on_delete=models.SET_NULL,null=True,blank=True,related_name='bookings')
    contact=models.ForeignKey(Contact,on_delete=models.SET_NULL,null=True,blank=True,related_name='bookings')
    matched_by=models.CharField(max_length=16,choices=MatchedBy.choices,default=MatchedBy.NONE)
    matched_at=models.DateTimeField(null=True,blank=True)
    events=models.JSONField(default=list,blank=True)  # [{evento, at, cuerpo_sha256}] each webhook that touched it
    created_at=models.DateTimeField(default=timezone.now)
    updated_at=models.DateTimeField(default=timezone.now)
    class Meta:
        ordering=['-created_at']
    def __str__(self):return f'{self.uid} · {self.state}'

class LeadHandoff(models.Model):
    """Phase 6 (entrega_lead.py): the lead handed to the sales machine once the meeting is booked, source-neutral (today
    only «linkedin»): who and the company, the journey (entry signal, touches, messages sent, the one she replied to, the
    bridge or the referral), the conversation in three lines, the meeting and what the team knows of the business with
    its sources. No qualification: that is the sales machine's. A model and not a JSON on the journey: the sales machine
    reads every source the same way and by state, and the opportunity, the conversation and the journey hang from it.
    Only Gustavo creates the opportunity (PRS-09): «Crear la oportunidad» confirms it with one tap."""
    class Source(models.TextChoices):
        LINKEDIN='linkedin','LinkedIn (máquina del comprador)'
    class State(models.TextChoices):
        READY='lista','Lista: espera que Gustavo cree o vincule la oportunidad'
        CONFIRMED='confirmada','Oportunidad creada o vinculada'
        CANCELLED='cancelada','La reunión se canceló'
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    key=models.CharField(max_length=120,unique=True)  # «linkedin:<journey>:<attempt>»: one handoff per journey attempt
    source=models.CharField(max_length=20,choices=Source.choices,default=Source.LINKEDIN)
    state=models.CharField(max_length=12,choices=State.choices,default=State.READY,db_index=True)
    contact=models.ForeignKey(Contact,on_delete=models.SET_NULL,null=True,blank=True,related_name='handoffs')
    journey=models.ForeignKey(BuyerJourney,on_delete=models.SET_NULL,null=True,blank=True,related_name='handoffs')
    booking=models.ForeignKey(MeetingBooking,on_delete=models.SET_NULL,null=True,blank=True,related_name='handoffs')
    conversation=models.ForeignKey(Conversation,on_delete=models.SET_NULL,null=True,blank=True,related_name='handoffs')
    opportunity=models.ForeignKey(Opportunity,on_delete=models.SET_NULL,null=True,blank=True,related_name='handoffs')
    meeting_at=models.DateTimeField(null=True,blank=True)
    data=models.JSONField(default=dict,blank=True)
    created_at=models.DateTimeField(default=timezone.now)
    updated_at=models.DateTimeField(default=timezone.now)
    confirmed_at=models.DateTimeField(null=True,blank=True)
    class Meta:
        ordering=['-created_at']
    def __str__(self):return f'{self.source} · {self.contact} · {self.state}'
