"""Industry referents and «what worked for them» (docs/plan-referentes-industria.md). Invented people and companies;
fake connector, web and model: no external call. Runs in CI only."""
from datetime import datetime, timedelta
from decimal import Decimal
from io import StringIO
from unittest.mock import patch
import json
import os

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from team_backend import evidencia, modelos_crecimiento as mc, referentes as refs, referentes_industria as ind, research
from team_backend.connectors import FakeConnector
from team_backend.models import (AuditEvent, ConnectorAccount, Contact, CycleLedger, Job, ObservedPost, Referent,
                                 ReferentChange, ReferentControl, ReferentNotice, ReferentReview)

POST_TEXT = ('We shipped an MVP for a seed-stage founder in six weeks. Here is what we cut from scope and why it mattered.\n\n'
             '- No admin panel\n- One payment provider\n- Manual onboarding\n\nWhat would you cut first?')
COMMENTS = [
    {'id': 'c1', 'is_sender': False, 'author': {'id': 'ACoPersonaUno', 'display_name': 'Persona Uno'},
     'text': 'How do you price an MVP like this for a seed-stage founder? Fixed scope or a monthly team on retainer?'},
    {'id': 'c2', 'is_sender': False, 'author': {'id': 'ACoPersonaDos', 'display_name': 'Persona Dos'}, 'text': 'Great post!'},
    {'id': 'c3', 'is_sender': False, 'author': {'id': 'ACoPersonaTres', 'display_name': 'Persona Tres'},
     'text': 'I disagree: cutting onboarding hurts validation with the first users, it depends on the market you sell to.'},
    {'id': 'c4', 'is_sender': False, 'author': {'id': 'ACoAutora', 'display_name': 'Autora'}, 'text': 'Thanks!'},
    {'id': 'c5', 'is_sender': True, 'author': {'id': 'me', 'display_name': 'Cuenta conectada'}, 'text': 'Own comment'},
]
SLUG = 'lia-constructora-test'
URL = f'https://www.linkedin.com/in/{SLUG}/'
OWN = {'id': f'linkedin:{SLUG}', 'url': URL, 'title': 'Perfil', 'retrieved_at': '2026-11-14T00:00:00Z', 'kind': 'web', 'truncated': False,
       'quoted_text': 'Lia Constructora · Founder · We build MVPs for US startups · Austin, Texas'}
WEB = {'id': 'web-1', 'url': 'https://example.org/estudio-ejemplo', 'title': 'Estudio Ejemplo', 'retrieved_at': '2026-11-14T00:00:00Z',
       'kind': 'web', 'truncated': False,
       'quoted_text': 'Estudio Ejemplo (Lia Constructora) shipped 120 products; a team of 40 engineers in Austin, Texas.'}
CLAIMS = {'company': 'Estudio Ejemplo', 'services': ['producto', 'ia_aplicada'], 'service_sources': [OWN['id']],
          'authority': [{'kind': 'casos', 'claim': 'Casos publicados', 'sources': ['web-1']},
                        {'kind': 'equipo', 'claim': 'Equipo propio', 'sources': ['web-1']}],
          'us_market': False, 'us_sources': []}


def windows(text, size=20):
    plain = ' '.join(text.split())
    return {plain[i:i + size] for i in range(len(plain) - size + 1)}


def measured(**over):
    c = {'slug': SLUG, 'display_name': 'Lia Constructora', 'profile_url': URL, 'followers': 25000, 'median_interactions': 90,
         'sample': 7, 'posts_read': 8, 'posts_30d': 8, 'days_since_last': 1, 'location': 'Austin, Texas', 'region': 'us',
         'found_by': ['producto'], 'audience': {'commenters': 6, 'classified': 5, 'fit': 3, 'us': 2, 'roles': {}, 'fit_share': 0.6},
         'source': OWN}
    c.update(over)
    return c


