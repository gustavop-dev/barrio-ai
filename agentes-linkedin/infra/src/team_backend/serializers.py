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
