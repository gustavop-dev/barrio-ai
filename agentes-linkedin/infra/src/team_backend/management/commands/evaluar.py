import json
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from team_backend import evaluaciones

def _usd(value):
    try:return Decimal(value)
    except InvalidOperation:raise ValueError(f'Importe inválido: {value}') from None

class Command(BaseCommand):
    help=('Evalúa los agentes con casos del historial de esta base (auditoría de IA, fase 3). Por defecto es un ensayo: cuenta '
          'los casos y estima el coste por agente y modelo sin llamar a la API. --ejecutar paga, dentro de --max-usd y EVAL_LIMIT_USD.')

    def add_arguments(self,parser):
        parser.add_argument('--agentes',default=','.join(evaluaciones.AGENTS),help='Lista separada por comas: '+', '.join(evaluaciones.AGENTS))
        parser.add_argument('--desde',type=date.fromisoformat,default=evaluaciones.GO_LIVE,help='Primer día del historial (AAAA-MM-DD)')
        parser.add_argument('--limite',type=int,default=evaluaciones.TARGET[1],help='Casos por agente como máximo')
        parser.add_argument('--modelo',action='append',default=[],help='Modelo a evaluar (repetible); «jev» solo para el clasificador')
        parser.add_argument('--ejecutar',action='store_true',help='Llamadas pagadas (requiere --max-usd y EVAL_LIMIT_USD)')
        parser.add_argument('--max-usd',type=_usd,help='Tope de gasto de esta corrida: se detiene antes de una llamada que pueda superarlo')
        parser.add_argument('--sin-lider',action='store_true',help='Comentarios: solo reglas deterministas, sin las preguntas del líder (Jev)')
        parser.add_argument('--catalogo',help='Comentarios: unidades del curso a medir. Una versión del catálogo (en sombra, sin '
                            'activarla) o «fijas» (las listas del código). Por defecto, las que carga producción.')
        parser.add_argument('--json',action='store_true',help='Imprime el informe en JSON')
        parser.add_argument('--salida',help='Además, escribe el informe JSON en esta ruta (dentro del servidor)')

    def handle(self,**o):
        agents=[a.strip() for a in o['agentes'].split(',') if a.strip()]
        if o['ejecutar'] and o['max_usd'] is None:raise CommandError('--ejecutar requiere --max-usd.')
        try:
            report=evaluaciones.evaluate(agents,since=o['desde'],limit=o['limite'],models=o['modelo'],execute=o['ejecutar'],
                                         max_usd=o['max_usd'],lead=not o['sin_lider'],catalog=o['catalogo'])
        except ValueError as exc:raise CommandError(str(exc)) from None
        data=json.dumps(report,ensure_ascii=False,indent=2,default=str)
        self.stdout.write(data if o['json'] else evaluaciones.render(report))
        if o['salida']:
            Path(o['salida']).write_text(data,encoding='utf-8')
            self.stdout.write(f'Informe JSON en {o["salida"]}.')
