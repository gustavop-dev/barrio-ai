"""HTTP API of the capture button, the Galería and office preferences (docs/capturas-galeria.md).
Writes need a human session (no service token) and `approve_actions`; reads need `operate_linkedin`.
Files are private: they are only streamed by these authenticated views, with `Cache-Control: private`."""
import re
from django.conf import settings
from django.http import FileResponse, HttpResponse
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import APIException, NotFound, ValidationError
from rest_framework.generics import ListAPIView
from rest_framework.negotiation import BaseContentNegotiation
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from . import capturas
from .jobs import audit
from .models import AIEdit, Capture, GalleryPhoto, OfficePreference
from .operador_views import get_or_404, human_session, valid
from .permissions import require

RANGE=re.compile(r'bytes=(\d*)-(\d*)$')
GALLERY_FILTERS={'todas':None,'sin_usar':['sin_usar'],'elegidas':['elegida','editada'],'publicadas':['publicada'],'perfil':None}

class TooLarge(APIException):
    status_code=413
    default_detail='El envío es demasiado grande.'

class AnyAccept(BaseContentNegotiation):
    """<img> and <audio> send their own Accept headers; files ignore content negotiation (errors stay JSON)."""
    def select_parser(self,request,parsers):return parsers[0]
    def select_renderer(self,request,renderers,format_suffix=None):return renderers[0],renderers[0].media_type

def _limit_body(request,limit):
    try:length=int(request.META.get('CONTENT_LENGTH') or 0)
    except ValueError:length=0
    if length>limit:raise TooLarge()

def serve(request,fieldfile,mime,ranges=False):
    """Stream a private file. Audio answers single byte ranges: Safari will not play media without them."""
    try:
        size=fieldfile.size;handle=fieldfile.open('rb')
    except (FileNotFoundError,ValueError):raise NotFound('El archivo ya no está disponible.') from None
    match=RANGE.match(request.headers.get('Range','')) if ranges else None
    if match and (match.group(1) or match.group(2)):
        first,last=match.groups()
        if first:start=int(first);end=min(int(last),size-1) if last else size-1
        else:start=max(0,size-int(last));end=size-1
        if start>end or start>=size:
            handle.close()
            response=HttpResponse(status=416);response['Content-Range']=f'bytes */{size}'
            return response
        handle.seek(start);data=handle.read(end-start+1);handle.close()
        response=HttpResponse(data,status=206,content_type=mime);response['Content-Range']=f'bytes {start}-{end}/{size}'
    else:
        response=FileResponse(handle,content_type=mime)
    response['Accept-Ranges']='bytes' if ranges else 'none'
    response['Cache-Control']='private, max-age=3600'
    response['Content-Disposition']='inline'
    response['Content-Security-Policy']="default-src 'none'; sandbox"
    response['X-Content-Type-Options']='nosniff'
    return response

class FileView(APIView):
    """Images and audio are many small authenticated reads (a gallery grid): no API throttle, any Accept."""
    throttle_classes=[]
    content_negotiation_class=AnyAccept

# --------------------------------------------------------------------------- serializers

class CaptureInput(serializers.Serializer):
    ai_edit=serializers.ChoiceField(choices=AIEdit.values,required=False)
    nota=serializers.CharField(required=False,allow_blank=True,max_length=capturas.NOTE_MAX)
    para=serializers.ChoiceField(choices=Capture.Purpose.values,required=False,allow_blank=True)
    contexto_tipo=serializers.ChoiceField(choices=Capture.Context.values,required=False,allow_blank=True)
    contexto_id=serializers.CharField(required=False,allow_blank=True,max_length=64)
    public_use=serializers.BooleanField(required=False,allow_null=True,default=None)
    audio_duration_s=serializers.FloatField(required=False,allow_null=True,min_value=0,max_value=1800,
                                            error_messages={'max_value':'El audio puede durar como mucho 30 minutos.'})

    def validate(self,attrs):
        if any(key.startswith('publish_asap') for key in self.initial_data):
            raise serializers.ValidationError('La prioridad se interpreta de la nota o transcripción; no es un campo editable.')
        return attrs

