"""Personas › Conexiones (12/11/2026): Gustavo's people database is only who accepted, by barrio role, the most recent
connection first; the agents' queue (candidate … discarded) never shows there, and the old funnel links land on it."""
from datetime import timedelta
from django.utils import timezone
from team_backend import operador
from team_backend.models import Contact
from team_backend.tests.test_operador import OperatorBase

QUEUE=('candidate','fit','followed','invited','incoming','closed','discarded')

class ConnectionsTests(OperatorBase):
    def person(self,handle,name,stage='connected',classification=None,connected_days=None,updated_days=0):
        now=timezone.now()
        return Contact.objects.create(account=self.account,provider_user_id=f'ACo{handle}',display_name=name,source='commenter',stage=stage,
            classification=classification or {},connected_at=now-timedelta(days=connected_days) if connected_days is not None else None,
            updated_at=now-timedelta(days=updated_days))

    def setUp(self):
        super().setUp()
        self.person('ana','Ana Compradora',classification={'fit':True,'role':'comprador'},connected_days=1,updated_days=9)
        self.person('bruno','Bruno Par',classification={'fit':True,'role':'par'},connected_days=12)
        self.person('carla','Carla Compradora',classification={'fit':True,'role':'comprador'},connected_days=40)
        # Connected before connected_at was recorded: its last update stands in for the connection.
        self.person('dario','Darío Sin Clasificar',updated_days=3)
        self.person('eva','Eva Rol Vacío',classification={'fit':True,'role':''},connected_days=20)
        self.person('fabio','Fabio Rol Nulo',classification={'fit':False,'role':None},connected_days=30)
        # The queue was touched more recently than anybody: it would come first if it leaked into Conexiones.
        for stage in QUEUE:
            self.person(stage,f'Persona {stage}',stage=stage,classification={'fit':True,'role':'comprador'})

    def names(self,query=''):
        response=self.human.get(f'/api/v1/red/contacts?vista=conexiones{query}')
        self.assertEqual(response.status_code,200,response.content)
        return [c['display_name'] for c in response.json()['results']]

    def test_only_the_people_who_accepted_most_recent_connection_first(self):
        self.assertEqual(self.names(),['Ana Compradora','Darío Sin Clasificar','Bruno Par','Eva Rol Vacío','Fabio Rol Nulo','Carla Compradora'])
        # An old stage filter does not open the queue again.
        self.assertEqual(len(self.names('&stage=fit')),6)
        # Without the view, the PWA's funnel still lists everybody.
        self.assertEqual(self.human.get('/api/v1/red/contacts').json()['count'],6+len(QUEUE))
        self.assertEqual([c['display_name'] for c in self.human.get('/api/v1/red/contacts?stage=fit').json()['results']],['Persona fit'])

    def test_filters_by_role_without_role_and_by_name(self):
        self.assertEqual(self.names('&role=comprador'),['Ana Compradora','Carla Compradora'])
        self.assertEqual(self.names('&role=sin_etiqueta'),['Darío Sin Clasificar','Eva Rol Vacío','Fabio Rol Nulo'])
        self.assertEqual(self.names('&role=comprador&q=carla'),['Carla Compradora'])
        self.assertEqual(self.names('&role=lider'),[])

    def test_the_summary_counts_the_connections_by_role(self):
        self.assertEqual(self.human.get('/api/v1/red/summary').json()['connections'],
                         {'total':6,'roles':{'comprador':2,'par':1,'sin_etiqueta':3}})

    def test_links_to_the_old_funnel_land_on_conexiones_or_go(self):
        today=timezone.now().astimezone(operador.local_tz()).date()
        body=self.human.get(f'/api/v1/calendario?desde={today-timedelta(days=2)}&hasta={today}').json()
        self.assertEqual({e['link'] for d in body['days'] for e in d['events'] if e['kind']=='connection_fit'},{'/personas'})
        # The people about to be invited are the agents' queue: Personas no longer lists them, so the forecast has no link.
        Contact.objects.filter(stage='followed').update(followed_at=timezone.now()-timedelta(days=30))
        upcoming=self.human.get('/api/v1/notificaciones').json()['upcoming']
        self.assertEqual([u['link'] for u in upcoming if u['kind']=='invites_expected'],[None])
