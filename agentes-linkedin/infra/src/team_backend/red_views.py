"""HTTP API of the neighborhood network (Red): contacts, their discard by Gustavo and the summary for the office."""
import uuid
from django.db.models import Q
from django.utils import timezone
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from . import red
from .models import ConnectorAccount, Contact
from .operador_views import get_or_404, human_session, valid
from .permissions import require
from .serializers import ContactOutput, DiscardInput, NoteInput

class Contacts(ListAPIView):
    serializer_class=ContactOutput
    def get_queryset(self):
        require(self.request.user,'operate_linkedin')
        qs=Contact.objects.prefetch_related('proposals').order_by('-updated_at')
        params=self.request.query_params
        stage=params.get('stage')
        open_opportunity=Q(opportunities__isnull=False)&~Q(opportunities__stage__in=['acuerdo','sin_acuerdo'])
        # Personas › Conexiones in the app: only who accepted, the most recent connection first (the stage is ignored).
        if params.get('vista')=='conexiones':qs=red.connections(qs)
        elif stage=='opportunity':qs=qs.filter(open_opportunity).distinct()
        elif stage=='conversation':qs=qs.none()  # conversations arrive with the inbox
        elif stage:qs=qs.filter(stage=stage)
        if params.get('source'):qs=qs.filter(source=params['source'])
        if params.get('role')==red.NO_ROLE:qs=qs.filter(red.without_role())
        elif params.get('role'):qs=qs.filter(classification__role=params['role'])
        if params.get('modality'):qs=qs.filter(classification__modality=params['modality'])
        if params.get('q'):qs=qs.filter(Q(display_name__icontains=params['q'])|Q(headline__icontains=params['q']))
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

class ContactConfirmFit(APIView):
    """Personas → «Sí, encaja»: Gustavo answers a doubt of the lead about a person the classifier said fits."""
    def post(self,request,cid):
        human_session(request);get_or_404(Contact,id=cid)
        return Response(ContactOutput(red.confirm_fit(request.user,cid)).data)

class ContactNotes(APIView):
    """Personas → Notas: Gustavo's free notes about a person, newest last."""
    def post(self,request,cid):
        human_session(request);data=valid(NoteInput,request);require(request.user,'approve_actions')
        contact=get_or_404(Contact,id=cid)
        contact.notes=list(contact.notes)+[{'id':uuid.uuid4().hex[:12],'at':timezone.now().isoformat(),'text':data['text'].strip(),
                                            'by':request.user.get_username()}]
        contact.save(update_fields=['notes'])
        return Response(ContactOutput(contact).data,status=201)

class Summary(APIView):
    def get(self,request):
        require(request.user,'operate_linkedin')
        account=request.query_params.get('account')
        data=red.summary(get_or_404(ConnectorAccount,id=account) if account else None)
        from .models import Opportunity
        data['stages']['opportunity']=Contact.objects.filter(opportunities__isnull=False).exclude(
            opportunities__stage__in=['acuerdo','sin_acuerdo']).distinct().count()
        data['stages']['conversation']=None  # measured once the inbox is read
        return Response(data)
