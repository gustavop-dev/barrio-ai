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
AUTHOR='Gustavo'


class _Text(HTMLParser):
    def __init__(self):super().__init__();self.parts=[]
    def handle_data(self,data):self.parts.append(data)
    def handle_endtag(self,tag):
        if tag in ('p','li','h1','h2','h3','tr','section','pre'):self.parts.append('\n')


@lru_cache(maxsize=1)
def rule():
    raw=(RESOURCE/'infografias.html').read_text(encoding='utf-8')
    parser=_Text();parser.feed(raw)
    return '\n'.join(line.strip() for line in ''.join(parser.parts).splitlines() if line.strip())


def version():return hashlib.sha256(rule().encode()).hexdigest()
def with_rule(system):return system+'\n\n<regla_infografias version="'+version()+'">\n'+rule()+'\n</regla_infografias>'
def obj(**fields):return {'type':'object','additionalProperties':False,'required':list(fields),'properties':fields}
def string():return {'type':'string'}
def array(items):return {'type':'array','items':items}
def enum(*values):return {'type':'string','enum':list(values)}

SOURCE=obj(ref=string(),label=string(),date=string(),estimate={'type':'boolean'})
SLIDE=obj(template=enum('portada','pasos','barras','numero','cierre','preguntas'),label=string(),title=string(),subtitle=string(),
          body=string(),number=string(),unit=string(),steps=array(string()),
          bars=array(obj(label=string(),value={'type':'number'},focus={'type':'boolean'})),
          source=SOURCE,alt=string(),highlight=string())
DESIGN_SCHEMA=obj(slides=array(SLIDE))
CHOICE_SCHEMA=obj(kind=enum('foto','infografia','carrusel'),reason=string(),
                  photos=array(obj(id=string(),reason=string(),alt=string(),edit=enum('none','light','straighten','crop','distractions'),
                                   edit_reason=string(),instruction=string(),instruction_kind=enum('none','original','crop','edit','unsafe'))))


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


# «preguntas»: 2–4 questions for the audience in `steps`, as bullets; the text after the «?» is an optional short answer.
QUESTIONS=(2,4)
LIST_MARK=re.compile(r'^\s*(?:\d+\s*[.):-]|[-•*·]|[A-Za-z]\))\s*')


def question_parts(item):
    """(question, answer) of a «preguntas» item: up to the first «?», then the optional short answer."""
    question,mark,answer=item.partition('?')
    return (question.strip()+mark,answer.strip(' -–—:\n'))


def source_refs(public,sources):
    return {str(x['key']) for x in public if 'key' in x}|{str(x['id']) for x in sources if 'id' in x}


