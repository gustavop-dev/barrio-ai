"""Independent API QA: real PostgreSQL, synthetic records, no paid network."""
import hashlib
import json
import os
import uuid
from unittest.mock import patch

from django.contrib.auth.models import Permission, User
from django.core.cache import cache
from django.db import connection
from django.test import TransactionTestCase, override_settings
from rest_framework.test import APIClient
from knowledge import db
from team_backend.models import ApiCredential, AuditEvent, Job, KnowledgeUnit

RUN_ID = uuid.UUID('fd8401fa-9b53-4c44-9d1a-b430eebdc5ad')
UNIT_ID = 'LI-01-M001-K01'

@override_settings(STORAGES={'default': {'BACKEND':'django.core.files.storage.FileSystemStorage'}, 'staticfiles': {'BACKEND':'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class ApiQaTests(TransactionTestCase):
    def setUp(self):
        self.assertEqual(connection.vendor, 'postgresql')
        self.assertEqual(connection.settings_dict['NAME'].startswith('test_'), True)
        cache.clear()
        env = patch.dict(os.environ, {'LIVE_PROVIDERS': 'false'})
        env.start(); self.addCleanup(env.stop)
        network = patch('httpx.post', side_effect=AssertionError('Provider calls forbidden in QA'))
        network.start(); self.addCleanup(network.stop)
        with db.connect() as conn:
            conn.execute('TRUNCATE memory,runs,usage_ledger,embedding_cache,unit_evidence,edges,chunks,units,source_files,evidence,unit_revisions CASCADE')
            conn.execute("INSERT INTO source_files(path,sha256) VALUES('qa-fixture','abc')")
            conn.execute('''INSERT INTO units(id,session,title,original,sha256,source_path,pointer,metadata)
                VALUES(%s,1,'Título original','{"title":"Título original"}','abc','qa-fixture','/units/0','{}')''',(UNIT_ID,))
            conn.execute('INSERT INTO runs(id,agent,task,status,payload) VALUES(%s,%s,%s,%s,%s)',
                (RUN_ID, 'perfil','Historical private task','preview',json.dumps({'marker':'historical-only'})))
        self.user = User.objects.create_user('qa-reader')
        self.user.user_permissions.add(Permission.objects.get(content_type__app_label='team_backend',codename='access_knowledge'))
        self.client = APIClient(); self.client.force_authenticate(self.user)
        self.operator = User.objects.create_user('qa-operator')
        self.operator.user_permissions.add(*Permission.objects.filter(content_type__app_label='team_backend',codename__in=['access_knowledge','run_agents','propose_memory']))
        self.other_job = Job.objects.create(owner=self.operator,agent='perfil',task='Other owner private task',request_hash='b'*64)
        self.proposal = {'namespace':'user','key':'nicho','value':{'sector':'B2B'},'evidence':'User declaration'}

    def test_audit_requires_manage_jobs(self):
        """Catch disclosure of actor/action history to a knowledge-only reader."""
        AuditEvent.objects.create(actor=self.operator,action='private.action',target='target')
        response = self.client.get('/api/v1/audit')
        self.assertEqual(response.status_code,403)

    def test_audit_manager_can_inspect_events(self):
        """Catch over-restriction that prevents an authorized reviewer reading audit events."""
        self.user.user_permissions.add(Permission.objects.get(content_type__app_label='team_backend',codename='manage_jobs'))
        AuditEvent.objects.create(actor=self.operator,action='private.action',target='target')
        response = self.client.get('/api/v1/audit')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['results'][0]['action'],'private.action')

    def test_integrity_requires_manage_jobs(self):
        """Catch accidental access to source verification without management permission."""
        self.assertEqual(self.client.get('/api/v1/integrity').status_code,403)

    def test_historical_run_hidden_from_operator(self):
        """Catch exposure of pre-ownership run payloads to ordinary operators."""
        response = self.client.get('/api/v1/runs/'+str(RUN_ID))
        self.assertEqual(response.status_code,404)

    def test_historical_run_visible_to_manager(self):
        """Catch loss of access to historical results after adopting Django jobs."""
        self.user.user_permissions.add(Permission.objects.get(content_type__app_label='team_backend',codename='manage_jobs'))
        response = self.client.get('/api/v1/runs/'+str(RUN_ID))
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['payload'],{'marker':'historical-only'})
        self.assertEqual(response.json()['historical'],True)

    def test_inactive_unit_hidden(self):
        """Catch inactive source material leaking through unit detail and list APIs."""
        KnowledgeUnit.objects.filter(pk=UNIT_ID).update(active=False)
        self.assertEqual(self.client.get('/api/v1/units/'+UNIT_ID).status_code,404)
        self.assertEqual(self.client.get('/api/v1/units').json()['count'],0)

    def test_missing_source_returns_404(self):
        """Catch an unknown evidence identifier becoming a server error or empty success."""
        self.assertEqual(self.client.get('/api/v1/sources/01:missing').status_code,404)

    def test_memory_author_cannot_be_spoofed(self):
        """Catch caller-supplied author impersonating the human confirmer."""
        self.client.force_authenticate(self.operator)
        response = self.client.post('/api/v1/memory/proposals',dict(self.proposal,author='user:administrator'),format='json')
        self.assertEqual(response.status_code,201)
        with db.connect() as conn:
            author = conn.execute('SELECT author FROM memory WHERE id=%s',(response.json()['id'],)).fetchone()['author']
        self.assertEqual(author,'user:'+str(self.operator.pk))

    def test_nested_nul_memory_returns_400(self):
        """Catch nested NUL reaching PostgreSQL JSONB and producing HTTP 500."""
        self.client.force_authenticate(self.operator)
        response = self.client.post('/api/v1/memory/proposals',dict(self.proposal,value={'nested':['bad\x00text']}),format='json')
        self.assertEqual(response.status_code,400)
        self.assertEqual(set(response.json()),{'value'})

    def test_unpaired_surrogate_memory_returns_400(self):
        """Catch invalid Unicode in nested memory JSON escaping validation and causing HTTP 500."""
        self.client.force_authenticate(self.operator)
        self.client.raise_request_exception=False
        body=json.dumps(dict(self.proposal,value={'nested':['\ud800']}))
        response = self.client.post('/api/v1/memory/proposals',body,content_type='application/json')
        self.assertEqual(response.status_code,400)
        self.assertEqual(set(response.json()),{'value'})

    def test_admin_unit_change_rejected(self):
        """Catch an admin POST rewriting original extracted knowledge despite readonly UI."""
        admin=User.objects.create_superuser('qa-admin',password='test-only-strong-password')
        client=APIClient();client.force_login(admin)
        response=client.post('/admin/team_backend/knowledgeunit/'+UNIT_ID+'/change/',{'title':'REWRITTEN'})
        self.assertEqual(response.status_code,403)
        self.assertEqual(KnowledgeUnit.objects.get(pk=UNIT_ID).title,'Título original')

    def test_admin_unit_delete_rejected(self):
        """Catch an admin deleting extracted knowledge through a direct delete URL."""
        admin=User.objects.create_superuser('qa-admin',password='test-only-strong-password')
        client=APIClient();client.force_login(admin)
        response=client.post('/admin/team_backend/knowledgeunit/'+UNIT_ID+'/delete/',{'post':'yes'})
        self.assertEqual(response.status_code,403)
        self.assertEqual(KnowledgeUnit.objects.filter(pk=UNIT_ID).count(),1)

    def test_staff_job_view_does_not_bypass_owner_scope(self):
        """Catch a staff reader bypassing job ownership through the Django admin detail URL."""
        self.user.is_staff=True;self.user.save()
        self.user.user_permissions.add(Permission.objects.get(content_type__app_label='team_backend',codename='view_job'))
        client=APIClient();client.force_login(self.user)
        response=client.get('/admin/team_backend/job/'+str(self.other_job.pk)+'/change/')
        self.assertEqual(response.status_code,302)
        self.assertEqual('Other owner private task' in response.content.decode(),False)

    def test_bad_bearer_cannot_fall_back_to_valid_session(self):
        """Catch a malformed Bearer header being ignored in favor of a valid human session."""
        client=APIClient();client.force_login(self.user)
        client.credentials(HTTP_AUTHORIZATION='Bearer invalid extra')
        self.assertEqual(client.get('/api/v1/units').status_code,401)

    def test_credential_change_does_not_reassign_identity(self):
        """Catch an admin POST reassigning a token identity through readonly form fields."""
        token=ApiCredential.objects.create(name='Token',user=self.operator,digest=hashlib.sha256(b'qa-token').hexdigest())
        admin=User.objects.create_superuser('qa-admin',password='test-only-strong-password')
        client=APIClient();client.force_login(admin)
        response=client.post('/admin/team_backend/apicredential/'+str(token.pk)+'/change/',{'user':admin.pk,'name':'Injected','revoked':'on','expires_at_0':'','expires_at_1':''})
        self.assertEqual(response.status_code,302)
        token.refresh_from_db()
        self.assertEqual(token.user_id,self.operator.pk)
        self.assertEqual(token.name,'Token')
        self.assertEqual(token.revoked,True)

    def test_admin_job_list_scoped_to_owner(self):
        """Catch admin changelist exposing another owner's task even if detail is protected."""
        self.user.is_staff=True;self.user.save()
        self.user.user_permissions.add(Permission.objects.get(content_type__app_label='team_backend',codename='view_job'))
        own=Job.objects.create(owner=self.user,agent='perfil',task='My task',request_hash='c'*64)
        client=APIClient();client.force_login(self.user)
        response=client.get('/admin/team_backend/job/')
        self.assertEqual(response.status_code,200)
        self.assertEqual(list(response.context['cl'].queryset.values_list('id',flat=True)),[own.pk])

    def test_admin_job_owner_can_view_own_job(self):
        """Catch ownership hardening accidentally blocking a staff member's own jobs."""
        self.operator.is_staff=True;self.operator.save()
        self.operator.user_permissions.add(Permission.objects.get(content_type__app_label='team_backend',codename='view_job'))
        client=APIClient();client.force_login(self.operator)
        response=client.get('/admin/team_backend/job/'+str(self.other_job.pk)+'/change/')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.context['original'].pk,self.other_job.pk)

    def test_admin_job_manager_can_view_other_job(self):
        """Catch ownership hardening removing the explicit management override."""
        self.user.is_staff=True;self.user.save()
        self.user.user_permissions.add(*Permission.objects.filter(content_type__app_label='team_backend',codename__in=['view_job','manage_jobs']))
        client=APIClient();client.force_login(self.user)
        response=client.get('/admin/team_backend/job/'+str(self.other_job.pk)+'/change/')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.context['original'].pk,self.other_job.pk)

    def test_historical_run_admin_requires_management(self):
        """Catch Django admin bypassing API protection of pre-ownership run payloads."""
        self.user.is_staff=True;self.user.save()
        self.user.user_permissions.add(Permission.objects.get(content_type__app_label='team_backend',codename='view_knowledgerun'))
        client=APIClient();client.force_login(self.user)
        response=client.get('/admin/team_backend/knowledgerun/'+str(RUN_ID)+'/change/')
        self.assertEqual(response.status_code,302)
        self.assertEqual('historical-only' in response.content.decode(),False)

    def test_overflow_json_memory_number_returns_400(self):
        """Catch syntactically valid overflowing JSON numbers reaching PostgreSQL as Infinity."""
        self.client.force_authenticate(self.operator)
        self.client.raise_request_exception=False
        body=json.dumps(dict(self.proposal,value='REPLACE')).replace('"REPLACE"','1e999')
        response=self.client.post('/api/v1/memory/proposals',body,content_type='application/json')
        self.assertEqual(response.status_code,400)
        self.assertEqual(set(response.json()),{'value'})

    def test_audit_admin_requires_management(self):
        """Catch a staff audit viewer bypassing the API's management permission."""
        self.user.is_staff=True;self.user.save()
        self.user.user_permissions.add(Permission.objects.get(content_type__app_label='team_backend',codename='view_auditevent'))
        client=APIClient();client.force_login(self.user)
        response=client.get('/admin/team_backend/auditevent/')
        self.assertEqual(response.status_code,403)

    def test_audit_admin_manager_can_read_events(self):
        """Catch management hardening denying the authorized audit reviewer."""
        self.user.is_staff=True;self.user.save()
        self.user.user_permissions.add(*Permission.objects.filter(content_type__app_label='team_backend',codename__in=['view_auditevent','manage_jobs']))
        event=AuditEvent.objects.create(actor=self.operator,action='reviewed',target='qa')
        client=APIClient();client.force_login(self.user)
        response=client.get('/admin/team_backend/auditevent/')
        self.assertEqual(response.status_code,200)
        self.assertEqual(list(response.context['cl'].queryset.values_list('id',flat=True)),[event.pk])

    def test_run_admin_owner_can_read_owned_result(self):
        """Catch run-admin filtering rejecting a result linked to the viewer's job."""
        self.user.is_staff=True;self.user.save()
        self.user.user_permissions.add(Permission.objects.get(content_type__app_label='team_backend',codename='view_knowledgerun'))
        Job.objects.create(id=RUN_ID,owner=self.user,agent='perfil',task='Owned result',request_hash='d'*64)
        client=APIClient();client.force_login(self.user)
        response=client.get('/admin/team_backend/knowledgerun/'+str(RUN_ID)+'/change/')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.context['original'].pk,RUN_ID)

