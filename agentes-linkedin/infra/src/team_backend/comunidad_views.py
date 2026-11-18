"""Private single-workspace API; session and device permissions are shared."""
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView
from . import alcance, comunidad
from .models import CommunitySource, ConnectorAccount
from .permissions import require


class AccountInput(serializers.Serializer):
    account = serializers.UUIDField()


class RefreshInput(AccountInput):
    refresh = serializers.BooleanField(default=True)


class WithdrawalInput(serializers.Serializer):
    whole_person = serializers.BooleanField(default=False)
    reason = serializers.ChoiceField(choices=['excluded', 'incorrect'], default='excluded')


class Community(APIView):
    def get(self, request):
        require(request.user, 'operate_linkedin')
        data = AccountInput(data=request.query_params)
        data.is_valid(raise_exception=True)
        account = alcance.obtener(request, ConnectorAccount, pk=data.validated_data['account'])  # her account, or 404
        return Response(comunidad.detail(account))

    def post(self, request):
        require(request.user, 'operate_linkedin')
        data = RefreshInput(data=request.data)
        data.is_valid(raise_exception=True)
        account = alcance.obtener(request, ConnectorAccount, pk=data.validated_data['account'])
        study, job, created = comunidad.enqueue(request.user, account, refresh=data.validated_data['refresh'])
        visible = job.owner_id == request.user.pk or request.user.has_perm('team_backend.manage_jobs')
        return Response({'study_id': str(study.pk), 'job_id': str(job.pk) if visible else None, 'created': created}, status=202)


class WithdrawSource(APIView):
    def post(self, request, sid):
        require(request.user, 'operate_linkedin')
        data = WithdrawalInput(data=request.data)
        data.is_valid(raise_exception=True)
        source = alcance.obtener(request, CommunitySource.objects.select_related('study', 'person'), pk=sid)
        comunidad.withdraw(request.user, source, **data.validated_data)
        return Response({'status': 'retirada'})
