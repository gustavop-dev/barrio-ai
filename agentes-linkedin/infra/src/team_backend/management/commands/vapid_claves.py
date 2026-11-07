from django.core.management.base import BaseCommand
from team_backend.push import generate_keys

class Command(BaseCommand):
    help='Genera claves VAPID para las notificaciones push. Copiar al .env privado; no versionar.'
    def handle(self,**options):
        public,private=generate_keys()
        self.stdout.write(f'VAPID_PUBLIC_KEY={public}\nVAPID_PRIVATE_KEY={private}\nVAPID_SUBJECT=mailto:tu-correo@ejemplo.com')
