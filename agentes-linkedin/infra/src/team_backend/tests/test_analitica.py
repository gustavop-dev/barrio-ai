"""Creator analytics of a `directo` account (docs/metricas-resultados.md, «Analítica de LinkedIn»; RES-10 and RES-11): the
workbook of LinkedIn's export dialog read in Spanish and English, the allowlist of that one request, the import (upserts,
idempotency, errors and pauses), the daily job and its guards, and GET /api/v1/resultados/analitica (range math, honesty
rules, permissions). Every workbook is hand-written with invented values (analitica_fixtures.py); nothing here reaches
LinkedIn or the navegador service."""
import json
import os
import re
import uuid
from datetime import date, datetime, time, timedelta, timezone as dt_timezone
from io import StringIO
from unittest.mock import patch
from django.contrib.auth.models import Permission, User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from linkedin_directo import Answer, Cliente, LinkedInError, Request, permitidas, rutas
from linkedin_directo import analitica as parser
from linkedin_directo.analitica import Day, Demographic, ParseError
from team_backend import analitica, autopiloto, connectors_directo, jobs
from team_backend.connectors import ConnectorError, FakeConnector, UnipileConnector
from team_backend.connectors_directo import DirectoConnector
from team_backend.models import (ActionExecution, ActionProposal, AnalyticsDay, AnalyticsImport, AnalyticsPost, AnalyticsRange,
                                 AnalyticsSnapshot, AuditEvent, ConnectorAccount, EditorialPiece, Job, OperatorControl, Worker)
from team_backend.tests import analitica_fixtures as A
from team_backend.tests import directo_fixtures as F
from team_backend.tests.test_metricas import MetricsBase

UTC=dt_timezone.utc
START,END=date(2026,11,1),date(2026,11,7)
NOW=datetime(2026,11,13,12,tzinfo=UTC)
EXPORT='^'+re.escape(rutas.navigation(rutas.ANALYTICS_SCREEN))+'$'
SERVICE={'LIVE_LINKEDIN_DIRECTO':'true','NAVEGADOR_URL':'http://navegador.interno:8080','NAVEGADOR_TOKEN':'token-ficticio',
         'ANALYTICS_EARLIEST':'','ANALYTICS_DAILY_DAYS':'14','ANALYTICS_DAILY_AFTER':'01:30','ANALYTICS_CHUNK_DAYS':'365',
         'ANALYTICS_DAILY_RANGES':'','ANALYTICS_DATE_ORDER':'','OPERATOR_PAUSED':'false'}
PRESETS=(7,14,28,90,365)

def answer(text,status=200):
    """The dialog's answer as the page gets it: a component stream served as octet-stream."""
    return Answer(status,text,'application/octet-stream','https://www.linkedin.com'+rutas.navigation(rutas.ANALYTICS_SCREEN))

def asked(request):
    payload=request.body['clientArguments']['payload']
    return date.fromisoformat(payload['startDate']),date.fromisoformat(payload['endDate'])

def grant(user,*codes):
    user.user_permissions.add(*Permission.objects.filter(content_type__app_label='team_backend',codename__in=codes))


