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
from knowledge.clases import CLASES_BIBLIOTECA,rango
from . import alcance,hechos,jobs,miembros
from .models import KnowledgeUnit,KnowledgeRun,Worker,AuditEvent,ApiCredential
from .permissions import require
from .serializers import SearchInput,RunInput,JobOutput,UnitOutput,ProposalInput,ConfirmationInput,AuditOutput

def health(request):
    with connection.cursor() as cursor:cursor.execute('SELECT 1')
    # `revision`: the commit of the deployed image (empty outside CI images); eas-update.yml waits for it.
    return JsonResponse({'status':'ok','framework':'django','revision':os.environ.get('BARRIO_REVISION','')})

@ensure_csrf_cookie
def console(request):
    return HttpResponse(Path(retrieval.__file__).with_name('console.html').read_text())

class Status(APIView):
    def get(self,request):
        result=db.status()
        result.update(framework='django',embedding_plan=providers.index(False),
            live_providers=os.environ.get('LIVE_PROVIDERS','false')=='true',
            credentials={p:bool(os.environ.get(p.upper()+'_API_KEY')) for p in ['openai','anthropic']},
            queue={state:alcance.trabajos(request).filter(state=state).count() for state in jobs.Job.State.values},
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
            if session not in [str(n) for n in CLASES_BIBLIOTECA]:raise ValueError(f'Clase fuera de la biblioteca ({rango(CLASES_BIBLIOTECA)})')
            qs=qs.filter(session=int(session))
        return qs

class UnitDetail(APIView):
    def get(self,request,uid):
        if not KnowledgeUnit.objects.filter(id=uid,active=True).exists():raise NotFound('Unidad no encontrada')
        # Consulta de la biblioteca, no contexto de un agente: muestra todas sus relaciones.
        return Response(retrieval.unit(uid,clases=CLASES_BIBLIOTECA))

class SourceDetail(APIView):
    def get(self,request,key):
        with db.connect() as c:row=c.execute('SELECT original FROM evidence WHERE key=%s',(key,)).fetchone()
        if not row:raise NotFound('Fuente no encontrada')
        return Response(row['original'])

class Runs(ListAPIView):
    serializer_class=JobOutput
    def get_queryset(self):return alcance.trabajos(self.request)  # hers; never another member's
    def post(self,request):
        data=RunInput(data=request.data);data.is_valid(raise_exception=True)
        job,created=jobs.enqueue(request.user,data.validated_data,request.request_id)
        return Response(JobOutput(job).data,status=202 if created else 200)

class RunDetail(APIView):
    def get(self,request,rid):
        job=alcance.trabajos(request).filter(id=rid).first()
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
    def post(self,request,rid):
        if not alcance.trabajos(request).filter(id=rid).exists():raise NotFound()  # another member's job looks missing
        return Response(JobOutput(jobs.cancel(request.user,rid,request.request_id)).data)

def _memory_scopes(request):
    """(her prefix, her organization's prefix) or None without members (every key, as before)."""
    member=alcance.miembro(request)
    if member is None:return None
    return hechos.scope(member),hechos.organization_scope(member.organization)

def _readable(key,scopes):
    return scopes is None or memory.in_scope(key,scopes[0]) or key.startswith(scopes[1])

class Memory(APIView):
    """The raw memory console: her keys and her organization's, as stored; never another member's."""
    def get(self,request):
        scopes=_memory_scopes(request)
        return Response([row for row in memory.latest() if _readable(row['key'],scopes)])

class ProposeMemory(APIView):
    def post(self,request):
        require(request.user,'propose_memory')
        data=ProposalInput(data=request.data);data.is_valid(raise_exception=True)
        values=dict(data.validated_data);scopes=_memory_scopes(request)
        if scopes is not None:
            # She proposes into her own memory only: a prefixed key would write someone else's or the company's.
            if memory.SCOPED.match(values['key']):raise PermissionDenied('Esa clave no es tuya: propón la clave sin prefijo.')
            values['key']=scopes[0]+values['key']
        result=memory.propose(**values,author='user:'+str(request.user.pk),
            on_write=lambda connection,result: jobs.audit(request.user,'memory.proposed',result['id'],request.request_id,connection=connection))
        return Response(result,status=201)

class ConfirmMemory(APIView):
    def post(self,request,mid):
        require(request.user,'confirm_memory')
        if isinstance(request.auth,ApiCredential):raise PermissionDenied('La confirmación requiere una sesión humana con CSRF')
        scopes=_memory_scopes(request)
        if scopes is not None:  # the fact first: another member's answers 404 whatever the body says
            with db.connect() as c:row=c.execute('SELECT key FROM memory WHERE id=%s',(str(mid),)).fetchone()
            if row is None or not memory.in_scope(row['key'],scopes[0]):raise NotFound()  # only her own facts
        data=ConfirmationInput(data=request.data);data.is_valid(raise_exception=True)
        result=memory.confirm(str(mid),data.validated_data['expected_version'],
            on_write=lambda connection,result: jobs.audit(request.user,'memory.confirmed',result['id'],request.request_id,connection=connection,version=result['version']))
        return Response(result)

class Integrity(APIView):
    def get(self,request):
        require(request.user,'manage_jobs')
        return Response(ingest.verify())

class Audit(ListAPIView):
    """The installation's audit trail, for its admin. Never another member's own actions (their metadata can carry her
    private notes, e.g. a conversation's closing note): organizaciones, phase 5. With one member, everything as before."""
    serializer_class=AuditOutput
    def get_queryset(self):
        require(self.request.user,'manage_jobs')
        rows=AuditEvent.objects.all()
        member=miembros.member_of_user(self.request.user)
        if member is not None:
            rows=rows.exclude(actor_id__in=miembros._models()[1].objects.exclude(pk=member.pk).values('user_id'))
        return rows
