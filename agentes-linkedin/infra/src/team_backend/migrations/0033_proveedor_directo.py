"""The provider `directo`: LinkedIn without Unipile, through the navegador service (docs/plan-linkedin-directo.md).
Only the choices change; existing accounts keep their provider."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('team_backend', '0032_segundo_post_del_dia'),
    ]

    operations = [
        migrations.AlterField(
            model_name='connectoraccount',
            name='provider',
            field=models.CharField(choices=[('unipile', 'Unipile v2'), ('fake', 'Simulado (pruebas)'), ('directo', 'LinkedIn directo (navegador)'), ('linkedin', 'API oficial de LinkedIn'), ('linkedin_fake', 'API oficial simulada (pruebas)')], max_length=20),
        ),
    ]
