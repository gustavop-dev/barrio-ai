from django.contrib import admin
from django.urls import path,include
from team_backend.views import health,console
urlpatterns=[path('admin/',admin.site.urls),path('health',health),path('',console),
 path('api/v1/',include('team_backend.urls')),path('',include('team_backend.urls'))]
