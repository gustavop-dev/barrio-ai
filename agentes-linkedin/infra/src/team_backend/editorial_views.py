"""Editorial calendar API for the office PWA (docs/publicacion-diaria.md)."""
from datetime import date, timedelta
from django.utils import timezone
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView
from . import editorial, operador, resultados
from .models import EditorialPiece
from .operador_views import valid
from .permissions import require
from .serializers import ActionOutput, JobOutput, OptionalRequestInput

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
            signals=piece.signals,usage=piece.usage,metrics=piece.metrics,action_detail=ActionOutput(action).data if action is not None else None,
            # APRE-01 (docs/metricas-resultados.md): snapshots at 24 h/72 h/7 d and who commented.
            snapshots=resultados.piece_snapshots(piece),commenters=resultados.piece_commenters(piece)))

class Plan(APIView):
    """Queue the preparation of the next free slot (paid: the editorial circuit calls Claude)."""
    def post(self,request):
        data=valid(OptionalRequestInput,request)
        job,created,slot=editorial.plan(request.user,data.get('request_id'),request.request_id)
        return Response({'slot_date':slot,'job':JobOutput(job).data},status=202 if created else 200)