class OutlierAndShapeTests(SimpleTestCase):
    def test_default_thresholds_are_the_documented_ones(self):
        t, i = mc.thresholds(), ind.thresholds()
        self.assertEqual((t['min_sample'], t['min_lift'], t['min_z'], t['min_interactions'], t['recent_days']), (6, 2.0, 3.0, 20, 45))
        self.assertEqual((i['min_followers'], i['min_median'], i['min_posts_30d'], i['max_days_since_post'], i['min_authority']),
                         (10000, 50, 4, 14, 2))
        self.assertFalse(i['audience_required'])

    def test_outlier_needs_its_own_sample_and_handles_ties_and_zero_medians(self):
        self.assertEqual(mc.judge(500, [10] * 5)['reason'], 'muestra_insuficiente')
        tie = mc.judge(500, [10] * 6)
        self.assertTrue(tie['flag'])
        self.assertIsNone(tie['z'])  # MAD 0: only the ratio decides
        self.assertEqual(mc.judge(25, [15] * 6)['reason'], 'poca_ventaja')
        self.assertTrue(mc.judge(25, [0] * 6)['flag'])  # median 0: the absolute floor decides
        self.assertEqual(mc.judge(15, [0] * 6)['reason'], 'pocas_interacciones')
        self.assertTrue(mc.judge(140, [40, 50, 60, 70, 80, 90])['flag'])
        self.assertEqual(mc.judge(130, [40, 50, 60, 70, 80, 90])['reason'], 'dentro_de_lo_normal')
        self.assertEqual(mc.judge(None, [10] * 6)['reason'], 'sin_contadores')

    def test_structure_keeps_the_shape_and_no_sentence_of_the_post(self):
        shape = mc.structure(POST_TEXT)
        dumped = json.dumps(shape, ensure_ascii=False)
        self.assertFalse([w for w in windows(POST_TEXT) if w in dumped])
        self.assertEqual((shape['form'], shape['hook']['type'], shape['closing'], shape['language']),
                         ('lista', 'primera_persona', 'pregunta', 'en'))
        self.assertEqual(shape['outline'], ['gancho', 'lista', 'cierre_pregunta'])
        self.assertEqual((shape['angle'], shape['pillar'], shape['list_items']), ('experiencia_propia', 'business_to_product', 3))
        self.assertEqual(shape['format'], 'desconocido')

    def test_comment_summary_counts_without_names_ids_or_sentences(self):
        summary = mc.comment_summary(COMMENTS, 'ACoAutora')
        self.assertEqual({k: summary[k] for k in ('read', 'substantive', 'questions', 'applause', 'objections', 'author_replies')},
                         {'read': 3, 'substantive': 2, 'questions': 1, 'applause': 1, 'objections': 1, 'author_replies': 1})
        self.assertEqual(set(summary['question_themes']), {'costo', 'mvp_alcance', 'financiacion'})
        self.assertEqual(summary['objection_themes'], {'validacion': 1})
        dumped = json.dumps(summary)
        for leak in ('Persona', 'ACo', 'disagree', 'retainer'):
            self.assertNotIn(leak, dumped)


