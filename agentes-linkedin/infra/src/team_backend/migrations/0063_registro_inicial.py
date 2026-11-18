"""Phase 6 of organizations, the data of before (docs/plan-organizaciones.md «Fase 6: lo construido»).

Everything there is today is the first member's (Gustavo in production): every contact gets its organization's card
(models.Person), and the first member becomes the owner of the people she already touched (the contact went past «fit»:
followed, invited, connected or closed; or a write reached her: an executed follow, invitation, acceptance, comment on
her post or reply to her). The candidates nobody touched stay free. LinkedIn's cannot_resend_yet refusals
(network.recipient_blocked) and the buyers who asked not to be contacted or said they are not interested become
exclusions for everyone, with the first member as the one whose history caused them (she keeps today's rules). Every
comment proposal on a referent's post becomes the post's claim of the member of its account (registro.claim_post).

Safe on the production database: inserts in new tables (hundreds of rows) and an UPDATE of Contact.person, in the
migration's transaction; nothing of before changes. Idempotent: run again it finds every card and claim in place.
Without members it does nothing (bootstrap_local's first member adopts them later: registro.adopt). Reversible: the
reverse step empties Contact.person and deletes the cards and claims."""
from django.db import migrations

STAGE_OF = {'candidate': 'candidata', 'fit': 'candidata', 'incoming': 'candidata', 'followed': 'seguida',
            'invited': 'invitada', 'connected': 'conectada', 'discarded': 'descartada', 'closed': 'descartada'}
SHARED_KEYS = ('fit', 'role', 'modality', 'affinity', 'confidence', 'region', 'reason', 'model', 'classified_at', 'rule',
               'buyer', 'stage_check', 'course_citations', 'minimum_confidence')
UNTOUCHED = ('candidate', 'fit', 'incoming', 'discarded')


def forwards(apps, schema_editor):
    from team_backend.sin_posts import company_of
    Member = apps.get_model('team_backend', 'Member')
    first = Member.objects.order_by('created_at', 'pk').first()
    if first is None:
        return
    Contact = apps.get_model('team_backend', 'Contact')
    Person = apps.get_model('team_backend', 'Person')
    PostClaim = apps.get_model('team_backend', 'PostClaim')
    Execution = apps.get_model('team_backend', 'ActionExecution')
    Proposal = apps.get_model('team_backend', 'ActionProposal')
    Journey = apps.get_model('team_backend', 'BuyerJourney')
    AuditEvent = apps.get_model('team_backend', 'AuditEvent')
    organizations = dict(Member.objects.values_list('pk', 'organization_id'))
    members = dict(Member.objects.values_list('pk', 'pk'))

    def org_of(account):
        return organizations.get(account.member_id) or first.organization_id

    journeys = {j.contact_id: j for j in Journey.objects.all()}
    written = Execution.objects.filter(wrote=True)
    touched_uids = set(written.exclude(proposal__contact__isnull=True).values_list('proposal__contact__provider_user_id', flat=True))
    touched_uids |= set(written.filter(proposal__post__referent__isnull=True).exclude(proposal__post__isnull=True)
                        .values_list('proposal__post__author_provider_id', flat=True))
    touched_uids |= set(written.exclude(proposal__comment__isnull=True).values_list('proposal__comment__author_provider_id', flat=True))
    blocked = set(AuditEvent.objects.filter(action='network.recipient_blocked').values_list('target', flat=True))
    for contact in Contact.objects.select_related('account').order_by('discovered_at', 'pk').iterator():
        uid = (contact.provider_user_id or '').strip()
        if uid in ('', 'me'):
            continue
        org = org_of(contact.account)
        owner = members.get(contact.account.member_id) or first.pk
        journey = journeys.get(contact.pk)
        stage = 'descanso' if journey is not None and journey.step == 'descanso' else STAGE_OF.get(contact.stage, 'candidata')
        classification = contact.classification or {}
        card, created = Person.objects.get_or_create(organization_id=org, provider_user_id=uid, defaults={
            'public_identifier': contact.public_identifier, 'display_name': contact.display_name, 'headline': contact.headline,
            'company': company_of(contact.headline)[:120], 'stage': stage, 'created_at': contact.discovered_at,
            'classification': ({**{k: classification[k] for k in SHARED_KEYS if k in classification},
                                'contact': str(contact.pk), 'member': str(owner)} if classification.get('classified_at') else {})})
        fields = {}
        was_touched = (contact.stage not in UNTOUCHED or contact.followed_at or contact.invited_at or contact.connected_at
                       or uid in touched_uids)
        if was_touched and card.owner_id is None:
            fields.update(owner_id=owner, owned_since=contact.followed_at or contact.invited_at or contact.connected_at
                          or contact.updated_at, touch='antes')
        if not card.excluded:
            if uid in blocked:
                fields.update(excluded='rechazo_linkedin', excluded_reason='LinkedIn rechazó su invitación (cannot_resend_yet).',
                              excluded_at=contact.updated_at, excluded_by_id=owner)
            elif journey is not None and journey.exit_reason in ('pidio_no_contacto', 'no_le_interesa'):
                fields.update(excluded='no_contactar', excluded_reason=f'Salida definitiva de su recorrido ({journey.exit_reason}).',
                              excluded_at=journey.exited_at or contact.updated_at, excluded_by_id=owner)
        if fields:
            Person.objects.filter(pk=card.pk).update(**fields)
        if contact.person_id != card.pk:
            Contact.objects.filter(pk=contact.pk).update(person_id=card.pk)
    for proposal in Proposal.objects.filter(capability='INT-03', post__referent__isnull=False).select_related(
            'post', 'account').order_by('created_at', 'pk'):
        PostClaim.objects.get_or_create(organization_id=org_of(proposal.account), provider_post_id=proposal.post.provider_post_id,
                                        defaults={'member_id': members.get(proposal.account.member_id) or first.pk,
                                                  'proposal': proposal.pk, 'claimed_at': proposal.created_at})


def backwards(apps, schema_editor):
    apps.get_model('team_backend', 'Contact').objects.exclude(person=None).update(person=None)
    apps.get_model('team_backend', 'PostClaim').objects.all().delete()
    apps.get_model('team_backend', 'Person').objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('team_backend', '0062_registro_de_personas'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