class ParserTests(SimpleTestCase):
    def read(self,doc,start=START,end=END,order=None,escaped=False):
        return parser.read(A.stream(doc,escaped),start,end,order)

    def test_spanish_and_english_workbooks_read_the_same(self):
        for locale in ('es','en'):
            for letters in (False,True):
                with self.subTest(locale=locale,letters=letters):
                    book=self.read(A.workbook(locale=locale,letters=letters))
                    labels=A.LOCALES[locale]['labels'];groups=labels['groups']
                    self.assertEqual((book.start,book.end,book.impressions,book.members_reached,book.followers_total),
                                     (START,END,910,777,2345))
                    self.assertEqual(len(book.daily),7)
                    self.assertEqual((book.daily[0],book.daily[-1]),(Day(date(2026,11,1),100,5,0),Day(date(2026,11,7),160,11,0)))
                    first,second=book.recent_posts
                    self.assertEqual((first.urn,first.url,first.published,first.kind),
                                     (f'urn:li:activity:{A.POST_A}',A.url(A.POST_A),date(2026,11,5),labels['kind']))
                    self.assertEqual((first.impressions,first.network_pct,first.outside_pct,first.members_reached,first.followers_gained,
                                      first.profile_views,first.reactions,first.comments,first.shares,first.saves,first.sends,
                                      first.button_clicks),(1234,60.0,40.0,800,3,12,25,4,1,2,0,0))
                    self.assertEqual((second.impressions,second.network_pct,second.outside_pct,second.members_reached),(2500,55.5,44.5,1700))
                    self.assertEqual([(t.urn[-19:],t.published,t.value) for t in book.top_by_engagements],
                                     [(A.POST_B,date(2026,10,28),54),(A.POST_A,date(2026,11,5),32),(A.OLD_POST,date(2026,3,25),20)])
                    # The two lists side by side are not as long: the shorter one simply ends.
                    self.assertEqual([(t.urn[-19:],t.value) for t in book.top_by_impressions],[(A.POST_B,2500),(A.POST_A,1234)])
                    self.assertEqual(book.audience[0],Demographic(groups[0],'Ciudad Ficticia',32.0))
                    self.assertEqual(book.audience[1].pct,12.5)
                    self.assertEqual(book.audience[-1],Demographic(groups[4],'Educación',1.0,below=True))
                    self.assertEqual((len(book.content),book.content[-1].group),(8,groups[5]))
                    self.assertEqual(book.sheets,A.LOCALES[locale]['sheets'])

    def test_six_sheets_and_readable_links(self):
        """The test account's shape: no content demographics when nobody saw a post, links naming a share urn."""
        book=self.read(A.workbook(sheets=6,link='readable'))
        self.assertIsNone(book.content);self.assertEqual((len(book.sheets),len(book.audience)),(6,7))
        self.assertEqual(book.recent_posts[0].urn,f'urn:li:share:{A.POST_A}')
        self.assertEqual([t.urn for t in book.top_by_impressions],[f'urn:li:share:{A.POST_B}',f'urn:li:share:{A.POST_A}'])

    def test_sheets_with_only_their_headers_are_empty_not_an_error(self):
        book=self.read(A.workbook(posts=[],top_lists=([],[]),audience=[],sheets=6))
        self.assertEqual((book.recent_posts,book.top_by_engagements,book.top_by_impressions,book.audience),([],[],[],[]))
        self.assertEqual(len(book.daily),7)

    def test_the_workbook_is_found_among_junk_raw_or_escaped(self):
        doc=A.workbook()
        for escaped in (False,True):
            with self.subTest(escaped=escaped):self.assertEqual(parser.excel_doc(A.stream(doc,escaped)),doc)
        decoy='0:{"excelDoc":"todavía no"}\n1:{"excelDoc":{"sheets":'
        self.assertEqual(parser.excel_doc(decoy+A.stream(doc)),doc)
        for junk in ('','<html></html>','0:{"excelDoc":{"documentTitle":"x"}}',None):
            with self.subTest(junk=junk),self.assertRaises(ParseError) as e:parser.excel_doc(junk)
            self.assertEqual(e.exception.kind,'analytics_parse');self.assertIn('no trae el libro',str(e.exception))

    def test_a_changed_shape_names_the_sheet_and_row_never_the_value(self):
        secret='99x99-valor-de-celda'
        def cell(doc,sheet,row,col):return doc['sheets'][sheet]['rows'][row]['cells'][col]
        def five(doc):del doc['sheets'][5:]
        def header(doc):doc['sheets'][2]['rows'][0]['cells'].pop()
        def number(doc):cell(doc,1,3,1)['displayValue']=secret
        def pct(doc):cell(doc,2,1,4)['displayValue']=secret
        def totals(doc):del doc['sheets'][0]['rows'][1:]
        def stray(doc):doc['sheets'][1]['rows'].insert(3,A.row(secret,'1','2'))
        def followers(doc):del doc['sheets'][4]['rows'][0]
        def demographic(doc):doc['sheets'][5]['rows'].append(A.row('Grupo',secret,'sin porcentaje'))
        cases=((five,None,None,'el libro trae 5 hojas'),(header,3,1,'encabezado de 14 columnas'),(number,2,4,'número ilegible'),
               (pct,3,2,'porcentaje ilegible'),(totals,1,None,'faltan los totales'),(stray,2,4,'fila sin fecha'),
               (followers,5,None,'falta el total de seguidores'),(demographic,6,9,'fila sin porcentaje'))
        for mutate,sheet,row,what in cases:
            with self.subTest(what):
                doc=A.workbook();mutate(doc)
                with self.assertRaises(ParseError) as e:self.read(doc)
                self.assertEqual((e.exception.kind,e.exception.sheet,e.exception.row,e.exception.pause),('analytics_parse',sheet,row,False))
                self.assertIn(what,str(e.exception));self.assertNotIn('99x99',str(e.exception))
                if sheet:self.assertIn(f'hoja {sheet}'+(f', fila {row}' if row else ''),str(e.exception))

    def test_the_date_order_comes_from_the_dates_and_the_hint_only_breaks_a_tie(self):
        self.assertEqual(self.read(A.workbook(),order='mdy').daily[0].day,date(2026,11,1))  # only d/m fits: the hint is ignored
        self.assertEqual(self.read(A.workbook(locale='en'),order='dmy').daily[0].day,date(2026,11,1))
        year=(date(2026,1,1),date(2026,12,31))
        doc=A.workbook(*year,days=[(date(2026,2,1),10,1,0),(date(2026,1,2),20,2,1)],posts=[],top_lists=([],[]))
        with self.assertRaises(ParseError) as e:self.read(doc,*year)
        self.assertIn('ambiguas',str(e.exception))
        self.assertEqual(self.read(doc,*year,order='dmy').daily,[Day(date(2026,1,2),20,2,1),Day(date(2026,2,1),10,1,0)])
        self.assertEqual(self.read(doc,*year,order='mdy').daily,[Day(date(2026,1,2),10,1,0),Day(date(2026,2,1),20,2,1)])
        with self.assertRaises(ParseError) as e:self.read(A.workbook(),date(2026,12,1),date(2026,12,7))  # days outside the range
        self.assertIn('dentro del rango',str(e.exception))

    def test_cells_in_any_locale_and_no_data_is_none(self):
        for text,value in (('1.234',1234),('1,234',1234),(f'1{A.NBSP}234',1234),('1234',1234),('1.234.567',1234567),('0',0),
                           ('-',None),('',None),('—',None)):
            with self.subTest(text=text):self.assertEqual(parser.count(text),value)
        for text in ('12.5','1.234,567','12a','1,23'):
            with self.subTest(text=text),self.assertRaises(ValueError):parser.count(text)
        for text,value in ((f'12{A.NBSP}%',(12.0,False)),('12,5%',(12.5,False)),('12.5 %',(12.5,False)),
                           (f'<{A.NBSP}1{A.NBSP}%',(1.0,True)),('-',(None,False))):
            with self.subTest(text=text):self.assertEqual(parser.percent(text),value)
        for text in ('12','doce %'):
            with self.subTest(text=text),self.assertRaises(ValueError):parser.percent(text)

    def test_post_links_name_their_urn(self):
        n='7390000000000000009'
        for link,kind in ((f'https://www.linkedin.com/feed/update/urn:li:activity:{n}/','activity'),
                          (f'https://www.linkedin.com/feed/update/urn:li:ugcPost:{n}','ugcPost'),
                          (f'https://www.linkedin.com/feed/update/urn%3Ali%3Ashare%3A{n}','share'),
                          (f'https://www.linkedin.com/posts/autor-ficticio_tema-share-{n}-AbCd/','share'),
                          (f'https://www.linkedin.com/posts/autor-ficticio_tema-activity-{n}-AbCd?utm=x','activity')):
            with self.subTest(link=link):self.assertEqual(parser.post_urn(link),f'urn:li:{kind}:{n}')
        for link in ('https://www.linkedin.com/pulse/un-articulo-ficticio/','',None,'https://www.linkedin.com/posts/autor_tema-share-123-AbCd'):
            with self.subTest(link=link):self.assertEqual(parser.post_urn(link),'')

    def test_a_dash_or_an_empty_cell_is_no_data_never_zero(self):
        doc=A.workbook()
        cells=doc['sheets'][2]['rows'][1]['cells']
        cells[12]['displayValue']='—';cells[4]['displayValue']='-';del cells[13]
        post=self.read(doc).recent_posts[0]
        self.assertEqual((post.saves,post.network_pct,post.sends,post.impressions),(None,None,None,1234))

    def test_demographics_take_a_group_title_row_and_an_optional_count(self):
        sheet=A.sheet('X',[A.row('Principales','Valor','Porcentaje',bold=True),A.row('Ubicaciones'),A.row('Ciudad Ficticia','32 %'),
                           A.row('Otra Ciudad','120','12 %'),A.row('Cargos'),A.row('Fundador','< 1 %')])
        self.assertEqual(parser.demographics(sheet,7),[Demographic('Ubicaciones','Ciudad Ficticia',32.0),
                                                       Demographic('Ubicaciones','Otra Ciudad',12.0,value=120),
                                                       Demographic('Cargos','Fundador',1.0,below=True)])
        self.assertEqual(parser.demographics(A.sheet('X',[A.row('Principales','Valor','Porcentaje',bold=True)]),6),[])