def validate(design,kind,public=(),sources=()):
    schema_check(design,DESIGN_SCHEMA)
    slides=design['slides'];carousel=kind=='carrusel'
    if not ((3<=len(slides)<=8) if carousel else len(slides)==1):raise ValueError('Número de láminas inválido')
    if carousel:
        if slides[0]['template']!='portada':raise ValueError('El carrusel empieza con portada')
        if slides[-1]['template']!='cierre' or not slides[-1]['title'].endswith('?'):raise ValueError('El cierre es una pregunta')
        if any(s['template']=='portada' for s in slides[1:]):raise ValueError('Una sola portada')
    for slide in slides:
        title=slide['title'];template=slide['template'];source=slide['source']
        texts=[title,slide['subtitle'],slide['body'],slide['number'],slide['unit'],*slide['steps'],
               *[b['label'] for b in slide['bars']],source['label'],source['date']]
        if not title.strip() or len(title.split())>8:raise ValueError('Titular: de 1 a 8 palabras')
        if sum(len(t.split()) for t in texts)+len(slide['label'].split())> (30 if carousel else 40):raise ValueError('Demasiadas palabras')
        if re.search(r'[#\U0001F000-\U0010FFFF\u2600-\u27BF]',slide['label']):raise ValueError('Etiqueta sin decoración')
        for text in texts+[slide['alt']]:
            if '#' in text or '!!' in text or any(ord(c)>=0x1F000 or 0x2600<=ord(c)<=0x27BF for c in text):
                raise ValueError('Sin emojis, hashtags ni dobles exclamaciones')
            if shouting(text):
                raise ValueError(f'Mayúsculas solo en etiquetas: «{shouting(text)[0]}» (las siglas conocidas, como AI, '
                                 'MVP o CTO, sí valen)')
        if not 8<=len(slide['alt'].strip())<=1500:raise ValueError('Falta texto alternativo descriptivo')
        if re.search(r'follow me|subscribe|sígueme', ' '.join(texts),re.I):raise ValueError('El cierre invita a conversar')
        if template=='portada':
            if not cover_case_ok(title):raise ValueError('Portada en minúsculas salvo primera letra y siglas conocidas')
            if slide['highlight'] not in title.split() or len(slide['highlight'].split())!=1:raise ValueError('Una palabra de acento en la portada')
        if template=='pasos' and not 3<=len(slide['steps'])<=5:raise ValueError('De 3 a 5 pasos')
        if template=='preguntas':
            low,high=QUESTIONS
            if not low<=len(slide['steps'])<=high:raise ValueError(f'De {low} a {high} preguntas en steps')
            for item in slide['steps']:
                if LIST_MARK.match(item):raise ValueError('Preguntas sin numerar ni viñetas en el texto: la plantilla las dibuja')
                question,answer=question_parts(item)
                if not question.endswith('?') or len(question)<4:raise ValueError('Cada elemento de preguntas empieza por una pregunta que termina en «?»')
                if '?' in answer:raise ValueError('Una pregunta por elemento; la respuesta corta va después del «?»')
        if template not in ('pasos','preguntas') and slide['steps']:raise ValueError('Pasos o preguntas fuera de su plantilla')
        if template=='barras':
            if not 1<=len(slide['bars'])<=5 or sum(b['focus'] for b in slide['bars'])!=1:raise ValueError('De 1 a 5 barras, un foco')
            if any(b['value']<0 for b in slide['bars']) or max(b['value'] for b in slide['bars'])<=0:raise ValueError('Barras desde cero, valores positivos')
            if any(b['value']!=round(b['value']) for b in slide['bars']):raise ValueError('Valores redondeados; corregir los datos antes de dibujar')
        elif slide['bars']:raise ValueError('Barras fuera de su plantilla')
        if template=='numero':
            if not re.fullmatch(r'\d{1,4}',slide['number']) or not slide['unit'].strip():raise ValueError('Cifra redondeada con unidad')
        elif slide['number'] or slide['unit']:raise ValueError('Cifra fuera de su plantilla')
        digits=re.findall(r'\S*\d\S*',' '.join(texts[:-2]))
        factual=template in ('numero','barras') or bool(digits)
        if factual or source['ref']:
            if source['ref'] not in source_refs(public,sources) or not source['label'] or not source['date']:
                # Say what made it a figure, so the one correction can fix it instead of repeating the same design.
                why=(f'la plantilla {template} siempre muestra un dato' if template in ('numero','barras')
                     else 'hay cifras en el texto: '+', '.join(f'«{d}»' for d in digits[:3]) if digits else 'cita una fuente')
                raise ValueError(f'Dato sin fuente pública identificable y fecha ({why}). Sin una fuente de public_facts o '
                                 'sources, quita las cifras; para preguntas a la audiencia usa la plantilla preguntas, sin numerarlas')
        if source['estimate'] and 'estimate' not in source['label'].lower():raise ValueError('La estimación debe decir estimate')
    return design


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


def render(slide,position=1,total=1,carousel=False):
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
    end=text(slide['title'],96,160,96 if template=='portada' else 72,104 if template=='portada' else 80,
             highlight=slide['highlight'] if template=='portada' else '')
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
    y=text(slide['subtitle'],96,y,40,56,color=muted)+24
    y=text(slide['body'],96,y,36,48)
    source=slide['source'];citation=' · '.join(x for x in (source['label'],source['date']) if x)
    if y>height-240:raise ValueError('El contenido invade la fuente y el pie')
    source_end=text(citation,96,height-224,28,36,color=muted)
    if source_end>height-152:raise ValueError('La fuente invade el pie')
    text(AUTHOR,96,height-128,28,32)
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


def fallback():
    """Fixed, non-factual brand card; safe even when every optional image provider is unavailable."""
    return {'template':'portada','label':'0ff1ce','title':'A question worth exploring','subtitle':'Ideas, tradeoffs and practical decisions.',
            'body':'','number':'','unit':'','steps':[],'bars':[],
            'source':{'ref':'','label':'','date':'','estimate':False},
            'alt':'A question worth exploring. A card from Gustavo about ideas, tradeoffs and practical decisions.',
            'highlight':'question'}
