"""HTTP API of the monthly review of analista_barrio_resultados (docs/funcionalidades/revision-mensual.md).
GET /api/v1/resultados/revision-mensual: the latest review with its changes, the previous months and «Generar ahora».
POST …/generar (paid), GET …/<id>, POST …/<id>/visto, and per change POST …/cambios/<id>/aprobar|rechazar|revertir.
Every decision needs a human session (a service token gets 403) and approve_actions."""
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView
from . import revision_mensual
from .models import MonthlyReview, StrategyChange
from .operador_views import get_or_404, human_session, valid
from .permissions import require
from .rediseno_views import _orientation_payload
from .serializers import JobOutput, OptionalRequestInput

class ApproveInput(serializers.Serializer):
    text=serializers.CharField(required=False,allow_blank=True,max_length=revision_mensual.MAX_PROPOSAL_CHARS)  # his edit, if any

class RejectInput(serializers.Serializer):
    note=serializers.CharField(required=False,allow_blank=True,max_length=1000)

class MonthlyReviews(APIView):
    def get(self,request):
        require(request.user,'operate_linkedin')
        return Response(revision_mensual.overview())

class MonthlyReviewDetail(APIView):
    """GET …/<id>: one review with the figures it was written from."""
    def get(self,request,rid):
        require(request.user,'operate_linkedin')
        return Response(revision_mensual.payload(get_or_404(MonthlyReview,id=rid),with_stats=True))

class MonthlyReviewGenerate(APIView):
    """POST …/generar {request_id?}: «Generar ahora» for the month that ended; paid, a human session only."""
    def post(self,request):
        human_session(request);data=valid(OptionalRequestInput,request)
        job,created,month=revision_mensual.generate(request.user,data.get('request_id'),request.request_id)
        return Response({'month_start':month,'job':JobOutput(job).data},status=202 if created else 200)

class MonthlyReviewSeen(APIView):
    def post(self,request,rid):
        human_session(request);get_or_404(MonthlyReview,id=rid)
        review,_=revision_mensual.mark_seen(request.user,rid)
        return Response({'review':revision_mensual.payload(review)})

def _decided(change,**extra):
    """A decided change and the orientation as it is now, so the screen shows what changed."""
    change.refresh_from_db()
    return Response(dict({'change':revision_mensual.change_payload(change),'orientation':_orientation_payload()},**extra))

class StrategyChangeApprove(APIView):
    """POST …/cambios/<id>/aprobar {text?}: «Aprobar». POST …/cambios/<id>/editar {text}: «Editar y aprobar», which
    refuses an empty text: a client that does not know the editable action must not approve the original by accident."""
    require_text=False
    def post(self,request,cid):
        human_session(request);get_or_404(StrategyChange,id=cid);data=valid(ApproveInput,request)
        if self.require_text and not (data.get('text') or '').strip():
            return Response({'detail':'Escribe el texto del cambio para aprobarlo editado.'},status=400)
        return _decided(revision_mensual.approve(request.user,cid,data.get('text')))

class StrategyChangeReject(APIView):
    """POST …/cambios/<id>/rechazar {note?}."""
    def post(self,request,cid):
        human_session(request);get_or_404(StrategyChange,id=cid);data=valid(RejectInput,request)
        return _decided(revision_mensual.reject(request.user,cid,data.get('note','')))

class StrategyChangeRevert(APIView):
    """POST …/cambios/<id>/revertir: removes exactly what «Aprobar» added to the orientation."""
    def post(self,request,cid):
        human_session(request);get_or_404(StrategyChange,id=cid)
        change,found=revision_mensual.revert(request.user,cid)
        return _decided(change,found=found,message=None if found else revision_mensual.NOT_FOUND)