class CaptureOutput(serializers.BaseSerializer):
    def to_representation(self,obj):return capturas.capture_payload(obj)

class PhotoOutput(serializers.BaseSerializer):
    def to_representation(self,obj):return capturas.photo_payload(obj)

class PhotoPatch(serializers.Serializer):
    category=serializers.ChoiceField(choices=['posts','perfil'],required=False)
    profile_edit=serializers.BooleanField(required=False)
    profile_role=serializers.ChoiceField(choices=['','01','02','03'],required=False)
    ai_edit=serializers.ChoiceField(choices=AIEdit.values,required=False)
    note=serializers.CharField(required=False,allow_blank=True,max_length=2000)
    allow_ai_edit=serializers.BooleanField(required=False)

class PreferencesInput(serializers.Serializer):
    gallery_ai_edit=serializers.ChoiceField(choices=AIEdit.values,required=False)
    gallery_ai_edit_default=serializers.BooleanField(required=False)
    push_disabled=serializers.ListField(child=serializers.CharField(max_length=40),required=False,max_length=40)
    push_enabled=serializers.ListField(child=serializers.CharField(max_length=40),required=False,max_length=40)

# --------------------------------------------------------------------------- captures

class Captures(ListAPIView):
    """GET: history of «Lo que enviaste», newest first (undone ones are hidden). POST (multipart): a new capture."""
    serializer_class=CaptureOutput
    parser_classes=[MultiPartParser,FormParser]
    def get_queryset(self):
        require(self.request.user,'operate_linkedin')
        capturas.reconcile_stale();capturas.expire_ideas()
        qs=Capture.objects.exclude(state=Capture.State.UNDONE).prefetch_related('photos')
        state=self.request.query_params.get('estado')
        return qs.filter(state=state) if state else qs
    def post(self,request):
        human_session(request);require(request.user,'approve_actions')
        _limit_body(request,settings.CAPTURE_AUDIO_MAX_BYTES+settings.GALLERY_MAX_PHOTOS_PER_REQUEST*settings.GALLERY_PHOTO_MAX_BYTES+1024*1024)
        data=valid(CaptureInput,request)
        capture=capturas.create(request.user,data,request.FILES.get('audio'),request.FILES.getlist('fotos'))
        return Response(CaptureOutput(capture).data,status=201)

class CaptureDetail(APIView):
    def get(self,request,cid):
        require(request.user,'operate_linkedin');capturas.reconcile_stale()
        return Response(CaptureOutput(get_or_404(Capture,id=cid)).data)
    def delete(self,request,cid):
        """«Deshacer» within 2 minutes; 409 afterwards."""
        human_session(request);require(request.user,'approve_actions');get_or_404(Capture,id=cid)
        return Response(CaptureOutput(capturas.undo(request.user,cid)).data)

class CaptureAudio(FileView):
    def get(self,request,cid):
        require(request.user,'operate_linkedin')
        capture=get_or_404(Capture,id=cid)
        if not capture.audio:raise NotFound('Esta captura no tiene audio.')
        return serve(request,capture.audio,capture.audio_mime or 'application/octet-stream',ranges=True)

# --------------------------------------------------------------------------- Galería

class Gallery(ListAPIView):
    """GET ?filtro=todas|sin_usar|elegidas|publicadas, newest first. POST (multipart `fotos`): upload photos."""
    serializer_class=PhotoOutput
    parser_classes=[MultiPartParser,FormParser]
    def get_queryset(self):
        require(self.request.user,'operate_linkedin')
        key=self.request.query_params.get('filtro') or 'todas'
        if key not in GALLERY_FILTERS:raise ValidationError({'filtro':'Usa todas, sin_usar, elegidas, publicadas o perfil.'})
        qs=GalleryPhoto.objects.select_related('chosen_piece')
        if key=='perfil':return qs.filter(category='perfil')
        return qs.filter(state__in=GALLERY_FILTERS[key]) if GALLERY_FILTERS[key] else qs
    def post(self,request):
        human_session(request);require(request.user,'approve_actions')
        _limit_body(request,settings.GALLERY_MAX_PHOTOS_PER_REQUEST*settings.GALLERY_PHOTO_MAX_BYTES+1024*1024)
        # DRF maps omitted multipart booleans to False unless partial=True. Preserve
        # the posts preference and let category=perfil grant its separate scoped consent.
        serializer=PhotoPatch(data=request.data,partial=True);serializer.is_valid(raise_exception=True)
        photos=capturas.add_photos(request.user,request.FILES.getlist('fotos'),serializer.validated_data)
        now=timezone.now()
        return Response([capturas.photo_payload(p,now) for p in photos],status=201)

