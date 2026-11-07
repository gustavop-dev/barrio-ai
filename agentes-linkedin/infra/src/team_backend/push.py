"""Web Push (VAPID) delivery to the office PWA. Failures never block the operator."""
import base64
import json
import logging
import os
from django.utils import timezone
from pywebpush import WebPushException, webpush
from .models import PushSubscription

logger=logging.getLogger('team_backend.push')
MAX_FAILURES=5

def public_key():
    return os.environ.get('VAPID_PUBLIC_KEY','').strip()

def configured():
    return bool(public_key() and os.environ.get('VAPID_PRIVATE_KEY','').strip())

def generate_keys():
    """Returns (public, private) as base64url strings for the private .env."""
    from cryptography.hazmat.primitives import serialization
    from py_vapid import Vapid
    vapid=Vapid();vapid.generate_keys()
    raw_public=vapid.public_key.public_bytes(serialization.Encoding.X962,serialization.PublicFormat.UncompressedPoint)
    raw_private=vapid.private_key.private_numbers().private_value.to_bytes(32,'big')
    encode=lambda b:base64.urlsafe_b64encode(b).rstrip(b'=').decode()
    return encode(raw_public),encode(raw_private)

def send(subscription,title,body,url='/maquina',tag='barrio'):
    payload=json.dumps({'title':title,'body':body,'url':url,'tag':tag},ensure_ascii=False)
    info={'endpoint':subscription.endpoint,'keys':{'p256dh':subscription.p256dh,'auth':subscription.auth}}
    try:
        webpush(info,payload,vapid_private_key=os.environ['VAPID_PRIVATE_KEY'].strip(),
                vapid_claims={'sub':os.environ.get('VAPID_SUBJECT','mailto:admin@localhost')},ttl=86400,timeout=10,
                headers={'Urgency':'high'})
    except WebPushException as exc:
        status=getattr(exc.response,'status_code',None)
        if status in (404,410):
            subscription.delete();return False  # The browser revoked this endpoint.
        PushSubscription.objects.filter(pk=subscription.pk).update(failures=subscription.failures+1)
        logger.warning('push_failed status=%s',status);return False
    except Exception:
        PushSubscription.objects.filter(pk=subscription.pk).update(failures=subscription.failures+1)
        logger.warning('push_failed unexpected');return False
    PushSubscription.objects.filter(pk=subscription.pk).update(failures=0,last_success_at=timezone.now())
    return True

def broadcast(title,body,url='/maquina',tag='barrio',users=None):
    if not configured():return 0
    subscriptions=PushSubscription.objects.filter(failures__lt=MAX_FAILURES,user__is_active=True)
    if users is not None:subscriptions=subscriptions.filter(user__in=users)
    return sum(send(s,title,body,url,tag) for s in subscriptions)
