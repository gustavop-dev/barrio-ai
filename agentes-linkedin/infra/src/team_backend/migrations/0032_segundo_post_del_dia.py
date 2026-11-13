"""A day and hour Gustavo asks for himself may hold a second post that day, once he authorizes it in Tu turno
(12/11/2026: «cuando yo pida una fecha específica pase por encima de la regla pero en tu turno me pida la autorización»).

One open piece per day stays the rule; the second one is marked `second_of_day` and has its own unique slot."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('team_backend', '0031_red_senales_rampa'),
    ]

    operations = [
        migrations.AddField(
            model_name='editorialpiece',
            name='second_of_day',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='capture',
            name='day_request',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.RemoveConstraint(
            model_name='editorialpiece',
            name='one_open_piece_per_day',
        ),
        migrations.AddConstraint(
            model_name='editorialpiece',
            constraint=models.UniqueConstraint(condition=models.Q(('second_of_day', False), ('state__in', ['preparing', 'ready'])),
                                               fields=('slot_date',), name='one_open_piece_per_day'),
        ),
        migrations.AddConstraint(
            model_name='editorialpiece',
            constraint=models.UniqueConstraint(condition=models.Q(('second_of_day', True), ('state__in', ['preparing', 'ready'])),
                                               fields=('slot_date',), name='one_second_piece_per_day'),
        ),
    ]
