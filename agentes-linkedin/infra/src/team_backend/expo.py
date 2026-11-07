"""Native push of the 0ff1ce mobile app through Expo's push service (docs/app-movil-backend.md).

Same events, title, body and per-kind switches as the Web Push of the PWA: alerts.notify calls both. No account is
needed for basic use; EXPO_ACCESS_TOKEN is sent only when set (Expo's enhanced push security). Failures never block
the work that triggered the push: everything here logs and returns 0 instead of raising."""
import logging
import os
import re
from datetime import datetime, timedelta
import httpx
from django.db.models import Max, Q
from django.utils import timezone
from .models import ExpoPushToken

logger=logging.getLogger('team_backend.expo')
SEND_URL='https://exp.host/--/api/v2/push/send'
RECEIPTS_URL='https://exp.host/--/api/v2/push/getReceipts'
BATCH=100                            # messages per send request (Expo's limit)
RECEIPT_BATCH=1000                   # ticket ids per receipts request (Expo's limit)
RECEIPT_AFTER=timedelta(minutes=15)  # Expo recommends asking for receipts after about 15 minutes...
RECEIPT_TTL=timedelta(hours=24)      # ...and clears them after 24 hours
MAX_TICKETS=50                       # pending tickets kept per token
CHANNEL='default'                    # Android notification channel the app creates
TTL=86400                            # seconds Expo keeps trying, as the Web Push (push.send)
TOKEN_FORMAT=re.compile(r'^Expo(nent)?PushToken\[[^\[\]\s]{1,180}\]$')
TRANSPORT=None  # tests inject an httpx.MockTransport; production uses the default transport

def valid_token(value):
    return bool(TOKEN_FORMAT.match(value or ''))

def _client():
    headers={'Accept':'application/json','Accept-Encoding':'gzip, deflate','Content-Type':'application/json'}
    access=os.environ.get('EXPO_ACCESS_TOKEN','').strip()
    if access:headers['Authorization']=f'Bearer {access}'
    return httpx.Client(transport=TRANSPORT,headers=headers,timeout=httpx.Timeout(10.0,connect=5.0))

def targets(users=None):
    """Active tokens of active users whose device login, when there is one, was not revoked."""
    tokens=(ExpoPushToken.objects.filter(active=True,user__is_active=True)
            .filter(Q(device__isnull=True)|Q(device__revoked_at__isnull=True)).order_by('created_at'))
    return tokens.filter(user__in=users) if users is not None else tokens

def message(token,title,body,url,tag,urgent=False):
    return {'to':token,'title':title,'body':body,'data':{'url':url,'tag':tag},'channelId':CHANNEL,
            'priority':'high' if urgent else 'default','sound':'default','ttl':TTL}

def deactivate(pks,reason):
    return ExpoPushToken.objects.filter(pk__in=pks).update(active=False,last_error=reason[:80],tickets=[],updated_at=timezone.now())

def status(user):
    """Ajustes › Dispositivos con la app: how many of the user's Expo tokens receive push, and the last delivery."""
    tokens=targets([user])
    last_error=tokens.exclude(last_error='').order_by('-updated_at').values_list('last_error',flat=True).first()
    return {'active':tokens.count(),'last_success_at':tokens.aggregate(at=Max('last_success_at'))['at'],'last_error':last_error or ''}

def _json(response):
    try:data=response.json()
    except ValueError:return {}
    return data if isinstance(data,dict) else {}

def _error(item):
    details=item.get('details') if isinstance(item,dict) else None
    return str((details.get('error') if isinstance(details,dict) else '') or 'error')

def _post(http,url,payload):
    """POST to Expo; returns the JSON body, or None after logging a network or request-level error."""
    try:response=http.post(url,json=payload)
    except httpx.HTTPError as exc:
        logger.warning('expo_request_failed url=%s kind=%s',url.rsplit('/',1)[-1],type(exc).__name__);return None
    data=_json(response)
    if response.status_code>=400:
        codes=','.join(str(e.get('code','')) for e in data.get('errors') or [] if isinstance(e,dict))
        logger.warning('expo_request_failed url=%s status=%s codes=%s',url.rsplit('/',1)[-1],response.status_code,codes);return None
    return data

