"""Alerts for the human on the loop: pauses, degradations and stops.
OPERATOR_ALERT_WEBHOOK accepts an ntfy topic URL (plain text + Title header) or any
Slack-compatible webhook ({"text": ...}). Delivery failures never block the operator."""
import logging
import os
import httpx

logger=logging.getLogger('team_backend.alerts')

def notify(title,message):
    url=os.environ.get('OPERATOR_ALERT_WEBHOOK','').strip()
    if not url:return False
    try:
        with httpx.Client(timeout=10.0) as client:
            if 'ntfy' in url:response=client.post(url,content=message.encode(),headers={'Title':title,'Priority':'high'})
            else:response=client.post(url,json={'text':f'{title}\n{message}'})
        return response.status_code<400
    except httpx.HTTPError:
        logger.warning('alert_delivery_failed title=%s',title)
        return False