# Named table-driven unittest cases, rather than loops/subtests inside test bodies.
# The project uses Django's runner, so pytest parameterization is not available.
ENDPOINTS = [
 ('status','get','/api/v1/status'),('search','post','/api/v1/search'),
 ('unit_detail','get','/api/v1/units/'+UNIT_ID),('sources','get','/api/v1/sources/01:test'),
 ('runs_list','get','/api/v1/runs'),('runs_create','post','/api/v1/runs'),
 ('run_detail','get','/api/v1/runs/'+str(RUN_ID)),('cancel','post','/api/v1/runs/'+str(RUN_ID)+'/cancel'),
 ('memory','get','/api/v1/memory'),('proposal','post','/api/v1/memory/proposals'),
 ('confirm','post','/api/v1/memory/'+str(RUN_ID)+'/confirm'),('integrity','get','/api/v1/integrity'),('audit','get','/api/v1/audit'),
]

def anonymous_case(method,path):
    def test(self):
        response=getattr(APIClient(),method)(path)
        self.assertEqual(response.status_code,401)
    test.__doc__='Catch missing authentication on '+method.upper()+' '+path+'.'
    return test

def unprivileged_case(method,path):
    def test(self):
        client=APIClient()
        outsider=User.objects.create_user('no-permission')
        client.force_authenticate(outsider)
        response=getattr(client,method)(path)
        self.assertEqual(response.status_code,403)
    test.__doc__='Catch missing knowledge permission on '+method.upper()+' '+path+'.'
    return test

