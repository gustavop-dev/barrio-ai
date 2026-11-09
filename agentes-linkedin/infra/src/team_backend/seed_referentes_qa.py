"""Synthetic OBS/TUR scenario, called only by seed_qa --referentes-mensual after its guards."""
from datetime import timedelta
from . import experimentos, referentes
from .models import Referent, ReferentControl, ReferentReview, ReferentChange, ReferentExperiment


def candidate(name, slug):
    return {'identifier': slug, 'display_name': name, 'profile_url': f'https://www.linkedin.com/in/{slug}/',
        'niche': 'Producto y software para startups', 'audience': 'Muestra pública de founders; datos sintéticos de QA',
        'contribution': 'Criterio de entrega de software e IA aplicada', 'top_voice': False, 'sources': ['qa-source']}


def seed(user, account, now, uid):
    main = []
    for n in range(1, 6):
        main.append(Referent.objects.create(id=uid(f'main:{n}'), account=account, public_identifier=f'main-qa-{n}',
            display_name=f'Main QA {n}', profile_url=f'https://www.linkedin.com/in/main-qa-{n}/',
            reason='Referente principal protegido; escenario sintético.', protected=True, position=n, created_by=user))
    ReferentControl.objects.create(account=account, initialized=True, initial_main=[str(r.pk) for r in main])
    month = referentes.month_start(now)
    start, deadline = referentes.bounds(month)
    review = ReferentReview.objects.create(id=uid('review:monthly'), account=account, month=month, state='published',
        deadline=deadline, published_at=start+timedelta(hours=9), dossier={'status': 'Propuestas listas',
        'summary': 'Revisión sintética del nicho: proteger main, probar voces con mejor encaje.',
        'sources': [{'id': 'qa-source', 'url': 'https://example.org/qa-referentes', 'title': 'Muestra sintética de QA', 'retrieved_at': now.isoformat()}],
        'limitations': ['Solo personas observadas; muestra de QA sin causalidad.'],
        'evidence': {'coverage': {'observed': 12, 'classified': 8, 'fit': 5, 'fit_pct': 62.5}, 'referents': []}})
    referentes.notice(review, 'day1', 'Revisión mensual de referentes', 'QA: el cierre real se prueba con reloj falso en backend.', now)
    for n, proposal in enumerate([
        {'kind': 'swap', 'outgoing': str(uid('referent:camejia-startups')), 'incoming': candidate('Nora Investigación', 'nora-investigacion-qa'), 'reason': 'Mejor encaje observado en founders que construyen producto.', 'evidence': ['qa-source']},
        {'kind': 'add', 'incoming': candidate('Ivo Producto', 'ivo-producto-qa'), 'reason': 'Hipótesis nueva con conversación pertinente.', 'evidence': ['qa-source']},
        {'kind': 'remove', 'outgoing': str(uid('referent:mafe-ruiz-producto')), 'reason': 'Revisar esta plaza variable con evidencia sintética.', 'evidence': ['qa-source']},
    ]):
        ReferentChange.objects.create(id=uid(f'monthly-change:{n}'), review=review, ordinal=n, proposal=proposal)
    exp = experimentos.propose(review, {'referent': str(uid('referent:analu-torres')), 'hypothesis': 'La conversación de Ana atrae personas con encaje.',
                                      'audience': 'Founders de startups', 'comparison': 'Encaje semanal frente a la base; sin control comparable disponible.'})
    # Future dates make positive approval reviewable on every CI day. The monthly deadline stays canonical.
    exp.starts_at = now+timedelta(days=1)
    exp.focus_at, exp.followup_at, exp.ends_at = (exp.starts_at+timedelta(days=d) for d in (14, 42, 49))
    exp.save()
