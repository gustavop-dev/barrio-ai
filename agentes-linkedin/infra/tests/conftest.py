import uuid
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo
from knowledge import db,ingest

@pytest.fixture(scope='session',autouse=True)
def isolated_database():
    original=db.dsn
    name='test_'+uuid.uuid4().hex
    with db.connect() as c:c.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(name)))
    db.dsn=lambda:make_conninfo(original(),options=f'-c search_path={name},public')
    db.init();ingest.ingest()
    yield
    db.dsn=original
    with db.connect() as c:c.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(name)))

@pytest.fixture(autouse=True)
def no_network_and_clean_state(monkeypatch):
    monkeypatch.setenv('LIVE_PROVIDERS','false')
    def blocked(*args,**kwargs):raise AssertionError('Las pruebas no deben llamar a proveedores')
    monkeypatch.setattr('httpx.post',blocked)
    with db.connect() as c:
        for table in ['usage_ledger','memory','runs','embedding_cache']:c.execute('DELETE FROM '+table)
