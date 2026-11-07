"""HTTP API of the neighborhood network (Red): contacts, their discard by Gustavo and the summary for the office."""
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from . import red
from .models import ConnectorAccount, Contact
from .operador_views import get_or_404, human_session, valid
from .permissions import require
from .serializers import ContactOutput, DiscardInput

class Contacts(ListAPIView):
    serializer_class=ContactOutput
    def get_queryset(self):
        require(self.request.user,'operate_linkedin')
        qs=Contact.objects.prefetch_related('proposals').order_by('-updated_at')
        for field in ('stage','source'):
            value=self.request.query_params.get(field)
            if value:qs=qs.filter(**{field:value})
        account=self.request.query_params.get('account')
        return qs.filter(account_id=account) if account else qs

class ContactDetail(APIView):
    def get(self,request,cid):
        require(request.user,'operate_linkedin')
        return Response(ContactOutput(get_or_404(Contact,id=cid)).data)

class ContactDiscard(APIView):
    def post(self,request,cid):
        human_session(request);data=valid(DiscardInput,request);get_or_404(Contact,id=cid)
        return Response(ContactOutput(red.discard(request.user,cid,data['note'])).data)

class Summary(APIView):
    def get(self,request):
        require(request.user,'operate_linkedin')
        account=request.query_params.get('account')
        return Response(red.summary(get_or_404(ConnectorAccount,id=account) if account else None))