class PhotoDetail(APIView):
    def get(self,request,pid):
        require(request.user,'operate_linkedin')
        return Response(PhotoOutput(get_or_404(GalleryPhoto,id=pid)).data)
    def patch(self,request,pid):
        human_session(request);require(request.user,'approve_actions')
        serializer=PhotoPatch(data=request.data,partial=True);serializer.is_valid(raise_exception=True)
        data=serializer.validated_data;photo=get_or_404(GalleryPhoto,id=pid)
        from .perfil_galeria import update
        photo=update(request.user,photo,data)
        return Response(PhotoOutput(photo).data)
    def delete(self,request,pid):
        human_session(request);require(request.user,'approve_actions')
        capturas.delete_photo(request.user,get_or_404(GalleryPhoto,id=pid))
        return Response(status=204)

class PhotoImage(FileView):
    def get(self,request,pid):
        require(request.user,'operate_linkedin')
        photo=get_or_404(GalleryPhoto,id=pid)
        return serve(request,photo.image,photo.mime)

# --------------------------------------------------------------------------- preferences

def _preferences():
    current=OfficePreference.current()
    return {'gallery_ai_edit':current.gallery_ai_edit,'gallery_ai_edit_default':current.gallery_ai_edit_default,'push_disabled':current.push_disabled,'push_enabled':current.push_enabled,
            'updated_at':current.updated_at}

class Preferences(APIView):
    """Ajustes → «El equipo puede editar mis fotos con IA» (default of each new photo) and the push switch of each kind
    (push_disabled: turned off; push_enabled: turned on although off by default)."""
    def get(self,request):
        require(request.user,'operate_linkedin')
        return Response(_preferences())
    def patch(self,request):
        human_session(request);require(request.user,'approve_actions')
        data=valid(PreferencesInput,request);current=OfficePreference.current()
        if not data:raise ValidationError('Envía gallery_ai_edit_default, push_disabled o push_enabled')
        if 'gallery_ai_edit_default' in data:current.gallery_ai_edit_default=data['gallery_ai_edit_default']
        if 'gallery_ai_edit' in data and 'gallery_ai_edit_default' in data:raise ValidationError('Envía solo gallery_ai_edit')
        if 'gallery_ai_edit' in data:current.gallery_ai_edit=data['gallery_ai_edit']
        if 'push_disabled' in data or 'push_enabled' in data:
            from .notificaciones import FEED_KINDS, INBOX_KINDS
            off=set(data.get('push_disabled') or []);on=set(data.get('push_enabled') or [])
            unknown=sorted(k for k in off|on if k not in INBOX_KINDS and k not in FEED_KINDS)
            if unknown:raise ValidationError(f'Tipos de aviso desconocidos: {", ".join(unknown)}')
            if off&on:raise ValidationError(f'Un tipo no puede estar encendido y apagado a la vez: {", ".join(sorted(off&on))}')
            # A client that sends one list only (older apps send push_disabled) keeps the other, minus what it moved.
            if 'push_disabled' not in data:off=set(current.push_disabled or [])-on
            if 'push_enabled' not in data:on=set(current.push_enabled or [])-off
            current.push_disabled=sorted(off);current.push_enabled=sorted(on)
        current.updated_by=request.user;current.updated_at=timezone.now();current.save()
        audit(request.user,'office.preferences',1,gallery_ai_edit_default=current.gallery_ai_edit_default,push_disabled=current.push_disabled,
              push_enabled=current.push_enabled)
        return Response(_preferences())
