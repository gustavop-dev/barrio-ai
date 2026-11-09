from rest_framework.response import Response
from rest_framework.views import APIView
from .operador_views import human_session, get_or_404
from .permissions import require
from .models import CycleLedger
from rest_framework.exceptions import ValidationError
from .orquestacion import human_decision


class CycleDecision(APIView):
    def post(self, request, cid):
        human_session(request)
        require(request.user,'manage_jobs')
        get_or_404(CycleLedger,id=cid)
        if not isinstance(request.data,dict):raise ValidationError('Se esperaba una decisión.')
        row=human_decision(request.user,cid,request.data.get('action'),request.data.get('plan'))
        return Response({'id':str(row.id),'state':row.state,'needs_attention':row.needs_attention})
