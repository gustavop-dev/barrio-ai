from rest_framework.permissions import BasePermission
from rest_framework.exceptions import PermissionDenied

class KnowledgeAccess(BasePermission):
    def has_permission(self,request,view):
        return bool(request.user.is_authenticated and request.user.has_perm('team_backend.access_knowledge'))

def require(user,codename):
    if not user.has_perm('team_backend.'+codename):raise PermissionDenied('No tienes permiso para esta operación')
