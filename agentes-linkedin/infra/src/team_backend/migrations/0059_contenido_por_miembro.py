"""Phase 4 of organizations: each member's content (docs/plan-organizaciones.md). A nullable `member` on pieces, weekly
plans and summaries, monthly reviews, audience snapshots, team questions, captures, gallery photos and the orientation;
the one-per-day, one-per-week and one-per-month rules become one per member (NULLS NOT DISTINCT: without members, one
for the whole installation, as before). Adding nullable columns and small indexes: no table rewrite. 0060 gives the rows
of before to the first member."""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('team_backend', '0058_identidad_inicial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='editorialpiece',
            name='one_open_piece_per_day',
        ),
        migrations.RemoveConstraint(
            model_name='editorialpiece',
            name='one_second_piece_per_day',
        ),
        migrations.RemoveConstraint(
            model_name='teamquestion',
            name='one_open_question_per_key',
        ),
        migrations.AddField(
            model_name='audiencesnapshot',
            name='member',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='audience', to='team_backend.member'),
        ),
        migrations.AddField(
            model_name='capture',
            name='member',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='captures', to='team_backend.member'),
        ),
        migrations.AddField(
            model_name='editorialpiece',
            name='member',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='pieces', to='team_backend.member'),
        ),
        migrations.AddField(
            model_name='galleryphoto',
            name='member',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='photos', to='team_backend.member'),
        ),
        migrations.AddField(
            model_name='monthlyreview',
            name='member',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='monthly_reviews', to='team_backend.member'),
        ),
        migrations.AddField(
            model_name='orientation',
            name='member',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='orientation', to='team_backend.member'),
        ),
        migrations.AddField(
            model_name='teamquestion',
            name='member',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='questions', to='team_backend.member'),
        ),
        migrations.AddField(
            model_name='weeklyplan',
            name='member',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='weekly_plans', to='team_backend.member'),
        ),
        migrations.AddField(
            model_name='weeklysummary',
            name='member',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='weekly_summaries', to='team_backend.member'),
        ),
        migrations.AlterField(
            model_name='audiencesnapshot',
            name='day',
            field=models.DateField(),
        ),
        migrations.AlterField(
            model_name='monthlyreview',
            name='month_start',
            field=models.DateField(),
        ),
        migrations.AlterField(
            model_name='weeklyplan',
            name='week_start',
            field=models.DateField(),
        ),
        migrations.AlterField(
            model_name='weeklysummary',
            name='week_start',
            field=models.DateField(),
        ),
        migrations.AddConstraint(
            model_name='audiencesnapshot',
            constraint=models.UniqueConstraint(fields=('member', 'day'), name='one_audience_per_member_day', nulls_distinct=False),
        ),
        migrations.AddConstraint(
            model_name='editorialpiece',
            constraint=models.UniqueConstraint(condition=models.Q(('second_of_day', False), ('state__in', ['preparing', 'ready'])), fields=('member', 'slot_date'), name='one_open_piece_per_member_day', nulls_distinct=False),
        ),
        migrations.AddConstraint(
            model_name='editorialpiece',
            constraint=models.UniqueConstraint(condition=models.Q(('second_of_day', True), ('state__in', ['preparing', 'ready'])), fields=('member', 'slot_date'), name='one_second_piece_per_member_day', nulls_distinct=False),
        ),
        migrations.AddConstraint(
            model_name='monthlyreview',
            constraint=models.UniqueConstraint(fields=('member', 'month_start'), name='one_review_per_member_month', nulls_distinct=False),
        ),
        migrations.AddConstraint(
            model_name='teamquestion',
            constraint=models.UniqueConstraint(condition=models.Q(('state', 'open')), fields=('member', 'memory_key'), name='one_open_question_per_member_key', nulls_distinct=False),
        ),
        migrations.AddConstraint(
            model_name='weeklyplan',
            constraint=models.UniqueConstraint(fields=('member', 'week_start'), name='one_plan_per_member_week', nulls_distinct=False),
        ),
        migrations.AddConstraint(
            model_name='weeklysummary',
            constraint=models.UniqueConstraint(fields=('member', 'week_start'), name='one_summary_per_member_week', nulls_distinct=False),
        ),
    ]
