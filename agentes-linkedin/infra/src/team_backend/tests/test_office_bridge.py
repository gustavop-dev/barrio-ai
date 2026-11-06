"""Office adapter contracts without network or writes to the operational DB."""
import json
import os
import tempfile
import uuid
from pathlib import Path
from unittest.mock import patch
import httpx
from django.test import SimpleTestCase
from team_backend.office_bridge import OfficeBridge,command_request,BridgeError

class OfficeBridgeTests(SimpleTestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'OFFICE_SITE_URL':'https://office.test','OFFICE_BRIDGE_TOKEN':'test-key','OFFICE_SITE_ACCESS_TOKEN':'','DJANGO_ADMIN_USERNAME':'test-owner','DJANGO_ADMIN_PASSWORD':'test-only'})
        self.env.start();self.addCleanup(self.env.stop)
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)

    def bridge(self,local_handler,remote_handler):
        local=httpx.Client(base_url='http://localhost:8787',transport=httpx.MockTransport(local_handler))
        remote=httpx.Client(base_url='https://office.test',transport=httpx.MockTransport(remote_handler))
        bridge=OfficeBridge(local,remote);bridge.heartbeat=Path(self.temp.name)/'heartbeat'
        self.addCleanup(bridge.close)
        return bridge

    def test_arbitrary_backend_urls_rejected(self):
        """Reject operations that could turn the local relay into an admin/SSRF proxy."""
        with self.assertRaises(ValueError):command_request({'operation':'http://127.0.0.1/admin','body':{}})
        with self.assertRaises(ValueError):command_request({'operation':'unit','body':{'id':'../../admin'}})

    def test_enqueue_retains_idempotency_and_drops_spoofed_owner(self):
        """Retain the caller's stable job UUID while preventing injected identity or endpoints."""
        rid=str(uuid.uuid4())
        method,path,data=command_request({'operation':'enqueue','body':{'request_id':rid,'agent':'perfil','task':'Review','execute':False,'owner':999,'url':'evil'}})
        self.assertEqual((method,path),('POST','/api/v1/runs'))
        self.assertEqual(data,{'request_id':rid,'agent':'perfil','task':'Review','execute':False})

    def test_missing_enqueue_uuid_cannot_create_ambiguous_retry(self):
        """Every remote enqueue needs an explicit stable id before touching Django."""
        with self.assertRaises(ValueError):command_request({'operation':'enqueue','body':{'agent':'perfil','task':'Review'}})

    def test_delivery_retry_never_reexecutes_django(self):
        """A failed response upload retries delivery of the saved result, never paid work."""
        rid=str(uuid.uuid4());claim=str(uuid.uuid4());local_requests=[];deliveries=[]
        def local(req):
            local_requests.append(req.url.path)
            if req.url.path=='/api/v1/status':return httpx.Response(200,json={'units':1035,'workers_alive':1})
            return httpx.Response(202,json={'id':rid,'status':'queued'})
        def remote(req):
            if req.url.path.endswith('/poll'):
                return httpx.Response(200,json={'requests':[{'id':rid,'claim':claim,'operation':'enqueue','body':{'request_id':rid,'agent':'perfil','task':'Review','execute':False}}],'poll_after':2})
            payload=json.loads(req.content);deliveries.append(payload)
            if len(deliveries)==1:raise httpx.ReadTimeout('Simulated delivery timeout')
            return httpx.Response(200,json={'saved':True})
        bridge=self.bridge(local,remote)
        with self.assertRaises(httpx.ReadTimeout):bridge.tick()
        bridge.deliver()
        self.assertEqual(local_requests,['/api/v1/status','/api/v1/runs'])
        self.assertEqual(deliveries,[{'id':rid,'claim':claim,'status':202,'data':{'id':rid,'status':'queued'}}]*2)
        self.assertEqual(bridge.deliveries,{})

    def test_local_timeout_is_reported_without_replay(self):
        """An ambiguous backend response must not lead to an automatic second enqueue."""
        seen=[]
        def timeout(req):seen.append(req.url.path);raise httpx.ReadTimeout('Simulated timeout')
        bridge=self.bridge(timeout,lambda req:httpx.Response(200,json={}))
        status,result=bridge.execute({'operation':'enqueue','body':{'request_id':str(uuid.uuid4()),'agent':'perfil','task':'Review'}})
        self.assertEqual(status,502)
        self.assertIn('Revisa el historial',result['detail'])
        self.assertEqual(seen,['/api/v1/runs'])

    def test_human_confirmation_keeps_csrf_and_exact_version(self):
        """Relay explicit human confirmation using the session's CSRF and version, not a service token."""
        observed=[];mid=str(uuid.uuid4())
        def local(req):observed.append((req.method,req.url.path,req.headers['X-CSRFToken'],json.loads(req.content)));return httpx.Response(200,json={'status':'confirmed','version':3})
        bridge=self.bridge(local,lambda req:httpx.Response(200,json={}))
        bridge.local.cookies.set('csrftoken','test-csrf')
        result=bridge.execute({'operation':'confirm','body':{'id':mid,'expected_version':2}})
        self.assertEqual(result,(200,{'status':'confirmed','version':3}))
        self.assertEqual(observed,[('POST','/api/v1/memory/'+mid+'/confirm','test-csrf',{'expected_version':2})])

    def test_login_failure_does_not_poll_or_execute_remote_work(self):
        """Invalid local credentials cannot expose a live office or execute pending requests."""
        def local(req):
            if req.url.path=='/api/v1/status':return httpx.Response(401,json={})
            return httpx.Response(200,text='Login',headers={'set-cookie':'csrftoken=test-csrf; Path=/'})
        remote_calls=[]
        def remote(req):remote_calls.append(req.url.path);return httpx.Response(200,json={})
        bridge=self.bridge(local,remote)
        with self.assertRaises(BridgeError):bridge.tick()
        self.assertEqual(remote_calls,[])
        self.assertEqual(bridge.heartbeat.exists(),False)
