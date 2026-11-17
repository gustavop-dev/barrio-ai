"""Industry referents and «what worked for them» (docs/plan-referentes-industria.md). Invented people and companies;
fake connector, web and model: no external call. Runs in CI only."""
from datetime import datetime, timedelta
from decimal import Decimal
from io import StringIO
from unittest.mock import patch
import json
import os
import uuid

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from team_backend import evidencia, modelos_crecimiento as mc, operador, referentes as refs, referentes_industria as ind, research
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
PRICES = dict(WEB_RESEARCH_MODEL='claude-sonnet-5-5', WEB_SEARCH_MAX_USES=2, WEB_FETCH_MAX_USES=2,
              WEB_FETCH_MAX_CONTENT_TOKENS=4000, WEB_SEARCH_RESERVED_TOKENS=25000, WEB_RESEARCH_MAX_TOKENS=4000,
              WEB_SEARCH_USD_PER_REQUEST='0.01')
AGENCY = 'Founder & CEO at Northwind Labs | Software development agency for US startups'


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

    @override_settings(**PRICES)
    def test_cost_estimate_is_the_worst_case_reservation(self):
        est = ind.estimate(6, 4)
        self.assertEqual((est['web_call_usd'], est['selection_usd'], est['web_calls']), (Decimal('0.82'), Decimal('0.27'), 2))
        self.assertEqual(est['usd_max'], Decimal('1.91'))
        # Two profile reads per candidate measured: a read may show a seller of something else or a small account.
        self.assertEqual(est['reads'], {'search': 5, 'profile': 12, 'content': 12})
        self.assertEqual(ind.estimate(9, 4)['usd_max'], Decimal('2.73'))
        # Seeds and the prefilter are LinkedIn reads and rules: the USD worst case does not move.
        seeded = ind.estimate(6, 5, empresas=2, perfiles=3)
        self.assertEqual(seeded['usd_max'], Decimal('1.91'))
        self.assertEqual(seeded['reads'], {'search': 5 + 2 + 1, 'profile': 12 + 3, 'content': 12})
        self.assertEqual(ind.estimate(6, 0, empresas=2)['reads']['search'], 2)  # no United States search: no location read

    def test_an_unmeasured_audience_never_puts_a_candidate_out(self):
        unmeasured = measured(audience={'commenters': 2, 'classified': 0, 'fit': 0, 'fit_share': None})
        prelim = ind.prequalify(unmeasured)
        self.assertTrue(prelim['ok'])
        self.assertEqual(prelim['criteria']['audiencia']['status'], 'sin_medir')
        result = ind.evaluate(unmeasured, CLAIMS, self.sources)
        self.assertTrue(result['passed'])
        self.assertNotIn('audiencia', ' '.join(result['reasons']).lower())
        # Out for another reason, the step is that reason, never the audience nobody could measure.
        late = ind.evaluate(measured(days_since_last=30, audience=unmeasured['audience']), CLAIMS, self.sources)
        failing = [row for row in late['criteria'] if row['status'] != 'cumple' and (row['required'] or row['status'] == 'no_cumple')]
        self.assertEqual(ind._step(failing), 'actividad')
        self.assertEqual([row['key'] for row in failing], ['actividad'])


