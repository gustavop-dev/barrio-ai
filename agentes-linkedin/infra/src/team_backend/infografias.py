"""IMG-INF: versioned agent rule, strict structured content and deterministic Ubuntu renderer.

No image model is used here. The fixed fallback is a reviewed brand card, not an
unverified dynamic infographic. Dynamic designs require a vision verdict downstream.
"""
import hashlib
import io
import math
import re
import zlib
from functools import lru_cache
from html.parser import HTMLParser
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

RESOURCE=Path(__file__).resolve().parent/'recursos'
PAPER='#F7F6F0';INK='#1E1E2B';SOFT='#565972';LINE='#DEDFD4';DEEP='#00715E';ACCENT='#0FF1CE'


def author(member=None):
    """The name drawn at the foot of every slide: the member's (identidad), never a fixed one."""
    from . import identidad
    return identidad.of(member).name


def _signer(name):
    """Who signs a slide: `name` (its caller's member, author(member)). Drawing never reads the database: without one,
    the initial identity's name, the one of always."""
    if name is not None:return name
    from . import identidad
    return identidad.initial_identity().name


class _Text(HTMLParser):
    def __init__(self):super().__init__();self.parts=[]
    def handle_data(self,data):self.parts.append(data)
    def handle_endtag(self,tag):
        if tag in ('p','li','h1','h2','h3','tr','section','pre'):self.parts.append('\n')


@lru_cache(maxsize=1)
def _document():
    raw=(RESOURCE/'infografias.html').read_text(encoding='utf-8')
    parser=_Text();parser.feed(raw)
    return '\n'.join(line.strip() for line in ''.join(parser.parts).splitlines() if line.strip())


EXAMPLE_ROLE=' · Product Engineer'  # the foot of the document's example slides, after the first person's name


def rule(name=None):
    """The rule (recursos/infografias.html). Its examples name the installation's first person: for anyone else they
    carry her `name` (only her name at the foot, which is what render() draws). None or his name: the document as is."""
    text=_document()
    from . import identidad
    first=identidad.initial()['member']['name']
    if name is None or name==first:return text
    return text.replace(first+EXAMPLE_ROLE,name).replace(first,name)


def version():
    """The document's version (pieces and reviews record it): the same for every member."""
    return hashlib.sha256(_document().encode()).hexdigest()


def with_rule(system,name=None):
    return system+'\n\n<regla_infografias version="'+version()+'">\n'+rule(name)+'\n</regla_infografias>'
def obj(**fields):return {'type':'object','additionalProperties':False,'required':list(fields),'properties':fields}
def string():return {'type':'string'}
def array(items):return {'type':'array','items':items}
def enum(*values):return {'type':'string','enum':list(values)}

SOURCE=obj(ref=string(),label=string(),date=string(),estimate={'type':'boolean'})
# The board's six templates, then the formats its «Datos y gráficos» allows that had no template (línea simple, antes y
# después, lista numerada) and the table Gustavo asked for (18/11/2026: «más formatos: tablas, comparaciones, gráficos»).
TEMPLATES=('portada','pasos','barras','numero','cierre','preguntas','tabla','comparacion','linea','lista','cita')
ROW=obj(label=string(),cells=array(string()),focus={'type':'boolean'})
SERIES=obj(name=string(),values=array({'type':'number'}),focus={'type':'boolean'})
SLIDE=obj(template=enum(*TEMPLATES),label=string(),title=string(),subtitle=string(),
          body=string(),number=string(),unit=string(),steps=array(string()),
          bars=array(obj(label=string(),value={'type':'number'},focus={'type':'boolean'})),
          source=SOURCE,alt=string(),highlight=string(),
          columns=array(string()),rows=array(ROW),series=array(SERIES))
# Fields the new templates added: a design stored before them (a ready piece, a cycle's checkpoint) has none, and is the
# same design with them empty (normalize).
NEW_FIELDS=('columns','rows','series')
# The free canvas (lienzo.py, INFOGRAFIA_LIENZO): one HTML+CSS document the code renders and checks. Unused: html ''.
LIENZO=obj(html=string(),title=string(),fondo=enum('papel','tinta'),source=SOURCE,alt=string())
# What the designer answers: data for the templates (TEMPLATE_DESIGN_SCHEMA, the only one while the canvas is off or
# another layout was chosen), or a canvas plus a template design of the same content as its fallback.
TEMPLATE_DESIGN_SCHEMA=obj(slides=array(SLIDE))
CANVAS_DESIGN_SCHEMA=obj(slides=array(SLIDE),lienzo=LIENZO)
# The `image_design` contract (grafo.yaml) accepts both: `lienzo` is optional there, and so are the new templates' fields
# in a slide (a design of before them is the same design with them empty: normalize).
CONTRACT_SLIDE=dict(SLIDE,required=[f for f in SLIDE['required'] if f not in NEW_FIELDS])
DESIGN_SCHEMA={'type':'object','additionalProperties':False,'required':['slides'],
               'properties':{'slides':array(CONTRACT_SLIDE),'lienzo':LIENZO}}
CHOICE_SCHEMA=obj(kind=enum('foto','infografia','carrusel'),reason=string(),
                  photos=array(obj(id=string(),reason=string(),alt=string(),edit=enum('none','light','straighten','crop','distractions'),
                                   edit_reason=string(),instruction=string(),instruction_kind=enum('none','original','crop','edit','unsafe'))))
# The single image's layout editor_visual chooses (point 3 of 18/11/2026): a template by the post's content, or the free
# canvas while INFOGRAFIA_LIENZO is on. `cierre` only closes a carousel. '' : photo, carousel or no preference.
LAYOUTS=('numero','barras','linea','tabla','comparacion','pasos','lista','preguntas','portada')
ALL_LAYOUTS=('',*LAYOUTS,'lienzo')


