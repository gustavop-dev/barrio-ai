import os
from pathlib import Path
from dotenv import load_dotenv

INFRA = Path(__file__).resolve().parents[2]
load_dotenv(INFRA / '.env')

def root():
    if os.environ.get('SOURCE_ROOT'):return Path(os.environ['SOURCE_ROOT'])
    return INFRA.parents[1]

def dsn():
    if os.environ.get('DATABASE_URL'):return os.environ['DATABASE_URL']
    return 'postgresql://knowledge:' + os.environ['POSTGRES_PASSWORD'] + '@127.0.0.1:55439/knowledge'

def live(provider):
    if os.environ.get('LIVE_PROVIDERS', 'false').lower() != 'true':
        raise ValueError('Proveedores desactivados: configurar LIVE_PROVIDERS=true para solicitudes pagadas.')
    key = os.environ.get(provider.upper() + '_API_KEY')
    if not key:
        raise ValueError('Falta ' + provider.upper() + '_API_KEY en el entorno privado.')
    return key
