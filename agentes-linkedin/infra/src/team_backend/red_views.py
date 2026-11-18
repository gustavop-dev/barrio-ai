"""HTTP API of the neighborhood network (Red): contacts, their discard by Gustavo and the summary for the office."""
import uuid
from django.db.models import Q
from django.utils import timezone
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from . import alcance, red
from .models import Contact
from .operador_views import human_session, valid
from .permissions import require
from .serializers import ContactOutput, DiscardInput, NoteInput

class Contacts(ListAPIView):
    serializer_class=ContactOutput
    def get_queryset(self):
        require(self.request.user,'operate_linkedin')
        qs=alcance.de(Contact.objects.prefetch_related('proposals'),alcance.miembro(self.request)).order_by('-updated_at')  # hers (phase 5)
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
        return Response(ContactOutput(alcance.obtener(request,Contact,id=cid)).data)

class ContactDiscard(APIView):
    def post(self,request,cid):
        human_session(request);data=valid(DiscardInput,request);alcance.obtener(request,Contact,id=cid)
        return Response(ContactOutput(red.discard(request.user,cid,data['note'])).data)

class ContactConfirmFit(APIView):
    """Personas → «Sí, encaja»: Gustavo answers a doubt of the lead about a person the classifier said fits."""
    def post(self,request,cid):
        human_session(request);alcance.obtener(request,Contact,id=cid)
        return Response(ContactOutput(red.confirm_fit(request.user,cid)).data)

class ContactNotes(APIView):
    """Personas → Notas: Gustavo's free notes about a person, newest last."""
    def post(self,request,cid):
        human_session(request);data=valid(NoteInput,request);require(request.user,'approve_actions')
        contact=alcance.obtener(request,Contact,id=cid)
        contact.notes=list(contact.notes)+[{'id':uuid.uuid4().hex[:12],'at':timezone.now().isoformat(),'text':data['text'].strip(),
                                            'by':request.user.get_username()}]
        contact.save(update_fields=['notes'])
        return Response(ContactOutput(contact).data,status=201)

class OldInvitations(APIView):
    """GET /api/v1/red/invitaciones-pendientes?dias=21: invitations still pending after `dias` (1–365), oldest first,
    for Gustavo to withdraw by hand if he wants (phase 2, calentamiento.old_invitations). Read-only, never calls
    LinkedIn; the team never withdraws nor sends one again."""
    def get(self,request):
        require(request.user,'operate_linkedin')
        from . import calentamiento
        member=alcance.miembro(request)
        return Response(calentamiento.old_invitations(request.query_params.get('dias','21'),
                                                      alcance.cuenta(request,request.query_params.get('account')),
                                                      contacts=alcance.de(Contact.objects.all(),member)))

class Summary(APIView):
    def get(self,request):
        require(request.user,'operate_linkedin')
        account=alcance.cuenta(request,request.query_params.get('account'));member=alcance.miembro(request)
        if account:data=red.summary(account)  # the rhythm of the account's member: one of hers
        else:data=red.summary(member=member)  # hers (organizaciones, phase 2; her contacts and reads, phase 5)
        data['stages']['opportunity']=alcance.de(Contact.objects.filter(opportunities__isnull=False),member).exclude(
            opportunities__stage__in=['acuerdo','sin_acuerdo']).distinct().count()
        data['stages']['conversation']=None  # measured once the inbox is read
        return Response(data)
