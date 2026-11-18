"""Alerts for the human on the loop: pauses, degradations, uncertain actions and stops.
Delivered as Web Push to the office PWA, as native push to the mobile app (Expo) and, optionally, to
OPERATOR_ALERT_WEBHOOK (ntfy topic URL or Slack-compatible webhook). Delivery failures never block the operator."""
import logging
import os
import httpx

logger=logging.getLogger('team_backend.alerts')

def notify(title,message,url='/maquina',tag='barrio-alerta',urgent=False,users=None,webhook=True):
    """Push to `users`' devices (None: every device, an installation without members) and, with `webhook`, to
    OPERATOR_ALERT_WEBHOOK (the first member's channel: notificaciones.avisar never sends another member's notice there)."""
    delivered=False
    try:
        from .push import broadcast
        delivered=broadcast(title,message,url=url,tag=tag,users=users)>0
    except Exception:
        logger.warning('alert_push_failed title=%s',title)
    try:
        from . import expo
        delivered=expo.broadcast(title,message,url=url,tag=tag,urgent=urgent,users=users)>0 or delivered
    except Exception:
        logger.warning('alert_expo_failed title=%s',title)
    webhook=os.environ.get('OPERATOR_ALERT_WEBHOOK','').strip() if webhook else ''
    if webhook:
        try:
            with httpx.Client(timeout=10.0) as client:
                if 'ntfy' in webhook:response=client.post(webhook,content=message.encode(),headers={'Title':title,'Priority':'high'})
                else:response=client.post(webhook,json={'text':f'{title}\n{message}'})
            delivered=delivered or response.status_code<400
        except httpx.HTTPError:
            logger.warning('alert_webhook_failed title=%s',title)
    return delivered
