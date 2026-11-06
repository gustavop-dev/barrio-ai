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
