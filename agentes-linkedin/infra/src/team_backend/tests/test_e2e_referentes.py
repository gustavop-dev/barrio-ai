"""End to end, with the fake LinkedIn connector and fake paid providers (no network, no USD):

1. The industry search: company and profile seeds from the command → headline prefilter → measured on LinkedIn →
   criteria → proposal in the Bandeja → Gustavo approves it from his card → an industry referent.
2. The analysis of their posts: observed by operador.observe (shares and media kept) → taken apart → each counter
   against its author's median → durable structures and current topics → the editorial's two signals → the endpoint."""
from datetime import timedelta
from io import StringIO
from unittest.mock import patch
import json
import os

from django.core.management import call_command
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from team_backend import analisis_referentes as an, estrategia, operador, referentes_industria as ind
from team_backend.connectors import FakeConnector
from team_backend.models import Job, ObservedPost, Referent, ReferentReview
from team_backend.tests import test_analisis_referentes as tar, test_referentes_industria as tri



def helpers(*names):
    """IndustrySearchRunTests' helpers, without binding that TestCase here (the loader would run its tests again)."""
    return [getattr(tri.IndustrySearchRunTests, name) for name in names]


@override_settings(REFERENTS_GUSTAVO_USERNAME='gustavo')
class IndustrySearchEndToEndTests(tri.IndustryMixin, TestCase):
    setUp, candidate, ctx, web, propose, run_job = helpers('setUp', 'candidate', 'ctx', 'web', 'propose', 'run_job')

    def test_seeds_prefilter_measurement_criteria_bandeja_and_gustavos_approval_make_an_industry_referent(self):
        days, scores = helpers('DAYS', 'SCORES')
        self.candidate('ivan-imagine-test', 'Ivan Imagine', 30000, days, scores, headline='Co-founder at Imagine Apps',
                       search='"Imagine Apps" founder', location='Austin, Texas', bio='We build MVPs for US startups.')
        self.candidate('semilla-chica-test', 'Semilla Chica', 4000, days, scores, headline='Founder | Product studio', search=None)
        self.conn.seed_person('coach-busqueda-test', 'Coach Busqueda', headline='Executive coach for founders and CEOs',
                              search=ind.QUERIES[0][1], location='New York, New York', signals={'followers': 50000})
        out = StringIO()
        call_command('operador', '--usuario', 'gustavo', 'referentes-industria', '--cuenta', str(self.account.pk),
                     '--busquedas', '1', '--empresas', 'Imagine Apps', '--perfiles', 'semilla-chica-test', '--confirmar', stdout=out)
        self.assertIn('Búsqueda de referentes de industria en cola', out.getvalue())
        job = Job.objects.get(kind='review_referents')
        self.assertEqual((job.params['empresas'], job.params['perfiles']), (['Imagine Apps'], ['semilla-chica-test']))
        review = self.run_job(job, self.propose('ivan-imagine-test', 'Ivan Imagine'))

        data = ReferentReview.objects.get(pk=review.pk).dossier['industria']
        steps = {d['slug']: (d['step'], d['reads']) for d in data['descartados']}
        self.assertEqual(steps['coach-busqueda-test'], ('prefiltro', 'ninguna'))  # out by its headline, no profile read
        self.assertEqual(steps['semilla-chica-test'][0], 'tamano')  # a seed meets the same criteria
        self.assertEqual(data['semillas'], {'empresas': ['Imagine Apps'], 'perfiles': ['semilla-chica-test']})
        self.assertEqual(data['embudo']['propuestos'], 1)

        gustavo = APIClient()
        gustavo.force_login(self.user)
        turn = gustavo.get('/api/v1/tu-turno')
        self.assertEqual(turn.status_code, 200)
        card = next(c for c in turn.json()['items'] if c['id'].startswith('referent_change:'))
        self.assertEqual(card['title'], 'Alta de industria: Ivan Imagine')
        self.assertIn('Requiere decisión explícita', card['body'])
        approve = next(a for a in card['actions'] if a.get('primary'))
        self.assertEqual(approve['label'], 'Aprobar alta')
        self.assertFalse(Referent.objects.filter(public_identifier='ivan-imagine-test').exists())
        answer = gustavo.post(approve['endpoint'], approve['body'], format='json')
        self.assertEqual((answer.status_code, answer.json()['state']), (200, 'approved'))
        referent = Referent.objects.get(public_identifier='ivan-imagine-test')
        self.assertEqual((referent.kind, referent.active, referent.protected), (Referent.Kind.INDUSTRIA, True, False))
        self.assertFalse(any(c['id'] == card['id'] for c in gustavo.get('/api/v1/tu-turno').json()['items']))


