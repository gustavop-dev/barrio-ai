import hashlib
import json
import re
import unicodedata
from collections import Counter
import tiktoken
from psycopg.types.json import Json,Jsonb
from .config import root
from .db import connect

ENC = tiktoken.get_encoding('cl100k_base')
VERSION = 'literal-sections-v1'
FIELDS = ['explanation','task','application','decisions','context','limits_errors','inputs_outputs','examples_counterexamples','exercises_resources','related_learning','glossary']
TOPICS = {
 'comprador': ['buyer persona','comprador','cliente ideal','nicho'],
 'perfil': ['perfil','titular','acerca de','banner'],
 'barrio': ['barrio','divulgador','aliado','comunidad'],
 'contenido': ['publicacion','contenido','post','pilar'],
 'escritura': ['copy','gancho','titulo','redaccion','estructura'],
 'investigacion': ['investigacion','referente','audiencia'],
}

def canonical(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))

def digest(value):
    return hashlib.sha256(value if isinstance(value,bytes) else value.encode()).hexdigest()

def normalized(text):
    return ''.join(c for c in unicodedata.normalize('NFD',text.lower()) if unicodedata.category(c)!='Mn')

def fragments(unit):
    """Verbatim sections; no summarization. Title is repeated solely for retrieval."""
    for field in FIELDS:
        value = unit.get(field)
        if not value:
            continue
        text = value if isinstance(value,str) else json.dumps(value,ensure_ascii=False)
        start = 0
        while start < len(text):
            end = min(start+2400,len(text))
            if end<len(text):
                boundary=text.rfind(' ',start+1200,end)
                if boundary>start: end=boundary+1
            raw=text[start:end]
            content=(unit['title']+'\n'+field+'\n'+raw).replace('\x00','\\u0000')
            while len(ENC.encode(content))>1800:
                end=start+(end-start)//2
                if end<=start: raise ValueError('Título excesivamente largo')
                raw=text[start:end];content=(unit['title']+'\n'+field+'\n'+raw).replace('\x00','\\u0000')
            yield field,start,end,content
            start=end

def paths():
    first='LinkedIn Sales - Entrega clase 01/01 - Clase 01/quality/'
    review='LinkedIn Sales - Procesamiento completo/revision-independiente/'
    return [(1,first+'aprendizajes.json')]+[(n,review+f'session-{n:02}-revisada.json') for n in range(2,7)]

def load_corpus():
    base=root(); files={}; units=[]; evidence={}; assignments={}
    def read(path):
        raw=(base/path).read_bytes();files[path]=digest(raw);return json.loads(raw)
    for session,path in paths():
        data=read(path)
        for i,unit in enumerate(data['learning_units']):
            units.append((session,path,i,unit))
    first='LinkedIn Sales - Entrega clase 01/01 - Clase 01/quality/'
    sources=read(first+'sources.json')['data']
    for item in sources['transcript']+sources['materials']+read(first+'visual/evidence.json')['visuals']:
        evidence['01:'+item['id']]={'key':'01:'+item['id'],'session':1,'source_id':item['id'],'original':item}
    path='LinkedIn Sales - Procesamiento completo/revision-independiente/fuentes.jsonl'
    raw=(base/path).read_bytes();files[path]=digest(raw)
    for line in raw.decode().splitlines():
        item=json.loads(line)
        if 2<=int(item['session'])<=6:evidence[item['key']]=item
    path='agentes-linkedin/equipos/estrategia-perfil/asignacion-clase-02.json'
    if (base/path).exists():
        for item in read(path)['assignments']:assignments[item['unit_id']]=item
    # Reuse only reference lists from the old class-1 design, never its synthesized rules.
    path='agentes-linkedin/equipos/estrategia-perfil/base-clase-01.json'
    if (base/path).exists():
        for rule in read(path)['rules']:
            for uid in rule.get('unit_ids',[]):
                item=assignments.setdefault(uid,{'agents':[]})
                item['agents']=sorted(set(item['agents']+rule.get('agents',[])))
    policy=read('LinkedIn Sales - Procesamiento completo/conocimiento-para-agentes/politica-de-uso.json')
    ids=[u['id'] for _,_,_,u in units]
    if len(ids)!=len(set(ids)):raise ValueError('IDs de unidad duplicados')
    missing=[f'{s:02}:{sid}' for s,_,_,u in units for sid in u.get('source_ids',[]) if f'{s:02}:{sid}' not in evidence]
    if missing:raise ValueError('Evidencias sin resolver: '+str(missing[:10]))
    return files,units,evidence,assignments,policy