class CriteriaTests(SimpleTestCase):
    sources = {OWN['id']: OWN, 'web-1': WEB}

    def test_a_candidate_passes_only_with_verified_claims(self):
        result = ind.evaluate(measured(), CLAIMS, self.sources)
        self.assertTrue(result['passed'])
        self.assertEqual(result['services'], ['producto'])  # IA claimed, no source says it: dropped
        self.assertEqual({c['key']: c['status'] for c in result['criteria']}, dict.fromkeys(ind.CRITERIA, 'cumple'))

    def test_unknown_is_never_met(self):
        unknown = ind.evaluate(measured(followers=None), CLAIMS, self.sources)
        self.assertFalse(unknown['passed'])
        self.assertIn('Es grande: sin medir (no cuenta como cumplido)', unknown['reasons'])
        audience = ind.evaluate(measured(audience={'commenters': 9, 'classified': 2, 'fit': 1, 'fit_share': None}), CLAIMS, self.sources)
        row = next(c for c in audience['criteria'] if c['key'] == 'audiencia')
        self.assertEqual(row['status'], 'sin_medir')
        self.assertIn('no cuenta como cumplido', row['status_label'])
        self.assertTrue(audience['passed'])  # not required by default, and labeled as unmeasured
        with patch.dict(os.environ, {'REFERENTES_INDUSTRIA_AUDIENCIA_OBLIGATORIA': 'true'}):
            self.assertFalse(ind.evaluate(measured(audience={'classified': 2, 'fit_share': None}), CLAIMS, self.sources)['passed'])

    def test_an_audience_measured_outside_the_barrio_blocks(self):
        result = ind.evaluate(measured(audience={'commenters': 20, 'classified': 10, 'fit': 1, 'fit_share': 0.1}), CLAIMS, self.sources)
        self.assertFalse(result['passed'])
        self.assertIn('Su audiencia es el barrio: no cumple', result['reasons'])

    def test_claims_need_a_source_that_names_the_candidate(self):
        other = dict(WEB, id='web-2', quoted_text='Another studio shipped 300 products with a team of 90 engineers.')
        claims = dict(CLAIMS, company='', authority=[{'kind': 'casos', 'claim': 'x', 'sources': ['web-2']},
                                                     {'kind': 'equipo', 'claim': 'y', 'sources': ['web-2']}])
        result = ind.evaluate(measured(), claims, dict(self.sources, **{'web-2': other}))
        self.assertFalse(result['passed'])
        self.assertEqual(next(c for c in result['criteria'] if c['key'] == 'autoridad')['status'], 'no_cumple')
        self.assertFalse(ind.evaluate(measured(), dict(CLAIMS, services=['liderazgo_tecnico']), self.sources)['passed'])

    def test_activity_and_us_market(self):
        self.assertFalse(ind.evaluate(measured(days_since_last=20), CLAIMS, self.sources)['passed'])
        abroad = measured(location='Medellín, Colombia', region='latam')
        self.assertFalse(ind.evaluate(abroad, CLAIMS, self.sources)['passed'])
        sells = dict(WEB, id='web-3', quoted_text='Estudio Ejemplo builds products for U.S. startups.')
        claims = dict(CLAIMS, us_market=True, us_sources=['web-3'])
        self.assertTrue(ind.evaluate(abroad, claims, dict(self.sources, **{'web-3': sells}))['passed'])

    @override_settings(WEB_RESEARCH_MODEL='claude-sonnet-5-5', WEB_SEARCH_MAX_USES=2, WEB_FETCH_MAX_USES=2,
                       WEB_FETCH_MAX_CONTENT_TOKENS=4000, WEB_SEARCH_RESERVED_TOKENS=25000, WEB_RESEARCH_MAX_TOKENS=4000,
                       WEB_SEARCH_USD_PER_REQUEST='0.01')
    def test_cost_estimate_is_the_worst_case_reservation(self):
        est = ind.estimate(6, 4)
        self.assertEqual((est['web_call_usd'], est['selection_usd'], est['web_calls']), (Decimal('0.82'), Decimal('0.27'), 2))
        self.assertEqual(est['usd_max'], Decimal('1.91'))
        self.assertEqual(est['reads'], {'search': 5, 'profile': 6, 'content': 12})
        self.assertEqual(ind.estimate(9, 4)['usd_max'], Decimal('2.73'))