class ExportRequestTests(SimpleTestCase):
    PATH=rutas.navigation(rutas.ANALYTICS_SCREEN)

    def request(self,body=None,path=None,kind='sdui',write=False):
        body=rutas.analytics_export('2026-11-01','2026-11-07') if body is None else body
        return Request('POST',path or self.PATH,kind,body,write,'analytics')

    def test_the_export_is_a_read_of_two_dates(self):
        for first,last in (('2026-11-01','2026-11-07'),('2026-11-13','2026-11-13'),('2025-11-13','2026-11-13')):  # 1 and 366 days
            with self.subTest(first=first,last=last):permitidas.check(self.request(rutas.analytics_export(first,last)))

    def test_everything_else_is_refused_before_leaving(self):
        body=rutas.analytics_export('2026-11-01','2026-11-07');args=body['clientArguments']
        other='com.linkedin.sdui.flagshipnav.settings.OtraPantalla'
        refused={
            'otra pantalla':self.request({**body,'clientArguments':{**args,'screenId':other}},rutas.navigation(other)),
            'otra pantalla con el cuerpo de la analítica':self.request(body,rutas.navigation(other)),
            'sduiid distinto':self.request(body,self.PATH.rsplit('&sduiid=',1)[0]+'&sduiid=otra'),
            'parámetro de más':self.request(body,self.PATH+'&extra=1'),
            'clave de más en el cuerpo':self.request({**body,'extra':1}),
            'clave de más en el payload':self.request({**body,'clientArguments':{**args,'payload':{**args['payload'],'granularity':'DAILY'}}}),
            'estados añadidos':self.request({**body,'clientArguments':{**args,'states':[{'key':'x'}]}}),
            'no modal':self.request({**body,'isModal':False}),
            'fecha no ISO':self.request(rutas.analytics_export('1/11/2026','2026-11-07')),
            'fecha imposible':self.request(rutas.analytics_export('2026-02-30','2026-03-01')),
            'fecha numérica':self.request(rutas.analytics_export(20261101,'2026-11-07')),
            'rango invertido':self.request(rutas.analytics_export('2026-11-07','2026-11-01')),
            '367 días':self.request(rutas.analytics_export('2025-11-12','2026-11-13')),
            'marcada como escritura':self.request(write=True),
            'GET':Request('GET',self.PATH,'sdui',operation='analytics'),
            'como acción del servidor':self.request(path=rutas.sdui(rutas.ANALYTICS_SCREEN)),
            'como página':self.request(kind='page'),
            'como Voyager':self.request(kind='voyager'),
        }
        for why,request in refused.items():
            with self.subTest(why):
                t=F.FakeTransport()
                with self.assertRaises(LinkedInError) as e:Cliente(t)._send(request)
                self.assertEqual(e.exception.kind,'refused');self.assertEqual(t.sent,[])
                self.assertIn('no se envió nada',str(e.exception))

    def test_the_client_sends_one_read_and_returns_the_workbook(self):
        t=F.FakeTransport(('POST',EXPORT,answer(A.stream(A.workbook()))))
        book=Cliente(t).analytics('2026-11-01',datetime(2026,11,7,23,tzinfo=UTC))
        self.assertEqual(book.impressions,910)
        [request]=t.sent
        self.assertEqual((request.method,request.kind,request.write,request.operation,request.body),
                         ('POST','sdui',False,'analytics',rutas.analytics_export('2026-11-01','2026-11-07')))

    def test_an_invalid_range_sends_nothing(self):
        for first,last in (('2026-11-07','2026-11-01'),('ayer','2026-11-01'),('2025-11-12','2026-11-13'),(None,'2026-11-01')):
            with self.subTest(first=first,last=last):
                t=F.FakeTransport()
                with self.assertRaises(LinkedInError) as e:Cliente(t).analytics(first,last)
                self.assertEqual(e.exception.kind,'invalid');self.assertEqual(t.sent,[])

    def test_a_stop_pauses_and_an_unreadable_workbook_does_not(self):
        cases=((F.html('<html><head><title>Security Verification</title></head></html>'),'challenge',True),
               (Answer(429,''),'pushback',True),
               (Answer(200,'{}','application/json','https://www.linkedin.com/checkpoint/challenge/x'),'login',True),
               (answer('0:["$","div",null,{}]'),'analytics_parse',False),
               (answer(A.stream({'sheets':A.workbook()['sheets'][:5]})),'analytics_parse',False),
               (Answer(500,''),'http_error',False))
        for reply,kind,pause in cases:
            with self.subTest(kind=kind):
                c=DirectoConnector('cuenta-prueba',transport=F.FakeTransport(('POST',EXPORT,reply)))
                with self.assertRaises(ConnectorError) as e:c.analytics(START,END)
                self.assertEqual((e.exception.kind,e.exception.pause),(kind,pause))

    def test_only_the_direct_connector_has_analytics(self):
        self.assertTrue(callable(getattr(DirectoConnector,'analytics',None)))
        for other in (UnipileConnector,FakeConnector):self.assertFalse(hasattr(other,'analytics'))


class ImportBase(TestCase):
    def setUp(self):
        env=patch.dict(os.environ,SERVICE);env.start();self.addCleanup(env.stop)
        push=patch('team_backend.alerts.notify');push.start();self.addCleanup(push.stop)
        self.book={};self.mutate=None;self.reply=None
        self.transport=F.FakeTransport(('POST',EXPORT,self.export))
        service=patch.object(connectors_directo,'TRANSPORT',self.transport);service.start();self.addCleanup(service.stop)
        self.account=ConnectorAccount.objects.create(provider='directo',external_account_id='cuenta-prueba',label='Cuenta directa de prueba')

    def export(self,request):
        """LinkedIn's answer for the range asked: the invented workbook of those days, tweaked by self.book/self.mutate."""
        if isinstance(self.reply,Answer):return self.reply
        if self.reply:return self.reply(request)
        doc=A.workbook(*asked(request),**self.book)
        if self.mutate:self.mutate(doc)
        return answer(A.stream(doc))

    def imported(self,start=START,end=END,now=NOW,**kw):
        return analitica.import_range(self.account,start,end,now=now,**kw)