def choice_schema(canvas=False):
    """editor_visual's answer: the IMG choice (CHOICE_SCHEMA, the director's brief keeps that one) plus the single
    image's `layout` and the other layouts that would also fit (`alternatives`, best first)."""
    layouts=('',*LAYOUTS,*(('lienzo',) if canvas else ()))
    return obj(**CHOICE_SCHEMA['properties'],layout=enum(*layouts),alternatives=array(enum(*layouts[1:])))


# The `visual_proposal` contract's choice (grafo.yaml): CHOICE_SCHEMA's required fields, layout and alternatives optional
# (a fallback proposal keeps a brief's choice, which has none).
CHOICE_CONTRACT=dict(CHOICE_SCHEMA,properties=dict(CHOICE_SCHEMA['properties'],layout=enum(*ALL_LAYOUTS),
                                                   alternatives=array(enum(*ALL_LAYOUTS[1:]))))


def check_choice(choice):
    """An IMG choice, with or without editor_visual's layout fields (a brief of before them has none)."""
    if not isinstance(choice,dict):raise ValueError('respuesta: tipo inválido')
    schema_check({k:v for k,v in choice.items() if k not in ('layout','alternatives')},CHOICE_SCHEMA)
    if 'layout' in choice:schema_check(choice['layout'],enum(*ALL_LAYOUTS),'respuesta.layout')
    if 'alternatives' in choice:schema_check(choice['alternatives'],array(enum(*ALL_LAYOUTS[1:])),'respuesta.alternatives')
    return choice


def layout_of(kind,spec):
    """What an image looked like, for not repeating it: the single image's template ('lienzo' for the canvas), or its
    kind (foto, carrusel, tarjeta)."""
    spec=spec if isinstance(spec,dict) else {}
    if kind!='infografia':return kind or ''
    if ((spec.get('lienzo') or {}).get('html') or '').strip():return 'lienzo'
    slides=spec.get('slides') or [{}]
    return str((slides[0] or {}).get('template') or '')


def normalize(design):
    """The design with the new templates' fields, empty where a design of before them has none."""
    if not isinstance(design,dict) or not isinstance(design.get('slides'),list):return design
    slides=[dict({f:[] for f in NEW_FIELDS},**s) if isinstance(s,dict) else s for s in design['slides']]
    return dict(design,slides=slides)


def schema_check(value,schema,path='respuesta'):
    """Validate model output locally too; JSON mode is not a trust boundary."""
    kind=schema['type']
    ok={'object':isinstance(value,dict),'array':isinstance(value,list),'string':isinstance(value,str),
        'boolean':type(value) is bool,'number':type(value) in (int,float) and math.isfinite(value) if type(value) in (int,float) else False}
    if not ok[kind]:raise ValueError(f'{path}: tipo inválido')
    if 'enum' in schema and value not in schema['enum']:raise ValueError(f'{path}: opción inválida')
    if kind=='object':
        if set(value)!=set(schema['properties']):raise ValueError(f'{path}: campos inválidos')
        for key,item in value.items():schema_check(item,schema['properties'][key],path+'.'+key)
    if kind=='array':
        for item in value:schema_check(item,schema['items'],path+'[]')


# Capitals only in labels, but an acronym is how the reader knows the word: «AI agents» or «your MVP» is not shouting.
# Plurals («APIs», «MVPs») and mixed forms («B2B», «SaaS», «iOS») never matched the rule; these are the all-capital ones.
ACRONYMS=frozenset(('AI ML LLM LLMS GPT NLP RAG API SDK UI UX QA MVP POC PMF GTM ROI KPI OKR ARR MRR CAC LTV NPS CRM ERP SEO '
                    'SQL AWS GCP CI CD IT IP OS PDF CSV JSON HTTP SSO SLA SOC GDPR HIPAA CEO CTO CFO COO CPO VP PM HR VC YC '
                    'US USA UK EU LATAM FAQ DM').split())
SHOUT=re.compile(r'\b[A-Z]{2,}\b')


def shouting(text):
    """The all-capital words of `text` that are not a known acronym."""
    return [word for word in SHOUT.findall(text) if word not in ACRONYMS]


def acronym(word):
    """A known acronym, alone or in plural («AI», «APIs»), with the punctuation around it."""
    core=word.strip('.,:;!?¿¡«»"\'()')
    return core in ACRONYMS or (core.endswith('s') and core[:-1] in ACRONYMS)


def cover_case_ok(title):
    """A cover title goes in lower case after its first letter; a known acronym keeps its capitals."""
    words=title.split()
    return all(acronym(w) or (w[1:] if i==0 else w)==(w[1:] if i==0 else w).lower() for i,w in enumerate(words))


# «preguntas»: questions for the audience in `steps`, as bullets (COUNTS); the text after the «?» is an optional short
# answer. A list mark at the start of an item is the template's to draw: fix() removes it.
LIST_MARK=re.compile(r'^\s*(?:\d+\s*[.):-]|[-•*·]|[A-Za-z]\))\s*')


def question_parts(item):
    """(question, answer) of a «preguntas» item: up to the first «?», then the optional short answer."""
    question,mark,answer=item.partition('?')
    return (question.strip()+mark,answer.strip(' -–—:\n'))


def source_refs(public,sources):
    return {str(x['key']) for x in public if 'key' in x}|{str(x['id']) for x in sources if 'id' in x}


EMOJI=re.compile('[\U0001F000-\U0010FFFF☀-➿️‍]')
# A figure: a quantity or a date written with digits («70%», «3x», «$2M», «2026», «10-15»), never a name that carries a
# digit («GPT-5», «B2B», «Q3», «3D»). Only figures need a source (IMG-INF-04).
FIGURE=re.compile(r'[~≈<>+±-]?[$€£]?\d[\d.,:/–-]*(?:%|[xX×]|[kKmMbB]|bn|pp|s|h|ms|min)?')


def figures(text):
    """The figures of `text`, as written."""
    out=[]
    for token in str(text).split():
        core=token.strip('.,;:!?¿¡«»"\'()[]“”‘’')
        if core and FIGURE.fullmatch(core):out.append(core)
    return out


