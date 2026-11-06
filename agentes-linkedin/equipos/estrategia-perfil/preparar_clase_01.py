"""Paquete local y trazable; no ejecuta agentes ni llama a proveedores."""
import hashlib
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
ORIGIN = ROOT / 'LinkedIn Sales - Entrega clase 01/01 - Clase 01'
SOURCE = ORIGIN / 'quality/aprendizajes.json'
DATA = json.loads(SOURCE.read_text())
UNITS = {u['id']: u for u in DATA['learning_units']}

def write(name, data):
    if name == 'memoria-compartida.json' and (OUT / name).exists():
        return  # Reconstruir conocimiento nunca borra la memoria ya trabajada.
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')

def ids(*short):
    return ['LI-01-' + s for s in short]

rules = []
def rule(key, agents, title, instruction, refs, limitation):
    rules.append(dict(id=key, agents=agents.split(), title=title,
                      instruction=instruction, unit_ids=ids(*refs.split()), limitation=limitation,
                      origin='síntesis operativa de la clase 01'))

rule('C01', 'posicionamiento perfil', 'Cliente antes que perfil',
     'Definir al destinatario y la ayuda que busca antes de decidir cómo presentarla. Mantener coherencia entre cliente, perfil, barrio, temas y publicaciones.',
     'V010-K01 V011-K01 V016-K02 V024-K07',
     'La clase anuncia las otras etapas; no las desarrolla todas. Perfil puede detectar vacíos, pero no inventar el cliente para poder redactar.')
rule('C02', 'posicionamiento perfil', 'Marca personal al servicio del comprador',
     'Comunicar la capacidad de ayudar a quien aún no conoce al profesional. Vincular experiencia y credenciales con esa ayuda. Mantener la identidad del profesional sin convertir su trayectoria en el único argumento.',
     'V002-K05 V012-K04 V018-K05', 'No borrar la experiencia ni suponer que todo logro es irrelevante.')
rule('C03', 'posicionamiento perfil', 'Asociación profesional reconocible',
     'Elegir por qué conocimiento y solución debe ser recordada la persona. Hacer convivir ofertas y negocios solo cuando exista un eje comprensible para la audiencia.',
     'V008-K02 V012-K02 V012-K03 V013-K01', 'La marca personal no obliga a exponer intimidad ni a describir todos los intereses del profesional.')
rule('C04', 'posicionamiento perfil', 'El barrio incluye a quienes no compran',
     'Distinguir comprador prioritario de comunidad: incluir aliados y divulgadores que aportan conversación y difusión aunque no contraten. Escuchar sus preguntas para entender mejor al cliente.',
     'V010-K03 V011-K04', 'La clase 01 no desarrolla una taxonomía exhaustiva ni tácticas de búsqueda. Los cinco lectores de nuestra arquitectura son un diseño del proyecto, no una lista literal de esta clase.')
rule('C05', 'posicionamiento perfil', 'Cliente protagonista y profesional guía',
     'Mostrar el problema y recorrido del cliente; el profesional aporta comprensión, capacidad y camino. Usar la trayectoria como evidencia relevante de esa capacidad.',
     'V017-K02 V017-K03 V018-K01 M007-K02', 'No inventar experiencias personales para mostrar empatía ni convertir la analogía de Gandalf en una regla psicológica demostrada.')
rule('C06', 'posicionamiento perfil', 'Las cinco frases del mensaje',
     'Articular problema central, empatía, respuesta que resuelve el problema, cambio que permite al cliente y resultado final con y sin solución. Usar las cinco funciones como marco, adaptando el estilo al caso.',
     'M007-K03 V018-K02 V018-K03 V019-K02 V019-K03 V020-K02',
     'No exige cinco frases literales en cada titular. Seis meses es un horizonte ilustrativo del marco, no una garantía. No inventar consecuencias ni miedo para forzar la compra.')
rule('C07', 'posicionamiento perfil', 'Siete componentes narrativos',
     'Distinguir personaje, problema, guía, plan, acción, éxito y fracaso evitado. Utilizarlos para comprobar que la ayuda y el recorrido resulten comprensibles.',
     'V017-K01 M007-K01', 'Es un marco narrativo distinto de las cinco frases; no son siete etapas obligatorias del servicio ni una ley de todas las historias.')
