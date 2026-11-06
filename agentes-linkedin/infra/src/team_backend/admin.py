from django.contrib import admin
from .models import ApiCredential,Worker,Job,AuditEvent,KnowledgeUnit,SourceEvidence,KnowledgeRun,MemoryEntry,UsageEntry

admin.site.site_header='LinkedIn Team · Administración'
admin.site.site_title='LinkedIn Team'

class ReadOnlyAdmin(admin.ModelAdmin):
    list_per_page=25
    list_defer=()
    def get_queryset(self,request):
        qs=super().get_queryset(request)
        if request.resolver_match and request.resolver_match.url_name.endswith("_changelist"):
            return qs.defer(*self.list_defer)
        return qs
    show_full_result_count=False
    def has_add_permission(self,request):return False
    def has_change_permission(self,request,obj=None):return False
    def has_delete_permission(self,request,obj=None):return False

@admin.register(KnowledgeUnit)
class UnitAdmin(ReadOnlyAdmin):
    list_defer=("original",)
    list_display=['id','session','title','active']
    list_filter=['session','active']
    search_fields=['id','title']

@admin.register(Job)
class JobAdmin(ReadOnlyAdmin):
    def get_queryset(self,request):
        qs=super().get_queryset(request)
        return qs if request.user.has_perm('team_backend.manage_jobs') else qs.filter(owner=request.user)
    list_display=['id','agent','state','owner','execute','created_at','result_status']
    list_filter=['state','agent','execute']
    list_select_related=['owner']

@admin.register(ApiCredential)
class CredentialAdmin(admin.ModelAdmin):
    list_display=['name','user','created_at','expires_at','revoked']
    fields=['name','user','created_at','expires_at','revoked']
    readonly_fields=['name','user','created_at']
    list_select_related=['user']
    def has_add_permission(self,request):return False
    def has_delete_permission(self,request,obj=None):return False

@admin.register(AuditEvent)
class AuditAdmin(ReadOnlyAdmin):
    def has_view_permission(self,request,obj=None):
        return request.user.has_perm('team_backend.manage_jobs') and super().has_view_permission(request,obj)
    list_display=['created_at','actor','action','target','request_id']
    list_select_related=['actor']

@admin.register(UsageEntry)
class UsageAdmin(ReadOnlyAdmin):
    list_display=['id','provider','purpose','status','actual_usd','reserved_usd','created_at']
    list_filter=['provider','status']

@admin.register(MemoryEntry)
class MemoryAdmin(ReadOnlyAdmin):
    list_display=['namespace','key','version','status','author','created_at']
    list_filter=['namespace','status']

@admin.register(KnowledgeRun)
class RunAdmin(ReadOnlyAdmin):
    def get_queryset(self,request):
        qs=super().get_queryset(request)
        if request.user.has_perm('team_backend.manage_jobs'):return qs
        return qs.filter(id__in=Job.objects.filter(owner=request.user).values('id'))
    list_defer=("payload",)
    list_display=['id','agent','status','created_at']
    list_filter=['agent','status']

admin.site.register(Worker,ReadOnlyAdmin)
admin.site.register(SourceEvidence,ReadOnlyAdmin)


# --------------------------------------------------------------------------- account operator
from django.contrib import messages
from . import operador
from .models import ConnectorAccount,Referent,ObservedPost,ActionProposal,ActionExecution

@admin.register(ConnectorAccount)
class ConnectorAccountAdmin(ReadOnlyAdmin):
    list_display=['label','provider','status','is_locked','paused','paused_reason','last_checked_at']
    actions=['pause_writes','resume_writes']
    @admin.action(description='Pausar escrituras en estas cuentas')
    def pause_writes(self,request,queryset):
        for account in queryset:operador.set_paused(request.user,account,True,'Pausa manual desde el panel')
    @admin.action(description='Reanudar escrituras en estas cuentas')
    def resume_writes(self,request,queryset):
        for account in queryset:operador.set_paused(request.user,account,False)

@admin.register(Referent)
class ReferentAdmin(ReadOnlyAdmin):
    list_display=['display_name','public_identifier','active','last_observed_at']
    search_fields=['display_name','public_identifier']

@admin.register(ObservedPost)
class ObservedPostAdmin(ReadOnlyAdmin):
    list_display=['author_name','posted_at','comments_count','reactions_count','observed_at']
    search_fields=['author_name','text']

class ExecutionInline(admin.StackedInline):
    model=ActionExecution
    extra=0;can_delete=False
    readonly_fields=['state','provider','started_at','finished_at','external_id','external_url','error_kind','http_status','note','reconciled_at']
    fields=readonly_fields
    def has_add_permission(self,request,obj=None):return False
    def has_change_permission(self,request,obj=None):return False

@admin.register(ActionProposal)
class ActionProposalAdmin(ReadOnlyAdmin):
    """Approving here approves exactly the version shown (its payload hash)."""
    list_display=['created_at','capability','state','source','post','short_payload','version']
    list_filter=['state','capability','source']
    list_select_related=['post']
    readonly_fields=['capability','state','post','payload','payload_hash','version','rationale','citations','risks','source','model','decision_note']
    fields=readonly_fields
    inlines=[ExecutionInline]
    actions=['approve_selected','reject_selected']
    def short_payload(self,obj):return (obj.payload.get('text') or obj.payload.get('reaction') or '')[:80]
    short_payload.short_description='Contenido'
    @admin.action(description='Aprobar (se ejecutará automáticamente una vez)')
    def approve_selected(self,request,queryset):
        for proposal in queryset:
            try:
                operador.approve(request.user,proposal.id,proposal.payload_hash,'Aprobada desde el panel')
                self.message_user(request,f'Aprobada y en cola: {proposal}',messages.SUCCESS)
            except Exception as exc:self.message_user(request,f'{proposal}: {getattr(exc,"detail",exc)}',messages.ERROR)
    @admin.action(description='Rechazar')
    def reject_selected(self,request,queryset):
        for proposal in queryset:
            try:operador.reject(request.user,proposal.id,'Rechazada desde el panel')
            except Exception as exc:self.message_user(request,f'{proposal}: {getattr(exc,"detail",exc)}',messages.ERROR)

from .models import LinkedInCredential

@admin.register(LinkedInCredential)
class LinkedInCredentialAdmin(ReadOnlyAdmin):
    """The encrypted token is never shown."""
    list_display=['member_urn','member_name','expires_at','connected_at','expiry_alerted_at']
    fields=['account','member_urn','member_name','scopes','expires_at','connected_by','connected_at','expiry_alerted_at']
    readonly_fields=fields