def clean_text(texts,alt=None):
    """What still makes public words unusable once fix() mended them: an emoji (the font cannot draw it), and an alt too
    short to carry the image to someone who cannot see it. Hashtags, «!!» and capitals are style: fix() mends them."""
    for text in [*texts,*([alt] if alt is not None else [])]:
        if EMOJI.search(text):raise ValueError('Sin emojis: la fuente no los dibuja')
    if alt is not None and not 8<=len(alt.strip())<=1500:raise ValueError('Falta texto alternativo descriptivo')


def sourced(texts,source,public,sources,template='',always=False):
    """IMG-INF-04: a figure needs a public, identifiable source with its date (public_facts or the piece's sources).
    `texts`: the public words, without the source's own label and date; `always`: the template shows a figure by itself."""
    found=figures(' '.join(texts))
    if always or found or source['ref']:
        if source['ref'] not in source_refs(public,sources) or not source['label'] or not source['date']:
            # Say what made it a figure, so a correction can fix it instead of repeating the same design.
            why=(f'la plantilla {template} siempre muestra un dato' if always
                 else 'hay cifras en el texto: '+', '.join(f'«{d}»' for d in found[:3]) if found else 'cita una fuente')
            raise ValueError(f'Dato sin fuente pública identificable y fecha ({why}). Sin una fuente de public_facts o '
                             'sources, quita las cifras; para preguntas a la audiencia usa la plantilla preguntas, sin numerarlas')
    if source['estimate'] and 'estimate' not in source['label'].lower():raise ValueError('La estimación debe decir estimate')


# Words per slide: the board's 30 (carousel) and 40 (single image) are a style target, not a wall. fix() trims secondary
# text over these limits; legibility itself is the renderer's (28 px floor, nothing overflows the grid).
WORDS={'tabla':70,'comparacion':60,'lista':60,'pasos':55,'preguntas':55,'cita':45}
TITLE_WORDS=8  # the board's headline; a longer one is a note, and up to TITLE_MAX it still renders legibly
TITLE_MAX={'cita':24}
FACTUAL=('numero','barras','linea')  # templates that always show a figure
STEPS=('pasos','preguntas','lista')
# (minimum, maximum): under the minimum the template has nothing to draw (a hard rule); over the maximum, fix() keeps the
# first ones (a subset of true items is still true).
COUNTS={'pasos':(2,6),'lista':(2,6),'preguntas':(1,4),'barras':(1,5)}
TABLE_COLUMNS=(2,4);TABLE_ROWS=(1,5);COMPARISON_ROWS=(1,4);LINE_POINTS=(2,12)
DETAIL=' — '  # a list item's short detail goes after it, drawn under it in grey
CALL=re.compile(r'follow me|subscribe|sígueme',re.I)


def _words(text):return len(text.split())


def _texts(slide):
    """Every public word of a slide but its source's label and date."""
    return [slide['title'],slide['subtitle'],slide['body'],slide['number'],slide['unit'],*slide['steps'],
            *[b['label'] for b in slide['bars']],*slide['columns'],*[r['label'] for r in slide['rows']],
            *[c for r in slide['rows'] for c in r['cells']],*[s['name'] for s in slide['series']]]


def _count(slide):
    return sum(_words(t) for t in _texts(slide))+_words(slide['label'])


def _limit(slide,carousel):
    return WORDS.get(slide['template'],30 if carousel else 40)


def _tidy(text):
    """Style mended in place: no emojis, no «#» before a word, a single «!», no all-capital words but known acronyms."""
    text=EMOJI.sub('',text).replace('#','')
    text=re.sub(r'!{2,}','!',text)
    text=SHOUT.sub(lambda m:m[0] if m[0] in ACRONYMS else m[0].lower(),text)
    return ' '.join(text.split())


def _structure(slide,carousel):
    """The hard rules of one slide (structure a template needs to draw, legibility, honesty of a chart), [] when it holds."""
    template=slide['template'];problems=[]
    title_max=TITLE_MAX.get(template,14)
    if not slide['title'].strip() or _words(slide['title'])>title_max:problems.append(f'Titular: de 1 a {title_max} palabras')
    if template in COUNTS and template!='barras':
        low,high=COUNTS[template]
        if not low<=len(slide['steps'])<=high:problems.append(f'{template}: de {low} a {high} elementos en steps')
    if template=='preguntas' and any(not question_parts(i)[0].endswith('?') for i in slide['steps']):
        problems.append('Cada elemento de preguntas empieza por una pregunta que termina en «?»')
    if template=='barras':
        low,high=COUNTS['barras']
        if not low<=len(slide['bars'])<=high:problems.append(f'De {low} a {high} barras')
        elif any(b['value']<0 for b in slide['bars']) or max(b['value'] for b in slide['bars'])<=0:
            problems.append('Barras desde cero, valores positivos')
    if template=='numero' and (not re.search(r'\d',slide['number']) or len(slide['number'])>7):
        problems.append('Cifra protagonista corta (hasta 7 caracteres), con su unidad al lado')
    columns,rows,series=slide['columns'],slide['rows'],slide['series']
    if template=='tabla':
        low,high=TABLE_COLUMNS
        if not low<=len(columns)<=high or any(not h.strip() for h in columns):problems.append(f'Tabla de {low} a {high} columnas con encabezado')
        low,high=TABLE_ROWS
        if not low<=len(rows)<=high:problems.append(f'Tabla de {low} a {high} filas')
        if any(len(r['cells'])!=len(columns)-1 or not r['label'].strip() for r in rows):
            problems.append('Cada fila: label (la primera columna) y una celda por cada columna siguiente')
    elif template=='comparacion':
        if len(columns)!=2 or any(not h.strip() for h in columns):problems.append('Comparación: dos encabezados')
        low,high=COMPARISON_ROWS
        if not low<=len(rows)<=high:problems.append(f'Comparación de {low} a {high} filas')
        if any(len(r['cells'])!=2 or not all(c.strip() for c in r['cells']) for r in rows):
            problems.append('Cada fila compara dos textos: izquierda y derecha')
    elif template=='linea':
        low,high=LINE_POINTS
        if not 1<=len(series)<=2:problems.append('Línea simple: una o dos series')
        elif not low<=len(columns)<=high or any(len(s['values'])!=len(columns) for s in series):
            problems.append(f'Línea: de {low} a {high} puntos, un valor por cada etiqueta de columns en cada serie')
        elif any(v<0 for s in series for v in s['values']) or max(v for s in series for v in s['values'])<=0:
            problems.append('Línea desde cero, valores positivos')
    return problems