rule('P01', 'posicionamiento', 'Cuatro dimensiones del comprador',
     'Documentar quién es (cargo, industria, tamaño y momento profesional cuando sean pertinentes), problema urgente, transformación deseada y freno u objeción. Diferenciar el problema de aquello que impide actuar.',
     'V015-K04 V016-K01 M006-K02 M006-K03', 'Cuantificar solo con base real. Los 90 días concretan lo que desea el cliente; no fijan la duración del servicio.')
rule('P02', 'posicionamiento', 'Persona, situación y consecuencia',
     'Pasar de una categoría de mercado a la persona que vive una situación concreta y su consecuencia. Identificar el detonante de búsqueda de ayuda y la urgencia real.',
     'V014-K03 V015-K02 M005-K03', 'No copiar el millón de dólares, dos semanas o edades de los ejemplos como filtros universales. No fabricar urgencia.')
rule('P03', 'posicionamiento', 'Puente hacia la mejoría',
     'Relacionar estado actual, dolor y sus causas con la ayuda que se puede prestar, el estado deseado y el beneficio que importa al comprador. Separar el método del resultado vivido por el cliente.',
     'V015-K03 V019-K03 M006-K01 M008-K01', 'La metáfora de puente corto y confiable no autoriza a prometer ser el más rápido ni a garantizar resultados.')
rule('P04', 'posicionamiento', 'Priorizar sin imponer un único comprador',
     'Elegir qué audiencias merecen prioridad y explicar su relación con ofertas distintas dentro de una especialidad común. Distinguir, cuando aplique, aprender a ejecutar frente a delegar.',
     'V022-K01 V022-K02 V022-K03', 'Máximo dos se propone para una tarea y después se habla de priorizar dos o tres: no establecer un máximo universal ni copiar los segmentos de Daniela.')
rule('P05', 'posicionamiento', 'Comprobar la definición',
     'Describir su semana en dos oraciones, nombrar cuándo buscaría ayuda y su objeción para contratar hoy; solicitar reconocimiento de esa descripción por alguien con conocimiento real del cliente.',
     'V020-K03 M007-K04', 'La cuarta prueba se expresa en clase como reconocimiento en la sala. Un acuerdo entre lectores simulados puede detectar ambigüedad, pero no acredita validación real de mercado.')
rule('P06', 'posicionamiento', 'Investigar sin delegar el criterio a una herramienta',
     'Usar preguntas reales, conversaciones y antecedentes de captación como insumos. AnswerThePublic, Value Proposition Canvas y Make My Persona se mencionan como apoyos opcionales para preguntas, valor y contexto.',
     'V013-K04 V014-K01 V016-K03 V020-K05 V021-K01', 'La clase no aporta un tutorial completo, precios vigentes ni resultados verificados para el cliente. Un avatar generado por IA es una hipótesis.')
rule('F01', 'perfil', 'Perfil como escaparate completo',
     'Revisar qué entiende un visitante nuevo sobre destinatario, ayuda y credibilidad. Coordinar titular, acerca de, experiencia, destacados y demás secciones bajo el posicionamiento recibido.',
     'V005-K03 V005-K04 V010-K02', 'La clase 01 aporta criterios estratégicos; no acredita optimización técnica completa de foto, banner o secciones. Completar esa base con la clase 02 antes de darla por terminada.')
rule('F02', 'perfil', 'Titular concreto y comprensible',
     'Revisar si el titular deja reconocer una persona o contexto, su problema o resultado y una ayuda pertinente. Cuestionar términos amplios como empresas, líderes, resultados o transformación digital y precisar lo relevante al caso.',
     'V021-K02 V021-K03 V023-K03 V023-K04 M008-K04', 'No exigir país, edad, cargo y sector en toda frase. No basta con añadir etiquetas si continúa sin entenderse la necesidad.')
rule('F03', 'perfil', 'Simplicidad con voz propia',
     'Proponer redacciones claras y directas, elegir un foco y eliminar enumeraciones que lo diluyen. Conservar la voz del profesional: ayudo, trabajo con u otra formulación pueden funcionar.',
     'V018-K02 V024-K01 V024-K06', 'No prohibir comas ni imponer ayudo. Brevedad no equivale a vaguedad; los ejemplos finales son mejoras relativas, no fórmulas perfectas.')
