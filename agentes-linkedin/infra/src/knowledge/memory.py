import uuid
from psycopg.types.json import Jsonb
from .db import connect

def latest(confirmed_only=False):
    with connect() as c:
        where="WHERE namespace='user' AND status='confirmed'" if confirmed_only else ''
        rows=c.execute('SELECT DISTINCT ON (namespace,key) * FROM memory '+where+' ORDER BY namespace,key,version DESC').fetchall()
    return rows

def propose(namespace,key,value,author,evidence,expected_version=0,on_write=None):
    if namespace not in ('user','working') or not key.strip() or not evidence.strip():raise ValueError('Memoria requiere espacio, clave y procedencia')
    with connect() as c:
        c.execute('SELECT pg_advisory_xact_lock(103504)')
        version=c.execute('SELECT coalesce(max(version),0) AS v FROM memory WHERE namespace=%s AND key=%s',(namespace,key)).fetchone()['v']
        if version!=expected_version:raise ValueError('Conflicto de versión; volver a leer la memoria')
        mid=str(uuid.uuid4())
        c.execute('INSERT INTO memory(id,namespace,key,version,value,status,author,evidence) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',(mid,namespace,key,version+1,Jsonb(value),'proposed',author,evidence))
        result={'id':mid,'version':version+1,'status':'proposed'}
        if on_write:on_write(c,result)
    return result

def confirm(mid,expected_version,on_write=None):
    """Only exposed on an authenticated human endpoint, never as an agent tool."""
    with connect() as c:
        c.execute('SELECT pg_advisory_xact_lock(103504)')
        row=c.execute('SELECT * FROM memory WHERE id=%s',(mid,)).fetchone()
        if not row or row['namespace']!='user':raise ValueError('Solo hechos del usuario pueden confirmarse')
        version=c.execute('SELECT max(version) AS v FROM memory WHERE namespace=%s AND key=%s',(row['namespace'],row['key'])).fetchone()['v']
        if row['version']!=expected_version or version!=expected_version:raise ValueError('Versión desactualizada')
        if row['status']=='confirmed':
            result={'id':str(row['id']),'version':version,'status':'confirmed'}
            if on_write:on_write(c,result)
            return result
        new_id=str(uuid.uuid4())
        c.execute('INSERT INTO memory(id,namespace,key,version,value,status,author,evidence) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',(new_id,row['namespace'],row['key'],version+1,Jsonb(row['value']),'confirmed','user',row['evidence']))
        result={'id':new_id,'version':version+1,'status':'confirmed'}
        if on_write:on_write(c,result)
    return result

def publishable(value):
    return isinstance(value,dict) and value.get('uso_publico') is True

def retired(value):
    """A confirmed tombstone ({'retirado': true}) withdraws a fact without deleting its history."""
    return isinstance(value,dict) and value.get('retirado') is True

def current_version(namespace,key):
    with connect() as c:
        return c.execute('SELECT coalesce(max(version),0) AS v FROM memory WHERE namespace=%s AND key=%s',(namespace,key)).fetchone()['v']

def confirmed_history(namespace,key):
    """Confirmed versions of one key, newest first."""
    with connect() as c:
        return c.execute("SELECT version,value,created_at FROM memory WHERE namespace=%s AND key=%s AND status='confirmed' ORDER BY version DESC",
                         (namespace,key)).fetchall()

def set_fact(key,value,author,evidence,on_write=None):
    """Human-only: propose and confirm a user fact in one step (an answer, a correction or a withdrawal)."""
    proposed=propose('user',key,value,author,evidence,expected_version=current_version('user',key))
    return confirm(proposed['id'],proposed['version'],on_write=on_write)

def confirmed_blocks():
    """Confirmed user facts split by `uso_publico`. Only a dict value with uso_publico=true may be
    attributed to the user in public text; anything else is private guidance (the safe default)."""
    public,private=[],[]
    for row in latest(True):
        value=row['value'];base={'key':row['key'],'version':row['version']}
        if retired(value):continue
        if publishable(value):
            fact=value['texto'] if isinstance(value.get('texto'),str) else {k:v for k,v in value.items() if k!='uso_publico'}
            public.append(dict(base,fact=fact))
        else:private.append(dict(base,guidance=value))
    return public,private
