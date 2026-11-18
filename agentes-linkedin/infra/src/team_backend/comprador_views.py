"""HTTP API of phase 6 of the buyer's system (docs/plan-outbound.md, BAR-23; oficina/CONTRATO-API.md «Comprador»).

POST /api/v1/comprador/calcom/webhook: Cal.com's booking webhook. Anonymous, signed (X-Cal-Signature-256); without
  CALCOM_WEBHOOK_SECRET every call is rejected (agenda_calcom.receive).
POST /api/v1/comprador/respuestas/<id>/agendo {note?}: «Agendó» on her reply card (agenda_calcom.manual).
POST /api/v1/comprador/respuestas/<id>/referido {note}: «Pegar su perfil» of the person she named (respuesta_comprador).
POST /api/v1/comprador/reservas/<id>/emparejar {recorrido} | {descartar: true}: a booking nobody matched.
GET  /api/v1/comprador/entregas?estado=&fuente=: the leads handed over (read-only, source-neutral; entrega_lead).
GET  /api/v1/comprador/entregas/<id>: one of them.
POST /api/v1/comprador/entregas/<id>/oportunidad: «Crear la oportunidad», Gustavo's one tap (PRS-09).
GET  /api/v1/comprador/lectura-semanal: the funnel's weekly reading (lectura_embudo), read-only.

Every route is the member's (organizaciones, phase 5; alcance): her drafts, bookings, handoffs and buyers; another
member's id answers 404. The webhook is a service with its own signature."""
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from . import alcance, agenda_calcom, entrega_lead, lectura_embudo, respuesta_comprador
from .models import BuyerDraft, BuyerJourney, LeadHandoff, MeetingBooking
from .operador_views import human_session
from .permissions import require

def _note(request,required=False,limit=1000):
    data=request.data if isinstance(request.data,dict) else {}
    note=data.get('note') or ''
    if not isinstance(note,str) or len(note)>limit:raise ValidationError(f'note debe ser un texto de hasta {limit} caracteres')
    if required and not note.strip():raise ValidationError('note es obligatorio')
    return note

class CalcomWebhook(APIView):
    """Cal.com posts here; no session, no CSRF: the HMAC signature is the only credential."""
    authentication_classes=[];permission_classes=[AllowAny]
    def post(self,request):
        raw=request.body  # the exact bytes Cal.com signed, read before any parsing
        status,body=agenda_calcom.receive(raw,request.headers.get('X-Cal-Signature-256',''))
        return Response(body,status=status)

class ReplyBooked(APIView):
    def post(self,request,did):
        human_session(request);alcance.obtener(request,BuyerDraft,id=did,kind=BuyerDraft.Kind.REPLY)
        booking=agenda_calcom.manual(request.user,did,_note(request))
        return Response({'reserva':str(booking.pk),'estado':booking.state,'inicio':booking.start_at})

class ReplyReferral(APIView):
    def post(self,request,did):
        human_session(request);alcance.obtener(request,BuyerDraft,id=did,kind=BuyerDraft.Kind.REPLY)
        row=respuesta_comprador.set_referral(request.user,did,_note(request,required=True,limit=500))
        return Response({'id':str(row.pk),'referido':(row.inputs or {}).get('referido')})

class BookingMatch(APIView):
    def post(self,request,bid):
        human_session(request);alcance.obtener(request,MeetingBooking,pk=bid)
        data=request.data if isinstance(request.data,dict) else {}
        discard=data.get('descartar') is True
        if not discard and not isinstance(data.get('recorrido'),str):raise ValidationError('recorrido o descartar')
        if not discard:alcance.obtener(request,BuyerJourney,pk=data['recorrido'])  # only one of her buyers
        booking=agenda_calcom.associate(request.user,bid,data.get('recorrido'),discard=discard)
        return Response({'reserva':str(booking.pk),'estado':booking.state,'emparejada_por':booking.matched_by,
                         'recorrido':str(booking.journey_id) if booking.journey_id else None})

class Handoffs(APIView):
    def get(self,request):
        require(request.user,'operate_linkedin')
        params=request.query_params
        return Response({'items':entrega_lead.listing(params.get('estado'),params.get('fuente'),member=alcance.miembro(request))})

class HandoffDetail(APIView):
    def get(self,request,hid):
        require(request.user,'operate_linkedin')
        return Response(entrega_lead.payload(alcance.obtener(request,LeadHandoff,pk=hid)))

class HandoffOpportunity(APIView):
    def post(self,request,hid):
        human_session(request)
        alcance.obtener(request,LeadHandoff,pk=hid)
        return Response(entrega_lead.payload(entrega_lead.confirm(request.user,hid)))

class WeeklyReading(APIView):
    def get(self,request):
        require(request.user,'operate_linkedin')
        reading=lectura_embudo.read(accounts=alcance.accounts(alcance.miembro(request)))  # her buyers
        return Response(dict(reading,activa=respuesta_comprador.enabled()))