rule('F04', 'perfil', 'Acerca de y banner deben hacer visible la ayuda',
     'Comenzar por la necesidad reconocible, desarrollar comprensión, ayuda y transformación, y respaldarlas con experiencia pertinente. Si se usa un logo desconocido, acompañarlo de información que explique la especialidad.',
     'V015-K01 V016-K02 V018-K03 V018-K05', 'No inventar textos completos de ejemplos incompletos. Este criterio no sustituye instrucciones gráficas ni una estructura detallada de la clase 02.')
rule('F05', 'perfil', 'Diagnosticar y devolver vacíos',
     'Leer como alguien que no conoce al autor. Identificar huecos, ambigüedades o servicios que el lector podría imaginar por error. Devolver a Posicionamiento las dudas de audiencia u oferta antes de resolverlas por estilo.',
     'V015-K04 V023-K03 V023-K04', 'Los tres segundos ilustran comprensión rápida; no certifican una prueba de usuarios. Una auditoría simulada no demuestra conversiones.')

assigned = {i for r in rules for i in r['unit_ids']}
assert assigned <= UNITS.keys()
admin = set(ids('V002-K01','V002-K02','V002-K03','V002-K04','V011-K02','V011-K03','V013-K02','V023-K02','M001-K01','BATCH-AUDIT-K01','BATCH-AUDIT-K02'))
routes = []
for unit_id, u in UNITS.items():
    linked = [r for r in rules if unit_id in r['unit_ids']]
    status = 'base_operativa' if linked else ('fuera_de_instrucciones' if unit_id in admin else 'consulta_contextual')
    routes.append({'unit_id':unit_id,'title':u['title'],'status':status,
                   'agents':sorted({a for r in linked for a in r['agents']}),
                   'rule_ids':[r['id'] for r in linked],
                   'reason': 'Sustenta criterios asignados.' if linked else ('Dinámica de clase, logística o acceso; no es una tarea para nuestros agentes.' if unit_id in admin else 'Contexto, repetición, testimonio o contenido de otros equipos; consultar con sus límites, no cargar como obligación.')})

write('base-clase-01.json',{
 'schema_version':1,'course':'LinkedIn Sales 30X','session':1,
 'status':'base_preparada_para_configuracion_no_ejecucion',
 'scope':'Solo clase 01; no incluye datos personales del usuario, ni outbound, ni conocimiento supuesto de otras clases.',
 'rules':rules,'routing':routes,
 'shared_knowledge_file':'clase-01-unidades.json',
 'evidence_files':['clase-01-fuentes.json','clase-01-evidencia-visual.json'],
 'evidence_root_relative_to_package':'../../../LinkedIn Sales - Entrega clase 01/01 - Clase 01',
 'authority_order':['Instrucciones explícitas del usuario','Hechos del usuario confirmados y con procedencia','Reglas operativas respaldadas por la clase, con sus límites','Hipótesis identificadas como tales'],
 'interpretation_policy':[
  'Las tareas de los alumnos se convierten en resultados de trabajo útiles; eliminar plazos del curso, gestos, cámaras, horarios y entregas a docentes.',
  'Mantener separados conocimiento del curso, datos del usuario, hipótesis de audiencia y decisiones aprobadas.',
  'Los ejemplos ajenos nunca se convierten en hechos del usuario, promesas propias ni nichos ya elegidos.',
  'Los testimonios, cifras, funcionamiento del algoritmo, descubrimiento por IA y políticas de plataforma no son hechos actuales verificados por este paquete.',
  'No reabrir detalles administrativos como bloqueos. Las incertidumbres de citas se conservan en evidencia y solo se elevan si afectan una decisión.',
  'Cada recomendación debe citar regla y unidad; si hace falta una fuente externa, identificarla como externa y verificarla antes de usarla.',
  'Las propuestas y revisiones de un agente no equivalen a aprobación humana ni a validación real de demanda.'
 ],
 'documented_limits':[
  'La revisión histórica pasó controles estructurales y una muestra semántica; no certificó escucha integral ni revisión humana.',
  'En qt00111 hay un referente no recuperado; no se necesita para los criterios asignados.',
  'Conservar diferencias CEO/COO, tres sesiones/tres semanas y cronología de seguidores como variantes de fuente; no hacerlas reglas.',
  'No atribuir a la clase 01 el desarrollo completo del barrio ni las técnicas de optimización del perfil de la clase 02.'
 ]})

