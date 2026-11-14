"""The weekly GASP plan in the app (docs/funcionalidades/calendario-piezas.md, «La semana»): read it, change a day's type,
move two days, discard a planned idea and plan the week again (paid). estrategia.py holds the rules."""
from datetime import date
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from . import estrategia, operador
from .operador_views import human_session, valid
from .permissions import require
from .serializers import JobOutput


def _day(value,name='dia'):
    try:return date.fromisoformat(str(value))
    except (TypeError,ValueError):raise ValidationError(f'{name} debe ser una fecha AAAA-MM-DD') from None


class DayInput(serializers.Serializer):
    tipo=serializers.ChoiceField(choices=list(estrategia.TYPES),required=False)
    descartar_idea=serializers.BooleanField(required=False,default=False)


class SwapInput(serializers.Serializer):
    desde=serializers.DateField();hasta=serializers.DateField()


class PlanInput(serializers.Serializer):
    semana=serializers.DateField();request_id=serializers.UUIDField(required=False)


class Week(APIView):
    """GET /api/v1/estrategia/semana?dia=AAAA-MM-DD: the plan of the week holding that day (today by default)."""
    def get(self,request):
        require(request.user,'operate_linkedin')
        raw=request.query_params.get('dia')
        day=_day(raw) if raw else timezone.now().astimezone(operador.local_tz()).date()
        return Response(estrategia.week(day))


class Day(APIView):
    """PATCH /api/v1/estrategia/dias/<AAAA-MM-DD> {tipo?, descartar_idea?}: a day's type or its planned idea."""
    def patch(self,request,day):
        human_session(request);data=valid(DayInput,request)
        try:plan=estrategia.change(request.user,_day(day),data.get('tipo'),data.get('descartar_idea',False))
        except ValueError as exc:raise ValidationError(str(exc)) from None
        return Response(estrategia.payload(plan))


class Swap(APIView):
    """POST /api/v1/estrategia/mover {desde, hasta}: two days of the same week swap type and idea."""
    def post(self,request):
        human_session(request);data=valid(SwapInput,request)
        try:plan=estrategia.swap(request.user,data['desde'],data['hasta'])
        except ValueError as exc:raise ValidationError(str(exc)) from None
        return Response(estrategia.payload(plan))


class Plan(APIView):
    """POST /api/v1/estrategia/planear {semana, request_id?}: plan this week or the next one again (one paid call)."""
    def post(self,request):
        human_session(request);data=valid(PlanInput,request)
        job,created=estrategia.regenerate(request.user,data['semana'],data.get('request_id'),request.request_id)
        return Response({'job':JobOutput(job).data},status=202 if created else 200)