for name,method,path in ENDPOINTS:
    setattr(ApiQaTests,'test_anonymous_'+name,anonymous_case(method,path))
    setattr(ApiQaTests,'test_no_permission_'+name,unprivileged_case(method,path))

INVALID_PAYLOADS = [
 ('search_unicode','/api/v1/search',{'query':'\ud800'},'query'),
 ('run_unicode','/api/v1/runs',{'agent':'perfil','task':'\ud800'},'task'),
 ('proposal_key_unicode','/api/v1/memory/proposals',{'namespace':'user','key':'\ud800','value':'x','evidence':'source'},'key'),
 ('proposal_evidence_unicode','/api/v1/memory/proposals',{'namespace':'user','key':'k','value':'x','evidence':'\ud800'},'evidence'),
 ('search_limit','/api/v1/search',{'query':'titular','limit':21},'limit'),
 ('search_blank','/api/v1/search',{'query':'   '},'query'),
 ('run_agent','/api/v1/runs',{'agent':'invented','task':'test'},'agent'),
 ('run_uuid','/api/v1/runs',{'agent':'perfil','task':'test','request_id':'bad'},'request_id'),
 ('proposal_namespace','/api/v1/memory/proposals',{'namespace':'system','key':'k','value':'x','evidence':'source'},'namespace'),
 ('proposal_version','/api/v1/memory/proposals',{'namespace':'user','key':'k','value':'x','evidence':'source','expected_version':-1},'expected_version'),
]

def validation_case(path,payload,field):
    def test(self):
        self.client.force_authenticate(self.operator)
        response=self.client.post(path,json.dumps(payload),content_type='application/json')
        self.assertEqual(response.status_code,400)
        self.assertEqual(set(response.json()),{field})
    test.__doc__='Catch invalid '+field+' escaping serializer validation at '+path+'.'
    return test

for name,path,payload,field in INVALID_PAYLOADS:
    setattr(ApiQaTests,'test_validation_'+name,validation_case(path,payload,field))