class IndustryMixin:
    def set_up_industry(self):
        self.now = timezone.now()
        self.user = get_user_model().objects.create_user('gustavo', is_superuser=True)
        self.account = ConnectorAccount.objects.create(provider='fake', external_account_id='industria-fake', label='Synthetic')
        self.main = [Referent.objects.create(account=self.account, public_identifier=f'main-{n}', display_name=f'Main {n}',
                                             reason='Synthetic main', protected=True) for n in range(5)]
        ReferentControl.objects.create(account=self.account, initialized=True, initial_main=[str(r.pk) for r in self.main])
        for target in ('httpx.Client.send', 'knowledge.providers.claude', 'team_backend.alerts.notify'):
            guard = patch(target, side_effect=AssertionError('No external calls'))
            guard.start()
            self.addCleanup(guard.stop)
        budget = patch('knowledge.presupuesto.left', return_value=Decimal('50'))
        budget.start()
        self.addCleanup(budget.stop)

    def referent(self, slug, kind='industria'):
        return Referent.objects.create(account=self.account, public_identifier=slug, display_name=slug, reason='Synthetic',
                                       kind=kind, provider_user_id='ACo' + slug)

    def post(self, referent, days, reactions, comments=0, text='Synthetic baseline post', n=[0]):
        n[0] += 1
        return ObservedPost.objects.create(account=self.account, referent=referent, provider_post_id=f'activity:{n[0]}',
            share_url=f'https://www.linkedin.com/feed/update/urn:li:activity:{n[0]}', author_name=referent.display_name,
            author_provider_id=referent.provider_user_id, text=text, posted_at=self.now - timedelta(days=days),
            reactions_count=reactions, comments_count=comments)


