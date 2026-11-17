"""The buyer's journey (comprador.py): one BuyerJourney per buyer beside Contact and its append-only BuyerTouch log.
New tables only; nothing existing changes. Filled by `manage.py comprador reconstruir` and by the passive hooks."""

import django.db.models.deletion
import django.utils.timezone
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('team_backend', '0045_biblioteca_clases_01_12'),
    ]

    operations = [
        migrations.CreateModel(
            name='BuyerJourney',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('entry', models.CharField(choices=[('saliente', 'El equipo lo eligió'), ('entrante', 'Llegó con su invitación')], default='saliente', max_length=10)),
                ('route', models.CharField(choices=[('sin_definir', 'Sin definir'), ('comentarios', 'Publica: se calienta con comentarios'), ('sin_posts', 'No publica')], default='sin_definir', max_length=12)),
                ('step', models.CharField(choices=[('elegido', 'Elegido'), ('calentando', 'Calentando'), ('invitado', 'Invitado'), ('acepto', 'Aceptó'), ('mensaje_1', 'Mensaje 1'), ('mensaje_2', 'Mensaje 2'), ('mensaje_3', 'Mensaje 3'), ('mensaje_4', 'Mensaje 4'), ('respondio', 'Respondió'), ('interesado', 'Interesado'), ('reunion', 'Reunión agendada'), ('descanso', 'En descanso; puede volver'), ('salio', 'Salió del recorrido')], db_index=True, default='elegido', max_length=12)),
                ('next_at', models.DateTimeField(blank=True, db_index=True, null=True)),
                ('attempt', models.PositiveSmallIntegerField(default=1)),
                ('attempts', models.JSONField(blank=True, default=list)),
                ('rest_reason', models.CharField(blank=True, choices=[('sin_respuesta_calentamiento', 'Sin respuesta al calentamiento'), ('invitacion_no_aceptada', 'Invitación no aceptada'), ('secuencia_sin_respuesta', 'Secuencia terminada sin respuesta'), ('no_es_el_momento', 'No es el momento')], max_length=30)),
                ('rest_until', models.DateTimeField(blank=True, null=True)),
                ('exit_reason', models.CharField(blank=True, choices=[('pidio_no_contacto', 'Pidió no ser contactado'), ('no_le_interesa', 'No le interesa'), ('descartado_por_gustavo', 'Descartado por Gustavo'), ('fuera_de_criterio', 'Dejó de cumplir el criterio de comprador'), ('invitacion_cerrada', 'Invitación ignorada o retirada'), ('perfil_restringido', 'Perfil restringido')], max_length=30)),
                ('exited_at', models.DateTimeField(blank=True, null=True)),
                ('exit_step', models.CharField(blank=True, max_length=12)),
                ('chosen_at', models.DateTimeField(db_index=True)),
                ('warming_at', models.DateTimeField(blank=True, null=True)),
                ('invited_at', models.DateTimeField(blank=True, null=True)),
                ('invite_note', models.BooleanField(blank=True, null=True)),
                ('accepted_at', models.DateTimeField(blank=True, null=True)),
                ('first_message_at', models.DateTimeField(blank=True, null=True)),
                ('last_message_at', models.DateTimeField(blank=True, null=True)),
                ('replied_at', models.DateTimeField(blank=True, null=True)),
                ('interested_at', models.DateTimeField(blank=True, null=True)),
                ('meeting_at', models.DateTimeField(blank=True, null=True)),
                ('messages_sent', models.PositiveSmallIntegerField(default=0)),
                ('warm_comments', models.PositiveSmallIntegerField(default=0)),
                ('comments_before_invite', models.PositiveSmallIntegerField(default=0)),
                ('visits', models.PositiveSmallIntegerField(default=0)),
                ('inbound_signals', models.PositiveIntegerField(default=0)),
                ('last_inbound_at', models.DateTimeField(blank=True, null=True)),
                ('signal_before_invite', models.BooleanField(default=False)),
                ('origin', models.CharField(choices=[('en_vivo', 'Registrado al ocurrir'), ('reconstruido', 'Reconstruido desde el historial')], default='en_vivo', max_length=12)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('contact', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='buyer_journey', to='team_backend.contact')),
            ],
            options={
                'ordering': ['-chosen_at'],
            },
        ),
        migrations.CreateModel(
            name='BuyerTouch',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('kind', models.CharField(choices=[('elegido', 'Elegido como comprador'), ('ruta', 'Ruta decidida'), ('angulo', 'Ángulo del intento'), ('descanso', 'Pasa a descanso'), ('reintento', 'Nuevo intento'), ('salida', 'Sale del recorrido'), ('reabierto', 'Vuelve al recorrido'), ('ya_conectados', 'Ya eran conexión'), ('no_escribirle', 'Gustavo decidió no escribirle'), ('oportunidad', 'Oportunidad registrada'), ('interesado', 'Respuesta con interés'), ('seguir', 'Seguir (RED-01)'), ('comentario', 'Comentario en un post suyo (INT-03)'), ('reaccion', 'Reacción a un post o comentario suyo (INT-02)'), ('respuesta_hilo', 'Respuesta a su comentario en un post de Gustavo (INT-04)'), ('visita', 'Visita a su perfil'), ('invitacion', 'Invitación (RED-02)'), ('aceptaste_invitacion', 'Gustavo aceptó su invitación (RED-04)'), ('mensaje', 'Mensaje enviado por Gustavo («Hecho, le escribí»)'), ('mensaje_visto', 'Mensaje de Gustavo leído en el inbox'), ('respondio_comentario', 'Respondió a un comentario del equipo'), ('comento_post', 'Comentó en un post de Gustavo'), ('reacciono_post', 'Reaccionó a un post de Gustavo'), ('nos_siguio', 'Siguió a Gustavo'), ('nos_invito', 'Invitó a Gustavo'), ('acepto_invitacion', 'Aceptó la invitación'), ('abrio_conversacion', 'Le escribió primero'), ('respondio_mensaje', 'Respondió un mensaje'), ('reunion', 'Agendó una reunión')], max_length=24)),
                ('direction', models.CharField(choices=[('saliente', 'Lo hizo el equipo o Gustavo'), ('entrante', 'Lo hizo la persona'), ('estado', 'Cambio de estado del recorrido')], max_length=10)),
                ('at', models.DateTimeField(db_index=True)),
                ('key', models.CharField(max_length=200)),
                ('detail', models.JSONField(blank=True, default=dict)),
                ('source', models.CharField(choices=[('en_vivo', 'Registrado al ocurrir'), ('reconstruido', 'Reconstruido desde el historial'), ('fase', 'Registrado por una fase del recorrido')], default='en_vivo', max_length=12)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('comment', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='team_backend.postcomment')),
                ('conversation', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='team_backend.conversation')),
                ('execution', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='team_backend.actionexecution')),
                ('journey', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='touches', to='team_backend.buyerjourney')),
                ('opportunity', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='team_backend.opportunity')),
                ('outcome', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='team_backend.actionoutcome')),
                ('post', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='team_backend.observedpost')),
                ('proposal', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='team_backend.actionproposal')),
            ],
            options={
                'ordering': ['at', 'created_at'],
                'constraints': [models.UniqueConstraint(fields=('journey', 'key'), name='one_buyer_touch_per_key')],
            },
        ),
    ]
