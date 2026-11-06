import os
from datetime import timedelta
from pathlib import Path
from django.conf import settings
from django.db import connection,transaction
from django.http import HttpResponse,JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.exceptions import NotFound,PermissionDenied
from knowledge import db,ingest,memory,providers,retrieval
from . import jobs
from .models import KnowledgeUnit,KnowledgeRun,Worker,AuditEvent,ApiCredential
from .permissions import require
from .serializers import SearchInput,RunInput,JobOutput,UnitOutput,ProposalInput,ConfirmationInput,AuditOutput

def health(request):
    with connection.cursor() as cursor:cursor.execute('SELECT 1')
    return JsonResponse({'status':'ok','framework':'django'})

@ensure_csrf_cookie
def console(request):
    return HttpResponse(Path(retrieval.__file__).with_name('console.html').read_text())

class Status(APIView):
    def get(self,request):
        result=db.status()
        result.update(framework='django',embedding_plan=providers.index(False),
            live_providers=os.environ.get('LIVE_PROVIDERS','false')=='true',
            credentials={p:bool(os.environ.get(p.upper()+'_API_KEY')) for p in ['openai','anthropic']},
            queue={state:jobs.visible_jobs(request.user).filter(state=state).count() for state in jobs.Job.State.values},
            workers_alive=Worker.objects.filter(last_seen__gte=timezone.now()-timedelta(seconds=settings.WORKER_STALE_SECONDS),stopped_at=None).count())
        return Response(result)

class Search(APIView):
    def post(self,request):
        data=SearchInput(data=request.data);data.is_valid(raise_exception=True)
        if data.validated_data['mode']=='hybrid':require(request.user,'use_paid_providers')
        return Response(retrieval.search(**data.validated_data))

class Units(ListAPIView):
    serializer_class=UnitOutput
    def get_queryset(self):
        qs=KnowledgeUnit.objects.filter(active=True).defer('original')
        session=self.request.query_params.get('session')
        if session:
            if session not in ['1','2','3','4','5','6']:raise ValueError('Clase fuera del alcance 01–06')
            qs=qs.filter(session=int(session))
        return qs

class UnitDetail(APIView):
    def get(self,request,uid):
        if not KnowledgeUnit.objects.filter(id=uid,active=True).exists():raise NotFound('Unidad no encontrada')
        return Response(retrieval.unit(uid))

class SourceDetail(APIView):
    def get(self,request,key):
        with db.connect() as c:row=c.execute('SELECT original FROM evidence WHERE key=%s',(key,)).fetchone()
        if not row:raise NotFound('Fuente no encontrada')
        return Response(row['original'])

class Runs(ListAPIView):
    serializer_class=JobOutput
    def get_queryset(self):return jobs.visible_jobs(self.request.user)
    def post(self,request):
        data=RunInput(data=request.data);data.is_valid(raise_exception=True)
        job,created=jobs.enqueue(request.user,data.validated_data,request.request_id)
        return Response(JobOutput(job).data,status=202 if created else 200)

class RunDetail(APIView):
    def get(self,request,rid):
        job=jobs.visible_jobs(request.user).filter(id=rid).first()
        if job:
            result=JobOutput(job).data
            historical=KnowledgeRun.objects.filter(id=rid).first()
            if historical:result['result']={'status':historical.status,'payload':historical.payload}
            return Response(result)
        # Historical runs predate job ownership. Only the human administrator
        # may inspect them; a service token cannot claim arbitrary run IDs.
        if request.user.has_perm('team_backend.manage_jobs'):
            historical=KnowledgeRun.objects.filter(id=rid).first()
            if historical:return Response({'id':historical.id,'status':historical.status,'payload':historical.payload,'historical':True})
        raise NotFound()

class CancelRun(APIView):
    def post(self,request,rid):return Response(JobOutput(jobs.cancel(request.user,rid,request.request_id)).data)

class Memory(APIView):
    def get(self,request):return Response(memory.latest())

class ProposeMemory(APIView):
    def post(self,request):
        require(request.user,'propose_memory')
        data=ProposalInput(data=request.data);data.is_valid(raise_exception=True)
        result=memory.propose(**data.validated_data,author='user:'+str(request.user.pk),
            on_write=lambda connection,result: jobs.audit(request.user,'memory.proposed',result['id'],request.request_id,connection=connection))
        return Response(result,status=201)

class ConfirmMemory(APIView):
    def post(self,request,mid):
        require(request.user,'confirm_memory')
        if isinstance(request.auth,ApiCredential):raise PermissionDenied('La confirmación requiere una sesión humana con CSRF')
        data=ConfirmationInput(data=request.data);data.is_valid(raise_exception=True)
        result=memory.confirm(str(mid),data.validated_data['expected_version'],
            on_write=lambda connection,result: jobs.audit(request.user,'memory.confirmed',result['id'],request.request_id,connection=connection,version=result['version']))
        return Response(result)

class Integrity(APIView):
    def get(self,request):
        require(request.user,'manage_jobs')
        return Response(ingest.verify())

class Audit(ListAPIView):
    serializer_class=AuditOutput
    def get_queryset(self):
        require(self.request.user,'manage_jobs')
        return AuditEvent.objects.all()