def _drop_figures(slide,refs,notes,where):
    """IMG-INF-04 mended without inventing anything: an unknown source is not cited, and the words that carry a figure
    without a source leave the slide. False when the figure IS the slide (its template, its headline or a table's
    headers): then the slide cannot stay."""
    source=slide['source']
    if source['ref'] and (source['ref'] not in refs or not source['label'] or not source['date']):
        slide['source']={'ref':'','label':'','date':'','estimate':False};notes.append(f'{where}: fuente sin respaldo retirada')
    if slide['source']['ref'] or not figures(' '.join(_texts(slide))):return True
    if slide['template'] in FACTUAL or figures(slide['title']) or figures(' '.join(slide['columns'])):return False
    for field in ('subtitle','body','label'):
        if figures(slide[field]):slide[field]='';notes.append(f'{where}: se quitó una cifra sin fuente ({field})')
    kept=[s for s in slide['steps'] if not figures(s)]
    if len(kept)!=len(slide['steps']):slide['steps']=kept;notes.append(f'{where}: se quitaron puntos con cifras sin fuente')
    kept=[r for r in slide['rows'] if not figures(' '.join([r['label'],*r['cells']]))]
    if len(kept)!=len(slide['rows']):slide['rows']=kept;notes.append(f'{where}: se quitaron filas con cifras sin fuente')
    return not figures(' '.join(_texts(slide)))


def _trim(slide,carousel,notes,where):
    """Words over the slide's style limit: secondary text goes first (body, subtitle, then the grey details of a list or
    the short answers of the questions). What is left is the designer's own words, never rewritten."""
    limit=_limit(slide,carousel)
    for field in ('body','subtitle'):
        if _count(slide)>limit and slide[field]:slide[field]='';notes.append(f'{where}: se quitó {field} por largo')
    if _count(slide)>limit and slide['template']=='lista' and any(DETAIL in s for s in slide['steps']):
        slide['steps']=[s.partition(DETAIL)[0].strip() for s in slide['steps']];notes.append(f'{where}: sin detalles por largo')
    if _count(slide)>limit and slide['template']=='preguntas' and any(question_parts(s)[1] for s in slide['steps']):
        slide['steps']=[question_parts(s)[0] for s in slide['steps']];notes.append(f'{where}: sin respuestas cortas por largo')
    # A list or a set of questions is still true with fewer items; the steps of a process are not: they stay whole.
    while _count(slide)>limit and slide['template'] in ('lista','preguntas') and len(slide['steps'])>COUNTS[slide['template']][0]:
        slide['steps']=slide['steps'][:-1];notes.append(f'{where}: un elemento menos por largo')
    if _count(slide)>limit:notes.append(f'{where}: {_count(slide)} palabras (la guía pide {limit}); decide la legibilidad')


def shorten(slide):
    """A copy of `slide` without its secondary text (body, subtitle, a list's details, the questions' short answers,
    a list's or the questions' last items down to their minimum): what imagenes draws once more when it overflowed."""
    import copy
    slide=copy.deepcopy(slide);slide['body']='';slide['subtitle']=''
    if slide['template']=='lista':slide['steps']=[s.partition(DETAIL)[0].strip() for s in slide['steps']]
    if slide['template']=='preguntas':slide['steps']=[question_parts(s)[0] for s in slide['steps']]
    if slide['template'] in ('lista','preguntas'):slide['steps']=slide['steps'][:max(COUNTS[slide['template']][0],3)]
    return slide


