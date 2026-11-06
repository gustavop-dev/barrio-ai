"""Read-only content fingerprints for every legacy table, including all vectors."""
import hashlib
import json
from knowledge.db import connect

TABLES = {
 'source_files':'path', 'units':'id', 'evidence':'key', 'unit_revisions':'unit_id,sha256',
 'unit_evidence':'unit_id,source_key', 'chunks':'id', 'embedding_cache':'content_hash,model,dimensions',
 'edges':'source_id,target_id,kind', 'memory':'id', 'usage_ledger':'id', 'runs':'id',
}
def snapshot():
    result={}
    with connect() as c:
        c.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
        for table,order in TABLES.items():
            digest=hashlib.sha256();count=0
            with c.cursor(name='snapshot_'+table) as cursor:
                cursor.execute(f'SELECT row_to_json(t)::text AS data FROM {table} t ORDER BY {order}')
                for row in cursor:
                    digest.update(row['data'].encode());digest.update(b'\n');count+=1
            result[table]={'count':count,'sha256':digest.hexdigest()}
    return result
if __name__=='__main__':print(json.dumps(snapshot(),indent=2))
