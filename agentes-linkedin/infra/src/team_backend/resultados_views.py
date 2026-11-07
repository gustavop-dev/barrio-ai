"""HTTP API of Resultados for the office (docs/metricas-resultados.md).
GET /api/v1/resultados?dias=7|28|90&modalidad=todo|personal_startups|projectapp (defaults: 28, todo).
/api/v1/resultados/resumen-semanal…: the weekly summary of analista_barrio_resultados (docs/resumen-semanal.md)."""
from rest_framework.response import Response
from rest_framework.views import APIView
from . import resultados, resumen_semanal
from .models import WeeklySummary
from .operador_views import get_or_404, human_session, valid
from .permissions import require
from .rediseno_views import _orientation_payload
from .serializers import JobOutput, OptionalRequestInput

class Resultados(APIView):
    def get(self,request):
        require(request.user,'operate_linkedin')
        params=request.query_params
        return Response(resultados.build(params.get('dias','28'),params.get('modalidad','todo')))

# --------------------------------------------------------------------------- weekly summary (docs/resumen-semanal.md)

class WeeklySummaries(APIView):
    """GET /api/v1/resultados/resumen-semanal: the latest summary, the previous weeks and «Generar ahora»."""
    def get(self,request):
        require(request.user,'operate_linkedin')
        return Response(resumen_semanal.overview())

class WeeklySummaryDetail(APIView):
    """GET /api/v1/resultados/resumen-semanal/<id>: one summary with the figures it was written from."""
    def get(self,request,sid):
        require(request.user,'operate_linkedin')
        return Response(resumen_semanal.payload(get_or_404(WeeklySummary,id=sid),with_stats=True))

class WeeklySummaryGenerate(APIView):
    """POST /api/v1/resultados/resumen-semanal/generar {request_id?}: paid; a human session only."""
    def post(self,request):
        human_session(request);data=valid(OptionalRequestInput,request)
        job,created,week=resumen_semanal.generate(request.user,data.get('request_id'),request.request_id)
        return Response({'week_start':week,'job':JobOutput(job).data},status=202 if created else 200)

def _decision(func,with_orientation=False):
    class View(APIView):
        def post(self,request,sid):
            human_session(request);get_or_404(WeeklySummary,id=sid)
            result=func(request.user,sid)
            summary,previous=result if isinstance(result,tuple) else (result,None)
            body={'summary':resumen_semanal.payload(summary)}
            if with_orientation:body.update(orientation=_orientation_payload(),previous_orientation=previous)
            return Response(body)
    return View

WeeklySummaryApply=_decision(resumen_semanal.apply,with_orientation=True)
WeeklySummaryDiscard=_decision(resumen_semanal.discard)
WeeklySummaryUndo=_decision(resumen_semanal.undo,with_orientation=True)
WeeklySummarySeen=_decision(lambda user,sid:resumen_semanal.mark_seen(user,sid)[0])
