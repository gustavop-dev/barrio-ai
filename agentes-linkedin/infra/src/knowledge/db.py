from pathlib import Path
import psycopg
from psycopg.rows import dict_row
from .config import dsn

def connect():
    # Django's test runner changes the actual database name. Never bypass it
    # using a production DATABASE_URL when called inside Django.
    from django.conf import settings
    if settings.configured:
        from django.db import connections
        cfg=connections['default'].settings_dict
        return psycopg.connect(dbname=cfg['NAME'],user=cfg['USER'],password=cfg['PASSWORD'],
            host=cfg['HOST'],port=cfg['PORT'],row_factory=dict_row,connect_timeout=5)
    return psycopg.connect(dsn(), row_factory=dict_row,connect_timeout=5)

def init():
    with connect() as c:
        c.execute(Path(__file__).with_name('schema.sql').read_text())

def status():
    with connect() as c:
        result = {name: c.execute('SELECT count(*) AS n FROM '+name).fetchone()['n'] for name in ['units','chunks','evidence','edges','embedding_cache','runs','memory']}
        result['classes'] = c.execute('SELECT session,count(*) AS units FROM units WHERE active GROUP BY session ORDER BY session').fetchall()
        result['usage'] = c.execute("SELECT provider,status,count(*) AS requests,sum(reserved_usd) AS reserved_usd,sum(actual_usd) AS actual_usd FROM usage_ledger GROUP BY provider,status").fetchall()
        result['review'] = 'Validación técnica local; no equivale a revisión humana ni a verificación integral de cada afirmación.'
        return result