def _mend(slide,carousel,refs,notes,where):
    """Style of one slide, mended in place: never a reason to discard it. False when its figures cannot stay."""
    template=slide['template']
    for field in ('title','subtitle','body','number','unit'):slide[field]=_tidy(slide[field])
    label=re.sub(r'[^\w\s&/·.,:-]','',_tidy(slide['label']))
    if label!=slide['label']:slide['label']=label
    slide['steps']=[_tidy(LIST_MARK.sub('',s)) for s in slide['steps'] if _tidy(LIST_MARK.sub('',s))]
    slide['columns']=[_tidy(c) for c in slide['columns']]
    for row in slide['rows']:row['label']=_tidy(row['label']);row['cells']=[_tidy(c) for c in row['cells']]
    for bar in slide['bars']:bar['label']=_tidy(bar['label'])
    for line in slide['series']:line['name']=_tidy(line['name'])
    # What a template does not draw is not shown: it leaves the design instead of failing it.
    stray=[]
    if template not in STEPS and slide['steps']:slide['steps']=[];stray.append('steps')
    if template!='barras' and slide['bars']:slide['bars']=[];stray.append('bars')
    if template!='numero' and slide['number']:slide['number']='';stray.append('number')
    if template not in ('numero','linea') and slide['unit']:slide['unit']='';stray.append('unit')
    if template not in ('tabla','comparacion') and slide['rows']:slide['rows']=[];stray.append('rows')
    if template not in ('tabla','comparacion','linea') and slide['columns']:slide['columns']=[];stray.append('columns')
    if template!='linea' and slide['series']:slide['series']=[];stray.append('series')
    if stray:notes.append(f'{where}: campos que la plantilla {template} no dibuja: '+', '.join(stray))
    for field in ('title','subtitle','body'):
        if field!='title' and CALL.search(slide[field]):slide[field]='';notes.append(f'{where}: sin «sígueme»')
    if template=='preguntas':
        kept=[s for s in slide['steps'] if question_parts(s)[0].endswith('?')]
        if kept and len(kept)!=len(slide['steps']):slide['steps']=kept;notes.append(f'{where}: se quitaron elementos que no eran preguntas')
    if template in COUNTS and template!='barras' and len(slide['steps'])>COUNTS[template][1]:
        slide['steps']=slide['steps'][:COUNTS[template][1]];notes.append(f'{where}: solo los primeros {COUNTS[template][1]}')
    if template=='barras' and slide['bars']:
        if len(slide['bars'])>COUNTS['barras'][1]:
            focus=[b for b in slide['bars'] if b['focus']][:1]
            rest=sorted((b for b in slide['bars'] if b not in focus),key=lambda b:-b['value'])
            slide['bars']=focus+rest[:COUNTS['barras'][1]-len(focus)];notes.append(f'{where}: solo las {COUNTS["barras"][1]} barras mayores')
        if sum(b['focus'] for b in slide['bars'])!=1:
            top=max(slide['bars'],key=lambda b:b['value'])
            for bar in slide['bars']:bar['focus']=bar is top
            notes.append(f'{where}: foco en la barra mayor')
        for bar in slide['bars']:bar['value']=round(bar['value'],1) if bar['value']!=round(bar['value']) else bar['value']
    if template=='linea' and slide['series']:
        if sum(s['focus'] for s in slide['series'])!=1:
            for i,line in enumerate(slide['series']):line['focus']=i==0
            notes.append(f'{where}: foco en la primera serie')
        for line in slide['series']:line['values']=[round(v,1) if v!=round(v) else v for v in line['values']]
    if template=='numero':
        match=re.fullmatch(r'([$€£]?[\d.,]+)\s*(%|x|×)',slide['number'])
        if match and not slide['unit']:slide['number'],slide['unit']=match[1],match[2];notes.append(f'{where}: unidad separada de la cifra')
    if template=='tabla':
        high=TABLE_COLUMNS[1]
        if len(slide['columns'])>high:
            slide['columns']=slide['columns'][:high]
            for row in slide['rows']:row['cells']=row['cells'][:high-1]
            notes.append(f'{where}: solo las primeras {high} columnas')
        if sum(r['focus'] for r in slide['rows'])>1:
            first=next(r for r in slide['rows'] if r['focus'])
            for row in slide['rows']:row['focus']=row is first
        if len(slide['rows'])>TABLE_ROWS[1]:slide['rows']=slide['rows'][:TABLE_ROWS[1]];notes.append(f'{where}: solo las primeras filas')
    if template=='comparacion':
        for row in slide['rows']:row['focus']=False
        if slide['highlight'] not in ('',*slide['columns']):slide['highlight']=''
        if len(slide['rows'])>COMPARISON_ROWS[1]:slide['rows']=slide['rows'][:COMPARISON_ROWS[1]];notes.append(f'{where}: solo las primeras filas')
    if template=='portada':
        if not cover_case_ok(slide['title']):notes.append(f'{where}: la portada va en minúsculas salvo la primera letra')
        if slide['highlight'] not in slide['title'].split() or len(slide['highlight'].split())!=1:slide['highlight']=''
    elif template!='comparacion':slide['highlight']=''
    if _words(slide['title'])>TITLE_WORDS and template!='cita':notes.append(f'{where}: titular de {_words(slide["title"])} palabras (la guía pide {TITLE_WORDS})')
    source=slide['source']
    if source['estimate'] and 'estimate' not in source['label'].lower():source['label']=(source['label']+' (estimate)').strip()
    ok=_drop_figures(slide,refs,notes,where)
    _trim(slide,carousel,notes,where)
    alt=' '.join(slide['alt'].split())
    if len(alt)<8:
        slide['alt']=' '.join(x for x in (slide['title'],slide['subtitle']) if x).strip()[:1500] or 'Infographic'
        notes.append(f'{where}: alt escrito desde el titular')
    elif EMOJI.search(alt):slide['alt']=_tidy(alt)
    return ok


def fix(design,kind,public=(),sources=()):
    """(design, notes): the designer's answer with its style mended by code (IMG-INF, 19/11/2026: «que no bloquee
    todo»). Nothing here invents or rewrites a claim: it removes (a figure without a source, secondary text over the
    word guide, what a template does not draw, decoration) and normalizes. A carousel loses a slide that cannot stay
    (its figure has no source, or it lacks what its template needs) while two remain. validate() then checks only
    what protects the truth and the legibility. A design that is not even the schema goes back unchanged."""
    import copy
    design=normalize(copy.deepcopy(design));notes=[]
    try:schema_check(design,CANVAS_DESIGN_SCHEMA if isinstance(design,dict) and 'lienzo' in design else TEMPLATE_DESIGN_SCHEMA)
    except ValueError:return design,notes
    carousel=kind=='carrusel';refs=source_refs(public,sources);slides=design['slides']
    if not carousel and len(slides)>1:slides[1:]=[];notes.append('Imagen única: solo la primera lámina')
    if carousel and len(slides)>8:slides[7:-1]=[];notes.append('Carrusel: como mucho 8 láminas')
    kept=[]
    for n,slide in enumerate(slides,1):
        where=f'Lámina {n} ({slide["template"]})' if carousel else f'Lámina ({slide["template"]})'
        ok=_mend(slide,carousel,refs,notes,where)
        problems=_structure(slide,carousel)
        if carousel and (not ok or problems):
            notes.append(f'{where}: fuera del carrusel ('+('cifra sin fuente' if not ok else '; '.join(problems))+')')
            continue
        kept.append(slide)
    if carousel and len(kept)>=2:design['slides']=kept
    if carousel and design['slides']:
        if design['slides'][0]['template']!='portada':notes.append('El carrusel suele abrir con portada')
        last=design['slides'][-1]
        if last['template']=='cierre' and not any('?' in last[f] for f in ('title','subtitle','body')):
            notes.append('El cierre suele devolver la pregunta del post')
    return design,notes


