from django.urls import path
from . import views
from . import operador_views as op
urlpatterns=[
 path('status',views.Status.as_view()),path('search',views.Search.as_view()),
 path('units',views.Units.as_view()),path('units/<str:uid>',views.UnitDetail.as_view()),
 path('sources/<path:key>',views.SourceDetail.as_view()),
 path('runs',views.Runs.as_view()),path('runs/<uuid:rid>',views.RunDetail.as_view()),
 path('runs/<uuid:rid>/cancel',views.CancelRun.as_view()),
 path('memory',views.Memory.as_view()),path('memory/proposals',views.ProposeMemory.as_view()),
 path('memory/<uuid:mid>/confirm',views.ConfirmMemory.as_view()),
 path('integrity',views.Integrity.as_view()),path('audit',views.Audit.as_view()),
 # Account operator (DESC-04, INT-02, INT-03, ADM-04/05).
 path('operador/accounts',op.Accounts.as_view()),
 path('operador/accounts/<uuid:aid>/check',op.AccountCheck.as_view()),
 path('operador/accounts/<uuid:aid>/pause',op.AccountPause.as_view()),
 path('operador/referents',op.Referents.as_view()),
 path('operador/observe',op.Observe.as_view()),
 path('operador/posts',op.Posts.as_view()),
 path('operador/posts/<uuid:pid>/propose-comment',op.ProposeComment.as_view()),
 path('operador/actions',op.Actions.as_view()),
 path('operador/actions/<uuid:pid>',op.ActionDetail.as_view()),
 path('operador/actions/<uuid:pid>/revise',op.ActionRevise.as_view()),
 path('operador/actions/<uuid:pid>/approve',op.ActionApprove.as_view()),
 path('operador/actions/<uuid:pid>/reject',op.ActionReject.as_view()),
 path('operador/actions/<uuid:pid>/execute',op.ActionExecute.as_view()),
 path('operador/actions/<uuid:pid>/reconcile',op.ActionReconcile.as_view()),
 path('operador/actions/<uuid:pid>/resolve',op.ActionResolve.as_view()),
]
