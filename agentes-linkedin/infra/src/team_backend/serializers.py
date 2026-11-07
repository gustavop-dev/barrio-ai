from django.utils import timezone
from rest_framework import serializers
from .models import Job,KnowledgeUnit,AuditEvent

class UTF8CharField(serializers.CharField):
    def to_internal_value(self,data):
        value=super().to_internal_value(data)
        try:value.encode('utf-8')
        except UnicodeEncodeError:raise serializers.ValidationError('Texto Unicode inválido') from None
        return value

class SearchInput(serializers.Serializer):
    query=UTF8CharField(max_length=6000)
    agent=serializers.ChoiceField(choices=['posicionamiento','perfil'],required=False,allow_null=True)
    limit=serializers.IntegerField(min_value=1,max_value=20,default=6)
    mode=serializers.ChoiceField(choices=['lexical','hybrid'],default='lexical')

class RunInput(serializers.Serializer):
    agent=serializers.ChoiceField(choices=['posicionamiento','perfil'])
    task=UTF8CharField(max_length=6000)
    execute=serializers.BooleanField(default=False)
    mode=serializers.ChoiceField(choices=['lexical','hybrid'],default='lexical')
    request_id=serializers.UUIDField(required=False)

class JobOutput(serializers.ModelSerializer):
    status=serializers.CharField(source='state',read_only=True)
    class Meta:
        model=Job
        fields=['id','owner_id','agent','task','execute','mode','status','result_status','error','created_at','started_at','finished_at']

class UnitOutput(serializers.ModelSerializer):
    class Meta:
        model=KnowledgeUnit
        fields=['id','session','title','metadata','sha256']

class ProposalInput(serializers.Serializer):
    namespace=serializers.ChoiceField(choices=['user','working'])
    key=UTF8CharField(max_length=200)
    value=serializers.JSONField()
    evidence=UTF8CharField(max_length=2000)
    expected_version=serializers.IntegerField(min_value=0,default=0)
    def validate_value(self,value):
        import json
        raw=json.dumps(value,ensure_ascii=False)
        try:raw.encode('utf-8')
        except UnicodeEncodeError:raise serializers.ValidationError('Texto Unicode inválido') from None
        if len(raw)>16000 or '\\u0000' in raw:raise serializers.ValidationError('Valor demasiado grande o contiene NUL')
        return value

class ConfirmationInput(serializers.Serializer):
    expected_version=serializers.IntegerField(min_value=1)

class AuditOutput(serializers.ModelSerializer):
    class Meta:
        model=AuditEvent
        fields=['id','actor_id','action','target','request_id','metadata','created_at']


# --------------------------------------------------------------------------- account operator
from .models import OPEN_ACTION_STATES,ConnectorAccount,Contact,Referent,ObservedPost,ActionProposal,ActionExecution

class AccountInput(serializers.Serializer):
    provider=serializers.ChoiceField(choices=ConnectorAccount.Provider.choices)
    external_account_id=UTF8CharField(max_length=120)
    label=UTF8CharField(max_length=120)

class AccountOutput(serializers.ModelSerializer):
    class Meta:
        model=ConnectorAccount
        fields=['id','provider','external_account_id','label','status','is_locked','paused','paused_reason','last_checked_at','created_at']

class PauseInput(serializers.Serializer):
    paused=serializers.BooleanField()
    reason=UTF8CharField(max_length=500,required=False,allow_blank=True,default='')

class ReferentInput(serializers.Serializer):
    account=serializers.UUIDField()
    identifier=UTF8CharField(max_length=300)
    reason=UTF8CharField(max_length=1000)

class ReferentOutput(serializers.ModelSerializer):
    contacts_count=serializers.SerializerMethodField()
    def get_contacts_count(self,obj):
        """People of the neighborhood discovered in this referent's posts."""
        posts=[str(pid) for pid in obj.posts.values_list('id',flat=True)]
        return Contact.objects.filter(evidence__post_id__in=posts).count() if posts else 0
    class Meta:
        model=Referent
        fields=['id','account_id','public_identifier','provider_user_id','display_name','profile_url','reason','active','created_at',
                'last_observed_at','contacts_count']

