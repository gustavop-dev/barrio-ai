from django.urls import path
from . import views
urlpatterns=[
 path('status',views.Status.as_view()),path('search',views.Search.as_view()),
 path('units',views.Units.as_view()),path('units/<str:uid>',views.UnitDetail.as_view()),
 path('sources/<path:key>',views.SourceDetail.as_view()),
 path('runs',views.Runs.as_view()),path('runs/<uuid:rid>',views.RunDetail.as_view()),
 path('runs/<uuid:rid>/cancel',views.CancelRun.as_view()),
 path('memory',views.Memory.as_view()),path('memory/proposals',views.ProposeMemory.as_view()),
 path('memory/<uuid:mid>/confirm',views.ConfirmMemory.as_view()),
 path('integrity',views.Integrity.as_view()),path('audit',views.Audit.as_view()),
]