# Una copia común conserva TODOS los campos de la extracción y su trazabilidad.
write('clase-01-unidades.json', DATA)
write('clase-01-fuentes.json', json.loads((ORIGIN/'quality/sources.json').read_text()))
write('clase-01-evidencia-visual.json', json.loads((ORIGIN/'quality/visual/evidence.json').read_text()))

common = {
 'status':'diseño_con_conocimiento_asignado_no_ejecutable',
 'knowledge':'base-clase-01.json', 'memory':'memoria-compartida.json',
 'load_policy':'Leer reglas comunes y propias; recuperar unidades y evidencia por ID cuando la tarea lo requiera. No cargar todo el curso en cada petición.',
 'design_origin':'Responsabilidades y flujo diseñados para este proyecto; las reglas pedagógicas tienen citas propias.',
 'permissions':{'publish_to_linkedin':False,'send_messages':False,'paid_requests':False,'modify_confirmed_user_facts_without_approval':False},
 'missing_information':'Preguntar solo lo que afecte la decisión actual. No completar huecos con estereotipos ni atribuir al usuario ejemplos del curso.',
 'output_provenance':'Cada salida debe indicar hechos usados, hipótesis, unidades de apoyo, vacíos y decisiones que requieren aprobación.'
}
pos = dict(common, id='posicionamiento', name='Posicionamiento', ui_agent='strategy:0',
 mission='Construir una elección de posicionamiento reconocible y defendible para el negocio real del usuario.',
 rule_ids=[r['id'] for r in rules if 'posicionamiento' in r['agents']],
 workflow=[
  'Cuando el usuario lo indique, recoger oferta, capacidades, casos demostrables y antecedentes de clientes. Ahora mantener esos datos pendientes.',
  'Proponer opciones de nicho justificadas y señalar qué falta para elegir; no declarar demanda validada por intuición.',
  'Describir compradores prioritarios con las cuatro dimensiones, detonante, semana y consecuencias; relacionarlos con la oferta real.',
  'Separar comprador de aliados y divulgadores del barrio; dejar el desarrollo posterior de esos roles para su equipo y clases pertinentes.',
  'Formular puente de transformación, asociación profesional y mensaje de cinco funciones. Comprobar coherencia de varias ofertas si existen.',
  'Aplicar las cuatro comprobaciones de definición y presentar decisiones al usuario.',
  'Entregar a Perfil una versión aprobada o explícitamente provisional, con evidencia y preguntas abiertas.'
 ],
 outputs=['opciones_de_posicionamiento','buyer_personas','mapa_inicial_del_barrio','propuesta_de_valor','mensaje_base','brief_para_perfil'],
 done_when=['Las cuatro dimensiones están expresadas con precisión y procedencia.', 'La oferta corresponde a capacidades demostrables; no contiene garantías inventadas.', 'Cada hipótesis y decisión pendiente es visible.', 'Para entregar una base definitiva, el usuario aprobó audiencia y posicionamiento.'],
 owns=['audiencia y propuesta de posicionamiento','coherencia entre ofertas','definición inicial de compradores y comunidad'],
 does_not_own=['decidir el nicho sin el usuario','publicaciones finales','diseño técnico completo del perfil','investigación de mercado no realizada'])