class ReferentPatch(serializers.Serializer):
    active=serializers.BooleanField(required=False)
    reason=serializers.CharField(required=False,max_length=2000)

class ObserveInput(serializers.Serializer):
    account=serializers.UUIDField()
    referents=serializers.ListField(child=serializers.UUIDField(),required=False,max_length=50)
    limit=serializers.IntegerField(min_value=1,max_value=20,default=5)
    request_id=serializers.UUIDField(required=False)

class PostOutput(serializers.ModelSerializer):
    class Meta:
        model=ObservedPost
        fields=['id','account_id','referent_id','provider_post_id','share_url','author_name','author_public_identifier',
                'text','posted_at','comments_count','reactions_count','is_repost','observed_at']

class OptionalRequestInput(serializers.Serializer):
    request_id=serializers.UUIDField(required=False)

class ActionInput(serializers.Serializer):
    post=serializers.UUIDField()
    # Own publications (CONT-09) are proposed by the editorial circuit, never on someone else's post.
    capability=serializers.ChoiceField(choices=[c for c in ActionProposal.Capability.choices if c[0]!='CONT-09'])
    payload=serializers.JSONField()
    rationale=UTF8CharField(max_length=4000,required=False,allow_blank=True,default='')

class ReviseInput(serializers.Serializer):
    payload=serializers.JSONField()
    note=UTF8CharField(max_length=2000,required=False,allow_blank=True,default='')

class DecisionInput(serializers.Serializer):
    expected_hash=serializers.RegexField(r'^[0-9a-f]{64}$',required=False)
    note=UTF8CharField(max_length=2000,required=False,allow_blank=True,default='')

class ResolveInput(serializers.Serializer):
    outcome=serializers.ChoiceField(choices=['confirmed','failed'])
    note=UTF8CharField(max_length=2000)

class ExecutionOutput(serializers.ModelSerializer):
    class Meta:
        model=ActionExecution
        fields=['id','state','provider','started_at','finished_at','external_id','external_url','error_kind','http_status','note','reconciled_at']

class ContactBrief(serializers.ModelSerializer):
    class Meta:
        model=Contact
        fields=['id','display_name','headline','profile_url','public_identifier','network_distance','stage','source','evidence','classification']