class ImportTests(ImportBase):
    def test_one_export_fills_every_table(self):
        log=self.imported()
        self.assertEqual((log.state,log.trigger,log.start,log.end,log.error),('ok','manual',START,END,''))
        self.assertEqual(log.rows,{'days':7,'posts':2,'posts_without_urn':0,'top_by_engagements':3,'top_by_impressions':2,
                                   'audience':7,'content':8})
        self.assertEqual(log.sheets,list(A.LOCALES['es']['sheets']));self.assertIsNotNone(log.finished_at)
        [request]=self.transport.sent
        self.assertEqual((request.body,request.write),(rutas.analytics_export('2026-11-01','2026-11-07'),False))
        self.assertEqual(AnalyticsDay.objects.count(),7)
        self.assertEqual(list(AnalyticsDay.objects.order_by('day').values_list('day','impressions','engagements','new_followers')[:2]),
                         [(date(2026,11,1),100,5,0),(date(2026,11,2),110,6,1)])
        post=AnalyticsPost.objects.get(post_urn=f'urn:li:activity:{A.POST_A}')
        self.assertEqual((post.url,post.published,post.kind,post.impressions,post.network_pct,post.saves,post.piece_id),
                         (A.url(A.POST_A),date(2026,11,5),'Imagen',1234,60.0,2,None))
        self.assertEqual((post.first_seen_at,post.last_seen_at),(NOW,NOW))
        snapshot=AnalyticsSnapshot.objects.get()
        self.assertEqual((snapshot.day,snapshot.followers,len(snapshot.audience)),(date(2026,11,13),2345,7))
        self.assertEqual(snapshot.audience[0],{'group':'Ubicaciones','label':'Ciudad Ficticia','pct':32.0,'below':False,'value':None})
        span=AnalyticsRange.objects.get()
        self.assertEqual((span.start,span.end,span.impressions,span.members_reached,len(span.content)),(START,END,910,777,8))
        self.assertEqual(span.top_by_engagements[0],{'post_urn':f'urn:li:activity:{A.POST_B}','url':A.url(A.POST_B),'piece_id':None,
                                                     'published':'2026-10-28','value':54})
        self.assertTrue(AuditEvent.objects.filter(action='analytics.imported',target=str(self.account.id)).exists())

    def test_importing_again_updates_in_place_and_a_gap_never_erases(self):
        self.imported()
        later=NOW+timedelta(hours=1)
        self.book={'days':[(date(2026,11,1),150,9,2),(date(2026,11,2),130,7,1)]}
        def dash(doc):doc['sheets'][1]['rows'][1]['cells'][1]['displayValue']='-'  # Nov 1 impressions: no data this time
        self.mutate=dash
        self.assertEqual(self.imported(now=later).state,'ok')
        days={d.day:(d.impressions,d.engagements,d.new_followers) for d in AnalyticsDay.objects.all()}
        self.assertEqual(len(days),7)
        self.assertEqual(days[date(2026,11,1)],(100,9,2))  # the dash kept the value already seen
        self.assertEqual(days[date(2026,11,2)],(130,7,1))
        self.assertEqual(days[date(2026,11,7)],(160,11,0))  # a day the new export leaves out stays as it was
        post=AnalyticsPost.objects.get(post_urn=f'urn:li:activity:{A.POST_A}')
        self.assertEqual((AnalyticsPost.objects.count(),post.first_seen_at,post.last_seen_at),(2,NOW,later))
        self.assertEqual((AnalyticsRange.objects.count(),AnalyticsSnapshot.objects.count(),AnalyticsImport.objects.count()),(1,1,2))
        span=AnalyticsRange.objects.get()
        self.assertEqual((span.impressions,span.captured_at),(280,later))

    def test_a_post_is_linked_to_its_piece_by_any_id_we_keep(self):
        author=User.objects.create_user('autor-prueba')
        def piece(n,**metrics):
            return EditorialPiece.objects.create(account=self.account,slot_date=date(2026,10,1)+timedelta(days=n),scheduled_for=NOW,
                                                 state='ready',final_text=f'Texto de prueba {n}',brief={'pillar':'applied_ai'},metrics=metrics)
        published=piece(1)
        proposal=ActionProposal.objects.create(account=self.account,piece=published,capability='CONT-09',payload={'text':'Texto'},
                                               payload_hash='0'*64,state='confirmed')
        ActionExecution.objects.create(proposal=proposal,idempotency_key=uuid.uuid4().hex,provider='linkedin_fake',state='confirmed',
                                       executed_by=author,started_at=NOW,external_id=f'urn:li:share:{A.POST_A}')
        read=piece(2,share_url=A.url(A.POST_B,'readable'))
        self.book={'link':'readable'}
        self.imported()
        self.assertEqual({urn:str(pid) for urn,pid in AnalyticsPost.objects.values_list('post_urn','piece_id')},
                         {f'urn:li:share:{A.POST_A}':str(published.id),f'urn:li:share:{A.POST_B}':str(read.id)})
        top={t['post_urn']:t['piece_id'] for t in AnalyticsRange.objects.get().top_by_engagements}
        self.assertEqual(top,{f'urn:li:share:{A.POST_B}':str(read.id),f'urn:li:share:{A.POST_A}':str(published.id),
                              f'urn:li:share:{A.OLD_POST}':None})

    def test_a_workbook_that_does_not_read_is_logged_by_sheet_and_row_without_values(self):
        def garble(doc):doc['sheets'][1]['rows'][2]['cells'][2]['displayValue']='77x77'
        self.mutate=garble
        log=self.imported()
        self.assertEqual((log.state,log.error_kind),('error','analytics_parse'))
        self.assertIn('hoja 2, fila 3',log.error);self.assertNotIn('77x77',log.error)
        self.assertFalse(AnalyticsDay.objects.exists());self.assertFalse(AnalyticsRange.objects.exists())
        self.account.refresh_from_db();self.assertFalse(self.account.paused)  # a changed workbook is ours to fix, not a stop

    def test_a_stop_pauses_the_account_and_nothing_more_is_asked(self):
        self.reply=Answer(429,'{}','application/json')
        log=self.imported()
        self.assertEqual((log.state,log.error_kind),('error','pushback'))
        self.account.refresh_from_db()
        self.assertTrue(self.account.paused);self.assertTrue(self.account.paused_reason.startswith('Analítica detenida por el proveedor'))
        with self.assertRaises(ValueError):self.imported()
        self.assertEqual((len(self.transport.sent),AnalyticsImport.objects.count()),(1,1))

    def test_nothing_is_read_while_paused_or_from_another_provider(self):
        with patch.dict(os.environ,{'OPERATOR_PAUSED':'true'}),self.assertRaises(ValueError):self.imported()
        OperatorControl.objects.update_or_create(pk=1,defaults={'paused':True})
        with self.assertRaises(ValueError):self.imported()
        OperatorControl.objects.filter(pk=1).update(paused=False)
        ConnectorAccount.objects.filter(pk=self.account.pk).update(paused=True)
        with self.assertRaises(ValueError):self.imported()  # the object in hand is stale: the stored pause wins
        other=ConnectorAccount.objects.create(provider='unipile',external_account_id='acc_prueba',label='Unipile')
        with self.assertRaises(ValueError):analitica.import_range(other,START,END,now=NOW)
        self.assertEqual(self.transport.sent,[]);self.assertFalse(AnalyticsImport.objects.exists())

    def test_ranges_are_clamped_to_what_linkedin_gives(self):
        log=self.imported(date(2025,1,1),date(2025,12,1))
        self.assertEqual((log.start,log.end),(analitica.EARLIEST,date(2025,12,1)))
        self.assertEqual(asked(self.transport.sent[-1]),(analitica.EARLIEST,date(2025,12,1)))
        with patch.dict(os.environ,{'ANALYTICS_EARLIEST':'2026-11-03'}):self.assertEqual(self.imported().start,date(2026,11,3))
        for first,last in ((date(2026,12,1),date(2026,12,5)),(date(2025,10,10),date(2026,11,13))):  # the future; 400 days
            with self.subTest(first=first),self.assertRaises(ValueError):self.imported(first,last)
        self.assertEqual(len(self.transport.sent),2)

    def test_the_backfill_goes_back_in_chunks_newest_first_and_stops_at_a_failure(self):
        with patch.dict(os.environ,{'ANALYTICS_EARLIEST':'2026-09-01'}):
            logs=analitica.backfill(self.account,chunk=30,now=NOW)
            self.assertEqual([(l.start,l.end,l.trigger,l.state) for l in logs],
                             [(date(2026,10,14),date(2026,11,12),'carga_inicial','ok'),(date(2026,9,14),date(2026,10,13),'carga_inicial','ok'),
                              (date(2026,9,1),date(2026,9,13),'carga_inicial','ok')])
            self.assertEqual(AnalyticsDay.objects.count(),73)
            calls=[]
            def second_fails(request):
                calls.append(asked(request))
                return Answer(500,'') if len(calls)==2 else answer(A.stream(A.workbook(*asked(request))))
            self.reply=second_fails
            logs=analitica.backfill(self.account,date(2026,10,1),chunk=10,now=NOW)
            self.assertEqual([(l.start,l.end,l.state) for l in logs],[(date(2026,11,3),date(2026,11,12),'ok'),(date(2026,10,24),date(2026,11,2),'error')])
            self.assertEqual(len(calls),2)
            self.account.refresh_from_db();self.assertFalse(self.account.paused)
        for chunk in (0,367):
            with self.subTest(chunk=chunk),self.assertRaises(ValueError):analitica.backfill(self.account,chunk=chunk,now=NOW)


