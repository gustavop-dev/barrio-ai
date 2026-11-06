"""Development retrieval probes, not a human-validated or held-out benchmark."""
import time
from .retrieval import search

CASES=[
 (['LI-01-M006-K02'],[
  '¿Cuáles son las cuatro dimensiones para definir al cliente?',
  'Identidad urgencia transformación freno del cliente',
  '¿Qué preguntas definen al cliente ideal?',
  '¿Cómo entender quién compra, qué necesita y qué le impide avanzar?']),
 (['LI-02-V016-K01','LI-02-V015-K05'],[
  '¿Cómo usar palabras clave en mi titular?',
  'Titular con palabras por las que busca el cliente',
  '¿Pongo mi cargo o términos reconocibles por el comprador?',
  '¿Cómo hacer que mi especialidad se asocie con mi nombre?']),
 (['LI-03-V009-K02','LI-03-M005-K05','LI-03-V017-K02'],[
  '¿El barrio debe tener solo compradores?',
  'Compradores referidores divulgadores en el barrio',
  '¿Quién puede ayudarme aunque nunca compre mis servicios?',
  '¿Qué papeles debe tener mi comunidad de LinkedIn?']),
 (['LI-04-M005-K01'],[
  '¿Cuáles son los cinco filtros para validar un pilar?',
  'Validar un pilar temático antes de usarlo',
  '¿Cómo sé que un territorio de contenido merece la pena?',
  '¿Basta con saber de un tema para elegirlo como pilar?']),
 (['LI-05-V009-K02','LI-05-V014-K03'],[
  '¿Cómo pasar del pilar a una idea de publicación?',
  'Tema dolor frase con tensión para un post',
  '¿Cómo convertir mi tema general en una frase concreta?',
  '¿Qué pasos conectan un pilar con el problema del lector?']),
 (['LI-06-M001-K04'],[
  '¿Cómo evitar el clickbait?',
  'Cumplir la promesa del gancho sin engañar al lector',
  '¿Qué pasa si el texto contradice lo prometido al inicio?',
  '¿Puedo exagerar la apertura para conseguir clics?']),
 (['LI-01-V024-K01'],[
  '¿Es obligatorio comenzar el titular con ayudo?',
  'Especializar el mensaje sin imponer una fórmula de expresión',
  '¿Puedo describir mi servicio sin usar la palabra ayudo?',
  '¿Elegir un nicho implica renunciar a oportunidades?']),
 (['LI-05-V010-K02'],[
  '¿Cómo usar Google Trends para comparar pilares?',
  'Interés de búsqueda no equivale a viralidad',
  '¿Una tendencia de búsqueda garantiza que mi post se vuelva viral?',
  '¿Qué límites tiene Google Trends para decidir contenido?']),
]

def evaluate(mode='lexical'):
    rows=[]
    for expected,queries in CASES:
        for query in queries:
            start=time.monotonic();result=search(query,limit=10,mode=mode)
            ids=[r['id'] for r in result['results']]
            ranks=[ids.index(uid)+1 for uid in expected if uid in ids]
            rows.append({'query':query,'expected_any':expected,'retrieved':ids,'hit_at_10':bool(ranks),
                         'reciprocal_rank':1/min(ranks) if ranks else 0,'seconds':round(time.monotonic()-start,3),'actual_mode':result['mode']})
    hits=sum(r['hit_at_10'] for r in rows)
    return {'requested_mode':mode,'cases':len(rows),'hits_at_10':hits,'hit_rate':hits/len(rows),
            'mrr':sum(r['reciprocal_rank'] for r in rows)/len(rows),
            'scope':'Consultas de desarrollo con unidades de referencia; no conjunto ciego ni evaluación humana. Otras unidades recuperadas también pueden ser pertinentes.',
            'production_acceptance':'Pendiente comparación híbrida y revisión de cobertura/excepciones; no inferir calidad de respuestas a partir de este indicador.',
            'results':rows}
