import json
import re
from .db import connect
from .ingest import normalized
from .providers import DIMENSIONS, embedding_model, embeddings

AGENTS={'posicionamiento':'Definir comprador, nicho y propuesta de valor con evidencia del usuario.',
        'perfil':'Diseñar un perfil coherente con el posicionamiento y la evidencia del usuario.'}

# A lower RRF constant preserves strong top-ranked evidence. With k=60 and
# equal weights, weak overlap in two lists could bury a semantic rank-1 result.
RRF_K=20
CHANNEL_WEIGHTS={'lexical':1.0,'semantic':2.0}

def unit(uid):
    with connect() as c:
        row=c.execute('SELECT * FROM units WHERE id=%s AND active',(uid,)).fetchone()
        if not row:raise ValueError('Unidad no encontrada')
        row['sources']=c.execute('SELECT e.key,e.original FROM evidence e JOIN unit_evidence ue ON e.key=ue.source_key WHERE ue.unit_id=%s ORDER BY e.key',(uid,)).fetchall()
        row['relations']=c.execute('SELECT * FROM edges WHERE source_id=%s OR target_id=%s',(uid,uid)).fetchall()
        return row

def search(query,agent=None,limit=6,mode='lexical'):
    if agent is not None and agent not in AGENTS:raise ValueError('Agente desconocido')
    if not query.strip() or len(query)>6000:raise ValueError('Consulta vacía o demasiado larga')
    if mode not in ('lexical','hybrid'):raise ValueError('Modo inválido')
    if not 1<=limit<=20:raise ValueError('Límite inválido')
    tokens=re.findall(r'[a-z0-9]+',normalized(query))
    tsquery=' | '.join(tokens)
    if not tsquery:return {'mode':'lexical','results':[],'relations':[]}
    candidates={};warnings=[];semantic_top_id=None
    def add(rows,channel):
        for rank,r in enumerate(rows,1):
            item=candidates.setdefault(r['id'],dict(r,score=0.0,channels=[]))
            item['score']+=CHANNEL_WEIGHTS[channel]/(RRF_K+rank);item['channels'].append(channel)
    with connect() as c:
        lexical=c.execute('''WITH terms AS (
                SELECT unnest(tsvector_to_array(to_tsvector('spanish',%s))) AS term
            ), hits AS (
                SELECT ch.unit_id,t.term,
                    max(ts_rank_cd(ch.search,to_tsquery('spanish',quote_literal(t.term)),32)) AS tf,
                    CASE WHEN to_tsvector('spanish',u.title) @@ to_tsquery('spanish',quote_literal(t.term)) THEN 0.15 ELSE 0 END AS title_bonus
                FROM terms t JOIN chunks ch ON ch.search @@ to_tsquery('spanish',quote_literal(t.term))
                JOIN units u ON u.id=ch.unit_id WHERE ch.active AND u.active
                GROUP BY ch.unit_id,t.term,u.title
            ), frequencies AS (SELECT term,count(*) AS df FROM hits GROUP BY term),
            scores AS (
                SELECT h.unit_id,sum((h.tf+h.title_bonus)*ln(1.0+(SELECT count(*) FROM units WHERE active)/(f.df+1.0))) AS rank
                FROM hits h JOIN frequencies f USING(term) GROUP BY h.unit_id
            ) SELECT u.id,u.title,u.session,u.metadata,s.rank
                FROM scores s JOIN units u ON u.id=s.unit_id ORDER BY s.rank DESC,u.id LIMIT 60''',(query,)).fetchall()
        add(lexical,'lexical')
        actual_mode='lexical'
        if mode=='hybrid':
            n=c.execute('''SELECT count(*) AS n FROM chunks ch JOIN embedding_cache e ON ch.sha256=e.content_hash
                WHERE ch.active AND e.model=%s AND e.dimensions=%s''',(embedding_model(),DIMENSIONS)).fetchone()['n']
            if n:
                vector=embeddings([query])[0]
                rows=c.execute('''SELECT u.id,u.title,u.session,u.metadata,min(e.embedding <=> %s::vector) AS distance
                    FROM chunks ch JOIN units u ON u.id=ch.unit_id JOIN embedding_cache e ON e.content_hash=ch.sha256
                    WHERE ch.active AND u.active AND e.model=%s AND e.dimensions=%s
                    GROUP BY u.id ORDER BY distance,u.id LIMIT 60''',(json.dumps(vector),embedding_model(),DIMENSIONS)).fetchall()
                add(rows,'semantic');actual_mode='hybrid'
                if rows:semantic_top_id=rows[0]['id']
                total=c.execute('SELECT count(*) AS n FROM chunks WHERE active').fetchone()['n']
                if n<total:warnings.append('Índice semántico parcial: faltan fragmentos por indexar.')
            else:warnings.append('Sin embeddings: búsqueda textual disponible; no se simuló búsqueda semántica.')
        for item in candidates.values():
            # Affinity is a small preference, never a permission or filter.
            if agent in item['metadata'].get('affinities',[]):item['score']*=1.05
        results=sorted(candidates.values(),key=lambda r:(-r['score'],r['id']))[:limit]
        selected=[r['id'] for r in results]
        edges=c.execute("SELECT * FROM edges WHERE status='explicit_reference' AND (source_id=ANY(%s) OR target_id=ANY(%s)) LIMIT 20",(selected,selected)).fetchall()
    return {'mode':actual_mode,'requested_mode':mode,'results':results,'relations':edges,'warnings':warnings,'scope':[1,2,3,4,5,6],
            'semantic_top_id':semantic_top_id,'ranking':{'method':'weighted_rrf','k':RRF_K,'weights':CHANNEL_WEIGHTS}}