class CommandTests(ImportBase):
    def command(self,*args):
        out=StringIO();call_command('analitica',*args,stdout=out)
        return json.loads(out.getvalue())

    def test_import_backfill_and_state(self):
        yesterday=analitica.utc_today()-timedelta(days=1)
        [result]=self.command('importar','--cuenta','cuenta-prueba','--dias','7')
        self.assertEqual((result['desde'],result['hasta'],result['estado'],result['tipo'],result['filas']['days']),
                         ((yesterday-timedelta(days=6)).isoformat(),yesterday.isoformat(),'ok','manual',7))
        [result]=self.command('importar','--cuenta',str(self.account.id),'--desde','2026-11-01','--hasta','2026-11-07')
        self.assertEqual((result['desde'],result['hasta'],result['estado']),('2026-11-01','2026-11-07','ok'))
        logs=self.command('carga-inicial','--cuenta','cuenta-prueba','--desde',(yesterday-timedelta(days=9)).isoformat(),'--trozo','5')
        self.assertEqual([(l['desde'],l['hasta'],l['tipo']) for l in logs],
                         [((yesterday-timedelta(days=4)).isoformat(),yesterday.isoformat(),'carga_inicial'),
                          ((yesterday-timedelta(days=9)).isoformat(),(yesterday-timedelta(days=5)).isoformat(),'carga_inicial')])
        self.assertEqual(len(self.command('estado','--cuenta','cuenta-prueba')),4)
        self.assertEqual(len(self.transport.sent),4)

    def test_bad_arguments_send_nothing_and_a_failed_import_is_an_error(self):
        for args in (('importar','--cuenta','cuenta-prueba'),('importar','--cuenta','cuenta-prueba','--dias','7','--desde','2026-11-01'),
                     ('importar','--cuenta','cuenta-prueba','--dias','400'),('importar','--cuenta','otra-cuenta','--dias','7'),
                     ('importar','--cuenta','cuenta-prueba','--desde','1/11/2026','--hasta','2026-11-07'),
                     ('carga-inicial','--cuenta','cuenta-prueba','--trozo','0')):
            with self.subTest(args=args),self.assertRaises(CommandError):call_command('analitica',*args,stdout=StringIO())
        self.assertEqual(self.transport.sent,[])
        self.reply=Answer(500,'')
        with self.assertRaises(CommandError):call_command('analitica','importar','--cuenta','cuenta-prueba','--dias','3',stdout=StringIO())
        self.assertEqual(AnalyticsImport.objects.get().state,'error')