@override_settings(REFERENTS_GUSTAVO_USERNAME='gustavo')
class AnalysisEndToEndTests(tri.IndustryMixin, TestCase):
    def setUp(self):
        self.set_up_industry()
        env = patch.dict(os.environ, {'OPERATOR_ALLOW_FAKE': 'true', 'LIVE_PROVIDERS': 'false', 'READ_WINDOW': '',
                                      'OPERATOR_WINDOW': '00:00-24:00', 'REFERENTES_ANALISIS': 'true', 'MODELOS_LECTURAS_DIA': '0'})
        env.start()
        self.addCleanup(env.stop)
        FakeConnector.reset()
        self.addCleanup(FakeConnector.reset)
        self.conn = FakeConnector(self.account.external_account_id)
        self.n = 0

    def author(self, slug):
        user = self.conn.seed_person(slug, slug.title(), headline='Founder · Software agency')
        return user, self.referent(slug)

    def publish(self, user, days, reactions, comments, text, reposts=1, media=''):
        self.n += 1
        pid = f'activity:e2e-{self.n}'
        self.conn.state['posts'][pid] = {'id': pid, 'share_url': 'https://www.linkedin.com/feed/update/urn:li:' + pid, 'text': text,
                                         'created_at': (self.now - timedelta(days=days)).isoformat(), 'author': user,
                                         'comments_counter': comments, 'reactions_counter': [{'reaction': '👍', 'count': reactions}],
                                         'reposts_counter': reposts, 'user_reacted': False, 'is_repost': False, 'media': media}
        self.conn.state['comments'][pid] = []
        return pid

    def test_observed_posts_are_taken_apart_compared_aggregated_signalled_to_the_editorial_and_served(self):
        (ana, _), (beto, _) = self.author('ana-e2e-test'), self.author('beto-e2e-test')
        for d in range(20, 60, 5):
            self.publish(ana, d, 40, 5, tar.BASE)
            self.publish(beto, d + 1, 25, 5, tar.BASE)
        top = self.publish(ana, 3, 300, 40, tar.LIST.format(n=12), reposts=12, media='documento')
        self.publish(ana, 17, 300, 40, tar.LIST.format(n=30))
        self.publish(beto, 10, 200, 20, tar.LIST.format(n=7))
        self.publish(beto, 2, 400, 60, tar.NEWS, media='imagen')
        self.publish(ana, 2, 40, 5, tar.DEVDAY)

        summary = operador.observe(self.user, self.account, limit=20)
        self.assertEqual((summary['referents'], summary['new_posts']), (2, 21))
        stored = ObservedPost.objects.get(provider_post_id=top)
        self.assertEqual((stored.reposts_count, stored.media), (12, 'documento'))

        gustavo = APIClient()
        gustavo.force_login(self.user)
        data = gustavo.get('/api/v1/referentes/analisis', {'account': str(self.account.pk)}).json()
        self.assertIs(data['activo'], True)
        best = next(s for s in data['destacados'] if s['post_id'] == str(stored.pk))
        self.assertEqual(best['metricas']['reacciones'], {'valor': 300, 'mediana_autor': 40, 'veces': 7.5, 'muestra': 10})
        self.assertEqual(best['metricas']['compartidos']['veces'], 12.0)
        self.assertEqual(best['partes']['recurso_visual']['tipo'], 'documento')
        self.assertEqual((best['firma'], best['veredicto']), (tar.DURABLE, 'funciono'))
        durable = next(s for s in data['estructuras_sostenidas'] if s['firma'] == tar.DURABLE)
        self.assertEqual((durable['estado'], durable['autores'], durable['semanas']), ('sostenida', 2, 3))
        self.assertIn('tendencia:nombre:devday', {t['id'] for t in data['temas_en_tendencia']})
        self.assertEqual(tar.leaks(data), [])

        signals = estrategia.audience_signals()
        self.assertEqual(signals['estructura_sostenida'][0]['id'], f'estructura:{tar.DURABLE}')
        self.assertIn('tendencia:nombre:devday', {t['id'] for t in signals['tema_en_tendencia']})
        self.assertEqual(tar.leaks([signals['estructura_sostenida'], signals['tema_en_tendencia']]), [])
        self.assertEqual(json.loads(json.dumps(signals['estructura_sostenida'], ensure_ascii=False))[0]['uso'], an.USE)
        with patch.dict(os.environ, {'REFERENTES_ANALISIS': 'false'}):
            self.assertNotIn('estructura_sostenida', estrategia.audience_signals())