def validate(design,kind,public=(),sources=()):
    """The design, normalized (normalize), when what protects the truth and the legibility holds; ValueError with the
    reasons otherwise (every slide's, so one correction can fix them all). Style is fix()'s: call it first. A design may
    carry the free canvas (`lienzo`): its document and its words pass lienzo.validate, with the same truth rules."""
    design=normalize(design)
    schema_check(design,CANVAS_DESIGN_SCHEMA if isinstance(design,dict) and 'lienzo' in design else TEMPLATE_DESIGN_SCHEMA)
    slides=design['slides'];carousel=kind=='carrusel'
    if (design.get('lienzo') or {}).get('html','').strip():
        if carousel:raise ValueError('El lienzo libre es de imagen única')
        from . import lienzo
        lienzo.validate(design['lienzo'],public,sources)
        if not slides:return design  # the canvas that went out, kept alone
    if not ((2<=len(slides)<=8) if carousel else len(slides)==1):raise ValueError('Número de láminas inválido')
    problems=[]
    for n,slide in enumerate(slides,1):
        where=f'Lámina {n} ({slide["template"]})' if carousel else f'Lámina ({slide["template"]})'
        try:
            found=_structure(slide,carousel)
            if found:raise ValueError('; '.join(found))
            clean_text(_texts(slide)+[slide['label'],slide['source']['label'],slide['source']['date']],slide['alt'])
            sourced(_texts(slide),slide['source'],public,sources,slide['template'],always=slide['template'] in FACTUAL)
        except ValueError as exc:problems.append(f'{where}: {exc}')
    if problems:raise ValueError('; '.join(problems))
    return design


# The content card (imagenes.fallback, 19/11/2026: «no un relleno genérico»): when no design passes, the post's own key
# line, and its question when it asks one, on the «cita» template. Its words are the post's, verbatim and verified with
# it; no figure (so no source is missing) and nothing the post does not already say.
CTA=re.compile(r'\b(?:follow|subscribe|repost|share this|dm me|link in|comment below|like if)\b',re.I)


def key_lines(post):
    """(statement, question) from the post: its first sentence that can stand alone on a card (4 to 24 words, no figure,
    link, mention, hashtag or call to follow) and its last question; '' when it has none."""
    text=re.sub(r'https?://\S+|www\.\S+','',post or '')
    lines=[]
    for line in text.splitlines():
        for sentence in re.split(r'(?<=[.!?])\s+',line.strip()):
            sentence=_tidy(sentence.strip(' -–—•*·>"“”'))
            if not 4<=_words(sentence)<=TITLE_MAX['cita'] or figures(sentence) or '@' in sentence or CTA.search(sentence):continue
            lines.append(sentence)
    statement=next((s for s in lines if not s.endswith('?')),'')
    question=next((s for s in reversed(lines) if s.endswith('?') and s!=statement),'')
    return statement,question


def content_card(post):
    """The «cita» slide of the post's key line (and its question), or None when the post has no line a card can carry."""
    statement,question=key_lines(post)
    title=statement or question
    if not title:return None
    subtitle=question if statement and question and _words(title)+_words(question)<=WORDS['cita'] else ''
    alt=f'Card with a key idea of the post: “{title}”'+(f' It asks: “{subtitle}”' if subtitle else '')
    return {'template':'cita','label':'','title':title,'subtitle':subtitle,'body':'','number':'','unit':'','steps':[],
            'bars':[],'source':{'ref':'','label':'','date':'','estimate':False},'alt':alt,'highlight':'',
            'columns':[],'rows':[],'series':[]}


@lru_cache(maxsize=24)
def font(size):
    face=ImageFont.truetype(str(RESOURCE/'fonts'/'Ubuntu.ttf'),size)
    # The bundled variable font has explicit regular weight, independent of host fonts.
    axes=face.get_variation_axes()
    face.set_variation_by_axes([400 if a['name']==b'Weight' else a['default'] for a in axes])
    return face


def contrast(a,b):
    def lum(color):
        rgb=[int(color[i:i+2],16)/255 for i in (1,3,5)]
        return sum(w*(v/12.92 if v<=0.04045 else ((v+0.055)/1.055)**2.4) for w,v in zip((.2126,.7152,.0722),rgb))
    x,y=sorted((lum(a),lum(b)));return (y+.05)/(x+.05)


def _columns(count,first_share):
    """(x, width) of `count` columns over the 888 px measure with 24 px gutters; with three or more, the first (a
    table's row labels) takes `first_share` of it and the rest share what is left."""
    inner=888-24*(count-1)
    first=round(inner*first_share) if count>2 else inner/count
    widths=[first]+[(inner-first)/(count-1)]*(count-1)
    out=[];x=96
    for width in widths:out.append((x,width));x+=width+24
    return out


def _rule(draw,occupied,y,color,x1=96,x2=984,width=2):
    """A structural line (a table's rules, a chart's zero line); its colour is the board's line or soft ink."""
    draw.rectangle((x1,y,x2,y+width-1),fill=color);occupied.append((x1,y,x2,y+width))


def _table(slide,y,text,draw,occupied,fg,accent,muted):
    """tabla: the headers in grey over a soft rule, one row per line with a light rule under it; the focused row (one at
    most) in the accent. The first column is the row's label."""
    columns=_columns(len(slide['columns']),.4)
    y=max(text(head,x,y,30,40,width=w,color=muted) for (x,w),head in zip(columns,slide['columns']))+12
    _rule(draw,occupied,y,SOFT);y+=16
    for row in slide['rows']:
        color=accent if row['focus'] else fg
        y=max(text(cell,x,y,32,44,width=w,color=color) for (x,w),cell in zip(columns,[row['label'],*row['cells']]))+12
        _rule(draw,occupied,y,LINE);y+=16
    return y+16