class DailyJobTests(ImportBase):
    def test_due_once_per_utc_day_after_the_hour(self):
        midnight=datetime(2026,11,13,tzinfo=UTC)
        self.assertFalse(analitica.daily_due(self.account,midnight+timedelta(hours=1,minutes=29)))
        self.assertTrue(analitica.daily_due(self.account,midnight+timedelta(hours=1,minutes=30)))
        AnalyticsImport.objects.create(account=self.account,start=START,end=END,trigger='manual',state='ok',started_at=midnight+timedelta(hours=2))
        self.assertTrue(analitica.daily_due(self.account,midnight+timedelta(hours=3)))  # a manual import is not the daily one
        AnalyticsImport.objects.create(account=self.account,start=START,end=END,trigger='diaria',state='error',started_at=midnight+timedelta(hours=2))
        self.assertFalse(analitica.daily_due(self.account,midnight+timedelta(hours=23)))  # one attempt a day, even a failed one
        self.assertTrue(analitica.daily_due(self.account,midnight+timedelta(days=1,hours=2)))
        with patch.dict(os.environ,{'ANALYTICS_DAILY_AFTER':'06:00'}):
            self.assertFalse(analitica.daily_due(self.account,midnight+timedelta(days=1,hours=5)))
        bogota=dt_timezone(timedelta(hours=-5))
        self.assertTrue(analitica.daily_due(self.account,datetime(2026,11,13,21,tzinfo=bogota)))  # 02:00 UTC of the 14th

    def test_off_without_the_service_or_for_other_providers(self):
        at=datetime(2026,11,13,2,tzinfo=UTC)
        for env in ({'LIVE_LINKEDIN_DIRECTO':'false'},{'NAVEGADOR_URL':' '},{'NAVEGADOR_TOKEN':''},{'ANALYTICS_DAILY_DAYS':'0'}):
            with self.subTest(env=env),patch.dict(os.environ,env):self.assertFalse(analitica.daily_due(self.account,at))
        other=ConnectorAccount.objects.create(provider='unipile',external_account_id='acc_prueba',label='Unipile')
        self.assertFalse(analitica.daily_due(other,at))
        self.assertTrue(analitica.daily_due(self.account,at))

    def test_the_job_imports_the_last_complete_days(self):
        bot=User.objects.create_user('autopiloto-prueba');grant(bot,'operate_linkedin')
        worker=Worker.objects.create()
        jobs.enqueue_operation(bot,'import_analytics',{'account':str(self.account.id)})
        jobs.process_one(worker)
        job=Job.objects.get(kind='import_analytics')
        self.assertEqual((job.state,job.result_status,job.error),('complete','analitica:ok dias:14',''))
        yesterday=analitica.utc_today()-timedelta(days=1)
        log=AnalyticsImport.objects.get()
        self.assertEqual((log.trigger,log.start,log.end),('diaria',yesterday-timedelta(days=13),yesterday))
        self.reply=Answer(429,'')
        failed,_=jobs.enqueue_operation(bot,'import_analytics',{'account':str(self.account.id)})
        jobs.process_one(worker);failed.refresh_from_db()
        self.assertEqual(failed.state,'failed');self.assertIn('429',failed.error)
        self.account.refresh_from_db();self.assertTrue(self.account.paused)

    def ranges(self,days):
        yesterday=NOW.date()-timedelta(days=1)
        return [(yesterday-timedelta(days=d-1),yesterday) for d in days]

    def test_the_job_then_imports_each_preset_range_in_order(self):
        """Catch a preset of the app without its exact range: after the 14-day refresh, every range of
        ANALYTICS_DAILY_RANGES ending yesterday, in order, each its own row; the refresh's length is not asked twice, and
        members reached then exist for every preset."""
        bot=User.objects.create_user('autopiloto-prueba');grant(bot,'operate_linkedin')
        with patch.dict(os.environ,{'ANALYTICS_DAILY_RANGES':'7,14,28,90,365'}):
            self.assertEqual(analitica.daily_ranges(),[7,28,90,365])
            result=analitica.run(bot,self.account,NOW)
        self.assertEqual(result,{'state':'ok','days':14,'ranges':4,'error':''})
        order=self.ranges((14,7,28,90,365))
        self.assertEqual([asked(r) for r in self.transport.sent],order)
        self.assertEqual(list(AnalyticsImport.objects.order_by('id').values_list('start','end','trigger','state')),
                         [(*r,'diaria','ok') for r in order])
        self.assertEqual(set(AnalyticsRange.objects.values_list('start','end')),set(order))
        for days in PRESETS:
            with self.subTest(days=days):
                reached=analitica.overview(periodo=f'{days}d',now=NOW)['totales']['members_reached']
                self.assertEqual((reached['value'],reached['unavailable_reason']),(777,None))

    def test_the_batch_stops_at_the_first_failure(self):
        """Catch a batch that keeps asking LinkedIn after a failure: the 28-day export fails, so 90 and 365 are not asked."""
        bot=User.objects.create_user('autopiloto-prueba');grant(bot,'operate_linkedin')
        calls=[]
        def third_fails(request):
            calls.append(asked(request))
            return Answer(500,'') if len(calls)==3 else answer(A.stream(A.workbook(*asked(request))))
        self.reply=third_fails
        with patch.dict(os.environ,{'ANALYTICS_DAILY_RANGES':'7,28,90,365'}):result=analitica.run(bot,self.account,NOW)
        self.assertEqual((result['state'],result['days'],result['ranges']),('error',14,1))
        self.assertTrue(result['error'])
        self.assertEqual(calls,self.ranges((14,7,28)))
        self.assertEqual(list(AnalyticsImport.objects.order_by('id').values_list('state',flat=True)),['ok','ok','error'])
        self.account.refresh_from_db();self.assertFalse(self.account.paused)

    def test_the_ranges_go_at_most_once_per_utc_day(self):
        """Catch a job run twice the same day (or resumed) asking LinkedIn for the long ranges again: the refresh runs, a
        range tried today is skipped, none follows a failure of the day, and the next day asks them again."""
        bot=User.objects.create_user('autopiloto-prueba');grant(bot,'operate_linkedin')
        sent=lambda:[asked(r) for r in self.transport.sent]
        with patch.dict(os.environ,{'ANALYTICS_DAILY_RANGES':'7,28'}):
            self.assertEqual(analitica.run(bot,self.account,NOW)['ranges'],2)
            self.assertFalse(analitica.daily_due(self.account,NOW))
            self.assertEqual(analitica.run(bot,self.account,NOW+timedelta(hours=5)),{'state':'ok','days':14,'ranges':0,'error':''})
            self.assertEqual(sent(),self.ranges((14,7,28,14)))
            # A batch cut short before its last range resumes with only what is left.
            AnalyticsImport.objects.filter(start=self.ranges((28,))[0][0]).delete()
            self.assertEqual(analitica.run(bot,self.account,NOW+timedelta(hours=6))['ranges'],1)
            self.assertEqual(sent()[-2:],self.ranges((14,28)))
            # A failure of the day: no range again that day.
            AnalyticsImport.objects.filter(start=self.ranges((7,))[0][0]).update(state='error',error='LinkedIn respondió 500.')
            self.assertEqual(analitica.run(bot,self.account,NOW+timedelta(hours=7))['ranges'],0)
            self.assertEqual(len(sent()),7)
            self.assertEqual(analitica.run(bot,self.account,NOW+timedelta(days=1))['ranges'],2)  # the next day
            self.assertEqual(len(sent()),10)

    def test_without_ranges_only_the_refresh(self):
        """Catch the ranges ignoring their switch: empty or 0 leaves the 14-day refresh alone."""
        bot=User.objects.create_user('autopiloto-prueba');grant(bot,'operate_linkedin')
        for value in ('','0',' , '):
            with self.subTest(value=value),patch.dict(os.environ,{'ANALYTICS_DAILY_RANGES':value}):
                self.assertEqual(analitica.daily_ranges(),[])
        self.assertEqual(analitica.run(bot,self.account,NOW),{'state':'ok','days':14,'ranges':0,'error':''})
        self.assertEqual([asked(r) for r in self.transport.sent],self.ranges((14,)))
        with patch.dict(os.environ,{'ANALYTICS_DAILY_RANGES':'90,400,90','ANALYTICS_DAILY_DAYS':'7'}):
            self.assertEqual(analitica.daily_ranges(),[90,366])  # deduplicated, at most one export's length


class AutopilotAnalyticsTests(MetricsBase):
    def test_queued_once_a_day_for_a_directo_account_and_never_breaks_the_tick(self):
        env=patch.dict(os.environ,SERVICE);env.start();self.addCleanup(env.stop)
        directo=ConnectorAccount.objects.create(provider='directo',external_account_id='cuenta-prueba',label='Cuenta directa de prueba',
                                                paused=True)
        midnight=datetime.combine(analitica.utc_today(),time(0),tzinfo=UTC)
        early,late=midnight+timedelta(hours=1,minutes=29),midnight+timedelta(hours=1,minutes=31)
        self.assertEqual(autopiloto.tick(self.bot,now=late)['analytics'],0)  # a paused account is not even looked at
        ConnectorAccount.objects.filter(pk=directo.pk).update(paused=False)
        self.assertEqual(autopiloto.tick(self.bot,now=early)['analytics'],0)
        self.assertEqual(autopiloto.tick(self.bot,now=late)['analytics'],1)
        job=Job.objects.get(kind='import_analytics')
        self.assertEqual((job.id,job.params,job.execute,job.state),
                         (autopiloto._job_id('analytics',directo.id,midnight.date()),{'account':str(directo.id)},False,'queued'))
        self.assertEqual(autopiloto.tick(self.bot,now=late)['analytics'],0)  # already queued
        Job.objects.filter(kind='import_analytics').update(state='failed')
        self.assertEqual(autopiloto.tick(self.bot,now=late+timedelta(hours=3))['analytics'],0)  # one job a day, whatever came of it
        self.assertEqual(autopiloto._analytics(self.bot,directo,late+timedelta(days=1)),1)  # the next day
        self.assertFalse(Job.objects.filter(kind='import_analytics',params__account=str(self.account.id)).exists())  # only directo
        with patch('team_backend.analitica.daily_due',side_effect=RuntimeError('boom')):report=autopiloto.tick(self.bot,now=late)
        self.assertEqual(report['analytics_error'],'RuntimeError')
        self.assertIn('execute',report);self.assertIn('reconcile',report)  # the rest of the tick still ran
        with patch.dict(os.environ,{'OPERATOR_PAUSED':'true'}):report=autopiloto.tick(self.bot,now=late)
        self.assertNotIn('analytics',report)