class GrowthModelTests(IndustryMixin, TestCase):
    def setUp(self):
        self.set_up_industry()
        self.lia = self.referent(SLUG)
        self.baseline = [self.post(self.lia, d, 10) for d in range(10, 16)]
        self.viral = self.post(self.lia, 3, 280, 20, POST_TEXT)
        self.hiring = self.post(self.lia, 4, 300, 0, "We're hiring senior engineers in Austin. Apply now.")
        self.stale = self.post(self.lia, 60, 500, 0, 'An old post that once did well.')

    def classify(self, ids, fit):
        for uid, ok in zip(ids, fit):
            Contact.objects.create(account=self.account, provider_user_id=uid, public_identifier=uid.lower(),
                source=Contact.Source.COMMENTER, location='Austin, Texas', classification={'fit': ok, 'role': 'comprador'})

    def test_one_viral_post_does_not_raise_its_own_bar_and_stale_or_hiring_posts_are_not_models(self):
        flagged = mc.refresh(self.account, now=self.now)
        self.assertEqual({p.pk for p in flagged}, {self.viral.pk, self.hiring.pk})
        self.viral.refresh_from_db()
        self.assertEqual((self.viral.outlier['median'], self.viral.outlier['lift']), (10, 30.0))
        self.baseline[0].refresh_from_db()
        self.assertFalse(self.baseline[0].outlier['flag'])
        self.assertEqual(self.baseline[0].outlier['sample'], 8)
        self.stale.refresh_from_db()
        self.assertEqual(self.stale.outlier, {})
        models = mc.growth_models(self.account, now=self.now)
        self.assertEqual([m['post_id'] for m in models], [str(self.viral.pk)])
        self.assertEqual(mc.growth_models(self.account, now=self.now, kinds=('nicho',)), [])

    def test_growth_model_carries_shape_audience_and_no_text(self):
        mc.refresh(self.account, now=self.now)
        people = ['ACoPersonaUno', 'ACoPersonaDos', 'ACoPersonaTres', 'ACoPersonaCuatro', 'ACoPersonaCinco']
        page = COMMENTS[:3] + [{'id': f'x{n}', 'is_sender': False, 'text': 'Useful.', 'author': {'id': uid}} for n, uid in enumerate(people[3:])]
        evidencia.referent_comments(self.viral, page, self.now)
        mc.store_audience(self.viral, page, self.now)
        self.classify(people, [True, True, True, True, False])
        model = mc.growth_models(self.account, now=self.now)[0]
        self.assertEqual(set(model), {'post_id', 'provider_post_id', 'url', 'posted_at', 'referent', 'performance', 'structure',
                                      'audience', 'fit_as_model', 'relevance', 'rule', 'use'})
        self.assertEqual(model['referent']['kind'], 'industria')
        self.assertEqual(model['audience']['barrio'], {'commenters': 5, 'classified': 5, 'fit': 4, 'us': 4,
                                                       'roles': {'comprador': 4}, 'fit_share': 0.8})
        self.assertEqual(model['relevance'], 26.0)  # lift 30 capped at 20, x (0.5 + 0.8)
        self.assertEqual(model['audience']['questions'][0]['theme'], 'costo')
        self.assertIn('Nunca copiar', model['use'])
        dumped = json.dumps(model, ensure_ascii=False)
        self.assertFalse([w for w in windows(POST_TEXT) if w in dumped])
        for leak in ('Persona Uno', 'retainer'):
            self.assertNotIn(leak, dumped)
        questions = mc.audience_questions(self.account, now=self.now)
        self.assertIn({'theme': 'costo', 'label': mc.THEMES['costo'][0], 'kind': 'pregunta', 'count': 1, 'posts': 1, 'referents': 1}, questions)
        self.assertIn('validacion', {q['theme'] for q in questions if q['kind'] == 'objecion'})

    def test_after_observe_reads_comments_of_new_industry_outliers_within_its_daily_room(self):
        calls = []

        class Reader:
            def list_comments(self, post_id, limit=50):
                calls.append(post_id)
                return COMMENTS

        summary = mc.after_observe(self.account, Reader(), [self.lia.pk], now=self.now)
        self.assertEqual((summary['outliers'], summary['audience_read']), (2, 2))
        self.viral.refresh_from_db()
        self.assertEqual(self.viral.audience['source'], 'modelos')
        self.assertEqual(AuditEvent.objects.filter(action=mc.READ_EVENT).count(), 2)
        self.assertEqual(mc.after_observe(self.account, Reader(), [self.lia.pk], now=self.now)['audience_read'], 0)
        self.assertEqual(len(calls), 2)
        niche = self.referent('voz-nicho-test', kind='nicho')
        for d in range(10, 16):
            self.post(niche, d, 10)
        self.post(niche, 2, 400)
        with patch.dict(os.environ, {'MODELOS_LECTURAS_DIA': '10'}):
            self.assertEqual(mc.after_observe(self.account, Reader(), [niche.pk], now=self.now)['audience_read'], 0)

    def test_an_industry_referent_without_a_sample_reads_twenty_posts_at_once(self):
        fresh = self.referent('nueva-voz-test')
        self.assertEqual(mc.read_limit(fresh, 5), 20)
        self.assertEqual(mc.read_limit(self.lia, 5), 5)
        self.assertEqual(mc.read_limit(self.referent('nicho-test', kind='nicho'), 5), 5)


