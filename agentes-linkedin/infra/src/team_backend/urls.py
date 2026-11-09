from django.urls import path
from . import views
from . import operador_views as op
from . import oficina_views as of
from . import linkedin_views as li
from . import editorial_views as ed
from . import red_views as rd
from . import resultados_views as rs
from . import rediseno_views as rv
from . import capturas_views as cv
from . import movil_views as mv
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
 # Self-hosted office PWA (oficina/CONTRATO-API.md).
 path('auth/session',of.session_view),path('auth/login',of.login_view),path('auth/logout',of.logout_view),
 path('operador/overview',of.Overview.as_view()),path('operador/control',of.Control.as_view()),
 path('operador/feed',of.Feed.as_view()),path('oficina/actividad',of.Actividad.as_view()),path('oficina/eventos',of.Eventos.as_view()),
 path('push/key',of.PushKey.as_view()),path('push/subscriptions',of.PushSubscriptions.as_view()),
 path('push/unsubscribe',of.PushUnsubscribe.as_view()),path('push/test',of.PushTest.as_view()),
 # Official LinkedIn API: member OAuth and token status (docs/publicacion-diaria.md).
 path('linkedin/oauth/start',li.OAuthStart.as_view()),path('linkedin/oauth/callback',li.oauth_callback),
 path('linkedin/status',li.Status.as_view()),
 path('red/contacts',rd.Contacts.as_view()),path('red/contacts/<uuid:cid>',rd.ContactDetail.as_view()),
 path('red/contacts/<uuid:cid>/discard',rd.ContactDiscard.as_view()),path('red/summary',rd.Summary.as_view()),
 # Resultados: own-post and audience metrics against the previous period (docs/metricas-resultados.md).
 path('resultados',rs.Resultados.as_view()),
 path('tu-turno',rv.TuTurno.as_view()),path('tu-turno/vistos',rv.TuTurnoSeen.as_view()),
 path('notificaciones',rv.Notifications.as_view()),path('notificaciones/leer',rv.NotificationsRead.as_view()),path('preguntas',rv.Questions.as_view()),
 path('preguntas/<uuid:qid>/responder',rv.QuestionAnswer.as_view()),path('preguntas/<uuid:qid>/no-compartir',rv.QuestionDecline.as_view()),
 path('preguntas/<uuid:qid>/deshacer',rv.QuestionUndo.as_view()),path('preguntas/<uuid:qid>/mas-tarde',rv.QuestionPostpone.as_view()),
 path('memoria/hechos',rv.Facts.as_view()),path('memoria/hechos/<str:key>/corregir',rv.FactCorrect.as_view()),
 path('memoria/hechos/<str:key>/retirar',rv.FactRetire.as_view()),path('orientacion',rv.OrientationView.as_view()),
 path('oportunidades',rv.Opportunities.as_view()),path('oportunidades/<uuid:oid>',rv.OpportunityDetail.as_view()),
 path('actividad',rv.Activity.as_view()),path('calendario',rv.Calendar.as_view()),path('ajustes',rv.Settings.as_view()),
 path('red/contacts/<uuid:cid>/notas',rd.ContactNotes.as_view()),
 path('operador/referents/<uuid:rid>',op.ReferentDetail.as_view()),
 # Daily own publication: editorial calendar and pieces (CONT-01..07, CONT-09).
 path('editorial/calendar',ed.Calendar.as_view()),path('editorial/pieces/<uuid:pid>',ed.PieceDetail.as_view()),
 path('editorial/plan',ed.Plan.as_view()),
 path('editorial/pieces/<uuid:pid>/images/<uuid:iid>',ed.PieceImageFile.as_view()),
 path('editorial/pieces/<uuid:pid>/document',ed.PieceDocument.as_view()),
 # Capture button and Galería (docs/capturas-galeria.md): private files, authenticated streaming only.
 path('capturas',cv.Captures.as_view()),path('capturas/<uuid:cid>',cv.CaptureDetail.as_view()),
 path('capturas/<uuid:cid>/audio',cv.CaptureAudio.as_view()),
 path('galeria',cv.Gallery.as_view()),path('galeria/<uuid:pid>',cv.PhotoDetail.as_view()),
 path('galeria/<uuid:pid>/imagen',cv.PhotoImage.as_view()),path('ajustes/preferencias',cv.Preferences.as_view()),
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
 # Inbox (docs/conversaciones-inbox.md): read-only; Gustavo closes the Tu turno card of a conversation.
 path('conversaciones/<uuid:cid>/cerrar',rv.ConversationClose.as_view()),
 # Weekly results summary of analista_barrio_resultados (docs/resumen-semanal.md).
 path('resultados/resumen-semanal',rs.WeeklySummaries.as_view()),path('resultados/resumen-semanal/generar',rs.WeeklySummaryGenerate.as_view()),
 path('resultados/resumen-semanal/<uuid:sid>',rs.WeeklySummaryDetail.as_view()),
 path('resultados/resumen-semanal/<uuid:sid>/visto',rs.WeeklySummarySeen.as_view()),
 path('resultados/resumen-semanal/<uuid:sid>/aplicar',rs.WeeklySummaryApply.as_view()),
 path('resultados/resumen-semanal/<uuid:sid>/descartar',rs.WeeklySummaryDiscard.as_view()),
 path('resultados/resumen-semanal/<uuid:sid>/deshacer',rs.WeeklySummaryUndo.as_view()),
 # Mobile app (docs/app-movil-backend.md): device-token login (a human session without CSRF) and Expo push.
 path('auth/token',mv.TokenIssue.as_view()),path('auth/token/revocar',mv.TokenRevoke.as_view()),
 path('auth/dispositivos',mv.Devices.as_view()),path('auth/dispositivos/<uuid:did>',mv.DeviceDetail.as_view()),
 path('push/expo',mv.ExpoPush.as_view()),
 # Client error reports of the app (CONTRATO-API.md «Errores del cliente»): metadata only, logged and kept.
 path('app/errores',mv.ClientErrors.as_view()),
]