perfil = dict(common, id='perfil', name='Perfil', ui_agent='strategy:1',
 mission='Traducir el posicionamiento en una presentación que un visitante nuevo pueda comprender y evaluar.',
 rule_ids=[r['id'] for r in rules if 'perfil' in r['agents']],
 workflow=[
  'Leer el brief de Posicionamiento y registrar su versión y estado de aprobación.',
  'Cuando el usuario aporte su perfil, diagnosticar claridad de audiencia, problema, transformación y respaldo.',
  'Devolver dudas estratégicas al agente de Posicionamiento; no inventar una oferta para mejorar una frase.',
  'Proponer alternativas de titular y mensaje del Acerca de, explicando qué necesidad y evidencia sostiene cada una.',
  'Indicar el mensaje que deberían apoyar banner, experiencia y destacados sin atribuir a la clase 01 reglas técnicas que no enseña.',
  'Revisar ambigüedad, coherencia, voz propia y promesas; presentar cambios al usuario.',
  'Antes de declarar el perfil completamente optimizado, incorporar el conocimiento pertinente de la clase 02.'
 ],
 outputs=['diagnostico_de_claridad','alternativas_de_titular','estructura_del_mensaje','respaldo_profesional_pertinente','preguntas_para_posicionamiento','pendientes_de_clase_02'],
 done_when=['El visitante puede reconocer a quién se ayuda y qué cambio se ofrece.', 'Titular y mensaje concuerdan con el brief recibido.', 'Experiencia y resultados tienen respaldo del usuario.', 'Se informa el alcance estratégico de clase 01 y lo pendiente para una optimización completa.'],
 owns=['traducción del posicionamiento a mensaje de perfil','claridad y coherencia de la presentación'],
 does_not_own=['cambiar la audiencia unilateralmente','inventar experiencia o testimonios','publicar cambios en LinkedIn','certificar conversión o optimización técnica completa con clase 01'])
write('posicionamiento.json',pos)
write('perfil.json',perfil)

# Plantilla compartida, sin deducir datos personales de conversaciones anteriores.
write('memoria-compartida.json',{
 'schema_version':1,'status':'pendiente_de_informacion_del_usuario',
 'record_format':{'value':None,'status':'pendiente | hipotesis | confirmado | aprobado','source':None,'updated_at':None,'owner':None},
 'user_facts':{'oferta':None,'capacidades':None,'casos_y_resultados':None,'restricciones':None,'voz_y_preferencias':None,'perfil_actual':None},
 'positioning':{'version':0,'status':'pendiente','asociacion_profesional':None,'audiencias_prioritarias':[], 'buyer_personas':[],'barrio':[],'propuesta_de_valor':None,'mensaje_base':None},
 'profile':{'positioning_version':None,'status':'pendiente','diagnostico':None,'titulares':[],'mensaje_acerca_de':None},
 'decisions':[],'open_questions':[],
 'coordination':[
  'Posicionamiento propone cambios de audiencia/oferta; Perfil propone cambios de expresión y devuelve contradicciones.',
  'Ninguno sobrescribe hechos confirmados ni decisiones aprobadas sin registrar el cambio y solicitar aprobación.',
  'Si cambia el posicionamiento aprobado, marcar los borradores del perfil como pendientes de revisión.',
  'La comunidad y el Observatorio podrán aportar evidencia nueva; una conversación o simulación aislada no representa a todo el mercado.'
 ]})

manifest = {
 'session':1,'original_files':{},'package_files':{},
 'learning_units_preserved':len(UNITS), 'operational_units':len(assigned),
 'operational_rules':len(rules),'administrative_or_class_dynamics_excluded':len(admin),
 'review_scope':'Lectura de las unidades relevantes y sus límites, revisión de la evaluación previa y contraste textual de buyer persona, barrio, marcos y matices con transcripción/PDF extraído. No nueva escucha integral ni revisión humana.',
 'api_calls':0,'runtime_connected':False,'user_personalization_started':False
}
for rel in ['quality/aprendizajes.json','quality/sources.json','quality/visual/evidence.json','quality/final-review.json','quality/final-validation.json']:
    path=ORIGIN/rel
    manifest['original_files'][str(path.relative_to(ROOT))]=hashlib.sha256(path.read_bytes()).hexdigest()
for path in sorted(OUT.glob('*.json')):
    if path.name != 'manifest.json':manifest['package_files'][path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
write('manifest.json',manifest)
print(json.dumps({k:manifest[k] for k in ['learning_units_preserved','operational_units','operational_rules','administrative_or_class_dynamics_excluded','api_calls']},ensure_ascii=False))