def _comparison(slide,y,text,draw,occupied,fg,accent,muted):
    """comparacion: two columns side by side (before and after, or two options), each under its heading and a rule. The
    highlighted heading carries the accent (one per piece); position and the heading say which side is which."""
    columns=_columns(2,.5);heads=slide['columns']
    for (x,w),head in zip(columns,heads):
        draw.rectangle((x,y,x+w,y+5),fill=accent if head==slide['highlight'] else LINE);occupied.append((x,y,x+w,y+6))
    y=max(text(head,x,y+24,36,48,width=w,color=accent if head==slide['highlight'] else fg) for (x,w),head in zip(columns,heads))+16
    for row in slide['rows']:
        if row['label']:y=text(row['label'],96,y,28,36,color=muted)+4
        y=max(text(cell,x,y,32,44,width=w) for (x,w),cell in zip(columns,row['cells']))+24
    return y


def _line_chart(slide,y,carousel,text,draw,occupied,fg,accent,muted):
    """linea: one or two series over the same points, from zero, without grid or legend. Each line is labelled at its end
    (name and last value) and the focus line also at its start; the first and last point labels go under the zero line."""
    unit=slide['unit'].strip()
    def value(v):return f'{v:g}{unit}' if unit=='%' else f'{v:g} {unit}'.strip()
    top=y+48;height=440 if carousel else 304;bottom=top+height;left,right=96,984-232
    labels=slide['columns'];maximum=max(v for s in slide['series'] for v in s['values'])
    def point(i,v):return (left+(right-left)*i/(len(labels)-1),bottom-height*v/maximum)
    _rule(draw,occupied,bottom,SOFT,left,right)
    ends=[]
    for series in sorted(slide['series'],key=lambda s:s['focus']):  # the focus line is drawn last, on top
        points=[point(i,v) for i,v in enumerate(series['values'])];color=accent if series['focus'] else SOFT
        draw.line(points,fill=color,width=6 if series['focus'] else 4,joint='curve')
        for x,at in (points[0],points[-1]):draw.ellipse((x-7,at-7,x+7,at+7),fill=color)
        if series['focus']:text(value(series['values'][0]),left,points[0][1]-48,28,36,width=right-left,color=accent)
        ends.append((points[-1][1],series))
    last=None
    for at,series in sorted(ends,key=lambda e:e[0]):
        at=at-18 if last is None else max(at-18,last+8)
        last=text(f'{series["name"]} · {value(series["values"][-1])}',right+16,at,28,36,width=984-right-16,
                  color=accent if series['focus'] else muted)
    end=draw.textlength(labels[-1],font=font(28))
    text(labels[0],left,bottom+12,28,36,width=(right-left)/2-12,color=muted)
    text(labels[-1],right-end,bottom+12,28,36,width=end+1,color=muted)
    return bottom+80


def render(slide,position=1,total=1,carousel=False,name=None):
    """PNG bytes of one slide. `name`: who signs it (author(member)); None, the initial identity's (_signer)."""
    name=_signer(name)
    height=1350 if carousel else 1080;template=slide['template']
    dark=template in ('portada','numero');bg=INK if dark else PAPER;fg=PAPER if dark else INK
    accent=ACCENT if dark else DEEP;muted='#B9BCCB' if dark else SOFT
    image=Image.new('RGB',(1080,height),bg);draw=ImageDraw.Draw(image);occupied=[]
    def text(value,x,y,size,line,width=888,color=fg,highlight=''):
        if not value:return y
        if contrast(color,bg)<4.5:raise ValueError('Contraste insuficiente')
        lines=[];current='';face=font(size)
        for word in value.split():
            if draw.textlength(word,font=face)>width:raise ValueError('Palabra demasiado ancha')
            candidate=(current+' '+word).strip()
            if draw.textlength(candidate,font=face)>width:lines.append(current);current=word
            else:current=candidate
        if current:lines.append(current)
        for row in lines:
            if y+line>height-96:raise ValueError('El contenido desborda la rejilla')
            if highlight:
                left=x
                for word in row.split():
                    draw.text((left,y),word,font=face,fill=accent if word==highlight else color,anchor='lt')
                    left+=draw.textlength(word+' ',font=face)
            else:draw.text((x,y),row,font=face,fill=color,anchor='lt')
            occupied.append((x,y,x+draw.textlength(row,font=face),y+line));y+=line
        return y
    # 6 columns of 128 px, 24 px gutters; all block starts follow the 8 px baseline.
    label=slide['label'].upper();left=96
    if label:
        for char in label:
            if left+draw.textlength(char,font=font(30))>984:raise ValueError('Etiqueta demasiado ancha')
            draw.text((left,96),char,font=font(30),fill=accent,anchor='lt');left+=draw.textlength(char,font=font(30))+1.8
        occupied.append((96,96,left,132))
    if template=='cita':  # the content card: a short accent rule where the label goes, then the post's line
        draw.rectangle((96,104,175,111),fill=accent);occupied.append((96,104,176,112))
    size,leading={'portada':(96,104),'cita':(60,72)}.get(template,(72,80))
    end=text(slide['title'],96,160,size,leading,highlight=slide['highlight'] if template=='portada' else '')
    y=math.ceil((end+32)/8)*8
    if template=='numero':
        end=text(slide['number'],96,y,240,256,width=584,color=accent)
        text(slide['unit'],704,y+128,96,104,width=280)
        y=end+32
    elif template=='pasos':
        for n,step in enumerate(slide['steps'],1):
            text(str(n),96,y,36,48,width=128,color=accent)
            y=text(step,248,y,36,48,width=736)+24
    elif template=='preguntas':
        # Bullets, never numbers: the questions carry no data. The short answer goes under its question, in grey.
        for item in slide['steps']:
            question,answer=question_parts(item)
            draw.ellipse((96,y+11,114,y+29),fill=accent);occupied.append((96,y+11,114,y+29))
            y=text(question,152,y,36,48,width=832)
            y=text(answer,152,y+8,32,44,width=832,color=muted)+32
    elif template=='barras':
        bars=sorted(slide['bars'],key=lambda b:b['value'],reverse=True);maximum=max(b['value'] for b in bars)
        for bar in bars:
            text(f'{bar["label"]} · {bar["value"]:g}',96,y,36,48);y+=56
            right=96+888*bar['value']/maximum
            if right>96:
                # Neutral fill follows the board; the dark outline gives the graphical edge >=3:1.
                draw.rectangle((96,y,right,y+24),fill=accent if bar['focus'] else LINE,outline=accent if bar['focus'] else SOFT,width=2)
                occupied.append((96,y,right,y+24))
            y+=64
    elif template=='lista':
        # Numbered by the template (the text never numbers itself); a short detail after « — » goes under it, in grey.
        for n,item in enumerate(slide['steps'],1):
            head,_,detail=item.partition(DETAIL)
            text(f'{n}.',96,y,36,48,width=128,color=accent)
            y=text(head.strip(),176,y,36,48,width=808)
            y=text(detail.strip(),176,y+4,32,44,width=808,color=muted)+24
    elif template=='tabla':
        y=_table(slide,y,text,draw,occupied,fg,accent,muted)
    elif template=='comparacion':
        y=_comparison(slide,y,text,draw,occupied,fg,accent,muted)
    elif template=='linea':
        y=_line_chart(slide,y,carousel,text,draw,occupied,fg,accent,muted)
    y=text(slide['subtitle'],96,y,40,56,color=muted)+24
    y=text(slide['body'],96,y,36,48)
    source=slide['source'];citation=' · '.join(x for x in (source['label'],source['date']) if x)
    if y>height-240:raise ValueError('El contenido invade la fuente y el pie')
    source_end=text(citation,96,height-224,28,36,color=muted)
    if source_end>height-152:raise ValueError('La fuente invade el pie')
    text(name,96,height-128,28,32)
    number=f'{position}/{total}';text(number,984-draw.textlength(number,font=font(28)),height-128,28,32,width=128)
    if sum((x2-x1)*(y2-y1) for x1,y1,x2,y2 in occupied)>.6*1080*height:raise ValueError('Menos del 40 % de espacio vacío')
    buffer=io.BytesIO();image.save(buffer,format='PNG')
    return buffer.getvalue()