@override_settings(REFERENTS_GUSTAVO_USERNAME='gustavo')
class IndustryWorkflowTests(IndustryMixin, TestCase):
    def setUp(self):
        self.set_up_industry()

    def review(self, kind='industria', state='ready', month=None):
        month = month or refs.month_start(self.now)
        return ReferentReview.objects.create(account=self.account, month=month, kind=kind, state=state,
                                             deadline=self.now + timedelta(days=14))

    def change(self, review, slug=SLUG, state='pending', history=()):
        incoming = {'identifier': slug, 'display_name': 'Lia Constructora', 'profile_url': f'https://www.linkedin.com/in/{slug}/',
                    'niche': 'Estudio de producto', 'audience': 'Founders', 'contribution': 'Entrega', 'top_voice': False,
                    'sources': [OWN['id']], 'industria': {'slug': slug, 'passed': True, 'criteria': []}}
        return ReferentChange.objects.create(review=review, ordinal=review.changes.count(), state=state, history=list(history),
            proposal={'kind': 'add', 'incoming': incoming, 'reason': 'Audiencia de founders en EE. UU.', 'evidence': [OWN['id']]})

    def test_an_evaluation_cannot_travel_to_another_profile(self):
        proposal = {'kind': 'add', 'reason': 'x', 'evidence': ['s'], 'incoming': {
            'identifier': 'otra-persona-test', 'display_name': 'Otra', 'profile_url': 'https://www.linkedin.com/in/otra-persona-test/',
            'niche': 'n', 'audience': 'a', 'contribution': 'c', 'top_voice': False, 'sources': ['s'], 'industria': {'slug': SLUG}}}
        with self.assertRaisesRegex(ValueError, 'otro perfil'):
            refs.validate_proposal(self.account, proposal)

    def test_rejections_referents_and_measured_failures_are_not_proposed_again(self):
        monthly = self.review(kind='mensual')
        self.change(monthly, 'cora-rechazada-test', state='rejected', history=[{'decision': 'reject', 'note': 'No vende software'}])
        old = self.review(month=refs.month_start(self.now - timedelta(days=40)))
        old.dossier = {'industria': {'descartados': [
            {'slug': 'medido-test', 'at': self.now.isoformat(), 'reasons': ['Publica seguido: no cumple'], 'remember': True},
            {'slug': 'sin-medir-test', 'at': self.now.isoformat(), 'reasons': ['Es grande: sin medir'], 'remember': False}]}}
        old.save()
        skip = ind.excluded(self.account, self.now)
        self.assertEqual(skip['cora-rechazada-test'], 'Gustavo lo rechazó: No vende software')
        self.assertIn('main-0', skip)
        self.assertIn('medido-test', skip)
        self.assertNotIn('sin-medir-test', skip)

    def test_nothing_is_enqueued_without_confirmation_and_the_guard_blocks_a_second_search(self):
        job, report = ind.enqueue(self.user, self.account)
        self.assertIsNone(job)
        self.assertTrue(report['ok'], report['issues'])
        self.assertFalse(Job.objects.exists())
        out = StringIO()
        call_command('operador', '--usuario', 'gustavo', 'referentes-industria', '--cuenta', str(self.account.pk), stdout=out)
        self.assertIn('Costo máximo', out.getvalue())
        self.assertIn('No se encoló nada', out.getvalue())
        self.assertFalse(Job.objects.exists())
        job, report = ind.enqueue(self.user, self.account, confirm=True)
        self.assertEqual((job.kind, job.params['industria'], job.params['tope_usd']), ('review_referents', True, '3'))
        self.review()
        _, report = ind.enqueue(self.user, self.account, confirm=True)
        self.assertFalse(report['ok'])
        self.assertIn('Ya hubo una búsqueda de referentes de industria este mes', ' '.join(report['issues']))
        _, small = ind.enqueue(self.user, self.account, tope_usd=Decimal('0.5'), confirm=True)
        self.assertTrue(any('no alcanza' in issue for issue in small['issues']))

    def test_an_industry_batch_is_never_applied_by_silence_nor_reminded_as_if_it_were(self):
        review = self.review()
        self.change(review)
        day4 = datetime.combine(review.month.replace(day=4), datetime.min.time(), refs.TZ).replace(hour=10)
        review.deadline = day4 + timedelta(days=14)
        review.save()
        with patch.dict(os.environ, {'OPERATOR_WINDOW': '00:00-01:00'}):
            refs.tick(self.user, day4)
        review.refresh_from_db()
        self.assertEqual(review.state, 'late')
        self.assertEqual(ReferentNotice.objects.get(review=review, event='day1').payload['title'], 'Referentes de industria por decidir')
        self.assertFalse(ReferentNotice.objects.filter(review=review, event='day4').exists())
        refs.close(review, review.deadline + timedelta(seconds=1))
        item = review.changes.get()
        self.assertEqual(item.state, 'conflict')
        self.assertIn('decisión explícita', item.conflict)
        self.assertFalse(Referent.objects.filter(public_identifier=SLUG).exists())

    def test_the_monthly_calendar_never_starts_an_industry_search(self):
        first = datetime(2026, 12, 1, 9, tzinfo=refs.TZ)
        with patch.dict(os.environ, {'OPERATOR_WINDOW': '00:00-01:00'}):
            refs.tick(self.user, first)
        jobs = list(Job.objects.filter(kind='review_referents'))
        self.assertTrue(jobs)
        self.assertFalse([j for j in jobs if j.params.get('industria')])

    def test_approval_makes_an_industry_referent_and_a_rejection_note_is_kept(self):
        review = self.review()
        approve, reject = self.change(review), self.change(review, 'otra-voz-test')
        refs.publish(review, self.now)
        refs.decide(self.user, approve.pk, approve.version, 'approve')
        self.assertEqual(Referent.objects.get(public_identifier=SLUG).kind, Referent.Kind.INDUSTRIA)
        refs.decide(self.user, reject.pk, reject.version, 'reject', note='Vende cursos, no software')
        self.assertEqual(ind.excluded(self.account, self.now)['otra-voz-test'], 'Gustavo lo rechazó: Vende cursos, no software')


