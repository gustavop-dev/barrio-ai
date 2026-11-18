"""HTTP API of Resultados for the office (docs/metricas-resultados.md).
GET /api/v1/resultados?dias=7|28|90&modalidad=todo|personal_startups|projectapp (defaults: 28, todo).
GET /api/v1/resultados/analitica?periodo=7d|14d|28d|90d|365d or ?desde&hasta: LinkedIn's own analytics, stored data only.
/api/v1/resultados/resumen-semanal…: the weekly summary of analista_barrio_resultados (docs/resumen-semanal.md).
GET /api/v1/resultados/embudo-comprador?semanas=1..26 (default 8): the buyer's funnel (comprador.funnel), read-only."""
from rest_framework.response import Response
from rest_framework.views import APIView
from . import alcance, analitica, comprador, resultados, resumen_semanal
from .models import WeeklySummary
from .operador_views import human_session, valid
from .permissions import require
from .rediseno_views import _orientation_payload
from .serializers import JobOutput, OptionalRequestInput

class Resultados(APIView):
    def get(self,request):
        require(request.user,'operate_linkedin')
        params=request.query_params
        return Response(resultados.build(params.get('dias','28'),params.get('modalidad','todo'),member=alcance.miembro(request)))  # hers

class Analitica(APIView):
    """LinkedIn's analytics of the directo account for a preset (default 28d) or a custom range, optional `cuenta`.
    Read-only and never calls LinkedIn: analitica.overview reads what the imports stored."""
    def get(self,request):
        require(request.user,'operate_linkedin')
        p=request.query_params
        return Response(analitica.overview(p.get('cuenta'),p.get('periodo'),p.get('desde'),p.get('hasta'),
                                           member=alcance.miembro(request)))

class EmbudoComprador(APIView):
    """The buyer's funnel by week and cumulative (docs/plan-outbound.md, phase 1). Read-only; never calls LinkedIn."""
    def get(self,request):
        require(request.user,'operate_linkedin')
        return Response(comprador.funnel(request.query_params.get('semanas','8'),accounts=alcance.accounts(alcance.miembro(request))))  # hers

# --------------------------------------------------------------------------- weekly summary (docs/resumen-semanal.md)

class WeeklySummaries(APIView):
    """GET /api/v1/resultados/resumen-semanal: the latest summary, the previous weeks and «Generar ahora»."""
    def get(self,request):
        require(request.user,'operate_linkedin')
        return Response(resumen_semanal.overview(member=alcance.miembro(request)))  # hers (phase 4)

class WeeklySummaryDetail(APIView):
    """GET /api/v1/resultados/resumen-semanal/<id>: one summary with the figures it was written from."""
    def get(self,request,sid):
        require(request.user,'operate_linkedin')
        return Response(resumen_semanal.payload(alcance.obtener(request,WeeklySummary,id=sid),with_stats=True))

class WeeklySummaryGenerate(APIView):
    """POST /api/v1/resultados/resumen-semanal/generar {request_id?}: paid; a human session only."""
    def post(self,request):
        human_session(request);data=valid(OptionalRequestInput,request)
        job,created,week=resumen_semanal.generate(request.user,data.get('request_id'),request.request_id)
        return Response({'week_start':week,'job':JobOutput(job).data},status=202 if created else 200)

def _decision(func,with_orientation=False):
    class View(APIView):
        def post(self,request,sid):
            human_session(request);alcance.obtener(request,WeeklySummary,id=sid)  # hers, else 404
            result=func(request.user,sid)
            summary,previous=result if isinstance(result,tuple) else (result,None)
            body={'summary':resumen_semanal.payload(summary)}
            if with_orientation:body.update(orientation=_orientation_payload(summary.member),previous_orientation=previous)  # hers
            return Response(body)
    return View

WeeklySummaryApply=_decision(resumen_semanal.apply,with_orientation=True)
WeeklySummaryDiscard=_decision(resumen_semanal.discard)
WeeklySummaryUndo=_decision(resumen_semanal.undo,with_orientation=True)
WeeklySummarySeen=_decision(lambda user,sid:resumen_semanal.mark_seen(user,sid)[0])
