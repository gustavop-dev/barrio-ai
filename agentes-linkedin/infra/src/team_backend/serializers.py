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
from .models import ConnectorAccount,Referent,ObservedPost,ActionProposal,ActionExecution

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
    class Meta:
        model=Referent
        fields=['id','account_id','public_identifier','provider_user_id','display_name','profile_url','reason','active','created_at','last_observed_at']

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
    capability=serializers.ChoiceField(choices=ActionProposal.Capability.choices)
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

class ActionOutput(serializers.ModelSerializer):
    execution=serializers.SerializerMethodField()
    post=PostOutput(read_only=True)
    def get_execution(self,obj):
        execution=getattr(obj,'execution',None) if hasattr(obj,'execution') else None
        return ExecutionOutput(execution).data if execution else None
    class Meta:
        model=ActionProposal
        fields=['id','account_id','post','capability','payload','payload_hash','version','previous_id','rationale','citations',
                'risks','source','origin_job','model','state','created_at','approved_hash','decided_by_id','decided_at',
                'decision_note','execution']
