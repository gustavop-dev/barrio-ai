"""HTTP API of the account operator. Decisions (approve, reject, pause, resolve) require a
human session: the PWA's with CSRF or the mobile app's device token. A service credential can observe and prepare
but never decide."""
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from . import operador
from .connectors import ConnectorError
from .jobs import enqueue_operation
from .models import ActionProposal, ConnectorAccount, DeviceToken, ObservedPost, Referent
from .permissions import require
from .serializers import (AccountInput, AccountOutput, ActionInput, ActionOutput, DecisionInput, JobOutput, ObserveInput,
                          OptionalRequestInput, PauseInput, PostOutput, ReferentInput, ReferentOutput, ReferentPatch, ResolveInput, ReviseInput)

REFERENT_NOT_FOUND='No encontramos ese perfil en LinkedIn: revisa la URL.'

def human_session(request):
    """A Django session (request.auth is None) or a device token of the mobile app; anything else, such as a service
    ApiCredential, is refused."""
    if request.auth is not None and not isinstance(request.auth,DeviceToken):
        raise PermissionDenied('Esta decisión requiere una sesión humana con CSRF')

def valid(serializer_class,request):
    data=serializer_class(data=request.data);data.is_valid(raise_exception=True)
    return data.validated_data

def get_or_404(model,**lookup):
    obj=model.objects.filter(**lookup).first()
    if not obj:raise NotFound()
    return obj

def action_response(proposal,status=200):
    proposal=ActionProposal.objects.select_related('post','piece','contact').get(pk=proposal.pk)
    return Response(ActionOutput(proposal).data,status=status)

class Accounts(ListAPIView):
    serializer_class=AccountOutput
    def get_queryset(self):
        require(self.request.user,'operate_linkedin')
        return ConnectorAccount.objects.order_by('created_at')
    def post(self,request):
        data=valid(AccountInput,request)
        return Response(AccountOutput(operador.register_account(request.user,**data)).data,status=201)

class AccountCheck(APIView):
    def post(self,request,aid):
        require(request.user,'operate_linkedin')
        return Response(AccountOutput(operador.check_account(get_or_404(ConnectorAccount,id=aid),request.user)).data)

class AccountPause(APIView):
    def post(self,request,aid):
        human_session(request);data=valid(PauseInput,request)
        account=operador.set_paused(request.user,get_or_404(ConnectorAccount,id=aid),data['paused'],data['reason'])
        return Response(AccountOutput(account).data)

class Referents(ListAPIView):
    serializer_class=ReferentOutput
    def get_queryset(self):
        require(self.request.user,'operate_linkedin')
        qs=Referent.objects.all()
        account=self.request.query_params.get('account')
        return qs.filter(account_id=account) if account else qs
    def post(self,request):
        data=valid(ReferentInput,request)
        try:
            referent,created=operador.add_referent(request.user,get_or_404(ConnectorAccount,id=data['account']),data['identifier'],data['reason'])
        except ConnectorError as exc:
            # The profile is looked up on LinkedIn first: say why it could not be added instead of a server error.
            if exc.status==404:return Response({'detail':REFERENT_NOT_FOUND},status=400)
            return Response({'detail':f'No se pudo consultar LinkedIn: {exc}'},status=503)
        return Response(ReferentOutput(referent).data,status=201 if created else 200)

class ReferentDetail(APIView):
    """Personas → Referentes: deactivate, reactivate, change the reason or remove a referent."""
    def patch(self,request,rid):
        human_session(request);require(request.user,'operate_linkedin');data=valid(ReferentPatch,request)
        referent=get_or_404(Referent,id=rid)
        for field in ('active','reason'):
            if field in data:setattr(referent,field,data[field])
        referent.save()
        from .jobs import audit
        audit(request.user,'operator.referent_updated',referent.id,active=referent.active)
        return Response(ReferentOutput(referent).data)
    def delete(self,request,rid):
        human_session(request);require(request.user,'approve_actions')
        referent=get_or_404(Referent,id=rid)
        from .jobs import audit
        referent.delete();audit(request.user,'operator.referent_removed',str(rid))
        return Response(status=204)

