"""seed_qa: the demo world of the mobile app's UI QA (.github/workflows/qa-movil.yml, movil/.maestro/README.md).

It builds a realistic, deterministic office for a CI-only user `qa`: the fake connector accounts, editorial pieces in
every state, pending proposals, people at every stage, opportunities, referents, every kind of Tu turno card,
notifications, captures, gallery photos, results history, a weekly summary and spend rows.

Idempotent in the strong sense: every run first empties the QA world and builds it again, so each Maestro flow starts
from the same state whatever the previous one changed. The `qa` user and its device logins survive, so the app stays
signed in between flows. Fixed ids (uuid5) and texts; times are relative to now (T = today in OPERATOR_TIMEZONE).

Because it empties tables, it refuses to run unless QA_SEED=permitido, no live provider or LinkedIn switch is on and the
database has no real LinkedIn account or credential. It never calls a provider or the network."""
import hashlib
import io
import os
import struct
import uuid
import wave
import zlib
from datetime import datetime, time, timedelta
from decimal import Decimal
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone
from psycopg.types.json import Jsonb
from team_backend import operador
from team_backend.authentication import digest
from team_backend.models import (ActionExecution, ActionProposal, AudienceSnapshot, AuditEvent, Capture, ConnectorAccount, Contact,
                                 Conversation, DeviceToken, EditorialPiece, GalleryPhoto, InboxSeen, Job, LinkedInCredential,
                                 Notification, ObservedPost, OfficePreference, OperatorControl, Opportunity, Orientation, PostMetric,
                                 Referent, TeamQuestion, WeeklySummary, Worker)

QA_USERNAME='qa'
QA_PASSWORD_DEFAULT='qa-0ff1ce-solo-ci'
NS=uuid.UUID('0ff1ce00-9a5e-4d00-8e00-00000000c1a0')
EXTRA_DEVICE='Pixel 7 de Gustavo (QA)'
LIVE_SWITCHES=('LIVE_PROVIDERS','LIVE_LINKEDIN','LIVE_LINKEDIN_OFFICIAL')
FAKE_URL='https://linkedin.example'  # never a real LinkedIn address: nothing in the QA world can open linkedin.com

def uid(name):
    return uuid.uuid5(NS,name)

def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()

# --------------------------------------------------------------------------- small generated files

def png(width,height,palette,seed):
    """A small RGB PNG drawn with the standard library: sky, ground and a few blocks, different per seed."""
    sky,ground,block=palette
    rows=[]
    for y in range(height):
        row=bytearray(b'\x00')
        for x in range(width):
            color=sky if y<height*0.6 else ground
            if (x//24+seed)%5==0 and height*0.35<y<height*0.6+((x*seed)%7):color=block
            if (x-width*0.75)**2+(y-height*0.2)**2<(height*0.08)**2:color=(250,235,140)
            row+=bytes(color)
        rows.append(bytes(row))
    def chunk(kind,data):
        return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    return (b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,2,0,0,0))
            +chunk(b'IDAT',zlib.compress(b''.join(rows),9))+chunk(b'IEND',b''))

def silent_wav(seconds=2,rate=8000):
    buffer=io.BytesIO()
    with wave.open(buffer,'wb') as out:
        out.setnchannels(1);out.setsampwidth(2);out.setframerate(rate);out.writeframes(b'\x00\x00'*rate*seconds)
    return buffer.getvalue()

# --------------------------------------------------------------------------- texts of the editorial pieces

READERS=['lector_comprador','lector_recomendador','lector_divulgador','lector_lider','lector_par']

def piece_texts(key,thesis,pillar,modality,reader):
    """Brief, variants, panel, selection and usage of one piece, so every fold of «Cómo se escribió» has content."""
    a=(f'Most teams write down what they did. Few write down why.\n\n{thesis} — in English: the decision log is the product memory.\n\n'
       'When a new engineer joins, the backlog tells them what. The decision log tells them which doors we already closed, and why.\n\n'
       'Three lines per decision are enough: context, options, the one we picked.')
    b=(f'We lost two weeks once because nobody remembered why we had dropped a queue.\n\n{thesis}.\n\n'
       'Since then every architectural choice gets three lines in the repo: the context, the options we weighed and the reason.\n\n'
       'It costs five minutes. It saves the meeting where everyone guesses.')
    brief={'decision':'write','skip_reason':'','primary_reader':reader,'modality':modality,'pillar':pillar,'thesis':thesis,
           'approach':'LI-05-M001-K03','format':'text_only','reader_value':'Una práctica concreta que un equipo pequeño puede copiar mañana.',
           'evidence':[{'ref':'LI-05-M001-K03','note':'Contar una decisión real con su contexto','kind':'observed_source'},
                       {'ref':'memoria:projectapp.fundacion','note':'Gustavo fundó ProjectApp','kind':'public_fact'}],
           'success_criterion':'Comentarios que cuentan cómo documenta decisiones cada equipo.',
           'avoid':['cifras inventadas','pitch de servicios'],'rationale':'Las señales de la semana hablan de equipos que pierden contexto.',
           'signals_used':[str(uid('post:1'))],'ideas_used':[],'questions_for_gustavo':[]}
    variants={'variant_a':{'angle':'La memoria del producto','text':a,'claims':[{'text':'El registro de decisiones evita repetir debates','kind':'opinion','ref':''}],
                           'uncertainties':['¿Gustavo usa ADRs o notas libres?']},
              'variant_b':{'angle':'Una historia de dos semanas perdidas','text':b,'claims':[{'text':'Perdimos dos semanas por una decisión olvidada','kind':'public_fact','ref':'memoria:projectapp.fundacion'}],
                           'uncertainties':[]},
              'citations':['LI-05-M001-K03','LI-06-M002-K09']}
    panel={'readers':[{'reader':r,'variant_a':{'strengths':['Claro y útil'],'objections':[] if i%2 else [{'text':'Algo genérico','severity':'preference'}]},
                       'variant_b':{'strengths':['Concreto','Con historia propia'],'objections':[{'text':'Falta decir cuánto cuesta','severity':'missing_data'}] if i==3 else []}}
                      for i,r in enumerate(READERS)],
           'summary':'La variante B convence más: cuenta una historia propia y termina con una práctica copiable.','citations':['LI-05-V005-K05']}
    selection={'decision':'B','final_text':b,'rationale':'B tiene una historia verificable y una práctica concreta.',
               'claims':variants['variant_b']['claims'],'resolved_objections':['Algo genérico'],'kept_objections':['Falta decir cuánto cuesta']}
    usage=[{'stage':s,'model':'claude-opus-5-5','input_tokens':n*100,'output_tokens':n*20,'estimated_usd':str(Decimal(n)/Decimal(1000))}
           for s,n in (('director',38),('redactor',52),('lectores',9),('seleccion',21),('verificador',17))]
    return brief,variants,panel,selection,b,usage

