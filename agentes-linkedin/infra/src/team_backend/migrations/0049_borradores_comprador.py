"""Phase 3 of the buyer (mensajes_comprador.py): BuyerDraft, one decision per person, kind, number and attempt (the first
message Gustavo sends himself, or the note of an invitation), and the «borrador» touch of the journey. A new table and a
new choice; nothing existing changes."""

import django.db.models.deletion
import django.utils.timezone
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('team_backend', '0048_recorrido_comprador'),
    ]

    operations = [
        migrations.AlterField(
            model_name='buyertouch',
            name='kind',
            field=models.CharField(choices=[('elegido', 'Elegido como comprador'), ('ruta', 'Ruta decidida'), ('angulo', 'Ángulo del intento'), ('descanso', 'Pasa a descanso'), ('reintento', 'Nuevo intento'), ('salida', 'Sale del recorrido'), ('reabierto', 'Vuelve al recorrido'), ('ya_conectados', 'Ya eran conexión'), ('no_escribirle', 'Gustavo decidió no escribirle'), ('borrador', 'Borrador preparado o descartado (fase 3)'), ('oportunidad', 'Oportunidad registrada'), ('interesado', 'Respuesta con interés'), ('seguir', 'Seguir (RED-01)'), ('comentario', 'Comentario en un post suyo (INT-03)'), ('reaccion', 'Reacción a un post o comentario suyo (INT-02)'), ('respuesta_hilo', 'Respuesta a su comentario en un post de Gustavo (INT-04)'), ('visita', 'Visita a su perfil'), ('invitacion', 'Invitación (RED-02)'), ('aceptaste_invitacion', 'Gustavo aceptó su invitación (RED-04)'), ('mensaje', 'Mensaje enviado por Gustavo («Hecho, le escribí»)'), ('mensaje_visto', 'Mensaje de Gustavo leído en el inbox'), ('respondio_comentario', 'Respondió a un comentario del equipo'), ('comento_post', 'Comentó en un post de Gustavo'), ('reacciono_post', 'Reaccionó a un post de Gustavo'), ('nos_siguio', 'Siguió a Gustavo'), ('nos_invito', 'Invitó a Gustavo'), ('acepto_invitacion', 'Aceptó la invitación'), ('abrio_conversacion', 'Le escribió primero'), ('respondio_mensaje', 'Respondió un mensaje'), ('reunion', 'Agendó una reunión')], max_length=24),
        ),
        migrations.CreateModel(
            name='BuyerDraft',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('kind', models.CharField(choices=[('mensaje', 'Primer mensaje (después de aceptar)'), ('nota', 'Nota de la invitación')], max_length=8)),
                ('number', models.PositiveSmallIntegerField(default=1)),
                ('attempt', models.PositiveSmallIntegerField(default=1)),
                ('state', models.CharField(choices=[('en_revision', 'Esperando la revisión del líder'), ('listo', 'Listo: en Tu turno (mensaje) o esperando la invitación (nota)'), ('usada', 'Nota puesta en una invitación'), ('enviado', 'Enviado (Gustavo le escribió o la nota salió con la invitación)'), ('no_enviado', 'No enviado (Gustavo decidió no escribirle o la invitación salió sin la nota)'), ('descartado', 'Descartado por las reglas fijas o el líder'), ('sin_borrador', 'Sin borrador: nada real que citar, sin cupo de notas o ya hay conversación'), ('caducado', 'Caducado sin usar'), ('reemplazado', 'Reemplazado: ya hubo otro primer mensaje o la persona ya no está en ese paso')], db_index=True, max_length=12)),
                ('stopped_by', models.CharField(blank=True, choices=[('reglas', 'Reglas fijas'), ('juez', 'Líder (Jev)'), ('hecho', 'Nada real que citar'), ('cupo', 'Sin cupo de notas este mes'), ('conversacion', 'Ya hay una conversación')], max_length=12)),
                ('reason', models.TextField(blank=True)),
                ('text', models.TextField(blank=True)),
                ('language', models.CharField(blank=True, max_length=10)),
                ('anchor', models.JSONField(blank=True, default=dict)),
                ('inputs', models.JSONField(blank=True, default=dict)),
                ('citations', models.JSONField(blank=True, default=list)),
                ('issues', models.JSONField(blank=True, default=list)),
                ('review', models.JSONField(blank=True, default=dict)),
                ('model', models.CharField(blank=True, max_length=100)),
                ('show_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('decided_at', models.DateTimeField(blank=True, null=True)),
                ('closed_at', models.DateTimeField(blank=True, null=True)),
                ('closed_note', models.TextField(blank=True)),
                ('contact', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='buyer_drafts', to='team_backend.contact')),
                ('proposal', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='buyer_drafts', to='team_backend.actionproposal')),
            ],
            options={
                'ordering': ['-created_at'],
                'constraints': [models.UniqueConstraint(fields=('contact', 'kind', 'number', 'attempt'), name='one_buyer_draft_per_step')],
            },
        ),
    ]