def ingest():
    files,units,evidence,assignments,_=load_corpus()
    totals=Counter();ids={u['id'] for _,_,_,u in units}
    with connect() as c:
        c.execute('SELECT pg_advisory_xact_lock(103501)')
        for path,sha in files.items():
            c.execute('INSERT INTO source_files(path,sha256) VALUES(%s,%s) ON CONFLICT(path) DO UPDATE SET sha256=excluded.sha256,imported_at=now()', (path,sha))
        for key,item in evidence.items():
            c.execute('INSERT INTO evidence VALUES(%s,%s,%s) ON CONFLICT(key) DO UPDATE SET original=excluded.original',(key,item['session'],Json(item)))
        c.execute('UPDATE units SET active=false');c.execute('UPDATE chunks SET active=false')
        for session,path,i,unit in units:
            uid=unit['id']; a=assignments.get(uid,{})
            c.execute('''INSERT INTO unit_revisions(unit_id,sha256,original,source_path,source_sha256,pointer)
                VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING''',
                (uid,digest(canonical(unit)),Json(unit),path,files[path],f'/learning_units/{i}'))
            searchable=normalized(unit['title']+' '+str(unit.get('explanation','')))
            metadata={'topics':[t for t,terms in TOPICS.items() if any(term in searchable for term in terms)],
                      'tag_origin':'deterministic-keywords-v1; derived, not course facts',
                      'affinities':a.get('agents',[]),'assignment_status':a.get('status'),
                      'review':'existing_extraction_or_targeted_review; human_review_pending',
                      'chunk_version':VERSION}
            c.execute('''INSERT INTO units VALUES(%s,%s,%s,%s,%s,%s,%s,%s,true)
                ON CONFLICT(id) DO UPDATE SET title=excluded.title,original=excluded.original,sha256=excluded.sha256,
                source_path=excluded.source_path,pointer=excluded.pointer,metadata=excluded.metadata,active=true''',
                (uid,session,unit['title'],Json(unit),digest(canonical(unit)),path,f'/learning_units/{i}',Jsonb(metadata)))
            c.execute('DELETE FROM unit_evidence WHERE unit_id=%s',(uid,))
            for sid in set(unit.get('source_ids',[])):
                c.execute('INSERT INTO unit_evidence VALUES(%s,%s)',(uid,f'{session:02}:{sid}'))
            for field,start,end,text in fragments(unit):
                sha=digest(text);cid=digest(uid+VERSION+field+str(start)+sha)
                c.execute('''INSERT INTO chunks(id,unit_id,section,text,sha256,tokens) VALUES(%s,%s,%s,%s,%s,%s)
                    ON CONFLICT(id) DO UPDATE SET active=true''',(cid,uid,f'{field}:{start}:{end}',text,sha,len(ENC.encode(text))))
                totals['chunks']+=1;totals['tokens']+=len(ENC.encode(text))
            totals['units']+=1
        c.execute('DELETE FROM edges')
        # Insert relations only after all their endpoints exist.
        for _,_,_,unit in units:
            uid=unit['id']
            # Only explicit unit IDs; prose such as "unidad 3" is not guessed.
            for target in set(re.findall(r'LI-\d{2}-[A-Z0-9-]+',str(unit.get('related_learning',''))))&ids:
                if target!=uid:
                    c.execute('INSERT INTO edges VALUES(%s,%s,%s,%s,%s)',(uid,target,'related','original.related_learning','explicit_reference'))
                    totals['edges']+=1
        # Detect source changes while the transaction was being built.
        if any(digest((root()/p).read_bytes())!=sha for p,sha in files.items()):raise ValueError('Las fuentes cambiaron durante la importación')
    return dict(totals,source_files=len(files),evidence=len(evidence),source_integrity=True,scope='01–06')

def verify():
    files,units,_,_,_=load_corpus()
    errors=[]
    with connect() as c:
        indexed={r['id']:r for r in c.execute('SELECT id,original,sha256 FROM units WHERE active')}
        for _,_,_,u in units:
            if u['id'] not in indexed or indexed[u['id']]['original']!=u: errors.append(u['id'])
        if set(indexed)!={u['id'] for _,_,_,u in units}:errors.append('active_unit_set')
        for r in c.execute('SELECT path,sha256 FROM source_files'):
            if files.get(r['path'])!=r['sha256']:errors.append(r['path'])
    return {'passed':not errors,'units':len(units),'errors':errors,'human_review':False}