def _send(http,tokens,title,body,url,tag,urgent,now):
    data=_post(http,SEND_URL,[message(t.token,title,body,url,tag,urgent) for t in tokens])
    tickets=data.get('data') if data else None
    if not isinstance(tickets,list):return 0
    accepted=0
    for token,ticket in zip(tokens,tickets):
        if isinstance(ticket,dict) and ticket.get('status')=='ok':
            accepted+=1
            pending=list(token.tickets or [])+([[str(ticket['id']),now.isoformat()]] if ticket.get('id') else [])
            ExpoPushToken.objects.filter(pk=token.pk).update(last_success_at=now,last_error='',tickets=pending[-MAX_TICKETS:])
            continue
        error=_error(ticket)
        if error=='DeviceNotRegistered':deactivate([token.pk],error)  # the app was uninstalled or the token rotated
        else:ExpoPushToken.objects.filter(pk=token.pk).update(last_error=error[:80],updated_at=now)
        logger.warning('expo_push_ticket_error error=%s',error)
    return accepted

def _sent_at(value):
    try:return datetime.fromisoformat(value)
    except (TypeError,ValueError):return None

def check_receipts(http,now=None):
    """Receipts of the tickets older than 15 minutes: DeviceNotRegistered deactivates the token. Tickets older than 24 h
    are dropped (Expo no longer has them); the rest wait for the next push. Returns how many tokens it deactivated."""
    now=now or timezone.now();due={};kept={}
    for token in ExpoPushToken.objects.filter(active=True).exclude(tickets=[]):
        kept[token.pk]=(token,[])
        for item in token.tickets:
            sent=_sent_at(item[1]) if isinstance(item,list) and len(item)==2 else None
            if sent is None or now-sent>RECEIPT_TTL:continue
            if now-sent>=RECEIPT_AFTER:due[item[0]]=token.pk
            kept[token.pk][1].append(item)
    dead=set();ids=list(due)
    for start in range(0,len(ids),RECEIPT_BATCH):
        data=_post(http,RECEIPTS_URL,{'ids':ids[start:start+RECEIPT_BATCH]})
        receipts=data.get('data') if data else None
        if not isinstance(receipts,dict):continue
        for ticket_id,receipt in receipts.items():
            pk=due.get(ticket_id)
            if pk is None:continue
            token,items=kept[pk];kept[pk]=(token,[i for i in items if i[0]!=ticket_id])
            if isinstance(receipt,dict) and receipt.get('status')=='error':
                error=_error(receipt)
                if error=='DeviceNotRegistered':dead.add(pk)
                else:ExpoPushToken.objects.filter(pk=pk).update(last_error=error[:80],updated_at=now)
                logger.warning('expo_push_receipt_error error=%s',error)
    for pk,(token,items) in kept.items():
        if items!=token.tickets:ExpoPushToken.objects.filter(pk=pk).update(tickets=items)
    return deactivate(dead,'DeviceNotRegistered') if dead else 0

def broadcast(title,body,url='/',tag='0ff1ce',users=None,urgent=False):
    """Send one notification to every target, in batches of 100, then check older receipts.
    Returns how many messages Expo accepted. Never raises."""
    try:
        tokens=list(targets(users))
        if not tokens:return 0
        now=timezone.now();accepted=0
        with _client() as http:
            for start in range(0,len(tokens),BATCH):
                accepted+=_send(http,tokens[start:start+BATCH],title,body,url,tag,urgent,now)
            try:check_receipts(http,now)
            except Exception:logger.warning('expo_receipts_failed unexpected')
        return accepted
    except Exception:
        logger.warning('expo_push_failed unexpected');return 0