def verification_ok(text):
    return {'verdict':'ready_for_execution','model_verdict':'ready_for_execution','findings':[{'issue':'tone','severity':'minor','quote':'It costs five minutes','detail':'Tono algo absoluto'}],
            'checked_claims':[{'text':'Perdimos dos semanas por una decisión olvidada','status':'supported'}],
            'summary':'Sin hallazgos materiales; una observación menor de tono.','blocking_reasons':[],'rules':[],'text_sha256':sha(text)}

# --------------------------------------------------------------------------- the command

class Command(BaseCommand):
    help='Rehace el mundo de demostración de la QA móvil (solo CI: exige QA_SEED=permitido).'

    def handle(self,**options):
        self.guard()
        with transaction.atomic():
            self.now=timezone.now();self.tz=operador.local_tz();self.today=self.now.astimezone(self.tz).date()
            self.user=self.qa_user()
            self.robot=User.objects.filter(username='barrio-autopiloto').first() or self.user
            self.wipe()
            self.accounts();self.network();self.pieces();self.proposals();self.opportunities();self.conversation()
            self.questions();self.facts();self.notifications();self.captures();self.gallery();self.results();self.summaries()
            self.spend();self.settings();self.devices()
        self.stdout.write(f'Mundo de QA listo para «{QA_USERNAME}» (hoy {self.today}, {self.tz}).')

    # ------------------------------------------------------------------ safety and reset

    def guard(self):
        if os.environ.get('QA_SEED')!='permitido':
            raise CommandError('seed_qa vacía y rehace datos: solo corre en la QA de CI (exporta QA_SEED=permitido).')
        on=[v for v in LIVE_SWITCHES if os.environ.get(v,'false').strip().lower()=='true']
        if on:raise CommandError(f'seed_qa no corre con proveedores o LinkedIn reales activados: {", ".join(on)}.')
        if ConnectorAccount.objects.filter(provider__in=['unipile','linkedin']).exists() or LinkedInCredential.objects.exists():
            raise CommandError('Esta base tiene una cuenta real de LinkedIn: seed_qa no la toca.')

    def qa_user(self):
        user,_=User.objects.get_or_create(username=QA_USERNAME)
        user.is_superuser=True;user.is_staff=True;user.is_active=True;user.email='qa@example.invalid'
        user.set_password(os.environ.get('QA_PASSWORD') or QA_PASSWORD_DEFAULT);user.save()
        return user

    def wipe(self):
        """Empty the QA world. Device logins, users, groups and Expo tokens stay."""
        for photo in GalleryPhoto.objects.all():photo.image.delete(save=False)
        for capture in Capture.objects.exclude(audio=''):capture.audio.delete(save=False)
        models=[ActionExecution,ActionProposal,PostMetric,GalleryPhoto,Capture,EditorialPiece,Conversation,Opportunity,Contact,
                ObservedPost,Referent,ConnectorAccount,TeamQuestion,Notification,InboxSeen,WeeklySummary,AudienceSnapshot,Job,Worker,AuditEvent]
        tables=', '.join(connection.ops.quote_name(m._meta.db_table) for m in models)
        with connection.cursor() as cursor:
            # Deferred foreign keys with pending checks in this transaction would make TRUNCATE fail: check them now.
            cursor.execute('SET CONSTRAINTS ALL IMMEDIATE')
            cursor.execute(f'TRUNCATE {tables}, memory, usage_ledger, runs CASCADE')
            cursor.execute('SET CONSTRAINTS ALL DEFERRED')

    def at(self,days,hour=9,minute=0):
        return datetime.combine(self.today+timedelta(days=days),time(hour,minute),tzinfo=self.tz)

    def ago(self,**delta):
        return self.now-timedelta(**delta)

    # ------------------------------------------------------------------ accounts, referents, posts, people

    def accounts(self):
        self.fake=ConnectorAccount.objects.create(id=uid('account:unipile'),provider='fake',external_account_id='qa-unipile-gustavo',
                                                  label='LinkedIn de Gustavo (simulado)',status='OK',last_checked_at=self.ago(hours=1))
        self.official=ConnectorAccount.objects.create(id=uid('account:official'),provider='linkedin_fake',external_account_id='urn:li:person:qa-gustavo',
                                                      label='API oficial (simulada)',status='OK',last_checked_at=self.ago(hours=1))

    def network(self):
        referents=[('mafe-ruiz-producto','María Fernanda Ruiz','Escribe sobre descubrimiento de producto con equipos pequeños; sus lectores son fundadores.'),
                   ('camejia-startups','Carlos Andrés Mejía','Inversionista ángel en startups latinoamericanas; comenta sobre MVPs y primeros clientes.'),
                   ('analu-torres','Ana Lucía Torres','CTO de una agrotech; publica sobre arquitectura y entrega de software.')]
        self.referents=[]
        for i,(handle,name,reason) in enumerate(referents):
            self.referents.append(Referent.objects.create(id=uid(f'referent:{handle}'),account=self.fake,public_identifier=handle,
                provider_user_id=f'qa-ref-{i}',display_name=name,profile_url=f'{FAKE_URL}/in/{handle}',reason=reason,created_by=self.user,
                last_observed_at=self.ago(hours=6+i)))
        texts=['Validar antes de construir no es lento: es lo que evita construir dos veces. ¿Cómo validan ustedes un MVP?',
               'Los primeros diez clientes no se consiguen con anuncios. Se consiguen con conversaciones incómodas.',
               'Migramos de un monolito a servicios y volvimos al monolito. Lo que aprendimos sobre el tamaño del equipo.',
               'La IA no arregla un proceso que nadie entiende. Primero el proceso, después el modelo.',
               'Un buen brief de producto cabe en una página. Si no cabe, todavía no sabemos qué queremos.',
               'Contratar al primer ingeniero: lo que pregunto en la entrevista y por qué.',
               'Medir activación antes que retención: el error que más veo en startups de etapa temprana.',
               'Lo que cambia cuando el cliente participa en la demo de cada viernes.']
        self.posts=[]
        for i,text in enumerate(texts):
            ref=self.referents[i%3]
            self.posts.append(ObservedPost.objects.create(id=uid(f'post:{i+1}'),account=self.fake,referent=ref,provider_post_id=f'urn:li:activity:qa-{i+1}',
                share_url=f'{FAKE_URL}/feed/update/qa-{i+1}',author_name=ref.display_name,author_public_identifier=ref.public_identifier,
                author_provider_id=ref.provider_user_id,text=text,posted_at=self.ago(days=i+1,hours=3),comments_count=12+i*3,reactions_count=80+i*17,
                observed_at=self.ago(days=i,hours=2)))
        people=[
            ('pedro-salazar','Pedro Salazar','Desarrollador backend en una fintech','candidate',None,'commenter',{}),
            ('laura-gomez','Laura Gómez','Head of Product en un marketplace B2B','fit',None,'commenter',
             {'fit':True,'role':'comprador','modality':'projectapp','reason':'Lidera producto en un marketplace B2B y pregunta por equipos externos.'}),
            ('tomas-recruiter','Tomás Recruiter','Reclutador de talento tech','discarded',None,'search',
             {'fit':False,'role':'aliado','modality':'comunidad_autoridad','reason':'Reclutador masivo: no encaja.'}),
            ('julian-herrera','Julián Herrera','Fundador de una edtech en etapa semilla','followed',{'followed':3},'commenter',
             {'fit':True,'role':'par','modality':'personal_startups','reason':'Fundador en etapa semilla; comenta sobre validación.'}),
            ('camila-ortiz','Camila Ortiz','COO de una startup de logística','followed',{'followed':1.5},'commenter',
             {'fit':True,'role':'comprador','modality':'projectapp','reason':'Opera una startup de logística que está creciendo su equipo de software.'}),
            ('diego-ramirez','Diego Ramírez','Product Manager en una aseguradora','invited',{'followed':7,'invited':4},'search',
             {'fit':True,'role':'recomendador','modality':'projectapp','reason':'PM en una aseguradora; recomienda proveedores.'}),
            ('andres-restrepo','Andrés Restrepo','CTO de una empresa de salud digital','connected',{'followed':9,'invited':6,'connected':2},'commenter',
             {'fit':True,'role':'comprador','modality':'projectapp','reason':'CTO que busca acelerar la entrega de su plataforma.'}),
            ('valentina-castro','Valentina Castro','Fundadora de una fintech para cooperativas','connected',{'followed':16,'invited':13,'connected':10},'commenter',
             {'fit':True,'role':'par','modality':'personal_startups','reason':'Fundadora; pide consejo sobre su MVP.'}),
            ('felipe-vargas','Felipe Vargas','Consultor de transformación digital','closed',{'followed':30,'invited':27},'search',
             {'fit':True,'role':'divulgador','modality':'comunidad_autoridad','reason':'Divulga sobre producto; ignoró la invitación.'}),
            ('natalia-rojas','Natalia Rojas','Directora de innovación en una cooperativa','incoming',None,'incoming',
             {'fit':True,'role':'comprador','modality':'projectapp','reason':'Te invitó: dirige innovación y busca socios de software.'}),
            ('sofia-martinez','Sofía Martínez','Gerente de una cooperativa de ahorro','connected',{'connected':5},'incoming',
             {'fit':True,'role':'comprador','modality':'projectapp','reason':'Te invitó y encaja: necesita una plataforma para su cooperativa.'}),
        ]
        self.people={}
        for i,(handle,name,headline,stage,times,source,classification) in enumerate(people):
            times=times or {};discovered=self.ago(days=max([30]+[v+3 for v in times.values()]) if times else 2+i)
            history=[{'at':discovered.isoformat(),'event':'discovered','detail':'Comentó en un post de un referente' if source=='commenter' else 'Búsqueda' if source=='search' else 'Invitación recibida'}]
            if classification:
                history.append({'at':(discovered+timedelta(hours=2)).isoformat(),'event':'classified','detail':'Encaja' if classification.get('fit') else 'No encaja'})
            moments={k:self.ago(days=v) for k,v in times.items()}
            for key,event,detail in (('followed','followed','Seguida'),('invited','invited','Invitación enviada sin nota'),('connected','connected','Aceptó la invitación')):
                if key in moments:history.append({'at':moments[key].isoformat(),'event':event,'detail':detail})
            if stage=='closed':history.append({'at':self.ago(days=6).isoformat(),'event':'closed','detail':'Invitación ignorada'})
            if stage=='discarded':history.append({'at':self.ago(days=1).isoformat(),'event':'discarded','detail':'Gustavo la descartó: reclutador'})
            if classification:
                classification=dict(classification,affinity='hispanohablante_declarada',confidence=0.82,model='claude-sonnet-5-5',
                                    at=(discovered+timedelta(hours=2)).isoformat())
            contact=Contact.objects.create(id=uid(f'contact:{handle}'),account=self.fake,provider_user_id=f'qa-user-{handle}',public_identifier=handle,
                display_name=name,headline=headline,profile_url=f'{FAKE_URL}/in/{handle}',location='Medellín, Colombia',source=source,
                evidence={'post_id':str(self.posts[i%len(self.posts)].id),'comment':'Muy de acuerdo: validar con clientes reales nos ahorró meses.'} if source=='commenter' else {},
                network_distance='FIRST_DEGREE' if stage=='connected' else 'SECOND_DEGREE',is_following=stage in ('followed','invited','connected'),
                invitation_id=f'qa-inv-{handle}' if stage in ('invited','incoming') else '',classification=classification,stage=stage,history=history,
                notes=[{'id':'qa-nota-1','at':self.ago(days=1).isoformat(),'text':'Hablamos en el meetup de producto; le interesa el tema de MVPs.','by':QA_USERNAME}] if handle=='andres-restrepo' else [],
                profile_checked_at=discovered+timedelta(hours=1),followed_at=moments.get('followed'),invited_at=moments.get('invited'),
                connected_at=moments.get('connected'),discovered_at=discovered,updated_at=max([discovered,*moments.values()]))
            self.people[handle]=contact

    # ------------------------------------------------------------------ editorial pieces

    def pieces(self):
        specs=[('manana',1,'ready','Documentar decisiones vale más que documentar tareas','architecture_delivery','projectapp','lector_comprador'),
               ('publicada3',-3,'published','Las startups pierden meses por no hablar con sus primeros clientes','business_to_product','personal_startups','lector_par'),
               ('publicada8',-8,'published','Un MVP no es una versión barata del producto','business_to_product','personal_startups','lector_lider'),
               ('bloqueada',-2,'blocked','Qué aprendí cobrando por mi primer proyecto','business_to_product','projectapp','lector_comprador'),
               ('saltada',-1,'skipped',None,None,None,None),
               ('fallida',-5,'failed','Cómo elegimos el stack de un MVP en dos días','architecture_delivery','projectapp','lector_divulgador')]
        self.piece={}
        for key,offset,kind,thesis,pillar,modality,reader in specs:
            day=self.today+timedelta(days=offset)
            when=datetime.combine(day,time(8,30),tzinfo=self.tz)
            fields={'brief':{},'variants':{},'panel':{},'selection':{},'verification':{},'final_text':'','citations':[],'signals':[],'usage':[],'metrics':{},'note':'','stage':''}
            if thesis:
                brief,variants,panel,selection,final,usage=piece_texts(key,thesis,pillar,modality,reader)
                fields.update(brief=brief,variants=variants,panel=panel,selection=selection,final_text=final,usage=usage,
                              citations=['LI-05-M001-K03','LI-05-M002-K04','LI-06-M002-K09'],
                              signals=[{'id':str(self.posts[0].id),'author':self.posts[0].author_name,'text':self.posts[0].text,'url':self.posts[0].share_url}],
                              verification=verification_ok(final),stage='verificador')
            if kind=='ready':
                state='ready';fields['note']='Lista para la política autónoma.'
            elif kind=='published':
                state='ready';fields['note']='Lista para la política autónoma.';fields['metrics']={'impressions':1840 if key=='publicada8' else 960}
            elif kind=='blocked':
                state='blocked'
                original=fields['final_text']
                repaired=original.replace('We lost two weeks','I once charged half of what the project cost')
                reasons=['Hallazgo material (invented_experience): «I once charged half of what the project cost» no está en la memoria confirmada',
                         'Ronda de reparación: el texto reparado siguió bloqueado']
                fields['final_text']=original
                fields['verification']={'verdict':'blocked','model_verdict':'blocked','summary':'Cuenta una experiencia que no está en la memoria de Gustavo.',
                    'findings':[{'issue':'invented_experience','severity':'material','quote':'I once charged half of what the project cost','detail':'Experiencia no confirmada'}],
                    'checked_claims':[{'text':'Cobré la mitad de lo que costó el proyecto','status':'unsupported'}],'blocking_reasons':reasons,'rules':[],
                    'text_sha256':sha(original),
                    'repair':{'trigger':'verificador','outcome':'bloqueada','decision':'repaired','model':'claude-opus-5-5',
                              'findings':[{'source':'verificador','issue':'invented_experience','quote':'We lost two weeks','detail':'Experiencia no confirmada'}],
                              'changes':[{'finding':'Experiencia no confirmada','change':'Reescribí la anécdota en términos generales'}],
                              'rationale':'Quité la cifra, pero la anécdota sigue sin respaldo.','note':'','original_text':original,
                              'original_sha256':sha(original),'repaired_sha256':sha(repaired),
                              'first_review':{'verdict':'blocked','findings':[],'checked_claims':[],'summary':'Primera lectura del verificador.','blocking_reasons':reasons[:1]}}}
                fields['usage']=fields['usage']+[{'stage':'reparacion','model':'claude-opus-5-5','input_tokens':2100,'output_tokens':420,'estimated_usd':'0.019'}]
                fields['note']='; '.join(reasons)
            elif kind=='skipped':
                state='skipped';fields['stage']='director'
                fields['brief']={'decision':'skip','skip_reason':'No había material genuino: las señales de la semana repetían el tema del lunes.'}
                fields['note']='No había material genuino: las señales de la semana repetían el tema del lunes.'
                fields['usage']=[{'stage':'director','model':'claude-opus-5-5','input_tokens':3600,'output_tokens':300,'estimated_usd':'0.031'}]
            else:
                state='failed';fields['stage']='lectores';fields['panel']={};fields['selection']={};fields['verification']={};fields['final_text']=''
                fields['note']='Error interno en la preparación; no se repite el gasto.'
                fields['usage']=fields['usage'][:2]
            piece=EditorialPiece.objects.create(id=uid(f'piece:{key}'),account=self.official,slot_date=day,scheduled_for=when,state=state,created_by=self.robot,
                                                origin_job=str(uid(f'job:piece:{key}')),**fields)
            EditorialPiece.objects.filter(pk=piece.pk).update(created_at=when-timedelta(hours=14))
            self.piece[key]=piece
        # CONT-09 of the ready pieces: approved (tomorrow) and published with its metrics.
        tomorrow=self.piece['manana']
        self.action(tomorrow,'CONT-09',{'text':tomorrow.final_text},'approved',created=self.ago(hours=3),decided=self.ago(hours=2),
                    rationale=f'{tomorrow.brief["thesis"]} — B tiene una historia verificable.',review={'decision':'approve','reasons':['Cumple la política'],'model':'jev-1.14.0'},key='cont09:manana')
        for key,impressions in (('publicada3',960),('publicada8',1840)):
            piece=self.piece[key];started=piece.scheduled_for+timedelta(minutes=1)
            self.action(piece,'CONT-09',{'text':piece.final_text},'confirmed',created=piece.scheduled_for-timedelta(hours=12),decided=piece.scheduled_for-timedelta(hours=11),
                        executed=started,external_url=f'{FAKE_URL}/feed/update/qa-{key}',key=f'cont09:{key}')
            ages=[('24h',timedelta(hours=24),0.45),('72h',timedelta(hours=72),0.8)]+([('7d',timedelta(days=7),1.0)] if key=='publicada8' else [])
            for kind,age,share in ages:
                PostMetric.objects.create(id=uid(f'metric:{key}:{kind}'),piece=piece,provider_post_id=f'qa-{key}',share_url=f'{FAKE_URL}/feed/update/qa-{key}',kind=kind,
                    impressions=int(impressions*share),reactions=int(42*share),comments=int(11*share),published_at=started,
                    # A reading that did not return the reposts (CAL-07, RES-06: «—», never 0).
                    reposts=None if (key,kind)==('publicada3','72h') else int(3*share),captured_at=started+age+timedelta(minutes=20),
                    commenters=[{'provider_user_id':'qa-user-andres-restrepo','name':'Andrés Restrepo','substantive':True,'role':'comprador','fit':True},
                                {'provider_user_id':'qa-user-pedro-salazar','name':'Pedro Salazar','substantive':False,'role':'par','fit':False}])

    def action(self,target,capability,payload,state,created,decided=None,executed=None,external_url='',rationale='',review=None,key=None,note=''):
        """One ActionProposal (and its execution when it ran), with the operator's exact payload hash."""
        post=target if isinstance(target,ObservedPost) else None
        piece=target if isinstance(target,EditorialPiece) else None
        contact=target if isinstance(target,Contact) else None
        account=(post or piece or contact).account_id
        proposal=ActionProposal.objects.create(id=uid(f'action:{key}'),account_id=account,post=post,piece=piece,contact=contact,capability=capability,
            payload=payload,payload_hash=operador.payload_hash(account,capability,operador.target_of(post,piece,contact),payload),
            rationale=rationale,source='agent',model='claude-sonnet-5-5' if capability=='INT-03' else '',state=state,created_by=self.robot,
            approved_hash='' if state=='proposed' else operador.payload_hash(account,capability,operador.target_of(post,piece,contact),payload),
            decided_at=decided,review=review or ({} if state=='proposed' else {'decision':'approve','reasons':['Dentro de la política'],'model':'jev-1.14.0'}))
        ActionProposal.objects.filter(pk=proposal.pk).update(created_at=created)
        if executed:
            execution_state={'confirmed':'confirmed','uncertain':'uncertain','failed':'failed','sent':'sent'}[state]
            ActionExecution.objects.create(id=uid(f'execution:{key}'),proposal=proposal,idempotency_key=sha(f'qa:{key}'),provider='fake',state=execution_state,
                executed_by=self.robot,started_at=executed,finished_at=None if state=='uncertain' else executed+timedelta(seconds=4),
                external_id=f'qa-ext-{key}' if state=='confirmed' else '',external_url=external_url,
                error_kind={'failed':'provider_error','uncertain':'timeout'}.get(state,''),http_status=502 if state=='failed' else None,
                note=note or {'uncertain':'El proveedor no respondió a tiempo: no se sabe si se publicó.','failed':'El proveedor rechazó el comentario.'}.get(state,''))
        return proposal

    # ------------------------------------------------------------------ proposals and past actions

    def proposals(self):
        p=self.posts;people=self.people
        self.action(p[0],'INT-03',{'text':'Totalmente: en ProjectApp validamos con cinco clientes antes de escribir código, y nos ahorró rehacer el MVP.'},
                    'proposed',created=self.ago(hours=2),rationale='Aporta una práctica concreta a la conversación.',key='comentario:propuesto:1')
        self.action(p[1],'INT-03',{'text':'Las conversaciones incómodas también enseñan qué no construir. ¿Cuál fue la que más te cambió el plan?'},
                    'proposed',created=self.ago(hours=1),rationale='Pregunta abierta que invita a la autora a profundizar.',key='comentario:propuesto:2')
        self.action(people['laura-gomez'],'RED-01',{},'proposed',created=self.ago(hours=5),rationale='Lidera producto en un marketplace B2B.',key='red01:laura')
        self.action(people['julian-herrera'],'RED-02',{},'proposed',created=self.ago(hours=4),rationale='Terminó la espera tras seguirlo.',key='red02:julian')
        # «¿Salió o no?»: an uncertain comment (Tu turno, urgente).
        self.action(p[2],'INT-03',{'text':'Volver al monolito con un equipo de cuatro personas suele ser la decisión más honesta.'},'uncertain',
                    created=self.ago(hours=4),decided=self.ago(hours=3,minutes=50),executed=self.ago(hours=3,minutes=30),key='comentario:incierto')
        # What already went out, for the Lista view, the calendar counts and Resultados.
        done=[(p[3],'INT-03',{'text':'Primero el proceso: lo vimos en tres proyectos de IA este año.'},1),
              (p[4],'INT-03',{'text':'Una página obliga a decidir. Lo demás es anexo.'},2),
              (p[5],'INT-03',{'text':'Yo pregunto por la última vez que borró código propio y por qué.'},4),
              (p[6],'INT-03',{'text':'Activación primero: si nadie llega al momento útil, no hay nada que retener.'},9),
              (p[0],'INT-02',{'reaction':'linkedin_insightful'},1),(p[1],'INT-02',{'reaction':'linkedin_like'},1),
              (p[3],'INT-02',{'reaction':'linkedin_celebrate'},3),(p[7],'INT-02',{'reaction':'linkedin_like'},5)]
        for i,(post,capability,payload,days) in enumerate(done):
            when=self.at(-days,10+i%6,15)
            self.action(post,capability,payload,'confirmed',created=when-timedelta(hours=2),decided=when-timedelta(hours=1),executed=when,
                        external_url=post.share_url,key=f'hecho:{i}')
        for handle,capability,days in (('julian-herrera','RED-01',3),('camila-ortiz','RED-01',1.5),('diego-ramirez','RED-01',7),('diego-ramirez','RED-02',4),
                                       ('andres-restrepo','RED-01',9),('andres-restrepo','RED-02',6),('valentina-castro','RED-02',13),
                                       ('felipe-vargas','RED-02',27),('sofia-martinez','RED-04',5)):
            when=self.ago(days=days)
            self.action(people[handle],capability,{},'confirmed',created=when-timedelta(hours=3),decided=when-timedelta(hours=2),executed=when,
                        external_url=people[handle].profile_url,key=f'red:{handle}:{capability}')
        self.action(p[7],'INT-03',{'text':'La demo de los viernes cambia quién se siente dueño del producto.'},'failed',
                    created=self.at(-6,11),decided=self.at(-6,11,10),executed=self.at(-6,11,20),key='comentario:fallido')
        # «En cola» (Calendario › Lista and the day panel, CAL-04 and CAL-13): approved, waiting for the window or the
        # spacing, each with its Vetar. Nothing executes them in the QA world (no worker runs).
        self.action(p[5],'INT-02',{'reaction':'linkedin_celebrate'},'approved',created=self.ago(hours=1,minutes=30),decided=self.ago(hours=1),
                    rationale='Una práctica de contratación que encaja con el pilar de equipo.',key='cola:reaccion')
        self.action(people['camila-ortiz'],'RED-02',{},'approved',created=self.ago(hours=2,minutes=30),decided=self.ago(hours=2),
                    rationale='Terminó la espera tras seguirla: invitación sin nota.',key='cola:red02:camila')

    def opportunities(self):
        def opportunity(key,stage,modality,contact=None,person='',company='',created_days=20,steps=(),next_action='',next_at=None,need=''):
            labels=dict(Opportunity.Stage.choices);created=self.ago(days=created_days)
            history=[{'at':created.isoformat(),'event':'created','detail':f'Etapa inicial: {labels[steps[0] if steps else stage]}','stage':steps[0] if steps else stage}]
            previous=steps[0] if steps else stage;moved=created
            for i,step in enumerate(steps[1:],start=1):
                moved=created+timedelta(days=i*max(1,created_days//(len(steps)+1)))
                history.append({'at':moved.isoformat(),'event':'stage','detail':f'{labels[previous]} → {labels[step]}','stage':step});previous=step
            item=Opportunity.objects.create(id=uid(f'opportunity:{key}'),contact=contact,person_name=person,company=company,modality=modality,channel='linkedin',
                stage=stage,attribution='cito_contenido' if contact else 'lo_dijo',need=need,budget='Por definir',dedication='',next_action=next_action,
                next_action_at=next_at,notes='',history=history,created_by=self.user,stage_changed_at=moved,
                closed_at=moved if stage in ('acuerdo','sin_acuerdo') else None)
            Opportunity.objects.filter(pk=item.pk).update(created_at=created,updated_at=moved)
        people=self.people
        opportunity('andres','reunion','projectapp',contact=people['andres-restrepo'],created_days=8,steps=('conversacion','necesidad','cualificada','reunion'),
                    next_action='Reunión de alcance',next_at=self.at(2,10),need='Acelerar la entrega de la plataforma de citas médicas.')
        opportunity('valentina','necesidad','personal_startups',contact=people['valentina-castro'],created_days=6,steps=('conversacion','necesidad'),
                    need='Consejo para recortar el alcance de su MVP.')
        opportunity('mauricio','propuesta','projectapp',person='Mauricio Peña',company='Agrotech del Valle',created_days=25,
                    steps=('conversacion','necesidad','cualificada','reunion','propuesta'),next_action='Enviar la propuesta revisada',next_at=self.at(1,15),
                    need='App de trazabilidad para pequeños productores.')
        opportunity('isabel','conversacion','personal_startups',person='Isabel Duarte',created_days=2,need='')
        opportunity('sofia','acuerdo','projectapp',contact=people['sofia-martinez'],created_days=60,steps=('conversacion','necesidad','propuesta','acuerdo'))
        opportunity('ricardo','sin_acuerdo','projectapp',person='Ricardo Gil',company='Logística Andina',created_days=45,steps=('conversacion','sin_acuerdo'))

    def conversation(self):
        contact=self.people['sofia-martinez'];inbound_at=self.ago(hours=5)
        messages=[{'id':'qa-msg-1','at':self.ago(days=4).isoformat(),'from_me':False,'text':'Gracias por aceptar la invitación, Gustavo.'},
                  {'id':'qa-msg-2','at':self.ago(days=4,hours=-1).isoformat(),'from_me':True,'text':'¡Con gusto, Sofía! Un placer.'},
                  {'id':'qa-msg-3','at':inbound_at.isoformat(),'from_me':False,
                   'text':'Hola Gustavo, vi tu post sobre MVPs. Estamos armando la plataforma de nuestra cooperativa y buscamos quién nos ayude a construirla. ¿Tienes espacio para una llamada esta semana?'}]
        Conversation.objects.create(id=uid('conversation:sofia'),account=self.fake,provider_chat_id='qa-chat-sofia',contact=contact,attendee_name=contact.display_name,
            attendee_provider_id=contact.provider_user_id,last_message_at=inbound_at,last_message_preview=messages[-1]['text'][:300],last_from_me=False,
            messages=messages,assessment={'message_id':'qa-msg-3','answers':{'oportunidad':0.86,'espera':0.91,'venta':0.04,'startups':0.2,'projectapp':0.8},
                                          'thresholds':{'opportunity':0.6,'reply':0.6,'pitch':0.4},'pitch':False,'opportunity':True,'awaiting_reply':True,
                                          'modality':'projectapp','model':'jev-1.14.0','cost_usd':0.0004,'at':self.ago(hours=4,minutes=50).isoformat()})

    # ------------------------------------------------------------------ Tu turno: questions and facts

    def questions(self):
        rows=[('proyectos','director_editorial','¿Cuántos proyectos de software entregó ProjectApp en 2025?','Para la pieza del jueves sobre aprendizajes de entregar software.',
               'projectapp.proyectos_2025','text',[],True,self.at(1,20),None,self.ago(hours=6)),
              ('startups','posicionamiento','¿Con qué tipo de startups prefieres trabajar?','Para priorizar a quién seguir e invitar en tu barrio.',
               'preferencia.startups','choice',['Fintech','Agrotech','Salud','Educación'],False,None,None,self.ago(days=1)),
              ('ingles','relaciones_comunidad','¿Te parece bien que el equipo comente en publicaciones en inglés?','Hoy solo comenta en español.',
               'comentarios.ingles','yes_no',[],False,None,None,self.ago(days=2)),
              ('ciudad','perfil','¿En qué ciudad vives actualmente?','Para presentarte bien en el perfil y en los posts.',
               'ubicacion.ciudad','text',[],True,None,self.at(2,9),self.ago(days=3))]
        for key,agent,question,purpose,memory_key,answer_type,options,public,deadline,postponed,created in rows:
            item=TeamQuestion.objects.create(id=uid(f'question:{key}'),kind='ask',agent=agent,question=question,purpose=purpose,memory_key=memory_key,
                answer_type=answer_type,options=options,suggested_public=public,origin='qa',deadline=deadline,postponed_until=postponed)
            TeamQuestion.objects.filter(pk=item.pk).update(created_at=created)

    def facts(self):
        """Confirmed user memory («Lo que el equipo sabe de ti»), written on this transaction's connection."""
        rows=[('projectapp.fundacion',{'texto':'Fundé ProjectApp en Medellín.','uso_publico':True,'tema':'ProjectApp'}),
              ('preferencia.equipos',{'texto':'Prefiero trabajar con equipos pequeños que deciden rápido.','uso_publico':True}),
              ('privado.clientes',{'texto':'No nombrar a los clientes actuales en público.','uso_publico':False})]
        with connection.cursor() as cursor:
            for key,value in rows:
                cursor.execute('INSERT INTO memory(id,namespace,key,version,value,status,author,evidence,created_at) VALUES(%s,%s,%s,1,%s,%s,%s,%s,%s)',
                               (str(uid(f'memory:{key}')),'user',key,Jsonb(value),'confirmed',f'user:{self.user.pk}','Semilla de QA',self.ago(days=10)))

    # ------------------------------------------------------------------ notifications, captures, gallery

    def notifications(self):
        blocked=self.piece['bloqueada'];andres=self.people['andres-restrepo']
        rows=[('bloqueada','piece_blocked','sistema',f'El verificador bloqueó la pieza del {blocked.slot_date:%d/%m}','Cuenta una experiencia que no está en tu memoria.',
               f'/calendario/pieza/{blocked.id}',self.ago(days=2,hours=-1),None),
              ('conexion','connection_fit','red','Andrés Restrepo aceptó tu invitación','CTO de una empresa de salud digital.',f'/personas/{andres.id}',self.ago(days=2),None),
              ('captura','capture_processed','tuyo','Tu nota quedó en Lo que el equipo sabe de ti','Míralo en «Lo que enviaste».','/?enviado=1',self.ago(days=1,hours=2),None),
              ('resumen','weekly_summary','tuyo','El resumen de la semana está listo','El analista propone una orientación.','/resultados#resumen',self.ago(days=1),None),
              ('manana','piece_scheduled','publicaciones','La pieza de mañana está lista','Sale a las 08:30 si no la vetas.',f'/calendario/pieza/{self.piece["manana"].id}',self.ago(hours=2),None),
              ('publicada','piece_published','publicaciones','Se publicó la pieza «Las startups pierden meses…»','Ya tiene sus primeras impresiones.',
               f'/calendario/pieza/{self.piece["publicada3"].id}',self.ago(days=3),self.ago(days=3)+timedelta(hours=1)),
              ('oportunidad','opportunity','conversaciones','Oportunidad con Mauricio Peña: Propuesta','Siguiente paso: Enviar la propuesta revisada',
               '/personas?pestana=oportunidades',self.ago(days=1,hours=6),self.ago(days=1))]
        for key,kind,layer,title,detail,link,created,read in rows:
            Notification.objects.create(id=uid(f'notification:{key}'),kind=kind,layer=layer,title=title,detail=detail,link=link,ref=f'qa:{key}',
                                        created_at=created,read_at=read)

    def captures(self):
        voice=Capture.objects.create(id=uid('capture:voz'),created_by=self.user,note='',purpose='dato',audio_mime='audio/wav',audio_duration_s=2.0,
            transcript='Fundé ProjectApp en 2019 en Medellín, con dos amigos de la universidad.',transcript_language='es',transcript_provider_id='qa-transcript-1',
            state='dato_guardado',outcome={'kind':'dato','text':'Está en Lo que el equipo sabe de ti · ProjectApp','link':'/tu-turno/sabe'},
            routed_to={'kind':'dato','classified':True,'reason':'Es un dato sobre Gustavo.','memory_key':'projectapp.fundacion'})
        voice.audio.save('nota.wav',ContentFile(silent_wav()),save=True)
        Capture.objects.filter(pk=voice.pk).update(created_at=self.ago(days=1,hours=3))
        idea=Capture.objects.create(id=uid('capture:idea'),created_by=self.user,note='Idea: contar cómo elegimos el stack de un MVP en dos días',purpose='post',
            state='usado',outcome={'kind':'idea','text':'Usada en la pieza del '+f'{self.piece["fallida"].slot_date:%d/%m}','link':f'/calendario/pieza/{self.piece["fallida"].id}'},
            routed_to={'kind':'idea','classified':False,'piece_id':str(self.piece['fallida'].id)})
        Capture.objects.filter(pk=idea.pk).update(created_at=self.ago(days=6))

    def gallery(self):
        palettes=[((120,190,230),(70,150,90),(200,90,60)),((240,200,150),(150,110,80),(60,60,90)),
                  ((30,40,80),(20,90,110),(15,241,206)),((200,220,240),(230,230,220),(0,113,94))]
        rows=[('nueva','sin_usar','',True,None,None,None,self.ago(hours=3)),
              ('pizarra','sin_usar','Pizarra de la sesión de producto',True,None,None,None,self.ago(days=3)),
              ('elegida','elegida','Equipo en la demo del viernes',True,self.piece['manana'],self.today+timedelta(days=1),None,self.ago(days=5)),
              ('publicada','publicada','Taller con fundadores en Medellín',False,self.piece['publicada3'],self.piece['publicada3'].slot_date,
               self.piece['publicada3'].scheduled_for,self.ago(days=9))]
        for i,(key,state,note,ai,piece,chosen_for,published,created) in enumerate(rows):
            data=png(240,180,palettes[i],i+2)
            photo=GalleryPhoto(id=uid(f'photo:{key}'),mime='image/png',size_bytes=len(data),width=240,height=180,note=note,allow_ai_edit=ai,state=state,
                               chosen_piece=piece,chosen_for=chosen_for,published_at=published,created_by=self.user)
            photo.image.save(f'{key}.png',ContentFile(data),save=False);photo.save()
            GalleryPhoto.objects.filter(pk=photo.pk).update(created_at=created)

    # ------------------------------------------------------------------ results history

    def results(self):
        """~100 days of audience snapshots, machine jobs and network syncs, so 7, 28 and 90 days compare with data."""
        days=100;snapshots=[];jobs=[]
        kinds=['observe','collect_metrics','sync_network','propose_comment','classify_contacts']
        for back in range(days,-1,-1):
            day=self.today-timedelta(days=back);progress=(days-back)/days
            snapshots.append(AudienceSnapshot(id=uid(f'audience:{back}'),day=day,followers=1800+int(250*progress)+(back*7)%5,
                connections=900+int(80*progress),profile_views=120+int(60*progress)+(back*13)%17,profile_views_days=28,
                captured_at=datetime.combine(day,time(6,5),tzinfo=self.tz)))
            moment=datetime.combine(day,time(7,10),tzinfo=self.tz)
            if moment<=self.now:
                kind=kinds[back%len(kinds)]
                jobs.append(Job(id=uid(f'job:{back}'),owner=self.robot,request_hash=sha(f'qa-job-{back}'),agent='operador_cuenta',task=kind,kind=kind,
                                state='complete',created_at=moment,started_at=moment,finished_at=moment+timedelta(minutes=2),result_status='ok'))
        AudienceSnapshot.objects.bulk_create(snapshots);Job.objects.bulk_create(jobs)
        events=[]
        for back in range(days,0,-1):
            moment=datetime.combine(self.today-timedelta(days=back),time(7,30),tzinfo=self.tz)
            events.append(AuditEvent(actor=self.robot,action='network.synced',target=str(self.fake.id),metadata={'qa':True},created_at=moment))
            if back%3==0:events.append(AuditEvent(actor=self.robot,action='network.discovered',target=str(self.fake.id),metadata={'qa':True},created_at=moment))
        AuditEvent.objects.bulk_create(events)
        # Jobs of the editorial pieces, so the office scene has a «last done» per role.
        for key,piece in self.piece.items():
            Job.objects.create(id=uid(f'job:piece:{key}'),owner=self.robot,request_hash=sha(f'qa-piece-{key}'),agent='director_editorial',task='prepare_piece',
                               kind='prepare_piece',params={'slot':piece.slot_date.isoformat()},state='complete' if piece.state!='failed' else 'failed',
                               created_at=piece.created_at,started_at=piece.created_at,finished_at=piece.created_at+timedelta(minutes=9),
                               result_status=piece.state,error=piece.note if piece.state=='failed' else '')

    def summaries(self):
        last=self.today-timedelta(days=self.today.weekday()+7)
        analysis={'titular':'Semana con más conversación que alcance: los posts sobre MVPs generaron dos oportunidades.',
                  'lo_que_funciono':[{'texto':'El post sobre MVPs tuvo la mejor interacción del mes.','cifra':'4,1 %'},
                                     {'texto':'Dos personas que encajan aceptaron la invitación.','cifra':'2'}],
                  'lo_que_no':[{'texto':'La pieza del martes quedó bloqueada por una experiencia sin respaldo.','cifra':'1'}],
                  'recomendaciones':[{'texto':'Contar decisiones reales de proyectos, con su contexto.','cifra':''},
                                     {'texto':'Responder a Sofía Martínez antes del viernes.','cifra':''}],
                  'orientacion_propuesta':'Prioriza posts sobre cómo validar un MVP con clientes reales; menos sobre herramientas.',
                  'advertencias':['Pocos datos: 2 de 3 posts con corte de 72 h.'],'validacion':{'ok':True,'numeros_desconocidos':[]}}
        older={'titular':'Primera semana completa del barrio: crecimiento estable.','lo_que_funciono':[{'texto':'Más visitas al perfil.','cifra':'+12 %'}],
               'lo_que_no':[],'recomendaciones':[{'texto':'Publicar sobre arquitectura una vez por semana.','cifra':''}],
               'orientacion_propuesta':'Habla a fundadores de startups latinoamericanas en etapa temprana.','advertencias':[],'validacion':{'ok':True}}
        stats={'semana':{'desde':last.isoformat(),'hasta':(last+timedelta(days=6)).isoformat()},'avisos_de_datos':analysis['advertencias']}
        WeeklySummary.objects.create(id=uid('summary:last'),week_start=last,stats=stats,analysis=analysis,state='nuevo',usage={'model':'claude-opus-5-5'},
                                     cost_usd=Decimal('0.084'),origin_job=str(uid('job:summary:last')))
        WeeklySummary.objects.create(id=uid('summary:older'),week_start=last-timedelta(days=7),stats={},analysis=older,state='aplicado',usage={'model':'claude-opus-5-5'},
                                     cost_usd=Decimal('0.079'),previous_orientation='',decided_by=self.user,decided_at=self.ago(days=12))
        WeeklySummary.objects.filter(id=uid('summary:last')).update(created_at=datetime.combine(last+timedelta(days=7),time(7),tzinfo=self.tz))

    def spend(self):
        rows=[('anthropic','propose-comment',Decimal('0.042'),0),('anthropic','editorial-director',Decimal('0.31'),0),('anthropic','network-classify',Decimal('0.05'),0),
              ('anthropic','editorial-redactor',Decimal('0.52'),3),('anthropic','weekly-summary',Decimal('0.084'),6),('typesafe','lead-review',Decimal('0.0021'),1),
              ('assemblyai','capture-transcription',Decimal('0.004'),1),('anthropic','propose-comment',Decimal('0.038'),2)]
        with connection.cursor() as cursor:
            for i,(provider,purpose,usd,days) in enumerate(rows):
                created=self.now-timedelta(days=days,minutes=30+i)
                if created.astimezone(self.tz).month!=self.now.astimezone(self.tz).month:created=self.now-timedelta(minutes=30+i)
                cursor.execute('INSERT INTO usage_ledger(id,provider,purpose,reserved_usd,actual_usd,status,usage,created_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',
                               (str(uid(f'usage:{i}')),provider,purpose,usd,usd,'complete',Jsonb({'qa':True}),created))

    # ------------------------------------------------------------------ settings and devices

    def settings(self):
        orientation=Orientation.current()
        orientation.text='Habla a fundadores de startups latinoamericanas en etapa temprana. Evita el tono de vendedor.'
        orientation.updated_by=self.user;orientation.updated_at=self.ago(days=12);orientation.save()
        control=OperatorControl.current();control.paused=False;control.reason='';control.updated_by=None;control.updated_at=None;control.save()
        preference=OfficePreference.current();preference.push_disabled=[];preference.gallery_ai_edit_default=True
        preference.updated_by=None;preference.updated_at=None;preference.save()

    def devices(self):
        """A second phone in «Dispositivos con la app» (the one running the app appears when it logs in)."""
        DeviceToken.objects.filter(id=uid('device:pixel7')).delete()
        device=DeviceToken.objects.create(id=uid('device:pixel7'),user=self.user,name=EXTRA_DEVICE,digest=digest('qa-seed-device-pixel7-never-a-real-token'))
        DeviceToken.objects.filter(pk=device.pk).update(created_at=self.ago(days=20),last_used_at=self.ago(days=2))
