"""Editorial calendar API for the office PWA (docs/publicacion-diaria.md)."""
from datetime import date, timedelta
from django.utils import timezone
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView
from . import capturas, editorial, operador, rescate, resultados, imagenes
from .jobs import enqueue_operation
from .models import EditorialPiece, PieceImage
from .capturas_views import FileView, serve
from .operador_views import human_session, valid
from .permissions import require
from .serializers import ActionOutput, JobOutput, OptionalRequestInput, OverrideInput
from .exceptions import Conflict

def summary(piece,action):
    brief=piece.brief or {};execution=getattr(action,'execution',None) if action is not None else None
    return {'id':str(piece.id),'slot_date':piece.slot_date,'scheduled_for':piece.scheduled_for,'state':piece.state,
            'status':editorial.status(piece,action),'stage':piece.stage,'note':piece.note,'modality':brief.get('modality'),
            'pillar':brief.get('pillar'),'primary_reader':brief.get('primary_reader'),'thesis':brief.get('thesis'),
            'approach':brief.get('approach'),'action':{'id':str(action.id),'state':action.state,'payload_hash':action.payload_hash}
            if action is not None else None,'external_url':execution.external_url if execution else None,'created_at':piece.created_at}

class Calendar(APIView):
    """Pieces per local day with their status; empty days are visible gaps, never filled without grounds."""
    def get(self,request):
        require(request.user,'operate_linkedin')
        today=timezone.now().astimezone(operador.local_tz()).date()
        try:
            start=date.fromisoformat(request.query_params['desde']) if 'desde' in request.query_params else today-timedelta(days=7)
            days=max(1,min(60,int(request.query_params.get('dias','15'))))
        except ValueError:raise ValueError('Parámetros inválidos: desde=AAAA-MM-DD y dias=1..60') from None
        end=start+timedelta(days=days)
        pieces={}
        for piece in EditorialPiece.objects.filter(slot_date__gte=start,slot_date__lt=end).prefetch_related('proposals__execution').order_by('created_at'):
            action=max(piece.proposals.all(),key=lambda a:a.created_at,default=None)
            pieces.setdefault(piece.slot_date,[]).append(summary(piece,action))
        try:post_time=editorial.post_time().strftime('%H:%M');config_error=None
        except ValueError as exc:post_time=None;config_error=str(exc)
        return Response({'timezone':str(operador.local_tz()),'post_time':post_time,'lead_hours':editorial.lead_time().total_seconds()/3600,
            'config_error':config_error,'today':today,'days':[{'date':start+timedelta(days=i),'pieces':pieces.get(start+timedelta(days=i),[])}
                                      for i in range(days)]})

class PieceDetail(APIView):
    def get(self,request,pid):
        require(request.user,'operate_linkedin')
        piece=EditorialPiece.objects.filter(id=pid).first()
        if not piece:raise NotFound()
        action=editorial.latest_action(piece)
        return Response(dict(summary(piece,action),brief=piece.brief,variants=piece.variants,panel=piece.panel,
            selection=piece.selection,verification=piece.verification,final_text=piece.final_text,citations=piece.citations,
            signals=piece.signals,research=piece.research,usage=piece.usage,metrics=piece.metrics,action_detail=ActionOutput(action).data if action is not None else None,
            # APRE-01 (docs/metricas-resultados.md): snapshots at 24 h/72 h/7 d and who commented.
            snapshots=resultados.piece_snapshots(piece),commenters=resultados.piece_commenters(piece),
            # «Comentario para el equipo» sent with the capture button (docs/capturas-galeria.md).
            team_comments=capturas.piece_comments(piece),image_kind=piece.image_kind or None,image_reason=piece.image_reason,
            images=[imagenes.payload(row) for row in piece.images.all()],image_review=piece.image_review,
            image_document_url=f'/api/v1/editorial/pieces/{piece.id}/document' if piece.image_document else None,
            # EDI-23: what he can do about a block («Pedir un cambio», «Desestimar el bloqueo»), or null.
            rescue=rescate.options(piece),override=(piece.verification or {}).get('override')))


class PieceOverride(APIView):
    """EDI-23 «Desestimar el bloqueo»: the piece goes out with his approval, without the leader. Queues the job that
    prepares its image if it lacks one and approves it (paid only when the image is missing)."""
    def post(self,request,pid):
        human_session(request);data=valid(OverrideInput,request)  # his decision: never a service credential
        require(request.user,'approve_actions')
        piece=EditorialPiece.objects.filter(id=pid).first()
        if not piece:raise NotFound()
        current=rescate.options(piece)
        if current is None:raise Conflict('La pieza no está bloqueada.')
        if current['why_not']:raise Conflict(current['why_not'])
        job,created=enqueue_operation(request.user,'override_piece',{'piece':str(piece.id),'note':data.get('note','')},
                                      data.get('request_id'),request.request_id)
        return Response({'job':JobOutput(job).data},status=202 if created else 200)


class PieceImageFile(FileView):
    def get(self,request,pid,iid):
        require(request.user,'operate_linkedin')
        row=PieceImage.objects.filter(piece_id=pid,id=iid).first()
        if row is None:raise NotFound()
        return serve(request,row.image,row.mime)


class PieceDocument(FileView):
    def get(self,request,pid):
        require(request.user,'operate_linkedin')
        piece=EditorialPiece.objects.filter(id=pid).first()
        if piece is None or not piece.image_document:raise NotFound()
        return serve(request,piece.image_document,'application/pdf')

class Plan(APIView):
    """Queue the preparation of the next free slot (paid: the editorial circuit calls Claude)."""
    def post(self,request):
        data=valid(OptionalRequestInput,request)
        job,created,slot=editorial.plan(request.user,data.get('request_id'),request.request_id)
        return Response({'slot_date':slot,'job':JobOutput(job).data},status=202 if created else 200)