class PrefilterTests(SimpleTestCase):
    """The free first look at a headline: who clearly sells something else is out before any read."""

    def test_sellers_of_something_else_are_out(self):
        for headline in ('Executive coach for founders and CEOs', 'Go-to-market consultant for B2B SaaS | GTM advisor',
                         'I help consultants land clients on LinkedIn | Lead generation', 'Personal branding for executives',
                         'Technical recruiter | Talent acquisition for startups'):
            with self.subTest(headline=headline):
                verdict = ind.prefilter(headline)
                self.assertEqual(verdict['decision'], 'descartar')
                self.assertIn('Titular de otra industria', verdict['reason'])

    def test_who_names_a_service_goes_first_even_with_a_sales_word(self):
        owner = ind.prefilter('Founder & CEO at Northwind Labs | Software development agency for startups')
        self.assertEqual((owner['decision'], owner['services']), ('priorizar', ['software_a_la_medida']))
        self.assertEqual(ind.prefilter('Fractional CTO for seed-stage startups')['decision'], 'priorizar')
        self.assertEqual(ind.prefilter('Sales and growth | Founder at an AI consulting studio')['decision'], 'priorizar')
        self.assertEqual(ind.prefilter('Building MVPs', bio='We help founders with MVP development.')['services'], ['producto'])
        neutral = ind.prefilter('CEO at Acme')
        self.assertEqual((neutral['decision'], neutral['services']), ('medir', []))
        self.assertEqual(ind.prefilter('')['decision'], 'sin_titular')

    def test_latin_america_only_when_the_headline_says_they_sell_in_the_united_states(self):
        quiet = ind.prefilter('Founder | Custom software development', location='Medellín, Colombia')
        self.assertEqual(quiet['decision'], 'descartar')
        self.assertIn('Fuera de EE. UU.', quiet['reason'])
        for headline in ('Founder | Custom software for US startups', 'Founder | Nearshore software development teams',
                         'CEO | Software development agency serving North American companies'):
            with self.subTest(headline=headline):
                self.assertEqual(ind.prefilter(headline, location='Bogotá, Colombia')['decision'], 'priorizar')
        self.assertEqual(ind.prefilter('Founder | Custom software development', location='Austin, Texas')['decision'], 'priorizar')
        self.assertEqual(ind.prefilter('Founder | Custom software development')['decision'], 'priorizar')  # place unknown: no guess
        named = ind.prefilter('Co-founder at Imagine Apps', location='Bogotá, Colombia', company='Imagine Apps')
        self.assertNotEqual(named['decision'], 'descartar')  # a company Gustavo named: the criterion decides the market
        self.assertEqual(ind.prefilter('Executive coach', location='Bogotá', company='Imagine Apps')['decision'], 'descartar')

    def test_seeds_are_cleaned_and_capped(self):
        companies, slugs, issues = ind.seeds([' Imagine  Apps ', 'imagine apps', 'Northwind Labs'],
                                             [URL, SLUG, 'https://www.linkedin.com/in/otra-voz-test/'])
        self.assertEqual((companies, slugs, issues), (['Imagine Apps', 'Northwind Labs'], [SLUG, 'otra-voz-test'], []))
        _, _, bad = ind.seeds(['https://evil.example/x', '"quoted"'], ['not a profile!'])
        self.assertEqual(len(bad), 3)
        _, _, many = ind.seeds([f'Empresa {n}' for n in range(ind.MAX_SEEDS + 1)])
        self.assertIn(f'Como máximo {ind.MAX_SEEDS} empresas', ' '.join(many))


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
class ReferentKindTests(IndustryMixin, TestCase):
    """The kind decides whether a referent's outliers are growth models (and get their comments read): Gustavo's
    manual industry referents came in as niche ones. `referente --industria` and `referente-tipo` fix that."""

    def setUp(self):
        self.set_up_industry()
        env = patch.dict(os.environ, {'OPERATOR_ALLOW_FAKE': 'true', 'LIVE_PROVIDERS': 'false'})
        env.start()
        self.addCleanup(env.stop)
        FakeConnector.reset()
        self.addCleanup(FakeConnector.reset)
        fake = FakeConnector(self.account.external_account_id)
        for slug in ('voz-agencia-test', 'voz-nicho-test'):
            fake.seed_user(slug, slug.title(), posts=['Synthetic post'])

    def cmd(self, *args):
        out = StringIO()
        call_command('operador', '--usuario', 'gustavo', *args, '--cuenta', str(self.account.id), stdout=out)
        return out.getvalue()

    def test_a_referent_added_as_industry_keeps_that_kind_and_one_added_without_the_option_is_a_niche_voice(self):
        out = self.cmd('referente', '--perfil', 'https://www.linkedin.com/in/voz-agencia-test/', '--motivo', 'Agencia en EE. UU.', '--industria')
        agency = Referent.objects.get(public_identifier='voz-agencia-test')
        self.assertEqual(agency.kind, 'industria')
        self.assertIn('tipo industria', out)
        self.assertEqual(AuditEvent.objects.get(action='operator.referent_added', target=str(agency.pk)).metadata['kind'], 'industria')
        again = self.cmd('referente', '--perfil', 'voz-agencia-test', '--motivo', 'Otra vez')
        self.assertIn('Ya existía', again)
        self.assertIn('referente-tipo --tipo nicho', again)
        agency.refresh_from_db()
        self.assertEqual(agency.kind, 'industria')
        self.cmd('referente', '--perfil', 'voz-nicho-test', '--motivo', 'Voz del nicho')
        self.assertEqual(Referent.objects.get(public_identifier='voz-nicho-test').kind, 'nicho')

    def test_correcting_the_kind_is_a_dry_run_without_confirmation_audited_and_leaves_the_list_revision_alone(self):
        manual = self.referent('voz-nicho-test', kind='nicho')
        for d in range(10, 16):
            self.post(manual, d, 10)
        viral = self.post(manual, 3, 280, 20, POST_TEXT)
        mc.refresh(self.account, now=self.now)
        self.assertEqual(mc.growth_models(self.account, now=self.now), [])
        list_revision = ReferentControl.objects.get(account=self.account).revision
        args = ('referente-tipo', '--perfil', 'https://www.linkedin.com/in/voz-nicho-test/', '--tipo', 'industria',
                '--motivo', 'Lo añadimos como nicho por error')
        self.assertIn('Sin --confirmar no se cambia nada', self.cmd(*args))
        manual.refresh_from_db()
        self.assertEqual((manual.kind, manual.revision), ('nicho', 1))
        self.assertFalse(AuditEvent.objects.filter(target=str(manual.pk)).exists())
        self.assertIn('nicho → industria', self.cmd(*args, '--confirmar'))
        manual.refresh_from_db()
        self.assertEqual((manual.kind, manual.revision), ('industria', 2))
        self.assertEqual(ReferentControl.objects.get(account=self.account).revision, list_revision)
        event = AuditEvent.objects.get(action='referents.changed', target=str(manual.pk))
        self.assertEqual((event.metadata['before']['kind'], event.metadata['after']['kind']), ('nicho', 'industria'))
        self.assertIn('por error', event.metadata['reason'])
        self.assertEqual(len(refs.history(manual)), 1)
        self.assertEqual([m['post_id'] for m in mc.growth_models(self.account, now=self.now)], [str(viral.pk)])
        self.assertIn('ya es industria', self.cmd(*args, '--confirmar'))
        self.assertEqual(AuditEvent.objects.filter(target=str(manual.pk)).count(), 1)
        with self.assertRaisesMessage(CommandError, 'No es referente de esta cuenta'):
            self.cmd('referente-tipo', '--perfil', 'quien-no-es-test', '--tipo', 'industria', '--motivo', 'x', '--confirmar')

    def test_a_main_referent_changes_kind_only_by_gustavo(self):
        operator = get_user_model().objects.create_user('operador-test', is_superuser=True)
        main = self.main[0]
        with self.assertRaisesMessage(PermissionDenied, 'Solo Gustavo'):
            operador.set_referent_kind(operator, self.account, main.public_identifier, 'industria', 'Prueba', confirm=True)
        main.refresh_from_db()
        self.assertEqual(main.kind, 'nicho')
        _, previous, changed = operador.set_referent_kind(self.user, self.account, main.public_identifier, 'industria', 'Prueba', confirm=True)
        self.assertEqual((previous, changed), ('nicho', True))


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
        self.assertNotIn('intento', job.params)
        self.change(self.review())  # the month's search proposed someone, still undecided
        _, report = ind.enqueue(self.user, self.account, confirm=True)
        self.assertFalse(report['ok'])
        self.assertIn('Ya hubo una búsqueda de referentes de industria este mes con propuestas por decidir', ' '.join(report['issues']))
        _, small = ind.enqueue(self.user, self.account, tope_usd=Decimal('0.5'), confirm=True)
        self.assertTrue(any('no alcanza' in issue for issue in small['issues']))

    def test_a_month_without_proposals_can_search_again_and_proposals_or_a_running_one_block_it(self):
        month = refs.month_start(self.now)
        first, _ = ind.enqueue(self.user, self.account, confirm=True)
        self.assertEqual(first.id, uuid.uuid5(uuid.NAMESPACE_URL, f'referents:{self.account.pk}:{month}:industria'))  # unchanged
        empty = self.review(state='late')  # what production has today: ran, published, nobody proposed
        report = ind.guard(self.account)
        self.assertTrue(report['ok'], report['issues'])
        self.assertEqual(report['attempt'], 2)
        self.assertIn('Intento 2 de este mes', ' '.join(report['warnings']))
        again, _ = ind.enqueue(self.user, self.account, confirm=True, empresas=['Imagine Apps'])
        self.assertNotEqual(again.id, first.id)
        self.assertEqual(again.id, uuid.uuid5(uuid.NAMESPACE_URL, f'referents:{self.account.pk}:{month}:industria:2'))
        self.assertEqual((again.params['intento'], again.params['empresas']), (2, ['Imagine Apps']))
        self.assertEqual(ind.enqueue(self.user, self.account, confirm=True, empresas=['Imagine Apps'])[0].id, again.id)
        empty.state = 'preparing'
        empty.save()
        self.assertIn('en curso', ' '.join(ind.guard(self.account)['issues']))
        empty.state = 'late'
        empty.save()
        decided = self.change(empty, state='rejected')
        self.assertIn('ya decididas', ' '.join(ind.guard(self.account)['issues']))
        decided.delete()
        ReferentReview.objects.create(account=self.account, month=month, kind='industria', attempt=2, state='late',
                                      deadline=self.now + timedelta(days=14))
        ReferentReview.objects.create(account=self.account, month=month, kind='industria', attempt=3, state='incomplete',
                                      deadline=self.now + timedelta(days=14))
        self.assertIn('Ya hubo 3 búsquedas', ' '.join(ind.guard(self.account)['issues']))
        with patch.dict(os.environ, {'REFERENTES_INDUSTRIA_MAX_INTENTOS': '4'}):
            self.assertEqual(ind.guard(self.account)['attempt'], 4)
        self.assertTrue(ind.guard(self.account, now=self.now + timedelta(days=40))['ok'])  # another month: attempt 1

    @override_settings(**PRICES)
    def test_the_command_prints_the_same_worst_case_with_seeds_and_the_searches_it_will_make(self):
        out = StringIO()
        call_command('operador', '--usuario', 'gustavo', 'referentes-industria', '--cuenta', str(self.account.pk),
                     '--empresas', 'Imagine Apps, Northwind Labs', '--perfiles', URL, stdout=out)
        text = out.getvalue()
        self.assertIn('Costo máximo (reserva): 1.91 USD = 2 investigaciones web × 0.82 + selección 0.27', text)
        self.assertIn('Lecturas de LinkedIn como máximo: 8 búsquedas, 13 perfiles, 12 lecturas de contenido', text)
        self.assertIn('"Imagine Apps" founder', text)
        self.assertIn(ind.QUERIES[0][1], text)
        self.assertIn(f'Perfiles semilla: {SLUG}', text)
        self.assertIn('No se encoló nada', text)
        self.assertFalse(Job.objects.exists())
        with self.assertRaisesRegex(CommandError, 'Empresa inválida'):
            call_command('operador', '--usuario', 'gustavo', 'referentes-industria', '--cuenta', str(self.account.pk),
                         '--empresas', 'https://example.org/x', stdout=StringIO())

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
        env = patch.dict(os.environ, {'OPERATOR_ALLOW_FAKE': 'true', 'LIVE_PROVIDERS': 'false'})
        env.start()
        self.addCleanup(env.stop)
        FakeConnector.reset()
        self.addCleanup(FakeConnector.reset)
        self.conn = FakeConnector(self.account.external_account_id)

    def candidate(self, slug, name, followers, days, scores, headline='Founder · Estudio de producto', search=ind.QUERIES[0][1],
                  location='Austin, Texas', bio='We build MVPs for US startups.'):
        user = self.conn.seed_person(slug, name, headline=headline, search=search, location=location,
                                     signals={'followers': followers, 'bio': bio})
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
        self.conn.seed_person('cora-rechazada-test', 'Cora Rechazada', search=ind.QUERIES[0][1],
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
        self.assertEqual((dropped[0]['step'], dropped[0]['reads'], dropped[0]['found_by']),
                         ('actividad', 'perfil y posts', ['software_a_la_medida']))
        evaluated = {e['slug']: e for e in review.dossier['industria']['evaluated']}
        self.assertEqual((evaluated[SLUG]['step'], evaluated['beto-inactivo-test']['step']), ('propuesto', 'actividad'))
        funnel = review.dossier['industria']['embudo']
        self.assertEqual((funnel['encontrados'], funnel['medidos'], funnel['actividad'], funnel['propuestos']), (2, 2, 1, 1))
        self.assertNotIn('cora-rechazada-test', json.dumps(review.dossier['industria']['evaluated']))
        dumped = json.dumps([review.dossier, change.proposal], ensure_ascii=False)
        self.assertNotIn('Synthetic post text', dumped)
        self.assertNotIn('Comentarista', dumped)
        self.assertFalse(ObservedPost.objects.exists())
        self.assertEqual(CycleLedger.objects.get(key=str(review.pk)).calls, 2)
        self.assertEqual(ReferentNotice.objects.get(review=review, event='day1').payload['title'], 'Referentes de industria por decidir')
        self.assertFalse(Referent.objects.filter(public_identifier=SLUG).exists())

    # -- where candidates come from, and what each one cost

    DAYS, SCORES = [1, 3, 5, 8, 12, 20], [90] * 6

    def ctx(self):
        return {'positioning': {'version': 'v1'}, 'orientation': {'version': 'o1'}, 'memory': {'version': 'm1'},
                'grounding': {'course_status': 'disponible'}, 'course': 'Synthetic course', 'experiments': [],
                'referents': [refs.snapshot(r) for r in self.main]}

    def web(self, request):
        source = research.Source('web-1', WEB['url'], WEB['title'], WEB['quoted_text'], self.now.isoformat())
        return research.ResearchResult(request.public_question, 'complete', self.now.isoformat(),
                                       (research.Finding('Synthetic finding', ('web-1',)),), (source,))

    def propose(self, slug, name):
        def select(request):
            c = next(c for c in request['context']['industria']['candidatos'] if c['slug'] == slug)
            own = c['fuente_linkedin']
            incoming = {'identifier': slug, 'display_name': name, 'profile_url': c['profile_url'], 'niche': 'Agencia de software',
                        'audience': 'Founders de EE. UU.', 'contribution': 'Criterio de entrega', 'top_voice': False,
                        'sources': [own], 'industria': dict(CLAIMS, service_sources=[own])}
            return {'summary': 'Synthetic dossier', 'continuity': [],
                    'changes': [{'kind': 'add', 'incoming': incoming, 'reason': 'Founders de EE. UU.', 'evidence': [own]}]}
        return select

    def run_job(self, job, select):
        from team_backend import referentes_research
        with patch.object(referentes_research, 'context', return_value=self.ctx()), \
             patch.object(ind, 'select', side_effect=select), patch('team_backend.research.research', side_effect=self.web):
            return referentes_research.run(job)

    def directo_like(self, keep_public=1):
        """The direct connector's search page: ids for all, a public id for the first few, no name, headline, place
        or followers (linkedin_directo.lectura.search_results)."""
        original = FakeConnector.search_people

        def search(conn, keywords, location=None, profile_language=None):
            rows = original(conn, keywords, location, profile_language)
            return [dict(r, display_name='', headline='', location='', signals={},
                         **({} if n < keep_public else {'public_identifier': '', 'profile_url': ''})) for n, r in enumerate(rows)]
        return patch.object(FakeConnector, 'search_people', autospec=True, side_effect=search)

    def test_queries_aim_at_sellers_in_the_united_states_and_at_nearshore_teams_anywhere(self):
        result = ind.read_linkedin(self.account, self.now, {'candidatos': 6, 'busquedas': 5})
        calls = self.conn.state['search_calls']
        self.assertEqual([c['keywords'] for c in calls], [q[1] for q in ind.QUERIES[:5]])
        self.assertEqual([c['location'] for c in calls], [['103644278']] * 4 + [None])
        self.assertEqual([q['scope'] for q in result['queries']], ['us'] * 4 + ['global'])
        for query in ind.QUERIES:  # a seller's role and a service, never the bare service words of the first run
            self.assertRegex(query[1], r'(?i)founder|ceo|cto|fundador')
            self.assertNotIn(query[1], ('custom software development', 'product development', 'applied ai', 'fractional cto'))

    def test_the_prefilter_drops_a_coach_and_a_gtm_consultant_without_a_profile_read_and_measures_an_agency_owner(self):
        self.candidate('nora-agencia-test', 'Nora Agencia', 22000, self.DAYS, self.SCORES, headline=AGENCY)
        for slug, headline, followers in (('coach-ejecutivo-test', 'Executive coach for founders and CEOs', 34000),
                                          ('gtm-consultora-test', 'Go-to-market consultant for B2B SaaS', 92000)):
            user = self.conn.seed_person(slug, slug, headline=headline, location='New York, New York', signals={'followers': followers})
            Contact.objects.create(account=self.account, provider_user_id=user['id'], public_identifier=slug, display_name=slug,
                                   headline=headline, location='New York, New York', signals={'followers': followers},
                                   source=Contact.Source.COMMENTER)
        self.conn.seed_person('lead-gen-test', 'Lead Gen', headline='LinkedIn lead generation for consultants',
                              search=ind.QUERIES[0][1], location='Miami, Florida', signals={'followers': 81000})
        original = FakeConnector.get_profile
        with patch.object(FakeConnector, 'get_profile', autospec=True, side_effect=original) as read:
            result = ind.read_linkedin(self.account, self.now, {'candidatos': 6, 'busquedas': 1})
        self.assertEqual([call.args[1] for call in read.call_args_list], ['AConora-agencia-test'])
        self.assertEqual(result['reads'], {'searches': 1, 'profiles': 1, 'content': 2})
        self.assertEqual(AuditEvent.objects.filter(action='operator.profile_read', metadata__purpose='industry_referent').count(), 1)
        self.assertEqual([c['slug'] for c in result['candidates']], ['nora-agencia-test'])
        self.assertTrue(result['candidates'][0]['prelim']['ok'])
        self.assertEqual(result['candidates'][0]['prefilter']['decision'], 'priorizar')
        dropped = {d['slug']: d for d in result['discarded']}
        self.assertEqual(set(dropped), {'coach-ejecutivo-test', 'gtm-consultora-test', 'lead-gen-test'})
        for row in dropped.values():
            self.assertEqual((row['step'], row['reads'], row['remember']), ('prefiltro', 'ninguna', False))
        self.assertIn('coach', dropped['coach-ejecutivo-test']['reasons'][0])
        self.assertIn('go-to-market', dropped['gtm-consultora-test']['reasons'][0])
        self.assertEqual(dropped['lead-gen-test']['found_by'], ['software_a_la_medida'])

    def test_search_rows_without_public_id_are_read_once_and_put_out_before_their_posts(self):
        self.candidate('nora-agencia-test', 'Nora Agencia', 22000, self.DAYS, self.SCORES, headline=AGENCY)
        self.candidate('coach-oculto-test', 'Coach Oculto', 50000, self.DAYS, self.SCORES, headline='Leadership coach for founders',
                       bio='I coach founders through their first leadership team.')
        self.candidate('agencia-chica-test', 'Agencia Chica', 3000, self.DAYS, self.SCORES, headline=AGENCY)
        original = FakeConnector.list_user_posts
        with self.directo_like(), patch.object(FakeConnector, 'list_user_posts', autospec=True, side_effect=original) as posts:
            result = ind.read_linkedin(self.account, self.now, {'candidatos': 6, 'busquedas': 1})
        # The first run skipped rows without public id and ranked the rest as if they had no followers.
        self.assertEqual(result['reads'], {'searches': 1, 'profiles': 3, 'content': 2})
        self.assertEqual([call.args[1] for call in posts.call_args_list], ['AConora-agencia-test'])
        self.assertEqual({d['slug']: (d['step'], d['reads'], d['remember']) for d in result['discarded']},
                         {'coach-oculto-test': ('prefiltro', 'perfil', True), 'agencia-chica-test': ('tamano', 'perfil', True)})
        self.assertEqual((result['queries'][0]['results'], result['queries'][0]['with_public_id']), (3, 1))
        ReferentReview.objects.create(account=self.account, month=refs.month_start(self.now), kind='industria', state='late',
                                      deadline=self.now + timedelta(days=14), dossier={'industria': {'descartados': result['discarded']}})
        skip = ind.excluded(self.account, self.now)
        self.assertIn('ACocoach-oculto-test', skip)  # found again by id next time, without reading the profile twice
        self.assertIn('agencia-chica-test', skip)

    def test_company_and_profile_seeds_go_first_and_meet_the_same_criteria(self):
        self.candidate('nora-agencia-test', 'Nora Agencia', 90000, self.DAYS, self.SCORES, headline=AGENCY)
        self.candidate('ivan-imagine-test', 'Ivan Imagine', 12000, self.DAYS, self.SCORES, headline='Co-founder at Imagine Apps',
                       search='"Imagine Apps" founder', location='Bogotá, Colombia', bio='We build apps for US startups.')
        self.candidate('semilla-chica-test', 'Semilla Chica', 4000, self.DAYS, self.SCORES, headline='Executive coach', search=None)
        self.candidate('semilla-test', 'Semilla Grande', 30000, self.DAYS, self.SCORES, headline='Founder | Product studio', search=None)
        self.referent('ya-referente-test', kind='nicho')
        result = ind.read_linkedin(self.account, self.now, {
            'candidatos': 2, 'busquedas': 1, 'empresas': ['Imagine Apps'],
            'perfiles': ['semilla-chica-test', 'semilla-test', 'ya-referente-test']})
        self.assertEqual(self.conn.state['search_calls'][0], {'keywords': '"Imagine Apps" founder', 'location': None,
                                                              'profile_language': None})
        self.assertEqual([(c['slug'], c['found_by']) for c in result['candidates']],
                         [('semilla-test', ['perfil_manual']), ('ivan-imagine-test', ['empresa:Imagine Apps'])])
        # Named by hand, so its «coach» headline did not put it out before measuring; the size did.
        self.assertEqual({d['slug']: d['step'] for d in result['discarded']}, {'semilla-chica-test': 'tamano'})
        self.assertEqual([(w['slug'], w['reason']) for w in result['waiting']], [('nora-agencia-test', 'Cupo de candidatos medidos')])
        self.assertIn('ya-referente-test: ya es o fue referente', ' '.join(result['limitations']))

    def test_a_search_after_an_empty_one_closes_it_and_proposes_on_its_own_review(self):
        self.candidate('nora-agencia-test', 'Nora Agencia', 22000, self.DAYS, self.SCORES, headline=AGENCY)
        month = refs.month_start(self.now)
        empty = ReferentReview.objects.create(account=self.account, month=month, kind='industria', state='late',
                                              published_at=self.now, deadline=self.now + timedelta(days=14),
                                              dossier={'kind': 'industria', 'status': 'Sin nuevas propuestas'})
        job, _ = ind.enqueue(self.user, self.account, confirm=True, busquedas=1)
        self.assertEqual(job.params['intento'], 2)
        review = self.run_job(job, self.propose('nora-agencia-test', 'Nora Agencia'))
        empty.refresh_from_db()
        self.assertIsNotNone(empty.closed_at)
        self.assertEqual((empty.dossier['status'], empty.dossier['reemplazada']['por_intento']), ('Sin nuevas propuestas', 2))
        self.assertTrue(AuditEvent.objects.filter(action='referents.industry_retry', target=str(empty.pk)).exists())
        review.refresh_from_db()
        self.assertNotEqual(review.pk, empty.pk)
        self.assertEqual((review.attempt, review.state, review.changes.count()), (2, 'late', 1))
        self.assertTrue(CycleLedger.objects.filter(key=str(review.pk)).exists())
        self.assertFalse(CycleLedger.objects.filter(key=str(empty.pk)).exists())
        data = review.dossier['industria']
        self.assertEqual((data['intento'], data['embudo']['propuestos']), (2, 1))
        self.assertIn('propuestos 1', data['diagnostico'])
        self.assertEqual(ReferentNotice.objects.get(review=review, event='day1').payload['title'], 'Referentes de industria por decidir')
        refs.close(empty, empty.deadline + timedelta(seconds=1))  # closed already: no closing notice for the empty one
        self.assertFalse(ReferentNotice.objects.filter(review=empty, event='closed').exists())
        self.assertIn('por decidir', ' '.join(ind.guard(self.account)['issues']))  # no third attempt while one waits
        lines = '\n'.join(ind.report_lines(self.account))
        self.assertIn('intento 1 (late · cerrada', lines)
        self.assertIn('intento 2 (late)', lines)
        self.assertIn('Embudo: encontrados 1', lines)

    def test_the_run_refuses_another_attempt_while_a_proposal_waits(self):
        from team_backend import referentes_research
        month = refs.month_start(self.now)
        first = ReferentReview.objects.create(account=self.account, month=month, kind='industria', state='late',
                                              deadline=self.now + timedelta(days=14))
        ReferentChange.objects.create(review=first, ordinal=0, proposal={'kind': 'add', 'incoming': {'identifier': SLUG}})
        job = Job.objects.create(owner=self.user, kind='review_referents', agent='operador', task='industria', request_hash='i2',
                                 params={'account': str(self.account.pk), 'month': month.isoformat(), 'industria': True,
                                         'tope_usd': '3', 'candidatos': 6, 'busquedas': 1, 'intento': 2})
        with self.assertRaisesRegex(ValueError, 'por decidir'):
            referentes_research.run(job)
        first.refresh_from_db()
        self.assertIsNone(first.closed_at)
        self.assertFalse(ReferentReview.objects.filter(account=self.account, attempt=2).exists())
        self.assertFalse(self.conn.state.get('search_calls'))
