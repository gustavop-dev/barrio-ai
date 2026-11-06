"""Outbound-only authenticated relay for the owner's private Sites office.

A claimed command is never executed twice by this process. Delivery retries only
send the saved HTTP result, never the original command. No arbitrary URLs.
"""
import json
import os
import re
import time
import uuid
from pathlib import Path
from urllib.parse import quote
import httpx

class BridgeError(Exception):
    pass

def command_request(command):
    operation=command.get('operation');body=command.get('body')
    if not isinstance(body,dict):raise ValueError('Cuerpo inválido')
    if operation=='status':return 'GET','/api/v1/status',None
    if operation=='memory':return 'GET','/api/v1/memory',None
    if operation=='runs':return 'GET','/api/v1/runs?page_size=30',None
    if operation in ('unit','source'):
        identifier=body.get('id','')
        pattern=r'LI-0[1-6]-[A-Za-z0-9-]+' if operation=='unit' else r'0[1-6]:[A-Za-z0-9_-]+'
        if not isinstance(identifier,str) or not re.fullmatch(pattern,identifier):raise ValueError('Referencia inválida')
        return 'GET',('/api/v1/units/' if operation=='unit' else '/api/v1/sources/')+quote(identifier,safe=':'),None
    if operation in ('run','cancel','confirm'):
        identifier=str(uuid.UUID(body.get('id','')))
        if operation=='run':return 'GET','/api/v1/runs/'+identifier,None
        if operation=='cancel':return 'POST','/api/v1/runs/'+identifier+'/cancel',{}
        return 'POST','/api/v1/memory/'+identifier+'/confirm',{'expected_version':body.get('expected_version')}
    if operation=='search':
        return 'POST','/api/v1/search',{k:v for k,v in body.items() if k in ('query','agent','limit','mode')}
    if operation=='propose':
        return 'POST','/api/v1/memory/proposals',{k:v for k,v in body.items() if k in ('namespace','key','value','evidence','expected_version')}
    # 'runs' GET is separate from 'enqueue' to prevent ambiguous side effects.
    if operation=='enqueue':
        uuid.UUID(body.get('request_id',''))
        return 'POST','/api/v1/runs',{k:v for k,v in body.items() if k in ('agent','task','execute','mode','request_id')}
    raise ValueError('Operación no permitida')

class OfficeBridge:
    def __init__(self,local=None,remote=None):
        self.local=local or httpx.Client(base_url=os.environ.get('OFFICE_LOCAL_URL','http://127.0.0.1:8787'),
            headers={'Host':'localhost:8787'},timeout=130,follow_redirects=False)
        site=os.environ.get('OFFICE_SITE_URL','').rstrip('/')
        if not site.startswith('https://') and not site.startswith('http://127.0.0.1:'):raise ValueError('URL de oficina inválida')
        headers={'Authorization':'Bearer '+os.environ['OFFICE_BRIDGE_TOKEN']}
        if os.environ.get('OFFICE_SITE_ACCESS_TOKEN'):headers['OAI-Sites-Authorization']='Bearer '+os.environ['OFFICE_SITE_ACCESS_TOKEN']
        self.remote=remote or httpx.Client(base_url=site,headers=headers,timeout=30,follow_redirects=False)
        self.deliveries={}
        self.heartbeat=Path(os.environ.get('OFFICE_HEARTBEAT_FILE','/tmp/linkedin-office-bridge-heartbeat'))

    def close(self):self.local.close();self.remote.close()

    def ensure_session(self):
        response=self.local.get('/api/v1/status')
        if response.status_code==200:return response.json()
        if response.status_code!=401:raise BridgeError('Backend no disponible')
        response=self.local.get('/admin/login/')
        if response.status_code!=200 or not self.local.cookies.get('csrftoken'):raise BridgeError('No se pudo iniciar sesión local')
        response=self.local.post('/admin/login/',data={
            'username':os.environ['DJANGO_ADMIN_USERNAME'],'password':os.environ['DJANGO_ADMIN_PASSWORD'],
            'csrfmiddlewaretoken':self.local.cookies['csrftoken'],'next':'/admin/',
        })
        if response.status_code!=302:raise BridgeError('Credenciales locales no disponibles; revisar configuración del puente')
        response=self.local.get('/api/v1/status')
        if response.status_code!=200:raise BridgeError('Sesión local sin acceso')
        return response.json()

    def execute(self,command):
        try:
            method,path,payload=command_request(command)
        except (ValueError,TypeError,AttributeError):return 400,{'detail':'Solicitud de oficina inválida'}
        # No HTTP replay on timeout: the backend may have accepted an enqueue.
        try:
            response=self.local.request(method,path,json=payload if method=='POST' else None,
                headers={'X-CSRFToken':self.local.cookies.get('csrftoken','')})
            data=response.json()
            if len(json.dumps(data))>850000:return 502,{'detail':'Resultado demasiado grande para la oficina'}
            return response.status_code,data
        except (httpx.HTTPError,ValueError):
            return 502,{'detail':'No se pudo confirmar la respuesta del backend. Revisa el historial antes de reenviar.'}

    def deliver(self):
        for identifier,payload in list(self.deliveries.items()):
            response=self.remote.post('/api/office/bridge/result',json=payload)
            if response.status_code in (200,409):del self.deliveries[identifier]
            else:raise BridgeError('No se pudo entregar un resultado')

    def tick(self):
        self.deliver()
        summary=self.ensure_session()
        # No provider secrets or full prompt/results in the heartbeat.
        safe={k:summary[k] for k in ('units','chunks','embedding_cache','classes','usage','workers_alive','queue','live_providers') if k in summary}
        safe['backend_ok']=True
        response=self.remote.post('/api/office/bridge/poll',json={'summary':safe})
        if response.status_code!=200:raise BridgeError('La oficina no aceptó el enlace')
        packet=response.json()
        self.heartbeat.write_text(str(time.time()))
        for command in packet.get('requests',[]):
            identifier=command['id']
            if identifier not in self.deliveries:
                status,data=self.execute(command)
                self.deliveries[identifier]={'id':identifier,'claim':command['claim'],'status':status,'data':data}
        self.deliver()
        return min(10,max(1,int(packet.get('poll_after',2))))