def document(pngs,alts):
    """Tagged PDF: each page is a Figure with an English /Alt, preserved by document uploads.

    LinkedIn's document payload has no per-slide alt field. A raster-only Pillow PDF
    would lose accessibility, so write the small PDF object graph explicitly.
    """
    if not 1<=len(pngs)<=8 or len(alts)!=len(pngs) or any(not a.strip() for a in alts):
        raise ValueError('Cada lámina del PDF necesita alt')
    objects=[b'']*4  # catalog, pages, structure root, parent tree
    def add(value):objects.append(value);return len(objects)
    def stream(data,attrs=''):
        return (f'<< /Length {len(data)} {attrs} >>\nstream\n'.encode()+data+b'\nendstream')
    pages=[];figures=[]
    for i,(raw,alt) in enumerate(zip(pngs,alts)):
        with Image.open(io.BytesIO(raw)) as im:
            width,height=im.size;raster=zlib.compress(im.convert('RGB').tobytes())
        # Lossless RGB: the PDF contains precisely the reviewed PNG pixels.
        bitmap=add(stream(raster,f'/Type /XObject /Subtype /Image /Width {width} /Height {height} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /FlateDecode'))
        commands=f'/Figure <</MCID 0>> BDC q {width} 0 0 {height} 0 0 cm /Im0 Do Q EMC'.encode()
        content=add(stream(commands));page=len(objects)+1
        pages.append(add(f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {width} {height}] /StructParents {i} /Resources << /XObject << /Im0 {bitmap} 0 R >> >> /Contents {content} 0 R >>'.encode()))
        unicode_alt=(b'\xfe\xff'+alt.encode('utf-16-be')).hex()
        figures.append(add(f'<< /Type /StructElem /S /Figure /P 3 0 R /Pg {page} 0 R /Alt <{unicode_alt}> /K << /Type /MCR /Pg {page} 0 R /MCID 0 >> >>'.encode()))
    objects[0]=b'<< /Type /Catalog /Pages 2 0 R /StructTreeRoot 3 0 R /MarkInfo << /Marked true >> /Lang (en-US) >>'
    objects[1]=f'<< /Type /Pages /Count {len(pages)} /Kids [{" ".join(f"{n} 0 R" for n in pages)}] >>'.encode()
    objects[2]=f'<< /Type /StructTreeRoot /K [{" ".join(f"{n} 0 R" for n in figures)}] /ParentTree 4 0 R /ParentTreeNextKey {len(pages)} >>'.encode()
    objects[3]=f'<< /Nums [{" ".join(f"{i} [{n} 0 R]" for i,n in enumerate(figures))}] >>'.encode()
    out=io.BytesIO();out.write(b'%PDF-1.7\n%\xe2\xe3\xcf\xd3\n');offsets=[0]
    for n,value in enumerate(objects,1):
        offsets.append(out.tell());out.write(f'{n} 0 obj\n'.encode()+value+b'\nendobj\n')
    xref=out.tell();out.write(f'xref\n0 {len(offsets)}\n0000000000 65535 f \n'.encode())
    for offset in offsets[1:]:out.write(f'{offset:010d} 00000 n \n'.encode())
    out.write(f'trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode())
    return out.getvalue()


def fallback(name=None):
    """Fixed, non-factual brand card; safe even when every optional image provider is unavailable. `name`: who signs it
    (_signer)."""
    name=_signer(name)
    return {'template':'portada','label':'0ff1ce','title':'A question worth exploring','subtitle':'Ideas, tradeoffs and practical decisions.',
            'body':'','number':'','unit':'','steps':[],'bars':[],
            'source':{'ref':'','label':'','date':'','estimate':False},
            'alt':f'A question worth exploring. A card from {name} about ideas, tradeoffs and practical decisions.',
            'highlight':'question'}
