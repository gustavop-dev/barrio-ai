"""IMG-14: a photo cut to LinkedIn's size by code (no image model) is marked apart from an AI edit. New column with a
default; existing rows stay as they are (original or AI-edited)."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('team_backend', '0038_traduccion_de_ids'),
    ]

    operations = [
        migrations.AddField(
            model_name='pieceimage',
            name='cropped',
            field=models.BooleanField(default=False),
        ),
    ]
