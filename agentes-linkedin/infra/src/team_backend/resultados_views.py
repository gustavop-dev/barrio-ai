"""HTTP API of Resultados for the office (docs/metricas-resultados.md).
GET /api/v1/resultados?dias=7|28|90&modalidad=todo|personal_startups|projectapp (defaults: 28, todo)."""
from rest_framework.response import Response
from rest_framework.views import APIView
from . import resultados
from .permissions import require

class Resultados(APIView):
    def get(self,request):
        require(request.user,'operate_linkedin')
        params=request.query_params
        return Response(resultados.build(params.get('dias','28'),params.get('modalidad','todo')))