class ApiTests(TestCase):
    URL='/api/v1/resultados/analitica'

    def setUp(self):
        env=patch.dict(os.environ,SERVICE);env.start();self.addCleanup(env.stop)
        # Reading never calls LinkedIn: a transport with no answers and no connector at all.
        self.transport=F.FakeTransport()
        service=patch.object(connectors_directo,'TRANSPORT',self.transport);service.start();self.addCleanup(service.stop)
        connector=patch('team_backend.analitica.get_connector',side_effect=AssertionError('sin LinkedIn al leer'))
        connector.start();self.addCleanup(connector.stop)
        self.account=ConnectorAccount.objects.create(provider='directo',external_account_id='cuenta-prueba',label='Cuenta directa de prueba')
        # Like every Resultados endpoint: the API's default access_knowledge plus operate_linkedin.
        reader=User.objects.create_user('lectora-prueba');grant(reader,'access_knowledge','operate_linkedin')
        self.api=APIClient();self.api.force_login(reader)

    def days(self,first,last,impressions,engagements,new):
        d=first
        while d<=last:
            AnalyticsDay.objects.create(account=self.account,day=d,impressions=impressions,engagements=engagements,new_followers=new)
            d+=timedelta(days=1)

    def imported(self,start,end,state='ok',at=NOW,trigger='diaria',**kw):
        return AnalyticsImport.objects.create(account=self.account,start=start,end=end,trigger=trigger,state=state,started_at=at,
                                              finished_at=at+timedelta(minutes=1),**kw)

    def seed(self):
        self.days(date(2026,9,18),date(2026,10,15),5,1,0)  # the 28 days before the default period
        self.days(date(2026,10,16),date(2026,11,12),10,1,1)  # the 28 days that end yesterday
        self.imported(date(2026,10,30),date(2026,11,12))

    @staticmethod
    def pick(card,*keys):return {k:card[k] for k in keys}

    def test_presets_end_yesterday_and_compare_with_the_period_before(self):
        self.seed()
        body=analitica.overview(now=NOW)
        self.assertTrue(body['disponible'])
        self.assertEqual(body['periodo'],{'desde':date(2026,10,16),'hasta':date(2026,11,12),'dias':28,'preset':'28d','zona_horaria':'UTC',
                                          'anterior':{'desde':date(2026,9,18),'hasta':date(2026,10,15)}})
        self.assertEqual(self.pick(body['totales']['impressions'],'value','previous','delta','delta_pct','comparable','days','days_with_data'),
                         {'value':280,'previous':140,'delta':140,'delta_pct':100.0,'comparable':True,'days':28,'days_with_data':28})
        self.assertEqual(self.pick(body['totales']['new_followers'],'value','previous','comparable'),{'value':28,'previous':0,'comparable':True})
        self.assertEqual(self.pick(body['totales']['engagement_rate'],'value','previous','numerator','denominator','comparable'),
                         {'value':10.0,'previous':20.0,'numerator':28,'denominator':280,'comparable':True})
        self.assertEqual(len(body['serie']),28)
        self.assertEqual(body['serie'][0],{'date':date(2026,10,16),'impressions':10,'engagements':1,'new_followers':1})
        self.assertEqual(body['limites'],{'primer_dia':date(2026,9,18),'ultimo_dia':date(2026,11,12),'linkedin_desde':date(2025,10,10)})
        week=analitica.overview(periodo='7d',now=NOW)
        self.assertEqual((week['periodo']['desde'],week['periodo']['hasta'],week['periodo']['dias']),(date(2026,11,6),date(2026,11,12),7))
        self.assertEqual(self.pick(week['totales']['impressions'],'value','previous','delta'),{'value':70,'previous':70,'delta':0})
        custom=analitica.overview(desde='2026-10-01',hasta='2026-10-10',now=NOW)
        self.assertEqual((custom['periodo']['preset'],custom['periodo']['anterior'],custom['totales']['impressions']['value']),
                         (None,{'desde':date(2026,9,21),'hasta':date(2026,9,30)},50))

    def test_a_preset_ends_on_the_last_stored_day_when_imports_are_behind(self):
        self.days(date(2026,11,1),date(2026,11,10),10,1,1);self.imported(date(2026,11,1),date(2026,11,10))
        body=analitica.overview(periodo='7d',now=NOW)
        self.assertEqual((body['periodo']['desde'],body['periodo']['hasta']),(date(2026,11,4),date(2026,11,10)))
        self.assertEqual(analitica.overview(desde='2026-11-06',hasta='2026-11-12',now=NOW)['periodo']['hasta'],date(2026,11,12))

    def test_a_period_not_fully_imported_has_values_but_no_comparison(self):
        self.seed()
        partial=analitica.overview(desde='2026-09-10',hasta='2026-09-20',now=NOW)['totales']['impressions']
        self.assertEqual(self.pick(partial,'value','previous','comparable','delta','days','days_with_data'),
                         {'value':15,'previous':None,'comparable':False,'delta':None,'days':11,'days_with_data':3})
        week=analitica.overview(desde='2026-09-20',hasta='2026-09-26',now=NOW)['totales']  # its previous week has 2 days of 7
        self.assertEqual(self.pick(week['impressions'],'value','previous','comparable'),{'value':35,'previous':None,'comparable':False})
        self.assertFalse(week['engagement_rate']['comparable'])
        empty=analitica.overview(desde='2026-01-01',hasta='2026-01-31',now=NOW)
        self.assertIsNone(empty['totales']['impressions']['value']);self.assertTrue(empty['totales']['impressions']['unavailable_reason'])
        self.assertEqual(empty['serie'][0],{'date':date(2026,1,1),'impressions':None,'engagements':None,'new_followers':None})
        AnalyticsDay.objects.filter(day=date(2026,11,1)).update(impressions=None)  # a day LinkedIn gave no impressions for
        month=analitica.overview(now=NOW)['totales']
        self.assertEqual(self.pick(month['impressions'],'value','days_with_data','comparable'),{'value':270,'days_with_data':27,'comparable':False})
        self.assertTrue(month['engagements']['comparable']);self.assertFalse(month['engagement_rate']['comparable'])

    def test_members_reached_and_linkedin_top_lists_only_for_the_exact_range(self):
        self.seed()
        top=[{'post_urn':f'urn:li:activity:{A.POST_B}','url':A.url(A.POST_B),'piece_id':None,'published':'2026-10-28','value':54}]
        AnalyticsRange.objects.create(account=self.account,start=date(2026,10,16),end=date(2026,11,12),impressions=280,members_reached=900,
                                      top_by_engagements=top,top_by_impressions=[],captured_at=NOW)
        AnalyticsRange.objects.create(account=self.account,start=date(2026,9,18),end=date(2026,10,15),members_reached=600,captured_at=NOW)
        month=analitica.overview(now=NOW)
        self.assertEqual(self.pick(month['totales']['members_reached'],'value','previous','delta','captured_at'),
                         {'value':900,'previous':600,'delta':300,'captured_at':NOW})
        self.assertEqual(month['posts']['top_linkedin'],{'desde':date(2026,10,16),'hasta':date(2026,11,12),'captured_at':NOW,
                                                         'por_interacciones':top,'por_impresiones':[]})
        self.assertIsNone(month['posts']['top_unavailable_reason'])
        week=analitica.overview(periodo='7d',now=NOW)  # never added up from days, never taken from another range
        self.assertEqual(self.pick(week['totales']['members_reached'],'value','unavailable_reason'),
                         {'value':None,'unavailable_reason':analitica.REACHED_REASON})
        self.assertEqual((week['posts']['top_linkedin'],week['posts']['top_unavailable_reason']),(None,analitica.TOP_REASON))

    def test_content_demographics_come_from_the_nearest_imported_range_labelled_with_it(self):
        self.seed()
        rows=[{'group':'Cargos','label':'Fundador','pct':8.0,'below':False,'value':None},
              {'group':'Cargos','label':'Otro cargo','pct':1.0,'below':True,'value':None}]
        AnalyticsRange.objects.create(account=self.account,start=date(2026,10,16),end=date(2026,11,12),content=None,captured_at=NOW)  # 6 sheets
        AnalyticsRange.objects.create(account=self.account,start=date(2026,10,30),end=date(2026,11,12),content=rows,captured_at=NOW)
        AnalyticsRange.objects.create(account=self.account,start=date(2026,1,1),end=date(2026,3,1),content=[],captured_at=NOW)
        content=analitica.overview(now=NOW)['demografia']['contenido']
        self.assertEqual(self.pick(content,'desde','hasta','exacto'),{'desde':date(2026,10,30),'hasta':date(2026,11,12),'exacto':False})
        self.assertEqual(content['groups'],[{'group':'Cargos','rows':[{'label':'Fundador','pct':8.0,'below':False,'value':None},
                                                                      {'label':'Otro cargo','pct':1.0,'below':True,'value':None}]}])
        self.assertTrue(analitica.overview(periodo='14d',now=NOW)['demografia']['contenido']['exacto'])

    def test_followers_and_the_audience_come_from_the_captures(self):
        self.seed()
        audience=[{'group':'Ubicaciones','label':'Ciudad Ficticia','pct':32.0,'below':False,'value':None}]
        AnalyticsSnapshot.objects.create(account=self.account,day=date(2026,11,1),followers=100,audience=[],captured_at=NOW)
        AnalyticsSnapshot.objects.create(account=self.account,day=date(2026,11,13),followers=110,audience=audience,captured_at=NOW)
        body=analitica.overview(now=NOW)
        self.assertEqual(self.pick(body['seguidores'],'total','at','serie','unavailable_reason'),
                         {'total':110,'at':date(2026,11,13),'serie':[{'date':date(2026,11,1),'value':100},{'date':date(2026,11,13),'value':110}],
                          'unavailable_reason':None})
        self.assertEqual(body['demografia']['audiencia'],{'at':date(2026,11,13),'groups':[
            {'group':'Ubicaciones','rows':[{'label':'Ciudad Ficticia','pct':32.0,'below':False,'value':None}]}]})
        old=analitica.overview(desde='2026-09-20',hasta='2026-09-26',now=NOW)
        self.assertEqual((old['seguidores']['total'],old['seguidores']['serie']),(None,[]))
        self.assertTrue(old['seguidores']['unavailable_reason'])
        self.assertEqual(old['demografia']['audiencia']['at'],date(2026,11,13))  # the latest audience, whatever the period

    def test_posts_of_the_period_with_their_lifetime_figures(self):
        self.seed()
        def post(n,published,impressions):
            AnalyticsPost.objects.create(account=self.account,post_urn=f'urn:li:activity:{n}',url=A.url(n),published=published,
                                         kind='Imagen',impressions=impressions,last_seen_at=NOW)
        post(A.POST_A,date(2026,11,5),1234);post(A.POST_B,date(2026,10,28),2500);post(A.OLD_POST,date(2026,3,25),900)
        post(A.POST_C,date(2026,11,10),None)
        posts=analitica.overview(now=NOW)['posts']['publicados']
        self.assertEqual([(p['post_urn'][-19:],p['impressions']) for p in posts],[(A.POST_B,2500),(A.POST_A,1234),(A.POST_C,None)])
        self.assertEqual(self.pick(posts[0],'as_of','published','piece_id','kind'),
                         {'as_of':NOW,'published':date(2026,10,28),'piece_id':None,'kind':'Imagen'})

    def test_freshness_and_the_last_error(self):
        self.seed()
        body=analitica.overview(now=NOW)
        self.assertEqual(body['actualizado'],{'at':NOW+timedelta(minutes=1),'desde':date(2026,10,30),'hasta':date(2026,11,12),'tipo':'diaria'})
        self.assertIsNone(body['ultimo_error'])
        self.imported(START,END,state='error',at=NOW-timedelta(days=1),error_kind='pushback',error='LinkedIn: HTTP 429 en analytics.')
        self.assertIsNone(analitica.overview(now=NOW)['ultimo_error'])  # an older failure, an import came after it
        error='Analítica de LinkedIn ilegible (hoja 2, fila 3): número ilegible.'
        self.imported(START,END,state='error',at=NOW+timedelta(hours=1),trigger='manual',error_kind='analytics_parse',error=error)
        body=analitica.overview(now=NOW)
        self.assertEqual(body['ultimo_error'],{'at':NOW+timedelta(hours=1),'tipo':'manual','kind':'analytics_parse','error':error})
        self.assertEqual(body['actualizado']['at'],NOW+timedelta(minutes=1))

    def test_without_a_directo_account_or_an_import(self):
        ConnectorAccount.objects.filter(pk=self.account.pk).delete()
        ConnectorAccount.objects.create(provider='unipile',external_account_id='acc_prueba',label='Unipile')
        self.assertEqual(analitica.overview(now=NOW),{'disponible':False,'motivo':analitica.NO_ACCOUNT})
        account=ConnectorAccount.objects.create(provider='directo',external_account_id='cuenta-nueva',label='Cuenta nueva')
        body=analitica.overview(now=NOW)
        self.assertEqual((body['disponible'],body['cuenta']['id'],body['actualizado'],body['totales']['impressions']['value']),
                         (False,str(account.id),None,None))
        self.assertTrue(body['motivo'])

    def test_parameters_and_permissions(self):
        self.seed()
        response=self.api.get(self.URL,{'periodo':'7d'})
        self.assertEqual(response.status_code,200,response.content)
        body=response.json()
        self.assertEqual((body['cuenta']['id'],body['periodo']['dias'],body['periodo']['zona_horaria']),(str(self.account.id),7,'UTC'))
        custom=self.api.get(self.URL,{'cuenta':str(self.account.id),'desde':'2026-10-01','hasta':'2026-10-10'}).json()
        self.assertEqual((custom['periodo']['desde'],custom['totales']['impressions']['value']),('2026-10-01',50))
        unipile=ConnectorAccount.objects.create(provider='unipile',external_account_id='acc_prueba',label='Unipile')
        for params in ({'periodo':'30d'},{'desde':'2026-10-01'},{'desde':'1/10/2026','hasta':'2026-10-10'},
                       {'desde':'2026-10-10','hasta':'2026-10-01'},{'desde':'2025-10-10','hasta':'2026-10-11'},{'cuenta':'x'},
                       {'cuenta':str(unipile.id)},{'cuenta':str(uuid.uuid4())}):
            with self.subTest(params=params):self.assertEqual(self.api.get(self.URL,params).status_code,400)
        stranger=APIClient();stranger.force_login(User.objects.create_user('sin-permisos'))
        self.assertEqual(stranger.get(self.URL).status_code,403)
        self.assertIn(APIClient().get(self.URL).status_code,(401,403))
        self.assertEqual(self.transport.sent,[])