class ContactOutput(serializers.ModelSerializer):
    """Personas: the contact, its derived stage (an open opportunity shows as «Oportunidad»), the next step and who
    it depends on, and Gustavo's notes."""
    open_action=serializers.SerializerMethodField()
    opportunity=serializers.SerializerMethodField()
    display_stage=serializers.SerializerMethodField()
    next_step=serializers.SerializerMethodField()
    your_turn=serializers.SerializerMethodField()
    last_event=serializers.SerializerMethodField()
    conversation=serializers.SerializerMethodField()
    def _conversation(self,obj):
        if not hasattr(obj,'_conversation_cache'):
            from . import conversaciones
            obj._conversation_cache=conversaciones.for_contact(obj)
        return obj._conversation_cache
    def _waiting(self,obj):
        from . import conversaciones
        conversation=self._conversation(obj)
        return bool(conversation and conversaciones.enabled() and conversaciones.needs_gustavo(conversation))
    def get_conversation(self,obj):
        from . import conversaciones
        conversation=self._conversation(obj)
        return conversaciones.payload(conversation) if conversation else None
    def _open_action(self,obj):
        if not hasattr(obj,'_open_action_cache'):
            obj._open_action_cache=obj.proposals.filter(state__in=OPEN_ACTION_STATES).order_by('-created_at').first()
        return obj._open_action_cache
    def _opportunity(self,obj):
        if not hasattr(obj,'_opportunity_cache'):
            obj._opportunity_cache=obj.opportunities.exclude(stage__in=['acuerdo','sin_acuerdo']).order_by('-updated_at').first()
        return obj._opportunity_cache
    def get_open_action(self,obj):
        proposal=self._open_action(obj)
        return {'id':str(proposal.id),'capability':proposal.capability,'state':proposal.state} if proposal else None
    def get_opportunity(self,obj):
        o=self._opportunity(obj)
        return {'id':str(o.id),'stage':o.stage,'stage_label':o.get_stage_display(),'modality':o.modality,'next_action':o.next_action,
                'next_action_at':o.next_action_at} if o else None
    def get_display_stage(self,obj):
        return 'opportunity' if self._opportunity(obj) else obj.stage
    def get_your_turn(self,obj):
        return self._waiting(obj)  # a conversation of this person is a Tu turno card
    def get_last_event(self,obj):
        return obj.history[-1] if obj.history else None
    def get_next_step(self,obj):
        from . import red
        o=self._opportunity(obj);action=self._open_action(obj)
        if self._waiting(obj):return {'owner':'gustavo','text':'Te toca: responder su mensaje','at':None}
        if o:return {'owner':'gustavo','text':f'Oportunidad: {o.get_stage_display()}'+(f' · {o.next_action}' if o.next_action else ''),'at':o.next_action_at}
        if action:
            labels={'RED-01':'seguirla','RED-02':'invitarla sin nota','RED-04':'aceptar su invitación'}
            return {'owner':'equipo','text':f'El equipo va a {labels.get(action.capability,action.capability)}','at':None,
                    'action':{'id':str(action.id),'capability':action.capability,'state':action.state}}
        stage=obj.stage
        if stage=='candidate':return {'owner':'equipo','text':'El equipo la clasificará','at':None}
        if stage=='fit':return {'owner':'equipo','text':'El equipo la seguirá','at':None}
        if stage=='followed' and obj.followed_at:
            blocked,reason=red.invites_blocked()
            when=obj.followed_at+red.invite_after()
            return {'owner':'equipo','text':reason if blocked else 'El equipo la invitará cuando termine la espera','at':when}
        if stage=='invited':
            days=(timezone.now()-obj.invited_at).days if obj.invited_at else None
            return {'owner':'equipo','text':'Esperando que acepte la invitación'+(f' (enviada hace {days} días)' if days is not None else ''),'at':None}
        if stage=='incoming':
            fit=(obj.classification or {}).get('fit')
            return {'owner':'equipo','text':'Se aceptará su invitación' if fit else ('Su invitación queda pendiente: no encaja' if obj.classification else 'El equipo la clasificará'),'at':None}
        if stage=='connected':return {'owner':None,'text':'Conectados','at':None}
        if stage=='closed':return {'owner':None,'text':'Invitación ignorada o retirada; no se reinvita','at':None}
        return {'owner':None,'text':'Descartada; no se volverá a proponer','at':None}
    class Meta:
        model=Contact
        fields=['id','account_id','provider_user_id','public_identifier','display_name','headline','profile_url','location','source',
                'evidence','network_distance','is_following','stage','display_stage','classification','history','notes','followed_at',
                'invited_at','connected_at','discovered_at','updated_at','open_action','opportunity','next_step','your_turn','last_event',
                'conversation']

class NoteInput(serializers.Serializer):
    text=serializers.CharField(max_length=4000)

class DiscardInput(serializers.Serializer):
    note=serializers.CharField(max_length=1000)

class ActionOutput(serializers.ModelSerializer):
    """`post` is null for own content (CONT-09), then `piece_id` and `scheduled_for` identify the target, and for
    network actions (RED-*), then `contact` is the person."""
    execution=serializers.SerializerMethodField()
    post=PostOutput(read_only=True,allow_null=True)
    contact=ContactBrief(read_only=True,allow_null=True)
    scheduled_for=serializers.SerializerMethodField()
    def get_execution(self,obj):
        execution=getattr(obj,'execution',None) if hasattr(obj,'execution') else None
        return ExecutionOutput(execution).data if execution else None
    def get_scheduled_for(self,obj):
        return serializers.DateTimeField().to_representation(obj.piece.scheduled_for) if obj.piece_id else None
    class Meta:
        model=ActionProposal
        fields=['id','account_id','post','piece_id','contact','scheduled_for','capability','payload','payload_hash','version','previous_id','rationale','citations',
                'risks','source','origin_job','model','state','created_at','approved_hash','decided_by_id','decided_at',
                'decision_note','execution']