@override_settings(REFERENTS_GUSTAVO_USERNAME='gustavo')
class IndustrySearchRunTests(IndustryMixin, TestCase):
    def setUp(self):
        self.set_up_industry()
        env = patch.dict(os.environ, {'OPERATOR_ALLOW_FAKE': 'true', 'LIVE_PROVIDERS': 'false', 'LIVE_LINKEDIN': 'false'})
        env.start()
        self.addCleanup(env.stop)
        FakeConnector.reset()
        self.addCleanup(FakeConnector.reset)
        self.conn = FakeConnector(self.account.external_account_id)

    def candidate(self, slug, name, followers, days, scores):
        user = self.conn.seed_person(slug, name, headline='Founder · Estudio de producto', search='custom software development',
                                     location='Austin, Texas', signals={'followers': followers, 'bio': 'We build MVPs for US startups.'})
        pids = []
        for n, (day, score) in enumerate(zip(days, scores)):
            pid = f'activity:{slug}-{n}'
            self.conn.state['posts'][pid] = {'id': pid, 'share_url': 'https://www.linkedin.com/feed/update/urn:li:' + pid,
                'text': f'Synthetic post text {n} written by {slug}', 'created_at': (self.now - timedelta(days=day)).isoformat(),
                'author': user, 'comments_counter': 0, 'reactions_counter': [{'reaction': '👍', 'count': score}],
                'reposts_counter': 0, 'user_reacted': False, 'is_repost': False}
            self.conn.state['comments'][pid] = []
            pids.append(pid)
        return pids

    def test_search_measures_on_linkedin_verifies_claims_and_proposes_only_who_passes(self):
        top = self.candidate(SLUG, 'Lia Constructora', 25000, [1, 3, 5, 8, 12, 20, 26, 29], [400] + [90] * 7)[0]
        self.candidate('beto-inactivo-test', 'Beto Inactivo', 15000, [40, 45, 50, 55, 60, 65], [100] * 6)
        self.conn.seed_person('cora-rechazada-test', 'Cora Rechazada', search='custom software development',
                              location='Boston, Massachusetts', signals={'followers': 30000})
        monthly = ReferentReview.objects.create(account=self.account, month=refs.month_start(self.now), state='ready',
                                                deadline=self.now + timedelta(days=5))
        ReferentChange.objects.create(review=monthly, ordinal=0, state='rejected', history=[{'decision': 'reject', 'note': 'No'}],
            proposal={'kind': 'add', 'reason': 'x', 'evidence': ['s'], 'incoming': {'identifier': 'cora-rechazada-test'}})
        people = [f'comentarista-{n}-test' for n in range(6)]
        for n, slug in enumerate(people):
            self.conn.seed_person(slug, f'Comentarista {n}', comment_on=top, comment='A long and specific question about scope ' * 3)
        for slug, fit in zip(people, [True, True, True, False, False]):
            Contact.objects.create(account=self.account, provider_user_id='ACo' + slug, public_identifier=slug,
                source=Contact.Source.COMMENTER, location='Austin, Texas', classification={'fit': fit, 'role': 'comprador'})
        ctx = {'positioning': {'version': 'v1'}, 'orientation': {'version': 'o1'}, 'memory': {'version': 'm1'},
               'grounding': {'course_status': 'disponible'}, 'course': 'Synthetic course', 'experiments': [],
               'referents': [refs.snapshot(r) for r in self.main]}
        questions = []

        def web(request):
            questions.append(request.public_question)
            source = research.Source('web-1', WEB['url'], WEB['title'], WEB['quoted_text'], self.now.isoformat())
            return research.ResearchResult(request.public_question, 'complete', self.now.isoformat(),
                                           (research.Finding('Synthetic finding', ('web-1',)),), (source,))

        def select(request):
            candidates = request['context']['industria']['candidatos']
            self.assertEqual([c['slug'] for c in candidates], [SLUG])
            own = candidates[0]['fuente_linkedin']
            incoming = {'identifier': SLUG, 'display_name': 'Lia Constructora', 'profile_url': candidates[0]['profile_url'],
                        'niche': 'Estudio de producto', 'audience': 'Founders de EE. UU.', 'contribution': 'Criterio de entrega',
                        'top_voice': False, 'sources': [own], 'industria': dict(CLAIMS, service_sources=[own])}
            return {'summary': 'Synthetic dossier', 'continuity': [],
                    'changes': [{'kind': 'add', 'incoming': incoming, 'reason': 'Su audiencia es de founders en EE. UU.', 'evidence': [own]}]}

        month = refs.month_start(self.now)
        job = Job.objects.create(owner=self.user, kind='review_referents', agent='operador', task='industria', request_hash='i',
                                 params={'account': str(self.account.pk), 'month': month.isoformat(), 'industria': True,
                                         'tope_usd': '3', 'candidatos': 6, 'busquedas': 4})
        from team_backend import referentes_research
        with patch.object(referentes_research, 'context', return_value=ctx), patch.object(ind, 'select', side_effect=select) as chosen, \
             patch('team_backend.research.research', side_effect=web) as tool:
            review = referentes_research.run(job)
            referentes_research.run(job)  # a retry pays nothing again
        self.assertEqual((tool.call_count, chosen.call_count), (1, 1))
        self.assertIn('Lia Constructora', questions[0])
        review.refresh_from_db()
        self.assertEqual((review.kind, review.state), ('industria', 'late'))
        change = review.changes.get()
        evaluation = change.proposal['incoming']['industria']
        self.assertTrue(evaluation['passed'])
        self.assertEqual(evaluation['services'], ['producto'])
        self.assertEqual({c['key']: c['status'] for c in evaluation['criteria']}, dict.fromkeys(ind.CRITERIA, 'cumple'))
        dropped = review.dossier['industria']['descartados']
        self.assertEqual([(d['slug'], d['remember']) for d in dropped], [('beto-inactivo-test', True)])
        self.assertNotIn('cora-rechazada-test', json.dumps(review.dossier['industria']['evaluated']))
        dumped = json.dumps([review.dossier, change.proposal], ensure_ascii=False)
        self.assertNotIn('Synthetic post text', dumped)
        self.assertNotIn('Comentarista', dumped)
        self.assertFalse(ObservedPost.objects.exists())
        self.assertEqual(CycleLedger.objects.get(key=str(review.pk)).calls, 2)
        self.assertEqual(ReferentNotice.objects.get(review=review, event='day1').payload['title'], 'Referentes de industria por decidir')
        self.assertFalse(Referent.objects.filter(public_identifier=SLUG).exists())
