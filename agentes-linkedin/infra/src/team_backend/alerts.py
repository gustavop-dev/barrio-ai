"""Alerts for the human on the loop: pauses, degradations, uncertain actions and stops.
Delivered as Web Push to the office PWA and, optionally, to OPERATOR_ALERT_WEBHOOK
(ntfy topic URL or Slack-compatible webhook). Delivery failures never block the operator."""
import logging
import os
import httpx

logger=logging.getLogger('team_backend.alerts')

def notify(title,message,url='/maquina',tag='barrio-alerta'):
    delivered=False
    try:
        from .push import broadcast
        delivered=broadcast(title,message,url=url,tag=tag)>0
    except Exception:
        logger.warning('alert_push_failed title=%s',title)
    webhook=os.environ.get('OPERATOR_ALERT_WEBHOOK','').strip()
    if webhook:
        try:
            with httpx.Client(timeout=10.0) as client:
                if 'ntfy' in webhook:response=client.post(webhook,content=message.encode(),headers={'Title':title,'Priority':'high'})
                else:response=client.post(webhook,json={'text':f'{title}\n{message}'})
            delivered=delivered or response.status_code<400
        except httpx.HTTPError:
            logger.warning('alert_webhook_failed title=%s',title)
    return delivered