class Observe(APIView):
    def post(self,request):
        data=valid(ObserveInput,request)
        get_or_404(ConnectorAccount,id=data['account'])
        params={'account':str(data['account']),'limit':data['limit'],'referents':[str(r) for r in data.get('referents',[])]}
        job,created=enqueue_operation(request.user,'observe',params,data.get('request_id'),request.request_id)
        return Response(JobOutput(job).data,status=202 if created else 200)

class Posts(ListAPIView):
    serializer_class=PostOutput
    def get_queryset(self):
        require(self.request.user,'operate_linkedin')
        qs=ObservedPost.objects.all()
        account=self.request.query_params.get('account')
        return qs.filter(account_id=account) if account else qs

class ProposeComment(APIView):
    def post(self,request,pid):
        data=valid(OptionalRequestInput,request);get_or_404(ObservedPost,id=pid)
        job,created=enqueue_operation(request.user,'propose_comment',{'post':str(pid)},data.get('request_id'),request.request_id)
        return Response(JobOutput(job).data,status=202 if created else 200)

class Actions(ListAPIView):
    serializer_class=ActionOutput
    def get_queryset(self):
        require(self.request.user,'operate_linkedin')
        qs=ActionProposal.objects.select_related('post','piece','contact')
        state=self.request.query_params.get('state');capability=self.request.query_params.get('capability')
        if state:qs=qs.filter(state=state)
        return qs.filter(capability=capability) if capability else qs
    def post(self,request):
        data=valid(ActionInput,request)
        post=get_or_404(ObservedPost,id=data['post'])
        proposal=operador.create_proposal(request.user,post,data['capability'],data['payload'],rationale=data['rationale'])
        return action_response(proposal,201)

class ActionDetail(APIView):
    def get(self,request,pid):
        require(request.user,'operate_linkedin')
        return action_response(get_or_404(ActionProposal,id=pid))

class ActionRevise(APIView):
    def post(self,request,pid):
        data=valid(ReviseInput,request);get_or_404(ActionProposal,id=pid)
        return action_response(operador.revise(request.user,pid,data['payload'],data['note']),201)

class ActionApprove(APIView):
    def post(self,request,pid):
        human_session(request);data=valid(DecisionInput,request)
        if 'expected_hash' not in data:raise PermissionDenied('Aprobar requiere el hash de la versión revisada')
        get_or_404(ActionProposal,id=pid)
        job=operador.approve(request.user,pid,data['expected_hash'],data['note'])
        return Response({'action':ActionOutput(ActionProposal.objects.select_related('post','piece','contact').get(pk=pid)).data,
                         'job':JobOutput(job).data},status=202)

class ActionReject(APIView):
    def post(self,request,pid):
        human_session(request);data=valid(DecisionInput,request);get_or_404(ActionProposal,id=pid)
        return action_response(operador.reject(request.user,pid,data['note']))

class ActionExecute(APIView):
    """Re-request the execution job of an approved proposal (idempotent: same job id)."""
    def post(self,request,pid):
        proposal=get_or_404(ActionProposal,id=pid)
        if proposal.state!=ActionProposal.State.APPROVED:raise PermissionDenied('Solo propuestas aprobadas')
        return Response(JobOutput(operador.enqueue_execution(request.user,proposal)).data,status=202)

class ActionReconcile(APIView):
    def post(self,request,pid):
        data=valid(OptionalRequestInput,request);get_or_404(ActionProposal,id=pid)
        job,created=enqueue_operation(request.user,'reconcile_action',{'proposal':str(pid)},data.get('request_id'),request.request_id)
        return Response(JobOutput(job).data,status=202 if created else 200)

class ActionResolve(APIView):
    def post(self,request,pid):
        human_session(request);data=valid(ResolveInput,request);get_or_404(ActionProposal,id=pid)
        operador.resolve_uncertain(request.user,pid,data['outcome'],data['note'])
        return action_response(get_or_404(ActionProposal,id=pid))
