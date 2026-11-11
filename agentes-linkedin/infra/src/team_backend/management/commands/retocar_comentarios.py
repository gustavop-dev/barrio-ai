"""Apply the comment rework (EDI-22) to comments left on ready pieces before the flow existed."""
from django.core.management.base import BaseCommand
from team_backend import retoque


class Command(BaseCommand):
    help = ('Lista los comentarios de Gustavo sobre piezas listas que nadie aplicó. Con --aplicar, el equipo rehace cada '
            'pieza (llamadas pagadas: director, verificador, edición y revisión visual) y la nueva versión pasa por Jev.')

    def add_arguments(self, parser):
        parser.add_argument('--aplicar', action='store_true')

    def handle(self, **options):
        rows = retoque.pending_comments()
        for capture, piece, proposal in rows:
            self.stdout.write(f'{capture.id} pieza {piece.id} {piece.scheduled_for:%Y-%m-%d %H:%M} propuesta {proposal.state}: '
                              f'{capture.text[:120]}')
        if not options['aplicar']:
            self.stdout.write(f'{len(rows)} comentario(s) pendiente(s); nada aplicado (usa --aplicar).')
            return
        for capture in retoque.apply_pending():
            rework = (capture.routed_to or {}).get('rework') or {}
            self.stdout.write(f'{capture.id}: {rework.get("state")} · {capture.outcome.get("text", "")}')
