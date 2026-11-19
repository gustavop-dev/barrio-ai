import json

from django.core.management.base import BaseCommand, CommandError

from team_backend import research


class Command(BaseCommand):
    help=('Investigación web (docs/acceso-web-equipo.md). Muestra las últimas investigaciones con su estado, propósito, '
          'limitación y diagnóstico, y cuántas hubo por estado cada día. Solo lee: no llama a modelos ni escribe. Nunca '
          'muestra la pregunta, URLs ni contenido de páginas.')

    def add_arguments(self,parser):
        parser.add_argument('--ultimas',type=int,default=20,help='Cuántas investigaciones recientes listar')
        parser.add_argument('--dias',type=int,default=7,help='Días del conteo por estado (hoy incluido)')
        parser.add_argument('--json',action='store_true',help='Imprime el informe en JSON')

    def handle(self,**o):
        if o['ultimas']<1 or o['dias']<1:raise CommandError('--ultimas y --dias deben ser al menos 1.')
        report=research.inspect(o['ultimas'],o['dias'])
        self.stdout.write(json.dumps(report,ensure_ascii=False,indent=2) if o['json'] else research.render(report))
